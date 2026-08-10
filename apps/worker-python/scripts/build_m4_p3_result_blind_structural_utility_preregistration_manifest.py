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
    M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
    M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_APPROVED_EVENT,
)
from dehps.research_os.structural_utility.m4_p3_result_blind_preregistration import (
    M4_P3_STRUCTURAL_UTILITY_EXECUTION_APPROVED_EVENT,
    M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
    M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_CAPABILITY,
    M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_COMPLETION_FACT,
    M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_SOURCE_CONTRACT_PATH,
    M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
    PARENT_COMPLETION_DIGEST,
    PARENT_DESIGN_DIGEST,
    PARENT_EXECUTION_DIGEST,
    PARENT_HANDOFF_DIGEST,
    RESEARCH_PREREGISTRATION_DIGEST,
    load_m4_p3_result_blind_structural_utility_preregistration_source_contract,
    verify_m4_p3_result_blind_structural_utility_preregistration_source_bytes,
)

PRE_MIGRATION_SOURCE_MANIFEST_DIGEST = (
    "6bfb2795468b0a9fbe5ef86c005903ce243fee0900a7ab2f72410eccf0330d3e"
)
MIGRATED_SOURCE_MANIFEST_DIGEST = (
    "6dff4a5326d7b7308cdca7be88c2307d7902c2366431d0a86a04c5ea3d6d1c95"
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


def _revised_preregistration_task(live_task: dict, source_digest: str) -> dict:
    task = copy.deepcopy(live_task)
    task.update(
        {
            "requested_capability": M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_CAPABILITY,
            "input_artifact_digests": [
                source_digest,
                RESEARCH_PREREGISTRATION_DIGEST,
                PARENT_EXECUTION_DIGEST,
                PARENT_DESIGN_DIGEST,
                PARENT_HANDOFF_DIGEST,
                PARENT_COMPLETION_DIGEST,
            ],
            "metric_contract": {
                "engineering_complete": True,
                "engineering_increment_percent": 0,
                "evidence_complete": False,
                "evidence_increment_percent": 0,
                "phase": "M4-P3-RESULT-BLIND-STRUCTURAL-UTILITY-PREREGISTRATION",
                "scope": (
                    "compile_the_frozen_research_contract_without_generating_"
                    "portfolios_or_executing_folds"
                ),
                "mainline_integration": {
                    "goal": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
                    "ready_condition": (
                        "the design completion is registered, Research Request 449 "
                        "and Execution 370 are completed, and the preregistration "
                        "approval event is available"
                    ),
                    "runner": "research_evidence_supervisor",
                    "upstream_artifacts": [
                        "M4-P3 design mainline execution",
                        "M4-P3 structural-utility design contract",
                        "M4-P3 preregistration handoff",
                        "M4-P3 design completion",
                        "Research Request 449 frozen preregistration",
                    ],
                    "downstream_artifacts": [
                        "frozen M4-P3 preregistration",
                        "blind-generator execution handoff",
                        "M4-P3 preregistration completion",
                        "M4-P3 preregistration mainline execution",
                    ],
                    "status_projection": (
                        "unified_m4_status.structural_utility."
                        "m4_p3_result_blind_preregistration"
                    ),
                    "evidence_progress_rule": (
                        "preregistration_execution_creates_no_prediction_or_"
                        "structural_result_evidence"
                    ),
                    "decision_consumer": M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
                    "downstream_consumer": M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
                },
                "research_request_id": 449,
                "research_execution_id": 370,
                "fold_count": 90,
                "portfolio_budget": 100,
                "arm_count": 3,
                "confirmatory_coordinate_count": 6,
                "result_blind": True,
                "portfolios_generated": 0,
                "folds_executed": 0,
                "target_draw_rows_read": 0,
                "metric_results_read": 0,
                "previous_structural_result_values_used_to_select_any_choice": 0,
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


def _execution_task() -> dict:
    return {
        "task_key": M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
        "goal_key": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
        "goal_digest": "",
        "task_type": (
            "m4_p3_result_blind_structural_utility_blind_generator_and_walk_forward"
        ),
        "lane": "research",
        "priority": 74,
        "dependencies": [
            {
                "dependency_type": "task",
                "target_key": M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
                "required_status": "completed",
            },
            {
                "dependency_type": "artifact",
                "target_key": M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_COMPLETION_FACT,
                "required_status": "available",
            },
            {
                "dependency_type": "external_event",
                "target_key": M4_P3_STRUCTURAL_UTILITY_EXECUTION_APPROVED_EVENT,
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
            "phase": "M4-P3-RESULT-BLIND-STRUCTURAL-UTILITY-EXECUTION",
            "scope": "future_separately_authorized_blind_generator_and_90_fold_execution",
            "mainline_integration": {
                "goal": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
                "ready_condition": (
                    "the preregistration is VALIDATED_IN_MAINLINE and replay "
                    "verified and a separate execution Research Request is approved"
                ),
                "runner": "pending_separately_approved_blind_execution_capability",
                "upstream_artifacts": [
                    "frozen M4-P3 preregistration",
                    "blind-generator execution handoff",
                    "M4-P3 preregistration completion",
                ],
                "downstream_artifacts": [
                    "90 immutable fold artifacts",
                    "structural metric result index",
                    "execution completion",
                ],
                "status_projection": (
                    "unified_m4_status.structural_utility.m4_p3_result_blind_execution"
                ),
                "evidence_progress_rule": (
                    "no_evidence_until_all_90_folds_validate_and_replay"
                ),
                "decision_consumer": "future structural Evidence Compiler",
                "downstream_consumer": "future structural Evidence Compiler",
            },
            "fold_count": 90,
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
    ControlPlaneManifest.from_dict(source)
    preregistration = _task(source, M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY)
    already_migrated = (
        preregistration.get("requested_capability")
        == M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_CAPABILITY
    )
    if already_migrated:
        if (
            len(
                [
                    item
                    for item in source.get("tasks", [])
                    if item.get("task_key")
                    == M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY
                ]
            )
            != 1
        ):
            raise SystemExit("migrated M4-P3 preregistration source shape changed")
        if preregistration.get("input_artifact_digests", [None])[0] != source_digest:
            source.pop("artifact_digest", None)
            source.pop("manifest_digest", None)
            source["tasks"] = [
                _revised_preregistration_task(item, source_digest)
                if item.get("task_key")
                == M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY
                else item
                for item in source["tasks"]
            ]
            source["facts"]["artifacts"] = [
                item
                for item in source["facts"]["artifacts"]
                if not item.startswith(
                    "m4-p3-result-blind-structural-utility-preregistration-source:"
                )
            ]
            source["facts"]["artifacts"].append(
                "m4-p3-result-blind-structural-utility-preregistration-source:"
                + source_digest
            )
            source["manifest_digest"] = ControlPlaneManifest.from_dict(
                source
            ).artifact_digest
        return source
    if source.get("manifest_digest") != PRE_MIGRATION_SOURCE_MANIFEST_DIGEST:
        raise SystemExit("M4-P3 preregistration source-base identity changed")
    if preregistration.get("requested_capability") is not None:
        raise SystemExit("M4-P3 preregistration source is not unimplemented")
    source.pop("artifact_digest", None)
    source.pop("manifest_digest", None)
    source["tasks"] = [
        _revised_preregistration_task(item, source_digest)
        if item.get("task_key") == M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY
        else item
        for item in source["tasks"]
    ]
    source["tasks"].append(_execution_task())
    source_fact = (
        "m4-p3-result-blind-structural-utility-preregistration-source:" + source_digest
    )
    if source_fact not in source["facts"]["artifacts"]:
        source["facts"]["artifacts"].append(source_fact)
    if (
        M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_APPROVED_EVENT
        not in source["facts"]["external_events"]
    ):
        source["facts"]["external_events"].append(
            M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_APPROVED_EVENT
        )
    source["manifest_digest"] = ControlPlaneManifest.from_dict(source).artifact_digest
    return source


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the additive M4-P3 structural-utility preregistration migration."
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
    current = _task(live, M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY)
    if (
        current.get("requested_capability") is not None
        or current.get("input_artifact_digests")
        or current.get("status") != "draft"
        or current.get("completion_classification") != "INTEGRATION_PENDING"
        or any(
            item.get("task_key") == M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY
            for item in live.get("tasks", [])
        )
    ):
        raise SystemExit("M4-P3 preregistration is not the exact unstarted target")
    source_contract = (
        load_m4_p3_result_blind_structural_utility_preregistration_source_contract(
            ROOT_DIR / M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_SOURCE_CONTRACT_PATH
        )
    )
    verify_m4_p3_result_blind_structural_utility_preregistration_source_bytes(
        root_dir=ROOT_DIR, contract=source_contract
    )
    source = _source_payload(source_base, str(source_contract["artifact_digest"]))
    source_fact = "m4-p3-result-blind-structural-utility-preregistration-source:" + str(
        source_contract["artifact_digest"]
    )
    merged, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,),
        allowlisted_revised_task_keys=(
            M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_APPROVED_EVENT,),
    )
    if (
        dry_run["new_goal_keys"] != []
        or dry_run["new_task_keys"] != [M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY]
        or dry_run["revised_task_keys"]
        != [M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY]
        or dry_run["existing_state_regressions"] != 0
        or dry_run["existing_fact_deletions"] != 0
        or dry_run["unallowlisted_definition_rewrites"] != 0
    ):
        raise SystemExit("M4-P3 preregistration migration scope changed")
    index = _load(args.artifact_index)
    artifacts = index.get("artifacts")
    if not isinstance(artifacts, dict):
        raise SystemExit("artifact index is invalid")
    digest = str(source_contract["artifact_digest"])
    stale_source_keys = [
        key
        for key, value in artifacts.items()
        if value.get("artifact_type")
        == "m4_p3_result_blind_structural_utility_preregistration_source"
        and value.get("path")
        == M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_SOURCE_CONTRACT_PATH.as_posix()
        and key != digest
    ]
    for key in stale_source_keys:
        artifacts.pop(key)
    expected_source_entry = {
        "artifact_type": (
            "m4_p3_result_blind_structural_utility_preregistration_source"
        ),
        "path": M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_SOURCE_CONTRACT_PATH.as_posix(),
        "identity_field": "artifact_digest",
    }
    if digest in artifacts and artifacts[digest] != expected_source_entry:
        raise SystemExit("M4-P3 preregistration source index identity changed")
    artifacts[digest] = expected_source_entry
    manifest_digest = str(source["manifest_digest"])
    manifest_path = "configs/research-os/m4-information-theory-evidence-v1.json"
    current_manifest_keys = [
        key
        for key, value in artifacts.items()
        if value.get("artifact_type") == "research_os_control_plane_manifest"
        and value.get("path") == manifest_path
    ]
    if len(current_manifest_keys) != 1:
        raise SystemExit(
            "current control-plane manifest index identity is not singular"
        )
    prior_manifest_digest = current_manifest_keys[0]
    expected_manifest_entry = {
        "artifact_type": "research_os_control_plane_manifest",
        "path": manifest_path,
        "identity_field": "manifest_digest",
    }
    if prior_manifest_digest != manifest_digest:
        if not args.superseded_manifest_source_commit:
            raise SystemExit(
                "--superseded-manifest-source-commit is required for source migration"
            )
        prior_entry = artifacts[prior_manifest_digest]
        prior_entry["artifact_type"] = "superseded_research_os_control_plane_manifest"
        prior_entry["source_commit"] = args.superseded_manifest_source_commit
        prior_entry["path_at_source"] = prior_entry.pop("path")
        prior_entry["superseded_by_digest"] = manifest_digest
        artifacts[manifest_digest] = {
            **expected_manifest_entry,
            "supersedes_digest": prior_manifest_digest,
        }
    elif artifacts[manifest_digest].get("path") != manifest_path:
        raise SystemExit("current control-plane manifest index entry changed")
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
