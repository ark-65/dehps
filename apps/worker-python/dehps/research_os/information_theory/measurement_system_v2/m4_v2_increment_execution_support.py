from __future__ import annotations

import re
import sys
from collections.abc import Iterable, Iterator, Mapping, Sequence
from typing import Any, Final

import numpy as np

from dehps.research_os.models import (
    M4_V2_ARTIFACT_TYPE_REGISTRY,
    MainlineArtifactRegistration,
    ResearchOSValidationError,
    m4_v2_build_artifact_envelope,
    m4_v2_domain_digest,
    validate_m4_v2_artifact_envelope,
    validate_m4_v2_nested_schema,
)

from .temporal_probability_capsule import (
    BLAS_LAPACK_BINARY_CLOSURE_DIGEST,
    NUMERIC_RUNTIME_CONTRACT_DIGEST,
    WORKER_IMAGE_DIGEST,
    validate_numeric_runtime_contract,
    validate_sealed_probability_capsule_index,
)


class AcceptedWorkloadContractError(ValueError):
    """Raised before work starts when a workload identity is not exact."""


EVENT_TYPES: Final = (
    "WORKLOAD_STARTED",
    "HEALTH_REPLICATE_COMMIT",
    "HEALTH_AGGREGATE_COMPLETE",
    "HISTORICAL_FOLD_COMMIT",
    "HISTORICAL_SENSITIVITY_SCHEME_COMMIT",
    "HISTORICAL_AGGREGATE_COMPLETE",
    "TERMINAL_OUTCOME",
)
INPUT_BUNDLE_FIELDS: Final = (
    "schema_version",
    "branch_id",
    "source_contract_artifact_digest",
    "source_set_digest",
    "preregistration_artifact_digest",
    "producer_execution_id",
    "ordered_parent_decision_artifact_digests",
    "ordered_parent_replay_artifact_digests",
    "accepted_support_model_artifact_digest",
    "accepted_support_model_registration_digest",
    "ordered_holm_lineage_artifact_digests",
    "dataset_snapshot_artifact_digest",
    "dataset_content_digest",
    "fold_manifest_artifact_digest",
    "checkpoint_order_manifest_artifact_digest",
    "resampling_manifest_artifact_digest",
    "historical_execution_plan_artifact_digest",
    "fixture_source_artifact_digest",
    "synthetic_root_seed_full_sha256",
    "historical_root_seed_full_sha256",
    "warmup_request_payload_digest",
    "runtime_contract",
    "resolved_inputs",
    "input_bundle_digest",
)
RESOLVED_INPUT_FIELDS: Final = (
    "source_contract_envelope",
    "preregistration_envelope",
    "ordered_parent_decision_envelopes",
    "ordered_parent_replay_envelopes",
    "accepted_support_model_envelope",
    "accepted_support_model_registration_record",
    "ordered_holm_lineage_envelopes",
    "dataset_snapshot_envelope",
    "fold_manifest_envelope",
    "checkpoint_order_manifest_envelope",
    "resampling_manifest_envelope",
    "historical_execution_plan_envelope",
    "fixture_source_envelope",
    "seed_contract",
)
REGISTRATION_RECORD_FIELDS: Final = (
    "registration_digest",
    "execution_id",
    "control_plane_key",
    "task_key",
    "task_digest",
    "artifact_digest",
    "artifact_type",
    "schema_version",
    "artifact_path",
    "parent_digests",
    "git_commit",
)
EVENT_FIELDS: Final = (
    "schema_version",
    "input_bundle_digest",
    "producer_task_key",
    "producer_execution_id",
    "branch_id",
    "event_index",
    "event_type",
    "coordinate_key",
    "payload_schema",
    "payload",
    "payload_digest",
    "previous_event_digest_or_null",
    "event_digest",
)
RESUME_INDEX_FIELDS: Final = (
    "schema_version",
    "input_bundle_digest",
    "producer_task_key",
    "producer_execution_id",
    "branch_id",
    "events",
    "ordered_event_digests",
    "next_event_index",
    "next_coordinate",
    "terminal_seen",
    "execution_subpath_or_null",
    "decision_path_or_null",
    "transcript_prefix_digest",
    "resume_index_digest",
)
ROLLING_PREFIX_ROOT_V2_FIELDS: Final = (
    "schema_version",
    "input_bundle_digest",
    "producer_task_key",
    "producer_execution_id",
    "branch_id",
    "event_index",
    "event_digest",
    "previous_prefix_root_digest_or_null",
)
RESUME_DELTA_V2_FIELDS: Final = (
    "schema_version",
    "input_bundle_digest",
    "producer_task_key",
    "producer_execution_id",
    "branch_id",
    "event_index",
    "event_digest",
    "previous_delta_digest_or_null",
    "previous_prefix_root_digest_or_null",
    "prefix_root_digest",
    "next_event_index",
    "next_coordinate",
    "terminal_seen",
    "execution_subpath_or_null",
    "decision_path_or_null",
    "latest_checkpoint_event_count",
    "latest_checkpoint_resume_index_digest_or_null",
    "delta_digest",
)
RESUME_JOURNAL_HEAD_V2_FIELDS: Final = (
    "schema_version",
    "input_bundle_digest",
    "producer_task_key",
    "producer_execution_id",
    "branch_id",
    "last_event_index",
    "last_event_digest",
    "last_delta_digest",
    "prefix_root_digest",
    "next_event_index",
    "next_coordinate",
    "terminal_seen",
    "execution_subpath_or_null",
    "decision_path_or_null",
    "latest_checkpoint_event_count",
    "latest_checkpoint_resume_index_digest_or_null",
    "latest_checkpoint_snapshot_path_or_null",
    "latest_checkpoint_reference_digest_or_null",
    "latest_checkpoint_reference_path_or_null",
    "head_digest",
)
RESUME_CHECKPOINT_REFERENCE_V2_FIELDS: Final = (
    "schema_version",
    "input_bundle_digest",
    "producer_task_key",
    "producer_execution_id",
    "branch_id",
    "checkpoint_event_count",
    "checkpoint_last_event_digest",
    "checkpoint_last_delta_digest",
    "checkpoint_prefix_root_digest",
    "v1_resume_index_digest",
    "v1_resume_snapshot_path",
    "checkpoint_reference_digest",
)
EVALUATED_RESUME_CHECKPOINT_COUNTS_V2: Final = (
    1,
    2,
    4,
    8,
    16,
    32,
    64,
    128,
    256,
    512,
    1024,
    2048,
    4096,
    8192,
    9761,
)
TRANSCRIPT_FIELDS: Final = (
    "schema_version",
    "input_bundle_digest",
    "producer_task_key",
    "producer_execution_id",
    "branch_id",
    "execution_subpath",
    "decision_path",
    "events",
    "ordered_event_digests",
    "event_count",
    "terminal_event_digest",
    "preterminal_transcript_digest",
    "transcript_digest",
)
STARTED_PAYLOAD_FIELDS: Final = (
    "input_bundle_digest",
    "producer_task_key",
    "producer_execution_id",
    "branch_id",
    "source_contract_digest",
    "preregistration_artifact_digest",
    "parent_decision_artifact_digests_in_order",
    "parent_replay_artifact_digests_in_order",
    "scientific_execution_started",
    "start_phase",
    "rng_draw_count",
    "synthetic_replicate_count",
    "historical_fold_count",
    "bootstrap_resample_count",
)
TERMINAL_PAYLOAD_FIELDS: Final = (
    "execution_subpath",
    "decision_path",
    "failure_stage",
    "terminal_decision",
    "scientific_decision",
    "evaluation_status",
    "measurement_health",
    "historical_evidence",
    "baseline_artifact_body_or_null",
    "health_artifact_body_or_null",
    "historical_artifact_body_or_null",
    "candidate_artifact_body_or_null",
    "failure_artifact_body_or_null",
    "expected_baseline_artifact_digest_or_null",
    "expected_health_artifact_digest_or_null",
    "expected_historical_artifact_digest_or_null",
    "expected_candidate_artifact_digest_or_null",
    "expected_failure_artifact_digest_or_null",
    "completed_fold_count",
    "completed_resample_count",
    "reason_codes",
    "planned_counts",
    "preterminal_transcript_digest",
)
_EVENT_PAYLOAD_SCHEMAS: Final = {
    "TEMPORAL_MARGINAL_INCREMENT": {
        "WORKLOAD_STARTED": "dehps-m4-v2-temporal-accepted-workload-started.v1",
        "HEALTH_REPLICATE_COMMIT": "Request486:shared_nested_schemas.synthetic_health_replicate_evidence_commitment:TEMPORAL_MARGINAL_INCREMENT",
        "HEALTH_AGGREGATE_COMPLETE": "dehps-m4-v2-temporal-marginal-increment-health-aggregate.v2",
        "HISTORICAL_FOLD_COMMIT": "Request485:accepted_temporal_evaluation_q_t_row+Request486:historical_score_row",
        "HISTORICAL_SENSITIVITY_SCHEME_COMMIT": "Request486:shared_nested_schemas.sensitivity_summary:TEMPORAL_MARGINAL_INCREMENT",
        "HISTORICAL_AGGREGATE_COMPLETE": "dehps-m4-v2-temporal-marginal-increment-historical-aggregate.v2",
        "TERMINAL_OUTCOME": "dehps-m4-v2-accepted-workload-terminal-outcome.v1:TEMPORAL_MARGINAL_INCREMENT",
    },
    "JOINT_RESIDUAL_INCREMENT": {
        "WORKLOAD_STARTED": "dehps-m4-v2-joint-accepted-workload-started.v1",
        "HEALTH_REPLICATE_COMMIT": "Request486:shared_nested_schemas.synthetic_health_replicate_evidence_commitment:JOINT_RESIDUAL_INCREMENT",
        "HEALTH_AGGREGATE_COMPLETE": "dehps-m4-v2-joint-residual-measurement-health.v2",
        "HISTORICAL_FOLD_COMMIT": "Request486:joint_target_prediction_checkpoint+historical_score_row",
        "HISTORICAL_SENSITIVITY_SCHEME_COMMIT": "Request486:shared_nested_schemas.sensitivity_summary:JOINT_RESIDUAL_INCREMENT",
        "HISTORICAL_AGGREGATE_COMPLETE": "dehps-m4-v2-joint-residual-historical-execution.v2",
        "TERMINAL_OUTCOME": "dehps-m4-v2-accepted-workload-terminal-outcome.v1:JOINT_RESIDUAL_INCREMENT",
    },
}
_AGGREGATE_IDENTITIES: Final = {
    "TEMPORAL_MARGINAL_INCREMENT": {
        "HEALTH_AGGREGATE_COMPLETE": (
            "M4V2TemporalMarginalIncrementHealthAggregateArtifact",
            "dehps-m4-v2-temporal-marginal-increment-health-aggregate.v2",
        ),
        "HISTORICAL_AGGREGATE_COMPLETE": (
            "M4V2TemporalMarginalIncrementHistoricalAggregateArtifact",
            "dehps-m4-v2-temporal-marginal-increment-historical-aggregate.v2",
        ),
    },
    "JOINT_RESIDUAL_INCREMENT": {
        "HEALTH_AGGREGATE_COMPLETE": (
            "M4V2JointResidualMeasurementHealthArtifact",
            "dehps-m4-v2-joint-residual-measurement-health.v2",
        ),
        "HISTORICAL_AGGREGATE_COMPLETE": (
            "M4V2JointResidualHistoricalExecutionArtifact",
            "dehps-m4-v2-joint-residual-historical-execution.v2",
        ),
    },
}
_PAYLOAD_DIGEST_SUFFIX: Final = {
    "WORKLOAD_STARTED": "accepted-workload-started.v1",
    "HEALTH_AGGREGATE_COMPLETE": "accepted-workload-health-aggregate-body-commit.v1",
    "HISTORICAL_FOLD_COMMIT": "accepted-workload-historical-fold-commit.v1",
    "HISTORICAL_SENSITIVITY_SCHEME_COMMIT": (
        "accepted-workload-historical-sensitivity-scheme-commit.v1"
    ),
    "HISTORICAL_AGGREGATE_COMPLETE": (
        "accepted-workload-historical-aggregate-body-commit.v1"
    ),
    "TERMINAL_OUTCOME": "accepted-workload-terminal-outcome.v1",
}
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
HISTORICAL_SETTLED_OUTCOME_DOMAIN: Final = (
    "dehps.m4.v2.historical-settled-outcome.v1"
)

REGISTERED_EXECUTION_PLAN_FIELDS: Final = (
    "status",
    "source_contract_digest",
    "dataset_snapshot_digest",
    "dataset_content_digest",
    "fold_manifest_digest",
    "checkpoint_order_manifest_digest",
    "resampling_manifest_digest",
    "inference_algorithms",
    "time_stability",
    "execution",
    "formal_historical_execution_authorized",
    "automatic_evidence_from_preregistration",
    "next_consumer",
    "formal_historical_folds_executed",
    "bootstrap_children_executed",
    "historical_scores_computed",
    "statistical_results_read",
    "evidence_created",
    "accepted_model_artifact_digest",
    "promotion_gate_opened",
    "duplicate_validation",
    "production_action",
)
REGISTERED_HISTORICAL_SCHEME_IDS: Final = (
    "MOVING_BLOCK_NONCIRCULAR_LENGTH_5_PRIMARY",
    "MOVING_BLOCK_NONCIRCULAR_LENGTH_3_SENSITIVITY",
    "MOVING_BLOCK_NONCIRCULAR_LENGTH_8_SENSITIVITY",
    "MOVING_BLOCK_NONCIRCULAR_LENGTH_13_SENSITIVITY",
    "STATIONARY_EXPECTED_LENGTH_3_SENSITIVITY",
    "STATIONARY_EXPECTED_LENGTH_5_SENSITIVITY",
    "STATIONARY_EXPECTED_LENGTH_8_SENSITIVITY",
    "STATIONARY_EXPECTED_LENGTH_13_SENSITIVITY",
)

_RUNTIME_CONTRACT: Final = {
    "python_implementation": "cpython",
    "python_version": "3.14.4",
    "numpy_version": "2.4.6",
    "byteorder": "little",
    "float_identity": (
        "IEEE-754 binary64 values serialized only by the already frozen "
        "float.hex and big-endian transport rules"
    ),
    "mismatch_rule": "fail before workload start; no compatibility fallback",
}


def _branch_value(branch_id: str, temporal: str, joint: str) -> str:
    if branch_id == "TEMPORAL_MARGINAL_INCREMENT":
        return temporal
    if branch_id == "JOINT_RESIDUAL_INCREMENT":
        return joint
    raise AcceptedWorkloadContractError("accepted_workload_branch_invalid")


def producer_task_key(branch_id: str) -> str:
    return _branch_value(
        branch_id,
        "m4-v2-temporal-marginal-increment-historical-measurement-gate-compiler",
        "m4-v2-joint-residual-increment-historical-measurement-gate-compiler",
    )


def _domain(branch_id: str, suffix: str) -> str:
    return f"{_branch_value(branch_id, 'dehps.m4.v2.temporal', 'dehps.m4.v2.joint')}.{suffix}"


def _closed(value: Mapping[str, Any], fields: Sequence[str], name: str) -> dict[str, Any]:
    result = dict(value)
    if set(result) != set(fields):
        raise AcceptedWorkloadContractError(f"{name}_fields_invalid")
    return {field: result[field] for field in fields}


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise AcceptedWorkloadContractError(f"{name}_invalid")
    return value


def historical_settled_outcome_digest(
    *, evaluation_ordinal: int, issue: str, red_numbers: Sequence[int]
) -> str:
    """Build Request516's branch-neutral registered outcome identity."""

    if (
        isinstance(evaluation_ordinal, bool)
        or not isinstance(evaluation_ordinal, int)
        or not 901 <= evaluation_ordinal <= 3481
        or not isinstance(issue, str)
        or not issue
    ):
        raise AcceptedWorkloadContractError(
            "accepted_workload_settled_outcome_owner_invalid"
        )
    numbers = list(red_numbers)
    if (
        len(numbers) != 6
        or any(type(value) is not int or not 1 <= value <= 33 for value in numbers)
        or numbers != sorted(set(numbers))
    ):
        raise AcceptedWorkloadContractError(
            "accepted_workload_settled_outcome_owner_invalid"
        )
    return m4_v2_domain_digest(
        {
            "evaluation_ordinal": evaluation_ordinal,
            "issue": issue,
            "red_numbers": numbers,
        },
        domain=HISTORICAL_SETTLED_OUTCOME_DOMAIN,
    )


def _envelope(
    value: Any, *, expected_digest: str, name: str, typed: bool = False
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AcceptedWorkloadContractError(f"{name}_missing")
    envelope = dict(value)
    if envelope.get("artifact_digest") != expected_digest:
        raise AcceptedWorkloadContractError(f"{name}_digest_mismatch")
    if typed:
        try:
            envelope = validate_m4_v2_artifact_envelope(envelope)
        except ResearchOSValidationError as exc:
            raise AcceptedWorkloadContractError(f"{name}_invalid") from exc
    return envelope


def _ordered_envelopes(
    value: Any, *, expected: Sequence[str], name: str, typed: bool = False
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != len(expected):
        raise AcceptedWorkloadContractError(f"{name}_cardinality_invalid")
    return [
        _envelope(item, expected_digest=digest, name=name, typed=typed)
        for item, digest in zip(value, expected, strict=True)
    ]


def _registration(value: Mapping[str, Any]) -> dict[str, Any]:
    registration = _closed(
        value, REGISTRATION_RECORD_FIELDS, "accepted_support_registration_record"
    )
    for field in ("registration_digest", "task_digest", "artifact_digest"):
        _digest(registration[field], field)
    if not isinstance(registration["execution_id"], str) or not registration["execution_id"]:
        raise AcceptedWorkloadContractError("accepted_support_registration_execution_invalid")
    if not isinstance(registration["parent_digests"], list):
        raise AcceptedWorkloadContractError("accepted_support_registration_parents_invalid")
    try:
        rebuilt = MainlineArtifactRegistration(
            execution_id=registration["execution_id"],
            control_plane_key=registration["control_plane_key"],
            task_key=registration["task_key"],
            task_digest=registration["task_digest"],
            artifact_digest=registration["artifact_digest"],
            artifact_type=registration["artifact_type"],
            schema_version=registration["schema_version"],
            artifact_path=registration["artifact_path"],
            parent_digests=tuple(registration["parent_digests"]),
            git_commit=registration["git_commit"],
        )
    except (TypeError, ValueError) as exc:
        raise AcceptedWorkloadContractError(
            "accepted_support_registration_invalid"
        ) from exc
    if rebuilt.registration_digest != registration["registration_digest"]:
        raise AcceptedWorkloadContractError(
            "accepted_support_registration_digest_mismatch"
        )
    return registration


def _coordinate(event_type: str, value: Mapping[str, Any]) -> dict[str, Any]:
    coordinate = dict(value)
    fields = {
        "WORKLOAD_STARTED": ("phase",),
        "HEALTH_REPLICATE_COMMIT": ("cell_index", "replicate_index"),
        "HEALTH_AGGREGATE_COMPLETE": ("phase",),
        "HISTORICAL_FOLD_COMMIT": ("evaluation_ordinal", "issue"),
        "HISTORICAL_SENSITIVITY_SCHEME_COMMIT": ("scheme_index", "scheme_id"),
        "HISTORICAL_AGGREGATE_COMPLETE": ("phase",),
        "TERMINAL_OUTCOME": ("phase", "execution_subpath", "decision_path"),
    }[event_type]
    _closed(coordinate, fields, f"accepted_workload_{event_type.lower()}_coordinate")
    if event_type == "WORKLOAD_STARTED" and coordinate["phase"] != "HEALTH_PRE_DRAW_VALIDATION":
        raise AcceptedWorkloadContractError("accepted_workload_started_coordinate_invalid")
    if event_type == "HEALTH_AGGREGATE_COMPLETE" and coordinate["phase"] != "HEALTH_AGGREGATE":
        raise AcceptedWorkloadContractError("accepted_workload_health_aggregate_coordinate_invalid")
    if event_type == "HISTORICAL_AGGREGATE_COMPLETE" and coordinate["phase"] != "HISTORICAL_AGGREGATE":
        raise AcceptedWorkloadContractError("accepted_workload_historical_aggregate_coordinate_invalid")
    if event_type == "TERMINAL_OUTCOME" and coordinate["phase"] != "TERMINAL_OUTCOME":
        raise AcceptedWorkloadContractError("accepted_workload_terminal_coordinate_invalid")
    if event_type == "HEALTH_REPLICATE_COMMIT" and not (
        isinstance(coordinate["cell_index"], int)
        and 0 <= coordinate["cell_index"] <= 13
        and isinstance(coordinate["replicate_index"], int)
        and 0 <= coordinate["replicate_index"] <= 511
    ):
        raise AcceptedWorkloadContractError("accepted_workload_health_coordinate_invalid")
    if event_type == "HISTORICAL_FOLD_COMMIT" and not (
        isinstance(coordinate["evaluation_ordinal"], int)
        and 901 <= coordinate["evaluation_ordinal"] <= 3481
    ):
        raise AcceptedWorkloadContractError("accepted_workload_fold_coordinate_invalid")
    if event_type == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT" and not (
        isinstance(coordinate["scheme_index"], int)
        and 0 <= coordinate["scheme_index"] <= 7
        and isinstance(coordinate["scheme_id"], str)
        and coordinate["scheme_id"]
    ):
        raise AcceptedWorkloadContractError("accepted_workload_scheme_coordinate_invalid")
    return coordinate


def _validate_terminal_payload(*, branch_id: str, payload: Mapping[str, Any]) -> None:
    path = payload["execution_subpath"]
    rules: dict[str, dict[str, Any]] = {
        "EARLY_IDENTITY_VALID_HEALTH_REPAIR": {
            "decision_path": "IDENTITY_VALID_HEALTH_REPAIR", "failure_stage": "HEALTH",
            "terminal_decision": "MEASUREMENT_REPAIR_REQUIRED",
            "evaluation_status": "REPAIR_REQUIRED", "measurement_health": "REPAIR",
            "historical_evidence": "NOT_RUN", "present": {"failure"},
        },
        "STARTED_PARTIAL_HEALTH_REPAIR": {
            "decision_path": "IDENTITY_VALID_HEALTH_REPAIR", "failure_stage": "HEALTH",
            "terminal_decision": "MEASUREMENT_REPAIR_REQUIRED",
            "evaluation_status": "REPAIR_REQUIRED", "measurement_health": "REPAIR",
            "historical_evidence": "NOT_RUN", "present": {"failure"},
        },
        "COMPLETE_GRID_HEALTH_REPAIR": {
            "decision_path": "IDENTITY_VALID_HEALTH_REPAIR", "failure_stage": "HEALTH",
            "terminal_decision": "MEASUREMENT_REPAIR_REQUIRED",
            "evaluation_status": "REPAIR_REQUIRED", "measurement_health": "REPAIR",
            "historical_evidence": "NOT_RUN", "present": {"health"},
        },
        "IDENTITY_VALID_HEALTH_INVALID": {
            "decision_path": "IDENTITY_VALID_HEALTH_INVALID", "failure_stage": "HEALTH",
            "terminal_decision": "INVALID_EXECUTION", "evaluation_status": "INVALID",
            "measurement_health": "INCONCLUSIVE", "historical_evidence": "NOT_RUN",
            "present": {"failure"},
        },
        "IDENTITY_VALID_HISTORICAL_REPAIR": {
            "decision_path": "IDENTITY_VALID_HISTORICAL_REPAIR",
            "failure_stage": "HISTORICAL", "terminal_decision": "MEASUREMENT_REPAIR_REQUIRED",
            "evaluation_status": "REPAIR_REQUIRED", "measurement_health": "REPAIR",
            "historical_evidence": "INCONCLUSIVE", "present": {"health", "failure"},
        },
        "IDENTITY_VALID_HISTORICAL_INVALID": {
            "decision_path": "IDENTITY_VALID_HISTORICAL_INVALID",
            "failure_stage": "HISTORICAL", "terminal_decision": "INVALID_EXECUTION",
            "evaluation_status": "INVALID", "measurement_health": "INCONCLUSIVE",
            "historical_evidence": "INCONCLUSIVE", "present": {"health", "failure"},
        },
        "EVALUATED_COMPLETE": {
            "decision_path": "EVALUATED_COMPLETE", "failure_stage": None,
            "evaluation_status": "COMPLETE", "measurement_health": "PASS",
            "present": {"health", "historical", "candidate"}
            | ({"baseline"} if branch_id == "JOINT_RESIDUAL_INCREMENT" else set()),
        },
    }
    rule = rules.get(path)
    if rule is None:
        raise AcceptedWorkloadContractError("accepted_workload_terminal_subpath_invalid")
    for field in ("decision_path", "failure_stage", "evaluation_status", "measurement_health"):
        if payload[field] != rule[field]:
            raise AcceptedWorkloadContractError("accepted_workload_terminal_union_mismatch")
    if path == "EVALUATED_COMPLETE":
        terminal_evidence = {
            "BRANCH_INFORMATION_ACCEPTED": "POSITIVE",
            "NO_DETECTABLE_INFORMATION": "NEGATIVE",
            "INCONCLUSIVE_DUE_TO_POWER": "INCONCLUSIVE",
        }
        expected_evidence = terminal_evidence.get(payload["terminal_decision"])
        if expected_evidence is None or payload["historical_evidence"] != expected_evidence:
            raise AcceptedWorkloadContractError("accepted_workload_terminal_decision_invalid")
    elif (
        payload["terminal_decision"] != rule["terminal_decision"]
        or payload["historical_evidence"] != rule["historical_evidence"]
    ):
        raise AcceptedWorkloadContractError("accepted_workload_terminal_decision_invalid")
    if payload["scientific_decision"] != payload["terminal_decision"]:
        raise AcceptedWorkloadContractError("accepted_workload_scientific_decision_mismatch")
    body_fields = {
        "baseline": "baseline_artifact_body_or_null",
        "health": "health_artifact_body_or_null",
        "historical": "historical_artifact_body_or_null",
        "candidate": "candidate_artifact_body_or_null",
        "failure": "failure_artifact_body_or_null",
    }
    digest_fields = {
        name: f"expected_{name}_artifact_digest_or_null" for name in body_fields
    }
    for name, body_field in body_fields.items():
        body = payload[body_field]
        digest = payload[digest_fields[name]]
        if name in rule["present"]:
            if not isinstance(body, Mapping):
                raise AcceptedWorkloadContractError("accepted_workload_terminal_body_missing")
            _digest(digest, digest_fields[name])
        elif body is not None or digest is not None:
            raise AcceptedWorkloadContractError("accepted_workload_terminal_body_unexpected")
    try:
        validate_m4_v2_nested_schema("planned_counts", payload["planned_counts"])
    except ResearchOSValidationError as exc:
        raise AcceptedWorkloadContractError("accepted_workload_planned_counts_invalid") from exc
    reasons = payload["reason_codes"]
    if (
        not isinstance(reasons, list)
        or any(not isinstance(item, str) or not item for item in reasons)
        or reasons != sorted(set(reasons))
    ):
        raise AcceptedWorkloadContractError("accepted_workload_terminal_reason_codes_invalid")
    folds = payload["completed_fold_count"]
    resamples = payload["completed_resample_count"]
    if not isinstance(folds, int) or not 0 <= folds <= 2581 or not isinstance(resamples, int):
        raise AcceptedWorkloadContractError("accepted_workload_terminal_counts_invalid")
    if path == "EVALUATED_COMPLETE" and (folds, resamples) != (2581, 16000):
        raise AcceptedWorkloadContractError("accepted_workload_terminal_counts_invalid")
    if path in {"EARLY_IDENTITY_VALID_HEALTH_REPAIR", "COMPLETE_GRID_HEALTH_REPAIR", "IDENTITY_VALID_HEALTH_INVALID"} and (folds, resamples) != (0, 0):
        raise AcceptedWorkloadContractError("accepted_workload_terminal_counts_invalid")
    if path == "STARTED_PARTIAL_HEALTH_REPAIR" and (folds != 0 or resamples % 2044):
        raise AcceptedWorkloadContractError("accepted_workload_terminal_counts_invalid")
    if path.startswith("IDENTITY_VALID_HISTORICAL_") and resamples % 2000:
        raise AcceptedWorkloadContractError("accepted_workload_terminal_counts_invalid")


def _validate_event_payload(
    *, branch_id: str, event_type: str, coordinate: Mapping[str, Any], payload_schema: str,
    payload: Mapping[str, Any], payload_digest: str, input_bundle_digest: str,
    producer_execution_id: str,
) -> None:
    try:
        expected_schema = _EVENT_PAYLOAD_SCHEMAS[branch_id][event_type]
    except KeyError as exc:
        raise AcceptedWorkloadContractError("accepted_workload_event_schema_unknown") from exc
    if payload_schema != expected_schema:
        raise AcceptedWorkloadContractError("accepted_workload_event_payload_schema_invalid")
    body = dict(payload)
    if event_type == "WORKLOAD_STARTED":
        _closed(body, STARTED_PAYLOAD_FIELDS, "accepted_workload_started_payload")
        expected = {
            "input_bundle_digest": input_bundle_digest,
            "producer_task_key": producer_task_key(branch_id),
            "producer_execution_id": producer_execution_id,
            "branch_id": branch_id,
            "scientific_execution_started": True,
            "start_phase": "HEALTH_PRE_DRAW_VALIDATION",
            "rng_draw_count": 0,
            "synthetic_replicate_count": 0,
            "historical_fold_count": 0,
            "bootstrap_resample_count": 0,
        }
        if any(body.get(key) != value for key, value in expected.items()):
            raise AcceptedWorkloadContractError("accepted_workload_started_payload_invalid")
    elif event_type == "TERMINAL_OUTCOME":
        _closed(body, TERMINAL_PAYLOAD_FIELDS, "accepted_workload_terminal_payload")
        if (
            body["execution_subpath"] != coordinate["execution_subpath"]
            or body["decision_path"] != coordinate["decision_path"]
        ):
            raise AcceptedWorkloadContractError("accepted_workload_terminal_coordinate_mismatch")
        _validate_terminal_payload(branch_id=branch_id, payload=body)
    elif event_type == "HEALTH_REPLICATE_COMMIT":
        try:
            body = validate_m4_v2_nested_schema(
                "synthetic_health_replicate_evidence_commitment", body
            )
        except ResearchOSValidationError as exc:
            raise AcceptedWorkloadContractError(
                "accepted_workload_replicate_payload_invalid"
            ) from exc
        expected_replicate = m4_v2_domain_digest(
            {key: value for key, value in body.items() if key != "replicate_evidence_digest"},
            domain=_domain(branch_id, "synthetic-health.replicate-evidence.v2"),
        )
        if (
            body.get("replicate_evidence_digest") != payload_digest
            or payload_digest != expected_replicate
            or body.get("branch_id") != branch_id
        ):
            raise AcceptedWorkloadContractError("accepted_workload_replicate_digest_mismatch")
    elif event_type == "HISTORICAL_FOLD_COMMIT":
        _closed(
            body,
            (
                "evaluation_ordinal", "issue", "fold_digest",
                "prediction_checkpoint_body", "prediction_checkpoint_digest",
                "score_row_body", "score_row_digest", "fold_commit_digest",
            ),
            "accepted_workload_fold_payload",
        )
        expected_fold = m4_v2_domain_digest(
            {key: value for key, value in body.items() if key != "fold_commit_digest"},
            domain=_domain(branch_id, "accepted-workload-historical-fold-commit.v1"),
        )
        if body.get("fold_commit_digest") != payload_digest or payload_digest != expected_fold:
            raise AcceptedWorkloadContractError("accepted_workload_fold_digest_mismatch")
        if any(body.get(key) != coordinate[key] for key in ("evaluation_ordinal", "issue")):
            raise AcceptedWorkloadContractError("accepted_workload_fold_coordinate_mismatch")
    elif event_type == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT":
        try:
            body = validate_m4_v2_nested_schema("sensitivity_summary", body)
        except ResearchOSValidationError as exc:
            raise AcceptedWorkloadContractError(
                "accepted_workload_scheme_payload_invalid"
            ) from exc
        if body.get("scheme_id") != coordinate["scheme_id"]:
            raise AcceptedWorkloadContractError("accepted_workload_scheme_coordinate_mismatch")
    elif event_type in {"HEALTH_AGGREGATE_COMPLETE", "HISTORICAL_AGGREGATE_COMPLETE"}:
        artifact_type, schema_version = _AGGREGATE_IDENTITIES[branch_id][event_type]
        spec = M4_V2_ARTIFACT_TYPE_REGISTRY[artifact_type]
        _closed(body, spec.body_fields, "accepted_workload_aggregate_payload")
        if body.get("branch_id") != branch_id:
            raise AcceptedWorkloadContractError("accepted_workload_aggregate_branch_mismatch")
        expected_aggregate = m4_v2_domain_digest(
            {"artifact_type": artifact_type, "schema_version": schema_version, "body": body},
            domain=_domain(
                branch_id,
                _PAYLOAD_DIGEST_SUFFIX[event_type],
            ),
        )
        if payload_digest != expected_aggregate:
            raise AcceptedWorkloadContractError("accepted_workload_aggregate_digest_mismatch")
    if event_type not in {"HEALTH_REPLICATE_COMMIT", "HISTORICAL_FOLD_COMMIT", "HEALTH_AGGREGATE_COMPLETE", "HISTORICAL_AGGREGATE_COMPLETE"}:
        expected_payload = m4_v2_domain_digest(
            body, domain=_domain(branch_id, _PAYLOAD_DIGEST_SUFFIX[event_type])
        )
        if payload_digest != expected_payload:
            raise AcceptedWorkloadContractError("accepted_workload_payload_digest_mismatch")
    _digest(payload_digest, "payload_digest")


def validate_input_bundle(value: Mapping[str, Any], *, branch_id: str) -> dict[str, Any]:
    bundle = _closed(value, INPUT_BUNDLE_FIELDS, "accepted_workload_input_bundle")
    expected_schema = _branch_value(
        branch_id,
        "m4-v2-temporal-accepted-parent-workload-input.v2",
        "m4-v2-joint-accepted-parent-workload-input.v2",
    )
    if bundle["branch_id"] != branch_id or bundle["schema_version"] != expected_schema:
        raise AcceptedWorkloadContractError("accepted_workload_input_identity_invalid")
    for field in INPUT_BUNDLE_FIELDS:
        if field.endswith("_digest") and field != "input_bundle_digest":
            _digest(bundle[field], field)
    for field in (
        "synthetic_root_seed_full_sha256",
        "historical_root_seed_full_sha256",
    ):
        _digest(bundle[field], field)
    for field in (
        "ordered_parent_decision_artifact_digests",
        "ordered_parent_replay_artifact_digests",
        "ordered_holm_lineage_artifact_digests",
    ):
        if not isinstance(bundle[field], list):
            raise AcceptedWorkloadContractError(f"{field}_invalid")
        for item in bundle[field]:
            _digest(item, field)
    if bundle["runtime_contract"] != _RUNTIME_CONTRACT or (
        sys.implementation.name != "cpython"
        or ".".join(str(item) for item in sys.version_info[:3]) != "3.14.4"
        or np.__version__ != "2.4.6"
        or sys.byteorder != "little"
    ):
        raise AcceptedWorkloadContractError("accepted_workload_runtime_mismatch")
    resolved = _closed(
        bundle["resolved_inputs"], RESOLVED_INPUT_FIELDS, "accepted_workload_resolved_inputs"
    )
    source = _envelope(
        resolved["source_contract_envelope"],
        expected_digest=bundle["source_contract_artifact_digest"],
        name="accepted_workload_source_contract",
    )
    if source.get("source_set_digest") != bundle["source_set_digest"]:
        raise AcceptedWorkloadContractError("accepted_workload_source_set_mismatch")
    preregistration = _envelope(
        resolved["preregistration_envelope"],
        expected_digest=bundle["preregistration_artifact_digest"],
        name="accepted_workload_preregistration",
        typed=True,
    )
    if branch_id == "TEMPORAL_MARGINAL_INCREMENT":
        source_body = source.get("body", source)
        try:
            runtime = validate_numeric_runtime_contract(
                source_body.get("numeric_runtime_contract", {})
            )
        except ValueError as exc:
            raise AcceptedWorkloadContractError(
                "accepted_workload_numeric_runtime_owner_invalid"
            ) from exc
        preregistration_body = preregistration.get("body")
        if (
            not isinstance(preregistration_body, Mapping)
            or source_body.get("numeric_runtime_contract_digest")
            != NUMERIC_RUNTIME_CONTRACT_DIGEST
            or preregistration_body.get("numerical_contract_digest")
            != NUMERIC_RUNTIME_CONTRACT_DIGEST
            or runtime["worker_image_digest"] != WORKER_IMAGE_DIGEST
            or runtime["blas_lapack_binary_closure_digest"]
            != BLAS_LAPACK_BINARY_CLOSURE_DIGEST
        ):
            raise AcceptedWorkloadContractError(
                "accepted_workload_numeric_runtime_propagation_mismatch"
            )
    decisions = _ordered_envelopes(
        resolved["ordered_parent_decision_envelopes"],
        expected=bundle["ordered_parent_decision_artifact_digests"],
        name="accepted_workload_parent_decision",
        typed=True,
    )
    replays = _ordered_envelopes(
        resolved["ordered_parent_replay_envelopes"],
        expected=bundle["ordered_parent_replay_artifact_digests"],
        name="accepted_workload_parent_replay",
        typed=True,
    )
    holm = _ordered_envelopes(
        resolved["ordered_holm_lineage_envelopes"],
        expected=bundle["ordered_holm_lineage_artifact_digests"],
        name="accepted_workload_holm_lineage",
    )
    dataset = _envelope(
        resolved["dataset_snapshot_envelope"],
        expected_digest=bundle["dataset_snapshot_artifact_digest"],
        name="accepted_workload_dataset_snapshot",
    )
    dataset_body = dataset.get("body")
    if not isinstance(dataset_body, Mapping) or dataset_body.get(
        "dataset_content_digest"
    ) != bundle["dataset_content_digest"]:
        raise AcceptedWorkloadContractError("accepted_workload_dataset_content_mismatch")
    for resolved_field, digest_field in (
        ("fold_manifest_envelope", "fold_manifest_artifact_digest"),
        ("checkpoint_order_manifest_envelope", "checkpoint_order_manifest_artifact_digest"),
        ("resampling_manifest_envelope", "resampling_manifest_artifact_digest"),
        ("historical_execution_plan_envelope", "historical_execution_plan_artifact_digest"),
        ("fixture_source_envelope", "fixture_source_artifact_digest"),
    ):
        _envelope(
            resolved[resolved_field], expected_digest=bundle[digest_field],
            name=f"accepted_workload_{resolved_field}",
        )
    registration = _registration(
        resolved["accepted_support_model_registration_record"]
    )
    support = _envelope(
        resolved["accepted_support_model_envelope"],
        expected_digest=bundle["accepted_support_model_artifact_digest"],
        name="accepted_support_model",
        typed=branch_id == "JOINT_RESIDUAL_INCREMENT",
    )
    if (
        registration["artifact_digest"] != bundle["accepted_support_model_artifact_digest"]
        or registration["registration_digest"]
        != bundle["accepted_support_model_registration_digest"]
    ):
        raise AcceptedWorkloadContractError("accepted_support_model_identity_mismatch")
    if branch_id == "TEMPORAL_MARGINAL_INCREMENT":
        expected_support = {
            "artifact_type": "m4_v2_marginal_static_evaluated_model_identity",
            "schema_version": "dehps-m4-v2-marginal-static-evaluated-model-identity.v1",
            "artifact_digest": "fb7eb603f7fc283ee645a38ae1d2555d47b43fb86dbb23439a91ef329f1167d6",
            "registration_digest": "e3fc6ac295d69c4771a6f00c4f42a95902b5f5c64811d5a2fb85b12ec6234eae",
            "task_key": "m4-v2-marginal-static-historical-measurement-gate-compiler",
            "execution_id": "f55ded4805b328738b85e1143dafde436c7925ee1c76dafbb049cd600c7e7da6",
            "git_commit": "720617d3d7745dd56498eab1f344dfb140ca99ee",
        }
        if any(
            registration.get(key) != expected_support[key]
            for key in ("artifact_type", "schema_version", "artifact_digest", "registration_digest", "task_key", "execution_id", "git_commit")
        ):
            raise AcceptedWorkloadContractError("accepted_support_model_owner_mismatch")
        support_body = support.get("body")
        if not isinstance(support_body, Mapping) or any(
            support_body.get(key) != expected
            for key, expected in {
                "model_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
                "accepted_for_downstream_baseline": True,
                "production_action": "none",
            }.items()
        ):
            raise AcceptedWorkloadContractError("accepted_support_model_body_mismatch")
    else:
        last_decision = decisions[-1]["body"]
        if (
            last_decision.get("accepted_model_artifact_digest")
            != bundle["accepted_support_model_artifact_digest"]
            or registration["task_key"] != last_decision.get("producer_task_key")
            or registration["execution_id"] != last_decision.get("producer_execution_id")
        ):
            raise AcceptedWorkloadContractError("accepted_support_model_owner_mismatch")
    for decision, replay in zip(decisions, replays, strict=True):
        decision_body = decision["body"]
        replay_body = replay["body"]
        if (
            decision_body.get("accepted_for_downstream_baseline") is not True
            or replay_body.get("decision_artifact_digest") != decision["artifact_digest"]
            or replay_body.get("decision_producer_task_key")
            != decision_body.get("producer_task_key")
            or replay_body.get("decision_producer_execution_id")
            != decision_body.get("producer_execution_id")
            or replay_body.get("registered_content_verified") is not True
            or replay_body.get("source_integrity_verified") is not True
            or replay_body.get("workload_rerun") is not False
            or replay_body.get("replay_status") != "REGISTERED_REPLAY_VERIFIED"
        ):
            raise AcceptedWorkloadContractError("accepted_workload_parent_lineage_mismatch")
    if not holm:
        raise AcceptedWorkloadContractError("accepted_workload_holm_lineage_missing")
    prereg_body = preregistration["body"]
    if (
        prereg_body.get("source_contract_digest") != bundle["source_contract_artifact_digest"]
        or prereg_body.get("warmup_request_payload_digest") != bundle["warmup_request_payload_digest"]
    ):
        raise AcceptedWorkloadContractError("accepted_workload_preregistration_owner_mismatch")
    seed = resolved["seed_contract"]
    if not isinstance(seed, Mapping):
        raise AcceptedWorkloadContractError("accepted_workload_seed_contract_missing")
    seed_body = dict(seed)
    seed_digest = seed_body.pop("seed_contract_digest", None)
    seed_domain = _domain(branch_id, "seed-contract.v3")
    source_body = source.get("body", source)
    upstream_seed = seed.get("upstream_seed_and_resampling_contract", {})
    roots = upstream_seed.get("root_seeds", {}) if isinstance(upstream_seed, Mapping) else {}
    if (
        seed_digest != m4_v2_domain_digest(seed_body, domain=seed_domain)
        or prereg_body.get("seed_contract_digest") != seed_digest
        or source_body.get("seed_contract_digest") != seed_digest
        or source_body.get("seed_contract") != seed
        or roots.get("synthetic", {}).get("known_material_full_sha256")
        != bundle["synthetic_root_seed_full_sha256"]
        or roots.get("historical", {}).get("known_material_full_sha256")
        != bundle["historical_root_seed_full_sha256"]
    ):
        raise AcceptedWorkloadContractError("accepted_workload_seed_contract_mismatch")
    expected = m4_v2_domain_digest(
        {field: bundle[field] for field in INPUT_BUNDLE_FIELDS[:-1]},
        domain=_domain(branch_id, "accepted-workload-input-bundle.v2"),
    )
    if bundle["input_bundle_digest"] != expected:
        raise AcceptedWorkloadContractError("accepted_workload_input_bundle_digest_mismatch")
    return bundle


def validate_registered_computation_inputs(
    bundle: Mapping[str, Any], *, branch_id: str
) -> tuple[list[tuple[int, str]], list[str]]:
    """Dereference the frozen preregistration inputs; never accept result bytes.

    This is deliberately separate from the detached-envelope validator: the
    latter authenticates bytes, while this function proves that those bytes are
    the complete registered computation inputs and contain no injected outcome
    stream.
    """

    resolved = bundle["resolved_inputs"]
    plan_envelope = resolved["historical_execution_plan_envelope"]
    plan = plan_envelope.get("body")
    if not isinstance(plan, Mapping):
        raise AcceptedWorkloadContractError("accepted_workload_registered_plan_missing")
    plan = _closed(
        plan, REGISTERED_EXECUTION_PLAN_FIELDS,
        "accepted_workload_registered_execution_plan",
    )
    expected_links = {
        "source_contract_digest": bundle["source_contract_artifact_digest"],
        "dataset_snapshot_digest": bundle["dataset_snapshot_artifact_digest"],
        "dataset_content_digest": bundle["dataset_content_digest"],
        "fold_manifest_digest": bundle["fold_manifest_artifact_digest"],
        "checkpoint_order_manifest_digest": bundle[
            "checkpoint_order_manifest_artifact_digest"
        ],
        "resampling_manifest_digest": bundle["resampling_manifest_artifact_digest"],
        "formal_historical_execution_authorized": False,
        "automatic_evidence_from_preregistration": False,
        "formal_historical_folds_executed": 0,
        "bootstrap_children_executed": 0,
        "historical_scores_computed": 0,
        "statistical_results_read": False,
        "evidence_created": False,
        "accepted_model_artifact_digest": None,
        "promotion_gate_opened": False,
        "duplicate_validation": False,
        "production_action": "none",
    }
    if any(plan.get(field) != expected for field, expected in expected_links.items()):
        raise AcceptedWorkloadContractError("accepted_workload_registered_plan_mismatch")
    if not all(
        isinstance(plan.get(field), Mapping)
        for field in ("inference_algorithms", "time_stability", "execution")
    ):
        raise AcceptedWorkloadContractError("accepted_workload_registered_plan_invalid")

    dataset_body = resolved["dataset_snapshot_envelope"].get("body")
    history = dataset_body.get("history_snapshot") if isinstance(dataset_body, Mapping) else None
    records = history.get("records") if isinstance(history, Mapping) else None
    fold_body = resolved["fold_manifest_envelope"].get("body")
    folds = fold_body.get("folds") if isinstance(fold_body, Mapping) else None
    order_body = resolved["checkpoint_order_manifest_envelope"].get("body")
    entries = order_body.get("entries") if isinstance(order_body, Mapping) else None
    resampling_body = resolved["resampling_manifest_envelope"].get("body")
    schemes = resampling_body.get("schemes") if isinstance(resampling_body, Mapping) else None
    roots = resampling_body.get("roots") if isinstance(resampling_body, Mapping) else None
    children = resampling_body.get("children") if isinstance(resampling_body, Mapping) else None
    if not (
        isinstance(records, list) and len(records) == 3481
        and isinstance(folds, list) and len(folds) == 2581
        and isinstance(entries, list) and len(entries) == 2581
        and schemes == list(REGISTERED_HISTORICAL_SCHEME_IDS)
        and isinstance(roots, list) and len(roots) == 2000
        and isinstance(children, list) and len(children) == 16000
    ):
        raise AcceptedWorkloadContractError("accepted_workload_registered_input_grid_invalid")
    fold_coordinates: list[tuple[int, str]] = []
    for offset, (fold, order) in enumerate(zip(folds, entries, strict=True)):
        ordinal = 901 + offset
        record = records[ordinal - 1]
        if not isinstance(fold, Mapping) or not isinstance(order, Mapping) or not isinstance(record, Mapping):
            raise AcceptedWorkloadContractError("accepted_workload_registered_row_invalid")
        issue = record.get("issue")
        if (
            fold.get("fold_index") != offset
            or fold.get("test_ordinal") != ordinal
            or fold.get("test_issue") != issue
            or order.get("fold_index") != offset
            or order.get("fold_digest") != fold.get("fold_digest")
            or order.get("test_ordinal") != ordinal
            or not isinstance(issue, str)
            or not issue
        ):
            raise AcceptedWorkloadContractError(
                "accepted_workload_registered_fold_owner_mismatch"
            )
        fold_coordinates.append((ordinal, issue))
    expected_children = [
        (replicate_index, scheme_id)
        for replicate_index in range(2000)
        for scheme_id in REGISTERED_HISTORICAL_SCHEME_IDS
    ]
    observed_children = [
        (item.get("replicate_index"), item.get("scheme_id"))
        if isinstance(item, Mapping) else (None, None)
        for item in children
    ]
    if observed_children != expected_children:
        raise AcceptedWorkloadContractError(
            "accepted_workload_registered_resampling_owner_mismatch"
        )
    if resolved["fixture_source_envelope"].get("artifact_digest") != (
        "391acc6a04518389f841e94a640a14dcaf98bd2c36614d31a0e713446980b06d"
    ):
        raise AcceptedWorkloadContractError("accepted_workload_fixture_owner_mismatch")
    return fold_coordinates, list(REGISTERED_HISTORICAL_SCHEME_IDS)


def validate_event_owner_equalities(
    event: Mapping[str, Any],
    *,
    bundle: Mapping[str, Any],
    prefix: Sequence[Mapping[str, Any]],
    fold_coordinates: Sequence[tuple[int, str]],
    sensitivity_scheme_ids: Sequence[str],
) -> dict[str, Any]:
    """Bind a valid event envelope back to its unique registered owner rows."""

    branch_id = bundle["branch_id"]
    validated = validate_event(
        event,
        branch_id=branch_id,
        input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=bundle["producer_execution_id"],
    )
    kind = validated["event_type"]
    payload = validated["payload"]
    coordinate = validated["coordinate_key"]
    if (
        validated["event_index"] != len(prefix)
        or validated["previous_event_digest_or_null"]
        != (prefix[-1]["event_digest"] if prefix else None)
        or (prefix and prefix[-1].get("event_type") == "TERMINAL_OUTCOME")
    ):
        raise AcceptedWorkloadContractError(
            "accepted_workload_event_prefix_owner_mismatch"
        )
    if kind == "WORKLOAD_STARTED":
        if (
            prefix
            or payload["input_bundle_digest"] != bundle["input_bundle_digest"]
            or payload["producer_task_key"] != producer_task_key(branch_id)
            or payload["producer_execution_id"] != bundle["producer_execution_id"]
            or payload["branch_id"] != branch_id
            or payload["source_contract_digest"]
            != bundle["source_contract_artifact_digest"]
            or payload["preregistration_artifact_digest"]
            != bundle["preregistration_artifact_digest"]
            or payload["parent_decision_artifact_digests_in_order"]
            != bundle["ordered_parent_decision_artifact_digests"]
            or payload["parent_replay_artifact_digests_in_order"]
            != bundle["ordered_parent_replay_artifact_digests"]
        ):
            raise AcceptedWorkloadContractError(
                "accepted_workload_started_owner_mismatch"
            )
    elif kind == "HEALTH_REPLICATE_COMMIT":
        expected_index = validated["event_index"] - 1
        if coordinate != {
            "cell_index": expected_index // 512,
            "replicate_index": expected_index % 512,
        }:
            raise AcceptedWorkloadContractError(
                "accepted_workload_health_replicate_order_mismatch"
            )
        from .m4_v2_increment_fixture_generators import (
            build_synthetic_health_replicate_evidence,
            build_temporal_registered_sequence_coordinate,
            generate_registered_synthetic_sequence,
            score_joint_residual_sequence,
            score_temporal_increment_sequence,
        )

        generated = generate_registered_synthetic_sequence(
            branch_id=branch_id,
            root_seed_full_sha256=bundle["synthetic_root_seed_full_sha256"],
            cell_index=coordinate["cell_index"],
            replicate_index=coordinate["replicate_index"],
        )
        prereg = bundle["resolved_inputs"]["preregistration_envelope"]["body"]
        if branch_id == "TEMPORAL_MARGINAL_INCREMENT":
            sequence = build_temporal_registered_sequence_coordinate(
                sequence=generated,
                fixture_source_digest=bundle["fixture_source_artifact_digest"],
                health_contract_digest=prereg["health_contract_digest"],
                seed_contract_digest=prereg["seed_contract_digest"],
                synthetic_root_seed_full_sha256=bundle[
                    "synthetic_root_seed_full_sha256"
                ],
                replicate_index=coordinate["replicate_index"],
            )
        else:
            from .joint_residual_increment import (
                build_joint_synthetic_sequence_coordinate,
            )

            sequence = build_joint_synthetic_sequence_coordinate(
                health_contract_digest=prereg["health_contract_digest"],
                seed_contract_digest=prereg["seed_contract_digest"],
                cell_index=coordinate["cell_index"],
                replicate_index=coordinate["replicate_index"],
            )
        if (
            payload["sequence_coordinate_digest"] != sequence["coordinate_digest"]
            or payload["horizon_id"] != sequence["horizon_id"]
        ):
            raise AcceptedWorkloadContractError(
                "accepted_workload_health_replicate_owner_mismatch"
            )
        scored = (
            score_temporal_increment_sequence
            if branch_id == "TEMPORAL_MARGINAL_INCREMENT"
            else score_joint_residual_sequence
        )(
            generated.draws,
            evaluation_issue_count=generated.cell.evaluation_issue_count,
        )
        expected_payload, _ = build_synthetic_health_replicate_evidence(
            scored.score_values,
            branch_id=branch_id,
            root_seed_full_sha256=bundle["synthetic_root_seed_full_sha256"],
            cell_index=coordinate["cell_index"],
            cell_id=generated.cell.cell_id,
            fixture_id=generated.cell.fixture_id,
            horizon_id=generated.cell.horizon_id,
            replicate_index=coordinate["replicate_index"],
            sequence_coordinate_digest=sequence["coordinate_digest"],
            prediction_checkpoint_chain_digest=(
                scored.prediction_checkpoint_chain_digest
            ),
            score_row_chain_digest=scored.score_row_chain_digest,
            analytic_truth_bits_per_issue=(
                generated.cell.analytic_target_bits_per_issue
            ),
        )
        if payload != expected_payload:
            raise AcceptedWorkloadContractError(
                "accepted_workload_health_replicate_owner_mismatch"
            )
    elif kind == "HEALTH_AGGREGATE_COMPLETE":
        if any(
            item["event_type"] not in {"WORKLOAD_STARTED", "HEALTH_REPLICATE_COMMIT"}
            for item in prefix
        ):
            raise AcceptedWorkloadContractError(
                "accepted_workload_health_aggregate_phase_mismatch"
            )
        replicate_events = [
            item for item in prefix if item["event_type"] == "HEALTH_REPLICATE_COMMIT"
        ]
        if len(replicate_events) != 7168:
            raise AcceptedWorkloadContractError(
                "accepted_workload_health_aggregate_owner_count_mismatch"
            )
        summaries = payload.get("cell_summaries")
        if not isinstance(summaries, list) or len(summaries) != 14:
            raise AcceptedWorkloadContractError(
                "accepted_workload_health_aggregate_owner_mismatch"
            )
        summary_digests: list[str] = []
        failed_ids: list[str] = []
        from .m4_v2_increment_fixture_generators import (
            build_synthetic_health_cell_summary,
            synthetic_cells,
        )

        cells = synthetic_cells(branch_id)
        for cell_index, summary in enumerate(summaries):
            owned = replicate_events[cell_index * 512:(cell_index + 1) * 512]
            expected_summary_body = build_synthetic_health_cell_summary(
                [item["payload"] for item in owned],
                branch_id=branch_id,
                cell=cells[cell_index],
            )
            expected_coordinate_chain = m4_v2_domain_digest(
                {
                    "branch_id": branch_id,
                    "cell_index": cell_index,
                    "cell_id": summary.get("cell_id"),
                    "ordered_replicate_evidence_digests": [
                        item["payload"]["replicate_evidence_digest"] for item in owned
                    ],
                },
                domain=_domain(
                    branch_id, "synthetic-health.cell-coordinate-chain.v2"
                ),
            )
            expected_summary = m4_v2_domain_digest(
                {
                    field: summary[field]
                    for field in summary
                    if field != "cell_summary_digest"
                },
                domain=_domain(branch_id, "health-cell-summary.v2"),
            )
            if (
                summary.get("cell_index") != cell_index
                or summary.get("replicate_count") != 512
                or summary.get("coordinate_chain_digest") != expected_coordinate_chain
                or summary.get("cell_summary_digest") != expected_summary
                or summary != expected_summary_body
            ):
                raise AcceptedWorkloadContractError(
                    "accepted_workload_health_aggregate_owner_mismatch"
                )
            summary_digests.append(expected_summary)
            if summary.get("threshold_pass") is False:
                failed_ids.append(summary["cell_id"])
        expected_chain = m4_v2_domain_digest(
            {"ordered_cell_summary_digests": summary_digests},
            domain=_domain(branch_id, "health-cell-summary-chain.v2"),
        )
        prereg = bundle["resolved_inputs"]["preregistration_envelope"]["body"]
        expected_health = {
            "status": "COMPLETE",
            "measurement_contract_key": prereg["measurement_contract_key"],
            "measurement_contract_digest": prereg["measurement_contract_digest"],
            "branch_id": branch_id,
            "estimand_digest": prereg["estimand_digest"],
            "decision_path": (
                "IDENTITY_VALID_HEALTH_REPAIR"
                if failed_ids
                else "EVALUATED_COMPLETE"
            ),
            "source_contract_digest": bundle["source_contract_artifact_digest"],
            "preregistration_artifact_digest": bundle[
                "preregistration_artifact_digest"
            ],
            "marginal_decision_digest": bundle[
                "ordered_parent_decision_artifact_digests"
            ][0],
            "marginal_replay_digest": bundle[
                "ordered_parent_replay_artifact_digests"
            ][0],
            "transition_local_warmup_rule_digest": prereg[
                "transition_local_warmup_rule_digest"
            ],
            "synthetic_warmup_application_or_null": None,
            "synthetic_warmup_application_digest_or_null": None,
            "warmup_alias_position_count": (
                0 if branch_id == "TEMPORAL_MARGINAL_INCREMENT" else 6_444_032
            ),
            "cell_summaries": summaries,
            "cell_summary_chain_digest": expected_chain,
            "measurement_health": "REPAIR" if failed_ids else "PASS",
            "failed_cell_ids": failed_ids,
            "synthetic_replicate_count": 7168,
            "synthetic_generated_issue_count": 15_920_128,
            "outer_evaluation_issue_count": 9_468_928,
            "bootstrap_resample_count": 14_651_392,
            "historical_started": False,
            "repair_required": bool(failed_ids),
            "production_action": "none",
        }
        if branch_id == "JOINT_RESIDUAL_INCREMENT":
            expected_health.update(
                {
                    "temporal_decision_digest": bundle[
                        "ordered_parent_decision_artifact_digests"
                    ][1],
                    "temporal_replay_digest": bundle[
                        "ordered_parent_replay_artifact_digests"
                    ][1],
                }
            )
        if payload != expected_health:
            raise AcceptedWorkloadContractError(
                "accepted_workload_health_aggregate_owner_mismatch"
            )
    elif kind == "HISTORICAL_FOLD_COMMIT":
        offset = coordinate["evaluation_ordinal"] - 901
        committed_offset = validated["event_index"] - 7170
        if not 0 <= offset < len(fold_coordinates) or fold_coordinates[offset] != (
            coordinate["evaluation_ordinal"], coordinate["issue"]
        ) or committed_offset != offset:
            raise AcceptedWorkloadContractError(
                "accepted_workload_fold_registered_row_mismatch"
            )
        resolved = bundle["resolved_inputs"]
        fold = resolved["fold_manifest_envelope"]["body"]["folds"][offset]
        order = resolved["checkpoint_order_manifest_envelope"]["body"]["entries"][
            offset
        ]
        registered_row = resolved["dataset_snapshot_envelope"]["body"][
            "history_snapshot"
        ]["records"][coordinate["evaluation_ordinal"] - 1]
        score = validate_m4_v2_nested_schema("historical_score_row", payload["score_row_body"])
        score_domain = _domain(branch_id, "historical-score-row.v2")
        expected_score = m4_v2_domain_digest(
            {field: score[field] for field in score if field != "score_row_digest"},
            domain=score_domain,
        )
        checkpoint = payload["prediction_checkpoint_body"]
        if branch_id == "TEMPORAL_MARGINAL_INCREMENT":
            from .temporal_marginal_increment import (
                validate_accepted_temporal_evaluation_row,
            )

            checkpoint = validate_accepted_temporal_evaluation_row(checkpoint)
            checkpoint_digest = checkpoint["q_t_row_digest"]
            checkpoint_ordinal = checkpoint["transition_ordinal"]
        else:
            from .joint_residual_increment import (
                validate_joint_target_prediction_checkpoint,
            )

            checkpoint = validate_joint_target_prediction_checkpoint(checkpoint)
            checkpoint_digest = checkpoint["checkpoint_digest"]
            checkpoint_ordinal = checkpoint["target_ordinal"]
        if (
            payload["fold_digest"] != fold["fold_digest"]
            or checkpoint_digest != payload["prediction_checkpoint_digest"]
            or checkpoint_ordinal != coordinate["evaluation_ordinal"]
            or checkpoint["issue"] != coordinate["issue"]
            or score["evaluation_ordinal"] != coordinate["evaluation_ordinal"]
            or score["issue"] != coordinate["issue"]
            or score["prediction_checkpoint_digest"] != checkpoint_digest
            or fold.get("test_ordinal") != coordinate["evaluation_ordinal"]
            or fold.get("test_issue") != coordinate["issue"]
            or order.get("test_ordinal") != coordinate["evaluation_ordinal"]
            or order.get("fold_index") != offset
            or order.get("fold_digest") != fold.get("fold_digest")
            or registered_row.get("issue") != coordinate["issue"]
            or score["settled_outcome_digest"]
            != historical_settled_outcome_digest(
                evaluation_ordinal=coordinate["evaluation_ordinal"],
                issue=coordinate["issue"],
                red_numbers=registered_row.get("red_numbers", ()),
            )
            or score["score_row_digest"] != payload["score_row_digest"]
            or score["score_row_digest"] != expected_score
        ):
            raise AcceptedWorkloadContractError(
                "accepted_workload_historical_fold_owner_mismatch"
            )
    elif kind == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT":
        scheme_index = coordinate["scheme_index"]
        committed_scheme_count = validated["event_index"] - 9751
        if (
            scheme_index >= len(sensitivity_scheme_ids)
            or committed_scheme_count != scheme_index
            or coordinate["scheme_id"] != sensitivity_scheme_ids[scheme_index]
            or payload["scheme_id"] != coordinate["scheme_id"]
            or payload["resample_count"] != 2000
        ):
            raise AcceptedWorkloadContractError(
                "accepted_workload_sensitivity_owner_mismatch"
            )
        from .m4_v2_increment_fixture_generators import (
            build_historical_sensitivity_summary,
        )

        fold_scores = [
            float.fromhex(item["payload"]["score_row_body"]["paired_score_float_hex"])
            for item in prefix
            if item["event_type"] == "HISTORICAL_FOLD_COMMIT"
        ]
        if len(fold_scores) != 2581:
            raise AcceptedWorkloadContractError(
                "accepted_workload_sensitivity_fold_owner_mismatch"
            )
        expected_summary, _ = build_historical_sensitivity_summary(
            fold_scores,
            branch_id=branch_id,
            root_seed_full_sha256=bundle["historical_root_seed_full_sha256"],
            scheme_index=scheme_index,
            scheme_id=coordinate["scheme_id"],
        )
        if payload != expected_summary:
            raise AcceptedWorkloadContractError(
                "accepted_workload_sensitivity_owner_mismatch"
            )
    elif kind == "HISTORICAL_AGGREGATE_COMPLETE":
        from .m4_v2_increment_fixture_generators import neumaier_mean

        folds = [item for item in prefix if item["event_type"] == "HISTORICAL_FOLD_COMMIT"]
        schemes = [
            item for item in prefix
            if item["event_type"] == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT"
        ]
        checkpoint_chain = m4_v2_domain_digest(
            {
                "ordered_checkpoint_digests": [
                    item["payload"]["prediction_checkpoint_digest"] for item in folds
                ]
            },
            domain=_domain(branch_id, "historical-checkpoint-chain.v2"),
        )
        score_chain = m4_v2_domain_digest(
            {
                "ordered_score_row_digests": [
                    item["payload"]["score_row_digest"] for item in folds
                ]
            },
            domain=_domain(branch_id, "historical-score-sequence.v2"),
        )
        if (
            len(folds) != 2581
            or len(schemes) != 8
            or payload.get("score_count") != 2581
            or payload.get("checkpoint_chain_digest") != checkpoint_chain
            or payload.get("score_sequence_digest") != score_chain
            or payload.get("sensitivity_summaries")
            != [item["payload"] for item in schemes]
            or payload.get("historical_child_count") != 16000
            or payload.get("observed_mean_bits_per_issue")
            != neumaier_mean(
                [
                    float.fromhex(
                        item["payload"]["score_row_body"][
                            "paired_score_float_hex"
                        ]
                    )
                    for item in folds
                ]
            )
        ):
            raise AcceptedWorkloadContractError(
                "accepted_workload_historical_aggregate_owner_mismatch"
            )
    elif kind == "TERMINAL_OUTCOME":
        fold_count = sum(
            item["event_type"] == "HISTORICAL_FOLD_COMMIT" for item in prefix
        )
        scheme_count = sum(
            item["event_type"] == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT"
            for item in prefix
        )
        expected_preterminal = preterminal_transcript_digest(
            branch_id=branch_id,
            input_bundle_digest=bundle["input_bundle_digest"],
            producer_execution_id=bundle["producer_execution_id"],
            execution_subpath=payload["execution_subpath"],
            decision_path=payload["decision_path"],
            ordered_preterminal_event_digests=[
                item["event_digest"] for item in prefix
            ],
        )
        prereg = bundle["resolved_inputs"]["preregistration_envelope"]["body"]
        path = payload["execution_subpath"]
        if path == "STARTED_PARTIAL_HEALTH_REPAIR":
            expected_resample_count = 2044 * sum(
                item["event_type"] == "HEALTH_REPLICATE_COMMIT"
                for item in prefix
            )
        elif path.startswith("IDENTITY_VALID_HISTORICAL_"):
            expected_resample_count = scheme_count * 2000
        elif path == "EVALUATED_COMPLETE":
            expected_resample_count = 16000
        else:
            expected_resample_count = 0
        if (
            payload["preterminal_transcript_digest"] != expected_preterminal
            or payload["completed_fold_count"] != fold_count
            or payload["completed_resample_count"] != expected_resample_count
            or payload["planned_counts"] != prereg["planned_counts"]
        ):
            raise AcceptedWorkloadContractError(
                "accepted_workload_terminal_prefix_owner_mismatch"
            )
        if payload["execution_subpath"] == "COMPLETE_GRID_HEALTH_REPAIR":
            health_events = [
                item
                for item in prefix
                if item["event_type"] == "HEALTH_AGGREGATE_COMPLETE"
            ]
            if len(health_events) != 1:
                raise AcceptedWorkloadContractError(
                    "accepted_workload_health_terminal_owner_mismatch"
                )
        if payload["failure_artifact_body_or_null"] is not None:
            failure_body = payload["failure_artifact_body_or_null"]
            expected_failure_fields = {
                "status": (
                    "COMPLETE"
                    if path == "EARLY_IDENTITY_VALID_HEALTH_REPAIR"
                    else "FAILED"
                ),
                "decision_path": payload["decision_path"],
                "failure_stage": payload["failure_stage"],
                "repairable": path in {
                    "EARLY_IDENTITY_VALID_HEALTH_REPAIR",
                    "STARTED_PARTIAL_HEALTH_REPAIR",
                    "IDENTITY_VALID_HISTORICAL_REPAIR",
                },
                "scientific_execution_started": True,
                "historical_started": path.startswith(
                    "IDENTITY_VALID_HISTORICAL_"
                ),
                "partial_evidence_created": False,
                "completed_fold_count": payload["completed_fold_count"],
                "completed_resample_count": payload["completed_resample_count"],
                "source_contract_digest": bundle[
                    "source_contract_artifact_digest"
                ],
                "preregistration_artifact_digest": bundle[
                    "preregistration_artifact_digest"
                ],
            }
            if any(
                failure_body.get(name) != expected
                for name, expected in expected_failure_fields.items()
            ):
                raise AcceptedWorkloadContractError(
                    "accepted_workload_failure_terminal_owner_mismatch"
                )
            if (
                payload["reason_codes"] != [failure_body.get("failure_code")]
            ):
                raise AcceptedWorkloadContractError(
                    "accepted_workload_failure_reason_owner_mismatch"
                )
            if path == "EARLY_IDENTITY_VALID_HEALTH_REPAIR":
                expected_codes: list[str] = []
                issues: set[str] = set()
                records = bundle["resolved_inputs"][
                    "dataset_snapshot_envelope"
                ]["body"]["history_snapshot"]["records"]
                for record in records:
                    issue = record.get("issue")
                    draw = record.get("red_numbers")
                    if not isinstance(issue, str) or issue in issues:
                        expected_codes.append(
                            "REGISTERED_DATASET_ISSUE_IDENTITY_INVALID"
                        )
                        break
                    issues.add(issue)
                    if (
                        not isinstance(draw, list)
                        or len(draw) != 6
                        or any(
                            type(value) is not int or not 1 <= value <= 33
                            for value in draw
                        )
                        or draw != sorted(set(draw))
                    ):
                        expected_codes.append(
                            "REGISTERED_DATASET_LEGAL_STATE_INVALID"
                        )
                        break
                if payload["reason_codes"] != expected_codes:
                    raise AcceptedWorkloadContractError(
                        "accepted_workload_early_failure_dataset_owner_mismatch"
                    )
            expected_message = event_payload_digest(
                branch_id=branch_id, event_type="WORKLOAD_STARTED",
                payload={
                    "structured_diagnostic_codes_in_order": payload[
                        "reason_codes"
                    ]
                },
            )
            if failure_body.get("message_digest") != expected_message:
                raise AcceptedWorkloadContractError(
                    "accepted_workload_failure_message_owner_mismatch"
                )
            if branch_id == "TEMPORAL_MARGINAL_INCREMENT":
                failure_type = (
                    "M4V2TemporalMarginalIncrementScientificFailureArtifact"
                )
                failure_schema = (
                    "dehps-m4-v2-temporal-marginal-increment-"
                    "scientific-failure.v3"
                )
            else:
                failure_type = "M4V2JointResidualScientificFailureArtifact"
                failure_schema = (
                    "dehps-m4-v2-joint-residual-scientific-failure.v3"
                )
            failure_parents = [
                bundle["source_contract_artifact_digest"],
                bundle["preregistration_artifact_digest"],
            ]
            if path.startswith("IDENTITY_VALID_HISTORICAL_"):
                health_body = payload["health_artifact_body_or_null"]
                prefix_health = [
                    item["payload"] for item in prefix
                    if item["event_type"] == "HEALTH_AGGREGATE_COMPLETE"
                ]
                if not isinstance(health_body, Mapping):
                    raise AcceptedWorkloadContractError(
                        "accepted_workload_historical_failure_health_missing"
                    )
                if len(prefix_health) != 1 or health_body != prefix_health[0]:
                    raise AcceptedWorkloadContractError(
                        "accepted_workload_historical_failure_health_owner_mismatch"
                    )
                health_type = (
                    "M4V2TemporalMarginalIncrementHealthAggregateArtifact"
                    if branch_id == "TEMPORAL_MARGINAL_INCREMENT"
                    else "M4V2JointResidualMeasurementHealthArtifact"
                )
                health_parents = [
                    bundle["source_contract_artifact_digest"],
                    bundle["preregistration_artifact_digest"],
                    *[
                        digest
                        for pair in zip(
                            bundle["ordered_parent_decision_artifact_digests"],
                            bundle["ordered_parent_replay_artifact_digests"],
                            strict=True,
                        )
                        for digest in pair
                    ],
                ]
                health = m4_v2_build_artifact_envelope(
                    artifact_type=health_type, body=health_body,
                    parent_digests=health_parents,
                )
                if (
                    payload["expected_health_artifact_digest_or_null"]
                    != health["artifact_digest"]
                ):
                    raise AcceptedWorkloadContractError(
                        "accepted_workload_historical_failure_health_owner_mismatch"
                    )
                failure_parents.append(health["artifact_digest"])
            try:
                failure = validate_m4_v2_artifact_envelope(
                    m4_v2_build_artifact_envelope(
                        artifact_type=failure_type,
                        schema_version=failure_schema,
                        body=failure_body,
                        parent_digests=failure_parents,
                    ),
                    expected_artifact_type=failure_type,
                )
            except ResearchOSValidationError as exc:
                raise AcceptedWorkloadContractError(
                    "accepted_workload_failure_terminal_schema_invalid"
                ) from exc
            if (
                payload["expected_failure_artifact_digest_or_null"]
                != failure["artifact_digest"]
            ):
                raise AcceptedWorkloadContractError(
                    "accepted_workload_failure_terminal_digest_mismatch"
                )
        if path == "EVALUATED_COMPLETE":
            prefix_health = [
                item["payload"] for item in prefix
                if item["event_type"] == "HEALTH_AGGREGATE_COMPLETE"
            ]
            prefix_historical = [
                item["payload"] for item in prefix
                if item["event_type"] == "HISTORICAL_AGGREGATE_COMPLETE"
            ]
            if (
                len(prefix_health) != 1
                or len(prefix_historical) != 1
                or payload["health_artifact_body_or_null"] != prefix_health[0]
                or payload["historical_artifact_body_or_null"]
                != prefix_historical[0]
                or payload["reason_codes"] != []
            ):
                raise AcceptedWorkloadContractError(
                    "accepted_workload_evaluated_terminal_prefix_mismatch"
                )
            health_type = (
                "M4V2TemporalMarginalIncrementHealthAggregateArtifact"
                if branch_id == "TEMPORAL_MARGINAL_INCREMENT"
                else "M4V2JointResidualMeasurementHealthArtifact"
            )
            health_parents = [
                bundle["source_contract_artifact_digest"],
                bundle["preregistration_artifact_digest"],
                *[
                    digest
                    for pair in zip(
                        bundle["ordered_parent_decision_artifact_digests"],
                        bundle["ordered_parent_replay_artifact_digests"],
                        strict=True,
                    )
                    for digest in pair
                ],
            ]
            if branch_id == "TEMPORAL_MARGINAL_INCREMENT":
                health = validate_m4_v2_artifact_envelope(
                    m4_v2_build_artifact_envelope(
                        artifact_type=health_type, body=prefix_health[0],
                        parent_digests=health_parents,
                    ), expected_artifact_type=health_type,
                )
                historical_type = (
                    "M4V2TemporalMarginalIncrementHistoricalAggregateArtifact"
                )
                historical_parents = [
                    bundle["source_contract_artifact_digest"],
                    bundle["preregistration_artifact_digest"],
                    health["artifact_digest"],
                    prefix_historical[0]["marginal_raw_p_artifact_digest"],
                ]
                candidate_type = (
                    "M4V2TemporalMarginalIncrementCandidateModelArtifact"
                )
                candidate_schema = (
                    "dehps-m4-v2-temporal-marginal-increment-"
                    "candidate-model.v3"
                )
            else:
                baseline_body = payload["baseline_artifact_body_or_null"]
                if not isinstance(baseline_body, Mapping):
                    raise AcceptedWorkloadContractError(
                        "accepted_workload_evaluated_baseline_missing"
                    )
                baseline_type = "M4V2JointResidualMaximumEntropyBaselineArtifact"
                candidate_body = payload["candidate_artifact_body_or_null"]
                if not isinstance(candidate_body, Mapping):
                    raise AcceptedWorkloadContractError(
                        "accepted_workload_evaluated_candidate_missing"
                    )
                prereg = bundle["resolved_inputs"][
                    "preregistration_envelope"
                ]["body"]
                expected_baseline_fields = {
                    "status": "COMPLETE",
                    "measurement_contract_key": prereg[
                        "measurement_contract_key"
                    ],
                    "measurement_contract_digest": prereg[
                        "measurement_contract_digest"
                    ],
                    "branch_id": branch_id,
                    "estimand_digest": prereg["estimand_digest"],
                    "baseline_id": (
                        "MAXIMUM_ENTROPY_LEGAL_DISTRIBUTION_MATCHING_"
                        "ACCEPTED_TEMPORAL_MARGINALS"
                    ),
                    "source_contract_digest": bundle[
                        "source_contract_artifact_digest"
                    ],
                    "dataset_content_digest": bundle["dataset_content_digest"],
                    "fold_manifest_digest": bundle[
                        "fold_manifest_artifact_digest"
                    ],
                    "temporal_parent_candidate_artifact_digest": bundle[
                        "accepted_support_model_artifact_digest"
                    ],
                    "temporal_composite_view_digest": bundle[
                        "resolved_inputs"
                    ]["accepted_support_model_envelope"]["body"][
                        "composite_view_digest"
                    ],
                    "q_base_checkpoint_index_digest": candidate_body[
                        "q_base_checkpoint_index_digest"
                    ],
                    "same_distribution_as_temporal_parent": True,
                    "distinct_artifact_from_temporal_parent": True,
                    "historical_support_count": 3480,
                    "historical_fold_count": 2581,
                    "production_action": "none",
                }
                if any(
                    baseline_body.get(name) != expected
                    for name, expected in expected_baseline_fields.items()
                ):
                    raise AcceptedWorkloadContractError(
                        "accepted_workload_evaluated_baseline_owner_mismatch"
                    )
                if (
                    baseline_body["q_base_checkpoint_index_digest"]
                    != prefix_historical[0]["q_base_checkpoint_index_digest"]
                ):
                    raise AcceptedWorkloadContractError(
                        "accepted_workload_evaluated_q_base_owner_mismatch"
                    )
                baseline = validate_m4_v2_artifact_envelope(
                    m4_v2_build_artifact_envelope(
                        artifact_type=baseline_type, body=baseline_body,
                        parent_digests=(
                            bundle["source_contract_artifact_digest"],
                            bundle["preregistration_artifact_digest"],
                            bundle["accepted_support_model_artifact_digest"],
                        ),
                    ), expected_artifact_type=baseline_type,
                )
                if (
                    payload["expected_baseline_artifact_digest_or_null"]
                    != baseline["artifact_digest"]
                ):
                    raise AcceptedWorkloadContractError(
                        "accepted_workload_evaluated_baseline_owner_mismatch"
                    )
                health = validate_m4_v2_artifact_envelope(
                    m4_v2_build_artifact_envelope(
                        artifact_type=health_type, body=prefix_health[0],
                        parent_digests=(*health_parents, baseline["artifact_digest"]),
                    ), expected_artifact_type=health_type,
                )
                historical_type = "M4V2JointResidualHistoricalExecutionArtifact"
                historical_parents = [
                    bundle["source_contract_artifact_digest"],
                    bundle["preregistration_artifact_digest"],
                    baseline["artifact_digest"], health["artifact_digest"],
                    prefix_historical[0]["marginal_raw_p_artifact_digest"],
                    prefix_historical[0]["temporal_raw_p_artifact_digest"],
                ]
                candidate_type = "M4V2JointResidualCandidateModelArtifact"
                candidate_schema = None
            historical = validate_m4_v2_artifact_envelope(
                m4_v2_build_artifact_envelope(
                    artifact_type=historical_type, body=prefix_historical[0],
                    parent_digests=historical_parents,
                ), expected_artifact_type=historical_type,
            )
            candidate_body = payload["candidate_artifact_body_or_null"]
            if not isinstance(candidate_body, Mapping):
                raise AcceptedWorkloadContractError(
                    "accepted_workload_evaluated_candidate_missing"
                )
            candidate_fixed = {
                "status": "COMPLETE",
                "measurement_contract_key": prereg["measurement_contract_key"],
                "measurement_contract_digest": prereg[
                    "measurement_contract_digest"
                ],
                "branch_id": branch_id,
                "estimand_digest": prereg["estimand_digest"],
                "source_contract_digest": bundle[
                    "source_contract_artifact_digest"
                ],
                "dataset_content_digest": bundle["dataset_content_digest"],
                "fold_manifest_digest": bundle[
                    "fold_manifest_artifact_digest"
                ],
                "historical_fold_count": 2581,
                "production_action": "none",
            }
            if branch_id == "TEMPORAL_MARGINAL_INCREMENT":
                capsule_index = validate_sealed_probability_capsule_index(
                    candidate_body["probability_capsule_index"]
                )
                if (
                    capsule_index["producer_source_contract_digest"]
                    != bundle["source_contract_artifact_digest"]
                ):
                    raise AcceptedWorkloadContractError(
                        "accepted_workload_probability_capsule_source_owner_mismatch"
                    )
                candidate_fixed.update(
                    {
                        "model_id": (
                            "EXPANDING_LEGAL_ONE_LAG_OVERLAP_TILT_MLE_V1"
                        ),
                        "marginal_parent_model_artifact_digest": bundle[
                            "accepted_support_model_artifact_digest"
                        ],
                        "marginal_parent_probability_chain_digest": bundle[
                            "accepted_support_model_artifact_digest"
                        ],
                        "support_model_id": (
                            "TRANSITION_LOCAL_TEMPORAL_PARENT_ALIAS_"
                            "THETA_ZERO_S2_900_V1"
                        ),
                        "warmup_index_digest": prefix_historical[0][
                            "warmup_index_digest"
                        ],
                        "accepted_temporal_evaluation_index_digest": (
                            prefix_historical[0][
                                "accepted_temporal_evaluation_index_digest"
                            ]
                        ),
                        "composite_view_digest": prefix_historical[0][
                            "composite_view_digest"
                        ],
                        "probability_capsule_index_digest": capsule_index[
                            "index_digest"
                        ],
                        "probability_capsule_evaluator_contract_digest": (
                            capsule_index["evaluator_contract_digest"]
                        ),
                    }
                )
            else:
                joint_estimator = (
                    "EXPANDING_MARGINAL_ORTHOGONAL_IS4_RESIDUAL_TILT_MLE_"
                    "WITH_FIXED_NULL_TEMPORAL_WARMUP_V2"
                )
                candidate_fixed.update(
                    {
                        "model_id": joint_estimator,
                        "joint_estimator_id": joint_estimator,
                        "joint_baseline_artifact_digest": baseline[
                            "artifact_digest"
                        ],
                        "temporal_parent_candidate_artifact_digest": bundle[
                            "accepted_support_model_artifact_digest"
                        ],
                        "temporal_composite_view_digest": prefix_historical[0][
                            "temporal_composite_view_digest"
                        ],
                        "q_base_checkpoint_index_digest": prefix_historical[0][
                            "q_base_checkpoint_index_digest"
                        ],
                        "joint_z_checkpoint_index_digest": prefix_historical[0][
                            "joint_z_checkpoint_index_digest"
                        ],
                        "joint_target_prediction_index_digest": (
                            prefix_historical[0][
                                "joint_target_prediction_index_digest"
                            ]
                        ),
                        "fitted_parameter_chain_digest": prefix_historical[0][
                            "joint_eta_checkpoint_chain_digest"
                        ],
                        "orthogonality_certificate_chain_digest": (
                            m4_v2_domain_digest(
                                {
                                    "ordered_certificate_digests": [
                                        row[
                                            "orthogonality_certificate_digest"
                                        ]
                                        for row in candidate_body[
                                            "joint_z_checkpoint_index"
                                        ]["rows"]
                                    ]
                                },
                                domain=(
                                    "dehps.m4.v2.joint-residual."
                                    "orthogonality-certificate-chain.v2"
                                ),
                            )
                        ),
                        "marginal_preservation_certificate_chain_digest": (
                            m4_v2_domain_digest(
                                {
                                    "ordered_certificate_digests": [
                                        row[
                                            "marginal_preservation_certificate_digest"
                                        ]
                                        for row in candidate_body[
                                            "joint_z_checkpoint_index"
                                        ]["rows"]
                                    ]
                                },
                                domain=(
                                    "dehps.m4.v2.joint-residual."
                                    "marginal-preservation-certificate-chain.v2"
                                ),
                            )
                        ),
                    }
                )
            if any(
                candidate_body.get(name) != expected
                for name, expected in candidate_fixed.items()
            ):
                raise AcceptedWorkloadContractError(
                    "accepted_workload_evaluated_candidate_owner_mismatch"
                )
            candidate_parents = (
                [
                    bundle["source_contract_artifact_digest"],
                    historical["artifact_digest"],
                    candidate_body["marginal_parent_model_artifact_digest"],
                    candidate_body["marginal_parent_probability_chain_digest"],
                ]
                if branch_id == "TEMPORAL_MARGINAL_INCREMENT"
                else [
                    bundle["source_contract_artifact_digest"],
                    historical["artifact_digest"], baseline["artifact_digest"],
                    bundle["accepted_support_model_artifact_digest"],
                ]
            )
            candidate = validate_m4_v2_artifact_envelope(
                m4_v2_build_artifact_envelope(
                    artifact_type=candidate_type,
                    schema_version=candidate_schema,
                    body=candidate_body, parent_digests=candidate_parents,
                ), expected_artifact_type=candidate_type,
            )
            if (
                payload["expected_health_artifact_digest_or_null"]
                != health["artifact_digest"]
                or payload["expected_historical_artifact_digest_or_null"]
                != historical["artifact_digest"]
                or payload["expected_candidate_artifact_digest_or_null"]
                != candidate["artifact_digest"]
            ):
                raise AcceptedWorkloadContractError(
                    "accepted_workload_evaluated_terminal_digest_mismatch"
                )
            adjusted = float(prefix_historical[0]["holm_adjusted_p_value"])
            interval = prefix_historical[0][
                "simultaneous_effect_interval_bits_per_issue"
            ]
            positive = (
                adjusted <= 0.05
                and float.fromhex(interval["lower_float_hex"]) > 0.01
                and prefix_historical[0]["positive_stability_pass"] is True
            )
            negative = (
                not positive and adjusted > 0.05
                and prefix_historical[0]["equivalence_power_sufficient"] is True
                and float(prefix_historical[0][
                    "equivalence_upper_bound_bits_per_issue"
                ]) <= 0.01
                and 0.0 <= float(prefix_historical[0]["mde_bits_per_issue"]) <= 0.01
            )
            expected_decision = (
                "BRANCH_INFORMATION_ACCEPTED" if positive
                else "NO_DETECTABLE_INFORMATION" if negative
                else "INCONCLUSIVE_DUE_TO_POWER"
            )
            if payload["terminal_decision"] != expected_decision:
                raise AcceptedWorkloadContractError(
                    "accepted_workload_evaluated_decision_owner_mismatch"
                )
        if path == "COMPLETE_GRID_HEALTH_REPAIR":
            health_body = health_events[0]["payload"]
            if branch_id == "TEMPORAL_MARGINAL_INCREMENT":
                artifact_type = (
                    "M4V2TemporalMarginalIncrementHealthAggregateArtifact"
                )
                parents = (
                    bundle["source_contract_artifact_digest"],
                    bundle["preregistration_artifact_digest"],
                    bundle["ordered_parent_decision_artifact_digests"][0],
                    bundle["ordered_parent_replay_artifact_digests"][0],
                )
                reasons = list(health_body["failed_cell_ids"])
            else:
                artifact_type = "M4V2JointResidualMeasurementHealthArtifact"
                parents = (
                    bundle["source_contract_artifact_digest"],
                    bundle["preregistration_artifact_digest"],
                    *[
                        digest
                        for pair in zip(
                            bundle["ordered_parent_decision_artifact_digests"],
                            bundle["ordered_parent_replay_artifact_digests"],
                            strict=True,
                        )
                        for digest in pair
                    ],
                )
                reasons = sorted(
                    f"HEALTH_CELL_FAILED:{cell_id}"
                    for cell_id in health_body["failed_cell_ids"]
                )
            health = m4_v2_build_artifact_envelope(
                artifact_type=artifact_type,
                body=health_body,
                parent_digests=parents,
            )
            expected_terminal = {
                "execution_subpath": "COMPLETE_GRID_HEALTH_REPAIR",
                "decision_path": "IDENTITY_VALID_HEALTH_REPAIR",
                "failure_stage": "HEALTH",
                "terminal_decision": "MEASUREMENT_REPAIR_REQUIRED",
                "scientific_decision": "MEASUREMENT_REPAIR_REQUIRED",
                "evaluation_status": "REPAIR_REQUIRED",
                "measurement_health": "REPAIR",
                "historical_evidence": "NOT_RUN",
                "baseline_artifact_body_or_null": None,
                "health_artifact_body_or_null": health_body,
                "historical_artifact_body_or_null": None,
                "candidate_artifact_body_or_null": None,
                "failure_artifact_body_or_null": None,
                "expected_baseline_artifact_digest_or_null": None,
                "expected_health_artifact_digest_or_null": health[
                    "artifact_digest"
                ],
                "expected_historical_artifact_digest_or_null": None,
                "expected_candidate_artifact_digest_or_null": None,
                "expected_failure_artifact_digest_or_null": None,
                "completed_fold_count": 0,
                "completed_resample_count": 0,
                "reason_codes": reasons,
                "planned_counts": prereg["planned_counts"],
                "preterminal_transcript_digest": expected_preterminal,
            }
            if payload != expected_terminal:
                raise AcceptedWorkloadContractError(
                    "accepted_workload_health_terminal_owner_mismatch"
                )
    return validated


def build_event(
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
    event_index: int,
    event_type: str,
    coordinate_key: Mapping[str, Any],
    payload_schema: str,
    payload: Mapping[str, Any],
    payload_digest: str,
    previous_event_digest_or_null: str | None,
) -> dict[str, Any]:
    if event_type not in EVENT_TYPES or not isinstance(event_index, int) or event_index < 0:
        raise AcceptedWorkloadContractError("accepted_workload_event_identity_invalid")
    if (event_index == 0) != (previous_event_digest_or_null is None):
        raise AcceptedWorkloadContractError("accepted_workload_event_chain_invalid")
    if previous_event_digest_or_null is not None:
        _digest(previous_event_digest_or_null, "previous_event_digest")
    coordinate = _coordinate(event_type, coordinate_key)
    _validate_event_payload(
        branch_id=branch_id,
        event_type=event_type,
        coordinate=coordinate,
        payload_schema=payload_schema,
        payload=payload,
        payload_digest=payload_digest,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
    )
    event = {
        "schema_version": "dehps-m4-v2-accepted-workload-event.v1",
        "input_bundle_digest": _digest(input_bundle_digest, "input_bundle_digest"),
        "producer_task_key": producer_task_key(branch_id),
        "producer_execution_id": _digest(producer_execution_id, "producer_execution_id"),
        "branch_id": branch_id,
        "event_index": event_index,
        "event_type": event_type,
        "coordinate_key": coordinate,
        "payload_schema": payload_schema,
        "payload": dict(payload),
        "payload_digest": _digest(payload_digest, "payload_digest"),
        "previous_event_digest_or_null": previous_event_digest_or_null,
    }
    event["event_digest"] = m4_v2_domain_digest(
        event, domain=_domain(branch_id, "accepted-workload-event.v1")
    )
    return event


def validate_event(
    value: Mapping[str, Any],
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
) -> dict[str, Any]:
    event = _closed(value, EVENT_FIELDS, "accepted_workload_event")
    expected = build_event(
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
        event_index=event["event_index"],
        event_type=event["event_type"],
        coordinate_key=event["coordinate_key"],
        payload_schema=event["payload_schema"],
        payload=event["payload"],
        payload_digest=event["payload_digest"],
        previous_event_digest_or_null=event["previous_event_digest_or_null"],
    )
    if event != expected:
        raise AcceptedWorkloadContractError("accepted_workload_event_digest_mismatch")
    return event


def _prefix_digest(
    *, branch_id: str, input_bundle_digest: str, producer_execution_id: str, digests: list[str]
) -> str:
    return m4_v2_domain_digest(
        {
            "input_bundle_digest": input_bundle_digest,
            "producer_task_key": producer_task_key(branch_id),
            "producer_execution_id": producer_execution_id,
            "branch_id": branch_id,
            "ordered_event_digests": digests,
        },
        domain=_domain(branch_id, "accepted-workload-transcript-prefix.v1"),
    )


def _validate_event_prefix(events: Sequence[Mapping[str, Any]]) -> None:
    types = [event["event_type"] for event in events]
    if not types or types[0] != "WORKLOAD_STARTED" or types.count("WORKLOAD_STARTED") != 1:
        raise AcceptedWorkloadContractError("accepted_workload_started_event_invalid")
    if types.count("HEALTH_AGGREGATE_COMPLETE") > 1 or types.count("HISTORICAL_AGGREGATE_COMPLETE") > 1:
        raise AcceptedWorkloadContractError("accepted_workload_aggregate_duplicate")
    health = [event for event in events if event["event_type"] == "HEALTH_REPLICATE_COMMIT"]
    for ordinal, event in enumerate(health):
        if event["coordinate_key"] != {
            "cell_index": ordinal // 512, "replicate_index": ordinal % 512
        }:
            raise AcceptedWorkloadContractError("accepted_workload_health_order_invalid")
    health_aggregate = next(
        (index for index, kind in enumerate(types) if kind == "HEALTH_AGGREGATE_COMPLETE"),
        None,
    )
    if health_aggregate is not None and (
        len(health) != 7168 or types[1:health_aggregate] != ["HEALTH_REPLICATE_COMMIT"] * 7168
    ):
        raise AcceptedWorkloadContractError("accepted_workload_health_aggregate_order_invalid")
    folds = [event for event in events if event["event_type"] == "HISTORICAL_FOLD_COMMIT"]
    for offset, event in enumerate(folds):
        if event["coordinate_key"]["evaluation_ordinal"] != 901 + offset:
            raise AcceptedWorkloadContractError("accepted_workload_fold_order_invalid")
    if folds and health_aggregate is None:
        raise AcceptedWorkloadContractError("accepted_workload_fold_before_health_invalid")
    schemes = [
        event for event in events
        if event["event_type"] == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT"
    ]
    for index, event in enumerate(schemes):
        if event["coordinate_key"]["scheme_index"] != index:
            raise AcceptedWorkloadContractError("accepted_workload_scheme_order_invalid")
    if schemes and len(folds) != 2581:
        raise AcceptedWorkloadContractError("accepted_workload_scheme_before_folds_invalid")
    historical_aggregate = next(
        (index for index, kind in enumerate(types) if kind == "HISTORICAL_AGGREGATE_COMPLETE"),
        None,
    )
    if historical_aggregate is not None and (len(folds), len(schemes)) != (2581, 8):
        raise AcceptedWorkloadContractError("accepted_workload_historical_aggregate_order_invalid")
    if "TERMINAL_OUTCOME" in types:
        if types.count("TERMINAL_OUTCOME") != 1 or types[-1] != "TERMINAL_OUTCOME":
            raise AcceptedWorkloadContractError("accepted_workload_terminal_order_invalid")
        terminal = events[-1]["payload"]
        path = terminal["execution_subpath"]
        cardinality = {
            "EARLY_IDENTITY_VALID_HEALTH_REPAIR": (0, False, 0, 0, False),
            "STARTED_PARTIAL_HEALTH_REPAIR": (len(health), False, 0, 0, False),
            "COMPLETE_GRID_HEALTH_REPAIR": (7168, True, 0, 0, False),
            "IDENTITY_VALID_HEALTH_INVALID": (len(health), False, 0, 0, False),
            "IDENTITY_VALID_HISTORICAL_REPAIR": (7168, True, len(folds), len(schemes), False),
            "IDENTITY_VALID_HISTORICAL_INVALID": (7168, True, len(folds), len(schemes), False),
            "EVALUATED_COMPLETE": (7168, True, 2581, 8, True),
        }[path]
        if cardinality != (
            len(health), health_aggregate is not None, len(folds), len(schemes),
            historical_aggregate is not None,
        ):
            raise AcceptedWorkloadContractError("accepted_workload_terminal_cardinality_invalid")
        if path == "STARTED_PARTIAL_HEALTH_REPAIR" and terminal["completed_resample_count"] != 2044 * len(health):
            raise AcceptedWorkloadContractError("accepted_workload_terminal_counts_invalid")
        if path.startswith("IDENTITY_VALID_HISTORICAL_") and (
            terminal["completed_fold_count"] != len(folds)
            or terminal["completed_resample_count"] != 2000 * len(schemes)
        ):
            raise AcceptedWorkloadContractError("accepted_workload_terminal_counts_invalid")


def _expected_next_coordinate_shape(events: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    if events[-1]["event_type"] == "TERMINAL_OUTCOME":
        return None
    types = [event["event_type"] for event in events]
    health_count = types.count("HEALTH_REPLICATE_COMMIT")
    fold_count = types.count("HISTORICAL_FOLD_COMMIT")
    scheme_count = types.count("HISTORICAL_SENSITIVITY_SCHEME_COMMIT")
    if len(events) == 1:
        return {"kind": "PRE_DRAW_VALIDATION"}
    if "HEALTH_AGGREGATE_COMPLETE" not in types:
        if health_count < 7168:
            return {
                "kind": "HEALTH_REPLICATE", "cell_index": health_count // 512,
                "replicate_index": health_count % 512,
            }
        return {"kind": "HEALTH_AGGREGATE"}
    if "HISTORICAL_AGGREGATE_COMPLETE" in types:
        return {
            "kind": "TERMINAL_OUTCOME", "execution_subpath": "EVALUATED_COMPLETE",
            "decision_path": "EVALUATED_COMPLETE",
        }
    health_payload = next(
        event["payload"] for event in events if event["event_type"] == "HEALTH_AGGREGATE_COMPLETE"
    )
    if health_payload.get("measurement_health") == "REPAIR":
        return {
            "kind": "TERMINAL_OUTCOME",
            "execution_subpath": "COMPLETE_GRID_HEALTH_REPAIR",
            "decision_path": "IDENTITY_VALID_HEALTH_REPAIR",
        }
    if fold_count < 2581:
        return {"kind": "HISTORICAL_FOLD", "evaluation_ordinal": 901 + fold_count}
    if scheme_count < 8:
        return {"kind": "HISTORICAL_SENSITIVITY_SCHEME", "scheme_index": scheme_count}
    return {"kind": "HISTORICAL_AGGREGATE"}


def next_coordinate_for_prefix(
    events: Sequence[Mapping[str, Any]], *, fold_coordinates: Sequence[tuple[int, str]],
    sensitivity_scheme_ids: Sequence[str],
) -> dict[str, Any] | None:
    expected = _expected_next_coordinate_shape(events)
    if expected is None:
        return None
    result = dict(expected)
    if result["kind"] == "HISTORICAL_FOLD":
        offset = result["evaluation_ordinal"] - 901
        if not 0 <= offset < len(fold_coordinates):
            raise AcceptedWorkloadContractError("accepted_workload_next_fold_missing")
        ordinal, issue = fold_coordinates[offset]
        if ordinal != result["evaluation_ordinal"] or not issue:
            raise AcceptedWorkloadContractError("accepted_workload_next_fold_invalid")
        result["issue"] = issue
    elif result["kind"] == "HISTORICAL_SENSITIVITY_SCHEME":
        index = result["scheme_index"]
        if not 0 <= index < len(sensitivity_scheme_ids) or not sensitivity_scheme_ids[index]:
            raise AcceptedWorkloadContractError("accepted_workload_next_scheme_invalid")
        result["scheme_id"] = sensitivity_scheme_ids[index]
    return result


def next_coordinate_after_event(
    event: Mapping[str, Any],
    *,
    fold_coordinates: Sequence[tuple[int, str]],
    sensitivity_scheme_ids: Sequence[str],
) -> dict[str, Any] | None:
    """Compute the state-machine successor from one already validated event."""

    kind = event["event_type"]
    coordinate = event["coordinate_key"]
    if kind == "WORKLOAD_STARTED":
        return {"kind": "PRE_DRAW_VALIDATION"}
    if kind == "HEALTH_REPLICATE_COMMIT":
        flat_index = coordinate["cell_index"] * 512 + coordinate["replicate_index"]
        if flat_index < 7167:
            next_index = flat_index + 1
            return {
                "kind": "HEALTH_REPLICATE",
                "cell_index": next_index // 512,
                "replicate_index": next_index % 512,
            }
        return {"kind": "HEALTH_AGGREGATE"}
    if kind == "HEALTH_AGGREGATE_COMPLETE":
        if event["payload"]["measurement_health"] == "REPAIR":
            return {
                "kind": "TERMINAL_OUTCOME",
                "execution_subpath": "COMPLETE_GRID_HEALTH_REPAIR",
                "decision_path": "IDENTITY_VALID_HEALTH_REPAIR",
            }
        ordinal, issue = fold_coordinates[0]
        return {"kind": "HISTORICAL_FOLD", "evaluation_ordinal": ordinal, "issue": issue}
    if kind == "HISTORICAL_FOLD_COMMIT":
        ordinal = coordinate["evaluation_ordinal"]
        if ordinal < 3481:
            next_ordinal, issue = fold_coordinates[ordinal - 900]
            return {
                "kind": "HISTORICAL_FOLD",
                "evaluation_ordinal": next_ordinal,
                "issue": issue,
            }
        return {
            "kind": "HISTORICAL_SENSITIVITY_SCHEME",
            "scheme_index": 0,
            "scheme_id": sensitivity_scheme_ids[0],
        }
    if kind == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT":
        index = coordinate["scheme_index"]
        if index < 7:
            return {
                "kind": "HISTORICAL_SENSITIVITY_SCHEME",
                "scheme_index": index + 1,
                "scheme_id": sensitivity_scheme_ids[index + 1],
            }
        return {"kind": "HISTORICAL_AGGREGATE"}
    if kind == "HISTORICAL_AGGREGATE_COMPLETE":
        return {
            "kind": "TERMINAL_OUTCOME",
            "execution_subpath": "EVALUATED_COMPLETE",
            "decision_path": "EVALUATED_COMPLETE",
        }
    return None


def is_resume_checkpoint_count(event_count: int, terminal_seen: bool = False) -> bool:
    """Return Request520's exact geometric checkpoint predicate."""

    if (
        isinstance(event_count, bool)
        or not isinstance(event_count, int)
        or event_count <= 0
        or type(terminal_seen) is not bool
    ):
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_checkpoint_count_invalid"
        )
    return terminal_seen or event_count & (event_count - 1) == 0


def resume_delta_relative_path_v2(*, event_index: int, delta_digest: str) -> str:
    if (
        isinstance(event_index, bool)
        or not isinstance(event_index, int)
        or event_index < 0
    ):
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_delta_path_index_invalid"
        )
    return f"resume-deltas/{event_index:08d}-{_digest(delta_digest, 'delta_digest')}.json"


def resume_checkpoint_relative_path_v2(
    *, checkpoint_event_count: int, checkpoint_reference_digest: str
) -> str:
    if (
        isinstance(checkpoint_event_count, bool)
        or not isinstance(checkpoint_event_count, int)
        or checkpoint_event_count <= 0
        or checkpoint_event_count > 99_999_999
    ):
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_checkpoint_path_count_invalid"
        )
    digest = _digest(checkpoint_reference_digest, "checkpoint_reference_digest")
    return f"resume-checkpoints/{checkpoint_event_count:08d}-{digest}.json"


def resume_snapshot_relative_path_v1(
    *, checkpoint_event_count: int, resume_index_digest: str
) -> str:
    """Return Request522's immutable full-v1 snapshot path."""

    if (
        isinstance(checkpoint_event_count, bool)
        or not isinstance(checkpoint_event_count, int)
        or checkpoint_event_count <= 0
        or checkpoint_event_count > 99_999_999
    ):
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_snapshot_path_count_invalid"
        )
    digest = _digest(resume_index_digest, "resume_index_digest")
    return f"resume-snapshots/{checkpoint_event_count:08d}-{digest}.json"


def validate_resume_snapshot_relative_path_v1(
    value: Any, *, checkpoint_event_count: int, resume_index_digest: str
) -> str:
    expected = resume_snapshot_relative_path_v1(
        checkpoint_event_count=checkpoint_event_count,
        resume_index_digest=resume_index_digest,
    )
    if value != expected:
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_snapshot_path_mismatch"
        )
    return expected


def validate_resume_checkpoint_relative_path_v2(
    value: Any, *, checkpoint_event_count: int, checkpoint_reference_digest: str
) -> str:
    expected = resume_checkpoint_relative_path_v2(
        checkpoint_event_count=checkpoint_event_count,
        checkpoint_reference_digest=checkpoint_reference_digest,
    )
    if value != expected:
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_checkpoint_path_mismatch"
        )
    return expected


def _validate_resume_v2_identity(
    value: Mapping[str, Any],
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
) -> None:
    if (
        value["branch_id"] != branch_id
        or value["input_bundle_digest"]
        != _digest(input_bundle_digest, "input_bundle_digest")
        or value["producer_task_key"] != producer_task_key(branch_id)
        or value["producer_execution_id"]
        != _digest(producer_execution_id, "producer_execution_id")
    ):
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_v2_identity_mismatch"
        )


def build_rolling_prefix_root_v2(
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
    event: Mapping[str, Any],
    previous_prefix_root_digest_or_null: str | None,
) -> dict[str, Any]:
    """Build one bounded Request520 rolling-prefix-root preimage."""

    validated_event = validate_event(
        event,
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
    )
    event_index = validated_event["event_index"]
    if (event_index == 0) != (previous_prefix_root_digest_or_null is None):
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_prefix_root_chain_invalid"
        )
    if previous_prefix_root_digest_or_null is not None:
        _digest(previous_prefix_root_digest_or_null, "previous_prefix_root_digest")
    return {
        "schema_version": "dehps-m4-v2-accepted-workload-resume-prefix-root.v2",
        "input_bundle_digest": input_bundle_digest,
        "producer_task_key": producer_task_key(branch_id),
        "producer_execution_id": producer_execution_id,
        "branch_id": branch_id,
        "event_index": event_index,
        "event_digest": validated_event["event_digest"],
        "previous_prefix_root_digest_or_null": (
            previous_prefix_root_digest_or_null
        ),
    }


def rolling_prefix_root_digest_v2(
    value: Mapping[str, Any], *, branch_id: str
) -> str:
    root = _closed(
        value,
        ROLLING_PREFIX_ROOT_V2_FIELDS,
        "accepted_workload_resume_prefix_root_v2",
    )
    if root["branch_id"] != branch_id:
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_prefix_root_identity_mismatch"
        )
    return m4_v2_domain_digest(
        root, domain=_domain(branch_id, "accepted-workload-resume-prefix-root.v2")
    )


def validate_rolling_prefix_root_v2(
    value: Mapping[str, Any],
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
    event: Mapping[str, Any],
    previous_prefix_root_digest_or_null: str | None,
    expected_prefix_root_digest: str | None = None,
) -> dict[str, Any]:
    root = _closed(
        value,
        ROLLING_PREFIX_ROOT_V2_FIELDS,
        "accepted_workload_resume_prefix_root_v2",
    )
    expected = build_rolling_prefix_root_v2(
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
        event=event,
        previous_prefix_root_digest_or_null=previous_prefix_root_digest_or_null,
    )
    if root != expected:
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_prefix_root_content_mismatch"
        )
    root_digest = rolling_prefix_root_digest_v2(root, branch_id=branch_id)
    if (
        expected_prefix_root_digest is not None
        and root_digest
        != _digest(expected_prefix_root_digest, "expected_prefix_root_digest")
    ):
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_prefix_root_digest_mismatch"
        )
    return root


def _validate_resume_delta_self_v2(
    value: Mapping[str, Any],
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
) -> dict[str, Any]:
    delta = _closed(
        value, RESUME_DELTA_V2_FIELDS, "accepted_workload_resume_delta_v2"
    )
    _validate_resume_v2_identity(
        delta,
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
    )
    if delta["schema_version"] != "dehps-m4-v2-accepted-workload-resume-delta.v2":
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_delta_schema_invalid"
        )
    preimage = {field: delta[field] for field in RESUME_DELTA_V2_FIELDS[:-1]}
    expected_digest = m4_v2_domain_digest(
        preimage, domain=_domain(branch_id, "accepted-workload-resume-delta.v2")
    )
    if delta["delta_digest"] != expected_digest:
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_delta_digest_mismatch"
        )
    return delta


def _checkpoint_resume_owner_v2(
    checkpoint_resume_index_or_null: Mapping[str, Any] | None,
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
    event: Mapping[str, Any],
    next_coordinate: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    event_count = event["event_index"] + 1
    terminal_seen = event["event_type"] == "TERMINAL_OUTCOME"
    required = is_resume_checkpoint_count(event_count, terminal_seen)
    if not required:
        if checkpoint_resume_index_or_null is not None:
            raise AcceptedWorkloadContractError(
                "accepted_workload_resume_checkpoint_unexpected"
            )
        return None
    if not isinstance(checkpoint_resume_index_or_null, Mapping):
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_checkpoint_missing"
        )
    checkpoint = validate_resume_index(
        checkpoint_resume_index_or_null,
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
    )
    parsed_next = None if terminal_seen else _next_coordinate(next_coordinate)
    if (
        checkpoint["next_event_index"] != event_count
        or len(checkpoint["events"]) != event_count
        or checkpoint["events"][-1] != event
        or checkpoint["ordered_event_digests"][-1] != event["event_digest"]
        or checkpoint["next_coordinate"] != parsed_next
        or checkpoint["terminal_seen"] is not terminal_seen
    ):
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_checkpoint_owner_mismatch"
        )
    return checkpoint


def _validate_next_coordinate_after_event_v2(
    event: Mapping[str, Any], next_coordinate: Mapping[str, Any] | None
) -> None:
    kind = event["event_type"]
    coordinate = event["coordinate_key"]
    payload = event["payload"]
    if kind == "TERMINAL_OUTCOME":
        valid = next_coordinate is None
    elif not isinstance(next_coordinate, Mapping):
        valid = False
    elif kind == "WORKLOAD_STARTED":
        valid = next_coordinate == {"kind": "PRE_DRAW_VALIDATION"}
    elif kind == "HEALTH_REPLICATE_COMMIT":
        flat_index = coordinate["cell_index"] * 512 + coordinate["replicate_index"]
        expected = (
            {
                "kind": "HEALTH_REPLICATE",
                "cell_index": (flat_index + 1) // 512,
                "replicate_index": (flat_index + 1) % 512,
            }
            if flat_index < 7167
            else {"kind": "HEALTH_AGGREGATE"}
        )
        valid = next_coordinate == expected
    elif kind == "HEALTH_AGGREGATE_COMPLETE":
        if payload["measurement_health"] == "REPAIR":
            expected = {
                "kind": "TERMINAL_OUTCOME",
                "execution_subpath": "COMPLETE_GRID_HEALTH_REPAIR",
                "decision_path": "IDENTITY_VALID_HEALTH_REPAIR",
            }
            valid = next_coordinate == expected
        else:
            valid = (
                next_coordinate.get("kind") == "HISTORICAL_FOLD"
                and next_coordinate.get("evaluation_ordinal") == 901
                and isinstance(next_coordinate.get("issue"), str)
                and bool(next_coordinate["issue"])
            )
    elif kind == "HISTORICAL_FOLD_COMMIT":
        ordinal = coordinate["evaluation_ordinal"]
        if ordinal < 3481:
            valid = (
                next_coordinate.get("kind") == "HISTORICAL_FOLD"
                and next_coordinate.get("evaluation_ordinal") == ordinal + 1
                and isinstance(next_coordinate.get("issue"), str)
                and bool(next_coordinate["issue"])
            )
        else:
            valid = (
                next_coordinate.get("kind")
                == "HISTORICAL_SENSITIVITY_SCHEME"
                and next_coordinate.get("scheme_index") == 0
                and isinstance(next_coordinate.get("scheme_id"), str)
                and bool(next_coordinate["scheme_id"])
            )
    elif kind == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT":
        scheme_index = coordinate["scheme_index"]
        if scheme_index < 7:
            valid = (
                next_coordinate.get("kind")
                == "HISTORICAL_SENSITIVITY_SCHEME"
                and next_coordinate.get("scheme_index") == scheme_index + 1
                and isinstance(next_coordinate.get("scheme_id"), str)
                and bool(next_coordinate["scheme_id"])
            )
        else:
            valid = next_coordinate == {"kind": "HISTORICAL_AGGREGATE"}
    elif kind == "HISTORICAL_AGGREGATE_COMPLETE":
        valid = next_coordinate == {
            "kind": "TERMINAL_OUTCOME",
            "execution_subpath": "EVALUATED_COMPLETE",
            "decision_path": "EVALUATED_COMPLETE",
        }
    else:
        valid = False
    if not valid:
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_delta_next_coordinate_mismatch"
        )


def _validate_event_matches_prior_next_coordinate_v2(
    event: Mapping[str, Any], prior_next_coordinate: Mapping[str, Any] | None
) -> None:
    if not isinstance(prior_next_coordinate, Mapping):
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_delta_prior_coordinate_invalid"
        )
    next_kind = prior_next_coordinate.get("kind")
    event_type = event["event_type"]
    coordinate = event["coordinate_key"]
    if next_kind == "PRE_DRAW_VALIDATION":
        valid = event_type in {"HEALTH_REPLICATE_COMMIT", "TERMINAL_OUTCOME"}
    elif next_kind == "HEALTH_REPLICATE":
        valid = event_type == "HEALTH_REPLICATE_COMMIT" and coordinate == {
            "cell_index": prior_next_coordinate.get("cell_index"),
            "replicate_index": prior_next_coordinate.get("replicate_index"),
        }
    elif next_kind == "HEALTH_AGGREGATE":
        valid = event_type == "HEALTH_AGGREGATE_COMPLETE"
    elif next_kind == "HISTORICAL_FOLD":
        valid = event_type == "HISTORICAL_FOLD_COMMIT" and coordinate == {
            "evaluation_ordinal": prior_next_coordinate.get("evaluation_ordinal"),
            "issue": prior_next_coordinate.get("issue"),
        }
    elif next_kind == "HISTORICAL_SENSITIVITY_SCHEME":
        valid = (
            event_type == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT"
            and coordinate
            == {
                "scheme_index": prior_next_coordinate.get("scheme_index"),
                "scheme_id": prior_next_coordinate.get("scheme_id"),
            }
        )
    elif next_kind == "HISTORICAL_AGGREGATE":
        valid = event_type == "HISTORICAL_AGGREGATE_COMPLETE"
    elif next_kind == "TERMINAL_OUTCOME":
        valid = event_type == "TERMINAL_OUTCOME" and all(
            event["payload"].get(key) == prior_next_coordinate.get(key)
            for key in ("execution_subpath", "decision_path")
        )
    else:
        valid = False
    if not valid:
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_delta_prior_coordinate_mismatch"
        )


def build_resume_delta_v2(
    previous_delta: Mapping[str, Any] | None,
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
    event: Mapping[str, Any],
    next_coordinate: Mapping[str, Any] | None,
    checkpoint_resume_index_or_null: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build one O(1) ordinary resume transition delta."""

    validated_event = validate_event(
        event,
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
    )
    event_index = validated_event["event_index"]
    if previous_delta is None:
        if (
            event_index != 0
            or validated_event["event_type"] != "WORKLOAD_STARTED"
            or validated_event["previous_event_digest_or_null"] is not None
        ):
            raise AcceptedWorkloadContractError(
                "accepted_workload_resume_delta_initial_event_invalid"
            )
        prior = None
        previous_delta_digest = None
        previous_prefix_root_digest = None
    else:
        prior = _validate_resume_delta_self_v2(
            previous_delta,
            branch_id=branch_id,
            input_bundle_digest=input_bundle_digest,
            producer_execution_id=producer_execution_id,
        )
        if (
            prior["terminal_seen"] is True
            or event_index != prior["next_event_index"]
            or validated_event["previous_event_digest_or_null"]
            != prior["event_digest"]
        ):
            raise AcceptedWorkloadContractError(
                "accepted_workload_resume_delta_chain_invalid"
            )
        _validate_event_matches_prior_next_coordinate_v2(
            validated_event, prior["next_coordinate"]
        )
        previous_delta_digest = prior["delta_digest"]
        previous_prefix_root_digest = prior["prefix_root_digest"]

    terminal_seen = validated_event["event_type"] == "TERMINAL_OUTCOME"
    if terminal_seen:
        if next_coordinate is not None:
            raise AcceptedWorkloadContractError(
                "accepted_workload_resume_terminal_next_coordinate_invalid"
            )
        parsed_next = None
        execution_subpath = validated_event["payload"]["execution_subpath"]
        decision_path = validated_event["payload"]["decision_path"]
    else:
        parsed_next = _next_coordinate(next_coordinate)
        execution_subpath = None
        decision_path = None
    _validate_next_coordinate_after_event_v2(validated_event, parsed_next)

    checkpoint = _checkpoint_resume_owner_v2(
        checkpoint_resume_index_or_null,
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
        event=validated_event,
        next_coordinate=parsed_next,
    )
    if checkpoint is not None:
        latest_checkpoint_event_count = event_index + 1
        latest_checkpoint_resume_digest = checkpoint["resume_index_digest"]
    elif prior is not None:
        latest_checkpoint_event_count = prior["latest_checkpoint_event_count"]
        latest_checkpoint_resume_digest = prior[
            "latest_checkpoint_resume_index_digest_or_null"
        ]
    else:  # event_count=1 is always a checkpoint
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_checkpoint_missing"
        )

    prefix_root = build_rolling_prefix_root_v2(
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
        event=validated_event,
        previous_prefix_root_digest_or_null=previous_prefix_root_digest,
    )
    prefix_root_digest = rolling_prefix_root_digest_v2(
        prefix_root, branch_id=branch_id
    )
    result = {
        "schema_version": "dehps-m4-v2-accepted-workload-resume-delta.v2",
        "input_bundle_digest": input_bundle_digest,
        "producer_task_key": producer_task_key(branch_id),
        "producer_execution_id": producer_execution_id,
        "branch_id": branch_id,
        "event_index": event_index,
        "event_digest": validated_event["event_digest"],
        "previous_delta_digest_or_null": previous_delta_digest,
        "previous_prefix_root_digest_or_null": previous_prefix_root_digest,
        "prefix_root_digest": prefix_root_digest,
        "next_event_index": event_index + 1,
        "next_coordinate": parsed_next,
        "terminal_seen": terminal_seen,
        "execution_subpath_or_null": execution_subpath,
        "decision_path_or_null": decision_path,
        "latest_checkpoint_event_count": latest_checkpoint_event_count,
        "latest_checkpoint_resume_index_digest_or_null": (
            latest_checkpoint_resume_digest
        ),
    }
    result["delta_digest"] = m4_v2_domain_digest(
        result, domain=_domain(branch_id, "accepted-workload-resume-delta.v2")
    )
    return result


def validate_resume_delta_v2(
    value: Mapping[str, Any],
    previous_delta: Mapping[str, Any] | None,
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
    event: Mapping[str, Any],
    next_coordinate: Mapping[str, Any] | None,
    checkpoint_resume_index_or_null: Mapping[str, Any] | None,
) -> dict[str, Any]:
    delta = _validate_resume_delta_self_v2(
        value,
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
    )
    expected = build_resume_delta_v2(
        previous_delta,
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
        event=event,
        next_coordinate=next_coordinate,
        checkpoint_resume_index_or_null=checkpoint_resume_index_or_null,
    )
    if delta != expected:
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_delta_content_mismatch"
        )
    return delta


def build_resume_journal_head_v2(
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
    delta: Mapping[str, Any],
    latest_checkpoint_reference_or_null: Mapping[str, Any] | None,
) -> dict[str, Any]:
    validated_delta = _validate_resume_delta_self_v2(
        delta,
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
    )
    checkpoint_count = validated_delta["latest_checkpoint_event_count"]
    checkpoint_resume_digest = validated_delta[
        "latest_checkpoint_resume_index_digest_or_null"
    ]
    if checkpoint_count is None or checkpoint_resume_digest is None:
        if not (checkpoint_count is None and checkpoint_resume_digest is None):
            raise AcceptedWorkloadContractError(
                "accepted_workload_resume_head_checkpoint_tuple_partial"
            )
        if latest_checkpoint_reference_or_null is not None:
            raise AcceptedWorkloadContractError(
                "accepted_workload_resume_head_checkpoint_unexpected"
            )
        snapshot_path = None
        checkpoint_reference_digest = None
        checkpoint_reference_path = None
    else:
        if not isinstance(latest_checkpoint_reference_or_null, Mapping):
            raise AcceptedWorkloadContractError(
                "accepted_workload_resume_head_checkpoint_missing"
            )
        reference = _validate_resume_checkpoint_reference_self_v2(
            latest_checkpoint_reference_or_null,
            branch_id=branch_id,
            input_bundle_digest=input_bundle_digest,
            producer_execution_id=producer_execution_id,
        )
        if (
            reference["checkpoint_event_count"] != checkpoint_count
            or reference["v1_resume_index_digest"] != checkpoint_resume_digest
            or checkpoint_count > validated_delta["next_event_index"]
        ):
            raise AcceptedWorkloadContractError(
                "accepted_workload_resume_head_checkpoint_owner_mismatch"
            )
        if checkpoint_count == validated_delta["next_event_index"] and (
            reference["checkpoint_last_event_digest"]
            != validated_delta["event_digest"]
            or reference["checkpoint_last_delta_digest"]
            != validated_delta["delta_digest"]
            or reference["checkpoint_prefix_root_digest"]
            != validated_delta["prefix_root_digest"]
        ):
            raise AcceptedWorkloadContractError(
                "accepted_workload_resume_head_checkpoint_endpoint_mismatch"
            )
        snapshot_path = reference["v1_resume_snapshot_path"]
        checkpoint_reference_digest = reference["checkpoint_reference_digest"]
        checkpoint_reference_path = resume_checkpoint_relative_path_v2(
            checkpoint_event_count=checkpoint_count,
            checkpoint_reference_digest=checkpoint_reference_digest,
        )
    result = {
        "schema_version": (
            "dehps-m4-v2-accepted-workload-resume-journal-head.v2"
        ),
        "input_bundle_digest": input_bundle_digest,
        "producer_task_key": producer_task_key(branch_id),
        "producer_execution_id": producer_execution_id,
        "branch_id": branch_id,
        "last_event_index": validated_delta["event_index"],
        "last_event_digest": validated_delta["event_digest"],
        "last_delta_digest": validated_delta["delta_digest"],
        "prefix_root_digest": validated_delta["prefix_root_digest"],
        "next_event_index": validated_delta["next_event_index"],
        "next_coordinate": validated_delta["next_coordinate"],
        "terminal_seen": validated_delta["terminal_seen"],
        "execution_subpath_or_null": validated_delta[
            "execution_subpath_or_null"
        ],
        "decision_path_or_null": validated_delta["decision_path_or_null"],
        "latest_checkpoint_event_count": validated_delta[
            "latest_checkpoint_event_count"
        ],
        "latest_checkpoint_resume_index_digest_or_null": validated_delta[
            "latest_checkpoint_resume_index_digest_or_null"
        ],
        "latest_checkpoint_snapshot_path_or_null": snapshot_path,
        "latest_checkpoint_reference_digest_or_null": (
            checkpoint_reference_digest
        ),
        "latest_checkpoint_reference_path_or_null": checkpoint_reference_path,
    }
    result["head_digest"] = m4_v2_domain_digest(
        result,
        domain=_domain(branch_id, "accepted-workload-resume-journal-head.v2"),
    )
    return result


def validate_resume_journal_head_v2(
    value: Mapping[str, Any],
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
    delta: Mapping[str, Any],
    latest_checkpoint_reference_or_null: Mapping[str, Any] | None,
) -> dict[str, Any]:
    head = _closed(
        value,
        RESUME_JOURNAL_HEAD_V2_FIELDS,
        "accepted_workload_resume_journal_head_v2",
    )
    _validate_resume_v2_identity(
        head,
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
    )
    expected = build_resume_journal_head_v2(
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
        delta=delta,
        latest_checkpoint_reference_or_null=latest_checkpoint_reference_or_null,
    )
    if head != expected:
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_journal_head_content_mismatch"
        )
    return head


def _validate_resume_checkpoint_reference_self_v2(
    value: Mapping[str, Any],
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
) -> dict[str, Any]:
    reference = _closed(
        value,
        RESUME_CHECKPOINT_REFERENCE_V2_FIELDS,
        "accepted_workload_resume_checkpoint_reference_v2",
    )
    _validate_resume_v2_identity(
        reference,
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
    )
    if reference["schema_version"] != (
        "dehps-m4-v2-accepted-workload-resume-checkpoint-reference.v2"
    ):
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_checkpoint_reference_schema_invalid"
        )
    event_count = reference["checkpoint_event_count"]
    if (
        isinstance(event_count, bool)
        or not isinstance(event_count, int)
        or not 1 <= event_count <= 99_999_999
    ):
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_checkpoint_reference_count_invalid"
        )
    for field in (
        "checkpoint_last_event_digest",
        "checkpoint_last_delta_digest",
        "checkpoint_prefix_root_digest",
        "v1_resume_index_digest",
        "checkpoint_reference_digest",
    ):
        _digest(reference[field], field)
    validate_resume_snapshot_relative_path_v1(
        reference["v1_resume_snapshot_path"],
        checkpoint_event_count=event_count,
        resume_index_digest=reference["v1_resume_index_digest"],
    )
    preimage = {
        field: reference[field]
        for field in RESUME_CHECKPOINT_REFERENCE_V2_FIELDS[:-1]
    }
    expected_digest = m4_v2_domain_digest(
        preimage,
        domain=_domain(
            branch_id, "accepted-workload-resume-checkpoint-reference.v2"
        ),
    )
    if reference["checkpoint_reference_digest"] != expected_digest:
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_checkpoint_reference_digest_mismatch"
        )
    return reference


def validate_resume_snapshot_v1(
    value: Mapping[str, Any],
    *,
    snapshot_path: Any,
    checkpoint_event_count: int,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
) -> dict[str, Any]:
    """Validate one immutable full-v1 snapshot and its content-addressed path."""

    checkpoint = validate_resume_index(
        value,
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
    )
    if (
        checkpoint["next_event_index"] != checkpoint_event_count
        or len(checkpoint["events"]) != checkpoint_event_count
        or not is_resume_checkpoint_count(
            checkpoint_event_count, checkpoint["terminal_seen"]
        )
    ):
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_snapshot_owner_mismatch"
        )
    validate_resume_snapshot_relative_path_v1(
        snapshot_path,
        checkpoint_event_count=checkpoint_event_count,
        resume_index_digest=checkpoint["resume_index_digest"],
    )
    return checkpoint


def build_resume_checkpoint_reference_v2(
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
    delta: Mapping[str, Any],
    checkpoint_resume_index: Mapping[str, Any],
) -> dict[str, Any]:
    validated_delta = _validate_resume_delta_self_v2(
        delta,
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
    )
    event_count = validated_delta["next_event_index"]
    if not is_resume_checkpoint_count(event_count, validated_delta["terminal_seen"]):
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_checkpoint_reference_cadence_invalid"
        )
    checkpoint = validate_resume_index(
        checkpoint_resume_index,
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
    )
    if (
        checkpoint["next_event_index"] != event_count
        or len(checkpoint["events"]) != event_count
        or checkpoint["ordered_event_digests"][-1]
        != validated_delta["event_digest"]
        or checkpoint["resume_index_digest"]
        != validated_delta["latest_checkpoint_resume_index_digest_or_null"]
        or checkpoint["next_coordinate"] != validated_delta["next_coordinate"]
        or checkpoint["terminal_seen"] is not validated_delta["terminal_seen"]
    ):
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_checkpoint_reference_owner_mismatch"
        )
    result = {
        "schema_version": (
            "dehps-m4-v2-accepted-workload-resume-checkpoint-reference.v2"
        ),
        "input_bundle_digest": input_bundle_digest,
        "producer_task_key": producer_task_key(branch_id),
        "producer_execution_id": producer_execution_id,
        "branch_id": branch_id,
        "checkpoint_event_count": event_count,
        "checkpoint_last_event_digest": validated_delta["event_digest"],
        "checkpoint_last_delta_digest": validated_delta["delta_digest"],
        "checkpoint_prefix_root_digest": validated_delta["prefix_root_digest"],
        "v1_resume_index_digest": checkpoint["resume_index_digest"],
        "v1_resume_snapshot_path": resume_snapshot_relative_path_v1(
            checkpoint_event_count=event_count,
            resume_index_digest=checkpoint["resume_index_digest"],
        ),
    }
    result["checkpoint_reference_digest"] = m4_v2_domain_digest(
        result,
        domain=_domain(
            branch_id, "accepted-workload-resume-checkpoint-reference.v2"
        ),
    )
    return result


def validate_resume_checkpoint_reference_v2(
    value: Mapping[str, Any],
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
    delta: Mapping[str, Any],
    checkpoint_resume_index: Mapping[str, Any],
) -> dict[str, Any]:
    reference = _validate_resume_checkpoint_reference_self_v2(
        value,
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
    )
    expected = build_resume_checkpoint_reference_v2(
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
        delta=delta,
        checkpoint_resume_index=checkpoint_resume_index,
    )
    if reference != expected:
        raise AcceptedWorkloadContractError(
            "accepted_workload_resume_checkpoint_reference_content_mismatch"
        )
    return reference


def build_resume_journal_transition(
    previous_delta: Mapping[str, Any] | None,
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
    event: Mapping[str, Any],
    next_coordinate: Mapping[str, Any] | None,
    checkpoint_resume_index_or_null: Mapping[str, Any] | None,
    latest_checkpoint_reference_or_null: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    """Build one delta, bounded journal head, and optional checkpoint reference."""

    delta = build_resume_delta_v2(
        previous_delta,
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
        event=event,
        next_coordinate=next_coordinate,
        checkpoint_resume_index_or_null=checkpoint_resume_index_or_null,
    )
    checkpoint_reference = None
    if checkpoint_resume_index_or_null is not None:
        if latest_checkpoint_reference_or_null is not None:
            raise AcceptedWorkloadContractError(
                "accepted_workload_resume_transition_checkpoint_ambiguous"
            )
        checkpoint_reference = build_resume_checkpoint_reference_v2(
            branch_id=branch_id,
            input_bundle_digest=input_bundle_digest,
            producer_execution_id=producer_execution_id,
            delta=delta,
            checkpoint_resume_index=checkpoint_resume_index_or_null,
        )
        head_checkpoint_reference = checkpoint_reference
    else:
        head_checkpoint_reference = latest_checkpoint_reference_or_null
    head = build_resume_journal_head_v2(
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
        delta=delta,
        latest_checkpoint_reference_or_null=head_checkpoint_reference,
    )
    return delta, head, checkpoint_reference


def advance_resume_index(
    previous: Mapping[str, Any] | None,
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
    event: Mapping[str, Any],
    fold_coordinates: Sequence[tuple[int, str]],
    sensitivity_scheme_ids: Sequence[str],
) -> dict[str, Any]:
    """Advance a verified resume root while validating only its unique next event."""

    if previous is None:
        return build_resume_index(
            branch_id=branch_id,
            input_bundle_digest=input_bundle_digest,
            producer_execution_id=producer_execution_id,
            events=[event],
            next_coordinate=next_coordinate_after_event(
                event,
                fold_coordinates=fold_coordinates,
                sensitivity_scheme_ids=sensitivity_scheme_ids,
            ),
        )
    prior = _closed(previous, RESUME_INDEX_FIELDS, "accepted_workload_resume_index")
    validated = validate_event(
        event,
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
    )
    if (
        prior["terminal_seen"] is True
        or validated["event_index"] != prior["next_event_index"]
        or validated["previous_event_digest_or_null"]
        != prior["ordered_event_digests"][-1]
    ):
        raise AcceptedWorkloadContractError("accepted_workload_resume_advance_invalid")
    expected_incoming = prior["next_coordinate"]
    incoming_kind = expected_incoming.get("kind") if isinstance(expected_incoming, Mapping) else None
    event_coordinate = validated["coordinate_key"]
    event_type = validated["event_type"]
    compatible = {
        "PRE_DRAW_VALIDATION": event_type
        in {"HEALTH_REPLICATE_COMMIT", "TERMINAL_OUTCOME"},
        "HEALTH_REPLICATE": event_type == "HEALTH_REPLICATE_COMMIT"
        and all(event_coordinate.get(key) == expected_incoming.get(key) for key in ("cell_index", "replicate_index")),
        "HEALTH_AGGREGATE": event_type == "HEALTH_AGGREGATE_COMPLETE",
        "HISTORICAL_FOLD": event_type == "HISTORICAL_FOLD_COMMIT"
        and all(event_coordinate.get(key) == expected_incoming.get(key) for key in ("evaluation_ordinal", "issue")),
        "HISTORICAL_SENSITIVITY_SCHEME": event_type
        == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT"
        and all(event_coordinate.get(key) == expected_incoming.get(key) for key in ("scheme_index", "scheme_id")),
        "HISTORICAL_AGGREGATE": event_type == "HISTORICAL_AGGREGATE_COMPLETE",
        "TERMINAL_OUTCOME": event_type == "TERMINAL_OUTCOME"
        and all(event_coordinate.get(key) == expected_incoming.get(key) for key in ("execution_subpath", "decision_path")),
    }.get(incoming_kind, False)
    if not compatible:
        raise AcceptedWorkloadContractError("accepted_workload_resume_advance_coordinate_invalid")
    events = [*prior["events"], validated]
    ordered = [*prior["ordered_event_digests"], validated["event_digest"]]
    terminal = validated["payload"] if event_type == "TERMINAL_OUTCOME" else None
    next_coordinate = next_coordinate_after_event(
        validated,
        fold_coordinates=fold_coordinates,
        sensitivity_scheme_ids=sensitivity_scheme_ids,
    )
    if terminal is not None and terminal["preterminal_transcript_digest"] != _preterminal_digest(
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
        execution_subpath=terminal["execution_subpath"],
        decision_path=terminal["decision_path"],
        digests=list(prior["ordered_event_digests"]),
    ):
        raise AcceptedWorkloadContractError("accepted_workload_preterminal_digest_mismatch")
    result = {
        "schema_version": "dehps-m4-v2-accepted-workload-resume-index.v1",
        "input_bundle_digest": input_bundle_digest,
        "producer_task_key": producer_task_key(branch_id),
        "producer_execution_id": producer_execution_id,
        "branch_id": branch_id,
        "events": events,
        "ordered_event_digests": ordered,
        "next_event_index": len(events),
        "next_coordinate": next_coordinate,
        "terminal_seen": terminal is not None,
        "execution_subpath_or_null": terminal.get("execution_subpath") if terminal else None,
        "decision_path_or_null": terminal.get("decision_path") if terminal else None,
        "transcript_prefix_digest": _prefix_digest(
            branch_id=branch_id,
            input_bundle_digest=input_bundle_digest,
            producer_execution_id=producer_execution_id,
            digests=ordered,
        ),
    }
    result["resume_index_digest"] = m4_v2_domain_digest(
        result, domain=_domain(branch_id, "accepted-workload-resume-index.v1")
    )
    return result


def build_resume_index(
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
    events: Iterable[Mapping[str, Any]],
    next_coordinate: Mapping[str, Any] | None,
) -> dict[str, Any]:
    validated = [
        validate_event(
            event,
            branch_id=branch_id,
            input_bundle_digest=input_bundle_digest,
            producer_execution_id=producer_execution_id,
        )
        for event in events
    ]
    if not validated or [event["event_index"] for event in validated] != list(
        range(len(validated))
    ):
        raise AcceptedWorkloadContractError("accepted_workload_resume_prefix_not_contiguous")
    if validated[0]["event_type"] != "WORKLOAD_STARTED":
        raise AcceptedWorkloadContractError("accepted_workload_started_event_missing")
    for index, event in enumerate(validated):
        previous = None if index == 0 else validated[index - 1]["event_digest"]
        if event["previous_event_digest_or_null"] != previous:
            raise AcceptedWorkloadContractError("accepted_workload_resume_event_chain_invalid")
    _validate_event_prefix(validated)
    terminals = [event for event in validated if event["event_type"] == "TERMINAL_OUTCOME"]
    if terminals not in ([], [validated[-1]]):
        raise AcceptedWorkloadContractError("accepted_workload_resume_terminal_invalid")
    terminal = terminals[0]["payload"] if terminals else None
    ordered = [event["event_digest"] for event in validated]
    parsed_next = None if terminal is not None else _next_coordinate(next_coordinate)
    expected_next = _expected_next_coordinate_shape(validated)
    if parsed_next is not None and expected_next is not None and any(
        parsed_next.get(key) != expected for key, expected in expected_next.items()
    ):
        raise AcceptedWorkloadContractError("accepted_workload_next_coordinate_mismatch")
    if (parsed_next is None) != (expected_next is None):
        raise AcceptedWorkloadContractError("accepted_workload_next_coordinate_mismatch")
    if terminal is not None:
        expected_preterminal = _preterminal_digest(
            branch_id=branch_id, input_bundle_digest=input_bundle_digest,
            producer_execution_id=producer_execution_id,
            execution_subpath=terminal["execution_subpath"],
            decision_path=terminal["decision_path"], digests=ordered[:-1],
        )
        if terminal["preterminal_transcript_digest"] != expected_preterminal:
            raise AcceptedWorkloadContractError("accepted_workload_preterminal_digest_mismatch")
    result = {
        "schema_version": "dehps-m4-v2-accepted-workload-resume-index.v1",
        "input_bundle_digest": input_bundle_digest,
        "producer_task_key": producer_task_key(branch_id),
        "producer_execution_id": producer_execution_id,
        "branch_id": branch_id,
        "events": validated,
        "ordered_event_digests": ordered,
        "next_event_index": len(validated),
        "next_coordinate": parsed_next,
        "terminal_seen": terminal is not None,
        "execution_subpath_or_null": (
            terminal.get("execution_subpath") if terminal is not None else None
        ),
        "decision_path_or_null": terminal.get("decision_path") if terminal is not None else None,
        "transcript_prefix_digest": _prefix_digest(
            branch_id=branch_id,
            input_bundle_digest=input_bundle_digest,
            producer_execution_id=producer_execution_id,
            digests=ordered,
        ),
    }
    result["resume_index_digest"] = m4_v2_domain_digest(
        result, domain=_domain(branch_id, "accepted-workload-resume-index.v1")
    )
    return result


def _next_coordinate(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AcceptedWorkloadContractError("accepted_workload_next_coordinate_missing")
    coordinate = dict(value)
    kind = coordinate.get("kind")
    fields = {
        "PRE_DRAW_VALIDATION": ("kind",),
        "HEALTH_REPLICATE": ("kind", "cell_index", "replicate_index"),
        "HEALTH_AGGREGATE": ("kind",),
        "HISTORICAL_FOLD": ("kind", "evaluation_ordinal", "issue"),
        "HISTORICAL_SENSITIVITY_SCHEME": ("kind", "scheme_index", "scheme_id"),
        "HISTORICAL_AGGREGATE": ("kind",),
        "TERMINAL_OUTCOME": ("kind", "execution_subpath", "decision_path"),
    }.get(kind)
    if fields is None:
        raise AcceptedWorkloadContractError("accepted_workload_next_coordinate_invalid")
    _closed(coordinate, fields, "accepted_workload_next_coordinate")
    if kind == "HEALTH_REPLICATE":
        _coordinate("HEALTH_REPLICATE_COMMIT", {k: coordinate[k] for k in fields[1:]})
    elif kind == "HISTORICAL_FOLD":
        _coordinate("HISTORICAL_FOLD_COMMIT", {k: coordinate[k] for k in fields[1:]})
    elif kind == "HISTORICAL_SENSITIVITY_SCHEME":
        _coordinate("HISTORICAL_SENSITIVITY_SCHEME_COMMIT", {k: coordinate[k] for k in fields[1:]})
    return coordinate


def _preterminal_digest(
    *, branch_id: str, input_bundle_digest: str, producer_execution_id: str,
    execution_subpath: str, decision_path: str, digests: list[str],
) -> str:
    return m4_v2_domain_digest(
        {
            "input_bundle_digest": input_bundle_digest,
            "producer_task_key": producer_task_key(branch_id),
            "producer_execution_id": producer_execution_id,
            "branch_id": branch_id,
            "execution_subpath": execution_subpath,
            "decision_path": decision_path,
            "ordered_preterminal_event_digests": digests,
        },
        domain=_domain(branch_id, "accepted-workload-preterminal-transcript.v1"),
    )


def build_full_transcript(
    *, branch_id: str, input_bundle_digest: str, producer_execution_id: str,
    events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    validated = [
        validate_event(event, branch_id=branch_id, input_bundle_digest=input_bundle_digest,
                       producer_execution_id=producer_execution_id)
        for event in events
    ]
    if len(validated) < 2 or validated[0]["event_type"] != "WORKLOAD_STARTED" or validated[-1]["event_type"] != "TERMINAL_OUTCOME":
        raise AcceptedWorkloadContractError("accepted_workload_transcript_boundary_invalid")
    if [event["event_index"] for event in validated] != list(range(len(validated))):
        raise AcceptedWorkloadContractError("accepted_workload_transcript_index_invalid")
    terminal = validated[-1]["payload"]
    ordered = [event["event_digest"] for event in validated]
    preterminal = _preterminal_digest(
        branch_id=branch_id, input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
        execution_subpath=terminal["execution_subpath"], decision_path=terminal["decision_path"],
        digests=ordered[:-1],
    )
    if terminal["preterminal_transcript_digest"] != preterminal:
        raise AcceptedWorkloadContractError("accepted_workload_preterminal_digest_mismatch")
    result = {
        "schema_version": "dehps-m4-v2-accepted-workload-transcript.v1",
        "input_bundle_digest": input_bundle_digest,
        "producer_task_key": producer_task_key(branch_id),
        "producer_execution_id": producer_execution_id,
        "branch_id": branch_id,
        "execution_subpath": terminal["execution_subpath"],
        "decision_path": terminal["decision_path"],
        "events": validated,
        "ordered_event_digests": ordered,
        "event_count": len(validated),
        "terminal_event_digest": ordered[-1],
        "preterminal_transcript_digest": preterminal,
    }
    result["transcript_digest"] = m4_v2_domain_digest(
        result, domain=_domain(branch_id, "accepted-workload-transcript.v1")
    )
    return result


def event_payload_schema(*, branch_id: str, event_type: str) -> str:
    try:
        return _EVENT_PAYLOAD_SCHEMAS[branch_id][event_type]
    except KeyError as exc:
        raise AcceptedWorkloadContractError("accepted_workload_event_schema_unknown") from exc


def event_payload_digest(
    *, branch_id: str, event_type: str, payload: Mapping[str, Any]
) -> str:
    body = dict(payload)
    if event_type == "HEALTH_REPLICATE_COMMIT":
        return _digest(body.get("replicate_evidence_digest"), "replicate_evidence_digest")
    if event_type == "HISTORICAL_FOLD_COMMIT":
        return _digest(body.get("fold_commit_digest"), "fold_commit_digest")
    if event_type in {"HEALTH_AGGREGATE_COMPLETE", "HISTORICAL_AGGREGATE_COMPLETE"}:
        artifact_type, schema_version = _AGGREGATE_IDENTITIES[branch_id][event_type]
        preimage: Mapping[str, Any] = {
            "artifact_type": artifact_type, "schema_version": schema_version, "body": body
        }
    else:
        preimage = body
    return m4_v2_domain_digest(
        preimage, domain=_domain(branch_id, _PAYLOAD_DIGEST_SUFFIX[event_type])
    )


def preterminal_transcript_digest(
    *, branch_id: str, input_bundle_digest: str, producer_execution_id: str,
    execution_subpath: str, decision_path: str,
    ordered_preterminal_event_digests: Sequence[str],
) -> str:
    return _preterminal_digest(
        branch_id=branch_id, input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
        execution_subpath=execution_subpath, decision_path=decision_path,
        digests=list(ordered_preterminal_event_digests),
    )


def validate_full_transcript(
    value: Mapping[str, Any], *, branch_id: str, input_bundle_digest: str,
    producer_execution_id: str,
) -> dict[str, Any]:
    transcript = _closed(value, TRANSCRIPT_FIELDS, "accepted_workload_transcript")
    rebuilt = build_full_transcript(
        branch_id=branch_id, input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id, events=transcript["events"]
    )
    if transcript != rebuilt:
        raise AcceptedWorkloadContractError("accepted_workload_transcript_content_mismatch")
    return transcript


def validate_resume_index(
    value: Mapping[str, Any],
    *,
    branch_id: str,
    input_bundle_digest: str,
    producer_execution_id: str,
) -> dict[str, Any]:
    index = _closed(value, RESUME_INDEX_FIELDS, "accepted_workload_resume_index")
    if (
        index["branch_id"] != branch_id
        or index["input_bundle_digest"] != input_bundle_digest
        or index["producer_task_key"] != producer_task_key(branch_id)
        or index["producer_execution_id"] != producer_execution_id
    ):
        raise AcceptedWorkloadContractError("accepted_workload_resume_identity_mismatch")
    rebuilt = build_resume_index(
        branch_id=branch_id,
        input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
        events=index["events"],
        next_coordinate=index["next_coordinate"],
    )
    if rebuilt != index:
        raise AcceptedWorkloadContractError("accepted_workload_resume_content_mismatch")
    return index


def resume_events(
    *, branch_id: str, input_bundle_digest: str, producer_execution_id: str,
    resume_index: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if resume_index is None:
        return []
    index = validate_resume_index(
        resume_index, branch_id=branch_id, input_bundle_digest=input_bundle_digest,
        producer_execution_id=producer_execution_id,
    )
    return [dict(event) for event in index["events"]]


def evaluated_coordinate_sequence(
    *, fold_coordinates: Sequence[tuple[int, str]],
    sensitivity_scheme_ids: Sequence[str], execution_subpath: str = "EVALUATED_COMPLETE",
    decision_path: str = "EVALUATED_COMPLETE",
) -> Iterator[tuple[str, dict[str, Any]]]:
    if len(fold_coordinates) != 2581 or len(sensitivity_scheme_ids) != 8:
        raise AcceptedWorkloadContractError("accepted_workload_registered_coordinates_invalid")
    yield "WORKLOAD_STARTED", {"phase": "HEALTH_PRE_DRAW_VALIDATION"}
    for cell_index in range(14):
        for replicate_index in range(512):
            yield "HEALTH_REPLICATE_COMMIT", {
                "cell_index": cell_index,
                "replicate_index": replicate_index,
            }
    yield "HEALTH_AGGREGATE_COMPLETE", {"phase": "HEALTH_AGGREGATE"}
    for offset, (evaluation_ordinal, issue) in enumerate(fold_coordinates):
        if evaluation_ordinal != 901 + offset or not issue:
            raise AcceptedWorkloadContractError("accepted_workload_registered_fold_invalid")
        yield "HISTORICAL_FOLD_COMMIT", {
            "evaluation_ordinal": evaluation_ordinal, "issue": issue,
        }
    for scheme_index, scheme_id in enumerate(sensitivity_scheme_ids):
        if not scheme_id:
            raise AcceptedWorkloadContractError("accepted_workload_registered_scheme_invalid")
        yield "HISTORICAL_SENSITIVITY_SCHEME_COMMIT", {
            "scheme_index": scheme_index, "scheme_id": scheme_id,
        }
    yield "HISTORICAL_AGGREGATE_COMPLETE", {"phase": "HISTORICAL_AGGREGATE"}
    yield "TERMINAL_OUTCOME", {
        "phase": "TERMINAL_OUTCOME", "execution_subpath": execution_subpath,
        "decision_path": decision_path,
    }


__all__ = [
    "EVALUATED_RESUME_CHECKPOINT_COUNTS_V2",
    "EVENT_FIELDS",
    "EVENT_TYPES",
    "INPUT_BUNDLE_FIELDS",
    "REGISTERED_EXECUTION_PLAN_FIELDS",
    "REGISTERED_HISTORICAL_SCHEME_IDS",
    "RESOLVED_INPUT_FIELDS",
    "RESUME_CHECKPOINT_REFERENCE_V2_FIELDS",
    "RESUME_DELTA_V2_FIELDS",
    "RESUME_INDEX_FIELDS",
    "RESUME_JOURNAL_HEAD_V2_FIELDS",
    "ROLLING_PREFIX_ROOT_V2_FIELDS",
    "TRANSCRIPT_FIELDS",
    "AcceptedWorkloadContractError",
    "advance_resume_index",
    "build_event",
    "build_full_transcript",
    "build_resume_checkpoint_reference_v2",
    "build_resume_delta_v2",
    "build_resume_index",
    "build_resume_journal_head_v2",
    "build_resume_journal_transition",
    "build_rolling_prefix_root_v2",
    "evaluated_coordinate_sequence",
    "event_payload_digest",
    "event_payload_schema",
    "historical_settled_outcome_digest",
    "is_resume_checkpoint_count",
    "next_coordinate_for_prefix",
    "preterminal_transcript_digest",
    "producer_task_key",
    "resume_checkpoint_relative_path_v2",
    "resume_delta_relative_path_v2",
    "resume_events",
    "resume_snapshot_relative_path_v1",
    "rolling_prefix_root_digest_v2",
    "validate_event",
    "validate_event_owner_equalities",
    "validate_full_transcript",
    "validate_input_bundle",
    "validate_registered_computation_inputs",
    "validate_resume_checkpoint_reference_v2",
    "validate_resume_checkpoint_relative_path_v2",
    "validate_resume_delta_v2",
    "validate_resume_index",
    "validate_resume_journal_head_v2",
    "validate_resume_snapshot_relative_path_v1",
    "validate_resume_snapshot_v1",
    "validate_rolling_prefix_root_v2",
]
