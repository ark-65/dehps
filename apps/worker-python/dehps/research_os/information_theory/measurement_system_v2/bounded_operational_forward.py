from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import date, datetime
from datetime import time as day_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentRequestStatus
from dehps.contracts import canonical_digest
from dehps.input_contracts.candidate_abi import candidate_unrank
from dehps.models.frequency_ranker import next_ssq_draw_date
from dehps.prediction.v2.generator import UNIVERSE, _sample_lex_ids
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_contract import (
    ESTIMATOR_ID,
    estimate_legal_marginals,
)
from dehps.research_os.models import m4_v2_domain_digest


class M4V2BoundedOperationalForwardError(ValueError):
    pass


SOURCE_CONTRACT_PATH = (
    "configs/research-os/m4-v2-bounded-operational-forward-source-v1.json"
)
SOURCE_SCHEMA = "dehps-m4-v2-bounded-operational-forward-source-contract.v1"
SOURCE_ARTIFACT_TYPE = "m4_v2_bounded_operational_forward_source_contract"
SOURCE_DOMAIN = "dehps.m4.v2.bounded-operational-forward-source-contract.v1"
SOURCE_SET_DOMAIN = "dehps.m4.v2.bounded-operational-forward-source-set.v1"

GOAL_KEY = "M4_V2_BOUNDED_OPERATIONAL_FORWARD_STUDY"
PREREGISTRATION_TASK_KEY = "m4-v2-bounded-operational-forward-study-preregistration"
PREREGISTRATION_CAPABILITY = "m4_v2_bounded_operational_forward_study_preregistration"
PREREGISTRATION_FACT = f"{PREREGISTRATION_TASK_KEY}:FROZEN"
SOURCE_FACT_PREFIX = "m4-v2-bounded-operational-forward-source:"

REFIT_CAPABILITY = "m4_v2_bounded_operational_forward_refit"
PREDRAW_CAPABILITY = "m4_v2_bounded_operational_forward_predraw"
PREDRAW_REPLAY_CAPABILITY = "m4_v2_bounded_operational_forward_predraw_replay"
SETTLEMENT_CAPABILITY = "m4_v2_bounded_operational_forward_settlement"
SETTLEMENT_REPLAY_CAPABILITY = "m4_v2_bounded_operational_forward_settlement_replay"

PREREGISTRATION_ARTIFACT_TYPE = "M4V2BoundedOperationalForwardPreregistrationArtifact"
PREREGISTRATION_REPLAY_ARTIFACT_TYPE = (
    "M4V2BoundedOperationalForwardPreregistrationReplayArtifact"
)
DATASET_ARTIFACT_TYPE = "M4V2BoundedOperationalForwardDatasetArtifact"
MODEL_ARTIFACT_TYPE = "M4V2BoundedOperationalForwardModelArtifact"
MODEL_CANDIDATE_ARTIFACT_TYPE = "M4V2BoundedOperationalForwardModelCandidateSet"
RANDOM_BASELINE_ARTIFACT_TYPE = "M4V2BoundedOperationalForwardRandomBaselineSet"
CHECKPOINT_ARTIFACT_TYPE = "M4V2BoundedOperationalForwardCheckpointArtifact"
PREDRAW_REPORT_ARTIFACT_TYPE = "M4V2BoundedOperationalForwardPreDrawReport"
PREDRAW_REPLAY_ARTIFACT_TYPE = "M4V2BoundedOperationalForwardPreDrawReplayArtifact"
SETTLEMENT_ARTIFACT_TYPE = "M4V2BoundedOperationalForwardSettlementArtifact"
SETTLEMENT_REPLAY_ARTIFACT_TYPE = (
    "M4V2BoundedOperationalForwardSettlementReplayArtifact"
)
ARTIFACT_DOMAINS = {
    PREREGISTRATION_ARTIFACT_TYPE: (
        "dehps.m4.v2.bounded-operational-forward-preregistration.v1"
    ),
    PREREGISTRATION_REPLAY_ARTIFACT_TYPE: (
        "dehps.m4.v2.bounded-operational-forward-preregistration-replay.v1"
    ),
    DATASET_ARTIFACT_TYPE: "dehps.m4.v2.bounded-operational-forward-dataset.v1",
    MODEL_ARTIFACT_TYPE: "dehps.m4.v2.bounded-operational-forward-model.v1",
    MODEL_CANDIDATE_ARTIFACT_TYPE: (
        "dehps.m4.v2.bounded-operational-forward-model-candidates.v1"
    ),
    RANDOM_BASELINE_ARTIFACT_TYPE: (
        "dehps.m4.v2.bounded-operational-forward-random-baseline.v1"
    ),
    CHECKPOINT_ARTIFACT_TYPE: ("dehps.m4.v2.bounded-operational-forward-checkpoint.v1"),
    PREDRAW_REPORT_ARTIFACT_TYPE: (
        "dehps.m4.v2.bounded-operational-forward-predraw-report.v1"
    ),
    PREDRAW_REPLAY_ARTIFACT_TYPE: (
        "dehps.m4.v2.bounded-operational-forward-predraw-replay.v1"
    ),
    SETTLEMENT_ARTIFACT_TYPE: ("dehps.m4.v2.bounded-operational-forward-settlement.v1"),
    SETTLEMENT_REPLAY_ARTIFACT_TYPE: (
        "dehps.m4.v2.bounded-operational-forward-settlement-replay.v1"
    ),
}

RESEARCH_REQUEST_KEY = (
    "research-m4-v2-bounded-operational-forward-study-preregistration-v1"
)
RESEARCH_REQUEST_ID = 637
RESEARCH_EXECUTION_ID = 521
RESEARCH_APPROVAL_DECISION_ID = 2682
RESEARCH_REQUEST_PAYLOAD_SHA256 = (
    "d6640bd4bc54df30ed20f427c69c53ce92d056bfad1aaafd99cecf9c97f42c19"
)
ENGINEERING_REQUEST_KEY = "engineering-m4-v2-bounded-operational-forward-launch-v1"
ENGINEERING_REQUEST_ID = 638
ENGINEERING_EXECUTION_ID = 522
ENGINEERING_APPROVAL_DECISION_ID = 2687
ENGINEERING_REQUEST_PAYLOAD_SHA256 = (
    "3b1a6043b2952261bc56ec59eece0eb462972d0349722c2eea79e11bf7621e19"
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
TARGET_COUNT = 120
MODEL_TICKET_COUNT = 100
BASELINE_TICKET_COUNT = 100
PROPOSAL_POOL_SIZE = 10_000
UNIFORM_Q = 2.0 / 11.0


def issue_task_keys(issue: str) -> dict[str, str]:
    prefix = f"m4-v2-bounded-operational-forward-{issue}"
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
        "draw_synced": f"m4-v2-bounded-operational-forward:{issue}:DRAW_SYNCED",
        "settlement": f"{keys['settlement']}:SETTLED",
        "settlement_replay": f"{keys['settlement_replay']}:REGISTERED_REPLAY_VERIFIED",
    }


def _canonical_payload_sha256(value: Mapping[str, Any]) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _require_digest(value: object, name: str) -> str:
    digest = str(value or "")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise M4V2BoundedOperationalForwardError(f"{name}_invalid")
    return digest


def _artifact(
    *,
    artifact_type: str,
    domain: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": f"dehps-{artifact_type}.v1",
        "artifact_type": artifact_type,
        "body": deepcopy(dict(body)),
        "parent_digests": [
            _require_digest(item, "parent_digest") for item in parent_digests
        ],
    }
    payload["artifact_digest"] = m4_v2_domain_digest(payload, domain=domain)
    return payload


def validate_artifact(
    value: Mapping[str, Any], *, artifact_type: str, domain: str
) -> dict[str, Any]:
    payload = deepcopy(dict(value))
    expected_schema = f"dehps-{artifact_type}.v1"
    if (
        set(payload)
        != {
            "schema_version",
            "artifact_type",
            "artifact_digest",
            "body",
            "parent_digests",
        }
        or payload.get("schema_version") != expected_schema
        or payload.get("artifact_type") != artifact_type
        or not isinstance(payload.get("body"), Mapping)
        or not isinstance(payload.get("parent_digests"), list)
    ):
        raise M4V2BoundedOperationalForwardError(f"{artifact_type}_shape_changed")
    observed = _require_digest(payload.pop("artifact_digest"), "artifact_digest")
    if m4_v2_domain_digest(payload, domain=domain) != observed:
        raise M4V2BoundedOperationalForwardError(f"{artifact_type}_digest_changed")
    payload["artifact_digest"] = observed
    return payload


def validate_registered_artifact(value: Mapping[str, Any]) -> dict[str, Any]:
    artifact_type = str(value.get("artifact_type") or "")
    domain = ARTIFACT_DOMAINS.get(artifact_type)
    if domain is None:
        raise M4V2BoundedOperationalForwardError(
            f"bounded_forward_registered_type_invalid:{artifact_type}"
        )
    return validate_artifact(value, artifact_type=artifact_type, domain=domain)


def load_source_contract(*, root_dir: Path) -> dict[str, Any]:
    root = root_dir.resolve()
    path = (root / SOURCE_CONTRACT_PATH).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise M4V2BoundedOperationalForwardError("bounded_forward_source_missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise M4V2BoundedOperationalForwardError(
            "bounded_forward_source_invalid"
        ) from exc
    required = {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "contract_key",
        "frozen_contract",
        "governance_bindings",
        "source_entries",
        "source_set_digest",
    }
    if (
        not isinstance(payload, dict)
        or set(payload) != required
        or payload.get("schema_version") != SOURCE_SCHEMA
        or payload.get("artifact_type") != SOURCE_ARTIFACT_TYPE
        or payload.get("contract_key") != GOAL_KEY
        or not isinstance(payload.get("frozen_contract"), Mapping)
        or not isinstance(payload.get("governance_bindings"), Mapping)
        or not isinstance(payload.get("source_entries"), list)
    ):
        raise M4V2BoundedOperationalForwardError("bounded_forward_source_shape_changed")
    frozen = payload["frozen_contract"]
    candidates = frozen.get("candidate_generation", {})
    cohort = frozen.get("cohort", {})
    immutable = frozen.get("immutable_scientific_state", {})
    checkpoint = frozen.get("checkpoint", {})
    if (
        frozen.get("branch") != "MARGINAL_STATIC"
        or frozen.get("estimator_identity") != ESTIMATOR_ID
        or frozen.get("feature_identity")
        != "NO_FEATURES_33_EXPANDING_RED_NUMBER_EVENT_COUNTS_ONLY"
        or cohort.get("valid_issue_target") != TARGET_COUNT
        or cohort.get("issue_20_review") != "integrity_only_no_aggregate_outcome_read"
        or cohort.get("issue_60_review") != "integrity_only_no_aggregate_outcome_read"
        or cohort.get("issue_120_review") != "sole_outcome_bearing_operational_decision"
        or candidates.get("model_ticket_count") != MODEL_TICKET_COUNT
        or candidates.get("random_baseline_ticket_count") != BASELINE_TICKET_COUNT
        or candidates.get("proposal_pool_size") != PROPOSAL_POOL_SIZE
        or immutable.get("data_reuse_policy") != "STAGED_INDEPENDENT_SAMPLES"
        or immutable.get("formal_p4") != "DEPENDENCY_WAIT"
        or immutable.get("pass_to_p4") != "NOT_EMITTED"
        or immutable.get("p5") != "NOT_AUTHORIZED"
        or immutable.get("promotion") != "CLOSED"
        or checkpoint.get("pre_draw_deadline")
        != "17:00:00 Asia/Shanghai on the official Tue/Thu/Sun draw date"
        or checkpoint.get("official_draw_time") != "21:15:00 Asia/Shanghai"
    ):
        raise M4V2BoundedOperationalForwardError("bounded_forward_contract_changed")
    entries: list[dict[str, str]] = []
    for item in payload["source_entries"]:
        if not isinstance(item, Mapping) or set(item) != {"path", "sha256"}:
            raise M4V2BoundedOperationalForwardError(
                "bounded_forward_source_entry_changed"
            )
        relative = str(item["path"])
        absolute = (root / relative).resolve()
        if (
            not absolute.is_relative_to(root)
            or not absolute.is_file()
            or hashlib.sha256(absolute.read_bytes()).hexdigest() != item["sha256"]
        ):
            raise M4V2BoundedOperationalForwardError(
                f"bounded_forward_source_bytes_changed:{relative}"
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
        raise M4V2BoundedOperationalForwardError(
            "bounded_forward_source_identity_changed"
        )
    return deepcopy(payload)


def verify_governance(repository: AgentRequestRepository) -> None:
    specs = (
        (
            RESEARCH_REQUEST_KEY,
            RESEARCH_REQUEST_ID,
            RESEARCH_EXECUTION_ID,
            RESEARCH_APPROVAL_DECISION_ID,
            RESEARCH_REQUEST_PAYLOAD_SHA256,
            "APPROVE_RESULT_BLIND_BOUNDED_OPERATIONAL_FORWARD_COHORT_A",
        ),
        (
            ENGINEERING_REQUEST_KEY,
            ENGINEERING_REQUEST_ID,
            ENGINEERING_EXECUTION_ID,
            ENGINEERING_APPROVAL_DECISION_ID,
            ENGINEERING_REQUEST_PAYLOAD_SHA256,
            "APPROVE_EXACT_BOUNDED_OPERATIONAL_FORWARD_LAUNCH_IMPLEMENTATION",
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
        observed_outcome = None
        if len(approvals) == 1:
            observed_outcome = approvals[0].reason.get("decision") or approvals[
                0
            ].reason.get("outcome")
        if (
            request.id != request_id
            or request.status
            not in {AgentRequestStatus.EXECUTING, AgentRequestStatus.COMPLETED}
            or _canonical_payload_sha256(request.payload) != payload_sha
            or len(executions) != 1
            or executions[0].id != execution_id
            or len(approvals) != 1
            or approvals[0].id != approval_id
            or observed_outcome != outcome
        ):
            raise M4V2BoundedOperationalForwardError(
                "bounded_forward_governance_changed"
            )


def build_preregistration_artifacts(
    *, source_contract: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_digest = _require_digest(
        source_contract.get("artifact_digest"), "source_digest"
    )
    frozen = deepcopy(dict(source_contract["frozen_contract"]))
    preregistration = _artifact(
        artifact_type=PREREGISTRATION_ARTIFACT_TYPE,
        domain="dehps.m4.v2.bounded-operational-forward-preregistration.v1",
        body={
            "status": "FROZEN",
            "diagnostic_only": False,
            "shadow_only": True,
            "confirmatory_p4": False,
            "eligible_for_p5": False,
            "eligible_for_promotion": False,
            "forward_results_read": False,
            "contract": frozen,
            "next_consumer": "initial_marginal_static_refit",
        },
        parent_digests=(source_digest,),
    )
    replay = _artifact(
        artifact_type=PREREGISTRATION_REPLAY_ARTIFACT_TYPE,
        domain="dehps.m4.v2.bounded-operational-forward-preregistration-replay.v1",
        body={
            "status": "REPLAY_VERIFIED",
            "registered_replay_status": "REGISTERED_REPLAY_VERIFIED",
            "preregistration_digest": preregistration["artifact_digest"],
            "same_registered_content": True,
            "workload_rerun": False,
            "forward_results_read": False,
        },
        parent_digests=(preregistration["artifact_digest"], source_digest),
    )
    return preregistration, replay


def _normalize_history_rows(
    history_rows: Sequence[object], *, before_issue: str
) -> tuple[tuple[str, str, tuple[int, ...]], ...]:
    normalized: list[tuple[str, str, tuple[int, ...]]] = []
    for row in history_rows:
        if not isinstance(row, Sequence) or len(row) != 3:
            raise M4V2BoundedOperationalForwardError("history_row_invalid")
        issue = str(row[0])
        draw_date = row[1]
        numbers = tuple(int(item) for item in row[2])
        if issue >= before_issue:
            continue
        if (
            not isinstance(draw_date, date)
            or len(numbers) != 6
            or tuple(sorted(numbers)) != numbers
            or len(set(numbers)) != 6
            or numbers[0] < 1
            or numbers[-1] > 33
        ):
            raise M4V2BoundedOperationalForwardError("history_boundary_invalid")
        normalized.append((issue, draw_date.isoformat(), numbers))
    if len(normalized) < 900 or tuple(item[0] for item in normalized) != tuple(
        sorted(item[0] for item in normalized)
    ):
        raise M4V2BoundedOperationalForwardError("training_history_invalid")
    return tuple(normalized)


def fit_model_artifacts(
    *,
    source_contract: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    history_rows: Sequence[object],
    target_issue: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    prereg = validate_artifact(
        preregistration,
        artifact_type=PREREGISTRATION_ARTIFACT_TYPE,
        domain="dehps.m4.v2.bounded-operational-forward-preregistration.v1",
    )
    rows = _normalize_history_rows(history_rows, before_issue=target_issue)
    counts = [0] * 33
    for _, _, numbers in rows:
        for number in numbers:
            counts[number - 1] += 1
    probabilities = estimate_legal_marginals(counts, training_issue_count=len(rows))
    source_digest = _require_digest(
        source_contract.get("artifact_digest"), "source_digest"
    )
    dataset_body = {
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
    }
    dataset = _artifact(
        artifact_type=DATASET_ARTIFACT_TYPE,
        domain="dehps.m4.v2.bounded-operational-forward-dataset.v1",
        body=dataset_body,
        parent_digests=(prereg["artifact_digest"], source_digest),
    )
    estimator_digest = canonical_digest(
        {"identity": ESTIMATOR_ID, "formula": "q_i=(c_i+2/11)/(n+1)"},
        domain="dehps.m4.v2.bounded-operational-forward-estimator.v1",
    )
    feature_digest = canonical_digest(
        {"identity": "NO_FEATURES_33_EXPANDING_RED_NUMBER_EVENT_COUNTS_ONLY"},
        domain="dehps.m4.v2.bounded-operational-forward-features.v1",
    )
    parameter_digest = canonical_digest(
        {
            "alpha": 1,
            "per_number_prior": "2/11",
            "minimum_training_issues": 900,
            "clipping": "forbidden",
            "renormalization": "forbidden",
            "hyperparameter_search": "none",
        },
        domain="dehps.m4.v2.bounded-operational-forward-parameters.v1",
    )
    baseline_digest = canonical_digest(
        {"identity": "LEGAL_UNIFORM_NUMBER_EVENT_BASELINE", "q": "2/11"},
        domain="dehps.m4.v2.bounded-operational-forward-baseline.v1",
    )
    model = _artifact(
        artifact_type=MODEL_ARTIFACT_TYPE,
        domain="dehps.m4.v2.bounded-operational-forward-model.v1",
        body={
            "status": "TRAINED",
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
            "estimator_digest": estimator_digest,
            "feature_digest": feature_digest,
            "parameter_digest": parameter_digest,
            "baseline_digest": baseline_digest,
            "source_digest": source_digest,
            "model_source_file_sha256": source_contract["frozen_contract"][
                "model_source_file_sha256"
            ],
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
    now = (moment or datetime.now(SHANGHAI)).astimezone(SHANGHAI)
    normalized = _normalize_history_rows(history_rows, before_issue="9999999")
    latest_issue, latest_date_value, _ = normalized[-1]
    candidate_date = next_ssq_draw_date(date.fromisoformat(latest_date_value))
    candidate_issue = int(latest_issue) + 1
    if candidate_date.year > int(latest_issue[:4]):
        candidate_issue = int(f"{candidate_date.year}001")
    while True:
        deadline = datetime.combine(candidate_date, day_time(17, 0), tzinfo=SHANGHAI)
        official = datetime.combine(candidate_date, day_time(21, 15), tzinfo=SHANGHAI)
        if now <= deadline:
            return str(candidate_issue), candidate_date, deadline, official
        candidate_date = next_ssq_draw_date(candidate_date)
        candidate_issue += 1
        if candidate_date.year > int(str(candidate_issue)[:4]):
            candidate_issue = int(f"{candidate_date.year}001")


def _arm_seed(
    *, preregistration_digest: str, target_issue: str, arm: str, model_digest: str = ""
) -> str:
    return canonical_digest(
        {
            "preregistration_digest": preregistration_digest,
            "target_issue": target_issue,
            "arm": arm,
            "model_digest": model_digest,
        },
        domain="dehps.m4.v2.bounded-operational-forward-arm-seed.v1",
    )


def _blue_numbers(*, preregistration_digest: str, target_issue: str) -> list[int]:
    values: list[int] = []
    for rank in range(1, 101):
        raw = hashlib.sha256(
            b"dehps.m4.v2.shared-blue-by-rank.v1\x00"
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
    source_contract: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    model: Mapping[str, Any],
    target_draw_date: date,
    sealed_at: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    prereg = validate_artifact(
        preregistration,
        artifact_type=PREREGISTRATION_ARTIFACT_TYPE,
        domain="dehps.m4.v2.bounded-operational-forward-preregistration.v1",
    )
    verified_model = validate_artifact(
        model,
        artifact_type=MODEL_ARTIFACT_TYPE,
        domain="dehps.m4.v2.bounded-operational-forward-model.v1",
    )
    body = verified_model["body"]
    target_issue = str(body["target_issue"])
    moment = (sealed_at or datetime.now(SHANGHAI)).astimezone(SHANGHAI)
    deadline = datetime.combine(target_draw_date, day_time(17, 0), tzinfo=SHANGHAI)
    official = datetime.combine(target_draw_date, day_time(21, 15), tzinfo=SHANGHAI)
    if moment > deadline or moment >= official:
        raise M4V2BoundedOperationalForwardError("checkpoint_deadline_missed")
    probabilities = [float(item) for item in body["probabilities_q_1_to_33"]]
    if len(probabilities) != 33 or not math.isclose(
        sum(probabilities), 6.0, abs_tol=1e-12
    ):
        raise M4V2BoundedOperationalForwardError("model_probability_vector_invalid")
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
        domain="dehps.m4.v2.bounded-operational-forward-blue-strategy.v1",
    )
    model_candidates = _artifact(
        artifact_type=MODEL_CANDIDATE_ARTIFACT_TYPE,
        domain="dehps.m4.v2.bounded-operational-forward-model-candidates.v1",
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
    random_baseline = _artifact(
        artifact_type=RANDOM_BASELINE_ARTIFACT_TYPE,
        domain="dehps.m4.v2.bounded-operational-forward-random-baseline.v1",
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
        domain="dehps.m4.v2.bounded-operational-forward-checkpoint.v1",
        body={
            "status": "SEALED_BEFORE_DRAW",
            "target_issue": target_issue,
            "training_end_issue": body["training_end_issue"],
            "dataset_digest": body["dataset_digest"],
            "model_digest": model_digest,
            "source_digest": body["source_digest"],
            "feature_digest": body["feature_digest"],
            "parameter_digest": body["parameter_digest"],
            "baseline_digest": body["baseline_digest"],
            "model_candidate_digest": model_candidates["artifact_digest"],
            "random_baseline_digest": random_baseline["artifact_digest"],
            "blue_strategy_digest": blue_strategy_digest,
            "same_blue_strategy": True,
            "model_ticket_count": MODEL_TICKET_COUNT,
            "random_baseline_ticket_count": BASELINE_TICKET_COUNT,
            "sealed_at": moment.isoformat(),
            "checkpoint_deadline": deadline.isoformat(),
            "official_draw_time": official.isoformat(),
            "configuration_drift": False,
            "production_betting_authorized": False,
        },
        parent_digests=(
            model_digest,
            model_candidates["artifact_digest"],
            random_baseline["artifact_digest"],
            prereg_digest,
        ),
    )
    markdown = "\n".join(
        [
            f"# M4-v2 bounded operational forward pre-draw report: {target_issue}",
            "",
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
            "This is a shadow-only operational output. It is not P3 PASS, PASS_TO_P4, formal P4, proof of predictive advantage, Promotion, or betting authorization.",
        ]
    )
    report = _artifact(
        artifact_type=PREDRAW_REPORT_ARTIFACT_TYPE,
        domain="dehps.m4.v2.bounded-operational-forward-predraw-report.v1",
        body={
            "status": "PUBLISHED",
            "target_issue": target_issue,
            "checkpoint_digest": checkpoint["artifact_digest"],
            "model_candidate_digest": model_candidates["artifact_digest"],
            "random_baseline_digest": random_baseline["artifact_digest"],
            "markdown": markdown,
        },
        parent_digests=(checkpoint["artifact_digest"],),
    )
    return model_candidates, random_baseline, checkpoint, report


def build_predraw_replay_artifact(
    *,
    model_candidates: Mapping[str, Any],
    random_baseline: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
    report: Mapping[str, Any],
) -> dict[str, Any]:
    values = (
        (model_candidates, MODEL_CANDIDATE_ARTIFACT_TYPE, "model-candidates"),
        (random_baseline, RANDOM_BASELINE_ARTIFACT_TYPE, "random-baseline"),
        (checkpoint, CHECKPOINT_ARTIFACT_TYPE, "checkpoint"),
        (report, PREDRAW_REPORT_ARTIFACT_TYPE, "predraw-report"),
    )
    digests = []
    for value, artifact_type, suffix in values:
        validated = validate_artifact(
            value,
            artifact_type=artifact_type,
            domain=f"dehps.m4.v2.bounded-operational-forward-{suffix}.v1",
        )
        digests.append(validated["artifact_digest"])
    checkpoint_body = checkpoint["body"]
    if (
        model_candidates["body"].get("candidate_count") != MODEL_TICKET_COUNT
        or random_baseline["body"].get("candidate_count") != BASELINE_TICKET_COUNT
        or checkpoint_body.get("configuration_drift") is not False
        or checkpoint_body.get("same_blue_strategy") is not True
    ):
        raise M4V2BoundedOperationalForwardError("predraw_replay_invariant_changed")
    return _artifact(
        artifact_type=PREDRAW_REPLAY_ARTIFACT_TYPE,
        domain="dehps.m4.v2.bounded-operational-forward-predraw-replay.v1",
        body={
            "status": "REPLAY_VERIFIED",
            "registered_replay_status": "REGISTERED_REPLAY_VERIFIED",
            "target_issue": checkpoint_body["target_issue"],
            "model_ticket_count": MODEL_TICKET_COUNT,
            "random_baseline_ticket_count": BASELINE_TICKET_COUNT,
            "same_blue_strategy": True,
            "configuration_drift": False,
            "same_registered_content": True,
            "workload_rerun": False,
        },
        parent_digests=tuple(digests),
    )


def _issue_log_score(
    probabilities: Sequence[float], actual_red_numbers: Sequence[int]
) -> float:
    return _ticket_score(tuple(int(item) for item in actual_red_numbers), probabilities)


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
) -> dict[str, Any]:
    model_body = model["body"]
    checkpoint_body = checkpoint["body"]
    actual = tuple(sorted(int(item) for item in actual_red_numbers))
    if (
        len(actual) != 6
        or len(set(actual)) != 6
        or actual[0] < 1
        or actual[-1] > 33
        or not 1 <= int(actual_blue_number) <= 16
        or checkpoint_body.get("status") != "SEALED_BEFORE_DRAW"
        or datetime.fromisoformat(checkpoint_body["sealed_at"])
        >= datetime.fromisoformat(checkpoint_body["official_draw_time"])
    ):
        raise M4V2BoundedOperationalForwardError("settlement_boundary_invalid")
    probabilities = [float(item) for item in model_body["probabilities_q_1_to_33"]]
    model_score = _issue_log_score(probabilities, actual)
    baseline_score = _issue_log_score([UNIFORM_Q] * 33, actual)

    def support(value: Mapping[str, Any]) -> dict[str, Any]:
        tickets = value["body"]["tickets"]
        red_hits = [len(set(item["red_numbers"]) & set(actual)) for item in tickets]
        blue_hits = [item["blue_number"] == int(actual_blue_number) for item in tickets]
        return {
            "max_red_hits": max(red_hits),
            "red_hit_histogram": {str(k): red_hits.count(k) for k in range(7)},
            "blue_hit_count": sum(blue_hits),
            "red6_blue_hit_count": sum(
                red == 6 and blue for red, blue in zip(red_hits, blue_hits, strict=True)
            ),
        }

    return _artifact(
        artifact_type=SETTLEMENT_ARTIFACT_TYPE,
        domain="dehps.m4.v2.bounded-operational-forward-settlement.v1",
        body={
            "status": "SETTLED",
            "target_issue": checkpoint_body["target_issue"],
            "actual_red_numbers": list(actual),
            "actual_blue_number": int(actual_blue_number),
            "durable_event_key": durable_event_key,
            "history_fingerprint": history_fingerprint,
            "model_probability_log2_score": model_score,
            "legal_uniform_log2_score": baseline_score,
            "primary_endpoint_bits_per_issue": model_score - baseline_score,
            "model_ticket_support": support(model_candidates),
            "random_baseline_ticket_support": support(random_baseline),
            "cohort_increment": 1,
            "aggregate_outcome_exposed": False,
            "configuration_drift": False,
            "next_consumer": "automatic_next_issue_refit",
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
    settled = validate_artifact(
        settlement,
        artifact_type=SETTLEMENT_ARTIFACT_TYPE,
        domain="dehps.m4.v2.bounded-operational-forward-settlement.v1",
    )
    check = validate_artifact(
        checkpoint,
        artifact_type=CHECKPOINT_ARTIFACT_TYPE,
        domain="dehps.m4.v2.bounded-operational-forward-checkpoint.v1",
    )
    if settled["body"]["target_issue"] != check["body"]["target_issue"]:
        raise M4V2BoundedOperationalForwardError("settlement_replay_issue_changed")
    return _artifact(
        artifact_type=SETTLEMENT_REPLAY_ARTIFACT_TYPE,
        domain="dehps.m4.v2.bounded-operational-forward-settlement-replay.v1",
        body={
            "status": "REPLAY_VERIFIED",
            "registered_replay_status": "REGISTERED_REPLAY_VERIFIED",
            "target_issue": settled["body"]["target_issue"],
            "cohort_increment": 1,
            "aggregate_outcome_exposed": False,
            "configuration_drift": False,
            "same_registered_content": True,
            "workload_rerun": False,
        },
        parent_digests=(settled["artifact_digest"], check["artifact_digest"]),
    )


__all__ = [name for name in globals() if name.isupper()] + [
    "M4V2BoundedOperationalForwardError",
    "build_predraw_replay_artifact",
    "build_preregistration_artifacts",
    "build_settlement_artifact",
    "build_settlement_replay_artifact",
    "fit_model_artifacts",
    "generate_predraw_artifacts",
    "issue_facts",
    "issue_task_keys",
    "load_source_contract",
    "target_for_now",
    "validate_artifact",
    "validate_registered_artifact",
    "verify_governance",
]
