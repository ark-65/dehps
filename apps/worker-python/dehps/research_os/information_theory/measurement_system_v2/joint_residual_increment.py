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


class JointResidualIncrementContractError(ValueError):
    """Raised when a frozen Joint successor identity is not exact."""


MEASUREMENT_CONTRACT_KEY: Final = "M4_MEASUREMENT_CONTRACT_V2"
MEASUREMENT_CONTRACT_DIGEST: Final = (
    "a0a367c99d7646cadc162bd9ceb0d5d73481cd7c26656bf02b40a99d9180095b"
)
JOINT_BRANCH_ID: Final = "JOINT_RESIDUAL_INCREMENT"
MARGINAL_BRANCH_ID: Final = "MARGINAL_STATIC"
MARGINAL_RAW_P_ARTIFACT_DIGEST: Final = (
    "bdb89dd183846e4124654b57021be9892158b2b1387a8ca08d476283e0e2ed87"
)
MARGINAL_RAW_P_REGISTRATION_DIGEST: Final = (
    "10216e732563a48ed3bd3852499c2ab4b980ca29ef3246c4cec20eb71879554a"
)
JOINT_ESTIMAND_DIGEST: Final = (
    "3cff53fe0dc73f442a850c00a8fc37ee64f7a0822cfdd219d7b877784f4e7ff1"
)
TEMPORAL_BRANCH_ID: Final = "TEMPORAL_MARGINAL_INCREMENT"
TEMPORAL_ESTIMAND_DIGEST: Final = (
    "f1bde59f8bb59bc4bb796df8ec5fe3f0a4ba723a6cc3828bb263e747cabd53b3"
)
SUPPORT_MODEL_ID: Final = (
    "TRANSITION_LOCAL_TEMPORAL_PARENT_ALIAS_THETA_ZERO_S2_900_V1"
)
REQUEST481_PREDECESSOR_ESTIMATOR_ID: Final = (
    "EXPANDING_MARGINAL_ORTHOGONAL_IS4_RESIDUAL_TILT_MLE_V1"
)
JOINT_ESTIMATOR_ID: Final = (
    "EXPANDING_MARGINAL_ORTHOGONAL_IS4_RESIDUAL_TILT_MLE_WITH_FIXED_NULL_"
    "TEMPORAL_WARMUP_V2"
)
JOINT_MODEL_ID: Final = JOINT_ESTIMATOR_ID
JOINT_BASELINE_ID: Final = (
    "MAXIMUM_ENTROPY_LEGAL_DISTRIBUTION_MATCHING_ACCEPTED_TEMPORAL_MARGINALS"
)
PARENT_ESTIMATOR_ID: Final = "EXPANDING_LEGAL_MARGINAL_ALPHA_1"
TEMPORAL_ESTIMATOR_ID: Final = "EXPANDING_LEGAL_ONE_LAG_OVERLAP_TILT_MLE_V1"
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
JOINT_SYNTHETIC_ROOT_SEED_FULL_SHA256: Final = (
    "7282624ee66eb89bc823a47b69c31086748bf6a393f51943d2c879aebb821482"
)
WARMUP_REQUEST_PAYLOAD_DIGEST: Final = (
    "aa25843e43a4a88413ca8ef50d2b2dd7ce7c1bf9631b5033f563ae4c5633d1f8"
)

WARMUP_START: Final = 2
WARMUP_END: Final = 900
WARMUP_COUNT: Final = 899
TARGET_START: Final = 901
TARGET_END: Final = 3481
TARGET_COUNT: Final = 2581
SUPPORT_START: Final = 2
SUPPORT_END: Final = 3481
SUPPORT_COUNT: Final = 3480
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
NUMERICAL_TOLERANCE: Final = 1e-12
MAXIMUM_CONDITION_NUMBER: Final = 1e12

JOINT_DESIGN_TASK_KEY: Final = (
    "m4-v2-joint-residual-increment-historical-measurement-design"
)
JOINT_DESIGN_CAPABILITY: Final = (
    "m4_v2_joint_residual_increment_historical_measurement_design"
)
JOINT_DESIGN_COMPLETION_FACT: Final = f"{JOINT_DESIGN_TASK_KEY}:FROZEN"
JOINT_PREREGISTRATION_TASK_KEY: Final = (
    "m4-v2-joint-residual-increment-historical-measurement-preregistration"
)
JOINT_PREREGISTRATION_CAPABILITY: Final = (
    "m4_v2_joint_residual_increment_historical_measurement_preregistration"
)
JOINT_PREREGISTRATION_COMPLETION_FACT: Final = (
    f"{JOINT_PREREGISTRATION_TASK_KEY}:FROZEN"
)
JOINT_PRODUCER_TASK_KEY: Final = (
    "m4-v2-joint-residual-increment-historical-measurement-gate-compiler"
)
JOINT_PRODUCER_CAPABILITY: Final = (
    "m4_v2_joint_residual_increment_historical_measurement_gate_compiler"
)
JOINT_PRODUCER_COMPLETION_FACT: Final = f"{JOINT_PRODUCER_TASK_KEY}:COMPLETE"
JOINT_REPLAY_TASK_KEY: Final = (
    "m4-v2-joint-residual-increment-historical-branch-decision-replay"
)
JOINT_REPLAY_CAPABILITY: Final = (
    "m4_v2_joint_residual_increment_historical_branch_decision_replay"
)
JOINT_REPLAY_COMPLETION_FACT: Final = f"{JOINT_REPLAY_TASK_KEY}:COMPLETE"
JOINT_TERMINAL_FACT: Final = (
    "m4-v2-historical-branch-decision:M4_MEASUREMENT_CONTRACT_V2:"
    "JOINT_RESIDUAL_INCREMENT:TERMINAL"
)
JOINT_REPLAY_FACT: Final = (
    "m4-v2-historical-branch-decision-replay:M4_MEASUREMENT_CONTRACT_V2:"
    "JOINT_RESIDUAL_INCREMENT:VERIFIED"
)

JOINT_DESIGN_ARTIFACT: Final = "M4V2JointResidualIncrementDesignArtifact"
JOINT_PREREGISTRATION_ARTIFACT: Final = (
    "M4V2JointResidualIncrementPreregistrationArtifact"
)
JOINT_BASELINE_ARTIFACT: Final = (
    "M4V2JointResidualMaximumEntropyBaselineArtifact"
)
JOINT_HEALTH_ARTIFACT: Final = "M4V2JointResidualMeasurementHealthArtifact"
JOINT_HISTORICAL_ARTIFACT: Final = (
    "M4V2JointResidualHistoricalExecutionArtifact"
)
JOINT_CANDIDATE_ARTIFACT: Final = "M4V2JointResidualCandidateModelArtifact"
JOINT_COMPLETION_ARTIFACT: Final = (
    "M4V2JointResidualProducerCompletionArtifact"
)
JOINT_FAILURE_ARTIFACT: Final = "M4V2JointResidualScientificFailureArtifact"
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
class JointRegistrationPlan:
    path: str
    task_key: str
    artifact_types_in_registration_order: tuple[str, ...]
    registration_count_including_mainline_execution: int
    full_four_task_registration_count: int

    @property
    def preceding_completion_artifact_types(self) -> tuple[str, ...]:
        if JOINT_COMPLETION_ARTIFACT not in self.artifact_types_in_registration_order:
            return ()
        index = self.artifact_types_in_registration_order.index(
            JOINT_COMPLETION_ARTIFACT
        )
        return self.artifact_types_in_registration_order[:index]


@dataclass(frozen=True)
class JointChronologyPlan:
    target_ordinal: int
    eta_training_range: tuple[int, int]
    eta_training_count: int
    required_existing_z_range: tuple[int, int]
    target_z_created_after_eta: bool
    target_q_j_created_before_reveal: bool
    target_z_may_be_reconstructed: bool


_REGISTRATION_ORDERS = MappingProxyType(
    {
        "DESIGN": (JOINT_DESIGN_ARTIFACT, MAINLINE_EXECUTION_ARTIFACT),
        "PREREGISTRATION": (
            JOINT_PREREGISTRATION_ARTIFACT,
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "EVALUATED_COMPLETE": (
            JOINT_BASELINE_ARTIFACT,
            JOINT_HEALTH_ARTIFACT,
            JOINT_HISTORICAL_ARTIFACT,
            JOINT_CANDIDATE_ARTIFACT,
            BRANCH_DECISION_ARTIFACT,
            JOINT_COMPLETION_ARTIFACT,
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "PARENT_NOT_ACCEPTED": (
            BRANCH_DECISION_ARTIFACT,
            JOINT_COMPLETION_ARTIFACT,
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "IDENTITY_VALID_HEALTH_REPAIR": (
            JOINT_HEALTH_ARTIFACT,
            BRANCH_DECISION_ARTIFACT,
            JOINT_COMPLETION_ARTIFACT,
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "EARLY_IDENTITY_VALID_HEALTH_REPAIR": (
            "M4V2JointResidualScientificFailureArtifact@dehps-m4-v2-joint-residual-scientific-failure.v3",
            BRANCH_DECISION_ARTIFACT,
            "M4V2JointResidualProducerCompletionArtifact@dehps-m4-v2-joint-residual-producer-completion.v3",
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "STARTED_PARTIAL_HEALTH_REPAIR": (
            "M4V2JointResidualScientificFailureArtifact@dehps-m4-v2-joint-residual-scientific-failure.v3",
            BRANCH_DECISION_ARTIFACT,
            "M4V2JointResidualProducerCompletionArtifact@dehps-m4-v2-joint-residual-producer-completion.v3",
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "IDENTITY_VALID_HEALTH_INVALID": (
            JOINT_FAILURE_ARTIFACT,
            BRANCH_DECISION_ARTIFACT,
            JOINT_COMPLETION_ARTIFACT,
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "IDENTITY_VALID_HISTORICAL_REPAIR": (
            JOINT_HEALTH_ARTIFACT,
            JOINT_FAILURE_ARTIFACT,
            BRANCH_DECISION_ARTIFACT,
            JOINT_COMPLETION_ARTIFACT,
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "IDENTITY_VALID_HISTORICAL_INVALID": (
            JOINT_HEALTH_ARTIFACT,
            JOINT_FAILURE_ARTIFACT,
            BRANCH_DECISION_ARTIFACT,
            JOINT_COMPLETION_ARTIFACT,
            MAINLINE_EXECUTION_ARTIFACT,
        ),
        "REPLAY": (BRANCH_REPLAY_ARTIFACT, MAINLINE_EXECUTION_ARTIFACT),
    }
)
_FULL_PATH_COUNTS = MappingProxyType(
    {
        "EVALUATED_COMPLETE": 13,
        "PARENT_NOT_ACCEPTED": 9,
        "IDENTITY_VALID_HEALTH_REPAIR": 10,
        "EARLY_IDENTITY_VALID_HEALTH_REPAIR": 10,
        "STARTED_PARTIAL_HEALTH_REPAIR": 10,
        "IDENTITY_VALID_HEALTH_INVALID": 10,
        "IDENTITY_VALID_HISTORICAL_REPAIR": 11,
        "IDENTITY_VALID_HISTORICAL_INVALID": 11,
    }
)

JOINT_ARTIFACT_TYPES: Final = frozenset(
    {
        JOINT_DESIGN_ARTIFACT,
        JOINT_PREREGISTRATION_ARTIFACT,
        JOINT_BASELINE_ARTIFACT,
        JOINT_HEALTH_ARTIFACT,
        JOINT_HISTORICAL_ARTIFACT,
        JOINT_CANDIDATE_ARTIFACT,
        JOINT_COMPLETION_ARTIFACT,
        JOINT_FAILURE_ARTIFACT,
        BRANCH_DECISION_ARTIFACT,
        BRANCH_REPLAY_ARTIFACT,
    }
)

JOINT_SYNTHETIC_CELLS: Final = (
    (0, "BASE:V2_J1_HISTORY_IS4_LAMBDA_HALF:FORWARD_61", "V2_J1_HISTORY_IS4_LAMBDA_HALF", "FORWARD_61"),
    (1, "BASE:V2_J1_HISTORY_IS4_LAMBDA_HALF:HISTORICAL_2581", "V2_J1_HISTORY_IS4_LAMBDA_HALF", "HISTORICAL_2581"),
    (2, "BASE:NULL_UNIFORM_LEGAL_SIX_OF_33:FORWARD_61", "NULL_UNIFORM_LEGAL_SIX_OF_33", "FORWARD_61"),
    (3, "BASE:NULL_UNIFORM_LEGAL_SIX_OF_33:HISTORICAL_2581", "NULL_UNIFORM_LEGAL_SIX_OF_33", "HISTORICAL_2581"),
    (4, "BASE:V2_M1_GROUP_ODDS_2_STATIONARY:FORWARD_61", "V2_M1_GROUP_ODDS_2_STATIONARY", "FORWARD_61"),
    (5, "BASE:V2_M1_GROUP_ODDS_2_STATIONARY:HISTORICAL_2581", "V2_M1_GROUP_ODDS_2_STATIONARY", "HISTORICAL_2581"),
    (6, "BASE:V2_T1_OVERLAP_ODDS_2_MARKOV:FORWARD_61", "V2_T1_OVERLAP_ODDS_2_MARKOV", "FORWARD_61"),
    (7, "BASE:V2_T1_OVERLAP_ODDS_2_MARKOV:HISTORICAL_2581", "V2_T1_OVERLAP_ODDS_2_MARKOV", "HISTORICAL_2581"),
    (8, "LOCAL:0.001:FORWARD_61", "LOCAL_UNIFORM_CARRIER_IS4_RESIDUAL_TILT", "FORWARD_61"),
    (9, "LOCAL:0.001:HISTORICAL_2581", "LOCAL_UNIFORM_CARRIER_IS4_RESIDUAL_TILT", "HISTORICAL_2581"),
    (10, "LOCAL:0.01:FORWARD_61", "LOCAL_UNIFORM_CARRIER_IS4_RESIDUAL_TILT", "FORWARD_61"),
    (11, "LOCAL:0.01:HISTORICAL_2581", "LOCAL_UNIFORM_CARRIER_IS4_RESIDUAL_TILT", "HISTORICAL_2581"),
    (12, "LOCAL:0.05:FORWARD_61", "LOCAL_UNIFORM_CARRIER_IS4_RESIDUAL_TILT", "FORWARD_61"),
    (13, "LOCAL:0.05:HISTORICAL_2581", "LOCAL_UNIFORM_CARRIER_IS4_RESIDUAL_TILT", "HISTORICAL_2581"),
)

PLANNED_COUNTS: Final = MappingProxyType(
    {
        "cell_count": SYNTHETIC_CELL_COUNT,
        "replicates_per_cell": SYNTHETIC_REPLICATES_PER_CELL,
        "synthetic_replicate_count": SYNTHETIC_REPLICATE_COUNT,
        "synthetic_generated_issue_count": SYNTHETIC_GENERATED_ISSUE_COUNT,
        "outer_evaluation_issue_count": SYNTHETIC_OUTER_EVALUATION_ISSUE_COUNT,
        "bootstrap_resample_count": SYNTHETIC_BOOTSTRAP_CHILD_COUNT,
        "historical_fold_count": TARGET_COUNT,
        "historical_child_count": HISTORICAL_CHILD_COUNT,
        "warmup_transition_count_per_replicate": WARMUP_COUNT,
        "warmup_alias_position_count": SYNTHETIC_WARMUP_ALIAS_POSITION_COUNT,
    }
)


def _mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise JointResidualIncrementContractError(f"{name}_must_be_object")
    return value


def _exact_fields(
    value: Mapping[str, Any], fields: Sequence[str], *, name: str
) -> None:
    expected = set(fields)
    actual = set(value)
    if actual != expected:
        raise JointResidualIncrementContractError(
            f"{name}_fields_mismatch:missing={sorted(expected-actual)}:"
            f"extra={sorted(actual-expected)}"
        )


def _digest(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise JointResidualIncrementContractError(f"{name}_must_be_sha256")
    return value


def _execution_id(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or _EXECUTION_ID_RE.fullmatch(value) is None:
        raise JointResidualIncrementContractError(
            f"{name}_must_be_lowercase_sha256_execution_identity"
        )
    return value


def _integer(value: Any, *, name: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise JointResidualIncrementContractError(f"{name}_must_be_integer")
    if minimum is not None and value < minimum:
        raise JointResidualIncrementContractError(f"{name}_below_minimum")
    return value


def _issue(value: Any, *, name: str = "issue") -> str:
    if not isinstance(value, str) or not value:
        raise JointResidualIncrementContractError(f"{name}_must_be_nonempty_string")
    return value


def _float_hex(
    value: Any,
    *,
    name: str,
    nonnegative: bool = False,
    positive: bool = False,
) -> str:
    if not isinstance(value, str):
        raise JointResidualIncrementContractError(f"{name}_must_be_float_hex")
    try:
        parsed = float.fromhex(value)
    except ValueError as exc:
        raise JointResidualIncrementContractError(
            f"{name}_must_be_float_hex"
        ) from exc
    if not math.isfinite(parsed) or parsed.hex() != value or value.startswith("-") and parsed == 0:
        raise JointResidualIncrementContractError(
            f"{name}_must_be_canonical_finite_positive_zero_safe_float_hex"
        )
    if nonnegative and parsed < 0:
        raise JointResidualIncrementContractError(f"{name}_must_be_nonnegative")
    if positive and parsed <= 0:
        raise JointResidualIncrementContractError(f"{name}_must_be_positive")
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
        raise JointResidualIncrementContractError(f"{name}_digest_mismatch")


def _validate_nested(schema_name: str, value: Any) -> Any:
    try:
        return validate_m4_v2_nested_schema(schema_name, value)
    except Exception as exc:
        raise JointResidualIncrementContractError(
            f"{schema_name}_shared_schema_invalid"
        ) from exc


def joint_registration_plan(path: str) -> JointRegistrationPlan:
    normalized = str(path or "").upper()
    try:
        artifact_types = _REGISTRATION_ORDERS[normalized]
    except KeyError as exc:
        raise JointResidualIncrementContractError(
            f"joint_registration_path_unknown:{path}"
        ) from exc
    if normalized == "DESIGN":
        task_key, full_count = JOINT_DESIGN_TASK_KEY, 2
    elif normalized == "PREREGISTRATION":
        task_key, full_count = JOINT_PREREGISTRATION_TASK_KEY, 2
    elif normalized == "REPLAY":
        task_key, full_count = JOINT_REPLAY_TASK_KEY, 2
    else:
        task_key, full_count = JOINT_PRODUCER_TASK_KEY, _FULL_PATH_COUNTS[normalized]
    return JointRegistrationPlan(
        path=normalized,
        task_key=task_key,
        artifact_types_in_registration_order=artifact_types,
        registration_count_including_mainline_execution=len(artifact_types),
        full_four_task_registration_count=full_count,
    )


def joint_checkpoint_plan(target_ordinal: int) -> JointChronologyPlan:
    target = _integer(target_ordinal, name="target_ordinal", minimum=TARGET_START)
    if target > TARGET_END:
        raise JointResidualIncrementContractError("joint_target_ordinal_out_of_range")
    return JointChronologyPlan(
        target_ordinal=target,
        eta_training_range=(SUPPORT_START, target - 1),
        eta_training_count=target - 2,
        required_existing_z_range=(SUPPORT_START, target - 1),
        target_z_created_after_eta=True,
        target_q_j_created_before_reveal=True,
        target_z_may_be_reconstructed=False,
    )


def _support_kind(ordinal: int) -> str:
    return "WARMUP_NULL_ALIAS" if ordinal <= WARMUP_END else "ACCEPTED_TEMPORAL_EVALUATION"


_Q_BASE_CERT_FIELDS = (
    "transition_ordinal",
    "temporal_support_row_digest",
    "q_t_full_distribution_content_digest",
    "q_base_full_distribution_content_digest",
    "max_probability_difference_float_hex",
    "max_marginal_difference_float_hex",
    "normalization_residual_float_hex",
    "certificate_pass",
    "certificate_digest",
)


def build_q_base_reconstruction_certificate(
    *,
    transition_ordinal: int,
    temporal_support_row_digest: str,
    q_t_full_distribution_content_digest: str,
    q_base_full_distribution_content_digest: str,
    max_probability_difference_float_hex: str,
    max_marginal_difference_float_hex: str,
    normalization_residual_float_hex: str,
) -> dict[str, Any]:
    residuals = (
        max_probability_difference_float_hex,
        max_marginal_difference_float_hex,
        normalization_residual_float_hex,
    )
    parsed = [float.fromhex(_float_hex(item, name="certificate_residual", nonnegative=True)) for item in residuals]
    certificate: dict[str, Any] = {
        "transition_ordinal": _integer(
            transition_ordinal, name="transition_ordinal", minimum=SUPPORT_START
        ),
        "temporal_support_row_digest": _digest(
            temporal_support_row_digest, name="temporal_support_row_digest"
        ),
        "q_t_full_distribution_content_digest": _digest(
            q_t_full_distribution_content_digest,
            name="q_t_full_distribution_content_digest",
        ),
        "q_base_full_distribution_content_digest": _digest(
            q_base_full_distribution_content_digest,
            name="q_base_full_distribution_content_digest",
        ),
        "max_probability_difference_float_hex": residuals[0],
        "max_marginal_difference_float_hex": residuals[1],
        "normalization_residual_float_hex": residuals[2],
        "certificate_pass": (
            q_t_full_distribution_content_digest
            == q_base_full_distribution_content_digest
            and all(item <= NUMERICAL_TOLERANCE for item in parsed)
        ),
    }
    certificate["certificate_digest"] = m4_v2_domain_digest(
        certificate,
        domain="dehps.m4.v2.joint-residual.q-base-reconstruction-certificate.v2",
    )
    return validate_q_base_reconstruction_certificate(certificate)


def validate_q_base_reconstruction_certificate(value: Any) -> dict[str, Any]:
    certificate = dict(_mapping(value, name="q_base_reconstruction_certificate"))
    _exact_fields(
        certificate, _Q_BASE_CERT_FIELDS, name="q_base_reconstruction_certificate"
    )
    ordinal = _integer(
        certificate["transition_ordinal"], name="transition_ordinal", minimum=2
    )
    if ordinal > SUPPORT_END:
        raise JointResidualIncrementContractError("q_base_certificate_ordinal_out_of_range")
    for name in (
        "temporal_support_row_digest",
        "q_t_full_distribution_content_digest",
        "q_base_full_distribution_content_digest",
        "certificate_digest",
    ):
        _digest(certificate[name], name=name)
    residuals = [
        float.fromhex(_float_hex(certificate[name], name=name, nonnegative=True))
        for name in (
            "max_probability_difference_float_hex",
            "max_marginal_difference_float_hex",
            "normalization_residual_float_hex",
        )
    ]
    expected_pass = (
        certificate["q_t_full_distribution_content_digest"]
        == certificate["q_base_full_distribution_content_digest"]
        and all(item <= NUMERICAL_TOLERANCE for item in residuals)
    )
    if certificate["certificate_pass"] is not expected_pass:
        raise JointResidualIncrementContractError("q_base_certificate_pass_mismatch")
    _self_digest(
        certificate,
        digest_field="certificate_digest",
        domain="dehps.m4.v2.joint-residual.q-base-reconstruction-certificate.v2",
        input_fields=_Q_BASE_CERT_FIELDS[:-1],
        name="q_base_reconstruction_certificate",
    )
    _validate_nested("q_base_reconstruction_certificate", certificate)
    return certificate


_Q_BASE_FIELDS = (
    "transition_ordinal",
    "issue",
    "support_kind",
    "temporal_support_row_digest",
    "temporal_composite_view_digest",
    "q_t_marginal_content_digest",
    "q_t_full_distribution_content_digest",
    "baseline_id",
    "baseline_contract_digest",
    "q_base_marginal_content_digest",
    "q_base_full_distribution_content_digest",
    "reconstruction_certificate_digest",
    "checkpoint_digest",
)


def build_q_base_checkpoint(
    *,
    transition_ordinal: int,
    issue: str,
    temporal_support_row_digest: str,
    temporal_composite_view_digest: str,
    q_t_marginal_content_digest: str,
    q_t_full_distribution_content_digest: str,
    baseline_contract_digest: str,
    reconstruction_certificate: Mapping[str, Any],
) -> dict[str, Any]:
    ordinal = _integer(
        transition_ordinal, name="transition_ordinal", minimum=SUPPORT_START
    )
    if ordinal > SUPPORT_END:
        raise JointResidualIncrementContractError("q_base_ordinal_out_of_range")
    certificate = validate_q_base_reconstruction_certificate(
        reconstruction_certificate
    )
    checkpoint: dict[str, Any] = {
        "transition_ordinal": ordinal,
        "issue": _issue(issue),
        "support_kind": _support_kind(ordinal),
        "temporal_support_row_digest": _digest(
            temporal_support_row_digest, name="temporal_support_row_digest"
        ),
        "temporal_composite_view_digest": _digest(
            temporal_composite_view_digest, name="temporal_composite_view_digest"
        ),
        "q_t_marginal_content_digest": _digest(
            q_t_marginal_content_digest, name="q_t_marginal_content_digest"
        ),
        "q_t_full_distribution_content_digest": _digest(
            q_t_full_distribution_content_digest,
            name="q_t_full_distribution_content_digest",
        ),
        "baseline_id": JOINT_BASELINE_ID,
        "baseline_contract_digest": _digest(
            baseline_contract_digest, name="baseline_contract_digest"
        ),
        "q_base_marginal_content_digest": q_t_marginal_content_digest,
        "q_base_full_distribution_content_digest": q_t_full_distribution_content_digest,
        "reconstruction_certificate_digest": certificate["certificate_digest"],
    }
    checkpoint["checkpoint_digest"] = m4_v2_domain_digest(
        checkpoint, domain="dehps.m4.v2.joint-residual.q-base-checkpoint.v2"
    )
    return validate_q_base_checkpoint(
        checkpoint, reconstruction_certificate=certificate
    )


def validate_q_base_checkpoint(
    value: Any,
    *,
    reconstruction_certificate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    checkpoint = dict(_mapping(value, name="q_base_checkpoint"))
    _exact_fields(checkpoint, _Q_BASE_FIELDS, name="q_base_checkpoint")
    ordinal = _integer(
        checkpoint["transition_ordinal"], name="transition_ordinal", minimum=2
    )
    if ordinal > SUPPORT_END or checkpoint["support_kind"] != _support_kind(ordinal):
        raise JointResidualIncrementContractError("q_base_support_mapping_mismatch")
    _issue(checkpoint["issue"])
    if checkpoint["baseline_id"] != JOINT_BASELINE_ID:
        raise JointResidualIncrementContractError("q_base_baseline_identity_mismatch")
    for name in (
        "temporal_support_row_digest",
        "temporal_composite_view_digest",
        "q_t_marginal_content_digest",
        "q_t_full_distribution_content_digest",
        "baseline_contract_digest",
        "q_base_marginal_content_digest",
        "q_base_full_distribution_content_digest",
        "reconstruction_certificate_digest",
        "checkpoint_digest",
    ):
        _digest(checkpoint[name], name=name)
    if (
        checkpoint["q_base_marginal_content_digest"]
        != checkpoint["q_t_marginal_content_digest"]
        or checkpoint["q_base_full_distribution_content_digest"]
        != checkpoint["q_t_full_distribution_content_digest"]
    ):
        raise JointResidualIncrementContractError(
            "q_base_temporal_distribution_content_alias_mismatch"
        )
    if reconstruction_certificate is not None:
        certificate = validate_q_base_reconstruction_certificate(
            reconstruction_certificate
        )
        if (
            certificate["transition_ordinal"] != ordinal
            or certificate["temporal_support_row_digest"]
            != checkpoint["temporal_support_row_digest"]
            or certificate["q_t_full_distribution_content_digest"]
            != checkpoint["q_t_full_distribution_content_digest"]
            or certificate["q_base_full_distribution_content_digest"]
            != checkpoint["q_base_full_distribution_content_digest"]
            or certificate["certificate_digest"]
            != checkpoint["reconstruction_certificate_digest"]
            or certificate["certificate_pass"] is not True
        ):
            raise JointResidualIncrementContractError(
                "q_base_reconstruction_certificate_owner_mismatch"
            )
    _self_digest(
        checkpoint,
        digest_field="checkpoint_digest",
        domain="dehps.m4.v2.joint-residual.q-base-checkpoint.v2",
        input_fields=_Q_BASE_FIELDS[:-1],
        name="q_base_checkpoint",
    )
    _validate_nested("q_base_checkpoint", checkpoint)
    return checkpoint


def build_q_base_checkpoint_index(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    validated = [validate_q_base_checkpoint(row) for row in rows]
    ordered = [row["checkpoint_digest"] for row in validated]
    chain = m4_v2_domain_digest(
        {"ordered_checkpoint_digests": ordered},
        domain="dehps.m4.v2.joint-residual.q-base-checkpoint-chain.v2",
    )
    index: dict[str, Any] = {
        "row_count": len(validated),
        "transition_range": [SUPPORT_START, SUPPORT_END],
        "rows": validated,
        "ordered_checkpoint_digests": ordered,
        "checkpoint_chain_digest": chain,
    }
    index["index_digest"] = m4_v2_domain_digest(
        {
            "row_count": index["row_count"],
            "transition_range": index["transition_range"],
            "checkpoint_chain_digest": chain,
        },
        domain="dehps.m4.v2.joint-residual.q-base-checkpoint-index.v2",
    )
    return validate_q_base_checkpoint_index(index)


def validate_q_base_checkpoint_index(value: Any) -> dict[str, Any]:
    index = dict(_mapping(value, name="q_base_checkpoint_index"))
    fields = (
        "row_count",
        "transition_range",
        "rows",
        "ordered_checkpoint_digests",
        "checkpoint_chain_digest",
        "index_digest",
    )
    _exact_fields(index, fields, name="q_base_checkpoint_index")
    if not isinstance(index["rows"], list) or not isinstance(
        index["ordered_checkpoint_digests"], list
    ):
        raise JointResidualIncrementContractError("q_base_index_rows_invalid")
    rows = [validate_q_base_checkpoint(row) for row in index["rows"]]
    ordered = [row["checkpoint_digest"] for row in rows]
    if (
        index["row_count"] != SUPPORT_COUNT
        or index["transition_range"] != [SUPPORT_START, SUPPORT_END]
        or [row["transition_ordinal"] for row in rows]
        != list(range(SUPPORT_START, SUPPORT_END + 1))
        or index["ordered_checkpoint_digests"] != ordered
    ):
        raise JointResidualIncrementContractError(
            "q_base_checkpoint_index_coverage_or_order_mismatch"
        )
    expected_chain = m4_v2_domain_digest(
        {"ordered_checkpoint_digests": ordered},
        domain="dehps.m4.v2.joint-residual.q-base-checkpoint-chain.v2",
    )
    if index["checkpoint_chain_digest"] != expected_chain:
        raise JointResidualIncrementContractError("q_base_checkpoint_chain_mismatch")
    _self_digest(
        index,
        digest_field="index_digest",
        domain="dehps.m4.v2.joint-residual.q-base-checkpoint-index.v2",
        input_fields=("row_count", "transition_range", "checkpoint_chain_digest"),
        name="q_base_checkpoint_index",
    )
    _validate_nested("q_base_checkpoint_index", index)
    return index


_COORDINATE_FIELDS = (
    "scope",
    "branch_id",
    "source_contract_digest",
    "preregistration_artifact_digest",
    "producer_execution_id",
    "transition_ordinal",
    "issue_or_sequence_coordinate_digest",
    "support_kind",
    "coordinate_digest",
)


def build_certificate_coordinate_identity(
    *,
    scope: str,
    source_contract_digest: str,
    preregistration_artifact_digest: str,
    producer_execution_id: str,
    transition_ordinal: int,
    issue_or_sequence_coordinate_digest: str,
    support_kind: str,
) -> dict[str, Any]:
    coordinate: dict[str, Any] = {
        "scope": scope,
        "branch_id": JOINT_BRANCH_ID,
        "source_contract_digest": _digest(
            source_contract_digest, name="source_contract_digest"
        ),
        "preregistration_artifact_digest": _digest(
            preregistration_artifact_digest,
            name="preregistration_artifact_digest",
        ),
        "producer_execution_id": _execution_id(
            producer_execution_id, name="producer_execution_id"
        ),
        "transition_ordinal": _integer(
            transition_ordinal, name="transition_ordinal", minimum=2
        ),
        "issue_or_sequence_coordinate_digest": issue_or_sequence_coordinate_digest,
        "support_kind": support_kind,
    }
    coordinate["coordinate_digest"] = m4_v2_domain_digest(
        coordinate, domain="dehps.m4.v2.numerical-certificate-coordinate.v1"
    )
    return validate_certificate_coordinate_identity(coordinate)


def validate_certificate_coordinate_identity(value: Any) -> dict[str, Any]:
    coordinate = dict(_mapping(value, name="certificate_coordinate_identity"))
    _exact_fields(coordinate, _COORDINATE_FIELDS, name="certificate_coordinate_identity")
    scopes = {
        "HISTORICAL_Z",
        "SYNTHETIC_Z",
        "HISTORICAL_TARGET_Q_J",
        "SYNTHETIC_TARGET_Q_J",
    }
    if coordinate["scope"] not in scopes or coordinate["branch_id"] != JOINT_BRANCH_ID:
        raise JointResidualIncrementContractError("certificate_coordinate_scope_mismatch")
    ordinal = _integer(
        coordinate["transition_ordinal"], name="transition_ordinal", minimum=2
    )
    if ordinal > SUPPORT_END or coordinate["support_kind"] != _support_kind(ordinal):
        raise JointResidualIncrementContractError("certificate_coordinate_support_mismatch")
    for name in (
        "source_contract_digest",
        "preregistration_artifact_digest",
        "coordinate_digest",
    ):
        _digest(coordinate[name], name=name)
    _execution_id(coordinate["producer_execution_id"], name="producer_execution_id")
    identity = coordinate["issue_or_sequence_coordinate_digest"]
    if coordinate["scope"].startswith("SYNTHETIC"):
        _digest(identity, name="issue_or_sequence_coordinate_digest")
    else:
        _issue(identity, name="issue_or_sequence_coordinate_digest")
    _self_digest(
        coordinate,
        digest_field="coordinate_digest",
        domain="dehps.m4.v2.numerical-certificate-coordinate.v1",
        input_fields=_COORDINATE_FIELDS[:-1],
        name="certificate_coordinate_identity",
    )
    _validate_nested("certificate_coordinate_identity", coordinate)
    return coordinate


def _validate_certificate_common(
    value: Any,
    *,
    schema_name: str,
    fields: Sequence[str],
    domain: str,
    residual_fields: Sequence[str],
    residual_count: int | None = None,
) -> dict[str, Any]:
    certificate = dict(_mapping(value, name=schema_name))
    _exact_fields(certificate, fields, name=schema_name)
    for name in fields:
        if name.endswith("_digest"):
            _digest(certificate[name], name=name)
    max_residual = 0.0
    for name in residual_fields:
        raw = certificate[name]
        if isinstance(raw, list):
            if residual_count is not None and len(raw) != residual_count:
                raise JointResidualIncrementContractError(
                    f"{schema_name}_{name}_cardinality_mismatch"
                )
            values = [
                float.fromhex(_float_hex(item, name=name, nonnegative=False))
                for item in raw
            ]
            max_residual = max(max_residual, *(abs(item) for item in values))
        else:
            parsed = float.fromhex(_float_hex(raw, name=name, nonnegative=True))
            max_residual = max(max_residual, parsed)
    tolerance = float.fromhex(
        _float_hex(certificate["tolerance_float_hex"], name="tolerance_float_hex", positive=True)
    )
    expected_pass = max_residual <= tolerance
    if certificate.get("certificate_pass") is not expected_pass:
        raise JointResidualIncrementContractError(f"{schema_name}_pass_mismatch")
    _self_digest(
        certificate,
        digest_field="certificate_digest",
        domain=domain,
        input_fields=fields[:-1],
        name=schema_name,
    )
    _validate_nested(schema_name, certificate)
    return certificate


_ORTHOGONALITY_FIELDS = (
    "coordinate_identity_digest",
    "q_base_full_distribution_content_digest",
    "raw_feature_content_digest",
    "projection_coefficients_float_hex_in_fixed_33_basis",
    "orthogonality_residuals_float_hex_in_fixed_34_constraint_order",
    "condition_number_float_hex",
    "rank",
    "tolerance_float_hex",
    "certificate_pass",
    "certificate_digest",
)


def validate_orthogonality_certificate(
    value: Any, *, synthetic: bool = False
) -> dict[str, Any]:
    certificate = dict(_mapping(value, name="orthogonality_certificate"))
    _exact_fields(certificate, _ORTHOGONALITY_FIELDS, name="orthogonality_certificate")
    coefficients = certificate["projection_coefficients_float_hex_in_fixed_33_basis"]
    residuals = certificate[
        "orthogonality_residuals_float_hex_in_fixed_34_constraint_order"
    ]
    if not isinstance(coefficients, list) or len(coefficients) != 33:
        raise JointResidualIncrementContractError(
            "orthogonality_projection_basis_cardinality_mismatch"
        )
    for item in coefficients:
        _float_hex(item, name="projection_coefficient")
    if not isinstance(residuals, list) or len(residuals) != 34:
        raise JointResidualIncrementContractError(
            "orthogonality_residual_cardinality_mismatch"
        )
    residual_values = [
        abs(float.fromhex(_float_hex(item, name="orthogonality_residual")))
        for item in residuals
    ]
    condition = float.fromhex(
        _float_hex(certificate["condition_number_float_hex"], name="condition_number_float_hex", positive=True)
    )
    tolerance = float.fromhex(
        _float_hex(certificate["tolerance_float_hex"], name="tolerance_float_hex", positive=True)
    )
    expected_pass = (
        certificate["rank"] == 33
        and condition <= MAXIMUM_CONDITION_NUMBER
        and max(residual_values) <= tolerance
    )
    if certificate["certificate_pass"] is not expected_pass:
        raise JointResidualIncrementContractError("orthogonality_certificate_pass_mismatch")
    for name in (
        "coordinate_identity_digest",
        "q_base_full_distribution_content_digest",
        "raw_feature_content_digest",
        "certificate_digest",
    ):
        _digest(certificate[name], name=name)
    domain = (
        "dehps.m4.v2.joint.synthetic-warmup.orthogonality-certificate.v1"
        if synthetic
        else "dehps.m4.v2.joint-residual.orthogonality-certificate.v2"
    )
    _self_digest(
        certificate,
        digest_field="certificate_digest",
        domain=domain,
        input_fields=_ORTHOGONALITY_FIELDS[:-1],
        name="orthogonality_certificate",
    )
    _validate_nested("orthogonality_certificate", certificate)
    return certificate


_Z_NEUTRALITY_FIELDS = (
    "coordinate_identity_digest",
    "q_base_full_distribution_content_digest",
    "raw_feature_content_digest",
    "projection_coefficients_float_hex_in_fixed_33_basis",
    "scale_B_float_hex",
    "weighted_marginal_residuals_float_hex_in_ball_order_1_through_33",
    "max_abs_residual_float_hex",
    "tolerance_float_hex",
    "certificate_pass",
    "certificate_digest",
)


def validate_z_direction_marginal_neutrality_certificate(
    value: Any, *, synthetic: bool = False
) -> dict[str, Any]:
    certificate = dict(_mapping(value, name="z_direction_marginal_neutrality_certificate"))
    _exact_fields(
        certificate, _Z_NEUTRALITY_FIELDS, name="z_direction_marginal_neutrality_certificate"
    )
    coefficients = certificate["projection_coefficients_float_hex_in_fixed_33_basis"]
    residuals = certificate[
        "weighted_marginal_residuals_float_hex_in_ball_order_1_through_33"
    ]
    if not isinstance(coefficients, list) or len(coefficients) != 33 or not isinstance(
        residuals, list
    ) or len(residuals) != 33:
        raise JointResidualIncrementContractError(
            "z_direction_certificate_cardinality_mismatch"
        )
    for item in coefficients:
        _float_hex(item, name="projection_coefficient")
    residual_values = [
        abs(float.fromhex(_float_hex(item, name="weighted_marginal_residual")))
        for item in residuals
    ]
    _float_hex(certificate["scale_B_float_hex"], name="scale_B_float_hex", positive=True)
    max_abs = float.fromhex(
        _float_hex(certificate["max_abs_residual_float_hex"], name="max_abs_residual_float_hex", nonnegative=True)
    )
    tolerance = float.fromhex(
        _float_hex(certificate["tolerance_float_hex"], name="tolerance_float_hex", positive=True)
    )
    expected_pass = max_abs == max(residual_values) and max_abs <= tolerance
    if certificate["certificate_pass"] is not expected_pass:
        raise JointResidualIncrementContractError("z_direction_certificate_pass_mismatch")
    for name in (
        "coordinate_identity_digest",
        "q_base_full_distribution_content_digest",
        "raw_feature_content_digest",
        "certificate_digest",
    ):
        _digest(certificate[name], name=name)
    domain = (
        "dehps.m4.v2.joint.synthetic-warmup.z-direction-marginal-neutrality-certificate.v1"
        if synthetic
        else "dehps.m4.v2.joint-residual.z-direction-marginal-neutrality-certificate.v2"
    )
    _self_digest(
        certificate,
        digest_field="certificate_digest",
        domain=domain,
        input_fields=_Z_NEUTRALITY_FIELDS[:-1],
        name="z_direction_marginal_neutrality_certificate",
    )
    _validate_nested("z_direction_marginal_neutrality_certificate", certificate)
    return certificate


_TARGET_MARGINAL_FIELDS = (
    "coordinate_identity_digest",
    "reference_marginal_content_digest",
    "candidate_full_distribution_content_digest",
    "derived_candidate_marginal_content_digest",
    "per_ball_residuals_float_hex_in_ball_order_1_through_33",
    "max_abs_residual_float_hex",
    "tolerance_float_hex",
    "certificate_pass",
    "certificate_digest",
)


def validate_target_q_j_marginal_preservation_certificate(
    value: Any, *, synthetic: bool = False
) -> dict[str, Any]:
    certificate = dict(_mapping(value, name="target_q_j_marginal_preservation_certificate"))
    _exact_fields(
        certificate, _TARGET_MARGINAL_FIELDS, name="target_q_j_marginal_preservation_certificate"
    )
    residuals = certificate["per_ball_residuals_float_hex_in_ball_order_1_through_33"]
    if not isinstance(residuals, list) or len(residuals) != 33:
        raise JointResidualIncrementContractError(
            "target_q_j_marginal_residual_cardinality_mismatch"
        )
    values = [abs(float.fromhex(_float_hex(item, name="per_ball_residual"))) for item in residuals]
    max_abs = float.fromhex(
        _float_hex(certificate["max_abs_residual_float_hex"], name="max_abs_residual_float_hex", nonnegative=True)
    )
    tolerance = float.fromhex(
        _float_hex(certificate["tolerance_float_hex"], name="tolerance_float_hex", positive=True)
    )
    expected_pass = max_abs == max(values) and max_abs <= tolerance
    if certificate["certificate_pass"] is not expected_pass:
        raise JointResidualIncrementContractError(
            "target_q_j_marginal_certificate_pass_mismatch"
        )
    for name in (
        "coordinate_identity_digest",
        "reference_marginal_content_digest",
        "candidate_full_distribution_content_digest",
        "derived_candidate_marginal_content_digest",
        "certificate_digest",
    ):
        _digest(certificate[name], name=name)
    domain = (
        "dehps.m4.v2.joint.synthetic-warmup.marginal-preservation-certificate.v1"
        if synthetic
        else "dehps.m4.v2.joint-residual.marginal-preservation-certificate.v2"
    )
    _self_digest(
        certificate,
        digest_field="certificate_digest",
        domain=domain,
        input_fields=_TARGET_MARGINAL_FIELDS[:-1],
        name="target_q_j_marginal_preservation_certificate",
    )
    _validate_nested("target_q_j_marginal_preservation_certificate", certificate)
    return certificate


_NORMALIZATION_FIELDS = (
    "coordinate_identity_digest",
    "full_distribution_content_digest",
    "sum_probability_float_hex",
    "normalization_residual_float_hex",
    "minimum_probability_float_hex",
    "finite_nonnegative",
    "tolerance_float_hex",
    "certificate_pass",
    "certificate_digest",
)


def validate_normalization_certificate(value: Any) -> dict[str, Any]:
    certificate = dict(_mapping(value, name="normalization_certificate"))
    _exact_fields(certificate, _NORMALIZATION_FIELDS, name="normalization_certificate")
    total = float.fromhex(
        _float_hex(certificate["sum_probability_float_hex"], name="sum_probability_float_hex", nonnegative=True)
    )
    residual = float.fromhex(
        _float_hex(certificate["normalization_residual_float_hex"], name="normalization_residual_float_hex", nonnegative=True)
    )
    minimum = float.fromhex(
        _float_hex(certificate["minimum_probability_float_hex"], name="minimum_probability_float_hex", nonnegative=True)
    )
    tolerance = float.fromhex(
        _float_hex(certificate["tolerance_float_hex"], name="tolerance_float_hex", positive=True)
    )
    expected_pass = (
        certificate["finite_nonnegative"] is True
        and minimum >= 0.0
        and residual <= tolerance
        and abs(total - 1.0) <= tolerance
    )
    if certificate["certificate_pass"] is not expected_pass:
        raise JointResidualIncrementContractError("normalization_certificate_pass_mismatch")
    for name in (
        "coordinate_identity_digest",
        "full_distribution_content_digest",
        "certificate_digest",
    ):
        _digest(certificate[name], name=name)
    _self_digest(
        certificate,
        digest_field="certificate_digest",
        domain="dehps.m4.v2.joint-residual.normalization-certificate.v2",
        input_fields=_NORMALIZATION_FIELDS[:-1],
        name="normalization_certificate",
    )
    _validate_nested("normalization_certificate", certificate)
    return certificate


_Z_FIELDS = (
    "source_contract_digest",
    "preregistration_artifact_digest",
    "producer_execution_id",
    "joint_estimator_id",
    "temporal_composite_view_digest",
    "transition_ordinal",
    "issue",
    "support_kind",
    "creation_phase",
    "creation_target_ordinal",
    "prefix_last_ordinal",
    "prefix_outcome_chain_digest",
    "q_base_checkpoint_digest",
    "q_base_full_distribution_content_digest",
    "history_state",
    "raw_feature_content_digest",
    "projection_coefficients_float_hex",
    "scale_B_float_hex",
    "z_function_identity_digest",
    "orthogonality_certificate_digest",
    "marginal_preservation_certificate_digest",
    "checkpoint_key_digest",
    "previous_z_chain_digest",
    "checkpoint_digest",
)


def joint_z_checkpoint_key(
    *,
    source_contract_digest: str,
    preregistration_artifact_digest: str,
    producer_execution_id: str,
    transition_ordinal: int,
) -> str:
    return m4_v2_domain_digest(
        {
            "source_contract_digest": _digest(
                source_contract_digest, name="source_contract_digest"
            ),
            "preregistration_artifact_digest": _digest(
                preregistration_artifact_digest,
                name="preregistration_artifact_digest",
            ),
            "producer_execution_id": _execution_id(
                producer_execution_id, name="producer_execution_id"
            ),
            "transition_ordinal": _integer(
                transition_ordinal, name="transition_ordinal", minimum=2
            ),
        },
        domain="dehps.m4.v2.joint-residual.z-checkpoint-key.v2",
    )


def build_joint_z_checkpoint(
    *,
    source_contract_digest: str,
    preregistration_artifact_digest: str,
    producer_execution_id: str,
    temporal_composite_view_digest: str,
    q_base_checkpoint: Mapping[str, Any],
    history_state: int,
    raw_feature_content_digest: str,
    projection_coefficients_float_hex: Sequence[str],
    scale_B_float_hex: str,
    prefix_outcome_chain_digest: str,
    certificate_coordinate_identity: Mapping[str, Any],
    orthogonality_certificate: Mapping[str, Any],
    z_direction_certificate: Mapping[str, Any],
    previous_z_checkpoint_digests: Sequence[str],
) -> dict[str, Any]:
    q_base = validate_q_base_checkpoint(q_base_checkpoint)
    ordinal = q_base["transition_ordinal"]
    coordinate = validate_certificate_coordinate_identity(
        certificate_coordinate_identity
    )
    orthogonality = validate_orthogonality_certificate(
        orthogonality_certificate
    )
    neutrality = validate_z_direction_marginal_neutrality_certificate(
        z_direction_certificate
    )
    coefficients = [
        _float_hex(item, name="projection_coefficient")
        for item in projection_coefficients_float_hex
    ]
    if len(coefficients) != 33 or history_state not in (-1, 1):
        raise JointResidualIncrementContractError("joint_z_feature_identity_invalid")
    if (
        orthogonality["q_base_full_distribution_content_digest"]
        != q_base["q_base_full_distribution_content_digest"]
        or neutrality["q_base_full_distribution_content_digest"]
        != q_base["q_base_full_distribution_content_digest"]
        or orthogonality["raw_feature_content_digest"]
        != raw_feature_content_digest
        or neutrality["raw_feature_content_digest"] != raw_feature_content_digest
        or orthogonality["projection_coefficients_float_hex_in_fixed_33_basis"]
        != coefficients
        or neutrality["projection_coefficients_float_hex_in_fixed_33_basis"]
        != coefficients
        or neutrality["scale_B_float_hex"] != scale_B_float_hex
        or orthogonality["coordinate_identity_digest"]
        != coordinate["coordinate_digest"]
        or neutrality["coordinate_identity_digest"]
        != coordinate["coordinate_digest"]
        or coordinate["scope"] != "HISTORICAL_Z"
        or coordinate["source_contract_digest"] != source_contract_digest
        or coordinate["preregistration_artifact_digest"]
        != preregistration_artifact_digest
        or coordinate["producer_execution_id"] != producer_execution_id
        or coordinate["transition_ordinal"] != ordinal
        or coordinate["issue_or_sequence_coordinate_digest"] != q_base["issue"]
        or coordinate["support_kind"] != q_base["support_kind"]
        or orthogonality["certificate_pass"] is not True
        or neutrality["certificate_pass"] is not True
    ):
        raise JointResidualIncrementContractError(
            "joint_z_certificate_owner_equality_mismatch"
        )
    z_identity = {
        "q_base_full_distribution_content_digest": q_base[
            "q_base_full_distribution_content_digest"
        ],
        "history_state": history_state,
        "raw_feature_content_digest": _digest(
            raw_feature_content_digest, name="raw_feature_content_digest"
        ),
        "projection_coefficients_float_hex": coefficients,
        "scale_B_float_hex": _float_hex(
            scale_B_float_hex, name="scale_B_float_hex", positive=True
        ),
        "orthogonality_certificate_digest": orthogonality["certificate_digest"],
        "marginal_preservation_certificate_digest": neutrality[
            "certificate_digest"
        ],
    }
    previous = [_digest(item, name="previous_z_checkpoint_digest") for item in previous_z_checkpoint_digests]
    if len(previous) != ordinal - SUPPORT_START:
        raise JointResidualIncrementContractError(
            "joint_z_previous_chain_cardinality_mismatch"
        )
    checkpoint: dict[str, Any] = {
        "source_contract_digest": _digest(
            source_contract_digest, name="source_contract_digest"
        ),
        "preregistration_artifact_digest": _digest(
            preregistration_artifact_digest,
            name="preregistration_artifact_digest",
        ),
        "producer_execution_id": _execution_id(
            producer_execution_id, name="producer_execution_id"
        ),
        "joint_estimator_id": JOINT_ESTIMATOR_ID,
        "temporal_composite_view_digest": _digest(
            temporal_composite_view_digest, name="temporal_composite_view_digest"
        ),
        "transition_ordinal": ordinal,
        "issue": q_base["issue"],
        "support_kind": q_base["support_kind"],
        "creation_phase": (
            "PRE_T901_SUPPORT" if ordinal <= WARMUP_END else "TARGET_PRE_REVEAL"
        ),
        "creation_target_ordinal": TARGET_START if ordinal <= WARMUP_END else ordinal,
        "prefix_last_ordinal": ordinal - 1,
        "prefix_outcome_chain_digest": _digest(
            prefix_outcome_chain_digest, name="prefix_outcome_chain_digest"
        ),
        "q_base_checkpoint_digest": q_base["checkpoint_digest"],
        **z_identity,
        "z_function_identity_digest": m4_v2_domain_digest(
            z_identity,
            domain="dehps.m4.v2.joint-residual.z-function-content.v2",
        ),
        "checkpoint_key_digest": joint_z_checkpoint_key(
            source_contract_digest=source_contract_digest,
            preregistration_artifact_digest=preregistration_artifact_digest,
            producer_execution_id=producer_execution_id,
            transition_ordinal=ordinal,
        ),
        "previous_z_chain_digest": m4_v2_domain_digest(
            {"ordered_checkpoint_digests": previous},
            domain="dehps.m4.v2.joint-residual.z-checkpoint-chain.v2",
        ),
    }
    checkpoint["checkpoint_digest"] = m4_v2_domain_digest(
        checkpoint, domain="dehps.m4.v2.joint-residual.z-checkpoint.v2"
    )
    return validate_joint_z_checkpoint(
        checkpoint,
        q_base_checkpoint=q_base,
        orthogonality_certificate=orthogonality,
        z_direction_certificate=neutrality,
        certificate_coordinate_identity=coordinate,
        previous_z_checkpoint_digests=previous,
    )


def validate_joint_z_checkpoint(
    value: Any,
    *,
    q_base_checkpoint: Mapping[str, Any] | None = None,
    orthogonality_certificate: Mapping[str, Any] | None = None,
    z_direction_certificate: Mapping[str, Any] | None = None,
    certificate_coordinate_identity: Mapping[str, Any] | None = None,
    previous_z_checkpoint_digests: Sequence[str] | None = None,
) -> dict[str, Any]:
    checkpoint = dict(_mapping(value, name="joint_z_checkpoint"))
    _exact_fields(checkpoint, _Z_FIELDS, name="joint_z_checkpoint")
    ordinal = _integer(
        checkpoint["transition_ordinal"], name="transition_ordinal", minimum=2
    )
    if ordinal > SUPPORT_END:
        raise JointResidualIncrementContractError("joint_z_ordinal_out_of_range")
    expected_phase = "PRE_T901_SUPPORT" if ordinal <= WARMUP_END else "TARGET_PRE_REVEAL"
    expected_target = TARGET_START if ordinal <= WARMUP_END else ordinal
    if (
        checkpoint["joint_estimator_id"] != JOINT_ESTIMATOR_ID
        or checkpoint["support_kind"] != _support_kind(ordinal)
        or checkpoint["creation_phase"] != expected_phase
        or checkpoint["creation_target_ordinal"] != expected_target
        or checkpoint["prefix_last_ordinal"] != ordinal - 1
        or checkpoint["history_state"] not in (-1, 1)
    ):
        raise JointResidualIncrementContractError("joint_z_chronology_or_identity_mismatch")
    _issue(checkpoint["issue"])
    _execution_id(checkpoint["producer_execution_id"], name="producer_execution_id")
    coefficients = checkpoint["projection_coefficients_float_hex"]
    if not isinstance(coefficients, list) or len(coefficients) != 33:
        raise JointResidualIncrementContractError("joint_z_projection_cardinality_mismatch")
    for item in coefficients:
        _float_hex(item, name="projection_coefficient")
    _float_hex(checkpoint["scale_B_float_hex"], name="scale_B_float_hex", positive=True)
    for name in (
        "source_contract_digest",
        "preregistration_artifact_digest",
        "temporal_composite_view_digest",
        "prefix_outcome_chain_digest",
        "q_base_checkpoint_digest",
        "q_base_full_distribution_content_digest",
        "raw_feature_content_digest",
        "z_function_identity_digest",
        "orthogonality_certificate_digest",
        "marginal_preservation_certificate_digest",
        "checkpoint_key_digest",
        "previous_z_chain_digest",
        "checkpoint_digest",
    ):
        _digest(checkpoint[name], name=name)
    expected_z = m4_v2_domain_digest(
        {
            "q_base_full_distribution_content_digest": checkpoint[
                "q_base_full_distribution_content_digest"
            ],
            "history_state": checkpoint["history_state"],
            "raw_feature_content_digest": checkpoint["raw_feature_content_digest"],
            "projection_coefficients_float_hex": coefficients,
            "scale_B_float_hex": checkpoint["scale_B_float_hex"],
            "orthogonality_certificate_digest": checkpoint[
                "orthogonality_certificate_digest"
            ],
            "marginal_preservation_certificate_digest": checkpoint[
                "marginal_preservation_certificate_digest"
            ],
        },
        domain="dehps.m4.v2.joint-residual.z-function-content.v2",
    )
    if checkpoint["z_function_identity_digest"] != expected_z or checkpoint[
        "checkpoint_key_digest"
    ] != joint_z_checkpoint_key(
        source_contract_digest=checkpoint["source_contract_digest"],
        preregistration_artifact_digest=checkpoint[
            "preregistration_artifact_digest"
        ],
        producer_execution_id=checkpoint["producer_execution_id"],
        transition_ordinal=ordinal,
    ):
        raise JointResidualIncrementContractError("joint_z_content_or_key_mismatch")
    if q_base_checkpoint is not None:
        q_base = validate_q_base_checkpoint(q_base_checkpoint)
        if (
            q_base["transition_ordinal"] != ordinal
            or q_base["issue"] != checkpoint["issue"]
            or q_base["support_kind"] != checkpoint["support_kind"]
            or q_base["checkpoint_digest"] != checkpoint["q_base_checkpoint_digest"]
            or q_base["q_base_full_distribution_content_digest"]
            != checkpoint["q_base_full_distribution_content_digest"]
        ):
            raise JointResidualIncrementContractError("joint_z_q_base_dereference_mismatch")
    if orthogonality_certificate is not None:
        orth = validate_orthogonality_certificate(orthogonality_certificate)
        if (
            orth["certificate_digest"]
            != checkpoint["orthogonality_certificate_digest"]
            or orth["q_base_full_distribution_content_digest"]
            != checkpoint["q_base_full_distribution_content_digest"]
            or orth["raw_feature_content_digest"]
            != checkpoint["raw_feature_content_digest"]
            or orth["projection_coefficients_float_hex_in_fixed_33_basis"]
            != checkpoint["projection_coefficients_float_hex"]
            or orth["certificate_pass"] is not True
        ):
            raise JointResidualIncrementContractError("joint_z_orthogonality_owner_mismatch")
    if z_direction_certificate is not None:
        neutral = validate_z_direction_marginal_neutrality_certificate(
            z_direction_certificate
        )
        if (
            neutral["certificate_digest"]
            != checkpoint["marginal_preservation_certificate_digest"]
            or neutral["q_base_full_distribution_content_digest"]
            != checkpoint["q_base_full_distribution_content_digest"]
            or neutral["raw_feature_content_digest"]
            != checkpoint["raw_feature_content_digest"]
            or neutral["projection_coefficients_float_hex_in_fixed_33_basis"]
            != checkpoint["projection_coefficients_float_hex"]
            or neutral["scale_B_float_hex"] != checkpoint["scale_B_float_hex"]
            or neutral["certificate_pass"] is not True
        ):
            raise JointResidualIncrementContractError("joint_z_neutrality_owner_mismatch")
    if certificate_coordinate_identity is not None:
        coordinate = validate_certificate_coordinate_identity(
            certificate_coordinate_identity
        )
        if (
            coordinate["scope"] != "HISTORICAL_Z"
            or coordinate["source_contract_digest"]
            != checkpoint["source_contract_digest"]
            or coordinate["preregistration_artifact_digest"]
            != checkpoint["preregistration_artifact_digest"]
            or coordinate["producer_execution_id"]
            != checkpoint["producer_execution_id"]
            or coordinate["transition_ordinal"] != ordinal
            or coordinate["issue_or_sequence_coordinate_digest"]
            != checkpoint["issue"]
            or coordinate["support_kind"] != checkpoint["support_kind"]
            or (
                orthogonality_certificate is not None
                and orth["coordinate_identity_digest"]
                != coordinate["coordinate_digest"]
            )
            or (
                z_direction_certificate is not None
                and neutral["coordinate_identity_digest"]
                != coordinate["coordinate_digest"]
            )
        ):
            raise JointResidualIncrementContractError(
                "joint_z_certificate_coordinate_owner_mismatch"
            )
    if previous_z_checkpoint_digests is not None:
        previous = [_digest(item, name="previous_z_checkpoint_digest") for item in previous_z_checkpoint_digests]
        if len(previous) != ordinal - SUPPORT_START or checkpoint[
            "previous_z_chain_digest"
        ] != m4_v2_domain_digest(
            {"ordered_checkpoint_digests": previous},
            domain="dehps.m4.v2.joint-residual.z-checkpoint-chain.v2",
        ):
            raise JointResidualIncrementContractError("joint_z_previous_chain_mismatch")
    _self_digest(
        checkpoint,
        digest_field="checkpoint_digest",
        domain="dehps.m4.v2.joint-residual.z-checkpoint.v2",
        input_fields=_Z_FIELDS[:-1],
        name="joint_z_checkpoint",
    )
    _validate_nested("joint_z_checkpoint", checkpoint)
    return checkpoint


def build_joint_z_checkpoint_index(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    validated: list[dict[str, Any]] = []
    prior: list[str] = []
    for row in rows:
        checked = validate_joint_z_checkpoint(
            row, previous_z_checkpoint_digests=prior
        )
        validated.append(checked)
        prior.append(checked["checkpoint_digest"])
    chain = m4_v2_domain_digest(
        {"ordered_checkpoint_digests": prior},
        domain="dehps.m4.v2.joint-residual.z-checkpoint-chain.v2",
    )
    index: dict[str, Any] = {
        "row_count": len(validated),
        "transition_range": [SUPPORT_START, SUPPORT_END],
        "rows": validated,
        "ordered_checkpoint_digests": prior,
        "z_chain_digest": chain,
    }
    index["index_digest"] = m4_v2_domain_digest(
        {
            "row_count": index["row_count"],
            "transition_range": index["transition_range"],
            "z_chain_digest": chain,
        },
        domain="dehps.m4.v2.joint-residual.z-checkpoint-index.v2",
    )
    return validate_joint_z_checkpoint_index(index)


def validate_joint_z_checkpoint_index(value: Any) -> dict[str, Any]:
    index = dict(_mapping(value, name="joint_z_checkpoint_index"))
    fields = (
        "row_count",
        "transition_range",
        "rows",
        "ordered_checkpoint_digests",
        "z_chain_digest",
        "index_digest",
    )
    _exact_fields(index, fields, name="joint_z_checkpoint_index")
    if not isinstance(index["rows"], list) or not isinstance(
        index["ordered_checkpoint_digests"], list
    ):
        raise JointResidualIncrementContractError("joint_z_index_rows_invalid")
    validated: list[dict[str, Any]] = []
    prior: list[str] = []
    for row in index["rows"]:
        checked = validate_joint_z_checkpoint(
            row, previous_z_checkpoint_digests=prior
        )
        validated.append(checked)
        prior.append(checked["checkpoint_digest"])
    if (
        index["row_count"] != SUPPORT_COUNT
        or index["transition_range"] != [SUPPORT_START, SUPPORT_END]
        or [row["transition_ordinal"] for row in validated]
        != list(range(SUPPORT_START, SUPPORT_END + 1))
        or index["ordered_checkpoint_digests"] != prior
    ):
        raise JointResidualIncrementContractError(
            "joint_z_checkpoint_index_coverage_or_order_mismatch"
        )
    expected_chain = m4_v2_domain_digest(
        {"ordered_checkpoint_digests": prior},
        domain="dehps.m4.v2.joint-residual.z-checkpoint-chain.v2",
    )
    if index["z_chain_digest"] != expected_chain:
        raise JointResidualIncrementContractError("joint_z_chain_mismatch")
    _self_digest(
        index,
        digest_field="index_digest",
        domain="dehps.m4.v2.joint-residual.z-checkpoint-index.v2",
        input_fields=("row_count", "transition_range", "z_chain_digest"),
        name="joint_z_checkpoint_index",
    )
    _validate_nested("joint_z_checkpoint_index", index)
    return index


_ETA_FIELDS = (
    "target_ordinal",
    "issue",
    "training_range",
    "training_count",
    "training_z_prefix_chain_digest",
    "settled_training_outcome_prefix_digest",
    "eta_float_hex",
    "solver_terminal_code",
    "checkpoint_digest",
)


def build_joint_eta_checkpoint(
    *,
    target_ordinal: int,
    issue: str,
    ordered_prior_z_checkpoint_digests: Sequence[str],
    settled_training_outcome_prefix_digest: str,
    eta_float_hex: str,
    solver_terminal_code: str,
) -> dict[str, Any]:
    plan = joint_checkpoint_plan(target_ordinal)
    prior = [_digest(item, name="prior_z_checkpoint_digest") for item in ordered_prior_z_checkpoint_digests]
    if len(prior) != plan.eta_training_count:
        raise JointResidualIncrementContractError("eta_training_z_count_mismatch")
    eta_value = float.fromhex(_float_hex(eta_float_hex, name="eta_float_hex"))
    if not -1.0 < eta_value < 1.0:
        raise JointResidualIncrementContractError("eta_outside_strict_admissible_interval")
    if not isinstance(solver_terminal_code, str) or not solver_terminal_code:
        raise JointResidualIncrementContractError("solver_terminal_code_invalid")
    checkpoint: dict[str, Any] = {
        "target_ordinal": plan.target_ordinal,
        "issue": _issue(issue),
        "training_range": list(plan.eta_training_range),
        "training_count": plan.eta_training_count,
        "training_z_prefix_chain_digest": m4_v2_domain_digest(
            {"ordered_checkpoint_digests": prior},
            domain="dehps.m4.v2.joint-residual.z-checkpoint-chain.v2",
        ),
        "settled_training_outcome_prefix_digest": _digest(
            settled_training_outcome_prefix_digest,
            name="settled_training_outcome_prefix_digest",
        ),
        "eta_float_hex": eta_float_hex,
        "solver_terminal_code": solver_terminal_code,
    }
    checkpoint["checkpoint_digest"] = m4_v2_domain_digest(
        checkpoint, domain="dehps.m4.v2.joint-residual.eta-checkpoint.v2"
    )
    return validate_joint_eta_checkpoint(
        checkpoint,
        ordered_prior_z_checkpoint_digests=prior,
    )


def validate_joint_eta_checkpoint(
    value: Any,
    *,
    ordered_prior_z_checkpoint_digests: Sequence[str] | None = None,
) -> dict[str, Any]:
    checkpoint = dict(_mapping(value, name="joint_eta_checkpoint"))
    _exact_fields(checkpoint, _ETA_FIELDS, name="joint_eta_checkpoint")
    plan = joint_checkpoint_plan(checkpoint["target_ordinal"])
    if (
        checkpoint["training_range"] != list(plan.eta_training_range)
        or checkpoint["training_count"] != plan.eta_training_count
    ):
        raise JointResidualIncrementContractError("eta_training_range_mismatch")
    _issue(checkpoint["issue"])
    eta = float.fromhex(_float_hex(checkpoint["eta_float_hex"], name="eta_float_hex"))
    if not -1.0 < eta < 1.0:
        raise JointResidualIncrementContractError("eta_outside_strict_admissible_interval")
    if not isinstance(checkpoint["solver_terminal_code"], str) or not checkpoint[
        "solver_terminal_code"
    ]:
        raise JointResidualIncrementContractError("solver_terminal_code_invalid")
    for name in (
        "training_z_prefix_chain_digest",
        "settled_training_outcome_prefix_digest",
        "checkpoint_digest",
    ):
        _digest(checkpoint[name], name=name)
    if ordered_prior_z_checkpoint_digests is not None:
        prior = [_digest(item, name="prior_z_checkpoint_digest") for item in ordered_prior_z_checkpoint_digests]
        if len(prior) != plan.eta_training_count or checkpoint[
            "training_z_prefix_chain_digest"
        ] != m4_v2_domain_digest(
            {"ordered_checkpoint_digests": prior},
            domain="dehps.m4.v2.joint-residual.z-checkpoint-chain.v2",
        ):
            raise JointResidualIncrementContractError("eta_z_prefix_chain_mismatch")
    _self_digest(
        checkpoint,
        digest_field="checkpoint_digest",
        domain="dehps.m4.v2.joint-residual.eta-checkpoint.v2",
        input_fields=_ETA_FIELDS[:-1],
        name="joint_eta_checkpoint",
    )
    _validate_nested("joint_eta_checkpoint", checkpoint)
    return checkpoint


_TARGET_FIELDS = (
    "target_ordinal",
    "issue",
    "eta_checkpoint_digest",
    "target_z_checkpoint_digest",
    "q_base_full_distribution_content_digest",
    "q_j_marginal_content_digest",
    "q_j_full_distribution_content_digest",
    "normalization_certificate_digest",
    "marginal_preservation_certificate_digest",
    "checkpoint_digest",
)


def build_joint_target_prediction_checkpoint(
    *,
    eta_checkpoint: Mapping[str, Any],
    target_z_checkpoint: Mapping[str, Any],
    q_base_checkpoint: Mapping[str, Any],
    q_j_marginal_content_digest: str,
    q_j_full_distribution_content_digest: str,
    certificate_coordinate_identity: Mapping[str, Any],
    normalization_certificate: Mapping[str, Any],
    marginal_preservation_certificate: Mapping[str, Any],
) -> dict[str, Any]:
    eta = validate_joint_eta_checkpoint(eta_checkpoint)
    z = validate_joint_z_checkpoint(target_z_checkpoint)
    q_base = validate_q_base_checkpoint(q_base_checkpoint)
    coordinate = validate_certificate_coordinate_identity(
        certificate_coordinate_identity
    )
    normalization = validate_normalization_certificate(normalization_certificate)
    marginal = validate_target_q_j_marginal_preservation_certificate(
        marginal_preservation_certificate
    )
    target = eta["target_ordinal"]
    if (
        z["transition_ordinal"] != target
        or q_base["transition_ordinal"] != target
        or z["issue"] != eta["issue"]
        or q_base["issue"] != eta["issue"]
        or z["q_base_checkpoint_digest"] != q_base["checkpoint_digest"]
        or normalization["full_distribution_content_digest"]
        != q_j_full_distribution_content_digest
        or marginal["reference_marginal_content_digest"]
        != q_base["q_base_marginal_content_digest"]
        or marginal["candidate_full_distribution_content_digest"]
        != q_j_full_distribution_content_digest
        or marginal["derived_candidate_marginal_content_digest"]
        != q_j_marginal_content_digest
        or normalization["coordinate_identity_digest"]
        != coordinate["coordinate_digest"]
        or marginal["coordinate_identity_digest"]
        != coordinate["coordinate_digest"]
        or coordinate["scope"] != "HISTORICAL_TARGET_Q_J"
        or coordinate["source_contract_digest"] != z["source_contract_digest"]
        or coordinate["preregistration_artifact_digest"]
        != z["preregistration_artifact_digest"]
        or coordinate["producer_execution_id"] != z["producer_execution_id"]
        or coordinate["transition_ordinal"] != target
        or coordinate["issue_or_sequence_coordinate_digest"] != eta["issue"]
        or coordinate["support_kind"] != "ACCEPTED_TEMPORAL_EVALUATION"
        or normalization["certificate_pass"] is not True
        or marginal["certificate_pass"] is not True
    ):
        raise JointResidualIncrementContractError(
            "joint_target_cross_object_equality_mismatch"
        )
    checkpoint: dict[str, Any] = {
        "target_ordinal": target,
        "issue": eta["issue"],
        "eta_checkpoint_digest": eta["checkpoint_digest"],
        "target_z_checkpoint_digest": z["checkpoint_digest"],
        "q_base_full_distribution_content_digest": q_base[
            "q_base_full_distribution_content_digest"
        ],
        "q_j_marginal_content_digest": _digest(
            q_j_marginal_content_digest, name="q_j_marginal_content_digest"
        ),
        "q_j_full_distribution_content_digest": _digest(
            q_j_full_distribution_content_digest,
            name="q_j_full_distribution_content_digest",
        ),
        "normalization_certificate_digest": normalization["certificate_digest"],
        "marginal_preservation_certificate_digest": marginal[
            "certificate_digest"
        ],
    }
    checkpoint["checkpoint_digest"] = m4_v2_domain_digest(
        checkpoint,
        domain="dehps.m4.v2.joint-residual.target-prediction-checkpoint.v2",
    )
    return validate_joint_target_prediction_checkpoint(
        checkpoint,
        eta_checkpoint=eta,
        target_z_checkpoint=z,
        q_base_checkpoint=q_base,
        certificate_coordinate_identity=coordinate,
        normalization_certificate=normalization,
        marginal_preservation_certificate=marginal,
    )


def validate_joint_target_prediction_checkpoint(
    value: Any,
    *,
    eta_checkpoint: Mapping[str, Any] | None = None,
    target_z_checkpoint: Mapping[str, Any] | None = None,
    q_base_checkpoint: Mapping[str, Any] | None = None,
    certificate_coordinate_identity: Mapping[str, Any] | None = None,
    normalization_certificate: Mapping[str, Any] | None = None,
    marginal_preservation_certificate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    checkpoint = dict(_mapping(value, name="joint_target_prediction_checkpoint"))
    _exact_fields(checkpoint, _TARGET_FIELDS, name="joint_target_prediction_checkpoint")
    target = _integer(
        checkpoint["target_ordinal"], name="target_ordinal", minimum=TARGET_START
    )
    if target > TARGET_END:
        raise JointResidualIncrementContractError("joint_target_ordinal_out_of_range")
    _issue(checkpoint["issue"])
    for name in _TARGET_FIELDS[2:]:
        _digest(checkpoint[name], name=name)
    if eta_checkpoint is not None:
        eta = validate_joint_eta_checkpoint(eta_checkpoint)
        if (
            eta["target_ordinal"] != target
            or eta["issue"] != checkpoint["issue"]
            or eta["checkpoint_digest"] != checkpoint["eta_checkpoint_digest"]
        ):
            raise JointResidualIncrementContractError("target_eta_dereference_mismatch")
    if target_z_checkpoint is not None:
        z = validate_joint_z_checkpoint(target_z_checkpoint)
        if (
            z["transition_ordinal"] != target
            or z["issue"] != checkpoint["issue"]
            or z["checkpoint_digest"] != checkpoint["target_z_checkpoint_digest"]
            or z["q_base_full_distribution_content_digest"]
            != checkpoint["q_base_full_distribution_content_digest"]
        ):
            raise JointResidualIncrementContractError("target_z_dereference_mismatch")
    if q_base_checkpoint is not None:
        q_base = validate_q_base_checkpoint(q_base_checkpoint)
        if (
            q_base["transition_ordinal"] != target
            or q_base["q_base_full_distribution_content_digest"]
            != checkpoint["q_base_full_distribution_content_digest"]
        ):
            raise JointResidualIncrementContractError("target_q_base_dereference_mismatch")
    if certificate_coordinate_identity is not None:
        coordinate = validate_certificate_coordinate_identity(
            certificate_coordinate_identity
        )
        if (
            coordinate["scope"] != "HISTORICAL_TARGET_Q_J"
            or coordinate["transition_ordinal"] != target
            or coordinate["issue_or_sequence_coordinate_digest"]
            != checkpoint["issue"]
            or coordinate["support_kind"] != "ACCEPTED_TEMPORAL_EVALUATION"
            or (
                target_z_checkpoint is not None
                and (
                    coordinate["source_contract_digest"]
                    != z["source_contract_digest"]
                    or coordinate["preregistration_artifact_digest"]
                    != z["preregistration_artifact_digest"]
                    or coordinate["producer_execution_id"]
                    != z["producer_execution_id"]
                )
            )
        ):
            raise JointResidualIncrementContractError(
                "target_certificate_coordinate_owner_mismatch"
            )
    if normalization_certificate is not None:
        normalization = validate_normalization_certificate(normalization_certificate)
        if (
            normalization["certificate_digest"]
            != checkpoint["normalization_certificate_digest"]
            or normalization["full_distribution_content_digest"]
            != checkpoint["q_j_full_distribution_content_digest"]
            or (
                certificate_coordinate_identity is not None
                and normalization["coordinate_identity_digest"]
                != coordinate["coordinate_digest"]
            )
            or normalization["certificate_pass"] is not True
        ):
            raise JointResidualIncrementContractError("target_normalization_owner_mismatch")
    if marginal_preservation_certificate is not None:
        marginal = validate_target_q_j_marginal_preservation_certificate(
            marginal_preservation_certificate
        )
        if (
            marginal["certificate_digest"]
            != checkpoint["marginal_preservation_certificate_digest"]
            or marginal["candidate_full_distribution_content_digest"]
            != checkpoint["q_j_full_distribution_content_digest"]
            or marginal["derived_candidate_marginal_content_digest"]
            != checkpoint["q_j_marginal_content_digest"]
            or (
                q_base_checkpoint is not None
                and marginal["reference_marginal_content_digest"]
                != q_base["q_base_marginal_content_digest"]
            )
            or (
                certificate_coordinate_identity is not None
                and marginal["coordinate_identity_digest"]
                != coordinate["coordinate_digest"]
            )
            or marginal["certificate_pass"] is not True
        ):
            raise JointResidualIncrementContractError(
                "target_marginal_preservation_owner_mismatch"
            )
    _self_digest(
        checkpoint,
        digest_field="checkpoint_digest",
        domain="dehps.m4.v2.joint-residual.target-prediction-checkpoint.v2",
        input_fields=_TARGET_FIELDS[:-1],
        name="joint_target_prediction_checkpoint",
    )
    _validate_nested("joint_target_prediction_checkpoint", checkpoint)
    return checkpoint


def build_joint_target_prediction_index(
    *,
    eta_rows: Sequence[Mapping[str, Any]],
    prediction_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    etas = [validate_joint_eta_checkpoint(row) for row in eta_rows]
    predictions = [
        validate_joint_target_prediction_checkpoint(row) for row in prediction_rows
    ]
    eta_digests = [row["checkpoint_digest"] for row in etas]
    prediction_digests = [row["checkpoint_digest"] for row in predictions]
    eta_chain = m4_v2_domain_digest(
        {"ordered_eta_checkpoint_digests": eta_digests},
        domain="dehps.m4.v2.joint-residual.eta-checkpoint-chain.v2",
    )
    q_j_chain = m4_v2_domain_digest(
        {"ordered_prediction_checkpoint_digests": prediction_digests},
        domain="dehps.m4.v2.joint-residual.target-prediction-chain.v2",
    )
    index: dict[str, Any] = {
        "row_count": len(etas),
        "transition_range": [TARGET_START, TARGET_END],
        "eta_rows": etas,
        "prediction_rows": predictions,
        "ordered_eta_checkpoint_digests": eta_digests,
        "ordered_prediction_checkpoint_digests": prediction_digests,
        "eta_chain_digest": eta_chain,
        "q_j_chain_digest": q_j_chain,
    }
    index["index_digest"] = m4_v2_domain_digest(
        {
            "row_count": index["row_count"],
            "transition_range": index["transition_range"],
            "eta_chain_digest": eta_chain,
            "q_j_chain_digest": q_j_chain,
        },
        domain="dehps.m4.v2.joint-residual.target-prediction-index.v2",
    )
    return validate_joint_target_prediction_index(index)


def validate_joint_target_prediction_index(value: Any) -> dict[str, Any]:
    index = dict(_mapping(value, name="joint_target_prediction_index"))
    fields = (
        "row_count",
        "transition_range",
        "eta_rows",
        "prediction_rows",
        "ordered_eta_checkpoint_digests",
        "ordered_prediction_checkpoint_digests",
        "eta_chain_digest",
        "q_j_chain_digest",
        "index_digest",
    )
    _exact_fields(index, fields, name="joint_target_prediction_index")
    arrays = ("eta_rows", "prediction_rows", "ordered_eta_checkpoint_digests", "ordered_prediction_checkpoint_digests")
    if any(not isinstance(index[name], list) for name in arrays):
        raise JointResidualIncrementContractError("joint_target_index_rows_invalid")
    etas = [validate_joint_eta_checkpoint(row) for row in index["eta_rows"]]
    predictions = [
        validate_joint_target_prediction_checkpoint(row)
        for row in index["prediction_rows"]
    ]
    expected_targets = list(range(TARGET_START, TARGET_END + 1))
    if (
        index["row_count"] != TARGET_COUNT
        or index["transition_range"] != [TARGET_START, TARGET_END]
        or [row["target_ordinal"] for row in etas] != expected_targets
        or [row["target_ordinal"] for row in predictions] != expected_targets
        or any(eta["issue"] != prediction["issue"] for eta, prediction in zip(etas, predictions, strict=True))
        or index["ordered_eta_checkpoint_digests"]
        != [row["checkpoint_digest"] for row in etas]
        or index["ordered_prediction_checkpoint_digests"]
        != [row["checkpoint_digest"] for row in predictions]
    ):
        raise JointResidualIncrementContractError(
            "joint_target_prediction_index_coverage_or_order_mismatch"
        )
    expected_eta_chain = m4_v2_domain_digest(
        {"ordered_eta_checkpoint_digests": index["ordered_eta_checkpoint_digests"]},
        domain="dehps.m4.v2.joint-residual.eta-checkpoint-chain.v2",
    )
    expected_qj_chain = m4_v2_domain_digest(
        {
            "ordered_prediction_checkpoint_digests": index[
                "ordered_prediction_checkpoint_digests"
            ]
        },
        domain="dehps.m4.v2.joint-residual.target-prediction-chain.v2",
    )
    if index["eta_chain_digest"] != expected_eta_chain or index[
        "q_j_chain_digest"
    ] != expected_qj_chain:
        raise JointResidualIncrementContractError("joint_target_chain_mismatch")
    _self_digest(
        index,
        digest_field="index_digest",
        domain="dehps.m4.v2.joint-residual.target-prediction-index.v2",
        input_fields=(
            "row_count",
            "transition_range",
            "eta_chain_digest",
            "q_j_chain_digest",
        ),
        name="joint_target_prediction_index",
    )
    _validate_nested("joint_target_prediction_index", index)
    return index


def assert_joint_t901_t902_chronology(
    *,
    eta_901: Mapping[str, Any],
    z_901: Mapping[str, Any],
    eta_902: Mapping[str, Any],
    z_checkpoint_digests_2_through_901: Sequence[str],
) -> None:
    first = validate_joint_eta_checkpoint(
        eta_901,
        ordered_prior_z_checkpoint_digests=z_checkpoint_digests_2_through_901[:-1],
    )
    target_z = validate_joint_z_checkpoint(
        z_901,
        previous_z_checkpoint_digests=z_checkpoint_digests_2_through_901[:-1],
    )
    second = validate_joint_eta_checkpoint(
        eta_902,
        ordered_prior_z_checkpoint_digests=z_checkpoint_digests_2_through_901,
    )
    if (
        first["target_ordinal"] != 901
        or first["training_count"] != 899
        or target_z["transition_ordinal"] != 901
        or second["target_ordinal"] != 902
        or second["training_count"] != 900
        or z_checkpoint_digests_2_through_901[-1]
        != target_z["checkpoint_digest"]
    ):
        raise JointResidualIncrementContractError("joint_t901_t902_chronology_mismatch")


def _joint_sequence_seed(
    *, cell_index: int, replicate_index: int
) -> str:
    _, cell_id, fixture_id, horizon_id = JOINT_SYNTHETIC_CELLS[cell_index]
    cell_kind = "BASE" if cell_id.startswith("BASE:") else "LOCAL"
    fixture_or_target = (
        fixture_id if cell_kind == "BASE" else cell_id.split(":", 2)[1]
    )
    material = {
        "domain": "dehps.m4.v2.joint-residual-increment.seed-child.v1",
        "root_seed_full_sha256": JOINT_SYNTHETIC_ROOT_SEED_FULL_SHA256,
        "branch_id": JOINT_BRANCH_ID,
        "stage": "SYNTHETIC_SEQUENCE",
        "cell_kind_or_null": cell_kind,
        "fixture_or_target_id_or_null": fixture_or_target,
        "horizon_id_or_null": horizon_id,
        "replicate_index_or_null": replicate_index,
        "block_length_or_null": None,
        "scheme_id_or_null": None,
        "child_index": 0,
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_joint_synthetic_sequence_coordinate(
    *,
    health_contract_digest: str,
    seed_contract_digest: str,
    cell_index: int,
    replicate_index: int,
) -> dict[str, Any]:
    cell = _integer(cell_index, name="cell_index", minimum=0)
    replicate = _integer(replicate_index, name="replicate_index", minimum=0)
    if cell >= SYNTHETIC_CELL_COUNT or replicate >= SYNTHETIC_REPLICATES_PER_CELL:
        raise JointResidualIncrementContractError(
            "joint_synthetic_sequence_coordinate_out_of_range"
        )
    _, cell_id, fixture_id, horizon_id = JOINT_SYNTHETIC_CELLS[cell]
    coordinate: dict[str, Any] = {
        "branch_id": JOINT_BRANCH_ID,
        "fixture_source_digest": FIXTURE_SOURCE_DIGEST,
        "health_contract_digest": _digest(
            health_contract_digest, name="health_contract_digest"
        ),
        "seed_contract_digest": _digest(
            seed_contract_digest, name="seed_contract_digest"
        ),
        "synthetic_root_seed_full_sha256": JOINT_SYNTHETIC_ROOT_SEED_FULL_SHA256,
        "cell_index": cell,
        "cell_id": cell_id,
        "fixture_id": fixture_id,
        "horizon_id": horizon_id,
        "sequence_issue_count": 961 if horizon_id == "FORWARD_61" else 3481,
        "replicate_index": replicate,
        "sequence_seed_full_sha256": _joint_sequence_seed(
            cell_index=cell, replicate_index=replicate
        ),
    }
    coordinate["coordinate_digest"] = m4_v2_domain_digest(
        coordinate,
        domain="dehps.m4.v2.joint.synthetic-warmup.sequence-coordinate.v1",
    )
    return validate_joint_synthetic_sequence_coordinate(coordinate)


def validate_joint_synthetic_sequence_coordinate(value: Any) -> dict[str, Any]:
    coordinate = dict(_mapping(value, name="joint_synthetic_sequence_coordinate"))
    _validate_nested("synthetic_warmup_sequence_coordinate", coordinate)
    cell = _integer(coordinate["cell_index"], name="cell_index", minimum=0)
    replicate = _integer(
        coordinate["replicate_index"], name="replicate_index", minimum=0
    )
    if cell >= SYNTHETIC_CELL_COUNT or replicate >= SYNTHETIC_REPLICATES_PER_CELL:
        raise JointResidualIncrementContractError(
            "joint_synthetic_sequence_coordinate_out_of_range"
        )
    _, cell_id, fixture_id, horizon_id = JOINT_SYNTHETIC_CELLS[cell]
    expected = {
        "branch_id": JOINT_BRANCH_ID,
        "fixture_source_digest": FIXTURE_SOURCE_DIGEST,
        "synthetic_root_seed_full_sha256": JOINT_SYNTHETIC_ROOT_SEED_FULL_SHA256,
        "cell_id": cell_id,
        "fixture_id": fixture_id,
        "horizon_id": horizon_id,
        "sequence_issue_count": 961 if horizon_id == "FORWARD_61" else 3481,
        "sequence_seed_full_sha256": _joint_sequence_seed(
            cell_index=cell, replicate_index=replicate
        ),
    }
    if any(coordinate.get(key) != item for key, item in expected.items()):
        raise JointResidualIncrementContractError(
            "joint_synthetic_sequence_seed_or_cell_mismatch"
        )
    _self_digest(
        coordinate,
        digest_field="coordinate_digest",
        domain="dehps.m4.v2.joint.synthetic-warmup.sequence-coordinate.v1",
        input_fields=tuple(key for key in coordinate if key != "coordinate_digest"),
        name="joint_synthetic_sequence_coordinate",
    )
    return coordinate


def build_joint_synthetic_cell_descriptors() -> tuple[dict[str, Any], ...]:
    cells: list[dict[str, Any]] = []
    for cell_index, cell_id, fixture_id, horizon_id in JOINT_SYNTHETIC_CELLS:
        cell: dict[str, Any] = {
            "cell_index": cell_index,
            "cell_id": cell_id,
            "fixture_id": fixture_id,
            "horizon_id": horizon_id,
            "sequence_issue_count": 961 if horizon_id == "FORWARD_61" else 3481,
            "replicate_count": SYNTHETIC_REPLICATES_PER_CELL,
        }
        cell["cell_digest"] = m4_v2_domain_digest(
            cell, domain="dehps.m4.v2.joint.synthetic-warmup.cell.v1"
        )
        cells.append(validate_joint_synthetic_cell_descriptor(cell))
    return tuple(cells)


def validate_joint_synthetic_cell_descriptor(value: Any) -> dict[str, Any]:
    cell = dict(_mapping(value, name="joint_synthetic_cell_descriptor"))
    _validate_nested("synthetic_warmup_cell_descriptor", cell)
    cell_index = _integer(cell["cell_index"], name="cell_index", minimum=0)
    if cell_index >= SYNTHETIC_CELL_COUNT:
        raise JointResidualIncrementContractError(
            "joint_synthetic_cell_index_out_of_range"
        )
    _, cell_id, fixture_id, horizon_id = JOINT_SYNTHETIC_CELLS[cell_index]
    expected = {
        "cell_id": cell_id,
        "fixture_id": fixture_id,
        "horizon_id": horizon_id,
        "sequence_issue_count": 961 if horizon_id == "FORWARD_61" else 3481,
        "replicate_count": SYNTHETIC_REPLICATES_PER_CELL,
    }
    if any(cell.get(key) != item for key, item in expected.items()):
        raise JointResidualIncrementContractError(
            "joint_synthetic_cell_descriptor_mismatch"
        )
    _self_digest(
        cell,
        digest_field="cell_digest",
        domain="dehps.m4.v2.joint.synthetic-warmup.cell.v1",
        input_fields=tuple(key for key in cell if key != "cell_digest"),
        name="joint_synthetic_cell_descriptor",
    )
    return cell


def build_joint_synthetic_replicate_commitment(
    *,
    sequence_coordinate: Mapping[str, Any],
    ordered_transition_row_digests: Sequence[str],
    ordered_support_row_digests: Sequence[str],
    ordered_settled_row_digests: Sequence[str],
) -> dict[str, Any]:
    coordinate = validate_joint_synthetic_sequence_coordinate(sequence_coordinate)
    transition_digests = [
        _digest(item, name="transition_row_digest")
        for item in ordered_transition_row_digests
    ]
    support_digests = [
        _digest(item, name="support_row_digest")
        for item in ordered_support_row_digests
    ]
    settled_digests = [
        _digest(item, name="settled_row_digest")
        for item in ordered_settled_row_digests
    ]
    if not (
        len(transition_digests)
        == len(support_digests)
        == len(settled_digests)
        == WARMUP_COUNT
    ):
        raise JointResidualIncrementContractError(
            "joint_synthetic_transition_chain_count_mismatch"
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
            {"ordered_transition_row_digests": transition_digests},
            domain="dehps.m4.v2.joint.synthetic-warmup.transition-chain.v1",
        ),
        "support_chain_digest": m4_v2_domain_digest(
            {"ordered_support_row_digests": support_digests},
            domain="dehps.m4.v2.joint.synthetic-warmup.support-chain.v1",
        ),
        "settled_chain_digest": m4_v2_domain_digest(
            {"ordered_settled_row_digests": settled_digests},
            domain="dehps.m4.v2.joint.synthetic-warmup.settled-chain.v1",
        ),
    }
    commitment["replicate_digest"] = m4_v2_domain_digest(
        commitment, domain="dehps.m4.v2.joint.synthetic-warmup.replicate.v1"
    )
    return validate_joint_synthetic_replicate_commitment(
        commitment,
        sequence_coordinate=coordinate,
        ordered_transition_row_digests=transition_digests,
        ordered_support_row_digests=support_digests,
        ordered_settled_row_digests=settled_digests,
    )


def validate_joint_synthetic_replicate_commitment(
    value: Any,
    *,
    sequence_coordinate: Mapping[str, Any] | None = None,
    ordered_transition_row_digests: Sequence[str] | None = None,
    ordered_support_row_digests: Sequence[str] | None = None,
    ordered_settled_row_digests: Sequence[str] | None = None,
) -> dict[str, Any]:
    commitment = dict(_mapping(value, name="joint_synthetic_replicate_commitment"))
    _validate_nested("synthetic_warmup_replicate_commitment", commitment)
    if (
        commitment["transition_range"] != [WARMUP_START, WARMUP_END]
        or commitment["transition_count"] != WARMUP_COUNT
    ):
        raise JointResidualIncrementContractError(
            "joint_synthetic_replicate_transition_range_mismatch"
        )
    cell = _integer(commitment["cell_index"], name="cell_index", minimum=0)
    replicate = _integer(
        commitment["replicate_index"], name="replicate_index", minimum=0
    )
    if cell >= SYNTHETIC_CELL_COUNT or replicate >= SYNTHETIC_REPLICATES_PER_CELL:
        raise JointResidualIncrementContractError(
            "joint_synthetic_replicate_coordinate_out_of_range"
        )
    _, cell_id, fixture_id, horizon_id = JOINT_SYNTHETIC_CELLS[cell]
    if (
        commitment["cell_id"] != cell_id
        or commitment["fixture_id"] != fixture_id
        or commitment["horizon_id"] != horizon_id
        or commitment["sequence_seed_full_sha256"]
        != _joint_sequence_seed(cell_index=cell, replicate_index=replicate)
    ):
        raise JointResidualIncrementContractError(
            "joint_synthetic_replicate_cell_or_seed_mismatch"
        )
    if sequence_coordinate is not None:
        coordinate = validate_joint_synthetic_sequence_coordinate(
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
            raise JointResidualIncrementContractError(
                "joint_synthetic_replicate_coordinate_dereference_mismatch"
            )
    chain_specs = (
        (
            ordered_transition_row_digests,
            "transition_chain_digest",
            "ordered_transition_row_digests",
            "dehps.m4.v2.joint.synthetic-warmup.transition-chain.v1",
        ),
        (
            ordered_support_row_digests,
            "support_chain_digest",
            "ordered_support_row_digests",
            "dehps.m4.v2.joint.synthetic-warmup.support-chain.v1",
        ),
        (
            ordered_settled_row_digests,
            "settled_chain_digest",
            "ordered_settled_row_digests",
            "dehps.m4.v2.joint.synthetic-warmup.settled-chain.v1",
        ),
    )
    for raw_digests, field, input_field, domain in chain_specs:
        if raw_digests is None:
            continue
        digests = [_digest(item, name=input_field) for item in raw_digests]
        if len(digests) != WARMUP_COUNT or commitment[field] != m4_v2_domain_digest(
            {input_field: digests}, domain=domain
        ):
            raise JointResidualIncrementContractError(
                f"joint_synthetic_replicate_{field}_mismatch"
            )
    _self_digest(
        commitment,
        digest_field="replicate_digest",
        domain="dehps.m4.v2.joint.synthetic-warmup.replicate.v1",
        input_fields=tuple(key for key in commitment if key != "replicate_digest"),
        name="joint_synthetic_replicate_commitment",
    )
    return commitment


def build_joint_synthetic_replicate_index(
    rows: Sequence[Mapping[str, Any]], *, cell_manifest_digest: str
) -> dict[str, Any]:
    validated = [
        validate_joint_synthetic_replicate_commitment(row) for row in rows
    ]
    row_digests = [row["replicate_digest"] for row in validated]
    index: dict[str, Any] = {
        "branch_id": JOINT_BRANCH_ID,
        "cell_manifest_digest": _digest(
            cell_manifest_digest, name="cell_manifest_digest"
        ),
        "row_count": len(validated),
        "rows": validated,
        "row_digests_in_order": row_digests,
        "row_chain_digest": m4_v2_domain_digest(
            {"ordered_replicate_digests": row_digests},
            domain="dehps.m4.v2.joint.synthetic-warmup.replicate-chain.v1",
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
        domain="dehps.m4.v2.joint.synthetic-warmup.replicate-index.v1",
    )
    return validate_joint_synthetic_replicate_index(index)


def validate_joint_synthetic_replicate_index(value: Any) -> dict[str, Any]:
    index = dict(_mapping(value, name="joint_synthetic_replicate_index"))
    _validate_nested("synthetic_warmup_replicate_index", index)
    rows_raw = index["rows"]
    if not isinstance(rows_raw, list):
        raise JointResidualIncrementContractError(
            "joint_synthetic_replicate_index_rows_invalid"
        )
    rows = [
        validate_joint_synthetic_replicate_commitment(row) for row in rows_raw
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
        domain="dehps.m4.v2.joint.synthetic-warmup.replicate-chain.v1",
    )
    fixed = {
        "branch_id": JOINT_BRANCH_ID,
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
        raise JointResidualIncrementContractError(
            "joint_synthetic_replicate_index_grid_or_chain_mismatch"
        )
    _self_digest(
        index,
        digest_field="index_digest",
        domain="dehps.m4.v2.joint.synthetic-warmup.replicate-index.v1",
        input_fields=(
            "branch_id",
            "cell_manifest_digest",
            "row_count",
            "replicates_per_cell",
            "warmup_transition_count_per_replicate",
            "warmup_alias_position_count",
            "row_chain_digest",
        ),
        name="joint_synthetic_replicate_index",
    )
    return index


def _validate_joint_health_summary_lineage(
    health_body: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    health = _mapping(health_body, name="joint_health_body")
    summaries = _validate_nested(
        "health_cell_summary[14]", health.get("cell_summaries")
    )
    summary_digests: list[str] = []
    failed_cell_ids: list[str] = []
    for index, summary in enumerate(summaries):
        if (
            summary["cell_index"] != index
            or summary["cell_id"] != JOINT_SYNTHETIC_CELLS[index][1]
            or summary["horizon"] != JOINT_SYNTHETIC_CELLS[index][3]
            or summary["replicate_count"] != SYNTHETIC_REPLICATES_PER_CELL
            or not isinstance(summary["threshold_pass"], bool)
        ):
            raise JointResidualIncrementContractError(
                "joint_health_cell_summary_coordinate_mismatch"
            )
        _self_digest(
            summary,
            digest_field="cell_summary_digest",
            domain="dehps.m4.v2.joint.health-cell-summary.v2",
            input_fields=tuple(
                key for key in summary if key != "cell_summary_digest"
            ),
            name="joint_health_cell_summary",
        )
        summary_digests.append(summary["cell_summary_digest"])
        if summary["threshold_pass"] is False:
            failed_cell_ids.append(summary["cell_id"])
    expected_chain = m4_v2_domain_digest(
        {"ordered_cell_summary_digests": summary_digests},
        domain="dehps.m4.v2.joint.health-cell-summary-chain.v2",
    )
    if (
        health.get("cell_summary_chain_digest") != expected_chain
        or health.get("failed_cell_ids") != failed_cell_ids
    ):
        raise JointResidualIncrementContractError(
            "joint_health_cell_summary_owner_mismatch"
        )
    return tuple(summaries)


def validate_joint_synthetic_warmup_application(
    value: Any,
    *,
    health_body: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    application = dict(_mapping(value, name="joint_synthetic_warmup_application"))
    _validate_nested("synthetic_warmup_application", application)
    if (
        application.get("branch_id") != JOINT_BRANCH_ID
        or application.get("owner_artifact_type") != JOINT_HEALTH_ARTIFACT
        or application.get("fixture_source_digest") != FIXTURE_SOURCE_DIGEST
        or application.get("synthetic_root_seed_full_sha256")
        != JOINT_SYNTHETIC_ROOT_SEED_FULL_SHA256
        or application.get("support_model_id") != SUPPORT_MODEL_ID
        or application.get("joint_estimator_id") != JOINT_ESTIMATOR_ID
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
        raise JointResidualIncrementContractError(
            "joint_synthetic_application_fixed_identity_mismatch"
        )
    cells_raw = application.get("cells")
    if not isinstance(cells_raw, list) or len(cells_raw) != SYNTHETIC_CELL_COUNT:
        raise JointResidualIncrementContractError("joint_synthetic_cell_manifest_mismatch")
    cells = [validate_joint_synthetic_cell_descriptor(cell) for cell in cells_raw]
    observed = [
        (cell["cell_index"], cell["cell_id"], cell["fixture_id"], cell["horizon_id"])
        for cell in cells
    ]
    if observed != list(JOINT_SYNTHETIC_CELLS):
        raise JointResidualIncrementContractError(
            "joint_synthetic_cell_order_or_identity_mismatch"
        )
    ordered_cell_digests = [cell["cell_digest"] for cell in cells]
    cell_manifest_digest = m4_v2_domain_digest(
        {"ordered_cell_digests": ordered_cell_digests},
        domain="dehps.m4.v2.joint.synthetic-warmup.cell-manifest.v1",
    )
    replicate_index = validate_joint_synthetic_replicate_index(
        application.get("replicate_index")
    )
    if (
        application.get("ordered_cell_digests") != ordered_cell_digests
        or application.get("cell_manifest_digest") != cell_manifest_digest
        or replicate_index["cell_manifest_digest"] != cell_manifest_digest
        or application.get("replicate_index_digest")
        != replicate_index["index_digest"]
    ):
        raise JointResidualIncrementContractError(
            "joint_synthetic_cell_or_replicate_owner_mismatch"
        )
    horizons_raw = application.get("horizons")
    if not isinstance(horizons_raw, list) or len(horizons_raw) != 2:
        raise JointResidualIncrementContractError(
            "joint_synthetic_horizon_manifest_mismatch"
        )
    horizons: list[dict[str, Any]] = []
    expected_horizon_indices = (
        ("FORWARD_61", list(range(0, SYNTHETIC_CELL_COUNT, 2))),
        ("HISTORICAL_2581", list(range(1, SYNTHETIC_CELL_COUNT, 2))),
    )
    for raw, (horizon_id, cell_indices) in zip(
        horizons_raw, expected_horizon_indices, strict=True
    ):
        horizon = dict(_mapping(raw, name="joint_synthetic_horizon_summary"))
        _validate_nested("synthetic_horizon_summary", horizon)
        if (
            horizon["horizon_id"] != horizon_id
            or horizon["ordered_cell_indices"] != cell_indices
            or horizon["cell_count"] != 7
            or horizon["replicate_count"] != 3584
            or horizon["warmup_alias_position_count"] != 3_222_016
        ):
            raise JointResidualIncrementContractError(
                "joint_synthetic_horizon_partition_mismatch"
            )
        _self_digest(
            horizon,
            digest_field="horizon_digest",
            domain="dehps.m4.v2.joint.synthetic-warmup.horizon.v1",
            input_fields=tuple(
                key for key in horizon if key != "horizon_digest"
            ),
            name="joint_synthetic_horizon_summary",
        )
        horizons.append(horizon)
    ordered_horizon_digests = [item["horizon_digest"] for item in horizons]
    if (
        application.get("ordered_horizon_digests")
        != ordered_horizon_digests
        or application.get("horizon_summary_chain_digest")
        != m4_v2_domain_digest(
            {"ordered_horizon_digests": ordered_horizon_digests},
            domain="dehps.m4.v2.joint.synthetic-warmup.horizon-chain.v1",
        )
    ):
        raise JointResidualIncrementContractError(
            "joint_synthetic_horizon_chain_mismatch"
        )
    application_digest_fields = tuple(
        key
        for key in application
        if key not in {"application_digest", "cells", "replicate_index"}
    )
    _self_digest(
        application,
        digest_field="application_digest",
        domain="dehps.m4.v2.joint.synthetic-warmup.application.v1",
        input_fields=application_digest_fields,
        name="joint_synthetic_warmup_application",
    )
    if health_body is not None:
        health = _mapping(health_body, name="joint_health_body")
        equalities = {
            "branch_id": JOINT_BRANCH_ID,
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
            raise JointResidualIncrementContractError(
                "joint_synthetic_health_owner_equality_mismatch"
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
            raise JointResidualIncrementContractError(
                "joint_synthetic_application_owner_digest_mismatch"
            )
        health_summaries_raw = health.get("cell_summaries")
        if not isinstance(health_summaries_raw, list):
            raise JointResidualIncrementContractError(
                "joint_health_cell_summaries_missing"
            )
        health_summaries = _validate_nested(
            "health_cell_summary[14]", health_summaries_raw
        )
        summary_digests: list[str] = []
        for index, summary in enumerate(health_summaries):
            if (
                summary["cell_index"] != index
                or summary["cell_id"] != JOINT_SYNTHETIC_CELLS[index][1]
                or summary["horizon"] != JOINT_SYNTHETIC_CELLS[index][3]
                or summary["replicate_count"] != SYNTHETIC_REPLICATES_PER_CELL
            ):
                raise JointResidualIncrementContractError(
                    "joint_health_cell_summary_coordinate_mismatch"
                )
            _self_digest(
                summary,
                digest_field="cell_summary_digest",
                domain="dehps.m4.v2.joint.health-cell-summary.v2",
                input_fields=tuple(
                    key for key in summary if key != "cell_summary_digest"
                ),
                name="joint_health_cell_summary",
            )
            summary_digests.append(summary["cell_summary_digest"])
        expected_summary_chain = m4_v2_domain_digest(
            {"ordered_cell_summary_digests": summary_digests},
            domain="dehps.m4.v2.joint.health-cell-summary-chain.v2",
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
            raise JointResidualIncrementContractError(
                "joint_health_horizon_summary_owner_mismatch"
            )
    return application


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
        parent_branch_id not in {"MARGINAL_STATIC", TEMPORAL_BRANCH_ID}
        or terminal_decision != "BRANCH_INFORMATION_ACCEPTED"
        or accepted_for_downstream_baseline is not True
        or (
            parent_branch_id == MARGINAL_BRANCH_ID
            and (
                historical_artifact_digest != MARGINAL_RAW_P_ARTIFACT_DIGEST
                or historical_registration_digest
                != MARGINAL_RAW_P_REGISTRATION_DIGEST
            )
        )
        or replay_status != "REGISTERED_REPLAY_VERIFIED"
    ):
        raise JointResidualIncrementContractError(
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
        raise JointResidualIncrementContractError("accepted_parent_raw_p_invalid")
    return float(raw_primary_p_value)


def formal_holm_one_allowed(
    *,
    branch_id: str,
    terminal_decision: str | None,
    replay_status: str | None,
    temporal_is_current_evaluated_branch: bool = False,
    joint_has_formally_not_run: bool = False,
) -> bool:
    if (
        branch_id == JOINT_BRANCH_ID
        and temporal_is_current_evaluated_branch
        and joint_has_formally_not_run
        and terminal_decision is None
        and replay_status is None
    ):
        return True
    return terminal_decision in {
        "NOT_EVALUABLE_PARENT_NOT_ACCEPTED",
        "MEASUREMENT_REPAIR_REQUIRED",
        "INVALID_EXECUTION",
    } and replay_status == "REGISTERED_REPLAY_VERIFIED"


def validate_joint_holm_family(
    value: Any,
    *,
    marginal_raw_p_value: float,
    temporal_raw_p_value: float,
    joint_raw_p_value: float,
) -> dict[str, float]:
    family = dict(_mapping(value, name="joint_holm_family"))
    _exact_fields(
        family,
        ("MARGINAL_STATIC", TEMPORAL_BRANCH_ID, JOINT_BRANCH_ID),
        name="joint_holm_family",
    )
    expected = {
        "MARGINAL_STATIC": float(marginal_raw_p_value),
        TEMPORAL_BRANCH_ID: float(temporal_raw_p_value),
        JOINT_BRANCH_ID: float(joint_raw_p_value),
    }
    for branch_id, raw_p in family.items():
        if (
            isinstance(raw_p, bool)
            or not isinstance(raw_p, (int, float))
            or not math.isfinite(float(raw_p))
            or not 0.0 <= float(raw_p) <= 1.0
            or float(raw_p) != expected[branch_id]
        ):
            raise JointResidualIncrementContractError(
                f"joint_holm_raw_p_mismatch:{branch_id}"
            )
    return {key: float(item) for key, item in family.items()}


def validate_joint_candidate_lineage(
    body: Mapping[str, Any],
    *,
    baseline_body: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    candidate = dict(_mapping(body, name="joint_candidate_body"))
    if (
        candidate.get("branch_id") != JOINT_BRANCH_ID
        or candidate.get("model_id") != JOINT_MODEL_ID
        or candidate.get("joint_estimator_id") != JOINT_ESTIMATOR_ID
        or candidate.get("historical_fold_count") != TARGET_COUNT
        or candidate.get("production_action") != "none"
    ):
        raise JointResidualIncrementContractError("joint_candidate_fixed_identity_mismatch")
    z_index = validate_joint_z_checkpoint_index(
        candidate.get("joint_z_checkpoint_index")
    )
    target_index = validate_joint_target_prediction_index(
        candidate.get("joint_target_prediction_index")
    )
    if (
        candidate.get("joint_z_checkpoint_index_digest") != z_index["index_digest"]
        or candidate.get("joint_target_prediction_index_digest")
        != target_index["index_digest"]
        or candidate.get("fitted_parameter_chain_digest")
        != target_index["eta_chain_digest"]
    ):
        raise JointResidualIncrementContractError(
            "joint_candidate_nested_owner_equality_mismatch"
        )
    if baseline_body is not None:
        baseline = _mapping(baseline_body, name="joint_baseline_body")
        if (
            candidate.get("joint_baseline_artifact_digest")
            == candidate.get("temporal_parent_candidate_artifact_digest")
            or candidate.get("temporal_composite_view_digest")
            != baseline.get("temporal_composite_view_digest")
            or candidate.get("q_base_checkpoint_index_digest")
            != baseline.get("q_base_checkpoint_index_digest")
        ):
            raise JointResidualIncrementContractError(
                "joint_candidate_baseline_sibling_lineage_mismatch"
            )
    return candidate


def _validate_joint_parent_decision_and_replay(
    *,
    decision_artifact: Mapping[str, Any],
    replay_artifact: Mapping[str, Any],
    expected_branch_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate one upstream terminal pair without opening result artifacts."""

    try:
        decision = M4V2BranchDecisionArtifact.from_dict(decision_artifact).to_dict()
        replay = M4V2BranchDecisionReplayArtifact.from_dict(replay_artifact).to_dict()
    except Exception as exc:
        raise JointResidualIncrementContractError(
            "joint_parent_decision_replay_schema_invalid"
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
        raise JointResidualIncrementContractError(
            "joint_parent_decision_replay_identity_mismatch"
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
        raise JointResidualIncrementContractError(
            "joint_parent_terminal_unknown"
        ) from exc
    if (
        decision_body.get("scientific_decision") != scientific
        or decision_body.get("evaluation_status") != evaluation
        or decision_body.get("measurement_health") != health
        or decision_body.get("historical_evidence") not in historical
        or decision_body.get("accepted_for_downstream_baseline") is not accepted
    ):
        raise JointResidualIncrementContractError(
            "joint_parent_terminal_mapping_mismatch"
        )
    return decision, replay


def build_joint_parent_not_accepted_path(
    *,
    source_contract_digest: str,
    preregistration_artifact_digest: str,
    marginal_decision_artifact: Mapping[str, Any],
    marginal_replay_artifact: Mapping[str, Any],
    temporal_decision_artifact: Mapping[str, Any],
    temporal_replay_artifact: Mapping[str, Any],
    producer_execution_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build only Decision + Completion when either exact parent is not accepted."""

    source_digest = _digest(source_contract_digest, name="source_contract_digest")
    prereg_digest = _digest(
        preregistration_artifact_digest,
        name="preregistration_artifact_digest",
    )
    producer_id = _execution_id(
        producer_execution_id, name="producer_execution_id"
    )
    marginal_decision, marginal_replay = _validate_joint_parent_decision_and_replay(
        decision_artifact=marginal_decision_artifact,
        replay_artifact=marginal_replay_artifact,
        expected_branch_id=MARGINAL_BRANCH_ID,
    )
    temporal_decision, temporal_replay = _validate_joint_parent_decision_and_replay(
        decision_artifact=temporal_decision_artifact,
        replay_artifact=temporal_replay_artifact,
        expected_branch_id=TEMPORAL_BRANCH_ID,
    )
    parent_decisions = (marginal_decision, temporal_decision)
    if all(
        item["body"]["terminal_decision"] == "BRANCH_INFORMATION_ACCEPTED"
        and item["body"]["accepted_for_downstream_baseline"] is True
        for item in parent_decisions
    ):
        raise JointResidualIncrementContractError(
            "joint_parents_accepted_require_frozen_scientific_workload"
        )
    decision_body: dict[str, Any] = {
        "measurement_contract_key": MEASUREMENT_CONTRACT_KEY,
        "measurement_contract_digest": MEASUREMENT_CONTRACT_DIGEST,
        "branch_id": JOINT_BRANCH_ID,
        "estimand_digest": JOINT_ESTIMAND_DIGEST,
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
        "producer_task_key": JOINT_PRODUCER_TASK_KEY,
        "producer_execution_id": producer_id,
    }
    decision = build_joint_artifact(
        artifact_type=BRANCH_DECISION_ARTIFACT,
        body=decision_body,
        parent_digests=(
            source_digest,
            prereg_digest,
            marginal_decision["artifact_digest"],
            marginal_replay["artifact_digest"],
            temporal_decision["artifact_digest"],
            temporal_replay["artifact_digest"],
        ),
    )
    completion_body: dict[str, Any] = {
        "status": "COMPLETE",
        "measurement_contract_key": MEASUREMENT_CONTRACT_KEY,
        "measurement_contract_digest": MEASUREMENT_CONTRACT_DIGEST,
        "branch_id": JOINT_BRANCH_ID,
        "estimand_digest": JOINT_ESTIMAND_DIGEST,
        "decision_path": "PARENT_NOT_ACCEPTED",
        "source_contract_digest": source_digest,
        "preregistration_artifact_digest": prereg_digest,
        "registered_artifact_digests_in_order": [decision["artifact_digest"]],
        "decision_artifact_digest": decision["artifact_digest"],
        "terminal_fact": JOINT_TERMINAL_FACT,
        "completion_fact": JOINT_PRODUCER_COMPLETION_FACT,
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
        "exact_consumer": JOINT_REPLAY_TASK_KEY,
    }
    completion = build_joint_artifact(
        artifact_type=JOINT_COMPLETION_ARTIFACT,
        body=completion_body,
        parent_digests=(source_digest, prereg_digest, decision["artifact_digest"]),
    )
    validate_joint_path_artifacts("PARENT_NOT_ACCEPTED", (decision, completion))
    return decision, completion


def build_joint_branch_replay(
    *,
    source_contract_digest: str,
    decision_artifact: Mapping[str, Any],
    decision_registration_digest: str,
    decision_producer_execution_artifact_digest: str,
    replay_execution_id: str,
) -> dict[str, Any]:
    """Build the later read-only registered replay; no workload is reconstructed."""

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
        raise JointResidualIncrementContractError(
            "joint_replay_decision_schema_invalid"
        ) from exc
    decision_body = decision.to_body()
    if (
        decision_body.get("branch_id") != JOINT_BRANCH_ID
        or decision_body.get("measurement_contract_key")
        != MEASUREMENT_CONTRACT_KEY
        or decision_body.get("measurement_contract_digest")
        != MEASUREMENT_CONTRACT_DIGEST
        or decision_body.get("producer_task_key") != JOINT_PRODUCER_TASK_KEY
        or not decision.parent_digests
        or decision.parent_digests[0] != source_digest
    ):
        raise JointResidualIncrementContractError(
            "joint_replay_decision_identity_mismatch"
        )
    replay = M4V2BranchDecisionReplayArtifact(
        measurement_contract_key=MEASUREMENT_CONTRACT_KEY,
        measurement_contract_digest=MEASUREMENT_CONTRACT_DIGEST,
        branch_id=JOINT_BRANCH_ID,
        decision_artifact_digest=decision.artifact_digest,
        decision_registration_digest=registration_digest,
        decision_producer_task_key=JOINT_PRODUCER_TASK_KEY,
        decision_producer_execution_id=decision_body["producer_execution_id"],
        replay_task_key=JOINT_REPLAY_TASK_KEY,
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
    return validate_joint_branch_replay(replay.to_dict())


def validate_joint_branch_replay(value: Any) -> dict[str, Any]:
    envelope = validate_m4_v2_artifact_envelope(
        value, expected_artifact_type=BRANCH_REPLAY_ARTIFACT
    )
    typed = M4V2BranchDecisionReplayArtifact.from_dict(envelope)
    body = typed.to_body()
    if (
        body.get("branch_id") != JOINT_BRANCH_ID
        or body.get("measurement_contract_key") != MEASUREMENT_CONTRACT_KEY
        or body.get("measurement_contract_digest") != MEASUREMENT_CONTRACT_DIGEST
        or body.get("replay_task_key") != JOINT_REPLAY_TASK_KEY
        or body.get("replay_status") != "REGISTERED_REPLAY_VERIFIED"
        or body.get("source_integrity_verified") is not True
        or body.get("registered_content_verified") is not True
        or body.get("workload_rerun") is not False
    ):
        raise JointResidualIncrementContractError("joint_branch_replay_contract_mismatch")
    return typed.to_dict()


def _validate_joint_artifact_body(
    artifact_type: str, body: Mapping[str, Any]
) -> None:
    if body.get("measurement_contract_key") != MEASUREMENT_CONTRACT_KEY or body.get(
        "measurement_contract_digest"
    ) != MEASUREMENT_CONTRACT_DIGEST:
        raise JointResidualIncrementContractError(
            "joint_measurement_contract_identity_mismatch"
        )
    if body.get("branch_id") != JOINT_BRANCH_ID:
        raise JointResidualIncrementContractError("joint_branch_identity_mismatch")
    if (
        artifact_type != BRANCH_REPLAY_ARTIFACT
        and body.get("estimand_digest") != JOINT_ESTIMAND_DIGEST
    ):
        raise JointResidualIncrementContractError("joint_estimand_mismatch")
    if "dataset_content_digest" in body and body.get(
        "dataset_content_digest"
    ) != DATASET_CONTENT_DIGEST:
        raise JointResidualIncrementContractError(
            "joint_dataset_content_digest_mismatch"
        )
    if "fold_manifest_digest" in body and body.get(
        "fold_manifest_digest"
    ) != FOLD_MANIFEST_DIGEST:
        raise JointResidualIncrementContractError(
            "joint_fold_manifest_digest_mismatch"
        )
    if "production_action" in body and body.get("production_action") != "none":
        raise JointResidualIncrementContractError("joint_production_action_forbidden")
    if artifact_type == JOINT_DESIGN_ARTIFACT:
        if (
            body.get("status") != "FROZEN"
            or body.get("exact_consumer") != JOINT_PREREGISTRATION_TASK_KEY
            or body.get("historical_outcomes_read") != 0
            or body.get("scientific_computation") != 0
            or body.get("evidence_created") is not False
        ):
            raise JointResidualIncrementContractError(
                "joint_design_fixed_contract_mismatch"
            )
    elif artifact_type == JOINT_PREREGISTRATION_ARTIFACT:
        if (
            body.get("status") != "FROZEN"
            or body.get("support_model_id") != SUPPORT_MODEL_ID
            or body.get("joint_estimator_id") != JOINT_ESTIMATOR_ID
            or body.get("joint_estimator_id") == REQUEST481_PREDECESSOR_ESTIMATOR_ID
            or body.get("warmup_request_payload_digest")
            != WARMUP_REQUEST_PAYLOAD_DIGEST
            or body.get("planned_counts") != dict(PLANNED_COUNTS)
            or body.get("execution_authorized") is not False
            or body.get("result_payload_reads") != 0
            or body.get("historical_outcomes_read") != 0
            or body.get("scientific_computation") != 0
            or body.get("evidence_created") is not False
            or body.get("exact_consumer") != JOINT_PRODUCER_TASK_KEY
        ):
            raise JointResidualIncrementContractError(
                "joint_preregistration_fixed_contract_mismatch"
            )
    elif artifact_type == JOINT_BASELINE_ARTIFACT:
        if (
            body.get("status") != "COMPLETE"
            or body.get("baseline_id") != JOINT_BASELINE_ID
            or body.get("same_distribution_as_temporal_parent") is not True
            or body.get("distinct_artifact_from_temporal_parent") is not True
            or body.get("historical_support_count") != SUPPORT_COUNT
            or body.get("historical_fold_count") != TARGET_COUNT
        ):
            raise JointResidualIncrementContractError("joint_baseline_fixed_contract_mismatch")
        qbase = validate_q_base_checkpoint_index(body.get("q_base_checkpoint_index"))
        if body.get("q_base_checkpoint_index_digest") != qbase["index_digest"]:
            raise JointResidualIncrementContractError("joint_baseline_qbase_owner_mismatch")
    elif artifact_type == JOINT_HEALTH_ARTIFACT:
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
            raise JointResidualIncrementContractError(
                "joint_health_path_mapping_mismatch"
            )
        _validate_joint_health_summary_lineage(body)
        application = body.get("synthetic_warmup_application_or_null")
        if (application is None) is not (
            body.get("synthetic_warmup_application_digest_or_null") is None
        ):
            raise JointResidualIncrementContractError(
                "joint_synthetic_application_nullability_mismatch"
            )
        if application is not None:
            validate_joint_synthetic_warmup_application(application, health_body=body)
            if body.get("outer_evaluation_issue_count") != (
                SYNTHETIC_OUTER_EVALUATION_ISSUE_COUNT
            ):
                raise JointResidualIncrementContractError(
                    "joint_health_outer_evaluation_count_mismatch"
                )
    elif artifact_type == JOINT_HISTORICAL_ARTIFACT:
        if (
            body.get("status") != "COMPLETE"
            or body.get("decision_path") != "EVALUATED_COMPLETE"
            or body.get("marginal_raw_p_artifact_digest")
            != MARGINAL_RAW_P_ARTIFACT_DIGEST
            or body.get("score_count") != TARGET_COUNT
            or body.get("historical_child_count") != HISTORICAL_CHILD_COUNT
        ):
            raise JointResidualIncrementContractError("joint_historical_counter_mismatch")
        validate_joint_holm_family(
            body.get("holm_family_raw_p_values"),
            marginal_raw_p_value=body.get("holm_family_raw_p_values", {}).get(
                "MARGINAL_STATIC"
            ),
            temporal_raw_p_value=body.get("holm_family_raw_p_values", {}).get(
                TEMPORAL_BRANCH_ID
            ),
            joint_raw_p_value=body.get("raw_primary_p_value"),
        )
    elif artifact_type == JOINT_CANDIDATE_ARTIFACT:
        if body.get("status") != "COMPLETE":
            raise JointResidualIncrementContractError(
                "joint_candidate_status_mismatch"
            )
        validate_joint_candidate_lineage(body)
    elif artifact_type == JOINT_COMPLETION_ARTIFACT:
        path = body.get("decision_path")
        if path not in DECISION_PATHS:
            raise JointResidualIncrementContractError(
                "joint_completion_decision_path_mismatch"
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
            or body.get("exact_consumer") != JOINT_REPLAY_TASK_KEY
            or body.get("terminal_fact") != JOINT_TERMINAL_FACT
            or body.get("completion_fact") != JOINT_PRODUCER_COMPLETION_FACT
            or body.get("registration_count_including_mainline_execution")
            != joint_registration_plan(path).registration_count_including_mainline_execution
        ):
            raise JointResidualIncrementContractError(
                "joint_completion_fixed_contract_mismatch"
            )
        if path == "PARENT_NOT_ACCEPTED" and any(
            body[field] != 0 for field in count_fields
        ):
            raise JointResidualIncrementContractError(
                "joint_parent_not_accepted_work_counter_nonzero"
            )
        if path == "EVALUATED_COMPLETE":
            evaluated_counts = {
                "synthetic_replicate_count": SYNTHETIC_REPLICATE_COUNT,
                "warmup_transition_count_per_replicate": WARMUP_COUNT,
                "warmup_alias_position_count": SYNTHETIC_WARMUP_ALIAS_POSITION_COUNT,
                "historical_fold_count": TARGET_COUNT,
                "bootstrap_resample_count": SYNTHETIC_BOOTSTRAP_CHILD_COUNT,
            }
            if any(body.get(key) != item for key, item in evaluated_counts.items()):
                raise JointResidualIncrementContractError(
                    "joint_evaluated_completion_counter_mismatch"
                )
    elif artifact_type == JOINT_FAILURE_ARTIFACT:
        path = body.get("decision_path")
        expected_failure = {
            "IDENTITY_VALID_HEALTH_INVALID": ("HEALTH", False, False),
            "IDENTITY_VALID_HISTORICAL_REPAIR": ("HISTORICAL", True, True),
            "IDENTITY_VALID_HISTORICAL_INVALID": ("HISTORICAL", False, True),
        }
        if path not in expected_failure:
            raise JointResidualIncrementContractError(
                "joint_failure_decision_path_mismatch"
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
            raise JointResidualIncrementContractError(
                "joint_failure_fixed_mapping_mismatch"
            )
    elif artifact_type == BRANCH_REPLAY_ARTIFACT and (
        body.get("replay_status") != "REGISTERED_REPLAY_VERIFIED"
        or body.get("workload_rerun") is not False
    ):
        raise JointResidualIncrementContractError(
            "joint_replay_workload_boundary_breached"
        )


def build_joint_artifact(
    *,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
) -> dict[str, Any]:
    if artifact_type not in JOINT_ARTIFACT_TYPES:
        raise JointResidualIncrementContractError(
            f"joint_artifact_type_not_authorized:{artifact_type}"
        )
    body_mapping = dict(_mapping(body, name="joint_artifact_body"))
    _validate_joint_artifact_body(artifact_type, body_mapping)
    parents = tuple(_digest(item, name="parent_digest") for item in parent_digests)
    envelope = m4_v2_build_artifact_envelope(
        artifact_type=artifact_type,
        body=body_mapping,
        parent_digests=parents,
    )
    return validate_joint_artifact(envelope, expected_artifact_type=artifact_type)


def validate_joint_artifact(
    value: Any, *, expected_artifact_type: str | None = None
) -> dict[str, Any]:
    envelope = validate_m4_v2_artifact_envelope(
        value, expected_artifact_type=expected_artifact_type
    )
    artifact_type = envelope["artifact_type"]
    if artifact_type not in JOINT_ARTIFACT_TYPES:
        raise JointResidualIncrementContractError(
            f"joint_artifact_type_not_authorized:{artifact_type}"
        )
    _validate_joint_artifact_body(artifact_type, envelope["body"])
    body = envelope["body"]
    parents = envelope["parent_digests"]
    expected_parents: list[str] | None = None
    if artifact_type == JOINT_DESIGN_ARTIFACT:
        if len(parents) != 3 or parents[0] != body["source_contract_digest"]:
            raise JointResidualIncrementContractError(
                "joint_design_parent_order_mismatch"
            )
    elif artifact_type == JOINT_PREREGISTRATION_ARTIFACT:
        if parents[:2] != [
            body["source_contract_digest"],
            body["design_artifact_digest"],
        ] or len(parents) != 3:
            raise JointResidualIncrementContractError(
                "joint_preregistration_parent_order_mismatch"
            )
    elif artifact_type == JOINT_BASELINE_ARTIFACT:
        if (
            len(parents) != 3
            or parents[0] != body["source_contract_digest"]
            or parents[2] != body["temporal_parent_candidate_artifact_digest"]
        ):
            raise JointResidualIncrementContractError(
                "joint_baseline_parent_order_mismatch"
            )
    elif artifact_type == JOINT_HEALTH_ARTIFACT:
        expected_parents = [
            body["source_contract_digest"],
            body["preregistration_artifact_digest"],
            body["marginal_decision_digest"],
            body["marginal_replay_digest"],
            body["temporal_decision_digest"],
            body["temporal_replay_digest"],
        ]
        if body["decision_path"] == "EVALUATED_COMPLETE":
            if len(parents) != 7 or parents[:6] != expected_parents:
                raise JointResidualIncrementContractError(
                    "joint_health_parent_order_mismatch"
                )
            expected_parents = None
    elif artifact_type == JOINT_HISTORICAL_ARTIFACT:
        if (
            len(parents) != 6
            or parents[:2]
            != [
                body["source_contract_digest"],
                body["preregistration_artifact_digest"],
            ]
            or parents[3:] != [
                body["health_artifact_digest"],
                body["marginal_raw_p_artifact_digest"],
                body["temporal_raw_p_artifact_digest"],
            ]
        ):
            raise JointResidualIncrementContractError(
                "joint_historical_parent_order_mismatch"
            )
    elif artifact_type == JOINT_CANDIDATE_ARTIFACT:
        if (
            len(parents) != 4
            or parents[0] != body["source_contract_digest"]
            or parents[2:]
            != [
                body["joint_baseline_artifact_digest"],
                body["temporal_parent_candidate_artifact_digest"],
            ]
        ):
            raise JointResidualIncrementContractError(
                "joint_candidate_parent_order_mismatch"
            )
    elif artifact_type == JOINT_FAILURE_ARTIFACT:
        expected_count = (
            2 if body["decision_path"] == "IDENTITY_VALID_HEALTH_INVALID" else 3
        )
        if parents[:2] != [
            body["source_contract_digest"],
            body["preregistration_artifact_digest"],
        ] or len(parents) != expected_count:
            raise JointResidualIncrementContractError(
                "joint_failure_parent_order_mismatch"
            )
    elif artifact_type == JOINT_COMPLETION_ARTIFACT and parents[:2] != [
        body["source_contract_digest"],
        body["preregistration_artifact_digest"],
    ]:
        raise JointResidualIncrementContractError(
            "joint_completion_parent_prefix_mismatch"
        )
    if expected_parents is not None and parents != expected_parents:
        raise JointResidualIncrementContractError(
            "joint_artifact_parent_order_mismatch"
        )
    if artifact_type == BRANCH_DECISION_ARTIFACT:
        return M4V2BranchDecisionArtifact.from_dict(envelope).to_dict()
    if artifact_type == BRANCH_REPLAY_ARTIFACT:
        return validate_joint_branch_replay(envelope)
    return dict(envelope)


def validate_joint_path_artifacts(
    path: str, artifacts: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, Any], ...]:
    plan = joint_registration_plan(path)
    expected_types = tuple(
        item
        for item in plan.artifact_types_in_registration_order
        if item != MAINLINE_EXECUTION_ARTIFACT
    )
    validated = tuple(validate_joint_artifact(item) for item in artifacts)
    if tuple(item["artifact_type"] for item in validated) != expected_types:
        raise JointResidualIncrementContractError(
            f"joint_path_registration_order_mismatch:{plan.path}"
        )
    for artifact in validated:
        body = artifact["body"]
        if "decision_path" in body and body["decision_path"] != plan.path:
            raise JointResidualIncrementContractError(
                "joint_path_body_decision_path_mismatch"
            )
    if JOINT_COMPLETION_ARTIFACT in expected_types:
        completion_index = expected_types.index(JOINT_COMPLETION_ARTIFACT)
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
        baseline_envelope = path_artifacts.get(JOINT_BASELINE_ARTIFACT)
        health_envelope = path_artifacts.get(JOINT_HEALTH_ARTIFACT)
        historical_envelope = path_artifacts.get(JOINT_HISTORICAL_ARTIFACT)
        candidate_envelope = path_artifacts.get(JOINT_CANDIDATE_ARTIFACT)
        failure_envelope = path_artifacts.get(JOINT_FAILURE_ARTIFACT)
        baseline_lineage_mismatch = baseline_envelope is not None and (
            baseline_envelope["parent_digests"][1] != prereg_digest
        )
        health_lineage_mismatch = health_envelope is not None and (
            decision_envelope["parent_digests"][2:6]
            != [
                health_envelope["body"]["marginal_decision_digest"],
                health_envelope["body"]["marginal_replay_digest"],
                health_envelope["body"]["temporal_decision_digest"],
                health_envelope["body"]["temporal_replay_digest"],
            ]
            or (
                baseline_envelope is not None
                and health_envelope["parent_digests"][-1]
                != baseline_envelope["artifact_digest"]
            )
        )
        historical_lineage_mismatch = historical_envelope is not None and (
            baseline_envelope is None
            or health_envelope is None
            or historical_envelope["parent_digests"][2]
            != baseline_envelope["artifact_digest"]
            or historical_envelope["parent_digests"][3]
            != health_envelope["artifact_digest"]
        )
        candidate_lineage_mismatch = candidate_envelope is not None and (
            baseline_envelope is None
            or candidate_envelope["body"]["joint_baseline_artifact_digest"]
            != baseline_envelope["artifact_digest"]
            or candidate_envelope["body"][
                "temporal_parent_candidate_artifact_digest"
            ]
            != baseline_envelope["body"][
                "temporal_parent_candidate_artifact_digest"
            ]
        )
        historical_sibling_lineage_mismatch = historical_envelope is not None and (
            baseline_envelope is None
            or candidate_envelope is None
            or historical_envelope["body"]["temporal_composite_view_digest"]
            != baseline_envelope["body"]["temporal_composite_view_digest"]
            or historical_envelope["body"]["temporal_composite_view_digest"]
            != candidate_envelope["body"]["temporal_composite_view_digest"]
            or historical_envelope["body"]["q_base_checkpoint_index_digest"]
            != baseline_envelope["body"]["q_base_checkpoint_index_digest"]
            or historical_envelope["body"]["q_base_checkpoint_index_digest"]
            != candidate_envelope["body"]["q_base_checkpoint_index_digest"]
            or historical_envelope["body"]["joint_z_checkpoint_index_digest"]
            != candidate_envelope["body"]["joint_z_checkpoint_index_digest"]
            or historical_envelope["body"]["joint_eta_checkpoint_chain_digest"]
            != candidate_envelope["body"]["joint_target_prediction_index"][
                "eta_chain_digest"
            ]
            or historical_envelope["body"]["joint_target_prediction_index_digest"]
            != candidate_envelope["body"]["joint_target_prediction_index_digest"]
        )
        decision_model_lineage_mismatch = candidate_envelope is not None and (
            baseline_envelope is None
            or decision_envelope["body"]["accepted_model_artifact_digest"]
            != candidate_envelope["artifact_digest"]
            or decision_envelope["body"]["baseline_artifact_digest"]
            != baseline_envelope["artifact_digest"]
            or decision_envelope["body"]["baseline_source_model_artifact_digest"]
            != baseline_envelope["body"][
                "temporal_parent_candidate_artifact_digest"
            ]
        )
        failure_lineage_mismatch = (
            failure_envelope is not None
            and health_envelope is not None
            and failure_envelope["parent_digests"][2]
            != health_envelope["artifact_digest"]
        )
        if candidate_envelope is not None and baseline_envelope is not None:
            validate_joint_candidate_lineage(
                candidate_envelope["body"],
                baseline_body=baseline_envelope["body"],
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
            or len(decision_envelope["parent_digests"]) != 6 + len(path_leaves)
            or decision_envelope["parent_digests"][:2]
            != [source_digest, prereg_digest]
            or decision_suffix_mismatch
            or path_parent_mismatch
            or baseline_lineage_mismatch
            or health_lineage_mismatch
            or historical_lineage_mismatch
            or candidate_lineage_mismatch
            or historical_sibling_lineage_mismatch
            or decision_model_lineage_mismatch
            or failure_lineage_mismatch
        ):
            raise JointResidualIncrementContractError(
                "joint_completion_preceding_lineage_mismatch"
            )
    return validated


__all__ = [
    "BRANCH_DECISION_ARTIFACT",
    "BRANCH_REPLAY_ARTIFACT",
    "CHECKPOINT_ORDER_MANIFEST_DIGEST",
    "DATASET_CONTENT_DIGEST",
    "DECISION_PATHS",
    "FIXTURE_SOURCE_DIGEST",
    "FOLD_MANIFEST_DIGEST",
    "HISTORICAL_CHILD_COUNT",
    "JOINT_ARTIFACT_TYPES",
    "JOINT_BASELINE_ARTIFACT",
    "JOINT_BASELINE_ID",
    "JOINT_BRANCH_ID",
    "JOINT_CANDIDATE_ARTIFACT",
    "JOINT_COMPLETION_ARTIFACT",
    "JOINT_DESIGN_ARTIFACT",
    "JOINT_DESIGN_CAPABILITY",
    "JOINT_DESIGN_COMPLETION_FACT",
    "JOINT_DESIGN_TASK_KEY",
    "JOINT_ESTIMAND_DIGEST",
    "JOINT_ESTIMATOR_ID",
    "JOINT_FAILURE_ARTIFACT",
    "JOINT_HEALTH_ARTIFACT",
    "JOINT_HISTORICAL_ARTIFACT",
    "JOINT_MODEL_ID",
    "JOINT_PREREGISTRATION_ARTIFACT",
    "JOINT_PREREGISTRATION_CAPABILITY",
    "JOINT_PREREGISTRATION_COMPLETION_FACT",
    "JOINT_PREREGISTRATION_TASK_KEY",
    "JOINT_PRODUCER_CAPABILITY",
    "JOINT_PRODUCER_COMPLETION_FACT",
    "JOINT_PRODUCER_TASK_KEY",
    "JOINT_REPLAY_CAPABILITY",
    "JOINT_REPLAY_COMPLETION_FACT",
    "JOINT_REPLAY_FACT",
    "JOINT_REPLAY_TASK_KEY",
    "JOINT_SYNTHETIC_CELLS",
    "JOINT_SYNTHETIC_ROOT_SEED_FULL_SHA256",
    "JOINT_TERMINAL_FACT",
    "MAINLINE_EXECUTION_ARTIFACT",
    "MARGINAL_BRANCH_ID",
    "MARGINAL_RAW_P_ARTIFACT_DIGEST",
    "MARGINAL_RAW_P_REGISTRATION_DIGEST",
    "MAXIMUM_CONDITION_NUMBER",
    "MEASUREMENT_CONTRACT_DIGEST",
    "MEASUREMENT_CONTRACT_KEY",
    "NUMERICAL_TOLERANCE",
    "PARENT_ESTIMATOR_ID",
    "PLANNED_COUNTS",
    "REQUEST481_PREDECESSOR_ESTIMATOR_ID",
    "SUPPORT_COUNT",
    "SUPPORT_END",
    "SUPPORT_MODEL_ID",
    "SUPPORT_START",
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
    "TARGET_COUNT",
    "TARGET_END",
    "TARGET_START",
    "TEMPORAL_BRANCH_ID",
    "TEMPORAL_ESTIMAND_DIGEST",
    "TEMPORAL_ESTIMATOR_ID",
    "WARMUP_COUNT",
    "WARMUP_END",
    "WARMUP_REQUEST_PAYLOAD_DIGEST",
    "WARMUP_START",
    "JointChronologyPlan",
    "JointRegistrationPlan",
    "JointResidualIncrementContractError",
    "assert_joint_t901_t902_chronology",
    "build_certificate_coordinate_identity",
    "build_joint_artifact",
    "build_joint_branch_replay",
    "build_joint_eta_checkpoint",
    "build_joint_parent_not_accepted_path",
    "build_joint_synthetic_cell_descriptors",
    "build_joint_synthetic_replicate_commitment",
    "build_joint_synthetic_replicate_index",
    "build_joint_synthetic_sequence_coordinate",
    "build_joint_target_prediction_checkpoint",
    "build_joint_target_prediction_index",
    "build_joint_z_checkpoint",
    "build_joint_z_checkpoint_index",
    "build_q_base_checkpoint",
    "build_q_base_checkpoint_index",
    "build_q_base_reconstruction_certificate",
    "formal_holm_one_allowed",
    "joint_checkpoint_plan",
    "joint_registration_plan",
    "joint_z_checkpoint_key",
    "validate_accepted_parent_raw_p_lineage",
    "validate_certificate_coordinate_identity",
    "validate_joint_artifact",
    "validate_joint_branch_replay",
    "validate_joint_candidate_lineage",
    "validate_joint_eta_checkpoint",
    "validate_joint_holm_family",
    "validate_joint_path_artifacts",
    "validate_joint_synthetic_cell_descriptor",
    "validate_joint_synthetic_replicate_commitment",
    "validate_joint_synthetic_replicate_index",
    "validate_joint_synthetic_sequence_coordinate",
    "validate_joint_synthetic_warmup_application",
    "validate_joint_target_prediction_checkpoint",
    "validate_joint_target_prediction_index",
    "validate_joint_z_checkpoint",
    "validate_joint_z_checkpoint_index",
    "validate_normalization_certificate",
    "validate_orthogonality_certificate",
    "validate_q_base_checkpoint",
    "validate_q_base_checkpoint_index",
    "validate_q_base_reconstruction_certificate",
    "validate_target_q_j_marginal_preservation_certificate",
    "validate_z_direction_marginal_neutrality_certificate",
]
