from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2.superseding_slot import (
    LEGACY_P3_TASK_KEY,
    M4_V2_DESIGN_REPLAY_TASK_KEY,
    M4_V2_DESIGN_TASK_KEY,
    M4_V2_PREFLIGHT_TASK_KEY,
    P263_SLOT_ELIGIBILITY_TASK_KEY,
    build_p263_post_stop_guard_decision,
    validate_p263_slot_eligibility_artifact,
)
from dehps.research_os.mainline import completion_execution_ids
from dehps.research_os.models import TaskStatus
from dehps.research_os.repository import PostgresResearchOSRepository

SERVICE_UNIT = "dehps-research-evidence-supervisor.service"
CONTROL_PLANE_KEY = "m4-information-theory-mainline"
DOWNSTREAM_TASK_KEYS = (
    M4_V2_DESIGN_TASK_KEY,
    M4_V2_DESIGN_REPLAY_TASK_KEY,
    M4_V2_PREFLIGHT_TASK_KEY,
    LEGACY_P3_TASK_KEY,
)


def _persist(payload: dict) -> Path:
    path = (
        ROOT_DIR
        / "runtime/research-os/operator/m4-p263-runtime-slot-guard"
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
        line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
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
        description=(
            "Result-blind post-P2.6.3 runtime-slot release guard. "
            "It never reads measurement result payloads."
        )
    )
    parser.add_argument("--control-plane-key", default=CONTROL_PLANE_KEY)
    parser.add_argument("--execute-stop", action="store_true")
    parser.add_argument("--operator-request-key")
    args = parser.parse_args()
    if args.execute_stop and not args.operator_request_key:
        raise SystemExit("--execute-stop requires --operator-request-key")

    repository = PostgresResearchOSRepository()
    repository.ensure_schema()
    manifest = repository.load_manifest(control_plane_key=args.control_plane_key)
    eligibility_task = next(
        task
        for task in manifest.tasks
        if task.task_key == P263_SLOT_ELIGIBILITY_TASK_KEY
    )
    state = manifest.task_state_by_digest[eligibility_task.artifact_digest]
    execution_ids = completion_execution_ids(manifest, task=eligibility_task)
    if state.declared_status is not TaskStatus.COMPLETED or len(execution_ids) != 1:
        raise SystemExit("P2.6.3 runtime-slot eligibility is not uniquely complete")
    execution_id = execution_ids[0]
    events = repository.list_mainline_execution_event_metadata(
        control_plane_key=args.control_plane_key,
        task_keys=(P263_SLOT_ELIGIBILITY_TASK_KEY,),
    )
    completed = [
        event
        for event in events
        if event["execution_id"] == execution_id
        and event["event_type"] == "completed"
        and event["task_digest"] == eligibility_task.artifact_digest
    ]
    if len(completed) != 1:
        raise SystemExit("P2.6.3 eligibility completed event is not unique")
    registrations = repository.list_mainline_artifacts(
        control_plane_key=args.control_plane_key,
        execution_id=execution_id,
    )
    eligibility_registrations = [
        item
        for item in registrations
        if item["artifact_type"] == "p263_runtime_slot_release_eligibility"
    ]
    if len(eligibility_registrations) != 1:
        raise SystemExit("P2.6.3 eligibility artifact registration is not unique")
    path = ROOT_DIR / str(eligibility_registrations[0]["artifact_path"])
    eligibility = json.loads(path.read_text(encoding="utf-8"))
    validate_p263_slot_eligibility_artifact(eligibility)
    if eligibility_registrations[0]["artifact_digest"] != eligibility["artifact_digest"]:
        raise SystemExit("P2.6.3 eligibility registration digest changed")

    if not args.execute_stop:
        print(
            json.dumps(
                {
                    "state": "STOP_REQUIRED",
                    "eligibility": eligibility,
                    "completed_event_digest": completed[0]["event_digest"],
                    "statistical_results_read": False,
                    "production_action": "none",
                },
                sort_keys=True,
            )
        )
        return

    subprocess.run(["systemctl", "--user", "stop", SERVICE_UNIT], check=True)
    active_state, control_group = _service_state()
    downstream_events = repository.list_mainline_execution_event_metadata(
        control_plane_key=args.control_plane_key,
        task_keys=DOWNSTREAM_TASK_KEYS,
    )
    decision = build_p263_post_stop_guard_decision(
        eligibility=eligibility,
        service_active_state=active_state,
        worker_cgroup_empty=_cgroup_empty(control_group),
        downstream_started_events=tuple(
            event for event in downstream_events if event["event_type"] == "started"
        ),
    )
    decision_path = _persist(decision)
    print(
        json.dumps(
            {
                "decision": decision,
                "path": str(decision_path),
                "operator_request_key": args.operator_request_key,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
