from datetime import datetime, timezone

from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.models import ControlPlaneManifest, TaskStatus
from dehps.research_os.repository import ManifestImportResult
from dehps.research_os.shadow import LegacyResearchOSShadowService
from dehps.research_scheduler.state import QueueStatus, ResearchAction, SchedulerQueueItem


def _goal(key: str, lane: str, objective: str) -> dict:
    return {
        "goal_key": key,
        "semantic_version": "1.0.0",
        "objective_class": objective,
        "status": "active",
        "success_evidence": [f"reviewed:{key}"],
        "owner_lane": lane,
    }


def _base_payload() -> dict:
    return {
        "schema_version": "research-os-control-plane-v1",
        "goals": [
            _goal("research", "research", "prediction_quality"),
            _goal("integrity", "maintenance", "maintenance_integrity"),
        ],
        "tasks": [
            {
                "task_key": "historical-replay",
                "goal_key": "research",
                "task_type": "replay",
                "lane": "research",
                "priority": 80,
            },
            {
                "task_key": "artifact-audit",
                "goal_key": "integrity",
                "task_type": "artifact_audit",
                "lane": "maintenance",
                "priority": 90,
            },
        ],
    }


class LegacyRepository:
    def __init__(self, items) -> None:
        self.items = items
        self.calls = []

    def list_queue(self, *, limit: int, open_only: bool):
        self.calls.append((limit, open_only))
        return self.items


class ShadowRepository:
    def __init__(self) -> None:
        self.payload = None
        self.observations = []

    def import_manifest(self, *, control_plane_key, payload, source):
        self.payload = payload
        manifest = ControlPlaneManifest.from_dict(payload)
        snapshot = ResearchOSControlPlane().resolve(manifest)
        return ManifestImportResult(
            control_plane_key=control_plane_key,
            manifest_digest=manifest.artifact_digest,
            snapshot_digest=snapshot.snapshot_digest,
            created_goal_definitions=len(manifest.goals),
            created_task_definitions=len(manifest.tasks),
            created_manifest=True,
            goal_revisions=(),
            task_revisions=(),
            ready_task_keys=tuple(item.task_key for item in snapshot.ready_queue),
        )

    def record_external_executor_observation(self, *, control_plane_key, observation):
        self.observations.append((control_plane_key, observation))
        return True


def _queue_item(*, key: str, action: ResearchAction, status: QueueStatus, reason: dict) -> SchedulerQueueItem:
    return SchedulerQueueItem(
        queue_key=key,
        queue_status=status,
        action=action,
        priority_score=0.1,
        context_fingerprint="legacy-context",
        reason=reason,
        budget={},
        policy={},
    )


def test_legacy_wait_and_running_supervisor_are_one_way_shadow_facts_not_global_blockers() -> None:
    legacy = LegacyRepository(
        [
            _queue_item(
                key="wait-2026083",
                action=ResearchAction.WAIT_FORWARD,
                status=QueueStatus.WAITING_FORWARD,
                reason={
                    "reason_code": "forward_evidence_insufficient",
                    "external_event_key": "draw:2026083",
                },
            ),
            _queue_item(
                key="proposal",
                action=ResearchAction.CREATE_PROPOSAL_REQUEST,
                status=QueueStatus.PROPOSAL,
                reason={"reason_code": "legacy_work"},
            ),
        ]
    )
    repository = ShadowRepository()
    service = LegacyResearchOSShadowService(
        repository=repository,  # type: ignore[arg-type]
        legacy_repository=legacy,  # type: ignore[arg-type]
        supervisor_observer=lambda: ("4242 scripts/run_training_supervisor.py",),
        clock=lambda: datetime(2026, 7, 21, 3, 0, tzinfo=timezone.utc),
    )

    result = service.refresh(
        control_plane_key="shadow",
        base_payload=_base_payload(),
        legacy_goal_key="research",
    )

    assert legacy.calls == [(500, True)]
    assert result.projected_wait_task_keys == ("legacy:wait-2026083",)
    assert result.ignored_legacy_queue_keys == ("proposal",)
    assert result.executor_state == "resource_or_executor_busy"
    assert result.legacy_write_back is False
    assert result.dispatch_performed is False
    assert len(repository.observations) == 1
    observation = repository.observations[0][1]
    assert observation.pid == 4242
    assert observation.owner == "legacy-supervisor"

    snapshot = ResearchOSControlPlane().resolve(
        ControlPlaneManifest.from_dict(repository.payload)
    )
    states = {item.task_key: item.status for item in snapshot.resolutions}
    assert states["legacy:wait-2026083"] is TaskStatus.EXTERNAL_WAIT
    assert states["historical-replay"] is TaskStatus.READY
    assert states["artifact-audit"] is TaskStatus.READY


def test_legacy_open_request_projects_to_approval_wait_only() -> None:
    legacy = LegacyRepository(
        [
            _queue_item(
                key="request-wait",
                action=ResearchAction.WAIT_FORWARD_PATTERN,
                status=QueueStatus.WAITING_FORWARD,
                reason={"reason_code": "open_agent_request", "request_key": "request-9"},
            )
        ]
    )
    repository = ShadowRepository()

    LegacyResearchOSShadowService(
        repository=repository,  # type: ignore[arg-type]
        legacy_repository=legacy,  # type: ignore[arg-type]
        supervisor_observer=lambda: (),
    ).refresh(
        control_plane_key="shadow",
        base_payload=_base_payload(),
        legacy_goal_key="research",
    )

    snapshot = ResearchOSControlPlane().resolve(
        ControlPlaneManifest.from_dict(repository.payload)
    )
    states = {item.task_key: item.status for item in snapshot.resolutions}
    assert states["legacy:request-wait"] is TaskStatus.APPROVAL_WAIT
    assert states["historical-replay"] is TaskStatus.READY
