"""Durable, content-addressed file publication; no overwrite or implicit GC.

A prepared file is not a committed task. Only the database reference commits it.
Unreferenced files after interruption are retained for audit/reconciliation.
"""
from dataclasses import dataclass
from hashlib import sha256
import os
import re
import stat
from uuid import uuid4

from .context import BoundaryError, RunContext, _directory


@dataclass(frozen=True)
class PreparedArtifact:
    sha256: str
    size: int


@dataclass(frozen=True)
class ArtifactStore:
    context: RunContext

    def _parts(self, digest: str):
        if not re.fullmatch('[0-9a-f]{64}', digest):
            raise BoundaryError('invalid artifact SHA-256')
        return self.context._location('artifacts', f'objects/{digest}.blob')

    def prepare(self, data: bytes) -> PreparedArtifact:
        if not isinstance(data, bytes):
            raise TypeError('artifact payload must be bytes')
        artifact = PreparedArtifact(sha256(data).hexdigest(), len(data))
        parts = self._parts(artifact.sha256)
        with _directory(self.context.root, parts[:-1], create=True) as directory:
            temporary = '.pending-' + uuid4().hex
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(data)
                    stream.flush()
                    os.fchmod(stream.fileno(), 0o400)
                    os.fsync(stream.fileno())
                try:
                    # Atomic no-replace publication on this filesystem. A process
                    # crash leaves either a pending file or a complete named blob.
                    os.link(temporary, parts[-1], src_dir_fd=directory,
                            dst_dir_fd=directory, follow_symlinks=False)
                except FileExistsError:
                    # Existing bytes are verified below, never repaired in place.
                    pass
                os.fsync(directory)
            finally:
                os.unlink(temporary, dir_fd=directory)
                os.fsync(directory)
        if self.read(artifact) != data:
            raise BoundaryError('existing immutable artifact conflicts')
        return artifact

    def read(self, artifact: PreparedArtifact) -> bytes:
        if type(artifact.size) is not int or artifact.size < 0:
            raise BoundaryError('invalid artifact size')
        parts = self._parts(artifact.sha256)
        with _directory(self.context.root, parts[:-1]) as directory:
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size != artifact.size:
                    raise BoundaryError('artifact size or file type mismatch')
                data = stream.read(artifact.size + 1)
        if len(data) != artifact.size or sha256(data).hexdigest() != artifact.sha256:
            raise BoundaryError('artifact digest mismatch')
        return data
