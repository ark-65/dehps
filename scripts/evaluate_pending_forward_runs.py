#!/usr/bin/env python
from __future__ import annotations

import sys
import argparse
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKER_ROOT = REPO_ROOT / "apps/worker-python"
sys.path.insert(0, str(WORKER_ROOT))

from dehps.forward_runtime.evaluation_service import ForwardEvaluationService  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Idempotently evaluate every persisted forward prediction whose draw is available."
    )
    parser.add_argument("--no-write-report", action="store_true")
    args = parser.parse_args(argv)
    result = ForwardEvaluationService().evaluate_pending(
        write_report=not args.no_write_report,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if int(result.get("failed_count") or 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
