from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from dehps.research_planning.fingerprint import canonical_json, stable_fingerprint


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class ImplementationStep:
    key: str
    order: int
    actor_role: str
    purpose: str
    required_interface: JsonObject
    acceptance_criteria: tuple[str, ...]
    non_goals: tuple[str, ...]


@dataclass(frozen=True)
class ExperimentStage:
    key: str
    order: int
    purpose: str
    input_window: JsonObject
    candidate_budget: int
    baseline_budget: int
    metrics: tuple[str, ...]
    entry_conditions: tuple[str, ...]
    success_conditions: tuple[str, ...]
    failure_conditions: tuple[str, ...]
    artifact_paths: tuple[str, ...]
    execution_environment: str
    status: str = "planned"


@dataclass(frozen=True)
class ResourceBudget:
    cpu_hours: float
    memory_gb: float
    timeout_seconds: int
    storage_mb: int
    candidate_budget_per_stage: JsonObject
    baseline_budget_per_stage: JsonObject
    production_access: bool = False


@dataclass(frozen=True)
class ArtifactContract:
    schema_version: str
    base_directory: str
    required_artifacts: tuple[str, ...]
    forbidden_artifacts: tuple[str, ...]
    retention_policy: str
    complete_stage_results_required: bool


@dataclass(frozen=True)
class EvidenceContract:
    evidence_type: str
    evidence_writes_allowed_during_planning: bool
    minimum_forward_issues: int
    required_result_fields: tuple[str, ...]
    decision_requires_reviewer: bool


@dataclass(frozen=True)
class ExperimentPlan:
    plan_key: str
    plan_version: str
    proposal_key: str
    hypothesis_key: str
    family_key: str
    mechanism: str
    scientific_question: str
    null_hypothesis: str
    minimal_non_null: str
    invariants: tuple[str, ...]
    input_boundary: JsonObject
    feature_contract: JsonObject
    model_contract: JsonObject
    baseline_contract: JsonObject
    metric_contract: JsonObject
    validation_protocol: JsonObject
    failure_condition: JsonObject
    self_deception_controls: tuple[str, ...]
    implementation_steps: tuple[ImplementationStep, ...]
    experiment_stages: tuple[ExperimentStage, ...]
    resource_budget: ResourceBudget
    artifact_contract: ArtifactContract
    evidence_contract: EvidenceContract
    stop_conditions: tuple[str, ...]
    proposal_fingerprint: str
    plan_fingerprint: str

    def canonical_json(self) -> str:
        return canonical_json(asdict(self))

    @property
    def recomputed_fingerprint(self) -> str:
        payload = asdict(self)
        payload["plan_fingerprint"] = ""
        return stable_fingerprint(payload)


@dataclass(frozen=True)
class ExperimentPlanValidationCheck:
    key: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class ExperimentPlanValidationReport:
    valid: bool
    checks: tuple[ExperimentPlanValidationCheck, ...]
    failure_reasons: tuple[str, ...]


@dataclass(frozen=True)
class MaterializationResult:
    plan_key: str
    hypothesis_key: str
    hypothesis_status: str
    experiment_keys: tuple[str, ...]
    preregistered: bool
    execution_started: bool
    evidence_created: bool
