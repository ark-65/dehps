from __future__ import annotations

import pytest

from dehps.training.cli import build_settings, parse_args
from dehps.training.production_runtime import (
    build_production_training_session,
    ranked_universe_size_status,
)


def test_legacy_supervisor_command_remains_cli_compatible() -> None:
    args = parse_args(
        [
            "--duration-hours",
            "24",
            "--train-mode",
            "expanding",
            "--train-window",
            "900",
            "--eval-window",
            "100",
            "--top-n",
            "10000",
            "--as-of-issue",
            "2026067",
            "--workers",
            "16",
            "--progress-interval",
            "10",
            "--max-configs-per-round",
            "20",
            "--max-rounds",
            "1",
            "--frozen-plateau-patience",
            "40",
            "--observability-only",
            "--memory-budget-gb",
            "20",
        ]
    )

    settings = build_settings(args)

    assert settings.run_arguments["duration_hours"] == 24
    assert settings.run_arguments["train_mode"] == "expanding"
    assert settings.run_arguments["train_window"] == 900
    assert settings.run_arguments["eval_window"] == 100
    assert settings.run_arguments["top_n"] == 10_000
    assert settings.run_arguments["as_of_issue"] == "2026067"
    assert settings.run_arguments["workers"] == 16
    assert settings.run_arguments["progress_interval"] == 10
    assert settings.run_arguments["max_configs_per_round"] == 20
    assert settings.run_arguments["max_rounds"] == 1
    assert settings.run_arguments["frozen_plateau_patience"] == 40
    assert settings.run_arguments["observability_only"] is True
    assert settings.run_arguments["memory_budget_gb"] == 20


def test_observability_only_requires_a_bounded_round_count(tmp_path) -> None:
    with pytest.raises(
        ValueError,
        match="observability-only mode requires --max-rounds >= 1",
    ):
        build_production_training_session(
            duration_hours=0,
            train_window=900,
            eval_window=100,
            top_n=10000,
            as_of_issue=None,
            workers=1,
            train_mode="expanding",
            history_scope="current_regime_default",
            regime_years=10,
            output_dir=tmp_path,
            progress_interval=10,
            max_configs_per_round=28,
            memory_budget_gb=20,
            max_rounds=None,
            observability_only=True,
        )


def test_ranked_universe_size_status_does_not_require_materialized_legal_universe() -> None:
    status = ranked_universe_size_status(range(1_105_506))

    assert status == {
        "legal_universe_size": 1_107_568,
        "ranked_universe_size": 1_105_506,
        "excluded_universe_count": 2_062,
        "universe_size": 1_105_506,
    }
