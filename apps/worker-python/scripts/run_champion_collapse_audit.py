from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.models.frequency_ranker import infer_next_ssq_draw_date
from dehps.optimization.champion_collapse_audit import (
    run_champion_collapse_audit,
    write_champion_collapse_artifacts,
)
from dehps.optimization.regime import select_history
from dehps.optimization.walk_forward import build_ranked_universe


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit all retained adaptive configs at one common full-space score "
            "boundary without accessing the target outcome."
        )
    )
    parser.add_argument("--source-status", type=Path, required=True)
    parser.add_argument("--as-of-issue", required=True)
    parser.add_argument("--target-issue", required=True)
    parser.add_argument(
        "--history-scope",
        choices=("full_history_audit", "current_regime_default"),
        default="current_regime_default",
    )
    parser.add_argument("--regime-years", type=int, default=10)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR / "data/output/optimization/champion-collapse-audit",
    )
    parser.add_argument(
        "--allow-dirty-smoke",
        action="store_true",
        help="Allow an explicitly non-authoritative development smoke.",
    )
    args = parser.parse_args()

    if not args.allow_dirty_smoke:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
        if status.stdout.strip():
            raise RuntimeError(
                "authoritative champion collapse audit requires a clean source tree"
            )
    source_bytes = args.source_status.read_bytes()
    source = json.loads(source_bytes)
    with get_connection() as conn:
        selection = select_history(
            conn,
            scope=args.history_scope,
            as_of_issue=args.as_of_issue,
            regime_years=args.regime_years,
        )
    history = selection.dated_history
    if not history or history[-1][0] != args.as_of_issue:
        raise ValueError("selected history does not end at the frozen as-of issue")
    universe = build_ranked_universe(include_hard_filter_exclusions=True)
    payload = run_champion_collapse_audit(
        source=source,
        source_path=str(args.source_status),
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        history=history,
        ranked_universe=universe,
        target_issue=args.target_issue,
        target_draw_date=infer_next_ssq_draw_date(history),
    )
    json_path, report_path = write_champion_collapse_artifacts(
        payload,
        args.output_dir,
    )
    print(
        json.dumps(
            {
                "status": payload["protocol"]["status"],
                "promotion_allowed": payload["protocol"]["promotion_allowed"],
                "snapshot_digest": payload["snapshot_digest"],
                "json_path": str(json_path),
                "report_path": str(report_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
