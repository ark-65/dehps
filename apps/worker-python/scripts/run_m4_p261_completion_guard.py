from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2.terminal_guard import (
    EXPECTED_P261_EXECUTION_ID,
    LEGACY_P3_TASK_KEY,
    P27_TASK_KEY,
    P261_TASK_KEY,
    evaluate_post_stop_boundary,
    evaluate_terminal_boundary,
)
from dehps.research_os.repository import PostgresResearchOSRepository

SERVICE_UNIT = "dehps-research-evidence-supervisor.service"


def _persist(payload: dict) -> Path:
    path = (
        ROOT_DIR
        / "runtime/research-os/operator/m4-p2-6-1-completion-guard"
        / str(payload["artifact_digest"])
        / "decision.json"
    )
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != payload:
            raise RuntimeError(f"immutable guard artifact collision: {path}")
        return path
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    return path


def _service_state() -> tuple[str, str]:
    result = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            SERVICE_UNIT,
            "--property=ActiveState",
            "--property=ControlGroup",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    values = dict(
        line.split("=", 1)
        for line in result.stdout.splitlines()
        if "=" in line
    )
    return values.get("ActiveState", "unknown"), values.get("ControlGroup", "")


def _cgroup_empty(control_group: str) -> bool:
    if not control_group:
        return True
    root = Path("/sys/fs/cgroup") / control_group.lstrip("/")
    if not root.exists():
        return True
    for path in (root, *sorted(item for item in root.rglob("*") if item.is_dir())):
        procs = path / "cgroup.procs"
        try:
            if procs.is_file() and procs.read_text(encoding="utf-8").strip():
                return False
        except OSError:
            return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Result-blind P2.6.1 terminal-boundary completion guard."
    )
    parser.add_argument(
        "--control-plane-key",
        default="m4-information-theory-mainline",
    )
    parser.add_argument("--interval-seconds", type=float, default=1.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--execute-stop", action="store_true")
    parser.add_argument("--operator-request-key")
    args = parser.parse_args()
    if args.interval_seconds <= 0 or args.interval_seconds >= 15:
        raise SystemExit("interval-seconds must be greater than 0 and less than 15")
    if args.execute_stop and not args.operator_request_key:
        raise SystemExit("--execute-stop requires --operator-request-key")

    repository = PostgresResearchOSRepository()
    repository.ensure_schema()
    task_keys = (P261_TASK_KEY, P27_TASK_KEY, LEGACY_P3_TASK_KEY)
    while True:
        events = repository.list_mainline_execution_event_metadata(
            control_plane_key=args.control_plane_key,
            task_keys=task_keys,
        )
        p261_events = tuple(
            item for item in events if item["task_key"] == P261_TASK_KEY
        )
        registrations = repository.list_mainline_artifacts(
            control_plane_key=args.control_plane_key,
            execution_id=EXPECTED_P261_EXECUTION_ID,
        )
        decision = evaluate_terminal_boundary(
            p261_events=p261_events,
            all_events=events,
            registrations=registrations,
            root_dir=ROOT_DIR,
        )
        if decision.state == "WAITING":
            if args.once:
                print(json.dumps(decision.to_artifact(), sort_keys=True))
                return
            time.sleep(args.interval_seconds)
            continue
        first_path = _persist(decision.to_artifact())
        if decision.state != "STOP_REQUIRED" or not args.execute_stop:
            print(json.dumps({"decision": decision.to_artifact(), "path": str(first_path)}))
            return

        subprocess.run(
            ["systemctl", "--user", "stop", SERVICE_UNIT],
            check=True,
        )
        active_state, control_group = _service_state()
        post_events = repository.list_mainline_execution_event_metadata(
            control_plane_key=args.control_plane_key,
            task_keys=(P27_TASK_KEY, LEGACY_P3_TASK_KEY),
        )
        post = evaluate_post_stop_boundary(
            service_active_state=active_state,
            worker_cgroup_empty=_cgroup_empty(control_group),
            downstream_started_events=tuple(
                item for item in post_events if item["event_type"] == "started"
            ),
            completion_artifact_digest=str(decision.completion_artifact_digest),
        )
        payload = post.to_artifact()
        path = _persist(payload)
        print(
            json.dumps(
                {
                    "decision": payload,
                    "path": str(path),
                    "operator_request_key": args.operator_request_key,
                },
                sort_keys=True,
            )
        )
        return


if __name__ == "__main__":
    main()
