from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from dehps.research_os.information_theory.measurement_system_v2.raw_replay_recovery import (
    MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_ERROR,
    MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_EVENT_DIGEST,
    MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_EXECUTION_ID,
    MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_TASK_DIGEST,
    MARGINAL_STATIC_HEALTH_EXECUTION_STARTED_EVENT_DIGEST,
    MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY,
    MarginalStaticHealthExecutionRecoveryError,
    build_marginal_static_health_execution_recovery_manifest,
)
from dehps.research_os.models import ControlPlaneManifest, TaskStatus

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"

CORRECT_PARENT_DIGESTS = (
    "5fbeb6ab0533478ac097747ab73fb0188561849505a76cf7a63a3a02061b2354",
    "8404a16dd48c081e9ada61eb1a968dd0df5b3e1a05e9b6529626f4683f91c362",
    "ec4848874c8883b5e07b72af43a140867e1d3a7e3a865678fde5d3b5a7b1b557",
    "9edf2998c034631f45c163caf5c14c9d53805e2c125a1df24d5dd6111139baa0",
    "4fed70e9d81266ab01c9dfaa689470ac870d5f20fb44f96cfa3761d6eb071ef9",
)
FAILED_PARENT_DIGESTS = (
    CORRECT_PARENT_DIGESTS[0],
    "8404a16ddc3523911c62b38fe7f91e2a1d6d143203061377741b8058991f0776",
    "ec48488730e8c98cf343145d19ebf7a47d0ad7e92aa5679962ed16fbad43528b",
    "9edf299880a4f572ea515d35dfa88829f03141847c3552bbf58b41678071539e",
    "4fed70e9e54872fd2ff148e5822c06de467503243790608237363317542c87db",
)


def _source_payload() -> dict[str, object]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payload.pop("manifest_digest")
    return payload


def _target(payload: dict[str, object]) -> dict[str, object]:
    return next(
        task
        for task in payload["tasks"]
        if task["task_key"] == MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY
    )


def _failed_live_manifest() -> ControlPlaneManifest:
    payload = _source_payload()
    target = _target(payload)
    target["input_artifact_digests"] = list(FAILED_PARENT_DIGESTS)
    target["status"] = "failed"
    target["completion_classification"] = "INTEGRATED"
    live = ControlPlaneManifest.from_dict(payload)
    failed_task = next(
        task
        for task in live.tasks
        if task.task_key == MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY
    )
    assert (
        failed_task.artifact_digest
        == MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_TASK_DIGEST
    )
    return live


def _events() -> list[dict[str, object]]:
    return [
        {
            "task_digest": MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_TASK_DIGEST,
            "execution_id": MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_EXECUTION_ID,
            "event_type": "started",
            "event_digest": MARGINAL_STATIC_HEALTH_EXECUTION_STARTED_EVENT_DIGEST,
            "payload": [],
        },
        {
            "task_digest": MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_TASK_DIGEST,
            "execution_id": MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_EXECUTION_ID,
            "event_type": "failed",
            "event_digest": MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_EVENT_DIGEST,
            "payload": [["error", MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_ERROR]],
        },
    ]


def test_source_manifest_uses_registered_round_41_parent_identities() -> None:
    assert tuple(_target(_source_payload())["input_artifact_digests"]) == (
        CORRECT_PARENT_DIGESTS
    )


def test_recovery_resets_only_exact_zero_replicate_health_execution_failure() -> None:
    live = _failed_live_manifest()
    before = live.to_dict(include_digest=True)
    recovered, report = build_marginal_static_health_execution_recovery_manifest(
        live_payload=before,
        execution_events=_events(),
        execution_artifacts=(),
    )
    after = ControlPlaneManifest.from_dict(recovered)
    state = after.task_state_by_digest[
        MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_TASK_DIGEST
    ]
    assert state.declared_status is TaskStatus.DRAFT
    assert state.completion_classification.value == "INTEGRATION_PENDING"
    assert report["status"] == "SAFE_TO_RECOVER"
    assert report["changed_task_count"] == 1
    assert report["deleted_event_count"] == 0
    assert report["rewritten_event_count"] == 0
    assert report["preexisting_execution_artifact_count"] == 0
    assert report["synthetic_replicates"] == 0
    assert report["duplicate_raw_replay"] is False
    assert report["physical_checkpoint_scan"] is False

    before_tasks = {item["task_key"]: item for item in before["tasks"]}
    after_tasks = {item["task_key"]: item for item in recovered["tasks"]}
    for task_key, before_task in before_tasks.items():
        if task_key == MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY:
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

    with pytest.raises(MarginalStaticHealthExecutionRecoveryError):
        build_marginal_static_health_execution_recovery_manifest(
            live_payload=_failed_live_manifest().to_dict(include_digest=True),
            execution_events=events,
            execution_artifacts=artifacts,
        )
