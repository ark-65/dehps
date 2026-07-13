from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
import json
from typing import Any, ContextManager

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.db import get_connection
from dehps.research.errors import RegistryConflictError, RegistryNotFoundError
from dehps.research.models import Hypothesis, HypothesisExperiment
from dehps.research.repository import HypothesisRepository
from dehps.research.service import ResearchHypothesisService
from dehps.research.status import ExperimentStatus, HypothesisFamilyStatus, HypothesisStatus
from dehps.research_planning.implementation_contract import EXPERIMENT_KEY_BY_STAGE
from dehps.research_planning.models import ExperimentPlan, MaterializationResult


ConnectionFactory = Callable[[], ContextManager[Connection[Any]]]


class ExperimentPlanningRepository:
    def __init__(
        self,
        connection_factory: ConnectionFactory = get_connection,
        hypothesis_repository: HypothesisRepository | None = None,
        hypothesis_service: ResearchHypothesisService | None = None,
    ) -> None:
        self.connection_factory = connection_factory
        self.hypothesis_repository = hypothesis_repository or HypothesisRepository(connection_factory)
        self.hypothesis_service = hypothesis_service or ResearchHypothesisService(
            self.hypothesis_repository
        )

    def ensure_schema(self) -> None:
        self.hypothesis_repository.ensure_schema()

    def list_plans(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT h.hypothesis_key, h.status AS hypothesis_status, h.metadata_json
                FROM research_hypotheses h
                WHERE h.metadata_json ? 'experiment_plan'
                ORDER BY h.created_at DESC, h.id DESC LIMIT %s OFFSET %s
                """,
                (limit, offset),
            ).fetchall()
        return [self._plan_record(dict(row)) for row in rows]

    def get_plan_record(self, plan_key: str) -> dict[str, Any]:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                """
                SELECT h.hypothesis_key, h.status AS hypothesis_status, h.metadata_json
                FROM research_hypotheses h
                WHERE h.metadata_json->'experiment_plan'->>'plan_key' = %s
                   OR h.hypothesis_key = %s
                ORDER BY h.created_at DESC, h.id DESC LIMIT 1
                """,
                (plan_key, plan_key),
            ).fetchone()
        if row is None:
            raise RegistryNotFoundError(f"experiment plan not found: {plan_key}")
        return self._plan_record(dict(row))

    def get_materialized_plan_payload(self, plan_key: str) -> dict[str, Any]:
        return dict(self.get_plan_record(plan_key)["plan"])

    def list_plan_requests(self, plan_key: str) -> list[dict[str, Any]]:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT request_key, request_type, status, requested_by_role, requested_by,
                       title, summary, payload_json, metadata_json, submitted_at, created_at
                FROM agent_requests
                WHERE payload_json->>'experiment_plan_key' = %s
                   OR metadata_json->>'experiment_plan_key' = %s
                ORDER BY created_at, id
                """,
                (plan_key, plan_key),
            ).fetchall()
        return [
            {
                "request_key": str(row["request_key"]),
                "request_type": str(row["request_type"]),
                "status": str(row["status"]),
                "requested_by_role": str(row["requested_by_role"]),
                "requested_by": str(row["requested_by"]),
                "title": str(row["title"]),
                "summary": str(row["summary"]),
                "payload": dict(row.get("payload_json") or {}),
                "metadata": dict(row.get("metadata_json") or {}),
                "submitted_at": None
                if row.get("submitted_at") is None
                else row["submitted_at"].isoformat(),
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]

    def materialize(
        self,
        plan: ExperimentPlan,
        *,
        proposal_request_key: str,
        reviewer_approval: dict[str, Any],
    ) -> MaterializationResult:
        self.ensure_schema()
        self._ensure_family(plan)
        hypothesis, preregistered = self._ensure_hypothesis(
            plan,
            proposal_request_key=proposal_request_key,
            reviewer_approval=reviewer_approval,
        )
        experiments = self._ensure_experiments(plan, hypothesis_key=hypothesis.hypothesis_key)
        return MaterializationResult(
            plan_key=plan.plan_key,
            hypothesis_key=hypothesis.hypothesis_key,
            hypothesis_status=hypothesis.status.value,
            experiment_keys=tuple(item.experiment_key for item in experiments),
            preregistered=preregistered,
            execution_started=False,
            evidence_created=False,
        )

    def _ensure_family(self, plan: ExperimentPlan) -> None:
        try:
            family = self.hypothesis_repository.get_family(plan.family_key)
        except RegistryNotFoundError:
            self.hypothesis_repository.create_family(
                family_key=plan.family_key,
                title=f"{plan.mechanism} family",
                mechanism=plan.mechanism,
                description=plan.scientific_question,
                status=HypothesisFamilyStatus.ACTIVE,
                metadata={
                    "source": "autonomous_experiment_planner",
                    "experiment_plan_key": plan.plan_key,
                    "plan_fingerprint": plan.plan_fingerprint,
                },
            )
            return
        if family.mechanism != plan.mechanism:
            raise RegistryConflictError("existing family mechanism does not match experiment plan")
        if family.status in {HypothesisFamilyStatus.REJECTED, HypothesisFamilyStatus.EXHAUSTED}:
            raise RegistryConflictError(f"family is closed: {plan.family_key}")

    def _ensure_hypothesis(
        self,
        plan: ExperimentPlan,
        *,
        proposal_request_key: str,
        reviewer_approval: dict[str, Any],
    ) -> tuple[Hypothesis, bool]:
        metadata = {
            "experiment_plan": asdict(plan),
            "experiment_plan_key": plan.plan_key,
            "plan_fingerprint": plan.plan_fingerprint,
            "proposal_request_key": proposal_request_key,
            "reviewer_approval": dict(reviewer_approval),
            "input_boundary": plan.input_boundary,
            "feature_contract": plan.feature_contract,
            "model_contract": plan.model_contract,
            "validation_protocol": plan.validation_protocol,
        }
        try:
            hypothesis = self.hypothesis_repository.get_hypothesis(plan.hypothesis_key)
        except RegistryNotFoundError:
            hypothesis = self.hypothesis_repository.create_hypothesis(
                hypothesis_key=plan.hypothesis_key,
                family_key=plan.family_key,
                title=f"Preregistered {plan.mechanism} experiment",
                mechanism=plan.mechanism,
                statement=plan.scientific_question,
                null_hypothesis=plan.null_hypothesis,
                minimal_non_null=plan.minimal_non_null,
                invariants=plan.invariants,
                baseline_definition=plan.baseline_contract,
                metric_definition=plan.metric_contract,
                failure_condition=plan.failure_condition,
                self_deception_risk=plan.self_deception_controls,
                metadata=metadata,
            )
        else:
            existing_fingerprint = hypothesis.metadata.get("plan_fingerprint")
            if existing_fingerprint != plan.plan_fingerprint:
                raise RegistryConflictError("existing hypothesis has a different plan fingerprint")
        preregistered = False
        if hypothesis.status == HypothesisStatus.PROPOSED:
            hypothesis = self.hypothesis_service.preregister(
                plan.hypothesis_key,
                decided_by=str(reviewer_approval.get("decided_by") or "reviewer:unknown"),
                decision_code="autonomous_plan_preregistered",
            )
            preregistered = True
        elif hypothesis.status != HypothesisStatus.PREREGISTERED:
            raise RegistryConflictError(
                f"hypothesis must be proposed or preregistered; found {hypothesis.status.value}"
            )
        return hypothesis, preregistered

    def _ensure_experiments(
        self,
        plan: ExperimentPlan,
        *,
        hypothesis_key: str,
    ) -> tuple[HypothesisExperiment, ...]:
        existing = {
            experiment.experiment_key: experiment
            for experiment in self.hypothesis_repository.list_experiments(hypothesis_key)
        }
        experiments: list[HypothesisExperiment] = []
        stages = {stage.key: stage for stage in plan.experiment_stages}
        for stage_key, experiment_key in EXPERIMENT_KEY_BY_STAGE.items():
            stage = stages[stage_key]
            if experiment_key in existing:
                experiment = existing[experiment_key]
                if experiment.metadata.get("plan_fingerprint") != plan.plan_fingerprint:
                    raise RegistryConflictError(
                        f"experiment exists with a different plan: {experiment_key}"
                    )
                experiments.append(experiment)
                continue
            experiments.append(
                self.hypothesis_repository.create_experiment(
                    hypothesis_key=hypothesis_key,
                    experiment_key=experiment_key,
                    experiment_type=stage.key,
                    artifact_paths=stage.artifact_paths,
                    config_snapshot={
                        "experiment_plan_key": plan.plan_key,
                        "stage_key": stage.key,
                        "plan_fingerprint": plan.plan_fingerprint,
                        "status": ExperimentStatus.PLANNED.value,
                    },
                    metadata={
                        "experiment_plan_key": plan.plan_key,
                        "plan_fingerprint": plan.plan_fingerprint,
                        "proposal_key": plan.proposal_key,
                        "stage": asdict(stage),
                    },
                )
            )
        return tuple(experiments)

    @staticmethod
    def _plan_record(row: dict[str, Any]) -> dict[str, Any]:
        metadata = dict(row.get("metadata_json") or {})
        plan = dict(metadata.get("experiment_plan") or {})
        if not plan:
            raise RegistryConflictError("hypothesis metadata is missing experiment_plan")
        return {
            "plan_key": str(plan.get("plan_key") or ""),
            "plan_version": str(plan.get("plan_version") or ""),
            "proposal_key": str(plan.get("proposal_key") or ""),
            "hypothesis_key": str(row["hypothesis_key"]),
            "family_key": str(plan.get("family_key") or ""),
            "mechanism": str(plan.get("mechanism") or ""),
            "plan_fingerprint": str(plan.get("plan_fingerprint") or ""),
            "proposal_fingerprint": str(plan.get("proposal_fingerprint") or ""),
            "hypothesis_status": str(row["hypothesis_status"]),
            "plan": plan,
            "metadata": json.loads(json.dumps(metadata, sort_keys=True, default=str)),
        }
