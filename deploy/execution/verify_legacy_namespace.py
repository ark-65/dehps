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
import errno, json, os, runpy, subprocess, sys
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
    # A root-owned installed release can fail DAC before the VFS reports EROFS.
    # Require the mount flag separately so EACCES cannot hide a writable mount.
    assert os.statvfs(path).f_flag & os.ST_RDONLY, path
    try:
        fd = os.open(path, os.O_WRONLY)
        os.close(fd)
    except OSError as exc:
        assert exc.errno in (errno.EROFS, errno.EACCES), (path, exc)
        denials.append({'path':path,'errno':exc.errno,'mount_readonly':True})
    else:
        raise AssertionError('release allows write-open: ' + path)
assert os.statvfs('/home/ark/workspace/dehps/runtime').f_flag & os.ST_RDONLY
assert os.statvfs('/home/ark/workspace/dehps/data/output').f_flag & os.ST_RDONLY
git_records = []
for root, expected in [
 ('/home/ark/workspace/dehps', 'ac0ef7832c6f13c7500b3f7d67731420b575c0f4'),
 ('/home/ark/workspace/dehps-m4-historical-exec-runtime-cd069c1', 'cd069c15110b0af0f3a83ff619272c14e4748edc'),
]:
    metadata = Path(root) / '.git'
    assert metadata.is_dir() and not metadata.is_symlink(), metadata
    assert os.statvfs(metadata).f_flag & os.ST_RDONLY, metadata
    assert not (metadata / 'objects/info/alternates').exists()
    assert not (metadata / 'shallow').exists()
    def git(*args):
        return subprocess.check_output(['/usr/bin/git', '-C', root, *args], text=True).strip()
    assert git('rev-parse', 'HEAD') == expected
    assert not git('status', '--porcelain'), root
    assert not git('remote'), root
    git('fsck', '--full', '--no-reflogs')
    # A parent and its original source object must remain accessible after the
    # development repository is hidden by the readonly archive mount.
    parent = git('rev-parse', 'HEAD^')
    git('merge-base', '--is-ancestor', parent, 'HEAD')
    git('cat-file', '-e', parent + ':apps/worker-python/dehps/config.py')
    git_records.append({'root':root,'commit':expected,'parent':parent,
                        'history_commits':int(git('rev-list','--count','HEAD')),
                        'clean':True,'metadata_mount_readonly':True})
root = Path('/home/ark/workspace/dehps')
worker = root / 'apps/worker-python'
sys.path.insert(0, str(worker))
retained = runpy.run_path(str(worker / 'scripts/run_m4_p3_performance_runtime.py'),
                         run_name='retained_contract_inspection')
config = json.loads((root / 'runtime/p3-performance/config.json').read_text())
retained['verify_runtime_compatibility_closure'](
    operator_commit=config['operator']['merged_commit'],
    closure=config['runtime_compatibility_closure'])
source = retained['successor'].load_source_contract(root_dir=root)
assert source['artifact_digest'] == retained['EXPECTED_SOURCE_DIGEST']
assert source['source_set_digest'] == retained['EXPECTED_SOURCE_SET_DIGEST']
frozen_contract = {'verified_by_original_functions':True,
                   'operator_commit':config['operator']['merged_commit'],
                   'closure_digest':config['runtime_compatibility_closure']['closure_digest'],
                   'source_artifact_digest':source['artifact_digest'],
                   'source_set_digest':source['source_set_digest']}
print(json.dumps({'uid':os.getuid(),'no_new_privileges':True,'denials':denials,
                  'inspection_data_mounts_readonly':True,'git':git_records,
                  'frozen_contract':frozen_contract}))
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
