from __future__ import annotations

import dehps.optimization.ranking_audit as audit


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
