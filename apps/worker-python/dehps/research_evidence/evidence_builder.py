from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from dehps.research.status import EvidenceDirection
from dehps.research_evidence.models import (
    ROUND25_SCHEMA_VERSION,
    ArtifactValidationReport,
    EvidenceRecord,
    MetricObservation,
    stable_hash,
)
from dehps.research_evidence.statistical_review import StatisticalReviewer


class EvidenceBuilder:
    def __init__(self, reviewer: StatisticalReviewer | None = None) -> None:
        self.reviewer = reviewer or StatisticalReviewer()

    def build(
        self,
        *,
        report: ArtifactValidationReport,
        observations: tuple[MetricObservation, ...],
        experiment_key: str = "ranking_disagreement_frozen_validation_v1",
    ) -> tuple[EvidenceRecord, ...]:
        if not report.valid:
            return (self._invalidating_record(report=report, experiment_key=experiment_key),)
        records: list[EvidenceRecord] = []
        for observation in observations:
            assessment = self.reviewer.assess(observation)
            payload = {
                "schema_version": ROUND25_SCHEMA_VERSION,
                "hypothesis_key": report.hypothesis_key,
                "plan_key": report.plan_key,
                "plan_fingerprint": report.plan_fingerprint,
                "manifest_hash": report.manifest_hash,
                "observation": asdict(observation),
                "assessment": asdict(assessment),
            }
            content_hash = stable_hash(payload)
            evidence_key = f"evidence-{report.hypothesis_key}-{content_hash[:16]}"
            records.append(
                EvidenceRecord(
                    evidence_key=evidence_key,
                    hypothesis_key=report.hypothesis_key,
                    experiment_key=experiment_key,
                    metric=observation.metric,
                    value=observation.value,
                    baseline=observation.baseline,
                    lift=observation.lift,
                    effect_size=observation.effect_size,
                    confidence_interval=observation.confidence_interval,
                    p_value=observation.p_value,
                    adjusted_p_value=observation.adjusted_p_value,
                    direction=assessment.direction,
                    supports_null=assessment.supports_null,
                    supports_alternative=assessment.supports_alternative,
                    stage=observation.stage,
                    stratum=observation.stratum,
                    artifact_path=_relative_artifact(report.artifact_directory, "statistics.json"),
                    content_hash=content_hash,
                    summary=(
                        f"{observation.metric} for {observation.stratum} vs {observation.baseline}: "
                        f"direction={assessment.direction.value}, adjusted_p={observation.adjusted_p_value:.4f}"
                    ),
                    metadata={
                        "schema_version": ROUND25_SCHEMA_VERSION,
                        "evidence_key": evidence_key,
                        "plan_key": report.plan_key,
                        "plan_fingerprint": report.plan_fingerprint,
                        "manifest_hash": report.manifest_hash,
                        "stage": observation.stage,
                        "statistical_assessment": asdict(assessment),
                        "metric_observation": asdict(observation),
                    },
                )
            )
        return tuple(records)

    def _invalidating_record(self, *, report: ArtifactValidationReport, experiment_key: str) -> EvidenceRecord:
        payload = {
            "schema_version": ROUND25_SCHEMA_VERSION,
            "hypothesis_key": report.hypothesis_key,
            "artifact_directory": report.artifact_directory,
            "failures": report.failure_reasons,
        }
        content_hash = stable_hash(payload)
        evidence_key = f"evidence-invalid-{report.hypothesis_key or 'unknown'}-{content_hash[:16]}"
        return EvidenceRecord(
            evidence_key=evidence_key,
            hypothesis_key=report.hypothesis_key,
            experiment_key=experiment_key,
            metric="artifact_validation",
            value=0.0,
            baseline="artifact_contract",
            lift=0.0,
            effect_size=0.0,
            confidence_interval={},
            p_value=1.0,
            adjusted_p_value=1.0,
            direction=EvidenceDirection.INVALIDATING,
            supports_null=False,
            supports_alternative=False,
            stage="artifact_validation",
            stratum="all",
            artifact_path=_relative_artifact(report.artifact_directory, "manifest.json"),
            content_hash=content_hash,
            summary="Round 24 artifact validation failed; Evidence is invalidating",
            metadata={
                "schema_version": ROUND25_SCHEMA_VERSION,
                "evidence_key": evidence_key,
                "artifact_validation": {
                    "valid": report.valid,
                    "failure_reasons": list(report.failure_reasons),
                    "checks": list(report.checks),
                },
            },
        )


def _relative_artifact(directory: str, filename: str) -> str:
    path = Path(directory) / filename
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()
