from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.runtime.heavy_job import DEFAULT_LOCK_PATH, mark_inactive_heavy_job_owner


DEFAULT_OUTPUT_DIR = ROOT_DIR / "data/output/optimization"


def _issue_int(value: Any) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def waiting_status_payload(
    status: dict[str, Any],
    *,
    expected_pid: int,
    history_issue: str,
    pending_issue: str,
) -> dict[str, Any]:
    if status.get("pid") != expected_pid:
        raise ValueError("status_pid_mismatch")
    history_value = _issue_int(history_issue)
    pending_value = _issue_int(pending_issue)
    if history_value is None or pending_value is None or pending_value <= history_value:
        raise ValueError("pending_issue_not_future")
    progress = (
        status.get("latest_progress")
        if isinstance(status.get("latest_progress"), dict)
        else {}
    )
    target_index = progress.get("target_index")
    target_total = progress.get("target_total")
    if (
        not isinstance(target_index, int)
        or not isinstance(target_total, int)
        or target_total <= 0
        or target_index < target_total
    ):
        raise ValueError("latest_progress_not_at_durable_target_boundary")

    payload = dict(status)
    payload["status"] = "waiting_for_forward_issue"
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
    payload["forward_wait"] = {
        "protocol": "dehps-forward-evidence-wait-v1",
        "status": "awaiting_new_forward_issue",
        "history_latest_issue": str(history_issue),
        "next_pending_issue": str(pending_issue),
        "resume_condition": "history_latest_issue_reaches_pending_issue",
        "process_active": False,
        "selection_changed": False,
        "promotion_allowed": False,
    }
    return payload


def find_status_path(*, output_dir: Path, expected_pid: int) -> Path:
    matches: list[Path] = []
    for path in output_dir.glob("training-supervisor-*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(payload, dict) and payload.get("pid") == expected_pid:
            matches.append(path)
    if not matches:
        raise FileNotFoundError(f"no_status_for_pid:{expected_pid}")
    return max(matches, key=lambda path: path.stat().st_mtime_ns)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mark a stopped training supervisor as waiting for a future issue."
    )
    parser.add_argument("--expected-pid", type=int, required=True)
    parser.add_argument("--history-issue", required=True)
    parser.add_argument("--pending-issue", required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--heavy-job-lock-path", type=Path, default=DEFAULT_LOCK_PATH)
    args = parser.parse_args()

    path = find_status_path(output_dir=args.output_dir, expected_pid=args.expected_pid)
    status = json.loads(path.read_text(encoding="utf-8"))
    payload = waiting_status_payload(
        status,
        expected_pid=args.expected_pid,
        history_issue=args.history_issue,
        pending_issue=args.pending_issue,
    )
    heavy_job_metadata = mark_inactive_heavy_job_owner(
        expected_pid=args.expected_pid,
        expected_owner="training-supervisor",
        status="waiting_for_forward_issue",
        lock_path=args.heavy_job_lock_path,
        context={"forward_wait": payload["forward_wait"]},
        missing_ok=True,
    )
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {
                "status": payload["status"],
                "run_id": payload.get("run_id"),
                "path": str(path),
                "history_issue": args.history_issue,
                "pending_issue": args.pending_issue,
                "heavy_job_metadata_status": (
                    heavy_job_metadata.get("status")
                    if heavy_job_metadata is not None
                    else "missing"
                ),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
