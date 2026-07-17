from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import dehps.optimization.ranking_audit as audit
import pytest


def _draw(issue: str, number: int) -> tuple[str, date, tuple[int, ...]]:
    return issue, date(2026, 1, number), (1, 2, 3, 4, 5, number + 5)


def test_legacy_current_regime_history_requires_exact_stored_digest(monkeypatch) -> None:
    full_history = [_draw("2026001", 1), _draw("2026002", 2), _draw("2026003", 3)]
    regime_history = full_history[-2:]
    monkeypatch.setattr(audit, "load_history_until_with_dates", lambda *_args: full_history)
    monkeypatch.setattr(
        audit,
        "select_history",
        lambda *_args, **_kwargs: SimpleNamespace(dated_history=regime_history),
    )
    run = {
        "prediction_run_key": "legacy-run",
        "as_of_issue": "2026003",
        "train_mode": "rolling",
        "train_window": 1,
        "metadata": {"history_fingerprint": audit.fingerprint_history(regime_history)},
    }

    replay = audit.resolve_training_history_for_prediction_run(object(), run)

    assert replay.base_history == regime_history
    assert replay.history == regime_history[-1:]
    assert replay.resolution == "legacy:current_regime_default:10y:exact_digest"
    assert replay.replay_fingerprint == replay.stored_fingerprint


def test_legacy_history_mismatch_is_rejected_instead_of_guessed(monkeypatch) -> None:
    full_history = [_draw("2026001", 1), _draw("2026002", 2)]
    monkeypatch.setattr(audit, "load_history_until_with_dates", lambda *_args: full_history)
    monkeypatch.setattr(
        audit,
        "select_history",
        lambda *_args, **_kwargs: SimpleNamespace(dated_history=full_history[-1:]),
    )

    with pytest.raises(audit.PredictionHistoryReplayError) as exc_info:
        audit.resolve_training_history_for_prediction_run(
            object(),
            {
                "prediction_run_key": "unreplayable-run",
                "as_of_issue": "2026002",
                "metadata": {"history_fingerprint": "0" * 64},
            },
        )

    assert exc_info.value.code == "prediction_history_fingerprint_mismatch"
    assert exc_info.value.context["prediction_run_key"] == "unreplayable-run"


def test_actual_ranking_audit_tracks_each_existing_stage_without_mutating_candidates(monkeypatch) -> None:
    candidates = [
        {"rank": 1, "red_numbers": [4, 5, 11, 19, 27, 32], "score": 0.9},
        {"rank": 2, "red_numbers": [1, 2, 3, 7, 8, 9], "score": 0.8},
    ]
    before = [dict(row) for row in candidates]
    monkeypatch.setattr(audit, "build_ranked_universe", lambda: object())
    monkeypatch.setattr(audit, "training_history_for_prediction_run", lambda *_args: [])
    monkeypatch.setattr(audit, "rank_target_structural", lambda **_kwargs: (900, 0.2))
    monkeypatch.setattr(audit, "rank_target", lambda **_kwargs: (1, 0.9))

    result = audit.build_actual_ranking_audit(
        object(),
        prediction_run={
            "prediction_run_key": "run-1",
            "line_key": "static_100",
            "snapshot_key": "snapshot-1",
            "target_issue": "2026080",
            "train_mode": "expanding",
            "train_window": 900,
            "top_n": 2,
            "config": {},
        },
        actual_draw={"issue": "2026080", "red_numbers": [4, 5, 11, 19, 27, 32]},
        candidates=candidates,
    )

    assert result["generated"] is True
    assert result["passed_hard_filters"] is True
    assert result["initial_score_rank"] == 900
    assert result["model_score_rank"] == 1
    assert result["rerank_applied"] is False
    assert result["rerank_rank"] == 1
    assert result["final_export_rank"] == 1
    assert result["elimination_reason"] is None
    assert candidates == before


def test_actual_ranking_audit_identifies_hard_filter_elimination() -> None:
    result = audit.build_actual_ranking_audit(
        object(),
        prediction_run={"line_key": "static_100", "target_issue": "2026080"},
        actual_draw={"issue": "2026080", "red_numbers": [1, 2, 3, 4, 5, 9]},
        candidates=[],
    )

    assert result["generated"] is True
    assert result["passed_hard_filters"] is False
    assert result["eliminated_stage"] == "hard_filter"
    assert result["elimination_reason"] == "max_consecutive_run_at_least_5"
