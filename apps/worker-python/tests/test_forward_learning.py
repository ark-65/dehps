import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from hashlib import sha256
from zoneinfo import ZoneInfo

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import numpy as np
import pytest

from dehps.execution.context import BoundaryError
from dehps.execution.release import canonical
from dehps.prediction.forward_learning import calculation as compute
from dehps.prediction.forward_learning.contract import (Inputs, POLICY, SCHEMA, digest,
                                                       validate_contract, validate_label)
from dehps.prediction.forward_learning.plan import build_plan
from dehps.prediction.frozen_learning import calculation as retained


def fixture(root, *, compact=False):
    now = datetime.now(timezone.utc)
    key = Ed25519PrivateKey.generate()
    rows = []
    for i in range(900):
        moment = now-timedelta(days=901-i)
        rows.append({'issue': f'2024{i+1:03d}', 'draw_at': moment.isoformat(),
                     'available_at': (moment+timedelta(minutes=5)).isoformat(),
                     'red': sorted({1+(i+j*5) % 33 for j in range(6)}),
                     'blue': 1+i % 16, 'audit_sha256': digest({'fixture_row': i})})
    targets = []
    for i in range(60):
        if compact:
            cutoff = now+timedelta(seconds=6 if i == 0 else 50+i*60)
            draw = cutoff+timedelta(seconds=2)
        else:
            day = now.astimezone(ZoneInfo('Asia/Shanghai'))+timedelta(days=1+i*3)
            cutoff = day.replace(hour=17, minute=0, second=0, microsecond=0)
            draw = cutoff.replace(hour=21, minute=15)
        targets.append({'issue': f'2026{i+1:03d}', 'deadline': cutoff.isoformat(), 'draw_at': draw.isoformat()})
    contract = {'schema': SCHEMA, 'policy': deepcopy(POLICY), 'targets': targets,
                'created_at': now.isoformat(), 'initial_sha256': digest(rows),
                'calendar_sha256': digest(targets),
                'calendar_source_sha256': sha256(b'SYNTHETIC TEST CALENDAR ONLY').hexdigest(),
                'export_public_key': base64.b64encode(key.public_key().public_bytes_raw()).decode()}
    root.mkdir(exist_ok=True)
    (root/'initial.json').write_bytes(canonical(rows)); (root/'contract.json').write_bytes(canonical(contract))
    (root/'calendar-source').write_bytes(b'SYNTHETIC TEST CALENDAR ONLY')
    (root/'opened').mkdir(exist_ok=True)
    return contract, rows, key


def publish(root, contract, key, index=0, *, available_at=None):
    target = contract['targets'][index]
    label = {'issue': target['issue'], 'draw_at': target['draw_at'],
             'available_at': available_at or (datetime.fromisoformat(target['draw_at'])+timedelta(seconds=1)).isoformat(),
             'red': [1, 3, 9, 13, 22, 33], 'blue': 7, 'audit_sha256': 'b'*64}
    body = {'contract_sha256': digest(contract), 'label': label}
    data = {'body': body, 'signature': base64.b64encode(key.sign(canonical(body))).decode()}
    (root/'opened'/f'{target["issue"]}.json').write_bytes(canonical(data))
    return label


def test_fixed_models_match_retained_fitting_and_legal_probabilities(tmp_path):
    _, rows, _ = fixture(tmp_path)
    labels = retained.targets(rows)
    counts = labels.sum(axis=0).tolist()
    actual = compute.fit_checkpoint(counts, len(rows))
    assert actual['shrink900'] == retained.fit(labels, retained.CONFIGS[0])[0].tolist()
    assert actual['old'] == list(map(float, retained.formal.estimate_legal_marginals(counts, training_issue_count=len(rows))))
    assert all(abs(sum(q)-6) < 1e-12 for q in actual.values())
    with pytest.raises(BoundaryError):
        compute.fit_checkpoint(counts, 899)


def test_contract_has_60_targets_no_result_dependent_policy_or_backdated_freeze(tmp_path):
    c, _, _ = fixture(tmp_path)
    validate_contract(c)
    for edit in ('size', 'alpha', 'date', 'extra'):
        bad = deepcopy(c)
        if edit == 'size': bad['targets'].pop()
        if edit == 'alpha': bad['policy']['alpha'] = 1
        if edit == 'date': bad['targets'][0]['deadline'] = c['created_at']
        if edit == 'extra': bad['promote'] = True
        with pytest.raises(BoundaryError): validate_contract(bad)


def test_future_unsigned_wrong_issue_and_replaced_inputs_rejected(tmp_path):
    c, _, key = fixture(tmp_path)
    inputs = Inputs(tmp_path, digest(c)); inputs.initial()
    assert inputs.opened(c['targets'][0], now=datetime.now(timezone.utc)) is None
    label = publish(tmp_path, c, key)
    with pytest.raises(BoundaryError, match='not yet'): inputs.opened(c['targets'][0], now=datetime.now(timezone.utc))
    later = datetime.fromisoformat(label['available_at'])+timedelta(seconds=1)
    assert inputs.opened(c['targets'][0], now=later) == label
    path = tmp_path/'opened'/f'{label["issue"]}.json'
    envelope = json.loads(path.read_text()); envelope['body']['label']['blue'] = 8
    path.write_bytes(canonical(envelope))
    with pytest.raises(BoundaryError, match='signature'): inputs.opened(c['targets'][0], now=later)
    (tmp_path/'initial.json').write_text('[]')
    with pytest.raises(BoundaryError, match='bytes changed'): inputs.initial()


def test_full_positive_and_negative_labels_and_hypothetical_omission(tmp_path):
    c, rows, key = fixture(tmp_path)
    q = compute.fit_checkpoint(retained.targets(rows).sum(axis=0).tolist(), len(rows))
    seal = {'status': 'SEALED_BEFORE_DRAW', 'probabilities': q,
            'tickets': {name: compute.portfolio(q[name], digest(c), c['targets'][0]['issue']) for name in ('old', 'shrink900')}}
    label = publish(tmp_path, c, key)
    result = compute.score(seal, label, digest(c))
    assert len(result['red_labels']) == 33 and sum(result['red_labels']) == 6
    assert len(result['blue_labels']) == 16 and sum(result['blue_labels']) == 1
    for name, metrics in result['probability'].items():
        assert len(metrics['numbers']) == 33
        assert metrics['log_loss'] == retained.loss(np.asarray(result['red_labels']), q[name])
    for diagnostic in result['diagnostics'].values():
        assert len(diagnostic['all_100_tickets']) == 100
        assert sum(diagnostic['number_exposures']) == 600
        assert sum(diagnostic['overlap_histogram'].values()) == 4950
        if diagnostic['first_loss_stage'] == 'NOT_GENERATED':
            assert diagnostic['actual_pool_rank'] is None
            assert diagnostic['hypothetical_insertion_rank'] is not None
    assert result['learnable_cause'] == '证据不足'


def test_gap_does_not_manufacture_forecast_or_block_labels(tmp_path):
    c, _, key = fixture(tmp_path)
    result = compute.score({'status': 'MISSED_SEAL'}, publish(tmp_path, c, key), digest(c))
    assert result['status'] == 'GAP' and not result['probability']
    assert sum(result['red_labels']) == 6


def test_report_failure_not_on_next_seal_dependency_and_observer_no_fit(tmp_path):
    c, _, _ = fixture(tmp_path)
    plan = build_plan(c)
    tasks = plan.validate().tasks
    second_seal = next(t for t in tasks if t.task_key.endswith('2026002-seal'))
    assert len(second_seal.dependencies) == 1
    assert second_seal.dependencies[0].target_key.endswith('2026001-score')
    assert len(tasks) == 181
    observer = build_plan(c, domain='observer')
    assert len(observer.validate().tasks) == 60
    assert all(t.requested_capability.endswith('observe.v1') for t in observer.validate().tasks)


def test_final_analysis_waits_for_exact_window_and_preserves_missingness(tmp_path):
    c, _, _ = fixture(tmp_path)
    scores = [{'issue': target['issue'], 'scientific': {'status': 'GAP'}} for target in c['targets']]
    with pytest.raises(BoundaryError): compute.final_analysis(scores[:-1], c['targets'])
    result = compute.final_analysis(scores, c['targets'])
    assert result['conclusion'] == '证据不足' and len(result['gaps']) == 60
    assert not result['family_intervals'] and not result['promotion']


def test_final_secondary_calibration_uses_all_numbers_and_never_decides_success(tmp_path):
    c, rows, key = fixture(tmp_path)
    q = compute.fit_checkpoint(retained.targets(rows).sum(axis=0).tolist(), len(rows))
    sealed = {'status': 'SEALED_BEFORE_DRAW', 'probabilities': q,
              'tickets': {name: compute.portfolio(q[name], digest(c), c['targets'][0]['issue']) for name in ('old', 'shrink900')}}
    scored = compute.score(sealed, publish(tmp_path, c, key), digest(c))
    result = compute.final_analysis([{'issue': t['issue'], 'scientific': scored} for t in c['targets']], c['targets'])
    for value in result['descriptive'].values():
        assert len(value['calibration_bins']) == 20
        assert sum(b['count'] for b in value['calibration_bins']) == 60*33
        assert value['decision_metric'] is False
    assert set(result['family_intervals']) == {'old', 'uniform'} and not result['promotion']
    final_report = next(t for t in build_plan(c).validate().tasks if t.task_key.endswith('2026060-report'))
    assert any(d.target_key.endswith('2026060-analysis') for d in final_report.dependencies)


def test_publisher_repeated_event_preserves_first_availability_and_rejects_correction(tmp_path, monkeypatch):
    from dehps.prediction.forward_learning import contract as module
    from dehps.prediction.forward_learning.publisher import publish_labels
    monkeypatch.setattr(module, 'validate_calendar_times', lambda cutoff, draw: None)
    c, _, key = fixture(tmp_path)
    now = datetime.now(timezone.utc)
    c['created_at'] = (now-timedelta(days=1)).isoformat()
    c['targets'][0]['deadline'] = (now-timedelta(minutes=2)).isoformat()
    c['targets'][0]['draw_at'] = (now-timedelta(minutes=1)).isoformat()
    c['calendar_sha256'] = digest(c['targets'])
    (tmp_path/'contract.json').write_bytes(canonical(c))
    inputs = Inputs(tmp_path, digest(c))
    receipt = {'synthetic_audit': 'fixture only'}
    label = {'issue': c['targets'][0]['issue'], 'draw_at': c['targets'][0]['draw_at'],
             'available_at': (now-timedelta(seconds=30)).isoformat(), 'red': [1, 3, 9, 13, 22, 33],
             'blue': 7, 'audit_sha256': digest(receipt)}
    expiry = (now+timedelta(hours=1)).isoformat()
    assert publish_labels(inputs, [label], receipt, key, approved_until=expiry) == [label['issue']]
    path = tmp_path/'opened'/f'{label["issue"]}.json'; original = path.read_bytes()
    label['available_at'] = now.isoformat()
    assert publish_labels(inputs, [label], receipt, key, approved_until=expiry) == []
    assert path.read_bytes() == original
    label['blue'] = 8
    with pytest.raises(BoundaryError, match='correction'):
        publish_labels(inputs, [label], receipt, key, approved_until=expiry)
    with pytest.raises(BoundaryError, match='expired'):
        publish_labels(inputs, [label], receipt, key, approved_until=(now-timedelta(seconds=1)).isoformat())


def test_atomic_publication_concurrency_and_conflict(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from dehps.prediction.forward_learning.publisher import append_bytes
    path = tmp_path/'output.json'
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: append_bytes(path, b'fixed artifact'), range(8)))
    assert path.read_bytes() == b'fixed artifact'
    with pytest.raises(BoundaryError, match='conflicts'):
        append_bytes(path, b'changed artifact')
    assert not list(tmp_path.glob('.pending-*'))
