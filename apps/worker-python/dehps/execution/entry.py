"""Image-bound entry for independently registered capabilities, never legacy CLI.

The trusted release launcher verifies the actual image before starting this entry.
The container receives no Docker socket or administrator/reviewer credentials.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from importlib import import_module
import json
import os
from pathlib import Path
import re
from uuid import uuid4
from psycopg.errors import InsufficientPrivilege

from .artifacts import ArtifactStore
from .authority import AuthorityClient
from .context import BoundaryError, RunContext
from .coordinator import Coordinator
from .database import DatabaseBinding
from .plan import ExecutionPlan
from .release import Release
from .store import ExecutionAuthorization, ExecutionStore


@dataclass(frozen=True)
class CapabilityContext:
    inputs: Path
    code_root: Path
    release: Release


def execute(*, inputs: Path = Path('/inputs'), code_root: Path = Path('/opt/dehps/source'),
            runtime_root: Path = Path('/runtime'), config_path: Path = Path('/opt/dehps/config.json'),
            credentials_path: Path = Path('/run/dehps-credentials.json')) -> dict:
    action = os.environ['DEHPS_EXECUTION_ACTION']
    if action not in {'run', 'replay', 'replay-prefix'}:
        raise BoundaryError('unsupported execution action')
    context = RunContext(runtime_root, os.environ['DEHPS_CONTROL_DOMAIN'])
    launch_id = str(uuid4())

    def project(phase, error=None):
        # Before authenticated admission there is no execution ID to assert.
        # v2 consumers deliberately return UNKNOWN for this startup envelope,
        # instead of retaining a previous run's success. Never copy an identity
        # from an old status file or expose credentials in failure messages.
        context.write_projection('status', 'execution.json', {
            'schema': 'execution-entry-status.v1', 'run_id': launch_id,
            'phase': phase, 'error_type': error,
            'updated_at': datetime.now(timezone.utc).isoformat(),
        })

    if action == 'run':
        project('starting')
    try:
        return _execute(inputs, code_root, context, config_path, credentials_path, action)
    except Exception as exc:
        if action == 'run':
            project('failed', type(exc).__name__)
        raise


def _execute(inputs, code_root, context, config_path, credentials_path, action):
    release = Release.read(inputs / 'release.json', os.environ['DEHPS_RELEASE_SHA256'])
    config_bytes = config_path.read_bytes()
    if sha256(config_bytes).hexdigest() != release.payload['config_sha256']:
        raise BoundaryError('baked configuration differs from verified release')
    config = json.loads(config_bytes)
    required = {'schema','control_plane','factory','lease_seconds'}
    if not required <= set(config) <= required | {'dependency_constraints'} or config['schema'] != 'execution-entry.v1':
        raise BoundaryError('closed execution entry configuration required')
    if config['control_plane'] != os.environ['DEHPS_CONTROL_DOMAIN']:
        raise BoundaryError('launch and baked control domains differ')
    if type(config['lease_seconds']) is not int or not 1 <= config['lease_seconds'] <= 3600:
        raise BoundaryError('lease duration must be between 1 and 3600 seconds')
    if not isinstance(config['factory'],str) or not re.fullmatch(r'dehps\.[a-zA-Z0-9_.]+:[a-zA-Z_][a-zA-Z0-9_]*',config['factory']):
        raise BoundaryError('explicit release-local capability factory required')
    packet = json.loads((inputs / 'execution.json').read_bytes())
    if set(packet) != {'schema','request_id','plan'} or packet['schema'] != 'execution-input.v1':
        raise BoundaryError('closed execution input required')
    if type(packet['request_id']) is not int or packet['request_id'] <= 0:
        raise BoundaryError('positive admitted request identity required')
    plan = ExecutionPlan(packet['plan'])
    plan.validate()
    credentials = json.loads(credentials_path.read_bytes())
    if set(credentials) != {'dsn','database','role'}:
        raise BoundaryError('explicit scoped database credentials required')
    database = DatabaseBinding(**credentials)
    authority = AuthorityClient(database)
    request = authority.get(packet['request_id'])
    if (request['payload'] != plan.payload or request['release_sha256'] != release.digest
            or request['control_plane'] != config['control_plane']):
        raise BoundaryError('admitted plan/release differs from runtime input')
    def admission_wait():
        # The exact request/plan/release has been read and matched above. There
        # is no admitted current execution. Report a wait without copying an old
        # execution ID, renewing approval, claiming a task or reading its labels.
        waiting = {'schema': 'execution-admission-status.v1', 'phase': 'waiting',
            'run_id': str(uuid4()), 'request_id': request['id'], 'plan_digest': plan.digest,
            'release_sha256': release.digest, 'reason': 'AUTHORIZATION_REQUIRED',
            'updated_at': datetime.now(timezone.utc).isoformat()}
        context.write_projection('status', 'execution.json', waiting)
        return {**waiting, 'control_plane': config['control_plane'], 'artifacts': {}, 'tasks': {}}

    # Readonly replay never begins/reauthorizes an execution or repairs records.
    try:
        execution_id = authority.begin(request['id'],request['content_sha256'],release.digest) if action == 'run' else 0
    except InsufficientPrivilege:
        return admission_wait()
    store = ExecutionStore(database,ArtifactStore(context),
                           ExecutionAuthorization(execution_id,request['content_sha256'],release.digest),{})
    module, attribute = config['factory'].split(':')
    factory = getattr(import_module(module),attribute)
    capabilities = factory(plan,store,CapabilityContext(inputs,code_root,release))
    engine = Coordinator(plan,store,capabilities,lease_seconds=config['lease_seconds'])
    try:
        manifest = engine.run() if action == 'run' else engine.replay(require_complete=action != 'replay-prefix')
    except InsufficientPrivilege:
        if action != 'run':
            raise
        # Revocation/expiry during a computation must also retain a wait. The
        # store has already rejected its commit under the actual request lock.
        return admission_wait()
    if engine.projection_errors:
        raise BoundaryError('canonical execution persisted but status projection failed')
    artifacts = {}
    with store.verification_scope():
        for task in manifest.tasks:
            result = store.result(engine.bindings[task.artifact_digest])
            if result is not None:
                artifacts[task.task_key] = {
                    'sha256': result.artifact.sha256, 'size': result.artifact.size,
                    'schema': result.task['artifact_schema'],
                    'path': f'{context.control_plane}/artifacts/objects/{result.artifact.sha256}.blob',
                }
    return {'schema':'execution-entry-result.v1','run_id':engine.run_id,'action':action,
            'control_plane':config['control_plane'],'release_sha256':release.digest,
            'plan_digest':plan.digest,'manifest_digest':manifest.artifact_digest,
            'artifacts': artifacts,
            'wait_reasons': engine.wait_reasons, 'task_errors': engine.task_errors,
            'tasks':{t.task_key:manifest.task_state_by_digest[t.artifact_digest].declared_status.value
                     for t in manifest.tasks}}


if __name__ == '__main__':
    print(json.dumps(execute(),sort_keys=True))
