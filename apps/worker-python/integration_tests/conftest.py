"""Disposable PostgreSQL authority fixture shared by control-layer checks."""
from importlib.resources import files
import os
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from dehps.execution.authority import AuthorityClient
from dehps.execution.database import DatabaseBinding

ENTRY_FUNCTIONS = (
    "request_create(jsonb,text,text)", "request_get(bigint)",
    "approve(bigint,text,text,timestamptz,text)", "revoke(bigint)",
    "begin_execution(bigint,text,text,text)", "reauthorize(bigint,text,text)",
)


@pytest.fixture
def authority():
    yield from authority_fixture()


def authority_fixture(domain='learning'):
    details = conninfo_to_dict(os.environ["DEHPS_EXECUTION_TEST_ADMIN_DSN"])
    assert details["dbname"] == "dehps_execution_test_admin"
    tag = "xa_" + uuid4().hex[:16]
    database, owner = tag + "_db", tag + "_owner"
    # Aliases share a principal even if permission roles/labels differ.
    subjects = {
        "engineer": ("person-a", domain, True, False, True),
        "alias": ("person-a", domain, False, True, True),
        "reviewer": ("person-b", domain, False, True, True),
        "operator": ("person-c", domain, False, False, True),
        "observer": ("person-d", 'observer' if domain == 'learning' else 'learning', True, True, True),
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
            # A persistence test may restart the disposable server. Cleanup must
            # reconnect rather than reuse a pre-restart administrator session.
            with psycopg.connect(make_conninfo(**details), autocommit=True) as cleanup:
                cleanup.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))
                for role in [*roles.values(), owner]:
                    cleanup.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
