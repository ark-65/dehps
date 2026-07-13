from dataclasses import replace

from dehps.research_autonomy.validation import HypothesisProposalValidator
from research_autonomy_fixtures import make_context, make_proposal


def failed_keys(report):
    return {item.key for item in report.checks if not item.passed}


def test_valid_proposal_passes_all_scientific_boundaries() -> None:
    context = make_context()
    report = HypothesisProposalValidator().validate(make_proposal(context), context)
    assert report.valid is True
    assert failed_keys(report) == set()


def test_validator_rejects_no_null_random_split_and_leakage() -> None:
    context = make_context()
    proposal = make_proposal(context)
    invalid = replace(
        proposal,
        null_hypothesis="",
        input_boundary={**proposal.input_boundary, "contains_future_information": True},
        validation_protocol={**proposal.validation_protocol, "kind": "random_split", "random_split": True},
    )
    report = HypothesisProposalValidator().validate(invalid, context)
    assert report.valid is False
    assert {"null_hypothesis", "no_random_split", "no_future_information"}.issubset(failed_keys(report))


def test_validator_rejects_unbounded_compute_and_missing_formal_data() -> None:
    context = replace(make_context(), source_training_run_ids=(), formal_source_paths=())
    proposal = replace(make_proposal(context), estimated_compute_cost=0.99)
    report = HypothesisProposalValidator().validate(proposal, context)
    assert {"compute_budget", "data_sufficiency"}.issubset(failed_keys(report))
