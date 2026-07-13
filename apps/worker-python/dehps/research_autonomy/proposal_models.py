from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Any


@dataclass(frozen=True)
class HypothesisProposal:
    proposal_key: str
    family_key: str
    title: str
    scientific_question: str
    statement: str
    mechanism: str
    null_hypothesis: str
    minimal_non_null: str
    invariants: tuple[str, ...]
    input_boundary: dict[str, Any]
    feature_contract: dict[str, Any]
    model_contract: dict[str, Any]
    baseline_contract: dict[str, Any]
    metric_contract: dict[str, Any]
    validation_protocol: dict[str, Any]
    failure_condition: dict[str, Any]
    self_deception_risks: tuple[str, ...]
    novelty_basis: tuple[str, ...]
    differs_from_rejected_families: tuple[str, ...]
    expected_information_gain: float
    estimated_compute_cost: float
    estimated_implementation_cost: float
    risk_level: str
    confidence: float

    def __post_init__(self) -> None:
        if not self.proposal_key.strip() or not self.family_key.strip():
            raise ValueError("proposal_key and family_key are required")
        if self.risk_level not in {"low", "medium", "high", "critical"}:
            raise ValueError(f"invalid proposal risk level: {self.risk_level}")
        for name in (
            "expected_information_gain",
            "estimated_compute_cost",
            "estimated_implementation_cost",
            "confidence",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=True, sort_keys=True, separators=(",", ":"))

    @property
    def content_hash(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def registry_preregistration(self) -> dict[str, Any]:
        return {
            "hypothesis_key": self.proposal_key,
            "family_key": self.family_key,
            "title": self.title,
            "statement": self.statement,
            "mechanism": self.mechanism,
            "null_hypothesis": self.null_hypothesis,
            "minimal_non_null": self.minimal_non_null,
            "invariants": list(self.invariants),
            "baseline_definition": self.baseline_contract,
            "metric_definition": self.metric_contract,
            "failure_condition": self.failure_condition,
            "self_deception_risk": list(self.self_deception_risks),
            "input_boundary": self.input_boundary,
            "feature_contract": self.feature_contract,
            "model_contract": self.model_contract,
            "validation_protocol": self.validation_protocol,
        }


@dataclass(frozen=True)
class NoveltyReport:
    is_novel: bool
    mechanism_distance: float
    feature_distance: float
    validation_distance: float
    closest_hypothesis_key: str | None
    closest_family_key: str | None
    duplicate_reasons: tuple[str, ...]
    rejected_reuse_detected: bool


@dataclass(frozen=True)
class ProposalScore:
    novelty: float
    falsifiability: float
    expected_information_gain: float
    implementation_cost: float
    compute_cost: float
    leakage_risk: float
    overfitting_risk: float
    forward_testability: float
    registry_compatibility: float
    total_score: float


@dataclass(frozen=True)
class ProposalValidationCheck:
    key: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class ProposalValidationReport:
    valid: bool
    checks: tuple[ProposalValidationCheck, ...]
    failure_reasons: tuple[str, ...]


@dataclass(frozen=True)
class RankedProposal:
    rank: int
    proposal: HypothesisProposal
    novelty_report: NoveltyReport
    proposal_score: ProposalScore
    validation_report: ProposalValidationReport


@dataclass(frozen=True)
class RejectedProposal:
    proposal_key: str
    mechanism: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ProposalEngineResult:
    selected: HypothesisProposal | None
    candidates: tuple[RankedProposal, ...]
    rejected_candidates: tuple[RejectedProposal, ...]
    context_fingerprint: str
    engine_version: str
    generated_at: datetime

    def canonical_json(self) -> str:
        return json.dumps(
            asdict(self),
            default=lambda value: value.isoformat() if isinstance(value, datetime) else str(value),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
