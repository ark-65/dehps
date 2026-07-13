from __future__ import annotations

"""Run bounded, read-only historical research while forward training is parked.

This lane deliberately never invokes the training supervisor and never writes current
prediction candidates.  It is a fixed audit suite: its artifacts may inform a human
review, but cannot change line selection or promotion.
"""

import argparse
import fcntl
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = WORKER_ROOT.parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.optimization.regime import select_history
from dehps.optimization.walk_forward import fingerprint_history


LANE_KEY = "isolated_historical_research"
SUITE_VERSION = "fixed-kdj-controls-v1"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data/output/optimization/research-lane"
DEFAULT_LOCK_PATH = ROOT_DIR / "runtime/logs/isolated-research-lane.lock"


def research_commands(*, as_of_issue: str, workers: int, output_dir: Path) -> list[tuple[str, list[str]]]:
    common = [
        "--as-of-issue",
        as_of_issue,
        "--train-mode",
        "expanding",
        "--train-window",
        "900",
        "--eval-window",
        "100",
        "--top-n",
        "10000",
        "--history-scope",
        "current_regime_default",
        "--regime-years",
        "10",
    ]
    return [
        (
            "dynamic_kdj_frozen_backtest",
            [
                sys.executable,
                "scripts/run_dynamic_kdj_backtest.py",
                *common,
                "--output-dir",
                str(output_dir / "dynamic-kdj"),
            ],
        ),
        (
            "kdj_advisor_frozen_controls",
            [
                sys.executable,
                "scripts/run_control_experiments.py",
                "--candidate-source",
                "kdj",
                *common,
                "--workers",
                str(workers),
                "--output-dir",
                str(output_dir / "kdj-controls"),
            ],
        ),
    ]


def manifest_matches(manifest: Any, *, as_of_issue: str, history_fingerprint_value: str) -> bool:
    return bool(
        isinstance(manifest, dict)
        and manifest.get("status") == "completed"
        and manifest.get("lane_key") == LANE_KEY
        and manifest.get("suite_version") == SUITE_VERSION
        and manifest.get("as_of_issue") == as_of_issue
        and manifest.get("history_fingerprint") == history_fingerprint_value
    )


def load_manifest(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def render_report(payload: dict[str, Any]) -> str:
    runs = payload.get("runs") if isinstance(payload.get("runs"), list) else []
    rows = [
        "# Isolated Historical Research Lane",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- As-of issue: `{payload.get('as_of_issue')}`",
        f"- Suite: `{payload.get('suite_version')}`",
        f"- History fingerprint: `{payload.get('history_fingerprint')}`",
        "- Boundary: this suite does not run the training supervisor, write current prediction candidates, select a line, or promote a model.",
        "",
        "## Fixed audits",
        "",
    ]
    for run in runs:
        rows.append(
            f"- `{run.get('name')}`: `{run.get('status')}` "
            f"({run.get('elapsed_seconds')}s; log `{run.get('log_path')}`)"
        )
    rows.extend(
        [
            "",
            "Results are historical diagnostics only. They require the normal frozen and forward-evidence gates before any main-line change.",
            "",
        ]
    )
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a fixed, isolated DEHPS historical research suite.")
    parser.add_argument("--as-of-issue", required=True)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--lock-path", type=Path, default=DEFAULT_LOCK_PATH)
    args = parser.parse_args()
    if args.workers < 1:
        raise ValueError("--workers must be positive")

    with get_connection() as conn:
        selection = select_history(
            conn,
            scope="current_regime_default",
            as_of_issue=args.as_of_issue,
            regime_years=10,
        )
    if not selection.dated_history:
        raise ValueError("selected history is empty")
    observed_issue = str(selection.dated_history[-1][0])
    if observed_issue != args.as_of_issue:
        raise ValueError(f"as-of issue mismatch: requested={args.as_of_issue} observed={observed_issue}")
    history_fingerprint_value = fingerprint_history(selection.dated_history)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.lock_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path = args.output_dir / "isolated-research-lane-latest.json"
    with args.lock_path.open("a+", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "already_running", "lane_key": LANE_KEY}, ensure_ascii=False))
            return
        previous = load_manifest(latest_path)
        if manifest_matches(
            previous,
            as_of_issue=args.as_of_issue,
            history_fingerprint_value=history_fingerprint_value,
        ):
            print(
                json.dumps(
                    {
                        "status": "already_completed_for_history",
                        "lane_key": LANE_KEY,
                        "as_of_issue": args.as_of_issue,
                        "suite_version": SUITE_VERSION,
                    },
                    ensure_ascii=False,
                )
            )
            return

        started = time.monotonic()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        payload: dict[str, Any] = {
            "status": "running",
            "lane_key": LANE_KEY,
            "suite_version": SUITE_VERSION,
            "as_of_issue": args.as_of_issue,
            "history_fingerprint": history_fingerprint_value,
            "selection_changed": False,
            "promotion_allowed": False,
            "main_candidate_write_allowed": False,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "runs": [],
        }
        for name, command in research_commands(
            as_of_issue=args.as_of_issue,
            workers=args.workers,
            output_dir=args.output_dir,
        ):
            log_path = args.output_dir / f"{stamp}-{name}.log"
            command_started = time.monotonic()
            with log_path.open("w", encoding="utf-8") as log_handle:
                completed = subprocess.run(
                    command,
                    cwd=WORKER_ROOT,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    check=False,
                    text=True,
                )
            result = {
                "name": name,
                "status": "completed" if completed.returncode == 0 else "failed",
                "returncode": completed.returncode,
                "elapsed_seconds": round(time.monotonic() - command_started, 3),
                "log_path": str(log_path),
            }
            payload["runs"].append(result)
            if completed.returncode != 0:
                payload["status"] = "failed"
                break
        else:
            payload["status"] = "completed"
        payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        payload["elapsed_seconds"] = round(time.monotonic() - started, 3)
        report_path = args.output_dir / f"isolated-research-lane-{stamp}.md"
        payload["report_path"] = str(report_path)
        latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report_path.write_text(render_report(payload), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        if payload["status"] != "completed":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
