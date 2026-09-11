"""Real Git object/history tests for retained-release packaging."""
import importlib.util
import os
from pathlib import Path
import subprocess

import pytest


MODULE = Path(__file__).resolve().parents[3] / 'deploy/execution/package_legacy_git.py'
spec = importlib.util.spec_from_file_location('package_legacy_git', MODULE)
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


def git(root, *args):
    return subprocess.check_output(
        ['/usr/bin/git', '-C', str(root), *args], env=package.environment(),
        stderr=subprocess.PIPE,
    ).decode().strip()


@pytest.fixture
def history(tmp_path):
    repo, source = tmp_path / 'repo', tmp_path / 'source'
    repo.mkdir()
    git(repo, 'init', '--template=')
    git(repo, 'config', 'user.name', 'Local test author')
    git(repo, 'config', 'user.email', 'local-test@example.invalid')
    (repo / 'module.py').write_text('value = 1\n')
    (repo / 'alias.py').symlink_to('module.py')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'Original source')
    parent = git(repo, 'rev-parse', 'HEAD')
    (repo / 'module.py').write_text('value = 2\n')
    git(repo, 'commit', '-am', 'Accepted source')
    head = git(repo, 'rev-parse', 'HEAD')
    source.mkdir()
    (source / 'module.py').write_bytes((repo / 'module.py').read_bytes())
    (source / 'alias.py').symlink_to('module.py')
    return repo, source, parent, head


def test_self_contained_history_and_real_dirty_detection(history, tmp_path, monkeypatch):
    repo, source, parent, head = history
    # Ambient Git identity/alternates must not select another repository.
    monkeypatch.setenv('GIT_DIR', '/missing/foreign-repository')
    monkeypatch.setenv('GIT_ALTERNATE_OBJECT_DIRECTORIES', '/missing/objects')
    record = package.build(repo, head, source, source / '.git')
    assert record['history_commits'] == 2
    assert record['commit'] == head
    assert not (source / '.git/objects/info/alternates').exists()
    assert not (source / '.git/shallow').exists()
    assert git(source, 'remote') == ''
    repo.rename(tmp_path / 'original-repository-unavailable')
    assert git(source, 'rev-parse', 'HEAD') == head
    assert git(source, 'show', f'{parent}:module.py') == 'value = 1'
    assert git(source, 'merge-base', '--is-ancestor', parent, head) == ''
    assert git(source, 'fsck', '--full', '--no-reflogs') == ''
    assert git(source, 'status', '--porcelain') == ''
    (source / 'module.py').write_text('value = 9\n')
    assert 'module.py' in git(source, 'status', '--porcelain')
    with pytest.raises(ValueError, match='preserve existing'):
        package.build(tmp_path / 'original-repository-unavailable', head, source, source / '.git')


def test_tampered_source_same_size_and_mtime_rejected(history, tmp_path):
    repo, source, _, head = history
    path = source / 'module.py'
    original = path.stat()
    path.write_text('value = 9\n')
    os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
    with pytest.raises(ValueError, match='source bytes changed'):
        package.build(repo, head, source, tmp_path / 'metadata')
    assert not (tmp_path / 'metadata').exists()


def test_untracked_file_and_mode_change_rejected(history, tmp_path):
    repo, source, _, head = history
    (source / 'module.py').chmod(0o755)
    with pytest.raises(ValueError, match='executable mode changed'):
        package.build(repo, head, source, tmp_path / 'metadata-mode')
    (source / 'module.py').chmod(0o644)
    (source / 'unexpected.py').write_text('unexpected = True\n')
    with pytest.raises(ValueError, match='not clean'):
        package.build(repo, head, source, tmp_path / 'metadata-untracked')
