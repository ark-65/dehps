from __future__ import annotations

import ast
import base64
import copy
import json
import lzma
import os
import subprocess
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace

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

ROOT = Path(__file__).resolve().parents[3]


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
    source_path = ROOT / recovery_v2.GLOBAL_SOURCE_PATH
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source_digest = recovery_v2.validate_global_source_contract(
        source, root_dir=ROOT
    )
    payload, _ = recovery_v2.build_manifest(
        baseline.to_dict(include_digest=True),
        global_source_contract_digest=source_digest,
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
