from pathlib import Path

import pytest

from dehps.agents.errors import AgentRequestTransitionError
from dehps.agents.requests import AgentRequestStatus
from dehps.agents.service import AgentRequestService
from test_agent_request_service import Repository, draft


def test_service_rejects_payload_edit_after_submission() -> None:
    repository = Repository()
    repository.value = repository.value.__class__(
        **{**repository.value.__dict__, "status": AgentRequestStatus.APPROVED}
    )
    service = AgentRequestService(repository)  # type: ignore[arg-type]
    with pytest.raises(AgentRequestTransitionError, match="only draft"):
        service.update_draft_payload(
            "eng-1",
            actor_role=repository.value.requested_by_role,
            actor_id=repository.value.requested_by,
            payload=draft().payload,
        )


def test_database_guard_checks_prior_approval_decision_even_after_cancel() -> None:
    sql = (Path(__file__).resolve().parents[3] / "infra/postgres/init/001_init.sql").read_text()
    assert "d.new_status = 'approved'" in sql
    assert "NEW.payload_json IS DISTINCT FROM OLD.payload_json" in sql
