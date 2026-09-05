"""Export one explicitly opened issue; cannot dispatch or deliver anything."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from dehps.config import ROOT_DIR
from dehps.prediction.error_learning import build_preview, capture_decision, missing_input_preview, write_immutable
from dehps.prediction.error_learning_io import (
    MissingFrozenInputError, ScopedReader, load_frozen, load_opened, read_only_connection,
)
from dehps.research_os.repository import PostgresResearchOSRepository


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--phase", choices=("record", "preview"), default="preview")
    args = parser.parse_args()
    source_root, output = args.source_root.resolve(), args.output.resolve()
    if output == source_root or output.is_relative_to(source_root / "runtime/research-os/mainline"):
        parser.error("output must not overwrite registered mainline artifacts")
    if output.exists():
        parser.error("use a new output directory; existing evidence is never overwritten")
    # Reuse the explicit source checkout's connection configuration in a clean
    # worktree. Credentials are neither printed nor copied into any sidecar.
    load_dotenv(source_root / ".env", override=False)
    reader = ScopedReader(PostgresResearchOSRepository(connection_factory=read_only_connection),
                          issue=args.issue, post=args.phase == "preview")
    # For a post-draw request, open only the already-approved report first.
    opened = load_opened(reader, issue=args.issue, source_root=source_root) if args.phase == "preview" else None
    try:
        inputs = load_frozen(reader, issue=args.issue, source_root=source_root, code_root=ROOT_DIR)
    except MissingFrozenInputError as exc:
        if opened is None:
            raise
        preview = missing_input_preview(opened[3], missing=[str(exc)])
        output.mkdir(parents=True)
        write_immutable(output / "previews", preview)
        (output / "preview.txt").write_text(preview["text"], encoding="utf-8")
        (output / "preview.html").write_text(preview["html"], encoding="utf-8")
        print(json.dumps({"issue": args.issue, "status": preview["status"], "missing": preview["missing"]}))
        return
    record = capture_decision(inputs, code_root=ROOT_DIR)
    output.mkdir(parents=True)
    decision_path = write_immutable(output / "decisions", record)
    result = {"issue": args.issue, "decision": str(decision_path),
              "record_mode": record["body"]["record_mode"]}
    if opened:
        bundle, payout, available_at, _ = opened
        preview = build_preview(record, bundle, payout, code_root=ROOT_DIR, available_at=available_at)
        sample_path = write_immutable(output / "samples", preview["sample"])
        preview_path = write_immutable(output / "previews", preview)
        (output / "preview.txt").write_text(preview["text"], encoding="utf-8")
        if "html" in preview:
            (output / "preview.html").write_text(preview["html"], encoding="utf-8")
        result.update(status=preview["status"], sample=str(sample_path), preview=str(preview_path),
                      integration=preview["integration"], accounting=preview["base_report"]["body"]["accounting"])
        if "diagnosis" in preview:
            result.update(winning_combination=preview["diagnosis"]["winning_combination"],
                          portfolio=preview["diagnosis"]["portfolio"])
    (output / "read-audit.json").write_text(json.dumps(reader.audit, indent=2) + "\n")
    (output / "summary.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
