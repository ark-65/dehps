from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from statistics import NormalDist
from typing import Any

from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentRequestStatus
from dehps.research_os.models import m4_v2_domain_digest


class M4V2DeeperValidationError(ValueError):
    pass


SOURCE_CONTRACT_PATH = "configs/research-os/m4-v2-deeper-validation-source-v1.json"
SOURCE_SCHEMA = "dehps-m4-v2-deeper-validation-source-contract.v1"
SOURCE_ARTIFACT_TYPE = "m4_v2_deeper_validation_source_contract"
SOURCE_SET_DOMAIN = "dehps.m4.v2.deeper-validation-source-set.v1"
SOURCE_DOMAIN = "dehps.m4.v2.deeper-validation-source-contract.v1"

INTAKE_TASK_KEY = "m4-v2-deeper-validation-intake"
INTAKE_CAPABILITY = "m4_v2_deeper_validation_intake"
INTAKE_COMPLETION_FACT = f"{INTAKE_TASK_KEY}:COMPLETE"
INTAKE_ARTIFACT_TYPE = "M4V2DeeperValidationIntakeArtifact"
INTAKE_SCHEMA = "dehps-m4-v2-deeper-validation-intake.v1"
INTAKE_DOMAIN = "dehps.m4.v2.deeper-validation-intake.v1"

DECISION_TASK_KEY = "m4-v2-deeper-validation-decision"
DECISION_CAPABILITY = "m4_v2_deeper_validation_decision"
DECISION_COMPLETION_FACT = f"{DECISION_TASK_KEY}:COMPLETE"
DECISION_ARTIFACT_TYPE = "M4V2DeeperValidationDecisionArtifact"
DECISION_SCHEMA = "dehps-m4-v2-deeper-validation-decision.v1"
DECISION_DOMAIN = "dehps.m4.v2.deeper-validation-decision.v1"

DECISION_REPLAY_TASK_KEY = "m4-v2-deeper-validation-decision-replay"
DECISION_REPLAY_CAPABILITY = "m4_v2_deeper_validation_decision_replay"
DECISION_REPLAY_COMPLETION_FACT = f"{DECISION_REPLAY_TASK_KEY}:COMPLETE"
DECISION_REPLAY_VERIFIED_FACT = (
    "m4-v2-deeper-validation-decision:REGISTERED_REPLAY_VERIFIED"
)
DECISION_REPLAY_ARTIFACT_TYPE = "M4V2DeeperValidationDecisionReplayArtifact"
DECISION_REPLAY_SCHEMA = "dehps-m4-v2-deeper-validation-decision-replay.v1"
DECISION_REPLAY_DOMAIN = "dehps.m4.v2.deeper-validation-decision-replay.v1"

ROUTE_TASK_KEY = "m4-v2-global-routing-after-deeper-validation"
ROUTE_CAPABILITY = "m4_v2_global_routing_after_deeper_validation"
ROUTE_COMPLETION_FACT = f"{ROUTE_TASK_KEY}:COMPLETE"
ROUTE_ARTIFACT_TYPE = "M4V2SupersedingGlobalRouteArtifact"
ROUTE_SCHEMA = "dehps-m4-v2-superseding-global-route.v1"
ROUTE_DOMAIN = "dehps.m4.v2.superseding-global-route.v1"
P3_CLOSURE_ARTIFACT_TYPE = "M4V2PredictiveP3ClosureArtifact"
P3_CLOSURE_SCHEMA = "dehps-m4-v2-predictive-p3-closure.v1"
P3_CLOSURE_DOMAIN = "dehps.m4.v2.predictive-p3-closure.v1"

ROUTE_REPLAY_TASK_KEY = "m4-v2-global-routing-after-deeper-validation-replay"
ROUTE_REPLAY_CAPABILITY = "m4_v2_global_routing_after_deeper_validation_replay"
ROUTE_REPLAY_COMPLETION_FACT = f"{ROUTE_REPLAY_TASK_KEY}:COMPLETE"
ROUTE_REPLAY_VERIFIED_FACT = (
    "m4-v2-global-routing-after-deeper-validation:REGISTERED_REPLAY_VERIFIED"
)
ROUTE_REPLAY_ARTIFACT_TYPE = "M4V2SupersedingGlobalRouteReplayArtifact"
ROUTE_REPLAY_SCHEMA = "dehps-m4-v2-superseding-global-route-replay.v1"
ROUTE_REPLAY_DOMAIN = "dehps.m4.v2.superseding-global-route-replay.v1"

OLD_GLOBAL_ROUTE = "DEEPER_VALIDATION_REQUIRED"
OLD_GLOBAL_ROUTE_DIGEST = (
    "b35a0860e7e2d330513ddf4c0cfee8e1b8a6a59dc24f78bd5d5f55f53daf02db"
)
OLD_INFRASTRUCTURE_INCIDENT = "P3_INFRASTRUCTURE_BLOCKED_PERMANENT"
MARGINAL_DECISION_DIGEST = (
    "483952200c4ec81408d9980aa26e7c68ce6d9134b0b6e97d2504e521835e92be"
)
TEMPORAL_DECISION_DIGEST = (
    "7697c7bd0587482584729921228909a2c14c8829eaa330c95c6e1fb97eae2433"
)
JOINT_DECISION_DIGEST = (
    "e1e19f274a54d5046b172c43c1875399c03a3d1a5fb605c91d10e0b6478157b7"
)
BRANCH_DECISION_DIGESTS = (
    MARGINAL_DECISION_DIGEST,
    TEMPORAL_DECISION_DIGEST,
    JOINT_DECISION_DIGEST,
)
MARGINAL_REPLAY_DIGEST = (
    "ca6665e69d5f74e0bfbe585af14f58f3ad6ca862aa28811b517047eadc0c9f1e"
)
TEMPORAL_REPLAY_DIGEST = (
    "6382446c1706446025b71a9f674167967b3b214027239711b535a23c7788d267"
)
JOINT_REPLAY_DIGEST = "711af70ee73549ac57e6df81c62c10216fee2e049970b45e08e27ab1818c5c2d"
BRANCH_REPLAY_DIGESTS = (
    MARGINAL_REPLAY_DIGEST,
    TEMPORAL_REPLAY_DIGEST,
    JOINT_REPLAY_DIGEST,
)
BRANCH_REPLAY_REGISTRATION_DIGESTS = (
    "c8e083fd799c4f58d937ed27ef28ad391f73757af34ea19a2bafc3294a93ca3f",
    "f1b4032348c9657d81a76621c54f77bed27f4ba74891d3e821180dff3ed2e999",
    "82a9a01277cb42e0506b31cbc4743f5924ec799ba4b0a26bcd8ec10b0f28b4cd",
)
HISTORICAL_INFERENCE_DIGEST = (
    "36056c0168bf71a995ec2a0bb9bf4663b0222b8fce621899a1e861282597e841"
)
HISTORICAL_DESIGN_DIGEST = (
    "e52220af0b6cd4c40dd3ff05b9eb692446fe4660b1118ff6cf2b4cd5423f5bb4"
)
DATASET_BOUNDARY_DIGEST = (
    "c2d03127d2eb966b699b4829402dd72947cf0c959dd013f33169649316a1d420"
)
HISTORICAL_INPUT_DIGESTS = (
    HISTORICAL_INFERENCE_DIGEST,
    HISTORICAL_DESIGN_DIGEST,
    DATASET_BOUNDARY_DIGEST,
)

INTAKE_REQUEST_KEY = "research-m4-v2-deeper-validation-intake-v1"
INTAKE_REQUEST_ID = 625
INTAKE_EXECUTION_ID = 509
INTAKE_APPROVAL_DECISION_ID = 2622
INTAKE_REQUEST_PAYLOAD_SHA256 = (
    "895a85f1f10ff2aa2679f53a5f02494c6e4a5d70d80efc378be5e75369ff5fe9"
)
REVIEW_REQUEST_KEY = "research-m4-v2-deeper-validation-reviewer-selection-v1"
REVIEW_REQUEST_ID = 626
REVIEW_EXECUTION_ID = 510
REVIEW_APPROVAL_DECISION_ID = 2627
REVIEW_REQUEST_PAYLOAD_SHA256 = (
    "f92e1803e3dab191cd9ed8b266f28dae55850ab401387b1a20694eaa4101ad9a"
)
ENGINEERING_REQUEST_KEY = (
    "engineering-m4-v2-bounded-deeper-validation-and-superseding-route-v1"
)
ENGINEERING_REQUEST_ID = 627
ENGINEERING_EXECUTION_ID = 511
ENGINEERING_REQUEST_PAYLOAD_SHA256 = (
    "165def5bc8833ebdf571945b4152516c517e6d3d47d2b797c81f618e57530e28"
)

SOURCE_PATHS = (
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/deeper_validation.py",
    "apps/worker-python/scripts/build_m4_v2_deeper_validation_manifest.py",
    "apps/worker-python/dehps/research_os/supervisor.py",
    "apps/worker-python/dehps/research_os/repository.py",
)
GOVERNANCE_BINDINGS = {
    "intake": {
        "request_key": INTAKE_REQUEST_KEY,
        "request_id": INTAKE_REQUEST_ID,
        "execution_id": INTAKE_EXECUTION_ID,
        "approval_decision_id": INTAKE_APPROVAL_DECISION_ID,
        "request_payload_sha256": INTAKE_REQUEST_PAYLOAD_SHA256,
    },
    "reviewer_selection": {
        "request_key": REVIEW_REQUEST_KEY,
        "request_id": REVIEW_REQUEST_ID,
        "execution_id": REVIEW_EXECUTION_ID,
        "approval_decision_id": REVIEW_APPROVAL_DECISION_ID,
        "request_payload_sha256": REVIEW_REQUEST_PAYLOAD_SHA256,
        "reviewer_decision": "POWER_RESOLUTION_REQUIRED",
        "selected_branch": "MARGINAL_STATIC",
    },
    "engineering": {
        "request_key": ENGINEERING_REQUEST_KEY,
        "request_id": ENGINEERING_REQUEST_ID,
        "execution_id": ENGINEERING_EXECUTION_ID,
        "request_payload_sha256": ENGINEERING_REQUEST_PAYLOAD_SHA256,
    },
}
LIMITS = {
    "unresolved_branch_limit": 1,
    "formal_validation_execution_limit": 1,
    "ci_fix_limit": 1,
    "new_holdout_or_forward_program_limit": 1,
    "new_historical_folds": 0,
    "predictive_p3_folds": 0,
    "p4_started": False,
    "promotion_triggered": False,
    "old_replay_compatibility_dependency": False,
}

REVIEWER_DECISIONS = (
    "POWER_RESOLUTION_REQUIRED",
    "MEASUREMENT_REPAIR_REQUIRED",
    "PARENT_BRANCH_RESOLUTION_REQUIRED",
    "FORWARD_EVIDENCE_REQUIRED",
    "NO_LEGAL_DEEPER_VALIDATION",
    "INVALID_FROZEN_ROUTE_ARTIFACT",
)
DEEPER_VALIDATION_DECISIONS = (
    "BRANCH_INFORMATION_ACCEPTED",
    "NO_DETECTABLE_INFORMATION",
    "INCONCLUSIVE_AT_AVAILABLE_INFORMATION",
    "FORWARD_EVIDENCE_REQUIRED",
    "MEASUREMENT_REPAIR_REQUIRED",
    "INVALID_DEEPER_VALIDATION_EXECUTION",
)
SUPERSEDING_ROUTES = (
    "ADAPTIVE_RESEARCH_ELIGIBLE_AFTER_DEEPER_VALIDATION",
    "NO_DETECTABLE_INFORMATION_UNDER_DEEPER_VALIDATION",
    "FORWARD_EVIDENCE_REQUIRED",
    "MEASUREMENT_REPAIR_REQUIRED",
    "DEEPER_VALIDATION_REMAINS_INCONCLUSIVE",
)

FROZEN_FOLD_COUNT = 2581
FROZEN_STANDARD_ERROR = 0.0045324645735604204
FROZEN_MDE = 0.013459908060402983
FROZEN_PRACTICAL_THRESHOLD = 0.01
FROZEN_FAMILYWISE_ALPHA = 0.05
FROZEN_BRANCH_COUNT = 3
FROZEN_TARGET_POWER = 0.8
FROZEN_EQUIVALENCE_POWER = 0.5311893549808094


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
        raise M4V2DeeperValidationError(f"{name}_invalid")
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
        raise M4V2DeeperValidationError(f"{artifact_type}_shape_changed")
    observed = _require_digest(payload.pop("artifact_digest"), "artifact_digest")
    if m4_v2_domain_digest(payload, domain=domain) != observed:
        raise M4V2DeeperValidationError(f"{artifact_type}_digest_changed")
    payload["artifact_digest"] = observed
    return payload


def load_source_contract(*, root_dir: Path) -> dict[str, Any]:
    path = (root_dir / SOURCE_CONTRACT_PATH).resolve()
    expected_root = root_dir.resolve()
    if not path.is_relative_to(expected_root) or not path.is_file():
        raise M4V2DeeperValidationError("deeper_validation_source_missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise M4V2DeeperValidationError("deeper_validation_source_invalid") from exc
    required = {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "contract_key",
        "old_global_route_artifact_digest",
        "branch_decision_digests",
        "branch_replay_registration_digests",
        "historical_input_digests",
        "source_entries",
        "source_set_digest",
        "governance_bindings",
        "limits",
        "production_action",
    }
    if (
        not isinstance(payload, dict)
        or set(payload) != required
        or payload.get("schema_version") != SOURCE_SCHEMA
        or payload.get("artifact_type") != SOURCE_ARTIFACT_TYPE
        or payload.get("contract_key") != "M4_V2_BOUNDED_DEEPER_VALIDATION_V1"
        or payload.get("old_global_route_artifact_digest") != OLD_GLOBAL_ROUTE_DIGEST
        or tuple(payload.get("branch_decision_digests", ())) != BRANCH_DECISION_DIGESTS
        or tuple(payload.get("branch_replay_registration_digests", ()))
        != BRANCH_REPLAY_REGISTRATION_DIGESTS
        or tuple(payload.get("historical_input_digests", ()))
        != HISTORICAL_INPUT_DIGESTS
        or payload.get("governance_bindings") != GOVERNANCE_BINDINGS
        or payload.get("limits") != LIMITS
        or payload.get("production_action") != "none"
    ):
        raise M4V2DeeperValidationError("deeper_validation_source_shape_changed")
    entries = payload.get("source_entries")
    if (
        not isinstance(entries, list)
        or tuple(
            item.get("path") for item in entries if isinstance(item, Mapping)
        )
        != SOURCE_PATHS
    ):
        raise M4V2DeeperValidationError("deeper_validation_source_entries_changed")
    verified: list[dict[str, str]] = []
    for item in entries:
        if not isinstance(item, Mapping) or set(item) != {"path", "sha256"}:
            raise M4V2DeeperValidationError("deeper_validation_source_entry_changed")
        relative = str(item["path"])
        absolute = (expected_root / relative).resolve()
        if (
            not absolute.is_relative_to(expected_root)
            or not absolute.is_file()
            or hashlib.sha256(absolute.read_bytes()).hexdigest() != item["sha256"]
        ):
            raise M4V2DeeperValidationError("deeper_validation_source_bytes_changed")
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
        raise M4V2DeeperValidationError("deeper_validation_source_identity_changed")
    return deepcopy(payload)


def verify_governance(agent_repository: AgentRequestRepository) -> None:
    specifications = (
        (
            INTAKE_REQUEST_KEY,
            INTAKE_REQUEST_ID,
            "research_scheduler_request",
            INTAKE_REQUEST_PAYLOAD_SHA256,
            INTAKE_EXECUTION_ID,
            INTAKE_APPROVAL_DECISION_ID,
            "APPROVE_ZERO_COMPUTE_DEEPER_VALIDATION_INTAKE",
        ),
        (
            REVIEW_REQUEST_KEY,
            REVIEW_REQUEST_ID,
            "research_scheduler_request",
            REVIEW_REQUEST_PAYLOAD_SHA256,
            REVIEW_EXECUTION_ID,
            REVIEW_APPROVAL_DECISION_ID,
            "POWER_RESOLUTION_REQUIRED",
        ),
        (
            ENGINEERING_REQUEST_KEY,
            ENGINEERING_REQUEST_ID,
            "engineering_implementation",
            ENGINEERING_REQUEST_PAYLOAD_SHA256,
            ENGINEERING_EXECUTION_ID,
            None,
            "APPROVE_BOUNDED_DEEPER_VALIDATION_IMPLEMENTATION",
        ),
    )
    for (
        request_key,
        request_id,
        request_type,
        payload_sha256,
        execution_id,
        approval_decision_id,
        approval_outcome,
    ) in specifications:
        request = agent_repository.get_request(request_key)
        executions = agent_repository.list_executions(request_key)
        decisions = agent_repository.list_decisions(request_key)
        approvals = [
            item for item in decisions if item.decision_code == "request_approved"
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
            or (
                approval_decision_id is not None
                and approvals[0].id != approval_decision_id
            )
            or approvals[0].reason.get("outcome") != approval_outcome
        ):
            raise M4V2DeeperValidationError("deeper_validation_governance_changed")
    intake_execution = agent_repository.list_executions(INTAKE_REQUEST_KEY)[0]
    review_execution = agent_repository.list_executions(REVIEW_REQUEST_KEY)[0]
    if (
        intake_execution.status.value != "completed"
        or intake_execution.result.get("artifact_type") != INTAKE_ARTIFACT_TYPE
        or intake_execution.result.get("recommended_single_validation_program")
        != "POWER_RESOLUTION_REQUIRED"
        or review_execution.status.value != "completed"
        or review_execution.result.get("reviewer_decision")
        != "POWER_RESOLUTION_REQUIRED"
        or review_execution.result.get("selected_branch") != "MARGINAL_STATIC"
        or review_execution.result.get("engineering_selected_program") is not False
    ):
        raise M4V2DeeperValidationError("deeper_validation_research_execution_changed")


def build_intake_artifact(
    *,
    old_route: Mapping[str, Any],
    branch_decisions: Sequence[Mapping[str, Any]],
    branch_replays: Sequence[Mapping[str, Any]],
    historical_inference: Mapping[str, Any],
    historical_design: Mapping[str, Any],
    dataset_boundary: Mapping[str, Any],
    source_contract_digest: str,
) -> dict[str, Any]:
    if (
        old_route.get("artifact_digest") != OLD_GLOBAL_ROUTE_DIGEST
        or old_route.get("route") != OLD_GLOBAL_ROUTE
    ):
        raise M4V2DeeperValidationError("frozen_global_route_changed")
    if (
        tuple(item.get("artifact_digest") for item in branch_decisions)
        != BRANCH_DECISION_DIGESTS
    ):
        raise M4V2DeeperValidationError("branch_decision_identity_changed")
    if (
        tuple(item.get("artifact_digest") for item in branch_replays)
        != BRANCH_REPLAY_DIGESTS
    ):
        raise M4V2DeeperValidationError("branch_replay_identity_changed")
    decision_bodies = [item.get("body") for item in branch_decisions]
    replay_bodies = [item.get("body") for item in branch_replays]
    if (
        any(not isinstance(item, Mapping) for item in decision_bodies)
        or any(not isinstance(item, Mapping) for item in replay_bodies)
        or [item.get("branch_id") for item in decision_bodies]
        != [
            "MARGINAL_STATIC",
            "TEMPORAL_MARGINAL_INCREMENT",
            "JOINT_RESIDUAL_INCREMENT",
        ]
        or any(
            item.get("replay_status") != "REGISTERED_REPLAY_VERIFIED"
            for item in replay_bodies
        )
        or any(item.get("workload_rerun") is not False for item in replay_bodies)
    ):
        raise M4V2DeeperValidationError("branch_projection_changed")
    marginal, temporal, joint = decision_bodies
    if (
        marginal.get("terminal_decision") != "INCONCLUSIVE_DUE_TO_POWER"
        or marginal.get("measurement_health") != "PASS"
        or marginal.get("historical_evidence") != "INCONCLUSIVE"
        or marginal.get("accepted_for_downstream_baseline") is not False
        or temporal.get("terminal_decision") != "NOT_EVALUABLE_PARENT_NOT_ACCEPTED"
        or joint.get("terminal_decision") != "NOT_EVALUABLE_PARENT_NOT_ACCEPTED"
    ):
        raise M4V2DeeperValidationError("branch_terminal_state_changed")
    if (
        historical_inference.get("artifact_digest") != HISTORICAL_INFERENCE_DIGEST
        or historical_inference.get("formal_historical_folds_executed")
        != FROZEN_FOLD_COUNT
        or historical_inference.get("mde_bits_per_issue") != FROZEN_MDE
        or historical_inference.get("primary_threshold_bits_per_issue")
        != FROZEN_PRACTICAL_THRESHOLD
        or historical_inference.get("equivalence_power_at_zero")
        != FROZEN_EQUIVALENCE_POWER
        or historical_design.get("artifact_digest") != HISTORICAL_DESIGN_DIGEST
        or dataset_boundary.get("artifact_digest") != DATASET_BOUNDARY_DIGEST
    ):
        raise M4V2DeeperValidationError("historical_evidence_state_changed")
    body = {
        "old_global_route": OLD_GLOBAL_ROUTE,
        "old_global_route_artifact_digest": OLD_GLOBAL_ROUTE_DIGEST,
        "old_infrastructure_incident": OLD_INFRASTRUCTURE_INCIDENT,
        "unresolved_branches": [
            "MARGINAL_STATIC",
            "TEMPORAL_MARGINAL_INCREMENT",
            "JOINT_RESIDUAL_INCREMENT",
        ],
        "priority_parent_branch": "MARGINAL_STATIC",
        "exact_terminal_decision_per_branch": {
            "MARGINAL_STATIC": "INCONCLUSIVE_DUE_TO_POWER",
            "TEMPORAL_MARGINAL_INCREMENT": "NOT_EVALUABLE_PARENT_NOT_ACCEPTED",
            "JOINT_RESIDUAL_INCREMENT": "NOT_EVALUABLE_PARENT_NOT_ACCEPTED",
        },
        "exact_reason_per_branch": {
            "MARGINAL_STATIC": (
                "measurement health PASS; complete 2581-fold registered historical execution; "
                "frozen MDE 0.013459908060402983 exceeds practical threshold 0.01 and "
                "equivalence power 0.5311893549808094 is below 0.8"
            ),
            "TEMPORAL_MARGINAL_INCREMENT": (
                "MARGINAL_STATIC was not accepted for downstream baseline; historical workload not run"
            ),
            "JOINT_RESIDUAL_INCREMENT": (
                "MARGINAL_STATIC and TEMPORAL_MARGINAL_INCREMENT were not accepted; historical workload not run"
            ),
        },
        "accepted_parent_chain": [],
        "positive_branches": [],
        "inconclusive_branches": ["MARGINAL_STATIC"],
        "repair_branches": [],
        "not_evaluable_branches": [
            "TEMPORAL_MARGINAL_INCREMENT",
            "JOINT_RESIDUAL_INCREMENT",
        ],
        "exact_missing_conclusive_coverage": (
            "MARGINAL_STATIC power resolution is the sole legal parent-first program; "
            "Temporal and Joint remain excluded descendants"
        ),
        "recommended_single_validation_program": "POWER_RESOLUTION_REQUIRED",
        "source_contract_digest": _require_digest(
            source_contract_digest, "source_contract_digest"
        ),
        "decision_projection_rows": deepcopy(old_route["decision_projection_rows"]),
        "branch_replay_registration_digests": list(BRANCH_REPLAY_REGISTRATION_DIGESTS),
        "scientific_computation": 0,
        "historical_database_reads": 0,
        "new_historical_folds": 0,
        "predictive_p3_folds": 0,
        "p4_started": False,
        "promotion_triggered": False,
        "result_blind": True,
    }
    return _artifact(
        artifact_type=INTAKE_ARTIFACT_TYPE,
        schema_version=INTAKE_SCHEMA,
        domain=INTAKE_DOMAIN,
        body=body,
        parent_digests=(
            source_contract_digest,
            OLD_GLOBAL_ROUTE_DIGEST,
            *BRANCH_DECISION_DIGESTS,
            *BRANCH_REPLAY_DIGESTS,
            *HISTORICAL_INPUT_DIGESTS,
        ),
    )


def build_deeper_validation_decision(
    *,
    intake_artifact: Mapping[str, Any],
    reviewer_decision: str,
    reviewer_approval_decision_id: int,
) -> dict[str, Any]:
    intake = _validate_artifact(
        intake_artifact,
        artifact_type=INTAKE_ARTIFACT_TYPE,
        schema_version=INTAKE_SCHEMA,
        domain=INTAKE_DOMAIN,
    )
    if (
        reviewer_decision not in REVIEWER_DECISIONS
        or reviewer_decision != "POWER_RESOLUTION_REQUIRED"
        or reviewer_approval_decision_id != REVIEW_APPROVAL_DECISION_ID
        or intake["body"].get("priority_parent_branch") != "MARGINAL_STATIC"
    ):
        raise M4V2DeeperValidationError("reviewer_program_selection_changed")
    per_branch_alpha = FROZEN_FAMILYWISE_ALPHA / FROZEN_BRANCH_COUNT
    critical_alpha = NormalDist().inv_cdf(1.0 - per_branch_alpha)
    critical_power = NormalDist().inv_cdf(FROZEN_TARGET_POWER)
    recalculated_mde = (critical_alpha + critical_power) * FROZEN_STANDARD_ERROR
    if not math.isclose(recalculated_mde, FROZEN_MDE, rel_tol=0.0, abs_tol=1e-15):
        raise M4V2DeeperValidationError("frozen_mde_formula_changed")
    required_independent_folds = math.ceil(
        FROZEN_FOLD_COUNT * (FROZEN_MDE / FROZEN_PRACTICAL_THRESHOLD) ** 2
    )
    if required_independent_folds != 4676:
        raise M4V2DeeperValidationError("required_independent_fold_count_changed")
    body = {
        "selected_branch": "MARGINAL_STATIC",
        "reviewer_decision": reviewer_decision,
        "reviewer_approval_decision_id": reviewer_approval_decision_id,
        "validation_program": "POWER_FEASIBILITY_ONLY_THEN_INDEPENDENT_HOLDOUT_OR_FORWARD_EVIDENCE",
        "frozen_practical_threshold_bits_per_issue": FROZEN_PRACTICAL_THRESHOLD,
        "frozen_estimator": "mean settled issue-level prequential score difference",
        "frozen_failure_rule": (
            "non-significance without equivalence power at least 0.8 remains INCONCLUSIVE"
        ),
        "frozen_primary_resampling": "non-circular moving-block bootstrap block_length_5",
        "repeated_resampling_is_independent_information": False,
        "observed_independent_fold_count": FROZEN_FOLD_COUNT,
        "frozen_mde_bits_per_issue": FROZEN_MDE,
        "minimum_detectable_effect_bits_per_issue": FROZEN_MDE,
        "required_independent_fold_count": required_independent_folds,
        "additional_independent_folds_required": required_independent_folds
        - FROZEN_FOLD_COUNT,
        "registered_unused_independent_holdout_available": False,
        "registered_predraw_checkpoint_digest": None,
        "holdout_reason": (
            "the frozen design permits a post-cutoff cohort only with a real pre-draw checkpoint; "
            "no registered unused holdout checkpoint is present in the accepted parent chain"
        ),
        "independent_new_data_used": False,
        "new_historical_folds": 0,
        "deeper_validation_decision": "FORWARD_EVIDENCE_REQUIRED",
        "formal_execution_count": 0,
        "ci_fix_count": 0,
        "new_holdout_or_forward_program_count": 1,
        "temporal_workload_executed": False,
        "joint_workload_executed": False,
        "predictive_p3_folds": 0,
        "p4_started": False,
        "promotion_triggered": False,
        "production_action": "none",
    }
    return _artifact(
        artifact_type=DECISION_ARTIFACT_TYPE,
        schema_version=DECISION_SCHEMA,
        domain=DECISION_DOMAIN,
        body=body,
        parent_digests=(intake["artifact_digest"],),
    )


def build_decision_replay(
    *,
    decision_artifact: Mapping[str, Any],
    decision_registration_digest: str,
) -> dict[str, Any]:
    decision = _validate_artifact(
        decision_artifact,
        artifact_type=DECISION_ARTIFACT_TYPE,
        schema_version=DECISION_SCHEMA,
        domain=DECISION_DOMAIN,
    )
    if (
        decision["body"].get("deeper_validation_decision")
        not in DEEPER_VALIDATION_DECISIONS
    ):
        raise M4V2DeeperValidationError("deeper_validation_decision_changed")
    body = {
        "decision_artifact_digest": decision["artifact_digest"],
        "decision_registration_digest": _require_digest(
            decision_registration_digest, "decision_registration_digest"
        ),
        "decision": decision["body"]["deeper_validation_decision"],
        "selected_branch": decision["body"]["selected_branch"],
        "replay_status": "REGISTERED_REPLAY_VERIFIED",
        "registered_content_verified": True,
        "same_decision_identity": True,
        "workload_rerun": False,
        "new_historical_folds": 0,
        "predictive_p3_folds": 0,
        "p4_started": False,
        "promotion_triggered": False,
    }
    return _artifact(
        artifact_type=DECISION_REPLAY_ARTIFACT_TYPE,
        schema_version=DECISION_REPLAY_SCHEMA,
        domain=DECISION_REPLAY_DOMAIN,
        body=body,
        parent_digests=(decision["artifact_digest"], decision_registration_digest),
    )


def build_superseding_global_route(
    *,
    old_route: Mapping[str, Any],
    branch_decisions: Sequence[Mapping[str, Any]],
    branch_replays: Sequence[Mapping[str, Any]],
    deeper_decision: Mapping[str, Any],
    deeper_replay: Mapping[str, Any],
    deeper_decision_registration_digest: str,
    deeper_replay_registration_digest: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    decision = _validate_artifact(
        deeper_decision,
        artifact_type=DECISION_ARTIFACT_TYPE,
        schema_version=DECISION_SCHEMA,
        domain=DECISION_DOMAIN,
    )
    replay = _validate_artifact(
        deeper_replay,
        artifact_type=DECISION_REPLAY_ARTIFACT_TYPE,
        schema_version=DECISION_REPLAY_SCHEMA,
        domain=DECISION_REPLAY_DOMAIN,
    )
    if (
        old_route.get("artifact_digest") != OLD_GLOBAL_ROUTE_DIGEST
        or old_route.get("route") != OLD_GLOBAL_ROUTE
        or tuple(item.get("artifact_digest") for item in branch_decisions)
        != BRANCH_DECISION_DIGESTS
        or tuple(item.get("artifact_digest") for item in branch_replays)
        != BRANCH_REPLAY_DIGESTS
        or replay["body"].get("replay_status") != "REGISTERED_REPLAY_VERIFIED"
        or replay["body"].get("decision_artifact_digest") != decision["artifact_digest"]
    ):
        raise M4V2DeeperValidationError("superseding_route_input_changed")
    decision_name = decision["body"]["deeper_validation_decision"]
    route_by_decision = {
        "BRANCH_INFORMATION_ACCEPTED": "ADAPTIVE_RESEARCH_ELIGIBLE_AFTER_DEEPER_VALIDATION",
        "NO_DETECTABLE_INFORMATION": "NO_DETECTABLE_INFORMATION_UNDER_DEEPER_VALIDATION",
        "FORWARD_EVIDENCE_REQUIRED": "FORWARD_EVIDENCE_REQUIRED",
        "MEASUREMENT_REPAIR_REQUIRED": "MEASUREMENT_REPAIR_REQUIRED",
        "INCONCLUSIVE_AT_AVAILABLE_INFORMATION": "DEEPER_VALIDATION_REMAINS_INCONCLUSIVE",
        "INVALID_DEEPER_VALIDATION_EXECUTION": "DEEPER_VALIDATION_REMAINS_INCONCLUSIVE",
    }
    route = route_by_decision[decision_name]
    if route not in SUPERSEDING_ROUTES:
        raise M4V2DeeperValidationError("superseding_route_changed")
    predictive_p3_status = (
        "P3_PREREGISTRATION_REQUIRED"
        if route == "ADAPTIVE_RESEARCH_ELIGIBLE_AFTER_DEEPER_VALIDATION"
        else "CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION"
    )
    route_body = {
        "old_global_route": OLD_GLOBAL_ROUTE,
        "old_global_route_artifact_digest": OLD_GLOBAL_ROUTE_DIGEST,
        "old_infrastructure_incident": OLD_INFRASTRUCTURE_INCIDENT,
        "registered_branch_decision_digests": list(BRANCH_DECISION_DIGESTS),
        "registered_branch_replay_registration_digests": list(
            BRANCH_REPLAY_REGISTRATION_DIGESTS
        ),
        "deeper_validation_decision_artifact_digest": decision["artifact_digest"],
        "deeper_validation_decision_registration_digest": _require_digest(
            deeper_decision_registration_digest, "deeper_decision_registration_digest"
        ),
        "deeper_validation_replay_artifact_digest": replay["artifact_digest"],
        "deeper_validation_replay_registration_digest": _require_digest(
            deeper_replay_registration_digest, "deeper_replay_registration_digest"
        ),
        "deeper_validation_decision": decision_name,
        "superseding_global_route": route,
        "predictive_p3_status": predictive_p3_status,
        "predictive_p3_folds": 0,
        "p4_started": False,
        "promotion_triggered": False,
        "natural_expansion": "STOPPED",
        "next_legal_task": (
            "new prediction-oriented P3 preregistration goal bound to the Deeper Validation route"
            if predictive_p3_status == "P3_PREREGISTRATION_REQUIRED"
            else "FORWARD_EVIDENCE_REQUIRED"
        ),
        "production_action": "none",
    }
    route_artifact = _artifact(
        artifact_type=ROUTE_ARTIFACT_TYPE,
        schema_version=ROUTE_SCHEMA,
        domain=ROUTE_DOMAIN,
        body=route_body,
        parent_digests=(
            OLD_GLOBAL_ROUTE_DIGEST,
            *BRANCH_DECISION_DIGESTS,
            *BRANCH_REPLAY_DIGESTS,
            decision["artifact_digest"],
            replay["artifact_digest"],
            deeper_decision_registration_digest,
            deeper_replay_registration_digest,
        ),
    )
    closure_body = {
        "superseding_global_route_artifact_digest": route_artifact["artifact_digest"],
        "predictive_p3_status": predictive_p3_status,
        "predictive_p3_folds": 0,
        "p4_started": False,
        "promotion_triggered": False,
        "old_predictive_p3_artifacts_mutated": False,
        "production_action": "none",
    }
    closure_artifact = _artifact(
        artifact_type=P3_CLOSURE_ARTIFACT_TYPE,
        schema_version=P3_CLOSURE_SCHEMA,
        domain=P3_CLOSURE_DOMAIN,
        body=closure_body,
        parent_digests=(route_artifact["artifact_digest"],),
    )
    return route_artifact, closure_artifact


def build_route_replay(
    *,
    route_artifact: Mapping[str, Any],
    route_registration_digest: str,
    p3_closure_artifact: Mapping[str, Any],
    p3_closure_registration_digest: str,
) -> dict[str, Any]:
    route = _validate_artifact(
        route_artifact,
        artifact_type=ROUTE_ARTIFACT_TYPE,
        schema_version=ROUTE_SCHEMA,
        domain=ROUTE_DOMAIN,
    )
    closure = _validate_artifact(
        p3_closure_artifact,
        artifact_type=P3_CLOSURE_ARTIFACT_TYPE,
        schema_version=P3_CLOSURE_SCHEMA,
        domain=P3_CLOSURE_DOMAIN,
    )
    if (
        route["body"].get("superseding_global_route") not in SUPERSEDING_ROUTES
        or route["body"].get("superseding_global_route") != "FORWARD_EVIDENCE_REQUIRED"
        or closure["body"].get("superseding_global_route_artifact_digest")
        != route["artifact_digest"]
        or closure["body"].get("predictive_p3_status")
        != "CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION"
    ):
        raise M4V2DeeperValidationError("superseding_route_replay_input_changed")
    body = {
        "route_artifact_digest": route["artifact_digest"],
        "route_registration_digest": _require_digest(
            route_registration_digest, "route_registration_digest"
        ),
        "p3_closure_artifact_digest": closure["artifact_digest"],
        "p3_closure_registration_digest": _require_digest(
            p3_closure_registration_digest, "p3_closure_registration_digest"
        ),
        "superseding_global_route": route["body"]["superseding_global_route"],
        "predictive_p3_status": closure["body"]["predictive_p3_status"],
        "replay_status": "REGISTERED_REPLAY_VERIFIED",
        "registered_content_verified": True,
        "same_route_identity": True,
        "same_closure_identity": True,
        "workload_rerun": False,
        "predictive_p3_folds": 0,
        "p4_started": False,
        "promotion_triggered": False,
    }
    return _artifact(
        artifact_type=ROUTE_REPLAY_ARTIFACT_TYPE,
        schema_version=ROUTE_REPLAY_SCHEMA,
        domain=ROUTE_REPLAY_DOMAIN,
        body=body,
        parent_digests=(
            route["artifact_digest"],
            route_registration_digest,
            closure["artifact_digest"],
            p3_closure_registration_digest,
        ),
    )
