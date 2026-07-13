from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from dehps.research.status import (
    EvidenceDirection,
    ExperimentStatus,
    HypothesisFamilyStatus,
    HypothesisStatus,
    RejectionScope,
)


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class HypothesisFamily:
    id: int
    family_key: str
    title: str
    description: str
    mechanism: str
    status: HypothesisFamilyStatus
    rejection_scope: RejectionScope
    rejection_reason: str | None
    reopen_condition: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class Hypothesis:
    id: int
    hypothesis_key: str
    family_id: int
    parent_hypothesis_id: int | None
    title: str
    statement: str
    mechanism: str
    null_hypothesis: str
    minimal_non_null: str
    invariants: list[Any]
    baseline_definition: JsonObject
    metric_definition: JsonObject
    failure_condition: JsonObject
    self_deception_risk: list[Any]
    status: HypothesisStatus
    rejection_scope: RejectionScope
    rejection_reason: str | None
    reopen_condition: str | None
    created_at: datetime
    updated_at: datetime
    preregistered_at: datetime | None
    started_at: datetime | None
    resolved_at: datetime | None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class HypothesisExperiment:
    id: int
    hypothesis_id: int
    experiment_key: str
    experiment_type: str
    external_run_id: str | None
    training_run_id: str | None
    training_round_index: int | None
    report_path: str | None
    artifact_paths: list[str]
    config_snapshot: JsonObject
    status: ExperimentStatus
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class HypothesisEvidence:
    id: int
    hypothesis_id: int
    experiment_id: int | None
    evidence_type: str
    direction: EvidenceDirection
    summary: str
    metrics: JsonObject
    artifact_path: str | None
    content_hash: str | None
    observed_at: datetime
    created_at: datetime
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class HypothesisDecision:
    id: int
    hypothesis_id: int | None
    family_id: int | None
    previous_status: str
    new_status: str
    decision_code: str
    summary: str
    reason: JsonObject
    evidence_ids: list[int]
    decided_by: str
    decided_at: datetime
    created_at: datetime
