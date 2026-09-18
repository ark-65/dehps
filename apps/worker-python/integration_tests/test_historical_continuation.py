"""Real committed mixed-release prefix, never rewritten or refitted."""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import psycopg
import pytest

from conftest import authority_fixture
from historical_scenario import engine
from test_execution_mainline import mainline_fixture, records
from test_historical_learning_mainline import helper
from dehps.execution.context import BoundaryError
from dehps.execution.release import canonical
from dehps.execution.store import ExecutionAuthorization
from dehps.prediction.forward_learning import calculation as fixed
from dehps.prediction.historical_learning import capabilities, contract, continuation, plan
from dehps.prediction.historical_learning.publisher import publish_observations


@pytest.fixture
def domains(tmp_path):
    with ExitStack() as stack:
        result = {}
        for domain in ('learning', 'observer'):
            identities = stack.enter_context(contextmanager(authority_fixture)(domain))
            root = tmp_path/domain; root.mkdir()
            _, admin, _ = stack.enter_context(contextmanager(mainline_fixture)(identities, root))
            clients = identities[0]
            def authorize(packet, release, clients=clients, root=root, domain=domain):
                request = clients['engineer'].request(packet.payload, release)
                digest = clients['reviewer'].get(request)['content_sha256']
                clients['reviewer'].approve(request, digest, release, datetime.now(timezone.utc)+timedelta(hours=1))
                execution = clients['operator'].begin(request, digest, release)
                db = clients['operator'].database
                return dict(dsn=db.dsn, database=db.database, role=db.role, root=str(root), domain=domain,
                    plan=packet.payload, authorization=asdict(ExecutionAuthorization(execution, digest, release)))
            result[domain] = dict(root=root, admin=admin, authorize=authorize, clients=clients)
        yield result


def setup_prefix(domains, monkeypatch, release_sha256="a"*64, count=904):
    root = domains['learning']['root']
    c, _, key = helper.fixture(root/'inputs', count=count)
    shutil.copytree(root/'inputs', domains['observer']['root']/'inputs')
    configs = {d: v['authorize'](plan.build_plan(c, domain=d), release_sha256) for d,v in domains.items()}
    first = engine(configs['learning'])
    capability = first.capabilities[plan.CAPABILITIES['learn']]
    def two_only(task, parents):
        if json.loads(task.metric_contract)['historical']['index'] >= 902:
            return 'ISOLATED_PREFIX_STOP'
        return capability.ready(task, parents)
    first.capabilities[plan.CAPABILITIES['learn']] = replace(capability, ready=two_only)
    first.run()
    expiry = (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
    publish_observations(contract.Inputs(domains['observer']['root']/'inputs', contract.digest(c)),
        engine(configs['learning']), key, approved_until=expiry)
    engine(configs['observer']).run()
    value = continuation.capture(c, {d:engine(config) for d,config in configs.items()},
        next_releases={'learning':'b'*64, 'observer':'c'*64}, original_approved_until=expiry)
    assert value['retained_count'] == 2
    return c, key, configs, value


def install_contract(domains, original, value):
    configs = {}
    for domain, environment in domains.items():
        (environment['root']/'inputs/continuation.json').write_bytes(canonical(value))
        configs[domain] = environment['authorize'](plan.build_plan(original, domain=domain, continuation=value),
                                                  value['domains'][domain]['next_release_sha256'])
    return configs


def test_new_release_continues_actual_old_prefix_reports_and_readonly_replay(domains, monkeypatch):
    fit = fixed.fit_checkpoint; calls = []
    def counted(counts, count):
        calls.append(count); return fit(counts, count)
    monkeypatch.setattr(fixed, 'fit_checkpoint', counted)
    c, key, old_configs, value = setup_prefix(domains, monkeypatch)
    assert calls == [900, 901]
    old_bytes = {d:{p:p.read_bytes() for p in (v['root']/d/'artifacts/objects').glob('*.blob')}
                 for d,v in domains.items()}
    # Original deadline remains a stop even outside the formal priority window.
    class Later(datetime):
        @classmethod
        def now(cls, tz=None):return datetime.now(tz)+timedelta(hours=25)
    with monkeypatch.context() as m:
        m.setattr(capabilities, 'datetime', Later)
        stopped = engine(old_configs['learning']); stopped.run()
        assert 'HISTORICAL_BATCH_BUDGET_EXHAUSTED' in stopped.wait_reasons.values()
    configs = install_contract(domains, c, value)
    new = engine(configs['learning'])
    commit = new.store.commit
    def lost_ack(*args, **kwargs):
        result = commit(*args, **kwargs)
        if json.loads(result.data)['phase'] == 'learn' and calls == [900,901,902]:
            raise psycopg.OperationalError('isolated continuation acknowledgement lost AFTER commit')
        return result
    monkeypatch.setattr(new.store, 'commit', lost_ack)
    def report_failure(*args):raise OSError('isolated continuation report rendering failure')
    report_cap = plan.CAPABILITIES['report']
    new.capabilities[report_cap] = replace(new.capabilities[report_cap], execute=report_failure)
    new.run()
    assert records(domains['learning']['admin'])['execution_store.commits'] == 8
    new = engine(configs['learning']); new.run()
    assert calls == [900,901,902,903]
    assert records(domains['learning']['admin'])['execution_store.commits'] == 11
    observer_inputs = contract.Inputs(domains['observer']['root']/'inputs', contract.digest(c))
    old_observations = {p:p.read_bytes() for p in (observer_inputs.root/'observations').glob('*.json')}
    assert publish_observations(observer_inputs, engine(configs['learning']), key,
        approved_until=value['original_approved_until']) == [-1,902,903]
    observed = engine(configs['observer']); observed.run()
    assert records(domains['observer']['admin'])['execution_store.commits'] == 6
    assert all(p.read_bytes()==b for p,b in old_observations.items())
    assert all(p.read_bytes()==b for files in old_bytes.values() for p,b in files.items())
    assert '保留原版本 2 期' in (observer_inputs.root/'reports/summary.md').read_text()
    counts = {d:records(v['admin']) for d,v in domains.items()}
    engine(configs['learning']).run(); engine(configs['observer']).run()
    assert calls == [900,901,902,903]
    replays = {}
    for group, candidates in [('old',old_configs), ('new',configs)]:
        for domain, config in candidates.items():
            p=domains[domain]['root']/(group+'-replay.json');p.write_text(json.dumps(config));p.chmod(0o600)
            replay=subprocess.run([sys.executable,str(Path(__file__).with_name('historical_scenario.py')),str(p),'replay'],
                capture_output=True,text=True,timeout=120,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
            assert replay.returncode==0,replay.stderr
            replays[group+'-'+domain]=json.loads(replay.stdout)['run_id']
    assert {d:records(v['admin']) for d,v in domains.items()} == counts
    progress=json.loads((domains['learning']['root']/'learning/status/execution.json').read_text())['payload']['capability_progress']
    assert progress['historical_learned']==4 and progress['continuation']['retained_prefix_count']==2
    assert progress['continuation']['new_committed_count']==2
    print(json.dumps({'scope':'DISPOSABLE_POSTGRES_CONTINUATION','learning_run':new.run_id,'observer_run':observed.run_id,
        'replays':replays,'fits':calls,'records':counts,'prefix_bytes_preserved':True,'retained':2,'new_committed':2}))


def test_wrong_prefix_digest_fails_without_new_learning(domains, monkeypatch):
    c, _, _, value = setup_prefix(domains, monkeypatch)
    wrong = deepcopy(value)
    name = next(iter(wrong['domains']['learning']['artifacts']))
    wrong['domains']['learning']['artifacts'][name]='f'*64
    configs = install_contract(domains,c,wrong)
    before=records(domains['learning']['admin'])
    monkeypatch.setattr(fixed,'fit_checkpoint',lambda *a:pytest.fail('corrupt prefix trained'))
    with pytest.raises(BoundaryError,match='retained artifact identity'):
        engine(configs['learning']).run()
    assert records(domains['learning']['admin'])==before


def test_continuation_contract_requires_exact_complete_prefix_and_finite_budget(domains, monkeypatch):
    c, _, _, value = setup_prefix(domains, monkeypatch)
    for mutate in [lambda v:v.update(budget_seconds=86401),
                   lambda v:v['domains']['observer']['artifacts'].pop(next(iter(v['domains']['observer']['artifacts']))),
                   lambda v:v['domains']['learning'].update(next_release_sha256='a'*64),
                   lambda v:v.update(retained_count=3)]:
        wrong=deepcopy(value);mutate(wrong)
        with pytest.raises(BoundaryError):plan.build_plan(c,continuation=wrong)
    assert continuation.deadline(value,datetime.now(timezone.utc).isoformat())==value['original_approved_until']


def test_continuation_process_interruption_concurrent_resume_and_revocation(domains, monkeypatch):
    c, _, _, value = setup_prefix(domains, monkeypatch)
    configs = install_contract(domains,c,value)
    root = domains['learning']['root'];config=configs['learning']
    path=root/'child.json';path.write_text(json.dumps(config));path.chmod(0o600)
    args=[sys.executable,str(Path(__file__).with_name('historical_scenario.py')),str(path)]
    killed=subprocess.run([*args,'kill-after-update'],capture_output=True,text=True,timeout=120)
    assert killed.returncode == -9,killed.stderr
    assert records(domains['learning']['admin'])['execution_store.commits']==7
    children=[subprocess.Popen([*args,'run'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
    for child in children:
        out,err=child.communicate(timeout=120)
        assert child.returncode==0,err
    assert (root/'fit-calls').read_text().splitlines()==['902','903']
    assert records(domains['learning']['admin'])['execution_store.commits']==11
    with psycopg.connect(domains['learning']['admin']) as db:
        request=db.execute('SELECT request_id FROM execution_authority.executions WHERE id=%s',
                          (config['authorization']['execution_id'],)).fetchone()[0]
    domains['learning']['clients']['reviewer'].revoke(request)
    before=records(domains['learning']['admin'])
    with pytest.raises(psycopg.errors.InsufficientPrivilege):engine(config).run()
    engine(config).replay(require_complete=False)
    assert records(domains['learning']['admin'])==before


def test_continuation_deadline_rolls_back_commit_and_restart_keeps_anchor(domains, monkeypatch):
    c, _, _, value = setup_prefix(domains, monkeypatch)
    value['budget_seconds']=5
    config=install_contract(domains,c,value)['learning']
    fit=fixed.fit_checkpoint
    def slow(*args):
        result=fit(*args);time.sleep(5.1);return result
    monkeypatch.setattr(fixed,'fit_checkpoint',slow)
    first=engine(config)
    with pytest.raises(BoundaryError, match='transaction exceeded budget'):
        first.run()
    assert records(domains['learning']['admin'])['execution_store.commits']==6
    preserved={p:p.read_bytes() for p in (domains['learning']['root']/'learning/artifacts/objects').glob('*.blob')}
    monkeypatch.setattr(fixed,'fit_checkpoint',lambda *a:pytest.fail('exhausted continuation trained'))
    resumed=engine(config);resumed.run()
    assert 'HISTORICAL_BATCH_BUDGET_EXHAUSTED' in resumed.wait_reasons.values()
    assert records(domains['learning']['admin'])['execution_store.commits']==6
    assert all(p.read_bytes()==b for p,b in preserved.items())


def test_expired_original_window_cannot_be_extended_by_new_release(domains, monkeypatch):
    c, _, _, value = setup_prefix(domains, monkeypatch)
    value['original_approved_until']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    config=install_contract(domains,c,value)['learning']
    before=records(domains['learning']['admin'])
    monkeypatch.setattr(fixed,'fit_checkpoint',lambda *a:pytest.fail('expired original window trained'))
    stopped=engine(config);stopped.run()
    assert 'AUTHORIZATION_REQUIRED' in stopped.wait_reasons.values()
    assert records(domains['learning']['admin'])==before


def test_second_continuation_retains_mixed_releases_and_all_budget_anchors(domains, monkeypatch):
    fit = fixed.fit_checkpoint; calls = []
    def counted(counts, count):
        calls.append(count); return fit(counts, count)
    monkeypatch.setattr(fixed, 'fit_checkpoint', counted)
    c, key, _, first = setup_prefix(domains, monkeypatch, count=906)
    configs = install_contract(domains, c, first)
    partial = engine(configs['learning'])
    capability = partial.capabilities[plan.CAPABILITIES['learn']]
    partial.capabilities[plan.CAPABILITIES['learn']] = replace(capability,
        ready=lambda task, parents: ('ISOLATED_SECOND_PREFIX_STOP'
            if json.loads(task.metric_contract)['historical']['index'] >= 904
            else capability.ready(task, parents)))
    partial.run()
    observer_inputs = contract.Inputs(domains['observer']['root']/'inputs', contract.digest(c))
    publish_observations(observer_inputs, engine(configs['learning']), key,
                         approved_until=first['original_approved_until'])
    engine(configs['observer']).run()
    assert calls == [900, 901, 902, 903]
    preserved = {p:p.read_bytes() for domain, item in domains.items()
                 for p in (item['root']/domain/'artifacts/objects').glob('*.blob')}
    second = continuation.capture(c, {d:engine(v) for d,v in configs.items()},
        next_releases={'learning':'d'*64, 'observer':'e'*64},
        original_approved_until=first['original_approved_until'], prior_continuation=first)
    assert second['schema'] == continuation.CHAIN_SCHEMA and second['retained_count'] == 4
    assert canonical(second['prior_continuation']) == canonical(first)
    for domain in domains:
        tasks = plan.build_plan(c, domain=domain, continuation=second).validate().tasks
        assert sum(json.loads(t.metric_contract)['historical']['phase'] in {'resume','observe-resume'}
                   for t in tasks) == 2
    for mutate in [lambda v:v.update(original_approved_until='2099-01-01T00:00:00+00:00'),
                   lambda v:v.update(retained_count=2),
                   lambda v:v['domains']['learning'].update(next_release_sha256='a'*64),
                   lambda v:v['domains']['learning'].update(prior_release_sha256='f'*64),
                   lambda v:v['prior_continuation'].update(budget_seconds=1),
                   lambda v:v['domains']['observer']['artifacts'].pop(next(iter(v['domains']['observer']['artifacts'])))]:
        bad = deepcopy(second); mutate(bad)
        with pytest.raises(BoundaryError):plan.build_plan(c, continuation=bad)
    latest = install_contract(domains, c, second)
    new = engine(latest['learning']); commit = new.store.commit
    def lost_ack(*args, **kwargs):
        result = commit(*args, **kwargs)
        if json.loads(result.data)['phase'] == 'learn' and calls == [900,901,902,903,904]:
            raise psycopg.OperationalError('second continuation committed acknowledgement lost')
        return result
    monkeypatch.setattr(new.store, 'commit', lost_ack)
    new.run(); engine(latest['learning']).run()
    publish_observations(observer_inputs, engine(latest['learning']), key,
                         approved_until=second['original_approved_until'])
    engine(latest['observer']).run()
    assert calls == list(range(900,906))
    assert all(p.read_bytes()==value for p,value in preserved.items())
    counts = {d:records(v['admin']) for d,v in domains.items()}
    for domain, config in latest.items():
        path=domains[domain]['root']/'chain-replay.json';path.write_text(json.dumps(config));path.chmod(0o600)
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('historical_scenario.py')),str(path),'replay'],
            capture_output=True,text=True,timeout=120,
            env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
        assert result.returncode==0,result.stderr
    assert {d:records(v['admin']) for d,v in domains.items()} == counts
    progress=json.loads((domains['learning']['root']/'learning/status/execution.json').read_text())['payload']['capability_progress']
    assert progress['historical_learned']==6 and progress['continuation']['retained_prefix_count']==4
    assert progress['continuation']['new_committed_count']==2
    print(json.dumps({'scope':'DISPOSABLE_POSTGRES_CHAINED_CONTINUATION','fits':calls,
        'records':counts,'all_prior_bytes_preserved':True,'retained':4,'new_committed':2}))
