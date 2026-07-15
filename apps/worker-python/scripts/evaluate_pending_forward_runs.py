from __future__ import annotations

import argparse
import json

from dehps.forward_runtime.evaluation_service import ForwardEvaluationService


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
