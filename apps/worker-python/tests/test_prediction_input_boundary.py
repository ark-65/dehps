from __future__ import annotations

from datetime import date

import pytest

from dehps.models.prediction_input_boundary import (
    DRAW_PREDICTION_HISTORY_FIELDS,
    build_prediction_input_boundary,
    enforce_prediction_input_boundary,
)


SAFE_HISTORY = [
    ("2026077", date(2026, 7, 7), (1, 6, 12, 18, 24, 33)),
    ("2026078", date(2026, 7, 9), (7, 11, 14, 16, 27, 28)),
]


def test_prediction_input_boundary_accepts_market_aggregates_only_when_excluded():
    boundary = build_prediction_input_boundary(
        history=SAFE_HISTORY,
        available_history_fields=(
            "id",
            *DRAW_PREDICTION_HISTORY_FIELDS,
            "blue_number",
            "sales_amount",
            "prize_tier_counts",
        ),
    )

    assert boundary["status"] == "passed"
    assert boundary["training_fields"] == list(DRAW_PREDICTION_HISTORY_FIELDS)
    assert boundary["selected_market_aggregate_fields"] == []
    assert boundary["available_market_aggregate_fields_excluded"] == [
        "prize_tier_counts",
        "sales_amount",
    ]
    assert boundary["ticket_distribution_observed"] is False
    assert boundary["draw_probability_effect"] == "none"
    assert boundary["selection_changed"] is False
    assert boundary["promotion_allowed"] is False
    enforce_prediction_input_boundary(boundary)


def test_prediction_input_boundary_blocks_market_aggregate_training_field():
    boundary = build_prediction_input_boundary(
        history=SAFE_HISTORY,
        training_fields=(*DRAW_PREDICTION_HISTORY_FIELDS, "winner_counts"),
        available_history_fields=(*DRAW_PREDICTION_HISTORY_FIELDS, "winner_counts"),
    )

    assert boundary["status"] == "blocked"
    assert boundary["selected_market_aggregate_fields"] == ["winner_counts"]
    assert "market_aggregate_selected_for_draw_prediction" in boundary["reasons"]
    assert "unexpected_training_fields" in boundary["reasons"]
    with pytest.raises(ValueError, match="prediction input boundary blocked"):
        enforce_prediction_input_boundary(boundary)


def test_prediction_input_boundary_blocks_ambiguous_record_shape():
    boundary = build_prediction_input_boundary(
        history=[(*SAFE_HISTORY[0], 123456.0)],
    )

    assert boundary["status"] == "blocked"
    assert boundary["history_record_shape_counts"] == {"4": 1}
    assert boundary["invalid_history_record_count"] == 1
    assert boundary["reasons"] == ["invalid_or_ambiguous_history_record_shape"]


def test_prediction_input_boundary_blocks_empty_history():
    boundary = build_prediction_input_boundary(history=[])

    assert boundary["status"] == "blocked"
    assert boundary["reasons"] == ["empty_training_history"]
