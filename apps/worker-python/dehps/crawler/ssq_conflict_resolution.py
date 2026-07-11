from __future__ import annotations

from typing import Any, Literal

from psycopg import Connection

from dehps.storage.postgres_store import ensure_ssq_data_conflicts_resolution_schema


ResolutionAction = Literal["existing", "incoming"]


class SsqConflictResolutionError(ValueError):
    """Raised when a conflict cannot be resolved without losing audit safety."""


def _numbers(value: object) -> tuple[int, ...]:
    return tuple(int(number) for number in (value or []))


def _validated_red_numbers(value: object, *, label: str) -> tuple[int, ...]:
    numbers = _numbers(value)
    if (
        len(numbers) != 6
        or tuple(sorted(numbers)) != numbers
        or len(set(numbers)) != 6
        or any(number < 1 or number > 33 for number in numbers)
    ):
        raise SsqConflictResolutionError(f"invalid_{label}_red_numbers:{numbers}")
    return numbers


def resolve_ssq_data_conflict(
    conn: Connection,
    *,
    conflict_id: int,
    action: ResolutionAction,
    resolution_note: str,
    resolved_by: str,
) -> dict[str, Any]:
    note = str(resolution_note or "").strip()
    actor = str(resolved_by or "").strip()
    if action not in {"existing", "incoming"}:
        raise SsqConflictResolutionError(f"invalid_resolution_action:{action}")
    if not note:
        raise SsqConflictResolutionError("resolution_note_required")
    if not actor:
        raise SsqConflictResolutionError("resolved_by_required")
    if int(conflict_id) <= 0:
        raise SsqConflictResolutionError(f"invalid_conflict_id:{conflict_id}")

    ensure_ssq_data_conflicts_resolution_schema(conn)
    conflict = conn.execute(
        """
        SELECT issue, existing_red_numbers, incoming_red_numbers,
               existing_blue_number, incoming_blue_number, source, resolved_at
        FROM ssq_data_conflicts
        WHERE id = %s
        FOR UPDATE
        """,
        (int(conflict_id),),
    ).fetchone()
    if not conflict:
        raise SsqConflictResolutionError(f"conflict_not_found:{conflict_id}")
    if conflict[6] is not None:
        raise SsqConflictResolutionError(f"conflict_already_resolved:{conflict_id}")

    issue = str(conflict[0])
    existing_red = _validated_red_numbers(conflict[1], label="existing")
    incoming_red = _validated_red_numbers(conflict[2], label="incoming")
    existing_blue = int(conflict[3]) if conflict[3] is not None else None
    incoming_blue = int(conflict[4]) if conflict[4] is not None else None
    incoming_source = str(conflict[5] or "")
    canonical = conn.execute(
        "SELECT red_numbers, blue_number FROM ssq_history WHERE issue = %s FOR UPDATE",
        (issue,),
    ).fetchone()
    if not canonical:
        raise SsqConflictResolutionError(f"canonical_issue_missing:{issue}")
    canonical_red = _validated_red_numbers(canonical[0], label="canonical")
    canonical_blue = int(canonical[1]) if canonical[1] is not None else None
    existing_state = (existing_red, existing_blue)
    incoming_state = (incoming_red, incoming_blue)
    canonical_state = (canonical_red, canonical_blue)

    selected_state = existing_state if action == "existing" else incoming_state
    if canonical_state not in {existing_state, incoming_state}:
        raise SsqConflictResolutionError(
            f"canonical_changed_outside_conflict:{issue}:{canonical_red}:{canonical_blue}"
        )
    canonical_updated = False
    if canonical_state != selected_state:
        if action != "incoming":
            raise SsqConflictResolutionError(
                f"canonical_no_longer_matches_existing:{issue}"
            )
        conn.execute(
            """
            UPDATE ssq_history
            SET red_numbers = %s,
                r1 = %s, r2 = %s, r3 = %s, r4 = %s, r5 = %s, r6 = %s,
                blue_number = %s,
                source = %s
            WHERE issue = %s
            """,
            (
                list(incoming_red),
                *incoming_red,
                incoming_blue,
                incoming_source,
                issue,
            ),
        )
        canonical_updated = True

    resolved_rows = conn.execute(
        """
        UPDATE ssq_data_conflicts
        SET resolution_action = %s,
            resolution_note = %s,
            resolved_by = %s,
            resolved_red_numbers = %s,
            resolved_blue_number = %s,
            resolved_at = now()
        WHERE resolved_at IS NULL
          AND issue = %s
          AND existing_red_numbers = %s
          AND incoming_red_numbers = %s
          AND existing_blue_number IS NOT DISTINCT FROM %s
          AND incoming_blue_number IS NOT DISTINCT FROM %s
        RETURNING id
        """,
        (
            action,
            note,
            actor,
            list(selected_state[0]),
            selected_state[1],
            issue,
            list(existing_red),
            list(incoming_red),
            existing_blue,
            incoming_blue,
        ),
    ).fetchall()
    resolved_ids = [int(row[0]) for row in resolved_rows]
    if int(conflict_id) not in resolved_ids:
        raise SsqConflictResolutionError(
            f"conflict_resolution_update_missed:{conflict_id}"
        )
    return {
        "status": "resolved",
        "conflict_id": int(conflict_id),
        "resolved_conflict_ids": resolved_ids,
        "issue": issue,
        "action": action,
        "canonical_updated": canonical_updated,
        "resolved_red_numbers": list(selected_state[0]),
        "resolved_blue_number": selected_state[1],
        "resolution_note": note,
        "resolved_by": actor,
    }
