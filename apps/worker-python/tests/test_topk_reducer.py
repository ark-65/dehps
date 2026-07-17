from __future__ import annotations

import numpy as np
import pytest

from dehps.scoring_kernel.topk_reducer import (
    PartitionMergeReducer,
    SmallKReducer,
    TileSelectionReducer,
    TopKReducerPlanner,
    TopKReductionPool,
)


def _expected(
    ids: np.ndarray,
    scores: np.ndarray,
    top_k: int,
    mask: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    if mask is not None:
        ids = ids[mask]
        scores = scores[mask]
    expected_ids = []
    expected_scores = []
    for config_index in range(scores.shape[1]):
        order = np.lexsort((ids, -scores[:, config_index]))[:top_k]
        expected_ids.append(ids[order])
        expected_scores.append(scores[order, config_index])
    return np.stack(expected_ids), np.stack(expected_scores)


def _reduce(
    *,
    ids: np.ndarray,
    scores: np.ndarray,
    top_k: int,
    tile_size: int,
    workers: int,
    reverse_tiles: bool = False,
    mask: np.ndarray | None = None,
):
    bounds = [
        (start, min(start + tile_size, len(ids)))
        for start in range(0, len(ids), tile_size)
    ]
    if reverse_tiles:
        bounds.reverse()
    with TopKReductionPool(workers, scores.shape[1]) as pool:
        reducer = TopKReducerPlanner().create(
            config_count=scores.shape[1],
            top_k=top_k,
            tile_size=tile_size,
            pool=pool,
        )
        for start, end in bounds:
            reducer.consume(
                np.ascontiguousarray(scores[start:end]),
                np.ascontiguousarray(ids[start:end]),
                np.ascontiguousarray(mask[start:end]) if mask is not None else None,
            )
        return reducer.finalize()


@pytest.mark.parametrize(
    ("top_k", "tile_size", "expected_type"),
    [
        (17, 4_096, SmallKReducer),
        (10_000, 262_144, TileSelectionReducer),
        (50_000, 262_144, PartitionMergeReducer),
    ],
)
def test_planner_selects_k_specific_reducer(top_k, tile_size, expected_type) -> None:
    with TopKReductionPool(4, 8) as pool:
        reducer = TopKReducerPlanner().create(
            config_count=8,
            top_k=top_k,
            tile_size=tile_size,
            pool=pool,
        )
    assert isinstance(reducer, expected_type)


@pytest.mark.parametrize(
    ("top_k", "tile_size", "workers"),
    [(1, 113, 1), (127, 257, 4), (1_000, 2_048, 8), (10_000, 16_384, 8)],
)
def test_reducer_is_tile_thread_and_schedule_invariant(top_k, tile_size, workers) -> None:
    row_count = 20_000
    config_count = 8
    ids = np.arange(row_count, dtype=np.int64)
    rng = np.random.default_rng(20_260_717)
    scores = np.ascontiguousarray(
        np.round(rng.normal(size=(row_count, config_count)), 2),
        dtype=np.float64,
    )
    expected_ids, expected_scores = _expected(ids, scores, top_k)

    forward = _reduce(
        ids=ids,
        scores=scores,
        top_k=top_k,
        tile_size=tile_size,
        workers=workers,
    )
    reverse = _reduce(
        ids=ids,
        scores=scores,
        top_k=top_k,
        tile_size=max(97, tile_size // 2),
        workers=1,
        reverse_tiles=True,
    )

    assert np.array_equal(forward.candidate_ids, expected_ids)
    assert np.array_equal(forward.scores, expected_scores)
    assert np.array_equal(reverse.candidate_ids, expected_ids)
    assert np.array_equal(reverse.scores, expected_scores)


def test_reducer_applies_shared_mask_and_strict_tie_order() -> None:
    ids = np.arange(2_000, dtype=np.int64)
    scores = np.zeros((2_000, 3), dtype=np.float64)
    mask = ids % 7 == 0

    result = _reduce(
        ids=ids,
        scores=scores,
        top_k=25,
        tile_size=137,
        workers=3,
        reverse_tiles=True,
        mask=mask,
    )
    expected_ids, expected_scores = _expected(ids, scores, 25, mask)

    assert np.array_equal(result.candidate_ids, expected_ids)
    assert np.array_equal(result.scores, expected_scores)
    assert result.merge_levels > 0


def test_reducer_rejects_implicit_dtype_or_shape_conversion() -> None:
    with TopKReductionPool(1, 2) as pool:
        reducer = TopKReducerPlanner().create(
            config_count=2,
            top_k=1,
            tile_size=10,
            pool=pool,
        )
        with pytest.raises(ValueError, match="float64"):
            reducer.consume(
                np.zeros((10, 2), dtype=np.float32),
                np.arange(10, dtype=np.int64),
            )


def test_zero_k_and_empty_mask_have_canonical_empty_outputs() -> None:
    ids = np.arange(20, dtype=np.int64)
    scores = np.zeros((20, 2), dtype=np.float64)
    zero = _reduce(
        ids=ids,
        scores=scores,
        top_k=0,
        tile_size=7,
        workers=2,
    )
    masked = _reduce(
        ids=ids,
        scores=scores,
        top_k=1,
        tile_size=7,
        workers=2,
        mask=np.zeros(20, dtype=np.bool_),
    )

    assert zero.candidate_ids.shape == (2, 0)
    assert zero.scores.shape == (2, 0)
    assert masked.candidate_ids.tolist() == [[-1], [-1]]
    assert np.isneginf(masked.scores).all()
