from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from dehps.evaluation.models import EvaluationResult
from dehps.evaluation.promotion import PromotionDecision
from dehps.models.frequency_ranker import FrequencyRankerConfig


@dataclass(frozen=True)
class TrainingRoundRequest:
    run_id: str
    round_index: int
    as_of_issue: str
    history_fingerprint: str
    objective_policy_version: str
    objective_policy_hash: str
    candidate_budget: int
    random_seed: int


@dataclass(frozen=True)
class CandidateProposal:
    config: FrequencyRankerConfig
    source_key: str
    protocol_version: str


@dataclass(frozen=True)
class CandidateSummary:
    config_hash: str
    source_key: str
    protocol_version: str
    metrics: Mapping[str, object]


@dataclass(frozen=True)
class EvaluatedRound:
    candidate_summaries: tuple[CandidateSummary, ...]
    selected_evaluation: EvaluationResult


@dataclass(frozen=True)
class TrainingRoundResult:
    candidate_summaries: tuple[CandidateSummary, ...]
    evaluation: EvaluationResult
    promotion_decision: PromotionDecision
    artifacts: tuple[str, ...]
    warnings: tuple[str, ...]
