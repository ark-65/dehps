"""Exact retained-P3 incident acceptance, against an explicitly supplied clone.

Run with the frozen ac0 worker on PYTHONPATH. No production DSN default, no mocked
persistence/runner/governance verifier, and no SMTP delivery path is invoked.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "p3_2026105_recovery", ROOT / "deploy/execution/recover_p3_2026105.py"
)
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


def test_missing_events_fail_closed():
    with pytest.raises(repair.RecoveryError, match="event_set_changed"):
        repair.validate_events([])


def test_exact_clone_recovery_and_existing_consumer():
    if os.environ.get("DEHPS_2026105_CLONE_TEST") != "1":
        pytest.skip("requires explicitly isolated exact incident clone")
    from dehps.agents.repository import AgentRequestRepository
    from dehps.agents.requests import AgentRequestType
    from dehps.agents.roles import AgentRole
    from dehps.agents.service import AgentRequestService
    from dehps.config import ROOT_DIR, get_settings
    from dehps.notifications.p3_top100 import load_postdraw_bundle
    from dehps.research_os.information_theory.measurement_system_v2 import (
        forward_prequential_confirmatory as p3,
    )
    from dehps.research_os.repository import PostgresResearchOSRepository
    from dehps.research_os.supervisor import ResearchEvidenceSupervisor
    from dehps.storage.postgres_store import ensure_research_os_schema

    root = Path(os.environ["DEHPS_2026105_CLONE_ROOT"]).resolve()
    assert ROOT_DIR.resolve() == root and not (root / ".env").exists()
    assert not root.is_relative_to(Path("/home/ark/workspace/dehps"))
    settings = get_settings()
    assert settings.db_name == "dehps_r5_105_clone" and settings.db_port == 55439

    @contextmanager
    def connect():
        with psycopg.connect(
            settings.database_url,
            options="-c statement_timeout=20000 -c lock_timeout=3000",
        ) as conn:
            identity = conn.execute(
                "SELECT current_database(),(SELECT system_identifier::text FROM pg_control_system())"
            ).fetchone()
            assert (
                identity[0] == "dehps_r5_105_clone"
                and identity[1] != "7651515426413260838"
            )
            yield conn

    repo = PostgresResearchOSRepository(connect)
    original = repo.load_manifest(control_plane_key=repair.CONTROL)
    assert original.artifact_digest == repair.OLD_HEAD
    with connect() as conn:
        before = conn.execute(
            "SELECT event_digest,event_json FROM research_os_mainline_execution_events ORDER BY event_digest"
        ).fetchall()
        original_definitions = conn.execute(
            "SELECT task_digest,definition_json FROM research_os_task_definitions ORDER BY task_digest"
        ).fetchall()
        original_registrations = conn.execute(
            "SELECT registration_digest,registration_json FROM research_os_mainline_artifacts ORDER BY registration_digest"
        ).fetchall()
        assert conn.execute("SHOW session_replication_role").fetchone()[0] == "origin"
    original_files = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root / "runtime").rglob("*")
        if p.is_file()
    }

    # The retained ac0 guard takes no DDL lock when installed. Repeating the old
    # migration under a publication lock is rejected by real PostgreSQL timeout.
    with connect() as writer:
        writer.execute("LOCK research_os_task_states IN ROW EXCLUSIVE MODE")
        with connect() as reader:
            reader.execute("SET lock_timeout='300ms'")
            ensure_research_os_schema(reader)
            assert (
                reader.execute(
                    "SELECT mode FROM pg_locks WHERE pid=pg_backend_pid() AND mode IN ('AccessExclusiveLock','ShareRowExclusiveLock')"
                ).fetchall()
                == []
            )
        with pytest.raises(psycopg.errors.LockNotAvailable), connect() as old_reader:
            old_reader.execute("SET lock_timeout='300ms'")
            old_reader.execute(
                (root / "infra/postgres/init/002_research_os.sql").read_text()
            )

    agent_repo = AgentRequestRepository(connect)
    service = AgentRequestService(agent_repo)
    key = "isolated-fixture-2026105-recovery-" + uuid4().hex
    actor = "isolated-fixture-operator"
    commit = "1" * 40
    payload = {
        "version": "isolated-recovery-fixture-结算",
        "commit": commit,
        "checks": ["real-clone-only"],
        "rollback": "discard clone",
        "recovery": repair.RECOVERY_CONTRACT,
    }
    service.create_draft(
        request_key=key,
        request_type=AgentRequestType.OPERATOR_RELEASE,
        requested_by_role=AgentRole.ENGINEERING,
        requested_by=actor,
        title="ISOLATED TEST FIXTURE ONLY",
        summary="No production approval",
        payload=payload,
        environment="production",
    )
    service.submit(
        key, actor_role=AgentRole.ENGINEERING, actor_id=actor, environment="production"
    )
    with pytest.raises(repair.RecoveryError, match="no_authorized_operator"):
        repair.prepare_retry(
            repo, root=root, request_key=key, executor_id=actor, commit=commit
        )
    service.begin_review(
        key,
        reviewer_role=AgentRole.REVIEWER,
        reviewer_id="isolated-fixture-reviewer",
        environment="production",
    )
    service.approve(
        key,
        reviewer_role=AgentRole.REVIEWER,
        reviewer_id="isolated-fixture-reviewer",
        environment="production",
        reason={
            "request_payload_sha256": hashlib.sha256(
                json.dumps(
                    payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode()
            ).hexdigest(),
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "isolated_test_fixture": True,
            "human_review": False,
        },
    )
    service.begin_execution(
        key,
        executor_role=AgentRole.OPERATOR,
        executor_id=actor,
        environment="production",
        run_id="isolated-fixture-only",
    )
    for wrong_actor, wrong_commit, message in (
        ("wrong", commit, "identity_changed"),
        (actor, "2" * 40, "no_authorized_operator"),
    ):
        with pytest.raises(repair.RecoveryError, match=message):
            repair.prepare_retry(
                repo,
                root=root,
                request_key=key,
                executor_id=wrong_actor,
                commit=wrong_commit,
            )
        assert (
            repo.load_manifest(control_plane_key=repair.CONTROL).artifact_digest
            == repair.OLD_HEAD
        )
    with connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        events = cur.execute(
            "SELECT event_digest,event_json FROM research_os_mainline_execution_events WHERE task_key=%s ORDER BY sequence",
            (repair.TASK,),
        ).fetchall()
    repair.validate_events(events)
    changed = json.loads(json.dumps(events))
    changed[1]["event_json"]["execution_id"] = "0" * 64
    with pytest.raises(repair.RecoveryError, match="identity_changed"):
        repair.validate_events(changed)
    with pytest.raises(repair.RecoveryError, match="event_set_changed"):
        repair.validate_events(events + events[-1:])

    prepared = repair.prepare_retry(
        repo, root=root, request_key=key, executor_id=actor, commit=commit
    )
    assert prepared["status"] == "PREPARED"
    assert repair.TASK in {
        r.task_key
        for r in repo.control_plane.resolve(
            repo.load_manifest(control_plane_key=repair.CONTROL)
        ).ready_queue
    }
    assert (
        repair.prepare_retry(
            repo, root=root, request_key=key, executor_id=actor, commit=commit
        )["status"]
        == "ALREADY_PREPARED"
    )
    sup = p3.ForwardPrequentialSupervisor(
        repository=repo,
        root_dir=root,
        control_plane_key=repair.CONTROL,
        git_commit=commit,
        require_clean_tree=False,
    )
    generic = ResearchEvidenceSupervisor(
        repository=repo, root_dir=root, control_plane_key=repair.CONTROL
    )
    results = []
    for task in (repair.TASK, repair.TASK + "-replay"):
        result = sup.run_once(task_key=task)
        assert result["execution_id"] != repair.OLD_EXECUTION
        results.append(
            {
                "execution": result,
                "typed": sup.replay(task_key=task),
                "generic": generic.replay(task_key=task),
            }
        )
        assert (
            results[-1]["typed"]["status"]
            == results[-1]["generic"]["status"]
            == "REPLAY_VERIFIED"
        )
    bundle = load_postdraw_bundle(repo, issue="2026105", root_dir=root)
    assert bundle.predraw.issue == "2026105"
    with connect() as conn:
        after = conn.execute(
            "SELECT event_digest,event_json FROM research_os_mainline_execution_events ORDER BY event_digest"
        ).fetchall()
        after_by_digest = dict(after)
        assert all(after_by_digest.get(digest) == value for digest, value in before)
        assert (
            conn.execute(
                "SELECT task_digest,definition_json FROM research_os_task_definitions ORDER BY task_digest"
            ).fetchall()
            == original_definitions
        )
        after_registrations = conn.execute(
            "SELECT registration_digest,registration_json FROM research_os_mainline_artifacts ORDER BY registration_digest"
        ).fetchall()
        after_by_registration = dict(after_registrations)
        assert all(
            after_by_registration.get(digest) == value
            for digest, value in original_registrations
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM research_os_mainline_execution_events WHERE task_key IN (%s,%s) AND event_type='completed'",
                (repair.TASK, repair.TASK + "-replay"),
            ).fetchone()[0]
            == 2
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM research_os_external_executor_observations WHERE owner=%s",
                (repair.OWNER,),
            ).fetchone()[0]
            == 1
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM research_os_mainline_execution_events WHERE task_key LIKE '%%2026106%%'"
            ).fetchone()[0]
            == 0
        )
    for relative, digest in original_files.items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == digest
    assert (
        repair.prepare_retry(
            repo, root=root, request_key=key, executor_id=actor, commit=commit
        )["status"]
        == "ALREADY_PREPARED"
    )
    evidence = {
        "status": "ISOLATED_CANONICAL_REPLAY_VERIFIED",
        "production_recovery": False,
        "smtp_connected": False,
        "human_approval": False,
        "prepared": prepared,
        "results": results,
        "preserved_events": len(before),
        "preserved_registrations": len(original_registrations),
        "preserved_files": len(original_files),
        "original_manifest": original.artifact_digest,
        "after_manifest": repo.load_manifest(
            control_plane_key=repair.CONTROL
        ).artifact_digest,
    }
    Path(os.environ["DEHPS_2026105_PROOF_OUTPUT"]).write_text(
        json.dumps(evidence, indent=2, default=str)
    )
