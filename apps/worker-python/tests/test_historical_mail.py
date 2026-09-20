import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from dehps.execution.context import BoundaryError
from dehps.execution.release import canonical
from dehps.notifications.historical_mail import contract, plan, reports
from dehps.notifications.historical_mail.delivery import Delivery
from dehps.prediction.forward_learning import calculation
from dehps.prediction.forward_learning.publisher import append_bytes, signed


def fixture(root, *, past=False):
    root.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc); local = now.astimezone(__import__('zoneinfo').ZoneInfo('Asia/Shanghai'))
    day = local.replace(hour=17, minute=0, second=0, microsecond=0)
    day += timedelta(days=-1 if past else 1)
    while day.weekday() not in (1, 3, 6):
        day += timedelta(days=-1 if past else 1)
    key = Ed25519PrivateKey.generate()
    c = {'schema': contract.SCHEMA, 'policy': contract.POLICY,
        'historical_contract_sha256': 'b'*64,
        'sources': {d: {'plan_digest': 'c'*64, 'release_sha256': 'd'*64} for d in ('learning', 'observer')},
        'targets': [{'issue': '2026109', 'previous_issue': '2026108', 'send_at': day.isoformat(),
                     'draw_at': (day+timedelta(hours=4, minutes=15)).isoformat()}],
        'recipient_sha256': sha256(b'fixture@example.test').hexdigest(),
        'export_public_key': base64.b64encode(key.public_key().public_bytes_raw()).decode(),
        'approved_until': (now+timedelta(days=14)).isoformat()}
    append_bytes(root/'contract.json', canonical(c)); identity = contract.digest(c)
    from dehps.notifications.historical_mail.publisher import gate
    inputs = contract.Inputs(root, identity); gate(inputs, key, None)
    counts = [sum(n in {(i*7+j)%33+1 for j in range(6)} for i in range(900)) for n in range(1, 34)]
    cp = {'count': 900, 'counts': counts, 'blue_counts': [57]*4+[56]*12,
          'training_end_issue': '2026108', 'last_input_sha256': 'e'*64}
    source = {'contract_sha256': identity, 'target_issue': '2026109', 'observed_at': (now-timedelta(seconds=2)).isoformat(),
        'checkpoint': cp, 'checkpoint_sha256': contract.digest(cp), 'audit_sha256': 'f'*64,
        'source_records': {p: {'artifact_sha256': 'a'*64, 'registration_digest': 'a'*64, 'completed_event_digest': 'a'*64,
                              'committed_at': (now-timedelta(seconds=3)).isoformat()}
                           for p in ('learn', 'report', 'summary', 'observe', 'observe-summary')}}
    if not past:
        append_bytes(root/'checkpoints/2026109.json', signed(source, key, c['export_public_key']))
    else:
        label = {'issue': '2026109', 'red': [1,2,3,4,5,6], 'blue': 1, 'draw_at': c['targets'][0]['draw_at'],
                 'available_at': now.isoformat()}
        receipt = {'schema': 'forward-source-audit.v1', 'completed_at': (now-timedelta(seconds=1)).isoformat(),
                   'observed_at': now.isoformat(), 'rows': [{'issue': label['issue'], 'red': label['red'], 'blue': 1,
                   'draw_date': contract.instant(label['draw_at']).date().isoformat()}]}
        label['audit_sha256'] = contract.digest(receipt)
        append_bytes(root/'labels/2026109.json', signed({'contract_sha256': identity, 'label': label, 'receipt': receipt}, key, c['export_public_key']))
    return c, key, source


def test_plan_separate_and_closed_no_algorithm_change(tmp_path):
    c, _, _ = fixture(tmp_path)
    p = plan.build_plan(c); assert len(p.validate().tasks) == 6
    assert all('historical-mail-' in t.task_key for t in p.validate().tasks)
    c['policy'] = {**c['policy'], 'model': 'something-new'}
    with pytest.raises(BoundaryError):
        plan.build_plan(c)


@pytest.mark.parametrize('change', ['signature', 'counts', 'cutoff', 'after_draw', 'missing_registration'])
def test_checkpoint_rejects_corruption_incomplete_and_leakage(tmp_path, change):
    c, key, value = fixture(tmp_path); target = c['targets'][0]
    p = tmp_path/'checkpoints/2026109.json'
    if change == 'counts':
        value['checkpoint']['counts'][0] += 1; value['checkpoint_sha256'] = contract.digest(value['checkpoint'])
    elif change == 'cutoff':
        value['checkpoint']['training_end_issue'] = target['issue']; value['checkpoint_sha256'] = contract.digest(value['checkpoint'])
    elif change == 'after_draw':
        value['observed_at'] = target['draw_at']
    elif change == 'missing_registration':
        del value['source_records']['summary']
    p.write_bytes(signed(value, key, c['export_public_key']))
    if change == 'signature':
        v = json.loads(p.read_bytes()); v['body']['checkpoint']['count'] += 1; p.write_bytes(canonical(v))
    with pytest.raises(BoundaryError):
        contract.Inputs(tmp_path, contract.digest(c)).snapshot(target)


def test_report_uses_sealed_tickets_no_postdraw_reranking(tmp_path):
    c, _, value = fixture(tmp_path); cp = value['checkpoint']
    q = calculation.probabilities(cp['counts'], cp['count'])['shrink900']
    tickets = calculation.portfolio(q, c['historical_contract_sha256'], '2026109')
    seal = {'issue':'2026109','status':'SEALED_BEFORE_DRAW','training_end_issue':'2026108','count':900,
            'sealed_at':value['observed_at'],'draw_at':c['targets'][0]['draw_at'],'checkpoint_sha256':value['checkpoint_sha256'],'tickets':tickets}
    label = {'issue':'2026109','red':tickets[0]['red'],'blue':tickets[0]['blue'],'audit_sha256':'a'*64}
    pre = reports.report(seal); post = reports.report(seal,label)
    assert post['hits'][0] == {'rank':1,'red_hits':6,'blue_hit':True}
    assert len(post['hits']) == 100 and '未优于均匀基线' in pre['text']
    gap = reports.report({'issue':'2026109','status':'MISSING_PREDRAW_SEAL','tickets':[]}, label)
    assert gap['hits'] == [] and '保留缺口' in gap['text']


def delivery_fixture(root):
    c, key, _ = fixture(root, past=True)
    config = SimpleNamespace(destination='fixture@example.test')
    called = []; mail = SimpleNamespace(send=lambda **kw: (called.append(kw) or SimpleNamespace(message_id='fixture-id')))
    inputs = contract.Inputs(root, contract.digest(c))
    delivery = Delivery(root/'ledger.json', config, c, reauthorize=lambda: None, gate=inputs.gate, mail=mail)
    message = {'kind':'post','issue':'2026109','artifact_sha256':'a'*64,'replay_sha256':'b'*64,'seal_status':'MISSING_PREDRAW_SEAL',
               'report':{'subject':'fixture','text':'fixture','html':'fixture'}}
    return delivery, message, called


def test_delivery_deduplicates_issue_and_refuses_mutated_envelope(tmp_path):
    d, message, called = delivery_fixture(tmp_path)
    assert d.deliver(message)['status'] == 'SENT'
    assert d.deliver(message)['status'] == 'ALREADY_SENT' and len(called) == 1
    with pytest.raises(BoundaryError, match='artifact changed'):
        d.deliver({**message,'artifact_sha256':'c'*64})
    assert len(called) == 1


@pytest.mark.parametrize('failure', ['smtp', 'after_smtp', 'reauthorize', 'source', 'expiry'])
def test_delivery_failure_never_silently_resends(tmp_path, failure):
    d, message, called = delivery_fixture(tmp_path)
    if failure == 'smtp':
        def bad(**kwargs):
            called.append(1); raise OSError('synthetic SMTP ambiguity')
        d.mail = SimpleNamespace(send=bad)
    elif failure == 'after_smtp':
        write = d.write
        def lost(value):
            if next(iter(value['deliveries'].values()))['status'] == 'sent':
                raise OSError('synthetic crash after SMTP before durable success')
            write(value)
        d.write = lost
    elif failure == 'reauthorize':
        d.reauthorize = lambda: (_ for _ in ()).throw(BoundaryError('revoked'))
    elif failure == 'source':
        d.gate = lambda: 'SOURCE_CONFLICT'
    else:
        d.contract = {**d.contract, 'approved_until':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()}
    with pytest.raises((BoundaryError,OSError)):
        d.deliver(message)
    with pytest.raises((BoundaryError,OSError)):
        d.deliver(message)
    assert len(called) <= 1


def test_concurrent_delivery_sends_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    d, message, called = delivery_fixture(tmp_path)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: d.deliver(message), range(2)))
    assert sorted(r['status'] for r in results) == ['ALREADY_SENT','SENT'] and len(called) == 1
