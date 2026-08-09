from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_balanced_design_feasibility_execution_recovery import (
    CORRECTED_SOURCE_CONTRACT_DIGEST,
    CORRECTED_TASK_DIGEST,
    FAILED_ERROR,
    FAILED_EVENT_DIGEST,
    FAILED_EXECUTION_ID,
    FAILED_SOURCE_CONTRACT_DIGEST,
    FAILED_STARTED_EVENT_DIGEST,
    FAILED_TASK_DIGEST,
    BalancedDesignExecutionRecoveryError,
    build_balanced_design_execution_recovery_manifest,
)
from dehps.research_os.models import ControlPlaneManifest, TaskStatus

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"
TASK_KEY = "prediction-v2-balanced-design-feasibility-execution"
NEW_SOURCE_FACT = (
    "prediction-v2-balanced-design-feasibility-execution-source:"
    f"{CORRECTED_SOURCE_CONTRACT_DIGEST}"
)


def _source_payload() -> dict:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payload.pop("manifest_digest")
    return payload


def _target(payload: dict) -> dict:
    return next(task for task in payload["tasks"] if task["task_key"] == TASK_KEY)


def _failed_live_manifest() -> ControlPlaneManifest:
    payload = _source_payload()
    target = _target(payload)
    target["input_artifact_digests"][0] = FAILED_SOURCE_CONTRACT_DIGEST
    target["status"] = "failed"
    target["completion_classification"] = "INTEGRATED"
    payload["facts"]["artifacts"].remove(NEW_SOURCE_FACT)
    live = ControlPlaneManifest.from_dict(payload)
    failed_task = next(task for task in live.tasks if task.task_key == TASK_KEY)
    assert failed_task.artifact_digest == FAILED_TASK_DIGEST
    return live


def _events() -> list[dict]:
    return [
        {
            "task_digest": FAILED_TASK_DIGEST,
            "execution_id": FAILED_EXECUTION_ID,
            "event_type": "started",
            "event_digest": FAILED_STARTED_EVENT_DIGEST,
            "payload": [],
        },
        {
            "task_digest": FAILED_TASK_DIGEST,
            "execution_id": FAILED_EXECUTION_ID,
            "event_type": "failed",
            "event_digest": FAILED_EVENT_DIGEST,
            "payload": [["error", FAILED_ERROR]],
        },
    ]


def test_corrected_source_revises_only_execution_source_identity() -> None:
    source = ControlPlaneManifest.from_dict(_source_payload())
    task = next(task for task in source.tasks if task.task_key == TASK_KEY)
    assert task.artifact_digest == CORRECTED_TASK_DIGEST
    assert task.input_artifact_digests[0] == CORRECTED_SOURCE_CONTRACT_DIGEST
    assert NEW_SOURCE_FACT in source.facts.artifacts


def test_recovery_revises_only_exact_zero_artifact_failure() -> None:
    live = _failed_live_manifest()
    before = live.to_dict(include_digest=True)
    recovered, report = build_balanced_design_execution_recovery_manifest(
        live_payload=before,
        corrected_source_payload=_source_payload(),
        execution_events=_events(),
        execution_artifacts=(),
        require_registered_failure=False,
    )
    after = ControlPlaneManifest.from_dict(recovered)
    corrected = next(task for task in after.tasks if task.task_key == TASK_KEY)
    state = after.task_state_by_digest[corrected.artifact_digest]
    assert corrected.artifact_digest == CORRECTED_TASK_DIGEST
    assert state.declared_status is TaskStatus.DRAFT
    assert state.completion_classification.value == "INTEGRATION_PENDING"
    assert NEW_SOURCE_FACT in after.facts.artifacts
    assert report["status"] == "SAFE_TO_RECOVER"
    assert report["preserved_started_event_digest"] == FAILED_STARTED_EVENT_DIGEST
    assert report["preserved_failed_event_digest"] == FAILED_EVENT_DIGEST
    assert report["deleted_event_count"] == 0
    assert report["rewritten_event_count"] == 0
    assert report["preexisting_execution_artifact_count"] == 0
    assert report["checkpoint_count"] == 0
    assert report["historical_outcomes_read"] is False

    before_tasks = {item["task_key"]: item for item in before["tasks"]}
    after_tasks = {item["task_key"]: item for item in recovered["tasks"]}
    for task_key, before_task in before_tasks.items():
        if task_key == TASK_KEY:
            continue
        assert after_tasks[task_key] == before_task


@pytest.mark.parametrize("tamper", ["error", "extra_event", "artifact", "task"])
def test_recovery_fails_closed_on_nonexact_failure(tamper: str) -> None:
    events = _events()
    artifacts: tuple[dict[str, str], ...] = ()
    source = _source_payload()
    if tamper == "error":
        events[-1] = copy.deepcopy(events[-1])
        events[-1]["payload"] = [["error", "different"]]
    elif tamper == "extra_event":
        events.append(
            {
                **events[-1],
                "event_type": "completed",
                "event_digest": "0" * 64,
            }
        )
    elif tamper == "artifact":
        artifacts = ({"artifact_digest": "1" * 64},)
    else:
        _target(source)["input_artifact_digests"][0] = "2" * 64

    with pytest.raises(BalancedDesignExecutionRecoveryError):
        build_balanced_design_execution_recovery_manifest(
            live_payload=_failed_live_manifest().to_dict(include_digest=True),
            corrected_source_payload=source,
            execution_events=events,
            execution_artifacts=artifacts,
            require_registered_failure=False,
        )
