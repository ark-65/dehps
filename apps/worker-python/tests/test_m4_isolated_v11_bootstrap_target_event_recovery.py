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
from dehps.research_os.models import ControlPlaneManifest, DependencyFacts

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
