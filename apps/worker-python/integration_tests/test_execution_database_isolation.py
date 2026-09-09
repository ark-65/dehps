"""Required explicit job: a disposable PostgreSQL instance, never production.

Missing configuration is a failure, not a skip. All created databases/roles are
randomly named and dropped in fixture teardown; only this fixture's objects are
mutated. The runner must supply the separately provisioned test-cluster DSN.
"""
import os
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from dehps.execution.context import BoundaryError
from dehps.execution.database import DatabaseBinding


@pytest.fixture
def cluster():
    admin_dsn = os.environ["DEHPS_EXECUTION_TEST_ADMIN_DSN"]
    details = conninfo_to_dict(admin_dsn)
    # An explicit disposable-cluster marker is required, in addition to a
    # nonproduction connection. The ordinary .env and shared worker DB are unused.
    assert details["dbname"] == "dehps_execution_test_admin"
    tag = "xr_" + uuid4().hex[:16]
    databases = {name: tag + "_" + name for name in ("formal", "observer", "learning")}
    roles = {name: tag + "_" + name + "_runner" for name in ("observer", "learning")}
    password = uuid4().hex
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        try:
            for role in roles.values():
                admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS").format(sql.Identifier(role), sql.Literal(password)))
            for name, database in databases.items():
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
                admin.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database)))
                if name in roles:
                    admin.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), sql.Identifier(roles[name])))
                with psycopg.connect(make_conninfo(**{**details, "dbname": database})) as connection:
                    connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
                    connection.execute("CREATE TABLE public.sentinel (id int PRIMARY KEY, value text NOT NULL)")
                    connection.execute("INSERT INTO public.sentinel VALUES (1,'original')")
                    if name in roles:
                        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(roles[name])))
                        connection.execute(sql.SQL("GRANT SELECT,UPDATE ON public.sentinel TO {}").format(sql.Identifier(roles[name])))
            yield details, databases, roles, password
        finally:
            for database in databases.values():
                admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database)))
            for role in roles.values():
                admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))


def binding(cluster, name, *, target=None):
    details, databases, roles, password = cluster
    database = databases[target or name]
    role = roles[name]
    dsn = make_conninfo(**{**details, "dbname": database, "user": role, "password": password})
    return DatabaseBinding(dsn, database, role)


def test_actual_roles_cannot_connect_to_formal_or_each_other(cluster):
    for name, other in (("observer", "learning"), ("learning", "observer")):
        with binding(cluster, name).connect() as connection:
            connection.execute("UPDATE public.sentinel SET value=%s WHERE id=1", (name,))
        # Call libpq directly as misbehaving code would. Admission checks are
        # deliberately bypassed; the PostgreSQL permission must still reject it.
        for target in ("formal", other):
            with pytest.raises(psycopg.OperationalError, match="permission denied for database"):
                psycopg.connect(binding(cluster, name, target=target).dsn)
    details, databases, _, _ = cluster
    with psycopg.connect(make_conninfo(**{**details, "dbname": databases["formal"]})) as admin:
        assert admin.execute("SELECT value FROM public.sentinel WHERE id=1").fetchone() == ("original",)


def test_role_cannot_create_database_role_or_table(cluster):
    for statement in ("CREATE DATABASE unauthorized", "CREATE ROLE unauthorized", "CREATE TABLE public.unauthorized(id int)"):
        with binding(cluster, "observer").connect() as connection:
            connection.autocommit = True
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                connection.execute(statement)


def test_runtime_rejects_admin_credentials(cluster):
    details, _, _, _ = cluster
    with pytest.raises(BoundaryError, match="nonprivileged"):
        DatabaseBinding(make_conninfo(**details), details["dbname"], details["user"]).connect()
