"""Fixture-only subprocess; real process death and SQL connection loss."""
import json
import os
from pathlib import Path
import signal
import sys

import psycopg
from psycopg import sql

from dehps.execution.artifacts import ArtifactStore
from dehps.execution.context import BoundaryError, RunContext
from dehps.execution.database import DatabaseBinding
from dehps.execution.store import Attempt, ExecutionAuthorization, ExecutionStore

PAYLOAD = b'{"schema":"fixture.v1","value":42}\n'
CONTRACT = 'c' * 64


def verify(task, data):
    if task['scientific_contract_sha256'] != CONTRACT or task['artifact_schema'] != 'fixture.v1' or data != PAYLOAD:
        raise BoundaryError('fixture scientific contract mismatch')


def make_store(config):
    return ExecutionStore(
        DatabaseBinding(config['dsn'], config['database'], config['role']),
        ArtifactStore(RunContext(Path(config['root']), 'learning')),
        ExecutionAuthorization(**config['authorization']), {'fixture.v1': verify},
    )


def main(config_path, mode):
    config = json.loads(Path(config_path).read_text())
    store = make_store(config)
    task_id = config['task_id']
    previous = store.result(task_id)
    if previous is not None:
        print('VERIFIED_COMMITTED')
        return
    attempt = store.claim(task_id, lease_seconds=1 if mode == 'before_commit' else 300)
    assert isinstance(attempt, Attempt)
    with open(Path(config['root']) / 'compute-count', 'ab') as count:
        count.write(b'computed\n')
        count.flush()
        os.fsync(count.fileno())
    artifact = store.prepare(task_id, PAYLOAD)
    if mode == 'before_commit':
        os.kill(os.getpid(), signal.SIGKILL)
    if mode == 'lost_commit_ack':
        # PostgreSQL commits, then terminates the connection before execute()
        # returns successfully. No stub substitutes commit, SQL or recovery.
        connection = store.database.connect()
        connection.autocommit = True
        parameters = (task_id, attempt.id, *store.authorization.parameters(), artifact.sha256, artifact.size)
        command = sql.SQL('BEGIN; SELECT execution_store.commit_result({},{},{},{},{},{},{}); COMMIT; SELECT pg_terminate_backend(pg_backend_pid())').format(*(sql.Literal(p) for p in parameters))
        try:
            connection.execute(command)
        except psycopg.OperationalError:
            os._exit(72)
        raise AssertionError('connection unexpectedly returned commit confirmation')
    store.commit(attempt, artifact)
    print('COMMITTED')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
