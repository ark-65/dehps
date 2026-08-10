from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

P2_CLOSURE_TASK_KEY = "m4-p2-synthetic-measurement-validation"
P2_CLOSURE_CAPABILITY = "m4_p2_repair_outcome_closure"
P2_CLOSURE_COMPLETION_FACT = "m4-p2-closure:COMPLETE_WITH_REPAIR_OUTCOME"
P2R_TASK_KEY = "m4-p2r-measurement-repair-validation"
P2R_EXECUTION_APPROVED_EVENT = (
    "research-contract:m4-p2r-measurement-repair-validation-execution:approved"
)
P2_CLOSURE_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-p2-repair-outcome-closure-source-v1.json"
)

RESEARCH_REQUEST_KEY = "research-m4-p2-closure-p2r-preregistration-round-136-20260810"
RESEARCH_REQUEST_ID = 468
RESEARCH_EXECUTION_ID = 389
RESEARCH_CONTEXT_FINGERPRINT = (
    "f486ec216030aeb1de38b68ebeac9543ab061b934bbfbed34b6cdc0367157016"
)

P27_TASK_KEY = "m4-p2-automatic-gate-and-report"
P27_TASK_DIGEST = "3c5a7ff11a96f4d5aec7ba5bfbc8bf7477b51b943f235170164df271495512df"
P27_EXECUTION_ID = "d0e313e2672fae3ae2d8c096d2b24ba399687e01e7654f004767866e0dfa798d"
P27_EXECUTION_DIGEST = (
    "be3507e895dcb7f3790db22553b0d6d262d5f8cd33cb769af8e167b34ed13576"
)
P27_GATE_DIGEST = "4b8a881c2d093d608d3e9c23e184034628f1440c9c0a08f868aea1028e78e3f8"
P27_REPLAY_DIGEST = "69394a8405ad7b08b147eb20f9cf198581d9a186cb4b478d50805788af7dbbb0"
P27_REPLAY_EXECUTION_ID = (
    "a7a26dc61d7d2ead4cf38fc8d36142b95c3ec5a5125d18838777f7e2fb4bc2bf"
)
P27_DECISION_FACT = "m4-p2-measurement-decision:REPAIR_MEASUREMENT_SYSTEM"

P261_FROZEN_TASK_DIGEST = (
    "80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa"
)
P261_FROZEN_FIXTURE_DIGEST = (
    "f9716c799e1e55e58585c7e9acf0730f9d05111ab6e375cfb9bea85ecbdeacc5"
)
P263_SUPERSEDING_TASK_DIGEST = (
    "85a08402a4a0c37f75ee1675f4970ef00a7a0b0992b4204251c0c2cc79324de4"
)
P263_SUPERSEDING_FIXTURE_DIGEST = (
    "53f9a4b7d92944dfd6a46d317b018bdc6b434fc69bb977d72ae6d1f177e0c73b"
)
P263_UPDATE_POLICY_DIGEST = (
    "ad58b9abcd90c5e7ee7b9892ac8c209b8033f7a50e603b58c043685b0c7d6f99"
)
P26_VALIDATION_MANIFEST_DIGEST = (
    "a4e46a434a4b2ef9fe56ed0390d58ca5a45bbad21685b81cb983f7261b3abf58"
)
P25_DECISION_POLICY_DIGEST = (
    "824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d"
)

_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/p2_repair_outcome_closure.py"
)
_CLOSURE_DOMAIN = "dehps.m4-p2.repair-outcome-closure.v1"


class P2RepairOutcomeClosureError(RuntimeError):
    pass


def load_p2_repair_outcome_closure_source_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise P2RepairOutcomeClosureError(
            f"p2_repair_outcome_closure_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-p2-repair-outcome-closure-source.v1"
        or payload.get("artifact_type") != "m4_p2_repair_outcome_closure_source"
        or payload.get("contract_key") != "M4_P2_REPAIR_OUTCOME_CLOSURE_SOURCE"
        or payload.get("research_request_key") != RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != RESEARCH_REQUEST_ID
        or payload.get("research_execution_id") != RESEARCH_EXECUTION_ID
        or payload.get("research_context_fingerprint") != RESEARCH_CONTEXT_FINGERPRINT
        or payload.get("p2_decision") != "REPAIR_MEASUREMENT_SYSTEM"
        or payload.get("p2_terminal_status") != "COMPLETE_WITH_REPAIR_OUTCOME"
        or payload.get("p2r_status") != "PENDING_VALIDATION"
        or payload.get("execution_authorized") is not False
        or payload.get("historical_results_read") is not False
        or payload.get("evidence_created") is not False
        or payload.get("promotion_gate_opened") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or len(entries) != 1
        or entries[0].get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entries[0].get("content_sha256"))
        or payload.get("source_set_digest")
        != config_digest({"source_entries": entries})
        or payload.get("artifact_digest")
        != config_digest(
            {key: value for key, value in payload.items() if key != "artifact_digest"}
        )
    ):
        raise P2RepairOutcomeClosureError("p2_repair_outcome_closure_source_invalid")
    return payload


def verify_p2_repair_outcome_closure_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    entry = contract["source_entries"][0]
    relative = str(entry["path"])
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise P2RepairOutcomeClosureError(
            f"p2_repair_outcome_closure_source_missing:{relative}"
        )
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
        raise P2RepairOutcomeClosureError(
            f"p2_repair_outcome_closure_source_modified:{relative}"
        )


def validate_p2_closure_research_contract(
    research_request: Mapping[str, Any],
    research_execution: Mapping[str, Any],
) -> Mapping[str, Any]:
    payload = research_request.get("payload")
    result = research_execution.get("result")
    preregistration = (
        payload.get("preregistration_snapshot") if isinstance(payload, dict) else None
    )
    closure = payload.get("closure_contract") if isinstance(payload, dict) else None
    if (
        research_request.get("id") != RESEARCH_REQUEST_ID
        or research_request.get("request_key") != RESEARCH_REQUEST_KEY
        or research_request.get("request_type") != "research_scheduler_request"
        or research_request.get("status") != "completed"
        or research_execution.get("id") != RESEARCH_EXECUTION_ID
        or research_execution.get("request_id") != RESEARCH_REQUEST_ID
        or research_execution.get("status") != "completed"
        or not isinstance(payload, dict)
        or payload.get("context_fingerprint") != RESEARCH_CONTEXT_FINGERPRINT
        or not isinstance(closure, dict)
        or closure.get("legal_flow_completed") is not True
        or closure.get("final_decision") != "REPAIR_MEASUREMENT_SYSTEM"
        or closure.get("terminal_status") != "COMPLETE_WITH_REPAIR_OUTCOME"
        or closure.get("p2_6_1_status") != "FROZEN_INCOMPLETE"
        or closure.get("p2_6_3_status") != "SUPERSEDING_COMPLETE"
        or closure.get("manual_override") is not False
        or closure.get("threshold_change") is not False
        or closure.get("rerun_authorized") is not False
        or not isinstance(preregistration, dict)
        or preregistration.get("node_key") != P2R_TASK_KEY
        or preregistration.get("status") != "PENDING_VALIDATION"
        or preregistration.get("execution_authorized") is not False
        or preregistration.get("evidence_created") is not False
        or preregistration.get("promotion_gate_opened") is not False
        or preregistration.get("production_action") != "none"
        or preregistration.get("seed_contract", {}).get("seed_root_sha256")
        != RESEARCH_CONTEXT_FINGERPRINT
        or not isinstance(result, dict)
        or result.get("research_contract_fingerprint") != RESEARCH_CONTEXT_FINGERPRINT
        or result.get("closure_outcome") != "COMPLETE_WITH_REPAIR_OUTCOME"
        or result.get("immutable_p2_decision") != "REPAIR_MEASUREMENT_SYSTEM"
        or result.get("p2r_status") != "PENDING_VALIDATION"
        or result.get("validation_execution_authorized") is not False
        or result.get("failed_samples_available_for_tuning") is not False
        or result.get("m4_p3_blocked") is not False
        or result.get("evidence_created") is not False
        or result.get("promotion_gate_opened") is not False
        or result.get("production_action") != "none"
    ):
        raise P2RepairOutcomeClosureError("p2_closure_research_contract_invalid")
    return payload


def build_p2_repair_outcome_closure(
    *,
    source_contract: Mapping[str, Any],
    research_request: Mapping[str, Any],
    research_execution: Mapping[str, Any],
    gate: Mapping[str, Any],
    gate_replay: Mapping[str, Any],
) -> dict[str, Any]:
    frozen = validate_p2_closure_research_contract(research_request, research_execution)
    _validate_gate(gate)
    _validate_gate_replay(gate_replay)
    preregistration = frozen["preregistration_snapshot"]
    closure = frozen["closure_contract"]
    return _artifact(
        schema_version="dehps-m4-p2-repair-outcome-closure.v1",
        artifact_type="m4_p2_repair_outcome_closure",
        body={
            "status": "COMPLETE_WITH_REPAIR_OUTCOME",
            "phase": "M4-P2",
            "p2_objective": closure["p2_objective"],
            "legal_measurement_validation_flow_completed": True,
            "final_decision": "REPAIR_MEASUREMENT_SYSTEM",
            "decision_fact": P27_DECISION_FACT,
            "health_execution": "COMPLETE",
            "health_decision": "REPAIR_MEASUREMENT_SYSTEM",
            "automatic_gate_artifact_digest": P27_GATE_DIGEST,
            "automatic_gate_execution_artifact_digest": P27_EXECUTION_DIGEST,
            "automatic_gate_replay_artifact_digest": P27_REPLAY_DIGEST,
            "automatic_gate_replay_status": "REPLAY_VERIFIED",
            "completed_stages": [
                "P2.1_SYNTHETIC_CONTRACTS_AND_NULL_GENERATOR",
                "P2.2_METRIC_KERNEL",
                "P2.3_WALK_FORWARD_PROBE_HARNESS",
                "P2.4_INJECTED_SIGNAL_CALIBRATION",
                "P2.5_RESAMPLING_AND_NEGATIVE_CONTROLS",
                "P2.6_IDENTIFIABILITY_PREFLIGHT",
                "P2.6.3_SUPERSEDING_MEASUREMENT_VALIDATION",
                "P2.7_AUTOMATIC_GATE_AND_REPLAY",
            ],
            "frozen_contracts": {
                "decision_policy_digest": P25_DECISION_POLICY_DIGEST,
                "measurement_validation_manifest_digest": P26_VALIDATION_MANIFEST_DIGEST,
                "periodic_refit_update_policy_digest": P263_UPDATE_POLICY_DIGEST,
                "p2_6_1_frozen_task_digest": P261_FROZEN_TASK_DIGEST,
                "p2_6_1_frozen_fixture_digest": P261_FROZEN_FIXTURE_DIGEST,
                "p2_6_3_superseding_task_digest": P263_SUPERSEDING_TASK_DIGEST,
                "p2_6_3_superseding_fixture_digest": P263_SUPERSEDING_FIXTURE_DIGEST,
            },
            "preserved_subphase_status": {
                "M4-P2.6.1": "FROZEN_INCOMPLETE",
                "M4-P2.6.3": "SUPERSEDING_COMPLETE",
            },
            "repair_rationale": list(gate["failed_requirements"]),
            "known_limitations": [
                "The completed validation did not satisfy every frozen practical-power, strong-power, PE2-bias, and PE2-coverage obligation.",
                "The repair outcome validates neither predictive ability nor betting advantage.",
                "P2R requires a future independent execution; this closure performs no repair validation.",
            ],
            "downstream_restrictions": {
                "p2_rerun_allowed": False,
                "frozen_artifact_mutation_allowed": False,
                "failed_p2_samples_available_for_tuning": False,
                "p2r_task_key": P2R_TASK_KEY,
                "p2r_status": "PENDING_VALIDATION",
                "p2r_execution_authorized": False,
                "p2r_seed_root_sha256": preregistration["seed_contract"][
                    "seed_root_sha256"
                ],
                "m4_p3_status": "ACTIVE",
                "m4_p3_blocked_by_p2r": False,
            },
            "research_request_key": RESEARCH_REQUEST_KEY,
            "research_request_id": RESEARCH_REQUEST_ID,
            "research_execution_id": RESEARCH_EXECUTION_ID,
            "research_context_fingerprint": RESEARCH_CONTEXT_FINGERPRINT,
            "manual_override_used": False,
            "threshold_changed": False,
            "formal_replicates_executed": 0,
            "samples_generated": 0,
            "historical_database_reads": 0,
            "historical_predictions_read": 0,
            "historical_results_read": 0,
            "historical_folds_read": 0,
            "statistical_result_payloads_read": 0,
            "artifacts_mutated": 0,
            "evidence_created": False,
            "evidence_progress_increment": 0,
            "promotion_gate_opened": False,
            "production_action": "none",
            "completion_fact": P2_CLOSURE_COMPLETION_FACT,
            "next_consumer": P2R_TASK_KEY,
        },
        parent_digests=(
            str(source_contract["artifact_digest"]),
            RESEARCH_CONTEXT_FINGERPRINT,
            P27_EXECUTION_DIGEST,
            P27_GATE_DIGEST,
            P27_REPLAY_DIGEST,
            P261_FROZEN_FIXTURE_DIGEST,
            P263_SUPERSEDING_FIXTURE_DIGEST,
        ),
    )


def replay_p2_repair_outcome_closure(
    *,
    closure_artifact: Mapping[str, Any],
    source_contract: Mapping[str, Any],
    research_request: Mapping[str, Any],
    research_execution: Mapping[str, Any],
    gate: Mapping[str, Any],
    gate_replay: Mapping[str, Any],
) -> dict[str, Any]:
    rebuilt = build_p2_repair_outcome_closure(
        source_contract=source_contract,
        research_request=research_request,
        research_execution=research_execution,
        gate=gate,
        gate_replay=gate_replay,
    )
    if dict(closure_artifact) != rebuilt:
        raise P2RepairOutcomeClosureError("p2_closure_replay_identity_changed")
    return {
        "status": "REPLAY_VERIFIED",
        "closure_artifact_digest": rebuilt["artifact_digest"],
        "decision": rebuilt["final_decision"],
        "p2_status": rebuilt["status"],
        "p2r_status": rebuilt["downstream_restrictions"]["p2r_status"],
        "m4_p3_blocked": False,
        "compute_executed": False,
        "historical_database_reads": 0,
        "artifacts_mutated": 0,
        "evidence_created": False,
        "promotion_gate_opened": False,
        "production_action": "none",
    }


def _validate_gate(gate: Mapping[str, Any]) -> None:
    identity = dict(gate)
    supplied = identity.pop("artifact_digest", None)
    expected = canonical_digest(
        identity, domain="dehps.m4-p2.automatic-measurement-gate.v1"
    )
    if (
        supplied != expected
        or supplied != P27_GATE_DIGEST
        or gate.get("artifact_type") != "automatic_measurement_gate"
        or gate.get("decision") != "REPAIR_MEASUREMENT_SYSTEM"
        or gate.get("decision_fact") != P27_DECISION_FACT
        or gate.get("P3_reachable") is not False
        or gate.get("repair_reachable") is not True
        or gate.get("manual_override_used") is not False
        or gate.get("failed_requirements")
        != [
            "all_practical_strength_cell_power_gates_pass",
            "all_strong_signal_cell_power_gates_pass",
            "all_primary_PE2_absolute_bias_cell_gates_pass",
            "all_primary_PE2_coverage_cell_gates_pass",
        ]
    ):
        raise P2RepairOutcomeClosureError("p2_closure_gate_identity_changed")


def _validate_gate_replay(gate_replay: Mapping[str, Any]) -> None:
    identity = dict(gate_replay)
    supplied = identity.pop("artifact_digest", None)
    expected = canonical_digest(
        identity, domain="dehps.m4.p27-measurement-gate-replay-artifact.v1"
    )
    if (
        supplied != expected
        or supplied != P27_REPLAY_DIGEST
        or gate_replay.get("artifact_type") != "P27MeasurementGateReplayArtifact"
        or gate_replay.get("status") != "REPLAY_VERIFIED"
        or gate_replay.get("task_key") != P27_TASK_KEY
        or gate_replay.get("task_digest") != P27_TASK_DIGEST
        or gate_replay.get("execution_id") != P27_EXECUTION_ID
        or gate_replay.get("execution_artifact_digest") != P27_EXECUTION_DIGEST
        or gate_replay.get("automatic_gate_digest") != P27_GATE_DIGEST
        or gate_replay.get("decision") != "REPAIR_MEASUREMENT_SYSTEM"
        or gate_replay.get("decision_fact") != P27_DECISION_FACT
        or gate_replay.get("same_execution_identity") is not True
        or gate_replay.get("same_artifact_identity") is not True
        or gate_replay.get("manual_input_assembly") is not False
    ):
        raise P2RepairOutcomeClosureError("p2_closure_gate_replay_identity_changed")


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "artifact_digest": "",
        **dict(body),
        "parent_digests": list(parent_digests),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=_CLOSURE_DOMAIN)
    return payload


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
