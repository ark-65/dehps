from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta
from math import ceil
from pathlib import Path
import sys
import time
from statistics import median
from typing import Callable

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.features.qian_kun import qian_kun_distribution
from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.models.frequency_ranker import history_draw_date, history_issue, history_numbers
from dehps.optimization.regime import HistoryScope, select_history
from dehps.optimization.walk_forward import (
    TargetRank,
    build_ranked_universe,
    config_hash,
    create_worker_pool,
    deterministic_run_key,
    fingerprint_history,
    normalize_worker_count,
    rank_target_grid_with_red5,
)
from dehps.storage.postgres_store import load_red_combination_universe


PRIMARY_FIELDS = ("structural_weight", "frequency_weight", "omission_weight")
CONTEXT_FIELDS = (
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
)
ALL_FIELDS = PRIMARY_FIELDS + CONTEXT_FIELDS
DEFAULT_UNIVERSE_SIZE = 1_107_568
DEFAULT_TRAINING_EVENT_URL = "http://127.0.0.1:3000/training-events/status"
TOP_100_REWARD = 1000
TOP_1000_REWARD = 100
TOP_10000_REWARD = 10
RED5_TOP_100_REWARD = 5
RED5_TOP_1000_REWARD = 1
RED5_TOP_10000_REWARD = 0.2
RANK_TOP_50000_REWARD = 0.04
RANK_TOP_100000_REWARD = 0.02
RANK_TOP_250000_REWARD = 0.01
RANK_TOP_500000_REWARD = 0.005
WORST_RANK_REWARD = 3.0
MEDIAN_RANK_REWARD = 2.0
TAIL_OVER_750000_PENALTY = 0.15
TAIL_OVER_900000_PENALTY = 0.50
TAIL_OVER_1000000_PENALTY = 1.25
WORST_RANK_PENALTY_WEIGHT = 12.0
P95_RANK_PENALTY_WEIGHT = 6.0
MEDIAN_RANK_PENALTY_WEIGHT = 2.0
PHASES = (
    ("micro", 0.01),
    ("small", 0.03),
    ("medium", 0.07),
    ("large", 0.15),
)


def log(message: str) -> None:
    print(f"[supervisor] {datetime.now().isoformat(timespec='seconds')} {message}", file=sys.stderr, flush=True)


def training_event_url(value: str | None = None) -> str | None:
    resolved = value if value is not None else os.getenv("DEHPS_TRAINING_EVENT_URL", DEFAULT_TRAINING_EVENT_URL)
    return resolved.strip() if resolved and resolved.strip() else None


def post_training_event(status: dict, *, event_url: str | None = None, timeout: float = 1.0) -> bool:
    resolved_url = training_event_url(event_url)
    if not resolved_url:
        return False
    try:
        payload = json.dumps(status, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            resolved_url,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        log(f"training_event_warning url={resolved_url} error={exc}")
        return False


def training_progress_payload(
    *,
    round_index: int,
    target_index: int,
    target_total: int,
    issue: str,
    train_draws: int,
    elapsed_seconds: float,
    logged_at: str | None = None,
) -> dict:
    return {
        "logged_at": logged_at or datetime.now().isoformat(timespec="seconds"),
        "round": round_index,
        "target_index": target_index,
        "target_total": target_total,
        "issue": issue,
        "train_draws": train_draws,
        "elapsed_seconds": round(elapsed_seconds, 1),
    }


def config_dict(config: FrequencyRankerConfig) -> dict[str, float]:
    return dict(config.__dict__)


def clamp_config(config: FrequencyRankerConfig) -> FrequencyRankerConfig:
    values = config_dict(config)
    for field in PRIMARY_FIELDS:
        values[field] = min(1.25, max(0.0, values[field]))
    for field in CONTEXT_FIELDS:
        values[field] = min(0.30, max(-0.30, values[field]))
    return FrequencyRankerConfig(**values)


def add_unique(configs: list[FrequencyRankerConfig], seen: set[str], config: FrequencyRankerConfig) -> None:
    normalized = clamp_config(config)
    key = json.dumps(config_dict(normalized), sort_keys=True)
    if key not in seen:
        seen.add(key)
        configs.append(normalized)


def generate_configs(
    base: FrequencyRankerConfig,
    *,
    phase: str,
    step: float,
    max_configs: int,
    elite_configs: tuple[FrequencyRankerConfig, ...] = (),
) -> list[FrequencyRankerConfig]:
    configs: list[FrequencyRankerConfig] = []
    seen: set[str] = set()
    add_unique(configs, seen, base)

    fine_step = max(0.005, step / 2)
    for elite in elite_configs[:4]:
        add_unique(configs, seen, elite)
        for field in ALL_FIELDS:
            add_unique(configs, seen, replace(elite, **{field: getattr(elite, field) + fine_step}))
            add_unique(configs, seen, replace(elite, **{field: getattr(elite, field) - fine_step}))

    if elite_configs:
        best = elite_configs[0]
        for other in elite_configs[1:4]:
            add_unique(configs, seen, blend_configs(best, other, 0.50))
            add_unique(configs, seen, extrapolate_config(best, other, 0.50))

    for field in ALL_FIELDS:
        add_unique(configs, seen, replace(base, **{field: getattr(base, field) + step}))
        add_unique(configs, seen, replace(base, **{field: getattr(base, field) - step}))

    if phase in {"medium", "large"}:
        add_unique(
            configs,
            seen,
            replace(
                base,
                structural_weight=base.structural_weight + step,
                frequency_weight=base.frequency_weight - step / 2,
                omission_weight=base.omission_weight - step / 2,
            ),
        )
        add_unique(
            configs,
            seen,
            replace(
                base,
                structural_weight=base.structural_weight - step / 2,
                frequency_weight=base.frequency_weight + step,
                omission_weight=base.omission_weight - step / 2,
            ),
        )
        add_unique(
            configs,
            seen,
            replace(
                base,
                structural_weight=base.structural_weight - step / 2,
                frequency_weight=base.frequency_weight - step / 2,
                omission_weight=base.omission_weight + step,
            ),
        )

    if phase == "large":
        large_candidates = (
            FrequencyRankerConfig(structural_weight=0.55, frequency_weight=0.30, omission_weight=0.15, previous_consecutive_weight=0.00),
            FrequencyRankerConfig(structural_weight=0.25, frequency_weight=0.50, omission_weight=0.25, previous_consecutive_weight=0.00),
            FrequencyRankerConfig(structural_weight=0.25, frequency_weight=0.25, omission_weight=0.50, previous_consecutive_weight=0.00),
            FrequencyRankerConfig(
                structural_weight=0.35,
                frequency_weight=0.30,
                omission_weight=0.25,
                previous_consecutive_weight=0.03,
                previous_overlap_weight=-0.04,
                previous_parity_shape_weight=0.03,
                dynamic_parity_transition_weight=0.04,
                previous_zone_shape_weight=0.08,
            ),
            FrequencyRankerConfig(
                structural_weight=0.35,
                frequency_weight=0.55,
                omission_weight=0.05,
                previous_consecutive_weight=0.10,
                previous_overlap_weight=-0.05,
                previous_parity_shape_weight=-0.02,
                dynamic_parity_transition_weight=0.06,
                previous_zone_shape_weight=0.12,
                recent_neighbor_weight=0.06,
                lagged_consecutive_weight=0.04,
                recent_gap_shape_weight=0.04,
                recent_sum_span_weight=0.04,
                qian_kun_pattern_weight=0.04,
            ),
            FrequencyRankerConfig(
                structural_weight=0.30,
                frequency_weight=0.25,
                omission_weight=0.15,
                first_last_sum_weight=0.05,
                span_trend_weight=0.06,
                sum_trend_weight=0.06,
                ac_trend_weight=0.04,
                zone_ratio_weight=0.06,
                parity_ratio_weight=0.04,
                stable_range_weight=0.08,
            ),
            FrequencyRankerConfig(
                structural_weight=0.30,
                frequency_weight=0.20,
                omission_weight=0.20,
                big_small_ratio_weight=0.05,
                prime_composite_weight=0.04,
                mod012_weight=0.05,
                tail_distribution_weight=0.05,
                sum_tail_weight=0.04,
                red_omission_shape_weight=0.06,
                sum_span_omission_weight=-0.04,
                consecutive_trend_weight=0.05,
                repeat_trend_weight=0.04,
            ),
            FrequencyRankerConfig(
                structural_weight=0.28,
                frequency_weight=0.22,
                omission_weight=0.18,
                weekday_trend_weight=0.10,
                zone_ratio_weight=0.04,
                parity_ratio_weight=0.04,
                big_small_ratio_weight=0.04,
                mod012_weight=0.04,
                tail_distribution_weight=0.04,
                consecutive_trend_weight=0.03,
                repeat_trend_weight=0.03,
            ),
        )
        for config in large_candidates:
            add_unique(configs, seen, config)

    return configs[:max_configs]


def blend_configs(left: FrequencyRankerConfig, right: FrequencyRankerConfig, alpha: float) -> FrequencyRankerConfig:
    return clamp_config(
        FrequencyRankerConfig(
            **{
                field: getattr(left, field) * alpha + getattr(right, field) * (1 - alpha)
                for field in ALL_FIELDS
            }
        )
    )


def extrapolate_config(best: FrequencyRankerConfig, other: FrequencyRankerConfig, scale: float) -> FrequencyRankerConfig:
    return clamp_config(
        FrequencyRankerConfig(
            **{
                field: getattr(best, field) + (getattr(best, field) - getattr(other, field)) * scale
                for field in ALL_FIELDS
            }
        )
    )


def reward_summary(summary: dict, *, universe_size: int = DEFAULT_UNIVERSE_SIZE) -> dict[str, float]:
    safe_universe = max(1, universe_size)
    hit_reward = (
        summary["top_100_hits"] * TOP_100_REWARD
        + summary["top_1000_hits"] * TOP_1000_REWARD
        + summary["top_10000_hits"] * TOP_10000_REWARD
    )
    red5 = summary.get("red5") if isinstance(summary.get("red5"), dict) else {}
    red5_reward = (
        float(red5.get("top_100_hits") or 0) * RED5_TOP_100_REWARD
        + float(red5.get("top_1000_hits") or 0) * RED5_TOP_1000_REWARD
        + float(red5.get("top_10000_hits") or 0) * RED5_TOP_10000_REWARD
    )
    rank_quality = summary.get("rank_quality") if isinstance(summary.get("rank_quality"), dict) else {}
    rank_quality_reward = float(rank_quality.get("reward") or 0)
    median_rank = summary.get("median_rank") or safe_universe
    worst_rank = summary.get("worst_rank") or safe_universe
    rank_penalty = median_rank / safe_universe + worst_rank / safe_universe / 4
    tail_risk_penalty = float(
        rank_quality.get("tail_risk_penalty")
        or calculate_tail_risk_penalty(
            median_rank=median_rank,
            worst_rank=worst_rank,
            p95_rank=rank_quality.get("p95_rank"),
            tail_over_750000_count=int(rank_quality.get("tail_over_750000_count") or 0),
            tail_over_900000_count=int(rank_quality.get("tail_over_900000_count") or 0),
            tail_over_1000000_count=int(rank_quality.get("tail_over_1000000_count") or 0),
            universe_size=safe_universe,
        )
    )
    return {
        "hitReward": round(hit_reward, 6),
        "red5Reward": round(red5_reward, 6),
        "rankQualityReward": round(rank_quality_reward, 6),
        "rankPenalty": round(rank_penalty, 6),
        "tailRiskPenalty": round(tail_risk_penalty, 6),
        "objectiveScore": round(hit_reward + red5_reward + rank_quality_reward - rank_penalty - tail_risk_penalty, 6),
    }


def empty_rank_quality_summary() -> dict:
    return {
        "top_50000_hits": 0,
        "top_100000_hits": 0,
        "top_250000_hits": 0,
        "top_500000_hits": 0,
        "p90_rank": None,
        "p95_rank": None,
        "tail_over_750000_count": 0,
        "tail_over_900000_count": 0,
        "tail_over_1000000_count": 0,
        "worst_rank_reward": 0.0,
        "median_rank_reward": 0.0,
        "band_reward": 0.0,
        "tail_risk_penalty": 0.0,
        "reward": 0.0,
    }


def percentile_rank(ranks: list[int], percentile: float) -> int | None:
    if not ranks:
        return None
    ordered = sorted(ranks)
    index = min(len(ordered) - 1, max(0, ceil(len(ordered) * percentile) - 1))
    return ordered[index]


def calculate_tail_risk_penalty(
    *,
    median_rank: int | float,
    worst_rank: int | float,
    p95_rank: int | float | None,
    tail_over_750000_count: int,
    tail_over_900000_count: int,
    tail_over_1000000_count: int,
    universe_size: int,
) -> float:
    safe_universe = max(1, universe_size)
    normalized_median = min(1.0, max(0.0, float(median_rank) / safe_universe))
    normalized_worst = min(1.0, max(0.0, float(worst_rank) / safe_universe))
    normalized_p95 = min(1.0, max(0.0, float(p95_rank if p95_rank is not None else worst_rank) / safe_universe))
    count_penalty = (
        tail_over_750000_count * TAIL_OVER_750000_PENALTY
        + tail_over_900000_count * TAIL_OVER_900000_PENALTY
        + tail_over_1000000_count * TAIL_OVER_1000000_PENALTY
    )
    shape_penalty = (
        normalized_worst**2 * WORST_RANK_PENALTY_WEIGHT
        + normalized_p95**2 * P95_RANK_PENALTY_WEIGHT
        + normalized_median**2 * MEDIAN_RANK_PENALTY_WEIGHT
    )
    return round(count_penalty + shape_penalty, 6)


def summarize_rank_quality(ranks: list[int], *, universe_size: int) -> dict:
    if not ranks:
        return empty_rank_quality_summary()
    safe_universe = max(1, universe_size)
    worst_rank = max(ranks)
    median_rank = median(ranks)
    p90_rank = percentile_rank(ranks, 0.90)
    p95_rank = percentile_rank(ranks, 0.95)
    tail_over_750000_count = sum(rank > 750_000 for rank in ranks)
    tail_over_900000_count = sum(rank > 900_000 for rank in ranks)
    tail_over_1000000_count = sum(rank > 1_000_000 for rank in ranks)
    band_reward = (
        sum(rank <= 50_000 for rank in ranks) * RANK_TOP_50000_REWARD
        + sum(rank <= 100_000 for rank in ranks) * RANK_TOP_100000_REWARD
        + sum(rank <= 250_000 for rank in ranks) * RANK_TOP_250000_REWARD
        + sum(rank <= 500_000 for rank in ranks) * RANK_TOP_500000_REWARD
    )
    worst_rank_reward = max(0.0, 1 - worst_rank / safe_universe) * WORST_RANK_REWARD
    median_rank_reward = max(0.0, 1 - median_rank / safe_universe) * MEDIAN_RANK_REWARD
    return {
        "top_50000_hits": sum(rank <= 50_000 for rank in ranks),
        "top_100000_hits": sum(rank <= 100_000 for rank in ranks),
        "top_250000_hits": sum(rank <= 250_000 for rank in ranks),
        "top_500000_hits": sum(rank <= 500_000 for rank in ranks),
        "p90_rank": p90_rank,
        "p95_rank": p95_rank,
        "tail_over_750000_count": tail_over_750000_count,
        "tail_over_900000_count": tail_over_900000_count,
        "tail_over_1000000_count": tail_over_1000000_count,
        "worst_rank_reward": round(worst_rank_reward, 6),
        "median_rank_reward": round(median_rank_reward, 6),
        "band_reward": round(band_reward, 6),
        "tail_risk_penalty": calculate_tail_risk_penalty(
            median_rank=median_rank,
            worst_rank=worst_rank,
            p95_rank=p95_rank,
            tail_over_750000_count=tail_over_750000_count,
            tail_over_900000_count=tail_over_900000_count,
            tail_over_1000000_count=tail_over_1000000_count,
            universe_size=safe_universe,
        ),
        "reward": round(worst_rank_reward + median_rank_reward + band_reward, 6),
    }


def empty_red5_summary() -> dict:
    return {
        "top_100_hits": 0,
        "top_1000_hits": 0,
        "top_10000_hits": 0,
        "median_rank": None,
        "best_rank": None,
        "missing_counts": {},
        "extra_counts": {},
        "pairs": [],
        "examples": [],
    }


def summarize_red5(target_ranks: list[TargetRank]) -> dict:
    red5_ranks = [target.red5_rank for target in target_ranks if target.red5_rank is not None]
    if not red5_ranks:
        return empty_red5_summary()

    missing_counts: Counter[int] = Counter()
    extra_counts: Counter[int] = Counter()
    pair_counts: Counter[tuple[int, int]] = Counter()
    examples = []
    for target in target_ranks:
        if (
            target.red5_rank is None
            or target.red5_numbers is None
            or target.red5_missing_number is None
            or target.red5_extra_number is None
        ):
            continue
        missing_counts[target.red5_missing_number] += 1
        extra_counts[target.red5_extra_number] += 1
        pair_counts[(target.red5_missing_number, target.red5_extra_number)] += 1
        if target.red5_rank <= 10000:
            examples.append(
                {
                    "issue": target.issue,
                    "rank": target.red5_rank,
                    "score": target.red5_score,
                    "numbers": list(target.red5_numbers),
                    "missing_number": target.red5_missing_number,
                    "extra_number": target.red5_extra_number,
                }
            )

    examples.sort(key=lambda item: (item["rank"], item["issue"]))
    pairs = [
        {"missing_number": missing, "extra_number": extra, "count": count}
        for (missing, extra), count in pair_counts.most_common(12)
    ]
    return {
        "top_100_hits": sum(target.hit_red5_top_100 for target in target_ranks),
        "top_1000_hits": sum(target.hit_red5_top_1000 for target in target_ranks),
        "top_10000_hits": sum(target.hit_red5_top_10000 for target in target_ranks),
        "median_rank": median(red5_ranks),
        "best_rank": min(red5_ranks),
        "missing_counts": {f"{number:02d}": count for number, count in sorted(missing_counts.items())},
        "extra_counts": {f"{number:02d}": count for number, count in sorted(extra_counts.items())},
        "pairs": pairs,
        "examples": examples[:12],
    }


def summarize_target_ranks(
    *,
    target_ranks: list[TargetRank],
    config: FrequencyRankerConfig,
    as_of_issue: str,
    history_fingerprint_value: str,
    train_window: int,
    train_mode: str,
    top_n: int,
    universe_size: int,
) -> dict:
    ranks = [target.rank for target in target_ranks]
    summary = {
        "config": config_dict(config),
        "as_of_issue": as_of_issue,
        "history_fingerprint": history_fingerprint_value,
        "config_hash": config_hash(config),
        "evaluated_draws": len(target_ranks),
        "top_100_hits": sum(target.hit_top_100 for target in target_ranks),
        "top_1000_hits": sum(target.hit_top_1000 for target in target_ranks),
        "top_10000_hits": sum(target.hit_top_10000 for target in target_ranks),
        "median_rank": median(ranks) if ranks else None,
        "best_rank": min(ranks) if ranks else None,
        "worst_rank": max(ranks) if ranks else None,
        "red5": summarize_red5(target_ranks),
        "rank_quality": summarize_rank_quality(ranks, universe_size=universe_size),
    }
    summary["reward"] = reward_summary(summary, universe_size=universe_size)
    summary["run_key"] = deterministic_run_key(
        strategy_key="frequency_v1",
        as_of_issue=as_of_issue,
        train_window=train_window,
        train_mode=train_mode,
        eval_window=len(target_ranks),
        top_n=top_n,
        history_fingerprint_value=history_fingerprint_value,
        config_hash_value=summary["config_hash"],
    )
    return summary


def sort_key(summary: dict) -> tuple:
    reward = summary.get("reward") or reward_summary(summary)
    red5 = summary.get("red5") if isinstance(summary.get("red5"), dict) else {}
    rank_quality = summary.get("rank_quality") if isinstance(summary.get("rank_quality"), dict) else {}
    return (
        summary["top_100_hits"],
        summary["top_1000_hits"],
        summary["top_10000_hits"],
        -int(rank_quality.get("tail_over_1000000_count") or 0),
        -int(rank_quality.get("tail_over_900000_count") or 0),
        -int(rank_quality.get("tail_over_750000_count") or 0),
        reward["objectiveScore"],
        int(red5.get("top_100_hits") or 0),
        int(red5.get("top_1000_hits") or 0),
        int(red5.get("top_10000_hits") or 0),
        -(summary.get("worst_rank") or 0),
        -(summary.get("median_rank") or 0),
        -(summary.get("best_rank") or 0),
    )


def merge_leaderboard(existing: list[dict], candidates: list[dict], *, limit: int = 12) -> list[dict]:
    by_hash: dict[str, dict] = {item["config_hash"]: item for item in existing}
    for candidate in candidates:
        current = by_hash.get(candidate["config_hash"])
        if current is None or sort_key(candidate) > sort_key(current):
            by_hash[candidate["config_hash"]] = candidate
    return sorted(by_hash.values(), key=sort_key, reverse=True)[:limit]


def normalize_red5_summary(raw_red5: object) -> dict:
    red5 = empty_red5_summary()
    if not isinstance(raw_red5, dict):
        return red5
    for field in ("top_100_hits", "top_1000_hits", "top_10000_hits"):
        red5[field] = int(raw_red5.get(field) or 0)
    for field in ("median_rank", "best_rank"):
        value = raw_red5.get(field)
        red5[field] = float(value) if isinstance(value, int | float) else None
    if isinstance(raw_red5.get("missing_counts"), dict):
        red5["missing_counts"] = {str(key): int(value) for key, value in raw_red5["missing_counts"].items()}
    if isinstance(raw_red5.get("extra_counts"), dict):
        red5["extra_counts"] = {str(key): int(value) for key, value in raw_red5["extra_counts"].items()}
    if isinstance(raw_red5.get("pairs"), list):
        red5["pairs"] = [item for item in raw_red5["pairs"] if isinstance(item, dict)]
    if isinstance(raw_red5.get("examples"), list):
        red5["examples"] = [item for item in raw_red5["examples"] if isinstance(item, dict)]
    return red5


def normalize_rank_quality_summary(raw_rank_quality: object) -> dict:
    rank_quality = empty_rank_quality_summary()
    if not isinstance(raw_rank_quality, dict):
        return rank_quality
    for field in (
        "top_50000_hits",
        "top_100000_hits",
        "top_250000_hits",
        "top_500000_hits",
        "tail_over_750000_count",
        "tail_over_900000_count",
        "tail_over_1000000_count",
    ):
        rank_quality[field] = int(raw_rank_quality.get(field) or 0)
    for field in ("p90_rank", "p95_rank", "worst_rank_reward", "median_rank_reward", "band_reward", "tail_risk_penalty", "reward"):
        value = raw_rank_quality.get(field)
        rank_quality[field] = float(value) if isinstance(value, int | float) else 0.0
    return rank_quality


def normalize_summary(raw_summary: object, *, universe_size: int) -> dict | None:
    if not isinstance(raw_summary, dict) or not isinstance(raw_summary.get("config"), dict):
        return None
    required_fields = (
        "as_of_issue",
        "history_fingerprint",
        "evaluated_draws",
        "top_100_hits",
        "top_1000_hits",
        "top_10000_hits",
        "median_rank",
        "best_rank",
        "worst_rank",
        "run_key",
    )
    if any(field not in raw_summary or raw_summary[field] is None for field in required_fields):
        return None
    summary = dict(raw_summary)
    normalized_config = config_dict(FrequencyRankerConfig())
    normalized_config.update({field: float(value) for field, value in raw_summary["config"].items()})
    summary["config"] = normalized_config
    summary["config_hash"] = config_hash(FrequencyRankerConfig(**summary["config"]))
    summary["red5"] = normalize_red5_summary(summary.get("red5"))
    summary["rank_quality"] = normalize_rank_quality_summary(summary.get("rank_quality"))
    rank_quality = summary["rank_quality"]
    if not rank_quality.get("p90_rank"):
        rank_quality["p90_rank"] = summary["median_rank"]
    if not rank_quality.get("p95_rank"):
        rank_quality["p95_rank"] = summary["worst_rank"]
    if not rank_quality.get("tail_over_750000_count") and summary["worst_rank"] > 750_000:
        rank_quality["tail_over_750000_count"] = 1
    if not rank_quality.get("tail_over_900000_count") and summary["worst_rank"] > 900_000:
        rank_quality["tail_over_900000_count"] = 1
    if not rank_quality.get("tail_over_1000000_count") and summary["worst_rank"] > 1_000_000:
        rank_quality["tail_over_1000000_count"] = 1
    if not rank_quality.get("tail_risk_penalty"):
        rank_quality["tail_risk_penalty"] = calculate_tail_risk_penalty(
            median_rank=summary["median_rank"],
            worst_rank=summary["worst_rank"],
            p95_rank=rank_quality.get("p95_rank"),
            tail_over_750000_count=int(rank_quality.get("tail_over_750000_count") or 0),
            tail_over_900000_count=int(rank_quality.get("tail_over_900000_count") or 0),
            tail_over_1000000_count=int(rank_quality.get("tail_over_1000000_count") or 0),
            universe_size=universe_size,
        )
    summary["reward"] = reward_summary(summary, universe_size=universe_size)
    return summary


def load_prior_supervisor_candidates(
    *,
    output_dir: Path,
    current_status_path: Path,
    as_of_issue: str,
    history_fingerprint_value: str,
    train_window: int,
    train_mode: str,
    eval_window: int,
    top_n: int,
    universe_size: int,
    limit: int = 12,
) -> list[dict]:
    candidates: list[dict] = []
    for status_path in sorted(output_dir.glob("training-supervisor-*.json")):
        if status_path == current_status_path:
            continue
        try:
            status = json.loads(status_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if (
            status.get("train_window") != train_window
            or status.get("train_mode") != train_mode
            or status.get("eval_window") != eval_window
            or status.get("top_n") != top_n
        ):
            continue
        raw_candidates = [status.get("best")]
        for round_info in status.get("rounds") or []:
            if isinstance(round_info, dict):
                raw_candidates.append(round_info.get("best"))
                raw_candidates.extend(round_info.get("top_results") or [])
        for raw_candidate in raw_candidates:
            candidate = normalize_summary(raw_candidate, universe_size=universe_size)
            if (
                candidate
                and candidate["as_of_issue"] == as_of_issue
                and candidate["history_fingerprint"] == history_fingerprint_value
            ):
                candidates = merge_leaderboard(candidates, [candidate], limit=limit)
    return candidates


def evaluate_configs(
    *,
    history: list,
    ranked_universe,
    configs: tuple[FrequencyRankerConfig, ...],
    train_window: int,
    train_mode: str,
    eval_window: int,
    top_n: int,
    workers: int,
    pool,
    progress_interval: int,
    round_index: int,
    progress_callback: Callable[[dict], None] | None = None,
) -> list[dict]:
    start_index = max(train_window, len(history) - eval_window)
    total_targets = len(history) - start_index
    target_rank_lists: list[list[TargetRank]] = [[] for _ in configs]
    started = time.time()

    for progress_index, target_index in enumerate(range(start_index, len(history)), start=1):
        train_start = 0 if train_mode == "expanding" else max(0, target_index - train_window)
        train_history = history[train_start:target_index]
        target_draw = history[target_index]
        issue = history_issue(target_draw)
        numbers = history_numbers(target_draw)
        ranked_targets = rank_target_grid_with_red5(
            target_numbers=numbers,
            train_history=train_history,
            configs=configs,
            ranked_universe=ranked_universe,
            target_draw_date=history_draw_date(target_draw),
            workers=workers,
            pool=pool,
        )
        for config_index, (rank, score, red5_match) in enumerate(ranked_targets):
            target_rank_lists[config_index].append(
                TargetRank(
                    issue=issue,
                    rank=rank,
                    score=score,
                    hit_top_100=rank <= 100,
                    hit_top_1000=rank <= 1000,
                    hit_top_10000=rank <= 10000,
                    red5_rank=red5_match.rank if red5_match else None,
                    red5_score=red5_match.score if red5_match else None,
                    red5_numbers=red5_match.numbers if red5_match else None,
                    red5_missing_number=red5_match.missing_number if red5_match else None,
                    red5_extra_number=red5_match.extra_number if red5_match else None,
                    hit_red5_top_100=red5_match is not None and red5_match.rank <= 100,
                    hit_red5_top_1000=red5_match is not None and red5_match.rank <= 1000,
                    hit_red5_top_10000=red5_match is not None and red5_match.rank <= 10000,
                )
            )
        if progress_interval > 0 and (
            progress_index == 1 or progress_index == total_targets or progress_index % progress_interval == 0
        ):
            elapsed = time.time() - started
            progress = training_progress_payload(
                round_index=round_index,
                target_index=progress_index,
                target_total=total_targets,
                issue=issue,
                train_draws=len(train_history),
                elapsed_seconds=elapsed,
            )
            log(
                f"round={round_index} target={progress_index}/{total_targets} "
                f"issue={issue} train_draws={len(train_history)} elapsed={elapsed:.1f}s"
            )
            if progress_callback is not None:
                progress_callback(progress)

    as_of_issue = history_issue(history[-1])
    history_fingerprint_value = fingerprint_history(history)
    summaries = [
        summarize_target_ranks(
            target_ranks=target_ranks,
            config=config,
            as_of_issue=as_of_issue,
            history_fingerprint_value=history_fingerprint_value,
            train_window=train_window,
            train_mode=train_mode,
            top_n=top_n,
            universe_size=len(ranked_universe),
        )
        for config, target_ranks in zip(configs, target_rank_lists, strict=True)
    ]
    summaries.sort(key=sort_key, reverse=True)
    return summaries


def write_status(output_path: Path, status: dict, *, event_url: str | None = None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(status, ensure_ascii=False, indent=2))
    if event_url is not None:
        post_training_event(status, event_url=event_url)


def write_report(report_path: Path, status: dict) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    rounds = "\n".join(
        (
            f"| {round_info['round']} | {round_info['phase']} | {round_info['best']['top_10000_hits']} | "
            f"{round_info['best']['top_1000_hits']} | {round_info['best']['top_100_hits']} | "
            f"{round_info['best']['red5']['top_100_hits']} | {round_info['best']['red5']['top_10000_hits']} | "
            f"{round_info['best']['rank_quality']['top_50000_hits']} | {round_info['best']['worst_rank']} | "
            f"{round_info['best']['rank_quality'].get('tail_over_1000000_count', 0)} | "
            f"{round_info['best']['median_rank']} | `{json.dumps(round_info['best']['config'], sort_keys=True)}` |"
        )
        for round_info in status["rounds"]
    )
    best = status["best"]
    report_path.write_text(
        f"""# DEHPS 24h Training Supervisor Report

- Run id: `{status["run_id"]}`
- Started at: {status["started_at"]}
- Updated at: {status["updated_at"]}
- Deadline: {status["deadline"]}
- Status: {status["status"]}
- Train mode: `{status["train_mode"]}`
- Train window: {status["train_window"]}
- Eval window: {status["eval_window"]}
- Top-N: {status["top_n"]}
- Workers: {status["workers"]}
- Memory budget GB: {status["memory_budget_gb"]}
- Universe size: {status["universe_size"]}
- Latest qian-kun pattern: {status["qian_kun"]["latest_issue"]} {status["qian_kun"]["latest_label"]} `{status["qian_kun"]["latest_pattern"]}`

## Current Best

```json
{json.dumps(best, ensure_ascii=False, indent=2, sort_keys=True)}
```

## Rounds

| Round | Phase | Top10000 | Top1000 | Top100 | Red5 Top100 | Red5 Top10000 | Top50000 | Worst rank | >100万 | Median rank | Config |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{rounds}

## Guardrail

The supervisor optimizes historical expanding walk-forward rank coverage. Any large jump must be checked for leakage and validated on future frozen draws before promotion.
"""
    )


def run_supervisor(
    *,
    duration_hours: float,
    train_window: int,
    eval_window: int,
    top_n: int,
    as_of_issue: str | None,
    workers: int | None,
    train_mode: str,
    history_scope: HistoryScope,
    regime_years: int,
    output_dir: Path,
    progress_interval: int,
    max_configs_per_round: int,
    memory_budget_gb: int,
    event_url: str | None = None,
) -> dict:
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    started_at = datetime.now()
    deadline = started_at + timedelta(hours=duration_hours)
    resolved_event_url = training_event_url(event_url)
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / f"training-supervisor-{run_id}.json"
    report_path = output_dir / f"training-supervisor-{run_id}.md"

    with get_connection() as conn:
        selection = select_history(conn, scope=history_scope, as_of_issue=as_of_issue, regime_years=regime_years)
        universe = load_red_combination_universe(conn)

    worker_count = normalize_worker_count(workers)
    training_history = selection.dated_history
    as_of_issue_value = history_issue(training_history[-1])
    history_fingerprint_value = fingerprint_history(training_history)
    prior_leaderboard = load_prior_supervisor_candidates(
        output_dir=output_dir,
        current_status_path=status_path,
        as_of_issue=as_of_issue_value,
        history_fingerprint_value=history_fingerprint_value,
        train_window=train_window,
        train_mode=train_mode,
        eval_window=eval_window,
        top_n=top_n,
        universe_size=len(universe),
    )
    log(
        f"run_id={run_id} building static universe rows={len(universe)} workers={worker_count} "
        f"memory_budget_gb={memory_budget_gb}"
    )
    if prior_leaderboard:
        log(
            "seeded_prior_best="
            f"top100={prior_leaderboard[0]['top_100_hits']} "
            f"top1000={prior_leaderboard[0]['top_1000_hits']} "
            f"top10000={prior_leaderboard[0]['top_10000_hits']} "
            f"run_key={prior_leaderboard[0]['run_key']}"
        )
    ranked_universe = build_ranked_universe(universe)
    pool = create_worker_pool(worker_count, ranked_universe)

    best_summary: dict | None = prior_leaderboard[0] if prior_leaderboard else None
    base_config = FrequencyRankerConfig(**best_summary["config"]) if best_summary else FrequencyRankerConfig()
    leaderboard: list[dict] = prior_leaderboard
    rounds: list[dict] = []
    status = {
        "run_id": run_id,
        "started_at": started_at.isoformat(timespec="seconds"),
        "updated_at": started_at.isoformat(timespec="seconds"),
        "deadline": deadline.isoformat(timespec="seconds"),
        "status": "running",
        "pid": os.getpid(),
        "history_scope": selection.scope,
        "regime_years": selection.regime_years,
        "regime_start_date": selection.start_date.isoformat() if selection.start_date else "",
        "train_mode": train_mode,
        "train_window": train_window,
        "eval_window": eval_window,
        "top_n": top_n,
        "workers": worker_count,
        "memory_budget_gb": memory_budget_gb,
        "universe_size": len(ranked_universe),
        "qian_kun": qian_kun_distribution(selection.history),
        "rounds": rounds,
        "best": best_summary,
        "latest_progress": None,
        "status_path": str(status_path),
        "report_path": str(report_path),
    }

    def publish_progress(progress: dict) -> None:
        status["latest_progress"] = progress
        status["updated_at"] = progress["logged_at"]
        write_status(status_path, status, event_url=resolved_event_url)

    write_status(status_path, status, event_url=resolved_event_url)

    try:
        round_index = 0
        while round_index == 0 or datetime.now() < deadline:
            phase, step = PHASES[round_index % len(PHASES)]
            elite_configs = tuple(FrequencyRankerConfig(**summary["config"]) for summary in leaderboard[:4])
            configs = tuple(
                generate_configs(
                    base_config,
                    phase=phase,
                    step=step,
                    max_configs=max_configs_per_round,
                    elite_configs=elite_configs,
                )
            )
            log(f"round={round_index + 1} phase={phase} step={step} configs={len(configs)} base={config_dict(base_config)}")
            summaries = evaluate_configs(
                history=training_history,
                ranked_universe=ranked_universe,
                configs=configs,
                train_window=train_window,
                train_mode=train_mode,
                eval_window=eval_window,
                top_n=top_n,
                workers=worker_count,
                pool=pool,
                progress_interval=progress_interval,
                round_index=round_index + 1,
                progress_callback=publish_progress,
            )
            round_best = summaries[0]
            leaderboard = merge_leaderboard(leaderboard, summaries[: min(8, len(summaries))])
            improved = best_summary is None or sort_key(round_best) > sort_key(best_summary)
            if improved:
                best_summary = round_best
                base_config = FrequencyRankerConfig(**round_best["config"])
                log(f"round={round_index + 1} retained_new_best={round_best}")
            else:
                log(f"round={round_index + 1} no_improvement best_top10000={best_summary['top_10000_hits'] if best_summary else 'n/a'}")

            rounds.append(
                {
                    "round": round_index + 1,
                    "phase": phase,
                    "step": step,
                    "config_count": len(configs),
                    "improved": improved,
                    "best": round_best,
                    "top_results": summaries[: min(5, len(summaries))],
                }
            )
            status["updated_at"] = datetime.now().isoformat(timespec="seconds")
            status["best"] = best_summary
            write_status(status_path, status, event_url=resolved_event_url)
            write_report(report_path, status)
            round_index += 1

        status["status"] = "completed"
    except KeyboardInterrupt:
        status["status"] = "interrupted"
        raise
    except Exception as exc:
        status["status"] = "failed"
        status["error_message"] = str(exc)
        raise
    finally:
        if pool is not None:
            pool.close()
            pool.join()
        status["updated_at"] = datetime.now().isoformat(timespec="seconds")
        status["best"] = best_summary
        write_status(status_path, status, event_url=resolved_event_url)
        write_report(report_path, status)
        log(f"finished status={status['status']} status_path={status_path} report_path={report_path}")

    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-hours", type=float, default=24.0)
    parser.add_argument("--train-window", type=int, default=900)
    parser.add_argument("--eval-window", type=int, default=100)
    parser.add_argument("--top-n", type=int, default=10000)
    parser.add_argument("--as-of-issue")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--train-mode", choices=["expanding", "rolling"], default="expanding")
    parser.add_argument("--history-scope", choices=["full_history_audit", "current_regime_default"], default="current_regime_default")
    parser.add_argument("--regime-years", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=ROOT_DIR / "data/output/optimization")
    parser.add_argument("--progress-interval", type=int, default=10)
    parser.add_argument("--max-configs-per-round", type=int, default=28)
    parser.add_argument("--memory-budget-gb", type=int, default=20)
    parser.add_argument("--event-url", default=os.getenv("DEHPS_TRAINING_EVENT_URL", DEFAULT_TRAINING_EVENT_URL))
    args = parser.parse_args()
    print(
        json.dumps(
            run_supervisor(
                duration_hours=args.duration_hours,
                train_window=args.train_window,
                eval_window=args.eval_window,
                top_n=args.top_n,
                as_of_issue=args.as_of_issue,
                workers=args.workers,
                train_mode=args.train_mode,
                history_scope=args.history_scope,
                regime_years=args.regime_years,
                output_dir=args.output_dir,
                progress_interval=args.progress_interval,
                max_configs_per_round=args.max_configs_per_round,
                memory_budget_gb=args.memory_budget_gb,
                event_url=args.event_url,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
