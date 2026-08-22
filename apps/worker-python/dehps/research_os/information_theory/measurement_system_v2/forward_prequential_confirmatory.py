from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from datetime import time as day_time
from pathlib import Path
from statistics import NormalDist, fmean
from typing import Any
from zoneinfo import ZoneInfo

from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentRequestStatus
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.db import get_connection
from dehps.input_contracts.candidate_abi import candidate_unrank
from dehps.prediction.v2.generator import UNIVERSE, _sample_lex_ids
from dehps.research_os.information_theory.measurement_system_v2 import (
    bounded_operational_forward as historical_bounded,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_contract import (
    ESTIMATOR_ID,
    estimate_legal_marginals,
)
from dehps.research_os.models import Task, m4_v2_domain_digest
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.research_os.supervisor import (
    AtomicArtifactPayload,
    AtomicCapabilityResult,
    MainlineSupervisorError,
    ResearchEvidenceSupervisor,
    integration_contract,
)
from dehps.storage.postgres_store import load_history_with_dates


class ForwardPrequentialConfirmatoryError(ValueError):
    pass


SOURCE_CONTRACT_PATH = (
    "configs/research-os/m4-p3-forward-prequential-confirmatory-source-v1.json"
)
SOURCE_SCHEMA = "dehps-m4-p3-forward-prequential-confirmatory-source-contract.v1"
SOURCE_ARTIFACT_TYPE = "m4_p3_forward_prequential_confirmatory_source_contract"
SOURCE_DOMAIN = "dehps.m4.p3.forward-prequential-confirmatory-source-contract.v1"
SOURCE_SET_DOMAIN = "dehps.m4.p3.forward-prequential-confirmatory-source-set.v1"

GOAL_KEY = "M4_P3_FORWARD_PREQUENTIAL_CONFIRMATORY_SUCCESSOR_AND_P4_ACTIVATION_GATE"
LINEAGE_ID = "M4_P3_FORWARD_PREQUENTIAL_CONFIRMATORY_SUCCESSOR_V1"
PREREGISTRATION_TASK_KEY = (
    "m4-p3-forward-prequential-confirmatory-successor-preregistration"
)
P4_TASK_KEY = "m4-p4-forward-prequential-confirmatory-negative-controls"
PREREGISTRATION_FACT = f"{PREREGISTRATION_TASK_KEY}:FROZEN"
P4_PREREGISTRATION_FACT = f"{P4_TASK_KEY}:PREREGISTRATION_FROZEN"
P3_COMPLETE_FACT = "m4-p3-forward-prequential-confirmatory-successor:COMPLETE"
PASS_TO_P4_FACT = "m4-p3-forward-prequential-confirmatory-successor-decision:PASS_TO_P4"
CURRENT_ROUTE_FACT = f"m4-forward-current-route:{LINEAGE_ID}"
OLD_ROUTE_HISTORY_FACT = (
    "m4-v2-bounded-operational-forward-study-preregistration:"
    "IMMUTABLE_HISTORY_NOT_CURRENT_ROUTE"
)
SOURCE_FACT_PREFIX = "m4-p3-forward-prequential-confirmatory-source:"

PREREGISTRATION_CAPABILITY = "m4_p3_forward_prequential_confirmatory_preregistration"
REFIT_CAPABILITY = "m4_p3_forward_prequential_confirmatory_refit"
PREDRAW_CAPABILITY = "m4_p3_forward_prequential_confirmatory_predraw"
PREDRAW_REPLAY_CAPABILITY = "m4_p3_forward_prequential_confirmatory_predraw_replay"
SETTLEMENT_CAPABILITY = "m4_p3_forward_prequential_confirmatory_settlement"
SETTLEMENT_REPLAY_CAPABILITY = (
    "m4_p3_forward_prequential_confirmatory_settlement_replay"
)
REVIEW_CAPABILITY = "m4_p3_forward_prequential_confirmatory_interim_review"
P4_CAPABILITY = "m4_p4_forward_prequential_confirmatory_negative_controls"

CAPABILITIES = (
    PREREGISTRATION_CAPABILITY,
    REFIT_CAPABILITY,
    PREDRAW_CAPABILITY,
    PREDRAW_REPLAY_CAPABILITY,
    SETTLEMENT_CAPABILITY,
    SETTLEMENT_REPLAY_CAPABILITY,
    REVIEW_CAPABILITY,
)

PREREGISTRATION_ARTIFACT_TYPE = "M4P3ForwardPrequentialPreregistration"
P4_PREREGISTRATION_ARTIFACT_TYPE = "M4P4ForwardConfirmatoryPreregistration"
DATASET_ARTIFACT_TYPE = "M4P3ForwardPrequentialDataset"
MODEL_ARTIFACT_TYPE = "M4P3ForwardPrequentialModel"
MODEL_CANDIDATE_ARTIFACT_TYPE = "M4P3ForwardPrequentialModelCandidateSet"
RANDOM_BASELINE_ARTIFACT_TYPE = "M4P3ForwardPrequentialRandomBaselineSet"
CHECKPOINT_ARTIFACT_TYPE = "M4P3ForwardPrequentialCheckpoint"
PREDRAW_REPORT_ARTIFACT_TYPE = "M4P3ForwardPrequentialPreDrawReport"
PREDRAW_REPLAY_ARTIFACT_TYPE = "M4P3ForwardPrequentialPreDrawReplay"
SETTLEMENT_ARTIFACT_TYPE = "M4P3ForwardPrequentialSettlement"
SETTLEMENT_REPLAY_ARTIFACT_TYPE = "M4P3ForwardPrequentialSettlementReplay"
REVIEW_ARTIFACT_TYPE = "M4P3ForwardPrequentialInterimDecision"

ARTIFACT_DOMAINS = {
    name: f"dehps.m4.p3.forward-prequential.{suffix}.v1"
    for name, suffix in {
        PREREGISTRATION_ARTIFACT_TYPE: "preregistration",
        P4_PREREGISTRATION_ARTIFACT_TYPE: "p4-preregistration",
        DATASET_ARTIFACT_TYPE: "dataset",
        MODEL_ARTIFACT_TYPE: "model",
        MODEL_CANDIDATE_ARTIFACT_TYPE: "model-candidates",
        RANDOM_BASELINE_ARTIFACT_TYPE: "random-baseline",
        CHECKPOINT_ARTIFACT_TYPE: "checkpoint",
        PREDRAW_REPORT_ARTIFACT_TYPE: "predraw-report",
        PREDRAW_REPLAY_ARTIFACT_TYPE: "predraw-replay",
        SETTLEMENT_ARTIFACT_TYPE: "settlement",
        SETTLEMENT_REPLAY_ARTIFACT_TYPE: "settlement-replay",
        REVIEW_ARTIFACT_TYPE: "interim-decision",
    }.items()
}

RESEARCH_REQUEST_KEY = (
    "research-m4-p3-forward-prequential-confirmatory-successor-preregistration-v1"
)
RESEARCH_REQUEST_ID = 640
RESEARCH_EXECUTION_ID = 524
RESEARCH_APPROVAL_DECISION_ID = 2697
ENGINEERING_REQUEST_KEY = (
    "engineering-m4-p3-forward-prequential-confirmatory-successor-launch-v1"
)
ENGINEERING_REQUEST_ID = 641
ENGINEERING_EXECUTION_ID = 525
ENGINEERING_APPROVAL_DECISION_ID = 2702

SHANGHAI = ZoneInfo("Asia/Shanghai")
LOOKS = (20, 40, 60, 90, 120)
MAX_N = 120
MODEL_TICKET_COUNT = 100
BASELINE_TICKET_COUNT = 100
PROPOSAL_POOL_SIZE = 10_000
UNIFORM_Q = 2.0 / 11.0
PRACTICAL_THRESHOLD = 0.05
FROZEN_LONG_RUN_VARIANCE = 0.05302208982040761
FROZEN_LONG_RUN_SD = 0.23026525969066114
CRITICAL_Z = 2.5758293035489
FUTILITY_THRESHOLD = 0.10


def issue_task_keys(issue: str) -> dict[str, str]:
    prefix = f"m4-p3-forward-prequential-{issue}"
    return {
        "refit": f"{prefix}-refit",
        "predraw": f"{prefix}-predraw",
        "predraw_replay": f"{prefix}-predraw-replay",
        "settlement": f"{prefix}-settlement",
        "settlement_replay": f"{prefix}-settlement-replay",
    }


def issue_facts(issue: str) -> dict[str, str]:
    keys = issue_task_keys(issue)
    return {
        "refit": f"{keys['refit']}:TRAINED",
        "predraw": f"{keys['predraw']}:SEALED_BEFORE_DRAW",
        "predraw_replay": f"{keys['predraw_replay']}:REGISTERED_REPLAY_VERIFIED",
        "draw_synced": f"m4-p3-forward-prequential:{issue}:DRAW_SYNCED",
        "settlement": f"{keys['settlement']}:SETTLED",
        "settlement_replay": f"{keys['settlement_replay']}:REGISTERED_REPLAY_VERIFIED",
    }


def review_task_key(look: int) -> str:
    if look not in LOOKS:
        raise ForwardPrequentialConfirmatoryError("unregistered_interim_look")
    return f"m4-p3-forward-prequential-look-{look}-review"


def review_ready_fact(look: int) -> str:
    return f"m4-p3-forward-prequential-look:{look}:READY"


def review_completion_fact(look: int) -> str:
    return f"{review_task_key(look)}:REVIEWED"


def decision_fact(look: int, decision: str) -> str:
    return f"m4-p3-forward-prequential-look:{look}:{decision}"


def _require_digest(value: object, name: str) -> str:
    digest = str(value or "")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ForwardPrequentialConfirmatoryError(f"{name}_invalid")
    return digest


def _artifact(
    *, artifact_type: str, body: Mapping[str, Any], parent_digests: Sequence[str]
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": f"dehps-{artifact_type}.v1",
        "artifact_type": artifact_type,
        "body": deepcopy(dict(body)),
        "parent_digests": [
            _require_digest(item, "parent_digest") for item in parent_digests
        ],
    }
    payload["artifact_digest"] = m4_v2_domain_digest(
        payload, domain=ARTIFACT_DOMAINS[artifact_type]
    )
    return payload


def validate_artifact(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(value))
    artifact_type = str(payload.get("artifact_type") or "")
    domain = ARTIFACT_DOMAINS.get(artifact_type)
    if domain is None or set(payload) != {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "body",
        "parent_digests",
    }:
        raise ForwardPrequentialConfirmatoryError("successor_artifact_shape_changed")
    if payload.get("schema_version") != f"dehps-{artifact_type}.v1":
        raise ForwardPrequentialConfirmatoryError("successor_artifact_schema_changed")
    observed = _require_digest(payload.pop("artifact_digest"), "artifact_digest")
    if m4_v2_domain_digest(payload, domain=domain) != observed:
        raise ForwardPrequentialConfirmatoryError("successor_artifact_digest_changed")
    payload["artifact_digest"] = observed
    return payload


def _canonical_payload_sha256(value: Mapping[str, Any]) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_source_contract(*, root_dir: Path = ROOT_DIR) -> dict[str, Any]:
    root = root_dir.resolve()
    path = (root / SOURCE_CONTRACT_PATH).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ForwardPrequentialConfirmatoryError("successor_source_missing")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or set(payload)
        != {
            "schema_version",
            "artifact_type",
            "artifact_digest",
            "contract_key",
            "frozen_contract",
            "governance_bindings",
            "source_entries",
            "source_set_digest",
        }
        or payload.get("schema_version") != SOURCE_SCHEMA
        or payload.get("artifact_type") != SOURCE_ARTIFACT_TYPE
        or payload.get("contract_key") != GOAL_KEY
    ):
        raise ForwardPrequentialConfirmatoryError("successor_source_shape_changed")
    frozen = payload.get("frozen_contract")
    if not isinstance(frozen, Mapping):
        raise ForwardPrequentialConfirmatoryError("successor_frozen_contract_missing")
    if (
        frozen.get("lineage_id") != LINEAGE_ID
        or frozen.get("practical_effect", {}).get("threshold_bits_per_issue")
        != PRACTICAL_THRESHOLD
        or tuple(frozen.get("interim_looks", ())) != LOOKS
        or frozen.get("maximum_valid_forward_issues") != MAX_N
        or frozen.get("historical_variance_freeze", {}).get("frozen_long_run_variance")
        != FROZEN_LONG_RUN_VARIANCE
        or frozen.get("multiplicity", {}).get("critical_z") != CRITICAL_Z
        or frozen.get("old_lineage", {}).get("disposition")
        != "IMMUTABLE_HISTORY_NOT_CURRENT_ROUTE"
    ):
        raise ForwardPrequentialConfirmatoryError("successor_contract_changed")
    entries: list[dict[str, str]] = []
    for item in payload.get("source_entries", []):
        if not isinstance(item, Mapping) or set(item) != {"path", "sha256"}:
            raise ForwardPrequentialConfirmatoryError("successor_source_entry_changed")
        relative = str(item["path"])
        absolute = (root / relative).resolve()
        if (
            not absolute.is_relative_to(root)
            or not absolute.is_file()
            or hashlib.sha256(absolute.read_bytes()).hexdigest() != item["sha256"]
        ):
            raise ForwardPrequentialConfirmatoryError(
                f"successor_source_bytes_changed:{relative}"
            )
        entries.append({"path": relative, "sha256": str(item["sha256"])})
    source_set_digest = m4_v2_domain_digest(
        {"source_entries": entries}, domain=SOURCE_SET_DOMAIN
    )
    identity = deepcopy(payload)
    observed = _require_digest(identity.pop("artifact_digest"), "source_digest")
    if (
        payload.get("source_set_digest") != source_set_digest
        or m4_v2_domain_digest(identity, domain=SOURCE_DOMAIN) != observed
    ):
        raise ForwardPrequentialConfirmatoryError("successor_source_identity_changed")
    return deepcopy(payload)


def verify_governance(repository: AgentRequestRepository) -> None:
    source = load_source_contract()
    bindings = source["governance_bindings"]
    specs = (
        (
            RESEARCH_REQUEST_KEY,
            RESEARCH_REQUEST_ID,
            RESEARCH_EXECUTION_ID,
            RESEARCH_APPROVAL_DECISION_ID,
            bindings["research_request_payload_sha256"],
            "APPROVE_RESULT_BLIND_FORWARD_PREQUENTIAL_CONFIRMATORY_SUCCESSOR_AND_DORMANT_P4",
        ),
        (
            ENGINEERING_REQUEST_KEY,
            ENGINEERING_REQUEST_ID,
            ENGINEERING_EXECUTION_ID,
            ENGINEERING_APPROVAL_DECISION_ID,
            bindings["engineering_request_payload_sha256"],
            "APPROVE_EXACT_FORWARD_PREQUENTIAL_CONFIRMATORY_SUCCESSOR_IMPLEMENTATION",
        ),
    )
    for key, request_id, execution_id, approval_id, payload_sha, outcome in specs:
        request = repository.get_request(key)
        executions = repository.list_executions(key)
        approvals = [
            item
            for item in repository.list_decisions(key)
            if item.decision_code == "request_approved"
        ]
        observed = None
        if len(approvals) == 1:
            observed = approvals[0].reason.get("decision") or approvals[0].reason.get(
                "outcome"
            )
        if (
            request.id != request_id
            or request.status
            not in {AgentRequestStatus.EXECUTING, AgentRequestStatus.COMPLETED}
            or _canonical_payload_sha256(request.payload) != payload_sha
            or len(executions) != 1
            or executions[0].id != execution_id
            or len(approvals) != 1
            or approvals[0].id != approval_id
            or observed != outcome
        ):
            raise ForwardPrequentialConfirmatoryError("successor_governance_changed")


def build_preregistration_artifacts(
    *, source_contract: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_digest = _require_digest(source_contract.get("artifact_digest"), "source")
    frozen = deepcopy(dict(source_contract["frozen_contract"]))
    preregistration = _artifact(
        artifact_type=PREREGISTRATION_ARTIFACT_TYPE,
        body={
            "status": "FROZEN",
            "result_blind": True,
            "successor_forward_results_read": False,
            "old_lineage_disposition": "IMMUTABLE_HISTORY_NOT_CURRENT_ROUTE",
            "old_checkpoint_reused": False,
            "contract": frozen,
            "next_consumer": "first_successor_marginal_static_refit",
        },
        parent_digests=(source_digest,),
    )
    p4 = _artifact(
        artifact_type=P4_PREREGISTRATION_ARTIFACT_TYPE,
        body={
            "status": "FROZEN_NOT_EXECUTED",
            "execution_task_key": P4_TASK_KEY,
            "ready_dependencies": [P3_COMPLETE_FACT, PASS_TO_P4_FACT],
            "execution_before_pass": "FORBIDDEN",
            "scope": frozen["formal_p4"]["scope"],
            "model_or_policy_change": "FORBIDDEN",
        },
        parent_digests=(preregistration["artifact_digest"], source_digest),
    )
    return preregistration, p4


def _normalize_history(
    history_rows: Sequence[object], *, target_issue: str
) -> list[tuple[str, str, tuple[int, ...]]]:
    return historical_bounded._normalize_history_rows(
        history_rows, before_issue=target_issue
    )


def fit_model_artifacts(
    *,
    source_contract: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    history_rows: Sequence[object],
    target_issue: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    prereg = validate_artifact(preregistration)
    rows = _normalize_history(history_rows, target_issue=target_issue)
    counts = [0] * 33
    for _, _, numbers in rows:
        for number in numbers:
            counts[number - 1] += 1
    probabilities = estimate_legal_marginals(counts, training_issue_count=len(rows))
    source_digest = str(source_contract["artifact_digest"])
    dataset = _artifact(
        artifact_type=DATASET_ARTIFACT_TYPE,
        body={
            "status": "FROZEN_INPUT",
            "target_issue": target_issue,
            "training_start_issue": rows[0][0],
            "training_end_issue": rows[-1][0],
            "training_issue_count": len(rows),
            "rows": [
                {"issue": issue, "draw_date": draw_date, "red_numbers": list(numbers)}
                for issue, draw_date, numbers in rows
            ],
            "future_rows_read": False,
        },
        parent_digests=(prereg["artifact_digest"], source_digest),
    )
    model = _artifact(
        artifact_type=MODEL_ARTIFACT_TYPE,
        body={
            "status": "TRAINED",
            "lineage_id": LINEAGE_ID,
            "mode": "MECHANICAL_REFIT_ONLY",
            "branch": "MARGINAL_STATIC",
            "estimator_identity": ESTIMATOR_ID,
            "target_issue": target_issue,
            "training_start_issue": rows[0][0],
            "training_end_issue": rows[-1][0],
            "training_issue_count": len(rows),
            "number_event_counts_1_to_33": counts,
            "probabilities_q_1_to_33": [float(item) for item in probabilities],
            "probability_fractions_q_1_to_33": [
                f"{item.numerator}/{item.denominator}" for item in probabilities
            ],
            "probability_sum": float(sum(probabilities)),
            "dataset_digest": dataset["artifact_digest"],
            "estimator_digest": canonical_digest(
                {"identity": ESTIMATOR_ID, "formula": "q_i=(c_i+2/11)/(n+1)"},
                domain="dehps.m4.p3.forward-prequential.estimator.v1",
            ),
            "feature_digest": canonical_digest(
                {"identity": "NO_FEATURES_33_EXPANDING_RED_NUMBER_EVENT_COUNTS_ONLY"},
                domain="dehps.m4.p3.forward-prequential.features.v1",
            ),
            "parameter_digest": canonical_digest(
                {
                    "alpha": 1,
                    "per_number_prior": "2/11",
                    "minimum_training_issues": 900,
                    "clipping": "forbidden",
                    "renormalization": "forbidden",
                    "hyperparameter_search": "none",
                },
                domain="dehps.m4.p3.forward-prequential.parameters.v1",
            ),
            "baseline_digest": canonical_digest(
                {"identity": "LEGAL_UNIFORM_NUMBER_EVENT_BASELINE", "q": "2/11"},
                domain="dehps.m4.p3.forward-prequential.baseline.v1",
            ),
            "source_digest": source_digest,
            "hyperparameter_search": "NONE",
            "model_selection": "NONE",
            "future_rows_read": False,
        },
        parent_digests=(
            dataset["artifact_digest"],
            prereg["artifact_digest"],
            source_digest,
        ),
    )
    return dataset, model


def target_for_now(
    history_rows: Sequence[object], *, moment: datetime | None = None
) -> tuple[str, date, datetime, datetime]:
    return historical_bounded.target_for_now(history_rows, moment=moment)


def _arm_seed(
    *, preregistration_digest: str, target_issue: str, arm: str, model_digest: str = ""
) -> str:
    return canonical_digest(
        {
            "lineage_id": LINEAGE_ID,
            "preregistration_digest": preregistration_digest,
            "target_issue": target_issue,
            "arm": arm,
            "model_digest": model_digest,
        },
        domain="dehps.m4.p3.forward-prequential.arm-seed.v1",
    )


def _blue_numbers(*, preregistration_digest: str, target_issue: str) -> list[int]:
    values: list[int] = []
    for rank in range(1, 101):
        raw = hashlib.sha256(
            b"dehps.m4.p3.forward-prequential.shared-blue-by-rank.v1\x00"
            + bytes.fromhex(preregistration_digest)
            + target_issue.encode("ascii")
            + rank.to_bytes(2, "big")
        ).digest()
        values.append(1 + (int.from_bytes(raw, "big") % 16))
    return values


def _ticket_score(numbers: Sequence[int], probabilities: Sequence[float]) -> float:
    selected = {int(item) for item in numbers}
    return sum(
        math.log2(q if index in selected else 1.0 - q)
        for index, q in enumerate(probabilities, start=1)
    )


def generate_predraw_artifacts(
    *,
    preregistration: Mapping[str, Any],
    model: Mapping[str, Any],
    target_draw_date: date,
    sealed_at: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    prereg = validate_artifact(preregistration)
    verified_model = validate_artifact(model)
    body = verified_model["body"]
    target_issue = str(body["target_issue"])
    moment = (sealed_at or datetime.now(SHANGHAI)).astimezone(SHANGHAI)
    deadline = datetime.combine(target_draw_date, day_time(17, 0), tzinfo=SHANGHAI)
    official = datetime.combine(target_draw_date, day_time(21, 15), tzinfo=SHANGHAI)
    if moment > deadline or moment >= official:
        raise ForwardPrequentialConfirmatoryError("checkpoint_deadline_missed")
    probabilities = [float(item) for item in body["probabilities_q_1_to_33"]]
    if len(probabilities) != 33 or not math.isclose(
        sum(probabilities), 6.0, abs_tol=1e-12
    ):
        raise ForwardPrequentialConfirmatoryError("model_probability_vector_invalid")
    prereg_digest = str(prereg["artifact_digest"])
    model_digest = str(verified_model["artifact_digest"])
    model_seed = _arm_seed(
        preregistration_digest=prereg_digest,
        target_issue=target_issue,
        arm="MODEL_PROPOSAL_POOL",
        model_digest=model_digest,
    )
    baseline_seed = _arm_seed(
        preregistration_digest=prereg_digest,
        target_issue=target_issue,
        arm="RANDOM_BASELINE",
    )
    proposal_lex_ids = _sample_lex_ids(
        seed_material=bytes.fromhex(model_seed), count=PROPOSAL_POOL_SIZE
    )
    proposal_rows = [
        candidate_unrank(item, universe=UNIVERSE) for item in proposal_lex_ids
    ]
    scored = sorted(
        (
            (_ticket_score(row, probabilities), lex_id, row)
            for lex_id, row in zip(proposal_lex_ids, proposal_rows, strict=True)
        ),
        key=lambda item: (-item[0], item[1]),
    )[:MODEL_TICKET_COUNT]
    baseline_lex_ids = _sample_lex_ids(
        seed_material=bytes.fromhex(baseline_seed), count=BASELINE_TICKET_COUNT
    )
    baseline_rows = [
        candidate_unrank(item, universe=UNIVERSE) for item in baseline_lex_ids
    ]
    blues = _blue_numbers(
        preregistration_digest=prereg_digest, target_issue=target_issue
    )
    blue_strategy_digest = canonical_digest(
        {
            "identity": "SHARED_DETERMINISTIC_UNIFORM_BLUE_BY_RANK_V1",
            "target_issue": target_issue,
            "values": blues,
        },
        domain="dehps.m4.p3.forward-prequential.blue-strategy.v1",
    )
    candidates = _artifact(
        artifact_type=MODEL_CANDIDATE_ARTIFACT_TYPE,
        body={
            "mode": "SHADOW_ONLY",
            "target_issue": target_issue,
            "candidate_count": MODEL_TICKET_COUNT,
            "proposal_pool_size": PROPOSAL_POOL_SIZE,
            "seed_digest": model_seed,
            "ranking": "DESCENDING_33_EVENT_BERNOULLI_LOG_SCORE",
            "tie_break": "ASCENDING_LEX_ID",
            "blue_strategy_digest": blue_strategy_digest,
            "tickets": [
                {
                    "rank": rank,
                    "lex_id": lex_id,
                    "red_numbers": list(row),
                    "blue_number": blues[rank - 1],
                    "model_log2_score": score,
                }
                for rank, (score, lex_id, row) in enumerate(scored, start=1)
            ],
        },
        parent_digests=(model_digest, prereg_digest),
    )
    baseline = _artifact(
        artifact_type=RANDOM_BASELINE_ARTIFACT_TYPE,
        body={
            "mode": "SHADOW_ONLY",
            "target_issue": target_issue,
            "candidate_count": BASELINE_TICKET_COUNT,
            "seed_digest": baseline_seed,
            "sampling": "UNIFORM_LEGAL_SIX_OF_33_WITHOUT_REPLACEMENT",
            "blue_strategy_digest": blue_strategy_digest,
            "tickets": [
                {
                    "rank": rank,
                    "lex_id": lex_id,
                    "red_numbers": list(row),
                    "blue_number": blues[rank - 1],
                }
                for rank, (lex_id, row) in enumerate(
                    zip(baseline_lex_ids, baseline_rows, strict=True), start=1
                )
            ],
        },
        parent_digests=(prereg_digest,),
    )
    checkpoint = _artifact(
        artifact_type=CHECKPOINT_ARTIFACT_TYPE,
        body={
            "status": "SEALED_BEFORE_DRAW",
            "lineage_id": LINEAGE_ID,
            "target_issue": target_issue,
            "training_end_issue": body["training_end_issue"],
            "dataset_digest": body["dataset_digest"],
            "model_digest": model_digest,
            "source_digest": body["source_digest"],
            "feature_digest": body["feature_digest"],
            "parameter_digest": body["parameter_digest"],
            "baseline_digest": body["baseline_digest"],
            "model_candidate_digest": candidates["artifact_digest"],
            "random_baseline_digest": baseline["artifact_digest"],
            "blue_strategy_digest": blue_strategy_digest,
            "same_blue_strategy": True,
            "model_ticket_count": MODEL_TICKET_COUNT,
            "random_baseline_ticket_count": BASELINE_TICKET_COUNT,
            "sealed_at": moment.isoformat(),
            "checkpoint_deadline": deadline.isoformat(),
            "official_draw_time": official.isoformat(),
            "configuration_drift": False,
            "old_checkpoint_reused": False,
            "production_betting_authorized": False,
        },
        parent_digests=(
            model_digest,
            candidates["artifact_digest"],
            baseline["artifact_digest"],
            prereg_digest,
        ),
    )
    markdown = "\n".join(
        [
            f"# M4-P3 forward prequential pre-draw report: {target_issue}",
            "",
            f"Lineage: `{LINEAGE_ID}`",
            "Mode: `SHADOW_ONLY / AUTONOMOUS_REFIT`",
            f"Training end issue: `{body['training_end_issue']}`",
            f"Model digest: `{model_digest}`",
            f"Model tickets: `{MODEL_TICKET_COUNT}`",
            f"Random baseline tickets: `{BASELINE_TICKET_COUNT}`",
            "Blue strategy: `SHARED_DETERMINISTIC_UNIFORM_BLUE_BY_RANK_V1` (same by rank)",
            f"Checkpoint sealed at: `{moment.isoformat()}`",
            f"Official draw time: `{official.isoformat()}`",
            "Configuration drift: `false`",
            "",
            "This is a preregistered shadow prediction artifact, not betting advice or proof of advantage.",
        ]
    )
    report = _artifact(
        artifact_type=PREDRAW_REPORT_ARTIFACT_TYPE,
        body={
            "status": "PUBLISHED",
            "target_issue": target_issue,
            "checkpoint_digest": checkpoint["artifact_digest"],
            "model_candidate_digest": candidates["artifact_digest"],
            "random_baseline_digest": baseline["artifact_digest"],
            "markdown": markdown,
        },
        parent_digests=(checkpoint["artifact_digest"],),
    )
    return candidates, baseline, checkpoint, report


def build_predraw_replay_artifact(
    *,
    model_candidates: Mapping[str, Any],
    random_baseline: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    report: Mapping[str, Any],
) -> dict[str, Any]:
    values = tuple(
        validate_artifact(item)
        for item in (
            model_candidates,
            random_baseline,
            checkpoint,
            report,
        )
    )
    if (
        model_candidates["body"].get("candidate_count") != 100
        or random_baseline["body"].get("candidate_count") != 100
        or checkpoint["body"].get("same_blue_strategy") is not True
        or checkpoint["body"].get("configuration_drift") is not False
        or checkpoint["body"].get("old_checkpoint_reused") is not False
    ):
        raise ForwardPrequentialConfirmatoryError("predraw_replay_invariant_changed")
    return _artifact(
        artifact_type=PREDRAW_REPLAY_ARTIFACT_TYPE,
        body={
            "status": "REPLAY_VERIFIED",
            "registered_replay_status": "REGISTERED_REPLAY_VERIFIED",
            "target_issue": checkpoint["body"]["target_issue"],
            "model_ticket_count": 100,
            "random_baseline_ticket_count": 100,
            "same_blue_strategy": True,
            "configuration_drift": False,
            "old_checkpoint_reused": False,
            "same_registered_content": True,
            "workload_rerun": False,
        },
        parent_digests=tuple(item["artifact_digest"] for item in values),
    )


def _support(
    value: Mapping[str, Any], actual: tuple[int, ...], blue: int
) -> dict[str, Any]:
    tickets = value["body"]["tickets"]
    red_hits = [len(set(item["red_numbers"]) & set(actual)) for item in tickets]
    blue_hits = [item["blue_number"] == blue for item in tickets]
    return {
        "max_red_hits": max(red_hits),
        "red_hit_histogram": {str(k): red_hits.count(k) for k in range(7)},
        "blue_hit_count": sum(blue_hits),
        "red6_blue_hit_count": sum(
            red == 6 and hit for red, hit in zip(red_hits, blue_hits, strict=True)
        ),
    }


def build_settlement_artifact(
    *,
    model: Mapping[str, Any],
    model_candidates: Mapping[str, Any],
    random_baseline: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    actual_red_numbers: Sequence[int],
    actual_blue_number: int,
    durable_event_key: str,
    history_fingerprint: str,
    cohort_index: int,
) -> dict[str, Any]:
    model = validate_artifact(model)
    model_candidates = validate_artifact(model_candidates)
    random_baseline = validate_artifact(random_baseline)
    checkpoint = validate_artifact(checkpoint)
    actual = tuple(sorted(int(item) for item in actual_red_numbers))
    blue = int(actual_blue_number)
    if (
        len(actual) != 6
        or len(set(actual)) != 6
        or actual[0] < 1
        or actual[-1] > 33
        or not 1 <= blue <= 16
        or checkpoint["body"].get("status") != "SEALED_BEFORE_DRAW"
        or datetime.fromisoformat(checkpoint["body"]["sealed_at"])
        >= datetime.fromisoformat(checkpoint["body"]["official_draw_time"])
        or cohort_index < 1
        or cohort_index > MAX_N
    ):
        raise ForwardPrequentialConfirmatoryError("settlement_boundary_invalid")
    probabilities = [float(item) for item in model["body"]["probabilities_q_1_to_33"]]
    model_score = _ticket_score(actual, probabilities)
    baseline_score = _ticket_score(actual, [UNIFORM_Q] * 33)
    return _artifact(
        artifact_type=SETTLEMENT_ARTIFACT_TYPE,
        body={
            "status": "SETTLED",
            "lineage_id": LINEAGE_ID,
            "cohort_index": cohort_index,
            "target_issue": checkpoint["body"]["target_issue"],
            "actual_red_numbers": list(actual),
            "actual_blue_number": blue,
            "durable_event_key": durable_event_key,
            "history_fingerprint": history_fingerprint,
            "model_probability_log2_score": model_score,
            "legal_uniform_log2_score": baseline_score,
            "primary_endpoint_bits_per_issue": model_score - baseline_score,
            "model_ticket_support": _support(model_candidates, actual, blue),
            "random_baseline_ticket_support": _support(random_baseline, actual, blue),
            "ticket_support_decision_credit": False,
            "configuration_drift": False,
            "old_lineage_result": False,
            "next_consumer": "registered_settlement_replay_then_next_issue_or_frozen_look",
        },
        parent_digests=(
            model["artifact_digest"],
            model_candidates["artifact_digest"],
            random_baseline["artifact_digest"],
            checkpoint["artifact_digest"],
        ),
    )


def build_settlement_replay_artifact(
    *, settlement: Mapping[str, Any], checkpoint: Mapping[str, Any]
) -> dict[str, Any]:
    settlement = validate_artifact(settlement)
    checkpoint = validate_artifact(checkpoint)
    if settlement["body"]["target_issue"] != checkpoint["body"]["target_issue"]:
        raise ForwardPrequentialConfirmatoryError("settlement_replay_issue_changed")
    return _artifact(
        artifact_type=SETTLEMENT_REPLAY_ARTIFACT_TYPE,
        body={
            "status": "REPLAY_VERIFIED",
            "registered_replay_status": "REGISTERED_REPLAY_VERIFIED",
            "target_issue": settlement["body"]["target_issue"],
            "cohort_index": settlement["body"]["cohort_index"],
            "configuration_drift": False,
            "same_registered_content": True,
            "workload_rerun": False,
        },
        parent_digests=(settlement["artifact_digest"], checkpoint["artifact_digest"]),
    )


def conditional_power_at_practical_threshold(*, n: int, total_gain: float) -> float:
    if n >= MAX_N:
        return 0.0
    final_required_sum = CRITICAL_Z * FROZEN_LONG_RUN_SD * math.sqrt(MAX_N)
    future_mean = (MAX_N - n) * PRACTICAL_THRESHOLD
    future_sd = FROZEN_LONG_RUN_SD * math.sqrt(MAX_N - n)
    z = (final_required_sum - total_gain - future_mean) / future_sd
    return 1.0 - NormalDist().cdf(z)


def build_review_artifact(
    *, look: int, settlements: Sequence[Mapping[str, Any]], source_digest: str
) -> tuple[dict[str, Any], str]:
    if look not in LOOKS or len(settlements) != look:
        raise ForwardPrequentialConfirmatoryError("interim_review_count_changed")
    validated = [validate_artifact(item) for item in settlements]
    ordered = sorted(validated, key=lambda item: int(item["body"]["cohort_index"]))
    indices = [int(item["body"]["cohort_index"]) for item in ordered]
    issues = [str(item["body"]["target_issue"]) for item in ordered]
    gains = [float(item["body"]["primary_endpoint_bits_per_issue"]) for item in ordered]
    integrity = (
        indices == list(range(1, look + 1))
        and len(set(issues)) == look
        and all(item["body"].get("configuration_drift") is False for item in ordered)
    )
    mean_gain = fmean(gains)
    standard_error = FROZEN_LONG_RUN_SD / math.sqrt(look)
    z_score = mean_gain / standard_error
    upper_bound = mean_gain + CRITICAL_Z * standard_error
    conditional_power = (
        conditional_power_at_practical_threshold(n=look, total_gain=sum(gains))
        if look < MAX_N
        else None
    )
    if not integrity:
        decision = "INVALID_FORWARD_EXECUTION"
    elif mean_gain >= PRACTICAL_THRESHOLD and z_score >= CRITICAL_Z:
        decision = "PASS_TO_P4"
    elif upper_bound < 0 or (
        look < MAX_N
        and conditional_power is not None
        and conditional_power < FUTILITY_THRESHOLD
    ):
        decision = "FAIL_NO_FORWARD_ADVANTAGE"
    elif look < MAX_N:
        decision = "CONTINUE_TO_NEXT_LOOK"
    else:
        decision = "INCONCLUSIVE_AT_MAX_N"
    artifact = _artifact(
        artifact_type=REVIEW_ARTIFACT_TYPE,
        body={
            "status": "FROZEN_POLICY_APPLIED",
            "look": look,
            "decision": decision,
            "allowed_decision": True,
            "integrity_pass": integrity,
            "issue_count": look,
            "issues": issues,
            "mean_gain_bits_per_issue": mean_gain,
            "standard_error_bits_per_issue": standard_error,
            "z_score": z_score,
            "critical_z": CRITICAL_Z,
            "practical_threshold_bits_per_issue": PRACTICAL_THRESHOLD,
            "one_sided_upper_bound_bits_per_issue": upper_bound,
            "conditional_power_at_practical_threshold": conditional_power,
            "multiplicity": "ONE_SIDED_BONFERRONI_FIXED_FIVE_LOOKS_ALPHA_0_005_PER_LOOK",
            "lineage_terminal": decision
            in {
                "PASS_TO_P4",
                "FAIL_NO_FORWARD_ADVANTAGE",
                "INVALID_FORWARD_EXECUTION",
                "INCONCLUSIVE_AT_MAX_N",
            },
            "formal_p4_ready": decision == "PASS_TO_P4",
            "source_digest": source_digest,
        },
        parent_digests=tuple(
            [item["artifact_digest"] for item in ordered] + [source_digest]
        ),
    )
    return artifact, decision


@dataclass
class ForwardPrequentialCapability:
    repository: PostgresResearchOSRepository
    root_dir: Path = ROOT_DIR

    def __post_init__(self) -> None:
        self.agent_repository = AgentRequestRepository()

    @staticmethod
    def _contract(task: Task) -> dict[str, Any]:
        return dict(task.to_dict().get("metric_contract", {}))

    def _source(self, task: Task) -> dict[str, Any]:
        source = load_source_contract(root_dir=self.root_dir)
        verify_governance(self.agent_repository)
        if task.input_artifact_digests != (source["artifact_digest"],):
            raise MainlineSupervisorError("successor source input changed")
        return source

    def _completed(self, *, task_key: str, artifact_type: str) -> dict[str, Any]:
        events = self.repository.list_mainline_execution_events(
            control_plane_key="m4-information-theory-mainline", task_key=task_key
        )
        completed = [item for item in events if item.get("event_type") == "completed"]
        if len(completed) != 1:
            raise MainlineSupervisorError(
                f"expected one completed successor task: {task_key}"
            )
        registrations = self.repository.list_mainline_artifacts(
            control_plane_key="m4-information-theory-mainline",
            execution_id=str(completed[0]["execution_id"]),
        )
        matches = [
            item for item in registrations if item["artifact_type"] == artifact_type
        ]
        if len(matches) != 1:
            raise MainlineSupervisorError(
                f"expected one successor artifact {artifact_type}: {task_key}"
            )
        return validate_artifact(
            json.loads((self.root_dir / str(matches[0]["artifact_path"])).read_text())
        )

    def _settlements(self) -> list[dict[str, Any]]:
        manifest = self.repository.load_manifest(
            control_plane_key="m4-information-theory-mainline"
        )
        output: list[dict[str, Any]] = []
        for task in manifest.tasks:
            if task.requested_capability != SETTLEMENT_CAPABILITY:
                continue
            events = self.repository.list_mainline_execution_events(
                control_plane_key="m4-information-theory-mainline",
                task_key=task.task_key,
            )
            completed = [
                item for item in events if item.get("event_type") == "completed"
            ]
            if len(completed) == 1:
                output.append(
                    self._completed(
                        task_key=task.task_key, artifact_type=SETTLEMENT_ARTIFACT_TYPE
                    )
                )
        return sorted(output, key=lambda item: int(item["body"]["cohort_index"]))

    def execute(
        self, *, control_plane_key: str, task: Task, execution_id: str, git_commit: str
    ) -> AtomicCapabilityResult:
        del execution_id, git_commit
        if control_plane_key != "m4-information-theory-mainline":
            raise MainlineSupervisorError("successor control plane changed")
        integration_contract(task)
        source = self._source(task)
        capability = str(task.requested_capability)
        contract = self._contract(task)
        metadata: list[tuple[str, Any]] = [
            ("source_contract_digest", source["artifact_digest"]),
            ("lineage_id", LINEAGE_ID),
            ("configuration_drift", False),
            ("old_lineage_current_projection", False),
        ]
        if capability == PREREGISTRATION_CAPABILITY:
            if task.task_key != PREREGISTRATION_TASK_KEY:
                raise MainlineSupervisorError(
                    "successor preregistration identity changed"
                )
            prereg, p4 = build_preregistration_artifacts(source_contract=source)
            return AtomicCapabilityResult(
                artifacts=(
                    AtomicArtifactPayload(
                        "forward-prequential-preregistration",
                        "preregistration.json",
                        prereg,
                    ),
                    AtomicArtifactPayload(
                        "formal-p4-preregistration", "preregistration.json", p4
                    ),
                ),
                completion_facts=(PREREGISTRATION_FACT, P4_PREREGISTRATION_FACT),
                execution_metadata=tuple(metadata)
                + (
                    ("practical_threshold", PRACTICAL_THRESHOLD),
                    ("forward_results_read", False),
                ),
            )
        target_issue = str(contract.get("target_issue") or "")
        keys = issue_task_keys(target_issue) if target_issue else {}
        expected = {
            REFIT_CAPABILITY: keys.get("refit"),
            PREDRAW_CAPABILITY: keys.get("predraw"),
            PREDRAW_REPLAY_CAPABILITY: keys.get("predraw_replay"),
            SETTLEMENT_CAPABILITY: keys.get("settlement"),
            SETTLEMENT_REPLAY_CAPABILITY: keys.get("settlement_replay"),
        }
        if capability in expected and task.task_key != expected[capability]:
            raise MainlineSupervisorError("successor issue task identity changed")
        if capability == REFIT_CAPABILITY:
            prereg = self._completed(
                task_key=PREREGISTRATION_TASK_KEY,
                artifact_type=PREREGISTRATION_ARTIFACT_TYPE,
            )
            with get_connection() as connection:
                history = load_history_with_dates(connection)
            dataset, model = fit_model_artifacts(
                source_contract=source,
                preregistration=prereg,
                history_rows=history,
                target_issue=target_issue,
            )
            return AtomicCapabilityResult(
                artifacts=(
                    AtomicArtifactPayload(
                        "forward-prequential-dataset", "dataset.json", dataset
                    ),
                    AtomicArtifactPayload(
                        "forward-prequential-model", "model.json", model
                    ),
                ),
                completion_facts=(issue_facts(target_issue)["refit"],),
                execution_metadata=tuple(metadata)
                + (("target_issue", target_issue), ("probability_vector_length", 33)),
            )
        if capability == PREDRAW_CAPABILITY:
            prereg = self._completed(
                task_key=PREREGISTRATION_TASK_KEY,
                artifact_type=PREREGISTRATION_ARTIFACT_TYPE,
            )
            model = self._completed(
                task_key=keys["refit"], artifact_type=MODEL_ARTIFACT_TYPE
            )
            artifacts = generate_predraw_artifacts(
                preregistration=prereg,
                model=model,
                target_draw_date=date.fromisoformat(str(contract["target_draw_date"])),
            )
            slugs = (
                ("forward-prequential-model-candidates", "model-candidates.json"),
                ("forward-prequential-random-baseline", "random-baseline.json"),
                ("forward-prequential-checkpoint", "checkpoint.json"),
                ("forward-prequential-predraw-report", "pre-draw-report.json"),
            )
            return AtomicCapabilityResult(
                artifacts=tuple(
                    AtomicArtifactPayload(slug, filename, payload)
                    for (slug, filename), payload in zip(slugs, artifacts, strict=True)
                ),
                completion_facts=(issue_facts(target_issue)["predraw"],),
                execution_metadata=tuple(metadata)
                + (
                    ("target_issue", target_issue),
                    ("model_ticket_count", 100),
                    ("random_baseline_ticket_count", 100),
                    ("same_blue_strategy", True),
                ),
            )
        if capability == PREDRAW_REPLAY_CAPABILITY:
            candidates = self._completed(
                task_key=keys["predraw"], artifact_type=MODEL_CANDIDATE_ARTIFACT_TYPE
            )
            baseline = self._completed(
                task_key=keys["predraw"], artifact_type=RANDOM_BASELINE_ARTIFACT_TYPE
            )
            checkpoint = self._completed(
                task_key=keys["predraw"], artifact_type=CHECKPOINT_ARTIFACT_TYPE
            )
            report = self._completed(
                task_key=keys["predraw"], artifact_type=PREDRAW_REPORT_ARTIFACT_TYPE
            )
            replay = build_predraw_replay_artifact(
                model_candidates=candidates,
                random_baseline=baseline,
                checkpoint=checkpoint,
                report=report,
            )
            return AtomicCapabilityResult(
                artifacts=(
                    AtomicArtifactPayload(
                        "forward-prequential-predraw-replay", "replay.json", replay
                    ),
                ),
                completion_facts=(issue_facts(target_issue)["predraw_replay"],),
                execution_metadata=tuple(metadata)
                + (
                    ("target_issue", target_issue),
                    ("registered_replay_status", "REGISTERED_REPLAY_VERIFIED"),
                ),
            )
        if capability == SETTLEMENT_CAPABILITY:
            model = self._completed(
                task_key=keys["refit"], artifact_type=MODEL_ARTIFACT_TYPE
            )
            candidates = self._completed(
                task_key=keys["predraw"], artifact_type=MODEL_CANDIDATE_ARTIFACT_TYPE
            )
            baseline = self._completed(
                task_key=keys["predraw"], artifact_type=RANDOM_BASELINE_ARTIFACT_TYPE
            )
            checkpoint = self._completed(
                task_key=keys["predraw"], artifact_type=CHECKPOINT_ARTIFACT_TYPE
            )
            with get_connection() as connection:
                row = connection.execute(
                    """
                    SELECT h.red_numbers, h.blue_number, e.event_key, e.history_fingerprint
                      FROM ssq_history h
                      JOIN draw_issue_events e ON e.new_issue = h.issue
                      JOIN draw_sync_runs r ON r.event_key = e.event_key
                     WHERE h.issue = %s AND r.completed_at IS NOT NULL
                       AND r.audit_passed IS TRUE AND r.status = 'new_issue'
                     ORDER BY r.completed_at DESC LIMIT 1
                    """,
                    (target_issue,),
                ).fetchone()
            if row is None:
                raise MainlineSupervisorError("successor settlement lacks audited draw")
            settlements = self._settlements()
            if any(
                item["body"]["target_issue"] == target_issue for item in settlements
            ):
                raise MainlineSupervisorError("successor duplicate issue settlement")
            settlement = build_settlement_artifact(
                model=model,
                model_candidates=candidates,
                random_baseline=baseline,
                checkpoint=checkpoint,
                actual_red_numbers=row[0],
                actual_blue_number=int(row[1]),
                durable_event_key=str(row[2]),
                history_fingerprint=str(row[3]),
                cohort_index=len(settlements) + 1,
            )
            return AtomicCapabilityResult(
                artifacts=(
                    AtomicArtifactPayload(
                        "forward-prequential-settlement", "settlement.json", settlement
                    ),
                ),
                completion_facts=(issue_facts(target_issue)["settlement"],),
                execution_metadata=tuple(metadata)
                + (
                    ("target_issue", target_issue),
                    ("cohort_index", len(settlements) + 1),
                ),
            )
        if capability == SETTLEMENT_REPLAY_CAPABILITY:
            settlement = self._completed(
                task_key=keys["settlement"], artifact_type=SETTLEMENT_ARTIFACT_TYPE
            )
            checkpoint = self._completed(
                task_key=keys["predraw"], artifact_type=CHECKPOINT_ARTIFACT_TYPE
            )
            replay = build_settlement_replay_artifact(
                settlement=settlement, checkpoint=checkpoint
            )
            cohort_index = int(settlement["body"]["cohort_index"])
            facts = [issue_facts(target_issue)["settlement_replay"]]
            if cohort_index in LOOKS:
                facts.append(review_ready_fact(cohort_index))
            return AtomicCapabilityResult(
                artifacts=(
                    AtomicArtifactPayload(
                        "forward-prequential-settlement-replay", "replay.json", replay
                    ),
                ),
                completion_facts=tuple(facts),
                execution_metadata=tuple(metadata)
                + (("target_issue", target_issue), ("cohort_index", cohort_index)),
            )
        if capability == REVIEW_CAPABILITY:
            look = int(contract.get("look") or 0)
            if task.task_key != review_task_key(look):
                raise MainlineSupervisorError("successor review task identity changed")
            settlements = self._settlements()
            artifact, decision = build_review_artifact(
                look=look,
                settlements=settlements,
                source_digest=str(source["artifact_digest"]),
            )
            facts = [review_completion_fact(look), decision_fact(look, decision)]
            if decision == "PASS_TO_P4":
                facts.extend((P3_COMPLETE_FACT, PASS_TO_P4_FACT))
            elif decision in {
                "FAIL_NO_FORWARD_ADVANTAGE",
                "INVALID_FORWARD_EXECUTION",
                "INCONCLUSIVE_AT_MAX_N",
            }:
                facts.append(
                    f"m4-p3-forward-prequential-confirmatory-successor:TERMINAL:{decision}"
                )
            return AtomicCapabilityResult(
                artifacts=(
                    AtomicArtifactPayload(
                        "forward-prequential-interim-decision",
                        "decision.json",
                        artifact,
                    ),
                ),
                completion_facts=tuple(facts),
                execution_metadata=tuple(metadata)
                + (
                    ("look", look),
                    ("decision", decision),
                    ("aggregate_outcome_exposed", True),
                ),
            )
        raise MainlineSupervisorError(f"unsupported successor capability: {capability}")


class ForwardPrequentialSupervisor(ResearchEvidenceSupervisor):
    """Research Evidence Supervisor with only the frozen successor extension."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        capability = ForwardPrequentialCapability(
            repository=self.repository, root_dir=self.root_dir
        )
        for name in CAPABILITIES:
            self.capabilities[name] = capability

    def replay(
        self, *, task_key: str, execution_id: str | None = None
    ) -> dict[str, Any]:
        manifest = self.repository.load_manifest(
            control_plane_key=self.control_plane_key
        )
        tasks = [item for item in manifest.tasks if item.task_key == task_key]
        if len(tasks) != 1 or tasks[0].requested_capability not in CAPABILITIES:
            return super().replay(task_key=task_key, execution_id=execution_id)
        events = self.repository.list_mainline_execution_events(
            control_plane_key=self.control_plane_key,
            task_key=task_key,
            execution_id=execution_id,
        )
        completed = [item for item in events if item.get("event_type") == "completed"]
        if len(completed) != 1:
            raise MainlineSupervisorError("successor replay requires one completion")
        resolved_execution_id = str(completed[0]["execution_id"])
        registrations = list(
            self.repository.list_mainline_artifacts(
                control_plane_key=self.control_plane_key,
                execution_id=resolved_execution_id,
            )
        )
        children = [
            item
            for item in registrations
            if item.get("artifact_type") != "research_os_mainline_execution"
        ]
        if not children:
            raise MainlineSupervisorError("successor replay artifact set is empty")
        validated = []
        for item in children:
            path = self.root_dir / str(item["artifact_path"])
            payload = validate_artifact(json.loads(path.read_text(encoding="utf-8")))
            if payload["artifact_digest"] != item["artifact_digest"]:
                raise MainlineSupervisorError("successor registered digest changed")
            validated.append(payload)
        types = {item["artifact_type"] for item in validated}
        capability = str(tasks[0].requested_capability)
        expected_types = {
            PREREGISTRATION_CAPABILITY: {
                PREREGISTRATION_ARTIFACT_TYPE,
                P4_PREREGISTRATION_ARTIFACT_TYPE,
            },
            REFIT_CAPABILITY: {DATASET_ARTIFACT_TYPE, MODEL_ARTIFACT_TYPE},
            PREDRAW_CAPABILITY: {
                MODEL_CANDIDATE_ARTIFACT_TYPE,
                RANDOM_BASELINE_ARTIFACT_TYPE,
                CHECKPOINT_ARTIFACT_TYPE,
                PREDRAW_REPORT_ARTIFACT_TYPE,
            },
            PREDRAW_REPLAY_CAPABILITY: {PREDRAW_REPLAY_ARTIFACT_TYPE},
            SETTLEMENT_CAPABILITY: {SETTLEMENT_ARTIFACT_TYPE},
            SETTLEMENT_REPLAY_CAPABILITY: {SETTLEMENT_REPLAY_ARTIFACT_TYPE},
            REVIEW_CAPABILITY: {REVIEW_ARTIFACT_TYPE},
        }[capability]
        if types != expected_types:
            raise MainlineSupervisorError("successor replay artifact types changed")
        return {
            "schema_version": "dehps-research-evidence-supervisor-replay.v1",
            "status": "REPLAY_VERIFIED",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "control_plane_key": self.control_plane_key,
            "task_key": task_key,
            "execution_id": resolved_execution_id,
            "registered_artifact_count": len(registrations),
            "same_execution_identity": True,
            "same_artifact_identity": True,
            "same_registered_content": True,
            "manual_input_assembly": False,
            "dispatch_performed": False,
            "durable_state_changed": False,
        }


def old_source_digest_verification() -> dict[str, Any]:
    source = historical_bounded.load_source_contract(root_dir=ROOT_DIR)
    return {
        "status": "VERIFIED",
        "artifact_digest": source["artifact_digest"],
        "source_set_digest": source["source_set_digest"],
    }


def unit_active(unit: str) -> bool:
    completed = subprocess.run(
        ["systemctl", "--user", "is-active", "--quiet", unit],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.returncode == 0


__all__ = [name for name in globals() if name.isupper()] + [
    "ForwardPrequentialCapability",
    "ForwardPrequentialConfirmatoryError",
    "ForwardPrequentialSupervisor",
    "build_predraw_replay_artifact",
    "build_preregistration_artifacts",
    "build_review_artifact",
    "build_settlement_artifact",
    "build_settlement_replay_artifact",
    "conditional_power_at_practical_threshold",
    "decision_fact",
    "fit_model_artifacts",
    "generate_predraw_artifacts",
    "issue_facts",
    "issue_task_keys",
    "load_source_contract",
    "old_source_digest_verification",
    "review_completion_fact",
    "review_ready_fact",
    "review_task_key",
    "target_for_now",
    "unit_active",
    "validate_artifact",
    "verify_governance",
]
