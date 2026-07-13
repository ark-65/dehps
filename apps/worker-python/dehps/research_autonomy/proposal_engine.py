from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256

from dehps.research_autonomy.context import ResearchContext
from dehps.research_autonomy.generators import DEFAULT_GENERATORS, ProposalGenerator
from dehps.research_autonomy.novelty import HypothesisNoveltyDetector
from dehps.research_autonomy.proposal_models import (
    ProposalEngineResult,
    RankedProposal,
    RejectedProposal,
)
from dehps.research_autonomy.ranking import HypothesisProposalRanker
from dehps.research_autonomy.validation import HypothesisProposalValidator


DEFAULT_ENGINE_VERSION = "autonomous-hypothesis-proposal-v1"


class AutonomousHypothesisProposalEngine:
    def __init__(
        self,
        *,
        engine_version: str = DEFAULT_ENGINE_VERSION,
        generators: tuple[ProposalGenerator, ...] = DEFAULT_GENERATORS,
        novelty_detector: HypothesisNoveltyDetector | None = None,
        validator: HypothesisProposalValidator | None = None,
        ranker: HypothesisProposalRanker | None = None,
    ) -> None:
        if not engine_version.strip():
            raise ValueError("engine_version is required")
        self.engine_version = engine_version
        self.generators = generators
        self.novelty_detector = novelty_detector or HypothesisNoveltyDetector()
        self.validator = validator or HypothesisProposalValidator(self.novelty_detector)
        self.ranker = ranker or HypothesisProposalRanker()

    def propose(
        self,
        context: ResearchContext,
        *,
        max_candidates: int = 20,
    ) -> ProposalEngineResult:
        if not 1 <= max_candidates <= 20:
            raise ValueError("max_candidates must be between 1 and 20")
        generated = {
            proposal.proposal_key: proposal
            for generator in self.generators
            for proposal in generator.generate(context)
        }
        accepted = []
        rejected = []
        for proposal in sorted(generated.values(), key=lambda item: item.proposal_key):
            novelty = self.novelty_detector.compare(proposal, context)
            validation = self.validator.validate(proposal, context)
            reasons = tuple(sorted({*novelty.duplicate_reasons, *validation.failure_reasons}))
            if reasons:
                rejected.append(
                    RejectedProposal(
                        proposal_key=proposal.proposal_key,
                        mechanism=proposal.mechanism,
                        reasons=reasons,
                    )
                )
                continue
            score = self.ranker.score(proposal, novelty, validation)
            accepted.append((score.total_score, proposal.proposal_key, proposal, novelty, score, validation))
        accepted.sort(key=lambda item: (-item[0], item[1]))
        candidates = tuple(
            RankedProposal(
                rank=index,
                proposal=item[2],
                novelty_report=item[3],
                proposal_score=item[4],
                validation_report=item[5],
            )
            for index, item in enumerate(accepted[:max_candidates], start=1)
        )
        return ProposalEngineResult(
            selected=None if not candidates else candidates[0].proposal,
            candidates=candidates,
            rejected_candidates=tuple(sorted(rejected, key=lambda item: item.proposal_key)),
            context_fingerprint=context.fingerprint,
            engine_version=self.engine_version,
            generated_at=self._deterministic_timestamp(context.fingerprint),
        )

    def _deterministic_timestamp(self, context_fingerprint: str) -> datetime:
        digest = sha256(f"{context_fingerprint}:{self.engine_version}".encode("utf-8")).hexdigest()
        seconds = int(digest[:8], 16) % (20 * 365 * 24 * 60 * 60)
        return datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)
