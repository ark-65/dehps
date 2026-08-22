from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentRequestStatus
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2 import (
    forward_prequential_confirmatory as p3,
)
from dehps.research_os.models import Task, m4_v2_domain_digest
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.research_os.supervisor import (
    AtomicArtifactPayload,
    AtomicCapabilityResult,
    M4V2SuccessorCapability,
    MainlineSupervisorError,
    integration_contract,
)


class FormalP4ForwardPrequentialError(ValueError):
    pass


CONTROL_PLANE_KEY = "m4-information-theory-mainline"
SOURCE_CONTRACT_PATH = (
    "configs/research-os/m4-p4-forward-prequential-formal-source-v3.json"
)
SOURCE_SCHEMA = "dehps-m4-p4-forward-prequential-formal-source-contract.v3"
SOURCE_ARTIFACT_TYPE = "m4_p4_forward_prequential_formal_source_contract_v3"
SOURCE_DOMAIN = "dehps.m4.p4.forward-prequential.formal-source-contract.v3"
SOURCE_SET_DOMAIN = "dehps.m4.p4.forward-prequential.formal-source-set.v3"

CONTRACT_KEY = "M4_P4_FORWARD_PREQUENTIAL_FORMAL_NEGATIVE_CONTROLS_V3"
CONTRACT_DIGEST = "8bcc651713e7356c5488727b786f987d01f08ea486a1df75d20de27ef339b3ac"
CONTRACT_FREEZE_FACT = "m4-p4-forward-prequential-formal-contract-v3:FROZEN"
P3_SOURCE_DIGEST = "139ddc97ce1d81ea4e6182359f8391532ed1911090db004bcdf9ebcdea5f9493"
P3_PREREGISTRATION_DIGEST = (
    "8d43f343f555e0a69580c0ccb1fb398b5ff2c191689ef37751c095ba94b144dd"
)

RESEARCH_REQUEST_KEY = (
    "research-m4-p4-forward-prequential-formal-contract-preregistration-v3"
)
RESEARCH_REQUEST_ID = 646
RESEARCH_REQUEST_PAYLOAD_SHA256 = (
    "ed45a98e6d826d015b52cac62df14ea2debe22cb5dd2b47f153c42f631a78031"
)
RESEARCH_APPROVAL_DECISION_ID = 2718
RESEARCH_APPROVAL_OUTCOME = "APPROVE_RESULT_BLIND_SUCCESSOR_FORMAL_P4_CONTRACT_V3"
ENGINEERING_REQUEST_KEY = (
    "engineering-m4-p4-forward-prequential-formal-armed-v3-task-identity-correction"
)
ENGINEERING_REQUEST_ID = 648
ENGINEERING_REQUEST_PAYLOAD_SHA256 = (
    "ec15d027b2d140b3be80711bb7940ea1a1d39421655f15849b77d835c6e3f5fb"
)
ENGINEERING_APPROVAL_DECISION_ID = 2724
ENGINEERING_EXECUTION_ID = 527
ENGINEERING_APPROVAL_OUTCOME = (
    "APPROVE_EXACT_V3_TASK_IDENTITY_FORMAL_P4_ARMED_IMPLEMENTATION"
)
IMPORT_REPAIR_REQUEST_KEY = (
    "engineering-m4-p4-forward-prequential-formal-v3-p4-only-import-repair"
)
IMPORT_REPAIR_REQUEST_ID = 652
IMPORT_REPAIR_REQUEST_PAYLOAD_SHA256 = (
    "85751a637f3bd24a8532b44eca79f8bb2639b04ecd227665258c34535234c21f"
)
IMPORT_REPAIR_APPROVAL_DECISION_ID = 2743
IMPORT_REPAIR_EXECUTION_ID = 530
IMPORT_REPAIR_APPROVAL_OUTCOME = (
    "APPROVE_P4_ONLY_FAIL_CLOSED_IMPORT_REPAIR_WITH_P3_BYTES_FROZEN"
)
COMPLETION_REPAIR_REQUEST_KEY = (
    "engineering-m4-p4-forward-prequential-formal-v3-"
    "completion-verifier-dispatch-repair"
)
COMPLETION_REPAIR_REQUEST_ID = 655
COMPLETION_REPAIR_REQUEST_PAYLOAD_SHA256 = (
    "b6bb71aca75fd00cb61ab68ff3b5ac91b8240af93174d5c38242ee17c57f6812"
)
COMPLETION_REPAIR_APPROVAL_DECISION_ID = 2756
COMPLETION_REPAIR_EXECUTION_ID = 532
COMPLETION_REPAIR_APPROVAL_OUTCOME = (
    "APPROVE_P4_ONLY_COMPLETION_VERIFIER_STATIC_DISPATCH_REPAIR_"
    "WITH_HISTORICAL_INTEGRITY_PRESERVED"
)

EXECUTION_TASK_KEY = p3.P4_TASK_KEY
EVIDENCE_TASK_KEY = "m4-p4-forward-prequential-formal-evidence-v3"
DECISION_TASK_KEY = "m4-p4-forward-prequential-formal-decision-v3"
REPLAY_TASK_KEY = "m4-p4-forward-prequential-formal-decision-replay-v3"
SUCCESSOR_P5_TASK_KEY = "m4-p5-forward-evidence-successor-after-formal-p4-v1"
LEGACY_P5_TASK_KEY = "m4-p5-forward-evidence"

EXECUTION_CAPABILITY = p3.P4_CAPABILITY
EVIDENCE_CAPABILITY = "m4_p4_forward_prequential_formal_evidence_v3"
DECISION_CAPABILITY = "m4_p4_forward_prequential_formal_decision_v3"
REPLAY_CAPABILITY = "m4_p4_forward_prequential_formal_decision_replay_v3"
SUCCESSOR_P5_CAPABILITY = "m4_p5_forward_evidence_successor_after_formal_p4_deferred"
CAPABILITIES = (
    EXECUTION_CAPABILITY,
    EVIDENCE_CAPABILITY,
    DECISION_CAPABILITY,
    REPLAY_CAPABILITY,
)
P4_TASK_KEY_ALLOWLIST = (
    EXECUTION_TASK_KEY,
    EVIDENCE_TASK_KEY,
    DECISION_TASK_KEY,
    REPLAY_TASK_KEY,
)

EXECUTION_COMPLETE_FACT = f"{EXECUTION_TASK_KEY}:COMPLETE"
EVIDENCE_COMPILED_FACT = f"{EVIDENCE_TASK_KEY}:COMPILED"
PASS_TO_P5_FACT = f"{DECISION_TASK_KEY}:PASS_TO_P5"
FAIL_FACT = f"{DECISION_TASK_KEY}:P4_FAIL_NEGATIVE_CONTROLS_OR_ROBUSTNESS"
INVALID_FACT = f"{DECISION_TASK_KEY}:P4_INVALID_EXECUTION"
REPLAY_VERIFIED_FACT = f"{REPLAY_TASK_KEY}:REGISTERED_REPLAY_VERIFIED"

PREREGISTRATION_ARTIFACT_TYPE = "M4P4ForwardPrequentialFormalPreregistrationV3"
INPUT_IDENTITY_ARTIFACT_TYPE = "M4P4ForwardPrequentialP3InputIdentityV3"
CONTROL_CHILD_ARTIFACT_TYPE = "M4P4ForwardPrequentialControlChildV3"
NC4_SENTINEL_ARTIFACT_TYPE = "M4P4ForwardPrequentialNC4SentinelV3"
NC4_SENTINEL_SET_ARTIFACT_TYPE = "M4P4ForwardPrequentialNC4SentinelSetV3"
EXECUTION_ARTIFACT_TYPE = "M4P4ForwardPrequentialFormalExecutionV3"
EVIDENCE_ARTIFACT_TYPE = "M4P4ForwardPrequentialFormalEvidenceV3"
DECISION_ARTIFACT_TYPE = "M4P4ForwardPrequentialFormalDecisionV3"
REPLAY_ARTIFACT_TYPE = "M4P4ForwardPrequentialFormalDecisionReplayV3"

ARTIFACT_SPECS = {
    PREREGISTRATION_ARTIFACT_TYPE: (
        "dehps-M4P4ForwardPrequentialFormalPreregistrationV3.v1",
        "dehps.m4.p4.forward-prequential.formal-preregistration.v3",
    ),
    INPUT_IDENTITY_ARTIFACT_TYPE: (
        "dehps-M4P4ForwardPrequentialP3InputIdentityV3.v1",
        "dehps.m4.p4.forward-prequential.p3-input-identity.v3",
    ),
    CONTROL_CHILD_ARTIFACT_TYPE: (
        "dehps-M4P4ForwardPrequentialControlChildV3.v1",
        "dehps.m4.p4.forward-prequential.control-child.v3",
    ),
    NC4_SENTINEL_ARTIFACT_TYPE: (
        "dehps-M4P4ForwardPrequentialNC4SentinelV3.v1",
        "dehps.m4.p4.forward-prequential.nc4-sentinel.v3",
    ),
    NC4_SENTINEL_SET_ARTIFACT_TYPE: (
        "dehps-M4P4ForwardPrequentialNC4SentinelSetV3.v1",
        "dehps.m4.p4.forward-prequential.nc4-sentinel-set.v3",
    ),
    EXECUTION_ARTIFACT_TYPE: (
        "dehps-M4P4ForwardPrequentialFormalExecutionV3.v1",
        "dehps.m4.p4.forward-prequential.formal-execution.v3",
    ),
    EVIDENCE_ARTIFACT_TYPE: (
        "dehps-M4P4ForwardPrequentialFormalEvidenceV3.v1",
        "dehps.m4.p4.forward-prequential.formal-evidence.v3",
    ),
    DECISION_ARTIFACT_TYPE: (
        "dehps-M4P4ForwardPrequentialFormalDecisionV3.v1",
        "dehps.m4.p4.forward-prequential.formal-decision.v3",
    ),
    REPLAY_ARTIFACT_TYPE: (
        "dehps-M4P4ForwardPrequentialFormalDecisionReplayV3.v1",
        "dehps.m4.p4.forward-prequential.formal-decision-replay.v3",
    ),
}

CONTROL_ORDER = (
    "NC1_ISSUE_LABEL_PERMUTATION",
    "NC2_NUMBER_LABEL_PERMUTATION",
    "NC3_CIRCULAR_TARGET_SHIFT",
    "NC4_MATCHED_RANDOM_FEATURES",
    "NC5_MATCHED_RANDOM_SCORE",
    "NC6_SYNTHETIC_NULL",
)
PRIMARY_CONTROL_ORDER = (
    "NC1_ISSUE_LABEL_PERMUTATION",
    "NC5_MATCHED_RANDOM_SCORE",
    "NC6_SYNTHETIC_NULL",
)
SENSITIVITY_ORDER = (
    "S1_MOVING_BLOCK_L3",
    "S1_MOVING_BLOCK_L5",
    "S1_MOVING_BLOCK_L8",
    "S1_MOVING_BLOCK_L13",
    "S2_STATIONARY_E3",
    "S2_STATIONARY_E5",
    "S2_STATIONARY_E8",
    "S2_STATIONARY_E13",
)
NC4_OPERATORS = (
    "M4_P4_FORWARD_PREQUENTIAL_FORMAL_V3|NC4_MATCHED_RANDOM_FEATURES|OPERATOR=INDEPENDENT_MATCHED_NO_FEATURE_SENTINEL",
    "M4_P4_FORWARD_PREQUENTIAL_FORMAL_V3|NC4_MATCHED_RANDOM_FEATURES|OPERATOR=BLOCK_CORRELATED_L5_MATCHED_NO_FEATURE_SENTINEL",
    "M4_P4_FORWARD_PREQUENTIAL_FORMAL_V3|NC4_MATCHED_RANDOM_FEATURES|OPERATOR=GLOBAL_ISSUE_PERMUTATION_MATCHED_NO_FEATURE_SENTINEL",
)
PASS_LOOKS = (20, 40, 60, 90, 120)
SHIFT_SET = (1, 2, 3, 5, 8, 13, 21)
PRIMARY_REPLICATES = 1000
SENSITIVITY_REPLICATES = 2000
FAMILYWISE_ALPHA = 0.05
UNIFORM_Q = 2.0 / 11.0
TOLERANCE = 1e-12


def _canonical_payload_sha256(value: Mapping[str, Any]) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _require_digest(value: object, name: str) -> str:
    digest = str(value or "")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise FormalP4ForwardPrequentialError(f"{name}_invalid")
    return digest


def _artifact(
    *, artifact_type: str, body: Mapping[str, Any], parent_digests: Sequence[str]
) -> dict[str, Any]:
    schema, domain = ARTIFACT_SPECS[artifact_type]
    payload: dict[str, Any] = {
        "schema_version": schema,
        "artifact_type": artifact_type,
        "body": deepcopy(dict(body)),
        "parent_digests": [
            _require_digest(item, "parent_digest") for item in parent_digests
        ],
    }
    payload["artifact_digest"] = m4_v2_domain_digest(payload, domain=domain)
    return payload


def validate_artifact(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(value))
    artifact_type = str(payload.get("artifact_type") or "")
    spec = ARTIFACT_SPECS.get(artifact_type)
    if spec is None or set(payload) != {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "body",
        "parent_digests",
    }:
        raise FormalP4ForwardPrequentialError("formal_p4_artifact_shape_changed")
    schema, domain = spec
    if payload.get("schema_version") != schema:
        raise FormalP4ForwardPrequentialError("formal_p4_artifact_schema_changed")
    observed = _require_digest(payload.pop("artifact_digest"), "artifact_digest")
    if m4_v2_domain_digest(payload, domain=domain) != observed:
        raise FormalP4ForwardPrequentialError("formal_p4_artifact_digest_changed")
    payload["artifact_digest"] = observed
    return payload


def load_source_contract(*, root_dir: Path = ROOT_DIR) -> dict[str, Any]:
    root = root_dir.resolve()
    path = (root / SOURCE_CONTRACT_PATH).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise FormalP4ForwardPrequentialError("formal_p4_source_missing")
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "source_set_digest",
        "contract_key",
        "contract_digest",
        "governance_bindings",
        "formal_preregistration",
        "source_entries",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise FormalP4ForwardPrequentialError("formal_p4_source_shape_changed")
    if (
        payload["schema_version"] != SOURCE_SCHEMA
        or payload["artifact_type"] != SOURCE_ARTIFACT_TYPE
        or payload["contract_key"] != CONTRACT_KEY
        or payload["contract_digest"] != CONTRACT_DIGEST
    ):
        raise FormalP4ForwardPrequentialError("formal_p4_source_contract_changed")
    entries = payload.get("source_entries")
    if not isinstance(entries, list) or not entries:
        raise FormalP4ForwardPrequentialError("formal_p4_source_entries_missing")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in entries:
        if not isinstance(raw, dict) or set(raw) != {"path", "sha256", "bytes"}:
            raise FormalP4ForwardPrequentialError("formal_p4_source_entry_changed")
        relative = str(raw["path"])
        source_path = (root / relative).resolve()
        if (
            relative in seen
            or not source_path.is_relative_to(root)
            or not source_path.is_file()
        ):
            raise FormalP4ForwardPrequentialError("formal_p4_source_path_changed")
        content = source_path.read_bytes()
        observed = hashlib.sha256(content).hexdigest()
        if observed != raw["sha256"] or len(content) != raw["bytes"]:
            raise FormalP4ForwardPrequentialError("formal_p4_source_bytes_changed")
        seen.add(relative)
        normalized.append({"path": relative, "sha256": observed, "bytes": len(content)})
    source_set = m4_v2_domain_digest(
        {"source_entries": normalized}, domain=SOURCE_SET_DOMAIN
    )
    identity = deepcopy(payload)
    observed_digest = _require_digest(identity.pop("artifact_digest"), "source_digest")
    if (
        payload["source_set_digest"] != source_set
        or m4_v2_domain_digest(identity, domain=SOURCE_DOMAIN) != observed_digest
    ):
        raise FormalP4ForwardPrequentialError("formal_p4_source_identity_changed")
    prereg = validate_artifact(payload["formal_preregistration"])
    if (
        prereg["body"].get("contract_key") != CONTRACT_KEY
        or prereg["body"].get("contract_digest") != CONTRACT_DIGEST
        or prereg["parent_digests"] != [P3_PREREGISTRATION_DIGEST, P3_SOURCE_DIGEST]
    ):
        raise FormalP4ForwardPrequentialError("formal_p4_preregistration_changed")
    return deepcopy(payload)


def verify_governance(repository: AgentRequestRepository) -> None:
    source = load_source_contract()
    bindings = source["governance_bindings"]
    specs = (
        (
            RESEARCH_REQUEST_KEY,
            RESEARCH_REQUEST_ID,
            None,
            RESEARCH_APPROVAL_DECISION_ID,
            RESEARCH_REQUEST_PAYLOAD_SHA256,
            RESEARCH_APPROVAL_OUTCOME,
        ),
        (
            ENGINEERING_REQUEST_KEY,
            ENGINEERING_REQUEST_ID,
            ENGINEERING_EXECUTION_ID,
            ENGINEERING_APPROVAL_DECISION_ID,
            ENGINEERING_REQUEST_PAYLOAD_SHA256,
            ENGINEERING_APPROVAL_OUTCOME,
        ),
        (
            IMPORT_REPAIR_REQUEST_KEY,
            IMPORT_REPAIR_REQUEST_ID,
            IMPORT_REPAIR_EXECUTION_ID,
            IMPORT_REPAIR_APPROVAL_DECISION_ID,
            IMPORT_REPAIR_REQUEST_PAYLOAD_SHA256,
            IMPORT_REPAIR_APPROVAL_OUTCOME,
        ),
        (
            COMPLETION_REPAIR_REQUEST_KEY,
            COMPLETION_REPAIR_REQUEST_ID,
            COMPLETION_REPAIR_EXECUTION_ID,
            COMPLETION_REPAIR_APPROVAL_DECISION_ID,
            COMPLETION_REPAIR_REQUEST_PAYLOAD_SHA256,
            COMPLETION_REPAIR_APPROVAL_OUTCOME,
        ),
    )
    expected_bindings = {
        "contract_digest": CONTRACT_DIGEST,
        "research_request_key": RESEARCH_REQUEST_KEY,
        "research_request_id": RESEARCH_REQUEST_ID,
        "research_request_payload_sha256": RESEARCH_REQUEST_PAYLOAD_SHA256,
        "research_approval_decision_id": RESEARCH_APPROVAL_DECISION_ID,
        "engineering_request_key": ENGINEERING_REQUEST_KEY,
        "engineering_request_id": ENGINEERING_REQUEST_ID,
        "engineering_request_payload_sha256": ENGINEERING_REQUEST_PAYLOAD_SHA256,
        "engineering_approval_decision_id": ENGINEERING_APPROVAL_DECISION_ID,
        "engineering_execution_id": ENGINEERING_EXECUTION_ID,
        "import_repair_request_key": IMPORT_REPAIR_REQUEST_KEY,
        "import_repair_request_id": IMPORT_REPAIR_REQUEST_ID,
        "import_repair_request_payload_sha256": IMPORT_REPAIR_REQUEST_PAYLOAD_SHA256,
        "import_repair_approval_decision_id": IMPORT_REPAIR_APPROVAL_DECISION_ID,
        "import_repair_execution_id": IMPORT_REPAIR_EXECUTION_ID,
        "completion_repair_request_key": COMPLETION_REPAIR_REQUEST_KEY,
        "completion_repair_request_id": COMPLETION_REPAIR_REQUEST_ID,
        "completion_repair_request_payload_sha256": (
            COMPLETION_REPAIR_REQUEST_PAYLOAD_SHA256
        ),
        "completion_repair_approval_decision_id": (
            COMPLETION_REPAIR_APPROVAL_DECISION_ID
        ),
        "completion_repair_execution_id": COMPLETION_REPAIR_EXECUTION_ID,
    }
    if bindings != expected_bindings:
        raise FormalP4ForwardPrequentialError("formal_p4_governance_binding_changed")
    for key, request_id, execution_id, approval_id, payload_sha, outcome in specs:
        request = repository.get_request(key)
        approvals = [
            item
            for item in repository.list_decisions(key)
            if item.decision_code == "request_approved"
        ]
        executions = repository.list_executions(key)
        observed_outcome = None
        if len(approvals) == 1:
            observed_outcome = (
                approvals[0].reason.get("outcome")
                or approvals[0].reason.get("decision")
                or approvals[0].reason.get("review_outcome")
            )
        execution_ok = (
            len(executions) == 0
            if execution_id is None
            else len(executions) == 1 and executions[0].id == execution_id
        )
        allowed_status = (
            {AgentRequestStatus.APPROVED}
            if execution_id is None
            else {AgentRequestStatus.EXECUTING, AgentRequestStatus.COMPLETED}
        )
        if (
            request.id != request_id
            or request.status not in allowed_status
            or _canonical_payload_sha256(request.payload) != payload_sha
            or not execution_ok
            or len(approvals) != 1
            or approvals[0].id != approval_id
            or observed_outcome != outcome
        ):
            raise FormalP4ForwardPrequentialError("formal_p4_governance_changed")


def formal_preregistration(source_contract: Mapping[str, Any]) -> dict[str, Any]:
    prereg = validate_artifact(source_contract["formal_preregistration"])
    expected = frozen_preregistration()
    if prereg != expected:
        raise FormalP4ForwardPrequentialError("formal_p4_preregistration_changed")
    return prereg


def frozen_preregistration() -> dict[str, Any]:
    """Rebuild the approved V3 preregistration without reading mutable runtime state."""

    return _artifact(
        artifact_type=PREREGISTRATION_ARTIFACT_TYPE,
        body={
            "contract_digest": CONTRACT_DIGEST,
            "contract_key": CONTRACT_KEY,
            "diagnostic_p4_decision_credit": False,
            "execution_before_pass": "FORBIDDEN",
            "p3_lineage_id": p3.LINEAGE_ID,
            "p3_request_id": 640,
            "p5_started": False,
            "promotion_triggered": False,
            "research_request_id": RESEARCH_REQUEST_ID,
            "research_request_payload_sha256": RESEARCH_REQUEST_PAYLOAD_SHA256,
            "source_digest": P3_SOURCE_DIGEST,
            "status": "FROZEN_NOT_EXECUTED",
        },
        parent_digests=(P3_PREREGISTRATION_DIGEST, P3_SOURCE_DIGEST),
    )


def _p3_artifact(value: Mapping[str, Any], artifact_type: str) -> dict[str, Any]:
    payload = p3.validate_artifact(value)
    if payload["artifact_type"] != artifact_type:
        raise FormalP4ForwardPrequentialError("formal_p4_p3_artifact_type_changed")
    return payload


def _p3_ticket_payload_valid(
    *,
    body: Mapping[str, Any],
    blue_numbers: Sequence[int],
    probabilities: Sequence[float] | None,
) -> bool:
    tickets = body.get("tickets")
    if not isinstance(tickets, list) or len(tickets) != 100:
        return False
    lex_ids: list[int] = []
    score_keys: list[tuple[float, int]] = []
    for rank, ticket in enumerate(tickets, start=1):
        if not isinstance(ticket, Mapping):
            return False
        numbers = ticket.get("red_numbers")
        lex_id = ticket.get("lex_id")
        if (
            ticket.get("rank") != rank
            or type(lex_id) is not int
            or not isinstance(numbers, list)
            or len(numbers) != 6
            or numbers != sorted(numbers)
            or len(set(numbers)) != 6
            or min(numbers) < 1
            or max(numbers) > 33
            or ticket.get("blue_number") != blue_numbers[rank - 1]
        ):
            return False
        lex_ids.append(lex_id)
        if probabilities is not None:
            score = ticket.get("model_log2_score")
            if not isinstance(score, (int, float)) or not math.isclose(
                float(score),
                p3._ticket_score(numbers, probabilities),
                rel_tol=0.0,
                abs_tol=TOLERANCE,
            ):
                return False
            score_keys.append((-float(score), lex_id))
    return len(set(lex_ids)) == 100 and (
        probabilities is None or score_keys == sorted(score_keys)
    )


def build_p3_input_identity(bundle: Mapping[str, Any]) -> dict[str, Any]:
    review = _p3_artifact(bundle["review"], p3.REVIEW_ARTIFACT_TYPE)
    prereg = _p3_artifact(bundle["preregistration"], p3.PREREGISTRATION_ARTIFACT_TYPE)
    settlements = [
        _p3_artifact(item, p3.SETTLEMENT_ARTIFACT_TYPE)
        for item in bundle["settlements"]
    ]
    replays = [
        _p3_artifact(item, p3.SETTLEMENT_REPLAY_ARTIFACT_TYPE)
        for item in bundle["settlement_replays"]
    ]
    checkpoints = [
        _p3_artifact(item, p3.CHECKPOINT_ARTIFACT_TYPE)
        for item in bundle["checkpoints"]
    ]
    models = [_p3_artifact(item, p3.MODEL_ARTIFACT_TYPE) for item in bundle["models"]]
    datasets = [
        _p3_artifact(item, p3.DATASET_ARTIFACT_TYPE) for item in bundle["datasets"]
    ]
    candidates = [
        _p3_artifact(item, p3.MODEL_CANDIDATE_ARTIFACT_TYPE)
        for item in bundle["model_candidates"]
    ]
    baselines = [
        _p3_artifact(item, p3.RANDOM_BASELINE_ARTIFACT_TYPE)
        for item in bundle["random_baselines"]
    ]
    look = review["body"].get("look")
    issue_count = review["body"].get("issue_count")
    if (
        type(look) is not int
        or look not in PASS_LOOKS
        or type(issue_count) is not int
        or issue_count != look
        or any(
            len(items) != look
            for items in (
                settlements,
                replays,
                checkpoints,
                models,
                datasets,
                candidates,
                baselines,
            )
        )
    ):
        raise FormalP4ForwardPrequentialError("formal_p4_p3_issue_count_invalid")
    issues = [str(item["body"].get("target_issue") or "") for item in settlements]
    if (
        review["body"].get("status") != "FROZEN_POLICY_APPLIED"
        or review["body"].get("decision") != "PASS_TO_P4"
        or review["body"].get("allowed_decision") is not True
        or review["body"].get("integrity_pass") is not True
        or review["body"].get("formal_p4_ready") is not True
        or review["body"].get("critical_z") != p3.CRITICAL_Z
        or review["body"].get("practical_threshold_bits_per_issue")
        != p3.PRACTICAL_THRESHOLD
        or review["body"].get("multiplicity")
        != "ONE_SIDED_BONFERRONI_FIXED_FIVE_LOOKS_ALPHA_0_005_PER_LOOK"
        or review["body"].get("source_digest") != P3_SOURCE_DIGEST
        or review["body"].get("issues") != issues
        or len(set(issues)) != look
        or review["parent_digests"]
        != [item["artifact_digest"] for item in settlements] + [P3_SOURCE_DIGEST]
        or prereg["artifact_digest"] != P3_PREREGISTRATION_DIGEST
        or prereg["parent_digests"] != [P3_SOURCE_DIGEST]
    ):
        raise FormalP4ForwardPrequentialError("formal_p4_p3_review_identity_invalid")
    for index, values in enumerate(
        zip(
            settlements,
            replays,
            checkpoints,
            models,
            datasets,
            candidates,
            baselines,
            strict=True,
        ),
        start=1,
    ):
        settlement, replay, checkpoint, model, dataset, candidate, baseline = values
        issue = issues[index - 1]
        q = model["body"].get("probabilities_q_1_to_33")
        actual = settlement["body"].get("actual_red_numbers")
        checkpoint_body = checkpoint["body"]
        model_body = model["body"]
        dataset_body = dataset["body"]
        candidate_body = candidate["body"]
        baseline_body = baseline["body"]
        expected_estimator_digest = p3.canonical_digest(
            {"identity": p3.ESTIMATOR_ID, "formula": "q_i=(c_i+2/11)/(n+1)"},
            domain="dehps.m4.p3.forward-prequential.estimator.v1",
        )
        expected_feature_digest = p3.canonical_digest(
            {"identity": "NO_FEATURES_33_EXPANDING_RED_NUMBER_EVENT_COUNTS_ONLY"},
            domain="dehps.m4.p3.forward-prequential.features.v1",
        )
        expected_parameter_digest = p3.canonical_digest(
            {
                "alpha": 1,
                "per_number_prior": "2/11",
                "minimum_training_issues": 900,
                "clipping": "forbidden",
                "renormalization": "forbidden",
                "hyperparameter_search": "none",
            },
            domain="dehps.m4.p3.forward-prequential.parameters.v1",
        )
        expected_baseline_digest = p3.canonical_digest(
            {"identity": "LEGAL_UNIFORM_NUMBER_EVENT_BASELINE", "q": "2/11"},
            domain="dehps.m4.p3.forward-prequential.baseline.v1",
        )
        model_seed = p3._arm_seed(
            preregistration_digest=prereg["artifact_digest"],
            target_issue=issue,
            arm="MODEL_PROPOSAL_POOL",
            model_digest=model["artifact_digest"],
        )
        baseline_seed = p3._arm_seed(
            preregistration_digest=prereg["artifact_digest"],
            target_issue=issue,
            arm="RANDOM_BASELINE",
        )
        blue_numbers = p3._blue_numbers(
            preregistration_digest=prereg["artifact_digest"], target_issue=issue
        )
        expected_blue_digest = p3.canonical_digest(
            {
                "identity": "SHARED_DETERMINISTIC_UNIFORM_BLUE_BY_RANK_V1",
                "target_issue": issue,
                "values": blue_numbers,
            },
            domain="dehps.m4.p3.forward-prequential.blue-strategy.v1",
        )
        if (
            settlement["body"].get("status") != "SETTLED"
            or settlement["body"].get("cohort_index") != index
            or settlement["body"].get("lineage_id") != p3.LINEAGE_ID
            or settlement["body"].get("configuration_drift") is not False
            or settlement["body"].get("old_lineage_result") is not False
            or replay["body"].get("status") != "REPLAY_VERIFIED"
            or replay["body"].get("registered_replay_status")
            != "REGISTERED_REPLAY_VERIFIED"
            or replay["body"].get("same_registered_content") is not True
            or replay["body"].get("workload_rerun") is not False
            or replay["body"].get("configuration_drift") is not False
            or replay["body"].get("target_issue") != issue
            or replay["body"].get("cohort_index") != index
            or checkpoint["body"].get("status") != "SEALED_BEFORE_DRAW"
            or checkpoint_body.get("lineage_id") != p3.LINEAGE_ID
            or checkpoint["body"].get("configuration_drift") is not False
            or checkpoint["body"].get("old_checkpoint_reused") is not False
            or checkpoint["body"].get("same_blue_strategy") is not True
            or checkpoint["body"].get("model_ticket_count") != 100
            or checkpoint["body"].get("random_baseline_ticket_count") != 100
            or model["body"].get("lineage_id") != p3.LINEAGE_ID
            or model["body"].get("source_digest") != P3_SOURCE_DIGEST
            or model_body.get("mode") != "MECHANICAL_REFIT_ONLY"
            or model_body.get("branch") != "MARGINAL_STATIC"
            or model_body.get("estimator_identity") != p3.ESTIMATOR_ID
            or model_body.get("estimator_digest") != expected_estimator_digest
            or model_body.get("feature_digest") != expected_feature_digest
            or model_body.get("parameter_digest") != expected_parameter_digest
            or model_body.get("baseline_digest") != expected_baseline_digest
            or model_body.get("hyperparameter_search") != "NONE"
            or model_body.get("model_selection") != "NONE"
            or model_body.get("future_rows_read") is not False
            or dataset_body.get("status") != "FROZEN_INPUT"
            or dataset_body.get("target_issue") != issue
            or dataset_body.get("future_rows_read") is not False
            or dataset_body.get("training_end_issue") >= issue
            or dataset_body.get("training_issue_count")
            != len(dataset_body.get("rows", ()))
            or model_body.get("training_start_issue")
            != dataset_body.get("training_start_issue")
            or model_body.get("training_end_issue")
            != dataset_body.get("training_end_issue")
            or model_body.get("training_issue_count")
            != dataset_body.get("training_issue_count")
            or candidate_body.get("mode") != "SHADOW_ONLY"
            or candidate_body.get("candidate_count") != p3.MODEL_TICKET_COUNT
            or candidate_body.get("proposal_pool_size") != p3.PROPOSAL_POOL_SIZE
            or candidate_body.get("target_issue") != issue
            or candidate_body.get("seed_digest") != model_seed
            or candidate_body.get("ranking")
            != "DESCENDING_33_EVENT_BERNOULLI_LOG_SCORE"
            or candidate_body.get("tie_break") != "ASCENDING_LEX_ID"
            or baseline_body.get("mode") != "SHADOW_ONLY"
            or baseline_body.get("candidate_count") != p3.BASELINE_TICKET_COUNT
            or baseline_body.get("target_issue") != issue
            or baseline_body.get("seed_digest") != baseline_seed
            or baseline_body.get("sampling")
            != "UNIFORM_LEGAL_SIX_OF_33_WITHOUT_REPLACEMENT"
            or candidate_body.get("blue_strategy_digest")
            != baseline_body.get("blue_strategy_digest")
            or checkpoint_body.get("blue_strategy_digest")
            != candidate_body.get("blue_strategy_digest")
            or checkpoint_body.get("blue_strategy_digest") != expected_blue_digest
            or not _p3_ticket_payload_valid(
                body=candidate_body,
                blue_numbers=blue_numbers,
                probabilities=[float(item) for item in q],
            )
            or not _p3_ticket_payload_valid(
                body=baseline_body,
                blue_numbers=blue_numbers,
                probabilities=None,
            )
            or checkpoint["body"].get("source_digest") != P3_SOURCE_DIGEST
            or any(item["body"].get("target_issue") != issue for item in values[:5])
            or candidate["body"].get("target_issue") != issue
            or baseline["body"].get("target_issue") != issue
            or len(q or ()) != 33
            or not all(
                math.isfinite(float(item)) and 0.0 < float(item) < 1.0 for item in q
            )
            or not math.isclose(
                math.fsum(float(item) for item in q), 6.0, abs_tol=TOLERANCE
            )
            or not isinstance(actual, list)
            or len(actual) != 6
            or len(set(actual)) != 6
            or min(actual) < 1
            or max(actual) > 33
        ):
            raise FormalP4ForwardPrequentialError(
                "formal_p4_p3_lineage_or_value_invalid"
            )
        if (
            datetime.fromisoformat(str(checkpoint_body.get("sealed_at")))
            >= datetime.fromisoformat(str(checkpoint_body.get("official_draw_time")))
            or datetime.fromisoformat(str(checkpoint_body.get("sealed_at")))
            > datetime.fromisoformat(str(checkpoint_body.get("checkpoint_deadline")))
            or checkpoint_body.get("dataset_digest") != dataset["artifact_digest"]
            or checkpoint_body.get("model_digest") != model["artifact_digest"]
            or checkpoint_body.get("feature_digest") != model_body.get("feature_digest")
            or checkpoint_body.get("parameter_digest")
            != model_body.get("parameter_digest")
            or checkpoint_body.get("baseline_digest")
            != model_body.get("baseline_digest")
            or checkpoint_body.get("model_candidate_digest")
            != candidate["artifact_digest"]
            or checkpoint_body.get("random_baseline_digest")
            != baseline["artifact_digest"]
            or model_body.get("dataset_digest") != dataset["artifact_digest"]
            or not math.isclose(
                _gain([float(item) for item in q], actual),
                float(settlement["body"].get("primary_endpoint_bits_per_issue")),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        ):
            raise FormalP4ForwardPrequentialError("formal_p4_p3_checkpoint_invalid")
        if (
            settlement["parent_digests"]
            != [
                model["artifact_digest"],
                candidate["artifact_digest"],
                baseline["artifact_digest"],
                checkpoint["artifact_digest"],
            ]
            or replay["parent_digests"]
            != [settlement["artifact_digest"], checkpoint["artifact_digest"]]
            or checkpoint["parent_digests"]
            != [
                model["artifact_digest"],
                candidate["artifact_digest"],
                baseline["artifact_digest"],
                prereg["artifact_digest"],
            ]
            or model["parent_digests"]
            != [dataset["artifact_digest"], prereg["artifact_digest"], P3_SOURCE_DIGEST]
            or dataset["parent_digests"]
            != [prereg["artifact_digest"], P3_SOURCE_DIGEST]
            or candidate["parent_digests"]
            != [model["artifact_digest"], prereg["artifact_digest"]]
            or baseline["parent_digests"] != [prereg["artifact_digest"]]
        ):
            raise FormalP4ForwardPrequentialError("formal_p4_p3_parent_graph_invalid")
    gains = [
        float(item["body"]["primary_endpoint_bits_per_issue"]) for item in settlements
    ]
    if not all(math.isfinite(item) for item in gains):
        raise FormalP4ForwardPrequentialError("formal_p4_p3_gain_nonfinite")
    observed = math.fsum(gains) / look
    if observed != float(
        review["body"].get("mean_gain_bits_per_issue")
    ) or not _p3_pass_predicate(observed, look):
        raise FormalP4ForwardPrequentialError("formal_p4_p3_observed_mean_changed")
    projection = {
        "schema_version": "dehps-m4-p4-successor-p3-input-identity-projection.v1",
        "source_digest": P3_SOURCE_DIGEST,
        "review_artifact_digest": review["artifact_digest"],
        "review_look": look,
        "review_issues": issues,
        "settlement_artifact_digests": [
            item["artifact_digest"] for item in settlements
        ],
        "settlement_replay_artifact_digests": [
            item["artifact_digest"] for item in replays
        ],
        "checkpoint_artifact_digests": [
            item["artifact_digest"] for item in checkpoints
        ],
        "model_artifact_digests": [item["artifact_digest"] for item in models],
        "dataset_artifact_digests": [item["artifact_digest"] for item in datasets],
        "preregistration_artifact_digest": prereg["artifact_digest"],
        "lineage_id_derived": p3.LINEAGE_ID,
        "configuration_status_derived": "NO_DRIFT",
    }
    projection_digest = m4_v2_domain_digest(
        projection,
        domain="dehps.m4.p4.successor-p3-input-identity-projection.v1",
    )
    body = {
        "contract_key": CONTRACT_KEY,
        "contract_digest": CONTRACT_DIGEST,
        "source_digest": P3_SOURCE_DIGEST,
        "review_artifact_digest": review["artifact_digest"],
        "review_look": look,
        "review_issues": issues,
        "settlement_artifact_digests": [
            item["artifact_digest"] for item in settlements
        ],
        "settlement_replay_artifact_digests": [
            item["artifact_digest"] for item in replays
        ],
        "checkpoint_artifact_digests": [
            item["artifact_digest"] for item in checkpoints
        ],
        "model_artifact_digests": [item["artifact_digest"] for item in models],
        "dataset_artifact_digests": [item["artifact_digest"] for item in datasets],
        "preregistration_artifact_digest": prereg["artifact_digest"],
        "lineage_id_derived": p3.LINEAGE_ID,
        "configuration_status_derived": "NO_DRIFT",
        "derived_projection": projection,
        "derived_projection_digest": projection_digest,
        "training_horizon": int(datasets[0]["body"]["training_issue_count"]),
        "observed_gains": gains,
        "observed_mean_gain_bits_per_issue": observed,
        "status": "VALIDATED_RESULT_INPUT_IDENTITY",
    }
    parents = (
        [review["artifact_digest"]]
        + [item["artifact_digest"] for item in settlements]
        + [item["artifact_digest"] for item in replays]
        + [item["artifact_digest"] for item in checkpoints]
        + [item["artifact_digest"] for item in models]
        + [item["artifact_digest"] for item in datasets]
        + [prereg["artifact_digest"], P3_SOURCE_DIGEST]
    )
    return _artifact(
        artifact_type=INPUT_IDENTITY_ARTIFACT_TYPE,
        body=body,
        parent_digests=parents,
    )


def _score(probabilities: Sequence[float], target: Sequence[int]) -> float:
    selected = {int(item) for item in target}
    return math.fsum(
        math.log2(float(q) if index in selected else 1.0 - float(q))
        for index, q in enumerate(probabilities, start=1)
    )


def _gain(probabilities: Sequence[float], target: Sequence[int]) -> float:
    return _score(probabilities, target) - _score([UNIFORM_Q] * 33, target)


def _seed(identity: str) -> tuple[int, str]:
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return int(digest[:32], 16), digest


def _non_identity_permutation(rng: np.random.Generator, size: int) -> list[int]:
    for _ in range(128):
        candidate = [int(item) for item in rng.permutation(size)]
        if any(candidate[index] != index for index in range(size)):
            return candidate
    return list(range(1, size)) + [0]


def _p3_pass_predicate(mean_gain: float, n: int) -> bool:
    standard_error = p3.FROZEN_LONG_RUN_SD / math.sqrt(n)
    return (
        mean_gain >= p3.PRACTICAL_THRESHOLD
        and mean_gain / standard_error >= p3.CRITICAL_Z
    )


def _hf7(values: Sequence[float], quantile: float = 0.95) -> float:
    ordered = sorted(float(item) for item in values)
    if not ordered or not all(math.isfinite(item) for item in ordered):
        raise FormalP4ForwardPrequentialError("formal_p4_quantile_input_invalid")
    h = (len(ordered) - 1) * quantile
    lower = math.floor(h)
    upper = math.ceil(h)
    return ordered[lower] + (h - lower) * (ordered[upper] - ordered[lower])


def holm(p_values: Mapping[str, float], order: Sequence[str]) -> dict[str, Any]:
    if set(p_values) != set(order):
        raise FormalP4ForwardPrequentialError("formal_p4_holm_family_changed")
    indexed = {key: index for index, key in enumerate(order)}
    ranked = sorted(order, key=lambda key: (float(p_values[key]), indexed[key]))
    adjusted: dict[str, float] = {}
    rejected: dict[str, bool] = {}
    running = 0.0
    earlier = True
    size = len(order)
    for rank, key in enumerate(ranked, start=1):
        raw = float(p_values[key])
        if not math.isfinite(raw) or not 0.0 <= raw <= 1.0:
            raise FormalP4ForwardPrequentialError("formal_p4_holm_p_invalid")
        running = max(running, (size - rank + 1) * raw)
        adjusted[key] = min(1.0, running)
        this_reject = earlier and raw <= FAMILYWISE_ALPHA / (size - rank + 1)
        rejected[key] = this_reject
        earlier = this_reject
    return {
        "canonical_order": list(order),
        "ranked_order": ranked,
        "raw_p_values": {key: float(p_values[key]) for key in order},
        "adjusted_p_values": {key: adjusted[key] for key in order},
        "rejected": {key: rejected[key] for key in order},
        "all_rejected": all(rejected.values()),
    }


def _child(
    *,
    control_id: str,
    identity: str,
    statistic: float,
    input_identity_digest: str,
    preregistration_digest: str,
    replicate_index: int | None,
    seed_digest: str | None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "contract_key": CONTRACT_KEY,
        "contract_digest": CONTRACT_DIGEST,
        "p3_input_identity_digest": input_identity_digest,
        "control_id": control_id,
        "child_identity": identity,
        "replicate_index": replicate_index,
        "seed_digest": seed_digest,
        "statistic_bits_per_issue": float(statistic),
        "status": "COMPLETE",
    }
    body.update(dict(extra or {}))
    return _artifact(
        artifact_type=CONTROL_CHILD_ARTIFACT_TYPE,
        body=body,
        parent_digests=(input_identity_digest, preregistration_digest),
    )


def execute_controls(
    *,
    bundle: Mapping[str, Any],
    input_identity: Mapping[str, Any],
    preregistration: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    identity = validate_artifact(input_identity)
    prereg = validate_artifact(preregistration)
    identity_digest = identity["artifact_digest"]
    prereg_digest = prereg["artifact_digest"]
    models = [_p3_artifact(item, p3.MODEL_ARTIFACT_TYPE) for item in bundle["models"]]
    settlements = [
        _p3_artifact(item, p3.SETTLEMENT_ARTIFACT_TYPE)
        for item in bundle["settlements"]
    ]
    q_values = [
        [float(value) for value in item["body"]["probabilities_q_1_to_33"]]
        for item in models
    ]
    targets = [list(item["body"]["actual_red_numbers"]) for item in settlements]
    gains = [float(item) for item in identity["body"]["observed_gains"]]
    n = len(gains)
    h = int(identity["body"]["training_horizon"])
    observed = math.fsum(gains) / n
    children: list[dict[str, Any]] = []
    distributions: dict[str, list[float]] = {key: [] for key in PRIMARY_CONTROL_ORDER}
    primary_seed_pairs: dict[str, list[list[object]]] = {
        key: []
        for key in (
            CONTROL_ORDER[0],
            CONTROL_ORDER[1],
            CONTROL_ORDER[4],
            CONTROL_ORDER[5],
        )
    }

    blocks = [list(range(start, start + 5)) for start in range(0, n, 5)]
    nc6_selected_look_pass_count = 0
    for replicate in range(PRIMARY_REPLICATES):
        seed_identity = (
            "M4_P4_FORWARD_PREQUENTIAL_FORMAL_V2|"
            "NC1_NONCIRCULAR_DERANGED_BLOCK_LABEL_PERMUTATION_L5|"
            f"replicate={replicate}|p3_input_identity={identity_digest}"
        )
        seed, seed_digest = _seed(seed_identity)
        primary_seed_pairs[CONTROL_ORDER[0]].append([seed_identity, seed])
        rng = np.random.Generator(np.random.PCG64(seed))
        block_count = len(blocks)
        permutation = None
        attempt_count = 0
        for attempt in range(128):
            candidate = [int(item) for item in rng.permutation(block_count)]
            attempt_count = attempt + 1
            if all(candidate[index] != index for index in range(block_count)):
                permutation = candidate
                break
        fallback = permutation is None
        rotation = None
        if permutation is None:
            rotation = 1 + seed % (block_count - 1)
            permutation = [
                (index + rotation) % block_count for index in range(block_count)
            ]
        target_order = [index for block in permutation for index in blocks[block]]
        statistic = (
            math.fsum(
                _gain(q_values[index], targets[target_order[index]])
                for index in range(n)
            )
            / n
        )
        distributions[CONTROL_ORDER[0]].append(statistic)
        children.append(
            _child(
                control_id=CONTROL_ORDER[0],
                identity=seed_identity,
                statistic=statistic,
                input_identity_digest=identity_digest,
                preregistration_digest=prereg_digest,
                replicate_index=replicate,
                seed_digest=seed_digest,
                extra={
                    "method": "NONCIRCULAR_DERANGED_BLOCK_LABEL_PERMUTATION_L5",
                    "attempt_count": attempt_count,
                    "fallback_used": fallback,
                    "rotation_if_any": rotation,
                    "block_order": permutation,
                },
            )
        )

    nc2_equivariant = True
    for replicate in range(PRIMARY_REPLICATES):
        seed_identity = (
            "M4_P4_FORWARD_PREQUENTIAL_FORMAL_V1|"
            f"{CONTROL_ORDER[1]}|none|{replicate}|{identity['body']['review_artifact_digest']}"
        )
        seed, seed_digest = _seed(seed_identity)
        primary_seed_pairs[CONTROL_ORDER[1]].append([seed_identity, seed])
        permutation = _non_identity_permutation(
            np.random.Generator(np.random.PCG64(seed)), 33
        )
        transformed = []
        for q, target in zip(q_values, targets, strict=True):
            q_new = [0.0] * 33
            target_new = []
            for old_index, new_index in enumerate(permutation):
                q_new[new_index] = q[old_index]
            for number in target:
                target_new.append(permutation[number - 1] + 1)
            transformed.append(_gain(q_new, target_new))
        statistic = math.fsum(transformed) / n
        exact = (
            max(abs(a - b) for a, b in zip(transformed, gains, strict=True))
            <= TOLERANCE
        )
        observed_decision = _p3_pass_predicate(observed, n)
        transformed_decision = _p3_pass_predicate(statistic, n)
        nc2_equivariant = (
            nc2_equivariant
            and exact
            and abs(statistic - observed) <= TOLERANCE
            and transformed_decision == observed_decision
        )
        children.append(
            _child(
                control_id=CONTROL_ORDER[1],
                identity=seed_identity,
                statistic=statistic,
                input_identity_digest=identity_digest,
                preregistration_digest=prereg_digest,
                replicate_index=replicate,
                seed_digest=seed_digest,
                extra={
                    "equivariance_verified": exact,
                    "selected_look": n,
                    "selected_look_decision": (
                        "PASS_TO_P4" if transformed_decision else "NOT_PASS_TO_P4"
                    ),
                    "selected_look_decision_identity": (
                        transformed_decision == observed_decision
                    ),
                },
            )
        )

    shifts: list[float] = []
    shift_pass_predicates: list[bool] = []
    for shift in (item for item in SHIFT_SET if item < n):
        statistic = (
            math.fsum(
                _gain(q_values[index], targets[(index + shift) % n])
                for index in range(n)
            )
            / n
        )
        shifts.append(statistic)
        shift_pass_predicates.append(_p3_pass_predicate(statistic, n))
        children.append(
            _child(
                control_id=CONTROL_ORDER[2],
                identity=f"CIRCULAR_SHIFT_K={shift}",
                statistic=statistic,
                input_identity_digest=identity_digest,
                preregistration_digest=prereg_digest,
                replicate_index=None,
                seed_digest=None,
                extra={"shift": shift, "rng": "NONE"},
            )
        )

    q_digest = _canonical_payload_sha256({"q": q_values})
    gain_digest = _canonical_payload_sha256({"gains": gains})
    decision_input_digest = _canonical_payload_sha256(
        {"observed": observed, "threshold": p3.PRACTICAL_THRESHOLD}
    )
    sentinels: list[dict[str, Any]] = []
    for ordinal, operator in enumerate(NC4_OPERATORS):
        sentinel = _artifact(
            artifact_type=NC4_SENTINEL_ARTIFACT_TYPE,
            body={
                "contract_key": CONTRACT_KEY,
                "contract_digest": CONTRACT_DIGEST,
                "p3_input_identity_digest": identity_digest,
                "control_id": CONTROL_ORDER[3],
                "operator_ordinal": ordinal,
                "operator_identity_utf8": operator,
                "input_shape": "[N,0]",
                "output_shape": "[N,0]",
                "dtype": "float64_empty",
                "rng": "NONE",
                "seed": None,
                "seed_digest": None,
                "replicate_index": None,
                "target_access": "FORBIDDEN_BEFORE_VALUE_ACCESS",
                "q_digest_before": q_digest,
                "q_digest_after": q_digest,
                "gain_sequence_digest_before": gain_digest,
                "gain_sequence_digest_after": gain_digest,
                "decision_input_digest_before": decision_input_digest,
                "decision_input_digest_after": decision_input_digest,
                "status": "EXACT_IDENTITY_VERIFIED",
            },
            parent_digests=(identity_digest, prereg_digest),
        )
        sentinels.append(sentinel)
        children.append(sentinel)
    sentinel_set = _artifact(
        artifact_type=NC4_SENTINEL_SET_ARTIFACT_TYPE,
        body={
            "contract_key": CONTRACT_KEY,
            "contract_digest": CONTRACT_DIGEST,
            "control_id": CONTROL_ORDER[3],
            "operator_count": 3,
            "operator_identities": list(NC4_OPERATORS),
            "replicate_count": 0,
            "rng": "NONE",
            "seed": None,
            "seed_digest": None,
            "sentinel_digests": [item["artifact_digest"] for item in sentinels],
            "status": "COMPLETE_EXACT_SENTINEL_SET",
        },
        parent_digests=[item["artifact_digest"] for item in sentinels]
        + [identity_digest, prereg_digest],
    )
    children.append(sentinel_set)

    for replicate in range(PRIMARY_REPLICATES):
        transformed: list[float] = []
        seed_identity = (
            "M4_P4_FORWARD_PREQUENTIAL_FORMAL_V1|"
            f"{CONTROL_ORDER[4]}|none|{replicate}|"
            f"{identity['body']['review_artifact_digest']}"
        )
        seed, seed_digest = _seed(seed_identity)
        primary_seed_pairs[CONTROL_ORDER[4]].append([seed_identity, seed])
        rng = np.random.Generator(np.random.PCG64(seed))
        for q, target in zip(q_values, targets, strict=True):
            permutation = _non_identity_permutation(rng, 33)
            transformed.append(_gain([q[item] for item in permutation], target))
        statistic = math.fsum(transformed) / n
        distributions[CONTROL_ORDER[4]].append(statistic)
        children.append(
            _child(
                control_id=CONTROL_ORDER[4],
                identity=seed_identity,
                statistic=statistic,
                input_identity_digest=identity_digest,
                preregistration_digest=prereg_digest,
                replicate_index=replicate,
                seed_digest=seed_digest,
            )
        )

    for replicate in range(PRIMARY_REPLICATES):
        seed_identity = (
            "M4_P4_FORWARD_PREQUENTIAL_FORMAL_V1|"
            f"{CONTROL_ORDER[5]}|none|{replicate}|{identity['body']['review_artifact_digest']}"
        )
        seed, seed_digest = _seed(seed_identity)
        primary_seed_pairs[CONTROL_ORDER[5]].append([seed_identity, seed])
        rng = np.random.Generator(np.random.PCG64(seed))
        counts = np.zeros(33, dtype=np.int64)
        for _ in range(h):
            counts[rng.choice(33, size=6, replace=False)] += 1
        synthetic_gains: list[float] = []
        for _ in range(n):
            q = (counts.astype(np.float64) + UNIFORM_Q) / (int(counts.sum() / 6) + 1)
            target_zero = rng.choice(33, size=6, replace=False)
            target = [int(item) + 1 for item in target_zero]
            synthetic_gains.append(_gain(q.tolist(), target))
            counts[target_zero] += 1
        statistic = math.fsum(synthetic_gains) / n
        selected_look_pass = _p3_pass_predicate(statistic, n)
        nc6_selected_look_pass_count += int(selected_look_pass)
        distributions[CONTROL_ORDER[5]].append(statistic)
        children.append(
            _child(
                control_id=CONTROL_ORDER[5],
                identity=seed_identity,
                statistic=statistic,
                input_identity_digest=identity_digest,
                preregistration_digest=prereg_digest,
                replicate_index=replicate,
                seed_digest=seed_digest,
                extra={
                    "selected_look": n,
                    "selected_look_decision": (
                        "PASS_TO_P4" if selected_look_pass else "NOT_PASS_TO_P4"
                    ),
                    "selected_look_pass": selected_look_pass,
                },
            )
        )

    primary_p = {
        key: (1 + sum(value >= observed for value in distributions[key]))
        / (PRIMARY_REPLICATES + 1)
        for key in PRIMARY_CONTROL_ORDER
    }
    primary_holm = holm(primary_p, PRIMARY_CONTROL_ORDER)
    quantiles = {key: _hf7(distributions[key]) for key in PRIMARY_CONTROL_ORDER}
    margin = min(observed - quantiles[key] for key in PRIMARY_CONTROL_ORDER)

    sensitivity_values: dict[str, list[float]] = {key: [] for key in SENSITIVITY_ORDER}
    sensitivity_seed_pairs: list[list[object]] = []
    for test_id in SENSITIVITY_ORDER:
        length = int(
            test_id.rsplit("L", 1)[-1]
            if "_L" in test_id
            else test_id.rsplit("E", 1)[-1]
        )
        for replicate in range(SENSITIVITY_REPLICATES):
            if test_id.startswith("S1_"):
                template = (
                    "M4_P4_FORWARD_PREQUENTIAL_FORMAL_V2|S1_MOVING_BLOCK|"
                    f"topology=NONCIRCULAR|L={length}|replicate={replicate}|"
                    f"p3_input_identity={identity_digest}"
                )
            else:
                template = (
                    "M4_P4_FORWARD_PREQUENTIAL_FORMAL_V2|S2_STATIONARY|"
                    f"topology=CIRCULAR|E={length}|replicate={replicate}|"
                    f"p3_input_identity={identity_digest}"
                )
            seed, seed_digest = _seed(template)
            sensitivity_seed_pairs.append([template, seed])
            rng = np.random.Generator(np.random.PCG64(seed))
            indices: list[int] = []
            if test_id.startswith("S1_"):
                while len(indices) < n:
                    start = int(rng.integers(0, n - length + 1))
                    indices.extend(range(start, start + length))
                indices = indices[:n]
            else:
                current = int(rng.integers(0, n))
                indices.append(current)
                while len(indices) < n:
                    if float(rng.random()) < 1.0 / length:
                        current = int(rng.integers(0, n))
                    else:
                        current = (current + 1) % n
                    indices.append(current)
            t_star = math.fsum(gains[index] for index in indices) / n
            centered = t_star - observed
            sensitivity_values[test_id].append(centered)
            children.append(
                _child(
                    control_id=test_id,
                    identity=template,
                    statistic=centered,
                    input_identity_digest=identity_digest,
                    preregistration_digest=prereg_digest,
                    replicate_index=replicate,
                    seed_digest=seed_digest,
                    extra={"centered_null": True},
                )
            )
    sensitivity_p = {
        key: (1 + sum(value >= observed for value in sensitivity_values[key]))
        / (SENSITIVITY_REPLICATES + 1)
        for key in SENSITIVITY_ORDER
    }
    sensitivity_holm = holm(sensitivity_p, SENSITIVITY_ORDER)
    sensitivity_bounds = {
        key: observed - _hf7(sensitivity_values[key]) for key in SENSITIVITY_ORDER
    }
    half = n // 2
    third = n // 3
    halves = [math.fsum(gains[:half]) / half, math.fsum(gains[half:]) / (n - half)]
    thirds = [
        math.fsum(gains[:third]) / third,
        math.fsum(gains[third : 2 * third]) / third,
        math.fsum(gains[2 * third :]) / (n - 2 * third),
    ]
    leave_one = [(math.fsum(gains) - value) / (n - 1) for value in gains]
    leave_blocks = [
        math.fsum(gains[:start] + gains[start + 5 :]) / (n - 5)
        for start in range(n - 4)
    ]
    summary = {
        "observed_mean_gain_bits_per_issue": observed,
        "primary_control_order": list(PRIMARY_CONTROL_ORDER),
        "primary_raw_p_values": primary_p,
        "primary_holm": primary_holm,
        "primary_q95": quantiles,
        "primary_margin": margin,
        "nc6_selected_look_pass_count": nc6_selected_look_pass_count,
        "nc6_selected_look_false_positive_rate": (
            nc6_selected_look_pass_count / PRIMARY_REPLICATES
        ),
        "primary_seed_set_digests": {
            key: m4_v2_domain_digest(
                {"control_id": key, "ordered_seed_pairs": primary_seed_pairs[key]},
                domain="dehps.m4.p4.primary-control-seed-set.v3",
            )
            for key in primary_seed_pairs
        },
        "nc2_equivariance_pass": nc2_equivariant,
        "nc3_shift_statistics": shifts,
        "nc3_gate_pass": bool(shifts)
        and observed > max(shifts)
        and not any(shift_pass_predicates),
        "nc4_sentinel_pass": len(sentinels) == 3,
        "sensitivity_order": list(SENSITIVITY_ORDER),
        "sensitivity_seed_set_digest": m4_v2_domain_digest(
            {
                "canonical_test_order": list(SENSITIVITY_ORDER),
                "ordered_seed_pairs": sensitivity_seed_pairs,
            },
            domain="dehps.m4.p4.sensitivity-seed-set.v2",
        ),
        "sensitivity_holm": sensitivity_holm,
        "sensitivity_lower_bounds": sensitivity_bounds,
        "s3_halves": halves,
        "s3_pass": all(value > 0.0 for value in halves),
        "s4_thirds": thirds,
        "s4_pass": sum(value > 0.0 for value in thirds) >= 2
        and all(value > -0.05 for value in thirds),
        "s5_min_leave_one": min(leave_one),
        "s5_min_leave_block_l5": min(leave_blocks),
        "s5_pass": min(leave_one) > 0.0 and min(leave_blocks) > 0.0,
        "child_count": len(children),
        "seed_completeness": True,
        "input_identity_valid": True,
        "leakage_gates_pass": True,
        "all_values_finite": True,
    }
    return children, summary


def build_execution_artifact(
    *,
    preregistration: Mapping[str, Any],
    input_identity: Mapping[str, Any],
    children: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    prereg = validate_artifact(preregistration)
    identity = validate_artifact(input_identity)
    validated = [validate_artifact(item) for item in children]
    if int(summary.get("child_count", -1)) != len(validated):
        raise FormalP4ForwardPrequentialError("formal_p4_child_count_changed")
    valid_input = identity["body"].get("status") == "VALIDATED_RESULT_INPUT_IDENTITY"
    return _artifact(
        artifact_type=EXECUTION_ARTIFACT_TYPE,
        body={
            "contract_key": CONTRACT_KEY,
            "contract_digest": CONTRACT_DIGEST,
            "status": "COMPLETE",
            "formal_p4_execution": (
                "EXECUTED_AFTER_VALID_PASS"
                if valid_input
                else "INVALID_BEFORE_WORKLOAD"
            ),
            "control_order": list(CONTROL_ORDER),
            "summary": deepcopy(dict(summary)),
            "child_digests": [item["artifact_digest"] for item in validated],
            "diagnostic_p4_decision_credit": False,
            "p5_started": False,
            "promotion_triggered": False,
        },
        parent_digests=[prereg["artifact_digest"], identity["artifact_digest"]]
        + [item["artifact_digest"] for item in validated],
    )


def _finite_numbers(value: object) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, Mapping):
        return all(_finite_numbers(item) for item in value.values())
    if isinstance(value, Sequence):
        return all(_finite_numbers(item) for item in value)
    return False


def _expected_seed_identity(
    *, control_id: str, replicate: int, input_identity: Mapping[str, Any]
) -> str:
    identity_digest = str(input_identity["artifact_digest"])
    review_digest = str(input_identity["body"]["review_artifact_digest"])
    if control_id == CONTROL_ORDER[0]:
        return (
            "M4_P4_FORWARD_PREQUENTIAL_FORMAL_V2|"
            "NC1_NONCIRCULAR_DERANGED_BLOCK_LABEL_PERMUTATION_L5|"
            f"replicate={replicate}|p3_input_identity={identity_digest}"
        )
    if control_id in {CONTROL_ORDER[1], CONTROL_ORDER[4], CONTROL_ORDER[5]}:
        return (
            "M4_P4_FORWARD_PREQUENTIAL_FORMAL_V1|"
            f"{control_id}|none|{replicate}|{review_digest}"
        )
    if control_id.startswith("S1_MOVING_BLOCK_L"):
        length = int(control_id.rsplit("L", 1)[-1])
        return (
            "M4_P4_FORWARD_PREQUENTIAL_FORMAL_V2|S1_MOVING_BLOCK|"
            f"topology=NONCIRCULAR|L={length}|replicate={replicate}|"
            f"p3_input_identity={identity_digest}"
        )
    if control_id.startswith("S2_STATIONARY_E"):
        length = int(control_id.rsplit("E", 1)[-1])
        return (
            "M4_P4_FORWARD_PREQUENTIAL_FORMAL_V2|S2_STATIONARY|"
            f"topology=CIRCULAR|E={length}|replicate={replicate}|"
            f"p3_input_identity={identity_digest}"
        )
    raise FormalP4ForwardPrequentialError("formal_p4_seed_control_unknown")


def verify_execution_completeness(
    *,
    execution: Mapping[str, Any],
    input_identity: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    children: Sequence[Mapping[str, Any]],
    integrity_reasons: Sequence[str] = (),
) -> tuple[list[str], dict[str, Any]]:
    execution = validate_artifact(execution)
    identity = validate_artifact(input_identity)
    prereg = validate_artifact(preregistration)
    summary = deepcopy(dict(execution["body"].get("summary", {})))
    if prereg["body"].get("fixture") is True:
        return [], summary
    reasons = [str(item) for item in integrity_reasons]
    if prereg != frozen_preregistration():
        reasons.append("PREREGISTRATION_IDENTITY")
    projection = identity["body"].get("derived_projection")
    projection_digest = identity["body"].get("derived_projection_digest")
    projection_fields = (
        "source_digest",
        "review_artifact_digest",
        "review_look",
        "review_issues",
        "settlement_artifact_digests",
        "settlement_replay_artifact_digests",
        "checkpoint_artifact_digests",
        "model_artifact_digests",
        "dataset_artifact_digests",
        "preregistration_artifact_digest",
        "lineage_id_derived",
        "configuration_status_derived",
    )
    if (
        identity["body"].get("contract_key") != CONTRACT_KEY
        or identity["body"].get("contract_digest") != CONTRACT_DIGEST
        or identity["body"].get("status") != "VALIDATED_RESULT_INPUT_IDENTITY"
        or not isinstance(projection, dict)
        or projection.get("schema_version")
        != "dehps-m4-p4-successor-p3-input-identity-projection.v1"
        or any(
            identity["body"].get(key) != projection.get(key)
            for key in projection_fields
        )
        or projection.get("source_digest") != P3_SOURCE_DIGEST
        or projection.get("preregistration_artifact_digest")
        != P3_PREREGISTRATION_DIGEST
        or projection.get("lineage_id_derived") != p3.LINEAGE_ID
        or projection.get("configuration_status_derived") != "NO_DRIFT"
        or m4_v2_domain_digest(
            projection,
            domain="dehps.m4.p4.successor-p3-input-identity-projection.v1",
        )
        != projection_digest
    ):
        reasons.append("INPUT_IDENTITY_PROJECTION")
    if isinstance(projection, dict):
        parent_list_fields = (
            "settlement_artifact_digests",
            "settlement_replay_artifact_digests",
            "checkpoint_artifact_digests",
            "model_artifact_digests",
            "dataset_artifact_digests",
        )
        if not all(isinstance(projection.get(key), list) for key in parent_list_fields):
            reasons.append("INPUT_IDENTITY_PARENT_ORDER")
        else:
            expected_identity_parents = [
                str(projection.get("review_artifact_digest") or ""),
                *[
                    str(item)
                    for key in parent_list_fields
                    for item in projection.get(key, ())
                ],
                str(projection.get("preregistration_artifact_digest") or ""),
                str(projection.get("source_digest") or ""),
            ]
            if identity["parent_digests"] != expected_identity_parents:
                reasons.append("INPUT_IDENTITY_PARENT_ORDER")
    try:
        validated = [validate_artifact(item) for item in children]
    except FormalP4ForwardPrequentialError:
        validated = []
        reasons.append("CHILD_ARTIFACT_IDENTITY")
    child_digests = [item["artifact_digest"] for item in validated]
    if (
        execution["body"].get("contract_key") != CONTRACT_KEY
        or execution["body"].get("contract_digest") != CONTRACT_DIGEST
        or execution["body"].get("status") != "COMPLETE"
        or execution["body"].get("formal_p4_execution")
        != (
            "EXECUTED_AFTER_VALID_PASS"
            if identity["body"].get("status") == "VALIDATED_RESULT_INPUT_IDENTITY"
            else "INVALID_BEFORE_WORKLOAD"
        )
        or execution["body"].get("control_order") != list(CONTROL_ORDER)
        or execution["body"].get("diagnostic_p4_decision_credit") is not False
        or execution["body"].get("p5_started") is not False
        or execution["body"].get("promotion_triggered") is not False
        or execution["body"].get("child_digests") != child_digests
        or execution["parent_digests"]
        != [prereg["artifact_digest"], identity["artifact_digest"], *child_digests]
        or summary.get("child_count") != len(validated)
    ):
        reasons.append("EXECUTION_PARENT_OR_CHILD_ORDER")
    n = int(identity["body"].get("review_look", 0))
    gains = [float(item) for item in identity["body"].get("observed_gains", ())]
    shifts = [item for item in SHIFT_SET if item < n]
    expected_count = (
        4 * PRIMARY_REPLICATES
        + len(shifts)
        + 4
        + len(SENSITIVITY_ORDER) * SENSITIVITY_REPLICATES
    )
    if n not in PASS_LOOKS or len(gains) != n or len(validated) != expected_count:
        reasons.append("CHILD_CARDINALITY")
    if (
        not isinstance(projection, dict)
        or len(projection.get("review_issues", ())) != n
        or len(set(projection.get("review_issues", ()))) != n
        or any(
            len(projection.get(key, ())) != n
            for key in (
                "settlement_artifact_digests",
                "settlement_replay_artifact_digests",
                "checkpoint_artifact_digests",
                "model_artifact_digests",
                "dataset_artifact_digests",
            )
        )
        or int(identity["body"].get("training_horizon", 0)) <= 0
        or not all(math.isfinite(value) for value in gains)
        or not math.isclose(
            float(
                identity["body"].get("observed_mean_gain_bits_per_issue", float("nan"))
            ),
            math.fsum(gains) / n if n else float("nan"),
            rel_tol=0.0,
            abs_tol=TOLERANCE,
        )
        or not _p3_pass_predicate(math.fsum(gains) / n, n)
    ):
        reasons.append("P3_PASS_INPUT_PREDICATE")
    control_children = [
        item
        for item in validated
        if item["artifact_type"] == CONTROL_CHILD_ARTIFACT_TYPE
    ]
    sentinels = [
        item
        for item in validated
        if item["artifact_type"] == NC4_SENTINEL_ARTIFACT_TYPE
    ]
    sentinel_sets = [
        item
        for item in validated
        if item["artifact_type"] == NC4_SENTINEL_SET_ARTIFACT_TYPE
    ]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for child in control_children:
        grouped.setdefault(str(child["body"].get("control_id")), []).append(child)
        if (
            child["body"].get("contract_key") != CONTRACT_KEY
            or child["body"].get("contract_digest") != CONTRACT_DIGEST
            or child["body"].get("p3_input_identity_digest")
            != identity["artifact_digest"]
            or child["parent_digests"]
            != [identity["artifact_digest"], prereg["artifact_digest"]]
            or not math.isfinite(
                float(child["body"].get("statistic_bits_per_issue", float("nan")))
            )
            or child["body"].get("status") != "COMPLETE"
        ):
            reasons.append("CHILD_CONTENT_OR_PARENT")
    expected_order: list[tuple[str, str, object]] = []
    for control_id in (CONTROL_ORDER[0], CONTROL_ORDER[1]):
        expected_order.extend(
            (CONTROL_CHILD_ARTIFACT_TYPE, control_id, replicate)
            for replicate in range(PRIMARY_REPLICATES)
        )
    expected_order.extend(
        (CONTROL_CHILD_ARTIFACT_TYPE, CONTROL_ORDER[2], shift) for shift in shifts
    )
    expected_order.extend(
        (NC4_SENTINEL_ARTIFACT_TYPE, CONTROL_ORDER[3], ordinal) for ordinal in range(3)
    )
    expected_order.append((NC4_SENTINEL_SET_ARTIFACT_TYPE, CONTROL_ORDER[3], "SET"))
    for control_id in (CONTROL_ORDER[4], CONTROL_ORDER[5]):
        expected_order.extend(
            (CONTROL_CHILD_ARTIFACT_TYPE, control_id, replicate)
            for replicate in range(PRIMARY_REPLICATES)
        )
    for control_id in SENSITIVITY_ORDER:
        expected_order.extend(
            (CONTROL_CHILD_ARTIFACT_TYPE, control_id, replicate)
            for replicate in range(SENSITIVITY_REPLICATES)
        )
    actual_order: list[tuple[str, str, object]] = []
    for child in validated:
        body = child["body"]
        ordinal: object = body.get("replicate_index")
        if (
            child["artifact_type"] == CONTROL_CHILD_ARTIFACT_TYPE
            and body.get("control_id") == CONTROL_ORDER[2]
        ):
            ordinal = body.get("shift")
        elif child["artifact_type"] == NC4_SENTINEL_ARTIFACT_TYPE:
            ordinal = body.get("operator_ordinal")
        elif child["artifact_type"] == NC4_SENTINEL_SET_ARTIFACT_TYPE:
            ordinal = "SET"
        actual_order.append(
            (child["artifact_type"], str(body.get("control_id")), ordinal)
        )
    if actual_order != expected_order:
        reasons.append("FROZEN_CHILD_ORDER")
    stochastic = {
        CONTROL_ORDER[0]: PRIMARY_REPLICATES,
        CONTROL_ORDER[1]: PRIMARY_REPLICATES,
        CONTROL_ORDER[4]: PRIMARY_REPLICATES,
        CONTROL_ORDER[5]: PRIMARY_REPLICATES,
        **{key: SENSITIVITY_REPLICATES for key in SENSITIVITY_ORDER},
    }
    seed_pairs: dict[str, list[list[object]]] = {}
    for control_id, count in stochastic.items():
        items = grouped.get(control_id, [])
        indices = [item["body"].get("replicate_index") for item in items]
        identities = [str(item["body"].get("child_identity") or "") for item in items]
        if indices != list(range(count)) or len(set(identities)) != count:
            reasons.append(f"{control_id}_REPLICATE_COMPLETENESS")
            continue
        pairs: list[list[object]] = []
        for replicate, item in enumerate(items):
            expected_identity = _expected_seed_identity(
                control_id=control_id,
                replicate=replicate,
                input_identity=identity,
            )
            seed, seed_digest = _seed(expected_identity)
            if (
                item["body"].get("child_identity") != expected_identity
                or item["body"].get("seed_digest") != seed_digest
            ):
                reasons.append(f"{control_id}_SEED_IDENTITY")
            pairs.append([expected_identity, seed])
        seed_pairs[control_id] = pairs
    nc3 = grouped.get(CONTROL_ORDER[2], [])
    if [item["body"].get("shift") for item in nc3] != shifts or any(
        item["body"].get("replicate_index") is not None
        or item["body"].get("seed_digest") is not None
        or item["body"].get("rng") != "NONE"
        or item["body"].get("child_identity")
        != f"CIRCULAR_SHIFT_K={item['body'].get('shift')}"
        for item in nc3
    ):
        reasons.append("NC3_DETERMINISTIC_COMPLETENESS")
    if any(
        item["body"].get("centered_null") is not True
        for key in SENSITIVITY_ORDER
        for item in grouped.get(key, ())
    ):
        reasons.append("SENSITIVITY_CENTERED_NULL_IDENTITY")
    if len(sentinels) != 3 or len(sentinel_sets) != 1:
        reasons.append("NC4_CARDINALITY")
    else:
        for ordinal, (operator, sentinel) in enumerate(
            zip(NC4_OPERATORS, sentinels, strict=True)
        ):
            body = sentinel["body"]
            if (
                set(body)
                != {
                    "contract_key",
                    "contract_digest",
                    "p3_input_identity_digest",
                    "control_id",
                    "operator_ordinal",
                    "operator_identity_utf8",
                    "input_shape",
                    "output_shape",
                    "dtype",
                    "rng",
                    "seed",
                    "seed_digest",
                    "replicate_index",
                    "target_access",
                    "q_digest_before",
                    "q_digest_after",
                    "gain_sequence_digest_before",
                    "gain_sequence_digest_after",
                    "decision_input_digest_before",
                    "decision_input_digest_after",
                    "status",
                }
                or body.get("contract_key") != CONTRACT_KEY
                or body.get("contract_digest") != CONTRACT_DIGEST
                or body.get("p3_input_identity_digest") != identity["artifact_digest"]
                or body.get("control_id") != CONTROL_ORDER[3]
                or body.get("operator_ordinal") != ordinal
                or body.get("operator_identity_utf8") != operator
                or body.get("input_shape") != "[N,0]"
                or body.get("output_shape") != "[N,0]"
                or body.get("dtype") != "float64_empty"
                or body.get("rng") != "NONE"
                or body.get("seed") is not None
                or body.get("seed_digest") is not None
                or body.get("replicate_index") is not None
                or body.get("target_access") != "FORBIDDEN_BEFORE_VALUE_ACCESS"
                or body.get("status") != "EXACT_IDENTITY_VERIFIED"
                or body.get("q_digest_before") != body.get("q_digest_after")
                or body.get("gain_sequence_digest_before")
                != body.get("gain_sequence_digest_after")
                or body.get("decision_input_digest_before")
                != body.get("decision_input_digest_after")
                or sentinel["parent_digests"]
                != [identity["artifact_digest"], prereg["artifact_digest"]]
            ):
                reasons.append("NC4_SENTINEL_IDENTITY")
        sentinel_set = sentinel_sets[0]
        if (
            set(sentinel_set["body"])
            != {
                "contract_key",
                "contract_digest",
                "control_id",
                "operator_count",
                "operator_identities",
                "replicate_count",
                "rng",
                "seed",
                "seed_digest",
                "sentinel_digests",
                "status",
            }
            or sentinel_set["body"].get("contract_key") != CONTRACT_KEY
            or sentinel_set["body"].get("contract_digest") != CONTRACT_DIGEST
            or sentinel_set["body"].get("control_id") != CONTROL_ORDER[3]
            or sentinel_set["body"].get("operator_count") != 3
            or sentinel_set["body"].get("replicate_count") != 0
            or sentinel_set["body"].get("rng") != "NONE"
            or sentinel_set["body"].get("seed") is not None
            or sentinel_set["body"].get("seed_digest") is not None
            or sentinel_set["body"].get("status") != "COMPLETE_EXACT_SENTINEL_SET"
            or sentinel_set["body"].get("operator_identities") != list(NC4_OPERATORS)
            or sentinel_set["body"].get("sentinel_digests")
            != [item["artifact_digest"] for item in sentinels]
            or sentinel_set["parent_digests"]
            != [item["artifact_digest"] for item in sentinels]
            + [identity["artifact_digest"], prereg["artifact_digest"]]
        ):
            reasons.append("NC4_SENTINEL_SET_IDENTITY")
    if reasons:
        return sorted(set(reasons)), summary
    observed = math.fsum(gains) / n
    primary_values = {
        key: [float(item["body"]["statistic_bits_per_issue"]) for item in grouped[key]]
        for key in PRIMARY_CONTROL_ORDER
    }
    primary_p = {
        key: (1 + sum(value >= observed for value in values)) / (PRIMARY_REPLICATES + 1)
        for key, values in primary_values.items()
    }
    primary_holm = holm(primary_p, PRIMARY_CONTROL_ORDER)
    primary_q95 = {key: _hf7(values) for key, values in primary_values.items()}
    sensitivity_values = {
        key: [float(item["body"]["statistic_bits_per_issue"]) for item in grouped[key]]
        for key in SENSITIVITY_ORDER
    }
    sensitivity_p = {
        key: (1 + sum(value >= observed for value in values))
        / (SENSITIVITY_REPLICATES + 1)
        for key, values in sensitivity_values.items()
    }
    sensitivity_holm = holm(sensitivity_p, SENSITIVITY_ORDER)
    nc6_children = grouped[CONTROL_ORDER[5]]
    nc6_selected_look_pass_count = 0
    for child in nc6_children:
        statistic = float(child["body"]["statistic_bits_per_issue"])
        selected_look_pass = _p3_pass_predicate(statistic, n)
        nc6_selected_look_pass_count += int(selected_look_pass)
        if (
            child["body"].get("selected_look") != n
            or child["body"].get("selected_look_pass") is not selected_look_pass
            or child["body"].get("selected_look_decision")
            != ("PASS_TO_P4" if selected_look_pass else "NOT_PASS_TO_P4")
        ):
            reasons.append("NC6_SELECTED_LOOK_COMPILER")
    half = n // 2
    third = n // 3
    halves = [math.fsum(gains[:half]) / half, math.fsum(gains[half:]) / (n - half)]
    thirds = [
        math.fsum(gains[:third]) / third,
        math.fsum(gains[third : 2 * third]) / third,
        math.fsum(gains[2 * third :]) / (n - 2 * third),
    ]
    leave_one = [(math.fsum(gains) - value) / (n - 1) for value in gains]
    leave_blocks = [
        math.fsum(gains[:start] + gains[start + 5 :]) / (n - 5)
        for start in range(n - 4)
    ]
    recomputed = {
        "observed_mean_gain_bits_per_issue": observed,
        "primary_raw_p_values": primary_p,
        "primary_holm": primary_holm,
        "primary_q95": primary_q95,
        "primary_margin": min(observed - value for value in primary_q95.values()),
        "primary_control_order": list(PRIMARY_CONTROL_ORDER),
        "nc6_selected_look_pass_count": nc6_selected_look_pass_count,
        "nc6_selected_look_false_positive_rate": (
            nc6_selected_look_pass_count / PRIMARY_REPLICATES
        ),
        "primary_seed_set_digests": {
            key: m4_v2_domain_digest(
                {"control_id": key, "ordered_seed_pairs": seed_pairs[key]},
                domain="dehps.m4.p4.primary-control-seed-set.v3",
            )
            for key in (
                CONTROL_ORDER[0],
                CONTROL_ORDER[1],
                CONTROL_ORDER[4],
                CONTROL_ORDER[5],
            )
        },
        "nc2_equivariance_pass": all(
            item["body"].get("equivariance_verified") is True
            and abs(float(item["body"]["statistic_bits_per_issue"]) - observed)
            <= TOLERANCE
            and item["body"].get("selected_look") == n
            and item["body"].get("selected_look_decision")
            == (
                "PASS_TO_P4"
                if _p3_pass_predicate(
                    float(item["body"]["statistic_bits_per_issue"]), n
                )
                else "NOT_PASS_TO_P4"
            )
            and item["body"].get("selected_look_decision_identity") is True
            and _p3_pass_predicate(float(item["body"]["statistic_bits_per_issue"]), n)
            == _p3_pass_predicate(observed, n)
            for item in grouped[CONTROL_ORDER[1]]
        ),
        "nc3_shift_statistics": [
            float(item["body"]["statistic_bits_per_issue"]) for item in nc3
        ],
        "nc4_sentinel_pass": True,
        "sensitivity_order": list(SENSITIVITY_ORDER),
        "sensitivity_seed_set_digest": m4_v2_domain_digest(
            {
                "canonical_test_order": list(SENSITIVITY_ORDER),
                "ordered_seed_pairs": [
                    pair for key in SENSITIVITY_ORDER for pair in seed_pairs[key]
                ],
            },
            domain="dehps.m4.p4.sensitivity-seed-set.v2",
        ),
        "sensitivity_holm": sensitivity_holm,
        "sensitivity_lower_bounds": {
            key: observed - _hf7(values) for key, values in sensitivity_values.items()
        },
        "s3_halves": halves,
        "s3_pass": all(value > 0.0 for value in halves),
        "s4_thirds": thirds,
        "s4_pass": sum(value > 0.0 for value in thirds) >= 2
        and all(value > -0.05 for value in thirds),
        "s5_min_leave_one": min(leave_one),
        "s5_min_leave_block_l5": min(leave_blocks),
        "s5_pass": min(leave_one) > 0.0 and min(leave_blocks) > 0.0,
    }
    shifted = recomputed["nc3_shift_statistics"]
    recomputed["nc3_gate_pass"] = (
        bool(shifted)
        and observed > max(shifted)
        and not any(_p3_pass_predicate(value, n) for value in shifted)
    )
    for key, value in recomputed.items():
        if summary.get(key) != value:
            reasons.append(f"SUMMARY_{key.upper()}")
    if not _finite_numbers(summary):
        reasons.append("SUMMARY_NONFINITE")
    recomputed.update(
        {
            "child_count": len(validated),
            "input_identity_valid": True,
            "leakage_gates_pass": True,
            "seed_completeness": True,
            "all_values_finite": True,
        }
    )
    return sorted(set(reasons)), recomputed


def compile_evidence(
    *,
    execution: Mapping[str, Any],
    input_identity: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    children: Sequence[Mapping[str, Any]] = (),
    integrity_reasons: Sequence[str] = (),
) -> dict[str, Any]:
    execution = validate_artifact(execution)
    identity = validate_artifact(input_identity)
    prereg = validate_artifact(preregistration)
    try:
        invalid_reasons, summary = verify_execution_completeness(
            execution=execution,
            input_identity=identity,
            preregistration=prereg,
            children=children,
            integrity_reasons=integrity_reasons,
        )
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        invalid_reasons = [*integrity_reasons, "COMPLETENESS_VALIDATION_EXCEPTION"]
        summary = deepcopy(dict(execution["body"].get("summary", {})))
    if execution["parent_digests"][:2] != [
        prereg["artifact_digest"],
        identity["artifact_digest"],
    ]:
        invalid_reasons.append("PARENT_BINDING")
    for key in (
        "input_identity_valid",
        "leakage_gates_pass",
        "seed_completeness",
        "all_values_finite",
    ):
        if summary.get(key) is not True:
            invalid_reasons.append(key.upper())
    primary_holm = summary.get("primary_holm", {})
    sensitivity_holm = summary.get("sensitivity_holm", {})
    if not isinstance(primary_holm, Mapping):
        primary_holm = {}
    if not isinstance(sensitivity_holm, Mapping):
        sensitivity_holm = {}
    sensitivity_bounds = summary.get("sensitivity_lower_bounds", {})
    if not isinstance(sensitivity_bounds, Mapping):
        sensitivity_bounds = {}

    def safe_float(value: object) -> float:
        try:
            return float(value)
        except (TypeError, ValueError, OverflowError):
            return float("nan")

    scientific_gates = {
        "observed_threshold": safe_float(
            summary.get("observed_mean_gain_bits_per_issue")
        )
        >= p3.PRACTICAL_THRESHOLD,
        "primary_margin_positive": safe_float(summary.get("primary_margin")) > 0.0,
        "primary_holm_all_rejected": primary_holm.get("all_rejected") is True,
        "nc2_equivariance": summary.get("nc2_equivariance_pass") is True,
        "nc3_shift": summary.get("nc3_gate_pass") is True,
        "nc4_feature_absence": summary.get("nc4_sentinel_pass") is True,
        "sensitivity_holm_all_rejected": sensitivity_holm.get("all_rejected") is True,
        "sensitivity_bounds_positive": all(
            safe_float(value) > 0.0 for value in sensitivity_bounds.values()
        )
        and set(sensitivity_bounds) == set(SENSITIVITY_ORDER),
        "s3_halves": summary.get("s3_pass") is True,
        "s4_thirds": summary.get("s4_pass") is True,
        "s5_influence": summary.get("s5_pass") is True,
    }
    return _artifact(
        artifact_type=EVIDENCE_ARTIFACT_TYPE,
        body={
            "contract_key": CONTRACT_KEY,
            "contract_digest": CONTRACT_DIGEST,
            "status": "COMPILED",
            "invalid_reasons": invalid_reasons,
            "execution_valid": not invalid_reasons,
            "scientific_gates": scientific_gates,
            "all_scientific_gates_pass": all(scientific_gates.values()),
            "decision_set": [
                "P4_PASS_TO_P5",
                "P4_FAIL_NEGATIVE_CONTROLS_OR_ROBUSTNESS",
                "P4_INVALID_EXECUTION",
            ],
            "diagnostic_p4_decision_credit": False,
            "secondary_metrics_decision_credit": False,
        },
        parent_digests=(
            execution["artifact_digest"],
            identity["artifact_digest"],
            prereg["artifact_digest"],
        ),
    )


def compile_decision(
    *,
    evidence: Mapping[str, Any],
    execution: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    integrity_reasons: Sequence[str] = (),
) -> dict[str, Any]:
    evidence = validate_artifact(evidence)
    execution = validate_artifact(execution)
    prereg = validate_artifact(preregistration)
    if integrity_reasons or evidence["body"].get("execution_valid") is not True:
        decision = "P4_INVALID_EXECUTION"
        emitted_fact = INVALID_FACT
    elif evidence["body"].get("all_scientific_gates_pass") is True:
        decision = "P4_PASS_TO_P5"
        emitted_fact = PASS_TO_P5_FACT
    else:
        decision = "P4_FAIL_NEGATIVE_CONTROLS_OR_ROBUSTNESS"
        emitted_fact = FAIL_FACT
    return _artifact(
        artifact_type=DECISION_ARTIFACT_TYPE,
        body={
            "contract_key": CONTRACT_KEY,
            "contract_digest": CONTRACT_DIGEST,
            "status": "FROZEN_DECISION_COMPILED",
            "decision": decision,
            "emitted_fact": emitted_fact,
            "invalid_precedence": True,
            "binding_invalid_reasons": sorted(
                {str(item) for item in integrity_reasons}
            ),
            "p5_execution_authorized": False,
            "promotion_triggered": False,
        },
        parent_digests=(
            evidence["artifact_digest"],
            execution["artifact_digest"],
            prereg["artifact_digest"],
        ),
    )


def build_typed_replay(
    *,
    decision: Mapping[str, Any],
    evidence: Mapping[str, Any],
    execution: Mapping[str, Any],
    input_identity: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    children: Sequence[Mapping[str, Any]] = (),
    integrity_reasons: Sequence[str] = (),
) -> dict[str, Any]:
    decision = validate_artifact(decision)
    evidence = validate_artifact(evidence)
    execution = validate_artifact(execution)
    identity = validate_artifact(input_identity)
    prereg = validate_artifact(preregistration)
    reproduced_evidence = compile_evidence(
        execution=execution,
        input_identity=identity,
        preregistration=prereg,
        children=children,
        integrity_reasons=integrity_reasons,
    )
    if reproduced_evidence != evidence:
        raise FormalP4ForwardPrequentialError(
            "formal_p4_typed_replay_evidence_mismatch"
        )
    reproduced = compile_decision(
        evidence=reproduced_evidence, execution=execution, preregistration=prereg
    )
    if reproduced != decision:
        raise FormalP4ForwardPrequentialError("formal_p4_typed_replay_mismatch")
    return _artifact(
        artifact_type=REPLAY_ARTIFACT_TYPE,
        body={
            "contract_key": CONTRACT_KEY,
            "contract_digest": CONTRACT_DIGEST,
            "status": "TYPED_REPLAY_VERIFIED_AWAITING_GENERIC_REGISTERED_REPLAY",
            "decision_artifact_digest": decision["artifact_digest"],
            "decision": decision["body"]["decision"],
            "emitted_fact": decision["body"]["emitted_fact"],
            "same_registered_content": True,
            "workload_rerun": False,
        },
        parent_digests=(
            decision["artifact_digest"],
            evidence["artifact_digest"],
            execution["artifact_digest"],
            prereg["artifact_digest"],
        ),
    )


def synthetic_decision_fixture(decision: str) -> tuple[dict[str, Any], ...]:
    if decision not in {
        "P4_PASS_TO_P5",
        "P4_FAIL_NEGATIVE_CONTROLS_OR_ROBUSTNESS",
        "P4_INVALID_EXECUTION",
    }:
        raise FormalP4ForwardPrequentialError("formal_p4_fixture_decision_invalid")
    prereg = _artifact(
        artifact_type=PREREGISTRATION_ARTIFACT_TYPE,
        body={
            "contract_key": CONTRACT_KEY,
            "contract_digest": CONTRACT_DIGEST,
            "fixture": True,
        },
        parent_digests=("1" * 64, "2" * 64),
    )
    identity = _artifact(
        artifact_type=INPUT_IDENTITY_ARTIFACT_TYPE,
        body={
            "contract_key": CONTRACT_KEY,
            "contract_digest": CONTRACT_DIGEST,
            "fixture": True,
        },
        parent_digests=("3" * 64,),
    )
    scientific_pass = decision == "P4_PASS_TO_P5"
    valid = decision != "P4_INVALID_EXECUTION"
    summary = {
        "child_count": 0,
        "input_identity_valid": valid,
        "leakage_gates_pass": valid,
        "seed_completeness": valid,
        "all_values_finite": valid,
        "observed_mean_gain_bits_per_issue": 0.10,
        "primary_margin": 0.01 if scientific_pass else -0.01,
        "primary_holm": {"all_rejected": scientific_pass},
        "nc2_equivariance_pass": scientific_pass,
        "nc3_gate_pass": scientific_pass,
        "nc4_sentinel_pass": scientific_pass,
        "sensitivity_holm": {"all_rejected": scientific_pass},
        "sensitivity_lower_bounds": {
            key: 0.01 if scientific_pass else -0.01 for key in SENSITIVITY_ORDER
        },
        "s3_pass": scientific_pass,
        "s4_pass": scientific_pass,
        "s5_pass": scientific_pass,
    }
    execution = build_execution_artifact(
        preregistration=prereg,
        input_identity=identity,
        children=(),
        summary=summary,
    )
    evidence = compile_evidence(
        execution=execution, input_identity=identity, preregistration=prereg
    )
    decision_artifact = compile_decision(
        evidence=evidence, execution=execution, preregistration=prereg
    )
    replay = build_typed_replay(
        decision=decision_artifact,
        evidence=evidence,
        execution=execution,
        input_identity=identity,
        preregistration=prereg,
    )
    return prereg, identity, execution, evidence, decision_artifact, replay


@dataclass
class FormalP4ForwardPrequentialCapability(M4V2SuccessorCapability):
    repository: PostgresResearchOSRepository
    root_dir: Path = ROOT_DIR

    def __post_init__(self) -> None:
        self.agent_repository = AgentRequestRepository()

    def _source(self, task: Task) -> dict[str, Any]:
        source = load_source_contract(root_dir=self.root_dir)
        verify_governance(self.agent_repository)
        if task.input_artifact_digests != (str(source["artifact_digest"]),):
            raise MainlineSupervisorError("formal P4 V3 source input changed")
        return source

    def _load_p3_bundle(self, *, control_plane_key: str) -> dict[str, Any]:
        _, _, prereg = self._completed_artifact(
            control_plane_key=control_plane_key,
            task_key=p3.PREREGISTRATION_TASK_KEY,
            artifact_type=p3.PREREGISTRATION_ARTIFACT_TYPE,
        )
        review = None
        for look in PASS_LOOKS:
            try:
                _, _, candidate = self._completed_artifact(
                    control_plane_key=control_plane_key,
                    task_key=p3.review_task_key(look),
                    artifact_type=p3.REVIEW_ARTIFACT_TYPE,
                )
            except MainlineSupervisorError:
                continue
            if candidate.get("body", {}).get("decision") == "PASS_TO_P4":
                if review is not None:
                    raise MainlineSupervisorError("formal P4 has multiple PASS reviews")
                review = candidate
        if review is None:
            raise MainlineSupervisorError("formal P4 lacks one registered PASS review")
        issues = [str(item) for item in review["body"]["issues"]]
        output: dict[str, Any] = {
            "preregistration": prereg,
            "review": review,
            "settlements": [],
            "settlement_replays": [],
            "checkpoints": [],
            "models": [],
            "datasets": [],
            "model_candidates": [],
            "random_baselines": [],
        }
        for issue in issues:
            keys = p3.issue_task_keys(issue)
            requested = (
                ("settlements", keys["settlement"], p3.SETTLEMENT_ARTIFACT_TYPE),
                (
                    "settlement_replays",
                    keys["settlement_replay"],
                    p3.SETTLEMENT_REPLAY_ARTIFACT_TYPE,
                ),
                ("checkpoints", keys["predraw"], p3.CHECKPOINT_ARTIFACT_TYPE),
                ("models", keys["refit"], p3.MODEL_ARTIFACT_TYPE),
                ("datasets", keys["refit"], p3.DATASET_ARTIFACT_TYPE),
                ("model_candidates", keys["predraw"], p3.MODEL_CANDIDATE_ARTIFACT_TYPE),
                ("random_baselines", keys["predraw"], p3.RANDOM_BASELINE_ARTIFACT_TYPE),
            )
            for name, key, artifact_type in requested:
                _, _, artifact = self._completed_artifact(
                    control_plane_key=control_plane_key,
                    task_key=key,
                    artifact_type=artifact_type,
                )
                output[name].append(artifact)
        return output

    @staticmethod
    def _invalid_input(
        *, preregistration: Mapping[str, Any], reason: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
        identity = _artifact(
            artifact_type=INPUT_IDENTITY_ARTIFACT_TYPE,
            body={
                "contract_key": CONTRACT_KEY,
                "contract_digest": CONTRACT_DIGEST,
                "status": "INVALID_INPUT_IDENTITY",
                "invalid_reason": reason,
                "configuration_status_derived": "INVALID",
            },
            parent_digests=(preregistration["artifact_digest"], P3_SOURCE_DIGEST),
        )
        return (
            identity,
            [],
            {
                "child_count": 0,
                "input_identity_valid": False,
                "leakage_gates_pass": False,
                "seed_completeness": False,
                "all_values_finite": False,
                "invalid_reason": reason,
            },
        )

    @staticmethod
    def _execution_result(
        *,
        preregistration: Mapping[str, Any],
        input_identity: Mapping[str, Any],
        children: Sequence[Mapping[str, Any]],
        summary: Mapping[str, Any],
    ) -> AtomicCapabilityResult:
        prereg = validate_artifact(preregistration)
        identity = validate_artifact(input_identity)
        execution = build_execution_artifact(
            preregistration=prereg,
            input_identity=identity,
            children=children,
            summary=summary,
        )
        artifacts = [
            AtomicArtifactPayload(
                "formal-p4-v3-preregistration", "preregistration.json", prereg
            ),
            AtomicArtifactPayload(
                "formal-p4-v3-input-identity", "input-identity.json", identity
            ),
        ]
        artifacts.extend(
            AtomicArtifactPayload(
                f"formal-p4-v3-child-{index:05d}", "child.json", child
            )
            for index, child in enumerate(children)
        )
        artifacts.append(
            AtomicArtifactPayload("formal-p4-v3-execution", "execution.json", execution)
        )
        input_valid = (
            identity["body"].get("status") == "VALIDATED_RESULT_INPUT_IDENTITY"
        )
        return AtomicCapabilityResult(
            artifacts=tuple(artifacts),
            completion_facts=(EXECUTION_COMPLETE_FACT,),
            execution_metadata=(
                ("contract_digest", CONTRACT_DIGEST),
                (
                    "p3_lineage_id",
                    p3.LINEAGE_ID if input_valid else "INVALID_OR_UNKNOWN",
                ),
                (
                    "configuration_drift",
                    False if input_valid else "INVALID_OR_UNKNOWN",
                ),
                ("formal_p4_executed", input_valid),
                ("child_count", len(children)),
                ("diagnostic_p4_decision_credit", False),
                ("p5_started", False),
                ("promotion_triggered", False),
            ),
            actual_fold_count=int(identity["body"].get("review_look", 0)),
        )

    def _execution(
        self, *, control_plane_key: str, task: Task, source: Mapping[str, Any]
    ) -> AtomicCapabilityResult:
        prereg = formal_preregistration(source)
        try:
            bundle = self._load_p3_bundle(control_plane_key=control_plane_key)
            identity = build_p3_input_identity(bundle)
            children, summary = execute_controls(
                bundle=bundle, input_identity=identity, preregistration=prereg
            )
        except (
            MainlineSupervisorError,
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
        ) as exc:
            identity, children, summary = self._invalid_input(
                preregistration=prereg, reason=type(exc).__name__
            )
        return self._execution_result(
            preregistration=prereg,
            input_identity=identity,
            children=children,
            summary=summary,
        )

    def _registered_execution_children(
        self, *, control_plane_key: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        execution_record, _, execution = self._completed_artifact(
            control_plane_key=control_plane_key,
            task_key=EXECUTION_TASK_KEY,
            artifact_type=EXECUTION_ARTIFACT_TYPE,
        )
        registrations = self.repository.list_mainline_artifacts(
            control_plane_key=control_plane_key,
            execution_id=str(execution_record["execution_id"]),
        )
        by_digest: dict[str, dict[str, Any]] = {}
        integrity_reasons: list[str] = []
        allowed_types = {
            CONTROL_CHILD_ARTIFACT_TYPE,
            NC4_SENTINEL_ARTIFACT_TYPE,
            NC4_SENTINEL_SET_ARTIFACT_TYPE,
        }
        for registration in registrations:
            if registration.get("artifact_type") not in allowed_types:
                continue
            try:
                path = (self.root_dir / str(registration["artifact_path"])).resolve()
                if (
                    not path.is_relative_to(self.root_dir.resolve())
                    or not path.is_file()
                ):
                    raise FormalP4ForwardPrequentialError("child_path")
                artifact = validate_artifact(
                    json.loads(path.read_text(encoding="utf-8"))
                )
                digest = str(artifact["artifact_digest"])
                if (
                    registration.get("execution_id")
                    != str(execution_record["execution_id"])
                    or registration.get("control_plane_key") != control_plane_key
                    or registration.get("task_key") != EXECUTION_TASK_KEY
                    or registration.get("task_digest")
                    != execution_record.get("task_digest")
                    or registration.get("artifact_digest") != digest
                    or registration.get("artifact_type") != artifact["artifact_type"]
                    or registration.get("schema_version") != artifact["schema_version"]
                    or tuple(
                        str(item) for item in registration.get("parent_digests", ())
                    )
                    != tuple(artifact["parent_digests"])
                    or digest in by_digest
                ):
                    raise FormalP4ForwardPrequentialError("child_registration")
                by_digest[digest] = artifact
            except (
                FormalP4ForwardPrequentialError,
                KeyError,
                OSError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
            ):
                integrity_reasons.append("CHILD_REGISTRATION_OR_CONTENT")
        ordered_digests = [str(item) for item in execution["body"]["child_digests"]]
        if len(set(ordered_digests)) != len(ordered_digests):
            integrity_reasons.append("EXECUTION_CHILD_DIGEST_DUPLICATE")
        if set(by_digest) != set(ordered_digests):
            integrity_reasons.append("CHILD_REGISTRATION_SET")
        children = [
            by_digest[digest] for digest in ordered_digests if digest in by_digest
        ]
        return execution, children, sorted(set(integrity_reasons))

    def _execution_chain_fail_closed(
        self, *, control_plane_key: str
    ) -> tuple[
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
        list[dict[str, Any]],
        list[str],
    ]:
        reasons: list[str] = []
        try:
            _, _, prereg = self._completed_artifact(
                control_plane_key=control_plane_key,
                task_key=EXECUTION_TASK_KEY,
                artifact_type=PREREGISTRATION_ARTIFACT_TYPE,
            )
        except (MainlineSupervisorError, KeyError, TypeError, ValueError, OSError):
            prereg = frozen_preregistration()
            reasons.append("TOP_LEVEL_PREREGISTRATION_REGISTRATION")
        try:
            _, _, identity = self._completed_artifact(
                control_plane_key=control_plane_key,
                task_key=EXECUTION_TASK_KEY,
                artifact_type=INPUT_IDENTITY_ARTIFACT_TYPE,
            )
        except (MainlineSupervisorError, KeyError, TypeError, ValueError, OSError):
            identity, _, _ = self._invalid_input(
                preregistration=prereg,
                reason="TOP_LEVEL_INPUT_IDENTITY_REGISTRATION",
            )
            reasons.append("TOP_LEVEL_INPUT_IDENTITY_REGISTRATION")
        try:
            execution, children, child_reasons = self._registered_execution_children(
                control_plane_key=control_plane_key
            )
            reasons.extend(child_reasons)
        except (MainlineSupervisorError, KeyError, TypeError, ValueError, OSError):
            identity, children, summary = self._invalid_input(
                preregistration=prereg,
                reason="TOP_LEVEL_EXECUTION_REGISTRATION",
            )
            execution = build_execution_artifact(
                preregistration=prereg,
                input_identity=identity,
                children=children,
                summary=summary,
            )
            reasons.append("TOP_LEVEL_EXECUTION_REGISTRATION")
        return prereg, identity, execution, children, sorted(set(reasons))

    def _evidence(
        self,
        *,
        control_plane_key: str,
        task: Task,
        source: Mapping[str, Any],
        integrity_reasons: Sequence[str] = (),
    ) -> AtomicCapabilityResult:
        del source
        prereg, identity, execution, children, registration_reasons = (
            self._execution_chain_fail_closed(control_plane_key=control_plane_key)
        )
        evidence = compile_evidence(
            execution=execution,
            input_identity=identity,
            preregistration=prereg,
            children=children,
            integrity_reasons=(*integrity_reasons, *registration_reasons),
        )
        return AtomicCapabilityResult(
            artifacts=(
                AtomicArtifactPayload(
                    "formal-p4-v3-evidence", "evidence.json", evidence
                ),
            ),
            completion_facts=(EVIDENCE_COMPILED_FACT,),
            execution_metadata=(
                ("contract_digest", CONTRACT_DIGEST),
                ("evidence_created", True),
            ),
        )

    def _decision(
        self,
        *,
        control_plane_key: str,
        task: Task,
        source: Mapping[str, Any],
        integrity_reasons: Sequence[str] = (),
    ) -> AtomicCapabilityResult:
        del source
        prereg, identity, execution, children, chain_reasons = (
            self._execution_chain_fail_closed(control_plane_key=control_plane_key)
        )
        try:
            _, _, evidence = self._completed_artifact(
                control_plane_key=control_plane_key,
                task_key=EVIDENCE_TASK_KEY,
                artifact_type=EVIDENCE_ARTIFACT_TYPE,
            )
        except (MainlineSupervisorError, KeyError, TypeError, ValueError, OSError):
            chain_reasons.append("TOP_LEVEL_EVIDENCE_REGISTRATION")
            evidence = compile_evidence(
                execution=execution,
                input_identity=identity,
                preregistration=prereg,
                children=children,
                integrity_reasons=chain_reasons,
            )
        decision = compile_decision(
            evidence=evidence,
            execution=execution,
            preregistration=prereg,
            integrity_reasons=(*integrity_reasons, *chain_reasons),
        )
        emitted = str(decision["body"]["emitted_fact"])
        return AtomicCapabilityResult(
            artifacts=(
                AtomicArtifactPayload(
                    "formal-p4-v3-decision", "decision.json", decision
                ),
            ),
            completion_facts=(f"{DECISION_TASK_KEY}:COMPLETE",),
            execution_metadata=(
                ("contract_digest", CONTRACT_DIGEST),
                ("decision", decision["body"]["decision"]),
                ("outcome_fact_deferred_to_typed_replay", emitted),
                ("p5_started", False),
                ("promotion_triggered", False),
            ),
        )

    def _replay(
        self,
        *,
        control_plane_key: str,
        task: Task,
        source: Mapping[str, Any],
        integrity_reasons: Sequence[str] = (),
    ) -> AtomicCapabilityResult:
        del source
        prereg, identity, execution, children, registration_reasons = (
            self._execution_chain_fail_closed(control_plane_key=control_plane_key)
        )
        try:
            _, _, evidence = self._completed_artifact(
                control_plane_key=control_plane_key,
                task_key=EVIDENCE_TASK_KEY,
                artifact_type=EVIDENCE_ARTIFACT_TYPE,
            )
        except (MainlineSupervisorError, KeyError, TypeError, ValueError, OSError):
            registration_reasons.append("TOP_LEVEL_EVIDENCE_REGISTRATION")
            evidence = compile_evidence(
                execution=execution,
                input_identity=identity,
                preregistration=prereg,
                children=children,
                integrity_reasons=registration_reasons,
            )
        try:
            _, _, decision = self._completed_artifact(
                control_plane_key=control_plane_key,
                task_key=DECISION_TASK_KEY,
                artifact_type=DECISION_ARTIFACT_TYPE,
            )
        except (MainlineSupervisorError, KeyError, TypeError, ValueError, OSError):
            registration_reasons.append("TOP_LEVEL_DECISION_REGISTRATION")
            decision = compile_decision(
                evidence=evidence,
                execution=execution,
                preregistration=prereg,
                integrity_reasons=registration_reasons,
            )
        try:
            replay = build_typed_replay(
                decision=decision,
                evidence=evidence,
                execution=execution,
                input_identity=identity,
                preregistration=prereg,
                children=children,
                integrity_reasons=(*integrity_reasons, *registration_reasons),
            )
            completion_facts = (f"{REPLAY_TASK_KEY}:COMPLETE",)
        except FormalP4ForwardPrequentialError as exc:
            replay = _artifact(
                artifact_type=REPLAY_ARTIFACT_TYPE,
                body={
                    "contract_key": CONTRACT_KEY,
                    "contract_digest": CONTRACT_DIGEST,
                    "status": "P4_INVALID_EXECUTION",
                    "decision_artifact_digest": decision["artifact_digest"],
                    "decision": "P4_INVALID_EXECUTION",
                    "emitted_fact": INVALID_FACT,
                    "same_registered_content": False,
                    "workload_rerun": False,
                    "invalid_reason": type(exc).__name__,
                },
                parent_digests=(
                    decision["artifact_digest"],
                    evidence["artifact_digest"],
                    execution["artifact_digest"],
                    prereg["artifact_digest"],
                ),
            )
            completion_facts = (f"{REPLAY_TASK_KEY}:COMPLETE",)
        return AtomicCapabilityResult(
            artifacts=(
                AtomicArtifactPayload(
                    "formal-p4-v3-decision-replay", "replay.json", replay
                ),
            ),
            completion_facts=completion_facts,
            execution_metadata=(
                ("contract_digest", CONTRACT_DIGEST),
                (
                    "same_registered_content",
                    replay["body"]["same_registered_content"],
                ),
                ("workload_rerun", False),
            ),
            workload_rerun=False,
        )

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> AtomicCapabilityResult:
        del execution_id, git_commit
        if control_plane_key != CONTROL_PLANE_KEY:
            raise MainlineSupervisorError("formal P4 control plane changed")
        expected = {
            EXECUTION_CAPABILITY: (EXECUTION_TASK_KEY, self._execution),
            EVIDENCE_CAPABILITY: (EVIDENCE_TASK_KEY, self._evidence),
            DECISION_CAPABILITY: (DECISION_TASK_KEY, self._decision),
            REPLAY_CAPABILITY: (REPLAY_TASK_KEY, self._replay),
        }
        capability = str(task.requested_capability)
        if capability not in expected:
            raise MainlineSupervisorError("unsupported formal P4 V3 capability")
        expected_key, runner = expected[capability]
        if task.task_key != expected_key:
            raise MainlineSupervisorError("formal P4 V3 task/capability mismatch")
        binding_reasons: tuple[str, ...] = ()
        try:
            integration_contract(task)
            source = self._source(task)
        except (
            FormalP4ForwardPrequentialError,
            MainlineSupervisorError,
            KeyError,
            TypeError,
            ValueError,
        ):
            source = {}
            binding_reasons = ("SOURCE_TASK_OR_GOVERNANCE_BINDING",)
        if binding_reasons and capability == EXECUTION_CAPABILITY:
            prereg = frozen_preregistration()
            identity, children, summary = self._invalid_input(
                preregistration=prereg, reason=binding_reasons[0]
            )
            return self._execution_result(
                preregistration=prereg,
                input_identity=identity,
                children=children,
                summary=summary,
            )
        if binding_reasons and capability == EVIDENCE_CAPABILITY:
            return self._evidence(
                control_plane_key=control_plane_key,
                task=task,
                source=source,
                integrity_reasons=binding_reasons,
            )
        if binding_reasons and capability == DECISION_CAPABILITY:
            return self._decision(
                control_plane_key=control_plane_key,
                task=task,
                source=source,
                integrity_reasons=binding_reasons,
            )
        if binding_reasons and capability == REPLAY_CAPABILITY:
            return self._replay(
                control_plane_key=control_plane_key,
                task=task,
                source=source,
                integrity_reasons=binding_reasons,
            )
        return runner(control_plane_key=control_plane_key, task=task, source=source)


class FormalP4ForwardPrequentialSupervisor(p3.ForwardPrequentialSupervisor):
    """Unified Supervisor extension that is reachable only through exact P4 keys."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        capability = FormalP4ForwardPrequentialCapability(
            repository=self.repository, root_dir=self.root_dir
        )
        for name in CAPABILITIES:
            self.capabilities[name] = capability


__all__ = [name for name in globals() if name.isupper()] + [
    "FormalP4ForwardPrequentialCapability",
    "FormalP4ForwardPrequentialError",
    "FormalP4ForwardPrequentialSupervisor",
    "build_execution_artifact",
    "build_p3_input_identity",
    "build_typed_replay",
    "compile_decision",
    "compile_evidence",
    "execute_controls",
    "formal_preregistration",
    "holm",
    "load_source_contract",
    "synthetic_decision_fixture",
    "validate_artifact",
    "verify_governance",
]
