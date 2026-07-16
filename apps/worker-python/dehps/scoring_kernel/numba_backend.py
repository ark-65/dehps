from __future__ import annotations

from dataclasses import replace
import time

import numpy as np
from numba import config as numba_config
from numba import get_num_threads, get_thread_id, njit, prange, set_num_threads

from dehps.scoring_kernel.contracts import (
    SCORE_ROUND_DIGITS,
    CandidateStore,
    KernelWorkspace,
    PackedWindowState,
)
from dehps.scoring_kernel.numpy_backend import NumpyReferenceBackend, TileResult


@njit(inline="always")
def _popcount(value: np.uint64) -> int:
    count = 0
    while value:
        value &= value - np.uint64(1)
        count += 1
    return count


@njit(parallel=True, fastmath=False)
def _score_rank_tile(
    start,
    numbers,
    candidate_masks,
    structural_score,
    consecutive_pair_count,
    odd_count,
    zone_counts,
    gaps,
    sum_value,
    span_value,
    qian_kun_code,
    first_last_sum,
    sum_bucket,
    span_bucket,
    ac_value,
    big_count,
    even_count,
    prime_count,
    mod012_counts,
    tail_unique_count,
    sum_tail,
    max_gap,
    min_gap,
    frequency_rate,
    recent_frequency_rate,
    omission_rate,
    recent_omission_pressure,
    recent_neighbor_rate,
    previous_number_mask,
    previous_consecutive_pair_count,
    previous_odd_count,
    parity_transition,
    previous_zone_counts,
    lagged_number_mask,
    recent_average_gaps,
    recent_average_sum,
    recent_average_span,
    qian_kun_rate,
    recent_qian_codes,
    first_last_sum_rate,
    span_bucket_rate,
    sum_bucket_rate,
    ac_rate,
    zone_rate,
    big_count_rate,
    even_count_rate,
    prime_count_rate,
    mod012_rate,
    tail_unique_rate,
    sum_tail_rate,
    consecutive_rate,
    repeat_rate,
    sum_bucket_omission,
    span_bucket_omission,
    recent_average_omission,
    stable_ranges_enabled,
    stable_lower,
    stable_upper,
    weekday_enabled,
    weekday_first_last_sum_rate,
    weekday_span_bucket_rate,
    weekday_sum_bucket_rate,
    weekday_ac_rate,
    weekday_zone_rate,
    weekday_big_count_rate,
    weekday_even_count_rate,
    weekday_prime_count_rate,
    weekday_mod012_rate,
    weekday_tail_unique_rate,
    weekday_sum_tail_rate,
    weekday_consecutive_rate,
    weekday_repeat_rate,
    weights,
    target_scores,
    target_lex_ids,
    exact_rank,
    target_mask,
    red5,
    scores,
    red5_flags,
):
    row_count = numbers.shape[0]
    config_count = weights.shape[0]
    better_local = np.zeros((get_num_threads(), config_count), dtype=np.int64)
    equal_local = np.zeros((get_num_threads(), config_count), dtype=np.int64)

    for row in prange(row_count):
        components = np.empty(32, dtype=np.float64)
        frequency = 0.0
        recent_frequency = 0.0
        omission = 0.0
        omission_pressure = 0.0
        neighbor = 0.0
        for column in range(6):
            number = numbers[row, column]
            frequency += frequency_rate[number]
            recent_frequency += recent_frequency_rate[number]
            omission += omission_rate[number]
            omission_pressure += recent_omission_pressure[number] ** 1.5
            neighbor += recent_neighbor_rate[number]
        recent_frequency /= 6.0
        omission /= 6.0
        omission_pressure = min(1.0, max(0.0, 1.0 - omission_pressure / 6.0))

        consecutive = min(consecutive_pair_count[row], 5) / 5.0
        previous_consecutive = (
            consecutive if previous_consecutive_pair_count > 0 else 1.0 - consecutive
        )
        repeat_count = _popcount(candidate_masks[row] & previous_number_mask)
        previous_overlap = repeat_count / 6.0
        previous_parity = 1.0 - abs(float(odd_count[row]) - previous_odd_count) / 6.0
        dynamic_parity = parity_transition[even_count[row]]
        zone_distance = 0.0
        for column in range(3):
            zone_distance += abs(float(zone_counts[row, column]) - previous_zone_counts[column])
        previous_zone = 1.0 - zone_distance / 12.0
        neighbor /= 6.0
        lagged = _popcount(candidate_masks[row] & lagged_number_mask) / 6.0
        gap_distance = 0.0
        for column in range(5):
            gap_distance += abs(float(gaps[row, column]) - recent_average_gaps[column])
        gap_score = max(0.0, 1.0 - gap_distance / 160.0)
        recent_sum_score = max(
            0.0, 1.0 - abs(float(sum_value[row]) - recent_average_sum) / 162.0
        )
        recent_span_score = max(
            0.0, 1.0 - abs(float(span_value[row]) - recent_average_span) / 32.0
        )
        recent_sum_span = (recent_sum_score + recent_span_score) / 2.0

        qian_code = qian_kun_code[row]
        qian_score = qian_kun_rate[qian_code]
        if recent_qian_codes.shape[0]:
            recent_qian_score = 0.0
            for index in range(recent_qian_codes.shape[0]):
                similarity = 1.0 - _popcount(
                    np.uint64(qian_code ^ recent_qian_codes[index])
                ) / 6.0
                recent_qian_score = max(recent_qian_score, similarity)
            qian_score = (qian_score + recent_qian_score) / 2.0

        zone_code = (
            int(zone_counts[row, 0]) * 49
            + int(zone_counts[row, 1]) * 7
            + int(zone_counts[row, 2])
        )
        mod_code = (
            int(mod012_counts[row, 0]) * 49
            + int(mod012_counts[row, 1]) * 7
            + int(mod012_counts[row, 2])
        )
        red_omission = max(0.0, 1.0 - abs(omission - recent_average_omission))
        sum_span_omission = (
            sum_bucket_omission[sum_bucket[row]]
            + span_bucket_omission[span_bucket[row]]
        ) / 2.0

        stable_score = 1.0
        if stable_ranges_enabled:
            stable_values = (
                float(sum_value[row]),
                float(span_value[row]),
                float(ac_value[row]),
                float(first_last_sum[row]),
                float(max_gap[row]),
                float(min_gap[row]),
            )
            stable_total = 0.0
            for index in range(6):
                lower = stable_lower[index]
                upper = stable_upper[index]
                width = max(upper - lower, 1.0)
                value = stable_values[index]
                distance = lower - value if value < lower else value - upper if value > upper else 0.0
                stable_total += 1.0 if distance == 0.0 else max(0.0, 1.0 - distance / width)
            stable_score = stable_total / 6.0

        weekday_score = 0.0
        if weekday_enabled:
            weekday_score = (
                weekday_first_last_sum_rate[first_last_sum[row]]
                + weekday_span_bucket_rate[span_bucket[row]]
                + weekday_sum_bucket_rate[sum_bucket[row]]
                + weekday_ac_rate[ac_value[row]]
                + weekday_zone_rate[zone_code]
                + weekday_big_count_rate[big_count[row]]
                + weekday_even_count_rate[even_count[row]]
                + weekday_prime_count_rate[prime_count[row]]
                + weekday_mod012_rate[mod_code]
                + weekday_tail_unique_rate[tail_unique_count[row]]
                + weekday_sum_tail_rate[sum_tail[row]]
                + weekday_consecutive_rate[consecutive_pair_count[row]]
                + weekday_repeat_rate[repeat_count]
            ) / 13.0

        components[0] = structural_score[row]
        components[1] = frequency
        components[2] = omission
        components[3] = previous_consecutive
        components[4] = previous_overlap
        components[5] = previous_parity
        components[6] = dynamic_parity
        components[7] = previous_zone
        components[8] = neighbor
        components[9] = lagged
        components[10] = gap_score
        components[11] = recent_sum_span
        components[12] = qian_score
        components[13] = first_last_sum_rate[first_last_sum[row]]
        components[14] = span_bucket_rate[span_bucket[row]]
        components[15] = sum_bucket_rate[sum_bucket[row]]
        components[16] = ac_rate[ac_value[row]]
        components[17] = zone_rate[zone_code]
        components[18] = big_count_rate[big_count[row]]
        components[19] = even_count_rate[even_count[row]]
        components[20] = prime_count_rate[prime_count[row]]
        components[21] = mod012_rate[mod_code]
        components[22] = tail_unique_rate[tail_unique_count[row]]
        components[23] = sum_tail_rate[sum_tail[row]]
        components[24] = red_omission
        components[25] = sum_span_omission
        components[26] = consecutive_rate[consecutive_pair_count[row]]
        components[27] = repeat_rate[repeat_count]
        components[28] = stable_score
        components[29] = weekday_score
        components[30] = recent_frequency
        components[31] = omission_pressure

        thread_id = get_thread_id()
        lex_id = start + row
        for config in range(config_count):
            score = 0.0
            for component in range(32):
                score += components[component] * weights[config, component]
            score = np.round(score, SCORE_ROUND_DIGITS)
            scores[row, config] = score
            if exact_rank:
                if score > target_scores[config]:
                    better_local[thread_id, config] += 1
                elif score == target_scores[config] and lex_id < target_lex_ids[config]:
                    equal_local[thread_id, config] += 1
        red5_flags[row] = (
            1 if red5 and _popcount(candidate_masks[row] & target_mask) == 5 else 0
        )

    return scores, better_local, equal_local, red5_flags


class NumbaCpuBackend(NumpyReferenceBackend):
    name = "numba_cpu"

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
        scores = workspace.score_view(end - start, weights.shape[0])
        red5_flags = workspace.red5_view(end - start)
        kernel_started = time.perf_counter()
        scores, better_local, equal_local, red5_flags = _score_rank_tile(
            start,
            store.numbers[start:end],
            store.candidate_mask[start:end],
            store.structural_score[start:end],
            store.consecutive_pair_count[start:end],
            store.odd_count[start:end],
            store.zone_counts[start:end],
            store.gaps[start:end],
            store.sum_value[start:end],
            store.span_value[start:end],
            store.qian_kun_code[start:end],
            store.first_last_sum[start:end],
            store.sum_bucket[start:end],
            store.span_bucket[start:end],
            store.ac_value[start:end],
            store.big_count[start:end],
            store.even_count[start:end],
            store.prime_count[start:end],
            store.mod012_counts[start:end],
            store.tail_unique_count[start:end],
            store.sum_tail[start:end],
            store.max_gap[start:end],
            store.min_gap[start:end],
            state.frequency_rate,
            state.recent_frequency_rate,
            state.omission_rate,
            state.recent_omission_pressure,
            state.recent_neighbor_rate,
            state.previous_number_mask,
            state.previous_consecutive_pair_count,
            state.previous_odd_count,
            state.parity_transition,
            state.previous_zone_counts,
            state.lagged_number_mask,
            state.recent_average_gaps,
            state.recent_average_sum,
            state.recent_average_span,
            state.qian_kun_rate,
            state.recent_qian_codes,
            state.first_last_sum_rate,
            state.span_bucket_rate,
            state.sum_bucket_rate,
            state.ac_rate,
            state.zone_rate,
            state.big_count_rate,
            state.even_count_rate,
            state.prime_count_rate,
            state.mod012_rate,
            state.tail_unique_rate,
            state.sum_tail_rate,
            state.consecutive_rate,
            state.repeat_rate,
            state.sum_bucket_omission,
            state.span_bucket_omission,
            state.recent_average_omission,
            state.stable_ranges_enabled,
            state.stable_lower,
            state.stable_upper,
            state.weekday_enabled,
            state.weekday_first_last_sum_rate,
            state.weekday_span_bucket_rate,
            state.weekday_sum_bucket_rate,
            state.weekday_ac_rate,
            state.weekday_zone_rate,
            state.weekday_big_count_rate,
            state.weekday_even_count_rate,
            state.weekday_prime_count_rate,
            state.weekday_mod012_rate,
            state.weekday_tail_unique_rate,
            state.weekday_sum_tail_rate,
            state.weekday_consecutive_rate,
            state.weekday_repeat_rate,
            weights,
            target_scores,
            target_lex_ids,
            exact_rank,
            target_mask,
            red5,
            scores,
            red5_flags,
        )
        kernel_seconds = time.perf_counter() - kernel_started
        return TileResult(
            scores=scores,
            better=np.ascontiguousarray(better_local.sum(axis=0), dtype=np.int64),
            equal_before=np.ascontiguousarray(equal_local.sum(axis=0), dtype=np.int64),
            red5_mask=red5_flags.view(np.bool_),
            kernel_seconds=kernel_seconds,
        )

    def score_rank(self, prepared_store, window_state, weights, request, workspace=None):
        effective_workers = min(
            request.worker_count, int(numba_config.NUMBA_NUM_THREADS)
        )
        set_num_threads(effective_workers)
        effective_request = (
            request
            if effective_workers == request.worker_count
            else replace(request, worker_count=effective_workers)
        )
        return super().score_rank(
            prepared_store,
            window_state,
            weights,
            effective_request,
            workspace,
        )
