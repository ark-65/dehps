from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import build_m4_p4_forward_prequential_manifest as builder
from dehps.agents.repository import AgentRequestRepository
from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2 import (
    formal_p4_forward_prequential as formal_p4,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_task_manifest,
)
from dehps.research_os.models import MainlineArtifactRegistration
from dehps.research_os.repository import PostgresResearchOSRepository

CONTROL_PLANE_KEY = formal_p4.CONTROL_PLANE_KEY
ARMING_EXECUTION_ID = hashlib.sha256(
    (
        f"{formal_p4.CONTRACT_KEY}|ARMING_PREREGISTRATION|{formal_p4.CONTRACT_DIGEST}"
    ).encode()
).hexdigest()


def _snapshot(repository: PostgresResearchOSRepository):
    manifest = repository.load_manifest(control_plane_key=CONTROL_PLANE_KEY)
    return manifest, repository.control_plane.resolve(manifest)


def compact_status(
    *, repository: PostgresResearchOSRepository | None = None
) -> dict[str, Any]:
    repository = repository or PostgresResearchOSRepository()
    repository.ensure_schema()
    manifest, snapshot = _snapshot(repository)
    by_key = {item.task_key: item.status.value for item in snapshot.resolutions}
    facts = set(manifest.facts.to_dict()["artifacts"])
    if formal_p4.EXECUTION_TASK_KEY not in by_key:
        return {"status": "NOT_REGISTERED", "formal_p4_execution": "NOT_EXECUTED"}
    p4_statuses = {
        key: by_key.get(key, "missing") for key in formal_p4.P4_TASK_KEY_ALLOWLIST
    }
    execution_status = p4_statuses[formal_p4.EXECUTION_TASK_KEY]
    supervisor = formal_p4.FormalP4ForwardPrequentialSupervisor(
        repository=repository, control_plane_key=CONTROL_PLANE_KEY
    )
    registered = [
        name for name in formal_p4.CAPABILITIES if name in supervisor.capabilities
    ]
    return {
        "status": (
            "ARMED_DEPENDENCY_WAIT"
            if execution_status == "dependency_wait"
            and formal_p4.p3.PASS_TO_P4_FACT not in facts
            else execution_status.upper()
        ),
        "formal_p4_contract": (
            "FROZEN" if formal_p4.CONTRACT_FREEZE_FACT in facts else "NOT_IMPORTED"
        ),
        "formal_p4_engineering": "COMPLETE",
        "formal_p4_capability": (
            "REGISTERED" if tuple(registered) == formal_p4.CAPABILITIES else "DRIFT"
        ),
        "formal_p4_execution": (
            "NOT_EXECUTED" if execution_status != "completed" else "COMPLETE"
        ),
        "formal_p4_tasks": p4_statuses,
        "pass_to_p4": formal_p4.p3.PASS_TO_P4_FACT in facts,
        "p4_task_key_allowlist": list(formal_p4.P4_TASK_KEY_ALLOWLIST),
        "unkeyed_dispatch_allowed": False,
        "p3_dispatch_allowed": False,
        "p5_dispatch_allowed": False,
        "successor_p5": by_key.get(formal_p4.SUCCESSOR_P5_TASK_KEY, "not_started"),
        "p5_executed": by_key.get(formal_p4.SUCCESSOR_P5_TASK_KEY) == "completed",
        "promotion_triggered": False,
    }


def cycle(
    *, apply: bool, repository: PostgresResearchOSRepository | None = None
) -> dict[str, Any]:
    repository = repository or PostgresResearchOSRepository()
    repository.ensure_schema()
    formal_p4.load_source_contract(root_dir=ROOT_DIR)
    formal_p4.verify_governance(AgentRequestRepository())
    manifest, snapshot = _snapshot(repository)
    status_by_key = {item.task_key: item.status.value for item in snapshot.resolutions}
    facts = set(manifest.facts.to_dict()["artifacts"])
    ready = [
        key
        for key in formal_p4.P4_TASK_KEY_ALLOWLIST
        if status_by_key.get(key) == "ready"
    ]
    outcome_facts = {
        formal_p4.PASS_TO_P5_FACT,
        formal_p4.FAIL_FACT,
        formal_p4.INVALID_FACT,
    }
    replay_activation_pending = (
        status_by_key.get(formal_p4.REPLAY_TASK_KEY) == "completed"
        and formal_p4.REPLAY_VERIFIED_FACT not in facts
        and not facts.intersection(outcome_facts)
    )
    if apply and not ready and replay_activation_pending:
        supervisor = formal_p4.FormalP4ForwardPrequentialSupervisor(
            repository=repository, control_plane_key=CONTROL_PLANE_KEY
        )
        generic_replay = supervisor.replay(task_key=formal_p4.REPLAY_TASK_KEY)
        activation = _activate_after_generic_replay(
            repository=repository,
            supervisor=supervisor,
            generic_replay=generic_replay,
        )
        return {
            "status": "RESUMED_POST_REPLAY_OUTCOME_ACTIVATION",
            "dispatch_performed": False,
            "workload_rerun": False,
            "generic_replay": generic_replay,
            "outcome_activation": activation,
            "p3_dispatched": False,
            "p5_dispatched": False,
            "promotion_triggered": False,
        }
    if not ready or not apply:
        result = compact_status(repository=repository)
        result.update(
            {
                "ready_p4_tasks": ready,
                "dispatch_performed": False,
                "apply_requested": apply,
            }
        )
        return result
    key = ready[0]
    if key not in formal_p4.P4_TASK_KEY_ALLOWLIST:
        raise RuntimeError("formal P4 dispatch escaped exact task-key allowlist")
    supervisor = formal_p4.FormalP4ForwardPrequentialSupervisor(
        repository=repository, control_plane_key=CONTROL_PLANE_KEY
    )
    execution = supervisor.run_once(task_key=key)
    generic_replay = supervisor.replay(task_key=key)
    outcome_activation = None
    if key == formal_p4.REPLAY_TASK_KEY:
        outcome_activation = _activate_after_generic_replay(
            repository=repository,
            supervisor=supervisor,
            generic_replay=generic_replay,
        )
    return {
        "status": "DISPATCHED_ONE_EXACT_P4_TASK",
        "task_key": key,
        "dispatch_performed": True,
        "unkeyed_dispatch": False,
        "execution_id": execution["execution_id"],
        "execution_artifact_digest": execution["execution_artifact_digest"],
        "generic_replay": generic_replay,
        "outcome_activation": outcome_activation,
        "remaining_ready_p4_tasks": ready[1:],
        "p3_dispatched": False,
        "p5_dispatched": False,
        "promotion_triggered": False,
    }


def _activate_after_generic_replay(
    *,
    repository: PostgresResearchOSRepository,
    supervisor: formal_p4.FormalP4ForwardPrequentialSupervisor,
    generic_replay: dict[str, Any],
) -> dict[str, Any]:
    """Publish the outcome only after generic replay verifies registered replay bytes."""

    if (
        generic_replay.get("status") != "REPLAY_VERIFIED"
        or generic_replay.get("task_key") != formal_p4.REPLAY_TASK_KEY
        or generic_replay.get("same_execution_identity") is not True
        or generic_replay.get("same_artifact_identity") is not True
        or generic_replay.get("manual_input_assembly") is not False
        or generic_replay.get("dispatch_performed") is not False
    ):
        raise RuntimeError("formal P4 generic replay did not verify exact identity")
    capability = formal_p4.FormalP4ForwardPrequentialCapability(
        repository=repository, root_dir=ROOT_DIR
    )
    _, replay_registration, replay = capability._completed_artifact(
        control_plane_key=CONTROL_PLANE_KEY,
        task_key=formal_p4.REPLAY_TASK_KEY,
        artifact_type=formal_p4.REPLAY_ARTIFACT_TYPE,
    )
    typed_replay_verified = replay["body"].get("status") != "P4_INVALID_EXECUTION"
    if typed_replay_verified:
        prereg, identity, execution, children, integrity_reasons = (
            capability._execution_chain_fail_closed(control_plane_key=CONTROL_PLANE_KEY)
        )
        _, _, evidence = capability._completed_artifact(
            control_plane_key=CONTROL_PLANE_KEY,
            task_key=formal_p4.EVIDENCE_TASK_KEY,
            artifact_type=formal_p4.EVIDENCE_ARTIFACT_TYPE,
        )
        _, _, decision = capability._completed_artifact(
            control_plane_key=CONTROL_PLANE_KEY,
            task_key=formal_p4.DECISION_TASK_KEY,
            artifact_type=formal_p4.DECISION_ARTIFACT_TYPE,
        )
        if integrity_reasons:
            raise RuntimeError(
                "formal P4 registered parent chain failed before activation"
            )
        expected = formal_p4.build_typed_replay(
            decision=decision,
            evidence=evidence,
            execution=execution,
            input_identity=identity,
            preregistration=prereg,
            children=children,
        )
    else:
        expected = replay
        if replay["body"].get("emitted_fact") != formal_p4.INVALID_FACT:
            raise RuntimeError("formal P4 typed replay failed without INVALID")
    if (
        replay != expected
        or replay_registration.get("artifact_digest") != replay["artifact_digest"]
    ):
        raise RuntimeError("formal P4 registered typed replay changed")
    outcome_fact = str(replay["body"]["emitted_fact"])
    if outcome_fact not in {
        formal_p4.PASS_TO_P5_FACT,
        formal_p4.FAIL_FACT,
        formal_p4.INVALID_FACT,
    }:
        raise RuntimeError("formal P4 replay outcome escaped frozen decision set")
    live = repository.export_manifest(control_plane_key=CONTROL_PLANE_KEY)
    activated, dry_run = build_additive_task_manifest(
        live_payload=live,
        new_tasks=(),
        add_artifact_facts=(
            (formal_p4.REPLAY_VERIFIED_FACT, outcome_fact)
            if typed_replay_verified
            else (outcome_fact,)
        ),
    )
    imported = repository.import_manifest(
        control_plane_key=CONTROL_PLANE_KEY,
        payload=activated,
        source="m4-p4-v3-outcome-after-generic-and-typed-replay",
    )
    return {
        "status": "AUTHORITATIVE_OUTCOME_ACTIVATED_AFTER_BOTH_REPLAYS",
        "generic_replay_execution_id": generic_replay["execution_id"],
        "typed_replay_artifact_digest": replay["artifact_digest"],
        "typed_replay_registration_digest": replay_registration["registration_digest"],
        "typed_replay_verified": typed_replay_verified,
        "outcome_fact": outcome_fact,
        "manifest_import": str(imported),
        "dry_run": dry_run,
        "p5_dispatched": False,
        "promotion_triggered": False,
    }


def _register_arming_preregistration(
    repository: PostgresResearchOSRepository,
) -> dict[str, Any]:
    source = formal_p4.load_source_contract(root_dir=ROOT_DIR)
    prereg = formal_p4.formal_preregistration(source)
    manifest = repository.load_manifest(control_plane_key=CONTROL_PLANE_KEY)
    matches = [
        item for item in manifest.tasks if item.task_key == formal_p4.EXECUTION_TASK_KEY
    ]
    if len(matches) != 1 or matches[0].input_artifact_digests != (
        str(source["artifact_digest"]),
    ):
        raise RuntimeError("formal P4 arming task definition is not imported")
    task = matches[0]
    relative = (
        "runtime/research-os/mainline/tasks/"
        f"{task.task_key}/{ARMING_EXECUTION_ID}/artifacts/"
        f"formal-p4-v3-preregistration/{prereg['artifact_digest']}/"
        "preregistration.json"
    )
    path = (ROOT_DIR / relative).resolve()
    if not path.is_relative_to(ROOT_DIR.resolve()):
        raise RuntimeError("formal P4 arming artifact escaped repository root")
    atomic_write_text(
        path,
        json.dumps(prereg, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
    )
    git_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True
    ).strip()
    registration = MainlineArtifactRegistration(
        execution_id=ARMING_EXECUTION_ID,
        control_plane_key=CONTROL_PLANE_KEY,
        task_key=task.task_key,
        task_digest=task.artifact_digest,
        artifact_digest=str(prereg["artifact_digest"]),
        artifact_type=formal_p4.PREREGISTRATION_ARTIFACT_TYPE,
        schema_version=str(prereg["schema_version"]),
        artifact_path=relative,
        parent_digests=tuple(str(item) for item in prereg["parent_digests"]),
        git_commit=git_commit,
    )
    inserted = repository.register_mainline_artifact(registration=registration)
    records = repository.list_mainline_artifacts(
        control_plane_key=CONTROL_PLANE_KEY, execution_id=ARMING_EXECUTION_ID
    )
    exact = [
        item
        for item in records
        if item.get("registration_digest") == registration.registration_digest
        and item.get("artifact_digest") == prereg["artifact_digest"]
        and item.get("execution_id") == ARMING_EXECUTION_ID
        and item.get("control_plane_key") == CONTROL_PLANE_KEY
        and item.get("task_key") == task.task_key
        and item.get("task_digest") == task.artifact_digest
        and item.get("artifact_type") == prereg["artifact_type"]
        and item.get("schema_version") == prereg["schema_version"]
        and tuple(item.get("parent_digests", ())) == tuple(prereg["parent_digests"])
        and item.get("artifact_path") == relative
    ]
    if len(exact) != 1:
        raise RuntimeError("formal P4 arming preregistration was not registered")
    return {
        "status": "REGISTERED",
        "inserted": inserted,
        "execution_id": ARMING_EXECUTION_ID,
        "registration_digest": registration.registration_digest,
        "control_plane_key": CONTROL_PLANE_KEY,
        "task_key": task.task_key,
        "contract_key": formal_p4.CONTRACT_KEY,
        "contract_digest": formal_p4.CONTRACT_DIGEST,
        "source_contract_digest": source["artifact_digest"],
        "preregistration_artifact_digest": prereg["artifact_digest"],
        "preregistration_schema_version": prereg["schema_version"],
        "preregistration_parent_digests": prereg["parent_digests"],
        "artifact_path": relative,
    }


def install_armed_manifest(
    *, apply: bool, repository: PostgresResearchOSRepository | None = None
) -> dict[str, Any]:
    repository = repository or PostgresResearchOSRepository()
    repository.ensure_schema()
    source = formal_p4.load_source_contract(root_dir=ROOT_DIR)
    formal_p4.verify_governance(AgentRequestRepository())
    live = repository.export_manifest(control_plane_key=CONTROL_PLANE_KEY)
    definition, definition_dry_run = builder.build_definition_manifest(
        live, source_digest=str(source["artifact_digest"])
    )
    if not apply:
        return {
            "status": "DRY_RUN_VERIFIED",
            "apply_requested": False,
            "definition": definition_dry_run,
            "activation": builder.activation_simulation(
                live, source_digest=str(source["artifact_digest"])
            ),
            "preregistration_registered": False,
            "freeze_fact_imported": False,
        }
    definition_import = repository.import_manifest(
        control_plane_key=CONTROL_PLANE_KEY,
        payload=definition,
        source="m4-p4-forward-prequential-v3-definition-before-freeze",
    )
    registration = _register_arming_preregistration(repository)
    registered_live = repository.export_manifest(control_plane_key=CONTROL_PLANE_KEY)
    frozen, frozen_dry_run = builder.build_frozen_manifest(
        registered_live,
        source_digest=str(source["artifact_digest"]),
        repository=repository,
        registration_execution_id=str(registration["execution_id"]),
        registration_digest=str(registration["registration_digest"]),
    )
    frozen_import = repository.import_manifest(
        control_plane_key=CONTROL_PLANE_KEY,
        payload=frozen,
        source="m4-p4-forward-prequential-v3-freeze-after-preregistration",
    )
    status = compact_status(repository=repository)
    if (
        status.get("formal_p4_contract") != "FROZEN"
        or status.get("status") != "ARMED_DEPENDENCY_WAIT"
        or status.get("formal_p4_execution") != "NOT_EXECUTED"
    ):
        raise RuntimeError("formal P4 armed import projection changed")
    return {
        "status": "ARMED_DEPENDENCY_WAIT",
        "definition_import": str(definition_import),
        "preregistration": registration,
        "freeze_import": str(frozen_import),
        "freeze_migration": frozen_dry_run,
        "projection": status,
        "formal_p4_executed": False,
        "p5_executed": False,
        "promotion_triggered": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Operate the armed successor Formal P4 V3 exact-key lane"
    )
    parser.add_argument("mode", choices=("status", "cycle", "install"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.mode == "status":
        result = compact_status()
    elif args.mode == "cycle":
        result = cycle(apply=args.apply)
    else:
        result = install_armed_manifest(apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
