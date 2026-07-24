import json
from pathlib import Path

from typer.testing import CliRunner

from dehps import cli
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory import (
    LEGACY_GOAL_KEY,
    M4_FORWARD_EVENT_KEY,
    M4_GOAL_KEY,
    build_m4_status,
    load_m4_manifest,
    manifest_with_external_event,
)
from dehps.research_os.models import GoalStatus, TaskStatus


ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"


def _by_task(snapshot):
    return {item.task_key: item for item in snapshot.resolutions}


def test_m4_manifest_freezes_legacy_mainline_and_selects_p1() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    goals = {goal.goal_key: goal for goal in manifest.goals}
    states = manifest.goal_state_by_digest

    assert states[goals[M4_GOAL_KEY].artifact_digest].status is GoalStatus.ACTIVE
    assert states[goals[LEGACY_GOAL_KEY].artifact_digest].status is GoalStatus.RETIRED
    legacy_target = json.loads(goals[LEGACY_GOAL_KEY].target_metric_manifest)
    assert legacy_target["research_status"] == "rejected"
    assert legacy_target["mainline_status"] == "frozen"
    assert [item.task_key for item in snapshot.ready_queue] == [
        "m4-p1-contract-and-preregistration"
    ]
    assert _by_task(snapshot)["m4-p1-contract-and-preregistration"].status is TaskStatus.READY

    legacy_resolutions = [
        item for item in snapshot.resolutions if item.goal_key == LEGACY_GOAL_KEY
    ]
    assert all(
        item.status in {TaskStatus.COMPLETED, TaskStatus.SUPERSEDED}
        for item in legacy_resolutions
    )


def test_m4_p1_ready_queue_does_not_unblock_formal_run() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    snapshot = ResearchOSControlPlane().resolve(manifest)

    assert [item.task_key for item in snapshot.ready_queue] == [
        "m4-p1-contract-and-preregistration"
    ]
    assert _by_task(snapshot)["m4-p2-synthetic-measurement-validation"].status is TaskStatus.DEPENDENCY_WAIT
    assert build_m4_status(manifest, snapshot=snapshot)["formal_real_data_run"] == "NOT_STARTED"


def test_forward_event_intake_is_local_and_does_not_change_p1_path() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    first = ResearchOSControlPlane().resolve(manifest)
    second_manifest = manifest_with_external_event(
        manifest,
        event_key=M4_FORWARD_EVENT_KEY,
    )
    second = ResearchOSControlPlane().resolve(second_manifest)

    assert _by_task(first)["m4-forward-evidence-intake-2026085"].status is TaskStatus.EXTERNAL_WAIT
    assert _by_task(second)["m4-forward-evidence-intake-2026085"].status is TaskStatus.READY
    assert _by_task(first)["m4-p1-contract-and-preregistration"].status is TaskStatus.READY
    assert _by_task(second)["m4-p1-contract-and-preregistration"].status is TaskStatus.READY
    assert _by_task(first)["m4-forward-evidence-intake-2026085"].task_digest == _by_task(
        second
    )["m4-forward-evidence-intake-2026085"].task_digest


def test_m4_status_keeps_engineering_and_evidence_progress_separate() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    status = build_m4_status(manifest)

    assert status["goal"] == M4_GOAL_KEY
    assert status["current_phase"] == "M4-P1"
    assert status["current_state"] == "READY"
    assert status["next_ready_task"] == "m4-p1-contract-and-preregistration"
    assert status["progress"]["engineering_percent"] == 5
    assert status["progress"]["evidence_percent"] == 0
    assert status["gate_status"] == {
        "promotion_gate": "CLOSED",
        "adaptive_supervisor": "STOPPED",
        "production_action": "none",
    }
    assert status["next_external_dependency"] == M4_FORWARD_EVENT_KEY
    assert status["current_statistics"]["practical_null"] == "NOT_PREREGISTERED"
    assert status["formal_real_data_run"] == "NOT_STARTED"
    assert status["production_impact"] == "none"


def test_m4_p5_projects_external_wait_as_wait_forward_then_settling() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    phase_keys = {
        "m4-p1-contract-and-preregistration",
        "m4-p2-synthetic-measurement-validation",
        "m4-p3-strict-historical-walk-forward",
        "m4-p4-negative-controls-and-robustness",
    }
    for task in payload["tasks"]:
        if task["task_key"] in phase_keys:
            task["status"] = "completed"
            task["metric_contract"]["engineering_complete"] = True
    p5_manifest = type(manifest).from_dict(payload)

    waiting = build_m4_status(p5_manifest)
    settling_manifest = manifest_with_external_event(
        p5_manifest,
        event_key=M4_FORWARD_EVENT_KEY,
    )
    settling = build_m4_status(settling_manifest)

    assert waiting["current_phase"] == "M4-P5"
    assert waiting["current_state"] == "WAIT_FORWARD"
    assert waiting["next_ready_task"] is None
    assert waiting["next_external_dependency"] == M4_FORWARD_EVENT_KEY
    assert settling["current_phase"] == "M4-P5"
    assert settling["current_state"] == "SETTLING"
    assert settling["next_ready_task"] == "m4-forward-evidence-intake-2026085"
    assert settling["next_external_dependency"] is None


def test_m4_cli_emits_digest_addressed_manifest_and_status() -> None:
    runner = CliRunner()

    manifest_result = runner.invoke(cli.app, ["research-os", "m4-manifest"])
    status_result = runner.invoke(cli.app, ["research-os", "m4-status"])

    assert manifest_result.exit_code == status_result.exit_code == 0
    manifest_payload = json.loads(manifest_result.stdout)
    status_payload = json.loads(status_result.stdout)
    assert len(manifest_payload["manifest_digest"]) == 64
    assert manifest_payload["manifest_digest"] == status_payload["manifest_digest"]
    assert status_payload["dispatch_performed"] is False
    assert status_payload["production_impact"] == "none"


def test_nightly_iteration_is_routed_through_m4_status_preflight() -> None:
    script = (ROOT / "scripts/hourly_self_iterate.sh").read_text(encoding="utf-8")

    assert 'M4_STATUS_FILE="$LOG_DIR/m4-information-theory-status.json"' in script
    assert "research-os m4-status" in script
    assert "canonical M4 status preflight failed" in script
    assert "当前唯一主线：`M4_INFORMATION_THEORY_EVIDENCE`" in script
    assert "不得恢复权重搜索、候选生成、TopK 调参或旧 adaptive training" in script
    assert "只允许处理状态报告中的 `next_ready_task`" in script
