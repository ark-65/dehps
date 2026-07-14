from dataclasses import replace
from datetime import datetime, timezone

from dehps.agents.requests import AgentRequestStatus
from dehps.research_evidence.service import EvidenceEvaluationService
from test_registry_update import request


NOW = datetime(2026, 7, 14, tzinfo=timezone.utc)


class AgentRepo:
    def __init__(self):
        self.value = replace(request(), status=AgentRequestStatus.SUBMITTED)

    def get_request(self, key):
        return self.value


class AgentService:
    def __init__(self, repo):
        self.repo = repo

    def begin_review(self, key, **kwargs):
        self.repo.value = replace(self.repo.value, status=AgentRequestStatus.UNDER_REVIEW)
        return self.repo.value

    def approve(self, key, **kwargs):
        self.repo.value = replace(self.repo.value, status=AgentRequestStatus.APPROVED)
        return self.repo.value

    def begin_execution(self, key, **kwargs):
        self.repo.value = replace(self.repo.value, status=AgentRequestStatus.EXECUTING)
        execution = type("Execution", (), {"id": 7})()
        return self.repo.value, execution

    def complete_execution(self, key, **kwargs):
        self.repo.value = replace(self.repo.value, status=AgentRequestStatus.COMPLETED)
        return self.repo.value, type("Execution", (), {"id": 7})()


class Updater:
    def apply_approved_request(self, key, *, decided_by):
        return {"hypothesis_status": "inconclusive", "family_status": "active"}


def test_reviewer_approval_executes_registry_update_and_completes_request() -> None:
    repo = AgentRepo()
    service = EvidenceEvaluationService(agent_repository=repo, agent_service=AgentService(repo))  # type: ignore[arg-type]
    service.updater = Updater()  # type: ignore[assignment]

    result = service.approve_decision(request_key="decision-1", reviewer_id="reviewer:test")

    assert result["request"].status == AgentRequestStatus.COMPLETED
    assert result["registry_update"]["hypothesis_status"] == "inconclusive"
