from __future__ import annotations

import json

from dehps.db import get_connection
from dehps.storage.postgres_store import DEFAULT_SSQ_DRAW_SITE
from dehps.storage.postgres_store import ensure_ssq_draw_site_schema
from dehps.storage.postgres_store import load_active_ssq_draw_site
from dehps.storage.postgres_store import upsert_ssq_draw_site


def main() -> None:
    with get_connection() as conn:
        ensure_ssq_draw_site_schema(conn)
        upsert_ssq_draw_site(conn, DEFAULT_SSQ_DRAW_SITE)
        site = load_active_ssq_draw_site(conn)
    print(json.dumps(site, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
