from __future__ import annotations

import ast
import base64
import copy
import hashlib
import json
import lzma
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from zoneinfo import ZoneInfo

import psycopg
import pytest
from dehps import config as dehps_config
from dehps.config import get_settings
from dehps.research_os import repository as repository_module
from dehps.research_os.models import (
    ControlPlaneManifest,
    ExternalExecutorObservation,
    MainlineArtifactRegistration,
    MainlineExecutionEvent,
    ResearchOSValidationError,
    TaskStatus,
    jsonable,
    m4_v2_domain_digest,
    stable_hash,
)
from dehps.research_os.repository import PostgresResearchOSRepository
from psycopg import sql

from scripts import build_m4_v2_global_routing_recovery_v2_manifest as recovery_v2
from scripts import build_m4_v2_global_routing_recovery_v3_manifest as recovery_v3
from scripts import (
    build_m4_v2_global_routing_replay_compatibility_v1_manifest as replay_compatibility,
)

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def _frozen_recovery_v3_source_root(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("frozen-recovery-v3-source")
    source = json.loads(
        (ROOT / recovery_v3.GLOBAL_SOURCE_PATH).read_text(encoding="utf-8")
    )
    for entry in source["source_entries"]:
        path = str(entry["path"])
        frozen = subprocess.run(
            ["git", "show", f"{replay_compatibility.OLD_GIT_COMMIT}:{path}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        assert hashlib.sha256(frozen).hexdigest() == entry["sha256"]
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(frozen)
    return root


@pytest.fixture(autouse=True)
def _bind_repository_historical_source_to_frozen_bytes(
    monkeypatch,
    _frozen_recovery_v3_source_root: Path,
) -> None:
    real_loader = repository_module._load_m4_v2_global_routing_recovery_v3_builder
    direct_validate = recovery_v3.validate_global_source_contract

    def validate_frozen(source, **_kwargs):
        return direct_validate(
            source,
            root_dir=_frozen_recovery_v3_source_root,
        )

    monkeypatch.setattr(
        recovery_v3,
        "validate_global_source_contract",
        validate_frozen,
    )

    def load_frozen_builder():
        module = real_loader()
        validate = module.validate_global_source_contract
        module.validate_global_source_contract = lambda source, **_kwargs: validate(
            source,
            root_dir=_frozen_recovery_v3_source_root,
        )
        return module

    monkeypatch.setattr(
        repository_module,
        "_load_m4_v2_global_routing_recovery_v3_builder",
        load_frozen_builder,
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
    if os.getenv("DEHPS_TEST_POSTGRES") != "1":
        pytest.skip("set DEHPS_TEST_POSTGRES=1 for isolated PostgreSQL acceptance")
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


class _Rows:
    def __init__(self, *, one=None, many=()):
        self.one = one
        self.many = many

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class _RecoveryV2Cursor:
    def __init__(
        self,
        manifest: ControlPlaneManifest,
        *,
        current: ControlPlaneManifest | None = None,
        runtime_events: list[dict] | None = None,
        registrations: list[dict] | None = None,
    ):
        self.manifest = manifest
        self.current = current or manifest
        self.baseline = _recovery_v2_baseline_manifest()
        self.old_definition = next(
            task
            for task in self.baseline.tasks
            if task.task_key == recovery_v2.OLD_TASK_KEY
        )
        self.state = {
            "declared_status": "failed",
            "completion_classification": "INTEGRATED",
            "superseded_by_task_digest": None,
        }
        self.events = [
            {
                "event_digest": recovery_v2.OLD_STARTED_EVENT_DIGEST,
                "execution_id": recovery_v2.OLD_EXECUTION_ID,
                "manifest_digest": recovery_v2.OLD_EVENT_MANIFEST_DIGEST,
                "task_digest": recovery_v2.OLD_TASK_DIGEST,
                "task_key": recovery_v2.OLD_TASK_KEY,
                "event_type": "started",
                "sequence": 0,
            },
            {
                "event_digest": recovery_v2.OLD_FAILED_EVENT_DIGEST,
                "execution_id": recovery_v2.OLD_EXECUTION_ID,
                "manifest_digest": recovery_v2.OLD_EVENT_MANIFEST_DIGEST,
                "task_digest": recovery_v2.OLD_TASK_DIGEST,
                "task_key": recovery_v2.OLD_TASK_KEY,
                "event_type": "failed",
                "sequence": 1,
            },
        ]
        self.runtime_events = runtime_events or []
        self.registrations = registrations or []
        self.statements: list[str] = []

    def execute(self, statement, parameters=()):
        query = " ".join(str(statement).split())
        self.statements.append(query)
        assert query.startswith("SELECT")
        if "FROM research_os_control_planes" in query:
            return _Rows(one={"current_manifest_digest": self.current.artifact_digest})
        if "FROM research_os_manifests" in query:
            stored = (
                self.baseline
                if parameters == (recovery_v2.INPUT_MANIFEST_DIGEST,)
                else self.current
            )
            return _Rows(one={"manifest_json": stored.to_dict(include_digest=True)})
        if "FROM research_os_task_definitions" in query:
            return _Rows(
                one={
                    "task_digest": recovery_v2.OLD_TASK_DIGEST,
                    "task_key": recovery_v2.OLD_TASK_KEY,
                    "definition_json": self.old_definition.to_dict(),
                }
            )
        if "FROM research_os_task_states" in query:
            return _Rows(one=self.state)
        if "FROM research_os_mainline_execution_events" in query:
            if parameters[1] == recovery_v2.RECOVERY_TASK_KEY:
                return _Rows(many=self.runtime_events)
            return _Rows(many=self.events)
        if "FROM research_os_mainline_artifacts" in query:
            return _Rows(many=self.registrations)
        raise AssertionError(query)


def _active_recovery_v2_manifest() -> ControlPlaneManifest:
    baseline = _recovery_v2_baseline_manifest()
    payload, _ = recovery_v2.build_manifest(
        baseline.to_dict(include_digest=True),
        global_source_contract_digest=(
            "24bfd16ee558f13ec2a50a30a8d903a11934fc128f996f370d78fdba9a4929ec"
        ),
    )
    manifest = ControlPlaneManifest.from_dict(payload)
    assert recovery_v2.RECOVERY_TASK_KEY in {
        task.task_key for task in manifest.tasks
    }
    return manifest


def _transition_recovery_v2_manifest(
    manifest: ControlPlaneManifest,
    *,
    status: str,
    classification: str,
    facts: tuple[str, ...] = (),
) -> ControlPlaneManifest:
    payload = manifest.to_dict(include_digest=False)
    task = next(
        item
        for item in payload["tasks"]
        if item["task_key"] == recovery_v2.RECOVERY_TASK_KEY
    )
    task["status"] = status
    task["completion_classification"] = classification
    payload["facts"]["artifacts"] = sorted(
        {*payload["facts"]["artifacts"], *facts}
    )
    return ControlPlaneManifest.from_dict(payload)


def _event_row(event: MainlineExecutionEvent) -> dict:
    payload = jsonable(event)
    return {
        "event_digest": event.artifact_digest,
        "execution_id": event.execution_id,
        "control_plane_key": event.control_plane_key,
        "manifest_digest": event.manifest_digest,
        "task_digest": event.task_digest,
        "task_key": event.task_key,
        "capability": event.capability,
        "event_type": event.event_type,
        "sequence": event.sequence,
        "recorded_at": event.recorded_at,
        "event_json": payload,
    }


def _event_row_with_recorded_at(row: dict, recorded_at: str) -> dict:
    raw = copy.deepcopy(row["event_json"])
    event = MainlineExecutionEvent(
        execution_id=str(raw["execution_id"]),
        control_plane_key=str(raw["control_plane_key"]),
        manifest_digest=str(raw["manifest_digest"]),
        task_key=str(raw["task_key"]),
        task_digest=str(raw["task_digest"]),
        capability=str(raw["capability"]),
        event_type=str(raw["event_type"]),
        sequence=int(raw["sequence"]),
        recorded_at=recorded_at,
        payload=tuple((str(item[0]), item[1]) for item in raw["payload"]),
    )
    return _event_row(event)


def _registration_row(registration: MainlineArtifactRegistration) -> dict:
    return {
        "registration_digest": registration.registration_digest,
        "execution_id": registration.execution_id,
        "control_plane_key": registration.control_plane_key,
        "task_digest": registration.task_digest,
        "task_key": registration.task_key,
        "artifact_digest": registration.artifact_digest,
        "artifact_type": registration.artifact_type,
        "schema_version": registration.schema_version,
        "artifact_path": registration.artifact_path,
        "parent_digests_json": list(registration.parent_digests),
        "git_commit": registration.git_commit,
        "registration_json": jsonable(registration),
    }


def _recovery_v2_runtime_fixture(
    terminal: str,
) -> tuple[
    ControlPlaneManifest,
    ControlPlaneManifest,
    list[dict],
    list[dict],
]:
    ready = _active_recovery_v2_manifest()
    running = _transition_recovery_v2_manifest(
        ready,
        status="running",
        classification="INTEGRATED",
    )
    assert (
        running.artifact_digest
        == "8d9ed3811969cb80979c51e2c27f451ca2c4b127d59a2c1a9e105127b68bb084"
    )
    task = next(
        item
        for item in ready.tasks
        if item.task_key == recovery_v2.RECOVERY_TASK_KEY
    )
    git_commit = "a" * 40
    execution_id = stable_hash(
        {
            "schema": "dehps-research-os-mainline-execution.v1",
            "control_plane_key": "m4-information-theory-mainline",
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "input_artifact_digests": task.input_artifact_digests,
            "git_commit": git_commit,
        }
    )
    started = MainlineExecutionEvent(
        execution_id=execution_id,
        control_plane_key="m4-information-theory-mainline",
        manifest_digest=running.artifact_digest,
        task_key=task.task_key,
        task_digest=task.artifact_digest,
        capability=str(task.requested_capability),
        event_type="started",
        sequence=0,
        recorded_at="2026-08-14T10:00:00+00:00",
        payload=(
            ("input_artifact_digests", list(task.input_artifact_digests)),
            ("git_commit", git_commit),
        ),
    )
    if terminal == "RUNNING":
        return running, running, [_event_row(started)], []
    if terminal == "FAILED":
        failed = _transition_recovery_v2_manifest(
            running,
            status="failed",
            classification="INTEGRATED",
        )
        assert (
            failed.artifact_digest
            == "b50a4c07ee75cd9e87842b8ad62846b6c37af23a17a9fc71e1e3610ce2e8c319"
        )
        event = MainlineExecutionEvent(
            execution_id=execution_id,
            control_plane_key="m4-information-theory-mainline",
            manifest_digest=running.artifact_digest,
            task_key=task.task_key,
            task_digest=task.artifact_digest,
            capability=str(task.requested_capability),
            event_type="failed",
            sequence=1,
            recorded_at="2026-08-14T10:01:00+00:00",
            payload=(("error", "frozen failure"), ("git_commit", git_commit)),
        )
        return failed, running, [_event_row(started), _event_row(event)], []
    if terminal != "COMPLETED":
        raise AssertionError(terminal)

    metric = json.loads(task.metric_contract)
    route = "DEEPER_VALIDATION_REQUIRED"
    route_fact = metric["route_facts"][route]
    completion_fact = metric["completion_fact"]
    route_digest = "b" * 64
    execution_artifact_digest = "c" * 64
    mainline_fact = (
        f"mainline-execution:{task.task_key}:{task.artifact_digest}:"
        f"{execution_id}:completed"
    )
    completed = _transition_recovery_v2_manifest(
        running,
        status="completed",
        classification="COMPLETE",
        facts=(mainline_fact, route_fact, completion_fact),
    )
    route_path = metric["route_artifact_path_template"].format(
        execution_id=execution_id,
        artifact_digest=route_digest,
    )
    execution_path = (
        f"runtime/research-os/mainline/tasks/{task.task_key}/"
        f"{execution_id}/execution.json"
    )
    route_registration = MainlineArtifactRegistration(
        execution_id=execution_id,
        control_plane_key="m4-information-theory-mainline",
        task_key=task.task_key,
        task_digest=task.artifact_digest,
        artifact_digest=route_digest,
        artifact_type=metric["route_serialized_artifact_type"],
        schema_version="dehps-m4-measurement-routing-decision.v1",
        artifact_path=route_path,
        parent_digests=(),
        git_commit=git_commit,
    )
    execution_registration = MainlineArtifactRegistration(
        execution_id=execution_id,
        control_plane_key="m4-information-theory-mainline",
        task_key=task.task_key,
        task_digest=task.artifact_digest,
        artifact_digest=execution_artifact_digest,
        artifact_type="research_os_mainline_execution",
        schema_version="dehps-research-os-mainline-execution.v1",
        artifact_path=execution_path,
        parent_digests=(task.input_artifact_digests[0], route_digest),
        git_commit=git_commit,
    )
    summary = {
        "execution_artifact_digest": execution_artifact_digest,
        "execution_artifact_path": execution_path,
        "actual_fold_count": 0,
        "registered_artifact_count": 2,
        "git_commit": git_commit,
        "completion_facts": [route_fact, completion_fact],
        "additional_completed_task_keys": [],
        "publication_batch_digest": m4_v2_domain_digest(
            {
                "control_plane_key": "m4-information-theory-mainline",
                "expected_head_manifest_digest": running.artifact_digest,
                "task_key": task.task_key,
                "task_digest": task.artifact_digest,
                "execution_id": execution_id,
                "git_commit": git_commit,
                "ordered_artifact_digest_path_pairs": [
                    {
                        "artifact_digest": route_digest,
                        "canonical_artifact_path": route_path,
                    },
                    {
                        "artifact_digest": execution_artifact_digest,
                        "canonical_artifact_path": execution_path,
                    },
                ],
            },
            domain="dehps.m4.v2.mainline-publication-batch-identity.v1",
        ),
        "workload_rerun": False,
        "source_contract_digest": task.input_artifact_digests[0],
        "source_set_digest": (
            "51416beac1b615c6b5b91786f40f105b45ec7503285126649aa4334715b3a00c"
        ),
        "route_decision_artifact_digest": route_digest,
        "route": route,
        "downstream_consumer": metric["mainline_integration"]["downstream_consumer"],
        "decision_replay_coverage": "COMPLETE",
        "historical_database_reads": 0,
        "scientific_computation": 0,
        "replay_status": "REGISTERED_REPLAY_PENDING",
    }
    event = MainlineExecutionEvent(
        execution_id=execution_id,
        control_plane_key="m4-information-theory-mainline",
        manifest_digest=running.artifact_digest,
        task_key=task.task_key,
        task_digest=task.artifact_digest,
        capability=str(task.requested_capability),
        event_type="completed",
        sequence=1,
        recorded_at="2026-08-14T10:01:00+00:00",
        payload=tuple(sorted(summary.items())),
    )
    return (
        completed,
        running,
        [_event_row(started), _event_row(event)],
        [
            _registration_row(route_registration),
            _registration_row(execution_registration),
        ],
    )


def _recovery_v2_baseline_manifest() -> ControlPlaneManifest:
    fixture_path = (
        ROOT
        / "apps/worker-python/tests/test_m4_v2_three_branch_decision_replay_global_routing.py"
    )
    syntax = ast.parse(fixture_path.read_text(encoding="utf-8"))
    encoded = next(
        ast.literal_eval(node.value)
        for node in syntax.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id == "RECOVERY_V2_INPUT_FIXTURE_B85"
            for target in node.targets
        )
    )
    return ControlPlaneManifest.from_dict(
        json.loads(lzma.decompress(base64.b85decode(encoded)).decode())
    )


def _terminal_recovery_v2_manifest() -> ControlPlaneManifest:
    payload, _ = recovery_v2.build_manifest(
        _recovery_v2_baseline_manifest().to_dict(include_digest=True),
        global_source_contract_digest=recovery_v3.OLD_SOURCE_DIGEST,
    )
    ready = ControlPlaneManifest.from_dict(payload)
    failed = _transition_recovery_v2_manifest(
        ready,
        status="failed",
        classification="INTEGRATED",
    )
    assert failed.artifact_digest == recovery_v3.INPUT_MANIFEST_DIGEST
    return failed


def _active_recovery_v3_manifest() -> ControlPlaneManifest:
    baseline = _terminal_recovery_v2_manifest()
    source_path = ROOT / recovery_v3.GLOBAL_SOURCE_PATH
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source_digest = recovery_v3.validate_global_source_contract(source, root_dir=ROOT)
    payload, _ = recovery_v3.build_manifest(
        baseline.to_dict(include_digest=True),
        global_source_contract_digest=source_digest,
    )
    manifest = ControlPlaneManifest.from_dict(payload)
    assert recovery_v3.RECOVERY_TASK_KEY in {task.task_key for task in manifest.tasks}
    return manifest


def _transition_recovery_v3_manifest(
    manifest: ControlPlaneManifest,
    *,
    status: str,
    classification: str,
    facts: tuple[str, ...] = (),
) -> ControlPlaneManifest:
    payload = manifest.to_dict(include_digest=False)
    task = next(
        item for item in payload["tasks"] if item["task_key"] == recovery_v3.RECOVERY_TASK_KEY
    )
    task["status"] = status
    task["completion_classification"] = classification
    payload["facts"]["artifacts"] = sorted({*payload["facts"]["artifacts"], *facts})
    return ControlPlaneManifest.from_dict(payload)


class _RecoveryV3Cursor:
    def __init__(
        self,
        manifest: ControlPlaneManifest,
        *,
        current: ControlPlaneManifest | None = None,
        runtime_events: list[dict] | None = None,
        registrations: list[dict] | None = None,
    ):
        self.manifest = manifest
        self.current = current or manifest
        self.baseline = _terminal_recovery_v2_manifest()
        self.predecessor_events = [
            {
                "event_digest": recovery_v3.OLD_STARTED_EVENT_DIGEST,
                "execution_id": recovery_v3.OLD_EXECUTION_ID,
                "manifest_digest": recovery_v3.OLD_EVENT_MANIFEST_DIGEST,
                "task_digest": recovery_v3.OLD_TASK_DIGEST,
                "task_key": recovery_v3.OLD_TASK_KEY,
                "event_type": "started",
                "sequence": 0,
            },
            {
                "event_digest": recovery_v3.OLD_FAILED_EVENT_DIGEST,
                "execution_id": recovery_v3.OLD_EXECUTION_ID,
                "manifest_digest": recovery_v3.OLD_EVENT_MANIFEST_DIGEST,
                "task_digest": recovery_v3.OLD_TASK_DIGEST,
                "task_key": recovery_v3.OLD_TASK_KEY,
                "event_type": "failed",
                "sequence": 1,
            },
        ]
        self.runtime_events = runtime_events or []
        self.registrations = registrations or []
        self.statements: list[str] = []

    def execute(self, statement, parameters=()):
        query = " ".join(str(statement).split())
        self.statements.append(query)
        assert query.startswith("SELECT")
        if "FROM research_os_control_planes" in query:
            return _Rows(one={"current_manifest_digest": self.current.artifact_digest})
        if "FROM research_os_manifests" in query:
            stored = self.baseline if parameters == (recovery_v3.INPUT_MANIFEST_DIGEST,) else self.current
            return _Rows(one={"manifest_json": stored.to_dict(include_digest=True)})
        if "FROM research_os_mainline_execution_events" in query:
            return _Rows(
                many=(
                    self.predecessor_events
                    if parameters[1] == recovery_v3.OLD_TASK_KEY
                    else self.runtime_events
                )
            )
        if "FROM research_os_mainline_artifacts" in query:
            return _Rows(
                many=[] if parameters[1] == recovery_v3.OLD_TASK_KEY else self.registrations
            )
        raise AssertionError(query)


def _recovery_v3_runtime_fixture(
    terminal: str,
) -> tuple[ControlPlaneManifest, ControlPlaneManifest, list[dict], list[dict]]:
    ready = _active_recovery_v3_manifest()
    running = _transition_recovery_v3_manifest(
        ready, status="running", classification="INTEGRATED"
    )
    task = next(item for item in ready.tasks if item.task_key == recovery_v3.RECOVERY_TASK_KEY)
    git_commit = "b" * 40
    execution_id = stable_hash(
        {
            "schema": "dehps-research-os-mainline-execution.v1",
            "control_plane_key": "m4-information-theory-mainline",
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "input_artifact_digests": task.input_artifact_digests,
            "git_commit": git_commit,
        }
    )
    started = MainlineExecutionEvent(
        execution_id=execution_id,
        control_plane_key="m4-information-theory-mainline",
        manifest_digest=running.artifact_digest,
        task_key=task.task_key,
        task_digest=task.artifact_digest,
        capability=str(task.requested_capability),
        event_type="started",
        sequence=0,
        recorded_at="2026-08-15T01:00:00+00:00",
        payload=(("input_artifact_digests", list(task.input_artifact_digests)), ("git_commit", git_commit)),
    )
    if terminal == "RUNNING":
        return running, running, [_event_row(started)], []
    if terminal == "FAILED":
        failed = _transition_recovery_v3_manifest(
            running, status="failed", classification="INTEGRATED"
        )
        event = MainlineExecutionEvent(
            execution_id=execution_id,
            control_plane_key="m4-information-theory-mainline",
            manifest_digest=running.artifact_digest,
            task_key=task.task_key,
            task_digest=task.artifact_digest,
            capability=str(task.requested_capability),
            event_type="failed",
            sequence=1,
            recorded_at="2026-08-15T01:01:00+00:00",
            payload=(("error", "frozen failure"), ("git_commit", git_commit)),
        )
        return failed, running, [_event_row(started), _event_row(event)], []
    if terminal != "COMPLETED":
        raise AssertionError(terminal)
    metric = json.loads(task.metric_contract)
    route = "DEEPER_VALIDATION_REQUIRED"
    route_fact = metric["route_facts"][route]
    completion_fact = metric["completion_fact"]
    route_digest = "c" * 64
    execution_artifact_digest = "d" * 64
    mainline_fact = (
        f"mainline-execution:{task.task_key}:{task.artifact_digest}:"
        f"{execution_id}:completed"
    )
    completed = _transition_recovery_v3_manifest(
        running,
        status="completed",
        classification="COMPLETE",
        facts=(mainline_fact, route_fact, completion_fact),
    )
    route_path = metric["route_artifact_path_template"].format(
        execution_id=execution_id, artifact_digest=route_digest
    )
    execution_path = f"runtime/research-os/mainline/tasks/{task.task_key}/{execution_id}/execution.json"
    route_registration = MainlineArtifactRegistration(
        execution_id=execution_id,
        control_plane_key="m4-information-theory-mainline",
        task_key=task.task_key,
        task_digest=task.artifact_digest,
        artifact_digest=route_digest,
        artifact_type=metric["route_serialized_artifact_type"],
        schema_version="dehps-m4-measurement-routing-decision.v1",
        artifact_path=route_path,
        parent_digests=(),
        git_commit=git_commit,
    )
    execution_registration = MainlineArtifactRegistration(
        execution_id=execution_id,
        control_plane_key="m4-information-theory-mainline",
        task_key=task.task_key,
        task_digest=task.artifact_digest,
        artifact_digest=execution_artifact_digest,
        artifact_type="research_os_mainline_execution",
        schema_version="dehps-research-os-mainline-execution.v1",
        artifact_path=execution_path,
        parent_digests=(task.input_artifact_digests[0], route_digest),
        git_commit=git_commit,
    )
    summary = {
        "execution_artifact_digest": execution_artifact_digest,
        "execution_artifact_path": execution_path,
        "actual_fold_count": 0,
        "registered_artifact_count": 2,
        "git_commit": git_commit,
        "completion_facts": [route_fact, completion_fact],
        "additional_completed_task_keys": [],
        "publication_batch_digest": m4_v2_domain_digest(
            {
                "control_plane_key": "m4-information-theory-mainline",
                "expected_head_manifest_digest": running.artifact_digest,
                "task_key": task.task_key,
                "task_digest": task.artifact_digest,
                "execution_id": execution_id,
                "git_commit": git_commit,
                "ordered_artifact_digest_path_pairs": [
                    {"artifact_digest": route_digest, "canonical_artifact_path": route_path},
                    {"artifact_digest": execution_artifact_digest, "canonical_artifact_path": execution_path},
                ],
            },
            domain="dehps.m4.v2.mainline-publication-batch-identity.v1",
        ),
        "workload_rerun": False,
        "source_contract_digest": task.input_artifact_digests[0],
        "source_set_digest": json.loads(
            (ROOT / recovery_v3.GLOBAL_SOURCE_PATH).read_text(encoding="utf-8")
        )["source_set_digest"],
        "route_decision_artifact_digest": route_digest,
        "route": route,
        "downstream_consumer": metric["mainline_integration"]["downstream_consumer"],
        "decision_replay_coverage": "COMPLETE",
        "historical_database_reads": 0,
        "scientific_computation": 0,
        "replay_status": "REGISTERED_REPLAY_PENDING",
    }
    completed_event = MainlineExecutionEvent(
        execution_id=execution_id,
        control_plane_key="m4-information-theory-mainline",
        manifest_digest=running.artifact_digest,
        task_key=task.task_key,
        task_digest=task.artifact_digest,
        capability=str(task.requested_capability),
        event_type="completed",
        sequence=1,
        recorded_at="2026-08-15T01:01:00+00:00",
        payload=tuple(sorted(summary.items())),
    )
    return (
        completed,
        running,
        [_event_row(started), _event_row(completed_event)],
        [_registration_row(route_registration), _registration_row(execution_registration)],
    )


def _builder_symbol_module() -> ModuleType:
    module = ModuleType("_test_m4_v2_global_recovery_v2_builder")
    for symbol in repository_module._M4_V2_GLOBAL_RECOVERY_V2_REQUIRED_SYMBOLS:
        setattr(module, symbol, object())
    module.GlobalRoutingRecoveryV2Error = RuntimeError
    module.build_manifest = lambda *_args, **_kwargs: None
    module.validate_global_source_contract = lambda *_args, **_kwargs: None
    return module


def _builder_v1_symbol_module() -> ModuleType:
    module = ModuleType("_test_m4_v2_global_recovery_v1_builder")
    for symbol in repository_module._M4_V2_GLOBAL_RECOVERY_V1_REQUIRED_SYMBOLS:
        setattr(module, symbol, object())
    module.build_manifest = lambda *_args, **_kwargs: None
    return module


def test_global_recovery_v2_builder_loader_works_from_repository_root_subprocess() -> None:
    old_import = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from scripts."
                "build_m4_v2_global_routing_recovery_v2_manifest import "
                "build_manifest"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert old_import.returncode != 0
    assert "ModuleNotFoundError" in old_import.stderr
    assert (
        "scripts.build_m4_v2_global_routing_recovery_v2_manifest"
        in old_import.stderr
    )

    corrected = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import os
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.repository import (
    PostgresResearchOSRepository,
    _load_m4_v2_global_routing_recovery_v2_builder,
)

before = os.getcwd()
builder = _load_m4_v2_global_routing_recovery_v2_builder()
manifest = ControlPlaneManifest.from_dict(
    {
        "schema_version": "research-os-control-plane-v1",
        "goals": [
            {
                "goal_key": "loader-check",
                "semantic_version": "1.0.0",
                "objective_class": "maintenance_integrity",
                "status": "active",
                "baseline_metric_manifest": {"metric": "loader", "value": 0},
                "target_metric_manifest": {"metric": "loader", "value": 1},
                "success_evidence": ["loader:verified"],
                "owner_lane": "maintenance",
                "guardrails": ["no_runtime_mutation"],
            }
        ],
        "tasks": [],
        "facts": {},
    }
)
PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v2_import(
    None,
    control_plane_key="m4-information-theory-mainline",
    manifest=manifest,
)
assert builder.__name__ == "_dehps_m4_v2_global_routing_recovery_v2_builder"
assert os.getcwd() == before
""",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert corrected.returncode == 0, corrected.stderr


def test_global_recovery_v1_builder_loader_works_from_repository_root_subprocess() -> None:
    old_import = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from scripts."
                "build_m4_v2_global_routing_recovery_manifest import "
                "build_manifest"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert old_import.returncode != 0
    assert "ModuleNotFoundError" in old_import.stderr
    assert "scripts.build_m4_v2_global_routing_recovery_manifest" in old_import.stderr

    corrected = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import os
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.repository import (
    PostgresResearchOSRepository,
    _load_m4_v2_global_routing_recovery_v1_builder,
    _load_m4_v2_global_routing_recovery_v2_builder,
)

before = os.getcwd()
v2_builder = _load_m4_v2_global_routing_recovery_v2_builder()
v1_builder = _load_m4_v2_global_routing_recovery_v1_builder()
manifest = ControlPlaneManifest.from_dict(
    {
        "schema_version": "research-os-control-plane-v1",
        "goals": [
            {
                "goal_key": "loader-check",
                "semantic_version": "1.0.0",
                "objective_class": "maintenance_integrity",
                "status": "active",
                "baseline_metric_manifest": {"metric": "loader", "value": 0},
                "target_metric_manifest": {"metric": "loader", "value": 1},
                "success_evidence": ["loader:verified"],
                "owner_lane": "maintenance",
                "guardrails": ["no_runtime_mutation"],
            }
        ],
        "tasks": [],
        "facts": {},
    }
)
PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v2_import(
    None,
    control_plane_key="m4-information-theory-mainline",
    manifest=manifest,
)
PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_import(
    None,
    control_plane_key="m4-information-theory-mainline",
    manifest=manifest,
)
assert v2_builder.__name__ == "_dehps_m4_v2_global_routing_recovery_v2_builder"
assert v1_builder.__name__ == "_dehps_m4_v2_global_routing_recovery_v1_builder"
assert os.getcwd() == before
""",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert corrected.returncode == 0, corrected.stderr


def test_global_recovery_v1_builder_loader_rejects_invalid_paths(
    monkeypatch, tmp_path
) -> None:
    def assert_unavailable() -> BaseException:
        with pytest.raises(
            ResearchOSValidationError,
            match="^m4_v2_global_recovery_v1_builder_unavailable$",
        ) as error:
            repository_module._load_m4_v2_global_routing_recovery_v1_builder()
        assert error.value.__cause__ is not None
        return error.value.__cause__

    monkeypatch.setattr(dehps_config, "ROOT_DIR", tmp_path / "missing-root")
    assert isinstance(assert_unavailable(), FileNotFoundError)

    non_file_root = tmp_path / "non-file-root"
    non_file_path = (
        non_file_root
        / "apps/worker-python/scripts/"
        "build_m4_v2_global_routing_recovery_manifest.py"
    )
    non_file_path.mkdir(parents=True)
    monkeypatch.setattr(dehps_config, "ROOT_DIR", non_file_root)
    assert isinstance(assert_unavailable(), FileNotFoundError)

    outside = tmp_path / "outside-builder.py"
    outside.write_text("raise RuntimeError('must not execute')\n", encoding="utf-8")
    escaped_root = tmp_path / "escaped-root"
    escaped_path = (
        escaped_root
        / "apps/worker-python/scripts/"
        "build_m4_v2_global_routing_recovery_manifest.py"
    )
    escaped_path.parent.mkdir(parents=True)
    escaped_path.symlink_to(outside)
    monkeypatch.setattr(dehps_config, "ROOT_DIR", escaped_root)
    assert isinstance(assert_unavailable(), ValueError)

    wrong_root = tmp_path / "wrong-root"
    wrong_path = (
        wrong_root
        / "apps/worker-python/scripts/"
        "build_m4_v2_global_routing_recovery_manifest.py"
    )
    wrong_path.parent.mkdir(parents=True)
    wrong_path.write_text("raise RuntimeError('wrong builder')\n", encoding="utf-8")
    monkeypatch.setattr(dehps_config, "ROOT_DIR", wrong_root)
    cause = assert_unavailable()
    assert isinstance(cause, RuntimeError)
    assert str(cause) == "wrong builder"


def test_global_recovery_v1_builder_loader_fail_closed_matrix(monkeypatch) -> None:
    def assert_unavailable() -> BaseException:
        with pytest.raises(
            ResearchOSValidationError,
            match="^m4_v2_global_recovery_v1_builder_unavailable$",
        ) as error:
            repository_module._load_m4_v2_global_routing_recovery_v1_builder()
        assert error.value.__cause__ is not None
        return error.value.__cause__

    monkeypatch.setattr(
        repository_module.importlib.util,
        "spec_from_file_location",
        lambda *_args: None,
    )
    assert isinstance(assert_unavailable(), ImportError)

    monkeypatch.setattr(
        repository_module.importlib.util,
        "spec_from_file_location",
        lambda *_args: SimpleNamespace(loader=None),
    )
    assert isinstance(assert_unavailable(), ImportError)

    class ExplodingLoader:
        def exec_module(self, _module):
            raise LookupError("builder exec failed")

    spec = SimpleNamespace(loader=ExplodingLoader())
    module = _builder_v1_symbol_module()
    monkeypatch.setattr(
        repository_module.importlib.util,
        "spec_from_file_location",
        lambda *_args: spec,
    )
    monkeypatch.setattr(
        repository_module.importlib.util,
        "module_from_spec",
        lambda _spec: module,
    )
    cause = assert_unavailable()
    assert isinstance(cause, LookupError)
    assert str(cause) == "builder exec failed"


@pytest.mark.parametrize(
    "missing_symbol",
    repository_module._M4_V2_GLOBAL_RECOVERY_V1_REQUIRED_SYMBOLS,
)
def test_global_recovery_v1_builder_loader_requires_every_symbol(
    monkeypatch, missing_symbol
) -> None:
    module = _builder_v1_symbol_module()
    delattr(module, missing_symbol)
    spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _module: None))
    monkeypatch.setattr(
        repository_module.importlib.util,
        "spec_from_file_location",
        lambda *_args: spec,
    )
    monkeypatch.setattr(
        repository_module.importlib.util,
        "module_from_spec",
        lambda _spec: module,
    )
    with pytest.raises(
        ResearchOSValidationError,
        match="^m4_v2_global_recovery_v1_builder_unavailable$",
    ) as error:
        repository_module._load_m4_v2_global_routing_recovery_v1_builder()
    assert isinstance(error.value.__cause__, AttributeError)
    assert error.value.__cause__.args == (missing_symbol,)


def test_global_recovery_v1_builder_loader_requires_callable_build(
    monkeypatch,
) -> None:
    module = _builder_v1_symbol_module()
    module.build_manifest = None
    spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _module: None))
    monkeypatch.setattr(
        repository_module.importlib.util,
        "spec_from_file_location",
        lambda *_args: spec,
    )
    monkeypatch.setattr(
        repository_module.importlib.util,
        "module_from_spec",
        lambda _spec: module,
    )
    with pytest.raises(
        ResearchOSValidationError,
        match="^m4_v2_global_recovery_v1_builder_unavailable$",
    ) as error:
        repository_module._load_m4_v2_global_routing_recovery_v1_builder()
    assert isinstance(error.value.__cause__, TypeError)
    assert error.value.__cause__.args == ("build_manifest",)


def test_global_recovery_v1_validator_uses_one_module_for_all_symbols(
    monkeypatch,
) -> None:
    accesses: list[tuple[int, str]] = []

    class RecordingModule(ModuleType):
        def __getattribute__(self, name):
            if name in repository_module._M4_V2_GLOBAL_RECOVERY_V1_REQUIRED_SYMBOLS:
                accesses.append((id(self), name))
            return super().__getattribute__(name)

    module = RecordingModule("_recording_recovery_v1_builder")
    values = _builder_v1_symbol_module()
    for symbol in repository_module._M4_V2_GLOBAL_RECOVERY_V1_REQUIRED_SYMBOLS:
        setattr(module, symbol, getattr(values, symbol))
    module.RECOVERY_TASK_KEY = "not-present"
    calls = 0

    def load_once():
        nonlocal calls
        calls += 1
        return module

    monkeypatch.setattr(
        repository_module,
        "_load_m4_v2_global_routing_recovery_v1_builder",
        load_once,
    )
    manifest = ControlPlaneManifest.from_dict(_manifest())
    PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_import(
        None,
        control_plane_key="m4-information-theory-mainline",
        manifest=manifest,
    )
    assert calls == 1
    assert {owner for owner, _symbol in accesses} == {id(module)}
    assert [symbol for _owner, symbol in accesses] == list(
        repository_module._M4_V2_GLOBAL_RECOVERY_V1_REQUIRED_SYMBOLS
    )


def test_global_recovery_v2_builder_loader_rejects_invalid_paths(
    monkeypatch, tmp_path
) -> None:
    def assert_unavailable() -> BaseException:
        with pytest.raises(
            ResearchOSValidationError,
            match="^m4_v2_global_recovery_v2_builder_unavailable$",
        ) as error:
            repository_module._load_m4_v2_global_routing_recovery_v2_builder()
        assert error.value.__cause__ is not None
        return error.value.__cause__

    monkeypatch.setattr(dehps_config, "ROOT_DIR", tmp_path / "missing-root")
    assert isinstance(assert_unavailable(), FileNotFoundError)

    non_file_root = tmp_path / "non-file-root"
    non_file_path = (
        non_file_root
        / "apps/worker-python/scripts/"
        "build_m4_v2_global_routing_recovery_v2_manifest.py"
    )
    non_file_path.mkdir(parents=True)
    monkeypatch.setattr(dehps_config, "ROOT_DIR", non_file_root)
    assert isinstance(assert_unavailable(), FileNotFoundError)

    outside = tmp_path / "outside-builder.py"
    outside.write_text("raise RuntimeError('must not execute')\n", encoding="utf-8")
    escaped_root = tmp_path / "escaped-root"
    escaped_path = (
        escaped_root
        / "apps/worker-python/scripts/"
        "build_m4_v2_global_routing_recovery_v2_manifest.py"
    )
    escaped_path.parent.mkdir(parents=True)
    escaped_path.symlink_to(outside)
    monkeypatch.setattr(dehps_config, "ROOT_DIR", escaped_root)
    assert isinstance(assert_unavailable(), ValueError)

    wrong_root = tmp_path / "wrong-root"
    wrong_path = (
        wrong_root
        / "apps/worker-python/scripts/"
        "build_m4_v2_global_routing_recovery_v2_manifest.py"
    )
    wrong_path.parent.mkdir(parents=True)
    wrong_path.write_text("raise RuntimeError('wrong builder')\n", encoding="utf-8")
    monkeypatch.setattr(dehps_config, "ROOT_DIR", wrong_root)
    cause = assert_unavailable()
    assert isinstance(cause, RuntimeError)
    assert str(cause) == "wrong builder"


def test_global_recovery_v2_builder_loader_fail_closed_matrix(monkeypatch) -> None:
    def assert_unavailable() -> BaseException:
        with pytest.raises(
            ResearchOSValidationError,
            match="^m4_v2_global_recovery_v2_builder_unavailable$",
        ) as error:
            repository_module._load_m4_v2_global_routing_recovery_v2_builder()
        assert error.value.__cause__ is not None
        return error.value.__cause__

    monkeypatch.setattr(
        repository_module.importlib.util,
        "spec_from_file_location",
        lambda *_args: None,
    )
    assert isinstance(assert_unavailable(), ImportError)

    monkeypatch.setattr(
        repository_module.importlib.util,
        "spec_from_file_location",
        lambda *_args: SimpleNamespace(loader=None),
    )
    assert isinstance(assert_unavailable(), ImportError)

    class ExplodingLoader:
        def exec_module(self, _module):
            raise LookupError("builder exec failed")

    spec = SimpleNamespace(loader=ExplodingLoader())
    module = _builder_symbol_module()
    monkeypatch.setattr(
        repository_module.importlib.util,
        "spec_from_file_location",
        lambda *_args: spec,
    )
    monkeypatch.setattr(
        repository_module.importlib.util,
        "module_from_spec",
        lambda _spec: module,
    )
    cause = assert_unavailable()
    assert isinstance(cause, LookupError)
    assert str(cause) == "builder exec failed"


@pytest.mark.parametrize(
    "missing_symbol",
    repository_module._M4_V2_GLOBAL_RECOVERY_V2_REQUIRED_SYMBOLS,
)
def test_global_recovery_v2_builder_loader_requires_every_symbol(
    monkeypatch, missing_symbol
) -> None:
    module = _builder_symbol_module()
    delattr(module, missing_symbol)
    spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _module: None))
    monkeypatch.setattr(
        repository_module.importlib.util,
        "spec_from_file_location",
        lambda *_args: spec,
    )
    monkeypatch.setattr(
        repository_module.importlib.util,
        "module_from_spec",
        lambda _spec: module,
    )
    with pytest.raises(
        ResearchOSValidationError,
        match="^m4_v2_global_recovery_v2_builder_unavailable$",
    ) as error:
        repository_module._load_m4_v2_global_routing_recovery_v2_builder()
    assert isinstance(error.value.__cause__, AttributeError)
    assert error.value.__cause__.args == (missing_symbol,)


@pytest.mark.parametrize(
    "symbol", ("build_manifest", "validate_global_source_contract")
)
def test_global_recovery_v2_builder_loader_requires_callable_functions(
    monkeypatch, symbol
) -> None:
    module = _builder_symbol_module()
    setattr(module, symbol, None)
    spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _module: None))
    monkeypatch.setattr(
        repository_module.importlib.util,
        "spec_from_file_location",
        lambda *_args: spec,
    )
    monkeypatch.setattr(
        repository_module.importlib.util,
        "module_from_spec",
        lambda _spec: module,
    )
    with pytest.raises(
        ResearchOSValidationError,
        match="^m4_v2_global_recovery_v2_builder_unavailable$",
    ) as error:
        repository_module._load_m4_v2_global_routing_recovery_v2_builder()
    assert isinstance(error.value.__cause__, TypeError)
    assert error.value.__cause__.args == (symbol,)


def test_global_recovery_v2_builder_loader_requires_exception_class(
    monkeypatch,
) -> None:
    module = _builder_symbol_module()
    module.GlobalRoutingRecoveryV2Error = object()
    spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _module: None))
    monkeypatch.setattr(
        repository_module.importlib.util,
        "spec_from_file_location",
        lambda *_args: spec,
    )
    monkeypatch.setattr(
        repository_module.importlib.util,
        "module_from_spec",
        lambda _spec: module,
    )
    with pytest.raises(
        ResearchOSValidationError,
        match="^m4_v2_global_recovery_v2_builder_unavailable$",
    ) as error:
        repository_module._load_m4_v2_global_routing_recovery_v2_builder()
    assert isinstance(error.value.__cause__, TypeError)
    assert error.value.__cause__.args == ("GlobalRoutingRecoveryV2Error",)


def test_global_recovery_v2_validator_uses_one_module_for_all_symbols(
    monkeypatch,
) -> None:
    accesses: list[tuple[int, str]] = []

    class RecordingModule(ModuleType):
        def __getattribute__(self, name):
            if name in repository_module._M4_V2_GLOBAL_RECOVERY_V2_REQUIRED_SYMBOLS:
                accesses.append((id(self), name))
            return super().__getattribute__(name)

    module = RecordingModule("_recording_recovery_v2_builder")
    values = _builder_symbol_module()
    for symbol in repository_module._M4_V2_GLOBAL_RECOVERY_V2_REQUIRED_SYMBOLS:
        setattr(module, symbol, getattr(values, symbol))
    module.RECOVERY_TASK_KEY = recovery_v2.RECOVERY_TASK_KEY
    calls = 0

    def load_once():
        nonlocal calls
        calls += 1
        return module

    monkeypatch.setattr(
        repository_module,
        "_load_m4_v2_global_routing_recovery_v2_builder",
        load_once,
    )
    manifest = ControlPlaneManifest.from_dict(_manifest())
    PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v2_import(
        None,
        control_plane_key="not-the-global-control-plane",
        manifest=manifest,
    )
    assert calls == 1
    assert {owner for owner, _symbol in accesses} == {id(module)}
    assert [symbol for _owner, symbol in accesses] == list(
        repository_module._M4_V2_GLOBAL_RECOVERY_V2_REQUIRED_SYMBOLS
    )


def test_global_recovery_v2_prewrite_validator_is_result_blind_and_fail_closed() -> None:
    manifest = _active_recovery_v2_manifest()
    cursor = _RecoveryV2Cursor(manifest)
    PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v2_import(
        cursor,
        control_plane_key="m4-information-theory-mainline",
        manifest=manifest,
    )
    assert cursor.statements

    mutations = (
        lambda candidate: candidate.state.update(declared_status="completed"),
        lambda candidate: candidate.events[0].update(event_digest="0" * 64),
        lambda candidate: setattr(candidate, "baseline", candidate.manifest),
        lambda candidate: setattr(
            candidate,
            "old_definition",
            next(
                task
                for task in candidate.manifest.tasks
                if task.task_key == recovery_v2.RECOVERY_TASK_KEY
            ),
        ),
    )
    for mutate in mutations:
        changed = _RecoveryV2Cursor(manifest)
        mutate(changed)
        with pytest.raises(ResearchOSValidationError):
            PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v2_import(
                changed,
                control_plane_key="m4-information-theory-mainline",
                manifest=manifest,
            )
        assert all(statement.startswith("SELECT") for statement in changed.statements)

    payload = manifest.to_dict(include_digest=False)
    unrelated = copy.deepcopy(payload)
    unrelated["facts"]["external_events"].append("unregistered-idempotent-drift")
    changed = _RecoveryV2Cursor(ControlPlaneManifest.from_dict(unrelated))
    with pytest.raises(
        ResearchOSValidationError, match="m4_v2_global_recovery_v2_output_changed"
    ):
        PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v2_import(
            changed,
            control_plane_key="m4-information-theory-mainline",
            manifest=changed.manifest,
        )

    p3_key = recovery_v2.P3_REVISIONS[0][0]
    p3 = next(task for task in payload["tasks"] if task["task_key"] == p3_key)
    p3["priority"] += 1
    changed_manifest = ControlPlaneManifest.from_dict(payload)
    changed = _RecoveryV2Cursor(changed_manifest)
    with pytest.raises(
        ResearchOSValidationError, match="m4_v2_global_recovery_v2_output_changed"
    ):
        PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v2_import(
            changed,
            control_plane_key="m4-information-theory-mainline",
            manifest=changed_manifest,
        )


def test_global_recovery_v2_lifecycle_automaton_accepts_only_exact_stages() -> None:
    baseline = _recovery_v2_baseline_manifest()
    ready = _active_recovery_v2_manifest()
    running = _transition_recovery_v2_manifest(
        ready,
        status="running",
        classification="INTEGRATED",
    )
    running_with_event, _, started, _ = _recovery_v2_runtime_fixture("RUNNING")
    failed, _, failed_events, _ = _recovery_v2_runtime_fixture("FAILED")
    completed, _, completed_events, registrations = (
        _recovery_v2_runtime_fixture("COMPLETED")
    )
    cases = (
        (baseline, baseline, [], []),
        (ready, baseline, [], []),
        (ready, ready, [], []),
        (running, ready, [], []),
        (running, running, [], []),
        (running_with_event, running_with_event, started, []),
        (failed, running, failed_events, []),
        (failed, failed, failed_events, []),
        (completed, running, completed_events, registrations),
        (completed, completed, completed_events, registrations),
    )
    for incoming, current, events, artifacts in cases:
        cursor = _RecoveryV2Cursor(
            incoming,
            current=current,
            runtime_events=copy.deepcopy(events),
            registrations=copy.deepcopy(artifacts),
        )
        PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v2_import(
            cursor,
            control_plane_key="m4-information-theory-mainline",
            manifest=incoming,
        )
        assert all(statement.startswith("SELECT") for statement in cursor.statements)


@pytest.mark.parametrize(
    ("current_stage", "incoming_stage"),
    (
        ("READY", "COMPLETED"),
        ("READY", "FAILED"),
        ("RUNNING", "READY"),
        ("FAILED", "RUNNING"),
        ("COMPLETED", "RUNNING"),
    ),
)
def test_global_recovery_v2_lifecycle_rejects_stage_skips_and_regressions(
    current_stage: str,
    incoming_stage: str,
) -> None:
    ready = _active_recovery_v2_manifest()
    running = _transition_recovery_v2_manifest(
        ready,
        status="running",
        classification="INTEGRATED",
    )
    failed, _, failed_events, _ = _recovery_v2_runtime_fixture("FAILED")
    completed, _, completed_events, registrations = (
        _recovery_v2_runtime_fixture("COMPLETED")
    )
    stages = {
        "READY": (ready, []),
        "RUNNING": (running, []),
        "FAILED": (failed, failed_events),
        "COMPLETED": (completed, completed_events),
    }
    incoming, incoming_events = stages[incoming_stage]
    current, current_events = stages[current_stage]
    events = incoming_events or current_events
    cursor = _RecoveryV2Cursor(
        incoming,
        current=current,
        runtime_events=copy.deepcopy(events),
        registrations=(
            copy.deepcopy(registrations)
            if "COMPLETED" in {current_stage, incoming_stage}
            else []
        ),
    )
    with pytest.raises(
        ResearchOSValidationError,
        match="^m4_v2_global_recovery_v2_output_changed$",
    ):
        PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v2_import(
            cursor,
            control_plane_key="m4-information-theory-mainline",
            manifest=incoming,
        )


@pytest.mark.parametrize(
    ("target", "field"),
    (
        ("started", "execution_id"),
        ("started", "manifest_digest"),
        ("started", "task_digest"),
        ("started", "capability"),
        ("started", "sequence"),
        ("completed", "execution_id"),
        ("completed", "manifest_digest"),
        ("completed", "task_digest"),
        ("completed", "capability"),
        ("completed", "sequence"),
        ("registration", "artifact_digest"),
        ("registration", "artifact_path"),
        ("registration", "task_digest"),
        ("registration", "git_commit"),
    ),
)
def test_global_recovery_v2_completed_metadata_tamper_fails_closed(
    target: str,
    field: str,
) -> None:
    completed, running, events, registrations = _recovery_v2_runtime_fixture(
        "COMPLETED"
    )
    if target in {"started", "completed"}:
        index = 0 if target == "started" else 1
        events[index][field] = (
            9 if field == "sequence" else ("0" * 40 if field == "git_commit" else "0" * 64)
        )
    else:
        registrations[0][field] = (
            "0" * 40 if field == "git_commit" else "0" * 64
        )
    cursor = _RecoveryV2Cursor(
        completed,
        current=running,
        runtime_events=events,
        registrations=registrations,
    )
    with pytest.raises(
        ResearchOSValidationError,
        match="^m4_v2_global_recovery_v2_output_changed$",
    ):
        PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v2_import(
            cursor,
            control_plane_key="m4-information-theory-mainline",
            manifest=completed,
        )


def test_global_recovery_v2_recomputes_publication_batch_digest() -> None:
    completed, running, events, registrations = _recovery_v2_runtime_fixture(
        "COMPLETED"
    )
    raw = copy.deepcopy(events[1]["event_json"])
    payload = dict(raw["payload"])
    payload["publication_batch_digest"] = "0" * 64
    changed = MainlineExecutionEvent(
        execution_id=str(raw["execution_id"]),
        control_plane_key=str(raw["control_plane_key"]),
        manifest_digest=str(raw["manifest_digest"]),
        task_key=str(raw["task_key"]),
        task_digest=str(raw["task_digest"]),
        capability=str(raw["capability"]),
        event_type=str(raw["event_type"]),
        sequence=int(raw["sequence"]),
        recorded_at=str(raw["recorded_at"]),
        payload=tuple(sorted(payload.items())),
    )
    events[1] = _event_row(changed)
    cursor = _RecoveryV2Cursor(
        completed,
        current=running,
        runtime_events=events,
        registrations=registrations,
    )
    with pytest.raises(
        ResearchOSValidationError,
        match="^m4_v2_global_recovery_v2_output_changed$",
    ):
        PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v2_import(
            cursor,
            control_plane_key="m4-information-theory-mainline",
            manifest=completed,
        )


def test_global_recovery_v2_failed_metadata_is_terminal_and_registration_free() -> None:
    failed, running, events, _ = _recovery_v2_runtime_fixture("FAILED")
    mutations = []

    changed_event = copy.deepcopy(events)
    changed_event[1]["event_type"] = "completed"
    mutations.append((failed, changed_event, []))

    third_event = copy.deepcopy(events)
    third_event.append(copy.deepcopy(third_event[1]))
    mutations.append((failed, third_event, []))

    _, _, _, completed_registrations = _recovery_v2_runtime_fixture("COMPLETED")
    mutations.append((failed, copy.deepcopy(events), completed_registrations[:1]))

    payload = failed.to_dict(include_digest=False)
    payload["facts"]["artifacts"].append("m4-v2-routing:FORGED")
    mutations.append(
        (ControlPlaneManifest.from_dict(payload), copy.deepcopy(events), [])
    )

    for incoming, runtime_events, registrations in mutations:
        cursor = _RecoveryV2Cursor(
            incoming,
            current=running,
            runtime_events=runtime_events,
            registrations=registrations,
        )
        with pytest.raises(
            ResearchOSValidationError,
            match="^m4_v2_global_recovery_v2_output_changed$",
        ):
            PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v2_import(
                cursor,
                control_plane_key="m4-information-theory-mainline",
                manifest=incoming,
            )


@pytest.mark.parametrize(
    "typed_offset",
    (timezone(timedelta(hours=-4)), timezone(timedelta(hours=5, minutes=30))),
)
def test_global_recovery_v2_event_timestamps_compare_as_utc_instants(
    typed_offset,
) -> None:
    failed, running, events, _ = _recovery_v2_runtime_fixture("FAILED")
    for index, row in enumerate(events):
        instant = datetime.fromisoformat(str(row["recorded_at"]))
        events[index] = _event_row_with_recorded_at(
            row,
            instant.astimezone(typed_offset).isoformat(),
        )
        events[index]["recorded_at"] = instant.astimezone(
            ZoneInfo("Asia/Shanghai")
        )
    cursor = _RecoveryV2Cursor(
        failed,
        current=running,
        runtime_events=events,
        registrations=[],
    )
    PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v2_import(
        cursor,
        control_plane_key="m4-information-theory-mainline",
        manifest=failed,
    )


@pytest.mark.parametrize(
    ("target", "value"),
    (
        ("row", datetime.fromisoformat("2026-08-14T10:00:00")),
        ("typed", "2026-08-14T10:00:00"),
        ("row", ""),
        ("row", "not-a-timestamp"),
        ("row", 123),
        ("row", datetime(2026, 8, 14, 10, 0, 1, tzinfo=UTC)),
    ),
)
def test_global_recovery_v2_event_timestamp_rejects_invalid_or_different_instants(
    target: str,
    value,
) -> None:
    failed, running, events, _ = _recovery_v2_runtime_fixture("FAILED")
    if target == "typed":
        events[0] = _event_row_with_recorded_at(events[0], value)
        events[0]["recorded_at"] = datetime(
            2026, 8, 14, 10, 0, tzinfo=UTC
        )
    else:
        events[0]["recorded_at"] = value
    cursor = _RecoveryV2Cursor(
        failed,
        current=running,
        runtime_events=events,
        registrations=[],
    )
    with pytest.raises(
        ResearchOSValidationError,
        match="^m4_v2_global_recovery_v2_output_changed$",
    ):
        PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v2_import(
            cursor,
            control_plane_key="m4-information-theory-mainline",
            manifest=failed,
        )


def test_mainline_completion_hook_reaches_shared_global_recovery_v2_policy(
    monkeypatch,
) -> None:
    manifest, _, _, _ = _recovery_v2_runtime_fixture("COMPLETED")
    calls: list[str] = []

    def verify(_cursor, *, control_plane_key, manifest):
        calls.append(f"{control_plane_key}:{manifest.artifact_digest}")

    monkeypatch.setattr(
        PostgresResearchOSRepository,
        "_verify_m4_v2_failed_global_routing_recovery_v2_import",
        verify,
    )
    monkeypatch.setattr(
        repository_module,
        "completion_execution_ids",
        lambda *_args, **_kwargs: (),
    )
    PostgresResearchOSRepository._verify_mainline_completion_records(
        object(),
        control_plane_key="m4-information-theory-mainline",
        manifest=manifest,
    )
    assert calls == [
        f"m4-information-theory-mainline:{manifest.artifact_digest}"
    ]
    calls.clear()
    PostgresResearchOSRepository._verify_mainline_completion_records(
        object(),
        control_plane_key="m4-information-theory-mainline",
        manifest=manifest,
        m4_v2_lifecycle_verified=True,
    )
    assert calls == []


def test_atomic_completed_helper_runs_shared_policy_before_manifest_writes() -> None:
    from dehps.research_os.supervisor import _atomic_import_completed_manifest

    completed, running, _, _ = _recovery_v2_runtime_fixture("COMPLETED")
    statements: list[str] = []
    policy_calls: list[str] = []

    class Cursor:
        def execute(self, statement, _parameters=()):
            query = " ".join(str(statement).split())
            statements.append(query)
            if query.startswith("SELECT current_manifest_digest"):
                return _Rows(
                    one={"current_manifest_digest": running.artifact_digest}
                )
            raise AssertionError("atomic manifest write preceded shared policy")

    class Repository:
        def _verify_mainline_completion_records(
            self,
            _cursor,
            *,
            control_plane_key,
            manifest,
        ):
            policy_calls.append(
                f"{control_plane_key}:{manifest.artifact_digest}"
            )
            raise ResearchOSValidationError("shared-policy-rejected")

    with pytest.raises(
        ResearchOSValidationError,
        match="^shared-policy-rejected$",
    ):
        _atomic_import_completed_manifest(
            repository=Repository(),  # type: ignore[arg-type]
            cursor=Cursor(),
            control_plane_key="m4-information-theory-mainline",
            expected_head_manifest_digest=running.artifact_digest,
            completed_manifest=completed,
        )
    assert statements == [
        (
            "SELECT current_manifest_digest FROM research_os_control_planes "
            "WHERE control_plane_key = %s FOR UPDATE"
        )
    ]
    assert policy_calls == [
        f"m4-information-theory-mainline:{completed.artifact_digest}"
    ]


def test_global_recovery_v2_import_rolls_back_before_first_write(monkeypatch) -> None:
    manifest = _active_recovery_v2_manifest()
    events: list[str] = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, *_args, **_kwargs):
            events.append("write")
            raise AssertionError("SQL reached before recovery preflight")

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, *_args):
            events.append("rollback" if exc_type else "commit")
            return False

        def cursor(self, **_kwargs):
            return Cursor()

    @contextmanager
    def connection_factory():
        with Connection() as connection:
            yield connection

    repository = PostgresResearchOSRepository(connection_factory)  # type: ignore[arg-type]

    def reject(*_args, **_kwargs):
        raise ResearchOSValidationError("frozen-v2-prewrite-rejected")

    monkeypatch.setattr(
        repository,
        "_verify_m4_v2_failed_global_routing_recovery_v2_import",
        reject,
    )
    with pytest.raises(ResearchOSValidationError, match="frozen-v2-prewrite-rejected"):
        repository.import_manifest(
            control_plane_key="m4-information-theory-mainline",
            payload=manifest.to_dict(include_digest=True),
        )
    assert events == ["rollback"]


def test_global_recovery_v3_builder_loader_works_from_repository_root_subprocess() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from dehps.research_os.repository import "
                "_load_m4_v2_global_routing_recovery_v3_builder as load; "
                "builder=load(); print(builder.__name__, builder.RECOVERY_TASK_KEY)"
            ),
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "apps/worker-python")},
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == (
        "_dehps_m4_v2_global_routing_recovery_v3_builder "
        "m4-v2-global-routing-recovery-v3"
    )


def test_global_recovery_v3_lifecycle_accepts_only_exact_finite_stages() -> None:
    baseline = _terminal_recovery_v2_manifest()
    ready = _active_recovery_v3_manifest()
    running = _transition_recovery_v3_manifest(
        ready, status="running", classification="INTEGRATED"
    )
    running_with_event, _, started, _ = _recovery_v3_runtime_fixture("RUNNING")
    failed, _, failed_events, _ = _recovery_v3_runtime_fixture("FAILED")
    completed, _, completed_events, registrations = _recovery_v3_runtime_fixture(
        "COMPLETED"
    )
    cases = (
        (baseline, baseline, [], []),
        (ready, baseline, [], []),
        (ready, ready, [], []),
        (running, ready, [], []),
        (running_with_event, running, started, []),
        (failed, running, failed_events, []),
        (failed, failed, failed_events, []),
        (completed, running, completed_events, registrations),
        (completed, completed, completed_events, registrations),
    )
    for incoming, current, events, artifacts in cases:
        cursor = _RecoveryV3Cursor(
            incoming,
            current=current,
            runtime_events=copy.deepcopy(events),
            registrations=copy.deepcopy(artifacts),
        )
        PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v3_import(
            cursor,
            control_plane_key="m4-information-theory-mainline",
            manifest=incoming,
        )
        assert all(statement.startswith("SELECT") for statement in cursor.statements)


@pytest.mark.parametrize(
    ("current_stage", "incoming_stage"),
    (
        ("INPUT", "RUNNING"),
        ("READY", "COMPLETED"),
        ("READY", "FAILED"),
        ("RUNNING", "READY"),
        ("FAILED", "RUNNING"),
        ("COMPLETED", "RUNNING"),
    ),
)
def test_global_recovery_v3_rejects_stage_skips_and_regressions(
    current_stage: str, incoming_stage: str
) -> None:
    baseline = _terminal_recovery_v2_manifest()
    ready = _active_recovery_v3_manifest()
    running = _transition_recovery_v3_manifest(
        ready, status="running", classification="INTEGRATED"
    )
    failed, _, failed_events, _ = _recovery_v3_runtime_fixture("FAILED")
    completed, _, completed_events, registrations = _recovery_v3_runtime_fixture(
        "COMPLETED"
    )
    stages = {
        "INPUT": (baseline, []),
        "READY": (ready, []),
        "RUNNING": (running, []),
        "FAILED": (failed, failed_events),
        "COMPLETED": (completed, completed_events),
    }
    incoming, incoming_events = stages[incoming_stage]
    current, current_events = stages[current_stage]
    cursor = _RecoveryV3Cursor(
        incoming,
        current=current,
        runtime_events=copy.deepcopy(incoming_events or current_events),
        registrations=(
            copy.deepcopy(registrations)
            if "COMPLETED" in {current_stage, incoming_stage}
            else []
        ),
    )
    with pytest.raises(
        ResearchOSValidationError,
        match="^m4_v2_global_recovery_v3_output_changed$",
    ):
        PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v3_import(
            cursor,
            control_plane_key="m4-information-theory-mainline",
            manifest=incoming,
        )


@pytest.mark.parametrize(
    ("target", "field"),
    (
        ("started", "execution_id"),
        ("started", "manifest_digest"),
        ("completed", "task_digest"),
        ("completed", "sequence"),
        ("registration", "artifact_digest"),
        ("registration", "artifact_path"),
        ("registration", "git_commit"),
        ("batch", "publication_batch_digest"),
    ),
)
def test_global_recovery_v3_completed_metadata_tamper_fails_closed(
    target: str, field: str
) -> None:
    completed, running, events, registrations = _recovery_v3_runtime_fixture("COMPLETED")
    if target in {"started", "completed"}:
        index = 0 if target == "started" else 1
        events[index][field] = 9 if field == "sequence" else "0" * 64
    elif target == "registration":
        registrations[0][field] = "0" * (40 if field == "git_commit" else 64)
    else:
        raw = copy.deepcopy(events[1]["event_json"])
        payload = dict(raw["payload"])
        payload[field] = "0" * 64
        changed = MainlineExecutionEvent(
            execution_id=str(raw["execution_id"]),
            control_plane_key=str(raw["control_plane_key"]),
            manifest_digest=str(raw["manifest_digest"]),
            task_key=str(raw["task_key"]),
            task_digest=str(raw["task_digest"]),
            capability=str(raw["capability"]),
            event_type=str(raw["event_type"]),
            sequence=int(raw["sequence"]),
            recorded_at=str(raw["recorded_at"]),
            payload=tuple(sorted(payload.items())),
        )
        events[1] = _event_row(changed)
    cursor = _RecoveryV3Cursor(
        completed,
        current=running,
        runtime_events=events,
        registrations=registrations,
    )
    with pytest.raises(
        ResearchOSValidationError,
        match="^m4_v2_global_recovery_v3_output_changed$",
    ):
        PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v3_import(
            cursor,
            control_plane_key="m4-information-theory-mainline",
            manifest=completed,
        )


def test_global_recovery_v3_failed_stage_is_terminal_and_registration_free() -> None:
    failed, running, events, _ = _recovery_v3_runtime_fixture("FAILED")
    _, _, _, completed_registrations = _recovery_v3_runtime_fixture("COMPLETED")
    mutations = []
    changed_event = copy.deepcopy(events)
    changed_event[1]["event_type"] = "completed"
    mutations.append((changed_event, []))
    mutations.append((events + [copy.deepcopy(events[1])], []))
    mutations.append((copy.deepcopy(events), completed_registrations[:1]))
    for runtime_events, registrations in mutations:
        cursor = _RecoveryV3Cursor(
            failed,
            current=running,
            runtime_events=runtime_events,
            registrations=registrations,
        )
        with pytest.raises(
            ResearchOSValidationError,
            match="^m4_v2_global_recovery_v3_output_changed$",
        ):
            PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v3_import(
                cursor,
                control_plane_key="m4-information-theory-mainline",
                manifest=failed,
            )


def test_mainline_completion_hook_reaches_shared_global_recovery_v3_policy(
    monkeypatch,
) -> None:
    manifest, _, _, _ = _recovery_v3_runtime_fixture("COMPLETED")
    calls: list[str] = []

    def verify(_cursor, *, control_plane_key, manifest):
        calls.append(f"{control_plane_key}:{manifest.artifact_digest}")

    monkeypatch.setattr(
        PostgresResearchOSRepository,
        "_verify_m4_v2_failed_global_routing_recovery_v3_import",
        verify,
    )
    monkeypatch.setattr(repository_module, "completion_execution_ids", lambda *_args, **_kwargs: ())
    PostgresResearchOSRepository._verify_mainline_completion_records(
        object(),
        control_plane_key="m4-information-theory-mainline",
        manifest=manifest,
    )
    assert calls == [f"m4-information-theory-mainline:{manifest.artifact_digest}"]


def test_global_recovery_v3_import_rolls_back_before_first_write(monkeypatch) -> None:
    manifest = _active_recovery_v3_manifest()
    events: list[str] = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, *_args, **_kwargs):
            events.append("write")
            raise AssertionError("SQL reached before recovery preflight")

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, *_args):
            events.append("rollback" if exc_type else "commit")
            return False

        def cursor(self, **_kwargs):
            return Cursor()

    @contextmanager
    def connection_factory():
        with Connection() as connection:
            yield connection

    repository = PostgresResearchOSRepository(connection_factory)  # type: ignore[arg-type]

    def reject(*_args, **_kwargs):
        raise ResearchOSValidationError("frozen-v3-prewrite-rejected")

    monkeypatch.setattr(
        repository,
        "_verify_m4_v2_failed_global_routing_recovery_v3_import",
        reject,
    )
    with pytest.raises(ResearchOSValidationError, match="frozen-v3-prewrite-rejected"):
        repository.import_manifest(
            control_plane_key="m4-information-theory-mainline",
            payload=manifest.to_dict(include_digest=True),
        )
    assert events == ["rollback"]


def _probe_global_recovery_v3_import_dispatch(
    monkeypatch,
    manifest: ControlPlaneManifest,
    *,
    expected_error: str = "dispatcher-probe-complete",
) -> list[str]:
    events: list[str] = []

    class Cursor(_RecoveryV3Cursor):
        def __init__(self):
            super().__init__(
                manifest,
                current=(
                    _terminal_recovery_v2_manifest()
                    if recovery_v3.RECOVERY_TASK_KEY
                    in {task.task_key for task in manifest.tasks}
                    else manifest
                ),
            )

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, parameters=()):
            if not " ".join(str(statement).split()).startswith("SELECT"):
                events.append("write")
                raise AssertionError("SQL reached before dispatcher probe stopped")
            return super().execute(statement, parameters)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, *_args):
            events.append("rollback" if exc_type else "commit")
            return False

        def cursor(self, **_kwargs):
            return Cursor()

    @contextmanager
    def connection_factory():
        with Connection() as connection:
            yield connection

    repository = PostgresResearchOSRepository(connection_factory)  # type: ignore[arg-type]
    real_verify_v3 = (
        repository._verify_m4_v2_failed_global_routing_recovery_v3_import
    )

    def verify_v3(*_args, **_kwargs):
        events.append("v3")
        return real_verify_v3(*_args, **_kwargs)

    def verify_v2(*_args, **_kwargs):
        events.append("v2")

    def verify_v1(*_args, **_kwargs):
        events.append("v1")

    def stop_after_dispatch(*_args, **_kwargs):
        events.append("replay")
        raise ResearchOSValidationError("dispatcher-probe-complete")

    monkeypatch.setattr(
        repository,
        "_verify_m4_v2_failed_global_routing_recovery_v3_import",
        verify_v3,
    )
    monkeypatch.setattr(
        repository,
        "_verify_m4_v2_failed_global_routing_recovery_v2_import",
        verify_v2,
    )
    monkeypatch.setattr(
        repository,
        "_verify_m4_v2_failed_global_routing_recovery_import",
        verify_v1,
    )
    monkeypatch.setattr(
        repository,
        "_verify_m4_v2_failed_replay_recovery_import",
        stop_after_dispatch,
    )
    with pytest.raises(ResearchOSValidationError, match=f"^{expected_error}$"):
        repository.import_manifest(
            control_plane_key="m4-information-theory-mainline",
            payload=manifest.to_dict(include_digest=True),
        )
    return events


def test_global_recovery_v3_import_dispatches_valid_successor_without_reentering_v2(
    monkeypatch,
) -> None:
    events = _probe_global_recovery_v3_import_dispatch(
        monkeypatch,
        _active_recovery_v3_manifest(),
    )
    assert events == ["v3", "v1", "replay", "rollback"]


@pytest.mark.parametrize(
    ("tamper", "expected_error"),
    (
        ("task", "m4_v2_global_recovery_v3_output_changed"),
        ("source", "m4_v2_global_recovery_v3_source_changed"),
        ("manifest", "m4_v2_global_recovery_v3_output_changed"),
    ),
)
def test_global_recovery_v3_import_rejects_malformed_successor_before_v2_skip_or_first_write(
    monkeypatch,
    tamper: str,
    expected_error: str,
) -> None:
    payload = _active_recovery_v3_manifest().to_dict(include_digest=False)
    recovery = next(
        item
        for item in payload["tasks"]
        if item["task_key"] == recovery_v3.RECOVERY_TASK_KEY
    )
    if tamper == "task":
        recovery["priority"] += 1
    elif tamper == "source":
        recovery["input_artifact_digests"] = ["0" * 64]
    else:
        payload["facts"]["external_events"].append("tamper:manifest")
    manifest = ControlPlaneManifest.from_dict(payload)
    assert manifest.artifact_digest != _active_recovery_v3_manifest().artifact_digest
    events = _probe_global_recovery_v3_import_dispatch(
        monkeypatch,
        manifest,
        expected_error=expected_error,
    )
    assert events == ["v3", "rollback"]


@pytest.mark.parametrize("stage", ("INPUT", "READY", "RUNNING", "FAILED", "COMPLETED"))
def test_global_recovery_v3_import_preserves_v2_and_input_baseline_dispatch(
    monkeypatch,
    stage: str,
) -> None:
    manifests = {
        "INPUT": _recovery_v2_baseline_manifest(),
        "READY": _active_recovery_v2_manifest(),
        "RUNNING": _recovery_v2_runtime_fixture("RUNNING")[0],
        "FAILED": _recovery_v2_runtime_fixture("FAILED")[0],
        "COMPLETED": _recovery_v2_runtime_fixture("COMPLETED")[0],
    }
    events = _probe_global_recovery_v3_import_dispatch(
        monkeypatch,
        manifests[stage],
    )
    assert events == ["v3", "v2", "v1", "replay", "rollback"]


def test_global_recovery_v3_ready_import_reaches_ready_queue_in_isolated_postgres(
    postgres_repository,
    monkeypatch,
) -> None:
    _, connection_factory, _schema = postgres_repository
    baseline = _terminal_recovery_v2_manifest()
    seed = PostgresResearchOSRepository(connection_factory)  # type: ignore[arg-type]
    for name in (
        "_verify_m4_v2_failed_global_routing_recovery_v3_import",
        "_verify_m4_v2_failed_global_routing_recovery_v2_import",
        "_verify_m4_v2_failed_global_routing_recovery_import",
        "_verify_mainline_completion_records",
        "_verify_no_mainline_completion_regression",
    ):
        monkeypatch.setattr(seed, name, lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        seed,
        "_verify_m4_v2_failed_replay_recovery_import",
        lambda *_args, **_kwargs: True,
    )
    seed.import_manifest(
        control_plane_key="m4-information-theory-mainline",
        payload=baseline.to_dict(include_digest=True),
        source="test-recovery-v3-dispatch-seed",
    )
    predecessor = _RecoveryV3Cursor(baseline).predecessor_events
    with connection_factory() as connection:
        for index, event in enumerate(predecessor):
            connection.execute(
                """INSERT INTO research_os_mainline_execution_events (
                     event_digest, execution_id, control_plane_key, manifest_digest,
                     task_digest, task_key, capability, event_type, sequence,
                     recorded_at, event_json
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '{}'::jsonb)""",
                (
                    event["event_digest"],
                    event["execution_id"],
                    "m4-information-theory-mainline",
                    event["manifest_digest"],
                    event["task_digest"],
                    event["task_key"],
                    "m4_v2_global_routing",
                    event["event_type"],
                    event["sequence"],
                    f"2026-08-14T00:0{index}:00+00:00",
                ),
            )

    repository = PostgresResearchOSRepository(connection_factory)  # type: ignore[arg-type]

    def reject_v2(*_args, **_kwargs):
        raise AssertionError("recovery-v2 verifier reentered for recovery-v3")

    monkeypatch.setattr(
        repository,
        "_verify_m4_v2_failed_global_routing_recovery_v2_import",
        reject_v2,
    )
    monkeypatch.setattr(
        repository,
        "_verify_m4_v2_failed_global_routing_recovery_import",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        repository,
        "_verify_m4_v2_failed_replay_recovery_import",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        repository,
        "_verify_mainline_completion_records",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        repository,
        "_verify_no_mainline_completion_regression",
        lambda *_args, **_kwargs: None,
    )
    ready = _active_recovery_v3_manifest()
    result = repository.import_manifest(
        control_plane_key="m4-information-theory-mainline",
        payload=ready.to_dict(include_digest=True),
        source="test-recovery-v3-dispatch",
    )
    assert result.manifest_digest == ready.artifact_digest
    assert result.snapshot_digest == (
        "ca5636d335b23495b068cf1a0cad9c900bba83a9830e0690b70846ba262eb99b"
    )
    assert result.ready_task_keys == (recovery_v3.RECOVERY_TASK_KEY,)
    assert repository.list_mainline_execution_event_metadata(
        control_plane_key="m4-information-theory-mainline",
        task_keys=(recovery_v3.RECOVERY_TASK_KEY,),
    ) == ()
    with connection_factory() as connection:
        registration_count = connection.execute(
            """SELECT COUNT(*) FROM research_os_mainline_artifacts
               WHERE control_plane_key = %s AND task_key = %s""",
            (
                "m4-information-theory-mainline",
                recovery_v3.RECOVERY_TASK_KEY,
            ),
        ).fetchone()[0]
    assert registration_count == 0

    before_tamper = _counts(connection_factory)
    tampered_payload = ready.to_dict(include_digest=False)
    tampered_payload["facts"]["external_events"].append("tamper:manifest")
    with pytest.raises(
        ResearchOSValidationError,
        match="^m4_v2_global_recovery_v3_output_changed$",
    ):
        repository.import_manifest(
            control_plane_key="m4-information-theory-mainline",
            payload=tampered_payload,
            source="test-recovery-v3-dispatch-tamper",
        )
    assert repository.load_manifest(
        control_plane_key="m4-information-theory-mainline"
    ).artifact_digest == ready.artifact_digest
    assert _counts(connection_factory) == before_tamper


def _completed_global_recovery_v3_manifest() -> ControlPlaneManifest:
    payload, _ = recovery_v3.build_manifest(
        _terminal_recovery_v2_manifest().to_dict(include_digest=True),
        global_source_contract_digest=(
            "11cb628f050f05465676fe083a6f9c183cbf855edfec8e194e98ad0450cdfd64"
        ),
    )
    ready = ControlPlaneManifest.from_dict(payload)
    task = next(
        item for item in ready.tasks if item.task_key == recovery_v3.RECOVERY_TASK_KEY
    )
    metric = json.loads(task.metric_contract)
    completed = _transition_recovery_v3_manifest(
        ready,
        status="completed",
        classification="COMPLETE",
        facts=(
            (
                f"mainline-execution:{task.task_key}:{task.artifact_digest}:"
                f"{replay_compatibility.OLD_EXECUTION_ID}:completed"
            ),
            metric["route_facts"][replay_compatibility.OLD_ROUTE],
            metric["completion_fact"],
        ),
    )
    assert completed.artifact_digest == replay_compatibility.INPUT_MANIFEST_DIGEST
    return completed


def _old_recovery_v3_rows() -> tuple[list[dict], list[dict]]:
    started = MainlineExecutionEvent(
        execution_id=replay_compatibility.OLD_EXECUTION_ID,
        control_plane_key="m4-information-theory-mainline",
        manifest_digest=replay_compatibility.OLD_EVENT_MANIFEST_DIGEST,
        task_key=replay_compatibility.OLD_TASK_KEY,
        task_digest=replay_compatibility.OLD_TASK_DIGEST,
        capability="m4_v2_global_routing",
        event_type="started",
        sequence=0,
        recorded_at="2026-08-19T01:31:56.544096+00:00",
        payload=(
            (
                "input_artifact_digests",
                ["11cb628f050f05465676fe083a6f9c183cbf855edfec8e194e98ad0450cdfd64"],
            ),
            ("git_commit", replay_compatibility.OLD_GIT_COMMIT),
        ),
    )
    completed = MainlineExecutionEvent(
        execution_id=replay_compatibility.OLD_EXECUTION_ID,
        control_plane_key="m4-information-theory-mainline",
        manifest_digest=replay_compatibility.OLD_EVENT_MANIFEST_DIGEST,
        task_key=replay_compatibility.OLD_TASK_KEY,
        task_digest=replay_compatibility.OLD_TASK_DIGEST,
        capability="m4_v2_global_routing",
        event_type="completed",
        sequence=1,
        recorded_at="2026-08-19T01:32:10.869481+00:00",
        payload=(
            ("actual_fold_count", 0),
            ("additional_completed_task_keys", []),
            (
                "completion_facts",
                [
                    "m4-v2-routing:DEEPER_VALIDATION_REQUIRED",
                    "m4-v2-global-routing-recovery-v3:COMPLETE",
                ],
            ),
            ("decision_replay_coverage", "COMPLETE"),
            ("downstream_consumer", "M4_DEEPER_VALIDATION"),
            (
                "execution_artifact_digest",
                replay_compatibility.OLD_EXECUTION_ARTIFACT_DIGEST,
            ),
            ("execution_artifact_path", replay_compatibility.OLD_EXECUTION_PATH),
            ("git_commit", replay_compatibility.OLD_GIT_COMMIT),
            ("historical_database_reads", 0),
            (
                "publication_batch_digest",
                "4b4b3cf8f1d39f0b3d06ad4b7a754fdd1a43a52f9f462c86176de99977b8305b",
            ),
            ("registered_artifact_count", 2),
            ("replay_status", "REGISTERED_REPLAY_PENDING"),
            ("route", replay_compatibility.OLD_ROUTE),
            (
                "route_decision_artifact_digest",
                replay_compatibility.OLD_ROUTE_ARTIFACT_DIGEST,
            ),
            ("scientific_computation", 0),
            (
                "source_contract_digest",
                "11cb628f050f05465676fe083a6f9c183cbf855edfec8e194e98ad0450cdfd64",
            ),
            (
                "source_set_digest",
                "cb48f271e3a082d143d435187b5ee8587f5684c9333259d79340d2c297c55631",
            ),
            ("workload_rerun", False),
        ),
    )
    assert started.artifact_digest == replay_compatibility.OLD_STARTED_EVENT_DIGEST
    assert completed.artifact_digest == replay_compatibility.OLD_COMPLETED_EVENT_DIGEST
    route = MainlineArtifactRegistration(
        execution_id=replay_compatibility.OLD_EXECUTION_ID,
        control_plane_key="m4-information-theory-mainline",
        task_key=replay_compatibility.OLD_TASK_KEY,
        task_digest=replay_compatibility.OLD_TASK_DIGEST,
        artifact_digest=replay_compatibility.OLD_ROUTE_ARTIFACT_DIGEST,
        artifact_type="m4_measurement_routing_decision",
        schema_version="dehps-m4-measurement-routing-decision.v1",
        artifact_path=replay_compatibility.OLD_ROUTE_PATH,
        git_commit=replay_compatibility.OLD_GIT_COMMIT,
    )
    execution = MainlineArtifactRegistration(
        execution_id=replay_compatibility.OLD_EXECUTION_ID,
        control_plane_key="m4-information-theory-mainline",
        task_key=replay_compatibility.OLD_TASK_KEY,
        task_digest=replay_compatibility.OLD_TASK_DIGEST,
        artifact_digest=replay_compatibility.OLD_EXECUTION_ARTIFACT_DIGEST,
        artifact_type="research_os_mainline_execution",
        schema_version="dehps-research-os-mainline-execution.v1",
        artifact_path=replay_compatibility.OLD_EXECUTION_PATH,
        parent_digests=(
            "11cb628f050f05465676fe083a6f9c183cbf855edfec8e194e98ad0450cdfd64",
            replay_compatibility.OLD_ROUTE_ARTIFACT_DIGEST,
        ),
        git_commit=replay_compatibility.OLD_GIT_COMMIT,
    )
    return [_event_row(started), _event_row(completed)], [
        _registration_row(route),
        _registration_row(execution),
    ]


class _ReplayCompatibilityCursor:
    def __init__(
        self,
        baseline: ControlPlaneManifest,
        *,
        current: ControlPlaneManifest,
        runtime_events: list[dict] | None = None,
        old_events: list[dict] | None = None,
        old_registrations: list[dict] | None = None,
        successor_registrations: list[dict] | None = None,
        governance_mismatch: str | None = None,
    ) -> None:
        self.baseline = baseline
        self.current = current
        default_events, default_registrations = _old_recovery_v3_rows()
        self.runtime_events = runtime_events or []
        self.old_events = default_events if old_events is None else old_events
        self.old_registrations = (
            default_registrations if old_registrations is None else old_registrations
        )
        self.successor_registrations = successor_registrations or []
        self.governance_mismatch = governance_mismatch
        self.inserted_registration_digests: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, parameters=()):
        query = " ".join(str(statement).split())
        if query.startswith("INSERT INTO research_os_mainline_artifacts"):
            self.inserted_registration_digests.append(str(parameters[0]))
            return _Rows(one={"registration_digest": parameters[0]})
        assert query.startswith("SELECT")
        if "FROM research_os_control_planes" in query:
            return _Rows(one={"current_manifest_digest": self.current.artifact_digest})
        if "FROM research_os_manifests" in query:
            stored = (
                self.baseline
                if parameters == (replay_compatibility.INPUT_MANIFEST_DIGEST,)
                else self.current
            )
            return _Rows(one={"manifest_json": stored.to_dict(include_digest=True)})
        if "FROM research_os_mainline_execution_events" in query:
            return _Rows(
                many=(
                    self.old_events
                    if parameters[1] == replay_compatibility.OLD_TASK_KEY
                    else self.runtime_events
                )
            )
        if "FROM research_os_mainline_artifacts" in query:
            return _Rows(
                many=(
                    self.old_registrations
                    if parameters[1] == replay_compatibility.OLD_TASK_KEY
                    else self.successor_registrations
                )
            )
        if "FROM agent_requests" in query:
            requests, _, _ = _replay_compatibility_governance_rows()
            if self.governance_mismatch == "authorization":
                requests[0]["payload_sha256"] = "0" * 64
            return _Rows(many=requests)
        if "FROM agent_request_executions" in query:
            _, executions, _ = _replay_compatibility_governance_rows()
            return _Rows(many=executions)
        if "FROM agent_request_decisions" in query:
            _, _, decisions = _replay_compatibility_governance_rows()
            return _Rows(many=decisions)
        raise AssertionError(query)


def _replay_compatibility_governance_rows() -> tuple[
    list[dict], list[dict], list[dict]
]:
    requests = [
        {
            "id": 621,
            "request_key": "research-m4-v2-global-routing-v3-exact-successor-registration-v1",
            "request_type": "research_scheduler_request",
            "requested_by_role": "research",
            "requested_by": "research:exact-successor-registration-v1",
            "parent_request_id": None,
            "status": "completed",
            "risk_level": "low",
            "requires_review": True,
            "payload_sha256": (
                "122ee0aa7aebe5fc3e99cecd9efe5fcd4b87a91571cceb7f6d67696227c65399"
            ),
        },
        {
            "id": 622,
            "request_key": "engineering-m4-v2-global-routing-v3-exact-successor-registration-v1",
            "request_type": "engineering_implementation",
            "requested_by_role": "engineering",
            "requested_by": "engineering:exact-successor-registration-v1",
            "parent_request_id": 621,
            "status": "completed",
            "risk_level": "medium",
            "requires_review": True,
            "payload_sha256": (
                "4e06a9af9253b3b77bf2838bd0d33451ec316b017f3ad799f0e76c952020f631"
            ),
        },
    ]
    executions = [
        {
            "id": 507,
            "request_id": 621,
            "executor_role": "research",
            "executor_id": "research:exact-successor-registration-v1",
            "execution_type": "schedule_research",
            "status": "completed",
            "environment": "isolated",
            "run_id": None,
            "artifact_paths": [],
        },
        {
            "id": 508,
            "request_id": 622,
            "executor_role": "engineering",
            "executor_id": "engineering:exact-successor-registration-v1",
            "execution_type": "modify_code",
            "status": "completed",
            "environment": "development",
            "run_id": "m4-v2-global-routing-v3-exact-successor-registration-v1",
            "artifact_paths": [],
        },
    ]
    decisions = [
        {
            "id": 2609,
            "request_id": 621,
            "previous_status": "draft",
            "new_status": "submitted",
            "decision_code": "request_submitted",
            "summary": "request submitted for review",
            "reason": {},
            "decided_by_role": "research",
            "decided_by": "research:exact-successor-registration-v1",
        },
        {
            "id": 2610,
            "request_id": 621,
            "previous_status": "submitted",
            "new_status": "under_review",
            "decision_code": "review_started",
            "summary": "request review started",
            "reason": {},
            "decided_by_role": "reviewer",
            "decided_by": "reviewer:exact-successor-registration-v1",
        },
        {
            "id": 2611,
            "request_id": 621,
            "previous_status": "under_review",
            "new_status": "approved",
            "decision_code": "request_approved",
            "summary": "request approved for execution",
            "reason": {"outcome": "APPROVE_EXACT_SUCCESSOR_REGISTRATION"},
            "decided_by_role": "reviewer",
            "decided_by": "reviewer:exact-successor-registration-v1",
        },
        {
            "id": 2612,
            "request_id": 621,
            "previous_status": "approved",
            "new_status": "executing",
            "decision_code": "execution_started",
            "summary": "approved request execution started",
            "reason": {
                "run_id": None,
                "environment": "isolated",
                "execution_type": "schedule_research",
            },
            "decided_by_role": "research",
            "decided_by": "research:exact-successor-registration-v1",
        },
        {
            "id": 2613,
            "request_id": 621,
            "previous_status": "executing",
            "new_status": "completed",
            "decision_code": "execution_completed",
            "summary": "request execution completed",
            "reason": {"execution_id": 507, "has_error": False},
            "decided_by_role": "research",
            "decided_by": "research:exact-successor-registration-v1",
        },
        {
            "id": 2614,
            "request_id": 622,
            "previous_status": "draft",
            "new_status": "submitted",
            "decision_code": "request_submitted",
            "summary": "request submitted for review",
            "reason": {},
            "decided_by_role": "engineering",
            "decided_by": "engineering:exact-successor-registration-v1",
        },
        {
            "id": 2615,
            "request_id": 622,
            "previous_status": "submitted",
            "new_status": "under_review",
            "decision_code": "review_started",
            "summary": "request review started",
            "reason": {},
            "decided_by_role": "reviewer",
            "decided_by": "reviewer:engineering622-successor-registration",
        },
        {
            "id": 2616,
            "request_id": 622,
            "previous_status": "under_review",
            "new_status": "approved",
            "decision_code": "request_approved",
            "summary": "request approved for execution",
            "reason": {"outcome": "APPROVE_EXACT_SUCCESSOR_REGISTRATION"},
            "decided_by_role": "reviewer",
            "decided_by": "reviewer:engineering622-successor-registration",
        },
        {
            "id": 2617,
            "request_id": 622,
            "previous_status": "approved",
            "new_status": "executing",
            "decision_code": "execution_started",
            "summary": "approved request execution started",
            "reason": {
                "run_id": "m4-v2-global-routing-v3-exact-successor-registration-v1",
                "environment": "development",
                "execution_type": "modify_code",
            },
            "decided_by_role": "engineering",
            "decided_by": "engineering:exact-successor-registration-v1",
        },
        {
            "id": 2618,
            "request_id": 622,
            "previous_status": "executing",
            "new_status": "completed",
            "decision_code": "execution_completed",
            "summary": "request execution completed",
            "reason": {"execution_id": 508, "has_error": False},
            "decided_by_role": "engineering",
            "decided_by": "engineering:exact-successor-registration-v1",
        },
    ]
    return requests, executions, decisions


def _active_replay_compatibility_manifest() -> ControlPlaneManifest:
    payload, _ = replay_compatibility.build_manifest(
        _completed_global_recovery_v3_manifest().to_dict(include_digest=True),
        source_contract_digest=(
            "348954707e00d611ecbd39fb3da99486ea3861754349100c3d0303edbdae5f04"
        ),
    )
    return ControlPlaneManifest.from_dict(payload)


def _exact_replay_compatibility_registration() -> MainlineArtifactRegistration:
    registration = MainlineArtifactRegistration(
        execution_id=(
            "d9aeb506915b15ed7aec7cda574dfeb7685d94f88844c938d1934d8350d1325c"
        ),
        control_plane_key="m4-information-theory-mainline",
        task_key=replay_compatibility.SUCCESSOR_TASK_KEY,
        task_digest=(
            "7e36a2d443744bedb2e6dd4223aad736045b730e7b9e839170454339190b0e88"
        ),
        artifact_digest=replay_compatibility.OLD_ROUTE_ARTIFACT_DIGEST,
        artifact_type="m4_measurement_routing_decision",
        schema_version="dehps-m4-measurement-routing-decision.v1",
        artifact_path=replay_compatibility.OLD_ROUTE_PATH,
        parent_digests=(),
        git_commit="bb39ee504ba22a497393e1f5e65ce3a25761650b",
    )
    assert registration.registration_digest == (
        "b9b0a3085519d69cccbedf4ff151d0e5761641510522769368965671a6ca8d02"
    )
    return registration


def _patch_replay_compatibility_source(monkeypatch, tmp_path: Path) -> None:
    source_path = "configs/research-os/m4-v2-global-routing-source-v1.json"
    route_fixture = (ROOT / source_path).read_bytes()
    copied_source = tmp_path / source_path
    copied_source.parent.mkdir(parents=True, exist_ok=True)
    copied_source.write_bytes(route_fixture)
    route_path = tmp_path / replay_compatibility.OLD_ROUTE_PATH
    route_path.parent.mkdir(parents=True, exist_ok=True)
    route_path.write_bytes(route_fixture)
    monkeypatch.setattr(dehps_config, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(
        replay_compatibility, "OLD_ROUTE_RAW_SHA256", hashlib.sha256(route_fixture).hexdigest()
    )
    monkeypatch.setattr(
        replay_compatibility, "OLD_ROUTE_RAW_LENGTH", len(route_fixture)
    )
    monkeypatch.setattr(
        replay_compatibility,
        "SOURCE_PATH",
        source_path,
    )
    monkeypatch.setattr(
        replay_compatibility,
        "validate_source_contract",
        lambda *_args, **_kwargs: (
            "348954707e00d611ecbd39fb3da99486ea3861754349100c3d0303edbdae5f04"
        ),
    )
    monkeypatch.setattr(
        repository_module,
        "_load_m4_v2_global_routing_replay_compatibility_v1_builder",
        lambda: replay_compatibility,
    )
    monkeypatch.setattr(
        repository_module,
        "_load_m4_v2_global_routing_recovery_v3_builder",
        lambda: recovery_v3,
    )


def test_replay_compatibility_builder_is_exactly_additive_and_unique_ready() -> None:
    baseline = _completed_global_recovery_v3_manifest()
    ready = _active_replay_compatibility_manifest()
    snapshot = repository_module.ResearchOSControlPlane().resolve(ready)
    assert tuple(ready.goals) == tuple(baseline.goals)
    assert tuple(ready.tasks[:-1]) == tuple(baseline.tasks)
    assert tuple(ready.goal_states) == tuple(baseline.goal_states)
    assert tuple(ready.task_states[:-1]) == tuple(baseline.task_states)
    assert [item.task_key for item in snapshot.ready_queue] == [
        replay_compatibility.SUCCESSOR_TASK_KEY
    ]
    assert ready.facts.artifacts - baseline.facts.artifacts == {
        "348954707e00d611ecbd39fb3da99486ea3861754349100c3d0303edbdae5f04"
    }
    assert ready.facts.external_events - baseline.facts.external_events == {
        replay_compatibility.AUTHORIZATION_EVENT
    }
    assert ready.facts.authorities == baseline.facts.authorities


def test_replay_compatibility_import_preserves_completed_v3_path(
    monkeypatch, tmp_path: Path
) -> None:
    baseline = _completed_global_recovery_v3_manifest()
    ready = _active_replay_compatibility_manifest()
    _patch_replay_compatibility_source(monkeypatch, tmp_path)
    PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v3_import(
        _ReplayCompatibilityCursor(baseline, current=baseline),
        control_plane_key="m4-information-theory-mainline",
        manifest=ready,
    )


def test_exact_completed_v3_path_does_not_load_compatibility_builder(
    monkeypatch,
) -> None:
    completed, running, events, registrations = _recovery_v3_runtime_fixture(
        "COMPLETED"
    )

    def reject_loader():
        raise AssertionError("compatibility builder loaded for exact completed-v3 input")

    monkeypatch.setattr(
        repository_module,
        "_load_m4_v2_global_routing_replay_compatibility_v1_builder",
        reject_loader,
    )
    PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v3_import(
        _RecoveryV3Cursor(
            completed,
            current=running,
            runtime_events=events,
            registrations=registrations,
        ),
        control_plane_key="m4-information-theory-mainline",
        manifest=completed,
    )


@pytest.mark.parametrize(
    "tamper",
    (
        "existing_task",
        "existing_state",
        "existing_fact",
        "extra_task",
        "old_event",
        "old_registration",
    ),
)
def test_replay_compatibility_rejects_unapproved_addition_or_identity_drift(
    monkeypatch,
    tmp_path: Path,
    tamper: str,
) -> None:
    baseline = _completed_global_recovery_v3_manifest()
    payload = _active_replay_compatibility_manifest().to_dict(include_digest=False)
    old_events, old_registrations = _old_recovery_v3_rows()
    if tamper == "existing_task":
        payload["tasks"][0]["priority"] += 1
    elif tamper == "existing_state":
        payload["tasks"][0]["status"] = "running"
    elif tamper == "existing_fact":
        payload["facts"]["artifacts"].append("unapproved:fact")
    elif tamper == "extra_task":
        extra = copy.deepcopy(payload["tasks"][-1])
        extra["task_key"] += "-extra"
        payload["tasks"].append(extra)
    elif tamper == "old_event":
        old_events[0] = {**old_events[0], "event_digest": "0" * 64}
    else:
        old_registrations[0] = {
            **old_registrations[0],
            "artifact_digest": "0" * 64,
        }
    incoming = ControlPlaneManifest.from_dict(payload)
    _patch_replay_compatibility_source(monkeypatch, tmp_path)
    with pytest.raises(ResearchOSValidationError):
        PostgresResearchOSRepository._verify_m4_v2_global_routing_replay_compatibility_v1_import(
            _ReplayCompatibilityCursor(
                baseline,
                current=baseline,
                old_events=old_events,
                old_registrations=old_registrations,
            ),
            control_plane_key="m4-information-theory-mainline",
            manifest=incoming,
            builder=replay_compatibility,
        )


def test_exact_successor_registration_passes_only_after_full_prewrite_validation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    baseline, running, _, started, completed_event, registration = (
        _completed_replay_compatibility_fixture()
    )
    cursor = _ReplayCompatibilityCursor(
        baseline,
        current=running,
        runtime_events=[_event_row(started), _event_row(completed_event)],
    )

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self, **_kwargs):
            return cursor

    @contextmanager
    def connection_factory():
        with Connection() as connection:
            yield connection

    _patch_replay_compatibility_source(monkeypatch, tmp_path)
    repository = PostgresResearchOSRepository(connection_factory)  # type: ignore[arg-type]
    assert repository.register_mainline_artifact(registration=registration) is True
    assert cursor.inserted_registration_digests == [registration.registration_digest]


@pytest.mark.parametrize(
    "tamper",
    (
        "task_digest",
        "route_artifact_digest",
        "parent_lineage",
        "source_contract_digest",
        "authorization_identity",
    ),
)
def test_exact_successor_registration_rejects_every_identity_drift(
    monkeypatch,
    tmp_path: Path,
    tamper: str,
) -> None:
    baseline, running, _, started, completed_event, registration = (
        _completed_replay_compatibility_fixture()
    )
    _patch_replay_compatibility_source(monkeypatch, tmp_path)
    if tamper == "task_digest":
        registration = MainlineArtifactRegistration(
            **{**registration.__dict__, "task_digest": "0" * 64}
        )
    elif tamper == "route_artifact_digest":
        registration = MainlineArtifactRegistration(
            **{**registration.__dict__, "artifact_digest": "0" * 64}
        )
    elif tamper == "parent_lineage":
        registration = MainlineArtifactRegistration(
            **{**registration.__dict__, "parent_digests": ("0" * 64,)}
        )
    elif tamper == "source_contract_digest":
        monkeypatch.setattr(
            replay_compatibility,
            "validate_source_contract",
            lambda *_args, **_kwargs: "f" * 64,
        )
    cursor = _ReplayCompatibilityCursor(
        baseline,
        current=running,
        runtime_events=[_event_row(started), _event_row(completed_event)],
        governance_mismatch=(
            "authorization" if tamper == "authorization_identity" else None
        ),
    )
    with pytest.raises(ResearchOSValidationError):
        PostgresResearchOSRepository._verify_m4_v2_global_routing_replay_compatibility_v1_registration(
            cursor,
            registration=registration,
        )
    assert cursor.inserted_registration_digests == []


def test_replay_compatibility_rejects_old_registration_from_other_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    baseline = _completed_global_recovery_v3_manifest()
    ready = _active_replay_compatibility_manifest()
    _, old_registrations = _old_recovery_v3_rows()
    extra = MainlineArtifactRegistration(
        execution_id="9" * 64,
        control_plane_key="m4-information-theory-mainline",
        task_key=replay_compatibility.OLD_TASK_KEY,
        task_digest=replay_compatibility.OLD_TASK_DIGEST,
        artifact_digest=replay_compatibility.OLD_ROUTE_ARTIFACT_DIGEST,
        artifact_type="m4_measurement_routing_decision",
        schema_version="dehps-m4-measurement-routing-decision.v1",
        artifact_path=replay_compatibility.OLD_ROUTE_PATH,
        git_commit=replay_compatibility.OLD_GIT_COMMIT,
    )
    old_registrations.append(_registration_row(extra))
    _patch_replay_compatibility_source(monkeypatch, tmp_path)
    with pytest.raises(
        ResearchOSValidationError,
        match="m4_v2_global_replay_compatibility_v1_old_registrations_changed",
    ):
        PostgresResearchOSRepository._verify_m4_v2_global_routing_replay_compatibility_v1_import(
            _ReplayCompatibilityCursor(
                baseline,
                current=baseline,
                old_registrations=old_registrations,
            ),
            control_plane_key="m4-information-theory-mainline",
            manifest=ready,
            builder=replay_compatibility,
        )


def _completed_replay_compatibility_fixture() -> tuple[
    ControlPlaneManifest,
    ControlPlaneManifest,
    ControlPlaneManifest,
    MainlineExecutionEvent,
    MainlineExecutionEvent,
    MainlineArtifactRegistration,
]:
    baseline = _completed_global_recovery_v3_manifest()
    ready = _active_replay_compatibility_manifest()
    running = ControlPlaneManifest.from_dict(
        replay_compatibility.transition_manifest(
            ready.to_dict(include_digest=True),
            status="running",
            classification="INTEGRATED",
        )
    )
    task = next(
        item for item in ready.tasks if item.task_key == replay_compatibility.SUCCESSOR_TASK_KEY
    )
    registration = _exact_replay_compatibility_registration()
    git_commit = registration.git_commit
    execution_id = registration.execution_id
    assert task.artifact_digest == registration.task_digest
    started = MainlineExecutionEvent(
        execution_id=execution_id,
        control_plane_key="m4-information-theory-mainline",
        manifest_digest=running.artifact_digest,
        task_key=task.task_key,
        task_digest=task.artifact_digest,
        capability=str(task.requested_capability),
        event_type="started",
        sequence=0,
        recorded_at="2026-08-19T06:00:00+00:00",
        payload=(
            ("input_artifact_digests", list(task.input_artifact_digests)),
            ("git_commit", git_commit),
        ),
    )
    terminal_payload = (
        ("git_commit", git_commit),
        ("registered_replay_status", "REGISTERED_REPLAY_VERIFIED"),
        ("replay_task_key", replay_compatibility.OLD_TASK_KEY),
        ("replay_execution_id", replay_compatibility.OLD_EXECUTION_ID),
        ("route_artifact_digest", replay_compatibility.OLD_ROUTE_ARTIFACT_DIGEST),
        (
            "route_registration_digest",
            replay_compatibility.OLD_ROUTE_REGISTRATION_DIGEST,
        ),
        ("global_route", replay_compatibility.OLD_ROUTE),
        ("durable_state_changed", False),
        ("workload_rerun", False),
        ("branch_workloads_rerun", False),
        ("global_router_workload_rerun", False),
        ("predictive_p3_folds", 0),
        ("p4_started", False),
        ("promotion_triggered", False),
    )
    completed_event = MainlineExecutionEvent(
        execution_id=execution_id,
        control_plane_key="m4-information-theory-mainline",
        manifest_digest=running.artifact_digest,
        task_key=task.task_key,
        task_digest=task.artifact_digest,
        capability=str(task.requested_capability),
        event_type="completed",
        sequence=1,
        recorded_at="2026-08-19T06:01:00+00:00",
        payload=terminal_payload,
    )
    completed = ControlPlaneManifest.from_dict(
        replay_compatibility.transition_manifest(
            ready.to_dict(include_digest=True),
            status="completed",
            classification="COMPLETE",
            execution_id=execution_id,
        )
    )
    return baseline, running, completed, started, completed_event, registration


def test_replay_compatibility_completed_stage_accepts_registered_replay_only(
    monkeypatch,
    tmp_path: Path,
) -> None:
    baseline, running, completed, started, completed_event, registration = (
        _completed_replay_compatibility_fixture()
    )
    _patch_replay_compatibility_source(monkeypatch, tmp_path)
    PostgresResearchOSRepository._verify_m4_v2_global_routing_replay_compatibility_v1_import(
        _ReplayCompatibilityCursor(
            baseline,
            current=running,
            runtime_events=[_event_row(started), _event_row(completed_event)],
            successor_registrations=[_registration_row(registration)],
        ),
        control_plane_key="m4-information-theory-mainline",
        manifest=completed,
        builder=replay_compatibility,
    )
    bad_event = MainlineExecutionEvent(
        **{
            **completed_event.__dict__,
            "payload": tuple(
                (key, True if key == "workload_rerun" else value)
                for key, value in completed_event.payload
            ),
        }
    )
    with pytest.raises(
        ResearchOSValidationError,
        match="m4_v2_global_replay_compatibility_v1_output_changed",
    ):
        PostgresResearchOSRepository._verify_m4_v2_global_routing_replay_compatibility_v1_import(
            _ReplayCompatibilityCursor(
                baseline,
                current=running,
                runtime_events=[_event_row(started), _event_row(bad_event)],
                successor_registrations=[_registration_row(registration)],
            ),
            control_plane_key="m4-information-theory-mainline",
            manifest=completed,
            builder=replay_compatibility,
        )


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
