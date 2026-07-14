from dehps.research.status import HypothesisStatus, RejectionScope
from dehps.research_evidence.decision_builder import DecisionBuilder
from test_decision_builder import aggregation
from dehps.research_evidence.validation import validate_decision_draft
from dehps.research_evidence.models import EvidenceStrength


def test_family_rejection_draft_contains_registry_required_rejection_fields() -> None:
    draft = DecisionBuilder().build(
        aggregation(
            forward_coverage=3,
            family_rejection_suggested=True,
            evidence_strength=EvidenceStrength.WEAK,
        )
    )

    assert draft.proposed_status == HypothesisStatus.REJECTED
    assert draft.rejection_scope == RejectionScope.MECHANISM_FAMILY
    assert validate_decision_draft(draft)["valid"] is True
    assert set(["seed", "epochs", "depth", "nearby_weights", "same_history_search_rounds", "rename"]).issubset(
        set(draft.reason["prohibited_parameter_only_changes"])
    )
