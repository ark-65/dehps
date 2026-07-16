from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class RankingContract(str, Enum):
    LEGACY_SCORE_PARTITION = "legacy_score_partition"
    STRICT_V1 = "strict_v1"


LEGACY_RANKING_CONTRACT = RankingContract.LEGACY_SCORE_PARTITION.value
STRICT_RANKING_CONTRACT = RankingContract.STRICT_V1.value

RANKING_COMPARISON_EXACT = "exact"
RANKING_CONTRACT_DIFFERENCE = "ranking-contract difference"
SCORE_REGRESSION = "score regression"
CANDIDATE_IDENTITY_REGRESSION = "candidate identity regression"


def normalize_ranking_contract(value: object) -> str:
    """Resolve one stored contract without mutating historical evidence.

    Historical rows predate the provenance column, so null and blank values have
    one fixed interpretation. Unknown non-empty values fail closed.
    """

    if value is None or not str(value).strip():
        return LEGACY_RANKING_CONTRACT
    if isinstance(value, RankingContract):
        return value.value
    normalized = str(value).strip()
    try:
        return RankingContract(normalized).value
    except ValueError as exc:
        raise ValueError(f"unknown ranking contract: {normalized}") from exc


def require_explicit_ranking_contract(value: object) -> str:
    if value is None or not str(value).strip():
        raise ValueError("ranking_contract must be explicitly provided for a new prediction run")
    return normalize_ranking_contract(value)


def with_effective_ranking_contract(
    row: Mapping[str, Any],
    *,
    stored_field: str = "ranking_contract",
    output_field: str | None = None,
) -> dict[str, Any]:
    normalized = dict(row)
    normalized[output_field or stored_field] = normalize_ranking_contract(row.get(stored_field))
    return normalized


def production_prediction_fingerprint(
    metadata: Mapping[str, Any],
    *,
    ranking_contract: object,
) -> str:
    """Hash the evidence contract for a newly created production prediction.

    This fingerprint is additive. Historical run keys and config hashes are never
    recomputed or backfilled.
    """

    contract = require_explicit_ranking_contract(ranking_contract)
    prediction_metadata = metadata.get("prediction_metadata")
    prediction_metadata = prediction_metadata if isinstance(prediction_metadata, Mapping) else {}
    config = metadata.get("config")
    config = config if isinstance(config, Mapping) else {}
    payload = {
        "protocol": "forward-prediction-fingerprint-v1",
        "history_snapshot": {
            "as_of_issue": str(metadata.get("as_of_issue") or "not_recorded"),
            "history_fingerprint": str(metadata.get("history_fingerprint") or "not_recorded"),
            "snapshot_key": str(metadata.get("snapshot_key") or "not_recorded"),
        },
        "model_config": {
            "config_hash": str(metadata.get("config_hash") or "not_recorded"),
            "config": dict(config),
        },
        "candidate_algorithm": str(
            prediction_metadata.get("candidate_algorithm_version")
            or prediction_metadata.get("protocol")
            or metadata.get("candidate_algorithm_version")
            or "not_recorded"
        ),
        "scoring_contract": str(
            prediction_metadata.get("scoring_contract")
            or metadata.get("scoring_contract")
            or "not_recorded"
        ),
        "ranking_contract": contract,
        "code_commit": str(metadata.get("git_commit") or "not_recorded"),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def classify_ranking_comparison(
    *,
    left_contract: object,
    right_contract: object,
    topk_id_mismatch_count: int,
    topk_score_mismatch_count: int,
) -> str:
    """Keep tie-boundary identity changes separate from score regressions."""

    if int(topk_score_mismatch_count) > 0:
        return SCORE_REGRESSION
    if int(topk_id_mismatch_count) > 0:
        if normalize_ranking_contract(left_contract) != normalize_ranking_contract(right_contract):
            return RANKING_CONTRACT_DIFFERENCE
        return CANDIDATE_IDENTITY_REGRESSION
    return RANKING_COMPARISON_EXACT


@dataclass(frozen=True)
class ShadowComparisonReport:
    target_issue: str
    official_backend: str
    shadow_backend: str
    official_ranking_contract: str
    shadow_ranking_contract: str
    candidate_store_version: str
    config_fingerprint: str
    target_score_diff: float
    rank_diff: int
    topk_id_mismatch_count: int
    topk_score_mismatch_count: int
    red5_mismatch_count: int
    evaluation_mismatch_count: int
    restart_recovery_result: str
    watchdog_result: str

    def as_dict(self) -> dict[str, Any]:
        official_contract = normalize_ranking_contract(self.official_ranking_contract)
        shadow_contract = normalize_ranking_contract(self.shadow_ranking_contract)
        return {
            "protocol": "scoring-kernel-shadow-comparison-v1",
            "target_issue": self.target_issue,
            "official_backend": self.official_backend,
            "shadow_backend": self.shadow_backend,
            "official_ranking_contract": official_contract,
            "shadow_ranking_contract": shadow_contract,
            "candidate_store_version": self.candidate_store_version,
            "config_fingerprint": self.config_fingerprint,
            "target_score_diff": float(self.target_score_diff),
            "rank_diff": int(self.rank_diff),
            "topk_id_mismatch_count": int(self.topk_id_mismatch_count),
            "topk_score_mismatch_count": int(self.topk_score_mismatch_count),
            "red5_mismatch_count": int(self.red5_mismatch_count),
            "evaluation_mismatch_count": int(self.evaluation_mismatch_count),
            "restart_recovery_result": self.restart_recovery_result,
            "watchdog_result": self.watchdog_result,
            "difference_classification": classify_ranking_comparison(
                left_contract=official_contract,
                right_contract=shadow_contract,
                topk_id_mismatch_count=self.topk_id_mismatch_count,
                topk_score_mismatch_count=self.topk_score_mismatch_count,
            ),
        }
