from dataclasses import replace

from dehps.research_autonomy.novelty import HypothesisNoveltyDetector
from research_autonomy_fixtures import make_context, make_proposal, rejected_family, rejected_hypothesis


def test_seed_only_and_epoch_only_changes_are_pseudo_innovation() -> None:
    context = make_context()
    proposal = make_proposal(context)
    detector = HypothesisNoveltyDetector()
    seed = detector.compare(replace(proposal, model_contract={**proposal.model_contract, "only_change": "seed"}), context)
    epoch = detector.compare(replace(proposal, model_contract={**proposal.model_contract, "only_change": "epochs"}), context)
    assert seed.is_novel is False and "seed_only_change" in seed.duplicate_reasons
    assert epoch.is_novel is False and "epoch_only_change" in epoch.duplicate_reasons


def test_rejected_mechanism_cannot_be_rewrapped_with_a_new_name_or_model() -> None:
    base = make_context()
    proposal = make_proposal(base)
    rejected = replace(
        base,
        rejected_hypotheses=(rejected_hypothesis(proposal.mechanism),),
        rejected_families=(rejected_family(proposal.mechanism),),
    )
    renamed = replace(proposal, title="A new sounding title", model_contract={**proposal.model_contract, "model_keys": ["ridge_kdj_adapter"]})
    report = HypothesisNoveltyDetector().compare(renamed, rejected)
    assert report.is_novel is False
    assert report.rejected_reuse_detected is True
    assert any("rejected_" in reason for reason in report.duplicate_reasons)
