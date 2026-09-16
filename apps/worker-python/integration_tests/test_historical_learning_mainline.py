from dataclasses import replace
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import psycopg
import pytest

from dehps.prediction.forward_learning import calculation as fixed
from dehps.prediction.historical_learning import contract, plan
from dehps.prediction.historical_learning import capabilities
from dehps.prediction.historical_learning.publisher import publish_observations
from conftest import authority_fixture
from test_execution_mainline import mainline, mainline_fixture, records
from historical_scenario import engine

spec = importlib.util.spec_from_file_location('historical_fixture', Path(__file__).resolve().parents[1]/'tests/test_historical_learning.py')
helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)


@pytest.fixture
def observer_mainline(tmp_path):
    root = tmp_path/'observer'; root.mkdir(mode=0o700)
    with contextmanager(authority_fixture)('observer') as identities:
        yield from mainline_fixture(identities, root)


def test_two_real_updates_lost_ack_report_retry_observer_and_new_process_replay(mainline, observer_mainline, monkeypatch):
    original, admin_dsn, authorize = mainline
    root = Path(original['root'])
    c, rows, key = helper.fixture(root/'inputs')
    config = authorize(plan.build_plan(c))
    fit = fixed.fit_checkpoint; calls = []
    def counted(*args):
        calls.append(1)
        return fit(*args)
    monkeypatch.setattr(fixed, 'fit_checkpoint', counted)
    first = engine(config)
    commit = first.store.commit
    def lost_ack(*args, **kwargs):
        value = commit(*args, **kwargs)
        if len(calls) == 1:
            raise psycopg.OperationalError('synthetic lost acknowledgement AFTER PostgreSQL commit')
        return value
    monkeypatch.setattr(first.store, 'commit', lost_ack)
    def report_failure(*args):
        raise OSError('synthetic independent report rendering failure')
    report_cap = plan.CAPABILITIES['report']
    first.capabilities[report_cap] = replace(first.capabilities[report_cap], execute=report_failure)
    first.run()
    assert len(calls) == 2 and records(admin_dsn)['execution_store.commits'] == 3
    second = engine(config); second.run()
    assert len(calls) == 2 and records(admin_dsn)['execution_store.commits'] == 6
    assert set(second.wait_reasons.values()) == {'WAITING_FOR_NEW_AUDITED_REPORT'}
    before = records(admin_dsn)
    engine(config).run()
    assert records(admin_dsn) == before and len(calls) == 2
    status = root/'learning/status/execution.json'; status_bytes = status.read_bytes(); stamp = status.stat().st_mtime_ns
    path = root/'child.json'; path.write_text(json.dumps(config)); path.chmod(0o600)
    replay = subprocess.run([sys.executable, str(Path(__file__).with_name('historical_scenario.py')), str(path), 'replay'],
        env={**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'}, capture_output=True, text=True, timeout=120)
    assert replay.returncode == 0, replay.stderr
    assert len(json.loads(replay.stdout)['completed']) == 6
    assert records(admin_dsn) == before and status.read_bytes() == status_bytes and status.stat().st_mtime_ns == stamp
    observer_original, observer_admin, observer_authorize = observer_mainline
    observer_root = Path(observer_original['root']); shutil.copytree(root/'inputs', observer_root/'inputs')
    observed = contract.Inputs(observer_root/'inputs', contract.digest(c))
    expiry = (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
    assert len(publish_observations(observed, engine(config), key, approved_until=expiry)) == 3
    assert publish_observations(observed, engine(config), key, approved_until=expiry) == []
    observer_config = observer_authorize(plan.build_plan(c, domain='observer')); observer_config['domain'] = 'observer'
    observer = engine(observer_config); observer.run(); observer.replay(require_complete=False)
    assert records(observer_admin)['execution_store.commits'] == 3
    assert len(calls) == 2 and records(admin_dsn) == before
    for issue in c['issues'][900:]:
        text = (observer_root/'inputs/reports'/f'{issue}.md').read_text()
        assert 'HISTORICAL_RECONSTRUCTION' in text and '完整遗漏诊断' in text and 'REPORT_GAP' in text
        original = (observer_root/'inputs/reports/original'/issue/'index.md').read_text()
        assert 'ORIGINAL_ARCHIVED_EVIDENCE' in original and 'REPORT_GAP' in original
    print(json.dumps({'run_id': second.run_id, 'replay_run_id': json.loads(replay.stdout)['run_id'],
        'observer_run_id': observer.run_id, 'producer_records': before, 'observer_records': records(observer_admin),
        'completed_issues': c['issues'][900:], 'fit_calls': len(calls)}))


def child_args(config):
    path = Path(config['root'])/'child.json'; path.write_text(json.dumps(config)); path.chmod(0o600)
    return [sys.executable, str(Path(__file__).with_name('historical_scenario.py')), str(path)]


def test_real_process_interruption_resumes_committed_checkpoint(mainline):
    original, admin, authorize = mainline
    root = Path(original['root']); c, _, _ = helper.fixture(root/'inputs')
    config = authorize(plan.build_plan(c)); args = child_args(config)
    killed = subprocess.run([*args, 'kill-after-update'], capture_output=True, text=True, timeout=120)
    assert killed.returncode == -9, killed.stderr
    assert records(admin)['execution_store.commits'] == 2
    resumed = subprocess.run([*args, 'run'], capture_output=True, text=True, timeout=120)
    assert resumed.returncode == 0, resumed.stderr
    assert records(admin)['execution_store.commits'] == 6
    assert (root/'fit-calls').read_text().splitlines() == ['900', '901']
    before = records(admin)
    replayed = subprocess.run([*args, 'replay'], capture_output=True, text=True, timeout=120)
    assert replayed.returncode == 0, replayed.stderr
    assert records(admin) == before


def test_real_concurrent_triggers_commit_each_input_once(mainline):
    original, admin, authorize = mainline
    root = Path(original['root']); c, _, _ = helper.fixture(root/'inputs')
    config = authorize(plan.build_plan(c)); args = child_args(config)
    first = subprocess.Popen([*args, 'run'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    second = subprocess.Popen([*args, 'run'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for process in (first, second):
        out, error = process.communicate(timeout=120)
        assert process.returncode == 0, error
    engine(config).run()
    assert records(admin)['execution_store.commits'] == 6
    assert sorted((root/'fit-calls').read_text().splitlines()) == ['900', '901']


def test_revocation_during_learning_rejects_update_but_preserves_readonly_prefix(mainline, authority, monkeypatch):
    original, admin, authorize = mainline
    root = Path(original['root']); c, _, _ = helper.fixture(root/'inputs')
    config = authorize(plan.build_plan(c))
    clients, _, _, _ = authority
    with psycopg.connect(admin) as connection:
        request_id = connection.execute('SELECT request_id FROM execution_authority.executions WHERE id=%s',
            (config['authorization']['execution_id'],)).fetchone()[0]
    fit = fixed.fit_checkpoint
    def revoke_during_fit(*args):
        clients['reviewer'].revoke(request_id)
        return fit(*args)
    monkeypatch.setattr(fixed, 'fit_checkpoint', revoke_during_fit)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        engine(config).run()
    assert records(admin)['execution_store.commits'] == 1
    before = records(admin)
    engine(config).replay(require_complete=False)
    assert records(admin) == before
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        engine(config).run()


def test_real_finite_approval_expires_before_historical_commit(mainline, authority, monkeypatch):
    from dataclasses import asdict
    from dehps.execution.store import ExecutionAuthorization
    original, admin, _ = mainline
    root = Path(original['root']); c, _, _ = helper.fixture(root/'inputs')
    clients, _, _, _ = authority
    packet = plan.build_plan(c); release = 'a'*64
    request = clients['engineer'].request(packet.payload, release)
    content = clients['reviewer'].get(request)['content_sha256']
    expires = datetime.now(timezone.utc)+timedelta(seconds=12)
    clients['reviewer'].approve(request, content, release, expires)
    execution = clients['operator'].begin(request, content, release)
    binding = clients['operator'].database
    config = dict(dsn=binding.dsn, database=binding.database, role=binding.role, root=str(root), plan=packet.payload,
        authorization=asdict(ExecutionAuthorization(execution, content, release)), lease_seconds=300)
    fit = fixed.fit_checkpoint
    def expire_during_fit(*args):
        time.sleep(max(0, (expires-datetime.now(timezone.utc)).total_seconds())+0.1)
        return fit(*args)
    monkeypatch.setattr(fixed, 'fit_checkpoint', expire_during_fit)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        engine(config).run()
    assert records(admin)['execution_store.commits'] == 1
    before = records(admin)
    engine(config).replay(require_complete=False)
    assert records(admin) == before


def test_priority_window_resumes_checkpoint_and_independent_reports(mainline, observer_mainline, monkeypatch):
    original, admin, authorize = mainline
    root = Path(original['root']); c, _, key = helper.fixture(root/'inputs')
    guard = root/'inputs/formal-cgroups/dehps-p3-top100-post-draw-mail.service/cgroup.procs'
    guard.parent.mkdir(); guard.write_text('123\n')  # isolated process-membership fixture
    config = authorize(plan.build_plan(c))
    window = [True]
    active = lambda now=None: window[0]
    monkeypatch.setattr(contract, 'formal_priority_active', active)
    monkeypatch.setattr(capabilities, 'formal_priority_active', active)
    held = engine(config); held.run()
    assert set(held.wait_reasons.values()) == {'FORMAL_TASK_RUNNING'}
    assert records(admin)['execution_store.commits'] == 0

    fit = fixed.fit_checkpoint; calls = []
    def enter_window_during_first_fit(*args):
        calls.append(args[1])
        result = fit(*args)
        if len(calls) == 1:
            window[0] = True  # an in-flight update commits; the next dispatch waits
        return result
    monkeypatch.setattr(fixed, 'fit_checkpoint', enter_window_during_first_fit)
    window[0] = False
    first = engine(config); first.run()
    assert calls == [900] and records(admin)['execution_store.commits'] == 2
    assert set(first.wait_reasons.values()) == {'FORMAL_TASK_RUNNING'}
    prefix = {p.name: p.read_bytes() for p in (root/'learning/artifacts/objects').glob('*.blob')}

    window[0] = False
    resumed = engine(config); resumed.run()
    assert calls == [900, 901] and records(admin)['execution_store.commits'] == 6
    assert all((root/'learning/artifacts/objects'/name).read_bytes() == data for name, data in prefix.items())
    projection = json.loads((root/'learning/status/execution.json').read_bytes())['payload']['capability_progress']
    assert projection['formal_priority_window'] == {'timezone': 'Asia/Shanghai', 'start_inclusive': '18:00:00',
        'end_exclusive': '22:00:00', 'active': False}

    observer_original, observer_admin, observer_authorize = observer_mainline
    observer_root = Path(observer_original['root']); shutil.copytree(root/'inputs', observer_root/'inputs')
    observed = contract.Inputs(observer_root/'inputs', contract.digest(c))
    assert len(publish_observations(observed, engine(config), key,
        approved_until=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())) == 3
    observer_config = observer_authorize(plan.build_plan(c, domain='observer')); observer_config['domain'] = 'observer'
    window[0] = True
    protected = engine(observer_config); protected.run()
    assert records(observer_admin)['execution_store.commits'] == 0
    window[0] = False
    observer = engine(observer_config); observer.run()
    assert records(observer_admin)['execution_store.commits'] == 3
    for issue in c['issues'][900:]:
        assert 'HISTORICAL_RECONSTRUCTION' in (observer_root/'inputs/reports'/f'{issue}.md').read_text()

    replays = {}
    for domain, cfg, database in [('learning', config, admin), ('observer', observer_config, observer_admin)]:
        before = records(database)
        result = subprocess.run([*child_args(cfg), 'replay'], capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stderr
        assert records(database) == before
        replays[domain] = json.loads(result.stdout)['run_id']
    assert calls == [900, 901]
    print(json.dumps({'scope': 'DISPOSABLE_POSTGRES_WINDOW_FIXTURE', 'learning_run_id': resumed.run_id,
        'observer_run_id': observer.run_id, 'replays': replays, 'issues': c['issues'][900:],
        'producer_records': records(admin), 'observer_records': records(observer_admin),
        'prefix_bytes_preserved': True, 'fit_calls': calls}))


def test_outside_window_does_not_renew_committed_batch_budget(mainline, monkeypatch):
    original, admin, authorize = mainline
    root = Path(original['root']); c, _, _ = helper.fixture(root/'inputs')
    config = authorize(plan.build_plan(c))
    monkeypatch.setattr(contract, 'formal_priority_active', lambda now=None: False)
    first = engine(config)
    name = plan.CAPABILITIES['learn']; cap = first.capabilities[name]
    first.capabilities[name] = replace(cap, ready=lambda *args: 'FIXTURE_FREEZE_ONLY')
    first.run()
    before = records(admin)
    assert before['execution_store.commits'] == 1
    class ExpiredBatchClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz)+timedelta(hours=25)
    # Advance only the capability readiness clock; retain the real committed
    # freeze, its deadline, input signatures and PostgreSQL admission unchanged.
    monkeypatch.setattr(capabilities, 'datetime', ExpiredBatchClock)
    current = engine(config); current.run()
    assert set(current.wait_reasons.values()) == {'HISTORICAL_BATCH_BUDGET_EXHAUSTED'}
    assert records(admin) == before


def test_new_release_cannot_relabel_existing_commits(mainline, authority):
    from dataclasses import asdict
    from dehps.execution.store import ExecutionAuthorization
    original, admin, authorize = mainline
    root = Path(original['root']); c, _, _ = helper.fixture(root/'inputs')
    packet = plan.build_plan(c); config = authorize(packet)
    engine(config).run()
    before = records(admin)
    prefix = {p.name: p.read_bytes() for p in (root/'learning/artifacts/objects').glob('*.blob')}
    clients, _, _, _ = authority
    new_release = 'b'*64  # isolated explicit second release, never a production identity
    request = clients['engineer'].request(packet.payload, new_release)
    content = clients['reviewer'].get(request)['content_sha256']
    clients['reviewer'].approve(request, content, new_release, datetime.now(timezone.utc)+timedelta(hours=1))
    execution = clients['operator'].begin(request, content, new_release)
    rebound = {**config, 'authorization': asdict(ExecutionAuthorization(execution, content, new_release))}
    with pytest.raises(psycopg.errors.UniqueViolation, match='business key already bound to another definition'):
        engine(rebound).run()
    engine(config).replay(require_complete=False)
    assert records(admin) == before
    assert all((root/'learning/artifacts/objects'/name).read_bytes() == data for name, data in prefix.items())
