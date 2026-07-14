from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from dehps.agents.errors import AgentAuthorityError, AgentRequestConflictError
from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentRequestStatus, AgentRequestType
from dehps.agents.roles import AgentRole
from dehps.agents.service import AgentRequestService
from dehps.research.repository import HypothesisRepository
from dehps.research_evidence.artifact_reader import Round24ArtifactReader
from dehps.research_evidence.decision_builder import DecisionBuilder, SequentialEvidenceAggregator
from dehps.research_evidence.evidence_builder import EvidenceBuilder
from dehps.research_evidence.evidence_repository import EvidenceRepository
from dehps.research_evidence.hypothesis_updater import HypothesisDecisionUpdater
from dehps.research_evidence.metrics_loader import MetricsLoader
from dehps.research_evidence.models import DecisionDraft, EvidenceRecord
from dehps.research_evidence.validation import validate_decision_draft, validate_evidence_records


class EvidenceEvaluationService:
    def __init__(
        self,
        *,
        evidence_repository: EvidenceRepository | None = None,
        hypothesis_repository: HypothesisRepository | None = None,
        agent_repository: AgentRequestRepository | None = None,
        agent_service: AgentRequestService | None = None,
    ) -> None:
        self.hypothesis_repository = hypothesis_repository or HypothesisRepository()
        self.evidence_repository = evidence_repository or EvidenceRepository(self.hypothesis_repository)
        self.agent_repository = agent_repository or AgentRequestRepository()
        self.agent_service = agent_service or AgentRequestService(self.agent_repository)
        self.reader = Round24ArtifactReader()
        self.metrics_loader = MetricsLoader()
        self.evidence_builder = EvidenceBuilder()
        self.aggregator = SequentialEvidenceAggregator()
        self.decision_builder = DecisionBuilder()
        self.updater = HypothesisDecisionUpdater(
            hypothesis_repository=self.hypothesis_repository,
            agent_repository=self.agent_repository,
        )

    def ensure_schema(self) -> None:
        self.evidence_repository.ensure_schema()
        self.agent_repository.ensure_schema()

    def build_evidence(
        self,
        *,
        artifact_directory: Path,
        hypothesis_key: str | None = None,
        plan_key: str | None = None,
        plan_fingerprint: str | None = None,
        append: bool = True,
    ) -> dict[str, Any]:
        report = self.reader.read(
            artifact_directory,
            expected_hypothesis_key=hypothesis_key,
            expected_plan_key=plan_key,
            expected_plan_fingerprint=plan_fingerprint,
        )
        observations = self.metrics_loader.load(report)
        records = self.evidence_builder.build(report=report, observations=observations)
        validation = validate_evidence_records(records)
        appended = self.evidence_repository.append(records) if append else records
        return {
            "artifact_validation": report,
            "observation_count": len(observations),
            "evidence_count": len(appended),
            "evidence": appended,
            "validation": validation,
            "appended": append,
        }

    def show_evidence(self, key: str) -> dict[str, Any]:
        for hypothesis in self.hypothesis_repository.list_hypotheses(limit=10_000):
            for evidence in self.hypothesis_repository.list_evidence(hypothesis.hypothesis_key):
                evidence_key = str(evidence.metadata.get("evidence_key") or "")
                if key in {str(evidence.id), evidence_key, str(evidence.content_hash or "")}:
                    return {"evidence": evidence, "hypothesis_key": hypothesis.hypothesis_key}
        raise AgentAuthorityError(f"evidence not found: {key}")

    def aggregate(self, *, hypothesis_key: str) -> dict[str, Any]:
        evidence = self.evidence_repository.list_round25_for_hypothesis(hypothesis_key)
        aggregation = self.aggregator.aggregate(hypothesis_key, evidence)
        return {"aggregation": aggregation, "evidence_count": len(evidence)}

    def draft_decision(
        self,
        *,
        hypothesis_key: str,
        requested_by: str = "research:evidence-engine",
        submit: bool = True,
    ) -> dict[str, Any]:
        evidence = self.evidence_repository.list_round25_for_hypothesis(hypothesis_key)
        aggregation = self.aggregator.aggregate(hypothesis_key, evidence)
        draft = self.decision_builder.build(aggregation)
        validation = validate_decision_draft(draft)
        if not validation["valid"]:
            return {"draft": draft, "request": None, "validation": validation, "submitted": False}
        request = self._create_decision_request(draft, requested_by=requested_by)
        submitted = False
        if submit and request.status == AgentRequestStatus.DRAFT:
            request = self.agent_service.submit(
                request.request_key,
                actor_role=AgentRole.RESEARCH,
                actor_id=requested_by,
                environment="isolated",
            )
            submitted = True
        return {"draft": draft, "request": request, "validation": validation, "submitted": submitted}

    def review_decision(self, *, request_key: str, reviewer_id: str) -> dict[str, Any]:
        request = self.agent_repository.get_request(request_key)
        if request.status == AgentRequestStatus.SUBMITTED:
            request = self.agent_service.begin_review(
                request_key,
                reviewer_role=AgentRole.REVIEWER,
                reviewer_id=reviewer_id,
                environment="isolated",
            )
        return {"request": request}

    def approve_decision(self, *, request_key: str, reviewer_id: str) -> dict[str, Any]:
        request = self.agent_repository.get_request(request_key)
        if request.status == AgentRequestStatus.SUBMITTED:
            request = self.agent_service.begin_review(
                request_key,
                reviewer_role=AgentRole.REVIEWER,
                reviewer_id=reviewer_id,
                environment="isolated",
            )
        if request.status == AgentRequestStatus.UNDER_REVIEW:
            request = self.agent_service.approve(
                request_key,
                reviewer_role=AgentRole.REVIEWER,
                reviewer_id=reviewer_id,
                reason={
                    "round25": "Reviewer approved autonomous Decision Draft",
                    "proposed_status": request.payload.get("proposed_status"),
                    "evidence_ids": request.payload.get("evidence_ids", []),
                },
                environment="isolated",
            )
        if request.status == AgentRequestStatus.APPROVED:
            request, execution = self.agent_service.begin_execution(
                request_key,
                executor_role=AgentRole.REVIEWER,
                executor_id=reviewer_id,
                environment="isolated",
            )
            update = self.updater.apply_approved_request(request_key, decided_by=reviewer_id)
            request, execution = self.agent_service.complete_execution(
                request_key,
                execution_id=execution.id,
                executor_role=AgentRole.REVIEWER,
                executor_id=reviewer_id,
                result={"registry_update": update},
                artifact_paths=[],
            )
            return {"request": request, "execution": execution, "registry_update": update}
        if request.status == AgentRequestStatus.COMPLETED:
            return {"request": request, "registry_update": {"already_completed": True}}
        raise AgentAuthorityError(f"decision request cannot be approved from status {request.status.value}")

    def reject_decision(self, *, request_key: str, reviewer_id: str, reason: dict[str, Any] | None = None) -> dict[str, Any]:
        request = self.agent_repository.get_request(request_key)
        if request.status == AgentRequestStatus.SUBMITTED:
            request = self.agent_service.begin_review(
                request_key,
                reviewer_role=AgentRole.REVIEWER,
                reviewer_id=reviewer_id,
                environment="isolated",
            )
        if request.status != AgentRequestStatus.UNDER_REVIEW:
            raise AgentAuthorityError(f"decision request cannot be rejected from status {request.status.value}")
        request = self.agent_service.reject(
            request_key,
            reviewer_role=AgentRole.REVIEWER,
            reviewer_id=reviewer_id,
            reason=reason or {"round25": "Reviewer rejected autonomous Decision Draft"},
            environment="isolated",
        )
        return {"request": request}

    def _create_decision_request(self, draft: DecisionDraft, *, requested_by: str):
        try:
            return self.agent_service.create_draft(
                request_key=draft.request_key(),
                request_type=AgentRequestType.RESEARCH_DECISION_SUBMISSION,
                requested_by_role=AgentRole.RESEARCH,
                requested_by=requested_by,
                title=f"Decision Draft for {draft.hypothesis_key}",
                summary=draft.summary,
                payload=draft.payload(),
                environment="isolated",
                hypothesis_key=draft.hypothesis_key,
                metadata={
                    "schema_version": "autonomous-evidence-evaluation-v1",
                    "decision_key": draft.decision_key,
                    "evidence_keys": list(draft.evidence_keys),
                },
            )
        except AgentRequestConflictError:
            return self.agent_repository.get_request(draft.request_key())


def jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
