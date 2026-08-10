from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.p2_repair_outcome_closure import (
    P2_CLOSURE_CAPABILITY,
    P2_CLOSURE_COMPLETION_FACT,
    P2_CLOSURE_SOURCE_CONTRACT_PATH,
    P2_CLOSURE_TASK_KEY,
    P2R_EXECUTION_APPROVED_EVENT,
    P2R_TASK_KEY,
    P25_DECISION_POLICY_DIGEST,
    P26_VALIDATION_MANIFEST_DIGEST,
    P27_GATE_DIGEST,
    P27_REPLAY_DIGEST,
    P261_FROZEN_FIXTURE_DIGEST,
    P263_SUPERSEDING_FIXTURE_DIGEST,
    P263_UPDATE_POLICY_DIGEST,
    RESEARCH_CONTEXT_FINGERPRINT,
    RESEARCH_EXECUTION_ID,
    RESEARCH_REQUEST_ID,
    load_p2_repair_outcome_closure_source_contract,
    verify_p2_repair_outcome_closure_source_bytes,
)
from dehps.research_os.models import ControlPlaneManifest, stable_json
from dehps.research_os.repository import PostgresResearchOSRepository

CONTROL_PLANE_KEY = "m4-information-theory-mainline"
M4_GOAL_KEY = "M4_INFORMATION_THEORY_EVIDENCE"
P27_TASK_KEY = "m4-p2-automatic-gate-and-report"
P27_REPLAY_TASK_KEY = "m4-v2-p2-7-measurement-gate-replay"
P27_REPLAY_FACT = "m4-p2-7-measurement-gate-replay:VERIFIED"
P27_DECISION_FACT = "m4-p2-measurement-decision:REPAIR_MEASUREMENT_SYSTEM"
P2_CLOSURE_APPROVED_EVENT = "research-contract:m4-p2-repair-outcome-closure:approved"
P2_CLOSURE_SOURCE_FACT_PREFIX = "m4-p2-repair-outcome-closure-source:"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"JSON root must be an object: {path}")
    return payload


def _task(payload: dict[str, Any], task_key: str) -> dict[str, Any]:
    matches = [item for item in payload["tasks"] if item.get("task_key") == task_key]
    if len(matches) != 1:
        raise SystemExit(f"task is not singular: {task_key}")
    return matches[0]


def _replace_prefixed_fact(
    values: list[str], *, prefix: str, replacement: str
) -> list[str]:
    output = [value for value in values if not value.startswith(prefix)]
    if replacement not in output:
        output.append(replacement)
    return output


def _append_once(values: list[str], value: str) -> list[str]:
    return values if value in values else [*values, value]


def _closure_task(source_digest: str) -> dict[str, Any]:
    return {
        "task_key": P2_CLOSURE_TASK_KEY,
        "goal_key": M4_GOAL_KEY,
        "task_type": "m4_p2_repair_outcome_closure",
        "lane": "research",
        "priority": 102,
        "dependencies": [
            {
                "dependency_type": "task",
                "target_key": P27_TASK_KEY,
                "required_status": "completed",
            },
            {
                "dependency_type": "task",
                "target_key": P27_REPLAY_TASK_KEY,
                "required_status": "completed",
            },
            {
                "dependency_type": "artifact",
                "target_key": P27_DECISION_FACT,
                "required_status": "available",
            },
            {
                "dependency_type": "artifact",
                "target_key": P27_REPLAY_FACT,
                "required_status": "available",
            },
            {
                "dependency_type": "external_event",
                "target_key": P2_CLOSURE_APPROVED_EVENT,
                "required_status": "available",
            },
        ],
        "input_artifact_digests": [
            source_digest,
            RESEARCH_CONTEXT_FINGERPRINT,
            P25_DECISION_POLICY_DIGEST,
            P26_VALIDATION_MANIFEST_DIGEST,
            P263_UPDATE_POLICY_DIGEST,
            P261_FROZEN_FIXTURE_DIGEST,
            P263_SUPERSEDING_FIXTURE_DIGEST,
            P27_GATE_DIGEST,
            P27_REPLAY_DIGEST,
        ],
        "requested_capability": P2_CLOSURE_CAPABILITY,
        "metric_contract": {
            "engineering_complete": True,
            "engineering_increment_percent": 0,
            "evidence_complete": False,
            "evidence_increment_percent": 0,
            "phase": "M4-P2-CLOSURE",
            "scope": "compile_immutable_repair_outcome_without_measurement_compute",
            "terminal_status": "COMPLETE_WITH_REPAIR_OUTCOME",
            "decision": "REPAIR_MEASUREMENT_SYSTEM",
            "research_request_id": RESEARCH_REQUEST_ID,
            "research_execution_id": RESEARCH_EXECUTION_ID,
            "compute_authorized": False,
            "historical_database_reads": 0,
            "artifact_mutation_allowed": False,
            "evidence_created": False,
            "promotion_gate_opened": False,
            "production_action": "none",
            "mainline_integration": {
                "goal": M4_GOAL_KEY,
                "ready_condition": (
                    "P2.7 gate and registered replay are complete with the immutable "
                    "REPAIR decision, and Research Request 468 is completed"
                ),
                "runner": "research_evidence_supervisor",
                "upstream_artifacts": [
                    "frozen P2 decision policy",
                    "frozen P2.6 validation manifest",
                    "P2.6.1 FROZEN_INCOMPLETE fixture",
                    "P2.6.3 SUPERSEDING_COMPLETE fixture and policy",
                    "registered P2.7 gate",
                    "registered P2.7 gate replay",
                    "Research Request 468 / Execution 389",
                ],
                "downstream_artifacts": [
                    "immutable P2 repair-outcome closure",
                    "canonical zero-work mainline execution",
                ],
                "status_projection": "unified_m4_status.p2_closure",
                "evidence_progress_rule": "closure_creates_no_evidence",
                "decision_consumer": P2R_TASK_KEY,
                "downstream_consumer": P2R_TASK_KEY,
            },
        },
        "status": "draft",
        "completion_classification": "INTEGRATION_PENDING",
    }


def _p2r_task() -> dict[str, Any]:
    return {
        "task_key": P2R_TASK_KEY,
        "goal_key": M4_GOAL_KEY,
        "task_type": "m4_p2r_measurement_repair_validation",
        "lane": "research",
        "priority": 89,
        "dependencies": [
            {
                "dependency_type": "task",
                "target_key": P2_CLOSURE_TASK_KEY,
                "required_status": "completed",
            },
            {
                "dependency_type": "artifact",
                "target_key": P2_CLOSURE_COMPLETION_FACT,
                "required_status": "available",
            },
            {
                "dependency_type": "external_event",
                "target_key": P2R_EXECUTION_APPROVED_EVENT,
                "required_status": "available",
            },
        ],
        "input_artifact_digests": [RESEARCH_CONTEXT_FINGERPRINT],
        "requested_capability": None,
        "metric_contract": {
            "engineering_complete": False,
            "engineering_increment_percent": 0,
            "evidence_complete": False,
            "evidence_increment_percent": 0,
            "phase": "M4-P2R",
            "status": "PENDING_VALIDATION",
            "scope": "future_independent_measurement_repair_validation",
            "research_request_id": RESEARCH_REQUEST_ID,
            "research_execution_id": RESEARCH_EXECUTION_ID,
            "seed_root_sha256": RESEARCH_CONTEXT_FINGERPRINT,
            "failed_p2_samples_available_for_tuning": False,
            "validation_execution_authorized": False,
            "m4_p3_dependency": False,
            "evidence_created": False,
            "promotion_gate_opened": False,
            "production_action": "none",
            "mainline_integration": {
                "goal": M4_GOAL_KEY,
                "ready_condition": (
                    "P2 closure is replay-verified and a future separate P2R "
                    "execution Research Request is approved"
                ),
                "runner": "pending_separately_authorized_p2r_capability",
                "upstream_artifacts": [
                    "P2 repair-outcome closure",
                    "Research Request 468 independent validation preregistration",
                ],
                "downstream_artifacts": [
                    "future independent validation samples",
                    "future isolation audit",
                    "future all-obligations gate and replay",
                ],
                "status_projection": "unified_m4_status.p2r",
                "evidence_progress_rule": "no_evidence_before_future_execution_and_decision",
                "decision_consumer": "future separately authorized P2R decision",
                "downstream_consumer": "future separately authorized P2R decision",
            },
        },
        "status": "draft",
        "completion_classification": "INTEGRATION_PENDING",
    }


def build_source_payload(
    payload: dict[str, Any], *, source_digest: str
) -> dict[str, Any]:
    source = copy.deepcopy(payload)
    source.pop("artifact_digest", None)
    source.pop("manifest_digest", None)
    before_p3 = {
        item["task_key"]: copy.deepcopy(item)
        for item in source["tasks"]
        if str(item["task_key"]).startswith("m4-p3")
    }
    closure = _closure_task(source_digest)
    p2r = _p2r_task()
    output_tasks: list[dict[str, Any]] = []
    p2r_seen = False
    for item in source["tasks"]:
        if item["task_key"] == P2_CLOSURE_TASK_KEY:
            output_tasks.append(closure)
        elif item["task_key"] == P2R_TASK_KEY:
            output_tasks.append(p2r)
            p2r_seen = True
        else:
            output_tasks.append(item)
    if not p2r_seen:
        output_tasks.append(p2r)
    source["tasks"] = output_tasks
    source["facts"]["artifacts"] = _replace_prefixed_fact(
        source["facts"]["artifacts"],
        prefix=P2_CLOSURE_SOURCE_FACT_PREFIX,
        replacement=P2_CLOSURE_SOURCE_FACT_PREFIX + source_digest,
    )
    source["facts"]["external_events"] = _append_once(
        source["facts"]["external_events"], P2_CLOSURE_APPROVED_EVENT
    )
    manifest = ControlPlaneManifest.from_dict(source)
    source["manifest_digest"] = manifest.artifact_digest
    after_p3 = {
        item["task_key"]: item
        for item in source["tasks"]
        if str(item["task_key"]).startswith("m4-p3")
    }
    if stable_json(before_p3) != stable_json(after_p3):
        raise SystemExit("M4-P3 task definitions changed during P2 closure migration")
    return source


def build_live_migration(
    *, live_payload: dict[str, Any], source_payload: dict[str, Any], source_digest: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    return build_additive_m4_v2_manifest(
        live_payload=live_payload,
        source_payload=source_payload,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(P2R_TASK_KEY,),
        allowlisted_revised_task_keys=(P2_CLOSURE_TASK_KEY,),
        add_artifact_facts=(P2_CLOSURE_SOURCE_FACT_PREFIX + source_digest,),
        add_external_events=(P2_CLOSURE_APPROVED_EVENT,),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the additive zero-work M4-P2 repair closure migration."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run-output", type=Path)
    parser.add_argument("--live-from-database", action="store_true")
    args = parser.parse_args()

    contract = load_p2_repair_outcome_closure_source_contract(
        ROOT_DIR / P2_CLOSURE_SOURCE_CONTRACT_PATH
    )
    verify_p2_repair_outcome_closure_source_bytes(root_dir=ROOT_DIR, contract=contract)
    source = build_source_payload(
        _load(args.source), source_digest=contract["artifact_digest"]
    )
    if args.live_from_database:
        live = (
            PostgresResearchOSRepository()
            .load_manifest(control_plane_key=CONTROL_PLANE_KEY)
            .to_dict(include_digest=True)
        )
        output, dry_run = build_live_migration(
            live_payload=live,
            source_payload=source,
            source_digest=contract["artifact_digest"],
        )
    else:
        output = source
        dry_run = {
            "status": "SOURCE_ONLY",
            "output_manifest_digest": source["manifest_digest"],
            "import_performed": False,
            "production_action": "none",
        }
    atomic_write_text(args.output, json.dumps(output, indent=2) + "\n")
    if args.dry_run_output is not None:
        atomic_write_text(
            args.dry_run_output,
            json.dumps(dry_run, indent=2, sort_keys=True) + "\n",
        )


if __name__ == "__main__":
    main()
