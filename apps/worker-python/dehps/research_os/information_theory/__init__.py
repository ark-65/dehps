"""M4 information-theory research contract and immutable preregistration."""

from .artifact_contracts import (
    ARTIFACT_IDENTITY_FIELDS,
    ArtifactContractViolation,
    validate_artifact_identity,
)
from .digest import (
    DECISION_POLICY_DIGEST_DOMAIN,
    PREREGISTRATION_DIGEST_DOMAIN,
    decision_policy_digest,
    information_theory_contract_digest,
    preregistration_digest,
)
from .enums import DecisionState, PreregistrationStatus
from .preregistration import (
    CANONICAL_PREREGISTRATION_RELATIVE_PATH,
    FrozenPreregistration,
    PhaseGateError,
    freeze_preregistration,
    load_preregistration,
    require_formal_run_gate,
    show_preregistration,
)
from .progress import (
    LEGACY_GOAL_KEY,
    M4_FORWARD_EVENT_KEY,
    M4_GOAL_KEY,
    M4_MANIFEST_RELATIVE_PATH,
    PHASE_TASK_KEYS,
    build_m4_status,
    load_m4_manifest,
    manifest_with_external_event,
)
from .validation import (
    InformationTheoryValidationError,
    validate_decision_policy,
    validate_p2_input_contract,
    validate_preregistration,
)

__all__ = [
    "ARTIFACT_IDENTITY_FIELDS",
    "CANONICAL_PREREGISTRATION_RELATIVE_PATH",
    "DECISION_POLICY_DIGEST_DOMAIN",
    "LEGACY_GOAL_KEY",
    "M4_FORWARD_EVENT_KEY",
    "M4_GOAL_KEY",
    "M4_MANIFEST_RELATIVE_PATH",
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
    "freeze_preregistration",
    "information_theory_contract_digest",
    "load_m4_manifest",
    "load_preregistration",
    "manifest_with_external_event",
    "preregistration_digest",
    "require_formal_run_gate",
    "show_preregistration",
    "validate_artifact_identity",
    "validate_decision_policy",
    "validate_p2_input_contract",
    "validate_preregistration",
]
