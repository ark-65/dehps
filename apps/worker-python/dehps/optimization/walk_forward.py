from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from heapq import nlargest
import json
import multiprocessing as mp
import os
from multiprocessing.pool import Pool
from pathlib import Path
import time
from typing import Callable, Iterable, Literal

import numpy as np

from dehps.config import ROOT_DIR
from dehps.domain.combination import iter_ssq_red_combinations
from dehps.features.qian_kun import qian_kun_pattern, qian_kun_similarity
from dehps.features.red_ball_features import calculate_red_ball_features
from dehps.models.frequency_ranker import (
    PRIME_NUMBERS,
    FrequencyRankerConfig,
    FrequencyStats,
    HistoryDraw,
    _profile_score,
    _previous_consecutive_score,
    _red_omission_shape_score,
    _shape_profile,
    _stable_range_score,
    _sum_span_omission_score,
    score_frequency_candidate,
    train_frequency_stats,
    history_draw_date,
    history_issue,
    history_numbers,
    infer_next_ssq_draw_date,
)
from dehps.scoring.strategy import score_numbers

_WORKER_UNIVERSE: object | None = None
DEFAULT_WORKERS = 16
ScoreComponents = tuple[float, ...]
FEATURE_SCHEMA_VERSION = "ranked-universe-matrix-v1"
FILTER_RULE_VERSION = "fixed-max-run-5-single-zone-v1"
DEFAULT_MATRIX_CACHE_DIR = ROOT_DIR / "data/output/cache"
QIAN_KUN_SIMILARITY = np.array(
    [
        [1 - (left ^ right).bit_count() / 6 for right in range(64)]
        for left in range(64)
    ],
    dtype=np.float64,
)
CONFIG_WEIGHT_FIELDS = (
    "structural_weight",
    "frequency_weight",
    "omission_weight",
    "previous_consecutive_weight",
    "previous_overlap_weight",
    "previous_parity_shape_weight",
    "dynamic_parity_transition_weight",
    "previous_zone_shape_weight",
    "recent_neighbor_weight",
    "lagged_consecutive_weight",
    "recent_gap_shape_weight",
    "recent_sum_span_weight",
    "qian_kun_pattern_weight",
    "first_last_sum_weight",
    "span_trend_weight",
    "sum_trend_weight",
    "ac_trend_weight",
    "zone_ratio_weight",
    "big_small_ratio_weight",
    "parity_ratio_weight",
    "prime_composite_weight",
    "mod012_weight",
    "tail_distribution_weight",
    "sum_tail_weight",
    "red_omission_shape_weight",
    "sum_span_omission_weight",
    "consecutive_trend_weight",
    "repeat_trend_weight",
    "stable_range_weight",
    "weekday_trend_weight",
    "short_hot_frequency_weight",
    "long_omission_cooldown_weight",
)


@dataclass(frozen=True)
class RankedUniverseEntry:
    numbers: tuple[int, ...]
    structural_score: float
    consecutive_pair_count: int
    odd_count: int
    zone_counts: tuple[int, int, int]
    gaps: tuple[int, int, int, int, int]
    sum_value: int
    span_value: int
    qian_kun_pattern: str
    first_last_sum: int
    sum_bucket: int
    span_bucket: int
    ac_value: int
    big_count: int
    even_count: int
    prime_count: int
    mod012_counts: tuple[int, int, int]
    tail_unique_count: int
    sum_tail: int
    max_gap: int
    min_gap: int


@dataclass
class RankedUniverseMatrix:
    numbers: np.ndarray
    structural_score: np.ndarray
    consecutive_pair_count: np.ndarray
    odd_count: np.ndarray
    zone_counts: np.ndarray
    gaps: np.ndarray
    sum_value: np.ndarray
    span_value: np.ndarray
    qian_kun_code: np.ndarray
    first_last_sum: np.ndarray
    sum_bucket: np.ndarray
    span_bucket: np.ndarray
    ac_value: np.ndarray
    big_count: np.ndarray
    even_count: np.ndarray
    prime_count: np.ndarray
    mod012_counts: np.ndarray
    tail_unique_count: np.ndarray
    sum_tail: np.ndarray
    max_gap: np.ndarray
    min_gap: np.ndarray
    number_presence: np.ndarray
    cache_info: dict

    def __len__(self) -> int:
        return int(self.numbers.shape[0])

    def __iter__(self):
        for index in range(len(self)):
            yield self.entry_at(index)

    def entry_at(self, index: int) -> RankedUniverseEntry:
        numbers = tuple(int(number) for number in self.numbers[index])
        return RankedUniverseEntry(
            numbers=numbers,
            structural_score=float(self.structural_score[index]),
            consecutive_pair_count=int(self.consecutive_pair_count[index]),
            odd_count=int(self.odd_count[index]),
            zone_counts=tuple(int(value) for value in self.zone_counts[index]),  # type: ignore[arg-type]
            gaps=tuple(int(value) for value in self.gaps[index]),  # type: ignore[arg-type]
            sum_value=int(self.sum_value[index]),
            span_value=int(self.span_value[index]),
            qian_kun_pattern=format(int(self.qian_kun_code[index]), "06b"),
            first_last_sum=int(self.first_last_sum[index]),
            sum_bucket=int(self.sum_bucket[index]),
            span_bucket=int(self.span_bucket[index]),
            ac_value=int(self.ac_value[index]),
            big_count=int(self.big_count[index]),
            even_count=int(self.even_count[index]),
            prime_count=int(self.prime_count[index]),
            mod012_counts=tuple(int(value) for value in self.mod012_counts[index]),  # type: ignore[arg-type]
            tail_unique_count=int(self.tail_unique_count[index]),
            sum_tail=int(self.sum_tail[index]),
            max_gap=int(self.max_gap[index]),
            min_gap=int(self.min_gap[index]),
        )


@dataclass(frozen=True)
class TargetRank:
    issue: str
    rank: int
    score: float
    hit_top_100: bool
    hit_top_1000: bool
    hit_top_10000: bool
    draw_date: date | None = None
    red_numbers: tuple[int, ...] | None = None
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


def fingerprint_history(history: list[HistoryDraw]) -> str:
    payload = "|".join(
        f"{history_issue(draw)}:{history_draw_date(draw).isoformat() if history_draw_date(draw) else ''}:"
        f"{','.join(map(str, history_numbers(draw)))}"
        for draw in history
    )
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


def is_excluded_red_combination(numbers: tuple[int, ...]) -> bool:
    features = calculate_red_ball_features(numbers)
    if int(features["max_consecutive_run"]) >= 5:
        return True
    return any(
        int(features[key]) == 6
        for key in ("zone_1_count", "zone_2_count", "zone_3_count")
    )


def build_ranked_universe(universe: Iterable[tuple[int, ...]] | None = None) -> list[RankedUniverseEntry]:
    entries: list[RankedUniverseEntry] = []
    for numbers in universe or iter_ssq_red_combinations():
        scored = score_numbers(numbers)
        features = calculate_red_ball_features(numbers)
        if int(features["max_consecutive_run"]) >= 5 or any(
            int(features[key]) == 6
            for key in ("zone_1_count", "zone_2_count", "zone_3_count")
        ):
            continue
        tails = [number % 10 for number in numbers]
        pairwise_distances = {right - left for index, left in enumerate(numbers) for right in numbers[index + 1:]}
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
                gaps=(numbers[1] - numbers[0], numbers[2] - numbers[1], numbers[3] - numbers[2], numbers[4] - numbers[3], numbers[5] - numbers[4]),
                sum_value=int(features["sum_value"]),
                span_value=int(features["span_value"]),
                qian_kun_pattern=qian_kun_pattern(numbers),
                first_last_sum=numbers[0] + numbers[-1],
                sum_bucket=int(features["sum_value"]) // 10,
                span_bucket=int(features["span_value"]) // 3,
                ac_value=max(0, len(pairwise_distances) - 5),
                big_count=int(features["big_count"]),
                even_count=int(features["even_count"]),
                prime_count=sum(1 for number in numbers if number in PRIME_NUMBERS),
                mod012_counts=(
                    sum(1 for number in numbers if number % 3 == 0),
                    sum(1 for number in numbers if number % 3 == 1),
                    sum(1 for number in numbers if number % 3 == 2),
                ),
                tail_unique_count=len(set(tails)),
                sum_tail=int(features["sum_value"]) % 10,
                max_gap=max(numbers[1] - numbers[0], numbers[2] - numbers[1], numbers[3] - numbers[2], numbers[4] - numbers[3], numbers[5] - numbers[4]),
                min_gap=min(numbers[1] - numbers[0], numbers[2] - numbers[1], numbers[3] - numbers[2], numbers[4] - numbers[3], numbers[5] - numbers[4]),
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
    short_hot_frequency_score = sum(stats.recent_frequency_rate[number] for number in entry.numbers) / 6
    omission_score = sum(stats.omission_rate[number] for number in entry.numbers) / 6
    long_omission_cooldown_score = max(
        0.0,
        min(1.0, 1 - sum(stats.recent_omission_pressure[number] ** 1.5 for number in entry.numbers) / 6),
    )
    previous_consecutive_score = _previous_consecutive_score(
        candidate_pair_count=entry.consecutive_pair_count,
        previous_pair_count=stats.previous_consecutive_pair_count,
    )
    previous_overlap_score = sum(1 for number in entry.numbers if number in stats.previous_number_set) / 6
    previous_parity_shape_score = 1 - abs(entry.odd_count - stats.previous_odd_count) / 6
    dynamic_parity_transition_score = stats.parity_transition_score_by_even_count[6 - entry.odd_count]
    previous_zone_shape_score = 1 - sum(
        abs(candidate_count - previous_count)
        for candidate_count, previous_count in zip(entry.zone_counts, stats.previous_zone_counts, strict=True)
    ) / 12
    recent_neighbor_score = sum(stats.recent_neighbor_rate[number] for number in entry.numbers) / 6
    lagged_consecutive_score = len(set(entry.numbers) & stats.lagged_consecutive_number_set) / 6
    recent_gap_shape_score = max(
        0.0,
        1
        - sum(abs(gap - average) for gap, average in zip(entry.gaps, stats.recent_average_gaps, strict=True))
        / (5 * 32),
    )
    recent_sum_span_score = (
        max(0.0, 1 - abs(entry.sum_value - stats.recent_average_sum) / 162)
        + max(0.0, 1 - abs(entry.span_value - stats.recent_average_span) / 32)
    ) / 2
    qian_kun_pattern_score = _qian_kun_pattern_score(entry.qian_kun_pattern, stats)
    first_last_sum_score = stats.shape_profile_rates.get("first_last_sum", {}).get(entry.first_last_sum, 0.0)
    span_trend_score = stats.shape_profile_rates.get("span_bucket", {}).get(entry.span_bucket, 0.0)
    sum_trend_score = stats.shape_profile_rates.get("sum_bucket", {}).get(entry.sum_bucket, 0.0)
    ac_trend_score = stats.shape_profile_rates.get("ac_value", {}).get(entry.ac_value, 0.0)
    zone_ratio_score = stats.shape_profile_rates.get("zone_signature", {}).get(entry.zone_counts, 0.0)
    big_small_ratio_score = stats.shape_profile_rates.get("big_count", {}).get(entry.big_count, 0.0)
    parity_ratio_score = stats.shape_profile_rates.get("even_count", {}).get(entry.even_count, 0.0)
    prime_composite_score = stats.shape_profile_rates.get("prime_count", {}).get(entry.prime_count, 0.0)
    mod012_score = stats.shape_profile_rates.get("mod012_signature", {}).get(entry.mod012_counts, 0.0)
    tail_distribution_score = stats.shape_profile_rates.get("tail_unique_count", {}).get(entry.tail_unique_count, 0.0)
    sum_tail_score = stats.shape_profile_rates.get("sum_tail", {}).get(entry.sum_tail, 0.0)
    candidate_omission_average = sum(stats.omission_rate[number] for number in entry.numbers) / 6
    red_omission_shape_score = max(0.0, 1 - abs(candidate_omission_average - stats.recent_average_omission))
    sum_span_omission_score = (
        stats.sum_bucket_omission_rate.get(entry.sum_bucket, 1.0)
        + stats.span_bucket_omission_rate.get(entry.span_bucket, 1.0)
    ) / 2
    consecutive_trend_score = stats.shape_profile_rates.get("consecutive_pair_count", {}).get(entry.consecutive_pair_count, 0.0)
    repeat_count = int(previous_overlap_score * 6)
    repeat_trend_score = stats.shape_profile_rates.get("repeat_count", {}).get(repeat_count, 0.0)
    stable_range_score = _stable_range_score(
        {
            "sum_value": entry.sum_value,
            "span_value": entry.span_value,
            "ac_numeric": entry.ac_value,
            "first_last_sum": entry.first_last_sum,
            "max_gap": entry.max_gap,
            "min_gap": entry.min_gap,
        },
        stats,
    )
    weekday_trend_score = _weekday_trend_score_for_entry(entry, stats, repeat_count)
    return (
        entry.structural_score,
        frequency_score,
        omission_score,
        previous_consecutive_score,
        previous_overlap_score,
        previous_parity_shape_score,
        dynamic_parity_transition_score,
        previous_zone_shape_score,
        recent_neighbor_score,
        lagged_consecutive_score,
        recent_gap_shape_score,
        recent_sum_span_score,
        qian_kun_pattern_score,
        first_last_sum_score,
        span_trend_score,
        sum_trend_score,
        ac_trend_score,
        zone_ratio_score,
        big_small_ratio_score,
        parity_ratio_score,
        prime_composite_score,
        mod012_score,
        tail_distribution_score,
        sum_tail_score,
        red_omission_shape_score,
        sum_span_omission_score,
        consecutive_trend_score,
        repeat_trend_score,
        stable_range_score,
        weekday_trend_score,
        short_hot_frequency_score,
        long_omission_cooldown_score,
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
    dynamic_parity_transition_score = stats.parity_transition_score_by_even_count[6 - features["odd_count"]]
    zone_counts = (features["zone_1_count"], features["zone_2_count"], features["zone_3_count"])
    previous_zone_shape_score = 1 - sum(
        abs(candidate_count - previous_count)
        for candidate_count, previous_count in zip(zone_counts, stats.previous_zone_counts, strict=True)
    ) / 12
    gaps = tuple(right - left for left, right in zip(numbers, numbers[1:]))
    recent_neighbor_score = sum(stats.recent_neighbor_rate[number] for number in numbers) / 6
    lagged_consecutive_score = len(set(numbers) & stats.lagged_consecutive_number_set) / 6
    recent_gap_shape_score = max(
        0.0,
        1
        - sum(abs(gap - average) for gap, average in zip(gaps, stats.recent_average_gaps, strict=True))
        / (5 * 32),
    )
    recent_sum_span_score = (
        max(0.0, 1 - abs(sum(numbers) - stats.recent_average_sum) / 162)
        + max(0.0, 1 - abs((numbers[-1] - numbers[0]) - stats.recent_average_span) / 32)
    ) / 2
    qian_kun_pattern_score = _qian_kun_pattern_score(qian_kun_pattern(numbers), stats)
    shape_profile = _shape_profile(numbers, previous_numbers=stats.previous_numbers)
    weekday_trend_score = _profile_weekday_trend_score(shape_profile, stats)
    return (
        structural_score,
        sum(stats.frequency_rate[number] for number in numbers),
        sum(stats.omission_rate[number] for number in numbers) / 6,
        previous_consecutive_score,
        previous_overlap_score,
        previous_parity_shape_score,
        dynamic_parity_transition_score,
        previous_zone_shape_score,
        recent_neighbor_score,
        lagged_consecutive_score,
        recent_gap_shape_score,
        recent_sum_span_score,
        qian_kun_pattern_score,
        _profile_score("first_last_sum", shape_profile, stats),
        _profile_score("span_bucket", shape_profile, stats),
        _profile_score("sum_bucket", shape_profile, stats),
        _profile_score("ac_value", shape_profile, stats),
        _profile_score("zone_signature", shape_profile, stats),
        _profile_score("big_count", shape_profile, stats),
        _profile_score("even_count", shape_profile, stats),
        _profile_score("prime_count", shape_profile, stats),
        _profile_score("mod012_signature", shape_profile, stats),
        _profile_score("tail_unique_count", shape_profile, stats),
        _profile_score("sum_tail", shape_profile, stats),
        _red_omission_shape_score(numbers, stats),
        _sum_span_omission_score(shape_profile, stats),
        _profile_score("consecutive_pair_count", shape_profile, stats),
        _profile_score("repeat_count", shape_profile, stats),
        _stable_range_score(shape_profile, stats),
        weekday_trend_score,
        sum(stats.recent_frequency_rate[number] for number in numbers) / 6,
        max(0.0, min(1.0, 1 - sum(stats.recent_omission_pressure[number] ** 1.5 for number in numbers) / 6)),
    )


def score_from_components(components: ScoreComponents, config: FrequencyRankerConfig) -> float:
    (
        structural_score,
        frequency_score,
        omission_score,
        previous_consecutive_score,
        previous_overlap_score,
        previous_parity_shape_score,
        dynamic_parity_transition_score,
        previous_zone_shape_score,
        recent_neighbor_score,
        lagged_consecutive_score,
        recent_gap_shape_score,
        recent_sum_span_score,
        qian_kun_pattern_score,
        first_last_sum_score,
        span_trend_score,
        sum_trend_score,
        ac_trend_score,
        zone_ratio_score,
        big_small_ratio_score,
        parity_ratio_score,
        prime_composite_score,
        mod012_score,
        tail_distribution_score,
        sum_tail_score,
        red_omission_shape_score,
        sum_span_omission_score,
        consecutive_trend_score,
        repeat_trend_score,
        stable_range_score,
        weekday_trend_score,
        short_hot_frequency_score,
        long_omission_cooldown_score,
    ) = components
    return round(
        config.structural_weight * structural_score
        + config.frequency_weight * frequency_score
        + config.omission_weight * omission_score
        + config.previous_consecutive_weight * previous_consecutive_score
        + config.previous_overlap_weight * previous_overlap_score
        + config.previous_parity_shape_weight * previous_parity_shape_score
        + config.dynamic_parity_transition_weight * dynamic_parity_transition_score
        + config.previous_zone_shape_weight * previous_zone_shape_score
        + config.recent_neighbor_weight * recent_neighbor_score
        + config.lagged_consecutive_weight * lagged_consecutive_score
        + config.recent_gap_shape_weight * recent_gap_shape_score
        + config.recent_sum_span_weight * recent_sum_span_score
        + config.qian_kun_pattern_weight * qian_kun_pattern_score
        + config.first_last_sum_weight * first_last_sum_score
        + config.span_trend_weight * span_trend_score
        + config.sum_trend_weight * sum_trend_score
        + config.ac_trend_weight * ac_trend_score
        + config.zone_ratio_weight * zone_ratio_score
        + config.big_small_ratio_weight * big_small_ratio_score
        + config.parity_ratio_weight * parity_ratio_score
        + config.prime_composite_weight * prime_composite_score
        + config.mod012_weight * mod012_score
        + config.tail_distribution_weight * tail_distribution_score
        + config.sum_tail_weight * sum_tail_score
        + config.red_omission_shape_weight * red_omission_shape_score
        + config.sum_span_omission_weight * sum_span_omission_score
        + config.consecutive_trend_weight * consecutive_trend_score
        + config.repeat_trend_weight * repeat_trend_score
        + config.stable_range_weight * stable_range_score
        + config.weekday_trend_weight * weekday_trend_score
        + config.short_hot_frequency_weight * short_hot_frequency_score
        + config.long_omission_cooldown_weight * long_omission_cooldown_score,
        8,
    )


def _qian_kun_pattern_score(pattern: str, stats: FrequencyStats) -> float:
    history_score = stats.qian_kun_pattern_rate.get(pattern, 0.0)
    if not stats.recent_qian_kun_patterns:
        return history_score
    recent_score = max(qian_kun_similarity(pattern, recent_pattern) for recent_pattern in stats.recent_qian_kun_patterns)
    return (history_score + recent_score) / 2


def _profile_weekday_trend_score(profile: dict[str, object], stats: FrequencyStats) -> float:
    if stats.target_weekday is None or not stats.weekday_profile_rates:
        return 0.0
    keys = (
        "first_last_sum",
        "span_bucket",
        "sum_bucket",
        "ac_value",
        "zone_signature",
        "big_count",
        "even_count",
        "prime_count",
        "mod012_signature",
        "tail_unique_count",
        "sum_tail",
        "consecutive_pair_count",
        "repeat_count",
    )
    return sum(stats.weekday_profile_rates.get(key, {}).get(profile[key], 0.0) for key in keys) / len(keys)


def _weekday_trend_score_for_entry(entry: RankedUniverseEntry, stats: FrequencyStats, repeat_count: int) -> float:
    profile = {
        "first_last_sum": entry.first_last_sum,
        "span_bucket": entry.span_bucket,
        "sum_bucket": entry.sum_bucket,
        "ac_value": entry.ac_value,
        "zone_signature": entry.zone_counts,
        "big_count": entry.big_count,
        "even_count": entry.even_count,
        "prime_count": entry.prime_count,
        "mod012_signature": entry.mod012_counts,
        "tail_unique_count": entry.tail_unique_count,
        "sum_tail": entry.sum_tail,
        "consecutive_pair_count": entry.consecutive_pair_count,
        "repeat_count": repeat_count,
    }
    return _profile_weekday_trend_score(profile, stats)


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
    train_history: list[HistoryDraw],
    config: FrequencyRankerConfig,
    target_draw_date: date | None = None,
    universe: Iterable[tuple[int, ...]] | None = None,
    ranked_universe: list[RankedUniverseEntry] | None = None,
    workers: int = 1,
    pool: Pool | None = None,
) -> tuple[int, float]:
    stats = train_frequency_stats(train_history, target_draw_date=target_draw_date)
    target_score = score_frequency_candidate(target_numbers, stats, config)["score"]
    better = 0
    equal_before = 0
    entries = ranked_universe or build_ranked_universe(universe)
    if is_excluded_red_combination(target_numbers):
        return len(entries) + 1, target_score
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
    train_history: list[HistoryDraw],
    configs: tuple[FrequencyRankerConfig, ...],
    ranked_universe: list[RankedUniverseEntry],
    target_draw_date: date | None = None,
    workers: int = 1,
    pool: Pool | None = None,
) -> list[tuple[int, float]]:
    stats = train_frequency_stats(train_history, target_draw_date=target_draw_date)
    target_components = score_components_for_numbers(target_numbers, stats)
    target_scores = tuple(score_from_components(target_components, config) for config in configs)
    if is_excluded_red_combination(target_numbers):
        excluded_rank = len(ranked_universe) + 1
        return [(excluded_rank, target_scores[index]) for index in range(len(configs))]
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
    train_history: list[HistoryDraw],
    configs: tuple[FrequencyRankerConfig, ...],
    ranked_universe: list[RankedUniverseEntry],
    target_draw_date: date | None = None,
    workers: int = 1,
    pool: Pool | None = None,
) -> list[tuple[int, float, RedFiveMatch | None]]:
    stats = train_frequency_stats(train_history, target_draw_date=target_draw_date)
    target_components = score_components_for_numbers(target_numbers, stats)
    target_scores = tuple(score_from_components(target_components, config) for config in configs)
    target_excluded = is_excluded_red_combination(target_numbers)
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
        target_rank = len(ranked_universe) + 1 if target_excluded else better[index] + equal_before[index] + 1
        results.append((target_rank, target_score, match))
    return results


def rank_target_structural(
    *,
    target_numbers: tuple[int, ...],
    ranked_universe: list[RankedUniverseEntry],
) -> tuple[int, float]:
    target_score = round(score_numbers(target_numbers)["score"], 8)
    if is_excluded_red_combination(target_numbers):
        return len(ranked_universe) + 1, target_score
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
    history: list[HistoryDraw],
    top_n: int,
    config: FrequencyRankerConfig,
    target_draw_date: date | None = None,
    universe: Iterable[tuple[int, ...]] | None = None,
    ranked_universe: list[RankedUniverseEntry] | None = None,
    workers: int = 1,
    pool: Pool | None = None,
) -> list[tuple[int, tuple[int, ...], float]]:
    resolved_target_draw_date = target_draw_date or infer_next_ssq_draw_date(history)
    stats = train_frequency_stats(history, target_draw_date=resolved_target_draw_date)
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


def _materialize_universe(universe: Iterable[tuple[int, ...]] | None) -> list[tuple[int, ...]]:
    return [tuple(int(number) for number in numbers) for numbers in (universe or iter_ssq_red_combinations())]


def _universe_fingerprint(combinations: list[tuple[int, ...]]) -> str:
    digest = sha256()
    for numbers in combinations:
        digest.update(bytes(numbers))
        digest.update(b"|")
    digest.update(str(len(combinations)).encode("ascii"))
    return digest.hexdigest()


def _matrix_cache_key(combinations: list[tuple[int, ...]]) -> str:
    payload = ":".join(
        (
            FEATURE_SCHEMA_VERSION,
            FILTER_RULE_VERSION,
            str(len(combinations)),
            _universe_fingerprint(combinations),
        )
    )
    return sha256(payload.encode("utf-8")).hexdigest()[:24]


def _qian_kun_code(numbers: tuple[int, ...]) -> int:
    code = 0
    for index, number in enumerate(numbers):
        code |= (number % 2) << (5 - index)
    return code


def _tuple_code(values: tuple[int, int, int]) -> int:
    return values[0] * 49 + values[1] * 7 + values[2]


def _dense_lookup(
    rates: dict[object, float],
    *,
    size: int,
    default: float = 0.0,
    encoder: Callable[[object], int] | None = None,
) -> np.ndarray:
    lookup = np.full(size, default, dtype=np.float64)
    for raw_key, value in rates.items():
        key = encoder(raw_key) if encoder is not None else int(raw_key)  # type: ignore[arg-type]
        if 0 <= key < size:
            lookup[key] = float(value)
    return lookup


def _number_lookup(rates: dict[int, float]) -> np.ndarray:
    lookup = np.zeros(34, dtype=np.float64)
    for number, value in rates.items():
        if 1 <= int(number) <= 33:
            lookup[int(number)] = float(value)
    return lookup


def _qian_kun_lookup(stats: FrequencyStats) -> np.ndarray:
    lookup = np.zeros(64, dtype=np.float64)
    for pattern, value in stats.qian_kun_pattern_rate.items():
        lookup[int(pattern, 2)] = float(value)
    return lookup


def _weekday_profile_lookup(stats: FrequencyStats, key: str, *, size: int, encoder: Callable[[object], int] | None = None) -> np.ndarray:
    return _dense_lookup(stats.weekday_profile_rates.get(key, {}), size=size, encoder=encoder)


def _load_matrix_cache(cache_path: Path, *, cache_key: str) -> RankedUniverseMatrix | None:
    started = time.time()
    try:
        data = np.load(cache_path, allow_pickle=False)
    except OSError:
        return None
    try:
        metadata = json.loads(str(data["metadata_json"].item()))
        if (
            metadata.get("cache_key") != cache_key
            or metadata.get("feature_schema_version") != FEATURE_SCHEMA_VERSION
            or metadata.get("filter_rule_version") != FILTER_RULE_VERSION
        ):
            return None
        metadata.update(
            {
                "cache_hit": True,
                "cache_path": str(cache_path),
                "build_seconds": round(time.time() - started, 3),
                "backend": "numpy_matrix",
            }
        )
        return RankedUniverseMatrix(
            numbers=data["numbers"],
            structural_score=data["structural_score"],
            consecutive_pair_count=data["consecutive_pair_count"],
            odd_count=data["odd_count"],
            zone_counts=data["zone_counts"],
            gaps=data["gaps"],
            sum_value=data["sum_value"],
            span_value=data["span_value"],
            qian_kun_code=data["qian_kun_code"],
            first_last_sum=data["first_last_sum"],
            sum_bucket=data["sum_bucket"],
            span_bucket=data["span_bucket"],
            ac_value=data["ac_value"],
            big_count=data["big_count"],
            even_count=data["even_count"],
            prime_count=data["prime_count"],
            mod012_counts=data["mod012_counts"],
            tail_unique_count=data["tail_unique_count"],
            sum_tail=data["sum_tail"],
            max_gap=data["max_gap"],
            min_gap=data["min_gap"],
            number_presence=data["number_presence"],
            cache_info=metadata,
        )
    finally:
        data.close()


def _write_matrix_cache(cache_path: Path, matrix: RankedUniverseMatrix) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = dict(matrix.cache_info)
    metadata["cache_hit"] = False
    np.savez(
        cache_path,
        metadata_json=np.array(json.dumps(metadata, sort_keys=True)),
        numbers=matrix.numbers,
        structural_score=matrix.structural_score,
        consecutive_pair_count=matrix.consecutive_pair_count,
        odd_count=matrix.odd_count,
        zone_counts=matrix.zone_counts,
        gaps=matrix.gaps,
        sum_value=matrix.sum_value,
        span_value=matrix.span_value,
        qian_kun_code=matrix.qian_kun_code,
        first_last_sum=matrix.first_last_sum,
        sum_bucket=matrix.sum_bucket,
        span_bucket=matrix.span_bucket,
        ac_value=matrix.ac_value,
        big_count=matrix.big_count,
        even_count=matrix.even_count,
        prime_count=matrix.prime_count,
        mod012_counts=matrix.mod012_counts,
        tail_unique_count=matrix.tail_unique_count,
        sum_tail=matrix.sum_tail,
        max_gap=matrix.max_gap,
        min_gap=matrix.min_gap,
        number_presence=matrix.number_presence,
    )


def _matrix_from_combinations(
    combinations: list[tuple[int, ...]],
    *,
    cache_key: str,
    cache_path: Path | None,
    started: float,
) -> RankedUniverseMatrix:
    rows: list[tuple[int, ...]] = []
    structural_scores: list[float] = []
    consecutive_pair_counts: list[int] = []
    odd_counts: list[int] = []
    zone_counts: list[tuple[int, int, int]] = []
    gaps_list: list[tuple[int, int, int, int, int]] = []
    sum_values: list[int] = []
    span_values: list[int] = []
    qian_kun_codes: list[int] = []
    first_last_sums: list[int] = []
    sum_buckets: list[int] = []
    span_buckets: list[int] = []
    ac_values: list[int] = []
    big_counts: list[int] = []
    even_counts: list[int] = []
    prime_counts: list[int] = []
    mod012_values: list[tuple[int, int, int]] = []
    tail_unique_counts: list[int] = []
    sum_tails: list[int] = []
    max_gaps: list[int] = []
    min_gaps: list[int] = []

    for numbers in combinations:
        features = calculate_red_ball_features(numbers)
        if int(features["max_consecutive_run"]) >= 5 or any(
            int(features[key]) == 6
            for key in ("zone_1_count", "zone_2_count", "zone_3_count")
        ):
            continue
        gaps = tuple(right - left for left, right in zip(numbers, numbers[1:]))
        tails = [number % 10 for number in numbers]
        pairwise_distances = {right - left for index, left in enumerate(numbers) for right in numbers[index + 1:]}
        rows.append(numbers)
        structural_scores.append(float(score_numbers(numbers)["score"]))
        consecutive_pair_counts.append(int(features["consecutive_pair_count"]))
        odd_counts.append(int(features["odd_count"]))
        zone_counts.append((
            int(features["zone_1_count"]),
            int(features["zone_2_count"]),
            int(features["zone_3_count"]),
        ))
        gaps_list.append(gaps)  # type: ignore[arg-type]
        sum_value = int(features["sum_value"])
        span_value = int(features["span_value"])
        sum_values.append(sum_value)
        span_values.append(span_value)
        qian_kun_codes.append(_qian_kun_code(numbers))
        first_last_sums.append(numbers[0] + numbers[-1])
        sum_buckets.append(sum_value // 10)
        span_buckets.append(span_value // 3)
        ac_values.append(max(0, len(pairwise_distances) - 5))
        big_counts.append(int(features["big_count"]))
        even_counts.append(int(features["even_count"]))
        prime_counts.append(sum(1 for number in numbers if number in PRIME_NUMBERS))
        mod012_values.append((
            sum(1 for number in numbers if number % 3 == 0),
            sum(1 for number in numbers if number % 3 == 1),
            sum(1 for number in numbers if number % 3 == 2),
        ))
        tail_unique_counts.append(len(set(tails)))
        sum_tails.append(sum_value % 10)
        max_gaps.append(max(gaps))
        min_gaps.append(min(gaps))

    numbers_array = np.array(rows, dtype=np.uint8).reshape((-1, 6))
    number_presence = np.zeros((len(numbers_array), 34), dtype=bool)
    if len(numbers_array):
        number_presence[np.arange(len(numbers_array))[:, None], numbers_array] = True
    cache_info = {
        "backend": "numpy_matrix",
        "cache_key": cache_key,
        "cache_path": str(cache_path) if cache_path else "",
        "cache_hit": False,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "filter_rule_version": FILTER_RULE_VERSION,
        "source_count": len(combinations),
        "filtered_count": len(numbers_array),
        "excluded_count": len(combinations) - len(numbers_array),
        "build_seconds": round(time.time() - started, 3),
        "red5_rank_mode": "score_vector_reuse",
    }
    return RankedUniverseMatrix(
        numbers=numbers_array,
        structural_score=np.array(structural_scores, dtype=np.float64),
        consecutive_pair_count=np.array(consecutive_pair_counts, dtype=np.uint8),
        odd_count=np.array(odd_counts, dtype=np.uint8),
        zone_counts=np.array(zone_counts, dtype=np.uint8).reshape((-1, 3)),
        gaps=np.array(gaps_list, dtype=np.uint8).reshape((-1, 5)),
        sum_value=np.array(sum_values, dtype=np.uint16),
        span_value=np.array(span_values, dtype=np.uint8),
        qian_kun_code=np.array(qian_kun_codes, dtype=np.uint8),
        first_last_sum=np.array(first_last_sums, dtype=np.uint8),
        sum_bucket=np.array(sum_buckets, dtype=np.uint8),
        span_bucket=np.array(span_buckets, dtype=np.uint8),
        ac_value=np.array(ac_values, dtype=np.uint8),
        big_count=np.array(big_counts, dtype=np.uint8),
        even_count=np.array(even_counts, dtype=np.uint8),
        prime_count=np.array(prime_counts, dtype=np.uint8),
        mod012_counts=np.array(mod012_values, dtype=np.uint8).reshape((-1, 3)),
        tail_unique_count=np.array(tail_unique_counts, dtype=np.uint8),
        sum_tail=np.array(sum_tails, dtype=np.uint8),
        max_gap=np.array(max_gaps, dtype=np.uint8),
        min_gap=np.array(min_gaps, dtype=np.uint8),
        number_presence=number_presence,
        cache_info=cache_info,
    )


def build_ranked_universe(
    universe: Iterable[tuple[int, ...]] | None = None,
    *,
    cache_dir: Path | None = DEFAULT_MATRIX_CACHE_DIR,
    use_cache: bool | None = None,
) -> RankedUniverseMatrix:
    started = time.time()
    combinations = _materialize_universe(universe)
    cache_enabled = (use_cache if use_cache is not None else len(combinations) >= 100_000) and cache_dir is not None
    cache_key = _matrix_cache_key(combinations)
    cache_path = (cache_dir / f"ranked-universe-{cache_key}.npz") if cache_enabled and cache_dir else None
    if cache_path is not None:
        cached = _load_matrix_cache(cache_path, cache_key=cache_key)
        if cached is not None:
            return cached
    matrix = _matrix_from_combinations(combinations, cache_key=cache_key, cache_path=cache_path, started=started)
    if cache_path is not None:
        _write_matrix_cache(cache_path, matrix)
    return matrix


def create_worker_pool(worker_count: int, ranked_universe: RankedUniverseMatrix) -> Pool | None:
    global _WORKER_UNIVERSE
    _WORKER_UNIVERSE = ranked_universe
    return None


def _config_weight_matrix(configs: tuple[FrequencyRankerConfig, ...]) -> np.ndarray:
    return np.array(
        [[float(getattr(config, field)) for field in CONFIG_WEIGHT_FIELDS] for config in configs],
        dtype=np.float64,
    )


def _lex_less_than(numbers: np.ndarray, target_numbers: tuple[int, ...]) -> np.ndarray:
    target = np.array(target_numbers, dtype=np.uint8)
    less = np.zeros(numbers.shape[0], dtype=bool)
    equal_prefix = np.ones(numbers.shape[0], dtype=bool)
    for column in range(6):
        less |= equal_prefix & (numbers[:, column] < target[column])
        equal_prefix &= numbers[:, column] == target[column]
    return less


def _components_for_matrix(
    matrix: RankedUniverseMatrix,
    stats: FrequencyStats,
    *,
    start: int = 0,
    end: int | None = None,
) -> np.ndarray:
    stop = len(matrix) if end is None else end
    numbers = matrix.numbers[start:stop]
    presence = matrix.number_presence[start:stop]
    frequency_lookup = _number_lookup(stats.frequency_rate)
    recent_frequency_lookup = _number_lookup(stats.recent_frequency_rate)
    omission_lookup = _number_lookup(stats.omission_rate)
    recent_omission_pressure_lookup = _number_lookup(stats.recent_omission_pressure)
    neighbor_lookup = _number_lookup(stats.recent_neighbor_rate)

    frequency_score = frequency_lookup[numbers].sum(axis=1)
    short_hot_frequency_score = recent_frequency_lookup[numbers].mean(axis=1)
    omission_score = omission_lookup[numbers].mean(axis=1)
    long_omission_cooldown_score = np.clip(
        1 - np.power(recent_omission_pressure_lookup[numbers], 1.5).mean(axis=1),
        0.0,
        1.0,
    )
    candidate_consecutive_score = np.minimum(matrix.consecutive_pair_count[start:stop], 5).astype(np.float64) / 5
    if stats.previous_consecutive_pair_count > 0:
        previous_consecutive_score = candidate_consecutive_score
    else:
        previous_consecutive_score = 1 - candidate_consecutive_score
    repeat_count = presence[:, list(stats.previous_number_set)].sum(axis=1) if stats.previous_number_set else np.zeros(stop - start, dtype=np.uint8)
    previous_overlap_score = repeat_count.astype(np.float64) / 6
    previous_parity_shape_score = 1 - np.abs(matrix.odd_count[start:stop].astype(np.float64) - stats.previous_odd_count) / 6
    parity_lookup = np.array(stats.parity_transition_score_by_even_count, dtype=np.float64)
    dynamic_parity_transition_score = parity_lookup[matrix.even_count[start:stop]]
    previous_zone_shape_score = 1 - np.abs(
        matrix.zone_counts[start:stop].astype(np.float64) - np.array(stats.previous_zone_counts, dtype=np.float64),
    ).sum(axis=1) / 12
    recent_neighbor_score = neighbor_lookup[numbers].mean(axis=1)
    if stats.lagged_consecutive_number_set:
        lagged_consecutive_score = presence[:, list(stats.lagged_consecutive_number_set)].sum(axis=1) / 6
    else:
        lagged_consecutive_score = np.zeros(stop - start, dtype=np.float64)
    recent_gap_shape_score = np.maximum(
        0.0,
        1 - np.abs(matrix.gaps[start:stop].astype(np.float64) - np.array(stats.recent_average_gaps, dtype=np.float64)).sum(axis=1) / (5 * 32),
    )
    recent_sum_span_score = (
        np.maximum(0.0, 1 - np.abs(matrix.sum_value[start:stop].astype(np.float64) - stats.recent_average_sum) / 162)
        + np.maximum(0.0, 1 - np.abs(matrix.span_value[start:stop].astype(np.float64) - stats.recent_average_span) / 32)
    ) / 2

    qian_history = _qian_kun_lookup(stats)
    qian_codes = matrix.qian_kun_code[start:stop]
    qian_kun_pattern_score = qian_history[qian_codes]
    if stats.recent_qian_kun_patterns:
        recent_codes = np.array([int(pattern, 2) for pattern in stats.recent_qian_kun_patterns], dtype=np.uint8)
        qian_kun_pattern_score = (qian_kun_pattern_score + QIAN_KUN_SIMILARITY[qian_codes][:, recent_codes].max(axis=1)) / 2

    first_last_sum_score = _dense_lookup(stats.shape_profile_rates.get("first_last_sum", {}), size=67)[matrix.first_last_sum[start:stop]]
    span_trend_score = _dense_lookup(stats.shape_profile_rates.get("span_bucket", {}), size=12)[matrix.span_bucket[start:stop]]
    sum_trend_score = _dense_lookup(stats.shape_profile_rates.get("sum_bucket", {}), size=20)[matrix.sum_bucket[start:stop]]
    ac_trend_score = _dense_lookup(stats.shape_profile_rates.get("ac_value", {}), size=16)[matrix.ac_value[start:stop]]
    zone_ratio_score = _dense_lookup(
        stats.shape_profile_rates.get("zone_signature", {}),
        size=343,
        encoder=lambda key: _tuple_code(tuple(key)),  # type: ignore[arg-type]
    )[(matrix.zone_counts[start:stop, 0] * 49 + matrix.zone_counts[start:stop, 1] * 7 + matrix.zone_counts[start:stop, 2]).astype(np.uint16)]
    big_small_ratio_score = _dense_lookup(stats.shape_profile_rates.get("big_count", {}), size=7)[matrix.big_count[start:stop]]
    parity_ratio_score = _dense_lookup(stats.shape_profile_rates.get("even_count", {}), size=7)[matrix.even_count[start:stop]]
    prime_composite_score = _dense_lookup(stats.shape_profile_rates.get("prime_count", {}), size=7)[matrix.prime_count[start:stop]]
    mod012_codes = (matrix.mod012_counts[start:stop, 0] * 49 + matrix.mod012_counts[start:stop, 1] * 7 + matrix.mod012_counts[start:stop, 2]).astype(np.uint16)
    mod012_score = _dense_lookup(
        stats.shape_profile_rates.get("mod012_signature", {}),
        size=343,
        encoder=lambda key: _tuple_code(tuple(key)),  # type: ignore[arg-type]
    )[mod012_codes]
    tail_distribution_score = _dense_lookup(stats.shape_profile_rates.get("tail_unique_count", {}), size=7)[matrix.tail_unique_count[start:stop]]
    sum_tail_score = _dense_lookup(stats.shape_profile_rates.get("sum_tail", {}), size=10)[matrix.sum_tail[start:stop]]
    red_omission_shape_score = np.maximum(0.0, 1 - np.abs(omission_score - stats.recent_average_omission))
    sum_span_omission_score = (
        _dense_lookup(stats.sum_bucket_omission_rate, size=20, default=1.0)[matrix.sum_bucket[start:stop]]
        + _dense_lookup(stats.span_bucket_omission_rate, size=12, default=1.0)[matrix.span_bucket[start:stop]]
    ) / 2
    consecutive_trend_score = _dense_lookup(stats.shape_profile_rates.get("consecutive_pair_count", {}), size=6)[matrix.consecutive_pair_count[start:stop]]
    repeat_trend_score = _dense_lookup(stats.shape_profile_rates.get("repeat_count", {}), size=7)[repeat_count]

    stable_range_score = np.ones(stop - start, dtype=np.float64)
    if stats.stable_ranges:
        stable_total = np.zeros(stop - start, dtype=np.float64)
        stable_count = 0
        stable_sources = {
            "sum_value": matrix.sum_value[start:stop].astype(np.float64),
            "span_value": matrix.span_value[start:stop].astype(np.float64),
            "ac_numeric": matrix.ac_value[start:stop].astype(np.float64),
            "first_last_sum": matrix.first_last_sum[start:stop].astype(np.float64),
            "max_gap": matrix.max_gap[start:stop].astype(np.float64),
            "min_gap": matrix.min_gap[start:stop].astype(np.float64),
        }
        for key, values in stable_sources.items():
            lower, upper = stats.stable_ranges.get(key, (0.0, 0.0))
            width = max(upper - lower, 1.0)
            distance = np.where(values < lower, lower - values, np.where(values > upper, values - upper, 0.0))
            stable_total += np.where(distance == 0, 1.0, np.maximum(0.0, 1 - distance / width))
            stable_count += 1
        stable_range_score = stable_total / stable_count

    if stats.target_weekday is None or not stats.weekday_profile_rates:
        weekday_trend_score = np.zeros(stop - start, dtype=np.float64)
    else:
        weekday_trend_score = (
            _weekday_profile_lookup(stats, "first_last_sum", size=67)[matrix.first_last_sum[start:stop]]
            + _weekday_profile_lookup(stats, "span_bucket", size=12)[matrix.span_bucket[start:stop]]
            + _weekday_profile_lookup(stats, "sum_bucket", size=20)[matrix.sum_bucket[start:stop]]
            + _weekday_profile_lookup(stats, "ac_value", size=16)[matrix.ac_value[start:stop]]
            + _weekday_profile_lookup(stats, "zone_signature", size=343, encoder=lambda key: _tuple_code(tuple(key)))[  # type: ignore[arg-type]
                (matrix.zone_counts[start:stop, 0] * 49 + matrix.zone_counts[start:stop, 1] * 7 + matrix.zone_counts[start:stop, 2]).astype(np.uint16)
            ]
            + _weekday_profile_lookup(stats, "big_count", size=7)[matrix.big_count[start:stop]]
            + _weekday_profile_lookup(stats, "even_count", size=7)[matrix.even_count[start:stop]]
            + _weekday_profile_lookup(stats, "prime_count", size=7)[matrix.prime_count[start:stop]]
            + _weekday_profile_lookup(stats, "mod012_signature", size=343, encoder=lambda key: _tuple_code(tuple(key)))[mod012_codes]  # type: ignore[arg-type]
            + _weekday_profile_lookup(stats, "tail_unique_count", size=7)[matrix.tail_unique_count[start:stop]]
            + _weekday_profile_lookup(stats, "sum_tail", size=10)[matrix.sum_tail[start:stop]]
            + _weekday_profile_lookup(stats, "consecutive_pair_count", size=6)[matrix.consecutive_pair_count[start:stop]]
            + _weekday_profile_lookup(stats, "repeat_count", size=7)[repeat_count]
        ) / 13

    return np.column_stack(
        (
            matrix.structural_score[start:stop],
            frequency_score,
            omission_score,
            previous_consecutive_score,
            previous_overlap_score,
            previous_parity_shape_score,
            dynamic_parity_transition_score,
            previous_zone_shape_score,
            recent_neighbor_score,
            lagged_consecutive_score,
            recent_gap_shape_score,
            recent_sum_span_score,
            qian_kun_pattern_score,
            first_last_sum_score,
            span_trend_score,
            sum_trend_score,
            ac_trend_score,
            zone_ratio_score,
            big_small_ratio_score,
            parity_ratio_score,
            prime_composite_score,
            mod012_score,
            tail_distribution_score,
            sum_tail_score,
            red_omission_shape_score,
            sum_span_omission_score,
            consecutive_trend_score,
            repeat_trend_score,
            stable_range_score,
            weekday_trend_score,
            short_hot_frequency_score,
            long_omission_cooldown_score,
        )
    )


def _score_matrix(
    matrix: RankedUniverseMatrix,
    stats: FrequencyStats,
    configs: tuple[FrequencyRankerConfig, ...],
) -> np.ndarray:
    components = _components_for_matrix(matrix, stats)
    return np.round(components @ _config_weight_matrix(configs).T, 8)


def score_config_grid(
    *,
    train_history: list[HistoryDraw],
    configs: tuple[FrequencyRankerConfig, ...],
    ranked_universe: RankedUniverseMatrix,
    target_draw_date: date | None = None,
) -> np.ndarray:
    """Score one fixed universe for several configs under the same history boundary."""
    stats = train_frequency_stats(train_history, target_draw_date=target_draw_date)
    return _score_matrix(ranked_universe, stats, configs)


def _target_scores(target_numbers: tuple[int, ...], stats: FrequencyStats, configs: tuple[FrequencyRankerConfig, ...]) -> tuple[float, ...]:
    components = score_components_for_numbers(target_numbers, stats)
    return tuple(score_from_components(components, config) for config in configs)


def _rank_targets_from_scores(
    *,
    matrix: RankedUniverseMatrix,
    scores: np.ndarray,
    target_numbers: tuple[int, ...],
    target_scores: tuple[float, ...],
    target_excluded: bool,
) -> list[tuple[int, float]]:
    if target_excluded:
        return [(len(matrix) + 1, target_score) for target_score in target_scores]
    lex_less = _lex_less_than(matrix.numbers, target_numbers)
    target_array = np.array(target_scores, dtype=np.float64)
    better = (scores > target_array).sum(axis=0)
    equal_before = ((scores == target_array) & lex_less[:, None]).sum(axis=0)
    return [(int(better[index] + equal_before[index] + 1), float(target_scores[index])) for index in range(len(target_scores))]


def rank_target(
    *,
    target_numbers: tuple[int, ...],
    train_history: list[HistoryDraw],
    config: FrequencyRankerConfig,
    target_draw_date: date | None = None,
    universe: Iterable[tuple[int, ...]] | None = None,
    ranked_universe: RankedUniverseMatrix | None = None,
    workers: int = 1,
    pool: Pool | None = None,
) -> tuple[int, float]:
    return rank_target_grid(
        target_numbers=target_numbers,
        train_history=train_history,
        configs=(config,),
        ranked_universe=ranked_universe or build_ranked_universe(universe),
        target_draw_date=target_draw_date,
        workers=workers,
        pool=pool,
    )[0]


def rank_target_grid(
    *,
    target_numbers: tuple[int, ...],
    train_history: list[HistoryDraw],
    configs: tuple[FrequencyRankerConfig, ...],
    ranked_universe: RankedUniverseMatrix,
    target_draw_date: date | None = None,
    workers: int = 1,
    pool: Pool | None = None,
) -> list[tuple[int, float]]:
    stats = train_frequency_stats(train_history, target_draw_date=target_draw_date)
    target_scores = _target_scores(target_numbers, stats, configs)
    scores = _score_matrix(ranked_universe, stats, configs)
    return _rank_targets_from_scores(
        matrix=ranked_universe,
        scores=scores,
        target_numbers=target_numbers,
        target_scores=target_scores,
        target_excluded=is_excluded_red_combination(target_numbers),
    )


def rank_target_grid_with_red5(
    *,
    target_numbers: tuple[int, ...],
    train_history: list[HistoryDraw],
    configs: tuple[FrequencyRankerConfig, ...],
    ranked_universe: RankedUniverseMatrix,
    target_draw_date: date | None = None,
    workers: int = 1,
    pool: Pool | None = None,
) -> list[tuple[int, float, RedFiveMatch | None]]:
    stats = train_frequency_stats(train_history, target_draw_date=target_draw_date)
    target_scores = _target_scores(target_numbers, stats, configs)
    scores = _score_matrix(ranked_universe, stats, configs)
    target_ranks = _rank_targets_from_scores(
        matrix=ranked_universe,
        scores=scores,
        target_numbers=target_numbers,
        target_scores=target_scores,
        target_excluded=is_excluded_red_combination(target_numbers),
    )

    target_set = set(target_numbers)
    red5_mask = ranked_universe.number_presence[:, list(target_numbers)].sum(axis=1) == 5
    red5_indices = np.flatnonzero(red5_mask)
    results: list[tuple[int, float, RedFiveMatch | None]] = []
    for config_index, (target_rank, target_score) in enumerate(target_ranks):
        match = None
        if len(red5_indices):
            candidate_scores = scores[red5_indices, config_index]
            candidate_numbers = ranked_universe.numbers[red5_indices]
            order = np.lexsort(
                (
                    candidate_numbers[:, 5],
                    candidate_numbers[:, 4],
                    candidate_numbers[:, 3],
                    candidate_numbers[:, 2],
                    candidate_numbers[:, 1],
                    candidate_numbers[:, 0],
                    -candidate_scores,
                )
            )
            best_index = int(red5_indices[int(order[0])])
            best_numbers = tuple(int(number) for number in ranked_universe.numbers[best_index])
            best_score = float(scores[best_index, config_index])
            candidate_set = set(best_numbers)
            missing = sorted(target_set - candidate_set)
            extra = sorted(candidate_set - target_set)
            if len(missing) == 1 and len(extra) == 1:
                red5_better = int((scores[:, config_index] > best_score).sum())
                red5_equal_before = int(
                    ((scores[:, config_index] == best_score) & _lex_less_than(ranked_universe.numbers, best_numbers)).sum()
                )
                match = RedFiveMatch(
                    rank=red5_better + red5_equal_before + 1,
                    score=best_score,
                    numbers=best_numbers,
                    missing_number=missing[0],
                    extra_number=extra[0],
                )
        results.append((target_rank, target_score, match))
    return results


def rank_target_structural(
    *,
    target_numbers: tuple[int, ...],
    ranked_universe: RankedUniverseMatrix,
) -> tuple[int, float]:
    target_score = round(score_numbers(target_numbers)["score"], 8)
    if is_excluded_red_combination(target_numbers):
        return len(ranked_universe) + 1, target_score
    scores = np.round(ranked_universe.structural_score, 8)
    better = int((scores > target_score).sum())
    equal_before = int(((scores == target_score) & _lex_less_than(ranked_universe.numbers, target_numbers)).sum())
    return better + equal_before + 1, target_score


def _top_indices(scores: np.ndarray, matrix: RankedUniverseMatrix, top_n: int) -> np.ndarray:
    limit = min(top_n, len(scores))
    if limit <= 0:
        return np.array([], dtype=np.int64)
    if limit < len(scores):
        candidate_indices = np.argpartition(scores, -limit)[-limit:]
    else:
        candidate_indices = np.arange(len(scores))
    candidate_numbers = matrix.numbers[candidate_indices]
    order = np.lexsort(
        (
            candidate_numbers[:, 5],
            candidate_numbers[:, 4],
            candidate_numbers[:, 3],
            candidate_numbers[:, 2],
            candidate_numbers[:, 1],
            candidate_numbers[:, 0],
            -scores[candidate_indices],
        )
    )
    return candidate_indices[order]


def top_indices_for_scores(
    *,
    scores: np.ndarray,
    ranked_universe: RankedUniverseMatrix,
    top_n: int,
) -> np.ndarray:
    """Return deterministic score-ranked row indexes for an already scored universe."""
    if scores.ndim != 1 or len(scores) != len(ranked_universe):
        raise ValueError("scores must be a one-dimensional array matching ranked_universe")
    if not np.isfinite(scores).all():
        raise ValueError("scores must contain only finite values")
    return _top_indices(scores, ranked_universe, top_n)


def top_candidates_for_next(
    *,
    history: list[HistoryDraw],
    top_n: int,
    config: FrequencyRankerConfig,
    target_draw_date: date | None = None,
    universe: Iterable[tuple[int, ...]] | None = None,
    ranked_universe: RankedUniverseMatrix | None = None,
    workers: int = 1,
    pool: Pool | None = None,
) -> list[tuple[int, tuple[int, ...], float]]:
    if top_n < 1:
        raise ValueError("top_n must be at least 1")

    resolved_target_draw_date = target_draw_date or infer_next_ssq_draw_date(history)
    stats = train_frequency_stats(history, target_draw_date=resolved_target_draw_date)
    matrix = ranked_universe or build_ranked_universe(universe)
    scores = _score_matrix(matrix, stats, (config,))[:, 0]
    indices = _top_indices(scores, matrix, top_n)
    return [
        (rank, tuple(int(number) for number in matrix.numbers[index]), float(scores[index]))
        for rank, index in enumerate(indices, start=1)
    ]


def run_walk_forward(
    *,
    history: list[HistoryDraw],
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
    if top_n < 1:
        raise ValueError("top_n must be at least 1")
    if train_mode not in ("expanding", "rolling"):
        raise ValueError("train_mode must be 'expanding' or 'rolling'")
    if len(history) <= train_window:
        raise ValueError("history must be longer than train_window")

    cfg = config or FrequencyRankerConfig()
    as_of_issue = history_issue(history[-1])
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
            target_draw = history[target_index]
            issue = history_issue(target_draw)
            numbers = history_numbers(target_draw)
            rank, score = rank_target(
                target_numbers=numbers,
                train_history=train_history,
                config=cfg,
                target_draw_date=history_draw_date(target_draw),
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
            top_n=top_n,
            config=cfg,
            target_draw_date=infer_next_ssq_draw_date(history),
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
