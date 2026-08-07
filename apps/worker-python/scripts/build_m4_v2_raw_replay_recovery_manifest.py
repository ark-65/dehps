from __future__ import annotations

import argparse
import json
from pathlib import Path

from dehps.artifacts import atomic_write_text
from dehps.research_os.information_theory.measurement_system_v2.raw_replay_recovery import (
    RAW_REPLAY_TASK_KEY,
    build_raw_replay_recovery_manifest,
)
from dehps.research_os.repository import PostgresResearchOSRepository


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the exact one-task Measurement v2 raw-replay recovery manifest."
    )
    parser.add_argument("--control-plane-key", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    repository = PostgresResearchOSRepository()
    live = repository.load_manifest(control_plane_key=args.control_plane_key)
    events = repository.list_mainline_execution_events(
        control_plane_key=args.control_plane_key,
        task_key=RAW_REPLAY_TASK_KEY,
    )
    output, report = build_raw_replay_recovery_manifest(
        live_payload=live.to_dict(include_digest=True),
        execution_events=events,
    )
    atomic_write_text(
        args.output,
        json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    atomic_write_text(
        args.report,
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
