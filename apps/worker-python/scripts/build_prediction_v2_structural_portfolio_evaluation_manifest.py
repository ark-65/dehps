from __future__ import annotations

import argparse
import json
from pathlib import Path

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_structural_portfolio_evaluation import (
    PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_CAPABILITY,
    PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY,
    PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY,
    load_prediction_v2_structural_portfolio_evaluation_source_contract,
    verify_prediction_v2_structural_portfolio_evaluation_source_bytes,
)
from dehps.research_os.repository import PostgresResearchOSRepository


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"manifest root must be an object: {path}")
    return value


def _task(payload: dict, task_key: str) -> dict:
    matches = [
        item for item in payload.get("tasks", []) if item.get("task_key") == task_key
    ]
    if len(matches) != 1:
        raise SystemExit(f"task is not unique: {task_key}")
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the exact additive structural-evaluation migration."
    )
    live_source = parser.add_mutually_exclusive_group(required=True)
    live_source.add_argument("--live", type=Path)
    live_source.add_argument("--control-plane-key")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run-artifact", type=Path, required=True)
    args = parser.parse_args()
    resolved_inputs = {args.source.resolve()}
    if args.live is not None:
        resolved_inputs.add(args.live.resolve())
    resolved_outputs = {args.output.resolve(), args.dry_run_artifact.resolve()}
    if len(resolved_outputs) != 2 or resolved_inputs.intersection(resolved_outputs):
        raise SystemExit("migration outputs must be distinct from inputs")

    live = (
        _load(args.live)
        if args.live is not None
        else PostgresResearchOSRepository().export_manifest(
            control_plane_key=str(args.control_plane_key)
        )
    )
    source = _load(args.source)
    live_evaluation = _task(
        live, PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY
    )
    source_evaluation = _task(
        source, PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY
    )
    source_route = _task(source, PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY)
    if (
        any(
            item.get("task_key") == PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY
            for item in live.get("tasks", [])
        )
        or live_evaluation.get("requested_capability") is not None
        or live_evaluation.get("input_artifact_digests")
        or live_evaluation.get("status") != "draft"
        or live_evaluation.get("completion_classification") != "INTEGRATION_PENDING"
        or source_evaluation.get("requested_capability")
        != PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_CAPABILITY
        or len(source_evaluation.get("input_artifact_digests", [])) != 6
        or source_route.get("requested_capability") is not None
        or source_route.get("input_artifact_digests")
        or source_route.get("status") != "draft"
        or source_route.get("completion_classification") != "INTEGRATION_PENDING"
    ):
        raise SystemExit(
            "structural portfolio evaluation is not the exact unstarted revision target"
        )
    source_contract = (
        load_prediction_v2_structural_portfolio_evaluation_source_contract(
            ROOT_DIR
            / PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_SOURCE_CONTRACT_PATH
        )
    )
    verify_prediction_v2_structural_portfolio_evaluation_source_bytes(
        root_dir=ROOT_DIR,
        contract=source_contract,
    )
    if (
        source_evaluation["input_artifact_digests"][0]
        != source_contract["artifact_digest"]
    ):
        raise SystemExit("structural portfolio evaluation source identity changed")

    source_fact = (
        "prediction-v2-structural-portfolio-evaluation-source:"
        f"{source_contract['artifact_digest']}"
    )
    manifest, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY,),
        allowlisted_revised_task_keys=(
            PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    if (
        dry_run["new_task_keys"] != [PREDICTION_V2_STRUCTURAL_ROUTE_DECISION_TASK_KEY]
        or dry_run["revised_task_keys"]
        != [PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY]
        or dry_run["existing_state_regressions"] != 0
        or dry_run["existing_fact_deletions"] != 0
        or dry_run["unallowlisted_definition_rewrites"] != 0
    ):
        raise SystemExit("structural portfolio evaluation migration scope changed")
    atomic_write_text(
        args.dry_run_artifact,
        json.dumps(dry_run, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    atomic_write_text(
        args.output,
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    print(json.dumps(dry_run, sort_keys=True))


if __name__ == "__main__":
    main()
