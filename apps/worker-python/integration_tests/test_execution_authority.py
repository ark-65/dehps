"""Real authentication and direct-SQL bypass tests on a disposable PostgreSQL.

No production settings, substituted actor strings, or mocked persistence.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from importlib.resources import files
import os
from queue import Queue
from threading import Event
from time import monotonic
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from dehps.execution.authority import AuthorityClient
from dehps.execution.database import DatabaseBinding

RELEASE = "a" * 64
OTHER = "b" * 64
ENTRY_FUNCTIONS = (
    "request_create(jsonb,text,text)", "request_get(bigint)",
    "approve(bigint,text,text,timestamptz,text)", "revoke(bigint)",
    "begin_execution(bigint,text,text,text)", "reauthorize(bigint,text,text)",
)


@pytest.fixture
def authority():
    details = conninfo_to_dict(os.environ["DEHPS_EXECUTION_TEST_ADMIN_DSN"])
    assert details["dbname"] == "dehps_execution_test_admin"
    tag = "xa_" + uuid4().hex[:16]
    database, owner = tag + "_db", tag + "_owner"
    # Aliases share a principal even if permission roles/labels differ.
    subjects = {
        "engineer": ("person-a", "learning", True, False, True),
        "alias": ("person-a", "learning", False, True, True),
        "reviewer": ("person-b", "learning", False, True, True),
        "operator": ("person-c", "learning", False, False, True),
        "observer": ("person-d", "observer", True, True, True),
        "unknown": None,
    }
    roles = {name: tag + "_" + name for name in subjects}
    secrets = {name: uuid4().hex for name in subjects}
    db_admin = make_conninfo(**{**details, "dbname": database})
    clients = {}
    with psycopg.connect(make_conninfo(**details), autocommit=True) as admin:
        try:
            admin.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS").format(sql.Identifier(owner)))
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
            admin.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database)))
            for name, role in roles.items():
                admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS").format(sql.Identifier(role), sql.Literal(secrets[name])))
                admin.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), sql.Identifier(role)))
                dsn = make_conninfo(**{**details, "dbname": database, "user": role, "password": secrets[name]})
                clients[name] = AuthorityClient(DatabaseBinding(dsn, database, role))
            with psycopg.connect(db_admin) as setup:
                setup.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
                setup.execute(sql.SQL("GRANT CREATE ON DATABASE {} TO {}").format(sql.Identifier(database), sql.Identifier(owner)))
                setup.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(owner)))
                setup.execute(files("dehps.execution").joinpath("migrations/001_authority.sql").read_text())
                setup.execute("RESET ROLE")
                setup.execute(sql.SQL("REVOKE CREATE ON DATABASE {} FROM {}").format(sql.Identifier(database), sql.Identifier(owner)))
                for name, subject in subjects.items():
                    role = roles[name]
                    if subject is not None:
                        setup.execute("""INSERT INTO execution_authority.identities
                            (login_oid,login_name,principal,control_plane,can_request,can_review,can_execute)
                            SELECT oid,rolname,%s,%s,%s,%s,%s FROM pg_roles WHERE rolname=%s""", (*subject, role))
                    # Even unmapped login with the same API grants must fail closed.
                    setup.execute(sql.SQL("GRANT USAGE ON SCHEMA execution_authority TO {}").format(sql.Identifier(role)))
                    for signature in ENTRY_FUNCTIONS:
                        setup.execute(sql.SQL("GRANT EXECUTE ON FUNCTION execution_authority.{} TO {}").format(sql.SQL(signature), sql.Identifier(role)))
            yield clients, db_admin, roles, owner
        finally:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))
            for role in [*roles.values(), owner]:
                admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))


def proposal(clients):
    request = clients["engineer"].request({"task": "fixture-only", "scope": "learning"}, RELEASE, label="Engineer")
    return request, clients["reviewer"].get(request)["content_sha256"]


def approved(clients):
    request, digest = proposal(clients)
    clients["reviewer"].approve(request, digest, RELEASE, datetime.now(timezone.utc) + timedelta(hours=1), label="Reviewer")
    return request, digest


def test_authenticated_principals_survive_reconnect_and_cannot_self_approve(authority):
    clients, admin_dsn, roles, _ = authority
    request, digest = proposal(clients)
    for name in ("engineer", "alias"):
        for label in ("Independent Reviewer", "ark", roles["reviewer"]):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                clients[name].approve(request, digest, RELEASE, datetime.now(timezone.utc) + timedelta(hours=1), label=label)
    with psycopg.connect(admin_dsn) as admin:
        row = admin.execute("SELECT requester,login_name,display_label FROM execution_authority.requests WHERE id=%s", (request,)).fetchone()
        assert row == ("person-a", roles["engineer"], "Engineer")
        assert admin.execute("SELECT count(*) FROM execution_authority.approvals").fetchone() == (0,)


def test_reverse_separation_and_idempotent_execution(authority):
    clients, admin_dsn, _, _ = authority
    request, digest = approved(clients)
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="independent approval"):
        clients["reviewer"].begin(request, digest, RELEASE, label="Different Operator")
    execution = clients["operator"].begin(request, digest, RELEASE)
    assert clients["operator"].begin(request, digest, RELEASE, label="retry") == execution
    clients["operator"].reauthorize(execution, digest, RELEASE)
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="another identity"):
        clients["engineer"].reauthorize(execution, digest, RELEASE)
    with psycopg.connect(admin_dsn) as admin:
        assert admin.execute("SELECT count(*) FROM execution_authority.executions").fetchone() == (1,)
        assert admin.execute("SELECT reviewer FROM execution_authority.approvals").fetchone() == ("person-b",)


def test_unmapped_and_cross_domain_sessions_are_denied(authority):
    clients, _, _, _ = authority
    request, digest = approved(clients)
    for name in ("unknown", "observer"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            clients[name].get(request)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            clients[name].begin(request, digest, RELEASE)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            clients[name].revoke(request)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        clients["unknown"].request({}, RELEASE)


@pytest.mark.parametrize("content,release", [(OTHER, RELEASE), (None, RELEASE), ("", RELEASE), (None, None), ("original", OTHER)])
def test_changed_content_or_release_never_executes(authority, content, release):
    clients, _, _, _ = authority
    request, digest = approved(clients)
    if content == "original":
        content = digest
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        clients["operator"].begin(request, content, release)
    execution = clients["operator"].begin(request, digest, RELEASE)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        clients["operator"].reauthorize(execution, content, release)


def test_approval_binds_both_digests_and_rejects_null_or_infinite_expiry(authority):
    clients, _, _, _ = authority
    request, digest = proposal(clients)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    for content, release, expiry in ((OTHER, RELEASE, future), (digest, OTHER, future), (None, RELEASE, future), (digest, RELEASE, None), (digest, RELEASE, datetime.now(timezone.utc) - timedelta(days=1))):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            clients["reviewer"].approve(request, content, release, expiry)
    with clients["reviewer"].database.connect() as connection:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT execution_authority.approve(%s,%s,%s,'infinity'::timestamptz,'label')", (request, digest, RELEASE))


@pytest.mark.parametrize("change", ["revoke", "reviewer_disabled", "reviewer_permission", "executor_disabled", "expired"])
def test_current_authority_rechecked_after_persisted_execution(authority, change):
    clients, admin_dsn, roles, _ = authority
    request, digest = approved(clients)
    execution = clients["operator"].begin(request, digest, RELEASE)
    if change == "revoke":
        clients["reviewer"].revoke(request)
    else:
        with psycopg.connect(admin_dsn) as admin:
            if change == "reviewer_disabled":
                admin.execute("UPDATE execution_authority.identities SET active=false WHERE login_name=%s", (roles["reviewer"],))
            elif change == "reviewer_permission":
                admin.execute("UPDATE execution_authority.identities SET can_review=false WHERE login_name=%s", (roles["reviewer"],))
            elif change == "executor_disabled":
                admin.execute("UPDATE execution_authority.identities SET active=false WHERE login_name=%s", (roles["operator"],))
            else:
                # Fixture-only clock arrangement; production clients cannot edit approvals.
                admin.execute("UPDATE execution_authority.approvals SET expires_at=clock_timestamp()-interval '1 second'")
    for action in (lambda: clients["operator"].begin(request, digest, RELEASE), lambda: clients["operator"].reauthorize(execution, digest, RELEASE)):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            action()
    with psycopg.connect(admin_dsn) as admin:
        assert admin.execute("SELECT count(*) FROM execution_authority.executions").fetchone() == (1,)
        assert admin.execute("SELECT count(*) FROM execution_authority.approvals").fetchone() == (1,)


def test_direct_sql_cannot_forge_mutate_or_assume_authority(authority):
    clients, _, roles, owner = authority
    request, digest = approved(clients)
    clients["operator"].begin(request, digest, RELEASE)
    statements = [
        "UPDATE execution_authority.identities SET can_review=true",
        "INSERT INTO execution_authority.identities(login_oid) VALUES (1)",
        "DELETE FROM execution_authority.requests",
        "UPDATE execution_authority.approvals SET reviewer='person-c'",
        "TRUNCATE execution_authority.revocations",
        "UPDATE execution_authority.executions SET executor='person-b'",
        "SELECT execution_authority.actor('review')",
        "SELECT execution_authority.check_execution(1,'a','a')",
        "CREATE TABLE execution_authority.forged(id int)",
        f'SET ROLE "{roles["reviewer"]}"',
        f'SET ROLE "{owner}"',
        f'SET SESSION AUTHORIZATION "{roles["reviewer"]}"',
    ]
    for statement in statements:
        # Raw libpq intentionally bypasses all client-side admission checks.
        with psycopg.connect(clients["operator"].database.dsn, autocommit=True) as connection:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                connection.execute(statement)


def test_search_path_and_identity_labels_cannot_spoof_session_user(authority):
    clients, _, roles, _ = authority
    request, digest = proposal(clients)
    with psycopg.connect(clients["alias"].database.dsn, autocommit=True) as connection:
        connection.execute("SET search_path = public, pg_temp")
        connection.execute("SELECT set_config('dehps.reviewer_id', %s, false)", (roles["reviewer"],))
        connection.execute("SELECT set_config('application_name', %s, false)", (roles["reviewer"],))
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="independent bound approval"):
            connection.execute("SELECT execution_authority.approve(%s,%s,%s,clock_timestamp()+interval '1 hour',%s)", (request, digest, RELEASE, roles["reviewer"]))


def test_stale_transaction_cannot_hide_revocation(authority):
    clients, _, _, _ = authority
    request, digest = approved(clients)
    with psycopg.connect(clients["operator"].database.dsn) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        connection.execute("SELECT 1")
        clients["reviewer"].revoke(request)
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="read committed"):
            connection.execute("SELECT execution_authority.begin_execution(%s,%s,%s,'')", (request, digest, RELEASE))


def test_set_role_does_not_change_authenticated_principal(authority):
    clients, admin_dsn, roles, _ = authority
    request, digest = proposal(clients)
    with psycopg.connect(admin_dsn) as admin:
        admin.execute(sql.SQL("GRANT {} TO {} WITH INHERIT FALSE, SET TRUE").format(
            sql.Identifier(roles["reviewer"]), sql.Identifier(roles["alias"])))
    with psycopg.connect(clients["alias"].database.dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(roles["reviewer"])))
        assert connection.execute("SELECT current_user,session_user").fetchone() == (
            roles["reviewer"], roles["alias"])
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="independent bound approval"):
            connection.execute("SELECT execution_authority.approve(%s,%s,%s,clock_timestamp()+interval '1 hour','')", (request, digest, RELEASE))


def test_concurrent_admission_has_one_durable_execution(authority):
    clients, admin_dsn, _, _ = authority
    request, digest = approved(clients)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: clients["operator"].begin(request, digest, RELEASE), range(4)))
    assert len(set(results)) == 1
    with psycopg.connect(admin_dsn) as admin:
        assert admin.execute("SELECT count(*) FROM execution_authority.executions").fetchone() == (1,)


def test_revocation_committed_while_start_waits_is_observed(authority):
    clients, admin_dsn, _, _ = authority
    request, digest = approved(clients)
    started = Queue()

    def begin():
        with psycopg.connect(clients["operator"].database.dsn) as connection:
            connection.execute("SET statement_timeout='10s'")
            started.put(connection.info.backend_pid)
            return connection.execute(
                "SELECT execution_authority.begin_execution(%s,%s,%s,'')",
                (request, digest, RELEASE),
            ).fetchone()[0]

    with ThreadPoolExecutor(max_workers=1) as pool:
        with psycopg.connect(clients["reviewer"].database.dsn) as reviewer:
            reviewer.execute("SELECT execution_authority.revoke(%s)", (request,))
            future = pool.submit(begin)
            pid = started.get(timeout=5)
            # Prove the actual session is blocked on the uncommitted revocation.
            with psycopg.connect(admin_dsn, autocommit=True) as admin:
                deadline = monotonic() + 5
                while not admin.execute("SELECT pg_blocking_pids(%s)", (pid,)).fetchone()[0]:
                    assert monotonic() < deadline, "execution did not reach the request lock"
                    Event().wait(0.01)
            assert not future.done()
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="revoked"):
            future.result(timeout=5)
    with psycopg.connect(admin_dsn) as admin:
        assert admin.execute("SELECT count(*) FROM execution_authority.executions").fetchone() == (0,)
