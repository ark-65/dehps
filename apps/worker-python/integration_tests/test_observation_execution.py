from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from dehps.execution.context import BoundaryError
from dehps.execution.release import canonical
from dehps.prediction.observation_plan import build_plan
from dehps.prediction.frozen_p3 import observation
from observation_scenario import coordinator
from test_execution_mainline import mainline, records
from tests.test_prediction_error_learning import inputs, outcome


@pytest.fixture
def observation_config(mainline, inputs):
    config, admin_dsn, authorize = mainline
    directory = Path(config['root']) / 'inputs'
    directory.mkdir(mode=0o700)
    frozen = canonical(asdict(inputs))
    bundle, payout = outcome(inputs)
    opened = canonical(dict(settlement=bundle.settlement, settlement_replay=bundle.settlement_replay,
                            payout=payout, available_at='2026-09-03T22:00:00+08:00'))
    (directory / 'frozen.json').write_bytes(frozen)
    (directory / 'opened.json').write_bytes(opened)
    arguments = dict(issue=inputs.predraw.issue, frozen_sha256=sha256(frozen).hexdigest(),
                     scientific_contract_sha256=inputs.source['artifact_digest'])
    return arguments, sha256(opened).hexdigest(), admin_dsn, authorize


def child(config, mode):
    path = Path(config['root']) / 'observation-config.json'
    path.write_bytes(canonical(config)); path.chmod(0o600)
    worker = Path(__file__).resolve().parents[1]
    return subprocess.run([sys.executable, str(Path(__file__).with_name('observation_scenario.py')), str(path), mode],
                          env={'PATH': os.defpath, 'PYTHONPATH': str(worker), 'PYTHONDONTWRITEBYTECODE': '1'},
                          capture_output=True, text=True, timeout=60)


def test_real_observation_dag_resumes_committed_decision_and_replays_complete_report(observation_config):
    arguments, opened, admin_dsn, authorize = observation_config
    config = authorize(build_plan(**arguments, opened_sha256=opened))
    stopped = child(config, 'before_report')
    assert stopped.returncode == -9, stopped.stderr
    assert records(admin_dsn)['execution_store.commits'] == 1
    time.sleep(1.05)
    resumed = child(config, 'normal')
    assert resumed.returncode == 0, resumed.stderr
    before = records(admin_dsn)
    replay = child(config, 'replay')
    assert replay.returncode == 0, replay.stderr
    assert records(admin_dsn) == before
    assert before['execution_store.commits'] == 2
    assert before['public.research_os_mainline_execution_events'] == 4
    first, last = json.loads(resumed.stdout), json.loads(replay.stdout)
    assert first['manifest'] == last['manifest'] and first['run_id'] != last['run_id']
    assert first['projection_errors'] == last['projection_errors'] == []
    engine = coordinator(config); engine.replay()
    decision_task, report_task = engine.initial.tasks
    assert (Path(config['root']) / (decision_task.task_key + '.calls')).read_bytes() == b'compute\n'
    value = json.loads(engine.store.result(engine.bindings[report_task.artifact_digest]).data)['scientific']
    assert len(value['diagnosis']['all_100_tickets']) == len(value['sample']['body']['original_top100']) == 100
    assert value['new_prediction'] is False
    assert value['status'] == 'OFFLINE_VERIFIED'
    assert value['sample']['body']['training_status'] == 'RECORDED_NOT_INGESTED_BY_NEW_LEARNER'
    assert value['text'] and value['html']


def test_later_opened_report_extends_decision_without_recapture(observation_config):
    arguments, opened, admin_dsn, authorize = observation_config
    initial = build_plan(**arguments)
    config = authorize(initial)
    # Capture does not read the outcome file, even though the test exported it.
    path = Path(config['root']) / 'inputs/opened.json'
    data = path.read_bytes(); path.unlink()
    assert child(config, 'normal').returncode == 0
    path.write_bytes(data)
    extended = build_plan(**arguments, opened_sha256=opened, previous=initial)
    config = authorize(extended)
    completed = child(config, 'normal')
    assert completed.returncode == 0, completed.stderr
    assert child(config, 'replay').returncode == 0
    assert records(admin_dsn)['execution_store.commits'] == 2
    assert records(admin_dsn)['execution_store.attempts'] == 2
    task_key = initial.validate().tasks[0].task_key
    assert (Path(config['root']) / (task_key + '.calls')).read_bytes() == b'compute\n'


def test_modified_input_blocks_committed_read_and_replay_without_rewriting_evidence(observation_config):
    arguments, opened, admin_dsn, authorize = observation_config
    config = authorize(build_plan(**arguments, opened_sha256=opened))
    engine = coordinator(config); engine.run()
    before = records(admin_dsn)
    path = Path(config['root']) / 'inputs/frozen.json'
    original = path.read_bytes()
    path.write_bytes(original + b' ')
    with pytest.raises(BoundaryError, match='input file changed'):
        engine.replay()
    with pytest.raises(BoundaryError, match='input file changed'):
        engine.store.result(next(iter(engine.bindings.values())))
    assert records(admin_dsn) == before
    path.write_bytes(original)
    engine.replay()


def test_resealed_backdate_and_false_prediction_metadata_cannot_be_submitted(observation_config):
    arguments, _, admin_dsn, authorize = observation_config
    config = authorize(build_plan(**arguments))
    engine = coordinator(config); engine.admit()
    task = engine.initial.tasks[0]
    task_id = engine.bindings[task.artifact_digest]
    attempt = engine.store.claim(task_id)
    original = engine.capabilities[task.requested_capability].execute(task, {}, engine.store.artifacts)
    for field, replacement, message in (
        ('recorded_at', '2026-09-03T12:00:00+08:00', 'captured by this execution'),
        ('new_prediction', True, 'metadata differs'),
    ):
        changed = json.loads(original)
        body = changed['scientific']['body']
        body[field] = replacement
        if field == 'recorded_at':
            body['record_mode'] = 'PREDRAW_OBSERVATION'
        changed['scientific'] = observation._seal('decision', body)
        with pytest.raises(BoundaryError, match=message):
            engine.store.prepare(task_id, canonical(changed))
    assert records(admin_dsn)['execution_store.commits'] == 0
    # The untouched current-clock capture still commits and reads successfully.
    engine.store.commit(attempt, engine.store.prepare(task_id, original), register=engine.ledger.register)
    engine.replay()
