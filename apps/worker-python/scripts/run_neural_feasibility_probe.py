from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.models.frequency_ranker import history_numbers
from dehps.optimization.regime import HistoryScope, select_history
from dehps.optimization.walk_forward import RankedUniverseMatrix, build_ranked_universe
from dehps.storage.postgres_store import load_red_combination_universe


DEFAULT_OUTPUT_DIR = ROOT_DIR / "data/output/optimization"
DEFAULT_HIDDEN_UNITS = 32


@dataclass(frozen=True)
class ProbeDataset:
    x_train: np.ndarray
    y_train: np.ndarray
    x_val: np.ndarray
    y_val: np.ndarray
    feature_mean: np.ndarray
    feature_std: np.ndarray
    positive_count: int
    negative_count: int
    feature_count: int
    sampled_rows: int


@dataclass(frozen=True)
class NumpyMlpModel:
    feature_mean: np.ndarray
    feature_std: np.ndarray
    w1: np.ndarray
    b1: np.ndarray
    w2: np.ndarray
    b2: np.ndarray


def combination_keys(numbers: np.ndarray) -> np.ndarray:
    values = numbers.astype(np.uint64, copy=False)
    keys = np.zeros(values.shape[0], dtype=np.uint64)
    for column in range(values.shape[1]):
        keys = keys * np.uint64(34) + values[:, column]
    return keys


def matrix_feature_frame(matrix: RankedUniverseMatrix) -> np.ndarray:
    columns = [
        matrix.structural_score.astype(np.float32),
        matrix.consecutive_pair_count.astype(np.float32) / 5.0,
        matrix.odd_count.astype(np.float32) / 6.0,
        matrix.sum_value.astype(np.float32) / 200.0,
        matrix.span_value.astype(np.float32) / 32.0,
        matrix.qian_kun_code.astype(np.float32) / 63.0,
        matrix.first_last_sum.astype(np.float32) / 66.0,
        matrix.sum_bucket.astype(np.float32) / 20.0,
        matrix.span_bucket.astype(np.float32) / 11.0,
        matrix.ac_value.astype(np.float32) / 10.0,
        matrix.big_count.astype(np.float32) / 6.0,
        matrix.even_count.astype(np.float32) / 6.0,
        matrix.prime_count.astype(np.float32) / 6.0,
        matrix.tail_unique_count.astype(np.float32) / 6.0,
        matrix.sum_tail.astype(np.float32) / 9.0,
        matrix.max_gap.astype(np.float32) / 32.0,
        matrix.min_gap.astype(np.float32) / 32.0,
    ]
    dense = np.column_stack(columns + [matrix.zone_counts.astype(np.float32) / 6.0])
    gaps = matrix.gaps.astype(np.float32) / 32.0
    mod012 = matrix.mod012_counts.astype(np.float32) / 6.0
    presence = matrix.number_presence[:, 1:].astype(np.float32)
    return np.concatenate([dense, gaps, mod012, presence], axis=1).astype(np.float32, copy=False)


def standardization_stats(x_train: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = x_train.mean(axis=0, keepdims=True)
    std = x_train.std(axis=0, keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    return mean.astype(np.float32), std.astype(np.float32)


def standardize_features(features: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return ((features - mean) / std).astype(np.float32, copy=False)


def standardize_train_val(x_train: np.ndarray, x_val: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean, std = standardization_stats(x_train)
    return standardize_features(x_train, mean, std), standardize_features(x_val, mean, std)


def dense_bytes(rows: int, columns: int, *, dtype_bytes: int = 4) -> int:
    return int(rows) * int(columns) * int(dtype_bytes)


def gibibytes(byte_count: int) -> float:
    return round(byte_count / (1024**3), 3)


def binary_auc(y_true: np.ndarray, scores: np.ndarray) -> float | None:
    labels = y_true.astype(np.int8, copy=False)
    positive_count = int(labels.sum())
    negative_count = int(labels.shape[0] - positive_count)
    if positive_count == 0 or negative_count == 0:
        return None
    order = np.argsort(scores, kind="mergesort")
    sorted_scores = scores[order]
    ranks = np.empty(scores.shape[0], dtype=np.float64)
    start = 0
    rank_value = 1.0
    while start < sorted_scores.shape[0]:
        end = start + 1
        while end < sorted_scores.shape[0] and sorted_scores[end] == sorted_scores[start]:
            end += 1
        average_rank = (rank_value + rank_value + (end - start) - 1) / 2
        ranks[order[start:end]] = average_rank
        rank_value += end - start
        start = end
    positive_rank_sum = float(ranks[labels == 1].sum())
    return (positive_rank_sum - positive_count * (positive_count + 1) / 2) / (positive_count * negative_count)


def sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def build_probe_dataset(
    *,
    matrix: RankedUniverseMatrix,
    history: list,
    max_sample_rows: int,
    negative_ratio: int,
    seed: int,
) -> ProbeDataset:
    matrix_keys = combination_keys(matrix.numbers)
    index_by_key = {int(key): index for index, key in enumerate(matrix_keys.tolist())}
    positive_indices = []
    seen_positive: set[int] = set()
    for draw in history:
        key = int(combination_keys(np.array([history_numbers(draw)], dtype=np.uint8))[0])
        index = index_by_key.get(key)
        if index is not None and index not in seen_positive:
            seen_positive.add(index)
            positive_indices.append(index)
    if len(positive_indices) < 8:
        raise ValueError("not enough historical positives are present in the filtered universe")

    rng = np.random.default_rng(seed)
    max_negatives = max(1, min(max_sample_rows - len(positive_indices), len(positive_indices) * negative_ratio))
    positive_set = set(positive_indices)
    negative_set: set[int] = set()
    negative_indices: list[int] = []
    while len(negative_indices) < max_negatives:
        batch = rng.integers(0, len(matrix), size=max(4096, max_negatives - len(negative_indices)))
        for index in batch.tolist():
            if index not in positive_set and index not in negative_set:
                negative_set.add(index)
                negative_indices.append(index)
                if len(negative_indices) >= max_negatives:
                    break

    selected_indices = np.array(positive_indices + negative_indices, dtype=np.int64)
    labels = np.concatenate(
        [
            np.ones(len(positive_indices), dtype=np.float32),
            np.zeros(len(negative_indices), dtype=np.float32),
        ]
    )
    permutation = rng.permutation(selected_indices.shape[0])
    selected_indices = selected_indices[permutation]
    labels = labels[permutation]

    features = matrix_feature_frame(matrix)[selected_indices]
    split = max(1, min(features.shape[0] - 1, int(features.shape[0] * 0.8)))
    feature_mean, feature_std = standardization_stats(features[:split])
    x_train = standardize_features(features[:split], feature_mean, feature_std)
    x_val = standardize_features(features[split:], feature_mean, feature_std)
    return ProbeDataset(
        x_train=x_train,
        y_train=labels[:split],
        x_val=x_val,
        y_val=labels[split:],
        feature_mean=feature_mean,
        feature_std=feature_std,
        positive_count=len(positive_indices),
        negative_count=len(negative_indices),
        feature_count=features.shape[1],
        sampled_rows=features.shape[0],
    )


def fit_numpy_mlp(
    dataset: ProbeDataset,
    *,
    hidden_units: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    seed: int,
) -> tuple[NumpyMlpModel, dict[str, Any]]:
    rng = np.random.default_rng(seed)
    input_dim = dataset.x_train.shape[1]
    w1 = rng.normal(0.0, 0.05, size=(input_dim, hidden_units)).astype(np.float32)
    b1 = np.zeros(hidden_units, dtype=np.float32)
    w2 = rng.normal(0.0, 0.05, size=(hidden_units,)).astype(np.float32)
    b2 = np.array(0.0, dtype=np.float32)
    positive_weight = max(1.0, float((dataset.y_train.shape[0] - dataset.y_train.sum()) / max(1.0, dataset.y_train.sum())))
    epoch_summaries = []

    for epoch in range(1, epochs + 1):
        started = time.time()
        permutation = rng.permutation(dataset.x_train.shape[0])
        total_loss = 0.0
        total_rows = 0
        for start in range(0, permutation.shape[0], batch_size):
            batch_index = permutation[start:start + batch_size]
            x = dataset.x_train[batch_index]
            y = dataset.y_train[batch_index]
            hidden_linear = x @ w1 + b1
            hidden = np.maximum(hidden_linear, 0)
            logits = hidden @ w2 + b2
            probs = sigmoid(logits).astype(np.float32)
            weights = np.where(y > 0.5, positive_weight, 1.0).astype(np.float32)
            error = (probs - y) * weights / max(1, y.shape[0])

            grad_w2 = hidden.T @ error
            grad_b2 = error.sum()
            grad_hidden = error[:, None] * w2[None, :]
            grad_hidden[hidden_linear <= 0] = 0
            grad_w1 = x.T @ grad_hidden
            grad_b1 = grad_hidden.sum(axis=0)

            w2 -= learning_rate * grad_w2.astype(np.float32)
            b2 -= np.float32(learning_rate * grad_b2)
            w1 -= learning_rate * grad_w1.astype(np.float32)
            b1 -= learning_rate * grad_b1.astype(np.float32)

            clipped = np.clip(probs, 1e-6, 1 - 1e-6)
            batch_loss = -np.mean(weights * (y * np.log(clipped) + (1 - y) * np.log(1 - clipped)))
            total_loss += float(batch_loss) * y.shape[0]
            total_rows += y.shape[0]

        val_scores = sigmoid(np.maximum(dataset.x_val @ w1 + b1, 0) @ w2 + b2).astype(np.float32)
        epoch_summaries.append(
            {
                "epoch": epoch,
                "seconds": round(time.time() - started, 3),
                "train_loss": round(total_loss / max(1, total_rows), 6),
                "val_auc": None if (auc := binary_auc(dataset.y_val, val_scores)) is None else round(float(auc), 6),
                "val_positive_rate": round(float(dataset.y_val.mean()), 6),
            }
        )

    model = NumpyMlpModel(
        feature_mean=dataset.feature_mean,
        feature_std=dataset.feature_std,
        w1=w1,
        b1=b1,
        w2=w2,
        b2=b2,
    )
    summary = {
        "backend": "numpy_cpu_mlp",
        "hidden_units": hidden_units,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "positive_weight": round(float(positive_weight), 6),
        "epoch_summaries": epoch_summaries,
        "rows_per_second_last_epoch": round(dataset.x_train.shape[0] / max(epoch_summaries[-1]["seconds"], 1e-9), 1),
    }
    return model, summary


def train_numpy_mlp(
    dataset: ProbeDataset,
    *,
    hidden_units: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    seed: int,
) -> dict[str, Any]:
    _model, summary = fit_numpy_mlp(
        dataset,
        hidden_units=hidden_units,
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        seed=seed,
    )
    return summary


def score_numpy_mlp(model: NumpyMlpModel, features: np.ndarray, *, batch_size: int = 200_000) -> np.ndarray:
    scores = np.empty(features.shape[0], dtype=np.float32)
    for start in range(0, features.shape[0], batch_size):
        end = min(features.shape[0], start + batch_size)
        x = standardize_features(features[start:end], model.feature_mean, model.feature_std)
        hidden = np.maximum(x @ model.w1 + model.b1, 0)
        scores[start:end] = sigmoid(hidden @ model.w2 + model.b2).astype(np.float32)
    return scores


def score_full_universe(
    matrix: RankedUniverseMatrix,
    model: NumpyMlpModel,
    *,
    top_k: int,
    batch_size: int = 200_000,
) -> dict[str, Any]:
    started = time.time()
    scores = score_numpy_mlp(model, matrix_feature_frame(matrix), batch_size=batch_size)
    safe_top_k = max(0, min(top_k, scores.shape[0]))
    if safe_top_k:
        top_indices = np.argpartition(scores, -safe_top_k)[-safe_top_k:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
    else:
        top_indices = np.array([], dtype=np.int64)
    return {
        "scorer_key": "neural_cpu_mlp_v0",
        "top_k": safe_top_k,
        "score_seconds": round(time.time() - started, 3),
        "score_min": round(float(scores.min()), 8),
        "score_median": round(float(np.median(scores)), 8),
        "score_max": round(float(scores.max()), 8),
        "top_candidates": [
            {
                "rank": rank,
                "numbers": [int(number) for number in matrix.numbers[index].tolist()],
                "score": round(float(scores[index]), 8),
            }
            for rank, index in enumerate(top_indices.tolist(), start=1)
        ],
    }


def total_memory_gib() -> float | None:
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return gibibytes(int(pages) * int(page_size))
    except (ValueError, OSError, AttributeError):
        return None


def accelerator_summary() -> dict[str, Any]:
    lspci = ""
    try:
        lspci = subprocess.check_output(["lspci"], text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        pass
    return {
        "nvidia_smi": bool(shutil.which("nvidia-smi")),
        "cuda_visible": bool(shutil.which("nvidia-smi")),
        "dri_render_node": Path("/dev/dri/renderD128").exists(),
        "intel_arc_hint": "Intel Arc Graphics" in lspci,
        "intel_npu_hint": "Meteor Lake NPU" in lspci,
    }


def render_report(payload: dict[str, Any]) -> str:
    epochs = "\n".join(
        f"| {row['epoch']} | {row['seconds']} | {row['train_loss']} | {row['val_auc']} |"
        for row in payload["training"]["epoch_summaries"]
    )
    scoring = payload.get("scoring") if isinstance(payload.get("scoring"), dict) else None
    candidates = "\n".join(
        f"| {item['rank']} | {' '.join(f'{number:02d}' for number in item['numbers'])} | {item['score']} |"
        for item in (scoring or {}).get("top_candidates", [])
    )
    scoring_section = ""
    if scoring is not None:
        scoring_section = f"""
## Explicit Neural Scorer

- Scorer key: `{scoring['scorer_key']}`
- Top-K: {scoring['top_k']}
- Score seconds: {scoring['score_seconds']}
- Score min/median/max: {scoring['score_min']} / {scoring['score_median']} / {scoring['score_max']}

| Rank | Numbers | Neural score |
| ---: | --- | ---: |
{candidates}
"""
    return f"""# DEHPS Neural Feasibility Probe

- Generated at: {payload["generated_at"]}
- Backend: `{payload["training"]["backend"]}`
- CPU: {payload["hardware"]["cpu_count"]} logical cores, {payload["hardware"]["machine"]}
- Memory: {payload["hardware"]["memory_gib"]} GiB
- Accelerator: {json.dumps(payload["hardware"]["accelerator"], sort_keys=True)}
- Universe rows: {payload["universe"]["rows"]}
- Sample rows: {payload["dataset"]["sampled_rows"]}
- Positives / negatives: {payload["dataset"]["positive_count"]} / {payload["dataset"]["negative_count"]}
- Feature columns: {payload["dataset"]["feature_count"]}
- Estimated dense full-universe feature memory: {payload["universe"]["estimated_dense_feature_gib"]} GiB
- Last epoch rows/sec: {payload["training"]["rows_per_second_last_epoch"]}

## Epochs

| Epoch | Seconds | Train loss | Validation AUC |
| ---: | ---: | ---: | ---: |
{epochs}

{scoring_section}

## Interpretation

This is a hardware and pipeline feasibility probe for a small CPU neural baseline. It does not claim predictive ability. A real experiment must freeze the feature set, split by time, and compare against same-budget structural/frequency/null baselines.
"""


def run_probe(
    *,
    as_of_issue: str | None,
    history_scope: HistoryScope,
    regime_years: int,
    max_sample_rows: int,
    negative_ratio: int,
    hidden_units: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    seed: int,
    score_top_k: int,
    output_dir: Path,
) -> dict[str, Any]:
    with get_connection() as conn:
        selection = select_history(
            conn,
            scope=history_scope,
            as_of_issue=as_of_issue,
            regime_years=regime_years,
        )
        universe = load_red_combination_universe(conn)
    started = time.time()
    matrix = build_ranked_universe(universe)
    matrix_seconds = time.time() - started
    dataset = build_probe_dataset(
        matrix=matrix,
        history=selection.dated_history,
        max_sample_rows=max_sample_rows,
        negative_ratio=negative_ratio,
        seed=seed,
    )
    model, training = fit_numpy_mlp(
        dataset,
        hidden_units=hidden_units,
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        seed=seed,
    )
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "as_of_issue": as_of_issue or (selection.dated_history[-1][0] if selection.dated_history else None),
        "history_scope": selection.scope,
        "regime_years": selection.regime_years,
        "regime_start_date": selection.start_date.isoformat() if selection.start_date else None,
        "history_draws": len(selection.dated_history),
        "hardware": {
            "machine": platform.platform(),
            "cpu_count": os.cpu_count(),
            "memory_gib": total_memory_gib(),
            "accelerator": accelerator_summary(),
        },
        "universe": {
            "rows": len(matrix),
            "cache_info": matrix.cache_info,
            "matrix_load_seconds": round(matrix_seconds, 3),
            "estimated_dense_feature_gib": gibibytes(dense_bytes(len(matrix), dataset.feature_count)),
        },
        "dataset": {
            "sampled_rows": dataset.sampled_rows,
            "positive_count": dataset.positive_count,
            "negative_count": dataset.negative_count,
            "feature_count": dataset.feature_count,
            "train_rows": int(dataset.x_train.shape[0]),
            "validation_rows": int(dataset.x_val.shape[0]),
        },
        "training": training,
    }
    if score_top_k > 0:
        payload["scoring"] = score_full_universe(
            matrix,
            model,
            top_k=score_top_k,
            batch_size=max(batch_size, 65_536),
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    key = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"neural-feasibility-{key}.json"
    report_path = output_dir / f"neural-feasibility-{key}.md"
    payload["json_path"] = str(json_path)
    payload["report_path"] = str(report_path)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    report_path.write_text(render_report(payload))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of-issue")
    parser.add_argument("--history-scope", choices=["full_history_audit", "current_regime_default"], default="current_regime_default")
    parser.add_argument("--regime-years", type=int, default=10)
    parser.add_argument("--max-sample-rows", type=int, default=60000)
    parser.add_argument("--negative-ratio", type=int, default=20)
    parser.add_argument("--hidden-units", type=int, default=DEFAULT_HIDDEN_UNITS)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    parser.add_argument("--seed", type=int, default=20260618)
    parser.add_argument("--score-top-k", type=int, default=0, help="Explicitly score the full universe and emit top-K neural candidates.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    payload = run_probe(
        as_of_issue=args.as_of_issue,
        history_scope=args.history_scope,
        regime_years=args.regime_years,
        max_sample_rows=args.max_sample_rows,
        negative_ratio=args.negative_ratio,
        hidden_units=args.hidden_units,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        seed=args.seed,
        score_top_k=args.score_top_k,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "report_path": payload["report_path"],
                "json_path": payload["json_path"],
                "sampled_rows": payload["dataset"]["sampled_rows"],
                "feature_count": payload["dataset"]["feature_count"],
                "last_epoch_rows_per_second": payload["training"]["rows_per_second_last_epoch"],
                "scoring": payload.get("scoring"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
