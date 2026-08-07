from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from math import comb, fsum, log, log2
from pathlib import Path
from typing import Any

import numpy as np

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

from .contracts import json_compatible_copy

FIXTURE_FREEZE_TASK_KEY = "m4-v2-branch-identifiability-fixture-freeze"
FIXTURE_FREEZE_CAPABILITY = "m4_v2_branch_identifiability_fixture_freeze"
FIXTURE_FREEZE_COMPLETION_FACT = (
    "m4-v2-branch-identifiability-fixture-freeze:FROZEN"
)
PREFLIGHT_EXECUTION_TASK_KEY = "m4-v2-branch-identifiability-preflight-execution"
FIXTURE_FREEZE_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-v2-branch-fixture-freeze-source-contract-v1.json"
)

LEGAL_NUMBER_COUNT = 33
DRAW_SIZE = 6
LEGAL_COMBINATION_COUNT = comb(LEGAL_NUMBER_COUNT, DRAW_SIZE)
NUMBER_MARGINAL = Fraction(DRAW_SIZE, LEGAL_NUMBER_COUNT)
PAIR_EVENT_PROBABILITY = Fraction(7, 124)
IS4_WEIGHTS = (
    Fraction(219, 221),
    Fraction(-1, 1),
    Fraction(1, 1),
    Fraction(-1, 1),
    Fraction(1, 1),
    Fraction(-219, 221),
    Fraction(1, 1),
)


class FixtureFreezeError(RuntimeError):
    pass


@dataclass(frozen=True)
class FixtureFreezeRun:
    solver_contract: Mapping[str, Any]
    orthogonal_control_contract: Mapping[str, Any]
    legacy_role_resolution_contract: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (
            self.solver_contract,
            self.orthogonal_control_contract,
            self.legacy_role_resolution_contract,
            self.completion,
        )


def load_fixture_freeze_source_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FixtureFreezeError(
            f"fixture_freeze_source_contract_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-branch-fixture-freeze-source-contract.v1"
        or payload.get("artifact_type")
        != "m4_v2_branch_fixture_freeze_source_contract"
        or payload.get("contract_key") != "M4_V2_BRANCH_FIXTURE_FREEZE_SOURCE"
        or payload.get("research_request_key")
        != "research-m4-v2-branch-fixture-freeze-round-37-20260807"
        or payload.get("research_request_id") != 306
        or payload.get("research_execution_id") != 227
        or payload.get("result_blind") is not True
        or payload.get("formal_execution_allowed") is not False
        or payload.get("historical_outcomes_read") is not False
        or payload.get("statistical_results_read") is not False
        or payload.get("evidence_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or not entries
        or not isinstance(frozen, dict)
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain="dehps.m4.v2.branch-fixture-freeze-source-set.v1",
        )
    ):
        raise FixtureFreezeError("fixture_freeze_source_contract_invalid")
    paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise FixtureFreezeError("fixture_freeze_source_entry_invalid")
        relative = str(entry.get("path") or "")
        digest = str(entry.get("content_sha256") or "")
        parsed = Path(relative)
        if (
            not relative
            or parsed.is_absolute()
            or ".." in parsed.parts
            or parsed.as_posix() != relative
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or relative in paths
        ):
            raise FixtureFreezeError("fixture_freeze_source_entry_invalid")
        paths.add(relative)
    _validate_frozen_contract(frozen)
    return payload


def verify_fixture_freeze_source_bytes(
    *,
    root_dir: Path,
    contract: Mapping[str, Any],
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise FixtureFreezeError(f"fixture_freeze_source_missing:{relative}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise FixtureFreezeError(f"fixture_freeze_source_modified:{relative}")


def build_fixture_freeze_artifacts(
    *,
    source_contract: Mapping[str, Any],
    preflight_design_execution_artifact_digest: str,
    preflight_design_completion_digest: str,
    cross_branch_preflight_design_digest: str,
    execution_id: str,
    git_commit: str,
) -> FixtureFreezeRun:
    for name, digest in (
        ("source contract", source_contract.get("artifact_digest")),
        ("preflight design execution", preflight_design_execution_artifact_digest),
        ("preflight design completion", preflight_design_completion_digest),
        ("cross-branch preflight design", cross_branch_preflight_design_digest),
    ):
        if not isinstance(digest, str) or len(digest) != 64:
            raise FixtureFreezeError(f"fixture_freeze_parent_invalid:{name}")
    frozen = source_contract.get("frozen_contract")
    if not isinstance(frozen, Mapping):
        raise FixtureFreezeError("fixture_freeze_contract_missing")
    _validate_frozen_contract(frozen)
    parents = (
        str(source_contract["artifact_digest"]),
        preflight_design_execution_artifact_digest,
        preflight_design_completion_digest,
        cross_branch_preflight_design_digest,
    )
    solver = _artifact(
        schema_version="dehps-m4-v2-joint-maxent-fixture-contract.v1",
        artifact_type="m4_v2_joint_maxent_fixture_contract",
        body={
            "status": "FROZEN_FIXTURES",
            "solver_contract": frozen["solver_contract"],
            "exact_solver_fixtures": frozen["exact_solver_fixtures"],
            "formal_execution_allowed": False,
            "preflight_execution_status": "NOT_RUN",
            "preflight_result_count": 0,
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "production_action": "none",
        },
        parent_digests=parents,
        domain="dehps.m4.v2.joint-maxent-fixture-contract.v1",
    )
    controls = _artifact(
        schema_version="dehps-m4-v2-orthogonal-control-fixture-contract.v1",
        artifact_type="m4_v2_orthogonal_control_fixture_contract",
        body={
            "status": "FROZEN_FIXTURES",
            "acceptance": frozen["acceptance"],
            "fixtures": frozen["orthogonal_control_fixtures"],
            "formal_execution_allowed": False,
            "preflight_execution_status": "NOT_RUN",
            "preflight_result_count": 0,
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "production_action": "none",
        },
        parent_digests=(*parents, str(solver["artifact_digest"])),
        domain="dehps.m4.v2.orthogonal-control-fixture-contract.v1",
    )
    legacy = _artifact(
        schema_version="dehps-m4-v2-legacy-role-resolution-fixture-contract.v1",
        artifact_type="m4_v2_legacy_role_resolution_fixture_contract",
        body={
            "status": "FROZEN_FIXTURES",
            "fixtures": frozen["legacy_role_resolution_fixtures"],
            "role_resolution_status": "NOT_RUN",
            "formal_execution_allowed": False,
            "preflight_result_count": 0,
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "decision_credit": False,
            "production_action": "none",
        },
        parent_digests=(*parents, str(solver["artifact_digest"])),
        domain="dehps.m4.v2.legacy-role-resolution-fixture-contract.v1",
    )
    completion = _artifact(
        schema_version="dehps-m4-v2-branch-fixture-freeze-completion.v1",
        artifact_type="m4_v2_branch_fixture_freeze_completion",
        body={
            "status": "COMPLETE",
            "execution_id": execution_id,
            "git_commit": git_commit,
            "source_contract_digest": source_contract["artifact_digest"],
            "solver_fixture_contract_digest": solver["artifact_digest"],
            "orthogonal_control_fixture_contract_digest": controls[
                "artifact_digest"
            ],
            "legacy_role_resolution_fixture_contract_digest": legacy[
                "artifact_digest"
            ],
            "fixture_contract_count": 3,
            "completion_fact": FIXTURE_FREEZE_COMPLETION_FACT,
            "formal_branch_runs_executed": 0,
            "preflight_execution_count": 0,
            "preflight_result_count": 0,
            "actual_fold_count": 0,
            "historical_outcomes_read": False,
            "p2_6_1_partial_statistical_results_read": False,
            "p2_6_3_statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_increment": 0,
            "next_consumer": PREFLIGHT_EXECUTION_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(
            *parents,
            str(solver["artifact_digest"]),
            str(controls["artifact_digest"]),
            str(legacy["artifact_digest"]),
        ),
        domain="dehps.m4.v2.branch-fixture-freeze-completion.v1",
    )
    return FixtureFreezeRun(
        solver_contract=solver,
        orthogonal_control_contract=controls,
        legacy_role_resolution_contract=legacy,
        completion=completion,
    )


def computed_fixture_contract() -> dict[str, Any]:
    group_partition, group_q_a, group_q_b = _group_fixture(
        group_a_size=16,
        group_b_size=17,
        group_a_weight=Fraction(2),
        group_b_weight=Fraction(1),
    )
    overlap_partition, overlap_q_in, overlap_q_out = _group_fixture(
        group_a_size=6,
        group_b_size=27,
        group_a_weight=Fraction(2),
        group_b_weight=Fraction(1),
    )
    marginal_gain = _composite_binary_gain(
        ((16, group_q_a), (17, group_q_b)),
        baseline=NUMBER_MARGINAL,
    )
    temporal_gain = _composite_binary_gain(
        ((6, overlap_q_in), (27, overlap_q_out)),
        baseline=NUMBER_MARGINAL,
    )
    joint_gain = _is4_joint_gain(Fraction(1, 2))
    is2_truth = _is2_joint_residual_truth()
    is3_truth = _is3_joint_residual_truth()
    return {
        "exact_solver_fixtures": [
            {
                "fixture_id": "JME_UNIFORM",
                "q": "q_i=6/33",
                "expected_lambda": "all_zero_in_lambda_33_equals_0_gauge",
                "expected_partition": LEGAL_COMBINATION_COUNT,
            },
            {
                "fixture_id": "JME_GROUP_16_17_ODDS_2",
                "weights": "w_1..w_16=2;w_17..w_33=1",
                "expected_partition": group_partition,
                "expected_q_group_a": _fraction_text(group_q_a),
                "expected_q_group_b": _fraction_text(group_q_b),
                "expected_lambda": "lambda_1..lambda_16=ln(2);lambda_17..lambda_33=0",
            },
            {
                "fixture_id": "JME_OVERLAP_6_27_ODDS_2",
                "weights": "w_i=2_for_six_prior_draw_numbers;otherwise_1",
                "expected_partition": overlap_partition,
                "expected_q_in_prior": _fraction_text(overlap_q_in),
                "expected_q_outside_prior": _fraction_text(overlap_q_out),
                "expected_lambda": "ln(2)_on_prior_draw_numbers;zero_elsewhere;number_33_outside_prior",
            },
            {
                "fixture_id": "JME_INVALID_BOUNDARIES",
                "cases": [
                    "sum(q)_outside_1e-12_of_6",
                    "q_i_outside_closed_interval_1e-9_to_1_minus_1e-9",
                    "nan_or_infinity",
                ],
                "expected": "FAIL_CLOSED_WITHOUT_SUBSTITUTION",
            },
        ],
        "orthogonal_control_fixtures": [
            {
                "fixture_id": "V2_M1_GROUP_ODDS_2_STATIONARY",
                "definition": "iid_legal_draws_from_JME_GROUP_16_17_ODDS_2",
                "expected_roles": {
                    "MARGINAL_STATIC": "POSITIVE_CONTROL",
                    "TEMPORAL_MARGINAL_INCREMENT": "NEGATIVE_CONTROL",
                    "JOINT_RESIDUAL_INCREMENT": "NEGATIVE_CONTROL",
                },
                "truth_anchor_bits": {
                    "marginal_static": marginal_gain,
                    "temporal_increment": 0.0,
                    "joint_residual": 0.0,
                },
            },
            {
                "fixture_id": "V2_T1_OVERLAP_ODDS_2_MARKOV",
                "definition": "Q(y_t|y_t_minus_1)_proportional_to_2_pow_intersection_size",
                "strict_history_state": "complete_previous_legal_draw",
                "stationarity_basis": "symmetric_kernel_is_doubly_stochastic_on_Omega",
                "expected_roles": {
                    "MARGINAL_STATIC": "NEGATIVE_CONTROL",
                    "TEMPORAL_MARGINAL_INCREMENT": "POSITIVE_CONTROL",
                    "JOINT_RESIDUAL_INCREMENT": "NEGATIVE_CONTROL",
                },
                "truth_anchor_bits": {
                    "marginal_static": 0.0,
                    "temporal_increment": temporal_gain,
                    "joint_residual": 0.0,
                },
            },
            {
                "fixture_id": "V2_J1_HISTORY_IS4_LAMBDA_HALF",
                "definition": "history_visible_state_selects_IS4_sign_with_lambda_1_over_2",
                "strict_history_state": "lexicographic_half_of_previous_legal_draw",
                "marginal_basis": "both_states_preserve_every_q_i_equal_6_over_33",
                "expected_roles": {
                    "MARGINAL_STATIC": "NEGATIVE_CONTROL",
                    "TEMPORAL_MARGINAL_INCREMENT": "NEGATIVE_CONTROL",
                    "JOINT_RESIDUAL_INCREMENT": "POSITIVE_CONTROL",
                },
                "truth_anchor_bits": {
                    "marginal_static": 0.0,
                    "temporal_increment": 0.0,
                    "joint_residual": joint_gain,
                },
            },
            {
                "fixture_id": "NULL_UNIFORM_LEGAL_SIX_OF_33",
                "expected_roles": {
                    "MARGINAL_STATIC": "NEGATIVE_CONTROL",
                    "TEMPORAL_MARGINAL_INCREMENT": "NEGATIVE_CONTROL",
                    "JOINT_RESIDUAL_INCREMENT": "NEGATIVE_CONTROL",
                },
                "truth_anchor_bits": {
                    "marginal_static": 0.0,
                    "temporal_increment": 0.0,
                    "joint_residual": 0.0,
                },
            },
        ],
        "legacy_role_resolution_fixtures": [
            {
                "fixture_id": "IS2_LOCAL_TEMPORAL_DELTA_QUARTER",
                "parameter": "delta=1/4",
                "joint_residual_truth_by_state_bits": list(is2_truth),
                "expected_joint_direction": "positive",
                "role_after_successful_preflight": "POSITIVE_CONTROL",
            },
            {
                "fixture_id": "IS3_PAIR_CONDITIONAL_QUARTER_BASE_RATE",
                "parameter": "delta=p_pair/4_where_p_pair=7/124",
                "conditional_pair_probabilities": ["21/496", "35/496"],
                "joint_residual_truth_by_state_bits": list(is3_truth),
                "expected_joint_direction": "positive",
                "role_after_successful_preflight": (
                    "POSITIVE_CONTROL_WITH_SYNTHETIC_INSTRUMENT_DECISION_CREDIT_FALSE"
                ),
            },
        ],
    }


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    solver = frozen.get("solver_contract")
    acceptance = frozen.get("acceptance")
    computed = computed_fixture_contract()
    if (
        not isinstance(solver, Mapping)
        or solver.get("family") != "fixed_cardinality_exponential_family"
        or solver.get("support") != "Omega_binary_33_sum_6"
        or solver.get("gauge") != "lambda_33=0"
        or solver.get("partition_method")
        != "float64_elementary_symmetric_polynomial_dynamic_program"
        or solver.get("solver")
        != "deterministic_damped_newton_with_analytic_covariance_hessian"
        or solver.get("maximum_iterations") != 100
        or solver.get("maximum_marginal_residual") != 1e-12
        or solver.get("input_sum_tolerance") != 1e-12
        or solver.get("input_interior_floor") != 1e-9
        or solver.get("renormalize_input") is not False
        or solver.get("uniform_fallback") is not False
        or solver.get("independent_bernoulli_fallback") is not False
        or solver.get("failure_status")
        != "NOT_RUN_MEASUREMENT_HEALTH_INCONCLUSIVE"
        or not isinstance(acceptance, Mapping)
        or acceptance.get("positive_floor_bits") != 0.001
        or acceptance.get("negative_absolute_tolerance_bits") != 1e-10
        or acceptance.get("maximum_solver_residual") != 1e-12
        or frozen.get("exact_solver_fixtures")
        != computed["exact_solver_fixtures"]
        or not _nested_float_close(
            frozen.get("orthogonal_control_fixtures"),
            computed["orthogonal_control_fixtures"],
            tolerance=5e-13,
        )
        or not _nested_float_close(
            frozen.get("legacy_role_resolution_fixtures"),
            computed["legacy_role_resolution_fixtures"],
            tolerance=5e-13,
        )
    ):
        raise FixtureFreezeError("fixture_freeze_frozen_contract_drift")


def _group_fixture(
    *,
    group_a_size: int,
    group_b_size: int,
    group_a_weight: Fraction,
    group_b_weight: Fraction,
) -> tuple[int, Fraction, Fraction]:
    weighted = tuple(
        (
            k,
            Fraction(comb(group_a_size, k) * comb(group_b_size, DRAW_SIZE - k))
            * group_a_weight**k
            * group_b_weight ** (DRAW_SIZE - k),
        )
        for k in range(DRAW_SIZE + 1)
        if k <= group_a_size and DRAW_SIZE - k <= group_b_size
    )
    partition = sum(value for _, value in weighted)
    expected_a_count = sum(Fraction(k) * value for k, value in weighted) / partition
    q_a = expected_a_count / group_a_size
    q_b = (DRAW_SIZE - expected_a_count) / group_b_size
    if partition.denominator != 1 or group_a_size * q_a + group_b_size * q_b != 6:
        raise FixtureFreezeError("fixture_freeze_group_combinatorics_invalid")
    return partition.numerator, q_a, q_b


def _composite_binary_gain(
    groups: Sequence[tuple[int, Fraction]],
    *,
    baseline: Fraction,
) -> float:
    p = float(baseline)
    return fsum(
        count
        * (
            float(q) * log2(float(q) / p)
            + float(1 - q) * log2(float(1 - q) / (1.0 - p))
        )
        for count, q in groups
    )


def _is4_joint_gain(parameter: Fraction) -> float:
    baseline = tuple(
        Fraction(comb(16, k) * comb(17, DRAW_SIZE - k), LEGAL_COMBINATION_COUNT)
        for k in range(DRAW_SIZE + 1)
    )
    rows = tuple(
        tuple(
            probability * (1 + sign * parameter * weight)
            for probability, weight in zip(baseline, IS4_WEIGHTS, strict=True)
        )
        for sign in (-1, 1)
    )
    if any(sum(row) != 1 for row in rows):
        raise FixtureFreezeError("fixture_freeze_is4_normalization_invalid")
    return 0.5 * fsum(
        float(value) * log2(float(value / null))
        for row in rows
        for value, null in zip(row, baseline, strict=True)
    )


@lru_cache(maxsize=1)
def _lexicographic_half_number_counts() -> tuple[int, ...]:
    counts = [0] * LEGAL_NUMBER_COUNT
    for index, draw in enumerate(
        combinations(range(LEGAL_NUMBER_COUNT), DRAW_SIZE)
    ):
        if index >= LEGAL_COMBINATION_COUNT // 2:
            break
        for number in draw:
            counts[number] += 1
    if sum(counts) != DRAW_SIZE * (LEGAL_COMBINATION_COUNT // 2):
        raise FixtureFreezeError("fixture_freeze_lexicographic_half_invalid")
    return tuple(counts)


def _is2_joint_residual_truth() -> tuple[float, float]:
    half = LEGAL_COMBINATION_COUNT // 2
    total_number_count = comb(LEGAL_NUMBER_COUNT - 1, DRAW_SIZE - 1)
    lower = _lexicographic_half_number_counts()
    upper = tuple(total_number_count - value for value in lower)
    results = []
    for lower_probability in (Fraction(3, 4), Fraction(1, 4)):
        marginals = tuple(
            lower_probability * Fraction(left, half)
            + (1 - lower_probability) * Fraction(right, half)
            for left, right in zip(lower, upper, strict=True)
        )
        theta, log_partition, _ = _solve_maxent(marginals)
        expected_log_probability = (
            float(lower_probability) * log(float(lower_probability) / half)
            + float(1 - lower_probability)
            * log(float(1 - lower_probability) / half)
        )
        expected_baseline_log_probability = (
            float(np.dot(np.asarray(marginals, dtype=np.float64), theta))
            - log_partition
        )
        results.append(
            (expected_log_probability - expected_baseline_log_probability)
            / log(2.0)
        )
    return tuple(results)  # type: ignore[return-value]


def _pair_event_number_counts() -> tuple[int, ...]:
    target = (
        comb(31, 4) + comb(30, 3) - comb(29, 2)
    )
    other = 2 * comb(30, 3) - 28
    counts = (target, target, target, target, *(other for _ in range(29)))
    event_count = PAIR_EVENT_PROBABILITY * LEGAL_COMBINATION_COUNT
    if event_count.denominator != 1 or sum(counts) != DRAW_SIZE * event_count:
        raise FixtureFreezeError("fixture_freeze_pair_counts_invalid")
    return counts


def _is3_joint_residual_truth() -> tuple[float, float]:
    event_count_fraction = PAIR_EVENT_PROBABILITY * LEGAL_COMBINATION_COUNT
    event_count = event_count_fraction.numerator
    non_event_count = LEGAL_COMBINATION_COUNT - event_count
    total_number_count = comb(LEGAL_NUMBER_COUNT - 1, DRAW_SIZE - 1)
    event_number_counts = _pair_event_number_counts()
    results = []
    for event_probability in (Fraction(21, 496), Fraction(35, 496)):
        marginals = tuple(
            event_probability * Fraction(count, event_count)
            + (1 - event_probability)
            * Fraction(total_number_count - count, non_event_count)
            for count in event_number_counts
        )
        theta, log_partition, _ = _solve_maxent(marginals)
        expected_log_probability = (
            float(event_probability) * log(float(event_probability) / event_count)
            + float(1 - event_probability)
            * log(float(1 - event_probability) / non_event_count)
        )
        expected_baseline_log_probability = (
            float(np.dot(np.asarray(marginals, dtype=np.float64), theta))
            - log_partition
        )
        results.append(
            (expected_log_probability - expected_baseline_log_probability)
            / log(2.0)
        )
    return tuple(results)  # type: ignore[return-value]


def _solve_maxent(
    target: Sequence[Fraction],
) -> tuple[np.ndarray, float, float]:
    target_array = np.asarray(target, dtype=np.float64)
    if (
        target_array.shape != (LEGAL_NUMBER_COUNT,)
        or not np.isfinite(target_array).all()
        or np.min(target_array) < 1e-9
        or np.max(target_array) > 1.0 - 1e-9
        or abs(float(target_array.sum()) - DRAW_SIZE) > 1e-12
    ):
        raise FixtureFreezeError("fixture_freeze_solver_input_invalid")
    gauge = np.zeros(LEGAL_NUMBER_COUNT - 1, dtype=np.float64)
    for _ in range(100):
        theta = np.concatenate((gauge, np.zeros(1, dtype=np.float64)))
        log_partition, marginals, covariance = _fixed_cardinality_moments(theta)
        residual = marginals[:-1] - target_array[:-1]
        maximum_residual = float(np.max(np.abs(marginals - target_array)))
        if maximum_residual <= 1e-12:
            return theta, log_partition, maximum_residual
        try:
            step = np.linalg.solve(covariance[:-1, :-1], residual)
        except np.linalg.LinAlgError as exc:
            raise FixtureFreezeError("fixture_freeze_solver_singular") from exc
        current_norm = float(np.dot(residual, residual))
        scale = 1.0
        accepted = False
        for _ in range(60):
            candidate = gauge - scale * step
            candidate_theta = np.concatenate(
                (candidate, np.zeros(1, dtype=np.float64))
            )
            _, candidate_marginals, _ = _fixed_cardinality_moments(
                candidate_theta
            )
            candidate_residual = candidate_marginals[:-1] - target_array[:-1]
            if float(np.dot(candidate_residual, candidate_residual)) < current_norm:
                gauge = candidate
                accepted = True
                break
            scale *= 0.5
        if not accepted:
            raise FixtureFreezeError("fixture_freeze_solver_line_search_failed")
    raise FixtureFreezeError("fixture_freeze_solver_not_converged")


def _fixed_cardinality_moments(
    theta: np.ndarray,
) -> tuple[float, np.ndarray, np.ndarray]:
    offset = float(np.max(theta))
    weights = np.exp(theta - offset)
    partition = _elementary_symmetric(weights, DRAW_SIZE)[DRAW_SIZE]
    log_partition = log(float(partition)) + DRAW_SIZE * offset
    marginals = np.empty(LEGAL_NUMBER_COUNT, dtype=np.float64)
    for index, weight in enumerate(weights):
        excluded = np.delete(weights, index)
        marginals[index] = (
            weight
            * _elementary_symmetric(excluded, DRAW_SIZE - 1)[DRAW_SIZE - 1]
            / partition
        )
    covariance = -np.outer(marginals, marginals)
    np.fill_diagonal(covariance, marginals * (1.0 - marginals))
    for left in range(LEGAL_NUMBER_COUNT):
        for right in range(left + 1, LEGAL_NUMBER_COUNT):
            excluded = np.delete(weights, (left, right))
            joint = (
                weights[left]
                * weights[right]
                * _elementary_symmetric(excluded, DRAW_SIZE - 2)[DRAW_SIZE - 2]
                / partition
            )
            covariance[left, right] += joint
            covariance[right, left] += joint
    return log_partition, marginals, covariance


def _elementary_symmetric(weights: np.ndarray, degree: int) -> np.ndarray:
    values = np.zeros(degree + 1, dtype=np.float64)
    values[0] = 1.0
    for weight in weights:
        for current in range(degree, 0, -1):
            values[current] += weight * values[current - 1]
    return values


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _nested_float_close(left: Any, right: Any, *, tolerance: float) -> bool:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return set(left) == set(right) and all(
            _nested_float_close(left[key], right[key], tolerance=tolerance)
            for key in left
        )
    if (
        isinstance(left, Sequence)
        and isinstance(right, Sequence)
        and not isinstance(left, (str, bytes))
        and not isinstance(right, (str, bytes))
    ):
        return len(left) == len(right) and all(
            _nested_float_close(a, b, tolerance=tolerance)
            for a, b in zip(left, right, strict=True)
        )
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if isinstance(left, bool) or isinstance(right, bool):
            return left is right
        return abs(float(left) - float(right)) <= tolerance
    return left == right


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
    domain: str,
) -> dict[str, Any]:
    json_body = json_compatible_copy(body)
    if not isinstance(json_body, dict):
        raise FixtureFreezeError("fixture_freeze_artifact_body_invalid")
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "artifact_digest": "",
        **json_body,
        "parent_digests": list(parent_digests),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload
