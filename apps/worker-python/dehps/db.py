from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg

from dehps.config import get_settings


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(get_settings().database_url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

