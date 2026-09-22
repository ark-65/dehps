"""Canonical supplementary source -> report -> replay; original bytes unchanged."""
import json
from dehps.execution.coordinator import Capability
from dehps.execution.ledger import MainlineLedger
from dehps.execution.release import canonical
from .contract import Inputs,SCHEMA,digest,instant,require,utcnow
from .plan import build_plan,CAPABILITIES
from .reports import report


def build_capabilities(plan,store,context):
    definitions={t.artifact_digest:json.loads(t.metric_contract)['notification'] for t in plan.validate().tasks}
    ids={d['contract_sha256'] for d in definitions.values()};require(len(ids)==1,'one return contract required')
    inputs=Inputs(context.inputs,ids.pop());c=inputs.contract;targets={t['issue']:t for t in c['targets']}
    require(build_plan(c).payload==plan.payload,'return plan differs')
    def expected(d,parents):
        if d['phase']=='source':
            require(not parents,'source has no compute parent');s=inputs.source(d['issue']);require(s is not None,'registered source missing');return s
        require(len(parents)==1,'one registered parent required');p=next(iter(parents.values()));v=json.loads(p.data)['value']
        if d['phase']=='report':return {'source_sha256':p.artifact.sha256,'report':report(v),'seal_status':v['original']['artifact']['value']['seal']['status']}
        require(d['phase']=='replay','unknown return phase');return {**v,'status':'REPLAY_VERIFIED','envelope_sha256':p.artifact.sha256}
    def parents_for(binding):
        output={}
        for row in MainlineLedger(store).context(binding['id'])['parents']:
            r=store.result(row['task_id']);require(r is not None,'registered parent missing');output[r.task['business_key']]=r
        return output
    def verify(binding,data):
        inputs.read_contract();v=json.loads(data);d=definitions[binding['task_digest']]
        require(set(v)=={'schema','phase','issue','task_digest','release_sha256','parents','value'} and v['schema']==SCHEMA==binding['artifact_schema']
                and v['phase']==d['phase'] and v['issue']==d['issue'] and v['task_digest']==binding['task_digest']
                and v['release_sha256']==binding['release_sha256']==context.release.digest and binding['scientific_contract_sha256']==inputs.identity,
                'return artifact identity differs')
        parents=parents_for(binding);require(v['parents']=={k:p.artifact.sha256 for k,p in parents.items()} and v['value']==expected(d,parents),'return replay differs')
    def execute(task,parents,artifacts):
        d=definitions[task.artifact_digest]
        return canonical({'schema':SCHEMA,'phase':d['phase'],'issue':d['issue'],'task_digest':task.artifact_digest,
            'release_sha256':context.release.digest,'parents':{k:p.artifact.sha256 for k,p in parents.items()},'value':expected(d,parents)})
    def ready(task,parents):
        reason=inputs.gate()
        if reason:return reason
        d=definitions[task.artifact_digest]
        if utcnow()<instant(targets[d['issue']]['draw_at']):return 'WAITING_FOR_AUDITED_DRAW'
        if d['phase']=='source' and inputs.source(d['issue']) is None:return 'WAITING_FOR_REGISTERED_POST_REPLAY_AND_PAYOUT'
    def guard(binding,data,server_time):
        d=definitions[binding['task_digest']]
        require(instant(targets[d['issue']]['draw_at'])<=server_time<instant(c['approved_until']),'return commit time outside admission/draw')
    def progress(manifest):
        return {'schema':SCHEMA,'registered_phases':sum(s.declared_status.value=='completed' for s in manifest.task_states),
            'training_performed':False,'next_consumer':'registered enhanced post email','evidence':'证据不足','approved_until':c['approved_until']}
    return {name:Capability(name,verify,execute,ready,failure_isolated=True,commit_guard=guard,progress=progress) for name in CAPABILITIES.values()}
