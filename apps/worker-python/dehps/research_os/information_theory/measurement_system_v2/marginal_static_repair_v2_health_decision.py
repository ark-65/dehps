from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-v2-health-decision"
)
MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_CAPABILITY = (
    "m4_v2_marginal_static_measurement_repair_v2_health_decision"
)
MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-v2-marginal-static-repair-v2-health-decision-source-v1.json"
)
MARGINAL_STATIC_HISTORICAL_MEASUREMENT_DESIGN_TASK_KEY = (
    "m4-v2-marginal-static-historical-measurement-design"
)
MARGINAL_STATIC_REPAIR_V3_DESIGN_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-v3-design"
)

MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_PASS_FACT = (
    "m4-v2-marginal-static-measurement-repair-v2-health-decision:PASS"
)
MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_REPAIR_FACT = (
    "m4-v2-marginal-static-measurement-repair-v2-health-decision:REPAIR"
)
MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_INCONCLUSIVE_FACT = (
    "m4-v2-marginal-static-measurement-repair-v2-health-decision:INCONCLUSIVE"
)

REPAIR_V2_HEALTH_EXECUTION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-v2-health-execution"
)
REPAIR_V2_HEALTH_EXECUTION_TASK_DIGEST = (
    "a2734547dcfd86b7da3d201f175f0063a4ddef539dc23861521f1c9a29c68ecc"
)
REPAIR_V2_HEALTH_EXECUTION_ID = (
    "96d23c946b8d5b0ee1df74026f0991c79683a26daa4630cf172974d822da920e"
)
REPAIR_V2_HEALTH_EXECUTION_ARTIFACT_DIGEST = (
    "7701f3ffe48e7163a7e8d68cd4b54d98008810b7cf1975bb4a3d533052f8e62a"
)
REPAIR_V2_HEALTH_RESULT_DIGEST = (
    "b09069a0774201b3cc59572f309416885c674e6d58d5bae050f01201e25493d5"
)
REPAIR_V2_HEALTH_COMPLETION_DIGEST = (
    "f817867000d810f622037c09a4b93280e46aae9178b8af0cd122e36f21397e21"
)
REPAIR_V2_HEALTH_COMPLETION_INDEX_DIGEST = (
    "577d93cfa220cb3df5589a16d15ab4ea35038b2f294ddca7b07a7fbb67533651"
)
REPAIR_V2_HEALTH_EXECUTION_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-repair-v2-health-execution:COMPLETE"
)
REPAIR_V2_WORKLOAD_SEED_DIGEST = (
    "ebf207815b452aa41a5f4c5071b5b05288784d420c4c7c16db05ce0ec67ec6fe"
)
REPAIR_V2_INFERENCE_GATE_DIGEST = (
    "2a4d86430b85e7a262918275a08fbe8e1977311de08eb3ee4fe603208714adf5"
)
REPAIR_V2_PREREGISTRATION_DIGEST = (
    "e3043d3c3c9e95e531d9255062bc1133f32937c82b99ca729ffdad5611a08ece"
)

REQUIRED_GATE_CELL_IDS = (
    "BASE:NULL_UNIFORM_LEGAL_SIX_OF_33:FORWARD_61",
    "BASE:NULL_UNIFORM_LEGAL_SIX_OF_33:HISTORICAL_2581",
    "BASE:V2_J1_HISTORY_IS4_LAMBDA_HALF:FORWARD_61",
    "BASE:V2_J1_HISTORY_IS4_LAMBDA_HALF:HISTORICAL_2581",
    "BASE:V2_M1_GROUP_ODDS_2_STATIONARY:FORWARD_61",
    "BASE:V2_M1_GROUP_ODDS_2_STATIONARY:HISTORICAL_2581",
    "BASE:V2_T1_OVERLAP_ODDS_2_MARKOV:FORWARD_61",
    "BASE:V2_T1_OVERLAP_ODDS_2_MARKOV:HISTORICAL_2581",
    "LOCAL_M1:0.010:HISTORICAL_2581",
    "LOCAL_M1:0.050:HISTORICAL_2581",
)
ADMISSIBLE_LOCAL_CELL_IDS = (
    "LOCAL_M1:0.010:HISTORICAL_2581",
    "LOCAL_M1:0.050:HISTORICAL_2581",
)
EXPECTED_SENSITIVITY_LIMIT_TOPOLOGY: dict[str, dict[str, float | str]] = {
    "LOCAL_M1:0.001:FORWARD_61": {
        "classification": "SENSITIVITY_LIMIT",
        "detection_rate": 0.0439453125,
        "wilson_lower_95": 0.03300347187860741,
        "wilson_upper_95": 0.0582960743844556,
    },
    "LOCAL_M1:0.001:HISTORICAL_2581": {
        "classification": "SENSITIVITY_LIMIT",
        "detection_rate": 0.1103515625,
        "wilson_lower_95": 0.09259750057271413,
        "wilson_upper_95": 0.13101817171628405,
    },
    "LOCAL_M1:0.010:FORWARD_61": {
        "classification": "SENSITIVITY_LIMIT",
        "detection_rate": 0.11328125,
        "wilson_lower_95": 0.09529706066474786,
        "wilson_upper_95": 0.13415608777245333,
    },
    "LOCAL_M1:0.050:FORWARD_61": {
        "classification": "SENSITIVITY_LIMIT",
        "detection_rate": 0.41796875,
        "wilson_lower_95": 0.3881208062204002,
        "wilson_upper_95": 0.4484298616299153,
    },
}

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-m4-v2-marginal-static-repair-v2-health-decision-round-51-20260808"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-v2-marginal-static-repair-v2-health-decision-round-51-20260808"
)
_SOURCE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/marginal_static_repair_v2_health_decision.py"
)

_DECISION_BY_HEALTH = {
    "PASS": (
        "PASS_TO_HISTORICAL_MEASUREMENT",
        MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_PASS_FACT,
        True,
        MARGINAL_STATIC_HISTORICAL_MEASUREMENT_DESIGN_TASK_KEY,
    ),
    "REPAIR": (
        "REPAIR_MEASUREMENT_SYSTEM",
        MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_REPAIR_FACT,
        False,
        MARGINAL_STATIC_REPAIR_V3_DESIGN_TASK_KEY,
    ),
    "INCONCLUSIVE": (
        "HOLD_INCONCLUSIVE",
        MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_INCONCLUSIVE_FACT,
        False,
        MARGINAL_STATIC_REPAIR_V3_DESIGN_TASK_KEY,
    ),
}


class MarginalStaticRepairV2HealthDecisionError(RuntimeError):
    pass


def load_marginal_static_repair_v2_health_decision_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticRepairV2HealthDecisionError(
            f"marginal_static_repair_v2_health_decision_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-repair-v2-health-decision-source.v1"
        or payload.get("artifact_type")
        != "m4_v2_marginal_static_repair_v2_health_decision_source"
        or payload.get("contract_key")
        != "M4_V2_MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 359
        or payload.get("research_execution_id") != 280
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 360
        or payload.get("engineering_execution_id") != 281
        or payload.get("result_aware") is not True
        or payload.get("formal_children_executed") != 0
        or payload.get("generated_issues") != 0
        or payload.get("compact_index_reads") != 0
        or payload.get("raw_replicates_regenerated") != 0
        or payload.get("sentinel_replicates_recomputed") != 0
        or payload.get("duplicate_validation") != "forbidden"
        or payload.get("historical_outcomes_read") is not False
        or payload.get("statistical_results_read") is not True
        or payload.get("evidence_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or len(entries) != 1
        or not isinstance(frozen, dict)
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain=(
                "dehps.m4.v2.marginal-static-repair-v2-health-decision-source-set.v1"
            ),
        )
    ):
        raise MarginalStaticRepairV2HealthDecisionError(
            "marginal_static_repair_v2_health_decision_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise MarginalStaticRepairV2HealthDecisionError(
            "marginal_static_repair_v2_health_decision_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_marginal_static_repair_v2_health_decision_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MarginalStaticRepairV2HealthDecisionError(
                f"marginal_static_repair_v2_health_decision_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise MarginalStaticRepairV2HealthDecisionError(
                f"marginal_static_repair_v2_health_decision_source_modified:{relative}"
            )


def repair_v2_health_decision_mapping(
    measurement_health: str,
) -> tuple[str, str, bool, str]:
    try:
        return _DECISION_BY_HEALTH[measurement_health]
    except KeyError as exc:
        raise MarginalStaticRepairV2HealthDecisionError(
            "marginal_static_repair_v2_health_decision_unrecognized_health"
        ) from exc


def build_marginal_static_repair_v2_health_decision(
    *,
    source_contract: Mapping[str, Any],
    health_execution: Mapping[str, Any],
    health_result: Mapping[str, Any],
    health_completion: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_frozen_contract(source_contract["frozen_contract"])
    _validate_parent_artifacts(
        health_execution=health_execution,
        health_result=health_result,
        health_completion=health_completion,
    )
    required_ids = _required_gate_cell_ids(health_result)
    sensitivity_topology = _sensitivity_limit_topology(health_result)
    measurement_health = str(health_result["preliminary_measurement_health"])
    decision, decision_fact, historical_eligible, next_consumer = (
        repair_v2_health_decision_mapping(measurement_health)
    )
    payload: dict[str, Any] = {
        "schema_version": ("dehps-m4-v2-marginal-static-repair-v2-health-decision.v1"),
        "artifact_type": (
            "m4_v2_marginal_static_measurement_repair_v2_health_decision"
        ),
        "artifact_digest": "",
        "status": "COMPLETE",
        "branch_id": "MARGINAL_STATIC",
        "source_contract_digest": source_contract["artifact_digest"],
        "workload_and_seed_digest": REPAIR_V2_WORKLOAD_SEED_DIGEST,
        "inference_gate_digest": REPAIR_V2_INFERENCE_GATE_DIGEST,
        "preregistration_digest": REPAIR_V2_PREREGISTRATION_DIGEST,
        "health_execution_id": health_execution["execution_id"],
        "health_execution_artifact_digest": health_execution["artifact_digest"],
        "health_result_digest": health_result["artifact_digest"],
        "health_completion_digest": health_completion["artifact_digest"],
        "completion_index_digest": REPAIR_V2_HEALTH_COMPLETION_INDEX_DIGEST,
        "measurement_health": measurement_health,
        "authoritative_decision": decision,
        "decision": decision,
        "decision_fact": decision_fact,
        "failed_required_gate_cell_ids": [],
        "failed_required_gate_cell_count": 0,
        "required_gate_cell_ids": list(required_ids),
        "required_gate_cell_count": len(required_ids),
        "admissible_local_cell_ids": list(ADMISSIBLE_LOCAL_CELL_IDS),
        "admissible_local_cell_count": len(ADMISSIBLE_LOCAL_CELL_IDS),
        "sensitivity_limit_cell_ids": list(sensitivity_topology),
        "sensitivity_limit_topology": sensitivity_topology,
        "sensitivity_limit_cell_count": len(sensitivity_topology),
        "eligible_for_historical_measurement": historical_eligible,
        "eligible_for_historical_measurement_design": historical_eligible,
        "historical_measurement_execution_authorized": False,
        "accepted_model_artifact_digest": None,
        "historical_evidence": "NOT_RUN",
        "historical_execution_status": "NOT_AUTHORIZED",
        "formal_children_executed": 0,
        "generated_issues": 0,
        "compact_index_reads": 0,
        "raw_replicates_regenerated": 0,
        "sentinel_replicates_recomputed": 0,
        "duplicate_validation": False,
        "statistical_results_read": True,
        "historical_outcomes_read": False,
        "evidence_created": False,
        "evidence_progress_increment": 0,
        "promotion_gate_opened": False,
        "production_action": "none",
        "manual_override": False,
        "threshold_changed": False,
        "next_consumer": next_consumer,
        "parent_digests": [
            str(source_contract["artifact_digest"]),
            REPAIR_V2_WORKLOAD_SEED_DIGEST,
            REPAIR_V2_INFERENCE_GATE_DIGEST,
            REPAIR_V2_PREREGISTRATION_DIGEST,
            str(health_execution["artifact_digest"]),
            str(health_result["artifact_digest"]),
            str(health_completion["artifact_digest"]),
        ],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.v2.marginal-static-repair-v2-health-decision.v1",
    )
    return payload


def _validate_parent_artifacts(
    *,
    health_execution: Mapping[str, Any],
    health_result: Mapping[str, Any],
    health_completion: Mapping[str, Any],
) -> None:
    _verify_artifact(
        health_execution,
        domain="dehps.research-os.mainline-execution.v1",
    )
    _verify_artifact(
        health_result,
        domain=("dehps.m4.v2.marginal-static-repair-v2-measurement-health-result.v1"),
    )
    _verify_artifact(
        health_completion,
        domain=("dehps.m4.v2.marginal-static-repair-v2-health-execution-completion.v1"),
    )
    if (
        health_execution.get("artifact_type") != "research_os_mainline_execution"
        or health_execution.get("artifact_digest")
        != REPAIR_V2_HEALTH_EXECUTION_ARTIFACT_DIGEST
        or health_execution.get("execution_id") != REPAIR_V2_HEALTH_EXECUTION_ID
        or health_execution.get("task_key") != REPAIR_V2_HEALTH_EXECUTION_TASK_KEY
        or health_execution.get("task_digest") != REPAIR_V2_HEALTH_EXECUTION_TASK_DIGEST
        or health_execution.get("status") != "COMPLETE"
        or health_execution.get("completion_classification") != "VALIDATED_IN_MAINLINE"
        or health_execution.get("completion_fact")
        != REPAIR_V2_HEALTH_EXECUTION_COMPLETION_FACT
        or health_execution.get("repair_v2_health_result_digest")
        != REPAIR_V2_HEALTH_RESULT_DIGEST
        or health_execution.get("repair_v2_health_execution_completion_digest")
        != REPAIR_V2_HEALTH_COMPLETION_DIGEST
        or health_execution.get("repair_v2_preliminary_measurement_health") != "PASS"
        or health_execution.get("repair_v2_authoritative_decision") is not None
        or health_execution.get("duplicate_validation") is not False
        or health_execution.get("historical_outcomes_read") is not False
        or health_execution.get("evidence_created") is not False
        or health_execution.get("production_action") != "none"
        or health_result.get("artifact_type")
        != "m4_v2_marginal_static_repair_v2_measurement_health_result"
        or health_result.get("artifact_digest") != REPAIR_V2_HEALTH_RESULT_DIGEST
        or health_result.get("status") != "COMPLETE_PENDING_DECISION_REPLAY"
        or health_result.get("preliminary_measurement_health") != "PASS"
        or health_result.get("authoritative_decision") is not None
        or health_result.get("branch_id") != "MARGINAL_STATIC"
        or health_result.get("cell_count") != 14
        or health_result.get("negative_control_count") != 6
        or health_result.get("positive_control_count") != 2
        or health_result.get("admissible_local_cell_count") != 2
        or health_result.get("failed_required_gate_cell_ids") != []
        or health_result.get("failed_required_gate_cell_count") != 0
        or health_result.get("all_children_complete") is not True
        or health_result.get("all_legal_finite_and_identity_valid") is not True
        or health_result.get("familywise_claim_basis") != "union_bound_only"
        or health_result.get("cross_cell_independence_claimed") is not False
        or health_result.get("manual_override") is not False
        or health_result.get("workload_digest") != REPAIR_V2_WORKLOAD_SEED_DIGEST
        or health_result.get("inference_digest") != REPAIR_V2_INFERENCE_GATE_DIGEST
        or health_result.get("preregistration_digest")
        != REPAIR_V2_PREREGISTRATION_DIGEST
        or health_result.get("completion_index_digest")
        != REPAIR_V2_HEALTH_COMPLETION_INDEX_DIGEST
        or health_result.get("historical_execution_status") != "NOT_AUTHORIZED"
        or health_result.get("historical_outcomes_read") is not False
        or health_result.get("evidence_created") is not False
        or health_result.get("promotion_gate_opened") is not False
        or health_result.get("production_action") != "none"
        or health_completion.get("artifact_type")
        != "m4_v2_marginal_static_repair_v2_health_execution_completion"
        or health_completion.get("artifact_digest")
        != REPAIR_V2_HEALTH_COMPLETION_DIGEST
        or health_completion.get("status") != "COMPLETE"
        or health_completion.get("execution_id") != REPAIR_V2_HEALTH_EXECUTION_ID
        or health_completion.get("preliminary_measurement_health") != "PASS"
        or health_completion.get("authoritative_decision") is not None
        or health_completion.get("health_result_digest")
        != REPAIR_V2_HEALTH_RESULT_DIGEST
        or health_completion.get("completion_index_digest")
        != REPAIR_V2_HEALTH_COMPLETION_INDEX_DIGEST
        or health_completion.get("completion_fact")
        != REPAIR_V2_HEALTH_EXECUTION_COMPLETION_FACT
        or health_completion.get("duplicate_validation") is not False
        or health_completion.get("historical_outcomes_read") is not False
        or health_completion.get("evidence_created") is not False
        or health_completion.get("promotion_gate_opened") is not False
        or health_completion.get("production_action") != "none"
    ):
        raise MarginalStaticRepairV2HealthDecisionError(
            "marginal_static_repair_v2_health_decision_parent_identity_changed"
        )
    if _required_gate_cell_ids(health_result) != REQUIRED_GATE_CELL_IDS:
        raise MarginalStaticRepairV2HealthDecisionError(
            "marginal_static_repair_v2_health_decision_required_topology_changed"
        )
    if (
        _sensitivity_limit_topology(health_result)
        != EXPECTED_SENSITIVITY_LIMIT_TOPOLOGY
    ):
        raise MarginalStaticRepairV2HealthDecisionError(
            "marginal_static_repair_v2_health_decision_sensitivity_topology_changed"
        )


def _required_gate_cell_ids(health_result: Mapping[str, Any]) -> tuple[str, ...]:
    cells = health_result.get("cell_results")
    if not isinstance(cells, list):
        raise MarginalStaticRepairV2HealthDecisionError(
            "marginal_static_repair_v2_health_decision_cells_invalid"
        )
    required: list[str] = []
    for result in cells:
        if not isinstance(result, Mapping):
            raise MarginalStaticRepairV2HealthDecisionError(
                "marginal_static_repair_v2_health_decision_cell_invalid"
            )
        cell = result.get("cell")
        gates = result.get("gates")
        if not isinstance(cell, Mapping) or not isinstance(gates, Mapping):
            raise MarginalStaticRepairV2HealthDecisionError(
                "marginal_static_repair_v2_health_decision_cell_invalid"
            )
        if result.get("required_gate") is True:
            if not gates or not all(value is True for value in gates.values()):
                raise MarginalStaticRepairV2HealthDecisionError(
                    "marginal_static_repair_v2_health_decision_required_gate_failed"
                )
            required.append(str(cell.get("cell_id") or ""))
    return tuple(sorted(required))


def _sensitivity_limit_topology(
    health_result: Mapping[str, Any],
) -> dict[str, dict[str, float | str]]:
    cells = health_result.get("cell_results")
    if not isinstance(cells, list):
        raise MarginalStaticRepairV2HealthDecisionError(
            "marginal_static_repair_v2_health_decision_cells_invalid"
        )
    limits: dict[str, dict[str, float | str]] = {}
    for result in cells:
        if not isinstance(result, Mapping):
            raise MarginalStaticRepairV2HealthDecisionError(
                "marginal_static_repair_v2_health_decision_cell_invalid"
            )
        cell = result.get("cell")
        if not isinstance(cell, Mapping):
            raise MarginalStaticRepairV2HealthDecisionError(
                "marginal_static_repair_v2_health_decision_cell_invalid"
            )
        if result.get("classification") != "SENSITIVITY_LIMIT":
            continue
        if (
            result.get("required_gate") is not False
            or cell.get("role") != "LOCAL_POWER"
        ):
            raise MarginalStaticRepairV2HealthDecisionError(
                "marginal_static_repair_v2_health_decision_sensitivity_invalid"
            )
        cell_id = str(cell.get("cell_id") or "")
        limits[cell_id] = {
            "classification": "SENSITIVITY_LIMIT",
            "detection_rate": float(result["detection_rate"]),
            "wilson_lower_95": float(result["wilson_lower_95"]),
            "wilson_upper_95": float(result["wilson_upper_95"]),
        }
    return {key: limits[key] for key in sorted(limits)}


def _verify_artifact(payload: Mapping[str, Any], *, domain: str) -> None:
    supplied = str(payload.get("artifact_digest") or "")
    identity = {
        key: value for key, value in payload.items() if key != "artifact_digest"
    }
    if not _is_digest(supplied) or supplied != canonical_digest(
        identity, domain=domain
    ):
        raise MarginalStaticRepairV2HealthDecisionError(
            "marginal_static_repair_v2_health_decision_parent_digest_changed"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if (
        frozen.get("task_key") != MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY
        or frozen.get("capability")
        != MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_CAPABILITY
        or frozen.get("next_consumer")
        != MARGINAL_STATIC_HISTORICAL_MEASUREMENT_DESIGN_TASK_KEY
        or frozen.get("repair_v2_health_execution_task_digest")
        != REPAIR_V2_HEALTH_EXECUTION_TASK_DIGEST
        or frozen.get("repair_v2_health_execution_id") != REPAIR_V2_HEALTH_EXECUTION_ID
        or frozen.get("repair_v2_health_execution_artifact_digest")
        != REPAIR_V2_HEALTH_EXECUTION_ARTIFACT_DIGEST
        or frozen.get("repair_v2_health_result_digest")
        != REPAIR_V2_HEALTH_RESULT_DIGEST
        or frozen.get("repair_v2_health_completion_digest")
        != REPAIR_V2_HEALTH_COMPLETION_DIGEST
        or frozen.get("repair_v2_health_completion_index_digest")
        != REPAIR_V2_HEALTH_COMPLETION_INDEX_DIGEST
        or frozen.get("repair_v2_workload_seed_digest")
        != REPAIR_V2_WORKLOAD_SEED_DIGEST
        or frozen.get("repair_v2_inference_gate_digest")
        != REPAIR_V2_INFERENCE_GATE_DIGEST
        or frozen.get("repair_v2_preregistration_digest")
        != REPAIR_V2_PREREGISTRATION_DIGEST
        or frozen.get("measurement_health") != "PASS"
        or frozen.get("decision") != "PASS_TO_HISTORICAL_MEASUREMENT"
        or frozen.get("decision_fact")
        != MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_PASS_FACT
        or frozen.get("required_gate_cell_ids") != list(REQUIRED_GATE_CELL_IDS)
        or frozen.get("admissible_local_cell_ids") != list(ADMISSIBLE_LOCAL_CELL_IDS)
        or frozen.get("sensitivity_limit_topology")
        != EXPECTED_SENSITIVITY_LIMIT_TOPOLOGY
        or frozen.get("decision_rule_changed") is not False
        or frozen.get("formal_children") != 0
        or frozen.get("generated_issues") != 0
        or frozen.get("compact_index_reads") != 0
        or frozen.get("raw_replicates_regenerated") != 0
        or frozen.get("sentinel_replicates_recomputed") != 0
        or frozen.get("duplicate_validation") != "forbidden"
        or frozen.get("historical_outcomes_read") is not False
        or frozen.get("evidence_created") is not False
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("production_action") != "none"
    ):
        raise MarginalStaticRepairV2HealthDecisionError(
            "marginal_static_repair_v2_health_decision_contract_invalid"
        )


def _is_digest(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)
