from __future__ import annotations

import pytest

from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.weight_kdj import WeightKdjSignal, WeightKdjState
import scripts.generate_weight_kdj_signals as kdj_script
from scripts.generate_weight_kdj_signals import (
    CANONICAL_SIGNAL_RUN_ID,
    eligible_target_indexes,
    generate_signals,
    parse_weights,
    probe_configs,
    selected_recent_eligible_target_indexes,
)


def test_parse_weights_defaults_to_all_fields_and_rejects_unknown():
    fields = parse_weights(None)

    assert "frequency_weight" in fields
    assert "weekday_trend_weight" in fields
    with pytest.raises(ValueError, match="unknown weight fields"):
        parse_weights("frequency_weight,not_a_weight")


def test_probe_configs_deduplicates_clamped_values():
    configs = probe_configs(
        FrequencyRankerConfig(frequency_weight=0.0),
        weight_name="frequency_weight",
        step=0.03,
    )

    values = [config.frequency_weight for config in configs]
    assert values == sorted(set(values))
    assert values[0] == 0.0
    assert values[-1] == 0.06


def toy_history(count: int):
    return [(f"{index:04d}", None, (1, 2, 3, 4, 5, 6)) for index in range(count)]


class FakeConn:
    def __init__(self):
        self.commits = 0
        self.upserts = []

    def commit(self):
        self.commits += 1


class FakeContext:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        return False


def fake_signal(issue: str, weight_name: str = "frequency_weight") -> tuple[WeightKdjSignal, WeightKdjState]:
    signal = WeightKdjSignal(
        signal_run_id=CANONICAL_SIGNAL_RUN_ID,
        issue=issue,
        draw_date=None,
        weight_name=weight_name,
        train_mode="expanding",
        train_window=3,
        eval_window=1,
        top_n=100,
        history_fingerprint="fp",
        source="weight_response_probe_v0",
        base_value=0.3,
        close_value=0.33,
        issue_low_value=0.27,
        issue_high_value=0.36,
        rolling_low_value=0.27,
        rolling_high_value=0.36,
        rsv=66.666667,
        k_value=55.555556,
        d_value=51.851852,
        j_value=62.962963,
        recommended_offset=0.003333,
        best_objective_score=10,
        objective_delta=1,
        sample_count=3,
        probe_results=[],
        advisor_metadata={"mode": "kdj_response_interval"},
    )
    return signal, WeightKdjState(rsv=signal.rsv, k_value=signal.k_value, d_value=signal.d_value, j_value=signal.j_value)


def patch_common_generation(monkeypatch, conn: FakeConn, history):
    monkeypatch.setattr(kdj_script, "get_connection", lambda: FakeContext(conn))
    monkeypatch.setattr(kdj_script, "ensure_training_weight_signals_schema", lambda _conn: None)
    monkeypatch.setattr(kdj_script, "load_history_until_with_dates", lambda _conn, _as_of_issue: history)
    monkeypatch.setattr(kdj_script, "load_red_combination_universe", lambda _conn: [(1, 2, 3, 4, 5, 6)])
    monkeypatch.setattr(kdj_script, "build_ranked_universe", lambda universe: universe)
    monkeypatch.setattr(kdj_script, "fingerprint_history", lambda _history: "fp")
    monkeypatch.setattr(kdj_script, "prune_stale_training_weight_signals", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(kdj_script, "upsert_training_weight_signal", lambda _conn, signal: conn.upserts.append(signal))


def test_eligible_selection_starts_after_train_window_and_uses_recent_issues():
    assert list(eligible_target_indexes(history_len=6, train_window=3)) == [3, 4, 5]
    assert list(selected_recent_eligible_target_indexes(history_len=8, train_window=3, issues=2, allow_partial=False)) == [6, 7]

    with pytest.raises(ValueError, match="not enough eligible issues"):
        selected_recent_eligible_target_indexes(history_len=5, train_window=3, issues=3, allow_partial=False)

    assert list(selected_recent_eligible_target_indexes(history_len=5, train_window=3, issues=3, allow_partial=True)) == [3, 4]


def test_full_mode_requires_allow_partial_for_short_history(monkeypatch):
    conn = FakeConn()
    patch_common_generation(monkeypatch, conn, toy_history(5))

    with pytest.raises(ValueError, match="not enough eligible issues"):
        generate_signals(
            signal_run_id=CANONICAL_SIGNAL_RUN_ID,
            mode="full",
            as_of_issue=None,
            issues=3,
            allow_partial=False,
            train_mode="expanding",
            train_window=3,
            top_n=100,
            weights=("frequency_weight",),
            primary_step=0.03,
            context_step=0.01,
            kdj_window=3,
            chunk_size=2,
            base_config=FrequencyRankerConfig(),
            dry_run=True,
        )


def test_full_mode_allow_partial_generates_available_eligible_issue(monkeypatch):
    conn = FakeConn()
    history = toy_history(4)
    patch_common_generation(monkeypatch, conn, history)
    monkeypatch.setattr(
        kdj_script,
        "build_weight_signal",
        lambda **kwargs: fake_signal(kdj_script.history_issue(kwargs["target_draw"]), kwargs["weight_name"]),
    )

    summary = generate_signals(
        signal_run_id=CANONICAL_SIGNAL_RUN_ID,
        mode="full",
        as_of_issue=None,
        issues=2,
        allow_partial=True,
        train_mode="expanding",
        train_window=3,
        top_n=100,
        weights=("frequency_weight",),
        primary_step=0.03,
        context_step=0.01,
        kdj_window=3,
        chunk_size=2,
        base_config=FrequencyRankerConfig(),
        dry_run=True,
    )

    assert summary["status"] == "generated"
    assert summary["eligible_issues"] == 1
    assert summary["issues"] == 1
    assert summary["signals"] == 1


def test_incremental_reports_seed_missing_without_loading_universe(monkeypatch):
    conn = FakeConn()
    patch_common_generation(monkeypatch, conn, toy_history(5))
    monkeypatch.setattr(kdj_script, "has_training_weight_signal_run", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        kdj_script,
        "load_red_combination_universe",
        lambda _conn: (_ for _ in ()).throw(AssertionError("universe should not load without a seed")),
    )

    summary = generate_signals(
        signal_run_id=CANONICAL_SIGNAL_RUN_ID,
        mode="incremental",
        as_of_issue=None,
        issues=2,
        allow_partial=False,
        train_mode="expanding",
        train_window=3,
        top_n=100,
        weights=("frequency_weight",),
        primary_step=0.03,
        context_step=0.01,
        kdj_window=3,
        chunk_size=2,
        base_config=FrequencyRankerConfig(),
        dry_run=True,
    )

    assert summary["status"] == "seed_missing"
    assert summary["signals"] == 0


def test_incremental_noop_does_not_load_universe(monkeypatch):
    conn = FakeConn()
    history = toy_history(5)
    patch_common_generation(monkeypatch, conn, history)
    monkeypatch.setattr(kdj_script, "has_training_weight_signal_run", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        kdj_script,
        "load_training_weight_signal_coverage",
        lambda _conn, **_kwargs: {"0003": {"frequency_weight"}, "0004": {"frequency_weight"}},
    )
    monkeypatch.setattr(
        kdj_script,
        "load_red_combination_universe",
        lambda _conn: (_ for _ in ()).throw(AssertionError("universe should not load for noop")),
    )

    summary = generate_signals(
        signal_run_id=CANONICAL_SIGNAL_RUN_ID,
        mode="incremental",
        as_of_issue=None,
        issues=2,
        allow_partial=False,
        train_mode="expanding",
        train_window=3,
        top_n=100,
        weights=("frequency_weight",),
        primary_step=0.03,
        context_step=0.01,
        kdj_window=3,
        chunk_size=2,
        base_config=FrequencyRankerConfig(),
        dry_run=True,
    )

    assert summary["status"] == "noop"
    assert summary["signals"] == 0


def test_incremental_generates_only_missing_issue_weight_rows_in_order(monkeypatch):
    conn = FakeConn()
    history = toy_history(5)
    generated = []
    patch_common_generation(monkeypatch, conn, history)
    monkeypatch.setattr(kdj_script, "has_training_weight_signal_run", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        kdj_script,
        "load_training_weight_signal_coverage",
        lambda _conn, **_kwargs: {"0003": {"frequency_weight"}},
    )
    monkeypatch.setattr(
        kdj_script,
        "load_training_weight_signal_rows",
        lambda _conn, **_kwargs: [
            {
                "issue": "0003",
                "weight_name": "frequency_weight",
                "issue_low_value": 0.27,
                "issue_high_value": 0.36,
                "rsv": 50,
                "k_value": 50,
                "d_value": 50,
                "j_value": 50,
            }
        ],
    )
    monkeypatch.setattr(kdj_script, "load_training_weight_signal_tail", lambda *_args, **_kwargs: [])

    def build_fake(**kwargs):
        issue = kdj_script.history_issue(kwargs["target_draw"])
        generated.append((issue, kwargs["weight_name"]))
        return fake_signal(issue, kwargs["weight_name"])

    monkeypatch.setattr(kdj_script, "build_weight_signal", build_fake)

    summary = generate_signals(
        signal_run_id=CANONICAL_SIGNAL_RUN_ID,
        mode="incremental",
        as_of_issue=None,
        issues=2,
        allow_partial=False,
        train_mode="expanding",
        train_window=3,
        top_n=100,
        weights=("frequency_weight",),
        primary_step=0.03,
        context_step=0.01,
        kdj_window=3,
        chunk_size=1,
        base_config=FrequencyRankerConfig(),
        dry_run=False,
    )

    assert generated == [("0004", "frequency_weight")]
    assert [signal["issue"] for signal in conn.upserts] == ["0004"]
    assert summary["status"] == "generated"
    assert summary["signals"] == 1
