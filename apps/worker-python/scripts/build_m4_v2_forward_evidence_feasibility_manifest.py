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
from dehps.research_os.information_theory.measurement_system_v2.forward_evidence_feasibility import (
    CAPABILITY,
    COMPLETION_FACT,
    GOAL_KEY,
    PROGRAM_FACT,
    REUSE_POLICY_FACT,
    SUCCESSOR_TASK_KEY,
    TASK_KEY,
    load_source_contract,
)
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.repository import PostgresResearchOSRepository


class M4V2ForwardEvidenceFeasibilityManifestError(ValueError):
    pass


CONTROL_PLANE_KEY = "m4-information-theory-mainline"
BASELINE_MANIFEST_DIGEST = (
    "7fedbd48cc7b1f27d7c5868720d167d707f796e84447f569ee1a2f80c92f0e78"
)
BASELINE_SNAPSHOT_DIGEST = (
    "1c3c21cb92e634f4162a2784079f0c5d411e45abc12acd864ef30a7df05fd1d2"
)
FORMAL_P4_TASK_KEY = "m4-p4-negative-controls-and-robustness"
SOURCE_FACT_PREFIX = "m4-v2-forward-evidence-feasibility-source:"
NEW_TASK_KEYS = (TASK_KEY, SUCCESSOR_TASK_KEY)


def _dependency(kind: str, key: str, status: str) -> dict[str, str]:
    return {"dependency_type": kind, "target_key": key, "required_status": status}


def _goal() -> dict[str, Any]:
    return {
        "goal_key": GOAL_KEY,
        "semantic_version": "1.0.0",
        "question": (
            "Which single prospective program is scientifically valid and operationally "
            "actionable after the closed power-inconclusive P3 and clean diagnostic P4?"
        ),
        "objective_class": "knowledge_quality",
        "owner_lane": "research",
        "baseline_metric_manifest": {
            "p3_scientific_disposition": "INCONCLUSIVE_DUE_TO_POWER",
            "p3_governance_status": "CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION",
            "diagnostic_p4_decision": "NEGATIVE_CONTROLS_CLEAN",
            "formal_p4": "DEPENDENCY_WAIT",
            "additional_independent_folds_required": 2095,
        },
        "target_metric_manifest": {
            "program_decision_count": 1,
            "selected_program": "LAUNCH_BOUNDED_OPERATIONAL_FORWARD_STUDY",
            "target_issue_count": 120,
            "data_reuse_policy": "STAGED_INDEPENDENT_SAMPLES",
            "successor_ready": True,
            "successor_executed": False,
        },
        "success_evidence": [
            "registered zero-compute feasibility artifact",
            "registered scientific Reviewer program decision",
            "registered deterministic decision replay",
            "one ready unexecuted bounded-study preregistration successor",
        ],
        "guardrails": [
            "old P3 unchanged",
            "no PASS_TO_P4",
            "formal P4 remains dependency_wait",
            "no model training or refit",
            "no historical folds, forward checkpoint, settlement, or collection",
            "no P5 or Promotion",
            "cohort A cannot enter later confirmatory P3",
        ],
        "status": "active",
        "retired_at": None,
        "superseded_by_goal_digest": None,
    }


def _integration(*, consumer: str) -> dict[str, Any]:
    return {
        "goal": GOAL_KEY,
        "ready_condition": (
            "registered FORWARD_EVIDENCE_REQUIRED route plus NEGATIVE_CONTROLS_CLEAN "
            "diagnostic decision and registered replay"
        ),
        "runner": "research_evidence_supervisor",
        "upstream_artifacts": [
            "M4V2DeeperValidationDecisionArtifact",
            "M4V2SupersedingGlobalRouteArtifact",
            "M4P4DiagnosticDecisionArtifact",
            "M4P4DiagnosticDecisionReplayArtifact",
            "Research Request 634 / Execution 518 / Reviewer Decision 2667",
        ],
        "downstream_artifacts": [
            "M4V2ForwardEvidenceFeasibilityArtifact",
            "M4V2ForwardEvidenceProgramDecisionArtifact",
            "M4V2ForwardEvidenceProgramDecisionReplayArtifact",
        ],
        "status_projection": "unified_m4_status.forward_evidence_program",
        "evidence_progress_rule": "zero_compute_decision_adds_no predictive evidence",
        "decision_consumer": consumer,
        "downstream_consumer": consumer,
    }


def _decision_task(source_digest: str) -> dict[str, Any]:
    return {
        "task_key": TASK_KEY,
        "goal_key": GOAL_KEY,
        "task_type": CAPABILITY,
        "lane": "research",
        "priority": 124,
        "dependencies": [
            _dependency(
                "artifact", "m4-v2-routing:FORWARD_EVIDENCE_REQUIRED", "available"
            ),
            _dependency(
                "artifact",
                "m4-p4-diagnostic-decision:NEGATIVE_CONTROLS_CLEAN",
                "available",
            ),
            _dependency(
                "artifact",
                "m4-p4-diagnostic-negative-controls-decision:REGISTERED_REPLAY_VERIFIED",
                "available",
            ),
        ],
        "input_artifact_digests": [source_digest],
        "requested_capability": CAPABILITY,
        "metric_contract": {
            "engineering_complete": True,
            "engineering_increment_percent": 0,
            "evidence_complete": False,
            "evidence_increment_percent": 0,
            "phase": "M4-V2-FORWARD-EVIDENCE-FEASIBILITY-AND-PROGRAM-DECISION",
            "scope": "zero_compute_forward_program_decision",
            "completion_fact": COMPLETION_FACT,
            "scientific_computation": 0,
            "model_training_started": False,
            "model_refit": False,
            "historical_p3_folds": 0,
            "forward_samples": 0,
            "forward_checkpoints": 0,
            "settlements": 0,
            "formal_p4_modified": False,
            "pass_to_p4_emitted": False,
            "p5_started": False,
            "promotion_triggered": False,
            "production_action": "none",
            "mainline_integration": _integration(consumer=SUCCESSOR_TASK_KEY),
        },
        "status": "draft",
        "completion_classification": "INTEGRATION_PENDING",
    }


def _successor_task() -> dict[str, Any]:
    return {
        "task_key": SUCCESSOR_TASK_KEY,
        "goal_key": GOAL_KEY,
        "task_type": "bounded_operational_forward_study_preregistration",
        "lane": "research",
        "priority": 123,
        "dependencies": [
            _dependency("task", TASK_KEY, "completed"),
            _dependency("artifact", COMPLETION_FACT, "available"),
            _dependency("artifact", PROGRAM_FACT, "available"),
            _dependency("artifact", REUSE_POLICY_FACT, "available"),
        ],
        "input_artifact_digests": [],
        "requested_capability": None,
        "metric_contract": {
            "engineering_complete": False,
            "engineering_increment_percent": 0,
            "evidence_complete": False,
            "evidence_increment_percent": 0,
            "phase": "M4-V2-BOUNDED-OPERATIONAL-FORWARD-STUDY-PREREGISTRATION",
            "scope": "ready_unexecuted_successor_identity_only",
            "target_issue_count": 120,
            "maximum_issue_count": 120,
            "data_reuse_policy": "STAGED_INDEPENDENT_SAMPLES",
            "execution_authorized": False,
            "forward_collection_started": False,
            "production_action": "none",
            "mainline_integration": {
                "goal": GOAL_KEY,
                "ready_condition": "the registered Reviewer program decision is complete",
                "runner": "not_implemented_not_authorized",
                "upstream_artifacts": [
                    "M4V2ForwardEvidenceProgramDecisionArtifact",
                    "M4V2ForwardEvidenceProgramDecisionReplayArtifact",
                ],
                "downstream_artifacts": ["future preregistration contract only"],
                "status_projection": "Ready Queue only",
                "evidence_progress_rule": "no work or evidence in this goal",
                "decision_consumer": "future separately authorized Research Request",
                "downstream_consumer": "future separately authorized Research Request",
            },
        },
        "status": "draft",
        "completion_classification": "INTEGRATION_PENDING",
    }


def build_manifest(
    live_payload: Mapping[str, Any], *, source_contract_digest: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    live = ControlPlaneManifest.from_dict(deepcopy(dict(live_payload)))
    if live.artifact_digest != BASELINE_MANIFEST_DIGEST:
        raise M4V2ForwardEvidenceFeasibilityManifestError("forward_baseline_changed")
    baseline_snapshot = ResearchOSControlPlane().resolve(live)
    if baseline_snapshot.snapshot_digest != BASELINE_SNAPSHOT_DIGEST:
        raise M4V2ForwardEvidenceFeasibilityManifestError("forward_snapshot_changed")
    if any(goal.goal_key == GOAL_KEY for goal in live.goals) or any(
        task.task_key in NEW_TASK_KEYS for task in live.tasks
    ):
        raise M4V2ForwardEvidenceFeasibilityManifestError("forward_identity_exists")
    payload = live.to_dict(include_digest=False)
    payload["goals"].append(_goal())
    payload["tasks"].extend((_decision_task(source_contract_digest), _successor_task()))
    source_fact = SOURCE_FACT_PREFIX + source_contract_digest
    payload["facts"]["artifacts"] = sorted(
        {*payload["facts"]["artifacts"], source_fact}
    )
    output = ControlPlaneManifest.from_dict(payload)
    snapshot = ResearchOSControlPlane().resolve(output)
    ready = tuple(item.task_key for item in snapshot.ready_queue)
    formal = next(
        item for item in snapshot.resolutions if item.task_key == FORMAL_P4_TASK_KEY
    )
    if ready != (TASK_KEY,) or formal.status.value != "dependency_wait":
        raise M4V2ForwardEvidenceFeasibilityManifestError(
            f"forward_ready_or_formal_changed:{ready}:{formal.status.value}"
        )
    dry_run = {
        "schema_version": "dehps-m4-v2-forward-evidence-feasibility-manifest-dry-run.v1",
        "status": "VERIFIED",
        "baseline_manifest_digest": live.artifact_digest,
        "baseline_snapshot_digest": baseline_snapshot.snapshot_digest,
        "output_manifest_digest": output.artifact_digest,
        "output_snapshot_digest": snapshot.snapshot_digest,
        "source_contract_digest": source_contract_digest,
        "new_goal_key": GOAL_KEY,
        "new_task_keys": list(NEW_TASK_KEYS),
        "unique_ready_task": TASK_KEY,
        "successor_status": "dependency_wait",
        "formal_p4_status": "dependency_wait",
        "model_training": "NOT_STARTED",
        "historical_p3_folds": 0,
        "forward_checkpoints": 0,
        "settlements": 0,
        "p5": "NOT_AUTHORIZED",
        "promotion": "NOT_TRIGGERED",
    }
    return output.to_dict(include_digest=True), dry_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Build M4-v2 forward program manifest")
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
