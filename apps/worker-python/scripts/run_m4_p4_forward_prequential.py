from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
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
from dehps.research_os.mainline import completion_fact_execution_id
from dehps.research_os.models import (
    CompletionClassification,
    ControlPlaneManifest,
    MainlineArtifactRegistration,
    ResearchOSValidationError,
    TaskStatus,
    jsonable,
)
from dehps.research_os.repository import PostgresResearchOSRepository

CONTROL_PLANE_KEY = formal_p4.CONTROL_PLANE_KEY
ARMING_EXECUTION_ID = hashlib.sha256(
    (
        f"{formal_p4.CONTRACT_KEY}|ARMING_PREREGISTRATION|{formal_p4.CONTRACT_DIGEST}"
    ).encode()
).hexdigest()
V3_EXCLUSIVE_TASK_KEYS = frozenset(
    {
        formal_p4.EVIDENCE_TASK_KEY,
        formal_p4.DECISION_TASK_KEY,
        formal_p4.REPLAY_TASK_KEY,
        formal_p4.SUCCESSOR_P5_TASK_KEY,
    }
)
V3_EXCLUSIVE_FACTS = frozenset(
    {
        formal_p4.CONTRACT_FREEZE_FACT,
        formal_p4.EXECUTION_COMPLETE_FACT,
        formal_p4.EVIDENCE_COMPILED_FACT,
        f"{formal_p4.DECISION_TASK_KEY}:COMPLETE",
        formal_p4.PASS_TO_P5_FACT,
        formal_p4.FAIL_FACT,
        formal_p4.INVALID_FACT,
        f"{formal_p4.REPLAY_TASK_KEY}:COMPLETE",
        formal_p4.REPLAY_VERIFIED_FACT,
        f"{formal_p4.SUCCESSOR_P5_TASK_KEY}:COMPLETE",
    }
)


class FormalP4ForwardPrequentialRepository(PostgresResearchOSRepository):
    """P4-only exact import gate; the frozen base repository stays untouched."""

    _outcome_gate: dict[str, Any] | None = None

    def _verify_m4_v2_failed_global_routing_recovery_v3_import(
        self,
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
    ) -> None:
        tasks = {item.task_key: item for item in manifest.tasks}
        facts = set(manifest.facts.artifacts)
        if not V3_EXCLUSIVE_TASK_KEYS.intersection(
            tasks
        ) and not V3_EXCLUSIVE_FACTS.intersection(facts):
            return super()._verify_m4_v2_failed_global_routing_recovery_v3_import(
                cursor,
                control_plane_key=control_plane_key,
                manifest=manifest,
            )
        handled = self._verify_formal_p4_v3_import(
            cursor,
            control_plane_key=control_plane_key,
            manifest=manifest,
        )
        if handled:
            return
        super()._verify_m4_v2_failed_global_routing_recovery_v3_import(
            cursor,
            control_plane_key=control_plane_key,
            manifest=manifest,
        )

    def _verify_formal_p4_v3_import(
        self,
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
        artifact_root: Path = ROOT_DIR,
    ) -> bool:
        error = "formal_p4_v3_repository_import_changed"
        if control_plane_key != CONTROL_PLANE_KEY:
            raise ResearchOSValidationError(error)
        control = cursor.execute(
            "SELECT current_manifest_digest FROM research_os_control_planes "
            "WHERE control_plane_key = %s FOR UPDATE",
            (control_plane_key,),
        ).fetchone()
        if control is None:
            raise ResearchOSValidationError(error)
        current_row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (str(control["current_manifest_digest"]),),
        ).fetchone()
        if current_row is None:
            raise ResearchOSValidationError(error)
        current = ControlPlaneManifest.from_dict(dict(current_row["manifest_json"]))
        current_tasks = {item.task_key: item for item in current.tasks}
        current_has_v3 = formal_p4.EVIDENCE_TASK_KEY in current_tasks
        current_frozen = formal_p4.CONTRACT_FREEZE_FACT in current.facts.artifacts
        incoming_frozen = formal_p4.CONTRACT_FREEZE_FACT in manifest.facts.artifacts

        if current_has_v3 and current_frozen:
            if not incoming_frozen:
                raise ResearchOSValidationError(error)
            self._verify_post_freeze_transition(current=current, incoming=manifest)
            return False

        try:
            source = formal_p4.load_source_contract(root_dir=ROOT_DIR)
            source_digest = str(source["artifact_digest"])
            definition_payload, _ = builder.build_definition_manifest(
                current.to_dict(include_digest=True),
                source_digest=source_digest,
            )
            definition = ControlPlaneManifest.from_dict(definition_payload)
            if not current_has_v3:
                if incoming_frozen or manifest.to_dict(
                    include_digest=True
                ) != definition.to_dict(include_digest=True):
                    raise ValueError("definition")
                return True
            if not current_frozen and not incoming_frozen:
                if manifest.to_dict(include_digest=True) != definition.to_dict(
                    include_digest=True
                ):
                    raise ValueError("idempotence")
                return True
            frozen_payload, _ = builder._build_manifest(
                current.to_dict(include_digest=True),
                source_digest=source_digest,
                include_freeze_fact=True,
            )
            frozen = ControlPlaneManifest.from_dict(frozen_payload)
            if manifest.to_dict(include_digest=True) != frozen.to_dict(
                include_digest=True
            ):
                raise ValueError("freeze")
            self._verify_arming_registration(
                cursor,
                manifest=frozen,
                artifact_root=artifact_root,
            )
            return True
        except ResearchOSValidationError:
            raise
        except Exception as exc:
            raise ResearchOSValidationError(error) from exc

    @staticmethod
    def _task_state(
        manifest: ControlPlaneManifest,
        task,
    ) -> tuple[str, str | None, str | None]:
        state = manifest.task_state_by_digest[task.artifact_digest]
        return (
            state.declared_status.value,
            (
                None
                if state.completion_classification is None
                else state.completion_classification.value
            ),
            state.superseded_by_task_digest,
        )

    def _verify_post_freeze_transition(
        self,
        *,
        current: ControlPlaneManifest,
        incoming: ControlPlaneManifest,
    ) -> None:
        error = "formal_p4_v3_post_freeze_transition_changed"
        current_payload = current.to_dict(include_digest=False)
        incoming_payload = incoming.to_dict(include_digest=False)
        if (
            current_payload["schema_version"] != incoming_payload["schema_version"]
            or current_payload["goals"] != incoming_payload["goals"]
            or current.facts.evidence != incoming.facts.evidence
            or current.facts.external_events != incoming.facts.external_events
            or current.facts.authorities != incoming.facts.authorities
        ):
            raise ResearchOSValidationError(error)
        current_tasks = {item.task_key: item for item in current.tasks}
        incoming_tasks = {item.task_key: item for item in incoming.tasks}
        if set(current_tasks) != set(incoming_tasks):
            raise ResearchOSValidationError(error)

        state_changes: list[tuple[str, tuple[str, str], tuple[str, str]]] = []
        for key, old in current_tasks.items():
            new = incoming_tasks[key]
            old_payload = old.to_dict()
            new_payload = new.to_dict()
            old_state = self._task_state(current, old)
            new_state = self._task_state(incoming, new)
            if key not in formal_p4.P4_TASK_KEY_ALLOWLIST:
                if old_payload != new_payload or old_state != new_state:
                    raise ResearchOSValidationError(error)
                continue
            if old_payload != new_payload or old_state[2] != new_state[2]:
                raise ResearchOSValidationError(error)
            if old_state != new_state:
                state_changes.append((key, old_state[:2], new_state[:2]))
        if len(state_changes) > 1:
            raise ResearchOSValidationError(error)

        old_facts = set(current.facts.artifacts)
        new_facts = set(incoming.facts.artifacts)
        if not old_facts.issubset(new_facts):
            raise ResearchOSValidationError(error)
        added = new_facts - old_facts
        if state_changes:
            key, old_state, new_state = state_changes[0]
            if (
                old_state[0] == TaskStatus.DRAFT.value
                and old_state[1]
                in {None, CompletionClassification.INTEGRATION_PENDING.value}
                and new_state
                == (
                    TaskStatus.RUNNING.value,
                    CompletionClassification.INTEGRATED.value,
                )
            ):
                if added:
                    raise ResearchOSValidationError(error)
                return
            if old_state == (
                TaskStatus.RUNNING.value,
                CompletionClassification.INTEGRATED.value,
            ) and new_state == (
                TaskStatus.COMPLETED.value,
                CompletionClassification.COMPLETE.value,
            ):
                task = incoming_tasks[key]
                completion_ids = [
                    value
                    for value in added
                    if completion_fact_execution_id(task=task, fact_key=value)
                    is not None
                ]
                custom = {
                    formal_p4.EXECUTION_TASK_KEY: formal_p4.EXECUTION_COMPLETE_FACT,
                    formal_p4.EVIDENCE_TASK_KEY: formal_p4.EVIDENCE_COMPILED_FACT,
                    formal_p4.DECISION_TASK_KEY: f"{formal_p4.DECISION_TASK_KEY}:COMPLETE",
                    formal_p4.REPLAY_TASK_KEY: f"{formal_p4.REPLAY_TASK_KEY}:COMPLETE",
                }[key]
                if len(completion_ids) != 1 or added != {
                    completion_ids[0],
                    custom,
                }:
                    raise ResearchOSValidationError(error)
                return
            raise ResearchOSValidationError(error)
        if not added:
            return
        gate = self._outcome_gate
        replay_state = self._task_state(
            current,
            current_tasks[formal_p4.REPLAY_TASK_KEY],
        )
        if (
            gate is None
            or gate.get("consumed") is not False
            or gate.get("manifest_digest") != incoming.artifact_digest
            or frozenset(added) != gate.get("added_facts")
            or replay_state[:2]
            != (
                TaskStatus.COMPLETED.value,
                CompletionClassification.COMPLETE.value,
            )
            or f"{formal_p4.REPLAY_TASK_KEY}:COMPLETE" not in old_facts
        ):
            raise ResearchOSValidationError(error)
        gate["consumed"] = True

    @staticmethod
    def _verify_arming_registration(
        cursor,
        *,
        manifest: ControlPlaneManifest,
        artifact_root: Path,
    ) -> None:
        error = "formal_p4_v3_arming_registration_changed"
        tasks = [
            item
            for item in manifest.tasks
            if item.task_key == formal_p4.EXECUTION_TASK_KEY
        ]
        prereg = formal_p4.frozen_preregistration()
        if len(tasks) != 1:
            raise ResearchOSValidationError(error)
        task = tasks[0]
        expected_path = (
            "runtime/research-os/mainline/tasks/"
            f"{task.task_key}/{ARMING_EXECUTION_ID}/artifacts/"
            f"formal-p4-v3-preregistration/{prereg['artifact_digest']}/"
            "preregistration.json"
        )
        rows = cursor.execute(
            """
            SELECT registration_digest, execution_id, control_plane_key,
                   task_digest, task_key, artifact_digest, artifact_type,
                   schema_version, artifact_path, parent_digests_json,
                   git_commit, registration_json
            FROM research_os_mainline_artifacts
            WHERE control_plane_key = %s AND task_key = %s
            ORDER BY registration_digest
            """,
            (CONTROL_PLANE_KEY, task.task_key),
        ).fetchall()
        if len(rows) != 1:
            raise ResearchOSValidationError(error)
        row = dict(rows[0])
        payload = dict(row.get("registration_json") or {})
        required = {
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
        }
        if set(payload) != required:
            raise ResearchOSValidationError(error)
        registration = MainlineArtifactRegistration(
            execution_id=str(payload["execution_id"]),
            control_plane_key=str(payload["control_plane_key"]),
            task_key=str(payload["task_key"]),
            task_digest=str(payload["task_digest"]),
            artifact_digest=str(payload["artifact_digest"]),
            artifact_type=str(payload["artifact_type"]),
            schema_version=str(payload["schema_version"]),
            artifact_path=str(payload["artifact_path"]),
            parent_digests=tuple(str(item) for item in payload["parent_digests"]),
            git_commit=str(payload["git_commit"]),
        )
        exact = {
            "execution_id": ARMING_EXECUTION_ID,
            "control_plane_key": CONTROL_PLANE_KEY,
            "task_digest": task.artifact_digest,
            "task_key": task.task_key,
            "artifact_digest": prereg["artifact_digest"],
            "artifact_type": prereg["artifact_type"],
            "schema_version": prereg["schema_version"],
            "artifact_path": expected_path,
        }
        git_commit = registration.git_commit
        if (
            len(git_commit) != 40
            or any(character not in "0123456789abcdef" for character in git_commit)
            or any(str(row.get(key)) != str(value) for key, value in exact.items())
            or any(str(payload.get(key)) != str(value) for key, value in exact.items())
            or str(row.get("git_commit")) != git_commit
            or tuple(row.get("parent_digests_json") or ())
            != tuple(prereg["parent_digests"])
            or registration.parent_digests != tuple(prereg["parent_digests"])
            or str(row.get("registration_digest")) != registration.registration_digest
            or jsonable(registration) != payload
        ):
            raise ResearchOSValidationError(error)
        root = artifact_root.resolve()
        path = (root / expected_path).resolve()
        expected_bytes = (
            json.dumps(
                prereg,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
        if (
            not path.is_relative_to(root)
            or not path.is_file()
            or path.read_bytes() != expected_bytes
        ):
            raise ResearchOSValidationError(error)
        try:
            registered = formal_p4.validate_artifact(
                json.loads(path.read_text(encoding="utf-8"))
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ResearchOSValidationError(error) from exc
        if registered != prereg:
            raise ResearchOSValidationError(error)

    def _import_authoritative_outcome(
        self,
        *,
        payload: Mapping[str, Any],
        outcome_fact: str,
        typed_replay_verified: bool,
    ):
        if self._outcome_gate is not None:
            raise ResearchOSValidationError("formal_p4_v3_outcome_gate_reentrant")
        if outcome_fact not in {
            formal_p4.PASS_TO_P5_FACT,
            formal_p4.FAIL_FACT,
            formal_p4.INVALID_FACT,
        }:
            raise ResearchOSValidationError("formal_p4_v3_outcome_gate_changed")
        if not typed_replay_verified and outcome_fact != formal_p4.INVALID_FACT:
            raise ResearchOSValidationError("formal_p4_v3_outcome_gate_changed")
        added = frozenset(
            (formal_p4.REPLAY_VERIFIED_FACT, outcome_fact)
            if typed_replay_verified
            else (outcome_fact,)
        )
        manifest = ControlPlaneManifest.from_dict(dict(payload))
        self._outcome_gate = {
            "manifest_digest": manifest.artifact_digest,
            "added_facts": added,
            "consumed": False,
        }
        try:
            result = super().import_manifest(
                control_plane_key=CONTROL_PLANE_KEY,
                payload=manifest.to_dict(include_digest=True),
                source="m4-p4-v3-outcome-after-generic-and-typed-replay",
            )
            if self._outcome_gate.get("consumed") is not True:
                raise ResearchOSValidationError(
                    "formal_p4_v3_outcome_gate_not_consumed"
                )
            return result
        finally:
            self._outcome_gate = None


def _snapshot(repository: PostgresResearchOSRepository):
    manifest = repository.load_manifest(control_plane_key=CONTROL_PLANE_KEY)
    return manifest, repository.control_plane.resolve(manifest)


def compact_status(
    *, repository: PostgresResearchOSRepository | None = None
) -> dict[str, Any]:
    repository = repository or FormalP4ForwardPrequentialRepository()
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
    repository = repository or FormalP4ForwardPrequentialRepository()
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
    if not isinstance(repository, FormalP4ForwardPrequentialRepository):
        raise TypeError("formal P4 authoritative outcome repository changed")
    imported = repository._import_authoritative_outcome(
        payload=activated,
        outcome_fact=outcome_fact,
        typed_replay_verified=typed_replay_verified,
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
    repository = repository or FormalP4ForwardPrequentialRepository()
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
