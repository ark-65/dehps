from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from experiment_plan_fixtures import APPROVAL, ranking_plan
from dehps.research.errors import RegistryNotFoundError
from dehps.research.models import Hypothesis, HypothesisExperiment, HypothesisFamily
from dehps.research.status import ExperimentStatus, HypothesisFamilyStatus, HypothesisStatus, RejectionScope
from dehps.research_planning.repository import ExperimentPlanningRepository


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)


def family(plan) -> HypothesisFamily:
    return HypothesisFamily(
        id=1,
        family_key=plan.family_key,
        title="family",
        description="",
        mechanism=plan.mechanism,
        status=HypothesisFamilyStatus.ACTIVE,
        rejection_scope=RejectionScope.NONE,
        rejection_reason=None,
        reopen_condition=None,
        created_at=NOW,
        updated_at=NOW,
        resolved_at=None,
        metadata={},
    )


def hypothesis(plan, status=HypothesisStatus.PROPOSED) -> Hypothesis:
    return Hypothesis(
        id=2,
        hypothesis_key=plan.hypothesis_key,
        family_id=1,
        parent_hypothesis_id=None,
        title="hypothesis",
        statement=plan.scientific_question,
        mechanism=plan.mechanism,
        null_hypothesis=plan.null_hypothesis,
        minimal_non_null=plan.minimal_non_null,
        invariants=list(plan.invariants),
        baseline_definition=plan.baseline_contract,
        metric_definition=plan.metric_contract,
        failure_condition=plan.failure_condition,
        self_deception_risk=list(plan.self_deception_controls),
        status=status,
        rejection_scope=RejectionScope.NONE,
        rejection_reason=None,
        reopen_condition=None,
        created_at=NOW,
        updated_at=NOW,
        preregistered_at=None,
        started_at=None,
        resolved_at=None,
        metadata={"plan_fingerprint": plan.plan_fingerprint, "experiment_plan": {}},
    )


class FakeHypothesisRepository:
    def __init__(self) -> None:
        self.plan = ranking_plan()
        self.family_value = None
        self.hypothesis_value = None
        self.experiments: dict[str, HypothesisExperiment] = {}
        self.evidence_writes = 0

    def ensure_schema(self) -> None:
        return None

    def get_family(self, key):
        if self.family_value is None:
            raise RegistryNotFoundError("missing family")
        return self.family_value

    def create_family(self, **kwargs):
        self.family_value = family(self.plan)
        return self.family_value

    def get_hypothesis(self, key):
        if self.hypothesis_value is None:
            raise RegistryNotFoundError("missing hypothesis")
        return self.hypothesis_value

    def create_hypothesis(self, **kwargs):
        self.hypothesis_value = replace(
            hypothesis(self.plan),
            metadata={
                "plan_fingerprint": self.plan.plan_fingerprint,
                "experiment_plan": kwargs["metadata"]["experiment_plan"],
            },
        )
        return self.hypothesis_value

    def list_experiments(self, hypothesis_key):
        return list(self.experiments.values())

    def create_experiment(self, **kwargs):
        experiment = HypothesisExperiment(
            id=len(self.experiments) + 1,
            hypothesis_id=2,
            experiment_key=kwargs["experiment_key"],
            experiment_type=kwargs["experiment_type"],
            external_run_id=None,
            training_run_id=None,
            training_round_index=None,
            report_path=None,
            artifact_paths=list(kwargs["artifact_paths"]),
            config_snapshot=dict(kwargs["config_snapshot"]),
            status=ExperimentStatus.PLANNED,
            started_at=None,
            completed_at=None,
            created_at=NOW,
            metadata=dict(kwargs["metadata"]),
        )
        self.experiments[experiment.experiment_key] = experiment
        return experiment


class FakeHypothesisService:
    def __init__(self, repository: FakeHypothesisRepository) -> None:
        self.repository = repository

    def preregister(self, key, **kwargs):
        self.repository.hypothesis_value = replace(
            self.repository.hypothesis_value,
            status=HypothesisStatus.PREREGISTERED,
            preregistered_at=NOW,
        )
        return self.repository.hypothesis_value


def test_materialization_creates_preregistered_hypothesis_and_four_planned_experiments() -> None:
    plan = ranking_plan()
    fake = FakeHypothesisRepository()
    repository = ExperimentPlanningRepository(
        hypothesis_repository=fake,  # type: ignore[arg-type]
        hypothesis_service=FakeHypothesisService(fake),  # type: ignore[arg-type]
    )

    result = repository.materialize(
        plan,
        proposal_request_key="research-proposal-1",
        reviewer_approval=APPROVAL,
    )

    assert result.hypothesis_status == "preregistered"
    assert result.preregistered is True
    assert result.execution_started is False
    assert result.evidence_created is False
    assert result.experiment_keys == (
        "ranking_disagreement_feasibility_v1",
        "ranking_disagreement_historical_search_v1",
        "ranking_disagreement_frozen_validation_v1",
        "ranking_disagreement_forward_validation_v1",
    )
    assert all(item.status == ExperimentStatus.PLANNED for item in fake.experiments.values())
    assert fake.evidence_writes == 0
