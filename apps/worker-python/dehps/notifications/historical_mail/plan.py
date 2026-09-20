"""A separate Goal in the existing observer domain, using the canonical DAG."""
import json
from dehps.execution.plan import ExecutionPlan
from dehps.research_os.models import (ControlPlaneManifest, DependencyType, Goal, GoalState,
    GoalStatus, ObjectiveClass, Task, TaskDependency, TaskLane, TaskState, TaskStatus)
from .contract import SCHEMA, PHASES, digest, validate

CAPABILITIES = {phase: 'historical-mail-'+phase+'.v1' for phase in PHASES}


def build_plan(contract):
    validate(contract); identity = digest(contract)
    goal = Goal('historical-mail-'+identity, '1', ObjectiveClass.RUNTIME_CAPABILITY,
                ('independent replay-bound Top100 and draw-result notifications',), TaskLane.RESEARCH)
    integration = {'goal': goal.goal_key, 'ready_condition': 'admission, registered checkpoint, audited source and phase time',
        'runner': 'canonical Coordinator', 'upstream_artifacts': 'historical registered checkpoints and audited labels',
        'downstream_artifacts': 'prospective seal, readable report and deterministic replay',
        'status_projection': 'execution-status.v2 in separate notification runtime',
        'evidence_progress_rule': 'exploratory prospective output; 证据不足; no promotion',
        'decision_consumer': 'same commit/read/replay verifier', 'downstream_consumer': 'registered deduplicated mail delivery',
        'next_consumer': 'post-draw result and immutable send ledger'}
    tasks = []
    for target in contract['targets']:
        prior = None
        for phase in PHASES:
            name = goal.goal_key+'-'+target['issue']+'-'+phase
            task = Task(name, goal.goal_key, goal.artifact_digest, SCHEMA, TaskLane.RESEARCH,
                dependencies=(() if prior is None else (TaskDependency(DependencyType.TASK, prior, 'completed'),)),
                input_artifact_digests=(identity, contract['historical_contract_sha256']),
                requested_capability=CAPABILITIES[phase], metric_contract=json.dumps({
                    'mainline_integration': integration, 'notification': {'contract_sha256': identity,
                    'issue': target['issue'], 'phase': phase}}, sort_keys=True))
            tasks.append(task); prior = name
    manifest = ControlPlaneManifest((goal,), tuple(tasks), (GoalState(goal.artifact_digest, GoalStatus.ACTIVE),),
                                   tuple(TaskState(t.artifact_digest, TaskStatus.DRAFT) for t in tasks))
    return ExecutionPlan.build(manifest, [dict(business_key=t.task_key, task_digest=t.artifact_digest,
        manifest_digest=manifest.artifact_digest, scientific_contract_sha256=identity,
        verifier_id=t.requested_capability, artifact_schema=SCHEMA) for t in tasks])
