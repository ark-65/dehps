from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from dehps.research_os.information_theory.digest import config_digest

from .contracts import (
    MEASUREMENT_VALIDATION_MANIFEST_DIGEST,
    MeasurementValidationContractError,
    MeasurementValidationManifest,
    load_measurement_validation_manifest,
)

REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST = (
    "a4e46a434a4b2ef9fe56ed0390d58ca5a45bbad21685b81cb983f7261b3abf58"
)
MEASUREMENT_REPAIR_MANIFEST_DIGEST = (
    "5e41910553643e6559e78aa401fdcdd1e661b5709eaf55f0e73e694fb5a61355"
)
DEVELOPMENT_SELECTION_ARTIFACT_DIGEST = (
    "90459ebf8b88afcc60ee1177043e436b90b71c00b557f15e9e4d7026f37586f2"
)
STATE_VISIBLE_FEATURE_MANIFEST_DIGEST = (
    "1a76f46d7a47a134c1688657749bc040290f65a03dbc7c860e38144e02005981"
)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MeasurementValidationContractError(
            "repaired_measurement_validation_manifest_invalid",
            str(exc),
        ) from exc
    if not isinstance(value, dict):
        raise MeasurementValidationContractError(
            "repaired_measurement_validation_manifest_invalid",
            "manifest root must be an object",
        )
    return value


def load_repaired_measurement_validation_manifest(
    path: Path,
) -> MeasurementValidationManifest:
    payload = _load(path)
    supplied = str(payload.get("artifact_digest") or "")
    if (
        payload.get("schema_version")
        != "dehps-m4-p2-repaired-measurement-validation-manifest.v1"
        or payload.get("artifact_type")
        != "repaired_measurement_validation_manifest"
        or payload.get("phase") != "M4-P2.6.1"
        or payload.get("status") != "FROZEN"
        or payload.get("approved_strategy")
        != "SCHEME_A_MARGINAL_TRUTH_TO_MARGINAL_METRIC"
        or payload.get("production_action") != "none"
        or supplied != config_digest(payload)
        or supplied != REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST
    ):
        raise MeasurementValidationContractError(
            "repaired_measurement_validation_manifest_digest_mismatch",
            "frozen P2.6.1 identity or strategy changed",
        )
    if (
        payload.get("base_measurement_validation_manifest_digest")
        != MEASUREMENT_VALIDATION_MANIFEST_DIGEST
        or payload.get("measurement_repair_manifest_digest")
        != MEASUREMENT_REPAIR_MANIFEST_DIGEST
        or payload.get("development_selection_artifact_digest")
        != DEVELOPMENT_SELECTION_ARTIFACT_DIGEST
        or payload.get("state_visible_feature_manifest_digest")
        != STATE_VISIBLE_FEATURE_MANIFEST_DIGEST
    ):
        raise MeasurementValidationContractError(
            "repaired_measurement_validation_upstream_mismatch",
            "repair, development selection, or feature identity changed",
        )
    result_blind = payload.get("result_blind_freeze")
    if not isinstance(result_blind, dict) or set(result_blind.values()) != {
        False
    }:
        raise MeasurementValidationContractError(
            "repaired_measurement_validation_result_blind_invalid",
            "formal or old statistical outcomes may not define P2.6.1",
        )
    truths = payload.get("truth_artifacts")
    if not isinstance(truths, list) or len(truths) != 12:
        raise MeasurementValidationContractError(
            "repaired_measurement_validation_truth_invalid",
            "all twelve repaired truth dispositions are required",
        )
    roles = [str(item.get("role")) for item in truths if isinstance(item, dict)]
    if (
        len(roles) != 12
        or roles.count("FORMAL_POWER_TARGET") != 8
        or roles.count("JOINT_ONLY_NEGATIVE_CONTROL") != 3
        or roles.count("MARGINAL_FEASIBILITY_SENTINEL") != 1
        or len(
            {
                str(item.get("scenario_id"))
                for item in truths
                if isinstance(item, dict)
            }
        )
        != 12
    ):
        raise MeasurementValidationContractError(
            "repaired_measurement_validation_truth_invalid",
            "P2.6.1 scenario roles changed",
        )
    fit = payload.get("frozen_probe_configs")
    if (
        not isinstance(fit, dict)
        or fit.get("inner_model_selection_per_outer_fold") != 0
        or fit.get("total_estimator_and_calibrator_fits_per_outer_fold")
        != 4
        or fit.get("REGULARIZED_LOGISTIC_REGRESSION", {}).get("selected_C")
        != 0.1
        or fit.get("NAIVE_BAYES", {}).get("selected_alpha") != 2.0
        or fit.get("SHALLOW_CALIBRATED_TREE", {}).get(
            "selected_max_depth"
        )
        != 2
        or fit.get("SHALLOW_CALIBRATED_TREE", {}).get(
            "selected_min_samples_leaf"
        )
        != 50
    ):
        raise MeasurementValidationContractError(
            "repaired_measurement_validation_probe_invalid",
            "frozen development selection or four-fit budget changed",
        )
    gate = payload.get("gate_scope")
    if (
        not isinstance(gate, dict)
        or len(gate.get("formal_power_scenarios", [])) != 8
        or gate.get("strong_pair_excluded_as_unreachable") is not True
        or gate.get("joint_only_controls_excluded_from_power_gate")
        is not True
        or gate.get("manual_override") != "forbidden"
    ):
        raise MeasurementValidationContractError(
            "repaired_measurement_validation_gate_invalid",
            "feasible power-cell gate scope changed",
        )

    base_path = path.with_name(
        "m4-information-theory-p2-6-measurement-validation-v1.json"
    )
    base = load_measurement_validation_manifest(base_path)
    repair_path = path.with_name(
        "m4-information-theory-p2-6-1-measurement-contract-repair-v1.json"
    )
    repair_payload = _load(repair_path)
    if (
        repair_payload.get("artifact_digest")
        != MEASUREMENT_REPAIR_MANIFEST_DIGEST
        or config_digest(repair_payload) != MEASUREMENT_REPAIR_MANIFEST_DIGEST
    ):
        raise MeasurementValidationContractError(
            "repaired_measurement_validation_upstream_mismatch",
            "measurement repair manifest changed",
        )
    scenario_contracts = repair_payload.get("scenario_contracts")
    if not isinstance(scenario_contracts, list):
        raise MeasurementValidationContractError(
            "repaired_measurement_validation_truth_invalid",
            "repair scenario contracts are missing",
        )
    effective = deepcopy(dict(base.payload))
    effective.update(
        {
            "schema_version": payload["schema_version"],
            "artifact_type": payload["artifact_type"],
            "artifact_digest": supplied,
            "phase": payload["phase"],
            "created_at": payload["created_at"],
            "base_measurement_validation_manifest_digest": (
                MEASUREMENT_VALIDATION_MANIFEST_DIGEST
            ),
            "measurement_repair_manifest_digest": (
                MEASUREMENT_REPAIR_MANIFEST_DIGEST
            ),
            "development_selection_artifact_digest": (
                DEVELOPMENT_SELECTION_ARTIFACT_DIGEST
            ),
            "state_visible_feature_manifest_digest": (
                STATE_VISIBLE_FEATURE_MANIFEST_DIGEST
            ),
            "scenario_contracts": scenario_contracts,
            "truth_artifacts": truths,
            "repaired_gate_scope": gate,
            "frozen_probe_configs": fit,
            "result_blind_freeze": result_blind,
        }
    )
    effective["estimator_contract"] = {
        **dict(effective["estimator_contract"]),
        "truth_target": (
            "marginal_information_bits_per_issue_and_zero_for_NULL_UNIFORM"
        ),
    }
    effective["automatic_gate"] = {
        **dict(effective["automatic_gate"]),
        "PASS_TO_P3_requires_all": [
            "all_31000_analysis_replicates_and_frozen_seeds_complete_exactly_once",
            "all_bootstrap_and_permutation_seed_sets_complete",
            "all_NULL_UNIFORM_point_and_Wilson_false_positive_gates_pass",
            "all_joint_only_marginal_controls_false_positive_gates_pass",
            "all_practical_strength_cell_power_gates_pass",
            "all_strong_signal_cell_power_gates_pass",
            "all_primary_PE2_absolute_bias_cell_gates_pass",
            "all_primary_PE2_coverage_cell_gates_pass",
            "all_RMSE_outputs_finite",
            "all_leakage_checks_pass",
            "deterministic_replay_passes",
        ],
    }
    return MeasurementValidationManifest(
        payload=effective,
        artifact_digest=supplied,
        scenario_replicates=base.scenario_replicates,
        outer_issue_predictions=base.outer_issue_predictions,
        bootstrap_replicates=base.bootstrap_replicates,
        permutation_replicates=base.permutation_replicates,
        negative_control_replicates=base.negative_control_replicates,
        coverage_lower=base.coverage_lower,
        coverage_upper=base.coverage_upper,
        practical_power_min=base.practical_power_min,
        strong_power_min=base.strong_power_min,
    )
