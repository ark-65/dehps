from __future__ import annotations

import math
from hashlib import sha256

import numpy as np

from dehps.input_contracts import CandidateArrayCompiler, CandidateUniverseManifest
from dehps.models.frequency_ranker import FrequencyStats
from dehps.scoring_kernel.contracts import CandidateStore, PackedWindowState


CANDIDATE_STORE_VERSION = "dehps-candidate-store-v1"
CANDIDATE_ABI_ADAPTER_VERSION = "candidate-store-to-candidate-abi-adapter.v1"
STABLE_RANGE_KEYS = ("sum_value", "span_value", "ac_numeric", "first_last_sum", "max_gap", "min_gap")


def _float_array(values, *, size: int, default: float = 0.0) -> np.ndarray:
    result = np.full(size, default, dtype=np.float64)
    for raw_key, raw_value in values.items():
        key = int(raw_key)
        if 0 <= key < size:
            result[key] = float(raw_value)
    return np.ascontiguousarray(result)


def _tuple_code(value: object) -> int:
    first, second, third = tuple(int(item) for item in value)  # type: ignore[arg-type]
    return first * 49 + second * 7 + third


def _profile_array(stats: FrequencyStats, key: str, size: int, *, weekday: bool = False) -> np.ndarray:
    source = stats.weekday_profile_rates if weekday else stats.shape_profile_rates
    values = source.get(key, {})
    result = np.zeros(size, dtype=np.float64)
    tuple_key = key in {"zone_signature", "mod012_signature"}
    for raw_key, raw_value in values.items():
        encoded = _tuple_code(raw_key) if tuple_key else int(raw_key)
        if 0 <= encoded < size:
            result[encoded] = float(raw_value)
    return np.ascontiguousarray(result)


def numbers_mask(numbers: tuple[int, ...] | list[int] | np.ndarray) -> np.uint64:
    mask = np.uint64(0)
    for raw_number in numbers:
        number = int(raw_number)
        if not 1 <= number <= 33:
            raise ValueError("red numbers must be between 1 and 33")
        mask |= np.uint64(1) << np.uint64(number - 1)
    return mask


def _candidate_masks(numbers: np.ndarray) -> np.ndarray:
    result = np.zeros(numbers.shape[0], dtype=np.uint64)
    for column in range(6):
        result |= np.left_shift(np.uint64(1), numbers[:, column].astype(np.uint64) - np.uint64(1))
    return np.ascontiguousarray(result)


def _lex_codes(numbers: np.ndarray) -> np.ndarray:
    result = np.zeros(numbers.shape[0], dtype=np.uint64)
    for column in range(6):
        result = result * np.uint64(34) + numbers[:, column].astype(np.uint64)
    return np.ascontiguousarray(result)


def _candidate_lex_ids(
    numbers: np.ndarray,
    *,
    domain_size: int = 33,
    pick_count: int = 6,
) -> np.ndarray:
    if numbers.dtype != np.uint8 or numbers.shape[1:] != (pick_count,):
        raise ValueError("candidate ABI adapter requires uint8[N,6] numbers")
    lex_id = np.zeros(numbers.shape[0], dtype=np.uint64)
    previous = np.zeros(numbers.shape[0], dtype=np.uint8)
    for column in range(pick_count):
        remaining = pick_count - column - 1
        current = numbers[:, column]
        for skipped in range(1, domain_size + 1):
            add = np.uint64(math.comb(domain_size - skipped, remaining))
            if add:
                lex_id += ((previous < skipped) & (current > skipped)).astype(np.uint64) * add
        previous = current
    if np.any(lex_id > np.iinfo(np.uint32).max):
        raise ValueError("candidate lex_id exceeds uint32")
    return np.ascontiguousarray(lex_id, dtype=np.dtype("<u4"))


def _candidate_abi_package(numbers: np.ndarray, candidate_masks: np.ndarray):
    if not numbers.flags.c_contiguous or numbers.dtype != np.uint8:
        raise ValueError("Candidate ABI adapter requires C-contiguous uint8 numbers")
    if not candidate_masks.flags.c_contiguous or candidate_masks.dtype != np.dtype("<u8"):
        raise ValueError("Candidate ABI adapter requires C-contiguous little-endian uint64 masks")
    universe = CandidateUniverseManifest(domain_size=33, pick_count=6)
    return CandidateArrayCompiler().compile(
        universe=universe,
        numbers=numbers,
        mask=candidate_masks,
        lex_id=_candidate_lex_ids(
            numbers,
            domain_size=universe.domain_size,
            pick_count=universe.pick_count,
        ),
    )


def target_lex_id(store: CandidateStore, numbers: tuple[int, ...]) -> int:
    code = np.uint64(0)
    for number in numbers:
        code = code * np.uint64(34) + np.uint64(number)
    return int(np.searchsorted(store.lex_code, code, side="left"))


def candidate_store_from_matrix(matrix) -> CandidateStore:
    numbers = np.ascontiguousarray(matrix.numbers, dtype=np.uint8)
    candidate_masks = _candidate_masks(numbers)
    candidate_abi_package = _candidate_abi_package(numbers, candidate_masks)
    cache_info = getattr(matrix, "cache_info", {}) or {}
    source = str(cache_info.get("cache_key") or cache_info.get("feature_schema_version") or "in-memory")
    fingerprint = sha256(
        (
            f"{CANDIDATE_STORE_VERSION}:{CANDIDATE_ABI_ADAPTER_VERSION}:"
            f"{source}:{len(numbers)}:{candidate_abi_package.package_digest}"
        ).encode("utf-8")
    ).hexdigest()
    store = CandidateStore(
        numbers=numbers,
        candidate_mask=candidate_masks,
        lex_code=_lex_codes(numbers),
        structural_score=np.ascontiguousarray(matrix.structural_score, dtype=np.float64),
        consecutive_pair_count=np.ascontiguousarray(matrix.consecutive_pair_count),
        odd_count=np.ascontiguousarray(matrix.odd_count),
        zone_counts=np.ascontiguousarray(matrix.zone_counts),
        gaps=np.ascontiguousarray(matrix.gaps),
        sum_value=np.ascontiguousarray(matrix.sum_value),
        span_value=np.ascontiguousarray(matrix.span_value),
        qian_kun_code=np.ascontiguousarray(matrix.qian_kun_code),
        first_last_sum=np.ascontiguousarray(matrix.first_last_sum),
        sum_bucket=np.ascontiguousarray(matrix.sum_bucket),
        span_bucket=np.ascontiguousarray(matrix.span_bucket),
        ac_value=np.ascontiguousarray(matrix.ac_value),
        big_count=np.ascontiguousarray(matrix.big_count),
        even_count=np.ascontiguousarray(matrix.even_count),
        prime_count=np.ascontiguousarray(matrix.prime_count),
        mod012_counts=np.ascontiguousarray(matrix.mod012_counts),
        tail_unique_count=np.ascontiguousarray(matrix.tail_unique_count),
        sum_tail=np.ascontiguousarray(matrix.sum_tail),
        max_gap=np.ascontiguousarray(matrix.max_gap),
        min_gap=np.ascontiguousarray(matrix.min_gap),
        store_version=CANDIDATE_STORE_VERSION,
        fingerprint=fingerprint,
        candidate_abi_package=candidate_abi_package,
    )
    store.validate()
    cache_info["candidate_abi"] = candidate_abi_package.runtime_envelope.as_dict()
    cache_info["candidate_abi_adapter_version"] = CANDIDATE_ABI_ADAPTER_VERSION
    cache_info["candidate_store_fingerprint"] = fingerprint
    return store


def pack_window_state(stats: FrequencyStats) -> PackedWindowState:
    qian = np.zeros(64, dtype=np.float64)
    for pattern, value in stats.qian_kun_pattern_rate.items():
        qian[int(pattern, 2)] = float(value)
    stable_lower = np.zeros(6, dtype=np.float64)
    stable_upper = np.zeros(6, dtype=np.float64)
    for index, key in enumerate(STABLE_RANGE_KEYS):
        stable_lower[index], stable_upper[index] = stats.stable_ranges.get(key, (0.0, 0.0))
    state = PackedWindowState(
        frequency_rate=_float_array(stats.frequency_rate, size=34),
        recent_frequency_rate=_float_array(stats.recent_frequency_rate, size=34),
        omission_rate=_float_array(stats.omission_rate, size=34),
        recent_omission_pressure=_float_array(stats.recent_omission_pressure, size=34),
        recent_neighbor_rate=_float_array(stats.recent_neighbor_rate, size=34),
        previous_number_mask=numbers_mask(stats.previous_numbers),
        previous_consecutive_pair_count=int(stats.previous_consecutive_pair_count),
        previous_odd_count=int(stats.previous_odd_count),
        parity_transition=np.ascontiguousarray(stats.parity_transition_score_by_even_count, dtype=np.float64),
        previous_zone_counts=np.ascontiguousarray(stats.previous_zone_counts, dtype=np.float64),
        lagged_number_mask=numbers_mask(tuple(stats.lagged_consecutive_number_set)),
        recent_average_gaps=np.ascontiguousarray(stats.recent_average_gaps, dtype=np.float64),
        recent_average_sum=float(stats.recent_average_sum),
        recent_average_span=float(stats.recent_average_span),
        qian_kun_rate=np.ascontiguousarray(qian),
        recent_qian_codes=np.ascontiguousarray([int(value, 2) for value in stats.recent_qian_kun_patterns], dtype=np.uint8),
        first_last_sum_rate=_profile_array(stats, "first_last_sum", 67),
        span_bucket_rate=_profile_array(stats, "span_bucket", 12),
        sum_bucket_rate=_profile_array(stats, "sum_bucket", 20),
        ac_rate=_profile_array(stats, "ac_value", 16),
        zone_rate=_profile_array(stats, "zone_signature", 343),
        big_count_rate=_profile_array(stats, "big_count", 7),
        even_count_rate=_profile_array(stats, "even_count", 7),
        prime_count_rate=_profile_array(stats, "prime_count", 7),
        mod012_rate=_profile_array(stats, "mod012_signature", 343),
        tail_unique_rate=_profile_array(stats, "tail_unique_count", 7),
        sum_tail_rate=_profile_array(stats, "sum_tail", 10),
        consecutive_rate=_profile_array(stats, "consecutive_pair_count", 6),
        repeat_rate=_profile_array(stats, "repeat_count", 7),
        sum_bucket_omission=_float_array(stats.sum_bucket_omission_rate, size=20, default=1.0),
        span_bucket_omission=_float_array(stats.span_bucket_omission_rate, size=12, default=1.0),
        recent_average_omission=float(stats.recent_average_omission),
        stable_ranges_enabled=bool(stats.stable_ranges),
        stable_lower=np.ascontiguousarray(stable_lower),
        stable_upper=np.ascontiguousarray(stable_upper),
        weekday_enabled=bool(stats.target_weekday is not None and stats.weekday_profile_rates),
        weekday_first_last_sum_rate=_profile_array(stats, "first_last_sum", 67, weekday=True),
        weekday_span_bucket_rate=_profile_array(stats, "span_bucket", 12, weekday=True),
        weekday_sum_bucket_rate=_profile_array(stats, "sum_bucket", 20, weekday=True),
        weekday_ac_rate=_profile_array(stats, "ac_value", 16, weekday=True),
        weekday_zone_rate=_profile_array(stats, "zone_signature", 343, weekday=True),
        weekday_big_count_rate=_profile_array(stats, "big_count", 7, weekday=True),
        weekday_even_count_rate=_profile_array(stats, "even_count", 7, weekday=True),
        weekday_prime_count_rate=_profile_array(stats, "prime_count", 7, weekday=True),
        weekday_mod012_rate=_profile_array(stats, "mod012_signature", 343, weekday=True),
        weekday_tail_unique_rate=_profile_array(stats, "tail_unique_count", 7, weekday=True),
        weekday_sum_tail_rate=_profile_array(stats, "sum_tail", 10, weekday=True),
        weekday_consecutive_rate=_profile_array(stats, "consecutive_pair_count", 6, weekday=True),
        weekday_repeat_rate=_profile_array(stats, "repeat_count", 7, weekday=True),
    )
    state.validate()
    return state
