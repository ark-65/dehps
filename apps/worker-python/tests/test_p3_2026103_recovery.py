from __future__ import annotations

import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from dehps.config import get_settings
from dehps.research_os import p3_2026103_recovery as repair
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.storage.postgres_store import ensure_research_os_schema

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def isolated_schema():
    if os.getenv("DEHPS_TEST_POSTGRES") != "1":
        pytest.skip("requires isolated PostgreSQL acceptance")
    dsn = os.getenv("DEHPS_TEST_DATABASE_URL", get_settings().database_url)
    schema = "p3_recovery_test_" + uuid4().hex
    with psycopg.connect(dsn) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

    @contextmanager
    def connect():
        with psycopg.connect(dsn) as conn:
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            conn.execute("SET statement_timeout='20s'")
            yield conn

    try:
        yield connect
    finally:
        with psycopg.connect(dsn) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_installed_schema_does_not_request_ddl_locks(isolated_schema):
    with isolated_schema() as conn:
        ensure_research_os_schema(conn)
    # Reproduces the lock held by atomic publication. The old unconditional
    # ALTER TABLE would block and time out here, even though schema is installed.
    with isolated_schema() as writer:
        writer.execute("LOCK research_os_task_states IN ROW EXCLUSIVE MODE")
        with isolated_schema() as reader:
            reader.execute("SET lock_timeout='500ms'")
            ensure_research_os_schema(reader)
            locks = reader.execute(
                "SELECT mode FROM pg_locks WHERE pid=pg_backend_pid() "
                "AND mode IN ('AccessExclusiveLock','ShareRowExclusiveLock')"
            ).fetchall()
            assert locks == []


def test_schema_marker_rolls_back_with_migration(isolated_schema):
    with pytest.raises(RuntimeError, match="rollback"):
        with isolated_schema() as conn:
            ensure_research_os_schema(conn)
            raise RuntimeError("rollback")
    with isolated_schema() as conn:
        assert conn.execute("SELECT to_regclass('dehps_schema_applications')").fetchone() == (None,)
        ensure_research_os_schema(conn)
    with isolated_schema() as conn:
        assert conn.execute("SELECT count(*) FROM dehps_schema_applications").fetchone() == (1,)


def test_concurrent_first_schema_installation(isolated_schema):
    def install():
        with isolated_schema() as conn:
            ensure_research_os_schema(conn)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: install(), range(2)))
    with isolated_schema() as conn:
        assert conn.execute("SELECT count(*) FROM dehps_schema_applications").fetchone() == (1,)


def test_event_cardinality_fails_closed():
    with pytest.raises(repair.RecoveryError, match="event_set_changed"):
        repair.validate_events([])


def _copy_frozen_sources(root):
    for contract in ("m4-p3-forward-prequential-confirmatory-source-v1.json",
                     "m4-p3-top100-notification-source-v3.json"):
        relative = Path("configs/research-os") / contract
        paths = [relative] + [Path(e["path"]) for e in json.loads((ROOT / relative).read_text())["source_entries"]]
        for path in paths:
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, root / path)


@pytest.fixture
def incident_clone(isolated_schema, tmp_path):
    if os.getenv("DEHPS_P3_INCIDENT_REPLAY") != "1":
        pytest.skip("requires explicit live incident snapshot clone")
    # Copy only Research OS tables into an isolated schema. Never mutate public
    # state or share writable runtime paths with production.
    tables = (
        "research_os_goal_definitions", "research_os_task_definitions",
        "research_os_manifests", "research_os_manifest_goals", "research_os_manifest_tasks",
        "research_os_control_planes", "research_os_goal_states", "research_os_task_states",
        "research_os_dependency_facts", "research_os_mainline_execution_events",
        "research_os_mainline_artifacts",
    )
    with isolated_schema() as conn:
        ensure_research_os_schema(conn)
        for table in tables:
            columns = [r[0] for r in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position",
                (table,),
            ).fetchall()]
            names = sql.SQL(',').join(map(sql.Identifier, columns))
            conn.execute(sql.SQL("INSERT INTO {} ({}) SELECT {} FROM public.{}").format(
                sql.Identifier(table), names, names, sql.Identifier(table)))
        head = conn.execute("SELECT current_manifest_digest FROM research_os_control_planes "
                            "WHERE control_plane_key=%s", (repair.CONTROL,)).fetchone()[0]
        if head != repair.OLD_HEAD:
            pytest.skip("live incident has advanced; exact pre-recovery clone no longer available")
        # Minimal typed-governance fixture, strictly in this disposable schema.
        conn.execute("CREATE TABLE agent_requests (id bigint, request_key text, status text, "
                     "metadata_json jsonb, request_type text,parent_request_id bigint,payload_json jsonb)")
        conn.execute("CREATE TABLE agent_request_executions (id bigint,request_id bigint,status text, "
                     "executor_role text,executor_id text,environment text,run_id text)")
        conn.execute("INSERT INTO agent_requests VALUES (812,%s,'completed',%s::jsonb,"
                     "'engineering_implementation',NULL,'{}')",
                     (repair.ENGINEERING_REQUEST,json.dumps({"payload_sha256":repair.ENGINEERING_PAYLOAD})))
        conn.execute("INSERT INTO agent_requests VALUES (900001,'test-operator','executing','{}',"
                     "'operator_release',812,%s::jsonb)",
                     (json.dumps({"commit":"1"*40,"recovery":repair.RECOVERY_CONTRACT}),))
        conn.execute("INSERT INTO agent_request_executions VALUES "
                     "(900002,900001,'running','operator','test-operator','production','isolated-test')")
        paths = conn.execute("SELECT artifact_path FROM research_os_mainline_artifacts "
                             "WHERE control_plane_key=%s", (repair.CONTROL,)).fetchall()
    source_root = Path(os.environ["DEHPS_INCIDENT_ARTIFACT_ROOT"])
    _copy_frozen_sources(tmp_path)
    for (relative,) in paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root / relative, destination)
    return PostgresResearchOSRepository(isolated_schema), tmp_path


def test_exact_incident_recovery_and_existing_consumers(incident_clone):
    from dehps.notifications.p3_top100 import load_postdraw_bundle
    from dehps.research_os.information_theory.measurement_system_v2 import forward_prequential_confirmatory as p3
    from dehps.research_os.supervisor import ResearchEvidenceSupervisor
    repo, root = incident_clone
    with repo.connection_factory() as conn:
        before = conn.execute("SELECT event_digest,event_json FROM research_os_mainline_execution_events "
                              "WHERE task_key=%s ORDER BY sequence", (repair.TASK,)).fetchall()
    prepared = repair.prepare_retry(repo, root=root, request_key="test-operator",
                                    executor_id="test-operator", commit="1"*40)
    assert prepared["status"] == "PREPARED"
    ready = repo.load_manifest(control_plane_key=repair.CONTROL)
    assert repair.TASK in {r.task_key for r in repo.control_plane.resolve(ready).ready_queue}
    assert repair.prepare_retry(repo, root=root, request_key="test-operator",
        executor_id="test-operator", commit="1"*40)["status"] == "ALREADY_PREPARED"
    sup = p3.ForwardPrequentialSupervisor(repository=repo, root_dir=root,
        control_plane_key=repair.CONTROL, git_commit="1"*40, require_clean_tree=False)
    completed = sup.run_once(task_key=repair.TASK)
    assert completed["execution_id"] != repair.OLD_EXECUTION
    assert sup.replay(task_key=repair.TASK)["status"] == "REPLAY_VERIFIED"
    generic = ResearchEvidenceSupervisor(repository=repo, root_dir=root,
                                         control_plane_key=repair.CONTROL)
    assert generic.replay(task_key=repair.TASK)["status"] == "REPLAY_VERIFIED"
    bundle = load_postdraw_bundle(repo, issue="2026103", root_dir=root)
    assert bundle.predraw.issue == "2026103"
    with repo.connection_factory() as conn:
        after = conn.execute("SELECT event_digest,event_json FROM research_os_mainline_execution_events "
                             "WHERE execution_id=%s ORDER BY sequence", (repair.OLD_EXECUTION,)).fetchall()
        assert before == after
        assert conn.execute("SELECT count(*) FROM research_os_mainline_execution_events "
                            "WHERE task_key=%s AND event_type='completed'", (repair.TASK,)).fetchone() == (1,)
        assert conn.execute("SELECT count(*) FROM research_os_external_executor_observations "
                            "WHERE owner=%s", (repair.OWNER,)).fetchone() == (1,)


def test_recovery_rejects_wrong_operator_and_preserves_head(incident_clone):
    repo, root = incident_clone
    with pytest.raises(repair.RecoveryError, match="operator_execution_identity_changed"):
        repair.prepare_retry(repo, root=root, request_key="test-operator",
                             executor_id="unapproved-operator", commit="1"*40)
    assert repo.load_manifest(control_plane_key=repair.CONTROL).artifact_digest == repair.OLD_HEAD
    with pytest.raises(repair.RecoveryError, match="no_authorized_operator_recovery"):
        repair.prepare_retry(repo, root=root, request_key="test-operator",
                             executor_id="test-operator", commit="2"*40)
    with repo.connection_factory() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            events = cur.execute("SELECT event_digest,event_json FROM research_os_mainline_execution_events "
                                 "WHERE task_key=%s ORDER BY sequence", (repair.TASK,)).fetchall()
    events[1]["event_json"]["execution_id"] = "0"*64
    with pytest.raises(repair.RecoveryError, match="incident_event_identity_changed"):
        repair.validate_events(events)
