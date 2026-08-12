from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import date, datetime, timezone
from enum import Enum
from hashlib import sha256
from types import MappingProxyType
from typing import Any

RESEARCH_OS_SCHEMA_VERSION = "research-os-control-plane-v1"


class ResearchOSValidationError(ValueError):
    """Raised when a control-plane artifact cannot be trusted."""


class ObjectiveClass(str, Enum):
    PREDICTION_QUALITY = "prediction_quality"
    STRUCTURAL_DECISION_UTILITY = "structural_decision_utility"
    RUNTIME_CAPABILITY = "runtime_capability"
    KNOWLEDGE_QUALITY = "knowledge_quality"
    MAINTENANCE_INTEGRITY = "maintenance_integrity"


class GoalStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    RETIRED = "retired"


class TaskLane(str, Enum):
    PRODUCTION = "production"
    RESEARCH = "research"
    MAINTENANCE = "maintenance"


class TaskStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    READY = "ready"
    DEPENDENCY_WAIT = "dependency_wait"
    EXTERNAL_WAIT = "external_wait"
    APPROVAL_WAIT = "approval_wait"
    BLOCKED_BY_CONTRACT = "blocked_by_contract"
    COMPLETED = "completed"
    FAILED = "failed"
    SUPERSEDED = "superseded"


TERMINAL_TASK_STATUSES = frozenset(
    {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SUPERSEDED}
)
DECLARED_TASK_STATUSES = frozenset(
    {
        TaskStatus.DRAFT,
        TaskStatus.RUNNING,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.SUPERSEDED,
    }
)


class CompletionClassification(str, Enum):
    CODE_COMPLETE = "CODE_COMPLETE"
    INTEGRATION_PENDING = "INTEGRATION_PENDING"
    INTEGRATED = "INTEGRATED"
    VALIDATED_IN_MAINLINE = "VALIDATED_IN_MAINLINE"
    COMPLETE = "COMPLETE"


class DependencyType(str, Enum):
    TASK = "task"
    ARTIFACT = "artifact"
    EVIDENCE = "evidence"
    EXTERNAL_EVENT = "external_event"
    AUTHORITY = "authority"


def _required_text(value: Any, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ResearchOSValidationError(f"{field_name} must be a non-empty string")
    return normalized


def _mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ResearchOSValidationError(f"{field_name} must be an object")
    return value


def _enum(enum_type: type[Enum], value: Any, *, field_name: str):
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(str(item.value) for item in enum_type)
        raise ResearchOSValidationError(
            f"invalid {field_name} {value!r}; allowed: {allowed}"
        ) from exc


def jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [jsonable(item) for item in value]
        return sorted(items) if isinstance(value, (set, frozenset)) else items
    return value


def stable_json(value: Any) -> str:
    return json.dumps(jsonable(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return sha256(stable_json(value).encode("utf-8")).hexdigest()


def _canonical_object(value: Any, *, field_name: str) -> str:
    if value is None:
        value = {}
    _mapping(value, field_name=field_name)
    return stable_json(value)


def _canonical_timestamp(value: Any, *, field_name: str) -> str | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResearchOSValidationError(f"{field_name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ResearchOSValidationError(f"{field_name} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _decoded_object(value: str) -> dict[str, Any]:
    decoded = json.loads(value)
    assert isinstance(decoded, dict)
    return decoded


@dataclass(frozen=True)
class Goal:
    """Immutable Goal definition. Lifecycle state is stored in GoalState."""

    goal_key: str
    semantic_version: str
    objective_class: ObjectiveClass
    success_evidence: tuple[str, ...]
    owner_lane: TaskLane
    question: str = ""
    baseline_metric_manifest: str = "{}"
    target_metric_manifest: str = "{}"
    guardrails: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Goal:
        value = _mapping(value, field_name="goal")
        success = value.get("success_evidence")
        if not isinstance(success, list) or not success:
            raise ResearchOSValidationError("goal success_evidence must be a non-empty array")
        guardrails = value.get("guardrails")
        if guardrails is None:
            guardrails = []
        if not isinstance(guardrails, list):
            raise ResearchOSValidationError("goal guardrails must be an array")
        return cls(
            goal_key=_required_text(value.get("goal_key"), field_name="goal_key"),
            semantic_version=_required_text(
                value.get("semantic_version", "1.0.0"), field_name="goal semantic_version"
            ),
            objective_class=_enum(
                ObjectiveClass,
                value.get("objective_class"),
                field_name="objective_class",
            ),
            success_evidence=tuple(
                _required_text(item, field_name="success_evidence item") for item in success
            ),
            owner_lane=_enum(TaskLane, value.get("owner_lane"), field_name="owner_lane"),
            question=str(value.get("question") or "").strip(),
            baseline_metric_manifest=_canonical_object(
                value.get("baseline_metric_manifest", value.get("baseline")),
                field_name="baseline_metric_manifest",
            ),
            target_metric_manifest=_canonical_object(
                value.get("target_metric_manifest", value.get("target")),
                field_name="target_metric_manifest",
            ),
            guardrails=tuple(str(item) for item in guardrails),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_key": self.goal_key,
            "semantic_version": self.semantic_version,
            "objective_class": self.objective_class.value,
            "success_evidence": list(self.success_evidence),
            "owner_lane": self.owner_lane.value,
            "question": self.question,
            "baseline_metric_manifest": _decoded_object(self.baseline_metric_manifest),
            "target_metric_manifest": _decoded_object(self.target_metric_manifest),
            "guardrails": list(self.guardrails),
        }

    @property
    def artifact_digest(self) -> str:
        return stable_hash(
            {
                "schema": RESEARCH_OS_SCHEMA_VERSION,
                "artifact_type": "goal_definition",
                "definition": self.to_dict(),
            }
        )


@dataclass(frozen=True)
class GoalState:
    goal_digest: str
    status: GoalStatus
    retired_at: str | None = None
    superseded_by_goal_digest: str | None = None


@dataclass(frozen=True)
class TaskDependency:
    dependency_type: DependencyType
    target_key: str
    required_status: str = "available"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> TaskDependency:
        value = _mapping(value, field_name="task dependency")
        return cls(
            dependency_type=_enum(
                DependencyType,
                value.get("dependency_type"),
                field_name="dependency_type",
            ),
            target_key=_required_text(value.get("target_key"), field_name="dependency target_key"),
            required_status=_required_text(
                value.get("required_status", "available"),
                field_name="dependency required_status",
            ),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "dependency_type": self.dependency_type.value,
            "target_key": self.target_key,
            "required_status": self.required_status,
        }


@dataclass(frozen=True)
class Task:
    """Immutable Task definition. Resolver state is stored separately."""

    task_key: str
    goal_key: str
    goal_digest: str
    task_type: str
    lane: TaskLane
    dependencies: tuple[TaskDependency, ...] = ()
    priority: int = 0
    input_artifact_digests: tuple[str, ...] = ()
    requested_capability: str | None = None
    metric_contract: str = "{}"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], *, goal_digest: str = "") -> Task:
        value = _mapping(value, field_name="task")
        raw_dependencies = value.get("dependencies")
        if raw_dependencies is None:
            raw_dependencies = []
        if not isinstance(raw_dependencies, list):
            raise ResearchOSValidationError("task dependencies must be an array")
        raw_inputs = value.get("input_artifact_digests")
        if raw_inputs is None:
            raw_inputs = []
        if not isinstance(raw_inputs, list):
            raise ResearchOSValidationError("task input_artifact_digests must be an array")
        dependencies = tuple(TaskDependency.from_dict(item) for item in raw_dependencies)
        identities = tuple((item.dependency_type.value, item.target_key) for item in dependencies)
        if len(identities) != len(set(identities)):
            raise ResearchOSValidationError(
                f"task {value.get('task_key')!r} has duplicate dependency identities"
            )
        try:
            priority = int(value.get("priority") or 0)
        except (TypeError, ValueError) as exc:
            raise ResearchOSValidationError("task priority must be an integer") from exc
        capability = value.get("requested_capability")
        return cls(
            task_key=_required_text(value.get("task_key"), field_name="task_key"),
            goal_key=_required_text(value.get("goal_key"), field_name="task goal_key"),
            goal_digest=str(value.get("goal_digest") or goal_digest).strip(),
            task_type=_required_text(value.get("task_type"), field_name="task_type"),
            lane=_enum(TaskLane, value.get("lane"), field_name="task lane"),
            dependencies=dependencies,
            priority=priority,
            input_artifact_digests=tuple(
                _required_text(item, field_name="input artifact digest") for item in raw_inputs
            ),
            requested_capability=(
                None
                if capability is None
                else _required_text(capability, field_name="requested_capability")
            ),
            metric_contract=_canonical_object(
                value.get("metric_contract"), field_name="task metric_contract"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_key": self.task_key,
            "goal_key": self.goal_key,
            "goal_digest": self.goal_digest,
            "task_type": self.task_type,
            "lane": self.lane.value,
            "dependencies": [item.to_dict() for item in self.dependencies],
            "priority": self.priority,
            "input_artifact_digests": list(self.input_artifact_digests),
            "requested_capability": self.requested_capability,
            "metric_contract": _decoded_object(self.metric_contract),
        }

    @property
    def artifact_digest(self) -> str:
        return stable_hash(
            {
                "schema": RESEARCH_OS_SCHEMA_VERSION,
                "artifact_type": "task_definition",
                "definition": self.to_dict(),
            }
        )


@dataclass(frozen=True)
class TaskState:
    task_digest: str
    declared_status: TaskStatus = TaskStatus.DRAFT
    completion_classification: CompletionClassification | None = None
    superseded_by_task_digest: str | None = None


@dataclass(frozen=True)
class DependencyFacts:
    artifacts: frozenset[str] = field(default_factory=frozenset)
    evidence: frozenset[str] = field(default_factory=frozenset)
    external_events: frozenset[str] = field(default_factory=frozenset)
    authorities: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> DependencyFacts:
        if value is not None:
            _mapping(value, field_name="facts")
        source = value or {}

        def values(name: str) -> frozenset[str]:
            raw = source.get(name)
            if raw is None:
                raw = []
            if not isinstance(raw, list):
                raise ResearchOSValidationError(f"facts.{name} must be an array")
            return frozenset(_required_text(item, field_name=f"facts.{name} item") for item in raw)

        return cls(
            artifacts=values("artifacts"),
            evidence=values("evidence"),
            external_events=values("external_events"),
            authorities=values("authorities"),
        )

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "artifacts": sorted(self.artifacts),
            "evidence": sorted(self.evidence),
            "external_events": sorted(self.external_events),
            "authorities": sorted(self.authorities),
        }


@dataclass(frozen=True)
class ControlPlaneManifest:
    goals: tuple[Goal, ...]
    tasks: tuple[Task, ...]
    goal_states: tuple[GoalState, ...]
    task_states: tuple[TaskState, ...]
    facts: DependencyFacts = field(default_factory=DependencyFacts)
    schema_version: str = RESEARCH_OS_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ControlPlaneManifest:
        value = _mapping(value, field_name="control-plane manifest")
        schema = str(value.get("schema_version") or "")
        if schema != RESEARCH_OS_SCHEMA_VERSION:
            raise ResearchOSValidationError(
                f"unsupported schema_version {schema!r}; expected {RESEARCH_OS_SCHEMA_VERSION!r}"
            )
        raw_goals = value.get("goals")
        raw_tasks = value.get("tasks")
        if not isinstance(raw_goals, list) or not isinstance(raw_tasks, list):
            raise ResearchOSValidationError("manifest goals and tasks must be arrays")

        goals = tuple(Goal.from_dict(item) for item in raw_goals)
        goal_by_key: dict[str, Goal] = {}
        for goal in goals:
            if goal.goal_key in goal_by_key:
                raise ResearchOSValidationError(f"duplicate goal_key: {goal.goal_key}")
            goal_by_key[goal.goal_key] = goal
        goal_states = tuple(
            GoalState(
                goal_digest=goal.artifact_digest,
                status=_enum(
                    GoalStatus,
                    raw_goals[index].get("status"),
                    field_name="goal status",
                ),
                retired_at=_canonical_timestamp(
                    raw_goals[index].get("retired_at"), field_name="goal retired_at"
                ),
                superseded_by_goal_digest=(
                    str(raw_goals[index].get("superseded_by_goal_digest"))
                    if raw_goals[index].get("superseded_by_goal_digest")
                    else None
                ),
            )
            for index, goal in enumerate(goals)
        )

        tasks_list: list[Task] = []
        task_states_list: list[TaskState] = []
        task_keys: set[str] = set()
        for raw_task in raw_tasks:
            raw_task = _mapping(raw_task, field_name="task")
            goal_key = _required_text(raw_task.get("goal_key"), field_name="task goal_key")
            goal = goal_by_key.get(goal_key)
            if goal is None:
                raise ResearchOSValidationError(
                    f"task {raw_task.get('task_key')!r} references missing goal {goal_key!r}"
                )
            task = Task.from_dict(raw_task, goal_digest=goal.artifact_digest)
            if task.goal_digest != goal.artifact_digest:
                raise ResearchOSValidationError(
                    f"task {task.task_key!r} goal_digest does not match Goal definition"
                )
            if task.task_key in task_keys:
                raise ResearchOSValidationError(f"duplicate task_key: {task.task_key}")
            task_keys.add(task.task_key)
            declared_status = _enum(
                TaskStatus,
                raw_task.get("status", TaskStatus.DRAFT.value),
                field_name="task declared status",
            )
            if declared_status not in DECLARED_TASK_STATUSES:
                allowed = ", ".join(sorted(item.value for item in DECLARED_TASK_STATUSES))
                raise ResearchOSValidationError(
                    f"task declared status must be one of: {allowed}"
                )
            tasks_list.append(task)
            task_states_list.append(
                TaskState(
                    task_digest=task.artifact_digest,
                    declared_status=declared_status,
                    completion_classification=(
                        None
                        if raw_task.get("completion_classification") in (None, "")
                        else _enum(
                            CompletionClassification,
                            raw_task.get("completion_classification"),
                            field_name="task completion_classification",
                        )
                    ),
                    superseded_by_task_digest=(
                        str(raw_task.get("superseded_by_task_digest"))
                        if raw_task.get("superseded_by_task_digest")
                        else None
                    ),
                )
            )

        manifest = cls(
            goals=goals,
            tasks=tuple(tasks_list),
            goal_states=goal_states,
            task_states=tuple(task_states_list),
            facts=DependencyFacts.from_dict(value.get("facts")),
            schema_version=schema,
        )
        p2_measurement_outcomes = {
            "m4-p2-measurement-decision:PASS_TO_P3",
            "m4-p2-measurement-decision:REPAIR_MEASUREMENT_SYSTEM",
        }
        if p2_measurement_outcomes.issubset(manifest.facts.artifacts):
            raise ResearchOSValidationError(
                "P2 measurement decision facts are mutually exclusive"
            )
        p2_identifiability_outcomes = {
            (
                "m4-p2-identifiability-decision:"
                "MEASUREMENT_CONTRACT_IDENTIFIABLE"
            ),
            (
                "m4-p2-identifiability-decision:"
                "MEASUREMENT_CONTRACT_REPAIR_REQUIRED"
            ),
        }
        if p2_identifiability_outcomes.issubset(
            manifest.facts.artifacts
        ):
            raise ResearchOSValidationError(
                "P2 identifiability decision facts are mutually exclusive"
            )
        expected_digest = value.get("manifest_digest")
        if expected_digest and str(expected_digest) != manifest.artifact_digest:
            raise ResearchOSValidationError(
                f"manifest digest mismatch: expected {expected_digest}, calculated {manifest.artifact_digest}"
            )
        return manifest

    @property
    def goal_state_by_digest(self) -> dict[str, GoalState]:
        return {item.goal_digest: item for item in self.goal_states}

    @property
    def task_state_by_digest(self) -> dict[str, TaskState]:
        return {item.task_digest: item for item in self.task_states}

    def to_dict(self, *, include_digest: bool = False) -> dict[str, Any]:
        goal_states = self.goal_state_by_digest
        task_states = self.task_state_by_digest
        goals: list[dict[str, Any]] = []
        for goal in self.goals:
            state = goal_states[goal.artifact_digest]
            item = {
                **goal.to_dict(),
                "status": state.status.value,
                "retired_at": state.retired_at,
                "superseded_by_goal_digest": state.superseded_by_goal_digest,
            }
            goals.append(item)
        tasks: list[dict[str, Any]] = []
        for task in self.tasks:
            state = task_states[task.artifact_digest]
            item = {
                **task.to_dict(),
                "status": state.declared_status.value,
                "completion_classification": (
                    None
                    if state.completion_classification is None
                    else state.completion_classification.value
                ),
                "superseded_by_task_digest": state.superseded_by_task_digest,
            }
            tasks.append(item)
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "goals": goals,
            "tasks": tasks,
            "facts": self.facts.to_dict(),
        }
        if include_digest:
            payload["manifest_digest"] = self.artifact_digest
        return payload

    @property
    def artifact_digest(self) -> str:
        return stable_hash(
            {
                "schema": self.schema_version,
                "artifact_type": "control_plane_manifest",
                "manifest": self.to_dict(include_digest=False),
            }
        )


@dataclass(frozen=True)
class TaskResolution:
    task_key: str
    goal_key: str
    task_digest: str
    status: TaskStatus
    reason_code: str
    unsatisfied_dependencies: tuple[TaskDependency, ...] = ()


@dataclass(frozen=True)
class ReadyQueueItem:
    task_key: str
    goal_key: str
    lane: TaskLane
    task_digest: str
    priority: int
    unblocks_count: int


@dataclass(frozen=True)
class ResolutionSnapshot:
    manifest_digest: str
    resolutions: tuple[TaskResolution, ...]
    ready_queue: tuple[ReadyQueueItem, ...]
    state_counts: tuple[tuple[str, int], ...]
    snapshot_digest: str
    schema_version: str = RESEARCH_OS_SCHEMA_VERSION


@dataclass(frozen=True)
class ExternalExecutorObservation:
    capability: str
    owner: str
    status: str
    observed_at: str
    pid: int | None = None
    metadata: tuple[tuple[str, Any], ...] = ()

    @property
    def artifact_digest(self) -> str:
        return stable_hash(
            {
                "schema": RESEARCH_OS_SCHEMA_VERSION,
                "artifact_type": "external_executor_observation",
                "observation": self,
            }
        )


@dataclass(frozen=True)
class MainlineExecutionEvent:
    execution_id: str
    control_plane_key: str
    manifest_digest: str
    task_key: str
    task_digest: str
    capability: str
    event_type: str
    sequence: int
    recorded_at: str
    payload: tuple[tuple[str, Any], ...] = ()

    @property
    def artifact_digest(self) -> str:
        return stable_hash(
            {
                "schema": RESEARCH_OS_SCHEMA_VERSION,
                "artifact_type": "mainline_execution_event",
                "event": self,
            }
        )


@dataclass(frozen=True)
class MainlineArtifactRegistration:
    execution_id: str
    control_plane_key: str
    task_key: str
    task_digest: str
    artifact_digest: str
    artifact_type: str
    schema_version: str
    artifact_path: str
    parent_digests: tuple[str, ...] = ()
    git_commit: str = ""

    @property
    def registration_digest(self) -> str:
        return stable_hash(
            {
                "schema": RESEARCH_OS_SCHEMA_VERSION,
                "artifact_type": "mainline_artifact_registration",
                "registration": self,
            }
        )


# M4-v2 successor identities deliberately live in this already hashed source
# entry.  They do not import ``dehps.contracts`` or the legacy predictive route
# module because either edge would expand the frozen seven-entry source sets.
M4_V2_MEASUREMENT_CONTRACT_KEY = "M4_MEASUREMENT_CONTRACT_V2"
M4_V2_MEASUREMENT_CONTRACT_DIGEST = (
    "a0a367c99d7646cadc162bd9ceb0d5d73481cd7c26656bf02b40a99d9180095b"
)
M4_V2_BRANCH_IDS = (
    "MARGINAL_STATIC",
    "TEMPORAL_MARGINAL_INCREMENT",
    "JOINT_RESIDUAL_INCREMENT",
)
M4_V2_ESTIMAND_DIGESTS = {
    "MARGINAL_STATIC": "821491eb28b19ebe4ce60d8f7baf7ff7233fec20dc6f25021581437ade56c631",
    "TEMPORAL_MARGINAL_INCREMENT": (
        "f1bde59f8bb59bc4bb796df8ec5fe3f0a4ba723a6cc3828bb263e747cabd53b3"
    ),
    "JOINT_RESIDUAL_INCREMENT": (
        "3cff53fe0dc73f442a850c00a8fc37ee64f7a0822cfdd219d7b877784f4e7ff1"
    ),
}
M4_V2_BRANCH_PRODUCER_TASK_KEYS = {
    "MARGINAL_STATIC": "m4-v2-marginal-static-historical-identity-adoption",
    "TEMPORAL_MARGINAL_INCREMENT": (
        "m4-v2-temporal-marginal-increment-historical-measurement-gate-compiler"
    ),
    "JOINT_RESIDUAL_INCREMENT": (
        "m4-v2-joint-residual-increment-historical-measurement-gate-compiler"
    ),
}
M4_V2_BRANCH_REPLAY_TASK_KEYS = {
    "MARGINAL_STATIC": (
        "m4-v2-marginal-static-historical-branch-decision-replay"
    ),
    "TEMPORAL_MARGINAL_INCREMENT": (
        "m4-v2-temporal-marginal-increment-historical-branch-decision-replay"
    ),
    "JOINT_RESIDUAL_INCREMENT": (
        "m4-v2-joint-residual-increment-historical-branch-decision-replay"
    ),
}

M4_V2_BRANCH_DECISION_ARTIFACT_TYPE = "M4V2BranchDecisionArtifact"
M4_V2_BRANCH_DECISION_SCHEMA = "dehps-m4-v2-branch-decision.v1"
M4_V2_BRANCH_DECISION_DIGEST_DOMAIN = (
    "dehps.m4.v2.historical-branch-decision.v1"
)
M4_V2_BRANCH_DECISION_BODY_FIELDS = (
    "measurement_contract_key",
    "measurement_contract_digest",
    "branch_id",
    "estimand_digest",
    "decision_path",
    "terminal_decision",
    "scientific_decision",
    "evaluation_status",
    "measurement_health",
    "historical_evidence",
    "accepted_for_downstream_baseline",
    "accepted_model_artifact_digest",
    "baseline_artifact_digest",
    "baseline_source_model_artifact_digest",
    "producer_task_key",
    "producer_execution_id",
)

M4_V2_BRANCH_DECISION_REPLAY_ARTIFACT_TYPE = (
    "M4V2BranchDecisionReplayArtifact"
)
M4_V2_BRANCH_DECISION_REPLAY_SCHEMA = (
    "dehps-m4-v2-branch-decision-replay.v1"
)
M4_V2_BRANCH_DECISION_REPLAY_DIGEST_DOMAIN = (
    "dehps.m4.v2.historical-branch-decision-replay.v1"
)
M4_V2_BRANCH_DECISION_REPLAY_BODY_FIELDS = (
    "measurement_contract_key",
    "measurement_contract_digest",
    "branch_id",
    "decision_artifact_digest",
    "decision_registration_digest",
    "decision_producer_task_key",
    "decision_producer_execution_id",
    "replay_task_key",
    "replay_execution_id",
    "replay_status",
    "source_integrity_verified",
    "registered_content_verified",
    "workload_rerun",
)

_M4_V2_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_M4_V2_FORBIDDEN_BLINDED_PAYLOAD_KEYS = frozenset(
    {
        "prediction_results",
        "predictive_p3_result_payload",
        "historical_fold_scores",
        "relative_random_baseline_performance",
        "winning_numbers",
        "prizes",
        "returns",
        "outcome_rank",
        "future_test_window_results",
    }
)
_M4_V2_FORBIDDEN_EXECUTION_PAYLOAD_FIELDS = frozenset(
    {"result", "result_json", "execution_result", "error", "error_json"}
)
_M4_V2_REQUEST_IDENTITY_DOMAIN = (
    "dehps.agent-request.result-blind-metadata.v1"
)
_M4_V2_EXECUTION_IDENTITY_DOMAIN = (
    "dehps.agent-request-execution.result-blind-metadata.v1"
)
_M4_V2_DECISION_IDENTITY_DOMAIN = (
    "dehps.agent-request-decision.append-only-identity.v1"
)


def _m4_v2_canonical_value(value: Any) -> Any:
    """Local byte-equivalent copy of the frozen canonical JSON normalizer."""

    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical payloads require finite floats")
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _m4_v2_canonical_value(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Enum):
        return _m4_v2_canonical_value(value.value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("canonical datetimes require an explicit timezone")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical mappings require string keys")
            normalized[key] = _m4_v2_canonical_value(item)
        return normalized
    if isinstance(value, (set, frozenset)):
        raise TypeError("canonical payloads may not contain unordered collections")
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return [_m4_v2_canonical_value(item) for item in value]
    raise TypeError(f"unsupported canonical payload type: {type(value).__name__}")


def m4_v2_canonical_json(value: Any) -> str:
    """Return the sole canonical JSON representation frozen by Request486."""

    return json.dumps(
        _m4_v2_canonical_value(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def m4_v2_domain_digest(value: Any, *, domain: str) -> str:
    """Hash ``domain + NUL + canonical_json(value)`` without a trailing newline."""

    if not isinstance(domain, str) or not domain.strip():
        raise ValueError("digest domain must be non-empty")
    encoded = f"{domain}\x00{m4_v2_canonical_json(value)}".encode()
    return sha256(encoded).hexdigest()


def _m4_v2_enum_text(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _m4_v2_reject_blinded_payload(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        forbidden = _M4_V2_FORBIDDEN_BLINDED_PAYLOAD_KEYS.intersection(value)
        if forbidden:
            names = ",".join(sorted(forbidden))
            raise ResearchOSValidationError(
                f"m4_v2_blinded_payload_contains_results:{path}:{names}"
            )
        for key, item in value.items():
            _m4_v2_reject_blinded_payload(item, path=f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, item in enumerate(value):
            _m4_v2_reject_blinded_payload(item, path=f"{path}[{index}]")


def governance_request_identity_digest(request: Mapping[str, Any]) -> str:
    """Result-blind Request identity, byte-equivalent to the frozen reference."""

    request = _mapping(request, field_name="governance request")
    payload = request.get("payload") or {}
    _m4_v2_reject_blinded_payload(payload)
    identity = {
        "id": request.get("id"),
        "request_key": request.get("request_key"),
        "request_type": _m4_v2_enum_text(request.get("request_type")),
        "requested_by_role": _m4_v2_enum_text(request.get("requested_by_role")),
        "requested_by": request.get("requested_by"),
        "hypothesis_id": request.get("hypothesis_id"),
        "experiment_id": request.get("experiment_id"),
        "parent_request_id": request.get("parent_request_id"),
        "title": request.get("title"),
        "summary": request.get("summary"),
        "payload": deepcopy(payload),
        "risk_level": _m4_v2_enum_text(request.get("risk_level")),
        "requires_review": request.get("requires_review"),
        "metadata": deepcopy(request.get("metadata") or {}),
    }
    return m4_v2_domain_digest(identity, domain=_M4_V2_REQUEST_IDENTITY_DOMAIN)


def governance_execution_metadata_digest(execution: Mapping[str, Any]) -> str:
    """Hash sanitized execution metadata; result/error keys are rejected."""

    execution = _mapping(execution, field_name="governance execution")
    forbidden = _M4_V2_FORBIDDEN_EXECUTION_PAYLOAD_FIELDS.intersection(execution)
    if forbidden:
        raise ResearchOSValidationError(
            "m4_v2_execution_metadata_not_sanitized:" + ",".join(sorted(forbidden))
        )
    identity = {
        "id": execution.get("id"),
        "request_id": execution.get("request_id"),
        "executor_role": _m4_v2_enum_text(execution.get("executor_role")),
        "executor_id": execution.get("executor_id"),
        "execution_type": execution.get("execution_type"),
        "environment": execution.get("environment"),
        "run_id": execution.get("run_id"),
        "started_at": execution.get("started_at"),
        "created_at": execution.get("created_at"),
    }
    return m4_v2_domain_digest(identity, domain=_M4_V2_EXECUTION_IDENTITY_DOMAIN)


def governance_reviewer_decision_digest(decision: Mapping[str, Any]) -> str:
    """Hash any append-only Decision using the historical frozen projection."""

    decision = _mapping(decision, field_name="governance decision")
    reason = decision.get("reason") or {}
    _m4_v2_reject_blinded_payload(reason, path="decision.reason")
    identity = {
        "id": decision.get("id"),
        "request_id": decision.get("request_id"),
        "previous_status": decision.get("previous_status"),
        "new_status": decision.get("new_status"),
        "decision_code": decision.get("decision_code"),
        "summary": decision.get("summary"),
        "reason": deepcopy(reason),
        "decided_by_role": _m4_v2_enum_text(decision.get("decided_by_role")),
        "decided_by": decision.get("decided_by"),
        "decided_at": decision.get("decided_at"),
        "created_at": decision.get("created_at"),
    }
    return m4_v2_domain_digest(identity, domain=_M4_V2_DECISION_IDENTITY_DOMAIN)


def _m4_v2_fields(value: str) -> tuple[str, ...]:
    return tuple(value.split())


@dataclass(frozen=True)
class M4V2ArtifactTypeSpec:
    schema_version: str
    digest_domain: str
    body_fields: tuple[str, ...]
    branch_id: str | None = None
    body_only_digest: bool = False
    nested_fields: tuple[tuple[str, str], ...] = ()


def _m4_v2_artifact_spec(
    schema_version: str,
    digest_domain: str,
    body_fields: str | tuple[str, ...],
    *,
    branch_id: str | None = None,
    body_only_digest: bool = False,
    nested_fields: Mapping[str, str] | None = None,
) -> M4V2ArtifactTypeSpec:
    return M4V2ArtifactTypeSpec(
        schema_version=schema_version,
        digest_domain=digest_domain,
        body_fields=(
            body_fields
            if isinstance(body_fields, tuple)
            else _m4_v2_fields(body_fields)
        ),
        branch_id=branch_id,
        body_only_digest=body_only_digest,
        nested_fields=tuple((nested_fields or {}).items()),
    )


M4_V2_ARTIFACT_TYPE_REGISTRY: Mapping[str, M4V2ArtifactTypeSpec] = MappingProxyType({
    M4_V2_BRANCH_DECISION_ARTIFACT_TYPE: _m4_v2_artifact_spec(
        M4_V2_BRANCH_DECISION_SCHEMA,
        M4_V2_BRANCH_DECISION_DIGEST_DOMAIN,
        M4_V2_BRANCH_DECISION_BODY_FIELDS,
        body_only_digest=True,
    ),
    M4_V2_BRANCH_DECISION_REPLAY_ARTIFACT_TYPE: _m4_v2_artifact_spec(
        M4_V2_BRANCH_DECISION_REPLAY_SCHEMA,
        M4_V2_BRANCH_DECISION_REPLAY_DIGEST_DOMAIN,
        M4_V2_BRANCH_DECISION_REPLAY_BODY_FIELDS,
        body_only_digest=True,
    ),
    "M4V2TemporalMarginalIncrementDesignArtifact": _m4_v2_artifact_spec(
        "dehps-m4-v2-temporal-marginal-increment-design.v2",
        "dehps.m4.v2.temporal-marginal-increment.design.v2",
        """
        status measurement_contract_key measurement_contract_digest branch_id
        estimand_digest source_contract_digest source_set_digest
        research_contract_digest dataset_contract_digest fold_contract_digest
        estimator_contract_digest health_contract_digest
        historical_inference_contract_digest gate_contract_digest exact_consumer
        historical_outcomes_read scientific_computation evidence_created
        production_action
        """,
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
    ),
    "M4V2TemporalMarginalIncrementPreregistrationBundleArtifact": _m4_v2_artifact_spec(
        "dehps-m4-v2-temporal-marginal-increment-preregistration.v2",
        "dehps.m4.v2.temporal-marginal-increment.preregistration.v2",
        """
        status measurement_contract_key measurement_contract_digest branch_id
        estimand_digest source_contract_digest design_artifact_digest
        dataset_contract_digest fold_contract_digest seed_contract_digest
        numerical_contract_digest health_contract_digest
        historical_inference_contract_digest gate_contract_digest
        stop_contract_digest replay_contract_digest support_model_id
        warmup_request_payload_digest transition_local_warmup_rule
        transition_local_warmup_rule_digest
        synthetic_warmup_application_contract_digest planned_counts
        execution_authorized exact_consumer result_payload_reads
        historical_outcomes_read scientific_computation evidence_created
        production_action
        """,
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
        nested_fields={
            "transition_local_warmup_rule": "warmup_rule_schema",
            "planned_counts": "planned_counts",
        },
    ),
    "M4V2TemporalMarginalIncrementHealthAggregateArtifact": _m4_v2_artifact_spec(
        "dehps-m4-v2-temporal-marginal-increment-health-aggregate.v2",
        "dehps.m4.v2.temporal-marginal-increment.health-aggregate.v2",
        """
        status measurement_contract_key measurement_contract_digest branch_id
        estimand_digest decision_path source_contract_digest
        preregistration_artifact_digest marginal_decision_digest
        marginal_replay_digest transition_local_warmup_rule_digest
        synthetic_warmup_application_or_null
        synthetic_warmup_application_digest_or_null warmup_alias_position_count
        cell_summaries cell_summary_chain_digest measurement_health
        failed_cell_ids synthetic_replicate_count synthetic_generated_issue_count
        outer_evaluation_issue_count bootstrap_resample_count historical_started
        repair_required production_action
        """,
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
        nested_fields={
            "synthetic_warmup_application_or_null": "synthetic_warmup_application?",
            "cell_summaries": "health_cell_summary[14]",
            "failed_cell_ids": "failed_cell_ids",
        },
    ),
    "M4V2TemporalMarginalIncrementHistoricalAggregateArtifact": _m4_v2_artifact_spec(
        "dehps-m4-v2-temporal-marginal-increment-historical-aggregate.v2",
        "dehps.m4.v2.temporal-marginal-increment.historical-aggregate.v2",
        """
        status measurement_contract_key measurement_contract_digest branch_id
        estimand_digest decision_path source_contract_digest
        preregistration_artifact_digest health_artifact_digest
        marginal_raw_p_artifact_digest dataset_content_digest fold_manifest_digest
        checkpoint_chain_digest score_sequence_digest score_count
        observed_mean_bits_per_issue raw_primary_p_value holm_family_raw_p_values
        holm_adjusted_p_value simultaneous_effect_interval_bits_per_issue
        equivalence_upper_bound_bits_per_issue bootstrap_standard_error
        mde_bits_per_issue equivalence_power_at_zero equivalence_power_sufficient
        half_means_bits_per_issue positive_stability_pass sensitivity_summaries
        historical_child_count warmup_index_digest
        accepted_temporal_evaluation_index_digest composite_view_digest
        production_action
        """,
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
        nested_fields={
            "holm_family_raw_p_values": "holm_family_raw_p_values",
            "simultaneous_effect_interval_bits_per_issue": "two_sided_interval",
            "half_means_bits_per_issue": "half_means",
            "sensitivity_summaries": "sensitivity_summary[8]",
        },
    ),
    "M4V2TemporalMarginalIncrementCandidateModelArtifact": _m4_v2_artifact_spec(
        "dehps-m4-v2-temporal-marginal-increment-candidate-model.v2",
        "dehps.m4.v2.temporal-marginal-increment.candidate-model.v2",
        """
        status measurement_contract_key measurement_contract_digest branch_id
        estimand_digest model_id source_contract_digest dataset_content_digest
        fold_manifest_digest marginal_parent_model_artifact_digest
        marginal_parent_probability_chain_digest support_model_id
        historical_warmup_index warmup_index_digest
        accepted_temporal_evaluation_index
        accepted_temporal_evaluation_index_digest composite_temporal_view
        composite_view_digest historical_fold_count production_action
        """,
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
        nested_fields={
            "historical_warmup_index": "warmup_index_schema",
            "accepted_temporal_evaluation_index": (
                "accepted_temporal_evaluation_index"
            ),
            "composite_temporal_view": "composite_temporal_view_schema",
        },
    ),
    "M4V2TemporalMarginalIncrementProducerCompletionArtifact": _m4_v2_artifact_spec(
        "dehps-m4-v2-temporal-marginal-increment-producer-completion.v2",
        "dehps.m4.v2.temporal-marginal-increment.producer-completion.v2",
        """
        status measurement_contract_key measurement_contract_digest branch_id
        estimand_digest decision_path source_contract_digest
        preregistration_artifact_digest registered_artifact_digests_in_order
        decision_artifact_digest terminal_fact completion_fact
        registration_count_including_mainline_execution historical_outcomes_read
        synthetic_replicate_count warmup_transition_count_per_replicate
        warmup_alias_position_count historical_fold_count bootstrap_resample_count
        evidence_created promotion_gate_opened production_action exact_consumer
        """,
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
        nested_fields={
            "registered_artifact_digests_in_order": (
                "preceding_artifact_digest_list"
            )
        },
    ),
    "M4V2TemporalMarginalIncrementScientificFailureArtifact": _m4_v2_artifact_spec(
        "dehps-m4-v2-temporal-marginal-increment-scientific-failure.v2",
        "dehps.m4.v2.temporal-marginal-increment.scientific-failure.v2",
        """
        status measurement_contract_key measurement_contract_digest branch_id
        estimand_digest decision_path source_contract_digest
        preregistration_artifact_digest failure_stage failure_code repairable
        scientific_execution_started historical_started message_digest
        partial_evidence_created completed_fold_count completed_resample_count
        production_action
        """,
        branch_id="TEMPORAL_MARGINAL_INCREMENT",
    ),
    "M4V2JointResidualIncrementDesignArtifact": _m4_v2_artifact_spec(
        "dehps-m4-v2-joint-residual-increment-design.v2",
        "dehps.m4.v2.joint-residual-increment.design.v2",
        """
        status measurement_contract_key measurement_contract_digest branch_id
        estimand_digest source_contract_digest source_set_digest
        research_contract_digest dataset_contract_digest fold_contract_digest
        estimator_contract_digest baseline_contract_digest health_contract_digest
        historical_inference_contract_digest gate_contract_digest exact_consumer
        historical_outcomes_read scientific_computation evidence_created
        production_action
        """,
        branch_id="JOINT_RESIDUAL_INCREMENT",
    ),
    "M4V2JointResidualIncrementPreregistrationArtifact": _m4_v2_artifact_spec(
        "dehps-m4-v2-joint-residual-increment-preregistration.v2",
        "dehps.m4.v2.joint-residual-increment.preregistration.v2",
        """
        status measurement_contract_key measurement_contract_digest branch_id
        estimand_digest source_contract_digest design_artifact_digest
        dataset_contract_digest fold_contract_digest seed_contract_digest
        numerical_contract_digest baseline_contract_digest health_contract_digest
        historical_inference_contract_digest gate_contract_digest
        stop_contract_digest replay_contract_digest support_model_id
        joint_estimator_id warmup_request_payload_digest
        temporal_composite_view_contract_digest q_base_checkpoint_contract_digest
        joint_z_checkpoint_contract_digest joint_target_prediction_contract_digest
        synthetic_warmup_application_contract_digest planned_counts
        execution_authorized exact_consumer result_payload_reads
        historical_outcomes_read scientific_computation evidence_created
        production_action
        """,
        branch_id="JOINT_RESIDUAL_INCREMENT",
        nested_fields={"planned_counts": "planned_counts"},
    ),
    "M4V2JointResidualMaximumEntropyBaselineArtifact": _m4_v2_artifact_spec(
        "dehps-m4-v2-joint-residual-maximum-entropy-baseline.v2",
        "dehps.m4.v2.joint-residual-increment.maximum-entropy-baseline.v2",
        """
        status measurement_contract_key measurement_contract_digest branch_id
        estimand_digest baseline_id source_contract_digest dataset_content_digest
        fold_manifest_digest temporal_parent_candidate_artifact_digest
        temporal_composite_view_digest q_base_checkpoint_index
        q_base_checkpoint_index_digest same_distribution_as_temporal_parent
        distinct_artifact_from_temporal_parent historical_support_count
        historical_fold_count production_action
        """,
        branch_id="JOINT_RESIDUAL_INCREMENT",
        nested_fields={"q_base_checkpoint_index": "q_base_checkpoint_index"},
    ),
    "M4V2JointResidualMeasurementHealthArtifact": _m4_v2_artifact_spec(
        "dehps-m4-v2-joint-residual-measurement-health.v2",
        "dehps.m4.v2.joint-residual-increment.measurement-health.v2",
        """
        status measurement_contract_key measurement_contract_digest branch_id
        estimand_digest decision_path source_contract_digest
        preregistration_artifact_digest marginal_decision_digest
        marginal_replay_digest temporal_decision_digest temporal_replay_digest
        transition_local_warmup_rule_digest synthetic_warmup_application_or_null
        synthetic_warmup_application_digest_or_null warmup_alias_position_count
        cell_summaries cell_summary_chain_digest measurement_health
        failed_cell_ids synthetic_replicate_count synthetic_generated_issue_count
        outer_evaluation_issue_count bootstrap_resample_count historical_started
        repair_required production_action
        """,
        branch_id="JOINT_RESIDUAL_INCREMENT",
        nested_fields={
            "synthetic_warmup_application_or_null": "synthetic_warmup_application?",
            "cell_summaries": "health_cell_summary[14]",
            "failed_cell_ids": "failed_cell_ids",
        },
    ),
    "M4V2JointResidualHistoricalExecutionArtifact": _m4_v2_artifact_spec(
        "dehps-m4-v2-joint-residual-historical-execution.v2",
        "dehps.m4.v2.joint-residual-increment.historical-execution.v2",
        """
        status measurement_contract_key measurement_contract_digest branch_id
        estimand_digest decision_path source_contract_digest
        preregistration_artifact_digest health_artifact_digest
        marginal_raw_p_artifact_digest temporal_raw_p_artifact_digest
        dataset_content_digest fold_manifest_digest checkpoint_chain_digest
        score_sequence_digest score_count observed_mean_bits_per_issue
        raw_primary_p_value holm_family_raw_p_values holm_adjusted_p_value
        simultaneous_effect_interval_bits_per_issue
        equivalence_upper_bound_bits_per_issue bootstrap_standard_error
        mde_bits_per_issue equivalence_power_at_zero equivalence_power_sufficient
        half_means_bits_per_issue positive_stability_pass sensitivity_summaries
        historical_child_count temporal_composite_view_digest
        q_base_checkpoint_index_digest joint_z_checkpoint_index_digest
        joint_eta_checkpoint_chain_digest joint_target_prediction_index_digest
        production_action
        """,
        branch_id="JOINT_RESIDUAL_INCREMENT",
        nested_fields={
            "holm_family_raw_p_values": "holm_family_raw_p_values",
            "simultaneous_effect_interval_bits_per_issue": "two_sided_interval",
            "half_means_bits_per_issue": "half_means",
            "sensitivity_summaries": "sensitivity_summary[8]",
        },
    ),
    "M4V2JointResidualCandidateModelArtifact": _m4_v2_artifact_spec(
        "dehps-m4-v2-joint-residual-candidate-model.v2",
        "dehps.m4.v2.joint-residual-increment.candidate-model.v2",
        """
        status measurement_contract_key measurement_contract_digest branch_id
        estimand_digest model_id joint_estimator_id source_contract_digest
        dataset_content_digest fold_manifest_digest joint_baseline_artifact_digest
        temporal_parent_candidate_artifact_digest temporal_composite_view_digest
        q_base_checkpoint_index_digest joint_z_checkpoint_index
        joint_z_checkpoint_index_digest joint_target_prediction_index
        joint_target_prediction_index_digest fitted_parameter_chain_digest
        orthogonality_certificate_chain_digest
        marginal_preservation_certificate_chain_digest historical_fold_count
        production_action
        """,
        branch_id="JOINT_RESIDUAL_INCREMENT",
        nested_fields={
            "joint_z_checkpoint_index": "joint_z_checkpoint_index",
            "joint_target_prediction_index": "joint_target_prediction_index",
        },
    ),
    "M4V2JointResidualProducerCompletionArtifact": _m4_v2_artifact_spec(
        "dehps-m4-v2-joint-residual-producer-completion.v2",
        "dehps.m4.v2.joint-residual-increment.producer-completion.v2",
        """
        status measurement_contract_key measurement_contract_digest branch_id
        estimand_digest decision_path source_contract_digest
        preregistration_artifact_digest registered_artifact_digests_in_order
        decision_artifact_digest terminal_fact completion_fact
        registration_count_including_mainline_execution historical_outcomes_read
        synthetic_replicate_count warmup_transition_count_per_replicate
        warmup_alias_position_count historical_fold_count bootstrap_resample_count
        evidence_created promotion_gate_opened production_action exact_consumer
        """,
        branch_id="JOINT_RESIDUAL_INCREMENT",
        nested_fields={
            "registered_artifact_digests_in_order": (
                "preceding_artifact_digest_list"
            )
        },
    ),
    "M4V2JointResidualScientificFailureArtifact": _m4_v2_artifact_spec(
        "dehps-m4-v2-joint-residual-scientific-failure.v2",
        "dehps.m4.v2.joint-residual-increment.scientific-failure.v2",
        """
        status measurement_contract_key measurement_contract_digest branch_id
        estimand_digest decision_path source_contract_digest
        preregistration_artifact_digest failure_stage failure_code repairable
        scientific_execution_started historical_started message_digest
        partial_evidence_created completed_fold_count completed_resample_count
        production_action
        """,
        branch_id="JOINT_RESIDUAL_INCREMENT",
    ),
})


def _m4_v2_versioned_artifact_spec(
    artifact_type: str,
    schema_version: str,
) -> M4V2ArtifactTypeSpec:
    """Resolve an artifact spec by its complete versioned identity.

    The public type registry remains the frozen seventeen-type v2 registry.  A
    schema version is nevertheless part of a registered artifact's identity;
    accepted-parent repair and Temporal probability-capsule artifacts therefore
    use this explicit dispatch table instead of a type-only alias or fallback.
    """

    base = M4_V2_ARTIFACT_TYPE_REGISTRY.get(artifact_type)
    if base is None:
        raise ResearchOSValidationError(
            f"unknown M4-v2 artifact_type: {artifact_type}"
        )
    if schema_version == base.schema_version:
        return base
    versioned: dict[tuple[str, str], M4V2ArtifactTypeSpec] = {
        (
            "M4V2TemporalMarginalIncrementCandidateModelArtifact",
            "dehps-m4-v2-temporal-marginal-increment-candidate-model.v3",
        ): _m4_v2_artifact_spec(
            "dehps-m4-v2-temporal-marginal-increment-candidate-model.v3",
            "dehps.m4.v2.temporal-marginal-increment.candidate-model.v3",
            (
                *M4_V2_ARTIFACT_TYPE_REGISTRY[
                    "M4V2TemporalMarginalIncrementCandidateModelArtifact"
                ].body_fields,
                "probability_capsule_index",
                "probability_capsule_index_digest",
                "probability_capsule_evaluator_contract_digest",
            ),
            branch_id="TEMPORAL_MARGINAL_INCREMENT",
            nested_fields=dict(
                M4_V2_ARTIFACT_TYPE_REGISTRY[
                    "M4V2TemporalMarginalIncrementCandidateModelArtifact"
                ].nested_fields
            ),
        ),
        (
            "M4V2TemporalMarginalIncrementScientificFailureArtifact",
            "dehps-m4-v2-temporal-marginal-increment-scientific-failure.v3",
        ): _m4_v2_artifact_spec(
            "dehps-m4-v2-temporal-marginal-increment-scientific-failure.v3",
            "dehps.m4.v2.temporal-marginal-increment.scientific-failure.v3",
            M4_V2_ARTIFACT_TYPE_REGISTRY[
                "M4V2TemporalMarginalIncrementScientificFailureArtifact"
            ].body_fields,
            branch_id="TEMPORAL_MARGINAL_INCREMENT",
        ),
        (
            "M4V2TemporalMarginalIncrementProducerCompletionArtifact",
            "dehps-m4-v2-temporal-marginal-increment-producer-completion.v3",
        ): _m4_v2_artifact_spec(
            "dehps-m4-v2-temporal-marginal-increment-producer-completion.v3",
            "dehps.m4.v2.temporal-marginal-increment.producer-completion.v3",
            M4_V2_ARTIFACT_TYPE_REGISTRY[
                "M4V2TemporalMarginalIncrementProducerCompletionArtifact"
            ].body_fields,
            branch_id="TEMPORAL_MARGINAL_INCREMENT",
            nested_fields={
                "registered_artifact_digests_in_order":
                "preceding_artifact_digest_list"
            },
        ),
        (
            "M4V2JointResidualScientificFailureArtifact",
            "dehps-m4-v2-joint-residual-scientific-failure.v3",
        ): _m4_v2_artifact_spec(
            "dehps-m4-v2-joint-residual-scientific-failure.v3",
            "dehps.m4.v2.joint-residual-increment.scientific-failure.v3",
            M4_V2_ARTIFACT_TYPE_REGISTRY[
                "M4V2JointResidualScientificFailureArtifact"
            ].body_fields,
            branch_id="JOINT_RESIDUAL_INCREMENT",
        ),
        (
            "M4V2JointResidualProducerCompletionArtifact",
            "dehps-m4-v2-joint-residual-producer-completion.v3",
        ): _m4_v2_artifact_spec(
            "dehps-m4-v2-joint-residual-producer-completion.v3",
            "dehps.m4.v2.joint-residual-increment.producer-completion.v3",
            M4_V2_ARTIFACT_TYPE_REGISTRY[
                "M4V2JointResidualProducerCompletionArtifact"
            ].body_fields,
            branch_id="JOINT_RESIDUAL_INCREMENT",
            nested_fields={
                "registered_artifact_digests_in_order":
                "preceding_artifact_digest_list"
            },
        ),
    }
    spec = versioned.get((artifact_type, schema_version))
    if spec is None:
        raise ResearchOSValidationError(
            f"{artifact_type} schema changed"
        )
    return spec


@dataclass(frozen=True)
class M4V2NestedSchemaSpec:
    field_variants: tuple[tuple[str, ...], ...]


def _m4_v2_nested_spec(*variants: str | tuple[str, ...]) -> M4V2NestedSchemaSpec:
    return M4V2NestedSchemaSpec(
        field_variants=tuple(
            item if isinstance(item, tuple) else _m4_v2_fields(item)
            for item in variants
        )
    )


_M4_V2_PLANNED_COUNTS = {
    "cell_count": 14,
    "replicates_per_cell": 512,
    "synthetic_replicate_count": 7168,
    "synthetic_generated_issue_count": 15920128,
    "outer_evaluation_issue_count": 9468928,
    "bootstrap_resample_count": 14651392,
    "historical_fold_count": 2581,
    "historical_child_count": 16000,
    "warmup_transition_count_per_replicate": 899,
    "warmup_alias_position_count": 6444032,
}

M4_V2_NESTED_SCHEMA_REGISTRY: Mapping[str, M4V2NestedSchemaSpec] = MappingProxyType({
    "full_distribution_content_identity": _m4_v2_nested_spec(
        """
        legal_space_id legal_state_order_id
        probabilities_float_hex_in_canonical_1107568_state_order
        """
    ),
    "marginal_vector_content": _m4_v2_nested_spec(
        "probabilities_float_hex_in_ball_order_1_through_33 marginal_content_digest"
    ),
    "dataset_prefix_outcome_chain": _m4_v2_nested_spec(
        """
        dataset_content_digest last_included_ordinal
        ordered_issue_and_six_red_number_rows_1_through_last_included_ordinal
        """
    ),
    "strict_prior_checkpoint_schema": _m4_v2_nested_spec(
        """
        dataset_content_digest checkpoint_order_manifest_digest
        transition_ordinal issue prefix_last_ordinal prefix_last_issue
        prefix_outcome_chain_digest parent_estimator_id
        q_m_marginal_content_digest q_m_full_distribution_content_digest
        checkpoint_digest
        """
    ),
    "pretarget_checkpoint_schema": _m4_v2_nested_spec(
        """
        dataset_content_digest fold_manifest_digest
        checkpoint_order_manifest_digest transition_ordinal issue
        training_prefix_last_ordinal training_prefix_outcome_chain_digest
        parent_estimator_id temporal_estimator_id theta_float_hex
        q_t_marginal_content_digest q_t_full_distribution_content_digest
        pretarget_checkpoint_digest
        """
    ),
    "certificate_coordinate_identity": _m4_v2_nested_spec(
        """
        scope branch_id source_contract_digest preregistration_artifact_digest
        producer_execution_id transition_ordinal
        issue_or_sequence_coordinate_digest support_kind coordinate_digest
        """
    ),
    "q_base_reconstruction_certificate": _m4_v2_nested_spec(
        """
        transition_ordinal temporal_support_row_digest
        q_t_full_distribution_content_digest
        q_base_full_distribution_content_digest
        max_probability_difference_float_hex max_marginal_difference_float_hex
        normalization_residual_float_hex certificate_pass certificate_digest
        """
    ),
    "orthogonality_certificate": _m4_v2_nested_spec(
        """
        coordinate_identity_digest q_base_full_distribution_content_digest
        raw_feature_content_digest
        projection_coefficients_float_hex_in_fixed_33_basis
        orthogonality_residuals_float_hex_in_fixed_34_constraint_order
        condition_number_float_hex rank tolerance_float_hex certificate_pass
        certificate_digest
        """
    ),
    "z_direction_marginal_neutrality_certificate": _m4_v2_nested_spec(
        """
        coordinate_identity_digest q_base_full_distribution_content_digest
        raw_feature_content_digest
        projection_coefficients_float_hex_in_fixed_33_basis scale_B_float_hex
        weighted_marginal_residuals_float_hex_in_ball_order_1_through_33
        max_abs_residual_float_hex tolerance_float_hex certificate_pass
        certificate_digest
        """
    ),
    "target_q_j_marginal_preservation_certificate": _m4_v2_nested_spec(
        """
        coordinate_identity_digest reference_marginal_content_digest
        candidate_full_distribution_content_digest
        derived_candidate_marginal_content_digest
        per_ball_residuals_float_hex_in_ball_order_1_through_33
        max_abs_residual_float_hex tolerance_float_hex certificate_pass
        certificate_digest
        """
    ),
    "normalization_certificate": _m4_v2_nested_spec(
        """
        coordinate_identity_digest full_distribution_content_digest
        sum_probability_float_hex normalization_residual_float_hex
        minimum_probability_float_hex finite_nonnegative tolerance_float_hex
        certificate_pass certificate_digest
        """
    ),
    "q_base_checkpoint": _m4_v2_nested_spec(
        """
        transition_ordinal issue support_kind temporal_support_row_digest
        temporal_composite_view_digest q_t_marginal_content_digest
        q_t_full_distribution_content_digest baseline_id baseline_contract_digest
        q_base_marginal_content_digest q_base_full_distribution_content_digest
        reconstruction_certificate_digest checkpoint_digest
        """
    ),
    "q_base_checkpoint_index": _m4_v2_nested_spec(
        """
        row_count transition_range rows ordered_checkpoint_digests
        checkpoint_chain_digest index_digest
        """
    ),
    "joint_z_checkpoint": _m4_v2_nested_spec(
        """
        source_contract_digest preregistration_artifact_digest
        producer_execution_id joint_estimator_id temporal_composite_view_digest
        transition_ordinal issue support_kind creation_phase
        creation_target_ordinal prefix_last_ordinal prefix_outcome_chain_digest
        q_base_checkpoint_digest q_base_full_distribution_content_digest
        history_state raw_feature_content_digest projection_coefficients_float_hex
        scale_B_float_hex z_function_identity_digest
        orthogonality_certificate_digest marginal_preservation_certificate_digest
        checkpoint_key_digest previous_z_chain_digest checkpoint_digest
        """
    ),
    "joint_z_checkpoint_index": _m4_v2_nested_spec(
        """
        row_count transition_range rows ordered_checkpoint_digests z_chain_digest
        index_digest
        """
    ),
    "joint_eta_checkpoint": _m4_v2_nested_spec(
        """
        target_ordinal issue training_range training_count
        training_z_prefix_chain_digest settled_training_outcome_prefix_digest
        eta_float_hex solver_terminal_code checkpoint_digest
        """
    ),
    "joint_target_prediction_checkpoint": _m4_v2_nested_spec(
        """
        target_ordinal issue eta_checkpoint_digest target_z_checkpoint_digest
        q_base_full_distribution_content_digest q_j_marginal_content_digest
        q_j_full_distribution_content_digest normalization_certificate_digest
        marginal_preservation_certificate_digest checkpoint_digest
        """
    ),
    "joint_target_prediction_index": _m4_v2_nested_spec(
        """
        row_count transition_range eta_rows prediction_rows
        ordered_eta_checkpoint_digests ordered_prediction_checkpoint_digests
        eta_chain_digest q_j_chain_digest index_digest
        """
    ),
    "synthetic_warmup_sequence_coordinate": _m4_v2_nested_spec(
        """
        branch_id fixture_source_digest health_contract_digest seed_contract_digest
        synthetic_root_seed_full_sha256 cell_index cell_id fixture_id horizon_id
        sequence_issue_count replicate_index sequence_seed_full_sha256
        coordinate_digest
        """
    ),
    "synthetic_warmup_cell_descriptor": _m4_v2_nested_spec(
        "cell_index cell_id fixture_id horizon_id sequence_issue_count replicate_count cell_digest"
    ),
    "synthetic_strict_prior_checkpoint": _m4_v2_nested_spec(
        """
        sequence_coordinate_digest transition_ordinal prefix_last_ordinal
        synthetic_prefix_outcome_chain_digest parent_estimator_id parent_formula_id
        q_m_marginal_content_digest q_m_full_distribution_content_digest
        checkpoint_digest
        """
    ),
    "temporal_synthetic_warmup_transition_row": _m4_v2_nested_spec(
        """
        sequence_coordinate_digest warmup_position transition_ordinal
        prefix_last_ordinal synthetic_prefix_outcome_chain_digest
        strict_prior_checkpoint_digest warmup_rule_digest theta_float_hex
        temporal_theta_fit_invoked temporal_theta_root_existence_test_invoked
        q_m_marginal_content_digest q_m_full_distribution_content_digest
        q_t_marginal_content_digest q_t_full_distribution_content_digest
        semantic_scope row_digest
        """
    ),
    "joint_synthetic_warmup_support_row": _m4_v2_nested_spec(
        """
        temporal_transition_row_digest sequence_coordinate_digest
        transition_ordinal q_base_full_distribution_content_digest history_state
        raw_feature_content_digest
        projection_coefficients_float_hex_in_fixed_33_basis scale_B_float_hex
        orthogonality_certificate_digest marginal_preservation_certificate_digest
        z_function_identity_digest z_certificate_digest support_row_digest
        """
    ),
    "joint_synthetic_warmup_settled_row": _m4_v2_nested_spec(
        """
        sequence_coordinate_digest support_row_digest transition_ordinal
        outcome_digest z_at_outcome_float_hex settled_row_digest
        """
    ),
    "synthetic_warmup_replicate_commitment": _m4_v2_nested_spec(
        """
        cell_index cell_id fixture_id horizon_id replicate_index
        sequence_seed_full_sha256 sequence_coordinate_digest transition_range
        transition_count transition_chain_digest replicate_digest
        """,
        """
        cell_index cell_id fixture_id horizon_id replicate_index
        sequence_seed_full_sha256 sequence_coordinate_digest transition_range
        transition_count transition_chain_digest support_chain_digest
        settled_chain_digest replicate_digest
        """,
    ),
    "synthetic_warmup_replicate_index": _m4_v2_nested_spec(
        """
        branch_id cell_manifest_digest row_count rows row_digests_in_order
        row_chain_digest replicates_per_cell warmup_transition_count_per_replicate
        warmup_alias_position_count index_digest
        """
    ),
    "synthetic_warmup_application": _m4_v2_nested_spec(
        """
        branch_id owner_artifact_type source_contract_digest
        preregistration_artifact_digest health_contract_digest seed_contract_digest
        fixture_source_digest synthetic_root_seed_full_sha256 warmup_rule_digest
        support_model_id cell_count cells cell_manifest_digest replicates_per_cell
        replicate_count warmup_transition_range
        warmup_transition_count_per_replicate warmup_alias_position_count
        replicate_index replicate_index_digest ordered_cell_digests
        cell_summary_chain_digest ordered_horizon_digests horizons
        horizon_summary_chain_digest bootstrap_child_count
        synthetic_generated_issue_count application_digest
        """,
        """
        branch_id owner_artifact_type source_contract_digest
        preregistration_artifact_digest health_contract_digest seed_contract_digest
        fixture_source_digest synthetic_root_seed_full_sha256 warmup_rule_digest
        support_model_id joint_estimator_id cell_count cells cell_manifest_digest
        replicates_per_cell replicate_count warmup_transition_range
        warmup_transition_count_per_replicate warmup_alias_position_count
        replicate_index replicate_index_digest ordered_cell_digests
        cell_summary_chain_digest ordered_horizon_digests horizons
        horizon_summary_chain_digest bootstrap_child_count
        synthetic_generated_issue_count application_digest
        """,
    ),
    "synthetic_health_replicate_evidence_commitment": _m4_v2_nested_spec(
        """
        branch_id sequence_coordinate_digest horizon_id evaluation_range
        evaluation_count prediction_checkpoint_chain_digest score_row_chain_digest
        observed_mean_float_hex analytic_truth_float_hex bias_float_hex
        bootstrap_block_lengths ordered_bootstrap_child_mean_chain_digests
        primary_detection primary_interval primary_standard_error_float_hex
        primary_mde_float_hex replicate_evidence_digest
        """
    ),
    "synthetic_health_prediction_checkpoint": _m4_v2_nested_spec(
        """
        branch_id sequence_coordinate_digest evaluation_ordinal
        pretarget_checkpoint_digest parent_distribution_content_digest
        candidate_distribution_content_digest fitted_parameter_float_hex_or_null
        branch_support_checkpoint_digest prediction_checkpoint_digest
        """
    ),
    "synthetic_health_score_row": _m4_v2_nested_spec(
        """
        sequence_coordinate_digest evaluation_ordinal
        prediction_checkpoint_digest settled_outcome_digest score_float_hex
        score_row_digest
        """
    ),
    "historical_score_row": _m4_v2_nested_spec(
        """
        evaluation_ordinal issue prediction_checkpoint_digest
        settled_outcome_digest paired_score_float_hex score_row_digest
        """
    ),
    "synthetic_health_cell_coordinate_chain": _m4_v2_nested_spec(
        "branch_id cell_index cell_id ordered_replicate_evidence_digests coordinate_chain_digest"
    ),
    "synthetic_horizon_summary": _m4_v2_nested_spec(
        """
        horizon_id ordered_cell_indices ordered_cell_summary_digests cell_count
        replicate_count warmup_alias_position_count horizon_digest
        """
    ),
    "health_cell_summary": _m4_v2_nested_spec(
        """
        cell_index cell_id scenario_id truth_effect_bits_per_issue horizon
        replicate_count detection_count detection_rate wilson_upper_95
        mean_bias_bits_per_issue coverage_rate mde_complete threshold_pass
        coordinate_chain_digest cell_summary_digest
        """
    ),
    "sensitivity_summary": _m4_v2_nested_spec(
        """
        scheme_id block_length resample_count child_mean_chain_digest
        effect_interval_bits_per_issue equivalence_upper_bound_bits_per_issue
        bootstrap_standard_error decision_credit
        """
    ),
    "scientific_failure_message_identity": _m4_v2_nested_spec(
        """
        branch_id decision_path failure_stage failure_code repairable
        scientific_execution_started historical_started
        structured_diagnostic_codes_in_order message_digest
        """
    ),
    "planned_counts": _m4_v2_nested_spec(tuple(_M4_V2_PLANNED_COUNTS)),
    "two_sided_interval": _m4_v2_nested_spec(
        "lower_float_hex upper_float_hex"
    ),
    "half_means": _m4_v2_nested_spec(
        "first_half_float_hex second_half_float_hex"
    ),
    "holm_family_raw_p_values": _m4_v2_nested_spec(tuple(M4_V2_BRANCH_IDS)),
    "warmup_rule_schema": _m4_v2_nested_spec(
        """
        schema_version support_model_id rule transition_range transition_count
        theta_float_hex theta_ieee754_binary64_be_hex negative_zero_allowed
        temporal_theta_fit_invoked temporal_theta_root_existence_test_invoked
        regularization fallback distribution_content_alias artifact_envelope_alias
        semantic_scope rule_digest
        """
    ),
    "warmup_row_schema": _m4_v2_nested_spec(
        """
        transition_ordinal issue strict_prior_checkpoint_digest
        q_m_marginal_content_digest q_m_full_distribution_content_digest
        theta_float_hex q_t_marginal_content_digest
        q_t_full_distribution_content_digest temporal_theta_fit_invoked
        semantic_scope row_digest
        """
    ),
    "warmup_index_schema": _m4_v2_nested_spec(
        """
        row_count transition_range rows row_digests_in_order row_chain_digest
        rule_digest warmup_index_digest
        """
    ),
    "accepted_temporal_evaluation_row": _m4_v2_nested_spec(
        """
        transition_ordinal issue pretarget_checkpoint_digest theta_float_hex
        q_t_marginal_content_digest q_t_full_distribution_content_digest
        q_t_row_digest
        """
    ),
    "accepted_temporal_evaluation_index": _m4_v2_nested_spec(
        """
        row_count transition_range rows ordered_q_t_row_digests
        accepted_temporal_evaluation_index_digest
        """
    ),
    "composite_temporal_view_schema": _m4_v2_nested_spec(
        """
        transition_range row_count warmup_index_digest
        accepted_temporal_evaluation_index_digest composite_view_digest
        """
    ),
})


def _m4_v2_is_digest(value: Any) -> bool:
    return isinstance(value, str) and _M4_V2_DIGEST_PATTERN.fullmatch(value) is not None


def _m4_v2_require_digest(value: Any, *, field_name: str) -> str:
    if not _m4_v2_is_digest(value):
        raise ResearchOSValidationError(
            f"{field_name} must be a lowercase sha256 digest"
        )
    return str(value)


def _m4_v2_require_exact_fields(
    value: Mapping[str, Any],
    expected_variants: tuple[tuple[str, ...], ...],
    *,
    field_name: str,
) -> None:
    if any(not isinstance(key, str) for key in value):
        raise ResearchOSValidationError(f"{field_name} requires string keys")
    actual = frozenset(value)
    if any(actual == frozenset(variant) and len(value) == len(variant) for variant in expected_variants):
        return
    expected = " or ".join(
        "[" + ",".join(variant) + "]" for variant in expected_variants
    )
    raise ResearchOSValidationError(
        f"{field_name} fields must be exactly {expected}"
    )


def _m4_v2_float_hex(value: Any, *, field_name: str) -> float:
    if not isinstance(value, str):
        raise ResearchOSValidationError(f"{field_name} must be a float.hex string")
    try:
        parsed = float.fromhex(value)
    except ValueError as exc:
        raise ResearchOSValidationError(
            f"{field_name} must be a float.hex string"
        ) from exc
    if not math.isfinite(parsed):
        raise ResearchOSValidationError(f"{field_name} must be finite")
    if parsed.hex() != value or value == "-0x0.0p+0":
        raise ResearchOSValidationError(
            f"{field_name} must be canonical Python float.hex without negative zero"
        )
    return parsed


def _m4_v2_float_hex_array(
    value: Any,
    *,
    field_name: str,
    length: int,
    nonnegative: bool = False,
) -> list[float]:
    if not isinstance(value, list) or len(value) != length:
        raise ResearchOSValidationError(
            f"{field_name} must contain exactly {length} float.hex values"
        )
    parsed = [
        _m4_v2_float_hex(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(value)
    ]
    if nonnegative and any(item < 0.0 for item in parsed):
        raise ResearchOSValidationError(f"{field_name} must be nonnegative")
    return parsed


def _m4_v2_nonnegative_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ResearchOSValidationError(
            f"{field_name} must be a nonnegative integer"
        )
    return value


def _m4_v2_validate_digest_named_fields(
    value: Mapping[str, Any], *, field_name: str
) -> None:
    for key, item in value.items():
        if key == "issue_or_sequence_coordinate_digest":
            if not isinstance(item, str) or not item:
                raise ResearchOSValidationError(
                    f"{field_name}.{key} must be a non-empty issue or digest string"
                )
        elif item is not None and key.endswith(
            ("_digest", "_digest_or_null", "_sha256", "_execution_id")
        ):
            _m4_v2_require_digest(item, field_name=f"{field_name}.{key}")
        elif key.endswith("_digests"):
            if not isinstance(item, list):
                raise ResearchOSValidationError(
                    f"{field_name}.{key} must be an ordered digest array"
                )
            for index, digest in enumerate(item):
                _m4_v2_require_digest(
                    digest, field_name=f"{field_name}.{key}[{index}]"
                )


def _m4_v2_validate_nested_object_semantics(
    schema_name: str, value: Mapping[str, Any]
) -> None:
    _m4_v2_validate_digest_named_fields(value, field_name=schema_name)
    for key, item in value.items():
        if key.endswith("_float_hex"):
            if key == "projection_coefficients_float_hex":
                _m4_v2_float_hex_array(
                    item,
                    field_name=f"{schema_name}.{key}",
                    length=33,
                )
            else:
                _m4_v2_float_hex(item, field_name=f"{schema_name}.{key}")
        elif key.endswith("_float_hex_or_null") and item is not None:
            _m4_v2_float_hex(item, field_name=f"{schema_name}.{key}")
    if schema_name == "full_distribution_content_identity":
        if (
            value["legal_space_id"] != "LEGAL_SIX_OF_33_COMBINATIONS"
            or value["legal_state_order_id"]
            != "INCREASING_LEXICOGRAPHIC_SIX_LABEL_TUPLE"
        ):
            raise ResearchOSValidationError(
                "full-distribution legal space or state order changed"
            )
        _m4_v2_float_hex_array(
            value["probabilities_float_hex_in_canonical_1107568_state_order"],
            field_name=(
                "full_distribution_content_identity."
                "probabilities_float_hex_in_canonical_1107568_state_order"
            ),
            length=1_107_568,
            nonnegative=True,
        )
    elif schema_name == "marginal_vector_content":
        _m4_v2_float_hex_array(
            value["probabilities_float_hex_in_ball_order_1_through_33"],
            field_name=(
                "marginal_vector_content."
                "probabilities_float_hex_in_ball_order_1_through_33"
            ),
            length=33,
            nonnegative=True,
        )
    elif schema_name == "dataset_prefix_outcome_chain":
        last = _m4_v2_nonnegative_int(
            value["last_included_ordinal"], field_name="last_included_ordinal"
        )
        rows = value["ordered_issue_and_six_red_number_rows_1_through_last_included_ordinal"]
        if not isinstance(rows, list) or len(rows) != last:
            raise ResearchOSValidationError(
                "dataset prefix outcome chain cardinality changed"
            )
    elif schema_name == "strict_prior_checkpoint_schema":
        transition = _m4_v2_nonnegative_int(
            value["transition_ordinal"], field_name="transition_ordinal"
        )
        prefix_last = _m4_v2_nonnegative_int(
            value["prefix_last_ordinal"], field_name="prefix_last_ordinal"
        )
        if (
            not 2 <= transition <= 3481
            or prefix_last != transition - 1
            or value["dataset_content_digest"]
            != "8f7b7527d6ee95301b58002e594b0955b7e0f391421b8c438b87fc4f2507b106"
            or value["checkpoint_order_manifest_digest"]
            != "40b85566e977311438add76d301d9614050bfac7fa0de618c1f415299f8b88cd"
            or value["parent_estimator_id"]
            != "EXPANDING_LEGAL_MARGINAL_ALPHA_1"
            or not isinstance(value["issue"], str)
            or not value["issue"]
            or not isinstance(value["prefix_last_issue"], str)
            or not value["prefix_last_issue"]
        ):
            raise ResearchOSValidationError("strict-prior checkpoint changed")
    elif schema_name == "pretarget_checkpoint_schema":
        transition = _m4_v2_nonnegative_int(
            value["transition_ordinal"], field_name="transition_ordinal"
        )
        prefix_last = _m4_v2_nonnegative_int(
            value["training_prefix_last_ordinal"],
            field_name="training_prefix_last_ordinal",
        )
        fixed = {
            "dataset_content_digest": (
                "8f7b7527d6ee95301b58002e594b0955b7e0f391421b8c438b87fc4f2507b106"
            ),
            "fold_manifest_digest": (
                "5a68579161ad5528ee15b8b1ea3e314d6acb05203885a5514e5654da026e9ad7"
            ),
            "checkpoint_order_manifest_digest": (
                "40b85566e977311438add76d301d9614050bfac7fa0de618c1f415299f8b88cd"
            ),
            "parent_estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "temporal_estimator_id": (
                "EXPANDING_LEGAL_ONE_LAG_OVERLAP_TILT_MLE_V1"
            ),
        }
        if (
            not 901 <= transition <= 3481
            or prefix_last != transition - 1
            or any(value.get(key) != item for key, item in fixed.items())
            or not isinstance(value["issue"], str)
            or not value["issue"]
        ):
            raise ResearchOSValidationError("Temporal pretarget checkpoint changed")
    elif schema_name == "certificate_coordinate_identity":
        if (
            value["scope"]
            not in {
                "HISTORICAL_Z",
                "SYNTHETIC_Z",
                "HISTORICAL_TARGET_Q_J",
                "SYNTHETIC_TARGET_Q_J",
            }
            or value["branch_id"] != "JOINT_RESIDUAL_INCREMENT"
            or value["support_kind"]
            not in {"WARMUP_NULL_ALIAS", "ACCEPTED_TEMPORAL_EVALUATION"}
        ):
            raise ResearchOSValidationError(
                "numerical certificate coordinate identity changed"
            )
        transition = _m4_v2_nonnegative_int(
            value["transition_ordinal"], field_name="transition_ordinal"
        )
        if not 2 <= transition <= 3481:
            raise ResearchOSValidationError(
                "certificate transition ordinal outside frozen range"
            )
    elif schema_name == "q_base_reconstruction_certificate":
        for key in (
            "max_probability_difference_float_hex",
            "max_marginal_difference_float_hex",
            "normalization_residual_float_hex",
        ):
            if _m4_v2_float_hex(value[key], field_name=key) < 0.0:
                raise ResearchOSValidationError(f"{key} must be nonnegative")
        if not isinstance(value["certificate_pass"], bool):
            raise ResearchOSValidationError("certificate_pass must be boolean")
    elif schema_name == "orthogonality_certificate":
        _m4_v2_float_hex_array(
            value["projection_coefficients_float_hex_in_fixed_33_basis"],
            field_name="projection_coefficients_float_hex_in_fixed_33_basis",
            length=33,
        )
        _m4_v2_float_hex_array(
            value[
                "orthogonality_residuals_float_hex_in_fixed_34_constraint_order"
            ],
            field_name=(
                "orthogonality_residuals_float_hex_in_fixed_34_constraint_order"
            ),
            length=34,
        )
        _m4_v2_nonnegative_int(value["rank"], field_name="rank")
        if (
            _m4_v2_float_hex(
                value["condition_number_float_hex"],
                field_name="condition_number_float_hex",
            )
            < 0.0
            or _m4_v2_float_hex(
                value["tolerance_float_hex"], field_name="tolerance_float_hex"
            )
            < 0.0
            or not isinstance(value["certificate_pass"], bool)
        ):
            raise ResearchOSValidationError("orthogonality certificate scalar invalid")
    elif schema_name == "z_direction_marginal_neutrality_certificate":
        _m4_v2_float_hex_array(
            value["projection_coefficients_float_hex_in_fixed_33_basis"],
            field_name="projection_coefficients_float_hex_in_fixed_33_basis",
            length=33,
        )
        _m4_v2_float_hex_array(
            value[
                "weighted_marginal_residuals_float_hex_in_ball_order_1_through_33"
            ],
            field_name=(
                "weighted_marginal_residuals_float_hex_in_ball_order_1_through_33"
            ),
            length=33,
        )
        if (
            _m4_v2_float_hex(value["scale_B_float_hex"], field_name="scale_B_float_hex")
            <= 0.0
            or _m4_v2_float_hex(
                value["max_abs_residual_float_hex"],
                field_name="max_abs_residual_float_hex",
            )
            < 0.0
            or _m4_v2_float_hex(
                value["tolerance_float_hex"], field_name="tolerance_float_hex"
            )
            < 0.0
            or not isinstance(value["certificate_pass"], bool)
        ):
            raise ResearchOSValidationError(
                "z-direction neutrality certificate scalar invalid"
            )
    elif schema_name == "target_q_j_marginal_preservation_certificate":
        _m4_v2_float_hex_array(
            value[
                "per_ball_residuals_float_hex_in_ball_order_1_through_33"
            ],
            field_name=(
                "per_ball_residuals_float_hex_in_ball_order_1_through_33"
            ),
            length=33,
        )
        if (
            _m4_v2_float_hex(
                value["max_abs_residual_float_hex"],
                field_name="max_abs_residual_float_hex",
            )
            < 0.0
            or _m4_v2_float_hex(
                value["tolerance_float_hex"], field_name="tolerance_float_hex"
            )
            < 0.0
            or not isinstance(value["certificate_pass"], bool)
        ):
            raise ResearchOSValidationError(
                "target marginal-preservation certificate scalar invalid"
            )
    elif schema_name == "normalization_certificate":
        if (
            _m4_v2_float_hex(
                value["normalization_residual_float_hex"],
                field_name="normalization_residual_float_hex",
            )
            < 0.0
            or _m4_v2_float_hex(
                value["tolerance_float_hex"], field_name="tolerance_float_hex"
            )
            < 0.0
            or not isinstance(value["finite_nonnegative"], bool)
            or not isinstance(value["certificate_pass"], bool)
        ):
            raise ResearchOSValidationError("normalization certificate scalar invalid")
    if schema_name == "planned_counts" and dict(value) != _M4_V2_PLANNED_COUNTS:
        raise ResearchOSValidationError("planned_counts values changed")
    if schema_name == "holm_family_raw_p_values":
        for branch_id in M4_V2_BRANCH_IDS:
            item = value[branch_id]
            if (
                isinstance(item, bool)
                or not isinstance(item, (int, float))
                or not math.isfinite(float(item))
                or not 0.0 <= float(item) <= 1.0
            ):
                raise ResearchOSValidationError(
                    f"holm_family_raw_p_values.{branch_id} must be in [0,1]"
                )
    elif schema_name == "two_sided_interval":
        lower = _m4_v2_float_hex(value["lower_float_hex"], field_name="lower_float_hex")
        upper = _m4_v2_float_hex(value["upper_float_hex"], field_name="upper_float_hex")
        if lower > upper:
            raise ResearchOSValidationError("two_sided_interval is reversed")
    elif schema_name == "half_means":
        _m4_v2_float_hex(value["first_half_float_hex"], field_name="first_half_float_hex")
        _m4_v2_float_hex(value["second_half_float_hex"], field_name="second_half_float_hex")
    elif schema_name == "warmup_rule_schema":
        expected = {
            "schema_version": "dehps-m4-v2-transition-local-temporal-warmup.v1",
            "support_model_id": (
                "TRANSITION_LOCAL_TEMPORAL_PARENT_ALIAS_THETA_ZERO_S2_900_V1"
            ),
            "rule": "FIXED_NULL_THETA_ZERO_PARENT_DISTRIBUTION_ALIAS",
            "transition_range": [2, 900],
            "transition_count": 899,
            "theta_float_hex": "0x0.0p+0",
            "theta_ieee754_binary64_be_hex": "0000000000000000",
            "negative_zero_allowed": False,
            "temporal_theta_fit_invoked": False,
            "temporal_theta_root_existence_test_invoked": False,
            "regularization": None,
            "fallback": None,
            "distribution_content_alias": True,
            "artifact_envelope_alias": False,
            "semantic_scope": "NON_EVIDENCE_JOINT_TRAINING_SUPPORT_ONLY",
        }
        if any(value.get(key) != item for key, item in expected.items()):
            raise ResearchOSValidationError("fixed-null warmup rule changed")
    elif schema_name == "warmup_row_schema":
        transition = _m4_v2_nonnegative_int(
            value["transition_ordinal"], field_name="transition_ordinal"
        )
        if (
            not 2 <= transition <= 900
            or value["theta_float_hex"] != "0x0.0p+0"
            or value["temporal_theta_fit_invoked"] is not False
            or value["semantic_scope"]
            != "NON_EVIDENCE_JOINT_TRAINING_SUPPORT_ONLY"
            or value["q_t_marginal_content_digest"]
            != value["q_m_marginal_content_digest"]
            or value["q_t_full_distribution_content_digest"]
            != value["q_m_full_distribution_content_digest"]
        ):
            raise ResearchOSValidationError("fixed-null warmup row changed")
    elif schema_name == "warmup_index_schema":
        if value["row_count"] != 899 or value["transition_range"] != [2, 900]:
            raise ResearchOSValidationError("warmup index coordinate changed")
        rows = value["rows"]
        digests = value["row_digests_in_order"]
        if not isinstance(rows, list) or not isinstance(digests, list) or len(rows) != 899 or len(digests) != 899:
            raise ResearchOSValidationError("warmup index cardinality changed")
        validated_rows = [validate_m4_v2_nested_schema("warmup_row_schema", item) for item in rows]
        if [item["row_digest"] for item in validated_rows] != digests:
            raise ResearchOSValidationError("warmup row digest order changed")
    elif schema_name == "accepted_temporal_evaluation_index":
        if value["row_count"] != 2581 or value["transition_range"] != [901, 3481]:
            raise ResearchOSValidationError("accepted Temporal index coordinate changed")
        rows = value["rows"]
        digests = value["ordered_q_t_row_digests"]
        if not isinstance(rows, list) or not isinstance(digests, list) or len(rows) != 2581 or len(digests) != 2581:
            raise ResearchOSValidationError("accepted Temporal index cardinality changed")
        validated_rows = [validate_m4_v2_nested_schema("accepted_temporal_evaluation_row", item) for item in rows]
        if [item["q_t_row_digest"] for item in validated_rows] != digests:
            raise ResearchOSValidationError("accepted Temporal row order changed")
    elif schema_name == "accepted_temporal_evaluation_row":
        transition = _m4_v2_nonnegative_int(
            value["transition_ordinal"], field_name="transition_ordinal"
        )
        if not 901 <= transition <= 3481:
            raise ResearchOSValidationError(
                "accepted Temporal row ordinal outside frozen range"
            )
    elif schema_name == "composite_temporal_view_schema":
        if value["row_count"] != 3480 or value["transition_range"] != [2, 3481]:
            raise ResearchOSValidationError("Temporal composite coordinate changed")
    elif schema_name in {"q_base_checkpoint_index", "joint_z_checkpoint_index"}:
        if value["row_count"] != 3480 or value["transition_range"] != [2, 3481]:
            raise ResearchOSValidationError(f"{schema_name} coordinate changed")
    elif schema_name == "joint_target_prediction_index":
        if value["row_count"] != 2581 or value["transition_range"] != [901, 3481]:
            raise ResearchOSValidationError("Joint target index coordinate changed")
    elif schema_name == "synthetic_warmup_replicate_index":
        expected = {
            "row_count": 7168,
            "replicates_per_cell": 512,
            "warmup_transition_count_per_replicate": 899,
            "warmup_alias_position_count": 6444032,
        }
        if any(value.get(key) != item for key, item in expected.items()):
            raise ResearchOSValidationError("synthetic replicate index counts changed")
    elif schema_name == "synthetic_warmup_application":
        expected = {
            "cell_count": 14,
            "replicates_per_cell": 512,
            "replicate_count": 7168,
            "warmup_transition_range": [2, 900],
            "warmup_transition_count_per_replicate": 899,
            "warmup_alias_position_count": 6444032,
            "bootstrap_child_count": 14651392,
            "synthetic_generated_issue_count": 15920128,
        }
        if any(value.get(key) != item for key, item in expected.items()):
            raise ResearchOSValidationError("synthetic warmup application counts changed")
    elif schema_name in {
        "historical_score_row",
        "synthetic_health_prediction_checkpoint",
        "synthetic_health_score_row",
    }:
        _m4_v2_nonnegative_int(
            value["evaluation_ordinal"], field_name="evaluation_ordinal"
        )


def validate_m4_v2_nested_schema(schema_name: str, value: Any) -> Any:
    """Validate one closed Request485/486 nested member and detach its bytes."""

    if not isinstance(schema_name, str) or not schema_name:
        raise ResearchOSValidationError("nested schema_name must be non-empty")
    allow_none = schema_name.endswith("?")
    if allow_none:
        schema_name = schema_name[:-1]
        if value is None:
            return None
    array_match = re.fullmatch(r"(.+)\[([0-9]+)\]", schema_name)
    if array_match:
        item_schema = array_match.group(1)
        expected_length = int(array_match.group(2))
        if not isinstance(value, list) or len(value) != expected_length:
            raise ResearchOSValidationError(
                f"{schema_name} must contain exactly {expected_length} items"
            )
        return [validate_m4_v2_nested_schema(item_schema, item) for item in value]
    if schema_name == "preceding_artifact_digest_list":
        if not isinstance(value, list) or len(value) != len(set(value)):
            raise ResearchOSValidationError(
                "preceding_artifact_digest_list must be an ordered unique array"
            )
        return [
            _m4_v2_require_digest(item, field_name="preceding artifact digest")
            for item in value
        ]
    if schema_name == "failed_cell_ids":
        if (
            not isinstance(value, list)
            or any(not isinstance(item, str) or not item for item in value)
            or len(value) != len(set(value))
        ):
            raise ResearchOSValidationError("failed_cell_ids must be unique strings")
        return list(value)
    spec = M4_V2_NESTED_SCHEMA_REGISTRY.get(schema_name)
    if spec is None:
        raise ResearchOSValidationError(f"unknown M4-v2 nested schema: {schema_name}")
    value = _mapping(value, field_name=schema_name)
    _m4_v2_require_exact_fields(
        value, spec.field_variants, field_name=f"nested {schema_name}"
    )
    _m4_v2_validate_nested_object_semantics(schema_name, value)
    return json.loads(m4_v2_canonical_json(value))


def _m4_v2_validate_branch_decision_body(body: Mapping[str, Any]) -> None:
    branch_id = body.get("branch_id")
    if branch_id not in M4_V2_BRANCH_IDS:
        raise ResearchOSValidationError("invalid M4-v2 branch_id")
    if body.get("estimand_digest") != M4_V2_ESTIMAND_DIGESTS[branch_id]:
        raise ResearchOSValidationError("M4-v2 branch estimand digest changed")
    allowed_terminal = {
        "BRANCH_INFORMATION_ACCEPTED",
        "NO_DETECTABLE_INFORMATION",
        "INCONCLUSIVE_DUE_TO_POWER",
        "MEASUREMENT_REPAIR_REQUIRED",
        "INVALID_EXECUTION",
        "NOT_EVALUABLE_PARENT_NOT_ACCEPTED",
    }
    terminal = body.get("terminal_decision")
    if terminal not in allowed_terminal:
        raise ResearchOSValidationError("invalid M4-v2 terminal Decision mapping")
    exact_terminal_fields: dict[str, tuple[Any, str, tuple[str, ...], bool]] = {
        "BRANCH_INFORMATION_ACCEPTED": (
            "BRANCH_INFORMATION_ACCEPTED",
            "COMPLETE",
            ("POSITIVE",),
            True,
        ),
        "NO_DETECTABLE_INFORMATION": (
            "NO_DETECTABLE_INFORMATION",
            "COMPLETE",
            ("NEGATIVE",),
            False,
        ),
        "INCONCLUSIVE_DUE_TO_POWER": (
            "INCONCLUSIVE_DUE_TO_POWER",
            "COMPLETE",
            ("INCONCLUSIVE",),
            False,
        ),
        "MEASUREMENT_REPAIR_REQUIRED": (
            "MEASUREMENT_REPAIR_REQUIRED",
            "REPAIR_REQUIRED",
            ("NOT_RUN", "INCONCLUSIVE"),
            False,
        ),
        "INVALID_EXECUTION": (
            "INVALID_EXECUTION",
            "INVALID",
            ("NOT_RUN", "INCONCLUSIVE"),
            False,
        ),
        "NOT_EVALUABLE_PARENT_NOT_ACCEPTED": (
            None,
            "NOT_RUN_PARENT_NOT_ACCEPTED",
            ("NOT_RUN",),
            False,
        ),
    }
    scientific, evaluation, evidence_values, accepted = exact_terminal_fields[terminal]
    if (
        body.get("scientific_decision") != scientific
        or body.get("evaluation_status") != evaluation
        or body.get("historical_evidence") not in evidence_values
        or body.get("accepted_for_downstream_baseline") is not accepted
    ):
        raise ResearchOSValidationError("invalid M4-v2 terminal Decision mapping")
    expected_health = {
        "BRANCH_INFORMATION_ACCEPTED": "PASS",
        "NO_DETECTABLE_INFORMATION": "PASS",
        "INCONCLUSIVE_DUE_TO_POWER": "PASS",
        "MEASUREMENT_REPAIR_REQUIRED": "REPAIR",
        "INVALID_EXECUTION": "INCONCLUSIVE",
        "NOT_EVALUABLE_PARENT_NOT_ACCEPTED": "INCONCLUSIVE",
    }[terminal]
    if body.get("measurement_health") != expected_health:
        raise ResearchOSValidationError("invalid M4-v2 measurement-health mapping")
    if not isinstance(body.get("accepted_for_downstream_baseline"), bool):
        raise ResearchOSValidationError(
            "accepted_for_downstream_baseline must be boolean"
        )
    for key in (
        "decision_path",
        "evaluation_status",
        "measurement_health",
        "historical_evidence",
        "producer_task_key",
    ):
        _required_text(body.get(key), field_name=f"branch Decision {key}")
    if body.get("producer_task_key") != M4_V2_BRANCH_PRODUCER_TASK_KEYS[branch_id]:
        raise ResearchOSValidationError("M4-v2 Decision producer task changed")
    decision_path = body.get("decision_path")
    if branch_id == "MARGINAL_STATIC":
        if decision_path != "IDENTITY_ADOPTION_COMPLETE":
            raise ResearchOSValidationError("Marginal Decision path changed")
    else:
        allowed_paths = {
            "BRANCH_INFORMATION_ACCEPTED": {"EVALUATED_COMPLETE"},
            "NO_DETECTABLE_INFORMATION": {"EVALUATED_COMPLETE"},
            "INCONCLUSIVE_DUE_TO_POWER": {"EVALUATED_COMPLETE"},
            "MEASUREMENT_REPAIR_REQUIRED": {
                "IDENTITY_VALID_HEALTH_REPAIR",
                "IDENTITY_VALID_HISTORICAL_REPAIR",
            },
            "INVALID_EXECUTION": {
                "IDENTITY_VALID_HEALTH_INVALID",
                "IDENTITY_VALID_HISTORICAL_INVALID",
            },
            "NOT_EVALUABLE_PARENT_NOT_ACCEPTED": {"PARENT_NOT_ACCEPTED"},
        }[terminal]
        if decision_path not in allowed_paths:
            raise ResearchOSValidationError("M4-v2 Decision path/terminal mismatch")
    _m4_v2_require_digest(
        body.get("producer_execution_id"), field_name="producer_execution_id"
    )
    for key in (
        "accepted_model_artifact_digest",
        "baseline_artifact_digest",
        "baseline_source_model_artifact_digest",
    ):
        if body.get(key) is not None:
            _m4_v2_require_digest(body[key], field_name=key)
    evaluated = terminal in {
        "BRANCH_INFORMATION_ACCEPTED",
        "NO_DETECTABLE_INFORMATION",
        "INCONCLUSIVE_DUE_TO_POWER",
    }
    if evaluated and (
        body.get("accepted_model_artifact_digest") is None
        or body.get("baseline_artifact_digest") is None
    ):
        raise ResearchOSValidationError(
            "evaluated branch Decision requires model and baseline identities"
        )
    if evaluated:
        accepted_model = body["accepted_model_artifact_digest"]
        baseline = body["baseline_artifact_digest"]
        baseline_source = body.get("baseline_source_model_artifact_digest")
        marginal_model = (
            "fb7eb603f7fc283ee645a38ae1d2555d47b43fb86dbb23439a91ef329f1167d6"
        )
        marginal_baseline = (
            "efbb2a3d3b711c5c63b9f05b8133f9cc4ba77b1121b90ef9f951ab56fe263b3e"
        )
        if branch_id == "MARGINAL_STATIC" and (
            accepted_model != marginal_model
            or baseline != marginal_baseline
            or baseline_source is not None
        ):
            raise ResearchOSValidationError("Marginal model/baseline mapping changed")
        if branch_id == "TEMPORAL_MARGINAL_INCREMENT" and (
            baseline != marginal_model or baseline_source != marginal_model
        ):
            raise ResearchOSValidationError("Temporal parent baseline mapping changed")
        if branch_id == "JOINT_RESIDUAL_INCREMENT" and (
            baseline_source is None
            or baseline == baseline_source
            or accepted_model == baseline
        ):
            raise ResearchOSValidationError("Joint parent baseline mapping changed")
    if not evaluated and any(
        body.get(key) is not None
        for key in (
            "accepted_model_artifact_digest",
            "baseline_artifact_digest",
            "baseline_source_model_artifact_digest",
        )
    ):
        raise ResearchOSValidationError(
            "non-evaluated branch Decision cannot carry model identities"
        )


def _m4_v2_validate_branch_replay_body(
    body: Mapping[str, Any], parent_digests: Sequence[str]
) -> None:
    branch_id = body.get("branch_id")
    if branch_id not in M4_V2_BRANCH_IDS:
        raise ResearchOSValidationError("invalid M4-v2 replay branch_id")
    for key in (
        "decision_artifact_digest",
        "decision_registration_digest",
        "decision_producer_execution_id",
        "replay_execution_id",
    ):
        _m4_v2_require_digest(body.get(key), field_name=key)
    for key in ("decision_producer_task_key", "replay_task_key"):
        _required_text(body.get(key), field_name=f"branch replay {key}")
    if (
        body.get("decision_producer_task_key")
        != M4_V2_BRANCH_PRODUCER_TASK_KEYS[branch_id]
        or body.get("replay_task_key") != M4_V2_BRANCH_REPLAY_TASK_KEYS[branch_id]
    ):
        raise ResearchOSValidationError("M4-v2 replay task identity changed")
    if body.get("decision_producer_execution_id") == body.get("replay_execution_id"):
        raise ResearchOSValidationError(
            "replay execution must differ from Decision producer execution"
        )
    if body.get("replay_status") != "REGISTERED_REPLAY_VERIFIED":
        raise ResearchOSValidationError("branch replay is not registered-verified")
    if body.get("source_integrity_verified") is not True:
        raise ResearchOSValidationError("branch replay source integrity not verified")
    if body.get("registered_content_verified") is not True:
        raise ResearchOSValidationError("branch replay content not verified")
    if body.get("workload_rerun") is not False:
        raise ResearchOSValidationError("branch replay may not rerun workload")
    if len(parent_digests) != 4:
        raise ResearchOSValidationError("branch replay requires exactly four parents")
    if parent_digests[1] != body["decision_artifact_digest"]:
        raise ResearchOSValidationError("branch replay Decision parent mismatch")
    if parent_digests[2] != body["decision_registration_digest"]:
        raise ResearchOSValidationError("branch replay registration parent mismatch")


def _m4_v2_validate_nested_owner_equalities(
    body: Mapping[str, Any], nested: Mapping[str, Any]
) -> None:
    equalities = (
        (
            "transition_local_warmup_rule",
            "rule_digest",
            "transition_local_warmup_rule_digest",
        ),
        ("historical_warmup_index", "warmup_index_digest", "warmup_index_digest"),
        (
            "accepted_temporal_evaluation_index",
            "accepted_temporal_evaluation_index_digest",
            "accepted_temporal_evaluation_index_digest",
        ),
        ("composite_temporal_view", "composite_view_digest", "composite_view_digest"),
        (
            "q_base_checkpoint_index",
            "index_digest",
            "q_base_checkpoint_index_digest",
        ),
        ("joint_z_checkpoint_index", "index_digest", "joint_z_checkpoint_index_digest"),
        (
            "joint_target_prediction_index",
            "index_digest",
            "joint_target_prediction_index_digest",
        ),
        (
            "synthetic_warmup_application_or_null",
            "application_digest",
            "synthetic_warmup_application_digest_or_null",
        ),
    )
    for nested_field, digest_field, owner_field in equalities:
        item = nested.get(nested_field)
        if item is not None and item.get(digest_field) != body.get(owner_field):
            raise ResearchOSValidationError(
                f"nested owner digest mismatch: {nested_field}.{digest_field}"
            )
    composite = nested.get("composite_temporal_view")
    if composite is not None and (
        composite.get("warmup_index_digest") != body.get("warmup_index_digest")
        or composite.get("accepted_temporal_evaluation_index_digest")
        != body.get("accepted_temporal_evaluation_index_digest")
    ):
        raise ResearchOSValidationError("Temporal composite owner references changed")


def validate_m4_v2_artifact_envelope(
    value: Mapping[str, Any],
    *,
    expected_artifact_type: str | None = None,
) -> dict[str, Any]:
    """Validate a closed registered M4-v2 envelope and its owned members."""

    value = _mapping(value, field_name="M4-v2 artifact envelope")
    _m4_v2_require_exact_fields(
        value,
        (("schema_version", "artifact_type", "artifact_digest", "body", "parent_digests"),),
        field_name="M4-v2 artifact envelope",
    )
    artifact_type = _required_text(
        value.get("artifact_type"), field_name="artifact_type"
    )
    if expected_artifact_type is not None and artifact_type != expected_artifact_type:
        raise ResearchOSValidationError(
            f"unexpected artifact_type {artifact_type!r}; expected {expected_artifact_type!r}"
        )
    schema_version = _required_text(
        value.get("schema_version"), field_name="schema_version"
    )
    spec = _m4_v2_versioned_artifact_spec(artifact_type, schema_version)
    body = _mapping(value.get("body"), field_name=f"{artifact_type}.body")
    _m4_v2_require_exact_fields(
        body, (spec.body_fields,), field_name=f"{artifact_type}.body"
    )
    if body.get("measurement_contract_key") != M4_V2_MEASUREMENT_CONTRACT_KEY:
        raise ResearchOSValidationError("M4-v2 measurement contract key changed")
    if body.get("measurement_contract_digest") != M4_V2_MEASUREMENT_CONTRACT_DIGEST:
        raise ResearchOSValidationError("M4-v2 measurement contract digest changed")
    if spec.branch_id is not None and body.get("branch_id") != spec.branch_id:
        raise ResearchOSValidationError(f"{artifact_type} branch changed")
    branch_id = body.get("branch_id")
    if (
        branch_id in M4_V2_ESTIMAND_DIGESTS
        and body.get("estimand_digest") is not None
        and body["estimand_digest"] != M4_V2_ESTIMAND_DIGESTS[branch_id]
    ):
        raise ResearchOSValidationError(f"{artifact_type} estimand changed")
    if "production_action" in body and body["production_action"] != "none":
        raise ResearchOSValidationError("M4-v2 artifacts cannot take production action")
    _m4_v2_validate_digest_named_fields(body, field_name=f"{artifact_type}.body")

    raw_parents = value.get("parent_digests")
    if not isinstance(raw_parents, list) or not raw_parents:
        raise ResearchOSValidationError("parent_digests must be a non-empty array")
    parents = [
        _m4_v2_require_digest(item, field_name="parent digest")
        for item in raw_parents
    ]
    if len(parents) != len(set(parents)):
        raise ResearchOSValidationError("parent_digests contain an identity collision")
    nested: dict[str, Any] = {}
    for field_name, nested_schema in spec.nested_fields:
        nested[field_name] = validate_m4_v2_nested_schema(
            nested_schema, body[field_name]
        )
    _m4_v2_validate_nested_owner_equalities(body, nested)

    if artifact_type == M4_V2_BRANCH_DECISION_ARTIFACT_TYPE:
        _m4_v2_validate_branch_decision_body(body)
    elif artifact_type == M4_V2_BRANCH_DECISION_REPLAY_ARTIFACT_TYPE:
        _m4_v2_validate_branch_replay_body(body, parents)

    digest_input: Mapping[str, Any]
    if spec.body_only_digest:
        digest_input = body
    else:
        digest_input = {
            "schema_version": spec.schema_version,
            "artifact_type": artifact_type,
            "body": body,
            "parent_digests": parents,
        }
    calculated = m4_v2_domain_digest(digest_input, domain=spec.digest_domain)
    supplied = _m4_v2_require_digest(
        value.get("artifact_digest"), field_name="artifact_digest"
    )
    if supplied != calculated:
        raise ResearchOSValidationError(
            f"{artifact_type} artifact digest mismatch"
        )
    return json.loads(m4_v2_canonical_json(value))


def m4_v2_build_artifact_envelope(
    *,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
    schema_version: str | None = None,
) -> dict[str, Any]:
    """Build then validate an exact Request486 envelope."""

    base = M4_V2_ARTIFACT_TYPE_REGISTRY.get(artifact_type)
    if base is None:
        raise ResearchOSValidationError(f"unknown M4-v2 artifact_type: {artifact_type}")
    spec = _m4_v2_versioned_artifact_spec(
        artifact_type, schema_version or base.schema_version
    )
    primitive_body = json.loads(m4_v2_canonical_json(body))
    parents = list(parent_digests)
    digest_input = (
        primitive_body
        if spec.body_only_digest
        else {
            "schema_version": spec.schema_version,
            "artifact_type": artifact_type,
            "body": primitive_body,
            "parent_digests": parents,
        }
    )
    envelope = {
        "schema_version": spec.schema_version,
        "artifact_type": artifact_type,
        "artifact_digest": m4_v2_domain_digest(
            digest_input, domain=spec.digest_domain
        ),
        "body": primitive_body,
        "parent_digests": parents,
    }
    validate_m4_v2_artifact_envelope(
        envelope, expected_artifact_type=artifact_type
    )
    return envelope


@dataclass(frozen=True)
class M4V2BranchDecisionArtifact:
    measurement_contract_key: str
    measurement_contract_digest: str
    branch_id: str
    estimand_digest: str
    decision_path: str
    terminal_decision: str
    scientific_decision: str | None
    evaluation_status: str
    measurement_health: str
    historical_evidence: str
    accepted_for_downstream_baseline: bool
    accepted_model_artifact_digest: str | None
    baseline_artifact_digest: str | None
    baseline_source_model_artifact_digest: str | None
    producer_task_key: str
    producer_execution_id: str
    parent_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_m4_v2_artifact_envelope(
            self.to_dict(),
            expected_artifact_type=M4_V2_BRANCH_DECISION_ARTIFACT_TYPE,
        )

    def to_body(self) -> dict[str, Any]:
        return {
            field_name: getattr(self, field_name)
            for field_name in M4_V2_BRANCH_DECISION_BODY_FIELDS
        }

    @property
    def artifact_digest(self) -> str:
        return m4_v2_domain_digest(
            self.to_body(), domain=M4_V2_BRANCH_DECISION_DIGEST_DOMAIN
        )

    def to_dict(self) -> dict[str, Any]:
        return m4_v2_build_artifact_envelope(
            artifact_type=M4_V2_BRANCH_DECISION_ARTIFACT_TYPE,
            body=self.to_body(),
            parent_digests=self.parent_digests,
        )

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any]
    ) -> M4V2BranchDecisionArtifact:
        validated = validate_m4_v2_artifact_envelope(
            value,
            expected_artifact_type=M4_V2_BRANCH_DECISION_ARTIFACT_TYPE,
        )
        body = validated["body"]
        return cls(
            **{field_name: body[field_name] for field_name in M4_V2_BRANCH_DECISION_BODY_FIELDS},
            parent_digests=tuple(validated["parent_digests"]),
        )


@dataclass(frozen=True)
class M4V2BranchDecisionReplayArtifact:
    measurement_contract_key: str
    measurement_contract_digest: str
    branch_id: str
    decision_artifact_digest: str
    decision_registration_digest: str
    decision_producer_task_key: str
    decision_producer_execution_id: str
    replay_task_key: str
    replay_execution_id: str
    replay_status: str
    source_integrity_verified: bool
    registered_content_verified: bool
    workload_rerun: bool
    parent_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_m4_v2_artifact_envelope(
            self.to_dict(),
            expected_artifact_type=M4_V2_BRANCH_DECISION_REPLAY_ARTIFACT_TYPE,
        )

    def to_body(self) -> dict[str, Any]:
        return {
            field_name: getattr(self, field_name)
            for field_name in M4_V2_BRANCH_DECISION_REPLAY_BODY_FIELDS
        }

    @property
    def artifact_digest(self) -> str:
        return m4_v2_domain_digest(
            self.to_body(), domain=M4_V2_BRANCH_DECISION_REPLAY_DIGEST_DOMAIN
        )

    def to_dict(self) -> dict[str, Any]:
        return m4_v2_build_artifact_envelope(
            artifact_type=M4_V2_BRANCH_DECISION_REPLAY_ARTIFACT_TYPE,
            body=self.to_body(),
            parent_digests=self.parent_digests,
        )

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any]
    ) -> M4V2BranchDecisionReplayArtifact:
        validated = validate_m4_v2_artifact_envelope(
            value,
            expected_artifact_type=M4_V2_BRANCH_DECISION_REPLAY_ARTIFACT_TYPE,
        )
        body = validated["body"]
        return cls(
            **{
                field_name: body[field_name]
                for field_name in M4_V2_BRANCH_DECISION_REPLAY_BODY_FIELDS
            },
            parent_digests=tuple(validated["parent_digests"]),
        )
