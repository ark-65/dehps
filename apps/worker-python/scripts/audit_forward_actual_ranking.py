from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dehps.db import get_connection
from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.prediction_evaluation import load_actual_draw
from dehps.optimization.ranking_audit import (
    build_actual_ranking_audit,
    training_history_for_prediction_run,
)
from dehps.optimization.walk_forward import (
    build_ranked_universe,
    config_hash,
    fingerprint_history,
    top_candidates_for_next,
)


def find_snapshot_metadata(value: Any, snapshot_key: str) -> dict[str, Any] | None:
    if isinstance(value, dict):
        if value.get("snapshot_key") == snapshot_key and isinstance(value.get("config"), dict):
            return value
        for child in value.values():
            found = find_snapshot_metadata(child, snapshot_key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_snapshot_metadata(child, snapshot_key)
            if found is not None:
                return found
    return None


def matched_red_counts(candidates: list[dict[str, Any]], actual: tuple[int, ...]) -> dict[str, dict[str, int]]:
    actual_set = set(actual)
    result = {
        "top_100": {"6": 0, "5": 0},
        "top_1000": {"6": 0, "5": 0},
        "top_10000": {"6": 0, "5": 0},
    }
    for row in candidates:
        overlap = len(actual_set.intersection(int(value) for value in row["red_numbers"]))
        for label, cutoff in (("top_100", 100), ("top_1000", 1000), ("top_10000", 10000)):
            if int(row["rank"]) <= cutoff and overlap in {5, 6}:
                result[label][str(overlap)] += 1
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reconstruct and audit a pre-draw snapshot from a timestamped supervisor artifact."
    )
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--issue", required=True)
    parser.add_argument("--snapshot-key", action="append", required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)

    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    matrix = build_ranked_universe()
    reports: list[dict[str, Any]] = []
    with get_connection() as conn:
        actual = load_actual_draw(conn, issue=args.issue)
        if actual is None:
            raise SystemExit(f"actual_draw_missing:{args.issue}")
        for snapshot_key in args.snapshot_key:
            metadata = find_snapshot_metadata(artifact, snapshot_key)
            if metadata is None:
                raise SystemExit(f"snapshot_metadata_missing:{snapshot_key}")
            run = {
                **metadata,
                "prediction_run_key": f"reconstructed:{metadata['line_key']}:{args.issue}:{snapshot_key}",
                "target_issue": args.issue,
                "metadata": metadata,
            }
            history = training_history_for_prediction_run(conn, run)
            config = FrequencyRankerConfig(
                **{
                    key: float(value)
                    for key, value in metadata["config"].items()
                    if isinstance(value, int | float)
                }
            )
            candidates_raw = top_candidates_for_next(
                history=history,
                top_n=int(metadata["top_n"]),
                config=config,
                target_draw_date=actual.get("draw_date"),
                target_issue=str(metadata["next_issue"]),
                ranked_universe=matrix,
            )
            candidates = [
                {"rank": rank, "red_numbers": list(numbers), "score": score}
                for rank, numbers, score in candidates_raw
            ]
            audit = build_actual_ranking_audit(
                conn,
                prediction_run=run,
                actual_draw=actual,
                candidates=candidates,
                ranked_universe=matrix,
            )
            audit["matched_red_count_by_cutoff"] = matched_red_counts(
                candidates,
                tuple(int(value) for value in actual["red_numbers"]),
            )
            audit["reconstruction"] = {
                "artifact": str(args.artifact),
                "artifact_snapshot_generated_at": metadata.get("generated_at"),
                "history_fingerprint_matches": fingerprint_history(
                    training_history_for_prediction_run(conn, run, apply_train_window=False)
                )
                == metadata.get("history_fingerprint"),
                "config_hash_matches": config_hash(config) == metadata.get("config_hash"),
                "official_forward_evidence": False,
                "reason": "candidate rows were overwritten before evaluation; ranks were deterministically reconstructed from the pre-draw artifact",
            }
            reports.append(audit)

    payload = {"issue": args.issue, "audits": reports}
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = args.output_dir / f"forward-ranking-audit-{args.issue}.json"
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
