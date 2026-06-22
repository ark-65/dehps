from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from hashlib import sha256
from math import ceil, log1p
from typing import Any, Literal, Mapping, Sequence

import numpy as np

from dehps.models.frequency_ranker import FrequencyRankerConfig


ADVISOR_SOURCE = "neural_kdj_advisor_v0"
PRIMARY_WEIGHT_FIELDS = ("structural_weight", "frequency_weight", "omission_weight")
FREQUENCY_RANKER_FIELDS = tuple(field.name for field in fields(FrequencyRankerConfig))
BASE_FEATURE_NAMES = (
    "rsv",
    "k",
    "d",
    "j",
    "k_minus_d",
    "j_minus_50",
    "interval_position",
    "distance_to_low_steps",
    "distance_to_high_steps",
    "interval_width_steps",
    "j_extreme_high",
    "j_extreme_low",
    "recommended_offset_steps",
    "close_minus_base_steps",
    "scaled_objective_delta",
    "log1p_sample_count",
)
NeuralKdjMode = Literal["joint", "per-weight"]


@dataclass(frozen=True)
class NeuralKdjOffsetAdvice:
    weight_name: str
    suggested_offset: float
    confidence: float
    train_rows: int
    validation_rows: int
    validation_metric: float
    baseline_metric: float
    feature_names: tuple[str, ...]
    source: str = ADVISOR_SOURCE
    advisory_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["feature_names"] = list(self.feature_names)
        return payload


@dataclass(frozen=True)
class _LatestFeature:
    weight_name: str
    x: np.ndarray
    base_value: float
    latest_issue: str


@dataclass(frozen=True)
class _LaggedKdjDataset:
    feature_names: tuple[str, ...]
    x: np.ndarray
    y: np.ndarray
    sample_weight: np.ndarray
    kdj_baseline: np.ndarray
    target_base_value: np.ndarray
    weight_names: tuple[str, ...]
    source_issues: tuple[str, ...]
    target_issues: tuple[str, ...]
    latest_by_weight: tuple[_LatestFeature, ...]


@dataclass(frozen=True)
class _MlpRegressor:
    feature_mean: np.ndarray
    feature_scale: np.ndarray
    target_mean: float
    target_scale: float
    w1: np.ndarray
    b1: np.ndarray
    w2: np.ndarray
    b2: float


def numpy_neural_kdj_offset_v0(
    rows: Sequence[Mapping[str, Any]],
    *,
    step: float,
    seed: int = 17,
    hidden_units: int = 8,
    epochs: int = 400,
    learning_rate: float = 0.01,
    validation_fraction: float = 0.25,
    min_train_rows: int = 16,
    min_validation_rows: int = 4,
    objective_delta_scale: float = 10.0,
    mode: NeuralKdjMode = "joint",
) -> tuple[NeuralKdjOffsetAdvice, ...]:
    if (
        step <= 0
        or hidden_units < 1
        or epochs < 1
        or learning_rate <= 0
        or validation_fraction <= 0
        or not rows
        or mode not in ("joint", "per-weight")
    ):
        return ()

    grouped = _group_ordered_rows(rows)
    if mode == "per-weight":
        advice: list[NeuralKdjOffsetAdvice] = []
        for weight_name, weight_rows in grouped.items():
            if weight_name not in FREQUENCY_RANKER_FIELDS:
                continue
            dataset = _build_lagged_dataset(
                {weight_name: weight_rows},
                step=step,
                objective_delta_scale=objective_delta_scale,
                joint=False,
            )
            candidate = _fit_and_validate_advice(
                dataset,
                step=step,
                seed=seed + _stable_int(weight_name),
                hidden_units=hidden_units,
                epochs=epochs,
                learning_rate=learning_rate,
                validation_fraction=validation_fraction,
                min_train_rows=min_train_rows,
                min_validation_rows=min_validation_rows,
            )
            if candidate:
                advice.extend(candidate)
        return tuple(sorted(advice, key=lambda item: (-item.confidence, item.weight_name)))

    dataset = _build_lagged_dataset(
        grouped,
        step=step,
        objective_delta_scale=objective_delta_scale,
        joint=True,
    )
    advice = _fit_and_validate_advice(
        dataset,
        step=step,
        seed=seed,
        hidden_units=hidden_units,
        epochs=epochs,
        learning_rate=learning_rate,
        validation_fraction=validation_fraction,
        min_train_rows=min_train_rows,
        min_validation_rows=min_validation_rows,
    )
    return tuple(sorted(advice or (), key=lambda item: (-item.confidence, item.weight_name)))


def neural_kdj_advice_to_frequency_ranker_config_candidates(
    base: FrequencyRankerConfig,
    advice_records: Sequence[NeuralKdjOffsetAdvice | Mapping[str, Any]],
    *,
    max_configs: int,
    min_confidence: float = 0.0,
) -> tuple[FrequencyRankerConfig, ...]:
    if max_configs <= 0:
        return ()

    ranked = sorted(
        (
            record
            for record in advice_records
            if _record_source(record) == ADVISOR_SOURCE and _record_float(record, "confidence") >= min_confidence
        ),
        key=lambda record: (
            _record_float(record, "confidence"),
            abs(_record_float(record, "suggested_offset")),
            _record_str(record, "weight_name"),
        ),
        reverse=True,
    )
    configs: list[FrequencyRankerConfig] = []
    seen: set[str] = set()
    for record in ranked:
        field = _record_str(record, "weight_name")
        bounds = _field_bounds(field)
        if bounds is None:
            continue
        offset = _record_float(record, "suggested_offset")
        if offset == 0:
            continue
        values = config_dict(base)
        values[field] = _clip(values[field] + offset, *bounds)
        config = FrequencyRankerConfig(**values)
        key = config_hash(config)
        if key in seen:
            continue
        seen.add(key)
        configs.append(config)
        if len(configs) >= max_configs:
            break
    return tuple(configs)


def neural_kdj_config_json_payload(
    *,
    base_config: FrequencyRankerConfig,
    advice: Sequence[NeuralKdjOffsetAdvice | Mapping[str, Any]],
    configs: Sequence[FrequencyRankerConfig],
    seed: int,
    hidden_units: int,
    epochs: int,
    mode: NeuralKdjMode = "joint",
    signal_run_id: str | None = None,
    train_window: int | None = None,
    top_n: int | None = None,
) -> dict[str, Any]:
    advice_dicts = [_advice_to_dict(record) for record in advice]
    config_entries = []
    for config in configs:
        config_advice = _matching_advice_for_config(base_config, config, advice_dicts)
        selected_fields = [item["weight_name"] for item in config_advice]
        validation_metrics = [float(item["validation_metric"]) for item in config_advice]
        baseline_metrics = [float(item["baseline_metric"]) for item in config_advice]
        confidences = [float(item["confidence"]) for item in config_advice]
        config_entries.append(
            {
                "config_hash": config_hash(config),
                "config": config_dict(config),
                "metadata": {
                    "advisor_source": ADVISOR_SOURCE,
                    "advisory_only": True,
                    "confidence": max(confidences) if confidences else 0.0,
                    "validation_metric": min(validation_metrics) if validation_metrics else None,
                    "baseline_metric": min(baseline_metrics) if baseline_metrics else None,
                    "selected_fields": selected_fields,
                    "selected_feature_names": sorted(
                        {
                            feature
                            for item in config_advice
                            for feature in item.get("feature_names", [])
                        }
                    ),
                },
            }
        )

    selected = config_entries[0] if config_entries else None
    metadata = {
        "advisor_source": ADVISOR_SOURCE,
        "advisory_only": True,
        "mode": mode,
        "seed": seed,
        "hidden_units": hidden_units,
        "epochs": epochs,
        "signal_run_id": signal_run_id,
        "train_window": train_window,
        "top_n": top_n,
        "base_config_hash": config_hash(base_config),
        "candidate_count": len(config_entries),
        "advice_count": len(advice_dicts),
        "selected_fields": selected["metadata"]["selected_fields"] if selected else [],
        "confidence": selected["metadata"]["confidence"] if selected else 0.0,
        "validation_metric": selected["metadata"]["validation_metric"] if selected else None,
        "baseline_metric": selected["metadata"]["baseline_metric"] if selected else None,
    }
    payload: dict[str, Any] = {
        "label": "candidate_neural_kdj_advisor_v0",
        "advisor_source": ADVISOR_SOURCE,
        "advisory_only": True,
        "metadata": metadata,
        "advice": advice_dicts,
        "candidate_configs": config_entries,
    }
    if selected:
        payload["config_hash"] = selected["config_hash"]
        payload["config"] = selected["config"]
    return payload


def config_dict(config: FrequencyRankerConfig) -> dict[str, float]:
    return {field: float(getattr(config, field)) for field in FREQUENCY_RANKER_FIELDS}


def config_hash(config: FrequencyRankerConfig) -> str:
    payload = json.dumps(config.__dict__, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def _fit_and_validate_advice(
    dataset: _LaggedKdjDataset | None,
    *,
    step: float,
    seed: int,
    hidden_units: int,
    epochs: int,
    learning_rate: float,
    validation_fraction: float,
    min_train_rows: int,
    min_validation_rows: int,
) -> tuple[NeuralKdjOffsetAdvice, ...]:
    if dataset is None:
        return ()
    row_count = int(dataset.x.shape[0])
    if row_count < min_train_rows + min_validation_rows:
        return ()
    if not np.any(dataset.sample_weight >= 1.0) or np.ptp(dataset.y[dataset.sample_weight >= 1.0]) <= 1e-12:
        return ()

    validation_rows = max(min_validation_rows, int(ceil(row_count * validation_fraction)))
    validation_rows = min(validation_rows, row_count - min_train_rows)
    train_rows = row_count - validation_rows
    if train_rows < min_train_rows or validation_rows < min_validation_rows:
        return ()

    x_train = dataset.x[:train_rows]
    y_train = dataset.y[:train_rows] / step
    weights_train = dataset.sample_weight[:train_rows]
    y_val = dataset.y[train_rows:]
    weights_val = dataset.sample_weight[train_rows:]

    if _looks_like_close_base_leakage(dataset, train_rows=train_rows, step=step):
        return ()

    model = _fit_mlp_regressor(
        x_train,
        y_train,
        weights_train,
        hidden_units=hidden_units,
        epochs=epochs,
        learning_rate=learning_rate,
        seed=seed,
    )
    val_steps = _predict_mlp(model, dataset.x[train_rows:])
    val_pred = val_steps * step
    val_pred = _bounded_offsets(
        val_pred,
        dataset.target_base_value[train_rows:],
        dataset.weight_names[train_rows:],
        step=step,
    )
    kdj_pred = _bounded_offsets(
        dataset.kdj_baseline[train_rows:],
        dataset.target_base_value[train_rows:],
        dataset.weight_names[train_rows:],
        step=step,
    )
    noop_pred = np.zeros_like(y_val)

    validation_metric = _weighted_mae(y_val, val_pred, weights_val)
    baseline_metric = min(_weighted_mae(y_val, noop_pred, weights_val), _weighted_mae(y_val, kdj_pred, weights_val))
    if not np.isfinite(validation_metric) or not np.isfinite(baseline_metric):
        return ()
    if baseline_metric <= 1e-12 or validation_metric >= baseline_metric:
        return ()

    confidence = float(_clip((baseline_metric - validation_metric) / baseline_metric, 0.0, 1.0))
    advice: list[NeuralKdjOffsetAdvice] = []
    for latest in dataset.latest_by_weight:
        bounds = _field_bounds(latest.weight_name)
        if bounds is None:
            continue
        suggested_steps = float(_predict_mlp(model, latest.x.reshape(1, -1))[0])
        suggested = _bounded_offset(suggested_steps * step, latest.base_value, weight_name=latest.weight_name, step=step)
        if abs(suggested) < step / 2:
            continue
        advice.append(
            NeuralKdjOffsetAdvice(
                weight_name=latest.weight_name,
                suggested_offset=suggested,
                confidence=confidence,
                train_rows=train_rows,
                validation_rows=validation_rows,
                validation_metric=float(validation_metric),
                baseline_metric=float(baseline_metric),
                feature_names=dataset.feature_names,
            )
        )
    return tuple(advice)


def _fit_mlp_regressor(
    x_train: np.ndarray,
    y_train: np.ndarray,
    sample_weight: np.ndarray,
    *,
    hidden_units: int,
    epochs: int,
    learning_rate: float,
    seed: int,
) -> _MlpRegressor:
    feature_mean = x_train.mean(axis=0, keepdims=True)
    feature_scale = x_train.std(axis=0, keepdims=True)
    feature_scale = np.where(feature_scale < 1e-8, 1.0, feature_scale)
    x_scaled = (x_train - feature_mean) / feature_scale
    target_mean = float(y_train.mean())
    target_scale = float(y_train.std())
    if target_scale < 1e-8:
        target_scale = 1.0
    y_scaled = (y_train - target_mean) / target_scale

    rng = np.random.default_rng(seed)
    input_units = x_scaled.shape[1]
    w1 = rng.normal(0.0, np.sqrt(2.0 / max(1, input_units + hidden_units)), size=(input_units, hidden_units))
    b1 = np.zeros(hidden_units, dtype=float)
    w2 = rng.normal(0.0, np.sqrt(1.0 / max(1, hidden_units)), size=hidden_units)
    b2 = 0.0

    m_w1 = np.zeros_like(w1)
    v_w1 = np.zeros_like(w1)
    m_b1 = np.zeros_like(b1)
    v_b1 = np.zeros_like(b1)
    m_w2 = np.zeros_like(w2)
    v_w2 = np.zeros_like(w2)
    m_b2 = 0.0
    v_b2 = 0.0
    beta1 = 0.9
    beta2 = 0.999
    epsilon = 1e-8
    l2 = 1e-4
    weights = np.maximum(sample_weight.astype(float, copy=False), 0.0)
    total_weight = max(float(weights.sum()), 1e-12)
    normalized_weight = weights / total_weight

    for epoch in range(1, epochs + 1):
        hidden_raw = x_scaled @ w1 + b1
        hidden = np.tanh(hidden_raw)
        prediction = hidden @ w2 + b2
        error_grad = 2.0 * (prediction - y_scaled) * normalized_weight

        grad_w2 = hidden.T @ error_grad + l2 * w2
        grad_b2 = float(error_grad.sum())
        grad_hidden = error_grad[:, None] * w2
        grad_hidden_raw = grad_hidden * (1.0 - hidden * hidden)
        grad_w1 = x_scaled.T @ grad_hidden_raw + l2 * w1
        grad_b1 = grad_hidden_raw.sum(axis=0)

        w1, m_w1, v_w1 = _adam_update(w1, grad_w1, m_w1, v_w1, learning_rate, epoch, beta1, beta2, epsilon)
        b1, m_b1, v_b1 = _adam_update(b1, grad_b1, m_b1, v_b1, learning_rate, epoch, beta1, beta2, epsilon)
        w2, m_w2, v_w2 = _adam_update(w2, grad_w2, m_w2, v_w2, learning_rate, epoch, beta1, beta2, epsilon)
        b2_array, m_b2_array, v_b2_array = _adam_update(
            np.asarray([b2]),
            np.asarray([grad_b2]),
            np.asarray([m_b2]),
            np.asarray([v_b2]),
            learning_rate,
            epoch,
            beta1,
            beta2,
            epsilon,
        )
        b2 = float(b2_array[0])
        m_b2 = float(m_b2_array[0])
        v_b2 = float(v_b2_array[0])

    return _MlpRegressor(
        feature_mean=feature_mean,
        feature_scale=feature_scale,
        target_mean=target_mean,
        target_scale=target_scale,
        w1=w1,
        b1=b1,
        w2=w2,
        b2=b2,
    )


def _predict_mlp(model: _MlpRegressor, x: np.ndarray) -> np.ndarray:
    x_scaled = (x - model.feature_mean) / model.feature_scale
    hidden = np.tanh(x_scaled @ model.w1 + model.b1)
    return (hidden @ model.w2 + model.b2) * model.target_scale + model.target_mean


def _adam_update(
    value: np.ndarray,
    grad: np.ndarray,
    moment: np.ndarray,
    velocity: np.ndarray,
    learning_rate: float,
    step_index: int,
    beta1: float,
    beta2: float,
    epsilon: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    moment = beta1 * moment + (1.0 - beta1) * grad
    velocity = beta2 * velocity + (1.0 - beta2) * (grad * grad)
    moment_hat = moment / (1.0 - beta1**step_index)
    velocity_hat = velocity / (1.0 - beta2**step_index)
    value = value - learning_rate * moment_hat / (np.sqrt(velocity_hat) + epsilon)
    return value, moment, velocity


def _build_lagged_dataset(
    grouped_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    step: float,
    objective_delta_scale: float,
    joint: bool,
) -> _LaggedKdjDataset | None:
    valid_weight_names = tuple(
        weight_name
        for weight_name in sorted(grouped_rows)
        if weight_name in FREQUENCY_RANKER_FIELDS and _field_bounds(weight_name) is not None
    )
    if not valid_weight_names:
        return None

    weight_feature_names = tuple(f"weight::{weight_name}" for weight_name in valid_weight_names) if joint else ()
    feature_names = BASE_FEATURE_NAMES + weight_feature_names
    x_rows: list[list[float]] = []
    labels: list[float] = []
    sample_weights: list[float] = []
    kdj_baselines: list[float] = []
    target_bases: list[float] = []
    row_weight_names: list[str] = []
    source_issues: list[str] = []
    target_issues: list[str] = []
    latest_by_weight: list[_LatestFeature] = []

    for weight_name in valid_weight_names:
        rows = list(grouped_rows.get(weight_name) or ())
        bounds = _field_bounds(weight_name)
        if bounds is None or len(rows) < 2 or _group_has_nan(rows) or not _strictly_increasing_issues(rows):
            continue
        one_hot = _weight_one_hot(weight_name, valid_weight_names) if joint else ()
        for current, next_row in zip(rows, rows[1:]):
            current_features = _feature_row(
                current,
                step=step,
                objective_delta_scale=objective_delta_scale,
                one_hot=one_hot,
            )
            label = _next_realized_offset(next_row, weight_name=weight_name, step=step)
            next_delta = _finite_float(next_row.get("objective_delta"))
            target_base = _finite_float(next_row.get("base_value"))
            if current_features is None or label is None or next_delta is None or target_base is None:
                return None
            x_rows.append(current_features)
            labels.append(label if next_delta > 0 else 0.0)
            sample_weights.append(1.0 if next_delta > 0 else 0.25)
            kdj_baselines.append(_finite_float(current.get("recommended_offset")) or 0.0)
            target_bases.append(target_base)
            row_weight_names.append(weight_name)
            source_issues.append(str(current.get("issue") or ""))
            target_issues.append(str(next_row.get("issue") or ""))

        latest_features = _feature_row(
            rows[-1],
            step=step,
            objective_delta_scale=objective_delta_scale,
            one_hot=one_hot,
        )
        latest_base = _finite_float(rows[-1].get("base_value"))
        if latest_features is None or latest_base is None:
            return None
        latest_by_weight.append(
            _LatestFeature(
                weight_name=weight_name,
                x=np.asarray(latest_features, dtype=float),
                base_value=latest_base,
                latest_issue=str(rows[-1].get("issue") or ""),
            )
        )

    if not x_rows or not latest_by_weight:
        return None
    order = sorted(range(len(x_rows)), key=lambda index: (target_issues[index], source_issues[index], row_weight_names[index]))
    x_rows = [x_rows[index] for index in order]
    labels = [labels[index] for index in order]
    sample_weights = [sample_weights[index] for index in order]
    kdj_baselines = [kdj_baselines[index] for index in order]
    target_bases = [target_bases[index] for index in order]
    row_weight_names = [row_weight_names[index] for index in order]
    source_issues = [source_issues[index] for index in order]
    target_issues = [target_issues[index] for index in order]
    arrays = (
        np.asarray(x_rows, dtype=float),
        np.asarray(labels, dtype=float),
        np.asarray(sample_weights, dtype=float),
        np.asarray(kdj_baselines, dtype=float),
        np.asarray(target_bases, dtype=float),
    )
    if not all(np.all(np.isfinite(array)) for array in arrays):
        return None
    return _LaggedKdjDataset(
        feature_names=feature_names,
        x=arrays[0],
        y=arrays[1],
        sample_weight=arrays[2],
        kdj_baseline=arrays[3],
        target_base_value=arrays[4],
        weight_names=tuple(row_weight_names),
        source_issues=tuple(source_issues),
        target_issues=tuple(target_issues),
        latest_by_weight=tuple(latest_by_weight),
    )


def _feature_row(
    row: Mapping[str, Any],
    *,
    step: float,
    objective_delta_scale: float,
    one_hot: tuple[float, ...],
) -> list[float] | None:
    rsv = _finite_float(row.get("rsv"))
    k_value = _finite_float(row.get("k_value", row.get("k")))
    d_value = _finite_float(row.get("d_value", row.get("d")))
    j_value = _finite_float(row.get("j_value", row.get("j")))
    recommended_offset = _finite_float(row.get("recommended_offset"))
    close_value = _finite_float(row.get("close_value"))
    base_value = _finite_float(row.get("base_value"))
    objective_delta = _finite_float(row.get("objective_delta"))
    sample_count = _finite_float(row.get("sample_count"))
    required = (rsv, k_value, d_value, j_value, recommended_offset, close_value, base_value, objective_delta, sample_count)
    if any(value is None for value in required) or sample_count is None or sample_count < 0:
        return None
    low_value, high_value = _interval_bounds(row, base_value=base_value, close_value=close_value)
    width = max(high_value - low_value, step)
    interval_position = _clip((close_value - low_value) / width, 0.0, 1.0)
    scale = max(abs(objective_delta_scale), 1e-12)
    return [
        rsv,
        k_value,
        d_value,
        j_value,
        k_value - d_value,
        j_value - 50.0,
        interval_position,
        (close_value - low_value) / step,
        (high_value - close_value) / step,
        width / step,
        max(0.0, (j_value - 80.0) / 20.0),
        max(0.0, (20.0 - j_value) / 20.0),
        recommended_offset / step,
        (close_value - base_value) / step,
        objective_delta / scale,
        log1p(sample_count),
        *one_hot,
    ]


def _interval_bounds(row: Mapping[str, Any], *, base_value: float, close_value: float) -> tuple[float, float]:
    low_value = _finite_float(row.get("rolling_low_value"))
    high_value = _finite_float(row.get("rolling_high_value"))
    if low_value is None:
        low_value = _finite_float(row.get("issue_low_value"))
    if high_value is None:
        high_value = _finite_float(row.get("issue_high_value"))
    if low_value is None:
        low_value = min(base_value, close_value)
    if high_value is None:
        high_value = max(base_value, close_value)
    if high_value < low_value:
        low_value, high_value = high_value, low_value
    if high_value <= low_value:
        low_value = min(low_value, base_value, close_value)
        high_value = max(high_value, base_value, close_value)
    return low_value, high_value


def _next_realized_offset(row: Mapping[str, Any], *, weight_name: str, step: float) -> float | None:
    close_value = _finite_float(row.get("close_value"))
    base_value = _finite_float(row.get("base_value"))
    if close_value is None or base_value is None:
        return None
    return _bounded_offset(close_value - base_value, base_value, weight_name=weight_name, step=step)


def _looks_like_close_base_leakage(dataset: _LaggedKdjDataset, *, train_rows: int, step: float) -> bool:
    try:
        close_base_index = dataset.feature_names.index("close_minus_base_steps")
    except ValueError:
        return False
    y_val = dataset.y[train_rows:]
    if y_val.size == 0:
        return False
    close_base_pred = dataset.x[train_rows:, close_base_index] * step
    close_base_pred = _bounded_offsets(
        close_base_pred,
        dataset.target_base_value[train_rows:],
        dataset.weight_names[train_rows:],
        step=step,
    )
    mae = _weighted_mae(y_val, close_base_pred, dataset.sample_weight[train_rows:])
    return np.isfinite(mae) and mae <= max(1e-9, step * 1e-6) and np.ptp(y_val) > 1e-12


def _bounded_offsets(
    offsets: np.ndarray,
    base_values: np.ndarray,
    weight_names: Sequence[str],
    *,
    step: float,
) -> np.ndarray:
    return np.asarray(
        [
            _bounded_offset(float(offset), float(base), weight_name=weight_name, step=step)
            for offset, base, weight_name in zip(offsets, base_values, weight_names, strict=True)
        ],
        dtype=float,
    )


def _bounded_offset(offset: float, base_value: float, *, weight_name: str, step: float) -> float:
    bounds = _field_bounds(weight_name)
    if bounds is None:
        return 0.0
    bounded_value = _clip(base_value + offset, *bounds)
    quantized = round((bounded_value - base_value) / step) * step
    return _clip(base_value + quantized, *bounds) - base_value


def _weighted_mae(y_true: np.ndarray, y_pred: np.ndarray, sample_weight: np.ndarray) -> float:
    total_weight = float(np.sum(sample_weight))
    if total_weight <= 0:
        return float("nan")
    return float(np.sum(np.abs(y_true - y_pred) * sample_weight) / total_weight)


def _group_ordered_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[tuple[int, Mapping[str, Any]]]] = {}
    for index, row in enumerate(rows):
        grouped.setdefault(str(row.get("weight_name") or ""), []).append((index, row))
    return {
        weight_name: [row for _index, row in sorted(items, key=lambda item: _row_order_key(item[1], item[0]))]
        for weight_name, items in grouped.items()
    }


def _row_order_key(row: Mapping[str, Any], index: int) -> tuple[str, str, int]:
    return (str(row.get("issue") or ""), str(row.get("draw_date") or ""), index)


def _strictly_increasing_issues(rows: Sequence[Mapping[str, Any]]) -> bool:
    issues = [str(row.get("issue") or "") for row in rows]
    return len(issues) == len(set(issues)) and all(left < right for left, right in zip(issues, issues[1:]))


def _group_has_nan(rows: Sequence[Mapping[str, Any]]) -> bool:
    numeric_keys = (
        "base_value",
        "close_value",
        "rsv",
        "k_value",
        "d_value",
        "j_value",
        "recommended_offset",
        "objective_delta",
        "sample_count",
    )
    return any(key in row and not _is_finite_number(row.get(key)) for row in rows for key in numeric_keys)


def _field_bounds(weight_name: str) -> tuple[float, float] | None:
    if weight_name not in FREQUENCY_RANKER_FIELDS:
        return None
    if weight_name in PRIMARY_WEIGHT_FIELDS:
        return (0.0, 1.25)
    return (-0.30, 0.30)


def _weight_one_hot(weight_name: str, weight_names: Sequence[str]) -> tuple[float, ...]:
    return tuple(1.0 if name == weight_name else 0.0 for name in weight_names)


def _finite_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def _is_finite_number(value: Any) -> bool:
    return _finite_float(value) is not None


def _clip(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def _stable_int(value: str) -> int:
    return int(sha256(value.encode("utf-8")).hexdigest()[:8], 16)


def _record_str(record: NeuralKdjOffsetAdvice | Mapping[str, Any], key: str) -> str:
    if isinstance(record, NeuralKdjOffsetAdvice):
        return str(getattr(record, key))
    return str(record.get(key) or "")


def _record_float(record: NeuralKdjOffsetAdvice | Mapping[str, Any], key: str) -> float:
    if isinstance(record, NeuralKdjOffsetAdvice):
        return float(getattr(record, key))
    return _finite_float(record.get(key)) or 0.0


def _record_source(record: NeuralKdjOffsetAdvice | Mapping[str, Any]) -> str:
    return _record_str(record, "source")


def _advice_to_dict(record: NeuralKdjOffsetAdvice | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(record, NeuralKdjOffsetAdvice):
        return record.to_dict()
    payload = dict(record)
    if "feature_names" in payload:
        payload["feature_names"] = list(payload["feature_names"])
    payload.setdefault("source", ADVISOR_SOURCE)
    payload.setdefault("advisory_only", True)
    return payload


def _matching_advice_for_config(
    base_config: FrequencyRankerConfig,
    config: FrequencyRankerConfig,
    advice_dicts: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    changed_fields = {
        field
        for field in FREQUENCY_RANKER_FIELDS
        if abs(float(getattr(config, field)) - float(getattr(base_config, field))) > 1e-12
    }
    return [item for item in advice_dicts if str(item.get("weight_name") or "") in changed_fields]
