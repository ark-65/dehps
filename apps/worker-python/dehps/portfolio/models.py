from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from math import isfinite
from numbers import Integral, Real
from platform import python_version
from types import MappingProxyType
from typing import Any

from dehps.contracts import canonical_digest
from dehps.input_contracts.candidate_abi import (
    CandidateContractViolation,
    CandidateUniverseManifest,
    candidate_rank,
    validate_candidate_numbers,
)
from dehps.source_version import resolve_git_commit


PORTFOLIO_AUDIT_PROTOCOL = "candidate_portfolio_audit.v1"
PORTFOLIO_METRIC_PROTOCOL = "candidate_portfolio_metrics.v1"
PORTFOLIO_NULL_PROTOCOL = "candidate_portfolio_nulls.v1"
PORTFOLIO_SELECTOR_PROTOCOL = "candidate_portfolio_selector.v1"
PORTFOLIO_SELECTOR_KEYS = frozenset(
    {
        "score_topk",
        "random_from_top_pool",
        "greedy_score_diversity",
        "cluster_quota",
    }
)
SSQ_RED_UNIVERSE = CandidateUniverseManifest(domain_size=33, pick_count=6)


class PortfolioAuditViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


def reject(code: str, message: str, **context: Any) -> None:
    raise PortfolioAuditViolation(code, message, **context)


@dataclass(frozen=True)
class ScoredCandidate:
    source_rank: int
    red_numbers: tuple[int, ...]
    score: float
    lex_id: int

    @classmethod
    def build(
        cls,
        *,
        source_rank: object,
        red_numbers: Sequence[object],
        score: object,
        lex_id: object | None = None,
    ) -> ScoredCandidate:
        if not isinstance(source_rank, Integral) or isinstance(source_rank, bool) or int(source_rank) < 1:
            reject(
                "invalid_portfolio_source_rank",
                "source_rank must be a positive integer",
                source_rank=source_rank,
            )
        try:
            canonical = validate_candidate_numbers(red_numbers, universe=SSQ_RED_UNIVERSE)
        except CandidateContractViolation as exc:
            raise PortfolioAuditViolation(
                "invalid_portfolio_candidate",
                "candidate violates the SSQ Candidate Contract",
                cause=exc.code,
                source_rank=int(source_rank),
            ) from exc
        if (
            not isinstance(score, (Real, Decimal))
            or isinstance(score, bool)
            or not isfinite(float(score))
        ):
            reject(
                "invalid_portfolio_score",
                "score must be a finite real number",
                source_rank=int(source_rank),
            )
        expected_lex_id = candidate_rank(canonical, universe=SSQ_RED_UNIVERSE)
        if lex_id is not None and (
            not isinstance(lex_id, Integral)
            or isinstance(lex_id, bool)
            or int(lex_id) != expected_lex_id
        ):
            reject(
                "portfolio_candidate_lex_id_mismatch",
                "lex_id does not match canonical candidate identity",
                source_rank=int(source_rank),
                expected_lex_id=expected_lex_id,
                actual_lex_id=lex_id,
            )
        return cls(
            source_rank=int(source_rank),
            red_numbers=canonical,
            score=float(score),
            lex_id=expected_lex_id,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_rank": self.source_rank,
            "lex_id": self.lex_id,
            "red_numbers": list(self.red_numbers),
            "score": self.score,
        }


@dataclass(frozen=True)
class NullModelConfig:
    master_seed: int = 20260722
    uniform_legal_replicates: int = 500
    random_from_pool_replicates: int = 500

    def __post_init__(self) -> None:
        if not isinstance(self.master_seed, int) or isinstance(self.master_seed, bool) or self.master_seed < 0:
            reject("invalid_portfolio_null_seed", "master_seed must be a non-negative integer")
        for field, value in (
            ("uniform_legal_replicates", self.uniform_legal_replicates),
            ("random_from_pool_replicates", self.random_from_pool_replicates),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 2:
                reject(
                    "invalid_portfolio_null_replicates",
                    f"{field} must be an integer of at least 2",
                    field=field,
                )

    def as_dict(self) -> dict[str, int]:
        return {
            "master_seed": self.master_seed,
            "uniform_legal_replicates": self.uniform_legal_replicates,
            "random_from_pool_replicates": self.random_from_pool_replicates,
        }


def normalize_candidates(
    values: Sequence[ScoredCandidate],
    *,
    field: str,
    require_rank_order: bool = True,
) -> tuple[ScoredCandidate, ...]:
    candidates = tuple(values)
    if not candidates:
        reject("portfolio_candidates_missing", f"{field} must contain at least one candidate")
    if any(not isinstance(candidate, ScoredCandidate) for candidate in candidates):
        reject("portfolio_candidate_type_invalid", f"{field} must contain ScoredCandidate rows")
    ranks = [candidate.source_rank for candidate in candidates]
    lex_ids = [candidate.lex_id for candidate in candidates]
    numbers = [candidate.red_numbers for candidate in candidates]
    if require_rank_order and any(left >= right for left, right in zip(ranks, ranks[1:])):
        reject(
            "portfolio_source_rank_order_invalid",
            f"{field} must be strictly increasing by source_rank",
        )
    if len(set(ranks)) != len(ranks):
        reject("portfolio_duplicate_source_rank", f"{field} contains duplicate source ranks")
    if len(set(lex_ids)) != len(lex_ids) or len(set(numbers)) != len(numbers):
        reject("portfolio_duplicate_candidate", f"{field} contains duplicate candidate identities")
    return candidates


def normalize_source(value: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(value or {})
    normalized: dict[str, Any] = {}
    for key, item in source.items():
        if not isinstance(key, str):
            reject("portfolio_source_key_invalid", "source keys must be strings")
        if item is None or isinstance(item, (str, int, float, bool)):
            normalized[key] = item
        elif isinstance(item, Mapping):
            normalized[key] = normalize_source(item)
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            normalized[key] = list(item)
        else:
            reject(
                "portfolio_source_value_invalid",
                "source contains a non-canonical value",
                field=key,
            )
    return normalized


def compute_candidate_pool_digest(candidates: Sequence[ScoredCandidate]) -> str:
    pool = normalize_candidates(candidates, field="candidate_pool")
    return canonical_digest(
        [candidate.as_dict() for candidate in pool],
        domain="dehps.candidate-portfolio.pool.v1",
    )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _freeze_json(value: Any, *, field: str) -> Any:
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in sorted(value.items()):
            if not isinstance(key, str):
                reject("portfolio_selector_mapping_key_invalid", f"{field} keys must be strings")
            frozen[key] = _freeze_json(item, field=f"{field}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(_freeze_json(item, field=field) for item in value)
    if isinstance(value, float) and not isfinite(value):
        reject("portfolio_selector_value_nonfinite", f"{field} contains a non-finite float")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    reject(
        "portfolio_selector_value_invalid",
        f"{field} contains a non-canonical value",
        value_type=type(value).__name__,
    )


def thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


@dataclass(frozen=True)
class PortfolioRequest:
    candidates: tuple[ScoredCandidate, ...]
    budget: int
    selector_key: str
    selector_config: Mapping[str, Any]
    candidate_pool_digest: str
    history_digest: str
    score_config_digest: str
    seed: int | None
    context: Mapping[str, Any]

    @classmethod
    def build(
        cls,
        *,
        candidates: Sequence[ScoredCandidate],
        budget: object,
        selector_key: object,
        selector_config: Mapping[str, Any] | None,
        candidate_pool_digest: object,
        history_digest: object,
        score_config_digest: object,
        seed: object | None,
        context: Mapping[str, Any],
    ) -> PortfolioRequest:
        pool = normalize_candidates(candidates, field="candidate_pool")
        if [candidate.source_rank for candidate in pool] != list(range(1, len(pool) + 1)):
            reject(
                "portfolio_selector_rank_sequence_invalid",
                "candidate pool must contain consecutive source ranks from one",
            )
        for left, right in zip(pool, pool[1:]):
            if left.score < right.score or (
                left.score == right.score and left.lex_id > right.lex_id
            ):
                reject(
                    "portfolio_selector_strict_ranking_mismatch",
                    "candidate pool must use strict_v1 score and lex_id order",
                )
        if (
            not isinstance(budget, Integral)
            or isinstance(budget, bool)
            or not 1 <= int(budget) <= len(pool)
        ):
            reject(
                "portfolio_selector_budget_invalid",
                "budget must be an integer within the candidate pool",
            )
        if not isinstance(selector_key, str) or selector_key not in PORTFOLIO_SELECTOR_KEYS:
            reject(
                "portfolio_selector_key_invalid",
                "selector_key is not a registered research backend",
                selector_key=selector_key,
            )
        expected_pool_digest = compute_candidate_pool_digest(pool)
        if candidate_pool_digest != expected_pool_digest:
            reject(
                "portfolio_selector_pool_digest_mismatch",
                "candidate_pool_digest does not match the sealed pool",
            )
        for field, value in (
            ("history_digest", history_digest),
            ("score_config_digest", score_config_digest),
        ):
            if not _is_digest(value):
                reject(
                    "portfolio_selector_provenance_digest_invalid",
                    f"{field} must be a lowercase sha256 digest",
                    field=field,
                )
        if seed is not None and (
            not isinstance(seed, Integral) or isinstance(seed, bool) or int(seed) < 0
        ):
            reject(
                "portfolio_selector_seed_invalid",
                "seed must be a non-negative integer when provided",
            )
        if not isinstance(context, Mapping):
            reject("portfolio_selector_context_invalid", "context must be an object")
        required_context = {"line_key", "as_of_issue", "target_issue", "replicate_id"}
        if set(context) != required_context:
            reject(
                "portfolio_selector_context_fields_invalid",
                "context must contain the exact v1 fields",
                required=sorted(required_context),
            )
        line_key = context["line_key"]
        as_of_issue = context["as_of_issue"]
        target_issue = context["target_issue"]
        replicate_id = context["replicate_id"]
        if not isinstance(line_key, str) or not line_key.strip():
            reject("portfolio_selector_line_key_invalid", "line_key must be non-empty")
        try:
            history_precedes_target = int(str(as_of_issue)) < int(str(target_issue))
        except ValueError:
            history_precedes_target = str(as_of_issue) < str(target_issue)
        if not str(as_of_issue) or not str(target_issue) or not history_precedes_target:
            reject(
                "portfolio_selector_history_cutoff_leakage",
                "as_of_issue must be earlier than target_issue",
            )
        if (
            not isinstance(replicate_id, Integral)
            or isinstance(replicate_id, bool)
            or int(replicate_id) < 0
        ):
            reject(
                "portfolio_selector_replicate_id_invalid",
                "replicate_id must be a non-negative integer",
            )
        if selector_config is None or not isinstance(selector_config, Mapping):
            reject("portfolio_selector_config_invalid", "selector_config must be an object")
        return cls(
            candidates=pool,
            budget=int(budget),
            selector_key=selector_key,
            selector_config=_freeze_json(selector_config, field="selector_config"),
            candidate_pool_digest=expected_pool_digest,
            history_digest=str(history_digest),
            score_config_digest=str(score_config_digest),
            seed=None if seed is None else int(seed),
            context=_freeze_json(context, field="context"),
        )

    @property
    def selector_config_digest(self) -> str:
        return canonical_digest(
            thaw_json(self.selector_config),
            domain="dehps.candidate-portfolio-selector-config.v1",
        )

    @property
    def request_digest(self) -> str:
        return canonical_digest(
            {
                "protocol": PORTFOLIO_SELECTOR_PROTOCOL,
                "budget": self.budget,
                "selector_key": self.selector_key,
                "selector_config_digest": self.selector_config_digest,
                "candidate_pool_digest": self.candidate_pool_digest,
                "history_digest": self.history_digest,
                "score_config_digest": self.score_config_digest,
                "seed": self.seed,
                "context": thaw_json(self.context),
            },
            domain="dehps.candidate-portfolio-selector-request.v1",
        )


@dataclass(frozen=True)
class PortfolioSelection:
    selected: tuple[ScoredCandidate, ...]
    selection_order_lex_ids: tuple[int, ...]
    selector_key: str
    selector_config_digest: str
    candidate_pool_digest: str
    portfolio_digest: str
    request_digest: str
    audit_metrics: Mapping[str, Any]
    provenance: Mapping[str, Any]

    @property
    def evidence_level(self) -> str:
        return "RESEARCH_ONLY"

    @property
    def automatic_promotion_allowed(self) -> bool:
        return False

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": PORTFOLIO_SELECTOR_PROTOCOL,
            "evidence_level": self.evidence_level,
            "automatic_promotion_allowed": self.automatic_promotion_allowed,
            "selector_key": self.selector_key,
            "selector_config_digest": self.selector_config_digest,
            "candidate_pool_digest": self.candidate_pool_digest,
            "portfolio_digest": self.portfolio_digest,
            "request_digest": self.request_digest,
            "selected": [candidate.as_dict() for candidate in self.selected],
            "selection_order_lex_ids": list(self.selection_order_lex_ids),
            "audit_metrics": thaw_json(self.audit_metrics),
            "provenance": thaw_json(self.provenance),
        }


def build_portfolio_selection(
    request: PortfolioRequest,
    choice_order: Sequence[ScoredCandidate],
    *,
    provenance: Mapping[str, Any],
) -> PortfolioSelection:
    chosen = tuple(choice_order)
    if len(chosen) != request.budget:
        reject(
            "portfolio_selector_output_budget_mismatch",
            "selector output must exactly match the requested budget",
        )
    pool_by_id = {candidate.lex_id: candidate for candidate in request.candidates}
    if len({candidate.lex_id for candidate in chosen}) != len(chosen):
        reject("portfolio_selector_output_duplicate", "selector output contains duplicates")
    for candidate in chosen:
        if pool_by_id.get(candidate.lex_id) != candidate:
            reject(
                "portfolio_selector_output_outside_pool",
                "selector output must be an exact subset of the sealed pool",
            )
    selected = tuple(sorted(chosen, key=lambda candidate: candidate.source_rank))
    from dehps.portfolio.audit import calculate_portfolio_metrics

    metrics = calculate_portfolio_metrics(
        [candidate.red_numbers for candidate in selected],
        scores=[candidate.score for candidate in selected],
    )
    score_topk = request.candidates[: request.budget]
    selected_mean = sum(candidate.score for candidate in selected) / request.budget
    topk_mean = sum(candidate.score for candidate in score_topk) / request.budget
    metrics["score"]["score_topk_mean"] = topk_mean
    metrics["score"]["mean_difference_vs_score_topk"] = selected_mean - topk_mean
    metrics["score"]["retention_ratio_vs_score_topk"] = (
        selected_mean / topk_mean if topk_mean != 0.0 else None
    )
    portfolio_digest_value = canonical_digest(
        [candidate.as_dict() for candidate in selected],
        domain="dehps.candidate-portfolio.selection.v1",
    )
    recorded_provenance = {
        "selector_protocol": PORTFOLIO_SELECTOR_PROTOCOL,
        "selector_code_commit": resolve_git_commit(),
        "python_version": python_version(),
        **dict(provenance),
    }
    return PortfolioSelection(
        selected=selected,
        selection_order_lex_ids=tuple(candidate.lex_id for candidate in chosen),
        selector_key=request.selector_key,
        selector_config_digest=request.selector_config_digest,
        candidate_pool_digest=request.candidate_pool_digest,
        portfolio_digest=portfolio_digest_value,
        request_digest=request.request_digest,
        audit_metrics=_freeze_json(metrics, field="audit_metrics"),
        provenance=_freeze_json(recorded_provenance, field="provenance"),
    )
