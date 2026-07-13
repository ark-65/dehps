from __future__ import annotations

from dataclasses import replace

from dehps.evaluation.models import BaselineComparison, EvaluationResult, LeakageReport
from dehps.evaluation.promotion import PromotionGate, PromotionReason


def _evaluation(**overrides: object) -> EvaluationResult:
    base = EvaluationResult(
        objective=10.0,
        top_100_hits=0,
        top_1000_hits=0,
        top_10000_hits=0,
        median_rank=500_000.0,
        p95_rank=800_000.0,
        worst_rank=800_000,
        tail_risk=1.0,
        tail_over_750000_count=1,
        tail_over_900000_count=0,
        tail_over_1000000_count=0,
        baseline_comparison=BaselineComparison(),
        leakage_report=LeakageReport(),
        config_hash="fixture",
    )
    return replace(base, **overrides)


def test_promotion_gate_accepts_only_higher_primary_objective_with_safe_tail() -> None:
    incumbent = _evaluation()
    candidate = _evaluation(objective=12.0, top_10000_hits=1, worst_rank=790_000, p95_rank=790_000.0)

    decision = PromotionGate().decide(candidate, incumbent)

    assert decision.accepted is True
    assert decision.reason_codes == (PromotionReason.ACCEPTED,)


def test_promotion_gate_rejects_higher_objective_when_tail_is_worse() -> None:
    incumbent = _evaluation()
    candidate = _evaluation(objective=12.0, top_10000_hits=1, tail_risk=2.0)

    decision = PromotionGate().decide(candidate, incumbent)

    assert decision.accepted is False
    assert PromotionReason.TAIL_RISK_WORSE in decision.reason_codes


def test_promotion_gate_fails_closed_for_overlap_leakage_invalid_and_missing_forward_evidence() -> None:
    incumbent = _evaluation()
    cases = (
        (_evaluation(baseline_comparison=BaselineComparison(acceptable=False)), PromotionReason.BASELINE_OVERLAP_TOO_HIGH),
        (_evaluation(leakage_report=LeakageReport(passed=False, failures=("target_in_train",))), PromotionReason.LEAKAGE_FAILURE),
        (_evaluation(valid=False), PromotionReason.INVALID_EXPERIMENT),
        (_evaluation(has_forward_evidence=False), PromotionReason.MISSING_FORWARD_EVIDENCE),
    )

    for candidate, reason in cases:
        decision = PromotionGate().decide(candidate, incumbent)
        assert decision.accepted is False
        assert reason in decision.reason_codes
