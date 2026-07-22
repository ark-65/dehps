from __future__ import annotations

from itertools import combinations
from math import comb, isfinite
from numbers import Real

from dehps.portfolio.models import (
    SSQ_RED_UNIVERSE,
    PortfolioRequest,
    PortfolioSelection,
    ScoredCandidate,
    build_portfolio_selection,
    reject,
    thaw_json,
)


_COEFFICIENTS = ("alpha", "lambda", "nu", "mu2", "mu3")


def _validated_coefficients(request: PortfolioRequest) -> dict[str, float]:
    config = thaw_json(request.selector_config)
    if set(config) != set(_COEFFICIENTS):
        reject(
            "portfolio_greedy_config_fields_invalid",
            "greedy_score_diversity requires all five coefficients and no defaults",
            required=list(_COEFFICIENTS),
        )
    coefficients: dict[str, float] = {}
    for field in _COEFFICIENTS:
        value = config[field]
        if (
            not isinstance(value, Real)
            or isinstance(value, bool)
            or not isfinite(float(value))
            or float(value) < 0.0
        ):
            reject(
                "portfolio_greedy_coefficient_invalid",
                "greedy coefficients must be finite and non-negative",
                field=field,
            )
        coefficients[field] = float(value)
    if not any(value > 0.0 for value in coefficients.values()):
        reject(
            "portfolio_greedy_coefficients_degenerate",
            "at least one greedy coefficient must be positive",
        )
    return coefficients


def _rank_quality(candidate: ScoredCandidate, pool_size: int) -> float:
    if pool_size == 1:
        return 1.0
    return (pool_size - candidate.source_rank) / (pool_size - 1)


class GreedyScoreDiversitySelector:
    key = "greedy_score_diversity"

    def select(self, request: PortfolioRequest) -> PortfolioSelection:
        if request.selector_key != self.key:
            reject("portfolio_selector_backend_mismatch", "request key does not match backend")
        coefficients = _validated_coefficients(request)
        budget = request.budget
        redundancy_denominator = comb(budget, 2) if budget > 1 else 1
        exposure_denominator = (6 * budget) ** 2 * (1.0 - 1.0 / 33.0)
        pair_denominator = min(comb(33, 2), budget * comb(6, 2))
        triple_denominator = min(comb(33, 3), budget * comb(6, 3))
        selected: list[ScoredCandidate] = []
        selected_ids: set[int] = set()
        selected_masks: list[int] = []
        number_counts = [0] * (SSQ_RED_UNIVERSE.domain_size + 1)
        covered_pairs: set[tuple[int, int]] = set()
        covered_triples: set[tuple[int, int, int]] = set()
        marginal_trace: list[float] = []

        for _position in range(budget):
            best_candidate: ScoredCandidate | None = None
            best_marginal = float("-inf")
            best_quality = float("-inf")
            for candidate in request.candidates:
                if candidate.lex_id in selected_ids:
                    continue
                quality = _rank_quality(candidate, len(request.candidates))
                mask = sum(1 << (number - 1) for number in candidate.red_numbers)
                pair_redundancy = sum(
                    comb((mask & selected_mask).bit_count(), 2)
                    for selected_mask in selected_masks
                )
                exposure_increment = sum(
                    2 * number_counts[number] + 1
                    for number in candidate.red_numbers
                )
                new_pair_count = sum(
                    pair not in covered_pairs
                    for pair in combinations(candidate.red_numbers, 2)
                )
                new_triple_count = sum(
                    triple not in covered_triples
                    for triple in combinations(candidate.red_numbers, 3)
                )
                marginal = (
                    coefficients["alpha"] * quality / budget
                    - coefficients["lambda"]
                    * (pair_redundancy / 15.0)
                    / redundancy_denominator
                    - coefficients["nu"] * exposure_increment / exposure_denominator
                    + coefficients["mu2"] * new_pair_count / pair_denominator
                    + coefficients["mu3"] * new_triple_count / triple_denominator
                )
                if (
                    marginal > best_marginal
                    or (
                        marginal == best_marginal
                        and (
                            quality > best_quality
                            or (
                                quality == best_quality
                                and best_candidate is not None
                                and candidate.lex_id < best_candidate.lex_id
                            )
                        )
                    )
                ):
                    best_candidate = candidate
                    best_marginal = marginal
                    best_quality = quality
            if best_candidate is None:  # pragma: no cover - request budget invariant
                reject("portfolio_greedy_selection_failed", "greedy selector exhausted its pool")
            selected.append(best_candidate)
            selected_ids.add(best_candidate.lex_id)
            selected_masks.append(
                sum(1 << (number - 1) for number in best_candidate.red_numbers)
            )
            for number in best_candidate.red_numbers:
                number_counts[number] += 1
            covered_pairs.update(combinations(best_candidate.red_numbers, 2))
            covered_triples.update(combinations(best_candidate.red_numbers, 3))
            marginal_trace.append(best_marginal)

        return build_portfolio_selection(
            request,
            selected,
            provenance={
                "backend": self.key,
                "algorithm": "exact_marginal_set_utility_v1",
                "utility_formula": "alpha*Q-lambda*R-nu*E+mu2*C2+mu3*C3",
                "coefficients": coefficients,
                "marginal_utility_trace": marginal_trace,
                "tie_break": "higher_rank_quality_then_lower_lex_id",
                "stochastic": False,
                "production_integration": False,
            },
        )
