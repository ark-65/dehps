from research_autonomy_fixtures import make_context, make_proposal


def test_proposal_schema_covers_registry_preregistration_fields() -> None:
    proposal = make_proposal(make_context())
    registry = proposal.registry_preregistration()
    for key in (
        "statement", "null_hypothesis", "minimal_non_null", "invariants",
        "baseline_definition", "metric_definition", "failure_condition", "self_deception_risk",
    ):
        assert registry[key]
    assert proposal.input_boundary["contains_future_information"] is False
    assert proposal.validation_protocol["random_split"] is False
    assert len(proposal.content_hash) == 64


def test_proposal_costs_confidence_and_risk_are_bounded() -> None:
    proposal = make_proposal()
    assert 0 <= proposal.expected_information_gain <= 1
    assert 0 <= proposal.estimated_compute_cost <= 1
    assert 0 <= proposal.confidence <= 1
    assert proposal.risk_level in {"low", "medium", "high", "critical"}
