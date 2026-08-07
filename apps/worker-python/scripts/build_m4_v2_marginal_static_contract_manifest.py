from __future__ import annotations

import argparse
import json
from pathlib import Path

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_contract import (
    MARGINAL_STATIC_CONTRACT_FREEZE_CAPABILITY,
    MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY,
    MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY,
    MARGINAL_STATIC_SOURCE_CONTRACT_PATH,
    load_marginal_static_source_contract,
    verify_marginal_static_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)


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
        description=(
            "Build the exact additive M4-v2 marginal-static contract migration."
        )
    )
    parser.add_argument("--live", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run-artifact", type=Path, required=True)
    args = parser.parse_args()
    resolved_inputs = {args.live.resolve(), args.source.resolve()}
    resolved_outputs = {args.output.resolve(), args.dry_run_artifact.resolve()}
    if len(resolved_outputs) != 2 or resolved_inputs.intersection(resolved_outputs):
        raise SystemExit("migration outputs must be distinct from inputs")

    live = _load(args.live)
    source = _load(args.source)
    live_contract = _task(live, MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY)
    source_contract_task = _task(source, MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY)
    _task(source, MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY)
    if (
        live_contract.get("requested_capability") is not None
        or live_contract.get("input_artifact_digests")
        or live_contract.get("status") != "draft"
        or live_contract.get("completion_classification") != "INTEGRATION_PENDING"
        or source_contract_task.get("requested_capability")
        != MARGINAL_STATIC_CONTRACT_FREEZE_CAPABILITY
        or len(source_contract_task.get("input_artifact_digests", [])) != 8
    ):
        raise SystemExit(
            "marginal-static contract task is not the exact unstarted revision target"
        )
    source_contract = load_marginal_static_source_contract(
        ROOT_DIR / MARGINAL_STATIC_SOURCE_CONTRACT_PATH
    )
    verify_marginal_static_source_bytes(
        root_dir=ROOT_DIR,
        contract=source_contract,
    )
    if source_contract_task["input_artifact_digests"][0] != source_contract[
        "artifact_digest"
    ]:
        raise SystemExit("marginal-static source contract identity changed")

    source_fact = (
        "m4-v2-marginal-static-contract-freeze-source:"
        f"{source_contract['artifact_digest']}"
    )
    manifest, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY,),
        allowlisted_revised_task_keys=(MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY,),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    if (
        dry_run["new_task_keys"] != [MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY]
        or dry_run["revised_task_keys"]
        != [MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY]
        or dry_run["existing_state_regressions"] != 0
        or dry_run["existing_fact_deletions"] != 0
        or dry_run["unallowlisted_definition_rewrites"] != 0
    ):
        raise SystemExit("marginal-static contract migration scope changed")
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
