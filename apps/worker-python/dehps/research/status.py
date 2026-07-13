from __future__ import annotations

from enum import Enum


class HypothesisStatus(str, Enum):
    PROPOSED = "proposed"
    PREREGISTERED = "preregistered"
    RUNNING = "running"
    ACCEPTED_FOR_FOLLOWUP = "accepted_for_followup"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"
    INVALIDATED = "invalidated"


class HypothesisFamilyStatus(str, Enum):
    ACTIVE = "active"
    PARTIALLY_REJECTED = "partially_rejected"
    REJECTED = "rejected"
    EXHAUSTED = "exhausted"
    REOPENED = "reopened"


class ExperimentStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INVALIDATED = "invalidated"
    CANCELLED = "cancelled"


class EvidenceDirection(str, Enum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    NEUTRAL = "neutral"
    INVALIDATING = "invalidating"


class RejectionScope(str, Enum):
    NONE = "none"
    PARAMETER_REGION = "parameter_region"
    MECHANISM_FAMILY = "mechanism_family"


TERMINAL_EXPERIMENT_STATUSES = frozenset(
    {
        ExperimentStatus.COMPLETED,
        ExperimentStatus.FAILED,
        ExperimentStatus.INVALIDATED,
        ExperimentStatus.CANCELLED,
    }
)

ACTIVE_HYPOTHESIS_STATUSES = frozenset(
    {
        HypothesisStatus.PROPOSED,
        HypothesisStatus.PREREGISTERED,
        HypothesisStatus.RUNNING,
        HypothesisStatus.ACCEPTED_FOR_FOLLOWUP,
    }
)
