"""Authenticated control-domain admission; no ambient settings or actor labels.

The database administrator installs the SQL migration and provisions identities.
This client cannot create/approve identities or install its own permissions.
Returned execution IDs are audit references, not transferable bearer tokens.
"""
from dataclasses import dataclass
from datetime import datetime

from psycopg.types.json import Jsonb

from .database import DatabaseBinding


@dataclass(frozen=True)
class AuthorityClient:
    database: DatabaseBinding

    def request(self, payload: dict, release_sha256: str, *, label: str = "") -> int:
        with self.database.connect() as connection:
            return connection.execute(
                "SELECT execution_authority.request_create(%s,%s,%s)",
                (Jsonb(payload), release_sha256, label),
            ).fetchone()[0]

    def get(self, request_id: int) -> dict:
        with self.database.connect() as connection:
            return connection.execute(
                "SELECT execution_authority.request_get(%s)", (request_id,),
            ).fetchone()[0]

    def approve(self, request_id: int, content_sha256: str, release_sha256: str,
                expires_at: datetime, *, label: str = "") -> None:
        with self.database.connect() as connection:
            connection.execute(
                "SELECT execution_authority.approve(%s,%s,%s,%s,%s)",
                (request_id, content_sha256, release_sha256, expires_at, label),
            )

    def revoke(self, request_id: int) -> None:
        with self.database.connect() as connection:
            connection.execute("SELECT execution_authority.revoke(%s)", (request_id,))

    def begin(self, request_id: int, content_sha256: str, release_sha256: str,
              *, label: str = "") -> int:
        with self.database.connect() as connection:
            return connection.execute(
                "SELECT execution_authority.begin_execution(%s,%s,%s,%s)",
                (request_id, content_sha256, release_sha256, label),
            ).fetchone()[0]

    def reauthorize(self, execution_id: int, content_sha256: str, release_sha256: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "SELECT execution_authority.reauthorize(%s,%s,%s)",
                (execution_id, content_sha256, release_sha256),
            )
