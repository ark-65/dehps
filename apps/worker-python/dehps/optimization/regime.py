from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from psycopg import Connection

from dehps.storage.postgres_store import latest_draw_date_until, load_history_since_date, load_history_until


HistoryScope = Literal["full_history_audit", "current_regime_default"]


@dataclass(frozen=True)
class HistorySelection:
    scope: HistoryScope
    as_of_issue: str | None
    regime_years: int
    start_date: date | None
    evidence_note: str
    history: list[tuple[str, tuple[int, ...]]]


CURRENT_REGIME_EVIDENCE_NOTE = (
    "Current public SSQ draw-equipment material facts are documented, but no authoritative issue-level "
    "material-change schedule is frozen in this repository. Use the last 10 years as the default current "
    "physical-regime proxy until sourced regime boundaries are added."
)


def subtract_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)


def select_history(
    conn: Connection,
    *,
    scope: HistoryScope,
    as_of_issue: str | None = None,
    regime_years: int = 10,
) -> HistorySelection:
    if regime_years < 1:
        raise ValueError("regime_years must be at least 1")

    if scope == "full_history_audit":
        return HistorySelection(
            scope=scope,
            as_of_issue=as_of_issue,
            regime_years=regime_years,
            start_date=None,
            evidence_note="Full history is used for audit only; it is not the default model-training regime.",
            history=load_history_until(conn, as_of_issue),
        )

    if scope == "current_regime_default":
        latest_date = latest_draw_date_until(conn, as_of_issue)
        if latest_date is None:
            return HistorySelection(
                scope=scope,
                as_of_issue=as_of_issue,
                regime_years=regime_years,
                start_date=None,
                evidence_note=CURRENT_REGIME_EVIDENCE_NOTE,
                history=[],
            )
        start_date = subtract_years(latest_date, regime_years)
        return HistorySelection(
            scope=scope,
            as_of_issue=as_of_issue,
            regime_years=regime_years,
            start_date=start_date,
            evidence_note=CURRENT_REGIME_EVIDENCE_NOTE,
            history=load_history_since_date(conn, start_date=start_date, as_of_issue=as_of_issue),
        )

    raise ValueError(f"unsupported history scope: {scope}")
