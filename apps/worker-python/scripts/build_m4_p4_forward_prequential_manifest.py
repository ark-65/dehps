from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.measurement_system_v2 import (
    formal_p4_forward_prequential as formal_p4,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_task_manifest,
)
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.repository import PostgresResearchOSRepository


class FormalP4ManifestError(ValueError):
    pass


CONTROL_PLANE_KEY = formal_p4.CONTROL_PLANE_KEY


def _dependency(kind: str, key: str, status: str) -> dict[str, str]:
    return {"dependency_type": kind, "target_key": key, "required_status": status}


def _integration(
    *,
    ready_condition: str,
    evidence_rule: str,
    decision_consumer: str,
    next_consumer: str,
) -> dict[str, Any]:
    return {
        "goal": formal_p4.p3.GOAL_KEY,
        "ready_condition": ready_condition,
        "runner": (
            "FormalP4ForwardPrequentialSupervisor P4-only exact-key dispatch through "
            "unified ResearchEvidenceSupervisor"
        ),
        "upstream_artifacts": [
            "Research Request 646 / Reviewer Decision 2718 / V3 contract digest",
            "Engineering Request 648 / Reviewer Decision 2724 / Execution 527",
            "registered successor P3 PASS review and exact parent graph",
        ],
        "downstream_artifacts": [
            "V3 preregistration/input/control/execution/evidence/decision/typed-replay artifacts"
        ],
        "status_projection": "FORMAL_P4 ARMED_DEPENDENCY_WAIT/READY/COMPLETE",
        "evidence_progress_rule": evidence_rule,
        "decision_consumer": decision_consumer,
        "downstream_consumer": next_consumer,
    }


def _metric_contract(
    *, phase: str, completion_fact: str, integration: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "engineering_complete": True,
        "engineering_increment_percent": 0,
        "evidence_complete": False,
        "evidence_increment_percent": 0,
        "phase": phase,
        "scope": formal_p4.CONTRACT_KEY,
        "contract_digest": formal_p4.CONTRACT_DIGEST,
        "completion_fact": completion_fact,
        "configuration_drift": False,
        "p3_lineage_modified": False,
        "diagnostic_p4_decision_credit": False,
        "p5_started": False,
        "promotion_triggered": False,
        "production_action": "none",
        "mainline_integration": deepcopy(dict(integration)),
    }


def _new_task(
    *,
    key: str,
    capability: str | None,
    task_type: str,
    priority: int,
    dependencies: list[dict[str, str]],
    source_digest: str,
    completion_fact: str,
    ready_condition: str,
    evidence_rule: str,
    decision_consumer: str,
    next_consumer: str,
) -> dict[str, Any]:
    return {
        "task_key": key,
        "goal_key": formal_p4.p3.GOAL_KEY,
        "task_type": task_type,
        "lane": "research",
        "priority": priority,
        "dependencies": dependencies,
        "input_artifact_digests": [source_digest],
        "requested_capability": capability,
        "metric_contract": _metric_contract(
            phase=task_type.upper().replace("_", "-"),
            completion_fact=completion_fact,
            integration=_integration(
                ready_condition=ready_condition,
                evidence_rule=evidence_rule,
                decision_consumer=decision_consumer,
                next_consumer=next_consumer,
            ),
        ),
        "status": "draft",
        "completion_classification": "INTEGRATION_PENDING",
    }


def task_definitions(
    live_payload: Mapping[str, Any], *, source_digest: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = ControlPlaneManifest.from_dict(deepcopy(dict(live_payload)))
    existing = [
        item for item in manifest.tasks if item.task_key == formal_p4.EXECUTION_TASK_KEY
    ]
    if len(existing) != 1:
        raise FormalP4ManifestError("canonical_formal_p4_task_not_unique")
    revised = existing[0].to_dict()
    revised["dependencies"] = [
        _dependency("artifact", formal_p4.CONTRACT_FREEZE_FACT, "available"),
        _dependency("artifact", formal_p4.p3.P3_COMPLETE_FACT, "available"),
        _dependency("artifact", formal_p4.p3.PASS_TO_P4_FACT, "available"),
    ]
    revised["input_artifact_digests"] = [source_digest]
    revised["requested_capability"] = formal_p4.EXECUTION_CAPABILITY
    revised["metric_contract"] = _metric_contract(
        phase="FORMAL-P4-V3-NEGATIVE-CONTROLS-AND-ROBUSTNESS",
        completion_fact=formal_p4.EXECUTION_COMPLETE_FACT,
        integration=_integration(
            ready_condition="V3 freeze + successor P3 COMPLETE + exact PASS_TO_P4",
            evidence_rule=(
                "exact N whole-issue PASS cluster; six frozen controls and five "
                "robustness requirements; no diagnostic decision credit"
            ),
            decision_consumer=formal_p4.EVIDENCE_TASK_KEY,
            next_consumer=formal_p4.EVIDENCE_TASK_KEY,
        ),
    )
    tasks = [
        _new_task(
            key=formal_p4.EVIDENCE_TASK_KEY,
            capability=formal_p4.EVIDENCE_CAPABILITY,
            task_type="formal_p4_evidence_compiler_v3",
            priority=207,
            dependencies=[
                _dependency("task", formal_p4.EXECUTION_TASK_KEY, "completed"),
                _dependency("artifact", formal_p4.EXECUTION_COMPLETE_FACT, "available"),
            ],
            source_digest=source_digest,
            completion_fact=formal_p4.EVIDENCE_COMPILED_FACT,
            ready_condition="canonical Formal P4 execution completed and registered",
            evidence_rule="compile only registered V3 aggregate parents",
            decision_consumer=formal_p4.DECISION_TASK_KEY,
            next_consumer=formal_p4.DECISION_TASK_KEY,
        ),
        _new_task(
            key=formal_p4.DECISION_TASK_KEY,
            capability=formal_p4.DECISION_CAPABILITY,
            task_type="formal_p4_decision_compiler_v3",
            priority=206,
            dependencies=[
                _dependency("task", formal_p4.EVIDENCE_TASK_KEY, "completed"),
                _dependency("artifact", formal_p4.EVIDENCE_COMPILED_FACT, "available"),
            ],
            source_digest=source_digest,
            completion_fact=f"{formal_p4.DECISION_TASK_KEY}:COMPLETE",
            ready_condition="V3 Evidence Compiler completed and registered",
            evidence_rule="INVALID precedence then exact PASS/FAIL scientific gates",
            decision_consumer=formal_p4.REPLAY_TASK_KEY,
            next_consumer=formal_p4.REPLAY_TASK_KEY,
        ),
        _new_task(
            key=formal_p4.REPLAY_TASK_KEY,
            capability=formal_p4.REPLAY_CAPABILITY,
            task_type="formal_p4_decision_replay_v3",
            priority=205,
            dependencies=[
                _dependency("task", formal_p4.DECISION_TASK_KEY, "completed"),
                _dependency(
                    "artifact", f"{formal_p4.DECISION_TASK_KEY}:COMPLETE", "available"
                ),
            ],
            source_digest=source_digest,
            completion_fact=formal_p4.REPLAY_VERIFIED_FACT,
            ready_condition="V3 Decision Compiler completed and registered",
            evidence_rule="recompute decision from registered parents; workload rerun forbidden",
            decision_consumer=formal_p4.SUCCESSOR_P5_TASK_KEY,
            next_consumer=formal_p4.SUCCESSOR_P5_TASK_KEY,
        ),
        _new_task(
            key=formal_p4.SUCCESSOR_P5_TASK_KEY,
            capability=formal_p4.SUCCESSOR_P5_CAPABILITY,
            task_type="successor_forward_evidence_after_formal_p4",
            priority=204,
            dependencies=[
                _dependency("task", formal_p4.EXECUTION_TASK_KEY, "completed"),
                _dependency("artifact", formal_p4.PASS_TO_P5_FACT, "available"),
                _dependency("artifact", formal_p4.REPLAY_VERIFIED_FACT, "available"),
            ],
            source_digest=source_digest,
            completion_fact=f"{formal_p4.SUCCESSOR_P5_TASK_KEY}:COMPLETE",
            ready_condition="P4 completed + V3 PASS_TO_P5 + V3 typed replay",
            evidence_rule="deferred successor P5; no execution in this authorization",
            decision_consumer="future_separately_authorized_successor_P5",
            next_consumer="future_separately_authorized_successor_P5",
        ),
    ]
    return revised, tasks


def _build_manifest(
    live_payload: Mapping[str, Any],
    *,
    source_digest: str,
    include_freeze_fact: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    live = deepcopy(dict(live_payload))
    legacy_before = next(
        item
        for item in ControlPlaneManifest.from_dict(live).tasks
        if item.task_key == formal_p4.LEGACY_P5_TASK_KEY
    ).to_dict()
    revised, new_tasks = task_definitions(live, source_digest=source_digest)
    output, dry_run = build_additive_task_manifest(
        live_payload=live,
        new_tasks=new_tasks,
        revised_tasks=(revised,),
        add_artifact_facts=(
            (formal_p4.CONTRACT_FREEZE_FACT,) if include_freeze_fact else ()
        ),
    )
    manifest = ControlPlaneManifest.from_dict(output)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    resolutions = {item.task_key: item.status.value for item in snapshot.resolutions}
    legacy_after = next(
        item for item in manifest.tasks if item.task_key == formal_p4.LEGACY_P5_TASK_KEY
    ).to_dict()
    p4_statuses = {key: resolutions[key] for key in formal_p4.P4_TASK_KEY_ALLOWLIST}
    if (
        p4_statuses
        != {key: "dependency_wait" for key in formal_p4.P4_TASK_KEY_ALLOWLIST}
        or resolutions[formal_p4.SUCCESSOR_P5_TASK_KEY] != "dependency_wait"
        or legacy_before != legacy_after
        or formal_p4.p3.PASS_TO_P4_FACT in set(manifest.facts.to_dict()["artifacts"])
    ):
        raise FormalP4ManifestError("formal_p4_armed_projection_changed")
    dry_run.update(
        {
            "formal_p4_contract": (
                "FROZEN" if include_freeze_fact else "REGISTRATION_PENDING"
            ),
            "formal_p4_status": "ARMED_DEPENDENCY_WAIT",
            "formal_p4_execution": "NOT_EXECUTED",
            "formal_p4_tasks": p4_statuses,
            "successor_p5": "NOT_STARTED",
            "legacy_p5_unchanged": True,
            "promotion_triggered": False,
        }
    )
    return manifest.to_dict(include_digest=True), dry_run


def build_manifest(
    live_payload: Mapping[str, Any], *, source_digest: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build definitions only; this public path can never emit the freeze fact."""

    return _build_manifest(
        live_payload,
        source_digest=source_digest,
        include_freeze_fact=False,
    )


def build_frozen_manifest(
    live_payload: Mapping[str, Any],
    *,
    source_digest: str,
    repository: PostgresResearchOSRepository,
    registration_execution_id: str,
    registration_digest: str,
    root_dir: Path = ROOT_DIR,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Emit FROZEN only after independently reloading exact durable registration."""

    manifest = ControlPlaneManifest.from_dict(live_payload)
    tasks = [
        item for item in manifest.tasks if item.task_key == formal_p4.EXECUTION_TASK_KEY
    ]
    records = repository.list_mainline_artifacts(
        control_plane_key=CONTROL_PLANE_KEY,
        execution_id=registration_execution_id,
    )
    matches = [
        item
        for item in records
        if item.get("registration_digest") == registration_digest
    ]
    prereg = formal_p4.frozen_preregistration()
    if len(tasks) != 1 or tasks[0].input_artifact_digests != (source_digest,):
        raise FormalP4ManifestError("formal_p4_definition_before_freeze_invalid")
    if len(matches) != 1:
        raise FormalP4ManifestError("formal_p4_preregistration_registration_missing")
    record = matches[0]
    relative = str(record.get("artifact_path") or "")
    path = (root_dir / relative).resolve()
    if not path.is_relative_to(root_dir.resolve()) or not path.is_file():
        raise FormalP4ManifestError(
            "formal_p4_preregistration_registration_path_invalid"
        )
    try:
        registered = formal_p4.validate_artifact(
            json.loads(path.read_text(encoding="utf-8"))
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise FormalP4ManifestError(
            "formal_p4_preregistration_registration_content_invalid"
        ) from exc
    if (
        registered != prereg
        or record.get("execution_id") != registration_execution_id
        or record.get("control_plane_key") != CONTROL_PLANE_KEY
        or record.get("task_key") != formal_p4.EXECUTION_TASK_KEY
        or record.get("task_digest") != tasks[0].artifact_digest
        or record.get("artifact_digest") != prereg["artifact_digest"]
        or record.get("artifact_type") != prereg["artifact_type"]
        or record.get("schema_version") != prereg["schema_version"]
        or tuple(record.get("parent_digests", ())) != tuple(prereg["parent_digests"])
    ):
        raise FormalP4ManifestError("formal_p4_preregistration_registration_changed")
    return _build_manifest(
        live_payload,
        source_digest=source_digest,
        include_freeze_fact=True,
    )


def build_definition_manifest(
    live_payload: Mapping[str, Any], *, source_digest: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Import task definitions before the preregistration receives a fact."""

    return build_manifest(live_payload, source_digest=source_digest)


def activation_simulation(
    live_payload: Mapping[str, Any], *, source_digest: str
) -> dict[str, Any]:
    definition, _ = build_definition_manifest(live_payload, source_digest=source_digest)
    fixture, _ = build_additive_task_manifest(
        live_payload=definition,
        new_tasks=(),
        add_artifact_facts=(
            formal_p4.CONTRACT_FREEZE_FACT,
            formal_p4.p3.P3_COMPLETE_FACT,
            formal_p4.p3.PASS_TO_P4_FACT,
        ),
    )
    manifest = ControlPlaneManifest.from_dict(fixture)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    ready_p4 = [
        item.task_key
        for item in snapshot.ready_queue
        if item.task_key in formal_p4.P4_TASK_KEY_ALLOWLIST
    ]
    supervisor = formal_p4.FormalP4ForwardPrequentialSupervisor(
        repository=PostgresResearchOSRepository(), control_plane_key=CONTROL_PLANE_KEY
    )
    matches = [
        name
        for name in supervisor.capabilities
        if name == formal_p4.EXECUTION_CAPABILITY
    ]
    if ready_p4 != [formal_p4.EXECUTION_TASK_KEY] or matches != [
        formal_p4.EXECUTION_CAPABILITY
    ]:
        raise FormalP4ManifestError("formal_p4_fixture_activation_changed")
    production = ControlPlaneManifest.from_dict(definition)
    production_snapshot = ResearchOSControlPlane().resolve(production)
    production_status = next(
        item.status.value
        for item in production_snapshot.resolutions
        if item.task_key == formal_p4.EXECUTION_TASK_KEY
    )
    return {
        "status": "RESULT_BLIND_ACTIVATION_VERIFIED",
        "fixture_persistent": False,
        "fixture_pass_fact": formal_p4.p3.PASS_TO_P4_FACT,
        "fixture_ready_p4_tasks": ready_p4,
        "unique_capability": matches[0],
        "dispatch_performed": False,
        "formal_p4_executed": False,
        "production_restored_status": (
            "ARMED_DEPENDENCY_WAIT"
            if production_status == "dependency_wait"
            else production_status
        ),
        "p5_executed": False,
        "promotion_triggered": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build definition-only successor Formal P4 V3 manifest"
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--activation-simulation", action="store_true")
    args = parser.parse_args()
    repository = PostgresResearchOSRepository()
    source = formal_p4.load_source_contract(root_dir=ROOT_DIR)
    formal_p4.verify_governance(formal_p4.AgentRequestRepository())
    live = repository.export_manifest(control_plane_key=CONTROL_PLANE_KEY)
    output, dry_run = build_manifest(
        live,
        source_digest=str(source["artifact_digest"]),
    )
    if args.output:
        atomic_write_text(
            args.output,
            json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )
    result: dict[str, Any] = {"migration": dry_run}
    if args.activation_simulation:
        result["activation"] = activation_simulation(
            live, source_digest=str(source["artifact_digest"])
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
