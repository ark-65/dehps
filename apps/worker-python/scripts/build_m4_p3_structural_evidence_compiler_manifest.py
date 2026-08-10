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
from dehps.research_os.structural_utility.m4_p3_evidence_compiler import (
    M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_APPROVED_EVENT,
    M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_CAPABILITY,
    M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_SOURCE_CONTRACT_PATH,
    PARENT_EXECUTION_COMPLETION_DIGEST,
    PARENT_EXECUTION_DIGEST,
    PARENT_RESULT_INDEX_DIGEST,
    RESEARCH_EXECUTION_CONTRACT_DIGEST,
    load_m4_p3_structural_evidence_compiler_source_contract,
    verify_m4_p3_structural_evidence_compiler_source_bytes,
)
from dehps.research_os.structural_utility.m4_p3_result_blind_execution import (
    M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY,
    PARENT_PREREGISTRATION_DIGEST,
)

PRE_MIGRATION_SOURCE_MANIFEST_DIGEST = (
    "86847be6f03486b7420e3daa24f286d20d7e872c4901260f6eb3f502b0df0ffe"
)


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON root must be an object: {path}")
    return value


def _task(payload: dict) -> dict:
    matches = [
        item
        for item in payload.get("tasks", [])
        if item.get("task_key")
        == M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY
    ]
    if len(matches) != 1:
        raise SystemExit("M4-P3 Evidence Compiler task is not singular")
    return matches[0]


def _revised_task(live_task: dict, source_digest: str) -> dict:
    task = copy.deepcopy(live_task)
    task.update(
        {
            "requested_capability": (
                M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_CAPABILITY
            ),
            "input_artifact_digests": [
                source_digest,
                RESEARCH_EXECUTION_CONTRACT_DIGEST,
                PARENT_EXECUTION_DIGEST,
                PARENT_RESULT_INDEX_DIGEST,
                PARENT_EXECUTION_COMPLETION_DIGEST,
                PARENT_PREREGISTRATION_DIGEST,
            ],
            "metric_contract": {
                "engineering_complete": True,
                "engineering_increment_percent": 0,
                "evidence_complete": False,
                "evidence_increment_percent": 0,
                "phase": (
                    "M4-P3-RESULT-BLIND-STRUCTURAL-UTILITY-EVIDENCE-COMPILER"
                ),
                "scope": (
                    "compile_the_frozen_joint_block_bootstrap_holm_family_and_"
                    "all_gate_structural_route_decision"
                ),
                "mainline_integration": {
                    "goal": "M4_P3_RESULT_BLIND_STRUCTURAL_UTILITY",
                    "ready_condition": (
                        "blind execution is VALIDATED_IN_MAINLINE and replay "
                        "verified, Research Request 462 / Execution 383 is "
                        "completed, and the Evidence Compiler approval event is "
                        "available"
                    ),
                    "runner": "research_evidence_supervisor",
                    "upstream_artifacts": [
                        "frozen Evidence Compiler Research contract",
                        "blind-execution mainline execution",
                        "90-fold structural metric result index",
                        "blind-execution completion",
                        "frozen M4-P3 preregistration",
                    ],
                    "downstream_artifacts": [
                        "joint moving-block bootstrap family",
                        "Holm-adjusted 12-hypothesis structural Evidence",
                        "all-gate structural route decision",
                        "Evidence Compiler completion",
                        "canonical mainline execution",
                    ],
                    "status_projection": (
                        "unified_m4_status.structural_utility."
                        "m4_p3_structural_evidence_compiler"
                    ),
                    "evidence_progress_rule": (
                        "evidence_and_route_only_after_all_12_frozen_gates_compile"
                    ),
                    "decision_consumer": "terminal structural route record",
                    "downstream_consumer": "terminal structural route record",
                },
                "research_request_id": 462,
                "research_execution_id": 383,
                "fold_count": 90,
                "bootstrap_resamples": 20000,
                "block_length": 5,
                "holm_family_size": 12,
                "registered_capability_artifact_count": 4,
                "result_blind": True,
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


def _source_payload(source_base: dict, source_digest: str) -> dict:
    source = copy.deepcopy(source_base)
    ControlPlaneManifest.from_dict(source)
    live_task = _task(source)
    already_migrated = (
        live_task.get("requested_capability")
        == M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_CAPABILITY
    )
    if not already_migrated and source.get("manifest_digest") != (
        PRE_MIGRATION_SOURCE_MANIFEST_DIGEST
    ):
        raise SystemExit("M4-P3 Evidence Compiler source-base identity changed")
    if not already_migrated and live_task.get("requested_capability") is not None:
        raise SystemExit("M4-P3 Evidence Compiler source is not unimplemented")
    if already_migrated and live_task.get("input_artifact_digests", [None])[0] == (
        source_digest
    ):
        return source
    source.pop("artifact_digest", None)
    source.pop("manifest_digest", None)
    source["tasks"] = [
        _revised_task(item, source_digest)
        if item.get("task_key")
        == M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY
        else item
        for item in source["tasks"]
    ]
    prefix = "m4-p3-result-blind-structural-utility-evidence-compiler-source:"
    source["facts"]["artifacts"] = [
        item for item in source["facts"]["artifacts"] if not item.startswith(prefix)
    ]
    source["facts"]["artifacts"].append(prefix + source_digest)
    if (
        M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_APPROVED_EVENT
        not in source["facts"]["external_events"]
    ):
        source["facts"]["external_events"].append(
            M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_APPROVED_EVENT
        )
    source["manifest_digest"] = ControlPlaneManifest.from_dict(
        source
    ).artifact_digest
    return source


def _update_artifact_index(
    *,
    index: dict,
    source_digest: str,
    manifest_digest: str,
    superseded_manifest_source_commit: str | None,
) -> dict:
    artifacts = index.get("artifacts")
    if not isinstance(artifacts, dict):
        raise SystemExit("artifact index is invalid")
    source_path = (
        M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_SOURCE_CONTRACT_PATH.as_posix()
    )
    for key in [
        key
        for key, value in artifacts.items()
        if value.get("artifact_type")
        == "m4_p3_result_blind_structural_utility_evidence_compiler_source"
        and value.get("path") == source_path
        and key != source_digest
    ]:
        artifacts.pop(key)
    artifacts[source_digest] = {
        "artifact_type": (
            "m4_p3_result_blind_structural_utility_evidence_compiler_source"
        ),
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
        if not superseded_manifest_source_commit:
            raise SystemExit("--superseded-manifest-source-commit is required")
        entry = artifacts[prior]
        entry["artifact_type"] = "superseded_research_os_control_plane_manifest"
        entry["source_commit"] = superseded_manifest_source_commit
        entry["path_at_source"] = entry.pop("path")
        entry["superseded_by_digest"] = manifest_digest
        artifacts[manifest_digest] = {
            "artifact_type": "research_os_control_plane_manifest",
            "path": manifest_path,
            "identity_field": "manifest_digest",
            "supersedes_digest": prior,
        }
    return index


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the additive M4-P3 Evidence Compiler migration."
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
    live = (
        _load(args.live)
        if args.live is not None
        else PostgresResearchOSRepository().export_manifest(
            control_plane_key=str(args.control_plane_key)
        )
    )
    source_base = _load(args.source_base)
    source_contract = load_m4_p3_structural_evidence_compiler_source_contract(
        ROOT_DIR / M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_SOURCE_CONTRACT_PATH
    )
    verify_m4_p3_structural_evidence_compiler_source_bytes(
        root_dir=ROOT_DIR,
        contract=source_contract,
    )
    source_digest = str(source_contract["artifact_digest"])
    source = _source_payload(source_base, source_digest)
    source_fact = (
        "m4-p3-result-blind-structural-utility-evidence-compiler-source:"
        + source_digest
    )
    new_external_events = (
        ()
        if M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_APPROVED_EVENT
        in live.get("facts", {}).get("external_events", [])
        else (M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_APPROVED_EVENT,)
    )
    merged, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(),
        allowlisted_revised_task_keys=(
            M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=new_external_events,
    )
    if (
        dry_run["new_goal_keys"] != []
        or dry_run["new_task_keys"] != []
        or dry_run["revised_task_keys"]
        != [M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY]
        or dry_run["existing_state_regressions"] != 0
        or dry_run["existing_fact_deletions"] != 0
        or dry_run["unallowlisted_definition_rewrites"] != 0
    ):
        raise SystemExit("M4-P3 Evidence Compiler migration scope changed")
    index = _update_artifact_index(
        index=_load(args.artifact_index),
        source_digest=source_digest,
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
