from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from dehps.research_os.information_theory.digest import config_digest


MEASUREMENT_VALIDATION_MANIFEST_DIGEST = (
    "953ae76e2e28523b7d067c2b73dac8bec63ff2417db283fd516fe900e52402f8"
)
PREREGISTRATION_DIGEST = (
    "4fff51c58e4a46d664e414bfe4cc0d7269c8e3712734153faec548648144d0d9"
)
DECISION_POLICY_DIGEST = (
    "824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d"
)
SYNTHETIC_MANIFEST_DIGEST = (
    "f84c2da3565f7eda41c3782517c78211805f57ea8f3bfd00659a93c380826a3c"
)
METRIC_KERNEL_DIGEST = (
    "56b9d0a62d43d167069e5222c7095383c9c5106bb3361b0b1def75cf2b6c86a2"
)
WALK_FORWARD_HARNESS_DIGEST = (
    "177a3d591b7557a4231a276bfb007f0d42a94d942824403f5376f94fe904d2ca"
)
INJECTED_SIGNAL_COMPLETION_DIGEST = (
    "328144fa1abebfee88d46dbbce6d9deb7b9f1f5834fb9a0c83cc55adef32a353"
)
RESAMPLING_KERNEL_DIGEST = (
    "1cde473524d7d6dcafba64ab7b0a1d2862b56149d5f6f198c73d88b406c3071b"
)


class MeasurementValidationContractError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class MeasurementValidationManifest:
    payload: Mapping[str, Any]
    artifact_digest: str
    scenario_replicates: int
    outer_issue_predictions: int
    bootstrap_replicates: int
    permutation_replicates: int
    negative_control_replicates: int
    coverage_lower: float
    coverage_upper: float
    practical_power_min: float
    strong_power_min: float


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise MeasurementValidationContractError(
            "measurement_validation_contract_invalid",
            f"{key} must be an object",
        )
    return value


def load_measurement_validation_manifest(
    path: Path,
) -> MeasurementValidationManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MeasurementValidationContractError(
            "measurement_validation_manifest_invalid",
            str(exc),
        ) from exc
    if not isinstance(payload, Mapping):
        raise MeasurementValidationContractError(
            "measurement_validation_manifest_invalid",
            "manifest root must be an object",
        )
    return validate_measurement_validation_manifest(payload)


def validate_measurement_validation_manifest(
    payload: Mapping[str, Any],
) -> MeasurementValidationManifest:
    if (
        payload.get("schema_version")
        != "dehps-m4-p2-measurement-validation-manifest.v1"
        or payload.get("artifact_type") != "measurement_validation_manifest"
        or payload.get("phase") != "M4-P2.6-P2.7"
        or payload.get("status") != "FROZEN"
        or payload.get("production_action") != "none"
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_contract_invalid",
            "manifest identity or governance changed",
        )
    supplied_digest = str(payload.get("artifact_digest") or "")
    calculated_digest = config_digest(payload)
    if (
        supplied_digest != calculated_digest
        or supplied_digest != MEASUREMENT_VALIDATION_MANIFEST_DIGEST
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_manifest_digest_mismatch",
            "the frozen P2.6 contract changed",
        )

    result_blind = _mapping(payload, "result_blind_freeze")
    if set(result_blind.values()) != {False}:
        raise MeasurementValidationContractError(
            "result_blind_freeze_invalid",
            "the P2.6 contract must precede every formal result",
        )

    upstream = _mapping(payload, "upstream_identities")
    expected_upstream = {
        "preregistration_digest": PREREGISTRATION_DIGEST,
        "decision_policy_digest": DECISION_POLICY_DIGEST,
        "synthetic_manifest_digest": SYNTHETIC_MANIFEST_DIGEST,
        "metric_kernel_digest": METRIC_KERNEL_DIGEST,
        "walk_forward_harness_digest": WALK_FORWARD_HARNESS_DIGEST,
        "injected_signal_completion_digest": INJECTED_SIGNAL_COMPLETION_DIGEST,
        "resampling_kernel_digest": RESAMPLING_KERNEL_DIGEST,
    }
    if dict(upstream) != expected_upstream:
        raise MeasurementValidationContractError(
            "measurement_validation_upstream_mismatch",
            "P2.6 must consume the accepted P2.1-P2.5 identities",
        )

    workload = _mapping(payload, "workload")
    schedule = workload.get("schedule")
    if not isinstance(schedule, list) or schedule != [
        {
            "scale_id": "HISTORICAL",
            "outer_issue_count": 2581,
            "scenario_ids": "ALL_13_FROZEN_SCENARIOS",
            "scenario_count": 13,
            "replicates_per_scenario": 1000,
        },
        {
            "scale_id": "FORWARD_61",
            "outer_issue_count": 61,
            "scenario_ids": "ALL_13_FROZEN_SCENARIOS",
            "scenario_count": 13,
            "replicates_per_scenario": 1000,
        },
        {
            "scale_id": "LONG",
            "outer_issue_count": 6062,
            "scenario_ids": [
                "NULL_UNIFORM",
                "MEDIUM_PRACTICAL_SINGLE_NUMBER",
                "MEDIUM_PRACTICAL_LOCAL_TEMPORAL",
                "MEDIUM_PRACTICAL_PAIR",
                "MEDIUM_PRACTICAL_MARGINAL_PRESERVING",
            ],
            "scenario_count": 5,
            "replicates_per_scenario": 1000,
        },
    ]:
        raise MeasurementValidationContractError(
            "measurement_validation_workload_invalid",
            "the complete three-scale schedule changed",
        )
    if (
        workload.get("scenario_replicates") != 31000
        or workload.get("outer_issue_predictions") != 64656000
        or workload.get("gate_probe") != "REGULARIZED_LOGISTIC_REGRESSION"
        or workload.get("missing_failed_or_duplicate_replicate") != "fail_closed"
        or workload.get("partial_scale_or_scenario_aggregation") != "forbidden"
        or workload.get("probe_allowlist")
        != [
            "EMPIRICAL_BASELINE",
            "REGULARIZED_LOGISTIC_REGRESSION",
            "NAIVE_BAYES",
            "SHALLOW_CALIBRATED_TREE",
        ]
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_workload_invalid",
            "workload, probes, or completeness rule changed",
        )

    resampling = _mapping(payload, "formal_resampling")
    if resampling != {
        "bootstrap_replicates": 2000,
        "permutation_replicates": 2000,
        "negative_control_replicates": 1000,
        "statistical_unit": "issue",
        "primary_block_size": 5,
        "sensitivity_block_sizes": [3, 5, 8, 13],
        "kernel_single_source": True,
    }:
        raise MeasurementValidationContractError(
            "measurement_validation_resampling_invalid",
            "P2.5 formal counts or issue-level semantics changed",
        )

    seeds = _mapping(payload, "seed_policy")
    if (
        seeds.get("root_seed_set_digest")
        != "b7fe8fab4e6fbb6387823d8354e6a9ac6da15b03f26ba0dc2ce7756f296e73b7"
        or seeds.get("replicate_orchestration_domain") != "M4_P2_POWER_REPLICATE"
        or seeds.get("evaluation_dataset_domain") != "M4_P2_EVALUATION_DATASET"
        or seeds.get("bootstrap_domain") != "M4_P2_BOOTSTRAP"
        or seeds.get("permutation_domain") != "M4_P2_ISSUE_PERMUTATION"
        or seeds.get("calibration_domain_reuse") != "forbidden"
        or seeds.get("wall_clock_seed") != "forbidden"
        or seeds.get("selection_policy") != "no_best_seed"
        or any(
            seeds.get(field) is not True
            for field in (
                "retry_reuses_child_seed",
                "resume_reuses_child_seed",
                "shard_change_preserves_child_seed",
            )
        )
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_seed_policy_invalid",
            "formal seed-domain separation changed",
        )

    estimator = _mapping(payload, "estimator_contract")
    if (
        _mapping(estimator, "PE1").get("unit") != "bits_per_issue"
        or _mapping(estimator, "PE2").get("definition")
        != "PE1_minus_permutation_null_center"
        or estimator.get("truth_target")
        != "P2.4_joint_draw_information_bits_per_issue_and_zero_for_NULL_UNIFORM"
        or estimator.get("absolute_bias_max_bits_per_issue") != 0.0025
        or estimator.get("rmse_role")
        != "required_descriptive_finite_value_gate_without_numeric_threshold"
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_estimator_invalid",
            "PE1, PE2, truth, bias, or RMSE semantics changed",
        )

    interval = _mapping(payload, "interval_contract")
    if (
        interval.get("confidence_level") != 0.95
        or interval.get("primary_method") != "moving_block_bootstrap_BCa"
        or interval.get("bootstrap_replicates") != 2000
        or interval.get("primary_block_size") != 5
        or interval.get("quantile_method") != "Hyndman-Fan_type_7"
        or interval.get("coverage_acceptance_interval") != [0.925, 0.975]
        or interval.get("silent_fallback") != "forbidden"
        or not isinstance(interval.get("bca_valid_when"), list)
        or len(interval["bca_valid_when"]) != 4
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_interval_invalid",
            "interval or coverage semantics changed",
        )

    detection = _mapping(payload, "detection_contract")
    if (
        detection.get("alpha") != 0.05
        or detection.get("tail") != "upper"
        or detection.get("primary_endpoint_family") != ["PE1", "PE2"]
        or detection.get("multiplicity") != "Holm"
        or detection.get("manual_or_partial_endpoint_override") != "forbidden"
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_detection_invalid",
            "final detection event changed",
        )

    false_positive = _mapping(payload, "false_positive_gate")
    if (
        false_positive.get("rate_max") != 0.075
        or false_positive.get("wilson_upper_95_max") != 0.09
        or false_positive.get("wilson_z") != 1.959963984540054
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_false_positive_gate_invalid",
            "false-positive thresholds changed",
        )

    power = _mapping(payload, "power_gates")
    if (
        power.get("practical_0_01_bits_per_issue_min") != 0.8
        or power.get("strong_0_05_bits_per_issue_min") != 0.95
        or "without_mechanism_or_scale_averaging"
        not in str(power.get("aggregation"))
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_power_gate_invalid",
            "practical, strong, or cell-local power semantics changed",
        )

    mde = _mapping(payload, "mde_contract")
    if (
        mde.get("target_power") != 0.8
        or mde.get("tested_strengths_bits_per_issue") != [0.001, 0.01, 0.05]
        or mde.get("interpolation") != "forbidden"
        or mde.get("decision_policy_mde_at_61")
        != "maximum_of_four_FORWARD_61_per_mechanism_conservative_MDE_upper_bounds"
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_mde_invalid",
            "the conservative tested-grid MDE contract changed",
        )

    gate = _mapping(payload, "automatic_gate")
    required = gate.get("PASS_TO_P3_requires_all")
    if (
        not isinstance(required, list)
        or len(required) != 10
        or gate.get("PASS_TO_P3_fact")
        != "m4-p2-measurement-decision:PASS_TO_P3"
        or gate.get("REPAIR_MEASUREMENT_SYSTEM_fact")
        != "m4-p2-measurement-decision:REPAIR_MEASUREMENT_SYSTEM"
        or gate.get("facts_mutually_exclusive") is not True
        or gate.get("manual_override") != "forbidden"
        or gate.get("P3_without_PASS_TO_P3_fact") != "unreachable"
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_automatic_gate_invalid",
            "the automatic PASS/REPAIR gate changed",
        )

    branch = _mapping(payload, "branch_contract")
    if branch != {
        "pass_fact": "m4-p2-measurement-decision:PASS_TO_P3",
        "repair_fact": "m4-p2-measurement-decision:REPAIR_MEASUREMENT_SYSTEM",
        "mutually_exclusive": True,
        "pass_consumer": "m4-p3-strict-historical-walk-forward",
        "repair_consumer": "m4-p2-repair-measurement-system",
        "P3_default": "closed",
    }:
        raise MeasurementValidationContractError(
            "measurement_validation_branch_invalid",
            "P3 and repair branch identities changed",
        )

    return MeasurementValidationManifest(
        payload=dict(payload),
        artifact_digest=supplied_digest,
        scenario_replicates=int(workload["scenario_replicates"]),
        outer_issue_predictions=int(workload["outer_issue_predictions"]),
        bootstrap_replicates=int(resampling["bootstrap_replicates"]),
        permutation_replicates=int(resampling["permutation_replicates"]),
        negative_control_replicates=int(
            resampling["negative_control_replicates"]
        ),
        coverage_lower=float(interval["coverage_acceptance_interval"][0]),
        coverage_upper=float(interval["coverage_acceptance_interval"][1]),
        practical_power_min=float(power["practical_0_01_bits_per_issue_min"]),
        strong_power_min=float(power["strong_0_05_bits_per_issue_min"]),
    )
