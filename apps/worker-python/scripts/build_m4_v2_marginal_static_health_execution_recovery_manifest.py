from __future__ import annotations

import argparse
import json
from pathlib import Path

from dehps.artifacts import atomic_write_text
from dehps.research_os.information_theory.measurement_system_v2.raw_replay_recovery import (
    MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_EXECUTION_ID,
    MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY,
    build_marginal_static_health_execution_recovery_manifest,
)
from dehps.research_os.repository import PostgresResearchOSRepository


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the exact one-task M4 v2 marginal-static health-execution "
            "recovery manifest."
        )
    )
    parser.add_argument("--control-plane-key", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    repository = PostgresResearchOSRepository()
    live = repository.load_manifest(control_plane_key=args.control_plane_key)
    events = repository.list_mainline_execution_events(
        control_plane_key=args.control_plane_key,
        task_key=MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY,
        execution_id=MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_EXECUTION_ID,
    )
    artifacts = repository.list_mainline_artifacts(
        control_plane_key=args.control_plane_key,
        execution_id=MARGINAL_STATIC_HEALTH_EXECUTION_FAILED_EXECUTION_ID,
    )
    output, report = build_marginal_static_health_execution_recovery_manifest(
        live_payload=live.to_dict(include_digest=True),
        execution_events=events,
        execution_artifacts=artifacts,
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
