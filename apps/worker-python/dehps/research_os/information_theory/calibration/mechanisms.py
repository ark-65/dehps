from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from math import comb, fsum, log2, sqrt
from typing import Any, Callable, Mapping

import numpy as np

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.seed_domains import (
    derive_m4_p2_seed,
)
from dehps.research_os.information_theory.synthetic.contracts import (
    SyntheticIssue,
)

from .contracts import (
    CALIBRATION_DATASET_FLAGS,
    DECISION_POLICY_DIGEST,
    PREREGISTRATION_DIGEST,
    SYNTHETIC_MANIFEST_DIGEST,
    TRUTH_SCHEMA_VERSION,
    P24CalibrationManifest,
)


LEGAL_NUMBER_COUNT = 33
DRAW_SIZE = 6
LEGAL_COMBINATION_COUNT = comb(LEGAL_NUMBER_COUNT, DRAW_SIZE)
NUMBER_MARGINAL = Fraction(DRAW_SIZE, LEGAL_NUMBER_COUNT)
PAIR_GROUP = ((1, 2), (3, 4))
IS4_WEIGHTS = (
    Fraction(219, 221),
    Fraction(-1, 1),
    Fraction(1, 1),
    Fraction(-1, 1),
    Fraction(1, 1),
    Fraction(-219, 221),
    Fraction(1, 1),
)
INFORMATION_DEFINITION = (
    "I(S_t;Y_{t+1})=sum_s P(s) sum_y P(y|s) "
    "log2(P(y|s)/P(y)) over exact legal C(33,6)"
)

GENERATOR_CONTRACTS: dict[str, dict[str, Any]] = {
    "single_number_conditional_shift": {
        "mechanism_id": "IS1_SINGLE_NUMBER_CONDITIONAL_SHIFT",
        "state_definition": (
            "balanced binary state fixed before target issue; "
            "available_through_issue=t,target_issue=t+1"
        ),
        "affected_numbers": [1],
        "parameter_name": "delta",
        "normalization": "exact contains/excludes legal stratum counts",
    },
    "local_temporal_state": {
        "mechanism_id": "IS2_LOCAL_TEMPORAL_STATE",
        "state_definition": (
            "lexicographic half of Y_t; "
            "available_through_issue=t,target_issue=t+1"
        ),
        "affected_numbers": [],
        "parameter_name": "delta",
        "normalization": "two equal 553784-combination legal strata",
    },
    "pair_conditional_signal": {
        "mechanism_id": "IS3_PAIR_CONDITIONAL",
        "state_definition": (
            "balanced binary state fixed before target issue; "
            "available_through_issue=t,target_issue=t+1"
        ),
        "affected_pairs": [list(pair) for pair in PAIR_GROUP],
        "parameter_name": "delta",
        "normalization": "exact pair-event/non-event legal stratum counts",
    },
    "marginal_preserving_conditional_signal": {
        "mechanism_id": "IS4_MARGINAL_PRESERVING_CONDITIONAL",
        "state_definition": (
            "balanced binary state fixed before target issue; "
            "available_through_issue=t,target_issue=t+1"
        ),
        "group_A": list(range(1, 17)),
        "parameter_name": "lambda",
        "normalization": "exact hypergeometric orthogonality",
        "orthogonal_weights": [
            {"numerator": value.numerator, "denominator": value.denominator}
            for value in IS4_WEIGHTS
        ],
    },
}


class CalibrationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class ExactDistribution:
    labels: tuple[str, ...]
    marginal: tuple[float, ...]
    conditional: tuple[tuple[float, ...], tuple[float, ...]]

    def __post_init__(self) -> None:
        if (
            len(self.labels) != len(self.marginal)
            or any(len(row) != len(self.marginal) for row in self.conditional)
        ):
            raise CalibrationError(
                "REPAIR_INJECTED_SIGNAL_GENERATOR",
                "distribution support dimensions differ",
            )
        for row in (*self.conditional, self.marginal):
            if any(value <= 0 or value >= 1 for value in row):
                raise CalibrationError(
                    "REPAIR_INJECTED_SIGNAL_GENERATOR",
                    "formal calibrated probabilities must be strictly positive",
                )
            if abs(fsum(row) - 1.0) > 1e-12:
                raise CalibrationError(
                    "REPAIR_INJECTED_SIGNAL_GENERATOR",
                    "conditional probabilities do not normalize",
                )
        for index, marginal in enumerate(self.marginal):
            if abs(
                marginal
                - 0.5
                * (self.conditional[0][index] + self.conditional[1][index])
            ) > 1e-12:
                raise CalibrationError(
                    "REPAIR_INJECTED_SIGNAL_GENERATOR",
                    "balanced conditional mixture differs from marginal",
                )

    @property
    def joint_information_bits(self) -> float:
        terms = []
        for row in self.conditional:
            for conditional, marginal in zip(row, self.marginal, strict=True):
                terms.append(0.5 * conditional * log2(conditional / marginal))
        return fsum(terms)

    @property
    def conditional_kl_bits(self) -> tuple[float, float]:
        return tuple(
            fsum(
                conditional * log2(conditional / marginal)
                for conditional, marginal in zip(
                    row, self.marginal, strict=True
                )
            )
            for row in self.conditional
        )  # type: ignore[return-value]


@dataclass(frozen=True)
class CalibratedScenario:
    scenario_id: str
    mechanism: str
    requested_bits: float
    parameter_name: str
    parameter_value: float
    bracket: tuple[float, float]
    solver_iterations: int
    calibrated_bits: float
    absolute_error: float
    relative_error: float
    monotonicity_status: str
    distribution: ExactDistribution
    marginal_diagnostics: Mapping[str, Any]
    mc_audit: Mapping[str, Any]
    generator_digest: str

    def truth_artifact(
        self,
        *,
        manifest: P24CalibrationManifest,
        git_commit: str,
    ) -> dict[str, Any]:
        conditional_payload = {
            "support": list(self.distribution.labels),
            "state_probability": [0.5, 0.5],
            "conditional_probability": [
                list(row) for row in self.distribution.conditional
            ],
            "parameter_name": self.parameter_name,
            "parameter_value": self.parameter_value,
        }
        unconditional_payload = {
            "legal_sample_space": "uniform_C(33,6)",
            "legal_combination_count": LEGAL_COMBINATION_COUNT,
            "support_marginal_probability": list(
                self.distribution.marginal
            ),
            "number_marginal": {
                "numerator": NUMBER_MARGINAL.numerator,
                "denominator": NUMBER_MARGINAL.denominator,
            },
        }
        contract = GENERATOR_CONTRACTS[self.mechanism]
        pair_information = (
            self.calibrated_bits
            if self.mechanism == "pair_conditional_signal"
            else None
        )
        payload: dict[str, Any] = {
            "schema_version": TRUTH_SCHEMA_VERSION,
            "artifact_type": "injected_signal_truth",
            "artifact_digest": "",
            "scenario_id": self.scenario_id,
            "mechanism": self.mechanism,
            "requested_bits_per_issue": self.requested_bits,
            "calibrated_bits_per_issue": self.calibrated_bits,
            "joint_draw_information_bits_per_issue": self.calibrated_bits,
            "composite_number_event_information_bits_per_issue": (
                self.marginal_diagnostics[
                    "composite_number_event_information_bits_per_issue"
                ]
            ),
            "pair_information_bits_per_issue": pair_information,
            "information_definition": INFORMATION_DEFINITION,
            "requested_strength_binding": (
                "joint_draw_information_bits_per_issue"
            ),
            "parameter_name": self.parameter_name,
            "parameter_value": self.parameter_value,
            "state_definition": contract["state_definition"],
            "conditional_distribution_digest": canonical_digest(
                conditional_payload,
                domain="dehps.m4-p2.calibration.conditional-distribution.v1",
            ),
            "unconditional_distribution_digest": canonical_digest(
                unconditional_payload,
                domain="dehps.m4-p2.calibration.unconditional-distribution.v1",
            ),
            "conditional_distribution": conditional_payload,
            "unconditional_distribution": unconditional_payload,
            "target_numbers_or_pairs": {
                "numbers": contract.get("affected_numbers", []),
                "pairs": contract.get("affected_pairs", []),
                "group_A": contract.get("group_A", []),
            },
            "marginal_diagnostics": dict(self.marginal_diagnostics),
            "conditional_kl_bits_per_issue": list(
                self.distribution.conditional_kl_bits
            ),
            "unconditional_kl_bits_per_issue": 0.0,
            "expected_selected_count": 6.0,
            "calibration_method": (
                "exact_analytic_or_deterministic_legal_space_sum"
            ),
            "calibration_tolerance": {
                "absolute_bits_tolerance": (
                    manifest.absolute_bits_tolerance
                ),
                "relative_tolerance": manifest.relative_tolerance,
            },
            "calibration_result": {
                "search_lower_bound": self.bracket[0],
                "search_upper_bound": self.bracket[1],
                "solved_parameter": self.parameter_value,
                "iteration_count": self.solver_iterations,
                "requested_bits": self.requested_bits,
                "calibrated_bits": self.calibrated_bits,
                "absolute_error": self.absolute_error,
                "relative_error": self.relative_error,
                "monotonicity_status": self.monotonicity_status,
                "solver_status": "CONVERGED",
            },
            "monte_carlo_truth_audit": dict(self.mc_audit),
            "calibration_seed_policy": {
                "seed_domain": "M4_P2_CALIBRATION",
                "seed_identity": self.mc_audit["seed_identity"],
                "selection_policy": "no_best_seed",
                "wall_clock_seed": "forbidden",
                "evaluation_seed_reuse": "forbidden",
            },
            "dataset_flags": list(CALIBRATION_DATASET_FLAGS),
            "generator_digest": self.generator_digest,
            "calibration_run_manifest_digest": manifest.artifact_digest,
            "preregistration_digest": PREREGISTRATION_DIGEST,
            "decision_policy_digest": DECISION_POLICY_DIGEST,
            "synthetic_manifest_digest": SYNTHETIC_MANIFEST_DIGEST,
            "git_commit": git_commit,
            "working_tree_clean": True,
            "eligible_for_p2_5_input": True,
            "eligible_for_power_evidence": False,
            "eligible_for_p2_gate_evidence": False,
            "parent_digests": [
                PREREGISTRATION_DIGEST,
                DECISION_POLICY_DIGEST,
                SYNTHETIC_MANIFEST_DIGEST,
                manifest.artifact_digest,
                self.generator_digest,
            ],
        }
        identity = dict(payload)
        identity.pop("artifact_digest")
        payload["artifact_digest"] = canonical_digest(
            identity, domain="dehps.m4-p2.injected-signal-truth.v1"
        )
        return payload


def _binary_information(
    probability: float,
    delta: float,
) -> ExactDistribution:
    low = probability - delta
    high = probability + delta
    return ExactDistribution(
        labels=("event_false", "event_true"),
        marginal=(1.0 - probability, probability),
        conditional=((1.0 - low, low), (1.0 - high, high)),
    )


def _distribution_for(
    mechanism: str,
    parameter: float,
) -> ExactDistribution:
    if mechanism == "single_number_conditional_shift":
        return _binary_information(float(NUMBER_MARGINAL), parameter)
    if mechanism == "local_temporal_state":
        return ExactDistribution(
            labels=("lower_lexicographic_half", "upper_lexicographic_half"),
            marginal=(0.5, 0.5),
            conditional=(
                (0.5 + parameter, 0.5 - parameter),
                (0.5 - parameter, 0.5 + parameter),
            ),
        )
    if mechanism == "pair_conditional_signal":
        return _binary_information(float(_pair_event_probability()), parameter)
    if mechanism == "marginal_preserving_conditional_signal":
        marginal = tuple(float(value) for value in _is4_k_probabilities())
        conditional = tuple(
            tuple(
                probability * (1.0 + sign * parameter * float(weight))
                for probability, weight in zip(
                    marginal, IS4_WEIGHTS, strict=True
                )
            )
            for sign in (-1.0, 1.0)
        )
        return ExactDistribution(
            labels=tuple(f"K={value}" for value in range(7)),
            marginal=marginal,
            conditional=conditional,  # type: ignore[arg-type]
        )
    raise CalibrationError(
        "REPAIR_PREREGISTRATION_CONTRACT",
        f"unknown injected mechanism: {mechanism}",
    )


def _parameter_upper_bound(mechanism: str) -> float:
    strict = 1.0 - 1e-12
    if mechanism == "single_number_conditional_shift":
        return float(NUMBER_MARGINAL) * strict
    if mechanism == "local_temporal_state":
        return 0.5 * strict
    if mechanism == "pair_conditional_signal":
        return float(_pair_event_probability()) * strict
    if mechanism == "marginal_preserving_conditional_signal":
        return strict
    raise CalibrationError(
        "REPAIR_PREREGISTRATION_CONTRACT", "mechanism has no parameter bracket"
    )


def _scenario_contract(scenario_id: str) -> tuple[str, float]:
    strengths = {
        "WEAK": 0.001,
        "MEDIUM_PRACTICAL": 0.01,
        "STRONG": 0.05,
    }
    mechanisms = {
        "SINGLE_NUMBER": "single_number_conditional_shift",
        "LOCAL_TEMPORAL": "local_temporal_state",
        "PAIR": "pair_conditional_signal",
        "MARGINAL_PRESERVING": (
            "marginal_preserving_conditional_signal"
        ),
    }
    for strength, bits in strengths.items():
        prefix = f"{strength}_"
        if not scenario_id.startswith(prefix):
            continue
        suffix = scenario_id[len(prefix):]
        if suffix in mechanisms:
            return mechanisms[suffix], bits
    raise CalibrationError(
        "REPAIR_PREREGISTRATION_CONTRACT",
        f"scenario is not frozen: {scenario_id}",
    )


def _signal_strength(scenario_id: str) -> str:
    for value in ("MEDIUM_PRACTICAL", "WEAK", "STRONG"):
        if scenario_id.startswith(f"{value}_"):
            return value
    raise CalibrationError(
        "REPAIR_PREREGISTRATION_CONTRACT",
        f"scenario strength is not frozen: {scenario_id}",
    )


def _solve_parameter(
    *,
    mechanism: str,
    requested_bits: float,
    manifest: P24CalibrationManifest,
) -> tuple[float, int, float, float, float, str, ExactDistribution]:
    lower = 0.0
    upper = _parameter_upper_bound(mechanism)

    def objective(parameter: float) -> float:
        return _distribution_for(mechanism, parameter).joint_information_bits

    grid = [
        lower + (upper - lower) * index / (
            manifest.monotonicity_grid_points - 1
        )
        for index in range(manifest.monotonicity_grid_points)
    ]
    values = [objective(value) for value in grid]
    monotone = all(
        right >= left - 1e-15
        for left, right in zip(values, values[1:])
    )
    strict = any(
        right > left + 1e-15
        for left, right in zip(values, values[1:])
    )
    if not monotone or not strict:
        raise CalibrationError(
            "REPAIR_INJECTED_SIGNAL_CALIBRATION",
            f"information is not monotone for {mechanism}",
        )
    if not (values[0] <= requested_bits <= values[-1]):
        raise CalibrationError(
            "REPAIR_INJECTED_SIGNAL_CALIBRATION",
            f"requested bits are not bracketed for {mechanism}",
        )
    solved = lower
    calibrated = values[0]
    iterations = 0
    for iterations in range(1, manifest.maximum_iterations + 1):
        solved = (lower + upper) / 2.0
        calibrated = objective(solved)
        absolute = abs(calibrated - requested_bits)
        relative = absolute / requested_bits
        if (
            absolute <= manifest.absolute_bits_tolerance
            and relative <= manifest.relative_tolerance
        ):
            break
        if calibrated < requested_bits:
            lower = solved
        else:
            upper = solved
        if upper - lower <= manifest.parameter_width_tolerance:
            break
    absolute = abs(calibrated - requested_bits)
    relative = absolute / requested_bits
    if (
        absolute > manifest.absolute_bits_tolerance
        or relative > manifest.relative_tolerance
    ):
        raise CalibrationError(
            "REPAIR_INJECTED_SIGNAL_CALIBRATION",
            f"solver tolerance exceeded for {mechanism}",
        )
    return (
        solved,
        iterations,
        calibrated,
        absolute,
        relative,
        "MONOTONE_BRACKETED",
        _distribution_for(mechanism, solved),
    )


def _bernoulli_information(
    state_probabilities: tuple[float, float],
) -> float:
    marginal = 0.5 * fsum(state_probabilities)
    if marginal <= 0 or marginal >= 1:
        return 0.0
    terms: list[float] = []
    for probability in state_probabilities:
        terms.extend(
            (
                0.5 * probability * log2(probability / marginal),
                0.5
                * (1.0 - probability)
                * log2((1.0 - probability) / (1.0 - marginal)),
            )
        )
    return fsum(terms)


@lru_cache(maxsize=1)
def _legal_space_diagnostics() -> dict[str, Any]:
    half = LEGAL_COMBINATION_COUNT // 2
    total_number_count = comb(32, 5)
    lower_counts = [0] * 33
    pair_event_count = 0
    pair_event_number_counts = [0] * 33
    for index, draw in enumerate(combinations(range(1, 34), 6)):
        if index < half:
            for number in draw:
                lower_counts[number - 1] += 1
        pair_event = any(
            left in draw and right in draw for left, right in PAIR_GROUP
        )
        if pair_event:
            pair_event_count += 1
            for number in draw:
                pair_event_number_counts[number - 1] += 1
    expected_pair_event_count = (
        2 * comb(31, 4) - comb(29, 2)
    )
    if pair_event_count != expected_pair_event_count:
        raise CalibrationError(
            "REPAIR_INJECTED_SIGNAL_GENERATOR",
            "pair-event enumeration disagrees with exact inclusion-exclusion",
        )
    return {
        "half": half,
        "total_number_count": total_number_count,
        "lower_counts": tuple(lower_counts),
        "upper_counts": tuple(
            total_number_count - value for value in lower_counts
        ),
        "pair_event_count": pair_event_count,
        "pair_non_event_count": LEGAL_COMBINATION_COUNT - pair_event_count,
        "pair_event_number_counts": tuple(pair_event_number_counts),
        "pair_non_event_number_counts": tuple(
            total_number_count - value
            for value in pair_event_number_counts
        ),
    }


@lru_cache(maxsize=1)
def _pair_event_probability() -> Fraction:
    return Fraction(
        2 * comb(31, 4) - comb(29, 2),
        LEGAL_COMBINATION_COUNT,
    )


@lru_cache(maxsize=1)
def _is4_k_probabilities() -> tuple[Fraction, ...]:
    probabilities = tuple(
        Fraction(comb(16, k) * comb(17, 6 - k), LEGAL_COMBINATION_COUNT)
        for k in range(7)
    )
    if sum(probabilities) != 1:
        raise CalibrationError(
            "REPAIR_INJECTED_SIGNAL_GENERATOR",
            "IS4 hypergeometric probabilities do not normalize",
        )
    if sum(
        probability * weight
        for probability, weight in zip(
            probabilities, IS4_WEIGHTS, strict=True
        )
    ) != 0:
        raise CalibrationError(
            "REPAIR_INJECTED_SIGNAL_GENERATOR",
            "IS4 weights do not preserve total probability",
        )
    if sum(
        probability * k * weight
        for k, (probability, weight) in enumerate(
            zip(probabilities, IS4_WEIGHTS, strict=True)
        )
    ) != 0:
        raise CalibrationError(
            "REPAIR_INJECTED_SIGNAL_GENERATOR",
            "IS4 weights do not preserve number marginals",
        )
    return probabilities


def _marginal_diagnostics(
    mechanism: str,
    parameter: float,
    calibrated_bits: float,
) -> dict[str, Any]:
    baseline = float(NUMBER_MARGINAL)
    state_probabilities: list[tuple[float, float]]
    if mechanism == "single_number_conditional_shift":
        target = (baseline - parameter, baseline + parameter)
        non_target = tuple(
            (6.0 - probability) / 32.0 for probability in target
        )
        state_probabilities = [target] + [non_target] * 32
    elif mechanism == "local_temporal_state":
        diagnostics = _legal_space_diagnostics()
        half = int(diagnostics["half"])
        lower = [
            value / half for value in diagnostics["lower_counts"]
        ]
        upper = [
            value / half for value in diagnostics["upper_counts"]
        ]
        state_probabilities = [
            (
                (0.5 + parameter) * lower[index]
                + (0.5 - parameter) * upper[index],
                (0.5 - parameter) * lower[index]
                + (0.5 + parameter) * upper[index],
            )
            for index in range(33)
        ]
    elif mechanism == "pair_conditional_signal":
        diagnostics = _legal_space_diagnostics()
        event_count = int(diagnostics["pair_event_count"])
        non_event_count = int(diagnostics["pair_non_event_count"])
        event_probability = float(_pair_event_probability())
        event_number = [
            value / event_count
            for value in diagnostics["pair_event_number_counts"]
        ]
        non_event_number = [
            value / non_event_count
            for value in diagnostics["pair_non_event_number_counts"]
        ]
        low = event_probability - parameter
        high = event_probability + parameter
        state_probabilities = [
            (
                low * event_number[index]
                + (1.0 - low) * non_event_number[index],
                high * event_number[index]
                + (1.0 - high) * non_event_number[index],
            )
            for index in range(33)
        ]
    elif mechanism == "marginal_preserving_conditional_signal":
        state_probabilities = [(baseline, baseline)] * 33
    else:
        raise CalibrationError(
            "REPAIR_PREREGISTRATION_CONTRACT",
            "unknown mechanism for marginal diagnostics",
        )
    single_information = [
        _bernoulli_information(probabilities)
        for probabilities in state_probabilities
    ]
    probability_shifts = [
        max(abs(value - baseline) for value in probabilities)
        for probabilities in state_probabilities
    ]
    composite = fsum(single_information)
    maximum_information = max(single_information)
    maximum_shift = max(probability_shifts)
    result: dict[str, Any] = {
        "unconditional_number_marginal": baseline,
        "max_absolute_unconditional_marginal_deviation": 0.0,
        "mean_absolute_unconditional_marginal_deviation": 0.0,
        "max_absolute_conditional_marginal_deviation": maximum_shift,
        "mean_absolute_conditional_marginal_deviation": (
            fsum(probability_shifts) / 33
        ),
        "maximum_single_number_information_bits": maximum_information,
        "mean_single_number_information_bits": (
            fsum(single_information) / 33
        ),
        "composite_number_event_information_bits_per_issue": composite,
        "expected_selected_count_by_state": [
            fsum(values[index] for values in state_probabilities)
            for index in (0, 1)
        ],
        "expected_selected_count_unconditional": 6.0,
    }
    if mechanism == "single_number_conditional_shift":
        result["target_number"] = 1
        result["target_number_probability_by_state"] = list(
            state_probabilities[0]
        )
        result["non_target_number_probability_by_state"] = list(
            state_probabilities[1]
        )
    if mechanism == "pair_conditional_signal":
        ratio = maximum_information / calibrated_bits
        pair_dominant = ratio <= 0.1 and maximum_shift <= 0.01
        result.update(
            {
                "requested_pair_information_bits_per_issue": calibrated_bits,
                "calibrated_pair_information_bits_per_issue": calibrated_bits,
                "joint_draw_information_bits_per_issue": calibrated_bits,
                "maximum_single_number_marginal_leakage_bits": (
                    maximum_information
                ),
                "mean_single_number_marginal_leakage_bits": (
                    fsum(single_information) / 33
                ),
                "maximum_single_number_probability_shift": maximum_shift,
                "maximum_single_number_information_fraction_of_pair_information": ratio,
                "classification": (
                    "PAIR_DOMINANT"
                    if pair_dominant
                    else "PAIR_CONDITIONAL_WITH_MARGINAL_LEAKAGE"
                ),
                "pair_dominance_tolerance_passed": pair_dominant,
            }
        )
    if mechanism == "marginal_preserving_conditional_signal":
        result.update(
            {
                "max_absolute_unconditional_marginal_deviation": 0.0,
                "mean_absolute_unconditional_marginal_deviation": 0.0,
                "max_absolute_conditional_marginal_deviation": 0.0,
                "mean_absolute_conditional_marginal_deviation": 0.0,
                "marginal_preservation_tolerance_passed": True,
            }
        )
    return result


def _mc_audit(
    *,
    scenario_id: str,
    distribution: ExactDistribution,
    exact_bits: float,
    manifest: P24CalibrationManifest,
    parent_run_digest: str,
) -> dict[str, Any]:
    derived = derive_m4_p2_seed(
        root_seed_set_digest=manifest.root_seed_set_digest,
        seed_domain="M4_P2_CALIBRATION",
        scenario_id=scenario_id,
        method_id="independent_truth_audit",
        replicate_index=0,
        parent_run_digest=parent_run_digest,
    )
    generator = np.random.default_rng(int(derived["seed"]))
    probabilities: list[float] = []
    information_density: list[float] = []
    for row in distribution.conditional:
        for conditional, marginal in zip(
            row, distribution.marginal, strict=True
        ):
            probabilities.append(0.5 * conditional)
            information_density.append(log2(conditional / marginal))
    probability_array = np.asarray(probabilities, dtype=np.float64)
    probability_array /= probability_array.sum()
    density_array = np.asarray(information_density, dtype=np.float64)
    total_count = 0
    total_sum = 0.0
    total_sum_squares = 0.0
    passed = False
    mc_mean = 0.0
    standard_error = float("inf")
    absolute_error = float("inf")
    for target_count in manifest.mc_sample_schedule:
        additional = target_count - total_count
        counts = generator.multinomial(additional, probability_array)
        total_count = target_count
        total_sum += float(np.dot(counts, density_array))
        total_sum_squares += float(
            np.dot(counts, density_array * density_array)
        )
        mc_mean = total_sum / total_count
        variance_numerator = max(
            0.0,
            total_sum_squares - total_sum * total_sum / total_count,
        )
        sample_variance = variance_numerator / (total_count - 1)
        standard_error = sqrt(sample_variance / total_count)
        absolute_error = abs(mc_mean - exact_bits)
        agreement_limit = (
            manifest.mc_agreement_standard_errors * standard_error
            + manifest.absolute_bits_tolerance
        )
        passed = (
            standard_error <= manifest.mc_standard_error_tolerance
            and absolute_error <= agreement_limit
        )
        if passed:
            break
    if not passed:
        raise CalibrationError(
            "REPAIR_INJECTED_SIGNAL_CALIBRATION",
            f"independent MC truth audit failed for {scenario_id}",
        )
    return {
        "role": "independent_non_calibrating_confirmation",
        "sample_count": total_count,
        "mc_mean_bits_per_issue": mc_mean,
        "exact_truth_bits_per_issue": exact_bits,
        "absolute_error_bits_per_issue": absolute_error,
        "standard_error_bits_per_issue": standard_error,
        "maximum_standard_error_bits_per_issue": (
            manifest.mc_standard_error_tolerance
        ),
        "agreement_standard_errors": (
            manifest.mc_agreement_standard_errors
        ),
        "agreement_limit_bits_per_issue": (
            manifest.mc_agreement_standard_errors * standard_error
            + manifest.absolute_bits_tolerance
        ),
        "status": "PASS",
        "may_change_solved_parameter": False,
        "seed_identity": derived["identity"],
        "seed_digest": derived["seed_digest"],
    }


def calibrate_scenario(
    scenario_id: str,
    *,
    manifest: P24CalibrationManifest,
    parent_run_digest: str,
) -> CalibratedScenario:
    if scenario_id not in manifest.scenario_ids:
        raise CalibrationError(
            "REPAIR_PREREGISTRATION_CONTRACT",
            f"scenario is not present in frozen manifest: {scenario_id}",
        )
    mechanism, requested_bits = _scenario_contract(scenario_id)
    (
        parameter,
        iterations,
        calibrated,
        absolute,
        relative,
        monotonicity,
        distribution,
    ) = _solve_parameter(
        mechanism=mechanism,
        requested_bits=requested_bits,
        manifest=manifest,
    )
    generator_digest = canonical_digest(
        GENERATOR_CONTRACTS[mechanism],
        domain=f"dehps.m4-p2.injected-generator.{mechanism}.v1",
    )
    marginal_diagnostics = _marginal_diagnostics(
        mechanism, parameter, calibrated
    )
    mc_audit = _mc_audit(
        scenario_id=scenario_id,
        distribution=distribution,
        exact_bits=calibrated,
        manifest=manifest,
        parent_run_digest=parent_run_digest,
    )
    return CalibratedScenario(
        scenario_id=scenario_id,
        mechanism=mechanism,
        requested_bits=requested_bits,
        parameter_name=str(
            GENERATOR_CONTRACTS[mechanism]["parameter_name"]
        ),
        parameter_value=parameter,
        bracket=(0.0, _parameter_upper_bound(mechanism)),
        solver_iterations=iterations,
        calibrated_bits=calibrated,
        absolute_error=absolute,
        relative_error=relative,
        monotonicity_status=monotonicity,
        distribution=distribution,
        marginal_diagnostics=marginal_diagnostics,
        mc_audit=mc_audit,
        generator_digest=generator_digest,
    )


def _unrank_lexicographic_combination(rank: int) -> tuple[int, ...]:
    if rank < 0 or rank >= LEGAL_COMBINATION_COUNT:
        raise ValueError("combination rank is outside C(33,6)")
    result: list[int] = []
    remaining_rank = rank
    next_value = 1
    for remaining_slots in range(DRAW_SIZE, 0, -1):
        for value in range(
            next_value,
            LEGAL_NUMBER_COUNT - remaining_slots + 2,
        ):
            suffix_count = comb(
                LEGAL_NUMBER_COUNT - value,
                remaining_slots - 1,
            )
            if remaining_rank < suffix_count:
                result.append(value)
                next_value = value + 1
                break
            remaining_rank -= suffix_count
    if len(result) != DRAW_SIZE:
        raise CalibrationError(
            "REPAIR_INJECTED_SIGNAL_GENERATOR",
            "lexicographic unranking failed",
        )
    return tuple(result)


def _sample_is1(
    generator: np.random.Generator,
    *,
    event_probability: float,
) -> tuple[int, ...]:
    contains_target = bool(generator.random() < event_probability)
    pool = np.arange(2, 34, dtype=np.int64)
    if contains_target:
        values = [1, *generator.choice(pool, 5, replace=False).tolist()]
    else:
        values = generator.choice(pool, 6, replace=False).tolist()
    return tuple(sorted(int(value) for value in values))


def _sample_is2(
    generator: np.random.Generator,
    *,
    previous_half: int,
    match_probability: float,
) -> tuple[tuple[int, ...], int]:
    matches = bool(generator.random() < match_probability)
    half = previous_half if matches else 1 - previous_half
    half_size = LEGAL_COMBINATION_COUNT // 2
    rank = int(generator.integers(0, half_size)) + half * half_size
    return _unrank_lexicographic_combination(rank), half


def _pair_event(numbers: tuple[int, ...]) -> bool:
    selected = set(numbers)
    return any(
        left in selected and right in selected for left, right in PAIR_GROUP
    )


def _sample_is3(
    generator: np.random.Generator,
    *,
    event_probability: float,
) -> tuple[int, ...]:
    desired = bool(generator.random() < event_probability)
    legal = np.arange(1, 34, dtype=np.int64)
    for _ in range(10000):
        numbers = tuple(
            sorted(
                int(value)
                for value in generator.choice(legal, 6, replace=False)
            )
        )
        if _pair_event(numbers) is desired:
            return numbers
    raise CalibrationError(
        "REPAIR_INJECTED_SIGNAL_GENERATOR",
        "pair-event rejection sampler exceeded fixed attempt bound",
    )


def _sample_is4(
    generator: np.random.Generator,
    *,
    state: int,
    parameter: float,
) -> tuple[int, ...]:
    sign = -1.0 if state == 0 else 1.0
    k_probabilities = np.asarray(
        [
            float(probability)
            * (1.0 + sign * parameter * float(weight))
            for probability, weight in zip(
                _is4_k_probabilities(), IS4_WEIGHTS, strict=True
            )
        ],
        dtype=np.float64,
    )
    k_probabilities /= k_probabilities.sum()
    k = int(generator.choice(np.arange(7), p=k_probabilities))
    group_a = generator.choice(
        np.arange(1, 17, dtype=np.int64), k, replace=False
    )
    group_b = generator.choice(
        np.arange(17, 34, dtype=np.int64), 6 - k, replace=False
    )
    return tuple(
        sorted(int(value) for value in np.concatenate((group_a, group_b)))
    )


def generate_calibration_dataset(
    calibrated: CalibratedScenario,
    *,
    truth_artifact: Mapping[str, Any],
    manifest: P24CalibrationManifest,
    issue_count: int,
    parent_run_digest: str,
) -> dict[str, Any]:
    if issue_count < 1:
        raise ValueError("calibration dataset issue count must be positive")
    derived = derive_m4_p2_seed(
        root_seed_set_digest=manifest.root_seed_set_digest,
        seed_domain="M4_P2_CALIBRATION",
        scenario_id=calibrated.scenario_id,
        method_id="calibration_smoke_dataset",
        replicate_index=0,
        parent_run_digest=parent_run_digest,
    )
    generator = np.random.default_rng(int(derived["seed"]))
    issues: list[SyntheticIssue] = []
    initial_state = int(derived["seed"]) % 2
    previous_half = initial_state
    for issue_index in range(1, issue_count + 1):
        state = (initial_state + issue_index - 1) % 2
        if calibrated.mechanism == "single_number_conditional_shift":
            target_probability = float(NUMBER_MARGINAL) + (
                -calibrated.parameter_value
                if state == 0
                else calibrated.parameter_value
            )
            numbers = _sample_is1(
                generator, event_probability=target_probability
            )
        elif calibrated.mechanism == "local_temporal_state":
            numbers, previous_half = _sample_is2(
                generator,
                previous_half=previous_half,
                match_probability=0.5 + calibrated.parameter_value,
            )
        elif calibrated.mechanism == "pair_conditional_signal":
            pair_probability = float(_pair_event_probability()) + (
                -calibrated.parameter_value
                if state == 0
                else calibrated.parameter_value
            )
            numbers = _sample_is3(
                generator, event_probability=pair_probability
            )
        elif (
            calibrated.mechanism
            == "marginal_preserving_conditional_signal"
        ):
            numbers = _sample_is4(
                generator,
                state=state,
                parameter=calibrated.parameter_value,
            )
        else:
            raise CalibrationError(
                "REPAIR_INJECTED_SIGNAL_GENERATOR",
                "unknown generator mechanism",
            )
        target = tuple(
            1 if number in numbers else 0 for number in range(1, 34)
        )
        issues.append(
            SyntheticIssue(
                issue_index=issue_index,
                red_mask=sum(1 << (number - 1) for number in numbers),
                sorted_red_numbers=numbers,
                target_vector=target,
            )
        )
    issue_payloads = [issue.to_dict() for issue in issues]
    seed_policy = {
        **derived["identity"],
        "seed_digest": derived["seed_digest"],
        "selection_policy": "no_best_seed",
        "wall_clock_seed": "forbidden",
        "dataset_role": "calibration_smoke_only",
    }
    seed_policy_digest = canonical_digest(
        seed_policy, domain="dehps.m4.synthetic.seed-policy.v1"
    )
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-information-theory-synthetic-dataset.v1",
        "artifact_type": "synthetic_dataset",
        "data_source": "synthetic_only",
        "real_dataset_reference": None,
        "dataset_role": "calibration_smoke_only",
        "dataset_flags": list(CALIBRATION_DATASET_FLAGS),
        "scenario": {
            "schema_version": (
                "dehps-m4-information-theory-synthetic-scenario.v1"
            ),
            "scenario_id": calibrated.scenario_id,
            "mechanism": calibrated.mechanism,
            "signal_strength": _signal_strength(calibrated.scenario_id),
            "target_bits_per_issue": calibrated.requested_bits,
            "implemented": True,
            "data_source": "synthetic_only",
        },
        "scale": {
            "scale_id": "P2_4_CALIBRATION_SMOKE",
            "sequence_length": issue_count,
            "minimum_training_length": 900,
            "outer_evaluation_length": issue_count - 900,
            "derivation": "frozen_P2.4_smoke_900_plus_2",
        },
        "truth": {
            "truth_artifact_digest": truth_artifact["artifact_digest"],
            "scenario_id": calibrated.scenario_id,
            "joint_draw_information_bits_per_issue": (
                calibrated.calibrated_bits
            ),
            "parameter_name": calibrated.parameter_name,
            "parameter_value": calibrated.parameter_value,
        },
        "truth_artifact_digest": truth_artifact["artifact_digest"],
        "seed_policy": seed_policy,
        "seed_policy_digest": seed_policy_digest,
        "replicate_seed": int(derived["seed"]) % (2**32),
        "issue_count": issue_count,
        "draw_digest": canonical_digest(
            [
                {
                    "issue_index": issue.issue_index,
                    "sorted_red_numbers": list(issue.sorted_red_numbers),
                }
                for issue in issues
            ],
            domain="dehps.m4.synthetic.draws.v1",
        ),
        "target_digest": canonical_digest(
            [list(issue.target_vector) for issue in issues],
            domain="dehps.m4.synthetic.targets.v1",
        ),
        "preregistration_digest": PREREGISTRATION_DIGEST,
        "decision_policy_digest": DECISION_POLICY_DIGEST,
        "config_digest": manifest.artifact_digest,
        "calibration_seed_domain": "M4_P2_CALIBRATION",
        "evaluation_seed_domain_used": False,
        "eligible_for_evaluation": False,
        "eligible_for_power_evidence": False,
        "eligible_for_false_positive_evidence": False,
        "eligible_for_p2_gate_evidence": False,
        "issues": issue_payloads,
    }
    payload["artifact_digest"] = canonical_digest(
        payload, domain="dehps.m4.synthetic.dataset.v1"
    )
    return payload
