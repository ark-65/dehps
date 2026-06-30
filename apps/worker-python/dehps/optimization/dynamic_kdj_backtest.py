from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from statistics import mean, median
from typing import Iterable, Literal

from dehps.models.frequency_ranker import FrequencyRankerConfig, HistoryDraw, history_draw_date, history_issue, history_numbers
from dehps.optimization.walk_forward import (
    CONFIG_WEIGHT_FIELDS,
    TargetRank,
    config_hash,
    fingerprint_history,
    rank_target_grid_with_red5,
)
from dehps.optimization.weight_kdj import WeightKdjAdvice, weight_kdj_advice_from_signals
from scripts.run_training_supervisor import (
    clamp_config,
    config_dict,
    summarize_target_ranks,
)


TrainMode = Literal["expanding", "rolling"]
DYNAMIC_CONFIG_HASH = "dynamic-kdj-per-target"
DEFAULT_KDJ_STRENGTH_SWEEP = (0.0, 0.25, 0.5, 1.0)
DEFAULT_RETENTION_BANDS = (100, 1000, 10000, 50000)
KDJ_LAYER_CONCENTRATION_WARNING_THRESHOLD = 0.65
STATIC_KDJ_ADVISOR_SKIP_REASON = (
    "skipped: a single static KDJ advisor candidate built with final as-of signals would leak eval-window outcomes; "
    "fair frozen comparison is static base vs per-target issue<T dynamic KDJ"
)


@dataclass(frozen=True)
class DynamicKdjThresholds:
    min_objective_delta: float = 0.0
    min_abs_offset: float = 0.005
    slope_window: int = 3
    neutral_band: float = 5.0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "min_objective_delta": self.min_objective_delta,
            "min_abs_offset": self.min_abs_offset,
            "slope_window": self.slope_window,
            "neutral_band": self.neutral_band,
        }


@dataclass(frozen=True)
class DynamicKdjAcceptanceConfig:
    min_eval_window_for_pass: int = 50
    max_median_changed_weights: int = 5
    max_max_changed_weights: int = 8
    max_abs_offset: float = 0.06

    def as_dict(self) -> dict[str, float | int]:
        return {
            "min_eval_window_for_pass": self.min_eval_window_for_pass,
            "max_median_changed_weights": self.max_median_changed_weights,
            "max_max_changed_weights": self.max_max_changed_weights,
            "max_abs_offset": self.max_abs_offset,
        }


@dataclass(frozen=True)
class DynamicKdjConfigResult:
    target_issue: str
    signal_cutoff_issue: str
    offset_scale: float
    config: FrequencyRankerConfig
    config_hash: str
    eligible_signal_count: int
    excluded_signal_count: int
    latest_signal_issue: str | None
    leakage_passed: bool
    applied_offsets: dict[str, float]
    advice: tuple[WeightKdjAdvice, ...]

    @property
    def changed_weight_count(self) -> int:
        return len(self.applied_offsets)

    @property
    def max_abs_offset(self) -> float:
        return max((abs(value) for value in self.applied_offsets.values()), default=0.0)

    @property
    def median_abs_offset(self) -> float:
        values = sorted(abs(value) for value in self.applied_offsets.values())
        return float(median(values)) if values else 0.0

    def as_dict(self) -> dict:
        return {
            "target_issue": self.target_issue,
            "signal_cutoff_issue": self.signal_cutoff_issue,
            "offset_scale": round(self.offset_scale, 8),
            "config_hash": self.config_hash,
            "eligible_signal_count": self.eligible_signal_count,
            "excluded_signal_count": self.excluded_signal_count,
            "latest_signal_issue": self.latest_signal_issue,
            "leakage_passed": self.leakage_passed,
            "changed_weight_count": self.changed_weight_count,
            "max_abs_offset": round(self.max_abs_offset, 8),
            "median_abs_offset": round(self.median_abs_offset, 8),
            "applied_offsets": {field: round(value, 8) for field, value in sorted(self.applied_offsets.items())},
            "advice": [item.as_dict() for item in self.advice],
        }


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


def target_indexes(*, history_len: int, train_window: int, eval_window: int) -> range:
    if train_window < 1:
        raise ValueError("train_window must be at least 1")
    if eval_window < 1:
        raise ValueError("eval_window must be at least 1")
    if history_len <= train_window:
        raise ValueError("history must contain more rows than train_window")
    return range(max(train_window, history_len - eval_window), history_len)


def _signal_issue(signal: dict) -> str:
    return str(signal.get("issue") or "")


def _normalize_strength(value: float) -> float:
    number = float(value)
    if not isfinite(number) or number < 0:
        raise ValueError("KDJ strength values must be finite non-negative numbers")
    return round(number, 8)


def normalize_strength_sweep(values: Iterable[float] | None = None) -> tuple[float, ...]:
    raw_values = tuple(DEFAULT_KDJ_STRENGTH_SWEEP if values is None else values)
    strengths = {_normalize_strength(value) for value in raw_values}
    strengths.add(0.0)
    strengths.add(1.0)
    return tuple(sorted(strengths))


def normalize_retention_bands(values: Iterable[int] | None = None) -> tuple[int, ...]:
    raw_values = tuple(DEFAULT_RETENTION_BANDS if values is None else values)
    bands: set[int] = set()
    for value in raw_values:
        band = int(value)
        if band < 1:
            raise ValueError("retention bands must be positive integers")
        bands.add(band)
    if not bands:
        bands.update(DEFAULT_RETENTION_BANDS)
    return tuple(sorted(bands))


def _eligible_signals_for_target(signals: Iterable[dict], *, target_issue: str) -> tuple[list[dict], int]:
    eligible: list[dict] = []
    excluded = 0
    for signal in signals:
        if issue_less_than(_signal_issue(signal), target_issue):
            eligible.append(signal)
        else:
            excluded += 1
    return eligible, excluded


def dynamic_config_for_target(
    *,
    base_config: FrequencyRankerConfig,
    signals: Iterable[dict],
    target_issue: str,
    signal_cutoff_issue: str | None = None,
    thresholds: DynamicKdjThresholds | None = None,
    offset_scale: float = 1.0,
) -> DynamicKdjConfigResult:
    threshold_values = thresholds or DynamicKdjThresholds()
    scale = _normalize_strength(offset_scale)
    cutoff_issue = signal_cutoff_issue or target_issue
    eligible, excluded = _eligible_signals_for_target(signals, target_issue=cutoff_issue)
    advice = weight_kdj_advice_from_signals(
        eligible,
        allowed_fields=CONFIG_WEIGHT_FIELDS,
        min_objective_delta=threshold_values.min_objective_delta,
        min_abs_offset=threshold_values.min_abs_offset,
        slope_window=threshold_values.slope_window,
        neutral_band=threshold_values.neutral_band,
    )
    values = config_dict(base_config)
    applied_offsets: dict[str, float] = {}
    applied_fields: set[str] = set()
    for item in advice:
        if item.decision not in {"selected", "downweighted"} or not item.applied_offset:
            continue
        if item.weight_name in applied_fields:
            continue
        scaled_offset = float(item.applied_offset) * scale
        if not scaled_offset:
            continue
        applied_fields.add(item.weight_name)
        values[item.weight_name] = float(values[item.weight_name]) + scaled_offset
        applied_offsets[item.weight_name] = scaled_offset

    dynamic_config = clamp_config(FrequencyRankerConfig(**values))
    latest_signal_issue = max((_signal_issue(signal) for signal in eligible), key=issue_sort_key, default=None)
    leakage_passed = all(issue_less_than(_signal_issue(signal), cutoff_issue) for signal in eligible)
    if latest_signal_issue is not None:
        leakage_passed = leakage_passed and issue_less_than(latest_signal_issue, cutoff_issue)
    return DynamicKdjConfigResult(
        target_issue=target_issue,
        signal_cutoff_issue=cutoff_issue,
        offset_scale=scale,
        config=dynamic_config,
        config_hash=config_hash(dynamic_config),
        eligible_signal_count=len(eligible),
        excluded_signal_count=excluded,
        latest_signal_issue=latest_signal_issue,
        leakage_passed=leakage_passed,
        applied_offsets=applied_offsets,
        advice=advice,
    )


def _target_rank_from_ranked_target(
    *,
    issue: str,
    draw_date,
    red_numbers: tuple[int, ...],
    ranked_target: tuple[int, float, object | None],
) -> TargetRank:
    rank, score, red5_match = ranked_target
    return TargetRank(
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


def _dynamic_summary(
    *,
    target_ranks: list[TargetRank],
    base_config: FrequencyRankerConfig,
    as_of_issue: str,
    history_fingerprint_value: str,
    train_window: int,
    train_mode: TrainMode,
    top_n: int,
    universe_size: int,
    target_configs: list[DynamicKdjConfigResult],
    offset_scale: float = 1.0,
    include_dynamic_configs: bool = True,
) -> dict:
    summary = summarize_target_ranks(
        target_ranks=target_ranks,
        config=base_config,
        as_of_issue=as_of_issue,
        history_fingerprint_value=history_fingerprint_value,
        train_window=train_window,
        train_mode=train_mode,
        top_n=top_n,
        universe_size=universe_size,
    )
    summary["label"] = "dynamic_kdj_per_target" if offset_scale == 1.0 else f"dynamic_kdj_strength_{offset_scale:g}"
    summary["config"] = None
    summary["base_config"] = config_dict(base_config)
    summary["config_hash"] = DYNAMIC_CONFIG_HASH if offset_scale == 1.0 else f"{DYNAMIC_CONFIG_HASH}-{offset_scale:g}"
    summary["offset_scale"] = offset_scale
    if include_dynamic_configs:
        summary["dynamic_configs"] = [item.as_dict() for item in target_configs]
    return summary


def _summary_for_config(
    *,
    label: str,
    target_ranks: list[TargetRank],
    config: FrequencyRankerConfig,
    as_of_issue: str,
    history_fingerprint_value: str,
    train_window: int,
    train_mode: TrainMode,
    top_n: int,
    universe_size: int,
) -> dict:
    summary = summarize_target_ranks(
        target_ranks=target_ranks,
        config=config,
        as_of_issue=as_of_issue,
        history_fingerprint_value=history_fingerprint_value,
        train_window=train_window,
        train_mode=train_mode,
        top_n=top_n,
        universe_size=universe_size,
    )
    summary["label"] = label
    return summary


def rank_movement_summary(*, static_ranks: list[TargetRank], dynamic_ranks: list[TargetRank]) -> dict:
    static_by_issue = {target.issue: target.rank for target in static_ranks}
    rows = []
    for dynamic in dynamic_ranks:
        static_rank = static_by_issue.get(dynamic.issue)
        if static_rank is None:
            continue
        delta = dynamic.rank - static_rank
        rows.append(
            {
                "issue": dynamic.issue,
                "static_rank": static_rank,
                "dynamic_rank": dynamic.rank,
                "delta": delta,
                "abs_delta": abs(delta),
                "improved": delta < 0,
            }
        )
    deltas = [int(row["delta"]) for row in rows]
    abs_deltas = [int(row["abs_delta"]) for row in rows]
    return {
        "target_count": len(rows),
        "changed_target_count": sum(delta != 0 for delta in deltas),
        "improved_count": sum(delta < 0 for delta in deltas),
        "worsened_count": sum(delta > 0 for delta in deltas),
        "unchanged_count": sum(delta == 0 for delta in deltas),
        "mean_delta": round(mean(deltas), 3) if deltas else 0.0,
        "median_delta": float(median(deltas)) if deltas else 0.0,
        "median_abs_delta": float(median(abs_deltas)) if abs_deltas else 0.0,
        "max_improvement": abs(min(deltas)) if deltas else 0,
        "max_worsening": max(deltas) if deltas else 0,
        "rows": rows,
    }


def offset_coverage_summary(target_configs: list[DynamicKdjConfigResult]) -> dict:
    changed_counts = [item.changed_weight_count for item in target_configs]
    abs_offsets = [abs(offset) for item in target_configs for offset in item.applied_offsets.values()]
    return {
        "target_count": len(target_configs),
        "targets_with_offsets": sum(count > 0 for count in changed_counts),
        "median_changed_weights": float(median(changed_counts)) if changed_counts else 0.0,
        "max_changed_weights": max(changed_counts, default=0),
        "median_abs_offset": round(float(median(abs_offsets)), 8) if abs_offsets else 0.0,
        "max_abs_offset": round(max(abs_offsets), 8) if abs_offsets else 0.0,
        "total_applied_offsets": len(abs_offsets),
    }


def zero_offset_coverage_summary(*, target_count: int) -> dict:
    return {
        "target_count": target_count,
        "targets_with_offsets": 0,
        "median_changed_weights": 0.0,
        "max_changed_weights": 0,
        "median_abs_offset": 0.0,
        "max_abs_offset": 0.0,
        "total_applied_offsets": 0,
    }


def retention_audit_summary(
    *,
    static_ranks: list[TargetRank],
    dynamic_ranks: list[TargetRank],
    bands: Iterable[int] | None = None,
) -> dict:
    normalized_bands = normalize_retention_bands(bands)
    dynamic_by_issue = {target.issue: target for target in dynamic_ranks}
    rows: dict[str, dict] = {}
    for band in normalized_bands:
        kept: list[str] = []
        gained: list[str] = []
        lost: list[dict] = []
        static_in_count = 0
        dynamic_in_count = 0
        for static in static_ranks:
            dynamic = dynamic_by_issue.get(static.issue)
            if dynamic is None:
                continue
            static_in = static.rank <= band
            dynamic_in = dynamic.rank <= band
            static_in_count += int(static_in)
            dynamic_in_count += int(dynamic_in)
            if static_in and dynamic_in:
                kept.append(static.issue)
            elif static_in and not dynamic_in:
                lost.append({"issue": static.issue, "static_rank": static.rank, "dynamic_rank": dynamic.rank})
            elif dynamic_in and not static_in:
                gained.append(static.issue)
        rows[str(band)] = {
            "band": band,
            "static_in_count": static_in_count,
            "dynamic_in_count": dynamic_in_count,
            "kept_count": len(kept),
            "gained_count": len(gained),
            "lost_count": len(lost),
            "retention_rate": round(len(kept) / static_in_count, 6) if static_in_count else None,
            "kept_issues": kept,
            "gained_issues": gained,
            "lost_issues": lost,
        }
    top10000 = rows.get("10000", {})
    lost_top10000_count = int(top10000.get("lost_count") or 0)
    return {
        "passed": lost_top10000_count == 0,
        "bands": rows,
        "lost_top10000_count": lost_top10000_count,
        "target_count": len(static_ranks),
        "language": (
            "Rank-band retention audit only: it measures whether dynamic KDJ loses historical targets already inside "
            "a static rank band. It is not a future-retention guarantee."
        ),
    }


def kdj_layer_for_weight(weight_name: str) -> str:
    name = str(weight_name)
    if "qian_kun" in name:
        return "qian_kun"
    if "weekday" in name:
        return "calendar"
    if "parity" in name:
        return "parity"
    if "zone" in name or "big_small" in name:
        return "zone"
    if "omission" in name or "cooldown" in name:
        return "omission"
    if "frequency" in name or "hot" in name:
        return "frequency"
    if "sum" in name:
        return "sum"
    if "span" in name:
        return "span"
    if any(token in name for token in ("consecutive", "neighbor", "gap", "overlap", "repeat")):
        return "adjacency"
    return "other"


def kdj_layer_audit_summary(
    target_configs: list[DynamicKdjConfigResult],
    *,
    concentration_threshold: float = KDJ_LAYER_CONCENTRATION_WARNING_THRESHOLD,
) -> dict:
    layer_counts: dict[str, Counter] = defaultdict(Counter)
    field_counts: dict[str, Counter] = defaultdict(Counter)
    decision_counts: Counter = Counter()
    layer_contribution: Counter = Counter()
    advice_count = 0
    for result in target_configs:
        for advice in result.advice:
            layer = kdj_layer_for_weight(advice.weight_name)
            decision = advice.decision or "unknown"
            advice_count += 1
            decision_counts[decision] += 1
            layer_counts[layer][decision] += 1
            field_counts[advice.weight_name][decision] += 1
            if decision in {"selected", "downweighted"}:
                layer_contribution[layer] += abs(float(advice.applied_offset)) * max(0.0, float(advice.objective_delta))

    total_contribution = float(sum(layer_contribution.values()))
    layers: dict[str, dict] = {}
    for layer in sorted(set(layer_counts) | set(layer_contribution)):
        contribution = float(layer_contribution.get(layer, 0.0))
        layers[layer] = {
            "selected": int(layer_counts[layer].get("selected", 0)),
            "downweighted": int(layer_counts[layer].get("downweighted", 0)),
            "rejected": int(layer_counts[layer].get("rejected", 0)),
            "other_decisions": int(sum(layer_counts[layer].values()) - layer_counts[layer].get("selected", 0) - layer_counts[layer].get("downweighted", 0) - layer_counts[layer].get("rejected", 0)),
            "contribution": round(contribution, 8),
            "contribution_share": round(contribution / total_contribution, 6) if total_contribution else 0.0,
        }
    top_layer_name = max(layers, key=lambda key: layers[key]["contribution_share"], default="")
    max_share = float(layers.get(top_layer_name, {}).get("contribution_share") or 0.0)
    warnings: list[str] = []
    if total_contribution > 0 and max_share >= concentration_threshold:
        warnings.append(f"layer_contribution_concentration:{top_layer_name}:{max_share:.3f}")
    return {
        "target_count": len(target_configs),
        "advice_count": advice_count,
        "decision_counts": {key: int(value) for key, value in sorted(decision_counts.items())},
        "layers": layers,
        "field_decision_counts": {
            field: {decision: int(count) for decision, count in sorted(counter.items())}
            for field, counter in sorted(field_counts.items())
        },
        "total_contribution": round(total_contribution, 8),
        "top_layer": {
            "name": top_layer_name,
            "contribution_share": round(max_share, 6),
        },
        "warnings": warnings,
        "language": (
            "Layer audit groups KDJ weight advice into structural layers to expose dominance. "
            "A concentrated layer is a diagnostic warning, not a rejection by itself."
        ),
    }


def leakage_audit_summary(target_configs: list[DynamicKdjConfigResult]) -> dict:
    violations = [item.as_dict() for item in target_configs if not item.leakage_passed]
    return {
        "passed": not violations,
        "target_count": len(target_configs),
        "violation_count": len(violations),
        "excluded_signal_rows_due_to_issue_gte_target": sum(item.excluded_signal_count for item in target_configs),
        "latest_signal_issue_by_target": {
            item.target_issue: item.latest_signal_issue for item in target_configs if item.latest_signal_issue is not None
        },
        "violations": violations,
        "rule": "target issue T may use only training_weight_signals rows with issue < T",
    }


def circular_shift_signal_issues(signals: Iterable[dict], *, shift: int = 1) -> list[dict]:
    rows = [dict(signal) for signal in signals]
    issues = sorted({_signal_issue(signal) for signal in rows if _signal_issue(signal)}, key=issue_sort_key)
    if not issues:
        return rows
    safe_shift = shift % len(issues)
    mapping = {issue: issues[(index + safe_shift) % len(issues)] for index, issue in enumerate(issues)}
    for row in rows:
        issue = _signal_issue(row)
        if issue in mapping:
            row["issue"] = mapping[issue]
            row["negative_control_original_issue"] = issue
    return rows


def shuffle_signal_weight_names(signals: Iterable[dict], *, shift: int = 1) -> list[dict]:
    rows = [dict(signal) for signal in signals]
    weights = sorted(
        {
            str(signal.get("weight_name") or "")
            for signal in rows
            if str(signal.get("weight_name") or "") in CONFIG_WEIGHT_FIELDS
        }
    )
    if not weights:
        return rows
    safe_shift = shift % len(weights)
    mapping = {weight: weights[(index + safe_shift) % len(weights)] for index, weight in enumerate(weights)}
    for row in rows:
        weight_name = str(row.get("weight_name") or "")
        if weight_name in mapping:
            row["weight_name"] = mapping[weight_name]
            row["negative_control_original_weight_name"] = weight_name
    return rows


def compact_experiment_payload(payload: dict) -> dict:
    return {
        "candidate_source": payload.get("candidate_source"),
        "control": payload.get("control"),
        "protocol": payload.get("protocol"),
        "thresholds": payload.get("thresholds"),
        "acceptance": payload.get("acceptance"),
        "dynamic": {
            "top_100_hits": payload.get("dynamic", {}).get("top_100_hits"),
            "top_1000_hits": payload.get("dynamic", {}).get("top_1000_hits"),
            "top_10000_hits": payload.get("dynamic", {}).get("top_10000_hits"),
            "median_rank": payload.get("dynamic", {}).get("median_rank"),
            "best_rank": payload.get("dynamic", {}).get("best_rank"),
            "worst_rank": payload.get("dynamic", {}).get("worst_rank"),
            "rank_quality": payload.get("dynamic", {}).get("rank_quality"),
            "reward": payload.get("dynamic", {}).get("reward"),
        },
        "rank_movement": payload.get("rank_movement"),
        "offset_coverage": payload.get("offset_coverage"),
        "retention_audit": {
            "passed": payload.get("retention_audit", {}).get("passed"),
            "lost_top10000_count": payload.get("retention_audit", {}).get("lost_top10000_count"),
        },
        "strength_sweep": {
            "strengths": payload.get("strength_sweep", {}).get("strengths"),
            "best_by_objective": payload.get("strength_sweep", {}).get("best_by_objective"),
            "best_by_median_rank": payload.get("strength_sweep", {}).get("best_by_median_rank"),
        },
        "kdj_layer_audit": {
            "top_layer": payload.get("kdj_layer_audit", {}).get("top_layer"),
            "warnings": payload.get("kdj_layer_audit", {}).get("warnings"),
        },
        "leakage_audit": {
            "passed": payload.get("leakage_audit", {}).get("passed"),
            "violation_count": payload.get("leakage_audit", {}).get("violation_count"),
            "excluded_signal_rows_due_to_issue_gte_target": payload.get("leakage_audit", {}).get(
                "excluded_signal_rows_due_to_issue_gte_target"
            ),
        },
    }


def negative_control_experiments(
    *,
    history: list[HistoryDraw],
    ranked_universe,
    base_config: FrequencyRankerConfig,
    signals: list[dict],
    train_window: int,
    train_mode: TrainMode,
    eval_window: int,
    top_n: int,
    thresholds: DynamicKdjThresholds,
    acceptance_config: DynamicKdjAcceptanceConfig,
) -> dict:
    controls: dict[str, dict] = {}
    variants = (
        ("issue_circular_shift", circular_shift_signal_issues(signals)),
        ("weight_name_shuffle", shuffle_signal_weight_names(signals)),
        ("issue_lag_1", signals),
        ("issue_lag_3", signals),
    )
    for name, control_signals in variants:
        lag = 1 if name == "issue_lag_1" else 3 if name == "issue_lag_3" else 0
        control_payload = evaluate_dynamic_kdj_backtest(
            history=history,
            ranked_universe=ranked_universe,
            base_config=base_config,
            signals=control_signals,
            train_window=train_window,
            train_mode=train_mode,
            eval_window=eval_window,
            top_n=top_n,
            thresholds=thresholds,
            acceptance_config=acceptance_config,
            include_negative_controls=False,
            control={"name": name, "signal_issue_lag": lag},
            signal_issue_lag=lag,
        )
        controls[name] = compact_experiment_payload(control_payload)
    passing_controls = [
        name
        for name, payload in controls.items()
        if isinstance(payload.get("acceptance"), dict) and payload["acceptance"].get("status") == "PASS"
    ]
    return {
        "passed": not passing_controls,
        "control_count": len(controls),
        "passing_controls": passing_controls,
        "controls": controls,
        "language": "If any shifted or shuffled KDJ control passes the same gate, the dynamic KDJ signal is treated as noise-like.",
    }


def _reward_objective(summary: dict) -> float:
    reward = summary.get("reward") if isinstance(summary.get("reward"), dict) else {}
    return float(reward.get("objectiveScore") or 0.0)


def _rank_quality(summary: dict) -> dict:
    return summary.get("rank_quality") if isinstance(summary.get("rank_quality"), dict) else {}


def _tail_not_worse_than(dynamic_summary: dict, baseline_summary: dict) -> bool:
    dynamic_rank_quality = _rank_quality(dynamic_summary)
    baseline_rank_quality = _rank_quality(baseline_summary)
    for field in ("p95_rank", "tail_risk_penalty"):
        dynamic_value = dynamic_rank_quality.get(field)
        baseline_value = baseline_rank_quality.get(field)
        if dynamic_value is not None and baseline_value is not None and float(dynamic_value) > float(baseline_value):
            return False
    for field in ("tail_over_750000_count", "tail_over_900000_count", "tail_over_1000000_count"):
        if int(dynamic_rank_quality.get(field) or 0) > int(baseline_rank_quality.get(field) or 0):
            return False
    if (dynamic_summary.get("worst_rank") or 0) > (baseline_summary.get("worst_rank") or 0):
        return False
    return True


def _median_rank(summary: dict) -> float:
    return float(summary.get("median_rank") or 0.0)


def _negative_control_summary(negative_controls: dict | None) -> dict:
    if not isinstance(negative_controls, dict):
        return {"passed": True, "control_count": 0, "passing_controls": []}
    controls = negative_controls.get("controls") if isinstance(negative_controls.get("controls"), dict) else {}
    passing = [
        name
        for name, control in controls.items()
        if isinstance(control, dict)
        and isinstance(control.get("acceptance"), dict)
        and control["acceptance"].get("status") == "PASS"
    ]
    return {"passed": not passing, "control_count": len(controls), "passing_controls": passing}


def _retention_audit_passed(retention_audit: dict | None) -> bool:
    if not isinstance(retention_audit, dict):
        return True
    return int(retention_audit.get("lost_top10000_count") or 0) == 0


def acceptance_summary(
    *,
    static_summary: dict,
    dynamic_summary: dict,
    null_summary: dict,
    movement: dict,
    leakage: dict,
    offset_coverage: dict,
    eval_window: int,
    acceptance_config: DynamicKdjAcceptanceConfig | None = None,
    negative_controls: dict | None = None,
    retention_audit: dict | None = None,
) -> dict:
    config = acceptance_config or DynamicKdjAcceptanceConfig()
    static_median = float(static_summary.get("median_rank") or 0.0)
    dynamic_median = float(dynamic_summary.get("median_rank") or 0.0)
    median_improvement_pct = ((static_median - dynamic_median) / static_median) if static_median > 0 else 0.0
    dynamic_top10000 = int(dynamic_summary.get("top_10000_hits") or 0)
    static_top10000 = int(static_summary.get("top_10000_hits") or 0)
    tail_not_worse = _tail_not_worse_than(dynamic_summary, static_summary) and _tail_not_worse_than(
        dynamic_summary,
        null_summary,
    )
    rank_movement_passed = int(movement.get("changed_target_count") or 0) > 0 and float(movement.get("median_abs_delta") or 0.0) > 2
    primary_passed = dynamic_top10000 > static_top10000 or median_improvement_pct >= 0.02
    beats_static = _reward_objective(dynamic_summary) > _reward_objective(static_summary) and dynamic_median <= static_median
    beats_null = _reward_objective(dynamic_summary) > _reward_objective(null_summary) and dynamic_median <= _median_rank(null_summary)
    offset_within_limit = (
        float(offset_coverage.get("median_changed_weights") or 0.0) <= config.max_median_changed_weights
        and int(offset_coverage.get("max_changed_weights") or 0) <= config.max_max_changed_weights
        and float(offset_coverage.get("max_abs_offset") or 0.0) <= config.max_abs_offset
    )
    negative_control_result = _negative_control_summary(negative_controls)
    retention_passed = _retention_audit_passed(retention_audit)
    min_window_passed = eval_window >= config.min_eval_window_for_pass
    gate_passed = bool(
        primary_passed
        and beats_static
        and beats_null
        and tail_not_worse
        and rank_movement_passed
        and bool(leakage.get("passed"))
        and offset_within_limit
        and negative_control_result["passed"]
        and retention_passed
    )
    status = "RESEARCH_ONLY" if not min_window_passed else "PASS" if gate_passed else "FAIL"
    failures: list[str] = []
    if not min_window_passed:
        failures.append("eval_window_below_min_for_pass")
    if not primary_passed:
        failures.append("primary_metric_not_improved")
    if not beats_static:
        failures.append("dynamic_did_not_beat_static")
    if not beats_null:
        failures.append("dynamic_did_not_beat_null")
    if not tail_not_worse:
        failures.append("tail_risk_worse_than_static_or_null")
    if not rank_movement_passed:
        failures.append("rank_movement_too_small")
    if not leakage.get("passed"):
        failures.append("leakage_audit_failed")
    if not offset_within_limit:
        failures.append("offset_coverage_too_wide")
    if not negative_control_result["passed"]:
        failures.append("negative_control_passed")
    if not retention_passed:
        failures.append("retention_lost_top10000")
    return {
        "status": status,
        "passed": status == "PASS",
        "research_only": status == "RESEARCH_ONLY",
        "failures": failures,
        "primary_passed": primary_passed,
        "beats_static": beats_static,
        "beats_null": beats_null,
        "tail_not_worse": tail_not_worse,
        "rank_movement_passed": rank_movement_passed,
        "leakage_passed": bool(leakage.get("passed")),
        "offset_within_limit": offset_within_limit,
        "negative_controls_passed": negative_control_result["passed"],
        "retention_passed": retention_passed,
        "negative_controls": negative_control_result,
        "lost_top10000_count": int((retention_audit or {}).get("lost_top10000_count") or 0),
        "dynamic_top10000": dynamic_top10000,
        "static_top10000": static_top10000,
        "null_top10000": int(null_summary.get("top_10000_hits") or 0),
        "median_improvement_pct": round(median_improvement_pct, 6),
        "dynamic_objective": _reward_objective(dynamic_summary),
        "static_objective": _reward_objective(static_summary),
        "null_objective": _reward_objective(null_summary),
        "acceptance_config": config.as_dict(),
        "language": (
            "PASS requires enough eval draws, dynamic primary lift, beating static and null objectives/median, "
            "no worse p95/worst/tail buckets than static or null, bounded offset coverage, non-jitter rank movement, "
            "zero leakage violations, no passing negative controls, and no loss of static Top10000 rank-band retention"
        ),
    }


def _strength_metric_row(*, strength: float, summary: dict, movement: dict, retention: dict, offset_coverage: dict) -> dict:
    reward = summary.get("reward") if isinstance(summary.get("reward"), dict) else {}
    return {
        "strength": strength,
        "label": summary.get("label"),
        "top_100_hits": int(summary.get("top_100_hits") or 0),
        "top_1000_hits": int(summary.get("top_1000_hits") or 0),
        "top_10000_hits": int(summary.get("top_10000_hits") or 0),
        "median_rank": summary.get("median_rank"),
        "best_rank": summary.get("best_rank"),
        "worst_rank": summary.get("worst_rank"),
        "objective": float(reward.get("objectiveScore") or 0.0),
        "changed_target_count": int(movement.get("changed_target_count") or 0),
        "improved_count": int(movement.get("improved_count") or 0),
        "worsened_count": int(movement.get("worsened_count") or 0),
        "unchanged_count": int(movement.get("unchanged_count") or 0),
        "median_abs_delta": movement.get("median_abs_delta"),
        "lost_top10000_count": int(retention.get("lost_top10000_count") or 0),
        "targets_with_offsets": int(offset_coverage.get("targets_with_offsets") or 0),
        "median_changed_weights": offset_coverage.get("median_changed_weights"),
        "max_abs_offset": offset_coverage.get("max_abs_offset"),
    }


def strength_sweep_summary(rows: list[dict]) -> dict:
    best_by_objective = max(rows, key=lambda row: row["objective"], default=None)
    best_by_median = min(
        rows,
        key=lambda row: (
            float(row["median_rank"] or 0),
            float(row["worst_rank"] or 0),
            -float(row["objective"] or 0.0),
        ),
        default=None,
    )
    return {
        "strengths": [row["strength"] for row in rows],
        "rows": rows,
        "best_by_objective": best_by_objective,
        "best_by_median_rank": best_by_median,
        "language": (
            "Strength sweep measures how much KDJ offset intensity changes historical ranks under the same universe. "
            "Strength 0.0 is the static baseline; strength 1.0 is the current dynamic KDJ offset scale."
        ),
    }


def evaluate_dynamic_kdj_backtest(
    *,
    history: list[HistoryDraw],
    ranked_universe,
    base_config: FrequencyRankerConfig,
    signals: Iterable[dict],
    train_window: int,
    train_mode: TrainMode,
    eval_window: int,
    top_n: int,
    thresholds: DynamicKdjThresholds | None = None,
    acceptance_config: DynamicKdjAcceptanceConfig | None = None,
    include_negative_controls: bool = True,
    control: dict | None = None,
    signal_issue_lag: int = 0,
    strength_sweep: Iterable[float] | None = None,
    retention_bands: Iterable[int] | None = None,
) -> dict:
    signal_rows = list(signals)
    threshold_values = thresholds or DynamicKdjThresholds()
    acceptance_values = acceptance_config or DynamicKdjAcceptanceConfig()
    strength_values = normalize_strength_sweep(strength_sweep)
    retention_band_values = normalize_retention_bands(retention_bands)
    nonzero_strengths = tuple(strength for strength in strength_values if strength != 0.0)
    indexes = list(target_indexes(history_len=len(history), train_window=train_window, eval_window=eval_window))
    static_ranks: list[TargetRank] = []
    null_ranks: list[TargetRank] = []
    sweep_ranks_by_strength: dict[float, list[TargetRank]] = {strength: [] for strength in nonzero_strengths}
    target_configs_by_strength: dict[float, list[DynamicKdjConfigResult]] = {strength: [] for strength in nonzero_strengths}
    null_config = FrequencyRankerConfig(
        structural_weight=0.0,
        frequency_weight=0.0,
        omission_weight=0.0,
        previous_consecutive_weight=0.0,
    )

    for target_index in indexes:
        target_draw = history[target_index]
        target_issue = history_issue(target_draw)
        cutoff_index = max(0, target_index - max(0, int(signal_issue_lag)))
        signal_cutoff_issue = history_issue(history[cutoff_index])
        dynamic_results = {
            strength: dynamic_config_for_target(
                base_config=base_config,
                signals=signal_rows,
                target_issue=target_issue,
                signal_cutoff_issue=signal_cutoff_issue,
                thresholds=threshold_values,
                offset_scale=strength,
            )
            for strength in nonzero_strengths
        }
        train_start = 0 if train_mode == "expanding" else max(0, target_index - train_window)
        train_history = history[train_start:target_index]
        ranked_targets = rank_target_grid_with_red5(
            target_numbers=history_numbers(target_draw),
            train_history=train_history,
            configs=(base_config, *(dynamic_results[strength].config for strength in nonzero_strengths), null_config),
            ranked_universe=ranked_universe,
            target_draw_date=history_draw_date(target_draw),
            workers=1,
            pool=None,
        )
        draw_date = history_draw_date(target_draw)
        red_numbers = history_numbers(target_draw)
        static_ranks.append(
            _target_rank_from_ranked_target(
                issue=target_issue,
                draw_date=draw_date,
                red_numbers=red_numbers,
                ranked_target=ranked_targets[0],
            )
        )
        for index, strength in enumerate(nonzero_strengths, start=1):
            sweep_ranks_by_strength[strength].append(
                _target_rank_from_ranked_target(
                    issue=target_issue,
                    draw_date=draw_date,
                    red_numbers=red_numbers,
                    ranked_target=ranked_targets[index],
                )
            )
            target_configs_by_strength[strength].append(dynamic_results[strength])
        null_ranks.append(
            _target_rank_from_ranked_target(
                issue=target_issue,
                draw_date=draw_date,
                red_numbers=red_numbers,
                ranked_target=ranked_targets[-1],
            )
        )

    as_of_issue = history_issue(history[-1])
    history_fingerprint_value = fingerprint_history(history)
    dynamic_ranks = sweep_ranks_by_strength[1.0]
    target_configs = target_configs_by_strength[1.0]
    static_summary = _summary_for_config(
        label="static_base_config",
        target_ranks=static_ranks,
        config=base_config,
        as_of_issue=as_of_issue,
        history_fingerprint_value=history_fingerprint_value,
        train_window=train_window,
        train_mode=train_mode,
        top_n=top_n,
        universe_size=len(ranked_universe),
    )
    dynamic_summary = _dynamic_summary(
        target_ranks=dynamic_ranks,
        base_config=base_config,
        as_of_issue=as_of_issue,
        history_fingerprint_value=history_fingerprint_value,
        train_window=train_window,
        train_mode=train_mode,
        top_n=top_n,
        universe_size=len(ranked_universe),
        target_configs=target_configs,
    )
    null_summary = _summary_for_config(
        label="null_baseline",
        target_ranks=null_ranks,
        config=null_config,
        as_of_issue=as_of_issue,
        history_fingerprint_value=history_fingerprint_value,
        train_window=train_window,
        train_mode=train_mode,
        top_n=top_n,
        universe_size=len(ranked_universe),
    )
    movement = rank_movement_summary(static_ranks=static_ranks, dynamic_ranks=dynamic_ranks)
    leakage = leakage_audit_summary(target_configs)
    offset_coverage = offset_coverage_summary(target_configs)
    retention_audit = retention_audit_summary(
        static_ranks=static_ranks,
        dynamic_ranks=dynamic_ranks,
        bands=retention_band_values,
    )
    layer_audit = kdj_layer_audit_summary(target_configs)
    sweep_rows: list[dict] = []
    for strength in strength_values:
        if strength == 0.0:
            sweep_summary = static_summary
            sweep_ranks = static_ranks
            sweep_offset_coverage = zero_offset_coverage_summary(target_count=len(static_ranks))
        else:
            sweep_ranks = sweep_ranks_by_strength[strength]
            sweep_summary = _dynamic_summary(
                target_ranks=sweep_ranks,
                base_config=base_config,
                as_of_issue=as_of_issue,
                history_fingerprint_value=history_fingerprint_value,
                train_window=train_window,
                train_mode=train_mode,
                top_n=top_n,
                universe_size=len(ranked_universe),
                target_configs=target_configs_by_strength[strength],
                offset_scale=strength,
                include_dynamic_configs=False,
            )
            sweep_offset_coverage = offset_coverage_summary(target_configs_by_strength[strength])
        sweep_movement = rank_movement_summary(static_ranks=static_ranks, dynamic_ranks=sweep_ranks)
        sweep_retention = retention_audit_summary(
            static_ranks=static_ranks,
            dynamic_ranks=sweep_ranks,
            bands=retention_band_values,
        )
        sweep_rows.append(
            _strength_metric_row(
                strength=strength,
                summary=sweep_summary,
                movement=sweep_movement,
                retention=sweep_retention,
                offset_coverage=sweep_offset_coverage,
            )
        )
    sweep = strength_sweep_summary(sweep_rows)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_source": "dynamic-kdj",
        "control": control,
        "protocol": {
            "as_of_issue": as_of_issue,
            "history_fingerprint": history_fingerprint_value,
            "train_mode": train_mode,
            "train_window": train_window,
            "eval_window": len(indexes),
            "top_n": top_n,
            "universe_size": len(ranked_universe),
            "signal_issue_lag": max(0, int(signal_issue_lag)),
            "kdj_strength_sweep": list(strength_values),
            "retention_bands": list(retention_band_values),
            "target_issues": [history_issue(history[index]) for index in indexes],
            "protocol_equality": {
                "same_universe": True,
                "same_target_issues": True,
                "same_top_n": True,
                "same_train_eval_protocol": True,
            },
        },
        "thresholds": threshold_values.as_dict(),
        "acceptance_config": acceptance_values.as_dict(),
        "dynamic": dynamic_summary,
        "static_baseline": static_summary,
        "null_baseline": null_summary,
        "strength_sweep": sweep,
        "rank_movement": movement,
        "offset_coverage": offset_coverage,
        "retention_audit": retention_audit,
        "kdj_layer_audit": layer_audit,
        "leakage_audit": leakage,
        "skill_audit": {
            "einstein_pass": "same-universe strength sweep turns KDJ strength into a falsifiable variable against static and null baselines",
            "gauss_pass": "retention bands record exact kept/gained/lost historical targets, with Top10000 loss as an audit failure",
            "riemann_pass": "layer audit treats KDJ advice as structural sheets and reports concentration instead of promoting a hidden hard filter",
        },
        "static_kdj_advisor_control": {"status": "skipped", "reason": STATIC_KDJ_ADVISOR_SKIP_REASON},
        "guardrail": (
            "Frozen historical response-surface test only. This does not claim lottery prediction; "
            "promotion requires later frozen or forward validation."
        ),
        "feature_matrix_cache": dict(getattr(ranked_universe, "cache_info", {})),
    }
    negative_controls = None
    if include_negative_controls:
        negative_controls = negative_control_experiments(
            history=history,
            ranked_universe=ranked_universe,
            base_config=base_config,
            signals=signal_rows,
            train_window=train_window,
            train_mode=train_mode,
            eval_window=eval_window,
            top_n=top_n,
            thresholds=threshold_values,
            acceptance_config=acceptance_values,
        )
        payload["negative_controls"] = negative_controls
    payload["acceptance"] = acceptance_summary(
        static_summary=static_summary,
        dynamic_summary=dynamic_summary,
        null_summary=null_summary,
        movement=movement,
        leakage=leakage,
        offset_coverage=offset_coverage,
        eval_window=len(indexes),
        acceptance_config=acceptance_values,
        negative_controls=negative_controls,
        retention_audit=retention_audit,
    )
    return payload


def render_dynamic_kdj_report(payload: dict) -> str:
    protocol = payload["protocol"]
    dynamic = payload["dynamic"]
    static = payload["static_baseline"]
    null = payload["null_baseline"]
    acceptance = payload["acceptance"]
    movement = payload["rank_movement"]
    leakage = payload["leakage_audit"]
    offset = payload["offset_coverage"]
    negative_controls = payload.get("negative_controls") if isinstance(payload.get("negative_controls"), dict) else {}
    strength_sweep_payload = payload.get("strength_sweep") if isinstance(payload.get("strength_sweep"), dict) else {}
    retention = payload.get("retention_audit") if isinstance(payload.get("retention_audit"), dict) else {}
    layer_audit = payload.get("kdj_layer_audit") if isinstance(payload.get("kdj_layer_audit"), dict) else {}
    skill_audit = payload.get("skill_audit") if isinstance(payload.get("skill_audit"), dict) else {}
    rows = "\n".join(
        f"| {item['label']} | {item['top_100_hits']} | {item['top_1000_hits']} | {item['top_10000_hits']} | "
        f"{item['median_rank']} | {item['best_rank']} | {item['worst_rank']} | "
        f"{item['rank_quality']['p95_rank']} | {item['rank_quality']['tail_over_750000_count']} | "
        f"{item['rank_quality']['tail_over_900000_count']} | {item['rank_quality']['tail_over_1000000_count']} | "
        f"{item['reward']['objectiveScore']} |"
        for item in (dynamic, static, null)
    )
    strength_rows = "\n".join(
        f"| {row['strength']} | {row['top_100_hits']} | {row['top_1000_hits']} | {row['top_10000_hits']} | "
        f"{row['median_rank']} | {row['worst_rank']} | {row['objective']} | "
        f"{row['improved_count']} | {row['worsened_count']} | {row['lost_top10000_count']} | "
        f"{row['median_changed_weights']} | {row['max_abs_offset']} |"
        for row in strength_sweep_payload.get("rows") or []
    ) or "| n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |"
    retention_rows = "\n".join(
        f"| {band} | {info['static_in_count']} | {info['dynamic_in_count']} | {info['kept_count']} | "
        f"{info['gained_count']} | {info['lost_count']} | {info['retention_rate']} |"
        for band, info in sorted((retention.get("bands") or {}).items(), key=lambda item: int(item[0]))
    ) or "| n/a | n/a | n/a | n/a | n/a | n/a | n/a |"
    layer_rows = "\n".join(
        f"| {layer} | {info['selected']} | {info['downweighted']} | {info['rejected']} | "
        f"{info['contribution']} | {info['contribution_share']} |"
        for layer, info in sorted((layer_audit.get("layers") or {}).items())
    ) or "| n/a | n/a | n/a | n/a | n/a | n/a |"
    negative_rows = "\n".join(
        f"| {name} | {control['acceptance']['status']} | {control['acceptance']['dynamic_objective']} | "
        f"{control['dynamic']['median_rank']} | {control['dynamic']['worst_rank']} | "
        f"{control['offset_coverage']['median_changed_weights']} |"
        for name, control in (negative_controls.get("controls") or {}).items()
    ) or "| n/a | n/a | n/a | n/a | n/a | n/a |"
    return f"""# Dynamic KDJ Frozen Backtest

- Generated at: {payload["generated_at"]}
- As-of issue: `{protocol["as_of_issue"]}`
- Train mode/window: `{protocol["train_mode"]}` / {protocol["train_window"]}
- Eval window: {protocol["eval_window"]}
- Top-N: {protocol["top_n"]}
- Universe size: {protocol["universe_size"]}
- Acceptance: `{acceptance["status"]}`

## Summary

| Label | Top100 | Top1000 | Top10000 | Median rank | Best rank | Worst rank | P95 rank | Tail >750000 | Tail >900000 | Tail >1000000 | Objective |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{rows}

## Einstein / Gauss / Riemann Audit

- Einstein pass: {skill_audit.get("einstein_pass", "")}
- Gauss pass: {skill_audit.get("gauss_pass", "")}
- Riemann pass: {skill_audit.get("riemann_pass", "")}

## Strength Sweep

- Best by objective: `{(strength_sweep_payload.get("best_by_objective") or {}).get("strength", "n/a")}`
- Best by median rank: `{(strength_sweep_payload.get("best_by_median_rank") or {}).get("strength", "n/a")}`
- Interpretation: {strength_sweep_payload.get("language", "")}

| KDJ strength | Top100 | Top1000 | Top10000 | Median rank | Worst rank | Objective | Improved | Worsened | Lost Top10000 | Median changed weights | Max abs offset |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{strength_rows}

## Retention Audit

- Passed: {retention.get("passed")}
- Lost Top10000 count: {retention.get("lost_top10000_count")}
- Boundary: {retention.get("language", "")}

| Band | Static in band | Dynamic in band | Kept | Gained | Lost | Retention rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{retention_rows}

## KDJ Layer Audit

- Top layer: `{(layer_audit.get("top_layer") or {}).get("name", "")}` share={(layer_audit.get("top_layer") or {}).get("contribution_share", 0)}
- Warnings: {", ".join(layer_audit.get("warnings") or []) or "none"}
- Boundary: {layer_audit.get("language", "")}

| Layer | Selected | Downweighted | Rejected | Contribution | Contribution share |
| --- | ---: | ---: | ---: | ---: | ---: |
{layer_rows}

## Dynamic Movement

- Changed targets: {movement["changed_target_count"]} / {movement["target_count"]}
- Improved / worsened / unchanged: {movement["improved_count"]} / {movement["worsened_count"]} / {movement["unchanged_count"]}
- Median abs delta: {movement["median_abs_delta"]}
- Mean delta: {movement["mean_delta"]}

## Offset Coverage

- Targets with offsets: {offset["targets_with_offsets"]} / {offset["target_count"]}
- Median changed weights: {offset["median_changed_weights"]}
- Max changed weights: {offset["max_changed_weights"]}
- Median / max abs offset: {offset["median_abs_offset"]} / {offset["max_abs_offset"]}

## Negative Controls

- Passed gate: {negative_controls.get("passed", True)}
- Passing controls: {", ".join(negative_controls.get("passing_controls") or []) or "none"}

| Control | Status | Objective | Median rank | Worst rank | Median changed weights |
| --- | --- | ---: | ---: | ---: | ---: |
{negative_rows}

## Leakage Audit

- Passed: {leakage["passed"]}
- Violations: {leakage["violation_count"]}
- Excluded issue>=T signal rows: {leakage["excluded_signal_rows_due_to_issue_gte_target"]}
- Rule: {leakage["rule"]}

## Acceptance

```json
{_json_dumps(acceptance)}
```

## Static KDJ Advisor Control

{payload["static_kdj_advisor_control"]["reason"]}

## Guardrail

{payload["guardrail"]}
"""


def _json_dumps(value: object) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
