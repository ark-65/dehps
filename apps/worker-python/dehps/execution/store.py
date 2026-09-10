"""Minimal authenticated execution store with the same verifier on every read.

Capability registration/dispatch is supplied by the entry point. This module
knows no experiment names or historical incident IDs. It never loads .env,
initializes a database, changes a source contract or treats status JSON as truth.
"""
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from uuid import UUID

from psycopg.types.json import Jsonb

from .artifacts import ArtifactStore, PreparedArtifact
from .context import BoundaryError
from .database import DatabaseBinding

Verifier = Callable[[dict, bytes], None]


@dataclass(frozen=True)
class ExecutionAuthorization:
    execution_id: int
    content_sha256: str
    release_sha256: str

    def parameters(self):
        return self.execution_id, self.content_sha256, self.release_sha256


@dataclass(frozen=True)
class Attempt:
    task_id: int
    id: UUID
    fence: int


@dataclass(frozen=True)
class StoredResult:
    task: dict
    artifact: PreparedArtifact
    data: bytes


class ExecutionStore:
    def __init__(self, database: DatabaseBinding, artifacts: ArtifactStore,
                 authorization: ExecutionAuthorization, verifiers: Mapping[str, Verifier]):
        self.database = database
        self.artifacts = artifacts
        self.authorization = authorization
        self.verifiers = dict(verifiers)

    def register(self, spec: dict) -> int:
        with self.database.connect() as connection:
            return connection.execute(
                'SELECT execution_store.register_task(%s,%s,%s,%s)',
                (*self.authorization.parameters(), Jsonb(spec)),
            ).fetchone()[0]

    def _snapshot(self, task_id: int) -> dict:
        with self.database.connect() as connection:
            snapshot = connection.execute('SELECT execution_store.read_result(%s)', (task_id,)).fetchone()[0]
        if snapshot['task']['control_plane'] != self.artifacts.context.control_plane:
            raise BoundaryError('database and filesystem control domains differ')
        return snapshot

    def _verify(self, task: dict, data: bytes) -> None:
        try:
            verifier = self.verifiers[task['verifier_id']]
        except KeyError:
            raise BoundaryError('unknown verifier version') from None
        # The same complete task binding reaches commit, readback, replay and
        # downstream consumers. Verification exceptions propagate fail-closed.
        verifier(task, data)

    def result(self, task_id: int) -> StoredResult | None:
        snapshot = self._snapshot(task_id)
        commit = snapshot['commit']
        if commit is None:
            return None
        artifact = PreparedArtifact(commit['artifact_sha256'], commit['artifact_size'])
        data = self.artifacts.read(artifact)
        self._verify(snapshot['task'], data)
        return StoredResult(snapshot['task'], artifact, data)

    def claim(self, task_id: int, *, lease_seconds: int = 300) -> Attempt | StoredResult | None:
        # Reject a wrong filesystem binding before admitting a computation.
        self._snapshot(task_id)
        with self.database.connect() as connection:
            response = connection.execute(
                'SELECT execution_store.claim(%s,%s,%s,%s,%s)',
                (task_id, *self.authorization.parameters(), lease_seconds),
            ).fetchone()[0]
        if response['status'] == 'committed':
            return self.result(task_id)
        if response['status'] == 'busy':
            return None
        attempt = response['attempt']
        return Attempt(task_id, UUID(attempt['id']), attempt['fence'])

    def renew(self, attempt: Attempt, *, lease_seconds: int = 300) -> None:
        with self.database.connect() as connection:
            connection.execute("SET LOCAL statement_timeout = '5s'")
            connection.execute(
                'SELECT execution_store.renew(%s,%s,%s,%s,%s,%s)',
                (attempt.task_id, attempt.id, *self.authorization.parameters(), lease_seconds),
            )

    def fail(self, attempt: Attempt, reason: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                'SELECT execution_store.fail(%s,%s,%s,%s,%s,%s)',
                (attempt.task_id, attempt.id, *self.authorization.parameters(), reason),
            )

    def prepare(self, task_id: int, data: bytes) -> PreparedArtifact:
        snapshot = self._snapshot(task_id)
        self._verify(snapshot['task'], data)
        return self.artifacts.prepare(data)

    def commit(self, attempt: Attempt, artifact: PreparedArtifact, *, register=None) -> StoredResult:
        snapshot = self._snapshot(attempt.task_id)
        data = self.artifacts.read(artifact)
        self._verify(snapshot['task'], data)
        with self.database.connect() as connection:
            # Function reauthorizes under the transaction's request/task locks.
            connection.execute(
                'SELECT execution_store.commit_result(%s,%s,%s,%s,%s,%s,%s)',
                (attempt.task_id, attempt.id, *self.authorization.parameters(), artifact.sha256, artifact.size),
            )
            if register is not None:
                # Trusted entry-point sink: canonical registrations participate
                # in the same transaction; capability code receives no connection.
                register(connection, attempt.task_id)
        result = self.result(attempt.task_id)
        if result is None:
            raise BoundaryError('committed result missing on readback')
        return result
