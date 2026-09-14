from __future__ import annotations

import re
from typing import Any

from dehps.research_os.models import (
    CompletionClassification,
    ControlPlaneManifest,
    ResearchOSValidationError,
    Task,
    TaskStatus,
)


MAINLINE_EXECUTION_FACT_PREFIX = "mainline-execution"
_DIGEST = r"[0-9a-f]{64}"


def mainline_completion_fact(
    *,
    task: Task,
    execution_id: str,
) -> str:
    if not re.fullmatch(_DIGEST, execution_id):
        raise ResearchOSValidationError("mainline execution_id must be a sha256 digest")
    return (
        f"{MAINLINE_EXECUTION_FACT_PREFIX}:{task.task_key}:"
        f"{task.artifact_digest}:{execution_id}:completed"
    )


def completion_fact_execution_id(*, task: Task, fact_key: str) -> str | None:
    pattern = (
        rf"^{re.escape(MAINLINE_EXECUTION_FACT_PREFIX)}:"
        rf"{re.escape(task.task_key)}:{re.escape(task.artifact_digest)}:"
        rf"({_DIGEST}):completed$"
    )
    match = re.fullmatch(pattern, fact_key)
    return None if match is None else match.group(1)


def completion_execution_ids(
    manifest: ControlPlaneManifest,
    *,
    task: Task,
) -> tuple[str, ...]:
    # Compute the immutable task digest and compile its exact match once, not
    # once per artifact fact. Long per-issue DAGs otherwise repeatedly hash the
    # entire metric contract during every resolver pass. Matching is unchanged.
    pattern = re.compile(
        rf"^{re.escape(MAINLINE_EXECUTION_FACT_PREFIX)}:"
        rf"{re.escape(task.task_key)}:{re.escape(task.artifact_digest)}:"
        rf"({_DIGEST}):completed$"
    )
    return tuple(
        sorted(
            match.group(1)
            for fact in manifest.facts.artifacts
            if (match := pattern.fullmatch(fact)) is not None
        )
    )


def validate_mainline_completion_declarations(
    manifest: ControlPlaneManifest,
) -> None:
    # Index the exact existing fact grammar once per resolver pass. Scanning
    # every artifact for every completed task makes long chronological DAGs
    # quadratic per transition. Both task key and immutable digest must match;
    # malformed facts and competing execution IDs keep their original meaning.
    fact_pattern = re.compile(
        rf"{re.escape(MAINLINE_EXECUTION_FACT_PREFIX)}:([\s\S]*):({_DIGEST}):({_DIGEST}):completed"
    )
    executions: dict[tuple[str, str], list[str]] = {}
    for fact in manifest.facts.artifacts:
        match = fact_pattern.fullmatch(fact)
        if match is not None:
            executions.setdefault((match.group(1), match.group(2)), []).append(match.group(3))
    states = manifest.task_state_by_digest
    for task in manifest.tasks:
        if task.requested_capability is None:
            continue
        state = states[task.artifact_digest]
        classification = state.completion_classification
        if state.declared_status is TaskStatus.COMPLETED:
            if classification is not CompletionClassification.COMPLETE:
                raise ResearchOSValidationError(
                    f"executable task {task.task_key!r} cannot be completed without "
                    "completion_classification COMPLETE"
                )
            execution_ids = executions.get((task.task_key, task.artifact_digest), ())
            if len(execution_ids) != 1:
                raise ResearchOSValidationError(
                    f"executable task {task.task_key!r} requires exactly one immutable "
                    "successful mainline execution fact"
                )
        elif classification is CompletionClassification.COMPLETE:
            raise ResearchOSValidationError(
                f"task {task.task_key!r} cannot claim COMPLETE before operational completion"
            )
        elif state.declared_status is TaskStatus.RUNNING and classification not in {
            CompletionClassification.INTEGRATED,
            CompletionClassification.VALIDATED_IN_MAINLINE,
        }:
            raise ResearchOSValidationError(
                f"running task {task.task_key!r} must be classified INTEGRATED "
                "or VALIDATED_IN_MAINLINE"
            )


def integration_contract(task: Task) -> dict[str, Any]:
    from json import loads

    metric = loads(task.metric_contract)
    value = metric.get("mainline_integration")
    if not isinstance(value, dict):
        raise ResearchOSValidationError(
            f"task {task.task_key!r} is missing metric_contract.mainline_integration"
        )
    required = {
        "goal",
        "ready_condition",
        "runner",
        "upstream_artifacts",
        "downstream_artifacts",
        "status_projection",
        "downstream_consumer",
        "evidence_progress_rule",
        "decision_consumer",
    }
    missing = sorted(required - set(value))
    if missing:
        raise ResearchOSValidationError(
            f"task {task.task_key!r} mainline integration contract is missing: "
            + ", ".join(missing)
        )
    return dict(value)
