import pytest

from dehps.agents.errors import AgentRequestTransitionError
from dehps.agents.requests import AgentRequestStatus, REQUEST_TRANSITIONS
from dehps.agents.service import AgentRequestService


def test_transition_map_covers_every_status_and_terminal_states_are_final() -> None:
    assert set(REQUEST_TRANSITIONS) == set(AgentRequestStatus)
    for status in (
        AgentRequestStatus.REJECTED,
        AgentRequestStatus.CANCELLED,
        AgentRequestStatus.COMPLETED,
        AgentRequestStatus.FAILED,
        AgentRequestStatus.INVALIDATED,
    ):
        assert REQUEST_TRANSITIONS[status] == frozenset()


def test_happy_path_requires_review_before_execution() -> None:
    path = [
        AgentRequestStatus.DRAFT,
        AgentRequestStatus.SUBMITTED,
        AgentRequestStatus.UNDER_REVIEW,
        AgentRequestStatus.APPROVED,
        AgentRequestStatus.EXECUTING,
        AgentRequestStatus.COMPLETED,
    ]
    for current, new in zip(path, path[1:]):
        AgentRequestService._ensure_transition(current, new)


def test_invalid_transition_is_rejected() -> None:
    with pytest.raises(AgentRequestTransitionError, match="draft -> approved"):
        AgentRequestService._ensure_transition(AgentRequestStatus.DRAFT, AgentRequestStatus.APPROVED)
