from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.contracts import canonical_digest
from dehps.input_contracts.candidate_abi import candidate_unrank
from dehps.input_contracts.history_window import HistorySnapshotArtifact
from dehps.prediction.v2.activation_binding import (
    CUTOVER_CAPABILITY,
    CUTOVER_TASK_KEY,
    LIVE_ACTIVATION_COMPLETION_FACT,
    PredictionV2ActivationBindingError,
    build_live_activation_attestation,
)
from dehps.prediction.v2.contracts import (
    load_legacy_baseline,
    load_shadow_contract,
    seal_artifact,
)
from dehps.prediction.v2.generator import UNIVERSE, generate_shadow_pool
from dehps.prediction.v2.replay import replay_post_draw, replay_pre_draw
from dehps.prediction.v2.reports import build_post_draw_report, build_pre_draw_report
from dehps.prediction.v2.retirement import load_cutover_plan, scheduler_cutover_dry_run
from dehps.prediction.v2.state import encode_state
from dehps.research_os.mainline import integration_contract
from dehps.research_os.models import MainlineArtifactRegistration, Task

CONTROL_PLANE_KEY = "prediction-v2-shadow"
REFERENCE_TASK_KEY = "prediction-v2-shadow-reference-execution"
REFERENCE_CAPABILITY = "prediction_v2_shadow_reference_execution"
REPLAY_TASK_KEY = "prediction-v2-shadow-reference-replay"
REPLAY_CAPABILITY = "prediction_v2_shadow_reference_replay"
REFERENCE_COMPLETION_FACT = "prediction-v2-shadow:REFERENCE_EXECUTION:COMPLETED"
REPLAY_COMPLETION_FACT = "prediction-v2-shadow:REFERENCE_REPLAY:VERIFIED"
MAINLINE_EXECUTION_SCHEMA = "dehps-research-os-mainline-execution.v1"


class PredictionV2MainlineError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionV2CapabilityResult:
    execution_artifact: Mapping[str, Any]
    execution_artifact_path: Path
    registrations: tuple[MainlineArtifactRegistration, ...]
    completion_facts: tuple[str, ...] = ()
    additional_completed_task_keys: tuple[str, ...] = ()


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2MainlineError(f"cannot load artifact: {path}") from exc
    if not isinstance(value, dict):
        raise PredictionV2MainlineError(f"artifact must be an object: {path}")
    return value


def _persist_immutable(path: Path, payload: Mapping[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise PredictionV2MainlineError(f"immutable artifact collision: {path}")
        return
    atomic_write_text(path, encoded)


def build_reference_history() -> tuple[HistorySnapshotArtifact, tuple[int, ...]]:
    rows = [
        (
            f"2026{index:03d}",
            None,
            candidate_unrank(
                (index * 7_919 + 104_729) % UNIVERSE.cardinality,
                universe=UNIVERSE,
            ),
        )
        for index in range(1, 121)
    ]
    actual = candidate_unrank(
        (121 * 7_919 + 104_729) % UNIVERSE.cardinality,
        universe=UNIVERSE,
    )
    return HistorySnapshotArtifact.from_history(rows, source="prediction_v2_reference_fixture"), actual


def build_reference_children(root_dir: Path) -> tuple[dict[str, Any], ...]:
    contract = load_shadow_contract(root_dir)
    baseline = load_legacy_baseline(root_dir)
    cutover_plan = load_cutover_plan(root_dir)
    cutover_dry_run = scheduler_cutover_dry_run(root_dir=root_dir)
    history, actual = build_reference_history()
    history_artifact = seal_artifact(
        {
            "schema_version": "dehps-prediction-v2-reference-history-artifact.v1",
            "artifact_type": "PredictionV2ReferenceHistoryArtifact.v1",
            "history_snapshot": history.as_dict(include_records=True),
            "fixture_only": True,
            "historical_outcomes_read": False,
            "historical_evidence": "NOT_RUN",
            "parent_digests": [],
        },
        domain="dehps.prediction-v2.reference-history-artifact.v1",
    )
    state = encode_state(
        history,
        as_of_issue="2026120",
        target_issue="2026121",
    )
    pool, top100 = generate_shadow_pool(contract=contract, state=state)
    pre_draw = build_pre_draw_report(
        contract=contract,
        state=state,
        pool=pool,
        top100=top100,
    )
    post_draw = build_post_draw_report(
        pre_draw_report=pre_draw,
        actual_issue="2026121",
        actual_red_numbers=actual,
    )
    return (
        baseline,
        contract,
        cutover_plan,
        cutover_dry_run,
        history_artifact,
        state,
        pool,
        top100,
        pre_draw,
        post_draw,
    )


def _execution_payload(
    *,
    task: Task,
    execution_id: str,
    control_plane_key: str,
    git_commit: str,
    child_payloads: tuple[Mapping[str, Any], ...],
    downstream_consumer: str,
    replay_status: str,
    historical_outcomes_read: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": MAINLINE_EXECUTION_SCHEMA,
        "artifact_type": "research_os_mainline_execution",
        "execution_id": execution_id,
        "control_plane_key": control_plane_key,
        "goal_key": task.goal_key,
        "task_key": task.task_key,
        "task_digest": task.artifact_digest,
        "capability": task.requested_capability,
        "status": "COMPLETE",
        "completion_classification": "VALIDATED_IN_MAINLINE",
        "input_artifact_digests": list(task.input_artifact_digests),
        "child_artifact_digests": [str(item["artifact_digest"]) for item in child_payloads],
        "actual_fold_count": 0,
        "engineering_progress_before": 0,
        "engineering_progress_after": 100,
        "evidence_progress_before": 0,
        "evidence_progress_after": 0,
        "replay_status": replay_status,
        "shadow_only": True,
        "historical_outcomes_read": historical_outcomes_read,
        "historical_evidence": "NOT_RUN",
        "promotion_gate_opened": False,
        "production_candidate_created": False,
        "m4_state_changed": False,
        "downstream_consumer": downstream_consumer,
        "git_commit": git_commit,
        "working_tree_clean": True,
        "parent_digests": [
            *task.input_artifact_digests,
            *(str(item["artifact_digest"]) for item in child_payloads),
        ],
    }
    payload["artifact_digest"] = canonical_digest(
        payload,
        domain="dehps.research-os.mainline-execution.v1",
    )
    return payload


def _persist_and_register(
    *,
    root_dir: Path,
    task: Task,
    execution_id: str,
    control_plane_key: str,
    git_commit: str,
    children: tuple[Mapping[str, Any], ...],
    execution: Mapping[str, Any],
) -> tuple[Path, tuple[MainlineArtifactRegistration, ...]]:
    task_dir = root_dir / "runtime/research-os/prediction-v2-shadow/tasks" / task.task_key / execution_id
    stored: list[tuple[Path, Mapping[str, Any]]] = []
    for child in children:
        child_path = task_dir / "artifacts" / str(child["artifact_digest"]) / "artifact.json"
        _persist_immutable(child_path, child)
        stored.append((child_path, child))
    execution_path = task_dir / "execution.json"
    _persist_immutable(execution_path, execution)
    stored.append((execution_path, execution))
    registrations = tuple(
        MainlineArtifactRegistration(
            execution_id=execution_id,
            control_plane_key=control_plane_key,
            task_key=task.task_key,
            task_digest=task.artifact_digest,
            artifact_digest=str(payload["artifact_digest"]),
            artifact_type=str(payload["artifact_type"]),
            schema_version=str(payload["schema_version"]),
            artifact_path=str(path.relative_to(root_dir)),
            parent_digests=tuple(str(value) for value in payload.get("parent_digests", ())),
            git_commit=git_commit,
        )
        for path, payload in stored
    )
    return execution_path, registrations


class PredictionV2ReferenceCapability:
    def __init__(self, *, root_dir: Path) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> PredictionV2CapabilityResult:
        integration_contract(task)
        if control_plane_key != CONTROL_PLANE_KEY:
            raise PredictionV2MainlineError("Prediction v2 must use its isolated control-plane key")
        if task.task_key != REFERENCE_TASK_KEY or task.requested_capability != REFERENCE_CAPABILITY:
            raise PredictionV2MainlineError("reference capability received the wrong task")
        children = build_reference_children(self.root_dir)
        execution = _execution_payload(
            task=task,
            execution_id=execution_id,
            control_plane_key=control_plane_key,
            git_commit=git_commit,
            child_payloads=children,
            downstream_consumer=REPLAY_TASK_KEY,
            replay_status="PENDING",
        )
        execution_path, registrations = _persist_and_register(
            root_dir=self.root_dir,
            task=task,
            execution_id=execution_id,
            control_plane_key=control_plane_key,
            git_commit=git_commit,
            children=children,
            execution=execution,
        )
        return PredictionV2CapabilityResult(
            execution_artifact=execution,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(REFERENCE_COMPLETION_FACT,),
        )


class PredictionV2ReplayCapability:
    def __init__(self, *, repository: Any, root_dir: Path) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> PredictionV2CapabilityResult:
        integration_contract(task)
        if control_plane_key != CONTROL_PLANE_KEY:
            raise PredictionV2MainlineError("Prediction v2 must use its isolated control-plane key")
        if task.task_key != REPLAY_TASK_KEY or task.requested_capability != REPLAY_CAPABILITY:
            raise PredictionV2MainlineError("replay capability received the wrong task")
        events = self.repository.list_mainline_execution_events(
            control_plane_key=control_plane_key,
            task_key=REFERENCE_TASK_KEY,
        )
        completed = [item for item in events if item.get("event_type") == "completed"]
        if len(completed) != 1:
            raise PredictionV2MainlineError("replay requires exactly one reference completion")
        parent_execution_id = str(completed[0]["execution_id"])
        registrations = self.repository.list_mainline_artifacts(
            control_plane_key=control_plane_key,
            execution_id=parent_execution_id,
        )
        stored = {
            str(item["artifact_type"]): _load_object(self.root_dir / str(item["artifact_path"]))
            for item in registrations
        }
        expected_children = build_reference_children(self.root_dir)
        expected_by_type = {str(item["artifact_type"]): item for item in expected_children}
        if (
            len(registrations) != len(expected_by_type) + 1
            or set(stored) != {*expected_by_type, "research_os_mainline_execution"}
        ):
            raise PredictionV2MainlineError("reference artifact registry set changed")
        for artifact_type, expected in expected_by_type.items():
            if stored[artifact_type] != expected:
                raise PredictionV2MainlineError(f"reference artifact content changed: {artifact_type}")
        history, actual = build_reference_history()
        contract = expected_by_type["PredictionV2ShadowContract.v1"]
        state = expected_by_type["PredictionV2StateArtifact.v1"]
        pool = expected_by_type["PredictionV2ShadowPoolArtifact.v1"]
        top100 = expected_by_type["PredictionV2ShadowTop100Artifact.v1"]
        pre_draw = expected_by_type["PredictionV2PreDrawReport.v1"]
        post_draw = expected_by_type["PredictionV2PostDrawReport.v1"]
        pre_replay = replay_pre_draw(
            contract=contract,
            history=history,
            expected_state=state,
            expected_pool=pool,
            expected_top100=top100,
            expected_report=pre_draw,
        )
        post_replay = replay_post_draw(
            pre_draw_report=pre_draw,
            actual_issue="2026121",
            actual_red_numbers=actual,
            expected_report=post_draw,
        )
        children = (pre_replay, post_replay)
        execution = _execution_payload(
            task=task,
            execution_id=execution_id,
            control_plane_key=control_plane_key,
            git_commit=git_commit,
            child_payloads=children,
            downstream_consumer="prediction-v2-shadow-scheduler-cutover-operator",
            replay_status="REPLAY_VERIFIED",
        )
        execution["reference_execution_id"] = parent_execution_id
        execution["reference_execution_artifact_digest"] = stored[
            "research_os_mainline_execution"
        ]["artifact_digest"]
        execution["parent_digests"] = [
            *execution["parent_digests"],
            execution["reference_execution_artifact_digest"],
        ]
        # The additional bindings are part of the immutable execution identity.
        unsigned = dict(execution)
        unsigned.pop("artifact_digest")
        execution["artifact_digest"] = canonical_digest(
            unsigned,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path, replay_registrations = _persist_and_register(
            root_dir=self.root_dir,
            task=task,
            execution_id=execution_id,
            control_plane_key=control_plane_key,
            git_commit=git_commit,
            children=children,
            execution=execution,
        )
        return PredictionV2CapabilityResult(
            execution_artifact=execution,
            execution_artifact_path=execution_path,
            registrations=replay_registrations,
            completion_facts=(REPLAY_COMPLETION_FACT,),
        )


class PredictionV2LiveActivationCapability:
    def __init__(self, *, root_dir: Path) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> PredictionV2CapabilityResult:
        integration_contract(task)
        if control_plane_key != CONTROL_PLANE_KEY:
            raise PredictionV2MainlineError(
                "Prediction v2 must use its isolated control-plane key"
            )
        if (
            task.task_key != CUTOVER_TASK_KEY
            or task.requested_capability != CUTOVER_CAPABILITY
        ):
            raise PredictionV2MainlineError(
                "live activation capability received the wrong task"
            )
        contract = json.loads(task.metric_contract)
        try:
            attestation = build_live_activation_attestation(
                root_dir=self.root_dir,
                activation_path=str(contract["activation_path"]),
                completion_path=str(contract["operator_completion_path"]),
            )
        except (KeyError, PredictionV2ActivationBindingError) as exc:
            raise PredictionV2MainlineError(
                "live activation input contract is not verifiable"
            ) from exc
        required_inputs = {
            str(attestation["cutover_plan_digest"]),
            str(attestation["retirement_activation_digest"]),
            str(attestation["operator_completion_payload_digest"]),
        }
        if set(task.input_artifact_digests) != required_inputs:
            raise PredictionV2MainlineError(
                "live activation task input identities changed"
            )
        execution = _execution_payload(
            task=task,
            execution_id=execution_id,
            control_plane_key=control_plane_key,
            git_commit=git_commit,
            child_payloads=(attestation,),
            downstream_consumer="prediction-v2-shadow-issue-scheduler",
            replay_status="ACTIVATION_VERIFIED",
        )
        execution_path, registrations = _persist_and_register(
            root_dir=self.root_dir,
            task=task,
            execution_id=execution_id,
            control_plane_key=control_plane_key,
            git_commit=git_commit,
            children=(attestation,),
            execution=execution,
        )
        return PredictionV2CapabilityResult(
            execution_artifact=execution,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(LIVE_ACTIVATION_COMPLETION_FACT,),
        )


def build_prediction_v2_status(
    *,
    manifest: Any,
    snapshot: Any,
    execution: Mapping[str, Any] | None,
    dispatch_performed: bool,
) -> dict[str, Any]:
    states = {item.task_key: item.status.value for item in snapshot.resolutions}
    replay_verified = REPLAY_COMPLETION_FACT in manifest.facts.artifacts
    activation_verified = LIVE_ACTIVATION_COMPLETION_FACT in manifest.facts.artifacts
    return {
        "schema_version": "dehps-prediction-v2-shadow-status.v1",
        "control_plane_key": CONTROL_PLANE_KEY,
        "mode": "SHADOW_ONLY",
        "source_state": "MERGED",
        "capability_state": "VALIDATED_IN_MAINLINE" if replay_verified else "INTEGRATION_PENDING",
        "task_states": states,
        "next_ready_task": snapshot.ready_queue[0].task_key if snapshot.ready_queue else None,
        "reference_execution": None if execution is None else dict(execution),
        "replay_verified": replay_verified,
        "legacy_retirement_activation": (
            "VERIFIED" if activation_verified else "NOT_PUBLISHED"
        ),
        "legacy_compute_state": (
            "STOPPED_AND_DISABLED"
            if activation_verified
            else "UNCHANGED_UNTIL_OPERATOR_ACTIVATION"
        ),
        "live_activation_verified": activation_verified,
        "historical_evidence": "NOT_RUN",
        "evidence_progress_percent": 0,
        "promotion_gate_opened": False,
        "production_candidate_created": False,
        "m4_state_changed": False,
        "dispatch_performed": dispatch_performed,
    }
