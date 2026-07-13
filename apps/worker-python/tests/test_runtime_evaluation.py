from __future__ import annotations

import pytest

from dehps.training.runtime_evaluation import RuntimeEvaluationNormalizer


def _normalizer(calls: list[str], *, isolation_passed: bool = True) -> RuntimeEvaluationNormalizer:
    def attach_source(*_args, **_kwargs):
        calls.append("source")

    def attach_baseline(*_args, **_kwargs):
        calls.append("baseline")

    def control(*_args, **_kwargs):
        calls.append("control")
        return [{"control": True}]

    def isolation(**_kwargs):
        calls.append("isolation")
        return {
            "passed": isolation_passed,
            "prefilter_frozen_issue_overlap": [],
            "prefilter_outside_split_issues": [],
        }

    def promotion(_candidate, _incumbent):
        calls.append("promotion")
        return {"passed": True}

    def quarantine(value):
        calls.append("quarantine")
        return value

    return RuntimeEvaluationNormalizer(
        attach_candidate_source_metadata=attach_source,
        attach_baseline_overlap=attach_baseline,
        sort_key=lambda summary: (summary["score"],),
        control_experiment_summaries=control,
        prefilter_holdout_isolation_audit=isolation,
        frozen_validation_promotion_gate=promotion,
        quarantine_historical_frozen_promotion=quarantine,
    )


def test_runtime_evaluation_normalizes_before_promotion() -> None:
    calls: list[str] = []
    summaries = [
        {"score": 1, "evaluation_split": {}},
        {"score": 2, "evaluation_split": {}},
    ]
    outcome = _normalizer(calls).normalize(
        summaries=summaries,
        diagnostic_sources={},
        advisor_candidates=(),
        control_configs=(),
        universe_size=10,
        prefilter_target_issues=(),
        prior_best_summary={"score": 0},
    )

    assert outcome.round_best["score"] == 2
    assert outcome.improved is True
    assert outcome.raw_improved is True
    assert outcome.evaluation_split == {}
    assert calls == [
        "source",
        "baseline",
        "control",
        "isolation",
        "promotion",
        "quarantine",
    ]


def test_runtime_evaluation_fails_closed_before_promotion_on_overlap() -> None:
    calls: list[str] = []
    with pytest.raises(RuntimeError, match="prefilter holdout isolation failed"):
        _normalizer(calls, isolation_passed=False).normalize(
            summaries=[{"score": 1, "evaluation_split": {}}],
            diagnostic_sources={},
            advisor_candidates=(),
            control_configs=(),
            universe_size=10,
            prefilter_target_issues=("issue",),
            prior_best_summary=None,
        )
    assert "promotion" not in calls
