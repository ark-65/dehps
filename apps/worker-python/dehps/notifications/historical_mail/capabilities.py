"""Canonical seal/report/replay chain; no training, SMTP or research decisions."""
import json
from dehps.execution.coordinator import Capability
from dehps.execution.ledger import MainlineLedger
from dehps.execution.release import canonical
from dehps.prediction.forward_learning.calculation import probabilities, portfolio
from .contract import Inputs, SCHEMA, digest, instant, require, utcnow
from .plan import build_plan, CAPABILITIES
from .reports import report


def build_capabilities(plan, store, context):
    definitions = {t.artifact_digest: json.loads(t.metric_contract)['notification'] for t in plan.validate().tasks}
    identities = {d['contract_sha256'] for d in definitions.values()}; require(len(identities) == 1, 'one mail contract required')
    inputs = Inputs(context.inputs, identities.pop()); contract = inputs.contract
    require(build_plan(contract).payload == plan.payload, 'notification plan differs')
    targets = {t['issue']: t for t in contract['targets']}; captured = {}

    def parent(parents):
        require(len(parents) == 1, 'one prior phase required')
        value = next(iter(parents.values()))
        return json.loads(value.data)['value'], value.artifact.sha256

    def expected(d, parents, stamp=None):
        phase = d['phase']; target = targets[d['issue']]
        if phase == 'seal':
            require(not parents and stamp is not None, 'seal timestamp required')
            base = {'issue': d['issue'], 'draw_at': target['draw_at'], 'sealed_at': stamp,
                    'model': 'shrink900', 'blue_training': False, 'promotion': False, 'evidence': 'EXPLORATORY_PROSPECTIVE'}
            if instant(stamp) >= instant(target['draw_at']):
                return {**base, 'status': 'MISSING_PREDRAW_SEAL', 'tickets': []}
            source = inputs.snapshot(target); require(source is not None, 'registered checkpoint missing')
            require(instant(source['observed_at']) <= instant(stamp), 'source observed after seal')
            cp = source['checkpoint']; q = probabilities(cp['counts'], cp['count'])['shrink900']
            return {**base, 'status': 'SEALED_BEFORE_DRAW', 'checkpoint_sha256': source['checkpoint_sha256'],
                    'source_snapshot_sha256': digest(source), 'source_records': source['source_records'],
                    'training_end_issue': cp['training_end_issue'], 'count': cp['count'], 'probabilities': q,
                    'tickets': portfolio(q, contract['historical_contract_sha256'], d['issue'])}
        prior, prior_sha = parent(parents)
        if phase == 'pre-report':
            return {'seal': prior, 'seal_sha256': prior_sha, 'report': report(prior)}
        if phase == 'pre-replay':
            return {'status': 'REPLAY_VERIFIED', 'envelope_sha256': prior_sha, **prior}
        if phase == 'result':
            label = inputs.label(target); require(label is not None, 'audited result missing')
            return {'seal': prior['seal'], 'pre_replay_sha256': prior_sha, 'source_sha256': digest(label), 'label': label['label']}
        if phase == 'post-report':
            return {**prior, 'result_sha256': prior_sha, 'report': report(prior['seal'], prior['label'])}
        require(phase == 'post-replay', 'unknown notification phase')
        return {'status': 'REPLAY_VERIFIED', 'envelope_sha256': prior_sha, **prior}

    def ready(task, parents):
        reason = inputs.gate()
        if reason:
            return reason
        d = definitions[task.artifact_digest]; target = targets[d['issue']]
        if d['phase'] == 'seal' and utcnow() < instant(target['draw_at']) and inputs.snapshot(target) is None:
            return 'WAITING_FOR_PREVIOUS_LEARNED_CHECKPOINT'
        if d['phase'] == 'result' and inputs.label(target) is None:
            return 'WAITING_FOR_AUDITED_DRAW'
        return None

    def parents_for(binding):
        output = {}
        for row in MainlineLedger(store).context(binding['id'])['parents']:
            result = store.result(row['task_id']); require(result is not None, 'registered parent missing')
            output[result.task['business_key']] = result
        return output

    def verify(binding, data):
        inputs.read_contract(); value = json.loads(data); d = definitions[binding['task_digest']]
        require(set(value) == {'schema', 'phase', 'issue', 'task_digest', 'release_sha256', 'parents', 'value'}, 'closed mail artifact required')
        require(value['schema'] == binding['artifact_schema'] == SCHEMA and value['phase'] == d['phase']
                and value['issue'] == d['issue'] and value['task_digest'] == binding['task_digest']
                and value['release_sha256'] == binding['release_sha256'] == context.release.digest
                and binding['scientific_contract_sha256'] == inputs.identity, 'mail artifact identity differs')
        parents = parents_for(binding)
        require(value['parents'] == {k: p.artifact.sha256 for k, p in parents.items()}, 'mail parent binding differs')
        stamp = value['value'].get('sealed_at') if d['phase'] == 'seal' else None
        require(value['value'] == expected(d, parents, stamp), 'mail deterministic calculation differs')
        if d['phase'] == 'seal':
            persisted = MainlineLedger(store).context(binding['id'])
            if persisted['commit'] is None:
                require(captured.get(binding['task_digest']) == digest(value), 'seal must be captured by current attempt')
            else:
                commit = instant(persisted['commit']['created_at'])
                require(instant(persisted['attempt']['created_at']) <= instant(stamp) <= commit, 'seal timestamp outside durable attempt')
                if value['value']['status'] == 'SEALED_BEFORE_DRAW':
                    require(commit < instant(targets[d['issue']]['draw_at']), 'seal committed after draw')

    def execute(task, parents, artifacts):
        d = definitions[task.artifact_digest]
        value = {'schema': SCHEMA, 'phase': d['phase'], 'issue': d['issue'], 'task_digest': task.artifact_digest,
            'release_sha256': context.release.digest, 'parents': {k: p.artifact.sha256 for k, p in parents.items()},
            'value': expected(d, parents, utcnow().isoformat())}
        captured[task.artifact_digest] = digest(value)
        return canonical(value)

    def commit_guard(binding, data, server_time):
        require(server_time < instant(contract['approved_until']), 'notification admission expired')
        value = json.loads(data)
        if value['phase'] == 'seal' and value['value']['status'] == 'SEALED_BEFORE_DRAW':
            require(server_time < instant(value['value']['draw_at']), 'seal transaction crossed draw deadline')
        elif value['phase'] == 'seal':
            require(server_time >= instant(value['value']['draw_at']), 'gap transaction preceded draw')
        if value['phase'] in ('result', 'post-report', 'post-replay'):
            require(server_time >= instant(targets[value['issue']]['draw_at']), 'result transaction preceded draw')

    def progress(manifest):
        states = manifest.task_state_by_digest
        completed = [definitions[t.artifact_digest] for t in manifest.tasks if states[t.artifact_digest].declared_status.value == 'completed']
        return {'schema': SCHEMA, 'completed_phases': completed, 'evidence': '证据不足', 'training_performed': False,
                'next_consumer': 'registered replay-gated email delivery', 'approved_until': contract['approved_until']}

    return {name: Capability(name, verify, execute, ready, failure_isolated=True, commit_guard=commit_guard, progress=progress)
            for name in CAPABILITIES.values()}
