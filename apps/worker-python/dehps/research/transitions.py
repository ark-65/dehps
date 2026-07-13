from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import TypeVar

from dehps.research.errors import InvalidTransitionError
from dehps.research.status import ExperimentStatus, HypothesisFamilyStatus, HypothesisStatus


StatusT = TypeVar("StatusT", bound=Enum)


HYPOTHESIS_TRANSITIONS: Mapping[HypothesisStatus, frozenset[HypothesisStatus]] = {
    HypothesisStatus.PROPOSED: frozenset(
        {HypothesisStatus.PREREGISTERED, HypothesisStatus.INVALIDATED}
    ),
    HypothesisStatus.PREREGISTERED: frozenset(
        {HypothesisStatus.RUNNING, HypothesisStatus.INVALIDATED}
    ),
    HypothesisStatus.RUNNING: frozenset(
        {
            HypothesisStatus.ACCEPTED_FOR_FOLLOWUP,
            HypothesisStatus.REJECTED,
            HypothesisStatus.INCONCLUSIVE,
            HypothesisStatus.INVALIDATED,
        }
    ),
    HypothesisStatus.ACCEPTED_FOR_FOLLOWUP: frozenset(
        {
            HypothesisStatus.RUNNING,
            HypothesisStatus.REJECTED,
            HypothesisStatus.INCONCLUSIVE,
        }
    ),
    HypothesisStatus.REJECTED: frozenset(),
    HypothesisStatus.INCONCLUSIVE: frozenset(),
    HypothesisStatus.INVALIDATED: frozenset(),
}


FAMILY_TRANSITIONS: Mapping[HypothesisFamilyStatus, frozenset[HypothesisFamilyStatus]] = {
    HypothesisFamilyStatus.ACTIVE: frozenset(
        {
            HypothesisFamilyStatus.PARTIALLY_REJECTED,
            HypothesisFamilyStatus.REJECTED,
            HypothesisFamilyStatus.EXHAUSTED,
        }
    ),
    HypothesisFamilyStatus.PARTIALLY_REJECTED: frozenset(
        {
            HypothesisFamilyStatus.ACTIVE,
            HypothesisFamilyStatus.REJECTED,
            HypothesisFamilyStatus.EXHAUSTED,
        }
    ),
    HypothesisFamilyStatus.REJECTED: frozenset(),
    HypothesisFamilyStatus.EXHAUSTED: frozenset(),
    HypothesisFamilyStatus.REOPENED: frozenset(
        {
            HypothesisFamilyStatus.ACTIVE,
            HypothesisFamilyStatus.PARTIALLY_REJECTED,
            HypothesisFamilyStatus.REJECTED,
            HypothesisFamilyStatus.EXHAUSTED,
        }
    ),
}


EXPERIMENT_TRANSITIONS: Mapping[ExperimentStatus, frozenset[ExperimentStatus]] = {
    ExperimentStatus.PLANNED: frozenset(
        {
            ExperimentStatus.RUNNING,
            ExperimentStatus.CANCELLED,
            ExperimentStatus.INVALIDATED,
        }
    ),
    ExperimentStatus.RUNNING: frozenset(
        {
            ExperimentStatus.COMPLETED,
            ExperimentStatus.FAILED,
            ExperimentStatus.INVALIDATED,
            ExperimentStatus.CANCELLED,
        }
    ),
    ExperimentStatus.COMPLETED: frozenset(),
    ExperimentStatus.FAILED: frozenset(),
    ExperimentStatus.INVALIDATED: frozenset(),
    ExperimentStatus.CANCELLED: frozenset(),
}


def _coerce(value: StatusT | str, enum_type: type[StatusT], label: str) -> StatusT:
    try:
        return value if isinstance(value, enum_type) else enum_type(value)
    except ValueError as exc:
        raise InvalidTransitionError(f"unknown {label} status: {value!r}") from exc


def _validate(
    current: StatusT,
    new: StatusT,
    transitions: Mapping[StatusT, frozenset[StatusT]],
    label: str,
) -> None:
    if current == new:
        raise InvalidTransitionError(f"{label} is already {current.value}")
    if new not in transitions[current]:
        raise InvalidTransitionError(
            f"invalid {label} transition: {current.value} -> {new.value}"
        )


def validate_hypothesis_transition(
    current_status: HypothesisStatus | str,
    new_status: HypothesisStatus | str,
) -> None:
    current = _coerce(current_status, HypothesisStatus, "hypothesis")
    new = _coerce(new_status, HypothesisStatus, "hypothesis")
    _validate(current, new, HYPOTHESIS_TRANSITIONS, "hypothesis")


def validate_family_transition(
    current_status: HypothesisFamilyStatus | str,
    new_status: HypothesisFamilyStatus | str,
) -> None:
    current = _coerce(current_status, HypothesisFamilyStatus, "family")
    new = _coerce(new_status, HypothesisFamilyStatus, "family")
    _validate(current, new, FAMILY_TRANSITIONS, "family")


def validate_family_reopen(current_status: HypothesisFamilyStatus | str) -> None:
    current = _coerce(current_status, HypothesisFamilyStatus, "family")
    if current not in {HypothesisFamilyStatus.REJECTED, HypothesisFamilyStatus.EXHAUSTED}:
        raise InvalidTransitionError(
            f"only rejected or exhausted families can reopen; current status is {current.value}"
        )


def validate_experiment_transition(
    current_status: ExperimentStatus | str,
    new_status: ExperimentStatus | str,
) -> None:
    current = _coerce(current_status, ExperimentStatus, "experiment")
    new = _coerce(new_status, ExperimentStatus, "experiment")
    _validate(current, new, EXPERIMENT_TRANSITIONS, "experiment")
