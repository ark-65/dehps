from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from dehps.advisors.registry import AdvisorRegistry
from dehps.evaluation.promotion import PromotionDecision, PromotionGate
from dehps.training.context import FrozenTrainingContext
from dehps.training.models import (
    CandidateProposal,
    EvaluatedRound,
    TrainingRoundRequest,
    TrainingRoundResult,
)


class TrainingRepository(Protocol):
    def load_context(self, request: TrainingRoundRequest) -> FrozenTrainingContext: ...
    def save_round(self, request: TrainingRoundRequest, result: TrainingRoundResult) -> None: ...


class CandidateSearchPolicy(Protocol):
    def propose(
        self,
        request: TrainingRoundRequest,
        context: FrozenTrainingContext,
    ) -> Sequence[CandidateProposal]: ...


class RoundEvaluationPipeline(Protocol):
    def evaluate(
        self,
        request: TrainingRoundRequest,
        context: FrozenTrainingContext,
        candidates: tuple[CandidateProposal, ...],
    ) -> EvaluatedRound: ...


class TrainingEventPublisher(Protocol):
    def publish(self, request: TrainingRoundRequest, result: TrainingRoundResult) -> None: ...


class ArtifactWriter(Protocol):
    def write(
        self,
        request: TrainingRoundRequest,
        evaluated: EvaluatedRound,
        decision: PromotionDecision,
    ) -> Sequence[str]: ...


@dataclass(frozen=True)
class TrainingDependencies:
    repository: TrainingRepository
    candidate_search: CandidateSearchPolicy
    advisor_registry: AdvisorRegistry
    evaluator: RoundEvaluationPipeline
    promotion_gate: PromotionGate
    event_publisher: TrainingEventPublisher
    artifact_writer: ArtifactWriter
