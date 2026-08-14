from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.db import get_connection
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.mainline import completion_execution_ids
from dehps.research_os.models import (
    ControlPlaneManifest,
    ExternalExecutorObservation,
    Goal,
    MainlineArtifactRegistration,
    MainlineExecutionEvent,
    ResearchOSValidationError,
    ResolutionSnapshot,
    Task,
    TaskResolution,
    jsonable,
    stable_json,
)
from dehps.storage.postgres_store import ensure_research_os_schema

ConnectionFactory = Callable[[], AbstractContextManager[Connection[Any]]]

_M4_V2_GLOBAL_RECOVERY_V2_BUILDER_MODULE_NAME = (
    "_dehps_m4_v2_global_routing_recovery_v2_builder"
)
_M4_V2_GLOBAL_RECOVERY_V2_REQUIRED_SYMBOLS = (
    "GLOBAL_SOURCE_PATH",
    "INPUT_MANIFEST_DIGEST",
    "OLD_EVENT_MANIFEST_DIGEST",
    "OLD_EXECUTION_ID",
    "OLD_FAILED_EVENT_DIGEST",
    "OLD_STARTED_EVENT_DIGEST",
    "OLD_TASK_DIGEST",
    "OLD_TASK_KEY",
    "P3_REVISIONS",
    "RECOVERY_TASK_KEY",
    "GlobalRoutingRecoveryV2Error",
    "build_manifest",
    "validate_global_source_contract",
)


def _load_m4_v2_global_routing_recovery_v2_builder() -> ModuleType:
    """Load the singular recovery-v2 builder without depending on cwd imports."""

    from dehps.config import ROOT_DIR

    try:
        root_dir = ROOT_DIR.resolve()
        builder_path = (
            ROOT_DIR
            / "apps/worker-python/scripts/"
            "build_m4_v2_global_routing_recovery_v2_manifest.py"
        ).resolve()
        if not builder_path.is_relative_to(root_dir):
            raise ValueError(str(builder_path))
        if not builder_path.is_file():
            raise FileNotFoundError(builder_path)
        spec = importlib.util.spec_from_file_location(
            _M4_V2_GLOBAL_RECOVERY_V2_BUILDER_MODULE_NAME,
            builder_path,
        )
        if spec is None:
            raise ImportError("m4_v2_global_recovery_v2_builder_spec_unavailable")
        if spec.loader is None:
            raise ImportError("m4_v2_global_recovery_v2_builder_loader_unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for symbol in _M4_V2_GLOBAL_RECOVERY_V2_REQUIRED_SYMBOLS:
            if not hasattr(module, symbol):
                raise AttributeError(symbol)
        for symbol in ("build_manifest", "validate_global_source_contract"):
            if not callable(getattr(module, symbol)):
                raise TypeError(symbol)
        error_class = module.GlobalRoutingRecoveryV2Error
        if not isinstance(error_class, type) or not issubclass(
            error_class, BaseException
        ):
            raise TypeError("GlobalRoutingRecoveryV2Error")
        return module
    except Exception as exc:
        raise ResearchOSValidationError(
            "m4_v2_global_recovery_v2_builder_unavailable"
        ) from exc


def _json(value: Any) -> str:
    return json.dumps(jsonable(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class ManifestImportResult:
    control_plane_key: str
    manifest_digest: str
    snapshot_digest: str
    created_goal_definitions: int
    created_task_definitions: int
    created_manifest: bool
    goal_revisions: tuple[tuple[str, str, str], ...]
    task_revisions: tuple[tuple[str, str, str], ...]
    ready_task_keys: tuple[str, ...]
    dispatch_performed: bool = False
    production_impact: str = "none"


class PostgresResearchOSRepository:
    """Durable P2 shadow repository; it never dispatches or writes legacy state."""

    def __init__(
        self,
        connection_factory: ConnectionFactory = get_connection,
        *,
        control_plane: ResearchOSControlPlane | None = None,
    ) -> None:
        self.connection_factory = connection_factory
        self.control_plane = control_plane or ResearchOSControlPlane()

    def ensure_schema(self) -> None:
        with self.connection_factory() as conn:
            ensure_research_os_schema(conn)

    def import_manifest(
        self,
        *,
        control_plane_key: str,
        payload: dict[str, Any],
        source: str = "native",
    ) -> ManifestImportResult:
        key = self._key(control_plane_key)
        source = self._key(source)
        manifest = ControlPlaneManifest.from_dict(payload)
        snapshot = self.control_plane.resolve(manifest)
        normalized_payload = manifest.to_dict(include_digest=False)
        resolutions = {item.task_digest: item for item in snapshot.resolutions}

        created_goals = 0
        created_tasks = 0
        created_manifest = False
        goal_revisions: list[tuple[str, str, str]] = []
        task_revisions: list[tuple[str, str, str]] = []

        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            self._verify_m4_v2_failed_global_routing_recovery_v2_import(
                cursor, control_plane_key=key, manifest=manifest
            )
            self._verify_m4_v2_failed_global_routing_recovery_import(
                cursor, control_plane_key=key, manifest=manifest
            )
            replay_recovery = self._verify_m4_v2_failed_replay_recovery_import(
                cursor, control_plane_key=key, manifest=manifest
            )
            if not replay_recovery:
                self._verify_m4_v2_failed_task_recovery_import(
                    cursor,
                    control_plane_key=key,
                    manifest=manifest,
                )
            self._verify_mainline_completion_records(
                cursor,
                control_plane_key=key,
                manifest=manifest,
            )
            previous_goals, previous_tasks = self._current_revisions(cursor, key)
            self._verify_no_mainline_completion_regression(
                cursor,
                control_plane_key=key,
                manifest=manifest,
                previous_tasks=previous_tasks,
            )
            for goal in manifest.goals:
                inserted = cursor.execute(
                    """
                    INSERT INTO research_os_goal_definitions (
                      goal_digest, goal_key, semantic_version, objective_class,
                      owner_lane, definition_json
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (goal_digest) DO NOTHING
                    RETURNING goal_digest
                    """,
                    (
                        goal.artifact_digest,
                        goal.goal_key,
                        goal.semantic_version,
                        goal.objective_class.value,
                        goal.owner_lane.value,
                        _json(goal.to_dict()),
                    ),
                ).fetchone()
                created_goals += int(inserted is not None)
                self._verify_goal_definition(cursor, goal)

            for task in manifest.tasks:
                inserted = cursor.execute(
                    """
                    INSERT INTO research_os_task_definitions (
                      task_digest, task_key, goal_digest, task_type, lane,
                      priority, definition_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (task_digest) DO NOTHING
                    RETURNING task_digest
                    """,
                    (
                        task.artifact_digest,
                        task.task_key,
                        task.goal_digest,
                        task.task_type,
                        task.lane.value,
                        task.priority,
                        _json(task.to_dict()),
                    ),
                ).fetchone()
                created_tasks += int(inserted is not None)
                self._verify_task_definition(cursor, task)

            inserted_manifest = cursor.execute(
                """
                INSERT INTO research_os_manifests (
                  manifest_digest, schema_version, manifest_json, source
                ) VALUES (%s, %s, %s::jsonb, %s)
                ON CONFLICT (manifest_digest) DO NOTHING
                RETURNING manifest_digest
                """,
                (
                    manifest.artifact_digest,
                    manifest.schema_version,
                    _json(normalized_payload),
                    source,
                ),
            ).fetchone()
            created_manifest = inserted_manifest is not None
            self._verify_manifest_row(cursor, manifest)

            for ordinal, goal in enumerate(manifest.goals):
                cursor.execute(
                    """
                    INSERT INTO research_os_manifest_goals (manifest_digest, goal_digest, ordinal)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (manifest.artifact_digest, goal.artifact_digest, ordinal),
                )
            for ordinal, task in enumerate(manifest.tasks):
                cursor.execute(
                    """
                    INSERT INTO research_os_manifest_tasks (manifest_digest, task_digest, ordinal)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (manifest.artifact_digest, task.artifact_digest, ordinal),
                )

            cursor.execute(
                """
                INSERT INTO research_os_control_planes (
                  control_plane_key, schema_version, current_manifest_digest, source
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (control_plane_key) DO UPDATE
                SET schema_version = EXCLUDED.schema_version,
                    current_manifest_digest = EXCLUDED.current_manifest_digest,
                    source = EXCLUDED.source,
                    updated_at = now()
                """,
                (key, manifest.schema_version, manifest.artifact_digest, source),
            )

            current_goals = {goal.goal_key: goal.artifact_digest for goal in manifest.goals}
            current_tasks = {task.task_key: task.artifact_digest for task in manifest.tasks}
            for goal_key, old_digest in previous_goals.items():
                new_digest = current_goals.get(goal_key)
                if new_digest and new_digest != old_digest:
                    goal_revisions.append((goal_key, old_digest, new_digest))
                    cursor.execute(
                        """
                        UPDATE research_os_goal_states
                        SET status = 'retired', retired_at = COALESCE(retired_at, now()),
                            superseded_by_goal_digest = %s, updated_at = now()
                        WHERE control_plane_key = %s AND goal_digest = %s
                        """,
                        (new_digest, key, old_digest),
                    )
            for task_key, old_digest in previous_tasks.items():
                new_digest = current_tasks.get(task_key)
                if new_digest and new_digest != old_digest:
                    task_revisions.append((task_key, old_digest, new_digest))
                    cursor.execute(
                        """
                        UPDATE research_os_task_states
                        SET declared_status = 'superseded', resolved_status = 'superseded',
                            reason_code = 'definition_superseded',
                            dependency_state_json = '[]'::jsonb,
                            superseded_by_task_digest = %s, updated_at = now()
                        WHERE control_plane_key = %s AND task_digest = %s
                        """,
                        (new_digest, key, old_digest),
                    )

            goal_states = manifest.goal_state_by_digest
            for goal in manifest.goals:
                state = goal_states[goal.artifact_digest]
                cursor.execute(
                    """
                    INSERT INTO research_os_goal_states (
                      control_plane_key, goal_digest, status, retired_at,
                      superseded_by_goal_digest
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (control_plane_key, goal_digest) DO UPDATE
                    SET status = EXCLUDED.status,
                        retired_at = EXCLUDED.retired_at,
                        superseded_by_goal_digest = EXCLUDED.superseded_by_goal_digest,
                        updated_at = now()
                    """,
                    (
                        key,
                        goal.artifact_digest,
                        state.status.value,
                        state.retired_at,
                        state.superseded_by_goal_digest,
                    ),
                )

            task_states = manifest.task_state_by_digest
            for task in manifest.tasks:
                state = task_states[task.artifact_digest]
                resolution = resolutions[task.artifact_digest]
                cursor.execute(
                    """
                    INSERT INTO research_os_task_states (
                      control_plane_key, task_digest, declared_status, resolved_status,
                      completion_classification, reason_code, dependency_state_json,
                      superseded_by_task_digest
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (control_plane_key, task_digest) DO UPDATE
                    SET declared_status = EXCLUDED.declared_status,
                        resolved_status = EXCLUDED.resolved_status,
                        completion_classification = EXCLUDED.completion_classification,
                        reason_code = EXCLUDED.reason_code,
                        dependency_state_json = EXCLUDED.dependency_state_json,
                        superseded_by_task_digest = EXCLUDED.superseded_by_task_digest,
                        updated_at = now()
                    """,
                    (
                        key,
                        task.artifact_digest,
                        state.declared_status.value,
                        resolution.status.value,
                        (
                            None
                            if state.completion_classification is None
                            else state.completion_classification.value
                        ),
                        resolution.reason_code,
                        _json(resolution.unsatisfied_dependencies),
                        state.superseded_by_task_digest,
                    ),
                )

            cursor.execute(
                "DELETE FROM research_os_dependency_facts WHERE control_plane_key = %s",
                (key,),
            )
            for fact_type, fact_key in self._fact_rows(manifest):
                cursor.execute(
                    """
                    INSERT INTO research_os_dependency_facts (
                      control_plane_key, fact_type, fact_key
                    ) VALUES (%s, %s, %s)
                    """,
                    (key, fact_type, fact_key),
                )

        return ManifestImportResult(
            control_plane_key=key,
            manifest_digest=manifest.artifact_digest,
            snapshot_digest=snapshot.snapshot_digest,
            created_goal_definitions=created_goals,
            created_task_definitions=created_tasks,
            created_manifest=created_manifest,
            goal_revisions=tuple(goal_revisions),
            task_revisions=tuple(task_revisions),
            ready_task_keys=tuple(item.task_key for item in snapshot.ready_queue),
        )

    @staticmethod
    def _verify_m4_v2_failed_task_recovery_import(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
    ) -> None:
        """Bind the frozen failed lineage before the recovery transaction writes."""

        from dehps.research_os.information_theory.measurement_system_v2.migration import (
            M4_V2_FAILED_EXECUTION_ID,
            M4_V2_FAILED_TASK_KEY,
            M4_V2_ORIGINAL_TASK_DEFINITIONS,
            M4_V2_RECOVERY_INPUT_MANIFEST_DIGEST,
            M4_V2_RECOVERY_TASK_KEY,
            AdditiveManifestMigrationError,
            verify_failed_task_recovery_event_metadata,
        )

        canonical_control_plane_key = "m4-information-theory-mainline"
        task_keys = {task.task_key for task in manifest.tasks}
        if (
            control_plane_key != canonical_control_plane_key
            or M4_V2_RECOVERY_TASK_KEY not in task_keys
        ):
            return
        if M4_V2_FAILED_TASK_KEY in task_keys:
            raise ResearchOSValidationError(
                "m4_v2_recovery_old_failed_task_still_active"
            )

        control = cursor.execute(
            """
            SELECT current_manifest_digest
            FROM research_os_control_planes
            WHERE control_plane_key = %s
            FOR UPDATE
            """,
            (control_plane_key,),
        ).fetchone()
        if control is None:
            raise ResearchOSValidationError(
                "m4_v2_recovery_control_plane_not_initialized"
            )
        current_manifest_digest = str(control["current_manifest_digest"])
        if current_manifest_digest not in {
            M4_V2_RECOVERY_INPUT_MANIFEST_DIGEST,
            manifest.artifact_digest,
        }:
            stored = cursor.execute(
                """
                SELECT manifest_json
                FROM research_os_manifests
                WHERE manifest_digest = %s
                """,
                (current_manifest_digest,),
            ).fetchone()
            if stored is None:
                raise ResearchOSValidationError(
                    "m4_v2_recovery_current_manifest_missing"
                )
            current_manifest = ControlPlaneManifest.from_dict(
                dict(stored["manifest_json"])
            )
            current_tasks = {
                task.task_key: task.artifact_digest for task in current_manifest.tasks
            }
            incoming_tasks = {
                task.task_key: task.artifact_digest for task in manifest.tasks
            }
            successor_keys = {
                key for key, _digest in M4_V2_ORIGINAL_TASK_DEFINITIONS
            }
            successor_keys.remove(M4_V2_FAILED_TASK_KEY)
            successor_keys.add(M4_V2_RECOVERY_TASK_KEY)
            if (
                M4_V2_FAILED_TASK_KEY in current_tasks
                or not successor_keys.issubset(current_tasks)
                or any(
                    current_tasks[key] != incoming_tasks.get(key)
                    for key in successor_keys
                )
            ):
                raise ResearchOSValidationError(
                    "m4_v2_recovery_current_manifest_lineage_changed"
                )

        original_task_digest = dict(M4_V2_ORIGINAL_TASK_DEFINITIONS)[
            M4_V2_FAILED_TASK_KEY
        ]
        state = cursor.execute(
            """
            SELECT td.task_digest, ts.declared_status,
                   ts.completion_classification, ts.superseded_by_task_digest
            FROM research_os_task_definitions td
            JOIN research_os_task_states ts ON ts.task_digest = td.task_digest
            WHERE ts.control_plane_key = %s
              AND td.task_key = %s
              AND td.task_digest = %s
            """,
            (
                control_plane_key,
                M4_V2_FAILED_TASK_KEY,
                original_task_digest,
            ),
        ).fetchone()
        if (
            state is None
            or str(state["task_digest"]) != original_task_digest
            or str(state["declared_status"]) != "failed"
            or str(state["completion_classification"]) != "INTEGRATED"
            or state["superseded_by_task_digest"] is not None
        ):
            raise ResearchOSValidationError(
                "m4_v2_recovery_failed_task_state_changed"
            )

        rows = cursor.execute(
            """
            SELECT event_digest, execution_id, control_plane_key,
                   manifest_digest, task_digest, task_key, capability,
                   event_type, sequence
            FROM research_os_mainline_execution_events
            WHERE control_plane_key = %s
              AND task_key = %s
              AND execution_id = %s
            ORDER BY sequence, event_digest
            """,
            (
                control_plane_key,
                M4_V2_FAILED_TASK_KEY,
                M4_V2_FAILED_EXECUTION_ID,
            ),
        ).fetchall()
        try:
            verify_failed_task_recovery_event_metadata(tuple(dict(row) for row in rows))
        except AdditiveManifestMigrationError as exc:
            raise ResearchOSValidationError(str(exc)) from exc

    @staticmethod
    def _verify_m4_v2_failed_replay_recovery_import(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
    ) -> bool:
        """Verify the append-only failed replay lineage before any import write."""

        from dehps.research_os.information_theory.measurement_system_v2.migration import (
            M4_V2_FAILED_REPLAY_EXECUTION_ID,
            M4_V2_FAILED_REPLAY_OLDER_TASK_DIGEST,
            M4_V2_FAILED_REPLAY_TASK_DIGEST,
            M4_V2_FAILED_REPLAY_TASK_KEY,
            M4_V2_REPLAY_RECOVERY_INPUT_MANIFEST_DIGEST,
            M4_V2_REPLAY_RECOVERY_TASK_KEY,
            AdditiveManifestMigrationError,
            verify_failed_replay_recovery_event_metadata,
        )

        task_by_key = {task.task_key: task for task in manifest.tasks}
        recovery = task_by_key.get(M4_V2_REPLAY_RECOVERY_TASK_KEY)
        if recovery is None:
            return False
        if control_plane_key != "m4-information-theory-mainline":
            raise ResearchOSValidationError(
                "m4_v2_replay_recovery_control_plane_changed"
            )
        if M4_V2_FAILED_REPLAY_TASK_KEY in task_by_key:
            raise ResearchOSValidationError(
                "m4_v2_replay_recovery_old_failed_task_still_active"
            )

        control = cursor.execute(
            """
            SELECT current_manifest_digest
            FROM research_os_control_planes
            WHERE control_plane_key = %s
            FOR UPDATE
            """,
            (control_plane_key,),
        ).fetchone()
        if control is None:
            raise ResearchOSValidationError(
                "m4_v2_replay_recovery_control_plane_not_initialized"
            )
        current_manifest_digest = str(control["current_manifest_digest"])
        if current_manifest_digest not in {
            M4_V2_REPLAY_RECOVERY_INPUT_MANIFEST_DIGEST,
            manifest.artifact_digest,
        }:
            stored = cursor.execute(
                """
                SELECT manifest_json
                FROM research_os_manifests
                WHERE manifest_digest = %s
                """,
                (current_manifest_digest,),
            ).fetchone()
            if stored is None:
                raise ResearchOSValidationError(
                    "m4_v2_replay_recovery_current_manifest_missing"
                )
            current_manifest = ControlPlaneManifest.from_dict(
                dict(stored["manifest_json"])
            )
            current_by_key = {
                task.task_key: task.artifact_digest
                for task in current_manifest.tasks
            }
            if (
                M4_V2_FAILED_REPLAY_TASK_KEY in current_by_key
                or current_by_key.get(M4_V2_REPLAY_RECOVERY_TASK_KEY)
                != recovery.artifact_digest
            ):
                raise ResearchOSValidationError(
                    "m4_v2_replay_recovery_current_manifest_lineage_changed"
                )

        states = cursor.execute(
            """
            SELECT td.task_digest, ts.declared_status,
                   ts.completion_classification, ts.superseded_by_task_digest
            FROM research_os_task_definitions td
            JOIN research_os_task_states ts ON ts.task_digest = td.task_digest
            WHERE ts.control_plane_key = %s
              AND td.task_key = %s
              AND td.task_digest IN (%s, %s)
            ORDER BY td.task_digest
            """,
            (
                control_plane_key,
                M4_V2_FAILED_REPLAY_TASK_KEY,
                M4_V2_FAILED_REPLAY_TASK_DIGEST,
                M4_V2_FAILED_REPLAY_OLDER_TASK_DIGEST,
            ),
        ).fetchall()
        state_by_digest = {str(row["task_digest"]): row for row in states}
        active = state_by_digest.get(M4_V2_FAILED_REPLAY_TASK_DIGEST)
        older = state_by_digest.get(M4_V2_FAILED_REPLAY_OLDER_TASK_DIGEST)
        if (
            active is None
            or str(active["declared_status"]) != "failed"
            or str(active["completion_classification"]) != "INTEGRATED"
            or active["superseded_by_task_digest"] is not None
            or older is None
            or str(older["declared_status"]) != "superseded"
            or str(older["completion_classification"]) != "INTEGRATION_PENDING"
            or str(older["superseded_by_task_digest"])
            != M4_V2_FAILED_REPLAY_TASK_DIGEST
        ):
            raise ResearchOSValidationError(
                "m4_v2_replay_recovery_failed_task_lineage_changed"
            )

        rows = cursor.execute(
            """
            SELECT event_digest, execution_id, control_plane_key,
                   manifest_digest, task_digest, task_key, capability,
                   event_type, sequence
            FROM research_os_mainline_execution_events
            WHERE control_plane_key = %s
              AND task_key = %s
              AND execution_id = %s
            ORDER BY sequence, event_digest
            """,
            (
                control_plane_key,
                M4_V2_FAILED_REPLAY_TASK_KEY,
                M4_V2_FAILED_REPLAY_EXECUTION_ID,
            ),
        ).fetchall()
        try:
            verify_failed_replay_recovery_event_metadata(
                tuple(dict(row) for row in rows)
            )
        except AdditiveManifestMigrationError as exc:
            raise ResearchOSValidationError(str(exc)) from exc
        return True

    @staticmethod
    def _verify_m4_v2_failed_global_routing_recovery_v2_import(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
    ) -> None:
        """Verify the exact failed recovery-v1 lineage before the first write."""

        from dehps.config import ROOT_DIR

        builder = _load_m4_v2_global_routing_recovery_v2_builder()
        GLOBAL_SOURCE_PATH = builder.GLOBAL_SOURCE_PATH
        INPUT_MANIFEST_DIGEST = builder.INPUT_MANIFEST_DIGEST
        OLD_EVENT_MANIFEST_DIGEST = builder.OLD_EVENT_MANIFEST_DIGEST
        OLD_EXECUTION_ID = builder.OLD_EXECUTION_ID
        OLD_FAILED_EVENT_DIGEST = builder.OLD_FAILED_EVENT_DIGEST
        OLD_STARTED_EVENT_DIGEST = builder.OLD_STARTED_EVENT_DIGEST
        OLD_TASK_DIGEST = builder.OLD_TASK_DIGEST
        OLD_TASK_KEY = builder.OLD_TASK_KEY
        P3_REVISIONS = builder.P3_REVISIONS
        RECOVERY_TASK_KEY = builder.RECOVERY_TASK_KEY
        GlobalRoutingRecoveryV2Error = builder.GlobalRoutingRecoveryV2Error
        build_manifest = builder.build_manifest
        validate_global_source_contract = builder.validate_global_source_contract
        tasks = {task.task_key: task for task in manifest.tasks}
        recovery = tasks.get(RECOVERY_TASK_KEY)
        if recovery is None:
            return
        if control_plane_key != "m4-information-theory-mainline":
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_control_plane_changed"
            )
        if OLD_TASK_KEY in tasks or len(recovery.input_artifact_digests) != 1:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_task_identity_changed"
            )

        control = cursor.execute(
            """SELECT current_manifest_digest FROM research_os_control_planes
               WHERE control_plane_key = %s FOR UPDATE""",
            (control_plane_key,),
        ).fetchone()
        if control is None:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_control_plane_missing"
            )
        current_digest = str(control["current_manifest_digest"])
        baseline_row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (INPUT_MANIFEST_DIGEST,),
        ).fetchone()
        if baseline_row is None:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_input_manifest_missing"
            )
        try:
            baseline = ControlPlaneManifest.from_dict(
                dict(baseline_row["manifest_json"])
            )
        except (KeyError, TypeError, ValueError, ResearchOSValidationError) as exc:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_input_manifest_changed"
            ) from exc
        baseline_old = tuple(
            task for task in baseline.tasks if task.task_key == OLD_TASK_KEY
        )
        if (
            baseline.artifact_digest != INPUT_MANIFEST_DIGEST
            or len(baseline_old) != 1
            or baseline_old[0].artifact_digest != OLD_TASK_DIGEST
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_input_manifest_changed"
            )
        definition = cursor.execute(
            """SELECT task_digest, task_key, definition_json
               FROM research_os_task_definitions WHERE task_digest = %s""",
            (OLD_TASK_DIGEST,),
        ).fetchone()
        if (
            definition is None
            or str(definition["task_digest"]) != OLD_TASK_DIGEST
            or str(definition["task_key"]) != OLD_TASK_KEY
            or dict(definition["definition_json"]) != baseline_old[0].to_dict()
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_old_definition_changed"
            )
        stored = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (current_digest,),
        ).fetchone()
        if stored is None:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_manifest_missing"
            )
        current = ControlPlaneManifest.from_dict(dict(stored["manifest_json"]))
        source_path = ROOT_DIR / GLOBAL_SOURCE_PATH
        try:
            source_payload = json.loads(source_path.read_text(encoding="utf-8"))
            source_digest = validate_global_source_contract(
                source_payload, root_dir=ROOT_DIR
            )
        except (OSError, ValueError, TypeError, GlobalRoutingRecoveryV2Error) as exc:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_source_changed"
            ) from exc
        if recovery.input_artifact_digests != (source_digest,):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_source_changed"
            )
        expected, _ = build_manifest(
            baseline.to_dict(include_digest=True),
            global_source_contract_digest=source_digest,
        )
        expected_digest = str(expected["manifest_digest"])
        if manifest.to_dict(include_digest=True) != expected:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_output_changed"
            )
        if current_digest not in {INPUT_MANIFEST_DIGEST, expected_digest}:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_current_manifest_changed"
            )
        if (
            current_digest == expected_digest
            and current.to_dict(include_digest=True) != expected
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_current_manifest_changed"
            )

        state = cursor.execute(
            """SELECT ts.declared_status, ts.completion_classification,
                      ts.superseded_by_task_digest
               FROM research_os_task_states ts
               WHERE ts.control_plane_key = %s AND ts.task_digest = %s""",
            (control_plane_key, OLD_TASK_DIGEST),
        ).fetchone()
        if (
            state is None
            or str(state["declared_status"]) != "failed"
            or str(state["completion_classification"]) != "INTEGRATED"
            or state["superseded_by_task_digest"] is not None
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_old_state_changed"
            )
        rows = cursor.execute(
            """SELECT event_digest, execution_id, manifest_digest, task_digest,
                      task_key, event_type, sequence
               FROM research_os_mainline_execution_events
               WHERE control_plane_key = %s AND task_key = %s AND execution_id = %s
               ORDER BY sequence, event_digest""",
            (control_plane_key, OLD_TASK_KEY, OLD_EXECUTION_ID),
        ).fetchall()
        expected_rows = (
            (OLD_STARTED_EVENT_DIGEST, "started", 0),
            (OLD_FAILED_EVENT_DIGEST, "failed", 1),
        )
        if len(rows) != 2 or any(
            str(row["event_digest"]) != digest
            or str(row["execution_id"]) != OLD_EXECUTION_ID
            or str(row["manifest_digest"]) != OLD_EVENT_MANIFEST_DIGEST
            or str(row["task_digest"]) != OLD_TASK_DIGEST
            or str(row["task_key"]) != OLD_TASK_KEY
            or str(row["event_type"]) != event_type
            or int(row["sequence"]) != sequence
            for row, (digest, event_type, sequence) in zip(
                rows, expected_rows, strict=True
            )
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_event_lineage_changed"
            )
        successor_by_key = {task.task_key: task for task in manifest.tasks}
        if any(
            successor_by_key[key].artifact_digest != after
            for key, _, after in P3_REVISIONS
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_p3_revisions_changed"
            )

    @staticmethod
    def _verify_m4_v2_failed_global_routing_recovery_import(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
    ) -> None:
        """Verify the frozen failed Global lineage before the first write."""

        from scripts.build_m4_v2_global_routing_recovery_manifest import (
            INPUT_MANIFEST_DIGEST,
            OLD_EVENT_MANIFEST_DIGEST,
            OLD_EXECUTION_ID,
            OLD_FAILED_EVENT_DIGEST,
            OLD_STARTED_EVENT_DIGEST,
            OLD_TASK_DIGEST,
            OLD_TASK_KEY,
            P3_REVISIONS,
            RECOVERY_TASK_KEY,
            build_manifest,
        )

        tasks = {task.task_key: task for task in manifest.tasks}
        recovery = tasks.get(RECOVERY_TASK_KEY)
        if recovery is None:
            return
        if control_plane_key != "m4-information-theory-mainline":
            raise ResearchOSValidationError("m4_v2_global_recovery_control_plane_changed")
        if OLD_TASK_KEY in tasks or len(recovery.input_artifact_digests) != 1:
            raise ResearchOSValidationError("m4_v2_global_recovery_task_identity_changed")

        control = cursor.execute(
            """SELECT current_manifest_digest FROM research_os_control_planes
               WHERE control_plane_key = %s FOR UPDATE""",
            (control_plane_key,),
        ).fetchone()
        if control is None:
            raise ResearchOSValidationError("m4_v2_global_recovery_control_plane_missing")
        current_digest = str(control["current_manifest_digest"])
        stored = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (current_digest,),
        ).fetchone()
        if stored is None:
            raise ResearchOSValidationError("m4_v2_global_recovery_manifest_missing")
        current = ControlPlaneManifest.from_dict(dict(stored["manifest_json"]))
        if current_digest == INPUT_MANIFEST_DIGEST:
            expected, _ = build_manifest(
                current.to_dict(include_digest=True),
                global_source_contract_digest=recovery.input_artifact_digests[0],
            )
            if manifest.to_dict(include_digest=True) != expected:
                raise ResearchOSValidationError("m4_v2_global_recovery_output_changed")
        else:
            current_tasks = {task.task_key: task for task in current.tasks}
            keys = {RECOVERY_TASK_KEY, *(key for key, _, _ in P3_REVISIONS)}
            if OLD_TASK_KEY in current_tasks or any(
                current_tasks.get(key) is None
                or current_tasks[key].artifact_digest != tasks[key].artifact_digest
                for key in keys
            ):
                raise ResearchOSValidationError("m4_v2_global_recovery_lineage_changed")

        state = cursor.execute(
            """SELECT ts.declared_status, ts.completion_classification,
                      ts.superseded_by_task_digest
               FROM research_os_task_states ts
               WHERE ts.control_plane_key = %s AND ts.task_digest = %s""",
            (control_plane_key, OLD_TASK_DIGEST),
        ).fetchone()
        if (
            state is None
            or str(state["declared_status"]) != "failed"
            or str(state["completion_classification"]) != "INTEGRATED"
            or state["superseded_by_task_digest"] is not None
        ):
            raise ResearchOSValidationError("m4_v2_global_recovery_old_state_changed")
        rows = cursor.execute(
            """SELECT event_digest, execution_id, manifest_digest, task_digest,
                      task_key, event_type, sequence
               FROM research_os_mainline_execution_events
               WHERE control_plane_key = %s AND task_key = %s AND execution_id = %s
               ORDER BY sequence, event_digest""",
            (control_plane_key, OLD_TASK_KEY, OLD_EXECUTION_ID),
        ).fetchall()
        expected_rows = (
            (OLD_STARTED_EVENT_DIGEST, "started", 0),
            (OLD_FAILED_EVENT_DIGEST, "failed", 1),
        )
        if len(rows) != 2 or any(
            str(row["event_digest"]) != digest
            or str(row["execution_id"]) != OLD_EXECUTION_ID
            or str(row["manifest_digest"]) != OLD_EVENT_MANIFEST_DIGEST
            or str(row["task_digest"]) != OLD_TASK_DIGEST
            or str(row["task_key"]) != OLD_TASK_KEY
            or str(row["event_type"]) != event_type
            or int(row["sequence"]) != sequence
            for row, (digest, event_type, sequence) in zip(rows, expected_rows, strict=True)
        ):
            raise ResearchOSValidationError("m4_v2_global_recovery_event_lineage_changed")

    def load_manifest(self, *, control_plane_key: str) -> ControlPlaneManifest:
        key = self._key(control_plane_key)
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            control = cursor.execute(
                """
                SELECT current_manifest_digest, schema_version
                FROM research_os_control_planes
                WHERE control_plane_key = %s
                """,
                (key,),
            ).fetchone()
            if control is None:
                raise ResearchOSValidationError(f"control plane not found: {key}")
            manifest_digest = str(control["current_manifest_digest"])
            stored_manifest = cursor.execute(
                "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
                (manifest_digest,),
            ).fetchone()
            if stored_manifest is None:
                raise ResearchOSValidationError("current manifest row is missing")

            goal_rows = cursor.execute(
                """
                SELECT gd.goal_digest, gd.definition_json, gs.status, gs.retired_at,
                       gs.superseded_by_goal_digest
                FROM research_os_manifest_goals mg
                JOIN research_os_goal_definitions gd ON gd.goal_digest = mg.goal_digest
                JOIN research_os_goal_states gs
                  ON gs.control_plane_key = %s AND gs.goal_digest = gd.goal_digest
                WHERE mg.manifest_digest = %s
                ORDER BY mg.ordinal
                """,
                (key, manifest_digest),
            ).fetchall()
            task_rows = cursor.execute(
                """
                SELECT td.task_digest, td.definition_json, ts.declared_status,
                       ts.completion_classification,
                       ts.superseded_by_task_digest, ts.resolved_status,
                       ts.reason_code, ts.dependency_state_json
                FROM research_os_manifest_tasks mt
                JOIN research_os_task_definitions td ON td.task_digest = mt.task_digest
                JOIN research_os_task_states ts
                  ON ts.control_plane_key = %s AND ts.task_digest = td.task_digest
                WHERE mt.manifest_digest = %s
                ORDER BY mt.ordinal
                """,
                (key, manifest_digest),
            ).fetchall()
            fact_rows = cursor.execute(
                """
                SELECT fact_type, fact_key
                FROM research_os_dependency_facts
                WHERE control_plane_key = %s AND fact_status = 'available'
                ORDER BY fact_type, fact_key
                """,
                (key,),
            ).fetchall()

        goals: list[dict[str, Any]] = []
        for row in goal_rows:
            definition = dict(row["definition_json"])
            goal = Goal.from_dict(definition)
            if goal.artifact_digest != str(row["goal_digest"]):
                raise ResearchOSValidationError(
                    f"stored Goal definition digest mismatch: {row['goal_digest']}"
                )
            goals.append(
                {
                    **definition,
                    "status": str(row["status"]),
                    "retired_at": row["retired_at"].isoformat() if row["retired_at"] else None,
                    "superseded_by_goal_digest": row["superseded_by_goal_digest"],
                }
            )

        tasks: list[dict[str, Any]] = []
        stored_projections: dict[str, dict[str, Any]] = {}
        for row in task_rows:
            definition = dict(row["definition_json"])
            task = Task.from_dict(definition, goal_digest=str(definition.get("goal_digest") or ""))
            if task.artifact_digest != str(row["task_digest"]):
                raise ResearchOSValidationError(
                    f"stored Task definition digest mismatch: {row['task_digest']}"
                )
            tasks.append(
                {
                    **definition,
                    "status": str(row["declared_status"]),
                    "completion_classification": row["completion_classification"],
                    "superseded_by_task_digest": row["superseded_by_task_digest"],
                }
            )
            stored_projections[task.artifact_digest] = {
                "status": str(row["resolved_status"]),
                "reason_code": str(row["reason_code"]),
                "dependencies": list(row["dependency_state_json"] or []),
            }

        facts: dict[str, list[str]] = {
            "artifacts": [],
            "evidence": [],
            "external_events": [],
            "authorities": [],
        }
        fact_field = {
            "artifact": "artifacts",
            "evidence": "evidence",
            "external_event": "external_events",
            "authority": "authorities",
        }
        for row in fact_rows:
            facts[fact_field[str(row["fact_type"])]].append(str(row["fact_key"]))

        payload = {
            "schema_version": str(control["schema_version"]),
            "goals": goals,
            "tasks": tasks,
            "facts": facts,
        }
        manifest = ControlPlaneManifest.from_dict(payload)
        if manifest.artifact_digest != manifest_digest:
            raise ResearchOSValidationError(
                f"repository manifest digest mismatch: expected {manifest_digest}, "
                f"calculated {manifest.artifact_digest}"
            )
        if stable_json(dict(stored_manifest["manifest_json"])) != stable_json(
            manifest.to_dict(include_digest=False)
        ):
            raise ResearchOSValidationError("stored immutable manifest payload mismatch")

        snapshot = self.control_plane.resolve(manifest)
        self._verify_state_projection(snapshot.resolutions, stored_projections)
        return manifest

    def resolve_persisted(self, *, control_plane_key: str) -> ResolutionSnapshot:
        return self.control_plane.resolve(self.load_manifest(control_plane_key=control_plane_key))

    def export_manifest(self, *, control_plane_key: str) -> dict[str, Any]:
        return self.load_manifest(control_plane_key=control_plane_key).to_dict(include_digest=True)

    def record_external_executor_observation(
        self,
        *,
        control_plane_key: str,
        observation: ExternalExecutorObservation,
    ) -> bool:
        key = self._key(control_plane_key)
        payload = jsonable(observation)
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            exists = cursor.execute(
                "SELECT 1 FROM research_os_control_planes WHERE control_plane_key = %s",
                (key,),
            ).fetchone()
            if exists is None:
                raise ResearchOSValidationError(f"control plane not found: {key}")
            row = cursor.execute(
                """
                INSERT INTO research_os_external_executor_observations (
                  observation_digest, control_plane_key, capability, owner,
                  status, pid, observed_at, observation_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (observation_digest) DO NOTHING
                RETURNING observation_digest
                """,
                (
                    observation.artifact_digest,
                    key,
                    observation.capability,
                    observation.owner,
                    observation.status,
                    observation.pid,
                    observation.observed_at,
                    _json(payload),
                ),
            ).fetchone()
        return row is not None

    def list_external_executor_observations(
        self,
        *,
        control_plane_key: str,
        limit: int = 100,
    ) -> tuple[dict[str, Any], ...]:
        key = self._key(control_plane_key)
        if limit < 1 or limit > 1000:
            raise ResearchOSValidationError("observation limit must be between 1 and 1000")
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT observation_digest, observation_json
                FROM research_os_external_executor_observations
                WHERE control_plane_key = %s
                ORDER BY observed_at DESC, observation_digest DESC
                LIMIT %s
                """,
                (key, limit),
            ).fetchall()
        return tuple(
            {"observation_digest": str(row["observation_digest"]), **dict(row["observation_json"])}
            for row in rows
        )

    def record_mainline_execution_event(
        self,
        *,
        event: MainlineExecutionEvent,
    ) -> bool:
        payload = jsonable(event)
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                """
                INSERT INTO research_os_mainline_execution_events (
                  event_digest, execution_id, control_plane_key, manifest_digest,
                  task_digest, task_key, capability, event_type, sequence,
                  recorded_at, event_json
                ) VALUES (
                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
                )
                ON CONFLICT (event_digest) DO NOTHING
                RETURNING event_digest
                """,
                (
                    event.artifact_digest,
                    event.execution_id,
                    event.control_plane_key,
                    event.manifest_digest,
                    event.task_digest,
                    event.task_key,
                    event.capability,
                    event.event_type,
                    event.sequence,
                    event.recorded_at,
                    _json(payload),
                ),
            ).fetchone()
        return row is not None

    def register_mainline_artifact(
        self,
        *,
        registration: MainlineArtifactRegistration,
    ) -> bool:
        payload = jsonable(registration)
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                """
                INSERT INTO research_os_mainline_artifacts (
                  registration_digest, execution_id, control_plane_key,
                  task_digest, task_key, artifact_digest, artifact_type,
                  schema_version, artifact_path, parent_digests_json,
                  git_commit, registration_json
                ) VALUES (
                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb
                )
                ON CONFLICT (registration_digest) DO NOTHING
                RETURNING registration_digest
                """,
                (
                    registration.registration_digest,
                    registration.execution_id,
                    registration.control_plane_key,
                    registration.task_digest,
                    registration.task_key,
                    registration.artifact_digest,
                    registration.artifact_type,
                    registration.schema_version,
                    registration.artifact_path,
                    _json(registration.parent_digests),
                    registration.git_commit,
                    _json(payload),
                ),
            ).fetchone()
        return row is not None

    def list_mainline_execution_events(
        self,
        *,
        control_plane_key: str,
        task_key: str | None = None,
        execution_id: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        clauses = ["control_plane_key = %s"]
        params: list[Any] = [self._key(control_plane_key)]
        if task_key is not None:
            clauses.append("task_key = %s")
            params.append(self._key(task_key))
        if execution_id is not None:
            clauses.append("execution_id = %s")
            params.append(self._key(execution_id))
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                f"""
                SELECT event_digest, event_json
                FROM research_os_mainline_execution_events
                WHERE {' AND '.join(clauses)}
                ORDER BY recorded_at, sequence, event_digest
                """,
                tuple(params),
            ).fetchall()
        return tuple(
            {"event_digest": str(row["event_digest"]), **dict(row["event_json"])}
            for row in rows
        )

    def list_mainline_execution_event_metadata(
        self,
        *,
        control_plane_key: str,
        task_keys: tuple[str, ...] = (),
    ) -> tuple[dict[str, Any], ...]:
        """Return a result-blind event projection without loading event payload."""

        clauses = ["control_plane_key = %s"]
        params: list[Any] = [self._key(control_plane_key)]
        if task_keys:
            clauses.append("task_key = ANY(%s)")
            params.append([self._key(item) for item in task_keys])
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                f"""
                SELECT event_digest, execution_id, control_plane_key,
                       manifest_digest, task_digest, task_key, capability,
                       event_type, sequence, recorded_at
                FROM research_os_mainline_execution_events
                WHERE {' AND '.join(clauses)}
                ORDER BY recorded_at, sequence, event_digest
                """,
                tuple(params),
            ).fetchall()
        return tuple(
            {
                "event_digest": str(row["event_digest"]),
                "execution_id": str(row["execution_id"]),
                "control_plane_key": str(row["control_plane_key"]),
                "manifest_digest": str(row["manifest_digest"]),
                "task_digest": str(row["task_digest"]),
                "task_key": str(row["task_key"]),
                "capability": str(row["capability"]),
                "event_type": str(row["event_type"]),
                "sequence": int(row["sequence"]),
                "recorded_at": row["recorded_at"].isoformat(),
            }
            for row in rows
        )

    def list_mainline_artifacts(
        self,
        *,
        control_plane_key: str,
        execution_id: str,
    ) -> tuple[dict[str, Any], ...]:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT registration_digest, registration_json
                FROM research_os_mainline_artifacts
                WHERE control_plane_key = %s AND execution_id = %s
                ORDER BY artifact_type, artifact_digest
                """,
                (self._key(control_plane_key), self._key(execution_id)),
            ).fetchall()
        return tuple(
            {
                "registration_digest": str(row["registration_digest"]),
                **dict(row["registration_json"]),
            }
            for row in rows
        )

    @staticmethod
    def _key(value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ResearchOSValidationError("repository key must be a non-empty string")
        return normalized

    @staticmethod
    def _fact_rows(manifest: ControlPlaneManifest) -> tuple[tuple[str, str], ...]:
        rows = [
            *(("artifact", item) for item in manifest.facts.artifacts),
            *(("evidence", item) for item in manifest.facts.evidence),
            *(("external_event", item) for item in manifest.facts.external_events),
            *(("authority", item) for item in manifest.facts.authorities),
        ]
        return tuple(sorted(rows))

    @staticmethod
    def _current_revisions(cursor, control_plane_key: str) -> tuple[dict[str, str], dict[str, str]]:
        exists = cursor.execute(
            """
            SELECT current_manifest_digest
            FROM research_os_control_planes
            WHERE control_plane_key = %s
            """,
            (control_plane_key,),
        ).fetchone()
        if exists is None:
            return {}, {}
        manifest_digest = str(exists["current_manifest_digest"])
        goal_rows = cursor.execute(
            """
            SELECT gd.goal_key, gd.goal_digest
            FROM research_os_manifest_goals mg
            JOIN research_os_goal_definitions gd ON gd.goal_digest = mg.goal_digest
            WHERE mg.manifest_digest = %s
            """,
            (manifest_digest,),
        ).fetchall()
        task_rows = cursor.execute(
            """
            SELECT td.task_key, td.task_digest
            FROM research_os_manifest_tasks mt
            JOIN research_os_task_definitions td ON td.task_digest = mt.task_digest
            WHERE mt.manifest_digest = %s
            """,
            (manifest_digest,),
        ).fetchall()
        return (
            {str(row["goal_key"]): str(row["goal_digest"]) for row in goal_rows},
            {str(row["task_key"]): str(row["task_digest"]) for row in task_rows},
        )

    @staticmethod
    def _verify_goal_definition(cursor, goal: Goal) -> None:
        row = cursor.execute(
            "SELECT definition_json FROM research_os_goal_definitions WHERE goal_digest = %s",
            (goal.artifact_digest,),
        ).fetchone()
        if row is None:
            raise ResearchOSValidationError("stored Goal definition is missing")
        stored = Goal.from_dict(dict(row["definition_json"]))
        if stored.artifact_digest != goal.artifact_digest:
            raise ResearchOSValidationError("stored Goal definition failed digest verification")

    @staticmethod
    def _verify_task_definition(cursor, task: Task) -> None:
        row = cursor.execute(
            "SELECT definition_json FROM research_os_task_definitions WHERE task_digest = %s",
            (task.artifact_digest,),
        ).fetchone()
        if row is None:
            raise ResearchOSValidationError("stored Task definition is missing")
        stored = Task.from_dict(dict(row["definition_json"]), goal_digest=task.goal_digest)
        if stored.artifact_digest != task.artifact_digest:
            raise ResearchOSValidationError("stored Task definition failed digest verification")

    @staticmethod
    def _verify_manifest_row(cursor, manifest: ControlPlaneManifest) -> None:
        row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (manifest.artifact_digest,),
        ).fetchone()
        if row is None:
            raise ResearchOSValidationError("stored manifest is missing")
        stored = ControlPlaneManifest.from_dict(dict(row["manifest_json"]))
        if stored.artifact_digest != manifest.artifact_digest:
            raise ResearchOSValidationError("stored manifest failed digest verification")

    @staticmethod
    def _verify_state_projection(
        resolutions: tuple[TaskResolution, ...],
        stored: dict[str, dict[str, Any]],
    ) -> None:
        if {item.task_digest for item in resolutions} != set(stored):
            raise ResearchOSValidationError("stored Task state projection membership mismatch")
        for resolution in resolutions:
            state = stored[resolution.task_digest]
            expected_dependencies = jsonable(resolution.unsatisfied_dependencies)
            if (
                state["status"] != resolution.status.value
                or state["reason_code"] != resolution.reason_code
                or state["dependencies"] != expected_dependencies
            ):
                raise ResearchOSValidationError(
                    f"stored Task state projection mismatch: {resolution.task_key}"
                )

    @staticmethod
    def _verify_mainline_completion_records(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
    ) -> None:
        for task in manifest.tasks:
            if task.requested_capability is None:
                continue
            execution_ids = completion_execution_ids(manifest, task=task)
            for execution_id in execution_ids:
                completed = cursor.execute(
                    """
                    SELECT 1
                    FROM research_os_mainline_execution_events
                    WHERE control_plane_key = %s
                      AND task_digest = %s
                      AND task_key = %s
                      AND execution_id = %s
                      AND event_type = 'completed'
                    """,
                    (
                        control_plane_key,
                        task.artifact_digest,
                        task.task_key,
                        execution_id,
                    ),
                ).fetchone()
                if completed is None:
                    raise ResearchOSValidationError(
                        f"task {task.task_key!r} completion fact has no immutable "
                        "completed mainline execution event"
                    )
                artifact = cursor.execute(
                    """
                    SELECT 1
                    FROM research_os_mainline_artifacts
                    WHERE control_plane_key = %s
                      AND task_digest = %s
                      AND execution_id = %s
                    LIMIT 1
                    """,
                    (control_plane_key, task.artifact_digest, execution_id),
                ).fetchone()
                if artifact is None:
                    raise ResearchOSValidationError(
                        f"task {task.task_key!r} completion fact has no registered "
                        "mainline artifact"
                    )

    @staticmethod
    def _verify_no_mainline_completion_regression(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
        previous_tasks: dict[str, str],
    ) -> None:
        incoming_states = manifest.task_state_by_digest
        for task in manifest.tasks:
            if task.requested_capability is None:
                continue
            if previous_tasks.get(task.task_key) != task.artifact_digest:
                continue
            row = cursor.execute(
                """
                SELECT declared_status, completion_classification
                FROM research_os_task_states
                WHERE control_plane_key = %s AND task_digest = %s
                """,
                (control_plane_key, task.artifact_digest),
            ).fetchone()
            if row is None or str(row["declared_status"]) != "completed":
                continue
            incoming = incoming_states[task.artifact_digest]
            if incoming.declared_status.value != "completed":
                raise ResearchOSValidationError(
                    f"mainline completion regression forbidden for task {task.task_key!r}"
                )
