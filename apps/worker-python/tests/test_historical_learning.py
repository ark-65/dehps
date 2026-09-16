from datetime import datetime, timedelta, timezone
from hashlib import sha256
import base64
import copy
import json
import shutil
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dehps.execution.context import BoundaryError
from dehps.execution.release import canonical
from dehps.prediction.forward_learning import calculation as fixed
from dehps.prediction.forward_learning.publisher import append_bytes, signed
from dehps.prediction.historical_learning import calculation, contract, plan


def fixture(root, count=902):
    root.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    # Synthetic compressed history. No production evidence or admission.
    raw = [{'issue': f'{2003001+i:07d}', 'draw_date': (now-timedelta(days=count+2-i)).date().isoformat(),
            'red': sorted({(i*7+n)%33+1 for n in range(6)}), 'blue': i%16+1} for i in range(count)]
    receipt = {'schema': 'forward-source-audit.v1', 'completed_at': (now-timedelta(hours=1)).isoformat(),
               'observed_at': now.isoformat(), 'rows': raw}
    receipt_sha = contract.digest(receipt)
    append_bytes(root/'receipts'/f'{receipt_sha}.json', canonical(receipt))
    history = [{'label': {'issue': r['issue'], 'red': r['red'], 'blue': r['blue'],
                 'draw_at': r['draw_date']+'T21:15:00+08:00', 'available_at': now.isoformat(), 'audit_sha256': receipt_sha},
                'references': []} for r in raw]
    key = Ed25519PrivateKey.generate()
    provenance = {'schema': 'historical-provenance.v1', 'sources': [], 'fixture': True}
    value = {'schema': contract.SCHEMA, 'policy': contract.POLICY, 'created_at': now.isoformat(),
        'history_sha256': contract.digest(history), 'issues': [r['issue'] for r in raw],
        'provenance_sha256': contract.digest(provenance),
        'export_public_key': base64.b64encode(key.public_key().public_bytes_raw()).decode()}
    for name, data in [('contract.json', value), ('history.json', history), ('provenance.json', provenance)]:
        append_bytes(root/name, canonical(data))
    gate = {'contract_sha256': contract.digest(value), 'observed_at': now.isoformat(),
            'approved_until': (now+timedelta(hours=1)).isoformat(), 'reason': None}
    append_bytes(root/'dispatch.json', signed(gate, key, value['export_public_key']))
    (root/'formal-cgroups').mkdir()
    return value, history, key


def test_complete_label_score_before_update_and_unchanged_forward_scoring(tmp_path, monkeypatch):
    c, rows, _ = fixture(tmp_path)
    inputs = contract.Inputs(tmp_path, contract.digest(c))
    before = calculation.initial(rows)
    learned = calculation.update(before, inputs.record(900), contract.digest(c), fitting=True)
    assert before['count'] == 900 and learned['after']['count'] == 901
    assert len(learned['score']['red_labels']) == 33 and sum(learned['score']['red_labels']) == 6
    assert len(learned['score']['blue_labels']) == 16 and sum(learned['score']['blue_labels']) == 1
    assert sum(learned['after']['counts']) == 6*901 and sum(learned['after']['blue_counts']) == 901
    assert learned['original_prediction_status'] == 'REPORT_GAP'
    for name in ('shrink900', 'old'):
        assert len(learned['score']['diagnostics'][name]['all_100_tickets']) == 100
    assert learned['probabilities'] == fixed.probabilities(before['counts'], 900)
    seal = {'status': 'SEALED_BEFORE_DRAW', 'probabilities': learned['probabilities'],
        'tickets': {m: fixed.portfolio(learned['probabilities'][m], contract.digest(c), rows[900]['label']['issue']) for m in ('old', 'shrink900')}}
    forward = fixed.score(seal, rows[900]['label'], contract.digest(c))
    assert {**forward, 'status': 'HISTORICAL_RECONSTRUCTION'} == learned['score']
    seal['status'] = 'MISSED_SEAL'
    assert fixed.score(seal, rows[900]['label'], contract.digest(c))['status'] == 'GAP'
    monkeypatch.setattr(fixed, 'fit_checkpoint', lambda *args: pytest.fail('replay trained'))
    assert calculation.update(before, rows[900], contract.digest(c)) == learned
    with pytest.raises(BoundaryError, match='score-before-update'):
        calculation.update(learned['after'], rows[900], contract.digest(c))


def test_corrupt_incomplete_unopened_and_original_gap_inputs_fail_closed(tmp_path):
    c, rows, _ = fixture(tmp_path)
    inputs = contract.Inputs(tmp_path, contract.digest(c))
    broken = copy.deepcopy(rows[900]); broken['label']['blue'] = None
    with pytest.raises(BoundaryError, match='blue'):
        inputs.validate_record(broken)
    broken = copy.deepcopy(rows[900]); broken['label']['red'][0] = broken['label']['red'][1]
    with pytest.raises(BoundaryError, match='red'):
        inputs.validate_record(broken)
    broken = copy.deepcopy(rows[900]); broken['label']['issue'] = '2026104'
    broken['references'] = [{'kind': 'ORIGINAL_PREDICTION', 'sha256': 'a'*64, 'source': 'fake', 'model': 'old', 'issue': '2026104'}]
    with pytest.raises(BoundaryError, match='2026104'):
        inputs.validate_record(broken)
    path = tmp_path/'receipts'/f"{rows[900]['label']['audit_sha256']}.json"
    path.write_bytes(b'corrupt')
    with pytest.raises(BoundaryError, match='changed'):
        inputs.validate_record(rows[900])


def test_frozen_plan_is_separate_and_incremental_waits_without_invented_issues(tmp_path):
    c, rows, _ = fixture(tmp_path)
    inputs = contract.Inputs(tmp_path, contract.digest(c))
    assert inputs.record(902) is None
    packet = plan.build_plan(c); packet.validate()
    assert len(packet.validate().tasks) == 2*(2+32)+2
    assert any(t.task_key.endswith('slot01-learn') for t in packet.validate().tasks)
    assert not any('forward-learning' in t.requested_capability for t in packet.validate().tasks)
    c['policy'] = {**c['policy'], 'alpha': 100}
    with pytest.raises(BoundaryError, match='policy'):
        plan.build_plan(c)


def test_incremental_order_missing_report_duplicate_and_source_correction(tmp_path):
    from dehps.prediction.historical_learning.publisher import publish_inputs
    c, history, key = fixture(tmp_path)
    inputs = contract.Inputs(tmp_path, contract.digest(c))
    rows = [r['label'] for r in history]
    now = datetime.now(timezone.utc)
    next_row = {**rows[-1], 'issue': '2003903', 'draw_at': (now-timedelta(days=1)).date().isoformat()+'T21:15:00+08:00',
                'available_at': now.isoformat()}
    receipt = {'schema': 'forward-source-audit.v1', 'completed_at': (now-timedelta(hours=1)).isoformat(),
        'observed_at': now.isoformat(), 'rows': [{'issue': r['issue'], 'draw_date': contract.instant(r['draw_at']).date().isoformat(),
        'red': r['red'], 'blue': r['blue']} for r in [*rows, next_row]]}
    next_row['audit_sha256'] = contract.digest(receipt)
    expiry = (now+timedelta(hours=1)).isoformat()
    assert publish_inputs(inputs, [*rows, next_row], receipt, key, approved_until=expiry, references=lambda row: []) == []
    blob = canonical({'fixture_post_report': '2003903'}); identity = sha256(blob).hexdigest()
    append_bytes(tmp_path/'sources'/identity, blob)
    def refs(row):
        return [{'kind': 'POST_DRAW_REPORT', 'sha256': identity, 'source': 'synthetic registered report fixture',
                 'model': 'fixture', 'issue': row['issue']}]
    assert publish_inputs(inputs, [*rows, next_row], receipt, key, approved_until=expiry, references=refs) == ['2003903']
    path = tmp_path/'incremental/00902.json'; original = path.read_bytes()
    assert inputs.record(902)['label'] == next_row and inputs.record(903) is None
    assert publish_inputs(inputs, [*rows, next_row], receipt, key, approved_until=expiry, references=refs) == []
    assert path.read_bytes() == original
    corrected = copy.deepcopy([*rows, next_row]); corrected[1]['blue'] = corrected[1]['blue']%16+1
    with pytest.raises(BoundaryError, match='correction conflicts'):
        publish_inputs(inputs, corrected, receipt, key, approved_until=expiry, references=refs)
    assert path.read_bytes() == original
    with pytest.raises(BoundaryError, match='authorization expired'):
        publish_inputs(inputs, rows, receipt, key, approved_until=(now-timedelta(seconds=1)).isoformat(), references=refs)


def test_dispatch_gate_checks_formal_process_membership_before_each_task(tmp_path, monkeypatch):
    monkeypatch.setattr(contract, 'formal_priority_active', lambda now=None: True)
    c, _, _ = fixture(tmp_path)
    inputs = contract.Inputs(tmp_path, contract.digest(c))
    assert inputs.gate() is None
    path = tmp_path/'formal-cgroups/dehps-forward-prequential-successor.service/cgroup.procs'
    path.parent.mkdir(); path.write_text('123\n')
    assert inputs.gate() == 'FORMAL_TASK_RUNNING'
    path.write_text('')
    assert inputs.gate() is None


@pytest.mark.parametrize(('utc', 'active'), [
    ('2026-09-16T09:59:59.999999+00:00', False),
    ('2026-09-16T10:00:00+00:00', True),
    ('2026-09-16T13:59:59.999999+00:00', True),
    ('2026-09-16T14:00:00+00:00', False),
    ('2026-09-16T15:59:59+00:00', False),
    ('2026-09-16T16:00:00+00:00', False),
])
@pytest.mark.parametrize('host_timezone', ['UTC', 'America/New_York'])
def test_formal_priority_boundaries_use_shanghai_not_host_timezone(monkeypatch, utc, active, host_timezone):
    try:
        with monkeypatch.context() as patch:
            patch.setenv('TZ', host_timezone)
            time.tzset()
            assert contract.formal_priority_active(datetime.fromisoformat(utc)) is active
    finally:
        time.tzset()


@pytest.mark.parametrize('guard', ['busy', 'idle', 'missing'])
def test_formal_guard_crosses_both_window_boundaries_without_restart(tmp_path, guard):
    c, _, _ = fixture(tmp_path)
    inputs = contract.Inputs(tmp_path, contract.digest(c))
    if guard == 'missing':
        (tmp_path/'formal-cgroups').rmdir()
    else:
        path = tmp_path/'formal-cgroups/dehps-p3-top100-post-draw-mail.service/cgroup.procs'
        path.parent.mkdir(); path.write_text('123\n' if guard == 'busy' else '')
    protected_reason = {'busy': 'FORMAL_TASK_RUNNING', 'idle': None,
                        'missing': 'MISSING_FORMAL_DISPATCH_GUARD'}[guard]
    for local, expected in [('17:59:59', None), ('18:00:00', protected_reason),
                            ('21:59:59', protected_reason), ('22:00:00', None)]:
        assert inputs.formal_guard(now=datetime.fromisoformat('2026-09-16T'+local+'+08:00')) == expected


@pytest.mark.parametrize('active', [False, True])
@pytest.mark.parametrize('reason', [None, 'FORMAL_TASK_RUNNING', 'SOURCE_CONFLICT', 'SOURCE_UNREADABLE'])
def test_dispatch_hint_waives_only_formal_deferral(tmp_path, monkeypatch, active, reason):
    c, _, key = fixture(tmp_path)
    inputs = contract.Inputs(tmp_path, contract.digest(c))
    monkeypatch.setattr(contract, 'formal_priority_active', lambda now=None: active)
    path = tmp_path/'dispatch.json'; body = json.loads(path.read_bytes())['body']
    body['reason'] = reason
    path.write_bytes(signed(body, key, c['export_public_key']))
    expected = None if reason == 'FORMAL_TASK_RUNNING' and not active else reason
    assert inputs.gate() == expected


@pytest.mark.parametrize(('failure', 'expected'), [
    ('missing', 'WAITING_FOR_SOURCE_CHECK'), ('stale', 'WAITING_FOR_SOURCE_CHECK'),
    ('expired', 'AUTHORIZATION_REQUIRED'),
])
def test_outside_priority_window_keeps_source_freshness_and_authorization(tmp_path, monkeypatch, failure, expected):
    c, _, key = fixture(tmp_path)
    monkeypatch.setattr(contract, 'formal_priority_active', lambda now=None: False)
    inputs = contract.Inputs(tmp_path, contract.digest(c))
    path = tmp_path/'dispatch.json'; body = json.loads(path.read_bytes())['body']
    body['reason'] = 'FORMAL_TASK_RUNNING'
    if failure == 'missing':
        path.unlink()
    else:
        name, seconds = ('observed_at', 1201) if failure == 'stale' else ('approved_until', 1)
        body[name] = (datetime.now(timezone.utc)-timedelta(seconds=seconds)).isoformat()
        path.write_bytes(signed(body, key, c['export_public_key']))
    assert inputs.gate() == expected


def test_outside_priority_window_still_verifies_signed_dispatch(tmp_path, monkeypatch):
    c, _, _ = fixture(tmp_path)
    monkeypatch.setattr(contract, 'formal_priority_active', lambda now=None: False)
    inputs = contract.Inputs(tmp_path, contract.digest(c))
    path = tmp_path/'dispatch.json'; envelope = json.loads(path.read_bytes())
    envelope['body']['reason'] = 'FORMAL_TASK_RUNNING'
    path.write_bytes(canonical(envelope))
    with pytest.raises(BoundaryError, match='signature invalid'):
        inputs.gate()


def test_damaged_frozen_source_is_retained_as_error_and_signed_stop_in_both_domains(tmp_path):
    from dehps.prediction.historical_learning.operations import publish
    learning = tmp_path/'learning'; observer = tmp_path/'observer'
    c, rows, key = fixture(learning); shutil.copytree(learning, observer)
    key_file = tmp_path/'key.json'
    key_file.write_bytes(canonical({'ed25519_private_key': base64.b64encode(key.private_bytes_raw()).decode()})); key_file.chmod(0o600)
    now = datetime.now(timezone.utc)
    config = {'schema': 'historical-publisher.v1', 'activated_at': now.isoformat(),
        'approved_until': (now+timedelta(hours=1)).isoformat(), 'key_file': str(key_file),
        'contract_sha256': contract.digest(c), 'learning_inputs': str(learning), 'observer_inputs': str(observer),
        'source_credentials': str(tmp_path/'unused-private-source.json'), 'source_root': str(tmp_path/'unused-source'), 'producer_reader': {}}
    (learning/'receipts'/f"{rows[0]['label']['audit_sha256']}.json").write_bytes(b'corrupt')
    with pytest.raises(BoundaryError, match='changed'):
        publish(config)
    assert len(list((learning/'errors').glob('*.json'))) == len(list((observer/'errors').glob('*.json'))) == 1
    assert contract.Inputs(observer, contract.digest(c)).gate() == 'SOURCE_CONFLICT'
    assert not (observer/'incremental').exists()


def test_signed_complete_but_unopened_incremental_input_cannot_be_scored(tmp_path):
    c, history, key = fixture(tmp_path)
    now = datetime.now(timezone.utc)
    row = {**history[-1]['label'], 'issue': '2003903',
        'draw_at': (now+timedelta(days=1)).isoformat(), 'available_at': (now+timedelta(days=1,hours=1)).isoformat()}
    receipt = {'schema': 'forward-source-audit.v1', 'completed_at': now.isoformat(), 'observed_at': now.isoformat(),
        'rows': [{'issue': r['issue'], 'red': r['red'], 'blue': r['blue'], 'draw_date': contract.instant(r['draw_at']).date().isoformat()}
                 for r in [*[item['label'] for item in history], row]]}
    row['audit_sha256'] = contract.digest(receipt)
    append_bytes(tmp_path/'receipts'/f'{contract.digest(receipt)}.json', canonical(receipt))
    body = {'contract_sha256': contract.digest(c), 'index': 902, 'previous_sha256': contract.digest(history[-1]),
            'record': {'label': row, 'references': []}}
    append_bytes(tmp_path/'incremental/00902.json', signed(body, key, c['export_public_key']))
    with pytest.raises(BoundaryError, match='not yet available'):
        contract.Inputs(tmp_path, contract.digest(c)).record(902)
