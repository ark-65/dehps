from __future__ import annotations

import numpy as np

from dehps.optimization.walk_forward import RankedUniverseMatrix
from scripts.run_neural_feasibility_probe import (
    ProbeDataset,
    binary_auc,
    build_probe_dataset,
    combination_keys,
    dense_bytes,
    fit_numpy_mlp,
    gibibytes,
    score_full_universe,
    train_numpy_mlp,
)


def fake_matrix() -> RankedUniverseMatrix:
    numbers = np.array(
        [
            [1, 2, 3, 4, 5, 6],
            [1, 3, 5, 7, 9, 11],
            [2, 4, 6, 8, 10, 12],
            [3, 8, 13, 18, 23, 28],
            [4, 9, 14, 19, 24, 29],
            [5, 10, 15, 20, 25, 30],
            [6, 11, 16, 21, 26, 31],
            [7, 12, 17, 22, 27, 32],
            [8, 13, 18, 23, 28, 33],
            [9, 14, 19, 24, 29, 33],
        ],
        dtype=np.uint8,
    )
    rows = numbers.shape[0]
    number_presence = np.zeros((rows, 34), dtype=bool)
    number_presence[np.arange(rows)[:, None], numbers] = True
    return RankedUniverseMatrix(
        numbers=numbers,
        structural_score=np.linspace(0.1, 1.0, rows, dtype=np.float64),
        consecutive_pair_count=np.arange(rows, dtype=np.uint8) % 3,
        odd_count=np.arange(rows, dtype=np.uint8) % 7,
        zone_counts=np.tile(np.array([[2, 2, 2]], dtype=np.uint8), (rows, 1)),
        gaps=np.tile(np.array([[1, 2, 3, 4, 5]], dtype=np.uint8), (rows, 1)),
        sum_value=numbers.sum(axis=1).astype(np.uint16),
        span_value=(numbers[:, -1] - numbers[:, 0]).astype(np.uint8),
        qian_kun_code=np.arange(rows, dtype=np.uint8),
        first_last_sum=(numbers[:, 0] + numbers[:, -1]).astype(np.uint8),
        sum_bucket=(numbers.sum(axis=1) // 10).astype(np.uint8),
        span_bucket=((numbers[:, -1] - numbers[:, 0]) // 3).astype(np.uint8),
        ac_value=np.arange(rows, dtype=np.uint8) % 8,
        big_count=np.arange(rows, dtype=np.uint8) % 7,
        even_count=np.arange(rows, dtype=np.uint8) % 7,
        prime_count=np.arange(rows, dtype=np.uint8) % 7,
        mod012_counts=np.tile(np.array([[2, 2, 2]], dtype=np.uint8), (rows, 1)),
        tail_unique_count=np.full(rows, 6, dtype=np.uint8),
        sum_tail=(numbers.sum(axis=1) % 10).astype(np.uint8),
        max_gap=np.full(rows, 5, dtype=np.uint8),
        min_gap=np.ones(rows, dtype=np.uint8),
        number_presence=number_presence,
        cache_info={"cache_hit": True},
    )


def test_combination_keys_are_stable_and_unique():
    numbers = np.array([[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 7]], dtype=np.uint8)

    keys = combination_keys(numbers)

    assert keys[0] != keys[1]
    assert combination_keys(numbers)[0] == keys[0]


def test_binary_auc_handles_perfect_scores_and_empty_class():
    assert binary_auc(np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.8, 0.9])) == 1.0
    assert binary_auc(np.array([1, 1]), np.array([0.2, 0.3])) is None


def test_probe_dataset_samples_history_positives_and_negatives():
    dataset = build_probe_dataset(
        matrix=fake_matrix(),
        history=[
            ("001", (1, 2, 3, 4, 5, 6)),
            ("002", (1, 3, 5, 7, 9, 11)),
            ("003", (2, 4, 6, 8, 10, 12)),
            ("004", (3, 8, 13, 18, 23, 28)),
            ("005", (4, 9, 14, 19, 24, 29)),
            ("006", (5, 10, 15, 20, 25, 30)),
            ("007", (6, 11, 16, 21, 26, 31)),
            ("008", (7, 12, 17, 22, 27, 32)),
        ],
        max_sample_rows=10,
        negative_ratio=1,
        seed=7,
    )

    assert dataset.positive_count == 8
    assert dataset.negative_count == 2
    assert dataset.feature_count > 40
    assert dataset.x_train.shape[0] == 8


def test_numpy_mlp_probe_runs_on_toy_data():
    rng = np.random.default_rng(11)
    x_train = rng.normal(size=(24, 5)).astype(np.float32)
    y_train = (x_train[:, 0] > 0).astype(np.float32)
    x_val = rng.normal(size=(12, 5)).astype(np.float32)
    y_val = (x_val[:, 0] > 0).astype(np.float32)
    result = train_numpy_mlp(
        ProbeDataset(
            x_train=x_train,
            y_train=y_train,
            x_val=x_val,
            y_val=y_val,
            feature_mean=np.zeros((1, 5), dtype=np.float32),
            feature_std=np.ones((1, 5), dtype=np.float32),
            positive_count=int(y_train.sum() + y_val.sum()),
            negative_count=int((1 - y_train).sum() + (1 - y_val).sum()),
            feature_count=5,
            sampled_rows=36,
        ),
        hidden_units=4,
        epochs=2,
        batch_size=8,
        learning_rate=0.01,
        seed=3,
    )

    assert result["backend"] == "numpy_cpu_mlp"
    assert len(result["epoch_summaries"]) == 2
    assert result["rows_per_second_last_epoch"] > 0
    assert dense_bytes(1024, 16) == 65536
    assert gibibytes(1024**3) == 1.0


def test_full_universe_scoring_returns_ranked_candidates():
    matrix = fake_matrix()
    dataset = build_probe_dataset(
        matrix=matrix,
        history=[
            ("001", (1, 2, 3, 4, 5, 6)),
            ("002", (1, 3, 5, 7, 9, 11)),
            ("003", (2, 4, 6, 8, 10, 12)),
            ("004", (3, 8, 13, 18, 23, 28)),
            ("005", (4, 9, 14, 19, 24, 29)),
            ("006", (5, 10, 15, 20, 25, 30)),
            ("007", (6, 11, 16, 21, 26, 31)),
            ("008", (7, 12, 17, 22, 27, 32)),
        ],
        max_sample_rows=10,
        negative_ratio=1,
        seed=17,
    )
    model, summary = fit_numpy_mlp(
        dataset,
        hidden_units=4,
        epochs=1,
        batch_size=4,
        learning_rate=0.01,
        seed=19,
    )

    scored = score_full_universe(matrix, model, top_k=3, batch_size=4)

    assert summary["backend"] == "numpy_cpu_mlp"
    assert scored["scorer_key"] == "neural_cpu_mlp_v0"
    assert scored["top_k"] == 3
    assert len(scored["top_candidates"]) == 3
    assert scored["top_candidates"][0]["rank"] == 1
    assert scored["score_min"] <= scored["score_median"] <= scored["score_max"]
