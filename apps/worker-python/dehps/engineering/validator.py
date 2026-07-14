from __future__ import annotations

from dehps.engineering.contracts import (
    ContractValidationCheck,
    ContractValidationReport,
    ImplementationContract,
    TestKind,
)


FORBIDDEN_SUBSTRINGS = (
    "training/production_runtime.py",
    "training/supervisor.py",
    "evaluation/objective_policy.py",
    "evaluation/promotion.py",
    "research/repository.py",
    "research/service.py",
    "research_evidence/",
    "infra/",
    "data/output/",
    "runtime/",
)


class ImplementationValidator:
    def validate(self, contract: ImplementationContract) -> ContractValidationReport:
        checks = (
            self._check(
                "identity",
                bool(contract.plan_key and contract.plan_fingerprint and contract.hypothesis_key),
                "contract records plan, fingerprint, and hypothesis identity",
            ),
            self._check(
                "located_components",
                len(contract.located_components) >= 4 and any(item.exists for item in contract.located_components),
                "contract locates existing repository components instead of reimplementing blindly",
            ),
            self._check(
                "change_plan",
                bool(contract.change_plan.items),
                "contract includes add/modify/reuse change plan items",
            ),
            self._check(
                "test_plan_complete",
                {item.kind for item in contract.test_plan.items}
                == {TestKind.UNIT, TestKind.INTEGRATION, TestKind.REGRESSION, TestKind.SMOKE},
                "contract includes unit, integration, regression, and smoke tests",
            ),
            self._check(
                "forbidden_paths_declared",
                bool(contract.forbidden_paths),
                "contract declares forbidden paths and runtime boundaries",
            ),
            self._check(
                "forbidden_paths_not_touched",
                not self._touches_forbidden(contract),
                "contract does not plan modifications in forbidden paths",
            ),
            self._check(
                "production_impact_none",
                contract.production_impact == "none",
                "contract has no production impact",
            ),
            self._check(
                "research_boundaries",
                not any(
                    (
                        contract.objective_policy_change_allowed,
                        contract.promotion_change_allowed,
                        contract.registry_update_allowed,
                        contract.experiment_execution_allowed,
                        contract.evidence_write_allowed,
                    )
                ),
                "contract cannot change Objective, Promotion, Registry, execute Experiment, or write Evidence",
            ),
            self._check(
                "non_goals",
                {
                    "do not execute Experiment",
                    "do not write Evidence",
                    "do not update Registry",
                }.issubset(set(contract.non_goals)),
                "contract records critical non-goals",
            ),
        )
        failures = tuple(check.reason for check in checks if not check.passed)
        return ContractValidationReport(valid=not failures, checks=checks, failure_reasons=failures)

    @staticmethod
    def _check(key: str, passed: bool, reason: str) -> ContractValidationCheck:
        return ContractValidationCheck(key=key, passed=bool(passed), reason=reason)

    @staticmethod
    def _touches_forbidden(contract: ImplementationContract) -> bool:
        planned = (
            *contract.modules_to_modify,
            *contract.files_to_add,
            *(item.path for item in contract.change_plan.items),
        )
        return any(
            any(fragment in path for fragment in FORBIDDEN_SUBSTRINGS)
            for path in planned
        )
