from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from heapq import nlargest
import json
import multiprocessing as mp
import os
from multiprocessing.pool import Pool
from typing import Iterable, Literal

from dehps.domain.combination import iter_ssq_red_combinations
from dehps.features.red_ball_features import calculate_red_ball_features
from dehps.models.frequency_ranker import (
    FrequencyRankerConfig,
    FrequencyStats,
    _previous_consecutive_score,
    score_frequency_candidate,
    train_frequency_stats,
)
from dehps.scoring.strategy import score_numbers

_WORKER_UNIVERSE: list["RankedUniverseEntry"] = []
DEFAULT_WORKERS = 16


@dataclass(frozen=True)
class RankedUniverseEntry:
    numbers: tuple[int, ...]
    structural_score: float
    consecutive_pair_count: int
    odd_count: int
    zone_counts: tuple[int, int, int]


@dataclass(frozen=True)
class TargetRank:
    issue: str
    rank: int
    score: float
    hit_top_100: bool
    hit_top_1000: bool
    hit_top_10000: bool


@dataclass(frozen=True)
class WalkForwardResult:
    strategy_key: str
    as_of_issue: str
    history_fingerprint: str
    config_hash: str
    train_window: int
    train_mode: str
    eval_window: int
    top_n: int
    workers: int
    evaluated_draws: int
    top_100_hits: int
    top_1000_hits: int
    top_10000_hits: int
    zero_model_top_100_hits: int
    zero_model_top_1000_hits: int
    zero_model_top_10000_hits: int
    universe_size: int
    target_ranks: list[TargetRank]
    zero_model_target_ranks: list[TargetRank]
    top_candidates: list[tuple[int, tuple[int, ...], float]]

    def as_dict(self, candidate_preview_limit: int = 100) -> dict:
        return {
            "strategy_key": self.strategy_key,
            "as_of_issue": self.as_of_issue,
            "history_fingerprint": self.history_fingerprint,
            "config_hash": self.config_hash,
            "train_window": self.train_window,
            "train_mode": self.train_mode,
            "eval_window": self.eval_window,
            "top_n": self.top_n,
            "workers": self.workers,
            "evaluated_draws": self.evaluated_draws,
            "top_100_hits": self.top_100_hits,
            "top_1000_hits": self.top_1000_hits,
            "top_10000_hits": self.top_10000_hits,
            "zero_model_top_100_hits": self.zero_model_top_100_hits,
            "zero_model_top_1000_hits": self.zero_model_top_1000_hits,
            "zero_model_top_10000_hits": self.zero_model_top_10000_hits,
            "universe_size": self.universe_size,
            "random_uniform_baseline": random_uniform_baseline(
                evaluated_draws=self.evaluated_draws,
                universe_size=self.universe_size,
            ),
            "target_ranks": [
                {
                    "issue": rank.issue,
                    "rank": rank.rank,
                    "score": rank.score,
                    "hit_top_100": rank.hit_top_100,
                    "hit_top_1000": rank.hit_top_1000,
                    "hit_top_10000": rank.hit_top_10000,
                }
                for rank in self.target_ranks
            ],
            "zero_model_target_ranks": [
                {
                    "issue": rank.issue,
                    "rank": rank.rank,
                    "score": rank.score,
                    "hit_top_100": rank.hit_top_100,
                    "hit_top_1000": rank.hit_top_1000,
                    "hit_top_10000": rank.hit_top_10000,
                }
                for rank in self.zero_model_target_ranks
            ],
            "top_candidates_preview": [
                {"rank": rank, "numbers": numbers, "score": score}
                for rank, numbers, score in self.top_candidates[:candidate_preview_limit]
            ],
        }


def random_uniform_baseline(*, evaluated_draws: int, universe_size: int) -> dict[str, dict[str, float]]:
    cutoffs = {"top_100": 100, "top_1000": 1000, "top_10000": 10000}
    return {
        name: {
            "hit_rate": min(cutoff, universe_size) / universe_size if universe_size else 0,
            "expected_hits": evaluated_draws * min(cutoff, universe_size) / universe_size if universe_size else 0,
        }
        for name, cutoff in cutoffs.items()
    }


def fingerprint_history(history: list[tuple[str, tuple[int, ...]]]) -> str:
    payload = "|".join(f"{issue}:{','.join(map(str, numbers))}" for issue, numbers in history)
    return sha256(payload.encode("utf-8")).hexdigest()


def config_hash(config: FrequencyRankerConfig) -> str:
    payload = json.dumps(config.__dict__, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def deterministic_run_key(
    *,
    strategy_key: str,
    as_of_issue: str,
    train_window: int,
    train_mode: str = "expanding",
    eval_window: int,
    top_n: int,
    history_fingerprint_value: str,
    config_hash_value: str,
) -> str:
    payload = ":".join(
        [
            strategy_key,
            as_of_issue,
            str(train_window),
            train_mode,
            str(eval_window),
            str(top_n),
            history_fingerprint_value,
            config_hash_value,
        ],
    )
    digest = sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"walk-forward-{strategy_key}-asof-{as_of_issue}-{digest}"


def build_ranked_universe(universe: Iterable[tuple[int, ...]] | None = None) -> list[RankedUniverseEntry]:
    entries: list[RankedUniverseEntry] = []
    for numbers in universe or iter_ssq_red_combinations():
        scored = score_numbers(numbers)
        features = calculate_red_ball_features(numbers)
        entries.append(
            RankedUniverseEntry(
                numbers=numbers,
                structural_score=scored["score"],
                consecutive_pair_count=features["consecutive_pair_count"],
                odd_count=features["odd_count"],
                zone_counts=(
                    features["zone_1_count"],
                    features["zone_2_count"],
                    features["zone_3_count"],
                ),
            )
        )
    return entries


def normalize_worker_count(workers: int | None) -> int:
    cpu_count = max(1, os.cpu_count() or 1)
    if workers is None or workers < 1:
        return min(DEFAULT_WORKERS, cpu_count)
    return min(workers, cpu_count)


def chunk_ranges(total: int, chunks: int) -> list[tuple[int, int]]:
    chunk_count = max(1, min(chunks, total))
    base, remainder = divmod(total, chunk_count)
    ranges: list[tuple[int, int]] = []
    start = 0
    for index in range(chunk_count):
        size = base + (1 if index < remainder else 0)
        end = start + size
        ranges.append((start, end))
        start = end
    return ranges


def _init_worker_universe(entries: list[RankedUniverseEntry]) -> None:
    global _WORKER_UNIVERSE
    _WORKER_UNIVERSE = entries


def score_ranked_entry(
    entry: RankedUniverseEntry,
    stats: FrequencyStats,
    config: FrequencyRankerConfig,
) -> float:
    frequency_score = sum(stats.frequency_rate[number] for number in entry.numbers)
    omission_score = sum(stats.omission_rate[number] for number in entry.numbers) / 6
    previous_consecutive_score = _previous_consecutive_score(
        candidate_pair_count=entry.consecutive_pair_count,
        previous_pair_count=stats.previous_consecutive_pair_count,
    )
    previous_overlap_score = sum(1 for number in entry.numbers if number in stats.previous_number_set) / 6
    previous_parity_shape_score = 1 - abs(entry.odd_count - stats.previous_odd_count) / 6
    previous_zone_shape_score = 1 - sum(
        abs(candidate_count - previous_count)
        for candidate_count, previous_count in zip(entry.zone_counts, stats.previous_zone_counts, strict=True)
    ) / 12
    return round(
        config.structural_weight * entry.structural_score
        + config.frequency_weight * frequency_score
        + config.omission_weight * omission_score
        + config.previous_consecutive_weight * previous_consecutive_score
        + config.previous_overlap_weight * previous_overlap_score
        + config.previous_parity_shape_weight * previous_parity_shape_score
        + config.previous_zone_shape_weight * previous_zone_shape_score,
        8,
    )


def _rank_chunk(args: tuple[int, int, tuple[int, ...], float, FrequencyStats, FrequencyRankerConfig]) -> tuple[int, int]:
    start, end, target_numbers, target_score, stats, config = args
    better = 0
    equal_before = 0
    for entry in _WORKER_UNIVERSE[start:end]:
        score = score_ranked_entry(entry, stats, config)
        if score > target_score:
            better += 1
        elif score == target_score and entry.numbers < target_numbers:
            equal_before += 1
    return better, equal_before


def _top_chunk(args: tuple[int, int, int, FrequencyStats, FrequencyRankerConfig]) -> list[tuple[float, tuple[int, ...]]]:
    start, end, top_n, stats, config = args
    ranked = nlargest(
        top_n,
        (
            (score_ranked_entry(entry, stats, config), entry.numbers)
            for entry in _WORKER_UNIVERSE[start:end]
        ),
        key=lambda item: (item[0], tuple(-number for number in item[1])),
    )
    return ranked


def rank_target(
    *,
    target_numbers: tuple[int, ...],
    train_history: list[tuple[str, tuple[int, ...]]],
    config: FrequencyRankerConfig,
    universe: Iterable[tuple[int, ...]] | None = None,
    ranked_universe: list[RankedUniverseEntry] | None = None,
    workers: int = 1,
    pool: Pool | None = None,
) -> tuple[int, float]:
    stats = train_frequency_stats(train_history)
    target_score = score_frequency_candidate(target_numbers, stats, config)["score"]
    better = 0
    equal_before = 0
    entries = ranked_universe or build_ranked_universe(universe)
    worker_count = normalize_worker_count(workers)
    if worker_count > 1 and pool is not None and entries is _WORKER_UNIVERSE:
        ranges = chunk_ranges(len(entries), worker_count)
        partials = pool.map(
            _rank_chunk,
            [(start, end, target_numbers, target_score, stats, config) for start, end in ranges],
        )
        better = sum(partial[0] for partial in partials)
        equal_before = sum(partial[1] for partial in partials)
        return better + equal_before + 1, target_score

    for entry in entries:
        score = score_ranked_entry(entry, stats, config)
        if score > target_score:
            better += 1
        elif score == target_score and entry.numbers < target_numbers:
            equal_before += 1
    return better + equal_before + 1, target_score


def rank_target_structural(
    *,
    target_numbers: tuple[int, ...],
    ranked_universe: list[RankedUniverseEntry],
) -> tuple[int, float]:
    target_score = round(score_numbers(target_numbers)["score"], 8)
    better = 0
    equal_before = 0
    for entry in ranked_universe:
        score = round(entry.structural_score, 8)
        if score > target_score:
            better += 1
        elif score == target_score and entry.numbers < target_numbers:
            equal_before += 1
    return better + equal_before + 1, target_score


def top_candidates_for_next(
    *,
    history: list[tuple[str, tuple[int, ...]]],
    top_n: int,
    config: FrequencyRankerConfig,
    universe: Iterable[tuple[int, ...]] | None = None,
    ranked_universe: list[RankedUniverseEntry] | None = None,
    workers: int = 1,
    pool: Pool | None = None,
) -> list[tuple[int, tuple[int, ...], float]]:
    stats = train_frequency_stats(history)
    entries = ranked_universe or build_ranked_universe(universe)
    worker_count = normalize_worker_count(workers)
    if worker_count > 1 and pool is not None and entries is _WORKER_UNIVERSE:
        ranges = chunk_ranges(len(entries), worker_count)
        partials = pool.map(
            _top_chunk,
            [(start, end, top_n, stats, config) for start, end in ranges],
        )
        merged = nlargest(
            top_n,
            (item for partial in partials for item in partial),
            key=lambda item: (item[0], tuple(-number for number in item[1])),
        )
        return [(rank, numbers, score) for rank, (score, numbers) in enumerate(merged, start=1)]

    ranked = nlargest(
        top_n,
        (
            (score_ranked_entry(entry, stats, config), tuple(-number for number in entry.numbers), entry.numbers)
            for entry in entries
        ),
    )
    return [(rank, numbers, score) for rank, (score, _, numbers) in enumerate(ranked, start=1)]


def run_walk_forward(
    *,
    history: list[tuple[str, tuple[int, ...]]],
    train_window: int,
    eval_window: int,
    top_n: int = 10000,
    train_mode: Literal["expanding", "rolling"] = "expanding",
    config: FrequencyRankerConfig | None = None,
    universe: Iterable[tuple[int, ...]] | None = None,
    workers: int | None = None,
) -> WalkForwardResult:
    if train_window < 1:
        raise ValueError("train_window must be at least 1")
    if eval_window < 1:
        raise ValueError("eval_window must be at least 1")
    if train_mode not in ("expanding", "rolling"):
        raise ValueError("train_mode must be 'expanding' or 'rolling'")
    if len(history) <= train_window:
        raise ValueError("history must be longer than train_window")

    cfg = config or FrequencyRankerConfig()
    as_of_issue = history[-1][0]
    history_fingerprint_value = fingerprint_history(history)
    config_hash_value = config_hash(cfg)
    worker_count = normalize_worker_count(workers)
    start = max(train_window, len(history) - eval_window)
    target_ranks: list[TargetRank] = []
    zero_model_target_ranks: list[TargetRank] = []
    ranked_universe = build_ranked_universe(universe)
    global _WORKER_UNIVERSE
    _WORKER_UNIVERSE = ranked_universe

    pool: Pool | None = None
    if worker_count > 1:
        context = mp.get_context("fork") if "fork" in mp.get_all_start_methods() else mp.get_context()
        pool = context.Pool(processes=worker_count, initializer=_init_worker_universe, initargs=(ranked_universe,))

    try:
        for target_index in range(start, len(history)):
            train_start = 0 if train_mode == "expanding" else max(0, target_index - train_window)
            train_history = history[train_start:target_index]
            issue, numbers = history[target_index]
            rank, score = rank_target(
                target_numbers=numbers,
                train_history=train_history,
                config=cfg,
                ranked_universe=ranked_universe,
                workers=worker_count,
                pool=pool,
            )
            target_ranks.append(
                TargetRank(
                    issue=issue,
                    rank=rank,
                    score=score,
                    hit_top_100=rank <= 100,
                    hit_top_1000=rank <= 1000,
                    hit_top_10000=rank <= 10000,
                ),
            )
            zero_rank, zero_score = rank_target_structural(
                target_numbers=numbers,
                ranked_universe=ranked_universe,
            )
            zero_model_target_ranks.append(
                TargetRank(
                    issue=issue,
                    rank=zero_rank,
                    score=zero_score,
                    hit_top_100=zero_rank <= 100,
                    hit_top_1000=zero_rank <= 1000,
                    hit_top_10000=zero_rank <= 10000,
                ),
            )

        top_candidates = top_candidates_for_next(
            history=history if train_mode == "expanding" else history[-train_window:],
            top_n=min(top_n, len(ranked_universe)),
            config=cfg,
            ranked_universe=ranked_universe,
            workers=worker_count,
            pool=pool,
        )
    finally:
        if pool is not None:
            pool.close()
            pool.join()

    return WalkForwardResult(
        strategy_key="frequency_v1",
        as_of_issue=as_of_issue,
        history_fingerprint=history_fingerprint_value,
        config_hash=config_hash_value,
        train_window=train_window,
        train_mode=train_mode,
        eval_window=len(target_ranks),
        top_n=top_n,
        workers=worker_count,
        evaluated_draws=len(target_ranks),
        top_100_hits=sum(rank.hit_top_100 for rank in target_ranks),
        top_1000_hits=sum(rank.hit_top_1000 for rank in target_ranks),
        top_10000_hits=sum(rank.hit_top_10000 for rank in target_ranks),
        zero_model_top_100_hits=sum(rank.hit_top_100 for rank in zero_model_target_ranks),
        zero_model_top_1000_hits=sum(rank.hit_top_1000 for rank in zero_model_target_ranks),
        zero_model_top_10000_hits=sum(rank.hit_top_10000 for rank in zero_model_target_ranks),
        universe_size=len(ranked_universe),
        target_ranks=target_ranks,
        zero_model_target_ranks=zero_model_target_ranks,
        top_candidates=top_candidates,
    )
