from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dehps.research.errors import (
    ArtifactReferenceError,
    PreregistrationError,
    RegistryConflictError,
    ReopenError,
)
from dehps.research.models import Hypothesis, HypothesisEvidence, HypothesisExperiment
from dehps.research.repository import HypothesisRepository
from dehps.research.status import (
    EvidenceDirection,
    ExperimentStatus,
    HypothesisFamilyStatus,
    HypothesisStatus,
    RejectionScope,
)


ALLOWED_REFERENCE_PREFIXES = ("docs/experiments/", "data/output/")
PARAMETER_REJECTION_FIELDS = frozenset(
    {"parameter_region", "failed_metrics", "data_boundary", "prohibited_parameter_only_changes"}
)
MECHANISM_REJECTION_FIELDS = frozenset(
    {"mechanism_signature", "failed_metrics", "data_boundary", "prohibited_parameter_only_changes"}
)


class ResearchHypothesisService:
    def __init__(
        self,
        repository: HypothesisRepository,
        *,
        repository_root: Path | None = None,
    ) -> None:
        self.repository = repository
        self.repository_root = (repository_root or Path(__file__).resolve().parents[4]).resolve()

    def preregister(
        self,
        hypothesis_key: str,
        *,
        decided_by: str,
        decision_code: str = "preregistration_completed",
    ) -> Hypothesis:
        hypothesis = self.repository.get_hypothesis(hypothesis_key)
        required = {
            "statement": hypothesis.statement,
            "null_hypothesis": hypothesis.null_hypothesis,
            "minimal_non_null": hypothesis.minimal_non_null,
            "invariants": hypothesis.invariants,
            "baseline_definition": hypothesis.baseline_definition,
            "metric_definition": hypothesis.metric_definition,
            "failure_condition": hypothesis.failure_condition,
            "self_deception_risk": hypothesis.self_deception_risk,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise PreregistrationError(
                "hypothesis preregistration is incomplete: " + ", ".join(sorted(missing))
            )
        return self.repository.transition_hypothesis(
            hypothesis_key=hypothesis_key,
            new_status=HypothesisStatus.PREREGISTERED,
            decision_code=decision_code,
            summary="hypothesis preregistration completed",
            decided_by=decided_by,
            reason={"validated_fields": sorted(required)},
        )

    def start(self, hypothesis_key: str, *, decided_by: str) -> Hypothesis:
        hypothesis = self.repository.get_hypothesis(hypothesis_key)
        family = self._family_for_hypothesis(hypothesis)
        if family.status in {HypothesisFamilyStatus.REJECTED, HypothesisFamilyStatus.EXHAUSTED}:
            raise RegistryConflictError(f"family {family.family_key} is not active")
        experiments = self.repository.list_experiments(hypothesis_key)
        if not any(experiment.status == ExperimentStatus.PLANNED for experiment in experiments):
            raise RegistryConflictError("starting a hypothesis requires at least one planned experiment")
        return self.repository.transition_hypothesis(
            hypothesis_key=hypothesis_key,
            new_status=HypothesisStatus.RUNNING,
            decision_code="hypothesis_started",
            summary="hypothesis execution started",
            decided_by=decided_by,
            reason={"planned_experiment_keys": [
                experiment.experiment_key
                for experiment in experiments
                if experiment.status == ExperimentStatus.PLANNED
            ]},
        )

    def complete_with_decision(
        self,
        hypothesis_key: str,
        *,
        new_status: HypothesisStatus,
        decision_code: str,
        summary: str,
        decided_by: str,
        reason: Mapping[str, Any],
        evidence_ids: Iterable[int],
        rejection_scope: RejectionScope = RejectionScope.NONE,
        rejection_reason: str | None = None,
        reopen_condition: str | None = None,
    ) -> Hypothesis:
        if new_status not in {
            HypothesisStatus.ACCEPTED_FOR_FOLLOWUP,
            HypothesisStatus.REJECTED,
            HypothesisStatus.INCONCLUSIVE,
        }:
            raise RegistryConflictError(f"unsupported completion status: {new_status.value}")
        if not decision_code.strip():
            raise RegistryConflictError("decision_code is required")
        hypothesis = self.repository.get_hypothesis(hypothesis_key)
        if hypothesis.status != HypothesisStatus.RUNNING:
            raise RegistryConflictError("only running hypotheses can complete")
        evidence = self.repository.list_evidence(hypothesis_key)
        if not evidence:
            raise RegistryConflictError("at least one evidence record is required")
        evidence_id_list = [int(value) for value in evidence_ids]
        if not evidence_id_list:
            raise RegistryConflictError("decision must cite at least one evidence id")
        experiments = self.repository.list_experiments(hypothesis_key)
        running = [
            experiment.experiment_key
            for experiment in experiments
            if experiment.status == ExperimentStatus.RUNNING
        ]
        if running:
            raise RegistryConflictError(
                "running experiments must end before decision: " + ", ".join(running)
            )
        if new_status == HypothesisStatus.REJECTED:
            self._validate_rejection(
                rejection_scope=rejection_scope,
                reason=reason,
                reopen_condition=reopen_condition,
            )
        return self.repository.transition_hypothesis(
            hypothesis_key=hypothesis_key,
            new_status=new_status,
            decision_code=decision_code,
            summary=summary,
            decided_by=decided_by,
            reason=reason,
            evidence_ids=evidence_id_list,
            rejection_scope=rejection_scope,
            rejection_reason=rejection_reason,
            reopen_condition=reopen_condition,
        )

    def reject(
        self,
        hypothesis_key: str,
        *,
        decision_code: str,
        summary: str,
        decided_by: str,
        reason: Mapping[str, Any],
        evidence_ids: Iterable[int],
        rejection_scope: RejectionScope,
        reopen_condition: str,
    ) -> Hypothesis:
        return self.complete_with_decision(
            hypothesis_key,
            new_status=HypothesisStatus.REJECTED,
            decision_code=decision_code,
            summary=summary,
            decided_by=decided_by,
            reason=reason,
            evidence_ids=evidence_ids,
            rejection_scope=rejection_scope,
            rejection_reason=summary,
            reopen_condition=reopen_condition,
        )

    def invalidate(
        self,
        hypothesis_key: str,
        *,
        decision_code: str,
        summary: str,
        decided_by: str,
        reason: Mapping[str, Any],
        evidence_ids: Iterable[int] = (),
    ) -> Hypothesis:
        return self.repository.transition_hypothesis(
            hypothesis_key=hypothesis_key,
            new_status=HypothesisStatus.INVALIDATED,
            decision_code=decision_code,
            summary=summary,
            decided_by=decided_by,
            reason=reason,
            evidence_ids=evidence_ids,
        )

    def reopen(
        self,
        hypothesis_key: str,
        *,
        new_hypothesis_key: str,
        reopen_reason: str,
        decided_by: str,
        changed_basis: Mapping[str, Any],
        title: str | None = None,
    ) -> Hypothesis:
        allowed_basis = {"new_data", "feature_family", "causal_variable", "validation_protocol"}
        if not allowed_basis.intersection(changed_basis):
            raise ReopenError(
                "changed_basis must record new_data, feature_family, causal_variable, or validation_protocol"
            )
        return self.repository.reopen_hypothesis(
            hypothesis_key=hypothesis_key,
            new_hypothesis_key=new_hypothesis_key,
            reopen_reason=reopen_reason,
            decided_by=decided_by,
            changed_basis=changed_basis,
            title=title,
        )

    def register_experiment(
        self,
        *,
        hypothesis_key: str,
        experiment_key: str,
        experiment_type: str,
        report_path: str | None = None,
        artifact_paths: Iterable[str] = (),
        external_run_id: str | None = None,
        training_run_id: str | None = None,
        training_round_index: int | None = None,
        config_snapshot: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        external_reference: bool = False,
        compute_hashes: bool = False,
    ) -> HypothesisExperiment:
        normalized_report = self._validate_reference(report_path, external_reference)
        normalized_artifacts = [
            self._validate_reference(path, external_reference) for path in artifact_paths
        ]
        normalized_artifacts = [path for path in normalized_artifacts if path is not None]
        merged_metadata = dict(metadata or {})
        if compute_hashes:
            merged_metadata["content_hashes"] = {
                path: self._sha256(path)
                for path in ([normalized_report] if normalized_report else []) + normalized_artifacts
            }
        return self.repository.create_experiment(
            hypothesis_key=hypothesis_key,
            experiment_key=experiment_key,
            experiment_type=experiment_type,
            external_run_id=external_run_id,
            training_run_id=training_run_id,
            training_round_index=training_round_index,
            report_path=normalized_report,
            artifact_paths=normalized_artifacts,
            config_snapshot=config_snapshot,
            metadata=merged_metadata,
        )

    def register_evidence(
        self,
        *,
        hypothesis_key: str,
        evidence_type: str,
        direction: EvidenceDirection,
        summary: str,
        experiment_key: str | None = None,
        metrics: Mapping[str, Any] | None = None,
        artifact_path: str | None = None,
        content_hash: str | None = None,
        observed_at: datetime | None = None,
        metadata: Mapping[str, Any] | None = None,
        external_reference: bool = False,
    ) -> HypothesisEvidence:
        normalized_artifact = self._validate_reference(artifact_path, external_reference)
        if normalized_artifact and content_hash is None and not external_reference:
            content_hash = self._sha256(normalized_artifact)
        return self.repository.add_evidence(
            hypothesis_key=hypothesis_key,
            experiment_key=experiment_key,
            evidence_type=evidence_type,
            direction=direction,
            summary=summary,
            metrics=metrics,
            artifact_path=normalized_artifact,
            content_hash=content_hash,
            observed_at=observed_at or datetime.now(timezone.utc),
            metadata=metadata,
        )

    def _family_for_hypothesis(self, hypothesis: Hypothesis):
        families = self.repository.list_families(limit=10_000)
        for family in families:
            if family.id == hypothesis.family_id:
                return family
        raise RegistryConflictError("hypothesis family is missing")

    @staticmethod
    def _validate_rejection(
        *,
        rejection_scope: RejectionScope,
        reason: Mapping[str, Any],
        reopen_condition: str | None,
    ) -> None:
        if rejection_scope == RejectionScope.NONE:
            raise RegistryConflictError("rejected hypotheses require a rejection scope")
        required = (
            PARAMETER_REJECTION_FIELDS
            if rejection_scope == RejectionScope.PARAMETER_REGION
            else MECHANISM_REJECTION_FIELDS
        )
        missing = sorted(field for field in required if not reason.get(field))
        if missing:
            raise RegistryConflictError(
                "rejection reason is incomplete: " + ", ".join(missing)
            )
        prohibited = {str(value).strip().lower() for value in reason["prohibited_parameter_only_changes"]}
        expected = {"seed", "epochs", "depth", "nearby_weights", "same_history_search_rounds", "rename"}
        if not expected.issubset(prohibited):
            raise RegistryConflictError(
                "rejection must prohibit seed, epochs, depth, nearby_weights, "
                "same_history_search_rounds, and rename-only retries"
            )
        if not str(reopen_condition or "").strip():
            raise RegistryConflictError("rejected hypotheses require a reopen_condition")

    def _validate_reference(self, value: str | None, external: bool) -> str | None:
        if value is None:
            return None
        candidate = Path(value)
        if candidate.is_absolute():
            try:
                candidate = candidate.resolve().relative_to(self.repository_root)
            except ValueError as exc:
                if external:
                    return value
                raise ArtifactReferenceError("reference must be inside the repository") from exc
        normalized = candidate.as_posix().lstrip("./")
        if not normalized.startswith(ALLOWED_REFERENCE_PREFIXES):
            if external:
                return value
            raise ArtifactReferenceError(
                "reference must be under docs/experiments or data/output"
            )
        full_path = (self.repository_root / normalized).resolve()
        if not full_path.is_relative_to(self.repository_root):
            raise ArtifactReferenceError("reference escapes repository root")
        if not external and not full_path.is_file():
            raise ArtifactReferenceError(f"reference file does not exist: {normalized}")
        return normalized

    def _sha256(self, relative_path: str) -> str:
        digest = hashlib.sha256()
        with (self.repository_root / relative_path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
