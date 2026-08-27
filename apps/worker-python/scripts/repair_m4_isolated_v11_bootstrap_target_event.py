from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[3]
WORKER_DIR = ROOT_DIR / "apps" / "worker-python"
SCRIPT_DIR = Path(__file__).resolve().parent
for path in (WORKER_DIR, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import build_m4_isolated_24h_challenger_v11_manifest as builder
from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import (
    AgentExecutionStatus,
    AgentRequestStatus,
    AgentRequestType,
)
from dehps.agents.roles import AgentRole
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_artifacts as artifacts,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_contract as contract,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_mainline as mainline,
)
from dehps.research_os.models import (
    CompletionClassification,
    ControlPlaneManifest,
    DependencyFacts,
    ResearchOSValidationError,
    TaskState,
    TaskStatus,
)
from dehps.research_os.repository import PostgresResearchOSRepository
from run_m4_isolated_24h_challenger_v11 import (
    LIVE_PARTIAL_FROZEN_GOAL_DIGEST,
    IsolatedChallengerRepository,
    _latest_history_identity,
    _task_context,
)

EVENT = "TARGET_PROJECTION_INPUT"
CURRENT_MANIFEST_DIGEST = (
    "47deed3ce085f6550ff757cb0cb114496dcc3afd6bb42e96612cb39d99931d66"
)
TARGET_TASK_KEY = "m4-isolated-24h-challenger-v11-target-2026099-to-2026100-projection"
TARGET_TASK_DIGEST = "a75f9502992621dd083d46c3f1614441a89a9f903430c0bdc022edbc9eea131b"
HISTORY_TASK_KEY = "m4-isolated-24h-challenger-v11-2026100-history-snapshot"
HISTORY_TASK_DIGEST = "c15be593011a6a1332f182cba0a63685cbc7f14d21648df7ebddfd398a37ee43"
FAILED_OPERATOR_REQUEST_KEY = (
    "operator-m4-isolated-v11-recover-attestation-and-deploy-v1"
)
FAILED_OPERATOR_REQUEST_ID = 725
FAILED_OPERATOR_EXECUTION_ID = 581
FAILED_TARGET_MANIFEST_DIGEST = (
    "d023e10b9ec4b62074b5c03bb8e065ae90dca84f3264856a20adc724134bf1f5"
)
FAILED_TARGET_EXECUTION_ID = (
    "55727e54bd17aa0e7347991f8d0a4a565c7b62ef4907ffda1b885565d2f78afb"
)
FAILED_TARGET_STARTED_EVENT_DIGEST = (
    "0d952aca80f10e6eec0f3e31f49d501254c3690fe1e3110bf19adfc9c3c60b3f"
)
FAILED_TARGET_EVENT_DIGEST = (
    "7324fbef2b42b2d5887de588fef6bb1992a74b9e3457b9c3ff39005383367b62"
)
FAILED_TARGET_GIT_COMMIT = "d76552684a0ad8d94373744721f4bdd1ead9df7b"
FAILED_TARGET_OPERATOR_REQUEST_KEY = (
    "operator-m4-isolated-v11-recover-target-event-run-and-deploy-v1"
)
FAILED_TARGET_OPERATOR_REQUEST_ID = 728
FAILED_TARGET_OPERATOR_EXECUTION_ID = 584
PREDECESSOR_SOURCE_DIGEST = (
    "38ea4d38e66558f30eb4c8660555ca35dd584aa3de02801fe6f6075d09ffaff1"
)
READY_REBIND_MANIFEST_DIGEST = (
    "db034176cd980ae4d4d5f7aea5475c0ac6b2e82d375c370dd43a935b16248ef6"
)
READY_REBIND_PREDECESSOR_SOURCE_DIGEST = (
    "fc1aee7ccffdb6965ae0c3e181118773ff8514edc066977d8352a7573efa9cba"
)
READY_REBIND_TARGET_TASK_DIGEST = (
    "14bf4f2ef9a14067fff075210c7b4e339d0b5e16f87c4344405a5a794896eeb1"
)
FAILED_READY_OPERATOR_REQUEST_KEY = (
    "operator-m4-isolated-v11-final-target-recovery-training-mail-deploy-v1"
)
FAILED_READY_OPERATOR_REQUEST_ID = 732
FAILED_READY_OPERATOR_EXECUTION_ID = 588


class TargetEventRecoveryError(RuntimeError):
    pass


def _task(manifest: ControlPlaneManifest, key: str, digest: str) -> Any:
    matches = [item for item in manifest.tasks if item.task_key == key]
    if len(matches) != 1 or matches[0].artifact_digest != digest:
        raise TargetEventRecoveryError("bootstrap_task_definition_changed")
    state = manifest.task_state_by_digest[digest]
    if (
        state.declared_status is not TaskStatus.DRAFT
        or state.completion_classification
        is not CompletionClassification.INTEGRATION_PENDING
        or state.superseded_by_task_digest is not None
    ):
        raise TargetEventRecoveryError("bootstrap_task_state_changed")
    return matches[0]


def build_event_extension(
    current: ControlPlaneManifest,
    *,
    source_digest: str,
    expected_manifest_digest: str = CURRENT_MANIFEST_DIGEST,
) -> ControlPlaneManifest:
    if current.artifact_digest != expected_manifest_digest:
        raise TargetEventRecoveryError("current_manifest_identity_changed")
    target = _task(current, TARGET_TASK_KEY, TARGET_TASK_DIGEST)
    _task(current, HISTORY_TASK_KEY, HISTORY_TASK_DIGEST)
    try:
        target_metric = json.loads(target.metric_contract)
        bound_source = str(target_metric["source_contract_digest"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise TargetEventRecoveryError("source_contract_identity_changed") from exc
    if bound_source != source_digest:
        raise TargetEventRecoveryError("source_contract_identity_changed")
    if EVENT in current.facts.external_events:
        raise TargetEventRecoveryError("target_projection_event_already_present")
    if current.facts.external_events != frozenset({"RESOURCE_QUIESCENT_60S"}):
        raise TargetEventRecoveryError("existing_external_events_changed")
    required = {
        contract.FREEZE_FACT,
        contract.OPERATOR_ATTESTATION_FACT,
        contract.MAIL_CONFIGURATION_FACT,
    }
    if not required.issubset(current.facts.artifacts):
        raise TargetEventRecoveryError("required_activation_facts_missing")
    if f"{TARGET_TASK_KEY}:COMPLETE" in current.facts.artifacts:
        raise TargetEventRecoveryError("target_projection_already_completed")
    incoming = replace(
        current,
        facts=DependencyFacts(
            artifacts=current.facts.artifacts,
            evidence=current.facts.evidence,
            external_events=current.facts.external_events | {EVENT},
            authorities=current.facts.authorities,
        ),
    )
    if (
        incoming.goals != current.goals
        or incoming.goal_states != current.goal_states
        or incoming.tasks != current.tasks
        or incoming.task_states != current.task_states
        or incoming.facts.artifacts != current.facts.artifacts
        or incoming.facts.evidence != current.facts.evidence
        or incoming.facts.authorities != current.facts.authorities
        or incoming.facts.external_events != current.facts.external_events | {EVENT}
    ):
        raise TargetEventRecoveryError("target_event_extension_delta_changed")
    return incoming


def validate_operator_scope(
    *, repository: AgentRequestRepository, source_digest: str, git_commit: str
) -> dict[str, int | str]:
    request_key = os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_REQUEST_KEY", "")
    try:
        decision_id = int(os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_DECISION_ID", ""))
        execution_id = int(
            os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_EXECUTION_ID", "")
        )
    except ValueError as exc:
        raise TargetEventRecoveryError("operator_identity_invalid") from exc
    if not request_key or decision_id < 1 or execution_id < 1:
        raise TargetEventRecoveryError("operator_identity_invalid")
    request = repository.get_request(request_key)
    approvals = [
        item
        for item in repository.list_decisions(request_key)
        if item.decision_code == "request_approved"
        and item.previous_status == "under_review"
        and item.new_status == "approved"
    ]
    executions = [
        item
        for item in repository.list_execution_metadata(request_key)
        if item.id == execution_id
    ]
    if (
        request.request_type is not AgentRequestType.OPERATOR_RELEASE
        or request.status is not AgentRequestStatus.EXECUTING
        or len(approvals) != 1
        or approvals[0].id != decision_id
        or approvals[0].decided_by_role is not AgentRole.REVIEWER
        or len(executions) != 1
        or executions[0].status is not AgentExecutionStatus.RUNNING
        or executions[0].environment != "production"
        or executions[0].executor_role is not AgentRole.OPERATOR
    ):
        raise TargetEventRecoveryError("operator_governance_invalid")
    checks = request.payload.get("checks")
    recovery = (
        checks.get("target_projection_event_recovery")
        if isinstance(checks, dict)
        else None
    )
    if (
        request.payload.get("commit") != git_commit
        or not isinstance(recovery, dict)
        or recovery
        != {
            "current_manifest_digest": CURRENT_MANIFEST_DIGEST,
            "event": EVENT,
            "source_contract_digest": source_digest,
            "target_task_digest": TARGET_TASK_DIGEST,
            "target_task_key": TARGET_TASK_KEY,
        }
    ):
        raise TargetEventRecoveryError("operator_scope_invalid")
    payload_sha = hashlib.sha256(
        contract.canonical_json(request.payload).encode("utf-8")
    ).hexdigest()
    if request.metadata.get("payload_sha256") != payload_sha:
        raise TargetEventRecoveryError("operator_payload_sha_changed")
    return {
        "request_id": request.id,
        "decision_id": decision_id,
        "execution_id": execution_id,
        "payload_sha256": payload_sha,
    }


def _validate_failed_operator(repository: AgentRequestRepository) -> None:
    request = repository.get_request(FAILED_OPERATOR_REQUEST_KEY)
    executions = [
        item
        for item in repository.list_execution_metadata(FAILED_OPERATOR_REQUEST_KEY)
        if item.id == FAILED_OPERATOR_EXECUTION_ID
    ]
    if (
        request.id != FAILED_OPERATOR_REQUEST_ID
        or request.status is not AgentRequestStatus.FAILED
        or len(executions) != 1
        or executions[0].status is not AgentExecutionStatus.FAILED
    ):
        raise TargetEventRecoveryError("failed_operator_identity_changed")


def build_failed_target_rebind(
    current: ControlPlaneManifest,
    *,
    source_digest: str,
    expected_manifest_digest: str = FAILED_TARGET_MANIFEST_DIGEST,
) -> ControlPlaneManifest:
    if current.artifact_digest != expected_manifest_digest:
        raise TargetEventRecoveryError("failed_target_manifest_identity_changed")
    if source_digest == PREDECESSOR_SOURCE_DIGEST:
        raise TargetEventRecoveryError("failed_target_source_not_advanced")
    if (
        len(current.goals) != 1
        or current.goals[0].artifact_digest != LIVE_PARTIAL_FROZEN_GOAL_DIGEST
        or any(
            task.goal_digest != LIVE_PARTIAL_FROZEN_GOAL_DIGEST
            for task in current.tasks
        )
    ):
        raise TargetEventRecoveryError("failed_target_goal_identity_changed")
    if EVENT not in current.facts.external_events:
        raise TargetEventRecoveryError("failed_target_event_missing")
    old_target = next(
        (item for item in current.tasks if item.task_key == TARGET_TASK_KEY), None
    )
    if old_target is None or old_target.artifact_digest != TARGET_TASK_DIGEST:
        raise TargetEventRecoveryError("failed_target_definition_changed")
    old_target_state = current.task_state_by_digest[TARGET_TASK_DIGEST]
    if (
        old_target_state.declared_status is not TaskStatus.FAILED
        or old_target_state.completion_classification
        is not CompletionClassification.INTEGRATED
        or old_target_state.superseded_by_task_digest is not None
    ):
        raise TargetEventRecoveryError("failed_target_state_changed")

    tasks = []
    states = []
    rebuilt_keys: list[str] = []
    for task in current.tasks:
        state = current.task_state_by_digest[task.artifact_digest]
        if state.declared_status is TaskStatus.COMPLETED:
            metric = json.loads(task.metric_contract)
            if metric.get("source_contract_digest") != PREDECESSOR_SOURCE_DIGEST:
                raise TargetEventRecoveryError("completed_task_source_changed")
            tasks.append(task)
            states.append(state)
            continue
        if task.task_key == TARGET_TASK_KEY:
            if state != old_target_state:
                raise TargetEventRecoveryError("failed_target_state_changed")
        elif (
            state.declared_status is not TaskStatus.DRAFT
            or state.completion_classification
            is not CompletionClassification.INTEGRATION_PENDING
            or state.superseded_by_task_digest is not None
        ):
            raise TargetEventRecoveryError("uncompleted_descendant_state_changed")
        context = _task_context(task)
        expected_payload, _ = builder.build_manifest(
            context=context,
            source_digest=source_digest,
            operator_configuration_authorized=True,
            simulation_events=False,
        )
        expected = ControlPlaneManifest.from_dict(expected_payload)
        matches = [item for item in expected.tasks if item.task_key == task.task_key]
        if len(matches) != 1:
            raise TargetEventRecoveryError("rebound_task_definition_missing")
        rebound = replace(matches[0], goal_digest=LIVE_PARTIAL_FROZEN_GOAL_DIGEST)
        tasks.append(rebound)
        states.append(
            TaskState(
                task_digest=rebound.artifact_digest,
                declared_status=TaskStatus.DRAFT,
                completion_classification=CompletionClassification.INTEGRATION_PENDING,
                superseded_by_task_digest=None,
            )
        )
        rebuilt_keys.append(task.task_key)
    if TARGET_TASK_KEY not in rebuilt_keys:
        raise TargetEventRecoveryError("failed_target_not_rebuilt")
    incoming = ControlPlaneManifest(
        goals=current.goals,
        tasks=tuple(tasks),
        goal_states=current.goal_states,
        task_states=tuple(states),
        facts=current.facts,
        schema_version=current.schema_version,
    )
    if (
        incoming.goals != current.goals
        or incoming.goal_states != current.goal_states
        or incoming.facts != current.facts
        or len(incoming.tasks) != len(current.tasks)
        or [item.task_key for item in incoming.tasks]
        != [item.task_key for item in current.tasks]
    ):
        raise TargetEventRecoveryError("failed_target_rebind_delta_changed")
    return incoming


def build_ready_source_rebind(
    current: ControlPlaneManifest,
    *,
    source_digest: str,
    expected_manifest_digest: str = READY_REBIND_MANIFEST_DIGEST,
) -> ControlPlaneManifest:
    if current.artifact_digest != expected_manifest_digest:
        raise TargetEventRecoveryError("ready_rebind_manifest_identity_changed")
    if source_digest in {
        PREDECESSOR_SOURCE_DIGEST,
        READY_REBIND_PREDECESSOR_SOURCE_DIGEST,
    }:
        raise TargetEventRecoveryError("ready_rebind_source_not_advanced")
    if (
        len(current.goals) != 1
        or current.goals[0].artifact_digest != LIVE_PARTIAL_FROZEN_GOAL_DIGEST
        or any(
            task.goal_digest != LIVE_PARTIAL_FROZEN_GOAL_DIGEST
            for task in current.tasks
        )
    ):
        raise TargetEventRecoveryError("ready_rebind_goal_identity_changed")
    target = next(
        (item for item in current.tasks if item.task_key == TARGET_TASK_KEY), None
    )
    if target is None or target.artifact_digest != READY_REBIND_TARGET_TASK_DIGEST:
        raise TargetEventRecoveryError("ready_rebind_target_definition_changed")
    if EVENT not in current.facts.external_events:
        raise TargetEventRecoveryError("ready_rebind_target_event_missing")
    target_state = current.task_state_by_digest[target.artifact_digest]
    if (
        target_state.declared_status is not TaskStatus.DRAFT
        or target_state.completion_classification
        is not CompletionClassification.INTEGRATION_PENDING
        or target_state.superseded_by_task_digest is not None
    ):
        raise TargetEventRecoveryError("ready_rebind_target_state_changed")

    tasks = []
    states = []
    for task in current.tasks:
        state = current.task_state_by_digest[task.artifact_digest]
        metric = json.loads(task.metric_contract)
        bound_source = metric.get("source_contract_digest")
        if state.declared_status is TaskStatus.COMPLETED:
            if bound_source != PREDECESSOR_SOURCE_DIGEST:
                raise TargetEventRecoveryError("ready_rebind_completed_source_changed")
            tasks.append(task)
            states.append(state)
            continue
        if (
            bound_source != READY_REBIND_PREDECESSOR_SOURCE_DIGEST
            or state.declared_status is not TaskStatus.DRAFT
            or state.completion_classification
            is not CompletionClassification.INTEGRATION_PENDING
            or state.superseded_by_task_digest is not None
        ):
            raise TargetEventRecoveryError("ready_rebind_uncompleted_state_changed")
        context = _task_context(task)
        expected_payload, _ = builder.build_manifest(
            context=context,
            source_digest=source_digest,
            operator_configuration_authorized=True,
            simulation_events=False,
        )
        expected = ControlPlaneManifest.from_dict(expected_payload)
        matches = [item for item in expected.tasks if item.task_key == task.task_key]
        if len(matches) != 1:
            raise TargetEventRecoveryError("ready_rebind_task_definition_missing")
        rebound = replace(matches[0], goal_digest=LIVE_PARTIAL_FROZEN_GOAL_DIGEST)
        tasks.append(rebound)
        states.append(
            TaskState(
                task_digest=rebound.artifact_digest,
                declared_status=TaskStatus.DRAFT,
                completion_classification=CompletionClassification.INTEGRATION_PENDING,
                superseded_by_task_digest=None,
            )
        )
    incoming = ControlPlaneManifest(
        goals=current.goals,
        tasks=tuple(tasks),
        goal_states=current.goal_states,
        task_states=tuple(states),
        facts=current.facts,
        schema_version=current.schema_version,
    )
    if (
        incoming.goals != current.goals
        or incoming.goal_states != current.goal_states
        or incoming.facts != current.facts
        or [item.task_key for item in incoming.tasks]
        != [item.task_key for item in current.tasks]
    ):
        raise TargetEventRecoveryError("ready_rebind_delta_changed")
    return incoming


def validate_failed_target_events(
    events: Sequence[Mapping[str, Any]],
    registrations: Sequence[Mapping[str, Any]],
) -> None:
    if len(events) != 2 or registrations:
        raise TargetEventRecoveryError("failed_target_event_or_artifact_count_changed")
    by_type = {str(item.get("event_type")): item for item in events}
    if set(by_type) != {"started", "failed"}:
        raise TargetEventRecoveryError("failed_target_event_types_changed")
    started = by_type["started"]
    failed = by_type["failed"]
    if (
        started.get("event_digest") != FAILED_TARGET_STARTED_EVENT_DIGEST
        or failed.get("event_digest") != FAILED_TARGET_EVENT_DIGEST
        or started.get("execution_id") != FAILED_TARGET_EXECUTION_ID
        or failed.get("execution_id") != FAILED_TARGET_EXECUTION_ID
        or started.get("task_digest") != TARGET_TASK_DIGEST
        or failed.get("task_digest") != TARGET_TASK_DIGEST
        or started.get("task_key") != TARGET_TASK_KEY
        or failed.get("task_key") != TARGET_TASK_KEY
        or started.get("sequence") != 0
        or failed.get("sequence") != 1
        or dict(started.get("payload") or ())
        != {
            "input_artifact_digests": [PREDECESSOR_SOURCE_DIGEST],
            "git_commit": FAILED_TARGET_GIT_COMMIT,
        }
        or dict(failed.get("payload") or ())
        != {
            "error": "artifact_type_body_overrides_common_field",
            "git_commit": FAILED_TARGET_GIT_COMMIT,
        }
    ):
        raise TargetEventRecoveryError("failed_target_event_identity_changed")


def _validate_failed_target_operator(repository: AgentRequestRepository) -> None:
    request = repository.get_request(FAILED_TARGET_OPERATOR_REQUEST_KEY)
    executions = [
        item
        for item in repository.list_execution_metadata(
            FAILED_TARGET_OPERATOR_REQUEST_KEY
        )
        if item.id == FAILED_TARGET_OPERATOR_EXECUTION_ID
    ]
    if (
        request.id != FAILED_TARGET_OPERATOR_REQUEST_ID
        or request.status is not AgentRequestStatus.FAILED
        or len(executions) != 1
        or executions[0].status is not AgentExecutionStatus.FAILED
    ):
        raise TargetEventRecoveryError("failed_target_operator_identity_changed")


def validate_failed_target_operator_scope(
    *, repository: AgentRequestRepository, source_digest: str, git_commit: str
) -> dict[str, int | str]:
    governance = validate_operator_scope_common(repository=repository)
    request = governance["request"]
    checks = request.payload.get("checks")
    recovery = (
        checks.get("target_projection_failure_recovery")
        if isinstance(checks, dict)
        else None
    )
    if request.payload.get("commit") != git_commit or recovery != {
        "current_manifest_digest": FAILED_TARGET_MANIFEST_DIGEST,
        "failed_execution_id": FAILED_TARGET_EXECUTION_ID,
        "failed_task_digest": TARGET_TASK_DIGEST,
        "failed_task_key": TARGET_TASK_KEY,
        "predecessor_source_contract_digest": PREDECESSOR_SOURCE_DIGEST,
        "source_contract_digest": source_digest,
    }:
        raise TargetEventRecoveryError("failed_target_operator_scope_invalid")
    payload_sha = hashlib.sha256(
        contract.canonical_json(request.payload).encode("utf-8")
    ).hexdigest()
    if request.metadata.get("payload_sha256") != payload_sha:
        raise TargetEventRecoveryError("operator_payload_sha_changed")
    return {
        "request_id": request.id,
        "decision_id": governance["decision_id"],
        "execution_id": governance["execution_id"],
        "payload_sha256": payload_sha,
    }


def validate_operator_scope_common(
    *, repository: AgentRequestRepository
) -> dict[str, Any]:
    request_key = os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_REQUEST_KEY", "")
    try:
        decision_id = int(os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_DECISION_ID", ""))
        execution_id = int(
            os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_EXECUTION_ID", "")
        )
    except ValueError as exc:
        raise TargetEventRecoveryError("operator_identity_invalid") from exc
    if not request_key or decision_id < 1 or execution_id < 1:
        raise TargetEventRecoveryError("operator_identity_invalid")
    request = repository.get_request(request_key)
    approvals = [
        item
        for item in repository.list_decisions(request_key)
        if item.decision_code == "request_approved"
        and item.previous_status == "under_review"
        and item.new_status == "approved"
    ]
    executions = [
        item
        for item in repository.list_execution_metadata(request_key)
        if item.id == execution_id
    ]
    if (
        request.request_type is not AgentRequestType.OPERATOR_RELEASE
        or request.status is not AgentRequestStatus.EXECUTING
        or len(approvals) != 1
        or approvals[0].id != decision_id
        or approvals[0].decided_by_role is not AgentRole.REVIEWER
        or len(executions) != 1
        or executions[0].status is not AgentExecutionStatus.RUNNING
        or executions[0].environment != "production"
        or executions[0].executor_role is not AgentRole.OPERATOR
    ):
        raise TargetEventRecoveryError("operator_governance_invalid")
    return {
        "request": request,
        "decision_id": decision_id,
        "execution_id": execution_id,
    }


class FailedTargetRecoveryRepository(IsolatedChallengerRepository):
    def __init__(self, *, context: Mapping[str, str], source_digest: str) -> None:
        super().__init__(context=context, source_digest=source_digest)
        self._failed_target_rebind_gate: dict[str, Any] | None = None

    def _verify_exact_transition(self, incoming: ControlPlaneManifest) -> None:
        gate = self._failed_target_rebind_gate
        if gate is None:
            return super()._verify_exact_transition(incoming)
        current = self.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        expected = build_failed_target_rebind(current, source_digest=self.source_digest)
        if (
            gate.get("consumed") is not False
            or gate.get("current_manifest_digest") != current.artifact_digest
            or gate.get("incoming_manifest_digest") != incoming.artifact_digest
            or expected.to_dict(include_digest=True)
            != incoming.to_dict(include_digest=True)
        ):
            raise ResearchOSValidationError("failed_target_rebind_gate_changed")
        gate["consumed"] = True

    def _verify_mainline_completion_records(
        self,
        cursor: Any,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
        m4_v2_lifecycle_verified: bool = False,
    ) -> None:
        gate = self._failed_target_rebind_gate
        if gate is None:
            return super()._verify_mainline_completion_records(
                cursor,
                control_plane_key=control_plane_key,
                manifest=manifest,
                m4_v2_lifecycle_verified=m4_v2_lifecycle_verified,
            )
        if (
            control_plane_key != contract.CONTROL_PLANE_KEY
            or gate.get("consumed") is not True
            or gate.get("incoming_manifest_digest") != manifest.artifact_digest
        ):
            raise ResearchOSValidationError(
                "failed_target_rebind_completion_gate_changed"
            )
        PostgresResearchOSRepository._verify_mainline_completion_records(
            cursor,
            control_plane_key=control_plane_key,
            manifest=manifest,
            m4_v2_lifecycle_verified=m4_v2_lifecycle_verified,
        )

    def apply_failed_target_rebind(self, incoming: ControlPlaneManifest) -> Any:
        if self._failed_target_rebind_gate is not None:
            raise TargetEventRecoveryError("failed_target_rebind_gate_reentrant")
        current = self.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        expected = build_failed_target_rebind(current, source_digest=self.source_digest)
        if incoming.to_dict(include_digest=True) != expected.to_dict(
            include_digest=True
        ):
            raise TargetEventRecoveryError("failed_target_rebind_manifest_changed")
        self._failed_target_rebind_gate = {
            "consumed": False,
            "current_manifest_digest": current.artifact_digest,
            "incoming_manifest_digest": incoming.artifact_digest,
        }
        try:
            result = self.import_manifest(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                payload=incoming.to_dict(include_digest=True),
                source="m4-isolated-v11-target-projection-failure-source-rebind-v1",
            )
            if self._failed_target_rebind_gate.get("consumed") is not True:
                raise TargetEventRecoveryError("failed_target_rebind_gate_not_consumed")
            return result
        finally:
            self._failed_target_rebind_gate = None


def _validate_failed_ready_operator(repository: AgentRequestRepository) -> None:
    request = repository.get_request(FAILED_READY_OPERATOR_REQUEST_KEY)
    executions = [
        item
        for item in repository.list_execution_metadata(
            FAILED_READY_OPERATOR_REQUEST_KEY
        )
        if item.id == FAILED_READY_OPERATOR_EXECUTION_ID
    ]
    if (
        request.id != FAILED_READY_OPERATOR_REQUEST_ID
        or request.status is not AgentRequestStatus.FAILED
        or len(executions) != 1
        or executions[0].status is not AgentExecutionStatus.FAILED
    ):
        raise TargetEventRecoveryError("failed_ready_operator_identity_changed")


def validate_ready_source_operator_scope(
    *, repository: AgentRequestRepository, source_digest: str, git_commit: str
) -> dict[str, int | str]:
    governance = validate_operator_scope_common(repository=repository)
    request = governance["request"]
    checks = request.payload.get("checks")
    recovery = (
        checks.get("ready_lineage_source_rebind") if isinstance(checks, dict) else None
    )
    if request.payload.get("commit") != git_commit or recovery != {
        "current_manifest_digest": READY_REBIND_MANIFEST_DIGEST,
        "frozen_goal_digest": LIVE_PARTIAL_FROZEN_GOAL_DIGEST,
        "predecessor_source_contract_digest": (READY_REBIND_PREDECESSOR_SOURCE_DIGEST),
        "source_contract_digest": source_digest,
        "target_task_digest": READY_REBIND_TARGET_TASK_DIGEST,
        "target_task_key": TARGET_TASK_KEY,
    }:
        raise TargetEventRecoveryError("ready_rebind_operator_scope_invalid")
    payload_sha = hashlib.sha256(
        contract.canonical_json(request.payload).encode("utf-8")
    ).hexdigest()
    if request.metadata.get("payload_sha256") != payload_sha:
        raise TargetEventRecoveryError("operator_payload_sha_changed")
    return {
        "request_id": request.id,
        "decision_id": governance["decision_id"],
        "execution_id": governance["execution_id"],
        "payload_sha256": payload_sha,
    }


class ReadySourceRecoveryRepository(IsolatedChallengerRepository):
    def __init__(self, *, context: Mapping[str, str], source_digest: str) -> None:
        super().__init__(context=context, source_digest=source_digest)
        self._ready_source_rebind_gate: dict[str, Any] | None = None

    def _verify_exact_transition(self, incoming: ControlPlaneManifest) -> None:
        gate = self._ready_source_rebind_gate
        if gate is None:
            return super()._verify_exact_transition(incoming)
        current = self.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        expected = build_ready_source_rebind(current, source_digest=self.source_digest)
        if (
            gate.get("consumed") is not False
            or gate.get("current_manifest_digest") != current.artifact_digest
            or gate.get("incoming_manifest_digest") != incoming.artifact_digest
            or expected.to_dict(include_digest=True)
            != incoming.to_dict(include_digest=True)
        ):
            raise ResearchOSValidationError("ready_source_rebind_gate_changed")
        gate["consumed"] = True

    def _verify_mainline_completion_records(
        self,
        cursor: Any,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
        m4_v2_lifecycle_verified: bool = False,
    ) -> None:
        gate = self._ready_source_rebind_gate
        if gate is None:
            return super()._verify_mainline_completion_records(
                cursor,
                control_plane_key=control_plane_key,
                manifest=manifest,
                m4_v2_lifecycle_verified=m4_v2_lifecycle_verified,
            )
        if (
            control_plane_key != contract.CONTROL_PLANE_KEY
            or gate.get("consumed") is not True
            or gate.get("incoming_manifest_digest") != manifest.artifact_digest
        ):
            raise ResearchOSValidationError(
                "ready_source_rebind_completion_gate_changed"
            )
        PostgresResearchOSRepository._verify_mainline_completion_records(
            cursor,
            control_plane_key=control_plane_key,
            manifest=manifest,
            m4_v2_lifecycle_verified=m4_v2_lifecycle_verified,
        )

    def apply_ready_source_rebind(self, incoming: ControlPlaneManifest) -> Any:
        if self._ready_source_rebind_gate is not None:
            raise TargetEventRecoveryError("ready_source_rebind_gate_reentrant")
        current = self.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        expected = build_ready_source_rebind(current, source_digest=self.source_digest)
        if incoming.to_dict(include_digest=True) != expected.to_dict(
            include_digest=True
        ):
            raise TargetEventRecoveryError("ready_source_rebind_manifest_changed")
        self._ready_source_rebind_gate = {
            "consumed": False,
            "current_manifest_digest": current.artifact_digest,
            "incoming_manifest_digest": incoming.artifact_digest,
        }
        try:
            result = self.import_manifest(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                payload=incoming.to_dict(include_digest=True),
                source="m4-isolated-v11-ready-lineage-source-rebind-v1",
            )
            if self._ready_source_rebind_gate.get("consumed") is not True:
                raise TargetEventRecoveryError("ready_source_rebind_gate_not_consumed")
            return result
        finally:
            self._ready_source_rebind_gate = None


def run(*, apply: bool) -> dict[str, Any]:
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise TargetEventRecoveryError("dirty_worktree")
    git_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True
    ).strip()
    source = artifacts.load_source_contract(root_dir=ROOT_DIR)
    source_digest = str(source["artifact_digest"])
    source_issue, source_date = _latest_history_identity()
    context = contract.render_context(
        source_max_issue=source_issue,
        source_max_draw_date=source_date,
    )
    repository = IsolatedChallengerRepository(
        context=context, source_digest=source_digest
    )
    current = repository.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    incoming = build_event_extension(current, source_digest=source_digest)
    agent_repository = AgentRequestRepository()
    _validate_failed_operator(agent_repository)
    governance = validate_operator_scope(
        repository=agent_repository,
        source_digest=source_digest,
        git_commit=git_commit,
    )
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        batch_count = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.registration_batches"
            ).fetchone()[0]
        )
        sent_count = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.delivery_ledger "
                "WHERE state='SENT'"
            ).fetchone()[0]
        )
    if batch_count != 0 or sent_count != 0:
        raise TargetEventRecoveryError("zero_workload_or_delivery_preflight_changed")
    imported = (
        repository.import_extension(incoming.to_dict(include_digest=True))
        if apply
        else None
    )
    return {
        "schema_version": "dehps-m4-isolated-v11-target-event-recovery.v1",
        "status": "EVENT_IMPORTED" if apply else "DRY_RUN_VERIFIED",
        "apply": apply,
        "current_manifest_digest": current.artifact_digest,
        "incoming_manifest_digest": incoming.artifact_digest,
        "event": EVENT,
        "target_task_key": TARGET_TASK_KEY,
        "target_task_digest": TARGET_TASK_DIGEST,
        "governance": governance,
        "import_result": None if imported is None else str(imported),
        "definitions_changed": False,
        "states_changed": False,
        "artifact_facts_changed": False,
        "sole_external_event_delta": True,
        "workloads": 0,
        "smtp_calls": 0,
        "external_sends": 0,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
    }


def run_failed_target_rebind(*, apply: bool) -> dict[str, Any]:
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise TargetEventRecoveryError("dirty_worktree")
    git_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True
    ).strip()
    source = artifacts.load_source_contract(root_dir=ROOT_DIR)
    source_digest = str(source["artifact_digest"])
    source_issue, source_date = _latest_history_identity()
    context = contract.render_context(
        source_max_issue=source_issue, source_max_draw_date=source_date
    )
    repository = FailedTargetRecoveryRepository(
        context=context, source_digest=source_digest
    )
    current = repository.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    incoming = build_failed_target_rebind(current, source_digest=source_digest)
    events = repository.list_mainline_execution_events(
        control_plane_key=contract.CONTROL_PLANE_KEY,
        task_key=TARGET_TASK_KEY,
    )
    registrations = repository.list_mainline_artifacts(
        control_plane_key=contract.CONTROL_PLANE_KEY,
        execution_id=FAILED_TARGET_EXECUTION_ID,
    )
    validate_failed_target_events(events, registrations)
    agent_repository = AgentRequestRepository()
    _validate_failed_target_operator(agent_repository)
    governance = validate_failed_target_operator_scope(
        repository=agent_repository,
        source_digest=source_digest,
        git_commit=git_commit,
    )
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        batch_count = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.registration_batches"
            ).fetchone()[0]
        )
        sent_count = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.delivery_ledger "
                "WHERE state='SENT'"
            ).fetchone()[0]
        )
    if batch_count != 0 or sent_count != 0:
        raise TargetEventRecoveryError("zero_workload_or_delivery_preflight_changed")
    registered_source = None
    imported = None
    if apply:
        registered_source = mainline.register_input_artifact(
            repository=repository,
            payload=source,
            git_commit=git_commit,
            source_path=contract.SOURCE_CONTRACT_PATH,
            content_bytes=(ROOT_DIR / contract.SOURCE_CONTRACT_PATH).read_bytes(),
        )
        imported = repository.apply_failed_target_rebind(incoming)
    new_target = next(
        item for item in incoming.tasks if item.task_key == TARGET_TASK_KEY
    )
    completed_count = sum(
        state.declared_status is TaskStatus.COMPLETED for state in current.task_states
    )
    return {
        "schema_version": "dehps-m4-isolated-v11-failed-target-source-rebind.v1",
        "status": "RECOVERED_TO_READY_SOURCE_REBOUND" if apply else "DRY_RUN_VERIFIED",
        "apply": apply,
        "current_manifest_digest": current.artifact_digest,
        "incoming_manifest_digest": incoming.artifact_digest,
        "predecessor_source_contract_digest": PREDECESSOR_SOURCE_DIGEST,
        "source_contract_digest": source_digest,
        "source_contract_registered": (
            None if registered_source is None else registered_source["artifact_digest"]
        ),
        "target_task_key": TARGET_TASK_KEY,
        "failed_target_task_digest": TARGET_TASK_DIGEST,
        "rebound_target_task_digest": new_target.artifact_digest,
        "failed_execution_id": FAILED_TARGET_EXECUTION_ID,
        "failed_execution_preserved": True,
        "completed_historical_task_count": completed_count,
        "rebound_uncompleted_task_count": len(current.tasks) - completed_count,
        "target_event_preserved": EVENT in incoming.facts.external_events,
        "facts_changed": False,
        "goals_changed": False,
        "governance": governance,
        "import_result": None if imported is None else str(imported),
        "workloads": 0,
        "smtp_calls": 0,
        "external_sends": 0,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
    }


def run_ready_source_rebind(*, apply: bool) -> dict[str, Any]:
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise TargetEventRecoveryError("dirty_worktree")
    git_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True
    ).strip()
    source = artifacts.load_source_contract(root_dir=ROOT_DIR)
    source_digest = str(source["artifact_digest"])
    source_issue, source_date = _latest_history_identity()
    context = contract.render_context(
        source_max_issue=source_issue, source_max_draw_date=source_date
    )
    repository = ReadySourceRecoveryRepository(
        context=context, source_digest=source_digest
    )
    current = repository.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    incoming = build_ready_source_rebind(current, source_digest=source_digest)
    agent_repository = AgentRequestRepository()
    _validate_failed_ready_operator(agent_repository)
    governance = validate_ready_source_operator_scope(
        repository=agent_repository,
        source_digest=source_digest,
        git_commit=git_commit,
    )
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        batch_count = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.registration_batches"
            ).fetchone()[0]
        )
        sent_count = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.delivery_ledger "
                "WHERE state='SENT'"
            ).fetchone()[0]
        )
    if batch_count != 0 or sent_count != 0:
        raise TargetEventRecoveryError("zero_workload_or_delivery_preflight_changed")
    registered_source = None
    imported = None
    if apply:
        registered_source = mainline.register_input_artifact(
            repository=repository,
            payload=source,
            git_commit=git_commit,
            source_path=contract.SOURCE_CONTRACT_PATH,
            content_bytes=(ROOT_DIR / contract.SOURCE_CONTRACT_PATH).read_bytes(),
        )
        imported = repository.apply_ready_source_rebind(incoming)
    target = next(item for item in incoming.tasks if item.task_key == TARGET_TASK_KEY)
    completed_count = sum(
        state.declared_status is TaskStatus.COMPLETED for state in current.task_states
    )
    return {
        "schema_version": "dehps-m4-isolated-v11-ready-source-rebind.v1",
        "status": "READY_LINEAGE_SOURCE_REBOUND" if apply else "DRY_RUN_VERIFIED",
        "apply": apply,
        "current_manifest_digest": current.artifact_digest,
        "incoming_manifest_digest": incoming.artifact_digest,
        "frozen_goal_digest": LIVE_PARTIAL_FROZEN_GOAL_DIGEST,
        "predecessor_source_contract_digest": (READY_REBIND_PREDECESSOR_SOURCE_DIGEST),
        "source_contract_digest": source_digest,
        "source_contract_registered": (
            None if registered_source is None else registered_source["artifact_digest"]
        ),
        "target_task_key": TARGET_TASK_KEY,
        "predecessor_target_task_digest": READY_REBIND_TARGET_TASK_DIGEST,
        "rebound_target_task_digest": target.artifact_digest,
        "completed_historical_task_count": completed_count,
        "rebound_uncompleted_task_count": len(current.tasks) - completed_count,
        "target_event_preserved": EVENT in incoming.facts.external_events,
        "facts_changed": False,
        "goals_changed": False,
        "failed_execution_preserved": True,
        "governance": governance,
        "import_result": None if imported is None else str(imported),
        "workloads": 0,
        "smtp_calls": 0,
        "external_sends": 0,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("repair", "recover-failed-target", "rebind-ready-lineage"),
    )
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "repair":
        result = run(apply=bool(args.apply))
    elif args.command == "recover-failed-target":
        result = run_failed_target_rebind(apply=bool(args.apply))
    else:
        result = run_ready_source_rebind(apply=bool(args.apply))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
