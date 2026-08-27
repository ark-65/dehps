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
from dehps.research_os.models import (
    CompletionClassification,
    ControlPlaneManifest,
    DependencyFacts,
    TaskStatus,
)

from scripts import repair_m4_isolated_v11_bootstrap_target_event as recovery
from scripts import run_m4_isolated_24h_challenger_v11 as runner

SOURCE_DIGEST = "38ea4d38e66558f30eb4c8660555ca35dd584aa3de02801fe6f6075d09ffaff1"


def _manifest():
    context = contract.render_context(
        source_max_issue="2026099",
        source_max_draw_date="2026-08-27",
        target_issue="2026100",
        target_draw_date="2026-08-30",
        projection_time="2026-08-28T00:27:06.982677+08:00",
    )
    payload, _ = runner.builder.build_manifest(
        context=context,
        source_digest=SOURCE_DIGEST,
        operator_configuration_authorized=True,
        simulation_events=False,
    )
    manifest = ControlPlaneManifest.from_dict(payload)
    facts = DependencyFacts(
        artifacts=frozenset(
            {
                contract.FREEZE_FACT,
                contract.OPERATOR_ATTESTATION_FACT,
                contract.MAIL_CONFIGURATION_FACT,
            }
        ),
        evidence=manifest.facts.evidence,
        external_events=frozenset({"RESOURCE_QUIESCENT_60S"}),
        authorities=manifest.facts.authorities,
    )
    return replace(manifest, facts=facts)


def test_event_extension_changes_only_external_event() -> None:
    current = _manifest()
    incoming = recovery.build_event_extension(
        current,
        source_digest=SOURCE_DIGEST,
        expected_manifest_digest=current.artifact_digest,
    )
    assert incoming.goals == current.goals
    assert incoming.goal_states == current.goal_states
    assert incoming.tasks == current.tasks
    assert incoming.task_states == current.task_states
    assert incoming.facts.artifacts == current.facts.artifacts
    assert incoming.facts.evidence == current.facts.evidence
    assert incoming.facts.authorities == current.facts.authorities
    assert incoming.facts.external_events == {
        "RESOURCE_QUIESCENT_60S",
        recovery.EVENT,
    }


def test_event_extension_rejects_existing_or_extra_event() -> None:
    current = _manifest()
    present = replace(
        current,
        facts=replace(
            current.facts,
            external_events=current.facts.external_events | {recovery.EVENT},
        ),
    )
    with pytest.raises(recovery.TargetEventRecoveryError, match="already_present"):
        recovery.build_event_extension(
            present,
            source_digest=SOURCE_DIGEST,
            expected_manifest_digest=present.artifact_digest,
        )
    extra = replace(
        current,
        facts=replace(
            current.facts,
            external_events=current.facts.external_events | {"DAILY_SEND"},
        ),
    )
    with pytest.raises(recovery.TargetEventRecoveryError, match="events_changed"):
        recovery.build_event_extension(
            extra,
            source_digest=SOURCE_DIGEST,
            expected_manifest_digest=extra.artifact_digest,
        )


def test_operator_scope_is_exact(monkeypatch) -> None:
    git_commit = "f" * 40
    payload = {
        "version": "m4-isolated-24h-challenger-v11",
        "commit": git_commit,
        "checks": {
            "target_projection_event_recovery": {
                "current_manifest_digest": recovery.CURRENT_MANIFEST_DIGEST,
                "event": recovery.EVENT,
                "source_contract_digest": SOURCE_DIGEST,
                "target_task_digest": recovery.TARGET_TASK_DIGEST,
                "target_task_key": recovery.TARGET_TASK_KEY,
            }
        },
        "rollback": {},
    }
    payload_sha = hashlib.sha256(
        contract.canonical_json(payload).encode("utf-8")
    ).hexdigest()
    request = SimpleNamespace(
        id=727,
        request_type=AgentRequestType.OPERATOR_RELEASE,
        status=AgentRequestStatus.EXECUTING,
        payload=payload,
        metadata={"payload_sha256": payload_sha},
    )
    approval = SimpleNamespace(
        id=3067,
        decision_code="request_approved",
        previous_status="under_review",
        new_status="approved",
        decided_by_role=AgentRole.REVIEWER,
    )
    execution = SimpleNamespace(
        id=583,
        status=AgentExecutionStatus.RUNNING,
        environment="production",
        executor_role=AgentRole.OPERATOR,
    )
    repository = SimpleNamespace(
        get_request=lambda _: request,
        list_decisions=lambda _: [approval],
        list_execution_metadata=lambda _: [execution],
    )
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_REQUEST_KEY", "operator")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_DECISION_ID", "3067")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_EXECUTION_ID", "583")
    assert (
        recovery.validate_operator_scope(
            repository=repository,
            source_digest=SOURCE_DIGEST,
            git_commit=git_commit,
        )["payload_sha256"]
        == payload_sha
    )
    request.payload = {**payload, "commit": "e" * 40}
    with pytest.raises(recovery.TargetEventRecoveryError, match="scope"):
        recovery.validate_operator_scope(
            repository=repository,
            source_digest=SOURCE_DIGEST,
            git_commit=git_commit,
        )


def _failed_target_manifest() -> ControlPlaneManifest:
    current = _manifest()
    tasks = {item.task_key: item for item in current.tasks}
    preregistration = tasks["m4-isolated-24h-challenger-v11-preregistration"]
    states = tuple(
        replace(
            state,
            declared_status=TaskStatus.COMPLETED,
            completion_classification=CompletionClassification.COMPLETE,
        )
        if state.task_digest == preregistration.artifact_digest
        else replace(
            state,
            declared_status=TaskStatus.FAILED,
            completion_classification=CompletionClassification.INTEGRATED,
        )
        if state.task_digest == recovery.TARGET_TASK_DIGEST
        else state
        for state in current.task_states
    )
    return replace(
        current,
        task_states=states,
        facts=replace(
            current.facts,
            artifacts=current.facts.artifacts
            | {
                (
                    f"mainline-execution:{preregistration.task_key}:"
                    f"{preregistration.artifact_digest}:{'9' * 64}:completed"
                )
            },
            external_events=current.facts.external_events | {recovery.EVENT},
        ),
    )


def test_failed_target_rebind_preserves_completed_and_rebuilds_only_uncompleted() -> (
    None
):
    current = _failed_target_manifest()
    source_digest = "f" * 64
    incoming = recovery.build_failed_target_rebind(
        current,
        source_digest=source_digest,
        expected_manifest_digest=current.artifact_digest,
    )
    assert incoming.goals == current.goals
    assert incoming.goal_states == current.goal_states
    assert incoming.facts == current.facts
    before = {item.task_key: item for item in current.tasks}
    after = {item.task_key: item for item in incoming.tasks}
    preregistration_key = "m4-isolated-24h-challenger-v11-preregistration"
    assert after[preregistration_key] == before[preregistration_key]
    assert (
        incoming.task_state_by_digest[
            after[preregistration_key].artifact_digest
        ].declared_status
        is TaskStatus.COMPLETED
    )
    assert (
        after[recovery.TARGET_TASK_KEY].artifact_digest != recovery.TARGET_TASK_DIGEST
    )
    target_state = incoming.task_state_by_digest[
        after[recovery.TARGET_TASK_KEY].artifact_digest
    ]
    assert target_state.declared_status is TaskStatus.DRAFT
    assert (
        target_state.completion_classification
        is CompletionClassification.INTEGRATION_PENDING
    )
    for key, task in after.items():
        if key == preregistration_key:
            continue
        metric = __import__("json").loads(task.metric_contract)
        assert metric["source_contract_digest"] == source_digest


def test_failed_target_rebind_rejects_nonfailed_target() -> None:
    current = _failed_target_manifest()
    target_state = current.task_state_by_digest[recovery.TARGET_TASK_DIGEST]
    changed = replace(
        current,
        task_states=tuple(
            replace(
                state,
                declared_status=TaskStatus.DRAFT,
                completion_classification=CompletionClassification.INTEGRATION_PENDING,
            )
            if state == target_state
            else state
            for state in current.task_states
        ),
    )
    with pytest.raises(recovery.TargetEventRecoveryError, match="target_state"):
        recovery.build_failed_target_rebind(
            changed,
            source_digest="f" * 64,
            expected_manifest_digest=changed.artifact_digest,
        )


def test_rebound_mixed_source_manifest_uses_normal_fail_closed_router() -> None:
    current = _failed_target_manifest()
    source_digest = "f" * 64
    rebound = recovery.build_failed_target_rebind(
        current,
        source_digest=source_digest,
        expected_manifest_digest=current.artifact_digest,
    )
    target = next(
        item for item in rebound.tasks if item.task_key == recovery.TARGET_TASK_KEY
    )
    transition = replace(
        rebound,
        task_states=tuple(
            replace(
                state,
                declared_status=TaskStatus.RUNNING,
                completion_classification=CompletionClassification.INTEGRATED,
            )
            if state.task_digest == target.artifact_digest
            else state
            for state in rebound.task_states
        ),
    )
    repository = object.__new__(runner.IsolatedChallengerRepository)
    repository.context = runner._task_context(target)
    repository.source_digest = source_digest
    repository._fact_gate = None
    repository._definition_gate = None
    repository._bootstrap_rebind_gate = None
    repository.load_manifest = lambda **_kwargs: rebound
    repository._verify_exact_transition(transition)
    without_attestation = replace(
        transition,
        facts=replace(
            transition.facts,
            artifacts=frozenset(
                item
                for item in transition.facts.artifacts
                if not item.startswith("mainline-execution:")
            ),
        ),
    )
    with pytest.raises(
        runner.ResearchOSValidationError, match="historical_task_source_changed"
    ):
        repository._verify_exact_transition(without_attestation)


def test_failed_target_private_rebind_gate_is_exact_and_single_use(monkeypatch) -> None:
    current = _failed_target_manifest()
    source_digest = "f" * 64
    incoming = recovery.build_failed_target_rebind(
        current,
        source_digest=source_digest,
        expected_manifest_digest=current.artifact_digest,
    )
    repository = object.__new__(recovery.FailedTargetRecoveryRepository)
    repository.source_digest = source_digest
    repository._failed_target_rebind_gate = {
        "consumed": False,
        "current_manifest_digest": current.artifact_digest,
        "incoming_manifest_digest": incoming.artifact_digest,
    }
    repository.load_manifest = lambda **_kwargs: current
    monkeypatch.setattr(
        recovery,
        "build_failed_target_rebind",
        lambda *_args, **_kwargs: incoming,
    )
    repository._verify_exact_transition(incoming)
    assert repository._failed_target_rebind_gate["consumed"] is True
    with pytest.raises(recovery.ResearchOSValidationError, match="gate"):
        repository._verify_exact_transition(incoming)


def test_ready_lineage_source_rebind_preserves_state_facts_and_frozen_goal() -> None:
    failed = _failed_target_manifest()
    ready = recovery.build_failed_target_rebind(
        failed,
        source_digest=recovery.READY_REBIND_PREDECESSOR_SOURCE_DIGEST,
        expected_manifest_digest=failed.artifact_digest,
    )
    advanced = recovery.build_ready_source_rebind(
        ready,
        source_digest="e" * 64,
        expected_manifest_digest=ready.artifact_digest,
    )
    assert advanced.goals == ready.goals
    assert advanced.goal_states == ready.goal_states
    assert advanced.facts == ready.facts
    assert [item.task_key for item in advanced.tasks] == [
        item.task_key for item in ready.tasks
    ]
    before = {item.task_key: item for item in ready.tasks}
    after = {item.task_key: item for item in advanced.tasks}
    for key, task in after.items():
        state = advanced.task_state_by_digest[task.artifact_digest]
        assert task.goal_digest == recovery.LIVE_PARTIAL_FROZEN_GOAL_DIGEST
        if state.declared_status is TaskStatus.COMPLETED:
            assert task == before[key]
        else:
            assert task.artifact_digest != before[key].artifact_digest
            assert state.declared_status is TaskStatus.DRAFT
            assert (
                __import__("json").loads(task.metric_contract)["source_contract_digest"]
                == "e" * 64
            )


def test_ready_lineage_operator_scope_is_exact(monkeypatch) -> None:
    source_digest = "e" * 64
    git_commit = "a" * 40
    payload = {
        "version": "ready-rebind",
        "commit": git_commit,
        "checks": {
            "ready_lineage_source_rebind": {
                "current_manifest_digest": recovery.READY_REBIND_MANIFEST_DIGEST,
                "frozen_goal_digest": recovery.LIVE_PARTIAL_FROZEN_GOAL_DIGEST,
                "predecessor_source_contract_digest": (
                    recovery.READY_REBIND_PREDECESSOR_SOURCE_DIGEST
                ),
                "source_contract_digest": source_digest,
                "target_task_digest": recovery.READY_REBIND_TARGET_TASK_DIGEST,
                "target_task_key": recovery.TARGET_TASK_KEY,
            }
        },
        "rollback": {},
    }
    payload_sha = hashlib.sha256(
        contract.canonical_json(payload).encode("utf-8")
    ).hexdigest()
    request = SimpleNamespace(
        id=734,
        request_type=AgentRequestType.OPERATOR_RELEASE,
        status=AgentRequestStatus.EXECUTING,
        payload=payload,
        metadata={"payload_sha256": payload_sha},
    )
    repository = SimpleNamespace(
        get_request=lambda _: request,
        list_decisions=lambda _: [
            SimpleNamespace(
                id=3103,
                decision_code="request_approved",
                previous_status="under_review",
                new_status="approved",
                decided_by_role=AgentRole.REVIEWER,
            )
        ],
        list_execution_metadata=lambda _: [
            SimpleNamespace(
                id=590,
                status=AgentExecutionStatus.RUNNING,
                environment="production",
                executor_role=AgentRole.OPERATOR,
            )
        ],
    )
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_REQUEST_KEY", "operator")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_DECISION_ID", "3103")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_EXECUTION_ID", "590")
    assert (
        recovery.validate_ready_source_operator_scope(
            repository=repository,
            source_digest=source_digest,
            git_commit=git_commit,
        )["payload_sha256"]
        == payload_sha
    )
    request.payload = {**payload, "commit": "b" * 40}
    with pytest.raises(recovery.TargetEventRecoveryError, match="scope"):
        recovery.validate_ready_source_operator_scope(
            repository=repository,
            source_digest=source_digest,
            git_commit=git_commit,
        )


def _failed_target_events():
    common = {
        "execution_id": recovery.FAILED_TARGET_EXECUTION_ID,
        "task_digest": recovery.TARGET_TASK_DIGEST,
        "task_key": recovery.TARGET_TASK_KEY,
    }
    return (
        {
            **common,
            "event_digest": recovery.FAILED_TARGET_STARTED_EVENT_DIGEST,
            "event_type": "started",
            "sequence": 0,
            "payload": (
                ("input_artifact_digests", [recovery.PREDECESSOR_SOURCE_DIGEST]),
                ("git_commit", recovery.FAILED_TARGET_GIT_COMMIT),
            ),
        },
        {
            **common,
            "event_digest": recovery.FAILED_TARGET_EVENT_DIGEST,
            "event_type": "failed",
            "sequence": 1,
            "payload": (
                ("error", "artifact_type_body_overrides_common_field"),
                ("git_commit", recovery.FAILED_TARGET_GIT_COMMIT),
            ),
        },
    )


def test_failed_target_event_chain_is_exact_and_artifact_free() -> None:
    recovery.validate_failed_target_events(_failed_target_events(), ())
    bad = list(_failed_target_events())
    bad[1] = {**bad[1], "event_digest": "0" * 64}
    with pytest.raises(recovery.TargetEventRecoveryError, match="identity"):
        recovery.validate_failed_target_events(bad, ())
    with pytest.raises(recovery.TargetEventRecoveryError, match="count"):
        recovery.validate_failed_target_events(
            _failed_target_events(), ({"artifact_digest": "1" * 64},)
        )


def test_failed_target_operator_scope_is_exact(monkeypatch) -> None:
    source_digest = "f" * 64
    git_commit = "a" * 40
    payload = {
        "version": "recovery",
        "commit": git_commit,
        "checks": {
            "target_projection_failure_recovery": {
                "current_manifest_digest": recovery.FAILED_TARGET_MANIFEST_DIGEST,
                "failed_execution_id": recovery.FAILED_TARGET_EXECUTION_ID,
                "failed_task_digest": recovery.TARGET_TASK_DIGEST,
                "failed_task_key": recovery.TARGET_TASK_KEY,
                "predecessor_source_contract_digest": recovery.PREDECESSOR_SOURCE_DIGEST,
                "source_contract_digest": source_digest,
            }
        },
        "rollback": {},
    }
    payload_sha = hashlib.sha256(
        contract.canonical_json(payload).encode("utf-8")
    ).hexdigest()
    request = SimpleNamespace(
        id=730,
        request_type=AgentRequestType.OPERATOR_RELEASE,
        status=AgentRequestStatus.EXECUTING,
        payload=payload,
        metadata={"payload_sha256": payload_sha},
    )
    approval = SimpleNamespace(
        id=3082,
        decision_code="request_approved",
        previous_status="under_review",
        new_status="approved",
        decided_by_role=AgentRole.REVIEWER,
    )
    execution = SimpleNamespace(
        id=586,
        status=AgentExecutionStatus.RUNNING,
        environment="production",
        executor_role=AgentRole.OPERATOR,
    )
    repository = SimpleNamespace(
        get_request=lambda _: request,
        list_decisions=lambda _: [approval],
        list_execution_metadata=lambda _: [execution],
    )
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_REQUEST_KEY", "operator")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_DECISION_ID", "3082")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_EXECUTION_ID", "586")
    assert (
        recovery.validate_failed_target_operator_scope(
            repository=repository,
            source_digest=source_digest,
            git_commit=git_commit,
        )["payload_sha256"]
        == payload_sha
    )
    request.payload = {**payload, "commit": "b" * 40}
    with pytest.raises(recovery.TargetEventRecoveryError, match="scope"):
        recovery.validate_failed_target_operator_scope(
            repository=repository,
            source_digest=source_digest,
            git_commit=git_commit,
        )
