from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from .branch_decision import (
    validate_marginal_static_branch_decision,
    validate_marginal_static_branch_decision_replay,
)
from .m4_v2_increment_execution_support import (
    AcceptedWorkloadContractError,
    build_event,
    event_payload_digest,
    event_payload_schema,
    preterminal_transcript_digest,
    producer_task_key,
    resume_events,
    validate_input_bundle,
)
from .temporal_marginal_increment import validate_temporal_branch_replay
from .temporal_probability_capsule import validate_probability_capsule_index

JOINT_BRANCH_ID = "JOINT_RESIDUAL_INCREMENT"
_COMPUTATION_FIELDS = (
    "pre_draw_terminal_outcome_or_null",
    "health_replicate_evidence_in_order",
    "health_aggregate_body_or_null",
    "historical_fold_commits_in_order",
    "historical_sensitivity_summaries_in_order",
    "historical_aggregate_body_or_null",
    "terminal_outcome_without_preterminal",
)


def _validate_accepted_parents_and_capsule(bundle: Mapping[str, Any]) -> None:
    resolved = bundle["resolved_inputs"]
    decisions = resolved["ordered_parent_decision_envelopes"]
    replays = resolved["ordered_parent_replay_envelopes"]
    if len(decisions) != 2 or len(replays) != 2:
        raise AcceptedWorkloadContractError("joint_parent_cardinality_invalid")
    try:
        marginal_decision = validate_marginal_static_branch_decision(
            decisions[0]
        ).to_dict()
        marginal_replay = validate_marginal_static_branch_decision_replay(
            replays[0], decision=marginal_decision
        ).to_dict()
        temporal_replay = validate_temporal_branch_replay(replays[1])
    except ValueError as exc:
        raise AcceptedWorkloadContractError("joint_parent_identity_invalid") from exc
    validated_decisions = (marginal_decision, decisions[1])
    validated_replays = (marginal_replay, temporal_replay)
    if any(
        decision["artifact_digest"] != expected
        or decision["body"]["accepted_for_downstream_baseline"] is not True
        for decision, expected in zip(
            validated_decisions,
            bundle["ordered_parent_decision_artifact_digests"],
            strict=True,
        )
    ) or any(
        replay["artifact_digest"] != expected
        or replay["body"]["workload_rerun"] is not False
        or replay["body"]["replay_status"] != "REGISTERED_REPLAY_VERIFIED"
        for replay, expected in zip(
            validated_replays,
            bundle["ordered_parent_replay_artifact_digests"],
            strict=True,
        )
    ) or any(
        replay["body"]["decision_artifact_digest"] != decision["artifact_digest"]
        for replay, decision in zip(
            validated_replays, validated_decisions, strict=True
        )
    ):
        raise AcceptedWorkloadContractError("joint_parent_acceptance_invalid")
    support = resolved["accepted_support_model_envelope"]
    if support.get("schema_version") != (
        "dehps-m4-v2-temporal-marginal-increment-candidate-model.v3"
    ) or support["artifact_digest"] != decisions[-1]["body"].get(
        "accepted_model_artifact_digest"
    ):
        raise AcceptedWorkloadContractError("joint_temporal_candidate_v3_required")
    body = support.get("body")
    if not isinstance(body, Mapping):
        raise AcceptedWorkloadContractError("joint_temporal_candidate_body_missing")
    capsule = validate_probability_capsule_index(body.get("probability_capsule_index", {}))
    if (
        body.get("probability_capsule_index_digest") != capsule["index_digest"]
        or body.get("probability_capsule_evaluator_contract_digest")
        != capsule["evaluator_contract_digest"]
        or body.get("source_contract_digest")
        != capsule["producer_source_contract_digest"]
    ):
        raise AcceptedWorkloadContractError("joint_temporal_capsule_identity_mismatch")


def _computation(bundle: Mapping[str, Any]) -> dict[str, Any]:
    plan = bundle["resolved_inputs"]["historical_execution_plan_envelope"].get("body")
    if not isinstance(plan, Mapping) or "deterministic_event_payloads" in plan:
        raise AcceptedWorkloadContractError("joint_precomputed_event_stream_forbidden")
    value = plan.get("accepted_workload_computation")
    if not isinstance(value, Mapping) or tuple(value) != _COMPUTATION_FIELDS:
        raise AcceptedWorkloadContractError("joint_registered_computation_missing")
    result = dict(value)
    for field in (
        "health_replicate_evidence_in_order", "historical_fold_commits_in_order",
        "historical_sensitivity_summaries_in_order",
    ):
        if not isinstance(result[field], list):
            raise AcceptedWorkloadContractError("joint_registered_computation_invalid")
    return result


def _started_payload(bundle: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "input_bundle_digest": bundle["input_bundle_digest"],
        "producer_task_key": producer_task_key(JOINT_BRANCH_ID),
        "producer_execution_id": bundle["producer_execution_id"],
        "branch_id": JOINT_BRANCH_ID,
        "source_contract_digest": bundle["source_contract_artifact_digest"],
        "preregistration_artifact_digest": bundle["preregistration_artifact_digest"],
        "parent_decision_artifact_digests_in_order": list(
            bundle["ordered_parent_decision_artifact_digests"]
        ),
        "parent_replay_artifact_digests_in_order": list(
            bundle["ordered_parent_replay_artifact_digests"]
        ),
        "scientific_execution_started": True,
        "start_phase": "HEALTH_PRE_DRAW_VALIDATION",
        "rng_draw_count": 0,
        "synthetic_replicate_count": 0,
        "historical_fold_count": 0,
        "bootstrap_resample_count": 0,
    }


def _coordinate(event_type: str, payload: Mapping[str, Any], index: int) -> dict[str, Any]:
    if event_type == "WORKLOAD_STARTED":
        return {"phase": "HEALTH_PRE_DRAW_VALIDATION"}
    if event_type == "HEALTH_REPLICATE_COMMIT":
        return {"cell_index": index // 512, "replicate_index": index % 512}
    if event_type == "HEALTH_AGGREGATE_COMPLETE":
        return {"phase": "HEALTH_AGGREGATE"}
    if event_type == "HISTORICAL_FOLD_COMMIT":
        return {"evaluation_ordinal": payload["evaluation_ordinal"], "issue": payload["issue"]}
    if event_type == "HISTORICAL_SENSITIVITY_SCHEME_COMMIT":
        return {"scheme_index": index, "scheme_id": payload["scheme_id"]}
    if event_type == "HISTORICAL_AGGREGATE_COMPLETE":
        return {"phase": "HISTORICAL_AGGREGATE"}
    return {
        "phase": "TERMINAL_OUTCOME", "execution_subpath": payload["execution_subpath"],
        "decision_path": payload["decision_path"],
    }


def _terminal_payload(
    *, bundle: Mapping[str, Any], events: Sequence[Mapping[str, Any]], raw: Mapping[str, Any]
) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or "preterminal_transcript_digest" in raw:
        raise AcceptedWorkloadContractError("joint_terminal_input_invalid")
    payload = dict(raw)
    payload["preterminal_transcript_digest"] = preterminal_transcript_digest(
        branch_id=JOINT_BRANCH_ID, input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=bundle["producer_execution_id"],
        execution_subpath=payload["execution_subpath"], decision_path=payload["decision_path"],
        ordered_preterminal_event_digests=[event["event_digest"] for event in events],
    )
    return payload


def _iter_events(bundle: Mapping[str, Any], computation: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    def append(event_type: str, payload: Mapping[str, Any], coordinate_index: int = 0) -> dict[str, Any]:
        event = build_event(
            branch_id=JOINT_BRANCH_ID, input_bundle_digest=bundle["input_bundle_digest"],
            producer_execution_id=bundle["producer_execution_id"], event_index=len(events),
            event_type=event_type, coordinate_key=_coordinate(event_type, payload, coordinate_index),
            payload_schema=event_payload_schema(branch_id=JOINT_BRANCH_ID, event_type=event_type),
            payload=payload,
            payload_digest=event_payload_digest(
                branch_id=JOINT_BRANCH_ID, event_type=event_type, payload=payload
            ),
            previous_event_digest_or_null=(events[-1]["event_digest"] if events else None),
        )
        events.append(event)
        return event

    yield append("WORKLOAD_STARTED", _started_payload(bundle))
    early = computation["pre_draw_terminal_outcome_or_null"]
    if early is not None:
        yield append("TERMINAL_OUTCOME", _terminal_payload(bundle=bundle, events=events, raw=early))
        return
    for index, payload in enumerate(computation["health_replicate_evidence_in_order"]):
        yield append("HEALTH_REPLICATE_COMMIT", payload, index)
    if computation["health_aggregate_body_or_null"] is not None:
        yield append("HEALTH_AGGREGATE_COMPLETE", computation["health_aggregate_body_or_null"])
    for payload in computation["historical_fold_commits_in_order"]:
        yield append("HISTORICAL_FOLD_COMMIT", payload)
    for index, payload in enumerate(computation["historical_sensitivity_summaries_in_order"]):
        yield append("HISTORICAL_SENSITIVITY_SCHEME_COMMIT", payload, index)
    if computation["historical_aggregate_body_or_null"] is not None:
        yield append("HISTORICAL_AGGREGATE_COMPLETE", computation["historical_aggregate_body_or_null"])
    yield append(
        "TERMINAL_OUTCOME",
        _terminal_payload(
            bundle=bundle, events=events, raw=computation["terminal_outcome_without_preterminal"]
        ),
    )


def iter_joint_residual_increment_accepted_parent_events(
    input_bundle: Mapping[str, Any], *, resume_index: Mapping[str, Any] | None = None,
) -> Iterator[Mapping[str, Any]]:
    bundle = validate_input_bundle(input_bundle, branch_id=JOINT_BRANCH_ID)
    _validate_accepted_parents_and_capsule(bundle)
    computation = _computation(bundle)
    prefix = resume_events(
        branch_id=JOINT_BRANCH_ID, input_bundle_digest=bundle["input_bundle_digest"],
        producer_execution_id=bundle["producer_execution_id"], resume_index=resume_index,
    )
    produced = 0
    for index, event in enumerate(_iter_events(bundle, computation)):
        produced = index + 1
        if index < len(prefix):
            if event != prefix[index]:
                raise AcceptedWorkloadContractError("joint_resume_event_rewrite")
            continue
        yield event
    if len(prefix) > produced:
        raise AcceptedWorkloadContractError("joint_resume_prefix_too_long")


__all__ = ["iter_joint_residual_increment_accepted_parent_events"]
