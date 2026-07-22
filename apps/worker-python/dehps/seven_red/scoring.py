from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from math import isfinite
from typing import Any

import numpy as np

from dehps.contracts import ContractRef, canonical_digest
from dehps.feature_runtime.compiler import feature_array_digest
from dehps.input_contracts.candidate_abi import candidate_unrank
from dehps.scoring_kernel.contracts import SCORE_ROUND_DIGITS, WeightMatrix
from dehps.scoring_kernel.full_score_artifact import (
    FULL_SCORE_GRID_ARTIFACT_VERSION,
    FullScoreGridArtifactV1,
    FullScoreGridArtifactVerifierV1,
)
from dehps.seven_red.domain import (
    LINE_KEY,
    RESEARCH_ONLY,
    SEVEN_RED_DOMAIN_CONTRACT_V1,
    SIX_RED_UNIVERSE,
    SevenRedCandidate,
    SixRedCombination,
)
from dehps.seven_red.raw_top10 import (
    RAW_TOP10_RANKING_CONTRACT,
    SEVEN_RED_RAW_TOP10_CONTRACT_V1,
    PreScoredSevenRedCandidateList,
    ScoredSevenRedCandidate,
)
from dehps.unified_runtime import VerifiedRuntimePackage


SCORE_TICK_SCALE = 10**SCORE_ROUND_DIGITS
SIX_RED_FULL_SCORE_VECTOR_VERSION = "six_red_full_score_vector.v1"
SEVEN_RED_SCORE_POOL_CONFIG_VERSION = "seven_red_score_pool_config.v1"
SEVEN_RED_SCORE_POOL_SNAPSHOT_VERSION = "seven_red_score_pool_snapshot.v1"
SEVEN_RED_SCORE_POOL_COMPILER_CONTRACT = (
    "seven_red_score_pool.top_m_superset_exact_constituent_mean.v1"
)
SEVEN_RED_SCORE_SOURCE_MODEL = "six_red_full_score_constituent_mean.v1"

SEVEN_RED_SCORE_POOL_NORMATIVE_DEFINITION = {
    "contract": "seven-red-score-pool.v1.0.0",
    "line_key": LINE_KEY,
    "research_only": RESEARCH_ONLY,
    "dependencies": {
        "seven_red_domain": SEVEN_RED_DOMAIN_CONTRACT_V1.normative_identity(),
        "seven_red_raw_top10": SEVEN_RED_RAW_TOP10_CONTRACT_V1.normative_identity(),
        "full_score_grid": FULL_SCORE_GRID_ARTIFACT_VERSION,
    },
    "six_red_score_vector": {
        "cardinality": SIX_RED_UNIVERSE.cardinality,
        "source": "one_verified_full_score_grid_configuration_column",
        "representation": "read_only_int64_ticks",
        "tick_scale": SCORE_TICK_SCALE,
        "round_digits": SCORE_ROUND_DIGITS,
        "identity": "source_artifact_runtime_config_and_tick_digest",
    },
    "configuration": {
        "seed_top_n": "explicit_positive_integer_M_without_default",
        "pool_top_n": "explicit_integer_P_at_least_10_without_default",
    },
    "generation": {
        "seed_order": "six_red_score_tick_desc_then_lex_id_asc",
        "supersets_per_seed": 27,
        "candidate_rule": "add_each_missing_red_number_in_[1,33]",
        "deduplication": "canonical_seven_red_lex_id",
    },
    "scoring": {
        "constituents": "all_seven_six_red_subsets",
        "aggregate": "exact_arithmetic_mean_of_seven_int64_score_ticks",
        "ranking_tick": "nearest_integer_tick_to_exact_mean",
        "ranking": "ranking_tick_desc_then_seven_red_lex_id_asc",
        "float_ranking": "forbidden",
        "output": "existing_PreScoredSevenRedCandidateList",
    },
    "chronology": {
        "target_issue": "explicit_seven_digit_issue",
        "source_history_latest_issue": "strictly_before_target_issue",
        "target_outcome": "forbidden",
    },
    "non_goals": [
        "no_default_or_recommended_M_or_P",
        "no_alternative_aggregator",
        "no_walk_forward_or_statistical_claim",
        "no_randomness",
        "no_target_outcome_input",
        "no_production_topk_integration",
    ],
}

SEVEN_RED_SCORE_POOL_GOLDEN_SUITE = {
    "suite": "seven_red_score_pool_golden.v1",
    "arithmetic": {
        "constituent_tick_sum": 10,
        "exact_mean_tick_fraction": "10/7",
        "expected_ranking_tick": 1,
        "negative_constituent_tick_sum": -10,
        "negative_exact_mean_tick_fraction": "-10/7",
        "expected_negative_ranking_tick": -1,
    },
    "supersets_per_seed": 27,
    "synthetic_replay": {
        "score_ticks": "all_zero_int64_over_full_six_red_universe",
        "source_digest_a": "a" * 64,
        "source_digest_b": "b" * 64,
        "source_code_commit": "c" * 40,
        "source_history_latest_issue": "2026001",
        "source_config_index": 0,
        "source_config_count": 1,
        "target_issue": "2026002",
        "seed_top_n": 2,
        "pool_top_n": 10,
        "expected_vector_digest": (
            "3e7c397c6c9cdfbfe2c093e57bbf24a043f421ed8d0d75ce2db31c2ae7aaf29f"
        ),
        "expected_configuration_digest": (
            "7052f65b9f42fb8f8cc5e989e773f085be0d4977661f5cde2e19748fef4c90da"
        ),
        "expected_candidate_pool_digest": (
            "dff8be9ae00300481e411ac02bddfc96199f7feee1622dddfd8f448179f0aee1"
        ),
        "expected_snapshot_digest": (
            "83aef5541caf520f80e97e3ad681242a9e9f7df76f1e694b74c3c194c6ccb0c5"
        ),
    },
    "stochastic": False,
}

SEVEN_RED_SCORE_POOL_CONTRACT_V1 = ContractRef.from_definition(
    family="seven-red-score-pool",
    semantic_version="1.0.0",
    schema_version="dehps.seven-red-score-pool.schema.v1",
    normative_definition=SEVEN_RED_SCORE_POOL_NORMATIVE_DEFINITION,
    golden_suite=SEVEN_RED_SCORE_POOL_GOLDEN_SUITE,
)


class SevenRedScorePoolViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


def _reject(code: str, message: str, **context: Any) -> None:
    raise SevenRedScorePoolViolation(code, message, **context)


def _require_digest(value: object, *, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _reject(
            "seven_red_score_pool_digest_invalid",
            f"{field_name} must be a lowercase sha256 digest",
            field=field_name,
        )
    return value


def _require_issue(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or len(value) != 7 or not value.isascii() or not value.isdigit():
        _reject(
            "seven_red_score_pool_issue_invalid",
            f"{field_name} must be a seven-digit issue string",
            field=field_name,
        )
    return value


def _score_tick_digest(values: np.ndarray) -> str:
    return feature_array_digest(values, domain="dehps.six-red.full-score-ticks.v1")


def _exact_mean_ranking_tick(total_tick: int) -> int:
    quotient, remainder = divmod(total_tick, 7)
    return quotient + int(2 * remainder > 7)


@dataclass(frozen=True)
class SixRedFullScoreVector:
    score_ticks: np.ndarray
    source_full_score_artifact_digest: str
    source_full_score_payload_digest: str
    source_full_score_scores_digest: str
    source_runtime_envelope_digest: str
    source_candidate_package_digest: str
    source_history_snapshot_digest: str
    source_history_latest_issue: str
    source_window_artifact_digest: str
    source_window_spec_digest: str
    source_weights_digest: str
    source_config_index: int
    source_config_count: int
    source_code_commit: str
    score_tick_digest: str = field(init=False)
    vector_digest: str = field(init=False)

    def __post_init__(self) -> None:
        ticks = self.score_ticks
        if (
            not isinstance(ticks, np.ndarray)
            or ticks.dtype != np.int64
            or ticks.shape != (SIX_RED_UNIVERSE.cardinality,)
            or not ticks.flags.c_contiguous
            or ticks.dtype.hasobject
        ):
            _reject(
                "six_red_score_vector_buffer_invalid",
                "score ticks must be a C-contiguous int64 vector over the full six-red universe",
                expected_count=SIX_RED_UNIVERSE.cardinality,
            )
        if ticks.flags.writeable:
            _reject(
                "six_red_score_vector_writable",
                "score tick vectors must be read-only",
            )
        for field_name in (
            "source_full_score_artifact_digest",
            "source_full_score_payload_digest",
            "source_full_score_scores_digest",
            "source_runtime_envelope_digest",
            "source_candidate_package_digest",
            "source_history_snapshot_digest",
            "source_window_artifact_digest",
            "source_window_spec_digest",
            "source_weights_digest",
        ):
            _require_digest(getattr(self, field_name), field_name=field_name)
        _require_issue(self.source_history_latest_issue, field_name="source_history_latest_issue")
        if (
            not isinstance(self.source_config_index, int)
            or isinstance(self.source_config_index, bool)
            or not isinstance(self.source_config_count, int)
            or isinstance(self.source_config_count, bool)
            or self.source_config_count < 1
            or not 0 <= self.source_config_index < self.source_config_count
        ):
            _reject(
                "six_red_score_vector_config_index_invalid",
                "source_config_index must identify one source configuration",
            )
        if (
            not isinstance(self.source_code_commit, str)
            or len(self.source_code_commit) != 40
            or any(character not in "0123456789abcdef" for character in self.source_code_commit)
        ):
            _reject(
                "six_red_score_vector_code_commit_invalid",
                "source_code_commit must be a full lowercase git SHA",
            )
        tick_digest = _score_tick_digest(ticks)
        object.__setattr__(self, "score_tick_digest", tick_digest)
        object.__setattr__(
            self,
            "vector_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.six-red.full-score-vector.v1",
            ),
        )

    @classmethod
    def from_full_score_grid(
        cls,
        artifact: FullScoreGridArtifactV1,
        *,
        verified_runtime: VerifiedRuntimePackage,
        weights: WeightMatrix,
        config_index: int,
    ) -> SixRedFullScoreVector:
        FullScoreGridArtifactVerifierV1().verify(
            artifact,
            verified_runtime=verified_runtime,
            weights=weights,
        )
        if artifact.header.candidate_count != SIX_RED_UNIVERSE.cardinality:
            _reject(
                "six_red_score_vector_universe_incomplete",
                "FullScore artifact must cover the complete six-red universe",
                expected=SIX_RED_UNIVERSE.cardinality,
                actual=artifact.header.candidate_count,
            )
        if (
            not isinstance(config_index, int)
            or isinstance(config_index, bool)
            or not 0 <= config_index < artifact.header.config_count
        ):
            _reject(
                "six_red_score_vector_config_index_invalid",
                "config_index must identify one FullScore configuration column",
            )
        scores = artifact.scores[:, config_index]
        with np.errstate(over="ignore", invalid="ignore"):
            scaled = scores * SCORE_TICK_SCALE
        if np.any(scaled > np.iinfo(np.int64).max) or np.any(scaled < np.iinfo(np.int64).min):
            _reject(
                "six_red_score_vector_tick_overflow",
                "round-8 scores do not fit signed int64 ticks",
            )
        ticks = np.ascontiguousarray(np.rint(scaled), dtype=np.int64)
        reconstructed = np.round(ticks.astype(np.float64) / SCORE_TICK_SCALE, SCORE_ROUND_DIGITS)
        if not np.array_equal(reconstructed, scores):
            _reject(
                "six_red_score_vector_round8_mismatch",
                "FullScore values must be exactly representable by round-8 score ticks",
            )
        ticks.setflags(write=False)
        envelope = artifact.runtime_envelope
        return cls(
            score_ticks=ticks,
            source_full_score_artifact_digest=artifact.artifact_digest,
            source_full_score_payload_digest=artifact.payload_digest,
            source_full_score_scores_digest=artifact.header.scores_digest,
            source_runtime_envelope_digest=envelope.envelope_digest,
            source_candidate_package_digest=envelope.candidate_package_digest,
            source_history_snapshot_digest=envelope.history_snapshot_digest,
            source_history_latest_issue=envelope.history_latest_issue or "",
            source_window_artifact_digest=envelope.window_artifact_digest,
            source_window_spec_digest=envelope.window_spec_digest,
            source_weights_digest=artifact.header.weights_digest,
            source_config_index=config_index,
            source_config_count=artifact.header.config_count,
            source_code_commit=envelope.code_commit,
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": SIX_RED_FULL_SCORE_VECTOR_VERSION,
            "contract": SEVEN_RED_SCORE_POOL_CONTRACT_V1.normative_identity(),
            "candidate_count": SIX_RED_UNIVERSE.cardinality,
            "tick_scale": SCORE_TICK_SCALE,
            "score_tick_digest": _score_tick_digest(self.score_ticks),
            "source_full_score_artifact_digest": self.source_full_score_artifact_digest,
            "source_full_score_payload_digest": self.source_full_score_payload_digest,
            "source_full_score_scores_digest": self.source_full_score_scores_digest,
            "source_runtime_envelope_digest": self.source_runtime_envelope_digest,
            "source_candidate_package_digest": self.source_candidate_package_digest,
            "source_history_snapshot_digest": self.source_history_snapshot_digest,
            "source_history_latest_issue": self.source_history_latest_issue,
            "source_window_artifact_digest": self.source_window_artifact_digest,
            "source_window_spec_digest": self.source_window_spec_digest,
            "source_weights_digest": self.source_weights_digest,
            "source_config_index": self.source_config_index,
            "source_config_count": self.source_config_count,
            "source_code_commit": self.source_code_commit,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "vector_digest": self.vector_digest}


@dataclass(frozen=True)
class SevenRedScorePoolConfig:
    seed_top_n: int
    pool_top_n: int
    configuration_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.seed_top_n, int)
            or isinstance(self.seed_top_n, bool)
            or not 1 <= self.seed_top_n <= SIX_RED_UNIVERSE.cardinality
        ):
            _reject(
                "seven_red_score_pool_seed_top_n_invalid",
                "seed_top_n must be an explicit integer in the full six-red universe",
            )
        if (
            not isinstance(self.pool_top_n, int)
            or isinstance(self.pool_top_n, bool)
            or self.pool_top_n < 10
        ):
            _reject(
                "seven_red_score_pool_pool_top_n_invalid",
                "pool_top_n must be an explicit integer of at least 10",
            )
        object.__setattr__(
            self,
            "configuration_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.score-pool-config.v1",
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": SEVEN_RED_SCORE_POOL_CONFIG_VERSION,
            "compiler_contract": SEVEN_RED_SCORE_POOL_COMPILER_CONTRACT,
            "seed_top_n": self.seed_top_n,
            "pool_top_n": self.pool_top_n,
            "default_policy": None,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "configuration_digest": self.configuration_digest}


@dataclass(frozen=True)
class SixRedSeed:
    seed_rank: int
    six_red: SixRedCombination
    score_tick: int

    def __post_init__(self) -> None:
        if not isinstance(self.seed_rank, int) or isinstance(self.seed_rank, bool) or self.seed_rank < 1:
            _reject("seven_red_score_pool_seed_rank_invalid", "seed_rank must be positive")
        if not isinstance(self.six_red, SixRedCombination):
            _reject("seven_red_score_pool_seed_type_invalid", "seed must be a SixRedCombination")
        if not isinstance(self.score_tick, int) or isinstance(self.score_tick, bool):
            _reject("seven_red_score_pool_seed_tick_invalid", "seed score_tick must be an integer")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "seed_rank": self.seed_rank,
            "six_red": self.six_red.identity_payload(),
            "score_tick": self.score_tick,
        }


@dataclass(frozen=True)
class SevenRedPoolScore:
    pool_rank: int
    scored_candidate: ScoredSevenRedCandidate
    constituent_six_red_lex_ids: tuple[int, ...]
    constituent_score_ticks: tuple[int, ...]
    constituent_tick_sum: int
    ranking_tick: int
    source_seed_ranks: tuple[int, ...]
    entry_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.pool_rank, int)
            or isinstance(self.pool_rank, bool)
            or self.pool_rank < 1
        ):
            _reject("seven_red_score_pool_rank_invalid", "pool_rank must be positive")
        if not isinstance(self.scored_candidate, ScoredSevenRedCandidate):
            _reject("seven_red_score_pool_row_type_invalid", "pool score requires a scored candidate")
        if (
            not isinstance(self.constituent_six_red_lex_ids, tuple)
            or len(self.constituent_six_red_lex_ids) != 7
            or tuple(sorted(self.constituent_six_red_lex_ids)) != self.constituent_six_red_lex_ids
            or len(set(self.constituent_six_red_lex_ids)) != 7
        ):
            _reject(
                "seven_red_score_pool_constituents_invalid",
                "constituent lex IDs must be seven unique sorted values",
            )
        if (
            not isinstance(self.constituent_score_ticks, tuple)
            or len(self.constituent_score_ticks) != 7
        ):
            _reject(
                "seven_red_score_pool_constituent_ticks_invalid",
                "seven constituent score ticks are required",
            )
        if any(
            not isinstance(value, int) or isinstance(value, bool)
            for value in self.constituent_score_ticks
        ):
            _reject(
                "seven_red_score_pool_constituent_ticks_invalid",
                "constituent score ticks must be integers",
            )
        if (
            not isinstance(self.constituent_tick_sum, int)
            or isinstance(self.constituent_tick_sum, bool)
            or self.constituent_tick_sum != sum(self.constituent_score_ticks)
        ):
            _reject(
                "seven_red_score_pool_tick_sum_mismatch",
                "constituent_tick_sum is inconsistent",
            )
        if (
            not isinstance(self.ranking_tick, int)
            or isinstance(self.ranking_tick, bool)
            or self.ranking_tick != _exact_mean_ranking_tick(self.constituent_tick_sum)
        ):
            _reject(
                "seven_red_score_pool_ranking_tick_mismatch",
                "ranking_tick is not the exact rounded mean tick",
            )
        if (
            not isinstance(self.source_seed_ranks, tuple)
            or not self.source_seed_ranks
            or tuple(sorted(set(self.source_seed_ranks))) != self.source_seed_ranks
            or any(
                not isinstance(rank, int) or isinstance(rank, bool) or rank < 1
                for rank in self.source_seed_ranks
            )
        ):
            _reject(
                "seven_red_score_pool_source_seed_ranks_invalid",
                "source seed ranks must be unique sorted positive integers",
            )
        expected = tuple(
            SixRedCombination(numbers).lex_id
            for numbers in combinations(self.scored_candidate.candidate.sorted_red_numbers, 6)
        )
        if self.constituent_six_red_lex_ids != expected:
            _reject(
                "seven_red_score_pool_constituent_identity_mismatch",
                "constituent lex IDs do not match candidate subsets",
            )
        expected_float = self.constituent_tick_sum / (7 * SCORE_TICK_SCALE)
        if (
            not isfinite(expected_float)
            or self.scored_candidate.raw_score != expected_float
            or self.scored_candidate.normalized_score != expected_float
            or self.scored_candidate.ranking_score != self.ranking_tick / SCORE_TICK_SCALE
        ):
            _reject(
                "seven_red_score_pool_float_projection_mismatch",
                "stored float projection does not match exact ticks",
            )
        object.__setattr__(
            self,
            "entry_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.score-pool-entry.v1",
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "pool_rank": self.pool_rank,
            "scored_candidate": self.scored_candidate.as_dict(),
            "constituent_six_red_lex_ids": list(self.constituent_six_red_lex_ids),
            "constituent_score_ticks": list(self.constituent_score_ticks),
            "constituent_tick_sum": self.constituent_tick_sum,
            "ranking_tick": self.ranking_tick,
            "source_seed_ranks": list(self.source_seed_ranks),
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "entry_digest": self.entry_digest}


@dataclass(frozen=True)
class SevenRedScoredCandidatePoolSnapshot:
    source_vector: SixRedFullScoreVector = field(repr=False)
    configuration: SevenRedScorePoolConfig
    target_issue: str
    seeds: tuple[SixRedSeed, ...]
    generated_occurrence_count: int
    deduplicated_candidate_count: int
    ranked_pool: tuple[SevenRedPoolScore, ...]
    candidate_pool: PreScoredSevenRedCandidateList
    snapshot_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_vector, SixRedFullScoreVector):
            _reject(
                "seven_red_score_pool_source_vector_invalid",
                "snapshot requires a full score vector",
            )
        if not isinstance(self.configuration, SevenRedScorePoolConfig):
            _reject(
                "seven_red_score_pool_config_invalid",
                "snapshot requires a score-pool configuration",
            )
        target = _require_issue(self.target_issue, field_name="target_issue")
        if int(self.source_vector.source_history_latest_issue) >= int(target):
            _reject(
                "seven_red_score_pool_chronology_invalid",
                "source history must end strictly before target_issue",
            )
        if (
            not isinstance(self.seeds, tuple)
            or len(self.seeds) != self.configuration.seed_top_n
        ):
            _reject(
                "seven_red_score_pool_seed_count_mismatch",
                "snapshot seed count does not match M",
            )
        if tuple(seed.seed_rank for seed in self.seeds) != tuple(
            range(1, len(self.seeds) + 1)
        ):
            _reject(
                "seven_red_score_pool_seed_order_invalid",
                "seed ranks must be contiguous",
            )
        if self.generated_occurrence_count != 27 * len(self.seeds):
            _reject("seven_red_score_pool_generated_count_mismatch", "each seed must generate 27 supersets")
        if (
            not isinstance(self.deduplicated_candidate_count, int)
            or isinstance(self.deduplicated_candidate_count, bool)
            or not self.configuration.pool_top_n
            <= self.deduplicated_candidate_count
            <= self.generated_occurrence_count
        ):
            _reject(
                "seven_red_score_pool_dedup_count_invalid",
                "deduplicated candidate count is invalid",
            )
        if (
            not isinstance(self.ranked_pool, tuple)
            or len(self.ranked_pool) != self.configuration.pool_top_n
        ):
            _reject(
                "seven_red_score_pool_output_count_mismatch",
                "ranked pool count does not match P",
            )
        if tuple(row.pool_rank for row in self.ranked_pool) != tuple(
            range(1, len(self.ranked_pool) + 1)
        ):
            _reject(
                "seven_red_score_pool_rank_order_invalid",
                "pool ranks must be contiguous",
            )
        canonical_ranked = tuple(
            sorted(
                self.ranked_pool,
                key=lambda row: (-row.ranking_tick, row.scored_candidate.candidate.lex_id),
            )
        )
        if self.ranked_pool != canonical_ranked:
            _reject(
                "seven_red_score_pool_rank_order_invalid",
                "ranked pool violates exact score/lex order",
            )
        if not isinstance(self.candidate_pool, PreScoredSevenRedCandidateList):
            _reject(
                "seven_red_score_pool_candidate_list_invalid",
                "candidate_pool must use the existing pre-scored candidate-list ABI",
            )
        expected_pool = PreScoredSevenRedCandidateList.build(
            [row.scored_candidate for row in self.ranked_pool]
        )
        if self.candidate_pool.artifact_digest != expected_pool.artifact_digest:
            _reject(
                "seven_red_score_pool_candidate_list_mismatch",
                "candidate_pool does not match ranked rows",
            )
        object.__setattr__(
            self,
            "snapshot_digest",
            canonical_digest(self.identity_payload(), domain="dehps.seven-red.score-pool-snapshot.v1"),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": SEVEN_RED_SCORE_POOL_SNAPSHOT_VERSION,
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": SEVEN_RED_SCORE_POOL_CONTRACT_V1.normative_identity(),
            "compiler_contract": SEVEN_RED_SCORE_POOL_COMPILER_CONTRACT,
            "raw_top10_ranking_contract": RAW_TOP10_RANKING_CONTRACT,
            "source_vector": self.source_vector.as_dict(),
            "configuration": self.configuration.as_dict(),
            "target_issue": self.target_issue,
            "seeds": [seed.identity_payload() for seed in self.seeds],
            "generated_occurrence_count": self.generated_occurrence_count,
            "deduplicated_candidate_count": self.deduplicated_candidate_count,
            "ranked_pool": [row.as_dict() for row in self.ranked_pool],
            "candidate_pool_artifact_digest": self.candidate_pool.artifact_digest,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "snapshot_digest": self.snapshot_digest}


class SevenRedScorePoolCompiler:
    def compile(
        self,
        *,
        source_vector: SixRedFullScoreVector,
        configuration: SevenRedScorePoolConfig,
        target_issue: str,
    ) -> SevenRedScoredCandidatePoolSnapshot:
        if not isinstance(source_vector, SixRedFullScoreVector):
            _reject("seven_red_score_pool_source_vector_invalid", "compiler requires a full score vector")
        if not isinstance(configuration, SevenRedScorePoolConfig):
            _reject("seven_red_score_pool_config_invalid", "compiler requires an explicit configuration")
        target = _require_issue(target_issue, field_name="target_issue")
        if int(source_vector.source_history_latest_issue) >= int(target):
            _reject("seven_red_score_pool_chronology_invalid", "source history must end strictly before target_issue")

        seed_ids = self._top_seed_ids(source_vector.score_ticks, configuration.seed_top_n)
        seeds = tuple(
            SixRedSeed(
                seed_rank=rank,
                six_red=SixRedCombination(
                    candidate_unrank(int(lex_id), universe=SIX_RED_UNIVERSE)
                ),
                score_tick=int(source_vector.score_ticks[lex_id]),
            )
            for rank, lex_id in enumerate(seed_ids, start=1)
        )

        source_ranks_by_candidate: dict[int, list[int]] = defaultdict(list)
        candidates: dict[int, SevenRedCandidate] = {}
        for seed in seeds:
            seed_numbers = set(seed.six_red.sorted_red_numbers)
            for added in range(1, 34):
                if added in seed_numbers:
                    continue
                candidate = SevenRedCandidate.from_numbers(
                    tuple(sorted((*seed.six_red.sorted_red_numbers, added)))
                )
                candidates[candidate.lex_id] = candidate
                source_ranks_by_candidate[candidate.lex_id].append(seed.seed_rank)
        if len(candidates) < configuration.pool_top_n:
            _reject(
                "seven_red_score_pool_insufficient_candidates",
                "deduplicated candidate space is smaller than P",
                deduplicated_candidate_count=len(candidates),
                pool_top_n=configuration.pool_top_n,
            )

        working: list[tuple[int, int, SevenRedCandidate, tuple[int, ...], tuple[int, ...], tuple[int, ...]]] = []
        for candidate_id in sorted(candidates):
            candidate = candidates[candidate_id]
            constituent_ids = tuple(
                SixRedCombination(numbers).lex_id
                for numbers in combinations(candidate.sorted_red_numbers, 6)
            )
            constituent_ticks = tuple(int(source_vector.score_ticks[lex_id]) for lex_id in constituent_ids)
            total_tick = sum(constituent_ticks)
            ranking_tick = _exact_mean_ranking_tick(total_tick)
            working.append(
                (
                    ranking_tick,
                    total_tick,
                    candidate,
                    constituent_ids,
                    constituent_ticks,
                    tuple(source_ranks_by_candidate[candidate_id]),
                )
            )
        working.sort(key=lambda row: (-row[0], row[2].lex_id))
        selected = working[: configuration.pool_top_n]
        source_run_id = f"seven-red-score-pool:{target}:{source_vector.vector_digest}"
        ranked_rows: list[SevenRedPoolScore] = []
        for rank, (
            ranking_tick,
            total_tick,
            candidate,
            constituent_ids,
            constituent_ticks,
            source_seed_ranks,
        ) in enumerate(selected, start=1):
            projected_score = total_tick / (7 * SCORE_TICK_SCALE)
            feature_digest = canonical_digest(
                {
                    "compiler_contract": SEVEN_RED_SCORE_POOL_COMPILER_CONTRACT,
                    "source_vector_digest": source_vector.vector_digest,
                    "configuration_digest": configuration.configuration_digest,
                    "target_issue": target,
                    "candidate_id": candidate.candidate_id,
                    "constituent_six_red_lex_ids": list(constituent_ids),
                    "constituent_score_ticks": list(constituent_ticks),
                    "constituent_tick_sum": total_tick,
                    "ranking_tick": ranking_tick,
                },
                domain="dehps.seven-red.score-pool-feature.v1",
            )
            scored = ScoredSevenRedCandidate.build(
                candidate=candidate,
                raw_score=projected_score,
                normalized_score=projected_score,
                source_model=SEVEN_RED_SCORE_SOURCE_MODEL,
                feature_digest=feature_digest,
                source_run_id=source_run_id,
            )
            ranked_rows.append(
                SevenRedPoolScore(
                    pool_rank=rank,
                    scored_candidate=scored,
                    constituent_six_red_lex_ids=constituent_ids,
                    constituent_score_ticks=constituent_ticks,
                    constituent_tick_sum=total_tick,
                    ranking_tick=ranking_tick,
                    source_seed_ranks=source_seed_ranks,
                )
            )
        ranked_pool = tuple(ranked_rows)
        candidate_pool = PreScoredSevenRedCandidateList.build(
            [row.scored_candidate for row in ranked_pool]
        )
        return SevenRedScoredCandidatePoolSnapshot(
            source_vector=source_vector,
            configuration=configuration,
            target_issue=target,
            seeds=seeds,
            generated_occurrence_count=27 * len(seeds),
            deduplicated_candidate_count=len(candidates),
            ranked_pool=ranked_pool,
            candidate_pool=candidate_pool,
        )

    @staticmethod
    def _top_seed_ids(score_ticks: np.ndarray, top_n: int) -> np.ndarray:
        count = len(score_ticks)
        if top_n < count:
            threshold = np.partition(score_ticks, count - top_n)[count - top_n]
            better = np.flatnonzero(score_ticks > threshold)
            equal = np.flatnonzero(score_ticks == threshold)
            remaining = top_n - len(better)
            selected_equal = equal[:remaining]
            selected = np.concatenate((better, selected_equal))
        else:
            selected = np.arange(count, dtype=np.int64)
        order = np.lexsort((selected, -score_ticks[selected]))
        return np.ascontiguousarray(selected[order[:top_n]], dtype=np.int64)


class SevenRedScorePoolVerifier:
    def verify(self, snapshot: SevenRedScoredCandidatePoolSnapshot) -> None:
        if not isinstance(snapshot, SevenRedScoredCandidatePoolSnapshot):
            _reject(
                "seven_red_score_pool_snapshot_type_invalid",
                "verifier requires a SevenRedScoredCandidatePoolSnapshot",
            )
        replay = SevenRedScorePoolCompiler().compile(
            source_vector=snapshot.source_vector,
            configuration=snapshot.configuration,
            target_issue=snapshot.target_issue,
        )
        if replay.snapshot_digest != snapshot.snapshot_digest:
            _reject(
                "seven_red_score_pool_snapshot_replay_mismatch",
                "snapshot does not match deterministic compilation from its bound source",
                expected=replay.snapshot_digest,
                actual=snapshot.snapshot_digest,
            )


def compile_seven_red_score_pool(
    *,
    source_vector: SixRedFullScoreVector,
    configuration: SevenRedScorePoolConfig,
    target_issue: str,
) -> SevenRedScoredCandidatePoolSnapshot:
    return SevenRedScorePoolCompiler().compile(
        source_vector=source_vector,
        configuration=configuration,
        target_issue=target_issue,
    )
