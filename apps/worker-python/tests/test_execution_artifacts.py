from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from dehps.execution.artifacts import ArtifactStore
from dehps.execution.context import BoundaryError, RunContext


@pytest.fixture
def artifacts(tmp_path):
    tmp_path.chmod(0o700)
    return ArtifactStore(RunContext(tmp_path, 'learning'))


def blob_path(artifacts, digest):
    return artifacts.context.root / 'learning' / 'artifacts' / 'objects' / f'{digest}.blob'


def test_repeated_publication_never_replaces_existing_bytes_or_mtime(artifacts):
    first = artifacts.prepare(b'committed bytes')
    path = blob_path(artifacts, first.sha256)
    before = path.stat()
    assert artifacts.prepare(b'committed bytes') == first
    assert artifacts.read(first) == b'committed bytes'
    after = path.stat()
    assert (before.st_ino, before.st_mtime_ns) == (after.st_ino, after.st_mtime_ns)
    assert not list(path.parent.glob('.pending-*'))


def test_tampered_blob_is_not_silently_repaired(artifacts):
    original = artifacts.prepare(b'original')
    path = blob_path(artifacts, original.sha256)
    path.chmod(0o600)
    path.write_bytes(b'tampered')
    with pytest.raises(BoundaryError, match='digest'):
        artifacts.read(original)
    with pytest.raises(BoundaryError, match='digest'):
        artifacts.prepare(b'original')
    assert path.read_bytes() == b'tampered'


def test_missing_evidence_blocks_read(artifacts):
    original = artifacts.prepare(b'original')
    blob_path(artifacts, original.sha256).unlink()
    with pytest.raises(FileNotFoundError):
        artifacts.read(original)


def test_final_and_parent_symlinks_cannot_redirect_publication(artifacts, tmp_path):
    sentinel = tmp_path / 'formal'
    sentinel.write_bytes(b'formal')
    artifacts.prepare(b'initialize')
    digest = sha256(b'new').hexdigest()
    path = blob_path(artifacts, digest)
    path.symlink_to(sentinel)
    with pytest.raises(OSError):
        artifacts.prepare(b'new')
    assert sentinel.read_bytes() == b'formal'
    path.unlink()
    root = path.parent
    renamed = root.with_name('old-objects')
    root.rename(renamed)
    root.symlink_to(renamed, target_is_directory=True)
    with pytest.raises(OSError):
        artifacts.prepare(b'new')


def test_size_and_digest_paths_fail_closed(artifacts):
    original = artifacts.prepare(b'original')
    for value in (replace(original, sha256='../formal'), replace(original, size=-1),
                  replace(original, size=True), replace(original, size=1234)):
        with pytest.raises(BoundaryError):
            artifacts.read(value)
