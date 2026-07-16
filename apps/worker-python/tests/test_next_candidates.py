from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

import dehps.optimization.next_candidates as next_candidates
from dehps.optimization.next_candidates import (
    DYNAMIC_KDJ_LINE_KEY,
    NEAR_DYNAMIC_KDJ_EVAL_WINDOW,
    NEAR_DYNAMIC_KDJ_LINE_KEY,
    build_dynamic_kdj_next_candidate_snapshot,
    build_near_dynamic_kdj_next_candidate_snapshot,
    build_training_next_candidate_snapshot,
    dynamic_kdj_regression_summary,
    dynamic_kdj_config_for_next,
    dynamic_kdj_strength_sweep_training_summary,
    load_best_training_summary,
    next_issue_hint,
    refresh_training_prediction_lines_current,
    STATIC_100_LINE_KEY,
    training_freshness_metadata,
    training_summary_sort_key,
)


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def execute(self, sql, params=None):
        self.conn.queries.append((sql, params))
        return self

    def fetchone(self):
        return self.conn.row


class FakeConn:
    def __init__(self, row):
        self.row = row
        self.queries = []

    def cursor(self, row_factory=None):
        self.row_factory = row_factory
        return FakeCursor(self)


def test_next_issue_hint_increments_numeric_issue():
    assert next_issue_hint("2026068") == "2026069"
    assert next_issue_hint("bad") == ""


def test_load_best_training_summary_prefers_supervisor_best_checkpoint(monkeypatch):
    checkpoint_row = {
        "run_id": "run-1",
        "round_index": 9,
        "train_mode": "expanding",
        "train_window": 900,
        "eval_window": 100,
        "top_n": 10000,
        "as_of_issue": "2026073",
        "history_fingerprint": "history-current",
        "history_scope": "current_regime_default",
        "regime_years": 10,
        "regime_start_date": date(2016, 6, 28),
        "best_summary": {
            "config_hash": "checkpoint-best",
            "config": {"structural_weight": 0.7, "frequency_weight": 0.8, "omission_weight": 0.05},
            "top_100_hits": 3,
            "top_1000_hits": 3,
            "top_10000_hits": 3,
        },
        "best_config": {"frequency_weight": 0.1},
    }
    conn = FakeConn(checkpoint_row)
    monkeypatch.setattr(next_candidates, "ensure_training_supervisor_best_schema", lambda _conn: None)

    best = load_best_training_summary(conn)

    assert best is not None
    assert best["source_round_index"] == 9
    assert best["training_regime_start_date"] == "2016-06-28"
    assert best["summary"]["config_hash"] == "checkpoint-best"
    assert best["config"]["frequency_weight"] == 0.8
    assert len(conn.queries) == 1
    assert "FROM training_supervisor_best" in conn.queries[0][0]


def test_training_freshness_metadata_marks_stale_history():
    metadata = training_freshness_metadata(
        training_as_of_issue="2026067",
        latest_issue="2026069",
        training_history_fingerprint="history-old",
        current_history_fingerprint="history-current",
    )

    assert metadata == {
        "status": "stale",
        "training_issue_matches_current": False,
        "training_history_matches_current": False,
        "training_issue_lag": 2,
    }


def test_training_next_candidate_snapshot_rejects_nonpositive_top_n():
    with pytest.raises(ValueError, match="top_n must be at least 1"):
        build_training_next_candidate_snapshot(object(), top_n=0)


def test_training_next_candidate_snapshot_reports_training_freshness(monkeypatch):
    history = [
        ("2026067", None, (1, 2, 3, 4, 5, 6)),
        ("2026068", None, (2, 3, 4, 5, 6, 7)),
    ]
    best = {
        "run_id": "run-1",
        "source_round_index": 5,
        "train_mode": "expanding",
        "train_window": 900,
        "eval_window": 100,
        "top_n": 10000,
        "training_as_of_issue": "2026067",
        "training_history_fingerprint": "history-old",
        "summary": {
            "evaluated_draws": 100,
            "top_100_hits": 1,
            "top_1000_hits": 2,
            "top_10000_hits": 4,
            "red5": {"top_100_hits": 3, "top_1000_hits": 5, "top_10000_hits": 8},
        },
        "config": {},
    }
    monkeypatch.setattr(next_candidates, "load_best_training_summary", lambda _conn, _run_id: best)
    monkeypatch.setattr(next_candidates, "load_history_with_dates", lambda _conn: history)
    monkeypatch.setattr(next_candidates, "resolve_git_commit", lambda: "source-commit")
    monkeypatch.setattr(
        next_candidates,
        "top_candidates_for_next",
        lambda **_kwargs: [(1, (1, 2, 3, 4, 5, 6), 0.75)],
    )

    snapshot = build_training_next_candidate_snapshot(object(), top_n=10, ranked_universe=[object(), object()])

    metadata = snapshot["metadata"]
    assert metadata["line_key"] == STATIC_100_LINE_KEY
    assert metadata["prediction_metadata"]["protocol"] == "static_training_best"
    assert metadata["prediction_metadata"]["regression_100"]["top_100_hits"] == 1
    assert metadata["prediction_metadata"]["regression_100"]["top_1000_hits"] == 2
    assert metadata["prediction_metadata"]["regression_100"]["top_10000_hits"] == 4
    assert metadata["prediction_metadata"]["regression_100"]["red5"]["top_10000_hits"] == 8
    assert metadata["history_fingerprint"] == next_candidates.fingerprint_history(history)
    assert metadata["freshness_mode"] == "legacy_full_history"
    assert metadata["git_commit"] == "source-commit"
    assert metadata["scoring_contract"] == "dehps-scoring-strict-v1"
    assert metadata["ranking_contract"] == "strict_v1"
    assert metadata["training_freshness"] == {
        "status": "stale",
        "training_issue_matches_current": False,
        "training_history_matches_current": False,
        "training_issue_lag": 1,
    }


def test_dynamic_kdj_config_for_next_falls_back_to_static_when_signals_missing():
    base_config = next_candidates.FrequencyRankerConfig(frequency_weight=0.30)

    config, metadata = dynamic_kdj_config_for_next(
        base_config=base_config,
        signals=[],
        target_issue="2026069",
    )

    assert config.frequency_weight == 0.30
    assert metadata["fallback_static_base"] is True
    assert metadata["applied_offsets"] == {}
    assert metadata["leakage_passed"] is True


def test_dynamic_kdj_config_for_next_applies_only_prior_issue_signals():
    base_config = next_candidates.FrequencyRankerConfig(frequency_weight=0.30)

    config, metadata = dynamic_kdj_config_for_next(
        base_config=base_config,
        target_issue="2026069",
        signals=[
            {
                "issue": "2026067",
                "weight_name": "frequency_weight",
                "recommended_offset": 0.02,
                "j_value": 65.0,
                "objective_delta": 1.0,
            },
            {
                "issue": "2026069",
                "weight_name": "frequency_weight",
                "recommended_offset": 0.20,
                "j_value": 95.0,
                "objective_delta": 1.0,
            },
        ],
    )

    assert round(config.frequency_weight, 6) == 0.32
    assert metadata["fallback_static_base"] is False
    assert metadata["excluded_signal_count"] == 1
    assert metadata["applied_offsets"] == {"frequency_weight": 0.02}
    assert metadata["latest_signal_issue"] == "2026067"
    assert metadata["leakage_passed"] is True


def test_dynamic_kdj_config_for_next_scales_offsets():
    base_config = next_candidates.FrequencyRankerConfig(frequency_weight=0.30)

    config, metadata = dynamic_kdj_config_for_next(
        base_config=base_config,
        target_issue="2026069",
        offset_scale=0.5,
        signals=[
            {
                "issue": "2026067",
                "weight_name": "frequency_weight",
                "recommended_offset": 0.02,
                "j_value": 65.0,
                "objective_delta": 1.0,
            },
        ],
    )

    assert round(config.frequency_weight, 6) == 0.31
    assert metadata["thresholds"]["offset_scale"] == 0.5
    assert metadata["applied_offsets"] == {"frequency_weight": 0.01}


def test_dynamic_kdj_config_for_next_uses_kdj_state_strength_band():
    base_config = next_candidates.FrequencyRankerConfig(frequency_weight=0.30)
    strength_policy = next_candidates.dynamic_strength_policy_from_anchor(
        0.25,
        strength_values=(0.25, 0.5, 1.0),
    )

    config, metadata = dynamic_kdj_config_for_next(
        base_config=base_config,
        target_issue="2026069",
        offset_scale=0.25,
        strength_policy=strength_policy,
        signals=[
            {
                "issue": "2026067",
                "weight_name": "frequency_weight",
                "recommended_offset": 0.02,
                "j_value": 100.0,
                "objective_delta": 1.0,
                "base_value": 0.0,
                "close_value": 0.02,
                "rolling_low_value": 0.0,
                "rolling_high_value": 0.02,
            },
        ],
    )

    effective_scale = metadata["effective_offset_scale"]
    assert 0.25 < effective_scale <= 0.5
    assert metadata["strength_policy"]["mode"] == "kdj_state_band"
    assert metadata["strength_state"]["confidence"] > 0.5
    assert round(config.frequency_weight, 8) == round(0.30 - 0.02 * effective_scale, 8)
    assert metadata["applied_offsets"] == {"frequency_weight": round(-0.02 * effective_scale, 8)}


def test_dynamic_kdj_regression_summary_runs_per_target_without_future_signals(monkeypatch):
    history = [
        ("2026061", date(2026, 6, 1), (1, 2, 3, 4, 5, 6)),
        ("2026062", date(2026, 6, 3), (2, 3, 4, 5, 6, 7)),
        ("2026063", date(2026, 6, 5), (3, 4, 5, 6, 7, 8)),
        ("2026064", date(2026, 6, 7), (4, 5, 6, 7, 8, 9)),
    ]
    calls: list[str] = []

    def fake_rank_target_grid_with_red5(**kwargs):
        target = kwargs["target_numbers"]
        calls.append(str(target[0]))
        red5 = SimpleNamespace(rank=50 if target[0] == 3 else 1200)
        exact_rank = 80 if target[0] == 3 else 9000
        return [(exact_rank, 0.5, red5)]

    monkeypatch.setattr(next_candidates, "rank_target_grid_with_red5", fake_rank_target_grid_with_red5)

    summary = dynamic_kdj_regression_summary(
        history=history,
        base_config=next_candidates.FrequencyRankerConfig(frequency_weight=0.30),
        signals=[
            {
                "issue": "2026063",
                "weight_name": "frequency_weight",
                "recommended_offset": 0.02,
                "j_value": 65.0,
                "objective_delta": 1.0,
            },
            {
                "issue": "2026064",
                "weight_name": "frequency_weight",
                "recommended_offset": 0.20,
                "j_value": 95.0,
                "objective_delta": 1.0,
            },
        ],
        ranked_universe=[object()],
        train_mode="rolling",
        train_window=2,
        eval_window=2,
        top_n=10000,
    )

    assert calls == ["3", "4"]
    assert summary["status"] == "evaluated"
    assert summary["eval_window"] == 2
    assert summary["top_100_hits"] == 1
    assert summary["top_1000_hits"] == 1
    assert summary["top_10000_hits"] == 2
    assert summary["red5"]["top_100_hits"] == 1
    assert summary["red5"]["top_1000_hits"] == 1
    assert summary["red5"]["top_10000_hits"] == 2
    assert summary["changed_target_count"] == 1
    assert summary["fallback_target_count"] == 1
    assert summary["latest_signal_issue"] == "2026063"
    assert summary["leakage_passed"] is True
    assert summary["target_issues"] == ["2026063", "2026064"]
    assert summary["target_results"] == [
        {
            "issue": "2026063",
            "draw_date": "2026-06-05",
            "red_numbers": [3, 4, 5, 6, 7, 8],
            "rank": 80,
            "score": 0.5,
            "hit_top_100": True,
            "hit_top_1000": True,
            "hit_top_10000": True,
            "red5_rank": 50,
            "red5_score": None,
            "red5_numbers": [],
            "red5_missing_number": None,
            "red5_extra_number": None,
            "hit_red5_top_100": True,
            "hit_red5_top_1000": True,
            "hit_red5_top_10000": True,
        },
        {
            "issue": "2026064",
            "draw_date": "2026-06-07",
            "red_numbers": [4, 5, 6, 7, 8, 9],
            "rank": 9000,
            "score": 0.5,
            "hit_top_100": False,
            "hit_top_1000": False,
            "hit_top_10000": True,
            "red5_rank": 1200,
            "red5_score": None,
            "red5_numbers": [],
            "red5_missing_number": None,
            "red5_extra_number": None,
            "hit_red5_top_100": False,
            "hit_red5_top_1000": False,
            "hit_red5_top_10000": True,
        },
    ]


def test_near_dynamic_kdj_strength_sweep_uses_latest_nine_targets(monkeypatch):
    history = [
        (f"2026{i:03d}", date(2026, 1, min(i, 28)), (i, i + 1, i + 2, i + 3, i + 4, i + 5))
        for i in range(1, 112)
    ]
    seen_targets: list[str] = []

    def fake_rank_target_grid_with_red5(**kwargs):
        target_issue = history[next(index for index, draw in enumerate(history) if draw[2] == kwargs["target_numbers"])][0]
        seen_targets.append(target_issue)
        return [(90, 0.5, SimpleNamespace(rank=80)) for _config in kwargs["configs"]]

    monkeypatch.setattr(next_candidates, "rank_target_grid_with_red5", fake_rank_target_grid_with_red5)

    payload = dynamic_kdj_strength_sweep_training_summary(
        history=history,
        base_config=next_candidates.FrequencyRankerConfig(frequency_weight=0.30),
        signals=[
            {
                "issue": "2026099",
                "weight_name": "frequency_weight",
                "recommended_offset": 0.02,
                "j_value": 65.0,
                "objective_delta": 1.0,
            }
        ],
        ranked_universe=[object()],
        train_mode="expanding",
        train_window=100,
        eval_window=NEAR_DYNAMIC_KDJ_EVAL_WINDOW,
        top_n=10000,
        strength_values=(0.25, 0.5, 1.0),
        line_key=NEAR_DYNAMIC_KDJ_LINE_KEY,
    )

    assert payload["line_key"] == NEAR_DYNAMIC_KDJ_LINE_KEY
    assert payload["selected_summary"]["eval_window"] == 9
    assert payload["selected_summary"]["target_issues"] == [f"2026{i:03d}" for i in range(103, 112)]
    assert [target["issue"] for target in payload["selected_summary"]["target_results"]] == [
        f"2026{i:03d}" for i in range(103, 112)
    ]
    assert all(target["hit_top_100"] for target in payload["selected_summary"]["target_results"])
    assert sorted(set(seen_targets)) == [f"2026{i:03d}" for i in range(103, 112)]


def test_dynamic_kdj_strength_sweep_training_summary_selects_best_strength(monkeypatch):
    history = [
        ("2026061", date(2026, 6, 1), (1, 2, 3, 4, 5, 6)),
        ("2026062", date(2026, 6, 3), (2, 3, 4, 5, 6, 7)),
        ("2026063", date(2026, 6, 5), (3, 4, 5, 6, 7, 8)),
        ("2026064", date(2026, 6, 7), (4, 5, 6, 7, 8, 9)),
    ]

    def fake_rank_target_grid_with_red5(**kwargs):
        ranks = [1000, 500, 80, 9000]
        return [(rank, 0.5, SimpleNamespace(rank=rank + 10)) for rank in ranks[: len(kwargs["configs"])]]

    monkeypatch.setattr(next_candidates, "rank_target_grid_with_red5", fake_rank_target_grid_with_red5)

    payload = dynamic_kdj_strength_sweep_training_summary(
        history=history,
        base_config=next_candidates.FrequencyRankerConfig(frequency_weight=0.30),
        signals=[
            {
                "issue": "2026062",
                "weight_name": "frequency_weight",
                "recommended_offset": 0.02,
                "j_value": 65.0,
                "objective_delta": 1.0,
            },
        ],
        ranked_universe=[object()],
        train_mode="rolling",
        train_window=2,
        eval_window=2,
        top_n=10000,
        strength_values=(0.0, 0.25, 0.5, 1.0),
    )

    assert payload["status"] == "evaluated"
    assert payload["selected_strength"] == 1.0
    assert payload["selected_strength_policy"]["mode"] == "kdj_state_band"
    assert len(payload["rows"]) == 3
    assert {row["strength"] for row in payload["rows"]} == {0.25, 0.5, 1.0}
    assert all(row["fully_dynamic"] for row in payload["rows"])
    assert payload["selected_summary"]["top_100_hits"] == 2
    assert payload["selected_summary"]["red5"]["top_100_hits"] == 2
    assert payload["selected_summary"]["fallback_target_count"] == 0
    assert payload["selected_summary"]["changed_target_count"] == 2
    assert payload["selected_summary"]["strength_policy"]["mode"] == "kdj_state_band"
    assert payload["selected_summary"]["as_of_issue"] == "2026064"
    assert payload["selected_summary"]["history_fingerprint"] == next_candidates.fingerprint_history(history)
    assert [target["rank"] for target in payload["selected_summary"]["target_results"]] == [80, 80]
    assert [target["red5_rank"] for target in payload["selected_summary"]["target_results"]] == [90, 90]


def test_dynamic_kdj_strength_sweep_parallel_matches_serial(monkeypatch):
    history = [
        (f"20260{index}", date(2026, 6, index), tuple(range(index, index + 6)))
        for index in range(1, 9)
    ]

    def fake_rank_target_grid_with_red5(**kwargs):
        target_seed = int(kwargs["target_numbers"][0])
        return [
            (
                target_seed * 100 + config_index,
                float(target_seed) + config_index / 10,
                SimpleNamespace(rank=target_seed * 90 + config_index),
            )
            for config_index, _config in enumerate(kwargs["configs"], start=1)
        ]

    monkeypatch.setattr(next_candidates, "rank_target_grid_with_red5", fake_rank_target_grid_with_red5)
    common = {
        "history": history,
        "base_config": next_candidates.FrequencyRankerConfig(frequency_weight=0.30),
        "signals": [
            {
                "issue": "202604",
                "weight_name": "frequency_weight",
                "recommended_offset": 0.02,
                "j_value": 65.0,
                "objective_delta": 1.0,
            }
        ],
        "ranked_universe": [object()],
        "train_mode": "expanding",
        "train_window": 4,
        "eval_window": 4,
        "top_n": 10000,
        "strength_values": (0.25, 0.5, 1.0),
    }

    serial = dynamic_kdj_strength_sweep_training_summary(**common, workers=1)
    parallel = dynamic_kdj_strength_sweep_training_summary(**common, workers=3)

    assert serial["target_worker_count"] == 1
    assert parallel["target_worker_count"] == 3
    assert parallel["selected_strength"] == serial["selected_strength"]
    assert parallel["selected_summary"] == serial["selected_summary"]
    assert parallel["rows"] == serial["rows"]


def test_dynamic_kdj_next_candidate_snapshot_includes_regression_summary(monkeypatch):
    history = [
        ("2026061", date(2026, 6, 1), (1, 2, 3, 4, 5, 6)),
        ("2026062", date(2026, 6, 3), (2, 3, 4, 5, 6, 7)),
        ("2026063", date(2026, 6, 5), (3, 4, 5, 6, 7, 8)),
    ]
    best = {
        "run_id": "run-1",
        "source_round_index": 5,
        "train_mode": "rolling",
        "train_window": 2,
        "eval_window": 1,
        "top_n": 10000,
        "training_as_of_issue": "2026063",
        "training_history_fingerprint": next_candidates.fingerprint_history(history),
        "history_scope": "",
        "regime_years": 0,
        "training_regime_start_date": "",
        "summary": {},
        "config": {"frequency_weight": 0.3},
    }
    monkeypatch.setattr(next_candidates, "load_best_training_summary", lambda _conn, _run_id: best)
    monkeypatch.setattr(next_candidates, "load_history_with_dates", lambda _conn: history)
    monkeypatch.setattr(next_candidates, "resolve_git_commit", lambda: "source-commit")
    monkeypatch.setattr(
        next_candidates,
        "load_recent_training_weight_signals",
        lambda *_args, **_kwargs: [
            {
                "issue": "2026062",
                "weight_name": "frequency_weight",
                "recommended_offset": 0.02,
                "j_value": 65.0,
                "objective_delta": 1.0,
            }
        ],
    )
    monkeypatch.setattr(next_candidates, "rank_target_grid_with_red5", lambda **_kwargs: [(1234, 0.5, SimpleNamespace(rank=99))])
    monkeypatch.setattr(
        next_candidates,
        "top_candidates_for_next",
        lambda **_kwargs: [(1, (1, 2, 3, 4, 5, 6), 0.75)],
    )

    snapshot = build_dynamic_kdj_next_candidate_snapshot(object(), top_n=10, ranked_universe=[object(), object()])

    metadata = snapshot["metadata"]
    assert metadata["line_key"] == DYNAMIC_KDJ_LINE_KEY
    assert metadata["prediction_metadata"]["regression_100"]["top_1000_hits"] == 0
    assert metadata["prediction_metadata"]["regression_100"]["top_10000_hits"] == 1
    assert metadata["prediction_metadata"]["regression_100"]["red5"]["top_100_hits"] == 1
    assert metadata["prediction_metadata"]["regression_100"]["fallback_target_count"] == 0
    assert metadata["prediction_metadata"]["dynamic_policy"]["strength_mode"] == "kdj_state_band"
    assert metadata["prediction_metadata"]["fallback_static_base"] is False
    assert metadata["prediction_metadata"]["gauss_guardrail"]["regression_leakage_passed"] is True
    assert metadata["git_commit"] == "source-commit"
    assert metadata["scoring_contract"] == "dehps-scoring-strict-v1"
    assert metadata["ranking_contract"] == "strict_v1"


def test_near_dynamic_kdj_next_candidate_snapshot_marks_window(monkeypatch):
    history = [
        (f"2026{i:03d}", date(2026, 1, min(i, 28)), (i, i + 1, i + 2, i + 3, i + 4, i + 5))
        for i in range(1, 112)
    ]
    best = {
        "run_id": "run-1",
        "source_round_index": 5,
        "train_mode": "expanding",
        "train_window": 100,
        "eval_window": 100,
        "top_n": 10000,
        "training_as_of_issue": "2026111",
        "training_history_fingerprint": next_candidates.fingerprint_history(history),
        "history_scope": "",
        "regime_years": 0,
        "training_regime_start_date": "",
        "summary": {},
        "config": {"frequency_weight": 0.3},
    }
    monkeypatch.setattr(next_candidates, "load_best_training_summary", lambda _conn, _run_id: best)
    monkeypatch.setattr(next_candidates, "load_history_with_dates", lambda _conn: history)
    monkeypatch.setattr(
        next_candidates,
        "load_recent_training_weight_signals",
        lambda *_args, **_kwargs: [
            {
                "issue": "2026099",
                "weight_name": "frequency_weight",
                "recommended_offset": 0.02,
                "j_value": 65.0,
                "objective_delta": 1.0,
            }
        ],
    )
    regression_train_lengths: list[int] = []
    candidate_history_lengths: list[int] = []

    def fake_rank_target_grid_with_red5(**kwargs):
        regression_train_lengths.append(len(kwargs["train_history"]))
        return [(80, 0.5, SimpleNamespace(rank=90))]

    def fake_top_candidates_for_next(**kwargs):
        candidate_history_lengths.append(len(kwargs["history"]))
        return [(1, (1, 2, 3, 4, 5, 6), 0.75)]

    monkeypatch.setattr(next_candidates, "rank_target_grid_with_red5", fake_rank_target_grid_with_red5)
    monkeypatch.setattr(next_candidates, "top_candidates_for_next", fake_top_candidates_for_next)

    snapshot = build_near_dynamic_kdj_next_candidate_snapshot(
        object(),
        top_n=10,
        ranked_universe=[object(), object()],
        dynamic_policy={"sealed": True, "seal_reason": "test"},
        sealed=True,
    )

    metadata = snapshot["metadata"]
    near_window = metadata["prediction_metadata"]["near_window"]
    assert metadata["line_key"] == NEAR_DYNAMIC_KDJ_LINE_KEY
    assert metadata["line_kind"] == "dynamic_kdj_near"
    assert metadata["train_mode"] == "rolling"
    assert metadata["eval_window"] == 9
    assert metadata["prediction_metadata"]["regression"]["eval_window"] == 9
    assert metadata["prediction_metadata"]["regression_9"]["target_issues"] == [f"2026{i:03d}" for i in range(103, 112)]
    assert metadata["prediction_metadata"]["regression_9"]["train_mode"] == "rolling"
    assert metadata["prediction_metadata"]["regression_9"]["train_window"] == 100
    assert metadata["prediction_metadata"]["effective_train_mode"] == "rolling"
    assert metadata["prediction_metadata"]["signal_train_mode"] == "expanding"
    assert metadata["prediction_metadata"]["regression_9"]["changed_target_count"] == 9
    assert near_window["window_key"] == "2026103-2026111->2026112"
    assert near_window["train_mode"] == "rolling"
    assert near_window["train_window"] == 100
    assert near_window["primary_objective"] == "exact_red6_top100"
    assert near_window["primary_metric"] == "top_100_hits"
    assert near_window["hit_definition"] == "exact red6 rank <= 100"
    assert near_window["diagnostic_metrics"] == ["red5_rank", "red4_plus_top100"]
    assert near_window["sealed"] is False
    assert near_window["seal_reason"] is None
    assert regression_train_lengths == [100] * 9
    assert candidate_history_lengths == [100]


def test_refresh_training_prediction_lines_builds_both_snapshots_before_writes(monkeypatch):
    events: list[str] = []

    def fake_static_snapshot(*_args, **_kwargs):
        events.append("build_static")
        return {
            "metadata": {"line_key": STATIC_100_LINE_KEY},
            "candidates": [],
        }

    def fake_dynamic_snapshot(*_args, **_kwargs):
        assert "replace_static_100" not in events
        events.append("build_dynamic")
        return {
            "metadata": {"line_key": DYNAMIC_KDJ_LINE_KEY},
            "candidates": [],
        }

    def fake_replace(_conn, *, metadata, candidates):
        events.append(f"replace_{metadata['line_key']}")

    monkeypatch.setattr(next_candidates, "build_training_next_candidate_snapshot", fake_static_snapshot)
    monkeypatch.setattr(next_candidates, "build_dynamic_kdj_next_candidate_snapshot", fake_dynamic_snapshot)
    monkeypatch.setattr(next_candidates, "replace_training_next_candidates_current", fake_replace)

    result = refresh_training_prediction_lines_current(object(), ranked_universe=[object()])

    assert result["status"] == "ready"
    assert events == ["build_static", "build_dynamic", "replace_static_100", "replace_dynamic_kdj"]


def test_refresh_training_prediction_lines_writes_near_line_when_policy_exists(monkeypatch):
    events: list[str] = []

    def fake_static_snapshot(*_args, **_kwargs):
        events.append("build_static")
        return {"metadata": {"line_key": STATIC_100_LINE_KEY}, "candidates": []}

    def fake_dynamic_snapshot(*_args, **_kwargs):
        events.append("build_dynamic")
        return {"metadata": {"line_key": DYNAMIC_KDJ_LINE_KEY}, "candidates": []}

    def fake_near_snapshot(*_args, **kwargs):
        assert kwargs["sealed"] is False
        events.append("build_near")
        return {"metadata": {"line_key": NEAR_DYNAMIC_KDJ_LINE_KEY}, "candidates": []}

    def fake_replace(_conn, *, metadata, candidates):
        events.append(f"replace_{metadata['line_key']}")

    monkeypatch.setattr(next_candidates, "build_training_next_candidate_snapshot", fake_static_snapshot)
    monkeypatch.setattr(next_candidates, "build_dynamic_kdj_next_candidate_snapshot", fake_dynamic_snapshot)
    monkeypatch.setattr(next_candidates, "build_near_dynamic_kdj_next_candidate_snapshot", fake_near_snapshot)
    monkeypatch.setattr(next_candidates, "replace_training_next_candidates_current", fake_replace)

    result = refresh_training_prediction_lines_current(
        object(),
        ranked_universe=[object()],
        near_dynamic_policy={"policy_key": "near"},
        near_dynamic_sealed=True,
    )

    assert result["status"] == "ready"
    assert set(result["lines"]) == {STATIC_100_LINE_KEY, DYNAMIC_KDJ_LINE_KEY, NEAR_DYNAMIC_KDJ_LINE_KEY}
    assert events == [
        "build_static",
        "build_dynamic",
        "build_near",
        "replace_static_100",
        "replace_dynamic_kdj",
        "replace_dynamic_kdj_near",
    ]


def test_refresh_training_prediction_lines_writes_fixed_forward_challenger(monkeypatch):
    events: list[str] = []
    static_metadata = {
        "line_key": STATIC_100_LINE_KEY,
        "next_issue": "2026081",
        "config_hash": "incumbent",
    }

    monkeypatch.setattr(
        next_candidates,
        "build_training_next_candidate_snapshot",
        lambda *_args, **_kwargs: {"metadata": static_metadata, "candidates": []},
    )
    monkeypatch.setattr(
        next_candidates,
        "build_dynamic_kdj_next_candidate_snapshot",
        lambda *_args, **_kwargs: {"metadata": {"line_key": DYNAMIC_KDJ_LINE_KEY}, "candidates": []},
    )
    monkeypatch.setattr(
        next_candidates,
        "ensure_active_forward_promotion_cohort",
        lambda *_args, **_kwargs: {"cohort_key": "cohort-1"},
    )
    monkeypatch.setattr(
        next_candidates,
        "build_forward_challenger_next_candidate_snapshot",
        lambda *_args, **_kwargs: {
            "metadata": {"line_key": "forward_challenger"},
            "candidates": [],
        },
    )
    monkeypatch.setattr(
        next_candidates,
        "replace_training_next_candidates_current",
        lambda _conn, *, metadata, candidates: events.append(metadata["line_key"]),
    )

    result = refresh_training_prediction_lines_current(object(), ranked_universe=[object()])

    assert "forward_challenger" in result["lines"]
    assert events == ["static_100", "dynamic_kdj", "forward_challenger"]


def test_training_next_candidate_snapshot_uses_training_regime_for_freshness(monkeypatch):
    history = [
        ("2026067", date(2026, 6, 20), (1, 2, 3, 4, 5, 6)),
        ("2026068", date(2026, 6, 22), (2, 3, 4, 5, 6, 7)),
    ]
    best = {
        "run_id": "run-1",
        "source_round_index": 5,
        "train_mode": "expanding",
        "train_window": 900,
        "eval_window": 100,
        "top_n": 10000,
        "training_as_of_issue": "2026068",
        "training_history_fingerprint": next_candidates.fingerprint_history(history),
        "history_scope": "current_regime_default",
        "regime_years": 10,
        "training_regime_start_date": "2016-06-22",
        "summary": {},
        "config": {},
    }
    seen = {}
    selection = SimpleNamespace(
        dated_history=history,
        scope="current_regime_default",
        regime_years=10,
        start_date=date(2016, 6, 22),
    )
    monkeypatch.setattr(next_candidates, "load_best_training_summary", lambda _conn, _run_id: best)
    monkeypatch.setattr(next_candidates, "select_history", lambda *_args, **_kwargs: selection)

    def fake_top_candidates_for_next(**kwargs):
        seen["history"] = kwargs["history"]
        return [(1, (1, 2, 3, 4, 5, 6), 0.75)]

    monkeypatch.setattr(next_candidates, "top_candidates_for_next", fake_top_candidates_for_next)

    snapshot = build_training_next_candidate_snapshot(object(), top_n=10, ranked_universe=[object(), object()])

    metadata = snapshot["metadata"]
    assert seen["history"] == history
    assert metadata["freshness_mode"] == "training_scope"
    assert metadata["history_scope"] == "current_regime_default"
    assert metadata["regime_start_date"] == "2016-06-22"
    assert metadata["training_freshness"] == {
        "status": "current",
        "training_issue_matches_current": True,
        "training_history_matches_current": True,
        "training_issue_lag": 0,
    }


def test_training_next_candidate_snapshot_marks_regime_fingerprint_mismatch_stale(monkeypatch):
    history = [
        ("2026068", date(2026, 6, 22), (2, 3, 4, 5, 6, 7)),
    ]
    best = {
        "run_id": "run-1",
        "source_round_index": 5,
        "train_mode": "expanding",
        "train_window": 900,
        "eval_window": 100,
        "top_n": 10000,
        "training_as_of_issue": "2026068",
        "training_history_fingerprint": "old-regime-fingerprint",
        "history_scope": "current_regime_default",
        "regime_years": 10,
        "summary": {},
        "config": {},
    }
    selection = SimpleNamespace(
        dated_history=history,
        scope="current_regime_default",
        regime_years=10,
        start_date=date(2016, 6, 22),
    )
    monkeypatch.setattr(next_candidates, "load_best_training_summary", lambda _conn, _run_id: best)
    monkeypatch.setattr(next_candidates, "select_history", lambda *_args, **_kwargs: selection)
    monkeypatch.setattr(
        next_candidates,
        "top_candidates_for_next",
        lambda **_kwargs: [(1, (1, 2, 3, 4, 5, 6), 0.75)],
    )

    snapshot = build_training_next_candidate_snapshot(object(), top_n=10, ranked_universe=[object(), object()])

    assert snapshot["metadata"]["training_freshness"] == {
        "status": "stale",
        "training_issue_matches_current": True,
        "training_history_matches_current": False,
        "training_issue_lag": 0,
    }


def test_training_summary_sort_key_prefers_historical_hits_before_reward():
    stronger_hits = {
        "top_100_hits": 0,
        "top_1000_hits": 1,
        "top_10000_hits": 3,
        "reward": {"objectiveScore": 1},
        "rank_quality": {},
        "red5": {},
    }
    stronger_reward = {
        "top_100_hits": 0,
        "top_1000_hits": 0,
        "top_10000_hits": 3,
        "reward": {"objectiveScore": 99},
        "rank_quality": {},
        "red5": {},
    }

    assert training_summary_sort_key(stronger_hits) > training_summary_sort_key(stronger_reward)


def test_training_summary_sort_key_prefers_unique_baseline_hits_with_same_top10000():
    unique_hits = {
        "top_100_hits": 0,
        "top_1000_hits": 0,
        "top_10000_hits": 3,
        "reward": {"objectiveScore": 12},
        "rank_quality": {},
        "red5": {},
        "baseline_overlap": {
            "bands": {
                "top_1000": {"unique_hit_count": 0},
                "top_10000": {"unique_hit_count": 3, "overlap_hit_count": 0},
            }
        },
    }
    overlapped_hits = {
        **unique_hits,
        "reward": {"objectiveScore": 3},
        "baseline_overlap": {
            "bands": {
                "top_1000": {"unique_hit_count": 0},
                "top_10000": {"unique_hit_count": 0, "overlap_hit_count": 3},
            }
        },
    }

    assert training_summary_sort_key(unique_hits) > training_summary_sort_key(overlapped_hits)
