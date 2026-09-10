"""Required PostgreSQL/FK/file/process recovery checks, no persistence mocks."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from importlib.resources import files
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest

from dehps.execution.context import BoundaryError, RunContext
from dehps.execution.store import Attempt, ExecutionAuthorization, StoredResult
from dehps.research_os.models import (
    ControlPlaneManifest, Goal, GoalState, GoalStatus, ObjectiveClass,
    Task, TaskLane, TaskState, TaskStatus,
)
from store_scenario import CONTRACT, PAYLOAD, make_store

STORE_FUNCTIONS = (
    'register_task(bigint,text,text,jsonb)', 'read_result(bigint)',
    'claim(bigint,bigint,text,text,integer)',
    'renew(bigint,uuid,bigint,text,text,integer)',
    'fail(bigint,uuid,bigint,text,text,text)',
    'commit_result(bigint,uuid,bigint,text,text,text,bigint)',
)
RELEASE = 'a' * 64


@pytest.fixture
def persisted(authority, tmp_path):
    clients, admin_dsn, roles, owner = authority
    goal = Goal('fixture-goal', '1', ObjectiveClass.RUNTIME_CAPABILITY, ('durable result',), TaskLane.RESEARCH)
    task = Task('fixture-task', goal.goal_key, goal.artifact_digest, 'fixture', TaskLane.RESEARCH, requested_capability='fixture.v1')
    manifest = ControlPlaneManifest((goal,), (task,), (GoalState(goal.artifact_digest, GoalStatus.ACTIVE),), (TaskState(task.artifact_digest, TaskStatus.DRAFT),))
    with psycopg.connect(admin_dsn) as admin:
        assert admin.execute("SELECT current_setting('fsync'),current_setting('synchronous_commit')").fetchone() == ('on','on')
        dbname = admin.info.dbname
        admin.execute(sql.SQL('GRANT CREATE ON DATABASE {} TO {}').format(sql.Identifier(dbname), sql.Identifier(owner)))
        admin.execute(sql.SQL('GRANT CREATE ON SCHEMA public TO {}').format(sql.Identifier(owner)))
        admin.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(owner)))
        schema = Path(__file__).resolve().parents[3] / 'infra/postgres/init/002_research_os.sql'
        admin.execute(schema.read_text())
        admin.execute(files('dehps.execution').joinpath('migrations/002_store.sql').read_text())
        admin.execute('RESET ROLE')
        admin.execute(sql.SQL('REVOKE CREATE ON DATABASE {} FROM {}').format(sql.Identifier(dbname), sql.Identifier(owner)))
        admin.execute(sql.SQL('REVOKE CREATE ON SCHEMA public FROM {}').format(sql.Identifier(owner)))
        admin.execute('INSERT INTO public.research_os_goal_definitions (goal_digest,goal_key,semantic_version,objective_class,owner_lane,definition_json) VALUES (%s,%s,%s,%s,%s,%s)', (goal.artifact_digest, goal.goal_key, goal.semantic_version, goal.objective_class.value, goal.owner_lane.value, Jsonb(goal.to_dict())))
        admin.execute('INSERT INTO public.research_os_task_definitions (task_digest,task_key,goal_digest,task_type,lane,definition_json) VALUES (%s,%s,%s,%s,%s,%s)', (task.artifact_digest, task.task_key, task.goal_digest, task.task_type, task.lane.value, Jsonb(task.to_dict())))
        admin.execute('INSERT INTO public.research_os_manifests (manifest_digest,schema_version,manifest_json) VALUES (%s,%s,%s)', (manifest.artifact_digest, manifest.schema_version, Jsonb(manifest.to_dict())))
        admin.execute('INSERT INTO public.research_os_manifest_goals VALUES (%s,%s,0)', (manifest.artifact_digest, goal.artifact_digest))
        admin.execute('INSERT INTO public.research_os_manifest_tasks VALUES (%s,%s,0)', (manifest.artifact_digest, task.artifact_digest))
        admin.execute('INSERT INTO public.research_os_control_planes (control_plane_key,schema_version,current_manifest_digest) VALUES (%s,%s,%s)', ('learning', manifest.schema_version, manifest.artifact_digest))
        for role in roles.values():
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA execution_store TO {}').format(sql.Identifier(role)))
            for signature in STORE_FUNCTIONS:
                admin.execute(sql.SQL('GRANT EXECUTE ON FUNCTION execution_store.{} TO {}').format(sql.SQL(signature), sql.Identifier(role)))
    spec = dict(business_key='snapshot-1/fixture-task', task_digest=task.artifact_digest,
                manifest_digest=manifest.artifact_digest, scientific_contract_sha256=CONTRACT,
                verifier_id='fixture.v1', artifact_schema='fixture.v1')
    request = clients['engineer'].request({'schema':'execution-plan.v1','tasks':[spec]}, RELEASE)
    digest = clients['reviewer'].get(request)['content_sha256']
    clients['reviewer'].approve(request, digest, RELEASE, datetime.now(timezone.utc)+timedelta(hours=1))
    execution = clients['operator'].begin(request, digest, RELEASE)
    tmp_path.chmod(0o700)
    binding = clients['operator'].database
    config = dict(dsn=binding.dsn, database=binding.database, role=binding.role, root=str(tmp_path),
                  authorization=asdict(ExecutionAuthorization(execution,digest,RELEASE)))
    store = make_store(config)
    config['task_id'] = store.register(spec)
    yield store, config, clients, request, admin_dsn, spec


def child(config, mode):
    path = Path(config['root']) / 'fixture-config.json'
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    return subprocess.run([sys.executable, str(Path(__file__).with_name('store_scenario.py')), str(path), mode],
                          env={**os.environ, 'PYTHONPATH':str(Path(__file__).resolve().parents[1]), 'PYTHONDONTWRITEBYTECODE':'1'},
                          capture_output=True, text=True, timeout=15)


def counts(admin_dsn):
    with psycopg.connect(admin_dsn) as admin:
        return (admin.execute('SELECT status,reason FROM execution_store.attempts ORDER BY fence').fetchall(),
                admin.execute('SELECT count(*) FROM execution_store.commits').fetchone()[0])


@pytest.mark.parametrize('mode,expected_code,expected_attempts', [('before_commit',-9,2), ('lost_commit_ack',72,1)])
def test_process_death_and_new_process_resume(persisted, mode, expected_code, expected_attempts):
    store, config, _, _, admin_dsn, _ = persisted
    first = child(config, mode)
    assert first.returncode == expected_code, first.stderr
    objects = Path(config['root']) / 'learning/artifacts/objects'
    prepared = list(objects.glob('*.blob'))
    assert len(prepared) == 1
    before = prepared[0].stat()
    if mode == 'before_commit':
        assert store.result(config['task_id']) is None
        time.sleep(1.05)  # Real database lease expiry, not a mocked clock.
    for _ in range(2):
        resumed = child(config, 'resume')
        assert resumed.returncode == 0, resumed.stderr
    after = prepared[0].stat()
    assert (before.st_ino,before.st_mtime_ns) == (after.st_ino,after.st_mtime_ns)
    assert len(list(objects.glob('*.blob'))) == 1
    assert (Path(config['root'])/'compute-count').read_bytes().count(b'computed\n') == expected_attempts
    attempts, commits = counts(admin_dsn)
    assert len(attempts) == expected_attempts and commits == 1
    assert attempts[-1] == ('completed', None)
    if mode == 'before_commit':
        assert attempts[0] == ('failed','lease_expired')
    assert store.result(config['task_id']).data == PAYLOAD


def test_concurrent_claim_and_expired_executor_fencing(persisted):
    store, config, _, _, admin_dsn, _ = persisted
    task = config['task_id']
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda _: make_store(config).claim(task,lease_seconds=1), range(4)))
    live = [claim for claim in claims if isinstance(claim,Attempt)]
    assert len(live) == 1 and claims.count(None) == 3
    artifact = store.prepare(task,PAYLOAD)
    time.sleep(1.05)
    newer = store.claim(task)
    assert isinstance(newer,Attempt) and newer.fence == live[0].fence+1
    for action in (lambda: store.commit(live[0],artifact), lambda: store.renew(live[0]), lambda: store.fail(live[0],'stale')):
        with pytest.raises(psycopg.errors.InsufficientPrivilege,match='fenced'):
            action()
    store.commit(newer,artifact)
    assert isinstance(store.claim(task),StoredResult)
    assert counts(admin_dsn) == ([('failed','lease_expired'),('completed',None)],1)


def test_failed_attempt_preserved_and_repeated_commit_is_idempotent(persisted):
    store, config, _, _, admin_dsn, _ = persisted
    task = config['task_id']
    first = store.claim(task)
    with pytest.raises(BoundaryError,match='contract'):
        store.prepare(task,b'wrong science')
    store.fail(first,'verification_failed')
    next_attempt = store.claim(task)
    artifact = store.prepare(task,PAYLOAD)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        store.commit(first,artifact)
    store.commit(next_attempt,artifact)
    store.commit(next_attempt,artifact)
    assert counts(admin_dsn) == ([('failed','verification_failed'),('completed',None)],1)


def test_successful_renewal_retains_the_same_attempt(persisted):
    store, config, _, _, admin_dsn, _ = persisted
    task = config['task_id']
    attempt = store.claim(task,lease_seconds=1)
    store.renew(attempt,lease_seconds=30)
    time.sleep(1.05)
    assert store.claim(task) is None
    artifact = store.prepare(task,PAYLOAD)
    store.commit(attempt,artifact)
    with psycopg.connect(store.database.dsn) as connection:
        with pytest.raises(psycopg.errors.UniqueViolation,match='commit conflict'):
            connection.execute('SELECT execution_store.commit_result(%s,%s,%s,%s,%s,%s,%s)',
                               (task,attempt.id,*store.authorization.parameters(),'d'*64,artifact.size))
    assert store.result(task).data == PAYLOAD
    assert counts(admin_dsn) == ([('completed',None)],1)


def test_revocation_applies_to_actual_claim_renew_and_commit(persisted):
    store, config, clients, request, admin_dsn, _ = persisted
    task = config['task_id']
    attempt = store.claim(task)
    artifact = store.prepare(task,PAYLOAD)
    clients['reviewer'].revoke(request)
    for action in (lambda: store.claim(task),lambda: store.renew(attempt),lambda: store.commit(attempt,artifact)):
        with pytest.raises(psycopg.errors.InsufficientPrivilege,match='revoked'):
            action()
    assert counts(admin_dsn)[1] == 0


@pytest.mark.parametrize('damage',['missing','bytes','unknown_verifier'])
def test_committed_evidence_failure_blocks_resume_without_retraining(persisted,damage):
    store, config, _, _, admin_dsn, _ = persisted
    task = config['task_id']
    attempt = store.claim(task)
    artifact = store.prepare(task,PAYLOAD)
    store.commit(attempt,artifact)
    path = Path(config['root']) / 'learning/artifacts/objects' / f'{artifact.sha256}.blob'
    if damage == 'missing':
        path.unlink()
    elif damage == 'bytes':
        path.chmod(0o600)
        path.write_bytes(b'x'*artifact.size)
    else:
        store.verifiers = {}
    for action in (lambda: store.result(task),lambda: store.claim(task)):
        with pytest.raises((BoundaryError,FileNotFoundError)):
            action()
    assert counts(admin_dsn) == ([('completed',None)],1)


def test_unapproved_task_and_direct_sql_mutations_denied(persisted):
    store, config, _, _, admin_dsn, spec = persisted
    with pytest.raises(psycopg.errors.InsufficientPrivilege,match='outside approved'):
        store.register({**spec,'business_key':'unapproved'})
    for statement in ('DELETE FROM execution_store.tasks', 'UPDATE execution_store.attempts SET status=\'completed\'',
                      'TRUNCATE execution_store.commits','DELETE FROM execution_store.leases',
                      'SELECT execution_store.live_attempt(1,NULL,1,NULL,NULL)'):
        with psycopg.connect(store.database.dsn,autocommit=True) as connection:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                connection.execute(statement)
    assert counts(admin_dsn) == ([],0)


def test_canonical_parent_foreign_keys_and_business_definition_immutability(persisted):
    store, config, _, _, admin_dsn, spec = persisted
    assert store.register(spec) == config['task_id']
    with psycopg.connect(admin_dsn) as admin:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            admin.execute("INSERT INTO execution_store.tasks (control_plane,business_key,task_digest,manifest_digest,scientific_contract_sha256,release_sha256,verifier_id,artifact_schema,spec) VALUES ('learning','bad',%s,%s,%s,%s,'fixture.v1','fixture.v1',%s)", ('f'*64,spec['manifest_digest'],CONTRACT,RELEASE,Jsonb(spec)))
    with psycopg.connect(admin_dsn) as admin:
        with pytest.raises(psycopg.errors.RaiseException,match='immutable'):
            admin.execute("UPDATE execution_store.tasks SET business_key='rewrite'")


def test_projection_failure_cannot_reverse_a_commit(persisted):
    store, config, _, _, admin_dsn, _ = persisted
    task = config['task_id']
    attempt = store.claim(task)
    artifact = store.prepare(task,PAYLOAD)
    store.commit(attempt,artifact)
    root = Path(config['root'])
    (root/'learning/status').write_bytes(b'not a directory')
    with pytest.raises(OSError):
        store.artifacts.context.write_projection('status','result.json',{'status':'completed'})
    assert make_store(config).result(task).data == PAYLOAD
    assert counts(admin_dsn) == ([('completed',None)],1)


def test_database_server_restart_retains_committed_result(persisted):
    store, config, _, _, admin_dsn, _ = persisted
    first = child(config, 'resume')
    assert first.returncode == 0, first.stderr
    container = os.environ['DEHPS_EXECUTION_TEST_CONTAINER']
    # Never operate on an arbitrary Docker name: require the test label, admin
    # marker, matching published port and the exact connected cluster identity.
    inspection = subprocess.run(['docker','inspect',container],capture_output=True,text=True,check=True,timeout=10)
    info = json.loads(inspection.stdout)[0]
    assert info['Config']['Labels'].get('dehps.execution-test') == 'true'
    assert 'POSTGRES_DB=dehps_execution_test_admin' in info['Config']['Env']
    details = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    assert any(port['HostPort'] == details['port'] for port in info['HostConfig']['PortBindings']['5432/tcp']), 'restart test requires a fixed published port'
    assert any(port['HostPort'] == details['port'] for port in info['NetworkSettings']['Ports']['5432/tcp'])
    with psycopg.connect(admin_dsn) as connection:
        before = connection.execute('SELECT system_identifier FROM pg_control_system()').fetchone()[0]
        start = connection.execute('SELECT pg_postmaster_start_time()').fetchone()[0]
    identity = subprocess.run(['docker','exec',container,'psql','-U',details['user'],'-d','dehps_execution_test_admin','-Atc','SELECT system_identifier FROM pg_control_system()'],capture_output=True,text=True,check=True,timeout=10)
    assert identity.stdout.strip() == str(before)
    subprocess.run(['docker','restart','--time','0',container],capture_output=True,text=True,check=True,timeout=20)
    deadline = time.monotonic()+15
    while True:
        try:
            with psycopg.connect(admin_dsn,connect_timeout=1) as connection:
                after, restarted = connection.execute('SELECT system_identifier,pg_postmaster_start_time() FROM pg_control_system()').fetchone()
                assert after == before and restarted > start
            break
        except psycopg.OperationalError:
            assert time.monotonic() < deadline, 'disposable PostgreSQL did not restart'
            time.sleep(0.1)
    for _ in range(2):
        resumed = child(config,'resume')
        assert resumed.returncode == 0 and resumed.stdout.strip() == 'VERIFIED_COMMITTED', resumed.stderr
    assert (Path(config['root'])/'compute-count').read_bytes() == b'computed\n'
    assert counts(admin_dsn) == ([('completed',None)],1)
