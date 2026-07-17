from __future__ import annotations

from dataclasses import dataclass
import resource
import time

import numpy as np

from dehps.scoring_kernel.contracts import (
    SCORE_ROUND_DIGITS,
    STRICT_CONTRACT_VERSION,
    CandidateStore,
    KernelRequest,
    KernelResult,
    KernelWorkspace,
    PackedWindowState,
    PreparedCandidateStore,
    WeightMatrix,
)
from dehps.scoring_kernel.telemetry import record_kernel_telemetry
from dehps.ranking_contract import STRICT_RANKING_CONTRACT


COMPONENT_COUNT = 32
QIAN_KUN_SIMILARITY = np.array(
    [[1 - (left ^ right).bit_count() / 6 for right in range(64)] for left in range(64)],
    dtype=np.float64,
)


@dataclass(frozen=True)
class TileResult:
    scores: np.ndarray
    better: np.ndarray
    equal_before: np.ndarray
    red5_mask: np.ndarray
    feature_seconds: float = 0.0
    kernel_seconds: float = 0.0
    rank_seconds: float = 0.0


def component_tile(
    store: CandidateStore,
    state: PackedWindowState,
    start: int,
    end: int,
) -> np.ndarray:
    numbers = store.numbers[start:end]
    masks = store.candidate_mask[start:end]
    row_count = end - start

    frequency_score = state.frequency_rate[numbers].sum(axis=1)
    short_hot_frequency_score = state.recent_frequency_rate[numbers].mean(axis=1)
    omission_score = state.omission_rate[numbers].mean(axis=1)
    long_omission_cooldown_score = np.clip(
        1 - np.power(state.recent_omission_pressure[numbers], 1.5).mean(axis=1),
        0.0,
        1.0,
    )
    candidate_consecutive_score = np.minimum(
        store.consecutive_pair_count[start:end], 5
    ).astype(np.float64) / 5
    previous_consecutive_score = (
        candidate_consecutive_score
        if state.previous_consecutive_pair_count > 0
        else 1 - candidate_consecutive_score
    )
    repeat_count = np.bitwise_count(masks & state.previous_number_mask).astype(np.uint8)
    previous_overlap_score = repeat_count.astype(np.float64) / 6
    previous_parity_shape_score = 1 - np.abs(
        store.odd_count[start:end].astype(np.float64) - state.previous_odd_count
    ) / 6
    dynamic_parity_transition_score = state.parity_transition[store.even_count[start:end]]
    previous_zone_shape_score = 1 - np.abs(
        store.zone_counts[start:end].astype(np.float64) - state.previous_zone_counts
    ).sum(axis=1) / 12
    recent_neighbor_score = state.recent_neighbor_rate[numbers].mean(axis=1)
    lagged_consecutive_score = np.bitwise_count(
        masks & state.lagged_number_mask
    ).astype(np.float64) / 6
    recent_gap_shape_score = np.maximum(
        0.0,
        1
        - np.abs(
            store.gaps[start:end].astype(np.float64) - state.recent_average_gaps
        ).sum(axis=1)
        / (5 * 32),
    )
    recent_sum_span_score = (
        np.maximum(
            0.0,
            1
            - np.abs(
                store.sum_value[start:end].astype(np.float64)
                - state.recent_average_sum
            )
            / 162,
        )
        + np.maximum(
            0.0,
            1
            - np.abs(
                store.span_value[start:end].astype(np.float64)
                - state.recent_average_span
            )
            / 32,
        )
    ) / 2

    qian_codes = store.qian_kun_code[start:end]
    qian_kun_pattern_score = state.qian_kun_rate[qian_codes]
    if len(state.recent_qian_codes):
        qian_kun_pattern_score = (
            qian_kun_pattern_score
            + QIAN_KUN_SIMILARITY[qian_codes][:, state.recent_qian_codes].max(axis=1)
        ) / 2

    zone_codes = (
        store.zone_counts[start:end, 0] * 49
        + store.zone_counts[start:end, 1] * 7
        + store.zone_counts[start:end, 2]
    ).astype(np.uint16)
    mod012_codes = (
        store.mod012_counts[start:end, 0] * 49
        + store.mod012_counts[start:end, 1] * 7
        + store.mod012_counts[start:end, 2]
    ).astype(np.uint16)
    first_last_sum_score = state.first_last_sum_rate[store.first_last_sum[start:end]]
    span_trend_score = state.span_bucket_rate[store.span_bucket[start:end]]
    sum_trend_score = state.sum_bucket_rate[store.sum_bucket[start:end]]
    ac_trend_score = state.ac_rate[store.ac_value[start:end]]
    zone_ratio_score = state.zone_rate[zone_codes]
    big_small_ratio_score = state.big_count_rate[store.big_count[start:end]]
    parity_ratio_score = state.even_count_rate[store.even_count[start:end]]
    prime_composite_score = state.prime_count_rate[store.prime_count[start:end]]
    mod012_score = state.mod012_rate[mod012_codes]
    tail_distribution_score = state.tail_unique_rate[store.tail_unique_count[start:end]]
    sum_tail_score = state.sum_tail_rate[store.sum_tail[start:end]]
    red_omission_shape_score = np.maximum(
        0.0, 1 - np.abs(omission_score - state.recent_average_omission)
    )
    sum_span_omission_score = (
        state.sum_bucket_omission[store.sum_bucket[start:end]]
        + state.span_bucket_omission[store.span_bucket[start:end]]
    ) / 2
    consecutive_trend_score = state.consecutive_rate[
        store.consecutive_pair_count[start:end]
    ]
    repeat_trend_score = state.repeat_rate[repeat_count]

    if state.stable_ranges_enabled:
        stable_sources = (
            store.sum_value[start:end],
            store.span_value[start:end],
            store.ac_value[start:end],
            store.first_last_sum[start:end],
            store.max_gap[start:end],
            store.min_gap[start:end],
        )
        stable_total = np.zeros(row_count, dtype=np.float64)
        for index, raw_values in enumerate(stable_sources):
            values = raw_values.astype(np.float64)
            lower = state.stable_lower[index]
            upper = state.stable_upper[index]
            width = max(upper - lower, 1.0)
            distance = np.where(
                values < lower,
                lower - values,
                np.where(values > upper, values - upper, 0.0),
            )
            stable_total += np.where(
                distance == 0,
                1.0,
                np.maximum(0.0, 1 - distance / width),
            )
        stable_range_score = stable_total / 6
    else:
        stable_range_score = np.ones(row_count, dtype=np.float64)

    if state.weekday_enabled:
        weekday_trend_score = (
            state.weekday_first_last_sum_rate[store.first_last_sum[start:end]]
            + state.weekday_span_bucket_rate[store.span_bucket[start:end]]
            + state.weekday_sum_bucket_rate[store.sum_bucket[start:end]]
            + state.weekday_ac_rate[store.ac_value[start:end]]
            + state.weekday_zone_rate[zone_codes]
            + state.weekday_big_count_rate[store.big_count[start:end]]
            + state.weekday_even_count_rate[store.even_count[start:end]]
            + state.weekday_prime_count_rate[store.prime_count[start:end]]
            + state.weekday_mod012_rate[mod012_codes]
            + state.weekday_tail_unique_rate[store.tail_unique_count[start:end]]
            + state.weekday_sum_tail_rate[store.sum_tail[start:end]]
            + state.weekday_consecutive_rate[store.consecutive_pair_count[start:end]]
            + state.weekday_repeat_rate[repeat_count]
        ) / 13
    else:
        weekday_trend_score = np.zeros(row_count, dtype=np.float64)

    return np.column_stack(
        (
            store.structural_score[start:end],
            frequency_score,
            omission_score,
            previous_consecutive_score,
            previous_overlap_score,
            previous_parity_shape_score,
            dynamic_parity_transition_score,
            previous_zone_shape_score,
            recent_neighbor_score,
            lagged_consecutive_score,
            recent_gap_shape_score,
            recent_sum_span_score,
            qian_kun_pattern_score,
            first_last_sum_score,
            span_trend_score,
            sum_trend_score,
            ac_trend_score,
            zone_ratio_score,
            big_small_ratio_score,
            parity_ratio_score,
            prime_composite_score,
            mod012_score,
            tail_distribution_score,
            sum_tail_score,
            red_omission_shape_score,
            sum_span_omission_score,
            consecutive_trend_score,
            repeat_trend_score,
            stable_range_score,
            weekday_trend_score,
            short_hot_frequency_score,
            long_omission_cooldown_score,
        )
    )


def _ordered_topk(
    candidate_ids: np.ndarray,
    scores: np.ndarray,
    top_k: int,
) -> tuple[np.ndarray, np.ndarray]:
    if top_k <= 0 or not len(candidate_ids):
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float64)
    limit = min(top_k, len(candidate_ids))
    if limit < len(candidate_ids):
        threshold = np.partition(scores, len(scores) - limit)[len(scores) - limit]
        better = np.flatnonzero(scores > threshold)
        equal = np.flatnonzero(scores == threshold)
        remaining = limit - len(better)
        if remaining < len(equal):
            equal_ids = candidate_ids[equal]
            chosen_equal = equal[np.argpartition(equal_ids, remaining - 1)[:remaining]]
        else:
            chosen_equal = equal
        selected = np.concatenate((better, chosen_equal))
    else:
        selected = np.arange(len(candidate_ids), dtype=np.int64)
    order = np.lexsort((candidate_ids[selected], -scores[selected]))
    chosen = selected[order[:limit]]
    return (
        np.ascontiguousarray(candidate_ids[chosen], dtype=np.int64),
        np.ascontiguousarray(scores[chosen], dtype=np.float64),
    )


class NumpyReferenceBackend:
    name = "numpy_reference"
    contract_version = STRICT_CONTRACT_VERSION

    def prepare(self, candidate_store: CandidateStore) -> PreparedCandidateStore:
        started = time.perf_counter()
        candidate_store.validate()
        return PreparedCandidateStore(
            store=candidate_store,
            backend_name=self.name,
            prepare_seconds=time.perf_counter() - started,
        )

    def _tile(
        self,
        store: CandidateStore,
        state: PackedWindowState,
        weights: np.ndarray,
        start: int,
        end: int,
        target_scores: np.ndarray,
        target_lex_ids: np.ndarray,
        exact_rank: bool,
        target_mask: np.uint64,
        red5: bool,
        workspace: KernelWorkspace,
    ) -> TileResult:
        feature_started = time.perf_counter()
        components = component_tile(store, state, start, end)
        feature_seconds = time.perf_counter() - feature_started
        kernel_started = time.perf_counter()
        scores = workspace.score_view(end - start, weights.shape[0])
        np.matmul(components, weights.T, out=scores)
        np.round(scores, SCORE_ROUND_DIGITS, out=scores)
        kernel_seconds = time.perf_counter() - kernel_started
        rank_started = time.perf_counter()
        ids = np.arange(start, end, dtype=np.int64)
        if exact_rank:
            better = (scores > target_scores).sum(axis=0, dtype=np.int64)
            equal_before = (
                (scores == target_scores) & (ids[:, None] < target_lex_ids)
            ).sum(axis=0, dtype=np.int64)
        else:
            better = np.zeros(weights.shape[0], dtype=np.int64)
            equal_before = np.zeros(weights.shape[0], dtype=np.int64)
        red5_flags = workspace.red5_view(end - start)
        if red5:
            red5_flags[:] = np.bitwise_count(
                store.candidate_mask[start:end] & target_mask
            ) == 5
        else:
            red5_flags.fill(0)
        rank_seconds = time.perf_counter() - rank_started
        return TileResult(
            scores=scores,
            better=np.ascontiguousarray(better),
            equal_before=np.ascontiguousarray(equal_before),
            red5_mask=red5_flags.view(np.bool_),
            feature_seconds=feature_seconds,
            kernel_seconds=kernel_seconds,
            rank_seconds=rank_seconds,
        )

    def score_rank(
        self,
        prepared_store: PreparedCandidateStore,
        window_state: PackedWindowState,
        weights: WeightMatrix,
        request: KernelRequest,
        workspace: KernelWorkspace | None = None,
    ) -> KernelResult:
        workspace = workspace or KernelWorkspace()
        store = prepared_store.store
        window_state.validate()
        request.validate(config_count=weights.config_count, candidate_count=len(store))
        if weights.values.shape[1] != COMPONENT_COUNT:
            raise ValueError(f"strict_v1 requires {COMPONENT_COUNT} components")
        started_wall = time.perf_counter()
        started_cpu = time.process_time()
        effective_top_k = min(request.top_k, len(store))
        better = np.zeros(weights.config_count, dtype=np.int64)
        equal_before = np.zeros(weights.config_count, dtype=np.int64)
        top_ids = [np.empty(0, dtype=np.int64) for _ in range(weights.config_count)]
        top_scores = [np.empty(0, dtype=np.float64) for _ in range(weights.config_count)]
        red5_ids = np.full(weights.config_count, -1, dtype=np.int64)
        red5_scores = np.full(weights.config_count, -np.inf, dtype=np.float64)
        target_lex_ids = np.full(weights.config_count, request.target_lex_id, dtype=np.int64)
        chunk_count = 0
        feature_seconds = 0.0
        kernel_seconds = 0.0
        rank_seconds = 0.0
        topk_merge_seconds = 0.0
        score_passes = 0

        if not request.target_excluded or request.top_k or request.red5:
            score_passes += 1
            for start in range(0, len(store), request.chunk_size):
                end = min(start + request.chunk_size, len(store))
                tile = self._tile(
                    store,
                    window_state,
                    weights.values,
                    start,
                    end,
                    request.target_scores,
                    target_lex_ids,
                    request.exact_rank and not request.target_excluded,
                    request.target_mask,
                    request.red5,
                    workspace,
                )
                feature_seconds += tile.feature_seconds
                kernel_seconds += tile.kernel_seconds
                rank_seconds += tile.rank_seconds
                merge_started = time.perf_counter()
                better += tile.better
                equal_before += tile.equal_before
                ids = np.arange(start, end, dtype=np.int64)
                for config_index in range(weights.config_count):
                    if effective_top_k:
                        merged_ids = np.concatenate((top_ids[config_index], ids))
                        merged_scores = np.concatenate(
                            (top_scores[config_index], tile.scores[:, config_index])
                        )
                        top_ids[config_index], top_scores[config_index] = _ordered_topk(
                            merged_ids, merged_scores, effective_top_k
                        )
                    if request.red5 and tile.red5_mask.any():
                        local_ids, local_scores = _ordered_topk(
                            ids[tile.red5_mask],
                            tile.scores[tile.red5_mask, config_index],
                            1,
                        )
                        merged_ids = np.concatenate(
                            (np.array([red5_ids[config_index]], dtype=np.int64), local_ids)
                        )
                        merged_scores = np.concatenate(
                            (np.array([red5_scores[config_index]], dtype=np.float64), local_scores)
                        )
                        valid = merged_ids >= 0
                        chosen_ids, chosen_scores = _ordered_topk(
                            merged_ids[valid], merged_scores[valid], 1
                        )
                        if len(chosen_ids):
                            red5_ids[config_index] = chosen_ids[0]
                            red5_scores[config_index] = chosen_scores[0]
                topk_merge_seconds += time.perf_counter() - merge_started
                chunk_count += 1

        if request.target_excluded and request.exact_rank:
            exact_ranks = np.full(weights.config_count, len(store) + 1, dtype=np.int64)
        elif request.exact_rank:
            exact_ranks = better + equal_before + 1
        else:
            exact_ranks = np.zeros(weights.config_count, dtype=np.int64)

        red5_ranks = np.full(weights.config_count, -1, dtype=np.int64)
        if request.red5 and np.any(red5_ids >= 0):
            score_passes += 1
            red5_better = np.zeros(weights.config_count, dtype=np.int64)
            red5_equal = np.zeros(weights.config_count, dtype=np.int64)
            for start in range(0, len(store), request.chunk_size):
                end = min(start + request.chunk_size, len(store))
                tile = self._tile(
                    store,
                    window_state,
                    weights.values,
                    start,
                    end,
                    red5_scores,
                    red5_ids,
                    True,
                    request.target_mask,
                    False,
                    workspace,
                )
                feature_seconds += tile.feature_seconds
                kernel_seconds += tile.kernel_seconds
                rank_seconds += tile.rank_seconds
                red5_better += tile.better
                red5_equal += tile.equal_before
                chunk_count += 1
            valid = red5_ids >= 0
            red5_ranks[valid] = red5_better[valid] + red5_equal[valid] + 1

        top_id_matrix = np.full(
            (weights.config_count, effective_top_k), -1, dtype=np.int64
        )
        top_score_matrix = np.full(
            (weights.config_count, effective_top_k), -np.inf, dtype=np.float64
        )
        for config_index in range(weights.config_count):
            count = len(top_ids[config_index])
            top_id_matrix[config_index, :count] = top_ids[config_index]
            top_score_matrix[config_index, :count] = top_scores[config_index]

        wall_seconds = time.perf_counter() - started_wall
        cpu_seconds = time.process_time() - started_cpu
        score_cells = len(store) * weights.config_count * score_passes
        tile_rows = min(request.chunk_size, len(store))
        score_workspace_bytes = tile_rows * weights.config_count * 8 + tile_rows
        component_workspace_bytes = (
            tile_rows * COMPONENT_COUNT * 8
            if self.name == "numpy_reference"
            else 0
        )
        candidate_envelope = store.candidate_runtime_envelope
        candidate_contract = candidate_envelope["candidate_contract"]
        if not isinstance(candidate_contract, dict):
            raise ValueError("candidate runtime envelope contract must be structured")
        telemetry: dict[str, int | float | str] = {
            "backend": self.name,
            "contract_version": self.contract_version,
            "ranking_contract": STRICT_RANKING_CONTRACT,
            "candidate_store_version": store.store_version,
            "candidate_count": len(store),
            "candidate_contract": str(candidate_contract["contract_key"]),
            "candidate_abi": str(candidate_envelope["candidate_abi"]),
            "candidate_digest": str(candidate_envelope["candidate_digest"]),
            "candidate_layout_digest": str(candidate_envelope["layout_digest"]),
            "candidate_package_digest": str(candidate_envelope["package_digest"]),
            "candidate_identity_id_kind": "candidate_store_row_index",
            "window_id": request.window_id,
            "config_count": weights.config_count,
            "score_cells": score_cells,
            "chunk_size": request.chunk_size,
            "chunk_count": chunk_count,
            "worker_count": request.worker_count,
            "prepare_time": prepared_store.prepare_seconds,
            "feature_time": feature_seconds,
            "kernel_time": kernel_seconds,
            "rank_time": rank_seconds,
            "topk_merge_time": topk_merge_seconds,
            "wall_time": wall_seconds,
            "cpu_time": cpu_seconds,
            "peak_rss": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
            "peak_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
            "cells_per_second": score_cells / wall_seconds if wall_seconds else 0.0,
            "bytes_read_estimate": int(
                len(store)
                * weights.config_count
                * COMPONENT_COUNT
                * 8
                * score_passes
            ),
            "workspace_bytes_estimate": int(
                score_workspace_bytes + component_workspace_bytes
            ),
        }
        result = KernelResult(
            backend=self.name,
            contract_version=self.contract_version,
            target_scores=np.ascontiguousarray(request.target_scores.copy()),
            exact_ranks=np.ascontiguousarray(exact_ranks),
            top_candidate_ids=np.ascontiguousarray(top_id_matrix),
            top_scores=np.ascontiguousarray(top_score_matrix),
            red5_candidate_ids=np.ascontiguousarray(red5_ids),
            red5_scores=np.ascontiguousarray(red5_scores),
            red5_ranks=np.ascontiguousarray(red5_ranks),
            telemetry=telemetry,
        )
        record_kernel_telemetry(telemetry)
        return result
