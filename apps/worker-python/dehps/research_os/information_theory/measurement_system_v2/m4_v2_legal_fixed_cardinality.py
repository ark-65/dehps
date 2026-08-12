from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from itertools import combinations
from typing import Final

LEGAL_BALL_COUNT: Final = 33
LEGAL_SELECTION_COUNT: Final = 6
LEGAL_STATE_COUNT: Final = 1_107_568
MAXIMUM_ENTROPY_MAX_ITERATIONS: Final = 100
MAXIMUM_ENTROPY_LINE_SEARCH_STEPS: Final = 60
MAXIMUM_ENTROPY_RESIDUAL_TOLERANCE: Final = 1e-12
MAXIMUM_ENTROPY_SUM_TOLERANCE: Final = 1e-12
MAXIMUM_ENTROPY_INTERIOR_FLOOR: Final = 1e-9
OVERLAP_THETA_MAX_ITERATIONS: Final = 128
OVERLAP_THETA_MAX_ABS_BRACKET: Final = 128.0
OVERLAP_THETA_SCORE_TOLERANCE: Final = 1e-12


class LegalFixedCardinalityError(ValueError):
    pass


@dataclass(frozen=True)
class FixedCardinalityMaximumEntropySolution:
    """Unique fixed-cardinality maximum-entropy fit in the lambda_33=0 gauge."""

    weights: tuple[float, ...]
    lambdas: tuple[float, ...]
    partition: float
    log_partition: float
    marginals: tuple[float, ...]
    maximum_marginal_residual: float
    iterations: int

    @property
    def lambda_values(self) -> tuple[float, ...]:
        """Unambiguous alias for callers that avoid the plural ``lambdas``."""

        return self.lambdas


@dataclass(frozen=True)
class OverlapTiltEvaluation:
    theta: float
    coefficient_masses: tuple[float, ...]
    partition: float
    expected_overlap: float
    marginals: tuple[float, ...]
    actual_overlap: int
    actual_log_probability: float


@dataclass(frozen=True)
class OverlapThetaSolution:
    theta: float
    expected_overlap_sum: float
    observed_overlap_sum: int
    score: float
    information: float
    iterations: int
    bracket: tuple[float, float]


@dataclass(frozen=True)
class IS4Projection:
    """Exact registered IS4 feature projected off constant/singleton tangents."""

    history_state: int
    intercept: float
    gauge_coefficients: tuple[float, ...]
    label_coefficients: tuple[float, ...]
    scale: float
    normalization_residual: float
    singleton_residuals: tuple[float, ...]


@dataclass(frozen=True)
class AffineResidualEtaSolution:
    eta: float
    score: float
    information: float
    iterations: int
    bracket: tuple[float, float]


def legal_states() -> Iterable[tuple[int, ...]]:
    """Yield zero-based six-of-33 states in the frozen lexicographic order."""

    return combinations(range(LEGAL_BALL_COUNT), LEGAL_SELECTION_COUNT)


def elementary_symmetric(weights: Sequence[float], degree: int = 6) -> float:
    checked = _checked_weights(weights)
    if degree != LEGAL_SELECTION_COUNT:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_shape_invalid")
    partition = _elementary_symmetric_coefficients(checked, degree)[degree]
    if not math.isfinite(partition) or partition <= 0.0:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_partition_invalid")
    return partition


def fixed_cardinality_marginals(weights: Sequence[float]) -> tuple[float, ...]:
    checked = _checked_weights(weights)
    partition = elementary_symmetric(checked)
    marginals = tuple(
        weight
        * _elementary_symmetric_coefficients(
            checked[:held_out] + checked[held_out + 1 :], 5
        )[5]
        / partition
        for held_out, weight in enumerate(checked)
    )
    if (
        any(not math.isfinite(value) for value in marginals)
        or abs(math.fsum(marginals) - LEGAL_SELECTION_COUNT) > 1e-11
    ):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_moments_invalid")
    return marginals


def elementary_symmetric_degree_five(weights: Sequence[float]) -> float:
    if len(weights) != LEGAL_BALL_COUNT - 1:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_shape_invalid")
    checked = _checked_positive_finite_values(weights)
    value = _elementary_symmetric_coefficients(checked, 5)[5]
    if not math.isfinite(value) or value <= 0.0:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_partition_invalid")
    return value


def solve_fixed_cardinality_maximum_entropy(
    target_marginals: Sequence[float],
    *,
    maximum_iterations: int = MAXIMUM_ENTROPY_MAX_ITERATIONS,
    residual_tolerance: float = MAXIMUM_ENTROPY_RESIDUAL_TOLERANCE,
) -> FixedCardinalityMaximumEntropySolution:
    """Fit the frozen six-of-33 exponential family without substitution.

    Inputs are validated, never clipped or renormalized.  Newton steps use the
    analytic indicator covariance on the 32-dimensional ``lambda_33=0`` gauge
    and a deterministic halving line search.
    """

    target = _checked_target_marginals(target_marginals)
    if (
        isinstance(maximum_iterations, bool)
        or not isinstance(maximum_iterations, int)
        or maximum_iterations <= 0
        or maximum_iterations > MAXIMUM_ENTROPY_MAX_ITERATIONS
    ):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_solver_limit_invalid")
    if (
        isinstance(residual_tolerance, bool)
        or not isinstance(residual_tolerance, (int, float))
        or not math.isfinite(residual_tolerance)
        or residual_tolerance <= 0.0
        or residual_tolerance > MAXIMUM_ENTROPY_RESIDUAL_TOLERANCE
    ):
        raise LegalFixedCardinalityError(
            "legal_fixed_cardinality_solver_tolerance_invalid"
        )

    gauge = [0.0] * (LEGAL_BALL_COUNT - 1)
    for iteration in range(maximum_iterations):
        lambdas = (*gauge, 0.0)
        log_partition, marginals, covariance = _fixed_cardinality_moments(lambdas)
        residual = tuple(
            marginals[index] - target[index]
            for index in range(LEGAL_BALL_COUNT - 1)
        )
        maximum_residual = max(
            abs(marginals[index] - target[index])
            for index in range(LEGAL_BALL_COUNT)
        )
        if maximum_residual <= residual_tolerance:
            return _maximum_entropy_solution(
                lambdas,
                log_partition=log_partition,
                marginals=marginals,
                maximum_residual=maximum_residual,
                iterations=iteration,
            )

        hessian = tuple(
            row[: LEGAL_BALL_COUNT - 1]
            for row in covariance[: LEGAL_BALL_COUNT - 1]
        )
        step = _solve_linear_system(hessian, residual)
        current_norm = math.fsum(value * value for value in residual)
        scale = 1.0
        accepted = False
        for _ in range(MAXIMUM_ENTROPY_LINE_SEARCH_STEPS):
            candidate_gauge = [
                gauge[index] - scale * step[index]
                for index in range(LEGAL_BALL_COUNT - 1)
            ]
            if not all(math.isfinite(value) for value in candidate_gauge):
                scale *= 0.5
                continue
            candidate_lambdas = (*candidate_gauge, 0.0)
            _, candidate_marginals, _ = _fixed_cardinality_moments(
                candidate_lambdas
            )
            candidate_norm = math.fsum(
                (candidate_marginals[index] - target[index]) ** 2
                for index in range(LEGAL_BALL_COUNT - 1)
            )
            if math.isfinite(candidate_norm) and candidate_norm < current_norm:
                gauge = candidate_gauge
                accepted = True
                break
            scale *= 0.5
        if not accepted:
            raise LegalFixedCardinalityError(
                "legal_fixed_cardinality_solver_line_search_failed"
            )
    raise LegalFixedCardinalityError("legal_fixed_cardinality_solver_not_converged")


def legal_state_log_probability(
    weights: Sequence[float],
    state: Sequence[int],
    *,
    partition: float | None = None,
) -> float:
    """Return the actual legal-state log probability under base weights."""

    checked_weights = _checked_weights(weights)
    checked_state = _checked_legal_state(state)
    checked_partition = _checked_partition_or_compute(checked_weights, partition)
    result = (
        math.fsum(math.log(checked_weights[index]) for index in checked_state)
        - math.log(checked_partition)
    )
    if not math.isfinite(result) or result > 0.0:
        raise LegalFixedCardinalityError(
            "legal_fixed_cardinality_log_probability_invalid"
        )
    return result


def legal_state_probability(
    weights: Sequence[float],
    state: Sequence[int],
    *,
    partition: float | None = None,
) -> float:
    """Return the actual legal-state probability under base weights."""

    probability = math.exp(
        legal_state_log_probability(weights, state, partition=partition)
    )
    if not math.isfinite(probability) or probability <= 0.0 or probability > 1.0:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_probability_invalid")
    return probability


def overlap_coefficient_masses(
    base_weights: Sequence[float], previous_state: Sequence[int]
) -> tuple[float, ...]:
    """Return raw partition masses for overlaps k=0..6 with ``previous_state``."""

    weights = _checked_weights(base_weights)
    previous = frozenset(_checked_legal_state(previous_state))
    # dynamic[chosen][overlap] is the weighted mass accumulated so far.
    dynamic = [
        [0.0] * (LEGAL_SELECTION_COUNT + 1)
        for _ in range(LEGAL_SELECTION_COUNT + 1)
    ]
    dynamic[0][0] = 1.0
    for label, weight in enumerate(weights):
        overlap_increment = int(label in previous)
        for chosen in range(LEGAL_SELECTION_COUNT, 0, -1):
            for overlap in range(LEGAL_SELECTION_COUNT, overlap_increment - 1, -1):
                dynamic[chosen][overlap] += (
                    dynamic[chosen - 1][overlap - overlap_increment] * weight
                )
    masses = tuple(dynamic[LEGAL_SELECTION_COUNT])
    if any(not math.isfinite(value) or value <= 0.0 for value in masses):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_overlap_mass_invalid")
    partition = elementary_symmetric(weights)
    if not math.isclose(
        math.fsum(masses), partition, rel_tol=2e-15, abs_tol=0.0
    ):
        raise LegalFixedCardinalityError(
            "legal_fixed_cardinality_overlap_partition_mismatch"
        )
    return masses


def evaluate_overlap_tilt(
    base_weights: Sequence[float],
    previous_state: Sequence[int],
    theta: float,
    actual_state: Sequence[int],
) -> OverlapTiltEvaluation:
    """Evaluate the exact one-lag overlap tilt on the legal support."""

    weights = _checked_weights(base_weights)
    previous_tuple = _checked_legal_state(previous_state)
    actual_tuple = _checked_legal_state(actual_state)
    if (
        isinstance(theta, bool)
        or not isinstance(theta, (int, float))
        or not math.isfinite(theta)
    ):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_theta_invalid")
    previous = frozenset(previous_tuple)
    overlap = len(previous.intersection(actual_tuple))
    masses = overlap_coefficient_masses(weights, previous_tuple)
    partition, expected_overlap, _ = _overlap_partition_moments(masses, theta)
    try:
        multiplier = math.exp(theta)
    except OverflowError as exc:
        raise LegalFixedCardinalityError(
            "legal_fixed_cardinality_tilt_weight_invalid"
        ) from exc
    tilted_weights = tuple(
        weight * multiplier if index in previous else weight
        for index, weight in enumerate(weights)
    )
    if any(not math.isfinite(value) or value <= 0.0 for value in tilted_weights):
        raise LegalFixedCardinalityError(
            "legal_fixed_cardinality_tilt_weight_invalid"
        )
    marginals = fixed_cardinality_marginals(tilted_weights)
    actual_log_probability = (
        math.fsum(math.log(weights[index]) for index in actual_tuple)
        + theta * overlap
        - math.log(partition)
    )
    if not math.isfinite(actual_log_probability) or actual_log_probability > 0.0:
        raise LegalFixedCardinalityError(
            "legal_fixed_cardinality_log_probability_invalid"
        )
    return OverlapTiltEvaluation(
        theta=theta,
        coefficient_masses=masses,
        partition=partition,
        expected_overlap=expected_overlap,
        marginals=marginals,
        actual_overlap=overlap,
        actual_log_probability=actual_log_probability,
    )


def solve_overlap_theta(
    coefficient_rows: Sequence[Sequence[float]],
    observed_overlaps: Sequence[int],
    *,
    score_tolerance: float = OVERLAP_THETA_SCORE_TOLERANCE,
    maximum_iterations: int = OVERLAP_THETA_MAX_ITERATIONS,
) -> OverlapThetaSolution:
    """Solve the shared one-lag theta by safeguarded Newton/bisection.

    Each coefficient row must contain the raw legal-support masses for overlap
    ``k=0..6`` under its registered prior.  Boundary-only observations have no
    finite maximum-likelihood root and therefore fail closed.
    """

    rows = tuple(_checked_overlap_masses(row) for row in coefficient_rows)
    if not rows or len(rows) != len(observed_overlaps):
        raise LegalFixedCardinalityError(
            "legal_fixed_cardinality_theta_observations_invalid"
        )
    observed: list[int] = []
    for value in observed_overlaps:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
            or value > LEGAL_SELECTION_COUNT
        ):
            raise LegalFixedCardinalityError(
                "legal_fixed_cardinality_theta_observations_invalid"
            )
        observed.append(value)
    if (
        isinstance(score_tolerance, bool)
        or not isinstance(score_tolerance, (int, float))
        or not math.isfinite(score_tolerance)
        or score_tolerance <= 0.0
        or score_tolerance > OVERLAP_THETA_SCORE_TOLERANCE
        or isinstance(maximum_iterations, bool)
        or not isinstance(maximum_iterations, int)
        or maximum_iterations <= 0
        or maximum_iterations > OVERLAP_THETA_MAX_ITERATIONS
    ):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_theta_limit_invalid")

    observed_sum = sum(observed)
    if observed_sum in (0, LEGAL_SELECTION_COUNT * len(rows)):
        raise LegalFixedCardinalityError(
            "legal_fixed_cardinality_theta_root_not_bracketed"
        )

    def score_information(theta: float) -> tuple[float, float, float]:
        moments = tuple(_overlap_expectation_variance(row, theta) for row in rows)
        expected_sum = math.fsum(item[0] for item in moments)
        information = math.fsum(item[1] for item in moments)
        score = expected_sum - observed_sum
        if (
            not math.isfinite(expected_sum)
            or not math.isfinite(score)
            or not math.isfinite(information)
            or information <= 0.0
        ):
            raise LegalFixedCardinalityError(
                "legal_fixed_cardinality_theta_moments_invalid"
            )
        return score, information, expected_sum

    zero_score, zero_information, zero_expected = score_information(0.0)
    if abs(zero_score) <= score_tolerance:
        return OverlapThetaSolution(
            theta=0.0,
            expected_overlap_sum=zero_expected,
            observed_overlap_sum=observed_sum,
            score=zero_score,
            information=zero_information,
            iterations=0,
            bracket=(0.0, 0.0),
        )

    if zero_score < 0.0:
        lower, lower_score = 0.0, zero_score
        upper = 1.0
        upper_score, _, _ = score_information(upper)
        while upper_score < 0.0 and upper < OVERLAP_THETA_MAX_ABS_BRACKET:
            upper = min(upper * 2.0, OVERLAP_THETA_MAX_ABS_BRACKET)
            upper_score, _, _ = score_information(upper)
    else:
        upper, upper_score = 0.0, zero_score
        lower = -1.0
        lower_score, _, _ = score_information(lower)
        while lower_score > 0.0 and -lower < OVERLAP_THETA_MAX_ABS_BRACKET:
            lower = max(lower * 2.0, -OVERLAP_THETA_MAX_ABS_BRACKET)
            lower_score, _, _ = score_information(lower)
    if lower_score > 0.0 or upper_score < 0.0:
        raise LegalFixedCardinalityError(
            "legal_fixed_cardinality_theta_root_not_bracketed"
        )

    theta = min(max(0.0, lower), upper)
    for iteration in range(1, maximum_iterations + 1):
        score, information, expected_sum = score_information(theta)
        if abs(score) <= score_tolerance:
            return OverlapThetaSolution(
                theta=theta,
                expected_overlap_sum=expected_sum,
                observed_overlap_sum=observed_sum,
                score=score,
                information=information,
                iterations=iteration,
                bracket=(lower, upper),
            )
        if score < 0.0:
            lower = theta
        else:
            upper = theta
        candidate = theta - score / information
        if not math.isfinite(candidate) or not lower < candidate < upper:
            candidate = (lower + upper) / 2.0
        theta = candidate
    raise LegalFixedCardinalityError("legal_fixed_cardinality_theta_not_converged")


_IS4_VALUES = (219.0 / 221.0, -1.0, 1.0, -1.0, 1.0, -219.0 / 221.0, 1.0)


def project_registered_is4_feature(
    base_weights: Sequence[float], *, history_state: int
) -> IS4Projection:
    """Project the frozen signed IS4 feature off all singleton directions.

    The implementation uses elementary-symmetric coefficient tables, never a
    state scan or Bernoulli approximation.  The basis is exactly constant plus
    ``x_i-x_33`` for labels 1..32.
    """

    weights = _checked_weights(base_weights)
    if history_state not in (-1, 1):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_history_state_invalid")
    partition, marginals, covariance = _fixed_cardinality_moments_from_weights(weights)
    group_a = weights[:16]
    group_b = weights[16:]
    a_coefficients = _elementary_symmetric_coefficients(group_a, 6)
    b_coefficients = _elementary_symmetric_coefficients(group_b, 6)
    feature_mean = 0.0
    feature_first = [0.0] * LEGAL_BALL_COUNT
    for k_a in range(7):
        k_b = LEGAL_SELECTION_COUNT - k_a
        mass = a_coefficients[k_a] * b_coefficients[k_b]
        feature = history_state * _IS4_VALUES[k_a]
        feature_mean += feature * mass
        for label, weight in enumerate(weights):
            if label < 16:
                if k_a == 0:
                    continue
                others = group_a[:label] + group_a[label + 1 :]
                owned_mass = (
                    weight
                    * _elementary_symmetric_coefficients(others, k_a - 1)[k_a - 1]
                    * b_coefficients[k_b]
                )
            else:
                if k_b == 0:
                    continue
                local = label - 16
                others = group_b[:local] + group_b[local + 1 :]
                owned_mass = (
                    weight
                    * a_coefficients[k_a]
                    * _elementary_symmetric_coefficients(others, k_b - 1)[k_b - 1]
                )
            feature_first[label] += feature * owned_mass
    feature_mean /= partition
    feature_first = [value / partition for value in feature_first]

    reference = LEGAL_BALL_COUNT - 1
    gram = [[0.0] * LEGAL_BALL_COUNT for _ in range(LEGAL_BALL_COUNT)]
    gram[0][0] = 1.0
    right = [0.0] * LEGAL_BALL_COUNT
    right[0] = feature_mean
    for left in range(LEGAL_BALL_COUNT - 1):
        row = left + 1
        mean = marginals[left] - marginals[reference]
        gram[0][row] = mean
        gram[row][0] = mean
        right[row] = feature_first[left] - feature_first[reference]
        for other in range(LEGAL_BALL_COUNT - 1):
            column = other + 1
            joint_left_other = (
                marginals[left]
                if left == other
                else covariance[left][other] + marginals[left] * marginals[other]
            )
            joint_left_ref = (
                covariance[left][reference]
                + marginals[left] * marginals[reference]
            )
            joint_other_ref = (
                covariance[other][reference]
                + marginals[other] * marginals[reference]
            )
            gram[row][column] = (
                joint_left_other - joint_left_ref - joint_other_ref
                + marginals[reference]
            )
    solution = _solve_symmetric_diagonal_pivoted_ldlt(gram, right)
    intercept = solution[0]
    gauge = solution[1:]
    label_coefficients = (*gauge, -math.fsum(gauge))

    scale = 0.0
    for k_a in range(7):
        k_b = LEGAL_SELECTION_COUNT - k_a
        a_values = sorted(label_coefficients[:16])
        b_values = sorted(label_coefficients[16:])
        minimum_projection = math.fsum(a_values[:k_a]) + math.fsum(b_values[:k_b])
        maximum_projection = (
            math.fsum(a_values[len(a_values) - k_a:])
            + math.fsum(b_values[len(b_values) - k_b:])
        )
        raw = history_state * _IS4_VALUES[k_a] - intercept
        scale = max(
            scale,
            abs(raw - minimum_projection),
            abs(raw - maximum_projection),
        )
    if not math.isfinite(scale) or scale <= 0.0:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_is4_scale_invalid")
    normalization = feature_mean - intercept - math.fsum(
        gauge[index] * (marginals[index] - marginals[reference])
        for index in range(LEGAL_BALL_COUNT - 1)
    )
    singleton_residuals = tuple(
        feature_first[label]
        - intercept * marginals[label]
        - math.fsum(
            gauge[index]
            * (
                (marginals[label] if label == index else covariance[label][index] + marginals[label] * marginals[index])
                - (marginals[label] if label == reference else covariance[label][reference] + marginals[label] * marginals[reference])
            )
            for index in range(LEGAL_BALL_COUNT - 1)
        )
        for label in range(LEGAL_BALL_COUNT)
    )
    if max(abs(normalization), *(abs(value) for value in singleton_residuals)) > 1e-12:
        raise LegalFixedCardinalityError(
            "legal_fixed_cardinality_is4_orthogonality_failed"
        )
    return IS4Projection(
        history_state=history_state,
        intercept=intercept,
        gauge_coefficients=tuple(gauge),
        label_coefficients=tuple(label_coefficients),
        scale=scale,
        normalization_residual=normalization,
        singleton_residuals=singleton_residuals,
    )


def registered_is4_residual_value(
    projection: IS4Projection, state: Sequence[int]
) -> float:
    checked = _checked_legal_state(state)
    k_a = sum(index < 16 for index in checked)
    residual = (
        projection.history_state * _IS4_VALUES[k_a]
        - projection.intercept
        - math.fsum(projection.label_coefficients[index] for index in checked)
    ) / projection.scale
    if not math.isfinite(residual) or abs(residual) > 1.0 + 2e-12:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_is4_residual_invalid")
    return residual


def solve_affine_residual_eta(
    registered_residual_values: Sequence[float],
) -> AffineResidualEtaSolution:
    values = tuple(float(value) for value in registered_residual_values)
    if not values or any(not math.isfinite(value) or abs(value) > 1.0 for value in values):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_eta_values_invalid")
    margin = 1e-12
    lower = -1.0 + margin
    upper = 1.0 - margin

    def score_information(eta: float) -> tuple[float, float]:
        denominators = tuple(1.0 + eta * value for value in values)
        if any(value <= 0.0 or not math.isfinite(value) for value in denominators):
            raise LegalFixedCardinalityError("legal_fixed_cardinality_eta_domain_invalid")
        score = math.fsum(value / denominator for value, denominator in zip(values, denominators, strict=True))
        information = math.fsum((value / denominator) ** 2 for value, denominator in zip(values, denominators, strict=True))
        return score, information

    zero_score, zero_information = score_information(0.0)
    if abs(zero_score) <= 1e-12:
        return AffineResidualEtaSolution(0.0, zero_score, zero_information, 0, (0.0, 0.0))
    lower_score, _ = score_information(lower)
    upper_score, _ = score_information(upper)
    if lower_score <= 0.0 or upper_score >= 0.0:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_eta_root_not_bracketed")
    eta = 0.0
    for iteration in range(1, 101):
        score, information = score_information(eta)
        if abs(score) <= 1e-12 or upper - lower <= 1e-12:
            quantized = float(
                Decimal.from_float(eta).quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_EVEN)
            )
            if not lower < quantized < upper:
                raise LegalFixedCardinalityError("legal_fixed_cardinality_eta_quantization_invalid")
            final_score, final_information = score_information(quantized)
            return AffineResidualEtaSolution(
                quantized, final_score, final_information, iteration, (lower, upper)
            )
        if score > 0.0:
            lower = eta
        else:
            upper = eta
        candidate = eta + score / information
        eta = candidate if lower < candidate < upper else (lower + upper) / 2.0
    raise LegalFixedCardinalityError("legal_fixed_cardinality_eta_not_converged")


def _checked_positive_finite_values(values: Sequence[float]) -> tuple[float, ...]:
    checked: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise LegalFixedCardinalityError("legal_fixed_cardinality_weight_invalid")
        converted = float(value)
        if not math.isfinite(converted) or converted <= 0.0:
            raise LegalFixedCardinalityError("legal_fixed_cardinality_weight_invalid")
        checked.append(converted)
    return tuple(checked)


def _checked_weights(weights: Sequence[float]) -> tuple[float, ...]:
    if len(weights) != LEGAL_BALL_COUNT:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_shape_invalid")
    return _checked_positive_finite_values(weights)


def _checked_target_marginals(values: Sequence[float]) -> tuple[float, ...]:
    if len(values) != LEGAL_BALL_COUNT:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_solver_input_invalid")
    target: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise LegalFixedCardinalityError(
                "legal_fixed_cardinality_solver_input_invalid"
            )
        converted = float(value)
        if (
            not math.isfinite(converted)
            or converted < MAXIMUM_ENTROPY_INTERIOR_FLOOR
            or converted > 1.0 - MAXIMUM_ENTROPY_INTERIOR_FLOOR
        ):
            raise LegalFixedCardinalityError(
                "legal_fixed_cardinality_solver_input_invalid"
            )
        target.append(converted)
    if abs(math.fsum(target) - LEGAL_SELECTION_COUNT) > MAXIMUM_ENTROPY_SUM_TOLERANCE:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_solver_input_invalid")
    return tuple(target)


def _checked_legal_state(state: Sequence[int]) -> tuple[int, ...]:
    if len(state) != LEGAL_SELECTION_COUNT:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_state_invalid")
    checked: list[int] = []
    for label in state:
        if (
            isinstance(label, bool)
            or not isinstance(label, int)
            or label < 0
            or label >= LEGAL_BALL_COUNT
        ):
            raise LegalFixedCardinalityError("legal_fixed_cardinality_state_invalid")
        checked.append(label)
    if len(set(checked)) != LEGAL_SELECTION_COUNT:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_state_invalid")
    return tuple(sorted(checked))


def _checked_partition_or_compute(
    weights: tuple[float, ...], partition: float | None
) -> float:
    if partition is None:
        return elementary_symmetric(weights)
    if (
        isinstance(partition, bool)
        or not isinstance(partition, (int, float))
        or not math.isfinite(float(partition))
        or float(partition) <= 0.0
    ):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_partition_invalid")
    expected = elementary_symmetric(weights)
    checked = float(partition)
    if not math.isclose(checked, expected, rel_tol=2e-15, abs_tol=0.0):
        raise LegalFixedCardinalityError(
            "legal_fixed_cardinality_partition_mismatch"
        )
    return checked


def _elementary_symmetric_coefficients(
    weights: Sequence[float], degree: int
) -> tuple[float, ...]:
    coefficients = [0.0] * (degree + 1)
    coefficients[0] = 1.0
    for weight in weights:
        for index in range(degree, 0, -1):
            coefficients[index] += coefficients[index - 1] * weight
    return tuple(coefficients)


def _fixed_cardinality_moments(
    lambdas: tuple[float, ...],
) -> tuple[float, tuple[float, ...], tuple[tuple[float, ...], ...]]:
    if len(lambdas) != LEGAL_BALL_COUNT or any(
        not math.isfinite(value) for value in lambdas
    ):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_lambda_invalid")
    offset = max(lambdas)
    weights = tuple(math.exp(value - offset) for value in lambdas)
    scaled_partition, marginals, covariance = _fixed_cardinality_moments_from_weights(
        weights
    )
    log_partition = math.log(scaled_partition) + LEGAL_SELECTION_COUNT * offset
    if not math.isfinite(log_partition):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_partition_invalid")
    return log_partition, marginals, covariance


def _fixed_cardinality_moments_from_weights(
    weights: tuple[float, ...],
) -> tuple[float, tuple[float, ...], tuple[tuple[float, ...], ...]]:
    partition = _elementary_symmetric_coefficients(
        weights, LEGAL_SELECTION_COUNT
    )[LEGAL_SELECTION_COUNT]
    if not math.isfinite(partition) or partition <= 0.0:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_partition_invalid")
    marginals: list[float] = []
    for held_out, weight in enumerate(weights):
        remaining = weights[:held_out] + weights[held_out + 1 :]
        degree_five = _elementary_symmetric_coefficients(remaining, 5)[5]
        marginals.append(weight * degree_five / partition)
    covariance = [
        [-marginals[left] * marginals[right] for right in range(LEGAL_BALL_COUNT)]
        for left in range(LEGAL_BALL_COUNT)
    ]
    for index, marginal in enumerate(marginals):
        covariance[index][index] = marginal * (1.0 - marginal)
    for left in range(LEGAL_BALL_COUNT):
        for right in range(left + 1, LEGAL_BALL_COUNT):
            remaining = tuple(
                weight
                for index, weight in enumerate(weights)
                if index != left and index != right
            )
            degree_four = _elementary_symmetric_coefficients(remaining, 4)[4]
            joint = weights[left] * weights[right] * degree_four / partition
            covariance[left][right] += joint
            covariance[right][left] += joint
    if (
        any(not math.isfinite(value) for value in marginals)
        or abs(math.fsum(marginals) - LEGAL_SELECTION_COUNT) > 1e-11
        or any(
            not math.isfinite(value)
            for row in covariance
            for value in row
        )
    ):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_moments_invalid")
    return partition, tuple(marginals), tuple(tuple(row) for row in covariance)


def _solve_linear_system(
    matrix: Sequence[Sequence[float]], right_hand_side: Sequence[float]
) -> tuple[float, ...]:
    size = len(right_hand_side)
    if len(matrix) != size or any(len(row) != size for row in matrix):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_solver_singular")
    augmented = [
        [float(value) for value in matrix[row]] + [float(right_hand_side[row])]
        for row in range(size)
    ]
    for column in range(size):
        pivot_row = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        pivot = augmented[pivot_row][column]
        if not math.isfinite(pivot) or pivot == 0.0:
            raise LegalFixedCardinalityError("legal_fixed_cardinality_solver_singular")
        if pivot_row != column:
            augmented[column], augmented[pivot_row] = (
                augmented[pivot_row],
                augmented[column],
            )
        pivot = augmented[column][column]
        for row in range(column + 1, size):
            factor = augmented[row][column] / pivot
            augmented[row][column] = 0.0
            for index in range(column + 1, size + 1):
                augmented[row][index] -= factor * augmented[column][index]
    solution = [0.0] * size
    for row in range(size - 1, -1, -1):
        numerator = augmented[row][size] - math.fsum(
            augmented[row][column] * solution[column]
            for column in range(row + 1, size)
        )
        pivot = augmented[row][row]
        if not math.isfinite(pivot) or pivot == 0.0:
            raise LegalFixedCardinalityError("legal_fixed_cardinality_solver_singular")
        solution[row] = numerator / pivot
    if any(not math.isfinite(value) for value in solution):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_solver_singular")
    return tuple(solution)


def _solve_symmetric_diagonal_pivoted_ldlt(
    matrix: Sequence[Sequence[float]], right_hand_side: Sequence[float]
) -> tuple[float, ...]:
    """Frozen diagonal-pivoted symmetric LDLT with increasing-index ties."""

    size = len(right_hand_side)
    if len(matrix) != size or any(len(row) != size for row in matrix):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_solver_singular")
    schur = [[float(value) for value in row] for row in matrix]
    permutation = list(range(size))
    transformed_rhs = [float(value) for value in right_hand_side]
    lower = [[0.0] * size for _ in range(size)]
    diagonal = [0.0] * size
    for index in range(size):
        lower[index][index] = 1.0
    for column in range(size):
        pivot = max(
            range(column, size),
            key=lambda index: (abs(schur[index][index]), -permutation[index]),
        )
        if pivot != column:
            schur[column], schur[pivot] = schur[pivot], schur[column]
            for row in schur:
                row[column], row[pivot] = row[pivot], row[column]
            transformed_rhs[column], transformed_rhs[pivot] = (
                transformed_rhs[pivot], transformed_rhs[column]
            )
            permutation[column], permutation[pivot] = (
                permutation[pivot], permutation[column]
            )
            for prior in range(column):
                lower[column][prior], lower[pivot][prior] = (
                    lower[pivot][prior], lower[column][prior]
                )
        diagonal[column] = schur[column][column]
        if not math.isfinite(diagonal[column]) or abs(diagonal[column]) <= 1e-18:
            raise LegalFixedCardinalityError("legal_fixed_cardinality_solver_singular")
        for row in range(column + 1, size):
            lower[row][column] = schur[row][column] / diagonal[column]
        for row in range(column + 1, size):
            for other in range(row, size):
                updated = (
                    schur[other][row]
                    - lower[row][column]
                    * diagonal[column]
                    * lower[other][column]
                )
                schur[other][row] = updated
                schur[row][other] = updated
    forward = [0.0] * size
    for row in range(size):
        forward[row] = transformed_rhs[row] - math.fsum(
            lower[row][column] * forward[column] for column in range(row)
        )
    scaled = [forward[index] / diagonal[index] for index in range(size)]
    permuted_solution = [0.0] * size
    for row in range(size - 1, -1, -1):
        permuted_solution[row] = scaled[row] - math.fsum(
            lower[column][row] * permuted_solution[column]
            for column in range(row + 1, size)
        )
    solution = [0.0] * size
    for current, original in enumerate(permutation):
        solution[original] = permuted_solution[current]
    if any(not math.isfinite(value) for value in solution):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_solver_singular")
    residual = max(
        abs(
            math.fsum(matrix[row][column] * solution[column] for column in range(size))
            - right_hand_side[row]
        )
        for row in range(size)
    )
    if residual > 1e-12:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_solver_residual")
    return tuple(solution)


def _maximum_entropy_solution(
    lambdas: tuple[float, ...],
    *,
    log_partition: float,
    marginals: tuple[float, ...],
    maximum_residual: float,
    iterations: int,
) -> FixedCardinalityMaximumEntropySolution:
    try:
        weights = tuple(math.exp(value) for value in lambdas)
    except OverflowError as exc:
        raise LegalFixedCardinalityError(
            "legal_fixed_cardinality_weight_invalid"
        ) from exc
    partition = elementary_symmetric(weights)
    if not math.isclose(math.log(partition), log_partition, rel_tol=0.0, abs_tol=2e-12):
        raise LegalFixedCardinalityError(
            "legal_fixed_cardinality_partition_mismatch"
        )
    return FixedCardinalityMaximumEntropySolution(
        weights=weights,
        lambdas=lambdas,
        partition=partition,
        log_partition=log_partition,
        marginals=marginals,
        maximum_marginal_residual=maximum_residual,
        iterations=iterations,
    )


def _checked_overlap_masses(values: Sequence[float]) -> tuple[float, ...]:
    if len(values) != LEGAL_SELECTION_COUNT + 1:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_overlap_mass_invalid")
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in values
    ):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_overlap_mass_invalid")
    checked = tuple(float(value) for value in values)
    if any(
        not math.isfinite(converted) or converted <= 0.0
        for value, converted in zip(values, checked, strict=True)
    ):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_overlap_mass_invalid")
    return checked


def _overlap_partition_moments(
    coefficient_masses: Sequence[float], theta: float
) -> tuple[float, float, float]:
    expected, variance, log_partition = _overlap_expectation_variance(
        coefficient_masses, theta
    )
    if log_partition > math.log(float.fromhex("0x1.fffffffffffffp+1023")):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_partition_invalid")
    partition = math.exp(log_partition)
    if not math.isfinite(partition) or partition <= 0.0:
        raise LegalFixedCardinalityError("legal_fixed_cardinality_partition_invalid")
    return partition, expected, variance


def _overlap_expectation_variance(
    coefficient_masses: Sequence[float], theta: float
) -> tuple[float, float, float]:
    masses = _checked_overlap_masses(coefficient_masses)
    if (
        isinstance(theta, bool)
        or not isinstance(theta, (int, float))
        or not math.isfinite(theta)
    ):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_theta_invalid")
    log_terms = tuple(math.log(mass) + theta * overlap for overlap, mass in enumerate(masses))
    offset = max(log_terms)
    scaled_terms = tuple(math.exp(value - offset) for value in log_terms)
    scaled_partition = math.fsum(scaled_terms)
    expected = (
        math.fsum(overlap * value for overlap, value in enumerate(scaled_terms))
        / scaled_partition
    )
    variance = (
        math.fsum(
            (overlap - expected) ** 2 * value
            for overlap, value in enumerate(scaled_terms)
        )
        / scaled_partition
    )
    log_partition = offset + math.log(scaled_partition)
    if (
        not math.isfinite(log_partition)
        or not math.isfinite(expected)
        or expected < 0.0
        or expected > LEGAL_SELECTION_COUNT
        or not math.isfinite(variance)
        or variance <= 0.0
    ):
        raise LegalFixedCardinalityError("legal_fixed_cardinality_theta_moments_invalid")
    return expected, variance, log_partition


__all__ = [
    "LEGAL_BALL_COUNT",
    "LEGAL_SELECTION_COUNT",
    "LEGAL_STATE_COUNT",
    "MAXIMUM_ENTROPY_INTERIOR_FLOOR",
    "MAXIMUM_ENTROPY_LINE_SEARCH_STEPS",
    "MAXIMUM_ENTROPY_MAX_ITERATIONS",
    "MAXIMUM_ENTROPY_RESIDUAL_TOLERANCE",
    "MAXIMUM_ENTROPY_SUM_TOLERANCE",
    "OVERLAP_THETA_MAX_ABS_BRACKET",
    "OVERLAP_THETA_MAX_ITERATIONS",
    "OVERLAP_THETA_SCORE_TOLERANCE",
    "AffineResidualEtaSolution",
    "FixedCardinalityMaximumEntropySolution",
    "IS4Projection",
    "LegalFixedCardinalityError",
    "OverlapThetaSolution",
    "OverlapTiltEvaluation",
    "elementary_symmetric",
    "elementary_symmetric_degree_five",
    "evaluate_overlap_tilt",
    "fixed_cardinality_marginals",
    "legal_state_log_probability",
    "legal_state_probability",
    "legal_states",
    "overlap_coefficient_masses",
    "project_registered_is4_feature",
    "registered_is4_residual_value",
    "solve_affine_residual_eta",
    "solve_fixed_cardinality_maximum_entropy",
    "solve_overlap_theta",
]
