from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dehps.notifications.prediction_v2_shadow import build_notification_envelope
from dehps.prediction.v2.contracts import (
    load_shadow_contract,
    seal_artifact,
    verify_artifact,
)
from dehps.prediction.v2.generator import generate_shadow_pool
from dehps.prediction.v2.issues import (
    POST_CAPABILITY,
    POST_REPLAY_CAPABILITY,
    PRE_CAPABILITY,
    PRE_REPLAY_CAPABILITY,
    history_from_artifact,
    issue_facts,
    issue_task_keys,
    load_json_artifact,
    task_contract,
)
from dehps.prediction.v2.mainline import (
    CONTROL_PLANE_KEY,
    PredictionV2CapabilityResult,
    PredictionV2MainlineError,
    _execution_payload,
    _load_object,
    _persist_and_register,
)
from dehps.prediction.v2.replay import replay_post_draw, replay_pre_draw
from dehps.prediction.v2.reports import build_post_draw_report, build_pre_draw_report
from dehps.prediction.v2.state import encode_state
from dehps.research_os.mainline import integration_contract
from dehps.research_os.models import Task


def _load_inputs(root_dir: Path, task: Task) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract = task_contract(task)
    issue_manifest = load_json_artifact(root_dir, str(contract["issue_manifest_path"]))
    history_artifact = load_json_artifact(root_dir, str(contract["history_artifact_path"]))
    scheduler_plan = load_json_artifact(root_dir, str(contract["scheduler_plan_path"]))
    issue_value = verify_artifact(
        issue_manifest,
        domain="dehps.prediction-v2.issue-manifest.v1",
    )
    history_value = verify_artifact(
        history_artifact,
        domain="dehps.prediction-v2.history-snapshot-artifact.v1",
    )
    scheduler_value = verify_artifact(
        scheduler_plan,
        domain="dehps.prediction-v2.live-scheduler-plan.v1",
    )
    if issue_value.get("history_artifact_digest") != history_value.get("artifact_digest"):
        raise PredictionV2MainlineError("issue manifest/history identity mismatch")
    if set(task.input_artifact_digests) != {
        str(issue_value["artifact_digest"]),
        str(history_value["artifact_digest"]),
        str(scheduler_value["artifact_digest"]),
    }:
        raise PredictionV2MainlineError("issue task input allowlist changed")
    if scheduler_value.get("issue") != issue_value.get("issue"):
        raise PredictionV2MainlineError("scheduler plan/issue identity mismatch")
    return issue_value, history_value, scheduler_value


def _completed_execution(repository: Any, *, task_key: str) -> tuple[str, tuple[dict, ...]]:
    events = repository.list_mainline_execution_events(
        control_plane_key=CONTROL_PLANE_KEY,
        task_key=task_key,
    )
    completed = [item for item in events if item.get("event_type") == "completed"]
    if len(completed) != 1:
        raise PredictionV2MainlineError(f"expected exactly one completion for {task_key}")
    execution_id = str(completed[0]["execution_id"])
    registrations = repository.list_mainline_artifacts(
        control_plane_key=CONTROL_PLANE_KEY,
        execution_id=execution_id,
    )
    if not registrations:
        raise PredictionV2MainlineError(f"missing registered artifacts for {task_key}")
    return execution_id, registrations


def _registered_by_type(root_dir: Path, registrations: tuple[dict, ...]) -> dict[str, dict]:
    values: dict[str, dict] = {}
    for item in registrations:
        artifact_type = str(item["artifact_type"])
        if artifact_type in values:
            raise PredictionV2MainlineError(f"duplicate registered artifact type: {artifact_type}")
        payload = _load_object(root_dir / str(item["artifact_path"]))
        if payload.get("artifact_digest") != item.get("artifact_digest"):
            raise PredictionV2MainlineError("registered artifact digest/path mismatch")
        values[artifact_type] = payload
    return values


def _assert_task(task: Task, *, expected_key: str, expected_capability: str) -> None:
    integration_contract(task)
    if task.task_key != expected_key or task.requested_capability != expected_capability:
        raise PredictionV2MainlineError("issue capability received the wrong task")


def _assert_control_plane(control_plane_key: str) -> None:
    if control_plane_key != CONTROL_PLANE_KEY:
        raise PredictionV2MainlineError("Prediction v2 issue task used another control plane")


def _typed_execution_artifact(
    *,
    kind: str,
    issue: str,
    task: Task,
    execution_id: str,
    child_payloads: tuple[Mapping[str, Any], ...],
    historical_outcomes_read: bool,
) -> dict[str, Any]:
    if kind not in {"predraw", "postdraw"}:
        raise ValueError("unsupported issue execution kind")
    artifact_kind = "PreDraw" if kind == "predraw" else "PostDraw"
    return seal_artifact(
        {
            "schema_version": f"dehps-prediction-v2-issue-{kind}-execution.v1",
            "artifact_type": f"PredictionV2Issue{artifact_kind}Execution.v1",
            "issue": issue,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "execution_id": execution_id,
            "status": "COMPLETE",
            "route": "BASELINE_ONLY",
            "historical_outcomes_read": historical_outcomes_read,
            "historical_evidence": "NOT_RUN",
            "evidence_progress_delta": 0,
            "promotion_gate_opened": False,
            "parent_digests": [str(item["artifact_digest"]) for item in child_payloads],
        },
        domain=f"dehps.prediction-v2.issue-{kind}-execution.v1",
    )


def _typed_replay_artifact(
    *,
    kind: str,
    issue: str,
    replay: Mapping[str, Any],
    envelope: Mapping[str, Any],
    parent_execution_digest: str,
) -> dict[str, Any]:
    if kind not in {"predraw", "postdraw"}:
        raise ValueError("unsupported issue replay kind")
    artifact_kind = "PreDraw" if kind == "predraw" else "PostDraw"
    return seal_artifact(
        {
            "schema_version": f"dehps-prediction-v2-issue-{kind}-replay-artifact.v1",
            "artifact_type": f"PredictionV2Issue{artifact_kind}ReplayArtifact.v1",
            "issue": issue,
            "status": "REPLAY_VERIFIED",
            "replay_artifact_digest": replay["artifact_digest"],
            "notification_envelope_digest": envelope["artifact_digest"],
            "parent_execution_artifact_digest": parent_execution_digest,
            "historical_evidence": "NOT_RUN",
            "evidence_progress_delta": 0,
            "promotion_gate_opened": False,
            "parent_digests": [
                replay["artifact_digest"],
                envelope["artifact_digest"],
                parent_execution_digest,
            ],
        },
        domain=f"dehps.prediction-v2.issue-{kind}-replay-artifact.v1",
    )


class PredictionV2IssuePreDrawCapability:
    def __init__(self, *, root_dir: Path) -> None:
        self.root_dir = root_dir

    def execute(self, *, control_plane_key: str, task: Task, execution_id: str, git_commit: str):
        _assert_control_plane(control_plane_key)
        issue_manifest, history_artifact, scheduler_plan = _load_inputs(self.root_dir, task)
        issue = str(issue_manifest["issue"])
        keys = issue_task_keys(issue)
        _assert_task(task, expected_key=keys["pre"], expected_capability=PRE_CAPABILITY)
        history = history_from_artifact(history_artifact)
        contract = load_shadow_contract(self.root_dir)
        state = encode_state(history, as_of_issue=str(issue_manifest["as_of_issue"]), target_issue=issue)
        pool, top100 = generate_shadow_pool(contract=contract, state=state)
        report = build_pre_draw_report(contract=contract, state=state, pool=pool, top100=top100)
        core_children = (issue_manifest, history_artifact, scheduler_plan, state, pool, top100, report)
        typed_execution = _typed_execution_artifact(
            kind="predraw",
            issue=issue,
            task=task,
            execution_id=execution_id,
            child_payloads=core_children,
            historical_outcomes_read=False,
        )
        children = (*core_children, typed_execution)
        execution = _execution_payload(
            task=task, execution_id=execution_id, control_plane_key=control_plane_key,
            git_commit=git_commit, child_payloads=children,
            downstream_consumer=keys["pre_replay"], replay_status="PENDING",
        )
        path, registrations = _persist_and_register(
            root_dir=self.root_dir, task=task, execution_id=execution_id,
            control_plane_key=control_plane_key, git_commit=git_commit,
            children=children, execution=execution,
        )
        return PredictionV2CapabilityResult(
            execution_artifact=execution, execution_artifact_path=path,
            registrations=registrations, completion_facts=(issue_facts(issue)["pre_complete"],),
        )


class PredictionV2IssuePreDrawReplayCapability:
    def __init__(self, *, repository: Any, root_dir: Path) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(self, *, control_plane_key: str, task: Task, execution_id: str, git_commit: str):
        _assert_control_plane(control_plane_key)
        issue_manifest, history_artifact, scheduler_plan = _load_inputs(self.root_dir, task)
        issue = str(issue_manifest["issue"])
        keys = issue_task_keys(issue)
        _assert_task(task, expected_key=keys["pre_replay"], expected_capability=PRE_REPLAY_CAPABILITY)
        parent_id, registrations = _completed_execution(self.repository, task_key=keys["pre"])
        stored = _registered_by_type(self.root_dir, registrations)
        required = {
            "PredictionV2IssueManifest.v1", "PredictionV2HistorySnapshotArtifact.v1",
            "PredictionV2LiveSchedulerPlan.v1",
            "PredictionV2StateArtifact.v1", "PredictionV2ShadowPoolArtifact.v1",
            "PredictionV2ShadowTop100Artifact.v1", "PredictionV2PreDrawReport.v1",
            "PredictionV2IssuePreDrawExecution.v1",
            "research_os_mainline_execution",
        }
        if set(stored) != required:
            raise PredictionV2MainlineError("pre-draw registered artifact set changed")
        if stored["PredictionV2IssueManifest.v1"] != issue_manifest or stored["PredictionV2HistorySnapshotArtifact.v1"] != history_artifact:
            raise PredictionV2MainlineError("pre-draw source artifacts changed")
        if stored["PredictionV2LiveSchedulerPlan.v1"] != scheduler_plan:
            raise PredictionV2MainlineError("pre-draw scheduler plan changed")
        verify_artifact(
            stored["PredictionV2IssuePreDrawExecution.v1"],
            domain="dehps.prediction-v2.issue-predraw-execution.v1",
        )
        replay = replay_pre_draw(
            contract=load_shadow_contract(self.root_dir), history=history_from_artifact(history_artifact),
            expected_state=stored["PredictionV2StateArtifact.v1"],
            expected_pool=stored["PredictionV2ShadowPoolArtifact.v1"],
            expected_top100=stored["PredictionV2ShadowTop100Artifact.v1"],
            expected_report=stored["PredictionV2PreDrawReport.v1"],
        )
        envelope = build_notification_envelope(
            report=stored["PredictionV2PreDrawReport.v1"], replay_artifact=replay,
            report_kind="pre_draw",
        )
        parent_execution_digest = str(stored["research_os_mainline_execution"]["artifact_digest"])
        typed_replay = _typed_replay_artifact(
            kind="predraw",
            issue=issue,
            replay=replay,
            envelope=envelope,
            parent_execution_digest=parent_execution_digest,
        )
        children = (replay, envelope, typed_replay)
        execution = _execution_payload(
            task=task, execution_id=execution_id, control_plane_key=control_plane_key,
            git_commit=git_commit, child_payloads=children,
            downstream_consumer="prediction-v2-shadow-pre-draw-notification",
            replay_status="REPLAY_VERIFIED",
        )
        execution["parent_execution_id"] = parent_id
        execution["parent_execution_artifact_digest"] = parent_execution_digest
        execution = _reseal_execution(execution)
        path, replay_registrations = _persist_and_register(
            root_dir=self.root_dir, task=task, execution_id=execution_id,
            control_plane_key=control_plane_key, git_commit=git_commit,
            children=children, execution=execution,
        )
        return PredictionV2CapabilityResult(
            execution_artifact=execution, execution_artifact_path=path,
            registrations=replay_registrations, completion_facts=(issue_facts(issue)["pre_replay"],),
        )


class PredictionV2IssuePostDrawCapability:
    def __init__(self, *, repository: Any, root_dir: Path) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(self, *, control_plane_key: str, task: Task, execution_id: str, git_commit: str):
        _assert_control_plane(control_plane_key)
        issue_manifest, _, _ = _load_inputs(self.root_dir, task)
        issue = str(issue_manifest["issue"])
        keys = issue_task_keys(issue)
        _assert_task(task, expected_key=keys["post"], expected_capability=POST_CAPABILITY)
        _, pre_registrations = _completed_execution(self.repository, task_key=keys["pre"])
        pre_stored = _registered_by_type(self.root_dir, pre_registrations)
        draw = load_json_artifact(self.root_dir, str(task_contract(task)["actual_draw_path"]))
        draw = verify_artifact(draw, domain="dehps.prediction-v2.actual-draw-artifact.v1")
        if draw.get("issue") != issue or draw.get("sync_status") != "COMPLETED":
            raise PredictionV2MainlineError("actual draw identity/status mismatch")
        report = build_post_draw_report(
            pre_draw_report=pre_stored["PredictionV2PreDrawReport.v1"],
            actual_issue=issue, actual_red_numbers=draw["red_numbers"],
        )
        core_children = (draw, report)
        typed_execution = _typed_execution_artifact(
            kind="postdraw",
            issue=issue,
            task=task,
            execution_id=execution_id,
            child_payloads=core_children,
            historical_outcomes_read=True,
        )
        children = (*core_children, typed_execution)
        execution = _execution_payload(
            task=task, execution_id=execution_id, control_plane_key=control_plane_key,
            git_commit=git_commit, child_payloads=children,
            downstream_consumer=keys["post_replay"], replay_status="PENDING",
            historical_outcomes_read=True,
        )
        path, registrations = _persist_and_register(
            root_dir=self.root_dir, task=task, execution_id=execution_id,
            control_plane_key=control_plane_key, git_commit=git_commit,
            children=children, execution=execution,
        )
        return PredictionV2CapabilityResult(
            execution_artifact=execution, execution_artifact_path=path,
            registrations=registrations, completion_facts=(issue_facts(issue)["post_complete"],),
        )


class PredictionV2IssuePostDrawReplayCapability:
    def __init__(self, *, repository: Any, root_dir: Path) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(self, *, control_plane_key: str, task: Task, execution_id: str, git_commit: str):
        _assert_control_plane(control_plane_key)
        issue_manifest, _, _ = _load_inputs(self.root_dir, task)
        issue = str(issue_manifest["issue"])
        keys = issue_task_keys(issue)
        _assert_task(task, expected_key=keys["post_replay"], expected_capability=POST_REPLAY_CAPABILITY)
        parent_id, post_registrations = _completed_execution(self.repository, task_key=keys["post"])
        post_stored = _registered_by_type(self.root_dir, post_registrations)
        if set(post_stored) != {
            "PredictionV2ActualDrawArtifact.v1",
            "PredictionV2PostDrawReport.v1",
            "PredictionV2IssuePostDrawExecution.v1",
            "research_os_mainline_execution",
        }:
            raise PredictionV2MainlineError("post-draw registered artifact set changed")
        _, pre_registrations = _completed_execution(self.repository, task_key=keys["pre"])
        pre_stored = _registered_by_type(self.root_dir, pre_registrations)
        draw = post_stored["PredictionV2ActualDrawArtifact.v1"]
        report = post_stored["PredictionV2PostDrawReport.v1"]
        replay = replay_post_draw(
            pre_draw_report=pre_stored["PredictionV2PreDrawReport.v1"],
            actual_issue=issue, actual_red_numbers=draw["red_numbers"], expected_report=report,
        )
        envelope = build_notification_envelope(
            report=report, replay_artifact=replay, report_kind="post_draw",
        )
        parent_execution_digest = str(post_stored["research_os_mainline_execution"]["artifact_digest"])
        verify_artifact(
            post_stored["PredictionV2IssuePostDrawExecution.v1"],
            domain="dehps.prediction-v2.issue-postdraw-execution.v1",
        )
        typed_replay = _typed_replay_artifact(
            kind="postdraw",
            issue=issue,
            replay=replay,
            envelope=envelope,
            parent_execution_digest=parent_execution_digest,
        )
        children = (replay, envelope, typed_replay)
        execution = _execution_payload(
            task=task, execution_id=execution_id, control_plane_key=control_plane_key,
            git_commit=git_commit, child_payloads=children,
            downstream_consumer="prediction-v2-shadow-post-draw-notification",
            replay_status="REPLAY_VERIFIED", historical_outcomes_read=True,
        )
        execution["parent_execution_id"] = parent_id
        execution["parent_execution_artifact_digest"] = parent_execution_digest
        execution = _reseal_execution(execution)
        path, replay_registrations = _persist_and_register(
            root_dir=self.root_dir, task=task, execution_id=execution_id,
            control_plane_key=control_plane_key, git_commit=git_commit,
            children=children, execution=execution,
        )
        return PredictionV2CapabilityResult(
            execution_artifact=execution, execution_artifact_path=path,
            registrations=replay_registrations, completion_facts=(issue_facts(issue)["post_replay"],),
        )


def _reseal_execution(execution: Mapping[str, Any]) -> dict[str, Any]:
    from dehps.contracts import canonical_digest

    value = dict(execution)
    value["parent_digests"] = [
        *value.get("parent_digests", []),
        str(value["parent_execution_artifact_digest"]),
    ]
    value.pop("artifact_digest", None)
    value["artifact_digest"] = canonical_digest(
        value,
        domain="dehps.research-os.mainline-execution.v1",
    )
    return value
