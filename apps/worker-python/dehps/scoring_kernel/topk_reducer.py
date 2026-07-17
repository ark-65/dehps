from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Protocol, TypeVar

import numpy as np


T = TypeVar("T")
U = TypeVar("U")


def ordered_topk(
    candidate_ids: np.ndarray,
    scores: np.ndarray,
    top_k: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Select the strict_v1 order: greater score, then smaller candidate id."""

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


@dataclass(frozen=True)
class TopKResult:
    candidate_ids: np.ndarray
    scores: np.ndarray
    algorithm: str
    input_rows: int
    shard_count: int
    merge_levels: int
    retained_cells_peak: int

    @property
    def workspace_bytes_estimate(self) -> int:
        return self.retained_cells_peak * (
            np.dtype(np.int64).itemsize + np.dtype(np.float64).itemsize
        )


class TopKReducer(Protocol):
    def consume(
        self,
        scores: np.ndarray,
        lex_ids: np.ndarray,
        optional_mask: np.ndarray | None = None,
    ) -> None: ...

    def finalize(self) -> TopKResult: ...


class TopKReductionPool:
    """One bounded pool shared by normal TopK and Red5 reduction."""

    def __init__(self, worker_count: int, config_count: int) -> None:
        self.worker_count = max(1, min(int(worker_count), int(config_count)))
        self._executor: ThreadPoolExecutor | None = None

    def __enter__(self) -> TopKReductionPool:
        if self.worker_count > 1:
            self._executor = ThreadPoolExecutor(
                max_workers=self.worker_count,
                thread_name_prefix="dehps-topk",
            )
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None

    def map(self, function: Callable[[T], U], items: Iterable[T]) -> list[U]:
        values = list(items)
        if self._executor is None:
            return [function(value) for value in values]
        return list(self._executor.map(function, values))


def _select_task(
    task: tuple[np.ndarray, np.ndarray, int],
) -> tuple[np.ndarray, np.ndarray]:
    candidate_ids, scores, top_k = task
    return ordered_topk(candidate_ids, scores, top_k)


def _merge_task(
    task: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int],
) -> tuple[np.ndarray, np.ndarray]:
    left_ids, left_scores, right_ids, right_scores, top_k = task
    return ordered_topk(
        np.concatenate((left_ids, right_ids)),
        np.concatenate((left_scores, right_scores)),
        top_k,
    )


class _BaseReducer:
    algorithm = "base"

    def __init__(
        self,
        *,
        config_count: int,
        top_k: int,
        pool: TopKReductionPool,
    ) -> None:
        if config_count < 1 or top_k < 0:
            raise ValueError("config_count must be positive and top_k non-negative")
        self.config_count = int(config_count)
        self.top_k = int(top_k)
        self.pool = pool
        self.input_rows = 0
        self.shard_count = 0
        self.merge_levels = 0
        self.retained_cells_peak = 0

    def _validate_inputs(
        self,
        scores: np.ndarray,
        lex_ids: np.ndarray,
        optional_mask: np.ndarray | None,
    ) -> tuple[np.ndarray, np.ndarray]:
        if (
            scores.dtype != np.float64
            or scores.ndim != 2
            or scores.shape[1] != self.config_count
        ):
            raise ValueError("TopK scores must be float64[R, config_count]")
        if (
            lex_ids.dtype != np.int64
            or lex_ids.ndim != 1
            or len(lex_ids) != len(scores)
        ):
            raise ValueError("TopK lex_ids must be int64[R]")
        if optional_mask is None:
            return lex_ids, scores
        if (
            optional_mask.dtype != np.bool_
            or optional_mask.ndim != 1
            or len(optional_mask) != len(scores)
        ):
            raise ValueError("TopK optional_mask must be bool[R]")
        return lex_ids[optional_mask], scores[optional_mask]

    def _empty_result(self) -> TopKResult:
        return TopKResult(
            candidate_ids=np.full((self.config_count, self.top_k), -1, dtype=np.int64),
            scores=np.full((self.config_count, self.top_k), -np.inf, dtype=np.float64),
            algorithm=self.algorithm,
            input_rows=self.input_rows,
            shard_count=self.shard_count,
            merge_levels=self.merge_levels,
            retained_cells_peak=self.retained_cells_peak,
        )

    def _result(self, shards: list[tuple[np.ndarray, np.ndarray]]) -> TopKResult:
        result = self._empty_result()
        for config_index, (candidate_ids, scores) in enumerate(shards):
            count = min(self.top_k, len(candidate_ids))
            result.candidate_ids[config_index, :count] = candidate_ids[:count]
            result.scores[config_index, :count] = scores[:count]
        return result


class TileSelectionReducer(_BaseReducer):
    """Tile-local selection followed by a deterministic balanced merge tree."""

    algorithm = "tile_selection_tree"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._shards: list[list[tuple[np.ndarray, np.ndarray]]] = [
            [] for _ in range(self.config_count)
        ]

    def consume(
        self,
        scores: np.ndarray,
        lex_ids: np.ndarray,
        optional_mask: np.ndarray | None = None,
    ) -> None:
        candidate_ids, selected_scores = self._validate_inputs(
            scores, lex_ids, optional_mask
        )
        self.input_rows += len(candidate_ids)
        if not len(candidate_ids) or self.top_k == 0:
            return
        tasks = [
            (candidate_ids, selected_scores[:, config_index], self.top_k)
            for config_index in range(self.config_count)
        ]
        selections = self.pool.map(_select_task, tasks)
        for config_index, selection in enumerate(selections):
            self._shards[config_index].append(selection)
        self.shard_count += 1
        retained = sum(
            len(candidate_ids)
            for config_shards in self._shards
            for candidate_ids, _ in config_shards
        )
        self.retained_cells_peak = max(self.retained_cells_peak, retained)

    def finalize(self) -> TopKResult:
        shards = [list(config_shards) for config_shards in self._shards]
        while any(len(config_shards) > 1 for config_shards in shards):
            tasks = []
            positions = []
            next_level: list[list[tuple[np.ndarray, np.ndarray]]] = [
                [] for _ in range(self.config_count)
            ]
            for config_index, config_shards in enumerate(shards):
                for shard_index in range(0, len(config_shards) - 1, 2):
                    left = config_shards[shard_index]
                    right = config_shards[shard_index + 1]
                    positions.append(config_index)
                    tasks.append((*left, *right, self.top_k))
                if len(config_shards) % 2:
                    next_level[config_index].append(config_shards[-1])
            for config_index, merged in zip(
                positions, self.pool.map(_merge_task, tasks)
            ):
                next_level[config_index].append(merged)
            shards = next_level
            self.merge_levels += 1
        final = [
            config_shards[0]
            if config_shards
            else (np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float64))
            for config_shards in shards
        ]
        return self._result(final)


class SmallKReducer(TileSelectionReducer):
    algorithm = "small_k_tree"


class PartitionMergeReducer(_BaseReducer):
    """Streaming partition merge for K large enough that tile retention is wasteful."""

    algorithm = "streaming_partition_merge"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current = [
            (np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float64))
            for _ in range(self.config_count)
        ]

    def consume(
        self,
        scores: np.ndarray,
        lex_ids: np.ndarray,
        optional_mask: np.ndarray | None = None,
    ) -> None:
        candidate_ids, selected_scores = self._validate_inputs(
            scores, lex_ids, optional_mask
        )
        self.input_rows += len(candidate_ids)
        if not len(candidate_ids) or self.top_k == 0:
            return
        tasks = [
            (
                current_ids,
                current_scores,
                candidate_ids,
                selected_scores[:, config_index],
                self.top_k,
            )
            for config_index, (current_ids, current_scores) in enumerate(self._current)
        ]
        self._current = self.pool.map(_merge_task, tasks)
        self.shard_count += 1
        self.merge_levels = self.shard_count
        retained = sum(len(ids) for ids, _ in self._current)
        self.retained_cells_peak = max(self.retained_cells_peak, retained)

    def finalize(self) -> TopKResult:
        return self._result(self._current)


class TopKReducerPlanner:
    SMALL_K_MAX = 256
    TILE_SELECTION_MIN_MAX = 10_000

    def create(
        self,
        *,
        config_count: int,
        top_k: int,
        tile_size: int,
        pool: TopKReductionPool,
    ) -> TopKReducer:
        kwargs = {
            "config_count": config_count,
            "top_k": top_k,
            "pool": pool,
        }
        if top_k <= self.SMALL_K_MAX:
            return SmallKReducer(**kwargs)
        tile_selection_max = max(self.TILE_SELECTION_MIN_MAX, tile_size // 8)
        if top_k <= tile_selection_max:
            return TileSelectionReducer(**kwargs)
        return PartitionMergeReducer(**kwargs)
