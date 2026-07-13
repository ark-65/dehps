from dataclasses import replace

from experiment_plan_fixtures import ranking_plan, ranking_proposal
from dehps.research_planning.validation import ExperimentPlanValidator
from research_autonomy_fixtures import make_context


def report(plan):
    return ExperimentPlanValidator().validate(plan, ranking_proposal(), make_context())


def test_valid_experiment_plan_passes_all_checks() -> None:
    result = report(ranking_plan())
    assert result.valid is True
    assert len(result.checks) >= 18


def test_unapproved_proposal_rejection() -> None:
    plan = ranking_plan()
    protocol = {**plan.validation_protocol, "reviewer_approval": {"status": "submitted"}}
    result = report(replace(plan, validation_protocol=protocol))
    assert result.valid is False
    assert any("proposal must have a frozen Reviewer approval" in reason for reason in result.failure_reasons)


def test_proposal_and_null_tampering_are_rejected() -> None:
    plan = ranking_plan()
    tampered_fingerprint = report(replace(plan, proposal_fingerprint="bad"))
    tampered_null = report(replace(plan, null_hypothesis="different null"))

    assert tampered_fingerprint.valid is False
    assert tampered_null.valid is False


def test_failure_condition_tampering_is_rejected() -> None:
    plan = ranking_plan()
    result = report(replace(plan, failure_condition={"rule": "weakened"}))
    assert result.valid is False


def test_overlapping_windows_and_reduced_forward_minimum_are_rejected() -> None:
    plan = ranking_plan()
    overlap = {**plan.validation_protocol, "search_frozen_overlap": 1}
    short_forward = {**plan.validation_protocol, "forward_min_paired_issues": 19}

    assert report(replace(plan, validation_protocol=overlap)).valid is False
    assert report(replace(plan, validation_protocol=short_forward)).valid is False


def test_unequal_baseline_budget_and_mutable_strata_are_rejected() -> None:
    plan = ranking_plan()
    bad_stage = replace(plan.experiment_stages[0], baseline_budget=plan.experiment_stages[0].candidate_budget + 1)
    bad_strata = {
        **plan.feature_contract,
        "strata": {**plan.feature_contract["strata"], "delete_failed_strata_allowed": True},
    }

    assert report(replace(plan, experiment_stages=(bad_stage, *plan.experiment_stages[1:]))).valid is False
    assert report(replace(plan, feature_contract=bad_strata)).valid is False


def test_future_field_rejection() -> None:
    plan = ranking_plan()
    features = dict(plan.feature_contract["disagreement_features"])
    features["rank_mean"] = {**features["rank_mean"], "future_information_allowed": True}
    result = report(replace(plan, feature_contract={**plan.feature_contract, "disagreement_features": features}))
    assert result.valid is False
