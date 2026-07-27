from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

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
    METRIC_KERNEL_DIGEST as P24_METRIC_KERNEL_DIGEST,
    PREREGISTRATION_DIGEST as P24_PREREGISTRATION_DIGEST,
    SYNTHETIC_MANIFEST_DIGEST as P24_SYNTHETIC_MANIFEST_DIGEST,
    WALK_FORWARD_HARNESS_DIGEST as P24_WALK_FORWARD_HARNESS_DIGEST,
)
from dehps.research_os.information_theory.metrics import load_metric_kernel_manifest
from dehps.research_os.information_theory.progress import build_m4_status
from dehps.research_os.information_theory.resampling import (
    KERNEL_MANIFEST_DIGEST,
    load_resampling_manifest,
    run_p25_resampling,
)
from dehps.research_os.information_theory.resampling.contracts import (
    DECISION_POLICY_DIGEST as P25_DECISION_POLICY_DIGEST,
    METRIC_KERNEL_DIGEST as P25_METRIC_KERNEL_DIGEST,
    P24_COMPLETION_DIGEST as P25_P24_COMPLETION_DIGEST,
    PREREGISTRATION_DIGEST as P25_PREREGISTRATION_DIGEST,
    SYNTHETIC_MANIFEST_DIGEST as P25_SYNTHETIC_MANIFEST_DIGEST,
    WALK_FORWARD_HARNESS_DIGEST as P25_WALK_FORWARD_HARNESS_DIGEST,
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
MAINLINE_EXECUTION_SCHEMA = "dehps-research-os-mainline-execution.v1"


class MainlineSupervisorError(RuntimeError):
    pass


@dataclass(frozen=True)
class CapabilityResult:
    execution_artifact: Mapping[str, Any]
    execution_artifact_path: Path
    registrations: tuple[MainlineArtifactRegistration, ...]


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
                git_commit=git_commit,
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
        }

    @property
    def state_path(self) -> Path:
        return self.root_dir / "runtime/logs/research-evidence-supervisor-state.json"

    def run_once(self, *, task_key: str | None = None) -> dict[str, Any]:
        self.repository.ensure_schema()
        git_commit = self.git_commit or resolve_git_commit(self.root_dir)
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
                    raise MainlineSupervisorError(
                        "running execution git commit differs from the current clean tree"
                    )
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
        summary = _event_payload(event)
        completion_fact = mainline_completion_fact(
            task=task,
            execution_id=execution_id,
        )
        completed_manifest = self._transition_manifest(
            manifest,
            task_key=task.task_key,
            status=TaskStatus.COMPLETED,
            classification=CompletionClassification.COMPLETE,
            completion_fact=completion_fact,
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
        status = build_m4_status(
            final_manifest,
            snapshot=final_snapshot,
            mainline_execution=summary,
            dispatch_performed=True,
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
        ):
            if key in summary:
                payload[key] = summary[key]
        self._write_state(payload)
        self._write_m4_status(status)
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
    ) -> dict[str, Any]:
        payload = manifest.to_dict(include_digest=False)
        found = False
        for task in payload["tasks"]:
            if task["task_key"] != task_key:
                continue
            found = True
            task["status"] = status.value
            task["completion_classification"] = classification.value
        if not found:
            raise ResearchOSValidationError(f"task not found: {task_key}")
        if completion_fact is not None:
            facts = set(payload["facts"]["artifacts"])
            facts.add(completion_fact)
            payload["facts"]["artifacts"] = sorted(facts)
        return payload

    def _write_state(self, payload: Mapping[str, Any]) -> None:
        atomic_write_text(
            self.state_path,
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )

    def _write_m4_status(self, payload: Mapping[str, Any]) -> None:
        atomic_write_text(
            self.root_dir / "runtime/logs/m4-information-theory-status.json",
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )
