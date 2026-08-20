from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.measurement_system_v2.deeper_validation import (
    DECISION_CAPABILITY,
    DECISION_COMPLETION_FACT,
    DECISION_REPLAY_CAPABILITY,
    DECISION_REPLAY_COMPLETION_FACT,
    DECISION_REPLAY_TASK_KEY,
    DECISION_REPLAY_VERIFIED_FACT,
    DECISION_TASK_KEY,
    INTAKE_CAPABILITY,
    INTAKE_COMPLETION_FACT,
    INTAKE_TASK_KEY,
    OLD_GLOBAL_ROUTE,
    ROUTE_CAPABILITY,
    ROUTE_COMPLETION_FACT,
    ROUTE_REPLAY_CAPABILITY,
    ROUTE_REPLAY_COMPLETION_FACT,
    ROUTE_REPLAY_TASK_KEY,
    ROUTE_REPLAY_VERIFIED_FACT,
    ROUTE_TASK_KEY,
    load_source_contract,
)
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.repository import PostgresResearchOSRepository


class M4V2DeeperValidationManifestError(ValueError):
    pass


CONTROL_PLANE_KEY = "m4-information-theory-mainline"
GOAL_KEY = "M4_INFORMATION_THEORY_EVIDENCE"
BASELINE_MANIFEST_DIGEST = (
    "175b4cf81a5ffd6398e00c97eb52a3efa06813f31f2d9bacfe6bfbb81243aceb"
)
BASELINE_SNAPSHOT_DIGEST = (
    "7b5370cdfc8ef17ee9bbd1ad699d7dd67f4a9d5e2b46b1ad01c473c81581010c"
)
OLD_ROUTE_TASK_KEY = "m4-v2-global-routing-recovery-v3"
OLD_ROUTE_COMPLETION_FACT = "m4-v2-global-routing-recovery-v3:COMPLETE"
OLD_ROUTE_FACT = f"m4-v2-routing:{OLD_GLOBAL_ROUTE}"
BRANCH_REPLAY_FACTS = (
    "m4-v2-historical-branch-decision-replay:M4_MEASUREMENT_CONTRACT_V2:MARGINAL_STATIC:VERIFIED",
    "m4-v2-historical-branch-decision-replay:M4_MEASUREMENT_CONTRACT_V2:TEMPORAL_MARGINAL_INCREMENT:VERIFIED",
    "m4-v2-historical-branch-decision-replay:M4_MEASUREMENT_CONTRACT_V2:JOINT_RESIDUAL_INCREMENT:VERIFIED",
)
SOURCE_FACT_PREFIX = "m4-v2-deeper-validation-source:"
P3_CLOSED_FACT = "m4-v2-predictive-p3:CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION"


def _dependency(
    dependency_type: str, target_key: str, required_status: str
) -> dict[str, str]:
    return {
        "dependency_type": dependency_type,
        "target_key": target_key,
        "required_status": required_status,
    }


def _integration(
    *,
    ready_condition: str,
    upstream: list[str],
    downstream: list[str],
    decision_consumer: str,
    status_projection: str,
) -> dict[str, Any]:
    return {
        "goal": GOAL_KEY,
        "ready_condition": ready_condition,
        "runner": "research_evidence_supervisor",
        "upstream_artifacts": upstream,
        "downstream_artifacts": downstream,
        "status_projection": status_projection,
        "evidence_progress_rule": "zero_compute_governed_decision_creates_no_evidence",
        "decision_consumer": decision_consumer,
        "downstream_consumer": decision_consumer,
    }


def _task(
    *,
    task_key: str,
    capability: str,
    priority: int,
    dependencies: list[dict[str, str]],
    source_digest: str,
    completion_fact: str,
    phase: str,
    ready_condition: str,
    upstream: list[str],
    downstream: list[str],
    decision_consumer: str,
) -> dict[str, Any]:
    return {
        "task_key": task_key,
        "goal_key": GOAL_KEY,
        "task_type": capability,
        "lane": "research",
        "priority": priority,
        "dependencies": dependencies,
        "input_artifact_digests": [source_digest],
        "requested_capability": capability,
        "metric_contract": {
            "engineering_complete": True,
            "engineering_increment_percent": 0,
            "evidence_complete": False,
            "evidence_increment_percent": 0,
            "phase": phase,
            "scope": "bounded_result_blind_deeper_validation_without_predictive_p3",
            "completion_fact": completion_fact,
            "unresolved_branch_limit": 1,
            "formal_validation_execution_limit": 1,
            "ci_fix_limit": 1,
            "new_holdout_or_forward_program_limit": 1,
            "new_historical_folds": 0,
            "predictive_p3_folds": 0,
            "p4_started": False,
            "promotion_triggered": False,
            "old_replay_compatibility_dependency": False,
            "production_action": "none",
            "mainline_integration": _integration(
                ready_condition=ready_condition,
                upstream=upstream,
                downstream=downstream,
                decision_consumer=decision_consumer,
                status_projection=f"unified_m4_status.deeper_validation.{task_key}",
            ),
        },
        "status": "draft",
        "completion_classification": "INTEGRATION_PENDING",
    }


def _new_tasks(source_digest: str) -> list[dict[str, Any]]:
    intake = _task(
        task_key=INTAKE_TASK_KEY,
        capability=INTAKE_CAPABILITY,
        priority=120,
        dependencies=[
            _dependency("task", OLD_ROUTE_TASK_KEY, "completed"),
            _dependency("artifact", OLD_ROUTE_COMPLETION_FACT, "available"),
            _dependency("artifact", OLD_ROUTE_FACT, "available"),
            *[
                _dependency("artifact", fact, "available")
                for fact in BRANCH_REPLAY_FACTS
            ],
        ],
        source_digest=source_digest,
        completion_fact=INTAKE_COMPLETION_FACT,
        phase="M4-V2-DEEPER-VALIDATION-INTAKE",
        ready_condition=(
            "the immutable recovery-v3 Global Route and all three registered branch replay "
            "facts are complete; the permanently blocked compatibility successor is not a dependency"
        ),
        upstream=[
            "three registered Branch Decision artifacts",
            "three registered Branch Replay artifacts and registration identities",
            "frozen recovery-v3 Global Route artifact",
            "registered historical inference/design/boundary state",
            "Research Request 625 / Execution 509",
        ],
        downstream=["M4V2DeeperValidationIntakeArtifact", INTAKE_COMPLETION_FACT],
        decision_consumer=DECISION_TASK_KEY,
    )
    decision = _task(
        task_key=DECISION_TASK_KEY,
        capability=DECISION_CAPABILITY,
        priority=119,
        dependencies=[
            _dependency("task", INTAKE_TASK_KEY, "completed"),
            _dependency("artifact", INTAKE_COMPLETION_FACT, "available"),
        ],
        source_digest=source_digest,
        completion_fact=DECISION_COMPLETION_FACT,
        phase="M4-V2-DEEPER-VALIDATION-DECISION",
        ready_condition=(
            "the zero-compute Intake is registered and Reviewer Decision 2627 selected "
            "POWER_RESOLUTION_REQUIRED for MARGINAL_STATIC"
        ),
        upstream=[
            "M4V2DeeperValidationIntakeArtifact",
            "Reviewer Decision 2627 / Research Request 626 / Execution 510",
            "frozen MDE, threshold, estimator and failure rule",
        ],
        downstream=["M4V2DeeperValidationDecisionArtifact", DECISION_COMPLETION_FACT],
        decision_consumer=DECISION_REPLAY_TASK_KEY,
    )
    decision_replay = _task(
        task_key=DECISION_REPLAY_TASK_KEY,
        capability=DECISION_REPLAY_CAPABILITY,
        priority=118,
        dependencies=[
            _dependency("task", DECISION_TASK_KEY, "completed"),
            _dependency("artifact", DECISION_COMPLETION_FACT, "available"),
        ],
        source_digest=source_digest,
        completion_fact=DECISION_REPLAY_COMPLETION_FACT,
        phase="M4-V2-DEEPER-VALIDATION-DECISION-REPLAY",
        ready_condition="the typed Deeper Validation decision is registered",
        upstream=[
            "M4V2DeeperValidationDecisionArtifact",
            "decision registration identity",
        ],
        downstream=[
            "M4V2DeeperValidationDecisionReplayArtifact",
            DECISION_REPLAY_VERIFIED_FACT,
            DECISION_REPLAY_COMPLETION_FACT,
        ],
        decision_consumer=ROUTE_TASK_KEY,
    )
    route = _task(
        task_key=ROUTE_TASK_KEY,
        capability=ROUTE_CAPABILITY,
        priority=117,
        dependencies=[
            _dependency("task", DECISION_REPLAY_TASK_KEY, "completed"),
            _dependency("artifact", DECISION_REPLAY_VERIFIED_FACT, "available"),
        ],
        source_digest=source_digest,
        completion_fact=ROUTE_COMPLETION_FACT,
        phase="M4-V2-GLOBAL-ROUTING-AFTER-DEEPER-VALIDATION",
        ready_condition=(
            "the immutable old route, original branch decisions/replays and the new registered "
            "Deeper Validation decision/replay are all available"
        ),
        upstream=[
            "old frozen Global Route artifact",
            "three original Branch Decision artifacts",
            "three original Branch Replay identities",
            "new Deeper Validation decision and registered replay identities",
        ],
        downstream=[
            "M4V2SupersedingGlobalRouteArtifact",
            "M4V2PredictiveP3ClosureArtifact",
            P3_CLOSED_FACT,
            ROUTE_COMPLETION_FACT,
        ],
        decision_consumer=ROUTE_REPLAY_TASK_KEY,
    )
    route_replay = _task(
        task_key=ROUTE_REPLAY_TASK_KEY,
        capability=ROUTE_REPLAY_CAPABILITY,
        priority=116,
        dependencies=[
            _dependency("task", ROUTE_TASK_KEY, "completed"),
            _dependency("artifact", ROUTE_COMPLETION_FACT, "available"),
            _dependency("artifact", P3_CLOSED_FACT, "available"),
        ],
        source_digest=source_digest,
        completion_fact=ROUTE_REPLAY_COMPLETION_FACT,
        phase="M4-V2-GLOBAL-ROUTING-AFTER-DEEPER-VALIDATION-REPLAY",
        ready_condition="the superseding route and predictive-P3 closure are registered",
        upstream=[
            "M4V2SupersedingGlobalRouteArtifact",
            "M4V2PredictiveP3ClosureArtifact",
            "their registration identities",
        ],
        downstream=[
            "M4V2SupersedingGlobalRouteReplayArtifact",
            ROUTE_REPLAY_VERIFIED_FACT,
            ROUTE_REPLAY_COMPLETION_FACT,
        ],
        decision_consumer="terminal:FORWARD_EVIDENCE_REQUIRED",
    )
    return [intake, decision, decision_replay, route, route_replay]


NEW_TASK_KEYS = tuple(task["task_key"] for task in _new_tasks("0" * 64))


def build_manifest(
    live_payload: Mapping[str, Any], *, source_contract_digest: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    live = ControlPlaneManifest.from_dict(deepcopy(dict(live_payload)))
    if live.artifact_digest != BASELINE_MANIFEST_DIGEST:
        raise M4V2DeeperValidationManifestError("deeper_validation_baseline_changed")
    baseline_snapshot = ResearchOSControlPlane().resolve(live)
    if baseline_snapshot.snapshot_digest != BASELINE_SNAPSHOT_DIGEST:
        raise M4V2DeeperValidationManifestError(
            "deeper_validation_baseline_snapshot_changed"
        )
    if any(task.task_key in NEW_TASK_KEYS for task in live.tasks):
        raise M4V2DeeperValidationManifestError(
            "deeper_validation_task_already_present"
        )
    payload = live.to_dict(include_digest=False)
    payload["tasks"].extend(_new_tasks(source_contract_digest))
    source_fact = SOURCE_FACT_PREFIX + source_contract_digest
    payload["facts"]["artifacts"] = sorted(
        {*payload["facts"]["artifacts"], source_fact}
    )
    output = ControlPlaneManifest.from_dict(payload)
    output_snapshot = ResearchOSControlPlane().resolve(output)
    ready = tuple(item.task_key for item in output_snapshot.ready_queue)
    if ready != (INTAKE_TASK_KEY,):
        raise M4V2DeeperValidationManifestError(
            f"deeper_validation_unique_ready_changed:{ready}"
        )
    dry_run = {
        "schema_version": "dehps-m4-v2-deeper-validation-manifest-dry-run.v1",
        "artifact_type": "m4_v2_deeper_validation_manifest_dry_run",
        "status": "VERIFIED",
        "baseline_manifest_digest": live.artifact_digest,
        "baseline_snapshot_digest": baseline_snapshot.snapshot_digest,
        "output_manifest_digest": output.artifact_digest,
        "output_snapshot_digest": output_snapshot.snapshot_digest,
        "source_contract_digest": source_contract_digest,
        "new_task_keys": list(NEW_TASK_KEYS),
        "unique_ready_task": INTAKE_TASK_KEY,
        "old_replay_compatibility_dependency": False,
        "predictive_p3_folds": 0,
        "p4_started": False,
        "promotion_triggered": False,
    }
    return output.to_dict(include_digest=True), dry_run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the exact additive M4-v2 bounded deeper-validation manifest."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--live", type=Path)
    source.add_argument("--control-plane-key")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run-output", type=Path, required=True)
    args = parser.parse_args()
    live = (
        json.loads(args.live.read_text(encoding="utf-8"))
        if args.live is not None
        else PostgresResearchOSRepository().export_manifest(
            control_plane_key=str(args.control_plane_key)
        )
    )
    contract = load_source_contract(root_dir=ROOT_DIR)
    output, dry_run = build_manifest(
        live, source_contract_digest=str(contract["artifact_digest"])
    )
    atomic_write_text(args.output, json.dumps(output, indent=2, sort_keys=True) + "\n")
    atomic_write_text(
        args.dry_run_output, json.dumps(dry_run, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
