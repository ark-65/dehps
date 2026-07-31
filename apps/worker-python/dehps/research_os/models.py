from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Any

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
