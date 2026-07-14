from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any


ROUND27_SCHEMA_VERSION = "autonomous-engineering-v1"


class ChangeAction(str, Enum):
    ADD = "add"
    MODIFY = "modify"
    DELETE = "delete"
    REUSE = "reuse"


class TestKind(str, Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    REGRESSION = "regression"
    SMOKE = "smoke"


@dataclass(frozen=True)
class CodeSymbol:
    name: str
    kind: str
    line: int


@dataclass(frozen=True)
class CodeFile:
    path: str
    module: str
    kind: str
    symbols: tuple[CodeSymbol, ...] = ()


@dataclass(frozen=True)
class CodeGraph:
    root: str
    source_files: tuple[CodeFile, ...]
    test_files: tuple[CodeFile, ...]
    interfaces: tuple[str, ...]


@dataclass(frozen=True)
class LocatedComponent:
    kind: str
    key: str
    path: str
    exists: bool
    reason: str
    symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class EngineeringContext:
    plan_key: str
    plan_fingerprint: str
    hypothesis_key: str
    mechanism: str
    repository_root: str
    feature_catalog: tuple[dict[str, Any], ...]
    mechanism_catalog: tuple[dict[str, Any], ...]
    code_graph: CodeGraph
    existing_tests: tuple[str, ...]
    current_interfaces: tuple[str, ...]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def fingerprint(self) -> str:
        return stable_hash(
            {
                "schema": ROUND27_SCHEMA_VERSION,
                "plan_key": self.plan_key,
                "plan_fingerprint": self.plan_fingerprint,
                "source_files": [item.path for item in self.code_graph.source_files],
                "test_files": list(self.existing_tests),
                "interfaces": list(self.current_interfaces),
            }
        )


@dataclass(frozen=True)
class ChangePlanItem:
    action: ChangeAction
    path: str
    purpose: str
    risk: str
    dependencies: tuple[str, ...] = ()
    compatibility_requirements: tuple[str, ...] = ()


@dataclass(frozen=True)
class EngineeringChangePlan:
    plan_key: str
    items: tuple[ChangePlanItem, ...]
    forbidden_paths: tuple[str, ...]
    production_impact: str


@dataclass(frozen=True)
class TestPlanItem:
    kind: TestKind
    path: str
    purpose: str
    assertions: tuple[str, ...]
    covers: tuple[str, ...]


@dataclass(frozen=True)
class EngineeringTestPlan:
    plan_key: str
    items: tuple[TestPlanItem, ...]
    commands: tuple[str, ...]


@dataclass(frozen=True)
class ImplementationContract:
    schema_version: str
    plan_key: str
    plan_fingerprint: str
    hypothesis_key: str
    mechanism: str
    target_experiment_key: str
    context_fingerprint: str
    located_components: tuple[LocatedComponent, ...]
    modules_to_modify: tuple[str, ...]
    files_to_add: tuple[str, ...]
    interfaces_to_add: tuple[str, ...]
    tests_to_add: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    compatibility_requirements: tuple[str, ...]
    change_plan: EngineeringChangePlan
    test_plan: EngineeringTestPlan
    non_goals: tuple[str, ...]
    production_impact: str = "none"
    objective_policy_change_allowed: bool = False
    promotion_change_allowed: bool = False
    registry_update_allowed: bool = False
    experiment_execution_allowed: bool = False
    evidence_write_allowed: bool = False

    @property
    def contract_hash(self) -> str:
        return stable_hash(asdict(self))

    def payload(self) -> dict[str, Any]:
        return {**jsonable(self), "contract_hash": self.contract_hash}


@dataclass(frozen=True)
class ContractValidationCheck:
    key: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class ContractValidationReport:
    valid: bool
    checks: tuple[ContractValidationCheck, ...]
    failure_reasons: tuple[str, ...]


def jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def stable_hash(value: Any) -> str:
    payload = json.dumps(jsonable(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()
