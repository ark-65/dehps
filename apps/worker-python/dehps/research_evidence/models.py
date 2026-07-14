from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from dehps.research.status import EvidenceDirection, HypothesisStatus, RejectionScope
from dehps.research_runtime.models import EvidenceSource


JsonObject = dict[str, Any]
ROUND25_SCHEMA_VERSION = "autonomous-evidence-evaluation-v1"


class EvidenceStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    INSUFFICIENT = "insufficient"
    INVALID = "invalid"


@dataclass(frozen=True)
class ArtifactValidationReport:
    valid: bool
    artifact_directory: str
    plan_key: str
    plan_fingerprint: str
    hypothesis_key: str
    manifest_hash: str
    checks: tuple[JsonObject, ...]
    failure_reasons: tuple[str, ...]
    loaded_artifacts: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class MetricObservation:
    metric: str
    value: float
    stage: str
    stratum: str
    baseline: str
    lift: float
    effect_size: float
    confidence_interval: JsonObject
    p_value: float
    adjusted_p_value: float
    top_100_hits: int
    top_1000_hits: int
    top_10000_hits: int
    mean_rank: float
    median_rank: float
    p95_rank: float
    worst_rank: float
    tail_over_750000: int
    tail_over_900000: int
    tail_over_1000000: int
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class StatisticalAssessment:
    direction: EvidenceDirection
    supports_null: bool
    supports_alternative: bool
    strength: EvidenceStrength
    reason: str


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_key: str
    hypothesis_key: str
    experiment_key: str
    metric: str
    value: float
    baseline: str
    lift: float
    effect_size: float
    confidence_interval: JsonObject
    p_value: float
    adjusted_p_value: float
    direction: EvidenceDirection
    supports_null: bool
    supports_alternative: bool
    stage: str
    stratum: str
    artifact_path: str
    content_hash: str
    summary: str
    metadata: JsonObject = field(default_factory=dict)
    registry_id: int | None = None
    evidence_source: EvidenceSource = EvidenceSource.RESEARCH

    def to_metrics(self) -> JsonObject:
        return {
            "metric": self.metric,
            "value": self.value,
            "baseline": self.baseline,
            "lift": self.lift,
            "effect_size": self.effect_size,
            "confidence_interval": self.confidence_interval,
            "p_value": self.p_value,
            "adjusted_p_value": self.adjusted_p_value,
            "supports_null": self.supports_null,
            "supports_alternative": self.supports_alternative,
            "stage": self.stage,
            "stratum": self.stratum,
            "evidence_source": self.evidence_source.value,
        }


@dataclass(frozen=True)
class EvidenceAggregation:
    hypothesis_key: str
    evidence_count: int
    supporting_count: int
    contradicting_count: int
    neutral_count: int
    invalidating_count: int
    overall_direction: EvidenceDirection
    consistency: float
    heterogeneity: float
    evidence_strength: EvidenceStrength
    forward_coverage: int
    windows: JsonObject
    family_rejection_suggested: bool
    parameter_rejection_suggested: bool
    evidence_ids: tuple[int, ...] = ()
    evidence_keys: tuple[str, ...] = ()
    reason: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionDraft:
    decision_key: str
    hypothesis_key: str
    proposed_status: HypothesisStatus
    evidence_ids: tuple[int, ...]
    evidence_keys: tuple[str, ...]
    reason: JsonObject
    summary: str
    decision_code: str
    rejection_scope: RejectionScope = RejectionScope.NONE
    rejection_reason: str | None = None
    reopen_condition: str | None = None
    family_action: str = "none"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat())

    def request_key(self) -> str:
        return f"decision-draft-{self.hypothesis_key}-{self.decision_key[:16]}"

    def payload(self) -> JsonObject:
        return {
            "hypothesis_key": self.hypothesis_key,
            "proposed_status": self.proposed_status.value,
            "evidence_ids": list(self.evidence_ids),
            "evidence_keys": list(self.evidence_keys),
            "reason": self.reason,
            "summary": self.summary,
            "decision_code": self.decision_code,
            "rejection_scope": self.rejection_scope.value,
            "rejection_reason": self.rejection_reason,
            "reopen_condition": self.reopen_condition,
            "family_action": self.family_action,
            "created_at": self.created_at,
            "schema_version": ROUND25_SCHEMA_VERSION,
        }


def json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def stable_json(value: Any) -> str:
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=json_default)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
