from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.runtime.heavy_job import (
    DEFAULT_LOCK_PATH,
    HeavyJobLockError,
    describe_heavy_job_owner,
    mark_inactive_heavy_job_owner,
)


DEFAULT_OUTPUT_DIR = ROOT_DIR / "data/output/optimization"


def update_waiting_report(status: dict[str, Any]) -> Path | None:
    report_value = status.get("report_path")
    if not isinstance(report_value, str) or not report_value.strip():
        return None
    report_path = Path(report_value)
    report = report_path.read_text(encoding="utf-8")
    replacements = {
        r"^- Updated at: .*?$": f"- Updated at: {status['updated_at']}",
        r"^- Status: .*?$": f"- Status: {status['status']}",
    }
    for pattern, replacement in replacements.items():
        report, count = re.subn(pattern, replacement, report, count=1, flags=re.MULTILINE)
        if count != 1:
            raise ValueError(f"supervisor_report_field_missing:{pattern}")
    atomic_write_text(report_path, report)
    return report_path


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


def sync_waiting_heavy_job_metadata(
    *,
    expected_pid: int,
    lock_path: Path,
    forward_wait: dict[str, Any],
) -> dict[str, Any]:
    owner_status = describe_heavy_job_owner(lock_path=lock_path)
    metadata = owner_status.metadata
    if isinstance(metadata, dict) and metadata.get("pid") != expected_pid:
        if owner_status.active:
            raise HeavyJobLockError(
                "Refusing to preserve parked supervisor state while another heavy job is active: "
                f"pid={metadata.get('pid')!r} reason={owner_status.reason}"
            )
        return {
            "status": "preserved_other_inactive_owner",
            "updated": False,
            "owner_pid": metadata.get("pid"),
            "owner_status": metadata.get("status"),
            "owner_reason": owner_status.reason,
        }

    updated = mark_inactive_heavy_job_owner(
        expected_pid=expected_pid,
        expected_owner="training-supervisor",
        status="waiting_for_forward_issue",
        lock_path=lock_path,
        context={"forward_wait": forward_wait},
        missing_ok=True,
    )
    return {
        "status": (
            updated.get("status")
            if isinstance(updated, dict)
            else "missing"
        ),
        "updated": isinstance(updated, dict),
        "owner_pid": updated.get("pid") if isinstance(updated, dict) else None,
        "owner_status": updated.get("status") if isinstance(updated, dict) else None,
        "owner_reason": owner_status.reason,
    }


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
    heavy_job_result = sync_waiting_heavy_job_metadata(
        expected_pid=args.expected_pid,
        lock_path=args.heavy_job_lock_path,
        forward_wait=payload["forward_wait"],
    )
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
    report_path = update_waiting_report(payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "run_id": payload.get("run_id"),
                "path": str(path),
                "history_issue": args.history_issue,
                "pending_issue": args.pending_issue,
                "report_path": str(report_path) if report_path is not None else None,
                "heavy_job_metadata_status": heavy_job_result["status"],
                "heavy_job_metadata_updated": heavy_job_result["updated"],
                "heavy_job_metadata_owner_pid": heavy_job_result["owner_pid"],
                "heavy_job_metadata_owner_status": heavy_job_result["owner_status"],
                "heavy_job_metadata_owner_reason": heavy_job_result["owner_reason"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
