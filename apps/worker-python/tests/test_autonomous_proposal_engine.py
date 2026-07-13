from dehps.research_autonomy.proposal_engine import AutonomousHypothesisProposalEngine
from research_autonomy_fixtures import make_context


def test_generation_is_deterministic_for_context_and_engine_version() -> None:
    context = make_context()
    engine = AutonomousHypothesisProposalEngine(engine_version="test-v1")
    first = engine.propose(context, max_candidates=20)
    second = engine.propose(context, max_candidates=20)
    assert first == second
    assert first.canonical_json() == second.canonical_json()
    assert len(first.candidates) == 12
    assert first.selected == first.candidates[0].proposal
    assert first.selected.mechanism == "ranking_model_disagreement"


def test_no_qualified_proposal_returns_selected_none() -> None:
    context = make_context(boundary_status="failed")
    result = AutonomousHypothesisProposalEngine().propose(context)
    assert result.selected is None
    assert result.candidates == ()


def test_max_candidates_limits_ranked_output_to_one_selection() -> None:
    result = AutonomousHypothesisProposalEngine().propose(make_context(), max_candidates=3)
    assert len(result.candidates) == 3
    assert result.selected == result.candidates[0].proposal
