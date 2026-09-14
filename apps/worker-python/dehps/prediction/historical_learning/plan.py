"""Frozen historical batch with bounded, ordered future intake slots."""
import json

from dehps.execution.plan import ExecutionPlan
from dehps.research_os.models import (ControlPlaneManifest, DependencyType, Goal, GoalState,
    GoalStatus, ObjectiveClass, Task, TaskDependency, TaskLane, TaskState, TaskStatus)
from .contract import SCHEMA, POLICY, digest, require, validate_contract

CAPABILITIES = {p: 'historical-report-'+p+'.v1' for p in ('freeze', 'learn', 'report', 'summary', 'observe', 'observe-summary')}


def build_plan(contract, *, domain='learning'):
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
