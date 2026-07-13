from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dehps.research.errors import ArtifactReferenceError, PreregistrationError, RegistryConflictError
from dehps.research.models import Hypothesis, HypothesisEvidence, HypothesisExperiment, HypothesisFamily
from dehps.research.service import ResearchHypothesisService
from dehps.research.status import (
    EvidenceDirection,
    ExperimentStatus,
    HypothesisFamilyStatus,
    HypothesisStatus,
    RejectionScope,
)


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)
PROHIBITED = ["seed", "epochs", "depth", "nearby_weights", "same_history_search_rounds", "rename"]


def family(status=HypothesisFamilyStatus.ACTIVE) -> HypothesisFamily:
    return HypothesisFamily(
        id=1,
        family_key="family-1",
        title="Family",
        description="",
        mechanism="mechanism",
        status=status,
        rejection_scope=RejectionScope.NONE,
        rejection_reason=None,
        reopen_condition=None,
        created_at=NOW,
        updated_at=NOW,
        resolved_at=None,
    )


def hypothesis(status=HypothesisStatus.PROPOSED, **overrides) -> Hypothesis:
    value = Hypothesis(
        id=2,
        hypothesis_key="hypothesis-1",
        family_id=1,
        parent_hypothesis_id=None,
        title="Hypothesis",
        statement="a falsifiable statement",
        mechanism="mechanism",
        null_hypothesis="no improvement",
        minimal_non_null="one preregistered metric improves",
        invariants=["history boundary"],
        baseline_definition={"key": "frozen"},
        metric_definition={"key": "objective"},
        failure_condition={"rule": "no lift"},
        self_deception_risk=["seed instability"],
        status=status,
        rejection_scope=RejectionScope.NONE,
        rejection_reason=None,
        reopen_condition=None,
        created_at=NOW,
        updated_at=NOW,
        preregistered_at=None,
        started_at=None,
        resolved_at=None,
    )
    return replace(value, **overrides)


def experiment(status=ExperimentStatus.PLANNED) -> HypothesisExperiment:
    return HypothesisExperiment(
        id=4,
        hypothesis_id=2,
        experiment_key="experiment-1",
        experiment_type="historical_backtest",
        external_run_id=None,
        training_run_id=None,
        training_round_index=None,
        report_path=None,
        artifact_paths=[],
        config_snapshot={},
        status=status,
        started_at=None,
        completed_at=None,
        created_at=NOW,
    )


def evidence() -> HypothesisEvidence:
    return HypothesisEvidence(
        id=5,
        hypothesis_id=2,
        experiment_id=4,
        evidence_type="metric_summary",
        direction=EvidenceDirection.CONTRADICTING,
        summary="failed",
        metrics={"objective": -1},
        artifact_path=None,
        content_hash="abc",
        observed_at=NOW,
        created_at=NOW,
    )


class FakeRepository:
    def __init__(self, current: Hypothesis | None = None) -> None:
        self.current = current or hypothesis()
        self.family = family()
        self.experiments: list[HypothesisExperiment] = []
        self.evidence: list[HypothesisEvidence] = []
        self.transitions: list[dict] = []
        self.created_experiment: dict | None = None
        self.added_evidence: dict | None = None

    def get_hypothesis(self, key):
        return self.current

    def list_families(self, **kwargs):
        return [self.family]

    def list_experiments(self, key):
        return self.experiments

    def list_evidence(self, key):
        return self.evidence

    def transition_hypothesis(self, **kwargs):
        self.transitions.append(kwargs)
        self.current = replace(self.current, status=kwargs["new_status"])
        return self.current

    def create_experiment(self, **kwargs):
        self.created_experiment = kwargs
        return experiment()

    def add_evidence(self, **kwargs):
        self.added_evidence = kwargs
        return evidence()


def service(repository: FakeRepository, root: Path | None = None) -> ResearchHypothesisService:
    return ResearchHypothesisService(repository, repository_root=root)  # type: ignore[arg-type]


def test_preregister_requires_every_falsifiability_field() -> None:
    repository = FakeRepository(hypothesis(statement=""))

    with pytest.raises(PreregistrationError, match="statement"):
        service(repository).preregister("hypothesis-1", decided_by="human:test")

    assert repository.transitions == []


def test_preregister_records_decision_transition() -> None:
    repository = FakeRepository()

    result = service(repository).preregister("hypothesis-1", decided_by="human:test")

    assert result.status == HypothesisStatus.PREREGISTERED
    assert repository.transitions[0]["decision_code"] == "preregistration_completed"


def test_start_requires_planned_experiment_and_open_family() -> None:
    repository = FakeRepository(hypothesis(HypothesisStatus.PREREGISTERED))
    with pytest.raises(RegistryConflictError, match="planned experiment"):
        service(repository).start("hypothesis-1", decided_by="human:test")

    repository.experiments = [experiment()]
    repository.family = family(HypothesisFamilyStatus.REJECTED)
    with pytest.raises(RegistryConflictError, match="not active"):
        service(repository).start("hypothesis-1", decided_by="human:test")

    repository.family = family()
    assert service(repository).start("hypothesis-1", decided_by="human:test").status == HypothesisStatus.RUNNING


def test_completion_requires_evidence_and_ended_experiments() -> None:
    repository = FakeRepository(hypothesis(HypothesisStatus.RUNNING))
    with pytest.raises(RegistryConflictError, match="evidence"):
        service(repository).complete_with_decision(
            "hypothesis-1",
            new_status=HypothesisStatus.INCONCLUSIVE,
            decision_code="no_signal",
            summary="no signal",
            decided_by="human:test",
            reason={"code": "no_signal"},
            evidence_ids=[5],
        )

    repository.evidence = [evidence()]
    repository.experiments = [experiment(ExperimentStatus.RUNNING)]
    with pytest.raises(RegistryConflictError, match="must end"):
        service(repository).complete_with_decision(
            "hypothesis-1",
            new_status=HypothesisStatus.INCONCLUSIVE,
            decision_code="no_signal",
            summary="no signal",
            decided_by="human:test",
            reason={"code": "no_signal"},
            evidence_ids=[5],
        )


def test_parameter_rejection_requires_auditable_boundary() -> None:
    repository = FakeRepository(hypothesis(HypothesisStatus.RUNNING))
    repository.evidence = [evidence()]
    repository.experiments = [experiment(ExperimentStatus.COMPLETED)]
    reason = {
        "parameter_region": {"depth": [1, 3]},
        "failed_metrics": {"objective": -1},
        "data_boundary": {"as_of": "2026079"},
        "prohibited_parameter_only_changes": PROHIBITED,
    }

    result = service(repository).reject(
        "hypothesis-1",
        decision_code="parameter_region_failed",
        summary="parameter region rejected",
        decided_by="human:test",
        reason=reason,
        evidence_ids=[5],
        rejection_scope=RejectionScope.PARAMETER_REGION,
        reopen_condition="new feature family",
    )

    assert result.status == HypothesisStatus.REJECTED
    assert repository.transitions[-1]["rejection_scope"] == RejectionScope.PARAMETER_REGION


def test_report_reference_is_relative_existing_and_hashable(tmp_path: Path) -> None:
    report = tmp_path / "docs/experiments/report.md"
    report.parent.mkdir(parents=True)
    report.write_text("evidence")
    repository = FakeRepository()

    service(repository, tmp_path).register_experiment(
        hypothesis_key="hypothesis-1",
        experiment_key="experiment-1",
        experiment_type="historical",
        report_path=str(report),
        compute_hashes=True,
    )

    assert repository.created_experiment is not None
    assert repository.created_experiment["report_path"] == "docs/experiments/report.md"
    assert len(repository.created_experiment["metadata"]["content_hashes"]["docs/experiments/report.md"]) == 64


def test_missing_or_out_of_scope_reference_is_rejected(tmp_path: Path) -> None:
    repository = FakeRepository()
    with pytest.raises(ArtifactReferenceError, match="does not exist"):
        service(repository, tmp_path).register_experiment(
            hypothesis_key="hypothesis-1",
            experiment_key="experiment-1",
            experiment_type="historical",
            report_path="docs/experiments/missing.md",
        )
    with pytest.raises(ArtifactReferenceError, match="must be under"):
        service(repository, tmp_path).register_experiment(
            hypothesis_key="hypothesis-1",
            experiment_key="experiment-1",
            experiment_type="historical",
            report_path="README.md",
        )
