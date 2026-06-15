from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel

from dehps.domain.combination import normalize_red_numbers


class ValidatedSsqDraw(BaseModel):
    issue: str
    draw_date: date | None
    red_numbers: tuple[int, int, int, int, int, int]
    blue_number: int | None
    source: str | None = None
    raw_payload: dict[str, Any] | None = None


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10] if fmt != "%Y%m%d" else text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"invalid draw_date: {value}")


def _extract_red_numbers(draw: dict[str, Any]) -> list[int]:
    if "red_numbers" in draw:
        value = draw["red_numbers"]
        if isinstance(value, str):
            return [int(part) for part in value.replace(",", " ").split()]
        return [int(n) for n in value]
    keys = ["r1", "r2", "r3", "r4", "r5", "r6"]
    if all(k in draw for k in keys):
        return [int(draw[k]) for k in keys]
    raise ValueError("missing red_numbers")


def validate_ssq_draw(draw: dict[str, Any]) -> ValidatedSsqDraw:
    issue = str(draw.get("issue") or "").strip()
    if not issue:
        raise ValueError("issue is required")

    red_numbers = normalize_red_numbers(_extract_red_numbers(draw))
    blue_value = draw.get("blue_number", draw.get("blue"))
    blue_number = int(blue_value) if blue_value not in (None, "") else None
    if blue_number is not None and not 1 <= blue_number <= 16:
        raise ValueError("blue_number must be between 1 and 16")

    return ValidatedSsqDraw(
        issue=issue,
        draw_date=_parse_date(draw.get("draw_date") or draw.get("date")),
        red_numbers=red_numbers,  # type: ignore[arg-type]
        blue_number=blue_number,
        source=draw.get("source"),
        raw_payload=dict(draw),
    )

