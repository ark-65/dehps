from __future__ import annotations

from scripts.generate_training_diagnostics import render_diagnostics_report, summarize_training_rounds


def test_summarize_training_rounds_reports_stagnation_and_weight_coverage():
    rows = [
        {
            "run_id": "run-1",
            "round_index": 1,
            "phase": "micro",
            "improved": True,
            "top_100_hits": 1,
            "top_1000_hits": 2,
            "top_10000_hits": 3,
            "red5_top_100_hits": 2,
            "red5_top_1000_hits": 4,
            "red5_top_10000_hits": 8,
            "best_config": {"frequency_weight": 0.4},
            "best_summary": {"frozen_validation": {"reward": {"objectiveScore": 1.5}}},
            "top_results": [{"config": {"tail_distribution_weight": 0.1}}],
            "target_results": [{"issue": "2026001", "rank": 950000}],
            "prefilter": {},
        },
        {
            "run_id": "run-1",
            "round_index": 2,
            "phase": "small",
            "improved": False,
            "top_100_hits": 1,
            "top_1000_hits": 2,
            "top_10000_hits": 3,
            "red5_top_100_hits": 2,
            "red5_top_1000_hits": 4,
            "red5_top_10000_hits": 9,
            "best_config": {"frequency_weight": 0.4, "weekday_trend_weight": 0.05},
            "best_summary": {"frozen_validation": {"reward": {"objectiveScore": 2.5}}},
            "top_results": [],
            "target_results": [{"issue": "2026001", "rank": 910000}],
            "prefilter": {
                "control_experiments": [
                    {
                        "label": "structural_baseline",
                        "top_10000_hits": 1,
                        "median_rank": 50000,
                        "objective_score": 2.0,
                        "frozen_validation": {"reward": {"objectiveScore": 1.0}},
                    }
                ]
            },
        },
    ]

    summary = summarize_training_rounds(rows)

    assert summary["run_id"] == "run-1"
    assert summary["stagnation_rounds"] == 1
    assert summary["phase_improvement_rates"]["micro"] == 1
    assert summary["phase_improvement_rates"]["small"] == 0
    assert summary["tail_target_issues"] == [{"issue": "2026001", "tail_count": 2}]
    assert {"field": "frequency_weight", "count": 2} in summary["most_covered_weights"]
    assert summary["latest_red5_hits"]["top_10000"] == 9
    assert summary["validation_objective_avg"] == 2.0
    assert summary["latest_control_experiments"][0]["label"] == "structural_baseline"

    report = render_diagnostics_report(summary)
    assert "DEHPS Training Diagnostics" in report
    assert "Latest Control Experiments" in report
    assert "structural_baseline" in report
    assert "historical walk-forward search behavior" in report
