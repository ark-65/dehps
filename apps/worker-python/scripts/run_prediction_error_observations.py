"""Poll only registered per-issue observation dependencies; never send mail."""
from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.agents.repository import AgentRequestRepository
from dehps.config import ROOT_DIR
from dehps.prediction import error_learning_mainline as observation
from dehps.prediction.error_learning import _require, _time
from dehps.research_os.models import ResearchOSValidationError
from dehps.research_os.repository import PostgresResearchOSRepository


def verify_operator(key: str, digest: str, minimum: str) -> None:
    request = AgentRequestRepository().get_request(request_key=key)
    _require(request.request_type.value == "operator_release" and
             request.status.value in {"approved", "executing", "completed"}, "observation_operator_not_approved")
    checks = request.payload["checks"]
    _require(checks.get("observer_source_digest") == digest and
             checks.get("minimum_issue") == minimum, "observation_operator_scope_changed")
    commit = request.payload["commit"]
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT_DIR,
                   check=True, capture_output=True)
    _require(not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT_DIR).strip(),
             "observation_worktree_dirty")


def ready_issues(repository, minimum: str) -> list[tuple[str, bool]]:
    p3 = observation.notification.p3
    manifest = repository.load_manifest(control_plane_key=observation.notification.P3_CONTROL_PLANE_KEY)
    statuses = {r.task_key: r.status.value for r in repository.control_plane.resolve(manifest).resolutions}
    reports = repository.load_manifest(control_plane_key=observation.notification.CONTROL_PLANE_KEY)
    opened = {r.task_key for r in repository.control_plane.resolve(reports).resolutions if r.status.value == "completed"}
    issues = set()
    for task in manifest.tasks:
        if task.requested_capability != p3.PREDRAW_REPLAY_CAPABILITY:
            continue
        issue = str(json.loads(task.metric_contract)["target_issue"])
        if issue >= minimum and statuses.get(task.task_key) == "completed":
            issues.add(issue)
    return [(issue, observation.notification.issue_task_keys(issue)["post_replay"] in opened)
            for issue in sorted(issues)]


def cycle(*, apply: bool, minimum: str, operator: str | None, repository=None) -> dict:
    repository = repository or PostgresResearchOSRepository()
    source = observation.source_digest()
    if apply:
        _require(bool(operator), "observation_operator_required")
        verify_operator(operator, source, minimum)
    try:
        manifest = repository.load_manifest(control_plane_key=observation.CONTROL_PLANE_KEY)
    except ResearchOSValidationError:
        manifest = None
    if manifest is None:
        if not apply:
            return {"status": "NOT_INSTALLED", "source_digest": source, "dispatch_performed": False}
        payload = observation.initial_manifest(minimum_issue=minimum, source=source)
        repository.import_manifest(control_plane_key=observation.CONTROL_PLANE_KEY,
                                   payload=payload, source="prediction-error-observation-install")
        manifest = repository.load_manifest(control_plane_key=observation.CONTROL_PLANE_KEY)
    target = json.loads(manifest.goals[0].target_metric_manifest)
    _require(target == {"minimum_issue": minimum, "source_digest": source}, "observation_install_binding_changed")
    supervisor = observation.ObservationSupervisor(repository=repository)
    output = []
    for issue, post_ready in ready_issues(repository, minimum):
        for phase in (["record", "report"] if post_ready else ["record"]):
            key = observation.task_key(issue, phase)
            live = repository.load_manifest(control_plane_key=observation.CONTROL_PLANE_KEY)
            status = {r.task_key: r.status.value for r in repository.control_plane.resolve(live).resolutions}.get(key)
            if status == "completed":
                output.append({"issue": issue, "phase": phase, "status": "ALREADY_COMPLETED"})
                continue
            if not apply:
                output.append({"issue": issue, "phase": phase, "status": status or "PARENTS_READY"})
                continue
            if status is None:
                inputs = supervisor.observer.inputs(issue, phase)
                payload = observation.add_task(live.to_dict(include_digest=True), issue=issue, phase=phase, inputs=inputs)
                repository.import_manifest(control_plane_key=observation.CONTROL_PLANE_KEY, payload=payload,
                                           source="prediction-error-observation-add-exact-task")
            # Existing failed tasks are never silently recovered or superseded.
            result = supervisor.run_once(task_key=key)
            replay = supervisor.replay(task_key=key)
            output.append({"issue": issue, "phase": phase, "status": "REPLAY_VERIFIED",
                           "execution_id": result["execution_id"], "replay": replay})
    acceptance = []
    current = repository.load_manifest(control_plane_key=observation.CONTROL_PLANE_KEY)
    statuses = {r.task_key: r.status.value for r in repository.control_plane.resolve(current).resolutions}
    for issue, _ in ready_issues(repository, minimum):
        if statuses.get(observation.task_key(issue, "record")) != "completed":
            continue
        record = supervisor.observer.stored(issue, "record")["body"]
        done = statuses.get(observation.task_key(issue, "report")) == "completed"
        events = repository.list_mainline_execution_event_metadata(
            control_plane_key=observation.CONTROL_PLANE_KEY,
            task_keys=(observation.task_key(issue, "record"),))
        completion = [e for e in events if e["event_type"] == "completed"]
        deadline = record["body"]["frozen_inputs"]["predraw"]["checkpoint"]["body"]["official_draw_time"]
        timely = (record["body"]["record_mode"] == "PREDRAW_OBSERVATION" and len(completion) == 1
                  and _time(completion[0]["recorded_at"]) < _time(deadline))
        acceptance.append({"issue": issue, "record_mode": record["body"]["record_mode"],
                           "registered_before_draw": timely,
                           "report_complete": done,
                           "real_cycle_acceptance": ("VALIDATED" if done else "WAITING_FOR_OPENED_DRAW")
                           if timely else "RETROSPECTIVE_ONLY"})
    result = {"status": "ARMED", "source_digest": source, "tasks": output, "acceptance": acceptance,
              "formal_prediction_changed": False, "scientific_credit": False, "external_delivery": False}
    if apply:
        observation.atomic_write_text(ROOT_DIR / "runtime/logs/prediction-error-observation-cycle.json",
                                      json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--minimum-issue", default="2026102")
    parser.add_argument("--operator-request")
    args = parser.parse_args()
    if args.apply:
        lock = ROOT_DIR / "runtime/prediction-error-observation.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        with lock.open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = cycle(apply=True, minimum=args.minimum_issue, operator=args.operator_request)
    else:
        result = cycle(apply=False, minimum=args.minimum_issue, operator=args.operator_request)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
