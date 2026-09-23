"""Reuse the protected retained namespace; change only the mail entry consumer."""
import argparse
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path

RETAINED = Path('/opt/dehps/releases/retained-p3-r5-alias-f8ec526')
LAUNCHER_SHA = '3f817f219df8da966df8cbe1bccb0d75878df529bdf45505fac96211179a6777'


def command(bundle, mode, deliver=False):
    path = RETAINED / 'legacy_p3_namespace.py'
    if sha256(path.read_bytes()).hexdigest() != LAUNCHER_SHA:
        raise ValueError('retained namespace launcher changed')
    spec = importlib.util.spec_from_file_location('retained_namespace', path)
    legacy = importlib.util.module_from_spec(spec); spec.loader.exec_module(legacy)
    legacy.canonical(bundle); legacy.protected_package(bundle)
    packet = json.loads((bundle / 'package.json').read_bytes())
    for name, identity in packet['files'].items():
        p = bundle / name
        if not p.resolve().is_relative_to(bundle) or sha256(p.read_bytes()).hexdigest() != identity:
            raise ValueError('presentation package file changed: ' + name)
    argv = legacy.command(RETAINED, 'pre-mail' if mode == 'pre' else 'post-mail', False)
    index = argv.index(legacy.BOOTSTRAP)
    argv[index + 2] = str(bundle / 'source/apps/worker-python/scripts/run_primary_p3_presentation.py')
    argv[index + 4:] = [mode, '--release', str(bundle / 'release.json')] + (['--deliver'] if deliver else [])
    return argv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--mode', required=True, choices=['pre', 'post', 'acceptance', 'replay'])
    parser.add_argument('--deliver', action='store_true')
    args = parser.parse_args()
    if args.deliver and args.mode not in ('pre', 'post'):
        raise ValueError('acceptance and replay cannot send')
    argv = command(args.bundle, args.mode, args.deliver)
    os.execv(argv[0], argv)


if __name__ == '__main__':
    main()
