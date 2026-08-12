from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from dehps.research_os.information_theory.measurement_system_v2.migration import (
    AdditiveManifestMigrationError,
    build_additive_task_manifest,
    require_sha256_digest,
)
from dehps.research_os.information_theory.measurement_system_v2.routing import (
    GLOBAL_ROUTE_ARTIFACT_FILENAME,
    GLOBAL_ROUTE_ARTIFACT_SLUG,
    GLOBAL_ROUTE_CAPABILITY,
    GLOBAL_ROUTE_COMPLETION_FACT,
    GLOBAL_ROUTE_TASK_KEY,
)
from dehps.research_os.models import (
    M4_V2_BRANCH_IDS,
    M4_V2_ESTIMAND_DIGESTS,
    M4_V2_MEASUREMENT_CONTRACT_DIGEST,
    M4_V2_MEASUREMENT_CONTRACT_KEY,
)

GOAL_KEY = "M4_INFORMATION_THEORY_EVIDENCE"
CONTRACT_KEY = M4_V2_MEASUREMENT_CONTRACT_KEY
CONTRACT_DIGEST = M4_V2_MEASUREMENT_CONTRACT_DIGEST
BRANCH_ORDER = M4_V2_BRANCH_IDS
ESTIMAND_DIGESTS = M4_V2_ESTIMAND_DIGESTS
SOURCE_FACT = "m4-v2-global-routing-contract:M4_MEASUREMENT_CONTRACT_V2:FROZEN"
REPLAY_FACTS = tuple(
    f"m4-v2-historical-branch-decision-replay:{CONTRACT_KEY}:{branch}:VERIFIED"
    for branch in BRANCH_ORDER
)
GLOBAL_TASK = GLOBAL_ROUTE_TASK_KEY
GLOBAL_CAPABILITY = GLOBAL_ROUTE_CAPABILITY
GLOBAL_COMPLETION_FACT = GLOBAL_ROUTE_COMPLETION_FACT
ADAPTIVE_FACT = "m4-v2-routing:ADAPTIVE_RESEARCH_ELIGIBLE"
P3_PREREG_TASK = "m4-p3-predictive-preregistration-freeze"
P3_PREREG_FACT = "m4-p3-predictive-preregistration:FROZEN"
PREDICTIVE_P3_TASK = "m4-p3-strict-historical-walk-forward"
ALLOWED_ROUTES = (
    "ADAPTIVE_RESEARCH_ELIGIBLE",
    "NO_DETECTABLE_INFORMATION_UNDER_FROZEN_M4_V2_CONTRACT",
    "DEEPER_VALIDATION_REQUIRED",
    "MEASUREMENT_REPAIR_REQUIRED",
)
GLOBAL_DOWNSTREAM_CONSUMER = (
    '{"ADAPTIVE_RESEARCH_ELIGIBLE":"P3_PREDICTIVE_PREREGISTRATION_FREEZE",'
    '"DEEPER_VALIDATION_REQUIRED":"M4_DEEPER_VALIDATION",'
    '"MEASUREMENT_REPAIR_REQUIRED":"MEASUREMENT_REPAIR",'
    '"NO_DETECTABLE_INFORMATION_UNDER_FROZEN_M4_V2_CONTRACT":'
    '"KERNEL_SEARCH_EFFICIENCY"}'
)


def _task(payload: Mapping[str, Any], task_key: str) -> dict[str, Any]:
    matches = [
        deepcopy(dict(item))
        for item in payload.get("tasks", [])
        if item.get("task_key") == task_key
    ]
    if len(matches) != 1:
        raise AdditiveManifestMigrationError(
            f"global_routing_manifest_task_not_singular:{task_key}"
        )
    return matches[0]


def _dep(kind: str, key: str, status: str) -> dict[str, str]:
    return {"dependency_type": kind, "target_key": key, "required_status": status}


def _global_task(live_payload: Mapping[str, Any], source_digest: str) -> dict[str, Any]:
    task = _task(live_payload, GLOBAL_TASK)
    task["dependencies"] = [
        _dep("artifact", SOURCE_FACT, "available"),
        *(_dep("artifact", fact, "available") for fact in REPLAY_FACTS),
    ]
    task["input_artifact_digests"] = [source_digest]
    task["requested_capability"] = GLOBAL_CAPABILITY
    task["metric_contract"] = {
        "phase": "M4-V2-GLOBAL-ROUTING",
        "measurement_contract_key": CONTRACT_KEY,
        "measurement_contract_digest": CONTRACT_DIGEST,
        "canonical_branch_order": list(BRANCH_ORDER),
        "canonical_estimand_digests": dict(ESTIMAND_DIGESTS),
        "allowed_routes": list(ALLOWED_ROUTES),
        "decision_replay_coverage_required": "COMPLETE",
        "measurement_global_coverage_values": ["FULL", "PARTIAL"],
        "router_conclusive_coverage_values": ["FULL", "PARTIAL"],
        "coverage_axes_are_not_aliases": True,
        "full_router_conclusive_coverage_required_for_adaptive": True,
        "partial_positive_route": "DEEPER_VALIDATION_REQUIRED",
        "route_artifact_type": "M4V2GlobalRouteDecisionArtifact",
        "route_serialized_artifact_type": "m4_measurement_routing_decision",
        "route_digest_domain": "dehps.m4.v2.global-routing-decision.v1",
        "route_artifact_slug": GLOBAL_ROUTE_ARTIFACT_SLUG,
        "route_artifact_filename": GLOBAL_ROUTE_ARTIFACT_FILENAME,
        "route_artifact_path_template": (
            "runtime/research-os/mainline/tasks/m4-v2-global-routing/"
            "{execution_id}/artifacts/global-routing-decision/"
            "{artifact_digest}/decision.json"
        ),
        "route_facts": {route: f"m4-v2-routing:{route}" for route in ALLOWED_ROUTES},
        "artifact_types_in_registration_order": [
            "M4V2GlobalRouteDecisionArtifact",
            "research_os_mainline_execution",
        ],
        "completion_fact": GLOBAL_COMPLETION_FACT,
        "route_fact_count": 1,
        "completion_fact_count": 1,
        "registered_artifact_count": 2,
        "mainline_execution_status": "COMPLETE",
        "mainline_completion_classification": "VALIDATED_IN_MAINLINE",
        "historical_database_reads": 0,
        "numeric_branch_result_reads": 0,
        "historical_folds_executed": 0,
        "scientific_computation": 0,
        "evidence_created": False,
        "promotion_gate_opened": False,
        "production_action": "none",
        "zero_write_replay": True,
        "mainline_integration": {
            "goal": GOAL_KEY,
            "ready_condition": "the exact source fact and all three canonical replay facts are available",
            "runner": "research_evidence_supervisor",
            "upstream_artifacts": [SOURCE_FACT, *REPLAY_FACTS],
            "downstream_artifacts": [
                "M4V2GlobalRouteDecisionArtifact",
                "research_os_mainline_execution",
                GLOBAL_COMPLETION_FACT,
                "m4-v2-routing:{ROUTE}",
            ],
            "status_projection": "unified_m4_status.measurement_system_v2.global_routing",
            "evidence_progress_rule": "zero Evidence; categorical registered Decision inputs only",
            "decision_consumer": P3_PREREG_TASK,
            "downstream_consumer": GLOBAL_DOWNSTREAM_CONSUMER,
        },
    }
    return task


def _p3_preregistration_placeholder() -> dict[str, Any]:
    return {
        "task_key": P3_PREREG_TASK,
        "goal_key": GOAL_KEY,
        "task_type": "m4_p3_predictive_preregistration_freeze",
        "lane": "research",
        "priority": 90,
        "dependencies": [
            _dep("task", GLOBAL_TASK, "completed"),
            _dep("artifact", ADAPTIVE_FACT, "available"),
        ],
        "input_artifact_digests": [],
        "requested_capability": None,
        "metric_contract": {
            "phase": "M4-P3-PREDICTIVE-PREREGISTRATION-FREEZE",
            "runner": None,
            "execution_authorized": False,
            "integration_state": "INTEGRATION_PENDING",
            "completion_fact": P3_PREREG_FACT,
            "completion_fact_emission_authorized": False,
            "scientific_contract_frozen": False,
            "predictive_result_reads": 0,
            "new_historical_folds": 0,
            "evidence_created": False,
            "promotion_gate_opened": False,
            "production_action": "none",
            "mainline_integration": {
                "goal": GOAL_KEY,
                "ready_condition": "global routing completed and ADAPTIVE_RESEARCH_ELIGIBLE is available",
                "runner": None,
                "upstream_artifacts": [GLOBAL_COMPLETION_FACT, ADAPTIVE_FACT],
                "downstream_artifacts": [],
                "status_projection": "unified_m4_status.predictive_p3_preregistration_barrier",
                "evidence_rule": "always zero; inert placeholder only",
                "decision_consumer": "independent result-blind P3 Research Request",
                "next_consumer": "research-m4-p3-predictive-preregistration-freeze",
            },
        },
        "status": "draft",
        "completion_classification": "INTEGRATION_PENDING",
    }


def _predictive_p3(live_payload: Mapping[str, Any]) -> dict[str, Any]:
    task = _task(live_payload, PREDICTIVE_P3_TASK)
    task["dependencies"] = [
        _dep("task", GLOBAL_TASK, "completed"),
        _dep("artifact", ADAPTIVE_FACT, "available"),
        _dep("task", P3_PREREG_TASK, "completed"),
        _dep("artifact", P3_PREREG_FACT, "available"),
    ]
    metric = deepcopy(dict(task.get("metric_contract") or {}))
    metric.update(
        {
            "predictive_preregistration_task": P3_PREREG_TASK,
            "predictive_preregistration_fact": P3_PREREG_FACT,
            "dependency_semantics": "AND-only",
            "required_dependency_count": 4,
            "preregistration_barrier_fail_closed": True,
            "promotion_allowed": False,
        }
    )
    task["metric_contract"] = metric
    return task


def build_m4_v2_global_routing_manifest(
    live_payload: Mapping[str, Any], source_contract_digest: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_digest = require_sha256_digest(
        source_contract_digest, field_name="global_routing_source_contract_digest"
    )
    return build_additive_task_manifest(
        live_payload=live_payload,
        new_tasks=(),
        revised_tasks=(_global_task(live_payload, source_digest),),
        add_artifact_facts=(SOURCE_FACT,),
    )


build_manifest = build_m4_v2_global_routing_manifest


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON root must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the exact additive global router and P3 barrier manifest."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", type=Path, required=True)
    args = parser.parse_args()
    if {args.source.resolve(), args.input.resolve()}.intersection(
        {args.output.resolve(), args.dry_run.resolve()}
    ) or args.output.resolve() == args.dry_run.resolve():
        raise SystemExit("builder outputs must be distinct from inputs")
    source = _load(args.source)
    manifest, dry_run = build_manifest(
        _load(args.input),
        require_sha256_digest(
            source.get("artifact_digest"), field_name="source.artifact_digest"
        ),
    )
    _write(args.dry_run, dry_run)
    _write(args.output, manifest)
    print(json.dumps(dry_run, sort_keys=True))


if __name__ == "__main__":
    main()
