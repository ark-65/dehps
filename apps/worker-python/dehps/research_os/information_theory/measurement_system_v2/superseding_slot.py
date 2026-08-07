from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.mainline import completion_execution_ids
from dehps.research_os.models import (
    ControlPlaneManifest,
    MainlineArtifactRegistration,
    Task,
    TaskStatus,
    stable_json,
)

from .compatibility import (
    COMPATIBILITY_REQUEST_DIGEST,
    P261_FROZEN_FIXTURE_DIGEST,
    P263_SUPERSEDING_FIXTURE_DIGEST,
)
from .terminal_guard import RUNTIME_SLOT_RELEASE_EVENT

CONTROL_PLANE_KEY = "m4-information-theory-mainline"
P263_SLOT_ELIGIBILITY_TASK_KEY = (
    "m4-p2-9-p263-runtime-slot-release-eligibility"
)
P263_SLOT_ELIGIBILITY_CAPABILITY = (
    "m4_p2_9_p263_runtime_slot_release_eligibility"
)
P263_SLOT_ELIGIBILITY_FACT = (
    "m4-p263-runtime-slot-release-eligibility:VERIFIED"
)
P263_SLOT_ELIGIBILITY_SCHEMA = (
    "dehps-m4-p263-runtime-slot-release-eligibility.v1"
)
P263_SLOT_ELIGIBILITY_TYPE = "p263_runtime_slot_release_eligibility"
P263_SLOT_ELIGIBILITY_DOMAIN = (
    "dehps.m4.p263.runtime-slot-release-eligibility.v1"
)
P263_SLOT_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-p263-runtime-slot-governance-source-contract-v1.json"
)
P263_SLOT_SOURCE_CONTRACT_SCHEMA = (
    "dehps-m4-p263-runtime-slot-governance-source-contract.v1"
)
P263_SLOT_SOURCE_CONTRACT_TYPE = (
    "p263_runtime_slot_governance_source_contract"
)
P263_SLOT_SOURCE_CONTRACT_DOMAIN = (
    "dehps.m4.p263.runtime-slot-governance-source-contract.v1"
)
P263_SLOT_SOURCE_SET_DOMAIN = (
    "dehps.m4.p263.runtime-slot-governance-source-set.v1"
)
P263_SLOT_GUARD_SCHEMA = "dehps-m4-p263-runtime-slot-guard-decision.v1"
P263_SLOT_GUARD_TYPE = "p263_runtime_slot_guard_decision"
P263_SLOT_GUARD_DOMAIN = "dehps.m4.p263.runtime-slot-guard-decision.v1"
P263_SLOT_MIGRATION_SCHEMA = "dehps-m4-p263-runtime-slot-migration.v1"
P263_SLOT_MIGRATION_DOMAIN = "dehps.m4.p263.runtime-slot-migration.v1"

P263_COMPATIBILITY_TASK_KEY = (
    "m4-p2-6-3-superseding-compatibility-acceptance"
)
P263_COMPATIBILITY_TASK_DIGEST = (
    "4e0693a09e23d4e7bc6d49bf8969c340684686815b6e8051a328aefa26fbb4e6"
)
P263_COMPATIBILITY_CAPABILITY = (
    "m4_p2_6_3_superseding_compatibility_acceptance"
)
P263_GOLDEN_TASK_KEY = "m4-p2-9-p263-golden-reference-freeze"
P263_GOLDEN_TASK_DIGEST = (
    "8c992aa2acd3a36a8671fc080a59846afc1d378ec21ca3c5856342482021824d"
)
P263_GOLDEN_CAPABILITY = "m4_p2_9_p263_golden_reference_freeze"
P263_GOLDEN_FACT = "m4-p2-9-p263-golden-reference:VERIFIED"
P263_FAILED_RUNTIME_TASK_KEY = "m4-p2-9-p263-measurement-runtime-audit"
P263_FAILED_RUNTIME_TASK_DIGEST = (
    "1e0033856ecd69803e861129e80e7d94180b819481353205640f53cb7b3d9e59"
)
P263_FAILED_RUNTIME_CAPABILITY = "m4_p2_9_p263_measurement_runtime_audit"
P263_RUNTIME_TASK_KEY = "m4-p2-9-p263-runtime-observation-arithmetic-fix"
P263_RUNTIME_TASK_DIGEST = (
    "d2c81c1afc0986ff48130d745269c57ba809c69ea29267d9c290f09e4026490f"
)
P263_RUNTIME_CAPABILITY = (
    "m4_p2_9_p263_runtime_observation_arithmetic_fix"
)
P263_RUNTIME_FACT = (
    "m4-p2-9-p263-runtime-audit-arithmetic-fix:VERIFIED"
)
P263_RUNTIME_PLAN_DIGEST = (
    "8c97fd5fdc006cba6a4145dbd56acc566b9507e18279d06437d0aa472adb2cd2"
)
M4_V2_DESIGN_TASK_KEY = "m4-v2-measurement-contract-design"
M4_V2_DESIGN_REPLAY_TASK_KEY = "m4-v2-measurement-contract-design-replay"
M4_V2_PREFLIGHT_TASK_KEY = "m4-v2-branch-identifiability-preflight-design"
LEGACY_P3_TASK_KEY = "m4-p3-strict-historical-walk-forward"

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_EVENT_FIELDS = {
    "event_digest",
    "execution_id",
    "control_plane_key",
    "manifest_digest",
    "task_digest",
    "task_key",
    "capability",
    "event_type",
    "sequence",
    "recorded_at",
}
_REGISTRATION_FIELDS = {
    "registration_digest",
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
_COMPLETED_TASKS = {
    P263_COMPATIBILITY_TASK_KEY: {
        "task_digest": P263_COMPATIBILITY_TASK_DIGEST,
        "capability": P263_COMPATIBILITY_CAPABILITY,
        "required_fact": "m4-p2-6-3-compatibility:VERIFIED",
        "artifacts": Counter(
            {
                (
                    "MeasurementCompatibilityAcceptanceArtifact",
                    "dehps-m4-p2-measurement-compatibility-acceptance.v1",
                ): 1,
                (
                    "measurement_source_fixture_replay",
                    "dehps-m4-p2-source-fixture-replay.v1",
                ): 2,
                (
                    "research_os_mainline_execution",
                    "dehps-research-os-mainline-execution.v1",
                ): 1,
            }
        ),
    },
    P263_GOLDEN_TASK_KEY: {
        "task_digest": P263_GOLDEN_TASK_DIGEST,
        "capability": P263_GOLDEN_CAPABILITY,
        "required_fact": P263_GOLDEN_FACT,
        "artifacts": Counter(
            {
                (
                    "GoldenReferencePlanArtifact",
                    "dehps-m4-p2-9-golden-reference-plan.v1",
                ): 1,
                (
                    "GoldenReferenceReplayArtifact",
                    "dehps-m4-p2-9-phase0-golden-equivalence.v1",
                ): 1,
                (
                    "Phase0GoldenReferenceFixture.v1",
                    "dehps-m4-p2-9-phase0-golden-reference.v1",
                ): 1,
                (
                    "SourceIntegrityAttestationArtifact",
                    "dehps-m4-p2-9-source-integrity-attestation.v1",
                ): 1,
                (
                    "research_os_mainline_execution",
                    "dehps-research-os-mainline-execution.v1",
                ): 1,
            }
        ),
    },
    P263_RUNTIME_TASK_KEY: {
        "task_digest": P263_RUNTIME_TASK_DIGEST,
        "capability": P263_RUNTIME_CAPABILITY,
        "required_fact": P263_RUNTIME_FACT,
        "artifacts": Counter(
            {
                (
                    "BenchmarkPlanArtifact",
                    "dehps-m4-p2-9-measurement-runtime-audit-plan.v1",
                ): 1,
                (
                    "EquivalenceAttestationArtifact",
                    "dehps-m4-p2-9-equivalence-attestation.v1",
                ): 1,
                (
                    "RuntimeBenchmarkAttemptArtifact",
                    "dehps-m4-p2-9-runtime-benchmark-attempt.v1",
                ): 1,
                (
                    "RuntimeObservationArtifact",
                    "dehps-m4-p2-9-runtime-observation.v1",
                ): 1,
                (
                    "SourceIntegrityAttestationArtifact",
                    "dehps-m4-p2-9-source-integrity-attestation.v1",
                ): 1,
                (
                    "research_os_mainline_execution",
                    "dehps-research-os-mainline-execution.v1",
                ): 1,
            }
        ),
    },
}
_DOWNSTREAM_TASK_KEYS = {
    M4_V2_DESIGN_TASK_KEY,
    M4_V2_DESIGN_REPLAY_TASK_KEY,
    M4_V2_PREFLIGHT_TASK_KEY,
    LEGACY_P3_TASK_KEY,
}
P263_SLOT_GOVERNANCE_SOURCE_PATHS = tuple(
    sorted(
        {
            "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/__init__.py",
            "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/runtime_audit.py",
            "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/superseding_slot.py",
            "apps/worker-python/dehps/research_os/information_theory/measurement_validation/source_integrity.py",
            "apps/worker-python/dehps/research_os/information_theory/progress.py",
            "apps/worker-python/dehps/research_os/supervisor.py",
            "apps/worker-python/scripts/build_m4_p263_slot_release_manifest.py",
            "apps/worker-python/scripts/run_m4_p263_slot_release_guard.py",
        }
    )
)


class P263SlotSupersessionError(RuntimeError):
    pass


def validate_p263_slot_source_contract(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    expected_fields = {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "contract_key",
        "source_entries",
        "source_set_digest",
        "execution_git_commit_required",
        "result_blind",
        "statistical_results_read",
        "historical_outcomes_read",
        "evidence_created",
        "evidence_progress_increment",
        "promotion_gate_opened",
        "production_action",
    }
    identity = dict(payload)
    digest = identity.pop("artifact_digest", None)
    entries = payload.get("source_entries")
    if not isinstance(entries, list):
        raise P263SlotSupersessionError("p263_slot_source_contract_invalid")
    paths: list[str] = []
    for entry in entries:
        if (
            not isinstance(entry, Mapping)
            or set(entry) != {"path", "content_sha256"}
            or Path(str(entry.get("path") or "")).is_absolute()
            or ".." in Path(str(entry.get("path") or "")).parts
            or _DIGEST.fullmatch(str(entry.get("content_sha256") or "")) is None
        ):
            raise P263SlotSupersessionError(
                "p263_slot_source_contract_entry_invalid"
            )
        paths.append(str(entry["path"]))
    if (
        set(payload) != expected_fields
        or payload.get("schema_version") != P263_SLOT_SOURCE_CONTRACT_SCHEMA
        or payload.get("artifact_type") != P263_SLOT_SOURCE_CONTRACT_TYPE
        or digest
        != canonical_digest(identity, domain=P263_SLOT_SOURCE_CONTRACT_DOMAIN)
        or payload.get("contract_key")
        != "M4-P2.6.3_RUNTIME_SLOT_GOVERNANCE_SOURCE"
        or tuple(paths) != P263_SLOT_GOVERNANCE_SOURCE_PATHS
        or len(paths) != len(set(paths))
        or payload.get("source_set_digest")
        != canonical_digest(entries, domain=P263_SLOT_SOURCE_SET_DOMAIN)
        or payload.get("execution_git_commit_required") is not True
        or payload.get("result_blind") is not True
        or payload.get("statistical_results_read") is not False
        or payload.get("historical_outcomes_read") is not False
        or payload.get("evidence_created") is not False
        or payload.get("evidence_progress_increment") != 0
        or payload.get("promotion_gate_opened") is not False
        or payload.get("production_action") != "none"
    ):
        raise P263SlotSupersessionError("p263_slot_source_contract_invalid")
    return dict(payload)


def load_p263_slot_source_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise P263SlotSupersessionError(
            f"p263_slot_source_contract_unreadable:{path}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise P263SlotSupersessionError("p263_slot_source_contract_invalid")
    return validate_p263_slot_source_contract(payload)


def verify_p263_slot_source_bytes(
    *,
    root_dir: Path,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    verified = validate_p263_slot_source_contract(contract)
    for entry in verified["source_entries"]:
        path = str(entry["path"])
        try:
            content = (root_dir / path).read_bytes()
        except OSError as exc:
            raise P263SlotSupersessionError(
                f"p263_slot_source_unreadable:{path}"
            ) from exc
        if sha256(content).hexdigest() != entry["content_sha256"]:
            raise P263SlotSupersessionError(
                f"p263_slot_source_modified:{path}"
            )
    return verified


def _task_by_key(manifest: ControlPlaneManifest, key: str) -> Task:
    matches = [task for task in manifest.tasks if task.task_key == key]
    if len(matches) != 1:
        raise P263SlotSupersessionError(f"p263_slot_task_not_unique:{key}")
    return matches[0]


def _validate_event(event: Mapping[str, Any]) -> None:
    if (
        set(event) != _EVENT_FIELDS
        or _DIGEST.fullmatch(str(event.get("event_digest") or "")) is None
        or _DIGEST.fullmatch(str(event.get("execution_id") or "")) is None
        or _DIGEST.fullmatch(str(event.get("manifest_digest") or "")) is None
        or _DIGEST.fullmatch(str(event.get("task_digest") or "")) is None
        or event.get("control_plane_key") != CONTROL_PLANE_KEY
        or event.get("event_type") not in {"started", "completed", "failed"}
        or not isinstance(event.get("sequence"), int)
        or not str(event.get("recorded_at") or "")
    ):
        raise P263SlotSupersessionError("p263_slot_event_metadata_invalid")
    try:
        datetime.fromisoformat(str(event["recorded_at"]))
    except ValueError as exc:
        raise P263SlotSupersessionError(
            "p263_slot_event_recorded_at_invalid"
        ) from exc


def _validate_registration(
    registration: Mapping[str, Any],
    *,
    task: Task,
    execution_id: str,
) -> None:
    relative_path = Path(str(registration.get("artifact_path") or ""))
    parent_digests = registration.get("parent_digests")
    try:
        reconstructed = MainlineArtifactRegistration(
            execution_id=str(registration.get("execution_id") or ""),
            control_plane_key=str(registration.get("control_plane_key") or ""),
            task_key=str(registration.get("task_key") or ""),
            task_digest=str(registration.get("task_digest") or ""),
            artifact_digest=str(registration.get("artifact_digest") or ""),
            artifact_type=str(registration.get("artifact_type") or ""),
            schema_version=str(registration.get("schema_version") or ""),
            artifact_path=relative_path.as_posix(),
            parent_digests=tuple(str(value) for value in parent_digests),
            git_commit=str(registration.get("git_commit") or ""),
        )
    except TypeError as exc:
        raise P263SlotSupersessionError(
            "p263_slot_registration_metadata_invalid"
        ) from exc
    expected_root = (
        Path("runtime/research-os/mainline/tasks") / task.task_key / execution_id
    )
    try:
        relative_path.relative_to(expected_root)
    except ValueError as exc:
        raise P263SlotSupersessionError(
            "p263_slot_registration_path_invalid"
        ) from exc
    if (
        set(registration) != _REGISTRATION_FIELDS
        or relative_path.is_absolute()
        or ".." in relative_path.parts
        or registration.get("execution_id") != execution_id
        or registration.get("control_plane_key") != CONTROL_PLANE_KEY
        or registration.get("task_key") != task.task_key
        or registration.get("task_digest") != task.artifact_digest
        or _DIGEST.fullmatch(str(registration.get("artifact_digest") or "")) is None
        or _DIGEST.fullmatch(str(registration.get("registration_digest") or ""))
        is None
        or not str(registration.get("artifact_type") or "")
        or not str(registration.get("schema_version") or "")
        or not isinstance(parent_digests, list)
        or any(_DIGEST.fullmatch(str(value)) is None for value in parent_digests)
        or _COMMIT.fullmatch(str(registration.get("git_commit") or "")) is None
        or registration.get("registration_digest")
        != reconstructed.registration_digest
    ):
        raise P263SlotSupersessionError(
            "p263_slot_registration_metadata_invalid"
        )


def _completed_task_basis(
    *,
    manifest: ControlPlaneManifest,
    task_key: str,
    contract: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    registrations_by_execution: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    task = _task_by_key(manifest, task_key)
    state = manifest.task_state_by_digest[task.artifact_digest]
    if (
        task.artifact_digest != contract["task_digest"]
        or task.requested_capability != contract["capability"]
        or state.declared_status is not TaskStatus.COMPLETED
        or state.completion_classification is None
        or state.completion_classification.value != "COMPLETE"
        or contract["required_fact"] not in manifest.facts.artifacts
    ):
        raise P263SlotSupersessionError(
            f"p263_slot_completed_task_invalid:{task_key}"
        )
    execution_ids = completion_execution_ids(manifest, task=task)
    if len(execution_ids) != 1:
        raise P263SlotSupersessionError(
            f"p263_slot_completion_identity_invalid:{task_key}"
        )
    execution_id = execution_ids[0]
    task_events = [event for event in events if event.get("task_key") == task_key]
    for event in task_events:
        _validate_event(event)
    if (
        len(task_events) != 2
        or Counter(event["event_type"] for event in task_events)
        != Counter({"started": 1, "completed": 1})
        or any(
            event.get("execution_id") != execution_id
            or event.get("task_digest") != task.artifact_digest
            or event.get("capability") != task.requested_capability
            for event in task_events
        )
    ):
        raise P263SlotSupersessionError(
            f"p263_slot_completion_events_invalid:{task_key}"
        )
    event_by_type = {str(event["event_type"]): event for event in task_events}
    if (
        event_by_type["started"]["sequence"] != 0
        or event_by_type["completed"]["sequence"] != 1
    ):
        raise P263SlotSupersessionError(
            f"p263_slot_completion_sequence_invalid:{task_key}"
        )

    registrations = list(registrations_by_execution.get(execution_id, ()))
    for registration in registrations:
        _validate_registration(registration, task=task, execution_id=execution_id)
    actual_artifacts = Counter(
        (
            str(registration["artifact_type"]),
            str(registration["schema_version"]),
        )
        for registration in registrations
    )
    if actual_artifacts != contract["artifacts"]:
        raise P263SlotSupersessionError(
            f"p263_slot_registered_artifacts_invalid:{task_key}"
        )
    return {
        "task_key": task.task_key,
        "task_digest": task.artifact_digest,
        "capability": task.requested_capability,
        "execution_id": execution_id,
        "started_event_digest": event_by_type["started"]["event_digest"],
        "completed_event_digest": event_by_type["completed"]["event_digest"],
        "registrations": [
            {
                "registration_digest": registration["registration_digest"],
                "artifact_digest": registration["artifact_digest"],
                "artifact_type": registration["artifact_type"],
                "schema_version": registration["schema_version"],
            }
            for registration in sorted(
                registrations,
                key=lambda item: str(item["registration_digest"]),
            )
        ],
    }


def _failed_superseded_basis(
    *,
    manifest: ControlPlaneManifest,
    events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    task = _task_by_key(manifest, P263_FAILED_RUNTIME_TASK_KEY)
    state = manifest.task_state_by_digest[task.artifact_digest]
    task_events = [
        event
        for event in events
        if event.get("task_key") == P263_FAILED_RUNTIME_TASK_KEY
    ]
    for event in task_events:
        _validate_event(event)
    if (
        task.artifact_digest != P263_FAILED_RUNTIME_TASK_DIGEST
        or task.requested_capability != P263_FAILED_RUNTIME_CAPABILITY
        or state.declared_status is not TaskStatus.SUPERSEDED
        or state.superseded_by_task_digest != P263_RUNTIME_TASK_DIGEST
        or len(task_events) != 2
        or Counter(event["event_type"] for event in task_events)
        != Counter({"started": 1, "failed": 1})
        or len({str(event["execution_id"]) for event in task_events}) != 1
        or any(
            event.get("task_digest") != task.artifact_digest
            or event.get("capability") != task.requested_capability
            for event in task_events
        )
    ):
        raise P263SlotSupersessionError("p263_slot_failed_history_invalid")
    event_by_type = {str(event["event_type"]): event for event in task_events}
    if (
        event_by_type["started"]["sequence"] != 0
        or event_by_type["failed"]["sequence"] != 1
    ):
        raise P263SlotSupersessionError("p263_slot_failed_sequence_invalid")
    return {
        "task_key": task.task_key,
        "task_digest": task.artifact_digest,
        "capability": task.requested_capability,
        "execution_id": event_by_type["failed"]["execution_id"],
        "started_event_digest": event_by_type["started"]["event_digest"],
        "failed_event_digest": event_by_type["failed"]["event_digest"],
        "status": "SUPERSEDED",
        "superseded_by_task_digest": P263_RUNTIME_TASK_DIGEST,
    }


def build_p263_slot_eligibility_artifact(
    *,
    manifest: ControlPlaneManifest,
    events: Sequence[Mapping[str, Any]],
    registrations_by_execution: Mapping[str, Sequence[Mapping[str, Any]]],
    execution_id: str,
    git_commit: str,
    p261_fixture_digest: str,
    p263_fixture_digest: str,
    slot_source_contract_digest: str,
    slot_source_set_digest: str,
) -> dict[str, Any]:
    if (
        _DIGEST.fullmatch(execution_id) is None
        or _COMMIT.fullmatch(git_commit) is None
        or p261_fixture_digest != P261_FROZEN_FIXTURE_DIGEST
        or p263_fixture_digest != P263_SUPERSEDING_FIXTURE_DIGEST
        or _DIGEST.fullmatch(slot_source_contract_digest) is None
        or _DIGEST.fullmatch(slot_source_set_digest) is None
        or RUNTIME_SLOT_RELEASE_EVENT in manifest.facts.external_events
    ):
        raise P263SlotSupersessionError("p263_slot_eligibility_input_invalid")

    for event in events:
        _validate_event(event)
    eligibility_task = _task_by_key(manifest, P263_SLOT_ELIGIBILITY_TASK_KEY)
    eligibility_state = manifest.task_state_by_digest[
        eligibility_task.artifact_digest
    ]
    eligibility_started = [
        event
        for event in events
        if event.get("task_key") == P263_SLOT_ELIGIBILITY_TASK_KEY
        and event.get("execution_id") == execution_id
        and event.get("event_type") == "started"
    ]
    if (
        eligibility_task.requested_capability != P263_SLOT_ELIGIBILITY_CAPABILITY
        or eligibility_state.declared_status
        not in {TaskStatus.RUNNING, TaskStatus.COMPLETED}
        or len(eligibility_started) != 1
        or eligibility_started[0].get("task_digest")
        != eligibility_task.artifact_digest
        or eligibility_started[0].get("capability")
        != P263_SLOT_ELIGIBILITY_CAPABILITY
        or eligibility_started[0].get("sequence") != 0
    ):
        raise P263SlotSupersessionError(
            "p263_slot_eligibility_execution_identity_invalid"
        )
    try:
        eligibility_started_at = datetime.fromisoformat(
            str(eligibility_started[0]["recorded_at"])
        )
    except ValueError as exc:
        raise P263SlotSupersessionError(
            "p263_slot_eligibility_started_at_invalid"
        ) from exc
    downstream_started = [
        event
        for event in events
        if event.get("task_key") in _DOWNSTREAM_TASK_KEYS
        and event.get("event_type") == "started"
        and datetime.fromisoformat(str(event["recorded_at"]))
        <= eligibility_started_at
    ]
    if downstream_started:
        raise P263SlotSupersessionError("p263_slot_downstream_dispatch_race")

    completed = [
        _completed_task_basis(
            manifest=manifest,
            task_key=task_key,
            contract=contract,
            events=events,
            registrations_by_execution=registrations_by_execution,
        )
        for task_key, contract in _COMPLETED_TASKS.items()
    ]
    failed = _failed_superseded_basis(manifest=manifest, events=events)

    design_resolution = next(
        item
        for item in ResearchOSControlPlane().resolve(manifest).resolutions
        if item.task_key == M4_V2_DESIGN_TASK_KEY
    )
    if (
        design_resolution.status is not TaskStatus.EXTERNAL_WAIT
        or [
            dependency.target_key
            for dependency in design_resolution.unsatisfied_dependencies
        ]
        != [RUNTIME_SLOT_RELEASE_EVENT]
    ):
        raise P263SlotSupersessionError(
            "p263_slot_design_wait_boundary_invalid"
        )

    basis = {
        "p2_6_1_frozen_fixture_digest": p261_fixture_digest,
        "p2_6_3_superseding_fixture_digest": p263_fixture_digest,
        "compatibility_request_digest": COMPATIBILITY_REQUEST_DIGEST,
        "runtime_audit_plan_digest": P263_RUNTIME_PLAN_DIGEST,
        "slot_governance_source_contract_digest": slot_source_contract_digest,
        "slot_governance_source_set_digest": slot_source_set_digest,
        "completed_tasks": completed,
        "failed_superseded_task": failed,
        "runtime_slot_event": RUNTIME_SLOT_RELEASE_EVENT,
        "runtime_slot_event_available": False,
        "measurement_v2_design_status": "external_wait",
        "downstream_started_event_digests": [],
        "eligibility_task_digest": eligibility_task.artifact_digest,
        "eligibility_started_event_digest": eligibility_started[0]["event_digest"],
        "eligibility_started_at": eligibility_started[0]["recorded_at"],
    }
    payload: dict[str, Any] = {
        "schema_version": P263_SLOT_ELIGIBILITY_SCHEMA,
        "artifact_type": P263_SLOT_ELIGIBILITY_TYPE,
        "artifact_digest": "",
        "status": "ELIGIBLE_AFTER_OPERATOR_STOP",
        "execution_id": execution_id,
        "git_commit": git_commit,
        "control_plane_key": CONTROL_PLANE_KEY,
        "eligibility_basis_digest": canonical_digest(
            basis,
            domain="dehps.m4.p263.runtime-slot-release-basis.v1",
        ),
        **basis,
        "statistical_results_read": False,
        "result_blind": True,
        "historical_outcomes_read": False,
        "evidence_created": False,
        "evidence_progress_increment": 0,
        "prediction_v2_promotion_allowed": False,
        "promotion_gate_opened": False,
        "production_action": "none",
        "stop_service_required": True,
        "post_stop_guard_required": True,
        "downstream_consumer": "operator-p263-runtime-slot-release",
        "parent_digests": sorted(
            {
                p261_fixture_digest,
                p263_fixture_digest,
                COMPATIBILITY_REQUEST_DIGEST,
                P263_RUNTIME_PLAN_DIGEST,
                slot_source_contract_digest,
                slot_source_set_digest,
                eligibility_started[0]["event_digest"],
                *(item["started_event_digest"] for item in completed),
                *(item["completed_event_digest"] for item in completed),
                *(
                    registration["registration_digest"]
                    for item in completed
                    for registration in item["registrations"]
                ),
                failed["started_event_digest"],
                failed["failed_event_digest"],
            }
        ),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain=P263_SLOT_ELIGIBILITY_DOMAIN,
    )
    return payload


def validate_p263_slot_eligibility_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    expected_fields = {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "status",
        "execution_id",
        "git_commit",
        "control_plane_key",
        "eligibility_basis_digest",
        "p2_6_1_frozen_fixture_digest",
        "p2_6_3_superseding_fixture_digest",
        "compatibility_request_digest",
        "runtime_audit_plan_digest",
        "slot_governance_source_contract_digest",
        "slot_governance_source_set_digest",
        "completed_tasks",
        "failed_superseded_task",
        "runtime_slot_event",
        "runtime_slot_event_available",
        "measurement_v2_design_status",
        "downstream_started_event_digests",
        "eligibility_task_digest",
        "eligibility_started_event_digest",
        "eligibility_started_at",
        "statistical_results_read",
        "result_blind",
        "historical_outcomes_read",
        "evidence_created",
        "evidence_progress_increment",
        "prediction_v2_promotion_allowed",
        "promotion_gate_opened",
        "production_action",
        "stop_service_required",
        "post_stop_guard_required",
        "downstream_consumer",
        "parent_digests",
    }
    identity = dict(payload)
    digest = identity.pop("artifact_digest", None)
    if (
        set(payload) != expected_fields
        or payload.get("schema_version") != P263_SLOT_ELIGIBILITY_SCHEMA
        or payload.get("artifact_type") != P263_SLOT_ELIGIBILITY_TYPE
        or digest != canonical_digest(identity, domain=P263_SLOT_ELIGIBILITY_DOMAIN)
        or payload.get("status") != "ELIGIBLE_AFTER_OPERATOR_STOP"
        or _DIGEST.fullmatch(str(payload.get("execution_id") or "")) is None
        or _COMMIT.fullmatch(str(payload.get("git_commit") or "")) is None
        or payload.get("control_plane_key") != CONTROL_PLANE_KEY
        or _DIGEST.fullmatch(str(payload.get("eligibility_basis_digest") or ""))
        is None
        or payload.get("p2_6_1_frozen_fixture_digest")
        != P261_FROZEN_FIXTURE_DIGEST
        or payload.get("p2_6_3_superseding_fixture_digest")
        != P263_SUPERSEDING_FIXTURE_DIGEST
        or payload.get("compatibility_request_digest")
        != COMPATIBILITY_REQUEST_DIGEST
        or payload.get("runtime_audit_plan_digest") != P263_RUNTIME_PLAN_DIGEST
        or _DIGEST.fullmatch(
            str(payload.get("slot_governance_source_contract_digest") or "")
        )
        is None
        or _DIGEST.fullmatch(
            str(payload.get("slot_governance_source_set_digest") or "")
        )
        is None
        or payload.get("runtime_slot_event") != RUNTIME_SLOT_RELEASE_EVENT
        or payload.get("runtime_slot_event_available") is not False
        or payload.get("measurement_v2_design_status") != "external_wait"
        or payload.get("downstream_started_event_digests") != []
        or _DIGEST.fullmatch(str(payload.get("eligibility_task_digest") or ""))
        is None
        or _DIGEST.fullmatch(
            str(payload.get("eligibility_started_event_digest") or "")
        )
        is None
        or not str(payload.get("eligibility_started_at") or "")
        or payload.get("statistical_results_read") is not False
        or payload.get("result_blind") is not True
        or payload.get("historical_outcomes_read") is not False
        or payload.get("evidence_created") is not False
        or payload.get("evidence_progress_increment") != 0
        or payload.get("prediction_v2_promotion_allowed") is not False
        or payload.get("promotion_gate_opened") is not False
        or payload.get("production_action") != "none"
        or payload.get("stop_service_required") is not True
        or payload.get("post_stop_guard_required") is not True
        or payload.get("downstream_consumer")
        != "operator-p263-runtime-slot-release"
        or not isinstance(payload.get("completed_tasks"), list)
        or len(payload["completed_tasks"]) != 3
        or not isinstance(payload.get("failed_superseded_task"), dict)
        or not isinstance(payload.get("parent_digests"), list)
        or any(
            _DIGEST.fullmatch(str(value)) is None
            for value in payload["parent_digests"]
        )
    ):
        raise P263SlotSupersessionError("p263_slot_eligibility_artifact_invalid")
    completed_by_key: dict[str, Mapping[str, Any]] = {}
    for completed in payload["completed_tasks"]:
        if not isinstance(completed, Mapping) or set(completed) != {
            "task_key",
            "task_digest",
            "capability",
            "execution_id",
            "started_event_digest",
            "completed_event_digest",
            "registrations",
        }:
            raise P263SlotSupersessionError(
                "p263_slot_completed_basis_invalid"
            )
        task_key = str(completed.get("task_key") or "")
        contract = _COMPLETED_TASKS.get(task_key)
        registrations = completed.get("registrations")
        if (
            contract is None
            or task_key in completed_by_key
            or completed.get("task_digest") != contract["task_digest"]
            or completed.get("capability") != contract["capability"]
            or _DIGEST.fullmatch(str(completed.get("execution_id") or ""))
            is None
            or _DIGEST.fullmatch(
                str(completed.get("started_event_digest") or "")
            )
            is None
            or _DIGEST.fullmatch(
                str(completed.get("completed_event_digest") or "")
            )
            is None
            or not isinstance(registrations, list)
        ):
            raise P263SlotSupersessionError(
                "p263_slot_completed_basis_invalid"
            )
        artifact_contracts: Counter[tuple[str, str]] = Counter()
        for registration in registrations:
            if (
                not isinstance(registration, Mapping)
                or set(registration)
                != {
                    "registration_digest",
                    "artifact_digest",
                    "artifact_type",
                    "schema_version",
                }
                or _DIGEST.fullmatch(
                    str(registration.get("registration_digest") or "")
                )
                is None
                or _DIGEST.fullmatch(
                    str(registration.get("artifact_digest") or "")
                )
                is None
            ):
                raise P263SlotSupersessionError(
                    "p263_slot_completed_registration_basis_invalid"
                )
            artifact_contracts[
                (
                    str(registration.get("artifact_type") or ""),
                    str(registration.get("schema_version") or ""),
                )
            ] += 1
        if artifact_contracts != contract["artifacts"]:
            raise P263SlotSupersessionError(
                "p263_slot_completed_artifact_contract_invalid"
            )
        completed_by_key[task_key] = completed
    if set(completed_by_key) != set(_COMPLETED_TASKS):
        raise P263SlotSupersessionError("p263_slot_completed_basis_invalid")
    failed = payload["failed_superseded_task"]
    if (
        set(failed)
        != {
            "task_key",
            "task_digest",
            "capability",
            "execution_id",
            "started_event_digest",
            "failed_event_digest",
            "status",
            "superseded_by_task_digest",
        }
        or failed.get("task_key") != P263_FAILED_RUNTIME_TASK_KEY
        or failed.get("task_digest") != P263_FAILED_RUNTIME_TASK_DIGEST
        or failed.get("capability") != P263_FAILED_RUNTIME_CAPABILITY
        or failed.get("status") != "SUPERSEDED"
        or failed.get("superseded_by_task_digest") != P263_RUNTIME_TASK_DIGEST
        or any(
            _DIGEST.fullmatch(str(failed.get(field) or "")) is None
            for field in (
                "execution_id",
                "started_event_digest",
                "failed_event_digest",
            )
        )
    ):
        raise P263SlotSupersessionError("p263_slot_failed_basis_invalid")
    try:
        datetime.fromisoformat(str(payload["eligibility_started_at"]))
    except ValueError as exc:
        raise P263SlotSupersessionError(
            "p263_slot_eligibility_started_at_invalid"
        ) from exc
    if payload["parent_digests"] != sorted(set(payload["parent_digests"])):
        raise P263SlotSupersessionError("p263_slot_parent_digests_invalid")
    basis = {
        key: payload[key]
        for key in (
            "p2_6_1_frozen_fixture_digest",
            "p2_6_3_superseding_fixture_digest",
            "compatibility_request_digest",
            "runtime_audit_plan_digest",
            "slot_governance_source_contract_digest",
            "slot_governance_source_set_digest",
            "completed_tasks",
            "failed_superseded_task",
            "runtime_slot_event",
            "runtime_slot_event_available",
            "measurement_v2_design_status",
            "downstream_started_event_digests",
            "eligibility_task_digest",
            "eligibility_started_event_digest",
            "eligibility_started_at",
        )
    }
    if payload.get("eligibility_basis_digest") != canonical_digest(
        basis,
        domain="dehps.m4.p263.runtime-slot-release-basis.v1",
    ):
        raise P263SlotSupersessionError("p263_slot_eligibility_basis_invalid")
    return dict(payload)


def replay_p263_slot_eligibility_artifact(
    *,
    payload: Mapping[str, Any],
    manifest: ControlPlaneManifest,
    events: Sequence[Mapping[str, Any]],
    registrations_by_execution: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    verified = validate_p263_slot_eligibility_artifact(payload)
    for event in events:
        _validate_event(event)
    events_by_digest = {str(event["event_digest"]): event for event in events}
    if len(events_by_digest) != len(events):
        raise P263SlotSupersessionError("p263_slot_replay_duplicate_event")

    for completed in verified["completed_tasks"]:
        task_key = str(completed["task_key"])
        contract = _COMPLETED_TASKS.get(task_key)
        if contract is None:
            raise P263SlotSupersessionError(
                "p263_slot_replay_unknown_completed_task"
            )
        task = _task_by_key(manifest, task_key)
        state = manifest.task_state_by_digest[task.artifact_digest]
        execution_id = str(completed["execution_id"])
        if (
            task.artifact_digest != contract["task_digest"]
            or task.requested_capability != contract["capability"]
            or state.declared_status is not TaskStatus.COMPLETED
            or completion_execution_ids(manifest, task=task) != (execution_id,)
        ):
            raise P263SlotSupersessionError(
                f"p263_slot_replay_completed_task_drift:{task_key}"
            )
        for field, event_type in (
            ("started_event_digest", "started"),
            ("completed_event_digest", "completed"),
        ):
            event = events_by_digest.get(str(completed[field]))
            if (
                event is None
                or event.get("execution_id") != execution_id
                or event.get("task_key") != task_key
                or event.get("task_digest") != task.artifact_digest
                or event.get("capability") != task.requested_capability
                or event.get("event_type") != event_type
            ):
                raise P263SlotSupersessionError(
                    f"p263_slot_replay_event_drift:{task_key}:{event_type}"
                )
        registered = {
            str(item["registration_digest"]): item
            for item in registrations_by_execution.get(execution_id, ())
        }
        if len(registered) != len(completed["registrations"]):
            raise P263SlotSupersessionError(
                f"p263_slot_replay_registration_count_drift:{task_key}"
            )
        for identity in completed["registrations"]:
            registration = registered.get(str(identity["registration_digest"]))
            if registration is None:
                raise P263SlotSupersessionError(
                    f"p263_slot_replay_registration_missing:{task_key}"
                )
            _validate_registration(
                registration,
                task=task,
                execution_id=execution_id,
            )
            if any(
                registration.get(field) != identity[field]
                for field in (
                    "registration_digest",
                    "artifact_digest",
                    "artifact_type",
                    "schema_version",
                )
            ):
                raise P263SlotSupersessionError(
                    f"p263_slot_replay_registration_drift:{task_key}"
                )

    failed = verified["failed_superseded_task"]
    failed_task = _task_by_key(manifest, P263_FAILED_RUNTIME_TASK_KEY)
    failed_state = manifest.task_state_by_digest[failed_task.artifact_digest]
    if (
        failed_task.artifact_digest != P263_FAILED_RUNTIME_TASK_DIGEST
        or failed_state.declared_status is not TaskStatus.SUPERSEDED
        or failed_state.superseded_by_task_digest != P263_RUNTIME_TASK_DIGEST
    ):
        raise P263SlotSupersessionError("p263_slot_replay_failed_history_drift")
    for field, event_type in (
        ("started_event_digest", "started"),
        ("failed_event_digest", "failed"),
    ):
        event = events_by_digest.get(str(failed[field]))
        if (
            event is None
            or event.get("execution_id") != failed["execution_id"]
            or event.get("task_key") != P263_FAILED_RUNTIME_TASK_KEY
            or event.get("task_digest") != P263_FAILED_RUNTIME_TASK_DIGEST
            or event.get("event_type") != event_type
        ):
            raise P263SlotSupersessionError(
                f"p263_slot_replay_failed_event_drift:{event_type}"
            )

    eligibility_task = _task_by_key(manifest, P263_SLOT_ELIGIBILITY_TASK_KEY)
    eligibility_state = manifest.task_state_by_digest[
        eligibility_task.artifact_digest
    ]
    eligibility_start = events_by_digest.get(
        str(verified["eligibility_started_event_digest"])
    )
    if (
        eligibility_task.artifact_digest != verified["eligibility_task_digest"]
        or eligibility_task.input_artifact_digests
        != (
            COMPATIBILITY_REQUEST_DIGEST,
            P261_FROZEN_FIXTURE_DIGEST,
            P263_SUPERSEDING_FIXTURE_DIGEST,
            P263_RUNTIME_PLAN_DIGEST,
            verified["slot_governance_source_contract_digest"],
        )
        or eligibility_state.declared_status is not TaskStatus.COMPLETED
        or completion_execution_ids(manifest, task=eligibility_task)
        != (verified["execution_id"],)
        or eligibility_start is None
        or eligibility_start.get("execution_id") != verified["execution_id"]
        or eligibility_start.get("task_digest") != eligibility_task.artifact_digest
        or eligibility_start.get("event_type") != "started"
    ):
        raise P263SlotSupersessionError(
            "p263_slot_replay_eligibility_identity_drift"
        )
    return {
        "schema_version": "dehps-m4-p263-runtime-slot-eligibility-replay.v1",
        "status": "REPLAY_VERIFIED",
        "eligibility_artifact_digest": verified["artifact_digest"],
        "eligibility_basis_digest": verified["eligibility_basis_digest"],
        "same_frozen_source_identities": True,
        "same_completed_task_identities": True,
        "same_event_metadata": True,
        "same_registration_metadata": True,
        "statistical_results_read": False,
        "historical_outcomes_read": False,
        "evidence_created": False,
        "promotion_gate_opened": False,
        "manual_input_assembly": False,
    }


def build_p263_post_stop_guard_decision(
    *,
    eligibility: Mapping[str, Any],
    service_active_state: str,
    worker_cgroup_empty: bool,
    downstream_started_events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    verified = validate_p263_slot_eligibility_artifact(eligibility)
    for event in downstream_started_events:
        _validate_event(event)
    started = [
        event
        for event in downstream_started_events
        if event.get("task_key") in _DOWNSTREAM_TASK_KEYS
        and event.get("event_type") == "started"
    ]
    if started:
        state = "GOVERNANCE_INCIDENT"
        reason = "DOWNSTREAM_DISPATCH_RACE"
        stop_service = True
        publish = False
    elif service_active_state != "inactive" or not worker_cgroup_empty:
        state = "STOP_VERIFICATION_FAILED"
        reason = "SERVICE_OR_WORKER_CGROUP_STILL_ACTIVE"
        stop_service = True
        publish = False
    else:
        state = "SAFE_TO_RELEASE_SLOT"
        reason = "P263_ELIGIBLE_SERVICE_INACTIVE_CGROUP_EMPTY_NO_DOWNSTREAM_START"
        stop_service = False
        publish = True
    payload: dict[str, Any] = {
        "schema_version": P263_SLOT_GUARD_SCHEMA,
        "artifact_type": P263_SLOT_GUARD_TYPE,
        "artifact_digest": "",
        "state": state,
        "reason": reason,
        "stop_service": stop_service,
        "publish_slot_event": publish,
        "service_active_state": service_active_state,
        "worker_cgroup_empty": worker_cgroup_empty,
        "eligibility_artifact_digest": verified["artifact_digest"],
        "runtime_slot_event": RUNTIME_SLOT_RELEASE_EVENT,
        "downstream_started_event_digests": sorted(
            str(event["event_digest"]) for event in started
        ),
        "statistical_results_read": False,
        "result_blind": True,
        "historical_outcomes_read": False,
        "prediction_v2_promotion_allowed": False,
        "promotion_gate_opened": False,
        "production_action": "service_stop_only_when_operator_authorized",
        "parent_digests": [verified["artifact_digest"]],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain=P263_SLOT_GUARD_DOMAIN,
    )
    return payload


def validate_p263_slot_release_guard_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    expected_fields = {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "state",
        "reason",
        "stop_service",
        "publish_slot_event",
        "service_active_state",
        "worker_cgroup_empty",
        "eligibility_artifact_digest",
        "runtime_slot_event",
        "downstream_started_event_digests",
        "statistical_results_read",
        "result_blind",
        "historical_outcomes_read",
        "prediction_v2_promotion_allowed",
        "promotion_gate_opened",
        "production_action",
        "parent_digests",
    }
    identity = dict(payload)
    digest = identity.pop("artifact_digest", None)
    eligibility_digest = str(payload.get("eligibility_artifact_digest") or "")
    if (
        set(payload) != expected_fields
        or payload.get("schema_version") != P263_SLOT_GUARD_SCHEMA
        or payload.get("artifact_type") != P263_SLOT_GUARD_TYPE
        or digest != canonical_digest(identity, domain=P263_SLOT_GUARD_DOMAIN)
        or payload.get("state") != "SAFE_TO_RELEASE_SLOT"
        or payload.get("reason")
        != "P263_ELIGIBLE_SERVICE_INACTIVE_CGROUP_EMPTY_NO_DOWNSTREAM_START"
        or payload.get("stop_service") is not False
        or payload.get("publish_slot_event") is not True
        or payload.get("service_active_state") != "inactive"
        or payload.get("worker_cgroup_empty") is not True
        or _DIGEST.fullmatch(eligibility_digest) is None
        or payload.get("runtime_slot_event") != RUNTIME_SLOT_RELEASE_EVENT
        or payload.get("downstream_started_event_digests") != []
        or payload.get("statistical_results_read") is not False
        or payload.get("result_blind") is not True
        or payload.get("historical_outcomes_read") is not False
        or payload.get("prediction_v2_promotion_allowed") is not False
        or payload.get("promotion_gate_opened") is not False
        or payload.get("production_action")
        != "service_stop_only_when_operator_authorized"
        or payload.get("parent_digests") != [eligibility_digest]
    ):
        raise P263SlotSupersessionError("p263_slot_release_guard_invalid")
    return dict(payload)


def build_p263_slot_release_manifest(
    *,
    live_payload: Mapping[str, Any],
    source_payload: Mapping[str, Any],
    eligibility_payload: Mapping[str, Any],
    guard_payload: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    eligibility_artifact = validate_p263_slot_eligibility_artifact(
        eligibility_payload
    )
    guard = validate_p263_slot_release_guard_artifact(guard_payload)
    if guard["eligibility_artifact_digest"] != eligibility_artifact[
        "artifact_digest"
    ]:
        raise P263SlotSupersessionError(
            "p263_slot_guard_eligibility_lineage_invalid"
        )
    live = ControlPlaneManifest.from_dict(live_payload)
    source = ControlPlaneManifest.from_dict(source_payload)
    if RUNTIME_SLOT_RELEASE_EVENT in live.facts.external_events:
        raise P263SlotSupersessionError("p263_slot_event_already_available")

    live_tasks = {task.task_key: task for task in live.tasks}
    source_tasks = {task.task_key: task for task in source.tasks}
    for key in (P263_SLOT_ELIGIBILITY_TASK_KEY, M4_V2_DESIGN_TASK_KEY):
        if (
            key not in live_tasks
            or key not in source_tasks
            or live_tasks[key].artifact_digest != source_tasks[key].artifact_digest
        ):
            raise P263SlotSupersessionError(
                f"p263_slot_source_task_identity_invalid:{key}"
            )
    eligibility = live_tasks[P263_SLOT_ELIGIBILITY_TASK_KEY]
    eligibility_state = live.task_state_by_digest[eligibility.artifact_digest]
    if (
        eligibility_state.declared_status is not TaskStatus.COMPLETED
        or P263_SLOT_ELIGIBILITY_FACT not in live.facts.artifacts
        or completion_execution_ids(live, task=eligibility)
        != (eligibility_artifact["execution_id"],)
        or eligibility.artifact_digest
        != eligibility_artifact["eligibility_task_digest"]
    ):
        raise P263SlotSupersessionError(
            "p263_slot_eligibility_completion_missing"
        )

    before_snapshot = ResearchOSControlPlane().resolve(live)
    before_design = next(
        item
        for item in before_snapshot.resolutions
        if item.task_key == M4_V2_DESIGN_TASK_KEY
    )
    if (
        before_design.status is not TaskStatus.EXTERNAL_WAIT
        or [item.target_key for item in before_design.unsatisfied_dependencies]
        != [RUNTIME_SLOT_RELEASE_EVENT]
    ):
        raise P263SlotSupersessionError("p263_slot_pre_migration_state_invalid")

    output = live.to_dict(include_digest=False)
    output["facts"]["external_events"] = sorted(
        {*output["facts"]["external_events"], RUNTIME_SLOT_RELEASE_EVENT}
    )
    migrated = ControlPlaneManifest.from_dict(output)
    normalized = migrated.to_dict(include_digest=True)
    after_snapshot = ResearchOSControlPlane().resolve(migrated)
    ready = [item.task_key for item in after_snapshot.ready_queue]
    if ready != [M4_V2_DESIGN_TASK_KEY]:
        raise P263SlotSupersessionError(
            f"p263_slot_post_migration_ready_queue_invalid:{ready}"
        )

    original = live.to_dict(include_digest=False)
    comparison = migrated.to_dict(include_digest=False)
    original_events = original["facts"]["external_events"]
    comparison["facts"]["external_events"] = original_events
    if stable_json(original) != stable_json(comparison):
        raise P263SlotSupersessionError("p263_slot_migration_rewrote_live_state")

    dry_run: dict[str, Any] = {
        "schema_version": P263_SLOT_MIGRATION_SCHEMA,
        "artifact_type": "p263_runtime_slot_event_migration",
        "artifact_digest": "",
        "status": "VERIFIED",
        "live_manifest_digest": live.artifact_digest,
        "source_manifest_digest": source.artifact_digest,
        "output_manifest_digest": migrated.artifact_digest,
        "guard_artifact_digest": guard["artifact_digest"],
        "added_external_events": [RUNTIME_SLOT_RELEASE_EVENT],
        "ready_queue_after": [M4_V2_DESIGN_TASK_KEY],
        "existing_goal_deletions": 0,
        "existing_task_deletions": 0,
        "existing_fact_deletions": 0,
        "existing_state_regressions": 0,
        "unallowlisted_definition_rewrites": 0,
        "statistical_results_read": False,
        "evidence_created": False,
        "prediction_v2_promotion_allowed": False,
        "promotion_gate_opened": False,
        "production_action": "none",
        "import_performed": False,
        "parent_digests": [
            eligibility_artifact["artifact_digest"],
            guard["artifact_digest"],
            live.artifact_digest,
        ],
    }
    identity = deepcopy(dry_run)
    identity.pop("artifact_digest")
    dry_run["artifact_digest"] = canonical_digest(
        identity,
        domain=P263_SLOT_MIGRATION_DOMAIN,
    )
    return normalized, dry_run
