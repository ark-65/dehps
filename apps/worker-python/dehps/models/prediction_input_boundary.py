from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any


PREDICTION_INPUT_BOUNDARY_PROTOCOL = "dehps-draw-outcome-input-boundary-v1"
DRAW_PREDICTION_HISTORY_FIELDS = ("issue", "draw_date", "red_numbers")
MARKET_AGGREGATE_FIELD_NAMES = frozenset(
    {
        "betting_density",
        "jackpot_pool",
        "prize_pool",
        "prize_tier_counts",
        "sales_amount",
        "sales_volume",
        "selected_number_counts",
        "ticket_distribution",
        "winner_counts",
        "winning_ticket_counts",
    }
)
MARKET_AGGREGATE_FIELD_PREFIXES = (
    "betting_",
    "jackpot_",
    "market_",
    "prize_",
    "sales_",
    "ticket_",
    "wager_",
    "winner_",
    "winning_ticket_",
)


def _normalized_field_names(values: Iterable[object]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        if value is None:
            continue
        field_name = str(value).strip().lower()
        if field_name and field_name not in normalized:
            normalized.append(field_name)
    return tuple(normalized)


def is_market_aggregate_field(field_name: object) -> bool:
    normalized = str(field_name).strip().lower()
    return normalized in MARKET_AGGREGATE_FIELD_NAMES or normalized.startswith(
        MARKET_AGGREGATE_FIELD_PREFIXES
    )


def _valid_history_record(record: object, expected_size: int) -> bool:
    if not isinstance(record, Sequence) or isinstance(record, (str, bytes, bytearray)):
        return False
    if len(record) != expected_size:
        return False
    issue, draw_date, red_numbers = record
    if not isinstance(issue, str) or not issue.strip():
        return False
    if draw_date is not None and not isinstance(draw_date, date):
        return False
    if not isinstance(red_numbers, Sequence) or isinstance(red_numbers, (str, bytes, bytearray)):
        return False
    if len(red_numbers) != 6:
        return False
    if any(isinstance(number, bool) or not isinstance(number, int) for number in red_numbers):
        return False
    return len(set(red_numbers)) == 6 and all(1 <= number <= 33 for number in red_numbers)


def build_prediction_input_boundary(
    *,
    history: Sequence[object],
    training_fields: Iterable[object] = DRAW_PREDICTION_HISTORY_FIELDS,
    available_history_fields: Iterable[object] = (),
) -> dict[str, Any]:
    selected_fields = _normalized_field_names(training_fields)
    available_fields = _normalized_field_names(available_history_fields)
    allowed_fields = set(DRAW_PREDICTION_HISTORY_FIELDS)
    selected_field_set = set(selected_fields)
    missing_required_fields = sorted(allowed_fields - selected_field_set)
    unexpected_training_fields = sorted(selected_field_set - allowed_fields)
    selected_market_fields = sorted(
        field_name for field_name in selected_fields if is_market_aggregate_field(field_name)
    )
    available_market_fields = sorted(
        field_name for field_name in available_fields if is_market_aggregate_field(field_name)
    )
    shape_counts = Counter(
        len(record)
        if isinstance(record, Sequence) and not isinstance(record, (str, bytes, bytearray))
        else -1
        for record in history
    )
    invalid_history_record_count = sum(
        not _valid_history_record(record, len(DRAW_PREDICTION_HISTORY_FIELDS))
        for record in history
    )

    reasons: list[str] = []
    if not history:
        reasons.append("empty_training_history")
    if missing_required_fields:
        reasons.append("missing_required_draw_fields")
    if unexpected_training_fields:
        reasons.append("unexpected_training_fields")
    if selected_market_fields:
        reasons.append("market_aggregate_selected_for_draw_prediction")
    if invalid_history_record_count:
        reasons.append("invalid_or_ambiguous_history_record_shape")
    status = "blocked" if reasons else "passed"

    return {
        "protocol": PREDICTION_INPUT_BOUNDARY_PROTOCOL,
        "status": status,
        "action": "block_supervisor_startup" if reasons else "continue_draw_outcome_training",
        "training_fields": list(selected_fields),
        "required_draw_fields": list(DRAW_PREDICTION_HISTORY_FIELDS),
        "missing_required_fields": missing_required_fields,
        "unexpected_training_fields": unexpected_training_fields,
        "available_history_fields": list(available_fields),
        "history_record_count": len(history),
        "history_record_shape_counts": {
            str(shape): count for shape, count in sorted(shape_counts.items())
        },
        "invalid_history_record_count": invalid_history_record_count,
        "selected_market_aggregate_fields": selected_market_fields,
        "available_market_aggregate_fields_excluded": available_market_fields,
        "ticket_distribution_observed": False,
        "ticket_distribution_identifiability": (
            "aggregate_prize_counts_do_not_identify_ticket_level_number_selection"
        ),
        "market_data_role": "separate_observation_only_not_draw_probability",
        "draw_probability_effect": "none",
        "selection_changed": False,
        "promotion_allowed": False,
        "reasons": reasons,
        "interpretation": (
            "The red-ball prediction surface accepts only issue, draw date, and realized red numbers. "
            "Sales, jackpot, prize-tier, winner-count, and ticket aggregates are excluded; without "
            "anonymized ticket-level selections they cannot identify the population selection distribution."
        ),
    }


def enforce_prediction_input_boundary(boundary: dict[str, Any]) -> None:
    if boundary.get("status") == "passed":
        return
    reasons = boundary.get("reasons") if isinstance(boundary.get("reasons"), list) else []
    detail = ",".join(str(reason) for reason in reasons) or "unknown_boundary_violation"
    raise ValueError(f"prediction input boundary blocked supervisor startup: {detail}")
