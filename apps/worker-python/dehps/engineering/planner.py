from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from dehps.engineering.change_plan import ChangePlanner
from dehps.engineering.code_graph import CodeGraphBuilder
from dehps.engineering.contracts import (
    EngineeringContext,
    ImplementationContract,
    LocatedComponent,
)
from dehps.engineering.locator import RepositoryLocator
from dehps.engineering.tests import EngineeringTestPlanner
from dehps.research_planning.implementation_contract import EXPERIMENT_KEY_BY_STAGE
from dehps.research_planning.models import (
    ArtifactContract,
    EvidenceContract,
    ExperimentPlan,
    ExperimentStage,
    ImplementationStep,
    ResourceBudget,
)
from dehps.research_planning.repository import ExperimentPlanningRepository


def plan_from_payload(payload: dict[str, Any]) -> ExperimentPlan:
    data = dict(payload)
    data["implementation_steps"] = tuple(
        ImplementationStep(**item) for item in data.get("implementation_steps", ())
    )
    data["experiment_stages"] = tuple(
        ExperimentStage(**item) for item in data.get("experiment_stages", ())
    )
    data["resource_budget"] = ResourceBudget(**data["resource_budget"])
    data["artifact_contract"] = ArtifactContract(**data["artifact_contract"])
    data["evidence_contract"] = EvidenceContract(**data["evidence_contract"])
    for key in ("invariants", "self_deception_controls", "stop_conditions"):
        data[key] = tuple(data.get(key, ()))
    return ExperimentPlan(**data)


class EngineeringPlanner:
    def __init__(
        self,
        *,
        repository_root: Path | None = None,
        planning_repository: ExperimentPlanningRepository | None = None,
        code_graph_builder: CodeGraphBuilder | None = None,
        locator: RepositoryLocator | None = None,
        change_planner: ChangePlanner | None = None,
        test_planner: EngineeringTestPlanner | None = None,
    ) -> None:
        self.root = (repository_root or Path(__file__).resolve().parents[4]).resolve()
        self.planning_repository = planning_repository or ExperimentPlanningRepository()
        self.code_graph_builder = code_graph_builder or CodeGraphBuilder(self.root)
        self.locator = locator
        self.change_planner = change_planner or ChangePlanner()
        self.test_planner = test_planner or EngineeringTestPlanner()

    def load_plan(self, plan_key: str | None = None) -> ExperimentPlan:
        if plan_key:
            payload = self.planning_repository.get_materialized_plan_payload(plan_key)
        else:
            plans = self.planning_repository.list_plans(limit=1)
            if not plans:
                raise ValueError("no materialized Experiment Plan is available")
            payload = dict(plans[0]["plan"])
        return plan_from_payload(payload)

    def build_context(self, plan: ExperimentPlan) -> EngineeringContext:
        code_graph = self.code_graph_builder.build()
        locator = self.locator or RepositoryLocator(repository_root=self.root, code_graph=code_graph)
        features, mechanisms = locator.context_catalogs()
        existing_tests = tuple(file.path for file in code_graph.test_files)
        return EngineeringContext(
            plan_key=plan.plan_key,
            plan_fingerprint=plan.plan_fingerprint,
            hypothesis_key=plan.hypothesis_key,
            mechanism=plan.mechanism,
            repository_root=self.root.as_posix(),
            feature_catalog=features,
            mechanism_catalog=mechanisms,
            code_graph=code_graph,
            existing_tests=existing_tests,
            current_interfaces=code_graph.interfaces,
        )

    def locate(self, plan: ExperimentPlan) -> tuple[LocatedComponent, ...]:
        code_graph = self.code_graph_builder.build()
        locator = self.locator or RepositoryLocator(repository_root=self.root, code_graph=code_graph)
        return locator.locate(plan)

    def build_contract(self, plan: ExperimentPlan) -> ImplementationContract:
        context = self.build_context(plan)
        located = self.locate(plan)
        change_plan = self.change_planner.build(plan, located)
        test_plan = self.test_planner.build(plan, mechanism=plan.mechanism)
        modules_to_modify = tuple(
            item.path for item in change_plan.items if item.action.value == "modify"
        )
        files_to_add = tuple(item.path for item in change_plan.items if item.action.value == "add")
        tests_to_add = tuple(item.path for item in test_plan.items)
        target_experiment_key = EXPERIMENT_KEY_BY_STAGE.get("feasibility", f"{plan.mechanism}_feasibility_v1")
        return ImplementationContract(
            schema_version="autonomous-engineering-v1",
            plan_key=plan.plan_key,
            plan_fingerprint=plan.plan_fingerprint,
            hypothesis_key=plan.hypothesis_key,
            mechanism=plan.mechanism,
            target_experiment_key=target_experiment_key,
            context_fingerprint=context.fingerprint,
            located_components=located,
            modules_to_modify=modules_to_modify,
            files_to_add=files_to_add,
            interfaces_to_add=(
                "Engineering implementation result must satisfy dehps.agents.handoffs.validate_engineering_result",
            ),
            tests_to_add=tests_to_add,
            forbidden_paths=change_plan.forbidden_paths,
            compatibility_requirements=(
                "existing CLI commands remain compatible",
                "existing artifact schemas remain backward compatible",
                "no production training, Objective, Promotion, Registry, or Evidence mutation",
            ),
            change_plan=change_plan,
            test_plan=test_plan,
            non_goals=(
                "do not modify production training",
                "do not modify Objective Policy",
                "do not modify Promotion Gate",
                "do not execute Experiment",
                "do not write Evidence",
                "do not update Registry",
                "do not create commits from this planner",
            ),
        )


def context_summary(context: EngineeringContext) -> dict[str, Any]:
    return {
        "plan_key": context.plan_key,
        "plan_fingerprint": context.plan_fingerprint,
        "hypothesis_key": context.hypothesis_key,
        "mechanism": context.mechanism,
        "context_fingerprint": context.fingerprint,
        "source_files": len(context.code_graph.source_files),
        "test_files": len(context.code_graph.test_files),
        "feature_catalog": len(context.feature_catalog),
        "mechanism_catalog": len(context.mechanism_catalog),
        "interfaces": len(context.current_interfaces),
    }
