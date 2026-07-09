from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.db import get_connection
from dehps.optimization.near_dynamic_report import (
    default_output_dir,
    write_near_dynamic_line_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the rolling near dynamic KDJ line report.")
    parser.add_argument("--output-dir", type=Path, default=default_output_dir())
    args = parser.parse_args()

    with get_connection() as conn:
        payload = write_near_dynamic_line_report(conn, output_dir=args.output_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
