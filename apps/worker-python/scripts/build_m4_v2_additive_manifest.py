from __future__ import annotations

import argparse
import json
from pathlib import Path

from dehps.artifacts import atomic_write_text
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)

NEW_TASK_KEYS = (
    "m4-v2-measurement-contract-design",
    "m4-v2-measurement-contract-design-replay",
    "m4-v2-branch-identifiability-preflight-design",
    "m4-v2-p2-6-1-raw-execution-replay",
    "m4-v2-p2-7-measurement-gate-replay",
    "m4-v2-p2-6-1-marginal-binding",
    "m4-v2-p2-6-1-marginal-decision-replay",
    "m4-p2-9-measurement-runtime-audit",
    "m4-v2-global-routing",
)
ARTIFACT_FACTS = (
    "m4-measurement-contract-v2:a0a367c99d7646cadc162bd9ceb0d5d73481cd7c26656bf02b40a99d9180095b",
    "m4-p2-6-1-marginal-binding-contract:dc45c140226a30d30f371f34628c05fa158b7dca86579f33431d2280a2987487",
    "m4-measurement-contract-v2-replay-fixture:92dddbf3528e61eb5997131c161b1ccb8c4d8bd20974d961d6f19c22b396300e",
    "m4-p2-9-runtime-audit-plan:c34836c3464bafd408c3eef1c87505040a69f79a5323bbb7d803bce9565be674",
)


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"manifest root must be an object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and verify an additive live-to-M4-v2 manifest migration."
    )
    parser.add_argument("--live", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run-artifact", type=Path, required=True)
    parser.add_argument("--guard-decision", type=Path, required=True)
    args = parser.parse_args()
    guard = _load(args.guard_decision)
    if (
        guard.get("state") != "SAFE_TO_RELEASE_SLOT"
        or guard.get("publish_slot_event") is not True
        or guard.get("result_blind") is not True
    ):
        raise SystemExit("guard decision does not authorize slot-event migration")
    manifest, dry_run = build_additive_m4_v2_manifest(
        live_payload=_load(args.live),
        source_payload=_load(args.source),
        allowlisted_new_goal_keys=("M4_MEASUREMENT_RUNTIME_AUDIT",),
        allowlisted_new_task_keys=NEW_TASK_KEYS,
        allowlisted_revised_task_keys=("m4-p3-strict-historical-walk-forward",),
        add_artifact_facts=ARTIFACT_FACTS,
        add_external_events=("m4-runtime-slot:p2-6-1-released",),
    )
    atomic_write_text(
        args.output,
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    atomic_write_text(
        args.dry_run_artifact,
        json.dumps(dry_run, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    print(json.dumps(dry_run, sort_keys=True))


if __name__ == "__main__":
    main()
