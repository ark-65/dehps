"""Frozen definitions preserved from dehps/research_os/information_theory/measurement_system_v2/forward_prequential_confirmatory.py.

Original files remain the legacy compatibility implementation. This release-local
copy has explicit calculation-only imports; scientific bodies are checked against
the originals. No historical digest or source contract is rewritten.
"""
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
from dehps.contracts import canonical_digest
from dehps.input_contracts.candidate_abi import candidate_unrank
from dehps.research_os.models import m4_v2_domain_digest
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_contract import ESTIMATOR_ID, estimate_legal_marginals
from .sampling import UNIVERSE, _sample_lex_ids
from . import history as historical_bounded


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


SHANGHAI = ZoneInfo("Asia/Shanghai")


LOOKS = (20, 40, 60, 90, 120)


MAX_N = 120


MODEL_TICKET_COUNT = 100


BASELINE_TICKET_COUNT = 100


PROPOSAL_POOL_SIZE = 10_000


UNIFORM_Q = 2.0 / 11.0


PRACTICAL_THRESHOLD = 0.05


FROZEN_LONG_RUN_VARIANCE = 0.05302208982040761


CRITICAL_Z = 2.5758293035489


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


def load_source_contract(*, root_dir: Path) -> dict[str, Any]:
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
