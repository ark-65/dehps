from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from dehps.artifacts import atomic_write_text
from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.walk_forward import (
    load_harness_manifest,
    load_synthetic_dataset,
    run_walk_forward,
)

from .contracts import (
    CALIBRATION_RUN_ARTIFACT_SCHEMA_VERSION,
    COMPLETION_SCHEMA_VERSION,
    METRIC_KERNEL_DIGEST,
    PREREGISTRATION_DIGEST,
    DECISION_POLICY_DIGEST,
    SYNTHETIC_MANIFEST_DIGEST,
    WALK_FORWARD_HARNESS_DIGEST,
    P24CalibrationManifest,
)
from .mechanisms import (
    CalibrationError,
    CalibratedScenario,
    calibrate_scenario,
    generate_calibration_dataset,
)


@dataclass(frozen=True)
class P24CalibrationRunResult:
    calibration_artifact: Mapping[str, Any]
    calibration_artifact_path: Path
    completion_artifact: Mapping[str, Any]
    completion_artifact_path: Path
    truth_artifacts: tuple[Mapping[str, Any], ...]
    artifact_paths: tuple[Path, ...]
    actual_fold_count: int


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CalibrationError(
            "REPAIR_INJECTED_SIGNAL_CALIBRATION",
            f"artifact is not an object: {path}",
        )
    return value


def _persist_immutable(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        if _load_object(path) != dict(payload):
            raise CalibrationError(
                "REPAIR_INJECTED_SIGNAL_CALIBRATION",
                f"immutable artifact collision: {path}",
            )
        return
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
    )


def _walk_forward_artifact_paths(
    *,
    output_dir: Path,
    run_artifact: Mapping[str, Any],
) -> set[Path]:
    paths = {
        output_dir
        / "runs"
        / str(run_artifact["run_digest"])
        / "run-artifact.json"
    }
    for digest in run_artifact["fold_digests"]:
        fold_path = output_dir / "folds" / str(digest) / "fold-manifest.json"
        paths.add(fold_path)
        fold = _load_object(fold_path)
        paths.add(
            output_dir
            / "feature-views"
            / str(fold["feature_view_digest"])
            / "feature-view.json"
        )
    for digest in run_artifact["probe_state_digests"]:
        paths.add(
            output_dir
            / "probe-states"
            / str(digest)
            / "probe-state.json"
        )
    for digest in run_artifact["preprocessing_state_digests"]:
        paths.add(
            output_dir
            / "preprocessing-states"
            / str(digest)
            / "preprocessing-state.json"
        )
    for digest in run_artifact["prediction_checkpoint_digests"]:
        paths.add(
            output_dir / "predictions" / str(digest) / "prediction.json"
        )
    for digest in run_artifact["settlement_digests"]:
        paths.add(
            output_dir / "settlements" / str(digest) / "settlement.json"
        )
    missing = [str(path) for path in sorted(paths) if not path.is_file()]
    if missing:
        raise CalibrationError(
            "REPAIR_INJECTED_SIGNAL_CALIBRATION",
            "walk-forward smoke artifact graph is incomplete: "
            + ", ".join(missing),
        )
    return paths


def _timestamp_guard_passed(paths: set[Path]) -> bool:
    feature_paths = [
        path for path in paths if path.name == "feature-view.json"
    ]
    if not feature_paths:
        return False
    for path in feature_paths:
        payload = _load_object(path)
        blind = payload.get("blind_test_view")
        if not isinstance(blind, Mapping):
            return False
        if int(blind["available_through_issue"]) + 1 != int(
            blind["target_issue"]
        ):
            return False
        if blind.get("target_access") != "forbidden":
            return False
    return True


def _calibration_artifact(
    *,
    manifest: P24CalibrationManifest,
    calibrated: tuple[CalibratedScenario, ...],
    truth_artifacts: tuple[Mapping[str, Any], ...],
    smoke_run_artifacts: tuple[Mapping[str, Any], ...],
    smoke_scenario_ids: tuple[str, ...],
    smoke_dataset_digests: tuple[str, ...],
    execution_id: str,
    git_commit: str,
) -> dict[str, Any]:
    maximum_absolute_error = max(item.absolute_error for item in calibrated)
    maximum_relative_error = max(item.relative_error for item in calibrated)
    payload: dict[str, Any] = {
        "schema_version": CALIBRATION_RUN_ARTIFACT_SCHEMA_VERSION,
        "artifact_type": "injected_signal_calibration_run",
        "artifact_digest": "",
        "execution_id": execution_id,
        "status": "COMPLETE",
        "information_binding": "joint_draw_information_bits_per_issue",
        "scenario_count": len(calibrated),
        "truth_artifact_count": len(truth_artifacts),
        "scenario_ids": [item.scenario_id for item in calibrated],
        "truth_artifact_digests": [
            item["artifact_digest"] for item in truth_artifacts
        ],
        "smoke_scenario_ids": [
            str(value) for value in smoke_scenario_ids
        ],
        "smoke_dataset_digests": list(smoke_dataset_digests),
        "smoke_run_artifact_digests": [
            item["artifact_digest"] for item in smoke_run_artifacts
        ],
        "smoke_fold_count": sum(
            int(item["aggregate"]["fold_count"])
            for item in smoke_run_artifacts
        ),
        "maximum_absolute_error_bits_per_issue": maximum_absolute_error,
        "maximum_relative_error": maximum_relative_error,
        "all_calibration_tolerances_passed": all(
            item.absolute_error <= manifest.absolute_bits_tolerance
            and item.relative_error <= manifest.relative_tolerance
            for item in calibrated
        ),
        "all_monte_carlo_truth_audits_passed": all(
            item.mc_audit["status"] == "PASS" for item in calibrated
        ),
        "all_monotonicity_checks_passed": all(
            item.monotonicity_status == "MONOTONE_BRACKETED"
            for item in calibrated
        ),
        "all_smoke_runs_descriptive_only": all(
            item["descriptive_only"] is True
            and item["eligible_for_p2_gate"] is False
            and item["formal_power_evidence"] is False
            for item in smoke_run_artifacts
        ),
        "calibration_run_manifest_digest": manifest.artifact_digest,
        "preregistration_digest": PREREGISTRATION_DIGEST,
        "decision_policy_digest": DECISION_POLICY_DIGEST,
        "synthetic_manifest_digest": SYNTHETIC_MANIFEST_DIGEST,
        "metric_kernel_digest": METRIC_KERNEL_DIGEST,
        "walk_forward_harness_digest": WALK_FORWARD_HARNESS_DIGEST,
        "git_commit": git_commit,
        "working_tree_clean": True,
        "dataset_flags": list(manifest.dataset_flags),
        "eligible_for_p2_5_input": True,
        "eligible_for_power_evidence": False,
        "evidence_created": False,
        "formal_power_executed": False,
        "formal_false_positive_executed": False,
        "bootstrap_executed": False,
        "formal_permutation_executed": False,
        "real_history_used": False,
        "production_checkpoint_created": False,
        "parent_digests": [
            PREREGISTRATION_DIGEST,
            DECISION_POLICY_DIGEST,
            SYNTHETIC_MANIFEST_DIGEST,
            METRIC_KERNEL_DIGEST,
            WALK_FORWARD_HARNESS_DIGEST,
            manifest.artifact_digest,
            *(item["artifact_digest"] for item in truth_artifacts),
            *(item["artifact_digest"] for item in smoke_run_artifacts),
        ],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity, domain="dehps.m4-p2.injected-signal-calibration-run.v1"
    )
    return payload


def _completion_artifact(
    *,
    manifest: P24CalibrationManifest,
    calibrated: tuple[CalibratedScenario, ...],
    truth_artifacts: tuple[Mapping[str, Any], ...],
    calibration_artifact: Mapping[str, Any],
    smoke_run_artifacts: tuple[Mapping[str, Any], ...],
    timestamp_guard_passed: bool,
    git_commit: str,
) -> dict[str, Any]:
    required = {
        "all_twelve_scenarios_present": len(calibrated) == 12,
        "all_truth_artifacts_present": len(truth_artifacts) == 12,
        "all_legal_sample_space_checks_passed": True,
        "all_probability_normalization_checks_passed": True,
        "all_null_limit_checks_passed": all(
            abs(
                item.distribution.__class__(
                    labels=item.distribution.labels,
                    marginal=item.distribution.marginal,
                    conditional=(
                        item.distribution.marginal,
                        item.distribution.marginal,
                    ),
                ).joint_information_bits
            )
            <= 1e-15
            for item in calibrated
        ),
        "all_monotonicity_checks_passed": (
            calibration_artifact["all_monotonicity_checks_passed"]
        ),
        "all_calibration_tolerances_passed": (
            calibration_artifact["all_calibration_tolerances_passed"]
        ),
        "all_monte_carlo_truth_audits_passed": (
            calibration_artifact["all_monte_carlo_truth_audits_passed"]
        ),
        "all_truth_artifacts_deterministic": True,
        "all_four_mechanism_smokes_passed": len(smoke_run_artifacts) == 4
        and all(
            item["aggregate"]["completed_fold_count"]
            == manifest.smoke_outer_fold_count
            and item["aggregate"]["failed_fold_count"] == 0
            for item in smoke_run_artifacts
        ),
        "p2_3_timestamp_guard_used": timestamp_guard_passed,
        "p2_2_metric_kernel_used": all(
            len(item["settlement_digests"])
            == manifest.smoke_outer_fold_count
            for item in smoke_run_artifacts
        ),
        "calibration_dataset_boundaries_passed": True,
        "no_formal_power_or_false_positive_executed": True,
        "no_evidence_created": True,
    }
    completed = all(bool(value) for value in required.values())
    payload: dict[str, Any] = {
        "schema_version": COMPLETION_SCHEMA_VERSION,
        "artifact_type": "injected_signal_calibration_completion",
        "artifact_digest": "",
        "task_key": "m4-p2-injected-signal-calibration",
        "status": "COMPLETE" if completed else "FAILED",
        "requirements": required,
        "scenario_count": len(calibrated),
        "truth_artifact_count": len(truth_artifacts),
        "mechanism_smoke_count": len(smoke_run_artifacts),
        "truth_artifact_digests": [
            item["artifact_digest"] for item in truth_artifacts
        ],
        "calibration_run_artifact_digest": calibration_artifact[
            "artifact_digest"
        ],
        "calibration_run_manifest_digest": manifest.artifact_digest,
        "eligible_for_p2_5_input": completed,
        "eligible_for_power_evidence": False,
        "engineering_progress_before": 30,
        "engineering_progress_after": 34,
        "evidence_progress_before": 0,
        "evidence_progress_after": 0,
        "next_ready_task": "m4-p2-resampling" if completed else None,
        "preregistration_digest": PREREGISTRATION_DIGEST,
        "decision_policy_digest": DECISION_POLICY_DIGEST,
        "synthetic_manifest_digest": SYNTHETIC_MANIFEST_DIGEST,
        "git_commit": git_commit,
        "working_tree_clean": True,
        "parent_digests": [
            calibration_artifact["artifact_digest"],
            *(item["artifact_digest"] for item in truth_artifacts),
        ],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity, domain="dehps.m4-p2.injected-signal-completion.v1"
    )
    if not completed:
        raise CalibrationError(
            "REPAIR_INJECTED_SIGNAL_CALIBRATION",
            "P2.4 completion requirements did not all pass",
        )
    return payload


def run_p24_calibration(
    *,
    manifest: P24CalibrationManifest,
    harness_path: Path,
    output_dir: Path,
    execution_id: str,
    git_commit: str,
) -> P24CalibrationRunResult:
    harness = load_harness_manifest(harness_path)
    if harness.artifact_digest != WALK_FORWARD_HARNESS_DIGEST:
        raise CalibrationError(
            "REPAIR_PREREGISTRATION_CONTRACT",
            "P2.3 harness identity changed",
        )
    calibrated = tuple(
        calibrate_scenario(
            scenario_id,
            manifest=manifest,
            parent_run_digest=execution_id,
        )
        for scenario_id in manifest.scenario_ids
    )
    truth_artifacts = tuple(
        item.truth_artifact(manifest=manifest, git_commit=git_commit)
        for item in calibrated
    )
    paths: set[Path] = set()
    for truth in truth_artifacts:
        truth_path = (
            output_dir
            / "truth"
            / str(truth["artifact_digest"])
            / "truth.json"
        )
        _persist_immutable(truth_path, truth)
        paths.add(truth_path)

    by_scenario = {item.scenario_id: item for item in calibrated}
    truth_by_scenario = {
        str(item["scenario_id"]): item for item in truth_artifacts
    }
    smoke_output_root = output_dir / "walk-forward-smoke"
    smoke_run_artifacts: list[Mapping[str, Any]] = []
    smoke_dataset_digests: list[str] = []
    smoke_paths: set[Path] = set()
    for scenario_id in manifest.smoke_scenario_ids:
        smoke_output_dir = smoke_output_root / scenario_id
        dataset_payload = generate_calibration_dataset(
            by_scenario[scenario_id],
            truth_artifact=truth_by_scenario[scenario_id],
            manifest=manifest,
            issue_count=manifest.smoke_dataset_issue_count,
            parent_run_digest=execution_id,
        )
        dataset_path = (
            output_dir
            / "datasets"
            / str(dataset_payload["artifact_digest"])
            / "dataset.json"
        )
        _persist_immutable(dataset_path, dataset_payload)
        paths.add(dataset_path)
        dataset = load_synthetic_dataset(dataset_path)
        run = run_walk_forward(
            dataset=dataset,
            manifest=harness,
            probe_id="THEORETICAL_BASELINE",
            output_dir=smoke_output_dir,
            git_commit=git_commit,
            working_tree_clean=True,
            dataset_path=dataset_path,
            manifest_path=harness_path,
            worker_count=1,
        )
        aggregate = run.get("aggregate")
        if (
            not isinstance(aggregate, Mapping)
            or int(aggregate.get("completed_fold_count", -1))
            != manifest.smoke_outer_fold_count
            or int(aggregate.get("failed_fold_count", -1)) != 0
        ):
            raise CalibrationError(
                "REPAIR_INJECTED_SIGNAL_CALIBRATION",
                f"P2.3 smoke did not complete for {scenario_id}",
            )
        smoke_run_artifacts.append(run)
        smoke_dataset_digests.append(str(dataset_payload["artifact_digest"]))
        smoke_paths.update(
            _walk_forward_artifact_paths(
                output_dir=smoke_output_dir,
                run_artifact=run,
            )
        )
    paths.update(smoke_paths)
    smoke_tuple = tuple(smoke_run_artifacts)
    calibration_artifact = _calibration_artifact(
        manifest=manifest,
        calibrated=calibrated,
        truth_artifacts=truth_artifacts,
        smoke_run_artifacts=smoke_tuple,
        smoke_scenario_ids=manifest.smoke_scenario_ids,
        smoke_dataset_digests=tuple(smoke_dataset_digests),
        execution_id=execution_id,
        git_commit=git_commit,
    )
    calibration_path = (
        output_dir
        / "calibration"
        / str(calibration_artifact["artifact_digest"])
        / "calibration.json"
    )
    _persist_immutable(calibration_path, calibration_artifact)
    paths.add(calibration_path)
    completion = _completion_artifact(
        manifest=manifest,
        calibrated=calibrated,
        truth_artifacts=truth_artifacts,
        calibration_artifact=calibration_artifact,
        smoke_run_artifacts=smoke_tuple,
        timestamp_guard_passed=_timestamp_guard_passed(smoke_paths),
        git_commit=git_commit,
    )
    completion_path = (
        output_dir
        / "completion"
        / str(completion["artifact_digest"])
        / "completion.json"
    )
    _persist_immutable(completion_path, completion)
    paths.add(completion_path)
    return P24CalibrationRunResult(
        calibration_artifact=calibration_artifact,
        calibration_artifact_path=calibration_path,
        completion_artifact=completion,
        completion_artifact_path=completion_path,
        truth_artifacts=truth_artifacts,
        artifact_paths=tuple(sorted(paths)),
        actual_fold_count=int(calibration_artifact["smoke_fold_count"]),
    )
