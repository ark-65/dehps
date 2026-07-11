from __future__ import annotations

import argparse
import json

from dehps.crawler.ssq_conflict_resolution import resolve_ssq_data_conflict
from dehps.db import get_connection


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manually resolve an SSQ draw conflict while preserving audit evidence."
    )
    parser.add_argument("--conflict-id", type=int, required=True)
    parser.add_argument("--accept", choices=("existing", "incoming"), required=True)
    parser.add_argument("--resolution-note", required=True)
    parser.add_argument("--resolved-by", required=True)
    args = parser.parse_args()

    with get_connection() as conn:
        result = resolve_ssq_data_conflict(
            conn,
            conflict_id=args.conflict_id,
            action=args.accept,
            resolution_note=args.resolution_note,
            resolved_by=args.resolved_by,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
