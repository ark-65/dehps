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

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_structural_portfolio_execution import (
    CounterRng,
    UniverseTables,
    build_universe_tables,
    structural_stats,
)

PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY = (
    "prediction-v2-structural-baseline-comparison-execution"
)
PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_CAPABILITY = (
    "prediction_v2_structural_baseline_comparison_execution"
)
PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_COMPLETION_FACT = (
    "prediction-v2-structural-baseline-comparison-execution:COMPLETE"
)
PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/"
    "prediction-v2-structural-baseline-comparison-execution-source-v1.json"
)
PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY = (
    "prediction-v2-structural-baseline-comparison-route-decision"
)

UPSTREAM_PREREGISTRATION_EXECUTION_DIGEST = (
    "6077b744b5f9bc125fa7e4de02d80cbce1cc724b3b7f227050b8024117444998"
)
UPSTREAM_PREREGISTRATION_DIGEST = (
    "296163f61a655179c1b1f28a6f13000510181b2256d4a32f1e4da1e0155f41d9"
)
UPSTREAM_EXECUTION_HANDOFF_DIGEST = (
    "7e8a4d7247f55030f77a74ef620833389dce83658075b2f62ab26f989c5881b0"
)
UPSTREAM_PREREGISTRATION_COMPLETION_DIGEST = (
    "aa409e307accf2b7258ae26b3571e51ca22949b7218eeee9e7215d35e40033f3"
)
CANDIDATE_PORTFOLIO_DIGEST = (
    "df7193046245f073c1d77526ad3e5b98ad6806d7ee566b5dd5833659b3ff7498"
)
CANDIDATE_EVALUATION_EXECUTION_DIGEST = (
    "f17d1a9f7aa19479599f35ce3eacf4847e9100b2548f25c7b848c19d8e02b3df"
)
CANDIDATE_EVALUATION_DECISION_DIGEST = (
    "e467e86bdac0a18d4c21d29aed3d5a41bdaf9ece545988169b13e0056cdf9893"
)

LEGAL_LABEL_COUNT = 33
COMBINATION_SIZE = 6
LEGAL_COMBINATION_COUNT = 1_107_568
PAIR_COUNT = 528
PORTFOLIO_BUDGET = 176
BASELINE_REPLICATES_PER_CLASS = 128
CANDIDATE_CHUNK_SIZE = 256
CANDIDATE_CONSIDERATIONS_PER_REPLICATE = 45_056
CANDIDATE_CONSIDERATIONS_PER_CLASS = 5_767_168
TOTAL_CANDIDATE_CONSIDERATIONS = 17_301_504
MASTER_SEED_HEX = "bbe0440383bfa1b55395ab61a195b0f1956a6d406c78b54ed318e353bdf82c3b"
CANDIDATE_STREAM_DOMAIN = (
    "dehps.prediction-v2.structural-baseline-comparison.candidate-stream.v1"
)
CHECKPOINT_EVERY_PORTFOLIO_STEPS = 16
PARALLEL_WORKERS = 22
WALL_CLOCK_LIMIT_SECONDS = 7_200
RESIDENT_MEMORY_LIMIT_BYTES = 4_294_967_296
REQUIRED_CANDIDATE_DOMINATED_REPLICATES_PER_CLASS = 122
MAXIMUM_BASELINE_REPLICATES_DOMINATING_CANDIDATE_PER_CLASS = 0
SUPPORTED_LABEL = "SUPPORTED_BEYOND_FROZEN_TRANSPARENT_BASELINES"
FAILURE_LABEL = "ARCHIVE_AS_ENGINEERING_EVIDENCE_ONLY"
INVALID_LABEL = "INVALID_EXECUTION_NO_DECISION"
STRICT_DOMINANCE = "NO_WORSE_ON_ALL_FOUR_AND_STRICTLY_BETTER_ON_AT_LEAST_ONE"
CONSTRUCTION_INVARIANT = (
    "DISJOINT_CHUNKS_OF_ONE_WITHOUT_REPLACEMENT_STREAM_PER_REPLICATE"
)
REPETITION_SCAN = "ABSENT_BY_CONSTRUCTION"

BASELINE_CLASSES = (
    "SINGLETON_FIRST_GREEDY_V1",
    "PAIR_FIRST_GREEDY_V1",
    "DISTANCE_FIRST_GREEDY_V1",
)
CLASS_CODES = {class_id: index for index, class_id in enumerate(BASELINE_CLASSES)}
CANDIDATE_STATS = {
    "singleton_square_sum": 33_796,
    "pair_square_sum": 14_152,
    "minimum_replacement_distance": 2,
    "sum_pairwise_replacement_distance": 76_030,
}

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-structural-baseline-comparison-execution-round-77-20260809"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-structural-baseline-comparison-"
    "execution-round-78-20260809"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/"
    "prediction_v2_structural_baseline_comparison_execution.py"
)
_SHARED_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/prediction_v2_structural_portfolio_execution.py"
)
FROZEN_CONTRACT_DIGEST = (
    "535eaacf055cfc745ca08bb3f5c89858b11660bd72f427919f3983b5406b957e"
)


class PredictionV2StructuralBaselineComparisonExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExecutionSettings:
    replicates_per_class: int = BASELINE_REPLICATES_PER_CLASS
    portfolio_budget: int = PORTFOLIO_BUDGET
    candidate_chunk_size: int = CANDIDATE_CHUNK_SIZE
    checkpoint_every_steps: int = CHECKPOINT_EVERY_PORTFOLIO_STEPS
    parallel_workers: int = PARALLEL_WORKERS
    wall_clock_limit_seconds: int = WALL_CLOCK_LIMIT_SECONDS
    resident_memory_limit_bytes: int = RESIDENT_MEMORY_LIMIT_BYTES

    @property
    def considerations_per_replicate(self) -> int:
        return self.portfolio_budget * self.candidate_chunk_size

    @property
    def considerations_per_class(self) -> int:
        return self.considerations_per_replicate * self.replicates_per_class

    @property
    def total_considerations(self) -> int:
        return self.considerations_per_class * len(BASELINE_CLASSES)

    def is_production(self) -> bool:
        return self == PRODUCTION_SETTINGS


PRODUCTION_SETTINGS = ExecutionSettings()


@dataclass(frozen=True)
class StructuralBaselineComparisonExecutionRun:
    result_index: Mapping[str, Any]
    gate_outcome: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.result_index, self.gate_outcome, self.completion


class SparsePartialFisherYates:
    """Lazy partial Fisher-Yates stream; uniqueness follows from the swap law."""

    def __init__(
        self,
        *,
        size: int,
        rng: CounterRng,
        position: int = 0,
        swaps: Mapping[int, int] | None = None,
    ) -> None:
        if size <= 0 or position < 0 or position > size:
            raise PredictionV2StructuralBaselineComparisonExecutionError(
                "partial_fisher_yates_state_invalid"
            )
        self.size = int(size)
        self.rng = rng
        self.position = int(position)
        self.swaps = {int(key): int(value) for key, value in (swaps or {}).items()}

    def draw(self) -> int:
        if self.position >= self.size:
            raise PredictionV2StructuralBaselineComparisonExecutionError(
                "partial_fisher_yates_stream_exhausted"
            )
        index = self.position
        swap_index = index + self.rng.bounded(self.size - index)
        emitted = self.swaps.get(swap_index, swap_index)
        replacement = self.swaps.get(index, index)
        if swap_index != index:
            self.swaps[swap_index] = replacement
        self.swaps.pop(index, None)
        self.position += 1
        return int(emitted)

    def draw_chunk(self, count: int) -> np.ndarray:
        if count <= 0 or self.position + count > self.size:
            raise PredictionV2StructuralBaselineComparisonExecutionError(
                "partial_fisher_yates_chunk_invalid"
            )
        result = np.empty(count, dtype=np.uint32)
        for index in range(count):
            result[index] = self.draw()
        return result

    def snapshot(self) -> dict[str, Any]:
        return {
            "position": self.position,
            "rng": self.rng.snapshot(),
            "swaps": [[key, value] for key, value in self.swaps.items()],
        }


def _replicate_seed(class_id: str, replicate_index: int) -> bytes:
    if class_id not in CLASS_CODES or replicate_index < 0:
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            "replicate_seed_identity_invalid"
        )
    material = (
        f"{MASTER_SEED_HEX.lower()}|{CANDIDATE_STREAM_DOMAIN}|"
        f"{class_id}|{replicate_index:08d}"
    ).encode("ascii")
    return hashlib.sha256(material).digest()


def build_candidate_stream(
    class_id: str,
    replicate_index: int,
    *,
    snapshot: Mapping[str, Any] | None = None,
) -> SparsePartialFisherYates:
    seed = _replicate_seed(class_id, replicate_index)
    if snapshot is None:
        return SparsePartialFisherYates(
            size=LEGAL_COMBINATION_COUNT,
            rng=CounterRng(seed),
        )
    swaps = snapshot.get("swaps")
    if not isinstance(swaps, list):
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            "candidate_stream_snapshot_invalid"
        )
    return SparsePartialFisherYates(
        size=LEGAL_COMBINATION_COUNT,
        position=int(snapshot["position"]),
        rng=CounterRng.restore(seed, snapshot["rng"]),
        swaps={int(item[0]): int(item[1]) for item in swaps},
    )


@njit(cache=True, nogil=True)
def _popcount_u64(value: np.uint64) -> int:
    count = 0
    while value:
        value &= value - np.uint64(1)
        count += 1
    return count


@njit(cache=True, nogil=True)
def _better_tuple(
    class_code: int,
    singleton_value: int,
    pair_value: int,
    minimum_distance: int,
    distance_sum: int,
    best_singleton: int,
    best_pair: int,
    best_minimum_distance: int,
    best_distance_sum: int,
) -> bool:
    if class_code == 0:
        if singleton_value != best_singleton:
            return singleton_value < best_singleton
        if pair_value != best_pair:
            return pair_value < best_pair
        if minimum_distance != best_minimum_distance:
            return minimum_distance > best_minimum_distance
        return distance_sum > best_distance_sum
    if class_code == 1:
        if pair_value != best_pair:
            return pair_value < best_pair
        if singleton_value != best_singleton:
            return singleton_value < best_singleton
        if minimum_distance != best_minimum_distance:
            return minimum_distance > best_minimum_distance
        return distance_sum > best_distance_sum
    if minimum_distance != best_minimum_distance:
        return minimum_distance > best_minimum_distance
    if distance_sum != best_distance_sum:
        return distance_sum > best_distance_sum
    if singleton_value != best_singleton:
        return singleton_value < best_singleton
    return pair_value < best_pair


@njit(cache=True, nogil=True)
def choose_chunk_candidate_kernel(
    class_code: int,
    candidate_ranks: np.ndarray,
    selected_ranks: np.ndarray,
    selected_count: int,
    singleton_counts: np.ndarray,
    pair_counts: np.ndarray,
    singleton_square_sum: int,
    pair_square_sum: int,
    current_minimum_distance: int,
    current_distance_sum: int,
    numbers: np.ndarray,
    masks: np.ndarray,
    pairs: np.ndarray,
) -> tuple[int, int, int, int, int, int]:
    best_position = 0
    best_rank = int(candidate_ranks[0])
    best_singleton = 0
    best_pair = 0
    best_minimum = 0
    best_distance_sum = 0
    for position in range(len(candidate_ranks)):
        rank = int(candidate_ranks[position])
        singleton_value = singleton_square_sum
        for offset in range(6):
            count = int(singleton_counts[int(numbers[rank, offset]) - 1])
            singleton_value += 2 * count + 1
        pair_value = pair_square_sum
        for offset in range(15):
            count = int(pair_counts[int(pairs[rank, offset])])
            pair_value += 2 * count + 1
        distance_sum = current_distance_sum
        candidate_minimum = 6
        candidate_mask = masks[rank]
        for offset in range(selected_count):
            distance = 6 - _popcount_u64(
                candidate_mask & masks[int(selected_ranks[offset])]
            )
            distance_sum += distance
            candidate_minimum = min(candidate_minimum, distance)
        if selected_count == 0:
            minimum_distance = 6
        elif selected_count == 1 or candidate_minimum < current_minimum_distance:
            minimum_distance = candidate_minimum
        else:
            minimum_distance = current_minimum_distance
        if position == 0 or _better_tuple(
            class_code,
            singleton_value,
            pair_value,
            minimum_distance,
            distance_sum,
            best_singleton,
            best_pair,
            best_minimum,
            best_distance_sum,
        ):
            best_position = position
            best_rank = rank
            best_singleton = singleton_value
            best_pair = pair_value
            best_minimum = minimum_distance
            best_distance_sum = distance_sum
    return (
        best_position,
        best_rank,
        best_singleton,
        best_pair,
        best_minimum,
        best_distance_sum,
    )


def _apply_selected_rank(
    *,
    rank: int,
    singleton_counts: np.ndarray,
    pair_counts: np.ndarray,
    tables: UniverseTables,
) -> None:
    for value in tables.numbers[rank]:
        singleton_counts[int(value) - 1] += 1
    for value in tables.pairs[rank]:
        pair_counts[int(value)] += 1


def _stats_dict(
    singleton_square_sum: int,
    pair_square_sum: int,
    minimum_replacement_distance: int,
    sum_pairwise_replacement_distance: int,
) -> dict[str, int]:
    return {
        "singleton_square_sum": int(singleton_square_sum),
        "pair_square_sum": int(pair_square_sum),
        "minimum_replacement_distance": int(minimum_replacement_distance),
        "sum_pairwise_replacement_distance": int(sum_pairwise_replacement_distance),
    }


def _scalar_candidate_metrics(
    *,
    rank: int,
    selected_ranks: Sequence[int],
    singleton_counts: np.ndarray,
    pair_counts: np.ndarray,
    current_stats: Mapping[str, int],
    tables: UniverseTables,
) -> dict[str, int]:
    singleton_value = int(current_stats["singleton_square_sum"])
    for value in tables.numbers[rank]:
        count = int(singleton_counts[int(value) - 1])
        singleton_value += 2 * count + 1
    pair_value = int(current_stats["pair_square_sum"])
    for value in tables.pairs[rank]:
        count = int(pair_counts[int(value)])
        pair_value += 2 * count + 1
    distances = [
        6
        - (int(tables.masks[rank]) & int(tables.masks[int(selected_rank)])).bit_count()
        for selected_rank in selected_ranks
    ]
    if not distances:
        minimum_distance = 6
    elif len(selected_ranks) == 1:
        minimum_distance = min(distances)
    else:
        minimum_distance = min(
            int(current_stats["minimum_replacement_distance"]), min(distances)
        )
    return _stats_dict(
        singleton_value,
        pair_value,
        minimum_distance,
        int(current_stats["sum_pairwise_replacement_distance"]) + sum(distances),
    )


def run_reference_preflight(tables: UniverseTables | None = None) -> dict[str, Any]:
    tables = tables or build_universe_tables()
    selected = np.asarray([0, 127, 8_192, 65_535], dtype=np.uint32)
    candidates = np.asarray(
        [1, 33, 521, 16_384, 70_000, 91_337, 700_000], dtype=np.uint32
    )
    exact, singleton_counts, pair_counts, _ = structural_stats(selected, tables)
    current = exact.to_dict()
    scalar_rows = [
        _scalar_candidate_metrics(
            rank=int(rank),
            selected_ranks=selected.tolist(),
            singleton_counts=singleton_counts,
            pair_counts=pair_counts,
            current_stats=current,
            tables=tables,
        )
        for rank in candidates
    ]
    for class_id, class_code in CLASS_CODES.items():
        chosen = choose_chunk_candidate_kernel(
            class_code,
            candidates,
            selected,
            len(selected),
            singleton_counts,
            pair_counts,
            exact.singleton_square_sum,
            exact.pair_square_sum,
            exact.minimum_replacement_distance,
            exact.sum_pairwise_replacement_distance,
            tables.numbers,
            tables.masks,
            tables.pairs,
        )
        keys = {
            0: (
                "singleton_square_sum",
                "pair_square_sum",
                "minimum_replacement_distance",
                "sum_pairwise_replacement_distance",
            ),
            1: (
                "pair_square_sum",
                "singleton_square_sum",
                "minimum_replacement_distance",
                "sum_pairwise_replacement_distance",
            ),
            2: (
                "minimum_replacement_distance",
                "sum_pairwise_replacement_distance",
                "singleton_square_sum",
                "pair_square_sum",
            ),
        }[class_code]
        directions = {
            "singleton_square_sum": 1,
            "pair_square_sum": 1,
            "minimum_replacement_distance": -1,
            "sum_pairwise_replacement_distance": -1,
        }
        scalar_position = min(
            range(len(scalar_rows)),
            key=lambda index: (
                tuple(directions[key] * scalar_rows[index][key] for key in keys)
                + (index,)
            ),
        )
        compiled_stats = _stats_dict(*chosen[2:])
        if (
            chosen[0] != scalar_position
            or compiled_stats != scalar_rows[scalar_position]
        ):
            raise PredictionV2StructuralBaselineComparisonExecutionError(
                f"baseline_reference_preflight_failed:{class_id}"
            )
    return {
        "schema_version": "dehps-prediction-v2-structural-baseline-reference-preflight.v1",
        "status": "PASS",
        "selected_fixture_count": len(selected),
        "candidate_fixture_count": len(candidates),
        "class_count": len(BASELINE_CLASSES),
        "integer_exact": True,
        "repetition_scan": REPETITION_SCAN,
    }


def _artifact(
    body: Mapping[str, Any],
    *,
    schema_version: str,
    artifact_type: str,
    domain: str,
) -> dict[str, Any]:
    payload = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "artifact_digest": "",
        **dict(body),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _is_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def load_prediction_v2_structural_baseline_comparison_execution_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            f"baseline_comparison_execution_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-prediction-v2-structural-baseline-comparison-execution-source.v1"
        or payload.get("artifact_type")
        != "prediction_v2_structural_baseline_comparison_execution_source"
        or payload.get("contract_key")
        != "PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 405
        or payload.get("research_execution_id") != 326
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 406
        or payload.get("engineering_execution_id") != 327
        or payload.get("registered_children") != 3
        or payload.get("database_queries") != 0
        or payload.get("historical_rows_read") != 0
        or payload.get("new_evidence_created") is not False
        or payload.get("new_model_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or len(entries) != 2
        or not isinstance(frozen, dict)
        or payload.get("frozen_contract_digest") != FROZEN_CONTRACT_DIGEST
        or canonical_digest(
            frozen,
            domain=(
                "dehps.prediction-v2.structural-baseline-comparison-"
                "execution-frozen-contract.v1"
            ),
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain=(
                "dehps.prediction-v2.structural-baseline-comparison-"
                "execution-source-set.v1"
            ),
        )
    ):
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            "baseline_comparison_execution_source_invalid"
        )
    if [entry.get("path") for entry in entries] != [
        _SOURCE_MODULE_PATH,
        _SHARED_SOURCE_MODULE_PATH,
    ] or any(not _is_digest(entry.get("content_sha256")) for entry in entries):
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            "baseline_comparison_execution_source_entries_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_prediction_v2_structural_baseline_comparison_execution_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise PredictionV2StructuralBaselineComparisonExecutionError(
                f"baseline_comparison_execution_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise PredictionV2StructuralBaselineComparisonExecutionError(
                f"baseline_comparison_execution_source_modified:{relative}"
            )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if (
        frozen.get("task_key")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY
        or frozen.get("capability")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_CAPABILITY
        or frozen.get("completion_fact")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_COMPLETION_FACT
        or frozen.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY
        or frozen.get("registered_input_digests")
        != [
            UPSTREAM_PREREGISTRATION_EXECUTION_DIGEST,
            UPSTREAM_PREREGISTRATION_DIGEST,
            UPSTREAM_EXECUTION_HANDOFF_DIGEST,
            UPSTREAM_PREREGISTRATION_COMPLETION_DIGEST,
            CANDIDATE_PORTFOLIO_DIGEST,
            CANDIDATE_EVALUATION_EXECUTION_DIGEST,
            CANDIDATE_EVALUATION_DECISION_DIGEST,
        ]
        or frozen.get("baseline_class_ids") != list(BASELINE_CLASSES)
        or frozen.get("portfolio_budget") != PORTFOLIO_BUDGET
        or frozen.get("replicates_per_class") != BASELINE_REPLICATES_PER_CLASS
        or frozen.get("candidate_chunk_size") != CANDIDATE_CHUNK_SIZE
        or frozen.get("total_candidate_considerations")
        != TOTAL_CANDIDATE_CONSIDERATIONS
        or frozen.get("master_seed_hex") != MASTER_SEED_HEX
        or frozen.get("candidate_stream_domain") != CANDIDATE_STREAM_DOMAIN
        or frozen.get("checkpoint_every_steps") != CHECKPOINT_EVERY_PORTFOLIO_STEPS
        or frozen.get("parallel_workers") != PARALLEL_WORKERS
        or frozen.get("wall_clock_limit_seconds") != WALL_CLOCK_LIMIT_SECONDS
        or frozen.get("resident_memory_limit_bytes") != RESIDENT_MEMORY_LIMIT_BYTES
        or frozen.get("construction_invariant") != CONSTRUCTION_INVARIANT
        or frozen.get("repetition_scan") != REPETITION_SCAN
        or frozen.get("candidate_stats") != CANDIDATE_STATS
        or frozen.get("strict_dominance") != STRICT_DOMINANCE
        or frozen.get("required_candidate_dominated_replicates_per_class")
        != REQUIRED_CANDIDATE_DOMINATED_REPLICATES_PER_CLASS
        or frozen.get("maximum_baseline_replicates_dominating_candidate_per_class")
        != MAXIMUM_BASELINE_REPLICATES_DOMINATING_CANDIDATE_PER_CLASS
        or frozen.get("supported_label") != SUPPORTED_LABEL
        or frozen.get("failure_label") != FAILURE_LABEL
        or frozen.get("invalid_label") != INVALID_LABEL
        or frozen.get("prediction_v2_mode") != "SHADOW_ONLY"
        or frozen.get("prediction_v2_route") != "BASELINE_ONLY"
        or frozen.get("portfolio_activation_authorized") is not False
        or frozen.get("new_evidence_created") is not False
        or frozen.get("new_model_created") is not False
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("p3_authorized") is not False
        or frozen.get("production_action") != "none"
    ):
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            "baseline_comparison_execution_frozen_contract_changed"
        )


def _verify_artifact(payload: Mapping[str, Any], *, domain: str) -> None:
    digest = payload.get("artifact_digest")
    identity = dict(payload)
    identity.pop("artifact_digest", None)
    if not _is_digest(digest) or digest != canonical_digest(identity, domain=domain):
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            "baseline_comparison_execution_artifact_identity_invalid"
        )


def _validate_inputs(
    *,
    preregistration_execution: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    execution_handoff: Mapping[str, Any],
    preregistration_completion: Mapping[str, Any],
    candidate_portfolio: Mapping[str, Any],
    candidate_evaluation_execution: Mapping[str, Any],
    candidate_evaluation_decision: Mapping[str, Any],
    require_registered_identities: bool,
) -> None:
    artifacts = (
        (preregistration_execution, "dehps.research-os.mainline-execution.v1"),
        (
            preregistration,
            "dehps.prediction-v2.structural-baseline-comparison-preregistration.v1",
        ),
        (
            execution_handoff,
            "dehps.prediction-v2.structural-baseline-comparison-execution-handoff.v1",
        ),
        (
            preregistration_completion,
            "dehps.prediction-v2.structural-baseline-comparison-preregistration-completion.v1",
        ),
        (candidate_portfolio, "dehps.prediction-v2.canonical-structural-portfolio.v1"),
        (candidate_evaluation_execution, "dehps.research-os.mainline-execution.v1"),
        (
            candidate_evaluation_decision,
            "dehps.prediction-v2.structural-portfolio-evaluation-decision.v1",
        ),
    )
    for artifact, domain in artifacts:
        _verify_artifact(artifact, domain=domain)
    observed = [str(artifact["artifact_digest"]) for artifact, _ in artifacts]
    if require_registered_identities and observed != [
        UPSTREAM_PREREGISTRATION_EXECUTION_DIGEST,
        UPSTREAM_PREREGISTRATION_DIGEST,
        UPSTREAM_EXECUTION_HANDOFF_DIGEST,
        UPSTREAM_PREREGISTRATION_COMPLETION_DIGEST,
        CANDIDATE_PORTFOLIO_DIGEST,
        CANDIDATE_EVALUATION_EXECUTION_DIGEST,
        CANDIDATE_EVALUATION_DECISION_DIGEST,
    ]:
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            "baseline_comparison_execution_registered_identity_changed"
        )
    program = preregistration.get("program")
    comparison = preregistration.get("comparison_contract")
    if (
        preregistration_execution.get("completion_classification")
        != "VALIDATED_IN_MAINLINE"
        or preregistration_execution.get("completion_fact")
        != "prediction-v2-structural-baseline-comparison-preregistration:COMPLETE"
        or not isinstance(program, dict)
        or [item.get("class_id") for item in program.get("baseline_classes", [])]
        != list(BASELINE_CLASSES)
        or program.get("portfolio_budget") != PORTFOLIO_BUDGET
        or program.get("replicates_per_class") != BASELINE_REPLICATES_PER_CLASS
        or program.get("candidate_chunk_size_per_step") != CANDIDATE_CHUNK_SIZE
        or program.get("total_candidate_considerations")
        != TOTAL_CANDIDATE_CONSIDERATIONS
        or program.get("master_seed_hex") != MASTER_SEED_HEX
        or program.get("candidate_stream_domain") != CANDIDATE_STREAM_DOMAIN
        or program.get("construction_invariant") != CONSTRUCTION_INVARIANT
        or not isinstance(comparison, dict)
        or comparison.get("strict_dominance") != STRICT_DOMINANCE
        or comparison.get("required_candidate_dominated_replicates_per_class")
        != REQUIRED_CANDIDATE_DOMINATED_REPLICATES_PER_CLASS
        or comparison.get("maximum_baseline_replicates_dominating_candidate_per_class")
        != MAXIMUM_BASELINE_REPLICATES_DOMINATING_CANDIDATE_PER_CLASS
        or execution_handoff.get("preregistration_digest")
        != preregistration.get("artifact_digest")
        or execution_handoff.get("comparison_execution_authorized") is not True
        or preregistration_completion.get("preregistration_digest")
        != preregistration.get("artifact_digest")
        or preregistration_completion.get("execution_handoff_digest")
        != execution_handoff.get("artifact_digest")
        or candidate_portfolio.get("candidate_budget") != PORTFOLIO_BUDGET
        or len(candidate_portfolio.get("selected_ranks", [])) != PORTFOLIO_BUDGET
        or candidate_portfolio.get("exact_stats") != CANDIDATE_STATS
        or candidate_evaluation_execution.get("completion_classification")
        != "VALIDATED_IN_MAINLINE"
        or candidate_evaluation_decision.get("selected_stats") != CANDIDATE_STATS
        or candidate_evaluation_decision.get("decision_usefulness_claim") is not False
        or candidate_evaluation_decision.get("prediction_probability_claim")
        is not False
    ):
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            "baseline_comparison_execution_parent_consistency_invalid"
        )


def _checkpoint_identity(source_set_digest: str, settings: ExecutionSettings) -> str:
    return canonical_digest(
        {
            "source_set_digest": source_set_digest,
            "baseline_classes": list(BASELINE_CLASSES),
            "replicates_per_class": settings.replicates_per_class,
            "portfolio_budget": settings.portfolio_budget,
            "candidate_chunk_size": settings.candidate_chunk_size,
            "master_seed_hex": MASTER_SEED_HEX,
            "candidate_stream_domain": CANDIDATE_STREAM_DOMAIN,
        },
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-checkpoint-identity.v1"
        ),
    )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _checkpoint_digest(payload: Mapping[str, Any], *, domain: str) -> str:
    identity = dict(payload)
    identity.pop("checkpoint_digest", None)
    return canonical_digest(identity, domain=domain)


def _replicate_paths(
    checkpoint_dir: Path, class_id: str, replicate_index: int
) -> tuple[Path, Path]:
    base = checkpoint_dir / "replicates" / class_id / f"{replicate_index:03d}"
    return base / "partial.json", base / "result.json"


def _initial_state() -> dict[str, Any]:
    return {
        "completed_steps": 0,
        "selected_ranks": [],
        "singleton_counts": [0] * LEGAL_LABEL_COUNT,
        "pair_counts": [0] * PAIR_COUNT,
        "stats": _stats_dict(0, 0, COMBINATION_SIZE, 0),
    }


_WORKER_TABLES: UniverseTables | None = None


def _run_replicate_child(arguments: tuple[Any, ...]) -> dict[str, Any]:
    class_id, replicate_index, checkpoint_dir_text, identity, settings = arguments
    tables = _WORKER_TABLES
    if tables is None:
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            "baseline_comparison_worker_tables_unavailable"
        )
    checkpoint_dir = Path(checkpoint_dir_text)
    partial_path, result_path = _replicate_paths(
        checkpoint_dir, str(class_id), int(replicate_index)
    )
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if (
            result.get("checkpoint_digest")
            != _checkpoint_digest(
                result,
                domain=(
                    "dehps.prediction-v2.structural-baseline-"
                    "replicate-result-checkpoint.v1"
                ),
            )
            or result.get("checkpoint_identity") != identity
            or result.get("class_id") != class_id
            or result.get("replicate_index") != replicate_index
            or result.get("candidate_considerations")
            != settings.considerations_per_replicate
            or len(result.get("selected_ranks", [])) != settings.portfolio_budget
            or result.get("seed_digest")
            != _replicate_seed(str(class_id), int(replicate_index)).hex()
            or result.get("construction_invariant") != CONSTRUCTION_INVARIANT
            or result.get("repetition_scan") != REPETITION_SCAN
        ):
            raise PredictionV2StructuralBaselineComparisonExecutionError(
                "baseline_comparison_completed_checkpoint_identity_changed"
            )
        return result
    state = _initial_state()
    stream_snapshot = None
    if partial_path.exists():
        partial = json.loads(partial_path.read_text(encoding="utf-8"))
        if (
            partial.get("checkpoint_digest")
            != _checkpoint_digest(
                partial,
                domain=(
                    "dehps.prediction-v2.structural-baseline-"
                    "replicate-partial-checkpoint.v1"
                ),
            )
            or partial.get("checkpoint_identity") != identity
            or partial.get("class_id") != class_id
            or partial.get("replicate_index") != replicate_index
        ):
            raise PredictionV2StructuralBaselineComparisonExecutionError(
                "baseline_comparison_partial_checkpoint_identity_changed"
            )
        state = dict(partial["state"])
        stream_snapshot = partial["candidate_stream"]
    stream = build_candidate_stream(
        str(class_id), int(replicate_index), snapshot=stream_snapshot
    )
    selected = np.empty(settings.portfolio_budget, dtype=np.uint32)
    selected_values = [int(value) for value in state["selected_ranks"]]
    selected[: len(selected_values)] = selected_values
    singleton_counts = np.asarray(state["singleton_counts"], dtype=np.int32)
    pair_counts = np.asarray(state["pair_counts"], dtype=np.int32)
    stats = {key: int(value) for key, value in state["stats"].items()}
    completed_steps = int(state["completed_steps"])
    if (
        completed_steps != len(selected_values)
        or stream.position != completed_steps * settings.candidate_chunk_size
    ):
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            "baseline_comparison_partial_checkpoint_position_changed"
        )
    class_code = CLASS_CODES[str(class_id)]
    for step in range(completed_steps, settings.portfolio_budget):
        candidates = stream.draw_chunk(settings.candidate_chunk_size)
        chosen = choose_chunk_candidate_kernel(
            class_code,
            candidates,
            selected,
            step,
            singleton_counts,
            pair_counts,
            stats["singleton_square_sum"],
            stats["pair_square_sum"],
            stats["minimum_replacement_distance"],
            stats["sum_pairwise_replacement_distance"],
            tables.numbers,
            tables.masks,
            tables.pairs,
        )
        rank = int(chosen[1])
        selected[step] = rank
        _apply_selected_rank(
            rank=rank,
            singleton_counts=singleton_counts,
            pair_counts=pair_counts,
            tables=tables,
        )
        stats = _stats_dict(*chosen[2:])
        completed_steps = step + 1
        if (
            completed_steps % settings.checkpoint_every_steps == 0
            and completed_steps < settings.portfolio_budget
        ):
            partial_payload = {
                "schema_version": (
                    "dehps-prediction-v2-structural-baseline-replicate-checkpoint.v1"
                ),
                "checkpoint_digest": "",
                "checkpoint_identity": identity,
                "class_id": class_id,
                "replicate_index": replicate_index,
                "state": {
                    "completed_steps": completed_steps,
                    "selected_ranks": selected[:completed_steps].tolist(),
                    "singleton_counts": singleton_counts.tolist(),
                    "pair_counts": pair_counts.tolist(),
                    "stats": stats,
                },
                "candidate_stream": stream.snapshot(),
                "repetition_scan": REPETITION_SCAN,
            }
            partial_payload["checkpoint_digest"] = _checkpoint_digest(
                partial_payload,
                domain=(
                    "dehps.prediction-v2.structural-baseline-"
                    "replicate-partial-checkpoint.v1"
                ),
            )
            _write_json(partial_path, partial_payload)
    exact, _, _, _ = structural_stats(selected, tables)
    exact_stats = exact.to_dict()
    if exact_stats != stats:
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            "baseline_comparison_incremental_metric_mismatch"
        )
    result = {
        "schema_version": (
            "dehps-prediction-v2-structural-baseline-replicate-result.v1"
        ),
        "checkpoint_identity": identity,
        "checkpoint_digest": "",
        "class_id": class_id,
        "replicate_index": replicate_index,
        "seed_digest": _replicate_seed(str(class_id), int(replicate_index)).hex(),
        "candidate_considerations": settings.considerations_per_replicate,
        "selected_ranks": selected.tolist(),
        "stats": exact_stats,
        "construction_invariant": CONSTRUCTION_INVARIANT,
        "repetition_scan": REPETITION_SCAN,
    }
    result["checkpoint_digest"] = _checkpoint_digest(
        result,
        domain=(
            "dehps.prediction-v2.structural-baseline-replicate-result-checkpoint.v1"
        ),
    )
    _write_json(result_path, result)
    if partial_path.exists():
        partial_path.unlink()
    return result


def _resident_bytes_for_pids(pids: Sequence[int]) -> int:
    total = 0
    page_size = os.sysconf("SC_PAGE_SIZE")
    for pid in pids:
        try:
            rollup = Path(f"/proc/{pid}/smaps_rollup").read_text(encoding="ascii")
            line = next(item for item in rollup.splitlines() if item.startswith("Pss:"))
            total += int(line.split()[1]) * 1024
        except (OSError, StopIteration, IndexError, ValueError):
            try:
                fields = Path(f"/proc/{pid}/statm").read_text(encoding="ascii").split()
                total += int(fields[1]) * page_size
            except (OSError, IndexError, ValueError):
                continue
    return total


def _run_parallel_replicates(
    *, arguments: Sequence[tuple[Any, ...]], settings: ExecutionSettings
) -> list[dict[str, Any]]:
    if not arguments:
        return []
    context = multiprocessing.get_context("fork")
    executor = ProcessPoolExecutor(
        max_workers=min(settings.parallel_workers, len(arguments)),
        mp_context=context,
    )
    started = time.monotonic()
    futures = [executor.submit(_run_replicate_child, item) for item in arguments]
    pending = set(futures)
    try:
        while pending:
            elapsed = time.monotonic() - started
            if elapsed > settings.wall_clock_limit_seconds:
                raise PredictionV2StructuralBaselineComparisonExecutionError(
                    "baseline_comparison_execution_timeout"
                )
            done, pending = wait(
                pending,
                timeout=min(0.5, settings.wall_clock_limit_seconds - elapsed),
                return_when=FIRST_COMPLETED,
            )
            processes = getattr(executor, "_processes", {})
            pids = [os.getpid(), *(process.pid for process in processes.values())]
            if _resident_bytes_for_pids(pids) > settings.resident_memory_limit_bytes:
                raise PredictionV2StructuralBaselineComparisonExecutionError(
                    "baseline_comparison_execution_memory_limit_exceeded"
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


def _dominates(left: Mapping[str, int], right: Mapping[str, int]) -> bool:
    comparisons = (
        int(left["singleton_square_sum"]) <= int(right["singleton_square_sum"]),
        int(left["pair_square_sum"]) <= int(right["pair_square_sum"]),
        int(left["minimum_replacement_distance"])
        >= int(right["minimum_replacement_distance"]),
        int(left["sum_pairwise_replacement_distance"])
        >= int(right["sum_pairwise_replacement_distance"]),
    )
    strict = (
        int(left["singleton_square_sum"]) < int(right["singleton_square_sum"])
        or int(left["pair_square_sum"]) < int(right["pair_square_sum"])
        or int(left["minimum_replacement_distance"])
        > int(right["minimum_replacement_distance"])
        or int(left["sum_pairwise_replacement_distance"])
        > int(right["sum_pairwise_replacement_distance"])
    )
    return all(comparisons) and strict


def _class_summaries(
    rows: Sequence[Mapping[str, Any]],
    candidate_stats: Mapping[str, int],
    *,
    expected_replicates_per_class: int,
    expected_considerations_per_replicate: int,
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for class_id in BASELINE_CLASSES:
        class_rows = [row for row in rows if row["class_id"] == class_id]
        if (
            len(class_rows) != expected_replicates_per_class
            or sorted(int(row["replicate_index"]) for row in class_rows)
            != list(range(expected_replicates_per_class))
            or any(
                int(row["candidate_considerations"])
                != expected_considerations_per_replicate
                for row in class_rows
            )
        ):
            raise PredictionV2StructuralBaselineComparisonExecutionError(
                "baseline_comparison_class_rows_missing"
            )
        candidate_dominates = sum(
            _dominates(candidate_stats, row["stats"]) for row in class_rows
        )
        baseline_dominates = sum(
            _dominates(row["stats"], candidate_stats) for row in class_rows
        )
        summaries.append(
            {
                "class_id": class_id,
                "replicate_count": len(class_rows),
                "candidate_considerations": sum(
                    int(row["candidate_considerations"]) for row in class_rows
                ),
                "candidate_dominated_replicate_count": candidate_dominates,
                "candidate_dominance_required": (
                    REQUIRED_CANDIDATE_DOMINATED_REPLICATES_PER_CLASS
                ),
                "baseline_dominating_candidate_count": baseline_dominates,
                "baseline_dominance_maximum": (
                    MAXIMUM_BASELINE_REPLICATES_DOMINATING_CANDIDATE_PER_CLASS
                ),
                "class_gate_pass": (
                    candidate_dominates
                    >= REQUIRED_CANDIDATE_DOMINATED_REPLICATES_PER_CLASS
                    and baseline_dominates
                    <= MAXIMUM_BASELINE_REPLICATES_DOMINATING_CANDIDATE_PER_CLASS
                ),
            }
        )
    return summaries


def _build_result_artifacts(
    *,
    source_contract: Mapping[str, Any],
    preregistration_execution: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    execution_handoff: Mapping[str, Any],
    preregistration_completion: Mapping[str, Any],
    candidate_portfolio: Mapping[str, Any],
    candidate_evaluation_execution: Mapping[str, Any],
    candidate_evaluation_decision: Mapping[str, Any],
    settings: ExecutionSettings,
    preflight: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> StructuralBaselineComparisonExecutionRun:
    ordered_rows = sorted(
        (dict(row) for row in rows),
        key=lambda row: (
            BASELINE_CLASSES.index(row["class_id"]),
            row["replicate_index"],
        ),
    )
    expected_rows = settings.replicates_per_class * len(BASELINE_CLASSES)
    metric_keys = set(CANDIDATE_STATS)
    if (
        len(ordered_rows) != expected_rows
        or sum(int(row["candidate_considerations"]) for row in ordered_rows)
        != settings.total_considerations
        or any(
            row.get("schema_version")
            != "dehps-prediction-v2-structural-baseline-replicate-result.v1"
            or row.get("checkpoint_digest")
            != _checkpoint_digest(
                row,
                domain=(
                    "dehps.prediction-v2.structural-baseline-"
                    "replicate-result-checkpoint.v1"
                ),
            )
            or row.get("class_id") not in BASELINE_CLASSES
            or row.get("seed_digest")
            != _replicate_seed(str(row["class_id"]), int(row["replicate_index"])).hex()
            or len(row.get("selected_ranks", [])) != settings.portfolio_budget
            or set(row.get("stats", {})) != metric_keys
            or row.get("construction_invariant") != CONSTRUCTION_INVARIANT
            or row.get("repetition_scan") != REPETITION_SCAN
            for row in ordered_rows
        )
    ):
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            "baseline_comparison_result_count_invalid"
        )
    summaries = _class_summaries(
        ordered_rows,
        CANDIDATE_STATS,
        expected_replicates_per_class=settings.replicates_per_class,
        expected_considerations_per_replicate=settings.considerations_per_replicate,
    )
    gate_pass = all(item["class_gate_pass"] for item in summaries)
    gate_label = SUPPORTED_LABEL if gate_pass else FAILURE_LABEL
    parents = [
        str(source_contract["artifact_digest"]),
        str(preregistration_execution["artifact_digest"]),
        str(preregistration["artifact_digest"]),
        str(execution_handoff["artifact_digest"]),
        str(preregistration_completion["artifact_digest"]),
        str(candidate_portfolio["artifact_digest"]),
        str(candidate_evaluation_execution["artifact_digest"]),
        str(candidate_evaluation_decision["artifact_digest"]),
    ]
    result_index = _artifact(
        {
            "status": "COMPLETE",
            "baseline_class_ids": list(BASELINE_CLASSES),
            "replicates_per_class": settings.replicates_per_class,
            "portfolio_budget": settings.portfolio_budget,
            "candidate_chunk_size": settings.candidate_chunk_size,
            "candidate_considerations_per_replicate": (
                settings.considerations_per_replicate
            ),
            "candidate_considerations_per_class": settings.considerations_per_class,
            "total_candidate_considerations": settings.total_considerations,
            "candidate_portfolio_digest": candidate_portfolio["artifact_digest"],
            "candidate_stats": dict(CANDIDATE_STATS),
            "ordered_replicates": ordered_rows,
            "class_summaries": summaries,
            "preflight": dict(preflight),
            "construction_invariant": CONSTRUCTION_INVARIANT,
            "repetition_scan": REPETITION_SCAN,
            "parent_digests": parents,
        },
        schema_version=(
            "dehps-prediction-v2-structural-baseline-comparison-result-index.v1"
        ),
        artifact_type="prediction_v2_structural_baseline_comparison_result_index",
        domain=("dehps.prediction-v2.structural-baseline-comparison-result-index.v1"),
    )
    gate_outcome = _artifact(
        {
            "status": "COMPLETE",
            "decision": gate_label,
            "valid_execution": True,
            "candidate_stats": dict(CANDIDATE_STATS),
            "class_summaries": summaries,
            "strict_dominance": STRICT_DOMINANCE,
            "required_candidate_dominated_replicates_per_class": (
                REQUIRED_CANDIDATE_DOMINATED_REPLICATES_PER_CLASS
            ),
            "maximum_baseline_replicates_dominating_candidate_per_class": (
                MAXIMUM_BASELINE_REPLICATES_DOMINATING_CANDIDATE_PER_CLASS
            ),
            "result_index_digest": result_index["artifact_digest"],
            "p_value_claim": False,
            "global_optimality_claim": False,
            "decision_usefulness_claim": False,
            "prediction_probability_claim": False,
            "historical_evidence": "INCONCLUSIVE",
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "portfolio_activation_authorized": False,
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "production_action": "none",
            "repetition_scan": REPETITION_SCAN,
            "parent_digests": [*parents, result_index["artifact_digest"]],
        },
        schema_version=(
            "dehps-prediction-v2-structural-baseline-comparison-gate-outcome.v1"
        ),
        artifact_type="prediction_v2_structural_baseline_comparison_gate_outcome",
        domain=("dehps.prediction-v2.structural-baseline-comparison-gate-outcome.v1"),
    )
    completion = _artifact(
        {
            "status": "COMPLETE",
            "completion_fact": (
                PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_COMPLETION_FACT
            ),
            "result_index_digest": result_index["artifact_digest"],
            "gate_outcome_digest": gate_outcome["artifact_digest"],
            "decision": gate_label,
            "registered_child_count": 3,
            "baseline_replicates_executed": expected_rows,
            "total_candidate_considerations": settings.total_considerations,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "bootstrap_children_executed": 0,
            "new_evidence_created": False,
            "new_model_created": False,
            "candidate_expert_authorized": False,
            "portfolio_activation_authorized": False,
            "promotion_gate_opened": False,
            "p3_authorized": False,
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "next_consumer": (
                PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY
            ),
            "production_action": "none",
            "repetition_scan": REPETITION_SCAN,
            "parent_digests": [
                str(source_contract["artifact_digest"]),
                str(result_index["artifact_digest"]),
                str(gate_outcome["artifact_digest"]),
            ],
        },
        schema_version=(
            "dehps-prediction-v2-structural-baseline-comparison-execution-completion.v1"
        ),
        artifact_type=(
            "prediction_v2_structural_baseline_comparison_execution_completion"
        ),
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-execution-completion.v1"
        ),
    )
    return StructuralBaselineComparisonExecutionRun(
        result_index=result_index,
        gate_outcome=gate_outcome,
        completion=completion,
    )


def execute_structural_baseline_comparison_program(
    *,
    source_contract: Mapping[str, Any],
    preregistration_execution: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    execution_handoff: Mapping[str, Any],
    preregistration_completion: Mapping[str, Any],
    candidate_portfolio: Mapping[str, Any],
    candidate_evaluation_execution: Mapping[str, Any],
    candidate_evaluation_decision: Mapping[str, Any],
    checkpoint_dir: Path,
    settings: ExecutionSettings = PRODUCTION_SETTINGS,
    require_registered_identities: bool = True,
) -> StructuralBaselineComparisonExecutionRun:
    _validate_frozen_contract(source_contract["frozen_contract"])
    _validate_inputs(
        preregistration_execution=preregistration_execution,
        preregistration=preregistration,
        execution_handoff=execution_handoff,
        preregistration_completion=preregistration_completion,
        candidate_portfolio=candidate_portfolio,
        candidate_evaluation_execution=candidate_evaluation_execution,
        candidate_evaluation_decision=candidate_evaluation_decision,
        require_registered_identities=require_registered_identities,
    )
    if (
        not settings.is_production()
        and source_contract.get("test_mode_allowed") is not True
    ):
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            "non_production_settings_require_explicit_test_contract"
        )
    if settings.is_production() and (
        settings.considerations_per_replicate != CANDIDATE_CONSIDERATIONS_PER_REPLICATE
        or settings.considerations_per_class != CANDIDATE_CONSIDERATIONS_PER_CLASS
        or settings.total_considerations != TOTAL_CANDIDATE_CONSIDERATIONS
    ):
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            "production_baseline_comparison_workload_changed"
        )
    tables = build_universe_tables()
    candidate_ranks = np.asarray(candidate_portfolio["selected_ranks"], dtype=np.uint32)
    candidate_exact, _, _, _ = structural_stats(candidate_ranks, tables)
    if candidate_exact.to_dict() != CANDIDATE_STATS:
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            "registered_candidate_metric_recomputation_changed"
        )
    preflight = run_reference_preflight(tables)
    identity = _checkpoint_identity(str(source_contract["source_set_digest"]), settings)
    index_path = checkpoint_dir / "checkpoint-index.json"
    index = {
        "schema_version": (
            "dehps-prediction-v2-structural-baseline-comparison-checkpoint-index.v1"
        ),
        "checkpoint_identity": identity,
        "source_set_digest": source_contract["source_set_digest"],
        "replicate_count": settings.replicates_per_class * len(BASELINE_CLASSES),
        "repetition_scan": REPETITION_SCAN,
    }
    if index_path.exists():
        if json.loads(index_path.read_text(encoding="utf-8")) != index:
            raise PredictionV2StructuralBaselineComparisonExecutionError(
                "baseline_comparison_checkpoint_index_changed"
            )
    else:
        _write_json(index_path, index)
    global _WORKER_TABLES
    _WORKER_TABLES = tables
    arguments = [
        (class_id, replicate_index, str(checkpoint_dir), identity, settings)
        for class_id in BASELINE_CLASSES
        for replicate_index in range(settings.replicates_per_class)
    ]
    rows = _run_parallel_replicates(arguments=arguments, settings=settings)
    return _build_result_artifacts(
        source_contract=source_contract,
        preregistration_execution=preregistration_execution,
        preregistration=preregistration,
        execution_handoff=execution_handoff,
        preregistration_completion=preregistration_completion,
        candidate_portfolio=candidate_portfolio,
        candidate_evaluation_execution=candidate_evaluation_execution,
        candidate_evaluation_decision=candidate_evaluation_decision,
        settings=settings,
        preflight=preflight,
        rows=rows,
    )


def replay_structural_baseline_comparison_artifacts(
    *,
    result_index: Mapping[str, Any],
    gate_outcome: Mapping[str, Any],
    completion: Mapping[str, Any],
) -> dict[str, Any]:
    _verify_artifact(
        result_index,
        domain=("dehps.prediction-v2.structural-baseline-comparison-result-index.v1"),
    )
    _verify_artifact(
        gate_outcome,
        domain=("dehps.prediction-v2.structural-baseline-comparison-gate-outcome.v1"),
    )
    _verify_artifact(
        completion,
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-execution-completion.v1"
        ),
    )
    rows = result_index.get("ordered_replicates")
    if not isinstance(rows, list) or len(rows) != 384:
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            "baseline_comparison_replay_rows_invalid"
        )
    summaries = _class_summaries(
        rows,
        CANDIDATE_STATS,
        expected_replicates_per_class=BASELINE_REPLICATES_PER_CLASS,
        expected_considerations_per_replicate=CANDIDATE_CONSIDERATIONS_PER_REPLICATE,
    )
    decision = (
        SUPPORTED_LABEL
        if all(row["class_gate_pass"] for row in summaries)
        else FAILURE_LABEL
    )
    if (
        result_index.get("class_summaries") != summaries
        or result_index.get("total_candidate_considerations")
        != TOTAL_CANDIDATE_CONSIDERATIONS
        or result_index.get("repetition_scan") != REPETITION_SCAN
        or gate_outcome.get("result_index_digest")
        != result_index.get("artifact_digest")
        or gate_outcome.get("class_summaries") != summaries
        or gate_outcome.get("decision") != decision
        or gate_outcome.get("repetition_scan") != REPETITION_SCAN
        or completion.get("result_index_digest") != result_index.get("artifact_digest")
        or completion.get("gate_outcome_digest") != gate_outcome.get("artifact_digest")
        or completion.get("decision") != decision
        or completion.get("completion_fact")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_COMPLETION_FACT
        or completion.get("next_consumer")
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY
        or completion.get("repetition_scan") != REPETITION_SCAN
    ):
        raise PredictionV2StructuralBaselineComparisonExecutionError(
            "baseline_comparison_replay_cross_identity_changed"
        )
    return {
        "schema_version": (
            "dehps-prediction-v2-structural-baseline-comparison-execution-replay.v1"
        ),
        "status": "REPLAY_VERIFIED",
        "decision": decision,
        "result_index_digest": result_index["artifact_digest"],
        "gate_outcome_digest": gate_outcome["artifact_digest"],
        "completion_digest": completion["artifact_digest"],
        "same_registered_content": True,
        "workload_rerun": False,
        "baseline_replicates_replayed": 0,
        "candidate_considerations_replayed": 0,
        "database_queries_during_replay": 0,
        "historical_rows_read": 0,
        "manual_input_assembly": False,
        "repetition_scan": REPETITION_SCAN,
        "next_consumer": (
            PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY
        ),
    }
