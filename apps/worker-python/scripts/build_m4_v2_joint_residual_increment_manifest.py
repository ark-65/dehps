from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_task_manifest,
    require_sha256_digest,
)
from dehps.research_os.models import (
    M4_V2_ESTIMAND_DIGESTS,
    M4_V2_MEASUREMENT_CONTRACT_DIGEST,
    M4_V2_MEASUREMENT_CONTRACT_KEY,
)

GOAL_KEY = "M4_INFORMATION_THEORY_EVIDENCE"
CONTRACT_KEY = M4_V2_MEASUREMENT_CONTRACT_KEY
CONTRACT_DIGEST = M4_V2_MEASUREMENT_CONTRACT_DIGEST
BRANCH_ID = "JOINT_RESIDUAL_INCREMENT"
ESTIMAND_DIGEST = M4_V2_ESTIMAND_DIGESTS[BRANCH_ID]
SOURCE_FACT = (
    "m4-v2-joint-residual-increment-contract:M4_MEASUREMENT_CONTRACT_V2:FROZEN"
)
MARGINAL_REPLAY_FACT = "m4-v2-historical-branch-decision-replay:M4_MEASUREMENT_CONTRACT_V2:MARGINAL_STATIC:VERIFIED"
TEMPORAL_REPLAY_FACT = "m4-v2-historical-branch-decision-replay:M4_MEASUREMENT_CONTRACT_V2:TEMPORAL_MARGINAL_INCREMENT:VERIFIED"
DESIGN_TASK = "m4-v2-joint-residual-increment-historical-measurement-design"
DESIGN_FACT = f"{DESIGN_TASK}:FROZEN"
PREREG_TASK = "m4-v2-joint-residual-increment-historical-measurement-preregistration"
PREREG_FACT = f"{PREREG_TASK}:FROZEN"
PRODUCER_TASK = "m4-v2-joint-residual-increment-historical-measurement-gate-compiler"
PRODUCER_FACT = f"{PRODUCER_TASK}:COMPLETE"
REPLAY_TASK = "m4-v2-joint-residual-increment-historical-branch-decision-replay"
TERMINAL_FACT = "m4-v2-historical-branch-decision:M4_MEASUREMENT_CONTRACT_V2:JOINT_RESIDUAL_INCREMENT:TERMINAL"
REPLAY_FACT = "m4-v2-historical-branch-decision-replay:M4_MEASUREMENT_CONTRACT_V2:JOINT_RESIDUAL_INCREMENT:VERIFIED"
SUPPORT_MODEL_ID = "TRANSITION_LOCAL_TEMPORAL_PARENT_ALIAS_THETA_ZERO_S2_900_V1"
ESTIMATOR_ID = "EXPANDING_MARGINAL_ORTHOGONAL_IS4_RESIDUAL_TILT_MLE_WITH_FIXED_NULL_TEMPORAL_WARMUP_V2"


def _dep(kind: str, key: str, status: str) -> dict[str, str]:
    return {"dependency_type": kind, "target_key": key, "required_status": status}


def _task(
    key: str,
    capability: str,
    priority: int,
    dependencies: list[dict[str, str]],
    source_digest: str,
    metric: Mapping[str, Any],
) -> dict[str, Any]:
    metric_payload = dict(metric)
    integration = dict(metric_payload["mainline_integration"])
    integration["upstream_artifacts"] = [item["target_key"] for item in dependencies]
    metric_payload["mainline_integration"] = integration
    return {
        "task_key": key,
        "goal_key": GOAL_KEY,
        "task_type": capability,
        "lane": "research",
        "priority": priority,
        "dependencies": dependencies,
        "input_artifact_digests": [source_digest],
        "requested_capability": capability,
        "metric_contract": metric_payload,
        "status": "draft",
        "completion_classification": "INTEGRATION_PENDING",
    }


def _metric(
    phase: str, completion_fact: str, artifacts: list[str], next_consumer: str
) -> dict[str, Any]:
    return {
        "phase": phase,
        "measurement_contract_key": CONTRACT_KEY,
        "measurement_contract_digest": CONTRACT_DIGEST,
        "branch_id": BRANCH_ID,
        "estimand_digest": ESTIMAND_DIGEST,
        "support_model_id": SUPPORT_MODEL_ID,
        "estimator_id": ESTIMATOR_ID,
        "fixed_null_warmup_ordinals": [2, 900],
        "fixed_null_warmup_row_count": 899,
        "theta_float_hex": "0x0.0p+0",
        "theta_fit_invoked": False,
        "warmup_rng_calls": 0,
        "completion_fact": completion_fact,
        "artifact_types_in_registration_order": artifacts,
        "historical_result_reads_before_authorized_producer": 0,
        "evidence_created": False,
        "promotion_gate_opened": False,
        "production_action": "none",
        "mainline_integration": {
            "goal": GOAL_KEY,
            "ready_condition": "all listed dependencies are conjunctively satisfied",
            "runner": "research_evidence_supervisor",
            "upstream_artifacts": [],
            "downstream_artifacts": artifacts,
            "status_projection": "unified_m4_status.measurement_system_v2.joint_residual_increment",
            "evidence_rule": "only the frozen producer path may create scientific artifacts; no Promotion",
            "decision_consumer": next_consumer,
            "next_consumer": next_consumer,
        },
    }


def build_m4_v2_joint_residual_increment_manifest(
    live_payload: Mapping[str, Any], source_contract_digest: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_digest = require_sha256_digest(
        source_contract_digest, field_name="joint_source_contract_digest"
    )
    design_deps = [
        _dep("artifact", SOURCE_FACT, "available"),
        _dep("artifact", TEMPORAL_REPLAY_FACT, "available"),
    ]
    prereg_deps = [
        _dep("task", DESIGN_TASK, "completed"),
        _dep("artifact", DESIGN_FACT, "available"),
    ]
    producer_deps = [
        _dep("task", PREREG_TASK, "completed"),
        _dep("artifact", PREREG_FACT, "available"),
        _dep("artifact", MARGINAL_REPLAY_FACT, "available"),
        _dep("artifact", TEMPORAL_REPLAY_FACT, "available"),
    ]
    replay_deps = [_dep("artifact", TERMINAL_FACT, "available")]
    design_metric = _metric(
        "M4-V2-JOINT-DESIGN",
        DESIGN_FACT,
        ["M4V2JointResidualIncrementDesignArtifact", "research_os_mainline_execution"],
        PREREG_TASK,
    )
    prereg_metric = _metric(
        "M4-V2-JOINT-PREREGISTRATION",
        PREREG_FACT,
        [
            "M4V2JointResidualIncrementPreregistrationArtifact",
            "research_os_mainline_execution",
        ],
        PRODUCER_TASK,
    )
    producer_metric = _metric(
        "M4-V2-JOINT-GATE-COMPILER", PRODUCER_FACT, [], REPLAY_TASK
    )
    producer_metric.update(
        {
            "terminal_fact": TERMINAL_FACT,
            "conditional_capability_not_resolver_or": True,
            "parent_not_accepted_decision": "NOT_EVALUABLE_PARENT_NOT_ACCEPTED",
            "parent_not_accepted_computation": 0,
            "strict_ordinal_chronology": True,
            "producer_path_artifacts": {
                "evaluated_complete": [
                    "M4V2JointResidualMaximumEntropyBaselineArtifact",
                    "M4V2JointResidualMeasurementHealthArtifact",
                    "M4V2JointResidualHistoricalExecutionArtifact",
                    "M4V2JointResidualCandidateModelArtifact",
                    "M4V2BranchDecisionArtifact",
                    "M4V2JointResidualProducerCompletionArtifact",
                    "research_os_mainline_execution",
                ],
                "parent_not_accepted": [
                    "M4V2BranchDecisionArtifact",
                    "M4V2JointResidualProducerCompletionArtifact",
                    "research_os_mainline_execution",
                ],
                "health_repair": [
                    "M4V2JointResidualMeasurementHealthArtifact",
                    "M4V2BranchDecisionArtifact",
                    "M4V2JointResidualProducerCompletionArtifact",
                    "research_os_mainline_execution",
                ],
                "health_invalid": [
                    "M4V2JointResidualScientificFailureArtifact",
                    "M4V2BranchDecisionArtifact",
                    "M4V2JointResidualProducerCompletionArtifact",
                    "research_os_mainline_execution",
                ],
                "historical_repair_or_invalid": [
                    "M4V2JointResidualMeasurementHealthArtifact",
                    "M4V2JointResidualScientificFailureArtifact",
                    "M4V2BranchDecisionArtifact",
                    "M4V2JointResidualProducerCompletionArtifact",
                    "research_os_mainline_execution",
                ],
            },
        }
    )
    producer_paths = producer_metric["producer_path_artifacts"]
    producer_metric["producer_path_counts"] = {
        path: len(artifacts) for path, artifacts in producer_paths.items()
    }
    producer_metric["mainline_integration"]["downstream_artifacts"] = [
        *dict.fromkeys(
            artifact for artifacts in producer_paths.values() for artifact in artifacts
        ),
        TERMINAL_FACT,
        PRODUCER_FACT,
    ]
    replay_metric = _metric(
        "M4-V2-JOINT-DECISION-REPLAY",
        f"{REPLAY_TASK}:COMPLETE",
        ["M4V2BranchDecisionReplayArtifact", "research_os_mainline_execution"],
        "m4-v2-global-routing",
    )
    replay_metric.update(
        {
            "replay_fact": REPLAY_FACT,
            "replay_status": "REGISTERED_REPLAY_VERIFIED",
            "outer_replay_status": "REPLAY_VERIFIED",
            "workload_rerun": False,
        }
    )
    tasks = (
        _task(
            DESIGN_TASK,
            "m4_v2_joint_residual_increment_historical_measurement_design",
            83,
            design_deps,
            source_digest,
            design_metric,
        ),
        _task(
            PREREG_TASK,
            "m4_v2_joint_residual_increment_historical_measurement_preregistration",
            82,
            prereg_deps,
            source_digest,
            prereg_metric,
        ),
        _task(
            PRODUCER_TASK,
            "m4_v2_joint_residual_increment_historical_measurement_gate_compiler",
            81,
            producer_deps,
            source_digest,
            producer_metric,
        ),
        _task(
            REPLAY_TASK,
            "m4_v2_joint_residual_increment_historical_branch_decision_replay",
            80,
            replay_deps,
            source_digest,
            replay_metric,
        ),
    )
    return build_additive_task_manifest(
        live_payload=live_payload, new_tasks=tasks, add_artifact_facts=(SOURCE_FACT,)
    )


build_manifest = build_m4_v2_joint_residual_increment_manifest


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
        description="Build the additive Joint M4-v2 four-task manifest."
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
