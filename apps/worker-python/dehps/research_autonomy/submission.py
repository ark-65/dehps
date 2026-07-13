from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json

from dehps.agents.errors import AgentRequestConflictError, AgentRequestValidationError
from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentRequest, AgentRequestStatus, AgentRequestType, AgentRiskLevel
from dehps.agents.roles import AgentRole
from dehps.agents.service import AgentRequestService
from dehps.research_autonomy.context import ResearchContext
from dehps.research_autonomy.proposal_models import ProposalEngineResult


class ResearchProposalSubmissionService:
    def __init__(
        self,
        agent_repository: AgentRequestRepository,
        agent_service: AgentRequestService | None = None,
    ) -> None:
        self.agent_repository = agent_repository
        self.agent_service = agent_service or AgentRequestService(agent_repository)

    def submit(
        self,
        result: ProposalEngineResult,
        context: ResearchContext,
        *,
        requested_by: str,
        request_key: str | None = None,
    ) -> AgentRequest:
        if result.selected is None or not result.candidates:
            raise AgentRequestValidationError("no validated autonomous proposal is available")
        selected = result.candidates[0]
        if selected.proposal != result.selected or not selected.validation_report.valid:
            raise AgentRequestValidationError("selected proposal is not the top validated candidate")
        key = request_key or self._request_key(result)
        payload = {
            "hypothesis_key": result.selected.proposal_key,
            "scientific_question": result.selected.scientific_question,
            "null_hypothesis": result.selected.null_hypothesis,
            "failure_condition": result.selected.failure_condition,
            "engine_version": result.engine_version,
            "context_fingerprint": result.context_fingerprint,
            "proposal": self._jsonable(result.selected),
            "novelty_report": self._jsonable(selected.novelty_report),
            "proposal_score": self._jsonable(selected.proposal_score),
            "validation_report": self._jsonable(selected.validation_report),
            "source_evidence_ids": [item.evidence_id for item in context.recent_evidence],
            "source_hypothesis_keys": [
                item.hypothesis_key
                for item in (*context.active_hypotheses, *context.rejected_hypotheses)
            ],
            "source_training_run_ids": list(context.source_training_run_ids),
        }
        try:
            request = self.agent_service.create_draft(
                request_key=key,
                request_type=AgentRequestType.RESEARCH_HYPOTHESIS_PROPOSAL,
                requested_by_role=AgentRole.RESEARCH,
                requested_by=requested_by,
                title=result.selected.title,
                summary=(
                    "Autonomous Research Agent proposal only; Reviewer approval is required before "
                    "any Hypothesis Registry conversion."
                ),
                payload=payload,
                environment="isolated",
                risk_level=AgentRiskLevel(result.selected.risk_level),
                metadata={
                    "engine_version": result.engine_version,
                    "context_fingerprint": result.context_fingerprint,
                    "proposal_content_hash": result.selected.content_hash,
                },
            )
        except AgentRequestConflictError:
            existing = self.agent_repository.get_request(key)
            if existing.payload != payload or existing.status != AgentRequestStatus.SUBMITTED:
                raise
            return existing
        return self.agent_service.submit(
            request.request_key,
            actor_role=AgentRole.RESEARCH,
            actor_id=requested_by,
            environment="isolated",
        )

    @staticmethod
    def _request_key(result: ProposalEngineResult) -> str:
        digest = sha256(
            f"{result.engine_version}:{result.context_fingerprint}:{result.selected.proposal_key}".encode(
                "utf-8"
            )
        ).hexdigest()[:16]
        return f"research-proposal-{digest}"

    @staticmethod
    def _jsonable(value: object) -> dict:
        return json.loads(json.dumps(asdict(value), sort_keys=True, separators=(",", ":")))
