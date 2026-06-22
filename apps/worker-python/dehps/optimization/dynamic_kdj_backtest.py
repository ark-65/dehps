from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
class DynamicKdjConfigResult:
    target_issue: str
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
    thresholds: DynamicKdjThresholds | None = None,
) -> DynamicKdjConfigResult:
    threshold_values = thresholds or DynamicKdjThresholds()
    eligible, excluded = _eligible_signals_for_target(signals, target_issue=target_issue)
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
    for item in advice:
        if item.decision not in {"selected", "downweighted"} or not item.applied_offset:
            continue
        values[item.weight_name] = float(values[item.weight_name]) + float(item.applied_offset)
        applied_offsets[item.weight_name] = float(item.applied_offset)

    dynamic_config = clamp_config(FrequencyRankerConfig(**values))
    latest_signal_issue = max((_signal_issue(signal) for signal in eligible), key=issue_sort_key, default=None)
    leakage_passed = all(issue_less_than(_signal_issue(signal), target_issue) for signal in eligible)
    if latest_signal_issue is not None:
        leakage_passed = leakage_passed and issue_less_than(latest_signal_issue, target_issue)
    return DynamicKdjConfigResult(
        target_issue=target_issue,
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
    summary["label"] = "dynamic_kdj_per_target"
    summary["config"] = None
    summary["base_config"] = config_dict(base_config)
    summary["config_hash"] = DYNAMIC_CONFIG_HASH
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


def acceptance_summary(*, static_summary: dict, dynamic_summary: dict, movement: dict, leakage: dict) -> dict:
    static_median = float(static_summary.get("median_rank") or 0.0)
    dynamic_median = float(dynamic_summary.get("median_rank") or 0.0)
    median_improvement_pct = ((static_median - dynamic_median) / static_median) if static_median > 0 else 0.0
    static_rank_quality = static_summary.get("rank_quality") if isinstance(static_summary.get("rank_quality"), dict) else {}
    dynamic_rank_quality = dynamic_summary.get("rank_quality") if isinstance(dynamic_summary.get("rank_quality"), dict) else {}
    dynamic_top10000 = int(dynamic_summary.get("top_10000_hits") or 0)
    static_top10000 = int(static_summary.get("top_10000_hits") or 0)
    tail_not_worse = (
        int(dynamic_rank_quality.get("tail_over_1000000_count") or 0)
        <= int(static_rank_quality.get("tail_over_1000000_count") or 0)
        and float(dynamic_rank_quality.get("tail_risk_penalty") or 0.0)
        <= float(static_rank_quality.get("tail_risk_penalty") or 0.0)
    )
    rank_movement_passed = int(movement.get("changed_target_count") or 0) > 0 and float(movement.get("median_abs_delta") or 0.0) > 2
    primary_passed = dynamic_top10000 > static_top10000 or median_improvement_pct >= 0.02
    passed = bool(primary_passed and tail_not_worse and rank_movement_passed and leakage.get("passed"))
    return {
        "passed": passed,
        "primary_passed": primary_passed,
        "tail_not_worse": tail_not_worse,
        "rank_movement_passed": rank_movement_passed,
        "leakage_passed": bool(leakage.get("passed")),
        "dynamic_top10000": dynamic_top10000,
        "static_top10000": static_top10000,
        "median_improvement_pct": round(median_improvement_pct, 6),
        "language": (
            "pass requires dynamic top10000 lift or >=2% median-rank improvement, no worse tail risk, "
            "non-jitter rank movement, and zero leakage violations"
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
) -> dict:
    signal_rows = list(signals)
    indexes = list(target_indexes(history_len=len(history), train_window=train_window, eval_window=eval_window))
    static_ranks: list[TargetRank] = []
    dynamic_ranks: list[TargetRank] = []
    null_ranks: list[TargetRank] = []
    target_configs: list[DynamicKdjConfigResult] = []
    null_config = FrequencyRankerConfig(
        structural_weight=0.0,
        frequency_weight=0.0,
        omission_weight=0.0,
        previous_consecutive_weight=0.0,
    )

    for target_index in indexes:
        target_draw = history[target_index]
        target_issue = history_issue(target_draw)
        dynamic_result = dynamic_config_for_target(
            base_config=base_config,
            signals=signal_rows,
            target_issue=target_issue,
            thresholds=thresholds,
        )
        train_start = 0 if train_mode == "expanding" else max(0, target_index - train_window)
        train_history = history[train_start:target_index]
        ranked_targets = rank_target_grid_with_red5(
            target_numbers=history_numbers(target_draw),
            train_history=train_history,
            configs=(base_config, dynamic_result.config, null_config),
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
        dynamic_ranks.append(
            _target_rank_from_ranked_target(
                issue=target_issue,
                draw_date=draw_date,
                red_numbers=red_numbers,
                ranked_target=ranked_targets[1],
            )
        )
        null_ranks.append(
            _target_rank_from_ranked_target(
                issue=target_issue,
                draw_date=draw_date,
                red_numbers=red_numbers,
                ranked_target=ranked_targets[2],
            )
        )
        target_configs.append(dynamic_result)

    as_of_issue = history_issue(history[-1])
    history_fingerprint_value = fingerprint_history(history)
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
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_source": "dynamic-kdj",
        "protocol": {
            "as_of_issue": as_of_issue,
            "history_fingerprint": history_fingerprint_value,
            "train_mode": train_mode,
            "train_window": train_window,
            "eval_window": len(indexes),
            "top_n": top_n,
            "universe_size": len(ranked_universe),
            "target_issues": [history_issue(history[index]) for index in indexes],
            "protocol_equality": {
                "same_universe": True,
                "same_target_issues": True,
                "same_top_n": True,
                "same_train_eval_protocol": True,
            },
        },
        "thresholds": (thresholds or DynamicKdjThresholds()).as_dict(),
        "dynamic": dynamic_summary,
        "static_baseline": static_summary,
        "null_baseline": null_summary,
        "rank_movement": movement,
        "offset_coverage": offset_coverage,
        "leakage_audit": leakage,
        "static_kdj_advisor_control": {"status": "skipped", "reason": STATIC_KDJ_ADVISOR_SKIP_REASON},
        "acceptance": acceptance_summary(
            static_summary=static_summary,
            dynamic_summary=dynamic_summary,
            movement=movement,
            leakage=leakage,
        ),
        "guardrail": (
            "Frozen historical response-surface test only. This does not claim lottery prediction; "
            "promotion requires later frozen or forward validation."
        ),
        "feature_matrix_cache": dict(getattr(ranked_universe, "cache_info", {})),
    }


def render_dynamic_kdj_report(payload: dict) -> str:
    protocol = payload["protocol"]
    dynamic = payload["dynamic"]
    static = payload["static_baseline"]
    null = payload["null_baseline"]
    acceptance = payload["acceptance"]
    movement = payload["rank_movement"]
    leakage = payload["leakage_audit"]
    offset = payload["offset_coverage"]
    rows = "\n".join(
        f"| {item['label']} | {item['top_100_hits']} | {item['top_1000_hits']} | {item['top_10000_hits']} | "
        f"{item['median_rank']} | {item['best_rank']} | {item['worst_rank']} | "
        f"{item['rank_quality']['tail_over_1000000_count']} | {item['reward']['objectiveScore']} |"
        for item in (dynamic, static, null)
    )
    return f"""# Dynamic KDJ Frozen Backtest

- Generated at: {payload["generated_at"]}
- As-of issue: `{protocol["as_of_issue"]}`
- Train mode/window: `{protocol["train_mode"]}` / {protocol["train_window"]}
- Eval window: {protocol["eval_window"]}
- Top-N: {protocol["top_n"]}
- Universe size: {protocol["universe_size"]}
- Acceptance: `{ "PASS" if acceptance["passed"] else "FAIL" }`

## Summary

| Label | Top100 | Top1000 | Top10000 | Median rank | Best rank | Worst rank | Tail >1000000 | Objective |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{rows}

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
