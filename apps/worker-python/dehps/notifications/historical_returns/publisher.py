"""Authenticated, read-only source export; no edits to original reports or ledger."""
from pathlib import Path
from hashlib import sha256
import json
from dehps.execution.ledger import MainlineLedger
from dehps.execution.release import canonical
from dehps.notifications.historical_mail.host import config,reader
from dehps.notifications.historical_mail.publisher import gate
from dehps.notifications.p3_top100 import validate_notification_artifact
from dehps.prediction.forward_learning.publisher import append_bytes,signed
from .contract import validate_source,digest,require,utcnow,instant


def publish(inputs,readers,database,key,source_root):
    require(set(readers)=={'original_config'},'one fixed original mail source required')
    cfg,p=config(Path(readers['original_config']));c=inputs.contract
    require(p['plan_digest']==c['original_plan_digest'] and p['release_sha256']==c['original_release_sha256']
            and p['contract_sha256']==digest(c['original_contract']), 'original source binding changed')
    engine,_=reader(cfg,p);manifest=engine.replay(require_complete=False);sources={}
    targets={t['issue'] for t in c['targets']}
    try:
        with engine.store.verification_scope():
            for task in manifest.tasks:
                d=json.loads(task.metric_contract)['notification']
                if d['phase']!='post-replay' or d['issue'] not in targets:continue
                r=engine.store.result(engine.bindings[task.artifact_digest])
                if r is None:continue
                ledger=MainlineLedger(engine.store);ledger.verify(r.task['id']);ctx=ledger.context(r.task['id'])
                sources[d['issue']]={'original':{'artifact':json.loads(r.data),'artifact_sha256':r.artifact.sha256,'task':r.task,'mainline':ctx}}
        with database.connect() as connection:
            connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            for issue,source in sources.items():
                rows=connection.execute("SELECT artifact_digest,artifact_path,task_key FROM research_os_mainline_artifacts WHERE artifact_type='P3Top100IssuePayoutSourceV1' AND task_key LIKE %s",('%'+issue+'-post-return-report',)).fetchall()
                if not rows:continue
                require(len(rows)==1,'ambiguous payout registration')
                identity,relative,task=rows[0];path=Path(source_root)/relative
                require(path.is_relative_to(Path(source_root)) and path.resolve()==path,'payout path escaped')
                raw=path.read_bytes();payout=json.loads(raw);validate_notification_artifact(payout)
                require(payout['artifact_digest']==identity,'registered payout digest differs')
                source['payout']={'artifact':payout,'registered_artifact_digest':identity,'registered_task':task,'file_sha256':sha256(raw).hexdigest()}
                validate_source(source,c,issue)
                body={'contract_sha256':inputs.identity,'issue':issue,'source':source}
                path=inputs.root/'sources'/(issue+'.json')
                if path.exists():require(inputs.source(issue)==source,'original source or payout changed; preserve prior evidence')
                else:append_bytes(path,signed(body,key,c['export_public_key']))
        gate(inputs,key,None)
        return {'status':'VERIFIED','registered_original_issues':sorted(sources)}
    except Exception:
        gate(inputs,key,'SOURCE_INTEGRITY_ERROR');raise
