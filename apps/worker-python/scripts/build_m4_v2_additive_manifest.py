from __future__ import annotations

import argparse
import json
from pathlib import Path

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.runtime_audit import (
    load_runtime_audit_plan,
)
from dehps.research_os.information_theory.measurement_system_v2.terminal_guard import (
    CompletionGuardError,
    validate_slot_release_guard_artifact,
)
from dehps.research_os.information_theory.measurement_validation.golden_reference import (
    build_canonical_executor_event_attestation,
    build_canonical_executor_fingerprint,
)
from dehps.research_os.information_theory.measurement_validation.source_integrity import (
    preflight_source_integrity,
)

NEW_TASK_KEYS = (
    "m4-v2-measurement-contract-design",
    "m4-v2-measurement-contract-design-replay",
    "m4-v2-branch-identifiability-preflight-design",
    "m4-v2-p2-6-1-raw-execution-replay",
    "m4-v2-p2-7-measurement-gate-replay",
    "m4-v2-p2-6-1-marginal-binding",
    "m4-v2-p2-6-1-marginal-decision-replay",
    "m4-p2-9-golden-reference-freeze",
    "m4-p2-9-measurement-runtime-audit",
    "m4-v2-global-routing",
)
ARTIFACT_FACTS = (
    "m4-measurement-contract-v2:a0a367c99d7646cadc162bd9ceb0d5d73481cd7c26656bf02b40a99d9180095b",
    "m4-p2-6-1-marginal-binding-contract:dc45c140226a30d30f371f34628c05fa158b7dca86579f33431d2280a2987487",
    "m4-measurement-contract-v2-replay-fixture:92dddbf3528e61eb5997131c161b1ccb8c4d8bd20974d961d6f19c22b396300e",
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
    parser.add_argument("--executor-attestation", type=Path, required=True)
    parser.add_argument("--runtime-audit-plan", type=Path, required=True)
    parser.add_argument("--guard-decision", type=Path, required=True)
    args = parser.parse_args()
    read_paths = {
        args.live.resolve(),
        args.source.resolve(),
        args.runtime_audit_plan.resolve(),
        args.guard_decision.resolve(),
    }
    write_paths = {
        args.output.resolve(),
        args.dry_run_artifact.resolve(),
        args.executor_attestation.resolve(),
    }
    if len(write_paths) != 3 or read_paths.intersection(write_paths):
        raise SystemExit(
            "migration outputs must be distinct and must not overwrite inputs"
        )
    try:
        validate_slot_release_guard_artifact(_load(args.guard_decision))
    except CompletionGuardError as exc:
        raise SystemExit(
            "guard decision does not authorize slot-event migration"
        ) from exc
    runtime_audit_plan = load_runtime_audit_plan(args.runtime_audit_plan)
    verified_source_identity = preflight_source_integrity(
        root_dir=ROOT_DIR,
        runtime_plan=runtime_audit_plan,
    )
    executor_attestation = build_canonical_executor_event_attestation(
        runtime_audit_plan,
        executor_fingerprint=build_canonical_executor_fingerprint(),
        construction_source_integrity_identity=verified_source_identity,
    )
    if (
        executor_attestation.get("construction_source_integrity_identity")
        != verified_source_identity
    ):
        raise SystemExit("canonical executor source integrity preflight changed")
    executor_event = str(executor_attestation["external_event"])
    executor_artifact_fact = (
        "m4-canonical-executor-attestation:"
        f"{executor_attestation['artifact_digest']}"
    )
    runtime_plan_artifact_fact = (
        "m4-p2-9-runtime-audit-plan:" f"{runtime_audit_plan['artifact_digest']}"
    )
    manifest, dry_run = build_additive_m4_v2_manifest(
        live_payload=_load(args.live),
        source_payload=_load(args.source),
        allowlisted_new_goal_keys=("M4_MEASUREMENT_RUNTIME_AUDIT",),
        allowlisted_new_task_keys=NEW_TASK_KEYS,
        allowlisted_revised_task_keys=("m4-p3-strict-historical-walk-forward",),
        add_artifact_facts=(
            *ARTIFACT_FACTS,
            runtime_plan_artifact_fact,
            executor_artifact_fact,
        ),
        add_external_events=(
            "m4-runtime-slot:p2-6-1-released",
            executor_event,
        ),
    )
    atomic_write_text(
        args.executor_attestation,
        json.dumps(
            executor_attestation,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )
    atomic_write_text(
        args.dry_run_artifact,
        json.dumps(dry_run, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    # The manifest is the commit marker: publish it only after both audit
    # artifacts are durable, so a crash cannot expose an unproved event.
    atomic_write_text(
        args.output,
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    print(json.dumps(dry_run, sort_keys=True))


if __name__ == "__main__":
    main()
