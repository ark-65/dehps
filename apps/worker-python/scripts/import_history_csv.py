from __future__ import annotations

import argparse
from pathlib import Path

from dehps.crawler.ssq_client import CsvSsqDataSource
from dehps.crawler.ssq_parser import validate_ssq_draw
from dehps.db import get_connection
from dehps.storage.postgres_store import upsert_ssq_draw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    args = parser.parse_args()

    source = CsvSsqDataSource(Path(args.file))
    rows = source.fetch_history()
    summary = {"inserted": 0, "skipped": 0, "conflict": 0}
    with get_connection() as conn:
        for row in rows:
            draw = validate_ssq_draw(row)
            result = upsert_ssq_draw(conn, draw, "csv")
            summary[result] = summary.get(result, 0) + 1
    print(summary)


if __name__ == "__main__":
    main()

