from __future__ import annotations

from dehps.training.cli import build_settings, parse_args


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
    assert settings.run_arguments["memory_budget_gb"] == 20
