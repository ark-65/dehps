from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isclose
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.calibration.mechanisms import (
    GENERATOR_CONTRACTS,
    _distribution_for,
    _marginal_diagnostics,
    _parameter_upper_bound,
)


class MeasurementRepairError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class MarginalCalibration:
    mechanism: str
    parameter_value: float
    parameter_upper_bound: float
    joint_information_bits_per_issue: float
    marginal_information_bits_per_issue: float
    solver_iterations: int
    classification: str


def information_at_parameter(
    mechanism: str,
    parameter: float,
) -> tuple[float, float]:
    upper = _parameter_upper_bound(mechanism)
    if mechanism not in GENERATOR_CONTRACTS or not 0.0 < parameter <= upper:
        raise MeasurementRepairError(
            "measurement_repair_parameter_invalid",
            f"{mechanism} parameter is outside the exact legal bracket",
        )
    joint = _distribution_for(mechanism, parameter).joint_information_bits
    marginal = float(
        _marginal_diagnostics(
            mechanism,
            parameter,
            joint,
        )["composite_number_event_information_bits_per_issue"]
    )
    return joint, marginal


def calibrate_marginal_target(
    mechanism: str,
    target_bits: float,
    *,
    absolute_tolerance: float = 1e-12,
    relative_tolerance: float = 1e-10,
    maximum_iterations: int = 256,
) -> MarginalCalibration:
    if mechanism == "marginal_preserving_conditional_signal":
        raise MeasurementRepairError(
            "marginal_target_not_identifiable",
            "marginal-preserving mechanism has exactly zero marginal information",
        )
    if not 0.0 < target_bits:
        raise MeasurementRepairError(
            "measurement_repair_target_invalid",
            "marginal information target must be positive",
        )
    upper = _parameter_upper_bound(mechanism)
    upper_joint, upper_marginal = information_at_parameter(mechanism, upper)
    if target_bits > upper_marginal + absolute_tolerance:
        return MarginalCalibration(
            mechanism=mechanism,
            parameter_value=upper,
            parameter_upper_bound=upper,
            joint_information_bits_per_issue=upper_joint,
            marginal_information_bits_per_issue=upper_marginal,
            solver_iterations=0,
            classification="TARGET_NOT_REACHABLE_BY_FROZEN_GENERATOR",
        )

    lower = 0.0
    solved = upper
    joint = upper_joint
    marginal = upper_marginal
    for iteration in range(1, maximum_iterations + 1):
        solved = (lower + upper) / 2.0
        joint, marginal = information_at_parameter(mechanism, solved)
        absolute_error = abs(marginal - target_bits)
        relative_error = absolute_error / target_bits
        if (
            absolute_error <= absolute_tolerance
            and relative_error <= relative_tolerance
        ):
            return MarginalCalibration(
                mechanism=mechanism,
                parameter_value=solved,
                parameter_upper_bound=_parameter_upper_bound(mechanism),
                joint_information_bits_per_issue=joint,
                marginal_information_bits_per_issue=marginal,
                solver_iterations=iteration,
                classification="MARGINAL_TARGET_CALIBRATED",
            )
        if marginal < target_bits:
            lower = solved
        else:
            upper = solved
    raise MeasurementRepairError(
        "measurement_repair_solver_failed",
        f"{mechanism} did not reach {target_bits} bits within tolerance",
    )


def verify_frozen_scenario(
    scenario: Mapping[str, Any],
) -> MarginalCalibration:
    mechanism = str(scenario.get("mechanism") or "")
    role = str(scenario.get("role") or "")
    parameter = float(scenario.get("parameter_value") or 0.0)
    expected_joint = float(scenario.get("joint_information_bits_per_issue") or 0.0)
    expected_marginal = float(
        scenario.get("marginal_information_bits_per_issue") or 0.0
    )
    if role == "FORMAL_POWER_TARGET":
        calibrated = calibrate_marginal_target(
            mechanism,
            float(scenario["requested_marginal_bits_per_issue"]),
        )
    elif role in {
        "JOINT_ONLY_NEGATIVE_CONTROL",
        "MARGINAL_FEASIBILITY_SENTINEL",
    }:
        joint, marginal = information_at_parameter(mechanism, parameter)
        calibrated = MarginalCalibration(
            mechanism=mechanism,
            parameter_value=parameter,
            parameter_upper_bound=_parameter_upper_bound(mechanism),
            joint_information_bits_per_issue=joint,
            marginal_information_bits_per_issue=marginal,
            solver_iterations=0,
            classification=(
                "JOINT_ONLY_NOT_A_POWER_TARGET"
                if role == "JOINT_ONLY_NEGATIVE_CONTROL"
                else "TARGET_NOT_REACHABLE_BY_FROZEN_GENERATOR"
            ),
        )
    else:
        raise MeasurementRepairError(
            "measurement_repair_role_invalid",
            f"unsupported scenario role: {role}",
        )
    if (
        not isclose(
            calibrated.parameter_value,
            parameter,
            rel_tol=1e-10,
            abs_tol=1e-12,
        )
        or not isclose(
            calibrated.joint_information_bits_per_issue,
            expected_joint,
            rel_tol=1e-10,
            abs_tol=1e-12,
        )
        or not isclose(
            calibrated.marginal_information_bits_per_issue,
            expected_marginal,
            rel_tol=1e-10,
            abs_tol=1e-12,
        )
    ):
        raise MeasurementRepairError(
            "measurement_repair_scenario_mismatch",
            f"frozen exact truth changed for {scenario.get('scenario_id')}",
        )
    return calibrated


def build_marginal_truth_artifact(
    scenario: Mapping[str, Any],
    *,
    repair_manifest_digest: str,
) -> dict[str, Any]:
    calibrated = verify_frozen_scenario(scenario)
    role = str(scenario["role"])
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-repaired-marginal-truth.v1",
        "artifact_type": "repaired_marginal_truth",
        "artifact_digest": "",
        "scenario_id": scenario["scenario_id"],
        "mechanism": calibrated.mechanism,
        "role": role,
        "truth_estimand": "sum_number_event_mutual_information_with_prior_state",
        "metric_estimand": "sum_number_event_log_loss_gain_bits_per_issue",
        "requested_marginal_bits_per_issue": scenario.get(
            "requested_marginal_bits_per_issue"
        ),
        "marginal_information_bits_per_issue": (
            calibrated.marginal_information_bits_per_issue
        ),
        "joint_information_bits_per_issue": (
            calibrated.joint_information_bits_per_issue
        ),
        "parameter_name": GENERATOR_CONTRACTS[calibrated.mechanism]["parameter_name"],
        "parameter_value": calibrated.parameter_value,
        "parameter_upper_bound": calibrated.parameter_upper_bound,
        "solver_iterations": calibrated.solver_iterations,
        "classification": calibrated.classification,
        "eligible_for_formal_power": role == "FORMAL_POWER_TARGET",
        "eligible_for_measurement_gate": role == "FORMAL_POWER_TARGET",
        "eligible_for_evidence": False,
        "measurement_repair_manifest_digest": repair_manifest_digest,
        "production_action": "none",
        "parent_digests": [repair_manifest_digest],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4-p2.repaired-marginal-truth.v1",
    )
    return payload
