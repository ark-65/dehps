"""One canonical observer Goal, including registered downstream mail consumers."""

import json

from dehps.execution.plan import ExecutionPlan
from dehps.research_os.models import (
    ControlPlaneManifest,
    DependencyType,
    Goal,
    GoalState,
    GoalStatus,
    ObjectiveClass,
    Task,
    TaskDependency,
    TaskLane,
    TaskState,
    TaskStatus,
)

from .contract import SCHEMA, digest, validate

PHASES = (
    "source",
    "report",
    "replay",
    "summary",
    "summary-replay",
    "seal",
    "pre-report",
    "pre-replay",
    "result",
    "post-report",
    "post-replay",
)
CAPABILITIES = {p: "historical-calendar-recovery-" + p + ".v1" for p in PHASES}


def build_plan(contract):
    validate(contract)
    identity = digest(contract)
    goal = Goal(
        "historical-calendar-recovery-" + identity,
        "1",
        ObjectiveClass.RUNTIME_CAPABILITY,
        ("recover immutable omission reports and prospective notifications",),
        TaskLane.RESEARCH,
    )
    integration = {
        "goal": goal.goal_key,
        "ready_condition": "admission, signed registered sources and phase deadline",
        "runner": "canonical Coordinator",
        "upstream_artifacts": "old seals, audited results and registered checkpoint116",
        "downstream_artifacts": "reports, summary, prospective seal and replay",
        "status_projection": "execution-status.v2",
        "evidence_progress_rule": "calendar recovery gives zero scientific credit; preserve all gaps",
        "decision_consumer": "same deterministic registered verifier",
        "downstream_consumer": "cross-version deduplicated mail",
        "next_consumer": "117 audited settlement and immutable delivery ledger",
    }
    tasks = []
    replays = []

    def add(issue, phase, parents=()):
        task = Task(
            goal.goal_key + "-" + issue + "-" + phase,
            goal.goal_key,
            goal.artifact_digest,
            SCHEMA,
            TaskLane.RESEARCH,
            dependencies=tuple(
                TaskDependency(DependencyType.TASK, p, "completed") for p in parents
            ),
            input_artifact_digests=(identity, digest(contract["original_contract"])),
            requested_capability=CAPABILITIES[phase],
            metric_contract=json.dumps(
                {
                    "mainline_integration": integration,
                    "recovery": {
                        "contract_sha256": identity,
                        "issue": issue,
                        "phase": phase,
                    },
                },
                sort_keys=True,
            ),
        )
        tasks.append(task)
        return task.task_key

    for target in contract["targets"][:-1]:
        prior = add(target["issue"], "source")
        prior = add(target["issue"], "report", (prior,))
        replays.append(add(target["issue"], "replay", (prior,)))
    summary = add("2026114-2026116", "summary", tuple(replays))
    add("2026114-2026116", "summary-replay", (summary,))
    prior = None
    for phase in PHASES[5:]:
        prior = add("2026117", phase, () if prior is None else (prior,))
    manifest = ControlPlaneManifest(
        (goal,),
        tuple(tasks),
        (GoalState(goal.artifact_digest, GoalStatus.ACTIVE),),
        tuple(TaskState(t.artifact_digest, TaskStatus.DRAFT) for t in tasks),
    )
    return ExecutionPlan.build(
        manifest,
        [
            {
                "business_key": t.task_key,
                "task_digest": t.artifact_digest,
                "manifest_digest": manifest.artifact_digest,
                "scientific_contract_sha256": identity,
                "verifier_id": t.requested_capability,
                "artifact_schema": SCHEMA,
            }
            for t in tasks
        ],
    )
