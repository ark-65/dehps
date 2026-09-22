"""One separately admitted resend, with the original delivery ledger preserved."""
import json
from pathlib import Path
from dehps.execution.ledger import MainlineLedger
from dehps.notifications.historical_mail.delivery import Delivery as BaseDelivery
from .contract import digest,require


def registered_emails(engine):
    manifest=engine.replay(require_complete=False);out=[]
    with engine.store.verification_scope():
        for t in manifest.tasks:
            d=json.loads(t.metric_contract)['notification']
            if d['phase']!='replay':continue
            r=engine.store.result(engine.bindings[t.artifact_digest])
            if r is None:continue
            MainlineLedger(engine.store).verify(r.task['id']);v=json.loads(r.data)['value']
            require(v['status']=='REPLAY_VERIFIED','enhanced replay missing')
            out.append({'kind':'post','issue':d['issue'],'artifact_sha256':v['envelope_sha256'],
                'replay_sha256':r.artifact.sha256,'seal_status':v['seal_status'],'report':v['report']})
    return out


class Delivery(BaseDelivery):
    def __init__(self,*args,original_ledger,**kwargs):
        super().__init__(*args,**kwargs);self.original_ledger=Path(original_ledger)

    def deliver(self,message):
        require(message['kind']=='post','return consumer only supports post email')
        state=json.loads(self.original_ledger.read_bytes())
        matches=[r for r in state['deliveries'].values() if r['issue']==message['issue'] and r['kind']=='post']
        require(len(matches)<=1,'ambiguous original post delivery')
        resend=self.contract['resend']
        if message['issue']==resend['issue']:
            require(len(matches)==1 and matches[0]['status']=='sent' and digest(matches[0])==resend['original_delivery_sha256'],
                    'exact original sent receipt required for authorized resend')
            message={**message,'report':{**message['report'],'subject':message['report']['subject']+'（补充版·按请求重发）'}}
        else:
            require(not matches,'original post already sent; no additional resend authorized')
        return super().deliver(message)
