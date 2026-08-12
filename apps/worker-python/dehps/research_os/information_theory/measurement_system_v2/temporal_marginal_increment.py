from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

from dehps.research_os.models import (
    M4V2BranchDecisionArtifact,
    M4V2BranchDecisionReplayArtifact,
    m4_v2_build_artifact_envelope,
    m4_v2_domain_digest,
    validate_m4_v2_artifact_envelope,
    validate_m4_v2_nested_schema,
)


class TemporalMarginalIncrementContractError(ValueError):
    """Raised when a frozen Temporal successor identity is not exact."""


MEASUREMENT_CONTRACT_KEY: Final = "M4_MEASUREMENT_CONTRACT_V2"
MEASUREMENT_CONTRACT_DIGEST: Final = (
    "a0a367c99d7646cadc162bd9ceb0d5d73481cd7c26656bf02b40a99d9180095b"
)
TEMPORAL_BRANCH_ID: Final = "TEMPORAL_MARGINAL_INCREMENT"
MARGINAL_BRANCH_ID: Final = "MARGINAL_STATIC"
MARGINAL_RAW_P_ARTIFACT_DIGEST: Final = (
    "bdb89dd183846e4124654b57021be9892158b2b1387a8ca08d476283e0e2ed87"
)
MARGINAL_RAW_P_REGISTRATION_DIGEST: Final = (
    "10216e732563a48ed3bd3852499c2ab4b980ca29ef3246c4cec20eb71879554a"
)
TEMPORAL_ESTIMAND_DIGEST: Final = (
    "f1bde59f8bb59bc4bb796df8ec5fe3f0a4ba723a6cc3828bb263e747cabd53b3"
)
TEMPORAL_MODEL_ID: Final = "EXPANDING_LEGAL_ONE_LAG_OVERLAP_TILT_MLE_V1"
PARENT_ESTIMATOR_ID: Final = "EXPANDING_LEGAL_MARGINAL_ALPHA_1"
SUPPORT_MODEL_ID: Final = (
    "TRANSITION_LOCAL_TEMPORAL_PARENT_ALIAS_THETA_ZERO_S2_900_V1"
)
REQUEST481_PREDECESSOR_JOINT_ESTIMATOR_ID: Final = (
    "EXPANDING_MARGINAL_ORTHOGONAL_IS4_RESIDUAL_TILT_MLE_V1"
)
SUCCESSOR_JOINT_ESTIMATOR_ID: Final = (
    "EXPANDING_MARGINAL_ORTHOGONAL_IS4_RESIDUAL_TILT_MLE_WITH_FIXED_NULL_"
    "TEMPORAL_WARMUP_V2"
)

DATASET_CONTENT_DIGEST: Final = (
    "8f7b7527d6ee95301b58002e594b0955b7e0f391421b8c438b87fc4f2507b106"
)
FOLD_MANIFEST_DIGEST: Final = (
    "5a68579161ad5528ee15b8b1ea3e314d6acb05203885a5514e5654da026e9ad7"
)
CHECKPOINT_ORDER_MANIFEST_DIGEST: Final = (
    "40b85566e977311438add76d301d9614050bfac7fa0de618c1f415299f8b88cd"
)
FIXTURE_SOURCE_DIGEST: Final = (
    "391acc6a04518389f841e94a640a14dcaf98bd2c36614d31a0e713446980b06d"
)
TEMPORAL_SYNTHETIC_ROOT_SEED_FULL_SHA256: Final = (
    "e29d5a88e74a1ebac8081066947b5c7b595b160602fc71934a3805157cb907f4"
)
WARMUP_REQUEST_PAYLOAD_DIGEST: Final = (
    "aa25843e43a4a88413ca8ef50d2b2dd7ce7c1bf9631b5033f563ae4c5633d1f8"
)

WARMUP_START: Final = 2
WARMUP_END: Final = 900
WARMUP_COUNT: Final = 899
EVALUATION_START: Final = 901
EVALUATION_END: Final = 3481
EVALUATION_COUNT: Final = 2581
COMPOSITE_START: Final = 2
COMPOSITE_END: Final = 3481
COMPOSITE_COUNT: Final = 3480
SYNTHETIC_CELL_COUNT: Final = 14
SYNTHETIC_REPLICATES_PER_CELL: Final = 512
SYNTHETIC_REPLICATE_COUNT: Final = 7168
SYNTHETIC_GENERATED_ISSUE_COUNT: Final = 15_920_128
SYNTHETIC_OUTER_EVALUATION_ISSUE_COUNT: Final = 9_468_928
SYNTHETIC_BOOTSTRAP_CHILD_COUNT: Final = 14_651_392
SYNTHETIC_WARMUP_ALIAS_POSITION_COUNT: Final = 6_444_032
HISTORICAL_CHILD_COUNT: Final = 16_000
SYNTHETIC_WARMUP_RNG_CALL_COUNT: Final = 0
SYNTHETIC_DGP_CHANGED_BY_WARMUP: Final = False
SYNTHETIC_BOOTSTRAP_SEED_MATERIAL_CHANGED_BY_WARMUP: Final = False
SYNTHETIC_WARMUP_COMPUTED_PER_BOOTSTRAP_CHILD: Final = False

POSITIVE_ZERO_FLOAT_HEX: Final = "0x0.0p+0"
POSITIVE_ZERO_IEEE754_BINARY64_BE_HEX: Final = "0000000000000000"
WARMUP_SEMANTIC_SCOPE: Final = "NON_EVIDENCE_JOINT_TRAINING_SUPPORT_ONLY"

TEMPORAL_DESIGN_TASK_KEY: Final = (
    "m4-v2-temporal-marginal-increment-historical-measurement-design"
)
TEMPORAL_DESIGN_CAPABILITY: Final = (
    "m4_v2_temporal_marginal_increment_historical_measurement_design"
)
TEMPORAL_DESIGN_COMPLETION_FACT: Final = f"{TEMPORAL_DESIGN_TASK_KEY}:FROZEN"
TEMPORAL_PREREGISTRATION_TASK_KEY: Final = (
    "m4-v2-temporal-marginal-increment-historical-measurement-preregistration"
)
TEMPORAL_PREREGISTRATION_CAPABILITY: Final = (
    "m4_v2_temporal_marginal_increment_historical_measurement_preregistration"
)
TEMPORAL_PREREGISTRATION_COMPLETION_FACT: Final = (
    f"{TEMPORAL_PREREGISTRATION_TASK_KEY}:FROZEN"
)
TEMPORAL_PRODUCER_TASK_KEY: Final = (
    "m4-v2-temporal-marginal-increment-historical-measurement-gate-compiler"
)
TEMPORAL_PRODUCER_CAPABILITY: Final = (
    "m4_v2_temporal_marginal_increment_historical_measurement_gate_compiler"
)
TEMPORAL_PRODUCER_COMPLETION_FACT: Final = f"{TEMPORAL_PRODUCER_TASK_KEY}:COMPLETE"
TEMPORAL_REPLAY_TASK_KEY: Final = (
    "m4-v2-temporal-marginal-increment-historical-branch-decision-replay"
)
TEMPORAL_REPLAY_CAPABILITY: Final = (
    "m4_v2_temporal_marginal_increment_historical_branch_decision_replay"
)
TEMPORAL_REPLAY_COMPLETION_FACT: Final = f"{TEMPORAL_REPLAY_TASK_KEY}:COMPLETE"
TEMPORAL_TERMINAL_FACT: Final = (
    "m4-v2-historical-branch-decision:M4_MEASUREMENT_CONTRACT_V2:"
    "TEMPORAL_MARGINAL_INCREMENT:TERMINAL"
)
TEMPORAL_REPLAY_FACT: Final = (
    "m4-v2-historical-branch-decision-replay:M4_MEASUREMENT_CONTRACT_V2:"
    "TEMPORAL_MARGINAL_INCREMENT:VERIFIED"
)

TEMPORAL_DESIGN_ARTIFACT: Final = "M4V2TemporalMarginalIncrementDesignArtifact"
TEMPORAL_PREREGISTRATION_ARTIFACT: Final = (
    "M4V2TemporalMarginalIncrementPreregistrationBundleArtifact"
)
TEMPORAL_HEALTH_ARTIFACT: Final = (
    "M4V2TemporalMarginalIncrementHealthAggregateArtifact"
)
TEMPORAL_HISTORICAL_ARTIFACT: Final = (
    "M4V2TemporalMarginalIncrementHistoricalAggregateArtifact"
)
TEMPORAL_CANDIDATE_ARTIFACT: Final = (
    "M4V2TemporalMarginalIncrementCandidateModelArtifact"
)
TEMPORAL_COMPLETION_ARTIFACT: Final = (
    "M4V2TemporalMarginalIncrementProducerCompletionArtifact"
)
TEMPORAL_FAILURE_ARTIFACT: Final = (
    "M4V2TemporalMarginalIncrementScientificFailureArtifact"
)
BRANCH_DECISION_ARTIFACT: Final = "M4V2BranchDecisionArtifact"
BRANCH_REPLAY_ARTIFACT: Final = "M4V2BranchDecisionReplayArtifact"
MAINLINE_EXECUTION_ARTIFACT: Final = "research_os_mainline_execution"

DECISION_PATHS: Final = frozenset(
    {
        "EVALUATED_COMPLETE",
        "PARENT_NOT_ACCEPTED",
        "IDENTITY_VALID_HEALTH_REPAIR",
        "IDENTITY_VALID_HEALTH_INVALID",
        "IDENTITY_VALID_HISTORICAL_REPAIR",
        "IDENTITY_VALID_HISTORICAL_INVALID",
    }
)

_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_EXECUTION_ID_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class TemporalRegistrationPlan:
    path: str
    task_key: str
    artifact_types_in_registration_order: tuple[str, ...]
    registration_count_including_mainline_execution: int
    full_four_task_registration_count: int

    @property
    def preceding_completion_artifact_types(self) -> tuple[str, ...]:
        if TEMPORAL_COMPLETION_ARTIFACT not in self.artifact_types_in_registration_order:
            return ()
        index = self.artifact_types_in_registration_order.index(
            TEMPORAL_COMPLETION_ARTIFACT
        )
        return self.artifact_types_in_registration_order[:index]


@dataclass(frozen=True)
class TemporalCheckpointPlan:
    transition_ordinal: int
    support_kind: str
    prefix_last_ordinal: int
    theta_fit_invoked: bool
    theta_root_existence_test_invoked: bool
    target_is_historical_evidence: bool


_REGISTRATION_ORDERS = MappingProxyType(
    {
        "DESIGN": (TEMPORAL_DESIGN_ARTIFACT, MAINLINE_EXECUTION_ARTIFACT),
        "PREREGISTRATION": (
            TEMPORAL_PREREGISTRATION_ARTIFACT,
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "EVALUATED_COMPLETE": (
            TEMPORAL_HEALTH_ARTIFACT,
            TEMPORAL_HISTORICAL_ARTIFACT,
            TEMPORAL_CANDIDATE_ARTIFACT,
            BRANCH_DECISION_ARTIFACT,
            TEMPORAL_COMPLETION_ARTIFACT,
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "PARENT_NOT_ACCEPTED": (
            BRANCH_DECISION_ARTIFACT,
            TEMPORAL_COMPLETION_ARTIFACT,
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "IDENTITY_VALID_HEALTH_REPAIR": (
            TEMPORAL_HEALTH_ARTIFACT,
            BRANCH_DECISION_ARTIFACT,
            TEMPORAL_COMPLETION_ARTIFACT,
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "EARLY_IDENTITY_VALID_HEALTH_REPAIR": (
            "M4V2TemporalMarginalIncrementScientificFailureArtifact@dehps-m4-v2-temporal-marginal-increment-scientific-failure.v3",
            BRANCH_DECISION_ARTIFACT,
            "M4V2TemporalMarginalIncrementProducerCompletionArtifact@dehps-m4-v2-temporal-marginal-increment-producer-completion.v3",
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "STARTED_PARTIAL_HEALTH_REPAIR": (
            "M4V2TemporalMarginalIncrementScientificFailureArtifact@dehps-m4-v2-temporal-marginal-increment-scientific-failure.v3",
            BRANCH_DECISION_ARTIFACT,
            "M4V2TemporalMarginalIncrementProducerCompletionArtifact@dehps-m4-v2-temporal-marginal-increment-producer-completion.v3",
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "IDENTITY_VALID_HEALTH_INVALID": (
            TEMPORAL_FAILURE_ARTIFACT,
            BRANCH_DECISION_ARTIFACT,
            TEMPORAL_COMPLETION_ARTIFACT,
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "IDENTITY_VALID_HISTORICAL_REPAIR": (
            TEMPORAL_HEALTH_ARTIFACT,
            TEMPORAL_FAILURE_ARTIFACT,
            BRANCH_DECISION_ARTIFACT,
            TEMPORAL_COMPLETION_ARTIFACT,
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "IDENTITY_VALID_HISTORICAL_INVALID": (
            TEMPORAL_HEALTH_ARTIFACT,
            TEMPORAL_FAILURE_ARTIFACT,
            BRANCH_DECISION_ARTIFACT,
            TEMPORAL_COMPLETION_ARTIFACT,
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "REPLAY": (BRANCH_REPLAY_ARTIFACT, MAINLINE_EXECUTION_ARTIFACT),
    }
)
_FULL_PATH_COUNTS = MappingProxyType(
    {
        "EVALUATED_COMPLETE": 12,
        "PARENT_NOT_ACCEPTED": 9,
        "IDENTITY_VALID_HEALTH_REPAIR": 10,
        "EARLY_IDENTITY_VALID_HEALTH_REPAIR": 10,
        "STARTED_PARTIAL_HEALTH_REPAIR": 10,
        "IDENTITY_VALID_HEALTH_INVALID": 10,
        "IDENTITY_VALID_HISTORICAL_REPAIR": 11,
        "IDENTITY_VALID_HISTORICAL_INVALID": 11,
    }
)

TEMPORAL_ARTIFACT_TYPES: Final = frozenset(
    {
        TEMPORAL_DESIGN_ARTIFACT,
        TEMPORAL_PREREGISTRATION_ARTIFACT,
        TEMPORAL_HEALTH_ARTIFACT,
        TEMPORAL_HISTORICAL_ARTIFACT,
        TEMPORAL_CANDIDATE_ARTIFACT,
        TEMPORAL_COMPLETION_ARTIFACT,
        TEMPORAL_FAILURE_ARTIFACT,
        BRANCH_DECISION_ARTIFACT,
        BRANCH_REPLAY_ARTIFACT,
    }
)

TEMPORAL_SYNTHETIC_CELLS: Final = (
    (0, "BASE:V2_T1_OVERLAP_ODDS_2_MARKOV:FORWARD_61", "V2_T1_OVERLAP_ODDS_2_MARKOV", "FORWARD_61"),
    (1, "BASE:V2_T1_OVERLAP_ODDS_2_MARKOV:HISTORICAL_2581", "V2_T1_OVERLAP_ODDS_2_MARKOV", "HISTORICAL_2581"),
    (2, "BASE:NULL_UNIFORM_LEGAL_SIX_OF_33:FORWARD_61", "NULL_UNIFORM_LEGAL_SIX_OF_33", "FORWARD_61"),
    (3, "BASE:NULL_UNIFORM_LEGAL_SIX_OF_33:HISTORICAL_2581", "NULL_UNIFORM_LEGAL_SIX_OF_33", "HISTORICAL_2581"),
    (4, "BASE:V2_M1_GROUP_ODDS_2_STATIONARY:FORWARD_61", "V2_M1_GROUP_ODDS_2_STATIONARY", "FORWARD_61"),
    (5, "BASE:V2_M1_GROUP_ODDS_2_STATIONARY:HISTORICAL_2581", "V2_M1_GROUP_ODDS_2_STATIONARY", "HISTORICAL_2581"),
    (6, "BASE:V2_J1_HISTORY_IS4_LAMBDA_HALF:FORWARD_61", "V2_J1_HISTORY_IS4_LAMBDA_HALF", "FORWARD_61"),
    (7, "BASE:V2_J1_HISTORY_IS4_LAMBDA_HALF:HISTORICAL_2581", "V2_J1_HISTORY_IS4_LAMBDA_HALF", "HISTORICAL_2581"),
    (8, "LOCAL:0.001:FORWARD_61", "LOCAL_UNIFORM_CARRIER_OVERLAP_TILT", "FORWARD_61"),
    (9, "LOCAL:0.001:HISTORICAL_2581", "LOCAL_UNIFORM_CARRIER_OVERLAP_TILT", "HISTORICAL_2581"),
    (10, "LOCAL:0.01:FORWARD_61", "LOCAL_UNIFORM_CARRIER_OVERLAP_TILT", "FORWARD_61"),
    (11, "LOCAL:0.01:HISTORICAL_2581", "LOCAL_UNIFORM_CARRIER_OVERLAP_TILT", "HISTORICAL_2581"),
    (12, "LOCAL:0.05:FORWARD_61", "LOCAL_UNIFORM_CARRIER_OVERLAP_TILT", "FORWARD_61"),
    (13, "LOCAL:0.05:HISTORICAL_2581", "LOCAL_UNIFORM_CARRIER_OVERLAP_TILT", "HISTORICAL_2581"),
)

PLANNED_COUNTS: Final = MappingProxyType(
    {
        "cell_count": SYNTHETIC_CELL_COUNT,
        "replicates_per_cell": SYNTHETIC_REPLICATES_PER_CELL,
        "synthetic_replicate_count": SYNTHETIC_REPLICATE_COUNT,
        "synthetic_generated_issue_count": SYNTHETIC_GENERATED_ISSUE_COUNT,
        "outer_evaluation_issue_count": SYNTHETIC_OUTER_EVALUATION_ISSUE_COUNT,
        "bootstrap_resample_count": SYNTHETIC_BOOTSTRAP_CHILD_COUNT,
        "historical_fold_count": EVALUATION_COUNT,
        "historical_child_count": HISTORICAL_CHILD_COUNT,
        "warmup_transition_count_per_replicate": WARMUP_COUNT,
        "warmup_alias_position_count": SYNTHETIC_WARMUP_ALIAS_POSITION_COUNT,
    }
)


def _mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TemporalMarginalIncrementContractError(f"{name}_must_be_object")
    return value


def _exact_fields(
    value: Mapping[str, Any], fields: Sequence[str], *, name: str
) -> None:
    expected = set(fields)
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise TemporalMarginalIncrementContractError(
            f"{name}_fields_mismatch:missing={missing}:extra={extra}"
        )


def _digest(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise TemporalMarginalIncrementContractError(f"{name}_must_be_sha256")
    return value


def _execution_id(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or _EXECUTION_ID_RE.fullmatch(value) is None:
        raise TemporalMarginalIncrementContractError(
            f"{name}_must_be_lowercase_sha256_execution_identity"
        )
    return value


def _integer(value: Any, *, name: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TemporalMarginalIncrementContractError(f"{name}_must_be_integer")
    if minimum is not None and value < minimum:
        raise TemporalMarginalIncrementContractError(f"{name}_below_minimum")
    return value


def _issue(value: Any, *, name: str = "issue") -> str:
    if not isinstance(value, str) or not value:
        raise TemporalMarginalIncrementContractError(f"{name}_must_be_nonempty_string")
    return value


def _float_hex(
    value: Any,
    *,
    name: str,
    nonnegative: bool = False,
    positive: bool = False,
) -> str:
    if not isinstance(value, str):
        raise TemporalMarginalIncrementContractError(f"{name}_must_be_float_hex")
    try:
        parsed = float.fromhex(value)
    except ValueError as exc:
        raise TemporalMarginalIncrementContractError(
            f"{name}_must_be_float_hex"
        ) from exc
    if not math.isfinite(parsed) or parsed.hex() != value or value.startswith("-") and parsed == 0:
        raise TemporalMarginalIncrementContractError(
            f"{name}_must_be_canonical_finite_positive_zero_safe_float_hex"
        )
    if nonnegative and parsed < 0:
        raise TemporalMarginalIncrementContractError(f"{name}_must_be_nonnegative")
    if positive and parsed <= 0:
        raise TemporalMarginalIncrementContractError(f"{name}_must_be_positive")
    return value


def _self_digest(
    value: Mapping[str, Any],
    *,
    digest_field: str,
    domain: str,
    input_fields: Sequence[str],
    name: str,
) -> None:
    expected = m4_v2_domain_digest(
        {field: value[field] for field in input_fields}, domain=domain
    )
    if value.get(digest_field) != expected:
        raise TemporalMarginalIncrementContractError(f"{name}_digest_mismatch")


def _validate_nested(schema_name: str, value: Any) -> Any:
    try:
        return validate_m4_v2_nested_schema(schema_name, value)
    except Exception as exc:  # shared registry is the canonical schema owner
        raise TemporalMarginalIncrementContractError(
            f"{schema_name}_shared_schema_invalid"
        ) from exc


def temporal_registration_plan(path: str) -> TemporalRegistrationPlan:
    normalized = str(path or "").upper()
    try:
        artifact_types = _REGISTRATION_ORDERS[normalized]
    except KeyError as exc:
        raise TemporalMarginalIncrementContractError(
            f"temporal_registration_path_unknown:{path}"
        ) from exc
    if normalized == "DESIGN":
        task_key = TEMPORAL_DESIGN_TASK_KEY
        full_count = 2
    elif normalized == "PREREGISTRATION":
        task_key = TEMPORAL_PREREGISTRATION_TASK_KEY
        full_count = 2
    elif normalized == "REPLAY":
        task_key = TEMPORAL_REPLAY_TASK_KEY
        full_count = 2
    else:
        task_key = TEMPORAL_PRODUCER_TASK_KEY
        full_count = _FULL_PATH_COUNTS[normalized]
    return TemporalRegistrationPlan(
        path=normalized,
        task_key=task_key,
        artifact_types_in_registration_order=artifact_types,
        registration_count_including_mainline_execution=len(artifact_types),
        full_four_task_registration_count=full_count,
    )


def temporal_checkpoint_plan(transition_ordinal: int) -> TemporalCheckpointPlan:
    ordinal = _integer(transition_ordinal, name="transition_ordinal", minimum=2)
    if ordinal > EVALUATION_END:
        raise TemporalMarginalIncrementContractError("transition_ordinal_out_of_range")
    warmup = ordinal <= WARMUP_END
    return TemporalCheckpointPlan(
        transition_ordinal=ordinal,
        support_kind=("WARMUP_NULL_ALIAS" if warmup else "ACCEPTED_TEMPORAL_EVALUATION"),
        prefix_last_ordinal=ordinal - 1,
        theta_fit_invoked=not warmup,
        theta_root_existence_test_invoked=not warmup,
        target_is_historical_evidence=not warmup,
    )


def build_transition_local_warmup_rule() -> dict[str, Any]:
    rule: dict[str, Any] = {
        "schema_version": "dehps-m4-v2-transition-local-temporal-warmup.v1",
        "support_model_id": SUPPORT_MODEL_ID,
        "rule": "FIXED_NULL_THETA_ZERO_PARENT_DISTRIBUTION_ALIAS",
        "transition_range": [WARMUP_START, WARMUP_END],
        "transition_count": WARMUP_COUNT,
        "theta_float_hex": POSITIVE_ZERO_FLOAT_HEX,
        "theta_ieee754_binary64_be_hex": POSITIVE_ZERO_IEEE754_BINARY64_BE_HEX,
        "negative_zero_allowed": False,
        "temporal_theta_fit_invoked": False,
        "temporal_theta_root_existence_test_invoked": False,
        "regularization": None,
        "fallback": None,
        "distribution_content_alias": True,
        "artifact_envelope_alias": False,
        "semantic_scope": WARMUP_SEMANTIC_SCOPE,
    }
    rule["rule_digest"] = m4_v2_domain_digest(
        rule,
        domain="dehps.m4.v2.transition-local-temporal-warmup.rule.v1",
    )
    return validate_transition_local_warmup_rule(rule)


def validate_transition_local_warmup_rule(value: Any) -> dict[str, Any]:
    rule = dict(_mapping(value, name="transition_local_warmup_rule"))
    fields = (
        "schema_version",
        "support_model_id",
        "rule",
        "transition_range",
        "transition_count",
        "theta_float_hex",
        "theta_ieee754_binary64_be_hex",
        "negative_zero_allowed",
        "temporal_theta_fit_invoked",
        "temporal_theta_root_existence_test_invoked",
        "regularization",
        "fallback",
        "distribution_content_alias",
        "artifact_envelope_alias",
        "semantic_scope",
        "rule_digest",
    )
    _exact_fields(rule, fields, name="transition_local_warmup_rule")
    expected = {
        "schema_version": "dehps-m4-v2-transition-local-temporal-warmup.v1",
        "support_model_id": SUPPORT_MODEL_ID,
        "rule": "FIXED_NULL_THETA_ZERO_PARENT_DISTRIBUTION_ALIAS",
        "transition_range": [WARMUP_START, WARMUP_END],
        "transition_count": WARMUP_COUNT,
        "theta_float_hex": POSITIVE_ZERO_FLOAT_HEX,
        "theta_ieee754_binary64_be_hex": POSITIVE_ZERO_IEEE754_BINARY64_BE_HEX,
        "negative_zero_allowed": False,
        "temporal_theta_fit_invoked": False,
        "temporal_theta_root_existence_test_invoked": False,
        "regularization": None,
        "fallback": None,
        "distribution_content_alias": True,
        "artifact_envelope_alias": False,
        "semantic_scope": WARMUP_SEMANTIC_SCOPE,
    }
    if {field: rule[field] for field in expected} != expected:
        raise TemporalMarginalIncrementContractError(
            "transition_local_warmup_fixed_values_changed"
        )
    _self_digest(
        rule,
        digest_field="rule_digest",
        domain="dehps.m4.v2.transition-local-temporal-warmup.rule.v1",
        input_fields=fields[:-1],
        name="transition_local_warmup_rule",
    )
    _validate_nested("warmup_rule_schema", rule)
    return rule


_STRICT_PRIOR_FIELDS = (
    "dataset_content_digest",
    "checkpoint_order_manifest_digest",
    "transition_ordinal",
    "issue",
    "prefix_last_ordinal",
    "prefix_last_issue",
    "prefix_outcome_chain_digest",
    "parent_estimator_id",
    "q_m_marginal_content_digest",
    "q_m_full_distribution_content_digest",
    "checkpoint_digest",
)


def build_strict_prior_marginal_checkpoint(
    *,
    transition_ordinal: int,
    issue: str,
    prefix_last_issue: str,
    prefix_outcome_chain_digest: str,
    q_m_marginal_content_digest: str,
    q_m_full_distribution_content_digest: str,
) -> dict[str, Any]:
    ordinal = _integer(transition_ordinal, name="transition_ordinal", minimum=2)
    if ordinal > EVALUATION_END:
        raise TemporalMarginalIncrementContractError("transition_ordinal_out_of_range")
    checkpoint: dict[str, Any] = {
        "dataset_content_digest": DATASET_CONTENT_DIGEST,
        "checkpoint_order_manifest_digest": CHECKPOINT_ORDER_MANIFEST_DIGEST,
        "transition_ordinal": ordinal,
        "issue": _issue(issue),
        "prefix_last_ordinal": ordinal - 1,
        "prefix_last_issue": _issue(prefix_last_issue, name="prefix_last_issue"),
        "prefix_outcome_chain_digest": _digest(
            prefix_outcome_chain_digest, name="prefix_outcome_chain_digest"
        ),
        "parent_estimator_id": PARENT_ESTIMATOR_ID,
        "q_m_marginal_content_digest": _digest(
            q_m_marginal_content_digest, name="q_m_marginal_content_digest"
        ),
        "q_m_full_distribution_content_digest": _digest(
            q_m_full_distribution_content_digest,
            name="q_m_full_distribution_content_digest",
        ),
    }
    checkpoint["checkpoint_digest"] = m4_v2_domain_digest(
        checkpoint,
        domain="dehps.m4.v2.strict-prior-marginal-checkpoint.v1",
    )
    return validate_strict_prior_marginal_checkpoint(checkpoint)


def validate_strict_prior_marginal_checkpoint(
    value: Any,
    *,
    prefix_preimage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    checkpoint = dict(_mapping(value, name="strict_prior_checkpoint"))
    _exact_fields(checkpoint, _STRICT_PRIOR_FIELDS, name="strict_prior_checkpoint")
    ordinal = _integer(
        checkpoint["transition_ordinal"], name="transition_ordinal", minimum=2
    )
    if ordinal > EVALUATION_END or checkpoint["prefix_last_ordinal"] != ordinal - 1:
        raise TemporalMarginalIncrementContractError("strict_prior_boundary_breached")
    if (
        checkpoint["dataset_content_digest"] != DATASET_CONTENT_DIGEST
        or checkpoint["checkpoint_order_manifest_digest"]
        != CHECKPOINT_ORDER_MANIFEST_DIGEST
        or checkpoint["parent_estimator_id"] != PARENT_ESTIMATOR_ID
    ):
        raise TemporalMarginalIncrementContractError("strict_prior_identity_mismatch")
    _issue(checkpoint["issue"])
    _issue(checkpoint["prefix_last_issue"], name="prefix_last_issue")
    for name in (
        "prefix_outcome_chain_digest",
        "q_m_marginal_content_digest",
        "q_m_full_distribution_content_digest",
        "checkpoint_digest",
    ):
        _digest(checkpoint[name], name=name)
    if prefix_preimage is not None:
        prefix = dict(_mapping(prefix_preimage, name="prefix_preimage"))
        _exact_fields(
            prefix,
            (
                "dataset_content_digest",
                "last_included_ordinal",
                "ordered_issue_and_six_red_number_rows_1_through_last_included_ordinal",
            ),
            name="prefix_preimage",
        )
        rows = prefix[
            "ordered_issue_and_six_red_number_rows_1_through_last_included_ordinal"
        ]
        if (
            prefix["dataset_content_digest"] != DATASET_CONTENT_DIGEST
            or prefix["last_included_ordinal"] != ordinal - 1
            or not isinstance(rows, list)
            or len(rows) != ordinal - 1
            or m4_v2_domain_digest(
                prefix, domain="dehps.m4.v2.dataset-prefix-outcome-chain.v1"
            )
            != checkpoint["prefix_outcome_chain_digest"]
        ):
            raise TemporalMarginalIncrementContractError(
                "strict_prior_prefix_preimage_mismatch"
            )
    _self_digest(
        checkpoint,
        digest_field="checkpoint_digest",
        domain="dehps.m4.v2.strict-prior-marginal-checkpoint.v1",
        input_fields=_STRICT_PRIOR_FIELDS[:-1],
        name="strict_prior_checkpoint",
    )
    return checkpoint


_WARMUP_ROW_FIELDS = (
    "transition_ordinal",
    "issue",
    "strict_prior_checkpoint_digest",
    "q_m_marginal_content_digest",
    "q_m_full_distribution_content_digest",
    "theta_float_hex",
    "q_t_marginal_content_digest",
    "q_t_full_distribution_content_digest",
    "temporal_theta_fit_invoked",
    "semantic_scope",
    "row_digest",
)


def build_temporal_warmup_row(
    strict_prior_checkpoint: Mapping[str, Any],
) -> dict[str, Any]:
    checkpoint = validate_strict_prior_marginal_checkpoint(strict_prior_checkpoint)
    ordinal = checkpoint["transition_ordinal"]
    if not WARMUP_START <= ordinal <= WARMUP_END:
        raise TemporalMarginalIncrementContractError("warmup_ordinal_out_of_range")
    row: dict[str, Any] = {
        "transition_ordinal": ordinal,
        "issue": checkpoint["issue"],
        "strict_prior_checkpoint_digest": checkpoint["checkpoint_digest"],
        "q_m_marginal_content_digest": checkpoint["q_m_marginal_content_digest"],
        "q_m_full_distribution_content_digest": checkpoint[
            "q_m_full_distribution_content_digest"
        ],
        "theta_float_hex": POSITIVE_ZERO_FLOAT_HEX,
        "q_t_marginal_content_digest": checkpoint["q_m_marginal_content_digest"],
        "q_t_full_distribution_content_digest": checkpoint[
            "q_m_full_distribution_content_digest"
        ],
        "temporal_theta_fit_invoked": False,
        "semantic_scope": WARMUP_SEMANTIC_SCOPE,
    }
    row["row_digest"] = m4_v2_domain_digest(
        row, domain="dehps.m4.v2.transition-local-temporal-warmup.row.v1"
    )
    return validate_temporal_warmup_row(row, strict_prior_checkpoint=checkpoint)


def validate_temporal_warmup_row(
    value: Any,
    *,
    strict_prior_checkpoint: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    row = dict(_mapping(value, name="temporal_warmup_row"))
    _exact_fields(row, _WARMUP_ROW_FIELDS, name="temporal_warmup_row")
    ordinal = _integer(
        row["transition_ordinal"], name="transition_ordinal", minimum=WARMUP_START
    )
    if ordinal > WARMUP_END:
        raise TemporalMarginalIncrementContractError("warmup_ordinal_out_of_range")
    _issue(row["issue"])
    for name in (
        "strict_prior_checkpoint_digest",
        "q_m_marginal_content_digest",
        "q_m_full_distribution_content_digest",
        "q_t_marginal_content_digest",
        "q_t_full_distribution_content_digest",
        "row_digest",
    ):
        _digest(row[name], name=name)
    if (
        row["theta_float_hex"] != POSITIVE_ZERO_FLOAT_HEX
        or row["temporal_theta_fit_invoked"] is not False
        or row["semantic_scope"] != WARMUP_SEMANTIC_SCOPE
        or row["q_t_marginal_content_digest"]
        != row["q_m_marginal_content_digest"]
        or row["q_t_full_distribution_content_digest"]
        != row["q_m_full_distribution_content_digest"]
    ):
        raise TemporalMarginalIncrementContractError(
            "warmup_positive_zero_alias_contract_breached"
        )
    if strict_prior_checkpoint is not None:
        checkpoint = validate_strict_prior_marginal_checkpoint(
            strict_prior_checkpoint
        )
        if (
            checkpoint["transition_ordinal"] != ordinal
            or checkpoint["issue"] != row["issue"]
            or checkpoint["checkpoint_digest"]
            != row["strict_prior_checkpoint_digest"]
            or checkpoint["q_m_marginal_content_digest"]
            != row["q_m_marginal_content_digest"]
            or checkpoint["q_m_full_distribution_content_digest"]
            != row["q_m_full_distribution_content_digest"]
        ):
            raise TemporalMarginalIncrementContractError(
                "warmup_strict_prior_dereference_mismatch"
            )
    _self_digest(
        row,
        digest_field="row_digest",
        domain="dehps.m4.v2.transition-local-temporal-warmup.row.v1",
        input_fields=_WARMUP_ROW_FIELDS[:-1],
        name="temporal_warmup_row",
    )
    _validate_nested("warmup_row_schema", row)
    return row


def build_temporal_warmup_index(
    rows: Sequence[Mapping[str, Any]], *, rule_digest: str
) -> dict[str, Any]:
    validated_rows = [validate_temporal_warmup_row(row) for row in rows]
    digests = [row["row_digest"] for row in validated_rows]
    chain_digest = m4_v2_domain_digest(
        {"row_digests_in_order": digests},
        domain="dehps.m4.v2.transition-local-temporal-warmup.row-chain.v1",
    )
    index: dict[str, Any] = {
        "row_count": len(validated_rows),
        "transition_range": [WARMUP_START, WARMUP_END],
        "rows": validated_rows,
        "row_digests_in_order": digests,
        "row_chain_digest": chain_digest,
        "rule_digest": _digest(rule_digest, name="rule_digest"),
    }
    index["warmup_index_digest"] = m4_v2_domain_digest(
        {
            "row_count": index["row_count"],
            "transition_range": index["transition_range"],
            "row_chain_digest": index["row_chain_digest"],
            "rule_digest": index["rule_digest"],
        },
        domain="dehps.m4.v2.transition-local-temporal-warmup.index.v1",
    )
    return validate_temporal_warmup_index(index, expected_rule_digest=rule_digest)


def validate_temporal_warmup_index(
    value: Any, *, expected_rule_digest: str | None = None
) -> dict[str, Any]:
    index = dict(_mapping(value, name="temporal_warmup_index"))
    fields = (
        "row_count",
        "transition_range",
        "rows",
        "row_digests_in_order",
        "row_chain_digest",
        "rule_digest",
        "warmup_index_digest",
    )
    _exact_fields(index, fields, name="temporal_warmup_index")
    rows_raw = index["rows"]
    digests_raw = index["row_digests_in_order"]
    if not isinstance(rows_raw, list) or not isinstance(digests_raw, list):
        raise TemporalMarginalIncrementContractError("warmup_index_rows_invalid")
    rows = [validate_temporal_warmup_row(row) for row in rows_raw]
    expected_ordinals = list(range(WARMUP_START, WARMUP_END + 1))
    if (
        index["row_count"] != WARMUP_COUNT
        or index["transition_range"] != [WARMUP_START, WARMUP_END]
        or [row["transition_ordinal"] for row in rows] != expected_ordinals
        or digests_raw != [row["row_digest"] for row in rows]
    ):
        raise TemporalMarginalIncrementContractError(
            "warmup_index_coverage_or_order_mismatch"
        )
    _digest(index["rule_digest"], name="rule_digest")
    if expected_rule_digest is not None and index["rule_digest"] != _digest(
        expected_rule_digest, name="expected_rule_digest"
    ):
        raise TemporalMarginalIncrementContractError("warmup_rule_owner_mismatch")
    expected_chain = m4_v2_domain_digest(
        {"row_digests_in_order": digests_raw},
        domain="dehps.m4.v2.transition-local-temporal-warmup.row-chain.v1",
    )
    if index["row_chain_digest"] != expected_chain:
        raise TemporalMarginalIncrementContractError("warmup_row_chain_mismatch")
    _self_digest(
        index,
        digest_field="warmup_index_digest",
        domain="dehps.m4.v2.transition-local-temporal-warmup.index.v1",
        input_fields=(
            "row_count",
            "transition_range",
            "row_chain_digest",
            "rule_digest",
        ),
        name="temporal_warmup_index",
    )
    _validate_nested("warmup_index_schema", index)
    return index


_PRETARGET_FIELDS = (
    "dataset_content_digest",
    "fold_manifest_digest",
    "checkpoint_order_manifest_digest",
    "transition_ordinal",
    "issue",
    "training_prefix_last_ordinal",
    "training_prefix_outcome_chain_digest",
    "parent_estimator_id",
    "temporal_estimator_id",
    "theta_float_hex",
    "q_t_marginal_content_digest",
    "q_t_full_distribution_content_digest",
    "pretarget_checkpoint_digest",
)


def build_accepted_temporal_pretarget_checkpoint(
    *,
    transition_ordinal: int,
    issue: str,
    training_prefix_outcome_chain_digest: str,
    theta_float_hex: str,
    q_t_marginal_content_digest: str,
    q_t_full_distribution_content_digest: str,
) -> dict[str, Any]:
    ordinal = _integer(
        transition_ordinal, name="transition_ordinal", minimum=EVALUATION_START
    )
    if ordinal > EVALUATION_END:
        raise TemporalMarginalIncrementContractError("evaluation_ordinal_out_of_range")
    checkpoint: dict[str, Any] = {
        "dataset_content_digest": DATASET_CONTENT_DIGEST,
        "fold_manifest_digest": FOLD_MANIFEST_DIGEST,
        "checkpoint_order_manifest_digest": CHECKPOINT_ORDER_MANIFEST_DIGEST,
        "transition_ordinal": ordinal,
        "issue": _issue(issue),
        "training_prefix_last_ordinal": ordinal - 1,
        "training_prefix_outcome_chain_digest": _digest(
            training_prefix_outcome_chain_digest,
            name="training_prefix_outcome_chain_digest",
        ),
        "parent_estimator_id": PARENT_ESTIMATOR_ID,
        "temporal_estimator_id": TEMPORAL_MODEL_ID,
        "theta_float_hex": _float_hex(theta_float_hex, name="theta_float_hex"),
        "q_t_marginal_content_digest": _digest(
            q_t_marginal_content_digest, name="q_t_marginal_content_digest"
        ),
        "q_t_full_distribution_content_digest": _digest(
            q_t_full_distribution_content_digest,
            name="q_t_full_distribution_content_digest",
        ),
    }
    checkpoint["pretarget_checkpoint_digest"] = m4_v2_domain_digest(
        checkpoint,
        domain="dehps.m4.v2.temporal.accepted-pretarget-checkpoint.v2",
    )
    return validate_accepted_temporal_pretarget_checkpoint(checkpoint)


def validate_accepted_temporal_pretarget_checkpoint(value: Any) -> dict[str, Any]:
    checkpoint = dict(_mapping(value, name="accepted_pretarget_checkpoint"))
    _exact_fields(checkpoint, _PRETARGET_FIELDS, name="accepted_pretarget_checkpoint")
    ordinal = _integer(
        checkpoint["transition_ordinal"],
        name="transition_ordinal",
        minimum=EVALUATION_START,
    )
    if ordinal > EVALUATION_END or checkpoint["training_prefix_last_ordinal"] != ordinal - 1:
        raise TemporalMarginalIncrementContractError(
            "accepted_pretarget_strict_prior_boundary_breached"
        )
    if (
        checkpoint["dataset_content_digest"] != DATASET_CONTENT_DIGEST
        or checkpoint["fold_manifest_digest"] != FOLD_MANIFEST_DIGEST
        or checkpoint["checkpoint_order_manifest_digest"]
        != CHECKPOINT_ORDER_MANIFEST_DIGEST
        or checkpoint["parent_estimator_id"] != PARENT_ESTIMATOR_ID
        or checkpoint["temporal_estimator_id"] != TEMPORAL_MODEL_ID
    ):
        raise TemporalMarginalIncrementContractError(
            "accepted_pretarget_identity_mismatch"
        )
    _issue(checkpoint["issue"])
    _float_hex(checkpoint["theta_float_hex"], name="theta_float_hex")
    for name in (
        "training_prefix_outcome_chain_digest",
        "q_t_marginal_content_digest",
        "q_t_full_distribution_content_digest",
        "pretarget_checkpoint_digest",
    ):
        _digest(checkpoint[name], name=name)
    _self_digest(
        checkpoint,
        digest_field="pretarget_checkpoint_digest",
        domain="dehps.m4.v2.temporal.accepted-pretarget-checkpoint.v2",
        input_fields=_PRETARGET_FIELDS[:-1],
        name="accepted_pretarget_checkpoint",
    )
    return checkpoint


_ACCEPTED_ROW_FIELDS = (
    "transition_ordinal",
    "issue",
    "pretarget_checkpoint_digest",
    "theta_float_hex",
    "q_t_marginal_content_digest",
    "q_t_full_distribution_content_digest",
    "q_t_row_digest",
)


def build_accepted_temporal_evaluation_row(
    pretarget_checkpoint: Mapping[str, Any],
) -> dict[str, Any]:
    checkpoint = validate_accepted_temporal_pretarget_checkpoint(
        pretarget_checkpoint
    )
    row: dict[str, Any] = {
        "transition_ordinal": checkpoint["transition_ordinal"],
        "issue": checkpoint["issue"],
        "pretarget_checkpoint_digest": checkpoint["pretarget_checkpoint_digest"],
        "theta_float_hex": checkpoint["theta_float_hex"],
        "q_t_marginal_content_digest": checkpoint["q_t_marginal_content_digest"],
        "q_t_full_distribution_content_digest": checkpoint[
            "q_t_full_distribution_content_digest"
        ],
    }
    row["q_t_row_digest"] = m4_v2_domain_digest(
        row, domain="dehps.m4.v2.temporal.accepted-evaluation-row.v2"
    )
    return validate_accepted_temporal_evaluation_row(
        row, pretarget_checkpoint=checkpoint
    )


def validate_accepted_temporal_evaluation_row(
    value: Any,
    *,
    pretarget_checkpoint: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    row = dict(_mapping(value, name="accepted_temporal_evaluation_row"))
    _exact_fields(row, _ACCEPTED_ROW_FIELDS, name="accepted_temporal_evaluation_row")
    ordinal = _integer(
        row["transition_ordinal"], name="transition_ordinal", minimum=EVALUATION_START
    )
    if ordinal > EVALUATION_END:
        raise TemporalMarginalIncrementContractError("evaluation_ordinal_out_of_range")
    _issue(row["issue"])
    _float_hex(row["theta_float_hex"], name="theta_float_hex")
    for name in (
        "pretarget_checkpoint_digest",
        "q_t_marginal_content_digest",
        "q_t_full_distribution_content_digest",
        "q_t_row_digest",
    ):
        _digest(row[name], name=name)
    if pretarget_checkpoint is not None:
        checkpoint = validate_accepted_temporal_pretarget_checkpoint(
            pretarget_checkpoint
        )
        pairs = (
            ("transition_ordinal", "transition_ordinal"),
            ("issue", "issue"),
            ("pretarget_checkpoint_digest", "pretarget_checkpoint_digest"),
            ("theta_float_hex", "theta_float_hex"),
            ("q_t_marginal_content_digest", "q_t_marginal_content_digest"),
            (
                "q_t_full_distribution_content_digest",
                "q_t_full_distribution_content_digest",
            ),
        )
        if any(row[left] != checkpoint[right] for left, right in pairs):
            raise TemporalMarginalIncrementContractError(
                "accepted_temporal_pretarget_dereference_mismatch"
            )
    _self_digest(
        row,
        digest_field="q_t_row_digest",
        domain="dehps.m4.v2.temporal.accepted-evaluation-row.v2",
        input_fields=_ACCEPTED_ROW_FIELDS[:-1],
        name="accepted_temporal_evaluation_row",
    )
    return row


def build_accepted_temporal_evaluation_index(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    validated = [validate_accepted_temporal_evaluation_row(row) for row in rows]
    digests = [row["q_t_row_digest"] for row in validated]
    index: dict[str, Any] = {
        "row_count": len(validated),
        "transition_range": [EVALUATION_START, EVALUATION_END],
        "rows": validated,
        "ordered_q_t_row_digests": digests,
    }
    index["accepted_temporal_evaluation_index_digest"] = m4_v2_domain_digest(
        {
            "row_count": index["row_count"],
            "transition_range": index["transition_range"],
            "ordered_q_t_row_digests": digests,
        },
        domain="dehps.m4.v2.temporal.accepted-evaluation-index.v2",
    )
    return validate_accepted_temporal_evaluation_index(index)


def validate_accepted_temporal_evaluation_index(value: Any) -> dict[str, Any]:
    index = dict(_mapping(value, name="accepted_temporal_evaluation_index"))
    fields = (
        "row_count",
        "transition_range",
        "rows",
        "ordered_q_t_row_digests",
        "accepted_temporal_evaluation_index_digest",
    )
    _exact_fields(index, fields, name="accepted_temporal_evaluation_index")
    if not isinstance(index["rows"], list) or not isinstance(
        index["ordered_q_t_row_digests"], list
    ):
        raise TemporalMarginalIncrementContractError(
            "accepted_temporal_evaluation_index_rows_invalid"
        )
    rows = [validate_accepted_temporal_evaluation_row(row) for row in index["rows"]]
    if (
        index["row_count"] != EVALUATION_COUNT
        or index["transition_range"] != [EVALUATION_START, EVALUATION_END]
        or [row["transition_ordinal"] for row in rows]
        != list(range(EVALUATION_START, EVALUATION_END + 1))
        or index["ordered_q_t_row_digests"]
        != [row["q_t_row_digest"] for row in rows]
    ):
        raise TemporalMarginalIncrementContractError(
            "accepted_temporal_evaluation_coverage_or_order_mismatch"
        )
    _self_digest(
        index,
        digest_field="accepted_temporal_evaluation_index_digest",
        domain="dehps.m4.v2.temporal.accepted-evaluation-index.v2",
        input_fields=(
            "row_count",
            "transition_range",
            "ordered_q_t_row_digests",
        ),
        name="accepted_temporal_evaluation_index",
    )
    _validate_nested("accepted_temporal_evaluation_index", index)
    return index


def build_temporal_composite_view(
    *, warmup_index_digest: str, accepted_temporal_evaluation_index_digest: str
) -> dict[str, Any]:
    view: dict[str, Any] = {
        "transition_range": [COMPOSITE_START, COMPOSITE_END],
        "row_count": COMPOSITE_COUNT,
        "warmup_index_digest": _digest(
            warmup_index_digest, name="warmup_index_digest"
        ),
        "accepted_temporal_evaluation_index_digest": _digest(
            accepted_temporal_evaluation_index_digest,
            name="accepted_temporal_evaluation_index_digest",
        ),
    }
    view["composite_view_digest"] = m4_v2_domain_digest(
        view,
        domain="dehps.m4.v2.transition-local-temporal-composite-view.v1",
    )
    return validate_temporal_composite_view(view)


def validate_temporal_composite_view(value: Any) -> dict[str, Any]:
    view = dict(_mapping(value, name="temporal_composite_view"))
    fields = (
        "transition_range",
        "row_count",
        "warmup_index_digest",
        "accepted_temporal_evaluation_index_digest",
        "composite_view_digest",
    )
    _exact_fields(view, fields, name="temporal_composite_view")
    if (
        view["transition_range"] != [COMPOSITE_START, COMPOSITE_END]
        or view["row_count"] != COMPOSITE_COUNT
    ):
        raise TemporalMarginalIncrementContractError(
            "temporal_composite_view_range_mismatch"
        )
    for name in fields[2:]:
        _digest(view[name], name=name)
    _self_digest(
        view,
        digest_field="composite_view_digest",
        domain="dehps.m4.v2.transition-local-temporal-composite-view.v1",
        input_fields=fields[:-1],
        name="temporal_composite_view",
    )
    _validate_nested("composite_temporal_view_schema", view)
    return view


def resolve_temporal_composite_row(
    *,
    transition_ordinal: int,
    warmup_index: Mapping[str, Any],
    accepted_evaluation_index: Mapping[str, Any],
) -> dict[str, Any]:
    ordinal = _integer(transition_ordinal, name="transition_ordinal", minimum=2)
    if ordinal <= WARMUP_END:
        index = validate_temporal_warmup_index(warmup_index)
        return dict(index["rows"][ordinal - WARMUP_START])
    if ordinal <= EVALUATION_END:
        index = validate_accepted_temporal_evaluation_index(
            accepted_evaluation_index
        )
        return dict(index["rows"][ordinal - EVALUATION_START])
    raise TemporalMarginalIncrementContractError("composite_ordinal_out_of_range")


def temporal_strict_prior_content_identity(value: Mapping[str, Any]) -> tuple[Any, ...]:
    row = _mapping(value, name="temporal_strict_prior_row")
    if "q_t_marginal_content_digest" in row:
        return (
            row.get("q_m_marginal_content_digest"),
            row.get("q_m_full_distribution_content_digest"),
            row.get("q_t_marginal_content_digest"),
            row.get("q_t_full_distribution_content_digest"),
            row.get("theta_float_hex"),
            row.get("temporal_theta_fit_invoked"),
        )
    raise TemporalMarginalIncrementContractError(
        "strict_prior_content_identity_fields_missing"
    )


def assert_temporal_suffix_noninterference(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> None:
    """Falsifier: source revisions may change provenance but not same-prefix content."""

    if temporal_strict_prior_content_identity(left) != temporal_strict_prior_content_identity(
        right
    ):
        raise TemporalMarginalIncrementContractError(
            "current_or_suffix_outcome_changed_strict_prior_content"
        )


def temporal_synthetic_warmup_position(
    *, cell_index: int, replicate_index: int, transition_ordinal: int
) -> int:
    cell = _integer(cell_index, name="cell_index", minimum=0)
    replicate = _integer(replicate_index, name="replicate_index", minimum=0)
    ordinal = _integer(
        transition_ordinal, name="transition_ordinal", minimum=WARMUP_START
    )
    if (
        cell >= SYNTHETIC_CELL_COUNT
        or replicate >= SYNTHETIC_REPLICATES_PER_CELL
        or ordinal > WARMUP_END
    ):
        raise TemporalMarginalIncrementContractError(
            "synthetic_warmup_coordinate_out_of_range"
        )
    return (
        (cell * SYNTHETIC_REPLICATES_PER_CELL + replicate) * WARMUP_COUNT
        + ordinal
        - WARMUP_START
    )


def _temporal_sequence_seed(
    *, cell_index: int, cell_id: str, replicate_index: int
) -> str:
    material = {
        "domain": "M4_V2_TEMPORAL_MARGINAL_INCREMENT_MEASUREMENT_HEALTH_V1",
        "root_seed_full_sha256": TEMPORAL_SYNTHETIC_ROOT_SEED_FULL_SHA256,
        "coordinate_type": "SEQUENCE",
        "cell_index": cell_index,
        "cell_id": cell_id,
        "replicate_index": replicate_index,
    }
    encoded = json.dumps(
        material, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_temporal_synthetic_sequence_coordinate(
    *,
    health_contract_digest: str,
    seed_contract_digest: str,
    cell_index: int,
    replicate_index: int,
) -> dict[str, Any]:
    cell = _integer(cell_index, name="cell_index", minimum=0)
    replicate = _integer(replicate_index, name="replicate_index", minimum=0)
    if cell >= SYNTHETIC_CELL_COUNT or replicate >= SYNTHETIC_REPLICATES_PER_CELL:
        raise TemporalMarginalIncrementContractError(
            "temporal_synthetic_sequence_coordinate_out_of_range"
        )
    _, cell_id, fixture_id, horizon_id = TEMPORAL_SYNTHETIC_CELLS[cell]
    coordinate: dict[str, Any] = {
        "branch_id": TEMPORAL_BRANCH_ID,
        "fixture_source_digest": FIXTURE_SOURCE_DIGEST,
        "health_contract_digest": _digest(
            health_contract_digest, name="health_contract_digest"
        ),
        "seed_contract_digest": _digest(
            seed_contract_digest, name="seed_contract_digest"
        ),
        "synthetic_root_seed_full_sha256": (
            TEMPORAL_SYNTHETIC_ROOT_SEED_FULL_SHA256
        ),
        "cell_index": cell,
        "cell_id": cell_id,
        "fixture_id": fixture_id,
        "horizon_id": horizon_id,
        "sequence_issue_count": 961 if horizon_id == "FORWARD_61" else 3481,
        "replicate_index": replicate,
        "sequence_seed_full_sha256": _temporal_sequence_seed(
            cell_index=cell, cell_id=cell_id, replicate_index=replicate
        ),
    }
    coordinate["coordinate_digest"] = m4_v2_domain_digest(
        coordinate,
        domain="dehps.m4.v2.temporal.synthetic-warmup.sequence-coordinate.v1",
    )
    return validate_temporal_synthetic_sequence_coordinate(coordinate)


def validate_temporal_synthetic_sequence_coordinate(value: Any) -> dict[str, Any]:
    coordinate = dict(
        _mapping(value, name="temporal_synthetic_sequence_coordinate")
    )
    _validate_nested("synthetic_warmup_sequence_coordinate", coordinate)
    cell = _integer(coordinate["cell_index"], name="cell_index", minimum=0)
    replicate = _integer(
        coordinate["replicate_index"], name="replicate_index", minimum=0
    )
    if cell >= SYNTHETIC_CELL_COUNT or replicate >= SYNTHETIC_REPLICATES_PER_CELL:
        raise TemporalMarginalIncrementContractError(
            "temporal_synthetic_sequence_coordinate_out_of_range"
        )
    _, cell_id, fixture_id, horizon_id = TEMPORAL_SYNTHETIC_CELLS[cell]
    expected = {
        "branch_id": TEMPORAL_BRANCH_ID,
        "fixture_source_digest": FIXTURE_SOURCE_DIGEST,
        "synthetic_root_seed_full_sha256": (
            TEMPORAL_SYNTHETIC_ROOT_SEED_FULL_SHA256
        ),
        "cell_id": cell_id,
        "fixture_id": fixture_id,
        "horizon_id": horizon_id,
        "sequence_issue_count": 961 if horizon_id == "FORWARD_61" else 3481,
        "sequence_seed_full_sha256": _temporal_sequence_seed(
            cell_index=cell, cell_id=cell_id, replicate_index=replicate
        ),
    }
    if any(coordinate.get(key) != item for key, item in expected.items()):
        raise TemporalMarginalIncrementContractError(
            "temporal_synthetic_sequence_seed_or_cell_mismatch"
        )
    _self_digest(
        coordinate,
        digest_field="coordinate_digest",
        domain="dehps.m4.v2.temporal.synthetic-warmup.sequence-coordinate.v1",
        input_fields=tuple(key for key in coordinate if key != "coordinate_digest"),
        name="temporal_synthetic_sequence_coordinate",
    )
    return coordinate


def build_temporal_synthetic_cell_descriptors() -> tuple[dict[str, Any], ...]:
    cells: list[dict[str, Any]] = []
    for cell_index, cell_id, fixture_id, horizon_id in TEMPORAL_SYNTHETIC_CELLS:
        cell: dict[str, Any] = {
            "cell_index": cell_index,
            "cell_id": cell_id,
            "fixture_id": fixture_id,
            "horizon_id": horizon_id,
            "sequence_issue_count": 961 if horizon_id == "FORWARD_61" else 3481,
            "replicate_count": SYNTHETIC_REPLICATES_PER_CELL,
        }
        cell["cell_digest"] = m4_v2_domain_digest(
            cell, domain="dehps.m4.v2.temporal.synthetic-warmup.cell.v1"
        )
        cells.append(validate_temporal_synthetic_cell_descriptor(cell))
    return tuple(cells)


def validate_temporal_synthetic_cell_descriptor(value: Any) -> dict[str, Any]:
    cell = dict(_mapping(value, name="temporal_synthetic_cell_descriptor"))
    _validate_nested("synthetic_warmup_cell_descriptor", cell)
    cell_index = _integer(cell["cell_index"], name="cell_index", minimum=0)
    if cell_index >= SYNTHETIC_CELL_COUNT:
        raise TemporalMarginalIncrementContractError(
            "temporal_synthetic_cell_index_out_of_range"
        )
    _, cell_id, fixture_id, horizon_id = TEMPORAL_SYNTHETIC_CELLS[cell_index]
    expected = {
        "cell_id": cell_id,
        "fixture_id": fixture_id,
        "horizon_id": horizon_id,
        "sequence_issue_count": 961 if horizon_id == "FORWARD_61" else 3481,
        "replicate_count": SYNTHETIC_REPLICATES_PER_CELL,
    }
    if any(cell.get(key) != item for key, item in expected.items()):
        raise TemporalMarginalIncrementContractError(
            "temporal_synthetic_cell_descriptor_mismatch"
        )
    _self_digest(
        cell,
        digest_field="cell_digest",
        domain="dehps.m4.v2.temporal.synthetic-warmup.cell.v1",
        input_fields=tuple(key for key in cell if key != "cell_digest"),
        name="temporal_synthetic_cell_descriptor",
    )
    return cell


def build_temporal_synthetic_replicate_commitment(
    *,
    sequence_coordinate: Mapping[str, Any],
    ordered_transition_row_digests: Sequence[str],
) -> dict[str, Any]:
    coordinate = validate_temporal_synthetic_sequence_coordinate(
        sequence_coordinate
    )
    row_digests = [
        _digest(item, name="transition_row_digest")
        for item in ordered_transition_row_digests
    ]
    if len(row_digests) != WARMUP_COUNT:
        raise TemporalMarginalIncrementContractError(
            "temporal_synthetic_transition_chain_count_mismatch"
        )
    commitment: dict[str, Any] = {
        "cell_index": coordinate["cell_index"],
        "cell_id": coordinate["cell_id"],
        "fixture_id": coordinate["fixture_id"],
        "horizon_id": coordinate["horizon_id"],
        "replicate_index": coordinate["replicate_index"],
        "sequence_seed_full_sha256": coordinate["sequence_seed_full_sha256"],
        "sequence_coordinate_digest": coordinate["coordinate_digest"],
        "transition_range": [WARMUP_START, WARMUP_END],
        "transition_count": WARMUP_COUNT,
        "transition_chain_digest": m4_v2_domain_digest(
            {"ordered_transition_row_digests": row_digests},
            domain="dehps.m4.v2.temporal.synthetic-warmup.transition-chain.v1",
        ),
    }
    commitment["replicate_digest"] = m4_v2_domain_digest(
        commitment,
        domain="dehps.m4.v2.temporal.synthetic-warmup.replicate.v1",
    )
    return validate_temporal_synthetic_replicate_commitment(
        commitment,
        sequence_coordinate=coordinate,
        ordered_transition_row_digests=row_digests,
    )


def validate_temporal_synthetic_replicate_commitment(
    value: Any,
    *,
    sequence_coordinate: Mapping[str, Any] | None = None,
    ordered_transition_row_digests: Sequence[str] | None = None,
) -> dict[str, Any]:
    commitment = dict(
        _mapping(value, name="temporal_synthetic_replicate_commitment")
    )
    _validate_nested("synthetic_warmup_replicate_commitment", commitment)
    if (
        commitment["transition_range"] != [WARMUP_START, WARMUP_END]
        or commitment["transition_count"] != WARMUP_COUNT
    ):
        raise TemporalMarginalIncrementContractError(
            "temporal_synthetic_replicate_transition_range_mismatch"
        )
    cell = _integer(commitment["cell_index"], name="cell_index", minimum=0)
    replicate = _integer(
        commitment["replicate_index"], name="replicate_index", minimum=0
    )
    if cell >= SYNTHETIC_CELL_COUNT or replicate >= SYNTHETIC_REPLICATES_PER_CELL:
        raise TemporalMarginalIncrementContractError(
            "temporal_synthetic_replicate_coordinate_out_of_range"
        )
    _, cell_id, fixture_id, horizon_id = TEMPORAL_SYNTHETIC_CELLS[cell]
    if (
        commitment["cell_id"] != cell_id
        or commitment["fixture_id"] != fixture_id
        or commitment["horizon_id"] != horizon_id
        or commitment["sequence_seed_full_sha256"]
        != _temporal_sequence_seed(
            cell_index=cell, cell_id=cell_id, replicate_index=replicate
        )
    ):
        raise TemporalMarginalIncrementContractError(
            "temporal_synthetic_replicate_cell_or_seed_mismatch"
        )
    if sequence_coordinate is not None:
        coordinate = validate_temporal_synthetic_sequence_coordinate(
            sequence_coordinate
        )
        equalities = (
            ("cell_index", "cell_index"),
            ("cell_id", "cell_id"),
            ("fixture_id", "fixture_id"),
            ("horizon_id", "horizon_id"),
            ("replicate_index", "replicate_index"),
            ("sequence_seed_full_sha256", "sequence_seed_full_sha256"),
            ("sequence_coordinate_digest", "coordinate_digest"),
        )
        if any(commitment[left] != coordinate[right] for left, right in equalities):
            raise TemporalMarginalIncrementContractError(
                "temporal_synthetic_replicate_coordinate_dereference_mismatch"
            )
    if ordered_transition_row_digests is not None:
        row_digests = [
            _digest(item, name="transition_row_digest")
            for item in ordered_transition_row_digests
        ]
        if len(row_digests) != WARMUP_COUNT or commitment[
            "transition_chain_digest"
        ] != m4_v2_domain_digest(
            {"ordered_transition_row_digests": row_digests},
            domain="dehps.m4.v2.temporal.synthetic-warmup.transition-chain.v1",
        ):
            raise TemporalMarginalIncrementContractError(
                "temporal_synthetic_replicate_transition_chain_mismatch"
            )
    _self_digest(
        commitment,
        digest_field="replicate_digest",
        domain="dehps.m4.v2.temporal.synthetic-warmup.replicate.v1",
        input_fields=tuple(key for key in commitment if key != "replicate_digest"),
        name="temporal_synthetic_replicate_commitment",
    )
    return commitment


def build_temporal_synthetic_replicate_index(
    rows: Sequence[Mapping[str, Any]], *, cell_manifest_digest: str
) -> dict[str, Any]:
    validated = [
        validate_temporal_synthetic_replicate_commitment(row) for row in rows
    ]
    row_digests = [row["replicate_digest"] for row in validated]
    index: dict[str, Any] = {
        "branch_id": TEMPORAL_BRANCH_ID,
        "cell_manifest_digest": _digest(
            cell_manifest_digest, name="cell_manifest_digest"
        ),
        "row_count": len(validated),
        "rows": validated,
        "row_digests_in_order": row_digests,
        "row_chain_digest": m4_v2_domain_digest(
            {"ordered_replicate_digests": row_digests},
            domain="dehps.m4.v2.temporal.synthetic-warmup.replicate-chain.v1",
        ),
        "replicates_per_cell": SYNTHETIC_REPLICATES_PER_CELL,
        "warmup_transition_count_per_replicate": WARMUP_COUNT,
        "warmup_alias_position_count": SYNTHETIC_WARMUP_ALIAS_POSITION_COUNT,
    }
    index["index_digest"] = m4_v2_domain_digest(
        {
            key: index[key]
            for key in (
                "branch_id",
                "cell_manifest_digest",
                "row_count",
                "replicates_per_cell",
                "warmup_transition_count_per_replicate",
                "warmup_alias_position_count",
                "row_chain_digest",
            )
        },
        domain="dehps.m4.v2.temporal.synthetic-warmup.replicate-index.v1",
    )
    return validate_temporal_synthetic_replicate_index(index)


def validate_temporal_synthetic_replicate_index(value: Any) -> dict[str, Any]:
    index = dict(_mapping(value, name="temporal_synthetic_replicate_index"))
    _validate_nested("synthetic_warmup_replicate_index", index)
    rows_raw = index["rows"]
    if not isinstance(rows_raw, list):
        raise TemporalMarginalIncrementContractError(
            "temporal_synthetic_replicate_index_rows_invalid"
        )
    rows = [
        validate_temporal_synthetic_replicate_commitment(row) for row in rows_raw
    ]
    expected_grid = [
        (cell, replicate)
        for cell in range(SYNTHETIC_CELL_COUNT)
        for replicate in range(SYNTHETIC_REPLICATES_PER_CELL)
    ]
    observed_grid = [
        (row["cell_index"], row["replicate_index"]) for row in rows
    ]
    row_digests = [row["replicate_digest"] for row in rows]
    expected_chain = m4_v2_domain_digest(
        {"ordered_replicate_digests": row_digests},
        domain="dehps.m4.v2.temporal.synthetic-warmup.replicate-chain.v1",
    )
    fixed = {
        "branch_id": TEMPORAL_BRANCH_ID,
        "row_count": SYNTHETIC_REPLICATE_COUNT,
        "replicates_per_cell": SYNTHETIC_REPLICATES_PER_CELL,
        "warmup_transition_count_per_replicate": WARMUP_COUNT,
        "warmup_alias_position_count": SYNTHETIC_WARMUP_ALIAS_POSITION_COUNT,
    }
    if (
        any(index.get(key) != item for key, item in fixed.items())
        or observed_grid != expected_grid
        or index["row_digests_in_order"] != row_digests
        or index["row_chain_digest"] != expected_chain
    ):
        raise TemporalMarginalIncrementContractError(
            "temporal_synthetic_replicate_index_grid_or_chain_mismatch"
        )
    _self_digest(
        index,
        digest_field="index_digest",
        domain="dehps.m4.v2.temporal.synthetic-warmup.replicate-index.v1",
        input_fields=(
            "branch_id",
            "cell_manifest_digest",
            "row_count",
            "replicates_per_cell",
            "warmup_transition_count_per_replicate",
            "warmup_alias_position_count",
            "row_chain_digest",
        ),
        name="temporal_synthetic_replicate_index",
    )
    return index


def _validate_temporal_health_summary_lineage(
    health_body: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    health = _mapping(health_body, name="temporal_health_body")
    summaries = _validate_nested(
        "health_cell_summary[14]", health.get("cell_summaries")
    )
    summary_digests: list[str] = []
    failed_cell_ids: list[str] = []
    for index, summary in enumerate(summaries):
        if (
            summary["cell_index"] != index
            or summary["cell_id"] != TEMPORAL_SYNTHETIC_CELLS[index][1]
            or summary["horizon"] != TEMPORAL_SYNTHETIC_CELLS[index][3]
            or summary["replicate_count"] != SYNTHETIC_REPLICATES_PER_CELL
            or not isinstance(summary["threshold_pass"], bool)
        ):
            raise TemporalMarginalIncrementContractError(
                "temporal_health_cell_summary_coordinate_mismatch"
            )
        _self_digest(
            summary,
            digest_field="cell_summary_digest",
            domain="dehps.m4.v2.temporal.health-cell-summary.v2",
            input_fields=tuple(
                key for key in summary if key != "cell_summary_digest"
            ),
            name="temporal_health_cell_summary",
        )
        summary_digests.append(summary["cell_summary_digest"])
        if summary["threshold_pass"] is False:
            failed_cell_ids.append(summary["cell_id"])
    expected_chain = m4_v2_domain_digest(
        {"ordered_cell_summary_digests": summary_digests},
        domain="dehps.m4.v2.temporal.health-cell-summary-chain.v2",
    )
    if (
        health.get("cell_summary_chain_digest") != expected_chain
        or health.get("failed_cell_ids") != failed_cell_ids
    ):
        raise TemporalMarginalIncrementContractError(
            "temporal_health_cell_summary_owner_mismatch"
        )
    return tuple(summaries)


def validate_temporal_synthetic_warmup_application(
    value: Any,
    *,
    health_body: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    application = dict(
        _mapping(value, name="temporal_synthetic_warmup_application")
    )
    _validate_nested("synthetic_warmup_application", application)
    if (
        application.get("branch_id") != TEMPORAL_BRANCH_ID
        or application.get("owner_artifact_type") != TEMPORAL_HEALTH_ARTIFACT
        or application.get("fixture_source_digest") != FIXTURE_SOURCE_DIGEST
        or application.get("synthetic_root_seed_full_sha256")
        != TEMPORAL_SYNTHETIC_ROOT_SEED_FULL_SHA256
        or application.get("support_model_id") != SUPPORT_MODEL_ID
        or application.get("cell_count") != SYNTHETIC_CELL_COUNT
        or application.get("replicates_per_cell") != SYNTHETIC_REPLICATES_PER_CELL
        or application.get("replicate_count") != SYNTHETIC_REPLICATE_COUNT
        or application.get("warmup_transition_range") != [WARMUP_START, WARMUP_END]
        or application.get("warmup_transition_count_per_replicate") != WARMUP_COUNT
        or application.get("warmup_alias_position_count")
        != SYNTHETIC_WARMUP_ALIAS_POSITION_COUNT
        or application.get("bootstrap_child_count")
        != SYNTHETIC_BOOTSTRAP_CHILD_COUNT
        or application.get("synthetic_generated_issue_count")
        != SYNTHETIC_GENERATED_ISSUE_COUNT
    ):
        raise TemporalMarginalIncrementContractError(
            "temporal_synthetic_application_fixed_identity_mismatch"
        )
    cells_raw = application.get("cells")
    if not isinstance(cells_raw, list) or len(cells_raw) != SYNTHETIC_CELL_COUNT:
        raise TemporalMarginalIncrementContractError(
            "temporal_synthetic_cell_manifest_mismatch"
        )
    cells = [
        validate_temporal_synthetic_cell_descriptor(cell) for cell in cells_raw
    ]
    observed = [
        (
            cell["cell_index"],
            cell["cell_id"],
            cell["fixture_id"],
            cell["horizon_id"],
        )
        for cell in cells
    ]
    if observed != list(TEMPORAL_SYNTHETIC_CELLS):
        raise TemporalMarginalIncrementContractError(
            "temporal_synthetic_cell_order_or_identity_mismatch"
        )
    ordered_cell_digests = [cell["cell_digest"] for cell in cells]
    cell_manifest_digest = m4_v2_domain_digest(
        {"ordered_cell_digests": ordered_cell_digests},
        domain="dehps.m4.v2.temporal.synthetic-warmup.cell-manifest.v1",
    )
    replicate_index = validate_temporal_synthetic_replicate_index(
        application.get("replicate_index")
    )
    if (
        application.get("ordered_cell_digests") != ordered_cell_digests
        or application.get("cell_manifest_digest") != cell_manifest_digest
        or replicate_index["cell_manifest_digest"] != cell_manifest_digest
        or application.get("replicate_index_digest")
        != replicate_index["index_digest"]
    ):
        raise TemporalMarginalIncrementContractError(
            "temporal_synthetic_cell_or_replicate_owner_mismatch"
        )
    horizons_raw = application.get("horizons")
    if not isinstance(horizons_raw, list) or len(horizons_raw) != 2:
        raise TemporalMarginalIncrementContractError(
            "temporal_synthetic_horizon_manifest_mismatch"
        )
    horizons: list[dict[str, Any]] = []
    expected_horizon_indices = (
        ("FORWARD_61", list(range(0, SYNTHETIC_CELL_COUNT, 2))),
        ("HISTORICAL_2581", list(range(1, SYNTHETIC_CELL_COUNT, 2))),
    )
    for raw, (horizon_id, cell_indices) in zip(
        horizons_raw, expected_horizon_indices, strict=True
    ):
        horizon = dict(_mapping(raw, name="temporal_synthetic_horizon_summary"))
        _validate_nested("synthetic_horizon_summary", horizon)
        if (
            horizon["horizon_id"] != horizon_id
            or horizon["ordered_cell_indices"] != cell_indices
            or horizon["cell_count"] != 7
            or horizon["replicate_count"] != 3584
            or horizon["warmup_alias_position_count"] != 3_222_016
        ):
            raise TemporalMarginalIncrementContractError(
                "temporal_synthetic_horizon_partition_mismatch"
            )
        _self_digest(
            horizon,
            digest_field="horizon_digest",
            domain="dehps.m4.v2.temporal.synthetic-warmup.horizon.v1",
            input_fields=tuple(
                key for key in horizon if key != "horizon_digest"
            ),
            name="temporal_synthetic_horizon_summary",
        )
        horizons.append(horizon)
    ordered_horizon_digests = [item["horizon_digest"] for item in horizons]
    if (
        application.get("ordered_horizon_digests")
        != ordered_horizon_digests
        or application.get("horizon_summary_chain_digest")
        != m4_v2_domain_digest(
            {"ordered_horizon_digests": ordered_horizon_digests},
            domain="dehps.m4.v2.temporal.synthetic-warmup.horizon-chain.v1",
        )
    ):
        raise TemporalMarginalIncrementContractError(
            "temporal_synthetic_horizon_chain_mismatch"
        )
    application_digest_fields = tuple(
        key
        for key in application
        if key not in {"application_digest", "cells", "replicate_index"}
    )
    _self_digest(
        application,
        digest_field="application_digest",
        domain="dehps.m4.v2.temporal.synthetic-warmup.application.v1",
        input_fields=application_digest_fields,
        name="temporal_synthetic_warmup_application",
    )
    if health_body is not None:
        health = _mapping(health_body, name="temporal_health_body")
        equalities = {
            "branch_id": TEMPORAL_BRANCH_ID,
            "source_contract_digest": application.get("source_contract_digest"),
            "preregistration_artifact_digest": application.get(
                "preregistration_artifact_digest"
            ),
            "synthetic_replicate_count": SYNTHETIC_REPLICATE_COUNT,
            "synthetic_generated_issue_count": SYNTHETIC_GENERATED_ISSUE_COUNT,
            "bootstrap_resample_count": SYNTHETIC_BOOTSTRAP_CHILD_COUNT,
            "warmup_alias_position_count": SYNTHETIC_WARMUP_ALIAS_POSITION_COUNT,
            "cell_summary_chain_digest": application.get(
                "cell_summary_chain_digest"
            ),
        }
        if any(health.get(key) != expected for key, expected in equalities.items()):
            raise TemporalMarginalIncrementContractError(
                "temporal_synthetic_health_owner_equality_mismatch"
            )
        if (
            health.get("synthetic_warmup_application_digest_or_null")
            != application.get("application_digest")
            or not isinstance(health.get("synthetic_warmup_application_or_null"), Mapping)
            or health["synthetic_warmup_application_or_null"].get(
                "application_digest"
            )
            != application.get("application_digest")
        ):
            raise TemporalMarginalIncrementContractError(
                "temporal_synthetic_application_owner_digest_mismatch"
            )
        health_summaries_raw = health.get("cell_summaries")
        if not isinstance(health_summaries_raw, list):
            raise TemporalMarginalIncrementContractError(
                "temporal_health_cell_summaries_missing"
            )
        health_summaries = _validate_nested(
            "health_cell_summary[14]", health_summaries_raw
        )
        summary_digests: list[str] = []
        for index, summary in enumerate(health_summaries):
            if (
                summary["cell_index"] != index
                or summary["cell_id"] != TEMPORAL_SYNTHETIC_CELLS[index][1]
                or summary["horizon"] != TEMPORAL_SYNTHETIC_CELLS[index][3]
                or summary["replicate_count"] != SYNTHETIC_REPLICATES_PER_CELL
            ):
                raise TemporalMarginalIncrementContractError(
                    "temporal_health_cell_summary_coordinate_mismatch"
                )
            _self_digest(
                summary,
                digest_field="cell_summary_digest",
                domain="dehps.m4.v2.temporal.health-cell-summary.v2",
                input_fields=tuple(
                    key for key in summary if key != "cell_summary_digest"
                ),
                name="temporal_health_cell_summary",
            )
            summary_digests.append(summary["cell_summary_digest"])
        expected_summary_chain = m4_v2_domain_digest(
            {"ordered_cell_summary_digests": summary_digests},
            domain="dehps.m4.v2.temporal.health-cell-summary-chain.v2",
        )
        if (
            application.get("cell_summary_chain_digest")
            != expected_summary_chain
            or health.get("cell_summary_chain_digest") != expected_summary_chain
            or horizons[0]["ordered_cell_summary_digests"]
            != summary_digests[0::2]
            or horizons[1]["ordered_cell_summary_digests"]
            != summary_digests[1::2]
        ):
            raise TemporalMarginalIncrementContractError(
                "temporal_health_horizon_summary_owner_mismatch"
            )
    return application


def validate_temporal_candidate_lineage(body: Mapping[str, Any]) -> dict[str, Any]:
    candidate = dict(_mapping(body, name="temporal_candidate_body"))
    if (
        candidate.get("branch_id") != TEMPORAL_BRANCH_ID
        or candidate.get("model_id") != TEMPORAL_MODEL_ID
        or candidate.get("support_model_id") != SUPPORT_MODEL_ID
        or candidate.get("historical_fold_count") != EVALUATION_COUNT
        or candidate.get("production_action") != "none"
    ):
        raise TemporalMarginalIncrementContractError(
            "temporal_candidate_fixed_identity_mismatch"
        )
    warmup = validate_temporal_warmup_index(
        candidate.get("historical_warmup_index"),
        expected_rule_digest=candidate.get("historical_warmup_index", {}).get(
            "rule_digest"
        )
        if isinstance(candidate.get("historical_warmup_index"), Mapping)
        else None,
    )
    accepted = validate_accepted_temporal_evaluation_index(
        candidate.get("accepted_temporal_evaluation_index")
    )
    composite = validate_temporal_composite_view(
        candidate.get("composite_temporal_view")
    )
    if (
        candidate.get("warmup_index_digest") != warmup["warmup_index_digest"]
        or candidate.get("accepted_temporal_evaluation_index_digest")
        != accepted["accepted_temporal_evaluation_index_digest"]
        or candidate.get("composite_view_digest") != composite["composite_view_digest"]
        or composite["warmup_index_digest"] != warmup["warmup_index_digest"]
        or composite["accepted_temporal_evaluation_index_digest"]
        != accepted["accepted_temporal_evaluation_index_digest"]
    ):
        raise TemporalMarginalIncrementContractError(
            "temporal_candidate_nested_owner_equality_mismatch"
        )
    return candidate


def validate_accepted_parent_raw_p_lineage(
    *,
    parent_branch_id: str,
    terminal_decision: str,
    accepted_for_downstream_baseline: bool,
    historical_artifact_digest: str,
    historical_registration_digest: str,
    producer_execution_id: str,
    replay_status: str,
    raw_primary_p_value: float,
) -> float:
    if (
        parent_branch_id != "MARGINAL_STATIC"
        or terminal_decision != "BRANCH_INFORMATION_ACCEPTED"
        or accepted_for_downstream_baseline is not True
        or historical_artifact_digest != MARGINAL_RAW_P_ARTIFACT_DIGEST
        or historical_registration_digest != MARGINAL_RAW_P_REGISTRATION_DIGEST
        or replay_status != "REGISTERED_REPLAY_VERIFIED"
    ):
        raise TemporalMarginalIncrementContractError(
            "accepted_parent_raw_p_lineage_not_verified"
        )
    _digest(historical_artifact_digest, name="historical_artifact_digest")
    _digest(historical_registration_digest, name="historical_registration_digest")
    _execution_id(producer_execution_id, name="producer_execution_id")
    if (
        isinstance(raw_primary_p_value, bool)
        or not isinstance(raw_primary_p_value, (int, float))
        or not math.isfinite(float(raw_primary_p_value))
        or not 0.0 <= float(raw_primary_p_value) <= 1.0
    ):
        raise TemporalMarginalIncrementContractError("accepted_parent_raw_p_invalid")
    return float(raw_primary_p_value)


def validate_temporal_holm_family(
    value: Any,
    *,
    marginal_raw_p_value: float,
    temporal_raw_p_value: float,
) -> dict[str, float]:
    family = dict(_mapping(value, name="temporal_holm_family"))
    _exact_fields(
        family,
        ("MARGINAL_STATIC", "TEMPORAL_MARGINAL_INCREMENT", "JOINT_RESIDUAL_INCREMENT"),
        name="temporal_holm_family",
    )
    for branch_id, raw_p in family.items():
        if (
            isinstance(raw_p, bool)
            or not isinstance(raw_p, (int, float))
            or not math.isfinite(float(raw_p))
            or not 0.0 <= float(raw_p) <= 1.0
        ):
            raise TemporalMarginalIncrementContractError(
                f"temporal_holm_raw_p_invalid:{branch_id}"
            )
    if (
        float(family["MARGINAL_STATIC"]) != float(marginal_raw_p_value)
        or float(family[TEMPORAL_BRANCH_ID]) != float(temporal_raw_p_value)
        or float(family["JOINT_RESIDUAL_INCREMENT"]) != 1.0
    ):
        raise TemporalMarginalIncrementContractError(
            "temporal_holm_preregistered_joint_not_run_slot_mismatch"
        )
    return {key: float(item) for key, item in family.items()}


def _validate_parent_decision_and_replay(
    *,
    decision_artifact: Mapping[str, Any],
    replay_artifact: Mapping[str, Any],
    expected_branch_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate an upstream terminal pair without reading scientific payloads."""

    try:
        decision = M4V2BranchDecisionArtifact.from_dict(decision_artifact).to_dict()
        replay = M4V2BranchDecisionReplayArtifact.from_dict(replay_artifact).to_dict()
    except Exception as exc:
        raise TemporalMarginalIncrementContractError(
            "temporal_parent_decision_replay_schema_invalid"
        ) from exc
    decision_body = decision["body"]
    replay_body = replay["body"]
    if (
        decision_body.get("measurement_contract_key") != MEASUREMENT_CONTRACT_KEY
        or decision_body.get("measurement_contract_digest")
        != MEASUREMENT_CONTRACT_DIGEST
        or decision_body.get("branch_id") != expected_branch_id
        or replay_body.get("measurement_contract_key") != MEASUREMENT_CONTRACT_KEY
        or replay_body.get("measurement_contract_digest")
        != MEASUREMENT_CONTRACT_DIGEST
        or replay_body.get("branch_id") != expected_branch_id
        or replay_body.get("decision_artifact_digest")
        != decision["artifact_digest"]
        or replay_body.get("decision_producer_task_key")
        != decision_body.get("producer_task_key")
        or replay_body.get("decision_producer_execution_id")
        != decision_body.get("producer_execution_id")
        or replay_body.get("replay_status") != "REGISTERED_REPLAY_VERIFIED"
        or replay_body.get("source_integrity_verified") is not True
        or replay_body.get("registered_content_verified") is not True
        or replay_body.get("workload_rerun") is not False
    ):
        raise TemporalMarginalIncrementContractError(
            "temporal_parent_decision_replay_identity_mismatch"
        )
    terminal = decision_body.get("terminal_decision")
    fixed_mapping: dict[str, tuple[Any, str, str, tuple[str, ...], bool]] = {
        "BRANCH_INFORMATION_ACCEPTED": (
            "BRANCH_INFORMATION_ACCEPTED",
            "COMPLETE",
            "PASS",
            ("POSITIVE",),
            True,
        ),
        "NO_DETECTABLE_INFORMATION": (
            "NO_DETECTABLE_INFORMATION",
            "COMPLETE",
            "PASS",
            ("NEGATIVE",),
            False,
        ),
        "INCONCLUSIVE_DUE_TO_POWER": (
            "INCONCLUSIVE_DUE_TO_POWER",
            "COMPLETE",
            "PASS",
            ("INCONCLUSIVE",),
            False,
        ),
        "MEASUREMENT_REPAIR_REQUIRED": (
            "MEASUREMENT_REPAIR_REQUIRED",
            "REPAIR_REQUIRED",
            "REPAIR",
            ("NOT_RUN", "INCONCLUSIVE"),
            False,
        ),
        "INVALID_EXECUTION": (
            "INVALID_EXECUTION",
            "INVALID",
            "INCONCLUSIVE",
            ("NOT_RUN", "INCONCLUSIVE"),
            False,
        ),
        "NOT_EVALUABLE_PARENT_NOT_ACCEPTED": (
            None,
            "NOT_RUN_PARENT_NOT_ACCEPTED",
            "INCONCLUSIVE",
            ("NOT_RUN",),
            False,
        ),
    }
    try:
        scientific, evaluation, health, historical, accepted = fixed_mapping[terminal]
    except KeyError as exc:
        raise TemporalMarginalIncrementContractError(
            "temporal_parent_terminal_unknown"
        ) from exc
    if (
        decision_body.get("scientific_decision") != scientific
        or decision_body.get("evaluation_status") != evaluation
        or decision_body.get("measurement_health") != health
        or decision_body.get("historical_evidence") not in historical
        or decision_body.get("accepted_for_downstream_baseline") is not accepted
    ):
        raise TemporalMarginalIncrementContractError(
            "temporal_parent_terminal_mapping_mismatch"
        )
    return decision, replay


def build_temporal_parent_not_accepted_path(
    *,
    source_contract_digest: str,
    preregistration_artifact_digest: str,
    marginal_decision_artifact: Mapping[str, Any],
    marginal_replay_artifact: Mapping[str, Any],
    producer_execution_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build only Decision + Completion for the zero-compute parent stop path."""

    source_digest = _digest(source_contract_digest, name="source_contract_digest")
    prereg_digest = _digest(
        preregistration_artifact_digest,
        name="preregistration_artifact_digest",
    )
    producer_id = _execution_id(
        producer_execution_id, name="producer_execution_id"
    )
    parent_decision, parent_replay = _validate_parent_decision_and_replay(
        decision_artifact=marginal_decision_artifact,
        replay_artifact=marginal_replay_artifact,
        expected_branch_id=MARGINAL_BRANCH_ID,
    )
    if (
        parent_decision["body"]["terminal_decision"]
        == "BRANCH_INFORMATION_ACCEPTED"
        and parent_decision["body"]["accepted_for_downstream_baseline"] is True
    ):
        raise TemporalMarginalIncrementContractError(
            "temporal_parent_accepted_requires_frozen_scientific_workload"
        )
    decision_body: dict[str, Any] = {
        "measurement_contract_key": MEASUREMENT_CONTRACT_KEY,
        "measurement_contract_digest": MEASUREMENT_CONTRACT_DIGEST,
        "branch_id": TEMPORAL_BRANCH_ID,
        "estimand_digest": TEMPORAL_ESTIMAND_DIGEST,
        "decision_path": "PARENT_NOT_ACCEPTED",
        "terminal_decision": "NOT_EVALUABLE_PARENT_NOT_ACCEPTED",
        "scientific_decision": None,
        "evaluation_status": "NOT_RUN_PARENT_NOT_ACCEPTED",
        "measurement_health": "INCONCLUSIVE",
        "historical_evidence": "NOT_RUN",
        "accepted_for_downstream_baseline": False,
        "accepted_model_artifact_digest": None,
        "baseline_artifact_digest": None,
        "baseline_source_model_artifact_digest": None,
        "producer_task_key": TEMPORAL_PRODUCER_TASK_KEY,
        "producer_execution_id": producer_id,
    }
    decision = build_temporal_artifact(
        artifact_type=BRANCH_DECISION_ARTIFACT,
        body=decision_body,
        parent_digests=(
            source_digest,
            prereg_digest,
            parent_decision["artifact_digest"],
            parent_replay["artifact_digest"],
        ),
    )
    completion_body: dict[str, Any] = {
        "status": "COMPLETE",
        "measurement_contract_key": MEASUREMENT_CONTRACT_KEY,
        "measurement_contract_digest": MEASUREMENT_CONTRACT_DIGEST,
        "branch_id": TEMPORAL_BRANCH_ID,
        "estimand_digest": TEMPORAL_ESTIMAND_DIGEST,
        "decision_path": "PARENT_NOT_ACCEPTED",
        "source_contract_digest": source_digest,
        "preregistration_artifact_digest": prereg_digest,
        "registered_artifact_digests_in_order": [decision["artifact_digest"]],
        "decision_artifact_digest": decision["artifact_digest"],
        "terminal_fact": TEMPORAL_TERMINAL_FACT,
        "completion_fact": TEMPORAL_PRODUCER_COMPLETION_FACT,
        "registration_count_including_mainline_execution": 3,
        "historical_outcomes_read": 0,
        "synthetic_replicate_count": 0,
        "warmup_transition_count_per_replicate": 0,
        "warmup_alias_position_count": 0,
        "historical_fold_count": 0,
        "bootstrap_resample_count": 0,
        "evidence_created": False,
        "promotion_gate_opened": False,
        "production_action": "none",
        "exact_consumer": TEMPORAL_REPLAY_TASK_KEY,
    }
    completion = build_temporal_artifact(
        artifact_type=TEMPORAL_COMPLETION_ARTIFACT,
        body=completion_body,
        parent_digests=(source_digest, prereg_digest, decision["artifact_digest"]),
    )
    validate_temporal_path_artifacts(
        "PARENT_NOT_ACCEPTED", (decision, completion)
    )
    return decision, completion


def build_temporal_branch_replay(
    *,
    source_contract_digest: str,
    decision_artifact: Mapping[str, Any],
    decision_registration_digest: str,
    decision_producer_execution_artifact_digest: str,
    replay_execution_id: str,
) -> dict[str, Any]:
    """Build the later read-only registered replay; workload_rerun is fixed false."""

    source_digest = _digest(source_contract_digest, name="source_contract_digest")
    registration_digest = _digest(
        decision_registration_digest, name="decision_registration_digest"
    )
    producer_execution_artifact_digest = _digest(
        decision_producer_execution_artifact_digest,
        name="decision_producer_execution_artifact_digest",
    )
    replay_id = _execution_id(replay_execution_id, name="replay_execution_id")
    try:
        decision = M4V2BranchDecisionArtifact.from_dict(decision_artifact)
    except Exception as exc:
        raise TemporalMarginalIncrementContractError(
            "temporal_replay_decision_schema_invalid"
        ) from exc
    decision_body = decision.to_body()
    if (
        decision_body.get("branch_id") != TEMPORAL_BRANCH_ID
        or decision_body.get("measurement_contract_key")
        != MEASUREMENT_CONTRACT_KEY
        or decision_body.get("measurement_contract_digest")
        != MEASUREMENT_CONTRACT_DIGEST
        or decision_body.get("producer_task_key") != TEMPORAL_PRODUCER_TASK_KEY
        or not decision.parent_digests
        or decision.parent_digests[0] != source_digest
    ):
        raise TemporalMarginalIncrementContractError(
            "temporal_replay_decision_identity_mismatch"
        )
    replay = M4V2BranchDecisionReplayArtifact(
        measurement_contract_key=MEASUREMENT_CONTRACT_KEY,
        measurement_contract_digest=MEASUREMENT_CONTRACT_DIGEST,
        branch_id=TEMPORAL_BRANCH_ID,
        decision_artifact_digest=decision.artifact_digest,
        decision_registration_digest=registration_digest,
        decision_producer_task_key=TEMPORAL_PRODUCER_TASK_KEY,
        decision_producer_execution_id=decision_body["producer_execution_id"],
        replay_task_key=TEMPORAL_REPLAY_TASK_KEY,
        replay_execution_id=replay_id,
        replay_status="REGISTERED_REPLAY_VERIFIED",
        source_integrity_verified=True,
        registered_content_verified=True,
        workload_rerun=False,
        parent_digests=(
            source_digest,
            decision.artifact_digest,
            registration_digest,
            producer_execution_artifact_digest,
        ),
    )
    return validate_temporal_branch_replay(replay.to_dict())


def validate_temporal_branch_replay(value: Any) -> dict[str, Any]:
    envelope = validate_m4_v2_artifact_envelope(
        value, expected_artifact_type=BRANCH_REPLAY_ARTIFACT
    )
    typed = M4V2BranchDecisionReplayArtifact.from_dict(envelope)
    body = typed.to_body()
    if (
        body.get("branch_id") != TEMPORAL_BRANCH_ID
        or body.get("measurement_contract_key") != MEASUREMENT_CONTRACT_KEY
        or body.get("measurement_contract_digest") != MEASUREMENT_CONTRACT_DIGEST
        or body.get("replay_task_key") != TEMPORAL_REPLAY_TASK_KEY
        or body.get("replay_status") != "REGISTERED_REPLAY_VERIFIED"
        or body.get("source_integrity_verified") is not True
        or body.get("registered_content_verified") is not True
        or body.get("workload_rerun") is not False
    ):
        raise TemporalMarginalIncrementContractError(
            "temporal_branch_replay_contract_mismatch"
        )
    return typed.to_dict()


def _validate_temporal_artifact_body(
    artifact_type: str, body: Mapping[str, Any]
) -> None:
    if body.get("measurement_contract_key") != MEASUREMENT_CONTRACT_KEY or body.get(
        "measurement_contract_digest"
    ) != MEASUREMENT_CONTRACT_DIGEST:
        raise TemporalMarginalIncrementContractError(
            "temporal_measurement_contract_identity_mismatch"
        )
    if body.get("branch_id") != TEMPORAL_BRANCH_ID:
        raise TemporalMarginalIncrementContractError("temporal_branch_identity_mismatch")
    if (
        artifact_type != BRANCH_REPLAY_ARTIFACT
        and body.get("estimand_digest") != TEMPORAL_ESTIMAND_DIGEST
    ):
        raise TemporalMarginalIncrementContractError("temporal_estimand_mismatch")
    if "dataset_content_digest" in body and body.get(
        "dataset_content_digest"
    ) != DATASET_CONTENT_DIGEST:
        raise TemporalMarginalIncrementContractError(
            "temporal_dataset_content_digest_mismatch"
        )
    if "fold_manifest_digest" in body and body.get(
        "fold_manifest_digest"
    ) != FOLD_MANIFEST_DIGEST:
        raise TemporalMarginalIncrementContractError(
            "temporal_fold_manifest_digest_mismatch"
        )
    if "production_action" in body and body.get("production_action") != "none":
        raise TemporalMarginalIncrementContractError("temporal_production_action_forbidden")
    if artifact_type == TEMPORAL_DESIGN_ARTIFACT:
        if (
            body.get("status") != "FROZEN"
            or body.get("exact_consumer") != TEMPORAL_PREREGISTRATION_TASK_KEY
            or body.get("historical_outcomes_read") != 0
            or body.get("scientific_computation") != 0
            or body.get("evidence_created") is not False
        ):
            raise TemporalMarginalIncrementContractError(
                "temporal_design_fixed_contract_mismatch"
            )
    elif artifact_type == TEMPORAL_PREREGISTRATION_ARTIFACT:
        if (
            body.get("status") != "FROZEN"
            or body.get("support_model_id") != SUPPORT_MODEL_ID
            or body.get("warmup_request_payload_digest")
            != WARMUP_REQUEST_PAYLOAD_DIGEST
            or body.get("execution_authorized") is not False
            or body.get("result_payload_reads") != 0
            or body.get("historical_outcomes_read") != 0
            or body.get("scientific_computation") != 0
            or body.get("evidence_created") is not False
            or body.get("planned_counts") != dict(PLANNED_COUNTS)
            or body.get("exact_consumer") != TEMPORAL_PRODUCER_TASK_KEY
        ):
            raise TemporalMarginalIncrementContractError(
                "temporal_preregistration_fixed_contract_mismatch"
            )
        rule = validate_transition_local_warmup_rule(
            body.get("transition_local_warmup_rule")
        )
        if body.get("transition_local_warmup_rule_digest") != rule["rule_digest"]:
            raise TemporalMarginalIncrementContractError(
                "temporal_preregistration_warmup_rule_owner_mismatch"
            )
    elif artifact_type == TEMPORAL_CANDIDATE_ARTIFACT:
        if body.get("status") != "COMPLETE":
            raise TemporalMarginalIncrementContractError(
                "temporal_candidate_status_mismatch"
            )
        validate_temporal_candidate_lineage(body)
        if "probability_capsule_index" in body:
            from .temporal_probability_capsule import (
                EVALUATOR_CONTRACT_DIGEST,
                validate_probability_capsule_index,
            )

            capsule = validate_probability_capsule_index(
                body.get("probability_capsule_index")
            )
            if (
                body.get("probability_capsule_index_digest")
                != capsule["index_digest"]
                or body.get("probability_capsule_evaluator_contract_digest")
                != EVALUATOR_CONTRACT_DIGEST
                or body.get("source_contract_digest")
                != capsule["producer_source_contract_digest"]
            ):
                raise TemporalMarginalIncrementContractError(
                    "temporal_candidate_v3_capsule_owner_mismatch"
                )
    elif artifact_type == TEMPORAL_HEALTH_ARTIFACT:
        path = body.get("decision_path")
        health_by_path = {
            "EVALUATED_COMPLETE": "PASS",
            "IDENTITY_VALID_HEALTH_REPAIR": "REPAIR",
            "IDENTITY_VALID_HISTORICAL_REPAIR": "PASS",
            "IDENTITY_VALID_HISTORICAL_INVALID": "PASS",
        }
        if (
            body.get("status") != "COMPLETE"
            or path not in health_by_path
            or body.get("measurement_health") != health_by_path[path]
            or body.get("repair_required")
            is not (path == "IDENTITY_VALID_HEALTH_REPAIR")
        ):
            raise TemporalMarginalIncrementContractError(
                "temporal_health_path_mapping_mismatch"
            )
        _validate_temporal_health_summary_lineage(body)
        application = body.get("synthetic_warmup_application_or_null")
        if (application is None) is not (
            body.get("synthetic_warmup_application_digest_or_null") is None
        ):
            raise TemporalMarginalIncrementContractError(
                "temporal_synthetic_application_nullability_mismatch"
            )
        if application is not None:
            validate_temporal_synthetic_warmup_application(
                application, health_body=body
            )
            if body.get("outer_evaluation_issue_count") != (
                SYNTHETIC_OUTER_EVALUATION_ISSUE_COUNT
            ):
                raise TemporalMarginalIncrementContractError(
                    "temporal_health_outer_evaluation_count_mismatch"
                )
    elif artifact_type == TEMPORAL_HISTORICAL_ARTIFACT:
        if (
            body.get("status") != "COMPLETE"
            or body.get("decision_path") != "EVALUATED_COMPLETE"
            or body.get("marginal_raw_p_artifact_digest")
            != MARGINAL_RAW_P_ARTIFACT_DIGEST
            or body.get("score_count") != EVALUATION_COUNT
            or body.get("historical_child_count") != HISTORICAL_CHILD_COUNT
        ):
            raise TemporalMarginalIncrementContractError(
                "temporal_historical_counter_mismatch"
            )
        validate_temporal_holm_family(
            body.get("holm_family_raw_p_values"),
            marginal_raw_p_value=body.get("holm_family_raw_p_values", {}).get(
                "MARGINAL_STATIC"
            ),
            temporal_raw_p_value=body.get("raw_primary_p_value"),
        )
    elif artifact_type == TEMPORAL_COMPLETION_ARTIFACT:
        path = body.get("decision_path")
        if path not in DECISION_PATHS:
            raise TemporalMarginalIncrementContractError(
                "temporal_completion_decision_path_mismatch"
            )
        count_fields = (
            "historical_outcomes_read",
            "synthetic_replicate_count",
            "warmup_transition_count_per_replicate",
            "warmup_alias_position_count",
            "historical_fold_count",
            "bootstrap_resample_count",
        )
        for field in count_fields:
            _integer(body.get(field), name=field, minimum=0)
        if (
            body.get("status") != "COMPLETE"
            or body.get("evidence_created") is not False
            or body.get("promotion_gate_opened") is not False
            or body.get("exact_consumer") != TEMPORAL_REPLAY_TASK_KEY
            or body.get("terminal_fact") != TEMPORAL_TERMINAL_FACT
            or body.get("completion_fact") != TEMPORAL_PRODUCER_COMPLETION_FACT
            or body.get("registration_count_including_mainline_execution")
            != temporal_registration_plan(path).registration_count_including_mainline_execution
        ):
            raise TemporalMarginalIncrementContractError(
                "temporal_completion_fixed_contract_mismatch"
            )
        if path == "PARENT_NOT_ACCEPTED" and any(
            body[field] != 0 for field in count_fields
        ):
            raise TemporalMarginalIncrementContractError(
                "temporal_parent_not_accepted_work_counter_nonzero"
            )
        if path == "EVALUATED_COMPLETE":
            evaluated_counts = {
                "synthetic_replicate_count": SYNTHETIC_REPLICATE_COUNT,
                "warmup_transition_count_per_replicate": WARMUP_COUNT,
                "warmup_alias_position_count": SYNTHETIC_WARMUP_ALIAS_POSITION_COUNT,
                "historical_fold_count": EVALUATION_COUNT,
                "bootstrap_resample_count": SYNTHETIC_BOOTSTRAP_CHILD_COUNT,
            }
            if any(body.get(key) != item for key, item in evaluated_counts.items()):
                raise TemporalMarginalIncrementContractError(
                    "temporal_evaluated_completion_counter_mismatch"
                )
    elif artifact_type == TEMPORAL_FAILURE_ARTIFACT:
        path = body.get("decision_path")
        expected_failure = {
            "IDENTITY_VALID_HEALTH_INVALID": ("HEALTH", False, False),
            "IDENTITY_VALID_HISTORICAL_REPAIR": ("HISTORICAL", True, True),
            "IDENTITY_VALID_HISTORICAL_INVALID": ("HISTORICAL", False, True),
        }
        if path not in expected_failure:
            raise TemporalMarginalIncrementContractError(
                "temporal_failure_decision_path_mismatch"
            )
        stage, repairable, historical_started = expected_failure[path]
        if (
            body.get("status") != "FAILED"
            or body.get("failure_stage") != stage
            or body.get("repairable") is not repairable
            or body.get("scientific_execution_started") is not True
            or body.get("historical_started") is not historical_started
            or body.get("partial_evidence_created") is not False
        ):
            raise TemporalMarginalIncrementContractError(
                "temporal_failure_fixed_mapping_mismatch"
            )
    elif artifact_type == BRANCH_REPLAY_ARTIFACT and (
        body.get("replay_status") != "REGISTERED_REPLAY_VERIFIED"
        or body.get("workload_rerun") is not False
    ):
        raise TemporalMarginalIncrementContractError(
            "temporal_replay_workload_boundary_breached"
        )


def build_temporal_artifact(
    *,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
) -> dict[str, Any]:
    if artifact_type not in TEMPORAL_ARTIFACT_TYPES:
        raise TemporalMarginalIncrementContractError(
            f"temporal_artifact_type_not_authorized:{artifact_type}"
        )
    body_mapping = dict(_mapping(body, name="temporal_artifact_body"))
    _validate_temporal_artifact_body(artifact_type, body_mapping)
    parents = tuple(_digest(item, name="parent_digest") for item in parent_digests)
    envelope = m4_v2_build_artifact_envelope(
        artifact_type=artifact_type,
        body=body_mapping,
        parent_digests=parents,
    )
    return validate_temporal_artifact(
        envelope, expected_artifact_type=artifact_type
    )


def validate_temporal_artifact(
    value: Any, *, expected_artifact_type: str | None = None
) -> dict[str, Any]:
    envelope = validate_m4_v2_artifact_envelope(
        value, expected_artifact_type=expected_artifact_type
    )
    artifact_type = envelope["artifact_type"]
    if artifact_type not in TEMPORAL_ARTIFACT_TYPES:
        raise TemporalMarginalIncrementContractError(
            f"temporal_artifact_type_not_authorized:{artifact_type}"
        )
    _validate_temporal_artifact_body(artifact_type, envelope["body"])
    body = envelope["body"]
    parents = envelope["parent_digests"]
    expected_parents: list[str] | None = None
    if artifact_type == TEMPORAL_DESIGN_ARTIFACT:
        if len(parents) != 3 or parents[0] != body["source_contract_digest"]:
            raise TemporalMarginalIncrementContractError(
                "temporal_design_parent_order_mismatch"
            )
    elif artifact_type == TEMPORAL_PREREGISTRATION_ARTIFACT:
        if parents[:2] != [
            body["source_contract_digest"],
            body["design_artifact_digest"],
        ] or len(parents) != 3:
            raise TemporalMarginalIncrementContractError(
                "temporal_preregistration_parent_order_mismatch"
            )
    elif artifact_type == TEMPORAL_HEALTH_ARTIFACT:
        expected_parents = [
            body["source_contract_digest"],
            body["preregistration_artifact_digest"],
            body["marginal_decision_digest"],
            body["marginal_replay_digest"],
        ]
    elif artifact_type == TEMPORAL_HISTORICAL_ARTIFACT:
        expected_parents = [
            body["source_contract_digest"],
            body["preregistration_artifact_digest"],
            body["health_artifact_digest"],
            body["marginal_raw_p_artifact_digest"],
        ]
    elif artifact_type == TEMPORAL_CANDIDATE_ARTIFACT:
        if (
            len(parents) != 4
            or parents[0] != body["source_contract_digest"]
            or parents[2:]
            != [
                body["marginal_parent_model_artifact_digest"],
                body["marginal_parent_probability_chain_digest"],
            ]
        ):
            raise TemporalMarginalIncrementContractError(
                "temporal_candidate_parent_order_mismatch"
            )
    elif artifact_type == TEMPORAL_FAILURE_ARTIFACT:
        expected_count = (
            2 if body["decision_path"] == "IDENTITY_VALID_HEALTH_INVALID" else 3
        )
        if parents[:2] != [
            body["source_contract_digest"],
            body["preregistration_artifact_digest"],
        ] or len(parents) != expected_count:
            raise TemporalMarginalIncrementContractError(
                "temporal_failure_parent_order_mismatch"
            )
    elif artifact_type == TEMPORAL_COMPLETION_ARTIFACT and parents[:2] != [
        body["source_contract_digest"],
        body["preregistration_artifact_digest"],
    ]:
        raise TemporalMarginalIncrementContractError(
            "temporal_completion_parent_prefix_mismatch"
        )
    if expected_parents is not None and parents != expected_parents:
        raise TemporalMarginalIncrementContractError(
            "temporal_artifact_parent_order_mismatch"
        )
    if artifact_type == BRANCH_DECISION_ARTIFACT:
        return M4V2BranchDecisionArtifact.from_dict(envelope).to_dict()
    if artifact_type == BRANCH_REPLAY_ARTIFACT:
        return validate_temporal_branch_replay(envelope)
    return dict(envelope)


def validate_temporal_path_artifacts(
    path: str, artifacts: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, Any], ...]:
    plan = temporal_registration_plan(path)
    expected_types = tuple(
        item
        for item in plan.artifact_types_in_registration_order
        if item != MAINLINE_EXECUTION_ARTIFACT
    )
    validated = tuple(validate_temporal_artifact(item) for item in artifacts)
    observed_types = tuple(item["artifact_type"] for item in validated)
    if observed_types != expected_types:
        raise TemporalMarginalIncrementContractError(
            f"temporal_path_registration_order_mismatch:{plan.path}"
        )
    for artifact in validated:
        body = artifact["body"]
        if "decision_path" in body and body["decision_path"] != plan.path:
            raise TemporalMarginalIncrementContractError(
                "temporal_path_body_decision_path_mismatch"
            )
    if TEMPORAL_COMPLETION_ARTIFACT in expected_types:
        completion_index = expected_types.index(TEMPORAL_COMPLETION_ARTIFACT)
        completion_envelope = validated[completion_index]
        completion = completion_envelope["body"]
        preceding = [item["artifact_digest"] for item in validated[:completion_index]]
        decision_index = expected_types.index(BRANCH_DECISION_ARTIFACT)
        decision_envelope = validated[decision_index]
        path_leaves = [
            item["artifact_digest"] for item in validated[:decision_index]
        ]
        source_digest = completion.get("source_contract_digest")
        prereg_digest = completion.get("preregistration_artifact_digest")
        decision_suffix_mismatch = bool(path_leaves) and (
            decision_envelope["parent_digests"][-len(path_leaves) :]
            != path_leaves
        )
        path_parent_mismatch = any(
            item["parent_digests"][:2] != [source_digest, prereg_digest]
            for item in validated[:decision_index]
        )
        path_artifacts = {
            item["artifact_type"]: item for item in validated[:decision_index]
        }
        health_envelope = path_artifacts.get(TEMPORAL_HEALTH_ARTIFACT)
        historical_envelope = path_artifacts.get(TEMPORAL_HISTORICAL_ARTIFACT)
        candidate_envelope = path_artifacts.get(TEMPORAL_CANDIDATE_ARTIFACT)
        upstream_pair_mismatch = health_envelope is not None and (
            decision_envelope["parent_digests"][2:4]
            != [
                health_envelope["body"]["marginal_decision_digest"],
                health_envelope["body"]["marginal_replay_digest"],
            ]
        )
        sibling_lineage_mismatch = (
            historical_envelope is not None
            and (
                candidate_envelope is None
                or historical_envelope["body"]["warmup_index_digest"]
                != candidate_envelope["body"]["warmup_index_digest"]
                or historical_envelope["body"][
                    "accepted_temporal_evaluation_index_digest"
                ]
                != candidate_envelope["body"][
                    "accepted_temporal_evaluation_index_digest"
                ]
                or historical_envelope["body"]["composite_view_digest"]
                != candidate_envelope["body"]["composite_view_digest"]
            )
        )
        decision_model_lineage_mismatch = candidate_envelope is not None and (
            decision_envelope["body"]["accepted_model_artifact_digest"]
            != candidate_envelope["artifact_digest"]
            or decision_envelope["body"]["baseline_artifact_digest"]
            != candidate_envelope["body"]["marginal_parent_model_artifact_digest"]
            or decision_envelope["body"]["baseline_source_model_artifact_digest"]
            != candidate_envelope["body"]["marginal_parent_model_artifact_digest"]
        )
        if (
            completion.get("registered_artifact_digests_in_order") != preceding
            or completion.get("registration_count_including_mainline_execution")
            != len(plan.artifact_types_in_registration_order)
            or completion.get("decision_artifact_digest")
            != next(
                (
                    item["artifact_digest"]
                    for item in validated[:completion_index]
                    if item["artifact_type"] == BRANCH_DECISION_ARTIFACT
                ),
                None,
            )
            or completion_envelope["parent_digests"]
            != [source_digest, prereg_digest, *preceding]
            or len(decision_envelope["parent_digests"]) != 4 + len(path_leaves)
            or decision_envelope["parent_digests"][:2]
            != [source_digest, prereg_digest]
            or decision_suffix_mismatch
            or path_parent_mismatch
            or upstream_pair_mismatch
            or sibling_lineage_mismatch
            or decision_model_lineage_mismatch
        ):
            raise TemporalMarginalIncrementContractError(
                "temporal_completion_preceding_lineage_mismatch"
            )
    return validated


__all__ = [
    "BRANCH_DECISION_ARTIFACT",
    "BRANCH_REPLAY_ARTIFACT",
    "CHECKPOINT_ORDER_MANIFEST_DIGEST",
    "COMPOSITE_COUNT",
    "COMPOSITE_END",
    "COMPOSITE_START",
    "DATASET_CONTENT_DIGEST",
    "DECISION_PATHS",
    "EVALUATION_COUNT",
    "EVALUATION_END",
    "EVALUATION_START",
    "FIXTURE_SOURCE_DIGEST",
    "FOLD_MANIFEST_DIGEST",
    "HISTORICAL_CHILD_COUNT",
    "MAINLINE_EXECUTION_ARTIFACT",
    "MARGINAL_BRANCH_ID",
    "MARGINAL_RAW_P_ARTIFACT_DIGEST",
    "MARGINAL_RAW_P_REGISTRATION_DIGEST",
    "MEASUREMENT_CONTRACT_DIGEST",
    "MEASUREMENT_CONTRACT_KEY",
    "PARENT_ESTIMATOR_ID",
    "PLANNED_COUNTS",
    "POSITIVE_ZERO_FLOAT_HEX",
    "POSITIVE_ZERO_IEEE754_BINARY64_BE_HEX",
    "REQUEST481_PREDECESSOR_JOINT_ESTIMATOR_ID",
    "SUCCESSOR_JOINT_ESTIMATOR_ID",
    "SUPPORT_MODEL_ID",
    "SYNTHETIC_BOOTSTRAP_CHILD_COUNT",
    "SYNTHETIC_BOOTSTRAP_SEED_MATERIAL_CHANGED_BY_WARMUP",
    "SYNTHETIC_CELL_COUNT",
    "SYNTHETIC_DGP_CHANGED_BY_WARMUP",
    "SYNTHETIC_GENERATED_ISSUE_COUNT",
    "SYNTHETIC_OUTER_EVALUATION_ISSUE_COUNT",
    "SYNTHETIC_REPLICATES_PER_CELL",
    "SYNTHETIC_REPLICATE_COUNT",
    "SYNTHETIC_WARMUP_ALIAS_POSITION_COUNT",
    "SYNTHETIC_WARMUP_COMPUTED_PER_BOOTSTRAP_CHILD",
    "SYNTHETIC_WARMUP_RNG_CALL_COUNT",
    "TEMPORAL_ARTIFACT_TYPES",
    "TEMPORAL_BRANCH_ID",
    "TEMPORAL_CANDIDATE_ARTIFACT",
    "TEMPORAL_COMPLETION_ARTIFACT",
    "TEMPORAL_DESIGN_ARTIFACT",
    "TEMPORAL_DESIGN_CAPABILITY",
    "TEMPORAL_DESIGN_COMPLETION_FACT",
    "TEMPORAL_DESIGN_TASK_KEY",
    "TEMPORAL_ESTIMAND_DIGEST",
    "TEMPORAL_FAILURE_ARTIFACT",
    "TEMPORAL_HEALTH_ARTIFACT",
    "TEMPORAL_HISTORICAL_ARTIFACT",
    "TEMPORAL_MODEL_ID",
    "TEMPORAL_PREREGISTRATION_ARTIFACT",
    "TEMPORAL_PREREGISTRATION_CAPABILITY",
    "TEMPORAL_PREREGISTRATION_COMPLETION_FACT",
    "TEMPORAL_PREREGISTRATION_TASK_KEY",
    "TEMPORAL_PRODUCER_CAPABILITY",
    "TEMPORAL_PRODUCER_COMPLETION_FACT",
    "TEMPORAL_PRODUCER_TASK_KEY",
    "TEMPORAL_REPLAY_CAPABILITY",
    "TEMPORAL_REPLAY_COMPLETION_FACT",
    "TEMPORAL_REPLAY_FACT",
    "TEMPORAL_REPLAY_TASK_KEY",
    "TEMPORAL_SYNTHETIC_CELLS",
    "TEMPORAL_SYNTHETIC_ROOT_SEED_FULL_SHA256",
    "TEMPORAL_TERMINAL_FACT",
    "WARMUP_COUNT",
    "WARMUP_END",
    "WARMUP_REQUEST_PAYLOAD_DIGEST",
    "WARMUP_SEMANTIC_SCOPE",
    "WARMUP_START",
    "TemporalCheckpointPlan",
    "TemporalMarginalIncrementContractError",
    "TemporalRegistrationPlan",
    "assert_temporal_suffix_noninterference",
    "build_accepted_temporal_evaluation_index",
    "build_accepted_temporal_evaluation_row",
    "build_accepted_temporal_pretarget_checkpoint",
    "build_strict_prior_marginal_checkpoint",
    "build_temporal_artifact",
    "build_temporal_branch_replay",
    "build_temporal_composite_view",
    "build_temporal_parent_not_accepted_path",
    "build_temporal_synthetic_cell_descriptors",
    "build_temporal_synthetic_replicate_commitment",
    "build_temporal_synthetic_replicate_index",
    "build_temporal_synthetic_sequence_coordinate",
    "build_temporal_warmup_index",
    "build_temporal_warmup_row",
    "build_transition_local_warmup_rule",
    "resolve_temporal_composite_row",
    "temporal_checkpoint_plan",
    "temporal_registration_plan",
    "temporal_strict_prior_content_identity",
    "temporal_synthetic_warmup_position",
    "validate_accepted_parent_raw_p_lineage",
    "validate_accepted_temporal_evaluation_index",
    "validate_accepted_temporal_evaluation_row",
    "validate_accepted_temporal_pretarget_checkpoint",
    "validate_strict_prior_marginal_checkpoint",
    "validate_temporal_artifact",
    "validate_temporal_branch_replay",
    "validate_temporal_candidate_lineage",
    "validate_temporal_composite_view",
    "validate_temporal_holm_family",
    "validate_temporal_path_artifacts",
    "validate_temporal_synthetic_cell_descriptor",
    "validate_temporal_synthetic_replicate_commitment",
    "validate_temporal_synthetic_replicate_index",
    "validate_temporal_synthetic_sequence_coordinate",
    "validate_temporal_synthetic_warmup_application",
    "validate_temporal_warmup_index",
    "validate_temporal_warmup_row",
    "validate_transition_local_warmup_rule",
]
