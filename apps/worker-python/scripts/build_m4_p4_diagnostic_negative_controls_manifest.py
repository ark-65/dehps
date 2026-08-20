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
from dehps.research_os.information_theory.measurement_system_v2.diagnostic_negative_controls import (
    DECISION_CAPABILITY,
    DECISION_COMPLETION_FACT,
    DECISION_TASK_KEY,
    EVIDENCE_CAPABILITY,
    EVIDENCE_COMPLETION_FACT,
    EVIDENCE_TASK_KEY,
    EXECUTION_CAPABILITY,
    EXECUTION_COMPLETION_FACT,
    EXECUTION_TASK_KEY,
    FORMAL_P4_TASK_KEY,
    FORWARD_ROUTE_FACT,
    P3_CLOSED_FACT,
    P3_CLOSURE_CAPABILITY,
    P3_CLOSURE_COMPLETION_FACT,
    P3_CLOSURE_TASK_KEY,
    PREREGISTRATION_CAPABILITY,
    PREREGISTRATION_COMPLETION_FACT,
    PREREGISTRATION_TASK_KEY,
    REPLAY_CAPABILITY,
    REPLAY_COMPLETION_FACT,
    REPLAY_TASK_KEY,
    REPLAY_VERIFIED_FACT,
    load_source_contract,
)
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.repository import PostgresResearchOSRepository


class M4P4DiagnosticManifestError(ValueError):
    pass


CONTROL_PLANE_KEY = "m4-information-theory-mainline"
GOAL_KEY = "M4_P4_DIAGNOSTIC_NEGATIVE_CONTROLS"
BASELINE_MANIFEST_DIGEST = (
    "31604e59c8355c97ee680fbd3bd6ba5a89b4e4d8ddbb961dc36880a4eba34ac8"
)
BASELINE_SNAPSHOT_DIGEST = (
    "7ae3457d07553ab90d3fd8813c551230bb4dcaef8de4df91e225a9c225790ef0"
)
DEEPER_ROUTE_REPLAY_FACT = (
    "m4-v2-global-routing-after-deeper-validation:REGISTERED_REPLAY_VERIFIED"
)
SOURCE_FACT_PREFIX = "m4-p4-diagnostic-negative-controls-source:"


def _dependency(
    dependency_type: str, target_key: str, required_status: str
) -> dict[str, str]:
    return {
        "dependency_type": dependency_type,
        "target_key": target_key,
        "required_status": required_status,
    }


def _goal() -> dict[str, Any]:
    return {
        "goal_key": GOAL_KEY,
        "semantic_version": "1.0.0",
        "question": (
            "Does the frozen historical evaluator reject six preregistered diagnostic "
            "negative controls and catch deliberate time-boundary violations without "
            "changing the closed inconclusive P3 disposition?"
        ),
        "objective_class": "knowledge_quality",
        "owner_lane": "research",
        "baseline_metric_manifest": {
            "p3_scientific_disposition": "INCONCLUSIVE_DUE_TO_POWER",
            "p3_governance_status": "CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION",
            "formal_p4": "DEPENDENCY_WAIT",
            "primary_endpoint": "mean settled issue-level prequential score difference in bits per issue",
            "practical_threshold_bits_per_issue": 0.01,
        },
        "target_metric_manifest": {
            "control_count": 6,
            "diagnostic_only": True,
            "confirmatory_p4": False,
            "allowed_decisions": [
                "NEGATIVE_CONTROLS_CLEAN",
                "LEAKAGE_OR_EVALUATOR_ARTIFACT_DETECTED",
                "INCONCLUSIVE_NEGATIVE_CONTROLS",
                "INVALID_NEGATIVE_CONTROL_EXECUTION",
            ],
            "eligible_for_p5": False,
            "eligible_for_promotion": False,
        },
        "success_evidence": [
            "registered P3 inconclusive closure consolidation",
            "result-blind diagnostic P4 preregistration",
            "six-family frozen negative-control execution",
            "diagnostic Evidence Compiler",
            "typed diagnostic decision and registered replay",
        ],
        "guardrails": [
            "no PASS_TO_P4",
            "formal P4 remains dependency_wait",
            "no new or revised historical folds",
            "randomized repeats are not independent information",
            "future-shift sentinel never enters legal prediction output",
            "no P5 or Promotion",
            "no model training, new model, new feature, or tuning",
            "production_action_none",
        ],
        "status": "active",
        "retired_at": None,
        "superseded_by_goal_digest": None,
    }


def _integration(
    *,
    ready_condition: str,
    upstream: list[str],
    downstream: list[str],
    decision_consumer: str,
    evidence_progress_rule: str,
) -> dict[str, Any]:
    return {
        "goal": GOAL_KEY,
        "ready_condition": ready_condition,
        "runner": "research_evidence_supervisor",
        "upstream_artifacts": upstream,
        "downstream_artifacts": downstream,
        "status_projection": "unified_m4_status.diagnostic_p4",
        "evidence_progress_rule": evidence_progress_rule,
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
    evidence_progress_rule: str,
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
            "scope": "diagnostic_only_negative_controls_after_closed_inconclusive_p3",
            "completion_fact": completion_fact,
            "diagnostic_only": True,
            "confirmatory_p4": False,
            "formal_p4_modified": False,
            "pass_to_p4_emitted": False,
            "predictive_p3_folds": 0,
            "p5_started": False,
            "promotion_triggered": False,
            "model_training_started": False,
            "new_model": "NONE",
            "production_action": "none",
            "mainline_integration": _integration(
                ready_condition=ready_condition,
                upstream=upstream,
                downstream=downstream,
                decision_consumer=decision_consumer,
                evidence_progress_rule=evidence_progress_rule,
            ),
        },
        "status": "draft",
        "completion_classification": "INTEGRATION_PENDING",
    }


def _new_tasks(source_digest: str) -> list[dict[str, Any]]:
    closure = _task(
        task_key=P3_CLOSURE_TASK_KEY,
        capability=P3_CLOSURE_CAPABILITY,
        priority=130,
        dependencies=[
            _dependency("artifact", DEEPER_ROUTE_REPLAY_FACT, "available"),
            _dependency("artifact", P3_CLOSED_FACT, "available"),
            _dependency("artifact", FORWARD_ROUTE_FACT, "available"),
        ],
        source_digest=source_digest,
        completion_fact=P3_CLOSURE_COMPLETION_FACT,
        phase="M4-P3-INCONCLUSIVE-CLOSURE-CONSOLIDATION",
        ready_condition=(
            "the superseding FORWARD_EVIDENCE_REQUIRED route and registered P3 closure replay are complete"
        ),
        upstream=[
            "registered historical inference identity",
            "Deeper Validation decision",
            "registered predictive P3 closure identity",
        ],
        downstream=["M4P3InconclusiveClosureArtifact", P3_CLOSURE_COMPLETION_FACT],
        decision_consumer=PREREGISTRATION_TASK_KEY,
        evidence_progress_rule="zero_compute_closure_creates_no_new_scientific_evidence",
    )
    preregistration = _task(
        task_key=PREREGISTRATION_TASK_KEY,
        capability=PREREGISTRATION_CAPABILITY,
        priority=129,
        dependencies=[
            _dependency("task", P3_CLOSURE_TASK_KEY, "completed"),
            _dependency("artifact", P3_CLOSURE_COMPLETION_FACT, "available"),
        ],
        source_digest=source_digest,
        completion_fact=PREREGISTRATION_COMPLETION_FACT,
        phase="M4-P4-DIAGNOSTIC-NEGATIVE-CONTROLS-PREREGISTRATION",
        ready_condition="the typed P3 inconclusive closure is registered",
        upstream=[
            "M4P3InconclusiveClosureArtifact",
            "Research Request 629 / Execution 513",
            "Reviewer Decision 2642",
            "frozen source, dataset, folds, endpoint, controls, seeds, repeats and gates",
        ],
        downstream=[
            "M4P4DiagnosticNegativeControlsPreregistrationArtifact",
            PREREGISTRATION_COMPLETION_FACT,
        ],
        decision_consumer=EXECUTION_TASK_KEY,
        evidence_progress_rule="result_blind_preregistration_creates_no_result_evidence",
    )
    execution = _task(
        task_key=EXECUTION_TASK_KEY,
        capability=EXECUTION_CAPABILITY,
        priority=128,
        dependencies=[
            _dependency("task", PREREGISTRATION_TASK_KEY, "completed"),
            _dependency("artifact", PREREGISTRATION_COMPLETION_FACT, "available"),
        ],
        source_digest=source_digest,
        completion_fact=EXECUTION_COMPLETION_FACT,
        phase="M4-P4-DIAGNOSTIC-NEGATIVE-CONTROLS-EXECUTION",
        ready_condition="the result-blind diagnostic P4 preregistration is registered",
        upstream=[
            "registered historical dataset snapshot",
            "registered 2581-fold manifest",
            "frozen marginal evaluator source",
            "M4P4DiagnosticNegativeControlsPreregistrationArtifact",
        ],
        downstream=[
            "M4P4DiagnosticNegativeControlsExecutionArtifact",
            EXECUTION_COMPLETION_FACT,
        ],
        decision_consumer=EVIDENCE_TASK_KEY,
        evidence_progress_rule="mechanical diagnostic refits create raw diagnostic output only",
    )
    evidence = _task(
        task_key=EVIDENCE_TASK_KEY,
        capability=EVIDENCE_CAPABILITY,
        priority=127,
        dependencies=[
            _dependency("task", EXECUTION_TASK_KEY, "completed"),
            _dependency("artifact", EXECUTION_COMPLETION_FACT, "available"),
        ],
        source_digest=source_digest,
        completion_fact=EVIDENCE_COMPLETION_FACT,
        phase="M4-P4-DIAGNOSTIC-EVIDENCE-COMPILER",
        ready_condition="the complete six-control execution artifact is registered",
        upstream=[
            "M4P4DiagnosticNegativeControlsPreregistrationArtifact",
            "M4P4DiagnosticNegativeControlsExecutionArtifact",
        ],
        downstream=["M4P4DiagnosticEvidenceArtifact", EVIDENCE_COMPLETION_FACT],
        decision_consumer=DECISION_TASK_KEY,
        evidence_progress_rule="compile diagnostic-only evidence without P3, P5 or Promotion credit",
    )
    decision = _task(
        task_key=DECISION_TASK_KEY,
        capability=DECISION_CAPABILITY,
        priority=126,
        dependencies=[
            _dependency("task", EVIDENCE_TASK_KEY, "completed"),
            _dependency("artifact", EVIDENCE_COMPLETION_FACT, "available"),
        ],
        source_digest=source_digest,
        completion_fact=DECISION_COMPLETION_FACT,
        phase="M4-P4-DIAGNOSTIC-DECISION",
        ready_condition="the typed diagnostic Evidence Compiler output is registered",
        upstream=["M4P4DiagnosticEvidenceArtifact", "frozen decision priority"],
        downstream=["M4P4DiagnosticDecisionArtifact", DECISION_COMPLETION_FACT],
        decision_consumer=REPLAY_TASK_KEY,
        evidence_progress_rule="deterministic typed decision consumes only preregistered diagnostic evidence",
    )
    replay = _task(
        task_key=REPLAY_TASK_KEY,
        capability=REPLAY_CAPABILITY,
        priority=125,
        dependencies=[
            _dependency("task", DECISION_TASK_KEY, "completed"),
            _dependency("artifact", DECISION_COMPLETION_FACT, "available"),
        ],
        source_digest=source_digest,
        completion_fact=REPLAY_COMPLETION_FACT,
        phase="M4-P4-DIAGNOSTIC-DECISION-REPLAY",
        ready_condition="the typed diagnostic decision is registered",
        upstream=["M4P4DiagnosticDecisionArtifact", "decision registration identity"],
        downstream=[
            "M4P4DiagnosticDecisionReplayArtifact",
            REPLAY_VERIFIED_FACT,
            REPLAY_COMPLETION_FACT,
        ],
        decision_consumer="terminal:FORWARD_EVIDENCE_REQUIRED_OR_EVALUATOR_REPAIR",
        evidence_progress_rule="registered replay verifies identity without rerunning controls",
    )
    return [closure, preregistration, execution, evidence, decision, replay]


NEW_TASK_KEYS = tuple(task["task_key"] for task in _new_tasks("0" * 64))


def build_manifest(
    live_payload: Mapping[str, Any], *, source_contract_digest: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    live = ControlPlaneManifest.from_dict(deepcopy(dict(live_payload)))
    if live.artifact_digest != BASELINE_MANIFEST_DIGEST:
        raise M4P4DiagnosticManifestError("diagnostic_p4_baseline_changed")
    baseline_snapshot = ResearchOSControlPlane().resolve(live)
    if baseline_snapshot.snapshot_digest != BASELINE_SNAPSHOT_DIGEST:
        raise M4P4DiagnosticManifestError("diagnostic_p4_baseline_snapshot_changed")
    if any(goal.goal_key == GOAL_KEY for goal in live.goals) or any(
        task.task_key in NEW_TASK_KEYS for task in live.tasks
    ):
        raise M4P4DiagnosticManifestError("diagnostic_p4_identity_already_present")
    formal_p4 = next(
        (task for task in live.tasks if task.task_key == FORMAL_P4_TASK_KEY), None
    )
    if formal_p4 is None:
        raise M4P4DiagnosticManifestError("formal_p4_missing")
    payload = live.to_dict(include_digest=False)
    payload["goals"].append(_goal())
    payload["tasks"].extend(_new_tasks(source_contract_digest))
    source_fact = SOURCE_FACT_PREFIX + source_contract_digest
    payload["facts"]["artifacts"] = sorted(
        {*payload["facts"]["artifacts"], source_fact}
    )
    output = ControlPlaneManifest.from_dict(payload)
    output_snapshot = ResearchOSControlPlane().resolve(output)
    ready = tuple(item.task_key for item in output_snapshot.ready_queue)
    formal_resolution = next(
        item
        for item in output_snapshot.resolutions
        if item.task_key == FORMAL_P4_TASK_KEY
    )
    if ready != (P3_CLOSURE_TASK_KEY,) or formal_resolution.status.value != "dependency_wait":
        raise M4P4DiagnosticManifestError(
            f"diagnostic_p4_ready_or_formal_p4_changed:{ready}:{formal_resolution.status.value}"
        )
    dry_run = {
        "schema_version": "dehps-m4-p4-diagnostic-negative-controls-manifest-dry-run.v1",
        "artifact_type": "m4_p4_diagnostic_negative_controls_manifest_dry_run",
        "status": "VERIFIED",
        "baseline_manifest_digest": live.artifact_digest,
        "baseline_snapshot_digest": baseline_snapshot.snapshot_digest,
        "output_manifest_digest": output.artifact_digest,
        "output_snapshot_digest": output_snapshot.snapshot_digest,
        "source_contract_digest": source_contract_digest,
        "new_goal_key": GOAL_KEY,
        "new_task_keys": list(NEW_TASK_KEYS),
        "unique_ready_task": P3_CLOSURE_TASK_KEY,
        "formal_p4_status": "dependency_wait",
        "pass_to_p4_emitted": False,
        "predictive_p3_folds": 0,
        "p5_started": False,
        "promotion_triggered": False,
    }
    return output.to_dict(include_digest=True), dry_run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the additive M4 diagnostic-negative-control manifest."
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
