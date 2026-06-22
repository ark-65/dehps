from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import quantiles

from dehps.features.red_ball_features import calculate_red_ball_features
from dehps.features.qian_kun import qian_kun_pattern, qian_kun_similarity
from dehps.scoring.strategy import score_numbers

PRIME_NUMBERS = frozenset({2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31})
SSQ_DRAW_WEEKDAYS = frozenset({1, 3, 6})
SHORT_HOT_WINDOW = 12
RECENT_OMISSION_HORIZON = 60
HistoryDraw = tuple[str, tuple[int, ...]] | tuple[str, date | None, tuple[int, ...]]


@dataclass(frozen=True)
class NormalizedHistoryDraw:
    issue: str
    draw_date: date | None
    numbers: tuple[int, ...]


@dataclass(frozen=True)
class FrequencyRankerConfig:
    structural_weight: float = 0.40
    frequency_weight: float = 0.30
    omission_weight: float = 0.25
    previous_consecutive_weight: float = 0.05
    previous_overlap_weight: float = 0.00
    previous_parity_shape_weight: float = 0.00
    dynamic_parity_transition_weight: float = 0.00
    previous_zone_shape_weight: float = 0.00
    recent_neighbor_weight: float = 0.00
    lagged_consecutive_weight: float = 0.00
    recent_gap_shape_weight: float = 0.00
    recent_sum_span_weight: float = 0.00
    qian_kun_pattern_weight: float = 0.00
    first_last_sum_weight: float = 0.00
    span_trend_weight: float = 0.00
    sum_trend_weight: float = 0.00
    ac_trend_weight: float = 0.00
    zone_ratio_weight: float = 0.00
    big_small_ratio_weight: float = 0.00
    parity_ratio_weight: float = 0.00
    prime_composite_weight: float = 0.00
    mod012_weight: float = 0.00
    tail_distribution_weight: float = 0.00
    sum_tail_weight: float = 0.00
    red_omission_shape_weight: float = 0.00
    sum_span_omission_weight: float = 0.00
    consecutive_trend_weight: float = 0.00
    repeat_trend_weight: float = 0.00
    stable_range_weight: float = 0.00
    weekday_trend_weight: float = 0.00
    short_hot_frequency_weight: float = 0.00
    long_omission_cooldown_weight: float = 0.00


@dataclass(frozen=True)
class FrequencyStats:
    train_draws: int
    frequency_rate: dict[int, float]
    recent_frequency_rate: dict[int, float]
    omission_rate: dict[int, float]
    recent_omission_pressure: dict[int, float]
    previous_numbers: tuple[int, ...]
    previous_number_set: frozenset[int]
    previous_consecutive_pair_count: int
    previous_odd_count: int
    parity_transition_score_by_even_count: tuple[float, float, float, float, float, float, float]
    previous_zone_counts: tuple[int, int, int]
    recent_neighbor_rate: dict[int, float]
    lagged_consecutive_number_set: frozenset[int]
    recent_average_gaps: tuple[float, float, float, float, float]
    recent_average_sum: float
    recent_average_span: float
    qian_kun_pattern_rate: dict[str, float]
    recent_qian_kun_patterns: tuple[str, ...]
    shape_profile_rates: dict[str, dict[object, float]]
    sum_bucket_omission_rate: dict[int, float]
    span_bucket_omission_rate: dict[int, float]
    recent_average_omission: float
    stable_ranges: dict[str, tuple[float, float]]
    target_weekday: int | None
    weekday_profile_rates: dict[str, dict[object, float]]


def history_issue(draw: HistoryDraw) -> str:
    return draw[0]


def history_draw_date(draw: HistoryDraw) -> date | None:
    return draw[1] if len(draw) == 3 else None


def history_numbers(draw: HistoryDraw) -> tuple[int, ...]:
    return tuple(draw[2] if len(draw) == 3 else draw[1])


def normalize_history_draw(draw: HistoryDraw) -> NormalizedHistoryDraw:
    return NormalizedHistoryDraw(
        issue=history_issue(draw),
        draw_date=history_draw_date(draw),
        numbers=history_numbers(draw),
    )


def next_ssq_draw_date(after_date: date) -> date:
    for offset in range(1, 8):
        candidate = after_date + timedelta(days=offset)
        if candidate.weekday() in SSQ_DRAW_WEEKDAYS:
            return candidate
    raise RuntimeError("failed to resolve next SSQ draw date")


def infer_next_ssq_draw_date(history: list[HistoryDraw]) -> date | None:
    for draw in reversed(history):
        draw_date = history_draw_date(draw)
        if draw_date is not None:
            return next_ssq_draw_date(draw_date)
    return None


def train_frequency_stats(history: list[HistoryDraw], *, target_draw_date: date | None = None) -> FrequencyStats:
    if not history:
        raise ValueError("history must contain at least one draw")

    records = [normalize_history_draw(draw) for draw in history]
    counts = {number: 0 for number in range(1, 34)}
    last_seen_index = {number: -1 for number in range(1, 34)}
    for index, record in enumerate(records):
        numbers = record.numbers
        for number in numbers:
            counts[number] += 1
            last_seen_index[number] = index

    train_draws = len(records)
    denominator = train_draws * 6
    max_omission = max(1, train_draws)
    omission_rate = {
        number: (train_draws - 1 - last_seen_index[number]) / max_omission
        if last_seen_index[number] >= 0
        else 1.0
        for number in range(1, 34)
    }
    previous_numbers = records[-1].numbers
    previous_features = calculate_red_ball_features(previous_numbers)
    parity_transition_score_by_even_count = _parity_transition_score_by_even_count(records)
    recent_numbers = [record.numbers for record in records[-3:]]
    shape_numbers = [record.numbers for record in records[-20:]]
    qian_kun_patterns = [qian_kun_pattern(record.numbers) for record in records]
    shape_profiles = [
        _shape_profile(record.numbers, previous_numbers=records[index - 1].numbers if index > 0 else None)
        for index, record in enumerate(records)
    ]
    recent_shape_profiles = shape_profiles[-20:]
    target_weekday = target_draw_date.weekday() if target_draw_date else None
    weekday_profiles = [
        profile
        for profile, record in zip(shape_profiles, records, strict=True)
        if target_weekday is not None and record.draw_date is not None and record.draw_date.weekday() == target_weekday
    ]
    recent_weekday_profiles = weekday_profiles[-20:]
    return FrequencyStats(
        train_draws=train_draws,
        frequency_rate={number: counts[number] / denominator for number in range(1, 34)},
        recent_frequency_rate=_recent_frequency_rate(records[-SHORT_HOT_WINDOW:]),
        omission_rate=omission_rate,
        recent_omission_pressure=_recent_omission_pressure(last_seen_index, train_draws),
        previous_numbers=previous_numbers,
        previous_number_set=frozenset(previous_numbers),
        previous_consecutive_pair_count=previous_features["consecutive_pair_count"],
        previous_odd_count=previous_features["odd_count"],
        parity_transition_score_by_even_count=parity_transition_score_by_even_count,
        previous_zone_counts=(
            previous_features["zone_1_count"],
            previous_features["zone_2_count"],
            previous_features["zone_3_count"],
        ),
        recent_neighbor_rate=_recent_neighbor_rate(recent_numbers),
        lagged_consecutive_number_set=frozenset(_lagged_consecutive_numbers(records)),
        recent_average_gaps=_recent_average_gaps(shape_numbers),
        recent_average_sum=sum(sum(numbers) for numbers in shape_numbers) / len(shape_numbers),
        recent_average_span=sum(numbers[-1] - numbers[0] for numbers in shape_numbers) / len(shape_numbers),
        qian_kun_pattern_rate=_qian_kun_pattern_rate(qian_kun_patterns),
        recent_qian_kun_patterns=tuple(qian_kun_patterns[-6:]),
        shape_profile_rates=_shape_profile_rates(shape_profiles, recent_shape_profiles),
        sum_bucket_omission_rate=_feature_omission_rate([profile["sum_bucket"] for profile in shape_profiles]),
        span_bucket_omission_rate=_feature_omission_rate([profile["span_bucket"] for profile in shape_profiles]),
        recent_average_omission=_recent_average_omission(shape_numbers, omission_rate),
        stable_ranges=_stable_ranges(recent_shape_profiles),
        target_weekday=target_weekday,
        weekday_profile_rates=_shape_profile_rates(weekday_profiles, recent_weekday_profiles) if weekday_profiles else {},
    )


def score_frequency_candidate(
    numbers: tuple[int, ...],
    stats: FrequencyStats,
    config: FrequencyRankerConfig | None = None,
) -> dict[str, float]:
    cfg = config or FrequencyRankerConfig()
    structural_score = score_numbers(numbers)["score"]
    frequency_score = sum(stats.frequency_rate[number] for number in numbers)
    short_hot_frequency_score = _short_hot_frequency_score(numbers, stats)
    omission_score = sum(stats.omission_rate[number] for number in numbers) / 6
    long_omission_cooldown_score = _long_omission_cooldown_score(numbers, stats)
    features = calculate_red_ball_features(numbers)
    previous_consecutive_score = _previous_consecutive_score(
        candidate_pair_count=features["consecutive_pair_count"],
        previous_pair_count=stats.previous_consecutive_pair_count,
    )
    previous_overlap_score = len(set(numbers) & stats.previous_number_set) / 6
    previous_parity_shape_score = 1 - abs(features["odd_count"] - stats.previous_odd_count) / 6
    dynamic_parity_transition_score = _dynamic_parity_transition_score(features["odd_count"], stats)
    candidate_zone_counts = (features["zone_1_count"], features["zone_2_count"], features["zone_3_count"])
    previous_zone_shape_score = 1 - sum(
        abs(candidate_count - previous_count)
        for candidate_count, previous_count in zip(candidate_zone_counts, stats.previous_zone_counts, strict=True)
    ) / 12
    recent_neighbor_score = _recent_neighbor_score(numbers, stats)
    lagged_consecutive_score = _lagged_consecutive_score(numbers, stats)
    recent_gap_shape_score = _recent_gap_shape_score(numbers, stats)
    recent_sum_span_score = _recent_sum_span_score(numbers, stats)
    qian_kun_pattern_score = _qian_kun_pattern_score(numbers, stats)
    shape_profile = _shape_profile(numbers, previous_numbers=stats.previous_numbers)
    first_last_sum_score = _profile_score("first_last_sum", shape_profile, stats)
    span_trend_score = _profile_score("span_bucket", shape_profile, stats)
    sum_trend_score = _profile_score("sum_bucket", shape_profile, stats)
    ac_trend_score = _profile_score("ac_value", shape_profile, stats)
    zone_ratio_score = _profile_score("zone_signature", shape_profile, stats)
    big_small_ratio_score = _profile_score("big_count", shape_profile, stats)
    parity_ratio_score = _profile_score("even_count", shape_profile, stats)
    prime_composite_score = _profile_score("prime_count", shape_profile, stats)
    mod012_score = _profile_score("mod012_signature", shape_profile, stats)
    tail_distribution_score = _profile_score("tail_unique_count", shape_profile, stats)
    sum_tail_score = _profile_score("sum_tail", shape_profile, stats)
    red_omission_shape_score = _red_omission_shape_score(numbers, stats)
    sum_span_omission_score = _sum_span_omission_score(shape_profile, stats)
    consecutive_trend_score = _profile_score("consecutive_pair_count", shape_profile, stats)
    repeat_trend_score = _profile_score("repeat_count", shape_profile, stats)
    stable_range_score = _stable_range_score(shape_profile, stats)
    weekday_trend_score = _weekday_trend_score(shape_profile, stats)
    score = (
        cfg.structural_weight * structural_score
        + cfg.frequency_weight * frequency_score
        + cfg.omission_weight * omission_score
        + cfg.previous_consecutive_weight * previous_consecutive_score
        + cfg.previous_overlap_weight * previous_overlap_score
        + cfg.previous_parity_shape_weight * previous_parity_shape_score
        + cfg.dynamic_parity_transition_weight * dynamic_parity_transition_score
        + cfg.previous_zone_shape_weight * previous_zone_shape_score
        + cfg.recent_neighbor_weight * recent_neighbor_score
        + cfg.lagged_consecutive_weight * lagged_consecutive_score
        + cfg.recent_gap_shape_weight * recent_gap_shape_score
        + cfg.recent_sum_span_weight * recent_sum_span_score
        + cfg.qian_kun_pattern_weight * qian_kun_pattern_score
        + cfg.first_last_sum_weight * first_last_sum_score
        + cfg.span_trend_weight * span_trend_score
        + cfg.sum_trend_weight * sum_trend_score
        + cfg.ac_trend_weight * ac_trend_score
        + cfg.zone_ratio_weight * zone_ratio_score
        + cfg.big_small_ratio_weight * big_small_ratio_score
        + cfg.parity_ratio_weight * parity_ratio_score
        + cfg.prime_composite_weight * prime_composite_score
        + cfg.mod012_weight * mod012_score
        + cfg.tail_distribution_weight * tail_distribution_score
        + cfg.sum_tail_weight * sum_tail_score
        + cfg.red_omission_shape_weight * red_omission_shape_score
        + cfg.sum_span_omission_weight * sum_span_omission_score
        + cfg.consecutive_trend_weight * consecutive_trend_score
        + cfg.repeat_trend_weight * repeat_trend_score
        + cfg.stable_range_weight * stable_range_score
        + cfg.weekday_trend_weight * weekday_trend_score
        + cfg.short_hot_frequency_weight * short_hot_frequency_score
        + cfg.long_omission_cooldown_weight * long_omission_cooldown_score
    )
    return {
        "score": round(score, 8),
        "structural_score": round(structural_score, 8),
        "frequency_score": round(frequency_score, 8),
        "short_hot_frequency_score": round(short_hot_frequency_score, 8),
        "omission_score": round(omission_score, 8),
        "long_omission_cooldown_score": round(long_omission_cooldown_score, 8),
        "previous_consecutive_score": round(previous_consecutive_score, 8),
        "previous_overlap_score": round(previous_overlap_score, 8),
        "previous_parity_shape_score": round(previous_parity_shape_score, 8),
        "dynamic_parity_transition_score": round(dynamic_parity_transition_score, 8),
        "previous_zone_shape_score": round(previous_zone_shape_score, 8),
        "recent_neighbor_score": round(recent_neighbor_score, 8),
        "lagged_consecutive_score": round(lagged_consecutive_score, 8),
        "recent_gap_shape_score": round(recent_gap_shape_score, 8),
        "recent_sum_span_score": round(recent_sum_span_score, 8),
        "qian_kun_pattern_score": round(qian_kun_pattern_score, 8),
        "first_last_sum_score": round(first_last_sum_score, 8),
        "span_trend_score": round(span_trend_score, 8),
        "sum_trend_score": round(sum_trend_score, 8),
        "ac_trend_score": round(ac_trend_score, 8),
        "zone_ratio_score": round(zone_ratio_score, 8),
        "big_small_ratio_score": round(big_small_ratio_score, 8),
        "parity_ratio_score": round(parity_ratio_score, 8),
        "prime_composite_score": round(prime_composite_score, 8),
        "mod012_score": round(mod012_score, 8),
        "tail_distribution_score": round(tail_distribution_score, 8),
        "sum_tail_score": round(sum_tail_score, 8),
        "red_omission_shape_score": round(red_omission_shape_score, 8),
        "sum_span_omission_score": round(sum_span_omission_score, 8),
        "consecutive_trend_score": round(consecutive_trend_score, 8),
        "repeat_trend_score": round(repeat_trend_score, 8),
        "stable_range_score": round(stable_range_score, 8),
        "weekday_trend_score": round(weekday_trend_score, 8),
        "sum_value": float(features["sum_value"]),
        "span_value": float(features["span_value"]),
        "odd_count": float(features["odd_count"]),
    }


def _previous_consecutive_score(*, candidate_pair_count: int, previous_pair_count: int) -> float:
    candidate_score = min(candidate_pair_count, 5) / 5
    if previous_pair_count > 0:
        return candidate_score
    return 1 - candidate_score


def _recent_neighbor_rate(recent_numbers: list[tuple[int, ...]]) -> dict[int, float]:
    rates = {number: 0.0 for number in range(1, 34)}
    weights = (1.0, 0.7, 0.5)
    max_weight = sum(weights[: len(recent_numbers)]) or 1.0
    for numbers, weight in zip(reversed(recent_numbers), weights, strict=False):
        for number in numbers:
            for neighbor in (number - 1, number + 1):
                if 1 <= neighbor <= 33:
                    rates[neighbor] += weight
    return {number: min(value / max_weight, 1.0) for number, value in rates.items()}


def _recent_frequency_rate(recent_records: list[NormalizedHistoryDraw]) -> dict[int, float]:
    rates = {number: 0.0 for number in range(1, 34)}
    denominator = max(1, len(recent_records))
    for record in recent_records:
        for number in record.numbers:
            rates[number] += 1.0
    return {number: min(value / denominator, 1.0) for number, value in rates.items()}


def _recent_omission_pressure(last_seen_index: dict[int, int], train_draws: int) -> dict[int, float]:
    horizon = max(1, RECENT_OMISSION_HORIZON)
    return {
        number: min(1.0, (train_draws - 1 - last_seen_index[number]) / horizon)
        if last_seen_index[number] >= 0
        else 1.0
        for number in range(1, 34)
    }


def _lagged_consecutive_numbers(history: list[NormalizedHistoryDraw]) -> set[int]:
    if len(history) < 2:
        return set()
    previous = set(history[-1].numbers)
    before_previous = set(history[-2].numbers)
    candidates: set[int] = set()
    for number in range(1, 34):
        increasing = number - 1 in previous and number - 2 in before_previous
        decreasing = number + 1 in previous and number + 2 in before_previous
        if increasing or decreasing:
            candidates.add(number)
    return candidates


def _even_count(numbers: tuple[int, ...]) -> int:
    return sum(1 for number in numbers if number % 2 == 0)


def _parity_transition_score_by_even_count(
    history: list[NormalizedHistoryDraw],
) -> tuple[float, float, float, float, float, float, float]:
    even_counts = [_even_count(draw.numbers) for draw in history]
    scores = [0.5 for _ in range(7)]
    if not even_counts:
        return (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)

    current_state = tuple(even_counts[-2:])
    if len(current_state) == 2:
        for index in range(2, len(even_counts)):
            if (even_counts[index - 2], even_counts[index - 1]) == current_state:
                scores[even_counts[index]] += 1.0

    current_even_count = even_counts[-1]
    for index in range(1, len(even_counts)):
        if even_counts[index - 1] == current_even_count:
            scores[even_counts[index]] += 0.35

    for even_count in even_counts:
        scores[even_count] += 0.10

    max_score = max(scores) or 1.0
    return tuple(round(score / max_score, 8) for score in scores)  # type: ignore[return-value]


def _dynamic_parity_transition_score(odd_count: int, stats: FrequencyStats) -> float:
    even_count = 6 - odd_count
    return stats.parity_transition_score_by_even_count[even_count]


def _recent_average_gaps(recent_numbers: list[tuple[int, ...]]) -> tuple[float, float, float, float, float]:
    if not recent_numbers:
        return (6.4, 6.4, 6.4, 6.4, 6.4)
    totals = [0, 0, 0, 0, 0]
    for numbers in recent_numbers:
        gaps = [right - left for left, right in zip(numbers, numbers[1:])]
        for index, gap in enumerate(gaps):
            totals[index] += gap
    return tuple(total / len(recent_numbers) for total in totals)  # type: ignore[return-value]


def _recent_neighbor_score(numbers: tuple[int, ...], stats: FrequencyStats) -> float:
    return sum(stats.recent_neighbor_rate[number] for number in numbers) / 6


def _short_hot_frequency_score(numbers: tuple[int, ...], stats: FrequencyStats) -> float:
    return sum(stats.recent_frequency_rate[number] for number in numbers) / 6


def _long_omission_cooldown_score(numbers: tuple[int, ...], stats: FrequencyStats) -> float:
    pressure = sum(stats.recent_omission_pressure[number] ** 1.5 for number in numbers) / 6
    return max(0.0, min(1.0, 1 - pressure))


def _lagged_consecutive_score(numbers: tuple[int, ...], stats: FrequencyStats) -> float:
    return len(set(numbers) & stats.lagged_consecutive_number_set) / 6


def _recent_gap_shape_score(numbers: tuple[int, ...], stats: FrequencyStats) -> float:
    gaps = [right - left for left, right in zip(numbers, numbers[1:])]
    distance = sum(abs(gap - average) for gap, average in zip(gaps, stats.recent_average_gaps, strict=True))
    return max(0.0, 1 - distance / (5 * 32))


def _recent_sum_span_score(numbers: tuple[int, ...], stats: FrequencyStats) -> float:
    sum_score = max(0.0, 1 - abs(sum(numbers) - stats.recent_average_sum) / 162)
    span_score = max(0.0, 1 - abs((numbers[-1] - numbers[0]) - stats.recent_average_span) / 32)
    return (sum_score + span_score) / 2


def _qian_kun_pattern_rate(patterns: list[str]) -> dict[str, float]:
    if not patterns:
        return {}
    counts = {pattern: patterns.count(pattern) for pattern in set(patterns)}
    max_count = max(counts.values()) or 1
    return {pattern: count / max_count for pattern, count in counts.items()}


def _qian_kun_pattern_score(numbers: tuple[int, ...], stats: FrequencyStats) -> float:
    pattern = qian_kun_pattern(numbers)
    history_score = stats.qian_kun_pattern_rate.get(pattern, 0.0)
    if not stats.recent_qian_kun_patterns:
        return history_score
    recent_score = max(qian_kun_similarity(pattern, recent_pattern) for recent_pattern in stats.recent_qian_kun_patterns)
    return (history_score + recent_score) / 2


def _shape_profile(numbers: tuple[int, ...], *, previous_numbers: tuple[int, ...] | None = None) -> dict[str, object]:
    features = calculate_red_ball_features(numbers)
    tails = [number % 10 for number in numbers]
    gaps = {right - left for left, right in zip(numbers, numbers[1:])}
    pairwise_distances = {right - left for index, left in enumerate(numbers) for right in numbers[index + 1:]}
    return {
        "first_last_sum": numbers[0] + numbers[-1],
        "span_bucket": int(features["span_value"]) // 3,
        "sum_bucket": int(features["sum_value"]) // 10,
        "ac_value": max(0, len(pairwise_distances) - 5),
        "zone_signature": (
            features["zone_1_count"],
            features["zone_2_count"],
            features["zone_3_count"],
        ),
        "big_count": features["big_count"],
        "even_count": features["even_count"],
        "prime_count": sum(1 for number in numbers if number in PRIME_NUMBERS),
        "mod012_signature": (
            sum(1 for number in numbers if number % 3 == 0),
            sum(1 for number in numbers if number % 3 == 1),
            sum(1 for number in numbers if number % 3 == 2),
        ),
        "tail_unique_count": len(set(tails)),
        "sum_tail": int(features["sum_value"]) % 10,
        "consecutive_pair_count": features["consecutive_pair_count"],
        "repeat_count": len(set(numbers) & set(previous_numbers)) if previous_numbers else 0,
        "sum_value": features["sum_value"],
        "span_value": features["span_value"],
        "ac_numeric": max(0, len(pairwise_distances) - 5),
        "max_gap": max(gaps) if gaps else 0,
        "min_gap": min(gaps) if gaps else 0,
    }


def _shape_profile_rates(
    profiles: list[dict[str, object]],
    recent_profiles: list[dict[str, object]],
) -> dict[str, dict[object, float]]:
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
    return {key: _normalized_rate(profiles, recent_profiles, key) for key in keys}


def _normalized_rate(
    profiles: list[dict[str, object]],
    recent_profiles: list[dict[str, object]],
    key: str,
) -> dict[object, float]:
    scores: dict[object, float] = {}
    for profile in profiles:
        value = profile[key]
        scores[value] = scores.get(value, 0.0) + 1.0
    for profile in recent_profiles:
        value = profile[key]
        scores[value] = scores.get(value, 0.0) + 0.75
    max_score = max(scores.values(), default=1.0)
    return {value: score / max_score for value, score in scores.items()}


def _profile_score(key: str, profile: dict[str, object], stats: FrequencyStats) -> float:
    return stats.shape_profile_rates.get(key, {}).get(profile[key], 0.0)


def _feature_omission_rate(values: list[object]) -> dict[object, float]:
    last_seen: dict[object, int] = {}
    for index, value in enumerate(values):
        last_seen[value] = index
    total = max(1, len(values))
    return {value: (total - 1 - index) / total for value, index in last_seen.items()}


def _recent_average_omission(
    recent_numbers: list[tuple[int, ...]],
    omission_rate: dict[int, float],
) -> float:
    if not recent_numbers:
        return 0.5
    return sum(sum(omission_rate[number] for number in numbers) / 6 for numbers in recent_numbers) / len(recent_numbers)


def _red_omission_shape_score(numbers: tuple[int, ...], stats: FrequencyStats) -> float:
    candidate_average = sum(stats.omission_rate[number] for number in numbers) / 6
    return max(0.0, 1 - abs(candidate_average - stats.recent_average_omission))


def _sum_span_omission_score(profile: dict[str, object], stats: FrequencyStats) -> float:
    sum_omission = stats.sum_bucket_omission_rate.get(profile["sum_bucket"], 1.0)
    span_omission = stats.span_bucket_omission_rate.get(profile["span_bucket"], 1.0)
    return (sum_omission + span_omission) / 2


def _stable_ranges(profiles: list[dict[str, object]]) -> dict[str, tuple[float, float]]:
    numeric_keys = ("sum_value", "span_value", "ac_numeric", "first_last_sum", "max_gap", "min_gap")
    ranges: dict[str, tuple[float, float]] = {}
    for key in numeric_keys:
        values = sorted(float(profile[key]) for profile in profiles)
        if not values:
            ranges[key] = (0.0, 0.0)
        elif len(values) < 4:
            ranges[key] = (values[0], values[-1])
        else:
            quartiles = quantiles(values, n=4, method="inclusive")
            q1, q3 = quartiles[0], quartiles[2]
            iqr = max(q3 - q1, 1.0)
            ranges[key] = (q1 - 1.5 * iqr, q3 + 1.5 * iqr)
    return ranges


def _stable_range_score(profile: dict[str, object], stats: FrequencyStats) -> float:
    if not stats.stable_ranges:
        return 1.0
    scores = []
    for key, (lower, upper) in stats.stable_ranges.items():
        value = float(profile[key])
        width = max(upper - lower, 1.0)
        if lower <= value <= upper:
            scores.append(1.0)
        else:
            distance = lower - value if value < lower else value - upper
            scores.append(max(0.0, 1 - distance / width))
    return sum(scores) / len(scores)


def _weekday_trend_score(profile: dict[str, object], stats: FrequencyStats) -> float:
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
    scores = [stats.weekday_profile_rates.get(key, {}).get(profile[key], 0.0) for key in keys]
    return sum(scores) / len(scores)
