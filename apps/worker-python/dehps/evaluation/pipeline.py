from __future__ import annotations

from dehps.evaluation.models import BaselineComparison, EvaluationResult, LeakageReport


class EvaluationPipeline:
    """Normalizes already-computed training facts without making promotion decisions."""

    def from_frozen_summary(
        self,
        summary: dict,
        *,
        valid: bool = True,
        leakage_report: LeakageReport | None = None,
        has_forward_evidence: bool = True,
        baseline_acceptable: bool = True,
    ) -> EvaluationResult:
        validation = summary.get("frozen_validation") if isinstance(summary.get("frozen_validation"), dict) else {}
        quality = validation.get("rank_quality") if isinstance(validation.get("rank_quality"), dict) else {}
        reward = validation.get("reward") if isinstance(validation.get("reward"), dict) else {}
        overlap = validation.get("baseline_overlap") if isinstance(validation.get("baseline_overlap"), dict) else {}
        worst_rank = int(validation.get("worst_rank") or 0)
        return EvaluationResult(
            objective=float(reward.get("objectiveScore") or 0.0),
            top_100_hits=int(validation.get("top_100_hits") or 0),
            top_1000_hits=int(validation.get("top_1000_hits") or 0),
            top_10000_hits=int(validation.get("top_10000_hits") or 0),
            median_rank=float(validation.get("median_rank") or 0.0),
            p95_rank=float(quality["p95_rank"]) if quality.get("p95_rank") is not None else None,
            worst_rank=worst_rank,
            tail_risk=float(quality["tail_risk_penalty"]) if quality.get("tail_risk_penalty") is not None else None,
            tail_over_750000_count=int(quality.get("tail_over_750000_count") or 0),
            tail_over_900000_count=int(quality.get("tail_over_900000_count") or 0),
            tail_over_1000000_count=int(quality.get("tail_over_1000000_count") or 0),
            baseline_comparison=BaselineComparison(
                unique_reward=float(overlap.get("unique_reward") or 0.0),
                overlap_penalty=float(overlap.get("overlap_penalty") or 0.0),
                acceptable=baseline_acceptable,
            ),
            leakage_report=leakage_report or LeakageReport(),
            valid=valid,
            has_forward_evidence=has_forward_evidence,
            config_hash=str(summary.get("config_hash") or ""),
        )
