from copy import deepcopy
from decimal import Decimal
from itertools import combinations
from types import SimpleNamespace
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from dehps.execution.context import BoundaryError
from dehps.notifications.historical_returns.contract import Inputs,digest,validate_source
from dehps.notifications.historical_returns.reports import settle,report,money
from dehps.notifications.historical_returns.delivery import Delivery
from dehps.notifications.p3_top100 import prize_tier,P3Top100NotificationError
from historical_returns_fixtures import fixture


@pytest.mark.parametrize('red,blue,tier',[(0,False,0),(1,False,0),(2,False,0),(3,False,0),(4,False,5),(5,False,4),(6,False,2),(0,True,6),(1,True,6),(2,True,6),(3,True,5),(4,True,4),(5,True,3),(6,True,1)])
def test_all_legal_hit_classes_use_one_highest_prize(red,blue,tier):
    assert prize_tier(red_hits=red,blue_hit=blue)==tier


def test_full_accounting_one_each_class_and_prominent_html(tmp_path):
    c,_,s,_=fixture(tmp_path);v=s['original']['artifact']['value'];tickets=[]
    for h in range(7):
        for b in (2,1):tickets.append({'rank':len(tickets)+1,'red':list(range(1,h+1))+list(range(7,13-h)),'blue':b})
    for nums in combinations(range(7,34),6):
        t={'rank':len(tickets)+1,'red':list(nums),'blue':3};tickets.append(t)
        if len(tickets)==100:break
    v['seal']['tickets']=tickets;r=report(s);a=r['settlement']
    assert a['cost_cny']=='200.00' and a['gross_cny']=='5103435.00' and a['net_cny']=='5103235.00' and a['winning_tickets']==10
    assert sum(a['tier_counts'].values())==100 and sum(Decimal(t['gross_cny']) for t in a['tickets'])==Decimal(a['gross_cny'])
    assert '开奖号码' in r['text'].splitlines()[2] and '<table' in r['html'] and '未优于均匀基线' in r['html']


@pytest.mark.parametrize('change',['signature','artifact','registration','cutoff','payout_issue','payout_amount','duplicate'])
def test_corrupt_sources_fail_closed(tmp_path,change):
    c,_,s,_=fixture(tmp_path);root=Inputs(tmp_path,digest(c));root.source(c['targets'][0]['issue'])
    if change=='signature':
        path=next((tmp_path/'sources').glob('*.json'));v=json.loads(path.read_bytes());v['signature']='AA==';path.write_text(json.dumps(v))
        with pytest.raises(BoundaryError):root.source(c['targets'][0]['issue'])
        return
    if change=='artifact':s['original']['artifact_sha256']='a'*64
    elif change=='registration':s['original']['mainline']['registration_count']=0
    elif change=='cutoff':s['original']['artifact']['value']['seal']['training_end_issue']=c['targets'][0]['issue']
    elif change=='payout_issue':s['payout']['artifact']['body']['issue']='2026110'
    elif change=='payout_amount':s['payout']['artifact']['body']['tiers'][0]['single_ticket_gross_cny']='nan'
    else:s['original']['artifact']['value']['seal']['tickets'][1]=s['original']['artifact']['value']['seal']['tickets'][0]
    with pytest.raises((ValueError,BoundaryError,P3Top100NotificationError)):validate_source(s,c,c['targets'][0]['issue'])


def test_gap_no_cost_or_fictional_profit(tmp_path):
    c,_,s,_=fixture(tmp_path,gap=True);validate_source(s,c,c['targets'][0]['issue']);r=report(s)
    assert r['settlement']['cost_cny'] is None and r['settlement']['net_cny'] is None and '开奖号码' in r['text']


@pytest.mark.parametrize('v',['NaN','Infinity','-1','0.001'])
def test_money_rejects_invalid_nonfinite_and_fractional_cents(v):
    with pytest.raises((ValueError,BoundaryError)):money(v)


def test_resend_idempotent_concurrent_and_preserves_old_ledger(tmp_path):
    c,_,s,sent=fixture(tmp_path);old=tmp_path/'old-ledger.json';old.write_text(json.dumps({'deliveries':{'old':sent}}));before=old.read_bytes();calls=[]
    d=Delivery(tmp_path/'new-ledger.json',SimpleNamespace(destination='fixture@example.test'),c,reauthorize=lambda:None,gate=lambda:None,
        original_ledger=old,mail=SimpleNamespace(send=lambda **kw:(calls.append(kw) or SimpleNamespace(message_id='fake-only'))))
    msg={'kind':'post','issue':sent['issue'],'artifact_sha256':'a'*64,'replay_sha256':'b'*64,'seal_status':'SEALED_BEFORE_DRAW','report':report(s)}
    with ThreadPoolExecutor(2) as pool:out=list(pool.map(lambda _:d.deliver(msg),range(2)))
    assert sorted(v['status'] for v in out)==['ALREADY_SENT','SENT'] and len(calls)==1 and old.read_bytes()==before
    assert '按请求重发' in calls[0]['subject']
    with pytest.raises(BoundaryError):d.deliver({**msg,'artifact_sha256':'d'*64})


def test_uncertain_smtp_never_resends_and_original_receipt_must_match(tmp_path):
    c,_,s,sent=fixture(tmp_path);old=tmp_path/'old-ledger.json';old.write_text(json.dumps({'deliveries':{'old':sent}}));calls=[]
    def fail(**kw):calls.append(1);raise OSError('synthetic uncertain transport')
    d=Delivery(tmp_path/'new-ledger.json',SimpleNamespace(destination='fixture@example.test'),c,reauthorize=lambda:None,gate=lambda:None,original_ledger=old,mail=SimpleNamespace(send=fail))
    msg={'kind':'post','issue':sent['issue'],'artifact_sha256':'a'*64,'replay_sha256':'b'*64,'seal_status':'SEALED_BEFORE_DRAW','report':report(s)}
    with pytest.raises(OSError):d.deliver(msg)
    with pytest.raises(BoundaryError):d.deliver(msg)
    assert calls==[1]
    sent['status']='uncertain';old.write_text(json.dumps({'deliveries':{'old':sent}}))
    with pytest.raises(BoundaryError):d.deliver(msg)


@pytest.mark.parametrize('mode',['missing_floating','wrong_draw','extra_tier','fixed_change','duplicate_ticket'])
def test_arithmetic_rejects_semantically_invalid_but_digest_valid_source(tmp_path,mode):
    from dehps.notifications.p3_top100 import _artifact
    _,_,s,_=fixture(tmp_path);v=s['original']['artifact']['value'];p=s['payout']['artifact'];body=deepcopy(p['body'])
    if mode=='missing_floating':
        v['seal']['tickets'][0]={'rank':1,'red':v['label']['red'],'blue':v['label']['blue']};body['tiers'][0]['single_ticket_gross_cny']='0.00'
    elif mode=='wrong_draw':body['actual_blue_number']=2
    elif mode=='extra_tier':body['tiers'].append({'tier':7,'single_ticket_gross_cny':'5.00'})
    elif mode=='fixed_change':body['tiers'][5]['single_ticket_gross_cny']='10.00'
    else:v['seal']['tickets'][1]={**v['seal']['tickets'][0],'rank':2}
    p=_artifact(artifact_type=p['artifact_type'],body=body,parent_digests=p['parent_digests'])
    with pytest.raises(BoundaryError):settle(v['seal'],v['label'],p)
