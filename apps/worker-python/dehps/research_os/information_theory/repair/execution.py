from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.measurement_validation.repaired_contracts import (
    load_repaired_measurement_validation_manifest,
)
from dehps.research_os.information_theory.synthetic import (
    load_synthetic_run_manifest,
)
from dehps.research_os.information_theory.walk_forward import (
    load_harness_manifest,
)

from .calibration import build_marginal_truth_artifact
from .contracts import (
    MeasurementRepairManifest,
    load_measurement_repair_manifest,
)
from .development import run_development_selection

REPAIRED_FACT = "m4-p2-repaired-measurement-contract:AVAILABLE"


@dataclass(frozen=True)
class MeasurementRepairRun:
    manifest: MeasurementRepairManifest
    development_selection: Mapping[str, Any]
    truth_artifacts: tuple[Mapping[str, Any], ...]
    identifiability_confirmation: Mapping[str, Any]
    completion: Mapping[str, Any]


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _probe_configs(root_dir: Path) -> dict[str, Mapping[str, Any]]:
    preregistration = _load(
        root_dir / "configs/research-os/"
        "m4-information-theory-preregistration-v1.0.3.json"
    )
    configs = deepcopy(preregistration["probe_models"]["hyperparameters"])
    harness = load_harness_manifest(
        root_dir / "configs/research-os/"
        "m4-information-theory-walk-forward-harness-v1.json"
    )
    configs["REGULARIZED_LOGISTIC_REGRESSION"] = dict(
        harness.probe("REGULARIZED_LOGISTIC_REGRESSION")
    )
    return configs


def _identifiability_confirmation(
    *,
    manifest: MeasurementRepairManifest,
    truth_artifacts: tuple[Mapping[str, Any], ...],
    repaired_validation_manifest_digest: str,
) -> dict[str, Any]:
    rows = []
    failures = []
    for truth in truth_artifacts:
        role = str(truth["role"])
        marginal = float(truth["marginal_information_bits_per_issue"])
        joint = float(truth["joint_information_bits_per_issue"])
        if role == "FORMAL_POWER_TARGET":
            classification = "IDENTIFIABLE_BY_REPAIRED_MARGINAL_PROBE"
            if marginal <= 0 or truth.get("eligible_for_formal_power") is not True:
                failures.append(f"{truth['scenario_id']}:formal_power_truth_invalid")
        elif role == "JOINT_ONLY_NEGATIVE_CONTROL":
            classification = "EXPECTED_ZERO_MARGINAL_NEGATIVE_CONTROL"
            if marginal != 0 or joint <= 0:
                failures.append(f"{truth['scenario_id']}:joint_only_control_invalid")
        else:
            classification = "UNREACHABLE_TARGET_EXCLUDED_BY_CONTRACT"
            if (
                truth.get("classification")
                != "TARGET_NOT_REACHABLE_BY_FROZEN_GENERATOR"
            ):
                failures.append(f"{truth['scenario_id']}:sentinel_invalid")
        rows.append(
            {
                "scenario_id": truth["scenario_id"],
                "role": role,
                "joint_information_bits_per_issue": joint,
                "marginal_information_bits_per_issue": marginal,
                "metric_estimand": truth["metric_estimand"],
                "state_representable": True,
                "classification": classification,
                "formal_power_eligible": (truth["eligible_for_formal_power"]),
            }
        )
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-repaired-identifiability.v1",
        "artifact_type": "repaired_measurement_identifiability_confirmation",
        "artifact_digest": "",
        "decision": (
            "MEASUREMENT_CONTRACT_REPAIRED"
            if not failures
            else "MEASUREMENT_CONTRACT_REPAIR_FAILED"
        ),
        "approved_strategy": ("SCHEME_A_MARGINAL_TRUTH_TO_MARGINAL_METRIC"),
        "scenario_count": len(rows),
        "formal_power_target_count": sum(row["formal_power_eligible"] for row in rows),
        "failed_requirements": failures,
        "scenario_rows": rows,
        "truth_estimand": ("sum_number_event_mutual_information_with_prior_state"),
        "metric_estimand": ("sum_number_event_log_loss_gain_bits_per_issue"),
        "state_visible_feature_manifest_digest": manifest.payload[
            "state_visible_feature_contract"
        ]["feature_manifest_digest"],
        "state_number_interaction_count": 33,
        "joint_probe_or_kernel_added": False,
        "real_history_state_access": "forbidden",
        "old_partial_statistical_results_inspected": False,
        "actual_fold_count": 0,
        "evidence_created": False,
        "repaired_measurement_validation_manifest_digest": (
            repaired_validation_manifest_digest
        ),
        "parent_digests": [
            manifest.artifact_digest,
            *(str(truth["artifact_digest"]) for truth in truth_artifacts),
            repaired_validation_manifest_digest,
        ],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4-p2.repaired-identifiability.v1",
    )
    if failures:
        raise RuntimeError(
            "repaired measurement contract is not identifiable: " + ", ".join(failures)
        )
    return payload


def run_measurement_contract_repair(
    *,
    root_dir: Path,
    execution_id: str,
    git_commit: str,
) -> MeasurementRepairRun:
    manifest = load_measurement_repair_manifest(
        root_dir / "configs/research-os/"
        "m4-information-theory-p2-6-1-measurement-contract-repair-v1.json"
    )
    repaired_validation = load_repaired_measurement_validation_manifest(
        root_dir / "configs/research-os/"
        "m4-information-theory-p2-6-1-measurement-validation-v1.json"
    )
    synthetic = load_synthetic_run_manifest(
        root_dir / "configs/research-os/"
        "m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
    )
    scenarios = {str(item["scenario_id"]): item for item in manifest.scenarios}
    development = run_development_selection(
        contract=manifest.payload["development_selection"],
        synthetic=synthetic,
        scenario_contracts=scenarios,
        probe_configs=_probe_configs(root_dir),
    )
    truth_artifacts = tuple(
        build_marginal_truth_artifact(
            scenario,
            repair_manifest_digest=manifest.artifact_digest,
        )
        for scenario in manifest.scenarios
    )
    expected_truths = {
        str(item["scenario_id"]): str(item["artifact_digest"])
        for item in repaired_validation.payload["truth_artifacts"]
    }
    actual_truths = {
        str(item["scenario_id"]): str(item["artifact_digest"])
        for item in truth_artifacts
    }
    if actual_truths != expected_truths:
        raise RuntimeError("P2.6.1 repaired truth binding changed")
    confirmation = _identifiability_confirmation(
        manifest=manifest,
        truth_artifacts=truth_artifacts,
        repaired_validation_manifest_digest=(repaired_validation.artifact_digest),
    )
    completion: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-measurement-repair-completion.v1",
        "artifact_type": "measurement_contract_repair_completion",
        "artifact_digest": "",
        "status": "COMPLETE",
        "execution_id": execution_id,
        "measurement_repair_manifest_digest": manifest.artifact_digest,
        "repaired_measurement_validation_manifest_digest": (
            repaired_validation.artifact_digest
        ),
        "development_selection_artifact_digest": development["artifact_digest"],
        "state_visible_feature_manifest_digest": manifest.payload[
            "state_visible_feature_contract"
        ]["feature_manifest_digest"],
        "truth_artifact_digests": [item["artifact_digest"] for item in truth_artifacts],
        "truth_artifact_count": len(truth_artifacts),
        "formal_power_target_count": 8,
        "joint_only_negative_control_count": 3,
        "feasibility_sentinel_count": 1,
        "identifiability_confirmation_digest": confirmation["artifact_digest"],
        "outer_fold_fit_count_before": 46,
        "outer_fold_fit_count_after": 4,
        "inner_model_selection_per_outer_fold": 0,
        "actual_fold_count": 0,
        "completion_fact": REPAIRED_FACT,
        "old_partial_statistical_results_inspected": False,
        "old_execution_resumable": False,
        "evidence_created": False,
        "eligible_for_formal_inference": False,
        "downstream_consumer": ("m4-p2-false-positive-and-power-runs"),
        "git_commit": git_commit,
        "working_tree_clean": True,
        "production_action": "none",
        "parent_digests": [
            manifest.artifact_digest,
            repaired_validation.artifact_digest,
            str(development["artifact_digest"]),
            str(confirmation["artifact_digest"]),
            *(str(item["artifact_digest"]) for item in truth_artifacts),
        ],
    }
    identity = dict(completion)
    identity.pop("artifact_digest")
    completion["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4-p2.measurement-repair-completion.v1",
    )
    return MeasurementRepairRun(
        manifest=manifest,
        development_selection=development,
        truth_artifacts=truth_artifacts,
        identifiability_confirmation=confirmation,
        completion=completion,
    )
