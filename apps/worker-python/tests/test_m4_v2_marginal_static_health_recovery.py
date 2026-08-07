from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from dehps.research_os.information_theory.measurement_system_v2.raw_replay_recovery import (
    MARGINAL_STATIC_HEALTH_DESIGN_FAILED_ERROR,
    MARGINAL_STATIC_HEALTH_DESIGN_FAILED_EVENT_DIGEST,
    MARGINAL_STATIC_HEALTH_DESIGN_FAILED_EXECUTION_ID,
    MARGINAL_STATIC_HEALTH_DESIGN_FAILED_TASK_DIGEST,
    MARGINAL_STATIC_HEALTH_DESIGN_STARTED_EVENT_DIGEST,
    MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY,
    MarginalStaticHealthDesignRecoveryError,
    build_marginal_static_health_design_recovery_manifest,
)
from dehps.research_os.models import ControlPlaneManifest, TaskStatus

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"


def _failed_live_manifest() -> ControlPlaneManifest:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payload.pop("manifest_digest")
    target = next(
        task
        for task in payload["tasks"]
        if task["task_key"] == MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY
    )
    target["status"] = "failed"
    target["completion_classification"] = "INTEGRATED"
    live = ControlPlaneManifest.from_dict(payload)
    live_target = next(
        task
        for task in live.tasks
        if task.task_key == MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY
    )
    assert (
        live_target.artifact_digest == MARGINAL_STATIC_HEALTH_DESIGN_FAILED_TASK_DIGEST
    )
    return live


def _events() -> list[dict[str, object]]:
    return [
        {
            "task_digest": MARGINAL_STATIC_HEALTH_DESIGN_FAILED_TASK_DIGEST,
            "execution_id": MARGINAL_STATIC_HEALTH_DESIGN_FAILED_EXECUTION_ID,
            "event_type": "started",
            "event_digest": MARGINAL_STATIC_HEALTH_DESIGN_STARTED_EVENT_DIGEST,
            "payload": [],
        },
        {
            "task_digest": MARGINAL_STATIC_HEALTH_DESIGN_FAILED_TASK_DIGEST,
            "execution_id": MARGINAL_STATIC_HEALTH_DESIGN_FAILED_EXECUTION_ID,
            "event_type": "failed",
            "event_digest": MARGINAL_STATIC_HEALTH_DESIGN_FAILED_EVENT_DIGEST,
            "payload": [["error", MARGINAL_STATIC_HEALTH_DESIGN_FAILED_ERROR]],
        },
    ]


def test_recovery_resets_only_exact_zero_work_health_design_failure() -> None:
    live = _failed_live_manifest()
    before = live.to_dict(include_digest=True)
    recovered, report = build_marginal_static_health_design_recovery_manifest(
        live_payload=before,
        execution_events=_events(),
        execution_artifacts=(),
    )
    after = ControlPlaneManifest.from_dict(recovered)
    state = after.task_state_by_digest[MARGINAL_STATIC_HEALTH_DESIGN_FAILED_TASK_DIGEST]
    assert state.declared_status is TaskStatus.DRAFT
    assert state.completion_classification.value == "INTEGRATION_PENDING"
    assert report["status"] == "SAFE_TO_RECOVER"
    assert report["changed_task_count"] == 1
    assert report["deleted_event_count"] == 0
    assert report["rewritten_event_count"] == 0
    assert report["preexisting_execution_artifact_count"] == 0
    assert report["generated_issues"] == 0
    assert report["historical_outcomes_read"] is False
    assert report["sampled_health_execution"] is False

    before_tasks = {item["task_key"]: item for item in before["tasks"]}
    after_tasks = {item["task_key"]: item for item in recovered["tasks"]}
    for task_key, before_task in before_tasks.items():
        if task_key == MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY:
            continue
        assert after_tasks[task_key] == before_task


@pytest.mark.parametrize("tamper", ["error", "extra_event", "artifact"])
def test_recovery_fails_closed_on_nonexact_execution_history(tamper: str) -> None:
    events = _events()
    artifacts: tuple[dict[str, str], ...] = ()
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
    else:
        artifacts = ({"artifact_digest": "1" * 64},)

    with pytest.raises(MarginalStaticHealthDesignRecoveryError):
        build_marginal_static_health_design_recovery_manifest(
            live_payload=_failed_live_manifest().to_dict(include_digest=True),
            execution_events=events,
            execution_artifacts=artifacts,
        )
