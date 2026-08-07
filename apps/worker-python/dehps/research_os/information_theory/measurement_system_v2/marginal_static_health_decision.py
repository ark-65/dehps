from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

MARGINAL_STATIC_HEALTH_DECISION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-health-decision"
)
MARGINAL_STATIC_HEALTH_DECISION_CAPABILITY = (
    "m4_v2_marginal_static_measurement_health_decision"
)
MARGINAL_STATIC_HEALTH_DECISION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-v2-marginal-static-health-decision-source-v1.json"
)
MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-design"
)
MARGINAL_STATIC_HISTORICAL_MEASUREMENT_TASK_KEY = (
    "m4-v2-marginal-static-historical-measurement"
)
MARGINAL_STATIC_HEALTH_DECISION_REPAIR_FACT = (
    "m4-v2-marginal-static-measurement-health-decision:REPAIR"
)
MARGINAL_STATIC_HEALTH_DECISION_PASS_FACT = (
    "m4-v2-marginal-static-measurement-health-decision:PASS"
)
MARGINAL_STATIC_HEALTH_DECISION_INCONCLUSIVE_FACT = (
    "m4-v2-marginal-static-measurement-health-decision:INCONCLUSIVE"
)

MEASUREMENT_CONTRACT_V2_DIGEST = (
    "a0a367c99d7646cadc162bd9ceb0d5d73481cd7c26656bf02b40a99d9180095b"
)
HEALTH_EXECUTION_TASK_KEY = "m4-v2-marginal-static-measurement-health-execution"
HEALTH_EXECUTION_TASK_DIGEST = (
    "92b38644e97517394be856d7753de1adf7b21d00b0be707a4bbcc02cde03bc7e"
)
HEALTH_EXECUTION_ID = "cd93e7d08535cbfe0046923d2b3eb90acff367897c4122805fe25cf7fa86baa1"
HEALTH_EXECUTION_ARTIFACT_DIGEST = (
    "89cb006231ae0956e70cee67050f0be090eb87c2441b4100d8c86a6cf646233b"
)
HEALTH_RESULT_DIGEST = (
    "40b449a7abe4ac9fff6eb0e98212f5809e0f0ff76c93f1344b673b4716905e2d"
)
HEALTH_COMPLETION_DIGEST = (
    "e77c35c68b6043875c54c1bb06d2c64a70730c026950fe7c813efcfe54d5f8d3"
)
HEALTH_EXECUTION_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-health-execution:COMPLETE"
)

EXPECTED_FAILED_GATE_MAP = {
    "BASE:V2_M1_GROUP_ODDS_2_STATIONARY:FORWARD_61": (
        "bias",
        "coverage",
        "positive_power",
    ),
    "LOCAL_M1:0.010:FORWARD_61": (
        "bias",
        "coverage",
        "practical_power",
    ),
    "LOCAL_M1:0.010:HISTORICAL_2581": ("practical_power",),
    "LOCAL_M1:0.050:FORWARD_61": ("bias", "strong_power"),
}

_DECISION_BY_HEALTH = {
    "PASS": (
        "PASS_TO_HISTORICAL_MEASUREMENT",
        MARGINAL_STATIC_HEALTH_DECISION_PASS_FACT,
        True,
        MARGINAL_STATIC_HISTORICAL_MEASUREMENT_TASK_KEY,
    ),
    "REPAIR": (
        "REPAIR_MEASUREMENT_SYSTEM",
        MARGINAL_STATIC_HEALTH_DECISION_REPAIR_FACT,
        False,
        MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY,
    ),
    "INCONCLUSIVE": (
        "HOLD_INCONCLUSIVE",
        MARGINAL_STATIC_HEALTH_DECISION_INCONCLUSIVE_FACT,
        False,
        MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY,
    ),
}


class MarginalStaticHealthDecisionError(RuntimeError):
    pass


def load_marginal_static_health_decision_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticHealthDecisionError(
            f"marginal_static_health_decision_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-health-decision-source.v1"
        or payload.get("artifact_type")
        != "m4_v2_marginal_static_health_decision_source"
        or payload.get("contract_key") != "M4_V2_MARGINAL_STATIC_HEALTH_DECISION_SOURCE"
        or payload.get("research_request_key")
        != "research-m4-v2-marginal-static-health-decision-round-43-20260808"
        or payload.get("research_request_id") != 331
        or payload.get("research_execution_id") != 252
        or payload.get("engineering_request_key")
        != "engineering-m4-v2-marginal-static-health-decision-round-43-20260808"
        or payload.get("engineering_request_id") != 332
        or payload.get("result_aware") is not True
        or payload.get("formal_replicates_executed") != 0
        or payload.get("generated_issues") != 0
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
            domain="dehps.m4.v2.marginal-static-health-decision-source-set.v1",
        )
    ):
        raise MarginalStaticHealthDecisionError(
            "marginal_static_health_decision_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path")
        != (
            "apps/worker-python/dehps/research_os/information_theory/"
            "measurement_system_v2/marginal_static_health_decision.py"
        )
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise MarginalStaticHealthDecisionError(
            "marginal_static_health_decision_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_marginal_static_health_decision_source_bytes(
    *,
    root_dir: Path,
    contract: Mapping[str, Any],
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MarginalStaticHealthDecisionError(
                f"marginal_static_health_decision_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise MarginalStaticHealthDecisionError(
                f"marginal_static_health_decision_source_modified:{relative}"
            )


def health_decision_mapping(
    measurement_health: str,
) -> tuple[str, str, bool, str]:
    try:
        return _DECISION_BY_HEALTH[measurement_health]
    except KeyError as exc:
        raise MarginalStaticHealthDecisionError(
            "marginal_static_health_decision_unrecognized_health"
        ) from exc


def build_marginal_static_health_decision(
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
    failed_gate_map = _failed_gate_map(health_result)
    measurement_health = str(health_result["measurement_health"])
    decision, decision_fact, historical_eligible, next_consumer = (
        health_decision_mapping(measurement_health)
    )
    payload: dict[str, Any] = {
        "schema_version": (
            "dehps-m4-v2-marginal-static-measurement-health-decision.v1"
        ),
        "artifact_type": "m4_v2_marginal_static_measurement_health_decision",
        "artifact_digest": "",
        "status": "COMPLETE",
        "branch_id": "MARGINAL_STATIC",
        "measurement_contract_v2_digest": MEASUREMENT_CONTRACT_V2_DIGEST,
        "source_contract_digest": source_contract["artifact_digest"],
        "health_execution_id": health_execution["execution_id"],
        "health_execution_artifact_digest": health_execution["artifact_digest"],
        "health_result_digest": health_result["artifact_digest"],
        "health_completion_digest": health_completion["artifact_digest"],
        "measurement_health": measurement_health,
        "decision": decision,
        "decision_fact": decision_fact,
        "failed_cell_ids": list(failed_gate_map),
        "failed_gate_map": {
            key: list(values) for key, values in failed_gate_map.items()
        },
        "failed_cell_count": len(failed_gate_map),
        "passed_cell_count": int(health_result["cell_count"]) - len(failed_gate_map),
        "eligible_for_historical_measurement": historical_eligible,
        "accepted_model_artifact_digest": None,
        "historical_evidence": "NOT_RUN",
        "historical_execution_status": "NOT_AUTHORIZED",
        "formal_replicates_executed": 0,
        "generated_issues": 0,
        "compact_index_reads": 0,
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
            MEASUREMENT_CONTRACT_V2_DIGEST,
            str(health_execution["artifact_digest"]),
            str(health_result["artifact_digest"]),
            str(health_completion["artifact_digest"]),
        ],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.v2.marginal-static-measurement-health-decision.v1",
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
        domain="dehps.m4.v2.marginal-static-measurement-health-result.v1",
    )
    _verify_artifact(
        health_completion,
        domain="dehps.m4.v2.marginal-static-health-execution-completion.v1",
    )
    if (
        health_execution.get("artifact_type") != "research_os_mainline_execution"
        or health_execution.get("artifact_digest") != HEALTH_EXECUTION_ARTIFACT_DIGEST
        or health_execution.get("execution_id") != HEALTH_EXECUTION_ID
        or health_execution.get("task_key") != HEALTH_EXECUTION_TASK_KEY
        or health_execution.get("task_digest") != HEALTH_EXECUTION_TASK_DIGEST
        or health_execution.get("status") != "COMPLETE"
        or health_execution.get("completion_classification") != "VALIDATED_IN_MAINLINE"
        or health_execution.get("completion_fact") != HEALTH_EXECUTION_COMPLETION_FACT
        or health_execution.get("marginal_static_health_result_digest")
        != HEALTH_RESULT_DIGEST
        or health_execution.get("marginal_static_health_execution_completion_digest")
        != HEALTH_COMPLETION_DIGEST
        or health_execution.get("measurement_health") != "REPAIR"
        or health_execution.get("historical_outcomes_read") is not False
        or health_execution.get("evidence_created") is not False
        or health_execution.get("production_action") != "none"
        or health_result.get("artifact_type")
        != "m4_v2_marginal_static_measurement_health_result"
        or health_result.get("artifact_digest") != HEALTH_RESULT_DIGEST
        or health_result.get("status") != "COMPLETE"
        or health_result.get("measurement_health") != "REPAIR"
        or health_result.get("branch_id") != "MARGINAL_STATIC"
        or health_result.get("cell_count") != 14
        or health_result.get("replicate_count") != 7_168
        or health_result.get("all_legal") is not True
        or health_result.get("all_finite") is not True
        or health_result.get("all_cells_complete") is not True
        or health_result.get("manual_or_partial_override") is not False
        or health_result.get("accepted_model_artifact_digest") is not None
        or health_result.get("historical_execution_status") != "NOT_AUTHORIZED"
        or health_result.get("historical_outcomes_read") is not False
        or health_result.get("statistical_results_read") is not False
        or health_result.get("evidence_created") is not False
        or health_result.get("production_action") != "none"
        or health_completion.get("artifact_type")
        != "m4_v2_marginal_static_health_execution_completion"
        or health_completion.get("artifact_digest") != HEALTH_COMPLETION_DIGEST
        or health_completion.get("status") != "COMPLETE"
        or health_completion.get("execution_id") != HEALTH_EXECUTION_ID
        or health_completion.get("measurement_health") != "REPAIR"
        or health_completion.get("health_result_digest") != HEALTH_RESULT_DIGEST
        or health_completion.get("completion_fact") != HEALTH_EXECUTION_COMPLETION_FACT
        or health_completion.get("accepted_model_artifact_digest") is not None
        or health_completion.get("historical_outcomes_read") is not False
        or health_completion.get("evidence_created") is not False
        or health_completion.get("production_action") != "none"
    ):
        raise MarginalStaticHealthDecisionError(
            "marginal_static_health_decision_parent_identity_changed"
        )
    if _failed_gate_map(health_result) != EXPECTED_FAILED_GATE_MAP:
        raise MarginalStaticHealthDecisionError(
            "marginal_static_health_decision_failed_topology_changed"
        )


def _failed_gate_map(
    health_result: Mapping[str, Any],
) -> dict[str, tuple[str, ...]]:
    cells = health_result.get("cell_results")
    if not isinstance(cells, list):
        raise MarginalStaticHealthDecisionError(
            "marginal_static_health_decision_cells_invalid"
        )
    failed: dict[str, tuple[str, ...]] = {}
    for result in cells:
        if not isinstance(result, Mapping) or result.get("status") != "FAIL":
            continue
        cell = result.get("cell")
        gates = result.get("gates")
        if not isinstance(cell, Mapping) or not isinstance(gates, Mapping):
            raise MarginalStaticHealthDecisionError(
                "marginal_static_health_decision_cell_invalid"
            )
        cell_id = str(cell.get("cell_id") or "")
        failed_gates = tuple(
            sorted(str(key) for key, value in gates.items() if not value)
        )
        if not cell_id or not failed_gates or cell_id in failed:
            raise MarginalStaticHealthDecisionError(
                "marginal_static_health_decision_failed_gate_invalid"
            )
        failed[cell_id] = failed_gates
    return failed


def _verify_artifact(payload: Mapping[str, Any], *, domain: str) -> None:
    supplied = str(payload.get("artifact_digest") or "")
    identity = {
        key: value for key, value in payload.items() if key != "artifact_digest"
    }
    if not _is_digest(supplied) or supplied != canonical_digest(
        identity, domain=domain
    ):
        raise MarginalStaticHealthDecisionError(
            "marginal_static_health_decision_parent_digest_changed"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    expected_failed_gate_map = {
        key: list(values) for key, values in EXPECTED_FAILED_GATE_MAP.items()
    }
    if (
        frozen.get("task_key") != MARGINAL_STATIC_HEALTH_DECISION_TASK_KEY
        or frozen.get("capability") != MARGINAL_STATIC_HEALTH_DECISION_CAPABILITY
        or frozen.get("next_consumer") != MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY
        or frozen.get("measurement_contract_v2_digest")
        != MEASUREMENT_CONTRACT_V2_DIGEST
        or frozen.get("health_execution_task_digest") != HEALTH_EXECUTION_TASK_DIGEST
        or frozen.get("health_execution_id") != HEALTH_EXECUTION_ID
        or frozen.get("health_execution_artifact_digest")
        != HEALTH_EXECUTION_ARTIFACT_DIGEST
        or frozen.get("health_result_digest") != HEALTH_RESULT_DIGEST
        or frozen.get("health_completion_digest") != HEALTH_COMPLETION_DIGEST
        or frozen.get("measurement_health") != "REPAIR"
        or frozen.get("decision") != "REPAIR_MEASUREMENT_SYSTEM"
        or frozen.get("decision_fact") != MARGINAL_STATIC_HEALTH_DECISION_REPAIR_FACT
        or frozen.get("failed_gate_map") != expected_failed_gate_map
        or frozen.get("decision_rule_changed") is not False
        or frozen.get("formal_replicates") != 0
        or frozen.get("generated_issues") != 0
        or frozen.get("compact_index_reads") != 0
        or frozen.get("sentinel_replicates_recomputed") != 0
        or frozen.get("duplicate_validation") != "forbidden"
        or frozen.get("historical_outcomes_read") is not False
        or frozen.get("evidence_created") is not False
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("production_action") != "none"
    ):
        raise MarginalStaticHealthDecisionError(
            "marginal_static_health_decision_contract_invalid"
        )


def _is_digest(value: object) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)
