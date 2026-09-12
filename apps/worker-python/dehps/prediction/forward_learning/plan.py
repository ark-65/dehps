"""One immutable, finite plan per domain; future input readiness is injected."""
import json

from dehps.execution.plan import ExecutionPlan
from dehps.research_os.models import (ControlPlaneManifest, DependencyType, Goal, GoalState,
    GoalStatus, ObjectiveClass, Task, TaskDependency, TaskLane, TaskState, TaskStatus)
from .contract import SCHEMA, digest, require, validate_contract

CAPABILITIES = {phase: 'forward-learning-' + phase + '.v1'
                for phase in ('seal', 'score', 'report', 'analysis', 'observe')}


def build_plan(contract, *, domain='learning'):
    validate_contract(contract)
    require(domain in {'learning', 'observer'}, 'explicit forward domain required')
    contract_sha = digest(contract)
    goal = Goal(f'forward-learning-{contract_sha}-{domain}', '1', ObjectiveClass.RUNTIME_CAPABILITY,
                ('fixed 60 issue learning, complete diagnostics, downstream report and replay',), TaskLane.RESEARCH)
    integration = {'goal': goal.goal_key,
        'ready_condition': 'scoped admission, committed predecessors and signed point-in-time inputs',
        'runner': 'existing canonical Coordinator with injected forward capabilities',
        'upstream_artifacts': 'frozen contract, initial history, prior committed checkpoint and audited label',
        'downstream_artifacts': 'sealed probabilities, complete errors, next update, independent report',
        'status_projection': 'execution-status.v2 in the explicit control domain with input wait reasons',
        'downstream_consumer': 'next canonical task, independent report reader and deterministic replay',
        'evidence_progress_rule': 'descriptive per issue; only final frozen window analysis; no formal evidence/promotion',
        'decision_consumer': 'same versioned verifier at commit, readback, replay and consumption'}
    tasks = []
    def key(index, phase):
        return f'{goal.goal_key}-{contract["targets"][index]["issue"]}-{phase}'
    def add(index, phase, dependencies):
        issue = contract['targets'][index]['issue']
        tasks.append(Task(key(index, phase), goal.goal_key, goal.artifact_digest, SCHEMA, TaskLane.RESEARCH,
            dependencies=tuple(TaskDependency(DependencyType.TASK, dep, 'completed') for dep in dependencies),
            input_artifact_digests=(contract_sha, contract['initial_sha256']),
            requested_capability=CAPABILITIES[phase],
            metric_contract=json.dumps({'mainline_integration': integration,
                'forward': {'phase': phase, 'issue': issue, 'index': index,
                            'contract_sha256': contract_sha, 'domain': domain}}, sort_keys=True)))
    if domain == 'observer':
        for i in range(60):
            add(i, 'observe', [])
    else:
        for i in range(60):
            add(i, 'seal', [] if i == 0 else [key(i-1, 'score')])
            add(i, 'score', [key(i, 'seal')])
            add(i, 'report', [key(i, 'score'), key(i+1, 'seal') if i < 59 else key(59, 'analysis')])
        add(59, 'analysis', [key(i, 'score') for i in range(60)])
    manifest = ControlPlaneManifest((goal,), tuple(tasks), (GoalState(goal.artifact_digest, GoalStatus.ACTIVE),),
                                   tuple(TaskState(t.artifact_digest, TaskStatus.DRAFT) for t in tasks))
    return ExecutionPlan.build(manifest, [dict(business_key=t.task_key, task_digest=t.artifact_digest,
        manifest_digest=manifest.artifact_digest, scientific_contract_sha256=contract_sha,
        verifier_id=t.requested_capability, artifact_schema=SCHEMA) for t in tasks])
