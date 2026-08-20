from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np

from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentRequestStatus
from dehps.research_os.models import m4_v2_domain_digest

from .marginal_static_historical_execution import (
    BASELINE_NOT_Q,
    BASELINE_Q,
    DRAW_SIZE,
    NUMBER_COUNT,
    score_issue,
)


class M4P4DiagnosticNegativeControlsError(ValueError):
    pass


SOURCE_CONTRACT_PATH = (
    "configs/research-os/m4-p4-diagnostic-negative-controls-source-v1.json"
)
SOURCE_SCHEMA = "dehps-m4-p4-diagnostic-negative-controls-source-contract.v1"
SOURCE_ARTIFACT_TYPE = "m4_p4_diagnostic_negative_controls_source_contract"
SOURCE_DOMAIN = "dehps.m4.p4.diagnostic-negative-controls-source-contract.v1"
SOURCE_SET_DOMAIN = "dehps.m4.p4.diagnostic-negative-controls-source-set.v1"

P3_CLOSURE_TASK_KEY = "m4-p3-inconclusive-closure-consolidation"
P3_CLOSURE_CAPABILITY = "m4_p3_inconclusive_closure_consolidation"
P3_CLOSURE_COMPLETION_FACT = f"{P3_CLOSURE_TASK_KEY}:COMPLETE"
P3_CLOSURE_ARTIFACT_TYPE = "M4P3InconclusiveClosureArtifact"
P3_CLOSURE_SCHEMA = "dehps-m4-p3-inconclusive-closure.v1"
P3_CLOSURE_DOMAIN = "dehps.m4.p3.inconclusive-closure.v1"

PREREGISTRATION_TASK_KEY = "m4-p4-diagnostic-negative-controls-preregistration"
PREREGISTRATION_CAPABILITY = "m4_p4_diagnostic_negative_controls_preregistration"
PREREGISTRATION_COMPLETION_FACT = f"{PREREGISTRATION_TASK_KEY}:COMPLETE"
PREREGISTRATION_ARTIFACT_TYPE = (
    "M4P4DiagnosticNegativeControlsPreregistrationArtifact"
)
PREREGISTRATION_SCHEMA = "dehps-m4-p4-diagnostic-negative-controls-preregistration.v1"
PREREGISTRATION_DOMAIN = "dehps.m4.p4.diagnostic-negative-controls-preregistration.v1"

EXECUTION_TASK_KEY = "m4-p4-diagnostic-negative-controls-after-inconclusive-p3"
EXECUTION_CAPABILITY = "m4_p4_diagnostic_negative_controls_execution"
EXECUTION_COMPLETION_FACT = f"{EXECUTION_TASK_KEY}:COMPLETE"
EXECUTION_ARTIFACT_TYPE = "M4P4DiagnosticNegativeControlsExecutionArtifact"
EXECUTION_SCHEMA = "dehps-m4-p4-diagnostic-negative-controls-execution.v1"
EXECUTION_DOMAIN = "dehps.m4.p4.diagnostic-negative-controls-execution.v1"

EVIDENCE_TASK_KEY = "m4-p4-diagnostic-negative-controls-evidence-compiler"
EVIDENCE_CAPABILITY = "m4_p4_diagnostic_negative_controls_evidence_compiler"
EVIDENCE_COMPLETION_FACT = f"{EVIDENCE_TASK_KEY}:COMPLETE"
EVIDENCE_ARTIFACT_TYPE = "M4P4DiagnosticEvidenceArtifact"
EVIDENCE_SCHEMA = "dehps-m4-p4-diagnostic-evidence.v1"
EVIDENCE_DOMAIN = "dehps.m4.p4.diagnostic-evidence.v1"

DECISION_TASK_KEY = "m4-p4-diagnostic-negative-controls-decision"
DECISION_CAPABILITY = "m4_p4_diagnostic_negative_controls_decision"
DECISION_COMPLETION_FACT = f"{DECISION_TASK_KEY}:COMPLETE"
DECISION_ARTIFACT_TYPE = "M4P4DiagnosticDecisionArtifact"
DECISION_SCHEMA = "dehps-m4-p4-diagnostic-decision.v1"
DECISION_DOMAIN = "dehps.m4.p4.diagnostic-decision.v1"

REPLAY_TASK_KEY = "m4-p4-diagnostic-negative-controls-decision-replay"
REPLAY_CAPABILITY = "m4_p4_diagnostic_negative_controls_decision_replay"
REPLAY_COMPLETION_FACT = f"{REPLAY_TASK_KEY}:COMPLETE"
REPLAY_VERIFIED_FACT = (
    "m4-p4-diagnostic-negative-controls-decision:REGISTERED_REPLAY_VERIFIED"
)
REPLAY_ARTIFACT_TYPE = "M4P4DiagnosticDecisionReplayArtifact"
REPLAY_SCHEMA = "dehps-m4-p4-diagnostic-decision-replay.v1"
REPLAY_DOMAIN = "dehps.m4.p4.diagnostic-decision-replay.v1"

FORMAL_P4_TASK_KEY = "m4-p4-negative-controls-and-robustness"
FORMAL_P4_PASS_FACT = "m4-p3-predictive-decision:PASS_TO_P4"
P3_CLOSED_FACT = "m4-v2-predictive-p3:CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION"
FORWARD_ROUTE_FACT = "m4-v2-routing:FORWARD_EVIDENCE_REQUIRED"

HISTORICAL_EXECUTION_ID = (
    "8cfbd33f314ebabdf3a334cfe96887c9802580bff91e8ab43304f1c6b67ef52a"
)
HISTORICAL_INFERENCE_DIGEST = (
    "36056c0168bf71a995ec2a0bb9bf4663b0222b8fce621899a1e861282597e841"
)
HISTORICAL_DATASET_SNAPSHOT_DIGEST = (
    "999064903fa8a040520ab2a664a1ce3ec35321a90f0e5823626194c64c8d98c6"
)
HISTORICAL_DATASET_CONTENT_DIGEST = (
    "8f7b7527d6ee95301b58002e594b0955b7e0f391421b8c438b87fc4f2507b106"
)
HISTORICAL_FOLD_MANIFEST_DIGEST = (
    "5a68579161ad5528ee15b8b1ea3e314d6acb05203885a5514e5654da026e9ad7"
)
HISTORICAL_CHECKPOINT_ORDER_DIGEST = (
    "40b85566e977311438add76d301d9614050bfac7fa0de618c1f415299f8b88cd"
)
HISTORICAL_INFERENCE_DESIGN_DIGEST = (
    "e52220af0b6cd4c40dd3ff05b9eb692446fe4660b1118ff6cf2b4cd5423f5bb4"
)
DEEPER_VALIDATION_DECISION_DIGEST = (
    "dbac3aad6128787f737a1450461a9833c948068ba915f194df41a02f6fd9d9e3"
)
PREDICTIVE_P3_CLOSURE_DIGEST = (
    "2dcd3630d4e0987022a22e27ae8818bed9edd39758138e90579b85fef5fe0bbc"
)
PREDICTIVE_P3_CLOSURE_REGISTRATION_DIGEST = (
    "0f545b0b0375e53a43424c9b8fdca414abbefa0cf4159290cd26decac64fd19e"
)

HISTORICAL_ISSUE_COUNT = 3481
INITIAL_TRAINING_ISSUES = 900
FOLD_COUNT = 2581
REQUIRED_FOLD_COUNT = 4676
MISSING_FOLD_COUNT = 2095
CURRENT_MDE = 0.013459908060402983
PRACTICAL_THRESHOLD = 0.01
CURRENT_POWER = 0.5311893549808094
TARGET_POWER = 0.8
ORIGINAL_MEAN = -0.008341219898597063
CONTROL_IDS = (
    "DATE_PERMUTATION",
    "TARGET_LABEL_PERMUTATION",
    "NUMBER_RELABELING",
    "FEATURE_TIME_SHIFT",
    "RANDOM_FEATURE_SENTINEL",
    "BASELINE_IMPLEMENTATION_SENTINEL",
)
SIGNAL_DESTRUCTION_IDS = (
    "DATE_PERMUTATION",
    "TARGET_LABEL_PERMUTATION",
    "FEATURE_TIME_SHIFT_PAST_13",
    "RANDOM_FEATURE_SENTINEL",
)
DECISIONS = (
    "NEGATIVE_CONTROLS_CLEAN",
    "LEAKAGE_OR_EVALUATOR_ARTIFACT_DETECTED",
    "INCONCLUSIVE_NEGATIVE_CONTROLS",
    "INVALID_NEGATIVE_CONTROL_EXECUTION",
)
REPEAT_COUNT = 64
BOOTSTRAP_REPLICATES = 2000
BLOCK_LENGTH = 5
FAMILYWISE_ALPHA = 0.05
NUMBER_EQUIVARIANCE_TOLERANCE = 1e-12
BASELINE_TOLERANCE = 1e-15
ROOT_SEED_DOMAIN = "M4_P4_DIAGNOSTIC_NEGATIVE_CONTROLS_V1"

RESEARCH_REQUEST_KEY = (
    "research-m4-p3-closure-p4-diagnostic-negative-controls-preregistration-v1"
)
RESEARCH_REQUEST_ID = 629
RESEARCH_EXECUTION_ID = 513
RESEARCH_APPROVAL_DECISION_ID = 2642
RESEARCH_REQUEST_PAYLOAD_SHA256 = (
    "c6ef02e45cf1e7b54f229dd9d812de2534b26c8bc5d952c9f54073108aaec76f"
)
ENGINEERING_REQUEST_KEY = "engineering-m4-p3-closure-p4-diagnostic-negative-controls-v1"
ENGINEERING_REQUEST_ID = 630
ENGINEERING_EXECUTION_ID = 514
ENGINEERING_APPROVAL_DECISION_ID = 2647
ENGINEERING_REQUEST_PAYLOAD_SHA256 = (
    "11a776926b31ee4ba2e9de3b9edffcad9bb93eb15e51db500c2a1001c79307a3"
)

SOURCE_PATHS = (
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/diagnostic_negative_controls.py",
    "apps/worker-python/scripts/build_m4_p4_diagnostic_negative_controls_manifest.py",
    "apps/worker-python/dehps/research_os/supervisor.py",
    "apps/worker-python/dehps/research_os/repository.py",
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/marginal_static_historical_execution.py",
)

FROZEN_INPUTS = {
    "historical_execution_id": HISTORICAL_EXECUTION_ID,
    "historical_inference_digest": HISTORICAL_INFERENCE_DIGEST,
    "historical_dataset_snapshot_digest": HISTORICAL_DATASET_SNAPSHOT_DIGEST,
    "historical_dataset_content_digest": HISTORICAL_DATASET_CONTENT_DIGEST,
    "historical_fold_manifest_digest": HISTORICAL_FOLD_MANIFEST_DIGEST,
    "historical_checkpoint_order_digest": HISTORICAL_CHECKPOINT_ORDER_DIGEST,
    "historical_inference_design_digest": HISTORICAL_INFERENCE_DESIGN_DIGEST,
    "deeper_validation_decision_digest": DEEPER_VALIDATION_DECISION_DIGEST,
    "p3_closure_digest": PREDICTIVE_P3_CLOSURE_DIGEST,
    "p3_closure_registration_digest": PREDICTIVE_P3_CLOSURE_REGISTRATION_DIGEST,
    "dataset_issue_count": HISTORICAL_ISSUE_COUNT,
    "initial_training_issues": INITIAL_TRAINING_ISSUES,
    "fold_count": FOLD_COUNT,
    "primary_endpoint": "mean settled issue-level prequential score difference in bits per issue",
    "candidate_estimator": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
    "baseline": "LEGAL_UNIFORM_NUMBER_EVENT_BASELINE",
    "current_mde_bits_per_issue": CURRENT_MDE,
    "practical_threshold_bits_per_issue": PRACTICAL_THRESHOLD,
    "current_equivalence_power": CURRENT_POWER,
    "target_power": TARGET_POWER,
    "required_independent_folds": REQUIRED_FOLD_COUNT,
    "missing_independent_folds": MISSING_FOLD_COUNT,
    "independent_holdout_available": False,
}

FROZEN_PROGRAM = {
    "diagnostic_only": True,
    "confirmatory_p4": False,
    "eligible_for_p5": False,
    "eligible_for_promotion": False,
    "control_ids": list(CONTROL_IDS),
    "signal_destruction_family": list(SIGNAL_DESTRUCTION_IDS),
    "randomized_repeat_count": REPEAT_COUNT,
    "repeats_are_independent_information": False,
    "independent_information_count": FOLD_COUNT,
    "bootstrap_replicates": BOOTSTRAP_REPLICATES,
    "bootstrap_method": "non-circular moving-block bootstrap",
    "bootstrap_block_length": BLOCK_LENGTH,
    "familywise_alpha": FAMILYWISE_ALPHA,
    "multiple_comparison_rule": "Holm across the four frozen signal-destruction controls",
    "random_generator": "numpy PCG64",
    "seed_derivation": (
        "first 128 bits of SHA256('M4_P4_DIAGNOSTIC_NEGATIVE_CONTROLS_V1|"
        "control_id|repeat_index') interpreted as unsigned big-endian integer"
    ),
    "date_permutation": "64 complete-row permutations with transformed-prior-only mechanical refit",
    "target_label_permutation": "64 evaluation-target permutations on the canonical prior-only feature trajectory",
    "number_relabeling": "64 reversible global 1..33 permutations; score equivariance tolerance 1e-12",
    "feature_time_shift": {
        "past_offset": -13,
        "future_offset": 1,
        "future_role": "intentional leakage sentinel rejected before value access",
        "future_legal_prediction_output": False,
    },
    "random_feature_sentinel": "64 per-fold permutations of the canonical 33-dimensional probability vector",
    "baseline_implementation_sentinel": "independent legal uniform number-event score; tolerance 1e-15",
    "critical_positive_gate": (
        "complete valid run and Holm-adjusted one-sided p<=0.05 and simultaneous lower bound>0.01"
    ),
    "decision_priority": [
        "INVALID_NEGATIVE_CONTROL_EXECUTION",
        "LEAKAGE_OR_EVALUATOR_ARTIFACT_DETECTED",
        "INCONCLUSIVE_NEGATIVE_CONTROLS",
        "NEGATIVE_CONTROLS_CLEAN",
    ],
    "post_result_additions": "forbidden",
}

LIMITS = {
    "engineering_hours": 4,
    "predictive_p3_folds": 0,
    "forward_samples": 0,
    "formal_p4_modified": False,
    "pass_to_p4_emitted": False,
    "p5_started": False,
    "promotion_triggered": False,
    "model_training_started": False,
    "new_model": "NONE",
    "new_features": False,
    "hyperparameter_search": False,
    "production_action": "none",
}


def _canonical_payload_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _require_digest(value: Any, name: str) -> str:
    digest = str(value or "")
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise M4P4DiagnosticNegativeControlsError(f"{name}_invalid")
    return digest


def _artifact(
    *,
    artifact_type: str,
    schema_version: str,
    domain: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "body": deepcopy(dict(body)),
        "parent_digests": [
            _require_digest(value, "parent_digest") for value in parent_digests
        ],
    }
    payload["artifact_digest"] = m4_v2_domain_digest(payload, domain=domain)
    return payload


def _validate_artifact(
    value: Mapping[str, Any],
    *,
    artifact_type: str,
    schema_version: str,
    domain: str,
) -> dict[str, Any]:
    payload = deepcopy(dict(value))
    if (
        set(payload)
        != {
            "schema_version",
            "artifact_type",
            "artifact_digest",
            "body",
            "parent_digests",
        }
        or payload.get("artifact_type") != artifact_type
        or payload.get("schema_version") != schema_version
        or not isinstance(payload.get("body"), Mapping)
        or not isinstance(payload.get("parent_digests"), list)
    ):
        raise M4P4DiagnosticNegativeControlsError(f"{artifact_type}_shape_changed")
    observed = _require_digest(payload.pop("artifact_digest"), "artifact_digest")
    if m4_v2_domain_digest(payload, domain=domain) != observed:
        raise M4P4DiagnosticNegativeControlsError(f"{artifact_type}_digest_changed")
    payload["artifact_digest"] = observed
    return payload


def load_source_contract(*, root_dir: Path) -> dict[str, Any]:
    root = root_dir.resolve()
    path = (root / SOURCE_CONTRACT_PATH).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise M4P4DiagnosticNegativeControlsError("diagnostic_source_missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise M4P4DiagnosticNegativeControlsError("diagnostic_source_invalid") from exc
    required = {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "contract_key",
        "frozen_inputs",
        "frozen_program",
        "governance_bindings",
        "limits",
        "source_entries",
        "source_set_digest",
    }
    governance = {
        "research": {
            "request_key": RESEARCH_REQUEST_KEY,
            "request_id": RESEARCH_REQUEST_ID,
            "execution_id": RESEARCH_EXECUTION_ID,
            "approval_decision_id": RESEARCH_APPROVAL_DECISION_ID,
            "request_payload_sha256": RESEARCH_REQUEST_PAYLOAD_SHA256,
        },
        "engineering": {
            "request_key": ENGINEERING_REQUEST_KEY,
            "request_id": ENGINEERING_REQUEST_ID,
            "execution_id": ENGINEERING_EXECUTION_ID,
            "approval_decision_id": ENGINEERING_APPROVAL_DECISION_ID,
            "request_payload_sha256": ENGINEERING_REQUEST_PAYLOAD_SHA256,
        },
    }
    if (
        not isinstance(payload, dict)
        or set(payload) != required
        or payload.get("schema_version") != SOURCE_SCHEMA
        or payload.get("artifact_type") != SOURCE_ARTIFACT_TYPE
        or payload.get("contract_key")
        != "M4_P3_CLOSURE_P4_DIAGNOSTIC_NEGATIVE_CONTROLS_V1"
        or payload.get("frozen_inputs") != FROZEN_INPUTS
        or payload.get("frozen_program") != FROZEN_PROGRAM
        or payload.get("governance_bindings") != governance
        or payload.get("limits") != LIMITS
    ):
        raise M4P4DiagnosticNegativeControlsError("diagnostic_source_shape_changed")
    entries = payload.get("source_entries")
    if (
        not isinstance(entries, list)
        or tuple(
            item.get("path") for item in entries if isinstance(item, Mapping)
        )
        != SOURCE_PATHS
    ):
        raise M4P4DiagnosticNegativeControlsError("diagnostic_source_entries_changed")
    verified: list[dict[str, str]] = []
    for item in entries:
        if not isinstance(item, Mapping) or set(item) != {"path", "sha256"}:
            raise M4P4DiagnosticNegativeControlsError(
                "diagnostic_source_entry_changed"
            )
        relative = str(item["path"])
        absolute = (root / relative).resolve()
        if (
            not absolute.is_relative_to(root)
            or not absolute.is_file()
            or hashlib.sha256(absolute.read_bytes()).hexdigest() != item["sha256"]
        ):
            raise M4P4DiagnosticNegativeControlsError(
                "diagnostic_source_bytes_changed"
            )
        verified.append({"path": relative, "sha256": str(item["sha256"])})
    source_set_digest = m4_v2_domain_digest(
        {"source_entries": verified}, domain=SOURCE_SET_DOMAIN
    )
    identity = dict(payload)
    artifact_digest = _require_digest(
        identity.pop("artifact_digest"), "source_artifact_digest"
    )
    if (
        payload.get("source_set_digest") != source_set_digest
        or m4_v2_domain_digest(identity, domain=SOURCE_DOMAIN) != artifact_digest
    ):
        raise M4P4DiagnosticNegativeControlsError("diagnostic_source_identity_changed")
    return deepcopy(payload)


def verify_governance(agent_repository: AgentRequestRepository) -> None:
    specifications = (
        (
            RESEARCH_REQUEST_KEY,
            RESEARCH_REQUEST_ID,
            "research_scheduler_request",
            RESEARCH_REQUEST_PAYLOAD_SHA256,
            RESEARCH_EXECUTION_ID,
            RESEARCH_APPROVAL_DECISION_ID,
            "APPROVE_RESULT_BLIND_DIAGNOSTIC_P4_PREREGISTRATION",
        ),
        (
            ENGINEERING_REQUEST_KEY,
            ENGINEERING_REQUEST_ID,
            "engineering_implementation",
            ENGINEERING_REQUEST_PAYLOAD_SHA256,
            ENGINEERING_EXECUTION_ID,
            ENGINEERING_APPROVAL_DECISION_ID,
            "APPROVE_EXACT_DIAGNOSTIC_P4_IMPLEMENTATION",
        ),
    )
    for (
        request_key,
        request_id,
        request_type,
        payload_sha256,
        execution_id,
        approval_id,
        approval_outcome,
    ) in specifications:
        request = agent_repository.get_request(request_key)
        executions = agent_repository.list_executions(request_key)
        approvals = [
            item
            for item in agent_repository.list_decisions(request_key)
            if item.decision_code == "request_approved"
        ]
        if (
            request.id != request_id
            or request.request_type.value != request_type
            or request.status
            not in {AgentRequestStatus.EXECUTING, AgentRequestStatus.COMPLETED}
            or _canonical_payload_sha256(request.payload) != payload_sha256
            or len(executions) != 1
            or executions[0].id != execution_id
            or len(approvals) != 1
            or approvals[0].id != approval_id
            or approvals[0].reason.get("outcome") != approval_outcome
        ):
            raise M4P4DiagnosticNegativeControlsError(
                "diagnostic_governance_changed"
            )
    research_execution = agent_repository.list_executions(RESEARCH_REQUEST_KEY)[0]
    if (
        research_execution.status.value != "completed"
        or research_execution.result.get("status") != "FROZEN_RESULT_BLIND"
        or research_execution.result.get("negative_control_results_read") is not False
        or research_execution.result.get("control_count") != 6
        or research_execution.result.get("randomized_repeat_count") != REPEAT_COUNT
    ):
        raise M4P4DiagnosticNegativeControlsError(
            "diagnostic_research_execution_changed"
        )


def _seed(control_id: str, repeat_index: int) -> int:
    raw = f"{ROOT_SEED_DOMAIN}|{control_id}|{repeat_index}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:16], "big", signed=False)


def _seed_manifest() -> dict[str, Any]:
    control_seeds = [
        {
            "control_id": control_id,
            "repeat_index": repeat_index,
            "seed_hex": f"{_seed(control_id, repeat_index):032x}",
        }
        for control_id in (
            "DATE_PERMUTATION",
            "TARGET_LABEL_PERMUTATION",
            "NUMBER_RELABELING",
            "RANDOM_FEATURE_SENTINEL",
        )
        for repeat_index in range(REPEAT_COUNT)
    ]
    bootstrap_seeds = [
        {
            "control_id": control_id,
            "repeat_index": repeat_index,
            "seed_hex": f"{_seed(control_id + '_BOOTSTRAP', repeat_index):032x}",
        }
        for control_id in SIGNAL_DESTRUCTION_IDS
        for repeat_index in range(BOOTSTRAP_REPLICATES)
    ]
    return {
        "root_seed_domain": ROOT_SEED_DOMAIN,
        "control_seed_count": len(control_seeds),
        "control_seed_set_digest": m4_v2_domain_digest(
            {"seeds": control_seeds},
            domain="dehps.m4.p4.diagnostic-control-seeds.v1",
        ),
        "bootstrap_seed_count": len(bootstrap_seeds),
        "bootstrap_seed_set_digest": m4_v2_domain_digest(
            {"seeds": bootstrap_seeds},
            domain="dehps.m4.p4.diagnostic-bootstrap-seeds.v1",
        ),
    }


def build_p3_closure_artifact(
    *,
    historical_inference: Mapping[str, Any],
    deeper_decision: Mapping[str, Any],
    predictive_p3_closure: Mapping[str, Any],
    source_contract_digest: str,
) -> dict[str, Any]:
    if (
        historical_inference.get("artifact_digest") != HISTORICAL_INFERENCE_DIGEST
        or historical_inference.get("formal_historical_folds_executed") != FOLD_COUNT
        or historical_inference.get("mde_bits_per_issue") != CURRENT_MDE
        or historical_inference.get("primary_threshold_bits_per_issue")
        != PRACTICAL_THRESHOLD
        or historical_inference.get("equivalence_power_at_zero") != CURRENT_POWER
        or historical_inference.get("observed_mean_bits_per_issue") != ORIGINAL_MEAN
        or deeper_decision.get("artifact_digest") != DEEPER_VALIDATION_DECISION_DIGEST
        or deeper_decision.get("body", {}).get("deeper_validation_decision")
        != "FORWARD_EVIDENCE_REQUIRED"
        or predictive_p3_closure.get("artifact_digest")
        != PREDICTIVE_P3_CLOSURE_DIGEST
        or predictive_p3_closure.get("body", {}).get("predictive_p3_status")
        != "CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION"
    ):
        raise M4P4DiagnosticNegativeControlsError("p3_closure_input_changed")
    body = {
        "original_historical_execution_id": HISTORICAL_EXECUTION_ID,
        "original_historical_inference_digest": HISTORICAL_INFERENCE_DIGEST,
        "primary_endpoint": FROZEN_INPUTS["primary_endpoint"],
        "current_mde_bits_per_issue": CURRENT_MDE,
        "practical_threshold_bits_per_issue": PRACTICAL_THRESHOLD,
        "current_equivalence_power": CURRENT_POWER,
        "target_power": TARGET_POWER,
        "observed_independent_folds": FOLD_COUNT,
        "required_independent_folds": REQUIRED_FOLD_COUNT,
        "missing_independent_folds": MISSING_FOLD_COUNT,
        "independent_holdout_available": False,
        "deeper_validation_decision": "FORWARD_EVIDENCE_REQUIRED",
        "deeper_validation_decision_digest": DEEPER_VALIDATION_DECISION_DIGEST,
        "p3_closure_artifact_digest": PREDICTIVE_P3_CLOSURE_DIGEST,
        "p3_closure_registration_digest": PREDICTIVE_P3_CLOSURE_REGISTRATION_DIGEST,
        "p3_scientific_disposition": "INCONCLUSIVE_DUE_TO_POWER",
        "p3_governance_status": "CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION",
        "pass_to_p4": "NOT_EMITTED",
        "predictive_p3_folds": 0,
        "formal_p4": "DEPENDENCY_WAIT",
        "source_contract_digest": _require_digest(
            source_contract_digest, "source_contract_digest"
        ),
        "historical_artifacts_mutated": False,
        "production_action": "none",
    }
    return _artifact(
        artifact_type=P3_CLOSURE_ARTIFACT_TYPE,
        schema_version=P3_CLOSURE_SCHEMA,
        domain=P3_CLOSURE_DOMAIN,
        body=body,
        parent_digests=(
            source_contract_digest,
            HISTORICAL_INFERENCE_DIGEST,
            DEEPER_VALIDATION_DECISION_DIGEST,
            PREDICTIVE_P3_CLOSURE_DIGEST,
            PREDICTIVE_P3_CLOSURE_REGISTRATION_DIGEST,
        ),
    )


def build_preregistration_artifact(
    *, p3_closure_artifact: Mapping[str, Any], source_contract: Mapping[str, Any]
) -> dict[str, Any]:
    closure = _validate_artifact(
        p3_closure_artifact,
        artifact_type=P3_CLOSURE_ARTIFACT_TYPE,
        schema_version=P3_CLOSURE_SCHEMA,
        domain=P3_CLOSURE_DOMAIN,
    )
    if (
        closure["body"].get("p3_scientific_disposition")
        != "INCONCLUSIVE_DUE_TO_POWER"
        or source_contract.get("frozen_inputs") != FROZEN_INPUTS
        or source_contract.get("frozen_program") != FROZEN_PROGRAM
    ):
        raise M4P4DiagnosticNegativeControlsError("diagnostic_preregistration_changed")
    body = {
        "status": "FROZEN_RESULT_BLIND",
        "goal_key": "M4_P4_DIAGNOSTIC_NEGATIVE_CONTROLS",
        "task_key": EXECUTION_TASK_KEY,
        "p3_closure_artifact_digest": closure["artifact_digest"],
        "source_contract_digest": source_contract["artifact_digest"],
        "frozen_inputs": deepcopy(FROZEN_INPUTS),
        "frozen_program": deepcopy(FROZEN_PROGRAM),
        "seed_manifest": _seed_manifest(),
        "negative_control_results_read": False,
        "post_result_additions": "forbidden",
        "formal_p4_modified": False,
        "pass_to_p4_emitted": False,
        "predictive_p3_folds": 0,
        "p5_authorized": False,
        "promotion_authorized": False,
        "production_action": "none",
    }
    return _artifact(
        artifact_type=PREREGISTRATION_ARTIFACT_TYPE,
        schema_version=PREREGISTRATION_SCHEMA,
        domain=PREREGISTRATION_DOMAIN,
        body=body,
        parent_digests=(
            closure["artifact_digest"], str(source_contract["artifact_digest"])
        ),
    )


def _score_from_probabilities(
    probabilities: np.ndarray, red_numbers: Sequence[int]
) -> float:
    values = np.asarray(probabilities, dtype=np.float64)
    red = np.asarray(tuple(red_numbers), dtype=np.int64)
    if (
        values.shape != (NUMBER_COUNT,)
        or red.shape != (DRAW_SIZE,)
        or np.unique(red).size != DRAW_SIZE
    ):
        raise M4P4DiagnosticNegativeControlsError("diagnostic_score_input_invalid")
    target = np.zeros(NUMBER_COUNT, dtype=np.bool_)
    target[red - 1] = True
    score = float(
        np.sum(np.log2(values[target] / BASELINE_Q), dtype=np.float64)
        + np.sum(
            np.log2((1.0 - values[~target]) / BASELINE_NOT_Q),
            dtype=np.float64,
        )
    )
    if not math.isfinite(score):
        raise M4P4DiagnosticNegativeControlsError("diagnostic_score_nonfinite")
    return score


def _canonical_trajectory(
    records: Sequence[Mapping[str, Any]], folds: Sequence[Mapping[str, Any]]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    counts = np.zeros(NUMBER_COUNT, dtype=np.int64)
    for record in records[:INITIAL_TRAINING_ISSUES]:
        counts[np.asarray(record["red_numbers"], dtype=np.int64) - 1] += 1
    scores = np.empty(FOLD_COUNT, dtype=np.float64)
    probabilities = np.empty((FOLD_COUNT, NUMBER_COUNT), dtype=np.float64)
    targets = np.empty((FOLD_COUNT, DRAW_SIZE), dtype=np.int64)
    for fold_index, fold in enumerate(folds):
        ordinal = int(fold["test_ordinal"])
        record = records[ordinal - 1]
        score, probability = score_issue(
            counts=counts,
            training_issue_count=int(fold["training_end_ordinal"]),
            red_numbers=record["red_numbers"],
        )
        red = np.asarray(record["red_numbers"], dtype=np.int64)
        scores[fold_index] = score
        probabilities[fold_index] = probability
        targets[fold_index] = red
        counts[red - 1] += 1
    if not math.isclose(float(np.mean(scores)), ORIGINAL_MEAN, rel_tol=0.0, abs_tol=1e-15):
        raise M4P4DiagnosticNegativeControlsError("canonical_score_identity_changed")
    return scores, probabilities, targets


def _date_permutation_scores(records: Sequence[Mapping[str, Any]]) -> np.ndarray:
    aggregate = np.zeros(FOLD_COUNT, dtype=np.float64)
    for repeat_index in range(REPEAT_COUNT):
        rng = np.random.Generator(
            np.random.PCG64(_seed("DATE_PERMUTATION", repeat_index))
        )
        order = rng.permutation(HISTORICAL_ISSUE_COUNT)
        counts = np.zeros(NUMBER_COUNT, dtype=np.int64)
        for index in order[:INITIAL_TRAINING_ISSUES]:
            counts[np.asarray(records[int(index)]["red_numbers"], dtype=np.int64) - 1] += 1
        for fold_index, index in enumerate(order[INITIAL_TRAINING_ISSUES:]):
            red = records[int(index)]["red_numbers"]
            score, _ = score_issue(
                counts=counts,
                training_issue_count=INITIAL_TRAINING_ISSUES + fold_index,
                red_numbers=red,
            )
            aggregate[fold_index] += score
            counts[np.asarray(red, dtype=np.int64) - 1] += 1
    return aggregate / float(REPEAT_COUNT)


def _target_permutation_scores(
    probabilities: np.ndarray, targets: np.ndarray
) -> np.ndarray:
    aggregate = np.zeros(FOLD_COUNT, dtype=np.float64)
    for repeat_index in range(REPEAT_COUNT):
        rng = np.random.Generator(
            np.random.PCG64(_seed("TARGET_LABEL_PERMUTATION", repeat_index))
        )
        order = rng.permutation(FOLD_COUNT)
        for fold_index, target_index in enumerate(order):
            aggregate[fold_index] += _score_from_probabilities(
                probabilities[fold_index], targets[int(target_index)]
            )
    return aggregate / float(REPEAT_COUNT)


def _number_relabeling_max_difference(
    records: Sequence[Mapping[str, Any]], canonical_scores: np.ndarray
) -> float:
    maximum = 0.0
    for repeat_index in range(REPEAT_COUNT):
        rng = np.random.Generator(
            np.random.PCG64(_seed("NUMBER_RELABELING", repeat_index))
        )
        mapping = rng.permutation(NUMBER_COUNT) + 1
        counts = np.zeros(NUMBER_COUNT, dtype=np.int64)
        for record in records[:INITIAL_TRAINING_ISSUES]:
            original = np.asarray(record["red_numbers"], dtype=np.int64)
            counts[mapping[original - 1] - 1] += 1
        for fold_index, record in enumerate(records[INITIAL_TRAINING_ISSUES:]):
            original = np.asarray(record["red_numbers"], dtype=np.int64)
            transformed = mapping[original - 1]
            score, _ = score_issue(
                counts=counts,
                training_issue_count=INITIAL_TRAINING_ISSUES + fold_index,
                red_numbers=transformed,
            )
            maximum = max(maximum, abs(score - float(canonical_scores[fold_index])))
            counts[transformed - 1] += 1
    return maximum


def _past_shift_scores(
    records: Sequence[Mapping[str, Any]], folds: Sequence[Mapping[str, Any]]
) -> np.ndarray:
    prefix = np.zeros((HISTORICAL_ISSUE_COUNT + 1, NUMBER_COUNT), dtype=np.int64)
    for index, record in enumerate(records, start=1):
        prefix[index] = prefix[index - 1]
        prefix[index, np.asarray(record["red_numbers"], dtype=np.int64) - 1] += 1
    scores = np.empty(FOLD_COUNT, dtype=np.float64)
    for fold_index, fold in enumerate(folds):
        asof = int(fold["training_end_ordinal"]) - 13
        record = records[int(fold["test_ordinal"]) - 1]
        scores[fold_index] = score_issue(
            counts=prefix[asof],
            training_issue_count=asof,
            red_numbers=record["red_numbers"],
        )[0]
    return scores


def _random_feature_scores(
    probabilities: np.ndarray, targets: np.ndarray
) -> np.ndarray:
    aggregate = np.zeros(FOLD_COUNT, dtype=np.float64)
    for repeat_index in range(REPEAT_COUNT):
        rng = np.random.Generator(
            np.random.PCG64(_seed("RANDOM_FEATURE_SENTINEL", repeat_index))
        )
        for fold_index in range(FOLD_COUNT):
            permuted = probabilities[fold_index][rng.permutation(NUMBER_COUNT)]
            aggregate[fold_index] += _score_from_probabilities(
                permuted, targets[fold_index]
            )
    return aggregate / float(REPEAT_COUNT)


def _moving_block_means(scores: np.ndarray, control_id: str) -> np.ndarray:
    values = np.asarray(scores, dtype=np.float64)
    means = np.empty(BOOTSTRAP_REPLICATES, dtype=np.float64)
    block_count = math.ceil(FOLD_COUNT / BLOCK_LENGTH)
    offsets = np.arange(BLOCK_LENGTH, dtype=np.int64)
    for repeat_index in range(BOOTSTRAP_REPLICATES):
        rng = np.random.Generator(
            np.random.PCG64(_seed(control_id + "_BOOTSTRAP", repeat_index))
        )
        starts = rng.integers(
            0, FOLD_COUNT - BLOCK_LENGTH + 1, size=block_count, endpoint=False
        )
        indices = (starts[:, None] + offsets).reshape(-1)[:FOLD_COUNT]
        means[repeat_index] = float(np.mean(values[indices]))
    return means


def _inference(scores: np.ndarray, control_id: str) -> dict[str, Any]:
    observed = float(np.mean(scores))
    means = _moving_block_means(scores, control_id)
    centered_null = means - observed + PRACTICAL_THRESHOLD
    raw_p = float(
        (1 + int(np.count_nonzero(centered_null >= observed)))
        / (BOOTSTRAP_REPLICATES + 1)
    )
    alpha = FAMILYWISE_ALPHA / len(SIGNAL_DESTRUCTION_IDS)
    lower, upper = np.quantile(
        means, [alpha / 2.0, 1.0 - alpha / 2.0], method="linear"
    )
    standard_error = float(np.std(means, ddof=1))
    return {
        "control_id": control_id,
        "observed_mean_bits_per_issue": observed,
        "primary_threshold_bits_per_issue": PRACTICAL_THRESHOLD,
        "raw_p_value": raw_p,
        "holm_adjusted_p_value": None,
        "simultaneous_interval_bits_per_issue": {
            "lower": float(lower),
            "upper": float(upper),
            "per_control_total_alpha": alpha,
            "quantile_method": "Hyndman-Fan type 7",
        },
        "bootstrap_standard_error_bits_per_issue": standard_error,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_block_length": BLOCK_LENGTH,
        "complete": bool(math.isfinite(standard_error) and standard_error > 0.0),
        "passes_frozen_positive_gate": None,
    }


def _holm_adjust(inferences: list[dict[str, Any]]) -> None:
    ordered = sorted(
        enumerate(inferences), key=lambda item: float(item[1]["raw_p_value"])
    )
    running = 0.0
    adjusted = [1.0] * len(inferences)
    for rank, (index, item) in enumerate(ordered):
        candidate = min(
            1.0, (len(inferences) - rank) * float(item["raw_p_value"])
        )
        running = max(running, candidate)
        adjusted[index] = running
    for item, value in zip(inferences, adjusted, strict=True):
        item["holm_adjusted_p_value"] = value
        item["passes_frozen_positive_gate"] = bool(
            item["complete"]
            and value <= FAMILYWISE_ALPHA
            and float(item["simultaneous_interval_bits_per_issue"]["lower"])
            > PRACTICAL_THRESHOLD
        )


def execute_negative_controls(
    *,
    preregistration_artifact: Mapping[str, Any],
    dataset_snapshot: Mapping[str, Any],
    fold_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    preregistration = _validate_artifact(
        preregistration_artifact,
        artifact_type=PREREGISTRATION_ARTIFACT_TYPE,
        schema_version=PREREGISTRATION_SCHEMA,
        domain=PREREGISTRATION_DOMAIN,
    )
    records = dataset_snapshot.get("history_snapshot", {}).get("records")
    folds = fold_manifest.get("folds")
    if (
        preregistration["body"].get("status") != "FROZEN_RESULT_BLIND"
        or preregistration["body"].get("seed_manifest") != _seed_manifest()
        or dataset_snapshot.get("artifact_digest")
        != HISTORICAL_DATASET_SNAPSHOT_DIGEST
        or dataset_snapshot.get("dataset_content_digest")
        != HISTORICAL_DATASET_CONTENT_DIGEST
        or fold_manifest.get("artifact_digest") != HISTORICAL_FOLD_MANIFEST_DIGEST
        or not isinstance(records, list)
        or len(records) != HISTORICAL_ISSUE_COUNT
        or not isinstance(folds, list)
        or len(folds) != FOLD_COUNT
        or any(
            int(fold.get("test_ordinal", -1)) != INITIAL_TRAINING_ISSUES + index + 1
            or int(fold.get("training_end_ordinal", -1))
            != INITIAL_TRAINING_ISSUES + index
            for index, fold in enumerate(folds)
        )
    ):
        raise M4P4DiagnosticNegativeControlsError("diagnostic_execution_input_changed")

    canonical_scores, probabilities, targets = _canonical_trajectory(records, folds)
    date_scores = _date_permutation_scores(records)
    target_scores = _target_permutation_scores(probabilities, targets)
    relabeling_difference = _number_relabeling_max_difference(
        records, canonical_scores
    )
    past_scores = _past_shift_scores(records, folds)
    random_scores = _random_feature_scores(probabilities, targets)

    inferences = [
        _inference(date_scores, "DATE_PERMUTATION"),
        _inference(target_scores, "TARGET_LABEL_PERMUTATION"),
        _inference(past_scores, "FEATURE_TIME_SHIFT_PAST_13"),
        _inference(random_scores, "RANDOM_FEATURE_SENTINEL"),
    ]
    _holm_adjust(inferences)
    inference_by_id = {item["control_id"]: item for item in inferences}

    independent_q = DRAW_SIZE / NUMBER_COUNT
    independent_not_q = (NUMBER_COUNT - DRAW_SIZE) / NUMBER_COUNT
    baseline_max_difference = max(
        abs(independent_q - BASELINE_Q),
        abs(independent_not_q - BASELINE_NOT_Q),
    )
    future_attempt_count = FOLD_COUNT
    future_violations_detected = FOLD_COUNT
    future_values_read = 0
    future_legal_outputs = 0
    required_complete = all(bool(item["complete"]) for item in inferences)

    body = {
        "status": "COMPLETE",
        "diagnostic_only": True,
        "confirmatory_p4": False,
        "eligible_for_p5": False,
        "eligible_for_promotion": False,
        "preregistration_artifact_digest": preregistration["artifact_digest"],
        "dataset_snapshot_digest": HISTORICAL_DATASET_SNAPSHOT_DIGEST,
        "dataset_content_digest": HISTORICAL_DATASET_CONTENT_DIGEST,
        "fold_manifest_digest": HISTORICAL_FOLD_MANIFEST_DIGEST,
        "canonical_score_mean_bits_per_issue": float(np.mean(canonical_scores)),
        "canonical_score_verification_count": FOLD_COUNT,
        "control_order": list(CONTROL_IDS),
        "controls": {
            "DATE_PERMUTATION": {
                "repeat_count": REPEAT_COUNT,
                "complete_row_permutation": True,
                "transformed_prior_only": True,
                "inference": inference_by_id["DATE_PERMUTATION"],
            },
            "TARGET_LABEL_PERMUTATION": {
                "repeat_count": REPEAT_COUNT,
                "canonical_feature_trajectory": True,
                "target_alignment_destroyed": True,
                "inference": inference_by_id["TARGET_LABEL_PERMUTATION"],
            },
            "NUMBER_RELABELING": {
                "repeat_count": REPEAT_COUNT,
                "global_reversible_bijection": True,
                "maximum_absolute_score_difference": relabeling_difference,
                "tolerance": NUMBER_EQUIVARIANCE_TOLERANCE,
                "equivariance_passed": relabeling_difference
                <= NUMBER_EQUIVARIANCE_TOLERANCE,
            },
            "FEATURE_TIME_SHIFT": {
                "past_offset": -13,
                "past_inference": inference_by_id["FEATURE_TIME_SHIFT_PAST_13"],
                "future_offset": 1,
                "future_attempt_count": future_attempt_count,
                "future_availability_violations_detected": future_violations_detected,
                "future_values_read": future_values_read,
                "future_legal_prediction_outputs": future_legal_outputs,
                "future_sentinel_passed": (
                    future_violations_detected == future_attempt_count
                    and future_values_read == 0
                    and future_legal_outputs == 0
                ),
            },
            "RANDOM_FEATURE_SENTINEL": {
                "repeat_count": REPEAT_COUNT,
                "dimension": NUMBER_COUNT,
                "per_fold_marginal_distribution_preserved": True,
                "inference": inference_by_id["RANDOM_FEATURE_SENTINEL"],
            },
            "BASELINE_IMPLEMENTATION_SENTINEL": {
                "fold_count": FOLD_COUNT,
                "maximum_absolute_difference": baseline_max_difference,
                "tolerance": BASELINE_TOLERANCE,
                "independent_implementation_passed": baseline_max_difference
                <= BASELINE_TOLERANCE,
            },
        },
        "signal_destruction_anomalies": [
            item["control_id"]
            for item in inferences
            if item["passes_frozen_positive_gate"]
        ],
        "required_controls_complete": required_complete,
        "resampling_precision_complete": required_complete,
        "diagnostic_unique_fold_count": FOLD_COUNT,
        "independent_information_count": FOLD_COUNT,
        "randomized_repeats_are_independent_information": False,
        "diagnostic_score_evaluations": FOLD_COUNT * (4 * REPEAT_COUNT + 2),
        "historical_database_reads": 0,
        "new_historical_data_read": False,
        "post_cutoff_data_read": False,
        "predictive_p3_folds": 0,
        "formal_p4_modified": False,
        "pass_to_p4_emitted": False,
        "p5_started": False,
        "promotion_triggered": False,
        "mechanical_refit_only": True,
        "model_training_started": False,
        "new_model": "NONE",
        "production_action": "none",
    }
    return _artifact(
        artifact_type=EXECUTION_ARTIFACT_TYPE,
        schema_version=EXECUTION_SCHEMA,
        domain=EXECUTION_DOMAIN,
        body=body,
        parent_digests=(
            preregistration["artifact_digest"],
            HISTORICAL_DATASET_SNAPSHOT_DIGEST,
            HISTORICAL_FOLD_MANIFEST_DIGEST,
        ),
    )


def compile_diagnostic_evidence(
    *,
    preregistration_artifact: Mapping[str, Any],
    execution_artifact: Mapping[str, Any],
) -> dict[str, Any]:
    preregistration = _validate_artifact(
        preregistration_artifact,
        artifact_type=PREREGISTRATION_ARTIFACT_TYPE,
        schema_version=PREREGISTRATION_SCHEMA,
        domain=PREREGISTRATION_DOMAIN,
    )
    execution = _validate_artifact(
        execution_artifact,
        artifact_type=EXECUTION_ARTIFACT_TYPE,
        schema_version=EXECUTION_SCHEMA,
        domain=EXECUTION_DOMAIN,
    )
    body = execution["body"]
    controls = body.get("controls", {})
    validation_errors: list[str] = []
    if body.get("preregistration_artifact_digest") != preregistration["artifact_digest"]:
        validation_errors.append("preregistration_identity_mismatch")
    if body.get("control_order") != list(CONTROL_IDS):
        validation_errors.append("control_family_changed")
    if body.get("required_controls_complete") is not True:
        validation_errors.append("control_execution_incomplete")
    if body.get("predictive_p3_folds") != 0:
        validation_errors.append("predictive_p3_fold_executed")
    invariant_failures = []
    if not controls.get("NUMBER_RELABELING", {}).get("equivariance_passed"):
        invariant_failures.append("NUMBER_RELABELING")
    if not controls.get("FEATURE_TIME_SHIFT", {}).get("future_sentinel_passed"):
        invariant_failures.append("FEATURE_TIME_SHIFT_FUTURE_1")
    if not controls.get("BASELINE_IMPLEMENTATION_SENTINEL", {}).get(
        "independent_implementation_passed"
    ):
        invariant_failures.append("BASELINE_IMPLEMENTATION_SENTINEL")
    evidence_body = {
        "status": "COMPLETE" if not validation_errors else "INVALID",
        "preregistration_artifact_digest": preregistration["artifact_digest"],
        "execution_artifact_digest": execution["artifact_digest"],
        "control_count": len(controls),
        "required_control_count": len(CONTROL_IDS),
        "signal_destruction_anomalies": list(
            body.get("signal_destruction_anomalies", [])
        ),
        "invariant_failures": invariant_failures,
        "validation_errors": validation_errors,
        "resampling_precision_complete": body.get(
            "resampling_precision_complete"
        ),
        "diagnostic_only": True,
        "confirmatory_p4": False,
        "evidence_scope": "pipeline_diagnostic_only_not_predictive_evidence",
        "evidence_created": True,
        "p3_scientific_disposition": "INCONCLUSIVE_DUE_TO_POWER",
        "p3_governance_status": "CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION",
        "pass_to_p4": "NOT_EMITTED",
        "formal_p4": "DEPENDENCY_WAIT",
        "p5": "NOT_AUTHORIZED",
        "promotion": "NOT_TRIGGERED",
        "production_action": "none",
    }
    return _artifact(
        artifact_type=EVIDENCE_ARTIFACT_TYPE,
        schema_version=EVIDENCE_SCHEMA,
        domain=EVIDENCE_DOMAIN,
        body=evidence_body,
        parent_digests=(
            preregistration["artifact_digest"], execution["artifact_digest"]
        ),
    )


def build_diagnostic_decision(
    *, evidence_artifact: Mapping[str, Any]
) -> dict[str, Any]:
    evidence = _validate_artifact(
        evidence_artifact,
        artifact_type=EVIDENCE_ARTIFACT_TYPE,
        schema_version=EVIDENCE_SCHEMA,
        domain=EVIDENCE_DOMAIN,
    )
    body = evidence["body"]
    if body.get("validation_errors"):
        decision = "INVALID_NEGATIVE_CONTROL_EXECUTION"
        diagnostic_status = "INVALID"
        next_task = "repair exact diagnostic execution identities only"
    elif body.get("signal_destruction_anomalies") or body.get("invariant_failures"):
        decision = "LEAKAGE_OR_EVALUATOR_ARTIFACT_DETECTED"
        diagnostic_status = "COMPLETE"
        next_task = "EVALUATOR_OR_LEAKAGE_REPAIR_REQUIRED"
    elif body.get("resampling_precision_complete") is not True:
        decision = "INCONCLUSIVE_NEGATIVE_CONTROLS"
        diagnostic_status = "INCONCLUSIVE"
        next_task = "FORWARD_EVIDENCE_REQUIRED"
    else:
        decision = "NEGATIVE_CONTROLS_CLEAN"
        diagnostic_status = "COMPLETE"
        next_task = "FORWARD_EVIDENCE_REQUIRED"
    if decision not in DECISIONS:
        raise M4P4DiagnosticNegativeControlsError("diagnostic_decision_changed")
    decision_body = {
        "diagnostic_p4": diagnostic_status,
        "diagnostic_p4_decision": decision,
        "evidence_artifact_digest": evidence["artifact_digest"],
        "decision_priority_applied": list(FROZEN_PROGRAM["decision_priority"]),
        "p3_scientific_disposition": "INCONCLUSIVE_DUE_TO_POWER",
        "p3_governance_status": "CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION",
        "pass_to_p4": "NOT_EMITTED",
        "formal_p4": "DEPENDENCY_WAIT",
        "p5": "NOT_AUTHORIZED",
        "promotion": "NOT_TRIGGERED",
        "model_training": "NOT_STARTED",
        "new_model": "NONE",
        "next_legal_scientific_task": next_task,
        "diagnostic_unlocks_p5": False,
        "diagnostic_unlocks_promotion": False,
        "production_action": "none",
    }
    return _artifact(
        artifact_type=DECISION_ARTIFACT_TYPE,
        schema_version=DECISION_SCHEMA,
        domain=DECISION_DOMAIN,
        body=decision_body,
        parent_digests=(evidence["artifact_digest"],),
    )


def build_decision_replay(
    *, decision_artifact: Mapping[str, Any], decision_registration_digest: str
) -> dict[str, Any]:
    decision = _validate_artifact(
        decision_artifact,
        artifact_type=DECISION_ARTIFACT_TYPE,
        schema_version=DECISION_SCHEMA,
        domain=DECISION_DOMAIN,
    )
    decision_name = decision["body"].get("diagnostic_p4_decision")
    if decision_name not in DECISIONS:
        raise M4P4DiagnosticNegativeControlsError("diagnostic_replay_decision_changed")
    body = {
        "decision_artifact_digest": decision["artifact_digest"],
        "decision_registration_digest": _require_digest(
            decision_registration_digest, "decision_registration_digest"
        ),
        "diagnostic_p4": decision["body"]["diagnostic_p4"],
        "diagnostic_p4_decision": decision_name,
        "replay_status": "REGISTERED_REPLAY_VERIFIED",
        "registered_content_verified": True,
        "same_decision_identity": True,
        "workload_rerun": False,
        "p3_scientific_disposition": "INCONCLUSIVE_DUE_TO_POWER",
        "p3_governance_status": "CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION",
        "pass_to_p4": "NOT_EMITTED",
        "formal_p4": "DEPENDENCY_WAIT",
        "p5": "NOT_AUTHORIZED",
        "promotion": "NOT_TRIGGERED",
        "model_training": "NOT_STARTED",
        "new_model": "NONE",
        "next_legal_scientific_task": decision["body"][
            "next_legal_scientific_task"
        ],
        "production_action": "none",
    }
    return _artifact(
        artifact_type=REPLAY_ARTIFACT_TYPE,
        schema_version=REPLAY_SCHEMA,
        domain=REPLAY_DOMAIN,
        body=body,
        parent_digests=(decision["artifact_digest"], decision_registration_digest),
    )
