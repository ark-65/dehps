from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from hashlib import sha256
from typing import Any, Mapping


RESEARCH_OS_SCHEMA_VERSION = "research-os-control-plane-v1"


class ResearchOSValidationError(ValueError):
    """Raised when a control-plane artifact cannot be trusted."""


class ObjectiveClass(str, Enum):
    PREDICTION_QUALITY = "prediction_quality"
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
    READY = "ready"
    DEPENDENCY_WAIT = "dependency_wait"
    EXTERNAL_WAIT = "external_wait"
    APPROVAL_WAIT = "approval_wait"
    COMPLETED = "completed"
    FAILED = "failed"
    SUPERSEDED = "superseded"


TERMINAL_TASK_STATUSES = frozenset(
    {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SUPERSEDED}
)


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


@dataclass(frozen=True)
class Goal:
    goal_key: str
    semantic_version: str
    objective_class: ObjectiveClass
    status: GoalStatus
    success_evidence: tuple[str, ...]
    owner_lane: TaskLane
    question: str = ""
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
            status=_enum(GoalStatus, value.get("status"), field_name="goal status"),
            success_evidence=tuple(
                _required_text(item, field_name="success_evidence item") for item in success
            ),
            owner_lane=_enum(TaskLane, value.get("owner_lane"), field_name="owner_lane"),
            question=str(value.get("question") or "").strip(),
            guardrails=tuple(str(item) for item in guardrails),
        )

    @property
    def artifact_digest(self) -> str:
        return stable_hash(
            {"schema": RESEARCH_OS_SCHEMA_VERSION, "artifact_type": "goal", "spec": self}
        )


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


@dataclass(frozen=True)
class Task:
    task_key: str
    goal_key: str
    task_type: str
    lane: TaskLane
    dependencies: tuple[TaskDependency, ...] = ()
    status: TaskStatus = TaskStatus.DRAFT
    priority: int = 0
    input_artifact_digests: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Task:
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
        return cls(
            task_key=_required_text(value.get("task_key"), field_name="task_key"),
            goal_key=_required_text(value.get("goal_key"), field_name="task goal_key"),
            task_type=_required_text(value.get("task_type"), field_name="task_type"),
            lane=_enum(TaskLane, value.get("lane"), field_name="task lane"),
            dependencies=dependencies,
            status=_enum(
                TaskStatus,
                value.get("status", TaskStatus.DRAFT.value),
                field_name="task status",
            ),
            priority=priority,
            input_artifact_digests=tuple(
                _required_text(item, field_name="input artifact digest") for item in raw_inputs
            ),
        )

    @property
    def artifact_digest(self) -> str:
        return stable_hash(
            {"schema": RESEARCH_OS_SCHEMA_VERSION, "artifact_type": "task", "spec": self}
        )


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


@dataclass(frozen=True)
class ControlPlaneManifest:
    goals: tuple[Goal, ...]
    tasks: tuple[Task, ...]
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
        return cls(
            goals=tuple(Goal.from_dict(item) for item in raw_goals),
            tasks=tuple(Task.from_dict(item) for item in raw_tasks),
            facts=DependencyFacts.from_dict(value.get("facts")),
            schema_version=schema,
        )

    @property
    def artifact_digest(self) -> str:
        return stable_hash(
            {
                "schema": self.schema_version,
                "artifact_type": "control_plane_manifest",
                "goals": self.goals,
                "tasks": self.tasks,
                "facts": self.facts,
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
