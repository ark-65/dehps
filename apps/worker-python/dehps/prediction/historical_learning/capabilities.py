"""Per-issue atomic updates through the singular canonical executor."""
from datetime import datetime, timedelta, timezone
import json

from dehps.execution.coordinator import Capability
from dehps.execution.ledger import MainlineLedger
from dehps.execution.release import canonical
from . import calculation as compute
from .contract import Inputs, POLICY, SCHEMA, digest, instant, require
from .plan import CAPABILITIES, build_plan
from .report import report, summary_text


def build_capabilities(plan, store, context):
    tasks = {t.artifact_digest: t for t in plan.validate().tasks}
    definitions = {k: json.loads(t.metric_contract)['historical'] for k, t in tasks.items()}
    hashes = {v['contract_sha256'] for v in definitions.values()}
    require(len(hashes) == 1, 'one historical contract required')
    inputs = Inputs(context.inputs, hashes.pop())
    domain = store.artifacts.context.control_plane
    require(build_plan(inputs.contract, domain=domain).payload == plan.payload, 'historical plan differs from frozen definition')
    captured = {}

    def values(parents):
        return [json.loads(p.data) for p in parents.values()]

    def predecessor(parents):
        records = [v for v in values(parents) if v['phase'] in {'freeze', 'learn'}]
        require(len(records) == 1, 'one committed checkpoint predecessor required')
        return records[0]['scientific']

    def expected(definition, parents, *, started_at=None, fitting=False):
        phase, index = definition['phase'], definition['index']
        if phase == 'freeze':
            require(not parents, 'freeze cannot have parents')
            return {'after': compute.initial(inputs.history), 'history_sha256': inputs.contract['history_sha256'],
                'batch_count': len(inputs.history)-900, 'started_at': started_at,
                'batch_deadline': (instant(started_at)+timedelta(seconds=POLICY['batch_budget_seconds'])).isoformat()}
        if phase == 'learn':
            previous = predecessor(parents)
            record = inputs.record(index)
            require(record is not None, 'missing audited input')
            require(previous['after']['count'] == index, 'checkpoint/sample index differs')
            value = compute.update(previous['after'], record, inputs.contract_sha256, fitting=fitting)
            return {**value, 'batch_deadline': previous['batch_deadline']}
        if phase == 'report':
            require(len(parents) == 1, 'report needs one committed update')
            result = next(iter(parents.values()))
            value = json.loads(result.data)
            require(value['phase'] == 'learn' and value['index'] == index, 'report update binding differs')
            return report(value['scientific'], result.artifact.sha256)
        if phase == 'summary':
            records = sorted(values(parents), key=lambda r: r['index'])
            require([r['index'] for r in records] == list(range(900, len(inputs.history)))
                    and all(r['phase'] == 'report' for r in records), 'batch summary needs every registered historical report')
            summary = compute.summarize([r['scientific'] for r in records])
            return {'summary': summary, 'text': summary_text(summary), 'external_delivery': False}
        bundle = inputs.observation(index)
        require(bundle is not None and set(bundle) == {'contract_sha256', 'index', 'report', 'learn',
            'report_sha256', 'learn_sha256', 'producer_committed_at', 'producer_execution_id', 'producer_release_sha256', 'producer_plan_digest'},
            'closed registered observation bundle required')
        require(bundle['index'] == index and instant(bundle['producer_committed_at']) <= datetime.now(timezone.utc), 'observer identity/time differs')
        for name in ('report', 'learn'):
            if bundle[name] is not None:
                require(digest(bundle[name]) == bundle[name+'_sha256'], 'producer artifact hash differs')
                require(bundle[name]['release_sha256'] == bundle['producer_release_sha256'], 'producer release differs')
        if phase == 'observe-summary':
            require(bundle['learn'] is None, 'summary must not fit a model')
            records = sorted(values(parents), key=lambda r: r['index'])
            require([r['index'] for r in records] == list(range(900, len(inputs.history))), 'independent summary missing reports')
            expected_summary = compute.summarize([r['scientific']['report'] for r in records])
            require(bundle['report']['scientific']['summary'] == expected_summary, 'independent batch summary differs')
            output = bundle['report']['scientific']
        else:
            learn = bundle['learn']
            require(learn['phase'] == 'learn' and learn['index'] == index, 'observed learning slot differs')
            value = learn['scientific']
            record = inputs.record(index)
            require(record is not None and value['before']['count'] == index, 'observed input incomplete')
            verified = compute.update(value['before'], record, inputs.contract_sha256)
            require(value == {**verified, 'batch_deadline': value['batch_deadline']}, 'observed score/checkpoint differs')
            expected_report = report(value, bundle['learn_sha256'])
            require(bundle['report']['scientific'] == expected_report, 'observed report differs from update')
            output = {'report': expected_report, 'text': expected_report['text'], 'external_delivery': False}
        return {**output, 'producer_report_sha256': bundle['report_sha256'],
            'producer_execution_id': bundle['producer_execution_id'], 'producer_plan_digest': bundle['producer_plan_digest']}

    def ready(task, parents):
        inputs.verify_frozen_identity()
        reason = inputs.formal_guard()
        if reason:
            return reason
        definition = definitions[task.artifact_digest]
        phase, index = definition['phase'], definition['index']
        if phase in {'freeze', 'learn'}:
            reason = inputs.gate()
            if reason:
                return reason
        if phase == 'learn':
            if index < len(inputs.history) and datetime.now(timezone.utc) >= instant(predecessor(parents)['batch_deadline']):
                return 'HISTORICAL_BATCH_BUDGET_EXHAUSTED'
            if inputs.record(index) is None:
                return 'WAITING_FOR_NEW_AUDITED_REPORT'
        if phase in {'observe', 'observe-summary'} and inputs.observation(index) is None:
            return 'WAITING_FOR_REGISTERED_HISTORICAL_REPORT'
        return None

    def parent_results(binding):
        result = {}
        for parent in MainlineLedger(store).context(binding['id'])['parents']:
            value = store.result(parent['task_id'])
            require(value is not None, 'committed historical parent missing')
            result[value.task['business_key']] = value
        return result

    def verify(binding, data):
        inputs.verify_frozen_identity()
        value = json.loads(data)
        definition = definitions[binding['task_digest']]
        require(set(value) == {'schema', 'phase', 'index', 'task_digest', 'release_sha256', 'parents', 'scientific'}, 'closed historical result required')
        require(value['schema'] == binding['artifact_schema'] == SCHEMA and value['phase'] == definition['phase']
                and value['index'] == definition['index'] and value['task_digest'] == binding['task_digest']
                and value['release_sha256'] == binding['release_sha256'] == context.release.digest
                and binding['scientific_contract_sha256'] == inputs.contract_sha256, 'historical artifact identity mismatch')
        parents = parent_results(binding)
        require(value['parents'] == {k: r.artifact.sha256 for k, r in parents.items()}, 'historical parent digest mismatch')
        started_at = value['scientific'].get('started_at') if value['phase'] == 'freeze' else None
        require(value['scientific'] == expected(definition, parents, started_at=started_at), 'historical calculation mismatch')
        if value['phase'] == 'freeze':
            persisted = MainlineLedger(store).context(binding['id'])
            if persisted['commit'] is None:
                require(captured.get(binding['task_digest']) == digest(value), 'batch start not captured by current attempt')
            else:
                require(instant(persisted['attempt']['created_at']) <= instant(started_at) <= instant(persisted['commit']['created_at']), 'batch start outside durable attempt')

    def execute(task, parents, artifacts):
        definition = definitions[task.artifact_digest]
        value = {'schema': SCHEMA, 'phase': definition['phase'], 'index': definition['index'],
            'task_digest': task.artifact_digest, 'release_sha256': context.release.digest,
            'parents': {k: r.artifact.sha256 for k, r in parents.items()},
            'scientific': expected(definition, parents, started_at=datetime.now(timezone.utc).isoformat(), fitting=True)}
        captured[task.artifact_digest] = digest(value)
        return canonical(value)

    def commit_guard(binding, data, server_time):
        value = json.loads(data)
        if value['phase'] == 'learn' and value['index'] < len(inputs.history):
            require(server_time < instant(value['scientific']['batch_deadline']), 'historical batch transaction exceeded budget')

    def progress(manifest):
        states = manifest.task_state_by_digest
        complete = [definitions[t.artifact_digest] for t in manifest.tasks
                    if states[t.artifact_digest].declared_status.value == 'completed']
        learned = sorted(d['index'] for d in complete if d['phase'] == 'learn')
        consumed = sorted(d['index'] for d in complete if d['phase'] in {'report', 'observe'})
        return {'schema': 'historical-progress.v1', 'historical_total': len(inputs.history)-900,
            'historical_learned': sum(i < len(inputs.history) for i in learned),
            'incremental_learned': sum(i >= len(inputs.history) for i in learned),
            'latest_learned_issue': inputs.issue(learned[-1]) if learned else None,
            'consumed_report_issues': [inputs.issue(i) for i in consumed],
            'batch_summary_registered': any(d['phase'] in {'summary', 'observe-summary'} for d in complete),
            'evidence': 'OPERATIONAL_PROJECTION_ONLY'}

    return {name: Capability(name, verify, execute, ready, failure_isolated=phase in {'report', 'observe', 'observe-summary'},
                             commit_guard=commit_guard, progress=progress) for phase, name in CAPABILITIES.items()}
