from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from dehps.research_evidence.models import ArtifactValidationReport, MetricObservation


class MetricsLoader:
    def load(self, report: ArtifactValidationReport) -> tuple[MetricObservation, ...]:
        if not report.valid:
            return ()
        artifacts = report.loaded_artifacts
        statistics = dict(artifacts["statistics"]["payload"])
        frozen_results = dict(artifacts["frozen_results"]["payload"])
        per_issue = [dict(item.get("payload", {})) for item in artifacts.get("per_issue_results", [])]
        frozen_per_issue = [item for item in per_issue if item.get("stage") == "frozen_validation"]

        aggregate = dict(frozen_results.get("aggregate") or {})
        aggregate_baselines = dict(aggregate.get("baselines") or {})
        observations: list[MetricObservation] = []
        for comparison in statistics.get("comparisons", []):
            if not isinstance(comparison, dict):
                continue
            stratum = str(comparison.get("stratum") or "")
            baseline = str(comparison.get("baseline") or "")
            baseline_aggregate = dict(dict(aggregate_baselines.get(stratum) or {}).get(baseline) or {})
            stage_metrics = _metric_summary(frozen_per_issue, stratum=stratum)
            observations.append(
                MetricObservation(
                    metric="paired_target_hit_lift",
                    value=float(comparison.get("paired_rank_difference") or 0.0),
                    stage="frozen_validation",
                    stratum=stratum,
                    baseline=baseline,
                    lift=float(baseline_aggregate.get("baseline_lift") or 0.0),
                    effect_size=float(comparison.get("effect_size") or 0.0),
                    confidence_interval=dict(comparison.get("bootstrap_confidence_interval") or {}),
                    p_value=float(dict(comparison.get("permutation_null") or {}).get("p_value") or 1.0),
                    adjusted_p_value=float(comparison.get("multiple_comparison_adjusted_p_value") or 1.0),
                    top_100_hits=int(stage_metrics["top_100_hits"]),
                    top_1000_hits=int(stage_metrics["top_1000_hits"]),
                    top_10000_hits=int(stage_metrics["top_10000_hits"]),
                    mean_rank=float(stage_metrics["mean_rank"]),
                    median_rank=float(stage_metrics["median_rank"]),
                    p95_rank=float(stage_metrics["p95_rank"]),
                    worst_rank=float(stage_metrics["worst_rank"]),
                    tail_over_750000=int(stage_metrics["tail_over_750000"]),
                    tail_over_900000=int(stage_metrics["tail_over_900000"]),
                    tail_over_1000000=int(stage_metrics["tail_over_1000000"]),
                    metadata={
                        "statistics_version": statistics.get("version"),
                        "comparison": comparison,
                        "stage_issue_count": len(frozen_per_issue),
                    },
                )
            )
        return tuple(observations)


def _metric_summary(per_issue: list[dict[str, Any]], *, stratum: str) -> dict[str, float | int]:
    values: dict[str, list[float]] = defaultdict(list)
    bools: dict[str, list[int]] = defaultdict(list)
    tails: dict[str, list[int]] = defaultdict(list)
    for item in per_issue:
        metrics = dict(dict(item.get("strata") or {}).get(stratum) or {})
        for key in ("top_100_hits", "top_1000_hits", "top_10000_hits"):
            bools[key].append(int(bool(metrics.get(key))))
        for key in ("mean_rank", "median_rank", "p95_rank", "worst_rank"):
            if key in metrics:
                values[key].append(float(metrics[key]))
        for key in ("tail_over_750000", "tail_over_900000", "tail_over_1000000"):
            tails[key].append(int(metrics.get(key) or 0))
    return {
        "top_100_hits": int(sum(bools["top_100_hits"])),
        "top_1000_hits": int(sum(bools["top_1000_hits"])),
        "top_10000_hits": int(sum(bools["top_10000_hits"])),
        "mean_rank": _mean(values["mean_rank"]),
        "median_rank": _mean(values["median_rank"]),
        "p95_rank": _mean(values["p95_rank"]),
        "worst_rank": _mean(values["worst_rank"]),
        "tail_over_750000": int(sum(tails["tail_over_750000"])),
        "tail_over_900000": int(sum(tails["tail_over_900000"])),
        "tail_over_1000000": int(sum(tails["tail_over_1000000"])),
    }


def _mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0
