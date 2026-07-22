from __future__ import annotations

from math import floor

from dehps.portfolio.models import (
    PortfolioRequest,
    PortfolioSelection,
    ScoredCandidate,
    build_portfolio_selection,
    reject,
    thaw_json,
)


_CONFIG_FIELDS = {
    "cluster_count",
    "medoid_initialization",
    "quota_mode",
    "within_cluster_rule",
    "redistribution_rule",
    "max_iterations",
}


def _mask(candidate: ScoredCandidate) -> int:
    return sum(1 << (number - 1) for number in candidate.red_numbers)


def _jaccard_distance(left_mask: int, right_mask: int) -> float:
    overlap = (left_mask & right_mask).bit_count()
    return 1.0 - overlap / (12 - overlap)


def _validate_config(request: PortfolioRequest) -> dict[str, object]:
    config = thaw_json(request.selector_config)
    if set(config) != _CONFIG_FIELDS:
        reject(
            "portfolio_cluster_config_fields_invalid",
            "cluster_quota requires the exact v1 configuration fields",
            required=sorted(_CONFIG_FIELDS),
        )
    cluster_count = config["cluster_count"]
    max_iterations = config["max_iterations"]
    if (
        not isinstance(cluster_count, int)
        or isinstance(cluster_count, bool)
        or not 1 <= cluster_count <= len(request.candidates)
    ):
        reject("portfolio_cluster_count_invalid", "cluster_count is outside the pool")
    if (
        not isinstance(max_iterations, int)
        or isinstance(max_iterations, bool)
        or max_iterations < 1
    ):
        reject("portfolio_cluster_iterations_invalid", "max_iterations must be positive")
    expected = {
        "medoid_initialization": "score_first_farthest",
        "within_cluster_rule": "score_topk",
        "redistribution_rule": "largest_deficit_then_cluster_id",
    }
    for field, required in expected.items():
        if config[field] != required:
            reject(
                "portfolio_cluster_contract_invalid",
                f"{field} must use the declared deterministic v1 contract",
                field=field,
            )
    if config["quota_mode"] not in {"equal", "size_proportional"}:
        reject(
            "portfolio_cluster_quota_mode_invalid",
            "quota_mode must be equal or size_proportional",
        )
    return config


def _assign(
    candidates: tuple[ScoredCandidate, ...],
    masks: list[int],
    medoid_indices: list[int],
) -> list[list[int]]:
    clusters = [[] for _medoid in medoid_indices]
    for candidate_index, candidate_mask in enumerate(masks):
        cluster_index = min(
            range(len(medoid_indices)),
            key=lambda index: (
                _jaccard_distance(candidate_mask, masks[medoid_indices[index]]),
                -candidates[medoid_indices[index]].score,
                candidates[medoid_indices[index]].lex_id,
            ),
        )
        clusters[cluster_index].append(candidate_index)
    return clusters


def _initial_medoids(candidates: tuple[ScoredCandidate, ...], masks: list[int], count: int) -> list[int]:
    medoids = [0]
    while len(medoids) < count:
        medoid_set = set(medoids)
        next_index = max(
            (index for index in range(len(candidates)) if index not in medoid_set),
            key=lambda index: (
                min(
                    _jaccard_distance(masks[index], masks[medoid])
                    for medoid in medoids
                ),
                candidates[index].score,
                -candidates[index].lex_id,
            ),
        )
        medoids.append(next_index)
    return medoids


def _updated_medoid(
    cluster: list[int],
    *,
    candidates: tuple[ScoredCandidate, ...],
    masks: list[int],
) -> int:
    return min(
        cluster,
        key=lambda candidate_index: (
            sum(
                _jaccard_distance(masks[candidate_index], masks[other_index])
                for other_index in cluster
            ),
            -candidates[candidate_index].score,
            candidates[candidate_index].lex_id,
        ),
    )


def _allocate_quotas(
    cluster_sizes: list[int],
    *,
    budget: int,
    quota_mode: str,
) -> tuple[list[int], list[dict[str, int]]]:
    total = sum(cluster_sizes)
    if quota_mode == "equal":
        ideals = [budget / len(cluster_sizes)] * len(cluster_sizes)
    else:
        ideals = [budget * size / total for size in cluster_sizes]
    quotas = [min(size, floor(ideal)) for size, ideal in zip(cluster_sizes, ideals)]
    redistributions: list[dict[str, int]] = []
    while sum(quotas) < budget:
        available = [
            index
            for index, size in enumerate(cluster_sizes)
            if quotas[index] < size
        ]
        if not available:  # pragma: no cover - request budget invariant
            reject("portfolio_cluster_quota_exhausted", "cluster capacities cannot fill budget")
        chosen = max(
            available,
            key=lambda index: (ideals[index] - quotas[index], -index),
        )
        quotas[chosen] += 1
        redistributions.append({"cluster_id": chosen, "new_quota": quotas[chosen]})
    return quotas, redistributions


class ClusterQuotaSelector:
    key = "cluster_quota"

    def select(self, request: PortfolioRequest) -> PortfolioSelection:
        if request.selector_key != self.key:
            reject("portfolio_selector_backend_mismatch", "request key does not match backend")
        config = _validate_config(request)
        candidates = request.candidates
        masks = [_mask(candidate) for candidate in candidates]
        medoids = _initial_medoids(candidates, masks, int(config["cluster_count"]))
        converged = False
        iterations = 0
        for iteration in range(1, int(config["max_iterations"]) + 1):
            clusters = _assign(candidates, masks, medoids)
            updated = [
                _updated_medoid(cluster, candidates=candidates, masks=masks)
                for cluster in clusters
            ]
            iterations = iteration
            if updated == medoids:
                converged = True
                break
            medoids = updated
        clusters = _assign(candidates, masks, medoids)
        cluster_sizes = [len(cluster) for cluster in clusters]
        quotas, redistributions = _allocate_quotas(
            cluster_sizes,
            budget=request.budget,
            quota_mode=str(config["quota_mode"]),
        )
        quota_candidates: list[ScoredCandidate] = []
        for cluster, quota in zip(clusters, quotas):
            ranked = sorted(
                (candidates[index] for index in cluster),
                key=lambda candidate: (-candidate.score, candidate.lex_id),
            )
            quota_candidates.extend(ranked[:quota])
        choice_order = sorted(
            quota_candidates,
            key=lambda candidate: (-candidate.score, candidate.lex_id),
        )
        return build_portfolio_selection(
            request,
            choice_order,
            provenance={
                "backend": self.key,
                "algorithm": "deterministic_jaccard_k_medoids_quota_v1",
                "config": config,
                "medoid_lex_ids": [candidates[index].lex_id for index in medoids],
                "cluster_sizes": cluster_sizes,
                "quotas": quotas,
                "quota_redistributions": redistributions,
                "iterations": iterations,
                "converged": converged,
                "stochastic": False,
                "production_integration": False,
            },
        )
