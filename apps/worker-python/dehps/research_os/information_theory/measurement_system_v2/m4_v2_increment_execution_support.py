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
    m4_v2_domain_digest,
    validate_m4_v2_artifact_envelope,
    validate_m4_v2_nested_schema,
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
    if tuple(result) != tuple(fields) or set(result) != set(fields):
        raise AcceptedWorkloadContractError(f"{name}_fields_invalid")
    return result


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise AcceptedWorkloadContractError(f"{name}_invalid")
    return value


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
    "EVENT_FIELDS",
    "EVENT_TYPES",
    "INPUT_BUNDLE_FIELDS",
    "RESOLVED_INPUT_FIELDS",
    "RESUME_INDEX_FIELDS",
    "TRANSCRIPT_FIELDS",
    "AcceptedWorkloadContractError",
    "build_event",
    "build_full_transcript",
    "build_resume_index",
    "evaluated_coordinate_sequence",
    "event_payload_digest",
    "event_payload_schema",
    "next_coordinate_for_prefix",
    "preterminal_transcript_digest",
    "producer_task_key",
    "resume_events",
    "validate_event",
    "validate_full_transcript",
    "validate_input_bundle",
    "validate_resume_index",
]
