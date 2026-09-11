"""Keep legacy P3 paths while selecting reviewed, immutable source/dependency copies.

This host launcher is part of the trusted Operator release package. It does not
approve deployment or move P3 tasks into the independent execution engine.
--inspect is an offline, read-only import/CLI check; --execute runs the fixed
service command and requires a root-owned package. Never use it as a new manual
completion path for a training task.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import pwd
import stat
import subprocess


ORIGINAL = Path('/home/ark/workspace/dehps')
RESIDENT = Path('/home/ark/workspace/dehps-m4-historical-exec-runtime-cd069c1')
SOURCE_COMMITS = {
    ORIGINAL: 'ac0ef7832c6f13c7500b3f7d67731420b575c0f4',
    RESIDENT: 'cd069c15110b0af0f3a83ff619272c14e4748edc',
}
ENTRIES = {
    'forward': (ORIGINAL, 'run_m4_p3_forward_prequential_confirmatory.py',
                ['cycle', '--apply', '--sync-draws']),
    'pre-mail': (ORIGINAL, 'run_m4_p3_top100_notification.py',
                 ['pre', '--apply', '--deliver']),
    'post-mail': (ORIGINAL, 'run_m4_p3_top100_notification.py',
                  ['post', '--apply', '--deliver']),
    'p4-armed': (ORIGINAL, 'run_m4_p4_forward_prequential.py', ['cycle', '--apply']),
    'supervisor': (RESIDENT, 'run_research_evidence_supervisor.py',
                   ['--control-plane-key', 'm4-information-theory-mainline',
                    '--interval-seconds', '15']),
    'performance-watch': (ORIGINAL, 'run_m4_p3_performance_runtime.py', ['watch', '--apply']),
    'performance-enter': (ORIGINAL, 'run_m4_p3_performance_runtime.py', ['enter', '--apply']),
    'performance-exit': (ORIGINAL, 'run_m4_p3_performance_runtime.py', ['exit', '--apply']),
    'draw-sync': (ORIGINAL, 'run_draw_sync_watch.py',
                  ['--once', '--no-resume-on-event', '--post-draw-report-notifications',
                   '--prediction-v2-shadow-notifications', '--interval-seconds', '900',
                   '--hot-interval-seconds', '300', '--cold-interval-seconds', '3600',
                   '--timezone', 'Asia/Shanghai']),
}

BOOTSTRAP = '''
import json, pathlib, runpy, sys
worker, script, inspect = sys.argv[1:4]
args = sys.argv[4:]
sys.path[:0] = [worker, str(pathlib.Path(script).parent)]
if inspect == 'yes':
    import dehps.config, numpy, numba, psycopg
    print(json.dumps({'root':str(dehps.config.ROOT_DIR),
          'config_file':dehps.config.__file__, 'prefix':sys.prefix,
          'numpy':numpy.__version__, 'numba':numba.__version__,
          'psycopg':psycopg.__version__}), flush=True)
sys.argv = [script] + args
runpy.run_path(script, run_name='__main__')
'''


def canonical(path: Path) -> Path:
    if not path.is_absolute() or path.resolve() != path or not path.is_dir():
        raise ValueError('existing canonical absolute bundle required')
    return path


def protected_package(bundle: Path) -> None:
    # Parent replacement is as significant as modifying an individual script.
    for path in [*bundle.parents, bundle, *bundle.rglob('*')]:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            # Exact symlink targets are verified against the retained manifest
            # when installing; their protected parent prevents replacement.
            if info.st_uid != 0:
                raise ValueError(f'unprotected release symlink: {path}')
        elif info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError(f'release must be root-owned and not writable by runtime: {path}')


def command(bundle: Path, entry: str, inspect: bool) -> list[str]:
    canonical(bundle)
    legacy = bundle / 'legacy'
    selected, script_name, run_args = ENTRIES[entry]
    worker = selected / 'apps/worker-python'
    original_worker = ORIGINAL / 'apps/worker-python'
    sources = [(legacy / 'ac0ef78', ORIGINAL), (legacy / 'cd069c1', RESIDENT)]
    for source, destination in sources:
        canonical(source)
        metadata = canonical(source / '.git')
        if (metadata / 'HEAD').read_text().strip() != SOURCE_COMMITS[destination]:
            raise ValueError('legacy metadata must retain its exact detached commit')
    canonical(legacy / 'environment')
    runtime_alias = legacy / 'cd069c1/runtime'
    if (not runtime_alias.is_symlink()
            or runtime_alias.readlink() != ORIGINAL / 'runtime'):
        raise ValueError('release must preserve the resident canonical runtime symlink')
    # The source directory is mounted readonly before the environment file.
    # bwrap cannot create a missing file target inside that readonly directory.
    # Package only an empty regular placeholder; credentials stay on the host.
    env_target = legacy / 'ac0ef78/.env'
    if (env_target.is_symlink() or not env_target.is_file()
            or env_target.stat().st_size != 0):
        raise ValueError('release requires an empty regular legacy/ac0ef78/.env mount target')
    if not inspect:
        if os.geteuid() != pwd.getpwnam('ark').pw_uid:
            raise ValueError('legacy execution must retain its existing ark runtime owner')
        protected_package(bundle)
    args = ['/usr/bin/bwrap', '--die-with-parent', '--unshare-pid',
            '--ro-bind', '/', '/']
    # Git called by frozen code must resolve the installed .git and real objects,
    # not ambient developer directories, replacements, alternates or config.
    for name in sorted(os.environ):
        if name.startswith('GIT_'):
            args += ['--unsetenv', name]
    if inspect:
        args += ['--unshare-net']
    for source, destination in sources:
        args += ['--ro-bind', str(source), str(destination)]
    args += ['--ro-bind', str(legacy / 'environment'), str(original_worker / '.venv')]
    # bwrap resolves bind sources in the original namespace. Keep every old
    # artifact path, including the resident checkout's original runtime alias.
    for relative in ['runtime', 'data/output']:
        path = str(ORIGINAL / relative)
        writable = not inspect and (relative == 'runtime' or entry not in {'pre-mail', 'post-mail'})
        args += ['--bind' if writable else '--ro-bind', path, path]
    # Exercise the same file mount during offline acceptance, with the empty
    # placeholder as its source instead of reading production credentials.
    args += ['--ro-bind', str(env_target if inspect else ORIGINAL / '.env'),
             str(ORIGINAL / '.env')]
    args += ['--tmpfs', '/tmp', '--tmpfs', '/var/tmp', '--proc', '/proc', '--dev', '/dev',
             '--chdir', str(ORIGINAL if entry == 'performance-watch' else worker),
             '--setenv', 'PYTHONPATH', str(worker),
             '--unsetenv', 'PYTHONHOME', '--unsetenv', 'PYTHONSTARTUP',
             '--setenv', 'PYTHONNOUSERSITE', '1',
             '--setenv', 'GIT_CONFIG_NOSYSTEM', '1',
             '--setenv', 'GIT_CONFIG_GLOBAL', '/dev/null',
             '--setenv', 'GIT_NO_REPLACE_OBJECTS', '1',
             '--setenv', 'GIT_OPTIONAL_LOCKS', '0',
             '--setenv', 'NUMBA_CACHE_DIR', '/tmp/dehps-numba' if inspect else
             str(ORIGINAL / 'runtime/control-layer-legacy-numba'),
             '--setenv', 'GIT_CONFIG_COUNT', '2',
             '--setenv', 'GIT_CONFIG_KEY_0', 'safe.directory',
             '--setenv', 'GIT_CONFIG_VALUE_0', str(ORIGINAL),
             '--setenv', 'GIT_CONFIG_KEY_1', 'safe.directory',
             '--setenv', 'GIT_CONFIG_VALUE_1', str(RESIDENT),
             str(original_worker / '.venv/bin/python'), '-I', '-B', '-c', BOOTSTRAP,
             str(worker), str(worker / 'scripts' / script_name), 'yes' if inspect else 'no',
             *(['--help'] if inspect else run_args)]
    return args


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--entry', required=True, choices=ENTRIES)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--inspect', action='store_true')
    mode.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    argv = command(args.bundle, args.entry, args.inspect)
    if args.inspect:
        result = subprocess.run(argv, check=False)
        raise SystemExit(result.returncode)
    # Signal delivery must reach bwrap and its child, not an orphaned shell.
    os.execv(argv[0], argv)


if __name__ == '__main__':
    main()
