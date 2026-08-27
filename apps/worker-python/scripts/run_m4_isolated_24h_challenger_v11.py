from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import build_m4_isolated_24h_challenger_v11_manifest as builder
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2 import (
    forward_prequential_confirmatory as formal_p3,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_artifacts as artifacts,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_contract as contract,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_mainline as mainline,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_reporting as reporting,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_search as search,
)
from dehps.research_os.models import (
    ControlPlaneManifest,
    ResearchOSValidationError,
    TaskStatus,
)
from dehps.research_os.repository import PostgresResearchOSRepository

_MAINLINE_FACT = re.compile(
    r"^mainline-execution:m4-isolated-24h-challenger-v11-[^:]+:"
    r"[0-9a-f]{64}:[0-9a-f]{64}:completed$"
)
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
KNOWN_EXTERNAL_EVENTS = frozenset(
    {
        "TARGET_PROJECTION_INPUT",
        "RESOURCE_QUIESCENT_60S",
        "SELECTION_CUTOFF",
        "FREEZE_DEADLINE",
        "PREDRAW_SEND",
        "AUDITED_DRAW",
        "DAILY_SEND",
        "INCIDENT_OPEN",
        "CAPACITY_BELOW_18",
    }
)
KNOWN_AUTHORITIES = frozenset(
    {builder.RESEARCH_APPROVAL_AUTHORITY, builder.OPERATOR_CONFIGURATION_AUTHORITY}
)
PREDECESSOR_BOOTSTRAP_SOURCE_DIGEST = (
    "99f058e6df7e36ebd07bb411c7c1960989367230cb0a9344619442466112460a"
)
APPROVED_BOOTSTRAP_PREDECESSOR_SOURCE_DIGESTS = frozenset(
    {
        PREDECESSOR_BOOTSTRAP_SOURCE_DIGEST,
        "a13889100c0f83a315f5e3997ce53ac1fb8a86b661bcd1d522d3cec59adf4fc0",
        "1d3a7766dfd7a3c09fd7cca0b54ec15ce154f5234bf1bbb97e61c63d55c92ada",
        "41d3c7431c29ae7c8af71a8b09653df5f28ed02954206835278f2e20dc7082cd",
    }
)
LIVE_PARTIAL_PREDECESSOR_SOURCE_DIGEST = (
    "38ea4d38e66558f30eb4c8660555ca35dd584aa3de02801fe6f6075d09ffaff1"
)
LIVE_PARTIAL_COMPLETED_SOURCE_DIGESTS = frozenset(
    {
        LIVE_PARTIAL_PREDECESSOR_SOURCE_DIGEST,
        "45cd0aff1964f603ffb698da019a9803681dbe480c7bee9a322a592a05b79ffc",
        "fb37933e24cc32677b13909e9f4689605b20eaf635a06ed364a4401ee768124c",
        "f067bc89f60826c15793e1ab6325a3dce088dd7c2af3e1c99e984d3aada50dd1",
        "5452fc522812220b6654c2bb8e54b8844b0c2fdab251d392c2af8de501e659ec",
    }
)
LIVE_PARTIAL_FROZEN_GOAL_DIGEST = (
    "b13054b699c75325c3a0fbb27ccc697e0a3176568140a7f0d5e59c9aa362d69a"
)


class IsolatedRunnerError(contract.IsolatedChallengerContractError):
    pass


class IsolatedChallengerRepository(PostgresResearchOSRepository):
    """Exact fail-closed repository gate for the independent V11 control plane."""

    def __init__(self, *, context: Mapping[str, str], source_digest: str) -> None:
        super().__init__()
        self.context = dict(context)
        self.source_digest = contract.require_digest(
            source_digest, field="source_digest"
        )
        self._fact_gate: dict[str, Any] | None = None
        self._definition_gate: dict[str, Any] | None = None
        self._bootstrap_rebind_gate: dict[str, Any] | None = None

    def _expected_definition(
        self,
        *,
        operator_authorized: bool,
        context: Mapping[str, str] | None = None,
        source_digest: str | None = None,
    ) -> ControlPlaneManifest:
        payload, _ = builder.build_bootstrap_manifest(
            context=dict(context or self.context),
            source_digest=source_digest or self.source_digest,
            operator_configuration_authorized=operator_authorized,
        )
        return ControlPlaneManifest.from_dict(payload)

    @staticmethod
    def _definitions(manifest: ControlPlaneManifest) -> tuple[Any, ...]:
        return tuple(item.to_dict() for item in manifest.goals)

    def _verify_isolated_task_definition(
        self,
        task: Any,
        *,
        state: Any,
        artifact_facts: frozenset[str],
        partial_live_rebind: bool,
    ) -> None:
        try:
            metric = json.loads(task.metric_contract)
            raw_context = metric["render_context"]
            bound_source_digest = contract.require_digest(
                metric["source_contract_digest"], field="task_source_contract_digest"
            )
            normalized = contract.render_context(
                source_max_issue=str(raw_context["source_max_issue"]),
                source_max_draw_date=str(raw_context["source_max_draw_date"]),
                target_issue=str(raw_context["target_issue"]),
                target_draw_date=str(raw_context["target_draw_date"]),
                batch_seq=int(raw_context["batch_seq"]),
                epoch_date=str(raw_context["epoch_date"]),
                minute=str(raw_context["minute"]),
                incident_id=str(raw_context["incident_id"]),
                incident_reason_code=str(raw_context["incident_reason_code"]),
                incident_offending_digest=str(raw_context["incident_offending_digest"]),
                cut_checkpoint_ref=str(raw_context["cut_checkpoint_ref"]),
                projection_time=str(raw_context["projection_time"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ResearchOSValidationError(
                "isolated_v11_task_context_changed"
            ) from exc
        if dict(raw_context) != normalized:
            raise ResearchOSValidationError("isolated_v11_task_context_changed")
        if bound_source_digest != self.source_digest:
            completion_prefix = (
                f"mainline-execution:{task.task_key}:{task.artifact_digest}:"
            )
            if (
                bound_source_digest not in LIVE_PARTIAL_COMPLETED_SOURCE_DIGESTS
                or state.declared_status is not TaskStatus.COMPLETED
                or not any(
                    fact.startswith(completion_prefix) and fact.endswith(":completed")
                    for fact in artifact_facts
                )
            ):
                raise ResearchOSValidationError(
                    "isolated_v11_historical_task_source_changed"
                )
        expected_payload, _ = builder.build_manifest(
            context=normalized,
            source_digest=bound_source_digest,
            operator_configuration_authorized=True,
            simulation_events=False,
        )
        expected = ControlPlaneManifest.from_dict(expected_payload)
        matches = [item for item in expected.tasks if item.task_key == task.task_key]
        if len(matches) != 1:
            raise ResearchOSValidationError("isolated_v11_task_definition_changed")
        expected_task = matches[0]
        if partial_live_rebind:
            expected_task = replace(
                expected_task, goal_digest=LIVE_PARTIAL_FROZEN_GOAL_DIGEST
            )
        if expected_task.artifact_digest != task.artifact_digest:
            raise ResearchOSValidationError("isolated_v11_task_definition_changed")

    def _verify_exact_transition(self, incoming: ControlPlaneManifest) -> None:
        if len(incoming.tasks) != len({item.task_key for item in incoming.tasks}):
            raise ResearchOSValidationError("isolated_v11_task_set_changed")
        bound_sources = {
            str(json.loads(task.metric_contract).get("source_contract_digest") or "")
            for task in incoming.tasks
        }
        historical_source_present = bool(
            (bound_sources & LIVE_PARTIAL_COMPLETED_SOURCE_DIGESTS)
            - {self.source_digest}
        )
        partial_live_rebind = historical_source_present and (
            self.source_digest in bound_sources
        )
        if historical_source_present and (
            not partial_live_rebind
            or not bound_sources.issubset(
                LIVE_PARTIAL_COMPLETED_SOURCE_DIGESTS | {self.source_digest}
            )
        ):
            raise ResearchOSValidationError(
                "isolated_v11_partial_live_source_set_changed"
            )
        for task in incoming.tasks:
            self._verify_isolated_task_definition(
                task,
                state=incoming.task_state_by_digest[task.artifact_digest],
                artifact_facts=incoming.facts.artifacts,
                partial_live_rebind=partial_live_rebind,
            )
        operator_authorized = (
            builder.OPERATOR_CONFIGURATION_AUTHORITY in incoming.facts.authorities
        )
        expected = self._expected_definition(operator_authorized=operator_authorized)
        if (
            not incoming.facts.evidence.issubset(frozenset())
            or not incoming.facts.external_events.issubset(KNOWN_EXTERNAL_EVENTS)
            or not incoming.facts.authorities.issubset(KNOWN_AUTHORITIES)
            or builder.RESEARCH_APPROVAL_AUTHORITY not in incoming.facts.authorities
        ):
            raise ResearchOSValidationError("isolated_v11_nonartifact_facts_changed")
        try:
            current = self.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        except ResearchOSValidationError as exc:
            if "control plane not found" not in str(exc):
                raise
            if (
                self._definitions(incoming) != self._definitions(expected)
                or incoming.facts.artifacts
                or incoming.facts.external_events
                or {item.artifact_digest for item in incoming.tasks}
                != {item.artifact_digest for item in expected.tasks}
            ):
                raise ResearchOSValidationError("isolated_v11_initial_facts_changed")
            return
        rebind_gate = self._bootstrap_rebind_gate
        if rebind_gate is not None:
            if (
                rebind_gate.get("consumed") is not False
                or rebind_gate.get("current_manifest_digest") != current.artifact_digest
                or rebind_gate.get("incoming_manifest_digest")
                != incoming.artifact_digest
                or rebind_gate.get("current_manifest")
                != current.to_dict(include_digest=True)
                or rebind_gate.get("incoming_manifest")
                != incoming.to_dict(include_digest=True)
            ):
                raise ResearchOSValidationError(
                    "isolated_v11_bootstrap_rebind_gate_changed"
                )
            rebind_gate["consumed"] = True
            return
        if self._definitions(current) != self._definitions(incoming):
            raise ResearchOSValidationError("isolated_v11_goal_transition_changed")
        current_tasks = {item.task_key: item for item in current.tasks}
        incoming_tasks = {item.task_key: item for item in incoming.tasks}
        if not set(current_tasks).issubset(incoming_tasks) or any(
            incoming_tasks[key].artifact_digest != task.artifact_digest
            for key, task in current_tasks.items()
        ):
            raise ResearchOSValidationError("isolated_v11_task_definition_regression")
        added_tasks = set(incoming_tasks) - set(current_tasks)
        added_events = set(incoming.facts.external_events) - set(
            current.facts.external_events
        )
        if added_tasks or added_events:
            gate = self._definition_gate
            if (
                gate is None
                or gate.get("consumed") is not False
                or gate.get("manifest_digest") != incoming.artifact_digest
                or gate.get("added_task_keys") != frozenset(added_tasks)
                or gate.get("added_external_events") != frozenset(added_events)
            ):
                raise ResearchOSValidationError("isolated_v11_definition_gate_changed")
            gate["consumed"] = True
        if (
            not current.facts.artifacts.issubset(incoming.facts.artifacts)
            or not current.facts.external_events.issubset(
                incoming.facts.external_events
            )
            or not current.facts.authorities.issubset(incoming.facts.authorities)
        ):
            raise ResearchOSValidationError("isolated_v11_fact_regression")
        current_states = current.task_state_by_digest
        incoming_states = incoming.task_state_by_digest
        state_changes: list[tuple[str, str, str]] = []
        for task in current.tasks:
            old = current_states[task.artifact_digest]
            new = incoming_states[task.artifact_digest]
            if old != new:
                state_changes.append(
                    (
                        task.task_key,
                        old.declared_status.value,
                        new.declared_status.value,
                    )
                )
        if len(state_changes) > 1:
            raise ResearchOSValidationError("isolated_v11_multi_task_state_change")
        if state_changes:
            _, old, new = state_changes[0]
            if (old, new) not in {
                (TaskStatus.DRAFT.value, TaskStatus.RUNNING.value),
                (TaskStatus.RUNNING.value, TaskStatus.COMPLETED.value),
                (TaskStatus.RUNNING.value, TaskStatus.FAILED.value),
            }:
                raise ResearchOSValidationError("isolated_v11_task_state_regression")
        if (added_tasks or added_events) and state_changes:
            raise ResearchOSValidationError("isolated_v11_extension_changed_task_state")
        added = set(incoming.facts.artifacts) - set(current.facts.artifacts)
        mainline_facts = {item for item in added if _MAINLINE_FACT.fullmatch(item)}
        gated_facts = added - mainline_facts
        if mainline_facts and not state_changes:
            raise ResearchOSValidationError("isolated_v11_orphan_completion_fact")
        if gated_facts:
            gate = self._fact_gate
            if (
                gate is None
                or gate.get("consumed") is not False
                or gate.get("manifest_digest") != incoming.artifact_digest
                or gate.get("added_facts") != frozenset(gated_facts)
                or state_changes
            ):
                raise ResearchOSValidationError("isolated_v11_fact_gate_changed")
            gate["consumed"] = True

    def _verify_mainline_completion_records(
        self,
        cursor: Any,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
        m4_v2_lifecycle_verified: bool = False,
    ) -> None:
        if control_plane_key != contract.CONTROL_PLANE_KEY:
            raise ResearchOSValidationError("isolated_v11_control_plane_changed")
        row = cursor.execute(
            "SELECT current_manifest_digest FROM research_os_control_planes "
            "WHERE control_plane_key=%s",
            (control_plane_key,),
        ).fetchone()
        if row is not None:
            stored = cursor.execute(
                "SELECT manifest_json FROM research_os_manifests "
                "WHERE manifest_digest=%s",
                (str(row["current_manifest_digest"]),),
            ).fetchone()
            if stored is None:
                raise ResearchOSValidationError("isolated_v11_current_manifest_missing")
            current = ControlPlaneManifest.from_dict(dict(stored["manifest_json"]))
            rebind_gate = self._bootstrap_rebind_gate
            if rebind_gate is not None:
                if (
                    rebind_gate.get("consumed") is not True
                    or rebind_gate.get("current_manifest_digest")
                    != current.artifact_digest
                    or rebind_gate.get("incoming_manifest_digest")
                    != manifest.artifact_digest
                    or rebind_gate.get("current_manifest")
                    != current.to_dict(include_digest=True)
                    or rebind_gate.get("incoming_manifest")
                    != manifest.to_dict(include_digest=True)
                ):
                    raise ResearchOSValidationError(
                        "isolated_v11_bootstrap_rebind_completion_gate_changed"
                    )
                PostgresResearchOSRepository._verify_mainline_completion_records(
                    cursor,
                    control_plane_key=control_plane_key,
                    manifest=manifest,
                    m4_v2_lifecycle_verified=m4_v2_lifecycle_verified,
                )
                return
            current_tasks = {item.task_key: item for item in current.tasks}
            incoming_tasks = {item.task_key: item for item in manifest.tasks}
            if not set(current_tasks).issubset(incoming_tasks) or any(
                incoming_tasks[key].artifact_digest != value.artifact_digest
                for key, value in current_tasks.items()
            ):
                raise ResearchOSValidationError(
                    "isolated_v11_completion_task_definition_changed"
                )
            state_changes = []
            for key, task in current_tasks.items():
                before = current.task_state_by_digest[task.artifact_digest]
                after = manifest.task_state_by_digest[task.artifact_digest]
                if before != after:
                    state_changes.append(
                        (
                            key,
                            before.declared_status.value,
                            after.declared_status.value,
                        )
                    )
            added_facts = set(manifest.facts.artifacts) - set(current.facts.artifacts)
            if state_changes:
                if len(state_changes) != 1:
                    raise ResearchOSValidationError(
                        "isolated_v11_atomic_completion_transition_changed"
                    )
                transition = state_changes[0][1:]
                if transition in {("draft", "running"), ("running", "failed")}:
                    if added_facts:
                        raise ResearchOSValidationError(
                            "isolated_v11_atomic_completion_transition_changed"
                        )
                elif transition == ("running", "completed"):
                    if (
                        len(added_facts) != 1
                        or _MAINLINE_FACT.fullmatch(next(iter(added_facts))) is None
                    ):
                        raise ResearchOSValidationError(
                            "isolated_v11_atomic_completion_transition_changed"
                        )
                else:
                    raise ResearchOSValidationError(
                        "isolated_v11_atomic_completion_transition_changed"
                    )
            elif added_facts:
                gate = self._fact_gate
                if (
                    gate is None
                    or gate.get("consumed") is not True
                    or gate.get("manifest_digest") != manifest.artifact_digest
                    or gate.get("added_facts") != frozenset(added_facts)
                ):
                    raise ResearchOSValidationError(
                        "isolated_v11_completion_fact_gate_changed"
                    )
        PostgresResearchOSRepository._verify_mainline_completion_records(
            cursor,
            control_plane_key=control_plane_key,
            manifest=manifest,
            m4_v2_lifecycle_verified=m4_v2_lifecycle_verified,
        )

    def import_bootstrap_manifest(self, payload: Mapping[str, Any]) -> tuple[Any, str]:
        incoming = ControlPlaneManifest.from_dict(dict(payload))
        try:
            current = self.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        except ResearchOSValidationError as exc:
            if "control plane not found" not in str(exc):
                raise
            result = self.import_manifest(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                payload=incoming.to_dict(include_digest=True),
                source="m4-isolated-24h-challenger-v11-operator-install",
            )
            return result, incoming.artifact_digest
        if current.artifact_digest == incoming.artifact_digest:
            result = self.import_manifest(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                payload=incoming.to_dict(include_digest=True),
                source="m4-isolated-24h-challenger-v11-operator-install",
            )
            return result, incoming.artifact_digest
        if self._bootstrap_rebind_gate is not None:
            raise ResearchOSValidationError(
                "isolated_v11_bootstrap_rebind_gate_reentrant"
            )
        current_contexts = tuple(_task_context(task) for task in current.tasks)
        incoming_contexts = {
            json.dumps(_task_context(task), sort_keys=True, separators=(",", ":"))
            for task in incoming.tasks
        }
        if not current_contexts or len(incoming_contexts) != 1:
            raise ResearchOSValidationError(
                "isolated_v11_bootstrap_rebind_context_changed"
            )
        incoming_context = json.loads(next(iter(incoming_contexts)))
        target_fields = (
            "source_max_issue",
            "source_max_draw_date",
            "target_issue",
            "target_draw_date",
        )
        incoming_target = tuple(incoming_context[key] for key in target_fields)
        if any(
            tuple(item[key] for key in target_fields) != incoming_target
            for item in current_contexts
        ):
            raise ResearchOSValidationError(
                "isolated_v11_bootstrap_rebind_target_changed"
            )

        def rebuild_task_set(source_digest: str) -> ControlPlaneManifest:
            base = self._expected_definition(
                operator_authorized=True,
                context=current_contexts[0],
                source_digest=source_digest,
            )
            tasks = []
            states = []
            for stored, item_context in zip(
                current.tasks, current_contexts, strict=True
            ):
                expected_payload, _ = builder.build_manifest(
                    context=item_context,
                    source_digest=source_digest,
                    operator_configuration_authorized=True,
                    simulation_events=False,
                )
                expected = ControlPlaneManifest.from_dict(expected_payload)
                if (
                    expected.goals != base.goals
                    or expected.goal_states != base.goal_states
                ):
                    raise ResearchOSValidationError(
                        "isolated_v11_bootstrap_rebind_goal_changed"
                    )
                matches = tuple(
                    task for task in expected.tasks if task.task_key == stored.task_key
                )
                if len(matches) != 1:
                    raise ResearchOSValidationError(
                        "isolated_v11_bootstrap_rebind_task_changed"
                    )
                task = matches[0]
                tasks.append(task)
                states.append(expected.task_state_by_digest[task.artifact_digest])
            return ControlPlaneManifest(
                goals=base.goals,
                tasks=tuple(tasks),
                goal_states=base.goal_states,
                task_states=tuple(states),
                facts=base.facts,
                schema_version=base.schema_version,
            )

        predecessor_matches = tuple(
            candidate
            for candidate in (
                rebuild_task_set(predecessor_source_digest)
                for predecessor_source_digest in sorted(
                    APPROVED_BOOTSTRAP_PREDECESSOR_SOURCE_DIGESTS
                )
            )
            if current.to_dict(include_digest=True)
            == candidate.to_dict(include_digest=True)
        )
        expected_incoming = rebuild_task_set(self.source_digest)
        live_incoming = self._expected_definition(
            operator_authorized=True,
            context=incoming_context,
        )
        if (
            len(predecessor_matches) != 1
            or incoming.to_dict(include_digest=True)
            != live_incoming.to_dict(include_digest=True)
            or len(current.tasks) < 14
            or len(expected_incoming.tasks) != len(current.tasks)
            or any(
                state.declared_status is not TaskStatus.DRAFT
                for state in current.task_states
            )
            or current.facts.artifacts
            or current.facts.evidence
            or current.facts.external_events
            or current.facts.authorities != predecessor_matches[0].facts.authorities
            or self.list_mainline_execution_event_metadata(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                task_keys=tuple(task.task_key for task in current.tasks),
            )
        ):
            raise ResearchOSValidationError(
                "isolated_v11_bootstrap_rebind_precondition_changed"
            )
        self._bootstrap_rebind_gate = {
            "current_manifest_digest": current.artifact_digest,
            "incoming_manifest_digest": expected_incoming.artifact_digest,
            "current_manifest": current.to_dict(include_digest=True),
            "incoming_manifest": expected_incoming.to_dict(include_digest=True),
            "consumed": False,
        }
        try:
            result = self.import_manifest(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                payload=expected_incoming.to_dict(include_digest=True),
                source="m4-isolated-24h-challenger-v11-exact-bootstrap-rebind",
            )
            if self._bootstrap_rebind_gate.get("consumed") is not True:
                raise ResearchOSValidationError(
                    "isolated_v11_bootstrap_rebind_gate_not_consumed"
                )
            return result, expected_incoming.artifact_digest
        finally:
            self._bootstrap_rebind_gate = None

    def import_manifest(
        self,
        *,
        control_plane_key: str,
        payload: dict[str, Any],
        source: str = "native",
    ):
        if control_plane_key != contract.CONTROL_PLANE_KEY:
            raise ResearchOSValidationError("isolated_v11_control_plane_changed")
        incoming = ControlPlaneManifest.from_dict(payload)
        self._verify_exact_transition(incoming)
        return super().import_manifest(
            control_plane_key=control_plane_key, payload=payload, source=source
        )

    def import_verified_facts(self, facts: Sequence[str]):
        if not facts or len(facts) != len(set(facts)):
            raise ResearchOSValidationError("isolated_v11_fact_delta_invalid")
        live = self.export_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        payload = builder.manifest_with_facts(live, add_artifact_facts=facts)
        manifest = ControlPlaneManifest.from_dict(payload)
        self._fact_gate = {
            "manifest_digest": manifest.artifact_digest,
            "added_facts": frozenset(facts),
            "consumed": False,
        }
        try:
            result = self.import_manifest(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                payload=payload,
                source="isolated-v11-after-typed-and-generic-replay",
            )
            if self._fact_gate.get("consumed") is not True:
                raise ResearchOSValidationError("isolated_v11_fact_gate_not_consumed")
            return result
        finally:
            self._fact_gate = None

    def import_extension(self, payload: Mapping[str, Any]):
        incoming = ControlPlaneManifest.from_dict(dict(payload))
        current = self.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        added = {item.task_key for item in incoming.tasks} - {
            item.task_key for item in current.tasks
        }
        added_events = set(incoming.facts.external_events) - set(
            current.facts.external_events
        )
        if not added and not added_events:
            return None
        self._definition_gate = {
            "manifest_digest": incoming.artifact_digest,
            "added_task_keys": frozenset(added),
            "added_external_events": frozenset(added_events),
            "consumed": False,
        }
        try:
            result = self.import_manifest(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                payload=incoming.to_dict(include_digest=True),
                source="m4-isolated-v11-exact-task-extension",
            )
            if self._definition_gate.get("consumed") is not True:
                raise ResearchOSValidationError(
                    "isolated_v11_definition_gate_not_consumed"
                )
            return result
        finally:
            self._definition_gate = None


def _p3_source_identity() -> dict[str, Any]:
    source = formal_p3.load_source_contract(root_dir=ROOT_DIR)
    if source["artifact_digest"] != contract.FORMAL_P3_SOURCE_DIGEST:
        raise IsolatedRunnerError("formal_p3_source_digest_changed")
    return {
        "artifact_digest": source["artifact_digest"],
        "source_set_digest": source["source_set_digest"],
        "entries": [
            (item["path"], item["sha256"]) for item in source["source_entries"]
        ],
    }


def _resource_observation() -> dict[str, Any]:
    command = [
        "systemctl",
        "--user",
        "show",
        contract.FORMAL_P3_UNIT,
        "--property=LoadState,ActiveState,SubState,MainPID,ControlPID",
        "--no-pager",
    ]
    observed_ns = time.monotonic_ns()
    try:
        result = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=2
        )
    except (OSError, subprocess.TimeoutExpired):
        return {
            "query_ok": False,
            "LoadState": None,
            "ActiveState": None,
            "SubState": None,
            "MainPID": None,
            "ControlPID": None,
            "observed_monotonic_ns": observed_ns,
        }
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in values:
            return {
                "query_ok": False,
                "LoadState": None,
                "ActiveState": None,
                "SubState": None,
                "MainPID": None,
                "ControlPID": None,
                "observed_monotonic_ns": observed_ns,
            }
        values[key] = value
    required = {"LoadState", "ActiveState", "SubState", "MainPID", "ControlPID"}
    query_ok = result.returncode == 0 and set(values) == required
    try:
        main_pid = int(values.get("MainPID", "-1"))
        control_pid = int(values.get("ControlPID", "-1"))
    except ValueError:
        query_ok = False
        main_pid = control_pid = -1
    return {
        "query_ok": query_ok,
        "LoadState": values.get("LoadState"),
        "ActiveState": values.get("ActiveState"),
        "SubState": values.get("SubState"),
        "MainPID": main_pid,
        "ControlPID": control_pid,
        "observed_monotonic_ns": observed_ns,
    }


def _continuous_quiescence(*, seconds: float = 60.0) -> dict[str, Any]:
    started = time.monotonic()
    last: dict[str, Any] | None = None
    while True:
        last = _resource_observation()
        if contract.formal_p3_activity_state(last) != "QUIESCENT":
            raise IsolatedRunnerError("formal_p3_not_continuously_quiescent")
        elapsed = time.monotonic() - started
        if elapsed >= seconds:
            return last
        time.sleep(min(1.0, seconds - elapsed))


def _latest_history_identity() -> tuple[str, str]:
    repository = PostgresResearchOSRepository()
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        rows = cursor.execute(
            "SELECT issue,draw_date FROM ssq_history "
            "WHERE issue=(SELECT MAX(issue) FROM ssq_history) ORDER BY id"
        ).fetchall()
    if not rows:
        raise IsolatedRunnerError("ssq_history_empty")
    if len(rows) != 1 or rows[0][1] is None:
        raise IsolatedRunnerError("ssq_history_latest_identity_changed")
    issue = contract.require_issue(rows[0][0])
    draw_date = contract.require_history_draw_date(
        rows[0][1], field="source_max_draw_date"
    ).isoformat()
    return issue, draw_date


def _task_context(task: Any) -> dict[str, str]:
    try:
        metric = json.loads(task.metric_contract)
        raw = metric["render_context"]
        context = contract.render_context(
            source_max_issue=str(raw["source_max_issue"]),
            source_max_draw_date=str(raw["source_max_draw_date"]),
            target_issue=str(raw["target_issue"]),
            target_draw_date=str(raw["target_draw_date"]),
            batch_seq=int(raw["batch_seq"]),
            epoch_date=str(raw["epoch_date"]),
            minute=str(raw["minute"]),
            incident_id=str(raw["incident_id"]),
            incident_reason_code=str(raw["incident_reason_code"]),
            incident_offending_digest=str(raw["incident_offending_digest"]),
            cut_checkpoint_ref=str(raw["cut_checkpoint_ref"]),
            projection_time=str(raw["projection_time"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise IsolatedRunnerError("task_render_context_changed") from exc
    if context != dict(raw):
        raise IsolatedRunnerError("task_render_context_changed")
    return context


def _issue_exists(repository: PostgresResearchOSRepository, *, issue: str) -> bool:
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        return bool(
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM ssq_history WHERE issue=%s)",
                (issue,),
            ).fetchone()[0]
        )


def _scheduled_minute(now: datetime, scheduled: datetime) -> bool:
    return scheduled <= now < scheduled + timedelta(minutes=1)


def _delivery_absent(
    *,
    now: datetime,
    scheduled: datetime,
    stop_at: datetime,
    delivery_task_key: str,
    facts: set[str],
) -> bool:
    if not scheduled + timedelta(minutes=1) <= now < stop_at:
        return False
    return (
        f"{delivery_task_key}:SENT" not in facts
        and f"{delivery_task_key}:UNCERTAIN" not in facts
    )


def _latest_registered_health_artifact(
    *,
    repository: IsolatedChallengerRepository,
    manifest: ControlPlaneManifest,
    facts: set[str],
    before: datetime,
    context: Mapping[str, str],
) -> dict[str, Any]:
    candidates: list[tuple[str, str]] = []
    before_minute = before.strftime("%Y%m%d%H%M")
    for task in manifest.tasks:
        metric = json.loads(task.metric_contract)
        if metric.get("task_template") != "runtime_health":
            continue
        item_context = _task_context(task)
        minute = item_context["minute"]
        if minute < before_minute and f"{task.task_key}:HEALTH_RECORDED" in facts:
            candidates.append((minute, task.task_key))
    if not candidates:
        return mainline._unique_type(
            mainline.load_completed_task_artifacts(
                repository=repository,
                root_dir=ROOT_DIR,
                task_key=contract.task_template_by_name("preregistration").key(context),
            ),
            "M4IsolatedPreregistrationV11",
        )
    _, task_key = max(candidates)
    return mainline._unique_type(
        mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=task_key,
        ),
        "M4IsolatedRuntimeHealthV11",
    )


def _roll_forward(
    *,
    repository: IsolatedChallengerRepository,
    context: Mapping[str, str],
    source_digest: str,
    now: datetime | None = None,
) -> None:
    now = (now or datetime.now(contract.TIMEZONE)).astimezone(contract.TIMEZONE)
    current = repository.export_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    manifest = ControlPlaneManifest.from_dict(current)
    facts = set(manifest.facts.artifacts)
    task_keys = {item.task_key for item in manifest.tasks}
    names: set[str] = {"runtime_health"}
    events: set[str] = set()

    target_key = contract.task_template_by_name("target_issue_projection").key(context)
    if target_key not in task_keys:
        names.update({"target_issue_projection", "history_snapshot"})
        events.add("TARGET_PROJECTION_INPUT")

    epoch_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        daily_batches = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.registration_batches "
                "WHERE epoch_date=%s",
                (epoch_start.date(),),
            ).fetchone()[0]
        )
        issue_batches = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.registration_batches "
                "WHERE target_issue=%s",
                (context["target_issue"],),
            ).fetchone()[0]
        )
        head = cursor.execute(
            "SELECT registration_seq,m_total FROM m4_isolated_v11.multiplicity_head "
            "WHERE singleton=TRUE"
        ).fetchone()
    if head is None:
        raise IsolatedRunnerError("multiplicity_head_missing")
    latest_completed_batch = -1
    for task in manifest.tasks:
        metric = json.loads(task.metric_contract)
        if metric.get("task_template") != "search_checkpoint_replay":
            continue
        item_context = _task_context(task)
        fact = f"{task.task_key}:REGISTERED_REPLAY_VERIFIED"
        if fact in facts:
            latest_completed_batch = max(
                latest_completed_batch, int(item_context["batch_seq"])
            )
    next_batch = latest_completed_batch + 1
    next_context = {
        **dict(context),
        "batch_seq": f"{next_batch:012d}",
        "epoch_date": now.strftime("%Y%m%d"),
        "minute": now.strftime("%Y%m%d%H%M"),
    }
    next_batch_key = contract.task_template_by_name("search_batch").key(next_context)
    target_schedule = contract.schedule_for_issue(
        context["target_issue"], target_draw_date=context["target_draw_date"]
    )
    # The frozen retry path can consume three 1,800-second attempts plus
    # quiescence and process-termination grace.  Stop admitting new batches two
    # hours before the scientific cut so the minute runner remains available
    # for the 16:40/16:45/17:00 freeze and mail chain.
    search_pause_start = target_schedule["selection_cutoff"] - timedelta(hours=2)
    search_pause_end = target_schedule["predraw_send"] + timedelta(minutes=1)
    daily_send_for_pause = now.replace(
        hour=contract.DAILY_SEND_TIME.hour,
        minute=contract.DAILY_SEND_TIME.minute,
        second=0,
        microsecond=0,
    )
    official_draw = datetime.combine(
        contract.require_draw_date(
            context["target_draw_date"], field="target_draw_date"
        ),
        contract.OFFICIAL_DRAW_TIME,
        contract.TIMEZONE,
    )
    search_temporarily_paused = bool(
        search_pause_start <= now < search_pause_end
        or daily_send_for_pause - timedelta(hours=2)
        <= now
        < daily_send_for_pause + timedelta(minutes=15)
        or official_draw - timedelta(hours=2)
        <= now
        < official_draw + timedelta(hours=2)
    )
    add_search = (
        contract.MAIL_CONFIGURATION_FACT in facts
        and next_batch_key not in task_keys
        and not search_temporarily_paused
        and daily_batches < contract.DAILY_BATCH_LIMIT
        and issue_batches < contract.ISSUE_BATCH_LIMIT
        and int(head[1]) + contract.ATTEMPTS_PER_BATCH
        <= contract.LIFETIME_MULTIPLICITY_LIMIT
    )

    daily_send = daily_send_for_pause
    if _scheduled_minute(now, daily_send):
        names.update(builder.DAILY_TEMPLATE_NAMES)
        events.add("DAILY_SEND")

    incident_context: dict[str, str] | None = None
    has_open_incident = any(
        fact.startswith("m4-isolated-24h-challenger-v11-incident-")
        and fact.endswith("-open:OPEN")
        for fact in facts
    )
    latest_health: dict[str, Any] | None = None
    if contract.FREEZE_FACT in facts:
        latest_health = _latest_registered_health_artifact(
            repository=repository,
            manifest=manifest,
            facts=facts,
            before=now,
            context=context,
        )
    if contract.MAIL_CONFIGURATION_FACT in facts and latest_health is None:
        raise IsolatedRunnerError("mail_configuration_without_preregistration")
    if (
        not has_open_incident
        and latest_health is not None
        and latest_health["artifact_type"] == "M4IsolatedRuntimeHealthV11"
        and latest_health["body"].get("status")
        in {"THERMAL_PAUSED", "THERMAL_HARD_STOP", "RESOURCE_GUARD_TRIGGERED"}
    ):
        incident_context = contract.render_context(
            source_max_issue=context["source_max_issue"],
            source_max_draw_date=context["source_max_draw_date"],
            target_issue=context["target_issue"],
            target_draw_date=context["target_draw_date"],
            batch_seq=int(context["batch_seq"]),
            epoch_date=now.strftime("%Y%m%d"),
            minute=now.strftime("%Y%m%d%H%M"),
            incident_reason_code="RESOURCE_GUARD_TRIGGERED",
            incident_offending_digest=latest_health["artifact_digest"],
            projection_time=context["projection_time"],
        )
    uncertain_delivery_keys = sorted(
        fact.removesuffix(":UNCERTAIN")
        for fact in facts
        if fact.startswith("m4-isolated-24h-challenger-v11-")
        and fact.endswith(":UNCERTAIN")
    )
    if not has_open_incident and uncertain_delivery_keys:
        uncertain_receipt = mainline._unique_type(
            mainline.load_completed_task_artifacts(
                repository=repository,
                root_dir=ROOT_DIR,
                task_key=uncertain_delivery_keys[0],
            ),
            "M4IsolatedDeliveryReceiptV11",
        )
        incident_context = contract.render_context(
            source_max_issue=context["source_max_issue"],
            source_max_draw_date=context["source_max_draw_date"],
            target_issue=context["target_issue"],
            target_draw_date=context["target_draw_date"],
            batch_seq=int(context["batch_seq"]),
            epoch_date=now.strftime("%Y%m%d"),
            minute=now.strftime("%Y%m%d%H%M"),
            incident_reason_code="UNVERIFIED_PREDICTION_DELIVERY_ATTEMPT",
            incident_offending_digest=uncertain_receipt["artifact_digest"],
            projection_time=context["projection_time"],
        )
    daily_context = {
        **dict(context),
        "epoch_date": now.strftime("%Y%m%d"),
        "minute": now.strftime("%Y%m%d%H%M"),
    }
    daily_delivery_key = contract.task_template_by_name("daily_delivery").key(
        daily_context
    )
    if (
        not has_open_incident
        and _delivery_absent(
            now=now,
            scheduled=daily_send,
            stop_at=daily_send + timedelta(days=1),
            delivery_task_key=daily_delivery_key,
            facts=facts,
        )
        and contract.MAIL_CONFIGURATION_FACT in facts
    ):
        offending = latest_health
        incident_context = contract.render_context(
            source_max_issue=context["source_max_issue"],
            source_max_draw_date=context["source_max_draw_date"],
            target_issue=context["target_issue"],
            target_draw_date=context["target_draw_date"],
            batch_seq=int(context["batch_seq"]),
            epoch_date=now.strftime("%Y%m%d"),
            minute=now.strftime("%Y%m%d%H%M"),
            incident_reason_code="DEADLINE_OR_ABSENCE",
            incident_offending_digest=offending["artifact_digest"],
            projection_time=context["projection_time"],
        )

    if target_schedule["selection_cutoff"] <= now < target_schedule["freeze_deadline"]:
        names.update({"multiplicity_seal", "eligibility"})
        events.add("SELECTION_CUTOFF")
    if _scheduled_minute(now, target_schedule["freeze_deadline"]):
        names.update(
            {
                "challenger_freeze",
                "random_baseline_freeze",
                "random_baseline_freeze_replay",
                "prediction",
                "prediction_replay",
            }
        )
        events.add("FREEZE_DEADLINE")
    prediction_replay_key = contract.task_template_by_name("prediction_replay").key(
        context
    )
    predraw_delivery_key = contract.task_template_by_name("predraw_delivery").key(
        context
    )
    if _scheduled_minute(now, target_schedule["predraw_send"]):
        if f"{prediction_replay_key}:REGISTERED_REPLAY_VERIFIED" in facts:
            names.update(
                {
                    "predraw_mail_envelope",
                    "predraw_mail_replay",
                    "predraw_delivery",
                }
            )
            events.add("PREDRAW_SEND")
        elif contract.MAIL_CONFIGURATION_FACT in facts and not has_open_incident:
            offending = latest_health
            incident_context = contract.render_context(
                source_max_issue=context["source_max_issue"],
                source_max_draw_date=context["source_max_draw_date"],
                target_issue=context["target_issue"],
                target_draw_date=context["target_draw_date"],
                batch_seq=int(context["batch_seq"]),
                epoch_date=now.strftime("%Y%m%d"),
                minute=now.strftime("%Y%m%d%H%M"),
                incident_reason_code="DEADLINE_OR_ABSENCE",
                incident_offending_digest=offending["artifact_digest"],
                projection_time=context["projection_time"],
            )
    if (
        not has_open_incident
        and _delivery_absent(
            now=now,
            scheduled=target_schedule["predraw_send"],
            stop_at=official_draw,
            delivery_task_key=predraw_delivery_key,
            facts=facts,
        )
        and contract.MAIL_CONFIGURATION_FACT in facts
    ):
        incident_context = contract.render_context(
            source_max_issue=context["source_max_issue"],
            source_max_draw_date=context["source_max_draw_date"],
            target_issue=context["target_issue"],
            target_draw_date=context["target_draw_date"],
            batch_seq=int(context["batch_seq"]),
            epoch_date=now.strftime("%Y%m%d"),
            minute=now.strftime("%Y%m%d%H%M"),
            incident_reason_code="DEADLINE_OR_ABSENCE",
            incident_offending_digest=latest_health["artifact_digest"],
            projection_time=context["projection_time"],
        )

    settlement_names = {
        "settlement",
        "random_baseline_settlement",
        "formal_p3_comparison_input",
        "formal_p3_comparison",
        "settlement_report",
        "settlement_replay",
        "post_mail_envelope",
        "post_mail_replay",
        "post_delivery",
    }
    settlement_contexts: list[dict[str, str]] = []
    if now.minute % 15 == 0:
        for task in manifest.tasks:
            metric = json.loads(task.metric_contract)
            if metric.get("task_template") != "prediction_replay":
                continue
            item_context = _task_context(task)
            if (
                now
                >= contract.schedule_for_issue(
                    item_context["target_issue"],
                    target_draw_date=item_context["target_draw_date"],
                )["predraw_send"]
                and f"{task.task_key}:REGISTERED_REPLAY_VERIFIED" in facts
                and _issue_exists(repository, issue=item_context["target_issue"])
            ):
                settlement_contexts.append(item_context)

    cut_context = {
        **dict(context),
        "batch_seq": f"{max(0, latest_completed_batch):012d}",
        "cut_checkpoint_ref": (
            "GENESIS"
            if latest_completed_batch < 0
            else f"{latest_completed_batch:012d}"
        ),
        "epoch_date": now.strftime("%Y%m%d"),
        "minute": now.strftime("%Y%m%d%H%M"),
    }
    payload = builder.extend_manifest(
        current,
        context=cut_context,
        source_digest=source_digest,
        template_names=frozenset(names),
        add_external_events=tuple(sorted(events)),
    )
    repository.import_extension(payload)
    if incident_context is not None:
        live = repository.export_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        incident_payload = builder.extend_manifest(
            live,
            context=incident_context,
            source_digest=source_digest,
            template_names=builder.INCIDENT_TEMPLATE_NAMES,
            add_external_events=("INCIDENT_OPEN",),
        )
        repository.import_extension(incident_payload)
    if add_search:
        live = repository.export_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        payload = builder.extend_manifest(
            live,
            context=next_context,
            source_digest=source_digest,
            template_names=builder.SEARCH_TEMPLATE_NAMES,
        )
        repository.import_extension(payload)
    for old_context in sorted(
        settlement_contexts, key=lambda item: item["target_issue"]
    ):
        live = repository.export_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        payload = builder.extend_manifest(
            live,
            context=old_context,
            source_digest=source_digest,
            template_names=frozenset(settlement_names),
            add_external_events=("AUDITED_DRAW",),
        )
        repository.import_extension(payload)


def _activation_facts(
    *,
    task_key: str,
    template: contract.TaskTemplate,
    context: Mapping[str, str],
    repository: PostgresResearchOSRepository,
) -> tuple[str, ...]:
    if template.activation_mode == contract.PAIRED:
        if template.name == "search_batch":
            _mirror_search_batch_ledger(
                repository=repository,
                task_key=task_key,
            )
        return ()
    if template.activation_mode == contract.REPLAY:
        upstream_name = {
            "genesis_replay": "genesis",
            "search_batch_replay": "search_batch",
            "search_checkpoint_replay": "search_checkpoint",
            "random_baseline_freeze_replay": "random_baseline_freeze",
            "prediction_replay": "prediction",
            "settlement_replay": "settlement_report",
            "daily_summary_replay": "daily_summary",
            "predraw_mail_replay": "predraw_mail_envelope",
            "post_mail_replay": "post_mail_envelope",
            "daily_mail_replay": "daily_mail_envelope",
            "incident_mail_replay": "incident_envelope",
        }.get(template.name)
        if upstream_name is None:
            raise IsolatedRunnerError("replay_activation_upstream_changed")
        if template.name in {"genesis_replay", "search_checkpoint_replay"}:
            _mirror_search_checkpoint(
                repository=repository,
                context=context,
                replay_task_key=task_key,
                replay_template_name=template.name,
            )
        upstream_key = contract.task_template_by_name(upstream_name).key(context)
        return (
            f"{upstream_key}:COMPLETE",
            f"{task_key}:REGISTERED_REPLAY_VERIFIED",
        )
    if template.activation_mode == contract.DELIVERY:
        values = mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=task_key,
        )
        receipts = [
            item
            for item in values
            if item["artifact_type"] == "M4IsolatedDeliveryReceiptV11"
        ]
        if len(receipts) != 1:
            raise IsolatedRunnerError("delivery_receipt_not_unique")
        receipt = receipts[0]
        body = receipt["body"]
        state = body.get("state")
        terminal_at = (
            body.get("smtp_data_accepted_at")
            or body.get("created_at")
            or body.get("smtp_transaction_started_at")
        )
        with (
            repository.connection_factory() as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "INSERT INTO m4_isolated_v11.delivery_ledger ("
                "delivery_key,mail_kind,target_identity,content_digest,"
                "recipient_set_digest,state,attempt_count,receipt_artifact_digest,"
                "started_at,terminal_at) VALUES ("
                "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (delivery_key) DO NOTHING",
                (
                    body["delivery_key"],
                    body["mail_kind"],
                    (
                        body.get("target_issue")
                        or body.get("target_identity")
                        or receipt["body"].get("target_issue")
                        or task_key
                    ),
                    body["content_digest"],
                    body["recipient_set_digest"],
                    state,
                    body["attempt_count"],
                    receipt["artifact_digest"],
                    body["smtp_transaction_started_at"],
                    terminal_at,
                ),
            )
            stored = cursor.execute(
                "SELECT mail_kind,content_digest,recipient_set_digest,state,"
                "attempt_count,receipt_artifact_digest FROM "
                "m4_isolated_v11.delivery_ledger WHERE delivery_key=%s",
                (body["delivery_key"],),
            ).fetchone()
        if stored is None or tuple(stored) != (
            body["mail_kind"],
            body["content_digest"],
            body["recipient_set_digest"],
            state,
            body["attempt_count"],
            receipt["artifact_digest"],
        ):
            raise IsolatedRunnerError("delivery_ledger_mirror_changed")
        if state == "SENT":
            return (f"{task_key}:SENT",)
        if state == "UNCERTAIN":
            return (f"{task_key}:UNCERTAIN",)
        raise IsolatedRunnerError("external_delivery_receipt_not_authoritative")
    if template.name == "challenger_freeze":
        values = mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=task_key,
        )
        types = {item["artifact_type"] for item in values}
        if types == {"M4IsolatedChallengerFreezeV11"}:
            return (f"{task_key}:FROZEN",)
        if types == {"M4IsolatedNoChallengerV11"}:
            return (f"{task_key}:NO_ELIGIBLE_CHALLENGER",)
        raise IsolatedRunnerError("challenger_freeze_artifact_set_changed")
    if template.name == "formal_p3_comparison_input":
        values = mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=task_key,
        )
        if len(values) != 1:
            raise IsolatedRunnerError("formal_p3_input_artifact_not_unique")
        artifact_type = values[0]["artifact_type"]
        if artifact_type == "M4IsolatedFormalP3IssueProjectionV11":
            subtype = "COMPLETE"
        elif artifact_type == "M4IsolatedFormalP3PendingMarkerV11":
            subtype = "PENDING_LEGAL_COMPARISON"
        else:
            raise IsolatedRunnerError("formal_p3_input_artifact_type_changed")
        return (f"{task_key}:{subtype}", f"{task_key}:RESOLVED")
    if template.name == "formal_p3_comparison":
        values = mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=task_key,
        )
        comparison = next(
            (
                item
                for item in values
                if item["artifact_type"] == "M4IsolatedFormalP3ComparisonV11"
            ),
            None,
        )
        status = comparison["body"].get("status") if comparison else None
        if status not in {"COMPLETE", "PENDING_LEGAL_COMPARISON"}:
            raise IsolatedRunnerError("formal_p3_comparison_status_changed")
        return (f"{task_key}:{status}", f"{task_key}:RESOLVED")
    suffix = {
        "preregistration": contract.FREEZE_FACT,
        "operator_attestation": contract.OPERATOR_ATTESTATION_FACT,
        "mail_configuration": contract.MAIL_CONFIGURATION_FACT,
        "incident_open": f"{task_key}:OPEN",
    }.get(template.name, f"{task_key}:COMPLETE")
    return (suffix,)


def _mirror_search_checkpoint(
    *,
    repository: IsolatedChallengerRepository,
    context: Mapping[str, str],
    replay_task_key: str,
    replay_template_name: str,
) -> None:
    replay_values = mainline.load_completed_task_artifacts(
        repository=repository,
        root_dir=ROOT_DIR,
        task_key=replay_task_key,
    )
    replay = next(
        (
            item
            for item in replay_values
            if item["artifact_type"] == "M4IsolatedSearchCheckpointReplayV11"
        ),
        None,
    )
    if replay is None:
        raise IsolatedRunnerError("checkpoint_replay_artifact_missing")
    if replay_template_name == "genesis_replay":
        checkpoint_task_key = contract.task_template_by_name("genesis").key(context)
        checkpoint_values = mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=checkpoint_task_key,
        )
        checkpoint = next(
            (
                item
                for item in checkpoint_values
                if item["artifact_type"] == "M4IsolatedSearchCheckpointV11"
            ),
            None,
        )
        row = (
            -1,
            context["target_issue"],
            None,
            None,
            None,
            None,
            checkpoint["artifact_digest"] if checkpoint else None,
            replay["artifact_digest"],
        )
    elif replay_template_name == "search_checkpoint_replay":
        checkpoint_task_key = contract.task_template_by_name("search_checkpoint").key(
            context
        )
        checkpoint_values = mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=checkpoint_task_key,
        )
        checkpoint = next(
            (
                item
                for item in checkpoint_values
                if item["artifact_type"] == "M4IsolatedSearchCheckpointV11"
            ),
            None,
        )
        if checkpoint is None or len(checkpoint["parent_digests"]) != 4:
            raise IsolatedRunnerError("checkpoint_parent_chain_changed")
        batch_seq = int(context["batch_seq"])
        previous_context = {**dict(context), "batch_seq": f"{batch_seq - 1:012d}"}
        previous_replay_key = (
            contract.task_template_by_name("genesis_replay").key(context)
            if batch_seq == 0
            else contract.task_template_by_name("search_checkpoint_replay").key(
                previous_context
            )
        )
        previous_replay_values = mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=previous_replay_key,
        )
        previous_replay = next(
            (
                item
                for item in previous_replay_values
                if item["artifact_type"] == "M4IsolatedSearchCheckpointReplayV11"
            ),
            None,
        )
        if previous_replay is None:
            raise IsolatedRunnerError("checkpoint_predecessor_replay_missing")
        row = (
            batch_seq,
            context["target_issue"],
            previous_replay["artifact_digest"],
            checkpoint["parent_digests"][1],
            checkpoint["parent_digests"][2],
            checkpoint["parent_digests"][3],
            checkpoint["artifact_digest"],
            replay["artifact_digest"],
        )
    else:
        raise IsolatedRunnerError("checkpoint_replay_template_changed")
    if row[6] is None:
        raise IsolatedRunnerError("checkpoint_artifact_missing")
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO m4_isolated_v11.search_checkpoints ("
            "batch_seq,target_issue,predecessor_replay_digest,batch_digest,"
            "batch_replay_digest,multiplicity_delta_digest,checkpoint_digest,"
            "replay_digest) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (batch_seq) DO NOTHING",
            row,
        )
        stored = cursor.execute(
            "SELECT batch_seq,target_issue,predecessor_replay_digest,batch_digest,"
            "batch_replay_digest,multiplicity_delta_digest,checkpoint_digest,"
            "replay_digest FROM m4_isolated_v11.search_checkpoints "
            "WHERE batch_seq=%s",
            (row[0],),
        ).fetchone()
    if stored is None or tuple(stored) != row:
        raise IsolatedRunnerError("checkpoint_ledger_mirror_changed")


def _mirror_search_batch_ledger(
    *, repository: PostgresResearchOSRepository, task_key: str
) -> None:
    values = mainline.load_completed_task_artifacts(
        repository=repository,
        root_dir=ROOT_DIR,
        task_key=task_key,
    )
    registrations = {
        str(item["body"]["candidate_id"]): item
        for item in values
        if item["artifact_type"] == "M4IsolatedCandidateRegistrationV11"
    }
    attempts = {
        str(item["body"]["execution_attempt_id"]): item
        for item in values
        if item["artifact_type"] == "M4IsolatedExecutionAttemptV11"
    }
    results = {
        str(item["body"]["candidate_id"]): item
        for item in values
        if item["artifact_type"] == "M4IsolatedCandidateResultV11"
    }
    if (
        len(registrations) != contract.ATTEMPTS_PER_BATCH
        or not contract.ATTEMPTS_PER_BATCH <= len(attempts) <= 54
        or len(results) != contract.ATTEMPTS_PER_BATCH
        or set(registrations) != set(results)
    ):
        raise IsolatedRunnerError("search_batch_ledger_cardinality_changed")
    with (
        repository.connection_factory() as connection,
        connection.cursor(row_factory=dict_row) as cursor,
    ):
        registration_rows = {
            str(item["candidate_id"]): dict(item)
            for item in cursor.execute(
                "SELECT candidate_id,artifact_digest,state FROM "
                "m4_isolated_v11.candidate_registrations "
                "WHERE candidate_id=ANY(%s) FOR UPDATE",
                (list(registrations),),
            ).fetchall()
        }
        if set(registration_rows) != set(registrations):
            raise IsolatedRunnerError("candidate_registration_ledger_incomplete")
        for candidate_id, artifact in registrations.items():
            row = registration_rows[candidate_id]
            if (
                row["artifact_digest"] != artifact["artifact_digest"]
                or row["state"] != "TERMINAL"
            ):
                raise IsolatedRunnerError("candidate_registration_ledger_changed")
        for attempt_id, artifact in attempts.items():
            body = artifact["body"]
            rows = cursor.execute(
                "SELECT candidate_id,retry_ordinal,worker_started_at,terminal_at,"
                "status,reason,artifact_digest,artifact_committed FROM "
                "m4_isolated_v11.execution_attempts "
                "WHERE execution_attempt_id=%s FOR UPDATE",
                (attempt_id,),
            ).fetchall()
            if len(rows) != 1:
                raise IsolatedRunnerError("execution_attempt_ledger_missing")
            row = dict(rows[0])
            exact = (
                row["candidate_id"] == body["candidate_id"]
                and int(row["retry_ordinal"]) == int(body["retry_ordinal"])
                and row["worker_started_at"].isoformat() == body["started_at"]
                and row["terminal_at"].isoformat() == body["completed_at"]
                and row["status"] == body["status"]
                and row["reason"] == body["reason"]
            )
            if not exact:
                raise IsolatedRunnerError("execution_attempt_ledger_changed")
            if bool(row["artifact_committed"]):
                if row["artifact_digest"] != artifact["artifact_digest"]:
                    raise IsolatedRunnerError("execution_attempt_artifact_changed")
                continue
            updated = cursor.execute(
                "UPDATE m4_isolated_v11.execution_attempts SET "
                "artifact_digest=%s,artifact_committed=TRUE "
                "WHERE execution_attempt_id=%s AND artifact_digest IS NULL "
                "AND artifact_committed=FALSE",
                (artifact["artifact_digest"], attempt_id),
            )
            if updated.rowcount != 1:
                raise IsolatedRunnerError("execution_attempt_artifact_commit_changed")
        for candidate_id, artifact in results.items():
            body = artifact["body"]
            ordered_attempt_ids = list(body["ordered_attempt_ids"])
            if any(attempt_id not in attempts for attempt_id in ordered_attempt_ids):
                raise IsolatedRunnerError("candidate_result_attempt_parent_missing")
            cursor.execute(
                "INSERT INTO m4_isolated_v11.candidate_results ("
                "candidate_id,status,terminal_reason,ordered_attempt_ids_json,"
                "fold_values_hex_json,primary_mean_hex,block_means_hex_json,"
                "eligible,artifact_digest,completed_at) VALUES ("
                "%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s::jsonb,FALSE,%s,%s) "
                "ON CONFLICT (candidate_id) DO NOTHING",
                (
                    candidate_id,
                    body["status"],
                    body["terminal_reason"],
                    json.dumps(ordered_attempt_ids, separators=(",", ":")),
                    (
                        json.dumps(body["fold_values_hex"], separators=(",", ":"))
                        if body["status"] == "SUCCEEDED"
                        else None
                    ),
                    (
                        body["primary_mean_hex"]
                        if body["status"] == "SUCCEEDED"
                        else None
                    ),
                    (
                        json.dumps(body["block_means_hex"], separators=(",", ":"))
                        if body["status"] == "SUCCEEDED"
                        else None
                    ),
                    artifact["artifact_digest"],
                    datetime.fromisoformat(
                        str(attempts[ordered_attempt_ids[-1]]["body"]["completed_at"])
                    ),
                ),
            )
        stored = {
            str(item["candidate_id"]): str(item["artifact_digest"])
            for item in cursor.execute(
                "SELECT candidate_id,artifact_digest FROM "
                "m4_isolated_v11.candidate_results WHERE candidate_id=ANY(%s)",
                (list(results),),
            ).fetchall()
        }
    expected = {
        candidate_id: str(item["artifact_digest"])
        for candidate_id, item in results.items()
    }
    if stored != expected:
        raise IsolatedRunnerError("candidate_result_ledger_changed")


def _search_batch_mirror_complete(
    *, repository: PostgresResearchOSRepository, context: Mapping[str, str]
) -> bool:
    batch_seq = int(context["batch_seq"])
    with (
        repository.connection_factory() as connection,
        connection.cursor(row_factory=dict_row) as cursor,
    ):
        batch = cursor.execute(
            "SELECT registration_seq FROM m4_isolated_v11.registration_batches "
            "WHERE batch_seq=%s",
            (batch_seq,),
        ).fetchone()
        if batch is None:
            return False
        counts = cursor.execute(
            "SELECT "
            "(SELECT count(*) FROM m4_isolated_v11.candidate_registrations "
            " WHERE registration_seq=%s),"
            "(SELECT count(*) FROM m4_isolated_v11.candidate_registrations "
            " WHERE registration_seq=%s AND state='TERMINAL'),"
            "(SELECT count(*) FROM m4_isolated_v11.candidate_results x JOIN "
            " m4_isolated_v11.candidate_registrations r USING(candidate_id) "
            " WHERE r.registration_seq=%s),"
            "(SELECT count(*) FROM m4_isolated_v11.execution_attempts a JOIN "
            " m4_isolated_v11.candidate_registrations r USING(candidate_id) "
            " WHERE r.registration_seq=%s),"
            "(SELECT count(*) FROM m4_isolated_v11.execution_attempts a JOIN "
            " m4_isolated_v11.candidate_registrations r USING(candidate_id) "
            " WHERE r.registration_seq=%s AND a.artifact_committed)",
            (int(batch["registration_seq"]),) * 5,
        ).fetchone()
    if counts is None:
        return False
    candidates, terminal, results, attempts, committed_attempts = map(int, counts)
    return bool(
        candidates == contract.ATTEMPTS_PER_BATCH
        and terminal == candidates
        and results == candidates
        and contract.ATTEMPTS_PER_BATCH <= attempts <= 54
        and committed_attempts == attempts
    )


def _activation_present(
    *,
    template: contract.TaskTemplate,
    task_key: str,
    context: Mapping[str, str],
    facts: set[str],
    repository: PostgresResearchOSRepository,
) -> bool:
    if template.activation_mode == contract.PAIRED:
        return template.name != "search_batch" or _search_batch_mirror_complete(
            repository=repository,
            context=context,
        )
    if template.activation_mode == contract.REPLAY:
        return f"{task_key}:REGISTERED_REPLAY_VERIFIED" in facts
    if template.activation_mode == contract.DELIVERY:
        return bool({f"{task_key}:SENT", f"{task_key}:UNCERTAIN"}.intersection(facts))
    if template.name == "challenger_freeze":
        return bool(
            {
                f"{task_key}:FROZEN",
                f"{task_key}:NO_ELIGIBLE_CHALLENGER",
                f"{task_key}:FREEZE_DEADLINE_MISSED",
            }.intersection(facts)
        )
    if template.name in {"formal_p3_comparison_input", "formal_p3_comparison"}:
        return f"{task_key}:RESOLVED" in facts
    expected = {
        "preregistration": contract.FREEZE_FACT,
        "operator_attestation": contract.OPERATOR_ATTESTATION_FACT,
        "mail_configuration": contract.MAIL_CONFIGURATION_FACT,
        "incident_open": f"{task_key}:OPEN",
    }.get(template.name, f"{task_key}:COMPLETE")
    return expected in facts


def _verify_generic_replay(generic: Mapping[str, Any]) -> None:
    if (
        generic.get("status") != "REPLAY_VERIFIED"
        or generic.get("same_execution_identity") is not True
        or generic.get("same_artifact_identity") is not True
        or generic.get("same_artifact_content") is not True
        or generic.get("all_registrations_and_parent_chains_exact") is not True
        or generic.get("manual_input_assembly") is not False
        or generic.get("dispatch_performed") is not False
    ):
        raise IsolatedRunnerError("generic_replay_failed")


def _recover_completed_activations(
    *,
    repository: IsolatedChallengerRepository,
    source_digest: str,
) -> list[dict[str, Any]]:
    manifest = repository.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    facts = set(manifest.facts.artifacts)
    recovered: list[dict[str, Any]] = []
    for task in sorted(manifest.tasks, key=lambda item: item.task_key):
        state = manifest.task_state_by_digest[task.artifact_digest]
        if state.declared_status != TaskStatus.COMPLETED:
            continue
        context = _task_context(task)
        template = mainline.template_for_task_key(task.task_key, context=context)
        if _activation_present(
            template=template,
            task_key=task.task_key,
            context=context,
            facts=facts,
            repository=repository,
        ):
            continue
        events = repository.list_mainline_execution_events(
            control_plane_key=contract.CONTROL_PLANE_KEY,
            task_key=task.task_key,
        )
        completed = [item for item in events if item.get("event_type") == "completed"]
        if len(completed) != 1:
            raise IsolatedRunnerError("completed_activation_event_not_unique")
        execution_id = str(completed[0].get("execution_id") or "")
        supervisor = mainline.IsolatedChallengerSupervisor(
            repository=repository,
            context=context,
            source_digest=source_digest,
            simulation=False,
        )
        generic = supervisor.replay(
            task_key=task.task_key,
            execution_id=execution_id,
        )
        _verify_generic_replay(generic)
        activated = _activation_facts(
            task_key=task.task_key,
            template=template,
            context=context,
            repository=repository,
        )
        if activated:
            repository.import_verified_facts(activated)
            facts.update(activated)
        recovered.append(
            {
                "task_key": task.task_key,
                "execution_id": execution_id,
                "activated_facts": list(activated),
            }
        )
    return recovered


def install(
    *,
    apply: bool,
    context: Mapping[str, str],
    source_digest: str,
    operator_configuration_authorized: bool,
    git_commit: str | None = None,
) -> dict[str, Any]:
    payload, dry_run = builder.build_bootstrap_manifest(
        context=context,
        source_digest=source_digest,
        operator_configuration_authorized=operator_configuration_authorized,
    )
    if not apply:
        return dry_run
    repository = IsolatedChallengerRepository(
        context=context, source_digest=source_digest
    )
    repository.ensure_schema()
    schema_attestation = _attest_database_schema(
        repository=repository,
        git_commit=str(git_commit or ""),
    )
    source_contract = artifacts.load_source_contract(root_dir=ROOT_DIR)
    if source_contract["artifact_digest"] != source_digest:
        raise IsolatedRunnerError("install_source_contract_changed")
    registered_source = mainline.register_input_artifact(
        repository=repository,
        payload=source_contract,
        git_commit=str(git_commit or ""),
        source_path=contract.SOURCE_CONTRACT_PATH,
        content_bytes=(ROOT_DIR / contract.SOURCE_CONTRACT_PATH).read_bytes(),
    )
    database_schema = mainline.build_registered_input(
        artifact_type="M4IsolatedDatabaseSchemaIdentityV11",
        body={
            "schema_version": contract.DATABASE_SCHEMA_VERSION,
            "contract_digest": contract.CONTRACT_DIGEST,
            "source_contract_digest": source_digest,
            "installed_git_commit": schema_attestation["installed_git_commit"],
        },
        parent_digests=(source_digest,),
    )
    registered_schema = mainline.register_input_artifact(
        repository=repository,
        payload=database_schema,
        git_commit=str(git_commit or ""),
    )
    result, imported_manifest_digest = repository.import_bootstrap_manifest(payload)
    return {
        "status": "IMPORTED",
        "manifest_digest": imported_manifest_digest,
        "import_result": str(result),
        "database_schema_attestation": schema_attestation,
        "registered_source_contract_digest": registered_source["artifact_digest"],
        "registered_database_schema_digest": registered_schema["artifact_digest"],
        "smtp_calls": 0,
        "workloads": 0,
        "formal_p3_mutated": False,
    }


def _attest_database_schema(
    *, repository: IsolatedChallengerRepository, git_commit: str
) -> dict[str, str]:
    if _GIT_COMMIT.fullmatch(git_commit) is None:
        raise IsolatedRunnerError("database_schema_git_commit_invalid")
    expected = (
        contract.DATABASE_SCHEMA_VERSION,
        contract.CONTRACT_DIGEST,
        git_commit,
    )
    with (
        repository.connection_factory() as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "INSERT INTO m4_isolated_v11.schema_identity ("
            "singleton,schema_version,contract_digest,installed_git_commit) "
            "VALUES (TRUE,%s,%s,%s) ON CONFLICT (singleton) DO NOTHING",
            expected,
        )
        row = cursor.execute(
            "SELECT schema_version,contract_digest,installed_git_commit FROM "
            "m4_isolated_v11.schema_identity WHERE singleton=TRUE"
        ).fetchone()
    if row is None:
        raise IsolatedRunnerError("database_schema_identity_changed")
    actual = tuple(str(item) for item in row)
    if actual[:2] != expected[:2] or _GIT_COMMIT.fullmatch(actual[2]) is None:
        raise IsolatedRunnerError("database_schema_identity_changed")
    if actual[2] != git_commit:
        ancestry = subprocess.run(
            ["git", "merge-base", "--is-ancestor", actual[2], git_commit],
            cwd=ROOT_DIR,
            check=False,
            capture_output=True,
            text=True,
        )
        if ancestry.returncode != 0:
            raise IsolatedRunnerError("database_schema_install_commit_not_ancestor")
    return {
        "schema_version": actual[0],
        "contract_digest": actual[1],
        "installed_git_commit": actual[2],
    }


def cycle(
    *,
    apply: bool,
    context: Mapping[str, str],
    source_digest: str,
) -> dict[str, Any]:
    repository = IsolatedChallengerRepository(
        context=context, source_digest=source_digest
    )
    if not apply:
        status = mainline.compact_status(repository=repository)
        return {**status, "dispatch_performed": False}
    p3_before = _p3_source_identity()
    recovered = _recover_completed_activations(
        repository=repository,
        source_digest=source_digest,
    )
    _roll_forward(
        repository=repository,
        context=context,
        source_digest=source_digest,
    )
    dispatched: list[dict[str, Any]] = list(recovered)
    search_dispatched = False
    resource_state = "PREEMPT"
    observation: dict[str, Any] = {}
    thermal_blocked = True
    thermal_state: dict[str, Any] = {}
    try:
        thermal_guard = mainline.ThermalGuard(root_dir=ROOT_DIR)
        thermal_state = thermal_guard.sample(force=True)
        thermal_blocked = thermal_guard.paused
    except mainline.IsolatedMainlineError:
        thermal_state = mainline.thermal_observation()
    for _ in range(64):
        manifest = repository.load_manifest(
            control_plane_key=contract.CONTROL_PLANE_KEY
        )
        snapshot = repository.control_plane.resolve(manifest)
        task_by_key = {item.task_key: item for item in manifest.tasks}
        candidates: list[tuple[bool, int, str, Any, dict[str, str], Any]] = []
        observation = _resource_observation()
        resource_state = contract.formal_p3_activity_state(observation)
        ready_keys = [item.task_key for item in snapshot.ready_queue]
        running_keys = [
            task.task_key
            for task in manifest.tasks
            if manifest.task_state_by_digest[task.artifact_digest].declared_status
            == TaskStatus.RUNNING
        ]
        if len(running_keys) > 1:
            raise IsolatedRunnerError("multiple_running_isolated_tasks")
        dispatch_keys = running_keys or ready_keys
        for dispatch_key in dispatch_keys:
            task = task_by_key[dispatch_key]
            dispatch_context = _task_context(task)
            template = mainline.template_for_task_key(
                task.task_key, context=dispatch_context
            )
            if template.name == "search_batch" and (
                search_dispatched or resource_state != "QUIESCENT" or thermal_blocked
            ):
                continue
            candidates.append(
                (
                    template.name == "search_batch",
                    -int(task.priority),
                    task.task_key,
                    task,
                    dispatch_context,
                    template,
                )
            )
        if not candidates:
            if (
                contract.MAIL_CONFIGURATION_FACT in manifest.facts.artifacts
                and "RESOURCE_QUIESCENT_60S" not in manifest.facts.external_events
                and resource_state == "QUIESCENT"
            ):
                try:
                    observation = _continuous_quiescence()
                except IsolatedRunnerError:
                    break
                live = repository.export_manifest(
                    control_plane_key=contract.CONTROL_PLANE_KEY
                )
                event_payload = builder.extend_manifest(
                    live,
                    context=context,
                    source_digest=source_digest,
                    template_names=builder.HEALTH_TEMPLATE_NAMES,
                    add_external_events=("RESOURCE_QUIESCENT_60S",),
                )
                repository.import_extension(event_payload)
                continue
            break
        _, _, task_key, task, dispatch_context, template = min(candidates)
        facts = set(manifest.facts.artifacts)
        if (
            template.name in {"genesis", "search_batch"}
            and contract.MAIL_CONFIGURATION_FACT not in facts
        ):
            raise IsolatedRunnerError(
                "search_lease_without_verified_mail_configuration"
            )
        if template.name == "search_batch":
            try:
                observation = _continuous_quiescence()
            except IsolatedRunnerError:
                break
            resource_state = contract.formal_p3_activity_state(observation)
            if resource_state != "QUIESCENT":
                break
            search_dispatched = True
            if "RESOURCE_QUIESCENT_60S" not in manifest.facts.external_events:
                live = repository.export_manifest(
                    control_plane_key=contract.CONTROL_PLANE_KEY
                )
                event_payload = builder.extend_manifest(
                    live,
                    context=dispatch_context,
                    source_digest=source_digest,
                    template_names=builder.HEALTH_TEMPLATE_NAMES,
                    add_external_events=("RESOURCE_QUIESCENT_60S",),
                )
                repository.import_extension(event_payload)
        supervisor = mainline.IsolatedChallengerSupervisor(
            repository=repository,
            context=dispatch_context,
            source_digest=source_digest,
            simulation=False,
        )
        result = supervisor.run_once(task_key=task_key)
        if result.get("task_key") != task_key or result.get("status") != "COMPLETE":
            return {
                **result,
                "dispatches": dispatched,
                "formal_p3_mutated": False,
            }
        generic = supervisor.replay(
            task_key=task_key, execution_id=str(result["execution_id"])
        )
        _verify_generic_replay(generic)
        activated = _activation_facts(
            task_key=task_key,
            template=template,
            context=dispatch_context,
            repository=repository,
        )
        if activated:
            repository.import_verified_facts(activated)
        dispatched.append(
            {
                "task_key": task_key,
                "execution_id": result["execution_id"],
                "activated_facts": list(activated),
            }
        )
    if _p3_source_identity() != p3_before:
        raise IsolatedRunnerError("formal_p3_source_changed_during_cycle")
    if not dispatched:
        status = mainline.compact_status(repository=repository)
        return {
            **status,
            "status": (
                "PREEMPTED_FOR_FORMAL_P3"
                if resource_state != "QUIESCENT"
                else (
                    "THERMAL_GUARD_PAUSED" if thermal_blocked else status.get("status")
                )
            ),
            "resource_state": resource_state,
            "observation": observation,
            "thermal_observation": thermal_state,
            "dispatch_performed": False,
            "new_leases": 0,
            "formal_p3_mutated": False,
        }
    last = dispatched[-1]
    return {
        "status": "COMPLETE_AND_REPLAY_VERIFIED",
        "task_key": last["task_key"],
        "execution_id": last["execution_id"],
        "activated_facts": last["activated_facts"],
        "dispatches": dispatched,
        "dispatch_count": len(dispatched),
        "resource_state": resource_state,
        "dispatch_performed": True,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
    }


def simulation(
    *, context: Mapping[str, str], source_digest: str, git_commit: str
) -> dict[str, Any]:
    p3_before = _p3_source_identity()
    payload, dry_run = builder.build_manifest(
        context=context,
        source_digest=source_digest,
        operator_configuration_authorized=True,
        simulation_events=True,
    )
    manifest = ControlPlaneManifest.from_dict(payload)
    if len(manifest.tasks) != 42:
        raise IsolatedRunnerError("simulation_manifest_task_count_changed")
    chain = mainline.simulate_artifact_chain(
        context=context,
        git_commit=git_commit,
        source_digest=source_digest,
    )
    snapshot_digest = hashlib.sha256(b"isolated-v11-synthetic-snapshot").hexdigest()
    configurations = search.base_configurations(
        snapshot_digest=snapshot_digest, source_contract_digest=source_digest
    )
    jobs = search.plan_batch(configurations, cursor=0)
    single = search.execute_jobs(jobs, worker_count=1)
    parallel = search.execute_jobs(jobs, worker_count=contract.WORKER_COUNT)
    single_equivalence = _parallel_equivalence_bundle(
        single,
        target_issue=context["target_issue"],
    )
    parallel_equivalence = _parallel_equivalence_bundle(
        parallel,
        target_issue=context["target_issue"],
    )
    if (
        search.result_bytes(single) != search.result_bytes(parallel)
        or single_equivalence != parallel_equivalence
    ):
        raise IsolatedRunnerError("PARALLEL_EQUIVALENCE_FAILED")
    registry = search.AtomicCandidateRegistry()
    state = registry.register_batch(jobs)
    if state.m_total != 18:
        raise IsolatedRunnerError("simulation_multiplicity_changed")
    probabilities = tuple(0.12 + index / 1000 for index in range(33))
    red_top100 = search.top_red_combinations(
        lambda candidate: search.probability_combination_score(candidate, probabilities)
    )
    prediction_seed = hashlib.sha256(
        f"prediction:{context['target_issue']}".encode()
    ).hexdigest()[:32]
    tickets = search.add_deterministic_blue(red_top100, seed_hex=prediction_seed)
    baseline = search.baseline_set(context["target_issue"])
    synthetic_result = tickets[0]
    settlement = reporting.settle_portfolio(
        tickets,
        winning_reds=synthetic_result[0],
        winning_blue=synthetic_result[1],
        first_prize_cny="5000000.00",
        second_prize_cny="100000.00",
    )
    baseline_gross = [
        reporting.settle_portfolio(
            item,
            winning_reds=synthetic_result[0],
            winning_blue=synthetic_result[1],
            first_prize_cny="5000000.00",
            second_prize_cny="100000.00",
        )["gross_prize_cny"]
        for item in baseline
    ]
    percentile = reporting.percentile_position(
        settlement["gross_prize_cny"], baseline_gross
    )
    p3_after = _p3_source_identity()
    if p3_before != p3_after:
        raise IsolatedRunnerError("formal_p3_bytes_changed_during_simulation")
    return {
        "schema_version": "dehps-m4-isolated-v11-result-blind-simulation.v1",
        "status": "SIMULATION_COMPLETE",
        "manifest_dry_run": dry_run,
        "chain": chain,
        "parallel_equivalence": "BYTE_IDENTICAL",
        "parallel_equivalence_bundle_sha256": hashlib.sha256(
            single_equivalence
        ).hexdigest(),
        "single_worker_sha256": hashlib.sha256(search.result_bytes(single)).hexdigest(),
        "worker18_sha256": hashlib.sha256(search.result_bytes(parallel)).hexdigest(),
        "multiplicity_m_total": state.m_total,
        "top100_count": len(tickets),
        "baseline_replicates": len(baseline),
        "hypothetical_cost_cny": settlement["cost_cny"],
        "gross_prize_cny": settlement["gross_prize_cny"],
        "estimated_tax_cny": settlement["estimated_tax_cny"],
        "estimated_after_tax_cny": settlement["estimated_after_tax_cny"],
        "net_cny": settlement["net_cny"],
        "roi": settlement["roi"],
        "baseline_percentile": percentile,
        "mail_transport": "FAKE_EPHEMERAL",
        "external_sent_count": 0,
        "smtp_calls": 0,
        "formal_p3_source_digest": p3_after["artifact_digest"],
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
    }


def _parallel_equivalence_bundle(
    results: Sequence[search.CandidateOutcome], *, target_issue: str
) -> bytes:
    """Bind every frozen downstream identity to the ordered worker output."""

    if len(results) != contract.ATTEMPTS_PER_BATCH:
        raise IsolatedRunnerError("equivalence_candidate_count_changed")
    candidate_result_bytes = search.result_bytes(results)
    candidate_result_digest = hashlib.sha256(candidate_result_bytes).hexdigest()
    ordered = sorted(
        results,
        key=lambda item: (
            item.status != "SUCCEEDED",
            -item.primary_mean,
            item.configuration_id,
            item.seed_ordinal,
            item.candidate_id,
        ),
    )
    selected = ordered[0]
    probability_seed = hashlib.sha256(
        f"{target_issue}\0{selected.candidate_id}".encode("ascii")
    ).digest()
    probabilities = tuple(
        0.10 + probability_seed[index % len(probability_seed)] / 2000.0
        for index in range(33)
    )
    red_top100 = search.top_red_combinations(
        lambda candidate: search.probability_combination_score(candidate, probabilities)
    )
    tickets = search.add_deterministic_blue(
        red_top100,
        seed_hex=hashlib.sha256(
            f"equivalence-blue\0{target_issue}\0{selected.candidate_id}".encode("ascii")
        ).hexdigest()[:32],
    )
    ordering = [item.candidate_id for item in ordered]
    top100_digest = contract.domain_digest(
        [[[int(value) for value in reds], blue] for reds, blue in tickets],
        domain="dehps.m4.isolated-24h-challenger.equivalence-top100.v11",
    )
    checkpoint = {
        "candidate_result_digest": candidate_result_digest,
        "candidate_order": ordering,
        "selected_candidate_id": selected.candidate_id,
        "top100_digest": top100_digest,
    }
    checkpoint_digest = contract.domain_digest(
        checkpoint,
        domain="dehps.m4.isolated-24h-challenger.equivalence-checkpoint.v11",
    )
    artifact_digest = contract.domain_digest(
        {
            "target_issue": target_issue,
            "checkpoint_digest": checkpoint_digest,
            "top100_digest": top100_digest,
        },
        domain="dehps.m4.isolated-24h-challenger.equivalence-artifact.v11",
    )
    replay_digest = contract.domain_digest(
        {
            "artifact_digest": artifact_digest,
            "checkpoint_digest": checkpoint_digest,
            "status": "REPLAY_VERIFIED",
        },
        domain="dehps.m4.isolated-24h-challenger.equivalence-replay.v11",
    )
    return contract.canonical_json(
        {
            "candidate_results": json.loads(candidate_result_bytes),
            "candidate_order": ordering,
            "selected_candidate_id": selected.candidate_id,
            "top100": [{"red": list(reds), "blue": blue} for reds, blue in tickets],
            "checkpoint_digest": checkpoint_digest,
            "artifact_digest": artifact_digest,
            "replay_digest": replay_digest,
        }
    ).encode("ascii")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("status", "simulate", "install", "cycle"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--source-max-issue")
    parser.add_argument("--source-max-draw-date")
    parser.add_argument("--target-issue")
    parser.add_argument("--target-draw-date")
    parser.add_argument("--batch-seq", type=int, default=0)
    parser.add_argument("--epoch-date")
    parser.add_argument("--minute")
    parser.add_argument("--incident-id")
    parser.add_argument("--incident-reason-code", default="DEADLINE_OR_ABSENCE")
    parser.add_argument("--incident-offending-digest")
    parser.add_argument("--projection-time")
    parser.add_argument("--operator-configuration-authorized", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if bool(args.source_max_issue) != bool(args.source_max_draw_date):
        raise IsolatedRunnerError("source_history_identity_incomplete")
    if args.command == "simulate" and args.source_max_issue:
        source_max_issue = args.source_max_issue
        source_max_draw_date = args.source_max_draw_date
    else:
        live_source_issue, live_source_draw_date = _latest_history_identity()
        source_max_issue = args.source_max_issue or live_source_issue
        source_max_draw_date = args.source_max_draw_date or live_source_draw_date
        if (
            source_max_issue != live_source_issue
            or source_max_draw_date != live_source_draw_date
        ):
            raise IsolatedRunnerError("rendered_source_history_identity_changed")
    context = contract.render_context(
        source_max_issue=source_max_issue,
        source_max_draw_date=source_max_draw_date,
        target_issue=args.target_issue,
        target_draw_date=args.target_draw_date,
        batch_seq=args.batch_seq,
        epoch_date=args.epoch_date,
        minute=args.minute,
        incident_id=args.incident_id,
        incident_reason_code=args.incident_reason_code,
        incident_offending_digest=args.incident_offending_digest,
        projection_time=(
            args.projection_time
            or (
                datetime.now(contract.TIMEZONE).isoformat()
                if args.command in {"status", "install", "cycle"}
                else None
            )
        ),
    )
    source = artifacts.load_source_contract(root_dir=ROOT_DIR)
    source_digest = str(source["artifact_digest"])
    git_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True
    ).strip()
    if args.command == "simulate":
        result = simulation(
            context=context, source_digest=source_digest, git_commit=git_commit
        )
    elif args.command == "install":
        result = install(
            apply=args.apply,
            context=context,
            source_digest=source_digest,
            operator_configuration_authorized=(args.operator_configuration_authorized),
            git_commit=git_commit,
        )
    else:
        repository = IsolatedChallengerRepository(
            context=context, source_digest=source_digest
        )
        if args.command == "status":
            result = mainline.compact_status(repository=repository)
        else:
            result = cycle(
                apply=args.apply, context=context, source_digest=source_digest
            )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
