from __future__ import annotations

import argparse
import json
from pathlib import Path

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_balanced_design_feasibility_design import (
    FAILED_EXECUTION_ID,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY,
    build_prediction_v2_balanced_design_feasibility_recovery_manifest,
    load_prediction_v2_balanced_design_feasibility_source_contract,
    verify_prediction_v2_balanced_design_feasibility_source_bytes,
)
from dehps.research_os.repository import PostgresResearchOSRepository


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"manifest root must be an object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the exact zero-artifact recovery for the failed Prediction v2 "
            "balanced-design feasibility task."
        )
    )
    parser.add_argument("--control-plane-key", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if len({args.source.resolve(), args.output.resolve(), args.report.resolve()}) != 3:
        raise SystemExit("recovery source, output, and report must be distinct")

    source_contract = load_prediction_v2_balanced_design_feasibility_source_contract(
        ROOT_DIR / PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_SOURCE_CONTRACT_PATH
    )
    verify_prediction_v2_balanced_design_feasibility_source_bytes(
        root_dir=ROOT_DIR,
        contract=source_contract,
    )
    source = _load(args.source)
    source_task = next(
        (
            task
            for task in source.get("tasks", [])
            if task.get("task_key")
            == PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY
        ),
        None,
    )
    if (
        source_task is None
        or source_task.get("input_artifact_digests", [None])[0]
        != source_contract["artifact_digest"]
    ):
        raise SystemExit("corrected source manifest is not bound to source bytes")

    repository = PostgresResearchOSRepository()
    live = repository.load_manifest(control_plane_key=args.control_plane_key)
    events = repository.list_mainline_execution_events(
        control_plane_key=args.control_plane_key,
        task_key=PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_TASK_KEY,
        execution_id=FAILED_EXECUTION_ID,
    )
    artifacts = repository.list_mainline_artifacts(
        control_plane_key=args.control_plane_key,
        execution_id=FAILED_EXECUTION_ID,
    )
    output, report = build_prediction_v2_balanced_design_feasibility_recovery_manifest(
        live_payload=live.to_dict(include_digest=True),
        corrected_source_payload=source,
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
