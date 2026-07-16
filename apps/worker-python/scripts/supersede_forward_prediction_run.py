from __future__ import annotations

import argparse
import json

from dehps.db import get_connection
from dehps.storage.postgres_store import supersede_forward_prediction_run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Explicitly supersede one active official forward prediction run."
    )
    parser.add_argument("--prediction-run-key", required=True)
    parser.add_argument("--confirm-prediction-run-key", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    if args.confirm_prediction_run_key != args.prediction_run_key:
        raise ValueError("confirmation does not match --prediction-run-key")
    with get_connection() as conn:
        result = supersede_forward_prediction_run(
            conn,
            prediction_run_key=args.prediction_run_key,
            actor=args.actor,
            reason=args.reason,
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
