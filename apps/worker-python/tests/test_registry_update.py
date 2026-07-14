from dataclasses import replace
from datetime import datetime, timezone

from dehps.agents.requests import AgentRequest, AgentRequestStatus, AgentRequestType, AgentRiskLevel
from dehps.agents.roles import AgentRole
from dehps.research.models import Hypothesis, HypothesisFamily
from dehps.research.status import HypothesisFamilyStatus, HypothesisStatus, RejectionScope
from dehps.research_evidence.hypothesis_updater import HypothesisDecisionUpdater


NOW = datetime(2026, 7, 14, tzinfo=timezone.utc)


def request(status=AgentRequestStatus.APPROVED):
    return AgentRequest(
        id=1,
        request_key="decision-1",
        request_type=AgentRequestType.RESEARCH_DECISION_SUBMISSION,
        requested_by_role=AgentRole.RESEARCH,
        requested_by="research:evidence",
        hypothesis_id=1,
        experiment_id=None,
        parent_request_id=None,
        title="Decision",
        summary="summary",
        payload={
            "hypothesis_key": "hypothesis-1",
            "proposed_status": "inconclusive",
            "evidence_ids": [10],
            "reason": {"why": "no forward"},
            "decision_code": "autonomous_evidence_inconclusive",
            "summary": "inconclusive",
            "rejection_scope": "none",
        },
        status=status,
        risk_level=AgentRiskLevel.HIGH,
        requires_review=True,
        created_at=NOW,
        updated_at=NOW,
        submitted_at=NOW,
        resolved_at=None,
    )


class AgentRepo:
    def get_request(self, key):
        return request()


class HypothesisRepo:
    def __init__(self):
        self.hypothesis = Hypothesis(
            id=1,
            hypothesis_key="hypothesis-1",
            family_id=2,
            parent_hypothesis_id=None,
            title="h",
            statement="s",
            mechanism="m",
            null_hypothesis="n",
            minimal_non_null="a",
            invariants=[],
            baseline_definition={},
            metric_definition={},
            failure_condition={},
            self_deception_risk=[],
            status=HypothesisStatus.PREREGISTERED,
            rejection_scope=RejectionScope.NONE,
            rejection_reason=None,
            reopen_condition=None,
            created_at=NOW,
            updated_at=NOW,
            preregistered_at=NOW,
            started_at=None,
            resolved_at=None,
        )

    def get_hypothesis(self, key):
        return self.hypothesis

    def list_families(self, limit=10000):
        return [
            HypothesisFamily(
                id=2,
                family_key="family",
                title="family",
                description="",
                mechanism="m",
                status=HypothesisFamilyStatus.ACTIVE,
                rejection_scope=RejectionScope.NONE,
                rejection_reason=None,
                reopen_condition=None,
                created_at=NOW,
                updated_at=NOW,
                resolved_at=None,
            )
        ]


class ResearchService:
    def __init__(self):
        self.started = False
        self.completed = False

    def start(self, hypothesis_key, *, decided_by):
        self.started = True

    def complete_with_decision(self, hypothesis_key, **kwargs):
        self.completed = True
        return replace(HypothesisRepo().hypothesis, status=kwargs["new_status"])


def test_hypothesis_updater_starts_preregistered_hypothesis_then_appends_decision() -> None:
    research_service = ResearchService()
    updater = HypothesisDecisionUpdater(
        hypothesis_repository=HypothesisRepo(),  # type: ignore[arg-type]
        agent_repository=AgentRepo(),  # type: ignore[arg-type]
        service=research_service,  # type: ignore[arg-type]
    )

    result = updater.apply_approved_request("decision-1", decided_by="reviewer:test")

    assert research_service.started is True
    assert research_service.completed is True
    assert result["hypothesis_status"] == "inconclusive"
