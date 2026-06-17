from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from heapq import nlargest
import json
import multiprocessing as mp
import os
from multiprocessing.pool import Pool
from typing import Callable, Iterable, Literal

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

_WORKER_UNIVERSE: list["RankedUniverseEntry"] = []
DEFAULT_WORKERS = 16
ScoreComponents = tuple[float, ...]


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
    omission_score = sum(stats.omission_rate[number] for number in entry.numbers) / 6
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
        + config.weekday_trend_weight * weekday_trend_score,
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
            top_n=min(top_n, len(ranked_universe)),
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
