from __future__ import annotations

import argparse
import json
from pathlib import Path

from dehps.artifacts import atomic_write_text
from dehps.research_os.information_theory.measurement_system_v2.superseding_slot import (
    build_p263_slot_release_manifest,
)


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON root must be an object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build a verified additive manifest that appends only the P2.6.1 "
            "runtime-slot release event after P2.6.3 superseding acceptance."
        )
    )
    parser.add_argument("--live", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--eligibility", type=Path, required=True)
    parser.add_argument("--guard-decision", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run-artifact", type=Path, required=True)
    args = parser.parse_args()
    read_paths = {
        args.live.resolve(),
        args.source.resolve(),
        args.eligibility.resolve(),
        args.guard_decision.resolve(),
    }
    write_paths = {args.output.resolve(), args.dry_run_artifact.resolve()}
    if len(write_paths) != 2 or read_paths.intersection(write_paths):
        raise SystemExit("migration outputs must be distinct from all inputs")

    manifest, dry_run = build_p263_slot_release_manifest(
        live_payload=_load(args.live),
        source_payload=_load(args.source),
        eligibility_payload=_load(args.eligibility),
        guard_payload=_load(args.guard_decision),
    )
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
