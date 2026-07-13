from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from dehps.evaluation.models import EvaluationResult


class PromotionReason(StrEnum):
    ACCEPTED = "accepted"
    NO_INCUMBENT = "no_incumbent"
    INVALID_EXPERIMENT = "invalid_experiment"
    LEAKAGE_FAILURE = "leakage_failure"
    MISSING_FORWARD_EVIDENCE = "missing_forward_evidence"
    BASELINE_OVERLAP_TOO_HIGH = "baseline_overlap_too_high"
    OBJECTIVE_NOT_HIGHER = "objective_not_higher"
    TAIL_RISK_WORSE = "tail_risk_worse"
    PRIMARY_HIT_NOT_HIGHER = "primary_hit_not_higher"


@dataclass(frozen=True)
class PromotionDecision:
    accepted: bool
    reason_codes: tuple[str, ...]
    human_summary: str


class PromotionGate:
    def decide(
        self,
        candidate: EvaluationResult,
        incumbent: EvaluationResult | None,
    ) -> PromotionDecision:
        failures: list[str] = []
        if not candidate.valid:
            failures.append(PromotionReason.INVALID_EXPERIMENT)
        if not candidate.leakage_report.passed:
            failures.append(PromotionReason.LEAKAGE_FAILURE)
        if not candidate.has_forward_evidence:
            failures.append(PromotionReason.MISSING_FORWARD_EVIDENCE)
        if not candidate.baseline_comparison.acceptable:
            failures.append(PromotionReason.BASELINE_OVERLAP_TOO_HIGH)
        if failures:
            return self._decision(False, failures)
        if incumbent is None:
            return self._decision(True, [PromotionReason.NO_INCUMBENT])
        if candidate.objective <= incumbent.objective:
            failures.append(PromotionReason.OBJECTIVE_NOT_HIGHER)
        if not self._tail_not_worse(candidate, incumbent):
            failures.append(PromotionReason.TAIL_RISK_WORSE)
        if candidate.primary_score <= incumbent.primary_score:
            failures.append(PromotionReason.PRIMARY_HIT_NOT_HIGHER)
        return self._decision(not failures, failures or [PromotionReason.ACCEPTED])

    @staticmethod
    def _tail_not_worse(candidate: EvaluationResult, incumbent: EvaluationResult) -> bool:
        if candidate.worst_rank > incumbent.worst_rank:
            return False
        for candidate_value, incumbent_value in (
            (candidate.p95_rank, incumbent.p95_rank),
            (candidate.tail_risk, incumbent.tail_risk),
        ):
            if candidate_value is not None and incumbent_value is not None and candidate_value > incumbent_value:
                return False
        return (
            candidate.tail_over_750000_count <= incumbent.tail_over_750000_count
            and candidate.tail_over_900000_count <= incumbent.tail_over_900000_count
            and candidate.tail_over_1000000_count <= incumbent.tail_over_1000000_count
        )

    @staticmethod
    def _decision(accepted: bool, reasons: list[str]) -> PromotionDecision:
        codes = tuple(str(reason) for reason in reasons)
        summary = "promotion accepted" if accepted else "promotion rejected: " + ", ".join(codes)
        return PromotionDecision(accepted=accepted, reason_codes=codes, human_summary=summary)
