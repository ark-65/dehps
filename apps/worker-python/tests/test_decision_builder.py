from dehps.research.status import EvidenceDirection, HypothesisStatus, RejectionScope
from dehps.research_evidence.decision_builder import DecisionBuilder
from dehps.research_evidence.models import EvidenceAggregation, EvidenceStrength


def aggregation(**overrides):
    base = dict(
        hypothesis_key="hypothesis-1",
        evidence_count=12,
        supporting_count=0,
        contradicting_count=0,
        neutral_count=12,
        invalidating_count=0,
        overall_direction=EvidenceDirection.NEUTRAL,
        consistency=1.0,
        heterogeneity=0.0,
        evidence_strength=EvidenceStrength.INSUFFICIENT,
        forward_coverage=0,
        windows={"historical": 0, "frozen": 12, "future": 0},
        family_rejection_suggested=False,
        parameter_rejection_suggested=False,
        evidence_ids=tuple(range(1, 13)),
        evidence_keys=tuple(f"e{i}" for i in range(1, 13)),
        reason={},
    )
    base.update(overrides)
    return EvidenceAggregation(**base)


def test_decision_builder_is_inconclusive_without_forward_coverage() -> None:
    draft = DecisionBuilder().build(aggregation())

    assert draft.proposed_status == HypothesisStatus.INCONCLUSIVE
    assert draft.rejection_scope == RejectionScope.NONE


def test_decision_builder_can_suggest_family_rejection_after_consistent_forward_failure() -> None:
    draft = DecisionBuilder().build(
        aggregation(
            forward_coverage=2,
            family_rejection_suggested=True,
            evidence_strength=EvidenceStrength.WEAK,
        )
    )

    assert draft.proposed_status == HypothesisStatus.REJECTED
    assert draft.rejection_scope == RejectionScope.MECHANISM_FAMILY
    assert draft.reason["mechanism_signature"] == "ranking_model_disagreement"
