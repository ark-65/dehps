from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class SsqDraw(BaseModel):
    issue: str
    draw_date: date | None = None
    red_numbers: tuple[int, int, int, int, int, int]
    blue_number: int | None = Field(default=None, ge=1, le=16)
    source: str | None = None

