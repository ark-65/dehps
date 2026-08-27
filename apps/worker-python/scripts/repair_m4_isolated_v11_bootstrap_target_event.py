from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[3]
WORKER_DIR = ROOT_DIR / "apps" / "worker-python"
SCRIPT_DIR = Path(__file__).resolve().parent
for path in (WORKER_DIR, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

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
    DependencyFacts,
    TaskStatus,
)
from run_m4_isolated_24h_challenger_v11 import (
    IsolatedChallengerRepository,
    _latest_history_identity,
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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("repair",))
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    print(json.dumps(run(apply=bool(args.apply)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
