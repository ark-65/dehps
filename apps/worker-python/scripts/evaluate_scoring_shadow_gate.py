from __future__ import annotations

import argparse
import json
from pathlib import Path

from dehps.scoring_kernel.shadow import (
    DEFAULT_PRODUCTION_LINES,
    shadow_promotion_readiness,
    verify_shadow_evidence,
)


def load_evidence(directory: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(directory.glob("shadow-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        verify_shadow_evidence(payload)
        rows.append(payload)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate sealed NumPy/Numba shadow evidence without promoting a backend.",
    )
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--required-issue-count", type=int, default=3)
    parser.add_argument(
        "--required-line",
        action="append",
        dest="required_lines",
        help="Required line key; repeat for multiple lines.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit 2 when evidence is not ready for independent approval.",
    )
    args = parser.parse_args(argv)

    rows = load_evidence(args.artifact_dir)
    result = shadow_promotion_readiness(
        rows,
        required_issue_count=args.required_issue_count,
        required_line_keys=tuple(args.required_lines or DEFAULT_PRODUCTION_LINES),
    )
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    if args.require_ready and not result["evidence_sufficient"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
