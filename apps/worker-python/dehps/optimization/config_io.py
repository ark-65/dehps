from __future__ import annotations

from math import isfinite
from typing import Any, Mapping

from dehps.models.frequency_ranker import FrequencyRankerConfig


def frequency_ranker_config_values(
    raw_config: Mapping[str, Any],
    *,
    source_label: str,
    reject_unknown: bool = True,
    unknown_error_prefix: str | None = None,
) -> dict[str, float]:
    values = dict(FrequencyRankerConfig().__dict__)
    unknown = sorted(set(raw_config) - set(values))
    if unknown and reject_unknown:
        prefix = unknown_error_prefix or f"unknown config fields in {source_label}"
        raise ValueError(f"{prefix}: {', '.join(unknown)}")
    for field, raw_value in raw_config.items():
        if field not in values:
            continue
        values[field] = finite_config_float(raw_value, field=field, source_label=source_label)
    return values


def finite_config_float(raw_value: Any, *, field: str, source_label: str) -> float:
    if isinstance(raw_value, bool):
        raise ValueError(f"{source_label} field {field} must be a finite number")
    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{source_label} field {field} must be a finite number") from exc
    if not isfinite(value):
        raise ValueError(f"{source_label} field {field} must be a finite number")
    return value
