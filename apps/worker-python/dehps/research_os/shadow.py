from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from dehps.research_os.compatibility import LEGACY_FORWARD_ACTIONS, project_legacy_wait_task
from dehps.research_os.models import (
    ControlPlaneManifest,
    ExternalExecutorObservation,
    ResearchOSValidationError,
)
from dehps.research_os.repository import ManifestImportResult, PostgresResearchOSRepository
from dehps.research_runtime.resident import legacy_supervisor_processes
from dehps.research_scheduler.repository import ResearchSchedulerRepository


Clock = Callable[[], datetime]
SupervisorObserver = Callable[[], tuple[str, ...]]


@dataclass(frozen=True)
class LegacyShadowRefreshResult:
    import_result: ManifestImportResult
    projected_wait_task_keys: tuple[str, ...]
    ignored_legacy_queue_keys: tuple[str, ...]
    external_observation_digests: tuple[str, ...]
    executor_state: str
    legacy_write_back: bool = False
    dispatch_performed: bool = False
    production_impact: str = "none"


class LegacyResearchOSShadowService:
    """Read legacy state once and persist a one-way Research OS shadow projection."""

    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository | None = None,
        legacy_repository: ResearchSchedulerRepository | None = None,
        supervisor_observer: SupervisorObserver | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.repository = repository or PostgresResearchOSRepository()
        self.legacy_repository = legacy_repository or ResearchSchedulerRepository()
        self.supervisor_observer = supervisor_observer or (
            lambda: legacy_supervisor_processes()
        )
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def refresh(
        self,
        *,
        control_plane_key: str,
        base_payload: dict[str, Any],
        legacy_goal_key: str,
    ) -> LegacyShadowRefreshResult:
        base = ControlPlaneManifest.from_dict(base_payload)
        goal = next((item for item in base.goals if item.goal_key == legacy_goal_key), None)
        if goal is None:
            raise ResearchOSValidationError(
                f"legacy shadow Goal not found in base manifest: {legacy_goal_key}"
            )
        payload = base.to_dict(include_digest=False)
        existing_task_keys = {str(item["task_key"]) for item in payload["tasks"]}
        projected: list[str] = []
        ignored: list[str] = []
        for item in self.legacy_repository.list_queue(limit=500, open_only=True):
            action = item.action.value
            if action not in LEGACY_FORWARD_ACTIONS:
                ignored.append(item.queue_key)
                continue
            task = project_legacy_wait_task(
                {
                    "queue_key": item.queue_key,
                    "action": action,
                    "priority_score": item.priority_score,
                    "reason": item.reason,
                },
                goal_key=goal.goal_key,
                goal_digest=goal.artifact_digest,
                lane=goal.owner_lane,
            )
            if task.task_key in existing_task_keys:
                continue
            payload["tasks"].append({**task.to_dict(), "status": "draft"})
            existing_task_keys.add(task.task_key)
            projected.append(task.task_key)

        imported = self.repository.import_manifest(
            control_plane_key=control_plane_key,
            payload=payload,
            source="legacy-shadow",
        )
        observation_digests: list[str] = []
        observed_at = self.clock().astimezone(timezone.utc).isoformat()
        processes = self.supervisor_observer()
        for process in processes:
            observation = self._observation(process, observed_at=observed_at)
            self.repository.record_external_executor_observation(
                control_plane_key=control_plane_key,
                observation=observation,
            )
            observation_digests.append(observation.artifact_digest)
        return LegacyShadowRefreshResult(
            import_result=imported,
            projected_wait_task_keys=tuple(sorted(projected)),
            ignored_legacy_queue_keys=tuple(sorted(ignored)),
            external_observation_digests=tuple(sorted(observation_digests)),
            executor_state="resource_or_executor_busy" if processes else "unobserved_or_idle",
        )

    @staticmethod
    def _observation(process: str, *, observed_at: str) -> ExternalExecutorObservation:
        stripped = str(process or "").strip()
        if not stripped:
            raise ResearchOSValidationError("legacy supervisor observation cannot be empty")
        first, _, command = stripped.partition(" ")
        try:
            pid = int(first)
        except ValueError:
            pid = None
            command = stripped
        return ExternalExecutorObservation(
            capability="historical_research",
            owner="legacy-supervisor",
            status="running",
            pid=pid,
            observed_at=observed_at,
            metadata=(
                ("command", command),
                ("scheduling_advisory", "resource_or_executor_busy"),
            ),
        )
