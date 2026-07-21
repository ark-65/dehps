from __future__ import annotations

import copy
import os
import uuid
from contextlib import contextmanager

import psycopg
import pytest
from psycopg import sql

from dehps.config import get_settings
from dehps.research_os.models import (
    ControlPlaneManifest,
    ExternalExecutorObservation,
    ResearchOSValidationError,
    TaskStatus,
)
from dehps.research_os.repository import PostgresResearchOSRepository


pytestmark = pytest.mark.skipif(
    os.getenv("DEHPS_TEST_POSTGRES") != "1",
    reason="set DEHPS_TEST_POSTGRES=1 for isolated PostgreSQL repository acceptance",
)


def _goal(key: str, lane: str, objective: str) -> dict:
    return {
        "goal_key": key,
        "semantic_version": "1.0.0",
        "objective_class": objective,
        "status": "active",
        "baseline_metric_manifest": {"metric": "recent100", "value": [3, 3, 4]},
        "target_metric_manifest": {"metric": "recent100", "value": [4, 4, 5]},
        "success_evidence": [f"reviewed:{key}"],
        "owner_lane": lane,
        "guardrails": ["no_automatic_promotion"],
    }


def _manifest(*, draw_available: bool = False) -> dict:
    return {
        "schema_version": "research-os-control-plane-v1",
        "goals": [
            _goal("forward", "production", "prediction_quality"),
            _goal("research", "research", "prediction_quality"),
            _goal("integrity", "maintenance", "maintenance_integrity"),
        ],
        "tasks": [
            {
                "task_key": "evaluation-2026083",
                "goal_key": "forward",
                "task_type": "evaluation",
                "lane": "production",
                "priority": 100,
                "dependencies": [
                    {"dependency_type": "external_event", "target_key": "draw:2026083"}
                ],
            },
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
        "facts": {"external_events": ["draw:2026083"] if draw_available else []},
    }


@pytest.fixture
def postgres_repository():
    database_url = os.getenv("DEHPS_TEST_DATABASE_URL", get_settings().database_url)
    schema = f"research_os_p2_{uuid.uuid4().hex}"
    with psycopg.connect(database_url) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

    @contextmanager
    def connection_factory():
        with psycopg.connect(database_url) as connection:
            connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            yield connection

    repository = PostgresResearchOSRepository(connection_factory)  # type: ignore[arg-type]
    repository.ensure_schema()
    repository.ensure_schema()
    try:
        yield repository, connection_factory, schema
    finally:
        with psycopg.connect(database_url) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def _counts(connection_factory) -> dict[str, int]:
    tables = (
        "research_os_goal_definitions",
        "research_os_task_definitions",
        "research_os_manifests",
    )
    with connection_factory() as connection:
        return {
            table: int(connection.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))).fetchone()[0])
            for table in tables
        }


def test_manifest_import_is_idempotent_and_preserves_definition_revisions(postgres_repository) -> None:
    repository, connection_factory, _schema = postgres_repository
    payload = _manifest()

    first = repository.import_manifest(control_plane_key="p2", payload=payload)
    second = repository.import_manifest(control_plane_key="p2", payload=payload)

    assert first.created_goal_definitions == 3
    assert first.created_task_definitions == 3
    assert first.created_manifest is True
    assert second.created_goal_definitions == 0
    assert second.created_task_definitions == 0
    assert second.created_manifest is False
    assert _counts(connection_factory) == {
        "research_os_goal_definitions": 3,
        "research_os_task_definitions": 3,
        "research_os_manifests": 1,
    }

    task_revision = copy.deepcopy(payload)
    task_revision["tasks"][1]["priority"] = 81
    revised_task = repository.import_manifest(control_plane_key="p2", payload=task_revision)

    assert revised_task.created_goal_definitions == 0
    assert revised_task.created_task_definitions == 1
    assert len(revised_task.task_revisions) == 1
    assert revised_task.task_revisions[0][0] == "historical-replay"

    goal_revision = copy.deepcopy(task_revision)
    goal_revision["goals"][1]["target_metric_manifest"]["value"] = [5, 4, 5]
    revised_goal = repository.import_manifest(control_plane_key="p2", payload=goal_revision)

    assert revised_goal.created_goal_definitions == 1
    assert revised_goal.created_task_definitions == 1
    assert len(revised_goal.goal_revisions) == 1
    assert revised_goal.goal_revisions[0][0] == "research"
    assert _counts(connection_factory) == {
        "research_os_goal_definitions": 4,
        "research_os_task_definitions": 5,
        "research_os_manifests": 3,
    }


def test_restart_export_reimport_and_fact_update_preserve_identities(postgres_repository) -> None:
    repository, connection_factory, _schema = postgres_repository
    payload = _manifest()
    initial_manifest = ControlPlaneManifest.from_dict(payload)
    initial_task_digests = {task.task_key: task.artifact_digest for task in initial_manifest.tasks}

    imported = repository.import_manifest(control_plane_key="before-restart", payload=payload)
    restarted = PostgresResearchOSRepository(connection_factory)  # type: ignore[arg-type]
    recovered = restarted.resolve_persisted(control_plane_key="before-restart")

    assert recovered.manifest_digest == imported.manifest_digest
    assert recovered.snapshot_digest == imported.snapshot_digest
    assert tuple(item.task_key for item in recovered.ready_queue) == (
        "artifact-audit",
        "historical-replay",
    )
    states = {item.task_key: item.status for item in recovered.resolutions}
    assert states["evaluation-2026083"] is TaskStatus.EXTERNAL_WAIT

    exported = restarted.export_manifest(control_plane_key="before-restart")
    reimported = restarted.import_manifest(control_plane_key="after-reimport", payload=exported)
    assert reimported.manifest_digest == imported.manifest_digest
    assert reimported.snapshot_digest == imported.snapshot_digest

    with_draw = copy.deepcopy(exported)
    with_draw.pop("manifest_digest")
    with_draw["facts"]["external_events"] = ["draw:2026083"]
    updated = restarted.import_manifest(control_plane_key="before-restart", payload=with_draw)
    updated_manifest = restarted.load_manifest(control_plane_key="before-restart")
    updated_task_digests = {task.task_key: task.artifact_digest for task in updated_manifest.tasks}

    assert updated_task_digests == initial_task_digests
    assert updated.manifest_digest != imported.manifest_digest
    assert updated.snapshot_digest != imported.snapshot_digest
    assert tuple(item.task_key for item in restarted.resolve_persisted(control_plane_key="before-restart").ready_queue) == (
        "evaluation-2026083",
        "artifact-audit",
        "historical-replay",
    )


def test_repository_corruption_and_digest_mismatch_fail_closed(postgres_repository) -> None:
    repository, connection_factory, _schema = postgres_repository
    imported = repository.import_manifest(control_plane_key="corrupt", payload=_manifest())

    with connection_factory() as connection:
        connection.execute(
            """
            UPDATE research_os_task_states
            SET resolved_status = 'ready'
            WHERE control_plane_key = 'corrupt'
              AND reason_code = 'external_event_dependency_unsatisfied'
            """
        )
    with pytest.raises(ResearchOSValidationError, match="state projection mismatch"):
        repository.resolve_persisted(control_plane_key="corrupt")

    repository.import_manifest(control_plane_key="corrupt", payload=_manifest())
    with connection_factory() as connection:
        connection.execute(
            "ALTER TABLE research_os_manifests DISABLE TRIGGER research_os_manifests_immutable"
        )
        connection.execute(
            """
            UPDATE research_os_manifests
            SET manifest_json = jsonb_set(manifest_json, '{facts,external_events}', '["draw:tampered"]'::jsonb)
            WHERE manifest_digest = %s
            """,
            (imported.manifest_digest,),
        )
        connection.execute(
            "ALTER TABLE research_os_manifests ENABLE TRIGGER research_os_manifests_immutable"
        )
    with pytest.raises(ResearchOSValidationError, match="immutable manifest payload mismatch"):
        repository.resolve_persisted(control_plane_key="corrupt")

    bad_export = _manifest()
    bad_export["manifest_digest"] = "0" * 64
    with pytest.raises(ResearchOSValidationError, match="manifest digest mismatch"):
        repository.import_manifest(control_plane_key="bad", payload=bad_export)


def test_external_executor_observation_is_append_only_and_does_not_block_resolution(
    postgres_repository,
) -> None:
    repository, _connection_factory, _schema = postgres_repository
    imported = repository.import_manifest(control_plane_key="legacy-shadow", payload=_manifest())
    before = repository.resolve_persisted(control_plane_key="legacy-shadow")
    observation = ExternalExecutorObservation(
        capability="historical_research",
        owner="legacy-supervisor",
        status="running",
        pid=4242,
        observed_at="2026-07-21T03:00:00+00:00",
        metadata=(
            ("command", "scripts/run_training_supervisor.py"),
            ("scheduling_advisory", "resource_or_executor_busy"),
        ),
    )

    assert repository.record_external_executor_observation(
        control_plane_key="legacy-shadow", observation=observation
    ) is True
    assert repository.record_external_executor_observation(
        control_plane_key="legacy-shadow", observation=observation
    ) is False
    stored = repository.list_external_executor_observations(control_plane_key="legacy-shadow")
    after = repository.resolve_persisted(control_plane_key="legacy-shadow")

    assert len(stored) == 1
    assert stored[0]["observation_digest"] == observation.artifact_digest
    assert stored[0]["capability"] == "historical_research"
    assert stored[0]["owner"] == "legacy-supervisor"
    assert stored[0]["status"] == "running"
    assert stored[0]["pid"] == 4242
    assert ["scheduling_advisory", "resource_or_executor_busy"] in stored[0]["metadata"]
    assert after.manifest_digest == imported.manifest_digest == before.manifest_digest
    assert after.snapshot_digest == imported.snapshot_digest == before.snapshot_digest
    assert tuple(item.task_key for item in after.ready_queue) == (
        "artifact-audit",
        "historical-replay",
    )
