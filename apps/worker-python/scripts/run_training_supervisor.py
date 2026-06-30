from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta
from math import ceil, comb, isfinite, sqrt
import multiprocessing as mp
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
from dehps.optimization.neural_kdj_advisor import (
    NeuralKdjOffsetAdvice,
    neural_kdj_advice_to_frequency_ranker_config_candidates,
    numpy_neural_kdj_offset_v0,
)
from dehps.optimization.next_candidates import refresh_training_next_candidates_current
from dehps.optimization.ridge_kdj_advisor import (
    RidgeKdjOffsetAdvice,
    numpy_ridge_kdj_offset_v0,
    ridge_kdj_advice_to_frequency_ranker_config_candidates,
)
from dehps.optimization.regime import HistoryScope, select_history
from dehps.optimization.target_inversion import invert_targets_for_summary, target_inversion_payload
from dehps.optimization.weight_kdj import (
    WeightKdjAdvice,
    weight_kdj_advice_from_signals,
    weight_kdj_advice_scenario_counts,
)
from dehps.runtime.heavy_job import apply_cpu_thread_env_defaults, heavy_job_lock
from dehps.optimization.walk_forward import (
    TargetRank,
    build_ranked_universe,
    config_hash,
    create_worker_pool,
    deterministic_run_key,
    fingerprint_history,
    normalize_worker_count,
    rank_target_grid,
    rank_target_grid_with_red5,
)
from dehps.storage.postgres_store import (
    ensure_training_round_results_schema,
    ensure_training_supervisor_best_schema,
    ensure_training_target_weight_inversions_schema,
    load_red_combination_universe,
    load_training_round_carryover_candidate_summaries,
    load_training_supervisor_best_carryover_candidate_summaries,
    load_training_supervisor_best_candidate_summaries,
    upsert_training_round_result,
    upsert_training_supervisor_best,
    upsert_training_target_weight_inversion,
)
from dehps.storage.postgres_store import load_training_round_candidate_summaries
from dehps.storage.postgres_store import load_recent_training_weight_signals


PRIMARY_FIELDS = ("structural_weight", "frequency_weight", "omission_weight")
CONTEXT_FIELDS = (
    "short_hot_frequency_weight",
    "long_omission_cooldown_weight",
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
PHASE_SEARCH_FIELDS = {
    "micro": (
        "short_hot_frequency_weight",
        "long_omission_cooldown_weight",
        "weekday_trend_weight",
        "stable_range_weight",
        "parity_ratio_weight",
        "zone_ratio_weight",
        "dynamic_parity_transition_weight",
        "red_omission_shape_weight",
        "sum_span_omission_weight",
        "tail_distribution_weight",
        "repeat_trend_weight",
        "consecutive_trend_weight",
    ),
    "small": (
        "short_hot_frequency_weight",
        "long_omission_cooldown_weight",
        "tail_distribution_weight",
        "sum_tail_weight",
        "mod012_weight",
        "prime_composite_weight",
        "big_small_ratio_weight",
        "first_last_sum_weight",
        "span_trend_weight",
        "sum_trend_weight",
        "ac_trend_weight",
        "weekday_trend_weight",
    ),
    "medium": (
        "short_hot_frequency_weight",
        "long_omission_cooldown_weight",
        "recent_neighbor_weight",
        "lagged_consecutive_weight",
        "recent_gap_shape_weight",
        "recent_sum_span_weight",
        "previous_overlap_weight",
        "previous_consecutive_weight",
        "previous_zone_shape_weight",
        "qian_kun_pattern_weight",
        "stable_range_weight",
        "red_omission_shape_weight",
    ),
    "large": CONTEXT_FIELDS,
}
DEFAULT_UNIVERSE_SIZE = 1_107_568
DEFAULT_TRAINING_EVENT_URL = "http://127.0.0.1:3000/training-events/status"
TRAINING_EVENT_TIMEOUT_SECONDS = 3.0
TRAINING_EVENT_WARNING_INTERVAL_SECONDS = 60.0
_TARGET_WORKER_UNIVERSE = None
TOP_100_REWARD = 1200
TOP_1000_REWARD = 180
TOP_10000_REWARD = 3
BASELINE_UNIQUE_TOP_100_REWARD = 250
BASELINE_UNIQUE_TOP_1000_REWARD = 60
BASELINE_UNIQUE_TOP_10000_REWARD = 4
BASELINE_OVERLAP_TOP_100_PENALTY = 80
BASELINE_OVERLAP_TOP_1000_PENALTY = 20
BASELINE_OVERLAP_TOP_10000_PENALTY = 3
BASELINE_OVERLAP_LABELS = ("null_baseline", "default_baseline")
RED5_TOP_100_REWARD = 5
RED5_TOP_1000_REWARD = 1
RED5_TOP_10000_REWARD = 0.2
RANK_TOP_50000_REWARD = 0.10
RANK_TOP_100000_REWARD = 0.05
RANK_TOP_250000_REWARD = 0.02
RANK_TOP_500000_REWARD = 0.01
WORST_RANK_REWARD = 6.0
MEDIAN_RANK_REWARD = 8.0
TAIL_OVER_750000_PENALTY = 0.15
TAIL_OVER_900000_PENALTY = 0.50
TAIL_OVER_1000000_PENALTY = 1.25
WORST_RANK_PENALTY_WEIGHT = 12.0
P95_RANK_PENALTY_WEIGHT = 6.0
MEDIAN_RANK_PENALTY_WEIGHT = 2.0
EARLY_BROAD_ROUNDS = 24
MID_SEARCH_ROUNDS = 72
PHASES = (
    ("large", 0.20),
    ("large", 0.15),
    ("medium", 0.10),
    ("large", 0.12),
)
MID_PHASES = (
    ("medium", 0.08),
    ("medium", 0.06),
    ("small", 0.04),
)
LATE_PHASES = (
    ("small", 0.03),
    ("micro", 0.015),
    ("micro", 0.01),
    ("small", 0.02),
)
EARLY_SEARCH_BASE_MIN_DISTANCE = 0.08
MID_SEARCH_BASE_MIN_DISTANCE = 0.04
LATE_SEARCH_BASE_MIN_DISTANCE = 0.015
STAGNATION_THRESHOLD = 16
RANK_HOMOGENEITY_STAGNATION_THRESHOLD = STAGNATION_THRESHOLD
RANK_HOMOGENEITY_WINDOW = 12
RANK_HOMOGENEITY_MAX_UNIQUE_SIGNATURES = 4
CANDIDATE_BUDGET_SHARES = {
    "exploitation": 0.40,
    "exploration": 0.30,
    "replay": 0.20,
    "baseline": 0.10,
}
DEFAULT_RECENCY_CANARY_BUDGET_SHARE = 0.12
RECENCY_CANARY_FIELDS = ("short_hot_frequency_weight", "long_omission_cooldown_weight")
DEFAULT_WEIGHT_KDJ_BUDGET_SHARE = 0.22
DEFAULT_WEIGHT_KDJ_MIN_OBJECTIVE_DELTA = 0.0
DEFAULT_WEIGHT_KDJ_MIN_ABS_OFFSET = 0.005
DEFAULT_WEIGHT_KDJ_SLOPE_WINDOW = 3
DEFAULT_WEIGHT_KDJ_NEUTRAL_BAND = 5.0
DEFAULT_RIDGE_KDJ_BUDGET_SHARE = 0.08
DEFAULT_RIDGE_KDJ_STEP = 0.01
DEFAULT_RIDGE_KDJ_ALPHA = 1.0
DEFAULT_RIDGE_KDJ_MIN_CONFIDENCE = 0.0
DEFAULT_RIDGE_KDJ_MIN_TRAIN_ROWS = 12
DEFAULT_RIDGE_KDJ_MIN_VALIDATION_ROWS = 4
DEFAULT_NEURAL_KDJ_BUDGET_SHARE = 0.10
DEFAULT_NEURAL_KDJ_STEP = 0.01
DEFAULT_NEURAL_KDJ_SEED = 17
DEFAULT_NEURAL_KDJ_HIDDEN_UNITS = 8
DEFAULT_NEURAL_KDJ_EPOCHS = 120
DEFAULT_NEURAL_KDJ_MIN_CONFIDENCE = 0.0
DEFAULT_TARGET_WEIGHT_INVERSION_BUDGET_SHARE = 0.20
DEFAULT_TARGET_WEIGHT_INVERSION_MAX_CANDIDATES = 8
DEFAULT_TARGET_WEIGHT_INVERSION_MAX_TARGETS = 100
DEFAULT_TARGET_WEIGHT_INVERSION_MAX_DELTAS_PER_TARGET = 8
TARGET_WEIGHT_INVERSION_STALE_STAGNATION_THRESHOLD = 64
NEAR_MISS_INVERSION_STAGNATION_THRESHOLD = STAGNATION_THRESHOLD
PROBABILITY_CALIBRATION_STAGNATION_THRESHOLD = STAGNATION_THRESHOLD
PROBABILITY_FOCUS_HOLD_ROUNDS = 4
PROBABILITY_PRIMARY_GATE_STAGNATION_THRESHOLD = TARGET_WEIGHT_INVERSION_STALE_STAGNATION_THRESHOLD
SOURCE_FRONTIER_STAGNATION_THRESHOLD = max(4, STAGNATION_THRESHOLD // 4)
SOURCE_FRONTIER_TOP_LIMIT = 12
NEAR_MISS_INVERSION_CUTOFF_BANDS = (
    {"cutoff": 100, "upper": 500, "max_targets": 4},
    {"cutoff": 1000, "upper": 5000, "max_targets": 4},
    {"cutoff": 10000, "upper": 50000, "max_targets": 4},
)
MAX_FROZEN_VALIDATION_WINDOW = 20


def _target_pool_context():
    return mp.get_context("fork") if "fork" in mp.get_all_start_methods() else mp.get_context()


def log(message: str) -> None:
    print(f"[supervisor] {datetime.now().isoformat(timespec='seconds')} {message}", file=sys.stderr, flush=True)


_TRAINING_EVENT_WARNING_LAST: dict[str, float] = {}


def should_log_training_event_warning(key: str, *, now: float | None = None) -> bool:
    current = time.monotonic() if now is None else now
    last = _TRAINING_EVENT_WARNING_LAST.get(key)
    if last is not None and current - last < TRAINING_EVENT_WARNING_INTERVAL_SECONDS:
        return False
    _TRAINING_EVENT_WARNING_LAST[key] = current
    return True


def training_event_url(value: str | None = None) -> str | None:
    resolved = value if value is not None else os.getenv("DEHPS_TRAINING_EVENT_URL", DEFAULT_TRAINING_EVENT_URL)
    return resolved.strip() if resolved and resolved.strip() else None


def training_event_payload(status: dict) -> dict:
    return {
        "run_id": status.get("run_id"),
        "status": status.get("status"),
        "pid": status.get("pid"),
        "updated_at": status.get("updated_at"),
        "latest_progress": status.get("latest_progress"),
        "search_base": status.get("search_base"),
        "status_path": status.get("status_path"),
        "report_path": status.get("report_path"),
    }


def resolve_training_deadline(started_at: datetime, duration_hours: float) -> datetime | None:
    if duration_hours <= 0:
        return None
    return started_at + timedelta(hours=duration_hours)


def should_continue_training(round_index: int, deadline: datetime | None, *, now: datetime | None = None) -> bool:
    if round_index == 0:
        return True
    if deadline is None:
        return True
    return (now or datetime.now()) < deadline


def post_training_event(status: dict, *, event_url: str | None = None, timeout: float = TRAINING_EVENT_TIMEOUT_SECONDS) -> bool:
    resolved_url = training_event_url(event_url)
    if not resolved_url:
        return False
    try:
        payload = json.dumps(training_event_payload(status), ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            resolved_url,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        if should_log_training_event_warning(resolved_url):
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


def add_unique_until(
    configs: list[FrequencyRankerConfig],
    seen: set[str],
    config: FrequencyRankerConfig,
    *,
    limit: int,
) -> None:
    if len(configs) < limit:
        add_unique(configs, seen, config)


def rank_signature_hash(summary: dict | None) -> str:
    signature = summary_rank_vector_signature(summary)
    if signature is None:
        return ""
    payload = json.dumps(signature, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def rank_homogeneity_guardrail(
    rounds: list[dict],
    *,
    stagnation_rounds: int,
    window: int = RANK_HOMOGENEITY_WINDOW,
    max_unique_signatures: int = RANK_HOMOGENEITY_MAX_UNIQUE_SIGNATURES,
) -> dict:
    signatures: list[str] = []
    for round_info in rounds[-max(0, window):]:
        prefilter = round_info.get("prefilter") if isinstance(round_info.get("prefilter"), dict) else {}
        signature = prefilter.get("round_best_rank_signature_hash")
        if isinstance(signature, str) and signature:
            signatures.append(signature)
    unique_signatures = sorted(set(signatures))
    active = (
        stagnation_rounds >= RANK_HOMOGENEITY_STAGNATION_THRESHOLD
        and len(signatures) >= window
        and len(unique_signatures) <= max_unique_signatures
    )
    reason = None
    if active:
        reason = "stale_rank_signature_cycle"
    elif stagnation_rounds < RANK_HOMOGENEITY_STAGNATION_THRESHOLD:
        reason = "below_stagnation_threshold"
    elif len(signatures) < window:
        reason = "insufficient_signature_window"
    else:
        reason = "rank_signatures_still_diverse"
    return {
        "active": active,
        "reason": reason,
        "stagnation_rounds": stagnation_rounds,
        "stagnation_threshold": RANK_HOMOGENEITY_STAGNATION_THRESHOLD,
        "window": window,
        "observed": len(signatures),
        "unique_signature_count": len(unique_signatures),
        "max_unique_signatures": max_unique_signatures,
        "signatures": unique_signatures[:8],
    }


def stagnation_restart_candidate_configs(
    base: FrequencyRankerConfig,
    *,
    max_configs: int,
    round_index: int,
    stagnation_rounds: int,
) -> tuple[FrequencyRankerConfig, ...]:
    if max_configs <= 0:
        return ()
    configs: list[FrequencyRankerConfig] = []
    seen: set[str] = set()
    primary_extremes = (
        {"structural_weight": 1.15, "frequency_weight": 0.05, "omission_weight": 0.05},
        {"structural_weight": 0.05, "frequency_weight": 1.15, "omission_weight": 0.05},
        {"structural_weight": 0.05, "frequency_weight": 0.05, "omission_weight": 1.15},
        {"structural_weight": 0.70, "frequency_weight": 0.70, "omission_weight": 0.05},
        {"structural_weight": 0.70, "frequency_weight": 0.05, "omission_weight": 0.70},
        {"structural_weight": 0.05, "frequency_weight": 0.70, "omission_weight": 0.70},
    )
    context_patterns = (
        {
            "short_hot_frequency_weight": 0.30,
            "long_omission_cooldown_weight": -0.30,
            "tail_distribution_weight": -0.30,
            "red_omission_shape_weight": 0.30,
        },
        {
            "short_hot_frequency_weight": -0.30,
            "long_omission_cooldown_weight": 0.30,
            "recent_gap_shape_weight": 0.30,
            "sum_span_omission_weight": -0.30,
        },
        {
            "previous_zone_shape_weight": -0.30,
            "dynamic_parity_transition_weight": 0.30,
            "prime_composite_weight": 0.30,
            "mod012_weight": -0.30,
        },
        {
            "weekday_trend_weight": -0.30,
            "stable_range_weight": 0.30,
            "consecutive_trend_weight": 0.30,
            "repeat_trend_weight": -0.30,
        },
    )
    for primary in primary_extremes:
        add_unique(configs, seen, FrequencyRankerConfig(**{**config_dict(base), **primary}))
        if len(configs) >= max_configs:
            return tuple(configs[:max_configs])
    for primary in primary_extremes:
        for context in context_patterns:
            add_unique(configs, seen, FrequencyRankerConfig(**{**config_dict(base), **primary, **context}))
            if len(configs) >= max_configs:
                return tuple(configs[:max_configs])
    rng = random.Random(deterministic_seed("stagnation_restart", round_index, stagnation_rounds))
    while len(configs) < max_configs:
        values = config_dict(base)
        for field in PRIMARY_FIELDS:
            values[field] = rng.choice((0.05, 0.20, 0.85, 1.15))
        for field in rng.sample(tuple(CONTEXT_FIELDS), k=min(6, len(CONTEXT_FIELDS))):
            values[field] = rng.choice((-0.30, -0.20, 0.20, 0.30))
        add_unique(configs, seen, FrequencyRankerConfig(**values))
        if len(seen) > max_configs * 8:
            break
    return tuple(configs[:max_configs])


def phase_for_round(round_index: int, *, stagnation_rounds: int = 0) -> tuple[str, float, str]:
    if stagnation_rounds >= STAGNATION_THRESHOLD:
        phase, step = PHASES[round_index % len(PHASES)]
        return "large", max(step, 0.15), "stagnation_broad"
    if round_index < EARLY_BROAD_ROUNDS:
        phase, step = PHASES[round_index % len(PHASES)]
        return phase, step, "early_broad"
    if round_index < MID_SEARCH_ROUNDS:
        phase, step = MID_PHASES[(round_index - EARLY_BROAD_ROUNDS) % len(MID_PHASES)]
        return phase, step, "mid_search"
    phase, step = LATE_PHASES[(round_index - MID_SEARCH_ROUNDS) % len(LATE_PHASES)]
    return phase, step, "late_refine"


def search_base_min_distance_for_phase(phase_stage: str) -> float:
    if phase_stage in {"early_broad", "stagnation_broad"}:
        return EARLY_SEARCH_BASE_MIN_DISTANCE
    if phase_stage == "mid_search":
        return MID_SEARCH_BASE_MIN_DISTANCE
    return LATE_SEARCH_BASE_MIN_DISTANCE


def _reserved_candidate_count(max_configs: int, budget_share: float, *, available: int) -> int:
    if max_configs <= 0 or available <= 0 or budget_share <= 0:
        return 0
    share = min(1.0, max(0.0, budget_share))
    return min(available, max(1, int(ceil(max_configs * share))))


def _target_weight_inversion_has_validation_lift(latest: dict | None) -> bool:
    if not isinstance(latest, dict):
        return False
    for advice in latest.get("advice") or ():
        if not isinstance(advice, dict) or advice.get("decision") != "selected":
            continue
        validation_metric = advice.get("validation_metric")
        baseline_metric = advice.get("baseline_metric")
        if validation_metric is None or baseline_metric is None:
            continue
        try:
            if float(validation_metric) > float(baseline_metric):
                return True
        except (TypeError, ValueError):
            continue
    return False


def target_weight_inversion_budget_guardrail(
    configured_share: float,
    *,
    latest: dict | None,
    stagnation_rounds: int,
) -> dict:
    effective_share = max(0.0, configured_share)
    active = (
        effective_share > 0
        and stagnation_rounds >= TARGET_WEIGHT_INVERSION_STALE_STAGNATION_THRESHOLD
        and isinstance(latest, dict)
        and latest.get("status", "ready") == "ready"
        and not _target_weight_inversion_has_validation_lift(latest)
    )
    if active:
        effective_share = 0.0
    return {
        "active": active,
        "configured_share": configured_share,
        "effective_share": effective_share,
        "stagnation_rounds": stagnation_rounds,
        "threshold": TARGET_WEIGHT_INVERSION_STALE_STAGNATION_THRESHOLD,
        "reason": "stale_no_validation_lift" if active else None,
    }


def candidate_budget(
    max_configs: int,
    *,
    recency_canary_budget_share: float = 0.0,
    weight_kdj_budget_share: float = 0.0,
    ridge_kdj_budget_share: float = 0.0,
    neural_kdj_budget_share: float = 0.0,
    target_weight_inversion_budget_share: float = 0.0,
    target_weight_inversion_available: int = 0,
    target_weight_inversion_max_candidates: int = DEFAULT_TARGET_WEIGHT_INVERSION_MAX_CANDIDATES,
) -> dict[str, int]:
    if max_configs <= 0:
        counts = {name: 0 for name in CANDIDATE_BUDGET_SHARES}
        if recency_canary_budget_share > 0:
            counts["recency_canary"] = 0
        if weight_kdj_budget_share > 0:
            counts["weight_kdj"] = 0
        if ridge_kdj_budget_share > 0:
            counts["ridge_kdj"] = 0
        if neural_kdj_budget_share > 0:
            counts["neural_kdj"] = 0
        if target_weight_inversion_budget_share > 0:
            counts["target_weight_inversion"] = 0
        return counts
    weight_kdj_count = _reserved_candidate_count(max_configs, weight_kdj_budget_share, available=max_configs)
    ridge_kdj_count = _reserved_candidate_count(
        max_configs,
        ridge_kdj_budget_share,
        available=max_configs - weight_kdj_count,
    )
    neural_kdj_count = _reserved_candidate_count(
        max_configs,
        neural_kdj_budget_share,
        available=max_configs - weight_kdj_count - ridge_kdj_count,
    )
    recency_canary_count = _reserved_candidate_count(
        max_configs,
        recency_canary_budget_share,
        available=max_configs - weight_kdj_count - ridge_kdj_count - neural_kdj_count,
    )
    target_weight_inversion_count = _reserved_candidate_count(
        max_configs,
        target_weight_inversion_budget_share,
        available=min(
            max(0, target_weight_inversion_max_candidates),
            max(0, target_weight_inversion_available),
            max_configs - weight_kdj_count - ridge_kdj_count - neural_kdj_count - recency_canary_count,
        ),
    )
    normal_budget = max_configs - weight_kdj_count - ridge_kdj_count - neural_kdj_count - recency_canary_count - target_weight_inversion_count
    names = tuple(CANDIDATE_BUDGET_SHARES)
    counts = {name: 0 for name in names}
    remaining = normal_budget
    for name in names:
        if remaining > 0:
            counts[name] = 1
            remaining -= 1
    raw = {
        name: normal_budget * share - counts[name]
        for name, share in CANDIDATE_BUDGET_SHARES.items()
    }
    for name in sorted(names, key=lambda item: raw[item], reverse=True):
        if remaining <= 0:
            break
        add = max(0, int(raw[name]))
        add = min(add, remaining)
        counts[name] += add
        remaining -= add
    for name in sorted(names, key=lambda item: raw[item] - int(raw[item]), reverse=True):
        if remaining <= 0:
            break
        counts[name] += 1
        remaining -= 1
    if weight_kdj_budget_share > 0:
        counts["weight_kdj"] = weight_kdj_count
    if ridge_kdj_budget_share > 0:
        counts["ridge_kdj"] = ridge_kdj_count
    if neural_kdj_budget_share > 0:
        counts["neural_kdj"] = neural_kdj_count
    if recency_canary_budget_share > 0:
        counts["recency_canary"] = recency_canary_count
    if target_weight_inversion_budget_share > 0:
        counts["target_weight_inversion"] = target_weight_inversion_count
    return counts


def config_distance(left: FrequencyRankerConfig, right: FrequencyRankerConfig) -> float:
    return sum(abs(float(getattr(left, field)) - float(getattr(right, field))) for field in ALL_FIELDS)


def weighted_config_distance(config: FrequencyRankerConfig, configs: list[FrequencyRankerConfig]) -> float:
    if not configs:
        return float("inf")
    return min(config_distance(config, other) for other in configs)


def deterministic_seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts)
    return sum((index + 1) * ord(char) for index, char in enumerate(payload)) % (2**32)


def nonzero_weight_fields(config: FrequencyRankerConfig) -> tuple[str, ...]:
    return tuple(field for field in ALL_FIELDS if abs(float(getattr(config, field))) > 1e-12)


def low_coverage_fields_from_summaries(summaries: list[dict], *, limit: int = 12) -> tuple[str, ...]:
    coverage: Counter[str] = Counter()
    for summary in summaries:
        config = summary.get("config") if isinstance(summary.get("config"), dict) else {}
        for field in ALL_FIELDS:
            if abs(float(config.get(field, 0) or 0)) > 1e-12:
                coverage[field] += 1
    return tuple(field for field, _count in sorted(coverage.items(), key=lambda item: (item[1], item[0])))[:limit] or CONTEXT_FIELDS[:limit]


def baseline_candidate_configs() -> tuple[FrequencyRankerConfig, ...]:
    return (
        FrequencyRankerConfig(),
        FrequencyRankerConfig(
            structural_weight=0.55,
            frequency_weight=0.30,
            omission_weight=0.15,
            previous_consecutive_weight=0.00,
        ),
        FrequencyRankerConfig(
            structural_weight=0.00,
            frequency_weight=0.00,
            omission_weight=0.00,
            previous_consecutive_weight=0.00,
        ),
        FrequencyRankerConfig(
            structural_weight=0.25,
            frequency_weight=0.50,
            omission_weight=0.25,
            previous_consecutive_weight=0.00,
        ),
    )


def control_experiment_configs(base: FrequencyRankerConfig) -> tuple[tuple[str, FrequencyRankerConfig], ...]:
    return (
        ("current_best_frozen_baseline", base),
        ("default_baseline", FrequencyRankerConfig()),
        ("structural_baseline", FrequencyRankerConfig(structural_weight=1.0, frequency_weight=0.0, omission_weight=0.0, previous_consecutive_weight=0.0)),
        ("frequency_baseline", FrequencyRankerConfig(structural_weight=0.0, frequency_weight=1.0, omission_weight=0.0, previous_consecutive_weight=0.0)),
        ("omission_baseline", FrequencyRankerConfig(structural_weight=0.0, frequency_weight=0.0, omission_weight=1.0, previous_consecutive_weight=0.0)),
        ("null_baseline", FrequencyRankerConfig(structural_weight=0.0, frequency_weight=0.0, omission_weight=0.0, previous_consecutive_weight=0.0)),
    )


def frozen_validation_window(eval_window: int) -> int:
    if eval_window <= 1:
        return max(0, eval_window)
    return min(MAX_FROZEN_VALIDATION_WINDOW, max(1, eval_window // 5))


def frozen_validation_summary(summary: dict, *, validation_window: int, universe_size: int) -> dict | None:
    target_results = summary.get("target_results")
    if validation_window <= 0 or not isinstance(target_results, list):
        return None
    targets = [target for target in target_results if isinstance(target, dict)]
    if not targets:
        return None
    selected = targets[-min(validation_window, len(targets)):]
    ranks = [int(target["rank"]) for target in selected if isinstance(target.get("rank"), int | float)]
    if not ranks:
        return None
    red5_ranks = [int(target["red5_rank"]) for target in selected if isinstance(target.get("red5_rank"), int | float)]
    validation = {
        "window": len(selected),
        "issues": [str(target.get("issue") or "") for target in selected],
        "top_100_hits": sum(bool(target.get("hit_top_100")) for target in selected),
        "top_1000_hits": sum(bool(target.get("hit_top_1000")) for target in selected),
        "top_10000_hits": sum(bool(target.get("hit_top_10000")) for target in selected),
        "median_rank": median(ranks),
        "best_rank": min(ranks),
        "worst_rank": max(ranks),
        "red5": {
            "top_100_hits": sum(bool(target.get("hit_red5_top_100")) for target in selected),
            "top_1000_hits": sum(bool(target.get("hit_red5_top_1000")) for target in selected),
            "top_10000_hits": sum(bool(target.get("hit_red5_top_10000")) for target in selected),
            "median_rank": median(red5_ranks) if red5_ranks else None,
            "best_rank": min(red5_ranks) if red5_ranks else None,
        },
        "rank_quality": summarize_rank_quality(ranks, universe_size=universe_size),
    }
    validation["reward"] = reward_summary(validation, universe_size=universe_size)
    return validation


def attach_frozen_validation(summaries: list[dict], *, validation_window: int, universe_size: int) -> None:
    for summary in summaries:
        validation = frozen_validation_summary(
            summary,
            validation_window=validation_window,
            universe_size=universe_size,
        )
        if validation is not None:
            summary["frozen_validation"] = validation


def _frozen_objective(summary: dict) -> float:
    validation = summary.get("frozen_validation") if isinstance(summary.get("frozen_validation"), dict) else {}
    reward = validation.get("reward") if isinstance(validation.get("reward"), dict) else {}
    return float(reward.get("objectiveScore") or 0.0)


def _frozen_tail_not_worse(candidate: dict, incumbent: dict) -> bool:
    candidate_validation = candidate.get("frozen_validation") if isinstance(candidate.get("frozen_validation"), dict) else {}
    incumbent_validation = incumbent.get("frozen_validation") if isinstance(incumbent.get("frozen_validation"), dict) else {}
    candidate_quality = candidate_validation.get("rank_quality") if isinstance(candidate_validation.get("rank_quality"), dict) else {}
    incumbent_quality = incumbent_validation.get("rank_quality") if isinstance(incumbent_validation.get("rank_quality"), dict) else {}
    if (candidate_validation.get("worst_rank") or 0) > (incumbent_validation.get("worst_rank") or 0):
        return False
    for field in ("p95_rank", "tail_risk_penalty"):
        candidate_value = candidate_quality.get(field)
        incumbent_value = incumbent_quality.get(field)
        if candidate_value is not None and incumbent_value is not None and float(candidate_value) > float(incumbent_value):
            return False
    for field in ("tail_over_750000_count", "tail_over_900000_count", "tail_over_1000000_count"):
        if int(candidate_quality.get(field) or 0) > int(incumbent_quality.get(field) or 0):
            return False
    return True


def frozen_validation_promotion_gate(candidate: dict, incumbent: dict | None) -> dict:
    if not isinstance(candidate, dict):
        return {"passed": False, "reason": "missing_candidate"}
    if not isinstance(incumbent, dict):
        return {"passed": True, "reason": "no_incumbent"}
    candidate_validation = candidate.get("frozen_validation")
    incumbent_validation = incumbent.get("frozen_validation")
    if not isinstance(candidate_validation, dict) or not isinstance(incumbent_validation, dict):
        return {
            "passed": True,
            "reason": "missing_frozen_validation",
            "candidate_config_hash": candidate.get("config_hash"),
            "incumbent_config_hash": incumbent.get("config_hash"),
        }
    candidate_objective = _frozen_objective(candidate)
    incumbent_objective = _frozen_objective(incumbent)
    objective_passed = candidate_objective > incumbent_objective
    tail_passed = _frozen_tail_not_worse(candidate, incumbent)
    candidate_primary_score = source_frontier_primary_score(candidate)
    incumbent_primary_score = source_frontier_primary_score(incumbent)
    primary_hit_passed = candidate_primary_score > incumbent_primary_score
    return {
        "passed": bool(objective_passed and tail_passed and primary_hit_passed),
        "reason": "passed" if objective_passed and tail_passed and primary_hit_passed else "frozen_validation_not_better",
        "objective_passed": objective_passed,
        "tail_passed": tail_passed,
        "primary_hit_passed": primary_hit_passed,
        "candidate_primary_score": list(candidate_primary_score),
        "incumbent_primary_score": list(incumbent_primary_score),
        "candidate_objective": candidate_objective,
        "incumbent_objective": incumbent_objective,
        "candidate_config_hash": candidate.get("config_hash"),
        "incumbent_config_hash": incumbent.get("config_hash"),
    }


def target_hit_issues(summary: dict | None, *, cutoff: int) -> set[str]:
    if not isinstance(summary, dict):
        return set()
    target_results = summary.get("target_results")
    if not isinstance(target_results, list):
        return set()
    issues: set[str] = set()
    for target in target_results:
        if not isinstance(target, dict):
            continue
        issue = str(target.get("issue") or "")
        rank = target.get("rank")
        if issue and isinstance(rank, int | float) and int(rank) <= cutoff:
            issues.add(issue)
    return issues


def target_hit_issue_rows(summary: dict | None, *, cutoff: int) -> list[dict]:
    if not isinstance(summary, dict):
        return []
    target_results = summary.get("target_results")
    if not isinstance(target_results, list):
        return []
    rows: list[dict] = []
    for target in target_results:
        if not isinstance(target, dict):
            continue
        issue = str(target.get("issue") or "")
        rank = target.get("rank")
        if not issue or not isinstance(rank, int | float):
            continue
        rank_value = int(rank)
        if rank_value <= cutoff:
            rows.append({"issue": issue, "rank": rank_value})
    return rows


def control_summary_map(
    summaries: list[dict],
    controls: tuple[tuple[str, FrequencyRankerConfig], ...],
) -> dict[str, dict]:
    by_hash = {summary.get("config_hash"): summary for summary in summaries if isinstance(summary.get("config_hash"), str)}
    rows: dict[str, dict] = {}
    for label, config in controls:
        summary = by_hash.get(config_hash(config))
        if summary is not None:
            rows[label] = summary
    return rows


def baseline_overlap_summary(
    summary: dict,
    baseline_summaries: dict[str, dict],
    *,
    baseline_labels: tuple[str, ...] = BASELINE_OVERLAP_LABELS,
) -> dict:
    selected_baselines = {
        label: baseline_summaries[label]
        for label in baseline_labels
        if isinstance(baseline_summaries.get(label), dict)
    }
    result = {
        "baseline_labels": list(selected_baselines),
        "bands": {},
        "unique_reward": 0.0,
        "overlap_penalty": 0.0,
    }
    reward_weights = {
        100: BASELINE_UNIQUE_TOP_100_REWARD,
        1000: BASELINE_UNIQUE_TOP_1000_REWARD,
        10000: BASELINE_UNIQUE_TOP_10000_REWARD,
    }
    penalty_weights = {
        100: BASELINE_OVERLAP_TOP_100_PENALTY,
        1000: BASELINE_OVERLAP_TOP_1000_PENALTY,
        10000: BASELINE_OVERLAP_TOP_10000_PENALTY,
    }
    for cutoff in (100, 1000, 10000):
        candidate_hits = target_hit_issues(summary, cutoff=cutoff)
        baseline_hits: set[str] = set()
        baseline_by_label = {}
        for label, baseline in selected_baselines.items():
            hits = target_hit_issues(baseline, cutoff=cutoff)
            baseline_by_label[label] = sorted(hits)
            baseline_hits.update(hits)
        overlap_hits = candidate_hits & baseline_hits
        unique_hits = candidate_hits - baseline_hits
        result["bands"][f"top_{cutoff}"] = {
            "candidate_hit_count": len(candidate_hits),
            "baseline_union_hit_count": len(baseline_hits),
            "unique_hit_count": len(unique_hits),
            "overlap_hit_count": len(overlap_hits),
            "candidate_hit_issues": sorted(candidate_hits),
            "baseline_hit_issues": sorted(baseline_hits),
            "unique_hit_issues": sorted(unique_hits),
            "overlap_hit_issues": sorted(overlap_hits),
            "baseline_hit_issues_by_label": baseline_by_label,
        }
        result["unique_reward"] += len(unique_hits) * reward_weights[cutoff]
        result["overlap_penalty"] += len(overlap_hits) * penalty_weights[cutoff]
    result["unique_reward"] = round(float(result["unique_reward"]), 6)
    result["overlap_penalty"] = round(float(result["overlap_penalty"]), 6)
    return result


def attach_baseline_overlap(
    summaries: list[dict],
    controls: tuple[tuple[str, FrequencyRankerConfig], ...],
    *,
    universe_size: int,
) -> None:
    baseline_summaries = control_summary_map(summaries, controls)
    for summary in summaries:
        summary["baseline_overlap"] = baseline_overlap_summary(summary, baseline_summaries)
        summary["reward"] = reward_summary(summary, universe_size=universe_size)


def target_rank_movement(candidate: dict | None, baseline: dict | None) -> dict:
    if not isinstance(candidate, dict) or not isinstance(baseline, dict):
        return {"target_count": 0, "changed_target_count": 0, "median_abs_delta": 0.0, "max_abs_delta": 0}
    candidate_targets = candidate.get("target_results")
    baseline_targets = baseline.get("target_results")
    if not isinstance(candidate_targets, list) or not isinstance(baseline_targets, list):
        return {"target_count": 0, "changed_target_count": 0, "median_abs_delta": 0.0, "max_abs_delta": 0}
    baseline_by_issue = {
        str(item.get("issue") or ""): int(item.get("rank"))
        for item in baseline_targets
        if isinstance(item, dict) and isinstance(item.get("rank"), int | float)
    }
    deltas: list[int] = []
    rows: list[dict] = []
    for item in candidate_targets:
        if not isinstance(item, dict) or not isinstance(item.get("rank"), int | float):
            continue
        issue = str(item.get("issue") or "")
        if issue not in baseline_by_issue:
            continue
        candidate_rank = int(item["rank"])
        baseline_rank = baseline_by_issue[issue]
        delta = candidate_rank - baseline_rank
        deltas.append(delta)
        rows.append(
            {
                "issue": issue,
                "candidate_rank": candidate_rank,
                "baseline_rank": baseline_rank,
                "delta": delta,
                "abs_delta": abs(delta),
                "improved": delta < 0,
            }
        )
    abs_deltas = [abs(delta) for delta in deltas]
    return {
        "target_count": len(deltas),
        "changed_target_count": sum(delta != 0 for delta in deltas),
        "improved_count": sum(delta < 0 for delta in deltas),
        "worsened_count": sum(delta > 0 for delta in deltas),
        "median_abs_delta": float(median(abs_deltas)) if abs_deltas else 0.0,
        "max_abs_delta": max(abs_deltas, default=0),
        "rows": rows[:12],
    }


def compact_control_summary(label: str, summary: dict) -> dict:
    validation = summary.get("frozen_validation") if isinstance(summary.get("frozen_validation"), dict) else None
    baseline_overlap = summary.get("baseline_overlap") if isinstance(summary.get("baseline_overlap"), dict) else None
    return {
        "label": label,
        "config_hash": summary.get("config_hash"),
        "top_100_hits": summary.get("top_100_hits"),
        "top_1000_hits": summary.get("top_1000_hits"),
        "top_10000_hits": summary.get("top_10000_hits"),
        "red5_top_100_hits": (summary.get("red5") or {}).get("top_100_hits") if isinstance(summary.get("red5"), dict) else None,
        "red5_top_10000_hits": (summary.get("red5") or {}).get("top_10000_hits") if isinstance(summary.get("red5"), dict) else None,
        "median_rank": summary.get("median_rank"),
        "worst_rank": summary.get("worst_rank"),
        "objective_score": (summary.get("reward") or {}).get("objectiveScore") if isinstance(summary.get("reward"), dict) else None,
        "probability_calibration": summary.get("probability_calibration") if isinstance(summary.get("probability_calibration"), dict) else None,
        "baseline_overlap": baseline_overlap,
        "frozen_validation": validation,
    }


def control_experiment_summaries(
    summaries: list[dict],
    controls: tuple[tuple[str, FrequencyRankerConfig], ...],
) -> list[dict]:
    by_label = control_summary_map(summaries, controls)
    rows: list[dict] = []
    for label, config in controls:
        summary = by_label.get(label)
        if summary is not None:
            rows.append(compact_control_summary(label, summary))
    return rows


def exploratory_candidate_configs(
    base: FrequencyRankerConfig,
    *,
    phase: str,
    step: float,
    low_coverage_fields: tuple[str, ...],
    stagnation_rounds: int,
    seed: int,
) -> tuple[FrequencyRankerConfig, ...]:
    rng = random.Random(seed)
    radius = min(0.30, step * (1.0 + min(stagnation_rounds, 48) / 16))
    fields = low_coverage_fields or search_fields_for_phase(phase)
    candidates: list[FrequencyRankerConfig] = []
    for field in fields:
        candidates.append(replace(base, **{field: getattr(base, field) + radius}))
        candidates.append(replace(base, **{field: getattr(base, field) - radius}))
    for _ in range(max(8, len(fields))):
        values = config_dict(base)
        for field in rng.sample(tuple(ALL_FIELDS), k=min(4, len(ALL_FIELDS))):
            values[field] = float(values[field]) + rng.uniform(-radius, radius)
        candidates.append(FrequencyRankerConfig(**values))
    return tuple(candidates)


def recency_canary_candidate_configs(
    base: FrequencyRankerConfig,
    *,
    step: float,
    max_configs: int,
) -> tuple[FrequencyRankerConfig, ...]:
    if max_configs <= 0:
        return ()
    bump = min(0.30, max(0.08, step))
    short_field, omission_field = RECENCY_CANARY_FIELDS
    candidates = (
        replace(base, **{short_field: getattr(base, short_field) + bump}),
        replace(base, **{short_field: getattr(base, short_field) - bump}),
        replace(base, **{omission_field: getattr(base, omission_field) + bump}),
        replace(base, **{omission_field: getattr(base, omission_field) - bump}),
        replace(
            base,
            **{
                short_field: getattr(base, short_field) + bump,
                omission_field: getattr(base, omission_field) + bump,
            },
        ),
        replace(
            base,
            **{
                short_field: getattr(base, short_field) - bump,
                omission_field: getattr(base, omission_field) + bump,
            },
        ),
    )
    return tuple(clamp_config(config) for config in candidates[:max_configs])


def replay_candidate_configs(
    base: FrequencyRankerConfig,
    historical_configs: tuple[FrequencyRankerConfig, ...],
    *,
    seed: int,
) -> tuple[FrequencyRankerConfig, ...]:
    rng = random.Random(seed)
    candidates: list[FrequencyRankerConfig] = []
    for historical in historical_configs[:8]:
        candidates.append(historical)
        candidates.append(blend_configs(base, historical, 0.50))
        candidates.append(extrapolate_config(historical, base, 0.35))
    if len(historical_configs) >= 2:
        for left, right in zip(historical_configs[::2], historical_configs[1::2], strict=False):
            alpha = rng.uniform(0.35, 0.65)
            candidates.append(blend_configs(left, right, alpha))
    return tuple(candidates)


def surrogate_candidate_configs(
    base: FrequencyRankerConfig,
    historical_summaries: list[dict],
    *,
    max_configs: int,
    seed: int,
) -> tuple[FrequencyRankerConfig, ...]:
    usable = [
        summary
        for summary in historical_summaries
        if isinstance(summary.get("config"), dict)
        and isinstance((summary.get("reward") or {}).get("objectiveScore"), (int, float))
    ]
    if len(usable) < 6 or max_configs <= 0:
        return ()
    usable.sort(key=lambda item: float(item["reward"]["objectiveScore"]), reverse=True)
    elite = usable[: max(2, len(usable) // 4)]
    weak = usable[-max(2, len(usable) // 4):]
    rng = random.Random(seed)
    candidates: list[FrequencyRankerConfig] = []
    for _ in range(max_configs):
        values = config_dict(base)
        for field in ALL_FIELDS:
            elite_mean = sum(float(item["config"].get(field, 0) or 0) for item in elite) / len(elite)
            weak_mean = sum(float(item["config"].get(field, 0) or 0) for item in weak) / len(weak)
            direction = elite_mean - weak_mean
            values[field] = elite_mean + direction * rng.uniform(0.15, 0.45) + rng.uniform(-0.015, 0.015)
        candidates.append(FrequencyRankerConfig(**values))
    return tuple(candidates)


def weight_kdj_advisor_candidate_configs(
    base: FrequencyRankerConfig,
    signals: list[dict],
    *,
    max_configs: int,
    min_objective_delta: float = DEFAULT_WEIGHT_KDJ_MIN_OBJECTIVE_DELTA,
    min_abs_offset: float = DEFAULT_WEIGHT_KDJ_MIN_ABS_OFFSET,
    slope_window: int = DEFAULT_WEIGHT_KDJ_SLOPE_WINDOW,
    neutral_band: float = DEFAULT_WEIGHT_KDJ_NEUTRAL_BAND,
) -> tuple[FrequencyRankerConfig, ...]:
    if max_configs <= 0 or not signals:
        return ()
    advice = weight_kdj_advice_from_signals(
        signals,
        allowed_fields=ALL_FIELDS,
        min_objective_delta=min_objective_delta,
        min_abs_offset=min_abs_offset,
        slope_window=slope_window,
        neutral_band=neutral_band,
    )
    configs: list[FrequencyRankerConfig] = []
    seen: set[str] = set()
    usable = [item for item in advice if item.decision in {"selected", "downweighted"} and item.applied_offset]
    for item in usable:
        add_unique_until(configs, seen, replace(base, **{item.weight_name: getattr(base, item.weight_name) + item.applied_offset}), limit=max_configs)
        if len(configs) >= max_configs:
            return tuple(configs)
    selected = [item for item in usable if item.decision == "selected"]
    if len(selected) >= 2:
        values = config_dict(base)
        combined_fields: set[str] = set()
        for item in selected:
            if item.weight_name in combined_fields:
                continue
            combined_fields.add(item.weight_name)
            values[item.weight_name] = values[item.weight_name] + item.applied_offset / 2
            if len(combined_fields) >= 4:
                break
        add_unique_until(configs, seen, FrequencyRankerConfig(**values), limit=max_configs)
    return tuple(configs[:max_configs])


def merge_reserved_candidate_configs(
    normal_configs: tuple[FrequencyRankerConfig, ...],
    reserved_configs: tuple[FrequencyRankerConfig, ...],
    *,
    max_configs: int,
    reserved_budget: int,
) -> tuple[FrequencyRankerConfig, ...]:
    normal_limit = max(0, max_configs - max(0, reserved_budget))
    configs: list[FrequencyRankerConfig] = []
    seen: set[str] = set()
    for config in normal_configs:
        add_unique_until(configs, seen, config, limit=normal_limit)
    for config in reserved_configs:
        add_unique_until(configs, seen, config, limit=max_configs)
    for config in normal_configs:
        if len(configs) >= max_configs:
            break
        add_unique(configs, seen, config)
    return tuple(configs[:max_configs])


def candidate_source_survival(
    source_configs: dict[str, tuple[FrequencyRankerConfig, ...]],
    *,
    refined_configs: tuple[FrequencyRankerConfig, ...] = (),
    full_eval_top_results: list[dict] | tuple[dict, ...] = (),
    round_best: dict | None = None,
    preview_limit: int = 8,
) -> dict:
    refined_hashes = {config_hash(config) for config in refined_configs}
    top_hashes = [str(summary.get("config_hash") or "") for summary in full_eval_top_results if isinstance(summary, dict)]
    round_best_hash = str(round_best.get("config_hash") or "") if isinstance(round_best, dict) else ""
    survival: dict[str, dict] = {}
    for source, configs in source_configs.items():
        hashes: list[str] = []
        seen: set[str] = set()
        for config in configs:
            key = config_hash(config)
            if key in seen:
                continue
            seen.add(key)
            hashes.append(key)
        hash_set = set(hashes)
        survival[source] = {
            "generated": len(hashes),
            "prefilter_selected": sum(hash_value in refined_hashes for hash_value in hashes),
            "full_eval_top5": sum(hash_value in set(top_hashes[:5]) for hash_value in hashes),
            "round_best": bool(round_best_hash and round_best_hash in hash_set),
            "hashes": hashes[:preview_limit],
        }
    return survival


def _source_by_config_hash(source_configs: dict[str, tuple[FrequencyRankerConfig, ...]]) -> dict[str, str]:
    source_by_hash: dict[str, str] = {}
    for source, configs in source_configs.items():
        for config in configs:
            key = config_hash(config)
            if key not in source_by_hash or source_by_hash[key] == "normal":
                source_by_hash[key] = source
    return source_by_hash


def _metric_int(container: dict, key: str, default: int = 0) -> int:
    try:
        return int(container.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def _metric_float(container: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(container.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def _frozen_validation_metrics(summary: dict | None) -> dict:
    validation = summary.get("frozen_validation") if isinstance(summary, dict) else None
    if not isinstance(validation, dict):
        return {
            "top_100_hits": 0,
            "top_1000_hits": 0,
            "top_10000_hits": 0,
            "red5_top_100_hits": 0,
            "red5_top_1000_hits": 0,
            "red5_top_10000_hits": 0,
            "tail_over_1000000_count": 0,
            "median_rank": None,
            "objective_score": 0.0,
        }
    red5 = validation.get("red5") if isinstance(validation.get("red5"), dict) else {}
    rank_quality = validation.get("rank_quality") if isinstance(validation.get("rank_quality"), dict) else {}
    reward = validation.get("reward") if isinstance(validation.get("reward"), dict) else {}
    return {
        "top_100_hits": _metric_int(validation, "top_100_hits"),
        "top_1000_hits": _metric_int(validation, "top_1000_hits"),
        "top_10000_hits": _metric_int(validation, "top_10000_hits"),
        "red5_top_100_hits": _metric_int(red5, "top_100_hits"),
        "red5_top_1000_hits": _metric_int(red5, "top_1000_hits"),
        "red5_top_10000_hits": _metric_int(red5, "top_10000_hits"),
        "tail_over_1000000_count": _metric_int(rank_quality, "tail_over_1000000_count"),
        "median_rank": validation.get("median_rank"),
        "objective_score": _metric_float(reward, "objectiveScore"),
    }


def source_frontier_primary_score(summary: dict | None) -> tuple:
    metrics = _frozen_validation_metrics(summary)
    return (
        metrics["top_100_hits"],
        metrics["top_1000_hits"],
        metrics["top_10000_hits"],
    )


def source_frontier_secondary_score(summary: dict | None) -> tuple:
    metrics = _frozen_validation_metrics(summary)
    median_rank = metrics["median_rank"]
    median_value = float(median_rank) if isinstance(median_rank, int | float) else 1_000_000_000.0
    return (
        metrics["red5_top_100_hits"],
        metrics["red5_top_1000_hits"],
        metrics["red5_top_10000_hits"],
        -metrics["tail_over_1000000_count"],
        -median_value,
        metrics["objective_score"],
    )


def source_frontier_score(summary: dict | None) -> tuple:
    return source_frontier_primary_score(summary) + source_frontier_secondary_score(summary)


def _source_frontier_summary_metrics(summary: dict | None) -> dict:
    if not isinstance(summary, dict):
        return {}
    reward = summary.get("reward") if isinstance(summary.get("reward"), dict) else {}
    frozen = _frozen_validation_metrics(summary)
    return {
        "config_hash": summary_config_hash(summary) or "",
        "top_100_hits": _metric_int(summary, "top_100_hits"),
        "top_1000_hits": _metric_int(summary, "top_1000_hits"),
        "top_10000_hits": _metric_int(summary, "top_10000_hits"),
        "median_rank": summary.get("median_rank"),
        "objective_score": _metric_float(reward, "objectiveScore"),
        "frozen_top_100_hits": frozen["top_100_hits"],
        "frozen_top_1000_hits": frozen["top_1000_hits"],
        "frozen_top_10000_hits": frozen["top_10000_hits"],
        "frozen_median_rank": frozen["median_rank"],
        "frozen_objective_score": frozen["objective_score"],
        "frozen_primary_score": list(source_frontier_primary_score(summary)),
        "frozen_secondary_score": list(source_frontier_secondary_score(summary)),
    }


def eval_slice_overfit_guardrail(
    *,
    summaries: list[dict],
    source_configs: dict[str, tuple[FrequencyRankerConfig, ...]],
    round_best: dict | None,
    prior_best_summary: dict | None,
    rank_homogeneity: dict,
    promotion_gate: dict,
    stagnation_rounds: int,
    top_100_threshold: int = 3,
    top_limit: int = 8,
) -> dict:
    source_by_hash = _source_by_config_hash(source_configs)
    round_best_hash = summary_config_hash(round_best) or ""
    round_best_eval_primary = (
        _metric_int(round_best or {}, "top_100_hits"),
        _metric_int(round_best or {}, "top_1000_hits"),
        _metric_int(round_best or {}, "top_10000_hits"),
    )
    round_best_frozen_primary = source_frontier_primary_score(round_best)
    incumbent_frozen_primary = source_frontier_primary_score(prior_best_summary)
    promotion_passed = bool(promotion_gate.get("passed")) if isinstance(promotion_gate, dict) else False
    primary_hit_passed = bool(promotion_gate.get("primary_hit_passed")) if isinstance(promotion_gate, dict) else False
    rank_homogeneity_active = bool(rank_homogeneity.get("active"))
    active = bool(
        rank_homogeneity_active
        and stagnation_rounds >= STAGNATION_THRESHOLD
        and not promotion_passed
        and not primary_hit_passed
        and round_best_eval_primary[0] >= top_100_threshold
        and round_best_frozen_primary == (0, 0, 0)
    )
    if active:
        reason = "eval_slice_overfit_no_frozen_primary_lift"
    elif promotion_passed:
        reason = "promotion_passed"
    elif primary_hit_passed:
        reason = "primary_hit_passed"
    elif round_best_eval_primary[0] < top_100_threshold:
        reason = "below_eval_top100_threshold"
    elif round_best_frozen_primary != (0, 0, 0):
        reason = "frozen_primary_present"
    elif stagnation_rounds < STAGNATION_THRESHOLD:
        reason = "below_stagnation_threshold"
    elif not rank_homogeneity_active:
        reason = "rank_homogeneity_inactive"
    else:
        reason = "inactive"

    suspicious_rows: list[dict] = []
    validation_issues = set()
    validation = round_best.get("frozen_validation") if isinstance(round_best, dict) else None
    if isinstance(validation, dict) and isinstance(validation.get("issues"), list):
        validation_issues = {str(issue) for issue in validation.get("issues") if issue}
    for index, summary in enumerate(summaries[: max(1, top_limit)], start=1):
        summary_eval_primary = (
            _metric_int(summary, "top_100_hits"),
            _metric_int(summary, "top_1000_hits"),
            _metric_int(summary, "top_10000_hits"),
        )
        summary_frozen_primary = source_frontier_primary_score(summary)
        if summary_eval_primary[0] < top_100_threshold or summary_frozen_primary != (0, 0, 0):
            continue
        summary_hash = summary_config_hash(summary) or ""
        hit_rows = target_hit_issue_rows(summary, cutoff=100)
        suspicious_rows.append(
            {
                "full_eval_rank": index,
                "config_hash": summary_hash,
                "source": source_by_hash.get(summary_hash, "unknown"),
                "rank_signature_hash": rank_signature_hash(summary),
                "eval_primary_score": list(summary_eval_primary),
                "frozen_primary_score": list(summary_frozen_primary),
                "top_100_hit_issues": [row["issue"] for row in hit_rows],
                "top_100_hit_ranks": [row["rank"] for row in hit_rows],
                "non_frozen_top_100_hit_issues": [
                    row["issue"] for row in hit_rows if row["issue"] not in validation_issues
                ],
            }
        )

    issue_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    signature_counts: Counter[str] = Counter()
    for row in suspicious_rows:
        source_counts[str(row.get("source") or "unknown")] += 1
        signature_counts[str(row.get("rank_signature_hash") or "")] += 1
        for issue in row.get("top_100_hit_issues") or []:
            issue_counts[str(issue)] += 1

    return {
        "active": active,
        "reason": reason,
        "threshold": STAGNATION_THRESHOLD,
        "stagnation_rounds": stagnation_rounds,
        "top_100_threshold": top_100_threshold,
        "rank_homogeneity_active": rank_homogeneity_active,
        "rank_homogeneity_unique_signature_count": rank_homogeneity.get("unique_signature_count"),
        "promotion_passed": promotion_passed,
        "primary_hit_passed": primary_hit_passed,
        "round_best_config_hash": round_best_hash,
        "round_best_source": source_by_hash.get(round_best_hash, "unknown") if round_best_hash else "",
        "round_best_rank_signature_hash": rank_signature_hash(round_best),
        "round_best_eval_primary_score": list(round_best_eval_primary),
        "round_best_frozen_primary_score": list(round_best_frozen_primary),
        "incumbent_frozen_primary_score": list(incumbent_frozen_primary),
        "round_best_top_100_hit_issues": [row["issue"] for row in target_hit_issue_rows(round_best, cutoff=100)],
        "suspicious_candidate_count": len(suspicious_rows),
        "suspicious_candidates": suspicious_rows,
        "issue_counts": dict(sorted(issue_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "rank_signature_counts": dict(sorted(signature_counts.items())),
        "force_primary_gate": active,
        "allow_unpromoted_round_best": not active,
    }


def source_frontier_diagnostics(
    *,
    summaries: list[dict],
    source_configs: dict[str, tuple[FrequencyRankerConfig, ...]],
    prior_best_summary: dict | None,
    round_best: dict | None,
    top_limit: int = SOURCE_FRONTIER_TOP_LIMIT,
) -> dict:
    summary_by_hash = {
        summary_config_hash(summary): (index, summary)
        for index, summary in enumerate(summaries, start=1)
        if summary_config_hash(summary)
    }
    round_best_hash = summary_config_hash(round_best) or ""
    baseline = prior_best_summary if isinstance(prior_best_summary, dict) else round_best
    baseline_score = source_frontier_score(baseline)
    baseline_primary_score = source_frontier_primary_score(baseline)
    baseline_secondary_score = source_frontier_secondary_score(baseline)
    sources: dict[str, dict] = {}
    best_non_normal: tuple[str, int, dict, tuple] | None = None
    best_non_normal_primary: tuple[str, int, dict, tuple] | None = None
    best_non_normal_secondary: tuple[str, int, dict, tuple] | None = None

    for source, configs in source_configs.items():
        hashes = bounded_unique_config_hashes(configs, limit=64)
        evaluated: list[tuple[int, dict]] = [
            summary_by_hash[key]
            for key in hashes
            if key in summary_by_hash
        ]
        top5_count = sum(index <= 5 for index, _summary in evaluated)
        best_entry = min(evaluated, key=lambda item: item[0]) if evaluated else None
        best_summary = best_entry[1] if best_entry is not None else None
        best_rank = best_entry[0] if best_entry is not None else None
        best_score = source_frontier_score(best_summary)
        best_primary_score = source_frontier_primary_score(best_summary)
        best_secondary_score = source_frontier_secondary_score(best_summary)
        sources[source] = {
            "generated": len(hashes),
            "full_eval_count": len(evaluated),
            "full_eval_top5": top5_count,
            "round_best": bool(round_best_hash and round_best_hash in set(hashes)),
            "best_full_eval_rank": best_rank,
            "best": _source_frontier_summary_metrics(best_summary),
            "score": list(best_score),
            "primary_score": list(best_primary_score),
            "secondary_score": list(best_secondary_score),
        }
        if source != "normal" and best_summary is not None and (best_non_normal is None or best_score > best_non_normal[3]):
            best_non_normal = (source, int(best_rank or 0), best_summary, best_score)
        if (
            source != "normal"
            and best_summary is not None
            and best_primary_score > baseline_primary_score
            and (best_non_normal_primary is None or best_primary_score > best_non_normal_primary[3])
        ):
            best_non_normal_primary = (source, int(best_rank or 0), best_summary, best_primary_score)
        if (
            source != "normal"
            and best_summary is not None
            and best_secondary_score > baseline_secondary_score
            and (best_non_normal_secondary is None or best_secondary_score > best_non_normal_secondary[3])
        ):
            best_non_normal_secondary = (source, int(best_rank or 0), best_summary, best_secondary_score)

    return {
        "top_limit": top_limit,
        "baseline_config_hash": summary_config_hash(baseline) or "",
        "baseline_score": list(baseline_score),
        "baseline_primary_score": list(baseline_primary_score),
        "baseline_secondary_score": list(baseline_secondary_score),
        "round_best_config_hash": round_best_hash,
        "sources": sources,
        "best_non_normal": {
            "source": best_non_normal[0],
            "full_eval_rank": best_non_normal[1],
            "score": list(best_non_normal[3]),
            **_source_frontier_summary_metrics(best_non_normal[2]),
        }
        if best_non_normal is not None
        else None,
        "best_non_normal_primary": {
            "source": best_non_normal_primary[0],
            "full_eval_rank": best_non_normal_primary[1],
            "primary_score": list(best_non_normal_primary[3]),
            **_source_frontier_summary_metrics(best_non_normal_primary[2]),
        }
        if best_non_normal_primary is not None
        else None,
        "best_non_normal_secondary": {
            "source": best_non_normal_secondary[0],
            "full_eval_rank": best_non_normal_secondary[1],
            "secondary_score": list(best_non_normal_secondary[3]),
            **_source_frontier_summary_metrics(best_non_normal_secondary[2]),
        }
        if best_non_normal_secondary is not None
        else None,
    }


def select_source_frontier_champion(
    *,
    summaries: list[dict],
    source_configs: dict[str, tuple[FrequencyRankerConfig, ...]],
    round_best: dict | None,
    prior_best_summary: dict | None,
    stagnation_rounds: int,
    top_limit: int = SOURCE_FRONTIER_TOP_LIMIT,
) -> tuple[dict | None, dict]:
    baseline = prior_best_summary if isinstance(prior_best_summary, dict) else round_best
    baseline_score = source_frontier_score(baseline)
    baseline_primary_score = source_frontier_primary_score(baseline)
    baseline_secondary_score = source_frontier_secondary_score(baseline)
    source_by_hash = _source_by_config_hash(source_configs)
    round_best_hash = summary_config_hash(round_best) or ""
    metadata = {
        "active": False,
        "threshold": SOURCE_FRONTIER_STAGNATION_THRESHOLD,
        "stagnation_rounds": stagnation_rounds,
        "source": "",
        "config_hash": "",
        "full_eval_rank": None,
        "round_best_config_hash": round_best_hash,
        "baseline_config_hash": summary_config_hash(baseline) or "",
        "baseline_score": list(baseline_score),
        "baseline_primary_score": list(baseline_primary_score),
        "baseline_secondary_score": list(baseline_secondary_score),
        "candidate_score": None,
        "candidate_primary_score": None,
        "candidate_secondary_score": None,
        "secondary_candidate_available": False,
        "secondary_candidate_config_hash": "",
        "secondary_candidate_source": "",
        "rank_vector_changed": None,
        "changed_target_count": None,
        "reason": None,
    }
    if stagnation_rounds < SOURCE_FRONTIER_STAGNATION_THRESHOLD:
        metadata["reason"] = "below_threshold"
        return None, metadata
    if not summaries:
        metadata["reason"] = "no_summaries"
        return None, metadata

    selected: tuple[dict, int, tuple] | None = None
    for index, summary in enumerate(summaries[: max(1, top_limit)], start=1):
        key = summary_config_hash(summary) or ""
        source = source_by_hash.get(key, "")
        if not source or source == "normal" or key == round_best_hash:
            continue
        score = source_frontier_score(summary)
        primary_score = source_frontier_primary_score(summary)
        secondary_score = source_frontier_secondary_score(summary)
        if primary_score <= baseline_primary_score:
            if secondary_score > baseline_secondary_score:
                metadata.update(
                    {
                        "secondary_candidate_available": True,
                        "secondary_candidate_config_hash": key,
                        "secondary_candidate_source": source,
                    }
                )
            continue
        if selected is None or primary_score > selected[2] or (
            primary_score == selected[2]
            and (secondary_score, sort_key(summary)) > (source_frontier_secondary_score(selected[0]), sort_key(selected[0]))
        ):
            selected = (summary, index, primary_score)

    if selected is None:
        metadata["reason"] = "no_non_normal_primary_frontier_lift"
        return None, metadata

    summary, index, primary_score = selected
    key = summary_config_hash(summary) or ""
    secondary_score = source_frontier_secondary_score(summary)
    movement = target_rank_movement(summary, baseline)
    metadata.update(
        {
            "active": True,
            "source": source_by_hash.get(key, "unknown"),
            "config_hash": key,
            "full_eval_rank": index,
            "candidate_score": list(source_frontier_score(summary)),
            "candidate_primary_score": list(primary_score),
            "candidate_secondary_score": list(secondary_score),
            "rank_vector_changed": rank_vector_changed(baseline, summary),
            "changed_target_count": movement.get("changed_target_count"),
            "reason": "source_frontier_primary_hit_lift",
        }
    )
    return summary, metadata


def select_stagnation_exploration_champion(
    *,
    summaries: list[dict],
    source_configs: dict[str, tuple[FrequencyRankerConfig, ...]],
    round_best: dict | None,
    stagnation_rounds: int,
    top_limit: int = 5,
) -> tuple[dict | None, dict]:
    round_best_hash = summary_config_hash(round_best) or ""
    source_by_hash: dict[str, str] = {}
    for source, configs in source_configs.items():
        for config in configs:
            key = config_hash(config)
            if key not in source_by_hash or source_by_hash[key] == "normal":
                source_by_hash[key] = source
    round_best_source = source_by_hash.get(round_best_hash, "")
    metadata = {
        "active": False,
        "threshold": STAGNATION_THRESHOLD,
        "stagnation_rounds": stagnation_rounds,
        "source": "",
        "config_hash": "",
        "top_rank": None,
        "round_best_config_hash": round_best_hash,
        "round_best_source": round_best_source,
        "reason": None,
    }
    if stagnation_rounds < STAGNATION_THRESHOLD:
        metadata["reason"] = "below_threshold"
        return None, metadata
    if round_best_source and round_best_source != "normal":
        metadata["reason"] = "round_best_already_exploratory"
        return None, metadata
    for index, summary in enumerate(summaries[: max(0, top_limit)], start=1):
        key = summary_config_hash(summary) or ""
        source = source_by_hash.get(key, "")
        if not source or source == "normal":
            continue
        metadata.update(
            {
                "active": True,
                "source": source,
                "config_hash": key,
                "top_rank": index,
                "reason": "stagnation_top_eval_exploration",
            }
        )
        return summary, metadata
    metadata["reason"] = "no_exploratory_top_candidate"
    return None, metadata


def select_rank_homogeneity_restart_champion(
    *,
    summaries: list[dict],
    source_configs: dict[str, tuple[FrequencyRankerConfig, ...]],
    round_best: dict | None,
    prior_best_summary: dict | None,
    rank_homogeneity: dict,
    source: str = "stagnation_restart",
) -> tuple[dict | None, dict]:
    source_hashes = {config_hash(config) for config in source_configs.get(source, ())}
    round_best_hash = summary_config_hash(round_best) or ""
    metadata = {
        "active": False,
        "source": source,
        "config_hash": "",
        "full_eval_rank": None,
        "round_best_config_hash": round_best_hash,
        "rank_vector_changed": None,
        "changed_target_count": None,
        "max_abs_delta": None,
        "reason": None,
    }
    if not rank_homogeneity.get("active"):
        metadata["reason"] = "rank_homogeneity_inactive"
        return None, metadata
    if not source_hashes:
        metadata["reason"] = "no_restart_candidates"
        return None, metadata

    fallback: tuple[dict, int, dict] | None = None
    for index, summary in enumerate(summaries, start=1):
        key = summary_config_hash(summary) or ""
        if key not in source_hashes:
            continue
        movement = target_rank_movement(summary, prior_best_summary)
        if fallback is None:
            fallback = (summary, index, movement)
        if int(movement.get("changed_target_count") or 0) > 0:
            metadata.update(
                {
                    "active": True,
                    "config_hash": key,
                    "full_eval_rank": index,
                    "rank_vector_changed": True,
                    "changed_target_count": movement.get("changed_target_count"),
                    "max_abs_delta": movement.get("max_abs_delta"),
                    "reason": "rank_homogeneity_restart_changed_rank_vector",
                }
            )
            return summary, metadata

    if fallback is None:
        metadata["reason"] = "restart_not_in_full_eval"
        return None, metadata
    summary, index, movement = fallback
    metadata.update(
        {
            "active": True,
            "config_hash": summary_config_hash(summary) or "",
            "full_eval_rank": index,
            "rank_vector_changed": False,
            "changed_target_count": movement.get("changed_target_count"),
            "max_abs_delta": movement.get("max_abs_delta"),
            "reason": "rank_homogeneity_restart_best_available",
        }
    )
    return summary, metadata


def select_experimental_navigation_candidate(
    *,
    exploration_champion: dict | None,
    exploration_champion_info: dict,
    restart_champion: dict | None,
    restart_champion_info: dict,
) -> tuple[dict | None, dict]:
    if exploration_champion is not None and exploration_champion_info.get("active"):
        return exploration_champion, {
            "source": "exploration_champion",
            "reason": exploration_champion_info.get("reason") or "active_exploration_champion",
            "config_hash": summary_config_hash(exploration_champion) or "",
        }
    if (
        restart_champion is not None
        and restart_champion_info.get("active")
        and restart_champion_info.get("rank_vector_changed") is True
    ):
        return restart_champion, {
            "source": "rank_homogeneity_restart_champion",
            "reason": restart_champion_info.get("reason") or "rank_vector_changed_restart_champion",
            "config_hash": summary_config_hash(restart_champion) or "",
        }
    if restart_champion is not None and restart_champion_info.get("active"):
        return None, {
            "source": "rank_homogeneity_restart_champion",
            "reason": "restart_champion_without_rank_vector_change",
            "config_hash": summary_config_hash(restart_champion) or "",
        }
    return None, {"source": "", "reason": "no_experimental_navigation_candidate", "config_hash": ""}


def select_probability_calibration_champion(
    *,
    summaries: list[dict],
    source_configs: dict[str, tuple[FrequencyRankerConfig, ...]],
    round_best: dict | None,
    prior_best_summary: dict | None,
    stagnation_rounds: int,
    top_limit: int = 8,
    force_primary_gate: bool = False,
) -> tuple[dict | None, dict]:
    round_best_hash = summary_config_hash(round_best) or ""
    source_by_hash: dict[str, str] = {}
    for source, configs in source_configs.items():
        for config in configs:
            key = config_hash(config)
            if key not in source_by_hash or source_by_hash[key] == "normal":
                source_by_hash[key] = source
    baseline = round_best if isinstance(round_best, dict) else prior_best_summary
    baseline_score = probability_calibration_score(baseline)
    primary_baseline = prior_best_summary if isinstance(prior_best_summary, dict) else baseline
    baseline_primary_score = source_frontier_primary_score(primary_baseline)
    primary_gate_active = force_primary_gate or stagnation_rounds >= PROBABILITY_PRIMARY_GATE_STAGNATION_THRESHOLD
    metadata = {
        "active": False,
        "threshold": PROBABILITY_CALIBRATION_STAGNATION_THRESHOLD,
        "primary_gate_active": primary_gate_active,
        "primary_gate_forced": force_primary_gate,
        "primary_gate_threshold": PROBABILITY_PRIMARY_GATE_STAGNATION_THRESHOLD,
        "stagnation_rounds": stagnation_rounds,
        "source": "",
        "config_hash": "",
        "full_eval_rank": None,
        "round_best_config_hash": round_best_hash,
        "round_best_score": list(baseline_score),
        "baseline_primary_score": list(baseline_primary_score),
        "candidate_score": None,
        "candidate_primary_score": None,
        "blocked_candidate_score": None,
        "blocked_candidate_primary_score": None,
        "blocked_candidate_config_hash": "",
        "rank_vector_changed": None,
        "changed_target_count": None,
        "reason": None,
    }
    if stagnation_rounds < PROBABILITY_CALIBRATION_STAGNATION_THRESHOLD:
        metadata["reason"] = "below_threshold"
        return None, metadata
    if not summaries:
        metadata["reason"] = "no_summaries"
        return None, metadata

    selected: tuple[dict, int, tuple, tuple] | None = None
    blocked: tuple[dict, tuple, tuple] | None = None
    for index, summary in enumerate(summaries[: max(1, top_limit)], start=1):
        key = summary_config_hash(summary) or ""
        if key and key == round_best_hash:
            continue
        score = probability_calibration_score(summary)
        if score <= baseline_score:
            continue
        primary_score = source_frontier_primary_score(summary)
        if primary_gate_active and primary_score <= baseline_primary_score:
            if blocked is None or score > blocked[1] or (score == blocked[1] and sort_key(summary) > sort_key(blocked[0])):
                blocked = (summary, score, primary_score)
            continue
        if selected is None or score > selected[2] or (score == selected[2] and sort_key(summary) > sort_key(selected[0])):
            selected = (summary, index, score, primary_score)

    if selected is None:
        if blocked is not None:
            blocked_summary, blocked_score, blocked_primary_score = blocked
            metadata.update(
                {
                    "reason": "probability_primary_gate_no_lift",
                    "blocked_candidate_score": list(blocked_score),
                    "blocked_candidate_primary_score": list(blocked_primary_score),
                    "blocked_candidate_config_hash": summary_config_hash(blocked_summary) or "",
                }
            )
        else:
            metadata["reason"] = "no_probability_better_candidate"
        return None, metadata

    summary, index, score, primary_score = selected
    movement = target_rank_movement(summary, prior_best_summary or round_best)
    key = summary_config_hash(summary) or ""
    metadata.update(
        {
            "active": True,
            "source": source_by_hash.get(key, "unknown"),
            "config_hash": key,
            "full_eval_rank": index,
            "candidate_score": list(score),
            "candidate_primary_score": list(primary_score),
            "rank_vector_changed": rank_vector_changed(prior_best_summary or round_best, summary),
            "changed_target_count": movement.get("changed_target_count"),
            "reason": "stagnation_probability_calibration_better",
        }
    )
    return summary, metadata


def bounded_unique_config_hashes(configs: tuple[FrequencyRankerConfig, ...], *, limit: int = 16) -> list[str]:
    hashes: list[str] = []
    seen: set[str] = set()
    for config in configs:
        key = config_hash(config)
        if key in seen:
            continue
        seen.add(key)
        hashes.append(key)
        if len(hashes) >= limit:
            break
    return hashes


def weight_kdj_advisor_metadata(
    signals: list[dict],
    configs: tuple[FrequencyRankerConfig, ...],
    *,
    budget: int = 0,
    thresholds: dict | None = None,
    advice: tuple[WeightKdjAdvice, ...] = (),
) -> dict:
    if not advice and signals:
        advice = weight_kdj_advice_from_signals(
            signals,
            allowed_fields=ALL_FIELDS,
            min_objective_delta=float((thresholds or {}).get("min_objective_delta", DEFAULT_WEIGHT_KDJ_MIN_OBJECTIVE_DELTA)),
            min_abs_offset=float((thresholds or {}).get("min_abs_offset", DEFAULT_WEIGHT_KDJ_MIN_ABS_OFFSET)),
            slope_window=int((thresholds or {}).get("slope_window", DEFAULT_WEIGHT_KDJ_SLOPE_WINDOW)),
            neutral_band=float((thresholds or {}).get("neutral_band", DEFAULT_WEIGHT_KDJ_NEUTRAL_BAND)),
        )
    counts = Counter(item.decision for item in advice)
    latest_issue = max((item.latest_issue for item in advice), default=max((str(signal.get("issue") or "") for signal in signals), default=""))
    fields = sorted({str(signal.get("weight_name")) for signal in signals if signal.get("weight_name") in ALL_FIELDS})
    selected_fields = [item.weight_name for item in advice if item.decision == "selected"]
    downweighted_fields = [item.weight_name for item in advice if item.decision == "downweighted"]
    return {
        "enabled": bool(signals),
        "signal_run_id": str(signals[-1].get("signal_run_id") or "") if signals else "",
        "latest_issue": latest_issue,
        "signal_count": len(signals),
        "field_count": len(fields),
        "fields": fields,
        "budget": budget,
        "thresholds": thresholds or {
            "min_objective_delta": DEFAULT_WEIGHT_KDJ_MIN_OBJECTIVE_DELTA,
            "min_abs_offset": DEFAULT_WEIGHT_KDJ_MIN_ABS_OFFSET,
            "slope_window": DEFAULT_WEIGHT_KDJ_SLOPE_WINDOW,
            "neutral_band": DEFAULT_WEIGHT_KDJ_NEUTRAL_BAND,
        },
        "selected_count": counts.get("selected", 0),
        "downweighted_count": counts.get("downweighted", 0),
        "rejected_count": counts.get("rejected", 0),
        "selected_fields": selected_fields,
        "downweighted_fields": downweighted_fields,
        "scenario_counts": weight_kdj_advice_scenario_counts(advice),
        "path_count": len(advice),
        "candidate_count": len(configs),
        "advice": [item.as_dict() for item in advice],
        "mode": "advisor_only",
    }


def ridge_kdj_advisor_metadata(
    signals: list[dict],
    configs: tuple[FrequencyRankerConfig, ...],
    *,
    enabled: bool,
    budget: int = 0,
    params: dict | None = None,
    thresholds: dict | None = None,
    advice: tuple[RidgeKdjOffsetAdvice, ...] = (),
) -> dict:
    min_confidence = float((thresholds or {}).get("min_confidence", DEFAULT_RIDGE_KDJ_MIN_CONFIDENCE))
    eligible_advice = sorted(
        (
            item
            for item in advice
            if item.weight_name in ALL_FIELDS and item.confidence >= min_confidence and abs(float(item.suggested_offset)) > 0
        ),
        key=lambda item: (item.confidence, abs(item.suggested_offset), item.weight_name),
        reverse=True,
    )
    selected_advice = tuple(eligible_advice[: len(configs)])
    selected_advice_keys = {
        (item.weight_name, float(item.suggested_offset), float(item.confidence))
        for item in selected_advice
    }
    latest_signal_issue = max((str(signal.get("issue") or "") for signal in signals), default="")
    fields = sorted({str(signal.get("weight_name")) for signal in signals if signal.get("weight_name") in ALL_FIELDS})
    signal_run_id = str(signals[-1].get("signal_run_id") or "") if signals else ""
    return {
        "mode": "advisor_only",
        "enabled": enabled,
        "budget": budget,
        "params": params or {
            "step": DEFAULT_RIDGE_KDJ_STEP,
            "ridge_alpha": DEFAULT_RIDGE_KDJ_ALPHA,
        },
        "thresholds": thresholds or {
            "min_confidence": DEFAULT_RIDGE_KDJ_MIN_CONFIDENCE,
            "min_train_rows": DEFAULT_RIDGE_KDJ_MIN_TRAIN_ROWS,
            "min_validation_rows": DEFAULT_RIDGE_KDJ_MIN_VALIDATION_ROWS,
        },
        "signal_run_id": signal_run_id,
        "loaded_signals": len(signals),
        "latest_signal_issue": latest_signal_issue,
        "selected_count": len(selected_advice),
        "rejected_count": max(0, len(advice) - len(selected_advice)),
        "field_count": len(fields),
        "fields": fields,
        "selected_fields": [item.weight_name for item in selected_advice],
        "advice": [
            {
                "weight_name": item.weight_name,
                "confidence": item.confidence,
                "validation_metric": item.validation_metric,
                "baseline_metric": item.baseline_metric,
                "suggested_offset": item.suggested_offset,
                "train_rows": item.train_rows,
                "source": item.source,
                "decision": "selected"
                if (item.weight_name, float(item.suggested_offset), float(item.confidence)) in selected_advice_keys
                else "rejected",
            }
            for item in advice
        ],
        "candidate_count": len(configs),
        "config_hashes": bounded_unique_config_hashes(configs),
    }


def neural_kdj_advisor_metadata(
    signals: list[dict],
    configs: tuple[FrequencyRankerConfig, ...],
    *,
    enabled: bool,
    budget: int = 0,
    params: dict | None = None,
    thresholds: dict | None = None,
    advice: tuple[NeuralKdjOffsetAdvice, ...] = (),
) -> dict:
    min_confidence = float((thresholds or {}).get("min_confidence", DEFAULT_NEURAL_KDJ_MIN_CONFIDENCE))
    eligible_advice = sorted(
        (
            item
            for item in advice
            if item.weight_name in ALL_FIELDS and item.confidence >= min_confidence and abs(float(item.suggested_offset)) > 0
        ),
        key=lambda item: (item.confidence, abs(item.suggested_offset), item.weight_name),
        reverse=True,
    )
    selected_advice = tuple(eligible_advice[: len(configs)])
    selected_advice_keys = {
        (item.weight_name, float(item.suggested_offset), float(item.confidence))
        for item in selected_advice
    }
    latest_signal_issue = max((str(signal.get("issue") or "") for signal in signals), default="")
    fields = sorted({str(signal.get("weight_name")) for signal in signals if signal.get("weight_name") in ALL_FIELDS})
    signal_run_id = str(signals[-1].get("signal_run_id") or "") if signals else ""
    return {
        "mode": "advisor_only",
        "enabled": enabled,
        "budget": budget,
        "params": params or {
            "step": DEFAULT_NEURAL_KDJ_STEP,
            "seed": DEFAULT_NEURAL_KDJ_SEED,
            "hidden_units": DEFAULT_NEURAL_KDJ_HIDDEN_UNITS,
            "epochs": DEFAULT_NEURAL_KDJ_EPOCHS,
            "model": "numpy_mlp_kdj_offset_v0",
        },
        "thresholds": thresholds or {
            "min_confidence": DEFAULT_NEURAL_KDJ_MIN_CONFIDENCE,
        },
        "signal_run_id": signal_run_id,
        "loaded_signals": len(signals),
        "latest_signal_issue": latest_signal_issue,
        "selected_count": len(selected_advice),
        "rejected_count": max(0, len(advice) - len(selected_advice)),
        "field_count": len(fields),
        "fields": fields,
        "selected_fields": [item.weight_name for item in selected_advice],
        "advice": [
            {
                "weight_name": item.weight_name,
                "confidence": item.confidence,
                "validation_metric": item.validation_metric,
                "baseline_metric": item.baseline_metric,
                "suggested_offset": item.suggested_offset,
                "train_rows": item.train_rows,
                "validation_rows": item.validation_rows,
                "source": item.source,
                "decision": "selected"
                if (item.weight_name, float(item.suggested_offset), float(item.confidence)) in selected_advice_keys
                else "rejected",
            }
            for item in advice
        ],
        "candidate_count": len(configs),
        "config_hashes": bounded_unique_config_hashes(configs),
    }


def target_weight_inversion_advisor_metadata(
    *,
    enabled: bool,
    budget: int,
    aggregate: dict | None = None,
    configs: tuple[FrequencyRankerConfig, ...] = (),
    control_experiments: list[dict] | None = None,
    frozen_validation_window_value: int = 0,
    max_targets: int = DEFAULT_TARGET_WEIGHT_INVERSION_MAX_TARGETS,
    max_deltas_per_target: int = DEFAULT_TARGET_WEIGHT_INVERSION_MAX_DELTAS_PER_TARGET,
) -> dict:
    aggregate = aggregate if isinstance(aggregate, dict) else {}
    selected_hashes = set(bounded_unique_config_hashes(configs, limit=len(configs) or 1))
    candidate_rows = [candidate for candidate in aggregate.get("candidates") or [] if isinstance(candidate, dict)]
    advice = []
    for candidate in candidate_rows:
        label = str(candidate.get("label") or "")
        candidate_hash = str(candidate.get("config_hash") or "")
        delta_config = candidate.get("delta_config") if isinstance(candidate.get("delta_config"), dict) else {}
        decision = "selected" if candidate_hash in selected_hashes else "rejected"
        for field, offset in delta_config.items():
            advice.append(
                {
                    "weight_name": str(field),
                    "suggested_offset": float(offset or 0.0),
                    "confidence": float(aggregate.get("success_rate") or 0.0),
                    "validation_metric": float(aggregate.get("success_rate") or 0.0),
                    "baseline_metric": float(aggregate.get("hit_count") or 0.0) / max(1, int(aggregate.get("sample_count") or 0)),
                    "config_hash": candidate_hash,
                    "decision": decision,
                    "reason": label,
                    "source": "target_weight_inversion_v0",
                }
            )
    fields = sorted({str(item["weight_name"]) for item in advice} | {str(field) for field in aggregate.get("stable_fields") or []})
    selected_count = sum(1 for item in advice if item["decision"] == "selected")
    rejected_count = sum(1 for item in advice if item["decision"] == "rejected")
    candidate_count = len(configs)
    status = "ready" if enabled and candidate_count else ("waiting" if enabled else "disabled")
    return {
        "mode": "target_weight_inversion_v0",
        "enabled": enabled,
        "status": status,
        "budget": budget,
        "max_targets": max_targets,
        "max_deltas_per_target": max_deltas_per_target,
        "latest_issue": str(aggregate.get("latest_issue") or ""),
        "sample_count": int(aggregate.get("sample_count") or 0),
        "success_count": int(aggregate.get("success_count") or 0),
        "success_rate": float(aggregate.get("success_rate") or 0.0),
        "hit_count": int(aggregate.get("hit_count") or 0),
        "miss_count": int(aggregate.get("miss_count") or 0),
        "outlier_count": int(aggregate.get("outlier_count") or 0),
        "partial_improvement_count": int(aggregate.get("partial_improvement_count") or 0),
        "candidate_count": candidate_count,
        "field_count": len(fields),
        "fields": fields,
        "selected_count": selected_count,
        "rejected_count": rejected_count,
        "candidate_hashes": bounded_unique_config_hashes(configs),
        "candidate_labels": [
            str(candidate.get("label") or "")
            for candidate in candidate_rows
        ][: len(configs)],
        "advice": advice,
        "control_experiment_count": len(control_experiments or []),
        "control_experiments": control_experiments or [],
        "control_verdict": {
            "passed": False,
            "status": "queued_for_next_round",
            "language": "candidate queued for the next full 100-draw regression and frozen validation",
        },
        "frozen_validation": {
            "window": frozen_validation_window_value,
            "control_count": len(control_experiments or []),
        },
        "advisory_only": True,
    }


def target_weight_inversion_advisor(
    *,
    history: list,
    ranked_universe,
    best_summary: dict | None,
    train_window: int,
    train_mode: str,
    top_n: int,
    max_candidates: int = DEFAULT_TARGET_WEIGHT_INVERSION_MAX_CANDIDATES,
    max_targets: int = DEFAULT_TARGET_WEIGHT_INVERSION_MAX_TARGETS,
    max_deltas_per_target: int = DEFAULT_TARGET_WEIGHT_INVERSION_MAX_DELTAS_PER_TARGET,
    budget: int = DEFAULT_TARGET_WEIGHT_INVERSION_MAX_CANDIDATES,
    control_experiments: list[dict] | None = None,
    frozen_validation_window_value: int = 0,
) -> tuple[list[dict], dict, tuple[FrequencyRankerConfig, ...], dict]:
    safe_max_targets = max(0, int(max_targets))
    safe_max_deltas = max(1, int(max_deltas_per_target))
    if not isinstance(best_summary, dict) or max_candidates <= 0 or budget <= 0 or safe_max_targets <= 0:
        metadata = target_weight_inversion_advisor_metadata(
            enabled=False,
            budget=max(0, budget),
            control_experiments=control_experiments,
            frozen_validation_window_value=frozen_validation_window_value,
            max_targets=safe_max_targets,
            max_deltas_per_target=safe_max_deltas,
        )
        return [], {}, (), metadata
    target_results = best_summary.get("target_results")
    config_values = best_summary.get("config")
    if not isinstance(target_results, list) or not isinstance(config_values, dict):
        metadata = target_weight_inversion_advisor_metadata(
            enabled=True,
            budget=max(0, budget),
            control_experiments=control_experiments,
            frozen_validation_window_value=frozen_validation_window_value,
            max_targets=safe_max_targets,
            max_deltas_per_target=safe_max_deltas,
        )
        return [], {}, (), metadata
    base_config = FrequencyRankerConfig(**{**config_dict(FrequencyRankerConfig()), **config_values})
    inversions = invert_targets_for_summary(
        history=history,
        ranked_universe=ranked_universe,
        base_config=base_config,
        target_results=target_results,
        train_window=train_window,
        train_mode=train_mode,
        top_n=top_n,
        max_targets=safe_max_targets,
        max_delta_candidates=safe_max_deltas,
    )
    rows, aggregate, configs = target_inversion_payload(inversions=inversions, base_config=base_config)
    limited_configs = tuple(configs[: min(max(0, max_candidates), max(0, budget))])
    metadata = target_weight_inversion_advisor_metadata(
        enabled=True,
        budget=max(0, budget),
        aggregate=aggregate,
        configs=limited_configs,
        control_experiments=control_experiments,
        frozen_validation_window_value=frozen_validation_window_value,
        max_targets=safe_max_targets,
        max_deltas_per_target=safe_max_deltas,
    )
    return rows, aggregate, limited_configs, metadata


def near_miss_targets_for_cutoff(
    target_results: list[dict],
    *,
    cutoff: int,
    upper: int,
    limit: int,
) -> list[dict]:
    candidates: list[dict] = []
    for target in target_results:
        if not isinstance(target, dict):
            continue
        try:
            rank = int(target.get("rank") or 0)
        except (TypeError, ValueError):
            continue
        red_numbers = target.get("red_numbers")
        if cutoff < rank <= upper and isinstance(red_numbers, list) and len(red_numbers) == 6:
            candidates.append(target)
    candidates.sort(key=lambda item: (int(item.get("rank") or 0) - cutoff, str(item.get("issue") or "")))
    return candidates[: max(0, limit)]


def near_miss_inversion_advisor(
    *,
    history: list,
    ranked_universe,
    best_summary: dict | None,
    train_window: int,
    train_mode: str,
    enabled: bool,
    max_configs: int,
    max_delta_candidates: int = DEFAULT_TARGET_WEIGHT_INVERSION_MAX_DELTAS_PER_TARGET,
) -> tuple[tuple[FrequencyRankerConfig, ...], dict]:
    metadata = {
        "mode": "near_miss_cutoff_inversion_v0",
        "enabled": enabled,
        "status": "disabled" if not enabled else "waiting",
        "candidate_count": 0,
        "candidate_hashes": [],
        "bands": [],
        "reason": None,
    }
    if not enabled:
        metadata["reason"] = "below_stagnation_threshold"
        return (), metadata
    if max_configs <= 0:
        metadata["reason"] = "no_budget"
        return (), metadata
    if not isinstance(best_summary, dict):
        metadata["reason"] = "missing_summary"
        return (), metadata
    target_results = best_summary.get("target_results")
    config_values = best_summary.get("config")
    if not isinstance(target_results, list) or not isinstance(config_values, dict):
        metadata["reason"] = "missing_target_results"
        return (), metadata

    base_config = FrequencyRankerConfig(**{**config_dict(FrequencyRankerConfig()), **config_values})
    configs: list[FrequencyRankerConfig] = []
    seen: set[str] = set()
    bands: list[dict] = []
    for band in NEAR_MISS_INVERSION_CUTOFF_BANDS:
        cutoff = int(band["cutoff"])
        upper = int(band["upper"])
        targets = near_miss_targets_for_cutoff(
            target_results,
            cutoff=cutoff,
            upper=upper,
            limit=int(band["max_targets"]),
        )
        if targets:
            inversions = invert_targets_for_summary(
                history=history,
                ranked_universe=ranked_universe,
                base_config=base_config,
                target_results=targets,
                train_window=train_window,
                train_mode=train_mode,
                top_n=cutoff,
                max_targets=len(targets),
                max_delta_candidates=max(1, int(max_delta_candidates)),
            )
            _rows, aggregate, band_configs = target_inversion_payload(inversions=inversions, base_config=base_config)
            for config in band_configs:
                add_unique(configs, seen, config)
                if len(configs) >= max_configs:
                    break
        else:
            aggregate = {}
            band_configs = ()
        bands.append(
            {
                "cutoff": cutoff,
                "upper": upper,
                "target_count": len(targets),
                "target_issues": [str(target.get("issue") or "") for target in targets],
                "target_ranks": [int(target.get("rank") or 0) for target in targets],
                "success_count": int(aggregate.get("success_count") or 0),
                "partial_improvement_count": int(aggregate.get("partial_improvement_count") or 0),
                "candidate_count": len(band_configs),
                "candidate_hashes": bounded_unique_config_hashes(band_configs, limit=8),
            }
        )
        if len(configs) >= max_configs:
            break

    limited_configs = tuple(configs[:max_configs])
    metadata.update(
        {
            "status": "ready" if limited_configs else "waiting",
            "candidate_count": len(limited_configs),
            "candidate_hashes": bounded_unique_config_hashes(limited_configs, limit=len(limited_configs) or 1),
            "bands": bands,
            "reason": None if limited_configs else "no_near_miss_candidates",
        }
    )
    return limited_configs, metadata


def search_fields_for_phase(phase: str) -> tuple[str, ...]:
    phase_fields = PHASE_SEARCH_FIELDS.get(phase, CONTEXT_FIELDS)
    phase_set = set(phase_fields)
    return PRIMARY_FIELDS + phase_fields + tuple(field for field in CONTEXT_FIELDS if field not in phase_set)


def themed_candidate_configs(base: FrequencyRankerConfig, *, phase: str, step: float) -> tuple[FrequencyRankerConfig, ...]:
    bump = max(step, 0.04)
    candidates = [
        replace(
            base,
            first_last_sum_weight=base.first_last_sum_weight + bump,
            span_trend_weight=base.span_trend_weight + bump,
            sum_trend_weight=base.sum_trend_weight + bump,
            ac_trend_weight=base.ac_trend_weight + bump / 2,
            zone_ratio_weight=base.zone_ratio_weight + bump,
            parity_ratio_weight=base.parity_ratio_weight + bump / 2,
            stable_range_weight=base.stable_range_weight + bump,
        ),
        replace(
            base,
            big_small_ratio_weight=base.big_small_ratio_weight + bump / 2,
            prime_composite_weight=base.prime_composite_weight + bump / 2,
            mod012_weight=base.mod012_weight + bump,
            tail_distribution_weight=base.tail_distribution_weight + bump,
            sum_tail_weight=base.sum_tail_weight + bump / 2,
            red_omission_shape_weight=base.red_omission_shape_weight + bump,
            sum_span_omission_weight=base.sum_span_omission_weight - bump / 2,
        ),
        replace(
            base,
            previous_consecutive_weight=base.previous_consecutive_weight + bump,
            previous_overlap_weight=base.previous_overlap_weight - bump,
            recent_neighbor_weight=base.recent_neighbor_weight + bump / 2,
            lagged_consecutive_weight=base.lagged_consecutive_weight + bump / 2,
            recent_gap_shape_weight=base.recent_gap_shape_weight + bump / 2,
            recent_sum_span_weight=base.recent_sum_span_weight + bump / 2,
            consecutive_trend_weight=base.consecutive_trend_weight + bump,
            repeat_trend_weight=base.repeat_trend_weight + bump / 2,
        ),
        replace(
            base,
            weekday_trend_weight=base.weekday_trend_weight + bump,
            zone_ratio_weight=base.zone_ratio_weight + bump / 2,
            parity_ratio_weight=base.parity_ratio_weight + bump / 2,
            big_small_ratio_weight=base.big_small_ratio_weight + bump / 2,
            mod012_weight=base.mod012_weight + bump / 2,
            tail_distribution_weight=base.tail_distribution_weight + bump / 2,
            consecutive_trend_weight=base.consecutive_trend_weight + bump / 2,
            repeat_trend_weight=base.repeat_trend_weight + bump / 2,
        ),
    ]
    if phase == "large":
        candidates.extend(
            [
                FrequencyRankerConfig(
                    structural_weight=0.55,
                    frequency_weight=0.30,
                    omission_weight=0.15,
                    previous_consecutive_weight=0.00,
                ),
                FrequencyRankerConfig(
                    structural_weight=0.25,
                    frequency_weight=0.50,
                    omission_weight=0.25,
                    previous_consecutive_weight=0.00,
                ),
                FrequencyRankerConfig(
                    structural_weight=0.25,
                    frequency_weight=0.25,
                    omission_weight=0.50,
                    previous_consecutive_weight=0.00,
                ),
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
            ]
        )
    return tuple(candidates)


def generate_configs(
    base: FrequencyRankerConfig,
    *,
    phase: str,
    step: float,
    max_configs: int,
    elite_configs: tuple[FrequencyRankerConfig, ...] = (),
    historical_summaries: list[dict] | None = None,
    low_coverage_fields: tuple[str, ...] = (),
    stagnation_rounds: int = 0,
    round_index: int = 0,
) -> list[FrequencyRankerConfig]:
    configs: list[FrequencyRankerConfig] = []
    seen: set[str] = set()
    add_unique(configs, seen, base)
    budgets = candidate_budget(max_configs)
    search_fields = search_fields_for_phase(phase)
    historical_summaries = historical_summaries or []
    historical_configs = tuple(
        FrequencyRankerConfig(**{**config_dict(FrequencyRankerConfig()), **summary["config"]})
        for summary in historical_summaries
        if isinstance(summary.get("config"), dict)
    )
    fine_step = max(0.005, step / 2)
    exploitation_limit = budgets["exploitation"]
    for elite in elite_configs[:4]:
        add_unique_until(configs, seen, elite, limit=exploitation_limit)
    for elite in elite_configs[:2]:
        for field in PRIMARY_FIELDS:
            add_unique_until(configs, seen, replace(elite, **{field: getattr(elite, field) + fine_step}), limit=exploitation_limit)
            add_unique_until(configs, seen, replace(elite, **{field: getattr(elite, field) - fine_step}), limit=exploitation_limit)

    for config in themed_candidate_configs(base, phase=phase, step=step):
        add_unique_until(configs, seen, config, limit=exploitation_limit)

    for elite in elite_configs[:4]:
        for field in search_fields:
            if field in PRIMARY_FIELDS:
                continue
            add_unique_until(configs, seen, replace(elite, **{field: getattr(elite, field) + fine_step}), limit=exploitation_limit)
            add_unique_until(configs, seen, replace(elite, **{field: getattr(elite, field) - fine_step}), limit=exploitation_limit)

    if elite_configs:
        best = elite_configs[0]
        for other in elite_configs[1:4]:
            add_unique_until(configs, seen, blend_configs(best, other, 0.50), limit=exploitation_limit)
            add_unique_until(configs, seen, extrapolate_config(best, other, 0.50), limit=exploitation_limit)

    for field in search_fields:
        add_unique_until(configs, seen, replace(base, **{field: getattr(base, field) + step}), limit=exploitation_limit)
        add_unique_until(configs, seen, replace(base, **{field: getattr(base, field) - step}), limit=exploitation_limit)

    if phase in {"medium", "large"}:
        add_unique_until(
            configs,
            seen,
            replace(
                base,
                structural_weight=base.structural_weight + step,
                frequency_weight=base.frequency_weight - step / 2,
                omission_weight=base.omission_weight - step / 2,
            ),
            limit=exploitation_limit,
        )
        add_unique_until(
            configs,
            seen,
            replace(
                base,
                structural_weight=base.structural_weight - step / 2,
                frequency_weight=base.frequency_weight + step,
                omission_weight=base.omission_weight - step / 2,
            ),
            limit=exploitation_limit,
        )
        add_unique_until(
            configs,
            seen,
            replace(
                base,
                structural_weight=base.structural_weight - step / 2,
                frequency_weight=base.frequency_weight - step / 2,
                omission_weight=base.omission_weight + step,
            ),
            limit=exploitation_limit,
        )

    exploration_limit = exploitation_limit + budgets["exploration"]
    for config in exploratory_candidate_configs(
        base,
        phase=phase,
        step=step,
        low_coverage_fields=low_coverage_fields,
        stagnation_rounds=stagnation_rounds,
        seed=deterministic_seed("explore", phase, step, round_index, stagnation_rounds),
    ):
        add_unique_until(configs, seen, config, limit=exploration_limit)

    replay_limit = exploration_limit + budgets["replay"]
    for config in (
        replay_candidate_configs(base, historical_configs, seed=deterministic_seed("replay", phase, round_index))
        + surrogate_candidate_configs(
            base,
            historical_summaries,
            max_configs=max(1, budgets["replay"] // 2),
            seed=deterministic_seed("surrogate", phase, round_index),
        )
    ):
        add_unique_until(configs, seen, config, limit=replay_limit)

    baseline_limit = replay_limit + budgets["baseline"]
    for config in baseline_candidate_configs():
        add_unique_until(configs, seen, config, limit=baseline_limit)

    if stagnation_rounds >= STAGNATION_THRESHOLD:
        stagnation_configs: list[FrequencyRankerConfig] = []
        stagnation_seen = set(seen)
        for config in exploratory_candidate_configs(
            base,
            phase="large",
            step=max(step, 0.15),
            low_coverage_fields=low_coverage_fields or CONTEXT_FIELDS,
            stagnation_rounds=stagnation_rounds,
            seed=deterministic_seed("stagnation", phase, round_index, stagnation_rounds),
        ):
            key = config_hash(config)
            if key in stagnation_seen:
                continue
            stagnation_configs.append(config)
            stagnation_seen.add(key)
        if stagnation_configs:
            reserve = min(len(stagnation_configs), max(2, max_configs // 4), max_configs)
            final_configs = configs[:max_configs]
            final_seen = {config_hash(config) for config in final_configs}
            protected_hashes = {
                *(config_hash(config) for config in baseline_candidate_configs()),
                *(config_hash(config) for config in historical_configs),
            }
            replace_indexes = [
                index
                for index in range(len(final_configs) - 1, -1, -1)
                if config_hash(final_configs[index]) not in protected_hashes
            ]
            replaced = 0
            for config in stagnation_configs:
                key = config_hash(config)
                if key in final_seen:
                    continue
                if len(final_configs) < max_configs:
                    final_configs.append(config)
                    final_seen.add(key)
                    replaced += 1
                elif replace_indexes:
                    replace_index = replace_indexes.pop(0)
                    final_seen.discard(config_hash(final_configs[replace_index]))
                    final_configs[replace_index] = config
                    final_seen.add(key)
                    replaced += 1
                else:
                    break
                if replaced >= reserve:
                    break
            for config in configs:
                if len(final_configs) >= max_configs:
                    break
                key = config_hash(config)
                if key in final_seen:
                    continue
                final_configs.append(config)
                final_seen.add(key)
            return final_configs[:max_configs]

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
    baseline_overlap = summary.get("baseline_overlap") if isinstance(summary.get("baseline_overlap"), dict) else {}
    baseline_unique_reward = float(baseline_overlap.get("unique_reward") or 0.0)
    baseline_overlap_penalty = float(baseline_overlap.get("overlap_penalty") or 0.0)
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
        "baselineUniqueReward": round(baseline_unique_reward, 6),
        "baselineOverlapPenalty": round(baseline_overlap_penalty, 6),
        "red5Reward": round(red5_reward, 6),
        "rankQualityReward": round(rank_quality_reward, 6),
        "rankPenalty": round(rank_penalty, 6),
        "tailRiskPenalty": round(tail_risk_penalty, 6),
        "objectiveScore": round(
            hit_reward + baseline_unique_reward + red5_reward + rank_quality_reward - rank_penalty - tail_risk_penalty - baseline_overlap_penalty,
            6,
        ),
    }


def binomial_upper_tail_probability(trials: int, hits: int, probability: float) -> float:
    if trials <= 0:
        return 1.0
    hits = max(0, min(int(hits), int(trials)))
    probability = min(1.0, max(0.0, float(probability)))
    if hits <= 0:
        return 1.0
    if probability <= 0.0:
        return 0.0
    if probability >= 1.0:
        return 1.0
    return min(
        1.0,
        max(
            0.0,
            sum(
                comb(trials, value) * (probability**value) * ((1.0 - probability) ** (trials - value))
                for value in range(hits, trials + 1)
            ),
        ),
    )


def wilson_interval(hits: int, trials: int, *, z_score: float = 1.96) -> dict[str, float]:
    if trials <= 0:
        return {"low": 0.0, "high": 0.0}
    hits = max(0, min(int(hits), int(trials)))
    z2 = z_score * z_score
    phat = hits / trials
    denominator = 1.0 + z2 / trials
    center = (phat + z2 / (2 * trials)) / denominator
    margin = z_score * sqrt((phat * (1.0 - phat) + z2 / (4 * trials)) / trials) / denominator
    return {
        "low": round(max(0.0, center - margin), 6),
        "high": round(min(1.0, center + margin), 6),
    }


def probability_band_diagnostic(
    *,
    label: str,
    cutoff: int,
    hits: int,
    trials: int,
    universe_size: int,
) -> dict:
    safe_universe = max(1, int(universe_size))
    safe_trials = max(0, int(trials))
    null_probability = min(1.0, max(0.0, float(cutoff) / safe_universe))
    expected_hits = safe_trials * null_probability
    observed_rate = (hits / safe_trials) if safe_trials else 0.0
    return {
        "label": label,
        "cutoff": int(cutoff),
        "hits": int(hits),
        "trials": safe_trials,
        "null_probability": round(null_probability, 10),
        "expected_hits": round(expected_hits, 6),
        "observed_rate": round(observed_rate, 6),
        "lift_vs_null": round(hits / expected_hits, 6) if expected_hits > 0 else None,
        "binomial_tail_p_value": round(
            binomial_upper_tail_probability(safe_trials, int(hits), null_probability),
            10,
        ),
        "wilson_interval_95": wilson_interval(int(hits), safe_trials),
    }


def rank_percentile(rank: int | float | None, *, universe_size: int) -> float | None:
    if not isinstance(rank, int | float):
        return None
    safe_universe = max(1, int(universe_size))
    return round(max(0.0, min(1.0, 1.0 - (float(rank) - 1.0) / safe_universe)), 6)


def probability_calibration_diagnostics(summary: dict, *, universe_size: int = DEFAULT_UNIVERSE_SIZE) -> dict:
    trials = int(summary.get("evaluated_draws") or 0)
    rank_quality = summary.get("rank_quality") if isinstance(summary.get("rank_quality"), dict) else {}
    target_results = summary.get("target_results") if isinstance(summary.get("target_results"), list) else []
    bands = [
        probability_band_diagnostic(
            label="top_100",
            cutoff=100,
            hits=int(summary.get("top_100_hits") or 0),
            trials=trials,
            universe_size=universe_size,
        ),
        probability_band_diagnostic(
            label="top_1000",
            cutoff=1000,
            hits=int(summary.get("top_1000_hits") or 0),
            trials=trials,
            universe_size=universe_size,
        ),
        probability_band_diagnostic(
            label="top_10000",
            cutoff=10000,
            hits=int(summary.get("top_10000_hits") or 0),
            trials=trials,
            universe_size=universe_size,
        ),
        probability_band_diagnostic(
            label="top_50000",
            cutoff=50000,
            hits=int(rank_quality.get("top_50000_hits") or 0),
            trials=trials,
            universe_size=universe_size,
        ),
    ]
    near_miss_windows = []
    for band in NEAR_MISS_INVERSION_CUTOFF_BANDS:
        cutoff = int(band["cutoff"])
        upper = int(band["upper"])
        count = 0
        issues: list[str] = []
        for target in target_results:
            if not isinstance(target, dict):
                continue
            rank = target.get("rank")
            if isinstance(rank, int | float) and cutoff < int(rank) <= upper:
                count += 1
                issues.append(str(target.get("issue") or ""))
        window_probability = max(0, upper - cutoff) / max(1, universe_size)
        near_miss_windows.append(
            {
                "cutoff": cutoff,
                "upper": upper,
                "count": count,
                "expected_count": round(trials * window_probability, 6),
                "lift_vs_null": round(count / (trials * window_probability), 6) if trials * window_probability > 0 else None,
                "issues": issues[:12],
            }
        )
    return {
        "mode": "null_binomial_rank_calibration_v0",
        "universe_size": int(universe_size),
        "trials": trials,
        "bands": bands,
        "rank_percentiles": {
            "best": rank_percentile(summary.get("best_rank"), universe_size=universe_size),
            "median": rank_percentile(summary.get("median_rank"), universe_size=universe_size),
            "worst": rank_percentile(summary.get("worst_rank"), universe_size=universe_size),
            "p90": rank_percentile(rank_quality.get("p90_rank"), universe_size=universe_size),
            "p95": rank_percentile(rank_quality.get("p95_rank"), universe_size=universe_size),
        },
        "near_miss_windows": near_miss_windows,
        "interpretation_note": "Unadjusted null diagnostics; repeated training rounds and candidate search require separate multiple-testing caution.",
    }


def finite_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return result if isfinite(result) else default


def _probability_calibration_for_score(summary: dict | None) -> dict:
    if not isinstance(summary, dict):
        return {}
    calibration = summary.get("probability_calibration")
    if isinstance(calibration, dict):
        return calibration
    return probability_calibration_diagnostics(summary)


def probability_calibration_score(summary: dict | None) -> tuple:
    calibration = _probability_calibration_for_score(summary)
    bands = calibration.get("bands") if isinstance(calibration.get("bands"), list) else []
    by_label = {
        str(band.get("label") or ""): band
        for band in bands
        if isinstance(band, dict)
    }

    def band_score(label: str) -> tuple[int, float, float]:
        band = by_label.get(label) or {}
        hits = int(band.get("hits") or 0)
        p_value = min(1.0, max(0.0, finite_float(band.get("binomial_tail_p_value"), 1.0)))
        lift = finite_float(band.get("lift_vs_null"), 0.0)
        return hits, -p_value, lift

    near_miss_windows = calibration.get("near_miss_windows")
    near_miss_count = 0
    near_miss_lift = 0.0
    if isinstance(near_miss_windows, list):
        for window in near_miss_windows:
            if not isinstance(window, dict):
                continue
            near_miss_count += int(window.get("count") or 0)
            near_miss_lift += finite_float(window.get("lift_vs_null"), 0.0)
    percentiles = calibration.get("rank_percentiles") if isinstance(calibration.get("rank_percentiles"), dict) else {}
    return (
        *band_score("top_100"),
        *band_score("top_1000"),
        *band_score("top_10000"),
        *band_score("top_50000"),
        near_miss_count,
        round(near_miss_lift, 6),
        finite_float(percentiles.get("best"), 0.0),
        finite_float(percentiles.get("median"), 0.0),
    )


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


def target_result_payload(target: TargetRank) -> dict:
    return {
        "issue": target.issue,
        "draw_date": target.draw_date.isoformat() if target.draw_date else None,
        "red_numbers": list(target.red_numbers or ()),
        "rank": target.rank,
        "score": target.score,
        "hit_top_100": target.hit_top_100,
        "hit_top_1000": target.hit_top_1000,
        "hit_top_10000": target.hit_top_10000,
        "red5_rank": target.red5_rank,
        "red5_score": target.red5_score,
        "red5_numbers": list(target.red5_numbers) if target.red5_numbers else [],
        "red5_missing_number": target.red5_missing_number,
        "red5_extra_number": target.red5_extra_number,
        "hit_red5_top_100": target.hit_red5_top_100,
        "hit_red5_top_1000": target.hit_red5_top_1000,
        "hit_red5_top_10000": target.hit_red5_top_10000,
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
        "target_results": [target_result_payload(target) for target in target_ranks],
    }
    summary["reward"] = reward_summary(summary, universe_size=universe_size)
    summary["probability_calibration"] = probability_calibration_diagnostics(summary, universe_size=universe_size)
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
    baseline_overlap = summary.get("baseline_overlap") if isinstance(summary.get("baseline_overlap"), dict) else {}
    baseline_bands = baseline_overlap.get("bands") if isinstance(baseline_overlap.get("bands"), dict) else {}
    top_10000_overlap = baseline_bands.get("top_10000") if isinstance(baseline_bands.get("top_10000"), dict) else {}
    top_1000_overlap = baseline_bands.get("top_1000") if isinstance(baseline_bands.get("top_1000"), dict) else {}
    return (
        summary["top_100_hits"],
        summary["top_1000_hits"],
        int(top_1000_overlap.get("unique_hit_count") or 0),
        reward["objectiveScore"],
        -int(rank_quality.get("tail_over_1000000_count") or 0),
        -int(rank_quality.get("tail_over_900000_count") or 0),
        -int(rank_quality.get("tail_over_750000_count") or 0),
        int(top_10000_overlap.get("unique_hit_count") or 0),
        -int(top_10000_overlap.get("overlap_hit_count") or 0),
        summary["top_10000_hits"],
        int(rank_quality.get("top_50000_hits") or 0),
        int(rank_quality.get("top_100000_hits") or 0),
        int(rank_quality.get("top_250000_hits") or 0),
        int(rank_quality.get("top_500000_hits") or 0),
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


def load_db_supervisor_candidates(
    *,
    as_of_issue: str,
    history_fingerprint_value: str,
    train_window: int,
    train_mode: str,
    eval_window: int,
    top_n: int,
    universe_size: int,
    limit: int = 24,
) -> list[dict]:
    with get_connection() as conn:
        ensure_training_round_results_schema(conn)
        ensure_training_supervisor_best_schema(conn)
        raw_candidates = load_training_supervisor_best_candidate_summaries(
            conn,
            as_of_issue=as_of_issue,
            history_fingerprint=history_fingerprint_value,
            train_window=train_window,
            train_mode=train_mode,
            eval_window=eval_window,
            top_n=top_n,
            limit=limit,
        )
        raw_candidates.extend(
            load_training_round_candidate_summaries(
                conn,
                as_of_issue=as_of_issue,
                history_fingerprint=history_fingerprint_value,
                train_window=train_window,
                train_mode=train_mode,
                eval_window=eval_window,
                top_n=top_n,
                limit=limit,
            )
        )
    candidates: list[dict] = []
    for raw_candidate in raw_candidates:
        candidate = normalize_summary(raw_candidate, universe_size=universe_size)
        if candidate:
            candidates = merge_leaderboard(candidates, [candidate], limit=limit)
    return candidates


def carryover_candidate_configs_from_summaries(
    raw_candidates: list[object],
    *,
    current_as_of_issue: str,
    current_history_fingerprint: str,
    universe_size: int,
    limit: int = 16,
) -> tuple[FrequencyRankerConfig, ...]:
    stale_leaderboard: list[dict] = []
    merge_limit = max(limit * 4, limit)
    for raw_candidate in raw_candidates:
        candidate = normalize_summary(raw_candidate, universe_size=universe_size)
        if not candidate:
            continue
        if (
            candidate["as_of_issue"] == current_as_of_issue
            and candidate["history_fingerprint"] == current_history_fingerprint
        ):
            continue
        stale_leaderboard = merge_leaderboard(stale_leaderboard, [candidate], limit=merge_limit)

    configs: list[FrequencyRankerConfig] = []
    seen: set[str] = set()
    for candidate in stale_leaderboard:
        config = FrequencyRankerConfig(**candidate["config"])
        key = config_hash(config)
        if key in seen:
            continue
        seen.add(key)
        configs.append(config)
        if len(configs) >= limit:
            break
    return tuple(configs)


def merge_config_candidates(
    *config_sets: tuple[FrequencyRankerConfig, ...],
    limit: int = 16,
) -> tuple[FrequencyRankerConfig, ...]:
    configs: list[FrequencyRankerConfig] = []
    seen: set[str] = set()
    for config_set in config_sets:
        for config in config_set:
            key = config_hash(config)
            if key in seen:
                continue
            seen.add(key)
            configs.append(config)
            if len(configs) >= limit:
                return tuple(configs)
    return tuple(configs)


def load_prior_supervisor_carryover_configs(
    *,
    output_dir: Path,
    current_status_path: Path,
    current_as_of_issue: str,
    current_history_fingerprint: str,
    train_window: int,
    train_mode: str,
    eval_window: int,
    top_n: int,
    universe_size: int,
    limit: int = 16,
) -> tuple[FrequencyRankerConfig, ...]:
    raw_candidates: list[object] = []
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
        raw_candidates.append(status.get("best"))
        for round_info in status.get("rounds") or []:
            if isinstance(round_info, dict):
                raw_candidates.append(round_info.get("best"))
                raw_candidates.extend(round_info.get("top_results") or [])
    return carryover_candidate_configs_from_summaries(
        raw_candidates,
        current_as_of_issue=current_as_of_issue,
        current_history_fingerprint=current_history_fingerprint,
        universe_size=universe_size,
        limit=limit,
    )


def load_db_supervisor_carryover_configs(
    *,
    current_as_of_issue: str,
    current_history_fingerprint: str,
    train_window: int,
    train_mode: str,
    eval_window: int,
    top_n: int,
    universe_size: int,
    limit: int = 16,
) -> tuple[FrequencyRankerConfig, ...]:
    with get_connection() as conn:
        ensure_training_round_results_schema(conn)
        ensure_training_supervisor_best_schema(conn)
        raw_candidates = load_training_supervisor_best_carryover_candidate_summaries(
            conn,
            current_as_of_issue=current_as_of_issue,
            current_history_fingerprint=current_history_fingerprint,
            train_window=train_window,
            train_mode=train_mode,
            eval_window=eval_window,
            top_n=top_n,
            limit=max(limit * 2, limit),
        )
        raw_candidates.extend(
            load_training_round_carryover_candidate_summaries(
                conn,
                current_as_of_issue=current_as_of_issue,
                current_history_fingerprint=current_history_fingerprint,
                train_window=train_window,
                train_mode=train_mode,
                eval_window=eval_window,
                top_n=top_n,
                limit=max(limit * 4, limit),
            )
        )
    return carryover_candidate_configs_from_summaries(
        raw_candidates,
        current_as_of_issue=current_as_of_issue,
        current_history_fingerprint=current_history_fingerprint,
        universe_size=universe_size,
        limit=limit,
    )


def stagnation_round_count(rounds: list[dict]) -> int:
    count = 0
    for round_info in reversed(rounds):
        if round_info.get("improved"):
            break
        count += 1
    return count


def strip_target_results(summary: dict) -> dict:
    stripped = dict(summary)
    stripped.pop("target_results", None)
    return stripped


def summary_config_hash(summary: dict | None) -> str | None:
    if not isinstance(summary, dict):
        return None
    existing = summary.get("config_hash")
    if isinstance(existing, str) and existing:
        return existing
    config_values = summary.get("config")
    if not isinstance(config_values, dict):
        return None
    try:
        return config_hash(FrequencyRankerConfig(**{**config_dict(FrequencyRankerConfig()), **config_values}))
    except (TypeError, ValueError):
        return None


def summary_config(summary: dict | None) -> FrequencyRankerConfig | None:
    if not isinstance(summary, dict):
        return None
    config_values = summary.get("config")
    if not isinstance(config_values, dict):
        return None
    try:
        return FrequencyRankerConfig(**{**config_dict(FrequencyRankerConfig()), **config_values})
    except (TypeError, ValueError):
        return None


def summary_rank_vector_signature(summary: dict | None) -> tuple[tuple[str, int, int | None], ...] | None:
    if not isinstance(summary, dict):
        return None
    target_results = summary.get("target_results")
    if not isinstance(target_results, list) or not target_results:
        return None
    signature: list[tuple[str, int, int | None]] = []
    for target in target_results:
        if not isinstance(target, dict):
            return None
        rank = target.get("rank")
        if not isinstance(rank, int):
            return None
        red5_rank = target.get("red5_rank")
        signature.append((str(target.get("issue") or ""), rank, red5_rank if isinstance(red5_rank, int) else None))
    return tuple(signature)


def best_challenger_summary(
    summaries: list[dict],
    incumbent_config_hash: str | None,
    *,
    incumbent_summary: dict | None = None,
    excluded_config_hashes: set[str] | None = None,
    excluded_rank_signature_hashes: set[str] | None = None,
    base_config: FrequencyRankerConfig | None = None,
    min_config_distance: float = 0.0,
    require_frozen_primary_lift: bool = False,
    frozen_primary_lift_baseline: dict | None = None,
) -> dict | None:
    if not incumbent_config_hash:
        return None
    excluded = set(excluded_config_hashes or set())
    excluded.add(incumbent_config_hash)
    excluded_signatures = {hash_value for hash_value in (excluded_rank_signature_hashes or set()) if hash_value}
    baseline_primary_score = source_frontier_primary_score(frozen_primary_lift_baseline)
    challengers = []
    for summary in summaries:
        if (summary_config_hash(summary) or "") in excluded:
            continue
        if rank_signature_hash(summary) in excluded_signatures:
            continue
        if require_frozen_primary_lift and source_frontier_primary_score(summary) <= baseline_primary_score:
            continue
        summary_candidate_config = summary_config(summary)
        if (
            base_config is not None
            and summary_candidate_config is not None
            and min_config_distance > 0
            and config_distance(summary_candidate_config, base_config) < min_config_distance
        ):
            continue
        challengers.append(summary)
    incumbent_rank_signature = summary_rank_vector_signature(incumbent_summary)
    if incumbent_rank_signature is not None:
        for summary in challengers:
            candidate_signature = summary_rank_vector_signature(summary)
            if candidate_signature is not None and candidate_signature != incumbent_rank_signature:
                return summary
    return challengers[0] if challengers else None


def rank_vector_changed(left: dict | None, right: dict | None) -> bool:
    left_signature = summary_rank_vector_signature(left)
    right_signature = summary_rank_vector_signature(right)
    return left_signature is not None and right_signature is not None and left_signature != right_signature


def rank_vector_available(summary: dict | None) -> bool:
    return summary_rank_vector_signature(summary) is not None


def _target_weight_anchor_metrics(summary: dict | None) -> dict:
    if not isinstance(summary, dict):
        return {}
    reward = summary.get("reward") if isinstance(summary.get("reward"), dict) else {}
    red5 = summary.get("red5") if isinstance(summary.get("red5"), dict) else {}
    rank_quality = summary.get("rank_quality") if isinstance(summary.get("rank_quality"), dict) else {}
    return {
        "config_hash": summary_config_hash(summary) or "",
        "top_100_hits": int(summary.get("top_100_hits") or 0),
        "top_1000_hits": int(summary.get("top_1000_hits") or 0),
        "top_10000_hits": int(summary.get("top_10000_hits") or 0),
        "median_rank": summary.get("median_rank"),
        "best_rank": summary.get("best_rank"),
        "worst_rank": summary.get("worst_rank"),
        "objective_score": float(reward.get("objectiveScore") or 0.0),
        "red5_top_100_hits": int(red5.get("top_100_hits") or 0),
        "red5_top_1000_hits": int(red5.get("top_1000_hits") or 0),
        "red5_top_10000_hits": int(red5.get("top_10000_hits") or 0),
        "tail_over_1000000_count": int(rank_quality.get("tail_over_1000000_count") or 0),
        "tail_over_900000_count": int(rank_quality.get("tail_over_900000_count") or 0),
        "tail_over_750000_count": int(rank_quality.get("tail_over_750000_count") or 0),
        "rank_quality": rank_quality,
        "reward": reward,
    }


def select_target_weight_inversion_anchor(
    *,
    summaries: list[dict],
    prior_best_summary: dict | None,
    round_best: dict | None,
    improved: bool,
    require_frozen_primary_lift: bool = False,
    frozen_primary_lift_baseline: dict | None = None,
) -> tuple[dict | None, dict | None, dict]:
    incumbent_hash = summary_config_hash(prior_best_summary)
    round_best_hash = summary_config_hash(round_best)
    incumbent_for_rank_signature = round_best if incumbent_hash and round_best_hash == incumbent_hash else prior_best_summary
    baseline = frozen_primary_lift_baseline if isinstance(frozen_primary_lift_baseline, dict) else prior_best_summary
    baseline_primary_score = source_frontier_primary_score(baseline)
    challenger = best_challenger_summary(
        summaries,
        incumbent_hash,
        incumbent_summary=incumbent_for_rank_signature,
        require_frozen_primary_lift=require_frozen_primary_lift,
        frozen_primary_lift_baseline=baseline,
    )
    round_best_replays_incumbent = bool(incumbent_hash and round_best_hash == incumbent_hash)
    round_best_primary_score = source_frontier_primary_score(round_best)
    round_best_primary_allowed = bool(
        not require_frozen_primary_lift
        or improved
        or round_best_primary_score > baseline_primary_score
    )
    if improved:
        source = "new_best"
        anchor = round_best
    elif not round_best_primary_allowed and isinstance(prior_best_summary, dict):
        source = "incumbent_primary_gate"
        anchor = prior_best_summary
    elif round_best_replays_incumbent and challenger is not None:
        source = "challenger_best"
        anchor = challenger
    else:
        source = "round_best"
        anchor = round_best
    metadata = {
        "source": source,
        "round_best_replays_incumbent": round_best_replays_incumbent,
        "incumbent_config_hash": incumbent_hash or "",
        "round_best_config_hash": round_best_hash or "",
        "challenger_available": challenger is not None,
        "challenger_config_hash": summary_config_hash(challenger) or "",
        "challenger_rank_vector_changed": rank_vector_changed(incumbent_for_rank_signature, challenger),
        "challenger_rank_vector_available": rank_vector_available(challenger),
        "frozen_primary_lift_required": require_frozen_primary_lift,
        "frozen_primary_lift_baseline_score": list(baseline_primary_score),
        "round_best_frozen_primary_score": list(round_best_primary_score),
        "round_best_primary_allowed": round_best_primary_allowed,
        "challenger_frozen_primary_score": list(source_frontier_primary_score(challenger)),
        **_target_weight_anchor_metrics(anchor),
    }
    return anchor, challenger, metadata


def select_next_search_base(
    *,
    current_base: FrequencyRankerConfig,
    summaries: list[dict],
    round_best: dict | None,
    improved: bool,
    exploration_navigation_candidate: dict | None = None,
    exploration_navigation_source: str = "",
    exploration_navigation_reason: str = "",
    recent_search_base_hashes: tuple[str, ...] = (),
    excluded_rank_signature_hashes: tuple[str, ...] = (),
    min_config_distance: float = 0.0,
    allow_unpromoted_round_best: bool = True,
    round_best_skip_reason: str = "",
    require_frozen_primary_lift: bool = False,
    frozen_primary_lift_baseline: dict | None = None,
) -> tuple[FrequencyRankerConfig, dict]:
    current_base_hash = config_hash(current_base)
    current_base_summary = None
    for summary in summaries:
        if summary_config_hash(summary) == current_base_hash:
            current_base_summary = summary
            break
    primary_lift_baseline = (
        frozen_primary_lift_baseline
        if isinstance(frozen_primary_lift_baseline, dict)
        else current_base_summary
    )
    primary_lift_baseline_score = source_frontier_primary_score(primary_lift_baseline)
    round_best_config = summary_config(round_best)
    round_best_distance = (
        config_distance(round_best_config, current_base)
        if round_best_config is not None
        else 0.0
    )
    round_best_hash = summary_config_hash(round_best) or ""
    round_best_signature_hash = rank_signature_hash(round_best)
    round_best_search_allowed = bool(improved or allow_unpromoted_round_best)
    round_best_search_blocked = bool(
        round_best is not None
        and not improved
        and not allow_unpromoted_round_best
    )
    blocked_round_best_hashes = {round_best_hash} if round_best_search_blocked and round_best_hash else set()
    excluded_hashes = {hash_value for hash_value in recent_search_base_hashes if hash_value}
    excluded_hashes.add(current_base_hash)
    excluded_hashes.update(blocked_round_best_hashes)
    search_challenger = best_challenger_summary(
        summaries,
        current_base_hash,
        incumbent_summary=current_base_summary,
        excluded_config_hashes=excluded_hashes,
        excluded_rank_signature_hashes=set(excluded_rank_signature_hashes),
        base_config=current_base,
        min_config_distance=min_config_distance,
        require_frozen_primary_lift=require_frozen_primary_lift,
        frozen_primary_lift_baseline=primary_lift_baseline,
    )
    fallback_search_challenger = None
    if search_challenger is None:
        fallback_search_challenger = best_challenger_summary(
            summaries,
            current_base_hash,
            incumbent_summary=current_base_summary,
            excluded_config_hashes=blocked_round_best_hashes,
            excluded_rank_signature_hashes=set(excluded_rank_signature_hashes),
            require_frozen_primary_lift=require_frozen_primary_lift,
            frozen_primary_lift_baseline=primary_lift_baseline,
        )
    exploration_navigation_hash = summary_config_hash(exploration_navigation_candidate) or ""
    exploration_navigation_config = summary_config(exploration_navigation_candidate)
    exploration_navigation_distance = (
        config_distance(exploration_navigation_config, current_base)
        if exploration_navigation_config is not None
        else None
    )
    exploration_navigation_eligible = bool(
        require_frozen_primary_lift
        and exploration_navigation_candidate is not None
        and exploration_navigation_hash not in excluded_hashes
        and rank_signature_hash(exploration_navigation_candidate) not in set(excluded_rank_signature_hashes)
        and exploration_navigation_config is not None
        and (exploration_navigation_distance or 0.0) >= min_config_distance
        and source_frontier_primary_score(exploration_navigation_candidate) <= primary_lift_baseline_score
        and rank_vector_changed(current_base_summary, exploration_navigation_candidate)
    )
    round_best_eligible = (
        round_best is not None
        and round_best_hash not in excluded_hashes
        and round_best_signature_hash not in set(excluded_rank_signature_hashes)
        and round_best_distance >= min_config_distance
        and (
            not require_frozen_primary_lift
            or source_frontier_primary_score(round_best) > primary_lift_baseline_score
        )
    )
    if improved:
        source = "new_best"
        selected_summary = round_best
    elif round_best_eligible and round_best_search_allowed:
        source = "round_best"
        selected_summary = round_best
    elif search_challenger is not None:
        source = "search_challenger"
        selected_summary = search_challenger
    elif fallback_search_challenger is not None:
        source = "search_challenger_revisit"
        selected_summary = fallback_search_challenger
    elif exploration_navigation_eligible:
        source = "experimental_navigation"
        selected_summary = exploration_navigation_candidate
    elif round_best is not None and round_best_search_allowed:
        source = "current_base_replay"
        selected_summary = round_best
    else:
        source = "unchanged"
        selected_summary = None
    selected_config = summary_config(selected_summary)
    next_base = selected_config or current_base
    previous_hash = current_base_hash
    next_hash = config_hash(next_base)
    search_challenger_config = summary_config(search_challenger)
    selected_distance = config_distance(next_base, current_base)
    metadata = {
        "source": source,
        "changed": next_hash != previous_hash,
        "previous_config_hash": previous_hash,
        "config_hash": next_hash,
        "candidate_config_hash": summary_config_hash(selected_summary) or "",
        "round_best_config_hash": round_best_hash,
        "search_challenger_config_hash": summary_config_hash(search_challenger) or "",
        "fallback_search_challenger_config_hash": summary_config_hash(fallback_search_challenger) or "",
        "rank_signature_hash": rank_signature_hash(selected_summary),
        "round_best_rank_signature_hash": round_best_signature_hash,
        "search_challenger_rank_signature_hash": rank_signature_hash(search_challenger),
        "excluded_rank_signature_hashes": list(excluded_rank_signature_hashes),
        "rank_signature_cooldown_hit": bool(
            selected_summary is not None
            and rank_signature_hash(selected_summary) in set(excluded_rank_signature_hashes)
            and not improved
        ),
        "round_best_search_allowed": round_best_search_allowed,
        "round_best_search_blocked": round_best_search_blocked,
        "round_best_skip_reason": round_best_skip_reason if round_best_search_blocked else "",
        "frozen_primary_lift_required": require_frozen_primary_lift,
        "frozen_primary_lift_baseline_score": list(primary_lift_baseline_score),
        "selected_frozen_primary_score": list(source_frontier_primary_score(selected_summary)),
        "round_best_frozen_primary_score": list(source_frontier_primary_score(round_best)),
        "search_challenger_frozen_primary_score": list(source_frontier_primary_score(search_challenger)),
        "fallback_search_challenger_frozen_primary_score": list(source_frontier_primary_score(fallback_search_challenger)),
        "exploration_navigation_config_hash": exploration_navigation_hash,
        "exploration_navigation_source": exploration_navigation_source if exploration_navigation_hash else "",
        "exploration_navigation_reason": exploration_navigation_reason if exploration_navigation_hash else "",
        "exploration_navigation_eligible": exploration_navigation_eligible,
        "exploration_navigation_frozen_primary_score": list(source_frontier_primary_score(exploration_navigation_candidate)),
        "exploration_navigation_config_distance": exploration_navigation_distance,
        "exploration_navigation_rank_vector_changed": rank_vector_changed(
            current_base_summary, exploration_navigation_candidate
        ),
        "round_best_config_distance": round_best_distance if round_best_config is not None else None,
        "min_config_distance": min_config_distance,
        "selected_config_distance": selected_distance,
        "search_challenger_config_distance": config_distance(search_challenger_config, current_base)
        if search_challenger_config is not None
        else None,
        "search_challenger_rank_vector_changed": rank_vector_changed(current_base_summary, search_challenger),
        "search_challenger_rank_vector_available": rank_vector_available(search_challenger),
        "recent_search_base_hashes": list(recent_search_base_hashes),
        "top_100_hits": int(selected_summary.get("top_100_hits") or 0) if isinstance(selected_summary, dict) else 0,
        "top_1000_hits": int(selected_summary.get("top_1000_hits") or 0) if isinstance(selected_summary, dict) else 0,
        "top_10000_hits": int(selected_summary.get("top_10000_hits") or 0) if isinstance(selected_summary, dict) else 0,
        "median_rank": selected_summary.get("median_rank") if isinstance(selected_summary, dict) else None,
        "best_rank": selected_summary.get("best_rank") if isinstance(selected_summary, dict) else None,
        "worst_rank": selected_summary.get("worst_rank") if isinstance(selected_summary, dict) else None,
        "config": config_dict(next_base),
        **_target_weight_anchor_metrics(selected_summary),
    }
    return next_base, metadata


def stale_round_best_search_base_gate(
    *,
    stagnation_rounds: int,
    rank_homogeneity: dict,
    promotion_gate: dict,
    eval_slice_overfit: dict | None = None,
) -> dict:
    threshold = PROBABILITY_PRIMARY_GATE_STAGNATION_THRESHOLD
    rank_homogeneity_active = bool(rank_homogeneity.get("active"))
    promotion_passed = bool(promotion_gate.get("passed")) if isinstance(promotion_gate, dict) else False
    primary_hit_passed = bool(promotion_gate.get("primary_hit_passed")) if isinstance(promotion_gate, dict) else False
    eval_slice_overfit_active = bool(eval_slice_overfit.get("active")) if isinstance(eval_slice_overfit, dict) else False
    active = bool(
        eval_slice_overfit_active
        or (
            rank_homogeneity_active
            and stagnation_rounds >= threshold
            and not promotion_passed
            and not primary_hit_passed
        )
    )
    if eval_slice_overfit_active:
        reason = str(eval_slice_overfit.get("reason") or "eval_slice_overfit_no_frozen_primary_lift")
    elif active:
        reason = "stale_unpromoted_round_best_primary_gate"
    elif promotion_passed:
        reason = "promotion_passed"
    elif primary_hit_passed:
        reason = "primary_hit_passed"
    elif stagnation_rounds < threshold:
        reason = "below_threshold"
    elif not rank_homogeneity_active:
        reason = "rank_homogeneity_inactive"
    else:
        reason = "inactive"
    return {
        "active": active,
        "reason": reason,
        "threshold": threshold,
        "stagnation_rounds": stagnation_rounds,
        "rank_homogeneity_active": rank_homogeneity_active,
        "promotion_passed": promotion_passed,
        "primary_hit_passed": primary_hit_passed,
        "eval_slice_overfit_active": eval_slice_overfit_active,
        "allow_unpromoted_round_best": not active,
        "require_frozen_primary_challenger": active,
    }


def select_decision_round_best(
    *,
    round_best: dict | None,
    prior_best_summary: dict | None,
    improved: bool,
    probability_focus_decision_summary: dict | None = None,
    probability_champion: dict | None = None,
    source_frontier_champion: dict | None = None,
    restart_champion: dict | None = None,
    exploration_champion: dict | None = None,
    require_frozen_primary_lift: bool = False,
) -> tuple[dict | None, dict]:
    baseline_primary_score = source_frontier_primary_score(prior_best_summary)
    metadata = {
        "source": "",
        "config_hash": "",
        "improved": improved,
        "frozen_primary_lift_required": require_frozen_primary_lift,
        "frozen_primary_lift_baseline_score": list(baseline_primary_score),
        "selected_frozen_primary_score": [],
        "blocked_candidates": [],
        "reason": None,
    }
    if improved:
        selected = round_best
        metadata.update(
            {
                "source": "new_best",
                "config_hash": summary_config_hash(selected) or "",
                "selected_frozen_primary_score": list(source_frontier_primary_score(selected)),
                "reason": "new_best",
            }
        )
        return selected, metadata

    candidates = (
        ("probability_focus", probability_focus_decision_summary),
        ("probability_calibration", probability_champion),
        ("source_frontier", source_frontier_champion),
        ("rank_homogeneity_restart", restart_champion),
        ("exploration", exploration_champion),
    )
    blocked_candidates: list[dict] = []
    for source, candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        candidate_primary_score = source_frontier_primary_score(candidate)
        if require_frozen_primary_lift and candidate_primary_score <= baseline_primary_score:
            blocked_candidates.append(
                {
                    "source": source,
                    "config_hash": summary_config_hash(candidate) or "",
                    "frozen_primary_score": list(candidate_primary_score),
                }
            )
            continue
        metadata.update(
            {
                "source": source,
                "config_hash": summary_config_hash(candidate) or "",
                "selected_frozen_primary_score": list(candidate_primary_score),
                "blocked_candidates": blocked_candidates,
                "reason": "selected_candidate",
            }
        )
        return candidate, metadata

    if require_frozen_primary_lift and isinstance(prior_best_summary, dict):
        metadata.update(
            {
                "source": "incumbent",
                "config_hash": summary_config_hash(prior_best_summary) or "",
                "selected_frozen_primary_score": list(source_frontier_primary_score(prior_best_summary)),
                "blocked_candidates": blocked_candidates,
                "reason": "incumbent_due_to_required_frozen_primary_lift",
            }
        )
        return prior_best_summary, metadata

    metadata.update(
        {
            "source": "round_best",
            "config_hash": summary_config_hash(round_best) or "",
            "selected_frozen_primary_score": list(source_frontier_primary_score(round_best)),
            "blocked_candidates": blocked_candidates,
            "reason": "round_best_default",
        }
    )
    return round_best, metadata


def should_refresh_probability_focus(
    *,
    champion_config: FrequencyRankerConfig | None,
    champion_hash: str,
    champion_score: tuple,
    probability_focus_hash: str,
    probability_focus_score: tuple,
) -> bool:
    if champion_config is None or not champion_hash:
        return False
    if not probability_focus_hash or not probability_focus_score:
        return True
    return champion_score > probability_focus_score


def select_probability_focus_search_base(
    *,
    current_base: FrequencyRankerConfig,
    focus_summary: dict | None,
    focus_info: dict,
    excluded_rank_signature_hashes: tuple[str, ...] = (),
    recent_search_base_hashes: tuple[str, ...] = (),
    min_config_distance: float = 0.0,
    require_frozen_primary_lift: bool = False,
    frozen_primary_lift_baseline: dict | None = None,
) -> tuple[FrequencyRankerConfig | None, dict]:
    selected_config = summary_config(focus_summary)
    current_base_hash = config_hash(current_base)
    baseline_primary_score = source_frontier_primary_score(frozen_primary_lift_baseline)
    focus_primary_score = source_frontier_primary_score(focus_summary)
    if not focus_info.get("active") or selected_config is None:
        return None, {
            "source": "probability_focus",
            "active": False,
            "changed": False,
            "previous_config_hash": current_base_hash,
            "config_hash": current_base_hash,
            "candidate_config_hash": summary_config_hash(focus_summary) or "",
            "reason": "missing_focus_config" if focus_info.get("active") else "inactive",
            "min_config_distance": min_config_distance,
            "frozen_primary_lift_required": require_frozen_primary_lift,
            "frozen_primary_lift_baseline_score": list(baseline_primary_score),
            "selected_frozen_primary_score": list(focus_primary_score),
            "recent_search_base_hashes": list(recent_search_base_hashes),
            "config": config_dict(current_base),
        }
    if require_frozen_primary_lift and focus_primary_score <= baseline_primary_score:
        return None, {
            "source": "probability_focus",
            "active": False,
            "changed": False,
            "previous_config_hash": current_base_hash,
            "config_hash": current_base_hash,
            "candidate_config_hash": summary_config_hash(focus_summary) or "",
            "rank_signature_hash": rank_signature_hash(focus_summary),
            "excluded_rank_signature_hashes": list(excluded_rank_signature_hashes),
            "rank_signature_cooldown_hit": False,
            "min_config_distance": min_config_distance,
            "selected_config_distance": config_distance(selected_config, current_base),
            "frozen_primary_lift_required": require_frozen_primary_lift,
            "frozen_primary_lift_baseline_score": list(baseline_primary_score),
            "selected_frozen_primary_score": list(focus_primary_score),
            "recent_search_base_hashes": list(recent_search_base_hashes),
            "reason": "frozen_primary_lift_required",
            "config": config_dict(current_base),
        }
    focus_rank_signature_hash = rank_signature_hash(focus_summary)
    if focus_rank_signature_hash in set(excluded_rank_signature_hashes):
        return None, {
            "source": "probability_focus",
            "active": False,
            "changed": False,
            "previous_config_hash": current_base_hash,
            "config_hash": current_base_hash,
            "candidate_config_hash": summary_config_hash(focus_summary) or "",
            "rank_signature_hash": focus_rank_signature_hash,
            "excluded_rank_signature_hashes": list(excluded_rank_signature_hashes),
            "rank_signature_cooldown_hit": True,
            "min_config_distance": min_config_distance,
            "frozen_primary_lift_required": require_frozen_primary_lift,
            "frozen_primary_lift_baseline_score": list(baseline_primary_score),
            "selected_frozen_primary_score": list(focus_primary_score),
            "recent_search_base_hashes": list(recent_search_base_hashes),
            "reason": "rank_signature_cooldown",
            "config": config_dict(current_base),
        }

    next_hash = config_hash(selected_config)
    selected_distance = config_distance(selected_config, current_base)
    recent_hashes = {hash_value for hash_value in recent_search_base_hashes if hash_value}
    if next_hash in recent_hashes:
        return None, {
            "source": "probability_focus",
            "active": False,
            "changed": False,
            "previous_config_hash": current_base_hash,
            "config_hash": current_base_hash,
            "candidate_config_hash": summary_config_hash(focus_summary) or "",
            "rank_signature_hash": focus_rank_signature_hash,
            "excluded_rank_signature_hashes": list(excluded_rank_signature_hashes),
            "rank_signature_cooldown_hit": False,
            "min_config_distance": min_config_distance,
            "selected_config_distance": selected_distance,
            "frozen_primary_lift_required": require_frozen_primary_lift,
            "frozen_primary_lift_baseline_score": list(baseline_primary_score),
            "selected_frozen_primary_score": list(focus_primary_score),
            "recent_search_base_hashes": list(recent_search_base_hashes),
            "reason": "search_base_cooldown",
            "config": config_dict(current_base),
        }
    if min_config_distance > 0 and selected_distance < min_config_distance:
        return None, {
            "source": "probability_focus",
            "active": False,
            "changed": False,
            "previous_config_hash": current_base_hash,
            "config_hash": current_base_hash,
            "candidate_config_hash": summary_config_hash(focus_summary) or "",
            "rank_signature_hash": focus_rank_signature_hash,
            "excluded_rank_signature_hashes": list(excluded_rank_signature_hashes),
            "rank_signature_cooldown_hit": False,
            "min_config_distance": min_config_distance,
            "selected_config_distance": selected_distance,
            "frozen_primary_lift_required": require_frozen_primary_lift,
            "frozen_primary_lift_baseline_score": list(baseline_primary_score),
            "selected_frozen_primary_score": list(focus_primary_score),
            "recent_search_base_hashes": list(recent_search_base_hashes),
            "reason": "search_base_too_close",
            "config": config_dict(current_base),
        }
    metadata = {
        "source": "probability_focus",
        "active": True,
        "changed": next_hash != current_base_hash,
        "previous_config_hash": current_base_hash,
        "config_hash": next_hash,
        "candidate_config_hash": summary_config_hash(focus_summary) or "",
        "search_challenger_config_hash": "",
        "fallback_search_challenger_config_hash": "",
        "rank_signature_hash": focus_rank_signature_hash,
        "excluded_rank_signature_hashes": list(excluded_rank_signature_hashes),
        "rank_signature_cooldown_hit": False,
        "min_config_distance": min_config_distance,
        "selected_config_distance": selected_distance,
        "frozen_primary_lift_required": require_frozen_primary_lift,
        "frozen_primary_lift_baseline_score": list(baseline_primary_score),
        "selected_frozen_primary_score": list(focus_primary_score),
        "search_challenger_config_distance": None,
        "search_challenger_rank_vector_changed": False,
        "search_challenger_rank_vector_available": False,
        "recent_search_base_hashes": list(recent_search_base_hashes),
        "focus_source": str(focus_info.get("source") or ""),
        "focus_reason": str(focus_info.get("reason") or ""),
        "hold_rounds": int(focus_info.get("hold_rounds") or 0),
        "remaining_rounds": int(focus_info.get("remaining_rounds") or 0),
        "refreshed": bool(focus_info.get("refreshed")),
        "top_100_hits": int(focus_summary.get("top_100_hits") or 0) if isinstance(focus_summary, dict) else 0,
        "top_1000_hits": int(focus_summary.get("top_1000_hits") or 0) if isinstance(focus_summary, dict) else 0,
        "top_10000_hits": int(focus_summary.get("top_10000_hits") or 0) if isinstance(focus_summary, dict) else 0,
        "median_rank": focus_summary.get("median_rank") if isinstance(focus_summary, dict) else None,
        "best_rank": focus_summary.get("best_rank") if isinstance(focus_summary, dict) else None,
        "worst_rank": focus_summary.get("worst_rank") if isinstance(focus_summary, dict) else None,
        "config": config_dict(selected_config),
        **_target_weight_anchor_metrics(focus_summary),
    }
    return selected_config, metadata


def recent_search_base_hashes(rounds: list[dict], current_base: FrequencyRankerConfig, *, limit: int = 6) -> tuple[str, ...]:
    hashes: list[str] = [config_hash(current_base)]
    for round_info in reversed(rounds[-limit:]):
        prefilter = round_info.get("prefilter") if isinstance(round_info.get("prefilter"), dict) else {}
        for key in ("search_base", "search_base_start"):
            item = prefilter.get(key) if isinstance(prefilter.get(key), dict) else {}
            hash_value = item.get("config_hash")
            if isinstance(hash_value, str) and hash_value:
                hashes.append(hash_value)
    deduped: list[str] = []
    for hash_value in hashes:
        if hash_value not in deduped:
            deduped.append(hash_value)
    return tuple(deduped[:limit])


def compact_round_info(round_info: dict) -> dict:
    compact = dict(round_info)
    compact["best"] = strip_target_results(compact["best"]) if isinstance(compact.get("best"), dict) else compact.get("best")
    compact["top_results"] = [
        strip_target_results(summary) if isinstance(summary, dict) else summary
        for summary in compact.get("top_results", [])
    ]
    return compact


def prefilter_configs(
    *,
    history: list,
    ranked_universe,
    configs: tuple[FrequencyRankerConfig, ...],
    keep_configs: tuple[FrequencyRankerConfig, ...],
    train_window: int,
    train_mode: str,
    eval_window: int,
    top_n: int,
    workers: int,
    pool,
    round_index: int,
    stride: int = 4,
    promote_limit: int = 8,
    diversity_quota: int = 2,
) -> tuple[tuple[FrequencyRankerConfig, ...], dict]:
    started = time.time()
    start_index = max(train_window, len(history) - eval_window)
    target_indices = list(range(start_index, len(history), max(1, stride)))
    if not configs or not target_indices:
        return configs, {
            "mode": "light_prefilter",
            "round": round_index,
            "target_stride": stride,
            "target_count": 0,
            "target_worker_count": 0,
            "generated_config_count": len(configs),
            "kept_config_count": len(keep_configs),
            "promote_limit": promote_limit,
            "diversity_quota": diversity_quota,
            "diversity_added_count": 0,
            "refined_config_count": len(configs),
            "elapsed_seconds": 0.0,
            "note": "预筛跳过：没有配置或目标期",
        }

    target_rank_lists: list[list[TargetRank]] = [[] for _ in configs]
    target_worker_count = max(1, min(workers, len(target_indices)))
    tasks = [
        (target_index, history, configs, train_window, train_mode, 1)
        for target_index in target_indices
    ]
    if target_worker_count > 1:
        context = _target_pool_context()
        with context.Pool(
            processes=target_worker_count,
            initializer=_init_target_worker,
            initargs=(ranked_universe,),
        ) as target_pool:
            target_results = list(target_pool.imap_unordered(_evaluate_prefilter_target_worker, tasks))
    else:
        _init_target_worker(ranked_universe)
        target_results = list(map(_evaluate_prefilter_target_worker, tasks))

    for _target_index, issue, ranked_targets in target_results:
        for config_index, (rank, score) in enumerate(ranked_targets):
            target_rank_lists[config_index].append(
                TargetRank(
                    issue=issue,
                    rank=rank,
                    score=score,
                    hit_top_100=rank <= 100,
                    hit_top_1000=rank <= 1000,
                    hit_top_10000=rank <= 10000,
                )
            )

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
    config_by_hash = {config_hash(config): config for config in configs}
    selected: list[FrequencyRankerConfig] = []
    seen: set[str] = set()

    def add_config(config: FrequencyRankerConfig) -> None:
        key = config_hash(config)
        resolved = config_by_hash.get(key, config)
        if key not in seen:
            selected.append(resolved)
            seen.add(key)

    for config in keep_configs:
        add_config(config)
    for summary in summaries[:promote_limit]:
        promoted = config_by_hash.get(summary["config_hash"])
        if promoted is not None:
            add_config(promoted)

    diversity_added = 0
    if diversity_quota > 0:
        diversity_pool = [config for config in configs if config_hash(config) not in seen]
        diversity_pool.sort(key=lambda config: weighted_config_distance(config, selected), reverse=True)
        for config in diversity_pool[:diversity_quota]:
            before = len(selected)
            add_config(config)
            if len(selected) > before:
                diversity_added += 1

    if not selected:
        selected = list(configs)
    metadata = {
        "mode": "light_prefilter",
        "round": round_index,
        "target_stride": stride,
        "target_count": len(target_indices),
        "target_worker_count": target_worker_count,
        "target_issues": [history_issue(history[index]) for index in target_indices],
        "generated_config_count": len(configs),
        "kept_config_count": len([config for config in keep_configs if config_hash(config) in config_by_hash]),
        "promote_limit": promote_limit,
        "diversity_quota": diversity_quota,
        "diversity_added_count": diversity_added,
        "refined_config_count": len(selected),
        "elapsed_seconds": round(time.time() - started, 3),
        "top_preview": summaries[: min(5, len(summaries))],
        "note": "预筛仅用于选择进入完整精排的配置，正式指标来自完整 100 期精排",
    }
    return tuple(selected), metadata


def _init_target_worker(ranked_universe) -> None:
    global _TARGET_WORKER_UNIVERSE
    _TARGET_WORKER_UNIVERSE = ranked_universe


def _evaluate_prefilter_target_worker(args: tuple) -> tuple[int, str, list[tuple[int, float]]]:
    (
        target_index,
        history,
        configs,
        train_window,
        train_mode,
        workers,
    ) = args
    if _TARGET_WORKER_UNIVERSE is None:
        raise RuntimeError("target worker universe is not initialized")
    train_start = 0 if train_mode == "expanding" else max(0, target_index - train_window)
    train_history = history[train_start:target_index]
    target_draw = history[target_index]
    issue = history_issue(target_draw)
    ranked_targets = rank_target_grid(
        target_numbers=history_numbers(target_draw),
        train_history=train_history,
        configs=configs,
        ranked_universe=_TARGET_WORKER_UNIVERSE,
        target_draw_date=history_draw_date(target_draw),
        workers=workers,
        pool=None,
    )
    return target_index, issue, ranked_targets


def _evaluate_target_worker(args: tuple) -> tuple[int, str, object, tuple[int, ...], int, list[tuple[int, float, object]]]:
    (
        progress_index,
        target_index,
        history,
        configs,
        train_window,
        train_mode,
        workers,
    ) = args
    if _TARGET_WORKER_UNIVERSE is None:
        raise RuntimeError("target worker universe is not initialized")
    train_start = 0 if train_mode == "expanding" else max(0, target_index - train_window)
    train_history = history[train_start:target_index]
    target_draw = history[target_index]
    issue = history_issue(target_draw)
    draw_date = history_draw_date(target_draw)
    red_numbers = history_numbers(target_draw)
    ranked_targets = rank_target_grid_with_red5(
        target_numbers=red_numbers,
        train_history=train_history,
        configs=configs,
        ranked_universe=_TARGET_WORKER_UNIVERSE,
        target_draw_date=history_draw_date(target_draw),
        workers=workers,
        pool=None,
    )
    return progress_index, issue, draw_date, red_numbers, len(train_history), ranked_targets


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
    target_results: list[tuple[int, str, object, tuple[int, ...], int, list[tuple[int, float, object]]] | None] = [
        None for _ in range(total_targets)
    ]
    started = time.time()

    tasks = [
        (progress_index, target_index, history, configs, train_window, train_mode, 1)
        for progress_index, target_index in enumerate(range(start_index, len(history)), start=1)
    ]
    target_worker_count = max(1, min(workers, total_targets))
    if target_worker_count > 1:
        context = _target_pool_context()
        with context.Pool(
            processes=target_worker_count,
            initializer=_init_target_worker,
            initargs=(ranked_universe,),
        ) as target_pool:
            iterator = target_pool.imap_unordered(_evaluate_target_worker, tasks)
            for completed_count, result in enumerate(iterator, start=1):
                progress_index, issue, _draw_date, _red_numbers, train_draws, _ranked_targets = result
                target_results[progress_index - 1] = result
                if progress_interval > 0 and (
                    completed_count == 1 or completed_count == total_targets or completed_count % progress_interval == 0
                ):
                    elapsed = time.time() - started
                    progress = training_progress_payload(
                        round_index=round_index,
                        target_index=completed_count,
                        target_total=total_targets,
                        issue=issue,
                        train_draws=train_draws,
                        elapsed_seconds=elapsed,
                    )
                    log(
                        f"round={round_index} target={completed_count}/{total_targets} "
                        f"issue={issue} train_draws={train_draws} elapsed={elapsed:.1f}s "
                        f"target_workers={target_worker_count}"
                    )
                    if progress_callback is not None:
                        progress_callback(progress)
    else:
        _init_target_worker(ranked_universe)
        for result in map(_evaluate_target_worker, tasks):
            progress_index, issue, _draw_date, _red_numbers, train_draws, _ranked_targets = result
            target_results[progress_index - 1] = result
            if progress_interval > 0 and (
                progress_index == 1 or progress_index == total_targets or progress_index % progress_interval == 0
            ):
                elapsed = time.time() - started
                progress = training_progress_payload(
                    round_index=round_index,
                    target_index=progress_index,
                    target_total=total_targets,
                    issue=issue,
                    train_draws=train_draws,
                    elapsed_seconds=elapsed,
                )
                log(
                    f"round={round_index} target={progress_index}/{total_targets} "
                    f"issue={issue} train_draws={train_draws} elapsed={elapsed:.1f}s "
                    f"target_workers={target_worker_count}"
                )
                if progress_callback is not None:
                    progress_callback(progress)

    target_rank_lists: list[list[TargetRank]] = [[] for _ in configs]
    for result in target_results:
        if result is None:
            continue
        _progress_index, issue, draw_date, red_numbers, _train_draws, ranked_targets = result
        for config_index, (rank, score, red5_match) in enumerate(ranked_targets):
            target_rank_lists[config_index].append(
                TargetRank(
                    issue=issue,
                    rank=rank,
                    score=score,
                    hit_top_100=rank <= 100,
                    hit_top_1000=rank <= 1000,
                    hit_top_10000=rank <= 10000,
                    draw_date=draw_date,
                    red_numbers=red_numbers,
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

    if progress_interval > 0 and not target_results:
        elapsed = time.time() - started
        progress = training_progress_payload(
            round_index=round_index,
            target_index=0,
            target_total=total_targets,
            issue="",
            train_draws=0,
            elapsed_seconds=elapsed,
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


def compact_status_payload(status: dict) -> dict:
    return {
        "run_id": status.get("run_id"),
        "started_at": status.get("started_at"),
        "updated_at": status.get("updated_at"),
        "deadline": status.get("deadline"),
        "status": status.get("status"),
        "pid": status.get("pid"),
        "history_scope": status.get("history_scope"),
        "regime_years": status.get("regime_years"),
        "regime_start_date": status.get("regime_start_date"),
        "train_mode": status.get("train_mode"),
        "train_window": status.get("train_window"),
        "eval_window": status.get("eval_window"),
        "top_n": status.get("top_n"),
        "workers": status.get("workers"),
        "memory_budget_gb": status.get("memory_budget_gb"),
        "legal_universe_size": status.get("legal_universe_size"),
        "ranked_universe_size": status.get("ranked_universe_size"),
        "excluded_universe_count": status.get("excluded_universe_count"),
        "universe_size": status.get("universe_size"),
        "matrix_backend": status.get("matrix_backend"),
        "feature_matrix_cache": status.get("feature_matrix_cache"),
        "red5_rank_mode": status.get("red5_rank_mode"),
        "prefilter": status.get("prefilter"),
        "weight_kdj_advisor": status.get("weight_kdj_advisor"),
        "ridge_kdj_advisor": status.get("ridge_kdj_advisor"),
        "neural_kdj_advisor": status.get("neural_kdj_advisor"),
        "target_weight_inversion_advisor": status.get("target_weight_inversion_advisor"),
        "near_miss_inversion_advisor": status.get("near_miss_inversion_advisor"),
        "probability_focus": status.get("probability_focus"),
        "carryover_seed": status.get("carryover_seed"),
        "qian_kun": status.get("qian_kun"),
        "next_candidates": status.get("next_candidates"),
        "search_base": status.get("search_base"),
        "latest_progress": status.get("latest_progress"),
        "status_path": status.get("status_path"),
        "report_path": status.get("report_path"),
    }


def publish_status_snapshot(
    status_path: Path,
    status: dict,
    *,
    event_url: str | None,
    write_json: bool,
) -> None:
    payload = compact_status_payload(status)
    if write_json:
        write_status(status_path, payload)
    if event_url is not None:
        post_training_event(payload, event_url=event_url)


def source_frontier_report_section(status: dict) -> str:
    latest_prefilter = (status.get("prefilter") or {}).get("latest")
    if not isinstance(latest_prefilter, dict):
        for round_info in reversed(status.get("rounds") or []):
            candidate = round_info.get("prefilter") if isinstance(round_info, dict) else None
            if isinstance(candidate, dict):
                latest_prefilter = candidate
                break
    frontier = latest_prefilter.get("source_frontier") if isinstance(latest_prefilter, dict) else None
    if not isinstance(frontier, dict):
        return "## Source Frontier\n\nNo source-frontier diagnostics recorded yet.\n"
    champion = latest_prefilter.get("source_frontier_champion") if isinstance(latest_prefilter, dict) else {}
    champion_line = (
        f"- Primary champion: active={bool(champion.get('active'))} "
        f"reason={champion.get('reason')} "
        f"source={champion.get('source', '')} "
        f"rank={champion.get('full_eval_rank')} "
        f"config_hash=`{champion.get('config_hash', '')}`"
        if isinstance(champion, dict)
        else "- Primary champion: unavailable"
    )
    primary_best = frontier.get("best_non_normal_primary") or {}
    secondary_best = frontier.get("best_non_normal_secondary") or {}
    rows: list[str] = []
    sources = frontier.get("sources") if isinstance(frontier.get("sources"), dict) else {}
    for source, info in sorted(sources.items()):
        if not isinstance(info, dict):
            continue
        best = info.get("best") if isinstance(info.get("best"), dict) else {}
        rows.append(
            f"| {source} | {info.get('generated', 0)} | {info.get('full_eval_count', 0)} | "
            f"{info.get('full_eval_top5', 0)} | {info.get('round_best', False)} | "
            f"{info.get('best_full_eval_rank')} | {best.get('top_10000_hits', 0)} | "
            f"{best.get('frozen_top_100_hits', 0)} | {best.get('frozen_top_1000_hits', 0)} | "
            f"{best.get('frozen_top_10000_hits', 0)} | {best.get('frozen_median_rank')} | "
            f"`{best.get('config_hash', '')}` |"
        )
    table = "\n".join(rows) or "| none | 0 | 0 | 0 | False |  | 0 | 0 | 0 | 0 |  | `` |"
    return f"""## Source Frontier

{champion_line}
- Baseline config hash: `{frontier.get("baseline_config_hash", "")}`
- Primary non-normal: `{primary_best.get("source", "")}` `{primary_best.get("config_hash", "")}`
- Secondary non-normal: `{secondary_best.get("source", "")}` `{secondary_best.get("config_hash", "")}`

| Source | Generated | Full eval | Top5 | Round best | Best rank | Best Top10000 | Frozen Top100 | Frozen Top1000 | Frozen Top10000 | Frozen median | Config hash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{table}
"""


def write_report(report_path: Path, status: dict) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    rounds = "\n".join(
        (
            f"| {round_info['round']} | {round_info['phase']} | "
            f"{round_info.get('generated_config_count', round_info['config_count'])} | {round_info['config_count']} | "
            f"{round_info.get('prefilter', {}).get('target_count', 0)} | {round_info['best']['top_10000_hits']} | "
            f"{round_info['best']['top_1000_hits']} | {round_info['best']['top_100_hits']} | "
            f"{round_info['best']['red5']['top_100_hits']} | {round_info['best']['red5']['top_10000_hits']} | "
            f"{round_info['best']['rank_quality']['top_50000_hits']} | {round_info['best']['worst_rank']} | "
            f"{round_info['best']['rank_quality'].get('tail_over_1000000_count', 0)} | "
            f"{round_info['best']['median_rank']} | `{json.dumps(round_info['best']['config'], sort_keys=True)}` |"
        )
        for round_info in status["rounds"]
    )
    best = status["best"]
    source_frontier = source_frontier_report_section(status)
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
- Legal universe size: {status.get("legal_universe_size", status["universe_size"])}
- Ranked universe size: {status.get("ranked_universe_size", status["universe_size"])}
- Excluded universe count: {status.get("excluded_universe_count", 0)}
- Universe size: {status["universe_size"]}
- Matrix backend: {status.get("matrix_backend", "")}
- Matrix cache: hit={status.get("feature_matrix_cache", {}).get("cache_hit")} build_seconds={status.get("feature_matrix_cache", {}).get("build_seconds")} path=`{status.get("feature_matrix_cache", {}).get("cache_path", "")}`
- Red5 rank mode: {status.get("red5_rank_mode", "")}
- Latest qian-kun pattern: {status["qian_kun"]["latest_issue"]} {status["qian_kun"]["latest_label"]} `{status["qian_kun"]["latest_pattern"]}`

## Current Best

```json
{json.dumps(best, ensure_ascii=False, indent=2, sort_keys=True)}
```

{source_frontier}

## Rounds

| Round | Phase | Generated | Refined | Prefilter targets | Top10000 | Top1000 | Top100 | Red5 Top100 | Red5 Top10000 | Top50000 | Worst rank | >100万 | Median rank | Config |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
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
    write_status_json: bool = False,
    enable_weight_kdj_advisor: bool = False,
    enable_ridge_kdj_advisor: bool = False,
    enable_neural_kdj_advisor: bool = False,
    enable_target_weight_inversion_advisor: bool = True,
    weight_kdj_run_id: str | None = None,
    weight_kdj_limit: int = 1000,
    weight_kdj_budget_share: float = DEFAULT_WEIGHT_KDJ_BUDGET_SHARE,
    weight_kdj_min_objective_delta: float = DEFAULT_WEIGHT_KDJ_MIN_OBJECTIVE_DELTA,
    weight_kdj_min_abs_offset: float = DEFAULT_WEIGHT_KDJ_MIN_ABS_OFFSET,
    weight_kdj_slope_window: int = DEFAULT_WEIGHT_KDJ_SLOPE_WINDOW,
    weight_kdj_neutral_band: float = DEFAULT_WEIGHT_KDJ_NEUTRAL_BAND,
    ridge_kdj_budget_share: float = DEFAULT_RIDGE_KDJ_BUDGET_SHARE,
    ridge_kdj_alpha: float = DEFAULT_RIDGE_KDJ_ALPHA,
    ridge_kdj_min_confidence: float = DEFAULT_RIDGE_KDJ_MIN_CONFIDENCE,
    ridge_kdj_min_train_rows: int = DEFAULT_RIDGE_KDJ_MIN_TRAIN_ROWS,
    ridge_kdj_min_validation_rows: int = DEFAULT_RIDGE_KDJ_MIN_VALIDATION_ROWS,
    neural_kdj_budget_share: float = DEFAULT_NEURAL_KDJ_BUDGET_SHARE,
    neural_kdj_min_confidence: float = DEFAULT_NEURAL_KDJ_MIN_CONFIDENCE,
    neural_kdj_seed: int = DEFAULT_NEURAL_KDJ_SEED,
    neural_kdj_hidden_units: int = DEFAULT_NEURAL_KDJ_HIDDEN_UNITS,
    neural_kdj_epochs: int = DEFAULT_NEURAL_KDJ_EPOCHS,
    target_weight_inversion_budget_share: float = DEFAULT_TARGET_WEIGHT_INVERSION_BUDGET_SHARE,
    target_weight_inversion_max_candidates: int = DEFAULT_TARGET_WEIGHT_INVERSION_MAX_CANDIDATES,
    target_weight_inversion_max_targets: int = DEFAULT_TARGET_WEIGHT_INVERSION_MAX_TARGETS,
    target_weight_inversion_max_deltas_per_target: int = DEFAULT_TARGET_WEIGHT_INVERSION_MAX_DELTAS_PER_TARGET,
) -> dict:
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    started_at = datetime.now()
    deadline = resolve_training_deadline(started_at, duration_hours)
    resolved_event_url = training_event_url(event_url)
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / f"training-supervisor-{run_id}.json"
    report_path = output_dir / f"training-supervisor-{run_id}.md"

    with get_connection() as conn:
        ensure_training_round_results_schema(conn)
        ensure_training_supervisor_best_schema(conn)
        selection = select_history(conn, scope=history_scope, as_of_issue=as_of_issue, regime_years=regime_years)
        universe = load_red_combination_universe(conn)

    worker_count = normalize_worker_count(workers)
    training_history = selection.dated_history
    as_of_issue_value = history_issue(training_history[-1])
    history_fingerprint_value = fingerprint_history(training_history)
    log(
        f"run_id={run_id} building static universe rows={len(universe)} workers={worker_count} "
        f"memory_budget_gb={memory_budget_gb}"
    )
    ranked_universe = build_ranked_universe(universe)
    matrix_cache_info = dict(getattr(ranked_universe, "cache_info", {}))
    log(
        "static_matrix_ready="
        f"backend={matrix_cache_info.get('backend', 'unknown')} "
        f"cache_hit={matrix_cache_info.get('cache_hit')} "
        f"rows={len(ranked_universe)} "
        f"elapsed={matrix_cache_info.get('build_seconds')}s"
    )
    prior_leaderboard = load_db_supervisor_candidates(
        as_of_issue=as_of_issue_value,
        history_fingerprint_value=history_fingerprint_value,
        train_window=train_window,
        train_mode=train_mode,
        eval_window=eval_window,
        top_n=top_n,
        universe_size=len(ranked_universe),
    )
    if not prior_leaderboard:
        prior_leaderboard = load_prior_supervisor_candidates(
            output_dir=output_dir,
            current_status_path=status_path,
            as_of_issue=as_of_issue_value,
            history_fingerprint_value=history_fingerprint_value,
            train_window=train_window,
            train_mode=train_mode,
            eval_window=eval_window,
            top_n=top_n,
            universe_size=len(ranked_universe),
        )
    if prior_leaderboard:
        log(
            "seeded_prior_best="
            f"top100={prior_leaderboard[0]['top_100_hits']} "
            f"top1000={prior_leaderboard[0]['top_1000_hits']} "
            f"top10000={prior_leaderboard[0]['top_10000_hits']} "
            f"run_key={prior_leaderboard[0]['run_key']}"
        )
    db_carryover_configs = load_db_supervisor_carryover_configs(
        current_as_of_issue=as_of_issue_value,
        current_history_fingerprint=history_fingerprint_value,
        train_window=train_window,
        train_mode=train_mode,
        eval_window=eval_window,
        top_n=top_n,
        universe_size=len(ranked_universe),
    )
    status_carryover_configs = load_prior_supervisor_carryover_configs(
        output_dir=output_dir,
        current_status_path=status_path,
        current_as_of_issue=as_of_issue_value,
        current_history_fingerprint=history_fingerprint_value,
        train_window=train_window,
        train_mode=train_mode,
        eval_window=eval_window,
        top_n=top_n,
        universe_size=len(ranked_universe),
    )
    carryover_configs = merge_config_candidates(db_carryover_configs, status_carryover_configs, limit=16)
    pool = create_worker_pool(worker_count, ranked_universe)

    carryover_summaries: list[dict] = []
    if carryover_configs:
        log(
            "seeded_carryover_configs="
            f"count={len(carryover_configs)} "
            f"hashes={bounded_unique_config_hashes(carryover_configs, limit=len(carryover_configs))}"
        )
        carryover_summaries = evaluate_configs(
            history=training_history,
            ranked_universe=ranked_universe,
            configs=carryover_configs,
            train_window=train_window,
            train_mode=train_mode,
            eval_window=eval_window,
            top_n=top_n,
            workers=worker_count,
            pool=pool,
            progress_interval=0,
            round_index=0,
        )
        attach_frozen_validation(
            carryover_summaries,
            validation_window=frozen_validation_window(eval_window),
            universe_size=len(ranked_universe),
        )
        prior_leaderboard = merge_leaderboard(prior_leaderboard, carryover_summaries, limit=32)
        if carryover_summaries:
            log(
                "seeded_carryover_best="
                f"top100={carryover_summaries[0]['top_100_hits']} "
                f"top1000={carryover_summaries[0]['top_1000_hits']} "
                f"top10000={carryover_summaries[0]['top_10000_hits']} "
                f"run_key={carryover_summaries[0]['run_key']}"
            )

    best_summary: dict | None = prior_leaderboard[0] if prior_leaderboard else None
    best_config = FrequencyRankerConfig(**best_summary["config"]) if best_summary else FrequencyRankerConfig()
    search_base_config = best_config
    leaderboard: list[dict] = prior_leaderboard
    rounds: list[dict] = []
    target_weight_inversion_configs: tuple[FrequencyRankerConfig, ...] = ()
    target_weight_inversion_latest: dict | None = None
    near_miss_inversion_configs: tuple[FrequencyRankerConfig, ...] = ()
    near_miss_inversion_latest: dict | None = None
    probability_focus_config: FrequencyRankerConfig | None = None
    probability_focus_hash = ""
    probability_focus_source = ""
    probability_focus_score: tuple = ()
    probability_focus_remaining = 0
    weight_kdj_thresholds = {
        "min_objective_delta": weight_kdj_min_objective_delta,
        "min_abs_offset": weight_kdj_min_abs_offset,
        "slope_window": weight_kdj_slope_window,
        "neutral_band": weight_kdj_neutral_band,
    }
    ridge_kdj_params = {
        "step": DEFAULT_RIDGE_KDJ_STEP,
        "ridge_alpha": ridge_kdj_alpha,
    }
    ridge_kdj_thresholds = {
        "min_confidence": ridge_kdj_min_confidence,
        "min_train_rows": ridge_kdj_min_train_rows,
        "min_validation_rows": ridge_kdj_min_validation_rows,
    }
    neural_kdj_params = {
        "step": DEFAULT_NEURAL_KDJ_STEP,
        "seed": neural_kdj_seed,
        "hidden_units": neural_kdj_hidden_units,
        "epochs": neural_kdj_epochs,
        "model": "numpy_mlp_kdj_offset_v0",
    }
    neural_kdj_thresholds = {
        "min_confidence": neural_kdj_min_confidence,
    }
    status = {
        "run_id": run_id,
        "started_at": started_at.isoformat(timespec="seconds"),
        "updated_at": started_at.isoformat(timespec="seconds"),
        "deadline": deadline.isoformat(timespec="seconds") if deadline else None,
        "run_mode": "continuous" if deadline is None else "timed",
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
        "legal_universe_size": len(universe),
        "ranked_universe_size": len(ranked_universe),
        "excluded_universe_count": max(0, len(universe) - len(ranked_universe)),
        "universe_size": len(ranked_universe),
        "matrix_backend": "NumPy 特征矩阵",
        "feature_matrix_cache": matrix_cache_info,
        "red5_rank_mode": "红5候选使用完整分数向量精排，不重复计算特征矩阵",
        "prefilter": {
            "mode": "light_prefilter",
            "description": "每轮先用最近100期每4期取1期做轻量预筛，正式指标仍来自完整精排",
            "latest": None,
            "completed_latest": None,
        },
        "weight_kdj_advisor": {
            "enabled": enable_weight_kdj_advisor,
            "signal_run_id": weight_kdj_run_id,
            "limit": weight_kdj_limit,
            "budget_share": weight_kdj_budget_share if enable_weight_kdj_advisor else 0.0,
            "thresholds": weight_kdj_thresholds,
            "latest": None,
        },
        "ridge_kdj_advisor": {
            "enabled": enable_ridge_kdj_advisor,
            "signal_run_id": weight_kdj_run_id,
            "limit": weight_kdj_limit,
            "budget_share": ridge_kdj_budget_share if enable_ridge_kdj_advisor else 0.0,
            "params": ridge_kdj_params,
            "thresholds": ridge_kdj_thresholds,
            "latest": None,
        },
        "neural_kdj_advisor": {
            "enabled": enable_neural_kdj_advisor,
            "signal_run_id": weight_kdj_run_id,
            "limit": weight_kdj_limit,
            "budget_share": neural_kdj_budget_share if enable_neural_kdj_advisor else 0.0,
            "params": neural_kdj_params,
            "thresholds": neural_kdj_thresholds,
            "latest": None,
        },
        "target_weight_inversion_advisor": {
            "enabled": enable_target_weight_inversion_advisor,
            "budget_share": target_weight_inversion_budget_share if enable_target_weight_inversion_advisor else 0.0,
            "max_candidates": max(0, target_weight_inversion_max_candidates),
            "max_targets": max(0, target_weight_inversion_max_targets),
            "max_deltas_per_target": max(1, target_weight_inversion_max_deltas_per_target),
            "latest": target_weight_inversion_latest,
        },
        "near_miss_inversion_advisor": {
            "enabled": enable_target_weight_inversion_advisor,
            "stagnation_threshold": NEAR_MISS_INVERSION_STAGNATION_THRESHOLD,
            "latest": near_miss_inversion_latest,
        },
        "probability_focus": {
            "enabled": True,
            "hold_rounds": PROBABILITY_FOCUS_HOLD_ROUNDS,
            "latest": None,
        },
        "carryover_seed": {
            "mode": "cross_history_config_replay",
            "config_count": len(carryover_configs),
            "config_hashes": bounded_unique_config_hashes(carryover_configs, limit=len(carryover_configs) or 1),
            "evaluated_config_count": len(carryover_summaries),
            "best": strip_target_results(carryover_summaries[0]) if carryover_summaries else None,
        },
        "qian_kun": qian_kun_distribution(selection.history),
        "next_candidates": None,
        "rounds": rounds,
        "best": strip_target_results(best_summary) if best_summary else None,
        "search_base": {
            "source": "initial_best",
            "changed": False,
            "previous_config_hash": "",
            "config_hash": config_hash(search_base_config),
            "config": config_dict(search_base_config),
        },
        "latest_progress": None,
        "status_path": str(status_path),
        "report_path": str(report_path),
    }

    def publish_progress(progress: dict) -> None:
        status["latest_progress"] = progress
        status["updated_at"] = progress["logged_at"]
        publish_status_snapshot(status_path, status, event_url=resolved_event_url, write_json=write_status_json)

    if best_summary:
        with get_connection() as conn:
            upsert_training_supervisor_best(
                conn,
                run_id=run_id,
                round_index=0,
                best_summary=best_summary,
                status=status,
            )
    publish_status_snapshot(status_path, status, event_url=resolved_event_url, write_json=write_status_json)

    try:
        round_index = 0
        while should_continue_training(round_index, deadline):
            stagnation_rounds = stagnation_round_count(rounds)
            phase, step, phase_stage = phase_for_round(round_index, stagnation_rounds=stagnation_rounds)
            min_search_base_distance = search_base_min_distance_for_phase(phase_stage)
            rank_homogeneity = rank_homogeneity_guardrail(rounds, stagnation_rounds=stagnation_rounds)
            rank_signature_cooldown_hashes = tuple(rank_homogeneity.get("signatures") or ()) if rank_homogeneity["active"] else ()
            stagnation_restart_budget = (
                min(max_configs_per_round, max(3, max_configs_per_round // 5))
                if rank_homogeneity["active"]
                else 0
            )
            near_miss_inversion_budget = (
                min(len(near_miss_inversion_configs), max(2, max_configs_per_round // 7))
                if enable_target_weight_inversion_advisor and stagnation_rounds >= NEAR_MISS_INVERSION_STAGNATION_THRESHOLD
                else 0
            )
            probability_focus_configs = (
                (probability_focus_config,)
                if probability_focus_config is not None and probability_focus_remaining > 0
                else ()
            )
            probability_focus_budget = len(probability_focus_configs)
            historical_summaries = merge_leaderboard(leaderboard, prior_leaderboard, limit=32)
            low_coverage_fields = low_coverage_fields_from_summaries(historical_summaries)
            elite_configs = tuple(FrequencyRankerConfig(**summary["config"]) for summary in leaderboard[:4])
            control_configs = control_experiment_configs(best_config)
            target_weight_inversion_guardrail = target_weight_inversion_budget_guardrail(
                target_weight_inversion_budget_share if enable_target_weight_inversion_advisor else 0.0,
                latest=target_weight_inversion_latest,
                stagnation_rounds=stagnation_rounds,
            )
            budgets = candidate_budget(
                max_configs_per_round,
                recency_canary_budget_share=DEFAULT_RECENCY_CANARY_BUDGET_SHARE,
                weight_kdj_budget_share=weight_kdj_budget_share if enable_weight_kdj_advisor else 0.0,
                ridge_kdj_budget_share=ridge_kdj_budget_share if enable_ridge_kdj_advisor else 0.0,
                neural_kdj_budget_share=neural_kdj_budget_share if enable_neural_kdj_advisor else 0.0,
                target_weight_inversion_budget_share=target_weight_inversion_guardrail["effective_share"],
                target_weight_inversion_available=len(target_weight_inversion_configs),
                target_weight_inversion_max_candidates=target_weight_inversion_max_candidates,
            )
            weight_kdj_budget = budgets.get("weight_kdj", 0)
            ridge_kdj_budget = budgets.get("ridge_kdj", 0)
            neural_kdj_budget = budgets.get("neural_kdj", 0)
            recency_canary_budget = budgets.get("recency_canary", 0)
            target_weight_inversion_budget = budgets.get("target_weight_inversion", 0)
            budgets["near_miss_inversion"] = near_miss_inversion_budget
            budgets["probability_focus"] = probability_focus_budget
            normal_config_budget = (
                max_configs_per_round
                - weight_kdj_budget
                - ridge_kdj_budget
                - neural_kdj_budget
                - recency_canary_budget
                - target_weight_inversion_budget
                - near_miss_inversion_budget
                - stagnation_restart_budget
                - probability_focus_budget
            )
            normal_config_budget = max(1, normal_config_budget)
            configs = tuple(
                generate_configs(
                    search_base_config,
                    phase=phase,
                    step=step,
                    max_configs=normal_config_budget,
                    elite_configs=elite_configs,
                    historical_summaries=historical_summaries,
                    low_coverage_fields=low_coverage_fields,
                    stagnation_rounds=stagnation_rounds,
                    round_index=round_index + 1,
                )
            )
            normal_configs = configs
            stagnation_restart_configs = stagnation_restart_candidate_configs(
                search_base_config,
                max_configs=stagnation_restart_budget,
                round_index=round_index + 1,
                stagnation_rounds=stagnation_rounds,
            )
            recency_canary_configs = recency_canary_candidate_configs(
                search_base_config,
                step=step,
                max_configs=recency_canary_budget,
            )
            kdj_signals: list[dict] = []
            weight_kdj_signals: list[dict] = []
            weight_kdj_configs: tuple[FrequencyRankerConfig, ...] = ()
            weight_kdj_advice: tuple[WeightKdjAdvice, ...] = ()
            ridge_kdj_signals: list[dict] = []
            ridge_kdj_configs: tuple[FrequencyRankerConfig, ...] = ()
            ridge_kdj_advice: tuple[RidgeKdjOffsetAdvice, ...] = ()
            neural_kdj_signals: list[dict] = []
            neural_kdj_configs: tuple[FrequencyRankerConfig, ...] = ()
            neural_kdj_advice: tuple[NeuralKdjOffsetAdvice, ...] = ()
            if enable_weight_kdj_advisor or enable_ridge_kdj_advisor or enable_neural_kdj_advisor:
                with get_connection() as conn:
                    kdj_signals = load_recent_training_weight_signals(
                        conn,
                        signal_run_id=weight_kdj_run_id,
                        as_of_issue=as_of_issue_value,
                        train_mode=train_mode,
                        train_window=train_window,
                        top_n=top_n,
                        limit=weight_kdj_limit,
                    )
            if enable_weight_kdj_advisor:
                weight_kdj_signals = kdj_signals
                weight_kdj_advice = weight_kdj_advice_from_signals(
                    weight_kdj_signals,
                    allowed_fields=ALL_FIELDS,
                    min_objective_delta=weight_kdj_min_objective_delta,
                    min_abs_offset=weight_kdj_min_abs_offset,
                    slope_window=weight_kdj_slope_window,
                    neutral_band=weight_kdj_neutral_band,
                )
                weight_kdj_configs = weight_kdj_advisor_candidate_configs(
                    search_base_config,
                    weight_kdj_signals,
                    max_configs=weight_kdj_budget,
                    min_objective_delta=weight_kdj_min_objective_delta,
                    min_abs_offset=weight_kdj_min_abs_offset,
                    slope_window=weight_kdj_slope_window,
                    neutral_band=weight_kdj_neutral_band,
                )
            if enable_ridge_kdj_advisor:
                ridge_kdj_signals = kdj_signals
                ridge_kdj_advice = numpy_ridge_kdj_offset_v0(
                    ridge_kdj_signals,
                    step=DEFAULT_RIDGE_KDJ_STEP,
                    ridge_alpha=ridge_kdj_alpha,
                    min_train_rows=ridge_kdj_min_train_rows,
                    min_validation_rows=ridge_kdj_min_validation_rows,
                )
                ridge_kdj_configs = ridge_kdj_advice_to_frequency_ranker_config_candidates(
                    search_base_config,
                    ridge_kdj_advice,
                    max_configs=ridge_kdj_budget,
                    min_confidence=ridge_kdj_min_confidence,
                )
            if enable_neural_kdj_advisor:
                neural_kdj_signals = kdj_signals
                neural_kdj_advice = numpy_neural_kdj_offset_v0(
                    neural_kdj_signals,
                    step=DEFAULT_NEURAL_KDJ_STEP,
                    seed=neural_kdj_seed,
                    hidden_units=neural_kdj_hidden_units,
                    epochs=neural_kdj_epochs,
                )
                neural_kdj_configs = neural_kdj_advice_to_frequency_ranker_config_candidates(
                    search_base_config,
                    neural_kdj_advice,
                    max_configs=neural_kdj_budget,
                    min_confidence=neural_kdj_min_confidence,
                )
            source_configs = {
                "normal": normal_configs,
                "recency_canary": recency_canary_configs,
                "weight_kdj": weight_kdj_configs,
                "ridge_kdj": ridge_kdj_configs,
                "neural_kdj": neural_kdj_configs,
                "target_weight_inversion": target_weight_inversion_configs,
                "near_miss_inversion": near_miss_inversion_configs,
                "stagnation_restart": stagnation_restart_configs,
                "probability_focus": probability_focus_configs,
            }
            if recency_canary_budget > 0:
                configs = merge_reserved_candidate_configs(
                    configs,
                    recency_canary_configs,
                    max_configs=max_configs_per_round
                    - weight_kdj_budget
                    - ridge_kdj_budget
                    - neural_kdj_budget
                    - target_weight_inversion_budget,
                    reserved_budget=recency_canary_budget,
                )
            if enable_weight_kdj_advisor:
                configs = merge_reserved_candidate_configs(
                    configs,
                    weight_kdj_configs,
                    max_configs=max_configs_per_round - ridge_kdj_budget - neural_kdj_budget - target_weight_inversion_budget,
                    reserved_budget=weight_kdj_budget,
                )
            if enable_ridge_kdj_advisor:
                configs = merge_reserved_candidate_configs(
                    configs,
                    ridge_kdj_configs,
                    max_configs=max_configs_per_round - neural_kdj_budget - target_weight_inversion_budget,
                    reserved_budget=ridge_kdj_budget,
                )
            if enable_neural_kdj_advisor:
                configs = merge_reserved_candidate_configs(
                    configs,
                    neural_kdj_configs,
                    max_configs=max_configs_per_round - target_weight_inversion_budget,
                    reserved_budget=neural_kdj_budget,
                )
            if enable_target_weight_inversion_advisor:
                configs = merge_reserved_candidate_configs(
                    configs,
                    target_weight_inversion_configs,
                    max_configs=max_configs_per_round - near_miss_inversion_budget - stagnation_restart_budget,
                    reserved_budget=target_weight_inversion_budget,
                )
            if near_miss_inversion_budget > 0:
                configs = merge_reserved_candidate_configs(
                    configs,
                    near_miss_inversion_configs,
                    max_configs=max_configs_per_round - stagnation_restart_budget,
                    reserved_budget=near_miss_inversion_budget,
                )
            if stagnation_restart_budget > 0:
                configs = merge_reserved_candidate_configs(
                    configs,
                    stagnation_restart_configs,
                    max_configs=max_configs_per_round,
                    reserved_budget=stagnation_restart_budget,
                )
            if probability_focus_budget > 0:
                configs = merge_reserved_candidate_configs(
                    configs,
                    probability_focus_configs,
                    max_configs=max_configs_per_round,
                    reserved_budget=probability_focus_budget,
                )
            generated_config_count = len(configs)
            keep_configs = (
                search_base_config,
                best_config,
                *elite_configs[:4],
                *probability_focus_configs,
                *(config for _label, config in control_configs),
            )
            refined_configs, prefilter_info = prefilter_configs(
                history=training_history,
                ranked_universe=ranked_universe,
                configs=configs,
                keep_configs=keep_configs,
                train_window=train_window,
                train_mode=train_mode,
                eval_window=eval_window,
                top_n=top_n,
                workers=worker_count,
                pool=pool,
                round_index=round_index + 1,
                diversity_quota=max(2, max_configs_per_round // 10),
            )
            prefilter_info["stagnation_rounds"] = stagnation_rounds
            prefilter_info["phase_stage"] = phase_stage
            prefilter_info["search_base_min_distance"] = min_search_base_distance
            prefilter_info["search_base_start"] = {
                "config_hash": config_hash(search_base_config),
                "config": config_dict(search_base_config),
            }
            prefilter_info["low_coverage_fields"] = list(low_coverage_fields)
            prefilter_info["candidate_budget"] = budgets
            prefilter_info["candidate_budget"]["stagnation_restart"] = stagnation_restart_budget
            prefilter_info["rank_homogeneity_guardrail"] = rank_homogeneity
            prefilter_info["target_weight_inversion_budget_guardrail"] = target_weight_inversion_guardrail
            prefilter_info["source_survival"] = candidate_source_survival(
                source_configs,
                refined_configs=refined_configs,
            )
            advisor_info = weight_kdj_advisor_metadata(
                weight_kdj_signals,
                weight_kdj_configs,
                budget=weight_kdj_budget,
                thresholds=weight_kdj_thresholds,
                advice=weight_kdj_advice,
            )
            ridge_advisor_info = ridge_kdj_advisor_metadata(
                ridge_kdj_signals,
                ridge_kdj_configs,
                enabled=enable_ridge_kdj_advisor,
                budget=ridge_kdj_budget,
                params=ridge_kdj_params,
                thresholds=ridge_kdj_thresholds,
                advice=ridge_kdj_advice,
            )
            neural_advisor_info = neural_kdj_advisor_metadata(
                neural_kdj_signals,
                neural_kdj_configs,
                enabled=enable_neural_kdj_advisor,
                budget=neural_kdj_budget,
                params=neural_kdj_params,
                thresholds=neural_kdj_thresholds,
                advice=neural_kdj_advice,
            )
            prefilter_info["weight_kdj_advisor"] = advisor_info
            prefilter_info["ridge_kdj_advisor"] = ridge_advisor_info
            prefilter_info["neural_kdj_advisor"] = neural_advisor_info
            prefilter_info["target_weight_inversion_advisor"] = target_weight_inversion_latest or target_weight_inversion_advisor_metadata(
                enabled=enable_target_weight_inversion_advisor,
                budget=target_weight_inversion_budget,
                configs=target_weight_inversion_configs[:target_weight_inversion_budget],
                max_targets=target_weight_inversion_max_targets,
                max_deltas_per_target=target_weight_inversion_max_deltas_per_target,
            )
            status["weight_kdj_advisor"]["latest"] = advisor_info
            status["ridge_kdj_advisor"]["latest"] = ridge_advisor_info
            status["neural_kdj_advisor"]["latest"] = neural_advisor_info
            status["target_weight_inversion_advisor"]["latest"] = prefilter_info["target_weight_inversion_advisor"]
            status["prefilter"]["latest"] = prefilter_info
            log(
                f"round={round_index + 1} phase={phase} step={step} "
                f"configs={generated_config_count}->{len(refined_configs)} "
                f"stagnation={stagnation_rounds} "
                f"prefilter_targets={prefilter_info['target_count']} "
                f"prefilter_workers={prefilter_info.get('target_worker_count', 1)} "
                f"prefilter_elapsed={prefilter_info['elapsed_seconds']}s "
                f"search_base={config_dict(search_base_config)}"
            )
            summaries = evaluate_configs(
                history=training_history,
                ranked_universe=ranked_universe,
                configs=refined_configs,
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
            validation_window = frozen_validation_window(eval_window)
            attach_frozen_validation(
                summaries,
                validation_window=validation_window,
                universe_size=len(ranked_universe),
            )
            attach_baseline_overlap(
                summaries,
                control_configs,
                universe_size=len(ranked_universe),
            )
            summaries.sort(key=sort_key, reverse=True)
            control_summaries = control_experiment_summaries(summaries, control_configs)
            round_best = summaries[0]
            prior_best_summary = best_summary
            raw_improved = prior_best_summary is None or sort_key(round_best) > sort_key(prior_best_summary)
            promotion_gate = frozen_validation_promotion_gate(round_best, prior_best_summary)
            improved = bool(raw_improved and promotion_gate["passed"])
            eval_slice_overfit = eval_slice_overfit_guardrail(
                summaries=summaries,
                source_configs=source_configs,
                round_best=round_best,
                prior_best_summary=prior_best_summary,
                rank_homogeneity=rank_homogeneity,
                promotion_gate=promotion_gate,
                stagnation_rounds=stagnation_rounds,
            )
            round_best_search_gate = stale_round_best_search_base_gate(
                stagnation_rounds=stagnation_rounds,
                rank_homogeneity=rank_homogeneity,
                promotion_gate=promotion_gate,
                eval_slice_overfit=eval_slice_overfit,
            )
            require_frozen_primary_navigation = bool(
                round_best_search_gate.get("require_frozen_primary_challenger")
            )
            exploration_champion, exploration_champion_info = select_stagnation_exploration_champion(
                summaries=summaries,
                source_configs=source_configs,
                round_best=round_best,
                stagnation_rounds=stagnation_rounds,
            )
            restart_champion, restart_champion_info = select_rank_homogeneity_restart_champion(
                summaries=summaries,
                source_configs=source_configs,
                round_best=round_best,
                prior_best_summary=prior_best_summary,
                rank_homogeneity=rank_homogeneity,
            )
            experimental_navigation_candidate, experimental_navigation_info = select_experimental_navigation_candidate(
                exploration_champion=exploration_champion,
                exploration_champion_info=exploration_champion_info,
                restart_champion=restart_champion,
                restart_champion_info=restart_champion_info,
            )
            probability_champion, probability_champion_info = select_probability_calibration_champion(
                summaries=summaries,
                source_configs=source_configs,
                round_best=round_best,
                prior_best_summary=prior_best_summary,
                stagnation_rounds=stagnation_rounds,
                force_primary_gate=bool(eval_slice_overfit["force_primary_gate"]),
            )
            source_frontier_champion, source_frontier_champion_info = select_source_frontier_champion(
                summaries=summaries,
                source_configs=source_configs,
                round_best=round_best,
                prior_best_summary=prior_best_summary,
                stagnation_rounds=stagnation_rounds,
            )
            evaluated_probability_focus_summary = None
            if probability_focus_hash:
                for summary in summaries:
                    if summary_config_hash(summary) == probability_focus_hash:
                        evaluated_probability_focus_summary = summary
                        break
            probability_focus_had_state = bool(
                probability_focus_hash or probability_focus_config is not None or probability_focus_remaining > 0
            )
            probability_focus_info = {
                "active": False,
                "hold_rounds": PROBABILITY_FOCUS_HOLD_ROUNDS,
                "remaining_rounds": max(0, probability_focus_remaining),
                "source": probability_focus_source,
                "config_hash": probability_focus_hash,
                "score": list(probability_focus_score) if probability_focus_score else None,
                "refreshed": False,
                "reason": "inactive",
            }
            probability_focus_decision_summary = None
            if improved:
                probability_focus_config = None
                probability_focus_hash = ""
                probability_focus_source = ""
                probability_focus_score = ()
                probability_focus_remaining = 0
                probability_focus_info["reason"] = "cleared_on_new_best" if probability_focus_had_state else "inactive"
            elif probability_champion is not None:
                champion_config = summary_config(probability_champion)
                champion_hash = summary_config_hash(probability_champion) or ""
                champion_score = probability_calibration_score(probability_champion)
                should_refresh_focus = should_refresh_probability_focus(
                    champion_config=champion_config,
                    champion_hash=champion_hash,
                    champion_score=champion_score,
                    probability_focus_hash=probability_focus_hash,
                    probability_focus_score=probability_focus_score,
                )
                if should_refresh_focus and champion_config is not None:
                    probability_focus_config = champion_config
                    probability_focus_hash = champion_hash
                    probability_focus_source = str(probability_champion_info.get("source") or "")
                    probability_focus_score = champion_score
                    probability_focus_remaining = PROBABILITY_FOCUS_HOLD_ROUNDS
                    probability_focus_decision_summary = probability_champion
                    probability_focus_info.update(
                        {
                            "active": True,
                            "remaining_rounds": probability_focus_remaining,
                            "source": probability_focus_source,
                            "config_hash": probability_focus_hash,
                            "score": list(probability_focus_score),
                            "refreshed": True,
                            "reason": "refreshed_from_probability_champion",
                        }
                    )
                elif probability_focus_config is not None and probability_focus_remaining > 0:
                    probability_focus_remaining = max(0, probability_focus_remaining - 1)
                    probability_focus_decision_summary = evaluated_probability_focus_summary
                    probability_focus_info.update(
                        {
                            "active": evaluated_probability_focus_summary is not None and probability_focus_remaining > 0,
                            "remaining_rounds": probability_focus_remaining,
                            "source": probability_focus_source,
                            "config_hash": probability_focus_hash,
                            "score": list(probability_focus_score) if probability_focus_score else None,
                            "reason": "kept_stronger_existing_focus",
                        }
                    )
            elif probability_focus_config is not None and probability_focus_remaining > 0:
                probability_focus_remaining = max(0, probability_focus_remaining - 1)
                probability_focus_decision_summary = evaluated_probability_focus_summary
                probability_focus_info.update(
                    {
                        "active": evaluated_probability_focus_summary is not None and probability_focus_remaining > 0,
                        "remaining_rounds": probability_focus_remaining,
                        "source": probability_focus_source,
                        "config_hash": probability_focus_hash,
                        "score": list(probability_focus_score) if probability_focus_score else None,
                        "reason": "held_previous_probability_focus",
                    }
                )
            if probability_focus_remaining <= 0 and probability_focus_had_state:
                probability_focus_reason = probability_focus_info.get("reason")
                probability_focus_decision_summary = None
                probability_focus_config = None
                probability_focus_hash = ""
                probability_focus_source = ""
                probability_focus_score = ()
                probability_focus_remaining = 0
                probability_focus_info.update(
                    {
                        "active": False,
                        "remaining_rounds": 0,
                        "source": "",
                        "config_hash": "",
                        "score": None,
                        "reason": "cleared_on_new_best"
                        if probability_focus_reason == "cleared_on_new_best"
                        else "expired",
                    }
                )
            decision_round_best, decision_round_best_info = select_decision_round_best(
                round_best=round_best,
                prior_best_summary=prior_best_summary,
                improved=improved,
                probability_focus_decision_summary=probability_focus_decision_summary,
                probability_champion=probability_champion,
                source_frontier_champion=source_frontier_champion,
                restart_champion=restart_champion,
                exploration_champion=exploration_champion,
                require_frozen_primary_lift=require_frozen_primary_navigation,
            )
            inversion_anchor, challenger_summary, inversion_anchor_info = select_target_weight_inversion_anchor(
                summaries=summaries,
                prior_best_summary=prior_best_summary,
                round_best=decision_round_best,
                improved=improved,
                require_frozen_primary_lift=require_frozen_primary_navigation,
                frozen_primary_lift_baseline=prior_best_summary,
            )
            prefilter_info["frozen_validation_window"] = validation_window
            prefilter_info["control_experiments"] = control_summaries
            prefilter_info["promotion_gate"] = promotion_gate
            prefilter_info["eval_slice_overfit_guardrail"] = eval_slice_overfit
            prefilter_info["stale_round_best_search_base_gate"] = round_best_search_gate
            prefilter_info["raw_improved"] = raw_improved
            prefilter_info["round_best_rank_movement_vs_incumbent"] = target_rank_movement(round_best, prior_best_summary)
            prefilter_info["round_best_rank_signature_hash"] = rank_signature_hash(round_best)
            prefilter_info["round_best_probability_calibration"] = round_best.get("probability_calibration")
            prefilter_info["exploration_champion"] = exploration_champion_info
            prefilter_info["rank_homogeneity_restart_champion"] = restart_champion_info
            prefilter_info["experimental_navigation_candidate"] = experimental_navigation_info
            prefilter_info["probability_calibration_champion"] = probability_champion_info
            prefilter_info["probability_focus"] = probability_focus_info
            prefilter_info["decision_round_best"] = decision_round_best_info
            status["probability_focus"]["latest"] = probability_focus_info
            prefilter_info["source_survival"] = candidate_source_survival(
                source_configs,
                refined_configs=refined_configs,
                full_eval_top_results=summaries[: min(5, len(summaries))],
                round_best=round_best,
            )
            prefilter_info["source_frontier"] = source_frontier_diagnostics(
                summaries=summaries,
                source_configs=source_configs,
                prior_best_summary=prior_best_summary,
                round_best=round_best,
            )
            prefilter_info["source_frontier_champion"] = source_frontier_champion_info
            prefilter_info["round_best_replays_incumbent"] = inversion_anchor_info["round_best_replays_incumbent"]
            prefilter_info["challenger_best"] = strip_target_results(challenger_summary) if challenger_summary else None
            prefilter_info["challenger_probability_calibration"] = (
                challenger_summary.get("probability_calibration")
                if isinstance(challenger_summary, dict)
                else None
            )
            prefilter_info["target_weight_inversion_anchor"] = inversion_anchor_info
            inversion_rows: list[dict] = []
            inversion_aggregate: dict = {}
            if enable_target_weight_inversion_advisor:
                inversion_rows, inversion_aggregate, target_weight_inversion_configs, target_weight_inversion_latest = target_weight_inversion_advisor(
                    history=training_history,
                    ranked_universe=ranked_universe,
                    best_summary=inversion_anchor,
                    train_window=train_window,
                    train_mode=train_mode,
                    top_n=top_n,
                    max_candidates=target_weight_inversion_max_candidates,
                    max_targets=target_weight_inversion_max_targets,
                    max_deltas_per_target=target_weight_inversion_max_deltas_per_target,
                    budget=max(0, target_weight_inversion_max_candidates),
                    control_experiments=control_summaries,
                    frozen_validation_window_value=validation_window,
                )
            else:
                target_weight_inversion_configs = ()
                target_weight_inversion_latest = target_weight_inversion_advisor_metadata(
                    enabled=False,
                    budget=0,
                    max_targets=target_weight_inversion_max_targets,
                    max_deltas_per_target=target_weight_inversion_max_deltas_per_target,
                )
            target_weight_inversion_latest = {
                **target_weight_inversion_latest,
                "anchor": inversion_anchor_info,
            }
            prefilter_info["target_weight_inversion_advisor"] = target_weight_inversion_latest
            status["target_weight_inversion_advisor"]["latest"] = target_weight_inversion_latest
            near_miss_inversion_configs, near_miss_inversion_latest = near_miss_inversion_advisor(
                history=training_history,
                ranked_universe=ranked_universe,
                best_summary=decision_round_best,
                train_window=train_window,
                train_mode=train_mode,
                enabled=enable_target_weight_inversion_advisor
                and stagnation_rounds >= NEAR_MISS_INVERSION_STAGNATION_THRESHOLD,
                max_configs=max(0, target_weight_inversion_max_candidates),
                max_delta_candidates=target_weight_inversion_max_deltas_per_target,
            )
            prefilter_info["near_miss_inversion_advisor"] = near_miss_inversion_latest
            status["near_miss_inversion_advisor"]["latest"] = near_miss_inversion_latest
            leaderboard = merge_leaderboard(leaderboard, summaries[: min(8, len(summaries))])
            if probability_focus_info["active"] and probability_focus_decision_summary is not None:
                focus_recent_search_base_hashes = (
                    recent_search_base_hashes(rounds, search_base_config)
                    if rank_homogeneity["active"]
                    else ()
                )
                next_search_base_config, search_base_info = select_probability_focus_search_base(
                    current_base=search_base_config,
                    focus_summary=probability_focus_decision_summary,
                    focus_info=probability_focus_info,
                    excluded_rank_signature_hashes=rank_signature_cooldown_hashes,
                    recent_search_base_hashes=focus_recent_search_base_hashes,
                    min_config_distance=min_search_base_distance if rank_homogeneity["active"] else 0.0,
                    require_frozen_primary_lift=require_frozen_primary_navigation,
                    frozen_primary_lift_baseline=prior_best_summary,
                )
                if next_search_base_config is None:
                    next_search_base_config, search_base_info = select_next_search_base(
                        current_base=search_base_config,
                        summaries=summaries,
                        round_best=decision_round_best,
                        improved=improved,
                        exploration_navigation_candidate=experimental_navigation_candidate,
                        exploration_navigation_source=str(experimental_navigation_info.get("source") or ""),
                        exploration_navigation_reason=str(experimental_navigation_info.get("reason") or ""),
                        recent_search_base_hashes=recent_search_base_hashes(rounds, search_base_config),
                        excluded_rank_signature_hashes=rank_signature_cooldown_hashes,
                        min_config_distance=min_search_base_distance,
                        allow_unpromoted_round_best=bool(
                            round_best_search_gate["allow_unpromoted_round_best"]
                        ),
                        round_best_skip_reason=str(round_best_search_gate["reason"]),
                        require_frozen_primary_lift=require_frozen_primary_navigation,
                        frozen_primary_lift_baseline=prior_best_summary,
                    )
            else:
                next_search_base_config, search_base_info = select_next_search_base(
                    current_base=search_base_config,
                    summaries=summaries,
                    round_best=decision_round_best,
                    improved=improved,
                    exploration_navigation_candidate=experimental_navigation_candidate,
                    exploration_navigation_source=str(experimental_navigation_info.get("source") or ""),
                    exploration_navigation_reason=str(experimental_navigation_info.get("reason") or ""),
                    recent_search_base_hashes=recent_search_base_hashes(rounds, search_base_config),
                    excluded_rank_signature_hashes=rank_signature_cooldown_hashes,
                    min_config_distance=min_search_base_distance,
                    allow_unpromoted_round_best=bool(round_best_search_gate["allow_unpromoted_round_best"]),
                    round_best_skip_reason=str(round_best_search_gate["reason"]),
                    require_frozen_primary_lift=require_frozen_primary_navigation,
                    frozen_primary_lift_baseline=prior_best_summary,
                )
            search_base_info["phase"] = phase
            search_base_info["phase_stage"] = phase_stage
            search_base_info["step"] = step
            prefilter_info["search_base"] = search_base_info
            log(
                f"round={round_index + 1} target_weight_inversion_anchor="
                f"{inversion_anchor_info['source']} "
                f"config_hash={inversion_anchor_info.get('config_hash', '')} "
                f"round_best_replays_incumbent={inversion_anchor_info['round_best_replays_incumbent']}"
            )
            if rank_homogeneity["active"]:
                log(
                    f"round={round_index + 1} rank_homogeneity_restart="
                    f"unique={rank_homogeneity['unique_signature_count']}/{rank_homogeneity['observed']} "
                    f"budget={stagnation_restart_budget}"
                )
            if eval_slice_overfit["active"]:
                log(
                    f"round={round_index + 1} eval_slice_overfit_guardrail="
                    f"{eval_slice_overfit['reason']} "
                    f"eval_primary={eval_slice_overfit['round_best_eval_primary_score']} "
                    f"frozen_primary={eval_slice_overfit['round_best_frozen_primary_score']} "
                    f"suspicious={eval_slice_overfit['suspicious_candidate_count']}"
                )
            if exploration_champion_info["active"]:
                log(
                    f"round={round_index + 1} exploration_champion="
                    f"{exploration_champion_info['source']} "
                    f"top_rank={exploration_champion_info['top_rank']} "
                    f"config_hash={exploration_champion_info['config_hash']}"
                )
            if restart_champion_info["active"]:
                log(
                    f"round={round_index + 1} rank_homogeneity_restart_champion="
                    f"rank={restart_champion_info['full_eval_rank']} "
                    f"changed_targets={restart_champion_info['changed_target_count']} "
                    f"config_hash={restart_champion_info['config_hash']}"
                )
            if probability_champion_info["active"]:
                log(
                    f"round={round_index + 1} probability_calibration_champion="
                    f"{probability_champion_info['source']} "
                    f"rank={probability_champion_info['full_eval_rank']} "
                    f"changed_targets={probability_champion_info['changed_target_count']} "
                    f"config_hash={probability_champion_info['config_hash']}"
                )
            if source_frontier_champion_info["active"]:
                log(
                    f"round={round_index + 1} source_frontier_champion="
                    f"{source_frontier_champion_info['source']} "
                    f"rank={source_frontier_champion_info['full_eval_rank']} "
                    f"changed_targets={source_frontier_champion_info['changed_target_count']} "
                    f"config_hash={source_frontier_champion_info['config_hash']}"
                )
            if probability_focus_info["active"]:
                log(
                    f"round={round_index + 1} probability_focus="
                    f"{probability_focus_info['reason']} "
                    f"source={probability_focus_info['source']} "
                    f"remaining={probability_focus_info['remaining_rounds']} "
                    f"config_hash={probability_focus_info['config_hash']}"
                )
            if near_miss_inversion_latest["candidate_count"]:
                band_summary = ",".join(
                    f"{band['cutoff']}:{band['target_count']}"
                    for band in near_miss_inversion_latest["bands"]
                )
                log(
                    f"round={round_index + 1} near_miss_inversion="
                    f"candidates={near_miss_inversion_latest['candidate_count']} "
                    f"bands={band_summary}"
                )
            log(
                f"round={round_index + 1} search_base_next="
                f"{search_base_info['source']} "
                f"changed={search_base_info['changed']} "
                f"config_hash={search_base_info['config_hash']}"
            )
            if improved:
                best_summary = round_best
                best_config = FrequencyRankerConfig(**round_best["config"])
                log(f"round={round_index + 1} retained_new_best={round_best}")
            else:
                log(f"round={round_index + 1} no_improvement best_top10000={best_summary['top_10000_hits'] if best_summary else 'n/a'}")
            search_base_config = next_search_base_config

            round_record = {
                "round": round_index + 1,
                "phase": phase,
                "step": step,
                "generated_config_count": generated_config_count,
                "config_count": len(refined_configs),
                "prefilter": prefilter_info,
                "improved": improved,
                "best": round_best,
                "top_results": summaries[: min(5, len(summaries))],
                "control_experiments": control_summaries,
            }
            status["updated_at"] = datetime.now().isoformat(timespec="seconds")
            status["best"] = strip_target_results(best_summary) if best_summary else None
            status["search_base"] = search_base_info
            status["prefilter"]["completed_latest"] = prefilter_info
            with get_connection() as conn:
                ensure_training_round_results_schema(conn)
                upsert_training_round_result(conn, run_id=run_id, round_info=round_record, status=status)
                if best_summary:
                    upsert_training_supervisor_best(
                        conn,
                        run_id=run_id,
                        round_index=round_index + 1,
                        best_summary=best_summary,
                        status=status,
                    )
                if enable_target_weight_inversion_advisor and inversion_rows:
                    ensure_training_target_weight_inversions_schema(conn)
                    for inversion in inversion_rows:
                        upsert_training_target_weight_inversion(
                            conn,
                            {
                                **inversion,
                                "run_id": run_id,
                                "round_index": round_index + 1,
                                "aggregate": inversion_aggregate,
                                "prefilter": target_weight_inversion_latest or {},
                            },
                        )
                if best_summary:
                    try:
                        status["next_candidates"] = refresh_training_next_candidates_current(
                            conn,
                            run_id=run_id,
                            top_n=top_n,
                            ranked_universe=ranked_universe,
                        )
                    except Exception as exc:  # pragma: no cover - candidate refresh must not stop training.
                        status["next_candidates"] = {"status": "failed", "error": str(exc)}
                        log(f"next_candidates_warning round={round_index + 1} error={exc}")
            rounds.append(compact_round_info(round_record))
            publish_status_snapshot(status_path, status, event_url=resolved_event_url, write_json=write_status_json)
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
        status["best"] = strip_target_results(best_summary) if best_summary else None
        publish_status_snapshot(status_path, status, event_url=resolved_event_url, write_json=write_status_json)
        write_report(report_path, status)
        log(f"finished status={status['status']} status_path={status_path} report_path={report_path}")

    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-hours", type=float, default=0.0, help="Training duration. Use 0 or a negative value to run continuously until stopped.")
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
    parser.add_argument("--write-status-json", action="store_true", help="Write a compact legacy status JSON snapshot.")
    parser.add_argument("--enable-weight-kdj-advisor", action="store_true", help="Use stored weight KDJ signals as advisor-only candidate proposals.")
    parser.add_argument("--enable-ridge-kdj-advisor", action="store_true", help="Use stored weight KDJ signals for advisor-only Ridge offset proposals.")
    parser.add_argument("--enable-neural-kdj-advisor", action="store_true", help="Use stored weight KDJ signals for advisor-only NumPy MLP offset proposals.")
    parser.add_argument("--disable-target-weight-inversion-advisor", action="store_true", help="Disable target-results inversion proposals for the next round.")
    parser.add_argument("--weight-kdj-run-id", help="Optional training_weight_signals signal_run_id to read.")
    parser.add_argument("--weight-kdj-limit", type=int, default=1000, help="Recent signal points per weight for advisor context.")
    parser.add_argument("--weight-kdj-budget-share", type=float, default=DEFAULT_WEIGHT_KDJ_BUDGET_SHARE, help="Candidate budget share reserved for KDJ advisor proposals when enabled.")
    parser.add_argument("--weight-kdj-min-objective-delta", type=float, default=DEFAULT_WEIGHT_KDJ_MIN_OBJECTIVE_DELTA)
    parser.add_argument("--weight-kdj-min-abs-offset", type=float, default=DEFAULT_WEIGHT_KDJ_MIN_ABS_OFFSET)
    parser.add_argument("--weight-kdj-slope-window", type=int, default=DEFAULT_WEIGHT_KDJ_SLOPE_WINDOW)
    parser.add_argument("--weight-kdj-neutral-band", type=float, default=DEFAULT_WEIGHT_KDJ_NEUTRAL_BAND)
    parser.add_argument("--ridge-kdj-budget-share", type=float, default=DEFAULT_RIDGE_KDJ_BUDGET_SHARE, help="Candidate budget share reserved for Ridge KDJ advisor proposals when enabled.")
    parser.add_argument("--ridge-kdj-alpha", type=float, default=DEFAULT_RIDGE_KDJ_ALPHA)
    parser.add_argument("--ridge-kdj-min-confidence", type=float, default=DEFAULT_RIDGE_KDJ_MIN_CONFIDENCE)
    parser.add_argument("--ridge-kdj-min-train-rows", type=int, default=DEFAULT_RIDGE_KDJ_MIN_TRAIN_ROWS)
    parser.add_argument("--ridge-kdj-min-validation-rows", type=int, default=DEFAULT_RIDGE_KDJ_MIN_VALIDATION_ROWS)
    parser.add_argument("--neural-kdj-budget-share", type=float, default=DEFAULT_NEURAL_KDJ_BUDGET_SHARE, help="Candidate budget share reserved for Neural KDJ advisor proposals when enabled.")
    parser.add_argument("--neural-kdj-min-confidence", type=float, default=DEFAULT_NEURAL_KDJ_MIN_CONFIDENCE)
    parser.add_argument("--neural-kdj-seed", type=int, default=DEFAULT_NEURAL_KDJ_SEED)
    parser.add_argument("--neural-kdj-hidden-units", type=int, default=DEFAULT_NEURAL_KDJ_HIDDEN_UNITS)
    parser.add_argument("--neural-kdj-epochs", type=int, default=DEFAULT_NEURAL_KDJ_EPOCHS)
    parser.add_argument("--target-weight-inversion-budget-share", type=float, default=DEFAULT_TARGET_WEIGHT_INVERSION_BUDGET_SHARE)
    parser.add_argument("--target-weight-inversion-max-candidates", type=int, default=DEFAULT_TARGET_WEIGHT_INVERSION_MAX_CANDIDATES)
    parser.add_argument("--target-weight-inversion-max-targets", type=int, default=DEFAULT_TARGET_WEIGHT_INVERSION_MAX_TARGETS)
    parser.add_argument("--target-weight-inversion-max-deltas-per-target", type=int, default=DEFAULT_TARGET_WEIGHT_INVERSION_MAX_DELTAS_PER_TARGET)
    parser.add_argument("--heavy-job-lock-timeout-seconds", type=float, default=0.0)
    parser.add_argument("--cpu-threads", type=int, default=1)
    args = parser.parse_args()
    apply_cpu_thread_env_defaults(args.cpu_threads)
    with heavy_job_lock(
        owner="training-supervisor",
        timeout_seconds=args.heavy_job_lock_timeout_seconds,
        context={
            "duration_hours": args.duration_hours,
            "train_window": args.train_window,
            "eval_window": args.eval_window,
            "top_n": args.top_n,
            "enable_weight_kdj_advisor": args.enable_weight_kdj_advisor,
            "enable_ridge_kdj_advisor": args.enable_ridge_kdj_advisor,
            "enable_neural_kdj_advisor": args.enable_neural_kdj_advisor,
            "enable_target_weight_inversion_advisor": not args.disable_target_weight_inversion_advisor,
            "target_weight_inversion_max_targets": args.target_weight_inversion_max_targets,
            "target_weight_inversion_max_deltas_per_target": args.target_weight_inversion_max_deltas_per_target,
        },
    ) as lock:
        result = run_supervisor(
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
            write_status_json=args.write_status_json,
            enable_weight_kdj_advisor=args.enable_weight_kdj_advisor,
            enable_ridge_kdj_advisor=args.enable_ridge_kdj_advisor,
            enable_neural_kdj_advisor=args.enable_neural_kdj_advisor,
            enable_target_weight_inversion_advisor=not args.disable_target_weight_inversion_advisor,
            weight_kdj_run_id=args.weight_kdj_run_id,
            weight_kdj_limit=args.weight_kdj_limit,
            weight_kdj_budget_share=args.weight_kdj_budget_share,
            weight_kdj_min_objective_delta=args.weight_kdj_min_objective_delta,
            weight_kdj_min_abs_offset=args.weight_kdj_min_abs_offset,
            weight_kdj_slope_window=args.weight_kdj_slope_window,
            weight_kdj_neutral_band=args.weight_kdj_neutral_band,
            ridge_kdj_budget_share=args.ridge_kdj_budget_share,
            ridge_kdj_alpha=args.ridge_kdj_alpha,
            ridge_kdj_min_confidence=args.ridge_kdj_min_confidence,
            ridge_kdj_min_train_rows=args.ridge_kdj_min_train_rows,
            ridge_kdj_min_validation_rows=args.ridge_kdj_min_validation_rows,
            neural_kdj_budget_share=args.neural_kdj_budget_share,
            neural_kdj_min_confidence=args.neural_kdj_min_confidence,
            neural_kdj_seed=args.neural_kdj_seed,
            neural_kdj_hidden_units=args.neural_kdj_hidden_units,
            neural_kdj_epochs=args.neural_kdj_epochs,
            target_weight_inversion_budget_share=args.target_weight_inversion_budget_share,
            target_weight_inversion_max_candidates=args.target_weight_inversion_max_candidates,
            target_weight_inversion_max_targets=args.target_weight_inversion_max_targets,
            target_weight_inversion_max_deltas_per_target=args.target_weight_inversion_max_deltas_per_target,
        )
        lock.heartbeat(status="completed", context={"run_id": result.get("run_id"), "rounds": result.get("rounds")})
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
