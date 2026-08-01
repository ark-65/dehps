from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.calibration import (
    CALIBRATION_RUN_MANIFEST_DIGEST,
    load_calibration_manifest,
    run_p24_calibration,
)
from dehps.research_os.information_theory.calibration.contracts import (
    DECISION_POLICY_DIGEST as P24_DECISION_POLICY_DIGEST,
)
from dehps.research_os.information_theory.calibration.contracts import (
    METRIC_KERNEL_DIGEST as P24_METRIC_KERNEL_DIGEST,
)
from dehps.research_os.information_theory.calibration.contracts import (
    PREREGISTRATION_DIGEST as P24_PREREGISTRATION_DIGEST,
)
from dehps.research_os.information_theory.calibration.contracts import (
    SYNTHETIC_MANIFEST_DIGEST as P24_SYNTHETIC_MANIFEST_DIGEST,
)
from dehps.research_os.information_theory.calibration.contracts import (
    WALK_FORWARD_HARNESS_DIGEST as P24_WALK_FORWARD_HARNESS_DIGEST,
)
from dehps.research_os.information_theory.identifiability import (
    IDENTIFIABILITY_PREFLIGHT_MANIFEST_DIGEST,
    SUPERSEDED_RUN_ARCHIVE_DIGEST,
    load_identifiability_preflight_manifest,
    load_superseded_run_archive,
    run_identifiability_preflight,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    DESIGN_REPLAY_COMPLETION_FACT,
    GATE_REPLAY_FIXTURE_PATH,
    MEASUREMENT_CONTRACT_V2_DIGEST,
    MEASUREMENT_CONTRACT_V2_PATH,
    P261_MARGINAL_BINDING_CONTRACT_PATH,
    bind_p261_marginal_acceptance,
    build_branch_decision_replay_artifact,
    build_design_artifacts,
    build_design_replay_artifacts,
    load_gate_replay_fixture,
    load_measurement_contract_v2,
    load_p261_marginal_binding_contract,
)
from dehps.research_os.information_theory.measurement_system_v2.execution import (
    DESIGN_COMPLETION_FACT,
)
from dehps.research_os.information_theory.measurement_system_v2.replay import (
    P27_GATE_REPLAY_FACT,
    P261_RAW_REPLAY_FACT,
    build_p27_gate_replay_artifact,
    build_p261_raw_replay_artifact,
)
from dehps.research_os.information_theory.measurement_system_v2.runtime_audit import (
    RUNTIME_AUDIT_PLAN_PATH,
    RuntimeAuditObserver,
    build_benchmark_plan_artifact,
    build_equivalence_attestation,
    load_runtime_audit_plan,
)
from dehps.research_os.information_theory.measurement_validation import (
    MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
    REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
    assemble_completion,
    evaluate_automatic_gate,
    load_repaired_measurement_validation_manifest,
    locate_repaired_truth_artifacts,
    run_parallel_execution,
    verify_completion_replay,
)
from dehps.research_os.information_theory.measurement_validation.reference import (
    ReferenceReplicateEvaluator,
)
from dehps.research_os.information_theory.measurement_validation.schedule import (
    iter_replicates,
)
from dehps.research_os.information_theory.metrics import load_metric_kernel_manifest
from dehps.research_os.information_theory.progress import build_m4_status
from dehps.research_os.information_theory.repair.contracts import (
    MEASUREMENT_REPAIR_MANIFEST_DIGEST,
)
from dehps.research_os.information_theory.repair.execution import (
    REPAIRED_FACT,
    run_measurement_contract_repair,
)
from dehps.research_os.information_theory.resampling import (
    KERNEL_MANIFEST_DIGEST,
    load_resampling_manifest,
    run_p25_resampling,
)
from dehps.research_os.information_theory.resampling.contracts import (
    DECISION_POLICY_DIGEST as P25_DECISION_POLICY_DIGEST,
)
from dehps.research_os.information_theory.resampling.contracts import (
    METRIC_KERNEL_DIGEST as P25_METRIC_KERNEL_DIGEST,
)
from dehps.research_os.information_theory.resampling.contracts import (
    P24_COMPLETION_DIGEST as P25_P24_COMPLETION_DIGEST,
)
from dehps.research_os.information_theory.resampling.contracts import (
    PREREGISTRATION_DIGEST as P25_PREREGISTRATION_DIGEST,
)
from dehps.research_os.information_theory.resampling.contracts import (
    SYNTHETIC_MANIFEST_DIGEST as P25_SYNTHETIC_MANIFEST_DIGEST,
)
from dehps.research_os.information_theory.resampling.contracts import (
    WALK_FORWARD_HARNESS_DIGEST as P25_WALK_FORWARD_HARNESS_DIGEST,
)
from dehps.research_os.information_theory.synthetic import (
    load_synthetic_run_manifest,
)
from dehps.research_os.information_theory.walk_forward import (
    load_harness_manifest,
    load_synthetic_dataset,
    run_walk_forward,
)
from dehps.research_os.mainline import (
    integration_contract,
    mainline_completion_fact,
)
from dehps.prediction.v2.mainline import (
    CONTROL_PLANE_KEY as PREDICTION_V2_CONTROL_PLANE_KEY,
    REFERENCE_CAPABILITY as PREDICTION_V2_REFERENCE_CAPABILITY,
    REFERENCE_TASK_KEY as PREDICTION_V2_REFERENCE_TASK_KEY,
    REPLAY_CAPABILITY as PREDICTION_V2_REPLAY_CAPABILITY,
    REPLAY_TASK_KEY as PREDICTION_V2_REPLAY_TASK_KEY,
    PredictionV2ReferenceCapability,
    PredictionV2ReplayCapability,
    build_reference_children,
    build_reference_history,
    build_prediction_v2_status,
)
from dehps.prediction.v2.issue_mainline import (
    PredictionV2IssuePostDrawCapability,
    PredictionV2IssuePostDrawReplayCapability,
    PredictionV2IssuePreDrawCapability,
    PredictionV2IssuePreDrawReplayCapability,
)
from dehps.prediction.v2.issues import (
    POST_CAPABILITY as PREDICTION_V2_POST_CAPABILITY,
    POST_REPLAY_CAPABILITY as PREDICTION_V2_POST_REPLAY_CAPABILITY,
    PRE_CAPABILITY as PREDICTION_V2_PRE_CAPABILITY,
    PRE_REPLAY_CAPABILITY as PREDICTION_V2_PRE_REPLAY_CAPABILITY,
)
from dehps.prediction.v2.replay import replay_post_draw as replay_prediction_v2_post_draw
from dehps.prediction.v2.replay import replay_pre_draw as replay_prediction_v2_pre_draw
from dehps.research_os.models import (
    CompletionClassification,
    ControlPlaneManifest,
    MainlineArtifactRegistration,
    MainlineExecutionEvent,
    ResearchOSValidationError,
    Task,
    TaskStatus,
    stable_hash,
)
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.source_version import resolve_git_commit

P23_TASK_KEY = "m4-p2-walk-forward-probe-harness"
P23_CAPABILITY = "m4_p2_3_walk_forward_harness"
P23_PROBES = (
    "THEORETICAL_BASELINE",
    "REGULARIZED_LOGISTIC_REGRESSION",
)
P24_TASK_KEY = "m4-p2-injected-signal-calibration"
P24_CAPABILITY = "m4_p2_4_injected_signal_calibration"
P25_TASK_KEY = "m4-p2-resampling"
P25_CAPABILITY = "m4_p2_5_resampling_and_negative_controls"
P26_PREFLIGHT_TASK_KEY = "m4-p2-measurement-identifiability-preflight"
P26_PREFLIGHT_CAPABILITY = "m4_p2_6_identifiability_preflight"
P26_REPAIR_TASK_KEY = "m4-p2-repair-measurement-system"
P26_REPAIR_CAPABILITY = "m4_p2_measurement_system_repair"
P26_TASK_KEY = "m4-p2-false-positive-and-power-runs"
P26_CAPABILITY = "m4_p2_6_1_false_positive_and_power"
P27_TASK_KEY = "m4-p2-automatic-gate-and-report"
P27_CAPABILITY = "m4_p2_7_automatic_measurement_gate"
M4_V2_DESIGN_TASK_KEY = "m4-v2-measurement-contract-design"
M4_V2_DESIGN_CAPABILITY = "m4_v2_measurement_contract_design"
M4_V2_DESIGN_REPLAY_TASK_KEY = "m4-v2-measurement-contract-design-replay"
M4_V2_DESIGN_REPLAY_CAPABILITY = "m4_v2_measurement_contract_design_replay"
M4_V2_P261_RAW_REPLAY_TASK_KEY = "m4-v2-p2-6-1-raw-execution-replay"
M4_V2_P261_RAW_REPLAY_CAPABILITY = "m4_v2_p2_6_1_raw_execution_replay"
M4_V2_P27_GATE_REPLAY_TASK_KEY = "m4-v2-p2-7-measurement-gate-replay"
M4_V2_P27_GATE_REPLAY_CAPABILITY = "m4_v2_p2_7_measurement_gate_replay"
M4_V2_MARGINAL_BINDING_TASK_KEY = "m4-v2-p2-6-1-marginal-binding"
M4_V2_MARGINAL_BINDING_CAPABILITY = "m4_v2_p2_6_1_marginal_binding"
M4_V2_MARGINAL_DECISION_REPLAY_TASK_KEY = (
    "m4-v2-p2-6-1-marginal-decision-replay"
)
M4_V2_MARGINAL_DECISION_REPLAY_CAPABILITY = (
    "m4_v2_p2_6_1_marginal_decision_replay"
)
MARGINAL_BINDING_COMPLETION_FACT = (
    "m4-v2-marginal-measurement-acceptance-decision:BOUND"
)
MARGINAL_DECISION_REPLAY_FACT = (
    "m4-v2-branch-decision-replay:MARGINAL_STATIC:VERIFIED"
)
M4_P29_RUNTIME_AUDIT_TASK_KEY = "m4-p2-9-measurement-runtime-audit"
M4_P29_RUNTIME_AUDIT_CAPABILITY = "m4_p2_9_measurement_runtime_audit"
M4_P29_RUNTIME_AUDIT_COMPLETION_FACT = "m4-p2-9-runtime-audit:VERIFIED"
P2_UMBRELLA_TASK_KEY = "m4-p2-synthetic-measurement-validation"
MAINLINE_EXECUTION_SCHEMA = "dehps-research-os-mainline-execution.v1"
P26_EQUIVALENT_RESUME_ENV = "DEHPS_P26_EQUIVALENT_RESUME_FROM_COMMIT"
P26_EQUIVALENT_RESUME_REPORT_ENV = "DEHPS_P26_EQUIVALENT_RESUME_REPORT"
P26_EQUIVALENT_RESUME_REPORT = (
    "docs/experiments/2026-07-31-m4-p2-6-exact-runtime-acceleration.md"
)


class MainlineSupervisorError(RuntimeError):
    pass


@dataclass(frozen=True)
class CapabilityResult:
    execution_artifact: Mapping[str, Any]
    execution_artifact_path: Path
    registrations: tuple[MainlineArtifactRegistration, ...]
    completion_facts: tuple[str, ...] = ()
    additional_completed_task_keys: tuple[str, ...] = ()


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MainlineSupervisorError(f"artifact is not an object: {path}")
    return value


def _persist_immutable(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        if _load_object(path) != dict(payload):
            raise MainlineSupervisorError(f"immutable artifact collision: {path}")
        return
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


def _verify_v2_registered_artifacts(
    *,
    root_dir: Path,
    registrations: list[Mapping[str, Any]],
    expected_payloads: tuple[Mapping[str, Any], ...],
) -> None:
    expected_by_digest = {
        str(payload["artifact_digest"]): dict(payload)
        for payload in expected_payloads
    }
    registered_digests = {
        str(item.get("artifact_digest") or "") for item in registrations
    }
    if (
        len(expected_by_digest) != len(expected_payloads)
        or registered_digests != set(expected_by_digest)
    ):
        raise MainlineSupervisorError(
            "M4 Measurement Contract v2 registered artifact set changed"
        )
    for registration in registrations:
        digest = str(registration.get("artifact_digest") or "")
        path = root_dir / str(registration.get("artifact_path") or "")
        actual = _load_object(path)
        expected = expected_by_digest[digest]
        if (
            actual != expected
            or actual.get("artifact_digest") != digest
            or actual.get("artifact_type")
            != registration.get("artifact_type")
        ):
            raise MainlineSupervisorError(
                "M4 Measurement Contract v2 registered artifact content changed"
            )


def _artifact_digest(payload: Mapping[str, Any]) -> str:
    for field in (
        "artifact_digest",
        "fold_digest",
        "feature_view_digest",
        "state_digest",
    ):
        value = payload.get(field)
        if isinstance(value, str) and len(value) == 64:
            return value
    raise MainlineSupervisorError("registered artifact has no digest identity")


def _typed_artifact(
    payload: Mapping[str, Any],
    *,
    artifact_type: str,
    parent_digests: tuple[str, ...],
    domain: str,
) -> dict[str, Any]:
    artifact: dict[str, Any] = {
        "artifact_type": artifact_type,
        "artifact_digest": "",
        **dict(payload),
        "parent_digests": list(parent_digests),
    }
    identity = dict(artifact)
    identity.pop("artifact_digest")
    artifact["artifact_digest"] = canonical_digest(identity, domain=domain)
    return artifact


def _load_single_completed_execution(
    *,
    repository: PostgresResearchOSRepository,
    root_dir: Path,
    control_plane_key: str,
    task_key: str,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    events = repository.list_mainline_execution_events(
        control_plane_key=control_plane_key,
        task_key=task_key,
    )
    completed = [
        dict(event)
        for event in events
        if event.get("event_type") == "completed"
    ]
    if len(completed) != 1:
        raise MainlineSupervisorError(
            f"mainline parent requires one completed execution: {task_key}"
        )
    event = completed[0]
    summary = _event_payload(event)
    path = root_dir / str(summary["execution_artifact_path"])
    execution = _load_object(path)
    expected = canonical_digest(
        {key: value for key, value in execution.items() if key != "artifact_digest"},
        domain="dehps.research-os.mainline-execution.v1",
    )
    if (
        execution.get("artifact_digest") != expected
        or execution.get("task_key") != task_key
        or execution.get("execution_id") != event.get("execution_id")
    ):
        raise MainlineSupervisorError(
            f"completed execution identity changed: {task_key}"
        )
    registrations = [
        dict(item)
        for item in repository.list_mainline_artifacts(
            control_plane_key=control_plane_key,
            execution_id=str(execution["execution_id"]),
        )
    ]
    if len(registrations) != int(summary["registered_artifact_count"]):
        raise MainlineSupervisorError(
            f"completed execution registry changed: {task_key}"
        )
    if any(not (root_dir / str(item["artifact_path"])).is_file() for item in registrations):
        raise MainlineSupervisorError(
            f"completed execution artifact missing: {task_key}"
        )
    return event, execution, registrations


def _load_registered_type(
    *,
    root_dir: Path,
    registrations: list[dict[str, Any]],
    artifact_type: str,
) -> dict[str, Any]:
    matches = [
        item
        for item in registrations
        if item.get("artifact_type") == artifact_type
    ]
    if len(matches) != 1:
        raise MainlineSupervisorError(
            f"registered artifact type is not unique: {artifact_type}"
        )
    payload = _load_object(root_dir / str(matches[0]["artifact_path"]))
    if (
        payload.get("artifact_type") != artifact_type
        or payload.get("artifact_digest") != matches[0].get("artifact_digest")
    ):
        raise MainlineSupervisorError(
            f"registered artifact content identity changed: {artifact_type}"
        )
    return payload


def _persist_small_capability(
    *,
    root_dir: Path,
    owner: Any,
    control_plane_key: str,
    task: Task,
    execution_id: str,
    git_commit: str,
    child_name: str,
    child_filename: str,
    child_payload: Mapping[str, Any],
    completion_fact: str,
    downstream_consumer: str,
    extra_execution: Mapping[str, Any],
) -> CapabilityResult:
    task_dir = (
        root_dir
        / "runtime/research-os/mainline/tasks"
        / task.task_key
        / execution_id
    )
    child_path = (
        task_dir
        / "artifacts"
        / child_name
        / str(child_payload["artifact_digest"])
        / child_filename
    )
    _persist_immutable(child_path, child_payload)
    execution_payload: dict[str, Any] = {
        "schema_version": MAINLINE_EXECUTION_SCHEMA,
        "artifact_type": "research_os_mainline_execution",
        "artifact_digest": "",
        "execution_id": execution_id,
        "control_plane_key": control_plane_key,
        "goal_key": task.goal_key,
        "task_key": task.task_key,
        "task_digest": task.artifact_digest,
        "capability": task.requested_capability,
        "status": "COMPLETE",
        "completion_classification": "VALIDATED_IN_MAINLINE",
        "input_artifact_digests": list(task.input_artifact_digests),
        "completion_fact": completion_fact,
        "actual_fold_count": 0,
        "registered_artifact_count": 2,
        "historical_outcomes_read": False,
        "p2_6_1_partial_statistical_results_read": False,
        "evidence_created": False,
        "evidence_progress_before": 0,
        "evidence_progress_after": 0,
        "downstream_consumer": downstream_consumer,
        "production_impact": "none",
        "git_commit": git_commit,
        "working_tree_clean": True,
        **dict(extra_execution),
        "parent_digests": [
            *task.input_artifact_digests,
            str(child_payload["artifact_digest"]),
        ],
    }
    identity = dict(execution_payload)
    identity.pop("artifact_digest")
    execution_payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.research-os.mainline-execution.v1",
    )
    execution_path = task_dir / "execution.json"
    _persist_immutable(execution_path, execution_payload)
    registrations = P24InjectedSignalCalibrationCapability._registrations(
        owner,
        control_plane_key=control_plane_key,
        task=task,
        execution_id=execution_id,
        git_commit=git_commit,
        child_payloads=((child_path, child_payload),),
        execution_path=execution_path,
        execution_payload=execution_payload,
    )
    return CapabilityResult(
        execution_artifact=execution_payload,
        execution_artifact_path=execution_path,
        registrations=registrations,
        completion_facts=(completion_fact,),
    )


def _runtime_audit_child_identities(
    replicate_payload: Mapping[str, Any],
) -> list[dict[str, str]]:
    children = [
        {
            "artifact_type": f"probe_run:{probe_id}",
            "artifact_digest": str(digest),
        }
        for probe_id, digest in sorted(
            dict(replicate_payload["probe_run_digests"]).items()
        )
    ]
    for field in (
        "dataset_digest",
        "ordered_outer_checkpoint_digest",
        "ordered_settlement_digest",
        "checkpoint_journal_digest",
        "bootstrap_seed_set_digest",
        "permutation_seed_set_digest",
    ):
        children.append(
            {
                "artifact_type": field,
                "artifact_digest": str(replicate_payload[field]),
            }
        )
    return children


def _event_payload(event: Mapping[str, Any]) -> dict[str, Any]:
    raw = event.get("payload", ())
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, list):
        return {str(key): value for key, value in raw}
    return {}


class P23WalkForwardCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if task.task_key != P23_TASK_KEY or task.requested_capability != P23_CAPABILITY:
            raise MainlineSupervisorError("P2.3 capability received the wrong task")
        if len(task.input_artifact_digests) != 3:
            raise MainlineSupervisorError("P2.3 requires exactly three frozen input digests")
        dataset_digest, metric_digest, harness_digest = task.input_artifact_digests
        dataset_path = (
            self.root_dir
            / "runtime/research-os/information-theory/synthetic"
            / dataset_digest
            / "dataset.json"
        )
        if not dataset_path.is_file():
            raise MainlineSupervisorError(
                f"canonical P2.1 dataset artifact is missing: {dataset_digest}"
            )
        dataset = load_synthetic_dataset(dataset_path)
        if dataset.artifact_digest != dataset_digest:
            raise MainlineSupervisorError("located P2.1 dataset digest changed")

        metric_path = (
            self.root_dir
            / "configs/research-os/m4-information-theory-metric-kernel-v1.json"
        )
        metric_manifest = load_metric_kernel_manifest(metric_path)
        if metric_manifest.artifact_digest != metric_digest:
            raise MainlineSupervisorError("P2.2 Metric Kernel identity changed")

        harness_path = (
            self.root_dir
            / "configs/research-os/m4-information-theory-walk-forward-harness-v1.json"
        )
        harness = load_harness_manifest(harness_path)
        if harness.artifact_digest != harness_digest:
            raise MainlineSupervisorError("P2.3 harness identity changed")

        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        output_dir = task_dir / "artifacts"
        run_artifacts = [
            run_walk_forward(
                dataset=dataset,
                manifest=harness,
                probe_id=probe_id,
                output_dir=output_dir,
                git_commit=git_commit,
                working_tree_clean=True,
                dataset_path=dataset_path,
                manifest_path=harness_path,
                worker_count=1,
            )
            for probe_id in P23_PROBES
        ]

        artifact_paths = self._child_artifact_paths(
            output_dir=output_dir,
            run_artifacts=run_artifacts,
        )
        child_payloads = tuple(
            (path, _load_object(path)) for path in sorted(artifact_paths)
        )
        child_identities = tuple(
            sorted(
                {
                    (
                        _artifact_digest(payload),
                        str(payload.get("artifact_type") or "typed_artifact"),
                    )
                    for _, payload in child_payloads
                }
            )
        )
        actual_fold_count = sum(
            int(artifact["aggregate"]["fold_count"]) for artifact in run_artifacts
        )
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "run_digests": [str(item["run_digest"]) for item in run_artifacts],
            "run_artifact_digests": [
                str(item["artifact_digest"]) for item in run_artifacts
            ],
            "actual_fold_count": actual_fold_count,
            "registered_artifact_count": len(child_identities) + 1,
            "engineering_progress_before": 26,
            "engineering_progress_after": 30,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": "m4-p2-injected-signal-calibration",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "descriptive_only": True,
            "eligible_for_p2_gate": False,
            "production_impact": "none",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(item["artifact_digest"]) for item in run_artifacts),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)

        registrations = self._registrations(
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
        )

    @staticmethod
    def _child_artifact_paths(
        *,
        output_dir: Path,
        run_artifacts: list[Mapping[str, Any]],
    ) -> set[Path]:
        paths: set[Path] = set()
        for run in run_artifacts:
            paths.add(output_dir / "runs" / str(run["run_digest"]) / "run-artifact.json")
            for digest in run["fold_digests"]:
                fold_path = output_dir / "folds" / str(digest) / "fold-manifest.json"
                paths.add(fold_path)
                fold = _load_object(fold_path)
                paths.add(
                    output_dir
                    / "feature-views"
                    / str(fold["feature_view_digest"])
                    / "feature-view.json"
                )
            for digest in run["probe_state_digests"]:
                paths.add(
                    output_dir
                    / "probe-states"
                    / str(digest)
                    / "probe-state.json"
                )
            for digest in run["preprocessing_state_digests"]:
                paths.add(
                    output_dir
                    / "preprocessing-states"
                    / str(digest)
                    / "preprocessing-state.json"
                )
            for digest in run["prediction_checkpoint_digests"]:
                paths.add(
                    output_dir / "predictions" / str(digest) / "prediction.json"
                )
            for digest in run["settlement_digests"]:
                paths.add(
                    output_dir / "settlements" / str(digest) / "settlement.json"
                )
        missing = sorted(str(path) for path in paths if not path.is_file())
        if missing:
            raise MainlineSupervisorError(
                "P2.3 child artifact graph is incomplete: " + ", ".join(missing)
            )
        return paths

    def _registrations(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
        child_payloads: tuple[tuple[Path, Mapping[str, Any]], ...],
        execution_path: Path,
        execution_payload: Mapping[str, Any],
    ) -> tuple[MainlineArtifactRegistration, ...]:
        by_identity: dict[tuple[str, str], MainlineArtifactRegistration] = {}
        for path, payload in (
            *child_payloads,
            (execution_path, execution_payload),
        ):
            digest = _artifact_digest(payload)
            artifact_type = str(payload.get("artifact_type") or "typed_artifact")
            registration = MainlineArtifactRegistration(
                execution_id=execution_id,
                control_plane_key=control_plane_key,
                task_key=task.task_key,
                task_digest=task.artifact_digest,
                artifact_digest=digest,
                artifact_type=artifact_type,
                schema_version=str(payload.get("schema_version") or "unknown"),
                artifact_path=str(path.relative_to(self.root_dir)),
                parent_digests=tuple(
                    str(value) for value in payload.get("parent_digests", ())
                ),
                git_commit=git_commit,
            )
            by_identity[(digest, artifact_type)] = registration
        return tuple(by_identity[key] for key in sorted(by_identity))


class P24InjectedSignalCalibrationCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != P24_TASK_KEY
            or task.requested_capability != P24_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "P2.4 capability received the wrong task"
            )
        expected_inputs = (
            P24_PREREGISTRATION_DIGEST,
            P24_DECISION_POLICY_DIGEST,
            P24_SYNTHETIC_MANIFEST_DIGEST,
            P24_METRIC_KERNEL_DIGEST,
            P24_WALK_FORWARD_HARNESS_DIGEST,
            CALIBRATION_RUN_MANIFEST_DIGEST,
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "P2.4 requires all six frozen input identities in order"
            )
        calibration_manifest_path = (
            self.root_dir
            / "configs/research-os/"
            "m4-information-theory-p2-4-calibration-run-manifest-v1.json"
        )
        calibration_manifest = load_calibration_manifest(
            calibration_manifest_path
        )
        metric_manifest = load_metric_kernel_manifest(
            self.root_dir
            / "configs/research-os/"
            "m4-information-theory-metric-kernel-v1.json"
        )
        if metric_manifest.artifact_digest != P24_METRIC_KERNEL_DIGEST:
            raise MainlineSupervisorError("P2.2 Metric Kernel identity changed")
        harness_path = (
            self.root_dir
            / "configs/research-os/"
            "m4-information-theory-walk-forward-harness-v1.json"
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        output_dir = task_dir / "artifacts"
        run = run_p24_calibration(
            manifest=calibration_manifest,
            harness_path=harness_path,
            output_dir=output_dir,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        child_payloads = tuple(
            (path, _load_object(path)) for path in run.artifact_paths
        )
        child_identities = {
            (
                _artifact_digest(payload),
                str(payload.get("artifact_type") or "typed_artifact"),
            )
            for _, payload in child_payloads
        }
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "calibration_run_manifest_digest": (
                calibration_manifest.artifact_digest
            ),
            "calibration_run_artifact_digest": run.calibration_artifact[
                "artifact_digest"
            ],
            "completion_artifact_digest": run.completion_artifact[
                "artifact_digest"
            ],
            "truth_artifact_digests": [
                item["artifact_digest"] for item in run.truth_artifacts
            ],
            "truth_artifact_count": len(run.truth_artifacts),
            "actual_fold_count": run.actual_fold_count,
            "registered_artifact_count": len(child_identities) + 1,
            "engineering_progress_before": 30,
            "engineering_progress_after": 34,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": "m4-p2-resampling",
            "eligible_for_p2_5_input": True,
            "eligible_for_power_evidence": False,
            "formal_power_executed": False,
            "formal_false_positive_executed": False,
            "bootstrap_executed": False,
            "formal_permutation_executed": False,
            "real_history_used": False,
            "production_checkpoint_created": False,
            "git_commit": git_commit,
            "working_tree_clean": True,
            "descriptive_only": True,
            "eligible_for_p2_gate": False,
            "evidence_created": False,
            "production_impact": "none",
            "parent_digests": [
                *task.input_artifact_digests,
                run.calibration_artifact["artifact_digest"],
                run.completion_artifact["artifact_digest"],
                *(
                    item["artifact_digest"]
                    for item in run.truth_artifacts
                ),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = self._registrations(
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "P2.4 registered artifact count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
        )

    def _registrations(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
        child_payloads: tuple[tuple[Path, Mapping[str, Any]], ...],
        execution_path: Path,
        execution_payload: Mapping[str, Any],
    ) -> tuple[MainlineArtifactRegistration, ...]:
        by_identity: dict[
            tuple[str, str], MainlineArtifactRegistration
        ] = {}
        for path, payload in (
            *child_payloads,
            (execution_path, execution_payload),
        ):
            digest = _artifact_digest(payload)
            artifact_type = str(
                payload.get("artifact_type") or "typed_artifact"
            )
            registration = MainlineArtifactRegistration(
                execution_id=execution_id,
                control_plane_key=control_plane_key,
                task_key=task.task_key,
                task_digest=task.artifact_digest,
                artifact_digest=digest,
                artifact_type=artifact_type,
                schema_version=str(
                    payload.get("schema_version") or "unknown"
                ),
                artifact_path=str(path.relative_to(self.root_dir)),
                parent_digests=tuple(
                    str(value)
                    for value in payload.get("parent_digests", ())
                ),
                git_commit=str(payload.get("runtime_git_commit") or git_commit),
            )
            by_identity[(digest, artifact_type)] = registration
        return tuple(by_identity[key] for key in sorted(by_identity))


class P25ResamplingCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != P25_TASK_KEY
            or task.requested_capability != P25_CAPABILITY
        ):
            raise MainlineSupervisorError("P2.5 capability received the wrong task")
        expected_inputs = (
            P25_PREREGISTRATION_DIGEST,
            P25_DECISION_POLICY_DIGEST,
            P25_SYNTHETIC_MANIFEST_DIGEST,
            P25_METRIC_KERNEL_DIGEST,
            P25_WALK_FORWARD_HARNESS_DIGEST,
            P25_P24_COMPLETION_DIGEST,
            KERNEL_MANIFEST_DIGEST,
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "P2.5 requires all seven frozen input identities in order"
            )
        manifest = load_resampling_manifest(
            self.root_dir
            / "configs/research-os/"
            "m4-information-theory-p2-5-resampling-kernel-v1.json"
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        run = run_p25_resampling(
            manifest=manifest,
            root_dir=self.root_dir,
            output_dir=task_dir / "artifacts",
            execution_id=execution_id,
            git_commit=git_commit,
            working_tree_clean=True,
        )
        child_payloads = tuple(
            (path, _load_object(path)) for path in run.artifact_paths
        )
        child_identities = {
            (
                _artifact_digest(payload),
                str(payload.get("artifact_type") or "typed_artifact"),
            )
            for _, payload in child_payloads
        }
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "resampling_kernel_digest": manifest.artifact_digest,
            "resampling_run_digest": run.run_artifact["artifact_digest"],
            "resampling_completion_digest": run.completion_artifact[
                "artifact_digest"
            ],
            "child_replicate_digests": [
                item["artifact_digest"] for item in run.child_artifacts
            ],
            "aggregate_digests": [
                item["artifact_digest"] for item in run.aggregate_artifacts
            ],
            "replicate_count": run.replicate_count,
            "aggregate_count": len(run.aggregate_artifacts),
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_identities) + 1,
            "engineering_progress_before": 34,
            "engineering_progress_after": 37,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": "m4-p2-false-positive-and-power-runs",
            "eligible_for_formal_inference": False,
            "formal_power_executed": False,
            "formal_false_positive_executed": False,
            "mde_computed": False,
            "pe2_finalized": False,
            "real_history_used": False,
            "production_checkpoint_created": False,
            "git_commit": git_commit,
            "working_tree_clean": True,
            "descriptive_only": True,
            "eligible_for_p2_gate": False,
            "evidence_created": False,
            "production_impact": "none",
            "parent_digests": [
                *task.input_artifact_digests,
                run.run_artifact["artifact_digest"],
                run.completion_artifact["artifact_digest"],
                *(item["artifact_digest"] for item in run.aggregate_artifacts),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity, domain="dehps.research-os.mainline-execution.v1"
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError("P2.5 registered artifact count changed")
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
        )


class P26IdentifiabilityPreflightCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != P26_PREFLIGHT_TASK_KEY
            or task.requested_capability != P26_PREFLIGHT_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "P2.6 identifiability preflight received the wrong task"
            )
        expected_inputs = (
            P25_P24_COMPLETION_DIGEST,
            P25_METRIC_KERNEL_DIGEST,
            P25_WALK_FORWARD_HARNESS_DIGEST,
            "38bfbb983f65e4d800cb3e177fc6bbb65ac13a38496ab8ffdd9afdea10897134",
            MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
            SUPERSEDED_RUN_ARCHIVE_DIGEST,
            IDENTIFIABILITY_PREFLIGHT_MANIFEST_DIGEST,
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "P2.6 identifiability preflight requires all seven frozen "
                "input identities in order"
            )
        manifest = load_identifiability_preflight_manifest(
            self.root_dir
            / "configs/research-os/"
            "m4-information-theory-p2-6-identifiability-preflight-v1.json"
        )
        archive = load_superseded_run_archive(
            self.root_dir
            / "configs/research-os/"
            "m4-information-theory-p2-6-superseded-run-archive-v1.json"
        )
        if archive["artifact_digest"] != SUPERSEDED_RUN_ARCHIVE_DIGEST:
            raise MainlineSupervisorError(
                "P2.6 superseded run archive identity changed"
            )
        run = run_identifiability_preflight(
            manifest=manifest,
            root_dir=self.root_dir,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        report_path = task_dir / "artifacts/preflight-report.json"
        _persist_immutable(report_path, run.report)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "identifiability_preflight_manifest_digest": (
                manifest.artifact_digest
            ),
            "identifiability_preflight_report_digest": (
                run.report["artifact_digest"]
            ),
            "superseded_run_archive_digest": (
                archive["artifact_digest"]
            ),
            "decision": run.report["decision"],
            "decision_fact": run.decision_fact,
            "failed_requirements": run.report["failed_classifications"],
            "scenario_count": run.report["scenario_count"],
            "actual_fold_count": 0,
            "registered_artifact_count": 2,
            "engineering_progress_before": 37,
            "engineering_progress_after": 38,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": "m4-p2-repair-measurement-system",
            "p2_6_partial_statistical_results_inspected": False,
            "old_p2_6_execution_resumable": False,
            "eligible_for_formal_inference": False,
            "eligible_for_p2_gate": False,
            "evidence_created": False,
            "production_impact": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "DETERMINISTIC",
            "parent_digests": [
                *task.input_artifact_digests,
                run.report["artifact_digest"],
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=((report_path, run.report),),
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError(
                "P2.6 identifiability preflight registered artifact count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(run.decision_fact,),
        )


class P26MeasurementSystemRepairCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != P26_REPAIR_TASK_KEY
            or task.requested_capability != P26_REPAIR_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "P2 measurement repair received the wrong task"
            )
        expected_inputs = (
            "79ba9b17b0e620e2a06e5fcfe96603351843d7e17510a3ca1ae5a9a1eba7986a",
            SUPERSEDED_RUN_ARCHIVE_DIGEST,
            MEASUREMENT_REPAIR_MANIFEST_DIGEST,
            REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
            "1a76f46d7a47a134c1688657749bc040290f65a03dbc7c860e38144e02005981",
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "P2 measurement repair requires all five frozen repair "
                "identities in order"
            )
        run = run_measurement_contract_repair(
            root_dir=self.root_dir,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        development_path = (
            task_dir
            / "artifacts/development-selection"
            / str(run.development_selection["artifact_digest"])
            / "selection.json"
        )
        _persist_immutable(development_path, run.development_selection)
        truth_payloads: list[tuple[Path, Mapping[str, Any]]] = []
        for truth in run.truth_artifacts:
            path = (
                task_dir
                / "artifacts/truth"
                / str(truth["artifact_digest"])
                / "truth.json"
            )
            _persist_immutable(path, truth)
            truth_payloads.append((path, truth))
        confirmation_path = (
            task_dir
            / "artifacts/identifiability"
            / str(run.identifiability_confirmation["artifact_digest"])
            / "confirmation.json"
        )
        _persist_immutable(
            confirmation_path,
            run.identifiability_confirmation,
        )
        completion_path = (
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json"
        )
        _persist_immutable(completion_path, run.completion)
        child_payloads = (
            (development_path, run.development_selection),
            *truth_payloads,
            (confirmation_path, run.identifiability_confirmation),
            (completion_path, run.completion),
        )
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "measurement_repair_manifest_digest": (
                run.manifest.artifact_digest
            ),
            "repaired_measurement_validation_manifest_digest": (
                REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST
            ),
            "development_selection_artifact_digest": (
                run.development_selection["artifact_digest"]
            ),
            "truth_artifact_digests": [
                item["artifact_digest"] for item in run.truth_artifacts
            ],
            "identifiability_confirmation_digest": (
                run.identifiability_confirmation["artifact_digest"]
            ),
            "completion_artifact_digest": run.completion[
                "artifact_digest"
            ],
            "completion_fact": REPAIRED_FACT,
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "engineering_progress_before": 38,
            "engineering_progress_after": 40,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "outer_fold_fit_count_before": 46,
            "outer_fold_fit_count_after": 4,
            "inner_model_selection_per_outer_fold": 0,
            "formal_power_target_count": 8,
            "joint_only_negative_control_count": 3,
            "feasibility_sentinel_count": 1,
            "downstream_consumer": P26_TASK_KEY,
            "old_p2_6_partial_statistical_results_inspected": False,
            "old_p2_6_execution_resumable": False,
            "eligible_for_formal_inference": False,
            "evidence_created": False,
            "production_impact": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "DETERMINISTIC",
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload[
            "registered_artifact_count"
        ]:
            raise MainlineSupervisorError(
                "P2 measurement repair registered artifact count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(REPAIRED_FACT,),
        )


class M4MeasurementContractV2DesignCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != M4_V2_DESIGN_TASK_KEY
            or task.requested_capability != M4_V2_DESIGN_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 Measurement Contract v2 design received the wrong task"
            )
        expected_inputs = (
            MEASUREMENT_CONTRACT_V2_DIGEST,
            "ae4e741cfc55547785ca9cf57b5b49f37a3d8c4f2bd53daeff9228982f797a69",
            "56b9d0a62d43d167069e5222c7095383c9c5106bb3361b0b1def75cf2b6c86a2",
            "177a3d591b7557a4231a276bfb007f0d42a94d942824403f5376f94fe904d2ca",
            MEASUREMENT_REPAIR_MANIFEST_DIGEST,
            REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "M4 v2 design requires the six frozen source-only identities"
            )
        contract = load_measurement_contract_v2(
            self.root_dir / MEASUREMENT_CONTRACT_V2_PATH
        )
        run = build_design_artifacts(
            contract,
            execution_id=execution_id,
            git_commit=git_commit,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        child_paths = (
            task_dir
            / "artifacts/estimand-contract"
            / str(run.estimand_contract["artifact_digest"])
            / "contract.json",
            task_dir
            / "artifacts/mechanism-role-contract"
            / str(run.mechanism_role_contract["artifact_digest"])
            / "contract.json",
            task_dir
            / "artifacts/gate-compiler-contract"
            / str(run.gate_compiler_contract["artifact_digest"])
            / "contract.json",
            task_dir
            / "artifacts/completion"
            / str(run.completion["artifact_digest"])
            / "completion.json",
        )
        child_payloads = tuple(zip(child_paths, run.artifacts, strict=True))
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "measurement_contract_v2_digest": contract.artifact_digest,
            "estimand_contract_digest": run.estimand_contract[
                "artifact_digest"
            ],
            "mechanism_role_contract_digest": run.mechanism_role_contract[
                "artifact_digest"
            ],
            "gate_compiler_contract_digest": run.gate_compiler_contract[
                "artifact_digest"
            ],
            "completion_artifact_digest": run.completion["artifact_digest"],
            "completion_fact": DESIGN_COMPLETION_FACT,
            "actual_fold_count": 0,
            "registered_artifact_count": len(child_payloads) + 1,
            "formal_branch_runs_executed": 0,
            "historical_outcomes_read": False,
            "p2_6_1_partial_statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": (
                "m4-v2-branch-identifiability-preflight-design"
            ),
            "production_impact": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "DETERMINISTIC",
            "parent_digests": [
                *task.input_artifact_digests,
                *(
                    str(payload["artifact_digest"])
                    for _, payload in child_payloads
                ),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload[
            "registered_artifact_count"
        ]:
            raise MainlineSupervisorError(
                "M4 v2 design registered artifact count changed"
            )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(DESIGN_COMPLETION_FACT,),
        )


class M4MeasurementContractV2DesignReplayCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != M4_V2_DESIGN_REPLAY_TASK_KEY
            or task.requested_capability != M4_V2_DESIGN_REPLAY_CAPABILITY
        ):
            raise MainlineSupervisorError(
                "M4 Measurement Contract v2 design replay received the wrong task"
            )
        fixture = load_gate_replay_fixture(
            self.root_dir / GATE_REPLAY_FIXTURE_PATH
        )
        if task.input_artifact_digests != (
            MEASUREMENT_CONTRACT_V2_DIGEST,
            fixture.artifact_digest,
        ):
            raise MainlineSupervisorError(
                "M4 v2 design replay source identities changed"
            )
        events = self.repository.list_mainline_execution_events(
            control_plane_key=control_plane_key,
            task_key=M4_V2_DESIGN_TASK_KEY,
        )
        completed = [
            event for event in events if event.get("event_type") == "completed"
        ]
        if len(completed) != 1:
            raise MainlineSupervisorError(
                "M4 v2 design replay requires one completed design execution"
            )
        parent_event = completed[0]
        summary = _event_payload(parent_event)
        parent_path = self.root_dir / str(summary["execution_artifact_path"])
        parent_execution = _load_object(parent_path)
        expected_parent_digest = canonical_digest(
            {
                key: value
                for key, value in parent_execution.items()
                if key != "artifact_digest"
            },
            domain="dehps.research-os.mainline-execution.v1",
        )
        if (
            parent_execution.get("artifact_digest") != expected_parent_digest
            or parent_execution.get("task_key") != M4_V2_DESIGN_TASK_KEY
            or parent_execution.get("execution_id")
            != parent_event.get("execution_id")
        ):
            raise MainlineSupervisorError(
                "M4 v2 design replay parent execution identity changed"
            )
        parent_registrations = list(
            self.repository.list_mainline_artifacts(
                control_plane_key=control_plane_key,
                execution_id=str(parent_event["execution_id"]),
            )
        )
        contract = load_measurement_contract_v2(
            self.root_dir / MEASUREMENT_CONTRACT_V2_PATH
        )
        reconstructed = build_design_artifacts(
            contract,
            execution_id=str(parent_execution["execution_id"]),
            git_commit=str(parent_execution["git_commit"]),
        )
        _verify_v2_registered_artifacts(
            root_dir=self.root_dir,
            registrations=parent_registrations,
            expected_payloads=(*reconstructed.artifacts, parent_execution),
        )
        replay = build_design_replay_artifacts(
            contract,
            fixture=fixture,
            design_execution=parent_execution,
            design_child_digests=[
                str(item["artifact_digest"])
                for item in parent_registrations
                if item.get("artifact_type")
                != "research_os_mainline_execution"
            ],
            registration_payloads=parent_registrations,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        child_paths = (
            task_dir
            / "artifacts/measurement-contract-replay"
            / str(replay.measurement_contract_replay["artifact_digest"])
            / "replay.json",
            task_dir
            / "artifacts/gate-compiler-replay"
            / str(replay.gate_compiler_replay["artifact_digest"])
            / "replay.json",
        )
        child_payloads = tuple(zip(child_paths, replay.artifacts, strict=True))
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "measurement_contract_v2_digest": contract.artifact_digest,
            "design_execution_id": parent_execution["execution_id"],
            "design_execution_artifact_digest": parent_execution[
                "artifact_digest"
            ],
            "measurement_contract_replay_digest": (
                replay.measurement_contract_replay["artifact_digest"]
            ),
            "gate_compiler_replay_digest": replay.gate_compiler_replay[
                "artifact_digest"
            ],
            "completion_fact": DESIGN_REPLAY_COMPLETION_FACT,
            "actual_fold_count": 0,
            "registered_artifact_count": 3,
            "formal_branch_runs_executed": 0,
            "historical_outcomes_read": False,
            "p2_6_1_partial_statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": (
                "m4-v2-branch-identifiability-preflight-design"
            ),
            "production_impact": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "replay_status": "REPLAY_VERIFIED",
            "parent_digests": [
                *task.input_artifact_digests,
                str(parent_execution["artifact_digest"]),
                *(str(item["artifact_digest"]) for item in replay.artifacts),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(DESIGN_REPLAY_COMPLETION_FACT,),
        )


class M4P261RawExecutionReplayCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != M4_V2_P261_RAW_REPLAY_TASK_KEY
            or task.requested_capability != M4_V2_P261_RAW_REPLAY_CAPABILITY
        ):
            raise MainlineSupervisorError("P2.6.1 raw replay received the wrong task")
        contract = load_p261_marginal_binding_contract(
            self.root_dir / P261_MARGINAL_BINDING_CONTRACT_PATH
        )
        sources = contract.payload["source_identities"]
        if task.input_artifact_digests != (
            contract.artifact_digest,
            str(sources["p2_6_1_measurement_validation_manifest_digest"]),
        ):
            raise MainlineSupervisorError("P2.6.1 raw replay inputs changed")
        event, parent, registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=P26_TASK_KEY,
        )
        manifest = load_repaired_measurement_validation_manifest(
            self.root_dir
            / "configs/research-os/m4-information-theory-p2-6-1-measurement-validation-v1.json"
        )
        synthetic = load_synthetic_run_manifest(
            self.root_dir
            / "configs/research-os/m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
        )
        replay = verify_completion_replay(
            manifest=manifest,
            synthetic=synthetic,
            parent_execution_id=str(parent["execution_id"]),
            output_dir=(
                self.root_dir
                / "runtime/research-os/mainline/tasks"
                / P26_TASK_KEY
                / str(parent["execution_id"])
                / "artifacts"
            ),
            git_commit=str(parent["git_commit"]),
            expected_completion_digest=str(parent["completion_artifact_digest"]),
        )
        if replay.get("status") != "REPLAY_VERIFIED":
            raise MainlineSupervisorError("P2.6.1 raw deterministic replay failed")
        raw = build_p261_raw_replay_artifact(
            execution=parent,
            completion_event=event,
            registrations=registrations,
            expected_task_key=str(sources["p2_6_1_task_key"]),
            expected_task_digest=str(sources["p2_6_1_task_digest"]),
            expected_execution_id=str(sources["p2_6_1_execution_id"]),
            expected_manifest_digest=str(
                sources["p2_6_1_measurement_validation_manifest_digest"]
            ),
        )
        replay_artifact = _typed_artifact(
            raw,
            artifact_type="P261RawExecutionReplayArtifact",
            parent_digests=(
                contract.artifact_digest,
                str(parent["artifact_digest"]),
                str(parent["completion_artifact_digest"]),
            ),
            domain="dehps.m4.p261-raw-execution-replay-artifact.v1",
        )
        return _persist_small_capability(
            root_dir=self.root_dir,
            owner=self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_name="raw-execution-replay",
            child_filename="replay.json",
            child_payload=replay_artifact,
            completion_fact=P261_RAW_REPLAY_FACT,
            downstream_consumer=M4_V2_P27_GATE_REPLAY_TASK_KEY,
            extra_execution={
                "p2_6_1_execution_id": parent["execution_id"],
                "p2_6_1_execution_artifact_digest": parent["artifact_digest"],
                "raw_replay_artifact_digest": replay_artifact["artifact_digest"],
                "replay_status": "REPLAY_VERIFIED",
            },
        )


class M4P27GateReplayCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != M4_V2_P27_GATE_REPLAY_TASK_KEY
            or task.requested_capability != M4_V2_P27_GATE_REPLAY_CAPABILITY
        ):
            raise MainlineSupervisorError("P2.7 gate replay received the wrong task")
        contract = load_p261_marginal_binding_contract(
            self.root_dir / P261_MARGINAL_BINDING_CONTRACT_PATH
        )
        if task.input_artifact_digests != (contract.artifact_digest,):
            raise MainlineSupervisorError("P2.7 gate replay inputs changed")
        _, parent, _ = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=P27_TASK_KEY,
        )
        replay = ResearchEvidenceSupervisor(
            repository=self.repository,
            control_plane_key=control_plane_key,
            root_dir=self.root_dir,
            git_commit=git_commit,
            require_clean_tree=False,
        ).replay(task_key=P27_TASK_KEY, execution_id=str(parent["execution_id"]))
        gate = build_p27_gate_replay_artifact(
            execution=parent,
            replay=replay,
            parent_p261_execution_id=str(
                contract.payload["source_identities"]["p2_6_1_execution_id"]
            ),
        )
        gate_artifact = _typed_artifact(
            gate,
            artifact_type="P27MeasurementGateReplayArtifact",
            parent_digests=(
                contract.artifact_digest,
                str(parent["artifact_digest"]),
                str(parent["automatic_gate_digest"]),
            ),
            domain="dehps.m4.p27-measurement-gate-replay-artifact.v1",
        )
        return _persist_small_capability(
            root_dir=self.root_dir,
            owner=self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_name="measurement-gate-replay",
            child_filename="replay.json",
            child_payload=gate_artifact,
            completion_fact=P27_GATE_REPLAY_FACT,
            downstream_consumer=M4_V2_MARGINAL_BINDING_TASK_KEY,
            extra_execution={
                "p2_7_execution_id": parent["execution_id"],
                "p2_7_execution_artifact_digest": parent["artifact_digest"],
                "gate_replay_artifact_digest": gate_artifact["artifact_digest"],
                "replay_status": "REPLAY_VERIFIED",
            },
        )


class M4P261MarginalBindingCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != M4_V2_MARGINAL_BINDING_TASK_KEY
            or task.requested_capability != M4_V2_MARGINAL_BINDING_CAPABILITY
        ):
            raise MainlineSupervisorError("P2.6.1 Marginal binding received the wrong task")
        contract = load_p261_marginal_binding_contract(
            self.root_dir / P261_MARGINAL_BINDING_CONTRACT_PATH
        )
        if task.input_artifact_digests != (contract.artifact_digest,):
            raise MainlineSupervisorError("P2.6.1 Marginal binding inputs changed")
        _, raw_parent, raw_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=M4_V2_P261_RAW_REPLAY_TASK_KEY,
        )
        _, gate_parent, gate_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=M4_V2_P27_GATE_REPLAY_TASK_KEY,
        )
        raw = _load_registered_type(
            root_dir=self.root_dir,
            registrations=raw_registrations,
            artifact_type="P261RawExecutionReplayArtifact",
        )
        gate = _load_registered_type(
            root_dir=self.root_dir,
            registrations=gate_registrations,
            artifact_type="P27MeasurementGateReplayArtifact",
        )
        raw_allowed = {
            key: raw[key]
            for key in contract.payload["input_allowlist"]["p2_6_1_raw_replay"]
            if key in raw
        }
        gate_allowed = {
            key: gate[key]
            for key in contract.payload["input_allowlist"]["p2_7_gate_replay"]
            if key in gate
        }
        decision = bind_p261_marginal_acceptance(
            contract,
            raw_replay=raw_allowed,
            gate_replay=gate_allowed,
        )
        return _persist_small_capability(
            root_dir=self.root_dir,
            owner=self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_name="marginal-measurement-acceptance-decision",
            child_filename="decision.json",
            child_payload=decision,
            completion_fact=MARGINAL_BINDING_COMPLETION_FACT,
            downstream_consumer=M4_V2_MARGINAL_DECISION_REPLAY_TASK_KEY,
            extra_execution={
                "binding_contract_digest": contract.artifact_digest,
                "raw_replay_execution_artifact_digest": raw_parent["artifact_digest"],
                "gate_replay_execution_artifact_digest": gate_parent["artifact_digest"],
                "marginal_decision_artifact_digest": decision["artifact_digest"],
                "measurement_health": decision["measurement_health"],
                "historical_evidence": "NOT_RUN",
            },
        )


class M4P261MarginalDecisionReplayCapability:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        root_dir: Path = ROOT_DIR,
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != M4_V2_MARGINAL_DECISION_REPLAY_TASK_KEY
            or task.requested_capability
            != M4_V2_MARGINAL_DECISION_REPLAY_CAPABILITY
        ):
            raise MainlineSupervisorError("Marginal decision replay received the wrong task")
        contract = load_p261_marginal_binding_contract(
            self.root_dir / P261_MARGINAL_BINDING_CONTRACT_PATH
        )
        if task.input_artifact_digests != (contract.artifact_digest,):
            raise MainlineSupervisorError("Marginal decision replay inputs changed")
        _, _, binding_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=M4_V2_MARGINAL_BINDING_TASK_KEY,
        )
        decision = _load_registered_type(
            root_dir=self.root_dir,
            registrations=binding_registrations,
            artifact_type="marginal_measurement_acceptance_decision",
        )
        _, _, raw_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=M4_V2_P261_RAW_REPLAY_TASK_KEY,
        )
        _, _, gate_registrations = _load_single_completed_execution(
            repository=self.repository,
            root_dir=self.root_dir,
            control_plane_key=control_plane_key,
            task_key=M4_V2_P27_GATE_REPLAY_TASK_KEY,
        )
        raw = _load_registered_type(
            root_dir=self.root_dir,
            registrations=raw_registrations,
            artifact_type="P261RawExecutionReplayArtifact",
        )
        gate = _load_registered_type(
            root_dir=self.root_dir,
            registrations=gate_registrations,
            artifact_type="P27MeasurementGateReplayArtifact",
        )
        reconstructed = bind_p261_marginal_acceptance(
            contract,
            raw_replay={
                key: raw[key]
                for key in contract.payload["input_allowlist"]["p2_6_1_raw_replay"]
                if key in raw
            },
            gate_replay={
                key: gate[key]
                for key in contract.payload["input_allowlist"]["p2_7_gate_replay"]
                if key in gate
            },
        )
        replay_artifact = build_branch_decision_replay_artifact(
            decision=decision,
            reconstructed_decision=reconstructed,
        )
        return _persist_small_capability(
            root_dir=self.root_dir,
            owner=self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_name="branch-decision-replay",
            child_filename="replay.json",
            child_payload=replay_artifact,
            completion_fact=MARGINAL_DECISION_REPLAY_FACT,
            downstream_consumer="m4-v2-marginal-historical-measurement",
            extra_execution={
                "binding_contract_digest": contract.artifact_digest,
                "marginal_decision_artifact_digest": decision["artifact_digest"],
                "branch_decision_replay_artifact_digest": replay_artifact[
                    "artifact_digest"
                ],
                "measurement_health": decision["measurement_health"],
                "historical_evidence": "NOT_RUN",
                "replay_status": "REPLAY_VERIFIED",
            },
        )


class M4P29MeasurementRuntimeAuditCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if (
            task.task_key != M4_P29_RUNTIME_AUDIT_TASK_KEY
            or task.requested_capability != M4_P29_RUNTIME_AUDIT_CAPABILITY
        ):
            raise MainlineSupervisorError("M4-P2.9 runtime audit received the wrong task")
        plan = load_runtime_audit_plan(self.root_dir / RUNTIME_AUDIT_PLAN_PATH)
        if task.input_artifact_digests != (str(plan["artifact_digest"]),):
            raise MainlineSupervisorError("M4-P2.9 runtime audit plan changed")
        manifest = load_repaired_measurement_validation_manifest(
            self.root_dir
            / "configs/research-os/m4-information-theory-p2-6-1-measurement-validation-v1.json"
        )
        synthetic = load_synthetic_run_manifest(
            self.root_dir
            / "configs/research-os/m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
        )
        truth_digests = tuple(
            str(item["artifact_digest"])
            for item in manifest.payload["truth_artifacts"]
        )
        truths = locate_repaired_truth_artifacts(
            self.root_dir,
            required_digests=truth_digests,
            repair_manifest_digest=MEASUREMENT_REPAIR_MANIFEST_DIGEST,
        )
        replicate = next(
            iter_replicates(
                manifest=manifest,
                synthetic=synthetic,
                parent_execution_id=execution_id,
            )
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )

        def evaluator(
            output_dir: Path,
            observer: RuntimeAuditObserver | None = None,
        ) -> ReferenceReplicateEvaluator:
            return ReferenceReplicateEvaluator.from_paths(
                manifest=manifest,
                synthetic=synthetic,
                preregistration_path=(
                    self.root_dir
                    / "configs/research-os/m4-information-theory-preregistration-v1.0.3.json"
                ),
                walk_forward_harness_path=(
                    self.root_dir
                    / "configs/research-os/m4-information-theory-walk-forward-harness-v1.json"
                ),
                resampling_path=(
                    self.root_dir
                    / "configs/research-os/m4-information-theory-p2-5-resampling-kernel-v1.json"
                ),
                truth_by_scenario=truths,
                git_commit=git_commit,
                output_dir=output_dir,
                audit_observer=observer,
            )

        reference_payload = evaluator(task_dir / "reference-work").evaluate(replicate)
        observer = RuntimeAuditObserver(enabled=True)
        audited_payload = evaluator(
            task_dir / "audited-work",
            observer,
        ).evaluate(replicate)
        benchmark_plan = build_benchmark_plan_artifact(plan)
        observation = observer.observation(
            plan_digest=str(benchmark_plan["artifact_digest"]),
            execution_id=execution_id,
            git_commit=git_commit,
        )
        reference_children = _runtime_audit_child_identities(reference_payload)
        audited_children = _runtime_audit_child_identities(audited_payload)
        equivalence = build_equivalence_attestation(
            plan_digest=str(benchmark_plan["artifact_digest"]),
            reference_payload=reference_payload,
            audited_payload=audited_payload,
            reference_child_artifacts=reference_children,
            audited_child_artifacts=audited_children,
        )
        child_payloads: tuple[tuple[Path, Mapping[str, Any]], ...] = (
            (
                task_dir
                / "artifacts/benchmark-plan"
                / str(benchmark_plan["artifact_digest"])
                / "plan.json",
                benchmark_plan,
            ),
            (
                task_dir
                / "artifacts/runtime-observation"
                / str(observation["artifact_digest"])
                / "observation.json",
                observation,
            ),
            (
                task_dir
                / "artifacts/equivalence-attestation"
                / str(equivalence["artifact_digest"])
                / "attestation.json",
                equivalence,
            ),
        )
        for path, payload in child_payloads:
            _persist_immutable(path, payload)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "benchmark_plan_artifact_digest": benchmark_plan["artifact_digest"],
            "runtime_observation_artifact_digest": observation["artifact_digest"],
            "equivalence_attestation_artifact_digest": equivalence[
                "artifact_digest"
            ],
            "completion_fact": M4_P29_RUNTIME_AUDIT_COMPLETION_FACT,
            "actual_fold_count": replicate.cell.outer_issue_count * 2,
            "registered_artifact_count": 4,
            "worker_count": 1,
            "formal_benchmark_after_slot_release": True,
            "reference_evaluator_is_oracle": True,
            "backend_modified": False,
            "historical_outcomes_read": False,
            "evidence_created": False,
            "evidence_progress_before": 0,
            "evidence_progress_after": 0,
            "downstream_consumer": "future independent optimization request",
            "production_impact": "none",
            "git_commit": git_commit,
            "working_tree_clean": True,
            "parent_digests": [
                *task.input_artifact_digests,
                *(str(payload["artifact_digest"]) for _, payload in child_payloads),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(M4_P29_RUNTIME_AUDIT_COMPLETION_FACT,),
        )


class P26MeasurementValidationCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if task.task_key != P26_TASK_KEY or task.requested_capability != P26_CAPABILITY:
            raise MainlineSupervisorError("P2.6 capability received the wrong task")
        contract_path = (
            self.root_dir
            / "configs/research-os/"
            "m4-information-theory-p2-6-1-measurement-validation-v1.json"
        )
        manifest = load_repaired_measurement_validation_manifest(
            contract_path
        )
        truth_digests = tuple(
            str(item["artifact_digest"])
            for item in manifest.payload["truth_artifacts"]
        )
        expected_inputs = (
            MEASUREMENT_REPAIR_MANIFEST_DIGEST,
            REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
            "90459ebf8b88afcc60ee1177043e436b90b71c00b557f15e9e4d7026f37586f2",
            "1a76f46d7a47a134c1688657749bc040290f65a03dbc7c860e38144e02005981",
            KERNEL_MANIFEST_DIGEST,
            P25_METRIC_KERNEL_DIGEST,
            P25_WALK_FORWARD_HARNESS_DIGEST,
            *truth_digests,
        )
        if task.input_artifact_digests != expected_inputs:
            raise MainlineSupervisorError(
                "P2.6.1 requires the repaired contract, four-fit probe "
                "instrument, resampling kernel, and all marginal truths"
            )
        synthetic = load_synthetic_run_manifest(
            self.root_dir
            / "configs/research-os/"
            "m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
        )
        resampling_path = (
            self.root_dir
            / "configs/research-os/"
            "m4-information-theory-p2-5-resampling-kernel-v1.json"
        )
        truths = locate_repaired_truth_artifacts(
            self.root_dir,
            required_digests=truth_digests,
            repair_manifest_digest=MEASUREMENT_REPAIR_MANIFEST_DIGEST,
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        output_dir = task_dir / "artifacts"
        runtime_migration_paths = tuple(
            sorted((task_dir / "runtime-migrations").glob("*/migration.json"))
        )
        evaluator = ReferenceReplicateEvaluator.from_paths(
            manifest=manifest,
            synthetic=synthetic,
            preregistration_path=(
                self.root_dir
                / "configs/research-os/"
                "m4-information-theory-preregistration-v1.0.3.json"
            ),
            walk_forward_harness_path=(
                self.root_dir
                / "configs/research-os/"
                "m4-information-theory-walk-forward-harness-v1.json"
            ),
            resampling_path=resampling_path,
            truth_by_scenario=truths,
            git_commit=git_commit,
            output_dir=output_dir,
        )
        configured_workers = int(
            os.environ.get(
                "DEHPS_P26_WORKERS",
                str(max(1, min(20, (os.cpu_count() or 2) - 2))),
            )
        )
        coordinator = run_parallel_execution(
            manifest=manifest,
            synthetic=synthetic,
            parent_execution_id=execution_id,
            output_dir=output_dir,
            evaluator=evaluator,
            worker_count=configured_workers,
            progress_projection_path=(
                self.root_dir
                / "runtime/logs/"
                "m4-p2-6-1-measurement-validation-progress.json"
            ),
        )
        completion = assemble_completion(
            manifest=manifest,
            synthetic=synthetic,
            parent_execution_id=execution_id,
            output_dir=output_dir,
            git_commit=git_commit,
        )
        child_paths = (
            coordinator.execution_plan_path,
            *completion.replicate_paths,
            *completion.aggregate_paths,
            completion.mde_summary_path,
            completion.completion_artifact_path,
            *runtime_migration_paths,
        )
        child_payloads = tuple(
            (path, _load_object(path)) for path in child_paths
        )
        child_identities = {
            (
                _artifact_digest(payload),
                str(payload.get("artifact_type") or "typed_artifact"),
            )
            for _, payload in child_payloads
        }
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "measurement_validation_manifest_digest": manifest.artifact_digest,
            "execution_plan_digest": coordinator.execution_plan["artifact_digest"],
            "completion_artifact_digest": completion.completion_artifact[
                "artifact_digest"
            ],
            "completion_artifact_path": str(
                completion.completion_artifact_path.relative_to(self.root_dir)
            ),
            "aggregate_digests": [
                item["artifact_digest"] for item in completion.aggregate_artifacts
            ],
            "mde_summary_digest": completion.mde_summary_artifact[
                "artifact_digest"
            ],
            "decision_policy_mde_at_61_bits_per_issue": (
                completion.mde_summary_artifact[
                    "decision_policy_mde_at_61_bits_per_issue"
                ]
            ),
            "replicate_count": len(completion.replicate_paths),
            "aggregate_count": len(completion.aggregate_artifacts),
            "actual_fold_count": manifest.outer_issue_predictions,
            "all_probe_outer_fold_count": manifest.outer_issue_predictions * 4,
            "estimator_and_calibrator_fit_count": (
                manifest.outer_issue_predictions * 4
            ),
            "inner_model_selection_fit_count": 0,
            "superseded_outer_fold_fit_count": (
                manifest.outer_issue_predictions * 46
            ),
            "number_probability_predictions": (
                manifest.outer_issue_predictions * 33 * 4
            ),
            "bootstrap_replicate_count": (
                manifest.scenario_replicates * manifest.bootstrap_replicates
            ),
            "permutation_replicate_count": (
                manifest.scenario_replicates * manifest.permutation_replicates
            ),
            "negative_control_id": "NC6_SYNTHETIC_NULL",
            "negative_control_cell_count": 3,
            "negative_control_replicates_per_cell": (
                manifest.negative_control_replicates
            ),
            "negative_control_replicate_count": 3000,
            "runtime_migration_digests": [
                _artifact_digest(_load_object(path))
                for path in runtime_migration_paths
            ],
            "runtime_git_commits": [
                str(_load_object(path)["runtime_git_commit"])
                for path in runtime_migration_paths
            ],
            "registered_artifact_count": len(child_identities) + 1,
            "engineering_progress_before": 37,
            "engineering_progress_after": 39,
            "evidence_progress_before": 0,
            "evidence_progress_after": 25,
            "downstream_consumer": P27_TASK_KEY,
            "eligible_for_formal_inference": True,
            "formal_power_executed": True,
            "formal_false_positive_executed": True,
            "mde_computed": True,
            "pe2_finalized": True,
            "real_history_used": False,
            "production_checkpoint_created": False,
            "git_commit": git_commit,
            "working_tree_clean": True,
            "evidence_created": True,
            "production_impact": "none",
            "parent_digests": [
                *task.input_artifact_digests,
                coordinator.execution_plan["artifact_digest"],
                completion.completion_artifact["artifact_digest"],
                completion.mde_summary_artifact["artifact_digest"],
                *(
                    _artifact_digest(_load_object(path))
                    for path in runtime_migration_paths
                ),
                *(
                    item["artifact_digest"]
                    for item in completion.aggregate_artifacts
                ),
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        if len(registrations) != execution_payload["registered_artifact_count"]:
            raise MainlineSupervisorError("P2.6 registered artifact count changed")
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
        )


class P27AutomaticMeasurementGateCapability:
    def __init__(self, *, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir = root_dir

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        integration_contract(task)
        if task.task_key != P27_TASK_KEY or task.requested_capability != P27_CAPABILITY:
            raise MainlineSupervisorError("P2.7 capability received the wrong task")
        manifest = load_repaired_measurement_validation_manifest(
            self.root_dir
            / "configs/research-os/"
            "m4-information-theory-p2-6-1-measurement-validation-v1.json"
        )
        if task.input_artifact_digests != (
            P25_DECISION_POLICY_DIGEST,
            REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
        ):
            raise MainlineSupervisorError("P2.7 frozen inputs changed")
        synthetic = load_synthetic_run_manifest(
            self.root_dir
            / "configs/research-os/"
            "m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
        )
        p26_root = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / P26_TASK_KEY
        )
        candidates = sorted(p26_root.glob("*/execution.json"))
        completed = [
            (path, _load_object(path))
            for path in candidates
            if _load_object(path).get("status") == "COMPLETE"
        ]
        if len(completed) != 1:
            raise MainlineSupervisorError(
                "P2.7 requires exactly one completed P2.6 execution artifact"
            )
        p26_execution_path, p26_execution = completed[0]
        p26_execution_id = str(p26_execution["execution_id"])
        p26_output = p26_execution_path.parent / "artifacts"
        replay = verify_completion_replay(
            manifest=manifest,
            synthetic=synthetic,
            parent_execution_id=p26_execution_id,
            output_dir=p26_output,
            git_commit=str(p26_execution["git_commit"]),
            expected_completion_digest=str(
                p26_execution["completion_artifact_digest"]
            ),
        )
        completion_path = (
            self.root_dir / str(p26_execution["completion_artifact_path"])
        )
        completion = _load_object(completion_path)
        aggregate_paths = sorted(p26_output.glob("aggregates/*/*.json"))
        aggregates = [_load_object(path) for path in aggregate_paths]
        gate = evaluate_automatic_gate(
            manifest=manifest,
            completion=completion,
            aggregates=aggregates,
            deterministic_replay_passed=replay["status"] == "REPLAY_VERIFIED",
        )
        task_dir = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        mde = dict(gate["mde_summary"])
        mde_path = task_dir / "artifacts/mde" / mde["artifact_digest"] / "mde.json"
        gate_path = (
            task_dir
            / "artifacts/gate"
            / str(gate["artifact_digest"])
            / "gate.json"
        )
        _persist_immutable(mde_path, mde)
        _persist_immutable(gate_path, gate)
        execution_payload: dict[str, Any] = {
            "schema_version": MAINLINE_EXECUTION_SCHEMA,
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "measurement_validation_manifest_digest": manifest.artifact_digest,
            "p26_execution_artifact_digest": p26_execution["artifact_digest"],
            "execution_plan_digest": p26_execution["execution_plan_digest"],
            "completion_artifact_digest": completion["artifact_digest"],
            "aggregate_digests": p26_execution["aggregate_digests"],
            "automatic_gate_digest": gate["artifact_digest"],
            "mde_summary_digest": mde["artifact_digest"],
            "decision": gate["decision"],
            "decision_fact": gate["decision_fact"],
            "decision_policy_mde_at_61_bits_per_issue": mde[
                "decision_policy_mde_at_61_bits_per_issue"
            ],
            "false_positive_by_scale": [
                {
                    "scale_id": item["scale_id"],
                    "false_positive_rate": item["false_positive_rate"],
                    "wilson_95_upper": item["wilson_95_interval"]["upper"],
                    "point_gate_pass": item[
                        "false_positive_point_gate_pass"
                    ],
                    "wilson_gate_pass": item[
                        "false_positive_wilson_gate_pass"
                    ],
                }
                for item in aggregates
                if item["scenario_id"] == "NULL_UNIFORM"
            ],
            "power_by_cell": [
                {
                    "scale_id": item["scale_id"],
                    "scenario_id": item["scenario_id"],
                    "signal_strength": item["signal_strength"],
                    "truth_bits_per_issue": item["truth_bits_per_issue"],
                    "empirical_power": item["empirical_power"],
                }
                for item in aggregates
                if item["scenario_id"] != "NULL_UNIFORM"
            ],
            "estimator_quality_by_cell": [
                {
                    "scale_id": item["scale_id"],
                    "scenario_id": item["scenario_id"],
                    "bias_bits_per_issue": item["bias_bits_per_issue"],
                    "rmse_bits_per_issue": item["rmse_bits_per_issue"],
                    "PE2_coverage_rate": item["PE2_coverage_rate"],
                    "bias_gate_pass": item["bias_gate_pass"],
                    "coverage_gate_pass": item["coverage_gate_pass"],
                    "rmse_finite_gate_pass": item[
                        "rmse_finite_gate_pass"
                    ],
                }
                for item in aggregates
                if item["scenario_id"] != "NULL_UNIFORM"
            ],
            "completion_facts": [gate["decision_fact"]],
            "additional_completed_task_keys": (
                [P2_UMBRELLA_TASK_KEY]
                if gate["decision"] == "PASS_TO_P3"
                else []
            ),
            "failed_requirements": gate["failed_requirements"],
            "replay_status": replay["status"],
            "replicate_count": completion["replicate_count"],
            "aggregate_count": completion["cell_aggregate_count"],
            "bootstrap_replicate_count": p26_execution[
                "bootstrap_replicate_count"
            ],
            "permutation_replicate_count": p26_execution[
                "permutation_replicate_count"
            ],
            "negative_control_id": p26_execution["negative_control_id"],
            "negative_control_cell_count": p26_execution[
                "negative_control_cell_count"
            ],
            "negative_control_replicates_per_cell": p26_execution[
                "negative_control_replicates_per_cell"
            ],
            "negative_control_replicate_count": p26_execution[
                "negative_control_replicate_count"
            ],
            "actual_fold_count": 0,
            "registered_artifact_count": 3,
            "engineering_progress_before": 39,
            "engineering_progress_after": 40,
            "evidence_progress_before": 25,
            "evidence_progress_after": 25,
            "downstream_consumer": (
                "m4-p3-strict-historical-walk-forward"
                if gate["decision"] == "PASS_TO_P3"
                else "m4-p2-repair-measurement-system"
            ),
            "eligible_for_formal_inference": True,
            "git_commit": git_commit,
            "working_tree_clean": True,
            "production_impact": "none",
            "parent_digests": [
                *task.input_artifact_digests,
                p26_execution["artifact_digest"],
                completion["artifact_digest"],
                gate["artifact_digest"],
                mde["artifact_digest"],
            ],
        }
        identity = dict(execution_payload)
        identity.pop("artifact_digest")
        execution_payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        execution_path = task_dir / "execution.json"
        _persist_immutable(execution_path, execution_payload)
        child_payloads = ((mde_path, mde), (gate_path, gate))
        registrations = P24InjectedSignalCalibrationCapability._registrations(
            self,
            control_plane_key=control_plane_key,
            task=task,
            execution_id=execution_id,
            git_commit=git_commit,
            child_payloads=child_payloads,
            execution_path=execution_path,
            execution_payload=execution_payload,
        )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(str(gate["decision_fact"]),),
            additional_completed_task_keys=(
                (P2_UMBRELLA_TASK_KEY,)
                if gate["decision"] == "PASS_TO_P3"
                else ()
            ),
        )


class ResearchEvidenceSupervisor:
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository | None = None,
        control_plane_key: str = "m4-information-theory-mainline",
        root_dir: Path = ROOT_DIR,
        now: Callable[[], datetime] | None = None,
        git_commit: str | None = None,
        require_clean_tree: bool = True,
    ) -> None:
        self.repository = repository or PostgresResearchOSRepository()
        self.control_plane_key = control_plane_key
        self.root_dir = root_dir
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.git_commit = git_commit
        self.require_clean_tree = require_clean_tree
        self.capabilities = {
            P23_CAPABILITY: P23WalkForwardCapability(root_dir=root_dir),
            P24_CAPABILITY: P24InjectedSignalCalibrationCapability(
                root_dir=root_dir
            ),
            P25_CAPABILITY: P25ResamplingCapability(root_dir=root_dir),
            P26_PREFLIGHT_CAPABILITY: P26IdentifiabilityPreflightCapability(
                root_dir=root_dir
            ),
            P26_REPAIR_CAPABILITY: P26MeasurementSystemRepairCapability(
                root_dir=root_dir
            ),
            P26_CAPABILITY: P26MeasurementValidationCapability(root_dir=root_dir),
            P27_CAPABILITY: P27AutomaticMeasurementGateCapability(
                root_dir=root_dir
            ),
            M4_V2_DESIGN_CAPABILITY: M4MeasurementContractV2DesignCapability(
                root_dir=root_dir
            ),
            M4_V2_DESIGN_REPLAY_CAPABILITY: (
                M4MeasurementContractV2DesignReplayCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            M4_V2_P261_RAW_REPLAY_CAPABILITY: (
                M4P261RawExecutionReplayCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            M4_V2_P27_GATE_REPLAY_CAPABILITY: M4P27GateReplayCapability(
                repository=self.repository,
                root_dir=root_dir,
            ),
            M4_V2_MARGINAL_BINDING_CAPABILITY: M4P261MarginalBindingCapability(
                repository=self.repository,
                root_dir=root_dir,
            ),
            M4_V2_MARGINAL_DECISION_REPLAY_CAPABILITY: (
                M4P261MarginalDecisionReplayCapability(
                    repository=self.repository,
                    root_dir=root_dir,
                )
            ),
            M4_P29_RUNTIME_AUDIT_CAPABILITY: M4P29MeasurementRuntimeAuditCapability(
                root_dir=root_dir
            ),
            PREDICTION_V2_REFERENCE_CAPABILITY: PredictionV2ReferenceCapability(
                root_dir=root_dir
            ),
            PREDICTION_V2_REPLAY_CAPABILITY: PredictionV2ReplayCapability(
                repository=self.repository,
                root_dir=root_dir,
            ),
            PREDICTION_V2_PRE_CAPABILITY: PredictionV2IssuePreDrawCapability(
                root_dir=root_dir,
            ),
            PREDICTION_V2_PRE_REPLAY_CAPABILITY: PredictionV2IssuePreDrawReplayCapability(
                repository=self.repository,
                root_dir=root_dir,
            ),
            PREDICTION_V2_POST_CAPABILITY: PredictionV2IssuePostDrawCapability(
                repository=self.repository,
                root_dir=root_dir,
            ),
            PREDICTION_V2_POST_REPLAY_CAPABILITY: PredictionV2IssuePostDrawReplayCapability(
                repository=self.repository,
                root_dir=root_dir,
            ),
        }

    @property
    def state_path(self) -> Path:
        if self.control_plane_key == PREDICTION_V2_CONTROL_PLANE_KEY:
            return self.root_dir / "runtime/logs/prediction-v2-shadow-supervisor-state.json"
        return self.root_dir / "runtime/logs/research-evidence-supervisor-state.json"

    def run_once(self, *, task_key: str | None = None) -> dict[str, Any]:
        self.repository.ensure_schema()
        runtime_git_commit = self.git_commit or resolve_git_commit(self.root_dir)
        git_commit = runtime_git_commit
        runtime_migration: Mapping[str, Any] | None = None
        if self.require_clean_tree:
            dirty = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.root_dir,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            if dirty:
                raise MainlineSupervisorError(
                    "dirty_worktree: mainline execution requires a clean tree"
                )

        manifest = self.repository.load_manifest(
            control_plane_key=self.control_plane_key
        )
        snapshot = self.repository.control_plane.resolve(manifest)
        task_by_key = {task.task_key: task for task in manifest.tasks}
        task_states = manifest.task_state_by_digest
        running = [
            item
            for item in snapshot.resolutions
            if item.status is TaskStatus.RUNNING
            and (task_key is None or item.task_key == task_key)
            and task_by_key[item.task_key].requested_capability in self.capabilities
        ]
        ready = [
            item
            for item in snapshot.ready_queue
            if (task_key is None or item.task_key == task_key)
            and task_by_key[item.task_key].requested_capability in self.capabilities
        ]
        if not running and not ready:
            unsupported = [
                item.task_key
                for item in snapshot.ready_queue
                if task_by_key[item.task_key].requested_capability not in self.capabilities
            ]
            payload = {
                "schema_version": "dehps-research-evidence-supervisor-state.v1",
                "status": "WAITING_FOR_CAPABILITY" if unsupported else "IDLE",
                "control_plane_key": self.control_plane_key,
                "manifest_digest": manifest.artifact_digest,
                "snapshot_digest": snapshot.snapshot_digest,
                "ready_tasks": [item.task_key for item in snapshot.ready_queue],
                "unsupported_ready_tasks": unsupported,
                "dispatch_performed": False,
                "git_commit": git_commit,
                "heartbeat_at": self.now().isoformat(),
            }
            self._write_state(payload)
            self._write_lane_status(
                self._build_lane_status(
                    manifest,
                    snapshot=snapshot,
                    dispatch_performed=False,
                )
            )
            return payload

        item = (running or ready)[0]
        task = task_by_key[item.task_key]
        capability = str(task.requested_capability)
        is_resume = (
            task_states[task.artifact_digest].declared_status is TaskStatus.RUNNING
        )
        if is_resume:
            running_manifest = manifest
            running_manifest_digest = manifest.artifact_digest
            events = self.repository.list_mainline_execution_events(
                control_plane_key=self.control_plane_key,
                task_key=task.task_key,
            )
            completed = [
                event
                for event in events
                if event.get("task_digest") == task.artifact_digest
                and event.get("event_type") == "completed"
            ]
            if len(completed) == 1:
                return self._finalize_completed_execution(
                    manifest=manifest,
                    task=task,
                    event=completed[0],
                    git_commit=git_commit,
                )
            started = [
                event
                for event in events
                if event.get("task_digest") == task.artifact_digest
                and event.get("event_type") == "started"
            ]
            failed = [
                event
                for event in events
                if event.get("task_digest") == task.artifact_digest
                and event.get("event_type") == "failed"
            ]
            if failed or len(started) > 1 or len(completed) > 1:
                raise MainlineSupervisorError(
                    f"inconsistent persisted execution state for running task: {task.task_key}"
                )
            if started:
                execution_id = str(started[0]["execution_id"])
                original_commit = str(_event_payload(started[0]).get("git_commit") or "")
                if original_commit != git_commit:
                    allowed_origin = os.environ.get(P26_EQUIVALENT_RESUME_ENV, "")
                    if (
                        task.task_key != P26_TASK_KEY
                        or not allowed_origin
                        or allowed_origin != original_commit
                    ):
                        raise MainlineSupervisorError(
                            "running execution git commit differs from the current clean tree"
                        )
                    runtime_migration = self._record_p26_runtime_migration(
                        task=task,
                        execution_id=execution_id,
                        execution_git_commit=original_commit,
                        runtime_git_commit=runtime_git_commit,
                    )
                    git_commit = original_commit
            else:
                execution_id = self._execution_id(
                    task=task,
                    capability=capability,
                    git_commit=git_commit,
                )
                self._record_started_event(
                    task=task,
                    capability=capability,
                    execution_id=execution_id,
                    manifest_digest=running_manifest_digest,
                    git_commit=git_commit,
                )
        else:
            execution_id = self._execution_id(
                task=task,
                capability=capability,
                git_commit=git_commit,
            )
            existing = self._completed_event(execution_id)
            if existing is not None:
                return self._finalize_completed_execution(
                    manifest=manifest,
                    task=task,
                    event=existing,
                    git_commit=git_commit,
                )
            running_payload = self._transition_manifest(
                manifest,
                task_key=task.task_key,
                status=TaskStatus.RUNNING,
                classification=CompletionClassification.INTEGRATED,
            )
            running_import = self.repository.import_manifest(
                control_plane_key=self.control_plane_key,
                payload=running_payload,
                source="research-evidence-supervisor-running",
            )
            running_manifest = self.repository.load_manifest(
                control_plane_key=self.control_plane_key
            )
            running_manifest_digest = running_import.manifest_digest
            self._record_started_event(
                task=task,
                capability=capability,
                execution_id=execution_id,
                manifest_digest=running_manifest_digest,
                git_commit=git_commit,
            )
        running_snapshot = self.repository.control_plane.resolve(running_manifest)
        running_status = self._build_lane_status(
            running_manifest,
            snapshot=running_snapshot,
            dispatch_performed=True,
        )
        self._write_state(
            {
                "schema_version": "dehps-research-evidence-supervisor-state.v1",
                "status": "RUNNING",
                "control_plane_key": self.control_plane_key,
                "task_key": task.task_key,
                "task_digest": task.artifact_digest,
                "execution_id": execution_id,
                "capability": capability,
                "manifest_digest": running_manifest_digest,
                "snapshot_digest": running_snapshot.snapshot_digest,
                "dispatch_performed": True,
                "git_commit": git_commit,
                "runtime_git_commit": runtime_git_commit,
                **(
                    {
                        "runtime_migration_digest": runtime_migration[
                            "artifact_digest"
                        ]
                    }
                    if runtime_migration is not None
                    else {}
                ),
                "heartbeat_at": self.now().isoformat(),
                **(
                    {
                        "progress_projection_path": (
                            "runtime/logs/"
                            "m4-p2-6-1-measurement-validation-progress.json"
                        )
                    }
                    if task.task_key == P26_TASK_KEY
                    else {}
                ),
            }
        )
        self._write_lane_status(running_status)
        completed_recorded = False
        try:
            result = self.capabilities[capability].execute(
                control_plane_key=self.control_plane_key,
                task=task,
                execution_id=execution_id,
                git_commit=git_commit,
            )
            for registration in result.registrations:
                self.repository.register_mainline_artifact(
                    registration=registration
                )
            completed_at = self.now().isoformat()
            completed = MainlineExecutionEvent(
                execution_id=execution_id,
                control_plane_key=self.control_plane_key,
                manifest_digest=running_manifest_digest,
                task_key=task.task_key,
                task_digest=task.artifact_digest,
                capability=capability,
                event_type="completed",
                sequence=1,
                recorded_at=completed_at,
                payload=tuple(
                    sorted(
                        {
                            "execution_artifact_digest": result.execution_artifact[
                                "artifact_digest"
                            ],
                            "execution_artifact_path": str(
                                result.execution_artifact_path.relative_to(
                                    self.root_dir
                                )
                            ),
                            "actual_fold_count": result.execution_artifact[
                                "actual_fold_count"
                            ],
                            "registered_artifact_count": len(result.registrations),
                            "git_commit": git_commit,
                            "completion_facts": list(result.completion_facts),
                            "additional_completed_task_keys": list(
                                result.additional_completed_task_keys
                            ),
                            **{
                                key: result.execution_artifact[key]
                                for key in (
                                    "calibration_run_manifest_digest",
                                    "calibration_run_artifact_digest",
                                    "completion_artifact_digest",
                                    "truth_artifact_digests",
                                    "truth_artifact_count",
                                    "eligible_for_p2_5_input",
                                    "eligible_for_power_evidence",
                                    "resampling_kernel_digest",
                                    "resampling_run_digest",
                                    "resampling_completion_digest",
                                    "child_replicate_digests",
                                    "aggregate_digests",
                                    "replicate_count",
                                    "aggregate_count",
                                    "eligible_for_formal_inference",
                                    "measurement_validation_manifest_digest",
                                    "identifiability_preflight_manifest_digest",
                                    "identifiability_preflight_report_digest",
                                    "superseded_run_archive_digest",
                                    "execution_plan_digest",
                                    "automatic_gate_digest",
                                    "mde_summary_digest",
                                    "decision",
                                    "decision_fact",
                                    "failed_requirements",
                                    "scenario_count",
                                    "p2_6_partial_statistical_results_inspected",
                                    "old_p2_6_execution_resumable",
                                    "old_p2_6_partial_statistical_results_inspected",
                                    "measurement_repair_manifest_digest",
                                    "repaired_measurement_validation_manifest_digest",
                                    "development_selection_artifact_digest",
                                    "identifiability_confirmation_digest",
                                    "outer_fold_fit_count_before",
                                    "outer_fold_fit_count_after",
                                    "inner_model_selection_per_outer_fold",
                                    "formal_power_target_count",
                                    "joint_only_negative_control_count",
                                    "feasibility_sentinel_count",
                                    "replay_status",
                                    "bootstrap_replicate_count",
                                    "permutation_replicate_count",
                                    "negative_control_id",
                                    "negative_control_cell_count",
                                    "negative_control_replicates_per_cell",
                                    "negative_control_replicate_count",
                                    "decision_policy_mde_at_61_bits_per_issue",
                                    "false_positive_by_scale",
                                    "power_by_cell",
                                    "estimator_quality_by_cell",
                                    "runtime_migration_digests",
                                    "runtime_git_commits",
                                    "measurement_contract_v2_digest",
                                    "estimand_contract_digest",
                                    "mechanism_role_contract_digest",
                                    "gate_compiler_contract_digest",
                                    "design_execution_id",
                                    "design_execution_artifact_digest",
                                    "measurement_contract_replay_digest",
                                    "gate_compiler_replay_digest",
                                    "p2_6_1_execution_id",
                                    "p2_6_1_execution_artifact_digest",
                                    "raw_replay_artifact_digest",
                                    "p2_7_execution_id",
                                    "p2_7_execution_artifact_digest",
                                    "gate_replay_artifact_digest",
                                    "binding_contract_digest",
                                    "marginal_decision_artifact_digest",
                                    "branch_decision_replay_artifact_digest",
                                    "measurement_health",
                                    "historical_evidence",
                                    "formal_branch_runs_executed",
                                    "historical_outcomes_read",
                                    "p2_6_1_partial_statistical_results_read",
                                )
                                if key in result.execution_artifact
                            },
                        }.items()
                    )
                ),
            )
            self.repository.record_mainline_execution_event(event=completed)
            completed_recorded = True
            return self._finalize_completed_execution(
                manifest=running_manifest,
                task=task,
                event={
                    "execution_id": execution_id,
                    "recorded_at": completed_at,
                    "payload": [list(item) for item in completed.payload],
                },
                git_commit=git_commit,
            )
        except Exception as exc:
            if completed_recorded:
                raise
            failed = MainlineExecutionEvent(
                execution_id=execution_id,
                control_plane_key=self.control_plane_key,
                manifest_digest=running_manifest_digest,
                task_key=task.task_key,
                task_digest=task.artifact_digest,
                capability=capability,
                event_type="failed",
                sequence=1,
                recorded_at=self.now().isoformat(),
                payload=(("error", str(exc)), ("git_commit", git_commit)),
            )
            self.repository.record_mainline_execution_event(event=failed)
            failed_manifest = self._transition_manifest(
                running_manifest,
                task_key=task.task_key,
                status=TaskStatus.FAILED,
                classification=CompletionClassification.INTEGRATED,
            )
            self.repository.import_manifest(
                control_plane_key=self.control_plane_key,
                payload=failed_manifest,
                source="research-evidence-supervisor-failed",
            )
            payload = {
                "schema_version": "dehps-research-evidence-supervisor-state.v1",
                "status": "FAILED",
                "control_plane_key": self.control_plane_key,
                "task_key": task.task_key,
                "execution_id": execution_id,
                "error": str(exc),
                "dispatch_performed": True,
                "git_commit": git_commit,
                "heartbeat_at": self.now().isoformat(),
            }
            self._write_state(payload)
            raise

    def _execution_id(
        self,
        *,
        task: Task,
        capability: str,
        git_commit: str,
    ) -> str:
        return stable_hash(
            {
                "schema": MAINLINE_EXECUTION_SCHEMA,
                "control_plane_key": self.control_plane_key,
                "task_digest": task.artifact_digest,
                "capability": capability,
                "input_artifact_digests": task.input_artifact_digests,
                "git_commit": git_commit,
            }
        )

    def _latest_completed_summary(
        self,
        snapshot: Any,
    ) -> dict[str, Any] | None:
        return self._latest_completed_summary_for_tasks(
            snapshot,
            (
                P27_TASK_KEY,
                P26_TASK_KEY,
                P26_REPAIR_TASK_KEY,
                P26_PREFLIGHT_TASK_KEY,
                P25_TASK_KEY,
                P24_TASK_KEY,
                P23_TASK_KEY,
            ),
        )

    def _latest_completed_v2_summary(
        self,
        snapshot: Any,
    ) -> dict[str, Any] | None:
        return self._latest_completed_summary_for_tasks(
            snapshot,
            (
                M4_V2_MARGINAL_DECISION_REPLAY_TASK_KEY,
                M4_V2_MARGINAL_BINDING_TASK_KEY,
                M4_V2_P27_GATE_REPLAY_TASK_KEY,
                M4_V2_P261_RAW_REPLAY_TASK_KEY,
                M4_V2_DESIGN_REPLAY_TASK_KEY,
                M4_V2_DESIGN_TASK_KEY,
            ),
        )

    def _latest_completed_summary_for_tasks(
        self,
        snapshot: Any,
        task_keys: tuple[str, ...],
    ) -> dict[str, Any] | None:
        resolutions = {
            item.task_key: item.status for item in snapshot.resolutions
        }
        for candidate in task_keys:
            if resolutions.get(candidate) is not TaskStatus.COMPLETED:
                continue
            events = self.repository.list_mainline_execution_events(
                control_plane_key=self.control_plane_key,
                task_key=candidate,
            )
            completed = [
                event
                for event in events
                if event.get("event_type") == "completed"
            ]
            if len(completed) == 1:
                return {
                    **_event_payload(completed[0]),
                    "execution_task_key": candidate,
                }
        return None

    def _record_started_event(
        self,
        *,
        task: Task,
        capability: str,
        execution_id: str,
        manifest_digest: str,
        git_commit: str,
    ) -> None:
        started = MainlineExecutionEvent(
            execution_id=execution_id,
            control_plane_key=self.control_plane_key,
            manifest_digest=manifest_digest,
            task_key=task.task_key,
            task_digest=task.artifact_digest,
            capability=capability,
            event_type="started",
            sequence=0,
            recorded_at=self.now().isoformat(),
            payload=(
                ("input_artifact_digests", list(task.input_artifact_digests)),
                ("git_commit", git_commit),
            ),
        )
        if not self.repository.record_mainline_execution_event(event=started):
            raise MainlineSupervisorError(
                f"could not persist unique started event: {execution_id}"
            )

    def _finalize_completed_execution(
        self,
        *,
        manifest: ControlPlaneManifest,
        task: Task,
        event: Mapping[str, Any],
        git_commit: str,
    ) -> dict[str, Any]:
        execution_id = str(event["execution_id"])
        summary = {
            **_event_payload(event),
            "execution_task_key": task.task_key,
        }
        completion_fact = mainline_completion_fact(
            task=task,
            execution_id=execution_id,
        )
        extra_facts = tuple(
            str(value) for value in summary.get("completion_facts", ())
        )
        additional_completed = tuple(
            str(value)
            for value in summary.get("additional_completed_task_keys", ())
        )
        completed_manifest = self._transition_manifest(
            manifest,
            task_key=task.task_key,
            status=TaskStatus.COMPLETED,
            classification=CompletionClassification.COMPLETE,
            completion_fact=completion_fact,
            completion_facts=extra_facts,
            additional_completed_task_keys=additional_completed,
        )
        completed_import = self.repository.import_manifest(
            control_plane_key=self.control_plane_key,
            payload=completed_manifest,
            source="research-evidence-supervisor-completed",
        )
        final_manifest = self.repository.load_manifest(
            control_plane_key=self.control_plane_key
        )
        final_snapshot = self.repository.control_plane.resolve(final_manifest)
        status = self._build_lane_status(
            final_manifest,
            snapshot=final_snapshot,
            dispatch_performed=True,
            completed_summary=summary,
        )
        completed_at = str(event.get("recorded_at") or self.now().isoformat())
        payload = {
            "schema_version": "dehps-research-evidence-supervisor-state.v1",
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "control_plane_key": self.control_plane_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "execution_id": execution_id,
            "execution_artifact_digest": summary["execution_artifact_digest"],
            "actual_fold_count": summary["actual_fold_count"],
            "registered_artifact_count": summary["registered_artifact_count"],
            "manifest_digest": completed_import.manifest_digest,
            "snapshot_digest": final_snapshot.snapshot_digest,
            "next_ready_task": status["next_ready_task"],
            "engineering_progress_percent": status["progress"][
                "engineering_percent"
            ],
            "evidence_progress_percent": status["progress"]["evidence_percent"],
            "dispatch_performed": True,
            "git_commit": git_commit,
            "heartbeat_at": completed_at,
        }
        for key in (
            "calibration_run_manifest_digest",
            "calibration_run_artifact_digest",
            "completion_artifact_digest",
            "truth_artifact_digests",
            "truth_artifact_count",
            "eligible_for_p2_5_input",
            "eligible_for_power_evidence",
            "resampling_kernel_digest",
            "resampling_run_digest",
            "resampling_completion_digest",
            "child_replicate_digests",
            "aggregate_digests",
            "replicate_count",
            "aggregate_count",
            "eligible_for_formal_inference",
            "measurement_validation_manifest_digest",
            "identifiability_preflight_manifest_digest",
            "identifiability_preflight_report_digest",
            "superseded_run_archive_digest",
            "execution_plan_digest",
            "automatic_gate_digest",
            "mde_summary_digest",
            "decision",
            "decision_fact",
            "failed_requirements",
            "scenario_count",
            "p2_6_partial_statistical_results_inspected",
            "old_p2_6_execution_resumable",
            "old_p2_6_partial_statistical_results_inspected",
            "measurement_repair_manifest_digest",
            "repaired_measurement_validation_manifest_digest",
            "development_selection_artifact_digest",
            "identifiability_confirmation_digest",
            "outer_fold_fit_count_before",
            "outer_fold_fit_count_after",
            "inner_model_selection_per_outer_fold",
            "formal_power_target_count",
            "joint_only_negative_control_count",
            "feasibility_sentinel_count",
            "replay_status",
            "bootstrap_replicate_count",
            "permutation_replicate_count",
            "negative_control_id",
            "negative_control_cell_count",
            "negative_control_replicates_per_cell",
            "negative_control_replicate_count",
            "decision_policy_mde_at_61_bits_per_issue",
            "false_positive_by_scale",
            "power_by_cell",
            "estimator_quality_by_cell",
            "runtime_migration_digests",
            "runtime_git_commits",
            "measurement_contract_v2_digest",
            "estimand_contract_digest",
            "mechanism_role_contract_digest",
            "gate_compiler_contract_digest",
            "design_execution_id",
            "design_execution_artifact_digest",
            "measurement_contract_replay_digest",
            "gate_compiler_replay_digest",
            "p2_6_1_execution_id",
            "p2_6_1_execution_artifact_digest",
            "raw_replay_artifact_digest",
            "p2_7_execution_id",
            "p2_7_execution_artifact_digest",
            "gate_replay_artifact_digest",
            "binding_contract_digest",
            "marginal_decision_artifact_digest",
            "branch_decision_replay_artifact_digest",
            "measurement_health",
            "historical_evidence",
            "formal_branch_runs_executed",
            "historical_outcomes_read",
            "p2_6_1_partial_statistical_results_read",
        ):
            if key in summary:
                payload[key] = summary[key]
        self._write_state(payload)
        self._write_lane_status(status)
        return payload

    def _record_p26_runtime_migration(
        self,
        *,
        task: Task,
        execution_id: str,
        execution_git_commit: str,
        runtime_git_commit: str,
    ) -> Mapping[str, Any]:
        report_relative = os.environ.get(
            P26_EQUIVALENT_RESUME_REPORT_ENV,
            P26_EQUIVALENT_RESUME_REPORT,
        )
        report_path = self.root_dir / report_relative
        if not report_path.is_file():
            raise MainlineSupervisorError(
                "P2.6 equivalent resume evidence report is missing"
            )
        try:
            normalized_report_path = str(report_path.relative_to(self.root_dir))
        except ValueError as exc:
            raise MainlineSupervisorError(
                "P2.6 equivalent resume evidence report must be inside the repository"
            ) from exc
        report_digest = sha256(report_path.read_bytes()).hexdigest()
        payload: dict[str, Any] = {
            "schema_version": "dehps-p2-6-runtime-migration.v1",
            "artifact_type": "measurement_validation_runtime_migration",
            "artifact_digest": "",
            "execution_id": execution_id,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "execution_git_commit": execution_git_commit,
            "runtime_git_commit": runtime_git_commit,
            "equivalence_evidence_path": normalized_report_path,
            "equivalence_evidence_sha256": report_digest,
            "compatibility_claim": (
                "byte_identical_result_artifact_and_checkpoint_replay"
            ),
            "statistical_contract_changed": False,
            "workload_changed": False,
            "parent_digests": [
                task.artifact_digest,
                report_digest,
            ],
        }
        identity = dict(payload)
        identity.pop("artifact_digest")
        payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.p2-6.runtime-migration.v1",
        )
        path = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
            / "runtime-migrations"
            / payload["artifact_digest"]
            / "migration.json"
        )
        _persist_immutable(path, payload)
        return payload

    def replay(self, *, task_key: str, execution_id: str | None = None) -> dict[str, Any]:
        events = self.repository.list_mainline_execution_events(
            control_plane_key=self.control_plane_key,
            task_key=task_key,
            execution_id=execution_id,
        )
        completed = [event for event in events if event.get("event_type") == "completed"]
        if len(completed) != 1:
            raise MainlineSupervisorError(
                f"mainline replay requires one completed execution: {task_key}"
            )
        event = completed[0]
        resolved_execution_id = str(event["execution_id"])
        summary = _event_payload(event)
        artifact_path = self.root_dir / str(summary["execution_artifact_path"])
        artifact = _load_object(artifact_path)
        expected = canonical_digest(
            {key: value for key, value in artifact.items() if key != "artifact_digest"},
            domain="dehps.research-os.mainline-execution.v1",
        )
        if expected != artifact.get("artifact_digest"):
            raise MainlineSupervisorError("mainline execution artifact digest changed")
        registrations = self.repository.list_mainline_artifacts(
            control_plane_key=self.control_plane_key,
            execution_id=resolved_execution_id,
        )
        if len(registrations) != int(summary["registered_artifact_count"]):
            raise MainlineSupervisorError("mainline artifact registry count changed")
        missing = [
            item["artifact_path"]
            for item in registrations
            if not (self.root_dir / str(item["artifact_path"])).is_file()
        ]
        if missing:
            raise MainlineSupervisorError(
                "registered mainline artifacts are missing: " + ", ".join(missing)
            )
        capability_replay: dict[str, Any] | None = None
        if task_key == PREDICTION_V2_REFERENCE_TASK_KEY:
            expected_children = build_reference_children(self.root_dir)
            registered_children = [
                item
                for item in registrations
                if item.get("artifact_type") != "research_os_mainline_execution"
            ]
            expected_by_digest = {
                str(item["artifact_digest"]): item for item in expected_children
            }
            if {
                str(item.get("artifact_digest") or "") for item in registered_children
            } != set(expected_by_digest):
                raise MainlineSupervisorError(
                    "Prediction v2 reference registered artifact set changed"
                )
            for registration in registered_children:
                stored = _load_object(
                    self.root_dir / str(registration["artifact_path"])
                )
                if stored != expected_by_digest[str(registration["artifact_digest"])]:
                    raise MainlineSupervisorError(
                        "Prediction v2 reference registered artifact content changed"
                    )
            capability_replay = {
                "status": "REPLAY_VERIFIED",
                "same_contract_identity": True,
                "same_fixture_identity": True,
                "same_pool_identity": True,
                "same_top100_identity": True,
                "same_pre_draw_report_identity": True,
                "same_post_draw_report_identity": True,
                "historical_evidence": "NOT_RUN",
                "promotion_gate_opened": False,
                "manual_input_assembly": False,
            }
        elif task_key == PREDICTION_V2_REPLAY_TASK_KEY:
            expected = build_reference_children(self.root_dir)
            expected_by_type = {str(item["artifact_type"]): item for item in expected}
            history, actual = build_reference_history()
            pre_replay = replay_prediction_v2_pre_draw(
                contract=expected_by_type["PredictionV2ShadowContract.v1"],
                history=history,
                expected_state=expected_by_type["PredictionV2StateArtifact.v1"],
                expected_pool=expected_by_type["PredictionV2ShadowPoolArtifact.v1"],
                expected_top100=expected_by_type["PredictionV2ShadowTop100Artifact.v1"],
                expected_report=expected_by_type["PredictionV2PreDrawReport.v1"],
            )
            post_replay = replay_prediction_v2_post_draw(
                pre_draw_report=expected_by_type["PredictionV2PreDrawReport.v1"],
                actual_issue="2026121",
                actual_red_numbers=actual,
                expected_report=expected_by_type["PredictionV2PostDrawReport.v1"],
            )
            expected_replay_by_digest = {
                str(item["artifact_digest"]): item for item in (pre_replay, post_replay)
            }
            registered_children = [
                item
                for item in registrations
                if item.get("artifact_type") != "research_os_mainline_execution"
            ]
            if {
                str(item.get("artifact_digest") or "") for item in registered_children
            } != set(expected_replay_by_digest):
                raise MainlineSupervisorError(
                    "Prediction v2 replay registered artifact set changed"
                )
            for registration in registered_children:
                stored = _load_object(
                    self.root_dir / str(registration["artifact_path"])
                )
                if stored != expected_replay_by_digest[str(registration["artifact_digest"])]:
                    raise MainlineSupervisorError(
                        "Prediction v2 replay attestation content changed"
                    )
            capability_replay = {
                "status": "REPLAY_VERIFIED",
                "same_pre_draw_identity": True,
                "same_post_draw_identity": True,
                "historical_evidence": "NOT_RUN",
                "promotion_gate_opened": False,
                "manual_input_assembly": False,
            }
        elif task_key == M4_V2_DESIGN_TASK_KEY:
            contract = load_measurement_contract_v2(
                self.root_dir / MEASUREMENT_CONTRACT_V2_PATH
            )
            reconstructed = build_design_artifacts(
                contract,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
            )
            if (
                reconstructed.estimand_contract["artifact_digest"]
                != artifact["estimand_contract_digest"]
                or reconstructed.mechanism_role_contract["artifact_digest"]
                != artifact["mechanism_role_contract_digest"]
                or reconstructed.gate_compiler_contract["artifact_digest"]
                != artifact["gate_compiler_contract_digest"]
                or reconstructed.completion["artifact_digest"]
                != artifact["completion_artifact_digest"]
            ):
                raise MainlineSupervisorError(
                    "M4 Measurement Contract v2 deterministic replay changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(
                    *reconstructed.artifacts,
                    artifact,
                ),
            )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-measurement-v2-design-replay.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "measurement_contract_v2_digest": contract.artifact_digest,
                "estimand_contract_digest": reconstructed.estimand_contract[
                    "artifact_digest"
                ],
                "mechanism_role_contract_digest": (
                    reconstructed.mechanism_role_contract["artifact_digest"]
                ),
                "gate_compiler_contract_digest": (
                    reconstructed.gate_compiler_contract["artifact_digest"]
                ),
                "completion_artifact_digest": reconstructed.completion[
                    "artifact_digest"
                ],
                "formal_branch_runs_executed": 0,
                "historical_outcomes_read": False,
                "manual_input_assembly": False,
            }
        elif task_key == M4_V2_DESIGN_REPLAY_TASK_KEY:
            parent_events = self.repository.list_mainline_execution_events(
                control_plane_key=self.control_plane_key,
                task_key=M4_V2_DESIGN_TASK_KEY,
            )
            parent_completed = [
                item
                for item in parent_events
                if item.get("event_type") == "completed"
                and item.get("execution_id")
                == artifact.get("design_execution_id")
            ]
            if len(parent_completed) != 1:
                raise MainlineSupervisorError(
                    "M4 v2 design replay cannot resolve its design parent"
                )
            parent_summary = _event_payload(parent_completed[0])
            parent_path = self.root_dir / str(
                parent_summary["execution_artifact_path"]
            )
            parent_execution = _load_object(parent_path)
            parent_registrations = list(
                self.repository.list_mainline_artifacts(
                    control_plane_key=self.control_plane_key,
                    execution_id=str(parent_execution["execution_id"]),
                )
            )
            contract = load_measurement_contract_v2(
                self.root_dir / MEASUREMENT_CONTRACT_V2_PATH
            )
            reconstructed_design = build_design_artifacts(
                contract,
                execution_id=str(parent_execution["execution_id"]),
                git_commit=str(parent_execution["git_commit"]),
            )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=parent_registrations,
                expected_payloads=(
                    *reconstructed_design.artifacts,
                    parent_execution,
                ),
            )
            fixture = load_gate_replay_fixture(
                self.root_dir / GATE_REPLAY_FIXTURE_PATH
            )
            reconstructed_replay = build_design_replay_artifacts(
                contract,
                fixture=fixture,
                design_execution=parent_execution,
                design_child_digests=[
                    str(item["artifact_digest"])
                    for item in parent_registrations
                    if item.get("artifact_type")
                    != "research_os_mainline_execution"
                ],
                registration_payloads=parent_registrations,
            )
            if (
                reconstructed_replay.measurement_contract_replay[
                    "artifact_digest"
                ]
                != artifact.get("measurement_contract_replay_digest")
                or reconstructed_replay.gate_compiler_replay[
                    "artifact_digest"
                ]
                != artifact.get("gate_compiler_replay_digest")
            ):
                raise MainlineSupervisorError(
                    "M4 Measurement Contract v2 replay attestation changed"
                )
            _verify_v2_registered_artifacts(
                root_dir=self.root_dir,
                registrations=registrations,
                expected_payloads=(*reconstructed_replay.artifacts, artifact),
            )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-measurement-v2-design-replay-attestation.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "design_execution_id": parent_execution["execution_id"],
                "measurement_contract_replay_digest": (
                    reconstructed_replay.measurement_contract_replay[
                        "artifact_digest"
                    ]
                ),
                "gate_compiler_replay_digest": (
                    reconstructed_replay.gate_compiler_replay[
                        "artifact_digest"
                    ]
                ),
                "same_registered_content": True,
                "same_gate_fixture_output": True,
                "formal_branch_runs_executed": 0,
                "historical_outcomes_read": False,
                "manual_input_assembly": False,
            }
        elif task_key == P26_REPAIR_TASK_KEY:
            repair = run_measurement_contract_repair(
                root_dir=self.root_dir,
                execution_id=resolved_execution_id,
                git_commit=str(artifact["git_commit"]),
            )
            if (
                repair.completion["artifact_digest"]
                != artifact["completion_artifact_digest"]
                or repair.development_selection["artifact_digest"]
                != artifact["development_selection_artifact_digest"]
                or repair.identifiability_confirmation["artifact_digest"]
                != artifact["identifiability_confirmation_digest"]
                or [
                    item["artifact_digest"]
                    for item in repair.truth_artifacts
                ]
                != artifact["truth_artifact_digests"]
            ):
                raise MainlineSupervisorError(
                    "measurement repair deterministic replay changed"
                )
            capability_replay = {
                "schema_version": (
                    "dehps-m4-p2-measurement-repair-replay.v1"
                ),
                "status": "REPLAY_VERIFIED",
                "completion_artifact_digest": repair.completion[
                    "artifact_digest"
                ],
                "development_selection_artifact_digest": (
                    repair.development_selection["artifact_digest"]
                ),
                "truth_artifact_count": len(repair.truth_artifacts),
                "same_contract_identity": True,
                "same_development_selection": True,
                "same_truth_identities": True,
                "manual_input_assembly": False,
            }
        elif task_key == P26_TASK_KEY:
            measurement_manifest = (
                load_repaired_measurement_validation_manifest(
                    self.root_dir
                    / "configs/research-os/"
                    "m4-information-theory-p2-6-1-measurement-validation-v1.json"
                )
            )
            synthetic = load_synthetic_run_manifest(
                self.root_dir
                / "configs/research-os/"
                "m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
            )
            capability_replay = verify_completion_replay(
                manifest=measurement_manifest,
                synthetic=synthetic,
                parent_execution_id=resolved_execution_id,
                output_dir=artifact_path.parent / "artifacts",
                git_commit=str(artifact["git_commit"]),
                expected_completion_digest=str(
                    artifact["completion_artifact_digest"]
                ),
            )
        elif task_key == P27_TASK_KEY:
            measurement_manifest = (
                load_repaired_measurement_validation_manifest(
                    self.root_dir
                    / "configs/research-os/"
                    "m4-information-theory-p2-6-1-measurement-validation-v1.json"
                )
            )
            synthetic = load_synthetic_run_manifest(
                self.root_dir
                / "configs/research-os/"
                "m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
            )
            p26_candidates = [
                (path, _load_object(path))
                for path in (
                    self.root_dir
                    / "runtime/research-os/mainline/tasks"
                    / P26_TASK_KEY
                ).glob("*/execution.json")
            ]
            p26_matches = [
                (path, payload)
                for path, payload in p26_candidates
                if payload.get("artifact_digest")
                == artifact.get("p26_execution_artifact_digest")
            ]
            if len(p26_matches) != 1:
                raise MainlineSupervisorError(
                    "P2.7 replay cannot resolve its unique P2.6 parent"
                )
            p26_path, p26_execution = p26_matches[0]
            p26_output = p26_path.parent / "artifacts"
            completion = _load_object(
                self.root_dir
                / str(p26_execution["completion_artifact_path"])
            )
            completion_replay = verify_completion_replay(
                manifest=measurement_manifest,
                synthetic=synthetic,
                parent_execution_id=str(p26_execution["execution_id"]),
                output_dir=p26_output,
                git_commit=str(p26_execution["git_commit"]),
                expected_completion_digest=str(
                    p26_execution["completion_artifact_digest"]
                ),
            )
            aggregates = [
                _load_object(path)
                for path in sorted(p26_output.glob("aggregates/*/*.json"))
            ]
            reconstructed_gate = evaluate_automatic_gate(
                manifest=measurement_manifest,
                completion=completion,
                aggregates=aggregates,
                deterministic_replay_passed=(
                    completion_replay["status"] == "REPLAY_VERIFIED"
                ),
            )
            if (
                reconstructed_gate["artifact_digest"]
                != artifact.get("automatic_gate_digest")
                or reconstructed_gate["mde_summary"]["artifact_digest"]
                != artifact.get("mde_summary_digest")
                or reconstructed_gate["decision"] != artifact.get("decision")
                or reconstructed_gate["decision_fact"]
                != artifact.get("decision_fact")
            ):
                raise MainlineSupervisorError(
                    "P2.7 automatic gate or MDE replay identity changed"
                )
            capability_replay = {
                "status": "REPLAY_VERIFIED",
                "completion_artifact_digest": completion[
                    "artifact_digest"
                ],
                "automatic_gate_digest": reconstructed_gate[
                    "artifact_digest"
                ],
                "mde_summary_digest": reconstructed_gate["mde_summary"][
                    "artifact_digest"
                ],
                "decision": reconstructed_gate["decision"],
                "decision_fact": reconstructed_gate["decision_fact"],
                "manual_input_assembly": False,
            }
        payload = {
            "schema_version": "dehps-research-evidence-supervisor-replay.v1",
            "status": "REPLAY_VERIFIED",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "control_plane_key": self.control_plane_key,
            "task_key": task_key,
            "execution_id": resolved_execution_id,
            "execution_artifact_digest": artifact["artifact_digest"],
            "actual_fold_count": artifact["actual_fold_count"],
            "registered_artifact_count": len(registrations),
            "same_execution_identity": True,
            "same_artifact_identity": True,
            "manual_input_assembly": False,
            "dispatch_performed": False,
        }
        if capability_replay is not None:
            payload["capability_replay"] = capability_replay
        self._write_state(payload)
        return payload

    def status(self) -> dict[str, Any]:
        if self.state_path.is_file():
            return _load_object(self.state_path)
        return {
            "schema_version": "dehps-research-evidence-supervisor-state.v1",
            "status": "NOT_STARTED",
            "control_plane_key": self.control_plane_key,
            "dispatch_performed": False,
        }

    def run_resident(self, *, interval_seconds: float = 15.0) -> None:
        if interval_seconds < 1:
            raise ValueError("resident supervisor interval must be at least one second")
        while True:
            try:
                self.run_once()
            except Exception as exc:
                payload = {
                    "schema_version": "dehps-research-evidence-supervisor-state.v1",
                    "status": "FAILED",
                    "control_plane_key": self.control_plane_key,
                    "error": str(exc),
                    "dispatch_performed": False,
                    "heartbeat_at": self.now().isoformat(),
                }
                self._write_state(payload)
            time.sleep(interval_seconds)

    def _completed_event(self, execution_id: str) -> dict[str, Any] | None:
        events = self.repository.list_mainline_execution_events(
            control_plane_key=self.control_plane_key,
            execution_id=execution_id,
        )
        completed = [event for event in events if event.get("event_type") == "completed"]
        if len(completed) > 1:
            raise MainlineSupervisorError("duplicate completed execution events")
        return None if not completed else completed[0]

    @staticmethod
    def _transition_manifest(
        manifest: ControlPlaneManifest,
        *,
        task_key: str,
        status: TaskStatus,
        classification: CompletionClassification,
        completion_fact: str | None = None,
        completion_facts: tuple[str, ...] = (),
        additional_completed_task_keys: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        payload = manifest.to_dict(include_digest=False)
        found = False
        additional = set(additional_completed_task_keys)
        located_additional: set[str] = set()
        for task in payload["tasks"]:
            if task["task_key"] == task_key:
                found = True
                task["status"] = status.value
                task["completion_classification"] = classification.value
            elif task["task_key"] in additional:
                located_additional.add(str(task["task_key"]))
                task["status"] = TaskStatus.COMPLETED.value
                task["completion_classification"] = (
                    CompletionClassification.COMPLETE.value
                )
        if not found:
            raise ResearchOSValidationError(f"task not found: {task_key}")
        missing_additional = additional - located_additional
        if missing_additional:
            raise ResearchOSValidationError(
                "additional completed tasks not found: "
                + ", ".join(sorted(missing_additional))
            )
        all_facts = set(completion_facts)
        if completion_fact is not None:
            all_facts.add(completion_fact)
        if all_facts:
            facts = set(payload["facts"]["artifacts"])
            facts.update(all_facts)
            payload["facts"]["artifacts"] = sorted(facts)
        return payload

    def _write_state(self, payload: Mapping[str, Any]) -> None:
        atomic_write_text(
            self.state_path,
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )

    def _build_lane_status(
        self,
        manifest: ControlPlaneManifest,
        *,
        snapshot: Any,
        dispatch_performed: bool,
        completed_summary: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.control_plane_key == PREDICTION_V2_CONTROL_PLANE_KEY:
            latest = completed_summary or self._latest_completed_summary_for_tasks(
                snapshot,
                (PREDICTION_V2_REPLAY_TASK_KEY, PREDICTION_V2_REFERENCE_TASK_KEY),
            )
            status = build_prediction_v2_status(
                manifest=manifest,
                snapshot=snapshot,
                execution=latest,
                dispatch_performed=dispatch_performed,
            )
            status["progress"] = {
                "engineering_percent": 100 if status["replay_verified"] else 0,
                "evidence_percent": 0,
            }
            return status
        return build_m4_status(
            manifest,
            snapshot=snapshot,
            mainline_execution=self._latest_completed_summary(snapshot),
            measurement_v2_execution=self._latest_completed_v2_summary(snapshot),
            dispatch_performed=dispatch_performed,
        )

    def _write_lane_status(self, payload: Mapping[str, Any]) -> None:
        status_name = (
            "prediction-v2-shadow-status.json"
            if self.control_plane_key == PREDICTION_V2_CONTROL_PLANE_KEY
            else "m4-information-theory-status.json"
        )
        atomic_write_text(
            self.root_dir / "runtime/logs" / status_name,
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )
