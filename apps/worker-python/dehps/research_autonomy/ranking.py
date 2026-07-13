from __future__ import annotations

from dehps.research_autonomy.proposal_models import (
    HypothesisProposal,
    NoveltyReport,
    ProposalScore,
    ProposalValidationReport,
)


class HypothesisProposalRanker:
    def score(
        self,
        proposal: HypothesisProposal,
        novelty: NoveltyReport,
        validation: ProposalValidationReport,
    ) -> ProposalScore:
        novelty_score = (
            (novelty.mechanism_distance + novelty.feature_distance + novelty.validation_distance) / 3
            if novelty.is_novel
            else 0.0
        )
        falsifiability = 1.0 if (
            proposal.failure_condition.get("rule")
            and proposal.failure_condition.get("reject_on_no_rank_tail_improvement") is True
        ) else 0.0
        leakage_risk = 0.0 if (
            proposal.input_boundary.get("contains_future_information") is False
            and proposal.validation_protocol.get("search_uses_frozen_validation") is False
        ) else 1.0
        overfitting_risk = 0.1 if (
            proposal.model_contract.get("random_seed_sweep") is False
            and proposal.model_contract.get("epoch_sweep") is False
            and proposal.validation_protocol.get("random_split") is False
        ) else 0.9
        forward_testability = 1.0 if (
            int(proposal.validation_protocol.get("forward_min_paired_issues") or 0) >= 20
            and proposal.validation_protocol.get("selection_uses_forward_outcomes") is False
        ) else 0.0
        registry_compatibility = 1.0 if validation.valid else 0.0
        total = (
            0.18 * novelty_score
            + 0.17 * falsifiability
            + 0.17 * proposal.expected_information_gain
            + 0.12 * forward_testability
            + 0.12 * registry_compatibility
            + 0.08 * (1 - proposal.estimated_implementation_cost)
            + 0.07 * (1 - proposal.estimated_compute_cost)
            + 0.05 * (1 - leakage_risk)
            + 0.04 * (1 - overfitting_risk)
        )
        return ProposalScore(
            novelty=round(novelty_score, 6),
            falsifiability=round(falsifiability, 6),
            expected_information_gain=round(proposal.expected_information_gain, 6),
            implementation_cost=round(proposal.estimated_implementation_cost, 6),
            compute_cost=round(proposal.estimated_compute_cost, 6),
            leakage_risk=round(leakage_risk, 6),
            overfitting_risk=round(overfitting_risk, 6),
            forward_testability=round(forward_testability, 6),
            registry_compatibility=round(registry_compatibility, 6),
            total_score=round(total, 9),
        )
