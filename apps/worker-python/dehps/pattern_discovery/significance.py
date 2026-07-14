from __future__ import annotations

from math import exp, isclose, lgamma, log, sqrt

from dehps.pattern_discovery.models import PatternCandidate, PatternSignificanceResult


def binomial_tail_p_value(observed: int, trials: int, probability: float, *, direction: str) -> float:
    if trials <= 0:
        return 1.0
    p = min(1.0, max(0.0, probability))
    if isclose(p, 0.0):
        if direction == "negative":
            return 1.0
        return 1.0 if observed <= 0 else 0.0
    if isclose(p, 1.0):
        if direction == "negative":
            return 1.0 if observed >= trials else 0.0
        return 1.0
    if direction == "negative":
        return _log_sum_exp_binomial(trials, p, range(0, observed + 1))
    return _log_sum_exp_binomial(trials, p, range(observed, trials + 1))


def _log_sum_exp_binomial(trials: int, probability: float, support: range) -> float:
    logs = [
        (
            lgamma(trials + 1)
            - lgamma(k + 1)
            - lgamma(trials - k + 1)
            + k * log(probability)
            + (trials - k) * log(1.0 - probability)
        )
        for k in support
    ]
    if not logs:
        return 0.0
    peak = max(logs)
    if peak == float("-inf"):
        return 0.0
    return min(1.0, max(0.0, exp(peak) * sum(exp(item - peak) for item in logs)))


def bootstrap_normal_ci(observed: float, trials: int, *, z: float = 1.96) -> tuple[float, float]:
    if trials <= 0:
        return (0.0, 0.0)
    rate = observed / trials
    stderr = sqrt(max(rate * (1.0 - rate), 0.0) / trials)
    return (max(0.0, rate - z * stderr), min(1.0, rate + z * stderr))


class PatternSignificanceReviewer:
    def review(
        self,
        candidate: PatternCandidate,
        *,
        multiplicity_count: int,
        multiplicity_complete: bool,
        sequential_search_count: int = 1,
        method: str = "binomial_exact_with_bootstrap_ci",
    ) -> PatternSignificanceResult:
        trials = max(1, int(candidate.metadata.get("sample_count") or len(candidate.source_artifacts) or 1))
        observed_count = max(0, min(trials, int(round(candidate.observed_support))))
        expected_count = max(0.0, float(candidate.expected_support))
        probability = min(1.0, max(0.0, expected_count / trials))
        direction = "positive" if observed_count >= expected_count else "negative"
        raw = binomial_tail_p_value(observed_count, trials, probability, direction=direction)
        family = min(1.0, raw * max(1, multiplicity_count))
        sequential = min(1.0, family * max(1, sequential_search_count))
        blockers: list[str] = []
        if not multiplicity_complete:
            blockers.append("incomplete_multiplicity_accounting")
        if not candidate.null_definition:
            blockers.append("missing_null_definition")
        if not candidate.failure_condition:
            blockers.append("missing_failure_condition")
        if "primary" not in candidate.null_definition:
            blockers.append("missing_primary_null")
        effect = 0.0 if trials == 0 else (observed_count - expected_count) / trials
        return PatternSignificanceResult(
            pattern_key=candidate.pattern_key,
            raw_p_value=float(raw),
            family_adjusted_p_value=float(family),
            sequential_adjusted_p_value=float(sequential),
            effect_size=float(effect),
            confidence_interval=bootstrap_normal_ci(float(observed_count), trials),
            expected_count=float(expected_count),
            observed_count=float(observed_count),
            multiplicity_count=max(1, int(multiplicity_count)),
            interpretable=not blockers,
            blocker_codes=tuple(blockers),
            direction=direction,
            method=method,
            nulls=dict(candidate.null_definition.get("matched") or {}),
        )
