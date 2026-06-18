from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from math import ceil, log1p
from typing import Any, Mapping, Sequence

import numpy as np

from dehps.models.frequency_ranker import FrequencyRankerConfig


ADVISOR_SOURCE = "ml_kdj_offset_advisor_v0"
PRIMARY_WEIGHT_FIELDS = ("structural_weight", "frequency_weight", "omission_weight")
FREQUENCY_RANKER_FIELDS = tuple(field.name for field in fields(FrequencyRankerConfig))
BASE_FEATURE_NAMES = (
    "rsv",
    "k",
    "d",
    "j",
    "k_minus_d",
    "j_minus_50",
    "recommended_offset_steps",
    "close_minus_base_steps",
    "scaled_objective_delta",
    "log1p_sample_count",
)


@dataclass(frozen=True)
class RidgeKdjOffsetAdvice:
    weight_name: str
    suggested_offset: float
    confidence: float
    train_rows: int
    validation_metric: float
    baseline_metric: float
    source: str = ADVISOR_SOURCE

    def to_dict(self) -> dict[str, float | int | str]:
        return asdict(self)


@dataclass(frozen=True)
class _LaggedKdjDataset:
    weight_name: str
    feature_names: tuple[str, ...]
    x: np.ndarray
    y: np.ndarray
    sample_weight: np.ndarray
    kdj_baseline: np.ndarray
    target_base_value: np.ndarray
    source_issues: tuple[str, ...]
    target_issues: tuple[str, ...]
    latest_x: np.ndarray
    latest_base_value: float


def numpy_ridge_kdj_offset_v0(
    rows: Sequence[Mapping[str, Any]],
    *,
    step: float,
    ridge_alpha: float = 1.0,
    validation_fraction: float = 0.25,
    min_train_rows: int = 12,
    min_validation_rows: int = 4,
    objective_delta_scale: float = 10.0,
) -> tuple[RidgeKdjOffsetAdvice, ...]:
    if step <= 0 or ridge_alpha < 0 or not rows:
        return ()

    advice: list[RidgeKdjOffsetAdvice] = []
    for weight_name, weight_rows in _group_ordered_rows(rows).items():
        if weight_name not in FREQUENCY_RANKER_FIELDS:
            continue
        bounds = _field_bounds(weight_name)
        if bounds is None or _group_has_nan(weight_rows):
            continue
        dataset = _build_lagged_dataset(
            weight_rows,
            weight_name=weight_name,
            step=step,
            bounds=bounds,
            objective_delta_scale=objective_delta_scale,
        )
        if dataset is None:
            continue
        candidate = _fit_and_validate_advice(
            dataset,
            bounds=bounds,
            step=step,
            ridge_alpha=ridge_alpha,
            validation_fraction=validation_fraction,
            min_train_rows=min_train_rows,
            min_validation_rows=min_validation_rows,
        )
        if candidate is not None:
            advice.append(candidate)

    return tuple(sorted(advice, key=lambda item: (-item.confidence, item.weight_name)))


def ridge_kdj_advice_to_frequency_ranker_config_candidates(
    base: FrequencyRankerConfig,
    advice_records: Sequence[RidgeKdjOffsetAdvice | Mapping[str, Any]],
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
    seen: set[tuple[tuple[str, float], ...]] = set()
    for record in ranked:
        field = _record_str(record, "weight_name")
        if field not in FREQUENCY_RANKER_FIELDS:
            continue
        offset = _record_float(record, "suggested_offset")
        if offset == 0:
            continue
        values = dict(base.__dict__)
        bounds = _field_bounds(field)
        if bounds is None:
            continue
        values[field] = _clip(float(values[field]) + offset, *bounds)
        config = FrequencyRankerConfig(**values)
        key = tuple(sorted((name, round(float(value), 12)) for name, value in config.__dict__.items()))
        if key in seen:
            continue
        seen.add(key)
        configs.append(config)
        if len(configs) >= max_configs:
            break
    return tuple(configs)


def _fit_and_validate_advice(
    dataset: _LaggedKdjDataset,
    *,
    bounds: tuple[float, float],
    step: float,
    ridge_alpha: float,
    validation_fraction: float,
    min_train_rows: int,
    min_validation_rows: int,
) -> RidgeKdjOffsetAdvice | None:
    row_count = int(dataset.x.shape[0])
    if row_count < min_train_rows + min_validation_rows:
        return None
    if not np.any(dataset.sample_weight >= 1.0) or np.ptp(dataset.y[dataset.sample_weight >= 1.0]) <= 1e-12:
        return None

    validation_rows = max(min_validation_rows, int(ceil(row_count * validation_fraction)))
    validation_rows = min(validation_rows, row_count - min_train_rows)
    train_rows = row_count - validation_rows
    if train_rows < min_train_rows or validation_rows < min_validation_rows:
        return None

    x_train = dataset.x[:train_rows]
    y_train = dataset.y[:train_rows]
    weights_train = dataset.sample_weight[:train_rows]
    x_val = dataset.x[train_rows:]
    y_val = dataset.y[train_rows:]
    weights_val = dataset.sample_weight[train_rows:]

    means = x_train.mean(axis=0)
    scales = x_train.std(axis=0)
    scales = np.where(scales < 1e-12, 1.0, scales)
    x_train_scaled = (x_train - means) / scales
    x_val_scaled = (x_val - means) / scales

    coefficients = _weighted_ridge_fit(x_train_scaled, y_train, weights_train, ridge_alpha=ridge_alpha)
    val_pred = _predict_with_intercept(x_val_scaled, coefficients)
    val_pred = _bounded_offsets(val_pred, dataset.target_base_value[train_rows:], bounds=bounds, step=step)
    kdj_pred = _bounded_offsets(dataset.kdj_baseline[train_rows:], dataset.target_base_value[train_rows:], bounds=bounds, step=step)
    noop_pred = np.zeros_like(y_val)

    validation_metric = _weighted_mae(y_val, val_pred, weights_val)
    baseline_metric = min(_weighted_mae(y_val, noop_pred, weights_val), _weighted_mae(y_val, kdj_pred, weights_val))
    if not np.isfinite(validation_metric) or not np.isfinite(baseline_metric):
        return None
    if baseline_metric <= 1e-12 or validation_metric >= baseline_metric:
        return None

    latest_scaled = (dataset.latest_x.reshape(1, -1) - means) / scales
    suggested = float(_predict_with_intercept(latest_scaled, coefficients)[0])
    suggested = _bounded_offset(suggested, dataset.latest_base_value, bounds=bounds, step=step)
    if abs(suggested) < step / 2:
        return None
    confidence = float(_clip((baseline_metric - validation_metric) / baseline_metric, 0.0, 1.0))
    return RidgeKdjOffsetAdvice(
        weight_name=dataset.weight_name,
        suggested_offset=suggested,
        confidence=confidence,
        train_rows=train_rows,
        validation_metric=float(validation_metric),
        baseline_metric=float(baseline_metric),
    )


def _weighted_ridge_fit(x: np.ndarray, y: np.ndarray, sample_weight: np.ndarray, *, ridge_alpha: float) -> np.ndarray:
    design = np.column_stack((np.ones(x.shape[0]), x))
    sqrt_weight = np.sqrt(np.maximum(sample_weight, 0.0)).reshape(-1, 1)
    weighted_design = design * sqrt_weight
    weighted_y = y * sqrt_weight.ravel()
    penalty = np.eye(design.shape[1]) * ridge_alpha
    penalty[0, 0] = 0.0
    lhs = weighted_design.T @ weighted_design + penalty
    rhs = weighted_design.T @ weighted_y
    try:
        return np.linalg.solve(lhs, rhs)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(lhs) @ rhs


def _predict_with_intercept(x: np.ndarray, coefficients: np.ndarray) -> np.ndarray:
    return coefficients[0] + x @ coefficients[1:]


def _build_lagged_dataset(
    rows: Sequence[Mapping[str, Any]],
    *,
    weight_name: str,
    step: float,
    bounds: tuple[float, float],
    objective_delta_scale: float = 10.0,
) -> _LaggedKdjDataset | None:
    if len(rows) < 2:
        return None
    include_base_value = all(_is_finite_number(row.get("base_value")) for row in rows)
    feature_names = BASE_FEATURE_NAMES + (("base_value",) if include_base_value else ())

    x_rows: list[list[float]] = []
    labels: list[float] = []
    sample_weights: list[float] = []
    kdj_baselines: list[float] = []
    target_bases: list[float] = []
    source_issues: list[str] = []
    target_issues: list[str] = []

    for current, next_row in zip(rows, rows[1:]):
        current_features = _feature_row(current, step=step, include_base_value=include_base_value, objective_delta_scale=objective_delta_scale)
        if current_features is None:
            return None
        label = _next_realized_offset(next_row, step=step, bounds=bounds)
        if label is None:
            return None
        next_delta = _finite_float(next_row.get("objective_delta"))
        if next_delta is None:
            return None
        target_base = _finite_float(next_row.get("base_value"))
        if target_base is None:
            return None
        x_rows.append(current_features)
        labels.append(label if next_delta > 0 else 0.0)
        sample_weights.append(1.0 if next_delta > 0 else 0.25)
        kdj_baselines.append(_finite_float(current.get("recommended_offset")) or 0.0)
        target_bases.append(target_base)
        source_issues.append(str(current.get("issue") or ""))
        target_issues.append(str(next_row.get("issue") or ""))

    latest_x = _feature_row(rows[-1], step=step, include_base_value=include_base_value, objective_delta_scale=objective_delta_scale)
    latest_base_value = _finite_float(rows[-1].get("base_value"))
    if latest_x is None or latest_base_value is None:
        return None

    arrays = (
        np.asarray(x_rows, dtype=float),
        np.asarray(labels, dtype=float),
        np.asarray(sample_weights, dtype=float),
        np.asarray(kdj_baselines, dtype=float),
        np.asarray(target_bases, dtype=float),
        np.asarray(latest_x, dtype=float),
    )
    if not all(np.all(np.isfinite(array)) for array in arrays):
        return None
    return _LaggedKdjDataset(
        weight_name=weight_name,
        feature_names=feature_names,
        x=arrays[0],
        y=arrays[1],
        sample_weight=arrays[2],
        kdj_baseline=arrays[3],
        target_base_value=arrays[4],
        source_issues=tuple(source_issues),
        target_issues=tuple(target_issues),
        latest_x=arrays[5],
        latest_base_value=latest_base_value,
    )


def _feature_row(
    row: Mapping[str, Any],
    *,
    step: float,
    include_base_value: bool,
    objective_delta_scale: float,
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
    scale = max(abs(objective_delta_scale), 1e-12)
    features = [
        rsv,
        k_value,
        d_value,
        j_value,
        k_value - d_value,
        j_value - 50.0,
        recommended_offset / step,
        (close_value - base_value) / step,
        objective_delta / scale,
        log1p(sample_count),
    ]
    if include_base_value:
        features.append(base_value)
    return features


def _next_realized_offset(row: Mapping[str, Any], *, step: float, bounds: tuple[float, float]) -> float | None:
    close_value = _finite_float(row.get("close_value"))
    base_value = _finite_float(row.get("base_value"))
    if close_value is None or base_value is None:
        return None
    bounded_value = _clip(close_value, *bounds)
    bounded_base = _clip(base_value, *bounds)
    return _bounded_offset(bounded_value - bounded_base, bounded_base, bounds=bounds, step=step)


def _bounded_offsets(offsets: np.ndarray, base_values: np.ndarray, *, bounds: tuple[float, float], step: float) -> np.ndarray:
    return np.asarray([_bounded_offset(float(offset), float(base), bounds=bounds, step=step) for offset, base in zip(offsets, base_values)], dtype=float)


def _bounded_offset(offset: float, base_value: float, *, bounds: tuple[float, float], step: float) -> float:
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


def _record_str(record: RidgeKdjOffsetAdvice | Mapping[str, Any], key: str) -> str:
    if isinstance(record, RidgeKdjOffsetAdvice):
        return str(getattr(record, key))
    return str(record.get(key) or "")


def _record_float(record: RidgeKdjOffsetAdvice | Mapping[str, Any], key: str) -> float:
    if isinstance(record, RidgeKdjOffsetAdvice):
        return float(getattr(record, key))
    return _finite_float(record.get(key)) or 0.0


def _record_source(record: RidgeKdjOffsetAdvice | Mapping[str, Any]) -> str:
    return _record_str(record, "source")
