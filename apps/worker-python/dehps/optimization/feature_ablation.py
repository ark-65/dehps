from __future__ import annotations

import json
import time
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Mapping

from dehps.config import ROOT_DIR
from dehps.models.frequency_ranker import FrequencyRankerConfig, HistoryDraw, history_issue
from dehps.optimization.control_experiments import (
    TrainMode,
    evaluate_config_summaries,
    objective_score,
    tail_risk_penalty,
    target_indexes,
    validate_positive_int,
)
from dehps.optimization.walk_forward import (
    CONFIG_WEIGHT_FIELDS,
    build_ranked_universe,
    fingerprint_history,
    normalize_worker_count,
)


FEATURE_FAMILIES: Mapping[str, tuple[str, ...]] = {
    "structural": (
        "structural_weight",
    ),
    "frequency": (
        "frequency_weight",
        "short_hot_frequency_weight",
    ),
    "omission": (
        "omission_weight",
        "red_omission_shape_weight",
        "sum_span_omission_weight",
        "long_omission_cooldown_weight",
    ),
    "recent_state": (
        "previous_consecutive_weight",
        "previous_overlap_weight",
        "previous_parity_shape_weight",
        "dynamic_parity_transition_weight",
        "previous_zone_shape_weight",
        "recent_neighbor_weight",
        "lagged_consecutive_weight",
        "recent_gap_shape_weight",
        "recent_sum_span_weight",
    ),
    "shape_trend": (
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
    ),
    "temporal_stability": (
        "consecutive_trend_weight",
        "repeat_trend_weight",
        "stable_range_weight",
        "weekday_trend_weight",
    ),
}

ABLATION_GUARDRAIL = (
    "Diagnostic only: leave-one-feature-family-out results do not authorize weight changes, "
    "hypothesis decisions, strategy promotion, or production mutation. Forward unseen evidence remains required."
)


def validate_feature_families(
    families: Mapping[str, tuple[str, ...]] = FEATURE_FAMILIES,
) -> dict[str, tuple[str, ...]]:
    expected = set(CONFIG_WEIGHT_FIELDS)
    counts: dict[str, int] = {}
    for fields in families.values():
        for field in fields:
            counts[field] = counts.get(field, 0) + 1
    missing = tuple(sorted(expected - set(counts)))
    unknown = tuple(sorted(set(counts) - expected))
    duplicates = tuple(sorted(field for field, count in counts.items() if count != 1))
    if missing or unknown or duplicates:
        raise ValueError(
            "invalid feature families: "
            f"missing={list(missing)} unknown={list(unknown)} duplicates={list(duplicates)}"
        )
    return {
        "missing": missing,
        "unknown": unknown,
        "duplicates": duplicates,
    }


validate_feature_families()


def feature_ablation_configs(
    base: FrequencyRankerConfig,
) -> tuple[tuple[str, FrequencyRankerConfig], ...]:
    configs: list[tuple[str, FrequencyRankerConfig]] = [("full_model", base)]
    for family, fields in FEATURE_FAMILIES.items():
        configs.append(
            (
                f"without_{family}",
                replace(base, **{field: 0.0 for field in fields}),
            )
        )
    return tuple(configs)


def _red5_metrics(summary: dict) -> dict:
    red5 = summary.get("red5") if isinstance(summary.get("red5"), dict) else {}
    return {
        "top_100_hits": int(red5.get("top_100_hits") or 0),
        "top_1000_hits": int(red5.get("top_1000_hits") or 0),
        "top_10000_hits": int(red5.get("top_10000_hits") or 0),
        "median_rank": red5.get("median_rank"),
        "best_rank": red5.get("best_rank"),
    }


def summary_metrics(summary: dict) -> dict:
    return {
        "evaluated_draws": int(summary.get("evaluated_draws") or summary.get("window") or 0),
        "top_100_hits": int(summary.get("top_100_hits") or 0),
        "top_1000_hits": int(summary.get("top_1000_hits") or 0),
        "top_10000_hits": int(summary.get("top_10000_hits") or 0),
        "median_rank": summary.get("median_rank"),
        "best_rank": summary.get("best_rank"),
        "worst_rank": summary.get("worst_rank"),
        "objective_score": objective_score(summary),
        "tail_risk_penalty": tail_risk_penalty(summary),
        "red5": _red5_metrics(summary),
    }


def _numeric_delta(value, baseline):
    if not isinstance(value, int | float) or not isinstance(baseline, int | float):
        return None
    return round(float(value) - float(baseline), 6)


def metric_delta(metrics: dict, baseline: dict) -> dict:
    delta = {
        key: _numeric_delta(metrics.get(key), baseline.get(key))
        for key in (
            "top_100_hits",
            "top_1000_hits",
            "top_10000_hits",
            "median_rank",
            "best_rank",
            "worst_rank",
            "objective_score",
            "tail_risk_penalty",
        )
    }
    delta["red5"] = {
        key: _numeric_delta(metrics["red5"].get(key), baseline["red5"].get(key))
        for key in ("top_100_hits", "top_1000_hits", "top_10000_hits", "median_rank", "best_rank")
    }
    return delta


def run_feature_ablation(
    *,
    history: list[HistoryDraw],
    base_config: FrequencyRankerConfig,
    train_mode: TrainMode,
    train_window: int,
    eval_window: int,
    top_n: int,
    workers: int | None = 1,
    ranked_universe=None,
) -> dict:
    started = time.time()
    top_n = validate_positive_int("top_n", top_n)
    worker_count = normalize_worker_count(workers)
    matrix = ranked_universe if ranked_universe is not None else build_ranked_universe()
    labeled_configs = feature_ablation_configs(base_config)
    summaries = evaluate_config_summaries(
        history=history,
        ranked_universe=matrix,
        labeled_configs=labeled_configs,
        train_window=train_window,
        train_mode=train_mode,
        eval_window=eval_window,
        top_n=top_n,
        workers=worker_count,
    )
    full = summaries[0]
    full_issues = tuple(str(row.get("issue") or "") for row in full.get("target_results") or ())
    full_metrics = summary_metrics(full)
    full_frozen = full.get("frozen_validation") if isinstance(full.get("frozen_validation"), dict) else {}
    full_frozen_metrics = summary_metrics(full_frozen)
    comparisons = []
    for summary in summaries[1:]:
        issues = tuple(str(row.get("issue") or "") for row in summary.get("target_results") or ())
        if issues != full_issues:
            raise RuntimeError(f"ablation target mismatch for {summary.get('label')}")
        family = str(summary["label"]).removeprefix("without_")
        metrics = summary_metrics(summary)
        frozen = summary.get("frozen_validation") if isinstance(summary.get("frozen_validation"), dict) else {}
        frozen_metrics = summary_metrics(frozen)
        comparisons.append(
            {
                "family": family,
                "label": summary["label"],
                "removed_fields": list(FEATURE_FAMILIES[family]),
                "config_hash": summary["config_hash"],
                "metrics": metrics,
                "delta_vs_full_model": metric_delta(metrics, full_metrics),
                "frozen_metrics": frozen_metrics,
                "frozen_delta_vs_full_model": metric_delta(frozen_metrics, full_frozen_metrics),
                "target_issues_equal": True,
                "summary": summary,
            }
        )
    indexes = list(target_indexes(history_len=len(history), train_window=train_window, eval_window=eval_window))
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "diagnostic_only",
        "promotion_allowed": False,
        "guardrail": ABLATION_GUARDRAIL,
        "protocol": {
            "as_of_issue": history_issue(history[-1]),
            "history_fingerprint": fingerprint_history(history),
            "train_mode": train_mode,
            "train_window": train_window,
            "eval_window": len(indexes),
            "top_n": top_n,
            "universe_size": len(matrix),
            "target_issues": [history_issue(history[index]) for index in indexes],
            "same_target_issues": all(item["target_issues_equal"] for item in comparisons),
            "frozen_window": int(full_frozen.get("window") or 0),
        },
        "feature_families": {family: list(fields) for family, fields in FEATURE_FAMILIES.items()},
        "family_validation": validate_feature_families(),
        "base_config": asdict(base_config),
        "full_model": {
            "config_hash": full["config_hash"],
            "metrics": full_metrics,
            "frozen_metrics": full_frozen_metrics,
            "summary": full,
        },
        "ablations": comparisons,
        "feature_matrix_cache": dict(getattr(matrix, "cache_info", {})),
        "elapsed_seconds": round(time.time() - started, 3),
    }


def render_feature_ablation_report(payload: dict) -> str:
    def formatted_delta(value) -> str:
        return "n/a" if value is None else f"{value:+g}"

    rows = []
    for item in payload["ablations"]:
        metrics = item["metrics"]
        delta = item["delta_vs_full_model"]
        frozen = item["frozen_metrics"]
        frozen_delta = item["frozen_delta_vs_full_model"]
        rows.append(
            f"| {item['family']} | {metrics['top_10000_hits']} ({formatted_delta(delta['top_10000_hits'])}) | "
            f"{metrics['red5']['top_10000_hits']} ({formatted_delta(delta['red5']['top_10000_hits'])}) | "
            f"{metrics['median_rank']} ({formatted_delta(delta['median_rank'])}) | "
            f"{metrics['objective_score']:.6f} ({formatted_delta(delta['objective_score'])}) | "
            f"{frozen['objective_score']:.6f} ({formatted_delta(frozen_delta['objective_score'])}) |"
        )
    protocol = payload["protocol"]
    return f"""# DEHPS Feature-Family Ablation

- Generated at: {payload['generated_at']}
- Status: `{payload['status']}`
- Promotion allowed: `{str(payload['promotion_allowed']).lower()}`
- As-of issue: `{protocol['as_of_issue']}`
- Train mode/window: `{protocol['train_mode']}` / {protocol['train_window']}
- Evaluation/frozen windows: {protocol['eval_window']} / {protocol['frozen_window']}
- Top-N / universe: {protocol['top_n']} / {protocol['universe_size']}
- Identical target issues: `{str(protocol['same_target_issues']).lower()}`

Positive hit/objective deltas mean the ablated model was higher than the full model. Positive rank and tail-risk deltas mean it was worse.

| Removed family | Top10000 (delta) | Red5 Top10000 (delta) | Median rank (delta) | Objective (delta) | Frozen objective (delta) |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

## Family contract

```json
{json.dumps(payload['feature_families'], ensure_ascii=False, indent=2, sort_keys=True)}
```

## Guardrail

{payload['guardrail']}
"""


def write_feature_ablation_artifacts(payload: dict, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    key = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"feature-ablation-{key}.json"
    report_path = output_dir / f"feature-ablation-{key}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    report_path.write_text(render_feature_ablation_report(payload))
    return json_path, report_path


def default_output_dir() -> Path:
    return ROOT_DIR / "data/output/optimization"
