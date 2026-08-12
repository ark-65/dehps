from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dehps.research_os.information_theory.measurement_system_v2.migration import (
    M4_V2_FAILED_TASK_KEY,
    M4_V2_RECOVERY_TASK_KEY,
    build_failed_task_recovery_manifest,
    require_sha256_digest,
)
from dehps.research_os.models import (
    M4_V2_MEASUREMENT_CONTRACT_DIGEST,
    M4_V2_MEASUREMENT_CONTRACT_KEY,
)

GOAL_KEY = "M4_INFORMATION_THEORY_EVIDENCE"
MEASUREMENT_CONTRACT_KEY = M4_V2_MEASUREMENT_CONTRACT_KEY
MEASUREMENT_CONTRACT_DIGEST = M4_V2_MEASUREMENT_CONTRACT_DIGEST
SOURCE_CONTRACT_FACT = (
    "m4-v2-marginal-static-historical-identity-adoption-contract:"
    "M4_MEASUREMENT_CONTRACT_V2:FROZEN"
)
DECISION_TASK_KEY = M4_V2_FAILED_TASK_KEY
RECOVERY_TASK_KEY = M4_V2_RECOVERY_TASK_KEY
DECISION_CAPABILITY = "m4_v2_marginal_static_historical_identity_adoption"
REPLAY_TASK_KEY = "m4-v2-marginal-static-historical-branch-decision-replay"
REPLAY_CAPABILITY = "m4_v2_marginal_static_historical_branch_decision_replay"
EXISTING_GATE_TASK_KEY = "m4-v2-marginal-static-historical-measurement-gate-compiler"
TERMINAL_FACT = (
    "m4-v2-historical-branch-decision:M4_MEASUREMENT_CONTRACT_V2:"
    "MARGINAL_STATIC:TERMINAL"
)
REPLAY_FACT = (
    "m4-v2-historical-branch-decision-replay:M4_MEASUREMENT_CONTRACT_V2:"
    "MARGINAL_STATIC:VERIFIED"
)


def _task(
    *,
    task_key: str,
    task_type: str,
    priority: int,
    dependencies: list[dict[str, str]],
    source_contract_digest: str,
    capability: str,
    metric_contract: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "task_key": task_key,
        "goal_key": GOAL_KEY,
        "task_type": task_type,
        "lane": "research",
        "priority": priority,
        "dependencies": dependencies,
        "input_artifact_digests": [source_contract_digest],
        "requested_capability": capability,
        "metric_contract": dict(metric_contract),
        "status": "draft",
        "completion_classification": "INTEGRATION_PENDING",
    }


def build_m4_v2_three_branch_decision_manifest(
    live_payload: Mapping[str, Any],
    source_contract_digest: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Add the identity-only MARGINAL_STATIC Decision and replay tasks.

    Despite the historical filename, this builder does not create Temporal or
    Joint scientific work.  It establishes the first canonical terminal and
    replay facts consumed by their separately frozen four-task DAGs.
    """

    source_digest = require_sha256_digest(
        source_contract_digest,
        field_name="marginal_identity_adoption_source_contract_digest",
    )
    decision = _task(
        task_key=RECOVERY_TASK_KEY,
        task_type=DECISION_CAPABILITY,
        priority=89,
        dependencies=[
            {
                "dependency_type": "artifact",
                "target_key": SOURCE_CONTRACT_FACT,
                "required_status": "available",
            },
            {
                "dependency_type": "task",
                "target_key": EXISTING_GATE_TASK_KEY,
                "required_status": "completed",
            },
        ],
        source_contract_digest=source_digest,
        capability=DECISION_CAPABILITY,
        metric_contract={
            "phase": "M4-V2-MARGINAL-STATIC-IDENTITY-ADOPTION",
            "measurement_contract_key": MEASUREMENT_CONTRACT_KEY,
            "measurement_contract_digest": MEASUREMENT_CONTRACT_DIGEST,
            "branch_id": "MARGINAL_STATIC",
            "identity_adoption_only": True,
            "historical_measurement_rerun": False,
            "historical_result_reads": 0,
            "scientific_computation": 0,
            "terminal_fact": TERMINAL_FACT,
            "completion_fact": f"{RECOVERY_TASK_KEY}:COMPLETE",
            "recovery_lineage": {
                "old_failed_task_key": DECISION_TASK_KEY,
                "old_failed_task_definition_digest": "6f21824945ebdf8e19dcd946ffbc6260f8e28fc52555a5060422f152d37677fd",
                "old_failed_execution_digest": "43eed4c903a59595336b514f17c3be318714535e3b61341ae3a492f03fb4e488",
                "old_started_event_digest": "dfae9cbce68c931b7e0b715223623a4e7691cbb2613b0f6ef3dbdb00deb550a3",
                "old_failed_event_digest": "8291bed8402c539f416f9c8d8a23c2f59800ff544d7b5ca90a5f3878d6ef665f",
                "old_event_manifest_digest": "79a8abb17bb705ab21350d6d3df882bbd39d89c3b7d2a3e9e5fa4f3c43046966",
                "old_durable_history_preserved": True,
            },
            "artifact_types_in_registration_order": [
                "M4V2BranchDecisionArtifact",
                "research_os_mainline_execution",
            ],
            "registration_count": 2,
            "promotion_gate_opened": False,
            "production_action": "none",
            "mainline_integration": {
                "goal": GOAL_KEY,
                "ready_condition": (
                    "the exact frozen source-contract fact is available and "
                    "the canonical existing MARGINAL_STATIC gate task is completed"
                ),
                "runner": "research_evidence_supervisor",
                "upstream_artifacts": [
                    SOURCE_CONTRACT_FACT,
                    EXISTING_GATE_TASK_KEY,
                ],
                "downstream_artifacts": [
                    "M4V2BranchDecisionArtifact",
                    "research_os_mainline_execution",
                    TERMINAL_FACT,
                ],
                "status_projection": (
                    "unified_m4_status.measurement_system_v2."
                    "marginal_static_historical_decision"
                ),
                "evidence_progress_rule": "zero Evidence; categorical identity adoption only",
                "decision_consumer": REPLAY_TASK_KEY,
                "downstream_consumer": REPLAY_TASK_KEY,
            },
        },
    )
    replay = _task(
        task_key=REPLAY_TASK_KEY,
        task_type=REPLAY_CAPABILITY,
        priority=88,
        dependencies=[
            {
                "dependency_type": "artifact",
                "target_key": TERMINAL_FACT,
                "required_status": "available",
            }
        ],
        source_contract_digest=source_digest,
        capability=REPLAY_CAPABILITY,
        metric_contract={
            "phase": "M4-V2-MARGINAL-STATIC-DECISION-REPLAY",
            "measurement_contract_key": MEASUREMENT_CONTRACT_KEY,
            "measurement_contract_digest": MEASUREMENT_CONTRACT_DIGEST,
            "branch_id": "MARGINAL_STATIC",
            "replay_status": "REGISTERED_REPLAY_VERIFIED",
            "outer_replay_status": "REPLAY_VERIFIED",
            "workload_rerun": False,
            "historical_result_reads": 0,
            "scientific_computation": 0,
            "replay_fact": REPLAY_FACT,
            "completion_fact": f"{REPLAY_TASK_KEY}:COMPLETE",
            "artifact_types_in_registration_order": [
                "M4V2BranchDecisionReplayArtifact",
                "research_os_mainline_execution",
            ],
            "registration_count": 2,
            "promotion_gate_opened": False,
            "production_action": "none",
            "mainline_integration": {
                "goal": GOAL_KEY,
                "ready_condition": "the unique registered MARGINAL_STATIC Decision is terminal",
                "runner": "research_evidence_supervisor",
                "upstream_artifacts": [TERMINAL_FACT],
                "downstream_artifacts": [
                    "M4V2BranchDecisionReplayArtifact",
                    "research_os_mainline_execution",
                    REPLAY_FACT,
                ],
                "status_projection": (
                    "unified_m4_status.measurement_system_v2."
                    "marginal_static_historical_decision_replay"
                ),
                "evidence_progress_rule": "zero Evidence; registered-content replay only",
                "decision_consumer": (
                    "m4-v2-temporal-marginal-increment-historical-measurement-design"
                ),
                "downstream_consumer": (
                    "m4-v2-temporal-marginal-increment-historical-measurement-design"
                ),
            },
        },
    )
    return build_failed_task_recovery_manifest(
        live_payload=live_payload,
        recovery_task=decision,
        revised_tasks=(replay,),
        add_artifact_facts=(SOURCE_CONTRACT_FACT,),
    )


build_manifest = build_m4_v2_three_branch_decision_manifest


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON root must be an object: {path}")
    return value


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the additive canonical MARGINAL_STATIC Decision/replay manifest."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", type=Path, required=True)
    args = parser.parse_args()
    inputs = {args.source.resolve(), args.input.resolve()}
    outputs = {args.output.resolve(), args.dry_run.resolve()}
    if len(outputs) != 2 or inputs.intersection(outputs):
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
