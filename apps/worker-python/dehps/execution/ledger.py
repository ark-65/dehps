"""Canonical event/registration adapter for the minimal execution store."""
from datetime import datetime
from hashlib import sha256
from uuid import UUID

from psycopg.types.json import Jsonb

from dehps.research_os.models import MainlineArtifactRegistration, MainlineExecutionEvent, jsonable
from .context import BoundaryError
from .store import ExecutionStore


def canonical_records(context: dict) -> dict:
    task, commit, attempt = context['task'],context['commit'],context['attempt']
    if commit is None or attempt is None:
        raise BoundaryError('committed attempt required for mainline registration')
    execution = sha256(UUID(attempt['id']).bytes).hexdigest()
    if any(parent['commit'] is None for parent in context['parents']):
        raise BoundaryError('required parent is not committed')
    parents = sorted(set(context['definition']['input_artifact_digests']) |
                     {parent['commit']['artifact_sha256'] for parent in context['parents']})
    path = f"{task['control_plane']}/artifacts/objects/{commit['artifact_sha256']}.blob"
    registration = MainlineArtifactRegistration(
        execution_id=execution,control_plane_key=task['control_plane'],
        task_key=context['definition']['task_key'],task_digest=task['task_digest'],
        artifact_digest=commit['artifact_sha256'],artifact_type='execution-result',
        schema_version=task['artifact_schema'],artifact_path=path,parent_digests=tuple(parents),
    )
    payload = tuple(sorted({
        'artifact_sha256':commit['artifact_sha256'],'artifact_size':commit['artifact_size'],
        'artifact_schema':task['artifact_schema'],'verifier_id':task['verifier_id'],
        'release_sha256':task['release_sha256'],
        'scientific_contract_sha256':task['scientific_contract_sha256'],
    }.items()))
    records = {'registration':{'digest':registration.registration_digest,'value':jsonable(registration)}}
    for name, sequence, instant, body in (
            ('started',0,attempt['created_at'],()),('completed',1,commit['created_at'],payload)):
        event = MainlineExecutionEvent(
            execution_id=execution,control_plane_key=task['control_plane'],
            manifest_digest=task['manifest_digest'],task_key=context['definition']['task_key'],
            task_digest=task['task_digest'],capability=context['definition']['requested_capability'],
            event_type=name,sequence=sequence,recorded_at=datetime.fromisoformat(instant).isoformat(),payload=body,
        )
        records[name] = {'digest':event.artifact_digest,'value':jsonable(event)}
    return records


class MainlineLedger:
    def __init__(self, store: ExecutionStore):
        self.store = store

    def context(self, task_id: int, *, connection=None):
        if connection is not None:
            return connection.execute('SELECT execution_store.mainline_context(%s)',(task_id,)).fetchone()[0]
        with self.store.database.connect() as connection:
            return self.context(task_id,connection=connection)

    def register(self, connection, task_id: int) -> None:
        context = self.context(task_id,connection=connection)
        records = canonical_records(context)
        connection.execute('SELECT execution_store.record_mainline(%s,%s,%s,%s,%s)',
                           (task_id,*self.store.authorization.parameters(),Jsonb(records)))

    def recover_registration(self, task_id: int) -> None:
        # Re-verify durable artifact bytes before repairing only missing ledger
        # records. The compute function is never called by this path.
        if self.store.result(task_id) is None:
            raise BoundaryError('no committed result to register')
        with self.store.database.connect() as connection:
            self.register(connection,task_id)
        self.verify(task_id)

    def verify(self, task_id: int) -> str:
        if self.store.result(task_id) is None:
            raise BoundaryError('mainline result missing')
        context = self.context(task_id)
        expected = canonical_records(context)
        if context['records'] != expected or context['event_count'] != 2 or context['registration_count'] != 1:
            raise BoundaryError('canonical execution or artifact registration mismatch')
        return expected['completed']['value']['execution_id']
