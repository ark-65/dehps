from copy import deepcopy
from dataclasses import asdict, replace
from decimal import Decimal
from types import SimpleNamespace

import pytest
from dehps.notifications import p3_top100 as original
from dehps.notifications.primary_style import mainline as style
from dehps.notifications.primary_style.render import render
from dehps.notifications.mail import QqMailConfig, MailDeliveryReceipt
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.control_plane import ResearchOSControlPlane
from pydantic import SecretStr
from test_p3_top100_notification import _predraw_bundle, _postdraw_bundle, _raw_payout, RECIPIENT, RECIPIENT_DIGEST


def fixture_source(kind='post'):
    predraw = _predraw_bundle()
    if kind == 'pre':
        report = original.build_pre_envelope(bundle=predraw, recipient_digest=RECIPIENT_DIGEST)
        replay = original.build_pre_replay(envelope=report, expected=report)
    else:
        bundle = _postdraw_bundle()
        payout = original.normalize_payout_record(record=_raw_payout(), bundle=bundle)
        report = original.build_post_report(bundle=bundle, payout=payout, recipient_digest=RECIPIENT_DIGEST)
        replay = original.build_post_replay(report=report, expected=report)
    body = report['body']
    email = original.NotificationEmail(kind, predraw.issue, report['artifact_digest'], replay['artifact_digest'], RECIPIENT_DIGEST,
                                      body['subject'], body['text'], body['html'])
    result = {'email': asdict(email), 'report': report, 'tickets': original._validated_tickets(predraw.model_candidates),
              'checkpoint': predraw.checkpoint, 'candidate_digest': predraw.model_candidates['artifact_digest']}
    if kind == 'post':
        result.update(payout=payout, draw={'red': payout['body']['actual_red_numbers'], 'blue': payout['body']['actual_blue_number']})
    return result


@pytest.mark.parametrize('kind', ['pre', 'post'])
def test_preserves_all_tickets_original_text_identity_and_tax(kind):
    source = fixture_source(kind); before = deepcopy(source)
    result = style.rendered(source); html = result['body']['html']
    assert source == before and result['body']['text'] == source['email']['text']
    assert result['body']['subject'] == source['email']['subject']
    assert '全部100注明细' in html and '<td style="padding:7px;border-bottom:1px solid #ddd">100</td>' in html
    assert render(source) == html
    if kind == 'post':
        assert '开奖号码' in html and '税后净收益' in html
        a = source['report']['body']['accounting']
        assert Decimal(a['estimated_tax_cny']) > 0  # Exercise actual tax-bearing output.
        assert all(v in html for v in a.values())
        assert '税务口径：' in html and '红色为命中号码' in html
    else:
        assert '待开奖' in html and '开奖号码' not in html


def test_html_escapes_registered_strings():
    source = fixture_source(); source['email']['subject'] = source['report']['body']['subject'] = '<script>alert(1)</script>'
    source['checkpoint']['body']['sealed_at'] = '<img onerror="bad">'
    html = render(source)
    assert '<script>' not in html and '<img' not in html and '&lt;script&gt;' in html


@pytest.mark.parametrize('damage', ['duplicate', 'count', 'winner', 'sum', 'seal'])
def test_invalid_or_drifting_source_is_rejected(damage):
    source = fixture_source()
    if damage == 'duplicate': source['tickets'][1] = {**source['tickets'][0], 'rank': 2}
    if damage == 'count': source['tickets'].pop()
    if damage == 'winner': source['report']['body']['winners'][0]['blue_number'] = 16
    if damage == 'sum': source['report']['body']['accounting']['gross_prize_cny'] = '0.00'
    if damage == 'seal': source['checkpoint']['body']['status'] = 'MISSING'
    with pytest.raises(ValueError): render(source)


def test_dag_blocks_replay_until_render_is_committed():
    source = fixture_source(); payload, _ = style.build_additive_task_manifest(live_payload=style.initial(), new_tasks=style.tasks(source))
    manifest = ControlPlaneManifest.from_dict(payload); snapshot = ResearchOSControlPlane().resolve(manifest)
    assert [r.task_key for r in snapshot.ready_queue] == [style.keys(source['email']['issue'], 'post')['render']]


def test_existing_sent_and_uncertain_ledger_prevent_style_resend(tmp_path):
    config = QqMailConfig(address='sender@example.com', recipient=RECIPIENT, authorization_code=SecretStr('test-only'))
    calls = []
    mail = SimpleNamespace(send=lambda **kw: (calls.append(kw), MailDeliveryReceipt('test-message', 'sender@example.com', RECIPIENT))[1])
    ledger = original.P3Top100DeliveryLedger(tmp_path / 'ledger.json')
    delivery = original.P3Top100NotificationDeliveryService(config, ledger=ledger, mail_service=mail)
    source = fixture_source(); old = original.NotificationEmail(**source['email']); styled = replace(old, html=render(source))
    assert old.delivery_key == styled.delivery_key
    delivery.deliver(old); before = ledger.path.read_bytes()
    assert delivery.deliver(styled)['status'] == 'ALREADY_SENT' and len(calls) == 1 and before == ledger.path.read_bytes()
    ledger2 = original.P3Top100DeliveryLedger(tmp_path / 'uncertain.json'); ledger2.begin(old); ledger2.finish(old.delivery_key, status='uncertain', receipt=None)
    with pytest.raises(original.P3Top100DeliveryStateError):
        original.P3Top100NotificationDeliveryService(config, ledger=ledger2, mail_service=mail).deliver(styled)
    assert len(calls) == 1


def test_render_artifact_tampering_is_rejected():
    value = style.rendered(fixture_source()); style.validate(value); value['body']['html'] += 'changed'
    with pytest.raises(ValueError): style.validate(value)


def test_readable_projection_retries_without_overwriting_history(tmp_path):
    source = fixture_source(); email = replace(original.NotificationEmail(**source['email']), html=render(source))
    path = style.publish_readable(tmp_path, email)
    assert style.publish_readable(tmp_path, email) == path
    with pytest.raises(ValueError): style.publish_readable(tmp_path, replace(email, html='drift'))


@pytest.mark.parametrize('retained', [False, True])
def test_relocated_entrypoint_loads_canonical_cli(tmp_path, retained):
    import os
    from pathlib import Path
    import shutil
    import subprocess
    import sys
    worker = Path(__file__).parents[1]
    dependencies = worker
    python = sys.executable
    if retained:
        base = Path('/opt/dehps/releases/retained-p3-r5-alias-f8ec526/legacy')
        if not base.exists():
            pytest.skip('host retained dependency compatibility check')
        dependencies = base / 'ac0ef78/apps/worker-python'
        python = str(base / 'environment/bin/python')
    relocated = tmp_path / 'source/apps/worker-python'
    shutil.copytree(worker / 'dehps/notifications/primary_style', relocated / 'dehps/notifications/primary_style', ignore=shutil.ignore_patterns('__pycache__'))
    entry = relocated / 'scripts/run_primary_p3_presentation.py'; entry.parent.mkdir()
    shutil.copyfile(worker / 'scripts/run_primary_p3_presentation.py', entry)
    assert not (entry.parent / 'run_m4_p3_top100_notification.py').exists()
    bootstrap = '''
import pathlib,runpy,sys
worker,script=sys.argv[1:3]
sys.path[:0]=[worker,str(pathlib.Path(script).parent)]
sys.argv=[script,'--help']
runpy.run_path(script,run_name='__main__')
'''
    env = {**os.environ, 'NUMBA_CACHE_DIR': str(tmp_path / 'numba')}
    result = subprocess.run([python, '-I', '-B', '-c', bootstrap, str(dependencies), str(entry)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert '{pre,post,acceptance,replay}' in result.stdout
