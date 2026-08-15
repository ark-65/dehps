from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.progress import (
    M4_V2_CONTRACT_DIGEST,
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.models import ResolutionSnapshot, TaskStatus
from dehps.research_os.supervisor import (
    M4_V2_DESIGN_TASK_KEY,
    P26_PREFLIGHT_TASK_KEY,
    P26_REPAIR_TASK_KEY,
    P26_TASK_KEY,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
CONTROL_PLANE_KEY = "m4-information-theory-mainline"


class _StaticControlPlane:
    def __init__(self, snapshot: ResolutionSnapshot) -> None:
        self.snapshot = snapshot

    def resolve(self, manifest: Any) -> ResolutionSnapshot:
        return replace(self.snapshot, manifest_digest=manifest.artifact_digest)


class _CompletedExecutionRepository:
    def __init__(
        self,
        *,
        snapshot: ResolutionSnapshot,
        events: tuple[dict[str, Any], ...],
    ) -> None:
        self.manifest = load_m4_manifest(MANIFEST_PATH)
        self.control_plane = _StaticControlPlane(snapshot)
        self.events = events

    def ensure_schema(self) -> None:
        return None

    def load_manifest(self, *, control_plane_key: str) -> Any:
        assert control_plane_key == CONTROL_PLANE_KEY
        return self.manifest

    def list_mainline_execution_events(
        self,
        *,
        control_plane_key: str,
        task_key: str | None = None,
        execution_id: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        assert control_plane_key == CONTROL_PLANE_KEY
        return tuple(
            event
            for event in self.events
            if (task_key is None or event["task_key"] == task_key)
            and (execution_id is None or event.get("execution_id") == execution_id)
        )


def _completed_event(task_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "control_plane_key": CONTROL_PLANE_KEY,
        "task_key": task_key,
        "event_type": "completed",
        "execution_id": f"{task_key}:execution",
        "payload": [[key, value] for key, value in payload.items()],
    }


def test_idle_heartbeat_retains_legacy_and_v2_execution_summaries(
    tmp_path: Path,
) -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    resolved = ResearchOSControlPlane().resolve(manifest)
    completed_keys = {P26_TASK_KEY, M4_V2_DESIGN_TASK_KEY}
    snapshot = replace(
        resolved,
        resolutions=tuple(
            (
                replace(item, status=TaskStatus.COMPLETED)
                if item.task_key in completed_keys
                else item
            )
            for item in resolved.resolutions
        ),
        ready_queue=(),
    )
    legacy_digest = "1" * 64
    v2_digest = "2" * 64
    repository = _CompletedExecutionRepository(
        snapshot=snapshot,
        events=(
            _completed_event(
                P26_TASK_KEY,
                {
                    "execution_artifact_digest": legacy_digest,
                    "registered_artifact_count": 64650000,
                    "actual_fold_count": 64650000,
                },
            ),
            _completed_event(
                M4_V2_DESIGN_TASK_KEY,
                {
                    "measurement_contract_v2_digest": M4_V2_CONTRACT_DIGEST,
                    "execution_artifact_digest": v2_digest,
                    "registered_artifact_count": 5,
                    "actual_fold_count": 0,
                },
            ),
        ),
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,
        control_plane_key=CONTROL_PLANE_KEY,
        root_dir=tmp_path,
        git_commit="a" * 40,
        require_clean_tree=False,
    )

    heartbeat = supervisor.run_once()

    assert heartbeat["status"] == "IDLE"
    status = json.loads(
        (tmp_path / "runtime/logs/m4-information-theory-status.json").read_text(
            encoding="utf-8"
        )
    )
    legacy_projection = status["mainline_integration"]
    assert legacy_projection["execution_artifact_digest"] == legacy_digest
    assert legacy_projection["registered_artifact_count"] == 64650000
    assert legacy_projection["actual_fold_count"] == 64650000
    assert status["measurement_system_v2"]["mainline_execution"] == {
        "execution_artifact_digest": v2_digest,
        "registered_artifact_count": 5,
        "actual_fold_count": 0,
    }


def test_running_projection_uses_repair_execution_not_preflight_summary(
    tmp_path: Path,
) -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    resolved = ResearchOSControlPlane().resolve(manifest)
    status_by_task = {
        P26_PREFLIGHT_TASK_KEY: TaskStatus.COMPLETED,
        P26_REPAIR_TASK_KEY: TaskStatus.COMPLETED,
        P26_TASK_KEY: TaskStatus.RUNNING,
    }
    snapshot = replace(
        resolved,
        resolutions=tuple(
            (
                replace(item, status=status_by_task[item.task_key])
                if item.task_key in status_by_task
                else item
            )
            for item in resolved.resolutions
        ),
        ready_queue=(),
    )
    preflight_digest = "3" * 64
    repair_digest = "4" * 64
    repository = _CompletedExecutionRepository(
        snapshot=snapshot,
        events=(
            _completed_event(
                P26_PREFLIGHT_TASK_KEY,
                {
                    "execution_artifact_digest": preflight_digest,
                    "registered_artifact_count": 2,
                    "actual_fold_count": 0,
                },
            ),
            _completed_event(
                P26_REPAIR_TASK_KEY,
                {
                    "execution_artifact_digest": repair_digest,
                    "registered_artifact_count": 8,
                    "actual_fold_count": 0,
                },
            ),
        ),
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,
        control_plane_key=CONTROL_PLANE_KEY,
        root_dir=tmp_path,
        git_commit="a" * 40,
        require_clean_tree=False,
    )

    summary = supervisor._latest_completed_summary(snapshot)
    assert summary is not None
    assert summary["execution_task_key"] == P26_REPAIR_TASK_KEY
    status = build_m4_status(
        manifest,
        snapshot=snapshot,
        mainline_execution=summary,
    )
    assert status["mainline_integration"]["task_key"] == P26_REPAIR_TASK_KEY
    assert status["mainline_integration"]["execution_artifact_digest"] == repair_digest
