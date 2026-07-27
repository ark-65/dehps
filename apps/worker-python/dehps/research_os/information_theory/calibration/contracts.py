from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from dehps.research_os.information_theory.digest import config_digest


CALIBRATION_SCHEMA_VERSION = (
    "dehps-m4-p2-injected-signal-calibration-run.v1"
)
TRUTH_SCHEMA_VERSION = "dehps-m4-p2-injected-signal-truth.v1"
COMPLETION_SCHEMA_VERSION = "dehps-m4-p2-injected-signal-completion.v1"
CALIBRATION_RUN_ARTIFACT_SCHEMA_VERSION = (
    "dehps-m4-p2-injected-signal-calibration-artifact.v1"
)
CALIBRATION_RUN_MANIFEST_DIGEST = (
    "f30186e3f5aeefb07565d25c4e0de68d955a07e87d1894fdaedbe8bedf4a2317"
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
CALIBRATION_DATASET_FLAGS = (
    "CALIBRATION_ONLY",
    "NOT_EVALUATION_DATA",
    "NOT_POWER_DATA",
    "NOT_FALSE_POSITIVE_DATA",
    "NOT_P2_GATE_EVIDENCE",
)
EXPECTED_SCENARIOS = (
    "WEAK_SINGLE_NUMBER",
    "WEAK_LOCAL_TEMPORAL",
    "WEAK_PAIR",
    "WEAK_MARGINAL_PRESERVING",
    "MEDIUM_PRACTICAL_SINGLE_NUMBER",
    "MEDIUM_PRACTICAL_LOCAL_TEMPORAL",
    "MEDIUM_PRACTICAL_PAIR",
    "MEDIUM_PRACTICAL_MARGINAL_PRESERVING",
    "STRONG_SINGLE_NUMBER",
    "STRONG_LOCAL_TEMPORAL",
    "STRONG_PAIR",
    "STRONG_MARGINAL_PRESERVING",
)
EXPECTED_MECHANISMS = (
    "single_number_conditional_shift",
    "local_temporal_state",
    "pair_conditional_signal",
    "marginal_preserving_conditional_signal",
)


class CalibrationContractError(ValueError):
    pass


@dataclass(frozen=True)
class P24CalibrationManifest:
    payload: Mapping[str, Any]
    artifact_digest: str
    scenario_ids: tuple[str, ...]
    smoke_scenario_ids: tuple[str, ...]
    smoke_dataset_issue_count: int
    smoke_outer_fold_count: int
    absolute_bits_tolerance: float
    relative_tolerance: float
    maximum_iterations: int
    parameter_width_tolerance: float
    monotonicity_grid_points: int
    mc_standard_error_tolerance: float
    mc_agreement_standard_errors: int
    mc_sample_schedule: tuple[int, ...]
    root_seed_set_digest: str
    dataset_flags: tuple[str, ...]


def load_calibration_manifest(path: Path) -> P24CalibrationManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CalibrationContractError(str(exc)) from exc
    if not isinstance(payload, Mapping):
        raise CalibrationContractError("calibration manifest must be an object")
    return validate_calibration_manifest(payload)


def validate_calibration_manifest(
    payload: Mapping[str, Any],
) -> P24CalibrationManifest:
    if (
        payload.get("schema_version") != CALIBRATION_SCHEMA_VERSION
        or payload.get("artifact_type")
        != "injected_signal_calibration_run_manifest"
        or payload.get("phase") != "M4-P2.4"
        or payload.get("status") != "FROZEN"
    ):
        raise CalibrationContractError("P2.4 calibration manifest is not frozen")
    expected_identities = {
        "preregistration_digest": PREREGISTRATION_DIGEST,
        "decision_policy_digest": DECISION_POLICY_DIGEST,
        "synthetic_manifest_digest": SYNTHETIC_MANIFEST_DIGEST,
        "metric_kernel_digest": METRIC_KERNEL_DIGEST,
        "walk_forward_harness_digest": WALK_FORWARD_HARNESS_DIGEST,
        "information_binding": "joint_draw_information_bits_per_issue",
    }
    for field, expected in expected_identities.items():
        if payload.get(field) != expected:
            raise CalibrationContractError(f"{field} changed")
    if tuple(payload.get("scenario_ids", ())) != EXPECTED_SCENARIOS:
        raise CalibrationContractError("all twelve frozen scenarios are required")
    if tuple(payload.get("mechanisms", ())) != EXPECTED_MECHANISMS:
        raise CalibrationContractError("all four frozen mechanisms are required")
    if payload.get("strengths_bits_per_issue") != [0.001, 0.01, 0.05]:
        raise CalibrationContractError("frozen strength set changed")
    calibration = payload.get("calibration")
    if not isinstance(calibration, Mapping) or dict(calibration) != {
        "method": "exact_analytic_or_deterministic_legal_space_sum",
        "solver": "deterministic_bisection",
        "absolute_bits_tolerance": 1e-10,
        "relative_tolerance": 1e-6,
        "maximum_iterations": 128,
        "parameter_width_tolerance": 1e-14,
        "monotonicity_grid_points": 65,
        "bracket_required": True,
        "extrapolation": "forbidden",
    }:
        raise CalibrationContractError("calibration solver contract changed")
    mc = payload.get("monte_carlo_truth_audit")
    if not isinstance(mc, Mapping) or dict(mc) != {
        "role": "independent_non_calibrating_confirmation",
        "maximum_standard_error_bits_per_issue": 0.00025,
        "agreement_standard_errors": 4,
        "sample_schedule": [
            262144,
            524288,
            1048576,
            2097152,
            4194304,
            8388608,
        ],
        "maximum_samples": 8388608,
        "seed_domain": "M4_P2_CALIBRATION",
        "method_id": "independent_truth_audit",
    }:
        raise CalibrationContractError("Monte Carlo audit contract changed")
    seeds = payload.get("seed_policy")
    if not isinstance(seeds, Mapping) or (
        seeds.get("seed_domain") != "M4_P2_CALIBRATION"
        or seeds.get("selection_policy") != "no_best_seed"
        or seeds.get("wall_clock_seed") != "forbidden"
        or seeds.get("retry_reuses_child_seed") is not True
        or seeds.get("resume_reuses_child_seed") is not True
        or seeds.get("shard_change_preserves_child_seed") is not True
        or seeds.get("domain_enters_artifact_digest") is not True
    ):
        raise CalibrationContractError("calibration seed policy changed")
    root_seed_set_digest = str(seeds.get("root_seed_set_digest", ""))
    if len(root_seed_set_digest) != 64:
        raise CalibrationContractError("root seed-set digest is missing")
    smoke = payload.get("smoke_execution")
    if not isinstance(smoke, Mapping) or dict(smoke) != {
        "scenario_ids": [
            "MEDIUM_PRACTICAL_SINGLE_NUMBER",
            "MEDIUM_PRACTICAL_LOCAL_TEMPORAL",
            "MEDIUM_PRACTICAL_PAIR",
            "MEDIUM_PRACTICAL_MARGINAL_PRESERVING",
        ],
        "dataset_issue_count": 902,
        "minimum_training_issues": 900,
        "outer_fold_count": 2,
        "probe_id": "THEORETICAL_BASELINE",
        "walk_forward_harness": "P2.3_FROZEN",
        "metric_kernel": "P2.2_FROZEN",
        "result_interpretation": "PIPELINE_SMOKE_ONLY",
    }:
        raise CalibrationContractError("P2.4 smoke contract changed")
    flags = tuple(payload.get("dataset_flags", ()))
    if flags != CALIBRATION_DATASET_FLAGS:
        raise CalibrationContractError("calibration dataset flags changed")
    supplied_digest = str(payload.get("artifact_digest", ""))
    expected_digest = config_digest(payload)
    if (
        supplied_digest != expected_digest
        or expected_digest != CALIBRATION_RUN_MANIFEST_DIGEST
    ):
        raise CalibrationContractError("calibration run manifest digest changed")
    return P24CalibrationManifest(
        payload=dict(payload),
        artifact_digest=expected_digest,
        scenario_ids=EXPECTED_SCENARIOS,
        smoke_scenario_ids=tuple(smoke["scenario_ids"]),
        smoke_dataset_issue_count=int(smoke["dataset_issue_count"]),
        smoke_outer_fold_count=int(smoke["outer_fold_count"]),
        absolute_bits_tolerance=float(calibration["absolute_bits_tolerance"]),
        relative_tolerance=float(calibration["relative_tolerance"]),
        maximum_iterations=int(calibration["maximum_iterations"]),
        parameter_width_tolerance=float(
            calibration["parameter_width_tolerance"]
        ),
        monotonicity_grid_points=int(calibration["monotonicity_grid_points"]),
        mc_standard_error_tolerance=float(
            mc["maximum_standard_error_bits_per_issue"]
        ),
        mc_agreement_standard_errors=int(mc["agreement_standard_errors"]),
        mc_sample_schedule=tuple(int(value) for value in mc["sample_schedule"]),
        root_seed_set_digest=root_seed_set_digest,
        dataset_flags=flags,
    )
