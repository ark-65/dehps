from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timedelta,timezone
from importlib.resources import files
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psycopg
from psycopg import sql
import pytest

from dehps.execution.context import BoundaryError
from dehps.execution.coordinator import Coordinator
from dehps.execution.ledger import canonical_records
from dehps.execution.plan import ExecutionPlan
from dehps.execution.store import ExecutionAuthorization
from dehps.research_os.models import (
    ControlPlaneManifest,Goal,GoalState,GoalStatus,ObjectiveClass,Task,TaskDependency,
    DependencyType,TaskLane,TaskState,TaskStatus,
)
from mainline_scenario import CONTRACT,coordinator
from test_execution_store import STORE_FUNCTIONS

MAINLINE_FUNCTIONS=('admit_plan(bigint,text,text)','read_plan(text)','mainline_context(bigint)','record_mainline(bigint,bigint,text,text,jsonb)')
RELEASE='a'*64


def plan(names=('source','consume')):
    goal=Goal('graph-fixture','1',ObjectiveClass.RUNTIME_CAPABILITY,('verified downstream replay',),TaskLane.RESEARCH)
    integration={key:'fixture' for key in ('goal','ready_condition','runner','upstream_artifacts','downstream_artifacts','status_projection','downstream_consumer','evidence_progress_rule','decision_consumer')}
    tasks=[]
    for index,name in enumerate(names):
        dependencies=() if index==0 else (TaskDependency(DependencyType.TASK,names[index-1],'completed'),)
        tasks.append(Task(name,goal.goal_key,goal.artifact_digest,'fixture',TaskLane.RESEARCH,dependencies=dependencies,
                          requested_capability='fixture-'+name,metric_contract=json.dumps({'mainline_integration':integration})))
    manifest=ControlPlaneManifest((goal,),tuple(tasks),(GoalState(goal.artifact_digest,GoalStatus.ACTIVE),),tuple(TaskState(task.artifact_digest,TaskStatus.DRAFT) for task in tasks))
    specs=[dict(business_key=t.task_key,task_digest=t.artifact_digest,manifest_digest=manifest.artifact_digest,
                scientific_contract_sha256=CONTRACT,verifier_id='fixture-graph.v1',artifact_schema='fixture-graph.v1') for t in tasks]
    return ExecutionPlan.build(manifest,specs)


@pytest.fixture
def mainline(authority,tmp_path):
    clients,admin_dsn,roles,owner=authority
    with psycopg.connect(admin_dsn) as admin:
        admin.execute(sql.SQL('GRANT CREATE ON DATABASE {} TO {}').format(sql.Identifier(admin.info.dbname),sql.Identifier(owner)))
        admin.execute(sql.SQL('GRANT CREATE ON SCHEMA public TO {}').format(sql.Identifier(owner)))
        admin.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(owner)))
        admin.execute((Path(__file__).resolve().parents[3]/'infra/postgres/init/002_research_os.sql').read_text())
        for migration in ('002_store.sql','003_mainline.sql'):
            admin.execute(files('dehps.execution').joinpath('migrations/'+migration).read_text())
        admin.execute('RESET ROLE')
        admin.execute(sql.SQL('REVOKE CREATE ON DATABASE {} FROM {}').format(sql.Identifier(admin.info.dbname),sql.Identifier(owner)))
        admin.execute(sql.SQL('REVOKE CREATE ON SCHEMA public FROM {}').format(sql.Identifier(owner)))
        for role in roles.values():
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA execution_store TO {}').format(sql.Identifier(role)))
            for signature in (*STORE_FUNCTIONS,*MAINLINE_FUNCTIONS):
                admin.execute(sql.SQL('GRANT EXECUTE ON FUNCTION execution_store.{} TO {}').format(sql.SQL(signature),sql.Identifier(role)))
    tmp_path.chmod(0o700)
    def authorize(packet):
        request=clients['engineer'].request(packet.payload,RELEASE)
        digest=clients['reviewer'].get(request)['content_sha256']
        clients['reviewer'].approve(request,digest,RELEASE,datetime.now(timezone.utc)+timedelta(hours=1))
        execution=clients['operator'].begin(request,digest,RELEASE)
        binding=clients['operator'].database
        return dict(dsn=binding.dsn,database=binding.database,role=binding.role,root=str(tmp_path),plan=packet.payload,
                    authorization=asdict(ExecutionAuthorization(execution,digest,RELEASE)))
    yield authorize(plan()),admin_dsn,authorize


def child(config,mode):
    config_path=Path(config['root'])/'mainline-config.json'
    config_path.write_text(json.dumps(config));config_path.chmod(0o600)
    return subprocess.run([sys.executable,str(Path(__file__).with_name('mainline_scenario.py')),str(config_path),mode],
                          env={'PATH':os.defpath,'PYTHONPATH':str(Path(__file__).resolve().parents[1]),'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=20)


def records(admin_dsn):
    with psycopg.connect(admin_dsn) as admin:
        return {name:admin.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(*name.split('.')))).fetchone()[0]
                for name in ('execution_store.commits','execution_store.attempts','public.research_os_mainline_execution_events','public.research_os_mainline_artifacts')}


def test_canonical_dag_executes_downstream_and_replays_in_new_process(mainline):
    config,admin_dsn,_=mainline
    completed=child(config,'normal')
    assert completed.returncode==0,completed.stderr
    status=Path(config['root'])/'learning/status/execution.json'
    status_mtime=status.stat().st_mtime_ns
    replayed=child(config,'replay')
    assert replayed.returncode==0,replayed.stderr
    first,last=json.loads(completed.stdout),json.loads(replayed.stdout)
    assert status.stat().st_mtime_ns==status_mtime
    assert first['run_id']!=last['run_id'] and first['manifest']==last['manifest']
    assert all(t['status']=='completed' and t['completion_classification']=='COMPLETE' for t in first['manifest']['tasks'])
    assert records(admin_dsn)=={'execution_store.commits':2,'execution_store.attempts':2,'public.research_os_mainline_execution_events':4,'public.research_os_mainline_artifacts':2}
    for name in ('source','consume'):
        assert (Path(config['root'])/(name+'.calls')).read_bytes()==b'compute\n'
    with psycopg.connect(admin_dsn) as admin:
        parents=admin.execute("SELECT parent_digests_json FROM public.research_os_mainline_artifacts WHERE task_key='consume'").fetchone()[0]
        source=admin.execute("SELECT artifact_digest FROM public.research_os_mainline_artifacts WHERE task_key='source'").fetchone()[0]
        assert parents==[source]
    print(json.dumps({'canonical_run_id':first['run_id'],'replay_run_id':last['run_id'],
                      'completed_manifest_digest':ControlPlaneManifest.from_dict(first['manifest']).artifact_digest}))


@pytest.mark.parametrize('mode',['before_next','during_registration'])
def test_real_process_interruption_preserves_atomic_records_and_downstream_resume(mainline,mode):
    config,admin_dsn,_=mainline
    interrupted=child(config,mode)
    assert interrupted.returncode==-9,interrupted.stderr
    prior=records(admin_dsn)
    if mode=='during_registration':
        assert prior['execution_store.commits']==0 and prior['public.research_os_mainline_execution_events']==0
    else:
        assert prior['execution_store.commits']==1 and prior['public.research_os_mainline_execution_events']==2
    time.sleep(1.05)
    resumed=child(config,'normal');assert resumed.returncode==0,resumed.stderr
    replayed=child(config,'replay');assert replayed.returncode==0,replayed.stderr
    assert records(admin_dsn)['execution_store.commits']==2
    assert records(admin_dsn)['public.research_os_mainline_execution_events']==4
    expected_source=2 if mode=='during_registration' else 1
    assert (Path(config['root'])/'source.calls').read_bytes().count(b'compute\n')==expected_source


def test_committed_component_result_requires_registration_before_canonical_completion(mainline):
    config,admin_dsn,_=mainline
    engine=coordinator(config);engine.admit()
    task=engine.initial.tasks[0];task_id=engine.bindings[task.artifact_digest]
    attempt=engine.store.claim(task_id)
    data=engine.capabilities[task.requested_capability].execute(task,{},engine.store.artifacts)
    artifact=engine.store.prepare(task_id,data)
    engine.store.commit(attempt,artifact)
    with pytest.raises(BoundaryError,match='registration mismatch'):
        engine.replay()
    assert records(admin_dsn)['public.research_os_mainline_execution_events']==0
    engine.run();engine.replay()
    assert (Path(config['root'])/'source.calls').read_bytes()==b'compute\n'
    assert records(admin_dsn)['public.research_os_mainline_execution_events']==4


def test_unregistered_capability_and_altered_canonical_digest_fail_closed(mainline):
    config,admin_dsn,_=mainline
    changed=deepcopy(config)
    changed['plan']['canonical']['tasks'][0]['digest']='f'*64
    with pytest.raises(BoundaryError,match='digest'):
        coordinator(changed)
    engine=coordinator(config)
    with pytest.raises(BoundaryError,match='not registered'):
        Coordinator(engine.plan,engine.store,{})
    assert records(admin_dsn)['execution_store.attempts']==0


def test_another_registered_capability_extends_completed_plan_without_core_changes(mainline):
    config,admin_dsn,authorize=mainline
    coordinator(config).run()
    extended=plan(('source','consume','extend'))
    # Preserve old business/implementation bindings for already committed tasks.
    old_specs={s['business_key']:s for s in config['plan']['tasks']}
    extended.payload['tasks']=[old_specs.get(s['business_key'],s) for s in extended.payload['tasks']]
    extended.validate()
    added=authorize(extended)
    result=coordinator(added).run()
    assert len(result.tasks)==3
    coordinator(added).replay()
    assert records(admin_dsn)['execution_store.commits']==3
    for name in ('source','consume','extend'):
        assert (Path(config['root'])/(name+'.calls')).read_bytes()==b'compute\n'


def test_automatic_lease_renewal_covers_longer_computation(mainline):
    config,admin_dsn,_=mainline
    result=child(config,'long_source')
    assert result.returncode==0,result.stderr
    assert records(admin_dsn)['execution_store.attempts']==2
    assert records(admin_dsn)['execution_store.commits']==2


def test_revoked_authority_blocks_writes_but_read_only_replay_preserves_facts(mainline,authority):
    config,admin_dsn,_=mainline
    clients,_,_,_=authority
    engine=coordinator(config);engine.run()
    before=records(admin_dsn)
    with psycopg.connect(admin_dsn) as admin:
        request=admin.execute('SELECT request_id FROM execution_authority.executions WHERE id=%s',(config['authorization']['execution_id'],)).fetchone()[0]
    clients['reviewer'].revoke(request)
    with pytest.raises(psycopg.errors.InsufficientPrivilege,match='revoked'):
        engine.run()
    engine.replay()
    assert records(admin_dsn)==before


def test_child_cannot_register_before_parent_and_record_failure_is_atomic(mainline):
    config,admin_dsn,_=mainline
    engine=coordinator(config);engine.admit()
    child_task=engine.initial.tasks[1];task_id=engine.bindings[child_task.artifact_digest]
    attempt=engine.store.claim(task_id)
    data=json.dumps({'task_digest':child_task.artifact_digest,'value':8,'schema':'fixture-graph.v1'}).encode()
    artifact=engine.store.prepare(task_id,data)
    with pytest.raises(BoundaryError,match='parent is not committed'):
        engine.store.commit(attempt,artifact,register=engine.ledger.register)
    def direct_registration(connection,task_id):
        connection.execute("SELECT execution_store.record_mainline(%s,%s,%s,%s,'{}'::jsonb)",
                           (task_id,*engine.store.authorization.parameters()))
    with pytest.raises(psycopg.errors.RaiseException,match='parent mainline'):
        engine.store.commit(attempt,artifact,register=direct_registration)
    assert records(admin_dsn)['execution_store.commits']==0
    assert records(admin_dsn)['public.research_os_mainline_execution_events']==0
    engine.store.fail(attempt,'parent_unavailable')
    engine.run();engine.replay()
    assert records(admin_dsn)['execution_store.attempts']==3


def test_raw_sql_cannot_create_readable_completion_with_forged_digest(mainline):
    config,admin_dsn,_=mainline
    engine=coordinator(config);engine.admit()
    task=engine.initial.tasks[0];task_id=engine.bindings[task.artifact_digest]
    attempt=engine.store.claim(task_id)
    data=engine.capabilities[task.requested_capability].execute(task,{},engine.store.artifacts)
    artifact=engine.store.prepare(task_id,data)
    engine.store.commit(attempt,artifact)
    record=canonical_records(engine.ledger.context(task_id))
    record['completed']['digest']='e'*64
    from psycopg.types.json import Jsonb
    with engine.store.database.connect() as connection:
        with pytest.raises(psycopg.errors.RaiseException,match='event digest mismatch'):
            connection.execute('SELECT execution_store.record_mainline(%s,%s,%s,%s,%s)',
                               (task_id,*engine.store.authorization.parameters(),Jsonb(record)))
    with pytest.raises(BoundaryError,match='registration mismatch'):
        engine.replay()
    assert records(admin_dsn)['public.research_os_mainline_execution_events']==0
    engine.run();engine.replay()
    assert (Path(config['root'])/'source.calls').read_bytes()==b'compute\n'


def test_verifier_failure_blocks_every_replay_and_downstream_read(mainline):
    config,admin_dsn,_=mainline
    engine=coordinator(config);engine.run()
    before=records(admin_dsn)
    def reject(binding,data):
        raise BoundaryError('versioned policy rejected')
    engine.store.verifiers={'fixture-graph.v1':reject}
    task_id=next(iter(engine.bindings.values()))
    for read in (lambda:engine.store.result(task_id),engine.replay,engine.run):
        with pytest.raises(BoundaryError,match='versioned policy rejected'):
            read()
    assert records(admin_dsn)==before


def test_runtime_record_digest_preserves_legacy_ascii_unicode_and_integer_semantics(mainline):
    _,admin_dsn,_=mainline
    from dehps.research_os.models import MainlineExecutionEvent,MainlineArtifactRegistration,jsonable
    from psycopg.types.json import Jsonb
    event=MainlineExecutionEvent('a'*64,'learning','b'*64,'验证🙂\x7f\\\n','c'*64,'fixture','completed',1,
                                 '2026-09-10T02:00:00+00:00',(('size',9223372036854775807),('text','汉字🙂\b\t/"')))
    registration=MainlineArtifactRegistration('a'*64,'learning','验证🙂','b'*64,'c'*64,'execution-result','v1','学习/🙂.blob')
    with psycopg.connect(admin_dsn) as admin:
        for kind,value,digest in (('event',event,event.artifact_digest),('registration',registration,registration.registration_digest)):
            actual=admin.execute('SELECT execution_store.record_digest_v1(%s,%s)',(kind,Jsonb(jsonable(value)))).fetchone()[0]
            assert actual==digest
        with pytest.raises(psycopg.errors.RaiseException,match='integer numeric'):
            admin.execute("SELECT execution_store.record_digest_v1('event',%s)",(Jsonb({'scientific_float':1.5}),))
