from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.predictive_route_reconciliation import (
    ENGINEERING_APPROVED_EVENT,
    P2R_TO_P6_POLICY_FACT,
    POLICY_RESEARCH_APPROVED_EVENT,
    PREDICTIVE_P3_PASS_TO_P4_FACT,
    PREDICTIVE_ROUTE_RECONCILIATION_CAPABILITY,
    PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_CONTRACT_PATH,
    PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY,
    ROUTE_RESEARCH_APPROVED_EVENT,
    load_predictive_route_reconciliation_source_contract,
    verify_predictive_route_reconciliation_source_bytes,
)
from dehps.research_os.models import ControlPlaneManifest, stable_json
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.research_os.structural_utility.m4_p3_evidence_compiler import (
    M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_COMPLETION_FACT,
)

CONTROL_PLANE_KEY = "m4-information-theory-mainline"
M4_GOAL_KEY = "M4_INFORMATION_THEORY_EVIDENCE"
P2_CLOSURE_TASK_KEY = "m4-p2-synthetic-measurement-validation"
P2_CLOSURE_COMPLETION_FACT = "m4-p2-closure:COMPLETE_WITH_REPAIR_OUTCOME"
GLOBAL_ROUTING_TASK_KEY = "m4-v2-global-routing"
PREDICTIVE_P3_TASK_KEY = "m4-p3-strict-historical-walk-forward"
P4_TASK_KEY = "m4-p4-negative-controls-and-robustness"
P5_TASK_KEY = "m4-p5-forward-evidence"
P6_TASK_KEY = "m4-p6-information-bound-and-decision"
ADAPTIVE_RESEARCH_ELIGIBLE_FACT = "m4-v2-routing:ADAPTIVE_RESEARCH_ELIGIBLE"
SOURCE_FACT_PREFIX = "m4-p3-predictive-route-reconciliation-source:"
P2_CLOSURE_SOURCE_FACT_PREFIX = "m4-p2-repair-outcome-closure-source:"
PRE_MIGRATION_SOURCE_MANIFEST_DIGEST = (
    "f3f263d3ef9c5028223070b7fc228c2ef95ffc315a86479d17ebccb0a87b890b"
)
_REVISED_TASK_FIELD_ALLOWLIST = frozenset({"dependencies", "metric_contract"})
_REVISED_METRIC_FIELD_ALLOWLIST = {
    PREDICTIVE_P3_TASK_KEY: frozenset(
        {
            "route_decision",
            "route_identity_repaired",
            "scientific_contract_changed",
            "ticket_budget_comparison_relationship",
            "promotion_allowed",
        }
    ),
    P4_TASK_KEY: frozenset(
        {
            "predictive_p3_pass_fact",
            "task_completion_alone_unlocks_p4",
            "p2r_blocks_research",
            "promotion_allowed",
        }
    ),
    P6_TASK_KEY: frozenset(
        {
            "p2r_to_p6_policy",
            "p2r_blocks_research_summary",
            "p2r_blocks_promotion",
            "promotion_release_fact",
            "promotion_gate_default",
            "promotion_allowed_in_this_capability",
            "prediction_v2_mode_while_p2r_pending",
            "prediction_v2_route_while_p2r_pending",
        }
    ),
}


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


def _append_once(values: list[str], value: str) -> list[str]:
    return values if value in values else [*values, value]


def _replace_prefixed_fact(
    values: list[str],
    *,
    prefix: str,
    replacement: str,
    insert_before_prefix: str | None = None,
) -> list[str]:
    output = [value for value in values if not value.startswith(prefix)]
    if insert_before_prefix is None:
        return [*output, replacement]
    index = next(
        (
            offset
            for offset, value in enumerate(output)
            if value.startswith(insert_before_prefix)
        ),
        len(output),
    )
    return [*output[:index], replacement, *output[index:]]


def _governance_task(
    *, source_digest: str, source_contract: dict[str, Any]
) -> dict[str, Any]:
    approval_digests = [
        source_contract["route_research_request"]["reviewer_approval_decision_digest"],
        source_contract["policy_research_request"]["reviewer_approval_decision_digest"],
        source_contract["engineering_request"]["reviewer_approval_decision_digest"],
    ]
    return {
        "task_key": PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY,
        "goal_key": M4_GOAL_KEY,
        "task_type": "m4_p3_predictive_route_reconciliation",
        "lane": "research",
        "priority": 103,
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
                "dependency_type": "artifact",
                "target_key": (
                    M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_COMPLETION_FACT
                ),
                "required_status": "available",
            },
            {
                "dependency_type": "artifact",
                "target_key": SOURCE_FACT_PREFIX + source_digest,
                "required_status": "available",
            },
            {
                "dependency_type": "external_event",
                "target_key": ROUTE_RESEARCH_APPROVED_EVENT,
                "required_status": "available",
            },
            {
                "dependency_type": "external_event",
                "target_key": POLICY_RESEARCH_APPROVED_EVENT,
                "required_status": "available",
            },
            {
                "dependency_type": "external_event",
                "target_key": ENGINEERING_APPROVED_EVENT,
                "required_status": "available",
            },
        ],
        "input_artifact_digests": [source_digest, *approval_digests],
        "requested_capability": PREDICTIVE_ROUTE_RECONCILIATION_CAPABILITY,
        "metric_contract": {
            "engineering_complete": True,
            "engineering_increment_percent": 0,
            "evidence_complete": False,
            "evidence_increment_percent": 0,
            "phase": "M4-P3-ROUTE-RECONCILIATION",
            "scope": "compile_result_blind_route_and_p2r_to_p6_policy_facts",
            "selected_route_decision": "DAG_REPAIR_REQUIRED",
            "selected_p2r_to_p6_policy": "RESEARCH_ALLOWED_PROMOTION_BLOCKED",
            "scientific_contract_changed": False,
            "predictive_result_reads": 0,
            "historical_database_reads": 0,
            "new_historical_folds": 0,
            "computation": 0,
            "evidence_created": False,
            "promotion_gate_opened": False,
            "production_action": "none",
            "mainline_integration": {
                "goal": M4_GOAL_KEY,
                "ready_condition": (
                    "P2 repair-outcome closure and terminal structural-P3 compiler "
                    "are complete; the source contract plus route, policy, and "
                    "Engineering approvals are available"
                ),
                "runner": "research_evidence_supervisor",
                "upstream_artifacts": [
                    "P2 COMPLETE_WITH_REPAIR_OUTCOME closure",
                    "terminal NO_STABLE_STRUCTURAL_UTILITY compiler completion",
                    "Research Request 472 / Execution 393 / Decision 1969",
                    "Research Request 473 / Execution 394 / Decision 1970",
                    "Engineering Request 474 / Execution 395 / Decision 1977",
                    "frozen route reconciliation source contract",
                ],
                "downstream_artifacts": [
                    "M4P3PredictiveRouteReconciliationArtifact",
                    "P2RToP6DependencyPolicyArtifact",
                    "PredictiveP3RouteDecisionArtifact",
                    "canonical zero-work mainline execution",
                ],
                "status_projection": (
                    "unified_m4_status.predictive_route_reconciliation"
                ),
                "evidence_progress_rule": "always_zero_governance_only",
                "decision_consumer": PREDICTIVE_P3_TASK_KEY,
                "downstream_consumer": (
                    "m4-v2-global-routing dependency wait and future predictive-P3 "
                    "PASS-only P4 gate"
                ),
            },
        },
        "status": "draft",
        "completion_classification": "INTEGRATION_PENDING",
    }


def _revised_predictive_p3(task: dict[str, Any]) -> dict[str, Any]:
    revised = copy.deepcopy(task)
    revised["dependencies"] = [
        {
            "dependency_type": "task",
            "target_key": GLOBAL_ROUTING_TASK_KEY,
            "required_status": "completed",
        },
        {
            "dependency_type": "artifact",
            "target_key": ADAPTIVE_RESEARCH_ELIGIBLE_FACT,
            "required_status": "available",
        },
    ]
    metric = copy.deepcopy(revised.get("metric_contract", {}))
    if metric.get("primary_endpoint") != "out_of_sample_log_loss_improvement":
        raise SystemExit("predictive-P3 primary endpoint changed")
    metric.update(
        {
            "route_decision": "DAG_REPAIR_REQUIRED",
            "route_identity_repaired": True,
            "scientific_contract_changed": False,
            "ticket_budget_comparison_relationship": (
                "SEPARATE_FUTURE_SECONDARY_OR_DOWNSTREAM_CONTRACT"
            ),
            "promotion_allowed": False,
        }
    )
    revised["metric_contract"] = metric
    return revised


def _revised_p4(task: dict[str, Any]) -> dict[str, Any]:
    revised = copy.deepcopy(task)
    expected_task_dependency = {
        "dependency_type": "task",
        "target_key": PREDICTIVE_P3_TASK_KEY,
        "required_status": "completed",
    }
    if expected_task_dependency not in revised.get("dependencies", []):
        raise SystemExit("P4 predictive-P3 dependency changed")
    pass_dependency = {
        "dependency_type": "artifact",
        "target_key": PREDICTIVE_P3_PASS_TO_P4_FACT,
        "required_status": "available",
    }
    if pass_dependency not in revised["dependencies"]:
        revised["dependencies"].append(pass_dependency)
    metric = copy.deepcopy(revised.get("metric_contract", {}))
    metric.update(
        {
            "predictive_p3_pass_fact": PREDICTIVE_P3_PASS_TO_P4_FACT,
            "task_completion_alone_unlocks_p4": False,
            "p2r_blocks_research": False,
            "promotion_allowed": False,
        }
    )
    revised["metric_contract"] = metric
    return revised


def _revised_p6(task: dict[str, Any]) -> dict[str, Any]:
    revised = copy.deepcopy(task)
    policy_dependency = {
        "dependency_type": "artifact",
        "target_key": P2R_TO_P6_POLICY_FACT,
        "required_status": "available",
    }
    if policy_dependency not in revised.get("dependencies", []):
        revised["dependencies"].append(policy_dependency)
    if any(
        item.get("dependency_type") == "task"
        and item.get("target_key") == "m4-p2r-measurement-repair-validation"
        for item in revised["dependencies"]
    ):
        raise SystemExit("P2R became a P6 research-summary hard dependency")
    metric = copy.deepcopy(revised.get("metric_contract", {}))
    metric.update(
        {
            "p2r_to_p6_policy": "RESEARCH_ALLOWED_PROMOTION_BLOCKED",
            "p2r_blocks_research_summary": False,
            "p2r_blocks_promotion": True,
            "promotion_release_fact": (
                "m4-p2r-measurement-repair-validation:"
                "ALL_FROZEN_ACCEPTANCE_PASS"
            ),
            "promotion_gate_default": "FAIL_CLOSED",
            "promotion_allowed_in_this_capability": False,
            "prediction_v2_mode_while_p2r_pending": "SHADOW_ONLY",
            "prediction_v2_route_while_p2r_pending": "BASELINE_ONLY",
        }
    )
    revised["metric_contract"] = metric
    return revised


def build_source_payload(
    payload: dict[str, Any], *, source_contract: dict[str, Any]
) -> dict[str, Any]:
    source_digest = str(source_contract["artifact_digest"])
    source = copy.deepcopy(payload)
    ControlPlaneManifest.from_dict(source)
    already_integrated = any(
        item.get("task_key") == PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY
        for item in source["tasks"]
    )
    if not already_integrated and source.get("manifest_digest") != (
        PRE_MIGRATION_SOURCE_MANIFEST_DIGEST
    ):
        raise SystemExit("predictive-route source-base identity changed")
    source.pop("artifact_digest", None)
    source.pop("manifest_digest", None)
    governance_task = _governance_task(
        source_digest=source_digest, source_contract=source_contract
    )
    output_tasks: list[dict[str, Any]] = []
    governance_seen = False
    for task in source["tasks"]:
        key = task.get("task_key")
        if key == PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY:
            output_tasks.append(governance_task)
            governance_seen = True
        elif key == PREDICTIVE_P3_TASK_KEY:
            output_tasks.append(_revised_predictive_p3(task))
        elif key == P4_TASK_KEY:
            output_tasks.append(_revised_p4(task))
        elif key == P6_TASK_KEY:
            output_tasks.append(_revised_p6(task))
        else:
            output_tasks.append(task)
    if not governance_seen:
        output_tasks.append(governance_task)
    source["tasks"] = output_tasks
    source_fact = SOURCE_FACT_PREFIX + source_digest
    source["facts"]["artifacts"] = _replace_prefixed_fact(
        source["facts"]["artifacts"],
        prefix=SOURCE_FACT_PREFIX,
        replacement=source_fact,
        insert_before_prefix=P2_CLOSURE_SOURCE_FACT_PREFIX,
    )
    for event in (
        ROUTE_RESEARCH_APPROVED_EVENT,
        POLICY_RESEARCH_APPROVED_EVENT,
        ENGINEERING_APPROVED_EVENT,
    ):
        source["facts"]["external_events"] = _append_once(
            source["facts"]["external_events"], event
        )
    source["manifest_digest"] = ControlPlaneManifest.from_dict(source).artifact_digest
    _validate_source_scope(source, source_contract=source_contract)
    return source


def build_live_migration(
    *,
    live_payload: dict[str, Any],
    source_payload: dict[str, Any],
    source_contract: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_frozen_live_source(
        live_payload=live_payload,
        source_contract=source_contract,
    )
    source_fact = SOURCE_FACT_PREFIX + str(source_contract["artifact_digest"])
    output, dry_run = build_additive_m4_v2_manifest(
        live_payload=live_payload,
        source_payload=source_payload,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY,),
        allowlisted_revised_task_keys=(PREDICTIVE_P3_TASK_KEY, P4_TASK_KEY, P6_TASK_KEY),
        add_artifact_facts=(source_fact,),
        add_external_events=(
            ROUTE_RESEARCH_APPROVED_EVENT,
            POLICY_RESEARCH_APPROVED_EVENT,
            ENGINEERING_APPROVED_EVENT,
        ),
    )
    if (
        dry_run["new_goal_keys"] != []
        or dry_run["new_task_keys"] != [PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY]
        or dry_run["revised_task_keys"]
        != sorted((PREDICTIVE_P3_TASK_KEY, P4_TASK_KEY, P6_TASK_KEY))
        or dry_run["existing_goal_deletions"] != 0
        or dry_run["existing_task_deletions"] != 0
        or dry_run["existing_state_regressions"] != 0
        or dry_run["existing_fact_deletions"] != 0
        or dry_run["unallowlisted_definition_rewrites"] != 0
    ):
        raise SystemExit("predictive-route additive migration scope changed")
    _validate_revised_task_scope(
        live_payload=live_payload,
        output_payload=output,
    )
    _validate_live_preservation(live_payload=live_payload, output_payload=output)
    return output, dry_run


def _validate_frozen_live_source(
    *, live_payload: dict[str, Any], source_contract: dict[str, Any]
) -> None:
    live_manifest = ControlPlaneManifest.from_dict(live_payload)
    if live_manifest.artifact_digest != str(
        source_contract["durable_manifest_digest"]
    ):
        raise SystemExit("predictive-route durable manifest identity changed")
    live_snapshot = ResearchOSControlPlane().resolve(live_manifest)
    if live_snapshot.snapshot_digest != str(
        source_contract["durable_snapshot_digest"]
    ):
        raise SystemExit("predictive-route durable snapshot identity changed")

    normalized_live = live_manifest.to_dict(include_digest=False)
    durable_p3_dependencies = _task(
        normalized_live, PREDICTIVE_P3_TASK_KEY
    ).get("dependencies")
    if stable_json(durable_p3_dependencies) != stable_json(
        source_contract["actual_dependencies"]
    ):
        raise SystemExit(
            "predictive-route durable predictive-P3 dependencies changed"
        )


def _validate_revised_task_scope(
    *, live_payload: dict[str, Any], output_payload: dict[str, Any]
) -> None:
    normalized_live = ControlPlaneManifest.from_dict(live_payload).to_dict(
        include_digest=False
    )
    normalized_output = ControlPlaneManifest.from_dict(output_payload).to_dict(
        include_digest=False
    )
    live_tasks = {item["task_key"]: item for item in normalized_live["tasks"]}
    output_tasks = {
        item["task_key"]: item for item in normalized_output["tasks"]
    }
    expected_tasks = {
        PREDICTIVE_P3_TASK_KEY: _revised_predictive_p3(
            live_tasks[PREDICTIVE_P3_TASK_KEY]
        ),
        P4_TASK_KEY: _revised_p4(live_tasks[P4_TASK_KEY]),
        P6_TASK_KEY: _revised_p6(live_tasks[P6_TASK_KEY]),
    }
    missing = object()
    for task_key, expected_task in expected_tasks.items():
        live_task = live_tasks[task_key]
        output_task = output_tasks[task_key]
        changed_fields = {
            field
            for field in live_task.keys() | output_task.keys()
            if live_task.get(field, missing) != output_task.get(field, missing)
        }
        if not changed_fields.issubset(_REVISED_TASK_FIELD_ALLOWLIST):
            raise SystemExit(
                f"predictive-route revised task field scope changed:{task_key}"
            )

        live_metric = live_task.get("metric_contract", {})
        output_metric = output_task.get("metric_contract", {})
        if not isinstance(live_metric, dict) or not isinstance(output_metric, dict):
            raise SystemExit(
                f"predictive-route revised task metric is invalid:{task_key}"
            )
        changed_metric_fields = {
            field
            for field in live_metric.keys() | output_metric.keys()
            if live_metric.get(field, missing) != output_metric.get(field, missing)
        }
        if not changed_metric_fields.issubset(
            _REVISED_METRIC_FIELD_ALLOWLIST[task_key]
        ):
            raise SystemExit(
                f"predictive-route revised metric field scope changed:{task_key}"
            )
        if stable_json(output_task) != stable_json(expected_task):
            raise SystemExit(
                f"predictive-route revised task value changed:{task_key}"
            )


def _validate_source_scope(
    source: dict[str, Any], *, source_contract: dict[str, Any]
) -> None:
    tasks = {item["task_key"]: item for item in source["tasks"]}
    if len(tasks) != len(source["tasks"]):
        raise SystemExit("task identity is not singular")
    if any("repair-outcome-strict-historical" in key for key in tasks):
        raise SystemExit("unauthorized predictive successor detected")
    p3 = tasks[PREDICTIVE_P3_TASK_KEY]
    if p3["dependencies"] != [
        {
            "dependency_type": "task",
            "target_key": GLOBAL_ROUTING_TASK_KEY,
            "required_status": "completed",
        },
        {
            "dependency_type": "artifact",
            "target_key": ADAPTIVE_RESEARCH_ELIGIBLE_FACT,
            "required_status": "available",
        },
    ]:
        raise SystemExit("predictive-P3 canonical dependencies changed")
    p2_metric = _task(source, P2_CLOSURE_TASK_KEY).get("metric_contract", {})
    if (
        p2_metric.get("decision") != "REPAIR_MEASUREMENT_SYSTEM"
        or p2_metric.get("terminal_status") != "COMPLETE_WITH_REPAIR_OUTCOME"
        or ADAPTIVE_RESEARCH_ELIGIBLE_FACT in source["facts"]["artifacts"]
        or PREDICTIVE_P3_PASS_TO_P4_FACT in source["facts"]["artifacts"]
        or P2R_TO_P6_POLICY_FACT in source["facts"]["artifacts"]
    ):
        raise SystemExit("result-blind source invariant changed")
    if source_contract["route_decision"] != "DAG_REPAIR_REQUIRED":
        raise SystemExit("route decision changed")
    if source_contract["p2r_to_p6_policy"] != (
        "RESEARCH_ALLOWED_PROMOTION_BLOCKED"
    ):
        raise SystemExit("P2R-to-P6 policy changed")


def _validate_live_preservation(
    *, live_payload: dict[str, Any], output_payload: dict[str, Any]
) -> None:
    live_tasks = {item["task_key"]: item for item in live_payload["tasks"]}
    output_tasks = {item["task_key"]: item for item in output_payload["tasks"]}
    if live_tasks[P2_CLOSURE_TASK_KEY].get("status") != "completed":
        raise SystemExit("durable P2 closure is not complete")
    if not {
        "m4-p2-measurement-decision:REPAIR_MEASUREMENT_SYSTEM",
        P2_CLOSURE_COMPLETION_FACT,
        M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_COMPLETION_FACT,
    }.issubset(live_payload["facts"]["artifacts"]):
        raise SystemExit("durable repair-outcome or structural-terminal facts changed")
    allowed = {
        PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY,
        PREDICTIVE_P3_TASK_KEY,
        P4_TASK_KEY,
        P6_TASK_KEY,
    }
    for key, task in live_tasks.items():
        if key in allowed:
            continue
        if stable_json(task) != stable_json(output_tasks[key]):
            raise SystemExit(f"unallowlisted task changed:{key}")
    if not set(live_payload["facts"]["artifacts"]).issubset(
        output_payload["facts"]["artifacts"]
    ):
        raise SystemExit("existing artifact fact deleted")
    if not set(live_payload["facts"]["external_events"]).issubset(
        output_payload["facts"]["external_events"]
    ):
        raise SystemExit("existing external event deleted")


def _update_artifact_index(
    *,
    index: dict[str, Any],
    source_digest: str,
    manifest_digest: str,
    superseded_manifest_source_commit: str | None,
) -> dict[str, Any]:
    output = copy.deepcopy(index)
    artifacts = output.get("artifacts")
    if not isinstance(artifacts, dict):
        raise SystemExit("artifact index is invalid")
    source_path = PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_CONTRACT_PATH.as_posix()
    artifacts[source_digest] = {
        "artifact_type": "m4_p3_predictive_route_reconciliation_source",
        "path": source_path,
        "identity_field": "artifact_digest",
    }
    manifest_path = "configs/research-os/m4-information-theory-evidence-v1.json"
    current = [
        key
        for key, value in artifacts.items()
        if value.get("artifact_type") == "research_os_control_plane_manifest"
        and value.get("path") == manifest_path
    ]
    if len(current) != 1:
        raise SystemExit("current control-plane manifest identity is not singular")
    prior = current[0]
    if prior != manifest_digest:
        if prior != PRE_MIGRATION_SOURCE_MANIFEST_DIGEST:
            raise SystemExit("current control-plane manifest identity changed")
        if not superseded_manifest_source_commit:
            raise SystemExit("--superseded-manifest-source-commit is required")
        entry = artifacts[prior]
        entry["artifact_type"] = "superseded_research_os_control_plane_manifest"
        entry["source_commit"] = superseded_manifest_source_commit
        entry["path_at_source"] = entry.pop("path")
        entry.pop("identity_field", None)
        entry["superseded_by_digest"] = manifest_digest
        artifacts[manifest_digest] = {
            "artifact_type": "research_os_control_plane_manifest",
            "path": manifest_path,
            "identity_field": "manifest_digest",
            "supersedes_digest": prior,
        }
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the additive zero-work M4-P3 route reconciliation."
    )
    live_source = parser.add_mutually_exclusive_group(required=True)
    live_source.add_argument("--live", type=Path)
    live_source.add_argument("--control-plane-key")
    parser.add_argument("--source-base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-kind", choices=("source", "merged"), default="source")
    parser.add_argument("--dry-run-artifact", type=Path, required=True)
    parser.add_argument("--artifact-index", type=Path, required=True)
    parser.add_argument("--artifact-index-output", type=Path, required=True)
    parser.add_argument("--superseded-manifest-source-commit")
    args = parser.parse_args()

    source_contract = load_predictive_route_reconciliation_source_contract(
        ROOT_DIR / PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_CONTRACT_PATH
    )
    verify_predictive_route_reconciliation_source_bytes(
        root_dir=ROOT_DIR, contract=source_contract
    )
    live = (
        _load(args.live)
        if args.live is not None
        else PostgresResearchOSRepository().export_manifest(
            control_plane_key=str(args.control_plane_key)
        )
    )
    source = build_source_payload(
        _load(args.source_base), source_contract=source_contract
    )
    merged, dry_run = build_live_migration(
        live_payload=live,
        source_payload=source,
        source_contract=source_contract,
    )
    index = _update_artifact_index(
        index=_load(args.artifact_index),
        source_digest=str(source_contract["artifact_digest"]),
        manifest_digest=str(source["manifest_digest"]),
        superseded_manifest_source_commit=args.superseded_manifest_source_commit,
    )
    output_payload = source if args.output_kind == "source" else merged
    atomic_write_text(
        args.output,
        json.dumps(output_payload, ensure_ascii=False, indent=2) + "\n",
    )
    atomic_write_text(
        args.dry_run_artifact,
        json.dumps(dry_run, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    atomic_write_text(
        args.artifact_index_output,
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
    )
    print(json.dumps(dry_run, sort_keys=True))


if __name__ == "__main__":
    main()
