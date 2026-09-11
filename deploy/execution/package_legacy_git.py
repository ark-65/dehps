"""Export authentic, self-contained Git metadata for an unchanged legacy tree.

Writes a new metadata directory only. Install it as .git in a NEW release copy;
never attach it to the running checkout or alter an already reviewed package.
"""
from __future__ import annotations

import argparse
from hashlib import sha1, sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile


def environment() -> dict[str, str]:
    # No developer hooks, alternates, replacements, filters or ambient Git config.
    return {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LC_ALL': 'C',
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
            'GIT_NO_REPLACE_OBJECTS': '1', 'GIT_OPTIONAL_LOCKS': '0'}


def git(*args: str, data: bytes | None = None) -> bytes:
    return subprocess.check_output(['/usr/bin/git', *args], input=data,
                                   env=environment(), stderr=subprocess.PIPE)


def build(repository: Path, commit: str, source: Path, output: Path) -> dict:
    repository, source = repository.resolve(), source.resolve()
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('exact SHA-1 commit required')
    if output.exists() or output.is_symlink():
        raise ValueError('preserve existing metadata; choose a new output')
    if not source.is_dir() or not repository.is_dir():
        raise ValueError('existing repository and frozen source copy required')
    origin = ['-c', f'safe.directory={repository}', '-C', str(repository)]
    if git(*origin, 'rev-parse', f'{commit}^{{commit}}').decode().strip() != commit:
        raise ValueError('commit must identify the original commit object')
    # Compare every tracked byte and mode without trusting an index stat cache,
    # clean/smudge filters, assume-unchanged, or a caller-provided identity string.
    entries = git(*origin, 'ls-tree', '-r', '-z', commit).split(b'\0')
    tracked = {}
    for entry in filter(None, entries):
        fields, raw_name = entry.split(b'\t', 1)
        mode, kind, oid = fields.decode().split()
        name = os.fsdecode(raw_name)
        path = source / name
        if path.parent.resolve() != path.parent or kind != 'blob':
            raise ValueError(f'unsupported source path or object: {name}')
        info = path.lstat()
        if mode == '120000' and stat.S_ISLNK(info.st_mode):
            content = os.fsencode(os.readlink(path))
        elif mode in {'100644', '100755'} and stat.S_ISREG(info.st_mode):
            if bool(info.st_mode & 0o111) != (mode == '100755'):
                raise ValueError(f'source executable mode changed: {name}')
            content = path.read_bytes()
        else:
            raise ValueError(f'source type changed: {name}')
        blob = sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        if blob != oid:
            raise ValueError(f'source bytes changed: {name}')
        tracked[name] = {'git_blob': oid, 'sha256': sha256(content).hexdigest(),
                         'bytes': len(content), 'mode': mode}
    output = output.absolute()
    # Existence is refused above and mkdir is exclusive, including concurrent runs.
    output.mkdir(mode=0o755)
    git('init', '--bare', '--template=', str(output))
    target = ['--git-dir', str(output)]
    # Export full ancestry: retained verifiers use merge-base and historical show.
    # Pack bytes are copied, never hardlinked to the development object database.
    with tempfile.TemporaryFile() as pack:
        subprocess.run(['/usr/bin/git', *origin, 'pack-objects', '--revs', '--stdout'],
                       input=(commit + '\n').encode(), stdout=pack, check=True,
                       stderr=subprocess.PIPE, env=environment())
        pack.seek(0)
        subprocess.run(['/usr/bin/git', *target, 'index-pack', '--stdin'],
                       stdin=pack, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       check=True, env=environment())
    git(*target, 'config', 'core.bare', 'false')
    git(*target, 'config', 'core.filemode', 'true')
    git(*target, 'config', 'core.logAllRefUpdates', 'false')
    (output / 'HEAD').write_text(commit + '\n')
    work = [*target, '--work-tree', str(source)]
    git(*work, 'read-tree', commit)
    git(*target, 'fsck', '--full', '--no-reflogs')
    dirty = git(*work, 'status', '--porcelain').decode()
    if dirty:
        raise ValueError(f'frozen source copy is not clean: {dirty}')
    records = {}
    for path in sorted(output.rglob('*')):
        if path.is_symlink():
            raise ValueError('Git metadata must not reference external paths')
        if path.is_file():
            content = path.read_bytes()
            records[str(path.relative_to(output))] = {
                'sha256': sha256(content).hexdigest(), 'bytes': len(content)}
    return {'schema': 'dehps-legacy-git-metadata.v1', 'commit': commit,
            'tree': git(*origin, 'rev-parse', f'{commit}^{{tree}}').decode().strip(),
            'history_commits': int(git(*target, 'rev-list', '--count', 'HEAD')),
            'source_files': tracked, 'metadata_files': records,
            'source_modified': False, 'production_execution': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['repository', 'source', 'output', 'manifest']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    if args.manifest.exists():
        parser.error('preserve existing manifest; choose a new output')
    evidence = build(args.repository, args.commit, args.source, args.output)
    with args.manifest.open('x') as stream:
        json.dump(evidence, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'commit': evidence['commit'],
                      'history_commits': evidence['history_commits'],
                      'source_files': len(evidence['source_files']),
                      'manifest': str(args.manifest)}))
