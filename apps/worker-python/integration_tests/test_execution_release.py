"""Actual image bytes, installed package, readonly mounts and release rollback."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess

import pytest

from dehps.execution.context import BoundaryError, RunContext
from dehps.execution.release import Release, archive_release, build_release, launch, restore_release


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def test_fixed_release_branch_changes_and_rollback(tmp_path):
    base = os.environ['DEHPS_EXECUTION_OS_IMAGE']
    repo = tmp_path / 'development'
    worker = repo / 'apps/worker-python'
    worker.mkdir(parents=True)
    (worker / 'pyproject.toml').write_text('''
[project]
name = "dehps-release-fixture"
version = "1.0.0"
[tool.setuptools]
py-modules = ["frozen_probe"]
''')
    probe = worker / 'frozen_probe.py'
    probe.write_text('VERSION = "one"\n')
    git(repo, 'init')
    git(repo, 'add', '.')
    git(repo, '-c', 'user.name=DEHPS Test Fixture', '-c', 'user.email=fixture@invalid', 'commit', '-m', 'fixture one')
    first_commit = git(repo, 'rev-parse', 'HEAD')
    # Fixed script is part of the image configuration, not a launch-time override.
    script = r'''
import json,os
from pathlib import Path
import frozen_probe
if Path('/inputs/force-timeout').exists():
    import time
    time.sleep(30)
config=json.loads(Path('/opt/dehps/config.json').read_bytes())
assert Path('/run/dehps-credentials.json').read_text() == 'test credential'
assert Path('/inputs/snapshot').read_text() == 'immutable historical input'
assert not Path('/home/ark/workspace/dehps/.env').exists()
for path in ['/opt/dehps/config.json','/inputs/snapshot','/run/dehps-credentials.json',frozen_probe.__file__]:
    try: Path(path).write_text('changed')
    except OSError: pass
    else: raise AssertionError('release/input/credential was writable')
output=Path('/runtime')/os.environ['DEHPS_CONTROL_DOMAIN']
if os.environ['DEHPS_EXECUTION_ACTION']=='run':
    output.mkdir(exist_ok=True)
    with (output/'history').open('a') as f: f.write(frozen_probe.VERSION+'\n')
else:
    try: (output/'history').write_text('illegal replay write')
    except OSError: pass
    else: raise AssertionError('replay runtime writable')
print(json.dumps({'version':frozen_probe.VERSION,'config':config,'release':os.environ['DEHPS_RELEASE_SHA256']}))
'''
    entry = ['/usr/local/bin/python', '-I', '-c', script]
    runtime = tmp_path / 'runtime'
    runtime.mkdir(mode=0o700)
    inputs = tmp_path / 'inputs'
    inputs.mkdir()
    (inputs / 'snapshot').write_text('immutable historical input')
    credentials = tmp_path / 'credentials'
    credentials.write_text('test credential')
    credentials.chmod(0o600)
    context = RunContext(runtime, 'isolated-release-test')
    images = []
    try:
        first = build_release(repo, first_commit, base, entry, {'configuration': 1}, tmp_path / 'one.json')
        images.append(first.payload['image_id'])
        assert first.payload['inventory']['packages']
        assert first.payload['git_commit'] == first_commit
        assert Release.read(tmp_path / 'one.json', first.digest).payload == first.payload

        def run(release, action='run'):
            result = launch(release, release.digest, context, inputs=inputs, credentials=credentials,
                            network='none', action=action, timeout=60)
            assert result.returncode == 0, result.stderr.decode()
            assert result.image_id == release.payload['image_id']
            value = json.loads(result.stdout)
            assert value['release'] == release.digest
            return value

        assert run(first)['version'] == 'one'
        probe.write_text('VERSION = "dirty development"\n')
        assert run(first)['version'] == 'one'
        with pytest.raises(BoundaryError, match='clean'):
            build_release(repo, first_commit, base, entry, {}, tmp_path / 'dirty.json')
        git(repo, 'switch', '-c', 'second-fixture')
        probe.write_text('VERSION = "two"\n')
        git(repo, 'add', '.')
        git(repo, '-c', 'user.name=DEHPS Test Fixture', '-c', 'user.email=fixture@invalid', 'commit', '-m', 'fixture two')
        second = build_release(repo, git(repo, 'rev-parse', 'HEAD'), base, entry,
                               {'configuration': 2}, tmp_path / 'two.json')
        images.append(second.payload['image_id'])
        assert first.digest != second.digest
        assert run(second) == {'version': 'two', 'config': {'configuration': 2}, 'release': second.digest}
        assert run(first) == {'version': 'one', 'config': {'configuration': 1}, 'release': first.digest}
        before = (runtime / context.control_plane / 'history').read_bytes()
        assert run(first, 'replay')['version'] == 'one'
        (inputs / 'force-timeout').touch()
        with pytest.raises(subprocess.TimeoutExpired):
            launch(first, first.digest, context, inputs=inputs, credentials=credentials,
                   network='none', action='run', timeout=0.2)
        (inputs / 'force-timeout').unlink()
        remaining = subprocess.run(['docker', 'ps', '-aq', '--filter', 'ancestor='+first.payload['image_id']],
                                   check=True, capture_output=True)
        assert not remaining.stdout.strip(), 'timed-out release left a detached container'
        assert before == (runtime / context.control_plane / 'history').read_bytes() == b'one\none\ntwo\none\n'
        assert (inputs / 'snapshot').read_text() == 'immutable historical input'
        archive = tmp_path / 'one-image.tar'
        archive_digest = archive_release(first, first.digest, archive)
        with pytest.raises(BoundaryError, match='already exists'):
            archive_release(first, first.digest, archive)
        subprocess.run(['docker', 'image', 'rm', first.payload['image_id']], check=True, capture_output=True)
        with pytest.raises(subprocess.CalledProcessError):
            first.verify()
        with pytest.raises(BoundaryError, match='content mismatch'):
            restore_release(first, first.digest, archive, '0'*64)
        restore_release(first, first.digest, archive, archive_digest)
        assert run(first, 'replay')['version'] == 'one'
        with pytest.raises(BoundaryError, match='accepted identity'):
            Release.read(tmp_path / 'two.json', first.digest)
        with pytest.raises(BoundaryError, match='approved identity'):
            launch(second, first.digest, context, inputs=inputs, credentials=credentials,
                   network='none', action='run')
        for key, value in [('entrypoint', ['/bin/false']), ('config_sha256', 'a'*64),
                           ('git_commit', 'a'*40), ('inventory', {'python': 'forged', 'packages': []})]:
            changed = deepcopy(first.payload)
            changed[key] = value
            with pytest.raises(BoundaryError, match='mismatch'):
                Release(changed).verify()
        credentials.chmod(0o644)
        with pytest.raises(BoundaryError, match='private'):
            run(first)
        print(json.dumps({'first_release': first.digest, 'second_release': second.digest,
                          'first_image': first.payload['image_id'], 'second_image': second.payload['image_id'],
                          'archive_sha256': archive_digest, 'rollback_history': before.decode()}))
    finally:
        for image in set(images):
            subprocess.run(['docker', 'image', 'rm', image], check=True, capture_output=True)
