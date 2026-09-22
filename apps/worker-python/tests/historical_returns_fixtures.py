"""Synthetic upstream fixture, including signed canonical registration receipts."""
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from uuid import uuid4
import base64,json
from dehps.execution.ledger import canonical_records
from dehps.execution.release import canonical
from dehps.notifications.historical_mail.plan import build_plan
from dehps.notifications.historical_mail.reports import report as old_report
from dehps.notifications.p3_top100 import _artifact,PAYOUT_SOURCE_ARTIFACT_TYPE
from dehps.notifications.historical_returns.contract import POLICY,SCHEMA,Inputs,digest
from dehps.notifications.historical_mail.publisher import gate
from dehps.prediction.forward_learning.publisher import signed,append_bytes
from dehps.prediction.forward_learning.calculation import portfolio,probabilities
from test_historical_mail import fixture as old_fixture


def fixture(root,gap=False):
    old,key,checkpoint=old_fixture(root/'old',past=True);target=old['targets'][0];issue=target['issue'];now=datetime.now(timezone.utc)
    cp=checkpoint['checkpoint'];seal={'issue':issue,'status':'SEALED_BEFORE_DRAW','training_end_issue':target['previous_issue'],'count':900,
        'sealed_at':(datetime.fromisoformat(target['draw_at'])-timedelta(hours=1)).isoformat(),'draw_at':target['draw_at'],
        'checkpoint_sha256':digest(cp),'tickets':portfolio(probabilities(cp['counts'],900)['shrink900'],old['historical_contract_sha256'],issue)}
    if gap:seal.update(status='MISSING_PREDRAW_SEAL',tickets=[])
    label={'issue':issue,'red':[1,2,3,4,5,6],'blue':1,'audit_sha256':'e'*64}
    prior=build_plan(old);t=prior.payload['tasks'][-1];definition=prior.payload['canonical']['tasks'][-1]['value'];task={'id':7,'spec':t,**t,'release_sha256':'b'*64,'control_plane':'observer'}
    artifact={'schema':old['schema'],'phase':'post-replay','issue':issue,'task_digest':t['task_digest'],'release_sha256':'b'*64,'parents':{},
        'value':{'seal':seal,'label':label,'report':old_report(seal,label),'status':'REPLAY_VERIFIED','envelope_sha256':'c'*64}}
    attempt={'id':str(uuid4()),'created_at':now.isoformat()}
    ctx={'task':task,'commit':{'artifact_sha256':digest(artifact),'artifact_size':len(canonical(artifact)),'created_at':now.isoformat()},
        'attempt':attempt,'definition':definition,'parents':[],'event_count':2,'registration_count':1};ctx['records']=canonical_records(ctx)
    original={'artifact':artifact,'artifact_sha256':digest(artifact),'task':task,'mainline':ctx}
    p=_artifact(artifact_type=PAYOUT_SOURCE_ARTIFACT_TYPE,body={'issue':issue,'status':'EXACT_ISSUE_PAYOUT_VALIDATED','actual_red_numbers':label['red'],'actual_blue_number':1,
        'source_url':'https://example.test/fixture','tiers':[{'tier':n,'single_ticket_gross_cny':str(v),'official_award_count':1} for n,v in enumerate([5000000,100000,3000,200,10,5],1)]},parent_digests=('d'*64,))
    payout={'artifact':p,'registered_artifact_digest':p['artifact_digest'],'registered_task':'m4-p3-top100-notification-v3-'+issue+'-post-return-report','file_sha256':sha256(canonical(p)).hexdigest()}
    sent={'issue':issue,'kind':'post','status':'sent','artifact_sha256':'c'*64,'replay_sha256':digest(artifact),'recipient_sha256':old['recipient_sha256']}
    c={'schema':SCHEMA,'policy':POLICY,'original_contract':old,'original_plan_digest':prior.digest,'original_release_sha256':'b'*64,
       'recipient_sha256':old['recipient_sha256'],'export_public_key':base64.b64encode(key.public_key().public_bytes_raw()).decode(),
       'approved_until':old['approved_until'],'targets':old['targets'],'resend':{'issue':issue,'original_delivery_sha256':digest(sent),'authorization':'one_user_requested_enhanced_post_resend'}}
    source={'original':original,'payout':payout};append_bytes(root/'contract.json',canonical(c));inputs=Inputs(root,digest(c));gate(inputs,key,None)
    append_bytes(root/'sources'/(issue+'.json'),signed({'contract_sha256':inputs.identity,'issue':issue,'source':source},key,c['export_public_key']))
    return c,key,source,sent
