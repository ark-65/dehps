import pytest

from dehps.research.errors import InvalidTransitionError
from dehps.research.status import ExperimentStatus, HypothesisFamilyStatus, HypothesisStatus
from dehps.research.transitions import (
    EXPERIMENT_TRANSITIONS,
    FAMILY_TRANSITIONS,
    HYPOTHESIS_TRANSITIONS,
    validate_experiment_transition,
    validate_family_reopen,
    validate_family_transition,
    validate_hypothesis_transition,
)


@pytest.mark.parametrize(
    ("current", "new"),
    [
        (current, new)
        for current, destinations in HYPOTHESIS_TRANSITIONS.items()
        for new in destinations
    ],
)
def test_all_declared_hypothesis_transitions_are_valid(current, new) -> None:
    validate_hypothesis_transition(current, new)


@pytest.mark.parametrize(
    "new",
    [
        HypothesisStatus.PROPOSED,
        HypothesisStatus.PREREGISTERED,
        HypothesisStatus.RUNNING,
        HypothesisStatus.ACCEPTED_FOR_FOLLOWUP,
    ],
)
def test_rejected_hypothesis_cannot_transition_in_place(new) -> None:
    with pytest.raises(InvalidTransitionError, match="rejected"):
        validate_hypothesis_transition(HypothesisStatus.REJECTED, new)


def test_hypothesis_cannot_skip_preregistration() -> None:
    with pytest.raises(InvalidTransitionError, match="proposed -> running"):
        validate_hypothesis_transition("proposed", "running")


@pytest.mark.parametrize(
    ("current", "new"),
    [
        (current, new)
        for current, destinations in FAMILY_TRANSITIONS.items()
        for new in destinations
    ],
)
def test_all_declared_family_transitions_are_valid(current, new) -> None:
    validate_family_transition(current, new)


def test_family_reopen_is_separate_from_normal_transition() -> None:
    with pytest.raises(InvalidTransitionError):
        validate_family_transition("rejected", "reopened")

    validate_family_reopen(HypothesisFamilyStatus.REJECTED)
    validate_family_reopen(HypothesisFamilyStatus.EXHAUSTED)
    with pytest.raises(InvalidTransitionError, match="only rejected or exhausted"):
        validate_family_reopen(HypothesisFamilyStatus.ACTIVE)


@pytest.mark.parametrize(
    ("current", "new"),
    [
        (current, new)
        for current, destinations in EXPERIMENT_TRANSITIONS.items()
        for new in destinations
    ],
)
def test_all_declared_experiment_transitions_are_valid(current, new) -> None:
    validate_experiment_transition(current, new)


@pytest.mark.parametrize(
    "status",
    [
        ExperimentStatus.COMPLETED,
        ExperimentStatus.FAILED,
        ExperimentStatus.INVALIDATED,
        ExperimentStatus.CANCELLED,
    ],
)
def test_terminal_experiment_statuses_are_immutable(status) -> None:
    with pytest.raises(InvalidTransitionError):
        validate_experiment_transition(status, ExperimentStatus.RUNNING)


def test_unknown_and_noop_statuses_are_rejected() -> None:
    with pytest.raises(InvalidTransitionError, match="unknown hypothesis status"):
        validate_hypothesis_transition("invented", "running")
    with pytest.raises(InvalidTransitionError, match="already proposed"):
        validate_hypothesis_transition("proposed", "proposed")
