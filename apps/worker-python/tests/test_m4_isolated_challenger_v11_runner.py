from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import json
import os
import uuid
from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_contract as contract,
)
from dehps.research_os.models import (
    CompletionClassification,
    ControlPlaneManifest,
    MainlineArtifactRegistration,
    MainlineExecutionEvent,
    TaskStatus,
)
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb


@pytest.fixture(scope="module")
def rebind_post_snapshot():
    """One production READ ONLY snapshot; every restore targets a temporary DB."""
    dsn = os.getenv("DEHPS_V11_READ_ONLY_SNAPSHOT_URL")
    test_dsn = os.getenv("DEHPS_TEST_DATABASE_URL")
    if os.getenv("DEHPS_TEST_POSTGRES") != "1" or not dsn or not test_dsn:
        pytest.skip("requires explicit read-only snapshot and isolated test URLs")
    assert dsn != test_dsn
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    cp = contract.CONTROL_PLANE_KEY
    tables = {}
    with psycopg.connect(dsn) as connection:
        connection.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        assert connection.execute("SHOW transaction_read_only").fetchone()[0] == "on"

        def capture(table, predicate, params):
            rows = connection.execute(
                sql.SQL("SELECT to_jsonb(t) FROM {} t WHERE ").format(
                    sql.Identifier(table)
                )
                + sql.SQL(predicate),
                params,
            ).fetchall()
            tables[table] = [row[0] for row in rows]
            return tables[table]

        controls = capture("research_os_control_planes", "control_plane_key=%s", (cp,))
        assert (
            controls[0]["current_manifest_digest"]
            == runner.DAILY_RECOVERY_POST_COMMIT_MANIFEST_DIGEST
        )
        events = capture(
            "research_os_mainline_execution_events", "control_plane_key=%s", (cp,)
        )
        manifest_ids = sorted(
            {
                controls[0]["current_manifest_digest"],
                *(r["manifest_digest"] for r in events),
            }
        )
        capture("research_os_manifests", "manifest_digest=ANY(%s)", (manifest_ids,))
        mg = capture(
            "research_os_manifest_goals", "manifest_digest=ANY(%s)", (manifest_ids,)
        )
        mt = capture(
            "research_os_manifest_tasks", "manifest_digest=ANY(%s)", (manifest_ids,)
        )
        goal_ids = sorted({r["goal_digest"] for r in mg})
        assert mt
        capture("research_os_goal_definitions", "goal_digest=ANY(%s)", (goal_ids,))
        capture("research_os_task_definitions", "goal_digest=ANY(%s)", (goal_ids,))
        for table in (
            "research_os_goal_states",
            "research_os_task_states",
            "research_os_dependency_facts",
        ):
            capture(table, "control_plane_key=%s", (cp,))
        registered = capture(
            "research_os_mainline_artifacts", "control_plane_key=%s", (cp,)
        )
        inputs = connection.execute(
            "SELECT to_jsonb(t) FROM m4_isolated_v11.registered_inputs t"
        ).fetchall()
        tables["m4_isolated_v11.registered_inputs"] = [r[0] for r in inputs]
        files = {}
        for row in registered:
            relative = row["artifact_path"]
            path = ROOT / relative
            assert (
                path.is_file()
                and not path.is_symlink()
                and path.resolve().is_relative_to(ROOT)
            )
            files[relative] = path.read_bytes()
    daily = [r for r in events if r["task_key"] == contract.DAILY_RECOVERY_TASK_KEY]
    assert sorted(r["sequence"] for r in daily) == [0, 1, 2]
    assert (
        len(
            [r for r in registered if r["task_key"] == contract.DAILY_RECOVERY_TASK_KEY]
        )
        == 2
    )
    return tables, files


@pytest.fixture
def real_rebind_repository(rebind_post_snapshot, tmp_path, monkeypatch):
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    tables, files = rebind_post_snapshot
    admin_dsn = os.environ["DEHPS_TEST_DATABASE_URL"]
    db_name = f"v11_rebind_{uuid.uuid4().hex}"
    test_dsn = make_conninfo(admin_dsn, dbname=db_name)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
    try:
        with psycopg.connect(test_dsn) as connection:
            connection.execute(
                (ROOT / "infra/postgres/init/002_research_os.sql").read_text()
            )
            for name in (
                "003_m4_isolated_24h_challenger_v11.sql",
                "004_m4_isolated_v11_runtime_migration_attestation_input.sql",
            ):
                connection.execute(
                    (ROOT / "infra/postgres/migrations" / name).read_text()
                )
            order = (
                "research_os_goal_definitions",
                "research_os_task_definitions",
                "research_os_manifests",
                "research_os_manifest_goals",
                "research_os_manifest_tasks",
                "research_os_control_planes",
                "research_os_goal_states",
                "research_os_task_states",
                "research_os_dependency_facts",
                "research_os_mainline_execution_events",
                "research_os_mainline_artifacts",
                "m4_isolated_v11.registered_inputs",
            )
            for name in order:
                qualified = sql.Identifier(*name.split("."))
                with connection.cursor() as cursor:
                    cursor.executemany(
                        sql.SQL(
                            "INSERT INTO {} SELECT * FROM jsonb_populate_record(NULL::{}, %s)"
                        ).format(qualified, qualified),
                        [(Jsonb(row),) for row in tables[name]],
                    )
        for relative, content in files.items():
            target = tmp_path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        source = json.loads((ROOT / contract.SOURCE_CONTRACT_PATH).read_bytes())
        for entry in source["source_entries"]:
            target = tmp_path / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / entry["path"]).read_bytes())
        target = tmp_path / contract.SOURCE_CONTRACT_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / contract.SOURCE_CONTRACT_PATH).read_bytes())
        monkeypatch.setattr(runner, "ROOT_DIR", tmp_path)
        monkeypatch.setattr(runner.mainline, "ROOT_DIR", tmp_path)
        origin = ControlPlaneManifest.from_dict(
            next(
                row["manifest_json"]
                for row in tables["research_os_manifests"]
                if row["manifest_digest"]
                == runner.DAILY_RECOVERY_POST_COMMIT_MANIFEST_DIGEST
            )
        )
        daily = next(
            t for t in origin.tasks if t.task_key == contract.DAILY_RECOVERY_TASK_KEY
        )
        repo = runner.IsolatedChallengerRepository(
            context=runner._task_context(daily), source_digest=source["artifact_digest"]
        )
        repo.connection_factory = lambda: psycopg.connect(test_dsn)
        assert (
            repo.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY) == origin
        )
        runner.mainline.register_input_artifact(
            repository=repo,
            payload=source,
            git_commit="ece499208227de1ac4dff28ddfc6d45ada243620",
            source_path=contract.SOURCE_CONTRACT_PATH,
            content_bytes=target.read_bytes(),
        )
        yield runner, repo, tmp_path, test_dsn
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(db_name))
            )


def _rebind_persisted_digest(repo, root):
    """Include all columns (including timestamps) and every artifact byte."""
    tables = {}
    with repo.connection_factory() as connection:
        names = connection.execute(
            "SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN ('public','m4_isolated_v11') ORDER BY 1,2"
        ).fetchall()
        for schema, name in names:
            rows = connection.execute(
                sql.SQL("SELECT to_jsonb(t) FROM {} t").format(
                    sql.Identifier(schema, name)
                )
            ).fetchall()
            tables[f"{schema}.{name}"] = sorted(
                contract.canonical_json(row[0]) for row in rows
            )
    tree = [
        (str(p.relative_to(root)), hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(root.rglob("*"))
        if p.is_file()
    ]
    return hashlib.sha256(
        contract.canonical_json({"tables": tables, "tree": tree}).encode("ascii")
    ).hexdigest()


def _commit_rebind_downstream_fixture(runner, repo, root, task_key):
    """Persist a deterministic completed downstream shape, with real records.

    This fixture producer runs no mail/science capability. The target under
    test uses the real loader, import, registry and completion provenance.
    """
    module = runner.mainline.supervisor_module
    current = repo.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    task = next(t for t in current.tasks if t.task_key == task_key)
    git_commit = "ece499208227de1ac4dff28ddfc6d45ada243620"
    execution_id = module.stable_hash(
        {
            "schema": module.MAINLINE_EXECUTION_SCHEMA,
            "control_plane_key": contract.CONTROL_PLANE_KEY,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "input_artifact_digests": task.input_artifact_digests,
            "git_commit": git_commit,
        }
    )
    relative = f"runtime/isolated-24h-challenger-v11/artifacts/{task_key}/{execution_id}/execution.json"
    payload = {
        "schema_version": module.MAINLINE_EXECUTION_SCHEMA,
        "artifact_type": "research_os_mainline_execution",
        "control_plane_key": contract.CONTROL_PLANE_KEY,
        "task_key": task_key,
        "task_digest": task.artifact_digest,
        "goal_key": task.goal_key,
        "capability": task.requested_capability,
        "execution_id": execution_id,
        "git_commit": git_commit,
        "status": "COMPLETE",
        "completion_classification": "VALIDATED_IN_MAINLINE",
        "input_artifact_digests": list(task.input_artifact_digests),
        "parent_digests": list(task.input_artifact_digests),
        "registered_artifact_count": 1,
        "actual_fold_count": 0,
        "simulation": True,
        "workload_rerun": False,
    }
    payload["artifact_digest"] = module.canonical_digest(
        payload, domain="dehps.research-os.mainline-execution.v1"
    )
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contract.canonical_json(payload) + "\n")
    common = {
        "execution_id": execution_id,
        "control_plane_key": contract.CONTROL_PLANE_KEY,
        "manifest_digest": current.artifact_digest,
        "task_key": task_key,
        "task_digest": task.artifact_digest,
        "capability": task.requested_capability,
    }
    started = MainlineExecutionEvent(
        **common,
        event_type="started",
        sequence=0,
        recorded_at="2026-09-05T01:00:00+00:00",
        payload=tuple(
            {
                "git_commit": git_commit,
                "input_artifact_digests": list(task.input_artifact_digests),
            }.items()
        ),
    )
    completed = MainlineExecutionEvent(
        **common,
        event_type="completed",
        sequence=1,
        recorded_at="2026-09-05T01:00:01+00:00",
        payload=tuple(
            {
                "git_commit": git_commit,
                "actual_fold_count": 0,
                "execution_artifact_path": relative,
                "execution_artifact_digest": payload["artifact_digest"],
                "registered_artifact_count": 1,
            }.items()
        ),
    )
    registration = MainlineArtifactRegistration(
        execution_id=execution_id,
        control_plane_key=contract.CONTROL_PLANE_KEY,
        task_key=task_key,
        task_digest=task.artifact_digest,
        artifact_digest=payload["artifact_digest"],
        artifact_type=payload["artifact_type"],
        schema_version=payload["schema_version"],
        artifact_path=relative,
        parent_digests=tuple(payload["parent_digests"]),
        git_commit=git_commit,
    )
    fact = module.mainline_completion_fact(task=task, execution_id=execution_id)
    states = tuple(
        replace(
            s,
            declared_status=TaskStatus.COMPLETED,
            completion_classification=CompletionClassification.COMPLETE,
        )
        if s.task_digest == task.artifact_digest
        else s
        for s in current.task_states
    )
    incoming = ControlPlaneManifest.from_dict(
        runner.builder.manifest_with_facts(
            replace(current, task_states=states).to_dict(include_digest=True),
            add_artifact_facts=(fact,),
        )
    )
    # All three rows plus completed manifest/state commit in one temporary DB
    # transaction; production is never connected through this factory.
    with repo.connection_factory() as connection:
        writer = runner.PostgresResearchOSRepository(lambda: nullcontext(connection))
        writer.record_mainline_execution_event(event=started)
        writer.register_mainline_artifact(registration=registration)
        writer.record_mainline_execution_event(event=completed)
        writer.import_manifest(
            control_plane_key=contract.CONTROL_PLANE_KEY,
            payload=incoming.to_dict(include_digest=True),
        )


@pytest.mark.parametrize(
    "point",
    [
        "rebind_committed_before_return",
        "daily_summary_replay_commit",
        "daily_mail_envelope_commit",
        "daily_mail_replay_commit",
        "daily_delivery_commit",
        "smtp_before_provider",
        "smtp_accepted_before_ledger",
        "smtp_ledger_before_return",
        "incident_resolution_commit",
        "activation_ready_boundary",
    ],
)
def test_real_post_rebind_interruption_matrix(real_rebind_repository, point):
    runner, repo, root, _ = real_rebind_repository
    origin = repo.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    before = _rebind_persisted_digest(repo, root)
    first = repo.rebind_unexecuted_daily_recovery_source()
    assert first["status"] == "REBIND_REQUIRED" and first["task_count"] == 6
    assert before != _rebind_persisted_digest(repo, root)
    rebound = repo.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    assert {t.task_key for t in rebound.tasks} == {t.task_key for t in origin.tasks}
    changed = {
        a.task_key for a, b in zip(origin.tasks, rebound.tasks, strict=True) if a != b
    }
    assert changed == set(first["task_keys"])
    stages = [
        "daily_summary_replay",
        "daily_mail_envelope",
        "daily_mail_replay",
        "daily_delivery",
    ]
    through = {
        "rebind_committed_before_return": 0,
        "daily_summary_replay_commit": 1,
        "daily_mail_envelope_commit": 2,
        "daily_mail_replay_commit": 3,
        "daily_delivery_commit": 4,
        "smtp_before_provider": 3,
        "smtp_accepted_before_ledger": 3,
        "smtp_ledger_before_return": 3,
        "incident_resolution_commit": 4,
        "activation_ready_boundary": 4,
    }[point]
    for name in stages[:through]:
        _commit_rebind_downstream_fixture(
            runner, repo, root, contract.task_template_by_name(name).key(repo.context)
        )
    if point in {"incident_resolution_commit", "activation_ready_boundary"}:
        current = repo.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        incident = next(
            t
            for t in origin.tasks
            if t.task_key
            == f"m4-isolated-24h-challenger-v11-incident-{contract.DAILY_RECOVERY_INCIDENT_ID}-open"
        )
        context = runner._task_context(incident)
        extension = runner.builder.extend_manifest(
            current.to_dict(include_digest=True),
            context=context,
            source_digest=repo.source_digest,
            template_names=frozenset({"incident_resolution"}),
        )
        repo.import_extension(extension)
        _commit_rebind_downstream_fixture(
            runner,
            repo,
            root,
            contract.task_template_by_name("incident_resolution").key(context),
        )
    # Interrupt after real durable fixture commits; repeated source rebind must
    # leave every event, registration, task state and byte untouched.
    with repo.connection_factory() as connection:
        connection.execute(
            "CREATE TABLE correction_interruption(point text PRIMARY KEY)"
        )
        connection.execute("INSERT INTO correction_interruption VALUES (%s)", (point,))
    stable = _rebind_persisted_digest(repo, root)
    results = [repo.rebind_unexecuted_daily_recovery_source() for _ in range(3)]
    assert all(r["status"] == "ALREADY_REBOUND" for r in results)
    assert results[0] == results[1] == results[2]
    assert stable == _rebind_persisted_digest(repo, root)
    assert all(
        r["manifest_digest"]
        == repo.load_manifest(
            control_plane_key=contract.CONTROL_PLANE_KEY
        ).artifact_digest
        for r in results
    )


@pytest.mark.parametrize(
    "mutation",
    ["partial", "missing", "extra", "parent", "state", "wrong_source", "head"],
)
def test_real_rebind_closure_rejects_drift(
    real_rebind_repository, monkeypatch, mutation
):
    runner, repo, root, _ = real_rebind_repository
    origin = repo.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    first = repo.rebind_unexecuted_daily_recovery_source()
    current = repo.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    keys = set(first["task_keys"])
    task = next(t for t in current.tasks if t.task_key in keys)
    old = next(t for t in origin.tasks if t.task_key == task.task_key)
    if mutation == "wrong_source":
        repo.source_digest = "0" * 64
    elif mutation == "head":
        with repo.connection_factory() as connection:
            connection.execute(
                "UPDATE research_os_control_planes SET current_manifest_digest=%s WHERE control_plane_key=%s",
                (origin.artifact_digest, contract.CONTROL_PLANE_KEY),
            )
    else:
        if mutation == "partial":
            changed = old
        elif mutation == "parent":
            changed = replace(task, input_artifact_digests=("0" * 64,))
        elif mutation == "extra":
            changed = replace(task, task_key=task.task_key + "-extra")
        else:
            changed = task
        tasks = tuple(changed if t == task else t for t in current.tasks)
        states = tuple(
            replace(s, task_digest=changed.artifact_digest)
            if s.task_digest == task.artifact_digest
            else s
            for s in current.task_states
        )
        if mutation == "missing":
            tasks = tuple(t for t in tasks if t != task)
            states = tuple(s for s in states if s.task_digest != task.artifact_digest)
        if mutation == "state":
            states = tuple(
                replace(
                    s,
                    declared_status=TaskStatus.COMPLETED,
                    completion_classification=CompletionClassification.COMPLETE,
                )
                if s.task_digest == task.artifact_digest
                else s
                for s in states
            )
        # Corrupt incoming immutable model, while retaining the actual DB for
        # provenance checks. The success matrix above never replaces this read.
        bad = replace(current, tasks=tasks, task_states=states)
        monkeypatch.setattr(repo, "load_manifest", lambda **_kwargs: bad)
    before = _rebind_persisted_digest(repo, root)
    with pytest.raises(
        (
            runner.ResearchOSValidationError,
            runner.mainline.IsolatedMainlineError,
            runner.mainline.MainlineSupervisorError,
        )
    ):
        repo.rebind_unexecuted_daily_recovery_source()
    assert before == _rebind_persisted_digest(repo, root)


ROOT = Path(__file__).resolve().parents[3]


def _load_script(name: str):
    path = ROOT / "apps/worker-python/scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _context():
    return contract.render_context(
        source_max_issue="2026100", source_max_draw_date="2026-08-30"
    )


def test_manifest_dry_run_has_exact_tasks_and_preregistration_ready() -> None:
    builder = _load_script("build_m4_isolated_24h_challenger_v11_manifest")
    context = _context()
    assert len(contract.TASK_TEMPLATES) == 43
    assert len(contract.ARTIFACT_TYPES) == 45
    payload, dry_run = builder.build_manifest(
        context=context,
        source_digest="a" * 64,
        operator_configuration_authorized=False,
        simulation_events=False,
    )
    manifest = ControlPlaneManifest.from_dict(payload)
    snapshot = builder.ControlPlaneManifest.from_dict(payload)
    resolved = (
        __import__(
            "dehps.research_os.control_plane", fromlist=["ResearchOSControlPlane"]
        )
        .ResearchOSControlPlane()
        .resolve(snapshot)
    )
    assert len(manifest.tasks) == 43
    assert dry_run["task_count"] == 43
    assert dry_run["import_performed"] is False
    assert [item.task_key for item in resolved.ready_queue] == [
        "m4-isolated-24h-challenger-v11-preregistration"
    ]


def test_incident_resolution_manifest_requires_sent_incident_and_daily_mail() -> None:
    builder = _load_script("build_m4_isolated_24h_challenger_v11_manifest")
    context = _context()
    assert "incident_resolution" not in builder.INCIDENT_TEMPLATE_NAMES
    payload, _ = builder.build_manifest(
        context=context,
        source_digest="a" * 64,
        operator_configuration_authorized=False,
        simulation_events=False,
    )
    manifest = ControlPlaneManifest.from_dict(payload)
    resolution = next(
        task
        for task in manifest.tasks
        if json.loads(task.metric_contract)["task_template"] == "incident_resolution"
    )
    incident_key = contract.task_template_by_name("incident_open").key(context)
    incident_delivery_key = contract.task_template_by_name("incident_delivery").key(
        context
    )
    daily_replay_key = contract.task_template_by_name("daily_summary_replay").key(
        context
    )
    daily_delivery_key = contract.task_template_by_name("daily_delivery").key(context)
    assert resolution.requested_capability == (
        "M4IsolatedIncidentResolutionCapabilityV11"
    )
    assert [
        (item.dependency_type.value, item.target_key)
        for item in resolution.dependencies
    ] == [
        ("artifact", f"{incident_key}:OPEN"),
        ("artifact", f"{incident_delivery_key}:SENT"),
        ("artifact", f"{daily_replay_key}:REGISTERED_REPLAY_VERIFIED"),
        ("artifact", f"{daily_delivery_key}:SENT"),
    ]


def test_daily_recovery_command_is_an_explicit_operator_surface() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    args = runner.parse_args(["recover-daily-mail", "--apply"])
    assert args.command == "recover-daily-mail"
    assert args.apply is True
    assert runner.DAILY_RECOVERY_OPERATIONS == (
        "disable-isolated-timer-and-wait-quiescent",
        "register-new-source-and-runtime-migration-input",
        "recover-daily-summary-sequence2-and-generic-replay",
        "rebind-all-unexecuted-old-source-tasks",
        "complete-daily-mail-chain-with-one-data250",
        "resolve-current-incident-and-advance-ledger",
        "prove-duplicate-cycle-zero-smtp",
        "reenable-isolated-timer-and-verify-status",
    )
    source = json.loads(
        (ROOT / contract.SOURCE_CONTRACT_PATH).read_text(encoding="utf-8")
    )
    expected = {
        "daily_recovery_historical_source_transition_fix_base_merged_commit": (
            "a00a30fc703064853d52f11b8576667ac34af401"
        ),
        "daily_recovery_historical_source_transition_fix_engineering_request_id": 791,
        "daily_recovery_historical_source_transition_fix_engineering_approval_decision_id": 3371,
        "daily_recovery_historical_source_transition_fix_engineering_execution_id": 638,
        "daily_recovery_historical_source_transition_fix_engineering_request_payload_sha256": (
            "aed8a3ed96ae39d276246a60c5ee926135793e438c0cee57cd936b04c72f9df3"
        ),
    }
    assert {key: source["governance_bindings"].get(key) for key in expected} == expected
    runner._validate_daily_recovery_transition_fix_source_binding(source)
    corrupted = json.loads(json.dumps(source))
    corrupted["governance_bindings"].pop(next(iter(expected)))
    with pytest.raises(
        runner.IsolatedRunnerError,
        match="historical_source_transition_fix_binding_changed",
    ):
        runner._validate_daily_recovery_transition_fix_source_binding(corrupted)
    health_expected = {
        "health_provenance_running_recovery_base_merged_commit": (
            "38a00a2c46427677e893b355c553e01b086f04eb"
        ),
        "health_provenance_running_recovery_engineering_request_key": (
            "engineering-m4-isolated-v11-health-provenance-and-running-daily-recovery-fix-v2"
        ),
        "health_provenance_running_recovery_engineering_request_id": 795,
        "health_provenance_running_recovery_engineering_approval_decision_id": 3387,
        "health_provenance_running_recovery_engineering_execution_id": 640,
        "health_provenance_running_recovery_engineering_request_payload_sha256": (
            "20047c995e9ecaf64ac2732118c649488341dc65dd936b9d4a2b6b523d7fc21e"
        ),
    }
    assert {
        key: source["governance_bindings"].get(key) for key in health_expected
    } == health_expected
    runner._validate_health_provenance_running_recovery_source_binding(source)
    corrupted = json.loads(json.dumps(source))
    corrupted["governance_bindings"].pop(next(iter(health_expected)))
    with pytest.raises(
        runner.IsolatedRunnerError,
        match="health_provenance_running_recovery_binding_changed",
    ):
        runner._validate_health_provenance_running_recovery_source_binding(corrupted)

    compatibility_expected = {
        "compatibility_binding_scope_fix_base_merged_commit": (
            "6968ed917e4f8bc7e7b9bf415531c93d4012aa9d"
        ),
        "compatibility_binding_scope_fix_engineering_request_key": (
            "engineering-m4-isolated-v11-actual-binding-scope-decoupling-v1"
        ),
        "compatibility_binding_scope_fix_engineering_request_id": 803,
        "compatibility_binding_scope_fix_engineering_approval_decision_id": 3417,
        "compatibility_binding_scope_fix_engineering_execution_id": 644,
        "compatibility_binding_scope_fix_engineering_request_payload_sha256": (
            "360e7221b935f72ece18f1dff9c4790c01d7264e0086fa9dcc36574175d7cfb4"
        ),
    }
    assert {
        key: source["governance_bindings"].get(key) for key in compatibility_expected
    } == compatibility_expected
    runner._validate_compatibility_binding_scope_fix_source_binding(source)
    for key in compatibility_expected:
        corrupted = json.loads(json.dumps(source))
        corrupted["governance_bindings"].pop(key)
        with pytest.raises(
            runner.IsolatedRunnerError,
            match="compatibility_binding_scope_fix_binding_changed",
        ):
            runner._validate_compatibility_binding_scope_fix_source_binding(corrupted)


def test_isolated_source_closure_excludes_unrelated_p3_top100(
    tmp_path: Path,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    source = json.loads(
        (ROOT / contract.SOURCE_CONTRACT_PATH).read_text(encoding="utf-8")
    )
    paths = [str(item["path"]) for item in source["source_entries"]]
    excluded = "apps/worker-python/dehps/notifications/p3_top100.py"
    assert len(paths) == 20
    assert excluded not in paths

    config_path = tmp_path / contract.SOURCE_CONTRACT_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(contract.canonical_json(source) + "\n", encoding="utf-8")
    for item in source["source_entries"]:
        relative = Path(str(item["path"]))
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    excluded_path = tmp_path / excluded
    excluded_path.parent.mkdir(parents=True, exist_ok=True)
    excluded_path.write_bytes(b"unrelated-mainline-p3-top100-change")

    loaded = runner.artifacts.load_source_contract(root_dir=tmp_path)
    assert loaded["artifact_digest"] == source["artifact_digest"]
    assert loaded["source_set_digest"] == source["source_set_digest"]

    retained = tmp_path / paths[0]
    retained.write_bytes(retained.read_bytes() + b"drift")
    with pytest.raises(
        runner.artifacts.IsolatedArtifactError,
        match="source_entry_bytes_changed",
    ):
        runner.artifacts.load_source_contract(root_dir=tmp_path)


def test_compatibility_binding_scope_fix_engineering_governance_is_exact() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")

    def validate(*, corruption: str | None = None) -> None:
        request = SimpleNamespace(
            id=runner.COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_REQUEST_ID,
            request_type=runner.AgentRequestType.ENGINEERING_IMPLEMENTATION,
            status=runner.AgentRequestStatus.COMPLETED,
            parent_request_id=(
                runner.COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_PARENT_REQUEST_ID
            ),
            metadata={
                "payload_sha256": (
                    runner.COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_PAYLOAD_SHA256
                )
            },
        )
        approval = SimpleNamespace(
            id=runner.COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_DECISION_ID,
            decision_code="request_approved",
            new_status="approved",
            decided_by_role=runner.AgentRole.REVIEWER,
        )
        execution = SimpleNamespace(
            id=runner.COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_EXECUTION_ID,
            status=runner.AgentExecutionStatus.COMPLETED,
            environment="development",
            executor_role=runner.AgentRole.ENGINEERING,
        )
        if corruption == "request_status":
            request.status = runner.AgentRequestStatus.EXECUTING
        elif corruption == "parent":
            request.parent_request_id += 1
        elif corruption == "payload":
            request.metadata = {"payload_sha256": "0" * 64}
        elif corruption == "approval":
            approval.id += 1
        elif corruption == "execution":
            execution.status = runner.AgentExecutionStatus.RUNNING

        class _Repository:
            @staticmethod
            def get_request(_key):
                return request

            @staticmethod
            def list_decisions(_key):
                return [approval]

            @staticmethod
            def list_execution_metadata(_key):
                return [execution]

        runner._validate_compatibility_binding_scope_fix_engineering_governance(
            _Repository()
        )

    validate()
    for corruption in (
        "request_status",
        "parent",
        "payload",
        "approval",
        "execution",
    ):
        with pytest.raises(
            runner.IsolatedRunnerError,
            match="compatibility_binding_scope_fix_engineering_governance_changed",
        ):
            validate(corruption=corruption)


def test_daily_recovery_operator_requires_completed_binding_scope_fix(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    source_digest = "a" * 64
    git_commit = "b" * 40
    scope_request = SimpleNamespace(
        id=runner.COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_REQUEST_ID,
        request_type=runner.AgentRequestType.ENGINEERING_IMPLEMENTATION,
        status=runner.AgentRequestStatus.COMPLETED,
        parent_request_id=(
            runner.COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_PARENT_REQUEST_ID
        ),
        metadata={
            "payload_sha256": (
                runner.COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_PAYLOAD_SHA256
            )
        },
    )
    research = SimpleNamespace(
        id=contract.DAILY_RECOVERY_RESEARCH_REQUEST_ID,
        status=runner.AgentRequestStatus.APPROVED,
        metadata={"payload_sha256": contract.DAILY_RECOVERY_RESEARCH_PAYLOAD_SHA256},
    )
    engineering = SimpleNamespace(
        id=contract.DAILY_RECOVERY_ENGINEERING_REQUEST_ID,
        status=runner.AgentRequestStatus.COMPLETED,
        parent_request_id=research.id,
        metadata={"payload_sha256": contract.DAILY_RECOVERY_ENGINEERING_PAYLOAD_SHA256},
    )
    binding_scope_fix = {
        "engineering_request_id": (
            runner.COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_REQUEST_ID
        ),
        "engineering_approval_decision_id": (
            runner.COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_DECISION_ID
        ),
        "engineering_execution_id": (
            runner.COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_EXECUTION_ID
        ),
        "engineering_request_payload_sha256": (
            runner.COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_PAYLOAD_SHA256
        ),
    }
    operator_payload = {
        "version": "m4-isolated-v11-daily-mail-recovery-operator-v1",
        "commit": git_commit,
        "source_contract_digest": source_digest,
        "binding_scope_fix": binding_scope_fix,
        "failed_execution": {
            "task_key": contract.DAILY_RECOVERY_TASK_KEY,
            "task_digest": contract.DAILY_RECOVERY_TASK_DIGEST,
            "execution_id": contract.DAILY_RECOVERY_EXECUTION_ID,
            "started_event_digest": contract.DAILY_RECOVERY_STARTED_EVENT_DIGEST,
            "failed_event_digest": contract.DAILY_RECOVERY_FAILED_EVENT_DIGEST,
            "original_source_contract_digest": (
                contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST
            ),
            "original_git_commit": contract.DAILY_RECOVERY_ORIGINAL_GIT_COMMIT,
            "workload_rerun": False,
        },
        "ordered_operations": list(runner.DAILY_RECOVERY_OPERATIONS),
        "smtp_budget": 1,
        "scientific_workload_budget": 0,
        "formal_p3_access_or_mutation": False,
        "p4_p5_p6_or_promotion": False,
        "checks": {},
        "rollback": {},
    }
    operator = SimpleNamespace(
        id=900,
        request_type=runner.AgentRequestType.OPERATOR_RELEASE,
        status=runner.AgentRequestStatus.EXECUTING,
        parent_request_id=engineering.id,
        payload=operator_payload,
        metadata={
            "payload_sha256": hashlib.sha256(
                contract.canonical_json(operator_payload).encode("utf-8")
            ).hexdigest()
        },
    )

    def approval(decision_id):
        return SimpleNamespace(
            id=decision_id,
            decision_code="request_approved",
            new_status="approved",
            decided_by_role=runner.AgentRole.REVIEWER,
        )

    executions = {
        runner.COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_REQUEST_KEY: [
            SimpleNamespace(
                id=runner.COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_EXECUTION_ID,
                status=runner.AgentExecutionStatus.COMPLETED,
                environment="development",
                executor_role=runner.AgentRole.ENGINEERING,
            )
        ],
        runner.DAILY_RECOVERY_ENGINEERING_REQUEST_KEY: [
            SimpleNamespace(
                id=contract.DAILY_RECOVERY_ENGINEERING_EXECUTION_ID,
                status=runner.AgentExecutionStatus.COMPLETED,
                environment="development",
                executor_role=runner.AgentRole.ENGINEERING,
            )
        ],
        "operator": [
            SimpleNamespace(
                id=901,
                status=runner.AgentExecutionStatus.RUNNING,
                environment="production",
                executor_role=runner.AgentRole.OPERATOR,
                started_at=datetime(2026, 8, 31, tzinfo=UTC),
            )
        ],
    }
    requests = {
        runner.COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_REQUEST_KEY: (scope_request),
        runner.DAILY_RECOVERY_RESEARCH_REQUEST_KEY: research,
        runner.DAILY_RECOVERY_ENGINEERING_REQUEST_KEY: engineering,
        "operator": operator,
    }
    decisions = {
        runner.COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_REQUEST_KEY: [
            approval(runner.COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_DECISION_ID)
        ],
        runner.DAILY_RECOVERY_RESEARCH_REQUEST_KEY: [
            approval(contract.DAILY_RECOVERY_RESEARCH_APPROVAL_DECISION_ID)
        ],
        runner.DAILY_RECOVERY_ENGINEERING_REQUEST_KEY: [
            approval(contract.DAILY_RECOVERY_ENGINEERING_APPROVAL_DECISION_ID)
        ],
        "operator": [approval(902)],
    }

    class _Repository:
        @staticmethod
        def get_request(key):
            return requests[key]

        @staticmethod
        def list_decisions(key):
            return decisions[key]

        @staticmethod
        def list_execution_metadata(key):
            return executions[key]

    source_contract = {
        "artifact_digest": source_digest,
        "governance_bindings": {
            "daily_mail_recovery_base_merged_commit": (
                contract.DAILY_RECOVERY_ORIGINAL_GIT_COMMIT
            ),
            "daily_mail_recovery_research_request_id": research.id,
            "daily_mail_recovery_research_approval_decision_id": (
                contract.DAILY_RECOVERY_RESEARCH_APPROVAL_DECISION_ID
            ),
            "daily_mail_recovery_research_request_payload_sha256": (
                contract.DAILY_RECOVERY_RESEARCH_PAYLOAD_SHA256
            ),
            "daily_mail_recovery_engineering_request_id": engineering.id,
            "daily_mail_recovery_engineering_approval_decision_id": (
                contract.DAILY_RECOVERY_ENGINEERING_APPROVAL_DECISION_ID
            ),
            "daily_mail_recovery_engineering_execution_id": (
                contract.DAILY_RECOVERY_ENGINEERING_EXECUTION_ID
            ),
            "daily_mail_recovery_engineering_request_payload_sha256": (
                contract.DAILY_RECOVERY_ENGINEERING_PAYLOAD_SHA256
            ),
        },
    }
    monkeypatch.setenv(runner.DAILY_RECOVERY_OPERATOR_ENV_KEY, "operator")
    monkeypatch.setenv(runner.DAILY_RECOVERY_OPERATOR_DECISION_ENV, "902")
    monkeypatch.setenv(runner.DAILY_RECOVERY_OPERATOR_EXECUTION_ENV, "901")
    result = runner.validate_daily_mail_recovery_governance(
        repository=_Repository(),
        source_contract=source_contract,
        runtime_source_digest=source_digest,
        git_commit=git_commit,
    )
    assert result["operator_request_id"] == operator.id

    operator.payload = {
        **operator_payload,
        "binding_scope_fix": {
            **binding_scope_fix,
            "engineering_execution_id": 0,
        },
    }
    operator.metadata = {
        "payload_sha256": hashlib.sha256(
            contract.canonical_json(operator.payload).encode("utf-8")
        ).hexdigest()
    }
    with pytest.raises(
        runner.IsolatedRunnerError,
        match="daily_recovery_operator_scope_changed",
    ):
        runner.validate_daily_mail_recovery_governance(
            repository=_Repository(),
            source_contract=source_contract,
            runtime_source_digest=source_digest,
            git_commit=git_commit,
        )


def test_runtime_health_activation_is_canonical_complete_and_never_backfilled() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = _context()
    template = contract.task_template_by_name("runtime_health")
    task_key = template.key(context)
    assert runner._activation_facts(
        task_key=task_key,
        template=template,
        context=context,
        repository=SimpleNamespace(),
    ) == (f"{task_key}:COMPLETE",)
    source = (
        ROOT / "apps/worker-python/scripts/run_m4_isolated_24h_challenger_v11.py"
    ).read_text(encoding="utf-8")
    activation = source[
        source.index("def _activation_facts(") : source.index(
            "def _activation_present(", source.index("def _activation_facts(")
        )
    ]
    assert "HEALTH_RECORDED" not in activation


def test_install_without_apply_is_non_mutating() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    result = runner.install(
        apply=False,
        context=_context(),
        source_digest="a" * 64,
        operator_configuration_authorized=False,
    )
    assert result["status"] == "DRY_RUN"
    assert result["import_performed"] is False
    assert result["smtp_calls"] == 0
    assert result["formal_p3_mutated"] is False


def test_install_apply_returns_imported_manifest_digest(monkeypatch) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    manifest_digest = "b" * 64
    payload = {"manifest_digest": manifest_digest}
    monkeypatch.setattr(
        runner.builder,
        "build_bootstrap_manifest",
        lambda **_kwargs: (payload, {"status": "DRY_RUN"}),
    )

    class _Repository:
        def __init__(self, **_kwargs):
            self.imported = None

        def ensure_schema(self):
            return None

        def import_bootstrap_manifest(self, manifest):
            kwargs = {"payload": manifest}
            self.imported = kwargs
            return "imported", manifest["manifest_digest"]

    monkeypatch.setattr(runner, "IsolatedChallengerRepository", _Repository)
    monkeypatch.setattr(
        runner,
        "_attest_database_schema",
        lambda **_kwargs: {
            "schema_version": contract.DATABASE_SCHEMA_VERSION,
            "contract_digest": contract.CONTRACT_DIGEST,
            "installed_git_commit": "c" * 40,
        },
    )
    monkeypatch.setattr(
        runner.artifacts,
        "load_source_contract",
        lambda **_kwargs: {"artifact_digest": "a" * 64},
    )
    monkeypatch.setattr(
        runner.mainline,
        "build_registered_input",
        lambda **_kwargs: {"artifact_digest": "d" * 64},
    )
    registered = iter(({"artifact_digest": "a" * 64}, {"artifact_digest": "d" * 64}))
    monkeypatch.setattr(
        runner.mainline,
        "register_input_artifact",
        lambda **_kwargs: next(registered),
    )

    result = runner.install(
        apply=True,
        context=_context(),
        source_digest="a" * 64,
        operator_configuration_authorized=True,
        git_commit="c" * 40,
    )

    assert result["status"] == "IMPORTED"
    assert result["manifest_digest"] == manifest_digest
    assert result["import_result"] == "imported"
    assert result["smtp_calls"] == 0
    assert result["workloads"] == 0
    assert result["formal_p3_mutated"] is False


def test_repository_allows_only_completed_attested_predecessor_tasks_in_mixed_source() -> (
    None
):
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = _context()
    old_payload, _ = runner.builder.build_manifest(
        context=context,
        source_digest=runner.LIVE_PARTIAL_PREDECESSOR_SOURCE_DIGEST,
        operator_configuration_authorized=True,
        simulation_events=False,
    )
    old = ControlPlaneManifest.from_dict(old_payload)
    old_task = old.tasks[0]
    task = replace(old_task, goal_digest=runner.LIVE_PARTIAL_FROZEN_GOAL_DIGEST)
    state = replace(
        old.task_state_by_digest[old_task.artifact_digest],
        task_digest=task.artifact_digest,
        declared_status=TaskStatus.COMPLETED,
        completion_classification=CompletionClassification.COMPLETE,
    )
    fact = (
        f"mainline-execution:{task.task_key}:{task.artifact_digest}:"
        f"{'1' * 64}:completed"
    )
    repository = object.__new__(runner.IsolatedChallengerRepository)
    repository.source_digest = "f" * 64
    repository._verify_isolated_task_definition(
        task,
        state=state,
        artifact_facts=frozenset({fact}),
        partial_live_rebind=True,
    )
    intermediate_payload, _ = runner.builder.build_manifest(
        context=context,
        source_digest=next(
            item
            for item in runner.LIVE_PARTIAL_COMPLETED_SOURCE_DIGESTS
            if item != runner.LIVE_PARTIAL_PREDECESSOR_SOURCE_DIGEST
        ),
        operator_configuration_authorized=True,
        simulation_events=False,
    )
    intermediate = ControlPlaneManifest.from_dict(intermediate_payload).tasks[0]
    intermediate = replace(
        intermediate, goal_digest=runner.LIVE_PARTIAL_FROZEN_GOAL_DIGEST
    )
    intermediate_state = replace(state, task_digest=intermediate.artifact_digest)
    intermediate_fact = (
        f"mainline-execution:{intermediate.task_key}:"
        f"{intermediate.artifact_digest}:{'3' * 64}:completed"
    )
    repository._verify_isolated_task_definition(
        intermediate,
        state=intermediate_state,
        artifact_facts=frozenset({intermediate_fact}),
        partial_live_rebind=True,
    )
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="historical_task_source_changed",
    ):
        repository._verify_isolated_task_definition(
            task,
            state=replace(
                state,
                declared_status=TaskStatus.DRAFT,
                completion_classification=CompletionClassification.INTEGRATION_PENDING,
            ),
            artifact_facts=frozenset({fact}),
            partial_live_rebind=True,
        )
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="historical_task_source_changed",
    ):
        repository._verify_isolated_task_definition(
            task,
            state=state,
            artifact_facts=frozenset(),
            partial_live_rebind=True,
        )
    arbitrary_payload, _ = runner.builder.build_manifest(
        context=context,
        source_digest="e" * 64,
        operator_configuration_authorized=True,
        simulation_events=False,
    )
    arbitrary = ControlPlaneManifest.from_dict(arbitrary_payload).tasks[0]
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="historical_task_source_changed",
    ):
        repository._verify_isolated_task_definition(
            arbitrary,
            state=replace(state, task_digest=arbitrary.artifact_digest),
            artifact_facts=frozenset(
                {
                    (
                        f"mainline-execution:{arbitrary.task_key}:"
                        f"{arbitrary.artifact_digest}:{'2' * 64}:completed"
                    )
                }
            ),
            partial_live_rebind=True,
        )


def test_daily_recovery_gate_allows_only_exact_historical_source_transition(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = contract.render_context(
        source_max_issue="2026099",
        source_max_draw_date="2026-08-27",
        target_issue="2026100",
        target_draw_date="2026-08-30",
        batch_seq=0,
        epoch_date="20260828",
        minute="202608280900",
        cut_checkpoint_ref="000000000000",
        projection_time="2026-08-28T09:00:21.441271+08:00",
    )
    payload, _ = runner.builder.build_manifest(
        context=context,
        source_digest=contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST,
        operator_configuration_authorized=True,
        simulation_events=False,
    )
    base = ControlPlaneManifest.from_dict(payload)
    original_tasks = {item.artifact_digest: item for item in base.tasks}
    frozen_tasks = tuple(
        replace(item, goal_digest=runner.LIVE_PARTIAL_FROZEN_GOAL_DIGEST)
        for item in base.tasks
    )
    frozen_by_key = {item.task_key: item for item in frozen_tasks}
    frozen_states = tuple(
        replace(
            state,
            task_digest=frozen_by_key[
                original_tasks[state.task_digest].task_key
            ].artifact_digest,
        )
        for state in base.task_states
    )
    daily = frozen_by_key[contract.DAILY_RECOVERY_TASK_KEY]
    assert daily.artifact_digest == contract.DAILY_RECOVERY_TASK_DIGEST
    failed_states = tuple(
        replace(
            state,
            declared_status=TaskStatus.FAILED,
            completion_classification=CompletionClassification.INTEGRATION_PENDING,
        )
        if state.task_digest == daily.artifact_digest
        else state
        for state in frozen_states
    )
    current = replace(base, tasks=frozen_tasks, task_states=failed_states)
    monkeypatch.setattr(
        runner, "DAILY_RECOVERY_CURRENT_MANIFEST_DIGEST", current.artifact_digest
    )
    running = replace(
        current,
        task_states=tuple(
            replace(
                state,
                declared_status=TaskStatus.RUNNING,
                completion_classification=CompletionClassification.INTEGRATED,
            )
            if state.task_digest == daily.artifact_digest
            else state
            for state in failed_states
        ),
    )
    repository = object.__new__(runner.IsolatedChallengerRepository)
    repository.context = context
    repository.source_digest = "f" * 64
    repository._fact_gate = None
    repository._definition_gate = None
    repository._bootstrap_rebind_gate = None
    repository._user_scope_resume_event_gate = False
    repository._user_scope_failed_transition_gate = None
    repository._daily_recovery_event_gate = False
    repository._daily_recovery_transition_gate = None
    repository._evolving_source_rebind_gate = None
    repository.load_manifest = lambda **_kwargs: current

    with pytest.raises(
        runner.ResearchOSValidationError,
        match="partial_live_source_set_changed",
    ):
        repository._verify_exact_transition(running)

    repository._daily_recovery_transition_gate = {
        "current_manifest_digest": "0" * 64,
        "running_manifest_digest": None,
        "router_consumed": False,
        "completion_consumed": False,
        "authoritative_completion_consumed": False,
    }
    repository._daily_recovery_event_gate = True
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="partial_live_source_set_changed",
    ):
        repository._verify_exact_transition(running)

    completion_fact = (
        f"mainline-execution:{daily.task_key}:{daily.artifact_digest}:"
        f"{'2' * 64}:completed"
    )
    completed = replace(
        running,
        task_states=tuple(
            replace(
                state,
                declared_status=TaskStatus.COMPLETED,
                completion_classification=CompletionClassification.COMPLETE,
            )
            if state.task_digest == daily.artifact_digest
            else state
            for state in running.task_states
        ),
        facts=replace(running.facts, artifacts=frozenset({completion_fact})),
    )
    repository._daily_recovery_transition_gate = {
        "current_manifest_digest": current.artifact_digest,
        "running_manifest_digest": running.artifact_digest,
        "router_consumed": True,
        "completion_consumed": True,
        "authoritative_completion_consumed": False,
    }
    repository.load_manifest = lambda **_kwargs: running
    repository._verify_exact_transition(completed)
    corrupted = replace(
        completed,
        facts=replace(
            completed.facts,
            artifacts=frozenset({completion_fact, "arbitrary:fact"}),
        ),
    )
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="fact_gate_changed",
    ):
        repository._verify_exact_transition(corrupted)

    repository._daily_recovery_transition_gate = {
        "current_manifest_digest": current.artifact_digest,
        "running_manifest_digest": None,
        "router_consumed": False,
        "completion_consumed": False,
        "authoritative_completion_consumed": False,
    }
    repository.load_manifest = lambda **_kwargs: current
    repository._verify_exact_transition(running)
    assert repository._daily_recovery_transition_gate == {
        "current_manifest_digest": current.artifact_digest,
        "running_manifest_digest": running.artifact_digest,
        "router_consumed": True,
        "completion_consumed": False,
        "authoritative_completion_consumed": False,
    }
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="daily_recovery_transition_gate_changed",
    ):
        repository._verify_exact_transition(running)

    repository._daily_recovery_transition_gate = {
        "current_manifest_digest": current.artifact_digest,
        "running_manifest_digest": running.artifact_digest,
        "router_consumed": True,
        "completion_consumed": True,
        "authoritative_completion_consumed": False,
    }
    repository.load_manifest = lambda **_kwargs: running
    monkeypatch.setattr(
        runner.PostgresResearchOSRepository,
        "_verify_mainline_completion_records",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        runner.ControlPlaneManifest,
        "from_dict",
        classmethod(lambda _cls, _value: running),
    )

    class _Cursor:
        statement = ""

        def execute(self, statement, _params):
            self.statement = statement
            return self

        def fetchone(self):
            if "current_manifest_digest" in self.statement:
                return {"current_manifest_digest": running.artifact_digest}
            return {"manifest_json": running.to_dict(include_digest=True)}

    cursor = _Cursor()
    repository._verify_mainline_completion_records(
        cursor,
        control_plane_key=contract.CONTROL_PLANE_KEY,
        manifest=completed,
    )
    assert (
        repository._daily_recovery_transition_gate["authoritative_completion_consumed"]
        is True
    )
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="authoritative_completion_gate_changed",
    ):
        repository._verify_mainline_completion_records(
            cursor,
            control_plane_key=contract.CONTROL_PLANE_KEY,
            manifest=completed,
        )

    for override in (
        {"current_manifest_digest": "0" * 64},
        {"running_manifest_digest": "0" * 64},
        {"router_consumed": False, "completion_consumed": False},
    ):
        repository._daily_recovery_transition_gate = {
            "current_manifest_digest": current.artifact_digest,
            "running_manifest_digest": running.artifact_digest,
            "router_consumed": True,
            "completion_consumed": True,
            "authoritative_completion_consumed": False,
            **override,
        }
        with pytest.raises(
            runner.ResearchOSValidationError,
            match="authoritative_completion_gate_changed",
        ):
            repository._verify_mainline_completion_records(
                cursor,
                control_plane_key=contract.CONTROL_PLANE_KEY,
                manifest=completed,
            )


def test_daily_recovery_exact_running_manifest_resumes_same_single_use_gate(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = contract.render_context(
        source_max_issue="2026099",
        source_max_draw_date="2026-08-27",
        target_issue="2026100",
        target_draw_date="2026-08-30",
        batch_seq=0,
        epoch_date="20260828",
        minute="202608280900",
        cut_checkpoint_ref="000000000000",
        projection_time="2026-08-28T09:00:21.441271+08:00",
    )
    payload, _ = runner.builder.build_manifest(
        context=context,
        source_digest=contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST,
        operator_configuration_authorized=True,
        simulation_events=False,
    )
    base = ControlPlaneManifest.from_dict(payload)
    original_tasks = {item.artifact_digest: item for item in base.tasks}
    frozen_tasks = tuple(
        replace(item, goal_digest=runner.LIVE_PARTIAL_FROZEN_GOAL_DIGEST)
        for item in base.tasks
    )
    frozen_by_key = {item.task_key: item for item in frozen_tasks}
    daily = frozen_by_key[contract.DAILY_RECOVERY_TASK_KEY]
    frozen_states = tuple(
        replace(
            state,
            task_digest=frozen_by_key[
                original_tasks[state.task_digest].task_key
            ].artifact_digest,
        )
        for state in base.task_states
    )
    failed = replace(
        base,
        tasks=frozen_tasks,
        task_states=tuple(
            replace(
                state,
                declared_status=TaskStatus.FAILED,
                completion_classification=CompletionClassification.INTEGRATED,
            )
            if state.task_digest == daily.artifact_digest
            else state
            for state in frozen_states
        ),
    )
    running = replace(
        failed,
        task_states=tuple(
            replace(
                state,
                declared_status=TaskStatus.RUNNING,
                completion_classification=CompletionClassification.INTEGRATED,
            )
            if state.task_digest == daily.artifact_digest
            else state
            for state in failed.task_states
        ),
    )
    completion_fact = (
        f"mainline-execution:{daily.task_key}:{daily.artifact_digest}:"
        f"{contract.DAILY_RECOVERY_EXECUTION_ID}:completed"
    )
    completed = replace(
        running,
        task_states=tuple(
            replace(
                state,
                declared_status=TaskStatus.COMPLETED,
                completion_classification=CompletionClassification.COMPLETE,
            )
            if state.task_digest == daily.artifact_digest
            else state
            for state in running.task_states
        ),
        facts=replace(
            running.facts,
            artifacts=running.facts.artifacts | frozenset({completion_fact}),
        ),
    )
    monkeypatch.setattr(
        runner, "DAILY_RECOVERY_CURRENT_MANIFEST_DIGEST", failed.artifact_digest
    )
    monkeypatch.setattr(
        runner, "DAILY_RECOVERY_RUNNING_MANIFEST_DIGEST", running.artifact_digest
    )
    repository = object.__new__(runner.IsolatedChallengerRepository)
    repository.context = context
    repository.source_digest = "f" * 64
    repository._fact_gate = None
    repository._definition_gate = None
    repository._bootstrap_rebind_gate = None
    repository._user_scope_resume_event_gate = False
    repository._user_scope_failed_transition_gate = None
    repository._daily_recovery_event_gate = False
    repository._daily_recovery_transition_gate = None
    repository._evolving_source_rebind_gate = None
    repository.load_manifest = lambda **_kwargs: running
    monkeypatch.setattr(
        runner.PostgresResearchOSRepository,
        "_verify_mainline_completion_records",
        lambda *_args, **_kwargs: None,
    )

    class _Cursor:
        statement = ""

        def execute(self, statement, _params):
            self.statement = statement
            return self

        def fetchone(self):
            if "current_manifest_digest" in self.statement:
                return {"current_manifest_digest": running.artifact_digest}
            return {"manifest_json": running.to_dict(include_digest=True)}

    with repository.daily_recovery_event_view():
        assert repository._daily_recovery_transition_gate == {
            "current_manifest_digest": failed.artifact_digest,
            "running_manifest_digest": running.artifact_digest,
            "router_consumed": True,
            "completion_consumed": True,
            "authoritative_completion_consumed": False,
        }
        repository._verify_exact_transition(completed)
        monkeypatch.setattr(
            runner.ControlPlaneManifest,
            "from_dict",
            classmethod(lambda _cls, _value: running),
        )
        repository._verify_mainline_completion_records(
            _Cursor(),
            control_plane_key=contract.CONTROL_PLANE_KEY,
            manifest=completed,
        )
        assert (
            repository._daily_recovery_transition_gate[
                "authoritative_completion_consumed"
            ]
            is True
        )
        with pytest.raises(
            runner.ResearchOSValidationError,
            match="authoritative_completion_gate_changed",
        ):
            repository._verify_mainline_completion_records(
                _Cursor(),
                control_plane_key=contract.CONTROL_PLANE_KEY,
                manifest=completed,
            )
    assert repository._daily_recovery_event_gate is False
    assert repository._daily_recovery_transition_gate is None

    for corrupted in (
        "0" * 64,
        failed.artifact_digest,
    ):
        monkeypatch.setattr(runner, "DAILY_RECOVERY_RUNNING_MANIFEST_DIGEST", corrupted)
        with (
            pytest.raises(runner.IsolatedRunnerError, match="current_manifest_changed"),
            repository.daily_recovery_event_view(),
        ):
            pass

    repository.load_manifest = lambda **_kwargs: failed
    monkeypatch.setattr(
        runner, "DAILY_RECOVERY_RUNNING_MANIFEST_DIGEST", running.artifact_digest
    )
    with (
        pytest.raises(runner.IsolatedRunnerError, match="current_manifest_changed"),
        repository.daily_recovery_event_view(),
    ):
        pass


@pytest.mark.parametrize(
    ("corruption", "expected_error"),
    (
        (None, None),
        ("registration", "live_registration_changed"),
        ("output", "live_output_changed"),
        ("delivery", "delivery_or_incident_state_changed"),
        ("incident", "delivery_or_incident_state_changed"),
        ("p3", "formal_p3_identity_changed"),
        ("source", "failed_operator_source_changed"),
        ("attestation", "failed_operator_attestation_changed"),
    ),
)
def test_daily_recovery_live_preflight_accepts_only_exact_d2c_resume_shape(
    monkeypatch, tmp_path, corruption, expected_error
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = contract.render_context(
        source_max_issue="2026099",
        source_max_draw_date="2026-08-27",
        target_issue="2026100",
        target_draw_date="2026-08-30",
        batch_seq=0,
        epoch_date="20260828",
        minute="202608280900",
        cut_checkpoint_ref="000000000000",
        projection_time="2026-08-28T09:00:21.441271+08:00",
    )
    daily_task = SimpleNamespace(
        task_key=contract.DAILY_RECOVERY_TASK_KEY,
        artifact_digest=contract.DAILY_RECOVERY_TASK_DIGEST,
        metric_contract=json.dumps(
            {
                "render_context": context,
                "source_contract_digest": contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
    )
    state = SimpleNamespace(
        declared_status=TaskStatus.RUNNING,
        completion_classification=CompletionClassification.INTEGRATED,
    )
    manifest = SimpleNamespace(
        artifact_digest=runner.DAILY_RECOVERY_RUNNING_MANIFEST_DIGEST,
        tasks=(daily_task,),
        task_state_by_digest={daily_task.artifact_digest: state},
    )
    events = (
        SimpleNamespace(
            event_type="started",
            sequence=0,
            artifact_digest=contract.DAILY_RECOVERY_STARTED_EVENT_DIGEST,
            execution_id=contract.DAILY_RECOVERY_EXECUTION_ID,
            task_digest=contract.DAILY_RECOVERY_TASK_DIGEST,
        ),
        SimpleNamespace(
            event_type="failed",
            sequence=1,
            artifact_digest=contract.DAILY_RECOVERY_FAILED_EVENT_DIGEST,
            execution_id=contract.DAILY_RECOVERY_EXECUTION_ID,
            task_digest=contract.DAILY_RECOVERY_TASK_DIGEST,
        ),
    )

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _statement, _params=None):
            return self

        def fetchone(self):
            return (1 if corruption == "delivery" else 0,)

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def cursor():
            return _Cursor()

    class _Repository:
        @staticmethod
        def load_manifest(**_kwargs):
            return manifest

        @staticmethod
        def list_mainline_execution_events(**_kwargs):
            return events

        @staticmethod
        def list_mainline_artifacts(**_kwargs):
            return ({"unexpected": True},) if corruption == "registration" else ()

        @staticmethod
        def connection_factory():
            return _Connection()

    monkeypatch.setattr(runner, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(runner, "_event_record", lambda value: value)
    monkeypatch.setattr(
        runner.mainline,
        "latest_incident_ledger_state",
        lambda **_kwargs: {
            "open_incident_ids": (
                []
                if corruption == "incident"
                else [contract.DAILY_RECOVERY_INCIDENT_ID]
            ),
            "transition_seq": 0,
        },
    )
    monkeypatch.setattr(
        runner,
        "_p3_source_identity",
        lambda: {
            "artifact_digest": (
                "0" * 64 if corruption == "p3" else contract.FORMAL_P3_SOURCE_DIGEST
            ),
            "source_set_digest": runner.FORMAL_P3_FROZEN_SOURCE_SET_DIGEST,
        },
    )

    def _input_prestate(**_kwargs):
        if corruption == "source":
            raise runner.IsolatedRunnerError(
                "daily_recovery_failed_operator_source_changed"
            )
        if corruption == "attestation":
            raise runner.IsolatedRunnerError(
                "daily_recovery_failed_operator_attestation_changed"
            )

    monkeypatch.setattr(
        runner, "_daily_recovery_failed_operator_input_prestate", _input_prestate
    )
    monkeypatch.setattr(
        runner,
        "_isolated_units_quiescent",
        lambda: {"timer": "inactive", "service": "inactive", "main_pid": 0},
    )
    if corruption == "output":
        output = (
            tmp_path
            / "runtime/isolated-24h-challenger-v11/artifacts"
            / contract.DAILY_RECOVERY_TASK_KEY
            / contract.DAILY_RECOVERY_EXECUTION_ID
        )
        output.mkdir(parents=True)

    if expected_error is None:
        live, live_context, incident = runner._daily_recovery_live_preflight(
            repository=_Repository()
        )
        assert live is manifest
        assert live_context == context
        assert incident["open_incident_ids"] == [contract.DAILY_RECOVERY_INCIDENT_ID]
    else:
        with pytest.raises(runner.IsolatedRunnerError, match=expected_error):
            runner._daily_recovery_live_preflight(repository=_Repository())


def test_daily_recovery_historical_tasks_require_exact_transient_states() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = contract.render_context(
        source_max_issue="2026099",
        source_max_draw_date="2026-08-27",
        target_issue="2026100",
        target_draw_date="2026-08-30",
        epoch_date="20260828",
        minute="202608280900",
        cut_checkpoint_ref="000000000000",
        projection_time="2026-08-28T09:00:21.441271+08:00",
    )
    payload, _ = runner.builder.build_manifest(
        context=context,
        source_digest=contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST,
        operator_configuration_authorized=True,
        simulation_events=False,
    )
    manifest = ControlPlaneManifest.from_dict(payload)
    daily_raw = next(
        item
        for item in manifest.tasks
        if item.task_key == contract.DAILY_RECOVERY_TASK_KEY
    )
    daily = replace(daily_raw, goal_digest=runner.LIVE_PARTIAL_FROZEN_GOAL_DIGEST)
    assert daily.artifact_digest == contract.DAILY_RECOVERY_TASK_DIGEST
    draft_raw = next(
        item
        for item in manifest.tasks
        if item.task_key != contract.DAILY_RECOVERY_TASK_KEY
    )
    draft = replace(draft_raw, goal_digest=runner.LIVE_PARTIAL_FROZEN_GOAL_DIGEST)
    repository = object.__new__(runner.IsolatedChallengerRepository)
    repository.source_digest = "f" * 64
    repository._daily_recovery_transition_gate = {"single_use": True}
    running_state = replace(
        manifest.task_state_by_digest[daily_raw.artifact_digest],
        task_digest=daily.artifact_digest,
        declared_status=TaskStatus.RUNNING,
        completion_classification=CompletionClassification.INTEGRATED,
    )
    repository._verify_isolated_task_definition(
        daily,
        state=running_state,
        artifact_facts=frozenset(),
        partial_live_rebind=True,
        daily_recovery_historical_only=True,
    )
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="historical_task_source_changed",
    ):
        repository._verify_isolated_task_definition(
            daily,
            state=running_state,
            artifact_facts=frozenset(),
            partial_live_rebind=True,
        )

    draft_state = replace(
        manifest.task_state_by_digest[draft_raw.artifact_digest],
        task_digest=draft.artifact_digest,
    )
    repository._verify_isolated_task_definition(
        draft,
        state=draft_state,
        artifact_facts=frozenset(),
        partial_live_rebind=True,
        daily_recovery_historical_only=True,
    )
    fake_completion = (
        f"mainline-execution:{draft.task_key}:{draft.artifact_digest}:"
        f"{'1' * 64}:completed"
    )
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="historical_task_source_changed",
    ):
        repository._verify_isolated_task_definition(
            draft,
            state=draft_state,
            artifact_facts=frozenset({fake_completion}),
            partial_live_rebind=True,
            daily_recovery_historical_only=True,
        )


def _bootstrap_rebind_fixture(runner):
    current_context = contract.render_context(
        source_max_issue="2026100",
        source_max_draw_date="2026-08-30",
        projection_time="2026-08-30T16:00:00+08:00",
    )
    incoming_context = contract.render_context(
        source_max_issue="2026100",
        source_max_draw_date="2026-08-30",
        projection_time="2026-08-30T16:30:00+08:00",
    )
    predecessor_payload, _ = runner.builder.build_bootstrap_manifest(
        context=current_context,
        source_digest=runner.PREDECESSOR_BOOTSTRAP_SOURCE_DIGEST,
        operator_configuration_authorized=True,
    )
    incoming_payload, _ = runner.builder.build_bootstrap_manifest(
        context=incoming_context,
        source_digest="f" * 64,
        operator_configuration_authorized=True,
    )
    return (
        current_context,
        incoming_context,
        ControlPlaneManifest.from_dict(predecessor_payload),
        incoming_payload,
    )


def _bootstrap_rebind_repository(runner, *, current, context, events=()):
    class _Cursor:
        def __init__(self):
            self.result = None

        def execute(self, statement, _params=None):
            if "SELECT current_manifest_digest" in statement:
                self.result = {"current_manifest_digest": current.artifact_digest}
            elif "SELECT manifest_json" in statement:
                self.result = {"manifest_json": current.to_dict(include_digest=True)}
            else:
                raise AssertionError(statement)
            return self

        def fetchone(self):
            return self.result

    class _Repository(runner.IsolatedChallengerRepository):
        def __init__(self):
            self.context = dict(context)
            self.source_digest = "f" * 64
            self._fact_gate = None
            self._definition_gate = None
            self._bootstrap_rebind_gate = None
            self.current = current

        def load_manifest(self, *, control_plane_key):
            assert control_plane_key == contract.CONTROL_PLANE_KEY
            return self.current

        def list_mainline_execution_event_metadata(self, **_kwargs):
            return tuple(events)

        def import_manifest(self, *, control_plane_key, payload, source="native"):
            assert control_plane_key == contract.CONTROL_PLANE_KEY
            assert source in {
                "native",
                "m4-isolated-24h-challenger-v11-operator-install",
                "m4-isolated-24h-challenger-v11-exact-bootstrap-rebind",
            }
            incoming = ControlPlaneManifest.from_dict(payload)
            self._verify_exact_transition(incoming)
            self._verify_mainline_completion_records(
                _Cursor(),
                control_plane_key=control_plane_key,
                manifest=incoming,
            )
            self.current = incoming
            return "imported"

    return _Repository()


def test_repository_rebinds_only_exact_unexecuted_predecessor_bootstrap() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    _, incoming_context, current, incoming_payload = _bootstrap_rebind_fixture(runner)
    repository = _bootstrap_rebind_repository(
        runner, current=current, context=incoming_context
    )

    result, digest = repository.import_bootstrap_manifest(incoming_payload)

    assert result == "imported"
    assert digest == repository.current.artifact_digest
    assert digest != ControlPlaneManifest.from_dict(incoming_payload).artifact_digest
    assert repository._bootstrap_rebind_gate is None
    assert all(
        state.declared_status is TaskStatus.DRAFT
        for state in repository.current.task_states
    )


def test_repository_rebind_preserves_exact_unexecuted_multicontext_task_set() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    current_context, incoming_context, current, incoming_payload = (
        _bootstrap_rebind_fixture(runner)
    )
    extra_context = {
        **current_context,
        "epoch_date": "20260828",
        "minute": "202608280052",
    }
    extended_payload = runner.builder.extend_manifest(
        current.to_dict(include_digest=True),
        context=extra_context,
        source_digest=runner.PREDECESSOR_BOOTSTRAP_SOURCE_DIGEST,
        template_names=frozenset({"runtime_health"}),
    )
    extended = ControlPlaneManifest.from_dict(extended_payload)
    assert len(extended.tasks) == 15
    preserved_keys = tuple(task.task_key for task in extended.tasks)
    repository = _bootstrap_rebind_repository(
        runner,
        current=extended,
        context=incoming_context,
    )

    result, digest = repository.import_bootstrap_manifest(incoming_payload)

    assert result == "imported"
    assert digest == repository.current.artifact_digest
    assert len(repository.current.tasks) == 15
    assert tuple(task.task_key for task in repository.current.tasks) == preserved_keys
    assert any(
        task.task_key.endswith("runtime-health-202608280052")
        for task in repository.current.tasks
    )
    assert repository._bootstrap_rebind_gate is None


def test_extension_inherits_the_single_frozen_live_goal_digest() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = _context()
    payload, _ = runner.builder.build_bootstrap_manifest(
        context=context,
        source_digest=runner.LIVE_PARTIAL_PREDECESSOR_SOURCE_DIGEST,
        operator_configuration_authorized=True,
    )
    current = ControlPlaneManifest.from_dict(payload)
    extension_context = {
        **context,
        "epoch_date": "20260828",
        "minute": "202608280216",
    }
    extended = ControlPlaneManifest.from_dict(
        runner.builder.extend_manifest(
            current.to_dict(include_digest=True),
            context=extension_context,
            source_digest="f" * 64,
            template_names=frozenset({"runtime_health"}),
        )
    )
    added = [
        item
        for item in extended.tasks
        if item.task_key not in {task.task_key for task in current.tasks}
    ]
    assert len(added) == 1
    assert added[0].goal_digest == current.goals[0].artifact_digest
    assert (
        __import__("json").loads(added[0].metric_contract)["source_contract_digest"]
        == "f" * 64
    )


@pytest.mark.parametrize("corruption", ["state", "fact", "event", "source"])
def test_repository_bootstrap_rebind_rejects_nonpristine_predecessor(
    corruption: str,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    current_context, incoming_context, current, incoming_payload = (
        _bootstrap_rebind_fixture(runner)
    )
    events = ()
    if corruption == "state":
        states = list(current.task_states)
        states[0] = replace(states[0], declared_status=TaskStatus.RUNNING)
        current = replace(current, task_states=tuple(states))
    elif corruption == "fact":
        current = replace(
            current,
            facts=replace(
                current.facts,
                artifacts=frozenset({"forged-bootstrap:COMPLETE"}),
            ),
        )
    elif corruption == "event":
        events = ({"event_type": "started"},)
    else:
        wrong_payload, _ = runner.builder.build_bootstrap_manifest(
            context=current_context,
            source_digest="e" * 64,
            operator_configuration_authorized=True,
        )
        current = ControlPlaneManifest.from_dict(wrong_payload)
    repository = _bootstrap_rebind_repository(
        runner,
        current=current,
        context=incoming_context,
        events=events,
    )

    with pytest.raises(
        runner.ResearchOSValidationError,
        match="bootstrap_rebind_precondition_changed",
    ):
        repository.import_bootstrap_manifest(incoming_payload)
    assert repository._bootstrap_rebind_gate is None


def test_repository_bootstrap_rebind_rejects_target_change_and_direct_import() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    _, incoming_context, current, incoming_payload = _bootstrap_rebind_fixture(runner)
    repository = _bootstrap_rebind_repository(
        runner, current=current, context=incoming_context
    )
    changed_context = contract.render_context(
        source_max_issue="2026101",
        source_max_draw_date="2026-09-01",
        projection_time="2026-09-01T16:30:00+08:00",
    )
    changed_payload, _ = runner.builder.build_bootstrap_manifest(
        context=changed_context,
        source_digest="f" * 64,
        operator_configuration_authorized=True,
    )
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="bootstrap_rebind_target_changed",
    ):
        repository.import_bootstrap_manifest(changed_payload)

    with pytest.raises(
        runner.ResearchOSValidationError,
        match="goal_transition_changed",
    ):
        repository.import_manifest(
            control_plane_key=contract.CONTROL_PLANE_KEY,
            payload=incoming_payload,
        )


def test_daily_recovery_exact_live_shape_enters_only_the_frozen_gate(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = contract.render_context(
        source_max_issue="2026099",
        source_max_draw_date="2026-08-27",
        target_issue="2026100",
        target_draw_date="2026-08-30",
        epoch_date="20260828",
        minute="202608280900",
        cut_checkpoint_ref="000000000000",
        projection_time="2026-08-28T09:00:21.441271+08:00",
    )
    source_counts = {
        runner.LIVE_PARTIAL_PREDECESSOR_SOURCE_DIGEST: 12,
        "45cd0aff1964f603ffb698da019a9803681dbe480c7bee9a322a592a05b79ffc": 1,
        "5452fc522812220b6654c2bb8e54b8844b0c2fdab251d392c2af8de501e659ec": 4,
        contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST: 80,
        "bf941daa91e4749354a237247f0c625ef0c47b57367d29acc58dc70642cda011": 2,
        "f067bc89f60826c15793e1ab6325a3dce088dd7c2af3e1c99e984d3aada50dd1": 2,
        "fb37933e24cc32677b13909e9f4689605b20eaf635a06ed364a4401ee768124c": 2,
    }
    assert frozenset(source_counts) == runner.LIVE_PARTIAL_COMPLETED_SOURCE_DIGESTS
    assert sum(source_counts.values()) == 103

    completed_tasks = []
    completed_states = []
    completion_facts = set()
    minute_zero = datetime(2026, 8, 26, 0, 0, tzinfo=UTC)
    minute_index = 0
    for source_digest, count in source_counts.items():
        for _ in range(count):
            rendered = dict(context)
            rendered["minute"] = (
                minute_zero + timedelta(minutes=minute_index)
            ).strftime("%Y%m%d%H%M")
            minute_index += 1
            payload, _ = runner.builder.build_manifest(
                context=rendered,
                source_digest=source_digest,
                operator_configuration_authorized=True,
                simulation_events=False,
            )
            generated = ControlPlaneManifest.from_dict(payload)
            raw_task = next(
                item
                for item in generated.tasks
                if json.loads(item.metric_contract)["task_template"] == "runtime_health"
            )
            task = replace(raw_task, goal_digest=runner.LIVE_PARTIAL_FROZEN_GOAL_DIGEST)
            state = replace(
                generated.task_state_by_digest[raw_task.artifact_digest],
                task_digest=task.artifact_digest,
                declared_status=TaskStatus.COMPLETED,
                completion_classification=CompletionClassification.COMPLETE,
            )
            execution_id = hashlib.sha256(
                f"live-shape:{task.task_key}".encode()
            ).hexdigest()
            completed_tasks.append(task)
            completed_states.append(state)
            completion_facts.add(
                f"mainline-execution:{task.task_key}:{task.artifact_digest}:"
                f"{execution_id}:completed"
            )

    daily_payload, _ = runner.builder.build_manifest(
        context=context,
        source_digest=contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST,
        operator_configuration_authorized=True,
        simulation_events=False,
    )
    daily_manifest = ControlPlaneManifest.from_dict(daily_payload)
    daily_tasks = {item.task_key: item for item in daily_manifest.tasks}
    draft_keys = {
        "m4-isolated-24h-challenger-v11-multiplicity-risk-limit",
        "m4-isolated-24h-challenger-v11-daily-20260828-delivery",
        "m4-isolated-24h-challenger-v11-daily-20260828-mail-replay",
        "m4-isolated-24h-challenger-v11-daily-20260828-mail-envelope",
        "m4-isolated-24h-challenger-v11-daily-20260828-summary-replay",
        "m4-isolated-24h-challenger-v11-search-checkpoint-000000000004-replay",
    }
    checkpoint_context = dict(context)
    checkpoint_context["batch_seq"] = "000000000004"
    checkpoint_context["cut_checkpoint_ref"] = "000000000004"
    checkpoint_payload, _ = runner.builder.build_manifest(
        context=checkpoint_context,
        source_digest=contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST,
        operator_configuration_authorized=True,
        simulation_events=False,
    )
    checkpoint_manifest = ControlPlaneManifest.from_dict(checkpoint_payload)
    checkpoint_key = (
        "m4-isolated-24h-challenger-v11-search-checkpoint-000000000004-replay"
    )
    daily_tasks[checkpoint_key] = next(
        item for item in checkpoint_manifest.tasks if item.task_key == checkpoint_key
    )
    assert draft_keys.issubset(daily_tasks)
    frozen_drafts = tuple(
        replace(daily_tasks[key], goal_digest=runner.LIVE_PARTIAL_FROZEN_GOAL_DIGEST)
        for key in sorted(draft_keys)
    )
    draft_states = tuple(
        replace(
            (
                checkpoint_manifest
                if task.task_key == checkpoint_key
                else daily_manifest
            ).task_state_by_digest[daily_tasks[task.task_key].artifact_digest],
            task_digest=task.artifact_digest,
            declared_status=TaskStatus.DRAFT,
            completion_classification=CompletionClassification.INTEGRATION_PENDING,
        )
        for task in frozen_drafts
    )
    raw_daily = daily_tasks[contract.DAILY_RECOVERY_TASK_KEY]
    daily = replace(raw_daily, goal_digest=runner.LIVE_PARTIAL_FROZEN_GOAL_DIGEST)
    assert daily.artifact_digest == contract.DAILY_RECOVERY_TASK_DIGEST
    failed_state = replace(
        daily_manifest.task_state_by_digest[raw_daily.artifact_digest],
        task_digest=daily.artifact_digest,
        declared_status=TaskStatus.FAILED,
        completion_classification=CompletionClassification.INTEGRATION_PENDING,
    )
    tasks = tuple(completed_tasks) + frozen_drafts + (daily,)
    states = tuple(completed_states) + draft_states + (failed_state,)
    current = replace(
        daily_manifest,
        tasks=tasks,
        task_states=states,
        facts=replace(
            daily_manifest.facts,
            artifacts=frozenset(completion_facts),
        ),
    )
    running = replace(
        current,
        task_states=tuple(
            replace(
                state,
                declared_status=TaskStatus.RUNNING,
                completion_classification=CompletionClassification.INTEGRATED,
            )
            if state.task_digest == daily.artifact_digest
            else state
            for state in current.task_states
        ),
    )
    monkeypatch.setattr(
        runner, "DAILY_RECOVERY_CURRENT_MANIFEST_DIGEST", current.artifact_digest
    )
    repository = object.__new__(runner.IsolatedChallengerRepository)
    repository.context = context
    repository.source_digest = "f" * 64
    repository._fact_gate = None
    repository._definition_gate = None
    repository._bootstrap_rebind_gate = None
    repository._user_scope_resume_event_gate = False
    repository._user_scope_failed_transition_gate = None
    repository._daily_recovery_event_gate = True
    repository._daily_recovery_transition_gate = {
        "current_manifest_digest": current.artifact_digest,
        "running_manifest_digest": None,
        "router_consumed": False,
        "completion_consumed": False,
        "authoritative_completion_consumed": False,
    }
    repository._evolving_source_rebind_gate = None
    repository.load_manifest = lambda **_kwargs: current

    status_counts = {
        status: sum(state.declared_status is status for state in current.task_states)
        for status in (TaskStatus.COMPLETED, TaskStatus.DRAFT, TaskStatus.FAILED)
    }
    assert len(current.tasks) == 110
    assert status_counts == {
        TaskStatus.COMPLETED: 103,
        TaskStatus.DRAFT: 6,
        TaskStatus.FAILED: 1,
    }
    assert {
        task.task_key
        for task in current.tasks
        if current.task_state_by_digest[task.artifact_digest].declared_status
        is TaskStatus.DRAFT
    } == draft_keys
    repository._verify_exact_transition(running)
    assert repository._daily_recovery_transition_gate == {
        "current_manifest_digest": current.artifact_digest,
        "running_manifest_digest": running.artifact_digest,
        "router_consumed": True,
        "completion_consumed": False,
        "authoritative_completion_consumed": False,
    }


def test_repository_bootstrap_rebind_gate_is_nonreentrant() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    _, incoming_context, current, incoming_payload = _bootstrap_rebind_fixture(runner)
    repository = _bootstrap_rebind_repository(
        runner, current=current, context=incoming_context
    )
    repository._bootstrap_rebind_gate = {"consumed": False}
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="bootstrap_rebind_gate_reentrant",
    ):
        repository.import_bootstrap_manifest(incoming_payload)


def test_recovery_completion_is_committed_then_replayed_before_activation(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = contract.render_context(
        source_max_issue="2026099",
        source_max_draw_date="2026-08-27",
        target_issue="2026100",
        target_draw_date="2026-08-30",
        epoch_date="20260828",
        minute="202608280900",
        cut_checkpoint_ref="000000000000",
        projection_time="2026-08-28T09:00:21.441271+08:00",
    )
    task = SimpleNamespace(
        task_key=contract.DAILY_RECOVERY_TASK_KEY,
        artifact_digest=contract.DAILY_RECOVERY_TASK_DIGEST,
    )
    manifest = SimpleNamespace(
        tasks=(task,),
        facts=SimpleNamespace(artifacts=frozenset()),
        task_state_by_digest={
            task.artifact_digest: SimpleNamespace(
                declared_status=TaskStatus.RUNNING,
            )
        },
    )
    order: list[str] = []

    class _Supervisor:
        def __init__(self, **_kwargs):
            pass

        @staticmethod
        def run_once(*, task_key):
            order.append("atomic_commit")
            return {
                "status": "COMPLETE",
                "task_key": task_key,
                "execution_id": contract.DAILY_RECOVERY_EXECUTION_ID,
            }

        @staticmethod
        def replay(*, task_key, execution_id):
            assert task_key == contract.DAILY_RECOVERY_TASK_KEY
            assert execution_id == contract.DAILY_RECOVERY_EXECUTION_ID
            order.append("typed_and_generic_replay")
            return {
                "status": "REPLAY_VERIFIED",
                "same_execution_identity": True,
                "same_artifact_identity": True,
                "same_artifact_content": True,
                "all_registrations_and_parent_chains_exact": True,
                "manual_input_assembly": False,
                "dispatch_performed": False,
            }

    class _Repository:
        def __init__(self):
            self.imported: list[tuple[str, ...]] = []

        @staticmethod
        def load_manifest(**_kwargs):
            return manifest

        def import_verified_facts(self, facts):
            order.append("ordinary_activation")
            self.imported.append(tuple(facts))

    monkeypatch.setattr(runner.mainline, "IsolatedChallengerSupervisor", _Supervisor)
    monkeypatch.setattr(
        runner.mainline,
        "load_completed_task_artifacts",
        lambda **_kwargs: (
            {
                "artifact_type": "M4IsolatedDailySummaryV11",
                "parent_digests": ["d" * 64],
            },
        ),
    )
    monkeypatch.setattr(
        runner.artifacts,
        "replay_artifact",
        lambda *_args, **_kwargs: {"status": "REPLAY_VERIFIED"},
    )
    original_activation = runner._activation_facts

    def _activation(**activation_kwargs):
        order.append("ordinary_activation")
        return original_activation(**activation_kwargs)

    monkeypatch.setattr(runner, "_activation_facts", _activation)
    repository = _Repository()
    kwargs = {
        "repository": repository,
        "task_key": contract.DAILY_RECOVERY_TASK_KEY,
        "context": context,
        "source_digest": contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST,
        "git_commit": contract.DAILY_RECOVERY_ORIGINAL_GIT_COMMIT,
        "runtime_source_digest": "a" * 64,
        "runtime_git_commit": "b" * 40,
        "attestation_digest": "c" * 64,
    }
    result = runner._dispatch_recovery_task(**kwargs)
    assert order == [
        "atomic_commit",
        "typed_and_generic_replay",
        "ordinary_activation",
    ]
    assert repository.imported == []
    assert result["generic_replay"] == "REPLAY_VERIFIED"

    order.clear()
    repository.imported.clear()
    monkeypatch.setattr(
        _Supervisor,
        "replay",
        staticmethod(
            lambda **_kwargs: {
                "status": "REPLAY_FAILED",
                "same_execution_identity": False,
            }
        ),
    )
    with pytest.raises(runner.IsolatedRunnerError, match="generic_replay_failed"):
        runner._dispatch_recovery_task(**kwargs)
    assert order == ["atomic_commit"]
    assert repository.imported == []


def test_committed_daily_preflight_accepts_exact_postcommit_and_rejects_uncertain(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = contract.render_context(
        source_max_issue="2026099",
        source_max_draw_date="2026-08-27",
        target_issue="2026100",
        target_draw_date="2026-08-30",
        epoch_date="20260828",
        minute="202608280900",
        cut_checkpoint_ref="000000000000",
        projection_time="2026-08-28T09:00:21.441271+08:00",
    )
    task = SimpleNamespace(
        task_key=contract.DAILY_RECOVERY_TASK_KEY,
        metric_contract=json.dumps(
            {"render_context": context}, sort_keys=True, separators=(",", ":")
        ),
    )
    manifest = SimpleNamespace(
        artifact_digest=runner.DAILY_RECOVERY_POST_COMMIT_MANIFEST_DIGEST,
        tasks=(task,),
    )

    class _Cursor:
        rows = ()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, _params=None):
            assert "delivery_ledger" in statement
            return self

        def fetchall(self):
            return list(self.rows)

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def cursor():
            return _Cursor()

    class _Repository:
        @staticmethod
        def load_manifest(**_kwargs):
            return manifest

        @staticmethod
        def connection_factory():
            return _Connection()

    monkeypatch.setattr(
        runner.mainline,
        "load_recovered_daily_summary_completed_execution",
        lambda **_kwargs: ({}, {}, []),
    )
    monkeypatch.setattr(
        runner.mainline,
        "latest_incident_ledger_state",
        lambda **_kwargs: {
            "open_incident_ids": [contract.DAILY_RECOVERY_INCIDENT_ID],
            "resolved_incident_ids": [],
            "transition_seq": 0,
        },
    )
    monkeypatch.setattr(
        runner,
        "_p3_source_identity",
        lambda: {
            "artifact_digest": contract.FORMAL_P3_SOURCE_DIGEST,
            "source_set_digest": runner.FORMAL_P3_FROZEN_SOURCE_SET_DIGEST,
        },
    )
    monkeypatch.setattr(
        runner, "_daily_recovery_failed_operator_input_prestate", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        runner, "_isolated_units_quiescent", lambda: {"status": "QUIESCENT"}
    )
    start, loaded, loaded_context, incident = (
        runner._daily_recovery_committed_state_preflight(repository=_Repository())
    )
    assert start == "POST_COMMIT"
    assert loaded is manifest
    assert loaded_context == context
    assert incident["transition_seq"] == 0

    _Cursor.rows = [("UNCERTAIN", 1)]
    with pytest.raises(
        runner.IsolatedRunnerError,
        match="daily_recovery_smtp_state_uncertain_or_changed",
    ):
        runner._daily_recovery_committed_state_preflight(repository=_Repository())


def test_postcommit_resume_skips_dispatch_and_orders_typed_generic_activation(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = contract.render_context(
        source_max_issue="2026099",
        source_max_draw_date="2026-08-27",
        target_issue="2026100",
        target_draw_date="2026-08-30",
        epoch_date="20260828",
        minute="202608280900",
        cut_checkpoint_ref="000000000000",
        projection_time="2026-08-28T09:00:21.441271+08:00",
    )
    task = SimpleNamespace(
        task_key=contract.DAILY_RECOVERY_TASK_KEY,
        artifact_digest=contract.DAILY_RECOVERY_TASK_DIGEST,
    )
    manifest = SimpleNamespace(
        tasks=(task,), facts=SimpleNamespace(artifacts=frozenset())
    )
    order: list[str] = []

    class _Repository:
        def __init__(self):
            self.imported = []

        @staticmethod
        def load_manifest(**_kwargs):
            return manifest

        def import_verified_facts(self, facts):
            order.append("activation")
            self.imported.append(tuple(facts))

    class _Supervisor:
        def __init__(self, **_kwargs):
            pass

        @staticmethod
        def run_once(**_kwargs):
            raise AssertionError("POST_COMMIT must not dispatch")

        @staticmethod
        def replay(**_kwargs):
            order.append("generic")
            return {
                "status": "REPLAY_VERIFIED",
                "same_execution_identity": True,
                "same_artifact_identity": True,
                "same_artifact_content": True,
                "all_registrations_and_parent_chains_exact": True,
                "manual_input_assembly": False,
                "dispatch_performed": False,
            }

    monkeypatch.setattr(
        runner.mainline,
        "load_recovered_daily_summary_completed_execution",
        lambda **_kwargs: (
            {"event_digest": runner.DAILY_RECOVERY_COMMITTED_EVENT_DIGEST},
            {
                "execution_id": contract.DAILY_RECOVERY_EXECUTION_ID,
                "artifact_digest": runner.DAILY_RECOVERY_COMMITTED_EXECUTION_DIGEST,
            },
            [],
        ),
    )
    monkeypatch.setattr(
        runner.mainline,
        "load_completed_task_artifacts",
        lambda **_kwargs: (
            {
                "artifact_type": "M4IsolatedDailySummaryV11",
                "artifact_digest": runner.DAILY_RECOVERY_COMMITTED_SUMMARY_DIGEST,
                "parent_digests": ["a" * 64],
            },
        ),
    )
    monkeypatch.setattr(
        runner.artifacts,
        "replay_artifact",
        lambda *_args, **_kwargs: (
            order.append("typed")
            or {
                "status": "REPLAY_VERIFIED",
                "artifact_digest": runner.DAILY_RECOVERY_COMMITTED_SUMMARY_DIGEST,
                "dispatch_performed": False,
            }
        ),
    )
    monkeypatch.setattr(runner.mainline, "IsolatedChallengerSupervisor", _Supervisor)
    monkeypatch.setattr(
        runner.mainline,
        "template_for_task_key",
        lambda *_args, **_kwargs: SimpleNamespace(name="daily_summary"),
    )
    monkeypatch.setattr(
        runner,
        "_activation_facts",
        lambda **_kwargs: order.append("activation_build") or ("daily:COMPLETE",),
    )
    result = runner._resume_committed_daily_summary(
        repository=_Repository(), context=context
    )
    assert result["dispatch_performed"] is False
    assert result["workload_rerun"] is False
    assert result["typed_replay"] == result["generic_replay"] == "REPLAY_VERIFIED"
    assert order == ["typed", "generic", "activation_build", "activation"]


def test_committed_recovery_fixture_identities_are_frozen() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    assert runner.DAILY_RECOVERY_PRE_COMMIT_FIXTURE_DIGEST == (
        "bcb0f311f2841e009a14a9b22ea8e1bc3787a70f413d24abae6f7bf7a720365d"
    )
    assert runner.DAILY_RECOVERY_POST_COMMIT_FIXTURE_DIGEST == (
        "cb2707fa51bb37209fea9c5aa54ef3b12d50a8f19cf7db1be934d1799626d76a"
    )


def test_roll_forward_before_preregistration_never_loads_completed_health(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = contract.render_context(
        source_max_issue="2026100",
        source_max_draw_date="2026-08-30",
        projection_time="2026-08-30T16:00:00+08:00",
    )
    payload, _ = runner.builder.build_bootstrap_manifest(
        context=context,
        source_digest="f" * 64,
        operator_configuration_authorized=True,
    )
    extensions = []

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, _params=None):
            self.statement = statement
            return self

        def fetchone(self):
            if "multiplicity_head" in self.statement:
                return (0, 0)
            assert "registration_batches" in self.statement
            return (0,)

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def cursor():
            return _Cursor()

    class _Repository:
        @staticmethod
        def connection_factory():
            return _Connection()

        @staticmethod
        def export_manifest(**_kwargs):
            return payload

        @staticmethod
        def import_extension(value):
            extensions.append(value)

    monkeypatch.setattr(
        runner,
        "_latest_registered_health_artifact",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("pre-preregistration health load")
        ),
    )

    runner._roll_forward(
        repository=_Repository(),
        context=context,
        source_digest="f" * 64,
        now=datetime(2026, 8, 28, 0, 47, tzinfo=contract.TIMEZONE),
    )

    assert len(extensions) == 1
    extended = ControlPlaneManifest.from_dict(extensions[0])
    assert len(extended.tasks) == 15
    assert contract.FREEZE_FACT not in extended.facts.artifacts


@pytest.mark.parametrize(
    ("before", "after", "with_completion_fact"),
    [
        (TaskStatus.DRAFT, TaskStatus.RUNNING, False),
        (TaskStatus.RUNNING, TaskStatus.FAILED, False),
        (TaskStatus.RUNNING, TaskStatus.COMPLETED, True),
    ],
)
def test_completion_verifier_accepts_only_exact_lifecycle_transition_shape(
    monkeypatch, before: TaskStatus, after: TaskStatus, with_completion_fact: bool
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = _context()
    payload, _ = runner.builder.build_bootstrap_manifest(
        context=context,
        source_digest="f" * 64,
        operator_configuration_authorized=True,
    )
    base = ControlPlaneManifest.from_dict(payload)
    states = list(base.task_states)
    states[0] = replace(states[0], declared_status=before)
    current = replace(base, task_states=tuple(states))
    states[0] = replace(states[0], declared_status=after)
    incoming = replace(base, task_states=tuple(states))
    if with_completion_fact:
        fact = (
            f"mainline-execution:{base.tasks[0].task_key}:"
            f"{'a' * 64}:{'b' * 64}:completed"
        )
        incoming = replace(
            incoming,
            facts=replace(incoming.facts, artifacts=frozenset({fact})),
        )

    class _Cursor:
        def __init__(self):
            self.result = None

        def execute(self, statement, _params=None):
            if "SELECT current_manifest_digest" in statement:
                self.result = {"current_manifest_digest": current.artifact_digest}
            elif "SELECT manifest_json" in statement:
                self.result = {"manifest_json": current.to_dict(include_digest=True)}
            else:
                raise AssertionError(statement)
            return self

        def fetchone(self):
            return self.result

    repository = object.__new__(runner.IsolatedChallengerRepository)
    repository._bootstrap_rebind_gate = None
    monkeypatch.setattr(
        runner.PostgresResearchOSRepository,
        "_verify_mainline_completion_records",
        lambda *_args, **_kwargs: None,
    )

    repository._verify_mainline_completion_records(
        _Cursor(),
        control_plane_key=contract.CONTROL_PLANE_KEY,
        manifest=incoming,
    )


@pytest.mark.parametrize(
    ("before", "after", "with_fact"),
    [
        (TaskStatus.DRAFT, TaskStatus.RUNNING, True),
        (TaskStatus.RUNNING, TaskStatus.FAILED, True),
        (TaskStatus.RUNNING, TaskStatus.COMPLETED, False),
        (TaskStatus.DRAFT, TaskStatus.COMPLETED, True),
    ],
)
def test_completion_verifier_rejects_wrong_fact_or_transition(
    monkeypatch, before: TaskStatus, after: TaskStatus, with_fact: bool
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    payload, _ = runner.builder.build_bootstrap_manifest(
        context=_context(),
        source_digest="f" * 64,
        operator_configuration_authorized=True,
    )
    base = ControlPlaneManifest.from_dict(payload)
    current_states = list(base.task_states)
    current_states[0] = replace(current_states[0], declared_status=before)
    current = replace(base, task_states=tuple(current_states))
    incoming_states = list(current.task_states)
    incoming_states[0] = replace(incoming_states[0], declared_status=after)
    incoming = replace(current, task_states=tuple(incoming_states))
    if with_fact:
        fact = (
            f"mainline-execution:{base.tasks[0].task_key}:"
            f"{'a' * 64}:{'b' * 64}:completed"
        )
        incoming = replace(
            incoming,
            facts=replace(incoming.facts, artifacts=frozenset({fact})),
        )

    class _Cursor:
        def __init__(self):
            self.result = None

        def execute(self, statement, _params=None):
            self.result = (
                {"current_manifest_digest": current.artifact_digest}
                if "SELECT current_manifest_digest" in statement
                else {"manifest_json": current.to_dict(include_digest=True)}
            )
            return self

        def fetchone(self):
            return self.result

    repository = object.__new__(runner.IsolatedChallengerRepository)
    repository._bootstrap_rebind_gate = None
    monkeypatch.setattr(
        runner.PostgresResearchOSRepository,
        "_verify_mainline_completion_records",
        lambda *_args, **_kwargs: None,
    )
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="atomic_completion_transition_changed",
    ):
        repository._verify_mainline_completion_records(
            _Cursor(),
            control_plane_key=contract.CONTROL_PLANE_KEY,
            manifest=incoming,
        )


def test_fact_builder_rejects_formal_route_or_promotion() -> None:
    builder = _load_script("build_m4_isolated_24h_challenger_v11_manifest")
    context = _context()
    payload, _ = builder.build_manifest(context=context, source_digest="a" * 64)
    for fact in (
        "m4-p3-illegal:COMPLETE",
        "successor:PASS_TO_P4",
        "successor:PASS_TO_P5",
        "PROMOTION:TRIGGERED",
    ):
        try:
            builder.manifest_with_facts(payload, add_artifact_facts=(fact,))
        except builder.IsolatedManifestError:
            pass
        else:
            raise AssertionError(f"forbidden fact accepted: {fact}")


def test_activation_compiles_delivery_only_from_registered_receipt(monkeypatch) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = _context()
    delivery = contract.task_template_by_name("predraw_delivery")
    body = {
        "state": "SENT",
        "delivery_key": "1" * 64,
        "mail_kind": "PREDRAW_TOP100",
        "target_issue": context["target_issue"],
        "content_digest": "2" * 64,
        "recipient_set_digest": "3" * 64,
        "attempt_count": 1,
        "smtp_transaction_started_at": "2026-08-27T09:00:00+00:00",
        "smtp_data_accepted_at": "2026-08-27T09:00:01+00:00",
    }
    artifact_digest = "4" * 64
    monkeypatch.setattr(
        runner.mainline,
        "load_completed_task_artifacts",
        lambda **kwargs: (
            {
                "artifact_type": "M4IsolatedDeliveryReceiptV11",
                "artifact_digest": artifact_digest,
                "body": body,
            },
        ),
    )

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, _params):
            self.statement = statement
            return self

        def fetchone(self):
            assert self.statement.startswith("SELECT")
            return (
                body["mail_kind"],
                body["content_digest"],
                body["recipient_set_digest"],
                body["state"],
                body["attempt_count"],
                artifact_digest,
            )

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self):
            return _Cursor()

    class _Repository:
        @staticmethod
        def connection_factory():
            return _Connection()

    repository = _Repository()
    assert runner._activation_facts(
        task_key=delivery.key(context),
        template=delivery,
        context=context,
        repository=repository,
    ) == (f"{delivery.key(context)}:SENT",)
    prereg = contract.task_template_by_name("preregistration")
    assert runner._activation_facts(
        task_key=prereg.key(context),
        template=prereg,
        context=context,
        repository=repository,
    ) == (contract.FREEZE_FACT,)


def test_incident_resolution_activation_advances_terminal_ledger(monkeypatch) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = _context()
    template = contract.task_template_by_name("incident_resolution")
    task_key = template.key(context)
    incident_id = context["incident_id"]
    monkeypatch.setattr(
        runner.mainline,
        "load_completed_task_artifacts",
        lambda **_kwargs: (
            {
                "artifact_type": "M4IsolatedIncidentResolutionV11",
                "artifact_digest": "1" * 64,
                "body": {"status": "RESOLVED", "incident_id": incident_id},
            },
            {
                "artifact_type": "M4IsolatedIncidentLedgerHeadV11",
                "artifact_digest": "2" * 64,
                "body": {
                    "transition_seq": 7,
                    "transition_kind": "RESOLVED",
                    "incident_id": incident_id,
                },
            },
        ),
    )
    assert runner._activation_facts(
        task_key=task_key,
        template=template,
        context=context,
        repository=object(),
    ) == (
        f"{task_key}:RESOLVED",
        "m4-isolated-24h-challenger-v11-incident-ledger-head-7:ADVANCED",
    )


def test_daily_and_predraw_absence_windows_are_fail_closed() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = _context()
    schedule = contract.schedule_for_issue(
        context["target_issue"], target_draw_date=context["target_draw_date"]
    )
    predraw_key = contract.task_template_by_name("predraw_delivery").key(context)
    start = schedule["predraw_send"]
    stop = datetime.combine(
        contract.require_draw_date(
            context["target_draw_date"], field="target_draw_date"
        ),
        contract.OFFICIAL_DRAW_TIME,
        contract.TIMEZONE,
    )
    assert runner._delivery_absent(
        now=start + timedelta(minutes=1),
        scheduled=start,
        stop_at=stop,
        delivery_task_key=predraw_key,
        facts=set(),
    )
    assert not runner._delivery_absent(
        now=start + timedelta(minutes=1),
        scheduled=start,
        stop_at=stop,
        delivery_task_key=predraw_key,
        facts={f"{predraw_key}:SENT"},
    )
    assert not runner._delivery_absent(
        now=stop,
        scheduled=start,
        stop_at=stop,
        delivery_task_key=predraw_key,
        facts=set(),
    )

    daily = start.replace(hour=9, minute=0)
    daily_context = {**context, "epoch_date": daily.strftime("%Y%m%d")}
    daily_key = contract.task_template_by_name("daily_delivery").key(daily_context)
    assert not runner._delivery_absent(
        now=daily + timedelta(seconds=59),
        scheduled=daily,
        stop_at=daily + timedelta(days=1),
        delivery_task_key=daily_key,
        facts=set(),
    )
    assert runner._delivery_absent(
        now=daily + timedelta(minutes=1),
        scheduled=daily,
        stop_at=daily + timedelta(days=1),
        delivery_task_key=daily_key,
        facts=set(),
    )


def test_resource_probe_reads_exact_user_manager_formal_p3_unit(monkeypatch) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    observed: list[list[str]] = []

    def fake_run(command, **kwargs):
        observed.append(list(command))
        assert kwargs == {
            "check": False,
            "capture_output": True,
            "text": True,
            "timeout": 2,
        }
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "LoadState=loaded\n"
                "ActiveState=inactive\n"
                "SubState=dead\n"
                "MainPID=0\n"
                "ControlPID=0\n"
            ),
        )

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    observation = runner._resource_observation()
    assert observed == [
        [
            "systemctl",
            "--user",
            "show",
            contract.FORMAL_P3_UNIT,
            "--property=LoadState,ActiveState,SubState,MainPID,ControlPID",
            "--no-pager",
        ]
    ]
    assert contract.formal_p3_activity_state(observation) == "QUIESCENT"


@pytest.mark.parametrize(
    "corruption",
    (None, "failed", "running_pid", "missing", "duplicate", "noninteger", "error"),
)
def test_daily_recovery_quiescence_requires_exact_dead_pidless_isolated_units(
    monkeypatch, corruption
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(list(command))
        assert kwargs == {
            "check": False,
            "capture_output": True,
            "text": True,
            "timeout": 5,
        }
        values = [
            "LoadState=loaded",
            "ActiveState=inactive",
            "SubState=dead",
        ]
        is_service = command[3].endswith(".service")
        if is_service:
            values.extend(("MainPID=0", "ControlPID=0"))
        if corruption == "failed":
            values[1:3] = ["ActiveState=failed", "SubState=failed"]
        elif corruption == "running_pid" and is_service:
            values[3] = "MainPID=123"
        elif corruption == "missing" and is_service:
            values.pop()
        elif corruption == "duplicate":
            values.append("LoadState=loaded")
        elif corruption == "noninteger" and is_service:
            values[4] = "ControlPID=not-an-integer"
        return SimpleNamespace(
            returncode=1 if corruption == "error" else 0,
            stdout="\n".join(values) + "\n",
        )

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    if corruption is None:
        observed = runner._isolated_units_quiescent()
        assert tuple(observed) == (
            "dehps-m4-isolated-24h-challenger-v11.timer",
            "dehps-m4-isolated-24h-challenger-v11.service",
        )
        assert observed == {
            "dehps-m4-isolated-24h-challenger-v11.timer": {
                "LoadState": "loaded",
                "ActiveState": "inactive",
                "SubState": "dead",
            },
            "dehps-m4-isolated-24h-challenger-v11.service": {
                "LoadState": "loaded",
                "ActiveState": "inactive",
                "SubState": "dead",
                "MainPID": 0,
                "ControlPID": 0,
            },
        }
        assert len(calls) == 2
        for command, unit in zip(calls, observed, strict=True):
            assert command == [
                "systemctl",
                "--user",
                "show",
                unit,
                "--property=LoadState,ActiveState,SubState,MainPID,ControlPID",
                "--no-pager",
            ]
    else:
        with pytest.raises(
            runner.IsolatedRunnerError,
            match="daily_recovery_isolated_units_not_quiescent",
        ):
            runner._isolated_units_quiescent()


def test_user_scope_recovery_governance_is_exact_and_keeps_mail_mandatory(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    repaired_source = "d" * 64
    repaired_commit = "e" * 40
    source_contract = {
        "artifact_digest": repaired_source,
        "governance_bindings": {
            "failed_state_recovery_gate_base_merged_commit": (
                runner.USER_SCOPE_FAILED_STATE_RECOVERY_BASE_COMMIT
            ),
            "failed_state_recovery_gate_engineering_approval_decision_id": (
                runner.USER_SCOPE_FAILED_STATE_ENGINEERING_DECISION_ID
            ),
            "failed_state_recovery_gate_engineering_execution_id": (
                runner.USER_SCOPE_FAILED_STATE_ENGINEERING_EXECUTION_ID
            ),
            "failed_state_recovery_gate_engineering_request_id": (
                runner.USER_SCOPE_FAILED_STATE_ENGINEERING_REQUEST_ID
            ),
            "failed_state_recovery_gate_engineering_request_key": (
                runner.USER_SCOPE_FAILED_STATE_ENGINEERING_REQUEST_KEY
            ),
            "failed_state_recovery_gate_engineering_request_payload_sha256": (
                runner.USER_SCOPE_FAILED_STATE_ENGINEERING_PAYLOAD_SHA256
            ),
            "sequence2_completion_gate_base_merged_commit": (
                runner.USER_SCOPE_COMPLETION_REPAIR_BASE_COMMIT
            ),
            "sequence2_completion_gate_engineering_approval_decision_id": (
                runner.USER_SCOPE_SEQUENCE2_ENGINEERING_DECISION_ID
            ),
            "sequence2_completion_gate_engineering_execution_id": (
                runner.USER_SCOPE_SEQUENCE2_ENGINEERING_EXECUTION_ID
            ),
            "sequence2_completion_gate_engineering_request_id": (
                runner.USER_SCOPE_SEQUENCE2_ENGINEERING_REQUEST_ID
            ),
            "sequence2_completion_gate_engineering_request_key": (
                runner.USER_SCOPE_SEQUENCE2_ENGINEERING_REQUEST_KEY
            ),
            "sequence2_completion_gate_engineering_request_payload_sha256": (
                runner.USER_SCOPE_SEQUENCE2_ENGINEERING_PAYLOAD_SHA256
            ),
            "sequence3_guard_recovery_base_merged_commit": (
                runner.USER_SCOPE_COMPLETION_REPAIR_BASE_COMMIT
            ),
            "sequence3_guard_recovery_engineering_approval_decision_id": (
                runner.USER_SCOPE_SEQUENCE3_ENGINEERING_DECISION_ID
            ),
            "sequence3_guard_recovery_engineering_execution_id": (
                runner.USER_SCOPE_SEQUENCE3_ENGINEERING_EXECUTION_ID
            ),
            "sequence3_guard_recovery_engineering_request_id": (
                runner.USER_SCOPE_SEQUENCE3_ENGINEERING_REQUEST_ID
            ),
            "sequence3_guard_recovery_engineering_request_key": (
                runner.USER_SCOPE_SEQUENCE3_ENGINEERING_REQUEST_KEY
            ),
            "sequence3_guard_recovery_engineering_request_payload_sha256": (
                runner.USER_SCOPE_SEQUENCE3_ENGINEERING_PAYLOAD_SHA256
            ),
            "second_terminal_guard_repair_base_merged_commit": (
                runner.USER_SCOPE_SECOND_GUARD_REPAIR_BASE_COMMIT
            ),
            "second_terminal_guard_repair_engineering_approval_decision_id": (
                runner.USER_SCOPE_SECOND_GUARD_ENGINEERING_DECISION_ID
            ),
            "second_terminal_guard_repair_engineering_execution_id": (
                runner.USER_SCOPE_SECOND_GUARD_ENGINEERING_EXECUTION_ID
            ),
            "second_terminal_guard_repair_engineering_request_id": (
                runner.USER_SCOPE_SECOND_GUARD_ENGINEERING_REQUEST_ID
            ),
            "second_terminal_guard_repair_engineering_request_key": (
                runner.USER_SCOPE_SECOND_GUARD_ENGINEERING_REQUEST_KEY
            ),
            "second_terminal_guard_repair_engineering_request_payload_sha256": (
                runner.USER_SCOPE_SECOND_GUARD_ENGINEERING_PAYLOAD_SHA256
            ),
            "running_projection_resume_repair_base_merged_commit": (
                runner.USER_SCOPE_RUNNING_RESUME_REPAIR_BASE_COMMIT
            ),
            "running_projection_resume_repair_engineering_approval_decision_id": (
                runner.USER_SCOPE_ENGINEERING_DECISION_ID
            ),
            "running_projection_resume_repair_engineering_execution_id": (
                runner.USER_SCOPE_ENGINEERING_EXECUTION_ID
            ),
            "running_projection_resume_repair_engineering_request_id": (
                runner.USER_SCOPE_ENGINEERING_REQUEST_ID
            ),
            "running_projection_resume_repair_engineering_request_key": (
                runner.USER_SCOPE_ENGINEERING_REQUEST_KEY
            ),
            "running_projection_resume_repair_engineering_request_payload_sha256": (
                runner.USER_SCOPE_ENGINEERING_PAYLOAD_SHA256
            ),
        },
    }
    engineering = SimpleNamespace(
        id=runner.USER_SCOPE_ENGINEERING_REQUEST_ID,
        request_type=runner.AgentRequestType.ENGINEERING_RUNTIME_FIX,
        status=runner.AgentRequestStatus.COMPLETED,
        metadata={"payload_sha256": runner.USER_SCOPE_ENGINEERING_PAYLOAD_SHA256},
    )
    engineering_approval = SimpleNamespace(
        id=runner.USER_SCOPE_ENGINEERING_DECISION_ID,
        decision_code="request_approved",
        previous_status="under_review",
        new_status="approved",
        decided_by_role=runner.AgentRole.REVIEWER,
    )
    engineering_execution = SimpleNamespace(
        id=runner.USER_SCOPE_ENGINEERING_EXECUTION_ID,
        status=runner.AgentExecutionStatus.COMPLETED,
        environment="development",
        executor_role=runner.AgentRole.ENGINEERING,
    )
    recovery = {
        "candidate_result_count": 0,
        "current_manifest_digest": runner.USER_SCOPE_FAILED_MANIFEST_DIGEST,
        "engineering_approval_decision_id": (runner.USER_SCOPE_ENGINEERING_DECISION_ID),
        "engineering_execution_id": runner.USER_SCOPE_ENGINEERING_EXECUTION_ID,
        "engineering_request_id": runner.USER_SCOPE_ENGINEERING_REQUEST_ID,
        "execution_attempt_count": contract.ATTEMPTS_PER_BATCH,
        "origin_commit": runner.USER_SCOPE_RESUME_ORIGIN_COMMIT,
        "origin_source_contract_digest": (
            runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST
        ),
        "registered_candidate_count": contract.ATTEMPTS_PER_BATCH,
        "repaired_source_contract_digest": repaired_source,
        "running_execution_id": runner.USER_SCOPE_RESUME_EXECUTION_ID,
        "running_task_digest": runner.USER_SCOPE_RESUME_TASK_DIGEST,
        "running_task_key": runner.USER_SCOPE_RESUME_TASK_KEY,
        "started_event_digest": runner.USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
        "failed_event_digest": runner.USER_SCOPE_GUARD_FAILED_EVENT_DIGEST,
        "prior_failed_event_digest": runner.USER_SCOPE_RESUME_FAILED_EVENT_DIGEST,
        "next_completion_sequence": 3,
        "predecessor_attestation_digest": (
            runner.USER_SCOPE_PREDECESSOR_ATTESTATION_DIGEST
        ),
    }
    payload = {
        "version": "m4-isolated-v11-sequence3-guard-recovery-v4",
        "commit": repaired_commit,
        "checks": {"user_systemd_running_batch_recovery": recovery},
        "mail_contract": {
            "mandatory_kinds": list(runner.USER_SCOPE_MANDATORY_MAIL_KINDS),
            "sent": (
                "Only SMTP final DATA250 plus append-only exactly-once "
                "receipt/artifact/replay projects SENT"
            ),
        },
        "resource_contract": {
            "continuous_24h": True,
            "p3_mutation": False,
            "p3_preempts": True,
            "p4_p5_p6_or_promotion": False,
            "workers_max": contract.WORKER_COUNT,
        },
        "ordered_operations": [
            "resume-p3-user-scope-running-batch",
            "recover-user-systemd-post-batch",
        ],
    }
    payload_sha = hashlib.sha256(
        contract.canonical_json(payload).encode("utf-8")
    ).hexdigest()
    operator = SimpleNamespace(
        id=746,
        parent_request_id=runner.USER_SCOPE_ENGINEERING_REQUEST_ID,
        request_type=runner.AgentRequestType.OPERATOR_RELEASE,
        status=runner.AgentRequestStatus.EXECUTING,
        payload=payload,
        metadata={"payload_sha256": payload_sha},
    )
    operator_approval = SimpleNamespace(
        id=3160,
        decision_code="request_approved",
        previous_status="under_review",
        new_status="approved",
        decided_by_role=runner.AgentRole.REVIEWER,
    )
    operator_execution = SimpleNamespace(
        id=601,
        status=runner.AgentExecutionStatus.RUNNING,
        environment="production",
        executor_role=runner.AgentRole.OPERATOR,
    )

    class _Repository:
        def get_request(self, key):
            return (
                engineering
                if key == runner.USER_SCOPE_ENGINEERING_REQUEST_KEY
                else operator
            )

        def list_decisions(self, key):
            return (
                [engineering_approval]
                if key == runner.USER_SCOPE_ENGINEERING_REQUEST_KEY
                else [operator_approval]
            )

        def list_execution_metadata(self, key):
            return (
                [engineering_execution]
                if key == runner.USER_SCOPE_ENGINEERING_REQUEST_KEY
                else [operator_execution]
            )

    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_REQUEST_KEY", "operator")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_DECISION_ID", "3160")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_EXECUTION_ID", "601")
    result = runner.validate_user_scope_recovery_governance(
        repository=_Repository(),
        source_contract=source_contract,
        repaired_source_digest=repaired_source,
        git_commit=repaired_commit,
        phase="resume",
    )
    assert result["operator_payload_sha256"] == payload_sha
    operator.payload = {
        **payload,
        "mail_contract": {
            **payload["mail_contract"],
            "mandatory_kinds": ["PREDRAW_TOP100"],
        },
    }
    with pytest.raises(runner.IsolatedRunnerError, match="operator_scope"):
        runner.validate_user_scope_recovery_governance(
            repository=_Repository(),
            source_contract=source_contract,
            repaired_source_digest=repaired_source,
            git_commit=repaired_commit,
            phase="resume",
        )


def test_user_scope_resume_surface_is_single_task_and_attestation_is_deterministic() -> (
    None
):
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    source = inspect.getsource(runner.resume_p3_user_scope_running_batch)
    tree = ast.parse(source)
    run_once_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run_once"
    ]
    assert len(run_once_calls) == 1
    assert "cycle(" not in source
    assert "_roll_forward(" not in source
    assert "send_external_once" not in source
    governance = {
        "phase": "resume",
        "engineering_request_id": runner.USER_SCOPE_ENGINEERING_REQUEST_ID,
        "engineering_decision_id": runner.USER_SCOPE_ENGINEERING_DECISION_ID,
        "engineering_execution_id": runner.USER_SCOPE_ENGINEERING_EXECUTION_ID,
        "operator_request_id": 746,
        "operator_decision_id": 3160,
        "operator_execution_id": 601,
        "operator_payload_sha256": "f" * 64,
    }
    first_path, first = runner._user_scope_runtime_attestation(
        repaired_source_digest="d" * 64,
        repaired_git_commit="e" * 40,
        governance=governance,
        predecessor_attestation_digest=(
            runner.USER_SCOPE_PREDECESSOR_ATTESTATION_DIGEST
        ),
    )
    second_path, second = runner._user_scope_runtime_attestation(
        repaired_source_digest="d" * 64,
        repaired_git_commit="e" * 40,
        governance=governance,
        predecessor_attestation_digest=(
            runner.USER_SCOPE_PREDECESSOR_ATTESTATION_DIGEST
        ),
    )
    assert first_path == second_path
    assert first == second
    assert first["scientific_contract_changed"] is False
    assert first["formal_p3_mutated"] is False
    assert first["p4_p5_p6_or_promotion_triggered"] is False
    assert first["parent_digests"][-1] == "f" * 64
    assert (
        first["parent_digests"][-2] == runner.USER_SCOPE_PREDECESSOR_ATTESTATION_DIGEST
    )


def test_user_scope_predecessor_attestation_is_exact_and_immutable(
    monkeypatch, tmp_path
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    foundation = {
        "schema_version": "dehps-m4-isolated-v11-user-systemd-runtime-migration.v1",
        "artifact_type": "m4_isolated_v11_user_systemd_runtime_migration",
        "artifact_digest": runner.USER_SCOPE_FOUNDATION_ATTESTATION_DIGEST,
        "scientific_contract_changed": False,
        "workload_definition_changed": False,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
        "task_key": runner.USER_SCOPE_RESUME_TASK_KEY,
        "task_digest": runner.USER_SCOPE_RESUME_TASK_DIGEST,
        "execution_id": runner.USER_SCOPE_RESUME_EXECUTION_ID,
        "started_event_digest": runner.USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
        "origin_git_commit": runner.USER_SCOPE_RESUME_ORIGIN_COMMIT,
        "runtime_git_commit": "dea22d7ca1cc876d278b1d18e4e68801a41291fd",
        "origin_source_contract_digest": runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
        "runtime_source_contract_digest": (
            "f6d043e22862c1ffd850dc5932a7be3c6f2dbaab4e9cf1d57db8a3f8158157ef"
        ),
        "repair": "SYSTEMD_SYSTEM_MANAGER_TO_EXACT_USER_MANAGER_QUERY",
        "registered_candidates": contract.ATTEMPTS_PER_BATCH,
        "execution_attempts_before_resume": 0,
        "candidate_results_before_resume": 0,
        "mail_delivery_before_resume": 0,
        "governance": {
            "phase": "resume",
            "engineering_request_id": 745,
            "engineering_decision_id": 3157,
            "engineering_execution_id": 600,
            "operator_request_id": 746,
            "operator_decision_id": 3162,
            "operator_execution_id": 601,
            "operator_payload_sha256": (
                "019bfa1769bd0359bc94b4b4d023c13ec3d02ce9a7a93c91a9bca86b5b2d876d"
            ),
        },
        "parent_digests": [
            runner.USER_SCOPE_RESUME_TASK_DIGEST,
            runner.USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
            runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
            "f6d043e22862c1ffd850dc5932a7be3c6f2dbaab4e9cf1d57db8a3f8158157ef",
            "019bfa1769bd0359bc94b4b4d023c13ec3d02ce9a7a93c91a9bca86b5b2d876d",
        ],
    }
    latest = {
        "schema_version": (
            "dehps-m4-isolated-v11-same-key-event-isolation-runtime-migration.v2"
        ),
        "artifact_type": "m4_isolated_v11_user_systemd_runtime_migration",
        "artifact_digest": runner.USER_SCOPE_SEQUENCE2_ATTESTATION_DIGEST,
        "scientific_contract_changed": False,
        "workload_definition_changed": False,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
        "task_key": runner.USER_SCOPE_RESUME_TASK_KEY,
        "task_digest": runner.USER_SCOPE_RESUME_TASK_DIGEST,
        "execution_id": runner.USER_SCOPE_RESUME_EXECUTION_ID,
        "started_event_digest": runner.USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
        "origin_git_commit": runner.USER_SCOPE_RESUME_ORIGIN_COMMIT,
        "runtime_git_commit": runner.USER_SCOPE_EVENT_ISOLATION_RUNTIME_COMMIT,
        "origin_source_contract_digest": runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
        "runtime_source_contract_digest": (
            "eaebe90afc17a3a226e08cb40891b38705eb0e48194d3ea656654210c69356ed"
        ),
        "repair": "EXACT_SAME_KEY_EVENT_VIEW_AFTER_USER_SYSTEMD_GUARD_REPAIR",
        "predecessor_attestation_digest": (
            runner.USER_SCOPE_FOUNDATION_ATTESTATION_DIGEST
        ),
        "registered_candidates": contract.ATTEMPTS_PER_BATCH,
        "execution_attempts_before_resume": 0,
        "candidate_results_before_resume": 0,
        "mail_delivery_before_resume": 0,
        "governance": {
            "phase": "resume",
            "engineering_request_id": 747,
            "engineering_decision_id": 3167,
            "engineering_execution_id": 602,
            "operator_request_id": 748,
            "operator_decision_id": 3172,
            "operator_execution_id": 603,
            "operator_payload_sha256": (
                "4a44a44bb4805bb80d9a026dd7a1556f2cbf9b98498095d13a8acfdc98186c8f"
            ),
        },
        "parent_digests": [
            runner.USER_SCOPE_RESUME_TASK_DIGEST,
            runner.USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
            runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
            "eaebe90afc17a3a226e08cb40891b38705eb0e48194d3ea656654210c69356ed",
            runner.USER_SCOPE_FOUNDATION_ATTESTATION_DIGEST,
            "4a44a44bb4805bb80d9a026dd7a1556f2cbf9b98498095d13a8acfdc98186c8f",
        ],
    }
    guard = {
        "schema_version": (
            "dehps-m4-isolated-v11-utc-registration-failed-event-runtime-migration.v3"
        ),
        "artifact_type": "m4_isolated_v11_user_systemd_runtime_migration",
        "artifact_digest": runner.USER_SCOPE_PREDECESSOR_ATTESTATION_DIGEST,
        "scientific_contract_changed": False,
        "workload_definition_changed": False,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
        "task_key": runner.USER_SCOPE_RESUME_TASK_KEY,
        "task_digest": runner.USER_SCOPE_RESUME_TASK_DIGEST,
        "execution_id": runner.USER_SCOPE_RESUME_EXECUTION_ID,
        "started_event_digest": runner.USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
        "failed_event_digest": runner.USER_SCOPE_RESUME_FAILED_EVENT_DIGEST,
        "origin_git_commit": runner.USER_SCOPE_RESUME_ORIGIN_COMMIT,
        "runtime_git_commit": "c30db93efb428198b4d7c0c0548feefbd315ba59",
        "origin_source_contract_digest": runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
        "runtime_source_contract_digest": (
            "7ef55ac4b726e39d1cfe5a0a6f3382d435c5d123c10618b4aee91a51454c1780"
        ),
        "repair": "UTC_REGISTRATION_RESUME_AND_EXACT_FAILED_EVENT_RECOVERY",
        "predecessor_attestation_digest": runner.USER_SCOPE_SEQUENCE2_ATTESTATION_DIGEST,
        "registered_candidates": contract.ATTEMPTS_PER_BATCH,
        "execution_attempts_before_resume": 0,
        "candidate_results_before_resume": 0,
        "mail_delivery_before_resume": 0,
        "governance": {
            "phase": "resume",
            "engineering_request_id": 750,
            "engineering_decision_id": 3182,
            "engineering_execution_id": 605,
            "operator_request_id": 751,
            "operator_decision_id": 3187,
            "operator_execution_id": 606,
            "operator_payload_sha256": (
                "9b533534e88b9b0476f9becd02456863cd70e8385c19053e19f023c2e5e123a5"
            ),
        },
        "parent_digests": [
            runner.USER_SCOPE_RESUME_TASK_DIGEST,
            runner.USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
            runner.USER_SCOPE_RESUME_FAILED_EVENT_DIGEST,
            runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
            "7ef55ac4b726e39d1cfe5a0a6f3382d435c5d123c10618b4aee91a51454c1780",
            runner.USER_SCOPE_SEQUENCE2_ATTESTATION_DIGEST,
            "9b533534e88b9b0476f9becd02456863cd70e8385c19053e19f023c2e5e123a5",
        ],
    }
    for payload in (foundation, latest, guard):
        path = (
            tmp_path
            / "runtime/research-os/mainline/tasks"
            / runner.USER_SCOPE_RESUME_TASK_KEY
            / runner.USER_SCOPE_RESUME_EXECUTION_ID
            / "runtime-migrations"
            / payload["artifact_digest"]
            / "user-systemd-runtime-migration.json"
        )
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(runner, "ROOT_DIR", tmp_path)
    assert runner._load_user_scope_predecessor_attestation() == guard
    guard["governance"]["operator_execution_id"] = 999
    path.write_text(json.dumps(guard), encoding="utf-8")
    with pytest.raises(runner.IsolatedRunnerError, match="attestation_changed"):
        runner._load_user_scope_predecessor_attestation()


def _user_scope_event_dict(record: MainlineExecutionEvent) -> dict[str, object]:
    return {
        "event_digest": record.artifact_digest,
        "execution_id": record.execution_id,
        "control_plane_key": record.control_plane_key,
        "manifest_digest": record.manifest_digest,
        "task_key": record.task_key,
        "task_digest": record.task_digest,
        "capability": record.capability,
        "event_type": record.event_type,
        "sequence": record.sequence,
        "recorded_at": record.recorded_at,
        "payload": list(record.payload),
    }


def _user_scope_events(runner, *, completed: bool) -> tuple[dict[str, object], ...]:
    shared = {
        "control_plane_key": contract.CONTROL_PLANE_KEY,
        "task_key": runner.USER_SCOPE_RESUME_TASK_KEY,
        "capability": runner.USER_SCOPE_RESUME_CAPABILITY,
    }
    records = [
        MainlineExecutionEvent(
            **shared,
            execution_id=runner.USER_SCOPE_HISTORICAL_EXECUTION_ID,
            manifest_digest=runner.USER_SCOPE_HISTORICAL_MANIFEST_DIGEST,
            task_digest=runner.USER_SCOPE_HISTORICAL_TASK_DIGEST,
            event_type="started",
            sequence=0,
            recorded_at=runner.USER_SCOPE_HISTORICAL_STARTED_AT,
            payload=(
                (
                    "input_artifact_digests",
                    [runner.USER_SCOPE_HISTORICAL_SOURCE_DIGEST],
                ),
                ("git_commit", runner.USER_SCOPE_HISTORICAL_COMMIT),
            ),
        ),
        MainlineExecutionEvent(
            **shared,
            execution_id=runner.USER_SCOPE_HISTORICAL_EXECUTION_ID,
            manifest_digest=runner.USER_SCOPE_HISTORICAL_MANIFEST_DIGEST,
            task_digest=runner.USER_SCOPE_HISTORICAL_TASK_DIGEST,
            event_type="failed",
            sequence=1,
            recorded_at=runner.USER_SCOPE_HISTORICAL_FAILED_AT,
            payload=(
                ("error", "atomic_registration_artifact_content_changed"),
                ("git_commit", runner.USER_SCOPE_HISTORICAL_COMMIT),
            ),
        ),
        MainlineExecutionEvent(
            **shared,
            execution_id=runner.USER_SCOPE_RESUME_EXECUTION_ID,
            manifest_digest=runner.USER_SCOPE_RESUME_MANIFEST_DIGEST,
            task_digest=runner.USER_SCOPE_RESUME_TASK_DIGEST,
            event_type="started",
            sequence=0,
            recorded_at=runner.USER_SCOPE_RESUME_STARTED_AT,
            payload=(
                (
                    "input_artifact_digests",
                    [runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST],
                ),
                ("git_commit", runner.USER_SCOPE_RESUME_ORIGIN_COMMIT),
            ),
        ),
        MainlineExecutionEvent(
            **shared,
            execution_id=runner.USER_SCOPE_RESUME_EXECUTION_ID,
            manifest_digest=runner.USER_SCOPE_RESUME_MANIFEST_DIGEST,
            task_digest=runner.USER_SCOPE_RESUME_TASK_DIGEST,
            event_type="failed",
            sequence=1,
            recorded_at=runner.USER_SCOPE_RESUME_FAILED_AT,
            payload=(
                ("error", "atomic_registration_resume_changed"),
                ("git_commit", runner.USER_SCOPE_RESUME_ORIGIN_COMMIT),
            ),
        ),
        MainlineExecutionEvent(
            **shared,
            execution_id=runner.USER_SCOPE_RESUME_EXECUTION_ID,
            manifest_digest=runner.USER_SCOPE_RESUME_MANIFEST_DIGEST,
            task_digest=runner.USER_SCOPE_RESUME_TASK_DIGEST,
            event_type="failed",
            sequence=2,
            recorded_at=runner.USER_SCOPE_GUARD_FAILED_AT,
            payload=(
                (
                    "error",
                    "M4-v2 atomic successor does not permit failed-execution recovery",
                ),
                ("git_commit", runner.USER_SCOPE_RESUME_ORIGIN_COMMIT),
            ),
        ),
    ]
    assert (
        records[0].artifact_digest == runner.USER_SCOPE_HISTORICAL_STARTED_EVENT_DIGEST
    )
    assert (
        records[1].artifact_digest == runner.USER_SCOPE_HISTORICAL_FAILED_EVENT_DIGEST
    )
    assert records[2].artifact_digest == runner.USER_SCOPE_RESUME_STARTED_EVENT_DIGEST
    assert records[3].artifact_digest == runner.USER_SCOPE_RESUME_FAILED_EVENT_DIGEST
    assert records[4].artifact_digest == runner.USER_SCOPE_GUARD_FAILED_EVENT_DIGEST
    if completed:
        records.append(
            MainlineExecutionEvent(
                **shared,
                execution_id=runner.USER_SCOPE_RESUME_EXECUTION_ID,
                manifest_digest=runner.USER_SCOPE_RESUME_MANIFEST_DIGEST,
                task_digest=runner.USER_SCOPE_RESUME_TASK_DIGEST,
                event_type="completed",
                sequence=3,
                recorded_at="2026-08-28T05:00:00+08:00",
                payload=tuple(
                    sorted(
                        {
                            "execution_artifact_digest": "a" * 64,
                            "execution_artifact_path": "runtime/execution.json",
                            "registered_artifact_count": 19,
                            "publication_batch_digest": "b" * 64,
                            "git_commit": runner.USER_SCOPE_RESUME_ORIGIN_COMMIT,
                        }.items()
                    )
                ),
            )
        )
    return tuple(_user_scope_event_dict(record) for record in records)


@pytest.mark.parametrize(
    ("counts", "expected"),
    (
        (
            {
                "candidates": contract.ATTEMPTS_PER_BATCH,
                "terminal": contract.ATTEMPTS_PER_BATCH,
                "results": contract.ATTEMPTS_PER_BATCH,
                "attempts": contract.ATTEMPTS_PER_BATCH,
                "committed_attempts": contract.ATTEMPTS_PER_BATCH,
            },
            True,
        ),
        (
            {
                "candidates": contract.ATTEMPTS_PER_BATCH,
                "terminal": contract.ATTEMPTS_PER_BATCH,
                "results": contract.ATTEMPTS_PER_BATCH - 1,
                "attempts": contract.ATTEMPTS_PER_BATCH,
                "committed_attempts": contract.ATTEMPTS_PER_BATCH,
            },
            False,
        ),
        (None, False),
    ),
)
def test_search_batch_mirror_complete_decodes_exact_dict_row(counts, expected) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")

    class _Cursor:
        statement = ""

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params):
            self.statement = statement
            if "SELECT registration_seq" in statement:
                assert params == (0,)
            else:
                assert params == (7,) * 5
                for alias in (
                    "AS candidates",
                    "AS terminal",
                    "AS results",
                    "AS attempts",
                    "AS committed_attempts",
                ):
                    assert alias in statement
            return self

        def fetchone(self):
            if "SELECT registration_seq" in self.statement:
                return {"registration_seq": 7}
            return counts

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def cursor(*, row_factory):
            assert row_factory is runner.dict_row
            return _Cursor()

    repository = SimpleNamespace(connection_factory=lambda: _Connection())
    assert (
        runner._search_batch_mirror_complete(
            repository=repository,
            context={"batch_seq": "000000000000"},
        )
        is expected
    )


@pytest.mark.parametrize(
    ("counts", "error"),
    (
        ({"count": contract.ATTEMPTS_PER_BATCH}, "count_row_changed"),
        (
            {
                "candidates": "count",
                "terminal": contract.ATTEMPTS_PER_BATCH,
                "results": contract.ATTEMPTS_PER_BATCH,
                "attempts": contract.ATTEMPTS_PER_BATCH,
                "committed_attempts": contract.ATTEMPTS_PER_BATCH,
            },
            "count_value_changed",
        ),
    ),
)
def test_search_batch_mirror_complete_fails_closed_on_dict_row_drift(
    counts, error
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")

    class _Cursor:
        statement = ""

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, _params):
            self.statement = statement
            return self

        def fetchone(self):
            if "SELECT registration_seq" in self.statement:
                return {"registration_seq": 7}
            return counts

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def cursor(*, row_factory):
            assert row_factory is runner.dict_row
            return _Cursor()

    repository = SimpleNamespace(connection_factory=lambda: _Connection())
    with pytest.raises(runner.IsolatedRunnerError, match=error):
        runner._search_batch_mirror_complete(
            repository=repository,
            context={"batch_seq": "000000000000"},
        )


@pytest.mark.parametrize(
    ("manifest_digest", "target_status"),
    (
        ("FAILED", TaskStatus.FAILED),
        ("RUNNING", TaskStatus.RUNNING),
    ),
)
def test_user_scope_live_preflight_distinguishes_failed_and_running_manifests(
    monkeypatch, manifest_digest, target_status
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    manifest_digest = {
        "FAILED": runner.USER_SCOPE_FAILED_MANIFEST_DIGEST,
        "RUNNING": runner.USER_SCOPE_RESUME_MANIFEST_DIGEST,
    }[manifest_digest]
    context = contract.render_context(
        source_max_issue="2026099",
        source_max_draw_date="2026-08-27",
        target_issue="2026100",
        target_draw_date="2026-08-30",
    )
    target = SimpleNamespace(
        task_key=runner.USER_SCOPE_RESUME_TASK_KEY,
        artifact_digest=runner.USER_SCOPE_RESUME_TASK_DIGEST,
        requested_capability=runner.USER_SCOPE_RESUME_CAPABILITY,
        metric_contract=json.dumps(
            {
                "render_context": context,
                "source_contract_digest": (
                    runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST
                ),
            }
        ),
    )
    completed_states = [
        SimpleNamespace(declared_status=TaskStatus.COMPLETED) for _ in range(22)
    ]
    draft_states = [SimpleNamespace(declared_status=TaskStatus.DRAFT) for _ in range(4)]
    target_state = SimpleNamespace(
        declared_status=target_status,
        completion_classification=CompletionClassification.INTEGRATED,
        superseded_by_task_digest=None,
    )
    manifest = SimpleNamespace(
        artifact_digest=manifest_digest,
        tasks=[target]
        + [
            SimpleNamespace(task_key=f"other-{index}", artifact_digest=f"{index:064x}")
            for index in range(26)
        ],
        task_states=(*completed_states, *draft_states, target_state),
        task_state_by_digest={target.artifact_digest: target_state},
        facts=SimpleNamespace(artifacts=frozenset()),
    )

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement):
            self.statement = statement
            return self

        def fetchall(self):
            if "registration_batches" in self.statement:
                return [
                    (
                        0,
                        0,
                        "2026100",
                        runner.USER_SCOPE_RESUME_EXECUTION_ID,
                        0,
                        contract.ATTEMPTS_PER_BATCH,
                        contract.ATTEMPTS_PER_BATCH,
                    )
                ]
            return [
                (
                    0,
                    "TERMINAL",
                    runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
                    contract.ATTEMPTS_PER_BATCH,
                )
            ]

        def fetchone(self):
            if "multiplicity_head" in self.statement:
                return (0, contract.ATTEMPTS_PER_BATCH)
            if "worker_started_at IS NOT NULL" in self.statement:
                return (
                    contract.ATTEMPTS_PER_BATCH,
                    contract.ATTEMPTS_PER_BATCH,
                    contract.ATTEMPTS_PER_BATCH,
                    contract.ATTEMPTS_PER_BATCH,
                    contract.ATTEMPTS_PER_BATCH,
                    contract.ATTEMPTS_PER_BATCH,
                    0,
                    0,
                )
            if "execution_attempts" in self.statement:
                return (contract.ATTEMPTS_PER_BATCH,)
            return (0,)

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def cursor():
            return _Cursor()

    repository = SimpleNamespace(
        load_manifest=lambda **_kwargs: manifest,
        list_mainline_execution_events=lambda **_kwargs: _user_scope_events(
            runner, completed=False
        ),
        list_mainline_artifacts=lambda **_kwargs: (),
        connection_factory=lambda: _Connection(),
    )
    monkeypatch.setattr(runner, "_p3_source_identity", lambda: ("p3", "unchanged"))

    verified_manifest, verified_context = runner._validate_user_scope_resume_live_state(
        repository=repository
    )

    assert verified_manifest is manifest
    assert verified_context == context
    assert runner.USER_SCOPE_FAILED_MANIFEST_DIGEST != (
        runner.USER_SCOPE_RESUME_MANIFEST_DIGEST
    )
    manifest.artifact_digest = "0" * 64
    with pytest.raises(runner.IsolatedRunnerError, match="manifest_changed"):
        runner._validate_user_scope_resume_live_state(repository=repository)


def test_user_scope_event_view_is_exact_filtered_non_reentrant_and_closes(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    events = _user_scope_events(runner, completed=True)
    monkeypatch.setattr(
        runner.PostgresResearchOSRepository,
        "list_mainline_execution_events",
        lambda _self, **_kwargs: events,
    )
    repository = object.__new__(runner.IsolatedChallengerRepository)
    repository._user_scope_resume_event_gate = False
    assert (
        repository.list_mainline_execution_events(
            control_plane_key=contract.CONTROL_PLANE_KEY,
            task_key=runner.USER_SCOPE_RESUME_TASK_KEY,
        )
        == events
    )
    with repository.user_scope_resume_event_view():
        current = repository.list_mainline_execution_events(
            control_plane_key=contract.CONTROL_PLANE_KEY,
            execution_id=runner.USER_SCOPE_RESUME_EXECUTION_ID,
        )
        assert [item["event_type"] for item in current] == [
            "started",
            "failed",
            "failed",
            "completed",
        ]
        assert all(
            item["task_digest"] == runner.USER_SCOPE_RESUME_TASK_DIGEST
            for item in current
        )
        with (
            pytest.raises(runner.IsolatedRunnerError, match="reentrant"),
            repository.user_scope_resume_event_view(),
        ):
            pass
    assert repository._user_scope_resume_event_gate is False
    assert (
        repository.list_mainline_execution_events(
            control_plane_key=contract.CONTROL_PLANE_KEY,
            task_key=runner.USER_SCOPE_RESUME_TASK_KEY,
        )
        == events
    )


def test_failed_to_running_transition_requires_exact_two_phase_user_scope_gate(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = _context()
    payload, _ = runner.builder.build_bootstrap_manifest(
        context=context,
        source_digest="f" * 64,
        operator_configuration_authorized=True,
    )
    base = ControlPlaneManifest.from_dict(payload)
    task = base.tasks[0]
    current_states = list(base.task_states)
    current_states[0] = replace(
        current_states[0],
        declared_status=TaskStatus.FAILED,
        completion_classification=CompletionClassification.INTEGRATED,
    )
    current = replace(base, task_states=tuple(current_states))
    incoming_states = list(current.task_states)
    incoming_states[0] = replace(
        incoming_states[0],
        declared_status=TaskStatus.RUNNING,
        completion_classification=CompletionClassification.INTEGRATED,
    )
    incoming = replace(current, task_states=tuple(incoming_states))

    class _Cursor:
        def __init__(self):
            self.result = None

        def execute(self, statement, _params=None):
            self.result = (
                {"current_manifest_digest": current.artifact_digest}
                if "SELECT current_manifest_digest" in statement
                else {"manifest_json": current.to_dict(include_digest=True)}
            )
            return self

        def fetchone(self):
            return self.result

    repository = object.__new__(runner.IsolatedChallengerRepository)
    repository.context = dict(context)
    repository.source_digest = "f" * 64
    repository._fact_gate = None
    repository._definition_gate = None
    repository._bootstrap_rebind_gate = None
    repository._user_scope_resume_event_gate = False
    repository._user_scope_failed_transition_gate = None
    repository.load_manifest = lambda **_kwargs: current
    monkeypatch.setattr(
        runner, "USER_SCOPE_FAILED_MANIFEST_DIGEST", current.artifact_digest
    )
    monkeypatch.setattr(
        runner, "USER_SCOPE_RESUME_MANIFEST_DIGEST", incoming.artifact_digest
    )
    monkeypatch.setattr(runner, "USER_SCOPE_RESUME_TASK_KEY", task.task_key)
    monkeypatch.setattr(runner, "USER_SCOPE_RESUME_TASK_DIGEST", task.artifact_digest)
    monkeypatch.setattr(
        runner.PostgresResearchOSRepository,
        "_verify_mainline_completion_records",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(
        runner.ResearchOSValidationError,
        match="failed_recovery_transition_gate_changed",
    ):
        repository._verify_exact_transition(incoming)
    with repository.user_scope_resume_event_view():
        repository._verify_exact_transition(incoming)
        assert repository._user_scope_failed_transition_gate == {
            "router_consumed": True,
            "completion_consumed": False,
        }
        repository._verify_mainline_completion_records(
            _Cursor(),
            control_plane_key=contract.CONTROL_PLANE_KEY,
            manifest=incoming,
        )
        assert repository._user_scope_failed_transition_gate == {
            "router_consumed": True,
            "completion_consumed": True,
        }
        with pytest.raises(
            runner.ResearchOSValidationError,
            match="failed_recovery_transition_gate_changed",
        ):
            repository._verify_exact_transition(incoming)
    assert repository._user_scope_resume_event_gate is False
    assert repository._user_scope_failed_transition_gate is None


@pytest.mark.parametrize("mutation", ("missing", "duplicate", "changed", "extra"))
def test_user_scope_event_view_rejects_any_raw_event_set_drift_and_closes(
    monkeypatch, mutation
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    raw = list(_user_scope_events(runner, completed=False))
    if mutation == "missing":
        raw.pop(0)
    elif mutation == "duplicate":
        raw.append(dict(raw[0]))
    elif mutation == "changed":
        raw[0] = {**raw[0], "recorded_at": "2026-08-27T19:42:00+00:00"}
    else:
        extra = MainlineExecutionEvent(
            execution_id="c" * 64,
            control_plane_key=contract.CONTROL_PLANE_KEY,
            manifest_digest=runner.USER_SCOPE_RESUME_MANIFEST_DIGEST,
            task_key=runner.USER_SCOPE_RESUME_TASK_KEY,
            task_digest="d" * 64,
            capability=runner.USER_SCOPE_RESUME_CAPABILITY,
            event_type="started",
            sequence=0,
            recorded_at="2026-08-28T05:00:00+08:00",
            payload=(),
        )
        raw.append(_user_scope_event_dict(extra))
    events = tuple(raw)
    monkeypatch.setattr(
        runner.PostgresResearchOSRepository,
        "list_mainline_execution_events",
        lambda _self, **_kwargs: events,
    )
    repository = object.__new__(runner.IsolatedChallengerRepository)
    repository._user_scope_resume_event_gate = False
    with (
        pytest.raises((runner.IsolatedRunnerError, ValueError)),
        repository.user_scope_resume_event_view(),
    ):
        repository.list_mainline_execution_events(
            control_plane_key=contract.CONTROL_PLANE_KEY,
            task_key=runner.USER_SCOPE_RESUME_TASK_KEY,
        )
    assert repository._user_scope_resume_event_gate is False


def test_completed_activation_recovery_replays_without_workload(monkeypatch) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = _context()
    payload, _ = runner.builder.build_manifest(
        context=context,
        source_digest="a" * 64,
        operator_configuration_authorized=True,
        simulation_events=True,
    )
    original = ControlPlaneManifest.from_dict(payload)
    task = next(
        item
        for item in original.tasks
        if item.task_key
        == contract.task_template_by_name("preregistration").key(context)
    )
    manifest = type("Manifest", (), {})()
    manifest.tasks = [task]
    manifest.facts = type("Facts", (), {"artifacts": frozenset()})()
    manifest.task_state_by_digest = {
        task.artifact_digest: type(
            "State", (), {"declared_status": TaskStatus.COMPLETED}
        )()
    }

    imported: list[tuple[str, ...]] = []

    class _Repository:
        @staticmethod
        def load_manifest(*, control_plane_key):
            assert control_plane_key == contract.CONTROL_PLANE_KEY
            return manifest

        @staticmethod
        def list_mainline_execution_events(**_kwargs):
            return [{"event_type": "completed", "execution_id": "b" * 64}]

        def import_verified_facts(self, values):
            imported.append(tuple(values))

    calls: list[tuple[str, str]] = []

    class _Supervisor:
        def __init__(self, **_kwargs):
            pass

        def replay(self, *, task_key, execution_id):
            calls.append((task_key, execution_id))
            return {
                "status": "REPLAY_VERIFIED",
                "same_execution_identity": True,
                "same_artifact_identity": True,
                "same_artifact_content": True,
                "all_registrations_and_parent_chains_exact": True,
                "manual_input_assembly": False,
                "dispatch_performed": False,
            }

    repository = _Repository()
    monkeypatch.setattr(runner.mainline, "IsolatedChallengerSupervisor", _Supervisor)
    monkeypatch.setattr(runner, "_activation_present", lambda **_kwargs: False)
    monkeypatch.setattr(
        runner,
        "_activation_facts",
        lambda **_kwargs: (contract.FREEZE_FACT,),
    )
    recovered = runner._recover_completed_activations(
        repository=repository, source_digest="a" * 64
    )
    assert calls == [(task.task_key, "b" * 64)]
    assert imported == [(contract.FREEZE_FACT,)]
    assert recovered[0]["execution_id"] == "b" * 64


def test_single_and_18_worker_equivalence_binds_all_downstream_identities() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    configurations = runner.search.base_configurations(
        snapshot_digest="1" * 64,
        source_contract_digest="2" * 64,
    )
    jobs = runner.search.plan_batch(configurations, cursor=0)
    single = runner.search.execute_jobs(jobs, worker_count=1)
    parallel = runner.search.execute_jobs(jobs, worker_count=contract.WORKER_COUNT)
    single_bundle = runner._parallel_equivalence_bundle(single, target_issue="2026101")
    parallel_bundle = runner._parallel_equivalence_bundle(
        parallel, target_issue="2026101"
    )
    assert single_bundle == parallel_bundle
    decoded = __import__("json").loads(single_bundle)
    assert len(decoded["candidate_results"]) == contract.ATTEMPTS_PER_BATCH
    assert len(decoded["candidate_order"]) == contract.ATTEMPTS_PER_BATCH
    assert len(decoded["top100"]) == contract.PORTFOLIO_SIZE
    assert all(
        len(decoded[field]) == 64
        for field in ("checkpoint_digest", "artifact_digest", "replay_digest")
    )


def test_service_outer_bound_keeps_mail_windows_recoverable() -> None:
    service = (
        ROOT / "infra/systemd/dehps-m4-isolated-24h-challenger-v11.service"
    ).read_text(encoding="utf-8")
    migration = (
        ROOT / "infra/postgres/migrations/003_m4_isolated_24h_challenger_v11.sql"
    ).read_text(encoding="utf-8")
    assert "TimeoutStartSec=1h45min" in service
    assert "CPUQuota=1800%" in service
    assert "MemoryMax=24G" in service
    assert (
        "EnvironmentFile=/home/ark/.config/dehps/m4-isolated-24h-challenger-v11.env"
    ) in service
    assert "/etc/dehps/" not in service
    assert "CREATE TRIGGER delivery_ledger_append_only" in migration
    assert "CREATE TRIGGER schema_identity_append_only" in migration
    assert "CREATE TRIGGER registered_inputs_append_only" in migration


def test_database_schema_attestation_is_exact_and_idempotent() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    commit = "a" * 40
    expected = (
        contract.DATABASE_SCHEMA_VERSION,
        contract.CONTRACT_DIGEST,
        commit,
    )

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params=None):
            if statement.startswith("INSERT"):
                assert params == expected
            else:
                assert statement.startswith("SELECT")
                assert params is None
            return self

        @staticmethod
        def fetchone():
            return expected

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def cursor():
            return _Cursor()

    class _Repository:
        @staticmethod
        def connection_factory():
            return _Connection()

    assert runner._attest_database_schema(
        repository=_Repository(), git_commit=commit
    ) == {
        "schema_version": contract.DATABASE_SCHEMA_VERSION,
        "contract_digest": contract.CONTRACT_DIGEST,
        "installed_git_commit": commit,
    }


def test_repository_helper_does_not_shadow_base_task_validator() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    namespace = runner.IsolatedChallengerRepository.__dict__
    assert "_verify_task_definition" not in namespace
    assert "_verify_isolated_task_definition" in namespace


@pytest.mark.parametrize("row_count", [1, 2])
def test_latest_history_identity_requires_one_exact_issue_date(
    monkeypatch, row_count: int
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    rows = [("2026099", date(2026, 8, 27))] * row_count

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement):
            assert "WHERE issue=(SELECT MAX(issue) FROM ssq_history)" in statement
            return self

        def fetchall(self):
            return rows

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def cursor():
            return _Cursor()

    class _Repository:
        @staticmethod
        def connection_factory():
            return _Connection()

    monkeypatch.setattr(runner, "PostgresResearchOSRepository", _Repository)
    if row_count == 1:
        assert runner._latest_history_identity() == ("2026099", "2026-08-27")
    else:
        with pytest.raises(runner.IsolatedRunnerError, match="latest_identity_changed"):
            runner._latest_history_identity()


@pytest.mark.parametrize("returncode", [0, 1])
def test_database_schema_attestation_accepts_only_ancestor_repair(
    monkeypatch, returncode: int
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    installed = "a" * 40
    current = "b" * 40
    expected_insert = (
        contract.DATABASE_SCHEMA_VERSION,
        contract.CONTRACT_DIGEST,
        current,
    )

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params=None):
            if statement.startswith("INSERT"):
                assert params == expected_insert
            else:
                assert statement.startswith("SELECT")
                assert params is None
            return self

        @staticmethod
        def fetchone():
            return (
                contract.DATABASE_SCHEMA_VERSION,
                contract.CONTRACT_DIGEST,
                installed,
            )

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def cursor():
            return _Cursor()

    class _Repository:
        @staticmethod
        def connection_factory():
            return _Connection()

    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(list(command))
        assert kwargs == {
            "cwd": runner.ROOT_DIR,
            "check": False,
            "capture_output": True,
            "text": True,
        }
        return SimpleNamespace(returncode=returncode)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    if returncode == 0:
        assert (
            runner._attest_database_schema(
                repository=_Repository(), git_commit=current
            )["installed_git_commit"]
            == installed
        )
    else:
        with pytest.raises(runner.IsolatedRunnerError, match="not_ancestor"):
            runner._attest_database_schema(repository=_Repository(), git_commit=current)
    assert commands == [["git", "merge-base", "--is-ancestor", installed, current]]


def test_committed_recovery_replays_and_mirrors_without_run_once_or_smtp(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    manifest = SimpleNamespace(
        artifact_digest=runner.USER_SCOPE_COMMITTED_MANIFEST_DIGEST
    )
    ledger = {"state": "PRE_MIRROR"}
    replay = {
        "status": "REPLAY_VERIFIED",
        "same_execution_identity": True,
        "same_artifact_identity": True,
        "same_artifact_content": True,
        "all_registrations_and_parent_chains_exact": True,
        "manual_input_assembly": False,
        "dispatch_performed": False,
    }

    class _Supervisor:
        def __init__(self, **_kwargs):
            pass

        @staticmethod
        def run_once(**_kwargs):
            raise AssertionError("committed recovery must not run workload")

        @staticmethod
        def replay(**_kwargs):
            return replay

    monkeypatch.setattr(
        runner,
        "validate_user_scope_committed_recovery_governance",
        lambda **_kwargs: {},
    )
    monkeypatch.setattr(
        runner.artifacts,
        "load_source_contract",
        lambda **_kwargs: {"artifact_digest": "a" * 64},
    )
    monkeypatch.setattr(
        runner,
        "_validate_user_scope_committed_live_state",
        lambda **_kwargs: (manifest, _context(), ledger["state"]),
    )
    monkeypatch.setattr(runner, "_p3_source_identity", lambda: ("p3", "unchanged"))
    monkeypatch.setattr(runner.mainline, "IsolatedChallengerSupervisor", _Supervisor)
    monkeypatch.setattr(
        runner,
        "_user_scope_committed_ledger_state",
        lambda **_kwargs: ledger["state"],
    )

    def mirror(**_kwargs):
        ledger["state"] = "MIRRORED"

    monkeypatch.setattr(runner, "_mirror_search_batch_ledger", mirror)
    result = runner.recover_p3_user_scope_committed_batch(
        apply=True,
        repository=object(),
        repaired_source_digest="a" * 64,
        repaired_git_commit="b" * 40,
    )
    assert result["status"] == "BATCH_COMPLETE_AND_REPLAY_VERIFIED"
    assert result["ledger_state_before"] == "PRE_MIRROR"
    assert result["ledger_state_after"] == "MIRRORED"
    assert result["scientific_workloads_executed"] == 0
    assert result["run_once_calls"] == 0
    assert result["smtp_calls"] == 0
    assert result["mandatory_mail_kinds"] == list(
        runner.USER_SCOPE_MANDATORY_MAIL_KINDS
    )
    assert result["mail_integration"] == (
        "PENDING_REAL_SCHEDULED_DATA250_RECEIPT_REPLAY"
    )


def test_committed_recovery_surface_contains_no_workload_dispatch() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    source = inspect.getsource(runner.recover_p3_user_scope_committed_batch)
    tree = ast.parse(source)
    run_once_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run_once"
    ]
    assert run_once_calls == []
    assert "send_external_once" not in source
    assert "_mirror_search_batch_ledger" in source
    assert "USER_SCOPE_MANDATORY_MAIL_KINDS" in source
