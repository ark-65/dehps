from dehps.backtest.coverage import run_baseline_backtest


def test_backtest_returns_metrics():
    metrics = run_baseline_backtest([("2026001", (1, 6, 10, 17, 22, 30))])
    assert metrics["total_combinations"] == 1107568
    assert 0 <= metrics["keep_rate"] <= 1
    assert 0 <= metrics["coverage_rate"] <= 1


def test_backtest_missed_issues_are_record_level_not_issue_set():
    metrics = run_baseline_backtest(
        [
            ("2026001", (1, 6, 10, 17, 22, 30)),
            ("2026001", (1, 2, 3, 4, 5, 6)),
        ]
    )

    assert metrics["covered_issues"] == ["2026001"]
    assert metrics["missed_issues"] == ["2026001"]
