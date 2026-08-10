from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.research_os.structural_utility.m4_p3_result_blind_design import (
    M4_P3_STRUCTURAL_UTILITY_DESIGN_APPROVED_EVENT,
    M4_P3_STRUCTURAL_UTILITY_DESIGN_CAPABILITY,
    M4_P3_STRUCTURAL_UTILITY_DESIGN_COMPLETION_FACT,
    M4_P3_STRUCTURAL_UTILITY_DESIGN_SOURCE_CONTRACT_PATH,
    M4_P3_STRUCTURAL_UTILITY_DESIGN_TASK_KEY,
    M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
    M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_APPROVED_EVENT,
    M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
    PARENT_COMPLETION_DIGEST,
    PARENT_EXECUTION_DIGEST,
    PARENT_INTAKE_HANDOFF_DIGEST,
    load_m4_p3_result_blind_structural_utility_design_source_contract,
    verify_m4_p3_result_blind_structural_utility_design_source_bytes,
)


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON root must be an object: {path}")
    return value


def _task(payload: dict, task_key: str) -> dict:
    matches = [
        item for item in payload.get("tasks", []) if item.get("task_key") == task_key
    ]
    if len(matches) != 1:
        raise SystemExit(f"task is not singular: {task_key}")
    return matches[0]


def _goal_definition() -> dict:
    return {
        "goal_key": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
        "semantic_version": "1.0.0",
        "objective_class": "structural_decision_utility",
        "status": "active",
        "success_evidence": [
            "result-blind structural-utility design",
            "frozen structural-utility preregistration",
            "blind generator and 60-to-120-fold execution",
            "structural Evidence Compiler bundle",
            "structural route decision",
        ],
        "owner_lane": "research",
        "question": (
            "Does a frozen candidate-portfolio construction produce stable, "
            "transparent structural utility at the same 100-ticket budget, "
            "independent of any target result?"
        ),
        "baseline_metric_manifest": {
            "legal_universe": "C(33,6)",
            "portfolio_budget": 100,
            "primary_null": "uniform_random_without_replacement",
            "secondary_comparator": "legacy_structural_top100",
            "prediction_evidence": "INCONCLUSIVE",
        },
        "target_metric_manifest": {
            "fold_count_range": [60, 120],
            "candidate_arm": "prediction_v2_structural_selection_100",
            "confirmatory_coordinate_count": 6,
            "allowed_decisions": [
                "STRUCTURAL_UTILITY_SUPPORTED_WITHIN_FROZEN_SCOPE",
                "NO_STABLE_STRUCTURAL_UTILITY",
                "INCONCLUSIVE_STRUCTURAL_UTILITY",
                "INVALID_RESULT_BLIND_EXECUTION",
            ],
            "prediction_promotion": "closed",
        },
        "guardrails": [
            "strict_result_blind_interfaces",
            "same_legal_universe_and_budget_for_every_arm",
            "preregister_before_portfolio_generation",
            "no_scalar_utility_score_without_prior_freeze",
            "previous_structural_result_cannot_tune_choices",
            "old_three_line_training_frozen",
            "prediction_v2_shadow_only_baseline_only",
            "predictive_m4_p3_not_authorized",
            "promotion_gate_closed",
            "production_action_none",
            "capability_complete_requires_mainline_execution_and_replay",
        ],
    }


def _revised_design_task(live_task: dict, source_digest: str) -> dict:
    task = copy.deepcopy(live_task)
    task.update(
        {
            "goal_key": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
            "goal_digest": "",
            "task_type": "m4_p3_result_blind_structural_utility_design",
            "requested_capability": M4_P3_STRUCTURAL_UTILITY_DESIGN_CAPABILITY,
            "input_artifact_digests": [
                source_digest,
                PARENT_EXECUTION_DIGEST,
                PARENT_INTAKE_HANDOFF_DIGEST,
                PARENT_COMPLETION_DIGEST,
            ],
            "dependencies": [
                dependency
                for dependency in task.get("dependencies", [])
                if dependency.get("dependency_type") != "task"
            ],
            "metric_contract": {
                "engineering_complete": True,
                "engineering_increment_percent": 0,
                "evidence_complete": False,
                "evidence_increment_percent": 0,
                "phase": "M4-P3-RESULT-BLIND-STRUCTURAL-UTILITY-DESIGN",
                "scope": "compile_estimands_and_interfaces_without_executing_portfolios_or_folds",
                "mainline_integration": {
                    "goal": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
                    "ready_condition": (
                        "the parent result-decision is VALIDATED_IN_MAINLINE, "
                        "the exact intake-handoff registration exists, and "
                        "Research Request 443 is approved"
                    ),
                    "runner": "research_evidence_supervisor",
                    "upstream_artifacts": [
                        "result-decision completed-event metadata",
                        "result-decision mainline execution registration identity",
                        "structural-utility intake-handoff registration identity",
                        "result-decision completion registration identity",
                        "approved M4-P3 result-blind Research Request",
                    ],
                    "downstream_artifacts": [
                        "M4-P3 structural-utility design contract",
                        "M4-P3 preregistration handoff",
                        "M4-P3 design completion",
                        "M4-P3 design mainline execution",
                    ],
                    "status_projection": (
                        "unified_m4_status.structural_utility.m4_p3_result_blind_design"
                    ),
                    "evidence_progress_rule": (
                        "design_execution_creates_no_prediction_or_structural_result_evidence"
                    ),
                    "decision_consumer": (
                        M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY
                    ),
                    "downstream_consumer": (
                        M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY
                    ),
                },
                "result_blind": True,
                "parent_payloads_read": 0,
                "portfolio_budget": 100,
                "fold_count_range": [60, 120],
                "portfolios_generated": 0,
                "folds_executed": 0,
                "metric_results_read": 0,
                "historical_prediction_evidence": "INCONCLUSIVE",
                "prediction_v2_mode": "SHADOW_ONLY",
                "prediction_v2_route": "BASELINE_ONLY",
                "old_training_lines": "FROZEN",
                "promotion_gate_opened": False,
                "predictive_p3_authorized": False,
                "production_action": "none",
            },
        }
    )
    return task


def _preregistration_task() -> dict:
    return {
        "task_key": M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
        "goal_key": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
        "goal_digest": "",
        "task_type": "m4_p3_result_blind_structural_utility_preregistration",
        "lane": "research",
        "priority": 75,
        "dependencies": [
            {
                "dependency_type": "task",
                "target_key": M4_P3_STRUCTURAL_UTILITY_DESIGN_TASK_KEY,
                "required_status": "completed",
            },
            {
                "dependency_type": "artifact",
                "target_key": M4_P3_STRUCTURAL_UTILITY_DESIGN_COMPLETION_FACT,
                "required_status": "available",
            },
            {
                "dependency_type": "external_event",
                "target_key": M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_APPROVED_EVENT,
                "required_status": "available",
            },
        ],
        "input_artifact_digests": [],
        "requested_capability": None,
        "metric_contract": {
            "engineering_complete": False,
            "engineering_increment_percent": 0,
            "evidence_complete": False,
            "evidence_increment_percent": 0,
            "phase": "M4-P3-RESULT-BLIND-STRUCTURAL-UTILITY-PREREGISTRATION",
            "scope": (
                "freeze_folds_arm_sources_seeds_family_partition_statistics_"
                "thresholds_and_failure_rules_before_generation"
            ),
            "mainline_integration": {
                "goal": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
                "ready_condition": (
                    "the design is VALIDATED_IN_MAINLINE and replay verified "
                    "and a separate preregistration Research Request is approved"
                ),
                "runner": "pending_separately_approved_preregistration_capability",
                "upstream_artifacts": [
                    "M4-P3 design mainline execution",
                    "M4-P3 structural-utility design contract",
                    "M4-P3 preregistration handoff",
                    "M4-P3 design completion",
                ],
                "downstream_artifacts": [
                    "frozen M4-P3 preregistration",
                    "blind-generator execution handoff",
                    "M4-P3 preregistration completion",
                ],
                "status_projection": (
                    "unified_m4_status.structural_utility."
                    "m4_p3_result_blind_preregistration"
                ),
                "evidence_progress_rule": (
                    "preregistration_creates_no_prediction_or_structural_result_evidence"
                ),
                "decision_consumer": "future blind-generator execution",
                "downstream_consumer": "future blind-generator execution",
            },
            "required_external_event": (
                M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_APPROVED_EVENT
            ),
            "exact_fold_count_pending_within": [60, 120],
            "portfolio_budget": 100,
            "result_blind": True,
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "old_training_lines": "FROZEN",
            "promotion_gate_opened": False,
            "predictive_p3_authorized": False,
            "production_action": "none",
        },
        "status": "draft",
        "completion_classification": "INTEGRATION_PENDING",
    }


def _source_payload(source_base: dict, source_digest: str) -> dict:
    source = copy.deepcopy(source_base)
    source.pop("artifact_digest", None)
    source.pop("manifest_digest", None)
    if any(
        goal.get("goal_key") == M4_P3_STRUCTURAL_UTILITY_GOAL_KEY
        for goal in source.get("goals", [])
    ):
        raise SystemExit("M4-P3 structural-utility Goal already exists")
    source["goals"].append(_goal_definition())
    current = _task(source, M4_P3_STRUCTURAL_UTILITY_DESIGN_TASK_KEY)
    replacement = _revised_design_task(current, source_digest)
    source["tasks"] = [
        replacement
        if item.get("task_key") == M4_P3_STRUCTURAL_UTILITY_DESIGN_TASK_KEY
        else item
        for item in source["tasks"]
    ]
    source["tasks"].append(_preregistration_task())
    source_fact = (
        "m4-p3-result-blind-structural-utility-design-source:" + source_digest
    )
    if source_fact not in source["facts"]["artifacts"]:
        source["facts"]["artifacts"].append(source_fact)
    if (
        M4_P3_STRUCTURAL_UTILITY_DESIGN_APPROVED_EVENT
        not in source["facts"]["external_events"]
    ):
        source["facts"]["external_events"].append(
            M4_P3_STRUCTURAL_UTILITY_DESIGN_APPROVED_EVENT
        )
    source["manifest_digest"] = ControlPlaneManifest.from_dict(
        source
    ).artifact_digest
    return source


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the additive M4-P3 structural-utility design migration."
    )
    live_source = parser.add_mutually_exclusive_group(required=True)
    live_source.add_argument("--live", type=Path)
    live_source.add_argument("--control-plane-key")
    parser.add_argument("--source-base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run-artifact", type=Path, required=True)
    parser.add_argument("--artifact-index", type=Path, required=True)
    parser.add_argument("--artifact-index-output", type=Path, required=True)
    parser.add_argument("--superseded-manifest-source-commit", required=True)
    args = parser.parse_args()
    outputs = {
        args.output.resolve(),
        args.dry_run_artifact.resolve(),
        args.artifact_index_output.resolve(),
    }
    if len(outputs) != 3:
        raise SystemExit("migration outputs must be distinct")
    live = (
        _load(args.live)
        if args.live is not None
        else PostgresResearchOSRepository().export_manifest(
            control_plane_key=str(args.control_plane_key)
        )
    )
    source_base = _load(args.source_base)
    current = _task(live, M4_P3_STRUCTURAL_UTILITY_DESIGN_TASK_KEY)
    if (
        current.get("requested_capability") is not None
        or current.get("input_artifact_digests")
        or current.get("status") != "draft"
        or current.get("completion_classification") != "INTEGRATION_PENDING"
        or any(
            item.get("task_key") == M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY
            for item in live.get("tasks", [])
        )
    ):
        raise SystemExit("M4-P3 intake is not the exact unstarted migration target")
    source_contract = load_m4_p3_result_blind_structural_utility_design_source_contract(
        ROOT_DIR / M4_P3_STRUCTURAL_UTILITY_DESIGN_SOURCE_CONTRACT_PATH
    )
    verify_m4_p3_result_blind_structural_utility_design_source_bytes(
        root_dir=ROOT_DIR,
        contract=source_contract,
    )
    source = _source_payload(
        source_base, str(source_contract["artifact_digest"])
    )
    source_fact = f"m4-p3-result-blind-structural-utility-design-source:{source_contract['artifact_digest']}"
    _, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,),
        allowlisted_new_task_keys=(M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,),
        allowlisted_revised_task_keys=(M4_P3_STRUCTURAL_UTILITY_DESIGN_TASK_KEY,),
        add_artifact_facts=(source_fact,),
        add_external_events=(M4_P3_STRUCTURAL_UTILITY_DESIGN_APPROVED_EVENT,),
    )
    if (
        dry_run["new_goal_keys"] != [M4_P3_STRUCTURAL_UTILITY_GOAL_KEY]
        or dry_run["new_task_keys"]
        != [M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY]
        or dry_run["revised_task_keys"] != [M4_P3_STRUCTURAL_UTILITY_DESIGN_TASK_KEY]
        or dry_run["existing_state_regressions"] != 0
        or dry_run["existing_fact_deletions"] != 0
        or dry_run["unallowlisted_definition_rewrites"] != 0
    ):
        raise SystemExit("M4-P3 structural-utility migration scope changed")
    index = _load(args.artifact_index)
    artifacts = index.get("artifacts")
    if not isinstance(artifacts, dict):
        raise SystemExit("artifact index is invalid")
    digest = str(source_contract["artifact_digest"])
    stale_candidate_keys = [
        key
        for key, value in artifacts.items()
        if value.get("artifact_type")
        == "m4_p3_result_blind_structural_utility_design_source"
        and value.get("path")
        == M4_P3_STRUCTURAL_UTILITY_DESIGN_SOURCE_CONTRACT_PATH.as_posix()
        and key != digest
    ]
    for key in stale_candidate_keys:
        artifacts.pop(key)
    expected_index_entry = {
        "artifact_type": "m4_p3_result_blind_structural_utility_design_source",
        "path": M4_P3_STRUCTURAL_UTILITY_DESIGN_SOURCE_CONTRACT_PATH.as_posix(),
        "identity_field": "artifact_digest",
    }
    if digest in artifacts and artifacts[digest] != expected_index_entry:
        raise SystemExit("M4-P3 source contract index identity changed")
    artifacts[digest] = expected_index_entry
    manifest_digest = str(source["manifest_digest"])
    manifest_path = "configs/research-os/m4-information-theory-evidence-v1.json"
    current_manifest_keys = [
        key
        for key, value in artifacts.items()
        if value.get("artifact_type") == "research_os_control_plane_manifest"
        and value.get("path") == manifest_path
    ]
    if len(current_manifest_keys) != 1:
        raise SystemExit("current control-plane manifest index identity is not singular")
    prior_manifest_digest = current_manifest_keys[0]
    if prior_manifest_digest == manifest_digest:
        raise SystemExit("M4-P3 migration did not change the manifest identity")
    prior_entry = artifacts[prior_manifest_digest]
    prior_entry["artifact_type"] = "superseded_research_os_control_plane_manifest"
    prior_entry["source_commit"] = args.superseded_manifest_source_commit
    prior_entry["path_at_source"] = prior_entry.pop("path")
    prior_entry["superseded_by_digest"] = manifest_digest
    artifacts[manifest_digest] = {
        "artifact_type": "research_os_control_plane_manifest",
        "path": manifest_path,
        "identity_field": "manifest_digest",
        "supersedes_digest": prior_manifest_digest,
    }
    atomic_write_text(
        args.output,
        json.dumps(source, ensure_ascii=False, indent=2) + "\n",
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
