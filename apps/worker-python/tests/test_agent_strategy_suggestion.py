import pytest
from pydantic import ValidationError

from dehps.agents.strategy_suggestion import StrategySuggestion


def test_strategy_suggestion_builds_versioned_advisory_key():
    suggestion = StrategySuggestion(
        proposal_key="naturalness_tighten",
        base_strategy_key="baseline",
        proposed_version="v2",
        hypothesis=(
            "Combinations with moderate structural naturalness and lower anomaly penalties "
            "should preserve coverage while reducing the retained sample space."
        ),
        rationale="This tests a transparent compression rule, not a probability edge.",
        baseline="baseline_v1",
        expected_keep_rate_min=0.75,
        expected_keep_rate_max=0.95,
        expected_coverage_rate_min=0.90,
        failure_conditions=[
            "Reject if coverage_rate drops below 0.90 on the frozen history window.",
            "Reject if missed issues cluster around one import source or parser period.",
        ],
        config_snapshot={"min_score": 0.5, "max_anomaly_penalty": 0.6},
    )

    assert suggestion.strategy_key == "baseline_v2"
    assert suggestion.advisory_only is True
    assert "not a prediction" in suggestion.to_review_markdown()


def test_strategy_suggestion_rejects_non_advisory_output():
    with pytest.raises(ValidationError, match="advisory"):
        StrategySuggestion(
            proposal_key="unsafe_auto",
            base_strategy_key="baseline",
            proposed_version="v3",
            hypothesis="This long enough hypothesis tries to skip review and enter production directly.",
            rationale="The rationale is long enough but intentionally unsafe.",
            baseline="baseline_v1",
            expected_keep_rate_min=0.7,
            expected_keep_rate_max=0.9,
            expected_coverage_rate_min=0.85,
            failure_conditions=["Reject if coverage_rate drops below 0.85."],
            advisory_only=False,
        )


def test_strategy_suggestion_rejects_inverted_keep_rate_range():
    with pytest.raises(ValidationError, match="expected_keep_rate_min"):
        StrategySuggestion(
            proposal_key="bad_range",
            base_strategy_key="baseline",
            proposed_version="v4",
            hypothesis="This proposal has a measurable hypothesis but invalid keep-rate bounds.",
            rationale="Bounds must be ordered so a backtest can judge the expectation.",
            baseline="baseline_v1",
            expected_keep_rate_min=0.9,
            expected_keep_rate_max=0.7,
            expected_coverage_rate_min=0.85,
            failure_conditions=["Reject if the metric bounds cannot be evaluated."],
        )
