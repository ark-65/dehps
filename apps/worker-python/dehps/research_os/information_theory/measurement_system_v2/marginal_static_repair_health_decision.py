from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-health-decision"
)
MARGINAL_STATIC_REPAIR_HEALTH_DECISION_CAPABILITY = (
    "m4_v2_marginal_static_measurement_repair_health_decision"
)
MARGINAL_STATIC_REPAIR_HEALTH_DECISION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-v2-marginal-static-repair-health-decision-source-v1.json"
)
MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-v2-design"
)
MARGINAL_STATIC_HISTORICAL_MEASUREMENT_TASK_KEY = (
    "m4-v2-marginal-static-historical-measurement"
)
MARGINAL_STATIC_REPAIR_HEALTH_DECISION_REPAIR_FACT = (
    "m4-v2-marginal-static-measurement-repair-health-decision:REPAIR"
)
MARGINAL_STATIC_REPAIR_HEALTH_DECISION_PASS_FACT = (
    "m4-v2-marginal-static-measurement-repair-health-decision:PASS"
)
MARGINAL_STATIC_REPAIR_HEALTH_DECISION_INCONCLUSIVE_FACT = (
    "m4-v2-marginal-static-measurement-repair-health-decision:INCONCLUSIVE"
)

REPAIR_HEALTH_EXECUTION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-health-execution"
)
REPAIR_HEALTH_EXECUTION_TASK_DIGEST = (
    "d26d486ce4eb16140a6d8c8696bdb9adac04daae4b99818ca22759c28116741f"
)
REPAIR_HEALTH_EXECUTION_ID = (
    "f030cff87b119653bbef3a0016846f001de10c9e4213307dff13c53d064b38cb"
)
REPAIR_HEALTH_EXECUTION_ARTIFACT_DIGEST = (
    "2d2e4b542d51980b131e303b931d56ccbc7e96c1e75c4c6115957bdf20827116"
)
REPAIR_HEALTH_RESULT_DIGEST = (
    "f7bc1d3a2d64945eb8a93d1f9afec499f11e4f7c90a1b91a8e1825e26d1dce3f"
)
REPAIR_HEALTH_COMPLETION_DIGEST = (
    "f9a79b6d2ea60237c575f39d4524636a5d9b6f31d1e461c7bf56e3ce7066b462"
)
REPAIR_HEALTH_EXECUTION_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-repair-health-execution:COMPLETE"
)
REPAIR_PREREGISTRATION_DIGEST = (
    "db904f2a5b934a8eef9c053b698b771a36a7c79f488439601e2dc66acc551476"
)
REPAIR_INFERENCE_GATE_DIGEST = (
    "4a4491baf21295a881451549cf7f99b668681eb11b3a890c84be26f3de41df0e"
)

EXPECTED_FAILED_CONTROL_TOPOLOGY: dict[str, dict[str, float | str]] = {
    "BASE:V2_J1_HISTORY_IS4_LAMBDA_HALF:HISTORICAL_2581": {
        "classification": "NEGATIVE_CONTROL_FAIL",
        "detection_rate": 0.0703125,
        "wilson_lower_95": 0.04493554746197091,
        "wilson_upper_95": 0.10839432915401236,
        "failed_gate": "negative_control_wilson_upper",
    },
    "BASE:V2_T1_OVERLAP_ODDS_2_MARKOV:FORWARD_61": {
        "classification": "NEGATIVE_CONTROL_FAIL",
        "detection_rate": 0.078125,
        "wilson_lower_95": 0.05114064056843023,
        "wilson_upper_95": 0.11758323829089878,
        "failed_gate": "negative_control_wilson_upper",
    },
    "BASE:V2_T1_OVERLAP_ODDS_2_MARKOV:HISTORICAL_2581": {
        "classification": "NEGATIVE_CONTROL_FAIL",
        "detection_rate": 0.1484375,
        "wilson_lower_95": 0.1100947469586396,
        "wilson_upper_95": 0.19717515209080125,
        "failed_gate": "negative_control_wilson_upper",
    },
}

_DECISION_BY_HEALTH = {
    "PASS": (
        "PASS_TO_HISTORICAL_MEASUREMENT",
        MARGINAL_STATIC_REPAIR_HEALTH_DECISION_PASS_FACT,
        True,
        MARGINAL_STATIC_HISTORICAL_MEASUREMENT_TASK_KEY,
    ),
    "REPAIR": (
        "REPAIR_MEASUREMENT_SYSTEM",
        MARGINAL_STATIC_REPAIR_HEALTH_DECISION_REPAIR_FACT,
        False,
        MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY,
    ),
    "INCONCLUSIVE": (
        "HOLD_INCONCLUSIVE",
        MARGINAL_STATIC_REPAIR_HEALTH_DECISION_INCONCLUSIVE_FACT,
        False,
        MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY,
    ),
}


class MarginalStaticRepairHealthDecisionError(RuntimeError):
    pass


def load_marginal_static_repair_health_decision_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticRepairHealthDecisionError(
            f"marginal_static_repair_health_decision_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-repair-health-decision-source.v1"
        or payload.get("artifact_type")
        != "m4_v2_marginal_static_repair_health_decision_source"
        or payload.get("contract_key")
        != "M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_DECISION_SOURCE"
        or payload.get("research_request_key")
        != "research-m4-v2-marginal-static-repair-health-decision-round-47-20260808"
        or payload.get("research_request_id") != 346
        or payload.get("research_execution_id") != 267
        or payload.get("engineering_request_key")
        != "engineering-m4-v2-marginal-static-repair-health-decision-round-47-20260808"
        or payload.get("engineering_request_id") != 347
        or payload.get("engineering_execution_id") != 268
        or payload.get("result_aware") is not True
        or payload.get("formal_replicates_executed") != 0
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
            domain=("dehps.m4.v2.marginal-static-repair-health-decision-source-set.v1"),
        )
    ):
        raise MarginalStaticRepairHealthDecisionError(
            "marginal_static_repair_health_decision_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path")
        != (
            "apps/worker-python/dehps/research_os/information_theory/"
            "measurement_system_v2/marginal_static_repair_health_decision.py"
        )
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise MarginalStaticRepairHealthDecisionError(
            "marginal_static_repair_health_decision_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_marginal_static_repair_health_decision_source_bytes(
    *,
    root_dir: Path,
    contract: Mapping[str, Any],
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MarginalStaticRepairHealthDecisionError(
                f"marginal_static_repair_health_decision_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise MarginalStaticRepairHealthDecisionError(
                f"marginal_static_repair_health_decision_source_modified:{relative}"
            )


def repair_health_decision_mapping(
    measurement_health: str,
) -> tuple[str, str, bool, str]:
    try:
        return _DECISION_BY_HEALTH[measurement_health]
    except KeyError as exc:
        raise MarginalStaticRepairHealthDecisionError(
            "marginal_static_repair_health_decision_unrecognized_health"
        ) from exc


def build_marginal_static_repair_health_decision(
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
    failed_topology = _failed_control_topology(health_result)
    measurement_health = str(health_result["preliminary_measurement_health"])
    decision, decision_fact, historical_eligible, next_consumer = (
        repair_health_decision_mapping(measurement_health)
    )
    payload: dict[str, Any] = {
        "schema_version": ("dehps-m4-v2-marginal-static-repair-health-decision.v1"),
        "artifact_type": ("m4_v2_marginal_static_measurement_repair_health_decision"),
        "artifact_digest": "",
        "status": "COMPLETE",
        "branch_id": "MARGINAL_STATIC",
        "source_contract_digest": source_contract["artifact_digest"],
        "repair_preregistration_digest": REPAIR_PREREGISTRATION_DIGEST,
        "repair_inference_gate_digest": REPAIR_INFERENCE_GATE_DIGEST,
        "health_execution_id": health_execution["execution_id"],
        "health_execution_artifact_digest": health_execution["artifact_digest"],
        "health_result_digest": health_result["artifact_digest"],
        "health_completion_digest": health_completion["artifact_digest"],
        "measurement_health": measurement_health,
        "authoritative_decision": decision,
        "decision": decision,
        "decision_fact": decision_fact,
        "failed_control_cell_ids": list(failed_topology),
        "failed_control_topology": failed_topology,
        "failed_control_cell_count": len(failed_topology),
        "instrument_limit_cell_ids": list(health_result["instrument_limit_cell_ids"]),
        "instrument_limit_cell_count": len(health_result["instrument_limit_cell_ids"]),
        "eligible_for_historical_measurement": historical_eligible,
        "accepted_model_artifact_digest": None,
        "historical_evidence": "NOT_RUN",
        "historical_execution_status": "NOT_AUTHORIZED",
        "formal_replicates_executed": 0,
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
            REPAIR_PREREGISTRATION_DIGEST,
            REPAIR_INFERENCE_GATE_DIGEST,
            str(health_execution["artifact_digest"]),
            str(health_result["artifact_digest"]),
            str(health_completion["artifact_digest"]),
        ],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.v2.marginal-static-repair-health-decision.v1",
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
        domain=("dehps.m4.v2.marginal-static-repaired-measurement-health-result.v1"),
    )
    _verify_artifact(
        health_completion,
        domain=("dehps.m4.v2.marginal-static-repair-health-execution-completion.v1"),
    )
    expected_failure_ids = sorted(EXPECTED_FAILED_CONTROL_TOPOLOGY)
    if (
        health_execution.get("artifact_type") != "research_os_mainline_execution"
        or health_execution.get("artifact_digest")
        != REPAIR_HEALTH_EXECUTION_ARTIFACT_DIGEST
        or health_execution.get("execution_id") != REPAIR_HEALTH_EXECUTION_ID
        or health_execution.get("task_key") != REPAIR_HEALTH_EXECUTION_TASK_KEY
        or health_execution.get("task_digest") != REPAIR_HEALTH_EXECUTION_TASK_DIGEST
        or health_execution.get("status") != "COMPLETE"
        or health_execution.get("completion_classification") != "VALIDATED_IN_MAINLINE"
        or health_execution.get("completion_fact")
        != REPAIR_HEALTH_EXECUTION_COMPLETION_FACT
        or health_execution.get("marginal_static_repair_health_result_digest")
        != REPAIR_HEALTH_RESULT_DIGEST
        or health_execution.get(
            "marginal_static_repair_health_execution_completion_digest"
        )
        != REPAIR_HEALTH_COMPLETION_DIGEST
        or health_execution.get("repair_health_preliminary_measurement_health")
        != "REPAIR"
        or health_execution.get("repair_health_authoritative_decision") is not None
        or health_execution.get("duplicate_validation") is not False
        or health_execution.get("historical_outcomes_read") is not False
        or health_execution.get("evidence_created") is not False
        or health_execution.get("production_action") != "none"
        or health_result.get("artifact_type")
        != "m4_v2_marginal_static_repaired_measurement_health_result"
        or health_result.get("artifact_digest") != REPAIR_HEALTH_RESULT_DIGEST
        or health_result.get("status") != "COMPLETE_PENDING_DECISION_REPLAY"
        or health_result.get("preliminary_measurement_health") != "REPAIR"
        or health_result.get("authoritative_decision") is not None
        or health_result.get("branch_id") != "MARGINAL_STATIC"
        or health_result.get("cell_count") != 14
        or health_result.get("replicate_count") != 4_608
        or health_result.get("all_legal") is not True
        or health_result.get("all_finite") is not True
        or health_result.get("all_cells_complete") is not True
        or health_result.get("conditional_identity_pass") is not True
        or health_result.get("manual_or_partial_override") is not False
        or health_result.get("control_failure_cell_ids") != expected_failure_ids
        or health_result.get("instrument_limit_cell_ids") != []
        or health_result.get("accepted_model_artifact_digest") is not None
        or health_result.get("historical_execution_status") != "NOT_AUTHORIZED"
        or health_result.get("historical_outcomes_read") is not False
        or health_result.get("round_42_statistical_results_read") is not False
        or health_result.get("evidence_created") is not False
        or health_result.get("production_action") != "none"
        or health_completion.get("artifact_type")
        != "m4_v2_marginal_static_repair_health_execution_completion"
        or health_completion.get("artifact_digest") != REPAIR_HEALTH_COMPLETION_DIGEST
        or health_completion.get("status") != "COMPLETE"
        or health_completion.get("execution_id") != REPAIR_HEALTH_EXECUTION_ID
        or health_completion.get("preliminary_measurement_health") != "REPAIR"
        or health_completion.get("authoritative_decision") is not None
        or health_completion.get("health_result_digest") != REPAIR_HEALTH_RESULT_DIGEST
        or health_completion.get("completion_fact")
        != REPAIR_HEALTH_EXECUTION_COMPLETION_FACT
        or health_completion.get("duplicate_validation") is not False
        or health_completion.get("historical_outcomes_read") is not False
        or health_completion.get("evidence_created") is not False
        or health_completion.get("production_action") != "none"
    ):
        raise MarginalStaticRepairHealthDecisionError(
            "marginal_static_repair_health_decision_parent_identity_changed"
        )
    if _failed_control_topology(health_result) != EXPECTED_FAILED_CONTROL_TOPOLOGY:
        raise MarginalStaticRepairHealthDecisionError(
            "marginal_static_repair_health_decision_failed_topology_changed"
        )


def _failed_control_topology(
    health_result: Mapping[str, Any],
) -> dict[str, dict[str, float | str]]:
    cells = health_result.get("cell_results")
    if not isinstance(cells, list):
        raise MarginalStaticRepairHealthDecisionError(
            "marginal_static_repair_health_decision_cells_invalid"
        )
    failure_ids = health_result.get("control_failure_cell_ids")
    if not isinstance(failure_ids, list):
        raise MarginalStaticRepairHealthDecisionError(
            "marginal_static_repair_health_decision_failure_ids_invalid"
        )
    failed: dict[str, dict[str, float | str]] = {}
    for result in cells:
        if not isinstance(result, Mapping):
            raise MarginalStaticRepairHealthDecisionError(
                "marginal_static_repair_health_decision_cell_invalid"
            )
        cell = result.get("cell")
        gates = result.get("gates")
        if not isinstance(cell, Mapping) or not isinstance(gates, Mapping):
            raise MarginalStaticRepairHealthDecisionError(
                "marginal_static_repair_health_decision_cell_invalid"
            )
        cell_id = str(cell.get("cell_id") or "")
        if cell_id not in failure_ids:
            continue
        false_gates = sorted(str(key) for key, value in gates.items() if not value)
        if (
            cell.get("role") != "NEGATIVE_CONTROL"
            or result.get("classification") != "NEGATIVE_CONTROL_FAIL"
            or false_gates != ["negative_control_wilson_upper"]
            or cell_id in failed
        ):
            raise MarginalStaticRepairHealthDecisionError(
                "marginal_static_repair_health_decision_failed_gate_invalid"
            )
        failed[cell_id] = {
            "classification": str(result["classification"]),
            "detection_rate": float(result["detection_rate"]),
            "wilson_lower_95": float(result["wilson_lower_95"]),
            "wilson_upper_95": float(result["wilson_upper_95"]),
            "failed_gate": "negative_control_wilson_upper",
        }
    return {key: failed[key] for key in sorted(failed)}


def _verify_artifact(payload: Mapping[str, Any], *, domain: str) -> None:
    supplied = str(payload.get("artifact_digest") or "")
    identity = {
        key: value for key, value in payload.items() if key != "artifact_digest"
    }
    if not _is_digest(supplied) or supplied != canonical_digest(
        identity, domain=domain
    ):
        raise MarginalStaticRepairHealthDecisionError(
            "marginal_static_repair_health_decision_parent_digest_changed"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if (
        frozen.get("task_key") != MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY
        or frozen.get("capability") != MARGINAL_STATIC_REPAIR_HEALTH_DECISION_CAPABILITY
        or frozen.get("next_consumer") != MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY
        or frozen.get("repair_health_execution_task_digest")
        != REPAIR_HEALTH_EXECUTION_TASK_DIGEST
        or frozen.get("repair_health_execution_id") != REPAIR_HEALTH_EXECUTION_ID
        or frozen.get("repair_health_execution_artifact_digest")
        != REPAIR_HEALTH_EXECUTION_ARTIFACT_DIGEST
        or frozen.get("repair_health_result_digest") != REPAIR_HEALTH_RESULT_DIGEST
        or frozen.get("repair_health_completion_digest")
        != REPAIR_HEALTH_COMPLETION_DIGEST
        or frozen.get("repair_preregistration_digest") != REPAIR_PREREGISTRATION_DIGEST
        or frozen.get("repair_inference_gate_digest") != REPAIR_INFERENCE_GATE_DIGEST
        or frozen.get("measurement_health") != "REPAIR"
        or frozen.get("decision") != "REPAIR_MEASUREMENT_SYSTEM"
        or frozen.get("decision_fact")
        != MARGINAL_STATIC_REPAIR_HEALTH_DECISION_REPAIR_FACT
        or frozen.get("failed_control_topology") != EXPECTED_FAILED_CONTROL_TOPOLOGY
        or frozen.get("instrument_limit_cell_ids") != []
        or frozen.get("decision_rule_changed") is not False
        or frozen.get("formal_replicates") != 0
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
        raise MarginalStaticRepairHealthDecisionError(
            "marginal_static_repair_health_decision_contract_invalid"
        )


def _is_digest(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)
