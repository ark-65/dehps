from __future__ import annotations

from typing import Any

from dehps.engineering.contracts import ImplementationContract
from dehps.engineering.planner import EngineeringPlanner, context_summary
from dehps.engineering.validator import ImplementationValidator


class AutonomousEngineeringService:
    def __init__(
        self,
        *,
        planner: EngineeringPlanner | None = None,
        validator: ImplementationValidator | None = None,
    ) -> None:
        self.planner = planner or EngineeringPlanner()
        self.validator = validator or ImplementationValidator()

    def graph(self, *, plan_key: str | None = None) -> dict[str, Any]:
        plan = self.planner.load_plan(plan_key)
        context = self.planner.build_context(plan)
        return {
            "context": context_summary(context),
            "source_files": context.code_graph.source_files,
            "test_files": context.code_graph.test_files,
            "interfaces": context.current_interfaces,
            "writes": [],
        }

    def locate(self, *, plan_key: str | None = None) -> dict[str, Any]:
        plan = self.planner.load_plan(plan_key)
        located = self.planner.locate(plan)
        return {
            "plan_key": plan.plan_key,
            "plan_fingerprint": plan.plan_fingerprint,
            "mechanism": plan.mechanism,
            "located_components": located,
            "writes": [],
        }

    def contract(self, *, plan_key: str | None = None) -> dict[str, Any]:
        contract = self._contract(plan_key)
        report = self.validator.validate(contract)
        return {
            "contract": contract,
            "contract_hash": contract.contract_hash,
            "validation": report,
            "writes": [],
        }

    def plan(self, *, plan_key: str | None = None) -> dict[str, Any]:
        contract = self._contract(plan_key)
        report = self.validator.validate(contract)
        return {
            "implementation_plan": {
                "contract": contract,
                "change_plan": contract.change_plan,
                "test_plan": contract.test_plan,
                "located_components": contract.located_components,
            },
            "validation": report,
            "writes": [],
        }

    def validate(self, *, plan_key: str | None = None) -> dict[str, Any]:
        contract = self._contract(plan_key)
        return {
            "plan_key": contract.plan_key,
            "contract_hash": contract.contract_hash,
            "validation": self.validator.validate(contract),
            "writes": [],
        }

    def _contract(self, plan_key: str | None) -> ImplementationContract:
        plan = self.planner.load_plan(plan_key)
        return self.planner.build_contract(plan)
