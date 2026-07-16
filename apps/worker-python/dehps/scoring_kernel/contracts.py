from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np


STRICT_CONTRACT_VERSION = "dehps-scoring-strict-v1"
SCORE_ROUND_DIGITS = 8
COMPONENT_DTYPE = np.dtype(np.float64)
WEIGHT_DTYPE = np.dtype(np.float64)


@dataclass(frozen=True)
class CandidateStore:
    """Fixed-dtype candidate data plane; no Python candidate objects enter a backend."""

    numbers: np.ndarray
    candidate_mask: np.ndarray
    lex_code: np.ndarray
    structural_score: np.ndarray
    consecutive_pair_count: np.ndarray
    odd_count: np.ndarray
    zone_counts: np.ndarray
    gaps: np.ndarray
    sum_value: np.ndarray
    span_value: np.ndarray
    qian_kun_code: np.ndarray
    first_last_sum: np.ndarray
    sum_bucket: np.ndarray
    span_bucket: np.ndarray
    ac_value: np.ndarray
    big_count: np.ndarray
    even_count: np.ndarray
    prime_count: np.ndarray
    mod012_counts: np.ndarray
    tail_unique_count: np.ndarray
    sum_tail: np.ndarray
    max_gap: np.ndarray
    min_gap: np.ndarray
    store_version: str
    fingerprint: str

    def __len__(self) -> int:
        return int(self.numbers.shape[0])

    def validate(self) -> None:
        row_count = len(self)
        if self.numbers.dtype != np.uint8 or self.numbers.shape != (row_count, 6):
            raise ValueError("candidate numbers must be uint8[N,6]")
        if self.candidate_mask.dtype != np.uint64 or self.candidate_mask.shape != (row_count,):
            raise ValueError("candidate_mask must be uint64[N]")
        if self.lex_code.dtype != np.uint64 or self.lex_code.shape != (row_count,):
            raise ValueError("lex_code must be uint64[N]")
        if row_count > 1 and not bool(np.all(self.lex_code[1:] > self.lex_code[:-1])):
            raise ValueError("candidate store must be strictly lexicographically ordered")
        for name, value in vars(self).items():
            if isinstance(value, np.ndarray):
                if value.dtype.hasobject:
                    raise ValueError(f"candidate store field {name} may not use object dtype")
                if not value.flags.c_contiguous:
                    raise ValueError(f"candidate store field {name} must be C-contiguous")
                if value.shape[0] != row_count:
                    raise ValueError(f"candidate store field {name} has a mismatched row count")
        if not np.isfinite(self.structural_score).all():
            raise ValueError("candidate structural scores must be finite")


@dataclass(frozen=True)
class PackedWindowState:
    frequency_rate: np.ndarray
    recent_frequency_rate: np.ndarray
    omission_rate: np.ndarray
    recent_omission_pressure: np.ndarray
    recent_neighbor_rate: np.ndarray
    previous_number_mask: np.uint64
    previous_consecutive_pair_count: int
    previous_odd_count: int
    parity_transition: np.ndarray
    previous_zone_counts: np.ndarray
    lagged_number_mask: np.uint64
    recent_average_gaps: np.ndarray
    recent_average_sum: float
    recent_average_span: float
    qian_kun_rate: np.ndarray
    recent_qian_codes: np.ndarray
    first_last_sum_rate: np.ndarray
    span_bucket_rate: np.ndarray
    sum_bucket_rate: np.ndarray
    ac_rate: np.ndarray
    zone_rate: np.ndarray
    big_count_rate: np.ndarray
    even_count_rate: np.ndarray
    prime_count_rate: np.ndarray
    mod012_rate: np.ndarray
    tail_unique_rate: np.ndarray
    sum_tail_rate: np.ndarray
    consecutive_rate: np.ndarray
    repeat_rate: np.ndarray
    sum_bucket_omission: np.ndarray
    span_bucket_omission: np.ndarray
    recent_average_omission: float
    stable_ranges_enabled: bool
    stable_lower: np.ndarray
    stable_upper: np.ndarray
    weekday_enabled: bool
    weekday_first_last_sum_rate: np.ndarray
    weekday_span_bucket_rate: np.ndarray
    weekday_sum_bucket_rate: np.ndarray
    weekday_ac_rate: np.ndarray
    weekday_zone_rate: np.ndarray
    weekday_big_count_rate: np.ndarray
    weekday_even_count_rate: np.ndarray
    weekday_prime_count_rate: np.ndarray
    weekday_mod012_rate: np.ndarray
    weekday_tail_unique_rate: np.ndarray
    weekday_sum_tail_rate: np.ndarray
    weekday_consecutive_rate: np.ndarray
    weekday_repeat_rate: np.ndarray

    def validate(self) -> None:
        for name, value in vars(self).items():
            if isinstance(value, np.ndarray):
                if value.dtype != np.float64 and name != "recent_qian_codes":
                    raise ValueError(f"packed window field {name} must be float64")
                if name == "recent_qian_codes" and value.dtype != np.uint8:
                    raise ValueError("recent_qian_codes must be uint8")
                if value.dtype.hasobject or not value.flags.c_contiguous:
                    raise ValueError(f"packed window field {name} must be contiguous and non-object")
                if value.dtype == np.float64 and not np.isfinite(value).all():
                    raise ValueError(f"packed window field {name} must be finite")
        for value in (self.recent_average_sum, self.recent_average_span, self.recent_average_omission):
            if not np.isfinite(value):
                raise ValueError("packed window scalar values must be finite")


@dataclass(frozen=True)
class WeightMatrix:
    values: np.ndarray

    def __post_init__(self) -> None:
        values = np.asarray(self.values)
        if values.dtype != WEIGHT_DTYPE or values.ndim != 2:
            raise ValueError("weights must be float64[config,component]")
        if not values.flags.c_contiguous or values.dtype.hasobject:
            raise ValueError("weights must be C-contiguous and non-object")
        if not np.isfinite(values).all():
            raise ValueError("weights must be finite")

    @property
    def config_count(self) -> int:
        return int(self.values.shape[0])


@dataclass(frozen=True)
class KernelRequest:
    target_scores: np.ndarray
    target_lex_id: int
    target_mask: np.uint64
    top_k: int = 0
    chunk_size: int = 262_144
    worker_count: int = 1
    exact_rank: bool = True
    red5: bool = False
    target_excluded: bool = False
    window_id: int = 0

    def validate(self, *, config_count: int, candidate_count: int) -> None:
        if self.target_scores.dtype != np.float64 or self.target_scores.shape != (config_count,):
            raise ValueError("target_scores must be float64[config]")
        if not self.target_scores.flags.c_contiguous or not np.isfinite(self.target_scores).all():
            raise ValueError("target_scores must be finite and C-contiguous")
        if self.chunk_size < 1 or self.worker_count < 1 or self.top_k < 0:
            raise ValueError("chunk_size and worker_count must be positive and top_k non-negative")
        if not 0 <= self.target_lex_id <= candidate_count:
            raise ValueError("target_lex_id is outside the candidate store")


@dataclass
class KernelWorkspace:
    score_buffer: np.ndarray | None = None
    red5_buffer: np.ndarray | None = None

    def score_view(self, row_count: int, config_count: int) -> np.ndarray:
        required_shape = (row_count, config_count)
        if (
            self.score_buffer is None
            or self.score_buffer.dtype != np.float64
            or self.score_buffer.ndim != 2
            or self.score_buffer.shape[0] < row_count
            or self.score_buffer.shape[1] != config_count
            or not self.score_buffer.flags.c_contiguous
        ):
            self.score_buffer = np.empty(required_shape, dtype=np.float64)
        return self.score_buffer[:row_count]

    def red5_view(self, row_count: int) -> np.ndarray:
        if (
            self.red5_buffer is None
            or self.red5_buffer.dtype != np.uint8
            or self.red5_buffer.ndim != 1
            or self.red5_buffer.shape[0] < row_count
            or not self.red5_buffer.flags.c_contiguous
        ):
            self.red5_buffer = np.empty(row_count, dtype=np.uint8)
        return self.red5_buffer[:row_count]


@dataclass(frozen=True)
class PreparedCandidateStore:
    store: CandidateStore
    backend_name: str
    prepare_seconds: float = 0.0


@dataclass(frozen=True)
class KernelResult:
    backend: str
    contract_version: str
    target_scores: np.ndarray
    exact_ranks: np.ndarray
    top_candidate_ids: np.ndarray
    top_scores: np.ndarray
    red5_candidate_ids: np.ndarray
    red5_scores: np.ndarray
    red5_ranks: np.ndarray
    telemetry: dict[str, int | float | str] = field(default_factory=dict)


class ScoringKernelBackend(Protocol):
    name: str
    contract_version: str

    def prepare(self, candidate_store: CandidateStore) -> PreparedCandidateStore: ...

    def score_rank(
        self,
        prepared_store: PreparedCandidateStore,
        window_state: PackedWindowState,
        weights: WeightMatrix,
        request: KernelRequest,
        workspace: KernelWorkspace | None = None,
    ) -> KernelResult: ...
