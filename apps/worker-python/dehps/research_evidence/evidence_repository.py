from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from dehps.research.models import HypothesisEvidence
from dehps.research.repository import HypothesisRepository
from dehps.research.service import ResearchHypothesisService
from dehps.research_evidence.models import EvidenceRecord


class EvidenceRepository:
    def __init__(
        self,
        repository: HypothesisRepository | None = None,
        service: ResearchHypothesisService | None = None,
    ) -> None:
        self.repository = repository or HypothesisRepository()
        self.service = service or ResearchHypothesisService(self.repository)

    def ensure_schema(self) -> None:
        self.repository.ensure_schema()

    def append(self, records: Iterable[EvidenceRecord]) -> tuple[EvidenceRecord, ...]:
        appended: list[EvidenceRecord] = []
        for record in records:
            evidence = self.service.register_evidence(
                hypothesis_key=record.hypothesis_key,
                experiment_key=record.experiment_key,
                evidence_type=f"round25_{record.metric}",
                direction=record.direction,
                summary=record.summary,
                metrics=record.to_metrics(),
                artifact_path=record.artifact_path,
                content_hash=record.content_hash,
                metadata={**record.metadata, "evidence_source": record.evidence_source.value},
            )
            appended.append(replace(record, registry_id=evidence.id))
        return tuple(appended)

    def list_for_hypothesis(self, hypothesis_key: str) -> tuple[HypothesisEvidence, ...]:
        return tuple(self.repository.list_evidence(hypothesis_key))

    def list_round25_for_hypothesis(self, hypothesis_key: str) -> tuple[HypothesisEvidence, ...]:
        return tuple(
            evidence
            for evidence in self.repository.list_evidence(hypothesis_key)
            if str(evidence.evidence_type).startswith("round25_")
        )
