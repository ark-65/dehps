"""Frozen definitions preserved from dehps/research_os/information_theory/measurement_system_v2/bounded_operational_forward.py.

Original files remain the legacy compatibility implementation. This release-local
copy has explicit calculation-only imports; scientific bodies are checked against
the originals. No historical digest or source contract is rewritten.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date


class M4V2BoundedOperationalForwardError(ValueError):
    pass


def _normalize_history_rows(
    history_rows: Sequence[object], *, before_issue: str
) -> tuple[tuple[str, str, tuple[int, ...]], ...]:
    normalized: list[tuple[str, str, tuple[int, ...]]] = []
    for row in history_rows:
        if not isinstance(row, Sequence) or len(row) != 3:
            raise M4V2BoundedOperationalForwardError("history_row_invalid")
        issue = str(row[0])
        draw_date = row[1]
        numbers = tuple(int(item) for item in row[2])
        if issue >= before_issue:
            continue
        if (
            not isinstance(draw_date, date)
            or len(numbers) != 6
            or tuple(sorted(numbers)) != numbers
            or len(set(numbers)) != 6
            or numbers[0] < 1
            or numbers[-1] > 33
        ):
            raise M4V2BoundedOperationalForwardError("history_boundary_invalid")
        normalized.append((issue, draw_date.isoformat(), numbers))
    if len(normalized) < 900 or tuple(item[0] for item in normalized) != tuple(
        sorted(item[0] for item in normalized)
    ):
        raise M4V2BoundedOperationalForwardError("training_history_invalid")
    return tuple(normalized)
