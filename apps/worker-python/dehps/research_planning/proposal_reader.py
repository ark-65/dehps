from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dehps.agents.errors import AgentRequestConflictError, AgentRequestNotFoundError
from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentRequest, AgentRequestStatus, AgentRequestType
from dehps.research_autonomy.proposal_models import HypothesisProposal


@dataclass(frozen=True)
class ApprovedProposal:
    request: AgentRequest
    proposal: HypothesisProposal
    approval_decision: dict[str, Any]


class ApprovedProposalReader:
    def __init__(self, repository: AgentRequestRepository) -> None:
        self.repository = repository

    def read(self, request_key: str) -> ApprovedProposal:
        request = self.repository.get_request(request_key)
        return self._approved(request)

    def latest(self) -> ApprovedProposal:
        requests = self.repository.list_requests(
            request_type=AgentRequestType.RESEARCH_HYPOTHESIS_PROPOSAL,
            status=AgentRequestStatus.APPROVED,
            limit=1,
        )
        if not requests:
            raise AgentRequestNotFoundError("no approved research_hypothesis_proposal request found")
        return self._approved(requests[0])

    def _approved(self, request: AgentRequest) -> ApprovedProposal:
        if request.request_type != AgentRequestType.RESEARCH_HYPOTHESIS_PROPOSAL:
            raise AgentRequestConflictError(
                f"request is not a research_hypothesis_proposal: {request.request_key}"
            )
        if request.status != AgentRequestStatus.APPROVED:
            raise AgentRequestConflictError(
                f"proposal request must be approved before planning; found {request.status.value}"
            )
        proposal_payload = request.payload.get("proposal")
        if not isinstance(proposal_payload, dict):
            raise AgentRequestConflictError("approved proposal request is missing proposal payload")
        proposal = _proposal_from_payload(proposal_payload)
        decisions = self.repository.list_decisions(request.request_key)
        approval = next(
            (
                {
                    "previous_status": item.previous_status,
                    "new_status": item.new_status,
                    "decision_code": item.decision_code,
                    "summary": item.summary,
                    "reason": item.reason,
                    "decided_by_role": item.decided_by_role.value,
                    "decided_by": item.decided_by,
                    "decided_at": item.decided_at.isoformat(),
                }
                for item in reversed(decisions)
                if item.new_status == AgentRequestStatus.APPROVED.value
            ),
            {
                "previous_status": AgentRequestStatus.UNDER_REVIEW.value,
                "new_status": AgentRequestStatus.APPROVED.value,
                "decision_code": "request_approved",
                "summary": "approved proposal request",
                "reason": {},
                "decided_by_role": "reviewer",
                "decided_by": "reviewer:unknown",
                "decided_at": None,
            },
        )
        return ApprovedProposal(request=request, proposal=proposal, approval_decision=approval)


def _proposal_from_payload(payload: dict[str, Any]) -> HypothesisProposal:
    tuple_fields = {
        "invariants",
        "self_deception_risks",
        "novelty_basis",
        "differs_from_rejected_families",
    }
    normalized = {
        key: tuple(value) if key in tuple_fields and isinstance(value, list) else value
        for key, value in payload.items()
    }
    return HypothesisProposal(**normalized)
