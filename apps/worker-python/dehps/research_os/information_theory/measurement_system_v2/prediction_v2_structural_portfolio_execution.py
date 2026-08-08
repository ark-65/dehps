from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numba import njit

from dehps.artifacts import atomic_write_text
from dehps.contracts import canonical_digest

PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY = (
    "prediction-v2-structural-portfolio-execution"
)
PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_CAPABILITY = (
    "prediction_v2_structural_portfolio_execution"
)
PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_COMPLETION_FACT = (
    "prediction-v2-structural-portfolio-execution:COMPLETE"
)
PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY = (
    "prediction-v2-structural-portfolio-evaluation"
)
PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/prediction-v2-structural-portfolio-execution-source-v1.json"
)

NUMBER_DOMAIN_SIZE = 33
COMBINATION_CARDINALITY = 6
LEGAL_UNIVERSE_CARDINALITY = 1_107_568
PAIR_UNIVERSE_CARDINALITY = 528
PRIMARY_CANDIDATE_BUDGET = 176
OPTIMIZER_ISLAND_COUNT = 22
PROPOSALS_PER_ISLAND = 262_144
TOTAL_OPTIMIZER_PROPOSALS = 5_767_168
NULL_REPLICATE_COUNT = 4_096
NULL_SHARD_SIZE = 64
NULL_SHARD_COUNT = 64
REFERENCE_PREFLIGHT_PROPOSALS = 1_024
CHECKPOINT_BOUNDARY_PROPOSALS = 16_384
OPTIMIZER_WALL_CLOCK_LIMIT_SECONDS = 7_200
NULL_WALL_CLOCK_LIMIT_SECONDS = 7_200
RESIDENT_MEMORY_LIMIT_BYTES = 2_147_483_648
MINIMUM_STRICTLY_DOMINATED_NULLS = 3_893
MAXIMUM_NULLS_DOMINATING_CANDIDATE = 0
REQUIRED_MINIMUM_REPLACEMENT_DISTANCE = 2
OPTIMIZER_ROOT_SEED_HEX = (
    "124aed827e6f68471da3733717919b9956be3c2e4ed256b11cf7ed2c8ed9b9d2"
)
NULL_ROOT_SEED_HEX = "ce969021ed72f5638d2b4534bd9c70af44854a6eb95973e5d7115a92f7a454ac"
UPSTREAM_PREREGISTRATION_EXECUTION_DIGEST = (
    "680baf366585babf63b8c2f10184a803d6d4333e73ed2d86717d367ff1169277"
)
UPSTREAM_PREREGISTRATION_DIGEST = (
    "67091e9bfe1ac05d2b659be71f669c96c17997d29ca7a100138338f9cad8218f"
)
UPSTREAM_EXECUTION_CONTRACT_DIGEST = (
    "70f4de2ad7684fdd35f6cdab3740559cbb5e2d1135be2554a871bf05a3c51028"
)
UPSTREAM_EXECUTION_HANDOFF_DIGEST = (
    "276b79eca9f28c736ee64b48385be95f31d0154b5a2c7dec1e95399c3bd1dc98"
)
UPSTREAM_PREREGISTRATION_COMPLETION_DIGEST = (
    "b5fca17f952ae3370b81239011d8f06154cd0b4cf5aa9f244eff670682fc95a3"
)

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-structural-portfolio-execution-round-66-20260809"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-structural-portfolio-execution-round-66-20260809"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/prediction_v2_structural_portfolio_execution.py"
)


class PredictionV2StructuralPortfolioExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class StructuralStats:
    singleton_square_sum: int
    pair_square_sum: int
    minimum_replacement_distance: int
    sum_pairwise_replacement_distance: int

    def to_dict(self) -> dict[str, int]:
        return {
            "singleton_square_sum": self.singleton_square_sum,
            "pair_square_sum": self.pair_square_sum,
            "minimum_replacement_distance": self.minimum_replacement_distance,
            "sum_pairwise_replacement_distance": (
                self.sum_pairwise_replacement_distance
            ),
        }


@dataclass(frozen=True)
class ExecutionSettings:
    candidate_budget: int = PRIMARY_CANDIDATE_BUDGET
    island_count: int = OPTIMIZER_ISLAND_COUNT
    proposals_per_island: int = PROPOSALS_PER_ISLAND
    null_replicate_count: int = NULL_REPLICATE_COUNT
    null_shard_size: int = NULL_SHARD_SIZE
    parallel_workers: int = OPTIMIZER_ISLAND_COUNT
    reference_preflight_proposals: int = REFERENCE_PREFLIGHT_PROPOSALS
    checkpoint_boundary_proposals: int = CHECKPOINT_BOUNDARY_PROPOSALS
    optimizer_wall_clock_limit_seconds: int = OPTIMIZER_WALL_CLOCK_LIMIT_SECONDS
    null_wall_clock_limit_seconds: int = NULL_WALL_CLOCK_LIMIT_SECONDS
    resident_memory_limit_bytes: int = RESIDENT_MEMORY_LIMIT_BYTES

    @property
    def null_shard_count(self) -> int:
        return (
            self.null_replicate_count + self.null_shard_size - 1
        ) // self.null_shard_size

    def is_production(self) -> bool:
        return self == PRODUCTION_SETTINGS


PRODUCTION_SETTINGS = ExecutionSettings()


@dataclass(frozen=True)
class UniverseTables:
    numbers: np.ndarray
    masks: np.ndarray
    pairs: np.ndarray

    @property
    def resident_bytes(self) -> int:
        return int(self.numbers.nbytes + self.masks.nbytes + self.pairs.nbytes)


@dataclass(frozen=True)
class StructuralPortfolioExecutionRun:
    portfolio: Mapping[str, Any]
    optimizer_index: Mapping[str, Any]
    null_comparison: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (
            self.portfolio,
            self.optimizer_index,
            self.null_comparison,
            self.completion,
        )


class CounterRng:
    """SHA256 counter stream with rejection-unbiased bounded draws."""

    def __init__(
        self,
        seed: bytes,
        *,
        counter: int = 0,
        words: Sequence[int] = (),
        cursor: int = 0,
    ) -> None:
        if len(seed) != 32:
            raise PredictionV2StructuralPortfolioExecutionError(
                "counter_rng_seed_must_be_32_bytes"
            )
        self.seed = seed
        self.counter = counter
        self.words = tuple(int(item) for item in words)
        self.cursor = cursor

    @classmethod
    def from_root(cls, root_seed_hex: str, purpose: str, index: int) -> CounterRng:
        material = f"{root_seed_hex.lower()}|{purpose}|{index:08d}".encode("ascii")
        return cls(hashlib.sha256(material).digest())

    def _next_word(self) -> int:
        if self.cursor >= len(self.words):
            block = hashlib.sha256(
                self.seed + self.counter.to_bytes(8, "big", signed=False)
            ).digest()
            self.counter += 1
            self.words = tuple(
                int.from_bytes(block[offset : offset + 8], "big", signed=False)
                for offset in range(0, 32, 8)
            )
            self.cursor = 0
        word = self.words[self.cursor]
        self.cursor += 1
        return word

    def bounded(self, bound: int) -> int:
        if bound <= 0 or bound > 2**64:
            raise PredictionV2StructuralPortfolioExecutionError(
                f"counter_rng_bound_invalid:{bound}"
            )
        limit = (2**64 // bound) * bound
        while True:
            word = self._next_word()
            if word < limit:
                return word % bound

    def snapshot(self) -> dict[str, Any]:
        return {
            "counter": self.counter,
            "words": list(self.words),
            "cursor": self.cursor,
        }

    @classmethod
    def restore(cls, seed: bytes, payload: Mapping[str, Any]) -> CounterRng:
        return cls(
            seed,
            counter=int(payload["counter"]),
            words=tuple(int(item) for item in payload["words"]),
            cursor=int(payload["cursor"]),
        )


def _artifact(
    payload: Mapping[str, Any],
    *,
    schema_version: str,
    artifact_type: str,
    domain: str,
) -> dict[str, Any]:
    result = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "artifact_digest": "",
        **dict(payload),
    }
    identity = dict(result)
    identity.pop("artifact_digest")
    result["artifact_digest"] = canonical_digest(identity, domain=domain)
    return result


def load_prediction_v2_structural_portfolio_execution_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2StructuralPortfolioExecutionError(
            f"structural_portfolio_execution_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-prediction-v2-structural-portfolio-execution-source.v1"
        or payload.get("artifact_type")
        != "prediction_v2_structural_portfolio_execution_source"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 391
        or payload.get("research_execution_id") != 312
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 392
        or payload.get("engineering_execution_id") != 313
        or not isinstance(entries, list)
        or len(entries) != 1
        or not isinstance(frozen, dict)
        or frozen.get("task_key")
        != PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_TASK_KEY
        or frozen.get("capability")
        != PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_CAPABILITY
        or frozen.get("upstream_execution_contract_digest")
        != UPSTREAM_EXECUTION_CONTRACT_DIGEST
        or frozen.get("candidate_budget") != PRIMARY_CANDIDATE_BUDGET
        or frozen.get("optimizer_island_count") != OPTIMIZER_ISLAND_COUNT
        or frozen.get("proposals_per_island") != PROPOSALS_PER_ISLAND
        or frozen.get("total_optimizer_proposals") != TOTAL_OPTIMIZER_PROPOSALS
        or frozen.get("null_replicate_count") != NULL_REPLICATE_COUNT
        or frozen.get("reference_preflight_proposals") != REFERENCE_PREFLIGHT_PROPOSALS
        or frozen.get("checkpoint_boundary_proposals") != CHECKPOINT_BOUNDARY_PROPOSALS
        or frozen.get("registered_child_count") != 4
        or frozen.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY
    ):
        raise PredictionV2StructuralPortfolioExecutionError(
            "structural_portfolio_execution_source_invalid"
        )
    identity = dict(payload)
    artifact_digest = str(identity.pop("artifact_digest", ""))
    if canonical_digest(
        {"source_entries": entries},
        domain="dehps.prediction-v2.structural-portfolio-execution-source-set.v1",
    ) != payload.get("source_set_digest") or canonical_digest(
        frozen,
        domain=(
            "dehps.prediction-v2.structural-portfolio-execution-frozen-contract.v1"
        ),
    ) != payload.get("frozen_contract_digest"):
        raise PredictionV2StructuralPortfolioExecutionError(
            "structural_portfolio_execution_nested_digest_invalid"
        )
    if (
        canonical_digest(
            identity,
            domain="dehps.prediction-v2.structural-portfolio-execution-source.v1",
        )
        != artifact_digest
    ):
        raise PredictionV2StructuralPortfolioExecutionError(
            "structural_portfolio_execution_source_digest_invalid"
        )
    return payload


def verify_prediction_v2_structural_portfolio_execution_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = root_dir / relative
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise PredictionV2StructuralPortfolioExecutionError(
                f"structural_portfolio_execution_source_missing:{relative}"
            ) from exc
        if hashlib.sha256(content).hexdigest() != entry["content_sha256"]:
            raise PredictionV2StructuralPortfolioExecutionError(
                f"structural_portfolio_execution_source_modified:{relative}"
            )


@njit(cache=True)
def _pair_rank(left: int, right: int) -> int:
    return left * (65 - left) // 2 + right - left - 1


@njit(cache=True)
def _build_universe_tables_kernel(
    numbers: np.ndarray, masks: np.ndarray, pairs: np.ndarray
) -> int:
    rank = 0
    for a in range(28):
        for b in range(a + 1, 29):
            for c in range(b + 1, 30):
                for d in range(c + 1, 31):
                    for e in range(d + 1, 32):
                        for f in range(e + 1, 33):
                            values = (a, b, c, d, e, f)
                            mask = np.uint64(0)
                            for idx in range(6):
                                value = values[idx]
                                numbers[rank, idx] = value + 1
                                mask |= np.uint64(1) << np.uint64(value)
                            masks[rank] = mask
                            pair_offset = 0
                            for left in range(5):
                                for right in range(left + 1, 6):
                                    pairs[rank, pair_offset] = _pair_rank(
                                        values[left], values[right]
                                    )
                                    pair_offset += 1
                            rank += 1
    return rank


_UNIVERSE_TABLES_CACHE: UniverseTables | None = None
_WORKER_TABLES: UniverseTables | None = None


def build_universe_tables() -> UniverseTables:
    global _UNIVERSE_TABLES_CACHE
    if _UNIVERSE_TABLES_CACHE is not None:
        return _UNIVERSE_TABLES_CACHE
    numbers = np.empty(
        (LEGAL_UNIVERSE_CARDINALITY, COMBINATION_CARDINALITY), dtype=np.uint8
    )
    masks = np.empty(LEGAL_UNIVERSE_CARDINALITY, dtype=np.uint64)
    pairs = np.empty((LEGAL_UNIVERSE_CARDINALITY, 15), dtype=np.uint16)
    count = int(_build_universe_tables_kernel(numbers, masks, pairs))
    if count != LEGAL_UNIVERSE_CARDINALITY:
        raise PredictionV2StructuralPortfolioExecutionError(
            f"legal_universe_materialization_count_changed:{count}"
        )
    numbers.flags.writeable = False
    masks.flags.writeable = False
    pairs.flags.writeable = False
    _UNIVERSE_TABLES_CACHE = UniverseTables(numbers=numbers, masks=masks, pairs=pairs)
    return _UNIVERSE_TABLES_CACHE


@njit(cache=True)
def _popcount_u64(value: np.uint64) -> int:
    count = 0
    while value:
        value &= value - np.uint64(1)
        count += 1
    return count


@njit(cache=True)
def _stats_from_ranks_kernel(
    ranks: np.ndarray,
    numbers: np.ndarray,
    masks: np.ndarray,
    pairs: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, int, int, int]:
    singleton_counts = np.zeros(NUMBER_DOMAIN_SIZE, dtype=np.int32)
    pair_counts = np.zeros(PAIR_UNIVERSE_CARDINALITY, dtype=np.int32)
    distance_histogram = np.zeros(7, dtype=np.int64)
    for rank in ranks:
        for idx in range(6):
            singleton_counts[int(numbers[int(rank), idx]) - 1] += 1
        for idx in range(15):
            pair_counts[int(pairs[int(rank), idx])] += 1
    singleton_square_sum = 0
    for value in singleton_counts:
        singleton_square_sum += int(value) * int(value)
    pair_square_sum = 0
    for value in pair_counts:
        pair_square_sum += int(value) * int(value)
    for left in range(len(ranks) - 1):
        left_mask = masks[int(ranks[left])]
        for right in range(left + 1, len(ranks)):
            distance = 6 - _popcount_u64(left_mask & masks[int(ranks[right])])
            distance_histogram[distance] += 1
    minimum_distance = 0
    distance_sum = 0
    for distance in range(7):
        if minimum_distance == 0 and distance_histogram[distance] > 0:
            minimum_distance = distance
        distance_sum += distance * int(distance_histogram[distance])
    return (
        singleton_counts,
        pair_counts,
        distance_histogram,
        singleton_square_sum,
        pair_square_sum,
        minimum_distance,
        distance_sum,
    )


def structural_stats(
    ranks: np.ndarray, tables: UniverseTables | None = None
) -> tuple[StructuralStats, np.ndarray, np.ndarray, np.ndarray]:
    tables = tables or build_universe_tables()
    result = _stats_from_ranks_kernel(
        np.asarray(ranks, dtype=np.uint32),
        tables.numbers,
        tables.masks,
        tables.pairs,
    )
    singleton_counts, pair_counts, histogram = result[:3]
    stats = StructuralStats(*(int(value) for value in result[3:]))
    return stats, singleton_counts, pair_counts, histogram


def _scalar_stats(
    ranks: Sequence[int], tables: UniverseTables
) -> tuple[StructuralStats, np.ndarray, np.ndarray, np.ndarray]:
    singleton_counts = np.zeros(NUMBER_DOMAIN_SIZE, dtype=np.int32)
    pair_counts = np.zeros(PAIR_UNIVERSE_CARDINALITY, dtype=np.int32)
    distance_histogram = np.zeros(7, dtype=np.int64)
    rank_list = [int(item) for item in ranks]
    for rank in rank_list:
        for value in tables.numbers[rank]:
            singleton_counts[int(value) - 1] += 1
        for pair in tables.pairs[rank]:
            pair_counts[int(pair)] += 1
    for left in range(len(rank_list) - 1):
        left_mask = int(tables.masks[rank_list[left]])
        for right in range(left + 1, len(rank_list)):
            distance = 6 - (left_mask & int(tables.masks[rank_list[right]])).bit_count()
            distance_histogram[distance] += 1
    singleton_square_sum = sum(int(value) ** 2 for value in singleton_counts)
    pair_square_sum = sum(int(value) ** 2 for value in pair_counts)
    minimum_distance = next(
        (idx for idx, value in enumerate(distance_histogram) if value), 0
    )
    distance_sum = sum(idx * int(value) for idx, value in enumerate(distance_histogram))
    return (
        StructuralStats(
            singleton_square_sum=singleton_square_sum,
            pair_square_sum=pair_square_sum,
            minimum_replacement_distance=minimum_distance,
            sum_pairwise_replacement_distance=distance_sum,
        ),
        singleton_counts,
        pair_counts,
        distance_histogram,
    )


@njit(cache=True)
def _run_proposal_block_kernel(
    permutation: np.ndarray,
    singleton_counts: np.ndarray,
    pair_counts: np.ndarray,
    distance_histogram: np.ndarray,
    singleton_square_sum: int,
    pair_square_sum: int,
    minimum_distance: int,
    distance_sum: int,
    selected_indexes: np.ndarray,
    suffix_positions: np.ndarray,
    numbers: np.ndarray,
    masks: np.ndarray,
    pairs: np.ndarray,
    candidate_budget: int,
) -> tuple[int, int, int, int, int]:
    accepted = 0
    changed_numbers = np.empty(12, dtype=np.int16)
    number_deltas = np.empty(12, dtype=np.int8)
    changed_pairs = np.empty(30, dtype=np.int16)
    pair_deltas = np.empty(30, dtype=np.int8)
    proposed_histogram = np.empty(7, dtype=np.int64)
    for proposal_index in range(len(selected_indexes)):
        selected_index = int(selected_indexes[proposal_index])
        suffix_position = int(suffix_positions[proposal_index])
        outgoing_rank = int(permutation[selected_index])
        incoming_rank = int(permutation[suffix_position])

        changed_number_count = 0
        for direction in range(2):
            rank = outgoing_rank if direction == 0 else incoming_rank
            delta = -1 if direction == 0 else 1
            for item_index in range(6):
                item = int(numbers[rank, item_index]) - 1
                found = -1
                for change_index in range(changed_number_count):
                    if changed_numbers[change_index] == item:
                        found = change_index
                        break
                if found < 0:
                    changed_numbers[changed_number_count] = item
                    number_deltas[changed_number_count] = delta
                    changed_number_count += 1
                else:
                    number_deltas[found] += delta
        proposed_singleton_square_sum = singleton_square_sum
        for change_index in range(changed_number_count):
            item = int(changed_numbers[change_index])
            delta = int(number_deltas[change_index])
            current = int(singleton_counts[item])
            proposed_singleton_square_sum += (current + delta) ** 2 - current**2

        changed_pair_count = 0
        for direction in range(2):
            rank = outgoing_rank if direction == 0 else incoming_rank
            delta = -1 if direction == 0 else 1
            for item_index in range(15):
                item = int(pairs[rank, item_index])
                found = -1
                for change_index in range(changed_pair_count):
                    if changed_pairs[change_index] == item:
                        found = change_index
                        break
                if found < 0:
                    changed_pairs[changed_pair_count] = item
                    pair_deltas[changed_pair_count] = delta
                    changed_pair_count += 1
                else:
                    pair_deltas[found] += delta
        proposed_pair_square_sum = pair_square_sum
        for change_index in range(changed_pair_count):
            item = int(changed_pairs[change_index])
            delta = int(pair_deltas[change_index])
            current = int(pair_counts[item])
            proposed_pair_square_sum += (current + delta) ** 2 - current**2

        for distance in range(7):
            proposed_histogram[distance] = distance_histogram[distance]
        outgoing_mask = masks[outgoing_rank]
        incoming_mask = masks[incoming_rank]
        proposed_distance_sum = distance_sum
        for other_index in range(candidate_budget):
            if other_index == selected_index:
                continue
            other_mask = masks[int(permutation[other_index])]
            old_distance = 6 - _popcount_u64(outgoing_mask & other_mask)
            new_distance = 6 - _popcount_u64(incoming_mask & other_mask)
            proposed_histogram[old_distance] -= 1
            proposed_histogram[new_distance] += 1
            proposed_distance_sum += new_distance - old_distance
        proposed_minimum_distance = 0
        for distance in range(7):
            if proposed_histogram[distance] > 0:
                proposed_minimum_distance = distance
                break

        no_worse = (
            proposed_singleton_square_sum <= singleton_square_sum
            and proposed_pair_square_sum <= pair_square_sum
            and proposed_minimum_distance >= minimum_distance
            and proposed_distance_sum >= distance_sum
        )
        strict = (
            proposed_singleton_square_sum < singleton_square_sum
            or proposed_pair_square_sum < pair_square_sum
            or proposed_minimum_distance > minimum_distance
            or proposed_distance_sum > distance_sum
        )
        equal_tie = (
            proposed_singleton_square_sum == singleton_square_sum
            and proposed_pair_square_sum == pair_square_sum
            and proposed_minimum_distance == minimum_distance
            and proposed_distance_sum == distance_sum
            and incoming_rank < outgoing_rank
        )
        if no_worse and (strict or equal_tie):
            for change_index in range(changed_number_count):
                singleton_counts[int(changed_numbers[change_index])] += int(
                    number_deltas[change_index]
                )
            for change_index in range(changed_pair_count):
                pair_counts[int(changed_pairs[change_index])] += int(
                    pair_deltas[change_index]
                )
            for distance in range(7):
                distance_histogram[distance] = proposed_histogram[distance]
            permutation[selected_index], permutation[suffix_position] = (
                permutation[suffix_position],
                permutation[selected_index],
            )
            singleton_square_sum = proposed_singleton_square_sum
            pair_square_sum = proposed_pair_square_sum
            minimum_distance = proposed_minimum_distance
            distance_sum = proposed_distance_sum
            accepted += 1
    return (
        accepted,
        singleton_square_sum,
        pair_square_sum,
        minimum_distance,
        distance_sum,
    )


def _initialization_draws(rng: CounterRng, candidate_budget: int) -> np.ndarray:
    draws = np.empty(candidate_budget, dtype=np.uint32)
    for index in range(candidate_budget):
        draws[index] = index + rng.bounded(LEGAL_UNIVERSE_CARDINALITY - index)
    return draws


@njit(cache=True)
def _initialize_permutation_kernel(draws: np.ndarray) -> np.ndarray:
    permutation = np.arange(LEGAL_UNIVERSE_CARDINALITY, dtype=np.uint32)
    for index in range(len(draws)):
        target = int(draws[index])
        permutation[index], permutation[target] = (
            permutation[target],
            permutation[index],
        )
    return permutation


def _proposal_draws(
    rng: CounterRng, count: int, candidate_budget: int
) -> tuple[np.ndarray, np.ndarray]:
    selected = np.empty(count, dtype=np.uint16)
    suffix = np.empty(count, dtype=np.uint32)
    complement_size = LEGAL_UNIVERSE_CARDINALITY - candidate_budget
    for index in range(count):
        selected[index] = rng.bounded(candidate_budget)
        suffix[index] = candidate_budget + rng.bounded(complement_size)
    return selected, suffix


def _stats_tuple(
    singleton_square_sum: int,
    pair_square_sum: int,
    minimum_distance: int,
    distance_sum: int,
) -> StructuralStats:
    return StructuralStats(
        singleton_square_sum=int(singleton_square_sum),
        pair_square_sum=int(pair_square_sum),
        minimum_replacement_distance=int(minimum_distance),
        sum_pairwise_replacement_distance=int(distance_sum),
    )


def _state_from_permutation(
    permutation: np.ndarray, candidate_budget: int, tables: UniverseTables
) -> tuple[np.ndarray, np.ndarray, np.ndarray, StructuralStats]:
    stats, singleton_counts, pair_counts, histogram = structural_stats(
        permutation[:candidate_budget], tables
    )
    return singleton_counts, pair_counts, histogram, stats


def run_reference_preflight(
    *,
    tables: UniverseTables,
    proposal_count: int = REFERENCE_PREFLIGHT_PROPOSALS,
    candidate_budget: int = PRIMARY_CANDIDATE_BUDGET,
) -> dict[str, Any]:
    fast_rng = CounterRng.from_root(OPTIMIZER_ROOT_SEED_HEX, "island", 0)
    scalar_rng = CounterRng.from_root(OPTIMIZER_ROOT_SEED_HEX, "island", 0)
    fast_initial = _initialization_draws(fast_rng, candidate_budget)
    scalar_initial = _initialization_draws(scalar_rng, candidate_budget)
    if not np.array_equal(fast_initial, scalar_initial):
        raise PredictionV2StructuralPortfolioExecutionError(
            "reference_preflight_initial_rng_disagreement"
        )
    fast_permutation = _initialize_permutation_kernel(fast_initial)
    scalar_permutation = _initialize_permutation_kernel(scalar_initial)
    fast_singletons, fast_pairs, fast_histogram, fast_stats = _state_from_permutation(
        fast_permutation, candidate_budget, tables
    )
    scalar_stats, scalar_singletons, scalar_pairs, scalar_histogram = _scalar_stats(
        scalar_permutation[:candidate_budget], tables
    )
    _require_state_equal(
        fast_permutation,
        fast_stats,
        fast_singletons,
        fast_pairs,
        fast_histogram,
        scalar_permutation,
        scalar_stats,
        scalar_singletons,
        scalar_pairs,
        scalar_histogram,
        candidate_budget,
        step=-1,
    )
    trace = hashlib.sha256()
    accepted = 0
    for step in range(proposal_count):
        fast_selected, fast_suffix = _proposal_draws(fast_rng, 1, candidate_budget)
        scalar_selected, scalar_suffix = _proposal_draws(
            scalar_rng, 1, candidate_budget
        )
        if (
            not np.array_equal(fast_selected, scalar_selected)
            or not np.array_equal(fast_suffix, scalar_suffix)
            or fast_rng.snapshot() != scalar_rng.snapshot()
        ):
            raise PredictionV2StructuralPortfolioExecutionError(
                f"reference_preflight_proposal_rng_disagreement:{step}"
            )
        selected_index = int(scalar_selected[0])
        suffix_position = int(scalar_suffix[0])
        outgoing_rank = int(scalar_permutation[selected_index])
        incoming_rank = int(scalar_permutation[suffix_position])
        proposed_ranks = scalar_permutation[:candidate_budget].copy()
        proposed_ranks[selected_index] = incoming_rank
        proposed_stats, _, _, _ = _scalar_stats(proposed_ranks, tables)
        scalar_accept = strictly_dominates(proposed_stats, scalar_stats) or (
            proposed_stats == scalar_stats and incoming_rank < outgoing_rank
        )
        if scalar_accept:
            scalar_permutation[selected_index], scalar_permutation[suffix_position] = (
                scalar_permutation[suffix_position],
                scalar_permutation[selected_index],
            )
            (
                scalar_stats,
                scalar_singletons,
                scalar_pairs,
                scalar_histogram,
            ) = _scalar_stats(scalar_permutation[:candidate_budget], tables)
        fast_result = _run_proposal_block_kernel(
            fast_permutation,
            fast_singletons,
            fast_pairs,
            fast_histogram,
            fast_stats.singleton_square_sum,
            fast_stats.pair_square_sum,
            fast_stats.minimum_replacement_distance,
            fast_stats.sum_pairwise_replacement_distance,
            fast_selected,
            fast_suffix,
            tables.numbers,
            tables.masks,
            tables.pairs,
            candidate_budget,
        )
        fast_accept = int(fast_result[0]) == 1
        fast_stats = _stats_tuple(*fast_result[1:])
        if scalar_accept != fast_accept:
            raise PredictionV2StructuralPortfolioExecutionError(
                f"reference_preflight_accept_disagreement:{step}"
            )
        accepted += int(fast_accept)
        _require_state_equal(
            fast_permutation,
            fast_stats,
            fast_singletons,
            fast_pairs,
            fast_histogram,
            scalar_permutation,
            scalar_stats,
            scalar_singletons,
            scalar_pairs,
            scalar_histogram,
            candidate_budget,
            step=step,
        )
        trace.update(
            json.dumps(
                {
                    "step": step,
                    "selected_index": selected_index,
                    "suffix_position": suffix_position,
                    "outgoing_rank": outgoing_rank,
                    "incoming_rank": incoming_rank,
                    "accepted": fast_accept,
                    "stats": fast_stats.to_dict(),
                    "rng": fast_rng.snapshot(),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
    return {
        "status": "PASS",
        "island_index": 0,
        "proposal_count": proposal_count,
        "accepted_move_count": accepted,
        "trace_sha256": trace.hexdigest(),
        "final_stats": fast_stats.to_dict(),
        "final_rng": fast_rng.snapshot(),
    }


def _require_state_equal(
    fast_permutation: np.ndarray,
    fast_stats: StructuralStats,
    fast_singletons: np.ndarray,
    fast_pairs: np.ndarray,
    fast_histogram: np.ndarray,
    scalar_permutation: np.ndarray,
    scalar_stats: StructuralStats,
    scalar_singletons: np.ndarray,
    scalar_pairs: np.ndarray,
    scalar_histogram: np.ndarray,
    candidate_budget: int,
    *,
    step: int,
) -> None:
    if (
        fast_stats != scalar_stats
        or not np.array_equal(fast_singletons, scalar_singletons)
        or not np.array_equal(fast_pairs, scalar_pairs)
        or not np.array_equal(fast_histogram, scalar_histogram)
        or not np.array_equal(
            np.sort(fast_permutation[:candidate_budget]),
            np.sort(scalar_permutation[:candidate_budget]),
        )
    ):
        raise PredictionV2StructuralPortfolioExecutionError(
            f"reference_preflight_state_disagreement:{step}"
        )


def strictly_dominates(left: StructuralStats, right: StructuralStats) -> bool:
    no_worse = (
        left.singleton_square_sum <= right.singleton_square_sum
        and left.pair_square_sum <= right.pair_square_sum
        and left.minimum_replacement_distance >= right.minimum_replacement_distance
        and left.sum_pairwise_replacement_distance
        >= right.sum_pairwise_replacement_distance
    )
    return no_worse and left != right


def _child_identity(
    *, source_set_digest: str, kind: str, index: int, settings: ExecutionSettings
) -> str:
    return canonical_digest(
        {
            "execution_contract_digest": UPSTREAM_EXECUTION_CONTRACT_DIGEST,
            "source_set_digest": source_set_digest,
            "kind": kind,
            "index": index,
            "candidate_budget": settings.candidate_budget,
            "proposals_per_island": settings.proposals_per_island,
            "null_replicate_count": settings.null_replicate_count,
        },
        domain="dehps.prediction-v2.structural-portfolio-child.v1",
    )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


def _write_npz(path: Path, **arrays: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temporary.open("wb") as handle:
        np.savez(handle, **arrays)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _checkpoint_index(
    *,
    checkpoint_dir: Path,
    source_set_digest: str,
    settings: ExecutionSettings,
) -> dict[str, Any]:
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    path = checkpoint_dir / "checkpoint-index.json"
    expected = {
        "schema_version": "dehps-prediction-v2-structural-checkpoint-index.v1",
        "execution_contract_digest": UPSTREAM_EXECUTION_CONTRACT_DIGEST,
        "source_set_digest": source_set_digest,
        "settings": {
            "candidate_budget": settings.candidate_budget,
            "island_count": settings.island_count,
            "proposals_per_island": settings.proposals_per_island,
            "null_replicate_count": settings.null_replicate_count,
            "null_shard_size": settings.null_shard_size,
        },
        "islands": [
            {
                "index": index,
                "identity": _child_identity(
                    source_set_digest=source_set_digest,
                    kind="island",
                    index=index,
                    settings=settings,
                ),
            }
            for index in range(settings.island_count)
        ],
        "null_shards": [
            {
                "index": index,
                "identity": _child_identity(
                    source_set_digest=source_set_digest,
                    kind="null-shard",
                    index=index,
                    settings=settings,
                ),
            }
            for index in range(settings.null_shard_count)
        ],
    }
    if path.exists():
        observed = json.loads(path.read_text(encoding="utf-8"))
        if observed != expected:
            raise PredictionV2StructuralPortfolioExecutionError(
                "checkpoint_index_identity_changed"
            )
        return observed
    _write_json(path, expected)
    return expected


def _island_paths(checkpoint_dir: Path, identity: str) -> tuple[Path, Path]:
    base = checkpoint_dir / "islands" / identity
    return base / "partial.npz", base / "result.json"


def _null_result_path(checkpoint_dir: Path, identity: str) -> Path:
    return checkpoint_dir / "null-shards" / identity / "result.json"


def _load_partial_island(
    path: Path, seed: bytes, identity: str
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    StructuralStats,
    CounterRng,
    int,
    int,
]:
    with np.load(path, allow_pickle=False) as state:
        if str(state["identity"].item()) != identity:
            raise PredictionV2StructuralPortfolioExecutionError(
                "partial_island_identity_changed"
            )
        rng = CounterRng.restore(
            seed,
            {
                "counter": int(state["rng_counter"].item()),
                "words": [int(item) for item in state["rng_words"]],
                "cursor": int(state["rng_cursor"].item()),
            },
        )
        stats = StructuralStats(
            singleton_square_sum=int(state["singleton_square_sum"].item()),
            pair_square_sum=int(state["pair_square_sum"].item()),
            minimum_replacement_distance=int(state["minimum_distance"].item()),
            sum_pairwise_replacement_distance=int(state["distance_sum"].item()),
        )
        return (
            state["permutation"].copy(),
            state["singleton_counts"].copy(),
            state["pair_counts"].copy(),
            state["distance_histogram"].copy(),
            stats,
            rng,
            int(state["proposal_index"].item()),
            int(state["accepted_move_count"].item()),
        )


def _save_partial_island(
    path: Path,
    *,
    identity: str,
    permutation: np.ndarray,
    singleton_counts: np.ndarray,
    pair_counts: np.ndarray,
    distance_histogram: np.ndarray,
    stats: StructuralStats,
    rng: CounterRng,
    proposal_index: int,
    accepted_move_count: int,
) -> None:
    rng_state = rng.snapshot()
    _write_npz(
        path,
        identity=np.array(identity),
        permutation=permutation,
        singleton_counts=singleton_counts,
        pair_counts=pair_counts,
        distance_histogram=distance_histogram,
        singleton_square_sum=np.int64(stats.singleton_square_sum),
        pair_square_sum=np.int64(stats.pair_square_sum),
        minimum_distance=np.int64(stats.minimum_replacement_distance),
        distance_sum=np.int64(stats.sum_pairwise_replacement_distance),
        rng_counter=np.uint64(rng_state["counter"]),
        rng_words=np.asarray(rng_state["words"], dtype=np.uint64),
        rng_cursor=np.uint8(rng_state["cursor"]),
        proposal_index=np.int64(proposal_index),
        accepted_move_count=np.int64(accepted_move_count),
    )


def _run_island_child(args: tuple[Any, ...]) -> dict[str, Any]:
    (
        island_index,
        identity,
        checkpoint_dir_text,
        settings,
    ) = args
    if _WORKER_TABLES is None:
        raise PredictionV2StructuralPortfolioExecutionError(
            "worker_universe_tables_not_initialized"
        )
    tables = _WORKER_TABLES
    checkpoint_dir = Path(checkpoint_dir_text)
    partial_path, result_path = _island_paths(checkpoint_dir, identity)
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["restored_completed"] = True
        return result
    rng_seed = hashlib.sha256(
        f"{OPTIMIZER_ROOT_SEED_HEX}|island|{island_index:08d}".encode("ascii")
    ).digest()
    if partial_path.exists():
        (
            permutation,
            singleton_counts,
            pair_counts,
            histogram,
            stats,
            rng,
            proposal_index,
            accepted_move_count,
        ) = _load_partial_island(partial_path, rng_seed, identity)
        resumed_from_proposal = proposal_index
    else:
        rng = CounterRng(rng_seed)
        permutation = _initialize_permutation_kernel(
            _initialization_draws(rng, settings.candidate_budget)
        )
        singleton_counts, pair_counts, histogram, stats = _state_from_permutation(
            permutation, settings.candidate_budget, tables
        )
        proposal_index = 0
        accepted_move_count = 0
        resumed_from_proposal = 0
    while proposal_index < settings.proposals_per_island:
        block_count = min(
            settings.checkpoint_boundary_proposals,
            settings.proposals_per_island - proposal_index,
        )
        selected, suffix = _proposal_draws(rng, block_count, settings.candidate_budget)
        result = _run_proposal_block_kernel(
            permutation,
            singleton_counts,
            pair_counts,
            histogram,
            stats.singleton_square_sum,
            stats.pair_square_sum,
            stats.minimum_replacement_distance,
            stats.sum_pairwise_replacement_distance,
            selected,
            suffix,
            tables.numbers,
            tables.masks,
            tables.pairs,
            settings.candidate_budget,
        )
        accepted_move_count += int(result[0])
        stats = _stats_tuple(*result[1:])
        proposal_index += block_count
        _save_partial_island(
            partial_path,
            identity=identity,
            permutation=permutation,
            singleton_counts=singleton_counts,
            pair_counts=pair_counts,
            distance_histogram=histogram,
            stats=stats,
            rng=rng,
            proposal_index=proposal_index,
            accepted_move_count=accepted_move_count,
        )
    expected_distance_sum = (
        6 * settings.candidate_budget * (settings.candidate_budget - 1) // 2
        - (stats.singleton_square_sum - 6 * settings.candidate_budget) // 2
    )
    if stats.sum_pairwise_replacement_distance != expected_distance_sum:
        raise PredictionV2StructuralPortfolioExecutionError(
            f"island_distance_identity_changed:{island_index}"
        )
    payload = {
        "island_index": island_index,
        "child_identity": identity,
        "status": "COMPLETE",
        "proposals_executed": settings.proposals_per_island,
        "accepted_move_count": accepted_move_count,
        "resumed_from_proposal": resumed_from_proposal,
        "restored_completed": False,
        "selected_ranks": sorted(
            int(item) for item in permutation[: settings.candidate_budget]
        ),
        "stats": stats.to_dict(),
        "rng_final": rng.snapshot(),
    }
    _write_json(result_path, payload)
    return payload


def _run_null_shard_child(args: tuple[Any, ...]) -> dict[str, Any]:
    shard_index, identity, checkpoint_dir_text, settings = args
    if _WORKER_TABLES is None:
        raise PredictionV2StructuralPortfolioExecutionError(
            "worker_universe_tables_not_initialized"
        )
    tables = _WORKER_TABLES
    result_path = _null_result_path(Path(checkpoint_dir_text), identity)
    if result_path.exists():
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        payload["restored_completed"] = True
        return payload
    start = shard_index * settings.null_shard_size
    stop = min(start + settings.null_shard_size, settings.null_replicate_count)
    replicates: list[dict[str, Any]] = []
    for replicate_index in range(start, stop):
        rng = CounterRng.from_root(NULL_ROOT_SEED_HEX, "replicate", replicate_index)
        permutation = _initialize_permutation_kernel(
            _initialization_draws(rng, settings.candidate_budget)
        )
        stats, _, _, _ = structural_stats(
            permutation[: settings.candidate_budget], tables
        )
        replicates.append(
            {
                "replicate_index": replicate_index,
                "stats": stats.to_dict(),
                "rng_final": rng.snapshot(),
            }
        )
    payload = {
        "shard_index": shard_index,
        "child_identity": identity,
        "status": "COMPLETE",
        "start_replicate": start,
        "stop_replicate": stop,
        "replicate_count": stop - start,
        "restored_completed": False,
        "replicates": replicates,
    }
    _write_json(result_path, payload)
    return payload


def _resident_bytes_for_pids(pids: Sequence[int]) -> int:
    page_size = os.sysconf("SC_PAGE_SIZE")
    total = 0
    for pid in pids:
        try:
            rollup = Path(f"/proc/{pid}/smaps_rollup").read_text(encoding="ascii")
            pss_line = next(
                line for line in rollup.splitlines() if line.startswith("Pss:")
            )
            total += int(pss_line.split()[1]) * 1024
        except (OSError, StopIteration, IndexError, ValueError):
            try:
                fields = Path(f"/proc/{pid}/statm").read_text(encoding="ascii").split()
                total += int(fields[1]) * page_size
            except (OSError, IndexError, ValueError):
                continue
    return total


def _run_parallel_children(
    *,
    function: Any,
    arguments: Sequence[tuple[Any, ...]],
    workers: int,
    wall_clock_limit_seconds: int,
    resident_memory_limit_bytes: int,
) -> list[dict[str, Any]]:
    if not arguments:
        return []
    context = multiprocessing.get_context("fork")
    executor = ProcessPoolExecutor(
        max_workers=min(workers, len(arguments)), mp_context=context
    )
    started = time.monotonic()
    futures = [executor.submit(function, item) for item in arguments]
    pending = set(futures)
    try:
        while pending:
            elapsed = time.monotonic() - started
            if elapsed > wall_clock_limit_seconds:
                raise PredictionV2StructuralPortfolioExecutionError(
                    "structural_execution_phase_timeout"
                )
            done, pending = wait(
                pending,
                timeout=min(0.5, wall_clock_limit_seconds - elapsed),
                return_when=FIRST_COMPLETED,
            )
            processes = getattr(executor, "_processes", {})
            pids = [os.getpid(), *(process.pid for process in processes.values())]
            if _resident_bytes_for_pids(pids) > resident_memory_limit_bytes:
                raise PredictionV2StructuralPortfolioExecutionError(
                    "structural_execution_resident_memory_limit_exceeded"
                )
            for future in done:
                future.result()
        results = [future.result() for future in futures]
    except BaseException:
        for future in futures:
            future.cancel()
        for process in getattr(executor, "_processes", {}).values():
            process.terminate()
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    executor.shutdown(wait=True)
    return results


def _stats_from_dict(payload: Mapping[str, Any]) -> StructuralStats:
    return StructuralStats(
        singleton_square_sum=int(payload["singleton_square_sum"]),
        pair_square_sum=int(payload["pair_square_sum"]),
        minimum_replacement_distance=int(payload["minimum_replacement_distance"]),
        sum_pairwise_replacement_distance=int(
            payload["sum_pairwise_replacement_distance"]
        ),
    )


def _build_result_artifacts(
    *,
    source_contract: Mapping[str, Any],
    preregistration_execution: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    execution_handoff: Mapping[str, Any],
    preregistration_completion: Mapping[str, Any],
    tables: UniverseTables,
    settings: ExecutionSettings,
    preflight: Mapping[str, Any],
    island_results: Sequence[Mapping[str, Any]],
    null_shards: Sequence[Mapping[str, Any]],
) -> StructuralPortfolioExecutionRun:
    ordered_islands = sorted(island_results, key=lambda item: int(item["island_index"]))
    null_replicates = sorted(
        (replicate for shard in null_shards for replicate in shard["replicates"]),
        key=lambda item: int(item["replicate_index"]),
    )
    if (
        len(ordered_islands) != settings.island_count
        or len(null_replicates) != settings.null_replicate_count
    ):
        raise PredictionV2StructuralPortfolioExecutionError(
            "structural_execution_result_cardinality_changed"
        )
    canonical_islands = [
        {
            "island_index": int(item["island_index"]),
            "child_identity": str(item["child_identity"]),
            "status": str(item["status"]),
            "proposals_executed": int(item["proposals_executed"]),
            "accepted_move_count": int(item["accepted_move_count"]),
            "selected_ranks": [int(rank) for rank in item["selected_ranks"]],
            "stats": dict(item["stats"]),
            "rng_final": dict(item["rng_final"]),
        }
        for item in ordered_islands
    ]
    null_stats = [_stats_from_dict(item["stats"]) for item in null_replicates]
    selection_rows: list[dict[str, Any]] = []
    for island in ordered_islands:
        candidate = _stats_from_dict(island["stats"])
        dominates_count = sum(
            strictly_dominates(candidate, item) for item in null_stats
        )
        dominated_by_count = sum(
            strictly_dominates(item, candidate) for item in null_stats
        )
        selection_rows.append(
            {
                "island_index": int(island["island_index"]),
                "strictly_dominated_null_count": dominates_count,
                "null_strictly_dominating_count": dominated_by_count,
                "stats": candidate.to_dict(),
                "selected_ranks": list(island["selected_ranks"]),
            }
        )
    selected = min(
        selection_rows,
        key=lambda item: (
            -int(item["strictly_dominated_null_count"]),
            int(item["null_strictly_dominating_count"]),
            -int(item["stats"]["minimum_replacement_distance"]),
            tuple(int(rank) for rank in item["selected_ranks"]),
        ),
    )
    selected_stats = _stats_from_dict(selected["stats"])
    gate_pass = (
        selected_stats.minimum_replacement_distance
        >= REQUIRED_MINIMUM_REPLACEMENT_DISTANCE
        and int(selected["strictly_dominated_null_count"])
        >= MINIMUM_STRICTLY_DOMINATED_NULLS
        and int(selected["null_strictly_dominating_count"])
        <= MAXIMUM_NULLS_DOMINATING_CANDIDATE
    )
    joint_failure_numerator = (
        1
        + settings.null_replicate_count
        - int(selected["strictly_dominated_null_count"])
    )
    joint_failure_cross_product_pass = (
        joint_failure_numerator * 20 <= settings.null_replicate_count + 1
    )
    if settings.is_production() and gate_pass != joint_failure_cross_product_pass:
        raise PredictionV2StructuralPortfolioExecutionError(
            "structural_gate_equivalence_changed"
        )
    parents = [
        str(source_contract["artifact_digest"]),
        str(preregistration_execution["artifact_digest"]),
        str(preregistration["artifact_digest"]),
        str(execution_handoff["artifact_digest"]),
        str(preregistration_completion["artifact_digest"]),
    ]
    optimizer_index = _artifact(
        {
            "status": "COMPLETE",
            "optimizer": "DETERMINISTIC_PARETO_PREFIX_EXCHANGE_V1",
            "candidate_budget": settings.candidate_budget,
            "island_count": settings.island_count,
            "proposals_per_island": settings.proposals_per_island,
            "total_proposals_executed": (
                settings.island_count * settings.proposals_per_island
            ),
            "accepted_move_count": sum(
                int(item["accepted_move_count"]) for item in canonical_islands
            ),
            "reference_preflight": dict(preflight),
            "checkpoint_resume_policy": (
                "MATCHING_COMPLETED_CHILD_DIRECT_SKIP_WITHOUT_REGENERATION"
            ),
            "islands": canonical_islands,
            "parent_digests": parents,
        },
        schema_version="dehps-prediction-v2-structural-optimizer-index.v1",
        artifact_type="prediction_v2_structural_optimizer_result_index",
        domain="dehps.prediction-v2.structural-optimizer-index.v1",
    )
    null_comparison = _artifact(
        {
            "status": "COMPLETE",
            "candidate_budget": settings.candidate_budget,
            "replicate_count": settings.null_replicate_count,
            "shard_count": settings.null_shard_count,
            "checkpoint_resume_policy": (
                "MATCHING_COMPLETED_SHARD_DIRECT_SKIP_WITHOUT_REGENERATION"
            ),
            "ordered_replicates": [dict(item) for item in null_replicates],
            "island_comparisons": selection_rows,
            "selected_island_index": int(selected["island_index"]),
            "selected_strictly_dominated_null_count": int(
                selected["strictly_dominated_null_count"]
            ),
            "selected_null_strictly_dominating_count": int(
                selected["null_strictly_dominating_count"]
            ),
            "joint_failure_numerator": joint_failure_numerator,
            "joint_failure_denominator": settings.null_replicate_count + 1,
            "joint_failure_cross_product_pass": joint_failure_cross_product_pass,
            "mechanical_gate_status": "PASS" if gate_pass else "FAIL",
            "gate_semantics": "STRUCTURAL_PERFORMANCE_GATE_NOT_PREDICTIVE_P_VALUE",
            "optimizer_index_digest": optimizer_index["artifact_digest"],
            "parent_digests": [*parents, optimizer_index["artifact_digest"]],
        },
        schema_version="dehps-prediction-v2-structural-null-comparison.v1",
        artifact_type="prediction_v2_structural_same_budget_null_comparison",
        domain="dehps.prediction-v2.structural-null-comparison.v1",
    )
    ranks = [int(item) for item in selected["selected_ranks"]]
    portfolio = _artifact(
        {
            "status": "COMPLETE",
            "candidate_budget": settings.candidate_budget,
            "selected_island_index": int(selected["island_index"]),
            "selected_ranks": ranks,
            "selected_combinations": [
                [int(value) for value in tables.numbers[rank]] for rank in ranks
            ],
            "exact_stats": selected_stats.to_dict(),
            "structural_gate_status": "PASS" if gate_pass else "FAIL",
            "prediction_probability_claim": False,
            "global_optimality_claim": False,
            "optimizer_index_digest": optimizer_index["artifact_digest"],
            "null_comparison_digest": null_comparison["artifact_digest"],
            "parent_digests": [
                *parents,
                optimizer_index["artifact_digest"],
                null_comparison["artifact_digest"],
            ],
        },
        schema_version="dehps-prediction-v2-canonical-structural-portfolio.v1",
        artifact_type="prediction_v2_canonical_b176_structural_portfolio",
        domain="dehps.prediction-v2.canonical-structural-portfolio.v1",
    )
    disposition = (
        "STRUCTURAL_DECISION_SUPPORT_HYPOTHESIS_SUPPORTED_AT_FROZEN_BUDGET_ONLY"
        if gate_pass
        else "STRUCTURAL_DECISION_SUPPORT_HYPOTHESIS_REJECTED_AT_FROZEN_BUDGET_NO_SAME_EXECUTION_RETUNING"
    )
    completion = _artifact(
        {
            "status": "COMPLETE",
            "completion_fact": (
                PREDICTION_V2_STRUCTURAL_PORTFOLIO_EXECUTION_COMPLETION_FACT
            ),
            "structural_disposition": disposition,
            "structural_gate_status": "PASS" if gate_pass else "FAIL",
            "portfolio_digest": portfolio["artifact_digest"],
            "optimizer_index_digest": optimizer_index["artifact_digest"],
            "null_comparison_digest": null_comparison["artifact_digest"],
            "candidate_portfolios_generated": settings.island_count,
            "optimizer_proposals_executed": (
                settings.island_count * settings.proposals_per_island
            ),
            "null_replicates_executed": settings.null_replicate_count,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "formal_historical_folds_executed": 0,
            "bootstrap_children_executed": 0,
            "evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "production_action": "none",
            "next_consumer": (PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY),
            "parent_digests": [
                *parents,
                optimizer_index["artifact_digest"],
                null_comparison["artifact_digest"],
                portfolio["artifact_digest"],
            ],
        },
        schema_version="dehps-prediction-v2-structural-portfolio-execution-completion.v1",
        artifact_type="prediction_v2_structural_portfolio_execution_completion",
        domain="dehps.prediction-v2.structural-portfolio-execution-completion.v1",
    )
    return StructuralPortfolioExecutionRun(
        portfolio=portfolio,
        optimizer_index=optimizer_index,
        null_comparison=null_comparison,
        completion=completion,
    )


def execute_structural_portfolio_program(
    *,
    source_contract: Mapping[str, Any],
    preregistration_execution: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    execution_handoff: Mapping[str, Any],
    preregistration_completion: Mapping[str, Any],
    checkpoint_dir: Path,
    settings: ExecutionSettings = PRODUCTION_SETTINGS,
) -> StructuralPortfolioExecutionRun:
    if (
        preregistration_execution.get("artifact_digest")
        != UPSTREAM_PREREGISTRATION_EXECUTION_DIGEST
        or preregistration.get("artifact_digest") != UPSTREAM_PREREGISTRATION_DIGEST
        or preregistration.get("execution_contract_digest")
        != UPSTREAM_EXECUTION_CONTRACT_DIGEST
        or execution_handoff.get("artifact_digest") != UPSTREAM_EXECUTION_HANDOFF_DIGEST
        or preregistration_completion.get("artifact_digest")
        != UPSTREAM_PREREGISTRATION_COMPLETION_DIGEST
    ):
        raise PredictionV2StructuralPortfolioExecutionError(
            "structural_portfolio_execution_upstream_identity_changed"
        )
    if (
        not settings.is_production()
        and source_contract.get("test_mode_allowed") is not True
    ):
        raise PredictionV2StructuralPortfolioExecutionError(
            "non_production_settings_require_explicit_test_contract"
        )
    if settings.is_production() and (
        settings.island_count * settings.proposals_per_island
        != TOTAL_OPTIMIZER_PROPOSALS
        or settings.null_shard_count != NULL_SHARD_COUNT
    ):
        raise PredictionV2StructuralPortfolioExecutionError(
            "production_structural_workload_changed"
        )
    tables = build_universe_tables()
    global _WORKER_TABLES
    _WORKER_TABLES = tables
    source_set_digest = str(source_contract["source_set_digest"])
    index = _checkpoint_index(
        checkpoint_dir=checkpoint_dir,
        source_set_digest=source_set_digest,
        settings=settings,
    )
    preflight_path = checkpoint_dir / "reference-preflight.json"
    if preflight_path.exists():
        preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    else:
        preflight = run_reference_preflight(
            tables=tables,
            proposal_count=settings.reference_preflight_proposals,
            candidate_budget=settings.candidate_budget,
        )
        _write_json(preflight_path, preflight)
    if preflight.get("status") != "PASS":
        raise PredictionV2StructuralPortfolioExecutionError(
            "structural_reference_preflight_failed"
        )
    island_arguments = [
        (
            int(item["index"]),
            str(item["identity"]),
            str(checkpoint_dir),
            settings,
        )
        for item in index["islands"]
    ]
    island_results = _run_parallel_children(
        function=_run_island_child,
        arguments=island_arguments,
        workers=settings.parallel_workers,
        wall_clock_limit_seconds=settings.optimizer_wall_clock_limit_seconds,
        resident_memory_limit_bytes=settings.resident_memory_limit_bytes,
    )
    null_arguments = [
        (
            int(item["index"]),
            str(item["identity"]),
            str(checkpoint_dir),
            settings,
        )
        for item in index["null_shards"]
    ]
    null_results = _run_parallel_children(
        function=_run_null_shard_child,
        arguments=null_arguments,
        workers=settings.parallel_workers,
        wall_clock_limit_seconds=settings.null_wall_clock_limit_seconds,
        resident_memory_limit_bytes=settings.resident_memory_limit_bytes,
    )
    return _build_result_artifacts(
        source_contract=source_contract,
        preregistration_execution=preregistration_execution,
        preregistration=preregistration,
        execution_handoff=execution_handoff,
        preregistration_completion=preregistration_completion,
        tables=tables,
        settings=settings,
        preflight=preflight,
        island_results=island_results,
        null_shards=null_results,
    )


def replay_structural_portfolio_artifacts(
    *,
    portfolio: Mapping[str, Any],
    optimizer_index: Mapping[str, Any],
    null_comparison: Mapping[str, Any],
    completion: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        portfolio.get("optimizer_index_digest")
        != optimizer_index.get("artifact_digest")
        or portfolio.get("null_comparison_digest")
        != null_comparison.get("artifact_digest")
        or completion.get("portfolio_digest") != portfolio.get("artifact_digest")
        or completion.get("optimizer_index_digest")
        != optimizer_index.get("artifact_digest")
        or completion.get("null_comparison_digest")
        != null_comparison.get("artifact_digest")
        or completion.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY
    ):
        raise PredictionV2StructuralPortfolioExecutionError(
            "structural_portfolio_replay_cross_identity_changed"
        )
    return {
        "schema_version": "dehps-prediction-v2-structural-portfolio-execution-replay.v1",
        "status": "REPLAY_VERIFIED",
        "portfolio_digest": portfolio["artifact_digest"],
        "optimizer_index_digest": optimizer_index["artifact_digest"],
        "null_comparison_digest": null_comparison["artifact_digest"],
        "completion_digest": completion["artifact_digest"],
        "same_registered_content": True,
        "workload_rerun": False,
        "optimizer_proposals_replayed": 0,
        "null_replicates_replayed": 0,
        "historical_rows_read": 0,
        "database_queries_during_replay": 0,
        "evidence_created": False,
        "manual_input_assembly": False,
        "next_consumer": PREDICTION_V2_STRUCTURAL_PORTFOLIO_EVALUATION_TASK_KEY,
    }
