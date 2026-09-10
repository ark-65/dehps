"""Admit the complete fixed historical learning path without core dispatch edits."""
import json
import re

from dehps.execution.context import BoundaryError
from dehps.execution.plan import ExecutionPlan
from dehps.research_os.models import (
    ControlPlaneManifest, DependencyType, Goal, GoalState, GoalStatus,
    ObjectiveClass, Task, TaskDependency, TaskLane, TaskState, TaskStatus,
)
from .learning_execution import CAPABILITIES, PHASES, SCHEMA


def build_plan(*, inputs_sha256, scientific_contract_sha256):
    if any(not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value)
           for value in (inputs_sha256, scientific_contract_sha256)):
        raise BoundaryError('exact learning input and scientific contract identities required')
    goal = Goal('frozen-learning-' + inputs_sha256, '1', ObjectiveClass.RUNTIME_CAPABILITY,
                ('independent finite fitting, evaluation, checkpoint, full report and replay',), TaskLane.RESEARCH)
    integration = {
        'goal': goal.goal_key, 'ready_condition': 'verified fixed inputs, original source, numerical runtime and scoped authority',
        'runner': 'fixed release entry with injected finite learning capabilities',
        'upstream_artifacts': 'fixed snapshot/contract, retained source/issue/payout evidence and canonical predecessor',
        'downstream_artifacts': 'fitted checkpoint, verified evaluations, analysis, archived Top-100 and complete report',
        'status_projection': 'explicit execution-status.v2 learning domain',
        'downstream_consumer': 'next canonical phase, verified report reader and readonly replay',
        'evidence_progress_rule': 'unchanged first-round science; historical reuse distinct from fresh calculation; no promotion',
        'decision_consumer': 'same versioned verifier on commit, readback and replay',
    }
    tasks = []
    for phase in PHASES:
        dependencies = () if not tasks else (TaskDependency(DependencyType.TASK, tasks[-1].task_key, 'completed'),)
        tasks.append(Task(goal.goal_key + '-' + phase, goal.goal_key, goal.artifact_digest,
                          'frozen-learning.v1', TaskLane.RESEARCH, dependencies=dependencies,
                          input_artifact_digests=(inputs_sha256,), requested_capability=CAPABILITIES[phase],
                          metric_contract=json.dumps({'mainline_integration': integration,
                                                      'learning': {'phase': phase, 'inputs_sha256': inputs_sha256}}, sort_keys=True)))
    manifest = ControlPlaneManifest((goal,), tuple(tasks), (GoalState(goal.artifact_digest, GoalStatus.ACTIVE),),
                                    tuple(TaskState(task.artifact_digest, TaskStatus.DRAFT) for task in tasks))
    specs = [dict(business_key=task.task_key, task_digest=task.artifact_digest, manifest_digest=manifest.artifact_digest,
                  scientific_contract_sha256=scientific_contract_sha256, verifier_id=task.requested_capability,
                  artifact_schema=SCHEMA) for task in tasks]
    return ExecutionPlan.build(manifest, specs)
