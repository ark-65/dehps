from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from dehps.advisors.protocol import AdvisorCandidate
from dehps.models.frequency_ranker import FrequencyRankerConfig


@dataclass(frozen=True)
class RuntimeEvaluationOutcome:
    summaries: list[dict]
    control_summaries: list[dict]
    round_best: dict
    prior_best_summary: dict | None
    promotion_gate: dict
    improved: bool
    prefilter_isolation: dict


@dataclass(frozen=True)
class RuntimeEvaluationNormalizer:
    attach_candidate_source_metadata: Callable[..., None]
    attach_baseline_overlap: Callable[..., None]
    sort_key: Callable[[dict], tuple]
    control_experiment_summaries: Callable[..., list[dict]]
    prefilter_holdout_isolation_audit: Callable[..., dict]
    frozen_validation_promotion_gate: Callable[[dict, dict | None], dict]
    quarantine_historical_frozen_promotion: Callable[[dict], dict]

    def normalize(
        self,
        *,
        summaries: list[dict],
        diagnostic_sources: dict[str, tuple[FrequencyRankerConfig, ...]],
        advisor_candidates: Sequence[AdvisorCandidate],
        control_configs: Sequence[tuple[str, FrequencyRankerConfig]],
        universe_size: int,
        prefilter_target_issues: Sequence[str],
        prior_best_summary: dict | None,
    ) -> RuntimeEvaluationOutcome:
        self.attach_candidate_source_metadata(
            summaries,
            diagnostic_sources,
            advisor_candidates=advisor_candidates,
        )
        self.attach_baseline_overlap(
            summaries,
            control_configs,
            universe_size=universe_size,
        )
        summaries.sort(key=self.sort_key, reverse=True)
        control_summaries = self.control_experiment_summaries(
            summaries,
            control_configs,
        )
        round_best = summaries[0]
        evaluation_split = (
            round_best.get("evaluation_split")
            if isinstance(round_best.get("evaluation_split"), dict)
            else {}
        )
        prefilter_isolation = self.prefilter_holdout_isolation_audit(
            prefilter_target_issues=prefilter_target_issues,
            evaluation_split=evaluation_split,
        )
        if not prefilter_isolation["passed"]:
            raise RuntimeError(
                "prefilter holdout isolation failed: "
                f"frozen_overlap={prefilter_isolation['prefilter_frozen_issue_overlap']} "
                f"outside_split={prefilter_isolation['prefilter_outside_split_issues']}"
            )
        raw_improved = (
            prior_best_summary is None
            or self.sort_key(round_best) > self.sort_key(prior_best_summary)
        )
        promotion_gate = self.quarantine_historical_frozen_promotion(
            self.frozen_validation_promotion_gate(round_best, prior_best_summary)
        )
        return RuntimeEvaluationOutcome(
            summaries=summaries,
            control_summaries=control_summaries,
            round_best=round_best,
            prior_best_summary=prior_best_summary,
            promotion_gate=promotion_gate,
            improved=bool(raw_improved and promotion_gate["passed"]),
            prefilter_isolation=prefilter_isolation,
        )
