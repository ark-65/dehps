from __future__ import annotations

import os
import uuid
from pathlib import Path

import psycopg
import pytest
from dehps.config import get_settings
from psycopg import sql

ROOT = Path(__file__).resolve().parents[3]
MIGRATION_003 = (
    ROOT / "infra/postgres/migrations/003_m4_isolated_24h_challenger_v11.sql"
)
MIGRATION_004 = (
    ROOT
    / "infra/postgres/migrations/004_m4_isolated_v11_runtime_migration_attestation_input.sql"
)
OLD_TYPES = (
    "m4_isolated_24h_challenger_source_contract_v11",
    "M4IsolatedDatabaseSchemaIdentityV11",
    "M4IsolatedHistorySchemaInputV11",
    "M4IsolatedHistoryContentInputV11",
    "M4IsolatedAuditedDrawInputV11",
)
NEW_TYPE = "M4IsolatedRuntimeMigrationAttestationInputV11"


def _migration(path: Path, schema: str) -> str:
    return path.read_text(encoding="utf-8").replace("m4_isolated_v11", schema)


def _constraint_definition(connection: psycopg.Connection, schema: str) -> str:
    return str(
        connection.execute(
            "SELECT pg_get_constraintdef(c.oid) "
            "FROM pg_constraint c "
            "WHERE c.conrelid=%s::regclass "
            "AND c.conname='registered_inputs_artifact_type_check' "
            "AND c.contype='c'",
            (f"{schema}.registered_inputs",),
        ).fetchone()[0]
    )


def _insert_input(
    connection: psycopg.Connection,
    schema: str,
    *,
    digest: str,
    artifact_type: str,
) -> None:
    source_path = (
        "configs/research-os/m4-isolated-24h-challenger-source-v11.json"
        if artifact_type == OLD_TYPES[0]
        else None
    )
    connection.execute(
        sql.SQL(
            "INSERT INTO {}.registered_inputs ("
            "artifact_digest,artifact_type,artifact_json,parent_digests_json,"
            "git_commit,source_path,content_sha256) "
            "VALUES (%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)"
        ).format(sql.Identifier(schema)),
        (
            digest,
            artifact_type,
            "{}",
            "[]",
            "a" * 40,
            source_path,
            "b" * 64,
        ),
    )


def _snapshot(connection: psycopg.Connection, schema: str) -> list[tuple[object, ...]]:
    return list(
        connection.execute(
            sql.SQL(
                "SELECT artifact_digest,artifact_type,artifact_json,"
                "parent_digests_json,git_commit,source_path,content_sha256,"
                "registered_at FROM {}.registered_inputs ORDER BY artifact_digest"
            ).format(sql.Identifier(schema))
        ).fetchall()
    )


def test_migration_is_exact_atomic_idempotent_and_dml_free() -> None:
    value = MIGRATION_004.read_text(encoding="utf-8")
    assert value.startswith("BEGIN;\n")
    assert value.endswith("COMMIT;\n")
    assert (
        "LOCK TABLE m4_isolated_v11.registered_inputs IN ACCESS EXCLUSIVE MODE" in value
    )
    assert "constraint_count <> 1" in value
    assert "current_definition = old_definition" in value
    assert "current_definition <> new_definition" in value
    assert "DROP CONSTRAINT registered_inputs_artifact_type_check" in value
    assert "ADD CONSTRAINT registered_inputs_artifact_type_check" in value
    assert all(item in value for item in (*OLD_TYPES, NEW_TYPE))
    upper = value.upper()
    assert "UPDATE M4_ISOLATED_V11.REGISTERED_INPUTS" not in upper
    assert "DELETE FROM M4_ISOLATED_V11.REGISTERED_INPUTS" not in upper
    assert "INSERT INTO M4_ISOLATED_V11.REGISTERED_INPUTS" not in upper


@pytest.mark.skipif(
    os.getenv("DEHPS_TEST_POSTGRES") != "1",
    reason="set DEHPS_TEST_POSTGRES=1 for isolated PostgreSQL acceptance",
)
def test_migration_accepts_fresh_and_existing_postgresql_states() -> None:
    database_url = os.getenv("DEHPS_TEST_DATABASE_URL", get_settings().database_url)
    schemas = [f"m4_isolated_v11_migration_{uuid.uuid4().hex}" for _ in range(4)]
    with psycopg.connect(database_url, autocommit=True) as connection:
        try:
            fresh, existing, missing, unexpected = schemas
            connection.execute(_migration(MIGRATION_003, fresh))
            connection.execute(_migration(MIGRATION_004, fresh))
            for index, artifact_type in enumerate((*OLD_TYPES, NEW_TYPE), start=1):
                _insert_input(
                    connection,
                    fresh,
                    digest=f"{index:064x}",
                    artifact_type=artifact_type,
                )
            with pytest.raises(psycopg.errors.CheckViolation):
                _insert_input(
                    connection,
                    fresh,
                    digest="f" * 64,
                    artifact_type="M4IsolatedUnauthorizedInputV11",
                )

            connection.execute(_migration(MIGRATION_003, existing))
            for index, artifact_type in enumerate(OLD_TYPES, start=10):
                _insert_input(
                    connection,
                    existing,
                    digest=f"{index:064x}",
                    artifact_type=artifact_type,
                )
            before = _snapshot(connection, existing)
            connection.execute(_migration(MIGRATION_004, existing))
            after_once = _snapshot(connection, existing)
            connection.execute(_migration(MIGRATION_004, existing))
            after_twice = _snapshot(connection, existing)
            assert before == after_once == after_twice
            assert NEW_TYPE in _constraint_definition(connection, existing)

            connection.execute(_migration(MIGRATION_003, missing))
            connection.execute(
                sql.SQL(
                    "ALTER TABLE {}.registered_inputs DROP CONSTRAINT "
                    "registered_inputs_artifact_type_check"
                ).format(sql.Identifier(missing))
            )
            with pytest.raises(psycopg.errors.RaiseException):
                connection.execute(_migration(MIGRATION_004, missing))
            connection.rollback()
            assert (
                connection.execute(
                    "SELECT count(*) FROM pg_constraint "
                    "WHERE conrelid=%s::regclass "
                    "AND conname='registered_inputs_artifact_type_check'",
                    (f"{missing}.registered_inputs",),
                ).fetchone()[0]
                == 0
            )

            connection.execute(_migration(MIGRATION_003, unexpected))
            connection.execute(
                sql.SQL(
                    "ALTER TABLE {}.registered_inputs DROP CONSTRAINT "
                    "registered_inputs_artifact_type_check"
                ).format(sql.Identifier(unexpected))
            )
            connection.execute(
                sql.SQL(
                    "ALTER TABLE {}.registered_inputs ADD CONSTRAINT "
                    "registered_inputs_artifact_type_check "
                    "CHECK (artifact_type='M4IsolatedUnexpectedInputV11')"
                ).format(sql.Identifier(unexpected))
            )
            unexpected_definition = _constraint_definition(connection, unexpected)
            with pytest.raises(psycopg.errors.RaiseException):
                connection.execute(_migration(MIGRATION_004, unexpected))
            connection.rollback()
            assert (
                _constraint_definition(connection, unexpected) == unexpected_definition
            )
        finally:
            connection.rollback()
            with psycopg.connect(database_url, autocommit=True) as cleanup:
                for schema in schemas:
                    cleanup.execute(
                        sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                            sql.Identifier(schema)
                        )
                    )
