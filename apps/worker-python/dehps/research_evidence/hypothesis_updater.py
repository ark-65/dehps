from __future__ import annotations

from typing import Any

from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentRequest, AgentRequestStatus, AgentRequestType
from dehps.research.errors import RegistryConflictError
from dehps.research.repository import HypothesisRepository
from dehps.research.service import ResearchHypothesisService
from dehps.research.status import HypothesisStatus, RejectionScope


class HypothesisDecisionUpdater:
    def __init__(
        self,
        *,
        hypothesis_repository: HypothesisRepository | None = None,
        agent_repository: AgentRequestRepository | None = None,
        service: ResearchHypothesisService | None = None,
    ) -> None:
        self.hypothesis_repository = hypothesis_repository or HypothesisRepository()
        self.agent_repository = agent_repository or AgentRequestRepository()
        self.service = service or ResearchHypothesisService(self.hypothesis_repository)

    def apply_approved_request(self, request_key: str, *, decided_by: str) -> dict[str, Any]:
        request = self.agent_repository.get_request(request_key)
        self._validate_request(request)
        payload = request.payload
        hypothesis_key = str(payload["hypothesis_key"])
        proposed_status = HypothesisStatus(str(payload["proposed_status"]))
        evidence_ids = [int(value) for value in payload.get("evidence_ids", [])]
        if not evidence_ids:
            raise RegistryConflictError("decision request must cite at least one evidence id")

        hypothesis = self.hypothesis_repository.get_hypothesis(hypothesis_key)
        started = False
        if proposed_status in {
            HypothesisStatus.ACCEPTED_FOR_FOLLOWUP,
            HypothesisStatus.REJECTED,
            HypothesisStatus.INCONCLUSIVE,
        } and hypothesis.status == HypothesisStatus.PREREGISTERED:
            self.service.start(hypothesis_key, decided_by=decided_by)
            started = True

        if proposed_status == HypothesisStatus.INVALIDATED:
            updated = self.hypothesis_repository.transition_hypothesis(
                hypothesis_key=hypothesis_key,
                new_status=HypothesisStatus.INVALIDATED,
                decision_code=str(payload.get("decision_code") or "autonomous_evidence_invalidated"),
                summary=str(payload.get("summary") or "autonomous evidence invalidated the hypothesis"),
                decided_by=decided_by,
                reason=dict(payload.get("reason") or {}),
                evidence_ids=evidence_ids,
            )
        else:
            updated = self.service.complete_with_decision(
                hypothesis_key,
                new_status=proposed_status,
                decision_code=str(payload.get("decision_code") or "autonomous_evidence_decision"),
                summary=str(payload.get("summary") or "autonomous evidence decision approved"),
                decided_by=decided_by,
                reason=dict(payload.get("reason") or {}),
                evidence_ids=evidence_ids,
                rejection_scope=RejectionScope(str(payload.get("rejection_scope") or RejectionScope.NONE.value)),
                rejection_reason=payload.get("rejection_reason"),
                reopen_condition=payload.get("reopen_condition"),
            )
        family = self._family_status(updated.family_id)
        return {
            "hypothesis_key": updated.hypothesis_key,
            "hypothesis_status": updated.status.value,
            "family_status": family,
            "started_before_completion": started,
            "evidence_ids": evidence_ids,
            "decision_request_key": request_key,
        }

    @staticmethod
    def _validate_request(request: AgentRequest) -> None:
        if request.request_type != AgentRequestType.RESEARCH_DECISION_SUBMISSION:
            raise RegistryConflictError("request is not a research_decision_submission")
        if request.status not in {AgentRequestStatus.APPROVED, AgentRequestStatus.EXECUTING}:
            raise RegistryConflictError(f"decision request must be approved; found {request.status.value}")

    def _family_status(self, family_id: int) -> str:
        for family in self.hypothesis_repository.list_families(limit=10_000):
            if family.id == family_id:
                return family.status.value
        return "unknown"
