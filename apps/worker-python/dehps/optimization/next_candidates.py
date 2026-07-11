from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from math import isfinite
from statistics import median
from time import perf_counter
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.models.frequency_ranker import (
    FrequencyRankerConfig,
    HistoryDraw,
    history_draw_date,
    history_issue,
    history_numbers,
    infer_next_ssq_draw_date,
)
from dehps.optimization.regime import select_history
from dehps.optimization.self_diagnostics import build_prediction_self_diagnostics
from dehps.optimization.weight_kdj import weight_kdj_advice_from_signals
from dehps.optimization.walk_forward import (
    CONFIG_WEIGHT_FIELDS,
    build_ranked_universe,
    config_hash,
    fingerprint_history,
    rank_target_grid_with_red5,
    top_candidates_for_next,
)
from dehps.storage.postgres_store import (
    CANONICAL_TRAINING_WEIGHT_SIGNAL_RUN_ID,
    TOTAL_SSQ_RED_COMBINATIONS,
    ensure_training_supervisor_best_schema,
    load_history_with_dates,
    load_recent_training_weight_signals,
    replace_training_next_candidates_current,
)

STATIC_100_LINE_KEY = "static_100"
DYNAMIC_KDJ_LINE_KEY = "dynamic_kdj"
NEAR_DYNAMIC_KDJ_LINE_KEY = "dynamic_kdj_near"
STATIC_100_LINE_LABEL = "100-period static training"
DYNAMIC_KDJ_LINE_LABEL = "Dynamic KDJ adjustment"
NEAR_DYNAMIC_KDJ_LINE_LABEL = "Near-term Dynamic KDJ"
PRIMARY_CONFIG_FIELDS = frozenset({"structural_weight", "frequency_weight", "omission_weight"})
CONTEXT_CONFIG_FIELDS = tuple(field for field in CONFIG_WEIGHT_FIELDS if field not in PRIMARY_CONFIG_FIELDS)
REGRESSION_PROTOCOL_VERSION = "dual-line-regression-100-v1"
DYNAMIC_KDJ_TRAINING_PROTOCOL_VERSION = "dynamic-kdj-line-training-v1"
NEAR_DYNAMIC_KDJ_TRAINING_PROTOCOL_VERSION = "near-dynamic-kdj-line-training-v1"
NEAR_DYNAMIC_KDJ_EVAL_WINDOW = 9
NEAR_DYNAMIC_KDJ_TRAIN_MODE = "rolling"
NEAR_DYNAMIC_KDJ_SUCCESS_WINDOW = 10
NEAR_DYNAMIC_KDJ_SUCCESS_TOP100_GOAL = 3
DEFAULT_DYNAMIC_KDJ_STRENGTH_SWEEP = (0.25, 0.5, 1.0)
DEFAULT_DYNAMIC_KDJ_MIN_EFFECTIVE_STRENGTH = 0.05
DEFAULT_DYNAMIC_KDJ_MAX_EFFECTIVE_STRENGTH = 1.0


def next_issue_hint(issue: str | None) -> str:
    if not issue or not issue.isdigit():
        return ""
    return str(int(issue) + 1)


def issue_less_than(left: object, right: object) -> bool:
    left_text = str(left)
    right_text = str(right)
    try:
        return int(left_text) < int(right_text)
    except ValueError:
        return left_text < right_text


def issue_sort_key(value: object) -> tuple[int, int | str]:
    text = str(value)
    try:
        return (0, int(text))
    except ValueError:
        return (1, text)


def config_values(config: FrequencyRankerConfig) -> dict[str, float]:
    return {field: float(getattr(config, field)) for field in CONFIG_WEIGHT_FIELDS}


def clamp_frequency_config(config: FrequencyRankerConfig) -> FrequencyRankerConfig:
    values = config_values(config)
    for field in PRIMARY_CONFIG_FIELDS:
        values[field] = min(1.25, max(0.0, values[field]))
    for field in CONTEXT_CONFIG_FIELDS:
        values[field] = min(0.30, max(-0.30, values[field]))
    return FrequencyRankerConfig(**values)


def training_freshness_metadata(
    *,
    training_as_of_issue: str | None,
    latest_issue: str | None,
    training_history_fingerprint: str | None,
    current_history_fingerprint: str | None,
) -> dict[str, Any]:
    training_issue = str(training_as_of_issue or "")
    current_issue = str(latest_issue or "")
    issue_lag: int | None = None
    if training_issue.isdigit() and current_issue.isdigit():
        issue_lag = int(current_issue) - int(training_issue)
    issue_matches = bool(training_issue and current_issue and training_issue == current_issue)
    history_matches = bool(
        training_history_fingerprint
        and current_history_fingerprint
        and training_history_fingerprint == current_history_fingerprint
    )
    return {
        "status": "current" if issue_matches and history_matches else "stale",
        "training_issue_matches_current": issue_matches,
        "training_history_matches_current": history_matches,
        "training_issue_lag": issue_lag,
    }


def training_summary_sort_key(summary: dict[str, Any]) -> tuple:
    red5 = summary.get("red5") if isinstance(summary.get("red5"), dict) else {}
    reward = summary.get("reward") if isinstance(summary.get("reward"), dict) else {}
    rank_quality = summary.get("rank_quality") if isinstance(summary.get("rank_quality"), dict) else {}
    baseline_overlap = summary.get("baseline_overlap") if isinstance(summary.get("baseline_overlap"), dict) else {}
    baseline_bands = baseline_overlap.get("bands") if isinstance(baseline_overlap.get("bands"), dict) else {}
    top_10000_overlap = baseline_bands.get("top_10000") if isinstance(baseline_bands.get("top_10000"), dict) else {}
    top_1000_overlap = baseline_bands.get("top_1000") if isinstance(baseline_bands.get("top_1000"), dict) else {}
    return (
        int(summary.get("top_100_hits") or 0),
        int(summary.get("top_1000_hits") or 0),
        int(top_1000_overlap.get("unique_hit_count") or 0),
        float(reward.get("objectiveScore") or 0),
        -int(rank_quality.get("tail_over_1000000_count") or 0),
        -int(rank_quality.get("tail_over_900000_count") or 0),
        -int(rank_quality.get("tail_over_750000_count") or 0),
        int(top_10000_overlap.get("unique_hit_count") or 0),
        -int(top_10000_overlap.get("overlap_hit_count") or 0),
        int(summary.get("top_10000_hits") or 0),
        int(rank_quality.get("top_50000_hits") or 0),
        int(rank_quality.get("top_100000_hits") or 0),
        int(rank_quality.get("top_250000_hits") or 0),
        int(rank_quality.get("top_500000_hits") or 0),
        int(red5.get("top_100_hits") or 0),
        int(red5.get("top_1000_hits") or 0),
        int(red5.get("top_10000_hits") or 0),
        -float(summary.get("worst_rank") or 0),
        -float(summary.get("median_rank") or 0),
        -float(summary.get("best_rank") or 0),
    )


def int_metric(source: dict[str, Any], key: str) -> int:
    return int(source.get(key) or 0)


def numeric_metric(source: dict[str, Any], key: str) -> float | None:
    value = source.get(key)
    return float(value) if isinstance(value, int | float) else None


def clamp_numeric(value: float, *, low: float, high: float) -> float:
    if high < low:
        low, high = high, low
    return min(high, max(low, value))


def positive_float(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if isfinite(number) and number > 0.0 else default


def rounded_float(value: float, digits: int = 8) -> float:
    return round(float(value), digits)


def normalize_strength_sweep(strength_values: tuple[float, ...] | list[float] | None = None) -> tuple[float, ...]:
    values = DEFAULT_DYNAMIC_KDJ_STRENGTH_SWEEP if strength_values is None else tuple(strength_values)
    normalized: set[float] = set()
    for value in values:
        scale = positive_float(value)
        if scale > 0.0:
            normalized.add(rounded_float(scale))
    normalized.add(1.0)
    return tuple(sorted(normalized))


def dynamic_strength_policy_from_anchor(
    anchor_offset_scale: float,
    *,
    strength_values: tuple[float, ...] | list[float] | None = None,
) -> dict[str, Any]:
    anchor = positive_float(anchor_offset_scale, 1.0)
    strengths = normalize_strength_sweep(strength_values)
    lower_neighbors = [strength for strength in strengths if strength < anchor]
    upper_neighbors = [strength for strength in strengths if strength > anchor]
    min_scale = lower_neighbors[-1] if lower_neighbors else anchor * 0.5
    max_scale = upper_neighbors[0] if upper_neighbors else anchor * 2.0
    min_scale = clamp_numeric(
        min_scale,
        low=DEFAULT_DYNAMIC_KDJ_MIN_EFFECTIVE_STRENGTH,
        high=DEFAULT_DYNAMIC_KDJ_MAX_EFFECTIVE_STRENGTH,
    )
    max_scale = clamp_numeric(
        max_scale,
        low=DEFAULT_DYNAMIC_KDJ_MIN_EFFECTIVE_STRENGTH,
        high=DEFAULT_DYNAMIC_KDJ_MAX_EFFECTIVE_STRENGTH,
    )
    anchor = clamp_numeric(
        anchor,
        low=DEFAULT_DYNAMIC_KDJ_MIN_EFFECTIVE_STRENGTH,
        high=DEFAULT_DYNAMIC_KDJ_MAX_EFFECTIVE_STRENGTH,
    )
    if min_scale > anchor:
        min_scale = max(DEFAULT_DYNAMIC_KDJ_MIN_EFFECTIVE_STRENGTH, anchor * 0.5)
    if max_scale < anchor:
        max_scale = min(DEFAULT_DYNAMIC_KDJ_MAX_EFFECTIVE_STRENGTH, anchor * 2.0)
    if max_scale <= min_scale:
        min_scale = max(DEFAULT_DYNAMIC_KDJ_MIN_EFFECTIVE_STRENGTH, anchor * 0.75)
        max_scale = min(DEFAULT_DYNAMIC_KDJ_MAX_EFFECTIVE_STRENGTH, anchor * 1.25)
    return {
        "mode": "kdj_state_band",
        "anchor_offset_scale": rounded_float(anchor),
        "min_offset_scale": rounded_float(min_scale),
        "max_offset_scale": rounded_float(max_scale),
        "confidence_midpoint": 0.5,
        "confidence_formula": "weighted_probability_j_extremity_slope_interval",
    }


def _weighted_average(values: list[tuple[float, float]]) -> float:
    total_weight = sum(max(0.0, weight) for _value, weight in values)
    if total_weight <= 0.0:
        return 0.0
    return sum(value * max(0.0, weight) for value, weight in values) / total_weight


def dynamic_effective_strength_from_advice(
    advice: list[Any],
    *,
    anchor_offset_scale: float,
    strength_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        raw_anchor = float(anchor_offset_scale)
    except (TypeError, ValueError):
        raw_anchor = 1.0
    if not isfinite(raw_anchor) or raw_anchor < 0.0:
        raw_anchor = 1.0
    anchor = raw_anchor
    if not isinstance(strength_policy, dict) or strength_policy.get("mode") != "kdj_state_band":
        return {
            "mode": "fixed_strength",
            "anchor_offset_scale": rounded_float(anchor),
            "effective_offset_scale": rounded_float(anchor),
            "min_offset_scale": rounded_float(anchor),
            "max_offset_scale": rounded_float(anchor),
            "confidence": 0.5,
            "usable_advice_count": len(advice),
            "downweighted_share": 0.0,
        }

    anchor = positive_float(strength_policy.get("anchor_offset_scale"), positive_float(anchor, 1.0))
    min_scale = positive_float(strength_policy.get("min_offset_scale"), max(anchor * 0.5, DEFAULT_DYNAMIC_KDJ_MIN_EFFECTIVE_STRENGTH))
    max_scale = positive_float(strength_policy.get("max_offset_scale"), min(anchor * 2.0, DEFAULT_DYNAMIC_KDJ_MAX_EFFECTIVE_STRENGTH))
    min_scale = clamp_numeric(
        min_scale,
        low=DEFAULT_DYNAMIC_KDJ_MIN_EFFECTIVE_STRENGTH,
        high=DEFAULT_DYNAMIC_KDJ_MAX_EFFECTIVE_STRENGTH,
    )
    max_scale = clamp_numeric(
        max_scale,
        low=DEFAULT_DYNAMIC_KDJ_MIN_EFFECTIVE_STRENGTH,
        high=DEFAULT_DYNAMIC_KDJ_MAX_EFFECTIVE_STRENGTH,
    )
    anchor = clamp_numeric(anchor, low=min_scale, high=max_scale)
    usable = [item for item in advice if getattr(item, "decision", "") in {"selected", "downweighted"} and getattr(item, "applied_offset", 0.0)]
    if not usable:
        return {
            "mode": "kdj_state_band",
            "anchor_offset_scale": rounded_float(anchor),
            "effective_offset_scale": rounded_float(anchor),
            "min_offset_scale": rounded_float(min_scale),
            "max_offset_scale": rounded_float(max_scale),
            "confidence": 0.5,
            "usable_advice_count": 0,
            "downweighted_share": 0.0,
        }

    weighted_probability: list[tuple[float, float]] = []
    weighted_j_extremity: list[tuple[float, float]] = []
    weighted_slope: list[tuple[float, float]] = []
    weighted_interval_edge: list[tuple[float, float]] = []
    downweighted_count = 0
    for item in usable:
        probability_weight = clamp_numeric(float(getattr(item, "probability_weight", 0.0) or 0.0), low=0.0, high=1.0)
        applied_offset = abs(float(getattr(item, "applied_offset", 0.0) or 0.0))
        objective_delta = max(0.0, float(getattr(item, "objective_delta", 0.0) or 0.0))
        weight = max(1e-9, applied_offset * max(0.05, probability_weight) * (1.0 + min(objective_delta, 10.0) / 10.0))
        weighted_probability.append((probability_weight, weight))
        weighted_j_extremity.append((clamp_numeric(abs(float(getattr(item, "j_value", 50.0) or 50.0) - 50.0) / 50.0, low=0.0, high=1.0), weight))
        weighted_slope.append((clamp_numeric(abs(float(getattr(item, "j_slope", 0.0) or 0.0)) / 100.0, low=0.0, high=1.0), weight))
        weighted_interval_edge.append((clamp_numeric(abs(float(getattr(item, "interval_position", 0.5) or 0.5) - 0.5) * 2.0, low=0.0, high=1.0), weight))
        if getattr(item, "decision", "") == "downweighted":
            downweighted_count += 1

    probability = _weighted_average(weighted_probability)
    j_extremity = _weighted_average(weighted_j_extremity)
    slope = _weighted_average(weighted_slope)
    interval_edge = _weighted_average(weighted_interval_edge)
    downweighted_share = downweighted_count / len(usable)
    confidence = (
        probability * 0.30
        + j_extremity * 0.30
        + slope * 0.20
        + interval_edge * 0.20
    )
    confidence *= 1.0 - min(0.35, downweighted_share * 0.35)
    confidence = clamp_numeric(confidence, low=0.0, high=1.0)
    if confidence >= 0.5:
        effective_scale = anchor + (max_scale - anchor) * ((confidence - 0.5) / 0.5)
    else:
        effective_scale = min_scale + (anchor - min_scale) * (confidence / 0.5)
    effective_scale = clamp_numeric(effective_scale, low=min_scale, high=max_scale)
    return {
        "mode": "kdj_state_band",
        "anchor_offset_scale": rounded_float(anchor),
        "effective_offset_scale": rounded_float(effective_scale),
        "min_offset_scale": rounded_float(min_scale),
        "max_offset_scale": rounded_float(max_scale),
        "confidence": rounded_float(confidence),
        "probability": rounded_float(probability),
        "j_extremity": rounded_float(j_extremity),
        "slope_strength": rounded_float(slope),
        "interval_edge_strength": rounded_float(interval_edge),
        "usable_advice_count": len(usable),
        "downweighted_share": rounded_float(downweighted_share),
    }


def compact_static_regression_summary(best: dict[str, Any]) -> dict[str, Any]:
    summary = best.get("summary") if isinstance(best.get("summary"), dict) else {}
    red5 = summary.get("red5") if isinstance(summary.get("red5"), dict) else {}
    configured_eval_window = int(best.get("eval_window") or 0)
    evaluated_draws = int(summary.get("evaluated_draws") or configured_eval_window)
    return {
        "status": "evaluated" if evaluated_draws else "unknown",
        "protocol": REGRESSION_PROTOCOL_VERSION,
        "source": "training_supervisor_best",
        "line_key": STATIC_100_LINE_KEY,
        "eval_window": evaluated_draws,
        "configured_eval_window": configured_eval_window,
        "top_100_hits": int_metric(summary, "top_100_hits"),
        "top_1000_hits": int_metric(summary, "top_1000_hits"),
        "top_10000_hits": int_metric(summary, "top_10000_hits"),
        "median_rank": numeric_metric(summary, "median_rank"),
        "best_rank": int_metric(summary, "best_rank") or None,
        "worst_rank": int_metric(summary, "worst_rank") or None,
        "red5": {
            "eval_window": evaluated_draws,
            "top_100_hits": int_metric(red5, "top_100_hits"),
            "top_1000_hits": int_metric(red5, "top_1000_hits"),
            "top_10000_hits": int_metric(red5, "top_10000_hits"),
            "median_rank": numeric_metric(red5, "median_rank"),
            "best_rank": int_metric(red5, "best_rank") or None,
        },
        "fallback_target_count": 0,
        "changed_target_count": 0,
        "leakage_passed": True,
        "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
    }


def regression_summary_from_ranks(
    *,
    line_key: str,
    source: str,
    eval_window: int,
    configured_eval_window: int,
    exact_ranks: list[int],
    red5_ranks: list[int],
    fallback_target_count: int,
    changed_target_count: int,
    leakage_passed: bool,
    target_issues: list[str] | None = None,
    target_results: list[dict[str, Any]] | None = None,
    train_mode: str | None = None,
    train_window: int | None = None,
    latest_signal_issue: str | None = None,
    offset_scale: float | None = None,
    effective_offset_scales: list[float] | None = None,
    strength_policy: dict[str, Any] | None = None,
    top_n: int | None = None,
) -> dict[str, Any]:
    issue_window = list(target_issues or [])
    summary = {
        "status": "evaluated" if exact_ranks else "skipped_insufficient_history",
        "protocol": REGRESSION_PROTOCOL_VERSION,
        "source": source,
        "line_key": line_key,
        "train_mode": train_mode,
        "train_window": int(train_window) if train_window is not None else None,
        "eval_window": eval_window,
        "configured_eval_window": configured_eval_window,
        "top_100_hits": sum(rank <= 100 for rank in exact_ranks),
        "top_1000_hits": sum(rank <= 1000 for rank in exact_ranks),
        "top_10000_hits": sum(rank <= 10000 for rank in exact_ranks),
        "median_rank": median(exact_ranks) if exact_ranks else None,
        "best_rank": min(exact_ranks) if exact_ranks else None,
        "worst_rank": max(exact_ranks) if exact_ranks else None,
        "red5": {
            "eval_window": eval_window,
            "top_100_hits": sum(rank <= 100 for rank in red5_ranks),
            "top_1000_hits": sum(rank <= 1000 for rank in red5_ranks),
            "top_10000_hits": sum(rank <= 10000 for rank in red5_ranks),
            "median_rank": median(red5_ranks) if red5_ranks else None,
            "best_rank": min(red5_ranks) if red5_ranks else None,
        },
        "fallback_target_count": fallback_target_count,
        "changed_target_count": changed_target_count,
        "leakage_passed": leakage_passed,
        "target_issues": issue_window,
        "target_results": list(target_results or []),
        "window_start_issue": issue_window[0] if issue_window else None,
        "window_end_issue": issue_window[-1] if issue_window else None,
        "latest_signal_issue": latest_signal_issue,
        "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
    }
    if offset_scale is not None:
        summary["offset_scale"] = round(float(offset_scale), 8)
        summary["anchor_offset_scale"] = round(float(offset_scale), 8)
    if effective_offset_scales:
        summary["effective_offset_scale_min"] = round(min(effective_offset_scales), 8)
        summary["effective_offset_scale_median"] = round(median(effective_offset_scales), 8)
        summary["effective_offset_scale_max"] = round(max(effective_offset_scales), 8)
    if isinstance(strength_policy, dict):
        summary["strength_policy"] = strength_policy
    if top_n is not None:
        summary["top_n"] = int(top_n)
    return summary


def regression_target_result_payload(
    *,
    target_draw: HistoryDraw,
    rank: int,
    score: float,
    red5_match: Any | None,
) -> dict[str, Any]:
    red5_rank = getattr(red5_match, "rank", None) if red5_match is not None else None
    red5_score = getattr(red5_match, "score", None) if red5_match is not None else None
    red5_numbers = getattr(red5_match, "numbers", None) if red5_match is not None else None
    red5_missing_number = getattr(red5_match, "missing_number", None) if red5_match is not None else None
    red5_extra_number = getattr(red5_match, "extra_number", None) if red5_match is not None else None
    normalized_red5_rank = int(red5_rank) if isinstance(red5_rank, int | float) else None
    draw_date = history_draw_date(target_draw)
    return {
        "issue": str(history_issue(target_draw)),
        "draw_date": draw_date.isoformat() if draw_date else None,
        "red_numbers": list(history_numbers(target_draw)),
        "rank": int(rank),
        "score": float(score),
        "hit_top_100": int(rank) <= 100,
        "hit_top_1000": int(rank) <= 1000,
        "hit_top_10000": int(rank) <= 10000,
        "red5_rank": normalized_red5_rank,
        "red5_score": float(red5_score) if isinstance(red5_score, int | float) else None,
        "red5_numbers": list(red5_numbers or ()),
        "red5_missing_number": red5_missing_number,
        "red5_extra_number": red5_extra_number,
        "hit_red5_top_100": normalized_red5_rank is not None and normalized_red5_rank <= 100,
        "hit_red5_top_1000": normalized_red5_rank is not None and normalized_red5_rank <= 1000,
        "hit_red5_top_10000": normalized_red5_rank is not None and normalized_red5_rank <= 10000,
    }


def regression_training_sort_key(summary: dict[str, Any]) -> tuple:
    red5 = summary.get("red5") if isinstance(summary.get("red5"), dict) else {}
    return (
        int(summary.get("top_100_hits") or 0),
        int(summary.get("top_1000_hits") or 0),
        int(red5.get("top_100_hits") or 0),
        int(red5.get("top_1000_hits") or 0),
        int(summary.get("top_10000_hits") or 0),
        int(red5.get("top_10000_hits") or 0),
        -float(summary.get("worst_rank") or 0),
        -float(summary.get("median_rank") or 0),
        -float(summary.get("best_rank") or 0),
        float(summary.get("offset_scale") or 0.0),
    )


def dynamic_regression_is_fully_dynamic(summary: dict[str, Any]) -> bool:
    eval_window = int(summary.get("eval_window") or 0)
    return (
        summary.get("status") == "evaluated"
        and eval_window > 0
        and positive_float(summary.get("anchor_offset_scale", summary.get("offset_scale"))) > 0.0
        and int(summary.get("fallback_target_count") or 0) == 0
        and int(summary.get("changed_target_count") or 0) == eval_window
        and bool(summary.get("leakage_passed"))
    )


def regression_target_indexes(*, history_len: int, train_window: int, eval_window: int) -> range:
    if train_window < 1:
        raise ValueError("train_window must be at least 1")
    if eval_window < 1:
        raise ValueError("eval_window must be at least 1")
    if history_len <= train_window:
        return range(0)
    return range(max(train_window, history_len - eval_window), history_len)


def dynamic_kdj_regression_summary(
    *,
    history: list[HistoryDraw],
    base_config: FrequencyRankerConfig,
    signals: list[dict[str, Any]],
    ranked_universe: Any,
    train_mode: str,
    train_window: int,
    eval_window: int,
    top_n: int,
    offset_scale: float = 1.0,
    strength_policy: dict[str, Any] | None = None,
    line_key: str = DYNAMIC_KDJ_LINE_KEY,
    source: str = "dynamic_kdj_per_target",
) -> dict[str, Any]:
    indexes = list(regression_target_indexes(history_len=len(history), train_window=train_window, eval_window=eval_window))
    if not indexes:
        return {
            "status": "skipped_insufficient_history",
            "protocol": REGRESSION_PROTOCOL_VERSION,
            "source": source,
            "line_key": line_key,
            "train_mode": train_mode,
            "train_window": train_window,
            "eval_window": 0,
            "configured_eval_window": eval_window,
            "top_100_hits": 0,
            "top_1000_hits": 0,
            "top_10000_hits": 0,
            "red5": {
                "eval_window": 0,
                "top_100_hits": 0,
                "top_1000_hits": 0,
                "top_10000_hits": 0,
                "median_rank": None,
                "best_rank": None,
            },
            "fallback_target_count": 0,
            "changed_target_count": 0,
            "leakage_passed": True,
            "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
            "target_results": [],
        }

    exact_ranks: list[int] = []
    red5_ranks: list[int] = []
    fallback_target_count = 0
    changed_target_count = 0
    leakage_passed = True
    latest_signal_issue: str | None = None
    effective_offset_scales: list[float] = []
    target_issues: list[str] = []
    target_results: list[dict[str, Any]] = []

    for target_index in indexes:
        target_draw = history[target_index]
        target_issue = history_issue(target_draw)
        target_issues.append(str(target_issue))
        dynamic_config, dynamic_metadata = dynamic_kdj_config_for_next(
            base_config=base_config,
            signals=signals,
            target_issue=target_issue,
            offset_scale=offset_scale,
            strength_policy=strength_policy,
        )
        if dynamic_metadata["fallback_static_base"]:
            fallback_target_count += 1
        else:
            changed_target_count += 1
        leakage_passed = leakage_passed and bool(dynamic_metadata["leakage_passed"])
        signal_issue = dynamic_metadata.get("latest_signal_issue")
        if signal_issue is not None and (latest_signal_issue is None or issue_sort_key(signal_issue) > issue_sort_key(latest_signal_issue)):
            latest_signal_issue = str(signal_issue)
        effective_offset_scales.append(float(dynamic_metadata.get("effective_offset_scale") or offset_scale))

        train_start = 0 if train_mode == "expanding" else max(0, target_index - train_window)
        train_history = history[train_start:target_index]
        ranked_target = rank_target_grid_with_red5(
            target_numbers=history_numbers(target_draw),
            train_history=train_history,
            configs=(dynamic_config,),
            ranked_universe=ranked_universe,
            target_draw_date=history_draw_date(target_draw),
            workers=1,
            pool=None,
        )[0]
        rank, score, red5_match = ranked_target
        exact_ranks.append(int(rank))
        if red5_match is not None:
            red5_ranks.append(int(red5_match.rank))
        target_results.append(
            regression_target_result_payload(
                target_draw=target_draw,
                rank=int(rank),
                score=float(score),
                red5_match=red5_match,
            )
        )

    return regression_summary_from_ranks(
        line_key=line_key,
        source=source,
        eval_window=len(exact_ranks),
        configured_eval_window=eval_window,
        exact_ranks=exact_ranks,
        red5_ranks=red5_ranks,
        fallback_target_count=fallback_target_count,
        changed_target_count=changed_target_count,
        leakage_passed=leakage_passed,
        target_issues=target_issues,
        target_results=target_results,
        train_mode=train_mode,
        train_window=train_window,
        latest_signal_issue=latest_signal_issue,
        offset_scale=offset_scale,
        effective_offset_scales=effective_offset_scales,
        strength_policy=strength_policy,
        top_n=top_n,
    )


def dynamic_kdj_strength_sweep_training_summary(
    *,
    history: list[HistoryDraw],
    base_config: FrequencyRankerConfig,
    signals: list[dict[str, Any]],
    ranked_universe: Any,
    train_mode: str,
    train_window: int,
    eval_window: int,
    top_n: int,
    workers: int = 1,
    strength_values: tuple[float, ...] | list[float] | None = None,
    line_key: str = DYNAMIC_KDJ_LINE_KEY,
    protocol: str = DYNAMIC_KDJ_TRAINING_PROTOCOL_VERSION,
    source: str = "dynamic_kdj_strength_sweep",
) -> dict[str, Any]:
    started = perf_counter()
    strengths = normalize_strength_sweep(strength_values)
    indexes = list(regression_target_indexes(history_len=len(history), train_window=train_window, eval_window=eval_window))
    target_worker_count = max(1, min(int(workers), len(indexes))) if indexes else 1
    if not indexes:
        default_anchor = strengths[0] if strengths else 1.0
        default_policy = dynamic_strength_policy_from_anchor(default_anchor, strength_values=strengths)
        return {
            "status": "skipped_insufficient_history",
            "protocol": protocol,
            "line_key": line_key,
            "strengths": list(strengths),
            "selected_strength": default_anchor,
            "selected_strength_policy": default_policy,
            "selected_summary": regression_summary_from_ranks(
                line_key=line_key,
                source=source,
                eval_window=0,
                configured_eval_window=eval_window,
                exact_ranks=[],
                red5_ranks=[],
                fallback_target_count=0,
                changed_target_count=0,
                leakage_passed=True,
                target_results=[],
                train_mode=train_mode,
                train_window=train_window,
                offset_scale=default_anchor,
                strength_policy=default_policy,
                top_n=top_n,
            ),
            "rows": [],
            "base_config_hash": config_hash(base_config),
            "base_config": config_values(base_config),
            "target_worker_count": target_worker_count,
            "elapsed_seconds": round(perf_counter() - started, 3),
        }

    exact_ranks_by_strength: dict[float, list[int]] = {strength: [] for strength in strengths}
    red5_ranks_by_strength: dict[float, list[int]] = {strength: [] for strength in strengths}
    fallback_counts: dict[float, int] = {strength: 0 for strength in strengths}
    changed_counts: dict[float, int] = {strength: 0 for strength in strengths}
    leakage_by_strength: dict[float, bool] = {strength: True for strength in strengths}
    latest_signal_by_strength: dict[float, str | None] = {strength: None for strength in strengths}
    effective_scales_by_strength: dict[float, list[float]] = {strength: [] for strength in strengths}
    target_results_by_strength: dict[float, list[dict[str, Any]]] = {strength: [] for strength in strengths}
    target_issues: list[str] = []
    strength_policies: dict[float, dict[str, Any]] = {
        strength: dynamic_strength_policy_from_anchor(strength, strength_values=strengths)
        for strength in strengths
    }
    as_of_issue = history_issue(history[-1])
    history_fingerprint_value = fingerprint_history(history)

    def evaluate_target(target_index: int) -> tuple[HistoryDraw, str, list[tuple[float, dict[str, Any], tuple]]]:
        target_draw = history[target_index]
        target_issue = history_issue(target_draw)
        configs: list[FrequencyRankerConfig] = []
        metadata_by_strength: list[tuple[float, dict[str, Any]]] = []
        for strength in strengths:
            dynamic_config, dynamic_metadata = dynamic_kdj_config_for_next(
                base_config=base_config,
                signals=signals,
                target_issue=target_issue,
                offset_scale=strength,
                strength_policy=strength_policies[strength],
            )
            configs.append(dynamic_config)
            metadata_by_strength.append((strength, dynamic_metadata))

        train_start = 0 if train_mode == "expanding" else max(0, target_index - train_window)
        ranked_targets = rank_target_grid_with_red5(
            target_numbers=history_numbers(target_draw),
            train_history=history[train_start:target_index],
            configs=tuple(configs),
            ranked_universe=ranked_universe,
            target_draw_date=history_draw_date(target_draw),
            workers=1,
            pool=None,
        )
        return (
            target_draw,
            str(target_issue),
            [
                (strength, dynamic_metadata, ranked_target)
                for (strength, dynamic_metadata), ranked_target in zip(
                    metadata_by_strength,
                    ranked_targets,
                    strict=True,
                )
            ],
        )

    if target_worker_count > 1:
        with ThreadPoolExecutor(max_workers=target_worker_count, thread_name_prefix="dynamic-kdj") as executor:
            target_evaluations = list(executor.map(evaluate_target, indexes))
    else:
        target_evaluations = list(map(evaluate_target, indexes))

    for target_draw, target_issue, target_rows in target_evaluations:
        target_issues.append(target_issue)
        for strength, dynamic_metadata, ranked_target in target_rows:
            if dynamic_metadata["fallback_static_base"]:
                fallback_counts[strength] += 1
            else:
                changed_counts[strength] += 1
            leakage_by_strength[strength] = leakage_by_strength[strength] and bool(dynamic_metadata["leakage_passed"])
            signal_issue = dynamic_metadata.get("latest_signal_issue")
            if signal_issue is not None and (
                latest_signal_by_strength[strength] is None
                or issue_sort_key(signal_issue) > issue_sort_key(latest_signal_by_strength[strength])
            ):
                latest_signal_by_strength[strength] = str(signal_issue)
            effective_scales_by_strength[strength].append(float(dynamic_metadata.get("effective_offset_scale") or strength))
            rank, score, red5_match = ranked_target
            exact_ranks_by_strength[strength].append(int(rank))
            if red5_match is not None:
                red5_ranks_by_strength[strength].append(int(red5_match.rank))
            target_results_by_strength[strength].append(
                regression_target_result_payload(
                    target_draw=target_draw,
                    rank=int(rank),
                    score=float(score),
                    red5_match=red5_match,
                )
            )

    summaries = [
        regression_summary_from_ranks(
            line_key=line_key,
            source=source,
            eval_window=len(exact_ranks_by_strength[strength]),
            configured_eval_window=eval_window,
            exact_ranks=exact_ranks_by_strength[strength],
            red5_ranks=red5_ranks_by_strength[strength],
            fallback_target_count=fallback_counts[strength],
            changed_target_count=changed_counts[strength],
            leakage_passed=leakage_by_strength[strength],
            target_issues=target_issues,
            target_results=target_results_by_strength[strength],
            train_mode=train_mode,
            train_window=train_window,
            latest_signal_issue=latest_signal_by_strength[strength],
            offset_scale=strength,
            effective_offset_scales=effective_scales_by_strength[strength],
            strength_policy=strength_policies[strength],
            top_n=top_n,
        )
        for strength in strengths
    ]
    for summary in summaries:
        summary["as_of_issue"] = as_of_issue
        summary["history_fingerprint"] = history_fingerprint_value
        summary["base_config_hash"] = config_hash(base_config)
    fully_dynamic_summaries = [summary for summary in summaries if dynamic_regression_is_fully_dynamic(summary)]
    rows = [
        {
            "strength": float(summary.get("offset_scale") or 0.0),
            "anchor_offset_scale": float(summary.get("anchor_offset_scale") or summary.get("offset_scale") or 0.0),
            "effective_offset_scale_min": summary.get("effective_offset_scale_min"),
            "effective_offset_scale_median": summary.get("effective_offset_scale_median"),
            "effective_offset_scale_max": summary.get("effective_offset_scale_max"),
            "top_100_hits": int(summary.get("top_100_hits") or 0),
            "top_1000_hits": int(summary.get("top_1000_hits") or 0),
            "top_10000_hits": int(summary.get("top_10000_hits") or 0),
            "red5_top_100_hits": int((summary.get("red5") or {}).get("top_100_hits") or 0)
            if isinstance(summary.get("red5"), dict)
            else 0,
            "red5_top_1000_hits": int((summary.get("red5") or {}).get("top_1000_hits") or 0)
            if isinstance(summary.get("red5"), dict)
            else 0,
            "red5_top_10000_hits": int((summary.get("red5") or {}).get("top_10000_hits") or 0)
            if isinstance(summary.get("red5"), dict)
            else 0,
            "median_rank": summary.get("median_rank"),
            "best_rank": summary.get("best_rank"),
            "worst_rank": summary.get("worst_rank"),
            "fallback_target_count": int(summary.get("fallback_target_count") or 0),
            "changed_target_count": int(summary.get("changed_target_count") or 0),
            "leakage_passed": bool(summary.get("leakage_passed")),
            "fully_dynamic": dynamic_regression_is_fully_dynamic(summary),
            "strength_policy": summary.get("strength_policy"),
        }
        for summary in summaries
    ]
    if not fully_dynamic_summaries:
        return {
            "status": "skipped_no_fully_dynamic_kdj",
            "protocol": protocol,
            "line_key": line_key,
            "selection_method": "regression_training_sort_key",
            "strength_mode": "kdj_state_band",
            "strengths": list(strengths),
            "selected_strength": 0.0,
            "selected_strength_policy": {},
            "selected_summary": {},
            "rows": rows,
            "base_config_hash": config_hash(base_config),
            "base_config": config_values(base_config),
            "eval_window": len(indexes),
            "configured_eval_window": eval_window,
            "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
            "as_of_issue": as_of_issue,
            "history_fingerprint": history_fingerprint_value,
            "target_worker_count": target_worker_count,
            "elapsed_seconds": round(perf_counter() - started, 3),
        }
    selected_summary = max(fully_dynamic_summaries, key=regression_training_sort_key)
    selected_strength = float(selected_summary.get("offset_scale") or 0.0)
    return {
        "status": "evaluated",
        "protocol": protocol,
        "line_key": line_key,
        "selection_method": "regression_training_sort_key",
        "strength_mode": "kdj_state_band",
        "strengths": list(strengths),
        "selected_strength": selected_strength,
        "selected_strength_policy": selected_summary.get("strength_policy"),
        "selected_summary": selected_summary,
        "rows": rows,
        "base_config_hash": config_hash(base_config),
        "base_config": config_values(base_config),
        "eval_window": len(indexes),
        "configured_eval_window": eval_window,
        "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
        "target_worker_count": target_worker_count,
        "elapsed_seconds": round(perf_counter() - started, 3),
    }


def resolve_latest_training_run_id(conn: Connection, run_id: str | None = None) -> str | None:
    if run_id:
        return run_id
    with conn.cursor() as cur:
        row = cur.execute(
            """
            SELECT run_id
            FROM training_round_results
            ORDER BY created_at DESC, round_index DESC
            LIMIT 1
            """
        ).fetchone()
    return str(row[0]) if row else None


def training_best_candidate_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    summary = row.get("best_summary") if isinstance(row.get("best_summary"), dict) else {}
    config = summary.get("config") if isinstance(summary.get("config"), dict) else row.get("best_config")
    if not isinstance(config, dict) or not config:
        return None
    return {
        "run_id": str(row["run_id"]),
        "source_round_index": int(row["round_index"]),
        "train_mode": str(row["train_mode"]),
        "train_window": int(row["train_window"]),
        "eval_window": int(row["eval_window"]),
        "top_n": int(row["top_n"]),
        "training_as_of_issue": str(row["as_of_issue"]),
        "training_history_fingerprint": str(row["history_fingerprint"]),
        "history_scope": str(row.get("history_scope") or ""),
        "regime_years": int(row.get("regime_years") or 0),
        "training_regime_start_date": row.get("regime_start_date").isoformat()
        if row.get("regime_start_date")
        else "",
        "summary": summary,
        "config": {key: float(value) for key, value in config.items() if isinstance(value, int | float)},
    }


def load_training_supervisor_best_summary(conn: Connection, run_id: str | None = None) -> dict[str, Any] | None:
    ensure_training_supervisor_best_schema(conn)
    if run_id:
        query = """
            SELECT run_id, round_index, train_mode, train_window, eval_window, top_n,
                   as_of_issue, history_fingerprint, history_scope, regime_years, regime_start_date,
                   best_summary, best_config, updated_at
            FROM training_supervisor_best
            WHERE run_id = %s
            ORDER BY round_index DESC, updated_at DESC
            LIMIT 1
        """
        params: tuple[Any, ...] = (run_id,)
    else:
        query = """
            SELECT run_id, round_index, train_mode, train_window, eval_window, top_n,
                   as_of_issue, history_fingerprint, history_scope, regime_years, regime_start_date,
                   best_summary, best_config, updated_at
            FROM training_supervisor_best
            ORDER BY updated_at DESC
            LIMIT 1
        """
        params = ()
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(query, params).fetchone()
    if not row:
        return None
    return training_best_candidate_from_row(row)


def load_best_training_summary(conn: Connection, run_id: str | None = None) -> dict[str, Any] | None:
    checkpoint_best = load_training_supervisor_best_summary(conn, run_id)
    if checkpoint_best is not None:
        return checkpoint_best
    resolved_run_id = resolve_latest_training_run_id(conn, run_id)
    if not resolved_run_id:
        return None
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT run_id, round_index, train_mode, train_window, eval_window, top_n,
                   as_of_issue, history_fingerprint, history_scope, regime_years, regime_start_date,
                   best_summary, best_config, updated_at
            FROM training_round_results
            WHERE run_id = %s
            ORDER BY round_index ASC
            """,
            (resolved_run_id,),
        ).fetchall()
    best: dict[str, Any] | None = None
    for row in rows:
        candidate = training_best_candidate_from_row(row)
        if candidate is None:
            continue
        if best is None or training_summary_sort_key(candidate["summary"]) > training_summary_sort_key(best["summary"]):
            best = candidate
    return best


def load_current_history_for_training_scope(conn: Connection, best: dict[str, Any]) -> tuple[list, dict[str, Any]]:
    scope = str(best.get("history_scope") or "")
    regime_years = int(best.get("regime_years") or 0)
    if scope in {"full_history_audit", "current_regime_default"} and regime_years >= 1:
        selection = select_history(conn, scope=scope, regime_years=regime_years)
        return selection.dated_history, {
            "history_scope": selection.scope,
            "regime_years": selection.regime_years,
            "regime_start_date": selection.start_date.isoformat() if selection.start_date else "",
            "freshness_mode": "training_scope",
        }
    return load_history_with_dates(conn), {
        "history_scope": scope,
        "regime_years": regime_years,
        "regime_start_date": "",
        "freshness_mode": "legacy_full_history",
    }


def build_training_next_candidate_snapshot(
    conn: Connection,
    *,
    run_id: str | None = None,
    top_n: int = 10000,
    ranked_universe: Any | None = None,
) -> dict[str, Any]:
    if top_n < 1:
        raise ValueError("top_n must be at least 1")

    best = load_best_training_summary(conn, run_id)
    if best is None:
        raise RuntimeError("no training_round_results best config is available")
    history, history_context = load_current_history_for_training_scope(conn, best)
    if not history:
        raise RuntimeError("ssq_history is empty")
    latest_issue = str(history[-1][0])
    target_draw_date = infer_next_ssq_draw_date(history)
    current_history_fingerprint = fingerprint_history(history)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    config = FrequencyRankerConfig(**best["config"])
    matrix = ranked_universe or build_ranked_universe()
    resolved_top_n = min(top_n, len(matrix))
    candidates = top_candidates_for_next(
        history=history if best["train_mode"] == "expanding" else history[-best["train_window"] :],
        top_n=resolved_top_n,
        config=config,
        target_draw_date=target_draw_date,
        ranked_universe=matrix,
    )
    regression_summary = compact_static_regression_summary(best)
    self_diagnostics = build_prediction_self_diagnostics(
        regression_summary=regression_summary,
        candidates=candidates,
        legal_sample_space=TOTAL_SSQ_RED_COMBINATIONS,
    )
    metadata = {
        "line_key": STATIC_100_LINE_KEY,
        "line_label": STATIC_100_LINE_LABEL,
        "line_kind": "static",
        "snapshot_key": f"training-next-{latest_issue}-{config_hash(config)[:12]}",
        "run_id": best["run_id"],
        "source_round_index": best["source_round_index"],
        "as_of_issue": latest_issue,
        "next_issue": next_issue_hint(latest_issue),
        "next_draw_date": target_draw_date.isoformat() if target_draw_date else None,
        "train_mode": best["train_mode"],
        "train_window": best["train_window"],
        "eval_window": best["eval_window"],
        "top_n": resolved_top_n,
        "history_fingerprint": current_history_fingerprint,
        "training_as_of_issue": best["training_as_of_issue"],
        "training_history_fingerprint": best["training_history_fingerprint"],
        "history_scope": history_context["history_scope"],
        "regime_years": history_context["regime_years"],
        "regime_start_date": history_context["regime_start_date"],
        "training_regime_start_date": best.get("training_regime_start_date") or "",
        "freshness_mode": history_context["freshness_mode"],
        "training_freshness": training_freshness_metadata(
            training_as_of_issue=best["training_as_of_issue"],
            latest_issue=latest_issue,
            training_history_fingerprint=best["training_history_fingerprint"],
            current_history_fingerprint=current_history_fingerprint,
        ),
        "config_hash": config_hash(config),
        "config": best["config"],
        "prediction_metadata": {
            "line_key": STATIC_100_LINE_KEY,
            "line_label": STATIC_100_LINE_LABEL,
            "protocol": "static_training_best",
            "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
            "regression_100": regression_summary,
            "gauss_guardrail": {
                "sample_space": TOTAL_SSQ_RED_COMBINATIONS,
                "as_of_issue": latest_issue,
                "next_issue": next_issue_hint(latest_issue),
                "leakage_boundary": "snapshot uses history through as_of_issue only",
                "regression_window": regression_summary["eval_window"],
            },
            "riemann_guardrail": {
                "shared_history_space": True,
                "shared_candidate_universe": True,
                "structural_change": "none_static_best_config",
            },
            "self_diagnostics": self_diagnostics,
            "fallback_static_base": False,
        },
        "generated_at": generated_at,
        "candidate_count": len(candidates),
    }
    return {"metadata": metadata, "candidates": candidates}


def dynamic_kdj_config_for_next(
    *,
    base_config: FrequencyRankerConfig,
    signals: list[dict[str, Any]],
    target_issue: str,
    offset_scale: float = 1.0,
    strength_policy: dict[str, Any] | None = None,
    min_objective_delta: float = 0.0,
    min_abs_offset: float = 0.005,
    slope_window: int = 3,
    neutral_band: float = 5.0,
) -> tuple[FrequencyRankerConfig, dict[str, Any]]:
    anchor_scale = positive_float(offset_scale)
    eligible = [signal for signal in signals if issue_less_than(signal.get("issue"), target_issue)]
    excluded = len(signals) - len(eligible)
    advice = weight_kdj_advice_from_signals(
        eligible,
        allowed_fields=CONFIG_WEIGHT_FIELDS,
        min_objective_delta=min_objective_delta,
        min_abs_offset=min_abs_offset,
        slope_window=slope_window,
        neutral_band=neutral_band,
    )
    usable_advice: list[Any] = []
    used_fields: set[str] = set()
    for item in advice:
        if item.decision not in {"selected", "downweighted"} or not item.applied_offset:
            continue
        if item.weight_name in used_fields:
            continue
        used_fields.add(item.weight_name)
        usable_advice.append(item)
    strength_state = dynamic_effective_strength_from_advice(
        usable_advice,
        anchor_offset_scale=anchor_scale,
        strength_policy=strength_policy,
    )
    scale = float(strength_state["effective_offset_scale"])
    values = config_values(base_config)
    applied_offsets: dict[str, float] = {}
    for item in usable_advice:
        offset = float(item.applied_offset) * scale
        if not offset:
            continue
        values[item.weight_name] = float(values[item.weight_name]) + offset
        applied_offsets[item.weight_name] = offset

    dynamic_config = clamp_frequency_config(FrequencyRankerConfig(**values))
    latest_signal_issue = max(
        (str(signal.get("issue") or "") for signal in eligible),
        key=issue_sort_key,
        default=None,
    )
    leakage_passed = all(issue_less_than(signal.get("issue"), target_issue) for signal in eligible)
    if latest_signal_issue is not None:
        leakage_passed = leakage_passed and issue_less_than(latest_signal_issue, target_issue)
    metadata = {
        "thresholds": {
            "offset_scale": scale,
            "anchor_offset_scale": anchor_scale,
            "min_objective_delta": min_objective_delta,
            "min_abs_offset": min_abs_offset,
            "slope_window": slope_window,
            "neutral_band": neutral_band,
        },
        "strength_policy": strength_policy or {
            "mode": "fixed_strength",
            "anchor_offset_scale": rounded_float(anchor_scale),
            "min_offset_scale": rounded_float(anchor_scale),
            "max_offset_scale": rounded_float(anchor_scale),
        },
        "strength_state": strength_state,
        "anchor_offset_scale": rounded_float(anchor_scale),
        "effective_offset_scale": rounded_float(scale),
        "signal_count": len(signals),
        "eligible_signal_count": len(eligible),
        "excluded_signal_count": excluded,
        "latest_signal_issue": latest_signal_issue,
        "leakage_passed": leakage_passed,
        "fallback_static_base": not bool(applied_offsets),
        "applied_offsets": {field: round(value, 8) for field, value in sorted(applied_offsets.items())},
        "advice": [item.as_dict() for item in advice],
    }
    return dynamic_config, metadata


def build_dynamic_kdj_next_candidate_snapshot(
    conn: Connection,
    *,
    run_id: str | None = None,
    top_n: int = 10000,
    ranked_universe: Any | None = None,
    signal_run_id: str | None = None,
    dynamic_policy: dict[str, Any] | None = None,
    line_key: str = DYNAMIC_KDJ_LINE_KEY,
    line_label: str = DYNAMIC_KDJ_LINE_LABEL,
    line_kind: str = "dynamic_kdj",
    training_protocol: str = DYNAMIC_KDJ_TRAINING_PROTOCOL_VERSION,
    prediction_protocol: str = "dynamic_kdj_next_issue",
    regression_eval_window: int | None = None,
    train_mode_override: str | None = None,
    sealed: bool = False,
) -> dict[str, Any]:
    if top_n < 1:
        raise ValueError("top_n must be at least 1")

    best = load_best_training_summary(conn, run_id)
    if best is None:
        raise RuntimeError("no training_round_results best config is available")
    history, history_context = load_current_history_for_training_scope(conn, best)
    if not history:
        raise RuntimeError("ssq_history is empty")
    effective_train_mode = train_mode_override or best["train_mode"]
    latest_issue = str(history[-1][0])
    next_issue = next_issue_hint(latest_issue)
    target_draw_date = infer_next_ssq_draw_date(history)
    current_history_fingerprint = fingerprint_history(history)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    policy = dynamic_policy if isinstance(dynamic_policy, dict) else {}
    policy_base_config = policy.get("base_config") if isinstance(policy.get("base_config"), dict) else None
    base_config_values = {
        key: float(value)
        for key, value in (policy_base_config or best["config"]).items()
        if isinstance(value, int | float)
    }
    base_config = FrequencyRankerConfig(**base_config_values)
    offset_scale = positive_float(
        policy.get("anchor_offset_scale", policy.get("offset_scale")),
        1.0,
    )
    strength_policy = policy.get("strength_policy") if isinstance(policy.get("strength_policy"), dict) else None
    if strength_policy is None:
        strength_policy = dynamic_strength_policy_from_anchor(offset_scale)
    signals = load_recent_training_weight_signals(
        conn,
        signal_run_id=signal_run_id or CANONICAL_TRAINING_WEIGHT_SIGNAL_RUN_ID,
        as_of_issue=latest_issue,
        train_mode=best["train_mode"],
        train_window=best["train_window"],
        top_n=best["top_n"],
        limit=1000,
    )
    dynamic_config, dynamic_metadata = dynamic_kdj_config_for_next(
        base_config=base_config,
        signals=signals,
        target_issue=next_issue,
        offset_scale=offset_scale,
        strength_policy=strength_policy,
    )
    if dynamic_metadata["fallback_static_base"]:
        raise RuntimeError("dynamic KDJ line produced no KDJ offsets; refusing static fallback")
    matrix = ranked_universe or build_ranked_universe()
    resolved_regression_eval_window = int(regression_eval_window or best["eval_window"])
    policy_regression = policy.get("regression_summary") if isinstance(policy.get("regression_summary"), dict) else None
    if policy_regression is not None and not dynamic_regression_is_fully_dynamic(policy_regression):
        raise RuntimeError("dynamic KDJ policy regression is not fully dynamic")
    regression_summary = policy_regression or dynamic_kdj_regression_summary(
        history=history,
        base_config=base_config,
        signals=signals,
        ranked_universe=matrix,
        train_mode=effective_train_mode,
        train_window=best["train_window"],
        eval_window=resolved_regression_eval_window,
        top_n=best["top_n"],
        offset_scale=offset_scale,
        strength_policy=strength_policy,
        line_key=line_key,
    )
    if not dynamic_regression_is_fully_dynamic(regression_summary):
        raise RuntimeError("dynamic KDJ regression is not fully dynamic")
    resolved_top_n = min(top_n, len(matrix))
    candidate_history = history if effective_train_mode == "expanding" else history[-best["train_window"] :]
    candidates = top_candidates_for_next(
        history=candidate_history,
        top_n=resolved_top_n,
        config=dynamic_config,
        target_draw_date=target_draw_date,
        ranked_universe=matrix,
    )
    dynamic_config_values = config_values(dynamic_config)
    self_diagnostics = build_prediction_self_diagnostics(
        regression_summary=regression_summary,
        candidates=candidates,
        legal_sample_space=TOTAL_SSQ_RED_COMBINATIONS,
        dynamic_metadata=dynamic_metadata,
    )
    regression_key = "regression_9" if resolved_regression_eval_window == NEAR_DYNAMIC_KDJ_EVAL_WINDOW else "regression_100"
    near_window = {
        "enabled": line_key == NEAR_DYNAMIC_KDJ_LINE_KEY,
        "known_eval_window": resolved_regression_eval_window,
        "success_window": NEAR_DYNAMIC_KDJ_SUCCESS_WINDOW,
        "success_top100_goal": NEAR_DYNAMIC_KDJ_SUCCESS_TOP100_GOAL,
        "target_issues": regression_summary.get("target_issues") or [],
        "window_start_issue": regression_summary.get("window_start_issue"),
        "window_end_issue": regression_summary.get("window_end_issue"),
        "as_of_issue": latest_issue,
        "next_issue": next_issue,
        "train_mode": effective_train_mode,
        "train_window": best["train_window"],
        "sealed": bool(sealed or policy.get("sealed")),
        "seal_reason": policy.get("seal_reason"),
        "sealed_round_index": policy.get("sealed_round_index"),
        "window_key": f"{regression_summary.get('window_start_issue') or 'none'}-{regression_summary.get('window_end_issue') or latest_issue}->{next_issue}",
    }
    metadata = {
        "line_key": line_key,
        "line_label": line_label,
        "line_kind": line_kind,
        "snapshot_key": f"training-next-{line_key.replace('_', '-')}-{latest_issue}-{config_hash(dynamic_config)[:12]}",
        "run_id": str(policy.get("run_id") or best["run_id"]),
        "source_round_index": int(policy.get("source_round_index") or best["source_round_index"]),
        "as_of_issue": latest_issue,
        "next_issue": next_issue,
        "next_draw_date": target_draw_date.isoformat() if target_draw_date else None,
        "train_mode": effective_train_mode,
        "train_window": best["train_window"],
        "eval_window": resolved_regression_eval_window,
        "top_n": resolved_top_n,
        "history_fingerprint": current_history_fingerprint,
        "training_as_of_issue": best["training_as_of_issue"],
        "training_history_fingerprint": best["training_history_fingerprint"],
        "history_scope": history_context["history_scope"],
        "regime_years": history_context["regime_years"],
        "regime_start_date": history_context["regime_start_date"],
        "training_regime_start_date": best.get("training_regime_start_date") or "",
        "freshness_mode": history_context["freshness_mode"],
        "training_freshness": training_freshness_metadata(
            training_as_of_issue=best["training_as_of_issue"],
            latest_issue=latest_issue,
            training_history_fingerprint=best["training_history_fingerprint"],
            current_history_fingerprint=current_history_fingerprint,
        ),
        "config_hash": config_hash(dynamic_config),
        "config": dynamic_config_values,
        "prediction_metadata": {
            "line_key": line_key,
            "line_label": line_label,
            "protocol": prediction_protocol,
            "base_config_hash": config_hash(base_config),
            "base_config": base_config_values,
            "dynamic_policy": {
                "protocol": policy.get("protocol") or training_protocol,
                "selection_method": policy.get("selection_method") or "kdj_state_band",
                "strength_mode": strength_policy.get("mode") or "kdj_state_band",
                "offset_scale": offset_scale,
                "anchor_offset_scale": offset_scale,
                "min_offset_scale": strength_policy.get("min_offset_scale"),
                "max_offset_scale": strength_policy.get("max_offset_scale"),
                "source_round_index": policy.get("source_round_index"),
                "base_config_hash": config_hash(base_config),
                "policy_key": policy.get("policy_key"),
                "strength_policy": strength_policy,
            },
            "signal_run_id": signal_run_id or CANONICAL_TRAINING_WEIGHT_SIGNAL_RUN_ID,
            "signal_train_mode": best["train_mode"],
            "effective_train_mode": effective_train_mode,
            "target_issue": next_issue,
            "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
            "regression": regression_summary,
            "regression_100": regression_summary,
            regression_key: regression_summary,
            "near_window": near_window,
            "snapshot_sealed": near_window["sealed"],
            **dynamic_metadata,
            "gauss_guardrail": {
                "sample_space": TOTAL_SSQ_RED_COMBINATIONS,
                "as_of_issue": latest_issue,
                "next_issue": next_issue,
                "leakage_boundary": "KDJ signals must have issue < next_issue",
                "leakage_passed": dynamic_metadata["leakage_passed"],
                "regression_window": regression_summary["eval_window"],
                "regression_leakage_passed": regression_summary["leakage_passed"],
                "random_top100_expected_hits_per_10": round(
                    NEAR_DYNAMIC_KDJ_SUCCESS_WINDOW * 100 / TOTAL_SSQ_RED_COMBINATIONS,
                    8,
                ),
            },
            "riemann_guardrail": {
                "shared_history_space": True,
                "shared_candidate_universe": True,
                "structural_change": "same base config plus per-issue KDJ offsets and KDJ-state adaptive offset-scale interval",
            },
            "self_diagnostics": self_diagnostics,
        },
        "generated_at": generated_at,
        "candidate_count": len(candidates),
    }
    return {"metadata": metadata, "candidates": candidates}


def refresh_training_next_candidates_current(
    conn: Connection,
    *,
    run_id: str | None = None,
    top_n: int = 10000,
    ranked_universe: Any | None = None,
) -> dict[str, Any]:
    snapshot = build_training_next_candidate_snapshot(conn, run_id=run_id, top_n=top_n, ranked_universe=ranked_universe)
    replace_training_next_candidates_current(
        conn,
        metadata=snapshot["metadata"],
        candidates=snapshot["candidates"],
    )
    return snapshot["metadata"]


def refresh_dynamic_kdj_next_candidates_current(
    conn: Connection,
    *,
    run_id: str | None = None,
    top_n: int = 10000,
    ranked_universe: Any | None = None,
    signal_run_id: str | None = None,
    dynamic_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = build_dynamic_kdj_next_candidate_snapshot(
        conn,
        run_id=run_id,
        top_n=top_n,
        ranked_universe=ranked_universe,
        signal_run_id=signal_run_id,
        dynamic_policy=dynamic_policy,
    )
    replace_training_next_candidates_current(
        conn,
        metadata=snapshot["metadata"],
        candidates=snapshot["candidates"],
    )
    return snapshot["metadata"]


def build_near_dynamic_kdj_next_candidate_snapshot(
    conn: Connection,
    *,
    run_id: str | None = None,
    top_n: int = 10000,
    ranked_universe: Any | None = None,
    signal_run_id: str | None = None,
    dynamic_policy: dict[str, Any] | None = None,
    sealed: bool = False,
) -> dict[str, Any]:
    policy = dict(dynamic_policy or {})
    policy.pop("sealed", None)
    policy.pop("seal_reason", None)
    policy.pop("sealed_round_index", None)
    return build_dynamic_kdj_next_candidate_snapshot(
        conn,
        run_id=run_id,
        top_n=top_n,
        ranked_universe=ranked_universe,
        signal_run_id=signal_run_id,
        dynamic_policy=policy,
        line_key=NEAR_DYNAMIC_KDJ_LINE_KEY,
        line_label=NEAR_DYNAMIC_KDJ_LINE_LABEL,
        line_kind="dynamic_kdj_near",
        training_protocol=NEAR_DYNAMIC_KDJ_TRAINING_PROTOCOL_VERSION,
        prediction_protocol="near_dynamic_kdj_next_issue",
        regression_eval_window=NEAR_DYNAMIC_KDJ_EVAL_WINDOW,
        train_mode_override=NEAR_DYNAMIC_KDJ_TRAIN_MODE,
        sealed=False,
    )


def refresh_near_dynamic_kdj_next_candidates_current(
    conn: Connection,
    *,
    run_id: str | None = None,
    top_n: int = 10000,
    ranked_universe: Any | None = None,
    signal_run_id: str | None = None,
    dynamic_policy: dict[str, Any] | None = None,
    sealed: bool = False,
) -> dict[str, Any]:
    snapshot = build_near_dynamic_kdj_next_candidate_snapshot(
        conn,
        run_id=run_id,
        top_n=top_n,
        ranked_universe=ranked_universe,
        signal_run_id=signal_run_id,
        dynamic_policy=dynamic_policy,
        sealed=sealed,
    )
    replace_training_next_candidates_current(
        conn,
        metadata=snapshot["metadata"],
        candidates=snapshot["candidates"],
    )
    return snapshot["metadata"]


def refresh_training_prediction_lines_current(
    conn: Connection,
    *,
    run_id: str | None = None,
    top_n: int = 10000,
    ranked_universe: Any | None = None,
    signal_run_id: str | None = None,
    dynamic_policy: dict[str, Any] | None = None,
    near_dynamic_policy: dict[str, Any] | None = None,
    near_dynamic_sealed: bool = False,
) -> dict[str, Any]:
    matrix = ranked_universe or build_ranked_universe()
    static_snapshot = build_training_next_candidate_snapshot(
        conn,
        run_id=run_id,
        top_n=top_n,
        ranked_universe=matrix,
    )
    dynamic_snapshot = build_dynamic_kdj_next_candidate_snapshot(
        conn,
        run_id=run_id,
        top_n=top_n,
        ranked_universe=matrix,
        signal_run_id=signal_run_id,
        dynamic_policy=dynamic_policy,
    )
    near_snapshot = None
    if isinstance(near_dynamic_policy, dict):
        near_snapshot = build_near_dynamic_kdj_next_candidate_snapshot(
            conn,
            run_id=run_id,
            top_n=top_n,
            ranked_universe=matrix,
            signal_run_id=signal_run_id,
            dynamic_policy=near_dynamic_policy,
            sealed=False,
        )
    replace_training_next_candidates_current(
        conn,
        metadata=static_snapshot["metadata"],
        candidates=static_snapshot["candidates"],
    )
    replace_training_next_candidates_current(
        conn,
        metadata=dynamic_snapshot["metadata"],
        candidates=dynamic_snapshot["candidates"],
    )
    if near_snapshot is not None:
        replace_training_next_candidates_current(
            conn,
            metadata=near_snapshot["metadata"],
            candidates=near_snapshot["candidates"],
        )
    lines = {
        STATIC_100_LINE_KEY: static_snapshot["metadata"],
        DYNAMIC_KDJ_LINE_KEY: dynamic_snapshot["metadata"],
    }
    if near_snapshot is not None:
        lines[NEAR_DYNAMIC_KDJ_LINE_KEY] = near_snapshot["metadata"]
    return {
        "status": "ready",
        "lines": lines,
    }
