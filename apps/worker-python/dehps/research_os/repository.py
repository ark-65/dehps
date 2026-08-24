from __future__ import annotations

import hashlib
import importlib.util
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from types import ModuleType
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.db import get_connection
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.mainline import completion_execution_ids
from dehps.research_os.models import (
    ControlPlaneManifest,
    ExternalExecutorObservation,
    Goal,
    MainlineArtifactRegistration,
    MainlineExecutionEvent,
    ResearchOSValidationError,
    ResolutionSnapshot,
    Task,
    TaskResolution,
    jsonable,
    m4_v2_domain_digest,
    stable_hash,
    stable_json,
)
from dehps.storage.postgres_store import ensure_research_os_schema

ConnectionFactory = Callable[[], AbstractContextManager[Connection[Any]]]

_M4_V2_GLOBAL_RECOVERY_V1_BUILDER_MODULE_NAME = (
    "_dehps_m4_v2_global_routing_recovery_v1_builder"
)
_M4_V2_GLOBAL_RECOVERY_V1_REQUIRED_SYMBOLS = (
    "INPUT_MANIFEST_DIGEST",
    "OLD_EVENT_MANIFEST_DIGEST",
    "OLD_EXECUTION_ID",
    "OLD_FAILED_EVENT_DIGEST",
    "OLD_STARTED_EVENT_DIGEST",
    "OLD_TASK_DIGEST",
    "OLD_TASK_KEY",
    "P3_REVISIONS",
    "RECOVERY_TASK_KEY",
    "build_manifest",
)
_M4_V2_GLOBAL_RECOVERY_V2_BUILDER_MODULE_NAME = (
    "_dehps_m4_v2_global_routing_recovery_v2_builder"
)
_M4_V2_GLOBAL_RECOVERY_V2_REQUIRED_SYMBOLS = (
    "GLOBAL_SOURCE_PATH",
    "INPUT_MANIFEST_DIGEST",
    "OLD_EVENT_MANIFEST_DIGEST",
    "OLD_EXECUTION_ID",
    "OLD_FAILED_EVENT_DIGEST",
    "OLD_STARTED_EVENT_DIGEST",
    "OLD_TASK_DIGEST",
    "OLD_TASK_KEY",
    "P3_REVISIONS",
    "RECOVERY_TASK_KEY",
    "GlobalRoutingRecoveryV2Error",
    "build_manifest",
    "validate_global_source_contract",
)
_M4_V2_GLOBAL_RECOVERY_V3_BUILDER_MODULE_NAME = (
    "_dehps_m4_v2_global_routing_recovery_v3_builder"
)
_M4_V2_GLOBAL_RECOVERY_V3_REQUIRED_SYMBOLS = (
    "GLOBAL_SOURCE_PATH",
    "INPUT_MANIFEST_DIGEST",
    "INPUT_SNAPSHOT_DIGEST",
    "OLD_EVENT_MANIFEST_DIGEST",
    "OLD_EXECUTION_ID",
    "OLD_FAILED_EVENT_DIGEST",
    "OLD_SOURCE_DIGEST",
    "OLD_STARTED_EVENT_DIGEST",
    "OLD_TASK_DIGEST",
    "OLD_TASK_KEY",
    "P3_TASK_KEYS",
    "RECOVERY_TASK_KEY",
    "GlobalRoutingRecoveryV3Error",
    "build_manifest",
    "validate_global_source_contract",
)
_M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_BUILDER_MODULE_NAME = (
    "_dehps_m4_v2_global_routing_replay_compatibility_v1_builder"
)
_M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_TASK_KEY = (
    "m4-v2-global-routing-recovery-v3-registered-replay-compatibility-v1"
)
_M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_REGISTRATION_DIGEST = (
    "b9b0a3085519d69cccbedf4ff151d0e5761641510522769368965671a6ca8d02"
)
_M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_RESEARCH_REQUEST_ID = 621
_M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_RESEARCH_EXECUTION_ID = 507
_M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_ENGINEERING_REQUEST_ID = 622
_M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_ENGINEERING_EXECUTION_ID = 508
_M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_RESEARCH_PAYLOAD_SHA256 = (
    "122ee0aa7aebe5fc3e99cecd9efe5fcd4b87a91571cceb7f6d67696227c65399"
)
_M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_ENGINEERING_PAYLOAD_SHA256 = (
    "4e06a9af9253b3b77bf2838bd0d33451ec316b017f3ad799f0e76c952020f631"
)
_M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_REQUIRED_SYMBOLS = (
    "AUTHORIZATION_EVENT",
    "INPUT_MANIFEST_DIGEST",
    "INPUT_SNAPSHOT_DIGEST",
    "OLD_COMPLETED_EVENT_DIGEST",
    "OLD_EVENT_MANIFEST_DIGEST",
    "OLD_EXECUTION_ARTIFACT_DIGEST",
    "OLD_EXECUTION_ID",
    "OLD_EXECUTION_PATH",
    "OLD_EXECUTION_REGISTRATION_DIGEST",
    "OLD_GIT_COMMIT",
    "OLD_ROUTE",
    "OLD_ROUTE_ARTIFACT_DIGEST",
    "OLD_ROUTE_PATH",
    "OLD_ROUTE_RAW_LENGTH",
    "OLD_ROUTE_RAW_SHA256",
    "OLD_ROUTE_REGISTRATION_DIGEST",
    "OLD_STARTED_EVENT_DIGEST",
    "OLD_TASK_DIGEST",
    "OLD_TASK_KEY",
    "REGISTERED_REPLAY_FACT",
    "SOURCE_PATH",
    "SUCCESSOR_COMPLETION_FACT",
    "SUCCESSOR_TASK_KEY",
    "GlobalRoutingReplayCompatibilityV1Error",
    "build_manifest",
    "transition_manifest",
    "validate_source_contract",
)
_M4_V2_DEEPER_VALIDATION_BUILDER_MODULE_NAME = (
    "_dehps_m4_v2_deeper_validation_builder"
)
_M4_V2_DEEPER_VALIDATION_INTAKE_TASK_KEY = "m4-v2-deeper-validation-intake"
_M4_V2_DEEPER_VALIDATION_REQUIRED_SYMBOLS = (
    "BASELINE_MANIFEST_DIGEST",
    "NEW_TASK_KEYS",
    "SOURCE_FACT_PREFIX",
    "build_manifest",
)
_M4_P4_DIAGNOSTIC_BUILDER_MODULE_NAME = "_dehps_m4_p4_diagnostic_builder"
_M4_P4_DIAGNOSTIC_FIRST_TASK_KEY = "m4-p3-inconclusive-closure-consolidation"
_M4_P4_DIAGNOSTIC_REQUIRED_SYMBOLS = (
    "BASELINE_MANIFEST_DIGEST",
    "FORMAL_P4_TASK_KEY",
    "GOAL_KEY",
    "NEW_TASK_KEYS",
    "SOURCE_FACT_PREFIX",
    "build_manifest",
)
_M4_V2_FORWARD_FEASIBILITY_BUILDER_MODULE_NAME = (
    "_dehps_m4_v2_forward_feasibility_builder"
)
_M4_V2_FORWARD_FEASIBILITY_TASK_KEY = (
    "m4-v2-forward-evidence-feasibility-and-program-decision"
)
_M4_V2_FORWARD_FEASIBILITY_REQUIRED_SYMBOLS = (
    "BASELINE_MANIFEST_DIGEST",
    "FORMAL_P4_TASK_KEY",
    "GOAL_KEY",
    "NEW_TASK_KEYS",
    "SOURCE_FACT_PREFIX",
    "build_manifest",
)
_M4_V2_BOUNDED_FORWARD_BUILDER_MODULE_NAME = "_dehps_m4_v2_bounded_forward_builder"
_M4_V2_BOUNDED_FORWARD_PREREGISTRATION_TASK_KEY = (
    "m4-v2-bounded-operational-forward-study-preregistration"
)
_M4_V2_BOUNDED_FORWARD_REQUIRED_SYMBOLS = (
    "BASELINE_MANIFEST_DIGEST",
    "FORMAL_P4_TASK_KEY",
    "GOAL_KEY",
    "PREREGISTRATION_TASK_KEY",
    "build_manifest",
    "issue_tasks",
    "preregistration_task",
)
_M4_P3_FORWARD_SUCCESSOR_BUILDER_MODULE_NAME = (
    "_dehps_m4_p3_forward_prequential_successor_builder"
)
_M4_P3_FORWARD_SUCCESSOR_REQUIRED_SYMBOLS = (
    "CONTROL_PLANE_KEY",
    "issue_tasks",
)


def _m4_v2_utc_instant(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError("recorded_at") from exc
    else:
        raise TypeError("recorded_at")
    if parsed.utcoffset() is None:
        raise ValueError("recorded_at")
    return parsed.astimezone(UTC)


def _load_m4_v2_global_routing_recovery_v1_builder() -> ModuleType:
    """Load the singular recovery-v1 builder without depending on cwd imports."""

    from dehps.config import ROOT_DIR

    try:
        root_dir = ROOT_DIR.resolve()
        builder_path = (
            ROOT_DIR
            / "apps/worker-python/scripts/"
            "build_m4_v2_global_routing_recovery_manifest.py"
        ).resolve()
        if not builder_path.is_relative_to(root_dir):
            raise ValueError(str(builder_path))
        if not builder_path.is_file():
            raise FileNotFoundError(builder_path)
        spec = importlib.util.spec_from_file_location(
            _M4_V2_GLOBAL_RECOVERY_V1_BUILDER_MODULE_NAME,
            builder_path,
        )
        if spec is None:
            raise ImportError("m4_v2_global_recovery_v1_builder_spec_unavailable")
        if spec.loader is None:
            raise ImportError("m4_v2_global_recovery_v1_builder_loader_unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for symbol in _M4_V2_GLOBAL_RECOVERY_V1_REQUIRED_SYMBOLS:
            if not hasattr(module, symbol):
                raise AttributeError(symbol)
        if not callable(module.build_manifest):
            raise TypeError("build_manifest")
        return module
    except Exception as exc:
        raise ResearchOSValidationError(
            "m4_v2_global_recovery_v1_builder_unavailable"
        ) from exc


def _load_m4_v2_global_routing_recovery_v2_builder() -> ModuleType:
    """Load the singular recovery-v2 builder without depending on cwd imports."""

    from dehps.config import ROOT_DIR

    try:
        root_dir = ROOT_DIR.resolve()
        builder_path = (
            ROOT_DIR
            / "apps/worker-python/scripts/"
            "build_m4_v2_global_routing_recovery_v2_manifest.py"
        ).resolve()
        if not builder_path.is_relative_to(root_dir):
            raise ValueError(str(builder_path))
        if not builder_path.is_file():
            raise FileNotFoundError(builder_path)
        spec = importlib.util.spec_from_file_location(
            _M4_V2_GLOBAL_RECOVERY_V2_BUILDER_MODULE_NAME,
            builder_path,
        )
        if spec is None:
            raise ImportError("m4_v2_global_recovery_v2_builder_spec_unavailable")
        if spec.loader is None:
            raise ImportError("m4_v2_global_recovery_v2_builder_loader_unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for symbol in _M4_V2_GLOBAL_RECOVERY_V2_REQUIRED_SYMBOLS:
            if not hasattr(module, symbol):
                raise AttributeError(symbol)
        for symbol in ("build_manifest", "validate_global_source_contract"):
            if not callable(getattr(module, symbol)):
                raise TypeError(symbol)
        error_class = module.GlobalRoutingRecoveryV2Error
        if not isinstance(error_class, type) or not issubclass(
            error_class, BaseException
        ):
            raise TypeError("GlobalRoutingRecoveryV2Error")
        return module
    except Exception as exc:
        raise ResearchOSValidationError(
            "m4_v2_global_recovery_v2_builder_unavailable"
        ) from exc


def _load_m4_v2_global_routing_recovery_v3_builder() -> ModuleType:
    """Load the singular recovery-v3 builder without depending on cwd imports."""

    from dehps.config import ROOT_DIR

    try:
        root_dir = ROOT_DIR.resolve()
        builder_path = (
            ROOT_DIR
            / "apps/worker-python/scripts/"
            "build_m4_v2_global_routing_recovery_v3_manifest.py"
        ).resolve()
        if not builder_path.is_relative_to(root_dir):
            raise ValueError(str(builder_path))
        if not builder_path.is_file():
            raise FileNotFoundError(builder_path)
        spec = importlib.util.spec_from_file_location(
            _M4_V2_GLOBAL_RECOVERY_V3_BUILDER_MODULE_NAME,
            builder_path,
        )
        if spec is None:
            raise ImportError("m4_v2_global_recovery_v3_builder_spec_unavailable")
        if spec.loader is None:
            raise ImportError("m4_v2_global_recovery_v3_builder_loader_unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for symbol in _M4_V2_GLOBAL_RECOVERY_V3_REQUIRED_SYMBOLS:
            if not hasattr(module, symbol):
                raise AttributeError(symbol)
        for symbol in ("build_manifest", "validate_global_source_contract"):
            if not callable(getattr(module, symbol)):
                raise TypeError(symbol)
        error_class = module.GlobalRoutingRecoveryV3Error
        if not isinstance(error_class, type) or not issubclass(error_class, BaseException):
            raise TypeError("GlobalRoutingRecoveryV3Error")
        return module
    except Exception as exc:
        raise ResearchOSValidationError(
            "m4_v2_global_recovery_v3_builder_unavailable"
        ) from exc


def _load_m4_v2_global_routing_replay_compatibility_v1_builder() -> ModuleType:
    """Load the singular approved replay-only compatibility builder."""

    from dehps.config import ROOT_DIR

    try:
        root_dir = ROOT_DIR.resolve()
        builder_path = (
            ROOT_DIR
            / "apps/worker-python/scripts/"
            "build_m4_v2_global_routing_replay_compatibility_v1_manifest.py"
        ).resolve()
        if not builder_path.is_relative_to(root_dir):
            raise ValueError(str(builder_path))
        if not builder_path.is_file():
            raise FileNotFoundError(builder_path)
        spec = importlib.util.spec_from_file_location(
            _M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_BUILDER_MODULE_NAME,
            builder_path,
        )
        if spec is None or spec.loader is None:
            raise ImportError("m4_v2_global_replay_compatibility_builder_unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for symbol in _M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_REQUIRED_SYMBOLS:
            if not hasattr(module, symbol):
                raise AttributeError(symbol)
        for symbol in ("build_manifest", "transition_manifest", "validate_source_contract"):
            if not callable(getattr(module, symbol)):
                raise TypeError(symbol)
        return module
    except Exception as exc:
        raise ResearchOSValidationError(
            "m4_v2_global_replay_compatibility_v1_builder_unavailable"
        ) from exc


def _load_m4_v2_deeper_validation_builder() -> ModuleType:
    """Load the exact additive deeper-validation manifest builder."""

    from dehps.config import ROOT_DIR

    try:
        root_dir = ROOT_DIR.resolve()
        builder_path = (
            ROOT_DIR
            / "apps/worker-python/scripts/build_m4_v2_deeper_validation_manifest.py"
        ).resolve()
        if not builder_path.is_relative_to(root_dir) or not builder_path.is_file():
            raise FileNotFoundError(builder_path)
        spec = importlib.util.spec_from_file_location(
            _M4_V2_DEEPER_VALIDATION_BUILDER_MODULE_NAME,
            builder_path,
        )
        if spec is None or spec.loader is None:
            raise ImportError("m4_v2_deeper_validation_builder_unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for symbol in _M4_V2_DEEPER_VALIDATION_REQUIRED_SYMBOLS:
            if not hasattr(module, symbol):
                raise AttributeError(symbol)
        if not callable(module.build_manifest):
            raise TypeError("build_manifest")
        return module
    except Exception as exc:
        raise ResearchOSValidationError(
            "m4_v2_deeper_validation_builder_unavailable"
        ) from exc


def _load_m4_p4_diagnostic_builder() -> ModuleType:
    """Load the exact additive diagnostic-P4 manifest builder."""

    from dehps.config import ROOT_DIR

    try:
        root_dir = ROOT_DIR.resolve()
        builder_path = (
            ROOT_DIR
            / "apps/worker-python/scripts/build_m4_p4_diagnostic_negative_controls_manifest.py"
        ).resolve()
        if not builder_path.is_relative_to(root_dir) or not builder_path.is_file():
            raise FileNotFoundError(builder_path)
        spec = importlib.util.spec_from_file_location(
            _M4_P4_DIAGNOSTIC_BUILDER_MODULE_NAME,
            builder_path,
        )
        if spec is None or spec.loader is None:
            raise ImportError("m4_p4_diagnostic_builder_unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for symbol in _M4_P4_DIAGNOSTIC_REQUIRED_SYMBOLS:
            if not hasattr(module, symbol):
                raise AttributeError(symbol)
        if not callable(module.build_manifest):
            raise TypeError("build_manifest")
        return module
    except Exception as exc:
        raise ResearchOSValidationError(
            "m4_p4_diagnostic_builder_unavailable"
        ) from exc


def _load_m4_v2_forward_feasibility_builder() -> ModuleType:
    """Load the exact additive zero-compute forward-program builder."""

    from dehps.config import ROOT_DIR

    try:
        root_dir = ROOT_DIR.resolve()
        builder_path = (
            ROOT_DIR
            / "apps/worker-python/scripts/build_m4_v2_forward_evidence_feasibility_manifest.py"
        ).resolve()
        if not builder_path.is_relative_to(root_dir) or not builder_path.is_file():
            raise FileNotFoundError(builder_path)
        spec = importlib.util.spec_from_file_location(
            _M4_V2_FORWARD_FEASIBILITY_BUILDER_MODULE_NAME,
            builder_path,
        )
        if spec is None or spec.loader is None:
            raise ImportError("m4_v2_forward_feasibility_builder_unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for symbol in _M4_V2_FORWARD_FEASIBILITY_REQUIRED_SYMBOLS:
            if not hasattr(module, symbol):
                raise AttributeError(symbol)
        if not callable(module.build_manifest):
            raise TypeError("build_manifest")
        return module
    except Exception as exc:
        raise ResearchOSValidationError(
            "m4_v2_forward_feasibility_builder_unavailable"
        ) from exc


def _load_m4_v2_bounded_forward_builder() -> ModuleType:
    """Load the exact bounded operational forward builder."""

    from dehps.config import ROOT_DIR

    try:
        root_dir = ROOT_DIR.resolve()
        builder_path = (
            ROOT_DIR
            / "apps/worker-python/scripts/build_m4_v2_bounded_operational_forward_manifest.py"
        ).resolve()
        if not builder_path.is_relative_to(root_dir) or not builder_path.is_file():
            raise FileNotFoundError(builder_path)
        spec = importlib.util.spec_from_file_location(
            _M4_V2_BOUNDED_FORWARD_BUILDER_MODULE_NAME, builder_path
        )
        if spec is None or spec.loader is None:
            raise ImportError("m4_v2_bounded_forward_builder_unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for symbol in _M4_V2_BOUNDED_FORWARD_REQUIRED_SYMBOLS:
            if not hasattr(module, symbol):
                raise AttributeError(symbol)
        return module
    except Exception as exc:
        raise ResearchOSValidationError(
            "m4_v2_bounded_forward_builder_unavailable"
        ) from exc


def _load_m4_p3_forward_successor_builder() -> ModuleType:
    """Load the frozen P3 successor builder without depending on cwd imports."""

    from dehps.config import ROOT_DIR

    try:
        root_dir = ROOT_DIR.resolve()
        builder_path = (
            ROOT_DIR
            / "apps/worker-python/scripts/"
            "build_m4_p3_forward_prequential_confirmatory_manifest.py"
        ).resolve()
        if not builder_path.is_relative_to(root_dir) or not builder_path.is_file():
            raise FileNotFoundError(builder_path)
        spec = importlib.util.spec_from_file_location(
            _M4_P3_FORWARD_SUCCESSOR_BUILDER_MODULE_NAME,
            builder_path,
        )
        if spec is None or spec.loader is None:
            raise ImportError("m4_p3_forward_successor_builder_unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for symbol in _M4_P3_FORWARD_SUCCESSOR_REQUIRED_SYMBOLS:
            if not hasattr(module, symbol):
                raise AttributeError(symbol)
        return module
    except Exception as exc:
        raise ResearchOSValidationError(
            "m4_p3_forward_successor_builder_unavailable"
        ) from exc


def _json(value: Any) -> str:
    return json.dumps(jsonable(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def self_or_none_task_digest(manifest: ControlPlaneManifest, task_key: str) -> str | None:
    matches = [task.artifact_digest for task in manifest.tasks if task.task_key == task_key]
    return matches[0] if len(matches) == 1 else None


def _typed_v3_event(row: Any) -> tuple[MainlineExecutionEvent, dict[str, Any]]:
    try:
        raw = dict(row["event_json"])
        if set(raw) != {
            "execution_id",
            "control_plane_key",
            "manifest_digest",
            "task_key",
            "task_digest",
            "capability",
            "event_type",
            "sequence",
            "recorded_at",
            "payload",
        }:
            raise ValueError("event fields")
        payload_items = raw["payload"]
        if not isinstance(payload_items, list) or any(
            not isinstance(item, list) or len(item) != 2 for item in payload_items
        ):
            raise ValueError("event payload")
        event = MainlineExecutionEvent(
            execution_id=str(raw["execution_id"]),
            control_plane_key=str(raw["control_plane_key"]),
            manifest_digest=str(raw["manifest_digest"]),
            task_key=str(raw["task_key"]),
            task_digest=str(raw["task_digest"]),
            capability=str(raw["capability"]),
            event_type=str(raw["event_type"]),
            sequence=int(raw["sequence"]),
            recorded_at=str(raw["recorded_at"]),
            payload=tuple((str(item[0]), item[1]) for item in payload_items),
        )
        payload = dict(event.payload)
        if len(payload) != len(event.payload):
            raise ValueError("duplicate payload field")
        columns = {
            "execution_id": event.execution_id,
            "control_plane_key": event.control_plane_key,
            "manifest_digest": event.manifest_digest,
            "task_digest": event.task_digest,
            "task_key": event.task_key,
            "capability": event.capability,
            "event_type": event.event_type,
            "sequence": event.sequence,
        }
        if (
            str(row["event_digest"]) != event.artifact_digest
            or any(str(row[name]) != str(value) for name, value in columns.items())
            or _m4_v2_utc_instant(row["recorded_at"])
            != _m4_v2_utc_instant(event.recorded_at)
        ):
            raise ValueError("event columns")
        return event, payload
    except (KeyError, TypeError, ValueError) as exc:
        raise ResearchOSValidationError(
            "m4_v2_global_recovery_v3_output_changed"
        ) from exc


def _verify_v3_started_event(
    row: Any,
    *,
    control_plane_key: str,
    running: ControlPlaneManifest,
    recovery_task: Task,
) -> tuple[str, str]:
    event, payload = _typed_v3_event(row)
    if (
        event.control_plane_key != control_plane_key
        or event.manifest_digest != running.artifact_digest
        or event.task_key != recovery_task.task_key
        or event.task_digest != recovery_task.artifact_digest
        or event.capability != recovery_task.requested_capability
        or event.event_type != "started"
        or event.sequence != 0
        or set(payload) != {"input_artifact_digests", "git_commit"}
        or payload["input_artifact_digests"]
        != list(recovery_task.input_artifact_digests)
    ):
        raise ResearchOSValidationError("m4_v2_global_recovery_v3_output_changed")
    git_commit = str(payload["git_commit"])
    if len(git_commit) != 40 or any(character not in "0123456789abcdef" for character in git_commit):
        raise ResearchOSValidationError("m4_v2_global_recovery_v3_output_changed")
    expected_execution = stable_hash(
        {
            "schema": "dehps-research-os-mainline-execution.v1",
            "control_plane_key": control_plane_key,
            "task_digest": recovery_task.artifact_digest,
            "capability": recovery_task.requested_capability,
            "input_artifact_digests": recovery_task.input_artifact_digests,
            "git_commit": git_commit,
        }
    )
    if event.execution_id != expected_execution:
        raise ResearchOSValidationError("m4_v2_global_recovery_v3_output_changed")
    return event.execution_id, git_commit


def _verify_v3_completed_projection(
    rows: Any,
    *,
    manifest: ControlPlaneManifest,
    running: ControlPlaneManifest,
    recovery_task: Task,
    terminal_event: MainlineExecutionEvent,
    terminal_payload: dict[str, Any],
    execution_id: str,
    git_commit: str,
    source_digest: str,
) -> None:
    error = "m4_v2_global_recovery_v3_output_changed"
    if terminal_event.event_type != "completed" or len(rows) != 2:
        raise ResearchOSValidationError(error)
    metric = json.loads(recovery_task.metric_contract)
    expected_fields = {
        "execution_artifact_digest",
        "execution_artifact_path",
        "actual_fold_count",
        "registered_artifact_count",
        "git_commit",
        "completion_facts",
        "additional_completed_task_keys",
        "publication_batch_digest",
        "workload_rerun",
        "source_contract_digest",
        "source_set_digest",
        "route_decision_artifact_digest",
        "route",
        "downstream_consumer",
        "decision_replay_coverage",
        "historical_database_reads",
        "scientific_computation",
        "replay_status",
    }
    route = str(terminal_payload.get("route") or "")
    route_fact = dict(metric["route_facts"]).get(route)
    completion_fact = str(metric["completion_fact"])
    route_digest = str(terminal_payload.get("route_decision_artifact_digest") or "")
    execution_digest = str(terminal_payload.get("execution_artifact_digest") or "")
    execution_path = (
        f"runtime/research-os/mainline/tasks/{recovery_task.task_key}/"
        f"{execution_id}/execution.json"
    )
    route_path = str(metric["route_artifact_path_template"]).format(
        execution_id=execution_id, artifact_digest=route_digest
    )
    if (
        set(terminal_payload) != expected_fields
        or route_fact is None
        or terminal_payload["completion_facts"] != [route_fact, completion_fact]
        or terminal_payload["additional_completed_task_keys"] != []
        or int(terminal_payload["actual_fold_count"]) != 0
        or int(terminal_payload["registered_artifact_count"]) != 2
        or terminal_payload["workload_rerun"] is not False
        or str(terminal_payload["git_commit"]) != git_commit
        or str(terminal_payload["source_contract_digest"]) != source_digest
        or terminal_payload["decision_replay_coverage"] != "COMPLETE"
        or int(terminal_payload["historical_database_reads"]) != 0
        or int(terminal_payload["scientific_computation"]) != 0
        or terminal_payload["replay_status"] != "REGISTERED_REPLAY_PENDING"
        or str(terminal_payload["execution_artifact_path"]) != execution_path
        or any(
            len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
            for value in (route_digest, execution_digest, str(terminal_payload["publication_batch_digest"]))
        )
    ):
        raise ResearchOSValidationError(error)
    mainline_fact = (
        f"mainline-execution:{recovery_task.task_key}:{recovery_task.artifact_digest}:"
        f"{execution_id}:completed"
    )
    payload = running.to_dict(include_digest=False)
    target = next(item for item in payload["tasks"] if item["task_key"] == recovery_task.task_key)
    target["status"] = "completed"
    target["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"] = sorted(
        {*payload["facts"]["artifacts"], mainline_fact, route_fact, completion_fact}
    )
    expected_manifest = ControlPlaneManifest.from_dict(payload)
    if manifest.to_dict(include_digest=True) != expected_manifest.to_dict(include_digest=True):
        raise ResearchOSValidationError(error)
    registrations: list[MainlineArtifactRegistration] = []
    try:
        for row in rows:
            raw = dict(row["registration_json"])
            registration = MainlineArtifactRegistration(
                execution_id=str(raw["execution_id"]),
                control_plane_key=str(raw["control_plane_key"]),
                task_key=str(raw["task_key"]),
                task_digest=str(raw["task_digest"]),
                artifact_digest=str(raw["artifact_digest"]),
                artifact_type=str(raw["artifact_type"]),
                schema_version=str(raw["schema_version"]),
                artifact_path=str(raw["artifact_path"]),
                parent_digests=tuple(str(value) for value in raw["parent_digests"]),
                git_commit=str(raw["git_commit"]),
            )
            expected_columns = {
                "registration_digest": registration.registration_digest,
                "execution_id": registration.execution_id,
                "control_plane_key": registration.control_plane_key,
                "task_digest": registration.task_digest,
                "task_key": registration.task_key,
                "artifact_digest": registration.artifact_digest,
                "artifact_type": registration.artifact_type,
                "schema_version": registration.schema_version,
                "artifact_path": registration.artifact_path,
                "git_commit": registration.git_commit,
            }
            if (
                set(row)
                != {
                    *expected_columns,
                    "parent_digests_json",
                    "registration_json",
                }
                or any(str(row[key]) != value for key, value in expected_columns.items())
                or tuple(str(value) for value in row["parent_digests_json"])
                != registration.parent_digests
                or raw != jsonable(registration)
            ):
                raise ValueError("registration digest")
            registrations.append(registration)
    except (KeyError, TypeError, ValueError) as exc:
        raise ResearchOSValidationError(error) from exc
    route_registration, execution_registration = registrations
    if (
        route_registration.artifact_digest != route_digest
        or route_registration.artifact_path != route_path
        or route_registration.parent_digests
        or execution_registration.artifact_digest != execution_digest
        or execution_registration.artifact_path != execution_path
        or execution_registration.parent_digests != (source_digest, route_digest)
        or any(
            item.execution_id != execution_id
            or item.control_plane_key != terminal_event.control_plane_key
            or item.task_key != recovery_task.task_key
            or item.task_digest != recovery_task.artifact_digest
            or item.git_commit != git_commit
            for item in registrations
        )
    ):
        raise ResearchOSValidationError(error)
    expected_batch = m4_v2_domain_digest(
        {
            "control_plane_key": terminal_event.control_plane_key,
            "expected_head_manifest_digest": running.artifact_digest,
            "task_key": recovery_task.task_key,
            "task_digest": recovery_task.artifact_digest,
            "execution_id": execution_id,
            "git_commit": git_commit,
            "ordered_artifact_digest_path_pairs": [
                {
                    "artifact_digest": route_registration.artifact_digest,
                    "canonical_artifact_path": route_registration.artifact_path,
                },
                {
                    "artifact_digest": execution_registration.artifact_digest,
                    "canonical_artifact_path": execution_registration.artifact_path,
                },
            ],
        },
        domain="dehps.m4.v2.mainline-publication-batch-identity.v1",
    )
    if str(terminal_payload["publication_batch_digest"]) != expected_batch:
        raise ResearchOSValidationError(error)


@dataclass(frozen=True)
class ManifestImportResult:
    control_plane_key: str
    manifest_digest: str
    snapshot_digest: str
    created_goal_definitions: int
    created_task_definitions: int
    created_manifest: bool
    goal_revisions: tuple[tuple[str, str, str], ...]
    task_revisions: tuple[tuple[str, str, str], ...]
    ready_task_keys: tuple[str, ...]
    dispatch_performed: bool = False
    production_impact: str = "none"


class PostgresResearchOSRepository:
    """Durable P2 shadow repository; it never dispatches or writes legacy state."""

    def __init__(
        self,
        connection_factory: ConnectionFactory = get_connection,
        *,
        control_plane: ResearchOSControlPlane | None = None,
    ) -> None:
        self.connection_factory = connection_factory
        self.control_plane = control_plane or ResearchOSControlPlane()

    def ensure_schema(self) -> None:
        with self.connection_factory() as conn:
            ensure_research_os_schema(conn)

    def import_manifest(
        self,
        *,
        control_plane_key: str,
        payload: dict[str, Any],
        source: str = "native",
    ) -> ManifestImportResult:
        key = self._key(control_plane_key)
        source = self._key(source)
        manifest = ControlPlaneManifest.from_dict(payload)
        snapshot = self.control_plane.resolve(manifest)
        normalized_payload = manifest.to_dict(include_digest=False)
        resolutions = {item.task_digest: item for item in snapshot.resolutions}

        created_goals = 0
        created_tasks = 0
        created_manifest = False
        goal_revisions: list[tuple[str, str, str]] = []
        task_revisions: list[tuple[str, str, str]] = []

        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            validation_manifest = manifest
            if type(self) is PostgresResearchOSRepository and self._verify_m4_p3_forward_successor_import(
                cursor,
                control_plane_key=key,
                manifest=manifest,
            ):
                validation_payload = manifest.to_dict(include_digest=False)
                validation_payload["facts"]["external_events"] = [
                    value
                    for value in validation_payload["facts"]["external_events"]
                    if not (
                        value.startswith("m4-p3-forward-prequential:")
                        and value.endswith(":DRAW_SYNCED")
                    )
                ]
                validation_manifest = ControlPlaneManifest.from_dict(
                    validation_payload
                )
            recovery_v3 = _load_m4_v2_global_routing_recovery_v3_builder()
            v3_successor_present = any(
                task.task_key == recovery_v3.RECOVERY_TASK_KEY
                for task in manifest.tasks
            )
            self._verify_m4_v2_failed_global_routing_recovery_v3_import(
                cursor, control_plane_key=key, manifest=validation_manifest
            )
            if not v3_successor_present:
                self._verify_m4_v2_failed_global_routing_recovery_v2_import(
                    cursor, control_plane_key=key, manifest=manifest
                )
            self._verify_m4_v2_failed_global_routing_recovery_import(
                cursor, control_plane_key=key, manifest=manifest
            )
            replay_recovery = self._verify_m4_v2_failed_replay_recovery_import(
                cursor, control_plane_key=key, manifest=manifest
            )
            if not replay_recovery:
                self._verify_m4_v2_failed_task_recovery_import(
                    cursor,
                    control_plane_key=key,
                    manifest=manifest,
                )
            self._verify_mainline_completion_records(
                cursor,
                control_plane_key=key,
                manifest=manifest,
                m4_v2_lifecycle_verified=True,
            )
            previous_goals, previous_tasks = self._current_revisions(cursor, key)
            self._verify_no_mainline_completion_regression(
                cursor,
                control_plane_key=key,
                manifest=manifest,
                previous_tasks=previous_tasks,
            )
            for goal in manifest.goals:
                inserted = cursor.execute(
                    """
                    INSERT INTO research_os_goal_definitions (
                      goal_digest, goal_key, semantic_version, objective_class,
                      owner_lane, definition_json
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (goal_digest) DO NOTHING
                    RETURNING goal_digest
                    """,
                    (
                        goal.artifact_digest,
                        goal.goal_key,
                        goal.semantic_version,
                        goal.objective_class.value,
                        goal.owner_lane.value,
                        _json(goal.to_dict()),
                    ),
                ).fetchone()
                created_goals += int(inserted is not None)
                self._verify_goal_definition(cursor, goal)

            for task in manifest.tasks:
                inserted = cursor.execute(
                    """
                    INSERT INTO research_os_task_definitions (
                      task_digest, task_key, goal_digest, task_type, lane,
                      priority, definition_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (task_digest) DO NOTHING
                    RETURNING task_digest
                    """,
                    (
                        task.artifact_digest,
                        task.task_key,
                        task.goal_digest,
                        task.task_type,
                        task.lane.value,
                        task.priority,
                        _json(task.to_dict()),
                    ),
                ).fetchone()
                created_tasks += int(inserted is not None)
                self._verify_task_definition(cursor, task)

            inserted_manifest = cursor.execute(
                """
                INSERT INTO research_os_manifests (
                  manifest_digest, schema_version, manifest_json, source
                ) VALUES (%s, %s, %s::jsonb, %s)
                ON CONFLICT (manifest_digest) DO NOTHING
                RETURNING manifest_digest
                """,
                (
                    manifest.artifact_digest,
                    manifest.schema_version,
                    _json(normalized_payload),
                    source,
                ),
            ).fetchone()
            created_manifest = inserted_manifest is not None
            self._verify_manifest_row(cursor, manifest)

            for ordinal, goal in enumerate(manifest.goals):
                cursor.execute(
                    """
                    INSERT INTO research_os_manifest_goals (manifest_digest, goal_digest, ordinal)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (manifest.artifact_digest, goal.artifact_digest, ordinal),
                )
            for ordinal, task in enumerate(manifest.tasks):
                cursor.execute(
                    """
                    INSERT INTO research_os_manifest_tasks (manifest_digest, task_digest, ordinal)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (manifest.artifact_digest, task.artifact_digest, ordinal),
                )

            cursor.execute(
                """
                INSERT INTO research_os_control_planes (
                  control_plane_key, schema_version, current_manifest_digest, source
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (control_plane_key) DO UPDATE
                SET schema_version = EXCLUDED.schema_version,
                    current_manifest_digest = EXCLUDED.current_manifest_digest,
                    source = EXCLUDED.source,
                    updated_at = now()
                """,
                (key, manifest.schema_version, manifest.artifact_digest, source),
            )

            current_goals = {goal.goal_key: goal.artifact_digest for goal in manifest.goals}
            current_tasks = {task.task_key: task.artifact_digest for task in manifest.tasks}
            for goal_key, old_digest in previous_goals.items():
                new_digest = current_goals.get(goal_key)
                if new_digest and new_digest != old_digest:
                    goal_revisions.append((goal_key, old_digest, new_digest))
                    cursor.execute(
                        """
                        UPDATE research_os_goal_states
                        SET status = 'retired', retired_at = COALESCE(retired_at, now()),
                            superseded_by_goal_digest = %s, updated_at = now()
                        WHERE control_plane_key = %s AND goal_digest = %s
                        """,
                        (new_digest, key, old_digest),
                    )
            for task_key, old_digest in previous_tasks.items():
                new_digest = current_tasks.get(task_key)
                if new_digest and new_digest != old_digest:
                    task_revisions.append((task_key, old_digest, new_digest))
                    cursor.execute(
                        """
                        UPDATE research_os_task_states
                        SET declared_status = 'superseded', resolved_status = 'superseded',
                            reason_code = 'definition_superseded',
                            dependency_state_json = '[]'::jsonb,
                            superseded_by_task_digest = %s, updated_at = now()
                        WHERE control_plane_key = %s AND task_digest = %s
                        """,
                        (new_digest, key, old_digest),
                    )

            goal_states = manifest.goal_state_by_digest
            for goal in manifest.goals:
                state = goal_states[goal.artifact_digest]
                cursor.execute(
                    """
                    INSERT INTO research_os_goal_states (
                      control_plane_key, goal_digest, status, retired_at,
                      superseded_by_goal_digest
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (control_plane_key, goal_digest) DO UPDATE
                    SET status = EXCLUDED.status,
                        retired_at = EXCLUDED.retired_at,
                        superseded_by_goal_digest = EXCLUDED.superseded_by_goal_digest,
                        updated_at = now()
                    """,
                    (
                        key,
                        goal.artifact_digest,
                        state.status.value,
                        state.retired_at,
                        state.superseded_by_goal_digest,
                    ),
                )

            task_states = manifest.task_state_by_digest
            for task in manifest.tasks:
                state = task_states[task.artifact_digest]
                resolution = resolutions[task.artifact_digest]
                cursor.execute(
                    """
                    INSERT INTO research_os_task_states (
                      control_plane_key, task_digest, declared_status, resolved_status,
                      completion_classification, reason_code, dependency_state_json,
                      superseded_by_task_digest
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (control_plane_key, task_digest) DO UPDATE
                    SET declared_status = EXCLUDED.declared_status,
                        resolved_status = EXCLUDED.resolved_status,
                        completion_classification = EXCLUDED.completion_classification,
                        reason_code = EXCLUDED.reason_code,
                        dependency_state_json = EXCLUDED.dependency_state_json,
                        superseded_by_task_digest = EXCLUDED.superseded_by_task_digest,
                        updated_at = now()
                    """,
                    (
                        key,
                        task.artifact_digest,
                        state.declared_status.value,
                        resolution.status.value,
                        (
                            None
                            if state.completion_classification is None
                            else state.completion_classification.value
                        ),
                        resolution.reason_code,
                        _json(resolution.unsatisfied_dependencies),
                        state.superseded_by_task_digest,
                    ),
                )

            cursor.execute(
                "DELETE FROM research_os_dependency_facts WHERE control_plane_key = %s",
                (key,),
            )
            for fact_type, fact_key in self._fact_rows(manifest):
                cursor.execute(
                    """
                    INSERT INTO research_os_dependency_facts (
                      control_plane_key, fact_type, fact_key
                    ) VALUES (%s, %s, %s)
                    """,
                    (key, fact_type, fact_key),
                )

        return ManifestImportResult(
            control_plane_key=key,
            manifest_digest=manifest.artifact_digest,
            snapshot_digest=snapshot.snapshot_digest,
            created_goal_definitions=created_goals,
            created_task_definitions=created_tasks,
            created_manifest=created_manifest,
            goal_revisions=tuple(goal_revisions),
            task_revisions=tuple(task_revisions),
            ready_task_keys=tuple(item.task_key for item in snapshot.ready_queue),
        )

    @staticmethod
    def _verify_m4_v2_failed_task_recovery_import(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
    ) -> None:
        """Bind the frozen failed lineage before the recovery transaction writes."""

        from dehps.research_os.information_theory.measurement_system_v2.migration import (
            M4_V2_FAILED_EXECUTION_ID,
            M4_V2_FAILED_TASK_KEY,
            M4_V2_ORIGINAL_TASK_DEFINITIONS,
            M4_V2_RECOVERY_INPUT_MANIFEST_DIGEST,
            M4_V2_RECOVERY_TASK_KEY,
            AdditiveManifestMigrationError,
            verify_failed_task_recovery_event_metadata,
        )

        canonical_control_plane_key = "m4-information-theory-mainline"
        task_keys = {task.task_key for task in manifest.tasks}
        if (
            control_plane_key != canonical_control_plane_key
            or M4_V2_RECOVERY_TASK_KEY not in task_keys
        ):
            return
        if M4_V2_FAILED_TASK_KEY in task_keys:
            raise ResearchOSValidationError(
                "m4_v2_recovery_old_failed_task_still_active"
            )

        control = cursor.execute(
            """
            SELECT current_manifest_digest
            FROM research_os_control_planes
            WHERE control_plane_key = %s
            FOR UPDATE
            """,
            (control_plane_key,),
        ).fetchone()
        if control is None:
            raise ResearchOSValidationError(
                "m4_v2_recovery_control_plane_not_initialized"
            )
        current_manifest_digest = str(control["current_manifest_digest"])
        if current_manifest_digest not in {
            M4_V2_RECOVERY_INPUT_MANIFEST_DIGEST,
            manifest.artifact_digest,
        }:
            stored = cursor.execute(
                """
                SELECT manifest_json
                FROM research_os_manifests
                WHERE manifest_digest = %s
                """,
                (current_manifest_digest,),
            ).fetchone()
            if stored is None:
                raise ResearchOSValidationError(
                    "m4_v2_recovery_current_manifest_missing"
                )
            current_manifest = ControlPlaneManifest.from_dict(
                dict(stored["manifest_json"])
            )
            current_tasks = {
                task.task_key: task.artifact_digest for task in current_manifest.tasks
            }
            incoming_tasks = {
                task.task_key: task.artifact_digest for task in manifest.tasks
            }
            successor_keys = {
                key for key, _digest in M4_V2_ORIGINAL_TASK_DEFINITIONS
            }
            successor_keys.remove(M4_V2_FAILED_TASK_KEY)
            successor_keys.add(M4_V2_RECOVERY_TASK_KEY)
            if (
                M4_V2_FAILED_TASK_KEY in current_tasks
                or not successor_keys.issubset(current_tasks)
                or any(
                    current_tasks[key] != incoming_tasks.get(key)
                    for key in successor_keys
                )
            ):
                raise ResearchOSValidationError(
                    "m4_v2_recovery_current_manifest_lineage_changed"
                )

        original_task_digest = dict(M4_V2_ORIGINAL_TASK_DEFINITIONS)[
            M4_V2_FAILED_TASK_KEY
        ]
        state = cursor.execute(
            """
            SELECT td.task_digest, ts.declared_status,
                   ts.completion_classification, ts.superseded_by_task_digest
            FROM research_os_task_definitions td
            JOIN research_os_task_states ts ON ts.task_digest = td.task_digest
            WHERE ts.control_plane_key = %s
              AND td.task_key = %s
              AND td.task_digest = %s
            """,
            (
                control_plane_key,
                M4_V2_FAILED_TASK_KEY,
                original_task_digest,
            ),
        ).fetchone()
        if (
            state is None
            or str(state["task_digest"]) != original_task_digest
            or str(state["declared_status"]) != "failed"
            or str(state["completion_classification"]) != "INTEGRATED"
            or state["superseded_by_task_digest"] is not None
        ):
            raise ResearchOSValidationError(
                "m4_v2_recovery_failed_task_state_changed"
            )

        rows = cursor.execute(
            """
            SELECT event_digest, execution_id, control_plane_key,
                   manifest_digest, task_digest, task_key, capability,
                   event_type, sequence
            FROM research_os_mainline_execution_events
            WHERE control_plane_key = %s
              AND task_key = %s
              AND execution_id = %s
            ORDER BY sequence, event_digest
            """,
            (
                control_plane_key,
                M4_V2_FAILED_TASK_KEY,
                M4_V2_FAILED_EXECUTION_ID,
            ),
        ).fetchall()
        try:
            verify_failed_task_recovery_event_metadata(tuple(dict(row) for row in rows))
        except AdditiveManifestMigrationError as exc:
            raise ResearchOSValidationError(str(exc)) from exc

    @staticmethod
    def _verify_m4_v2_failed_replay_recovery_import(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
    ) -> bool:
        """Verify the append-only failed replay lineage before any import write."""

        from dehps.research_os.information_theory.measurement_system_v2.migration import (
            M4_V2_FAILED_REPLAY_EXECUTION_ID,
            M4_V2_FAILED_REPLAY_OLDER_TASK_DIGEST,
            M4_V2_FAILED_REPLAY_TASK_DIGEST,
            M4_V2_FAILED_REPLAY_TASK_KEY,
            M4_V2_REPLAY_RECOVERY_INPUT_MANIFEST_DIGEST,
            M4_V2_REPLAY_RECOVERY_TASK_KEY,
            AdditiveManifestMigrationError,
            verify_failed_replay_recovery_event_metadata,
        )

        task_by_key = {task.task_key: task for task in manifest.tasks}
        recovery = task_by_key.get(M4_V2_REPLAY_RECOVERY_TASK_KEY)
        if recovery is None:
            return False
        if control_plane_key != "m4-information-theory-mainline":
            raise ResearchOSValidationError(
                "m4_v2_replay_recovery_control_plane_changed"
            )
        if M4_V2_FAILED_REPLAY_TASK_KEY in task_by_key:
            raise ResearchOSValidationError(
                "m4_v2_replay_recovery_old_failed_task_still_active"
            )

        control = cursor.execute(
            """
            SELECT current_manifest_digest
            FROM research_os_control_planes
            WHERE control_plane_key = %s
            FOR UPDATE
            """,
            (control_plane_key,),
        ).fetchone()
        if control is None:
            raise ResearchOSValidationError(
                "m4_v2_replay_recovery_control_plane_not_initialized"
            )
        current_manifest_digest = str(control["current_manifest_digest"])
        if current_manifest_digest not in {
            M4_V2_REPLAY_RECOVERY_INPUT_MANIFEST_DIGEST,
            manifest.artifact_digest,
        }:
            stored = cursor.execute(
                """
                SELECT manifest_json
                FROM research_os_manifests
                WHERE manifest_digest = %s
                """,
                (current_manifest_digest,),
            ).fetchone()
            if stored is None:
                raise ResearchOSValidationError(
                    "m4_v2_replay_recovery_current_manifest_missing"
                )
            current_manifest = ControlPlaneManifest.from_dict(
                dict(stored["manifest_json"])
            )
            current_by_key = {
                task.task_key: task.artifact_digest
                for task in current_manifest.tasks
            }
            if (
                M4_V2_FAILED_REPLAY_TASK_KEY in current_by_key
                or current_by_key.get(M4_V2_REPLAY_RECOVERY_TASK_KEY)
                != recovery.artifact_digest
            ):
                raise ResearchOSValidationError(
                    "m4_v2_replay_recovery_current_manifest_lineage_changed"
                )

        states = cursor.execute(
            """
            SELECT td.task_digest, ts.declared_status,
                   ts.completion_classification, ts.superseded_by_task_digest
            FROM research_os_task_definitions td
            JOIN research_os_task_states ts ON ts.task_digest = td.task_digest
            WHERE ts.control_plane_key = %s
              AND td.task_key = %s
              AND td.task_digest IN (%s, %s)
            ORDER BY td.task_digest
            """,
            (
                control_plane_key,
                M4_V2_FAILED_REPLAY_TASK_KEY,
                M4_V2_FAILED_REPLAY_TASK_DIGEST,
                M4_V2_FAILED_REPLAY_OLDER_TASK_DIGEST,
            ),
        ).fetchall()
        state_by_digest = {str(row["task_digest"]): row for row in states}
        active = state_by_digest.get(M4_V2_FAILED_REPLAY_TASK_DIGEST)
        older = state_by_digest.get(M4_V2_FAILED_REPLAY_OLDER_TASK_DIGEST)
        if (
            active is None
            or str(active["declared_status"]) != "failed"
            or str(active["completion_classification"]) != "INTEGRATED"
            or active["superseded_by_task_digest"] is not None
            or older is None
            or str(older["declared_status"]) != "superseded"
            or str(older["completion_classification"]) != "INTEGRATION_PENDING"
            or str(older["superseded_by_task_digest"])
            != M4_V2_FAILED_REPLAY_TASK_DIGEST
        ):
            raise ResearchOSValidationError(
                "m4_v2_replay_recovery_failed_task_lineage_changed"
            )

        rows = cursor.execute(
            """
            SELECT event_digest, execution_id, control_plane_key,
                   manifest_digest, task_digest, task_key, capability,
                   event_type, sequence
            FROM research_os_mainline_execution_events
            WHERE control_plane_key = %s
              AND task_key = %s
              AND execution_id = %s
            ORDER BY sequence, event_digest
            """,
            (
                control_plane_key,
                M4_V2_FAILED_REPLAY_TASK_KEY,
                M4_V2_FAILED_REPLAY_EXECUTION_ID,
            ),
        ).fetchall()
        try:
            verify_failed_replay_recovery_event_metadata(
                tuple(dict(row) for row in rows)
            )
        except AdditiveManifestMigrationError as exc:
            raise ResearchOSValidationError(str(exc)) from exc
        return True

    @staticmethod
    def _verify_m4_v2_failed_global_routing_recovery_v3_import(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
    ) -> None:
        """Verify the terminal recovery-v2 lineage and finite recovery-v3 stages."""

        from dehps.config import ROOT_DIR

        builder = _load_m4_v2_global_routing_recovery_v3_builder()
        tasks = {task.task_key: task for task in manifest.tasks}
        bounded_preregistration = tasks.get(
            _M4_V2_BOUNDED_FORWARD_PREREGISTRATION_TASK_KEY
        )
        if (
            bounded_preregistration is not None
            and bounded_preregistration.requested_capability
            == "m4_v2_bounded_operational_forward_study_preregistration"
        ):
            PostgresResearchOSRepository._verify_m4_v2_bounded_forward_import(
                cursor,
                control_plane_key=control_plane_key,
                manifest=manifest,
            )
            return
        if _M4_V2_FORWARD_FEASIBILITY_TASK_KEY in tasks:
            PostgresResearchOSRepository._verify_m4_v2_forward_feasibility_import(
                cursor,
                control_plane_key=control_plane_key,
                manifest=manifest,
            )
            return
        if _M4_P4_DIAGNOSTIC_FIRST_TASK_KEY in tasks:
            PostgresResearchOSRepository._verify_m4_p4_diagnostic_import(
                cursor,
                control_plane_key=control_plane_key,
                manifest=manifest,
            )
            return
        if _M4_V2_DEEPER_VALIDATION_INTAKE_TASK_KEY in tasks:
            PostgresResearchOSRepository._verify_m4_v2_deeper_validation_import(
                cursor,
                control_plane_key=control_plane_key,
                manifest=manifest,
            )
            return
        if _M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_TASK_KEY in tasks:
            compatibility = _load_m4_v2_global_routing_replay_compatibility_v1_builder()
            if (
                compatibility.SUCCESSOR_TASK_KEY
                != _M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_TASK_KEY
            ):
                raise ResearchOSValidationError(
                    "m4_v2_global_replay_compatibility_v1_task_identity_changed"
                )
            PostgresResearchOSRepository._verify_m4_v2_global_routing_replay_compatibility_v1_import(
                cursor,
                control_plane_key=control_plane_key,
                manifest=manifest,
                builder=compatibility,
            )
            return
        recovery = tasks.get(builder.RECOVERY_TASK_KEY)
        incoming_baseline = manifest.artifact_digest == builder.INPUT_MANIFEST_DIGEST
        if recovery is None and not incoming_baseline:
            return
        error = "m4_v2_global_recovery_v3_output_changed"
        if control_plane_key != "m4-information-theory-mainline":
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v3_control_plane_changed"
            )
        if (
            builder.OLD_TASK_KEY not in tasks
            or tasks[builder.OLD_TASK_KEY].artifact_digest != builder.OLD_TASK_DIGEST
            or (incoming_baseline and recovery is not None)
            or (
                not incoming_baseline
                and (
                    recovery is None
                    or len(recovery.input_artifact_digests) != 1
                )
            )
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v3_task_identity_changed"
            )
        control = cursor.execute(
            """SELECT current_manifest_digest FROM research_os_control_planes
               WHERE control_plane_key = %s FOR UPDATE""",
            (control_plane_key,),
        ).fetchone()
        if control is None:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v3_control_plane_missing"
            )
        baseline_row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (builder.INPUT_MANIFEST_DIGEST,),
        ).fetchone()
        if baseline_row is None:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v3_input_manifest_missing"
            )
        try:
            baseline = ControlPlaneManifest.from_dict(dict(baseline_row["manifest_json"]))
        except (KeyError, TypeError, ValueError, ResearchOSValidationError) as exc:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v3_input_manifest_changed"
            ) from exc
        if (
            baseline.artifact_digest != builder.INPUT_MANIFEST_DIGEST
            or self_or_none_task_digest(baseline, builder.OLD_TASK_KEY)
            != builder.OLD_TASK_DIGEST
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v3_input_manifest_changed"
            )
        current_digest = str(control["current_manifest_digest"])
        current_row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (current_digest,),
        ).fetchone()
        if current_row is None:
            raise ResearchOSValidationError("m4_v2_global_recovery_v3_manifest_missing")
        current = ControlPlaneManifest.from_dict(dict(current_row["manifest_json"]))
        try:
            source_payload = json.loads(
                (ROOT_DIR / builder.GLOBAL_SOURCE_PATH).read_text(encoding="utf-8")
            )
            source_digest = builder.validate_global_source_contract(
                source_payload, root_dir=ROOT_DIR
            )
            expected_payload, _ = builder.build_manifest(
                baseline.to_dict(include_digest=True),
                global_source_contract_digest=source_digest,
            )
        except (OSError, ValueError, TypeError, builder.GlobalRoutingRecoveryV3Error) as exc:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v3_source_changed"
            ) from exc
        ready = ControlPlaneManifest.from_dict(expected_payload)
        if recovery is not None and recovery.input_artifact_digests != (source_digest,):
            raise ResearchOSValidationError("m4_v2_global_recovery_v3_source_changed")

        def transition(
            source_manifest: ControlPlaneManifest,
            *,
            status: str,
            classification: str,
            facts: tuple[str, ...] = (),
        ) -> ControlPlaneManifest:
            payload = source_manifest.to_dict(include_digest=False)
            matches = [
                item
                for item in payload["tasks"]
                if item["task_key"] == builder.RECOVERY_TASK_KEY
            ]
            if len(matches) != 1:
                raise ResearchOSValidationError(error)
            matches[0]["status"] = status
            matches[0]["completion_classification"] = classification
            if facts:
                payload["facts"]["artifacts"] = sorted(
                    {*payload["facts"]["artifacts"], *facts}
                )
            return ControlPlaneManifest.from_dict(payload)

        running = transition(ready, status="running", classification="INTEGRATED")
        failed = transition(running, status="failed", classification="INTEGRATED")

        def fixed_stage(value: ControlPlaneManifest) -> str | None:
            digest = value.artifact_digest
            return {
                baseline.artifact_digest: "INPUT_BASELINE",
                ready.artifact_digest: "READY",
                running.artifact_digest: "RUNNING",
                failed.artifact_digest: "FAILED",
            }.get(digest)

        incoming_stage = fixed_stage(manifest)
        current_stage = fixed_stage(current)
        if incoming_stage is None:
            target = tasks.get(builder.RECOVERY_TASK_KEY)
            if target is not None:
                state = manifest.task_state_by_digest[target.artifact_digest]
                if state.declared_status.value == "completed":
                    incoming_stage = "COMPLETED"
        if current_stage is None:
            target = next(
                (task for task in current.tasks if task.task_key == builder.RECOVERY_TASK_KEY),
                None,
            )
            if target is not None:
                state = current.task_state_by_digest[target.artifact_digest]
                if state.declared_status.value == "completed":
                    current_stage = "COMPLETED"
        legal = {
            "INPUT_BASELINE": {"INPUT_BASELINE", "READY"},
            "READY": {"READY", "RUNNING"},
            "RUNNING": {"RUNNING", "COMPLETED", "FAILED"},
            "COMPLETED": {"COMPLETED"},
            "FAILED": {"FAILED"},
        }
        if current_stage is None or incoming_stage not in legal[current_stage]:
            raise ResearchOSValidationError(error)

        predecessor_events = cursor.execute(
            """SELECT event_digest, execution_id, manifest_digest, task_digest,
                      task_key, event_type, sequence
               FROM research_os_mainline_execution_events
               WHERE control_plane_key = %s AND task_key = %s
               ORDER BY sequence, event_digest""",
            (control_plane_key, builder.OLD_TASK_KEY),
        ).fetchall()
        expected_predecessor_events = (
            (
                builder.OLD_STARTED_EVENT_DIGEST,
                builder.OLD_EXECUTION_ID,
                builder.OLD_EVENT_MANIFEST_DIGEST,
                builder.OLD_TASK_DIGEST,
                builder.OLD_TASK_KEY,
                "started",
                0,
            ),
            (
                builder.OLD_FAILED_EVENT_DIGEST,
                builder.OLD_EXECUTION_ID,
                builder.OLD_EVENT_MANIFEST_DIGEST,
                builder.OLD_TASK_DIGEST,
                builder.OLD_TASK_KEY,
                "failed",
                1,
            ),
        )
        observed_predecessor_events = tuple(
            (
                str(row["event_digest"]),
                str(row["execution_id"]),
                str(row["manifest_digest"]),
                str(row["task_digest"]),
                str(row["task_key"]),
                str(row["event_type"]),
                int(row["sequence"]),
            )
            for row in predecessor_events
        )
        predecessor_registrations = cursor.execute(
            """SELECT registration_digest FROM research_os_mainline_artifacts
               WHERE control_plane_key = %s AND task_key = %s""",
            (control_plane_key, builder.OLD_TASK_KEY),
        ).fetchall()
        if (
            observed_predecessor_events != expected_predecessor_events
            or predecessor_registrations
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v3_event_lineage_changed"
            )

        runtime_rows = cursor.execute(
            """SELECT event_digest, execution_id, control_plane_key,
                      manifest_digest, task_digest, task_key, capability,
                      event_type, sequence, recorded_at, event_json
               FROM research_os_mainline_execution_events
               WHERE control_plane_key = %s AND task_key = %s
               ORDER BY sequence, event_digest""",
            (control_plane_key, builder.RECOVERY_TASK_KEY),
        ).fetchall()
        if incoming_stage in {"INPUT_BASELINE", "READY"}:
            if runtime_rows:
                raise ResearchOSValidationError(error)
            return
        if incoming_stage == "RUNNING":
            if len(runtime_rows) not in ({0} if current_stage == "READY" else {0, 1}):
                raise ResearchOSValidationError(error)
            if runtime_rows:
                _verify_v3_started_event(
                    runtime_rows[0],
                    control_plane_key=control_plane_key,
                    running=running,
                    recovery_task=next(
                        task for task in ready.tasks if task.task_key == builder.RECOVERY_TASK_KEY
                    ),
                )
            return
        if len(runtime_rows) != 2:
            raise ResearchOSValidationError(error)
        execution_id, git_commit = _verify_v3_started_event(
            runtime_rows[0],
            control_plane_key=control_plane_key,
            running=running,
            recovery_task=next(
                task for task in ready.tasks if task.task_key == builder.RECOVERY_TASK_KEY
            ),
        )
        terminal_event, terminal_payload = _typed_v3_event(runtime_rows[1])
        recovery_task = next(
            task for task in ready.tasks if task.task_key == builder.RECOVERY_TASK_KEY
        )
        if (
            terminal_event.execution_id != execution_id
            or terminal_event.control_plane_key != control_plane_key
            or terminal_event.manifest_digest != running.artifact_digest
            or terminal_event.task_key != builder.RECOVERY_TASK_KEY
            or terminal_event.task_digest != recovery_task.artifact_digest
            or terminal_event.capability != recovery_task.requested_capability
            or terminal_event.sequence != 1
        ):
            raise ResearchOSValidationError(error)
        registration_rows = cursor.execute(
            """SELECT registration_digest, execution_id, control_plane_key,
                      task_digest, task_key, artifact_digest, artifact_type,
                      schema_version, artifact_path, parent_digests_json,
                      git_commit, registration_json
               FROM research_os_mainline_artifacts
               WHERE control_plane_key = %s AND task_key = %s
                 AND execution_id = %s
               ORDER BY artifact_path, registration_digest""",
            (control_plane_key, builder.RECOVERY_TASK_KEY, execution_id),
        ).fetchall()
        if incoming_stage == "FAILED":
            if (
                terminal_event.event_type != "failed"
                or set(terminal_payload) != {"error", "git_commit"}
                or not str(terminal_payload["error"])
                or str(terminal_payload["git_commit"]) != git_commit
                or registration_rows
                or manifest.to_dict(include_digest=True)
                != failed.to_dict(include_digest=True)
            ):
                raise ResearchOSValidationError(error)
            return
        _verify_v3_completed_projection(
            registration_rows,
            manifest=manifest,
            running=running,
            recovery_task=recovery_task,
            terminal_event=terminal_event,
            terminal_payload=terminal_payload,
            execution_id=execution_id,
            git_commit=git_commit,
            source_digest=source_digest,
        )

    @staticmethod
    def _verify_m4_p4_diagnostic_import(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
    ) -> None:
        """Verify the exact additive diagnostic-only P4 lifecycle."""

        from dehps.config import ROOT_DIR
        from dehps.research_os.information_theory.measurement_system_v2 import (
            diagnostic_negative_controls as diagnostic,
        )

        error = "m4_p4_diagnostic_output_changed"
        if control_plane_key != "m4-information-theory-mainline":
            raise ResearchOSValidationError("m4_p4_diagnostic_control_plane_changed")
        builder = _load_m4_p4_diagnostic_builder()
        control = cursor.execute(
            """SELECT current_manifest_digest FROM research_os_control_planes
               WHERE control_plane_key = %s FOR UPDATE""",
            (control_plane_key,),
        ).fetchone()
        baseline_row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (builder.BASELINE_MANIFEST_DIGEST,),
        ).fetchone()
        if control is None or baseline_row is None:
            raise ResearchOSValidationError("m4_p4_diagnostic_baseline_missing")
        current_digest = str(control["current_manifest_digest"])
        current_row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (current_digest,),
        ).fetchone()
        if current_row is None:
            raise ResearchOSValidationError("m4_p4_diagnostic_current_missing")
        try:
            baseline = ControlPlaneManifest.from_dict(dict(baseline_row["manifest_json"]))
            current = ControlPlaneManifest.from_dict(dict(current_row["manifest_json"]))
            source = diagnostic.load_source_contract(root_dir=ROOT_DIR)
            expected_payload, _ = builder.build_manifest(
                baseline.to_dict(include_digest=True),
                source_contract_digest=str(source["artifact_digest"]),
            )
            expected = ControlPlaneManifest.from_dict(expected_payload)
        except Exception as exc:
            raise ResearchOSValidationError(error) from exc

        baseline_goals = {item.goal_key: item for item in baseline.goals}
        expected_goals = {item.goal_key: item for item in expected.goals}
        incoming_goals = {item.goal_key: item for item in manifest.goals}
        baseline_tasks = {item.task_key: item for item in baseline.tasks}
        expected_tasks = {item.task_key: item for item in expected.tasks}
        incoming_tasks = {item.task_key: item for item in manifest.tasks}
        new_keys = tuple(builder.NEW_TASK_KEYS)
        if (
            baseline.artifact_digest != builder.BASELINE_MANIFEST_DIGEST
            or len(incoming_goals) != len(manifest.goals)
            or len(incoming_tasks) != len(manifest.tasks)
            or set(incoming_goals) != set(expected_goals)
            or set(incoming_tasks) != set(expected_tasks)
            or any(
                incoming_goals[key].to_dict() != baseline_goals[key].to_dict()
                for key in baseline_goals
            )
            or incoming_goals[builder.GOAL_KEY].to_dict()
            != expected_goals[builder.GOAL_KEY].to_dict()
            or any(
                incoming_tasks[key].to_dict() != baseline_tasks[key].to_dict()
                for key in baseline_tasks
            )
            or any(
                incoming_tasks[key].to_dict() != expected_tasks[key].to_dict()
                for key in new_keys
            )
        ):
            raise ResearchOSValidationError(error)

        baseline_states = baseline.task_state_by_digest
        incoming_states = manifest.task_state_by_digest
        if any(
            incoming_states[baseline_tasks[key].artifact_digest]
            != baseline_states[baseline_tasks[key].artifact_digest]
            for key in baseline_tasks
        ):
            raise ResearchOSValidationError(error)
        states = [incoming_states[incoming_tasks[key].artifact_digest] for key in new_keys]
        state_values = [state.declared_status.value for state in states]
        completed_count = 0
        while completed_count < len(state_values) and state_values[completed_count] == "completed":
            completed_count += 1
        expected_tail = ["draft"] * (len(state_values) - completed_count)
        if completed_count < len(state_values) and state_values[completed_count] == "running":
            expected_tail[0] = "running"
        if state_values != ["completed"] * completed_count + expected_tail:
            raise ResearchOSValidationError(error)
        for index, state in enumerate(states):
            expected_classification = (
                "COMPLETE"
                if index < completed_count
                else "INTEGRATED"
                if state.declared_status.value == "running"
                else "INTEGRATION_PENDING"
            )
            actual = (
                None
                if state.completion_classification is None
                else state.completion_classification.value
            )
            if actual != expected_classification:
                raise ResearchOSValidationError(error)

        formal_baseline = baseline_tasks[builder.FORMAL_P4_TASK_KEY]
        formal_incoming = incoming_tasks[builder.FORMAL_P4_TASK_KEY]
        if (
            formal_incoming.to_dict() != formal_baseline.to_dict()
            or incoming_states[formal_incoming.artifact_digest]
            != baseline_states[formal_baseline.artifact_digest]
        ):
            raise ResearchOSValidationError("m4_p4_diagnostic_formal_p4_changed")

        base_facts = baseline.facts.to_dict()
        incoming_facts = manifest.facts.to_dict()
        for category in ("evidence", "external_events", "authorities"):
            if incoming_facts[category] != base_facts[category]:
                raise ResearchOSValidationError(error)
        source_fact = builder.SOURCE_FACT_PREFIX + str(source["artifact_digest"])
        custom_by_task = (
            {
                diagnostic.P3_CLOSURE_COMPLETION_FACT,
                "m4-p3-scientific-disposition:INCONCLUSIVE_DUE_TO_POWER",
                "m4-p3-governance-status:CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION",
            },
            {diagnostic.PREREGISTRATION_COMPLETION_FACT},
            {diagnostic.EXECUTION_COMPLETION_FACT},
            {diagnostic.EVIDENCE_COMPLETION_FACT},
            {diagnostic.DECISION_COMPLETION_FACT},
            {
                diagnostic.REPLAY_COMPLETION_FACT,
                diagnostic.REPLAY_VERIFIED_FACT,
            },
        )
        expected_custom = {source_fact}
        for facts in custom_by_task[:completed_count]:
            expected_custom.update(facts)
        artifacts = set(incoming_facts["artifacts"])
        base_artifacts = set(base_facts["artifacts"])
        if diagnostic.FORMAL_P4_PASS_FACT in artifacts:
            raise ResearchOSValidationError("m4_p4_diagnostic_pass_to_p4_emitted")
        decision_facts = {
            fact for fact in artifacts if fact.startswith("m4-p4-diagnostic-decision:")
        }
        status_facts = {
            fact for fact in artifacts if fact.startswith("m4-p4-diagnostic-status:")
        }
        if completed_count >= 5:
            allowed_decisions = {
                f"m4-p4-diagnostic-decision:{value}" for value in diagnostic.DECISIONS
            }
            allowed_statuses = {
                "m4-p4-diagnostic-status:COMPLETE",
                "m4-p4-diagnostic-status:INVALID",
                "m4-p4-diagnostic-status:INCONCLUSIVE",
            }
            if (
                len(decision_facts) != 1
                or not decision_facts.issubset(allowed_decisions)
                or len(status_facts) != 1
                or not status_facts.issubset(allowed_statuses)
            ):
                raise ResearchOSValidationError(error)
            expected_custom.update(decision_facts | status_facts)
        elif decision_facts or status_facts:
            raise ResearchOSValidationError(error)
        dynamic = artifacts - base_artifacts - expected_custom
        if not base_artifacts.issubset(artifacts) or any(
            not any(
                fact.startswith(
                    f"mainline-execution:{key}:{incoming_tasks[key].artifact_digest}:"
                )
                and fact.endswith(":completed")
                for key in new_keys[:completed_count]
            )
            for fact in dynamic
        ):
            raise ResearchOSValidationError(error)
        if len(dynamic) != completed_count or artifacts != (
            base_artifacts | expected_custom | dynamic
        ):
            raise ResearchOSValidationError(error)
        current_keys = {item.task_key for item in current.tasks}
        if current.artifact_digest != baseline.artifact_digest and not all(
            key in current_keys for key in new_keys
        ):
            raise ResearchOSValidationError(error)

    @staticmethod
    def _verify_m4_p3_forward_successor_import(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
    ) -> bool:
        """Fail closed around the exact frozen successor runtime transitions."""

        from dehps.config import ROOT_DIR
        from dehps.research_os.information_theory.measurement_system_v2 import (
            forward_prequential_confirmatory as successor,
        )

        if control_plane_key != "m4-information-theory-mainline":
            return False
        incoming_tasks = {item.task_key: item for item in manifest.tasks}
        if not any(
            task.requested_capability in successor.CAPABILITIES
            for task in incoming_tasks.values()
        ):
            return False
        control = cursor.execute(
            "SELECT current_manifest_digest FROM research_os_control_planes "
            "WHERE control_plane_key = %s FOR UPDATE",
            (control_plane_key,),
        ).fetchone()
        if control is None:
            return False
        current_row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests "
            "WHERE manifest_digest = %s",
            (str(control["current_manifest_digest"]),),
        ).fetchone()
        if current_row is None:
            raise ResearchOSValidationError(
                "m4_p3_forward_successor_current_manifest_missing"
            )
        current = ControlPlaneManifest.from_dict(dict(current_row["manifest_json"]))
        current_tasks = {item.task_key: item for item in current.tasks}
        current_p3_keys = {
            key
            for key, task in current_tasks.items()
            if task.requested_capability in successor.CAPABILITIES
        }
        if not current_p3_keys:
            return False

        current_external = set(current.facts.external_events)
        incoming_external = set(manifest.facts.external_events)
        added_external = incoming_external - current_external
        added_tasks = set(incoming_tasks) - set(current_tasks)
        state_changes: list[
            tuple[str, tuple[str, str | None], tuple[str, str | None]]
        ] = []
        for key in set(current_tasks).intersection(incoming_tasks):
            old = current_tasks[key]
            new = incoming_tasks[key]
            old_state = current.task_state_by_digest[old.artifact_digest]
            new_state = manifest.task_state_by_digest[new.artifact_digest]
            old_pair = (
                old_state.declared_status.value,
                (
                    None
                    if old_state.completion_classification is None
                    else old_state.completion_classification.value
                ),
            )
            new_pair = (
                new_state.declared_status.value,
                (
                    None
                    if new_state.completion_classification is None
                    else new_state.completion_classification.value
                ),
            )
            if old_pair != new_pair:
                state_changes.append((key, old_pair, new_pair))

        p3_event_delta = {
            value
            for value in added_external
            if value.startswith("m4-p3-forward-prequential:")
            and value.endswith(":DRAW_SYNCED")
        }
        p3_added_tasks = {
            key
            for key in added_tasks
            if incoming_tasks[key].requested_capability in successor.CAPABILITIES
        }
        p3_state_changes = [
            value for value in state_changes if value[0] in current_p3_keys
        ]
        if not p3_event_delta and not p3_added_tasks and not p3_state_changes:
            return False

        error = "m4_p3_forward_successor_import_changed"
        current_payload = current.to_dict(include_digest=False)
        incoming_payload = manifest.to_dict(include_digest=False)
        if (
            current_payload["schema_version"] != incoming_payload["schema_version"]
            or current_payload["goals"] != incoming_payload["goals"]
            or current.facts.evidence != manifest.facts.evidence
            or current.facts.authorities != manifest.facts.authorities
            or current.facts.artifacts != manifest.facts.artifacts
            or not current_external.issubset(incoming_external)
        ):
            raise ResearchOSValidationError(error)
        if set(current_tasks) - set(incoming_tasks):
            raise ResearchOSValidationError(error)
        if any(
            incoming_tasks[key].to_dict() != current_tasks[key].to_dict()
            for key in current_tasks
        ):
            raise ResearchOSValidationError(error)
        if any(value[0] not in current_p3_keys for value in state_changes):
            raise ResearchOSValidationError(error)
        if added_tasks != p3_added_tasks or added_external != p3_event_delta:
            raise ResearchOSValidationError(error)

        operation_count = sum(
            bool(value)
            for value in (p3_event_delta, p3_added_tasks, p3_state_changes)
        )
        if operation_count != 1:
            raise ResearchOSValidationError(error)

        issue_values: set[str] = set()
        for task in current_tasks.values():
            if task.requested_capability not in successor.CAPABILITIES:
                continue
            issue = str(task.to_dict().get("metric_contract", {}).get("target_issue") or "")
            if issue:
                issue_values.add(issue)

        if p3_event_delta:
            if len(p3_event_delta) != 1 or state_changes or added_tasks:
                raise ResearchOSValidationError(error)
            event = next(iter(p3_event_delta))
            issue = event.removeprefix("m4-p3-forward-prequential:").removesuffix(
                ":DRAW_SYNCED"
            )
            keys = successor.issue_task_keys(issue)
            if (
                issue not in issue_values
                or set(keys.values()) - set(current_tasks)
                or event != successor.issue_facts(issue)["draw_synced"]
            ):
                raise ResearchOSValidationError(error)
            replay = current_tasks[keys["predraw_replay"]]
            replay_state = current.task_state_by_digest[replay.artifact_digest]
            settlement = current_tasks[keys["settlement"]]
            settlement_state = current.task_state_by_digest[settlement.artifact_digest]
            if (
                replay_state.declared_status.value != "completed"
                or replay_state.completion_classification is None
                or replay_state.completion_classification.value != "COMPLETE"
                or successor.issue_facts(issue)["predraw_replay"]
                not in current.facts.artifacts
                or settlement_state.declared_status.value == "completed"
            ):
                raise ResearchOSValidationError(error)
            return True

        if p3_state_changes:
            if len(p3_state_changes) != 1 or added_tasks or added_external:
                raise ResearchOSValidationError(error)
            key, old_state, new_state = p3_state_changes[0]
            if (
                old_state[0] != "draft"
                or old_state[1] not in {None, "INTEGRATION_PENDING"}
                or new_state != ("running", "INTEGRATED")
                or current_tasks[key].requested_capability not in successor.CAPABILITIES
            ):
                raise ResearchOSValidationError(error)
            return True

        if len(p3_added_tasks) != 5 or state_changes or added_external:
            raise ResearchOSValidationError(error)
        added_issues = {
            str(
                incoming_tasks[key]
                .to_dict()
                .get("metric_contract", {})
                .get("target_issue")
                or ""
            )
            for key in p3_added_tasks
        }
        if len(added_issues) != 1 or not issue_values:
            raise ResearchOSValidationError(error)
        target_issue = next(iter(added_issues))
        previous_issue = max(issue_values)
        if not target_issue or target_issue <= previous_issue:
            raise ResearchOSValidationError(error)
        expected_keys = set(successor.issue_task_keys(target_issue).values())
        draw_dates = {
            str(
                incoming_tasks[key]
                .to_dict()
                .get("metric_contract", {})
                .get("target_draw_date")
                or ""
            )
            for key in p3_added_tasks
        }
        previous_fact = successor.issue_facts(previous_issue)["settlement_replay"]
        previous_replay = current_tasks[
            successor.issue_task_keys(previous_issue)["settlement_replay"]
        ]
        previous_state = current.task_state_by_digest[previous_replay.artifact_digest]
        if (
            p3_added_tasks != expected_keys
            or len(draw_dates) != 1
            or "" in draw_dates
            or previous_fact not in current.facts.artifacts
            or previous_state.declared_status.value != "completed"
            or previous_state.completion_classification is None
            or previous_state.completion_classification.value != "COMPLETE"
        ):
            raise ResearchOSValidationError(error)
        source = successor.load_source_contract(root_dir=ROOT_DIR)
        builder = _load_m4_p3_forward_successor_builder()
        goal_digest = next(
            item.artifact_digest
            for item in current.goals
            if item.goal_key == successor.GOAL_KEY
        )
        expected = {
            item["task_key"]: Task.from_dict({**item, "goal_digest": goal_digest})
            for item in builder.issue_tasks(
                source_digest=str(source["artifact_digest"]),
                target_issue=target_issue,
                target_draw_date=next(iter(draw_dates)),
                previous_settlement_replay_fact=previous_fact,
            )
        }
        if any(
            key not in expected
            or incoming_tasks[key].to_dict() != expected[key].to_dict()
            for key in p3_added_tasks
        ):
            raise ResearchOSValidationError(error)
        return True

    @staticmethod
    def _verify_m4_v2_bounded_forward_import(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
    ) -> None:
        """Verify the frozen bounded forward lifecycle and per-issue shape."""

        from dehps.config import ROOT_DIR
        from dehps.research_os.information_theory.measurement_system_v2 import (
            bounded_operational_forward as bounded,
        )

        error = "m4_v2_bounded_forward_output_changed"
        if control_plane_key != "m4-information-theory-mainline":
            raise ResearchOSValidationError("m4_v2_bounded_forward_control_plane_changed")
        builder = _load_m4_v2_bounded_forward_builder()
        source = bounded.load_source_contract(root_dir=ROOT_DIR)
        source_digest = str(source["artifact_digest"])
        control = cursor.execute(
            "SELECT current_manifest_digest FROM research_os_control_planes "
            "WHERE control_plane_key = %s FOR UPDATE",
            (control_plane_key,),
        ).fetchone()
        if control is None:
            raise ResearchOSValidationError("m4_v2_bounded_forward_control_missing")
        current_row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (str(control["current_manifest_digest"]),),
        ).fetchone()
        baseline_row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (builder.BASELINE_MANIFEST_DIGEST,),
        ).fetchone()
        if current_row is None or baseline_row is None:
            raise ResearchOSValidationError("m4_v2_bounded_forward_baseline_missing")
        current = ControlPlaneManifest.from_dict(dict(current_row["manifest_json"]))
        baseline = ControlPlaneManifest.from_dict(dict(baseline_row["manifest_json"]))
        incoming_tasks = {item.task_key: item for item in manifest.tasks}
        incoming_goals = {item.goal_key: item for item in manifest.goals}
        refits = [
            item
            for item in manifest.tasks
            if item.requested_capability == bounded.REFIT_CAPABILITY
        ]
        if not refits:
            raise ResearchOSValidationError(error)

        if current.artifact_digest == builder.BASELINE_MANIFEST_DIGEST:
            contract = refits[0].to_dict().get("metric_contract", {})
            target_issue = str(contract.get("target_issue") or "")
            target_draw_date = str(contract.get("target_draw_date") or "")
            try:
                expected_payload, _ = builder.build_manifest(
                    baseline.to_dict(include_digest=True),
                    source_contract_digest=source_digest,
                    target_issue=target_issue,
                    target_draw_date=target_draw_date,
                )
                expected = ControlPlaneManifest.from_dict(expected_payload)
            except Exception as exc:
                raise ResearchOSValidationError(error) from exc
            if manifest.to_dict(include_digest=True) != expected.to_dict(include_digest=True):
                raise ResearchOSValidationError(error)
            return

        def definition(value: Task) -> dict[str, Any]:
            payload = value.to_dict()
            for field in (
                "goal_digest",
                "status",
                "completion_classification",
                "superseded_by_task_digest",
            ):
                payload.pop(field, None)
            return payload

        current_tasks = {item.task_key: item for item in current.tasks}
        current_goals = {item.goal_key: item for item in current.goals}
        if any(
            key not in incoming_tasks
            or definition(incoming_tasks[key]) != definition(task)
            for key, task in current_tasks.items()
        ) or any(
            key not in incoming_goals
            or incoming_goals[key].to_dict() != goal.to_dict()
            for key, goal in current_goals.items()
        ):
            raise ResearchOSValidationError(error)
        if (
            bounded.GOAL_KEY not in incoming_goals
            or incoming_goals[bounded.GOAL_KEY].to_dict()
            != Goal.from_dict(builder._goal()).to_dict()
        ):
            raise ResearchOSValidationError(error)
        preregistration = incoming_tasks.get(bounded.PREREGISTRATION_TASK_KEY)
        if (
            preregistration is None
            or definition(preregistration)
            != definition(Task.from_dict(builder.preregistration_task(source_digest=source_digest)))
        ):
            raise ResearchOSValidationError(error)

        issue_values = sorted(
            {
                str(item.to_dict().get("metric_contract", {}).get("target_issue"))
                for item in manifest.tasks
                if item.requested_capability
                in {
                    bounded.REFIT_CAPABILITY,
                    bounded.PREDRAW_CAPABILITY,
                    bounded.PREDRAW_REPLAY_CAPABILITY,
                    bounded.SETTLEMENT_CAPABILITY,
                    bounded.SETTLEMENT_REPLAY_CAPABILITY,
                }
            }
        )
        for index, issue in enumerate(issue_values):
            matching = [
                item
                for item in manifest.tasks
                if item.task_key in bounded.issue_task_keys(issue).values()
            ]
            if len(matching) != 5:
                raise ResearchOSValidationError(error)
            draw_dates = {
                str(item.to_dict()["metric_contract"].get("target_draw_date"))
                for item in matching
            }
            if len(draw_dates) != 1:
                raise ResearchOSValidationError(error)
            refit = incoming_tasks[bounded.issue_task_keys(issue)["refit"]]
            replay_dependencies = [
                dependency.target_key
                for dependency in refit.dependencies
                if dependency.dependency_type.value == "artifact"
                and dependency.target_key.endswith(
                    ":REGISTERED_REPLAY_VERIFIED"
                )
            ]
            if len(replay_dependencies) > 1:
                raise ResearchOSValidationError(error)
            previous_fact = replay_dependencies[0] if replay_dependencies else None
            if previous_fact is not None:
                earlier_facts = {
                    bounded.issue_facts(value)["settlement_replay"]
                    for value in issue_values[:index]
                }
                if (
                    previous_fact not in earlier_facts
                    or previous_fact not in manifest.facts.artifacts
                ):
                    raise ResearchOSValidationError(error)
            expected = {
                item["task_key"]: Task.from_dict(item)
                for item in builder.issue_tasks(
                    source_digest=source_digest,
                    target_issue=issue,
                    target_draw_date=next(iter(draw_dates)),
                    previous_settlement_replay_fact=previous_fact,
                )
            }
            if any(
                key not in incoming_tasks
                or definition(incoming_tasks[key]) != definition(task)
                for key, task in expected.items()
            ):
                raise ResearchOSValidationError(error)

        facts = manifest.facts.to_dict()
        if (
            builder.SOURCE_FACT_PREFIX + source_digest not in facts["artifacts"]
            or "m4-p3-predictive-decision:PASS_TO_P4" in facts["artifacts"]
            or any(
                not value.startswith("m4-v2-bounded-operational-forward:")
                or not value.endswith(":DRAW_SYNCED")
                for value in set(facts["external_events"])
                - set(current.facts.to_dict()["external_events"])
            )
        ):
            raise ResearchOSValidationError(error)
        formal_baseline = next(
            item for item in baseline.tasks if item.task_key == builder.FORMAL_P4_TASK_KEY
        )
        formal_incoming = incoming_tasks[builder.FORMAL_P4_TASK_KEY]
        if definition(formal_incoming) != definition(formal_baseline):
            raise ResearchOSValidationError("m4_v2_bounded_forward_formal_p4_changed")
        formal_resolution = next(
            item
            for item in ResearchOSControlPlane().resolve(manifest).resolutions
            if item.task_key == builder.FORMAL_P4_TASK_KEY
        )
        if formal_resolution.status.value != "dependency_wait":
            raise ResearchOSValidationError(error)

    @staticmethod
    def _verify_m4_v2_forward_feasibility_import(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
    ) -> None:
        """Verify the exact two-task zero-compute forward-program lifecycle."""

        from dehps.config import ROOT_DIR
        from dehps.research_os.information_theory.measurement_system_v2 import (
            forward_evidence_feasibility as forward,
        )

        error = "m4_v2_forward_feasibility_output_changed"
        if control_plane_key != "m4-information-theory-mainline":
            raise ResearchOSValidationError(
                "m4_v2_forward_feasibility_control_plane_changed"
            )
        builder = _load_m4_v2_forward_feasibility_builder()
        baseline_row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (builder.BASELINE_MANIFEST_DIGEST,),
        ).fetchone()
        control = cursor.execute(
            "SELECT current_manifest_digest FROM research_os_control_planes "
            "WHERE control_plane_key = %s FOR UPDATE",
            (control_plane_key,),
        ).fetchone()
        if baseline_row is None or control is None:
            raise ResearchOSValidationError(
                "m4_v2_forward_feasibility_baseline_missing"
            )
        try:
            baseline = ControlPlaneManifest.from_dict(dict(baseline_row["manifest_json"]))
            source = forward.load_source_contract(root_dir=ROOT_DIR)
            expected_payload, _ = builder.build_manifest(
                baseline.to_dict(include_digest=True),
                source_contract_digest=str(source["artifact_digest"]),
            )
            expected = ControlPlaneManifest.from_dict(expected_payload)
        except Exception as exc:
            raise ResearchOSValidationError(error) from exc

        baseline_goals = {item.goal_key: item for item in baseline.goals}
        expected_goals = {item.goal_key: item for item in expected.goals}
        incoming_goals = {item.goal_key: item for item in manifest.goals}
        baseline_tasks = {item.task_key: item for item in baseline.tasks}
        expected_tasks = {item.task_key: item for item in expected.tasks}
        incoming_tasks = {item.task_key: item for item in manifest.tasks}
        if (
            baseline.artifact_digest != builder.BASELINE_MANIFEST_DIGEST
            or len(incoming_goals) != len(manifest.goals)
            or len(incoming_tasks) != len(manifest.tasks)
            or set(incoming_goals) != set(expected_goals)
            or set(incoming_tasks) != set(expected_tasks)
            or any(
                incoming_goals[key].to_dict() != baseline_goals[key].to_dict()
                for key in baseline_goals
            )
            or incoming_goals[builder.GOAL_KEY].to_dict()
            != expected_goals[builder.GOAL_KEY].to_dict()
            or any(
                incoming_tasks[key].to_dict() != baseline_tasks[key].to_dict()
                for key in baseline_tasks
            )
            or any(
                incoming_tasks[key].to_dict() != expected_tasks[key].to_dict()
                for key in builder.NEW_TASK_KEYS
            )
        ):
            raise ResearchOSValidationError(error)

        baseline_states = baseline.task_state_by_digest
        incoming_states = manifest.task_state_by_digest
        if any(
            incoming_states[task.artifact_digest]
            != baseline_states[task.artifact_digest]
            for task in baseline.tasks
        ):
            raise ResearchOSValidationError(error)
        decision_task = incoming_tasks[forward.TASK_KEY]
        successor_task = incoming_tasks[forward.SUCCESSOR_TASK_KEY]
        decision_state = incoming_states[decision_task.artifact_digest]
        successor_state = incoming_states[successor_task.artifact_digest]
        decision_status = decision_state.declared_status.value
        decision_class = (
            None
            if decision_state.completion_classification is None
            else decision_state.completion_classification.value
        )
        if (
            (decision_status, decision_class)
            not in {
                ("draft", "INTEGRATION_PENDING"),
                ("running", "INTEGRATED"),
                ("completed", "COMPLETE"),
            }
            or successor_state.declared_status.value != "draft"
            or successor_state.completion_classification is None
            or successor_state.completion_classification.value
            != "INTEGRATION_PENDING"
        ):
            raise ResearchOSValidationError(error)

        baseline_facts = baseline.facts.to_dict()
        incoming_facts = manifest.facts.to_dict()
        for category in ("evidence", "external_events", "authorities"):
            if incoming_facts[category] != baseline_facts[category]:
                raise ResearchOSValidationError(error)
        base_artifacts = set(baseline_facts["artifacts"])
        artifacts = set(incoming_facts["artifacts"])
        source_fact = builder.SOURCE_FACT_PREFIX + str(source["artifact_digest"])
        expected_custom = {source_fact}
        if decision_status == "completed":
            expected_custom.update(
                {
                    forward.COMPLETION_FACT,
                    forward.PROGRAM_FACT,
                    forward.REUSE_POLICY_FACT,
                }
            )
        dynamic = artifacts - base_artifacts - expected_custom
        if decision_status == "completed":
            dynamic_fact = next(iter(dynamic)) if len(dynamic) == 1 else ""
            if (
                not dynamic_fact.startswith(
                    f"mainline-execution:{forward.TASK_KEY}:"
                    f"{decision_task.artifact_digest}:"
                )
                or not dynamic_fact.endswith(":completed")
            ):
                raise ResearchOSValidationError(error)
        elif dynamic:
            raise ResearchOSValidationError(error)
        if artifacts != base_artifacts | expected_custom | dynamic:
            raise ResearchOSValidationError(error)
        if (
            "m4-p3-predictive-decision:PASS_TO_P4" in artifacts
            or any(fact.startswith("m4-v2-forward-program:") for fact in artifacts)
            != (decision_status == "completed")
        ):
            raise ResearchOSValidationError(error)

        formal_expected = baseline_tasks[builder.FORMAL_P4_TASK_KEY]
        formal_incoming = incoming_tasks[builder.FORMAL_P4_TASK_KEY]
        if (
            formal_incoming.to_dict() != formal_expected.to_dict()
            or incoming_states[formal_incoming.artifact_digest]
            != baseline_states[formal_expected.artifact_digest]
        ):
            raise ResearchOSValidationError(
                "m4_v2_forward_feasibility_formal_p4_changed"
            )
        snapshot = ResearchOSControlPlane().resolve(manifest)
        ready = tuple(item.task_key for item in snapshot.ready_queue)
        expected_ready = (
            (forward.TASK_KEY,)
            if decision_status == "draft"
            else (forward.SUCCESSOR_TASK_KEY,)
            if decision_status == "completed"
            else ()
        )
        formal_resolution = next(
            item for item in snapshot.resolutions
            if item.task_key == builder.FORMAL_P4_TASK_KEY
        )
        if ready != expected_ready or formal_resolution.status.value != "dependency_wait":
            raise ResearchOSValidationError(error)

    @staticmethod
    def _verify_m4_v2_deeper_validation_import(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
    ) -> None:
        """Verify the exact additive, zero-compute deeper-validation lifecycle."""

        from dehps.config import ROOT_DIR
        from dehps.research_os.information_theory.measurement_system_v2 import (
            deeper_validation,
        )

        error = "m4_v2_deeper_validation_output_changed"
        if control_plane_key != "m4-information-theory-mainline":
            raise ResearchOSValidationError(
                "m4_v2_deeper_validation_control_plane_changed"
            )
        builder = _load_m4_v2_deeper_validation_builder()
        control = cursor.execute(
            """SELECT current_manifest_digest FROM research_os_control_planes
               WHERE control_plane_key = %s FOR UPDATE""",
            (control_plane_key,),
        ).fetchone()
        baseline_row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (builder.BASELINE_MANIFEST_DIGEST,),
        ).fetchone()
        if control is None or baseline_row is None:
            raise ResearchOSValidationError(
                "m4_v2_deeper_validation_baseline_missing"
            )
        current_digest = str(control["current_manifest_digest"])
        current_row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (current_digest,),
        ).fetchone()
        if current_row is None:
            raise ResearchOSValidationError(
                "m4_v2_deeper_validation_current_missing"
            )
        try:
            baseline = ControlPlaneManifest.from_dict(dict(baseline_row["manifest_json"]))
            current = ControlPlaneManifest.from_dict(dict(current_row["manifest_json"]))
            source = deeper_validation.load_source_contract(root_dir=ROOT_DIR)
            expected_payload, _ = builder.build_manifest(
                baseline.to_dict(include_digest=True),
                source_contract_digest=str(source["artifact_digest"]),
            )
            expected = ControlPlaneManifest.from_dict(expected_payload)
        except Exception as exc:
            raise ResearchOSValidationError(error) from exc

        baseline_tasks = {item.task_key: item for item in baseline.tasks}
        expected_tasks = {item.task_key: item for item in expected.tasks}
        incoming_tasks = {item.task_key: item for item in manifest.tasks}
        new_keys = tuple(builder.NEW_TASK_KEYS)
        if (
            baseline.artifact_digest != builder.BASELINE_MANIFEST_DIGEST
            or len(incoming_tasks) != len(manifest.tasks)
            or set(incoming_tasks) != set(expected_tasks)
            or tuple(goal.to_dict() for goal in manifest.goals)
            != tuple(goal.to_dict() for goal in baseline.goals)
            or any(
                incoming_tasks[key].to_dict() != baseline_tasks[key].to_dict()
                for key in baseline_tasks
            )
            or any(
                incoming_tasks[key].to_dict() != expected_tasks[key].to_dict()
                for key in new_keys
            )
        ):
            raise ResearchOSValidationError(error)

        baseline_states = baseline.task_state_by_digest
        incoming_states = manifest.task_state_by_digest
        if any(
            incoming_states[baseline_tasks[key].artifact_digest]
            != baseline_states[baseline_tasks[key].artifact_digest]
            for key in baseline_tasks
        ):
            raise ResearchOSValidationError(error)
        states = [incoming_states[incoming_tasks[key].artifact_digest] for key in new_keys]
        state_values = [state.declared_status.value for state in states]
        completed_count = 0
        while (
            completed_count < len(state_values)
            and state_values[completed_count] == "completed"
        ):
            completed_count += 1
        expected_tail = ["draft"] * (len(state_values) - completed_count)
        if completed_count < len(state_values) and state_values[completed_count] == "running":
            expected_tail[0] = "running"
        if state_values != ["completed"] * completed_count + expected_tail:
            raise ResearchOSValidationError(error)
        for index, state in enumerate(states):
            expected_classification = (
                "COMPLETE"
                if index < completed_count
                else "INTEGRATED"
                if state.declared_status.value == "running"
                else "INTEGRATION_PENDING"
            )
            actual_classification = (
                None
                if state.completion_classification is None
                else state.completion_classification.value
            )
            if actual_classification != expected_classification:
                raise ResearchOSValidationError(error)

        base_facts = baseline.facts.to_dict()
        incoming_facts = manifest.facts.to_dict()
        for category in ("evidence", "external_events", "authorities"):
            if incoming_facts[category] != base_facts[category]:
                raise ResearchOSValidationError(error)
        source_fact = builder.SOURCE_FACT_PREFIX + str(source["artifact_digest"])
        custom_by_task = (
            {deeper_validation.INTAKE_COMPLETION_FACT},
            {deeper_validation.DECISION_COMPLETION_FACT},
            {
                deeper_validation.DECISION_REPLAY_COMPLETION_FACT,
                deeper_validation.DECISION_REPLAY_VERIFIED_FACT,
            },
            {
                deeper_validation.ROUTE_COMPLETION_FACT,
                "m4-v2-routing:FORWARD_EVIDENCE_REQUIRED",
                "m4-v2-predictive-p3:CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION",
            },
            {
                deeper_validation.ROUTE_REPLAY_COMPLETION_FACT,
                deeper_validation.ROUTE_REPLAY_VERIFIED_FACT,
            },
        )
        expected_custom = {source_fact}
        for facts in custom_by_task[:completed_count]:
            expected_custom.update(facts)
        artifacts = set(incoming_facts["artifacts"])
        base_artifacts = set(base_facts["artifacts"])
        dynamic = artifacts - base_artifacts - expected_custom
        if not base_artifacts.issubset(artifacts) or any(
            not any(
                fact.startswith(
                    f"mainline-execution:{key}:{incoming_tasks[key].artifact_digest}:"
                )
                and fact.endswith(":completed")
                for key in new_keys[:completed_count]
            )
            for fact in dynamic
        ):
            raise ResearchOSValidationError(error)
        if len(dynamic) != completed_count or artifacts != (
            base_artifacts | expected_custom | dynamic
        ):
            raise ResearchOSValidationError(error)
        current_keys = {item.task_key for item in current.tasks}
        if current.artifact_digest != baseline.artifact_digest and not all(
            key in current_keys for key in new_keys
        ):
            raise ResearchOSValidationError(error)

    @staticmethod
    def _verify_m4_v2_global_routing_replay_compatibility_v1_import(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
        builder: ModuleType | None = None,
        pending_successor_registration: MainlineArtifactRegistration | None = None,
    ) -> None:
        """Verify the one approved replay-only additive successor and no other delta."""

        from dehps.config import ROOT_DIR

        builder = builder or _load_m4_v2_global_routing_replay_compatibility_v1_builder()
        error = "m4_v2_global_replay_compatibility_v1_output_changed"
        if control_plane_key != "m4-information-theory-mainline":
            raise ResearchOSValidationError(
                "m4_v2_global_replay_compatibility_v1_control_plane_changed"
            )
        tasks = {task.task_key: task for task in manifest.tasks}
        successor = tasks.get(builder.SUCCESSOR_TASK_KEY)
        if successor is None or len(tasks) != len(manifest.tasks):
            raise ResearchOSValidationError(
                "m4_v2_global_replay_compatibility_v1_task_identity_changed"
            )

        control = cursor.execute(
            """SELECT current_manifest_digest FROM research_os_control_planes
               WHERE control_plane_key = %s FOR UPDATE""",
            (control_plane_key,),
        ).fetchone()
        if control is None:
            raise ResearchOSValidationError(
                "m4_v2_global_replay_compatibility_v1_control_plane_missing"
            )
        baseline_row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (builder.INPUT_MANIFEST_DIGEST,),
        ).fetchone()
        if baseline_row is None:
            raise ResearchOSValidationError(
                "m4_v2_global_replay_compatibility_v1_baseline_missing"
            )
        current_digest = str(control["current_manifest_digest"])
        current_row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (current_digest,),
        ).fetchone()
        if current_row is None:
            raise ResearchOSValidationError(
                "m4_v2_global_replay_compatibility_v1_current_missing"
            )
        try:
            baseline = ControlPlaneManifest.from_dict(dict(baseline_row["manifest_json"]))
            current = ControlPlaneManifest.from_dict(dict(current_row["manifest_json"]))
            source_payload = json.loads(
                (ROOT_DIR / builder.SOURCE_PATH).read_text(encoding="utf-8")
            )
            source_digest = builder.validate_source_contract(
                source_payload, root_dir=ROOT_DIR
            )
            ready_payload, _ = builder.build_manifest(
                baseline.to_dict(include_digest=True),
                source_contract_digest=source_digest,
            )
            ready = ControlPlaneManifest.from_dict(ready_payload)
        except (
            KeyError,
            OSError,
            TypeError,
            ValueError,
            ResearchOSValidationError,
            builder.GlobalRoutingReplayCompatibilityV1Error,
        ) as exc:
            raise ResearchOSValidationError(
                "m4_v2_global_replay_compatibility_v1_source_or_baseline_changed"
            ) from exc
        if baseline.artifact_digest != builder.INPUT_MANIFEST_DIGEST:
            raise ResearchOSValidationError(
                "m4_v2_global_replay_compatibility_v1_baseline_changed"
            )
        baseline_snapshot = ResearchOSControlPlane().resolve(baseline)
        if (
            baseline_snapshot.snapshot_digest != builder.INPUT_SNAPSHOT_DIGEST
            or baseline_snapshot.ready_queue
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_replay_compatibility_v1_baseline_changed"
            )
        old = next((task for task in baseline.tasks if task.task_key == builder.OLD_TASK_KEY), None)
        if old is None or old.artifact_digest != builder.OLD_TASK_DIGEST:
            raise ResearchOSValidationError(
                "m4_v2_global_replay_compatibility_v1_old_task_changed"
            )

        successor_task = next(
            task for task in ready.tasks if task.task_key == builder.SUCCESSOR_TASK_KEY
        )
        if successor.artifact_digest != successor_task.artifact_digest:
            raise ResearchOSValidationError(
                "m4_v2_global_replay_compatibility_v1_task_identity_changed"
            )

        running = ControlPlaneManifest.from_dict(
            builder.transition_manifest(
                ready.to_dict(include_digest=True),
                status="running",
                classification="INTEGRATED",
            )
        )
        failed = ControlPlaneManifest.from_dict(
            builder.transition_manifest(
                ready.to_dict(include_digest=True),
                status="failed",
                classification="INTEGRATED",
            )
        )

        old_events = cursor.execute(
            """SELECT event_digest, execution_id, control_plane_key,
                      manifest_digest, task_digest, task_key, capability,
                      event_type, sequence, recorded_at, event_json
               FROM research_os_mainline_execution_events
               WHERE control_plane_key = %s AND task_key = %s
               ORDER BY sequence, event_digest""",
            (control_plane_key, builder.OLD_TASK_KEY),
        ).fetchall()
        if len(old_events) != 2:
            raise ResearchOSValidationError(
                "m4_v2_global_replay_compatibility_v1_old_events_changed"
            )
        observed_old_events = []
        for row in old_events:
            event, _ = _typed_v3_event(row)
            observed_old_events.append(
                (
                    event.artifact_digest,
                    event.execution_id,
                    event.manifest_digest,
                    event.task_digest,
                    event.task_key,
                    event.event_type,
                    event.sequence,
                )
            )
        if tuple(observed_old_events) != (
            (
                builder.OLD_STARTED_EVENT_DIGEST,
                builder.OLD_EXECUTION_ID,
                builder.OLD_EVENT_MANIFEST_DIGEST,
                builder.OLD_TASK_DIGEST,
                builder.OLD_TASK_KEY,
                "started",
                0,
            ),
            (
                builder.OLD_COMPLETED_EVENT_DIGEST,
                builder.OLD_EXECUTION_ID,
                builder.OLD_EVENT_MANIFEST_DIGEST,
                builder.OLD_TASK_DIGEST,
                builder.OLD_TASK_KEY,
                "completed",
                1,
            ),
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_replay_compatibility_v1_old_events_changed"
            )

        old_registration_rows = cursor.execute(
            """SELECT registration_digest, execution_id, control_plane_key,
                      task_digest, task_key, artifact_digest, artifact_type,
                      schema_version, artifact_path, parent_digests_json,
                      git_commit, registration_json
               FROM research_os_mainline_artifacts
               WHERE control_plane_key = %s AND task_key = %s
               ORDER BY artifact_type, artifact_digest, registration_digest""",
            (control_plane_key, builder.OLD_TASK_KEY),
        ).fetchall()
        if len(old_registration_rows) != 2:
            raise ResearchOSValidationError(
                "m4_v2_global_replay_compatibility_v1_old_registrations_changed"
            )
        expected_old_registrations = (
            (
                builder.OLD_ROUTE_REGISTRATION_DIGEST,
                builder.OLD_ROUTE_ARTIFACT_DIGEST,
                "m4_measurement_routing_decision",
                "dehps-m4-measurement-routing-decision.v1",
                builder.OLD_ROUTE_PATH,
                (),
            ),
            (
                builder.OLD_EXECUTION_REGISTRATION_DIGEST,
                builder.OLD_EXECUTION_ARTIFACT_DIGEST,
                "research_os_mainline_execution",
                "dehps-research-os-mainline-execution.v1",
                builder.OLD_EXECUTION_PATH,
                (
                    "11cb628f050f05465676fe083a6f9c183cbf855edfec8e194e98ad0450cdfd64",
                    builder.OLD_ROUTE_ARTIFACT_DIGEST,
                ),
            ),
        )
        observed_old_registrations = []
        for row in old_registration_rows:
            raw = dict(row["registration_json"])
            registration = MainlineArtifactRegistration(
                execution_id=str(raw["execution_id"]),
                control_plane_key=str(raw["control_plane_key"]),
                task_key=str(raw["task_key"]),
                task_digest=str(raw["task_digest"]),
                artifact_digest=str(raw["artifact_digest"]),
                artifact_type=str(raw["artifact_type"]),
                schema_version=str(raw["schema_version"]),
                artifact_path=str(raw["artifact_path"]),
                parent_digests=tuple(str(value) for value in raw["parent_digests"]),
                git_commit=str(raw["git_commit"]),
            )
            if (
                str(row["registration_digest"]) != registration.registration_digest
                or str(row["execution_id"]) != registration.execution_id
                or str(row["control_plane_key"]) != registration.control_plane_key
                or str(row["task_digest"]) != registration.task_digest
                or str(row["task_key"]) != registration.task_key
                or str(row["artifact_digest"]) != registration.artifact_digest
                or str(row["artifact_type"]) != registration.artifact_type
                or str(row["schema_version"]) != registration.schema_version
                or str(row["artifact_path"]) != registration.artifact_path
                or tuple(str(value) for value in row["parent_digests_json"])
                != registration.parent_digests
                or str(row["git_commit"]) != registration.git_commit
                or registration.execution_id != builder.OLD_EXECUTION_ID
                or registration.control_plane_key != control_plane_key
                or registration.task_key != builder.OLD_TASK_KEY
                or registration.task_digest != builder.OLD_TASK_DIGEST
                or registration.git_commit != builder.OLD_GIT_COMMIT
            ):
                raise ResearchOSValidationError(
                    "m4_v2_global_replay_compatibility_v1_old_registrations_changed"
                )
            observed_old_registrations.append(
                (
                    registration.registration_digest,
                    registration.artifact_digest,
                    registration.artifact_type,
                    registration.schema_version,
                    registration.artifact_path,
                    registration.parent_digests,
                )
            )
        if tuple(observed_old_registrations) != expected_old_registrations:
            raise ResearchOSValidationError(
                "m4_v2_global_replay_compatibility_v1_old_registrations_changed"
            )
        route_path = (ROOT_DIR / builder.OLD_ROUTE_PATH).resolve()
        root_dir = ROOT_DIR.resolve()
        if (
            not route_path.is_relative_to(root_dir)
            or not route_path.is_file()
            or route_path.stat().st_size != builder.OLD_ROUTE_RAW_LENGTH
            or hashlib.sha256(route_path.read_bytes()).hexdigest()
            != builder.OLD_ROUTE_RAW_SHA256
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_replay_compatibility_v1_old_route_bytes_changed"
            )

        runtime_rows = cursor.execute(
            """SELECT event_digest, execution_id, control_plane_key,
                      manifest_digest, task_digest, task_key, capability,
                      event_type, sequence, recorded_at, event_json
               FROM research_os_mainline_execution_events
               WHERE control_plane_key = %s AND task_key = %s
               ORDER BY sequence, event_digest""",
            (control_plane_key, builder.SUCCESSOR_TASK_KEY),
        ).fetchall()
        successor_registration_rows = cursor.execute(
            """SELECT registration_digest, execution_id, control_plane_key,
                      task_digest, task_key, artifact_digest, artifact_type,
                      schema_version, artifact_path, parent_digests_json,
                      git_commit, registration_json
               FROM research_os_mainline_artifacts
               WHERE control_plane_key = %s AND task_key = %s""",
            (control_plane_key, builder.SUCCESSOR_TASK_KEY),
        ).fetchall()

        def stage(value: ControlPlaneManifest) -> str | None:
            fixed = {
                baseline.artifact_digest: "COMPLETED_V3",
                ready.artifact_digest: "READY",
                running.artifact_digest: "RUNNING",
                failed.artifact_digest: "FAILED",
            }.get(value.artifact_digest)
            if fixed:
                return fixed
            target = next(
                (task for task in value.tasks if task.task_key == builder.SUCCESSOR_TASK_KEY),
                None,
            )
            if target is not None:
                state = value.task_state_by_digest[target.artifact_digest]
                if state.declared_status.value == "completed":
                    return "COMPLETED"
            return None

        incoming_stage = stage(manifest)
        current_stage = stage(current)
        legal = {
            "COMPLETED_V3": {"READY"},
            "READY": {"READY", "RUNNING"},
            "RUNNING": {"RUNNING", "COMPLETED", "FAILED"},
            "COMPLETED": {"COMPLETED"},
            "FAILED": {"FAILED"},
        }
        if current_stage is None or incoming_stage not in legal[current_stage]:
            raise ResearchOSValidationError(error)
        if incoming_stage == "READY":
            if runtime_rows or successor_registration_rows or pending_successor_registration:
                raise ResearchOSValidationError(error)
            return

        def typed_successor_event(row: Any) -> tuple[MainlineExecutionEvent, dict[str, Any]]:
            event, payload = _typed_v3_event(row)
            if (
                event.control_plane_key != control_plane_key
                or event.manifest_digest != running.artifact_digest
                or event.task_key != builder.SUCCESSOR_TASK_KEY
                or event.task_digest != successor_task.artifact_digest
                or event.capability != successor_task.requested_capability
            ):
                raise ResearchOSValidationError(error)
            return event, payload

        if incoming_stage == "RUNNING":
            if (
                successor_registration_rows
                or pending_successor_registration
                or len(runtime_rows) not in ({0} if current_stage == "READY" else {0, 1})
            ):
                raise ResearchOSValidationError(error)
            if runtime_rows:
                started, started_payload = typed_successor_event(runtime_rows[0])
                if (
                    started.event_type != "started"
                    or started.sequence != 0
                    or set(started_payload) != {"input_artifact_digests", "git_commit"}
                    or started_payload["input_artifact_digests"]
                    != list(successor_task.input_artifact_digests)
                ):
                    raise ResearchOSValidationError(error)
            return
        if len(runtime_rows) != 2:
            raise ResearchOSValidationError(error)
        started, started_payload = typed_successor_event(runtime_rows[0])
        terminal, terminal_payload = typed_successor_event(runtime_rows[1])
        if (
            started.event_type != "started"
            or started.sequence != 0
            or set(started_payload) != {"input_artifact_digests", "git_commit"}
            or started_payload["input_artifact_digests"]
            != list(successor_task.input_artifact_digests)
            or terminal.execution_id != started.execution_id
            or terminal.sequence != 1
            or str(terminal_payload.get("git_commit"))
            != str(started_payload["git_commit"])
        ):
            raise ResearchOSValidationError(error)
        if incoming_stage == "FAILED":
            if (
                terminal.event_type != "failed"
                or set(terminal_payload) != {"error", "git_commit"}
                or not str(terminal_payload["error"])
                or successor_registration_rows
                or pending_successor_registration
                or manifest.to_dict(include_digest=True)
                != failed.to_dict(include_digest=True)
            ):
                raise ResearchOSValidationError(error)
            return
        expected_terminal = {
            "git_commit",
            "registered_replay_status",
            "replay_task_key",
            "replay_execution_id",
            "route_artifact_digest",
            "route_registration_digest",
            "global_route",
            "durable_state_changed",
            "workload_rerun",
            "branch_workloads_rerun",
            "global_router_workload_rerun",
            "predictive_p3_folds",
            "p4_started",
            "promotion_triggered",
        }
        if (
            terminal.event_type != "completed"
            or set(terminal_payload) != expected_terminal
            or terminal_payload["registered_replay_status"]
            != "REGISTERED_REPLAY_VERIFIED"
            or terminal_payload["replay_task_key"] != builder.OLD_TASK_KEY
            or terminal_payload["replay_execution_id"] != builder.OLD_EXECUTION_ID
            or terminal_payload["route_artifact_digest"]
            != builder.OLD_ROUTE_ARTIFACT_DIGEST
            or terminal_payload["route_registration_digest"]
            != builder.OLD_ROUTE_REGISTRATION_DIGEST
            or terminal_payload["global_route"] != builder.OLD_ROUTE
            or terminal_payload["durable_state_changed"] is not False
            or terminal_payload["workload_rerun"] is not False
            or terminal_payload["branch_workloads_rerun"] is not False
            or terminal_payload["global_router_workload_rerun"] is not False
            or terminal_payload["predictive_p3_folds"] != 0
            or terminal_payload["p4_started"] is not False
            or terminal_payload["promotion_triggered"] is not False
        ):
            raise ResearchOSValidationError(error)

        def typed_successor_registration(row: Any) -> MainlineArtifactRegistration:
            try:
                raw = dict(row["registration_json"])
                registration = MainlineArtifactRegistration(
                    execution_id=str(raw["execution_id"]),
                    control_plane_key=str(raw["control_plane_key"]),
                    task_key=str(raw["task_key"]),
                    task_digest=str(raw["task_digest"]),
                    artifact_digest=str(raw["artifact_digest"]),
                    artifact_type=str(raw["artifact_type"]),
                    schema_version=str(raw["schema_version"]),
                    artifact_path=str(raw["artifact_path"]),
                    parent_digests=tuple(str(value) for value in raw["parent_digests"]),
                    git_commit=str(raw["git_commit"]),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ResearchOSValidationError(error) from exc
            if (
                str(row["registration_digest"]) != registration.registration_digest
                or str(row["execution_id"]) != registration.execution_id
                or str(row["control_plane_key"]) != registration.control_plane_key
                or str(row["task_digest"]) != registration.task_digest
                or str(row["task_key"]) != registration.task_key
                or str(row["artifact_digest"]) != registration.artifact_digest
                or str(row["artifact_type"]) != registration.artifact_type
                or str(row["schema_version"]) != registration.schema_version
                or str(row["artifact_path"]) != registration.artifact_path
                or tuple(str(value) for value in row["parent_digests_json"])
                != registration.parent_digests
                or str(row["git_commit"]) != registration.git_commit
            ):
                raise ResearchOSValidationError(error)
            return registration

        if pending_successor_registration is not None:
            if successor_registration_rows:
                raise ResearchOSValidationError(error)
            successor_registration = pending_successor_registration
        else:
            if len(successor_registration_rows) != 1:
                raise ResearchOSValidationError(error)
            successor_registration = typed_successor_registration(
                successor_registration_rows[0]
            )
        if (
            successor_registration.registration_digest
            != _M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_REGISTRATION_DIGEST
            or successor_registration.execution_id != started.execution_id
            or successor_registration.control_plane_key != control_plane_key
            or successor_registration.task_key != builder.SUCCESSOR_TASK_KEY
            or successor_registration.task_digest != successor_task.artifact_digest
            or successor_registration.artifact_digest
            != builder.OLD_ROUTE_ARTIFACT_DIGEST
            or successor_registration.artifact_type
            != "m4_measurement_routing_decision"
            or successor_registration.schema_version
            != "dehps-m4-measurement-routing-decision.v1"
            or successor_registration.artifact_path != builder.OLD_ROUTE_PATH
            or successor_registration.parent_digests != ()
            or successor_registration.git_commit != str(started_payload["git_commit"])
        ):
            raise ResearchOSValidationError(error)
        expected_completed = ControlPlaneManifest.from_dict(
            builder.transition_manifest(
                ready.to_dict(include_digest=True),
                status="completed",
                classification="COMPLETE",
                execution_id=started.execution_id,
            )
        )
        if manifest.to_dict(include_digest=True) != expected_completed.to_dict(
            include_digest=True
        ):
            raise ResearchOSValidationError(error)

    @staticmethod
    def _verify_m4_v2_global_routing_replay_compatibility_v1_registration(
        cursor,
        *,
        registration: MainlineArtifactRegistration,
    ) -> None:
        """Authorize only the reviewed registration for the frozen replay successor."""

        builder = _load_m4_v2_global_routing_replay_compatibility_v1_builder()
        error = "m4_v2_global_replay_compatibility_v1_registration_changed"
        if (
            registration.task_key != builder.SUCCESSOR_TASK_KEY
            or registration.registration_digest
            != _M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_REGISTRATION_DIGEST
        ):
            raise ResearchOSValidationError(error)
        control = cursor.execute(
            """SELECT current_manifest_digest FROM research_os_control_planes
               WHERE control_plane_key = %s FOR UPDATE""",
            (registration.control_plane_key,),
        ).fetchone()
        if control is None:
            raise ResearchOSValidationError(error)
        current_row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (str(control["current_manifest_digest"]),),
        ).fetchone()
        if current_row is None:
            raise ResearchOSValidationError(error)
        try:
            current = ControlPlaneManifest.from_dict(dict(current_row["manifest_json"]))
            completed = ControlPlaneManifest.from_dict(
                builder.transition_manifest(
                    current.to_dict(include_digest=True),
                    status="completed",
                    classification="COMPLETE",
                    execution_id=registration.execution_id,
                )
            )
        except (
            KeyError,
            TypeError,
            ValueError,
            ResearchOSValidationError,
            builder.GlobalRoutingReplayCompatibilityV1Error,
        ) as exc:
            raise ResearchOSValidationError(error) from exc
        PostgresResearchOSRepository._verify_m4_v2_global_routing_replay_compatibility_v1_import(
            cursor,
            control_plane_key=registration.control_plane_key,
            manifest=completed,
            builder=builder,
            pending_successor_registration=registration,
        )
        PostgresResearchOSRepository._verify_m4_v2_global_routing_replay_compatibility_v1_registration_governance(
            cursor
        )

    @staticmethod
    def _verify_m4_v2_global_routing_replay_compatibility_v1_registration_governance(
        cursor,
    ) -> None:
        """Bind the registration to the one reviewed Research and Engineering chain."""

        error = "m4_v2_global_replay_compatibility_v1_registration_authority_changed"
        request_ids = [
            _M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_RESEARCH_REQUEST_ID,
            _M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_ENGINEERING_REQUEST_ID,
        ]
        requests = cursor.execute(
            """SELECT id, request_key, request_type, requested_by_role, requested_by,
                      parent_request_id, status, risk_level, requires_review,
                      metadata_json->>'payload_sha256' AS payload_sha256
               FROM agent_requests WHERE id = ANY(%s) ORDER BY id""",
            (request_ids,),
        ).fetchall()
        executions = cursor.execute(
            """SELECT id, request_id, executor_role, executor_id, execution_type,
                      status, environment, run_id, artifact_paths_json AS artifact_paths
               FROM agent_request_executions WHERE request_id = ANY(%s)
               ORDER BY request_id, id""",
            (request_ids,),
        ).fetchall()
        decisions = cursor.execute(
            """SELECT id, request_id, previous_status, new_status, decision_code,
                      summary, reason_json AS reason, decided_by_role, decided_by
               FROM agent_request_decisions WHERE request_id = ANY(%s)
               ORDER BY request_id, id""",
            (request_ids,),
        ).fetchall()
        observed_requests = [
            (
                int(row["id"]),
                str(row["request_key"]),
                str(row["request_type"]),
                str(row["requested_by_role"]),
                str(row["requested_by"]),
                None if row["parent_request_id"] is None else int(row["parent_request_id"]),
                str(row["status"]),
                str(row["risk_level"]),
                bool(row["requires_review"]),
                str(row["payload_sha256"]),
            )
            for row in requests
        ]
        expected_requests = [
            (
                621,
                "research-m4-v2-global-routing-v3-exact-successor-registration-v1",
                "research_scheduler_request",
                "research",
                "research:exact-successor-registration-v1",
                None,
                "completed",
                "low",
                True,
                _M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_RESEARCH_PAYLOAD_SHA256,
            ),
            (
                622,
                "engineering-m4-v2-global-routing-v3-exact-successor-registration-v1",
                "engineering_implementation",
                "engineering",
                "engineering:exact-successor-registration-v1",
                621,
                "completed",
                "medium",
                True,
                _M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_ENGINEERING_PAYLOAD_SHA256,
            ),
        ]
        observed_executions = [
            (
                int(row["id"]),
                int(row["request_id"]),
                str(row["executor_role"]),
                str(row["executor_id"]),
                str(row["execution_type"]),
                str(row["status"]),
                str(row["environment"]),
                row["run_id"],
                list(row["artifact_paths"]),
            )
            for row in executions
        ]
        expected_executions = [
            (
                507,
                621,
                "research",
                "research:exact-successor-registration-v1",
                "schedule_research",
                "completed",
                "isolated",
                None,
                [],
            ),
            (
                508,
                622,
                "engineering",
                "engineering:exact-successor-registration-v1",
                "modify_code",
                "completed",
                "development",
                "m4-v2-global-routing-v3-exact-successor-registration-v1",
                [],
            ),
        ]
        decisions_by_request: dict[int, list[dict[str, Any]]] = {}
        for row in decisions:
            decisions_by_request.setdefault(int(row["request_id"]), []).append(dict(row))
        research_decisions = decisions_by_request.get(621, [])
        engineering_decisions = decisions_by_request.get(622, [])
        research_approval = next(
            (row for row in research_decisions if int(row["id"]) == 2611), None
        )
        engineering_approval = next(
            (row for row in engineering_decisions if int(row["id"]) == 2616), None
        )
        engineering_terminal = engineering_decisions[-1] if engineering_decisions else None
        if (
            observed_requests != expected_requests
            or observed_executions != expected_executions
            or [int(row["id"]) for row in research_decisions]
            != [2609, 2610, 2611, 2612, 2613]
            or [int(row["id"]) for row in engineering_decisions[:-1]]
            != [2614, 2615, 2616, 2617]
            or len(engineering_decisions) != 5
            or research_approval is None
            or (
                research_approval["previous_status"],
                research_approval["new_status"],
                research_approval["decision_code"],
                research_approval["decided_by_role"],
                research_approval["decided_by"],
            )
            != (
                "under_review",
                "approved",
                "request_approved",
                "reviewer",
                "reviewer:exact-successor-registration-v1",
            )
            or dict(research_approval["reason"]).get("outcome")
            != "APPROVE_EXACT_SUCCESSOR_REGISTRATION"
            or engineering_approval is None
            or (
                engineering_approval["previous_status"],
                engineering_approval["new_status"],
                engineering_approval["decision_code"],
                engineering_approval["decided_by_role"],
                engineering_approval["decided_by"],
            )
            != (
                "under_review",
                "approved",
                "request_approved",
                "reviewer",
                "reviewer:engineering622-successor-registration",
            )
            or dict(engineering_approval["reason"]).get("outcome")
            != "APPROVE_EXACT_SUCCESSOR_REGISTRATION"
            or engineering_terminal is None
            or {
                "previous_status": engineering_terminal["previous_status"],
                "new_status": engineering_terminal["new_status"],
                "decision_code": engineering_terminal["decision_code"],
                "summary": engineering_terminal["summary"],
                "reason": dict(engineering_terminal["reason"]),
                "decided_by_role": engineering_terminal["decided_by_role"],
                "decided_by": engineering_terminal["decided_by"],
            }
            != {
                "previous_status": "executing",
                "new_status": "completed",
                "decision_code": "execution_completed",
                "summary": "request execution completed",
                "reason": {"execution_id": 508, "has_error": False},
                "decided_by_role": "engineering",
                "decided_by": "engineering:exact-successor-registration-v1",
            }
        ):
            raise ResearchOSValidationError(error)

    @staticmethod
    def _verify_m4_v2_failed_global_routing_recovery_v2_import(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
    ) -> None:
        """Verify the exact failed recovery-v1 lineage before the first write."""

        from dehps.config import ROOT_DIR

        builder = _load_m4_v2_global_routing_recovery_v2_builder()
        GLOBAL_SOURCE_PATH = builder.GLOBAL_SOURCE_PATH
        INPUT_MANIFEST_DIGEST = builder.INPUT_MANIFEST_DIGEST
        OLD_EVENT_MANIFEST_DIGEST = builder.OLD_EVENT_MANIFEST_DIGEST
        OLD_EXECUTION_ID = builder.OLD_EXECUTION_ID
        OLD_FAILED_EVENT_DIGEST = builder.OLD_FAILED_EVENT_DIGEST
        OLD_STARTED_EVENT_DIGEST = builder.OLD_STARTED_EVENT_DIGEST
        OLD_TASK_DIGEST = builder.OLD_TASK_DIGEST
        OLD_TASK_KEY = builder.OLD_TASK_KEY
        P3_REVISIONS = builder.P3_REVISIONS
        RECOVERY_TASK_KEY = builder.RECOVERY_TASK_KEY
        GlobalRoutingRecoveryV2Error = builder.GlobalRoutingRecoveryV2Error
        build_manifest = builder.build_manifest
        validate_global_source_contract = builder.validate_global_source_contract
        tasks = {task.task_key: task for task in manifest.tasks}
        recovery = tasks.get(RECOVERY_TASK_KEY)
        incoming_input_baseline = manifest.artifact_digest == INPUT_MANIFEST_DIGEST
        if recovery is None and not incoming_input_baseline:
            return
        if control_plane_key != "m4-information-theory-mainline":
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_control_plane_changed"
            )
        if (
            (
                incoming_input_baseline
                and (
                    recovery is not None
                    or OLD_TASK_KEY not in tasks
                    or tasks[OLD_TASK_KEY].artifact_digest != OLD_TASK_DIGEST
                )
            )
            or (
                not incoming_input_baseline
                and (
                    recovery is None
                    or OLD_TASK_KEY in tasks
                    or len(recovery.input_artifact_digests) != 1
                )
            )
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_task_identity_changed"
            )

        control = cursor.execute(
            """SELECT current_manifest_digest FROM research_os_control_planes
               WHERE control_plane_key = %s FOR UPDATE""",
            (control_plane_key,),
        ).fetchone()
        if control is None:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_control_plane_missing"
            )
        current_digest = str(control["current_manifest_digest"])
        baseline_row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (INPUT_MANIFEST_DIGEST,),
        ).fetchone()
        if baseline_row is None:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_input_manifest_missing"
            )
        try:
            baseline = ControlPlaneManifest.from_dict(
                dict(baseline_row["manifest_json"])
            )
        except (KeyError, TypeError, ValueError, ResearchOSValidationError) as exc:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_input_manifest_changed"
            ) from exc
        baseline_old = tuple(
            task for task in baseline.tasks if task.task_key == OLD_TASK_KEY
        )
        if (
            baseline.artifact_digest != INPUT_MANIFEST_DIGEST
            or len(baseline_old) != 1
            or baseline_old[0].artifact_digest != OLD_TASK_DIGEST
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_input_manifest_changed"
            )
        definition = cursor.execute(
            """SELECT task_digest, task_key, definition_json
               FROM research_os_task_definitions WHERE task_digest = %s""",
            (OLD_TASK_DIGEST,),
        ).fetchone()
        if (
            definition is None
            or str(definition["task_digest"]) != OLD_TASK_DIGEST
            or str(definition["task_key"]) != OLD_TASK_KEY
            or dict(definition["definition_json"]) != baseline_old[0].to_dict()
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_old_definition_changed"
            )
        stored = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (current_digest,),
        ).fetchone()
        if stored is None:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_manifest_missing"
            )
        current = ControlPlaneManifest.from_dict(dict(stored["manifest_json"]))
        source_path = ROOT_DIR / GLOBAL_SOURCE_PATH
        try:
            source_payload = json.loads(source_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError) as exc:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_source_changed"
            ) from exc
        try:
            source_digest = validate_global_source_contract(
                source_payload, root_dir=ROOT_DIR
            )
        except GlobalRoutingRecoveryV2Error:
            try:
                v3_builder = _load_m4_v2_global_routing_recovery_v3_builder()
            except ResearchOSValidationError as exc:
                raise ResearchOSValidationError(
                    "m4_v2_global_recovery_v2_source_changed"
                ) from exc
            try:
                v3_builder.validate_global_source_contract(
                    source_payload, root_dir=ROOT_DIR
                )
                source_digest = v3_builder.OLD_SOURCE_DIGEST
            except (
                OSError,
                ValueError,
                TypeError,
                v3_builder.GlobalRoutingRecoveryV3Error,
            ) as exc:
                raise ResearchOSValidationError(
                    "m4_v2_global_recovery_v2_source_changed"
                ) from exc
        if (
            recovery is not None
            and recovery.input_artifact_digests != (source_digest,)
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_source_changed"
            )
        expected, _ = build_manifest(
            baseline.to_dict(include_digest=True),
            global_source_contract_digest=source_digest,
        )
        ready = ControlPlaneManifest.from_dict(expected)

        def transition(
            source_manifest: ControlPlaneManifest,
            *,
            status: str,
            classification: str,
            facts: tuple[str, ...] = (),
        ) -> ControlPlaneManifest:
            payload = source_manifest.to_dict(include_digest=False)
            matches = [
                item
                for item in payload["tasks"]
                if item["task_key"] == RECOVERY_TASK_KEY
            ]
            if len(matches) != 1:
                raise ResearchOSValidationError(
                    "m4_v2_global_recovery_v2_output_changed"
                )
            matches[0]["status"] = status
            matches[0]["completion_classification"] = classification
            if facts:
                payload["facts"]["artifacts"] = sorted(
                    {*payload["facts"]["artifacts"], *facts}
                )
            return ControlPlaneManifest.from_dict(payload)

        running = transition(
            ready,
            status="running",
            classification="INTEGRATED",
        )
        failed = transition(
            running,
            status="failed",
            classification="INTEGRATED",
        )
        if (
            ready.artifact_digest
            != "1cc4ebf7a458ecaf6eba3e3a8079012318a2bf7354cb4b3f9770dcfa9ddbe84d"
            or running.artifact_digest
            != "8d9ed3811969cb80979c51e2c27f451ca2c4b127d59a2c1a9e105127b68bb084"
            or failed.artifact_digest
            != "b50a4c07ee75cd9e87842b8ad62846b6c37af23a17a9fc71e1e3610ce2e8c319"
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_output_changed"
            )

        frozen = {
            "INPUT_BASELINE": baseline,
            "READY": ready,
            "RUNNING": running,
            "FAILED": failed,
        }

        def stage(value: ControlPlaneManifest) -> str | None:
            serialized = value.to_dict(include_digest=True)
            for name, candidate in frozen.items():
                if serialized == candidate.to_dict(include_digest=True):
                    return name
            candidate = next(
                (
                    item
                    for item in value.tasks
                    if item.task_key == RECOVERY_TASK_KEY
                ),
                None,
            )
            if candidate is None:
                return None
            state = value.task_state_by_digest[candidate.artifact_digest]
            if (
                state.declared_status.value == "completed"
                and state.completion_classification is not None
                and state.completion_classification.value == "COMPLETE"
            ):
                return "COMPLETED"
            return None

        incoming_stage = stage(manifest)
        if incoming_stage is None:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_output_changed"
            )
        current_stage = stage(current)
        if current_stage is None or current.artifact_digest != current_digest:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_current_manifest_changed"
            )
        allowed = {
            ("INPUT_BASELINE", "INPUT_BASELINE"),
            ("INPUT_BASELINE", "READY"),
            ("READY", "READY"),
            ("READY", "RUNNING"),
            ("RUNNING", "RUNNING"),
            ("RUNNING", "COMPLETED"),
            ("RUNNING", "FAILED"),
            ("COMPLETED", "COMPLETED"),
            ("FAILED", "FAILED"),
        }
        if (current_stage, incoming_stage) not in allowed:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_output_changed"
            )
        if (
            current_stage in {"COMPLETED", "FAILED"}
            and current.to_dict(include_digest=True)
            != manifest.to_dict(include_digest=True)
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_current_manifest_changed"
            )

        state = cursor.execute(
            """SELECT ts.declared_status, ts.completion_classification,
                      ts.superseded_by_task_digest
               FROM research_os_task_states ts
               WHERE ts.control_plane_key = %s AND ts.task_digest = %s""",
            (control_plane_key, OLD_TASK_DIGEST),
        ).fetchone()
        if (
            state is None
            or str(state["declared_status"]) != "failed"
            or str(state["completion_classification"]) != "INTEGRATED"
            or state["superseded_by_task_digest"] is not None
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_old_state_changed"
            )
        rows = cursor.execute(
            """SELECT event_digest, execution_id, manifest_digest, task_digest,
                      task_key, event_type, sequence
               FROM research_os_mainline_execution_events
               WHERE control_plane_key = %s AND task_key = %s AND execution_id = %s
               ORDER BY sequence, event_digest""",
            (control_plane_key, OLD_TASK_KEY, OLD_EXECUTION_ID),
        ).fetchall()
        expected_rows = (
            (OLD_STARTED_EVENT_DIGEST, "started", 0),
            (OLD_FAILED_EVENT_DIGEST, "failed", 1),
        )
        if len(rows) != 2 or any(
            str(row["event_digest"]) != digest
            or str(row["execution_id"]) != OLD_EXECUTION_ID
            or str(row["manifest_digest"]) != OLD_EVENT_MANIFEST_DIGEST
            or str(row["task_digest"]) != OLD_TASK_DIGEST
            or str(row["task_key"]) != OLD_TASK_KEY
            or str(row["event_type"]) != event_type
            or int(row["sequence"]) != sequence
            for row, (digest, event_type, sequence) in zip(
                rows, expected_rows, strict=True
            )
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_event_lineage_changed"
            )
        successor_by_key = {task.task_key: task for task in manifest.tasks}
        if any(
            key not in successor_by_key
            or successor_by_key[key].artifact_digest
            != (before if incoming_stage == "INPUT_BASELINE" else after)
            for key, before, after in P3_REVISIONS
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_p3_revisions_changed"
            )

        runtime_rows = cursor.execute(
            """SELECT event_digest, execution_id, control_plane_key,
                      manifest_digest, task_digest, task_key, capability,
                      event_type, sequence, recorded_at, event_json
               FROM research_os_mainline_execution_events
               WHERE control_plane_key = %s AND task_key = %s
               ORDER BY sequence, event_digest""",
            (control_plane_key, RECOVERY_TASK_KEY),
        ).fetchall()

        def typed_event(row: Any) -> tuple[MainlineExecutionEvent, dict[str, Any]]:
            try:
                raw = dict(row["event_json"])
                if set(raw) != {
                    "execution_id",
                    "control_plane_key",
                    "manifest_digest",
                    "task_key",
                    "task_digest",
                    "capability",
                    "event_type",
                    "sequence",
                    "recorded_at",
                    "payload",
                }:
                    raise ValueError("event fields")
                payload_items = raw["payload"]
                if (
                    not isinstance(payload_items, list)
                    or any(
                        not isinstance(item, list) or len(item) != 2
                        for item in payload_items
                    )
                ):
                    raise ValueError("event payload")
                event = MainlineExecutionEvent(
                    execution_id=str(raw["execution_id"]),
                    control_plane_key=str(raw["control_plane_key"]),
                    manifest_digest=str(raw["manifest_digest"]),
                    task_key=str(raw["task_key"]),
                    task_digest=str(raw["task_digest"]),
                    capability=str(raw["capability"]),
                    event_type=str(raw["event_type"]),
                    sequence=int(raw["sequence"]),
                    recorded_at=str(raw["recorded_at"]),
                    payload=tuple((str(item[0]), item[1]) for item in payload_items),
                )
                payload = dict(event.payload)
                if len(payload) != len(event.payload):
                    raise ValueError("duplicate payload field")
                column_values = {
                    "execution_id": event.execution_id,
                    "control_plane_key": event.control_plane_key,
                    "manifest_digest": event.manifest_digest,
                    "task_digest": event.task_digest,
                    "task_key": event.task_key,
                    "capability": event.capability,
                    "event_type": event.event_type,
                    "sequence": event.sequence,
                }
                if (
                    str(row["event_digest"]) != event.artifact_digest
                    or any(
                        str(row[name]) != str(value)
                        for name, value in column_values.items()
                    )
                    or _m4_v2_utc_instant(row["recorded_at"])
                    != _m4_v2_utc_instant(event.recorded_at)
                ):
                    raise ValueError("event columns")
                return event, payload
            except (KeyError, TypeError, ValueError) as exc:
                raise ResearchOSValidationError(
                    "m4_v2_global_recovery_v2_output_changed"
                ) from exc

        events = tuple(typed_event(row) for row in runtime_rows)
        recovery_task = next(
            (
                item
                for item in manifest.tasks
                if item.task_key == RECOVERY_TASK_KEY
            ),
            next(
                (
                    item
                    for item in ready.tasks
                    if item.task_key == RECOVERY_TASK_KEY
                ),
                None,
            ),
        )
        if recovery_task is None:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_task_identity_changed"
            )
        metric = json.loads(recovery_task.metric_contract)
        capability = str(recovery_task.requested_capability or "")
        source_inputs = list(recovery_task.input_artifact_digests)

        def valid_digest(value: Any, *, length: int = 64) -> bool:
            text = str(value or "")
            return (
                len(text) == length
                and text == text.lower()
                and all(character in "0123456789abcdef" for character in text)
            )

        def validate_started(
            item: tuple[MainlineExecutionEvent, dict[str, Any]],
        ) -> tuple[str, str]:
            event, payload = item
            if (
                event.control_plane_key != control_plane_key
                or event.manifest_digest != running.artifact_digest
                or event.task_key != RECOVERY_TASK_KEY
                or event.task_digest != recovery_task.artifact_digest
                or event.capability != capability
                or event.event_type != "started"
                or event.sequence != 0
                or not event.recorded_at
                or set(payload) != {"input_artifact_digests", "git_commit"}
                or payload["input_artifact_digests"] != source_inputs
                or not valid_digest(payload["git_commit"], length=40)
            ):
                raise ResearchOSValidationError(
                    "m4_v2_global_recovery_v2_output_changed"
                )
            git_commit = str(payload["git_commit"])
            expected_execution = stable_hash(
                {
                    "schema": "dehps-research-os-mainline-execution.v1",
                    "control_plane_key": control_plane_key,
                    "task_digest": recovery_task.artifact_digest,
                    "capability": capability,
                    "input_artifact_digests": recovery_task.input_artifact_digests,
                    "git_commit": git_commit,
                }
            )
            if event.execution_id != expected_execution:
                raise ResearchOSValidationError(
                    "m4_v2_global_recovery_v2_output_changed"
                )
            return event.execution_id, git_commit

        if incoming_stage in {"INPUT_BASELINE", "READY"}:
            if events:
                raise ResearchOSValidationError(
                    "m4_v2_global_recovery_v2_output_changed"
                )
            return
        if incoming_stage == "RUNNING":
            allowed_event_counts = (
                {0}
                if current_stage == "READY"
                else {0, 1}
            )
            if len(events) not in allowed_event_counts:
                raise ResearchOSValidationError(
                    "m4_v2_global_recovery_v2_output_changed"
                )
            if events:
                validate_started(events[0])
            return
        if len(events) != 2:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_output_changed"
            )
        execution_id, git_commit = validate_started(events[0])
        terminal_event, terminal_payload = events[1]
        if (
            terminal_event.execution_id != execution_id
            or terminal_event.control_plane_key != control_plane_key
            or terminal_event.manifest_digest != running.artifact_digest
            or terminal_event.task_key != RECOVERY_TASK_KEY
            or terminal_event.task_digest != recovery_task.artifact_digest
            or terminal_event.capability != capability
            or terminal_event.sequence != 1
            or not terminal_event.recorded_at
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_output_changed"
            )

        registration_rows = cursor.execute(
            """SELECT registration_digest, execution_id, control_plane_key,
                      task_digest, task_key, artifact_digest, artifact_type,
                      schema_version, artifact_path, parent_digests_json,
                      git_commit, registration_json
               FROM research_os_mainline_artifacts
               WHERE control_plane_key = %s AND task_key = %s
                 AND execution_id = %s
               ORDER BY artifact_path, registration_digest""",
            (control_plane_key, RECOVERY_TASK_KEY, execution_id),
        ).fetchall()

        if incoming_stage == "FAILED":
            if (
                terminal_event.event_type != "failed"
                or set(terminal_payload) != {"error", "git_commit"}
                or not str(terminal_payload["error"])
                or str(terminal_payload["git_commit"]) != git_commit
                or registration_rows
                or manifest.facts != running.facts
            ):
                raise ResearchOSValidationError(
                    "m4_v2_global_recovery_v2_output_changed"
                )
            return

        if terminal_event.event_type != "completed":
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_output_changed"
            )
        expected_completed_fields = {
            "execution_artifact_digest",
            "execution_artifact_path",
            "actual_fold_count",
            "registered_artifact_count",
            "git_commit",
            "completion_facts",
            "additional_completed_task_keys",
            "publication_batch_digest",
            "workload_rerun",
            "source_contract_digest",
            "source_set_digest",
            "route_decision_artifact_digest",
            "route",
            "downstream_consumer",
            "decision_replay_coverage",
            "historical_database_reads",
            "scientific_computation",
            "replay_status",
        }
        routes = dict(metric["route_facts"])
        route = str(terminal_payload.get("route") or "")
        route_fact = routes.get(route)
        completion_fact = str(metric["completion_fact"])
        completion_facts = terminal_payload.get("completion_facts")
        execution_artifact_digest = str(
            terminal_payload.get("execution_artifact_digest") or ""
        )
        route_digest = str(
            terminal_payload.get("route_decision_artifact_digest") or ""
        )
        expected_execution_path = (
            f"runtime/research-os/mainline/tasks/{RECOVERY_TASK_KEY}/"
            f"{execution_id}/execution.json"
        )
        expected_route_path = str(metric["route_artifact_path_template"]).format(
            execution_id=execution_id,
            artifact_digest=route_digest,
        )
        if (
            set(terminal_payload) != expected_completed_fields
            or route_fact is None
            or completion_facts != [route_fact, completion_fact]
            or terminal_payload["additional_completed_task_keys"] != []
            or int(terminal_payload["actual_fold_count"]) != 0
            or int(terminal_payload["registered_artifact_count"]) != 2
            or terminal_payload["workload_rerun"] is not False
            or str(terminal_payload["git_commit"]) != git_commit
            or str(terminal_payload["source_contract_digest"]) != source_digest
            or str(terminal_payload["source_set_digest"])
            != "51416beac1b615c6b5b91786f40f105b45ec7503285126649aa4334715b3a00c"
            or str(terminal_payload["downstream_consumer"])
            != json.loads(recovery_task.metric_contract)["mainline_integration"][
                "downstream_consumer"
            ]
            or terminal_payload["decision_replay_coverage"] != "COMPLETE"
            or int(terminal_payload["historical_database_reads"]) != 0
            or int(terminal_payload["scientific_computation"]) != 0
            or terminal_payload["replay_status"] != "REGISTERED_REPLAY_PENDING"
            or not valid_digest(execution_artifact_digest)
            or not valid_digest(route_digest)
            or not valid_digest(terminal_payload["publication_batch_digest"])
            or str(terminal_payload["execution_artifact_path"])
            != expected_execution_path
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_output_changed"
            )

        mainline_fact = (
            f"mainline-execution:{RECOVERY_TASK_KEY}:"
            f"{recovery_task.artifact_digest}:{execution_id}:completed"
        )
        expected_completed = transition(
            running,
            status="completed",
            classification="COMPLETE",
            facts=(mainline_fact, route_fact, completion_fact),
        )
        if manifest.to_dict(include_digest=True) != expected_completed.to_dict(
            include_digest=True
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_output_changed"
            )

        registrations: list[MainlineArtifactRegistration] = []
        try:
            for row in registration_rows:
                raw = dict(row["registration_json"])
                if set(raw) != {
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
                }:
                    raise ValueError("registration fields")
                registration = MainlineArtifactRegistration(
                    execution_id=str(raw["execution_id"]),
                    control_plane_key=str(raw["control_plane_key"]),
                    task_key=str(raw["task_key"]),
                    task_digest=str(raw["task_digest"]),
                    artifact_digest=str(raw["artifact_digest"]),
                    artifact_type=str(raw["artifact_type"]),
                    schema_version=str(raw["schema_version"]),
                    artifact_path=str(raw["artifact_path"]),
                    parent_digests=tuple(str(value) for value in raw["parent_digests"]),
                    git_commit=str(raw["git_commit"]),
                )
                column_values = {
                    "execution_id": registration.execution_id,
                    "control_plane_key": registration.control_plane_key,
                    "task_digest": registration.task_digest,
                    "task_key": registration.task_key,
                    "artifact_digest": registration.artifact_digest,
                    "artifact_type": registration.artifact_type,
                    "schema_version": registration.schema_version,
                    "artifact_path": registration.artifact_path,
                    "git_commit": registration.git_commit,
                }
                if (
                    str(row["registration_digest"])
                    != registration.registration_digest
                    or list(row["parent_digests_json"])
                    != list(registration.parent_digests)
                    or any(
                        str(row[name]) != str(value)
                        for name, value in column_values.items()
                    )
                ):
                    raise ValueError("registration columns")
                registrations.append(registration)
        except (KeyError, TypeError, ValueError) as exc:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_output_changed"
            ) from exc
        if len(registrations) != 2:
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_output_changed"
            )
        route_registration, execution_registration = registrations
        if (
            route_registration.execution_id != execution_id
            or route_registration.control_plane_key != control_plane_key
            or route_registration.task_key != RECOVERY_TASK_KEY
            or route_registration.task_digest != recovery_task.artifact_digest
            or route_registration.artifact_digest != route_digest
            or route_registration.artifact_type
            != str(metric["route_serialized_artifact_type"])
            or route_registration.schema_version
            != "dehps-m4-measurement-routing-decision.v1"
            or route_registration.artifact_path != expected_route_path
            or route_registration.parent_digests
            or route_registration.git_commit != git_commit
            or execution_registration.execution_id != execution_id
            or execution_registration.control_plane_key != control_plane_key
            or execution_registration.task_key != RECOVERY_TASK_KEY
            or execution_registration.task_digest != recovery_task.artifact_digest
            or execution_registration.artifact_digest
            != execution_artifact_digest
            or execution_registration.artifact_type
            != "research_os_mainline_execution"
            or execution_registration.schema_version
            != "dehps-research-os-mainline-execution.v1"
            or execution_registration.artifact_path != expected_execution_path
            or execution_registration.parent_digests
            != (source_digest, route_digest)
            or execution_registration.git_commit != git_commit
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_output_changed"
            )
        expected_publication_batch_digest = m4_v2_domain_digest(
            {
                "control_plane_key": control_plane_key,
                "expected_head_manifest_digest": running.artifact_digest,
                "task_key": RECOVERY_TASK_KEY,
                "task_digest": recovery_task.artifact_digest,
                "execution_id": execution_id,
                "git_commit": git_commit,
                "ordered_artifact_digest_path_pairs": [
                    {
                        "artifact_digest": route_registration.artifact_digest,
                        "canonical_artifact_path": route_registration.artifact_path,
                    },
                    {
                        "artifact_digest": execution_registration.artifact_digest,
                        "canonical_artifact_path": execution_registration.artifact_path,
                    },
                ],
            },
            domain="dehps.m4.v2.mainline-publication-batch-identity.v1",
        )
        if (
            str(terminal_payload["publication_batch_digest"])
            != expected_publication_batch_digest
        ):
            raise ResearchOSValidationError(
                "m4_v2_global_recovery_v2_output_changed"
            )

    @staticmethod
    def _verify_m4_v2_failed_global_routing_recovery_import(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
    ) -> None:
        """Verify the frozen failed Global lineage before the first write."""

        builder = _load_m4_v2_global_routing_recovery_v1_builder()
        INPUT_MANIFEST_DIGEST = builder.INPUT_MANIFEST_DIGEST
        OLD_EVENT_MANIFEST_DIGEST = builder.OLD_EVENT_MANIFEST_DIGEST
        OLD_EXECUTION_ID = builder.OLD_EXECUTION_ID
        OLD_FAILED_EVENT_DIGEST = builder.OLD_FAILED_EVENT_DIGEST
        OLD_STARTED_EVENT_DIGEST = builder.OLD_STARTED_EVENT_DIGEST
        OLD_TASK_DIGEST = builder.OLD_TASK_DIGEST
        OLD_TASK_KEY = builder.OLD_TASK_KEY
        P3_REVISIONS = builder.P3_REVISIONS
        RECOVERY_TASK_KEY = builder.RECOVERY_TASK_KEY
        build_manifest = builder.build_manifest

        tasks = {task.task_key: task for task in manifest.tasks}
        recovery = tasks.get(RECOVERY_TASK_KEY)
        if recovery is None:
            return
        if control_plane_key != "m4-information-theory-mainline":
            raise ResearchOSValidationError("m4_v2_global_recovery_control_plane_changed")
        if OLD_TASK_KEY in tasks or len(recovery.input_artifact_digests) != 1:
            raise ResearchOSValidationError("m4_v2_global_recovery_task_identity_changed")

        control = cursor.execute(
            """SELECT current_manifest_digest FROM research_os_control_planes
               WHERE control_plane_key = %s FOR UPDATE""",
            (control_plane_key,),
        ).fetchone()
        if control is None:
            raise ResearchOSValidationError("m4_v2_global_recovery_control_plane_missing")
        current_digest = str(control["current_manifest_digest"])
        stored = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (current_digest,),
        ).fetchone()
        if stored is None:
            raise ResearchOSValidationError("m4_v2_global_recovery_manifest_missing")
        current = ControlPlaneManifest.from_dict(dict(stored["manifest_json"]))
        if current_digest == INPUT_MANIFEST_DIGEST:
            expected, _ = build_manifest(
                current.to_dict(include_digest=True),
                global_source_contract_digest=recovery.input_artifact_digests[0],
            )
            if manifest.to_dict(include_digest=True) != expected:
                raise ResearchOSValidationError("m4_v2_global_recovery_output_changed")
        else:
            current_tasks = {task.task_key: task for task in current.tasks}
            keys = {RECOVERY_TASK_KEY, *(key for key, _, _ in P3_REVISIONS)}
            if OLD_TASK_KEY in current_tasks or any(
                current_tasks.get(key) is None
                or current_tasks[key].artifact_digest != tasks[key].artifact_digest
                for key in keys
            ):
                raise ResearchOSValidationError("m4_v2_global_recovery_lineage_changed")

        state = cursor.execute(
            """SELECT ts.declared_status, ts.completion_classification,
                      ts.superseded_by_task_digest
               FROM research_os_task_states ts
               WHERE ts.control_plane_key = %s AND ts.task_digest = %s""",
            (control_plane_key, OLD_TASK_DIGEST),
        ).fetchone()
        if (
            state is None
            or str(state["declared_status"]) != "failed"
            or str(state["completion_classification"]) != "INTEGRATED"
            or state["superseded_by_task_digest"] is not None
        ):
            raise ResearchOSValidationError("m4_v2_global_recovery_old_state_changed")
        rows = cursor.execute(
            """SELECT event_digest, execution_id, manifest_digest, task_digest,
                      task_key, event_type, sequence
               FROM research_os_mainline_execution_events
               WHERE control_plane_key = %s AND task_key = %s AND execution_id = %s
               ORDER BY sequence, event_digest""",
            (control_plane_key, OLD_TASK_KEY, OLD_EXECUTION_ID),
        ).fetchall()
        expected_rows = (
            (OLD_STARTED_EVENT_DIGEST, "started", 0),
            (OLD_FAILED_EVENT_DIGEST, "failed", 1),
        )
        if len(rows) != 2 or any(
            str(row["event_digest"]) != digest
            or str(row["execution_id"]) != OLD_EXECUTION_ID
            or str(row["manifest_digest"]) != OLD_EVENT_MANIFEST_DIGEST
            or str(row["task_digest"]) != OLD_TASK_DIGEST
            or str(row["task_key"]) != OLD_TASK_KEY
            or str(row["event_type"]) != event_type
            or int(row["sequence"]) != sequence
            for row, (digest, event_type, sequence) in zip(rows, expected_rows, strict=True)
        ):
            raise ResearchOSValidationError("m4_v2_global_recovery_event_lineage_changed")

    def load_manifest(self, *, control_plane_key: str) -> ControlPlaneManifest:
        key = self._key(control_plane_key)
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            control = cursor.execute(
                """
                SELECT current_manifest_digest, schema_version
                FROM research_os_control_planes
                WHERE control_plane_key = %s
                """,
                (key,),
            ).fetchone()
            if control is None:
                raise ResearchOSValidationError(f"control plane not found: {key}")
            manifest_digest = str(control["current_manifest_digest"])
            stored_manifest = cursor.execute(
                "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
                (manifest_digest,),
            ).fetchone()
            if stored_manifest is None:
                raise ResearchOSValidationError("current manifest row is missing")

            goal_rows = cursor.execute(
                """
                SELECT gd.goal_digest, gd.definition_json, gs.status, gs.retired_at,
                       gs.superseded_by_goal_digest
                FROM research_os_manifest_goals mg
                JOIN research_os_goal_definitions gd ON gd.goal_digest = mg.goal_digest
                JOIN research_os_goal_states gs
                  ON gs.control_plane_key = %s AND gs.goal_digest = gd.goal_digest
                WHERE mg.manifest_digest = %s
                ORDER BY mg.ordinal
                """,
                (key, manifest_digest),
            ).fetchall()
            task_rows = cursor.execute(
                """
                SELECT td.task_digest, td.definition_json, ts.declared_status,
                       ts.completion_classification,
                       ts.superseded_by_task_digest, ts.resolved_status,
                       ts.reason_code, ts.dependency_state_json
                FROM research_os_manifest_tasks mt
                JOIN research_os_task_definitions td ON td.task_digest = mt.task_digest
                JOIN research_os_task_states ts
                  ON ts.control_plane_key = %s AND ts.task_digest = td.task_digest
                WHERE mt.manifest_digest = %s
                ORDER BY mt.ordinal
                """,
                (key, manifest_digest),
            ).fetchall()
            fact_rows = cursor.execute(
                """
                SELECT fact_type, fact_key
                FROM research_os_dependency_facts
                WHERE control_plane_key = %s AND fact_status = 'available'
                ORDER BY fact_type, fact_key
                """,
                (key,),
            ).fetchall()

        goals: list[dict[str, Any]] = []
        for row in goal_rows:
            definition = dict(row["definition_json"])
            goal = Goal.from_dict(definition)
            if goal.artifact_digest != str(row["goal_digest"]):
                raise ResearchOSValidationError(
                    f"stored Goal definition digest mismatch: {row['goal_digest']}"
                )
            goals.append(
                {
                    **definition,
                    "status": str(row["status"]),
                    "retired_at": row["retired_at"].isoformat() if row["retired_at"] else None,
                    "superseded_by_goal_digest": row["superseded_by_goal_digest"],
                }
            )

        tasks: list[dict[str, Any]] = []
        stored_projections: dict[str, dict[str, Any]] = {}
        for row in task_rows:
            definition = dict(row["definition_json"])
            task = Task.from_dict(definition, goal_digest=str(definition.get("goal_digest") or ""))
            if task.artifact_digest != str(row["task_digest"]):
                raise ResearchOSValidationError(
                    f"stored Task definition digest mismatch: {row['task_digest']}"
                )
            tasks.append(
                {
                    **definition,
                    "status": str(row["declared_status"]),
                    "completion_classification": row["completion_classification"],
                    "superseded_by_task_digest": row["superseded_by_task_digest"],
                }
            )
            stored_projections[task.artifact_digest] = {
                "status": str(row["resolved_status"]),
                "reason_code": str(row["reason_code"]),
                "dependencies": list(row["dependency_state_json"] or []),
            }

        facts: dict[str, list[str]] = {
            "artifacts": [],
            "evidence": [],
            "external_events": [],
            "authorities": [],
        }
        fact_field = {
            "artifact": "artifacts",
            "evidence": "evidence",
            "external_event": "external_events",
            "authority": "authorities",
        }
        for row in fact_rows:
            facts[fact_field[str(row["fact_type"])]].append(str(row["fact_key"]))

        payload = {
            "schema_version": str(control["schema_version"]),
            "goals": goals,
            "tasks": tasks,
            "facts": facts,
        }
        manifest = ControlPlaneManifest.from_dict(payload)
        if manifest.artifact_digest != manifest_digest:
            raise ResearchOSValidationError(
                f"repository manifest digest mismatch: expected {manifest_digest}, "
                f"calculated {manifest.artifact_digest}"
            )
        if stable_json(dict(stored_manifest["manifest_json"])) != stable_json(
            manifest.to_dict(include_digest=False)
        ):
            raise ResearchOSValidationError("stored immutable manifest payload mismatch")

        snapshot = self.control_plane.resolve(manifest)
        self._verify_state_projection(snapshot.resolutions, stored_projections)
        return manifest

    def resolve_persisted(self, *, control_plane_key: str) -> ResolutionSnapshot:
        return self.control_plane.resolve(self.load_manifest(control_plane_key=control_plane_key))

    def export_manifest(self, *, control_plane_key: str) -> dict[str, Any]:
        return self.load_manifest(control_plane_key=control_plane_key).to_dict(include_digest=True)

    def record_external_executor_observation(
        self,
        *,
        control_plane_key: str,
        observation: ExternalExecutorObservation,
    ) -> bool:
        key = self._key(control_plane_key)
        payload = jsonable(observation)
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            exists = cursor.execute(
                "SELECT 1 FROM research_os_control_planes WHERE control_plane_key = %s",
                (key,),
            ).fetchone()
            if exists is None:
                raise ResearchOSValidationError(f"control plane not found: {key}")
            row = cursor.execute(
                """
                INSERT INTO research_os_external_executor_observations (
                  observation_digest, control_plane_key, capability, owner,
                  status, pid, observed_at, observation_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (observation_digest) DO NOTHING
                RETURNING observation_digest
                """,
                (
                    observation.artifact_digest,
                    key,
                    observation.capability,
                    observation.owner,
                    observation.status,
                    observation.pid,
                    observation.observed_at,
                    _json(payload),
                ),
            ).fetchone()
        return row is not None

    def list_external_executor_observations(
        self,
        *,
        control_plane_key: str,
        limit: int = 100,
    ) -> tuple[dict[str, Any], ...]:
        key = self._key(control_plane_key)
        if limit < 1 or limit > 1000:
            raise ResearchOSValidationError("observation limit must be between 1 and 1000")
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT observation_digest, observation_json
                FROM research_os_external_executor_observations
                WHERE control_plane_key = %s
                ORDER BY observed_at DESC, observation_digest DESC
                LIMIT %s
                """,
                (key, limit),
            ).fetchall()
        return tuple(
            {"observation_digest": str(row["observation_digest"]), **dict(row["observation_json"])}
            for row in rows
        )

    def record_mainline_execution_event(
        self,
        *,
        event: MainlineExecutionEvent,
    ) -> bool:
        payload = jsonable(event)
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                """
                INSERT INTO research_os_mainline_execution_events (
                  event_digest, execution_id, control_plane_key, manifest_digest,
                  task_digest, task_key, capability, event_type, sequence,
                  recorded_at, event_json
                ) VALUES (
                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
                )
                ON CONFLICT (event_digest) DO NOTHING
                RETURNING event_digest
                """,
                (
                    event.artifact_digest,
                    event.execution_id,
                    event.control_plane_key,
                    event.manifest_digest,
                    event.task_digest,
                    event.task_key,
                    event.capability,
                    event.event_type,
                    event.sequence,
                    event.recorded_at,
                    _json(payload),
                ),
            ).fetchone()
        return row is not None

    def register_mainline_artifact(
        self,
        *,
        registration: MainlineArtifactRegistration,
    ) -> bool:
        payload = jsonable(registration)
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            if (
                registration.task_key
                == _M4_V2_GLOBAL_REPLAY_COMPATIBILITY_V1_TASK_KEY
            ):
                self._verify_m4_v2_global_routing_replay_compatibility_v1_registration(
                    cursor,
                    registration=registration,
                )
            row = cursor.execute(
                """
                INSERT INTO research_os_mainline_artifacts (
                  registration_digest, execution_id, control_plane_key,
                  task_digest, task_key, artifact_digest, artifact_type,
                  schema_version, artifact_path, parent_digests_json,
                  git_commit, registration_json
                ) VALUES (
                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb
                )
                ON CONFLICT (registration_digest) DO NOTHING
                RETURNING registration_digest
                """,
                (
                    registration.registration_digest,
                    registration.execution_id,
                    registration.control_plane_key,
                    registration.task_digest,
                    registration.task_key,
                    registration.artifact_digest,
                    registration.artifact_type,
                    registration.schema_version,
                    registration.artifact_path,
                    _json(registration.parent_digests),
                    registration.git_commit,
                    _json(payload),
                ),
            ).fetchone()
        return row is not None

    def list_mainline_execution_events(
        self,
        *,
        control_plane_key: str,
        task_key: str | None = None,
        execution_id: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        clauses = ["control_plane_key = %s"]
        params: list[Any] = [self._key(control_plane_key)]
        if task_key is not None:
            clauses.append("task_key = %s")
            params.append(self._key(task_key))
        if execution_id is not None:
            clauses.append("execution_id = %s")
            params.append(self._key(execution_id))
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                f"""
                SELECT event_digest, event_json
                FROM research_os_mainline_execution_events
                WHERE {' AND '.join(clauses)}
                ORDER BY recorded_at, sequence, event_digest
                """,
                tuple(params),
            ).fetchall()
        return tuple(
            {"event_digest": str(row["event_digest"]), **dict(row["event_json"])}
            for row in rows
        )

    def list_mainline_execution_event_metadata(
        self,
        *,
        control_plane_key: str,
        task_keys: tuple[str, ...] = (),
    ) -> tuple[dict[str, Any], ...]:
        """Return a result-blind event projection without loading event payload."""

        clauses = ["control_plane_key = %s"]
        params: list[Any] = [self._key(control_plane_key)]
        if task_keys:
            clauses.append("task_key = ANY(%s)")
            params.append([self._key(item) for item in task_keys])
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                f"""
                SELECT event_digest, execution_id, control_plane_key,
                       manifest_digest, task_digest, task_key, capability,
                       event_type, sequence, recorded_at
                FROM research_os_mainline_execution_events
                WHERE {' AND '.join(clauses)}
                ORDER BY recorded_at, sequence, event_digest
                """,
                tuple(params),
            ).fetchall()
        return tuple(
            {
                "event_digest": str(row["event_digest"]),
                "execution_id": str(row["execution_id"]),
                "control_plane_key": str(row["control_plane_key"]),
                "manifest_digest": str(row["manifest_digest"]),
                "task_digest": str(row["task_digest"]),
                "task_key": str(row["task_key"]),
                "capability": str(row["capability"]),
                "event_type": str(row["event_type"]),
                "sequence": int(row["sequence"]),
                "recorded_at": row["recorded_at"].isoformat(),
            }
            for row in rows
        )

    def list_mainline_artifacts(
        self,
        *,
        control_plane_key: str,
        execution_id: str,
    ) -> tuple[dict[str, Any], ...]:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT registration_digest, registration_json
                FROM research_os_mainline_artifacts
                WHERE control_plane_key = %s AND execution_id = %s
                ORDER BY artifact_type, artifact_digest
                """,
                (self._key(control_plane_key), self._key(execution_id)),
            ).fetchall()
        return tuple(
            {
                "registration_digest": str(row["registration_digest"]),
                **dict(row["registration_json"]),
            }
            for row in rows
        )

    @staticmethod
    def _key(value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ResearchOSValidationError("repository key must be a non-empty string")
        return normalized

    @staticmethod
    def _fact_rows(manifest: ControlPlaneManifest) -> tuple[tuple[str, str], ...]:
        rows = [
            *(("artifact", item) for item in manifest.facts.artifacts),
            *(("evidence", item) for item in manifest.facts.evidence),
            *(("external_event", item) for item in manifest.facts.external_events),
            *(("authority", item) for item in manifest.facts.authorities),
        ]
        return tuple(sorted(rows))

    @staticmethod
    def _current_revisions(cursor, control_plane_key: str) -> tuple[dict[str, str], dict[str, str]]:
        exists = cursor.execute(
            """
            SELECT current_manifest_digest
            FROM research_os_control_planes
            WHERE control_plane_key = %s
            """,
            (control_plane_key,),
        ).fetchone()
        if exists is None:
            return {}, {}
        manifest_digest = str(exists["current_manifest_digest"])
        goal_rows = cursor.execute(
            """
            SELECT gd.goal_key, gd.goal_digest
            FROM research_os_manifest_goals mg
            JOIN research_os_goal_definitions gd ON gd.goal_digest = mg.goal_digest
            WHERE mg.manifest_digest = %s
            """,
            (manifest_digest,),
        ).fetchall()
        task_rows = cursor.execute(
            """
            SELECT td.task_key, td.task_digest
            FROM research_os_manifest_tasks mt
            JOIN research_os_task_definitions td ON td.task_digest = mt.task_digest
            WHERE mt.manifest_digest = %s
            """,
            (manifest_digest,),
        ).fetchall()
        return (
            {str(row["goal_key"]): str(row["goal_digest"]) for row in goal_rows},
            {str(row["task_key"]): str(row["task_digest"]) for row in task_rows},
        )

    @staticmethod
    def _verify_goal_definition(cursor, goal: Goal) -> None:
        row = cursor.execute(
            "SELECT definition_json FROM research_os_goal_definitions WHERE goal_digest = %s",
            (goal.artifact_digest,),
        ).fetchone()
        if row is None:
            raise ResearchOSValidationError("stored Goal definition is missing")
        stored = Goal.from_dict(dict(row["definition_json"]))
        if stored.artifact_digest != goal.artifact_digest:
            raise ResearchOSValidationError("stored Goal definition failed digest verification")

    @staticmethod
    def _verify_task_definition(cursor, task: Task) -> None:
        row = cursor.execute(
            "SELECT definition_json FROM research_os_task_definitions WHERE task_digest = %s",
            (task.artifact_digest,),
        ).fetchone()
        if row is None:
            raise ResearchOSValidationError("stored Task definition is missing")
        stored = Task.from_dict(dict(row["definition_json"]), goal_digest=task.goal_digest)
        if stored.artifact_digest != task.artifact_digest:
            raise ResearchOSValidationError("stored Task definition failed digest verification")

    @staticmethod
    def _verify_manifest_row(cursor, manifest: ControlPlaneManifest) -> None:
        row = cursor.execute(
            "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest = %s",
            (manifest.artifact_digest,),
        ).fetchone()
        if row is None:
            raise ResearchOSValidationError("stored manifest is missing")
        stored = ControlPlaneManifest.from_dict(dict(row["manifest_json"]))
        if stored.artifact_digest != manifest.artifact_digest:
            raise ResearchOSValidationError("stored manifest failed digest verification")

    @staticmethod
    def _verify_state_projection(
        resolutions: tuple[TaskResolution, ...],
        stored: dict[str, dict[str, Any]],
    ) -> None:
        if {item.task_digest for item in resolutions} != set(stored):
            raise ResearchOSValidationError("stored Task state projection membership mismatch")
        for resolution in resolutions:
            state = stored[resolution.task_digest]
            expected_dependencies = jsonable(resolution.unsatisfied_dependencies)
            if (
                state["status"] != resolution.status.value
                or state["reason_code"] != resolution.reason_code
                or state["dependencies"] != expected_dependencies
            ):
                raise ResearchOSValidationError(
                    f"stored Task state projection mismatch: {resolution.task_key}"
                )

    @staticmethod
    def _verify_mainline_completion_records(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
        m4_v2_lifecycle_verified: bool = False,
    ) -> None:
        recovery_v3 = next(
            (
                task
                for task in manifest.tasks
                if task.task_key == "m4-v2-global-routing-recovery-v3"
            ),
            None,
        )
        if (
            recovery_v3 is not None
            and manifest.task_state_by_digest[
                recovery_v3.artifact_digest
            ].declared_status.value
            == "completed"
        ):
            PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v3_import(
                cursor,
                control_plane_key=control_plane_key,
                manifest=manifest,
            )
        recovery_v2 = next(
            (
                task
                for task in manifest.tasks
                if task.task_key == "m4-v2-global-routing-recovery-v2"
            ),
            None,
        )
        if (
            not m4_v2_lifecycle_verified
            and recovery_v2 is not None
            and manifest.task_state_by_digest[
                recovery_v2.artifact_digest
            ].declared_status.value
            == "completed"
        ):
            PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v2_import(
                cursor,
                control_plane_key=control_plane_key,
                manifest=manifest,
            )
        for task in manifest.tasks:
            if task.requested_capability is None:
                continue
            execution_ids = completion_execution_ids(manifest, task=task)
            for execution_id in execution_ids:
                completed = cursor.execute(
                    """
                    SELECT 1
                    FROM research_os_mainline_execution_events
                    WHERE control_plane_key = %s
                      AND task_digest = %s
                      AND task_key = %s
                      AND execution_id = %s
                      AND event_type = 'completed'
                    """,
                    (
                        control_plane_key,
                        task.artifact_digest,
                        task.task_key,
                        execution_id,
                    ),
                ).fetchone()
                if completed is None:
                    raise ResearchOSValidationError(
                        f"task {task.task_key!r} completion fact has no immutable "
                        "completed mainline execution event"
                    )
                artifact = cursor.execute(
                    """
                    SELECT 1
                    FROM research_os_mainline_artifacts
                    WHERE control_plane_key = %s
                      AND task_digest = %s
                      AND execution_id = %s
                    LIMIT 1
                    """,
                    (control_plane_key, task.artifact_digest, execution_id),
                ).fetchone()
                if artifact is None:
                    raise ResearchOSValidationError(
                        f"task {task.task_key!r} completion fact has no registered "
                        "mainline artifact"
                    )

    @staticmethod
    def _verify_no_mainline_completion_regression(
        cursor,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
        previous_tasks: dict[str, str],
    ) -> None:
        incoming_states = manifest.task_state_by_digest
        for task in manifest.tasks:
            if task.requested_capability is None:
                continue
            if previous_tasks.get(task.task_key) != task.artifact_digest:
                continue
            row = cursor.execute(
                """
                SELECT declared_status, completion_classification
                FROM research_os_task_states
                WHERE control_plane_key = %s AND task_digest = %s
                """,
                (control_plane_key, task.artifact_digest),
            ).fetchone()
            if row is None or str(row["declared_status"]) != "completed":
                continue
            incoming = incoming_states[task.artifact_digest]
            if incoming.declared_status.value != "completed":
                raise ResearchOSValidationError(
                    f"mainline completion regression forbidden for task {task.task_key!r}"
                )
