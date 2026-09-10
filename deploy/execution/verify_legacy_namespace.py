"""Offline acceptance of the retained P3 namespace; never runs --execute."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

# This verifier lives beside the trusted, versioned deployment launcher.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import legacy_p3_namespace as legacy


PROBE = '''
import errno, json, os
from pathlib import Path
paths = [
 '/home/ark/workspace/dehps/apps/worker-python/dehps/config.py',
 '/home/ark/workspace/dehps-m4-historical-exec-runtime-cd069c1/apps/worker-python/dehps/config.py',
 '/home/ark/workspace/dehps/apps/worker-python/.venv/lib/python3.14/site-packages/numpy/__init__.py',
]
status = dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
assert status['NoNewPrivs'].strip() == '1'
assert os.getuid() == 1000
denials = []
for path in paths:
    try:
        fd = os.open(path, os.O_WRONLY)
        os.close(fd)
    except OSError as exc:
        assert exc.errno == errno.EROFS, (path, exc)
        denials.append({'path':path,'errno':exc.errno})
    else:
        raise AssertionError('release allows write-open: ' + path)
assert os.statvfs('/home/ark/workspace/dehps/runtime').f_flag & os.ST_RDONLY
assert os.statvfs('/home/ark/workspace/dehps/data/output').f_flag & os.ST_RDONLY
print(json.dumps({'uid':os.getuid(),'no_new_privileges':True,'denials':denials,
                  'inspection_data_mounts_readonly':True}))
'''


def verify(bundle: Path) -> dict:
    records = []
    for entry, (selected, _, _) in legacy.ENTRIES.items():
        result = subprocess.run(legacy.command(bundle, entry, True), capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f'{entry} inspection failed: {result.stderr}')
        first = json.loads(result.stdout.splitlines()[0])
        assert first['root'] == str(selected), first
        assert first['config_file'] == str(selected / 'apps/worker-python/dehps/config.py'), first
        assert first['prefix'] == str(legacy.ORIGINAL / 'apps/worker-python/.venv'), first
        assert 'usage:' in result.stdout
        records.append({'entry':entry,'imports':first,
                        'stdout_sha256':sha256(result.stdout.encode()).hexdigest()})
    argv = legacy.command(bundle, 'forward', True)
    argv = argv[:argv.index('-c') + 1] + [PROBE]
    probe = subprocess.run(argv, capture_output=True, text=True)
    if probe.returncode:
        raise RuntimeError(f'namespace permissions failed: {probe.stderr}')
    return {'schema':'dehps-legacy-namespace-verification.v1',
            'verified_at':datetime.now(timezone.utc).isoformat(),
            'launcher_sha256':sha256(Path(legacy.__file__).read_bytes()).hexdigest(),
            'bundle':str(bundle),'entries':records,'permissions':json.loads(probe.stdout),
            'production_execution':False,'scientific_acceptance':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('preserve existing verification records; choose a new output path')
    evidence = verify(args.bundle)
    with args.output.open('x') as stream:
        json.dump(evidence, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'entries_verified':len(evidence['entries']),
                      'launcher_sha256':evidence['launcher_sha256'],
                      'permissions':evidence['permissions'], 'evidence':str(args.output)}))
