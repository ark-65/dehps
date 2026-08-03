"""M4 information-theory research contract and immutable preregistration.

Public exports are resolved lazily to keep capability imports isolated from
progress projection and other control-plane orchestration.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_ARTIFACT_CONTRACTS = "dehps.research_os.information_theory.artifact_contracts"
_DIGEST = "dehps.research_os.information_theory.digest"
_ENUMS = "dehps.research_os.information_theory.enums"
_PREREGISTRATION = "dehps.research_os.information_theory.preregistration"
_PROGRESS = "dehps.research_os.information_theory.progress"
_SEEDS = "dehps.research_os.information_theory.seed_domains"
_VALIDATION = "dehps.research_os.information_theory.validation"

_EXPORTS = {
    "ARTIFACT_IDENTITY_FIELDS": (_ARTIFACT_CONTRACTS, "ARTIFACT_IDENTITY_FIELDS"),
    "ArtifactContractViolation": (_ARTIFACT_CONTRACTS, "ArtifactContractViolation"),
    "validate_artifact_identity": (_ARTIFACT_CONTRACTS, "validate_artifact_identity"),
    "DECISION_POLICY_DIGEST_DOMAIN": (_DIGEST, "DECISION_POLICY_DIGEST_DOMAIN"),
    "PREREGISTRATION_DIGEST_DOMAIN": (_DIGEST, "PREREGISTRATION_DIGEST_DOMAIN"),
    "decision_policy_digest": (_DIGEST, "decision_policy_digest"),
    "information_theory_contract_digest": (
        _DIGEST,
        "information_theory_contract_digest",
    ),
    "preregistration_digest": (_DIGEST, "preregistration_digest"),
    "DecisionState": (_ENUMS, "DecisionState"),
    "PreregistrationStatus": (_ENUMS, "PreregistrationStatus"),
    "CANONICAL_PREREGISTRATION_RELATIVE_PATH": (
        _PREREGISTRATION,
        "CANONICAL_PREREGISTRATION_RELATIVE_PATH",
    ),
    "FrozenPreregistration": (_PREREGISTRATION, "FrozenPreregistration"),
    "PhaseGateError": (_PREREGISTRATION, "PhaseGateError"),
    "freeze_preregistration": (_PREREGISTRATION, "freeze_preregistration"),
    "load_preregistration": (_PREREGISTRATION, "load_preregistration"),
    "require_formal_run_gate": (_PREREGISTRATION, "require_formal_run_gate"),
    "show_preregistration": (_PREREGISTRATION, "show_preregistration"),
    "LEGACY_GOAL_KEY": (_PROGRESS, "LEGACY_GOAL_KEY"),
    "M4_CONTRACT_REPAIR_TASK_KEY": (_PROGRESS, "M4_CONTRACT_REPAIR_TASK_KEY"),
    "M4_FORWARD_EVENT_KEY": (_PROGRESS, "M4_FORWARD_EVENT_KEY"),
    "M4_GOAL_KEY": (_PROGRESS, "M4_GOAL_KEY"),
    "M4_MANIFEST_RELATIVE_PATH": (_PROGRESS, "M4_MANIFEST_RELATIVE_PATH"),
    "PHASE_TASK_KEYS": (_PROGRESS, "PHASE_TASK_KEYS"),
    "build_m4_status": (_PROGRESS, "build_m4_status"),
    "load_m4_manifest": (_PROGRESS, "load_m4_manifest"),
    "manifest_with_contract_repair_pending": (
        _PROGRESS,
        "manifest_with_contract_repair_pending",
    ),
    "manifest_with_external_event": (_PROGRESS, "manifest_with_external_event"),
    "M4_P2_SEED_DOMAINS": (_SEEDS, "M4_P2_SEED_DOMAINS"),
    "derive_m4_p2_seed": (_SEEDS, "derive_m4_p2_seed"),
    "InformationTheoryValidationError": (
        _VALIDATION,
        "InformationTheoryValidationError",
    ),
    "validate_decision_policy": (_VALIDATION, "validate_decision_policy"),
    "validate_p2_input_contract": (_VALIDATION, "validate_p2_input_contract"),
    "validate_preregistration": (_VALIDATION, "validate_preregistration"),
}

__all__ = [
    "ARTIFACT_IDENTITY_FIELDS",
    "CANONICAL_PREREGISTRATION_RELATIVE_PATH",
    "DECISION_POLICY_DIGEST_DOMAIN",
    "LEGACY_GOAL_KEY",
    "M4_CONTRACT_REPAIR_TASK_KEY",
    "M4_FORWARD_EVENT_KEY",
    "M4_GOAL_KEY",
    "M4_MANIFEST_RELATIVE_PATH",
    "M4_P2_SEED_DOMAINS",
    "PHASE_TASK_KEYS",
    "PREREGISTRATION_DIGEST_DOMAIN",
    "ArtifactContractViolation",
    "DecisionState",
    "FrozenPreregistration",
    "InformationTheoryValidationError",
    "PhaseGateError",
    "PreregistrationStatus",
    "build_m4_status",
    "decision_policy_digest",
    "derive_m4_p2_seed",
    "freeze_preregistration",
    "information_theory_contract_digest",
    "load_m4_manifest",
    "load_preregistration",
    "manifest_with_contract_repair_pending",
    "manifest_with_external_event",
    "preregistration_digest",
    "require_formal_run_gate",
    "show_preregistration",
    "validate_artifact_identity",
    "validate_decision_policy",
    "validate_p2_input_contract",
    "validate_preregistration",
]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(target[0]), target[1])
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
