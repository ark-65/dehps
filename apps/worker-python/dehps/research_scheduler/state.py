from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Any


ROUND26_SCHEMA_VERSION = "autonomous-research-scheduler-v1"


class QueueStatus(str, Enum):
    PROPOSAL = "proposal"
    PLANNING = "planning"
    ENGINEERING = "engineering"
    OPERATOR = "operator"
    WAITING_FORWARD = "waiting_forward"
    REVIEW = "review"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class ResearchAction(str, Enum):
    CREATE_PROPOSAL_REQUEST = "create_proposal_request"
    CREATE_PLANNING_REQUEST = "create_planning_request"
    CREATE_ENGINEERING_REQUEST = "create_engineering_request"
    CREATE_OPERATOR_REQUEST = "create_operator_request"
    CREATE_REVIEW_REQUEST = "create_review_request"
    DISCOVER_PATTERNS = "discover_patterns"
    SCREEN_PATTERNS = "screen_patterns"
    SYNTHESIZE_FEATURES = "synthesize_features"
    SYNTHESIZE_STRATEGIES = "synthesize_strategies"
    SUBMIT_PATTERN_HYPOTHESIS = "submit_pattern_hypothesis"
    WAIT_FORWARD_PATTERN = "wait_forward_pattern"
    WAIT_FORWARD = "wait_forward"
    BLOCK = "block"
    STOP = "stop"
    CONTINUE_EXISTING = "continue_existing"


REQUEST_ACTIONS = frozenset(
    {
        ResearchAction.CREATE_PROPOSAL_REQUEST,
        ResearchAction.CREATE_PLANNING_REQUEST,
        ResearchAction.CREATE_ENGINEERING_REQUEST,
        ResearchAction.CREATE_OPERATOR_REQUEST,
        ResearchAction.CREATE_REVIEW_REQUEST,
        ResearchAction.DISCOVER_PATTERNS,
        ResearchAction.SCREEN_PATTERNS,
        ResearchAction.SYNTHESIZE_FEATURES,
        ResearchAction.SYNTHESIZE_STRATEGIES,
        ResearchAction.SUBMIT_PATTERN_HYPOTHESIS,
    }
)

OPEN_QUEUE_STATUSES = frozenset(
    {
        QueueStatus.PROPOSAL,
        QueueStatus.PLANNING,
        QueueStatus.ENGINEERING,
        QueueStatus.OPERATOR,
        QueueStatus.WAITING_FORWARD,
        QueueStatus.REVIEW,
    }
)

TERMINAL_AGENT_REQUEST_STATUSES = frozenset(
    {"rejected", "cancelled", "completed", "failed", "invalidated"}
)


@dataclass(frozen=True)
class SchedulerQueueItem:
    queue_key: str
    queue_status: QueueStatus
    action: ResearchAction
    priority_score: float
    context_fingerprint: str
    reason: dict[str, Any]
    budget: dict[str, Any]
    policy: dict[str, Any]
    target_hypothesis_key: str | None = None
    target_family_key: str | None = None
    target_experiment_key: str | None = None
    request_key: str | None = None
    created_by: str = "research:scheduler"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        return self.queue_status in OPEN_QUEUE_STATUSES


@dataclass(frozen=True)
class OpenAgentRequest:
    request_key: str
    request_type: str
    status: str
    requested_by_role: str
    requested_by: str
    title: str
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TrainingStatusSnapshot:
    latest_run_id: str | None
    latest_round_index: int | None
    active: bool
    source_training_run_ids: tuple[str, ...]
    failure_count: int
    sequential_null_status: dict[str, Any]
    forward_evidence_status: dict[str, Any]


@dataclass(frozen=True)
class SchedulerState:
    context_fingerprint: str
    active_hypotheses: tuple[Any, ...]
    rejected_families: tuple[Any, ...]
    recent_experiments: tuple[Any, ...]
    recent_evidence: tuple[Any, ...]
    open_queue: tuple[SchedulerQueueItem, ...]
    open_agent_requests: tuple[OpenAgentRequest, ...]
    training_status: TrainingStatusSnapshot
    pattern_discovery: dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_running_work(self) -> bool:
        return bool(self.open_agent_requests or self.open_queue)


@dataclass(frozen=True)
class NextResearchAction:
    action: ResearchAction
    queue_status: QueueStatus
    summary: str
    reason: dict[str, Any]
    priority_score: float
    context_fingerprint: str
    budget: dict[str, Any]
    policy: dict[str, Any]
    target_hypothesis_key: str | None = None
    target_family_key: str | None = None
    target_experiment_key: str | None = None
    existing_queue_key: str | None = None
    existing_request_key: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def creates_request(self) -> bool:
        return self.action in REQUEST_ACTIONS

    @property
    def queue_key(self) -> str:
        if self.existing_queue_key:
            return self.existing_queue_key
        digest = stable_hash(
            {
                "schema": ROUND26_SCHEMA_VERSION,
                "action": self.action.value,
                "status": self.queue_status.value,
                "context": self.context_fingerprint,
                "hypothesis": self.target_hypothesis_key,
                "family": self.target_family_key,
                "experiment": self.target_experiment_key,
            }
        )[:16]
        return f"scheduler-{self.action.value}-{digest}"

    @property
    def request_key(self) -> str:
        digest = stable_hash(
            {
                "queue_key": self.queue_key,
                "action": self.action.value,
                "context": self.context_fingerprint,
            }
        )[:16]
        return f"research-scheduler-{digest}"

    def queue_item(self, *, created_by: str) -> SchedulerQueueItem:
        return SchedulerQueueItem(
            queue_key=self.queue_key,
            queue_status=self.queue_status,
            action=self.action,
            priority_score=self.priority_score,
            context_fingerprint=self.context_fingerprint,
            reason=dict(self.reason),
            budget=dict(self.budget),
            policy=dict(self.policy),
            target_hypothesis_key=self.target_hypothesis_key,
            target_family_key=self.target_family_key,
            target_experiment_key=self.target_experiment_key,
            request_key=self.existing_request_key,
            created_by=created_by,
            metadata={"schema_version": ROUND26_SCHEMA_VERSION},
        )

    def payload(self) -> dict[str, Any]:
        return {
            "queue_key": self.queue_key,
            "action": self.action.value,
            "queue_status": self.queue_status.value,
            "reason": dict(self.reason),
            "context_fingerprint": self.context_fingerprint,
            "budget": dict(self.budget),
            "policy": dict(self.policy),
            "priority_score": round(float(self.priority_score), 6),
            "target_hypothesis_key": self.target_hypothesis_key,
            "target_family_key": self.target_family_key,
            "target_experiment_key": self.target_experiment_key,
            "non_goals": [
                "do_not_execute_experiment",
                "do_not_modify_code",
                "do_not_modify_registry",
                "do_not_modify_training",
                "do_not_promote_production",
                "do_not_execute_pattern_strategy_in_production",
            ],
        }


def jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def stable_json(value: Any) -> str:
    return json.dumps(jsonable(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return sha256(stable_json(value).encode("utf-8")).hexdigest()
