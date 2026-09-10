"""Explicit writable domains; no production defaults or ambient configuration.

Directory descriptors and O_NOFOLLOW protect each filesystem traversal, including
the final atomic rename. OS permissions still provide the cross-process boundary;
this API does not claim to sandbox arbitrary capability code.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import re
from uuid import uuid4


class BoundaryError(ValueError):
    pass


AREAS = frozenset({"state", "status", "logs", "artifacts", "locks", "outbox"})
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _parts(relative: str) -> tuple[str, ...]:
    value = PurePosixPath(relative)
    if (not relative or not value.parts or value.is_absolute() or str(value) != relative
            or any(x in {".", ".."} for x in value.parts)):
        raise BoundaryError("path must be a canonical relative path")
    return value.parts


@contextmanager
def _directory(root: Path, parts: tuple[str, ...], *, create: bool = False):
    # Walk the absolute root too: a symlink in any ancestor is rejected.
    if not root.is_absolute() or ".." in root.parts:
        raise BoundaryError("runtime root must be absolute and canonical")
    fd = os.open("/", DIRECTORY_FLAGS)
    try:
        for name in root.parts[1:]:
            child = os.open(name, DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        for name in parts:
            if create:
                try:
                    os.mkdir(name, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                # Another writer may have created this entry but died before
                # flushing its parent. Existing entries need the same barrier.
                os.fsync(fd)
            child = os.open(name, DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


@dataclass(frozen=True)
class RunContext:
    """One domain owns six fixed subdirectories under an explicit existing root."""

    root: Path
    control_plane: str

    def __post_init__(self):
        if not isinstance(self.root, Path) or not self.root.is_absolute():
            raise BoundaryError("an explicit absolute runtime root is required")
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,95}", self.control_plane):
            raise BoundaryError("invalid control-plane identity")
        with _directory(self.root, ()) as fd:
            info = os.fstat(fd)
            if info.st_uid != os.geteuid() or info.st_mode & 0o022:
                raise BoundaryError("runtime root must be owned by this uid and not writable by others")

    def _location(self, area: str, relative: str) -> tuple[str, ...]:
        if area not in AREAS:
            raise BoundaryError("unknown writable area")
        return (self.control_plane, area, *_parts(relative))

    def write_projection(self, area: str, relative: str, payload: dict) -> None:
        if not isinstance(payload, dict):
            raise BoundaryError("projection payload must be an object")
        if area not in {"state", "status", "logs"}:
            raise BoundaryError("mutable projection cannot write immutable artifacts, locks or outbox")
        parts = self._location(area, relative)
        data = (json.dumps({"control_plane": self.control_plane, "payload": payload},
                           sort_keys=True, allow_nan=False) + "\n").encode()
        with _directory(self.root, parts[:-1], create=True) as directory:
            temporary = ".pending-" + uuid4().hex
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                # Replaces a final symlink itself rather than following its target.
                os.replace(temporary, parts[-1], src_dir_fd=directory, dst_dir_fd=directory)
                os.fsync(directory)
            finally:
                try:
                    os.unlink(temporary, dir_fd=directory)
                except FileNotFoundError:
                    pass

    def read_projection(self, area: str, relative: str) -> dict:
        if area not in {"state", "status", "logs"}:
            raise BoundaryError("not a projection area")
        parts = self._location(area, relative)
        with _directory(self.root, parts[:-1]) as directory:
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=directory)
            with os.fdopen(fd, "rb") as stream:
                import stat
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise BoundaryError("projection must be a regular file")
                value = json.load(stream)
        if (not isinstance(value, dict) or value.get("control_plane") != self.control_plane
                or set(value) != {"control_plane", "payload"} or not isinstance(value["payload"], dict)):
            raise BoundaryError("projection identity or schema mismatch")
        return value["payload"]
