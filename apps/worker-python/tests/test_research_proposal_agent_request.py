from dataclasses import replace
from datetime import datetime, timezone

from dehps.agents.requests import AgentRequest, AgentRequestStatus, AgentRequestType
from dehps.agents.roles import AgentRole
from dehps.research_autonomy.proposal_engine import AutonomousHypothesisProposalEngine
from dehps.research_autonomy.submission import ResearchProposalSubmissionService
from research_autonomy_fixtures import make_context


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)


class Repository:
    def get_request(self, key):
        raise AssertionError("idempotent lookup not expected")


class AgentService:
    def __init__(self):
        self.created = None
        self.executions = 0

    def create_draft(self, **kwargs):
        self.created = kwargs
        return AgentRequest(
            id=1, request_key=kwargs["request_key"], request_type=kwargs["request_type"],
            requested_by_role=kwargs["requested_by_role"], requested_by=kwargs["requested_by"],
            hypothesis_id=None, experiment_id=None, parent_request_id=None, title=kwargs["title"],
            summary=kwargs["summary"], payload=kwargs["payload"], status=AgentRequestStatus.DRAFT,
            risk_level=kwargs["risk_level"], requires_review=True, created_at=NOW, updated_at=NOW,
            submitted_at=None, resolved_at=None, metadata=kwargs["metadata"],
        )

    def submit(self, key, **kwargs):
        return replace(self.request, status=AgentRequestStatus.SUBMITTED, submitted_at=NOW)

    @property
    def request(self):
        kwargs = self.created
        return AgentRequest(
            id=1, request_key=kwargs["request_key"], request_type=kwargs["request_type"],
            requested_by_role=kwargs["requested_by_role"], requested_by=kwargs["requested_by"],
            hypothesis_id=None, experiment_id=None, parent_request_id=None, title=kwargs["title"],
            summary=kwargs["summary"], payload=kwargs["payload"], status=AgentRequestStatus.DRAFT,
            risk_level=kwargs["risk_level"], requires_review=True, created_at=NOW, updated_at=NOW,
            submitted_at=None, resolved_at=None, metadata=kwargs["metadata"],
        )


def test_selected_proposal_creates_only_submitted_research_request() -> None:
    context = make_context()
    result = AutonomousHypothesisProposalEngine().propose(context)
    agent_service = AgentService()
    request = ResearchProposalSubmissionService(Repository(), agent_service).submit(
        result, context, requested_by="research:auto"
    )
    assert request.status == AgentRequestStatus.SUBMITTED
    assert request.request_type == AgentRequestType.RESEARCH_HYPOTHESIS_PROPOSAL
    assert request.requested_by_role == AgentRole.RESEARCH
    assert request.hypothesis_id is None
    assert agent_service.executions == 0
    assert request.payload["engine_version"] == result.engine_version
    assert request.payload["validation_report"]["valid"] is True
