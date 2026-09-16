"""Frozen historical batch with bounded, ordered future intake slots."""
import json

from dehps.execution.plan import ExecutionPlan
from dehps.research_os.models import (ControlPlaneManifest, DependencyType, Goal, GoalState,
    GoalStatus, ObjectiveClass, Task, TaskDependency, TaskLane, TaskState, TaskStatus)
from .contract import SCHEMA, POLICY, digest, require, validate_contract

CAPABILITIES = {p: 'historical-report-'+p+'.v1' for p in ('freeze', 'learn', 'report', 'summary', 'observe', 'observe-summary')}
CAPABILITIES.update({p: 'historical-report-'+p+'.v1' for p in ('resume', 'observe-resume')})


def build_plan(contract, *, domain='learning', continuation=None):
    if continuation is not None:
        return continuation_plan(contract, continuation, domain=domain)
    validate_contract(contract)
    require(domain in {'learning', 'observer'}, 'explicit historical control domain required')
    contract_sha = digest(contract)
    goal = Goal(f'historical-report-{contract_sha}-{domain}', '1', ObjectiveClass.RUNTIME_CAPABILITY,
        ('historical batch, complete labels, independent reports and deterministic replay',), TaskLane.RESEARCH)
    integration = {'goal': goal.goal_key, 'ready_condition': 'admission, frozen inputs, committed predecessor and audited source',
        'runner': 'canonical Coordinator with injected historical-report capabilities',
        'upstream_artifacts': 'frozen history, signed ordered labels, prior checkpoint, original machine references',
        'downstream_artifacts': 'complete scores, pre/post checkpoint, omission diagnostics and independent report',
        'status_projection': 'execution-status.v2 in explicit domain and current plan/release/execution',
        'downstream_consumer': 'next update, report, independent observer and deterministic replay',
        'evidence_progress_rule': 'historical reconstruction, descriptive only; no promotion',
        'decision_consumer': 'same versioned verifier at commit, readback, replay and observation'}
    n = len(contract['issues'])
    tasks = []
    def key(index, phase):
        marker = contract['issues'][index] if 900 <= index < n else ('batch' if index < 900 else f'slot{index-n+1:02d}')
        return f'{goal.goal_key}-{marker}-{phase}'
    def add(index, phase, dependencies):
        tasks.append(Task(key(index, phase), goal.goal_key, goal.artifact_digest, SCHEMA, TaskLane.RESEARCH,
            dependencies=tuple(TaskDependency(DependencyType.TASK, d, 'completed') for d in dependencies),
            input_artifact_digests=(contract_sha, contract['history_sha256']), requested_capability=CAPABILITIES[phase],
            metric_contract=json.dumps({'mainline_integration': integration, 'historical': {
                'phase': phase, 'index': index, 'contract_sha256': contract_sha, 'domain': domain}}, sort_keys=True)))
    if domain == 'learning':
        add(-1, 'freeze', [])
        for i in range(900, n+POLICY['incremental_slots']):
            deps = [key(-1, 'freeze') if i == 900 else key(i-1, 'learn')]
            if i == n:
                deps.append(key(-1, 'summary'))
            add(i, 'learn', deps)
            add(i, 'report', [key(i, 'learn')])
        add(-1, 'summary', [key(i, 'report') for i in range(900, n)])
    else:
        for i in range(900, n+POLICY['incremental_slots']):
            add(i, 'observe', [])
        add(-1, 'observe-summary', [key(i, 'observe') for i in range(900, n)])
    manifest = ControlPlaneManifest((goal,), tuple(tasks), (GoalState(goal.artifact_digest, GoalStatus.ACTIVE),),
        tuple(TaskState(t.artifact_digest, TaskStatus.DRAFT) for t in tasks))
    manifest_digest = manifest.artifact_digest
    return ExecutionPlan.build(manifest, [dict(business_key=t.task_key, task_digest=t.artifact_digest,
        manifest_digest=manifest_digest, scientific_contract_sha256=contract_sha,
        verifier_id=t.requested_capability, artifact_schema=SCHEMA) for t in tasks])


def continuation_plan(contract, continuation, *, domain):
    from .continuation import validate, retained_tasks
    validate(continuation, contract)
    require(domain in {'learning', 'observer'}, 'explicit historical control domain required')
    original = build_plan(contract, domain=domain)
    old_manifest = original.validate()
    retained = retained_tasks(original, continuation['retained_count'])
    contract_sha, continuation_sha = digest(contract), digest(continuation)
    start = 900 + continuation['retained_count']
    n = len(contract['issues'])
    # Keep the original Goal; the canonical resolver forbids cross-Goal edges.
    # Only the new task business keys carry the explicitly admitted continuation.
    goal = old_manifest.goals[0]
    namespace = f'historical-report-continuation-{continuation_sha}-{domain}'
    integration = json.loads(old_manifest.tasks[0].metric_contract)['mainline_integration']
    integration = {**integration, 'goal': goal.goal_key,
        'upstream_artifacts': 'exact registered prior-release prefix, admitted continuation and next audited label'}
    tasks = []
    def key(index, phase):
        marker = contract['issues'][index] if 900 <= index < n else ('batch' if index < 900 else f'slot{index-n+1:02d}')
        return f'{namespace}-{marker}-{phase}'
    def add(index, phase, parents):
        tasks.append(Task(key(index, phase), goal.goal_key, goal.artifact_digest, SCHEMA, TaskLane.RESEARCH,
            dependencies=tuple(TaskDependency(DependencyType.TASK, p, 'completed') for p in parents),
            input_artifact_digests=(contract_sha, contract['history_sha256'], continuation_sha),
            requested_capability=CAPABILITIES[phase], metric_contract=json.dumps({'mainline_integration': integration,
                'historical': {'phase': phase, 'index': index, 'domain': domain,
                    'contract_sha256': contract_sha, 'continuation_sha256': continuation_sha}}, sort_keys=True)))
    old = {(json.loads(t.metric_contract)['historical']['index'],
            json.loads(t.metric_contract)['historical']['phase']): t.task_key for t in retained}
    if domain == 'learning':
        reports = [old[i, 'report'] for i in range(900, start)]
        add(-1, 'resume', [old[start-1, 'learn'], *reports])
        for index in range(start, n+POLICY['incremental_slots']):
            deps = [key(-1, 'resume') if index == start else key(index-1, 'learn')]
            if index == n:
                deps.append(key(-1, 'summary'))
            add(index, 'learn', deps)
            add(index, 'report', [key(index, 'learn')])
        add(-1, 'summary', reports + [key(i, 'report') for i in range(start, n)])
    else:
        observations = [old[i, 'observe'] for i in range(900, start)]
        add(-1, 'observe-resume', observations)
        for index in range(start, n+POLICY['incremental_slots']):
            add(index, 'observe', [key(-1, 'observe-resume')])
        add(-1, 'observe-summary', observations + [key(i, 'observe') for i in range(start, n)])
    manifest = ControlPlaneManifest(old_manifest.goals, (*retained, *tasks), old_manifest.goal_states,
        tuple(TaskState(t.artifact_digest, TaskStatus.DRAFT) for t in (*retained, *tasks)))
    retained_digests = {t.artifact_digest for t in retained}
    specs = [s for s in original.payload['tasks'] if s['task_digest'] in retained_digests]
    specs += [dict(business_key=t.task_key, task_digest=t.artifact_digest,
        manifest_digest=manifest.artifact_digest, scientific_contract_sha256=contract_sha,
        verifier_id=t.requested_capability, artifact_schema=SCHEMA) for t in tasks]
    return ExecutionPlan.build(manifest, specs)
