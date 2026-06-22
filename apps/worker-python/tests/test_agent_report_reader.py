import pytest

from dehps.agents.report_reader import parse_experiment_report
from dehps.backtest.report import render_experiment_report


def test_experiment_report_round_trips_agent_required_fields():
    report = render_experiment_report(
        "baseline_v1-test",
        "baseline_v1",
        {
            "total_combinations": 1107568,
            "kept_combinations": 1073093,
            "keep_rate": 0.96887324,
            "history_draws": 2,
            "covered_draws": 1,
            "coverage_rate": 0.5,
            "lift": 0.51606338,
            "missed_issues": ["2026001"],
        },
        {"min_score": 0.45, "max_anomaly_penalty": 0.7},
    )

    summary = parse_experiment_report(report)

    assert summary.experiment_key == "baseline_v1-test"
    assert summary.strategy_key == "baseline_v1"
    assert summary.metrics["total_combinations"] == 1107568
    assert summary.metrics["coverage_rate"] == 0.5
    assert summary.missed_issues == ["2026001"]
    assert summary.config_snapshot == {"min_score": 0.45, "max_anomaly_penalty": 0.7}


def test_experiment_report_reader_ignores_none_missed_issue():
    report = render_experiment_report(
        "baseline_v1-clean",
        "baseline_v1",
        {
            "total_combinations": 1107568,
            "kept_combinations": 1073093,
            "keep_rate": 0.96887324,
            "history_draws": 1,
            "covered_draws": 1,
            "coverage_rate": 1.0,
            "lift": 1.03212676,
            "missed_issues": [],
        },
    )

    summary = parse_experiment_report(report)

    assert summary.missed_issues == []


def test_experiment_report_reader_rejects_malformed_metric_bullet():
    report = "\n".join(
        [
            "# Experiment Report",
            "- Experiment: `baseline_v1-test`",
            "- Strategy: `baseline_v1`",
            "## Metrics",
            "- coverage_rate",
        ]
    )

    with pytest.raises(ValueError, match="expected '- key: value' bullet"):
        parse_experiment_report(report)


def test_experiment_report_reader_rejects_boolean_metric_value():
    report = "\n".join(
        [
            "# Experiment Report",
            "- Experiment: `baseline_v1-test`",
            "- Strategy: `baseline_v1`",
            "## Metrics",
            "- coverage_rate: True",
        ]
    )

    with pytest.raises(ValueError, match="expected numeric metric"):
        parse_experiment_report(report)
