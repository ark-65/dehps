from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from math import comb
from typing import Any

import numpy as np

from dehps.domain.combination import normalize_red_numbers


FROZEN_PROPOSAL_KEY = "auto-ranking_model_disagreement-1bf87b0c0493"
FROZEN_PLAN_KEY = "plan-auto-ranking_model_disagreement-1bf87b0c0493-v1"
FROZEN_PLAN_FINGERPRINT = "ab9c47ce344691fd73767d903dcd181898937b9297fd2d2b9ea61c823432a356"
FROZEN_HYPOTHESIS_KEY = FROZEN_PROPOSAL_KEY
FROZEN_PROPOSAL_FINGERPRINT = "1bf87b0c0493"
FROZEN_ENGINEERING_REQUEST_KEY = "engineering-experiment-tool-ab9c47ce344691fd"
FROZEN_OPERATOR_REQUEST_KEY = "operator-isolated-run-ab9c47ce344691fd"

RANKING_DISAGREEMENT_SCHEMA_VERSION = "ranking-disagreement-round24-v1"
RANKER_VERSION = "ranking-disagreement-rankers-v1"
FEATURE_VERSION = "ranking-disagreement-features-v1"
STRATA_VERSION = "ranking-disagreement-strata-v1"
BASELINE_VERSION = "ranking-disagreement-baselines-v1"
METRICS_VERSION = "ranking-disagreement-metrics-v1"
STATISTICS_VERSION = "ranking-disagreement-statistics-v1"

FROZEN_RANKER_KEYS = ("frequency_based", "structural", "omission_based")
FROZEN_FEATURE_KEYS = (
    "rank_mean",
    "rank_median",
    "rank_min",
    "rank_max",
    "rank_std",
    "rank_range",
    "pairwise_rank_gap",
    "ranker_order_entropy",
    "consensus_band",
    "disagreement_band",
)
STRATA_KEYS = (
    "low_disagreement",
    "medium_disagreement",
    "high_disagreement",
    "extreme_disagreement",
)
BASELINE_KEYS = (
    "budget_matched_random",
    "rank_matched_consensus",
    "current_production_ranker",
)
STAGE_EXPERIMENT_KEYS = {
    "feasibility": "ranking_disagreement_feasibility_v1",
    "historical_search": "ranking_disagreement_historical_search_v1",
    "frozen_validation": "ranking_disagreement_frozen_validation_v1",
    "forward_validation": "ranking_disagreement_forward_validation_v1",
}


JsonObject = dict[str, Any]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=json_default,
    )


def stable_hash(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def array_hash(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(contiguous.dtype).encode("utf-8"))
    digest.update(stable_json(tuple(int(v) for v in contiguous.shape)).encode("utf-8"))
    digest.update(contiguous.tobytes())
    return digest.hexdigest()


def normalize_ranker_key(key: str) -> str:
    aliases = {
        "frequency_based_ranker": "frequency_based",
        "structural_ranker": "structural",
        "omission_based_ranker": "omission_based",
    }
    normalized = aliases.get(key, key)
    if normalized not in FROZEN_RANKER_KEYS:
        raise ValueError(f"ranker is outside the frozen Round 24 list: {key}")
    return normalized


def combination_id(numbers: tuple[int, ...] | list[int]) -> int:
    """1-based lexicographic id matching itertools.combinations(range(1, 34), 6)."""
    nums = normalize_red_numbers(numbers)
    rank = 0
    previous = 0
    total_numbers = 33
    sample_size = 6
    for index, number in enumerate(nums, start=1):
        remaining = sample_size - index
        for skipped in range(previous + 1, number):
            rank += comb(total_numbers - skipped, remaining)
        previous = number
    return rank + 1


@dataclass(frozen=True)
class DrawRecord:
    issue: str
    draw_date: date | None
    red_numbers: tuple[int, ...]

    @property
    def combination_id(self) -> int:
        return combination_id(self.red_numbers)


@dataclass(frozen=True)
class LegalUniverse:
    combination_ids: np.ndarray
    combinations: np.ndarray
    fingerprint: str
    full_lexicographic_universe: bool = True

    @property
    def count(self) -> int:
        return int(self.combination_ids.shape[0])

    def require_contains(self, numbers: tuple[int, ...] | list[int]) -> int:
        combo_id = combination_id(numbers)
        if combo_id < int(self.combination_ids[0]) or combo_id > int(self.combination_ids[-1]):
            raise ValueError(f"target combination is outside the legal universe materialized for this run: {combo_id}")
        if self.combination_ids[combo_id - 1] != combo_id:
            raise ValueError(f"target combination id is not present in legal universe: {combo_id}")
        return combo_id


@dataclass(frozen=True)
class RankerOutput:
    ranker_key: str
    version: str
    config_hash: str
    as_of_issue: str
    history_fingerprint: str
    legal_universe_fingerprint: str
    combination_ids: np.ndarray
    ranks: np.ndarray
    score_fingerprint: str

    @property
    def fingerprint(self) -> str:
        return stable_hash(
            {
                "ranker_key": self.ranker_key,
                "version": self.version,
                "config_hash": self.config_hash,
                "as_of_issue": self.as_of_issue,
                "history_fingerprint": self.history_fingerprint,
                "legal_universe_fingerprint": self.legal_universe_fingerprint,
                "combination_ids": array_hash(self.combination_ids),
                "ranks": array_hash(self.ranks),
            }
        )


@dataclass(frozen=True)
class RankMatrix:
    combination_ids: np.ndarray
    ranker_keys: tuple[str, ...]
    values: np.ndarray
    as_of_issue: str
    history_fingerprint: str
    legal_universe_fingerprint: str
    fingerprint: str


@dataclass(frozen=True)
class FeatureFrame:
    combination_ids: np.ndarray
    numeric: dict[str, np.ndarray]
    categorical: dict[str, np.ndarray]
    as_of_issue: str
    rank_matrix_fingerprint: str
    feature_fingerprint: str
    version: str = FEATURE_VERSION

    @property
    def disagreement_score(self) -> np.ndarray:
        return self.numeric["rank_range"] + self.numeric["rank_std"]


@dataclass(frozen=True)
class StrataThresholds:
    low_max: float
    medium_max: float
    high_max: float
    source_stage: str
    source_issue_count: int
    version: str = STRATA_VERSION
    fingerprint: str = ""

    def finalized(self) -> "StrataThresholds":
        return StrataThresholds(
            low_max=float(self.low_max),
            medium_max=float(self.medium_max),
            high_max=float(self.high_max),
            source_stage=self.source_stage,
            source_issue_count=int(self.source_issue_count),
            version=self.version,
            fingerprint=stable_hash(
                {
                    "version": self.version,
                    "low_max": float(self.low_max),
                    "medium_max": float(self.medium_max),
                    "high_max": float(self.high_max),
                    "source_stage": self.source_stage,
                    "source_issue_count": int(self.source_issue_count),
                }
            ),
        )

    def to_json(self) -> JsonObject:
        finalized = self.finalized() if not self.fingerprint else self
        return {
            "version": finalized.version,
            "low_max": finalized.low_max,
            "medium_max": finalized.medium_max,
            "high_max": finalized.high_max,
            "source_stage": finalized.source_stage,
            "source_issue_count": finalized.source_issue_count,
            "fingerprint": finalized.fingerprint,
        }


@dataclass(frozen=True)
class IssueWindows:
    feasibility_issue: str
    search_issues: tuple[str, ...]
    frozen_issues: tuple[str, ...]
    forward_issues: tuple[str, ...] = field(default_factory=tuple)
    search_issue_count: int = 100
    frozen_issue_count: int = 20
    minimum_training_issues: int = 20
    fingerprint: str = ""

    def finalized(self) -> "IssueWindows":
        payload = {
            "feasibility_issue": self.feasibility_issue,
            "search_issues": self.search_issues,
            "frozen_issues": self.frozen_issues,
            "forward_issues": self.forward_issues,
            "search_issue_count": self.search_issue_count,
            "frozen_issue_count": self.frozen_issue_count,
            "minimum_training_issues": self.minimum_training_issues,
        }
        return IssueWindows(
            feasibility_issue=self.feasibility_issue,
            search_issues=tuple(self.search_issues),
            frozen_issues=tuple(self.frozen_issues),
            forward_issues=tuple(self.forward_issues),
            search_issue_count=int(self.search_issue_count),
            frozen_issue_count=int(self.frozen_issue_count),
            minimum_training_issues=int(self.minimum_training_issues),
            fingerprint=stable_hash(payload),
        )

    def to_json(self) -> JsonObject:
        finalized = self.finalized() if not self.fingerprint else self
        return {
            "feasibility_issue": finalized.feasibility_issue,
            "search_issues": list(finalized.search_issues),
            "frozen_issues": list(finalized.frozen_issues),
            "forward_issues": list(finalized.forward_issues),
            "search_issue_count": finalized.search_issue_count,
            "frozen_issue_count": finalized.frozen_issue_count,
            "minimum_training_issues": finalized.minimum_training_issues,
            "fingerprint": finalized.fingerprint,
            "forward_validation_executed": False,
        }
