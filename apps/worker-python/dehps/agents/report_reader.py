from __future__ import annotations

import ast
import json
import math
from typing import Any

from pydantic import BaseModel, Field


class ExperimentReportSummary(BaseModel):
    experiment_key: str
    strategy_key: str
    metrics: dict[str, int | float] = Field(default_factory=dict)
    missed_issues: list[str] = Field(default_factory=list)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)


def parse_experiment_report(markdown: str) -> ExperimentReportSummary:
    fields: dict[str, Any] = {"metrics": {}, "missed_issues": [], "config_snapshot": {}}
    section = None

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("## "):
            section = line.removeprefix("## ").strip()
            continue
        if line.startswith("- Experiment:"):
            fields["experiment_key"] = _strip_code(line.split(":", 1)[1].strip())
            continue
        if line.startswith("- Strategy:"):
            fields["strategy_key"] = _strip_code(line.split(":", 1)[1].strip())
            continue
        if section == "Metrics" and line.startswith("- "):
            key, value = _split_bullet(line)
            fields["metrics"][key] = _parse_number(value)
            continue
        if section == "Missed Issues" and line.startswith("- "):
            issue = _strip_code(line.removeprefix("- ").strip())
            if issue != "None":
                fields["missed_issues"].append(issue)
            continue
        if section == "Config Snapshot" and line.startswith("- "):
            key, value = _split_bullet(line)
            fields["config_snapshot"][key] = _parse_value(value)

    return ExperimentReportSummary(**fields)


def _split_bullet(line: str) -> tuple[str, str]:
    body = line.removeprefix("- ")
    if ":" not in body:
        raise ValueError(f"expected '- key: value' bullet, got {line!r}")
    key, value = body.split(":", 1)
    return key.strip(), value.strip()


def _strip_code(value: str) -> str:
    return value.strip().strip("`")


def _parse_number(value: str) -> int | float:
    parsed = _parse_value(value)
    if isinstance(parsed, bool) or not isinstance(parsed, int | float):
        raise ValueError(f"expected numeric metric, got {value!r}")
    if isinstance(parsed, float) and not math.isfinite(parsed):
        raise ValueError(f"expected finite numeric metric, got {value!r}")
    return parsed


def _parse_value(value: str) -> Any:
    value = _strip_code(value)
    if value == "None":
        return None
    if value in {"True", "False"}:
        return value == "True"
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return value
