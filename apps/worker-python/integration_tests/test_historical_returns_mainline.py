from datetime import datetime,timedelta,timezone
from dataclasses import asdict
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import psycopg
import pytest
from dehps.execution.store import ExecutionAuthorization
from dehps.notifications.historical_returns.plan import build_plan
from dehps.notifications.historical_returns.delivery import registered_emails
from conftest import authority
from test_execution_mainline import mainline, records
from historical_returns_scenario import engine

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
spec=importlib.util.spec_from_file_location('returns_fixture',Path(__file__).resolve().parents[1]/'tests/historical_returns_fixtures.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)


def setup(mainline,past=False):
    initial,admin,authorize=mainline
    c,_,_,_=helper.fixture(Path(initial['root'])/'inputs',gap=past)
    return authorize(build_plan(c)),admin


def child(config,mode):
    path=Path(config['root'])/'child.json';path.write_text(json.dumps(config));path.chmod(0o600)
    return [sys.executable,str(Path(__file__).with_name('historical_returns_scenario.py')),str(path),mode]


@pytest.mark.parametrize('past,expected',[(False,3),(True,3)])
def test_registered_pre_and_complete_gap_chain_new_process_readonly_replay(mainline,past,expected):
    config,admin=setup(mainline,past);e=engine(config);e.run()
    assert not e.task_errors and records(admin)['execution_store.commits']==expected
    emails=registered_emails(e);assert len(emails)==1
    assert emails[0]['seal_status']==('MISSING_PREDRAW_SEAL' if past else 'SEALED_BEFORE_DRAW')
    before=records(admin);engine(config).run();assert records(admin)==before
    result=subprocess.run(child(config,'replay'),capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['completed']==expected and records(admin)==before


def test_process_crash_and_concurrent_triggers_do_not_duplicate(mainline):
    config,admin=setup(mainline,True)
    result=subprocess.run(child(config,'kill-after-commit'),capture_output=True,text=True,timeout=60)
    assert result.returncode==-9 and records(admin)['execution_store.commits']==1
    processes=[subprocess.Popen(child(config,'run'),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
    for p in processes:
        out,err=p.communicate(timeout=60);assert p.returncode==0,err
    e=engine(config);e.run();assert not e.task_errors and records(admin)['execution_store.commits']==3


def test_ambiguous_commit_ack_recovers_without_new_attempt(mainline,monkeypatch):
    config,admin=setup(mainline,True);e=engine(config);original=e.store.commit;calls=[]
    def lost(*a,**kw):
        result=original(*a,**kw);calls.append(1)
        if len(calls)==1:raise psycopg.OperationalError('synthetic lost acknowledgement')
        return result
    monkeypatch.setattr(e.store,'commit',lost);e.run()
    assert records(admin)['execution_store.commits']==3
    assert records(admin)['execution_store.attempts']==3 and not e.task_errors


def test_report_failure_cannot_be_consumed_and_retry_keeps_original_seal(mainline):
    from dataclasses import replace
    from dehps.notifications.historical_returns.plan import CAPABILITIES
    config,admin=setup(mainline);e=engine(config)
    def failure(*args):
        raise OSError('synthetic report rendering failure')
    name=CAPABILITIES['report'];e.capabilities[name]=replace(e.capabilities[name],execute=failure)
    e.run();assert e.task_errors and records(admin)['execution_store.commits']==1
    assert registered_emails(engine(config))==[]
    root=Path(config['root'])/'learning/artifacts/objects'
    retained={p.name:p.read_bytes() for p in root.glob('*.blob')}
    resumed=engine(config);resumed.run()
    assert not resumed.task_errors and records(admin)['execution_store.commits']==3
    assert len(registered_emails(resumed))==1 and all((root/n).read_bytes()==v for n,v in retained.items())


@pytest.mark.parametrize('mode',['revoke','expire'])
def test_live_admission_loss_blocks_commit_and_keeps_replay(mainline,authority,mode,monkeypatch):
    initial,admin,_=mainline;c,_,_,_=helper.fixture(Path(initial['root'])/'inputs',gap=True)
    clients,_,_,_=authority;p=build_plan(c);rid=clients['engineer'].request(p.payload,'a'*64)
    content=clients['reviewer'].get(rid)['content_sha256'];expiry=datetime.now(timezone.utc)+timedelta(seconds=3 if mode=='expire' else 60)
    clients['reviewer'].approve(rid,content,'a'*64,expiry);execution=clients['operator'].begin(rid,content,'a'*64)
    b=clients['operator'].database
    config=dict(dsn=b.dsn,database=b.database,role=b.role,root=initial['root'],plan=p.payload,
                authorization=asdict(ExecutionAuthorization(execution,content,'a'*64)))
    e=engine(config);original=e.store.prepare
    def blocked(*a,**kw):
        result=original(*a,**kw)
        if mode=='revoke':clients['reviewer'].revoke(rid)
        else:time.sleep(max(0,(expiry-datetime.now(timezone.utc)).total_seconds())+0.1)
        return result
    monkeypatch.setattr(e.store,'prepare',blocked)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):e.run()
    assert records(admin)['execution_store.commits']==0
    before=records(admin);engine(config).replay(require_complete=False);assert records(admin)==before
