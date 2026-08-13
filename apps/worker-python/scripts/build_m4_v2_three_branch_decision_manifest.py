from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dehps.research_os.information_theory.measurement_system_v2.migration import (
    M4_V2_FAILED_REPLAY_TASK_KEY,
    M4_V2_REPLAY_RECOVERY_LINEAGE,
    M4_V2_REPLAY_RECOVERY_LINEAGE_DIGEST,
    M4_V2_REPLAY_RECOVERY_TASK_KEY,
    build_failed_replay_recovery_manifest,
    require_sha256_digest,
)

REPLAY_TASK_KEY = M4_V2_FAILED_REPLAY_TASK_KEY
REPLAY_RECOVERY_TASK_KEY = M4_V2_REPLAY_RECOVERY_TASK_KEY
REPLAY_RECOVERY_LINEAGE = M4_V2_REPLAY_RECOVERY_LINEAGE
REPLAY_RECOVERY_LINEAGE_DIGEST = M4_V2_REPLAY_RECOVERY_LINEAGE_DIGEST
REPLAY_CAPABILITY = "m4_v2_marginal_static_historical_branch_decision_replay"
REPLAY_FACT = (
    "m4-v2-historical-branch-decision-replay:M4_MEASUREMENT_CONTRACT_V2:"
    "MARGINAL_STATIC:VERIFIED"
)


def build_m4_v2_three_branch_decision_manifest(
    live_payload: Mapping[str, Any],
    source_contract_digest: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the append-only recovery for the failed MARGINAL_STATIC replay."""

    source_digest = require_sha256_digest(
        source_contract_digest,
        field_name="marginal_identity_adoption_source_contract_digest",
    )
    return build_failed_replay_recovery_manifest(
        live_payload=live_payload,
        source_contract_digest=source_digest,
    )


build_manifest = build_m4_v2_three_branch_decision_manifest


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON root must be an object: {path}")
    return value


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the additive MARGINAL_STATIC replay recovery manifest."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", type=Path, required=True)
    args = parser.parse_args()
    inputs = {args.source.resolve(), args.input.resolve()}
    outputs = {args.output.resolve(), args.dry_run.resolve()}
    if len(outputs) != 2 or inputs.intersection(outputs):
        raise SystemExit("builder outputs must be distinct from inputs")
    source = _load(args.source)
    manifest, dry_run = build_manifest(
        _load(args.input),
        require_sha256_digest(
            source.get("artifact_digest"), field_name="source.artifact_digest"
        ),
    )
    _write(args.dry_run, dry_run)
    _write(args.output, manifest)
    print(json.dumps(dry_run, sort_keys=True))


if __name__ == "__main__":
    main()
