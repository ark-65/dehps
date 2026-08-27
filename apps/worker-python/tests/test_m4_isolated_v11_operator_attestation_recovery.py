from __future__ import annotations

import hashlib
from dataclasses import replace
from types import SimpleNamespace

import pytest
from dehps.agents.requests import (
    AgentExecutionStatus,
    AgentRequestStatus,
    AgentRequestType,
)
from dehps.agents.roles import AgentRole
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_contract as contract,
)
from dehps.research_os.models import CompletionClassification, TaskStatus

from scripts import recover_m4_isolated_v11_operator_attestation as recovery
from scripts import run_m4_isolated_24h_challenger_v11 as runner


def _failed_manifest():
    context = contract.render_context(
        source_max_issue="2026099",
        source_max_draw_date="2026-08-27",
        target_issue="2026100",
        target_draw_date="2026-08-30",
        projection_time="2026-08-28T00:27:06.982677+08:00",
    )
    payload, _ = runner.builder.build_manifest(
        context=context,
        source_digest="38ea4d38e66558f30eb4c8660555ca35dd584aa3de02801fe6f6075d09ffaff1",
        operator_configuration_authorized=True,
        simulation_events=False,
    )
    manifest = runner.ControlPlaneManifest.from_dict(payload)
    task = next(item for item in manifest.tasks if item.task_key == recovery.TASK_KEY)
    states = tuple(
        replace(
            state,
            declared_status=TaskStatus.FAILED,
            completion_classification=CompletionClassification.INTEGRATED,
        )
        if state.task_digest == task.artifact_digest
        else state
        for state in manifest.task_states
    )
    return replace(manifest, task_states=states)


def _events():
    common = {
        "execution_id": recovery.FAILED_EXECUTION_ID,
        "task_digest": recovery.TASK_DIGEST,
        "task_key": recovery.TASK_KEY,
    }
    return (
        {
            **common,
            "event_digest": recovery.STARTED_EVENT_DIGEST,
            "event_type": "started",
            "sequence": 0,
            "payload": (
                ("input_artifact_digests", ("source",)),
                ("git_commit", recovery.FAILED_GIT_COMMIT),
            ),
        },
        {
            **common,
            "event_digest": recovery.FAILED_EVENT_DIGEST,
            "event_type": "failed",
            "sequence": 1,
            "payload": (
                ("error", "operator_attestation_scope_invalid"),
                ("git_commit", recovery.FAILED_GIT_COMMIT),
            ),
        },
    )


def test_recovery_manifest_changes_only_failed_state() -> None:
    current = _failed_manifest()
    incoming = recovery.recovery_manifest(
        current, expected_manifest_digest=current.artifact_digest
    )
    before = current.task_state_by_digest
    after = incoming.task_state_by_digest
    assert current.tasks == incoming.tasks
    assert current.goals == incoming.goals
    assert current.facts == incoming.facts
    assert [key for key in before if before[key] != after[key]] == [
        recovery.TASK_DIGEST
    ]
    state = after[recovery.TASK_DIGEST]
    assert state.declared_status is TaskStatus.DRAFT
    assert (
        state.completion_classification is CompletionClassification.INTEGRATION_PENDING
    )


def test_recovery_rejects_nonfailed_task() -> None:
    current = _failed_manifest()
    states = tuple(
        replace(state, declared_status=TaskStatus.RUNNING)
        if state.task_digest == recovery.TASK_DIGEST
        else state
        for state in current.task_states
    )
    with pytest.raises(recovery.AttestationRecoveryError, match="failed_task_state"):
        changed = replace(current, task_states=states)
        recovery.recovery_manifest(
            changed, expected_manifest_digest=changed.artifact_digest
        )


def test_failed_event_chain_is_exact() -> None:
    recovery.validate_failed_events(_events(), ())
    bad = list(_events())
    bad[1] = {**bad[1], "payload": (("error", "other"),)}
    with pytest.raises(recovery.AttestationRecoveryError, match="payload"):
        recovery.validate_failed_events(bad, ())
    with pytest.raises(recovery.AttestationRecoveryError, match="artifact"):
        recovery.validate_failed_events(_events(), ({"artifact_digest": "bad"},))


def test_new_commit_derives_distinct_execution_id() -> None:
    old = {
        "schema": recovery.MAINLINE_EXECUTION_SCHEMA,
        "control_plane_key": contract.CONTROL_PLANE_KEY,
        "task_digest": recovery.TASK_DIGEST,
        "capability": "M4IsolatedOperatorAttestationCapabilityV11",
        "input_artifact_digests": (
            "38ea4d38e66558f30eb4c8660555ca35dd584aa3de02801fe6f6075d09ffaff1",
        ),
        "git_commit": recovery.FAILED_GIT_COMMIT,
    }
    new = {**old, "git_commit": "f" * 40}
    assert recovery.stable_hash(old) == recovery.FAILED_EXECUTION_ID
    assert recovery.stable_hash(new) != recovery.FAILED_EXECUTION_ID


def test_cli_rejects_apply_on_status() -> None:
    with pytest.raises(SystemExit):
        recovery.parse_args(["status", "--apply"])


def test_private_recovery_gate_is_exact_and_single_use(monkeypatch) -> None:
    current = _failed_manifest()
    incoming = recovery.recovery_manifest(
        current, expected_manifest_digest=current.artifact_digest
    )
    repository = object.__new__(recovery.RecoveryRepository)
    repository._recovery_gate = {
        "consumed": False,
        "current_manifest_digest": current.artifact_digest,
        "incoming_manifest_digest": incoming.artifact_digest,
        "expected_manifest_digest": incoming.artifact_digest,
    }
    repository.load_manifest = lambda **_: current
    monkeypatch.setattr(recovery, "recovery_manifest", lambda _: incoming)
    repository._verify_exact_transition(incoming)
    assert repository._recovery_gate["consumed"] is True
    with pytest.raises(recovery.ResearchOSValidationError, match="gate"):
        repository._verify_exact_transition(incoming)


def test_corrected_operator_scope_is_frozen(monkeypatch) -> None:
    source_digest = "a" * 64
    git_commit = "f" * 40
    payload = {
        "version": "m4-isolated-24h-challenger-v11",
        "commit": git_commit,
        "checks": {
            "isolated_v11_activation": {
                "allowed_actions": recovery.EXPECTED_ACTIONS,
                "source_contract_digest": source_digest,
                "lifecycle_addendum_request_id": 702,
                "lifecycle_addendum_approval_decision_id": 2949,
                "external_isolated_mail_required": True,
                "formal_p3_mutation": False,
            }
        },
        "rollback": {},
    }
    payload_sha = hashlib.sha256(
        contract.canonical_json(payload).encode("utf-8")
    ).hexdigest()
    request = SimpleNamespace(
        id=725,
        request_type=AgentRequestType.OPERATOR_RELEASE,
        status=AgentRequestStatus.EXECUTING,
        payload=payload,
        metadata={"payload_sha256": payload_sha},
    )
    approval = SimpleNamespace(
        id=3057,
        decision_code="request_approved",
        previous_status="under_review",
        new_status="approved",
        decided_by_role=AgentRole.REVIEWER,
    )
    execution = SimpleNamespace(
        id=581,
        status=AgentExecutionStatus.RUNNING,
        environment="production",
        executor_role=AgentRole.OPERATOR,
    )
    repository = SimpleNamespace(
        get_request=lambda _: request,
        list_decisions=lambda _: [approval],
        list_execution_metadata=lambda _: [execution],
    )
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_REQUEST_KEY", "corrected")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_DECISION_ID", "3057")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_EXECUTION_ID", "581")
    result = recovery.validate_corrected_operator_scope(
        repository=repository, source_digest=source_digest, git_commit=git_commit
    )
    assert result["payload_sha256"] == payload_sha
    request.payload = {**payload, "version": "wrong"}
    with pytest.raises(recovery.AttestationRecoveryError, match="scope"):
        recovery.validate_corrected_operator_scope(
            repository=repository,
            source_digest=source_digest,
            git_commit=git_commit,
        )
