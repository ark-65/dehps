from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import islice
from typing import Protocol

import numpy as np

from dehps.domain.combination import iter_ssq_red_combinations
from dehps.experiments.ranking_disagreement.models import (
    FROZEN_RANKER_KEYS,
    LegalUniverse,
    DrawRecord,
    RankerOutput,
    RANKER_VERSION,
    array_hash,
    normalize_ranker_key,
    stable_hash,
)


@dataclass(frozen=True)
class RankingContext:
    as_of_issue: str
    history: tuple[DrawRecord, ...]
    legal_universe: LegalUniverse
    history_fingerprint: str


class RankerAdapter(Protocol):
    key: str
    version: str
    config_hash: str

    def rank(self, context: RankingContext) -> RankerOutput:
        ...


class VectorizedRankerAdapter:
    def __init__(self, key: str, config: dict[str, object] | None = None) -> None:
        self.key = normalize_ranker_key(key)
        self.version = f"{RANKER_VERSION}:{self.key}"
        self.config = {"rank_direction": "descending_score", "tie_break": "combination_id", **(config or {})}
        self.config_hash = stable_hash(self.config)

    def rank(self, context: RankingContext) -> RankerOutput:
        if not context.history:
            raise ValueError(f"{self.key} requires at least one pre-target history draw")
        scores = self._scores(context)
        ranks = _ranks_from_scores(context.legal_universe.combination_ids, scores)
        return RankerOutput(
            ranker_key=self.key,
            version=self.version,
            config_hash=self.config_hash,
            as_of_issue=context.as_of_issue,
            history_fingerprint=context.history_fingerprint,
            legal_universe_fingerprint=context.legal_universe.fingerprint,
            combination_ids=context.legal_universe.combination_ids.copy(),
            ranks=ranks,
            score_fingerprint=array_hash(scores),
        )

    def _scores(self, context: RankingContext) -> np.ndarray:
        if self.key == "frequency_based":
            return _frequency_scores(context.history, context.legal_universe.combinations)
        if self.key == "omission_based":
            return _omission_scores(context.history, context.legal_universe.combinations)
        if self.key == "structural":
            return _structural_scores(context.legal_universe.combinations)
        raise AssertionError(f"unreachable ranker key: {self.key}")


def built_in_rankers() -> tuple[RankerAdapter, ...]:
    return tuple(VectorizedRankerAdapter(key) for key in FROZEN_RANKER_KEYS)


def get_ranker(key: str) -> RankerAdapter:
    normalized = normalize_ranker_key(key)
    return VectorizedRankerAdapter(normalized)


def build_legal_universe(*, limit: int | None = None) -> LegalUniverse:
    if limit is not None and limit < 1:
        raise ValueError("legal universe limit must be positive")
    source: Iterable[tuple[int, ...]] = iter_ssq_red_combinations()
    if limit is not None:
        source = islice(source, limit)
    flat = np.fromiter((number for combo in source for number in combo), dtype=np.int16)
    if flat.size == 0 or flat.size % 6 != 0:
        raise ValueError("failed to materialize the legal SSQ red-ball universe")
    combinations = flat.reshape((-1, 6))
    combination_ids = np.arange(1, combinations.shape[0] + 1, dtype=np.int32)
    fingerprint = stable_hash(
        {
            "schema": "ssq-red-legal-universe-v1",
            "combination_count": int(combinations.shape[0]),
            "first_combination": combinations[0].tolist(),
            "last_combination": combinations[-1].tolist(),
            "full_lexicographic_universe": limit is None,
            "combination_hash": array_hash(combinations),
        }
    )
    return LegalUniverse(
        combination_ids=combination_ids,
        combinations=combinations,
        fingerprint=fingerprint,
        full_lexicographic_universe=limit is None,
    )


def _ranks_from_scores(combination_ids: np.ndarray, scores: np.ndarray) -> np.ndarray:
    if scores.shape[0] != combination_ids.shape[0]:
        raise ValueError("score vector length does not match legal universe")
    if not np.all(np.isfinite(scores)):
        raise ValueError("ranker produced non-finite scores")
    order = np.lexsort((combination_ids, -scores))
    ranks = np.empty_like(combination_ids, dtype=np.int32)
    ranks[order] = np.arange(1, combination_ids.shape[0] + 1, dtype=np.int32)
    return ranks


def _frequency_scores(history: tuple[DrawRecord, ...], combinations: np.ndarray) -> np.ndarray:
    counts = np.zeros(34, dtype=np.float64)
    for draw in history:
        counts[np.asarray(draw.red_numbers, dtype=np.int16)] += 1.0
    denominator = max(1.0, float(len(history) * 6))
    rates = counts / denominator
    return rates[combinations].sum(axis=1)


def _omission_scores(history: tuple[DrawRecord, ...], combinations: np.ndarray) -> np.ndarray:
    last_seen = np.full(34, -1, dtype=np.int32)
    for index, draw in enumerate(history):
        last_seen[np.asarray(draw.red_numbers, dtype=np.int16)] = index
    train_draws = len(history)
    omission = np.ones(34, dtype=np.float64)
    seen = last_seen >= 0
    omission[seen] = (train_draws - 1 - last_seen[seen]) / max(1.0, float(train_draws))
    return omission[combinations].sum(axis=1) / 6.0


def _structural_scores(combinations: np.ndarray) -> np.ndarray:
    # A frozen transparent structural plausibility score. It intentionally does not
    # inspect history or target outcomes.
    sums = combinations.sum(axis=1).astype(np.float64)
    spans = (combinations[:, -1] - combinations[:, 0]).astype(np.float64)
    odd_counts = (combinations % 2 == 1).sum(axis=1).astype(np.float64)
    gaps = np.diff(combinations, axis=1)
    consecutive_pairs = (gaps == 1).sum(axis=1).astype(np.float64)
    zone1 = (combinations <= 11).sum(axis=1).astype(np.float64)
    zone2 = ((combinations >= 12) & (combinations <= 22)).sum(axis=1).astype(np.float64)
    zone3 = (combinations >= 23).sum(axis=1).astype(np.float64)
    zone_balance = 1.0 - (np.abs(zone1 - 2) + np.abs(zone2 - 2) + np.abs(zone3 - 2)) / 12.0
    sum_score = 1.0 - np.abs(sums - 102.0) / 102.0
    span_score = 1.0 - np.abs(spans - 25.0) / 32.0
    parity_score = 1.0 - np.abs(odd_counts - 3.0) / 6.0
    consecutive_score = 1.0 - np.minimum(consecutive_pairs, 4.0) / 5.0
    return (
        0.30 * sum_score
        + 0.25 * span_score
        + 0.20 * parity_score
        + 0.20 * zone_balance
        + 0.05 * consecutive_score
    )
