from __future__ import annotations

import hashlib
import inspect
from dataclasses import replace
from types import SimpleNamespace

import pytest
from dehps.agents.requests import (
    AgentExecutionStatus,
    AgentRequestStatus,
    AgentRequestType,
)
from dehps.agents.roles import AgentRole
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_contract as contract,
)
from dehps.research_os.models import (
    CompletionClassification,
    ControlPlaneManifest,
    DependencyFacts,
    MainlineExecutionEvent,
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


def _input_collision_manifest() -> ControlPlaneManifest:
    failed = _failed_target_manifest()
    intermediate = recovery.build_failed_target_rebind(
        failed,
        source_digest=recovery.READY_REBIND_PREDECESSOR_SOURCE_DIGEST,
        expected_manifest_digest=failed.artifact_digest,
    )
    current = recovery.build_ready_source_rebind(
        intermediate,
        source_digest=recovery.INPUT_COLLISION_PREDECESSOR_SOURCE_DIGEST,
        expected_manifest_digest=intermediate.artifact_digest,
    )
    retained_names = {
        "genesis",
        "search_batch",
        "genesis_replay",
        "preregistration",
        "operator_attestation",
        "incident_head_genesis",
        "search_checkpoint",
        "mail_configuration",
        "search_batch_replay",
        "multiplicity_risk_limit",
        "target_issue_projection",
        "search_checkpoint_replay",
        "history_snapshot",
    }
    retained_keys = {
        contract.task_template_by_name(name).key(runner._task_context(current.tasks[0]))
        for name in retained_names
    }
    retained_tasks = tuple(
        task for task in current.tasks if task.task_key in retained_keys
    )
    retained_digests = {task.artifact_digest for task in retained_tasks}
    current = ControlPlaneManifest(
        goals=current.goals,
        tasks=retained_tasks,
        goal_states=current.goal_states,
        task_states=tuple(
            state
            for state in current.task_states
            if state.task_digest in retained_digests
        ),
        facts=current.facts,
        schema_version=current.schema_version,
    )
    base_context = runner._task_context(current.tasks[0])
    for index in range(9):
        current = ControlPlaneManifest.from_dict(
            runner.builder.extend_manifest(
                current.to_dict(include_digest=True),
                context={
                    **base_context,
                    "epoch_date": "20260828",
                    "minute": f"2026082802{index:02d}",
                },
                source_digest=recovery.INPUT_COLLISION_PREDECESSOR_SOURCE_DIGEST,
                template_names=frozenset({"runtime_health"}),
            )
        )
    target = next(
        item for item in current.tasks if item.task_key == recovery.TARGET_TASK_KEY
    )
    completed_keys = {
        contract.task_template_by_name(name).key(base_context)
        for name in (
            "preregistration",
            "operator_attestation",
            "incident_head_genesis",
            "mail_configuration",
        )
    }
    completed_digests = {
        task.artifact_digest
        for task in current.tasks
        if task.task_key in completed_keys or "-runtime-health-" in task.task_key
    }
    states = tuple(
        replace(
            state,
            declared_status=TaskStatus.FAILED,
            completion_classification=CompletionClassification.INTEGRATED,
        )
        if state.task_digest == target.artifact_digest
        else replace(
            state,
            declared_status=TaskStatus.COMPLETED,
            completion_classification=CompletionClassification.COMPLETE,
        )
        if state.task_digest in completed_digests
        else state
        for state in current.task_states
    )
    task_by_digest = {task.artifact_digest: task for task in current.tasks}
    facts = {
        (
            f"mainline-execution:{task_by_digest[digest].task_key}:"
            f"{digest}:{hashlib.sha256(digest.encode()).hexdigest()}:completed"
        )
        for digest in completed_digests
    }
    return replace(
        current,
        task_states=states,
        facts=replace(
            current.facts,
            artifacts=current.facts.artifacts | facts,
            external_events=current.facts.external_events | {recovery.EVENT},
        ),
    )


def test_input_collision_rebind_preserves_13_and_rebuilds_9() -> None:
    current = _input_collision_manifest()
    incoming = recovery.build_input_collision_rebind(
        current,
        source_digest="f" * 64,
        expected_manifest_digest=current.artifact_digest,
    )
    before = {item.task_key: item for item in current.tasks}
    after = {item.task_key: item for item in incoming.tasks}
    completed = 0
    rebound = 0
    for key, task in after.items():
        state = incoming.task_state_by_digest[task.artifact_digest]
        if state.declared_status is TaskStatus.COMPLETED:
            completed += 1
            assert task == before[key]
        else:
            rebound += 1
            assert task.artifact_digest != before[key].artifact_digest
            assert task.goal_digest == recovery.LIVE_PARTIAL_FROZEN_GOAL_DIGEST
            assert (
                __import__("json").loads(task.metric_contract)["source_contract_digest"]
                == "f" * 64
            )
    assert completed == 13
    assert rebound == 9
    target = after[recovery.TARGET_TASK_KEY]
    assert (
        incoming.task_state_by_digest[target.artifact_digest].declared_status
        is TaskStatus.DRAFT
    )
    assert incoming.facts == current.facts


def test_input_collision_rebind_requires_completed_attestation() -> None:
    current = _input_collision_manifest()
    completed_task = next(
        task
        for task in current.tasks
        if current.task_state_by_digest[task.artifact_digest].declared_status
        is TaskStatus.COMPLETED
    )
    prefix = f"mainline-execution:{completed_task.task_key}:{completed_task.artifact_digest}:"
    completions = {fact for fact in current.facts.artifacts if fact.startswith(prefix)}
    assert completions
    corrupted = replace(
        current,
        facts=replace(
            current.facts,
            artifacts=current.facts.artifacts - completions,
        ),
    )
    with pytest.raises(
        recovery.TargetEventRecoveryError, match="completed_task_changed"
    ):
        recovery.build_input_collision_rebind(
            corrupted,
            source_digest="f" * 64,
            expected_manifest_digest=corrupted.artifact_digest,
        )


def _history_common_field_manifest() -> ControlPlaneManifest:
    current = _input_collision_manifest()
    current = recovery.build_input_collision_rebind(
        current,
        source_digest=recovery.HISTORY_COMMON_FIELD_PREDECESSOR_SOURCE_DIGEST,
        expected_manifest_digest=current.artifact_digest,
    )
    context = {
        **runner._task_context(current.tasks[0]),
        "epoch_date": "20260828",
        "minute": "202608280226",
    }
    current = ControlPlaneManifest.from_dict(
        runner.builder.extend_manifest(
            current.to_dict(include_digest=True),
            context=context,
            source_digest=recovery.HISTORY_COMMON_FIELD_PREDECESSOR_SOURCE_DIGEST,
            template_names=frozenset({"runtime_health"}),
        )
    )
    target = next(
        item for item in current.tasks if item.task_key == recovery.TARGET_TASK_KEY
    )
    history = next(
        item for item in current.tasks if item.task_key == recovery.HISTORY_TASK_KEY
    )
    runtime = next(
        item
        for item in current.tasks
        if item.task_key.endswith("runtime-health-202608280226")
    )
    states = tuple(
        replace(
            state,
            declared_status=TaskStatus.COMPLETED,
            completion_classification=CompletionClassification.COMPLETE,
        )
        if state.task_digest in {target.artifact_digest, runtime.artifact_digest}
        else replace(
            state,
            declared_status=TaskStatus.FAILED,
            completion_classification=CompletionClassification.INTEGRATED,
        )
        if state.task_digest == history.artifact_digest
        else state
        for state in current.task_states
    )
    completion_facts = {
        (
            f"mainline-execution:{task.task_key}:{task.artifact_digest}:"
            f"{hashlib.sha256(task.artifact_digest.encode()).hexdigest()}:completed"
        )
        for task in (target, runtime)
    }
    return replace(
        current,
        task_states=states,
        facts=replace(
            current.facts,
            artifacts=current.facts.artifacts | completion_facts,
        ),
    )


def test_history_common_field_rebind_preserves_15_and_rebuilds_8() -> None:
    current = _history_common_field_manifest()
    incoming = recovery.build_history_common_field_rebind(
        current,
        source_digest="e" * 64,
        expected_manifest_digest=current.artifact_digest,
    )
    before = {item.task_key: item for item in current.tasks}
    after = {item.task_key: item for item in incoming.tasks}
    completed = 0
    rebound = 0
    for key, task in after.items():
        state = incoming.task_state_by_digest[task.artifact_digest]
        if state.declared_status is TaskStatus.COMPLETED:
            completed += 1
            assert task == before[key]
        else:
            rebound += 1
            assert task.artifact_digest != before[key].artifact_digest
            assert (
                __import__("json").loads(task.metric_contract)["source_contract_digest"]
                == "e" * 64
            )
    assert completed == 15
    assert rebound == 8
    history = after[recovery.HISTORY_TASK_KEY]
    assert (
        incoming.task_state_by_digest[history.artifact_digest].declared_status
        is TaskStatus.DRAFT
    )
    assert incoming.facts == current.facts


def test_history_common_field_private_gate_is_one_shot(monkeypatch) -> None:
    current = _history_common_field_manifest()
    incoming = recovery.build_history_common_field_rebind(
        current,
        source_digest="e" * 64,
        expected_manifest_digest=current.artifact_digest,
    )
    repository = object.__new__(recovery.HistoryCommonFieldRecoveryRepository)
    repository.source_digest = "e" * 64
    repository._history_rebind_gate = {
        "consumed": False,
        "current_manifest_digest": current.artifact_digest,
        "incoming_manifest_digest": incoming.artifact_digest,
    }
    repository.load_manifest = lambda **_kwargs: current
    monkeypatch.setattr(
        recovery,
        "build_history_common_field_rebind",
        lambda *_args, **_kwargs: incoming,
    )
    repository._verify_exact_transition(incoming)
    assert repository._history_rebind_gate["consumed"] is True
    with pytest.raises(recovery.ResearchOSValidationError, match="gate"):
        repository._verify_exact_transition(incoming)


def _genesis_common_field_manifest() -> ControlPlaneManifest:
    current = _history_common_field_manifest()
    current = recovery.build_history_common_field_rebind(
        current,
        source_digest=recovery.GENESIS_COMMON_FIELD_PREDECESSOR_SOURCE_DIGEST,
        expected_manifest_digest=current.artifact_digest,
    )
    context = {
        **runner._task_context(current.tasks[0]),
        "epoch_date": "20260828",
        "minute": "202608280300",
    }
    current = ControlPlaneManifest.from_dict(
        runner.builder.extend_manifest(
            current.to_dict(include_digest=True),
            context=context,
            source_digest=recovery.GENESIS_COMMON_FIELD_PREDECESSOR_SOURCE_DIGEST,
            template_names=frozenset({"runtime_health"}),
        )
    )
    history = next(
        item for item in current.tasks if item.task_key == recovery.HISTORY_TASK_KEY
    )
    genesis = next(
        item for item in current.tasks if item.task_key == recovery.GENESIS_TASK_KEY
    )
    runtime = next(
        item
        for item in current.tasks
        if item.task_key.endswith("runtime-health-202608280300")
    )
    states = tuple(
        replace(
            state,
            declared_status=TaskStatus.COMPLETED,
            completion_classification=CompletionClassification.COMPLETE,
        )
        if state.task_digest in {history.artifact_digest, runtime.artifact_digest}
        else replace(
            state,
            declared_status=TaskStatus.FAILED,
            completion_classification=CompletionClassification.INTEGRATED,
        )
        if state.task_digest == genesis.artifact_digest
        else state
        for state in current.task_states
    )
    completion_facts = {
        (
            f"mainline-execution:{task.task_key}:{task.artifact_digest}:"
            f"{hashlib.sha256(task.artifact_digest.encode()).hexdigest()}:completed"
        )
        for task in (history, runtime)
    }
    return replace(
        current,
        task_states=states,
        facts=replace(
            current.facts,
            artifacts=current.facts.artifacts | completion_facts,
        ),
    )


def test_genesis_common_field_rebind_preserves_17_and_rebuilds_7() -> None:
    current = _genesis_common_field_manifest()
    incoming = recovery.build_genesis_common_field_rebind(
        current,
        source_digest="d" * 64,
        expected_manifest_digest=current.artifact_digest,
    )
    before = {item.task_key: item for item in current.tasks}
    after = {item.task_key: item for item in incoming.tasks}
    completed = 0
    rebound = 0
    for key, task in after.items():
        state = incoming.task_state_by_digest[task.artifact_digest]
        if state.declared_status is TaskStatus.COMPLETED:
            completed += 1
            assert task == before[key]
        else:
            rebound += 1
            assert state.declared_status is TaskStatus.DRAFT
            assert task.artifact_digest != before[key].artifact_digest
            assert (
                __import__("json").loads(task.metric_contract)["source_contract_digest"]
                == "d" * 64
            )
    assert completed == 17
    assert rebound == 7
    assert (
        incoming.task_state_by_digest[
            after[recovery.GENESIS_TASK_KEY].artifact_digest
        ].declared_status
        is TaskStatus.DRAFT
    )
    assert incoming.facts == current.facts


def test_genesis_common_field_private_gate_is_one_shot(monkeypatch) -> None:
    current = _genesis_common_field_manifest()
    incoming = recovery.build_genesis_common_field_rebind(
        current,
        source_digest="d" * 64,
        expected_manifest_digest=current.artifact_digest,
    )
    repository = object.__new__(recovery.GenesisCommonFieldRecoveryRepository)
    repository.source_digest = "d" * 64
    repository._genesis_rebind_gate = {
        "consumed": False,
        "current_manifest_digest": current.artifact_digest,
        "incoming_manifest_digest": incoming.artifact_digest,
    }
    repository.load_manifest = lambda **_kwargs: current
    monkeypatch.setattr(
        recovery,
        "build_genesis_common_field_rebind",
        lambda *_args, **_kwargs: incoming,
    )
    repository._verify_exact_transition(incoming)
    assert repository._genesis_rebind_gate["consumed"] is True
    with pytest.raises(recovery.ResearchOSValidationError, match="gate"):
        repository._verify_exact_transition(incoming)


def _batch_timestamp_manifest() -> ControlPlaneManifest:
    current = _genesis_common_field_manifest()
    current = recovery.build_genesis_common_field_rebind(
        current,
        source_digest=recovery.BATCH_TIMESTAMP_PREDECESSOR_SOURCE_DIGEST,
        expected_manifest_digest=current.artifact_digest,
    )
    contexts = (
        {**runner._task_context(current.tasks[0]), "minute": "202608280339"},
        {**runner._task_context(current.tasks[0]), "minute": "202608280341"},
    )
    for context in contexts:
        current = ControlPlaneManifest.from_dict(
            runner.builder.extend_manifest(
                current.to_dict(include_digest=True),
                context=context,
                source_digest=recovery.BATCH_TIMESTAMP_PREDECESSOR_SOURCE_DIGEST,
                template_names=frozenset({"runtime_health"}),
            )
        )
    genesis = next(
        item for item in current.tasks if item.task_key == recovery.GENESIS_TASK_KEY
    )
    genesis_replay = next(
        item
        for item in current.tasks
        if item.task_key.endswith("search-genesis-replay")
    )
    batch = next(
        item
        for item in current.tasks
        if item.task_key == recovery.BATCH_TIMESTAMP_TASK_KEY
    )
    runtimes = tuple(
        item
        for item in current.tasks
        if item.task_key.endswith("runtime-health-202608280339")
        or item.task_key.endswith("runtime-health-202608280341")
    )
    completed_tasks = (genesis, genesis_replay, *runtimes)
    completed_digests = {item.artifact_digest for item in completed_tasks}
    states = tuple(
        replace(
            state,
            declared_status=TaskStatus.COMPLETED,
            completion_classification=CompletionClassification.COMPLETE,
        )
        if state.task_digest in completed_digests
        else replace(
            state,
            declared_status=TaskStatus.FAILED,
            completion_classification=CompletionClassification.INTEGRATED,
        )
        if state.task_digest == batch.artifact_digest
        else state
        for state in current.task_states
    )
    completion_facts = {
        (
            f"mainline-execution:{task.task_key}:{task.artifact_digest}:"
            f"{hashlib.sha256(task.artifact_digest.encode()).hexdigest()}:completed"
        )
        for task in completed_tasks
    }
    return replace(
        current,
        task_states=states,
        facts=replace(
            current.facts,
            artifacts=current.facts.artifacts | completion_facts,
        ),
    )


def test_batch_timestamp_rebind_preserves_21_and_rebuilds_5() -> None:
    current = _batch_timestamp_manifest()
    incoming = recovery.build_batch_timestamp_rebind(
        current,
        source_digest="c" * 64,
        expected_manifest_digest=current.artifact_digest,
    )
    before = {item.task_key: item for item in current.tasks}
    after = {item.task_key: item for item in incoming.tasks}
    completed = 0
    rebound = 0
    for key, task in after.items():
        state = incoming.task_state_by_digest[task.artifact_digest]
        if state.declared_status is TaskStatus.COMPLETED:
            completed += 1
            assert task == before[key]
        else:
            rebound += 1
            assert state.declared_status is TaskStatus.DRAFT
            assert task.artifact_digest != before[key].artifact_digest
    assert completed == 21
    assert rebound == 5
    assert (
        incoming.task_state_by_digest[
            after[recovery.BATCH_TIMESTAMP_TASK_KEY].artifact_digest
        ].declared_status
        is TaskStatus.DRAFT
    )
    assert incoming.facts == current.facts


def test_batch_timestamp_private_gate_is_one_shot(monkeypatch) -> None:
    current = _batch_timestamp_manifest()
    incoming = recovery.build_batch_timestamp_rebind(
        current,
        source_digest="c" * 64,
        expected_manifest_digest=current.artifact_digest,
    )
    repository = object.__new__(recovery.BatchTimestampRecoveryRepository)
    repository.source_digest = "c" * 64
    repository._batch_timestamp_gate = {
        "consumed": False,
        "current_manifest_digest": current.artifact_digest,
        "incoming_manifest_digest": incoming.artifact_digest,
    }
    repository.load_manifest = lambda **_kwargs: current
    monkeypatch.setattr(
        recovery,
        "build_batch_timestamp_rebind",
        lambda *_args, **_kwargs: incoming,
    )
    repository._verify_exact_transition(incoming)
    assert repository._batch_timestamp_gate["consumed"] is True
    with pytest.raises(recovery.ResearchOSValidationError, match="gate"):
        repository._verify_exact_transition(incoming)


def _user_scope_post_batch_manifest() -> ControlPlaneManifest:
    current = recovery.build_batch_timestamp_rebind(
        _batch_timestamp_manifest(),
        source_digest=recovery.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
        expected_manifest_digest=_batch_timestamp_manifest().artifact_digest,
    )
    context = {
        **runner._task_context(current.tasks[0]),
        "minute": "202608280355",
    }
    current = ControlPlaneManifest.from_dict(
        runner.builder.extend_manifest(
            current.to_dict(include_digest=True),
            context=context,
            source_digest=recovery.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
            template_names=frozenset({"runtime_health"}),
        )
    )
    batch = next(
        item
        for item in current.tasks
        if item.task_key == recovery.USER_SCOPE_RESUME_TASK_KEY
    )
    assert batch.artifact_digest == recovery.USER_SCOPE_RESUME_TASK_DIGEST
    health = next(
        item
        for item in current.tasks
        if item.task_key.endswith("runtime-health-202608280355")
    )
    completed_digests = {batch.artifact_digest, health.artifact_digest}
    states = tuple(
        replace(
            state,
            declared_status=TaskStatus.COMPLETED,
            completion_classification=CompletionClassification.COMPLETE,
        )
        if state.task_digest in completed_digests
        else state
        for state in current.task_states
    )
    state_by_digest = {state.task_digest: state for state in states}
    completion_facts = set(current.facts.artifacts)
    for task in current.tasks:
        if (
            state_by_digest[task.artifact_digest].declared_status
            is not TaskStatus.COMPLETED
        ):
            continue
        prefix = f"mainline-execution:{task.task_key}:{task.artifact_digest}:"
        completion_facts.difference_update(
            {
                fact
                for fact in completion_facts
                if fact.startswith(prefix) and fact.endswith(":completed")
            }
        )
        completion_facts.add(
            f"{prefix}{hashlib.sha256(task.artifact_digest.encode()).hexdigest()}:completed"
        )
    return replace(
        current,
        task_states=states,
        facts=replace(
            current.facts,
            artifacts=frozenset(completion_facts),
        ),
    )


def test_user_scope_post_batch_rebind_preserves_23_and_rebuilds_only_4() -> None:
    current = _user_scope_post_batch_manifest()
    incoming = recovery.build_user_scope_post_batch_rebind(
        current, source_digest="e" * 64
    )
    before = {item.task_key: item for item in current.tasks}
    after = {item.task_key: item for item in incoming.tasks}
    completed = 0
    rebound = 0
    for key, task in after.items():
        state = incoming.task_state_by_digest[task.artifact_digest]
        if state.declared_status is TaskStatus.COMPLETED:
            completed += 1
            assert task == before[key]
        else:
            rebound += 1
            assert state.declared_status is TaskStatus.DRAFT
            assert task.artifact_digest != before[key].artifact_digest
            assert (
                __import__("json").loads(task.metric_contract)["source_contract_digest"]
                == "e" * 64
            )
    assert completed == 23
    assert rebound == 4
    assert incoming.facts == current.facts
    assert [
        item.task_key for item in ResearchOSControlPlane().resolve(incoming).ready_queue
    ] == ["m4-isolated-24h-challenger-v11-search-batch-000000000000-replay"]


def test_user_scope_post_batch_rebind_accepts_only_exact_ecaf_to_b677(
    monkeypatch,
) -> None:
    committed = _user_scope_post_batch_manifest()
    rebound = recovery.build_user_scope_post_batch_rebind(
        committed,
        source_digest=recovery.USER_SCOPE_POST_BATCH_REBOUND_SOURCE_DIGEST,
    )
    monkeypatch.setattr(
        recovery,
        "USER_SCOPE_POST_BATCH_REBOUND_MANIFEST_DIGEST",
        rebound.artifact_digest,
    )
    repaired = recovery.build_user_scope_post_batch_rebind(
        rebound,
        source_digest=recovery.USER_SCOPE_POST_BATCH_REPAIRED_SOURCE_DIGEST,
    )
    before = {item.task_key: item for item in rebound.tasks}
    completed = 0
    rebuilt = 0
    for task in repaired.tasks:
        state = repaired.task_state_by_digest[task.artifact_digest]
        if state.declared_status is TaskStatus.COMPLETED:
            completed += 1
            assert task == before[task.task_key]
            continue
        rebuilt += 1
        assert state.declared_status is TaskStatus.DRAFT
        assert task.artifact_digest != before[task.task_key].artifact_digest
        assert (
            __import__("json").loads(task.metric_contract)["source_contract_digest"]
            == recovery.USER_SCOPE_POST_BATCH_REPAIRED_SOURCE_DIGEST
        )
    assert completed == 23
    assert rebuilt == 4
    assert repaired.goals == rebound.goals
    assert repaired.goal_states == rebound.goal_states
    assert repaired.facts == rebound.facts
    assert [
        item.task_key for item in ResearchOSControlPlane().resolve(repaired).ready_queue
    ] == ["m4-isolated-24h-challenger-v11-search-batch-000000000000-replay"]

    with pytest.raises(recovery.TargetEventRecoveryError, match="transition_changed"):
        recovery.build_user_scope_post_batch_rebind(
            rebound,
            source_digest="f" * 64,
        )
    drifted = replace(
        rebound,
        facts=replace(
            rebound.facts,
            external_events=rebound.facts.external_events | {"UNAUTHORIZED"},
        ),
    )
    with pytest.raises(recovery.TargetEventRecoveryError, match="changed"):
        recovery.build_user_scope_post_batch_rebind(
            drifted,
            source_digest=recovery.USER_SCOPE_POST_BATCH_REPAIRED_SOURCE_DIGEST,
        )


def test_user_scope_post_batch_uses_only_committed_recovery_governance() -> None:
    source = inspect.getsource(recovery.run_user_scope_post_batch_rebind)
    assert "validate_user_scope_committed_recovery_governance(" in source
    assert "validate_user_scope_recovery_governance(" not in source


def test_user_scope_post_batch_private_gate_is_one_shot(monkeypatch) -> None:
    current = _user_scope_post_batch_manifest()
    incoming = recovery.build_user_scope_post_batch_rebind(
        current, source_digest="e" * 64
    )
    repository = object.__new__(recovery.UserScopePostBatchRecoveryRepository)
    repository.source_digest = "e" * 64
    repository._user_scope_post_batch_gate = {
        "consumed": False,
        "current_manifest_digest": current.artifact_digest,
        "incoming_manifest_digest": incoming.artifact_digest,
    }
    repository.load_manifest = lambda **_kwargs: current
    monkeypatch.setattr(
        recovery,
        "build_user_scope_post_batch_rebind",
        lambda *_args, **_kwargs: incoming,
    )
    repository._verify_exact_transition(incoming)
    assert repository._user_scope_post_batch_gate["consumed"] is True
    with pytest.raises(recovery.ResearchOSValidationError, match="gate"):
        repository._verify_exact_transition(incoming)


def test_user_scope_post_batch_event_chain_is_exact() -> None:
    shared = {
        "capability": "M4IsolatedSearchBatchCapabilityV11",
        "control_plane_key": contract.CONTROL_PLANE_KEY,
        "task_key": recovery.USER_SCOPE_RESUME_TASK_KEY,
    }
    records = (
        MainlineExecutionEvent(
            **shared,
            execution_id=runner.USER_SCOPE_HISTORICAL_EXECUTION_ID,
            manifest_digest=runner.USER_SCOPE_HISTORICAL_MANIFEST_DIGEST,
            task_digest=runner.USER_SCOPE_HISTORICAL_TASK_DIGEST,
            event_type="started",
            sequence=0,
            recorded_at=runner.USER_SCOPE_HISTORICAL_STARTED_AT,
            payload=(
                (
                    "input_artifact_digests",
                    [runner.USER_SCOPE_HISTORICAL_SOURCE_DIGEST],
                ),
                ("git_commit", runner.USER_SCOPE_HISTORICAL_COMMIT),
            ),
        ),
        MainlineExecutionEvent(
            **shared,
            execution_id=runner.USER_SCOPE_HISTORICAL_EXECUTION_ID,
            manifest_digest=runner.USER_SCOPE_HISTORICAL_MANIFEST_DIGEST,
            task_digest=runner.USER_SCOPE_HISTORICAL_TASK_DIGEST,
            event_type="failed",
            sequence=1,
            recorded_at=runner.USER_SCOPE_HISTORICAL_FAILED_AT,
            payload=(
                ("error", "atomic_registration_artifact_content_changed"),
                ("git_commit", runner.USER_SCOPE_HISTORICAL_COMMIT),
            ),
        ),
        MainlineExecutionEvent(
            **shared,
            execution_id=recovery.USER_SCOPE_RESUME_EXECUTION_ID,
            manifest_digest=recovery.USER_SCOPE_RESUME_MANIFEST_DIGEST,
            task_digest=recovery.USER_SCOPE_RESUME_TASK_DIGEST,
            event_type="started",
            sequence=0,
            recorded_at=runner.USER_SCOPE_RESUME_STARTED_AT,
            payload=(
                (
                    "input_artifact_digests",
                    [recovery.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST],
                ),
                ("git_commit", recovery.USER_SCOPE_RESUME_ORIGIN_COMMIT),
            ),
        ),
        MainlineExecutionEvent(
            **shared,
            execution_id=recovery.USER_SCOPE_RESUME_EXECUTION_ID,
            manifest_digest=recovery.USER_SCOPE_RESUME_MANIFEST_DIGEST,
            task_digest=recovery.USER_SCOPE_RESUME_TASK_DIGEST,
            event_type="failed",
            sequence=1,
            recorded_at=runner.USER_SCOPE_RESUME_FAILED_AT,
            payload=(
                ("error", "atomic_registration_resume_changed"),
                ("git_commit", recovery.USER_SCOPE_RESUME_ORIGIN_COMMIT),
            ),
        ),
        MainlineExecutionEvent(
            **shared,
            execution_id=recovery.USER_SCOPE_RESUME_EXECUTION_ID,
            manifest_digest=recovery.USER_SCOPE_RESUME_MANIFEST_DIGEST,
            task_digest=recovery.USER_SCOPE_RESUME_TASK_DIGEST,
            event_type="failed",
            sequence=2,
            recorded_at=runner.USER_SCOPE_GUARD_FAILED_AT,
            payload=(
                (
                    "error",
                    "M4-v2 atomic successor does not permit failed-execution recovery",
                ),
                ("git_commit", recovery.USER_SCOPE_RESUME_ORIGIN_COMMIT),
            ),
        ),
        MainlineExecutionEvent(
            **shared,
            execution_id=recovery.USER_SCOPE_RESUME_EXECUTION_ID,
            manifest_digest=recovery.USER_SCOPE_RESUME_MANIFEST_DIGEST,
            task_digest=recovery.USER_SCOPE_RESUME_TASK_DIGEST,
            event_type="completed",
            sequence=3,
            recorded_at="2026-08-27T22:43:51.392312+00:00",
            payload=tuple(
                sorted(
                    {
                        "actual_fold_count": contract.OUTER_FOLD_COUNT,
                        "additional_completed_task_keys": [],
                        "completion_facts": [],
                        "execution_artifact_digest": (
                            recovery.USER_SCOPE_COMMITTED_EXECUTION_ARTIFACT_DIGEST
                        ),
                        "execution_artifact_path": (
                            "runtime/isolated-24h-challenger-v11/artifacts/"
                            "m4-isolated-24h-challenger-v11-search-batch-"
                            "000000000000/"
                            f"{recovery.USER_SCOPE_RESUME_EXECUTION_ID}/execution.json"
                        ),
                        "formal_p3_mutated": False,
                        "git_commit": recovery.USER_SCOPE_RESUME_ORIGIN_COMMIT,
                        "isolated_lineage": contract.LINEAGE_ID,
                        "promotion_triggered": False,
                        "publication_batch_digest": (
                            recovery.USER_SCOPE_COMMITTED_PUBLICATION_BATCH_DIGEST
                        ),
                        "registered_artifact_count": 65,
                        "simulation": False,
                        "task_template": "search_batch",
                        "workload_rerun": False,
                    }.items()
                )
            ),
        ),
    )
    expected_digests = (
        runner.USER_SCOPE_HISTORICAL_STARTED_EVENT_DIGEST,
        runner.USER_SCOPE_HISTORICAL_FAILED_EVENT_DIGEST,
        recovery.USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
        recovery.USER_SCOPE_RESUME_FAILED_EVENT_DIGEST,
        recovery.USER_SCOPE_GUARD_FAILED_EVENT_DIGEST,
        recovery.USER_SCOPE_COMMITTED_EVENT_DIGEST,
    )
    assert tuple(item.artifact_digest for item in records) == expected_digests
    events = tuple(
        {
            "event_digest": item.artifact_digest,
            "execution_id": item.execution_id,
            "control_plane_key": item.control_plane_key,
            "manifest_digest": item.manifest_digest,
            "task_key": item.task_key,
            "task_digest": item.task_digest,
            "capability": item.capability,
            "event_type": item.event_type,
            "sequence": item.sequence,
            "recorded_at": item.recorded_at,
            "payload": list(item.payload),
        }
        for item in records
    )
    registrations = (
        {
            "artifact_digest": (
                recovery.USER_SCOPE_COMMITTED_EXECUTION_ARTIFACT_DIGEST
            ),
            "artifact_type": "research_os_mainline_execution",
        },
        *(
            {
                "artifact_digest": f"{index:064x}",
                "artifact_type": "isolated_challenger_fixture_artifact",
            }
            for index in range(1, 65)
        ),
    )
    assert (
        recovery.validate_user_scope_post_batch_events(events, registrations)
        == recovery.USER_SCOPE_COMMITTED_EVENT_DIGEST
    )
    with pytest.raises(recovery.TargetEventRecoveryError, match="count"):
        recovery.validate_user_scope_post_batch_events(events[:-1], registrations)
    with pytest.raises(recovery.TargetEventRecoveryError, match="integrity"):
        recovery.validate_user_scope_post_batch_events(events[1:], registrations)
    for field, changed in (
        ("sequence", 4),
        ("event_digest", "8" * 64),
        ("payload", [("git_commit", "9" * 40)]),
    ):
        bad = (*events[:-1], {**events[-1], field: changed})
        with pytest.raises(recovery.TargetEventRecoveryError, match="integrity"):
            recovery.validate_user_scope_post_batch_events(bad, registrations)


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


def _input_collision_events():
    current_common = {
        "execution_id": recovery.INPUT_COLLISION_EXECUTION_ID,
        "task_digest": recovery.INPUT_COLLISION_TARGET_TASK_DIGEST,
        "task_key": recovery.TARGET_TASK_KEY,
    }
    return (
        *_failed_target_events(),
        {
            **current_common,
            "event_digest": recovery.INPUT_COLLISION_STARTED_EVENT_DIGEST,
            "event_type": "started",
            "sequence": 0,
            "payload": (
                (
                    "input_artifact_digests",
                    [recovery.INPUT_COLLISION_PREDECESSOR_SOURCE_DIGEST],
                ),
                ("git_commit", recovery.INPUT_COLLISION_GIT_COMMIT),
            ),
        },
        {
            **current_common,
            "event_digest": recovery.INPUT_COLLISION_FAILED_EVENT_DIGEST,
            "event_type": "failed",
            "sequence": 1,
            "payload": (
                ("error", "registered_input_persistence_changed"),
                ("git_commit", recovery.INPUT_COLLISION_GIT_COMMIT),
            ),
        },
    )


def test_input_collision_event_chain_is_exact_and_artifact_free() -> None:
    recovery.validate_input_collision_events(_input_collision_events(), ())
    bad = list(_input_collision_events())
    bad[-1] = {**bad[-1], "event_digest": "0" * 64}
    with pytest.raises(recovery.TargetEventRecoveryError, match="identity"):
        recovery.validate_input_collision_events(bad, ())
    with pytest.raises(recovery.TargetEventRecoveryError, match="artifact_count"):
        recovery.validate_input_collision_events(
            _input_collision_events(), ({"artifact_digest": "1" * 64},)
        )


def test_input_collision_operator_scope_is_exact(monkeypatch) -> None:
    source_digest = "f" * 64
    git_commit = "a" * 40
    recovery_contract = {
        "completed_source_contract_digests": sorted(
            recovery.INPUT_COLLISION_COMPLETED_SOURCE_DIGESTS
        ),
        "current_manifest_digest": recovery.INPUT_COLLISION_MANIFEST_DIGEST,
        "failed_execution_id": recovery.INPUT_COLLISION_EXECUTION_ID,
        "failed_task_digest": recovery.INPUT_COLLISION_TARGET_TASK_DIGEST,
        "failed_task_key": recovery.TARGET_TASK_KEY,
        "frozen_goal_digest": recovery.LIVE_PARTIAL_FROZEN_GOAL_DIGEST,
        "predecessor_source_contract_digest": (
            recovery.INPUT_COLLISION_PREDECESSOR_SOURCE_DIGEST
        ),
        "source_contract_digest": source_digest,
    }
    payload = {
        "version": "input-collision-recovery",
        "commit": git_commit,
        "checks": {"registered_input_collision_recovery": recovery_contract},
        "rollback": {},
    }
    payload_sha = hashlib.sha256(
        contract.canonical_json(payload).encode("utf-8")
    ).hexdigest()
    request = SimpleNamespace(
        id=737,
        request_type=AgentRequestType.OPERATOR_RELEASE,
        status=AgentRequestStatus.EXECUTING,
        payload=payload,
        metadata={"payload_sha256": payload_sha},
    )
    repository = SimpleNamespace(
        get_request=lambda _: request,
        list_decisions=lambda _: [
            SimpleNamespace(
                id=3118,
                decision_code="request_approved",
                previous_status="under_review",
                new_status="approved",
                decided_by_role=AgentRole.REVIEWER,
            )
        ],
        list_execution_metadata=lambda _: [
            SimpleNamespace(
                id=593,
                status=AgentExecutionStatus.RUNNING,
                environment="production",
                executor_role=AgentRole.OPERATOR,
            )
        ],
    )
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_REQUEST_KEY", "operator")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_DECISION_ID", "3118")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_EXECUTION_ID", "593")
    assert (
        recovery.validate_input_collision_operator_scope(
            repository=repository,
            source_digest=source_digest,
            git_commit=git_commit,
        )["payload_sha256"]
        == payload_sha
    )
    request.payload = {
        **payload,
        "checks": {
            "registered_input_collision_recovery": {
                **recovery_contract,
                "completed_source_contract_digests": ["0" * 64],
            }
        },
    }
    with pytest.raises(recovery.TargetEventRecoveryError, match="scope"):
        recovery.validate_input_collision_operator_scope(
            repository=repository,
            source_digest=source_digest,
            git_commit=git_commit,
        )


def _history_common_field_events():
    common = {
        "execution_id": recovery.HISTORY_COMMON_FIELD_EXECUTION_ID,
        "task_digest": recovery.HISTORY_COMMON_FIELD_TASK_DIGEST,
        "task_key": recovery.HISTORY_TASK_KEY,
    }
    return (
        {
            **common,
            "event_digest": recovery.HISTORY_COMMON_FIELD_STARTED_EVENT_DIGEST,
            "event_type": "started",
            "sequence": 0,
            "payload": (
                (
                    "input_artifact_digests",
                    [recovery.HISTORY_COMMON_FIELD_PREDECESSOR_SOURCE_DIGEST],
                ),
                ("git_commit", recovery.HISTORY_COMMON_FIELD_GIT_COMMIT),
            ),
        },
        {
            **common,
            "event_digest": recovery.HISTORY_COMMON_FIELD_FAILED_EVENT_DIGEST,
            "event_type": "failed",
            "sequence": 1,
            "payload": (
                ("error", "artifact_type_body_overrides_common_field"),
                ("git_commit", recovery.HISTORY_COMMON_FIELD_GIT_COMMIT),
            ),
        },
    )


def test_history_common_field_event_chain_is_exact_and_artifact_free() -> None:
    recovery.validate_history_common_field_events(_history_common_field_events(), ())
    bad = list(_history_common_field_events())
    bad[-1] = {**bad[-1], "event_digest": "0" * 64}
    with pytest.raises(recovery.TargetEventRecoveryError, match="identity"):
        recovery.validate_history_common_field_events(bad, ())


def test_history_common_field_operator_scope_is_exact(monkeypatch) -> None:
    source_digest = "e" * 64
    git_commit = "a" * 40
    recovery_contract = {
        "completed_source_contract_digests": sorted(
            recovery.HISTORY_COMMON_FIELD_COMPLETED_SOURCE_DIGESTS
        ),
        "current_manifest_digest": recovery.HISTORY_COMMON_FIELD_MANIFEST_DIGEST,
        "failed_execution_id": recovery.HISTORY_COMMON_FIELD_EXECUTION_ID,
        "failed_task_digest": recovery.HISTORY_COMMON_FIELD_TASK_DIGEST,
        "failed_task_key": recovery.HISTORY_TASK_KEY,
        "frozen_goal_digest": recovery.LIVE_PARTIAL_FROZEN_GOAL_DIGEST,
        "predecessor_source_contract_digest": (
            recovery.HISTORY_COMMON_FIELD_PREDECESSOR_SOURCE_DIGEST
        ),
        "source_contract_digest": source_digest,
    }
    payload = {
        "version": "history-common-field-recovery",
        "commit": git_commit,
        "checks": {"history_snapshot_failure_recovery": recovery_contract},
        "rollback": {},
    }
    payload_sha = hashlib.sha256(
        contract.canonical_json(payload).encode("utf-8")
    ).hexdigest()
    request = SimpleNamespace(
        id=739,
        request_type=AgentRequestType.OPERATOR_RELEASE,
        status=AgentRequestStatus.EXECUTING,
        payload=payload,
        metadata={"payload_sha256": payload_sha},
    )
    repository = SimpleNamespace(
        get_request=lambda _: request,
        list_decisions=lambda _: [
            SimpleNamespace(
                id=3128,
                decision_code="request_approved",
                previous_status="under_review",
                new_status="approved",
                decided_by_role=AgentRole.REVIEWER,
            )
        ],
        list_execution_metadata=lambda _: [
            SimpleNamespace(
                id=595,
                status=AgentExecutionStatus.RUNNING,
                environment="production",
                executor_role=AgentRole.OPERATOR,
            )
        ],
    )
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_REQUEST_KEY", "operator")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_DECISION_ID", "3128")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_EXECUTION_ID", "595")
    assert (
        recovery.validate_history_common_field_operator_scope(
            repository=repository,
            source_digest=source_digest,
            git_commit=git_commit,
        )["payload_sha256"]
        == payload_sha
    )
    request.payload = {**payload, "commit": "b" * 40}
    with pytest.raises(recovery.TargetEventRecoveryError, match="scope"):
        recovery.validate_history_common_field_operator_scope(
            repository=repository,
            source_digest=source_digest,
            git_commit=git_commit,
        )


def _genesis_common_field_events():
    common = {
        "execution_id": recovery.GENESIS_COMMON_FIELD_EXECUTION_ID,
        "task_digest": recovery.GENESIS_COMMON_FIELD_TASK_DIGEST,
        "task_key": recovery.GENESIS_TASK_KEY,
    }
    return (
        {
            **common,
            "event_digest": recovery.GENESIS_COMMON_FIELD_STARTED_EVENT_DIGEST,
            "event_type": "started",
            "sequence": 0,
            "payload": (
                (
                    "input_artifact_digests",
                    [recovery.GENESIS_COMMON_FIELD_PREDECESSOR_SOURCE_DIGEST],
                ),
                ("git_commit", recovery.GENESIS_COMMON_FIELD_GIT_COMMIT),
            ),
        },
        {
            **common,
            "event_digest": recovery.GENESIS_COMMON_FIELD_FAILED_EVENT_DIGEST,
            "event_type": "failed",
            "sequence": 1,
            "payload": (
                ("error", "artifact_type_body_overrides_common_field"),
                ("git_commit", recovery.GENESIS_COMMON_FIELD_GIT_COMMIT),
            ),
        },
    )


def test_genesis_common_field_event_chain_is_exact_and_artifact_free() -> None:
    recovery.validate_genesis_common_field_events(_genesis_common_field_events(), ())
    bad = list(_genesis_common_field_events())
    bad[-1] = {**bad[-1], "event_digest": "0" * 64}
    with pytest.raises(recovery.TargetEventRecoveryError, match="identity"):
        recovery.validate_genesis_common_field_events(bad, ())
    with pytest.raises(recovery.TargetEventRecoveryError, match="count"):
        recovery.validate_genesis_common_field_events(
            _genesis_common_field_events(), ({"artifact_digest": "1" * 64},)
        )


def test_genesis_common_field_operator_scope_is_exact(monkeypatch) -> None:
    source_digest = "d" * 64
    git_commit = "a" * 40
    recovery_contract = {
        "completed_source_contract_digests": sorted(
            recovery.GENESIS_COMMON_FIELD_COMPLETED_SOURCE_DIGESTS
        ),
        "current_manifest_digest": recovery.GENESIS_COMMON_FIELD_MANIFEST_DIGEST,
        "failed_execution_id": recovery.GENESIS_COMMON_FIELD_EXECUTION_ID,
        "failed_task_digest": recovery.GENESIS_COMMON_FIELD_TASK_DIGEST,
        "failed_task_key": recovery.GENESIS_TASK_KEY,
        "frozen_goal_digest": recovery.LIVE_PARTIAL_FROZEN_GOAL_DIGEST,
        "predecessor_source_contract_digest": (
            recovery.GENESIS_COMMON_FIELD_PREDECESSOR_SOURCE_DIGEST
        ),
        "source_contract_digest": source_digest,
    }
    payload = {
        "version": "genesis-common-field-recovery",
        "commit": git_commit,
        "checks": {"genesis_failure_recovery": recovery_contract},
        "rollback": {},
    }
    payload_sha = hashlib.sha256(
        contract.canonical_json(payload).encode("utf-8")
    ).hexdigest()
    request = SimpleNamespace(
        id=742,
        request_type=AgentRequestType.OPERATOR_RELEASE,
        status=AgentRequestStatus.EXECUTING,
        payload=payload,
        metadata={"payload_sha256": payload_sha},
    )
    repository = SimpleNamespace(
        get_request=lambda _: request,
        list_decisions=lambda _: [
            SimpleNamespace(
                id=3140,
                decision_code="request_approved",
                previous_status="under_review",
                new_status="approved",
                decided_by_role=AgentRole.REVIEWER,
            )
        ],
        list_execution_metadata=lambda _: [
            SimpleNamespace(
                id=597,
                status=AgentExecutionStatus.RUNNING,
                environment="production",
                executor_role=AgentRole.OPERATOR,
            )
        ],
    )
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_REQUEST_KEY", "operator")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_DECISION_ID", "3140")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_EXECUTION_ID", "597")
    assert (
        recovery.validate_genesis_common_field_operator_scope(
            repository=repository,
            source_digest=source_digest,
            git_commit=git_commit,
        )["payload_sha256"]
        == payload_sha
    )
    request.payload = {**payload, "commit": "b" * 40}
    with pytest.raises(recovery.TargetEventRecoveryError, match="scope"):
        recovery.validate_genesis_common_field_operator_scope(
            repository=repository,
            source_digest=source_digest,
            git_commit=git_commit,
        )


def _batch_timestamp_events():
    common = {
        "execution_id": recovery.BATCH_TIMESTAMP_EXECUTION_ID,
        "task_digest": recovery.BATCH_TIMESTAMP_TASK_DIGEST,
        "task_key": recovery.BATCH_TIMESTAMP_TASK_KEY,
    }
    return (
        {
            **common,
            "event_digest": recovery.BATCH_TIMESTAMP_STARTED_EVENT_DIGEST,
            "event_type": "started",
            "sequence": 0,
            "payload": (
                (
                    "input_artifact_digests",
                    [recovery.BATCH_TIMESTAMP_PREDECESSOR_SOURCE_DIGEST],
                ),
                ("git_commit", recovery.BATCH_TIMESTAMP_GIT_COMMIT),
            ),
        },
        {
            **common,
            "event_digest": recovery.BATCH_TIMESTAMP_FAILED_EVENT_DIGEST,
            "event_type": "failed",
            "sequence": 1,
            "payload": (
                ("error", "atomic_registration_artifact_content_changed"),
                ("git_commit", recovery.BATCH_TIMESTAMP_GIT_COMMIT),
            ),
        },
    )


def test_batch_timestamp_event_chain_is_exact_and_artifact_free() -> None:
    recovery.validate_batch_timestamp_events(_batch_timestamp_events(), ())
    bad = list(_batch_timestamp_events())
    bad[-1] = {**bad[-1], "event_digest": "0" * 64}
    with pytest.raises(recovery.TargetEventRecoveryError, match="identity"):
        recovery.validate_batch_timestamp_events(bad, ())


def test_batch_timestamp_operator_scope_is_exact(monkeypatch) -> None:
    source_digest = "c" * 64
    git_commit = "a" * 40
    recovery_contract = {
        "completed_source_contract_digests": sorted(
            recovery.BATCH_TIMESTAMP_COMPLETED_SOURCE_DIGESTS
        ),
        "current_manifest_digest": recovery.BATCH_TIMESTAMP_MANIFEST_DIGEST,
        "failed_execution_id": recovery.BATCH_TIMESTAMP_EXECUTION_ID,
        "failed_task_digest": recovery.BATCH_TIMESTAMP_TASK_DIGEST,
        "failed_task_key": recovery.BATCH_TIMESTAMP_TASK_KEY,
        "frozen_goal_digest": recovery.LIVE_PARTIAL_FROZEN_GOAL_DIGEST,
        "predecessor_source_contract_digest": (
            recovery.BATCH_TIMESTAMP_PREDECESSOR_SOURCE_DIGEST
        ),
        "source_contract_digest": source_digest,
    }
    payload = {
        "version": "batch-timestamp-recovery",
        "commit": git_commit,
        "checks": {"batch_timestamp_failure_recovery": recovery_contract},
        "rollback": {},
    }
    payload_sha = hashlib.sha256(
        contract.canonical_json(payload).encode("utf-8")
    ).hexdigest()
    request = SimpleNamespace(
        id=744,
        request_type=AgentRequestType.OPERATOR_RELEASE,
        status=AgentRequestStatus.EXECUTING,
        payload=payload,
        metadata={"payload_sha256": payload_sha},
    )
    repository = SimpleNamespace(
        get_request=lambda _: request,
        list_decisions=lambda _: [
            SimpleNamespace(
                id=3150,
                decision_code="request_approved",
                previous_status="under_review",
                new_status="approved",
                decided_by_role=AgentRole.REVIEWER,
            )
        ],
        list_execution_metadata=lambda _: [
            SimpleNamespace(
                id=599,
                status=AgentExecutionStatus.RUNNING,
                environment="production",
                executor_role=AgentRole.OPERATOR,
            )
        ],
    )
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_REQUEST_KEY", "operator")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_DECISION_ID", "3150")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_EXECUTION_ID", "599")
    assert (
        recovery.validate_batch_timestamp_operator_scope(
            repository=repository,
            source_digest=source_digest,
            git_commit=git_commit,
        )["payload_sha256"]
        == payload_sha
    )
    request.payload = {**payload, "commit": "b" * 40}
    with pytest.raises(recovery.TargetEventRecoveryError, match="scope"):
        recovery.validate_batch_timestamp_operator_scope(
            repository=repository,
            source_digest=source_digest,
            git_commit=git_commit,
        )
