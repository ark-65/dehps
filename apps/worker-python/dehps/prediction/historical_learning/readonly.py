"""Historical inspection only, with the existing authenticated SQL read APIs.

Identity checks take FOR SHARE locks, so transaction_read_only is incompatible.
This facade rejects unintended writes before SQL and exposes neither a cursor
nor a connection. It is not a sandbox for arbitrary Python; the existing scoped
database grants and host authentication remain the security boundary.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path

from dehps.execution.artifacts import ArtifactStore
from dehps.execution.context import BoundaryError, RunContext, _directory
from dehps.execution.database import DatabaseBinding


READ_STATEMENTS = frozenset({
    'SELECT execution_authority.request_get(%s)',
    'SELECT execution_store.read_plan(%s)',
    'SELECT execution_store.read_result(%s)',
    'SELECT execution_store.mainline_context(%s)',
})
DOMAIN_OWNERS = {'learning': 61010, 'observer': 61011}


@dataclass(frozen=True)
class ReadResult:
    row: tuple | None

    def fetchone(self):
        return self.row


class ReadConnection:
    __slots__ = ('__connection',)

    def __init__(self, connection):
        self.__connection = connection

    def execute(self, statement, parameters):
        if type(statement) is not str or statement not in READ_STATEMENTS:
            raise BoundaryError('historical reader permits only four authenticated read statements')
        if not isinstance(parameters, tuple) or len(parameters) != 1:
            raise BoundaryError('historical reader requires one bound read parameter')
        return ReadResult(self.__connection.execute(statement, parameters).fetchone())


class ReadonlyDatabase(DatabaseBinding):
    @contextmanager
    def connect(self):
        # Normal transaction retains the identity locks used by SQL authority.
        with super().connect() as connection:
            yield ReadConnection(connection)


class ReadonlyContext(RunContext):
    def __post_init__(self):
        if self.control_plane not in DOMAIN_OWNERS:
            raise BoundaryError('historical reader requires learning or observer domain')
        if not isinstance(self.root, Path) or not self.root.is_absolute():
            raise BoundaryError('an explicit absolute runtime root is required')
        with _directory(self.root, ()) as fd:
            info = os.fstat(fd)
            owner = info.st_uid == os.geteuid()
            service = os.geteuid() == 0 and info.st_uid == DOMAIN_OWNERS[self.control_plane]
            if not (owner or service) or info.st_mode & 0o022:
                raise BoundaryError('historical reader runtime owner or permissions differ')

    def write_projection(self, *args, **kwargs):
        raise BoundaryError('historical reader cannot write projections')


class ReadonlyArtifacts(ArtifactStore):
    def prepare(self, *args, **kwargs):
        raise BoundaryError('historical reader cannot prepare artifacts')
