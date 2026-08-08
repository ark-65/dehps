from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from dehps.research_os.information_theory.measurement_system_v2.raw_replay_recovery import (
    MARGINAL_STATIC_HISTORICAL_GATE_FAILED_ERROR,
    MARGINAL_STATIC_HISTORICAL_GATE_FAILED_EVENT_DIGEST,
    MARGINAL_STATIC_HISTORICAL_GATE_FAILED_EXECUTION_ID,
    MARGINAL_STATIC_HISTORICAL_GATE_FAILED_TASK_DIGEST,
    MARGINAL_STATIC_HISTORICAL_GATE_STARTED_EVENT_DIGEST,
    MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,
    MarginalStaticHistoricalGateRecoveryError,
    build_marginal_static_historical_gate_recovery_manifest,
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
        if task["task_key"] == MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY
    )
    target["status"] = "failed"
    target["completion_classification"] = "INTEGRATED"
    live = ControlPlaneManifest.from_dict(payload)
    live_target = next(
        task
        for task in live.tasks
        if task.task_key == MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY
    )
    assert (
        live_target.artifact_digest
        == MARGINAL_STATIC_HISTORICAL_GATE_FAILED_TASK_DIGEST
    )
    return live


def _events() -> list[dict[str, object]]:
    return [
        {
            "task_digest": MARGINAL_STATIC_HISTORICAL_GATE_FAILED_TASK_DIGEST,
            "execution_id": MARGINAL_STATIC_HISTORICAL_GATE_FAILED_EXECUTION_ID,
            "event_type": "started",
            "event_digest": MARGINAL_STATIC_HISTORICAL_GATE_STARTED_EVENT_DIGEST,
            "payload": [],
        },
        {
            "task_digest": MARGINAL_STATIC_HISTORICAL_GATE_FAILED_TASK_DIGEST,
            "execution_id": MARGINAL_STATIC_HISTORICAL_GATE_FAILED_EXECUTION_ID,
            "event_type": "failed",
            "event_digest": MARGINAL_STATIC_HISTORICAL_GATE_FAILED_EVENT_DIGEST,
            "payload": [
                ["error", MARGINAL_STATIC_HISTORICAL_GATE_FAILED_ERROR]
            ],
        },
    ]


def test_recovery_resets_only_exact_zero_artifact_gate_failure() -> None:
    live = _failed_live_manifest()
    before = live.to_dict(include_digest=True)
    recovered, report = build_marginal_static_historical_gate_recovery_manifest(
        live_payload=before,
        execution_events=_events(),
        execution_artifacts=(),
    )
    after = ControlPlaneManifest.from_dict(recovered)
    state = after.task_state_by_digest[
        MARGINAL_STATIC_HISTORICAL_GATE_FAILED_TASK_DIGEST
    ]
    assert state.declared_status is TaskStatus.DRAFT
    assert state.completion_classification.value == "INTEGRATION_PENDING"
    assert report["status"] == "SAFE_TO_RECOVER"
    assert report["changed_task_count"] == 1
    assert report["preserved_started_event_digest"] == (
        MARGINAL_STATIC_HISTORICAL_GATE_STARTED_EVENT_DIGEST
    )
    assert report["preserved_failed_event_digest"] == (
        MARGINAL_STATIC_HISTORICAL_GATE_FAILED_EVENT_DIGEST
    )
    assert report["deleted_event_count"] == 0
    assert report["rewritten_event_count"] == 0
    assert report["preexisting_execution_artifact_count"] == 0
    assert report["historical_artifact_payloads_read"] is False
    assert report["statistical_result_payloads_read"] is False
    assert report["gate_compilation_executed"] is False
    assert report["evidence_created"] is False

    before_tasks = {item["task_key"]: item for item in before["tasks"]}
    after_tasks = {item["task_key"]: item for item in recovered["tasks"]}
    for task_key, before_task in before_tasks.items():
        if task_key == MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY:
            recovered_target = dict(after_tasks[task_key])
            recovered_target["status"] = before_task["status"]
            recovered_target["completion_classification"] = before_task[
                "completion_classification"
            ]
            assert recovered_target == before_task
            continue
        assert after_tasks[task_key] == before_task


@pytest.mark.parametrize(
    "tamper",
    ["task_digest", "started_digest", "error", "extra_event", "artifact"],
)
def test_recovery_fails_closed_on_nonexact_incident(tamper: str) -> None:
    events = _events()
    artifacts: tuple[dict[str, str], ...] = ()
    if tamper == "task_digest":
        events[0] = copy.deepcopy(events[0])
        events[0]["task_digest"] = "0" * 64
    elif tamper == "started_digest":
        events[0] = copy.deepcopy(events[0])
        events[0]["event_digest"] = "0" * 64
    elif tamper == "error":
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

    with pytest.raises(MarginalStaticHistoricalGateRecoveryError):
        build_marginal_static_historical_gate_recovery_manifest(
            live_payload=_failed_live_manifest().to_dict(include_digest=True),
            execution_events=events,
            execution_artifacts=artifacts,
        )
