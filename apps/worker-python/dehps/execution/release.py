"""Fixed userspace releases. Invoked by a trusted builder/operator, never a worker.

Docker daemon access is administrative authority, not granted to capabilities.
Descriptors are content bindings, not signatures or independent approvals.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
from uuid import uuid4

from .context import BoundaryError, RunContext, _directory


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode()


def _digest(value: str):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise BoundaryError('an exact SHA-256 identity is required')


def _command(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, **kwargs)


def _file_digest(stream):
    value = sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        value.update(block)
    return value.hexdigest()


def image_info(image_id: str) -> dict:
    if not isinstance(image_id, str) or not image_id.startswith('sha256:'):
        raise BoundaryError('mutable image references are forbidden')
    _digest(image_id[7:])
    result = json.loads(_command(['docker', 'image', 'inspect', image_id], timeout=30).stdout)
    if len(result) != 1 or result[0]['Id'] != image_id:
        raise BoundaryError('image identity mismatch')
    info = result[0]
    if info['Config'].get('Volumes') or info['Config'].get('Healthcheck'):
        raise BoundaryError('release cannot inject anonymous volumes or health commands')
    return info


@dataclass(frozen=True)
class Release:
    payload: dict

    def validate(self):
        p = self.payload
        if set(p) != {'schema', 'image_id', 'git_commit', 'source_archive_sha256',
                      'base_image_id', 'entrypoint', 'config_sha256', 'inventory', 'platform'}:
            raise BoundaryError('closed release descriptor required')
        if p['schema'] != 'execution-release.v1':
            raise BoundaryError('unknown release schema')
        for name in ('image_id', 'base_image_id'):
            if not isinstance(p[name], str) or not p[name].startswith('sha256:'):
                raise BoundaryError('release image must be content addressed')
            _digest(p[name][7:])
        for name in ('source_archive_sha256', 'config_sha256'):
            _digest(p[name])
        if not re.fullmatch('[0-9a-f]{40}', p['git_commit']):
            raise BoundaryError('source commit must be an exact Git object')
        entry = p['entrypoint']
        if (not isinstance(entry, list) or not entry or not all(isinstance(a, str) and a and '\0' not in a for a in entry)
                or not entry[0].startswith('/')):
            raise BoundaryError('release requires an explicit executable and arguments')
        if not isinstance(p['inventory'], dict) or set(p['inventory']) != {'python', 'packages'}:
            raise BoundaryError('installed dependency inventory required')
        if not isinstance(p['platform'], str) or not p['platform'].startswith('linux/'):
            raise BoundaryError('Linux release platform required')
        canonical(p)

    @property
    def digest(self):
        self.validate()
        return sha256(canonical(self.payload)).hexdigest()

    @classmethod
    def read(cls, path: Path, expected_sha256: str):
        _digest(expected_sha256)
        result = cls(json.loads(path.read_bytes()))
        if result.digest != expected_sha256:
            raise BoundaryError('release descriptor differs from accepted identity')
        return result

    def verify(self):
        self.validate()
        info = image_info(self.payload['image_id'])
        labels = info['Config'].get('Labels') or {}
        expected = {
            'org.dehps.source.commit': self.payload['git_commit'],
            'org.dehps.source.archive': self.payload['source_archive_sha256'],
            'org.dehps.config': self.payload['config_sha256'],
            'org.dehps.base': self.payload['base_image_id'],
        }
        if (any(labels.get(k) != v for k, v in expected.items())
                or info['Config']['Entrypoint'] != self.payload['entrypoint']
                or info['Config'].get('Cmd') not in (None, [])
                or self.payload['platform'] != f"{info['Os']}/{info['Architecture']}"):
            raise BoundaryError('release provenance, entrypoint or platform mismatch')
        # The inventory is itself baked into the content-addressed rootfs.
        result = _command([
            'docker', 'run', '--rm', '--network=none', '--read-only', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--user=65532:65532',
            '--entrypoint=/usr/local/bin/python', self.payload['image_id'], '-I', '-c',
            'from pathlib import Path; print(Path("/opt/dehps/inventory.json").read_text())',
        ], timeout=30)
        if json.loads(result.stdout) != self.payload['inventory']:
            raise BoundaryError('installed inventory mismatch')


def build_release(repository: Path, commit: str, base_image_id: str,
                  entrypoint: list[str], config: dict, output: Path) -> Release:
    """Build committed bytes only; retain the image and fail if output exists.

    Dependencies resolve once at build time. The resulting full userspace image,
    not a later reinstall from version ranges, is the release/replay environment.
    """
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise BoundaryError('build requires an exact source commit')
    base_info = image_info(base_image_id)
    # BuildKit interprets bare sha256:... in FROM as a repository/tag. Resolve
    # only a registry digest already attached to this exact local image.
    references = base_info.get('RepoDigests') or []
    references = sorted(r for r in references if re.fullmatch(r'[a-zA-Z0-9./:_-]+@sha256:[0-9a-f]{64}', r))
    if not references:
        raise BoundaryError('base image requires a retained immutable registry digest')
    base_reference = references[0]
    resolved = json.loads(_command(['docker', 'image', 'inspect', base_reference], timeout=30).stdout)
    if len(resolved) != 1 or resolved[0]['Id'] != base_image_id:
        raise BoundaryError('base registry digest differs from selected image')
    if output.exists():
        raise BoundaryError('release output already exists')
    if _command(['git', '-C', str(repository), 'status', '--porcelain'], timeout=30).stdout:
        raise BoundaryError('release builder requires a clean source checkout')
    if not isinstance(config, dict):
        raise BoundaryError('explicit non-secret configuration required')
    config_data = canonical(config)
    source = _command(['git', '-C', str(repository), 'archive', '--format=tar', commit], timeout=60).stdout
    source_sha = sha256(source).hexdigest()
    config_sha = sha256(config_data).hexdigest()
    # Validate entry/identities before invoking the build backend.
    candidate = Release({'schema': 'execution-release.v1', 'image_id': base_image_id,
                         'base_image_id': base_image_id, 'git_commit': commit,
                         'source_archive_sha256': source_sha, 'config_sha256': config_sha,
                         'entrypoint': entrypoint, 'inventory': {'python': '', 'packages': []},
                         'platform': 'linux/unknown'})
    candidate.validate()
    with tempfile.TemporaryDirectory(prefix='dehps-release-build-') as directory:
        root = Path(directory)
        (root / 'source.tar').write_bytes(source)
        (root / 'config.json').write_bytes(config_data)
        # No host venv, ambient .env or untracked runtime file enters this context.
        (root / 'Dockerfile').write_text('\n'.join([
            f'FROM {base_reference}',
            'ENV PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 NUMBA_CACHE_DIR=/tmp/dehps-numba',
            'ADD source.tar /opt/dehps/source/',
            'COPY config.json /opt/dehps/config.json',
            'RUN python -m pip install --no-cache-dir /opt/dehps/source/apps/worker-python && python -m pip check',
            'RUN python -c "import importlib.metadata as m,json,sys; from pathlib import Path; '
            'Path(\'/opt/dehps/inventory.json\').write_text(json.dumps({\'python\':sys.version,'
            '\'packages\':sorted((d.metadata[\'Name\'],d.version) for d in m.distributions())},sort_keys=True))"',
            f'LABEL org.dehps.source.commit="{commit}" org.dehps.source.archive="{source_sha}" '
            f'org.dehps.config="{config_sha}" org.dehps.base="{base_image_id}"',
            'WORKDIR /tmp', 'USER 65532:65532',
            'ENTRYPOINT ' + json.dumps(entrypoint), 'CMD []', '',
        ]))
        # Keep build output in its normal stream; it contains no runtime credentials.
        subprocess.run(['docker', 'build', '--pull=false', '--platform',
                        f"{base_info['Os']}/{base_info['Architecture']}",
                        '--iidfile', str(root / 'image-id'), str(root)], check=True)
        image_id = (root / 'image-id').read_text().strip()
    info = image_info(image_id)
    inventory = json.loads(_command([
        'docker', 'run', '--rm', '--network=none', '--read-only', '--cap-drop=ALL',
        '--security-opt=no-new-privileges', '--user=65532:65532',
        '--entrypoint=/usr/local/bin/python', image_id, '-I', '-c',
        'from pathlib import Path; print(Path("/opt/dehps/inventory.json").read_text())',
    ], timeout=30).stdout)
    result = Release({**candidate.payload, 'image_id': image_id, 'inventory': inventory,
                      'platform': f"{info['Os']}/{info['Architecture']}"})
    result.verify()
    # A descriptor is immutable evidence; do not overwrite an older release.
    with output.open('xb') as stream:
        stream.write(canonical(result.payload) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    with _directory(output.absolute().parent, ()) as parent:
        os.fsync(parent)
    return result


def archive_release(release: Release, expected_sha256: str, output: Path) -> str:
    """Retain exact image bytes for offline restore; return the archive digest."""
    if release.digest != expected_sha256:
        raise BoundaryError('archive release differs from accepted identity')
    release.verify()
    if output.exists():
        raise BoundaryError('release archive already exists')
    with tempfile.TemporaryDirectory(prefix='.dehps-image-', dir=output.parent) as directory:
        temporary = Path(directory) / 'image.tar'
        _command(['docker', 'image', 'save', '--output', str(temporary), release.payload['image_id']])
        with temporary.open('rb') as stream:
            digest = _file_digest(stream)
            os.fsync(stream.fileno())
        temporary.chmod(0o400)
        os.link(temporary, output)
        with _directory(output.absolute().parent, ()) as parent:
            os.fsync(parent)
    return digest


def restore_release(release: Release, expected_sha256: str, archive: Path, archive_sha256: str):
    """Load verified retained bytes, never substitute a tag or reinstall packages."""
    _digest(archive_sha256)
    if release.digest != expected_sha256:
        raise BoundaryError('restore release differs from accepted identity')
    with archive.open('rb') as stream:
        if _file_digest(stream) != archive_sha256:
            raise BoundaryError('release archive content mismatch')
        stream.seek(0)
        _command(['docker', 'image', 'load'], stdin=stream)
    release.verify()


@dataclass(frozen=True)
class LaunchResult:
    release_sha256: str
    container_id: str
    image_id: str
    returncode: int
    stdout: bytes
    stderr: bytes


def launch(release: Release, expected_sha256: str, context: RunContext, *,
           inputs: Path, credentials: Path, network: str, action: str,
           timeout: float | None = None) -> LaunchResult:
    """Run the frozen entry with fixed mount targets; no code or config overrides.

    Operator must supply a dedicated domain root and restricted login. This is
    not an approval interface; R5 must authenticate/review the deployment inputs.
    """
    _digest(expected_sha256)
    if release.digest != expected_sha256:
        raise BoundaryError('launch release differs from approved identity')
    if action not in {'run', 'replay'}:
        raise BoundaryError('unsupported release action')
    if network != 'none' and not re.fullmatch('dehps-[a-z0-9-]+', network):
        raise BoundaryError('explicit isolated Docker network required')
    if os.geteuid() == 0:
        raise BoundaryError('launch requires a non-root runtime owner')
    # Revalidate even if a previously constructed context has since changed.
    RunContext(context.root, context.control_plane)
    roots = (context.root, inputs, credentials)
    for path in roots:
        if not path.is_absolute() or path.resolve() != path or ',' in str(path):
            raise BoundaryError('canonical mount source required')
    if not inputs.is_dir():
        raise BoundaryError('explicit read-only input directory required')
    if any(a == b or a in b.parents or b in a.parents for i,a in enumerate(roots) for b in roots[i+1:]):
        raise BoundaryError('runtime, inputs and credentials must not overlap')
    info = credentials.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise BoundaryError('credentials must be a private file owned by the runtime uid')
    release.verify()
    # The content-addressed ID is used after verification, never a mutable tag.
    # No Docker socket, host home, source tree or production credential fallback.
    nonce = uuid4().hex
    args = [
        'docker', 'create', '--init', '--network=' + network, '--read-only',
        '--label=org.dehps.launch=' + nonce,
        '--cap-drop=ALL', '--security-opt=no-new-privileges', '--pids-limit=256',
        '--user', f'{os.getuid()}:{os.getgid()}', '--workdir=/tmp',
        '--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=256m',
        '--mount', f'type=bind,src={context.root},dst=/runtime' + (',readonly' if action == 'replay' else ''),
        '--mount', f'type=bind,src={inputs},dst=/inputs,readonly',
        '--mount', f'type=bind,src={credentials},dst=/run/dehps-credentials.json,readonly',
        '--env', 'DEHPS_RELEASE_SHA256=' + expected_sha256,
        '--env', 'DEHPS_CONTROL_DOMAIN=' + context.control_plane,
        '--env', 'DEHPS_EXECUTION_ACTION=' + action,
        release.payload['image_id'],
    ]
    container = _command(args, timeout=30).stdout.decode().strip()
    if not re.fullmatch('[0-9a-f]{64}', container):
        raise BoundaryError('invalid created container identity')
    try:
        info = json.loads(_command(['docker', 'inspect', container], timeout=30).stdout)[0]
        if (info['Image'] != release.payload['image_id']
                or info['Config']['Labels'].get('org.dehps.launch') != nonce):
            raise BoundaryError('created container differs from verified release')
        result = subprocess.run(['docker', 'start', '--attach', container],
                                check=False, capture_output=True, timeout=timeout)
        info = json.loads(_command(['docker', 'inspect', container], timeout=30).stdout)[0]
        if info['State']['Running'] or info['State']['Status'] != 'exited':
            raise BoundaryError('container did not reach a terminal execution state')
        return LaunchResult(expected_sha256, container, info['Image'], info['State']['ExitCode'],
                            result.stdout, result.stderr)
    finally:
        # Only the exact container created by this call is removed. In particular,
        # a CLI timeout must not leave a detached computation running unnoticed.
        _command(['docker', 'rm', '--force', container], timeout=30)


def main():
    """Explicit build/verify/archive/restore/run commands for reviewed procedures."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('build')
    build.add_argument('--repository', type=Path, required=True)
    build.add_argument('--commit', required=True)
    build.add_argument('--base-image-id', required=True)
    build.add_argument('--entrypoint-json', type=Path, required=True)
    build.add_argument('--config-json', type=Path, required=True)
    build.add_argument('--output', type=Path, required=True)
    for name in ('verify', 'archive', 'restore', 'run'):
        command = commands.add_parser(name)
        command.add_argument('--descriptor', type=Path, required=True)
        command.add_argument('--release-sha256', required=True)
        if name in ('archive', 'restore'):
            command.add_argument('--archive', type=Path, required=True)
        if name == 'restore':
            command.add_argument('--archive-sha256', required=True)
        if name == 'run':
            command.add_argument('--runtime-root', type=Path, required=True)
            command.add_argument('--control-domain', required=True)
            command.add_argument('--inputs', type=Path, required=True)
            command.add_argument('--credentials', type=Path, required=True)
            command.add_argument('--network', required=True)
            command.add_argument('--action', choices=['run', 'replay'], required=True)
    args = parser.parse_args()
    if args.command == 'build':
        release = build_release(args.repository, args.commit, args.base_image_id,
                                json.loads(args.entrypoint_json.read_bytes()),
                                json.loads(args.config_json.read_bytes()), args.output)
        print(json.dumps({'release_sha256': release.digest, 'image_id': release.payload['image_id']}))
        return
    release = Release.read(args.descriptor, args.release_sha256)
    if args.command == 'verify':
        release.verify()
        print(json.dumps({'verified_release_sha256': release.digest}))
    elif args.command == 'archive':
        digest = archive_release(release, args.release_sha256, args.archive)
        print(json.dumps({'release_sha256': release.digest, 'archive_sha256': digest}))
    elif args.command == 'restore':
        restore_release(release, args.release_sha256, args.archive, args.archive_sha256)
        print(json.dumps({'restored_release_sha256': release.digest}))
    else:
        result = launch(release, args.release_sha256, RunContext(args.runtime_root, args.control_domain),
                        inputs=args.inputs, credentials=args.credentials,
                        network=args.network, action=args.action)
        sys.stdout.buffer.write(result.stdout)
        sys.stdout.buffer.flush()
        sys.stderr.buffer.write(result.stderr)
        sys.stderr.buffer.flush()
        print(json.dumps({'release_sha256': result.release_sha256, 'container_id': result.container_id,
                          'image_id': result.image_id, 'exit_code': result.returncode}), file=sys.stderr)
        raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
