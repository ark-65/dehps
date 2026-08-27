from __future__ import annotations

import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Any

import requests
from psycopg.rows import dict_row

from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import (
    AgentExecutionStatus,
    AgentRequestStatus,
    AgentRequestType,
)
from dehps.agents.roles import AgentRole
from dehps.config import ROOT_DIR
from dehps.notifications import isolated_challenger_v11 as mail
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.models import ResearchOSValidationError, Task
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.research_os.supervisor import (
    AtomicArtifactPayload,
    AtomicCapabilityResult,
    MainlineSupervisorError,
    ResearchEvidenceSupervisor,
)

from . import forward_prequential_confirmatory as formal_p3
from . import isolated_challenger_v11_artifacts as artifacts
from . import isolated_challenger_v11_contract as contract
from . import isolated_challenger_v11_reporting as reporting
from . import isolated_challenger_v11_search as search


class IsolatedMainlineError(contract.IsolatedChallengerContractError):
    pass


_PUBLICATION_PATCH_LOCK = RLock()
_EXACT_FAILED_RECOVERY_TASK_KEY = (
    "m4-isolated-24h-challenger-v11-search-batch-000000000000"
)
_EXACT_FAILED_RECOVERY_TASK_DIGEST = (
    "fc6bacf51dfe3de513aabb908900a1d67b8f7f3b67b1042631bf2c8177860f0b"
)
_EXACT_FAILED_RECOVERY_EXECUTION_ID = (
    "a493038f96f8b5657ae36642ce6d4007df1f1c9911071c8fb33047995e5816ef"
)
_EXACT_FAILED_RECOVERY_MANIFEST_DIGEST = (
    "96bf5c5b13b9f65fa48b0d8da119412f256a1ec657141be8ca8968b5fb12762f"
)
_EXACT_FAILED_RECOVERY_STARTED_EVENT_DIGEST = (
    "13c3b265371482f3291c239f5af1a2523e88e4028505e18d42d06da3e81f8222"
)
_EXACT_FAILED_RECOVERY_EVENT_DIGEST = (
    "71d714427c8c5e9219b8424095fa80a3fedfb7b97107dae19af79a03c47d501c"
)
_EXACT_FAILED_RECOVERY_ATTESTATION_DIGEST = (
    "2810d17a645483fbfb368334c20ba5264e9dcbca937908ed5dbd9471144d73e1"
)
_EXACT_FAILED_RECOVERY_ORIGIN_SOURCE_DIGEST = (
    "bf941daa91e4749354a237247f0c625ef0c47b57367d29acc58dc70642cda011"
)
_EXACT_FAILED_RECOVERY_ORIGIN_COMMIT = "443a1d72e3135b9a90912bc3e890566de4338f65"


def _external_delivery_evidence(facts: set[str]) -> dict[str, Any]:
    predraw: set[str] = set()
    postdraw: set[str] = set()
    daily: set[str] = set()
    incidents: set[str] = set()
    incident_receipts: set[str] = set()
    for fact in facts:
        if not fact.endswith(":SENT"):
            if fact.endswith("-open:OPEN") and fact.startswith(
                "m4-isolated-24h-challenger-v11-incident-"
            ):
                incidents.add(fact)
            continue
        task_key = fact.removesuffix(":SENT")
        prefix = "m4-isolated-24h-challenger-v11-"
        if not task_key.startswith(prefix):
            continue
        identity = task_key.removeprefix(prefix)
        if identity.endswith("-predraw-delivery"):
            predraw.add(identity.removesuffix("-predraw-delivery"))
        elif identity.endswith("-post-delivery"):
            postdraw.add(identity.removesuffix("-post-delivery"))
        elif identity.startswith("daily-") and identity.endswith("-delivery"):
            daily.add(identity.removeprefix("daily-").removesuffix("-delivery"))
        elif identity.startswith("incident-") and identity.endswith("-delivery"):
            incident_receipts.add(
                identity.removeprefix("incident-").removesuffix("-delivery")
            )
    completed_issues = predraw.intersection(postdraw)
    return {
        "predraw_sent_issues": sorted(predraw),
        "postdraw_sent_issues": sorted(postdraw),
        "daily_sent_epochs": sorted(daily),
        "incident_sent_ids": sorted(incident_receipts),
        "complete_external_issue_cycles": sorted(completed_issues),
        "open_incident_count": len(incidents),
        "real_mail_acceptance": bool(completed_issues and daily and not incidents),
    }


def _candidate_outcome_payload(
    outcome: search.CandidateOutcome,
) -> dict[str, Any]:
    return {
        "candidate_id": outcome.candidate_id,
        "configuration_id": outcome.configuration_id,
        "seed_ordinal": outcome.seed_ordinal,
        "seed_hex": outcome.seed_hex,
        "status": outcome.status,
        "primary_mean_hex": outcome.primary_mean.hex(),
        "block_means_hex": [value.hex() for value in outcome.block_means],
        "fold_values_hex": [value.hex() for value in outcome.fold_values],
        "error_code": outcome.error_code,
    }


def _candidate_outcome_from_payload(
    job: search.CandidateJob, payload: Mapping[str, Any]
) -> search.CandidateOutcome:
    required = {
        "candidate_id",
        "configuration_id",
        "seed_ordinal",
        "seed_hex",
        "status",
        "primary_mean_hex",
        "block_means_hex",
        "fold_values_hex",
        "error_code",
    }
    if set(payload) != required:
        raise IsolatedMainlineError("attempt_outcome_payload_shape_changed")
    outcome = search.CandidateOutcome(
        candidate_id=str(payload["candidate_id"]),
        configuration_id=str(payload["configuration_id"]),
        seed_ordinal=int(payload["seed_ordinal"]),
        seed_hex=str(payload["seed_hex"]),
        status=str(payload["status"]),
        primary_mean=float.fromhex(str(payload["primary_mean_hex"])),
        block_means=tuple(
            float.fromhex(str(value)) for value in payload["block_means_hex"]
        ),
        fold_values=tuple(
            float.fromhex(str(value)) for value in payload["fold_values_hex"]
        ),
        error_code=(
            None if payload["error_code"] is None else str(payload["error_code"])
        ),
    )
    if (
        outcome.candidate_id != job.candidate_id
        or outcome.configuration_id != job.configuration.configuration_id
        or outcome.seed_ordinal != job.seed_ordinal
        or outcome.seed_hex != job.seed_hex
        or outcome.status not in {"SUCCEEDED", "FAILED"}
        or len(outcome.block_means) != 3
        or (
            outcome.status == "SUCCEEDED"
            and (
                len(outcome.fold_values) != contract.OUTER_FOLD_COUNT
                or outcome.error_code is not None
            )
        )
        or (
            outcome.status == "FAILED"
            and (outcome.fold_values or outcome.error_code is None)
        )
    ):
        raise IsolatedMainlineError("attempt_outcome_payload_identity_changed")
    return outcome


def _isolated_atomic_artifact_relative_path(
    *,
    task_key: str,
    execution_id: str,
    slug: str,
    artifact_digest: str,
    filename: str,
) -> str:
    values = (task_key, execution_id, slug, artifact_digest, filename)
    if any(
        not value
        or Path(value).name != value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        for value in values
    ):
        raise MainlineSupervisorError("isolated atomic artifact path is not canonical")
    return (
        "runtime/isolated-24h-challenger-v11/artifacts/"
        f"{task_key}/{execution_id}/{slug}/{artifact_digest}/{filename}"
    )


def _isolated_atomic_execution_relative_path(
    *, task_key: str, execution_id: str
) -> str:
    if any(
        not value or Path(value).name != value or value in {".", ".."}
        for value in (task_key, execution_id)
    ):
        raise MainlineSupervisorError("isolated execution path is not canonical")
    return (
        "runtime/isolated-24h-challenger-v11/artifacts/"
        f"{task_key}/{execution_id}/execution.json"
    )


def _isolated_canonical_task_artifact_path(
    *,
    root_dir: Path,
    control_plane_key: str,
    task_key: str,
    execution_id: str,
    relative_path: str,
) -> Path:
    if control_plane_key != contract.CONTROL_PLANE_KEY:
        raise MainlineSupervisorError("isolated artifact control plane changed")
    raw = Path(relative_path)
    if (
        not relative_path
        or raw.is_absolute()
        or ".." in raw.parts
        or raw.as_posix() != relative_path
    ):
        raise MainlineSupervisorError("isolated artifact path is not canonical")
    root = root_dir.resolve()
    task_root = (
        root / "runtime/isolated-24h-challenger-v11/artifacts" / task_key / execution_id
    )
    if task_root.resolve() != task_root:
        raise MainlineSupervisorError("isolated artifact task root changed")
    path = (root / raw).resolve()
    if not path.is_relative_to(task_root):
        raise MainlineSupervisorError("isolated artifact escaped task execution")
    return path


def _event_payload(event: Mapping[str, Any]) -> dict[str, Any]:
    raw = event.get("payload")
    if not isinstance(raw, (list, tuple)) or any(
        not isinstance(item, (list, tuple)) or len(item) != 2 for item in raw
    ):
        raise IsolatedMainlineError("completed_event_payload_changed")
    payload = dict(raw)
    if len(payload) != len(raw):
        raise IsolatedMainlineError("completed_event_payload_duplicate")
    return payload


def formal_p3_resource_observation() -> dict[str, Any]:
    observed_monotonic_ns = time.monotonic_ns()
    try:
        result = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                contract.FORMAL_P3_UNIT,
                "--property=LoadState,ActiveState,SubState,MainPID,ControlPID",
                "--no-pager",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {
            "query_ok": False,
            "LoadState": None,
            "ActiveState": None,
            "SubState": None,
            "MainPID": None,
            "ControlPID": None,
            "observed_monotonic_ns": observed_monotonic_ns,
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
                "observed_monotonic_ns": observed_monotonic_ns,
            }
        values[key] = value
    required = {"LoadState", "ActiveState", "SubState", "MainPID", "ControlPID"}
    query_ok = result.returncode == 0 and set(values) == required
    try:
        observation: dict[str, Any] = {
            "query_ok": query_ok,
            **values,
            "MainPID": int(values["MainPID"]),
            "ControlPID": int(values["ControlPID"]),
            "observed_monotonic_ns": observed_monotonic_ns,
        }
    except (KeyError, ValueError):
        observation = {
            "query_ok": False,
            "LoadState": values.get("LoadState"),
            "ActiveState": values.get("ActiveState"),
            "SubState": values.get("SubState"),
            "MainPID": None,
            "ControlPID": None,
            "observed_monotonic_ns": observed_monotonic_ns,
        }
    return observation


def _formal_p3_quiescent() -> bool:
    return (
        contract.formal_p3_activity_state(formal_p3_resource_observation())
        == "QUIESCENT"
    )


def _wait_formal_p3_quiescence(
    *, seconds: float = contract.FORMAL_P3_QUIESCENCE_SECONDS
) -> bool:
    """Wait for one new continuous quiescent interval after a preemption."""

    quiet_started: float | None = None
    while True:
        if _formal_p3_quiescent():
            if quiet_started is None:
                quiet_started = time.monotonic()
            if time.monotonic() - quiet_started >= seconds:
                return True
        else:
            quiet_started = None
        time.sleep(contract.FORMAL_P3_POLL_SECONDS)


def thermal_observation() -> dict[str, Any]:
    observed_at = datetime.now(UTC).isoformat()
    observed_monotonic_ns = time.monotonic_ns()
    try:
        result = subprocess.run(
            ["sensors", "-j"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        payload = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return {
            "query_ok": False,
            "source": "lm-sensors-json",
            "max_cpu_celsius": None,
            "sample_count": 0,
            "observed_at": observed_at,
            "observed_monotonic_ns": observed_monotonic_ns,
        }
    samples: list[float] = []
    if isinstance(payload, dict):
        for chip_name, chip in payload.items():
            if not isinstance(chip_name, str) or not chip_name.startswith(
                ("coretemp-", "k10temp-")
            ):
                continue
            if not isinstance(chip, dict):
                continue
            for feature in chip.values():
                if not isinstance(feature, dict):
                    continue
                for field, value in feature.items():
                    if not str(field).endswith("_input") or not isinstance(
                        value, (int, float)
                    ):
                        continue
                    sample = float(value)
                    if math.isfinite(sample) and -20.0 <= sample <= 150.0:
                        samples.append(sample)
    query_ok = result.returncode == 0 and bool(samples)
    return {
        "query_ok": query_ok,
        "source": "lm-sensors-json",
        "max_cpu_celsius": max(samples) if query_ok else None,
        "sample_count": len(samples),
        "observed_at": observed_at,
        "observed_monotonic_ns": observed_monotonic_ns,
    }


class ThermalGuard:
    def __init__(self, *, root_dir: Path) -> None:
        self.state_path = (
            root_dir / "runtime/isolated-24h-challenger-v11/thermal-guard-state.json"
        )
        self._last_sample_monotonic = float("-inf")
        self._state = self._load_state()

    @staticmethod
    def _initial_state() -> dict[str, Any]:
        return {
            "schema_version": "dehps-m4-isolated-thermal-guard-state.v11",
            "paused": False,
            "consecutive_hot_samples": 0,
            "resume_below_started_at": None,
            "hard_stop_seen": False,
            "last_observation": None,
        }

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._initial_state()
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IsolatedMainlineError("thermal_guard_state_unreadable") from exc
        required = set(self._initial_state())
        if not isinstance(payload, dict) or set(payload) != required:
            raise IsolatedMainlineError("thermal_guard_state_shape_changed")
        if (
            payload["schema_version"] != "dehps-m4-isolated-thermal-guard-state.v11"
            or not isinstance(payload["paused"], bool)
            or not isinstance(payload["hard_stop_seen"], bool)
            or not isinstance(payload["consecutive_hot_samples"], int)
            or payload["consecutive_hot_samples"] < 0
            or (
                payload["resume_below_started_at"] is not None
                and not isinstance(payload["resume_below_started_at"], str)
            )
            or (
                payload["last_observation"] is not None
                and not isinstance(payload["last_observation"], dict)
            )
        ):
            raise IsolatedMainlineError("thermal_guard_state_invalid")
        return payload

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(
            f".tmp.{os.getpid()}.{time.monotonic_ns()}"
        )
        raw = (contract.canonical_json(self._state) + "\n").encode("utf-8")
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.state_path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def sample(self, *, force: bool = False) -> dict[str, Any]:
        monotonic_now = time.monotonic()
        if (
            not force
            and monotonic_now - self._last_sample_monotonic
            < contract.THERMAL_SAMPLE_SECONDS
        ):
            observation = self._state["last_observation"]
            if isinstance(observation, dict):
                return dict(observation)
        observation = thermal_observation()
        self._last_sample_monotonic = monotonic_now
        self._state["last_observation"] = observation
        if not observation["query_ok"]:
            self._state["paused"] = True
            self._state["hard_stop_seen"] = True
            self._state["resume_below_started_at"] = None
            self._persist()
            raise IsolatedMainlineError("RESOURCE_GUARD_TRIGGERED")
        temperature = float(observation["max_cpu_celsius"])
        if temperature >= contract.THERMAL_HARD_STOP_CELSIUS:
            self._state["paused"] = True
            self._state["hard_stop_seen"] = True
            self._state["consecutive_hot_samples"] = max(
                contract.THERMAL_PAUSE_CONSECUTIVE_SAMPLES,
                int(self._state["consecutive_hot_samples"]) + 1,
            )
            self._state["resume_below_started_at"] = None
        elif temperature >= contract.THERMAL_PAUSE_CELSIUS:
            self._state["consecutive_hot_samples"] = (
                int(self._state["consecutive_hot_samples"]) + 1
            )
            if (
                self._state["consecutive_hot_samples"]
                >= contract.THERMAL_PAUSE_CONSECUTIVE_SAMPLES
            ):
                self._state["paused"] = True
            self._state["resume_below_started_at"] = None
        else:
            self._state["consecutive_hot_samples"] = 0
            if self._state["paused"]:
                if temperature < contract.THERMAL_RESUME_BELOW_CELSIUS:
                    started = self._state["resume_below_started_at"]
                    if started is None:
                        self._state["resume_below_started_at"] = observation[
                            "observed_at"
                        ]
                    else:
                        elapsed = datetime.fromisoformat(
                            observation["observed_at"]
                        ) - datetime.fromisoformat(started)
                        if (
                            elapsed.total_seconds()
                            >= contract.THERMAL_RESUME_STABLE_SECONDS
                        ):
                            self._state["paused"] = False
                            self._state["hard_stop_seen"] = False
                            self._state["resume_below_started_at"] = None
                else:
                    self._state["resume_below_started_at"] = None
        self._persist()
        return dict(observation)

    @property
    def paused(self) -> bool:
        return bool(self._state["paused"])

    @property
    def hard_stop_seen(self) -> bool:
        return bool(self._state["hard_stop_seen"])

    def wait_until_ready(self) -> bool:
        while True:
            self.sample(force=True)
            if not self.paused:
                return True
            time.sleep(contract.THERMAL_SAMPLE_SECONDS)

    def preemption_reason(self) -> str | None:
        observation = self.sample()
        if float(observation["max_cpu_celsius"]) >= contract.THERMAL_HARD_STOP_CELSIUS:
            return "WORKER_PROCESS_CRASH"
        return None


def runtime_resource_observation(*, root_dir: Path) -> dict[str, Any]:
    del root_dir
    cpu_stat: dict[str, int] = {}
    memory_current: int | None = None
    cgroup_path: str | None = None
    try:
        membership = Path("/proc/self/cgroup").read_text(encoding="utf-8")
        unified = [
            line.split(":", 2)[2]
            for line in membership.splitlines()
            if line.startswith("0::")
        ]
        if len(unified) == 1:
            relative = unified[0].lstrip("/")
            cgroup = (Path("/sys/fs/cgroup") / relative).resolve()
            if cgroup.is_relative_to(Path("/sys/fs/cgroup").resolve()):
                cgroup_path = unified[0]
                memory_current = int(
                    (cgroup / "memory.current").read_text(encoding="ascii").strip()
                )
                for line in (
                    (cgroup / "cpu.stat").read_text(encoding="ascii").splitlines()
                ):
                    key, value = line.split()
                    cpu_stat[key] = int(value)
    except (OSError, ValueError):
        cpu_stat = {}
        memory_current = None
        cgroup_path = None
    load_average = os.getloadavg()
    return {
        "cgroup_query_ok": cgroup_path is not None,
        "cgroup_path": cgroup_path,
        "memory_current_bytes": memory_current,
        "cpu_stat": cpu_stat,
        "load_average_hex": [float(item).hex() for item in load_average],
        "observed_at": datetime.now(UTC).isoformat(),
    }


def load_completed_task_artifacts(
    *,
    repository: PostgresResearchOSRepository,
    root_dir: Path,
    task_key: str,
) -> tuple[dict[str, Any], ...]:
    events = repository.list_mainline_execution_events(
        control_plane_key=contract.CONTROL_PLANE_KEY,
        task_key=task_key,
    )
    completed = [item for item in events if item.get("event_type") == "completed"]
    if len(completed) != 1:
        raise IsolatedMainlineError(f"upstream_completed_event_not_unique:{task_key}")
    execution_id = str(completed[0].get("execution_id") or "")
    summary = _event_payload(completed[0])
    registrations = repository.list_mainline_artifacts(
        control_plane_key=contract.CONTROL_PLANE_KEY,
        execution_id=execution_id,
    )
    if len(registrations) != int(summary.get("registered_artifact_count", -1)):
        raise IsolatedMainlineError("upstream_registration_count_changed")
    output: list[dict[str, Any]] = []
    for registration in registrations:
        supervisor_module._registration_record(registration)
        if registration.get("control_plane_key") != contract.CONTROL_PLANE_KEY:
            raise IsolatedMainlineError("upstream_registration_control_plane_changed")
        if (
            registration.get("task_key") != task_key
            or registration.get("execution_id") != execution_id
            or registration.get("git_commit") != summary.get("git_commit")
        ):
            raise IsolatedMainlineError("upstream_registration_identity_changed")
        relative_path = str(registration.get("artifact_path") or "")
        expected_prefix = (
            f"runtime/isolated-24h-challenger-v11/artifacts/{task_key}/{execution_id}/"
        )
        path = (root_dir / relative_path).resolve()
        if (
            not relative_path.startswith(expected_prefix)
            or not path.is_relative_to(root_dir.resolve())
            or not path.is_file()
        ):
            raise IsolatedMainlineError("upstream_registration_path_changed")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if registration.get("artifact_type") == "research_os_mainline_execution":
            if payload.get("artifact_digest") != registration.get("artifact_digest"):
                raise IsolatedMainlineError("upstream_execution_digest_changed")
            continue
        parsed = artifacts.validate_artifact(payload)
        if (
            parsed.get("artifact_digest") != registration.get("artifact_digest")
            or parsed.get("artifact_type") != registration.get("artifact_type")
            or parsed.get("parent_digests") != registration.get("parent_digests")
            or parsed["body"].get("task_key") != task_key
        ):
            raise IsolatedMainlineError("upstream_artifact_registration_changed")
        output.append(parsed)
    if not output:
        raise IsolatedMainlineError("upstream_artifact_set_empty")
    return tuple(output)


def load_registered_isolated_artifact(
    *,
    repository: PostgresResearchOSRepository,
    root_dir: Path,
    artifact_digest: str,
    expected_artifact_type: str | None = None,
) -> dict[str, Any]:
    artifact_digest = contract.require_digest(
        artifact_digest, field="registered_artifact_digest"
    )
    with (
        repository.connection_factory() as connection,
        connection.cursor(row_factory=dict_row) as cursor,
    ):
        rows = cursor.execute(
            "SELECT registration_json FROM research_os_mainline_artifacts "
            "WHERE control_plane_key=%s AND artifact_digest=%s",
            (contract.CONTROL_PLANE_KEY, artifact_digest),
        ).fetchall()
    if len(rows) != 1:
        raise IsolatedMainlineError("registered_artifact_identity_not_unique")
    registration = dict(rows[0]["registration_json"])
    supervisor_module._registration_record(registration)
    if (
        registration.get("control_plane_key") != contract.CONTROL_PLANE_KEY
        or registration.get("artifact_digest") != artifact_digest
        or (
            expected_artifact_type is not None
            and registration.get("artifact_type") != expected_artifact_type
        )
    ):
        raise IsolatedMainlineError("registered_artifact_identity_changed")
    relative_path = str(registration.get("artifact_path") or "")
    root = root_dir.resolve()
    path = (root / relative_path).resolve()
    if (
        not relative_path.startswith("runtime/isolated-24h-challenger-v11/artifacts/")
        or not path.is_relative_to(root)
        or not path.is_file()
    ):
        raise IsolatedMainlineError("registered_artifact_path_changed")
    parsed = artifacts.validate_artifact(json.loads(path.read_text(encoding="utf-8")))
    if (
        parsed["artifact_digest"] != artifact_digest
        or parsed["artifact_type"] != registration.get("artifact_type")
        or parsed["parent_digests"] != registration.get("parent_digests")
        or parsed["body"].get("task_key") != registration.get("task_key")
        or parsed["body"].get("git_commit") != registration.get("git_commit")
    ):
        raise IsolatedMainlineError("registered_artifact_content_changed")
    return parsed


def load_formal_p3_completed_task_artifacts(
    *,
    repository: PostgresResearchOSRepository,
    root_dir: Path,
    task_key: str,
    expected_registration_count: int,
    expected_artifact_types: frozenset[str],
) -> tuple[str, tuple[dict[str, Any], ...]]:
    control_plane_key = "m4-information-theory-mainline"
    events = repository.list_mainline_execution_events(
        control_plane_key=control_plane_key,
        task_key=task_key,
    )
    completed = [item for item in events if item.get("event_type") == "completed"]
    if len(completed) != 1:
        raise IsolatedMainlineError(f"formal_p3_task_not_complete:{task_key}")
    execution_id = str(completed[0].get("execution_id") or "")
    summary = _event_payload(completed[0])
    registrations = repository.list_mainline_artifacts(
        control_plane_key=control_plane_key,
        execution_id=execution_id,
    )
    if (
        len(registrations) != expected_registration_count
        or int(summary.get("registered_artifact_count", -1))
        != expected_registration_count
    ):
        raise IsolatedMainlineError("formal_p3_registration_count_mismatch")
    output: list[dict[str, Any]] = []
    root = root_dir.resolve()
    for registration in registrations:
        supervisor_module._registration_record(registration)
        if (
            registration.get("control_plane_key") != control_plane_key
            or registration.get("task_key") != task_key
            or registration.get("execution_id") != execution_id
            or registration.get("git_commit") != summary.get("git_commit")
        ):
            raise IsolatedMainlineError("formal_p3_registration_identity_mismatch")
        relative_path = str(registration.get("artifact_path") or "")
        raw = Path(relative_path)
        path = (root / raw).resolve()
        if (
            not relative_path
            or raw.is_absolute()
            or ".." in raw.parts
            or not path.is_relative_to(root)
            or not path.is_file()
        ):
            raise IsolatedMainlineError("formal_p3_registration_path_mismatch")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if registration.get("artifact_type") == "research_os_mainline_execution":
            if payload.get("artifact_digest") != registration.get("artifact_digest"):
                raise IsolatedMainlineError("formal_p3_execution_digest_mismatch")
            continue
        parsed = formal_p3.validate_artifact(payload)
        if (
            parsed.get("artifact_digest") != registration.get("artifact_digest")
            or parsed.get("artifact_type") != registration.get("artifact_type")
            or parsed.get("schema_version") != registration.get("schema_version")
            or parsed.get("parent_digests") != registration.get("parent_digests")
        ):
            raise IsolatedMainlineError("formal_p3_artifact_registration_mismatch")
        output.append(parsed)
    if {item["artifact_type"] for item in output} != expected_artifact_types:
        raise IsolatedMainlineError("formal_p3_artifact_type_set_mismatch")
    return execution_id, tuple(output)


def verify_formal_p3_generic_replay(
    *,
    repository: PostgresResearchOSRepository,
    root_dir: Path,
    task_key: str,
    execution_id: str,
) -> dict[str, Any]:
    replay = ResearchEvidenceSupervisor(
        repository=repository,
        control_plane_key="m4-information-theory-mainline",
        root_dir=root_dir,
        require_clean_tree=False,
    ).replay(task_key=task_key, execution_id=execution_id)
    if (
        replay.get("status") != "REPLAY_VERIFIED"
        or replay.get("same_execution_identity") is not True
        or replay.get("same_artifact_identity") is not True
        or replay.get("same_artifact_content") is not True
        or replay.get("manual_input_assembly") is not False
        or replay.get("dispatch_performed") is not False
    ):
        raise IsolatedMainlineError("formal_p3_generic_replay_not_verified")
    return dict(replay)


def _unique_type(
    values: Sequence[Mapping[str, Any]], artifact_type: str
) -> dict[str, Any]:
    matches = [
        dict(item) for item in values if item.get("artifact_type") == artifact_type
    ]
    if len(matches) != 1:
        raise IsolatedMainlineError(f"artifact_type_not_unique:{artifact_type}")
    return matches[0]


def _ordered_unique(values: Sequence[str]) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        digest = contract.require_digest(value, field="parent_digest")
        if digest not in seen:
            output.append(digest)
            seen.add(digest)
    return tuple(output)


REGISTERED_INPUT_SCHEMA = "dehps-m4-isolated-registered-input.v11"
REGISTERED_INPUT_DOMAIN = "dehps.m4.isolated-24h-challenger.registered-input.v11"


def build_registered_input(
    *,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
    artifact_digest: str | None = None,
) -> dict[str, Any]:
    parents = list(_ordered_unique(tuple(parent_digests)))
    payload: dict[str, Any] = {
        "schema_version": REGISTERED_INPUT_SCHEMA,
        "artifact_type": artifact_type,
        "body": dict(body),
        "parent_digests": parents,
    }
    payload["artifact_digest"] = artifact_digest or contract.domain_digest(
        payload, domain=REGISTERED_INPUT_DOMAIN
    )
    validate_registered_input_payload(payload)
    return payload


def validate_registered_input_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(value)
    artifact_type = str(payload.get("artifact_type") or "")
    digest = contract.require_digest(
        payload.get("artifact_digest"), field="registered_input_digest"
    )
    if artifact_type == contract.SOURCE_ARTIFACT_TYPE:
        required = {
            "schema_version",
            "artifact_type",
            "artifact_digest",
            "source_set_digest",
            "contract_key",
            "contract_digest",
            "governance_bindings",
            "runtime_versions",
            "source_entries",
        }
        identity = dict(payload)
        identity.pop("artifact_digest")
        if (
            set(payload) != required
            or payload.get("schema_version") != contract.SOURCE_SCHEMA
            or payload.get("contract_digest") != contract.CONTRACT_DIGEST
            or contract.domain_digest(identity, domain=contract.SOURCE_DOMAIN) != digest
        ):
            raise IsolatedMainlineError("registered_source_contract_changed")
        return payload
    if (
        set(payload)
        != {
            "schema_version",
            "artifact_type",
            "artifact_digest",
            "body",
            "parent_digests",
        }
        or payload.get("schema_version") != REGISTERED_INPUT_SCHEMA
    ):
        raise IsolatedMainlineError("registered_input_shape_changed")
    body = payload.get("body")
    parents = payload.get("parent_digests")
    if not isinstance(body, dict) or not isinstance(parents, list):
        raise IsolatedMainlineError("registered_input_body_changed")
    _ordered_unique(tuple(str(item) for item in parents))
    if len(parents) != len(set(parents)):
        raise IsolatedMainlineError("registered_input_parent_duplicate")
    if artifact_type == "M4IsolatedDatabaseSchemaIdentityV11":
        expected_keys = {
            "schema_version",
            "contract_digest",
            "source_contract_digest",
            "installed_git_commit",
        }
        expected_digest = contract.domain_digest(
            {
                "schema_version": payload["schema_version"],
                "artifact_type": artifact_type,
                "body": body,
                "parent_digests": parents,
            },
            domain=REGISTERED_INPUT_DOMAIN,
        )
        valid = (
            set(body) == expected_keys
            and body.get("schema_version") == contract.DATABASE_SCHEMA_VERSION
            and body.get("contract_digest") == contract.CONTRACT_DIGEST
            and re.fullmatch(r"[0-9a-f]{40}", str(body.get("installed_git_commit")))
            is not None
            and len(parents) == 1
            and body.get("source_contract_digest") == parents[0]
            and digest == expected_digest
        )
    elif artifact_type == "M4IsolatedHistorySchemaInputV11":
        schema_digest = contract.require_digest(
            body.get("schema_digest"), field="history_schema_digest"
        )
        query_digest = contract.require_digest(
            body.get("history_query_digest"), field="history_query_digest"
        )
        source_digest = contract.require_digest(
            body.get("source_contract_digest"), field="source_contract_digest"
        )
        expected_digest = contract.domain_digest(
            {
                "schema_version": payload["schema_version"],
                "artifact_type": artifact_type,
                "body": body,
                "parent_digests": parents,
            },
            domain=REGISTERED_INPUT_DOMAIN,
        )
        valid = (
            set(body)
            == {"schema_digest", "history_query_digest", "source_contract_digest"}
            and digest == expected_digest
            and len(schema_digest) == 64
            and len(query_digest) == 64
            and len(parents) == 1
            and source_digest == parents[0]
        )
    elif artifact_type == "M4IsolatedHistoryContentInputV11":
        content_digest = contract.require_digest(
            body.get("history_content_digest"), field="history_content_digest"
        )
        schema_digest = contract.require_digest(
            body.get("schema_digest"), field="history_schema_digest"
        )
        query_digest = contract.require_digest(
            body.get("history_query_digest"), field="history_query_digest"
        )
        schedule_digest = contract.require_digest(
            body.get("schedule_contract_digest"), field="schedule_contract_digest"
        )
        source_digest = contract.require_digest(
            body.get("source_contract_digest"), field="source_contract_digest"
        )
        expected_digest = contract.domain_digest(
            {
                "schema_version": payload["schema_version"],
                "artifact_type": artifact_type,
                "body": body,
                "parent_digests": parents,
            },
            domain=REGISTERED_INPUT_DOMAIN,
        )
        valid = (
            set(body)
            == {
                "source_max_issue",
                "source_max_draw_date",
                "target_issue",
                "target_draw_date",
                "deadline",
                "official_draw_time",
                "projection_time",
                "history_query_digest",
                "history_content_digest",
                "schema_digest",
                "schedule_contract_digest",
                "source_contract_digest",
            }
            and digest == expected_digest
            and len(content_digest) == 64
            and len(schema_digest) == 64
            and len(query_digest) == 64
            and len(schedule_digest) == 64
            and len(parents) == 2
            and source_digest == parents[0]
        )
    elif artifact_type == "M4IsolatedAuditedDrawInputV11":
        valid = (
            set(body)
            == {
                "issue",
                "draw_date",
                "red_numbers",
                "blue_number",
                "history_source",
                "payout_source",
                "payout_source_url",
                "raw_record_sha256",
                "tier_amounts_cny",
            }
            and digest
            == contract.domain_digest(
                body,
                domain="dehps.m4.isolated-24h-challenger.audited-draw.v11",
            )
            and len(parents) == 2
        )
    else:
        raise IsolatedMainlineError("registered_input_type_changed")
    if not valid:
        raise IsolatedMainlineError("registered_input_identity_changed")
    return payload


def _validate_history_content_parent_binding(
    *,
    repository: PostgresResearchOSRepository,
    payload: Mapping[str, Any],
) -> None:
    if payload.get("artifact_type") != "M4IsolatedHistoryContentInputV11":
        return
    parsed = validate_registered_input_payload(payload)
    schema = load_registered_input(
        repository=repository,
        artifact_digest=str(parsed["parent_digests"][1]),
        expected_artifact_type="M4IsolatedHistorySchemaInputV11",
    )
    body = parsed["body"]
    schema_body = schema["body"]
    if (
        schema["parent_digests"] != [parsed["parent_digests"][0]]
        or schema_body.get("source_contract_digest")
        != body.get("source_contract_digest")
        or schema_body.get("schema_digest") != body.get("schema_digest")
        or schema_body.get("history_query_digest") != body.get("history_query_digest")
    ):
        raise IsolatedMainlineError("registered_history_schema_parent_changed")


def register_input_artifact(
    *,
    repository: PostgresResearchOSRepository,
    payload: Mapping[str, Any],
    git_commit: str,
    source_path: str | None = None,
    content_bytes: bytes | None = None,
) -> dict[str, Any]:
    parsed = validate_registered_input_payload(payload)
    if re.fullmatch(r"[0-9a-f]{40}", git_commit) is None:
        raise IsolatedMainlineError("registered_input_git_commit_changed")
    parents = (
        []
        if parsed["artifact_type"] == contract.SOURCE_ARTIFACT_TYPE
        else parsed["parent_digests"]
    )
    content = content_bytes or contract.canonical_json(parsed).encode("ascii")
    content_sha256 = hashlib.sha256(content).hexdigest()
    with (
        repository.connection_factory() as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "INSERT INTO m4_isolated_v11.registered_inputs ("
            "artifact_digest,artifact_type,artifact_json,parent_digests_json,"
            "git_commit,source_path,content_sha256) VALUES ("
            "%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s) "
            "ON CONFLICT (artifact_digest) DO NOTHING",
            (
                parsed["artifact_digest"],
                parsed["artifact_type"],
                contract.canonical_json(parsed),
                contract.canonical_json(parents),
                git_commit,
                source_path,
                content_sha256,
            ),
        )
        row = cursor.execute(
            "SELECT artifact_type,artifact_json,parent_digests_json,git_commit,"
            "source_path,content_sha256 FROM m4_isolated_v11.registered_inputs "
            "WHERE artifact_digest=%s",
            (parsed["artifact_digest"],),
        ).fetchone()
    if row is None or (
        str(row[0]) != parsed["artifact_type"]
        or dict(row[1]) != parsed
        or list(row[2]) != parents
        or str(row[3]) != git_commit
        or row[4] != source_path
        or str(row[5]) != content_sha256
    ):
        raise IsolatedMainlineError("registered_input_persistence_changed")
    _validate_history_content_parent_binding(repository=repository, payload=parsed)
    return parsed


def load_registered_input(
    *,
    repository: PostgresResearchOSRepository,
    artifact_digest: str,
    expected_artifact_type: str | None = None,
) -> dict[str, Any]:
    digest = contract.require_digest(artifact_digest, field="registered_input_digest")
    with (
        repository.connection_factory() as connection,
        connection.cursor() as cursor,
    ):
        rows = cursor.execute(
            "SELECT artifact_type,artifact_json,parent_digests_json,git_commit,"
            "source_path,content_sha256 FROM m4_isolated_v11.registered_inputs "
            "WHERE artifact_digest=%s",
            (digest,),
        ).fetchall()
    if len(rows) != 1:
        raise IsolatedMainlineError("registered_input_not_unique")
    row = rows[0]
    parsed = validate_registered_input_payload(dict(row[1]))
    parents = (
        []
        if parsed["artifact_type"] == contract.SOURCE_ARTIFACT_TYPE
        else parsed["parent_digests"]
    )
    content = (
        (ROOT_DIR / contract.SOURCE_CONTRACT_PATH).read_bytes()
        if parsed["artifact_type"] == contract.SOURCE_ARTIFACT_TYPE
        else contract.canonical_json(parsed).encode("ascii")
    )
    if (
        parsed["artifact_digest"] != digest
        or str(row[0]) != parsed["artifact_type"]
        or list(row[2]) != parents
        or re.fullmatch(r"[0-9a-f]{40}", str(row[3])) is None
        or (
            parsed["artifact_type"] == contract.SOURCE_ARTIFACT_TYPE
            and row[4] != contract.SOURCE_CONTRACT_PATH
        )
        or (
            parsed["artifact_type"] != contract.SOURCE_ARTIFACT_TYPE
            and row[4] is not None
        )
        or str(row[5]) != hashlib.sha256(content).hexdigest()
        or (
            expected_artifact_type is not None
            and parsed["artifact_type"] != expected_artifact_type
        )
    ):
        raise IsolatedMainlineError("registered_input_registration_changed")
    _validate_history_content_parent_binding(repository=repository, payload=parsed)
    return parsed


def verify_registered_parent_closure(
    *,
    repository: PostgresResearchOSRepository,
    payloads: Sequence[Mapping[str, Any]],
) -> None:
    """Require every parent to be registered or emitted earlier atomically."""

    produced: set[str] = set()
    existing_required: set[str] = set()
    for payload in payloads:
        parsed = artifacts.validate_artifact(payload)
        digest = str(parsed["artifact_digest"])
        if digest in produced:
            raise IsolatedMainlineError("atomic_artifact_digest_duplicate")
        for parent in parsed["parent_digests"]:
            if parent not in produced:
                existing_required.add(str(parent))
        produced.add(digest)
    if not existing_required:
        return
    with (
        repository.connection_factory() as connection,
        connection.cursor() as cursor,
    ):
        registered = {
            str(row[0])
            for row in cursor.execute(
                "SELECT artifact_digest FROM research_os_mainline_artifacts "
                "WHERE artifact_digest=ANY(%s) GROUP BY artifact_digest",
                (sorted(existing_required),),
            ).fetchall()
        }
        remaining = existing_required - registered
        if remaining:
            rows = cursor.execute(
                "SELECT artifact_digest,artifact_type,artifact_json,"
                "parent_digests_json FROM "
                "m4_isolated_v11.multiplicity_registration_artifacts "
                "WHERE artifact_digest=ANY(%s)",
                (sorted(remaining),),
            ).fetchall()
            for digest, artifact_type, artifact_json, parent_digests_json in rows:
                parsed = artifacts.validate_artifact(dict(artifact_json))
                if (
                    parsed["artifact_digest"] != str(digest)
                    or parsed["artifact_type"] != str(artifact_type)
                    or parsed["parent_digests"] != list(parent_digests_json)
                ):
                    raise IsolatedMainlineError(
                        "multiplicity_parent_registration_changed"
                    )
                registered.add(str(digest))
    for digest in sorted(existing_required - registered):
        try:
            load_registered_input(
                repository=repository,
                artifact_digest=digest,
            )
        except IsolatedMainlineError as exc:
            if str(exc) != "registered_input_not_unique":
                raise
        else:
            registered.add(digest)
    if registered != existing_required:
        raise IsolatedMainlineError("artifact_parent_not_registered")


def _history_from_artifact(value: Mapping[str, Any]) -> tuple[search.HistoryRow, ...]:
    body = value.get("body")
    if not isinstance(body, dict) or not isinstance(body.get("rows"), list):
        raise IsolatedMainlineError("history_snapshot_body_changed")
    rows = tuple(
        search.HistoryRow(
            issue=str(item["issue"]),
            draw_date=datetime.fromisoformat(str(item["draw_date"])).date(),
            red_numbers=tuple(int(number) for number in item["red_numbers"]),
            blue_number=int(item["blue_number"]),
            source=str(item["source"]),
        )
        for item in body["rows"]
    )
    target_issue = str(body.get("target_issue") or "")
    target_draw_date = str(body.get("target_draw_date") or "")
    if search.history_snapshot_digest(
        rows,
        target_issue=target_issue,
        target_draw_date=target_draw_date,
    ) != body.get("history_snapshot_digest"):
        raise IsolatedMainlineError("history_snapshot_reconstruction_changed")
    return rows


def _seed(task_key: str, ordinal: int) -> str:
    return hashlib.sha256(
        f"M4_ISOLATED_24H_V6|ARTIFACT|{task_key}|{ordinal}".encode()
    ).hexdigest()[:32]


def _artifact_count(artifact_type: str) -> int:
    return {
        "M4IsolatedCandidateRegistrationV11": 18,
        "M4IsolatedExecutionAttemptV11": 18,
        "M4IsolatedCandidateResultV11": 18,
        "M4IsolatedSeedCohortV11": 6,
        "M4IsolatedDuplicateSuppressionV11": 0,
    }.get(artifact_type, 1)


def _config_digest(source_digest: str) -> str:
    return contract.domain_digest(
        {
            "contract_digest": contract.CONTRACT_DIGEST,
            "source_digest": source_digest,
            "worker_count": contract.WORKER_COUNT,
            "daily_batch_limit": contract.DAILY_BATCH_LIMIT,
            "issue_batch_limit": contract.ISSUE_BATCH_LIMIT,
        },
        domain="dehps.m4.isolated-24h-challenger.runtime-configuration.v11",
    )


def _same_aware_timestamp_instant(stored: object, expected: object) -> bool:
    try:
        stored_at = (
            stored
            if isinstance(stored, datetime)
            else datetime.fromisoformat(str(stored))
        )
        expected_at = (
            expected
            if isinstance(expected, datetime)
            else datetime.fromisoformat(str(expected))
        )
    except (TypeError, ValueError):
        return False
    if (
        stored_at.tzinfo is None
        or stored_at.utcoffset() is None
        or expected_at.tzinfo is None
        or expected_at.utcoffset() is None
    ):
        return False
    return stored_at == expected_at


def _canonical_registration_created_at(committed_at: object) -> str:
    if (
        not isinstance(committed_at, datetime)
        or committed_at.tzinfo is None
        or committed_at.utcoffset() is None
    ):
        raise IsolatedMainlineError("registration_committed_at_timezone_changed")
    return committed_at.astimezone(UTC).isoformat()


def _mail_configuration_body(*, simulation: bool) -> dict[str, Any]:
    if simulation:
        from dehps.notifications.isolated_challenger_v11 import fake_configuration_body

        return fake_configuration_body()
    from dehps.notifications.isolated_challenger_v11 import (
        MailRuntimeConfiguration,
        probe_external_configuration,
    )

    return probe_external_configuration(MailRuntimeConfiguration.from_environment())


def _fake_receipt_body(
    *, task_key: str, parents: Sequence[str], configuration_digest: str
) -> dict[str, Any]:
    zero = "0" * 64
    content_digest = contract.domain_digest(
        [task_key, list(parents)],
        domain="dehps.m4.isolated-24h-challenger.mail-content.v11",
    )
    delivery_key = contract.domain_digest(
        ["SIMULATION", task_key, content_digest, zero],
        domain="dehps.m4.isolated-24h-challenger.delivery-key.v11",
    )
    return {
        "mail_kind": (
            "PREDRAW_TOP100"
            if "predraw" in task_key
            else "POSTDRAW_SETTLEMENT"
            if "post-delivery" in task_key
            else "DAILY_24H_RESEARCH_SUMMARY"
            if "daily-" in task_key
            else "IMMEDIATE_FAIL_CLOSED_INCIDENT"
        ),
        "delivery_key": delivery_key,
        "mail_envelope_digest": parents[-2] if len(parents) >= 2 else zero,
        "mail_replay_digest": parents[-1] if parents else zero,
        "content_digest": content_digest,
        "recipient_set_digest": contract.domain_digest(
            [], domain="dehps.m4.isolated-24h-challenger.recipient-set.v11"
        ),
        "mail_configuration_digest": configuration_digest,
        "transport_mode": "FAKE_EPHEMERAL",
        "simulation": True,
        "attempt_count": 0,
        "client_message_id": f"<{delivery_key}@simulation.invalid>",
        "smtp_transaction_started_at": None,
        "smtp_data_accepted_at": None,
        "smtp_final_reply_code": None,
        "smtp_final_reply_bytes_digest": None,
        "tls_peer_certificate_sha256": None,
        "provider_message_id_or_null": None,
        "state": "SIMULATED",
        "error_code_or_null": None,
    }


def build_task_artifacts(
    *,
    template: contract.TaskTemplate,
    task_key: str,
    target_issue: str | None,
    git_commit: str,
    source_digest: str,
    parent_digests: Sequence[str],
    execution_id: str,
    simulation: bool,
    created_at: str | None = None,
) -> tuple[dict[str, Any], ...]:
    source_digest = contract.require_digest(source_digest, field="source_digest")
    config_digest = _config_digest(source_digest)
    output: list[dict[str, Any]] = []
    ordinal = 0
    artifact_types = template.artifact_types
    if template.name == "challenger_freeze":
        artifact_types = ("M4IsolatedChallengerFreezeV11",)
    elif template.name == "formal_p3_comparison_input":
        artifact_types = ("M4IsolatedFormalP3PendingMarkerV11",)
    for artifact_type in artifact_types:
        for local_index in range(_artifact_count(artifact_type)):
            type_body: dict[str, Any]
            if artifact_type == "M4IsolatedMailConfigurationV11":
                type_body = _mail_configuration_body(simulation=simulation)
                config_digest = str(type_body["configuration_digest"])
            elif artifact_type == "M4IsolatedDeliveryReceiptV11":
                if not simulation:
                    raise IsolatedMainlineError(
                        "external_delivery_requires_replay_bound_runtime_context"
                    )
                type_body = _fake_receipt_body(
                    task_key=task_key,
                    parents=parent_digests,
                    configuration_digest=config_digest,
                )
            elif artifact_type == "M4IsolatedOperatorAttestationV11":
                type_body = {
                    "operator_request_id": 0,
                    "approval_decision_id": 0,
                    "execution_id": 0,
                    "payload_sha256": "0" * 64,
                    "environment": "simulation",
                    "scope_digest": "0" * 64,
                    "secret_values_serialized": False,
                }
            elif artifact_type == "M4IsolatedFormalP3PendingMarkerV11":
                type_body = {
                    "status": "PENDING_LEGAL_COMPARISON",
                    "reason_codes": ["P3_ISSUE_TASK_MISSING"],
                    "formal_p3_aggregate_result_reads": 0,
                    "formal_p3_write_access": "FORBIDDEN",
                }
            elif artifact_type == "M4IsolatedEmptyIncidentHeadV11":
                type_body = {
                    "incident_seq": -1,
                    "open_count": 0,
                    "latest_incident_digest": None,
                }
            elif artifact_type == "M4IsolatedIncidentV11":
                incident_id = task_key.removeprefix(
                    "m4-isolated-24h-challenger-v11-incident-"
                ).removesuffix("-open")
                type_body = {
                    "status": "OPEN",
                    "incident_id": contract.require_digest(
                        incident_id, field="incident_id"
                    ),
                    "reason_code": "DEADLINE_OR_ABSENCE",
                    "offending_artifact_digests": list(parent_digests),
                    "opened_at": created_at,
                }
            elif artifact_type == "M4IsolatedIncidentHeadV11":
                incidents = [
                    item
                    for item in output
                    if item["artifact_type"] == "M4IsolatedIncidentV11"
                ]
                if len(incidents) != 1:
                    raise IsolatedMainlineError("simulation_incident_not_unique")
                type_body = {
                    "incident_seq": 0,
                    "open_count": 1,
                    "latest_incident_digest": incidents[0]["artifact_digest"],
                    "opened_at": created_at,
                }
            else:
                type_body = {
                    "template_name": template.name,
                    "activation_mode": template.activation_mode,
                    "status_projection": template.status_projection,
                    "execution_id": execution_id,
                    "artifact_ordinal": ordinal,
                    "type_ordinal": local_index,
                    "simulation": simulation,
                    "formal_p3_mutated": False,
                    "formal_p4_p5_p6_or_promotion_triggered": False,
                }
            seed = (
                _seed(task_key, ordinal)
                if artifact_type in artifacts.RNG_TYPES
                else None
            )
            artifact_parents = tuple(parent_digests)
            if artifact_type == "M4IsolatedIncidentHeadV11":
                artifact_parents = _ordered_unique(
                    (
                        *parent_digests,
                        type_body["latest_incident_digest"],
                    )
                )
            output.append(
                artifacts.build_artifact(
                    artifact_type=artifact_type,
                    task_key=task_key,
                    target_issue=target_issue,
                    git_commit=git_commit,
                    source_contract_digest=source_digest,
                    config_digest=config_digest,
                    parent_digests=artifact_parents,
                    type_body=type_body,
                    deterministic_seed=seed,
                    replay_status=(
                        "REPLAY_VERIFIED"
                        if "Replay" in artifact_type
                        else "NOT_APPLICABLE"
                    ),
                    created_at=created_at,
                )
            )
            ordinal += 1
    return tuple(output)


def template_for_task_key(
    task_key: str, *, context: Mapping[str, str]
) -> contract.TaskTemplate:
    matches = [
        item for item in contract.TASK_TEMPLATES if item.key(context) == task_key
    ]
    if len(matches) != 1:
        raise IsolatedMainlineError(f"task_key_not_uniquely_frozen:{task_key}")
    return matches[0]


class IsolatedV11Capability:
    def __init__(
        self,
        *,
        capability_name: str,
        context: Mapping[str, str],
        source_digest: str,
        simulation: bool,
        repository: PostgresResearchOSRepository,
        root_dir: Path,
    ) -> None:
        self.capability_name = capability_name
        self.context = dict(context)
        self.source_digest = source_digest
        self.simulation = simulation
        self.repository = repository
        self.root_dir = root_dir
        self._active_created_at: str | None = None
        self._active_execution_id: str | None = None

    def _task_key(self, name: str) -> str:
        return contract.task_template_by_name(name).key(self.context)

    def _upstream(self, name: str) -> tuple[dict[str, Any], ...]:
        return load_completed_task_artifacts(
            repository=self.repository,
            root_dir=self.root_dir,
            task_key=self._task_key(name),
        )

    def _previous_checkpoint(self) -> tuple[dict[str, Any], ...]:
        batch_seq = int(self.context["batch_seq"])
        if batch_seq == 0:
            return self._upstream("genesis")
        previous_context = {
            **self.context,
            "batch_seq": f"{batch_seq - 1:012d}",
        }
        return load_completed_task_artifacts(
            repository=self.repository,
            root_dir=self.root_dir,
            task_key=contract.task_template_by_name("search_checkpoint").key(
                previous_context
            ),
        )

    def _build(
        self,
        *,
        artifact_type: str,
        task_key: str,
        target_issue: str | None,
        git_commit: str,
        parent_digests: Sequence[str],
        type_body: Mapping[str, Any],
        seed: str | None = None,
        replay_status: str = "NOT_APPLICABLE",
        created_at: str | None = None,
        config_digest: str | None = None,
    ) -> dict[str, Any]:
        return artifacts.build_artifact(
            artifact_type=artifact_type,
            task_key=task_key,
            target_issue=target_issue,
            git_commit=git_commit,
            source_contract_digest=self.source_digest,
            config_digest=config_digest or _config_digest(self.source_digest),
            parent_digests=parent_digests,
            type_body=type_body,
            deterministic_seed=seed,
            replay_status=replay_status,
            created_at=created_at or self._active_created_at,
        )

    def _execution_started_at(self, execution_id: str) -> str:
        events = self.repository.list_mainline_execution_events(
            control_plane_key=contract.CONTROL_PLANE_KEY,
            execution_id=execution_id,
        )
        started = [item for item in events if item.get("event_type") == "started"]
        if len(started) != 1:
            raise IsolatedMainlineError("execution_started_event_not_unique")
        return str(started[0]["recorded_at"])

    def _preregistration(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        return (
            self._build(
                artifact_type="M4IsolatedPreregistrationV11",
                task_key=task_key,
                target_issue=None,
                git_commit=git_commit,
                parent_digests=(),
                type_body={
                    "research_request_id": 694,
                    "research_approval_decision_id": 2925,
                    "contract_key": contract.CONTRACT_KEY,
                    "contract_digest_verified": contract.CONTRACT_DIGEST,
                    "source_contract_digest_verified": self.source_digest,
                    "operating_mode": ["RESEARCH_ONLY", "SHADOW"],
                    "formal_p3_write_access": "FORBIDDEN",
                    "promotion_authority": "NONE",
                },
            ),
        )

    def _target_projection(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        preregistration = _unique_type(
            self._upstream("preregistration"), "M4IsolatedPreregistrationV11"
        )
        projection_time = datetime.fromisoformat(self.context["projection_time"])
        projection_body = search.load_target_issue_projection(
            self.repository.connection_factory,
            projection_time=projection_time,
        )
        if (
            projection_body["source_max_issue"] != self.context["source_max_issue"]
            or projection_body["source_max_draw_date"]
            != self.context["source_max_draw_date"]
            or projection_body["target_issue"] != self.context["target_issue"]
            or projection_body["target_draw_date"] != self.context["target_draw_date"]
            or projection_body["projection_time"] != self.context["projection_time"]
        ):
            raise IsolatedMainlineError("target_projection_history_changed")
        load_registered_input(
            repository=self.repository,
            artifact_digest=self.source_digest,
            expected_artifact_type=contract.SOURCE_ARTIFACT_TYPE,
        )
        schema_input = build_registered_input(
            artifact_type="M4IsolatedHistorySchemaInputV11",
            body={
                "schema_digest": projection_body["schema_digest"],
                "history_query_digest": projection_body["history_query_digest"],
                "source_contract_digest": self.source_digest,
            },
            parent_digests=(self.source_digest,),
        )
        register_input_artifact(
            repository=self.repository,
            payload=schema_input,
            git_commit=git_commit,
        )
        content_input = build_registered_input(
            artifact_type="M4IsolatedHistoryContentInputV11",
            body={
                **projection_body,
                "source_contract_digest": self.source_digest,
            },
            parent_digests=(
                self.source_digest,
                schema_input["artifact_digest"],
            ),
        )
        register_input_artifact(
            repository=self.repository,
            payload=content_input,
            git_commit=git_commit,
        )
        parents = (
            preregistration["artifact_digest"],
            self.source_digest,
            schema_input["artifact_digest"],
            content_input["artifact_digest"],
        )
        type_body = dict(projection_body)
        if type_body.pop("target_issue", None) != self.context["target_issue"]:
            raise IsolatedMainlineError("target_projection_common_issue_changed")
        return (
            self._build(
                artifact_type="M4IsolatedTargetIssueProjectionV11",
                task_key=task_key,
                target_issue=self.context["target_issue"],
                git_commit=git_commit,
                parent_digests=parents,
                type_body=type_body,
            ),
        )

    def _history_snapshot(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        preregistration = _unique_type(
            self._upstream("preregistration"), "M4IsolatedPreregistrationV11"
        )
        projection = _unique_type(
            self._upstream("target_issue_projection"),
            "M4IsolatedTargetIssueProjectionV11",
        )
        target_issue = self.context["target_issue"]
        history = search.load_history(
            self.repository.connection_factory,
            target_issue=target_issue,
            target_draw_date=self.context["target_draw_date"],
        )
        snapshot_digest = search.history_snapshot_digest(
            history,
            target_issue=target_issue,
            target_draw_date=self.context["target_draw_date"],
        )
        if (
            projection["body"].get("source_max_issue") != history[-1].issue
            or projection["body"].get("source_max_draw_date")
            != history[-1].draw_date.isoformat()
            or projection["body"].get("target_issue") != target_issue
            or projection["body"].get("target_draw_date")
            != self.context["target_draw_date"]
            or projection["body"].get("history_query_digest")
            != contract.domain_digest(
                search.TARGET_PROJECTION_SQL,
                domain="dehps.m4.isolated-24h-challenger.schema-query.v11",
            )
        ):
            raise IsolatedMainlineError("history_projection_identity_changed")
        type_body = {
            "target_projection_digest": projection["artifact_digest"],
            "history_snapshot_digest": snapshot_digest,
            "minimum_issue": history[0].issue,
            "maximum_issue": history[-1].issue,
            "issue_count": len(history),
            "target_issue": target_issue,
            "target_draw_date": self.context["target_draw_date"],
            "query": search.HISTORY_SQL,
            "future_rows_read": 0,
            "target_rows_read": 0,
            "rows": [
                {
                    "issue": row.issue,
                    "draw_date": row.draw_date.isoformat(),
                    "red_numbers": list(row.red_numbers),
                    "blue_number": row.blue_number,
                    "source": row.source,
                }
                for row in history
            ],
        }
        if type_body.pop("target_issue", None) != target_issue:
            raise IsolatedMainlineError("history_snapshot_common_issue_changed")
        return (
            self._build(
                artifact_type="M4IsolatedHistorySnapshotV11",
                task_key=task_key,
                target_issue=target_issue,
                git_commit=git_commit,
                parent_digests=(
                    preregistration["artifact_digest"],
                    projection["artifact_digest"],
                ),
                type_body=type_body,
            ),
        )

    def _mail_configuration(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        preregistration = _unique_type(
            self._upstream("preregistration"), "M4IsolatedPreregistrationV11"
        )
        operator_attestation = _unique_type(
            self._upstream("operator_attestation"),
            "M4IsolatedOperatorAttestationV11",
        )
        load_registered_input(
            repository=self.repository,
            artifact_digest=self.source_digest,
            expected_artifact_type=contract.SOURCE_ARTIFACT_TYPE,
        )
        configuration = mail.MailRuntimeConfiguration.from_environment()
        body = mail.probe_external_configuration(configuration)
        return (
            mail.build_configuration_artifact(
                task_key=task_key,
                git_commit=git_commit,
                source_contract_digest=self.source_digest,
                parent_digests=(
                    preregistration["artifact_digest"],
                    operator_attestation["artifact_digest"],
                    self.source_digest,
                ),
                configuration_body=body,
                created_at=self._active_created_at,
            ),
        )

    def _operator_attestation(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        preregistration = _unique_type(
            self._upstream("preregistration"), "M4IsolatedPreregistrationV11"
        )
        load_registered_input(
            repository=self.repository,
            artifact_digest=self.source_digest,
            expected_artifact_type=contract.SOURCE_ARTIFACT_TYPE,
        )
        request_key = str(
            os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_REQUEST_KEY") or ""
        )
        try:
            approval_decision_id = int(
                os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_DECISION_ID", "")
            )
            execution_id = int(
                os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_EXECUTION_ID", "")
            )
        except ValueError as exc:
            raise IsolatedMainlineError(
                "operator_attestation_identity_invalid"
            ) from exc
        if not request_key or approval_decision_id < 1 or execution_id < 1:
            raise IsolatedMainlineError("operator_attestation_identity_invalid")
        agent_repository = AgentRequestRepository()
        request = agent_repository.get_request(request_key)
        decisions = agent_repository.list_decisions(request_key)
        executions = agent_repository.list_execution_metadata(request_key)
        approvals = [
            item
            for item in decisions
            if item.decision_code == "request_approved"
            and item.previous_status == "under_review"
            and item.new_status == "approved"
        ]
        execution_matches = [item for item in executions if item.id == execution_id]
        if (
            request.request_type != AgentRequestType.OPERATOR_RELEASE
            or request.status != AgentRequestStatus.EXECUTING
            or len(approvals) != 1
            or approvals[0].id != approval_decision_id
            or approvals[0].decided_by_role != AgentRole.REVIEWER
            or len(execution_matches) != 1
        ):
            raise IsolatedMainlineError("operator_attestation_governance_invalid")
        execution = execution_matches[0]
        if (
            execution.status != AgentExecutionStatus.RUNNING
            or execution.environment != "production"
            or execution.executor_role != AgentRole.OPERATOR
        ):
            raise IsolatedMainlineError("operator_attestation_execution_invalid")
        expected_actions = [
            "IMPORT_ISOLATED_V11_MANIFEST",
            "APPLY_ISOLATED_V11_MIGRATION",
            "VERIFY_ISOLATED_QQ_SMTP",
            "DEPLOY_ISOLATED_V11_SYSTEMD",
        ]
        checks = request.payload.get("checks")
        activation = (
            checks.get("isolated_v11_activation") if isinstance(checks, dict) else None
        )
        if (
            request.payload.get("version") != "m4-isolated-24h-challenger-v11"
            or request.payload.get("commit") != git_commit
            or not isinstance(activation, dict)
            or activation.get("allowed_actions") != expected_actions
            or activation.get("source_contract_digest") != self.source_digest
            or activation.get("lifecycle_addendum_request_id")
            != contract.LIFECYCLE_ADDENDUM_REQUEST_ID
            or activation.get("lifecycle_addendum_approval_decision_id")
            != contract.LIFECYCLE_ADDENDUM_APPROVAL_DECISION_ID
            or activation.get("external_isolated_mail_required") is not True
            or activation.get("formal_p3_mutation") is not False
        ):
            raise IsolatedMainlineError("operator_attestation_scope_invalid")
        payload_sha = hashlib.sha256(
            contract.canonical_json(request.payload).encode("utf-8")
        ).hexdigest()
        if request.metadata.get("payload_sha256") != payload_sha:
            raise IsolatedMainlineError("operator_attestation_payload_sha_changed")
        scope_digest = contract.domain_digest(
            request.payload,
            domain="dehps.m4.isolated-24h-challenger.operator-scope.v11",
        )
        return (
            self._build(
                artifact_type="M4IsolatedOperatorAttestationV11",
                task_key=task_key,
                target_issue=None,
                git_commit=git_commit,
                parent_digests=(
                    preregistration["artifact_digest"],
                    self.source_digest,
                ),
                type_body={
                    "operator_request_id": request.id,
                    "approval_decision_id": approval_decision_id,
                    "execution_id": execution_id,
                    "payload_sha256": payload_sha,
                    "environment": "production",
                    "scope_digest": scope_digest,
                    "secret_values_serialized": False,
                },
            ),
        )

    def _typed_replay(
        self,
        *,
        task_key: str,
        git_commit: str,
        upstream_name: str,
        artifact_type: str,
        target_issue: str | None,
    ) -> tuple[dict[str, Any], ...]:
        values = self._upstream(upstream_name)
        if upstream_name in {"search_batch", "genesis"}:
            primary_type = {
                "search_batch": "M4IsolatedSearchBatchV11",
                "genesis": "M4IsolatedSearchCheckpointV11",
            }[upstream_name]
            primary = _unique_type(values, primary_type)
        else:
            if len(values) != 1:
                raise IsolatedMainlineError("typed_replay_upstream_set_changed")
            primary = values[0]
        typed = artifacts.replay_artifact(
            primary, expected_parent_digests=primary["parent_digests"]
        )
        parents = _ordered_unique(
            (primary["artifact_digest"], *primary["parent_digests"])
        )
        return (
            self._build(
                artifact_type=artifact_type,
                task_key=task_key,
                target_issue=target_issue,
                git_commit=git_commit,
                parent_digests=parents,
                type_body={
                    "replayed_task_key": primary["body"]["task_key"],
                    "replayed_artifact_type": primary["artifact_type"],
                    "replayed_artifact_digest": primary["artifact_digest"],
                    "replayed_parent_digests": list(primary["parent_digests"]),
                    "replayed_body": primary["body"],
                    "typed_replay": typed,
                },
                replay_status="REPLAY_VERIFIED",
            ),
        )

    def _runtime_mail_configuration(
        self, configuration_artifact: Mapping[str, Any]
    ) -> mail.MailRuntimeConfiguration:
        configuration = mail.MailRuntimeConfiguration.from_environment()
        configuration.validate()
        body = configuration_artifact.get("body")
        if (
            not isinstance(body, dict)
            or body.get("transport_mode") != mail.TRANSPORT_EXTERNAL
            or body.get("configuration_digest") != configuration.configuration_digest
            or body.get("recipient_set_digest") != configuration.recipient_set_digest
            or body.get("sender_address_digest") != configuration.sender_address_digest
            or body.get("auth_probe_result") != "TLS_AUTH_NOOP_VERIFIED"
            or body.get("smtp_noop_reply_code") != 250
        ):
            raise IsolatedMainlineError("mail_configuration_runtime_drift")
        return configuration

    def _mail_envelope(
        self,
        *,
        template_name: str,
        task_key: str,
        git_commit: str,
    ) -> tuple[dict[str, Any], ...]:
        configuration_artifact = _unique_type(
            self._upstream("mail_configuration"), "M4IsolatedMailConfigurationV11"
        )
        configuration = self._runtime_mail_configuration(configuration_artifact)
        target_issue: str | None = None
        if template_name == "predraw_mail_envelope":
            replay = _unique_type(
                self._upstream("prediction_replay"), "M4IsolatedPredictionReplayV11"
            )
            prediction = replay["body"].get("replayed_body")
            if not isinstance(prediction, dict):
                raise IsolatedMainlineError("prediction_replay_body_changed")
            target_issue = self.context["target_issue"]
            tickets = tuple(
                (tuple(int(value) for value in item["reds"]), int(item["blue"]))
                for item in prediction.get("tickets", [])
            )
            subject = reporting.predraw_subject(target_issue)
            body = reporting.predraw_body(
                target_issue=target_issue,
                configuration_id=str(prediction["configuration_id"]),
                cohort_id=str(prediction["cohort_id"]),
                model_summary=str(prediction["model_summary"]),
                feature_summary=tuple(
                    str(item) for item in prediction["feature_summary"]
                ),
                maximum_training_issue=str(prediction["maximum_training_issue"]),
                tickets=tickets,
                checkpoint_digest=str(prediction["checkpoint_digest"]),
                prediction_digest=str(replay["body"]["replayed_artifact_digest"]),
                source_digest=self.source_digest,
            )
            mail_kind = "PREDRAW_TOP100"
            target_identity = target_issue
            content_parent = replay
        elif template_name == "post_mail_envelope":
            replay = _unique_type(
                self._upstream("settlement_replay"), "M4IsolatedSettlementReplayV11"
            )
            report = replay["body"].get("replayed_body")
            if not isinstance(report, dict):
                raise IsolatedMainlineError("settlement_replay_body_changed")
            target_issue = self.context["target_issue"]
            subject = reporting.postdraw_subject(target_issue)
            body = reporting.postdraw_body(
                target_issue=target_issue,
                settlement=report["settlement"],
                baseline_percentile=str(report["baseline_percentile"]),
                formal_p3_comparison=str(report["formal_p3_comparison"]),
                prediction_digest=str(report["prediction_digest"]),
                settlement_digest=str(report["settlement_digest"]),
                report_digest=str(replay["body"]["replayed_artifact_digest"]),
            )
            mail_kind = "POSTDRAW_SETTLEMENT"
            target_identity = target_issue
            content_parent = replay
        elif template_name == "daily_mail_envelope":
            replay = _unique_type(
                self._upstream("daily_summary_replay"),
                "M4IsolatedDailySummaryReplayV11",
            )
            summary = replay["body"].get("replayed_body")
            if not isinstance(summary, dict):
                raise IsolatedMainlineError("daily_replay_body_changed")
            subject = reporting.daily_subject(self.context["epoch_date"])
            body = reporting.daily_body(summary)
            mail_kind = "DAILY_24H_RESEARCH_SUMMARY"
            target_identity = self.context["epoch_date"]
            content_parent = replay
        elif template_name == "incident_envelope":
            incident = _unique_type(
                self._upstream("incident_open"), "M4IsolatedIncidentV11"
            )
            if (
                incident["body"].get("status") != "OPEN"
                or incident["body"].get("incident_id") != self.context["incident_id"]
            ):
                raise IsolatedMainlineError("incident_envelope_parent_changed")
            subject = "【隔离研发线 / 故障告警】研究流水线已故障关闭"
            body = "\n".join(
                [
                    "隔离研发线即时故障告警（RESEARCH_ONLY / SHADOW）",
                    f"incident_id: {self.context['incident_id']}",
                    f"reason_code: {incident['body']['reason_code']}",
                    "状态：FAIL_CLOSED；未修改 Formal P3。",
                    "未经重放验证的预测不会投递。",
                ]
            )
            mail_kind = "IMMEDIATE_FAIL_CLOSED_INCIDENT"
            target_identity = self.context["incident_id"]
            content_parent = incident
        else:
            raise IsolatedMainlineError("mail_envelope_template_changed")
        envelope = mail.compile_envelope(
            configuration=configuration,
            mail_kind=mail_kind,
            target_identity=target_identity,
            subject=subject,
            body=body,
        )
        envelope_body = {
            **envelope.artifact_body(),
            "mail_configuration_digest": configuration.configuration_digest,
            "subject": subject,
            "plaintext_body": body,
            "content_parent_digest": content_parent["artifact_digest"],
        }
        return (
            self._build(
                artifact_type="M4IsolatedMailEnvelopeV11",
                task_key=task_key,
                target_issue=target_issue,
                git_commit=git_commit,
                parent_digests=(content_parent["artifact_digest"],),
                type_body=envelope_body,
                config_digest=configuration.configuration_digest,
            ),
        )

    def _mail_delivery(
        self,
        *,
        template_name: str,
        task_key: str,
        git_commit: str,
    ) -> tuple[dict[str, Any], ...]:
        replay_name = {
            "predraw_delivery": "predraw_mail_replay",
            "post_delivery": "post_mail_replay",
            "daily_delivery": "daily_mail_replay",
            "incident_delivery": "incident_mail_replay",
        }.get(template_name)
        if replay_name is None:
            raise IsolatedMainlineError("delivery_template_changed")
        now = datetime.now(contract.TIMEZONE)
        if template_name == "predraw_delivery":
            scheduled = contract.schedule_for_issue(
                self.context["target_issue"],
                target_draw_date=self.context["target_draw_date"],
            )["predraw_send"]
            if not scheduled <= now < scheduled + timedelta(minutes=1):
                raise IsolatedMainlineError("PREDRAW_DELIVERY_DEADLINE_MISSED")
        elif template_name == "daily_delivery":
            scheduled = datetime.combine(
                date.fromisoformat(
                    f"{self.context['epoch_date'][:4]}-"
                    f"{self.context['epoch_date'][4:6]}-"
                    f"{self.context['epoch_date'][6:]}"
                ),
                contract.DAILY_SEND_TIME,
                contract.TIMEZONE,
            )
            if not scheduled <= now < scheduled + timedelta(minutes=1):
                raise IsolatedMainlineError("DAILY_DELIVERY_DEADLINE_MISSED")
        replay = _unique_type(self._upstream(replay_name), "M4IsolatedMailReplayV11")
        envelope_body = replay["body"].get("replayed_body")
        if not isinstance(envelope_body, dict):
            raise IsolatedMainlineError("mail_replay_envelope_body_changed")
        configuration_artifact = _unique_type(
            self._upstream("mail_configuration"), "M4IsolatedMailConfigurationV11"
        )
        configuration = self._runtime_mail_configuration(configuration_artifact)
        envelope = mail.compile_envelope(
            configuration=configuration,
            mail_kind=str(envelope_body["mail_kind"]),
            target_identity=str(envelope_body["target_identity"]),
            subject=str(envelope_body["subject"]),
            body=str(envelope_body["plaintext_body"]),
        )
        for key, value in envelope.artifact_body().items():
            if envelope_body.get(key) != value:
                raise IsolatedMainlineError("mail_envelope_typed_replay_changed")
        envelope_digest = str(replay["body"]["replayed_artifact_digest"])
        receipt_body = mail.send_external_once(
            configuration=configuration,
            envelope=envelope,
            mail_envelope_digest=envelope_digest,
            mail_replay_digest=str(replay["artifact_digest"]),
            mail_configuration_digest=configuration.configuration_digest,
            ledger=mail.DeliveryLedger(self.root_dir / mail.LEDGER_RELATIVE_PATH),
        )
        target_issue = (
            self.context["target_issue"]
            if template_name in {"predraw_delivery", "post_delivery"}
            else None
        )
        parents = (
            configuration_artifact["artifact_digest"],
            envelope_digest,
            replay["artifact_digest"],
        )
        return (
            mail.build_receipt_artifact(
                task_key=task_key,
                target_issue=target_issue,
                git_commit=git_commit,
                source_contract_digest=self.source_digest,
                receipt_body=receipt_body,
                parent_digests=parents,
                created_at=(
                    receipt_body.get("smtp_data_accepted_at")
                    or receipt_body.get("smtp_transaction_started_at")
                    or self._active_created_at
                ),
            ),
        )

    def _genesis(self, *, task_key: str, git_commit: str) -> tuple[dict[str, Any], ...]:
        preregistration = _unique_type(
            self._upstream("preregistration"), "M4IsolatedPreregistrationV11"
        )
        history = _unique_type(
            self._upstream("history_snapshot"), "M4IsolatedHistorySnapshotV11"
        )
        parents = (preregistration["artifact_digest"], history["artifact_digest"])
        empty = self._build(
            artifact_type="M4IsolatedEmptyMultiplicityHeadV11",
            task_key=task_key,
            target_issue=self.context["target_issue"],
            git_commit=git_commit,
            parent_digests=parents,
            type_body={
                "registration_seq": -1,
                "m_total": 0,
            },
        )
        checkpoint = self._build(
            artifact_type="M4IsolatedSearchCheckpointV11",
            task_key=task_key,
            target_issue=self.context["target_issue"],
            git_commit=git_commit,
            parent_digests=(empty["artifact_digest"],),
            type_body={
                "batch_seq": -1,
                "base_cursor": 0,
                "adaptive_cursor": None,
                "m_total": 0,
                "eligible_cohorts": [],
                "status": "GENESIS",
            },
        )
        with (
            self.repository.connection_factory() as connection,
            connection.cursor() as cursor,
        ):
            row = cursor.execute(
                "SELECT registration_seq,m_total,head_artifact_digest "
                "FROM m4_isolated_v11.multiplicity_head WHERE singleton=TRUE FOR UPDATE"
            ).fetchone()
            if row is None or int(row[0]) != -1 or int(row[1]) != 0:
                raise IsolatedMainlineError("multiplicity_genesis_state_changed")
            if row[2] is None:
                cursor.execute(
                    "UPDATE m4_isolated_v11.multiplicity_head "
                    "SET head_artifact_digest=%s,committed_at=%s WHERE singleton=TRUE",
                    (empty["artifact_digest"], self._active_created_at),
                )
            elif str(row[2]) != empty["artifact_digest"]:
                raise IsolatedMainlineError("multiplicity_genesis_digest_changed")
        return empty, checkpoint

    def _search_batch(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        preregistration = _unique_type(
            self._upstream("preregistration"), "M4IsolatedPreregistrationV11"
        )
        projection = _unique_type(
            self._upstream("target_issue_projection"),
            "M4IsolatedTargetIssueProjectionV11",
        )
        history_artifact = _unique_type(
            self._upstream("history_snapshot"), "M4IsolatedHistorySnapshotV11"
        )
        history = _history_from_artifact(history_artifact)
        batch_seq = int(self.context["batch_seq"])
        predecessor_values = self._previous_checkpoint()
        predecessor = _unique_type(predecessor_values, "M4IsolatedSearchCheckpointV11")
        configurations = search.base_configurations(
            snapshot_digest=str(history_artifact["body"]["history_snapshot_digest"]),
            source_contract_digest=self.source_digest,
        )
        with (
            self.repository.connection_factory() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            existing = cursor.execute(
                "SELECT registration_seq,m_before,m_after,batch_plan_digest,"
                "batch_plan_json,predecessor_head_digest,registration_delta_digest,"
                "registration_head_digest,committed_at,registration_execution_id "
                "FROM m4_isolated_v11.registration_batches WHERE batch_seq=%s",
                (batch_seq,),
            ).fetchone()
            if existing is None:
                head = cursor.execute(
                    "SELECT registration_seq,m_total,head_artifact_digest "
                    "FROM m4_isolated_v11.multiplicity_head WHERE singleton=TRUE"
                ).fetchone()
                registered_states = {
                    str(item["candidate_id"]): str(item["state"])
                    for item in cursor.execute(
                        "SELECT candidate_id,state FROM "
                        "m4_isolated_v11.candidate_registrations "
                        "WHERE snapshot_digest=%s",
                        (history_artifact["body"]["history_snapshot_digest"],),
                    ).fetchall()
                }
                existing_candidates: list[dict[str, Any]] = []
            else:
                head = None
                registered_states = {}
                existing_candidates = [
                    dict(item)
                    for item in cursor.execute(
                        "SELECT candidate_id,slot_ordinal,configuration_id,cohort_id,"
                        "parent_configuration_id,parent_candidate_id,family,"
                        "feature_ids_json,hyperparameters_json,training_window,"
                        "seed_ordinal,seed_hex,snapshot_digest,source_contract_digest "
                        "FROM m4_isolated_v11.candidate_registrations "
                        "WHERE registration_seq=%s ORDER BY slot_ordinal",
                        (int(existing["registration_seq"]),),
                    ).fetchall()
                ]
        predecessor_body = predecessor["body"]
        same_snapshot = (
            predecessor_body.get("target_issue") == self.context["target_issue"]
        )
        base_cursor = (
            int(predecessor_body.get("base_cursor", 0)) if same_snapshot else 0
        )
        adaptive_cursor = (
            int(predecessor_body.get("adaptive_cursor") or 0) if same_snapshot else 0
        )
        if existing is None:
            prior_cohorts = (
                list(predecessor_body.get("cohorts", [])) if same_snapshot else []
            )
            prior_epochs = sorted(
                {
                    str(item["body"].get("epoch_date"))
                    for item in prior_cohorts
                    if str(item["body"].get("epoch_date")) < self.context["epoch_date"]
                }
            )
            parent_records: list[dict[str, Any]] = []
            if prior_epochs:
                previous_epoch = prior_epochs[-1]
                parent_records = [
                    self._cohort_selection_record(
                        item, m_total=int(predecessor_body.get("m_total", 0))
                    )
                    for item in prior_cohorts
                    if item["body"].get("epoch_date") == previous_epoch
                ]
                parent_records = [item for item in parent_records if item["eligible"]]
                parent_records.sort(
                    key=lambda item: (
                        -float(item["multiplicity_penalized_lcb"]),
                        -float(item["minimum_block_mean"]),
                        -float(item["full_300_primary_mean"]),
                        -int(item["top100_union_size"]),
                        float(item["mean_pairwise_jaccard"]),
                        int(item["complexity_cost"]),
                        str(item["configuration_id"]),
                    )
                )
            adaptive_configurations: list[search.CandidateConfiguration] = []
            seen_adaptive: set[str] = set()
            for record in parent_records[:20]:
                raw = record["configuration"]
                parent = search.CandidateConfiguration(
                    family=str(raw["family"]),
                    representation=str(raw["representation"]),
                    training_window=raw["training_window"],
                    ordered_feature_ids=tuple(raw["ordered_feature_ids"]),
                    ordered_hyperparameters=tuple(
                        tuple(item) for item in raw["ordered_hyperparameters"]
                    ),
                    snapshot_digest=str(
                        history_artifact["body"]["history_snapshot_digest"]
                    ),
                    source_contract_digest=self.source_digest,
                    parent_configuration_id=raw.get("parent_configuration_id"),
                )
                if parent.configuration_id != record["configuration_id"]:
                    raise IsolatedMainlineError("adaptive_parent_identity_changed")
                for neighbor in search.adaptive_neighbors(parent):
                    if neighbor.configuration_id not in seen_adaptive:
                        adaptive_configurations.append(neighbor)
                        seen_adaptive.add(neighbor.configuration_id)
            proposal = search.plan_deterministic_batch(
                configurations,
                base_cursor=base_cursor,
                adaptive_configurations=adaptive_configurations,
                adaptive_cursor=adaptive_cursor,
                registered_states=registered_states,
            )
            jobs = proposal.jobs
            batch_plan = {
                "batch_seq": batch_seq,
                "epoch_date": self.context["epoch_date"],
                "target_issue": self.context["target_issue"],
                "predecessor_checkpoint_digest": predecessor["artifact_digest"],
                "base_cursor_before": base_cursor,
                "base_cursor_after": proposal.base_cursor,
                "adaptive_cursor_before": adaptive_cursor,
                "adaptive_cursor_after": proposal.adaptive_cursor,
                "slot_sources": list(proposal.slot_sources),
                "ordered_candidate_ids": [job.candidate_id for job in jobs],
                "duplicate_candidate_ids": [
                    job.candidate_id for job in proposal.duplicate_suppressions
                ],
            }
            batch_plan_digest = contract.domain_digest(
                batch_plan,
                domain="dehps.m4.isolated-24h-challenger.batch-plan.v11",
            )
        else:
            if len(existing_candidates) != contract.ATTEMPTS_PER_BATCH:
                raise IsolatedMainlineError("atomic_registration_resume_incomplete")
            resumed_jobs: list[search.CandidateJob] = []
            for row in existing_candidates:
                window_raw = str(row["training_window"])
                window: int | str = (
                    int(window_raw) if window_raw in {"900", "1500"} else window_raw
                )
                configuration = search.CandidateConfiguration(
                    family=str(row["family"]),
                    representation=(
                        "FEATURE_ABI32_COMBINATION_V1"
                        if row["family"] == "FEATURE_ABI32_LINEAR_RANKER"
                        else "STRICT_PRIOR_NUMBER_EVENT_V1"
                    ),
                    training_window=window,
                    ordered_feature_ids=tuple(row["feature_ids_json"]),
                    ordered_hyperparameters=tuple(
                        tuple(item) for item in row["hyperparameters_json"]
                    ),
                    snapshot_digest=str(row["snapshot_digest"]),
                    source_contract_digest=str(row["source_contract_digest"]),
                    parent_configuration_id=(
                        None
                        if row["parent_configuration_id"] is None
                        else str(row["parent_configuration_id"])
                    ),
                )
                job = search.candidate_job(configuration, int(row["seed_ordinal"]))
                if (
                    job.candidate_id != row["candidate_id"]
                    or job.seed_hex != row["seed_hex"]
                    or configuration.configuration_id != row["configuration_id"]
                    or search.candidate_cohort_id(configuration) != row["cohort_id"]
                    or job.parent_candidate_id != row["parent_candidate_id"]
                ):
                    raise IsolatedMainlineError("atomic_registration_resume_changed")
                resumed_jobs.append(job)
            jobs = tuple(resumed_jobs)
            batch_plan = dict(existing["batch_plan_json"])
            batch_plan_digest = contract.domain_digest(
                batch_plan,
                domain="dehps.m4.isolated-24h-challenger.batch-plan.v11",
            )
            if batch_plan_digest != existing["batch_plan_digest"] or batch_plan.get(
                "ordered_candidate_ids"
            ) != [job.candidate_id for job in jobs]:
                raise IsolatedMainlineError("batch_plan_resume_changed")
        if existing is None:
            if head is None:
                raise IsolatedMainlineError("multiplicity_head_missing")
            registration_seq = int(head["registration_seq"]) + 1
            m_before = int(head["m_total"])
            previous_head = contract.require_digest(
                head["head_artifact_digest"],
                field="previous_registration_head_digest",
            )
            registration_created_at = str(self._active_created_at)
            registration_execution_id = str(self._active_execution_id or "")
        else:
            registration_seq = int(existing["registration_seq"])
            m_before = int(existing["m_before"])
            previous_head = contract.require_digest(
                existing["predecessor_head_digest"],
                field="previous_registration_head_digest",
            )
            registration_created_at = _canonical_registration_created_at(
                existing["committed_at"]
            )
            registration_execution_id = str(existing["registration_execution_id"])
        if not re.fullmatch(r"[0-9a-f]{64}", registration_execution_id):
            raise IsolatedMainlineError("registration_execution_identity_changed")
        if registration_seq != batch_seq:
            raise IsolatedMainlineError("registration_and_batch_sequence_changed")
        if (
            m_before + contract.ATTEMPTS_PER_BATCH
            > contract.LIFETIME_MULTIPLICITY_LIMIT
        ):
            raise IsolatedMainlineError("MULTIPLICITY_RISK_LIMIT")
        registration_parents = (
            preregistration["artifact_digest"],
            projection["artifact_digest"],
            history_artifact["artifact_digest"],
            predecessor["artifact_digest"],
        )
        registrations: list[dict[str, Any]] = []
        for slot, job in enumerate(jobs):
            configuration = job.configuration
            registrations.append(
                self._build(
                    artifact_type="M4IsolatedCandidateRegistrationV11",
                    task_key=task_key,
                    target_issue=self.context["target_issue"],
                    git_commit=git_commit,
                    parent_digests=registration_parents,
                    type_body={
                        "batch_plan_digest": batch_plan_digest,
                        "batch_seq": batch_seq,
                        "slot_ordinal": slot,
                        "candidate_id": job.candidate_id,
                        "configuration_id": configuration.configuration_id,
                        "cohort_id": search.candidate_cohort_id(configuration),
                        "parent_configuration_id": configuration.parent_configuration_id,
                        "parent_candidate_id": job.parent_candidate_id,
                        "family": configuration.family,
                        "representation": configuration.representation,
                        "features": list(configuration.ordered_feature_ids),
                        "hyperparameters": [
                            list(item) for item in configuration.ordered_hyperparameters
                        ],
                        "training_window": str(configuration.training_window),
                        "seed_ordinal": job.seed_ordinal,
                        "seed_hex": job.seed_hex,
                        "snapshot_digest": configuration.snapshot_digest,
                        "source_contract_digest_bound": configuration.source_contract_digest,
                        "registry_state": "REGISTERED",
                        "started_at": None,
                        "completed_at": None,
                        "status": "REGISTERED",
                        "elimination_reason": None,
                        "eligible": False,
                        "comparison_count": 0,
                        "selection_count": 0,
                        "derived_from_existing_result": False,
                        "execution_id": registration_execution_id,
                    },
                    seed=job.seed_hex,
                    created_at=registration_created_at,
                )
            )
        duplicate_records: list[dict[str, Any]] = []
        duplicate_candidate_ids = [
            str(item) for item in batch_plan.get("duplicate_candidate_ids", [])
        ]
        if len(duplicate_candidate_ids) != len(set(duplicate_candidate_ids)):
            raise IsolatedMainlineError("duplicate_suppression_identity_changed")
        if duplicate_candidate_ids:
            with (
                self.repository.connection_factory() as connection,
                connection.cursor(row_factory=dict_row) as cursor,
            ):
                duplicate_rows = {
                    str(item["candidate_id"]): dict(item)
                    for item in cursor.execute(
                        "SELECT r.candidate_id,r.configuration_id,"
                        "r.artifact_digest AS registration_artifact_digest,"
                        "x.artifact_digest AS result_artifact_digest "
                        "FROM m4_isolated_v11.candidate_registrations r "
                        "JOIN m4_isolated_v11.candidate_results x "
                        "ON x.candidate_id=r.candidate_id "
                        "WHERE r.candidate_id=ANY(%s) AND r.state='TERMINAL'",
                        (duplicate_candidate_ids,),
                    ).fetchall()
                }
            if set(duplicate_rows) != set(duplicate_candidate_ids):
                raise IsolatedMainlineError("duplicate_terminal_evidence_incomplete")
            for candidate_id in duplicate_candidate_ids:
                row = duplicate_rows[candidate_id]
                registration_artifact = load_registered_isolated_artifact(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    artifact_digest=str(row["registration_artifact_digest"]),
                    expected_artifact_type="M4IsolatedCandidateRegistrationV11",
                )
                result_artifact = load_registered_isolated_artifact(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    artifact_digest=str(row["result_artifact_digest"]),
                    expected_artifact_type="M4IsolatedCandidateResultV11",
                )
                proposal_identity = contract.domain_digest(
                    [batch_plan_digest, candidate_id],
                    domain=("dehps.m4.isolated-24h-challenger.duplicate-proposal.v11"),
                )
                duplicate_records.append(
                    self._build(
                        artifact_type="M4IsolatedDuplicateSuppressionV11",
                        task_key=task_key,
                        target_issue=self.context["target_issue"],
                        git_commit=git_commit,
                        parent_digests=(
                            predecessor["artifact_digest"],
                            registration_artifact["artifact_digest"],
                            result_artifact["artifact_digest"],
                        ),
                        type_body={
                            "batch_plan_digest": batch_plan_digest,
                            "proposal_identity": proposal_identity,
                            "candidate_id": candidate_id,
                            "configuration_id": row["configuration_id"],
                            "existing_registration_digest": registration_artifact[
                                "artifact_digest"
                            ],
                            "existing_result_digest": result_artifact[
                                "artifact_digest"
                            ],
                            "outcome": "DUPLICATE_SUPPRESSED",
                        },
                        created_at=registration_created_at,
                    )
                )
        delta = self._build(
            artifact_type="M4IsolatedMultiplicityRegistrationDeltaV11",
            task_key=task_key,
            target_issue=self.context["target_issue"],
            git_commit=git_commit,
            parent_digests=(
                previous_head,
                *(item["artifact_digest"] for item in registrations),
            ),
            type_body={
                "registration_seq": registration_seq,
                "batch_seq": batch_seq,
                "m_before": m_before,
                "ordered_candidate_ids": [job.candidate_id for job in jobs],
                "m_after": m_before + contract.ATTEMPTS_PER_BATCH,
                "committed_at": registration_created_at,
            },
            created_at=registration_created_at,
        )
        new_head = self._build(
            artifact_type="M4IsolatedMultiplicityRegistrationHeadV11",
            task_key=task_key,
            target_issue=self.context["target_issue"],
            git_commit=git_commit,
            parent_digests=(previous_head, delta["artifact_digest"]),
            type_body={
                "registration_seq": registration_seq,
                "m_total": m_before + contract.ATTEMPTS_PER_BATCH,
                "delta_digest": delta["artifact_digest"],
                "committed_at": registration_created_at,
            },
            created_at=registration_created_at,
        )
        candidate_rows = [
            {
                "candidate_id": job.candidate_id,
                "slot_ordinal": slot,
                "configuration_id": job.configuration.configuration_id,
                "cohort_id": search.candidate_cohort_id(job.configuration),
                "parent_configuration_id": (
                    job.configuration.parent_configuration_id or ""
                ),
                "parent_candidate_id": job.parent_candidate_id or "",
                "family": job.configuration.family,
                "feature_ids": list(job.configuration.ordered_feature_ids),
                "hyperparameters": [
                    list(item) for item in job.configuration.ordered_hyperparameters
                ],
                "training_window": str(job.configuration.training_window),
                "seed_ordinal": job.seed_ordinal,
                "seed_hex": job.seed_hex,
                "snapshot_digest": job.configuration.snapshot_digest,
                "source_contract_digest": job.configuration.source_contract_digest,
                "artifact_digest": registrations[slot]["artifact_digest"],
            }
            for slot, job in enumerate(jobs)
        ]
        expected_registration_artifacts = [*registrations, delta, new_head]
        with (
            self.repository.connection_factory() as connection,
            connection.cursor() as cursor,
        ):
            if existing is None:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                committed = cursor.execute(
                    "SELECT registration_seq,m_before,m_after FROM "
                    "m4_isolated_v11.register_exact_batch("
                    "%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s::jsonb,"
                    "%s::jsonb,%s)",
                    (
                        batch_seq,
                        date.fromisoformat(
                            f"{self.context['epoch_date'][:4]}-"
                            f"{self.context['epoch_date'][4:6]}-"
                            f"{self.context['epoch_date'][6:]}"
                        ),
                        self.context["target_issue"],
                        batch_plan_digest,
                        json.dumps(batch_plan, separators=(",", ":")),
                        registration_execution_id,
                        previous_head,
                        delta["artifact_digest"],
                        new_head["artifact_digest"],
                        json.dumps(candidate_rows, separators=(",", ":")),
                        json.dumps(
                            [*registrations, delta, new_head],
                            separators=(",", ":"),
                        ),
                        registration_created_at,
                    ),
                ).fetchone()
                if committed is None or tuple(map(int, committed)) != (
                    registration_seq,
                    m_before,
                    m_before + 18,
                ):
                    raise IsolatedMainlineError("atomic_registration_result_changed")
            elif (
                int(existing["registration_seq"]) != registration_seq
                or int(existing["m_before"]) != m_before
                or int(existing["m_after"]) != m_before + 18
                or str(existing["registration_delta_digest"])
                != delta["artifact_digest"]
                or str(existing["registration_head_digest"])
                != new_head["artifact_digest"]
            ):
                raise IsolatedMainlineError("atomic_registration_resume_changed")
            persisted_registration_artifacts = [
                dict(
                    zip(
                        (
                            "artifact_digest",
                            "artifact_type",
                            "artifact_json",
                            "parent_digests_json",
                            "registered_at",
                        ),
                        item,
                        strict=True,
                    )
                )
                for item in cursor.execute(
                    "SELECT artifact_digest,artifact_type,artifact_json,"
                    "parent_digests_json,registered_at FROM "
                    "m4_isolated_v11.multiplicity_registration_artifacts "
                    "WHERE registration_seq=%s ORDER BY "
                    "CASE artifact_type "
                    "WHEN 'M4IsolatedCandidateRegistrationV11' THEN 0 "
                    "WHEN 'M4IsolatedMultiplicityRegistrationDeltaV11' THEN 1 "
                    "ELSE 2 END, artifact_digest",
                    (registration_seq,),
                ).fetchall()
            ]
            by_digest = {
                str(item["artifact_digest"]): item
                for item in persisted_registration_artifacts
            }
            if len(by_digest) != len(expected_registration_artifacts) or set(
                by_digest
            ) != {
                str(item["artifact_digest"]) for item in expected_registration_artifacts
            }:
                raise IsolatedMainlineError("atomic_registration_artifact_set_changed")
            for expected_artifact in expected_registration_artifacts:
                persisted = by_digest[expected_artifact["artifact_digest"]]
                if (
                    persisted["artifact_type"] != expected_artifact["artifact_type"]
                    or dict(persisted["artifact_json"]) != expected_artifact
                    or list(persisted["parent_digests_json"])
                    != expected_artifact["parent_digests"]
                    or not _same_aware_timestamp_instant(
                        persisted["registered_at"], registration_created_at
                    )
                ):
                    raise IsolatedMainlineError(
                        "atomic_registration_artifact_content_changed"
                    )
        execution_id = str(self._active_execution_id or "")
        if not execution_id:
            raise IsolatedMainlineError("search_execution_identity_missing")
        job_by_id = {job.candidate_id: job for job in jobs}
        retryable_reasons = {
            "P3_PREEMPTED",
            "WORKER_PROCESS_CRASH",
            "WALL_TIMEOUT",
        }
        now_utc = datetime.now(UTC)
        with (
            self.repository.connection_factory() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            attempt_rows = [
                dict(item)
                for item in cursor.execute(
                    "SELECT execution_attempt_id,candidate_id,retry_ordinal,"
                    "lease_owner,lease_acquired_at,heartbeat_at,worker_started_at,"
                    "terminal_at,status,reason,attempt_payload_json,artifact_digest,"
                    "artifact_committed FROM m4_isolated_v11.execution_attempts "
                    "WHERE candidate_id=ANY(%s) ORDER BY candidate_id,retry_ordinal",
                    ([job.candidate_id for job in jobs],),
                ).fetchall()
            ]
            for row in attempt_rows:
                if row["status"] != "LEASED":
                    continue
                heartbeat = row["heartbeat_at"]
                if heartbeat is None or heartbeat >= now_utc - timedelta(
                    seconds=contract.LEASE_STALE_AFTER_SECONDS
                ):
                    raise IsolatedMainlineError("candidate_lease_not_stale")
                candidate_id = str(row["candidate_id"])
                retry_ordinal = int(row["retry_ordinal"])
                job = job_by_id.get(candidate_id)
                if job is None:
                    raise IsolatedMainlineError("candidate_lease_identity_changed")
                if row["worker_started_at"] is None:
                    cursor.execute(
                        "DELETE FROM m4_isolated_v11.execution_attempts "
                        "WHERE execution_attempt_id=%s AND status='LEASED'",
                        (row["execution_attempt_id"],),
                    )
                    cursor.execute(
                        "UPDATE m4_isolated_v11.candidate_registrations SET "
                        "state='REGISTERED',lease_owner=NULL,lease_token=NULL,"
                        "retry_cursor=NULL,lease_acquired_at=NULL,heartbeat_at=NULL,"
                        "worker_started_at=NULL WHERE candidate_id=%s "
                        "AND state='LEASED'",
                        (candidate_id,),
                    )
                    continue
                recovered = search.CandidateOutcome(
                    candidate_id=candidate_id,
                    configuration_id=job.configuration.configuration_id,
                    seed_ordinal=job.seed_ordinal,
                    seed_hex=job.seed_hex,
                    status="FAILED",
                    primary_mean=0.0,
                    block_means=(0.0, 0.0, 0.0),
                    fold_values=(),
                    error_code="WORKER_PROCESS_CRASH",
                )
                cursor.execute(
                    "UPDATE m4_isolated_v11.execution_attempts SET "
                    "terminal_at=%s,status='FAILED',reason='WORKER_PROCESS_CRASH',"
                    "attempt_payload_json=%s::jsonb WHERE execution_attempt_id=%s "
                    "AND status='LEASED'",
                    (
                        now_utc,
                        json.dumps(_candidate_outcome_payload(recovered)),
                        row["execution_attempt_id"],
                    ),
                )
                if retry_ordinal < 2:
                    cursor.execute(
                        "UPDATE m4_isolated_v11.candidate_registrations SET "
                        "state='REGISTERED',lease_owner=NULL,lease_token=NULL,"
                        "retry_cursor=NULL,lease_acquired_at=NULL,heartbeat_at=NULL,"
                        "worker_started_at=NULL WHERE candidate_id=%s",
                        (candidate_id,),
                    )
                else:
                    cursor.execute(
                        "UPDATE m4_isolated_v11.candidate_registrations SET "
                        "state='TERMINAL' WHERE candidate_id=%s",
                        (candidate_id,),
                    )
            attempt_rows = [
                dict(item)
                for item in cursor.execute(
                    "SELECT execution_attempt_id,candidate_id,retry_ordinal,"
                    "lease_owner,lease_acquired_at,heartbeat_at,worker_started_at,"
                    "terminal_at,status,reason,attempt_payload_json,artifact_digest,"
                    "artifact_committed FROM m4_isolated_v11.execution_attempts "
                    "WHERE candidate_id=ANY(%s) ORDER BY candidate_id,retry_ordinal",
                    ([job.candidate_id for job in jobs],),
                ).fetchall()
            ]
        initial_attempts: list[search.CandidateAttemptOutcome] = []
        initial_outcomes: dict[str, search.CandidateOutcome] = {}
        initial_retry_ordinals: dict[str, int] = {}
        rows_by_candidate: dict[str, list[dict[str, Any]]] = {
            job.candidate_id: [] for job in jobs
        }
        for row in attempt_rows:
            candidate_id = str(row["candidate_id"])
            if candidate_id not in rows_by_candidate or row["status"] == "LEASED":
                raise IsolatedMainlineError("attempt_resume_state_changed")
            rows_by_candidate[candidate_id].append(row)
        for job in jobs:
            rows = rows_by_candidate[job.candidate_id]
            if [int(item["retry_ordinal"]) for item in rows] != list(range(len(rows))):
                raise IsolatedMainlineError("attempt_resume_sequence_changed")
            for row in rows:
                expected_id = contract.domain_digest(
                    [job.candidate_id, int(row["retry_ordinal"])],
                    domain="dehps.m4.isolated-24h-challenger.execution-attempt.v11",
                )
                payload = row["attempt_payload_json"]
                if (
                    str(row["execution_attempt_id"]) != expected_id
                    or not isinstance(payload, dict)
                    or bool(row["artifact_committed"])
                    or row["artifact_digest"] is not None
                ):
                    raise IsolatedMainlineError("attempt_resume_integrity_changed")
                outcome = _candidate_outcome_from_payload(job, payload)
                trace = search.CandidateAttemptOutcome(
                    candidate_id=job.candidate_id,
                    retry_ordinal=int(row["retry_ordinal"]),
                    status=str(row["status"]),
                    reason=None if row["reason"] is None else str(row["reason"]),
                )
                if trace.status != outcome.status or trace.reason != outcome.error_code:
                    raise IsolatedMainlineError("attempt_resume_outcome_changed")
                initial_attempts.append(trace)
            if not rows:
                initial_retry_ordinals[job.candidate_id] = 0
                continue
            last_row = rows[-1]
            last_outcome = _candidate_outcome_from_payload(
                job, last_row["attempt_payload_json"]
            )
            retry_ordinal = int(last_row["retry_ordinal"])
            if (
                last_outcome.status == "FAILED"
                and last_outcome.error_code in retryable_reasons
                and retry_ordinal < 2
            ):
                initial_retry_ordinals[job.candidate_id] = retry_ordinal + 1
            else:
                initial_outcomes[job.candidate_id] = last_outcome

        thermal_guard = ThermalGuard(root_dir=self.root_dir)

        def wait_for_resource_guards() -> bool:
            return thermal_guard.wait_until_ready() and _wait_formal_p3_quiescence(
                seconds=contract.FORMAL_P3_QUIESCENCE_SECONDS
            )

        def resource_preemption_reason() -> str | None:
            if not _formal_p3_quiescent():
                return "P3_PREEMPTED"
            return thermal_guard.preemption_reason()

        def lease_attempts(
            leases: tuple[tuple[search.CandidateJob, int], ...],
        ) -> None:
            if not wait_for_resource_guards():
                raise IsolatedMainlineError("RESOURCE_GUARD_TRIGGERED")
            acquired = datetime.now(UTC)
            with (
                self.repository.connection_factory() as connection,
                connection.cursor() as cursor,
            ):
                for job, retry_ordinal in leases:
                    attempt_id = contract.domain_digest(
                        [job.candidate_id, retry_ordinal],
                        domain=(
                            "dehps.m4.isolated-24h-challenger.execution-attempt.v11"
                        ),
                    )
                    lease_token = contract.domain_digest(
                        [execution_id, job.candidate_id, retry_ordinal],
                        domain="dehps.m4.isolated-24h-challenger.lease.v11",
                    )
                    updated = cursor.execute(
                        "UPDATE m4_isolated_v11.candidate_registrations SET "
                        "state='LEASED',lease_owner=%s,lease_token=%s,retry_cursor=%s,"
                        "lease_acquired_at=%s,heartbeat_at=%s,worker_started_at=NULL "
                        "WHERE candidate_id=%s AND state='REGISTERED'",
                        (
                            execution_id,
                            lease_token,
                            retry_ordinal,
                            acquired,
                            acquired,
                            job.candidate_id,
                        ),
                    )
                    if updated.rowcount != 1:
                        raise IsolatedMainlineError("candidate_lease_state_changed")
                    inserted = cursor.execute(
                        "INSERT INTO m4_isolated_v11.execution_attempts ("
                        "execution_attempt_id,candidate_id,retry_ordinal,lease_owner,"
                        "lease_acquired_at,heartbeat_at,status,artifact_committed) "
                        "VALUES (%s,%s,%s,%s,%s,%s,'LEASED',FALSE) "
                        "ON CONFLICT (execution_attempt_id) DO NOTHING",
                        (
                            attempt_id,
                            job.candidate_id,
                            retry_ordinal,
                            execution_id,
                            acquired,
                            acquired,
                        ),
                    )
                    if inserted.rowcount != 1:
                        raise IsolatedMainlineError("candidate_attempt_lease_changed")

        def acknowledge_started(
            leases: tuple[tuple[search.CandidateJob, int], ...],
        ) -> None:
            started_at = datetime.now(UTC)
            with (
                self.repository.connection_factory() as connection,
                connection.cursor() as cursor,
            ):
                for job, retry_ordinal in leases:
                    attempt_id = contract.domain_digest(
                        [job.candidate_id, retry_ordinal],
                        domain=(
                            "dehps.m4.isolated-24h-challenger.execution-attempt.v11"
                        ),
                    )
                    updated = cursor.execute(
                        "UPDATE m4_isolated_v11.execution_attempts SET "
                        "worker_started_at=%s,heartbeat_at=%s "
                        "WHERE execution_attempt_id=%s AND status='LEASED' "
                        "AND worker_started_at IS NULL",
                        (started_at, started_at, attempt_id),
                    )
                    if updated.rowcount != 1:
                        raise IsolatedMainlineError("worker_start_ack_changed")
                    registration_updated = cursor.execute(
                        "UPDATE m4_isolated_v11.candidate_registrations SET "
                        "worker_started_at=%s,heartbeat_at=%s WHERE candidate_id=%s "
                        "AND state='LEASED' AND retry_cursor=%s "
                        "AND worker_started_at IS NULL",
                        (started_at, started_at, job.candidate_id, retry_ordinal),
                    )
                    if registration_updated.rowcount != 1:
                        raise IsolatedMainlineError(
                            "candidate_worker_start_ack_changed"
                        )

        def release_unstarted(
            leases: tuple[tuple[search.CandidateJob, int], ...],
        ) -> None:
            with (
                self.repository.connection_factory() as connection,
                connection.cursor() as cursor,
            ):
                for job, retry_ordinal in leases:
                    attempt_id = contract.domain_digest(
                        [job.candidate_id, retry_ordinal],
                        domain=(
                            "dehps.m4.isolated-24h-challenger.execution-attempt.v11"
                        ),
                    )
                    deleted = cursor.execute(
                        "DELETE FROM m4_isolated_v11.execution_attempts "
                        "WHERE execution_attempt_id=%s AND status='LEASED' "
                        "AND worker_started_at IS NULL",
                        (attempt_id,),
                    )
                    if deleted.rowcount != 1:
                        raise IsolatedMainlineError("unstarted_attempt_release_changed")
                    released = cursor.execute(
                        "UPDATE m4_isolated_v11.candidate_registrations SET "
                        "state='REGISTERED',lease_owner=NULL,lease_token=NULL,"
                        "retry_cursor=NULL,lease_acquired_at=NULL,heartbeat_at=NULL,"
                        "worker_started_at=NULL WHERE candidate_id=%s "
                        "AND state='LEASED' AND retry_cursor=%s "
                        "AND worker_started_at IS NULL",
                        (job.candidate_id, retry_ordinal),
                    )
                    if released.rowcount != 1:
                        raise IsolatedMainlineError(
                            "unstarted_candidate_release_changed"
                        )

        def heartbeat_attempts(
            leases: tuple[tuple[search.CandidateJob, int], ...],
        ) -> None:
            heartbeat = datetime.now(UTC)
            ids = [
                contract.domain_digest(
                    [job.candidate_id, retry_ordinal],
                    domain="dehps.m4.isolated-24h-challenger.execution-attempt.v11",
                )
                for job, retry_ordinal in leases
            ]
            with (
                self.repository.connection_factory() as connection,
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    "UPDATE m4_isolated_v11.execution_attempts SET heartbeat_at=%s "
                    "WHERE execution_attempt_id=ANY(%s) AND status='LEASED'",
                    (heartbeat, ids),
                )
                cursor.execute(
                    "UPDATE m4_isolated_v11.candidate_registrations SET "
                    "heartbeat_at=%s WHERE candidate_id=ANY(%s) AND state='LEASED'",
                    (heartbeat, [job.candidate_id for job, _ in leases]),
                )

        def terminal_attempt(
            job: search.CandidateJob,
            trace: search.CandidateAttemptOutcome,
            outcome: search.CandidateOutcome | None,
        ) -> None:
            terminal_at = datetime.now(UTC)
            final_outcome = outcome or search.CandidateOutcome(
                candidate_id=job.candidate_id,
                configuration_id=job.configuration.configuration_id,
                seed_ordinal=job.seed_ordinal,
                seed_hex=job.seed_hex,
                status="FAILED",
                primary_mean=0.0,
                block_means=(0.0, 0.0, 0.0),
                fold_values=(),
                error_code=trace.reason,
            )
            attempt_id = contract.domain_digest(
                [job.candidate_id, trace.retry_ordinal],
                domain="dehps.m4.isolated-24h-challenger.execution-attempt.v11",
            )
            retryable = trace.reason in retryable_reasons and trace.retry_ordinal < 2
            with (
                self.repository.connection_factory() as connection,
                connection.cursor() as cursor,
            ):
                updated = cursor.execute(
                    "UPDATE m4_isolated_v11.execution_attempts SET terminal_at=%s,"
                    "heartbeat_at=%s,status=%s,reason=%s,attempt_payload_json=%s::jsonb "
                    "WHERE execution_attempt_id=%s AND status='LEASED' "
                    "AND worker_started_at IS NOT NULL",
                    (
                        terminal_at,
                        terminal_at,
                        trace.status,
                        trace.reason,
                        json.dumps(_candidate_outcome_payload(final_outcome)),
                        attempt_id,
                    ),
                )
                if updated.rowcount != 1:
                    raise IsolatedMainlineError("terminal_attempt_state_changed")
                if retryable:
                    cursor.execute(
                        "UPDATE m4_isolated_v11.candidate_registrations SET "
                        "state='REGISTERED',lease_owner=NULL,lease_token=NULL,"
                        "retry_cursor=NULL,lease_acquired_at=NULL,heartbeat_at=NULL,"
                        "worker_started_at=NULL WHERE candidate_id=%s "
                        "AND state='LEASED'",
                        (job.candidate_id,),
                    )
                else:
                    cursor.execute(
                        "UPDATE m4_isolated_v11.candidate_registrations SET "
                        "state='TERMINAL',heartbeat_at=%s WHERE candidate_id=%s "
                        "AND state='LEASED'",
                        (terminal_at, job.candidate_id),
                    )

        outcomes, attempt_outcomes = search.execute_history_jobs_with_retries(
            jobs,
            history=history,
            activity_probe=_formal_p3_quiescent,
            quiescence_waiter=wait_for_resource_guards,
            initial_outcomes=initial_outcomes,
            initial_attempts=initial_attempts,
            initial_retry_ordinals=initial_retry_ordinals,
            on_lease=lease_attempts,
            on_started=acknowledge_started,
            on_unstarted=release_unstarted,
            on_heartbeat=heartbeat_attempts,
            on_attempt=terminal_attempt,
            preemption_reason_probe=resource_preemption_reason,
        )
        with (
            self.repository.connection_factory() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            terminal_rows = [
                dict(item)
                for item in cursor.execute(
                    "SELECT execution_attempt_id,candidate_id,retry_ordinal,"
                    "worker_started_at,terminal_at,status,reason,attempt_payload_json,"
                    "artifact_digest,artifact_committed FROM "
                    "m4_isolated_v11.execution_attempts WHERE candidate_id=ANY(%s) "
                    "ORDER BY candidate_id,retry_ordinal",
                    ([job.candidate_id for job in jobs],),
                ).fetchall()
            ]
            candidate_states = {
                str(item["candidate_id"]): str(item["state"])
                for item in cursor.execute(
                    "SELECT candidate_id,state FROM "
                    "m4_isolated_v11.candidate_registrations "
                    "WHERE candidate_id=ANY(%s)",
                    ([job.candidate_id for job in jobs],),
                ).fetchall()
            }
        attempt_metadata = {
            str(item["execution_attempt_id"]): item for item in terminal_rows
        }
        if (
            len(attempt_metadata) != len(attempt_outcomes)
            or set(candidate_states) != {job.candidate_id for job in jobs}
            or set(candidate_states.values()) != {"TERMINAL"}
        ):
            raise IsolatedMainlineError("terminal_attempt_ledger_incomplete")
        attempt_records: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []
        attempts_by_candidate: dict[str, list[dict[str, Any]]] = {
            job.candidate_id: [] for job in jobs
        }
        job_by_id = {job.candidate_id: job for job in jobs}
        registration_by_id = {
            job.candidate_id: registration
            for job, registration in zip(jobs, registrations, strict=True)
        }
        slot_by_id = {job.candidate_id: slot for slot, job in enumerate(jobs)}
        for trace in attempt_outcomes:
            job = job_by_id[trace.candidate_id]
            registration = registration_by_id[trace.candidate_id]
            prior_attempts = attempts_by_candidate[trace.candidate_id]
            if trace.retry_ordinal != len(prior_attempts):
                raise IsolatedMainlineError("execution_attempt_sequence_changed")
            attempt_id = contract.domain_digest(
                [job.candidate_id, trace.retry_ordinal],
                domain="dehps.m4.isolated-24h-challenger.execution-attempt.v11",
            )
            metadata = attempt_metadata.get(attempt_id)
            if (
                metadata is None
                or metadata["worker_started_at"] is None
                or metadata["terminal_at"] is None
                or metadata["status"] != trace.status
                or metadata["reason"] != trace.reason
                or metadata["artifact_digest"] is not None
                or bool(metadata["artifact_committed"])
            ):
                raise IsolatedMainlineError("execution_attempt_ledger_changed")
            persisted_outcome = _candidate_outcome_from_payload(
                job, metadata["attempt_payload_json"]
            )
            if (
                persisted_outcome.status != trace.status
                or persisted_outcome.error_code != trace.reason
            ):
                raise IsolatedMainlineError("execution_attempt_payload_changed")
            attempt_parents = [registration["artifact_digest"]]
            if prior_attempts:
                attempt_parents.append(prior_attempts[-1]["artifact_digest"])
            attempt_parents.extend(
                (
                    preregistration["artifact_digest"],
                    history_artifact["artifact_digest"],
                    predecessor["artifact_digest"],
                )
            )
            attempt = self._build(
                artifact_type="M4IsolatedExecutionAttemptV11",
                task_key=task_key,
                target_issue=self.context["target_issue"],
                git_commit=git_commit,
                parent_digests=tuple(attempt_parents),
                type_body={
                    "execution_attempt_id": attempt_id,
                    "candidate_id": job.candidate_id,
                    "retry_ordinal": trace.retry_ordinal,
                    "status": trace.status,
                    "reason": trace.reason,
                    "worker_slot": slot_by_id[job.candidate_id],
                    "started_at": metadata["worker_started_at"].isoformat(),
                    "completed_at": metadata["terminal_at"].isoformat(),
                    "formal_p3_preempted": trace.reason == "P3_PREEMPTED",
                },
                seed=job.seed_hex,
                created_at=metadata["terminal_at"].isoformat(),
            )
            prior_attempts.append(attempt)
            attempt_records.append(attempt)
        for job, outcome, registration in zip(
            jobs, outcomes, registrations, strict=True
        ):
            candidate_attempts = attempts_by_candidate[job.candidate_id]
            if not candidate_attempts or not 1 <= len(candidate_attempts) <= 3:
                raise IsolatedMainlineError("candidate_attempt_count_changed")
            validated_attempts = search.retry_attempts(
                job, [item["body"]["reason"] for item in candidate_attempts]
            )
            if [
                item["body"]["execution_attempt_id"] for item in candidate_attempts
            ] != [item["execution_attempt_id"] for item in validated_attempts] or [
                item["body"]["status"] for item in candidate_attempts
            ] != [item["status"] for item in validated_attempts]:
                raise IsolatedMainlineError("candidate_attempt_reducer_changed")
            terminal_attempt = candidate_attempts[-1]["body"]
            if terminal_attempt["status"] != outcome.status or (
                terminal_attempt["reason"] != outcome.error_code
            ):
                raise IsolatedMainlineError("candidate_terminal_outcome_changed")
            result = self._build(
                artifact_type="M4IsolatedCandidateResultV11",
                task_key=task_key,
                target_issue=self.context["target_issue"],
                git_commit=git_commit,
                parent_digests=(
                    registration["artifact_digest"],
                    *(item["artifact_digest"] for item in candidate_attempts),
                ),
                type_body={
                    "candidate_id": job.candidate_id,
                    "configuration_id": job.configuration.configuration_id,
                    "cohort_id": search.candidate_cohort_id(job.configuration),
                    "seed_ordinal": job.seed_ordinal,
                    "ordered_attempt_ids": [
                        item["body"]["execution_attempt_id"]
                        for item in candidate_attempts
                    ],
                    "status": outcome.status,
                    "terminal_reason": outcome.error_code,
                    "fold_values_hex": [value.hex() for value in outcome.fold_values],
                    "primary_mean_hex": outcome.primary_mean.hex(),
                    "block_means_hex": [value.hex() for value in outcome.block_means],
                    "comparison_count": contract.OUTER_FOLD_COUNT,
                    "selection_count": 0,
                    "eligible": False,
                },
                seed=job.seed_hex,
                created_at=candidate_attempts[-1]["body"]["completed_at"],
            )
            results.append(result)
        cohorts: list[dict[str, Any]] = []
        for start in range(0, 18, 3):
            cohort_results = outcomes[start : start + 3]
            complete = all(item.status == "SUCCEEDED" for item in cohort_results)
            aggregate = (
                search.aggregate_seed_cohort(cohort_results) if complete else None
            )
            configuration = jobs[start].configuration
            cohorts.append(
                self._build(
                    artifact_type="M4IsolatedSeedCohortV11",
                    task_key=task_key,
                    target_issue=self.context["target_issue"],
                    git_commit=git_commit,
                    parent_digests=tuple(
                        item["artifact_digest"] for item in results[start : start + 3]
                    ),
                    type_body={
                        "cohort_id": search.candidate_cohort_id(configuration),
                        "configuration_id": configuration.configuration_id,
                        "family": configuration.family,
                        "configuration": {
                            "family": configuration.family,
                            "representation": configuration.representation,
                            "training_window": configuration.training_window,
                            "parent_configuration_id": (
                                configuration.parent_configuration_id
                            ),
                            "ordered_feature_ids": list(
                                configuration.ordered_feature_ids
                            ),
                            "ordered_hyperparameters": [
                                list(item)
                                for item in configuration.ordered_hyperparameters
                            ],
                        },
                        "epoch_date": self.context["epoch_date"],
                        "complete": complete,
                        "aggregate": aggregate,
                    },
                    created_at=max(
                        item["body"]["completed_at"]
                        for item in attempt_records
                        if item["body"]["candidate_id"]
                        in {job.candidate_id for job in jobs[start : start + 3]}
                    ),
                )
            )
        batch_completed_at = max(
            item["body"]["completed_at"] for item in attempt_records
        )
        completion_delta = self._build(
            artifact_type="M4IsolatedMultiplicityDeltaV11",
            task_key=task_key,
            target_issue=self.context["target_issue"],
            git_commit=git_commit,
            parent_digests=_ordered_unique(
                (
                    delta["artifact_digest"],
                    new_head["artifact_digest"],
                    *(item["artifact_digest"] for item in registrations),
                    *(item["artifact_digest"] for item in duplicate_records),
                    *(item["artifact_digest"] for item in results),
                    *(item["artifact_digest"] for item in attempt_records),
                )
            ),
            type_body={
                "registration_seq": registration_seq,
                "m_total": m_before + 18,
                "execution_attempt_count": len(attempt_records),
                "candidate_result_count": len(results),
                "retry_count": len(attempt_records) - contract.ATTEMPTS_PER_BATCH,
            },
            created_at=batch_completed_at,
        )
        batch_parents = _ordered_unique(
            (
                preregistration["artifact_digest"],
                projection["artifact_digest"],
                history_artifact["artifact_digest"],
                predecessor["artifact_digest"],
                delta["artifact_digest"],
                new_head["artifact_digest"],
                *(item["artifact_digest"] for item in registrations),
                *(item["artifact_digest"] for item in duplicate_records),
                *(item["artifact_digest"] for item in attempt_records),
                *(item["artifact_digest"] for item in results),
                *(item["artifact_digest"] for item in cohorts),
                completion_delta["artifact_digest"],
            )
        )
        batch = self._build(
            artifact_type="M4IsolatedSearchBatchV11",
            task_key=task_key,
            target_issue=self.context["target_issue"],
            git_commit=git_commit,
            parent_digests=batch_parents,
            type_body={
                "batch_seq": batch_seq,
                "batch_plan_digest": batch_plan_digest,
                "batch_plan": batch_plan,
                "m_before": m_before,
                "m_after": m_before + 18,
                "candidate_count": 18,
                "attempt_count": len(attempt_records),
                "cohort_count": 6,
                "worker_count": contract.WORKER_COUNT,
                "merge_order": "candidate_id",
                "formal_p3_mutated": False,
            },
            created_at=batch_completed_at,
        )
        return (
            *registrations,
            delta,
            new_head,
            *duplicate_records,
            *attempt_records,
            *results,
            *cohorts,
            completion_delta,
            batch,
        )

    def _search_checkpoint(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        batch_values = self._upstream("search_batch")
        batch = _unique_type(batch_values, "M4IsolatedSearchBatchV11")
        batch_replay = _unique_type(
            self._upstream("search_batch_replay"), "M4IsolatedSearchBatchReplayV11"
        )
        multiplicity = _unique_type(batch_values, "M4IsolatedMultiplicityDeltaV11")
        cohorts = sorted(
            (
                item
                for item in batch_values
                if item["artifact_type"] == "M4IsolatedSeedCohortV11"
            ),
            key=lambda item: str(item["body"]["configuration_id"]),
        )
        if len(cohorts) != contract.CONFIGURATIONS_PER_BATCH:
            raise IsolatedMainlineError("checkpoint_cohort_count_changed")
        batch_seq = int(self.context["batch_seq"])
        predecessor = _unique_type(
            self._previous_checkpoint(), "M4IsolatedSearchCheckpointV11"
        )
        batch_plan = batch["body"].get("batch_plan")
        if not isinstance(batch_plan, dict) or contract.domain_digest(
            batch_plan,
            domain="dehps.m4.isolated-24h-challenger.batch-plan.v11",
        ) != batch["body"].get("batch_plan_digest"):
            raise IsolatedMainlineError("checkpoint_batch_plan_changed")
        previous_cohorts = (
            list(predecessor["body"].get("cohorts", []))
            if predecessor["body"].get("target_issue") == self.context["target_issue"]
            else []
        )
        current_cohorts = [
            {"artifact_digest": item["artifact_digest"], "body": item["body"]}
            for item in cohorts
        ]
        cumulative_cohorts = [*previous_cohorts, *current_cohorts]
        configuration_ids = [
            str(item["body"]["configuration_id"]) for item in cumulative_cohorts
        ]
        if len(configuration_ids) != len(set(configuration_ids)):
            raise IsolatedMainlineError("checkpoint_cohort_identity_changed")
        return (
            self._build(
                artifact_type="M4IsolatedSearchCheckpointV11",
                task_key=task_key,
                target_issue=self.context["target_issue"],
                git_commit=git_commit,
                parent_digests=(
                    predecessor["artifact_digest"],
                    batch["artifact_digest"],
                    batch_replay["artifact_digest"],
                    multiplicity["artifact_digest"],
                ),
                type_body={
                    "batch_seq": batch_seq,
                    "epoch_date": self.context["epoch_date"],
                    "base_cursor": int(batch_plan["base_cursor_after"]),
                    "adaptive_cursor": int(batch_plan["adaptive_cursor_after"]),
                    "m_total": multiplicity["body"]["m_total"],
                    "cohorts": cumulative_cohorts,
                    "batch_replay_verified": True,
                    "status": "SEALED",
                },
            ),
        )

    def _cut_registration_head(
        self,
        *,
        cutoff: datetime,
        genesis_head: Mapping[str, Any],
    ) -> dict[str, Any]:
        if cutoff.tzinfo is None:
            raise IsolatedMainlineError("multiplicity_cutoff_not_aware")
        parsed_genesis = artifacts.validate_artifact(genesis_head)
        if (
            parsed_genesis["artifact_type"] != "M4IsolatedEmptyMultiplicityHeadV11"
            or parsed_genesis["body"].get("registration_seq") != -1
            or parsed_genesis["body"].get("m_total") != 0
        ):
            raise IsolatedMainlineError("multiplicity_genesis_identity_changed")
        with (
            self.repository.connection_factory() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            batch_rows = [
                dict(item)
                for item in cursor.execute(
                    "SELECT registration_seq,batch_seq,batch_plan_digest,"
                    "predecessor_head_digest,registration_delta_digest,"
                    "registration_head_digest,m_before,m_after,candidate_count,"
                    "committed_at FROM m4_isolated_v11.registration_batches "
                    "WHERE committed_at<=%s ORDER BY registration_seq",
                    (cutoff,),
                ).fetchall()
            ]
            artifact_rows = [
                dict(item)
                for item in cursor.execute(
                    "SELECT artifact_digest,registration_seq,artifact_type,"
                    "artifact_json,parent_digests_json,registered_at FROM "
                    "m4_isolated_v11.multiplicity_registration_artifacts "
                    "WHERE registered_at<=%s ORDER BY registration_seq,"
                    "artifact_type,artifact_digest",
                    (cutoff,),
                ).fetchall()
            ]
        grouped: dict[int, list[dict[str, Any]]] = {}
        for raw in artifact_rows:
            grouped.setdefault(int(raw["registration_seq"]), []).append(raw)
        if set(grouped) != {int(item["registration_seq"]) for item in batch_rows}:
            raise IsolatedMainlineError("multiplicity_cut_registration_set_changed")
        previous_head_digest = parsed_genesis["artifact_digest"]
        expected_m_before = 0
        latest_head = dict(parsed_genesis)
        for expected_registration_seq, batch_row in enumerate(batch_rows):
            registration_seq = int(batch_row["registration_seq"])
            committed_at = batch_row["committed_at"]
            if (
                registration_seq != expected_registration_seq
                or int(batch_row["candidate_count"]) != contract.ATTEMPTS_PER_BATCH
                or int(batch_row["m_before"]) != expected_m_before
                or int(batch_row["m_after"])
                != expected_m_before + contract.ATTEMPTS_PER_BATCH
                or str(batch_row["predecessor_head_digest"]) != previous_head_digest
                or committed_at > cutoff
            ):
                raise IsolatedMainlineError("MULTIPLICITY_LEDGER_INCOMPLETE")
            registered = grouped.get(registration_seq, [])
            parsed: list[dict[str, Any]] = []
            for row in registered:
                payload = artifacts.validate_artifact(dict(row["artifact_json"]))
                if (
                    payload["artifact_digest"] != row["artifact_digest"]
                    or payload["artifact_type"] != row["artifact_type"]
                    or payload["parent_digests"] != list(row["parent_digests_json"])
                    or row["registered_at"] != committed_at
                ):
                    raise IsolatedMainlineError(
                        "multiplicity_cut_registration_content_changed"
                    )
                parsed.append(payload)
            registrations = sorted(
                (
                    item
                    for item in parsed
                    if item["artifact_type"] == "M4IsolatedCandidateRegistrationV11"
                ),
                key=lambda item: int(item["body"].get("slot_ordinal", -1)),
            )
            deltas = [
                item
                for item in parsed
                if item["artifact_type"] == "M4IsolatedMultiplicityRegistrationDeltaV11"
            ]
            heads = [
                item
                for item in parsed
                if item["artifact_type"] == "M4IsolatedMultiplicityRegistrationHeadV11"
            ]
            ordered_candidate_ids = [
                str(item["body"].get("candidate_id")) for item in registrations
            ]
            if (
                len(parsed) != 20
                or len(registrations) != contract.ATTEMPTS_PER_BATCH
                or [int(item["body"].get("slot_ordinal", -1)) for item in registrations]
                != list(range(contract.ATTEMPTS_PER_BATCH))
                or len(set(ordered_candidate_ids)) != contract.ATTEMPTS_PER_BATCH
                or len(deltas) != 1
                or len(heads) != 1
            ):
                raise IsolatedMainlineError(
                    "multiplicity_cut_registration_artifacts_incomplete"
                )
            delta = deltas[0]
            head = heads[0]
            committed_iso = committed_at.isoformat()
            if (
                delta["artifact_digest"] != batch_row["registration_delta_digest"]
                or head["artifact_digest"] != batch_row["registration_head_digest"]
                or any(
                    item["body"].get("batch_plan_digest")
                    != batch_row["batch_plan_digest"]
                    or int(item["body"].get("batch_seq", -1))
                    != int(batch_row["batch_seq"])
                    or item["body"].get("registry_state") != "REGISTERED"
                    or item["body"].get("status") != "REGISTERED"
                    for item in registrations
                )
                or delta["parent_digests"]
                != [
                    previous_head_digest,
                    *(item["artifact_digest"] for item in registrations),
                ]
                or delta["body"]
                != {
                    "registration_seq": registration_seq,
                    "batch_seq": int(batch_row["batch_seq"]),
                    "m_before": expected_m_before,
                    "ordered_candidate_ids": ordered_candidate_ids,
                    "m_after": expected_m_before + contract.ATTEMPTS_PER_BATCH,
                    "committed_at": committed_iso,
                }
                or head["parent_digests"]
                != [previous_head_digest, delta["artifact_digest"]]
                or head["body"]
                != {
                    "registration_seq": registration_seq,
                    "m_total": expected_m_before + contract.ATTEMPTS_PER_BATCH,
                    "delta_digest": delta["artifact_digest"],
                    "committed_at": committed_iso,
                }
            ):
                raise IsolatedMainlineError(
                    "multiplicity_cut_registration_chain_changed"
                )
            previous_head_digest = head["artifact_digest"]
            expected_m_before += contract.ATTEMPTS_PER_BATCH
            latest_head = head
        return latest_head

    def _multiplicity_seal(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        projection = _unique_type(
            self._upstream("target_issue_projection"),
            "M4IsolatedTargetIssueProjectionV11",
        )
        history = _unique_type(
            self._upstream("history_snapshot"), "M4IsolatedHistorySnapshotV11"
        )
        checkpoint = _unique_type(
            self._upstream("search_checkpoint"), "M4IsolatedSearchCheckpointV11"
        )
        checkpoint_replay = _unique_type(
            self._upstream("search_checkpoint_replay"),
            "M4IsolatedSearchCheckpointReplayV11",
        )
        genesis_head = _unique_type(
            self._upstream("genesis"), "M4IsolatedEmptyMultiplicityHeadV11"
        )
        preregistration = _unique_type(
            self._upstream("preregistration"), "M4IsolatedPreregistrationV11"
        )
        cutoff = contract.schedule_for_issue(
            self.context["target_issue"],
            target_draw_date=self.context["target_draw_date"],
        )["selection_cutoff"]
        head = self._cut_registration_head(
            cutoff=cutoff,
            genesis_head=genesis_head,
        )
        cut_checkpoint_ref = self.context["cut_checkpoint_ref"]
        expected_batch_seq = (
            -1 if cut_checkpoint_ref == "GENESIS" else int(cut_checkpoint_ref)
        )
        if (
            checkpoint["body"].get("batch_seq") != expected_batch_seq
            or checkpoint_replay["body"].get("replayed_artifact_digest")
            != checkpoint["artifact_digest"]
            or int(checkpoint["body"].get("m_total", -1)) > int(head["body"]["m_total"])
        ):
            raise IsolatedMainlineError("multiplicity_scientific_cut_changed")
        return (
            self._build(
                artifact_type="M4IsolatedMultiplicitySealV11",
                task_key=task_key,
                target_issue=self.context["target_issue"],
                git_commit=git_commit,
                parent_digests=(
                    projection["artifact_digest"],
                    history["artifact_digest"],
                    checkpoint["artifact_digest"],
                    checkpoint_replay["artifact_digest"],
                    head["artifact_digest"],
                    preregistration["artifact_digest"],
                ),
                type_body={
                    "cutoff": cutoff.isoformat(),
                    "cut_checkpoint_ref": cut_checkpoint_ref,
                    "checkpoint_digest": checkpoint["artifact_digest"],
                    "checkpoint_replay_digest": checkpoint_replay["artifact_digest"],
                    "registration_head_digest": head["artifact_digest"],
                    "m_total": head["body"]["m_total"],
                    "scientific_and_multiplicity_cuts_independent": True,
                },
            ),
        )

    @staticmethod
    def _cohort_selection_record(
        cohort: Mapping[str, Any], *, m_total: int
    ) -> dict[str, Any]:
        body = cohort["body"]
        aggregate = body.get("aggregate")
        if not body.get("complete") or not isinstance(aggregate, dict):
            return {
                "cohort_id": body["cohort_id"],
                "configuration_id": body["configuration_id"],
                "eligible": False,
                "reason": "SEED_COHORT_INCOMPLETE",
            }
        folds = tuple(
            float.fromhex(value) for value in aggregate["averaged_fold_values_hex"]
        )
        mean = math.fsum(folds) / len(folds)
        variance = math.fsum((value - mean) ** 2 for value in folds) / (len(folds) - 1)
        standard_error = math.sqrt(max(0.0, variance) / len(folds))
        alpha = 0.05 / max(1, m_total)
        z_value = statistics.NormalDist().inv_cdf(1.0 - alpha)
        lcb = mean - z_value * standard_error
        eligible = bool(aggregate["seed_gate_pass"] and mean > 0.0 and lcb > 0.0)
        configuration = body["configuration"]
        complexity = (
            len(configuration["ordered_feature_ids"]) * 4
            + (
                int(dict(configuration["ordered_hyperparameters"]).get("max_depth", 0))
                * 20
            )
            + (
                int(
                    dict(configuration["ordered_hyperparameters"]).get(
                        "active_component_count", 0
                    )
                )
                * 100
            )
        )
        return {
            "cohort_id": body["cohort_id"],
            "configuration_id": body["configuration_id"],
            "cohort_artifact_digest": cohort["artifact_digest"],
            "eligible": eligible,
            "reason": "ELIGIBLE" if eligible else "HISTORICAL_GATE_FAILED",
            "multiplicity_penalized_lcb": lcb,
            "minimum_block_mean": min(
                float.fromhex(value)
                for value in body["aggregate"].get("block_means_hex", [])
            )
            if body["aggregate"].get("block_means_hex")
            else min(
                math.fsum(folds[offset : offset + 100]) / 100.0
                for offset in (0, 100, 200)
            ),
            "full_300_primary_mean": mean,
            "top100_union_size": 33,
            "mean_pairwise_jaccard": 1.0,
            "complexity_cost": complexity,
            "configuration": configuration,
        }

    def _eligibility(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        history = _unique_type(
            self._upstream("history_snapshot"), "M4IsolatedHistorySnapshotV11"
        )
        seal = _unique_type(
            self._upstream("multiplicity_seal"), "M4IsolatedMultiplicitySealV11"
        )
        checkpoint = _unique_type(
            self._upstream("search_checkpoint"), "M4IsolatedSearchCheckpointV11"
        )
        records = [
            self._cohort_selection_record(
                {"artifact_digest": item["artifact_digest"], "body": item["body"]},
                m_total=int(seal["body"]["m_total"]),
            )
            for item in checkpoint["body"]["cohorts"]
        ]
        records.sort(key=lambda item: str(item["configuration_id"]))
        return (
            self._build(
                artifact_type="M4IsolatedEligibilityV11",
                task_key=task_key,
                target_issue=self.context["target_issue"],
                git_commit=git_commit,
                parent_digests=_ordered_unique(
                    (
                        history["artifact_digest"],
                        seal["artifact_digest"],
                        checkpoint["artifact_digest"],
                        *(
                            str(item.get("cohort_artifact_digest"))
                            for item in records
                            if item.get("cohort_artifact_digest")
                        ),
                    )
                ),
                type_body={
                    "candidate_records": records,
                    "eligible_count": sum(bool(item["eligible"]) for item in records),
                    "selection_rule": "seed_cohort_decision_v11",
                    "all_attempts_registered": True,
                    "unresolved_integrity_incident": False,
                },
            ),
        )

    def _challenger_freeze(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        history = _unique_type(
            self._upstream("history_snapshot"), "M4IsolatedHistorySnapshotV11"
        )
        seal = _unique_type(
            self._upstream("multiplicity_seal"), "M4IsolatedMultiplicitySealV11"
        )
        eligibility = _unique_type(
            self._upstream("eligibility"), "M4IsolatedEligibilityV11"
        )
        eligible = [
            item
            for item in eligibility["body"]["candidate_records"]
            if item["eligible"]
        ]
        if not eligible:
            return (
                self._build(
                    artifact_type="M4IsolatedNoChallengerV11",
                    task_key=task_key,
                    target_issue=self.context["target_issue"],
                    git_commit=git_commit,
                    parent_digests=(
                        history["artifact_digest"],
                        seal["artifact_digest"],
                        eligibility["artifact_digest"],
                    ),
                    type_body={
                        "outcome": "NO_ELIGIBLE_CHALLENGER",
                        "eligible_count": 0,
                        "freeze_deadline": contract.schedule_for_issue(
                            self.context["target_issue"],
                            target_draw_date=self.context["target_draw_date"],
                        )["freeze_deadline"].isoformat(),
                    },
                ),
            )
        eligible.sort(
            key=lambda item: (
                -float(item["multiplicity_penalized_lcb"]),
                -float(item["minimum_block_mean"]),
                -float(item["full_300_primary_mean"]),
                -int(item["top100_union_size"]),
                float(item["mean_pairwise_jaccard"]),
                int(item["complexity_cost"]),
                str(item["configuration_id"]),
            )
        )
        selected = eligible[0]
        return (
            self._build(
                artifact_type="M4IsolatedChallengerFreezeV11",
                task_key=task_key,
                target_issue=self.context["target_issue"],
                git_commit=git_commit,
                parent_digests=(
                    history["artifact_digest"],
                    seal["artifact_digest"],
                    eligibility["artifact_digest"],
                    selected["cohort_artifact_digest"],
                ),
                type_body={
                    "outcome": "FROZEN",
                    "challenger_id": selected["cohort_id"],
                    "cohort_id": selected["cohort_id"],
                    "configuration_id": selected["configuration_id"],
                    "selected_seed_ordinal": 0,
                    "configuration": selected["configuration"],
                    "selection_tuple": {
                        key: selected[key]
                        for key in (
                            "multiplicity_penalized_lcb",
                            "minimum_block_mean",
                            "full_300_primary_mean",
                            "top100_union_size",
                            "mean_pairwise_jaccard",
                            "complexity_cost",
                        )
                    },
                    "checkpoint_digest": seal["body"]["checkpoint_digest"],
                    "frozen_before_target_result": True,
                    "replacement_allowed": False,
                },
            ),
        )

    def _baseline_freeze(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        preregistration = _unique_type(
            self._upstream("preregistration"), "M4IsolatedPreregistrationV11"
        )
        history = _unique_type(
            self._upstream("history_snapshot"), "M4IsolatedHistorySnapshotV11"
        )
        freeze = _unique_type(
            self._upstream("challenger_freeze"), "M4IsolatedChallengerFreezeV11"
        )
        target_issue = self.context["target_issue"]
        portfolios = search.baseline_set(target_issue)
        seed_rows = [
            [replicate, search.baseline_seed(target_issue, replicate)]
            for replicate in range(contract.BASELINE_REPLICATES)
        ]
        portfolio_rows = [
            [{"reds": list(reds), "blue": blue} for reds, blue in portfolio]
            for portfolio in portfolios
        ]
        return (
            self._build(
                artifact_type="M4IsolatedRandomBaselineSetV11",
                task_key=task_key,
                target_issue=target_issue,
                git_commit=git_commit,
                parent_digests=(
                    preregistration["artifact_digest"],
                    history["artifact_digest"],
                    freeze["artifact_digest"],
                ),
                type_body={
                    "identity": "ISOLATED_LEGAL_UNIFORM_100_TICKET_BASELINE_V6",
                    "replicate_count": contract.BASELINE_REPLICATES,
                    "portfolio_size": contract.PORTFOLIO_SIZE,
                    "ordered_seed_set_digest": contract.domain_digest(
                        seed_rows,
                        domain="dehps.m4.isolated-24h-challenger.baseline-seed-set.v11",
                    ),
                    "ordered_seed_rows": seed_rows,
                    "portfolios": portfolio_rows,
                    "target_result_access": "FORBIDDEN",
                },
                seed=_seed(task_key, 0),
            ),
        )

    def _prediction(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        preregistration = _unique_type(
            self._upstream("preregistration"), "M4IsolatedPreregistrationV11"
        )
        history_artifact = _unique_type(
            self._upstream("history_snapshot"), "M4IsolatedHistorySnapshotV11"
        )
        history = _history_from_artifact(history_artifact)
        freeze = _unique_type(
            self._upstream("challenger_freeze"), "M4IsolatedChallengerFreezeV11"
        )
        baseline = _unique_type(
            self._upstream("random_baseline_freeze"),
            "M4IsolatedRandomBaselineSetV11",
        )
        baseline_replay = _unique_type(
            self._upstream("random_baseline_freeze_replay"),
            "M4IsolatedRandomBaselineReplayV11",
        )
        load_registered_input(
            repository=self.repository,
            artifact_digest=self.source_digest,
            expected_artifact_type=contract.SOURCE_ARTIFACT_TYPE,
        )
        frozen = freeze["body"]
        configuration_body = frozen["configuration"]
        configuration = search.CandidateConfiguration(
            family=str(configuration_body["family"]),
            representation=str(configuration_body["representation"]),
            training_window=configuration_body["training_window"],
            ordered_feature_ids=tuple(configuration_body["ordered_feature_ids"]),
            ordered_hyperparameters=tuple(
                tuple(item) for item in configuration_body["ordered_hyperparameters"]
            ),
            snapshot_digest=str(history_artifact["body"]["history_snapshot_digest"]),
            source_contract_digest=self.source_digest,
        )
        if configuration.configuration_id != frozen["configuration_id"]:
            raise IsolatedMainlineError("frozen_configuration_reconstruction_changed")
        job = search.candidate_job(configuration, 0)
        score = search.candidate_prediction_score(
            job,
            history,
            target_issue=self.context["target_issue"],
            target_draw_date=self.context["target_draw_date"],
        )
        if configuration.family == "FEATURE_ABI32_LINEAR_RANKER":
            red_top100 = search.top_red_combinations(score)
        else:
            probabilities = search.candidate_prediction_probabilities(
                job,
                history,
                target_issue=self.context["target_issue"],
                target_draw_date=self.context["target_draw_date"],
            )
            red_top100 = search.probability_top_red_combinations(probabilities)
        tickets = search.isolated_rank_blue_portfolio(
            red_top100,
            target_issue=self.context["target_issue"],
            challenger_id=str(frozen["challenger_id"]),
        )
        return (
            self._build(
                artifact_type="M4IsolatedPredictionV11",
                task_key=task_key,
                target_issue=self.context["target_issue"],
                git_commit=git_commit,
                parent_digests=(
                    preregistration["artifact_digest"],
                    self.source_digest,
                    history_artifact["artifact_digest"],
                    freeze["artifact_digest"],
                    baseline["artifact_digest"],
                    baseline_replay["artifact_digest"],
                ),
                type_body={
                    "challenger_id": frozen["challenger_id"],
                    "cohort_id": frozen["cohort_id"],
                    "configuration_id": frozen["configuration_id"],
                    "model_summary": configuration.family,
                    "feature_summary": list(configuration.ordered_feature_ids),
                    "maximum_training_issue": history[-1].issue,
                    "checkpoint_digest": frozen["checkpoint_digest"],
                    "tickets": [
                        {"rank": rank, "reds": list(reds), "blue": blue}
                        for rank, (reds, blue) in enumerate(tickets, start=1)
                    ],
                    "ticket_count": len(tickets),
                    "hypothetical_cost_cny": "200.00",
                    "target_result_access": "FORBIDDEN",
                    "formal_p3_mutated": False,
                    "promotion_triggered": False,
                },
                seed=_seed(task_key, 0),
            ),
        )

    def _audited_draw(self) -> dict[str, Any]:
        issue = self.context["target_issue"]
        with (
            self.repository.connection_factory() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            rows = cursor.execute(
                "SELECT issue,draw_date,red_numbers,blue_number,source "
                "FROM ssq_history WHERE issue=%s",
                (issue,),
            ).fetchall()
        if len(rows) != 1:
            raise IsolatedMainlineError("audited_draw_not_unique")
        row = dict(rows[0])
        response = requests.get(
            "https://jc.zhcw.com/port/client_json.php",
            params={
                "transactionType": "10001001",
                "lotteryId": "1",
                "type": 1,
                "pageNum": 1,
                "pageSize": 10,
                "issueCount": 0,
                "startIssue": issue,
                "endIssue": issue,
                "startDate": "",
                "endDate": "",
                "tt": time.time(),
            },
            headers={
                "Referer": "https://www.zhcw.com/kjxx/ssq/",
                "User-Agent": os.environ.get(
                    "SSQ_CRAWLER_USER_AGENT", "DEHPS/1.0 (+local research)"
                ),
            },
            timeout=float(os.environ.get("SSQ_CRAWLER_TIMEOUT_SECONDS", "20")),
        )
        response.raise_for_status()
        response_payload = response.json()
        if not isinstance(response_payload, dict) or response_payload.get(
            "resCode"
        ) not in {None, "000000"}:
            raise IsolatedMainlineError("official_payout_not_available")
        matches = [
            dict(item)
            for item in response_payload.get("data", [])
            if isinstance(item, Mapping)
            and str(item.get("issue") or item.get("code") or item.get("term") or "")
            == issue
        ]
        if len(matches) != 1:
            raise IsolatedMainlineError("official_payout_not_unique")
        remote = matches[0]
        remote_issue = str(
            remote.get("issue") or remote.get("code") or remote.get("term") or ""
        )
        red_raw = (
            remote.get("red")
            or remote.get("red_numbers")
            or remote.get("redBalls")
            or remote.get("frontWinningNum")
        )
        blue_raw = (
            remote.get("blue")
            or remote.get("blue_number")
            or remote.get("blueBall")
            or remote.get("backWinningNum")
        )
        remote_reds = tuple(
            int(item)
            for item in (
                red_raw.replace(",", " ").split()
                if isinstance(red_raw, str)
                else red_raw or ()
            )
        )
        details = remote.get("winnerDetails")
        if (
            remote_issue != issue
            or tuple(row["red_numbers"]) != remote_reds
            or int(row["blue_number"]) != int(blue_raw or 0)
            or not isinstance(details, list)
            or len(details) != 6
        ):
            raise IsolatedMainlineError("official_draw_payout_identity_changed")
        tier_amounts: dict[int, str] = {}
        for item in details:
            if not isinstance(item, Mapping) or not isinstance(
                item.get("baseBetWinner"), Mapping
            ):
                raise IsolatedMainlineError("official_payout_tier_changed")
            tier = int(item.get("awardEtc", 0))
            raw_amount = str(item["baseBetWinner"].get("awardMoney", "")).replace(
                ",", ""
            )
            if tier not in range(1, 7) or tier in tier_amounts:
                raise IsolatedMainlineError("official_payout_tier_changed")
            try:
                amount = f"{float(raw_amount):.2f}"
            except ValueError as exc:
                raise IsolatedMainlineError("official_payout_amount_changed") from exc
            tier_amounts[tier] = amount
        if set(tier_amounts) != set(range(1, 7)):
            raise IsolatedMainlineError("official_payout_tier_set_changed")
        canonical_remote = contract.canonical_json(remote)
        return {
            "issue": issue,
            "draw_date": row["draw_date"].isoformat(),
            "red_numbers": list(remote_reds),
            "blue_number": int(blue_raw),
            "history_source": str(row["source"]),
            "payout_source": "zhcw",
            "payout_source_url": "https://jc.zhcw.com/port/client_json.php",
            "raw_record_sha256": hashlib.sha256(
                canonical_remote.encode("ascii")
            ).hexdigest(),
            "tier_amounts_cny": {
                str(key): tier_amounts[key] for key in sorted(tier_amounts)
            },
        }

    def _settlement(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        prediction = _unique_type(
            self._upstream("prediction"), "M4IsolatedPredictionV11"
        )
        prediction_replay = _unique_type(
            self._upstream("prediction_replay"), "M4IsolatedPredictionReplayV11"
        )
        preregistration = _unique_type(
            self._upstream("preregistration"), "M4IsolatedPreregistrationV11"
        )
        projection = _unique_type(
            self._upstream("target_issue_projection"),
            "M4IsolatedTargetIssueProjectionV11",
        )
        draw = self._audited_draw()
        draw_digest = contract.domain_digest(
            draw, domain="dehps.m4.isolated-24h-challenger.audited-draw.v11"
        )
        draw_input = build_registered_input(
            artifact_type="M4IsolatedAuditedDrawInputV11",
            artifact_digest=draw_digest,
            body=draw,
            parent_digests=(
                self.source_digest,
                projection["artifact_digest"],
            ),
        )
        register_input_artifact(
            repository=self.repository,
            payload=draw_input,
            git_commit=git_commit,
        )
        tickets = tuple(
            (tuple(int(value) for value in item["reds"]), int(item["blue"]))
            for item in prediction["body"]["tickets"]
        )
        accounting = reporting.settle_portfolio(
            tickets,
            winning_reds=draw["red_numbers"],
            winning_blue=int(draw["blue_number"]),
            first_prize_cny=draw["tier_amounts_cny"]["1"],
            second_prize_cny=draw["tier_amounts_cny"]["2"],
        )
        return (
            self._build(
                artifact_type="M4IsolatedSettlementV11",
                task_key=task_key,
                target_issue=self.context["target_issue"],
                git_commit=git_commit,
                parent_digests=(
                    prediction["artifact_digest"],
                    prediction_replay["artifact_digest"],
                    draw_input["artifact_digest"],
                    preregistration["artifact_digest"],
                ),
                type_body={
                    "audited_draw": draw,
                    "audited_draw_digest": draw_digest,
                    "prediction_digest": prediction["artifact_digest"],
                    "prediction_replay_digest": prediction_replay["artifact_digest"],
                    "accounting": accounting,
                    "evidence_label": "INSUFFICIENT_FOR_STATISTICAL_CONCLUSION",
                },
            ),
        )

    def _baseline_settlement(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        baseline = _unique_type(
            self._upstream("random_baseline_freeze"),
            "M4IsolatedRandomBaselineSetV11",
        )
        baseline_replay = _unique_type(
            self._upstream("random_baseline_freeze_replay"),
            "M4IsolatedRandomBaselineReplayV11",
        )
        settlement = _unique_type(
            self._upstream("settlement"), "M4IsolatedSettlementV11"
        )
        draw = settlement["body"]["audited_draw"]
        gross: list[str] = []
        roi: list[str] = []
        for raw_portfolio in baseline["body"]["portfolios"]:
            portfolio = tuple(
                (tuple(int(value) for value in item["reds"]), int(item["blue"]))
                for item in raw_portfolio
            )
            result = reporting.settle_portfolio(
                portfolio,
                winning_reds=draw["red_numbers"],
                winning_blue=int(draw["blue_number"]),
                first_prize_cny=draw["tier_amounts_cny"]["1"],
                second_prize_cny=draw["tier_amounts_cny"]["2"],
            )
            gross.append(result["gross_prize_cny"])
            roi.append(result["roi"])
        return (
            self._build(
                artifact_type="M4IsolatedRandomBaselineSettlementV11",
                task_key=task_key,
                target_issue=self.context["target_issue"],
                git_commit=git_commit,
                parent_digests=(
                    baseline["artifact_digest"],
                    baseline_replay["artifact_digest"],
                    settlement["artifact_digest"],
                    str(settlement["body"]["audited_draw_digest"]),
                ),
                type_body={
                    "replicate_count": len(gross),
                    "gross_prize_cny": gross,
                    "roi": roi,
                    "challenger_gross_percentile": reporting.percentile_position(
                        settlement["body"]["accounting"]["gross_prize_cny"], gross
                    ),
                    "challenger_roi_percentile": reporting.percentile_position(
                        settlement["body"]["accounting"]["roi"], roi
                    ),
                },
            ),
        )

    def _formal_p3_comparison_input(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        settlement = _unique_type(
            self._upstream("settlement"), "M4IsolatedSettlementV11"
        )
        preregistration = _unique_type(
            self._upstream("preregistration"), "M4IsolatedPreregistrationV11"
        )
        issue = self.context["target_issue"]
        keys = formal_p3.issue_task_keys(issue)
        required_keys = {
            formal_p3.PREREGISTRATION_TASK_KEY,
            keys["refit"],
            keys["predraw"],
            keys["predraw_replay"],
            keys["settlement"],
            keys["settlement_replay"],
        }
        p3_manifest = self.repository.load_manifest(
            control_plane_key="m4-information-theory-mainline"
        )
        known_keys = {item.task_key for item in p3_manifest.tasks}
        reason_codes: list[str] = []
        if not required_keys.issubset(known_keys):
            reason_codes.append("P3_ISSUE_TASK_MISSING")
        values: dict[str, tuple[str, tuple[dict[str, Any], ...]]] = {}
        if not reason_codes:
            specs = {
                "prereg": (
                    formal_p3.PREREGISTRATION_TASK_KEY,
                    3,
                    frozenset(
                        {
                            formal_p3.PREREGISTRATION_ARTIFACT_TYPE,
                            formal_p3.P4_PREREGISTRATION_ARTIFACT_TYPE,
                        }
                    ),
                ),
                "refit": (
                    keys["refit"],
                    3,
                    frozenset(
                        {
                            formal_p3.DATASET_ARTIFACT_TYPE,
                            formal_p3.MODEL_ARTIFACT_TYPE,
                        }
                    ),
                ),
                "predraw": (
                    keys["predraw"],
                    5,
                    frozenset(
                        {
                            formal_p3.MODEL_CANDIDATE_ARTIFACT_TYPE,
                            formal_p3.RANDOM_BASELINE_ARTIFACT_TYPE,
                            formal_p3.CHECKPOINT_ARTIFACT_TYPE,
                            formal_p3.PREDRAW_REPORT_ARTIFACT_TYPE,
                        }
                    ),
                ),
                "predraw_replay": (
                    keys["predraw_replay"],
                    2,
                    frozenset({formal_p3.PREDRAW_REPLAY_ARTIFACT_TYPE}),
                ),
                "settlement": (
                    keys["settlement"],
                    2,
                    frozenset({formal_p3.SETTLEMENT_ARTIFACT_TYPE}),
                ),
                "settlement_replay": (
                    keys["settlement_replay"],
                    2,
                    frozenset({formal_p3.SETTLEMENT_REPLAY_ARTIFACT_TYPE}),
                ),
            }
            try:
                for name, (p3_task_key, count, expected_types) in specs.items():
                    values[name] = load_formal_p3_completed_task_artifacts(
                        repository=self.repository,
                        root_dir=self.root_dir,
                        task_key=p3_task_key,
                        expected_registration_count=count,
                        expected_artifact_types=expected_types,
                    )
            except IsolatedMainlineError as exc:
                if "not_complete" in str(exc):
                    reason_codes.append("P3_ISSUE_TASK_NOT_COMPLETE")
                elif "registration_count" in str(exc):
                    reason_codes.append("P3_REGISTRATION_COUNT_MISMATCH")
                else:
                    reason_codes.append("P3_ARTIFACT_IDENTITY_MISMATCH")
        if not reason_codes:
            try:
                verify_formal_p3_generic_replay(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    task_key=keys["predraw_replay"],
                    execution_id=values["predraw_replay"][0],
                )
                verify_formal_p3_generic_replay(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    task_key=keys["settlement_replay"],
                    execution_id=values["settlement_replay"][0],
                )
            except (IsolatedMainlineError, MainlineSupervisorError):
                reason_codes.append("P3_GENERIC_REPLAY_NOT_VERIFIED")
        if not reason_codes:
            p3_prereg = _unique_type(
                values["prereg"][1], formal_p3.PREREGISTRATION_ARTIFACT_TYPE
            )
            dataset = _unique_type(values["refit"][1], formal_p3.DATASET_ARTIFACT_TYPE)
            model = _unique_type(values["refit"][1], formal_p3.MODEL_ARTIFACT_TYPE)
            candidates = _unique_type(
                values["predraw"][1], formal_p3.MODEL_CANDIDATE_ARTIFACT_TYPE
            )
            baseline = _unique_type(
                values["predraw"][1], formal_p3.RANDOM_BASELINE_ARTIFACT_TYPE
            )
            checkpoint = _unique_type(
                values["predraw"][1], formal_p3.CHECKPOINT_ARTIFACT_TYPE
            )
            report = _unique_type(
                values["predraw"][1], formal_p3.PREDRAW_REPORT_ARTIFACT_TYPE
            )
            predraw_replay = _unique_type(
                values["predraw_replay"][1],
                formal_p3.PREDRAW_REPLAY_ARTIFACT_TYPE,
            )
            p3_settlement = _unique_type(
                values["settlement"][1], formal_p3.SETTLEMENT_ARTIFACT_TYPE
            )
            settlement_replay = _unique_type(
                values["settlement_replay"][1],
                formal_p3.SETTLEMENT_REPLAY_ARTIFACT_TYPE,
            )
            identities_valid = (
                dataset["body"].get("target_issue") == issue
                and dataset["body"].get("future_rows_read") is False
                and dataset["parent_digests"]
                == [p3_prereg["artifact_digest"], contract.FORMAL_P3_SOURCE_DIGEST]
                and model["body"].get("target_issue") == issue
                and model["body"].get("lineage_id") == contract.FORMAL_P3_LINEAGE
                and model["body"].get("source_digest")
                == contract.FORMAL_P3_SOURCE_DIGEST
                and model["body"].get("future_rows_read") is False
                and model["parent_digests"]
                == [
                    dataset["artifact_digest"],
                    p3_prereg["artifact_digest"],
                    contract.FORMAL_P3_SOURCE_DIGEST,
                ]
                and checkpoint["body"].get("target_issue") == issue
                and checkpoint["body"].get("lineage_id") == contract.FORMAL_P3_LINEAGE
                and checkpoint["body"].get("source_digest")
                == contract.FORMAL_P3_SOURCE_DIGEST
                and checkpoint["body"].get("status") == "SEALED_BEFORE_DRAW"
                and checkpoint["body"].get("configuration_drift") is False
                and checkpoint["parent_digests"]
                == [
                    model["artifact_digest"],
                    candidates["artifact_digest"],
                    baseline["artifact_digest"],
                    p3_prereg["artifact_digest"],
                ]
                and predraw_replay["body"].get("target_issue") == issue
                and predraw_replay["body"].get("status") == "REPLAY_VERIFIED"
                and predraw_replay["parent_digests"]
                == [
                    candidates["artifact_digest"],
                    baseline["artifact_digest"],
                    checkpoint["artifact_digest"],
                    report["artifact_digest"],
                ]
                and p3_settlement["body"].get("target_issue") == issue
                and p3_settlement["body"].get("lineage_id")
                == contract.FORMAL_P3_LINEAGE
                and p3_settlement["body"].get("configuration_drift") is False
                and p3_settlement["parent_digests"]
                == [
                    model["artifact_digest"],
                    candidates["artifact_digest"],
                    baseline["artifact_digest"],
                    checkpoint["artifact_digest"],
                ]
                and settlement_replay["body"].get("target_issue") == issue
                and settlement_replay["body"].get("status") == "REPLAY_VERIFIED"
                and settlement_replay["parent_digests"]
                == [p3_settlement["artifact_digest"], checkpoint["artifact_digest"]]
            )
            if not identities_valid:
                reason_codes.append("P3_ARTIFACT_IDENTITY_MISMATCH")
        if reason_codes:
            return (
                self._build(
                    artifact_type="M4IsolatedFormalP3PendingMarkerV11",
                    task_key=task_key,
                    target_issue=issue,
                    git_commit=git_commit,
                    parent_digests=(
                        settlement["artifact_digest"],
                        preregistration["artifact_digest"],
                    ),
                    type_body={
                        "status": "PENDING_LEGAL_COMPARISON",
                        "reason_codes": sorted(set(reason_codes)),
                        "formal_p3_aggregate_result_reads": 0,
                        "formal_p3_write_access": "FORBIDDEN",
                    },
                ),
            )
        projection = {
            "issue": issue,
            "lineage_id": contract.FORMAL_P3_LINEAGE,
            "source_digest": contract.FORMAL_P3_SOURCE_DIGEST,
            "refit_task_key": keys["refit"],
            "predraw_task_key": keys["predraw"],
            "predraw_execution_id": values["predraw"][0],
            "checkpoint_digest": checkpoint["artifact_digest"],
            "predraw_replay_task_key": keys["predraw_replay"],
            "predraw_replay_digest": predraw_replay["artifact_digest"],
            "settlement_task_key": keys["settlement"],
            "settlement_execution_id": values["settlement"][0],
            "settlement_digest": p3_settlement["artifact_digest"],
            "settlement_replay_task_key": keys["settlement_replay"],
            "settlement_replay_digest": settlement_replay["artifact_digest"],
        }
        projection_digest = contract.domain_digest(
            projection,
            domain=("dehps.m4.isolated-24h-challenger.formal-p3-issue-projection.v11"),
        )
        return (
            self._build(
                artifact_type="M4IsolatedFormalP3IssueProjectionV11",
                task_key=task_key,
                target_issue=issue,
                git_commit=git_commit,
                parent_digests=(
                    settlement["artifact_digest"],
                    checkpoint["artifact_digest"],
                    predraw_replay["artifact_digest"],
                    p3_settlement["artifact_digest"],
                    settlement_replay["artifact_digest"],
                ),
                type_body={
                    "status": "COMPLETE",
                    "projection": projection,
                    "projection_digest": projection_digest,
                    "formal_p3_artifact_digests": [
                        checkpoint["artifact_digest"],
                        predraw_replay["artifact_digest"],
                        p3_settlement["artifact_digest"],
                        settlement_replay["artifact_digest"],
                    ],
                    "formal_p3_aggregate_result_reads": 0,
                    "formal_p3_write_access": "FORBIDDEN",
                },
            ),
        )

    def _formal_p3_comparison(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        settlement = _unique_type(
            self._upstream("settlement"), "M4IsolatedSettlementV11"
        )
        inputs = self._upstream("formal_p3_comparison_input")
        if len(inputs) != 1:
            raise IsolatedMainlineError("formal_p3_comparison_input_not_unique")
        input_artifact = inputs[0]
        if input_artifact["artifact_type"] == "M4IsolatedFormalP3IssueProjectionV11":
            status = "COMPLETE"
            reason_codes: list[str] = []
            projection = input_artifact["body"]["projection"]
        elif input_artifact["artifact_type"] == "M4IsolatedFormalP3PendingMarkerV11":
            status = "PENDING_LEGAL_COMPARISON"
            reason_codes = list(input_artifact["body"]["reason_codes"])
            projection = None
        else:
            raise IsolatedMainlineError("formal_p3_comparison_input_type_changed")
        return (
            self._build(
                artifact_type="M4IsolatedFormalP3ComparisonV11",
                task_key=task_key,
                target_issue=self.context["target_issue"],
                git_commit=git_commit,
                parent_digests=(
                    settlement["artifact_digest"],
                    input_artifact["artifact_digest"],
                ),
                type_body={
                    "status": status,
                    "reason_codes": reason_codes,
                    "formal_p3_issue_projection": projection,
                    "formal_p3_aggregate_result_reads": 0,
                    "formal_p3_write_access": "FORBIDDEN",
                },
            ),
        )

    def _settlement_report(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        settlement = _unique_type(
            self._upstream("settlement"), "M4IsolatedSettlementV11"
        )
        baseline = _unique_type(
            self._upstream("random_baseline_settlement"),
            "M4IsolatedRandomBaselineSettlementV11",
        )
        comparison = _unique_type(
            self._upstream("formal_p3_comparison"),
            "M4IsolatedFormalP3ComparisonV11",
        )
        prediction_digest = str(settlement["body"]["prediction_digest"])
        return (
            self._build(
                artifact_type="M4IsolatedSettlementReportV11",
                task_key=task_key,
                target_issue=self.context["target_issue"],
                git_commit=git_commit,
                parent_digests=(
                    settlement["artifact_digest"],
                    baseline["artifact_digest"],
                    comparison["artifact_digest"],
                ),
                type_body={
                    "settlement": settlement["body"]["accounting"],
                    "baseline_percentile": baseline["body"][
                        "challenger_gross_percentile"
                    ],
                    "baseline_roi_percentile": baseline["body"][
                        "challenger_roi_percentile"
                    ],
                    "formal_p3_comparison": comparison["body"]["status"],
                    "prediction_digest": prediction_digest,
                    "settlement_digest": settlement["artifact_digest"],
                    "early_evidence_label": "INSUFFICIENT_FOR_STATISTICAL_CONCLUSION",
                },
            ),
        )

    def _daily_summary(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        preregistration = _unique_type(
            self._upstream("preregistration"), "M4IsolatedPreregistrationV11"
        )
        self._latest_runtime_health(preregistration=preregistration)
        epoch_day = date.fromisoformat(
            f"{self.context['epoch_date'][:4]}-"
            f"{self.context['epoch_date'][4:6]}-"
            f"{self.context['epoch_date'][6:]}"
        )
        window_end = datetime.combine(
            epoch_day, contract.DAILY_SEND_TIME, contract.TIMEZONE
        )
        window_start = window_end - timedelta(days=1)
        with (
            self.repository.connection_factory() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            checkpoint_rows = [
                dict(item)
                for item in cursor.execute(
                    "SELECT batch_seq,target_issue,checkpoint_digest,replay_digest,"
                    "registered_at FROM m4_isolated_v11.search_checkpoints "
                    "WHERE registered_at < %s ORDER BY registered_at,batch_seq",
                    (window_end,),
                ).fetchall()
            ]
            if not checkpoint_rows:
                raise IsolatedMainlineError("CHECKPOINT_INCOMPLETE")
            prior = [
                item
                for item in checkpoint_rows
                if item["registered_at"] <= window_start
            ]
            opening = prior[-1] if prior else checkpoint_rows[0]
            closing = checkpoint_rows[-1]
            window_checkpoints = [
                item
                for item in checkpoint_rows
                if window_start <= item["registered_at"] < window_end
                and int(item["batch_seq"]) >= 0
            ]
            batch_sequences = [int(item["batch_seq"]) for item in window_checkpoints]
            if batch_sequences and batch_sequences != list(
                range(batch_sequences[0], batch_sequences[-1] + 1)
            ):
                raise IsolatedMainlineError("CHECKPOINT_INCOMPLETE")
            attempted_row = dict(
                cursor.execute(
                    "SELECT count(*) AS attempted FROM "
                    "m4_isolated_v11.candidate_registrations "
                    "WHERE registered_at >= %s AND registered_at < %s",
                    (window_start, window_end),
                ).fetchone()
            )
            result_row = dict(
                cursor.execute(
                    "SELECT count(*) FILTER (WHERE status='SUCCEEDED') AS succeeded,"
                    "count(*) FILTER (WHERE status='FAILED') AS failed "
                    "FROM m4_isolated_v11.candidate_results "
                    "WHERE completed_at >= %s AND completed_at < %s",
                    (window_start, window_end),
                ).fetchone()
            )
            attempt_row = dict(
                cursor.execute(
                    "SELECT count(*) FILTER (WHERE reason='WALL_TIMEOUT') AS timed_out,"
                    "count(*) FILTER (WHERE retry_ordinal>0) AS retried "
                    "FROM m4_isolated_v11.execution_attempts "
                    "WHERE terminal_at >= %s AND terminal_at < %s",
                    (window_start, window_end),
                ).fetchone()
            )
            family_rows = cursor.execute(
                "SELECT family,count(*) AS candidate_count FROM "
                "m4_isolated_v11.candidate_registrations "
                "WHERE registered_at >= %s AND registered_at < %s "
                "GROUP BY family ORDER BY family",
                (window_start, window_end),
            ).fetchall()
            head = cursor.execute(
                "SELECT registration_seq,m_total,head_artifact_digest "
                "FROM m4_isolated_v11.multiplicity_head WHERE singleton=TRUE"
            ).fetchone()
            lease_row = dict(
                cursor.execute(
                    "SELECT count(*) FILTER (WHERE status='LEASED') AS leased,"
                    "count(*) FILTER (WHERE status='LEASED' AND heartbeat_at < %s) "
                    "AS stale FROM m4_isolated_v11.execution_attempts",
                    (window_end - timedelta(seconds=180),),
                ).fetchone()
            )
        if head is None:
            raise IsolatedMainlineError("MULTIPLICITY_LEDGER_INCOMPLETE")
        opening_checkpoint = load_registered_isolated_artifact(
            repository=self.repository,
            root_dir=self.root_dir,
            artifact_digest=str(opening["checkpoint_digest"]),
            expected_artifact_type="M4IsolatedSearchCheckpointV11",
        )
        closing_checkpoint = load_registered_isolated_artifact(
            repository=self.repository,
            root_dir=self.root_dir,
            artifact_digest=str(closing["checkpoint_digest"]),
            expected_artifact_type="M4IsolatedSearchCheckpointV11",
        )
        batch_replays = [
            load_registered_isolated_artifact(
                repository=self.repository,
                root_dir=self.root_dir,
                artifact_digest=str(item["replay_digest"]),
                expected_artifact_type="M4IsolatedSearchCheckpointReplayV11",
            )
            for item in window_checkpoints
        ]
        manifest = self.repository.load_manifest(
            control_plane_key=contract.CONTROL_PLANE_KEY
        )
        manifest_facts = set(manifest.facts.artifacts)
        health_events = [
            item
            for item in self.repository.list_mainline_execution_event_metadata(
                control_plane_key=contract.CONTROL_PLANE_KEY
            )
            if item["event_type"] == "completed"
            and item["task_key"].startswith(
                "m4-isolated-24h-challenger-v11-runtime-health-"
            )
            and window_start
            <= datetime.fromisoformat(str(item["recorded_at"]))
            < window_end
        ]
        health_events.sort(key=lambda item: str(item["task_key"]))
        health_artifacts: list[dict[str, Any]] = []
        minutes: list[str] = []
        for event in health_events:
            health = _unique_type(
                load_completed_task_artifacts(
                    repository=self.repository,
                    root_dir=self.root_dir,
                    task_key=str(event["task_key"]),
                ),
                "M4IsolatedRuntimeHealthV11",
            )
            minute = str(health["body"].get("minute") or "")
            if (
                f"{event['task_key']}:HEALTH_RECORDED" not in manifest_facts
                or minute in minutes
            ):
                raise IsolatedMainlineError("daily_health_registration_changed")
            minutes.append(minute)
            health_artifacts.append(health)
        if minutes != sorted(minutes):
            raise IsolatedMainlineError("daily_health_minute_order_changed")
        observed_memory = [
            int(item["body"]["resource_observation"]["memory_current_bytes"])
            for item in health_artifacts
            if item["body"].get("resource_observation", {}).get("memory_current_bytes")
            is not None
        ]
        observed_temperature = [
            float(item["body"]["thermal_observation"]["max_cpu_celsius"])
            for item in health_artifacts
            if item["body"].get("thermal_observation", {}).get("max_cpu_celsius")
            is not None
        ]
        health_statuses = [str(item["body"].get("status")) for item in health_artifacts]
        incident_head = self._latest_incident_head()
        m_total = int(head[1])
        cohort_records = [
            self._cohort_selection_record(item, m_total=m_total)
            for item in closing_checkpoint["body"].get("cohorts", [])
        ]
        eligible = [item for item in cohort_records if item["eligible"]]
        eligible.sort(
            key=lambda item: (
                -float(item["multiplicity_penalized_lcb"]),
                -float(item["minimum_block_mean"]),
                -float(item["full_300_primary_mean"]),
                -int(item["top100_union_size"]),
                float(item["mean_pairwise_jaccard"]),
                int(item["complexity_cost"]),
                str(item["configuration_id"]),
            )
        )
        attempted = int(attempted_row["attempted"])
        parents = _ordered_unique(
            (
                opening_checkpoint["artifact_digest"],
                closing_checkpoint["artifact_digest"],
                *(item["artifact_digest"] for item in batch_replays),
                *(item["artifact_digest"] for item in health_artifacts),
                incident_head["artifact_digest"],
            )
        )
        return (
            self._build(
                artifact_type="M4IsolatedDailySummaryV11",
                task_key=task_key,
                target_issue=None,
                git_commit=git_commit,
                parent_digests=parents,
                type_body={
                    "attempted": attempted,
                    "succeeded": int(result_row["succeeded"]),
                    "failed": int(result_row["failed"]),
                    "timed_out": int(attempt_row["timed_out"]),
                    "retried": int(attempt_row["retried"]),
                    "family_distribution": {
                        str(item["family"]): int(item["candidate_count"])
                        for item in family_rows
                    },
                    "multiplicity_lifetime_total": m_total,
                    "multiplicity_increment": attempted,
                    "eligible_count": len(eligible),
                    "leading_candidate": (
                        eligible[0]["configuration_id"] if eligible else "NONE"
                    ),
                    "cpu": {
                        "quota": "1800%",
                        "weight": 1,
                        "scheduling_policy": "idle",
                    },
                    "memory": {
                        "high": "20G",
                        "max": "24G",
                        "observed_max_bytes": max(observed_memory, default=0),
                    },
                    "runtime": {
                        "mode": "24H_CONTINUOUS_WITH_P3_PREEMPTION",
                        "window_start": window_start.isoformat(),
                        "window_end": window_end.isoformat(),
                    },
                    "checkpoint": {
                        "opening_batch_seq": int(opening["batch_seq"]),
                        "opening_digest": opening_checkpoint["artifact_digest"],
                        "closing_batch_seq": int(closing["batch_seq"]),
                        "closing_digest": closing_checkpoint["artifact_digest"],
                    },
                    "worker_health": {
                        "record_count": len(health_artifacts),
                        "ordered_minutes": minutes,
                        "statuses": health_statuses,
                        "maximum_cpu_temperature_celsius": max(
                            observed_temperature, default=None
                        ),
                    },
                    "replay": {
                        "checkpoint_replay_count": len(batch_replays),
                        "checkpoint_replay_digests": [
                            item["artifact_digest"] for item in batch_replays
                        ],
                        "status": "REGISTERED_REPLAY_VERIFIED",
                    },
                    "incidents": dict(incident_head["body"]),
                    "recovery": {
                        "leased": int(lease_row["leased"]),
                        "stale_leases": int(lease_row["stale"]),
                        "policy": "EXACT_CHECKPOINT_RESUME",
                    },
                    "time_to_next_freeze": contract.schedule_for_issue(
                        self.context["target_issue"],
                        target_draw_date=self.context["target_draw_date"],
                    )["freeze_deadline"].isoformat(),
                },
            ),
        )

    def _incident_head_genesis(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        preregistration = _unique_type(
            self._upstream("preregistration"), "M4IsolatedPreregistrationV11"
        )
        return (
            self._build(
                artifact_type="M4IsolatedEmptyIncidentHeadV11",
                task_key=task_key,
                target_issue=None,
                git_commit=git_commit,
                parent_digests=(preregistration["artifact_digest"],),
                type_body={
                    "incident_seq": -1,
                    "open_count": 0,
                    "latest_incident_digest": None,
                },
            ),
        )

    def _latest_incident_head(self) -> dict[str, Any]:
        genesis = _unique_type(
            self._upstream("incident_head_genesis"),
            "M4IsolatedEmptyIncidentHeadV11",
        )
        manifest = self.repository.load_manifest(
            control_plane_key=contract.CONTROL_PLANE_KEY
        )
        heads: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for task in manifest.tasks:
            if task.requested_capability != "M4IsolatedIncidentOpenCapabilityV11":
                continue
            events = self.repository.list_mainline_execution_events(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                task_key=task.task_key,
            )
            if (
                len([item for item in events if item.get("event_type") == "completed"])
                != 1
            ):
                continue
            values = load_completed_task_artifacts(
                repository=self.repository,
                root_dir=self.root_dir,
                task_key=task.task_key,
            )
            incident = _unique_type(values, "M4IsolatedIncidentV11")
            head = _unique_type(values, "M4IsolatedIncidentHeadV11")
            heads.append((incident, head))
        previous = genesis
        for expected_seq, (incident, head) in enumerate(
            sorted(heads, key=lambda pair: int(pair[1]["body"]["incident_seq"]))
        ):
            if (
                head["body"].get("incident_seq") != expected_seq
                or head["body"].get("open_count") != expected_seq + 1
                or head["body"].get("latest_incident_digest")
                != incident["artifact_digest"]
                or head["parent_digests"]
                != [previous["artifact_digest"], incident["artifact_digest"]]
            ):
                raise IsolatedMainlineError("incident_head_chain_changed")
            previous = head
        return previous

    def _incident_open(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        reason_code = self.context["incident_reason_code"]
        offending_digest = contract.require_digest(
            self.context["incident_offending_digest"],
            field="incident_offending_digest",
        )
        incident_id = contract.incident_identity(
            reason_code=reason_code,
            first_offending_digest=offending_digest,
        )
        if incident_id != self.context["incident_id"]:
            raise IsolatedMainlineError("incident_identity_changed")
        with (
            self.repository.connection_factory() as connection,
            connection.cursor() as cursor,
        ):
            count = int(
                cursor.execute(
                    "SELECT count(*) FROM research_os_mainline_artifacts "
                    "WHERE artifact_digest=%s",
                    (offending_digest,),
                ).fetchone()[0]
            )
        if count < 1:
            raise IsolatedMainlineError("incident_offending_artifact_unregistered")
        previous = self._latest_incident_head()
        opened_at = self._active_created_at
        incident = self._build(
            artifact_type="M4IsolatedIncidentV11",
            task_key=task_key,
            target_issue=None,
            git_commit=git_commit,
            parent_digests=(offending_digest,),
            type_body={
                "status": "OPEN",
                "incident_id": incident_id,
                "reason_code": reason_code,
                "offending_artifact_digests": [offending_digest],
                "opened_at": opened_at,
            },
        )
        head = self._build(
            artifact_type="M4IsolatedIncidentHeadV11",
            task_key=task_key,
            target_issue=None,
            git_commit=git_commit,
            parent_digests=(
                previous["artifact_digest"],
                incident["artifact_digest"],
            ),
            type_body={
                "incident_seq": int(previous["body"]["incident_seq"]) + 1,
                "open_count": int(previous["body"]["open_count"]) + 1,
                "latest_incident_digest": incident["artifact_digest"],
                "opened_at": opened_at,
            },
        )
        return incident, head

    def _latest_runtime_health(
        self, *, preregistration: Mapping[str, Any]
    ) -> dict[str, Any]:
        manifest = self.repository.load_manifest(
            control_plane_key=contract.CONTROL_PLANE_KEY
        )
        facts = set(manifest.facts.artifacts)
        health: list[dict[str, Any]] = []
        for task in manifest.tasks:
            if (
                task.requested_capability != "M4IsolatedRuntimeHealthCapabilityV11"
                or f"{task.task_key}:HEALTH_RECORDED" not in facts
            ):
                continue
            values = load_completed_task_artifacts(
                repository=self.repository,
                root_dir=self.root_dir,
                task_key=task.task_key,
            )
            health.append(_unique_type(values, "M4IsolatedRuntimeHealthV11"))
        previous = dict(preregistration)
        for item in sorted(health, key=lambda value: str(value["body"]["minute"])):
            if item["parent_digests"] != [previous["artifact_digest"]]:
                raise IsolatedMainlineError("runtime_health_parent_chain_changed")
            previous = item
        return previous

    def _runtime_health(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        preregistration = _unique_type(
            self._upstream("preregistration"), "M4IsolatedPreregistrationV11"
        )
        previous = self._latest_runtime_health(preregistration=preregistration)
        p3_observation = formal_p3_resource_observation()
        p3_state = contract.formal_p3_activity_state(p3_observation)
        thermal = thermal_observation()
        temperature = thermal.get("max_cpu_celsius")
        if not thermal["query_ok"]:
            health_status = "RESOURCE_GUARD_TRIGGERED"
        elif float(temperature) >= contract.THERMAL_HARD_STOP_CELSIUS:
            health_status = "THERMAL_HARD_STOP"
        else:
            guard = ThermalGuard(root_dir=self.root_dir)
            guard.sample(force=True)
            if guard.paused:
                health_status = "THERMAL_PAUSED"
            elif p3_state != "QUIESCENT":
                health_status = "PREEMPTED_FOR_FORMAL_P3"
            else:
                health_status = "HEALTHY"
        resources = runtime_resource_observation(root_dir=self.root_dir)
        with (
            self.repository.connection_factory() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            worker = dict(
                cursor.execute(
                    "SELECT count(*) FILTER (WHERE state='LEASED') AS leased,"
                    "count(*) FILTER (WHERE state='TERMINAL') AS terminal "
                    "FROM m4_isolated_v11.candidate_registrations"
                ).fetchone()
            )
        return (
            self._build(
                artifact_type="M4IsolatedRuntimeHealthV11",
                task_key=task_key,
                target_issue=None,
                git_commit=git_commit,
                parent_digests=(previous["artifact_digest"],),
                type_body={
                    "minute": self.context["minute"],
                    "worker_limit": contract.WORKER_COUNT,
                    "cpu_quota": "1800%",
                    "memory_high": "20G",
                    "memory_max": "24G",
                    "formal_p3_unit": contract.FORMAL_P3_UNIT,
                    "formal_p3_priority": "ABSOLUTE_PREEMPTIVE",
                    "formal_p3_observation": p3_observation,
                    "formal_p3_state": p3_state,
                    "thermal_observation": thermal,
                    "thermal_policy": {
                        "sample_seconds": contract.THERMAL_SAMPLE_SECONDS,
                        "pause_new_work_at_celsius": contract.THERMAL_PAUSE_CELSIUS,
                        "pause_after_consecutive_samples": (
                            contract.THERMAL_PAUSE_CONSECUTIVE_SAMPLES
                        ),
                        "hard_stop_celsius": contract.THERMAL_HARD_STOP_CELSIUS,
                        "resume_below_celsius": contract.THERMAL_RESUME_BELOW_CELSIUS,
                        "resume_stable_seconds": (
                            contract.THERMAL_RESUME_STABLE_SECONDS
                        ),
                    },
                    "resource_observation": resources,
                    "workers": {
                        "leased": int(worker["leased"]),
                        "terminal": int(worker["terminal"]),
                    },
                    "status": health_status,
                },
            ),
        )

    def _multiplicity_risk_limit(
        self, *, task_key: str, git_commit: str
    ) -> tuple[dict[str, Any], ...]:
        preregistration = _unique_type(
            self._upstream("preregistration"), "M4IsolatedPreregistrationV11"
        )
        with (
            self.repository.connection_factory() as connection,
            connection.cursor() as cursor,
        ):
            row = cursor.execute(
                "SELECT registration_seq,m_total,head_artifact_digest "
                "FROM m4_isolated_v11.multiplicity_head WHERE singleton=TRUE"
            ).fetchone()
        if row is None:
            raise IsolatedMainlineError("multiplicity_head_missing")
        head_digest = contract.require_digest(
            row[2], field="multiplicity_head_artifact_digest"
        )
        m_total = int(row[1])
        return (
            self._build(
                artifact_type="M4IsolatedMultiplicityRiskLimitV11",
                task_key=task_key,
                target_issue=None,
                git_commit=git_commit,
                parent_digests=(head_digest, preregistration["artifact_digest"]),
                type_body={
                    "registration_seq": int(row[0]),
                    "m_total": m_total,
                    "lifetime_limit": contract.LIFETIME_MULTIPLICITY_LIMIT,
                    "remaining_capacity": contract.LIFETIME_MULTIPLICITY_LIMIT
                    - m_total,
                    "capacity_for_exact_batch": m_total + contract.ATTEMPTS_PER_BATCH
                    <= contract.LIFETIME_MULTIPLICITY_LIMIT,
                },
            ),
        )

    def _production_artifacts(
        self,
        *,
        template: contract.TaskTemplate,
        task_key: str,
        git_commit: str,
    ) -> tuple[dict[str, Any], ...]:
        direct = {
            "preregistration": self._preregistration,
            "operator_attestation": self._operator_attestation,
            "incident_head_genesis": self._incident_head_genesis,
            "incident_open": self._incident_open,
            "target_issue_projection": self._target_projection,
            "history_snapshot": self._history_snapshot,
            "mail_configuration": self._mail_configuration,
            "runtime_health": self._runtime_health,
            "genesis": self._genesis,
            "search_batch": self._search_batch,
            "search_checkpoint": self._search_checkpoint,
            "multiplicity_risk_limit": self._multiplicity_risk_limit,
            "multiplicity_seal": self._multiplicity_seal,
            "eligibility": self._eligibility,
            "challenger_freeze": self._challenger_freeze,
            "random_baseline_freeze": self._baseline_freeze,
            "prediction": self._prediction,
            "settlement": self._settlement,
            "random_baseline_settlement": self._baseline_settlement,
            "formal_p3_comparison_input": self._formal_p3_comparison_input,
            "formal_p3_comparison": self._formal_p3_comparison,
            "settlement_report": self._settlement_report,
            "daily_summary": self._daily_summary,
        }
        if template.name in direct:
            return direct[template.name](task_key=task_key, git_commit=git_commit)
        if template.name in {
            "predraw_mail_envelope",
            "post_mail_envelope",
            "daily_mail_envelope",
            "incident_envelope",
        }:
            return self._mail_envelope(
                template_name=template.name,
                task_key=task_key,
                git_commit=git_commit,
            )
        if template.name in {
            "predraw_delivery",
            "post_delivery",
            "daily_delivery",
            "incident_delivery",
        }:
            return self._mail_delivery(
                template_name=template.name,
                task_key=task_key,
                git_commit=git_commit,
            )
        replay = {
            "genesis_replay": (
                "genesis",
                "M4IsolatedSearchCheckpointReplayV11",
                None,
            ),
            "search_batch_replay": (
                "search_batch",
                "M4IsolatedSearchBatchReplayV11",
                self.context["target_issue"],
            ),
            "search_checkpoint_replay": (
                "search_checkpoint",
                "M4IsolatedSearchCheckpointReplayV11",
                None,
            ),
            "random_baseline_freeze_replay": (
                "random_baseline_freeze",
                "M4IsolatedRandomBaselineReplayV11",
                self.context["target_issue"],
            ),
            "prediction_replay": (
                "prediction",
                "M4IsolatedPredictionReplayV11",
                self.context["target_issue"],
            ),
            "settlement_replay": (
                "settlement_report",
                "M4IsolatedSettlementReplayV11",
                self.context["target_issue"],
            ),
            "daily_summary_replay": (
                "daily_summary",
                "M4IsolatedDailySummaryReplayV11",
                None,
            ),
            "predraw_mail_replay": (
                "predraw_mail_envelope",
                "M4IsolatedMailReplayV11",
                self.context["target_issue"],
            ),
            "post_mail_replay": (
                "post_mail_envelope",
                "M4IsolatedMailReplayV11",
                self.context["target_issue"],
            ),
            "daily_mail_replay": (
                "daily_mail_envelope",
                "M4IsolatedMailReplayV11",
                None,
            ),
            "incident_mail_replay": (
                "incident_envelope",
                "M4IsolatedMailReplayV11",
                None,
            ),
        }.get(template.name)
        if replay is None:
            raise IsolatedMainlineError(
                f"production_template_not_implemented:{template.name}"
            )
        return self._typed_replay(
            task_key=task_key,
            git_commit=git_commit,
            upstream_name=replay[0],
            artifact_type=replay[1],
            target_issue=replay[2],
        )

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> AtomicCapabilityResult:
        if control_plane_key != contract.CONTROL_PLANE_KEY:
            raise MainlineSupervisorError("isolated_control_plane_key_changed")
        template = template_for_task_key(task.task_key, context=self.context)
        if (
            task.requested_capability != self.capability_name
            or template.capability != self.capability_name
        ):
            raise MainlineSupervisorError("isolated_capability_identity_changed")
        self._active_created_at = self._execution_started_at(execution_id)
        self._active_execution_id = execution_id
        try:
            if self.simulation:
                target_issue = (
                    self.context["target_issue"]
                    if template.group == "issue"
                    or template.name
                    in {
                        "target_issue_projection",
                        "genesis",
                        "search_batch",
                        "search_checkpoint",
                    }
                    else None
                )
                payloads = build_task_artifacts(
                    template=template,
                    task_key=task.task_key,
                    target_issue=target_issue,
                    git_commit=git_commit,
                    source_digest=self.source_digest,
                    parent_digests=task.input_artifact_digests,
                    execution_id=execution_id,
                    simulation=True,
                    created_at=self._active_created_at,
                )
            else:
                payloads = self._production_artifacts(
                    template=template,
                    task_key=task.task_key,
                    git_commit=git_commit,
                )
        finally:
            self._active_created_at = None
            self._active_execution_id = None
        if not self.simulation:
            verify_registered_parent_closure(
                repository=self.repository,
                payloads=payloads,
            )
        atomic = tuple(
            AtomicArtifactPayload(
                slug=f"isolated-v11-{index:03d}-{payload['artifact_type'].lower()}",
                filename="artifact.json",
                payload=payload,
            )
            for index, payload in enumerate(payloads)
        )
        return AtomicCapabilityResult(
            artifacts=atomic,
            completion_facts=(),
            actual_fold_count=(
                contract.OUTER_FOLD_COUNT if template.name == "search_batch" else 0
            ),
            workload_rerun=False,
            execution_metadata=(
                ("isolated_lineage", contract.LINEAGE_ID),
                ("task_template", template.name),
                ("simulation", self.simulation),
                ("formal_p3_mutated", False),
                ("promotion_triggered", False),
            ),
        )


class IsolatedChallengerSupervisor(ResearchEvidenceSupervisor):
    def __init__(
        self,
        *,
        repository: PostgresResearchOSRepository,
        context: Mapping[str, str],
        source_digest: str,
        root_dir: Path = ROOT_DIR,
        git_commit: str | None = None,
        require_clean_tree: bool = True,
        simulation: bool = False,
        failed_recovery_event_digest: str = "",
        failed_recovery_attestation_digest: str = "",
    ) -> None:
        supervisor_module._TASK_ARTIFACT_NAMESPACE_BY_CONTROL_PLANE[
            contract.CONTROL_PLANE_KEY
        ] = "isolated-24h-challenger-v11"
        super().__init__(
            repository=repository,
            control_plane_key=contract.CONTROL_PLANE_KEY,
            root_dir=root_dir,
            git_commit=git_commit,
            require_clean_tree=require_clean_tree,
        )
        capability_names = tuple(
            dict.fromkeys(item.capability for item in contract.TASK_TEMPLATES)
        )
        isolated = {
            name: IsolatedV11Capability(
                capability_name=name,
                context=context,
                source_digest=source_digest,
                simulation=simulation,
                repository=repository,
                root_dir=root_dir,
            )
            for name in capability_names
        }
        overlap = set(isolated).intersection(self.capabilities)
        if overlap:
            raise MainlineSupervisorError("isolated_capability_name_collision")
        self.capabilities.update(isolated)
        self.isolated_capability_names = capability_names
        self.isolated_context = dict(context)
        self.isolated_source_digest = source_digest
        self.failed_recovery_event_digest = failed_recovery_event_digest
        self.failed_recovery_attestation_digest = failed_recovery_attestation_digest

    def _validated_additional_failed_recovery_event(
        self,
        *,
        task: Task,
        events: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any] | None:
        tokens = {
            self.failed_recovery_event_digest,
            self.failed_recovery_attestation_digest,
        }
        if tokens == {""}:
            return None
        if (
            self.failed_recovery_event_digest != _EXACT_FAILED_RECOVERY_EVENT_DIGEST
            or self.failed_recovery_attestation_digest
            != _EXACT_FAILED_RECOVERY_ATTESTATION_DIGEST
            or task.task_key != _EXACT_FAILED_RECOVERY_TASK_KEY
            or task.artifact_digest != _EXACT_FAILED_RECOVERY_TASK_DIGEST
            or tuple(task.input_artifact_digests)
            != (_EXACT_FAILED_RECOVERY_ORIGIN_SOURCE_DIGEST,)
            or self.isolated_source_digest
            != _EXACT_FAILED_RECOVERY_ORIGIN_SOURCE_DIGEST
        ):
            raise MainlineSupervisorError(
                "isolated exact failed recovery authorization changed"
            )
        if len(events) != 2:
            raise MainlineSupervisorError(
                "isolated exact failed recovery event set changed"
            )
        records = [supervisor_module._event_record(item) for item in events]
        started = [item for item in records if item.event_type == "started"]
        failed = [item for item in records if item.event_type == "failed"]
        if len(started) != 1 or len(failed) != 1:
            raise MainlineSupervisorError(
                "isolated exact failed recovery event set changed"
            )
        started_record = started[0]
        failed_record = failed[0]
        raw_by_digest = {str(item.get("event_digest") or ""): item for item in events}
        if (
            len(raw_by_digest) != 2
            or started_record.artifact_digest
            != _EXACT_FAILED_RECOVERY_STARTED_EVENT_DIGEST
            or failed_record.artifact_digest != _EXACT_FAILED_RECOVERY_EVENT_DIGEST
            or started_record.execution_id != _EXACT_FAILED_RECOVERY_EXECUTION_ID
            or failed_record.execution_id != _EXACT_FAILED_RECOVERY_EXECUTION_ID
            or started_record.control_plane_key != contract.CONTROL_PLANE_KEY
            or failed_record.control_plane_key != contract.CONTROL_PLANE_KEY
            or started_record.manifest_digest != _EXACT_FAILED_RECOVERY_MANIFEST_DIGEST
            or failed_record.manifest_digest != _EXACT_FAILED_RECOVERY_MANIFEST_DIGEST
            or started_record.task_key != _EXACT_FAILED_RECOVERY_TASK_KEY
            or failed_record.task_key != _EXACT_FAILED_RECOVERY_TASK_KEY
            or started_record.task_digest != _EXACT_FAILED_RECOVERY_TASK_DIGEST
            or failed_record.task_digest != _EXACT_FAILED_RECOVERY_TASK_DIGEST
            or started_record.capability != "M4IsolatedSearchBatchCapabilityV11"
            or failed_record.capability != "M4IsolatedSearchBatchCapabilityV11"
            or started_record.sequence != 0
            or failed_record.sequence != 1
            or dict(started_record.payload)
            != {
                "input_artifact_digests": [_EXACT_FAILED_RECOVERY_ORIGIN_SOURCE_DIGEST],
                "git_commit": _EXACT_FAILED_RECOVERY_ORIGIN_COMMIT,
            }
            or dict(failed_record.payload)
            != {
                "error": "atomic_registration_resume_changed",
                "git_commit": _EXACT_FAILED_RECOVERY_ORIGIN_COMMIT,
            }
        ):
            raise MainlineSupervisorError(
                "isolated exact failed recovery event provenance changed"
            )
        attestation_path = (
            self.root_dir
            / "runtime/research-os/mainline/tasks"
            / _EXACT_FAILED_RECOVERY_TASK_KEY
            / _EXACT_FAILED_RECOVERY_EXECUTION_ID
            / "runtime-migrations"
            / _EXACT_FAILED_RECOVERY_ATTESTATION_DIGEST
            / "user-systemd-runtime-migration.json"
        )
        try:
            attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MainlineSupervisorError(
                "isolated exact failed recovery attestation missing"
            ) from exc
        identity = dict(attestation)
        artifact_digest = identity.pop("artifact_digest", None)
        if (
            artifact_digest != _EXACT_FAILED_RECOVERY_ATTESTATION_DIGEST
            or attestation.get("task_digest") != _EXACT_FAILED_RECOVERY_TASK_DIGEST
            or attestation.get("execution_id") != _EXACT_FAILED_RECOVERY_EXECUTION_ID
            or attestation.get("started_event_digest")
            != _EXACT_FAILED_RECOVERY_STARTED_EVENT_DIGEST
            or attestation.get("origin_source_contract_digest")
            != _EXACT_FAILED_RECOVERY_ORIGIN_SOURCE_DIGEST
            or attestation.get("predecessor_attestation_digest")
            != "4d2c037b172beaa525de05c855d0d0e1ad72e8978c271f3cdf68fb9d23aa6452"
            or attestation.get("governance", {}).get("operator_request_id") != 748
            or attestation.get("governance", {}).get("operator_execution_id") != 603
            or contract.domain_digest(
                identity,
                domain=(
                    "dehps.m4.isolated-24h-challenger."
                    "same-key-event-isolation-runtime-migration.v11"
                ),
            )
            != _EXACT_FAILED_RECOVERY_ATTESTATION_DIGEST
        ):
            raise MainlineSupervisorError(
                "isolated exact failed recovery attestation changed"
            )
        return raw_by_digest[_EXACT_FAILED_RECOVERY_EVENT_DIGEST]

    def run_once(self, *, task_key: str | None = None) -> dict[str, Any]:
        if task_key is None or task_key not in {
            item.key(self.isolated_context) for item in contract.TASK_TEMPLATES
        }:
            raise MainlineSupervisorError("unkeyed_or_nonisolated_dispatch_forbidden")
        with _PUBLICATION_PATCH_LOCK:
            original_artifact = supervisor_module._atomic_artifact_relative_path
            original_execution = supervisor_module._atomic_execution_relative_path
            original_canonical = supervisor_module._canonical_task_artifact_path
            supervisor_module._atomic_artifact_relative_path = (
                _isolated_atomic_artifact_relative_path
            )
            supervisor_module._atomic_execution_relative_path = (
                _isolated_atomic_execution_relative_path
            )
            supervisor_module._canonical_task_artifact_path = (
                _isolated_canonical_task_artifact_path
            )
            try:
                return super().run_once(task_key=task_key)
            finally:
                supervisor_module._atomic_artifact_relative_path = original_artifact
                supervisor_module._atomic_execution_relative_path = original_execution
                supervisor_module._canonical_task_artifact_path = original_canonical

    def _complete_atomic_capability(self, **kwargs: Any) -> dict[str, Any]:
        # The base publication transaction is reused, while all registered files
        # are bound to the isolated runtime root.  The patch is process-local,
        # held for the entire atomic publication, and always restored; the V11
        # systemd unit is a separate process from Formal P3.
        with _PUBLICATION_PATCH_LOCK:
            original_artifact = supervisor_module._atomic_artifact_relative_path
            original_execution = supervisor_module._atomic_execution_relative_path
            original_canonical = supervisor_module._canonical_task_artifact_path
            supervisor_module._atomic_artifact_relative_path = (
                _isolated_atomic_artifact_relative_path
            )
            supervisor_module._atomic_execution_relative_path = (
                _isolated_atomic_execution_relative_path
            )
            supervisor_module._canonical_task_artifact_path = (
                _isolated_canonical_task_artifact_path
            )
            try:
                return super()._complete_atomic_capability(**kwargs)
            finally:
                supervisor_module._atomic_artifact_relative_path = original_artifact
                supervisor_module._atomic_execution_relative_path = original_execution
                supervisor_module._canonical_task_artifact_path = original_canonical

    def replay(
        self, *, task_key: str, execution_id: str | None = None
    ) -> dict[str, Any]:
        if task_key not in {
            item.key(self.isolated_context) for item in contract.TASK_TEMPLATES
        }:
            raise MainlineSupervisorError("replay_task_escaped_isolated_allowlist")
        generic = super().replay(task_key=task_key, execution_id=execution_id)
        children = load_completed_task_artifacts(
            repository=self.repository,
            root_dir=self.root_dir,
            task_key=task_key,
        )
        if not children:
            raise MainlineSupervisorError("isolated_replay_child_set_empty")
        return {
            **generic,
            "same_artifact_content": True,
            "all_registrations_and_parent_chains_exact": True,
        }

    def _build_lane_status(
        self,
        manifest: Any,
        *,
        snapshot: Any,
        dispatch_performed: bool,
        completed_summary: Mapping[str, Any] | None = None,
        m4_v2_global_replay_summary: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        del m4_v2_global_replay_summary
        facts = set(manifest.facts.artifacts)
        by_status = Counter(item.status.value for item in snapshot.resolutions)
        ready = [item.task_key for item in snapshot.ready_queue]
        mail_verified = contract.MAIL_CONFIGURATION_FACT in facts
        delivery_evidence = _external_delivery_evidence(facts)
        active = bool(mail_verified and delivery_evidence["real_mail_acceptance"])
        return {
            "schema_version": "dehps-m4-isolated-v11-status.v1",
            "status": (
                "ACTIVE_RESEARCH_ONLY"
                if active
                else (
                    "INTEGRATION_PENDING"
                    if mail_verified
                    else "ACTIVATION_BLOCKED_MAIL"
                )
            ),
            "activation": (
                "VALIDATED_IN_MAINLINE" if active else "INTEGRATION_PENDING"
            ),
            "control_plane_key": contract.CONTROL_PLANE_KEY,
            "manifest_digest": manifest.artifact_digest,
            "snapshot_digest": snapshot.snapshot_digest,
            "task_count": len(manifest.tasks),
            "task_status_counts": dict(sorted(by_status.items())),
            "ready_queue": ready,
            "next_ready_task": ready[0] if ready else None,
            "mail_configuration_verified": mail_verified,
            "external_mail": "ENABLED" if mail_verified else "BLOCKED",
            "external_delivery_evidence": delivery_evidence,
            "dispatch_performed": dispatch_performed,
            "completed_summary": (
                None if completed_summary is None else dict(completed_summary)
            ),
            "formal_p3": contract.FORMAL_P3_REQUIRED_STATUS,
            "formal_p3_mutated": False,
            "p4_p5_p6_or_promotion_triggered": False,
            "progress": {
                "engineering_percent": 100,
                "evidence_percent": 0,
            },
        }

    def _write_lane_status(self, payload: Mapping[str, Any]) -> None:
        supervisor_module.atomic_write_text(
            self.root_dir / "runtime/isolated-24h-challenger-v11/status.json",
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )

    @property
    def state_path(self) -> Path:
        return (
            self.root_dir / "runtime/isolated-24h-challenger-v11/supervisor-state.json"
        )


def simulate_artifact_chain(
    *,
    context: Mapping[str, str],
    git_commit: str,
    source_digest: str,
    created_at: str = "2026-08-27T00:00:00+00:00",
) -> dict[str, Any]:
    keys = contract.rendered_task_keys(context)
    artifacts_by_task: dict[str, list[dict[str, Any]]] = {}
    replays: list[dict[str, Any]] = []
    previous: list[str] = [source_digest]
    registered_artifact_digests: set[str] = {source_digest}
    for template, task_key in zip(contract.TASK_TEMPLATES, keys, strict=True):
        target_issue = context["target_issue"] if template.group == "issue" else None
        generated = build_task_artifacts(
            template=template,
            task_key=task_key,
            target_issue=target_issue,
            git_commit=git_commit,
            source_digest=source_digest,
            parent_digests=tuple(previous[-3:]),
            execution_id=hashlib.sha256(task_key.encode("utf-8")).hexdigest(),
            simulation=True,
            created_at=created_at,
        )
        artifacts_by_task[task_key] = list(generated)
        for payload in generated:
            if not set(payload["parent_digests"]).issubset(registered_artifact_digests):
                raise IsolatedMainlineError("simulation_unregistered_parent")
            replay = artifacts.replay_artifact(
                payload, expected_parent_digests=payload["parent_digests"]
            )
            replays.append(replay)
            previous.append(payload["artifact_digest"])
            registered_artifact_digests.add(payload["artifact_digest"])
    artifact_counts = Counter(
        payload["artifact_type"]
        for payloads in artifacts_by_task.values()
        for payload in payloads
    )
    if set(artifacts_by_task) != set(keys):
        raise IsolatedMainlineError("simulation_task_coverage_changed")
    if any(item["status"] != "REPLAY_VERIFIED" for item in replays):
        raise IsolatedMainlineError("simulation_replay_failed")
    delivery_states = [
        payload["body"]["state"]
        for payloads in artifacts_by_task.values()
        for payload in payloads
        if payload["artifact_type"] == "M4IsolatedDeliveryReceiptV11"
    ]
    delivery_mail_kinds = [
        payload["body"]["mail_kind"]
        for payloads in artifacts_by_task.values()
        for payload in payloads
        if payload["artifact_type"] == "M4IsolatedDeliveryReceiptV11"
    ]
    if not delivery_states or set(delivery_states) != {"SIMULATED"}:
        raise IsolatedMainlineError("simulation_delivery_created_external_state")
    return {
        "schema_version": "dehps-m4-isolated-v11-simulation.v1",
        "status": "SIMULATION_REPLAY_VERIFIED",
        "task_count": len(keys),
        "task_keys": list(keys),
        "artifact_count": sum(artifact_counts.values()),
        "artifact_type_counts": dict(sorted(artifact_counts.items())),
        "replay_count": len(replays),
        "all_parents_registered": True,
        "delivery_states": delivery_states,
        "delivery_mail_kinds": delivery_mail_kinds,
        "external_sent_count": 0,
        "smtp_calls": 0,
        "formal_p3_mutated": False,
        "formal_p4_p5_p6_or_promotion_triggered": False,
        "simulation_digest": contract.domain_digest(
            {
                "tasks": keys,
                "artifact_digests": [
                    payload["artifact_digest"]
                    for payloads in artifacts_by_task.values()
                    for payload in payloads
                ],
            },
            domain="dehps.m4.isolated-24h-challenger.simulation.v11",
        ),
    }


def compact_status(*, repository: PostgresResearchOSRepository) -> dict[str, Any]:
    try:
        manifest = repository.load_manifest(
            control_plane_key=contract.CONTROL_PLANE_KEY
        )
    except ResearchOSValidationError as exc:
        if "control plane not found" not in str(exc):
            raise
        return {
            "status": "NOT_REGISTERED",
            "activation": "INTEGRATION_PENDING",
            "formal_p3": contract.FORMAL_P3_REQUIRED_STATUS,
            "formal_p3_mutated": False,
            "external_mail": "NOT_CONFIGURED",
        }
    snapshot = repository.control_plane.resolve(manifest)
    facts = set(manifest.facts.artifacts)
    by_status = Counter(item.status.value for item in snapshot.resolutions)
    mail_verified = contract.MAIL_CONFIGURATION_FACT in facts
    delivery_evidence = _external_delivery_evidence(facts)
    active = bool(mail_verified and delivery_evidence["real_mail_acceptance"])
    return {
        "status": (
            "ACTIVE_RESEARCH_ONLY"
            if active
            else ("INTEGRATION_PENDING" if mail_verified else "ACTIVATION_BLOCKED_MAIL")
        ),
        "activation": "VALIDATED_IN_MAINLINE" if active else "INTEGRATION_PENDING",
        "control_plane_key": contract.CONTROL_PLANE_KEY,
        "manifest_digest": manifest.artifact_digest,
        "task_count": len(manifest.tasks),
        "task_status_counts": dict(sorted(by_status.items())),
        "ready_queue": [item.task_key for item in snapshot.ready_queue],
        "mail_configuration_verified": mail_verified,
        "external_mail": "ENABLED" if mail_verified else "BLOCKED",
        "external_delivery_evidence": delivery_evidence,
        "formal_p3": contract.FORMAL_P3_REQUIRED_STATUS,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
    }
