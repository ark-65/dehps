from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from itertools import combinations
from math import comb, exp, log, sqrt
from platform import python_version
import random
from statistics import mean
from typing import Any

from dehps.contracts import canonical_digest
from dehps.portfolio.artifact import PortfolioAuditArtifact
from dehps.portfolio.models import (
    NullModelConfig,
    PORTFOLIO_METRIC_PROTOCOL,
    PORTFOLIO_NULL_PROTOCOL,
    SSQ_RED_UNIVERSE,
    ScoredCandidate,
    normalize_candidates,
    normalize_source,
    reject,
)
from dehps.source_version import resolve_git_commit


_STANDARDIZED_METRICS = (
    "average_pair_overlap",
    "maximum_number_exposure_rate",
    "number_hhi",
    "normalized_number_entropy",
    "unique_pair_legal_coverage",
    "maximum_pair_concentration",
    "unique_triple_legal_coverage",
    "maximum_triple_concentration",
    "ess_red3_plus",
    "ess_red4_plus",
)


def _is_lowercase_hex(value: object, lengths: tuple[int, ...]) -> bool:
    return (
        isinstance(value, str)
        and len(value) in lengths
        and all(character in "0123456789abcdef" for character in value)
    )


def _issue_less_than(left: object, right: object) -> bool:
    left_text = str(left or "")
    right_text = str(right or "")
    if not left_text or not right_text:
        return False
    try:
        return int(left_text) < int(right_text)
    except ValueError:
        return left_text < right_text


def _quantile(values: Sequence[float | int], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _sample_sd(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    center = mean(values)
    return sqrt(sum((value - center) ** 2 for value in values) / (len(values) - 1))


def _rounded(value: float, digits: int = 10) -> float:
    return round(float(value), digits)


def _hit_probability(threshold: int) -> float:
    return sum(
        comb(SSQ_RED_UNIVERSE.pick_count, matched)
        * comb(
            SSQ_RED_UNIVERSE.domain_size - SSQ_RED_UNIVERSE.pick_count,
            SSQ_RED_UNIVERSE.pick_count - matched,
        )
        for matched in range(threshold, SSQ_RED_UNIVERSE.pick_count + 1)
    ) / SSQ_RED_UNIVERSE.cardinality


def _joint_hit_probability(ticket_overlap: int, threshold: int) -> float:
    shared = ticket_overlap
    exclusive = SSQ_RED_UNIVERSE.pick_count - shared
    outside = SSQ_RED_UNIVERSE.domain_size - (2 * SSQ_RED_UNIVERSE.pick_count - shared)
    total = 0
    for selected_shared in range(shared + 1):
        for selected_left in range(exclusive + 1):
            for selected_right in range(exclusive + 1):
                selected_outside = (
                    SSQ_RED_UNIVERSE.pick_count
                    - selected_shared
                    - selected_left
                    - selected_right
                )
                if not 0 <= selected_outside <= outside:
                    continue
                if selected_shared + selected_left < threshold:
                    continue
                if selected_shared + selected_right < threshold:
                    continue
                total += (
                    comb(shared, selected_shared)
                    * comb(exclusive, selected_left)
                    * comb(exclusive, selected_right)
                    * comb(outside, selected_outside)
                )
    return total / SSQ_RED_UNIVERSE.cardinality


def _indicator_correlations(threshold: int) -> dict[int, float]:
    probability = _hit_probability(threshold)
    variance = probability * (1.0 - probability)
    return {
        overlap: (_joint_hit_probability(overlap, threshold) - probability**2) / variance
        for overlap in range(SSQ_RED_UNIVERSE.pick_count + 1)
    }


_RED3_CORRELATIONS = _indicator_correlations(3)
_RED4_CORRELATIONS = _indicator_correlations(4)


def _effective_sample_size(
    overlaps: Sequence[int],
    *,
    budget: int,
    threshold: int,
) -> dict[str, Any]:
    correlations = _RED3_CORRELATIONS if threshold == 3 else _RED4_CORRELATIONS
    average_correlation = mean(correlations[value] for value in overlaps) if overlaps else 0.0
    denominator = 1.0 + (budget - 1) * average_correlation
    if denominator <= 0.0:
        reject(
            "portfolio_ess_non_positive_variance",
            "effective sample size denominator must be positive",
            threshold=threshold,
            denominator=denominator,
        )
    return {
        "event": f"red{threshold}_plus",
        "definition": "variance_equivalent_count_under_uniform_legal_draw_null",
        "formula": "B/(1+(B-1)*mean_pair_indicator_correlation)",
        "null_hit_probability_per_ticket": _rounded(_hit_probability(threshold), 12),
        "mean_pair_indicator_correlation": _rounded(average_correlation, 12),
        "effective_sample_size": _rounded(budget / denominator),
    }


def _core_summary(
    counts: Counter[tuple[int, ...]],
    *,
    budget: int,
    core_size: int,
) -> dict[str, Any]:
    maximum = max(counts.values(), default=0)
    tied = [list(core) for core, count in sorted(counts.items()) if count == maximum]
    unique_count = len(counts)
    legal_count = comb(SSQ_RED_UNIVERSE.domain_size, core_size)
    attainable = min(legal_count, budget * comb(SSQ_RED_UNIVERSE.pick_count, core_size))
    return {
        "unique_count": unique_count,
        "legal_universe_count": legal_count,
        "legal_coverage": _rounded(unique_count / legal_count),
        "attainable_budget_count": attainable,
        "attainable_budget_coverage": _rounded(unique_count / attainable) if attainable else 0.0,
        "maximum_count": maximum,
        "maximum_concentration": _rounded(maximum / budget),
        "maximum_cores": tied,
    }


def calculate_portfolio_metrics(
    red_number_rows: Sequence[tuple[int, ...]],
    *,
    scores: Sequence[float] | None = None,
) -> dict[str, Any]:
    rows = tuple(red_number_rows)
    budget = len(rows)
    if budget < 1:
        reject("portfolio_metrics_rows_missing", "at least one candidate is required")
    masks = [sum(1 << (number - 1) for number in row) for row in rows]
    overlaps = [
        (left & right).bit_count()
        for left, right in combinations(masks, 2)
    ]
    overlap_counts = Counter(overlaps)
    number_counts = Counter(number for row in rows for number in row)
    pair_counts = Counter(pair for row in rows for pair in combinations(row, 2))
    triple_counts = Counter(triple for row in rows for triple in combinations(row, 3))
    total_slots = budget * SSQ_RED_UNIVERSE.pick_count
    exposure_probabilities = [
        number_counts[number] / total_slots
        for number in range(1, SSQ_RED_UNIVERSE.domain_size + 1)
    ]
    entropy = -sum(value * log(value) for value in exposure_probabilities if value > 0.0)
    max_number_count = max(number_counts.values())
    maximum_numbers = [
        number
        for number in range(1, SSQ_RED_UNIVERSE.domain_size + 1)
        if number_counts[number] == max_number_count
    ]
    score_payload: dict[str, Any] = {"available": False}
    if scores is not None:
        if len(scores) != budget:
            reject("portfolio_score_count_mismatch", "scores must match candidate count")
        score_values = [float(score) for score in scores]
        score_payload = {
            "available": True,
            "minimum": _rounded(min(score_values)),
            "p05": _rounded(_quantile(score_values, 0.05)),
            "p50": _rounded(_quantile(score_values, 0.50)),
            "p95": _rounded(_quantile(score_values, 0.95)),
            "maximum": _rounded(max(score_values)),
            "mean": _rounded(mean(score_values)),
        }
    red3_ess = _effective_sample_size(overlaps, budget=budget, threshold=3)
    red4_ess = _effective_sample_size(overlaps, budget=budget, threshold=4)
    return {
        "metric_protocol": PORTFOLIO_METRIC_PROTOCOL,
        "candidate_count": budget,
        "unique_candidate_count": len(set(rows)),
        "duplicate_candidate_count": budget - len(set(rows)),
        "number_exposure": {
            "occurrences": [
                {
                    "number": number,
                    "count": number_counts[number],
                    "per_ticket_rate": _rounded(number_counts[number] / budget),
                    "slot_share": _rounded(number_counts[number] / total_slots),
                }
                for number in range(1, SSQ_RED_UNIVERSE.domain_size + 1)
            ],
            "maximum_count": max_number_count,
            "maximum_per_ticket_rate": _rounded(max_number_count / budget),
            "maximum_numbers": maximum_numbers,
            "hhi": _rounded(sum(value**2 for value in exposure_probabilities), 12),
            "normalized_entropy": _rounded(entropy / log(SSQ_RED_UNIVERSE.domain_size), 12),
            "effective_exposed_number_count": _rounded(exp(entropy)),
        },
        "pairwise_overlap": {
            "pair_count": len(overlaps),
            "histogram": {
                str(overlap): overlap_counts[overlap]
                for overlap in range(SSQ_RED_UNIVERSE.pick_count + 1)
            },
            "mean": _rounded(mean(overlaps)) if overlaps else 0.0,
            "p50": _rounded(_quantile(overlaps, 0.50)) if overlaps else 0.0,
            "p90": _rounded(_quantile(overlaps, 0.90)) if overlaps else 0.0,
            "maximum": max(overlaps, default=0),
        },
        "pair_coverage": _core_summary(pair_counts, budget=budget, core_size=2),
        "triple_coverage": _core_summary(triple_counts, budget=budget, core_size=3),
        "effective_sample_size": {
            "red3_plus": red3_ess,
            "red4_plus": red4_ess,
        },
        "score": score_payload,
    }


def _comparison_values(metrics: Mapping[str, Any]) -> dict[str, float]:
    exposure = metrics["number_exposure"]
    overlap = metrics["pairwise_overlap"]
    pairs = metrics["pair_coverage"]
    triples = metrics["triple_coverage"]
    ess = metrics["effective_sample_size"]
    return {
        "average_pair_overlap": float(overlap["mean"]),
        "maximum_number_exposure_rate": float(exposure["maximum_per_ticket_rate"]),
        "number_hhi": float(exposure["hhi"]),
        "normalized_number_entropy": float(exposure["normalized_entropy"]),
        "unique_pair_legal_coverage": float(pairs["legal_coverage"]),
        "maximum_pair_concentration": float(pairs["maximum_concentration"]),
        "unique_triple_legal_coverage": float(triples["legal_coverage"]),
        "maximum_triple_concentration": float(triples["maximum_concentration"]),
        "ess_red3_plus": float(ess["red3_plus"]["effective_sample_size"]),
        "ess_red4_plus": float(ess["red4_plus"]["effective_sample_size"]),
    }


def _derive_seed(master_seed: int, *, scope: Mapping[str, Any]) -> tuple[int, str]:
    digest = canonical_digest(
        {"master_seed": master_seed, "scope": dict(scope)},
        domain="dehps.candidate-portfolio-derived-seed.v1",
    )
    return int(digest[:16], 16), digest


def _random_legal_portfolio(rng: random.Random, *, budget: int) -> tuple[tuple[int, ...], ...]:
    seen: set[tuple[int, ...]] = set()
    rows: list[tuple[int, ...]] = []
    domain = range(1, SSQ_RED_UNIVERSE.domain_size + 1)
    while len(rows) < budget:
        candidate = tuple(sorted(rng.sample(domain, SSQ_RED_UNIVERSE.pick_count)))
        if candidate not in seen:
            seen.add(candidate)
            rows.append(candidate)
    return tuple(rows)


def _summarize_null_samples(
    samples: Mapping[str, Sequence[float]],
    *,
    observed: Mapping[str, float],
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in _STANDARDIZED_METRICS:
        values = [float(value) for value in samples[key]]
        center = mean(values)
        deviation = _sample_sd(values)
        summary[key] = {
            "mean": _rounded(center, 12),
            "sample_sd": _rounded(deviation, 12),
            "p05": _rounded(_quantile(values, 0.05), 12),
            "p50": _rounded(_quantile(values, 0.50), 12),
            "p95": _rounded(_quantile(values, 0.95), 12),
            "observed": _rounded(observed[key], 12),
            "standardized_deviation": (
                _rounded((observed[key] - center) / deviation, 8)
                if deviation > 0.0
                else None
            ),
            "zero_variance": deviation == 0.0,
        }
    return summary


def _run_null(
    *,
    null_key: str,
    replicates: int,
    budget: int,
    master_seed: int,
    observed: Mapping[str, float],
    pool: Sequence[ScoredCandidate] | None = None,
    pool_digest: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    scope: dict[str, Any] = {
        "null_key": null_key,
        "budget": budget,
        "replicates": replicates,
    }
    if pool_digest is not None:
        scope["candidate_pool_digest"] = pool_digest
    derived_seed, seed_digest = _derive_seed(master_seed, scope=scope)
    rng = random.Random(derived_seed)
    samples = {key: [] for key in _STANDARDIZED_METRICS}
    score_means: list[float] = []
    for _replicate in range(replicates):
        if null_key == "uniform_legal_same_budget":
            rows = _random_legal_portfolio(rng, budget=budget)
            selected_scores = None
        elif null_key == "random_from_candidate_pool":
            if pool is None or len(pool) < budget:
                reject(
                    "portfolio_null_pool_too_small",
                    "candidate pool must contain at least budget rows",
                    pool_size=0 if pool is None else len(pool),
                    budget=budget,
                )
            selected = rng.sample(tuple(pool), budget)
            rows = tuple(candidate.red_numbers for candidate in selected)
            selected_scores = tuple(candidate.score for candidate in selected)
        else:  # pragma: no cover - private call invariant
            raise AssertionError(f"unsupported null model: {null_key}")
        sample_metrics = calculate_portfolio_metrics(rows, scores=selected_scores)
        values = _comparison_values(sample_metrics)
        for key in _STANDARDIZED_METRICS:
            samples[key].append(values[key])
        if selected_scores is not None:
            score_means.append(float(sample_metrics["score"]["mean"]))
    payload = {
        "protocol": PORTFOLIO_NULL_PROTOCOL,
        "null_key": null_key,
        "sample_space": (
            "uniform_distinct_portfolios_from_candidate.v1.0.0_C(33,6)"
            if null_key == "uniform_legal_same_budget"
            else "uniform_without_replacement_from_sealed_candidate_pool"
        ),
        "budget": budget,
        "replicates": replicates,
        "metrics": _summarize_null_samples(samples, observed=observed),
    }
    if score_means:
        center = mean(score_means)
        deviation = _sample_sd(score_means)
        payload["mean_score_distribution"] = {
            "mean": _rounded(center, 12),
            "sample_sd": _rounded(deviation, 12),
            "p05": _rounded(_quantile(score_means, 0.05), 12),
            "p50": _rounded(_quantile(score_means, 0.50), 12),
            "p95": _rounded(_quantile(score_means, 0.95), 12),
        }
    seed_manifest = {
        "null_key": null_key,
        "master_seed": master_seed,
        "derived_seed": derived_seed,
        "derivation_digest": seed_digest,
        "rng_algorithm": "python.random.MT19937",
        "python_version": python_version(),
        "replicates": replicates,
    }
    return payload, seed_manifest


def _candidate_digest(candidates: Sequence[ScoredCandidate], *, domain: str) -> str:
    return canonical_digest(
        [candidate.as_dict() for candidate in candidates],
        domain=domain,
    )


def audit_candidate_portfolio(
    candidates: Sequence[ScoredCandidate],
    *,
    candidate_pool: Sequence[ScoredCandidate] | None = None,
    source: Mapping[str, Any] | None = None,
    null_config: NullModelConfig | None = None,
    generated_at: str | None = None,
    code_commit: str | None = None,
) -> PortfolioAuditArtifact:
    portfolio = normalize_candidates(candidates, field="candidates")
    pool = normalize_candidates(
        portfolio if candidate_pool is None else candidate_pool,
        field="candidate_pool",
    )
    normalized_source = normalize_source(source)
    as_of_issue = normalized_source.get("as_of_issue")
    target_issue = normalized_source.get("target_issue")
    if as_of_issue and target_issue and not _issue_less_than(as_of_issue, target_issue):
        reject(
            "portfolio_history_cutoff_leakage",
            "as_of_issue must be earlier than target_issue",
            as_of_issue=as_of_issue,
            target_issue=target_issue,
        )
    if normalized_source.get("ranking_contract") == "strict_v1":
        for left, right in zip(pool, pool[1:]):
            if left.score < right.score or (
                left.score == right.score and left.lex_id > right.lex_id
            ):
                reject(
                    "portfolio_strict_ranking_order_mismatch",
                    "strict_v1 pool must order by score descending then lex_id ascending",
                    left_rank=left.source_rank,
                    right_rank=right.source_rank,
                )
    pool_by_id = {candidate.lex_id: candidate for candidate in pool}
    for candidate in portfolio:
        pool_candidate = pool_by_id.get(candidate.lex_id)
        if pool_candidate is None:
            reject(
                "portfolio_candidate_outside_pool",
                "selected portfolio must be a subset of the candidate pool",
                lex_id=candidate.lex_id,
            )
        if pool_candidate != candidate:
            reject(
                "portfolio_candidate_pool_record_mismatch",
                "portfolio row differs from its sealed candidate-pool row",
                lex_id=candidate.lex_id,
            )
    config = null_config or NullModelConfig()
    portfolio_digest = _candidate_digest(
        portfolio,
        domain="dehps.candidate-portfolio.selected.v1",
    )
    pool_digest = _candidate_digest(
        pool,
        domain="dehps.candidate-portfolio.pool.v1",
    )
    metrics = calculate_portfolio_metrics(
        [candidate.red_numbers for candidate in portfolio],
        scores=[candidate.score for candidate in portfolio],
    )
    score_topk = tuple(sorted(pool, key=lambda item: (-item.score, item.lex_id)))[: len(portfolio)]
    selected_mean_score = mean(candidate.score for candidate in portfolio)
    topk_mean_score = mean(candidate.score for candidate in score_topk)
    metrics["score"]["score_topk_mean"] = _rounded(topk_mean_score)
    metrics["score"]["mean_difference_vs_score_topk"] = _rounded(
        selected_mean_score - topk_mean_score
    )
    metrics["score"]["retention_ratio_vs_score_topk"] = (
        _rounded(selected_mean_score / topk_mean_score)
        if topk_mean_score != 0.0
        else None
    )
    observed = _comparison_values(metrics)
    uniform_null, uniform_seed = _run_null(
        null_key="uniform_legal_same_budget",
        replicates=config.uniform_legal_replicates,
        budget=len(portfolio),
        master_seed=config.master_seed,
        observed=observed,
    )
    pool_null, pool_seed = _run_null(
        null_key="random_from_candidate_pool",
        replicates=config.random_from_pool_replicates,
        budget=len(portfolio),
        master_seed=config.master_seed,
        observed=observed,
        pool=pool,
        pool_digest=pool_digest,
    )
    resolved_code_commit = code_commit or resolve_git_commit()
    provenance_gaps: list[str] = []
    if not _is_lowercase_hex(normalized_source.get("history_digest"), (64,)):
        provenance_gaps.append("history_digest")
    if not _is_lowercase_hex(normalized_source.get("score_config_digest"), (64,)):
        provenance_gaps.append("score_config_digest")
    for field in ("scoring_contract", "ranking_contract"):
        if not isinstance(normalized_source.get(field), str) or not normalized_source[field].strip():
            provenance_gaps.append(field)
    if not _is_lowercase_hex(normalized_source.get("source_code_commit"), (40, 64)):
        provenance_gaps.append("source_code_commit")
    if not _is_lowercase_hex(resolved_code_commit, (40, 64)):
        provenance_gaps.append("audit_code_commit")
    null_config_digest = canonical_digest(
        config.as_dict(),
        domain="dehps.candidate-portfolio-null-config.v1",
    )
    return PortfolioAuditArtifact.build(
        source=normalized_source,
        candidate_count=len(portfolio),
        candidate_pool_count=len(pool),
        portfolio_digest=portfolio_digest,
        candidate_pool_digest=pool_digest,
        metrics=metrics,
        null_comparisons={
            "uniform_legal_same_budget": uniform_null,
            "random_from_candidate_pool": pool_null,
        },
        null_config=config.as_dict(),
        null_config_digest=null_config_digest,
        seed_manifest={
            "protocol": "candidate_portfolio_seed_manifest.v1",
            "master_seed": config.master_seed,
            "nulls": [uniform_seed, pool_seed],
        },
        provenance_gaps=provenance_gaps,
        code_commit=resolved_code_commit,
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
