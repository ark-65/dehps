from dehps.research_autonomy.novelty import HypothesisNoveltyDetector
from dehps.research_autonomy.ranking import HypothesisProposalRanker
from dehps.research_autonomy.validation import HypothesisProposalValidator
from research_autonomy_fixtures import make_context, make_proposal


def test_proposal_score_is_deterministic_and_rewards_falsifiability() -> None:
    context = make_context()
    proposal = make_proposal(context)
    novelty = HypothesisNoveltyDetector().compare(proposal, context)
    validation = HypothesisProposalValidator().validate(proposal, context)
    ranker = HypothesisProposalRanker()
    first = ranker.score(proposal, novelty, validation)
    second = ranker.score(proposal, novelty, validation)
    assert first == second
    assert first.falsifiability == 1.0
    assert first.leakage_risk == 0.0
    assert 0 < first.total_score <= 1
