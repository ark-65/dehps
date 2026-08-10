from __future__ import annotations

import argparse
import json
from pathlib import Path

from dehps.artifacts import atomic_write_text
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.research_os.structural_utility.m4_p3_result_blind_preregistration import (
    M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
    M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
)
from dehps.research_os.structural_utility.m4_p3_result_blind_preregistration_recovery import (
    FAILED_EXECUTION_ID,
    build_m4_p3_result_blind_preregistration_recovery_manifest,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the exact recovery for the failed M4-P3 zero-work "
            "preregistration completion projection."
        )
    )
    parser.add_argument("--control-plane-key", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.report.resolve():
        raise SystemExit("recovery manifest and report outputs must be distinct")

    repository = PostgresResearchOSRepository()
    live = repository.load_manifest(control_plane_key=args.control_plane_key)
    events = repository.list_mainline_execution_events(
        control_plane_key=args.control_plane_key,
        task_key=M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
        execution_id=FAILED_EXECUTION_ID,
    )
    registrations = repository.list_mainline_artifacts(
        control_plane_key=args.control_plane_key,
        execution_id=FAILED_EXECUTION_ID,
    )
    output, report = build_m4_p3_result_blind_preregistration_recovery_manifest(
        live_payload=live.to_dict(include_digest=True),
        execution_events=events,
        execution_artifacts=registrations,
    )
    recovered = live.from_dict(output)
    resolutions = {
        item.task_key: item.status.value
        for item in ResearchOSControlPlane().resolve(recovered).resolutions
    }
    ready = sorted(key for key, status in resolutions.items() if status == "ready")
    if (
        ready != [M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY]
        or resolutions[M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY] != "external_wait"
    ):
        raise SystemExit("M4-P3 preregistration recovery Ready Queue changed")
    report["ready_task_keys"] = ready
    report["blind_execution_resolver_status"] = resolutions[
        M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY
    ]
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
