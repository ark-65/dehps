from __future__ import annotations

from datetime import date

import dehps.optimization.prediction_evaluation as evaluation
from dehps.optimization.prediction_evaluation import evaluate_prediction_snapshot


def _row(*, rank: int, numbers: tuple[int, ...], line_key: str = "static_100", as_of_issue: str = "2026068") -> dict:
    return {
        "line_key": line_key,
        "line_label": "100-period static training" if line_key == "static_100" else "Dynamic KDJ adjustment",
        "line_kind": "static" if line_key == "static_100" else "dynamic_kdj",
        "snapshot_key": f"snapshot-{line_key}",
        "run_id": "run-1",
        "source_round_index": 7,
        "as_of_issue": as_of_issue,
        "next_issue": "2026069",
        "prediction_metadata": {"fallback_static_base": False},
        "rank": rank,
        "red_numbers": list(numbers),
        "score": 1.0 / rank,
        "generated_at": "2026-06-18T10:00:00Z",
    }


def _actual() -> dict:
    return {
        "issue": "2026069",
        "draw_date": date(2026, 6, 18),
        "red_numbers": [1, 2, 3, 4, 5, 6],
        "blue_number": 9,
    }


def test_evaluate_prediction_snapshot_scores_exact_and_red5(monkeypatch):
    monkeypatch.setattr(
        evaluation,
        "load_prediction_rows",
        lambda *_args, **_kwargs: (
            [
                _row(rank=1, numbers=(1, 2, 3, 4, 5, 7)),
                _row(rank=2, numbers=(1, 2, 3, 4, 5, 6)),
            ],
            None,
        ),
    )
    monkeypatch.setattr(evaluation, "load_actual_draw", lambda *_args, **_kwargs: _actual())

    payload = evaluate_prediction_snapshot(
        object(),
        line_key="static_100",
        predicted_issue="2026069",
        write_report=False,
        persist=False,
    )

    assert payload["status"] == "evaluated"
    assert payload["exact_rank"] == 2
    assert payload["hit_top_100"] is True
    assert payload["red5_rank"] == 1
    assert payload["hit_red5_top_100"] is True
    assert payload["actual_blue_number"] == 9
    assert payload["summary"]["blue_scored"] is False


def test_evaluate_prediction_snapshot_reports_missing_snapshot(monkeypatch):
    monkeypatch.setattr(evaluation, "load_prediction_rows", lambda *_args, **_kwargs: ([], None))
    monkeypatch.setattr(evaluation, "load_actual_draw", lambda *_args, **_kwargs: _actual())

    payload = evaluate_prediction_snapshot(
        object(),
        line_key="dynamic_kdj",
        predicted_issue="2026069",
        write_report=False,
        persist=False,
    )

    assert payload["status"] == "missing_prediction_snapshot"
    assert payload["line_key"] == "dynamic_kdj"
    assert payload["actual_red_numbers"] == [1, 2, 3, 4, 5, 6]


def test_evaluate_prediction_snapshot_reports_snapshot_mismatch(monkeypatch):
    monkeypatch.setattr(evaluation, "load_prediction_rows", lambda *_args, **_kwargs: ([], "snapshot-current"))
    monkeypatch.setattr(evaluation, "load_actual_draw", lambda *_args, **_kwargs: _actual())

    payload = evaluate_prediction_snapshot(
        object(),
        line_key="static_100",
        predicted_issue="2026069",
        snapshot_key="snapshot-old",
        write_report=False,
        persist=False,
    )

    assert payload["status"] == "prediction_snapshot_mismatch"
    assert payload["summary"] == {"found_snapshot_key": "snapshot-current"}


def test_evaluate_prediction_snapshot_rejects_leaking_snapshot(monkeypatch):
    monkeypatch.setattr(
        evaluation,
        "load_prediction_rows",
        lambda *_args, **_kwargs: ([_row(rank=1, numbers=(1, 2, 3, 4, 5, 6), as_of_issue="2026069")], None),
    )
    monkeypatch.setattr(evaluation, "load_actual_draw", lambda *_args, **_kwargs: _actual())

    payload = evaluate_prediction_snapshot(
        object(),
        line_key="static_100",
        predicted_issue="2026069",
        write_report=False,
        persist=False,
    )

    assert payload["status"] == "leakage_guard_failed"
    assert payload["summary"]["leakage_passed"] is False
