"""Build reviewable observation plans; this module never runs or approves them."""
import json
import re

from dehps.execution.context import BoundaryError
from dehps.execution.plan import ExecutionPlan
from dehps.research_os.models import (
    ControlPlaneManifest, DependencyType, Goal, GoalState, GoalStatus,
    ObjectiveClass, Task, TaskDependency, TaskLane, TaskState, TaskStatus,
)

from .observation_execution import CAPABILITIES, SCHEMA


def build_plan(*, issue: str, frozen_sha256: str, scientific_contract_sha256: str,
               opened_sha256: str | None = None, previous: ExecutionPlan | None = None) -> ExecutionPlan:
    """An opened report extends the same decision task without recapturing it.

    File hashes identify immutable exported inputs, not a caller's assertion of
    scientific validity. The capability's frozen verifier still checks all data,
    source contracts, original seals and outcome availability when executing.
    """
    if not isinstance(issue, str) or not re.fullmatch(r'[0-9]{7}', issue):
        raise BoundaryError('explicit seven-digit issue required')
    for digest in (frozen_sha256, scientific_contract_sha256, opened_sha256):
        if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)):
            raise BoundaryError('exact observation input and scientific identities required')
    if frozen_sha256 is None or scientific_contract_sha256 is None:
        raise BoundaryError('frozen input and scientific identities required')
    goal = Goal('prediction-observation-' + issue, '1', ObjectiveClass.RUNTIME_CAPABILITY,
                ('verified all-100 diagnostics and replay; no new prediction',), TaskLane.RESEARCH)
    integration = {
        'goal': goal.goal_key,
        'ready_condition': 'authenticated plan and legally opened frozen artifacts',
        'runner': 'fixed release entry with registered observation capabilities',
        'upstream_artifacts': 'frozen prediction/model/data; report additionally requires opened settlement/payout',
        'downstream_artifacts': 'immutable decision, complete diagnostic sample and report',
        'status_projection': 'explicit execution-status.v2 control domain',
        'downstream_consumer': 'report capability and deterministic readonly replay',
        'evidence_progress_rule': 'preserve scientific contract; post hoc records are never new predictions',
        'decision_consumer': 'same versioned verifier on commit, read and replay',
    }
    tasks = []
    for phase in ('record', 'report') if opened_sha256 is not None else ('record',):
        contract = {'phase': phase, 'issue': issue, 'frozen_sha256': frozen_sha256}
        dependencies = ()
        inputs = (frozen_sha256,)
        if phase == 'report':
            contract['opened_sha256'] = opened_sha256
            inputs += (opened_sha256,)
            dependencies = (TaskDependency(DependencyType.TASK, tasks[0].task_key, 'completed'),)
        tasks.append(Task(
            goal.goal_key + '-' + phase, goal.goal_key, goal.artifact_digest,
            'frozen-p3-observation.v1', TaskLane.RESEARCH,
            dependencies=dependencies, input_artifact_digests=inputs,
            requested_capability=CAPABILITIES[phase],
            metric_contract=json.dumps({'mainline_integration': integration, 'observation': contract}, sort_keys=True),
        ))
    manifest = ControlPlaneManifest(
        (goal,), tuple(tasks), (GoalState(goal.artifact_digest, GoalStatus.ACTIVE),),
        tuple(TaskState(task.artifact_digest, TaskStatus.DRAFT) for task in tasks),
    )
    specs = [dict(business_key=task.task_key, task_digest=task.artifact_digest,
                  manifest_digest=manifest.artifact_digest,
                  scientific_contract_sha256=scientific_contract_sha256,
                  verifier_id=task.requested_capability, artifact_schema=SCHEMA) for task in tasks]
    if previous is not None:
        previous.validate()
        old = {spec['business_key']: spec for spec in previous.payload['tasks']}
        current = {spec['business_key']: spec for spec in specs}
        for key, spec in old.items():
            if key not in current or any(current[key][field] != value for field, value in spec.items()
                                         if field != 'manifest_digest'):
                raise BoundaryError('extended plan cannot change an existing observation binding')
        specs = [old.get(spec['business_key'], spec) for spec in specs]
    return ExecutionPlan.build(manifest, specs)
