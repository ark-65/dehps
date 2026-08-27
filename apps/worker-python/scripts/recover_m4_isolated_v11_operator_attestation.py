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
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

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
from dehps.research_os.models import (
    CompletionClassification,
    ControlPlaneManifest,
    ResearchOSValidationError,
    TaskState,
    TaskStatus,
    stable_hash,
)
from dehps.research_os.repository import (
    PostgresResearchOSRepository,
)
from dehps.research_os.supervisor import MAINLINE_EXECUTION_SCHEMA
from run_m4_isolated_24h_challenger_v11 import (
    IsolatedChallengerRepository,
    _latest_history_identity,
)

TASK_KEY = "m4-isolated-24h-challenger-v11-operator-attestation"
TASK_DIGEST = "381bb0be9cfd978801c5a38662ca7a408fe5816d2ec5132844016848b19cfb08"
FAILED_MANIFEST_DIGEST = (
    "ae1bd0535fe96ca0ecafcb725b6e482882e27abc0965bee661c4267670f14492"
)
FAILED_GIT_COMMIT = "13d39ada0a64aee51786b9c9e6802948afe789cc"
FAILED_EXECUTION_ID = "b925ad3ba7a701a995c32ea90b60ee38f1bbe13928bfbc911f1b06c43a714278"
STARTED_EVENT_DIGEST = (
    "ddd54b4e85b40c8e5006df020d21484eb2ff5b4abe47b90e0aa170bb9b6e6ce7"
)
FAILED_EVENT_DIGEST = "2529f7dc744e82c32a55b18199e568e1ceca8378caa6e09b5302d85f11c2a40b"
FAILED_OPERATOR_REQUEST_KEY = (
    "operator-m4-isolated-v11-production-resume-after-multicontext-rebind-v1"
)
FAILED_OPERATOR_REQUEST_ID = 723
FAILED_OPERATOR_EXECUTION_ID = 579
EXPECTED_ACTIONS = [
    "IMPORT_ISOLATED_V11_MANIFEST",
    "APPLY_ISOLATED_V11_MIGRATION",
    "VERIFY_ISOLATED_QQ_SMTP",
    "DEPLOY_ISOLATED_V11_SYSTEMD",
]


class AttestationRecoveryError(RuntimeError):
    pass


def recovery_manifest(
    current: ControlPlaneManifest,
    *,
    expected_manifest_digest: str = FAILED_MANIFEST_DIGEST,
) -> ControlPlaneManifest:
    if current.artifact_digest != expected_manifest_digest:
        raise AttestationRecoveryError("failed_manifest_identity_changed")
    matches = [task for task in current.tasks if task.task_key == TASK_KEY]
    if len(matches) != 1 or matches[0].artifact_digest != TASK_DIGEST:
        raise AttestationRecoveryError("failed_task_definition_changed")
    old = current.task_state_by_digest[TASK_DIGEST]
    if (
        old.declared_status is not TaskStatus.FAILED
        or old.completion_classification is not CompletionClassification.INTEGRATED
        or old.superseded_by_task_digest is not None
    ):
        raise AttestationRecoveryError("failed_task_state_changed")
    if contract.OPERATOR_ATTESTATION_FACT in current.facts.artifacts:
        raise AttestationRecoveryError("attestation_fact_already_exists")
    states = tuple(
        TaskState(
            task_digest=state.task_digest,
            declared_status=TaskStatus.DRAFT,
            completion_classification=CompletionClassification.INTEGRATION_PENDING,
            superseded_by_task_digest=None,
        )
        if state.task_digest == TASK_DIGEST
        else state
        for state in current.task_states
    )
    return replace(current, task_states=states)


def validate_failed_events(
    events: Sequence[Mapping[str, Any]],
    artifacts_for_execution: Sequence[Mapping[str, Any]],
) -> None:
    if len(events) != 2:
        raise AttestationRecoveryError("failed_event_count_changed")
    by_type = {str(event.get("event_type")): event for event in events}
    if set(by_type) != {"started", "failed"}:
        raise AttestationRecoveryError("failed_event_types_changed")
    started = by_type["started"]
    failed = by_type["failed"]
    if (
        started.get("event_digest") != STARTED_EVENT_DIGEST
        or failed.get("event_digest") != FAILED_EVENT_DIGEST
        or started.get("execution_id") != FAILED_EXECUTION_ID
        or failed.get("execution_id") != FAILED_EXECUTION_ID
        or started.get("task_digest") != TASK_DIGEST
        or failed.get("task_digest") != TASK_DIGEST
        or started.get("task_key") != TASK_KEY
        or failed.get("task_key") != TASK_KEY
        or started.get("sequence") != 0
        or failed.get("sequence") != 1
    ):
        raise AttestationRecoveryError("failed_event_identity_changed")
    started_payload = dict(started.get("payload") or ())
    failed_payload = dict(failed.get("payload") or ())
    if started_payload.get("git_commit") != FAILED_GIT_COMMIT or failed_payload != {
        "error": "operator_attestation_scope_invalid",
        "git_commit": FAILED_GIT_COMMIT,
    }:
        raise AttestationRecoveryError("failed_event_payload_changed")
    if artifacts_for_execution:
        raise AttestationRecoveryError("failed_execution_artifact_exists")


def validate_corrected_operator_scope(
    *, repository: AgentRequestRepository, source_digest: str, git_commit: str
) -> dict[str, int | str]:
    request_key = os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_REQUEST_KEY", "")
    try:
        decision_id = int(os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_DECISION_ID", ""))
        execution_id = int(
            os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_EXECUTION_ID", "")
        )
    except ValueError as exc:
        raise AttestationRecoveryError("operator_identity_invalid") from exc
    if not request_key or decision_id < 1 or execution_id < 1:
        raise AttestationRecoveryError("operator_identity_invalid")
    request = repository.get_request(request_key)
    decisions = repository.list_decisions(request_key)
    executions = repository.list_execution_metadata(request_key)
    approvals = [
        item
        for item in decisions
        if item.decision_code == "request_approved"
        and item.previous_status == "under_review"
        and item.new_status == "approved"
    ]
    execution_matches = [item for item in executions if item.id == execution_id]
    if (
        request.request_type is not AgentRequestType.OPERATOR_RELEASE
        or request.status is not AgentRequestStatus.EXECUTING
        or len(approvals) != 1
        or approvals[0].id != decision_id
        or approvals[0].decided_by_role is not AgentRole.REVIEWER
        or len(execution_matches) != 1
    ):
        raise AttestationRecoveryError("operator_governance_invalid")
    execution = execution_matches[0]
    if (
        execution.status is not AgentExecutionStatus.RUNNING
        or execution.environment != "production"
        or execution.executor_role is not AgentRole.OPERATOR
    ):
        raise AttestationRecoveryError("operator_execution_invalid")
    checks = request.payload.get("checks")
    activation = (
        checks.get("isolated_v11_activation") if isinstance(checks, dict) else None
    )
    if (
        request.payload.get("version") != "m4-isolated-24h-challenger-v11"
        or request.payload.get("commit") != git_commit
        or not isinstance(activation, dict)
        or activation.get("allowed_actions") != EXPECTED_ACTIONS
        or activation.get("source_contract_digest") != source_digest
        or activation.get("lifecycle_addendum_request_id")
        != contract.LIFECYCLE_ADDENDUM_REQUEST_ID
        or activation.get("lifecycle_addendum_approval_decision_id")
        != contract.LIFECYCLE_ADDENDUM_APPROVAL_DECISION_ID
        or activation.get("external_isolated_mail_required") is not True
        or activation.get("formal_p3_mutation") is not False
    ):
        raise AttestationRecoveryError("operator_scope_invalid")
    scope_digest = contract.domain_digest(
        request.payload,
        domain="dehps.m4.isolated-24h-challenger.operator-scope.v11",
    )
    actual_sha = hashlib.sha256(
        contract.canonical_json(request.payload).encode("utf-8")
    ).hexdigest()
    if request.metadata.get("payload_sha256") != actual_sha:
        raise AttestationRecoveryError("operator_payload_sha_changed")
    return {
        "request_id": request.id,
        "decision_id": decision_id,
        "execution_id": execution_id,
        "payload_sha256": actual_sha,
        "scope_digest": scope_digest,
    }


class RecoveryRepository(IsolatedChallengerRepository):
    def __init__(self, *, context: Mapping[str, str], source_digest: str) -> None:
        super().__init__(context=context, source_digest=source_digest)
        self._recovery_gate: dict[str, Any] | None = None

    def _verify_exact_transition(self, incoming: ControlPlaneManifest) -> None:
        gate = self._recovery_gate
        if gate is None:
            return super()._verify_exact_transition(incoming)
        current = self.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        expected = recovery_manifest(current)
        if (
            gate.get("consumed") is not False
            or gate.get("current_manifest_digest") != current.artifact_digest
            or gate.get("incoming_manifest_digest") != incoming.artifact_digest
            or gate.get("expected_manifest_digest") != expected.artifact_digest
            or incoming.to_dict(include_digest=True)
            != expected.to_dict(include_digest=True)
        ):
            raise ResearchOSValidationError("isolated_v11_recovery_gate_changed")
        gate["consumed"] = True

    def _verify_mainline_completion_records(
        self,
        cursor: Any,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
        m4_v2_lifecycle_verified: bool = False,
    ) -> None:
        gate = self._recovery_gate
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
                "isolated_v11_recovery_completion_gate_changed"
            )
        PostgresResearchOSRepository._verify_mainline_completion_records(
            cursor,
            control_plane_key=control_plane_key,
            manifest=manifest,
            m4_v2_lifecycle_verified=m4_v2_lifecycle_verified,
        )

    def apply_recovery(self, incoming: ControlPlaneManifest) -> Any:
        if self._recovery_gate is not None:
            raise AttestationRecoveryError("recovery_gate_reentrant")
        current = self.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        expected = recovery_manifest(current)
        if incoming.artifact_digest != expected.artifact_digest:
            raise AttestationRecoveryError("recovery_manifest_changed")
        gate: dict[str, Any] = {
            "consumed": False,
            "current_manifest_digest": current.artifact_digest,
            "incoming_manifest_digest": incoming.artifact_digest,
            "expected_manifest_digest": expected.artifact_digest,
        }
        self._recovery_gate = gate
        try:
            result = self.import_manifest(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                payload=incoming.to_dict(include_digest=True),
                source="m4-isolated-v11-failed-operator-attestation-state-recovery-v1",
            )
            if gate.get("consumed") is not True:
                raise AttestationRecoveryError("recovery_gate_not_consumed")
            return result
        finally:
            self._recovery_gate = None


def run(*, apply: bool) -> dict[str, Any]:
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise AttestationRecoveryError("dirty_worktree")
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
    repository = RecoveryRepository(context=context, source_digest=source_digest)
    current = repository.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    incoming = recovery_manifest(current)
    events = repository.list_mainline_execution_events(
        control_plane_key=contract.CONTROL_PLANE_KEY, task_key=TASK_KEY
    )
    validate_failed_events(
        events,
        repository.list_mainline_artifacts(
            control_plane_key=contract.CONTROL_PLANE_KEY,
            execution_id=FAILED_EXECUTION_ID,
        ),
    )
    old_request = AgentRequestRepository().get_request(FAILED_OPERATOR_REQUEST_KEY)
    old_executions = AgentRequestRepository().list_execution_metadata(
        FAILED_OPERATOR_REQUEST_KEY
    )
    if (
        old_request.id != FAILED_OPERATOR_REQUEST_ID
        or old_request.status is not AgentRequestStatus.FAILED
        or len(
            [item for item in old_executions if item.id == FAILED_OPERATOR_EXECUTION_ID]
        )
        != 1
        or next(
            item for item in old_executions if item.id == FAILED_OPERATOR_EXECUTION_ID
        ).status
        is not AgentExecutionStatus.FAILED
    ):
        raise AttestationRecoveryError("old_operator_failure_changed")
    governance = validate_corrected_operator_scope(
        repository=AgentRequestRepository(),
        source_digest=source_digest,
        git_commit=git_commit,
    )
    task = next(item for item in current.tasks if item.task_key == TASK_KEY)
    next_execution_id = stable_hash(
        {
            "schema": MAINLINE_EXECUTION_SCHEMA,
            "control_plane_key": contract.CONTROL_PLANE_KEY,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "input_artifact_digests": task.input_artifact_digests,
            "git_commit": git_commit,
        }
    )
    if next_execution_id == FAILED_EXECUTION_ID:
        raise AttestationRecoveryError("recovery_execution_id_not_distinct")
    imported = None
    if apply:
        imported = repository.apply_recovery(incoming)
    return {
        "schema_version": "dehps-m4-isolated-v11-attestation-recovery.v1",
        "status": "RECOVERED_TO_DRAFT" if apply else "DRY_RUN_VERIFIED",
        "apply": apply,
        "current_manifest_digest": current.artifact_digest,
        "recovered_manifest_digest": incoming.artifact_digest,
        "task_key": TASK_KEY,
        "task_digest": TASK_DIGEST,
        "failed_execution_id": FAILED_EXECUTION_ID,
        "next_execution_id": next_execution_id,
        "governance": governance,
        "import_result": None if imported is None else str(imported),
        "old_failure_preserved": True,
        "definitions_changed": False,
        "facts_changed": False,
        "other_task_states_changed": False,
        "workloads": 0,
        "smtp_calls": 0,
        "external_sends": 0,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("status", "recover"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and args.command != "recover":
        parser.error("--apply requires recover")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    print(json.dumps(run(apply=bool(args.apply)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
