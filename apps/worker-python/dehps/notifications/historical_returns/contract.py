"""An additive presentation contract bound to the original immutable mail plan."""
from pathlib import Path
from dehps.execution.ledger import canonical_records
from dehps.execution.release import canonical
from dehps.notifications.historical_mail.contract import (Inputs as OriginalInputs, validate as validate_original,
    digest, instant, require, utcnow)
from dehps.notifications.historical_mail.reports import report as original_report
from dehps.prediction.historical_learning.contract import sha
from .reports import settle

SCHEMA='historical-learning-returns.v1'
PHASES=('source','report','replay')
POLICY={'tickets':100,'unit_cost_cny':'2.00','multiplier':1,'tax':'not_estimated','prizes':'registered_base_six_tiers',
        'model_changed':False,'training_performed':False,'promotion':False,'conclusion':'证据不足'}


def validate(c):
    require(set(c)=={'schema','policy','original_contract','original_plan_digest','original_release_sha256',
            'recipient_sha256','export_public_key','approved_until','targets','resend'},'closed return contract required')
    require(c['schema']==SCHEMA and c['policy']==POLICY,'return policy differs')
    old=validate_original(c['original_contract'])
    require(c['recipient_sha256']==old['recipient_sha256'] and c['approved_until']==old['approved_until'],
            'recipient or expiry changed')
    require(c['targets'] and c['targets']==[t for t in old['targets'] if t['issue']>=c['targets'][0]['issue']], 'target suffix required')
    sha(c['original_plan_digest']);sha(c['original_release_sha256'])
    require(set(c['resend'])=={'issue','original_delivery_sha256','authorization'}
            and c['resend']['issue']==c['targets'][0]['issue'] and c['resend']['authorization']=='one_user_requested_enhanced_post_resend',
            'one exact enhanced resend required')
    sha(c['resend']['original_delivery_sha256'])
    import base64
    require(len(base64.b64decode(c['export_public_key'],validate=True))==32,'invalid export key')
    return c


def validate_source(source,c,issue):
    require(set(source)=={'original','payout'},'closed return source required')
    o=source['original'];require(set(o)=={'artifact','artifact_sha256','task','mainline'},'closed original source required')
    a=o['artifact'];ctx=o['mainline'];v=a['value']
    require(digest(a)==o['artifact_sha256']==ctx['commit']['artifact_sha256'] and ctx['commit']['artifact_size']==len(canonical(a))
            and ctx['records']==canonical_records(ctx) and ctx['event_count']==2 and ctx['registration_count']==1,
            'original source registration/hash differs')
    require(o['task']==ctx['task'] and a['task_digest']==o['task']['task_digest']
            and a['release_sha256']==o['task']['release_sha256']==c['original_release_sha256']
            and o['task']['scientific_contract_sha256']==digest(c['original_contract'])
            and a['phase']=='post-replay' and a['issue']==issue and v['status']=='REPLAY_VERIFIED', 'wrong original source')
    from dehps.notifications.historical_mail.plan import build_plan as original_plan
    old=original_plan(c['original_contract']);require(old.digest==c['original_plan_digest'],'original plan digest differs')
    specs={t['task_digest']:t for t in old.payload['tasks']}
    definitions={t['digest']:t['value'] for t in old.payload['canonical']['tasks']}
    require(o['task']['spec']==specs.get(a['task_digest']) and ctx['definition']==definitions.get(a['task_digest'])
            and o['task']['business_key'].endswith(issue+'-post-replay'), 'original task definition differs')
    target=next(t for t in c['targets'] if t['issue']==issue);seal=v['seal'];label=v['label']
    require(seal['issue']==label['issue']==issue and instant(seal['draw_at'])==instant(target['draw_at'])
            and v['report']==original_report(seal,label),'original report or draw changed')
    if seal['status']=='SEALED_BEFORE_DRAW':
        require(instant(seal['sealed_at'])<instant(seal['draw_at']) and seal['training_end_issue']==target['previous_issue'],
                'original seal cutoff invalid')
    payout=source['payout'];require(set(payout)=={'artifact','registered_artifact_digest','registered_task','file_sha256'}, 'closed payout reference required')
    require(payout['artifact']['artifact_digest']==payout['registered_artifact_digest']
            and payout['registered_task'].endswith(issue+'-post-return-report'),'wrong registered payout reference')
    sha(payout['file_sha256']);settle(seal,label,payout['artifact'])
    return source


class Inputs(OriginalInputs):
    def __init__(self,root,expected):
        self.root=Path(root);self.identity=sha(expected);self.contract=validate(self.read_contract())

    def source(self,issue):
        body=self.read('sources/'+issue+'.json')
        if body is None:return None
        require(set(body)=={'contract_sha256','issue','source'} and body['contract_sha256']==self.identity and body['issue']==issue,
                'signed source identity differs')
        return validate_source(body['source'],self.contract,issue)
