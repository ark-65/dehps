from datetime import datetime, timedelta, timezone
from dataclasses import replace
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import shutil

import psycopg
import pytest

from dehps.execution.context import BoundaryError
from dehps.execution.release import canonical
from dehps.prediction.forward_learning import calculation, contract as contract_module, plan as plan_module
from test_execution_mainline import mainline, mainline_fixture, records
from conftest import authority_fixture
from dehps.prediction.forward_learning.publisher import publish_observation
from forward_scenario import engine

# Load fixture helpers without colliding with this integration module's name.
import importlib.util
spec = importlib.util.spec_from_file_location('forward_fixture', Path(__file__).resolve().parents[1]/'tests/test_forward_learning.py')
helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)


@pytest.fixture
def observer_mainline(tmp_path):
    root = tmp_path/'separate-observer'; root.mkdir(mode=0o700)
    with contextmanager(authority_fixture)('observer') as identities:
        yield from mainline_fixture(identities, root)


def test_real_forward_prefix_wait_update_lost_ack_repeat_and_new_process_replay(mainline, observer_mainline, monkeypatch):
    original, admin_dsn, authorize = mainline
    root = Path(original['root']); inputs = root/'inputs'
    monkeypatch.setattr(contract_module, 'validate_calendar_times', lambda cutoff, draw: None)
    contract, rows, key = helper.fixture(inputs, compact=True)
    now = datetime.now(timezone.utc)
    contract['targets'][0]['deadline'] = (now+timedelta(seconds=18)).isoformat()
    contract['targets'][0]['draw_at'] = (now+timedelta(seconds=20)).isoformat()
    contract['calendar_sha256'] = contract_module.digest(contract['targets'])
    (inputs/'contract.json').write_bytes(canonical(contract))
    config = authorize(plan_module.build_plan(contract))
    calls = []
    fit = calculation.fit_checkpoint
    def counted(*args):
        calls.append(1)
        return fit(*args)
    monkeypatch.setattr(calculation, 'fit_checkpoint', counted)
    first = engine(config)
    commit = first.store.commit
    def lost_ack(*args, **kwargs):
        result = commit(*args, **kwargs)
        if len(calls) == 1:
            raise psycopg.OperationalError('synthetic lost acknowledgment after actual PostgreSQL commit')
        return result
    monkeypatch.setattr(first.store, 'commit', lost_ack)
    manifest = first.run()
    assert len(calls) == 1
    assert records(admin_dsn)['execution_store.commits'] == 1
    assert set(first.wait_reasons.values()) == {'WAITING_FOR_AUDITED_DRAW'}
    engine(config).run()
    assert len(calls) == 1 and records(admin_dsn)['execution_store.attempts'] == 1
    available = datetime.fromisoformat(contract['targets'][0]['draw_at'])+timedelta(milliseconds=100)
    time.sleep(max(0, (available-datetime.now(timezone.utc)).total_seconds()))
    helper.publish(inputs, contract, key, available_at=available.isoformat())
    second = engine(config)
    report_cap = plan_module.CAPABILITIES['report']
    def report_failure(*args):
        raise OSError('synthetic independent report failure')
    second.capabilities[report_cap] = replace(second.capabilities[report_cap], execute=report_failure)
    second.run()
    assert len(second.task_errors) == 1
    assert records(admin_dsn)['execution_store.commits'] == 3
    assert len(calls) == 2  # next seal was not blocked by the report failure
    second = engine(config); second.run()
    assert len(calls) == 2
    assert records(admin_dsn) == {'execution_store.commits': 4, 'execution_store.attempts': 5,
        'public.research_os_mainline_execution_events': 8, 'public.research_os_mainline_artifacts': 4}
    before = records(admin_dsn)
    config_path = root/'fixture-config.json'; config_path.write_text(json.dumps(config)); config_path.chmod(0o600)
    status = root/'learning/status/execution.json'; status_before = status.read_bytes(); mtime = status.stat().st_mtime_ns
    replay = subprocess.run([sys.executable, str(Path(__file__).with_name('forward_scenario.py')), str(config_path), 'replay'],
        env={'PATH': os.defpath, 'PYTHONPATH': str(Path(__file__).resolve().parents[1]), 'PYTHONDONTWRITEBYTECODE': '1'},
        capture_output=True, text=True, timeout=90)
    assert replay.returncode == 0, replay.stderr
    assert len(json.loads(replay.stdout)['completed']) == 4
    assert records(admin_dsn) == before and status.read_bytes() == status_before and status.stat().st_mtime_ns == mtime
    engine(config).run(); assert len(calls) == 2 and records(admin_dsn) == before
    with psycopg.connect(admin_dsn) as admin:
        report = admin.execute("SELECT artifact_path FROM public.research_os_mainline_artifacts WHERE task_key LIKE '%2026001-report'").fetchone()[0]
    readable = json.loads((root/report).read_bytes())['scientific']
    assert readable['score']['status'] == 'SCORED' and len(readable['score']['red_labels']) == 33
    assert readable['next_checkpoint']['issue'] == '2026002'
    assert '完整遗漏过程' in readable['text'] and '证据不足' in readable['text']
    observer_original, observer_admin, observer_authorize = observer_mainline
    observer_root = Path(observer_original['root'])
    shutil.copytree(inputs, observer_root/'inputs')
    observer_config = observer_authorize(plan_module.build_plan(contract, domain='observer'))
    observer_config['domain'] = 'observer'
    observed_inputs = contract_module.Inputs(observer_root/'inputs', contract_module.digest(contract))
    expiry = (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
    assert publish_observation(observed_inputs, engine(config), '2026001', key, approved_until=expiry)
    assert publish_observation(observed_inputs, engine(config), '2026001', key, approved_until=expiry)
    assert records(admin_dsn) == before
    observer = engine(observer_config); observer.run()
    observer.replay(require_complete=False)
    observer_before = records(observer_admin)
    assert observer_before == {'execution_store.commits': 1, 'execution_store.attempts': 1,
        'public.research_os_mainline_execution_events': 2, 'public.research_os_mainline_artifacts': 1}
    engine(observer_config).run()
    assert records(observer_admin) == observer_before and len(calls) == 2
    print(json.dumps({'first_run': first.run_id, 'next_run': second.run_id,
                      'replay_run': json.loads(replay.stdout)['run_id'], 'records': before, 'fitting_calls': len(calls)}))


def test_deadline_crossed_in_real_transaction_rolls_back_and_leaves_explicit_gap(mainline, monkeypatch):
    original, admin_dsn, authorize = mainline
    root = Path(original['root']); inputs = root/'inputs'
    monkeypatch.setattr(contract_module, 'validate_calendar_times', lambda cutoff, draw: None)
    contract, _, _ = helper.fixture(inputs, compact=True)
    cutoff = datetime.now(timezone.utc)+timedelta(seconds=16)
    contract['targets'][0]['deadline'] = cutoff.isoformat()
    contract['targets'][0]['draw_at'] = (cutoff+timedelta(seconds=2)).isoformat()
    contract['calendar_sha256'] = contract_module.digest(contract['targets'])
    (inputs/'contract.json').write_bytes(canonical(contract))
    config = authorize(plan_module.build_plan(contract))
    first = engine(config)
    cap = plan_module.CAPABILITIES['seal']; guard = first.store.commit_guards[cap]
    # Hold the actual transaction after canonical registration until the real
    # deadline passes. No substituted clock, database result or committed row.
    register = first.ledger.register
    def delayed_register(connection, task_id):
        register(connection, task_id)
        connection.execute('SELECT pg_sleep(%s)', (max(0, (cutoff-datetime.now(timezone.utc)).total_seconds())+0.05,))
    monkeypatch.setattr(first.ledger, 'register', delayed_register)
    with pytest.raises(BoundaryError, match='transaction crossed cutoff'):
        first.run()
    assert records(admin_dsn) == {'execution_store.commits': 0, 'execution_store.attempts': 1,
        'public.research_os_mainline_execution_events': 0, 'public.research_os_mainline_artifacts': 0}
    recovered = engine(config); recovered.run()
    task = next(t for t in recovered.initial.tasks if t.task_key.endswith('2026001-seal'))
    result = recovered.store.result(recovered.bindings[task.artifact_digest])
    assert json.loads(result.data)['scientific']['status'] == 'MISSED_SEAL'
    assert not json.loads(result.data)['scientific']['probabilities']


def test_complete_fixed_window_preserves_all_60_gaps_and_consumes_final_analysis(mainline, monkeypatch):
    """Real 181-task DAG, synthetic past inputs; never a retrospective forecast."""
    original, admin_dsn, authorize = mainline
    root = Path(original['root']); inputs = root/'inputs'
    contract, rows, key = helper.fixture(inputs)
    now = datetime.now(timezone.utc)
    for row in rows:
        for field in ('draw_at', 'available_at'):
            row[field] = (datetime.fromisoformat(row[field])-timedelta(days=400)).isoformat()
    contract['created_at'] = (now-timedelta(days=365)).isoformat()
    for index, target in enumerate(contract['targets']):
        cutoff = datetime.fromisoformat(target['deadline'])-timedelta(days=200)
        target['deadline'] = cutoff.isoformat()
        target['draw_at'] = (cutoff+timedelta(hours=4, minutes=15)).isoformat()
    contract['initial_sha256'] = contract_module.digest(rows)
    contract['calendar_sha256'] = contract_module.digest(contract['targets'])
    (inputs/'initial.json').write_bytes(canonical(rows)); (inputs/'contract.json').write_bytes(canonical(contract))
    for index in range(60):
        helper.publish(inputs, contract, key, index)
    def no_retrospective_fitting(*args):
        raise AssertionError('a missing historical seal must not fit a retrospective forecast')
    monkeypatch.setattr(calculation, 'fit_checkpoint', no_retrospective_fitting)
    configured = authorize(plan_module.build_plan(contract))
    live = engine(configured); manifest = live.run()
    assert len(manifest.tasks) == 181
    assert all(manifest.task_state_by_digest[t.artifact_digest].declared_status.value == 'completed' for t in manifest.tasks)
    before = records(admin_dsn)
    assert before['execution_store.commits'] == before['execution_store.attempts'] == 181
    assert before['public.research_os_mainline_execution_events'] == 362
    fresh = engine(configured); fresh.replay()
    assert records(admin_dsn) == before
    with fresh.store.verification_scope():
        task = next(t for t in fresh.initial.tasks if t.task_key.endswith('2026060-report'))
        result = json.loads(fresh.store.result(fresh.bindings[task.artifact_digest]).data)['scientific']
    assert result['window_analysis']['conclusion'] == '证据不足'
    assert len(result['window_analysis']['gaps']) == 60
    assert '固定窗口最终分析' in result['text']


def test_real_source_export_is_readonly_audited_and_freezes_without_replacing(mainline):
    from hashlib import sha256
    from psycopg import sql
    from dehps.draw_sync.audit import DrawDatabaseAuditor
    from dehps.execution.database import DatabaseBinding
    from dehps.prediction.forward_learning.operations import freeze
    from dehps.prediction.forward_learning.publisher import audited_source
    config, admin_dsn, _ = mainline
    root = Path(config['root']); c, rows, key = helper.fixture(root/'fixture-inputs')
    audit = DrawDatabaseAuditor().audit(tuple((r['issue'], tuple(r['red']), r['blue']) for r in rows))
    with psycopg.connect(admin_dsn) as admin:
        admin.execute('CREATE TABLE ssq_history(issue text, draw_date date, red_numbers integer[], blue_number integer)')
        admin.execute('CREATE TABLE draw_issue_events(event_key text, new_issue text, history_fingerprint text, audit_report_hash text)')
        admin.execute('CREATE TABLE draw_sync_runs(event_key text, run_key text, completed_at timestamptz, audit_passed boolean, status text)')
        with admin.cursor() as cur:
            cur.executemany('INSERT INTO ssq_history VALUES (%s,%s,%s,%s)',
                [(r['issue'], datetime.fromisoformat(r['draw_at']).date(), r['red'], r['blue']) for r in rows])
        admin.execute('INSERT INTO draw_issue_events VALUES (%s,%s,%s,%s)', ('fixture-event', rows[-1]['issue'], audit.history_fingerprint, 'a'*64))
        admin.execute("INSERT INTO draw_sync_runs VALUES ('fixture-event','fixture-run',clock_timestamp(),true,'new_issue')")
        admin.execute(sql.SQL('GRANT SELECT ON ssq_history,draw_issue_events,draw_sync_runs TO {}').format(sql.Identifier(config['role'])))
    source = DatabaseBinding(config['dsn'], config['database'], config['role'])
    with source.connect() as connection:
        labels, receipt = audited_source(connection)
        assert len(labels) == 900 and labels[-1]['audit_sha256'] == contract_module.digest(receipt)
        assert connection.execute('SHOW transaction_read_only').fetchone()[0] == 'on'
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            connection.execute("CREATE TABLE prohibited_write(value text)")
    calendar_source = root/'calendar-source.txt'; calendar_source.write_bytes(b'SYNTHETIC TEST CALENDAR; NOT A DEPLOYMENT APPROVAL')
    calendar = {'schema': 'forward-calendar.v1', 'targets': c['targets'],
                'source_sha256': sha256(calendar_source.read_bytes()).hexdigest(), 'source_description': 'synthetic fixture only'}
    calendar_path = root/'calendar.json'; calendar_path.write_bytes(canonical(calendar))
    args = dict(source=source, calendar=calendar_path, calendar_sha256=contract_module.digest(calendar),
                calendar_source=calendar_source, output=root/'frozen', key=key)
    result = freeze(**args)
    assert result['status'] == 'FROZEN_INPUTS_NOT_EXECUTED' and result['initial_count'] == 900
    assert len(contract_module.Inputs(root/'frozen', result['contract_sha256']).initial()) == 900
    before = (root/'frozen/contract.json').read_bytes()
    with pytest.raises(BoundaryError, match='new directory'):
        freeze(**args)
    assert (root/'frozen/contract.json').read_bytes() == before
