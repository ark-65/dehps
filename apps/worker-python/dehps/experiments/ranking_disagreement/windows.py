from __future__ import annotations

from datetime import date
from typing import Any

from psycopg.rows import dict_row

from dehps.db import get_connection
from dehps.domain.combination import normalize_red_numbers
from dehps.experiments.ranking_disagreement.models import DrawRecord, IssueWindows, stable_hash


def load_history() -> tuple[DrawRecord, ...]:
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(
            """
            SELECT issue, draw_date, red_numbers
            FROM ssq_history
            ORDER BY draw_date NULLS FIRST, issue
            """
        ).fetchall()
    return tuple(_draw(row) for row in rows)


def build_issue_windows(
    history: tuple[DrawRecord, ...],
    *,
    search_issue_count: int = 100,
    frozen_issue_count: int = 20,
    minimum_training_issues: int = 20,
) -> IssueWindows:
    if search_issue_count < 1 or frozen_issue_count < 1 or minimum_training_issues < 1:
        raise ValueError("window sizes must all be positive")
    required = minimum_training_issues + search_issue_count + frozen_issue_count
    if len(history) < required:
        raise ValueError(
            "insufficient historical issues for frozen Round 24 windows: "
            f"have {len(history)}, require {required}"
        )
    start = len(history) - search_issue_count - frozen_issue_count
    if start < minimum_training_issues:
        raise ValueError("search window would not have enough pre-target history")
    search = tuple(draw.issue for draw in history[start : start + search_issue_count])
    frozen = tuple(draw.issue for draw in history[start + search_issue_count : start + search_issue_count + frozen_issue_count])
    if set(search) & set(frozen):
        raise ValueError("search and frozen validation windows overlap")
    return IssueWindows(
        feasibility_issue=search[0],
        search_issues=search,
        frozen_issues=frozen,
        forward_issues=(),
        search_issue_count=search_issue_count,
        frozen_issue_count=frozen_issue_count,
        minimum_training_issues=minimum_training_issues,
    ).finalized()


def history_before_issue(history: tuple[DrawRecord, ...], issue: str) -> tuple[DrawRecord, ...]:
    for index, draw in enumerate(history):
        if draw.issue == issue:
            if index == 0:
                raise ValueError(f"issue has no pre-target history: {issue}")
            return tuple(history[:index])
    raise ValueError(f"issue not found in history: {issue}")


def target_for_issue(history: tuple[DrawRecord, ...], issue: str) -> DrawRecord:
    for draw in history:
        if draw.issue == issue:
            return draw
    raise ValueError(f"issue not found in history: {issue}")


def history_fingerprint(history: tuple[DrawRecord, ...]) -> str:
    return stable_hash(
        {
            "schema": "ssq-history-prefix-v1",
            "draws": [
                {
                    "issue": draw.issue,
                    "draw_date": draw.draw_date.isoformat() if draw.draw_date else None,
                    "red_numbers": draw.red_numbers,
                }
                for draw in history
            ],
        }
    )


def full_history_fingerprint(history: tuple[DrawRecord, ...]) -> str:
    return history_fingerprint(history)


def _draw(row: dict[str, Any]) -> DrawRecord:
    raw_date = row.get("draw_date")
    draw_date = raw_date if isinstance(raw_date, date) else None
    return DrawRecord(
        issue=str(row["issue"]),
        draw_date=draw_date,
        red_numbers=normalize_red_numbers(row["red_numbers"]),
    )
