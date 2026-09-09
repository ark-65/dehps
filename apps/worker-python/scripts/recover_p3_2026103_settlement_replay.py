"""Apply the approved incident migration, then dispatch the exact canonical task."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

WORKER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKER))

from dehps.config import ROOT_DIR
from dehps.notifications.p3_top100 import load_postdraw_bundle
from dehps.research_os import p3_2026103_recovery as recovery
from dehps.research_os.information_theory.measurement_system_v2 import (
    forward_prequential_confirmatory as p3,
)
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.research_os.supervisor import ResearchEvidenceSupervisor


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--operator-request")
    parser.add_argument("--executor-id")
    args = parser.parse_args()
    repo = PostgresResearchOSRepository()
    if not args.apply:
        recovery.verify_sources(ROOT_DIR)
        manifest = repo.load_manifest(control_plane_key=recovery.CONTROL)
        ready = recovery.ready_manifest(manifest)
        print(json.dumps({"status": "PLAN_VERIFIED", "task": recovery.TASK,
                          "old_manifest": manifest.artifact_digest,
                          "ready_manifest": ready.artifact_digest,
                          "external_delivery": False, "durable_state_changed": False}))
        return
    if not args.operator_request or not args.executor_id:
        parser.error("--apply requires --operator-request and --executor-id")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT_DIR).strip():
        raise recovery.RecoveryError("dirty_worktree")
    for stem in ("dehps-forward-prequential-successor", "dehps-p3-top100-pre-draw-mail",
                 "dehps-p3-top100-post-draw-mail"):
        for suffix in ("timer", "service"):
            state = subprocess.check_output(
                ["systemctl", "--user", "show", f"{stem}.{suffix}", "-p", "ActiveState", "--value"],
                text=True,
            ).strip()
            if state not in {"inactive", "failed"}:
                raise recovery.RecoveryError(f"quiescence_required:{stem}.{suffix}:{state}")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True).strip()
    prepared = recovery.prepare_retry(
        repo, root=ROOT_DIR, request_key=args.operator_request,
        executor_id=args.executor_id, commit=commit,
    )
    supervisor = p3.ForwardPrequentialSupervisor(repository=repo, root_dir=ROOT_DIR,
                                                 control_plane_key=recovery.CONTROL)
    manifest = repo.load_manifest(control_plane_key=recovery.CONTROL)
    state = next(r.status.value for r in repo.control_plane.resolve(manifest).resolutions
                 if r.task_key == recovery.TASK)
    if state == "ready":
        execution = supervisor.run_once(task_key=recovery.TASK)
    elif state == "completed":
        execution = {"status": "ALREADY_COMPLETED"}
    else:
        raise recovery.RecoveryError(f"recovery_not_ready:{state}")
    typed = supervisor.replay(task_key=recovery.TASK)
    generic = ResearchEvidenceSupervisor(repository=repo, root_dir=ROOT_DIR,
        control_plane_key=recovery.CONTROL).replay(task_key=recovery.TASK)
    bundle = load_postdraw_bundle(repo, issue="2026103", root_dir=ROOT_DIR)
    print(json.dumps({"status": "RECOVERY_REPLAY_VERIFIED", "preparation": prepared,
                      "execution": execution, "typed_replay": typed,
                      "generic_replay": generic,
                      "postdraw_consumer_issue": bundle.predraw.issue,
                      "external_delivery": False}, sort_keys=True))


if __name__ == "__main__":
    main()
