from __future__ import annotations

import hashlib
import json
import os
import resource
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import shake_256
from itertools import combinations
from math import comb
from pathlib import Path
from typing import Any

import numpy as np
from numba import config as numba_config
from numba import get_num_threads, njit, prange, set_num_threads

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_balanced_design_feasibility_execution import (
    OrbitInventory,
    orbit_inventory_from_artifact,
)

PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_TASK_KEY = (
    "prediction-v2-balanced-design-structural-evaluation-execution"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_CAPABILITY = (
    "prediction_v2_balanced_design_structural_evaluation_execution"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_COMPLETION_FACT = (
    "prediction-v2-balanced-design-structural-evaluation-execution:COMPLETE"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_TASK_KEY = (
    "prediction-v2-balanced-design-structural-evaluation-result-decision"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/"
    "prediction-v2-balanced-design-structural-evaluation-execution-source-v1.json"
)
PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_APPROVED_EVENT = (
    "research-contract:prediction-v2-balanced-design-structural-evaluation-"
    "execution:approved"
)

PREREGISTRATION_MAINLINE_EXECUTION_DIGEST = (
    "0d4dcffc37f30fa8b58fe9b9ab8749b22d03ea091b0f12a07c2ac9c5eba8ce94"
)
PREREGISTRATION_DIGEST = (
    "47b6ead65dbcde5a65b1f7c23b1823f0fc63f56b92f523e7b1f75a3e252c72cc"
)
EXECUTION_HANDOFF_DIGEST = (
    "f5d636b0d8bb8e43883ceb4ef2597dcf1c01d88825474302251d7a63617856ef"
)
PREREGISTRATION_COMPLETION_DIGEST = (
    "d1b15201611275ae89d580a387e8de711b10edfb320e8c5984a59f9dea3caa0d"
)
FEASIBILITY_MAINLINE_EXECUTION_DIGEST = (
    "4e060203c9172d13987b9e4597a70d01ccbd905aa7f0b1db8a74fa2a1f31ee6d"
)
ORBIT_INVENTORY_DIGEST = (
    "dde85462b725ec8719a30c5879dee0ba90b4a6d97f4a78b2d08b2beadc0c1f90"
)
SEARCH_RESULT_DIGEST = (
    "da9283998bd5833b6ad66f64543c42d0a94b06b7a730891eb718e21188210e79"
)
FIXED_CERTIFICATE_DIGEST = (
    "b7a0069edef9f6a2aeec3f2205a50a63ba39594ed555c3c89b108830cd3c28db"
)

POINT_COUNT = 33
BLOCK_SIZE = 6
BLOCK_COUNT = 176
LEGAL_BLOCK_COUNT = 1_107_568
FULL_ORBIT_COUNT = 33_561
SHORT_ORBIT_COUNT = 5
PRIMARY_REPLICATES = 9_999
SECONDARY_REPLICATES = 1_999
DIAGNOSTIC_REPLICATES = 199
PRIMARY_CHUNK_SIZE = 512
SECONDARY_CHUNK_SIZE = 256
MAXIMUM_WALL_SECONDS = 1_800
MAXIMUM_RESIDENT_BYTES = 4_294_967_296
PRIMARY_NULL = "Z33_ORBIT_PROFILE_MATCHED_WITHOUT_REPLACEMENT_5_FULL_1_SHORT_B176"
SECONDARY_NULL = (
    "UNIFORM_PREFIX_WITHOUT_REPLACEMENT_FROM_ALL_1107568_LEGAL_BLOCKS_B176"
)
POSITIVE_OUTCOME = "HIGHER_ORDER_STRUCTURAL_HOLDOUT_ADVANTAGE_WITHIN_MATCHED_NULL_ONLY"
NULL_OUTCOME = "PAIR_BALANCE_ONLY_NO_PREREGISTERED_HIGHER_ORDER_ADVANTAGE"
REGRESSION_OUTCOME = "HIGHER_ORDER_STRUCTURAL_REGRESSION_AGAINST_MATCHED_NULL"
INVALID_OUTCOME = "INVALID_EVALUATION_NO_DECISION"
REPETITION_SCAN = "ABSENT_BY_CONSTRUCTION"

_SOURCE_SCHEMA = (
    "dehps-prediction-v2-balanced-design-structural-evaluation-execution-source.v1"
)
_SOURCE_ARTIFACT_TYPE = (
    "prediction_v2_balanced_design_structural_evaluation_execution_source"
)
_RESULT_DOMAIN = (
    "dehps.prediction-v2.balanced-design-structural-evaluation-result.v1"
)
_DIAGNOSTICS_DOMAIN = (
    "dehps.prediction-v2.balanced-design-structural-evaluation-diagnostics.v1"
)
_COMPLETION_DOMAIN = (
    "dehps.prediction-v2.balanced-design-structural-evaluation-execution-completion.v1"
)
_CHECKPOINT_DOMAIN = (
    "dehps.prediction-v2.balanced-design-structural-evaluation-checkpoint-chunk.v1"
)
_CHECKPOINT_MANIFEST_DOMAIN = (
    "dehps.prediction-v2.balanced-design-structural-evaluation-checkpoint-manifest.v1"
)
_CERTIFICATE_DOMAIN = "dehps.prediction-v2.balanced-design.certificate.v1"
_INVENTORY_DOMAIN = "dehps.prediction-v2.balanced-design.orbit-inventory.v1"
_SEARCH_RESULT_DOMAIN = "dehps.prediction-v2.balanced-design.search-result.v1"
_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-prediction-v2-balanced-design-structural-evaluation-execution-"
    "round-105-20260809"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-prediction-v2-balanced-design-structural-evaluation-execution-"
    "round-105-20260809"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/"
    "prediction_v2_balanced_design_structural_evaluation_execution.py"
)
_REUSED_INVENTORY_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/"
    "prediction_v2_balanced_design_feasibility_execution.py"
)
FROZEN_EXECUTION_CONTRACT_DIGEST = (
    "0e2de0fb60fafd008237562a2825f1af4629bb958ffb790e75d4389f4d3717e1"
)


class PredictionV2BalancedDesignStructuralEvaluationExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class CollisionDiagnostics:
    triple_collision_mass: int
    quadruple_collision_mass: int
    quintuple_collision_mass: int
    block_intersection_histogram_0_through_5: tuple[int, ...]
    maximum_block_intersection: int
    minimum_replacement_distance: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "triple_collision_mass": self.triple_collision_mass,
            "quadruple_collision_mass": self.quadruple_collision_mass,
            "quintuple_collision_mass": self.quintuple_collision_mass,
            "block_intersection_histogram_0_through_5": list(
                self.block_intersection_histogram_0_through_5
            ),
            "maximum_block_intersection": self.maximum_block_intersection,
            "minimum_replacement_distance": self.minimum_replacement_distance,
        }


@dataclass(frozen=True)
class PredictionV2BalancedDesignStructuralEvaluationExecutionRun:
    result: Mapping[str, Any]
    diagnostics: Mapping[str, Any]
    completion: Mapping[str, Any]
    elapsed_wall_seconds: float
    peak_resident_bytes: int
    thread_count: int
    resumed_chunk_count: int
    executed_chunk_count: int

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.result, self.diagnostics, self.completion


class Shake256CounterRandomBelow:
    def __init__(self, domain: str) -> None:
        self._domain = domain.encode("utf-8")
        self._counter = 0

    @property
    def counter(self) -> int:
        return self._counter

    def random_below(self, exclusive_bound: int) -> int:
        if exclusive_bound <= 0:
            raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
                "random_below_bound_invalid"
            )
        if exclusive_bound == 1:
            return 0
        bits = (exclusive_bound - 1).bit_length()
        width = (bits + 7) // 8
        high_mask = (1 << (bits - 8 * (width - 1))) - 1
        while True:
            if self._counter >= 1 << 128:
                raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
                    "random_counter_exhausted"
                )
            message = (
                self._domain
                + b"\x00"
                + self._counter.to_bytes(16, byteorder="big", signed=False)
            )
            self._counter += 1
            raw = bytearray(shake_256(message).digest(width))
            raw[0] &= high_mask
            value = int.from_bytes(raw, byteorder="big", signed=False)
            if value < exclusive_bound:
                return value


def sparse_partial_fisher_yates_prefix(
    *, population_size: int, sample_size: int, random: Shake256CounterRandomBelow
) -> tuple[int, ...]:
    if not 0 <= sample_size <= population_size:
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "sample_shape_invalid"
        )
    swaps: dict[int, int] = {}
    selected: list[int] = []
    for position in range(sample_size):
        swap_position = position + random.random_below(population_size - position)
        chosen = swaps.get(swap_position, swap_position)
        swaps[swap_position] = swaps.get(position, position)
        selected.append(chosen)
    return tuple(selected)


def block_to_mask(block: Sequence[int]) -> int:
    mask = 0
    for point in block:
        mask |= 1 << int(point)
    return mask


def direct_triple_collision_mass(blocks: Sequence[Sequence[int]]) -> int:
    counts: dict[tuple[int, int, int], int] = {}
    for block in blocks:
        canonical = tuple(int(value) for value in block)
        for triple in combinations(canonical, 3):
            counts[triple] = counts.get(triple, 0) + 1
    return sum(value * (value - 1) // 2 for value in counts.values())


def pair_intersection_collision_diagnostics(
    block_masks: Sequence[int],
) -> CollisionDiagnostics:
    triple = 0
    quadruple = 0
    quintuple = 0
    histogram = [0] * 6
    maximum = 0
    masks = tuple(int(mask) for mask in block_masks)
    for left_index, left in enumerate(masks):
        for right in masks[left_index + 1 :]:
            intersection = (left & right).bit_count()
            triple += comb(intersection, 3) if intersection >= 3 else 0
            quadruple += comb(intersection, 4) if intersection >= 4 else 0
            quintuple += comb(intersection, 5) if intersection >= 5 else 0
            if intersection < 6:
                histogram[intersection] += 1
            maximum = max(maximum, intersection)
    return CollisionDiagnostics(
        triple_collision_mass=triple,
        quadruple_collision_mass=quadruple,
        quintuple_collision_mass=quintuple,
        block_intersection_histogram_0_through_5=tuple(histogram),
        maximum_block_intersection=maximum,
        minimum_replacement_distance=BLOCK_SIZE - maximum,
    )


@njit(cache=True, inline="always")
def _popcount_uint64(value: np.uint64) -> int:
    count = 0
    while value != 0:
        value &= value - np.uint64(1)
        count += 1
    return count


@njit(cache=True, parallel=True)
def _batch_pair_intersection_kernel(
    block_masks: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    replicate_count = block_masks.shape[0]
    triple = np.zeros(replicate_count, dtype=np.int64)
    quadruple = np.zeros(replicate_count, dtype=np.int64)
    quintuple = np.zeros(replicate_count, dtype=np.int64)
    histograms = np.zeros((replicate_count, 6), dtype=np.int64)
    maxima = np.zeros(replicate_count, dtype=np.int64)
    triple_lookup = np.asarray((0, 0, 0, 1, 4, 10, 20), dtype=np.int64)
    quadruple_lookup = np.asarray((0, 0, 0, 0, 1, 5, 15), dtype=np.int64)
    quintuple_lookup = np.asarray((0, 0, 0, 0, 0, 1, 6), dtype=np.int64)
    for replicate_index in prange(replicate_count):
        local_triple = 0
        local_quadruple = 0
        local_quintuple = 0
        local_maximum = 0
        for left_index in range(block_masks.shape[1]):
            left = block_masks[replicate_index, left_index]
            for right_index in range(left_index + 1, block_masks.shape[1]):
                intersection = _popcount_uint64(
                    left & block_masks[replicate_index, right_index]
                )
                local_triple += triple_lookup[intersection]
                local_quadruple += quadruple_lookup[intersection]
                local_quintuple += quintuple_lookup[intersection]
                if intersection < 6:
                    histograms[replicate_index, intersection] += 1
                local_maximum = max(local_maximum, intersection)
        triple[replicate_index] = local_triple
        quadruple[replicate_index] = local_quadruple
        quintuple[replicate_index] = local_quintuple
        maxima[replicate_index] = local_maximum
    return triple, quadruple, quintuple, histograms, maxima


def batch_pair_intersection_diagnostics(
    block_masks: np.ndarray,
    *,
    thread_count: int | None = None,
) -> tuple[CollisionDiagnostics, ...]:
    masks = np.ascontiguousarray(block_masks, dtype=np.uint64)
    if masks.ndim != 2 or masks.shape[1] != BLOCK_COUNT:
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "batch_block_shape_invalid"
        )
    previous_threads = get_num_threads()
    selected_threads = _resolved_thread_count(thread_count)
    set_num_threads(selected_threads)
    try:
        triple, quadruple, quintuple, histograms, maxima = (
            _batch_pair_intersection_kernel(masks)
        )
    finally:
        set_num_threads(previous_threads)
    return tuple(
        CollisionDiagnostics(
            triple_collision_mass=int(triple[index]),
            quadruple_collision_mass=int(quadruple[index]),
            quintuple_collision_mass=int(quintuple[index]),
            block_intersection_histogram_0_through_5=tuple(
                int(value) for value in histograms[index]
            ),
            maximum_block_intersection=int(maxima[index]),
            minimum_replacement_distance=BLOCK_SIZE - int(maxima[index]),
        )
        for index in range(masks.shape[0])
    )


def load_prediction_v2_balanced_design_structural_evaluation_execution_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            f"balanced_design_structural_evaluation_execution_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != _SOURCE_SCHEMA
        or payload.get("artifact_type") != _SOURCE_ARTIFACT_TYPE
        or payload.get("contract_key")
        != "PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 435
        or payload.get("research_execution_id") != 356
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 436
        or payload.get("engineering_execution_id") != 357
        or payload.get("scientific_contract_change_allowed") is not False
        or payload.get("duplicate_membership_uniqueness_or_repetition_scans") != 0
        or payload.get("registered_children") != 3
        or payload.get("new_evidence_created") is not False
        or payload.get("new_model_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or len(entries) != 2
        or not isinstance(frozen, dict)
        or dict(frozen) != _expected_frozen_execution_contract()
        or payload.get("frozen_contract_digest")
        != FROZEN_EXECUTION_CONTRACT_DIGEST
        or canonical_digest(
            frozen,
            domain=(
                "dehps.prediction-v2.balanced-design-structural-evaluation-"
                "execution-frozen-contract.v1"
            ),
        )
        != FROZEN_EXECUTION_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain=(
                "dehps.prediction-v2.balanced-design-structural-evaluation-"
                "execution-source-set.v1"
            ),
        )
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "balanced_design_structural_evaluation_execution_source_invalid"
        )
    expected_paths = (_SOURCE_MODULE_PATH, _REUSED_INVENTORY_MODULE_PATH)
    for entry, expected_path in zip(entries, expected_paths, strict=True):
        if (
            not isinstance(entry, dict)
            or entry.get("path") != expected_path
            or not _is_digest(entry.get("content_sha256"))
        ):
            raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
                "balanced_design_structural_evaluation_execution_source_entry_invalid"
            )
    return payload


def verify_prediction_v2_balanced_design_structural_evaluation_execution_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
                f"balanced_design_structural_evaluation_execution_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
                f"balanced_design_structural_evaluation_execution_source_modified:{relative}"
            )


def execute_prediction_v2_balanced_design_structural_evaluation(
    *,
    source_contract: Mapping[str, Any],
    preregistration_mainline_execution: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    execution_handoff: Mapping[str, Any],
    preregistration_completion: Mapping[str, Any],
    preregistration_replay: Mapping[str, Any],
    feasibility_mainline_execution: Mapping[str, Any],
    orbit_inventory_artifact: Mapping[str, Any],
    search_result_artifact: Mapping[str, Any],
    feasibility_replay: Mapping[str, Any],
    checkpoint_path: Path,
    thread_count: int | None = None,
    require_registered_identities: bool = True,
) -> PredictionV2BalancedDesignStructuralEvaluationExecutionRun:
    started = time.monotonic()
    _validate_parent_artifacts(
        preregistration_mainline_execution=preregistration_mainline_execution,
        preregistration=preregistration,
        execution_handoff=execution_handoff,
        preregistration_completion=preregistration_completion,
        preregistration_replay=preregistration_replay,
        feasibility_mainline_execution=feasibility_mainline_execution,
        orbit_inventory_artifact=orbit_inventory_artifact,
        search_result_artifact=search_result_artifact,
        feasibility_replay=feasibility_replay,
        require_registered_identities=require_registered_identities,
    )
    if dict(source_contract["frozen_contract"]) != _expected_frozen_execution_contract():
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "balanced_design_structural_evaluation_execution_frozen_contract_changed"
        )
    inventory = orbit_inventory_from_artifact(
        orbit_inventory_artifact,
        require_formal_identity=True,
    )
    certificate = search_result_artifact.get("certificate")
    if not isinstance(certificate, Mapping):
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "balanced_design_structural_evaluation_execution_certificate_missing"
        )
    candidate_masks = _candidate_block_masks(
        inventory=inventory,
        certificate=certificate,
    )
    candidate = batch_pair_intersection_diagnostics(
        candidate_masks.reshape(1, BLOCK_COUNT),
        thread_count=1,
    )[0]
    selected_threads = _resolved_thread_count(thread_count)
    chunks = _load_checkpoint_chunks(checkpoint_path)
    resumed_chunk_count = len(chunks)
    primary_masses, primary_diagnostics = _checkpoint_family_outputs(
        chunks=chunks,
        family="primary",
    )
    secondary_masses, secondary_diagnostics = _checkpoint_family_outputs(
        chunks=chunks,
        family="secondary",
    )
    legal_masks: np.ndarray | None = None
    executed_chunk_count = 0
    while len(primary_masses) < PRIMARY_REPLICATES:
        _require_resource_budget(started=started)
        start = len(primary_masses)
        end = min(start + PRIMARY_CHUNK_SIZE, PRIMARY_REPLICATES)
        masks = _build_primary_chunk_masks(
            inventory=inventory,
            start=start,
            end=end,
        )
        diagnostics = batch_pair_intersection_diagnostics(
            masks,
            thread_count=selected_threads,
        )
        record = _checkpoint_record(
            family="primary",
            start=start,
            diagnostics=diagnostics,
        )
        _append_checkpoint(checkpoint_path, record)
        chunks.append(record)
        executed_chunk_count += 1
        primary_masses.extend(
            item.triple_collision_mass for item in diagnostics
        )
        primary_diagnostics.extend(
            item.to_dict()
            for offset, item in enumerate(diagnostics, start=start)
            if offset < DIAGNOSTIC_REPLICATES
        )
    while len(secondary_masses) < SECONDARY_REPLICATES:
        _require_resource_budget(started=started)
        if legal_masks is None:
            legal_masks = _build_lexicographic_legal_block_masks()
        start = len(secondary_masses)
        end = min(start + SECONDARY_CHUNK_SIZE, SECONDARY_REPLICATES)
        masks = _build_secondary_chunk_masks(
            legal_masks=legal_masks,
            start=start,
            end=end,
        )
        diagnostics = batch_pair_intersection_diagnostics(
            masks,
            thread_count=selected_threads,
        )
        record = _checkpoint_record(
            family="secondary",
            start=start,
            diagnostics=diagnostics,
        )
        _append_checkpoint(checkpoint_path, record)
        chunks.append(record)
        executed_chunk_count += 1
        secondary_masses.extend(
            item.triple_collision_mass for item in diagnostics
        )
        secondary_diagnostics.extend(
            item.to_dict()
            for offset, item in enumerate(diagnostics, start=start)
            if offset < DIAGNOSTIC_REPLICATES
        )
    _require_resource_budget(started=started)
    terminal_checkpoint_digest = canonical_digest(
        [str(record["artifact_digest"]) for record in chunks],
        domain=_CHECKPOINT_MANIFEST_DOMAIN,
    )
    run = build_prediction_v2_balanced_design_structural_evaluation_artifacts(
        source_contract=source_contract,
        preregistration_mainline_execution=preregistration_mainline_execution,
        preregistration=preregistration,
        execution_handoff=execution_handoff,
        preregistration_completion=preregistration_completion,
        feasibility_mainline_execution=feasibility_mainline_execution,
        orbit_inventory_artifact=orbit_inventory_artifact,
        search_result_artifact=search_result_artifact,
        candidate=candidate.to_dict(),
        primary_masses=primary_masses,
        secondary_masses=secondary_masses,
        primary_diagnostics=primary_diagnostics,
        secondary_diagnostics=secondary_diagnostics,
        checkpoint_chunk_count=len(chunks),
        terminal_checkpoint_digest=terminal_checkpoint_digest,
    )
    return PredictionV2BalancedDesignStructuralEvaluationExecutionRun(
        result=run.result,
        diagnostics=run.diagnostics,
        completion=run.completion,
        elapsed_wall_seconds=time.monotonic() - started,
        peak_resident_bytes=_peak_resident_bytes(),
        thread_count=selected_threads,
        resumed_chunk_count=resumed_chunk_count,
        executed_chunk_count=executed_chunk_count,
    )


def build_prediction_v2_balanced_design_structural_evaluation_artifacts(
    *,
    source_contract: Mapping[str, Any],
    preregistration_mainline_execution: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    execution_handoff: Mapping[str, Any],
    preregistration_completion: Mapping[str, Any],
    feasibility_mainline_execution: Mapping[str, Any],
    orbit_inventory_artifact: Mapping[str, Any],
    search_result_artifact: Mapping[str, Any],
    candidate: Mapping[str, Any],
    primary_masses: Sequence[int],
    secondary_masses: Sequence[int],
    primary_diagnostics: Sequence[Mapping[str, Any]],
    secondary_diagnostics: Sequence[Mapping[str, Any]],
    checkpoint_chunk_count: int,
    terminal_checkpoint_digest: str,
) -> PredictionV2BalancedDesignStructuralEvaluationExecutionRun:
    primary = tuple(int(value) for value in primary_masses)
    secondary = tuple(int(value) for value in secondary_masses)
    if (
        len(primary) != PRIMARY_REPLICATES
        or len(secondary) != SECONDARY_REPLICATES
        or len(primary_diagnostics) != DIAGNOSTIC_REPLICATES
        or len(secondary_diagnostics) != DIAGNOSTIC_REPLICATES
        or not _is_digest(terminal_checkpoint_digest)
        or checkpoint_chunk_count <= 0
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "balanced_design_structural_evaluation_execution_output_incomplete"
        )
    candidate_mass = int(candidate["triple_collision_mass"])
    inference = _inference(
        candidate_mass=candidate_mass,
        primary_masses=primary,
        secondary_masses=secondary,
    )
    source_digest = str(source_contract["artifact_digest"])
    parent_digests = (
        source_digest,
        str(preregistration_mainline_execution["artifact_digest"]),
        str(preregistration["artifact_digest"]),
        str(execution_handoff["artifact_digest"]),
        str(preregistration_completion["artifact_digest"]),
        str(feasibility_mainline_execution["artifact_digest"]),
        str(orbit_inventory_artifact["artifact_digest"]),
        str(search_result_artifact["artifact_digest"]),
    )
    result = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-structural-evaluation-result.v1"
        ),
        artifact_type="prediction_v2_balanced_design_structural_evaluation_result",
        body={
            "status": "COMPLETE",
            "outcome": inference["outcome"],
            "confirmatory_endpoint": "triple_collision_mass",
            "optimized_equivalent_formula": (
                "sum_over_unordered_block_pairs_of_C(popcount(block_i_bitmask_and_"
                "block_j_bitmask),3)"
            ),
            "candidate_triple_collision_mass": candidate_mass,
            "primary_null": PRIMARY_NULL,
            "primary_replicate_count": PRIMARY_REPLICATES,
            "primary_masses_by_replicate_index": list(primary),
            "secondary_null": SECONDARY_NULL,
            "secondary_replicate_count": SECONDARY_REPLICATES,
            "secondary_masses_by_replicate_index": list(secondary),
            "inference": inference,
            "terminal_checkpoint_digest": terminal_checkpoint_digest,
            "checkpoint_chunk_count": checkpoint_chunk_count,
            "candidate_evaluation_statistics_read": True,
            "candidate_evaluations": 1,
            "null_replicates_executed": PRIMARY_REPLICATES + SECONDARY_REPLICATES,
            "primary_null_replicates_executed": PRIMARY_REPLICATES,
            "secondary_null_replicates_executed": SECONDARY_REPLICATES,
            "legal_blocks_materialized": LEGAL_BLOCK_COUNT,
            **_claim_boundary(),
        },
        parent_digests=parent_digests,
        domain=_RESULT_DOMAIN,
    )
    diagnostics = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-structural-evaluation-"
            "diagnostics.v1"
        ),
        artifact_type=(
            "prediction_v2_balanced_design_structural_evaluation_diagnostics"
        ),
        body={
            "status": "COMPLETE",
            "candidate": dict(candidate),
            "primary_null_replicate_indices": [0, DIAGNOSTIC_REPLICATES - 1],
            "primary_null_diagnostics": [dict(item) for item in primary_diagnostics],
            "secondary_null_replicate_indices": [0, DIAGNOSTIC_REPLICATES - 1],
            "secondary_null_diagnostics": [
                dict(item) for item in secondary_diagnostics
            ],
            "diagnostics_gate_primary_outcome": False,
            "secondary_null_may_change_primary_outcome": False,
            **_claim_boundary(),
        },
        parent_digests=(*parent_digests, str(result["artifact_digest"])),
        domain=_DIAGNOSTICS_DOMAIN,
    )
    completion = _artifact(
        schema_version=(
            "dehps-prediction-v2-balanced-design-structural-evaluation-"
            "execution-completion.v1"
        ),
        artifact_type=(
            "prediction_v2_balanced_design_structural_evaluation_execution_completion"
        ),
        body={
            "status": "COMPLETE",
            "completion_fact": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_COMPLETION_FACT,
            "source_contract_digest": source_digest,
            "result_artifact_digest": result["artifact_digest"],
            "diagnostics_artifact_digest": diagnostics["artifact_digest"],
            "outcome": inference["outcome"],
            "registered_child_count": 3,
            "next_consumer": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_TASK_KEY,
            **_claim_boundary(),
        },
        parent_digests=(
            source_digest,
            str(result["artifact_digest"]),
            str(diagnostics["artifact_digest"]),
        ),
        domain=_COMPLETION_DOMAIN,
    )
    return PredictionV2BalancedDesignStructuralEvaluationExecutionRun(
        result=result,
        diagnostics=diagnostics,
        completion=completion,
        elapsed_wall_seconds=0.0,
        peak_resident_bytes=0,
        thread_count=0,
        resumed_chunk_count=0,
        executed_chunk_count=0,
    )


def replay_prediction_v2_balanced_design_structural_evaluation_execution(
    *,
    result_artifact: Mapping[str, Any],
    diagnostics_artifact: Mapping[str, Any],
    completion_artifact: Mapping[str, Any],
) -> dict[str, Any]:
    _verify_artifact(result_artifact, domain=_RESULT_DOMAIN)
    _verify_artifact(diagnostics_artifact, domain=_DIAGNOSTICS_DOMAIN)
    _verify_artifact(completion_artifact, domain=_COMPLETION_DOMAIN)
    primary = result_artifact.get("primary_masses_by_replicate_index")
    secondary = result_artifact.get("secondary_masses_by_replicate_index")
    candidate_mass = result_artifact.get("candidate_triple_collision_mass")
    if (
        not isinstance(primary, list)
        or not isinstance(secondary, list)
        or len(primary) != PRIMARY_REPLICATES
        or len(secondary) != SECONDARY_REPLICATES
        or not isinstance(candidate_mass, int)
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "registered_structural_evaluation_result_incomplete"
        )
    inference = _inference(
        candidate_mass=candidate_mass,
        primary_masses=primary,
        secondary_masses=secondary,
    )
    if (
        result_artifact.get("inference") != inference
        or result_artifact.get("outcome") != inference["outcome"]
        or diagnostics_artifact.get("candidate", {}).get(
            "triple_collision_mass"
        )
        != candidate_mass
        or completion_artifact.get("result_artifact_digest")
        != result_artifact.get("artifact_digest")
        or completion_artifact.get("diagnostics_artifact_digest")
        != diagnostics_artifact.get("artifact_digest")
        or completion_artifact.get("outcome") != inference["outcome"]
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "registered_structural_evaluation_inference_changed"
        )
    _validate_registered_diagnostics(
        diagnostics_artifact=diagnostics_artifact,
        primary_masses=primary,
        secondary_masses=secondary,
    )
    return {
        "schema_version": (
            "dehps-prediction-v2-balanced-design-structural-evaluation-"
            "execution-replay.v1"
        ),
        "status": "REPLAY_VERIFIED",
        "same_registered_content": True,
        "workload_rerun": False,
        "sample_regeneration": False,
        "manual_input_assembly": False,
        "inference_recomputed_from_registered_arrays": True,
        "candidate_evaluations_replayed": 0,
        "null_replicates_replayed": 0,
        "database_queries_during_replay": 0,
        "historical_rows_read": 0,
        "folds_replayed": 0,
        "duplicate_membership_uniqueness_or_repetition_scans": 0,
        "repetition_scan": REPETITION_SCAN,
        "outcome": inference["outcome"],
        "next_consumer": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_TASK_KEY,
    }


def _build_primary_chunk_masks(
    *, inventory: OrbitInventory, start: int, end: int
) -> np.ndarray:
    output = np.empty((end - start, BLOCK_COUNT), dtype=np.uint64)
    for row, replicate_index in enumerate(range(start, end)):
        domain = _random_domain(PRIMARY_NULL, replicate_index)
        random = Shake256CounterRandomBelow(domain)
        full_indices = sparse_partial_fisher_yates_prefix(
            population_size=FULL_ORBIT_COUNT,
            sample_size=5,
            random=random,
        )
        short_indices = sparse_partial_fisher_yates_prefix(
            population_size=SHORT_ORBIT_COUNT,
            sample_size=1,
            random=random,
        )
        cursor = 0
        for index in full_indices:
            representative = inventory.full_representatives[index]
            base = block_to_mask(representative.block)
            for shift in range(representative.orbit_size):
                output[row, cursor] = _rotate_mask(base, shift)
                cursor += 1
        for index in short_indices:
            representative = inventory.short_representatives[index]
            base = block_to_mask(representative.block)
            for shift in range(representative.orbit_size):
                output[row, cursor] = _rotate_mask(base, shift)
                cursor += 1
        if cursor != BLOCK_COUNT:
            raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
                "primary_block_count_changed"
            )
    return output


def _build_lexicographic_legal_block_masks() -> np.ndarray:
    output = np.empty(LEGAL_BLOCK_COUNT, dtype=np.uint64)
    cursor = 0
    for block in combinations(range(POINT_COUNT), BLOCK_SIZE):
        output[cursor] = block_to_mask(block)
        cursor += 1
    if cursor != LEGAL_BLOCK_COUNT:
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "legal_block_count_changed"
        )
    return output


def _build_secondary_chunk_masks(
    *, legal_masks: np.ndarray, start: int, end: int
) -> np.ndarray:
    output = np.empty((end - start, BLOCK_COUNT), dtype=np.uint64)
    for row, replicate_index in enumerate(range(start, end)):
        random = Shake256CounterRandomBelow(
            _random_domain(SECONDARY_NULL, replicate_index)
        )
        indices = sparse_partial_fisher_yates_prefix(
            population_size=LEGAL_BLOCK_COUNT,
            sample_size=BLOCK_COUNT,
            random=random,
        )
        output[row] = legal_masks[np.asarray(indices, dtype=np.int64)]
    return output


def _candidate_block_masks(
    *, inventory: OrbitInventory, certificate: Mapping[str, Any]
) -> np.ndarray:
    _verify_artifact(certificate, domain=_CERTIFICATE_DOMAIN)
    if certificate.get("artifact_digest") != FIXED_CERTIFICATE_DIGEST:
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "fixed_certificate_identity_changed"
        )
    by_id = {
        item.representative_id: item
        for item in (*inventory.full_representatives, *inventory.short_representatives)
    }
    representative_ids = (
        *certificate["selected_full_orbit_representative_ids"],
        *certificate["selected_short_orbit_representative_ids"],
    )
    output = np.empty(BLOCK_COUNT, dtype=np.uint64)
    cursor = 0
    try:
        for representative_id in representative_ids:
            representative = by_id[int(representative_id)]
            base = block_to_mask(representative.block)
            for shift in range(representative.orbit_size):
                output[cursor] = _rotate_mask(base, shift)
                cursor += 1
    except KeyError as exc:
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "fixed_certificate_representative_changed"
        ) from exc
    if cursor != BLOCK_COUNT:
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "fixed_candidate_block_count_changed"
        )
    return output


def _checkpoint_record(
    *, family: str, start: int, diagnostics: Sequence[CollisionDiagnostics]
) -> dict[str, Any]:
    end = start + len(diagnostics)
    body = {
        "schema_version": (
            "dehps-prediction-v2-balanced-design-structural-evaluation-"
            "checkpoint-chunk.v1"
        ),
        "artifact_type": (
            "prediction_v2_balanced_design_structural_evaluation_checkpoint_chunk"
        ),
        "artifact_digest": "",
        "frozen_execution_contract_digest": FROZEN_EXECUTION_CONTRACT_DIGEST,
        "family": family,
        "start_replicate_index": start,
        "end_replicate_index_exclusive": end,
        "triple_collision_masses": [
            item.triple_collision_mass for item in diagnostics
        ],
        "diagnostics": [
            {"replicate_index": index, **item.to_dict()}
            for index, item in enumerate(diagnostics, start=start)
            if index < DIAGNOSTIC_REPLICATES
        ],
        "duplicate_membership_uniqueness_or_repetition_scans": 0,
        "repetition_scan": REPETITION_SCAN,
    }
    identity = dict(body)
    identity.pop("artifact_digest")
    body["artifact_digest"] = canonical_digest(identity, domain=_CHECKPOINT_DOMAIN)
    return body


def _append_checkpoint(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        os.write(descriptor, payload.encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _load_checkpoint_chunks(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "checkpoint_unreadable"
        ) from exc
    records: list[dict[str, Any]] = []
    expected_family = "primary"
    expected_start = 0
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
                "checkpoint_partial_or_invalid"
            ) from exc
        _verify_artifact(record, domain=_CHECKPOINT_DOMAIN)
        family = record.get("family")
        start = record.get("start_replicate_index")
        end = record.get("end_replicate_index_exclusive")
        masses = record.get("triple_collision_masses")
        maximum = PRIMARY_REPLICATES if family == "primary" else SECONDARY_REPLICATES
        expected_chunk = PRIMARY_CHUNK_SIZE if family == "primary" else SECONDARY_CHUNK_SIZE
        if (
            record.get("frozen_execution_contract_digest")
            != FROZEN_EXECUTION_CONTRACT_DIGEST
            or family != expected_family
            or start != expected_start
            or not isinstance(end, int)
            or not isinstance(masses, list)
            or end - start != len(masses)
            or not 0 < end - start <= expected_chunk
            or end > maximum
            or record.get("duplicate_membership_uniqueness_or_repetition_scans")
            != 0
            or record.get("repetition_scan") != REPETITION_SCAN
        ):
            raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
                "checkpoint_sequence_invalid"
            )
        records.append(record)
        expected_start = end
        if family == "primary" and end == PRIMARY_REPLICATES:
            expected_family = "secondary"
            expected_start = 0
    return records


def _checkpoint_family_outputs(
    *, chunks: Sequence[Mapping[str, Any]], family: str
) -> tuple[list[int], list[dict[str, Any]]]:
    masses: list[int] = []
    diagnostics: list[dict[str, Any]] = []
    for record in chunks:
        if record["family"] != family:
            continue
        masses.extend(int(value) for value in record["triple_collision_masses"])
        diagnostics.extend(dict(item) for item in record["diagnostics"])
    for item in diagnostics:
        item.pop("replicate_index", None)
    return masses, diagnostics


def _inference(
    *, candidate_mass: int, primary_masses: Sequence[int], secondary_masses: Sequence[int]
) -> dict[str, Any]:
    primary_lower = 1 + sum(value <= candidate_mass for value in primary_masses)
    primary_upper = 1 + sum(value >= candidate_mass for value in primary_masses)
    secondary_lower = 1 + sum(value <= candidate_mass for value in secondary_masses)
    secondary_upper = 1 + sum(value >= candidate_mass for value in secondary_masses)
    if primary_lower <= 100:
        outcome = POSITIVE_OUTCOME
    elif primary_upper <= 100:
        outcome = REGRESSION_OUTCOME
    else:
        outcome = NULL_OUTCOME
    return {
        "primary_lower_tail_numerator": primary_lower,
        "primary_upper_tail_numerator": primary_upper,
        "primary_denominator": 10_000,
        "secondary_lower_tail_numerator": secondary_lower,
        "secondary_upper_tail_numerator": secondary_upper,
        "secondary_denominator": 2_000,
        "ties_included": True,
        "alpha": "1/100",
        "secondary_null_can_change_outcome": False,
        "outcome": outcome,
    }


def _validate_registered_diagnostics(
    *,
    diagnostics_artifact: Mapping[str, Any],
    primary_masses: Sequence[int],
    secondary_masses: Sequence[int],
) -> None:
    for key, masses in (
        ("primary_null_diagnostics", primary_masses),
        ("secondary_null_diagnostics", secondary_masses),
    ):
        diagnostics = diagnostics_artifact.get(key)
        if not isinstance(diagnostics, list) or len(diagnostics) != DIAGNOSTIC_REPLICATES:
            raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
                "registered_diagnostics_incomplete"
            )
        for index, item in enumerate(diagnostics):
            histogram = item.get("block_intersection_histogram_0_through_5")
            maximum = item.get("maximum_block_intersection")
            if (
                item.get("triple_collision_mass") != masses[index]
                or not isinstance(histogram, list)
                or len(histogram) != 6
                or sum(histogram) != comb(BLOCK_COUNT, 2)
                or not isinstance(maximum, int)
                or item.get("minimum_replacement_distance")
                != BLOCK_SIZE - maximum
            ):
                raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
                    "registered_diagnostics_changed"
                )


def _validate_parent_artifacts(
    *,
    preregistration_mainline_execution: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    execution_handoff: Mapping[str, Any],
    preregistration_completion: Mapping[str, Any],
    preregistration_replay: Mapping[str, Any],
    feasibility_mainline_execution: Mapping[str, Any],
    orbit_inventory_artifact: Mapping[str, Any],
    search_result_artifact: Mapping[str, Any],
    feasibility_replay: Mapping[str, Any],
    require_registered_identities: bool,
) -> None:
    artifacts_and_domains = (
        (preregistration_mainline_execution, "dehps.research-os.mainline-execution.v1"),
        (
            preregistration,
            "dehps.prediction-v2.balanced-design-structural-evaluation-preregistration.v1",
        ),
        (
            execution_handoff,
            "dehps.prediction-v2.balanced-design-structural-evaluation-execution-handoff.v1",
        ),
        (
            preregistration_completion,
            "dehps.prediction-v2.balanced-design-structural-evaluation-preregistration-completion.v1",
        ),
        (feasibility_mainline_execution, "dehps.research-os.mainline-execution.v1"),
        (orbit_inventory_artifact, _INVENTORY_DOMAIN),
        (search_result_artifact, _SEARCH_RESULT_DOMAIN),
    )
    for artifact, domain in artifacts_and_domains:
        _verify_artifact(artifact, domain=domain)
    observed = tuple(
        str(artifact.get("artifact_digest")) for artifact, _ in artifacts_and_domains
    )
    expected = (
        PREREGISTRATION_MAINLINE_EXECUTION_DIGEST,
        PREREGISTRATION_DIGEST,
        EXECUTION_HANDOFF_DIGEST,
        PREREGISTRATION_COMPLETION_DIGEST,
        FEASIBILITY_MAINLINE_EXECUTION_DIGEST,
        ORBIT_INVENTORY_DIGEST,
        SEARCH_RESULT_DIGEST,
    )
    if require_registered_identities and observed != expected:
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "balanced_design_structural_evaluation_execution_registered_identity_changed"
        )
    certificate = search_result_artifact.get("certificate")
    if (
        preregistration_mainline_execution.get("completion_classification")
        != "VALIDATED_IN_MAINLINE"
        or preregistration_mainline_execution.get("preregistration_artifact_digest")
        != preregistration.get("artifact_digest")
        or preregistration_mainline_execution.get("execution_handoff_digest")
        != execution_handoff.get("artifact_digest")
        or preregistration_mainline_execution.get("preregistration_completion_digest")
        != preregistration_completion.get("artifact_digest")
        or preregistration.get("status") != "FROZEN"
        or preregistration.get("primary_null", {}).get("replicate_count")
        != PRIMARY_REPLICATES
        or preregistration.get("secondary_null", {}).get("replicate_count")
        != SECONDARY_REPLICATES
        or preregistration.get("repetition_scan") != REPETITION_SCAN
        or execution_handoff.get("fixed_certificate_artifact_digest")
        != FIXED_CERTIFICATE_DIGEST
        or execution_handoff.get("execution_authorized") is not False
        or preregistration_completion.get("completion_fact")
        != "prediction-v2-balanced-design-structural-evaluation-preregistration:COMPLETE"
        or preregistration_replay.get("status") != "REPLAY_VERIFIED"
        or preregistration_replay.get("same_registered_content") is not True
        or feasibility_mainline_execution.get("completion_classification")
        != "VALIDATED_IN_MAINLINE"
        or feasibility_mainline_execution.get("orbit_inventory_digest")
        != orbit_inventory_artifact.get("artifact_digest")
        or feasibility_mainline_execution.get("search_result_digest")
        != search_result_artifact.get("artifact_digest")
        or search_result_artifact.get("certificate_artifact_digest")
        != FIXED_CERTIFICATE_DIGEST
        or not isinstance(certificate, Mapping)
        or certificate.get("artifact_digest") != FIXED_CERTIFICATE_DIGEST
        or feasibility_replay.get("status") != "REPLAY_VERIFIED"
        or feasibility_replay.get("certificate_verified") is not True
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "balanced_design_structural_evaluation_execution_parent_consistency_invalid"
        )
    if any(
        artifact.get("production_action") != "none"
        or artifact.get("new_model_created") is not False
        or artifact.get("promotion_gate_opened") is not False
        or artifact.get("p3_authorized") is not False
        for artifact in (
            preregistration_mainline_execution,
            preregistration,
            execution_handoff,
            preregistration_completion,
            feasibility_mainline_execution,
        )
    ):
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "balanced_design_structural_evaluation_execution_claim_boundary_invalid"
        )


def _expected_frozen_execution_contract() -> dict[str, Any]:
    return {
        "task_key": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_TASK_KEY,
        "capability": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_CAPABILITY,
        "completion_fact": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_EXECUTION_COMPLETION_FACT,
        "next_consumer": PREDICTION_V2_BALANCED_DESIGN_STRUCTURAL_EVALUATION_RESULT_DECISION_TASK_KEY,
        "registered_input_digests": [
            PREREGISTRATION_MAINLINE_EXECUTION_DIGEST,
            PREREGISTRATION_DIGEST,
            EXECUTION_HANDOFF_DIGEST,
            PREREGISTRATION_COMPLETION_DIGEST,
            FEASIBILITY_MAINLINE_EXECUTION_DIGEST,
            ORBIT_INVENTORY_DIGEST,
            SEARCH_RESULT_DIGEST,
        ],
        "research_request_id": 435,
        "research_execution_id": 356,
        "endpoint": "triple_collision_mass",
        "optimized_formula": (
            "sum_over_unordered_block_pairs_of_C(popcount(block_i_bitmask_and_"
            "block_j_bitmask),3)"
        ),
        "random_stream": "SHAKE256_COUNTER_MODE_RANDOM_BELOW_V1",
        "counter_encoding": "unsigned_128_bit_big_endian",
        "message_framing": "domain_utf8 || 0x00 || counter_u128_be",
        "sampling": "SPARSE_PARTIAL_FISHER_YATES_WITHOUT_REPLACEMENT_V1",
        "kernel": "NUMBA_PARALLEL_UINT64_PAIR_INTERSECTION_LOOKUP_V1",
        "primary_replicate_count": PRIMARY_REPLICATES,
        "secondary_replicate_count": SECONDARY_REPLICATES,
        "diagnostic_replicate_count_per_family": DIAGNOSTIC_REPLICATES,
        "primary_chunk_size": PRIMARY_CHUNK_SIZE,
        "secondary_chunk_size": SECONDARY_CHUNK_SIZE,
        "maximum_wall_seconds": MAXIMUM_WALL_SECONDS,
        "maximum_resident_memory_bytes": MAXIMUM_RESIDENT_BYTES,
        "duplicate_validation_pass": False,
        "membership_validation_pass": False,
        "uniqueness_validation_pass": False,
        "repetition_scan": REPETITION_SCAN,
        "historical_evidence": "INCONCLUSIVE",
        "new_evidence_created": False,
        "new_model_created": False,
        "promotion_gate_opened": False,
        "p3_authorized": False,
        "production_action": "none",
    }


def _claim_boundary() -> dict[str, Any]:
    return {
        "duplicate_membership_uniqueness_or_repetition_scans": 0,
        "duplicate_validation_pass": False,
        "membership_validation_pass": False,
        "uniqueness_validation_pass": False,
        "repetition_scan": REPETITION_SCAN,
        "database_queries_during_capability": 0,
        "historical_rows_read": 0,
        "folds_executed": 0,
        "historical_evidence": "INCONCLUSIVE",
        "prediction_v2_mode": "SHADOW_ONLY",
        "prediction_v2_route": "BASELINE_ONLY",
        "evidence_created": False,
        "new_model_created": False,
        "promotion_gate_opened": False,
        "p3_authorized": False,
        "production_action": "none",
    }


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
    domain: str,
) -> dict[str, Any]:
    payload = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "artifact_digest": "",
        **dict(body),
        "parent_digests": list(parent_digests),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _verify_artifact(artifact: Mapping[str, Any], *, domain: str) -> None:
    identity = dict(artifact)
    observed = identity.pop("artifact_digest", None)
    if observed != canonical_digest(identity, domain=domain):
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "balanced_design_structural_evaluation_execution_artifact_digest_invalid"
        )


def _random_domain(family: str, replicate_index: int) -> str:
    return (
        "dehps|prediction-v2|balanced-design|structural-evaluation|v1|"
        f"{family}|replicate={replicate_index}|stream"
    )


def _rotate_mask(mask: int, shift: int) -> int:
    shift %= POINT_COUNT
    if shift == 0:
        return mask
    point_mask = (1 << POINT_COUNT) - 1
    return ((mask << shift) | (mask >> (POINT_COUNT - shift))) & point_mask


def _resolved_thread_count(requested: int | None) -> int:
    maximum = int(numba_config.NUMBA_NUM_THREADS)
    detected = os.cpu_count() or 1
    selected = min(detected, maximum) if requested is None else int(requested)
    if not 1 <= selected <= maximum:
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "thread_count_out_of_range"
        )
    return selected


def _peak_resident_bytes() -> int:
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024


def _require_resource_budget(*, started: float) -> None:
    if time.monotonic() - started > MAXIMUM_WALL_SECONDS:
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "maximum_wall_seconds_exceeded"
        )
    if _peak_resident_bytes() > MAXIMUM_RESIDENT_BYTES:
        raise PredictionV2BalancedDesignStructuralEvaluationExecutionError(
            "maximum_resident_memory_exceeded"
        )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
