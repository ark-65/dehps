from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentRequestStatus
from dehps.research_os.models import m4_v2_domain_digest


class M4V2ForwardEvidenceFeasibilityError(ValueError):
    pass


SOURCE_CONTRACT_PATH = (
    "configs/research-os/m4-v2-forward-evidence-feasibility-source-v1.json"
)
SOURCE_SCHEMA = "dehps-m4-v2-forward-evidence-feasibility-source-contract.v1"
SOURCE_ARTIFACT_TYPE = "m4_v2_forward_evidence_feasibility_source_contract"
SOURCE_DOMAIN = "dehps.m4.v2.forward-evidence-feasibility-source-contract.v1"
SOURCE_SET_DOMAIN = "dehps.m4.v2.forward-evidence-feasibility-source-set.v1"

GOAL_KEY = "M4_V2_FORWARD_EVIDENCE_FEASIBILITY_AND_PROGRAM_DECISION"
TASK_KEY = "m4-v2-forward-evidence-feasibility-and-program-decision"
CAPABILITY = "m4_v2_forward_evidence_feasibility_and_program_decision"
COMPLETION_FACT = f"{TASK_KEY}:COMPLETE"
PROGRAM_FACT = "m4-v2-forward-program:LAUNCH_BOUNDED_OPERATIONAL_FORWARD_STUDY"
REUSE_POLICY_FACT = "m4-v2-forward-data-reuse-policy:STAGED_INDEPENDENT_SAMPLES"

SUCCESSOR_TASK_KEY = "m4-v2-bounded-operational-forward-study-preregistration"

FEASIBILITY_ARTIFACT_TYPE = "M4V2ForwardEvidenceFeasibilityArtifact"
FEASIBILITY_SCHEMA = "dehps-m4-v2-forward-evidence-feasibility.v1"
FEASIBILITY_DOMAIN = "dehps.m4.v2.forward-evidence-feasibility.v1"
DECISION_ARTIFACT_TYPE = "M4V2ForwardEvidenceProgramDecisionArtifact"
DECISION_SCHEMA = "dehps-m4-v2-forward-evidence-program-decision.v1"
DECISION_DOMAIN = "dehps.m4.v2.forward-evidence-program-decision.v1"
REPLAY_ARTIFACT_TYPE = "M4V2ForwardEvidenceProgramDecisionReplayArtifact"
REPLAY_SCHEMA = "dehps-m4-v2-forward-evidence-program-decision-replay.v1"
REPLAY_DOMAIN = "dehps.m4.v2.forward-evidence-program-decision-replay.v1"

RESEARCH_REQUEST_KEY = "research-m4-v2-forward-evidence-feasibility"
RESEARCH_REQUEST_ID = 634
RESEARCH_EXECUTION_ID = 518
RESEARCH_APPROVAL_DECISION_ID = 2667
SCIENTIFIC_REVIEWER_DECISION_ID = 2667
RESEARCH_REQUEST_PAYLOAD_SHA256 = (
    "f062f2ecde7db95870adb321c449e39d1b7bb38cab5962123573d2f88e80ea75"
)
ANALYSIS_SHA256 = "c84543098541d9697707ed3013984bb03217616ae07f00e1c3c3fa63f778eada"
ENGINEERING_REQUEST_KEY = "engineering-m4-v2-forward-evidence-feasibility-v1"
ENGINEERING_REQUEST_ID = 635
ENGINEERING_EXECUTION_ID = 519
ENGINEERING_APPROVAL_DECISION_ID = 2672
ENGINEERING_REQUEST_PAYLOAD_SHA256 = (
    "4125e9e97773afb60bf3edc9a9bdceaa9aa22aafdc467fe1cf887f26c2e70af5"
)

SELECTED_DECISION = "LAUNCH_BOUNDED_OPERATIONAL_FORWARD_STUDY"
SELECTED_PROGRAM = "BOUNDED_OPERATIONAL_FORWARD_STUDY"
TARGET_ISSUE_COUNT = 120
DATA_REUSE_POLICY = "STAGED_INDEPENDENT_SAMPLES"
ESTIMATED_COMPLETION_DATE = "2027-06-07"

FROZEN_INPUT_DIGESTS = (
    "869f4302cbfdfe2af8076e5bf2aea50779f1bb3f58548611bfbaa25af69a7685",
    "dbac3aad6128787f737a1450461a9833c948068ba915f194df41a02f6fd9d9e3",
    "36056c0168bf71a995ec2a0bb9bf4663b0222b8fce621899a1e861282597e841",
    "999064903fa8a040520ab2a664a1ce3ec35321a90f0e5823626194c64c8d98c6",
    "5a68579161ad5528ee15b8b1ea3e314d6acb05203885a5514e5654da026e9ad7",
    "e52220af0b6cd4c40dd3ff05b9eb692446fe4660b1118ff6cf2b4cd5423f5bb4",
    "2dcd3630d4e0987022a22e27ae8818bed9edd39758138e90579b85fef5fe0bbc",
    "8d17fc0fba0a29d7ae8eef50d228d31af920c3d770f6095db8ca2448147448c7",
    "c54ad7b645a189a5cde6e1770baed08f59805e0a935cb2eb684e5fc33e7afc10",
    "f3f019e82b4391cbbbda88a11a6c1fc0373050a67a67d164ed65432c232ab56d",
    "5767580c5072d3c73cb4d04f67f7b17a4c92d4d199c56ef405b558a5d50b9daa",
    "225286ea27d48cad2abefc4adf1677b1b04da160a25bec49da98bcc5952e133c",
)

SOURCE_PATHS = (
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/forward_evidence_feasibility.py",
    "apps/worker-python/scripts/build_m4_v2_forward_evidence_feasibility_manifest.py",
    "apps/worker-python/dehps/research_os/supervisor.py",
    "apps/worker-python/dehps/research_os/repository.py",
)


def _canonical_payload_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _require_digest(value: Any, name: str) -> str:
    digest = str(value or "")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise M4V2ForwardEvidenceFeasibilityError(f"{name}_invalid")
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
        "parent_digests": [_require_digest(v, "parent_digest") for v in parent_digests],
    }
    payload["artifact_digest"] = m4_v2_domain_digest(payload, domain=domain)
    return payload


def _validate_artifact(
    value: Mapping[str, Any], *, artifact_type: str, schema_version: str, domain: str
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
        raise M4V2ForwardEvidenceFeasibilityError(f"{artifact_type}_shape_changed")
    observed = _require_digest(payload.pop("artifact_digest"), "artifact_digest")
    if m4_v2_domain_digest(payload, domain=domain) != observed:
        raise M4V2ForwardEvidenceFeasibilityError(f"{artifact_type}_digest_changed")
    payload["artifact_digest"] = observed
    return payload


def load_source_contract(*, root_dir: Path) -> dict[str, Any]:
    root = root_dir.resolve()
    path = (root / SOURCE_CONTRACT_PATH).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise M4V2ForwardEvidenceFeasibilityError("forward_source_missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise M4V2ForwardEvidenceFeasibilityError("forward_source_invalid") from exc
    required = {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "contract_key",
        "frozen_inputs",
        "feasibility_analysis",
        "reviewer_decision",
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
            "scientific_reviewer_decision_id": SCIENTIFIC_REVIEWER_DECISION_ID,
            "request_payload_sha256": RESEARCH_REQUEST_PAYLOAD_SHA256,
            "analysis_sha256": ANALYSIS_SHA256,
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
        or payload.get("contract_key") != GOAL_KEY
        or payload.get("governance_bindings") != governance
    ):
        raise M4V2ForwardEvidenceFeasibilityError("forward_source_shape_changed")
    frozen = payload.get("frozen_inputs")
    analysis = payload.get("feasibility_analysis")
    decision = payload.get("reviewer_decision")
    limits = payload.get("limits")
    if (
        not isinstance(frozen, Mapping)
        or tuple(frozen.get("registered_artifact_digests", ())) != FROZEN_INPUT_DIGESTS
        or frozen.get("existing_independent_folds") != 2581
        or frozen.get("required_independent_folds") != 4676
        or frozen.get("additional_independent_folds_required") != 2095
        or frozen.get("frozen_mde_bits_per_issue") != 0.013459908060402983
        or frozen.get("practical_threshold_bits_per_issue") != 0.01
        or frozen.get("current_equivalence_power") != 0.5311893549808094
        or frozen.get("target_power") != 0.8
        or frozen.get("unused_independent_historical_holdout") is not False
        or not isinstance(analysis, Mapping)
        or analysis.get("decision_matrix", {}).get("maximum_weighted_score") != 84
        or analysis.get("decision_matrix", {}).get("program_weighted_totals")
        != {
            "LONG_HORIZON_CONFIRMATORY_FORWARD": 57,
            "BOUNDED_OPERATIONAL_FORWARD_STUDY": 67,
            "REDESIGN_PROSPECTIVE_RESEARCH_QUESTION": 56,
            "TERMINATE_PREDICTIVE_ROUTE": 58,
        }
        or not isinstance(decision, Mapping)
        or decision.get("decision") != SELECTED_DECISION
        or decision.get("selected_program") != SELECTED_PROGRAM
        or decision.get("target_issue_count") != TARGET_ISSUE_COUNT
        or decision.get("maximum_issue_count") != TARGET_ISSUE_COUNT
        or decision.get("data_reuse_policy") != DATA_REUSE_POLICY
        or decision.get("estimated_completion_date") != ESTIMATED_COMPLETION_DATE
        or decision.get("next_task_key") != SUCCESSOR_TASK_KEY
        or not isinstance(limits, Mapping)
        or any(
            limits.get(key) != value
            for key, value in {
                "scientific_computation": 0,
                "model_training": False,
                "model_refit": False,
                "historical_p3_folds": 0,
                "forward_samples": 0,
                "forward_checkpoints": 0,
                "settlements": 0,
                "formal_p4": False,
                "pass_to_p4_emitted": False,
                "p5_authorized": False,
                "promotion_triggered": False,
                "successor_execution_authorized": False,
            }.items()
        )
    ):
        raise M4V2ForwardEvidenceFeasibilityError("forward_source_content_changed")
    entries = payload.get("source_entries")
    if (
        not isinstance(entries, list)
        or tuple(item.get("path") for item in entries if isinstance(item, Mapping))
        != SOURCE_PATHS
    ):
        raise M4V2ForwardEvidenceFeasibilityError("forward_source_entries_changed")
    verified: list[dict[str, str]] = []
    for item in entries:
        if not isinstance(item, Mapping) or set(item) != {"path", "sha256"}:
            raise M4V2ForwardEvidenceFeasibilityError("forward_source_entry_changed")
        relative = str(item["path"])
        absolute = (root / relative).resolve()
        if (
            not absolute.is_relative_to(root)
            or not absolute.is_file()
            or hashlib.sha256(absolute.read_bytes()).hexdigest() != item["sha256"]
        ):
            raise M4V2ForwardEvidenceFeasibilityError("forward_source_bytes_changed")
        verified.append({"path": relative, "sha256": str(item["sha256"])})
    source_set_digest = m4_v2_domain_digest(
        {"source_entries": verified}, domain=SOURCE_SET_DOMAIN
    )
    identity = dict(payload)
    artifact_digest = _require_digest(identity.pop("artifact_digest"), "source_digest")
    if (
        payload.get("source_set_digest") != source_set_digest
        or m4_v2_domain_digest(identity, domain=SOURCE_DOMAIN) != artifact_digest
    ):
        raise M4V2ForwardEvidenceFeasibilityError("forward_source_identity_changed")
    return deepcopy(payload)


def verify_governance(agent_repository: AgentRequestRepository) -> None:
    specs = (
        (
            RESEARCH_REQUEST_KEY,
            RESEARCH_REQUEST_ID,
            "research_scheduler_request",
            RESEARCH_REQUEST_PAYLOAD_SHA256,
            RESEARCH_EXECUTION_ID,
            RESEARCH_APPROVAL_DECISION_ID,
            SELECTED_DECISION,
        ),
        (
            ENGINEERING_REQUEST_KEY,
            ENGINEERING_REQUEST_ID,
            "engineering_implementation",
            ENGINEERING_REQUEST_PAYLOAD_SHA256,
            ENGINEERING_EXECUTION_ID,
            ENGINEERING_APPROVAL_DECISION_ID,
            "APPROVE_EXACT_ZERO_COMPUTE_FORWARD_PROGRAM_DECISION_IMPLEMENTATION",
        ),
    )
    for key, request_id, request_type, sha, execution_id, approval_id, outcome in specs:
        request = agent_repository.get_request(key)
        executions = agent_repository.list_executions(key)
        approvals = [
            item
            for item in agent_repository.list_decisions(key)
            if item.decision_code == "request_approved"
        ]
        if (
            request.id != request_id
            or request.request_type.value != request_type
            or request.status
            not in {AgentRequestStatus.EXECUTING, AgentRequestStatus.COMPLETED}
            or _canonical_payload_sha256(request.payload) != sha
            or len(executions) != 1
            or executions[0].id != execution_id
            or len(approvals) != 1
            or approvals[0].id != approval_id
            or approvals[0].reason.get("outcome") != outcome
        ):
            raise M4V2ForwardEvidenceFeasibilityError("forward_governance_changed")
    research_execution = agent_repository.list_executions(RESEARCH_REQUEST_KEY)[0]
    reviewer = [
        item
        for item in agent_repository.list_decisions(RESEARCH_REQUEST_KEY)
        if item.id == SCIENTIFIC_REVIEWER_DECISION_ID
    ]
    if (
        research_execution.status.value != "completed"
        or research_execution.result.get("analysis_mode")
        != "ZERO_COMPUTE_RESEARCH_DECISION"
        or research_execution.result.get("analysis_sha256") != ANALYSIS_SHA256
        or research_execution.result.get("new_historical_folds") != 0
        or research_execution.result.get("forward_checkpoints") != 0
        or research_execution.result.get("settlements") != 0
        or len(reviewer) != 1
        or reviewer[0].reason.get("outcome") != SELECTED_DECISION
        or reviewer[0].reason.get("target_issue_count") != TARGET_ISSUE_COUNT
        or reviewer[0].reason.get("data_reuse_policy") != DATA_REUSE_POLICY
    ):
        raise M4V2ForwardEvidenceFeasibilityError("forward_reviewer_decision_changed")


def build_artifacts(
    *,
    source_contract: Mapping[str, Any],
    registered_inputs: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source = deepcopy(dict(source_contract))
    observed = tuple(str(item.get("artifact_digest")) for item in registered_inputs)
    if observed != FROZEN_INPUT_DIGESTS:
        raise M4V2ForwardEvidenceFeasibilityError("forward_registered_inputs_changed")
    source_digest = _require_digest(source.get("artifact_digest"), "source_digest")
    analysis = deepcopy(dict(source["feasibility_analysis"]))
    decision_body = deepcopy(dict(source["reviewer_decision"]))
    feasibility = _artifact(
        artifact_type=FEASIBILITY_ARTIFACT_TYPE,
        schema_version=FEASIBILITY_SCHEMA,
        domain=FEASIBILITY_DOMAIN,
        body={
            "status": "COMPLETE",
            "mode": "ZERO_COMPUTE_RESEARCH_DECISION",
            "frozen_inputs": deepcopy(dict(source["frozen_inputs"])),
            "analysis": analysis,
            "candidate_program_count": 4,
            "scientific_computation": 0,
            "model_training": "NOT_STARTED",
            "model_refit": "NOT_RUN",
            "historical_p3_folds": 0,
            "forward_samples": 0,
            "forward_checkpoints": 0,
            "settlements": 0,
        },
        parent_digests=(*FROZEN_INPUT_DIGESTS, source_digest),
    )
    decision = _artifact(
        artifact_type=DECISION_ARTIFACT_TYPE,
        schema_version=DECISION_SCHEMA,
        domain=DECISION_DOMAIN,
        body={
            **decision_body,
            "status": "COMPLETE",
            "p3_scientific_disposition": "INCONCLUSIVE_DUE_TO_POWER",
            "p3_governance_status": "CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION",
            "formal_p4": "DEPENDENCY_WAIT",
            "pass_to_p4": "NOT_EMITTED",
            "p5": "NOT_AUTHORIZED",
            "promotion": "NOT_TRIGGERED",
            "successor_status_after_mainline": "READY",
            "successor_execution_authorized": False,
        },
        parent_digests=(feasibility["artifact_digest"], source_digest),
    )
    replay = _artifact(
        artifact_type=REPLAY_ARTIFACT_TYPE,
        schema_version=REPLAY_SCHEMA,
        domain=REPLAY_DOMAIN,
        body={
            "status": "REPLAY_VERIFIED",
            "registered_replay_status": "REGISTERED_REPLAY_VERIFIED",
            "feasibility_artifact_digest": feasibility["artifact_digest"],
            "program_decision_artifact_digest": decision["artifact_digest"],
            "same_registered_content": True,
            "workload_rerun": False,
            "scientific_computation": 0,
            "historical_result_values_read": 0,
            "forward_result_values_read": 0,
        },
        parent_digests=(feasibility["artifact_digest"], decision["artifact_digest"]),
    )
    return feasibility, decision, replay


def replay_registered_artifacts(
    *,
    source_contract: Mapping[str, Any],
    registered_inputs: Sequence[Mapping[str, Any]],
    stored_artifacts: Sequence[Mapping[str, Any]],
) -> tuple[tuple[dict[str, Any], ...], dict[str, Any]]:
    if len(stored_artifacts) != 3:
        raise M4V2ForwardEvidenceFeasibilityError(
            "forward_replay_artifact_count_changed"
        )
    expected = build_artifacts(
        source_contract=source_contract, registered_inputs=registered_inputs
    )
    validated = (
        _validate_artifact(
            stored_artifacts[0],
            artifact_type=FEASIBILITY_ARTIFACT_TYPE,
            schema_version=FEASIBILITY_SCHEMA,
            domain=FEASIBILITY_DOMAIN,
        ),
        _validate_artifact(
            stored_artifacts[1],
            artifact_type=DECISION_ARTIFACT_TYPE,
            schema_version=DECISION_SCHEMA,
            domain=DECISION_DOMAIN,
        ),
        _validate_artifact(
            stored_artifacts[2],
            artifact_type=REPLAY_ARTIFACT_TYPE,
            schema_version=REPLAY_SCHEMA,
            domain=REPLAY_DOMAIN,
        ),
    )
    if validated != expected:
        raise M4V2ForwardEvidenceFeasibilityError("forward_replay_content_changed")
    return expected, {
        "schema_version": "dehps-m4-v2-forward-evidence-program-capability-replay.v1",
        "status": "REPLAY_VERIFIED",
        "registered_replay_status": "REGISTERED_REPLAY_VERIFIED",
        "artifact_digests": [item["artifact_digest"] for item in expected],
        "same_registered_content": True,
        "workload_rerun": False,
        "scientific_computation": 0,
        "manual_input_assembly": False,
    }
