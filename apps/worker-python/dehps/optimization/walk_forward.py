from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from heapq import nlargest
import json
import multiprocessing as mp
import os
from multiprocessing.pool import Pool
from typing import Callable, Iterable, Literal

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
ScoreComponents = tuple[float, float, float, float, float, float, float]


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
    red5_rank: int | None = None
    red5_score: float | None = None
    red5_numbers: tuple[int, ...] | None = None
    red5_missing_number: int | None = None
    red5_extra_number: int | None = None
    hit_red5_top_100: bool = False
    hit_red5_top_1000: bool = False
    hit_red5_top_10000: bool = False


@dataclass(frozen=True)
class RedFiveMatch:
    rank: int
    score: float
    numbers: tuple[int, ...]
    missing_number: int
    extra_number: int


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
                    "red5_rank": rank.red5_rank,
                    "red5_score": rank.red5_score,
                    "red5_numbers": rank.red5_numbers,
                    "red5_missing_number": rank.red5_missing_number,
                    "red5_extra_number": rank.red5_extra_number,
                    "hit_red5_top_100": rank.hit_red5_top_100,
                    "hit_red5_top_1000": rank.hit_red5_top_1000,
                    "hit_red5_top_10000": rank.hit_red5_top_10000,
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


def create_worker_pool(worker_count: int, ranked_universe: list[RankedUniverseEntry]) -> Pool | None:
    global _WORKER_UNIVERSE
    _WORKER_UNIVERSE = ranked_universe
    if worker_count <= 1:
        return None
    context = mp.get_context("fork") if "fork" in mp.get_all_start_methods() else mp.get_context()
    return context.Pool(processes=worker_count, initializer=_init_worker_universe, initargs=(ranked_universe,))


def score_components_for_entry(entry: RankedUniverseEntry, stats: FrequencyStats) -> ScoreComponents:
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
    return (
        entry.structural_score,
        frequency_score,
        omission_score,
        previous_consecutive_score,
        previous_overlap_score,
        previous_parity_shape_score,
        previous_zone_shape_score,
    )


def score_components_for_numbers(numbers: tuple[int, ...], stats: FrequencyStats) -> ScoreComponents:
    structural_score = score_numbers(numbers)["score"]
    features = calculate_red_ball_features(numbers)
    previous_consecutive_score = _previous_consecutive_score(
        candidate_pair_count=features["consecutive_pair_count"],
        previous_pair_count=stats.previous_consecutive_pair_count,
    )
    previous_overlap_score = len(set(numbers) & stats.previous_number_set) / 6
    previous_parity_shape_score = 1 - abs(features["odd_count"] - stats.previous_odd_count) / 6
    zone_counts = (features["zone_1_count"], features["zone_2_count"], features["zone_3_count"])
    previous_zone_shape_score = 1 - sum(
        abs(candidate_count - previous_count)
        for candidate_count, previous_count in zip(zone_counts, stats.previous_zone_counts, strict=True)
    ) / 12
    return (
        structural_score,
        sum(stats.frequency_rate[number] for number in numbers),
        sum(stats.omission_rate[number] for number in numbers) / 6,
        previous_consecutive_score,
        previous_overlap_score,
        previous_parity_shape_score,
        previous_zone_shape_score,
    )


def score_from_components(components: ScoreComponents, config: FrequencyRankerConfig) -> float:
    (
        structural_score,
        frequency_score,
        omission_score,
        previous_consecutive_score,
        previous_overlap_score,
        previous_parity_shape_score,
        previous_zone_shape_score,
    ) = components
    return round(
        config.structural_weight * structural_score
        + config.frequency_weight * frequency_score
        + config.omission_weight * omission_score
        + config.previous_consecutive_weight * previous_consecutive_score
        + config.previous_overlap_weight * previous_overlap_score
        + config.previous_parity_shape_weight * previous_parity_shape_score
        + config.previous_zone_shape_weight * previous_zone_shape_score,
        8,
    )


def score_ranked_entry(
    entry: RankedUniverseEntry,
    stats: FrequencyStats,
    config: FrequencyRankerConfig,
) -> float:
    return score_from_components(score_components_for_entry(entry, stats), config)


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


def _rank_grid_chunk(
    args: tuple[int, int, tuple[int, ...], tuple[float, ...], FrequencyStats, tuple[FrequencyRankerConfig, ...]],
) -> tuple[list[int], list[int]]:
    start, end, target_numbers, target_scores, stats, configs = args
    better = [0 for _ in configs]
    equal_before = [0 for _ in configs]
    for entry in _WORKER_UNIVERSE[start:end]:
        components = score_components_for_entry(entry, stats)
        for index, config in enumerate(configs):
            score = score_from_components(components, config)
            if score > target_scores[index]:
                better[index] += 1
            elif score == target_scores[index] and entry.numbers < target_numbers:
                equal_before[index] += 1
    return better, equal_before


def _candidate_sort_key(score: float, numbers: tuple[int, ...]) -> tuple[float, tuple[int, ...]]:
    return score, tuple(-number for number in numbers)


def _is_better_candidate(
    candidate: tuple[float, tuple[int, ...]] | None,
    current: tuple[float, tuple[int, ...]] | None,
) -> bool:
    if candidate is None:
        return False
    if current is None:
        return True
    return _candidate_sort_key(candidate[0], candidate[1]) > _candidate_sort_key(current[0], current[1])


def _rank_grid_red5_chunk(
    args: tuple[int, int, tuple[int, ...], tuple[float, ...], FrequencyStats, tuple[FrequencyRankerConfig, ...]],
) -> tuple[list[int], list[int], list[tuple[float, tuple[int, ...]] | None]]:
    start, end, target_numbers, target_scores, stats, configs = args
    target_set = set(target_numbers)
    better = [0 for _ in configs]
    equal_before = [0 for _ in configs]
    best_red5: list[tuple[float, tuple[int, ...]] | None] = [None for _ in configs]
    for entry in _WORKER_UNIVERSE[start:end]:
        components = score_components_for_entry(entry, stats)
        red_overlap = sum(1 for number in entry.numbers if number in target_set)
        for index, config in enumerate(configs):
            score = score_from_components(components, config)
            if score > target_scores[index]:
                better[index] += 1
            elif score == target_scores[index] and entry.numbers < target_numbers:
                equal_before[index] += 1
            if red_overlap == 5:
                candidate = (score, entry.numbers)
                if _is_better_candidate(candidate, best_red5[index]):
                    best_red5[index] = candidate
    return better, equal_before, best_red5


def _rank_specific_grid_chunk(
    args: tuple[
        int,
        int,
        tuple[tuple[int, ...] | None, ...],
        tuple[float | None, ...],
        FrequencyStats,
        tuple[FrequencyRankerConfig, ...],
    ],
) -> tuple[list[int], list[int]]:
    start, end, candidate_numbers, candidate_scores, stats, configs = args
    better = [0 for _ in configs]
    equal_before = [0 for _ in configs]
    for entry in _WORKER_UNIVERSE[start:end]:
        components = score_components_for_entry(entry, stats)
        for index, config in enumerate(configs):
            numbers = candidate_numbers[index]
            score_threshold = candidate_scores[index]
            if numbers is None or score_threshold is None:
                continue
            score = score_from_components(components, config)
            if score > score_threshold:
                better[index] += 1
            elif score == score_threshold and entry.numbers < numbers:
                equal_before[index] += 1
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


def rank_target_grid(
    *,
    target_numbers: tuple[int, ...],
    train_history: list[tuple[str, tuple[int, ...]]],
    configs: tuple[FrequencyRankerConfig, ...],
    ranked_universe: list[RankedUniverseEntry],
    workers: int = 1,
    pool: Pool | None = None,
) -> list[tuple[int, float]]:
    stats = train_frequency_stats(train_history)
    target_components = score_components_for_numbers(target_numbers, stats)
    target_scores = tuple(score_from_components(target_components, config) for config in configs)
    worker_count = normalize_worker_count(workers)

    if worker_count > 1 and pool is not None:
        ranges = chunk_ranges(len(ranked_universe), worker_count)
        partials = pool.map(
            _rank_grid_chunk,
            [(start, end, target_numbers, target_scores, stats, configs) for start, end in ranges],
        )
        better = [0 for _ in configs]
        equal_before = [0 for _ in configs]
        for partial_better, partial_equal_before in partials:
            for index in range(len(configs)):
                better[index] += partial_better[index]
                equal_before[index] += partial_equal_before[index]
        return [(better[index] + equal_before[index] + 1, target_scores[index]) for index in range(len(configs))]

    better = [0 for _ in configs]
    equal_before = [0 for _ in configs]
    for entry in ranked_universe:
        components = score_components_for_entry(entry, stats)
        for index, config in enumerate(configs):
            score = score_from_components(components, config)
            if score > target_scores[index]:
                better[index] += 1
            elif score == target_scores[index] and entry.numbers < target_numbers:
                equal_before[index] += 1
    return [(better[index] + equal_before[index] + 1, target_scores[index]) for index in range(len(configs))]


def rank_target_grid_with_red5(
    *,
    target_numbers: tuple[int, ...],
    train_history: list[tuple[str, tuple[int, ...]]],
    configs: tuple[FrequencyRankerConfig, ...],
    ranked_universe: list[RankedUniverseEntry],
    workers: int = 1,
    pool: Pool | None = None,
) -> list[tuple[int, float, RedFiveMatch | None]]:
    stats = train_frequency_stats(train_history)
    target_components = score_components_for_numbers(target_numbers, stats)
    target_scores = tuple(score_from_components(target_components, config) for config in configs)
    worker_count = normalize_worker_count(workers)

    better = [0 for _ in configs]
    equal_before = [0 for _ in configs]
    best_red5: list[tuple[float, tuple[int, ...]] | None] = [None for _ in configs]

    if worker_count > 1 and pool is not None:
        ranges = chunk_ranges(len(ranked_universe), worker_count)
        partials = pool.map(
            _rank_grid_red5_chunk,
            [(start, end, target_numbers, target_scores, stats, configs) for start, end in ranges],
        )
        for partial_better, partial_equal_before, partial_red5 in partials:
            for index in range(len(configs)):
                better[index] += partial_better[index]
                equal_before[index] += partial_equal_before[index]
                if _is_better_candidate(partial_red5[index], best_red5[index]):
                    best_red5[index] = partial_red5[index]
    else:
        target_set = set(target_numbers)
        for entry in ranked_universe:
            components = score_components_for_entry(entry, stats)
            red_overlap = sum(1 for number in entry.numbers if number in target_set)
            for index, config in enumerate(configs):
                score = score_from_components(components, config)
                if score > target_scores[index]:
                    better[index] += 1
                elif score == target_scores[index] and entry.numbers < target_numbers:
                    equal_before[index] += 1
                if red_overlap == 5:
                    candidate = (score, entry.numbers)
                    if _is_better_candidate(candidate, best_red5[index]):
                        best_red5[index] = candidate

    red5_numbers = tuple(candidate[1] if candidate else None for candidate in best_red5)
    red5_scores = tuple(candidate[0] if candidate else None for candidate in best_red5)
    red5_better = [0 for _ in configs]
    red5_equal_before = [0 for _ in configs]
    if any(candidate is not None for candidate in best_red5):
        if worker_count > 1 and pool is not None:
            ranges = chunk_ranges(len(ranked_universe), worker_count)
            partials = pool.map(
                _rank_specific_grid_chunk,
                [(start, end, red5_numbers, red5_scores, stats, configs) for start, end in ranges],
            )
            for partial_better, partial_equal_before in partials:
                for index in range(len(configs)):
                    red5_better[index] += partial_better[index]
                    red5_equal_before[index] += partial_equal_before[index]
        else:
            for entry in ranked_universe:
                components = score_components_for_entry(entry, stats)
                for index, config in enumerate(configs):
                    numbers = red5_numbers[index]
                    score_threshold = red5_scores[index]
                    if numbers is None or score_threshold is None:
                        continue
                    score = score_from_components(components, config)
                    if score > score_threshold:
                        red5_better[index] += 1
                    elif score == score_threshold and entry.numbers < numbers:
                        red5_equal_before[index] += 1

    target_set = set(target_numbers)
    results: list[tuple[int, float, RedFiveMatch | None]] = []
    for index, target_score in enumerate(target_scores):
        match = None
        candidate_numbers = red5_numbers[index]
        candidate_score = red5_scores[index]
        if candidate_numbers is not None and candidate_score is not None:
            candidate_set = set(candidate_numbers)
            missing = sorted(target_set - candidate_set)
            extra = sorted(candidate_set - target_set)
            if len(missing) == 1 and len(extra) == 1:
                match = RedFiveMatch(
                    rank=red5_better[index] + red5_equal_before[index] + 1,
                    score=candidate_score,
                    numbers=candidate_numbers,
                    missing_number=missing[0],
                    extra_number=extra[0],
                )
        results.append((better[index] + equal_before[index] + 1, target_score, match))
    return results


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
    progress_callback: Callable[[int, int, str, int], None] | None = None,
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
    pool = create_worker_pool(worker_count, ranked_universe)

    try:
        total_targets = len(history) - start
        for progress_index, target_index in enumerate(range(start, len(history)), start=1):
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
            if progress_callback:
                progress_callback(progress_index, total_targets, issue, len(train_history))

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
