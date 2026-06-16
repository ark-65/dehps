from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path

from dehps.candidates.generator import generate_candidates, render_candidate_report
from dehps.candidates.leakage import audit_candidate_protocol
from dehps.candidates.null_model import generate_null_candidates
from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.storage.postgres_store import latest_draw, load_history


def next_issue_hint(issue: str | None) -> str | None:
    if not issue or not issue.isdigit():
        return None
    return str(int(issue) + 1)


def generate_next_candidates(
    *,
    limit: int,
    random_sets: int,
    seed: str | None = None,
    output_dir: Path | None = None,
) -> dict[str, str | int]:
    with get_connection() as conn:
        history = load_history(conn)
        latest = latest_draw(conn)

    latest_issue = latest["issue"] if latest else None
    frozen_seed = seed or latest_issue or datetime.now().strftime("%Y%m%d")
    candidate_key = f"next-red-candidates-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    candidates = generate_candidates(limit=limit, seed=frozen_seed, history=history)
    null_summary = generate_null_candidates(
        candidate_count=limit,
        random_sets=random_sets,
        seed=f"{frozen_seed}:null",
        history=history,
    )
    checks = audit_candidate_protocol(
        candidates=candidates,
        history=history,
        latest_issue=latest_issue,
        seed=frozen_seed,
    )

    root = output_dir or ROOT_DIR / "data/output/candidates"
    root.mkdir(parents=True, exist_ok=True)
    csv_path = root / f"{candidate_key}.csv"
    report_path = root / f"{candidate_key}.md"

    with csv_path.open("w", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(
            [
                "rank",
                "red_numbers",
                "score",
                "anomaly_penalty",
                "structure_naturalness_score",
                "pattern_complexity_score",
                "tie_hash",
            ],
        )
        for candidate in candidates:
            writer.writerow(
                [
                    candidate.rank,
                    candidate.numbers_text,
                    candidate.score,
                    candidate.anomaly_penalty,
                    candidate.structure_naturalness_score,
                    candidate.pattern_complexity_score,
                    candidate.tie_breaker,
                ],
            )

    report = render_candidate_report(
        candidate_key=candidate_key,
        seed=frozen_seed,
        latest_issue=latest_issue,
        next_issue_hint=next_issue_hint(latest_issue),
        candidates=candidates,
        null_summary=null_summary.as_dict(),
        leakage_checks=[check.as_dict() for check in checks],
    )
    report_path.write_text(report)
    return {
        "candidate_key": candidate_key,
        "latest_issue": latest_issue or "",
        "next_issue_hint": next_issue_hint(latest_issue) or "",
        "candidate_count": len(candidates),
        "csv_path": str(csv_path),
        "report_path": str(report_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--random-sets", type=int, default=200)
    parser.add_argument("--seed")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(
        generate_next_candidates(
            limit=args.limit,
            random_sets=args.random_sets,
            seed=args.seed,
            output_dir=args.output_dir,
        ),
    )


if __name__ == "__main__":
    main()
