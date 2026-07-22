from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from math import isfinite
from numbers import Integral, Real
from typing import Any

from dehps.input_contracts.candidate_abi import (
    CandidateContractViolation,
    CandidateUniverseManifest,
    candidate_rank,
    validate_candidate_numbers,
)


PORTFOLIO_AUDIT_PROTOCOL = "candidate_portfolio_audit.v1"
PORTFOLIO_METRIC_PROTOCOL = "candidate_portfolio_metrics.v1"
PORTFOLIO_NULL_PROTOCOL = "candidate_portfolio_nulls.v1"
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
