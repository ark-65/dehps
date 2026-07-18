from __future__ import annotations

from dataclasses import replace
import time

import numpy as np
from numba import config as numba_config
from numba import get_num_threads, get_thread_id, njit, prange, set_num_threads

from dehps.scoring_kernel.contracts import (
    SCORE_ROUND_DIGITS,
    KernelRequest,
    KernelResult,
    KernelWorkspace,
    WeightMatrix,
)
from dehps.scoring_kernel.feature_abi_backend import (
    FeatureABINumpyReferenceBackend,
    FeatureABITileResult,
    PreparedFeatureABIRuntime,
)


@njit(inline="always")
def _popcount(value: np.uint64) -> int:
    count = 0
    while value:
        value &= value - np.uint64(1)
        count += 1
    return count


@njit(parallel=True, fastmath=False)
def _score_rank_feature_tile(
    start,
    values,
    candidate_masks,
    weights,
    target_scores,
    target_ids,
    exact_rank,
    target_mask,
    red5,
    scores,
    red5_flags,
):
    """Score anonymous Feature ABI rows without interpreting Feature semantics."""

    row_count = values.shape[0]
    config_count = weights.shape[0]
    component_count = values.shape[1]
    better_local = np.zeros((get_num_threads(), config_count), dtype=np.int64)
    equal_local = np.zeros((get_num_threads(), config_count), dtype=np.int64)

    for row in prange(row_count):
        thread_id = get_thread_id()
        candidate_id = start + row
        for config in range(config_count):
            score = 0.0
            for component in range(component_count):
                score += values[row, component] * weights[config, component]
            score = np.round(score, SCORE_ROUND_DIGITS)
            scores[row, config] = score
            if exact_rank:
                if score > target_scores[config]:
                    better_local[thread_id, config] += 1
                elif score == target_scores[config] and candidate_id < target_ids[config]:
                    equal_local[thread_id, config] += 1
        red5_flags[row] = (
            1
            if red5 and _popcount(candidate_masks[row] & target_mask) == 5
            else 0
        )

    return scores, better_local, equal_local, red5_flags


class FeatureABINumbaCpuBackend(FeatureABINumpyReferenceBackend):
    """Numba implementation of the sealed Feature ABI scoring boundary."""

    name = "feature_abi_numba_cpu"

    def _tile(
        self,
        *,
        values: np.ndarray,
        candidate_masks: np.ndarray,
        start: int,
        weights: np.ndarray,
        target_scores: np.ndarray,
        target_ids: np.ndarray,
        exact_rank: bool,
        target_mask: np.uint64,
        red5: bool,
        workspace: KernelWorkspace,
    ) -> FeatureABITileResult:
        row_count = len(values)
        scores = workspace.score_view(row_count, weights.shape[0])
        red5_flags = workspace.red5_view(row_count)
        kernel_started = time.perf_counter()
        scores, better_local, equal_local, red5_flags = _score_rank_feature_tile(
            start,
            values,
            candidate_masks,
            weights,
            target_scores,
            target_ids,
            exact_rank,
            target_mask,
            red5,
            scores,
            red5_flags,
        )
        kernel_seconds = time.perf_counter() - kernel_started
        return FeatureABITileResult(
            scores=scores,
            better=np.ascontiguousarray(better_local.sum(axis=0), dtype=np.int64),
            equal_before=np.ascontiguousarray(equal_local.sum(axis=0), dtype=np.int64),
            red5_mask=red5_flags.view(np.bool_),
            kernel_seconds=kernel_seconds,
            rank_seconds=0.0,
        )

    def score_rank(
        self,
        prepared: PreparedFeatureABIRuntime,
        weights: WeightMatrix,
        request: KernelRequest,
        workspace: KernelWorkspace | None = None,
    ) -> KernelResult:
        effective_workers = min(
            request.worker_count,
            int(numba_config.NUMBA_NUM_THREADS),
        )
        set_num_threads(effective_workers)
        effective_request = (
            request
            if effective_workers == request.worker_count
            else replace(request, worker_count=effective_workers)
        )
        return super().score_rank(
            prepared,
            weights,
            effective_request,
            workspace,
        )
