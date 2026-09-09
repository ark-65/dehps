"""Explicit connection admission, in addition to database-enforced privileges."""
from __future__ import annotations

from dataclasses import dataclass, field
import os

import psycopg

from .context import BoundaryError


@dataclass(frozen=True)
class DatabaseBinding:
    dsn: str = field(repr=False)
    database: str
    role: str

    def connect(self):
        # libpq defaults/environment (service files, ambient user/password, etc.)
        # must not silently select the production connection.
        supplied = psycopg.conninfo.conninfo_to_dict(self.dsn)
        if any(os.environ.get(name) for name in ("PGSERVICE", "PGSERVICEFILE", "PGOPTIONS", "PGHOSTADDR")):
            raise BoundaryError("ambient libpq service, options or host override is forbidden")
        required = {"host", "port", "dbname", "user", "password"}
        if not required.issubset(supplied) or not all(supplied[k] for k in required):
            raise BoundaryError("explicit host, port, dbname, user and password required")
        if set(supplied) - (required | {"sslmode", "sslrootcert"}):
            raise BoundaryError("unsupported connection option")
        if supplied["dbname"] != self.database or supplied["user"] != self.role:
            raise BoundaryError("configured database identity mismatch")
        connection = psycopg.connect(self.dsn, connect_timeout=5)
        try:
            with connection.transaction():
                identity = connection.execute("""
                    SELECT current_database(), current_user, session_user,
                           r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolbypassrls,
                           pg_has_role(current_user, d.datdba, 'MEMBER')
                    FROM pg_roles r JOIN pg_database d ON d.datname=current_database()
                    WHERE r.rolname=current_user
                    """).fetchone()
                if (identity is None or identity[:3] != (self.database, self.role, self.role)
                        or any(identity[3:])):
                    raise BoundaryError("runtime role must be nonprivileged and not a database owner")
                inherited = connection.execute("""
                    SELECT EXISTS (SELECT 1 FROM pg_roles r
                        WHERE (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolbypassrls)
                        AND pg_has_role(current_user, r.oid, 'MEMBER'))
                    """).fetchone()[0]
                if inherited:
                    raise BoundaryError("runtime role can assume a privileged role")
            return connection
        except BaseException:
            connection.close()
            raise
