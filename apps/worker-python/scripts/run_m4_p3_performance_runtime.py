from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import resource
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentExecutionStatus, AgentRequestStatus
from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2 import (
    forward_prequential_confirmatory as successor,
)
from dehps.research_os.repository import PostgresResearchOSRepository

CONTROL_PLANE_KEY = "m4-information-theory-mainline"
RESEARCH_REQUEST_KEY = "research-m4-p3-persistent-high-performance-runtime-contract-v1"
RESEARCH_REQUEST_ID = 657
RESEARCH_APPROVAL_DECISION_ID = 2766
RESEARCH_PAYLOAD_SHA256 = (
    "e6ee163550746fe7a40840200bb8c707d6e3b8629a72e59e0426013bcda98cbb"
)
ENGINEERING_REQUEST_KEY = "engineering-m4-p3-persistent-high-performance-runtime-v1"
ENGINEERING_REQUEST_ID = 658
ENGINEERING_APPROVAL_DECISION_ID = 2769
ENGINEERING_EXECUTION_ID = 534
ENGINEERING_PAYLOAD_SHA256 = (
    "f1cb7084205dc994f46ed46f98beb5962f67dfcc2b5045ecb3599b3ab0c15d0d"
)

TARGET_ISSUE = "2026097"
EXPECTED_DIGESTS = {
    successor.PREREGISTRATION_ARTIFACT_TYPE: (
        "8d43f343f555e0a69580c0ccb1fb398b5ff2c191689ef37751c095ba94b144dd"
    ),
    successor.DATASET_ARTIFACT_TYPE: (
        "e006bcb35136f794e44966915627e45b5b2291438ad51215893da44dd0e60392"
    ),
    successor.MODEL_ARTIFACT_TYPE: (
        "70c3c976a7eee7c31b00103bcd8755abfa2add24f5e8ebee1a0e09345dfc8b6b"
    ),
    successor.MODEL_CANDIDATE_ARTIFACT_TYPE: (
        "1f1e8e429e09d00cf9dddefbc624b0c4d9e1b42c52be40b082803728d01e754e"
    ),
    successor.RANDOM_BASELINE_ARTIFACT_TYPE: (
        "b70c6f48e3588c03591c27f692ef9077c03c6a32a7404051aa02d221f17a582e"
    ),
    successor.CHECKPOINT_ARTIFACT_TYPE: (
        "1b448f9090feed24c64aff5ad0bcdb40281c0df5372347345bf4b91a4b9e137c"
    ),
    successor.PREDRAW_REPORT_ARTIFACT_TYPE: (
        "be33a4e1fc0fb5b66c99b20fa2bb2719653cba3b53d2f2b97c56d74fc19d7858"
    ),
    successor.PREDRAW_REPLAY_ARTIFACT_TYPE: (
        "72b6ddedb727777d07986b8dbb14ac8ef084d3ac464d3575fc16257bc2063645"
    ),
}
EXPECTED_SOURCE_DIGEST = (
    "139ddc97ce1d81ea4e6182359f8391532ed1911090db004bcdf9ebcdea5f9493"
)
EXPECTED_SOURCE_SET_DIGEST = (
    "a3b34318d784d9477fe82f7e66c3c04e5640eaed87e2b4c49cd8b397fc27cd9c"
)

RUNTIME_ROOT = ROOT_DIR / "runtime/p3-performance"
DEFAULT_CONFIG_PATH = RUNTIME_ROOT / "config.json"
DEFAULT_STATE_PATH = RUNTIME_ROOT / "state.json"
DEFAULT_MODE_PATH = RUNTIME_ROOT / "mode.json"
PLATFORM_PROFILE_PATH = Path("/sys/firmware/acpi/platform_profile")
MSR_RELATIVE = Path(
    "devices/virtual/powercap/intel-rapl/intel-rapl:0/constraint_0_power_limit_uw"
)
MMIO_RELATIVE = Path(
    "devices/virtual/powercap/intel-rapl-mmio/intel-rapl-mmio:0/constraint_0_power_limit_uw"
)
MSR_MAX_RELATIVE = Path(
    "devices/virtual/powercap/intel-rapl/intel-rapl:0/constraint_0_max_power_uw"
)
MMIO_MAX_RELATIVE = Path(
    "devices/virtual/powercap/intel-rapl-mmio/intel-rapl-mmio:0/constraint_0_max_power_uw"
)
MSR_PL2_RELATIVE = Path(
    "devices/virtual/powercap/intel-rapl/intel-rapl:0/constraint_1_power_limit_uw"
)
MMIO_PL2_RELATIVE = Path(
    "devices/virtual/powercap/intel-rapl-mmio/intel-rapl-mmio:0/constraint_1_power_limit_uw"
)
P3_UNIT = "dehps-forward-prequential-successor.service"
OLD_GUARD_UNIT = "dehps-p26-mmio-pl1-guard.service"
WATCHDOG_UNIT = "dehps-p3-performance-watchdog.service"
ALLOWED_MMIO_WATTS = (20, 28)
MSR_PL2_WATTS = 55
MMIO_PL2_WATTS = 43
OUTER_VALUES = (1, 2, 4, 6, 8, 12, 22)
INNER_VALUES = (1, 2, 4, 6, 8, 12, 22)
HYBRID_VALUES = ((2, 2), (4, 2), (6, 2), (8, 2), (2, 4), (4, 4))
AFFINITIES = {
    "all": "0-21",
    "p_logical": "0-11",
    "p_physical_plus_e": "0,1,3,6,8,10,12-19",
    "p_plus_e_no_lp": "0-19",
    "p_physical": "0,1,3,6,8,10",
}
THREAD_PROFILES = {
    "uniform_1": {
        "OMP_NUM_THREADS": 1,
        "OPENBLAS_NUM_THREADS": 1,
        "MKL_NUM_THREADS": 1,
        "NUMEXPR_NUM_THREADS": 1,
    },
    "native_default_explicit": {
        "OMP_NUM_THREADS": 1,
        "OPENBLAS_NUM_THREADS": 22,
        "MKL_NUM_THREADS": 1,
        "NUMEXPR_NUM_THREADS": 1,
    },
}

RUNTIME_COMPATIBILITY_CLOSURE_SCHEMA = (
    "dehps-m4-p3-runtime-descendant-compatibility-closure.v1"
)
RUNTIME_COMPATIBILITY_CLOSURE_DOMAIN = (
    "dehps.m4.p3.runtime-descendant-compatibility-closure.v1"
)
RUNTIME_COMPATIBILITY_PATHS = (
    "apps/worker-python/dehps/prediction/v2/generator.py",
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/forward_prequential_confirmatory.py",
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/marginal_static_contract.py",
    "apps/worker-python/dehps/research_os/repository.py",
    "apps/worker-python/dehps/research_os/supervisor.py",
    "apps/worker-python/scripts/build_m4_p3_forward_prequential_confirmatory_manifest.py",
    "apps/worker-python/scripts/run_m4_p3_forward_prequential_confirmatory.py",
    "apps/worker-python/scripts/run_m4_p3_performance_runtime.py",
    "deploy/systemd/dehps-forward-prequential-successor.service",
    "deploy/systemd/dehps-forward-prequential-successor.timer",
)


class P3PerformanceRuntimeError(RuntimeError):
    pass


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    raw = json.dumps(
        dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _closure_digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(
        dict(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(
        RUNTIME_COMPATIBILITY_CLOSURE_DOMAIN.encode("utf-8") + b"\0" + raw
    ).hexdigest()


def _git_output(root_dir: Path, *arguments: str, text: bool = True) -> str | bytes:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=root_dir,
            check=True,
            capture_output=True,
            text=text,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise P3PerformanceRuntimeError(
            "runtime compatibility git boundary changed: " + " ".join(arguments)
        ) from exc
    return completed.stdout


def _commit(value: Any, *, root_dir: Path) -> str:
    commit = str(value or "")
    if (
        len(commit) != 40
        or commit.lower() != commit
        or any(character not in "0123456789abcdef" for character in commit)
    ):
        raise P3PerformanceRuntimeError("runtime compatibility commit is invalid")
    _git_output(root_dir, "cat-file", "-e", f"{commit}^{{commit}}")
    return commit


def _git_blob_record(root_dir: Path, *, commit: str, relative: str) -> dict[str, Any]:
    listing = str(_git_output(root_dir, "ls-tree", commit, "--", relative)).strip()
    metadata, separator, observed_path = listing.partition("\t")
    values = metadata.split()
    if (
        separator != "\t"
        or observed_path != relative
        or len(values) != 3
        or values[0] != "100644"
        or values[1] != "blob"
    ):
        raise P3PerformanceRuntimeError(
            f"runtime compatibility path is not one regular blob: {relative}"
        )
    data = bytes(_git_output(root_dir, "show", f"{commit}:{relative}", text=False))
    return {
        "path": relative,
        "git_mode": values[0],
        "git_type": values[1],
        "git_blob": values[2],
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def build_runtime_compatibility_closure(
    commit: str, *, root_dir: Path = ROOT_DIR
) -> dict[str, Any]:
    root = root_dir.resolve()
    resolved_commit = _commit(commit, root_dir=root)
    preimage = {
        "schema_version": RUNTIME_COMPATIBILITY_CLOSURE_SCHEMA,
        "records": [
            _git_blob_record(root, commit=resolved_commit, relative=relative)
            for relative in RUNTIME_COMPATIBILITY_PATHS
        ],
    }
    return {**preimage, "closure_digest": _closure_digest(preimage)}


def _validate_runtime_compatibility_closure(
    value: Any,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "records",
        "closure_digest",
    }:
        raise P3PerformanceRuntimeError("runtime compatibility closure shape changed")
    records = value.get("records")
    if not isinstance(records, list) or len(records) != len(
        RUNTIME_COMPATIBILITY_PATHS
    ):
        raise P3PerformanceRuntimeError("runtime compatibility record count changed")
    expected_keys = {
        "path",
        "git_mode",
        "git_type",
        "git_blob",
        "bytes",
        "sha256",
    }
    if [item.get("path") for item in records if isinstance(item, Mapping)] != list(
        RUNTIME_COMPATIBILITY_PATHS
    ) or any(
        not isinstance(item, Mapping) or set(item) != expected_keys for item in records
    ):
        raise P3PerformanceRuntimeError("runtime compatibility path order changed")
    for item in records:
        if (
            item["git_mode"] != "100644"
            or item["git_type"] != "blob"
            or not isinstance(item["git_blob"], str)
            or len(item["git_blob"]) != 40
            or item["git_blob"].lower() != item["git_blob"]
            or any(
                character not in "0123456789abcdef" for character in item["git_blob"]
            )
            or not isinstance(item["sha256"], str)
            or len(item["sha256"]) != 64
            or item["sha256"].lower() != item["sha256"]
            or any(character not in "0123456789abcdef" for character in item["sha256"])
            or isinstance(item["bytes"], bool)
            or not isinstance(item["bytes"], int)
            or item["bytes"] < 1
        ):
            raise P3PerformanceRuntimeError("runtime compatibility record changed")
    preimage = {
        "schema_version": value["schema_version"],
        "records": [dict(item) for item in records],
    }
    if value["schema_version"] != RUNTIME_COMPATIBILITY_CLOSURE_SCHEMA or value[
        "closure_digest"
    ] != _closure_digest(preimage):
        raise P3PerformanceRuntimeError("runtime compatibility digest changed")
    return {**preimage, "closure_digest": str(value["closure_digest"])}


def verify_runtime_compatibility_closure(
    *,
    operator_commit: str,
    closure: Any,
    root_dir: Path = ROOT_DIR,
) -> None:
    root = root_dir.resolve()
    stored = _validate_runtime_compatibility_closure(closure)
    commit = _commit(operator_commit, root_dir=root)
    head = str(_git_output(root, "rev-parse", "HEAD")).strip()
    try:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, head],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise P3PerformanceRuntimeError(
            "operator merged commit is not an ancestor of HEAD"
        ) from exc
    if str(_git_output(root, "status", "--porcelain")).strip():
        raise P3PerformanceRuntimeError("runtime compatibility worktree is dirty")
    expected = build_runtime_compatibility_closure(commit, root_dir=root)
    if stored != expected:
        raise P3PerformanceRuntimeError(
            "operator runtime compatibility closure changed"
        )
    head_closure = build_runtime_compatibility_closure(head, root_dir=root)
    if head_closure != stored:
        raise P3PerformanceRuntimeError("descendant runtime compatibility drifted")
    for record in stored["records"]:
        path = root / str(record["path"])
        if not path.is_file() or path.is_symlink():
            raise P3PerformanceRuntimeError(
                f"runtime compatibility worktree path changed: {record['path']}"
            )
        data = path.read_bytes()
        if (
            len(data) != int(record["bytes"])
            or hashlib.sha256(data).hexdigest() != record["sha256"]
        ):
            raise P3PerformanceRuntimeError(
                f"runtime compatibility worktree bytes changed: {record['path']}"
            )


def _json_load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise P3PerformanceRuntimeError(f"expected JSON object: {path}")
    return value


def _json_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        path,
        json.dumps(dict(value), sort_keys=True, indent=2, ensure_ascii=False) + "\n",
    )


def _verify_request(
    repository: AgentRequestRepository,
    *,
    key: str,
    request_id: int,
    approval_id: int,
    payload_sha256: str,
    execution_id: int | None = None,
) -> None:
    request = repository.get_request(key)
    contract = repository.get_request_contract(key, include_payload=True)
    approvals = [
        item
        for item in repository.list_decision_metadata(key)
        if item["decision_code"] == "request_approved"
    ]
    if (
        request.id != request_id
        or request.status
        not in {
            AgentRequestStatus.APPROVED,
            AgentRequestStatus.EXECUTING,
            AgentRequestStatus.COMPLETED,
        }
        or _canonical_sha256(dict(contract["payload_json"])) != payload_sha256
        or len(approvals) != 1
        or int(approvals[0]["id"]) != approval_id
    ):
        raise P3PerformanceRuntimeError(f"governance identity changed: {key}")
    if execution_id is not None:
        execution = repository.get_execution_metadata(key, execution_id)
        if execution.status not in {
            AgentExecutionStatus.RUNNING,
            AgentExecutionStatus.COMPLETED,
        }:
            raise P3PerformanceRuntimeError(f"engineering execution inactive: {key}")


def verify_engineering_governance() -> None:
    repository = AgentRequestRepository()
    _verify_request(
        repository,
        key=RESEARCH_REQUEST_KEY,
        request_id=RESEARCH_REQUEST_ID,
        approval_id=RESEARCH_APPROVAL_DECISION_ID,
        payload_sha256=RESEARCH_PAYLOAD_SHA256,
    )
    _verify_request(
        repository,
        key=ENGINEERING_REQUEST_KEY,
        request_id=ENGINEERING_REQUEST_ID,
        approval_id=ENGINEERING_APPROVAL_DECISION_ID,
        payload_sha256=ENGINEERING_PAYLOAD_SHA256,
        execution_id=ENGINEERING_EXECUTION_ID,
    )


def verify_operator_governance(config: Mapping[str, Any]) -> None:
    operator = config.get("operator")
    if not isinstance(operator, Mapping):
        raise P3PerformanceRuntimeError("operator authorization is missing")
    required = {
        "request_key",
        "request_id",
        "approval_decision_id",
        "execution_id",
        "payload_sha256",
        "merged_commit",
    }
    if set(operator) != required:
        raise P3PerformanceRuntimeError("operator authorization shape changed")
    repository = AgentRequestRepository()
    request = repository.get_request(str(operator["request_key"]))
    if not request.request_type.value.startswith("operator_"):
        raise P3PerformanceRuntimeError(
            "production operation requires Operator Request"
        )
    _verify_request(
        repository,
        key=str(operator["request_key"]),
        request_id=int(operator["request_id"]),
        approval_id=int(operator["approval_decision_id"]),
        payload_sha256=str(operator["payload_sha256"]),
        execution_id=int(operator["execution_id"]),
    )
    verify_runtime_compatibility_closure(
        operator_commit=str(operator["merged_commit"]),
        closure=config.get("runtime_compatibility_closure"),
    )
    successor.verify_governance(repository)
    source = successor.load_source_contract(root_dir=ROOT_DIR)
    if (
        source.get("artifact_digest") != EXPECTED_SOURCE_DIGEST
        or source.get("source_set_digest") != EXPECTED_SOURCE_SET_DIGEST
    ):
        raise P3PerformanceRuntimeError("Formal P3 source identity changed")


def _registered_payload(
    repository: PostgresResearchOSRepository,
    *,
    task_key: str,
    artifact_type: str,
) -> dict[str, Any]:
    completed = [
        item
        for item in repository.list_mainline_execution_events(
            control_plane_key=CONTROL_PLANE_KEY, task_key=task_key
        )
        if item.get("event_type") == "completed"
    ]
    if len(completed) != 1:
        raise P3PerformanceRuntimeError(f"expected one completed P3 task: {task_key}")
    registrations = repository.list_mainline_artifacts(
        control_plane_key=CONTROL_PLANE_KEY,
        execution_id=str(completed[0]["execution_id"]),
    )
    matches = [item for item in registrations if item["artifact_type"] == artifact_type]
    if len(matches) != 1:
        raise P3PerformanceRuntimeError(
            f"expected one registered P3 artifact: {artifact_type}"
        )
    registration = matches[0]
    path = (ROOT_DIR / str(registration["artifact_path"])).resolve()
    if not path.is_relative_to(ROOT_DIR.resolve()) or not path.is_file():
        raise P3PerformanceRuntimeError(
            f"registered artifact path invalid: {artifact_type}"
        )
    payload = _json_load(path)
    expected = EXPECTED_DIGESTS[artifact_type]
    if (
        payload.get("artifact_digest") != expected
        or registration.get("artifact_digest") != expected
        or registration.get("parent_digests") != payload.get("parent_digests")
    ):
        raise P3PerformanceRuntimeError(
            f"registered artifact identity changed: {artifact_type}"
        )
    return payload


def load_reference_bundle() -> dict[str, Any]:
    verify_engineering_governance()
    repository = PostgresResearchOSRepository()
    keys = successor.issue_task_keys(TARGET_ISSUE)
    source = successor.load_source_contract(root_dir=ROOT_DIR)
    if (
        source.get("artifact_digest") != EXPECTED_SOURCE_DIGEST
        or source.get("source_set_digest") != EXPECTED_SOURCE_SET_DIGEST
    ):
        raise P3PerformanceRuntimeError("frozen P3 source identity changed")
    preregistration = _registered_payload(
        repository,
        task_key=successor.PREREGISTRATION_TASK_KEY,
        artifact_type=successor.PREREGISTRATION_ARTIFACT_TYPE,
    )
    dataset = _registered_payload(
        repository,
        task_key=keys["refit"],
        artifact_type=successor.DATASET_ARTIFACT_TYPE,
    )
    model = _registered_payload(
        repository,
        task_key=keys["refit"],
        artifact_type=successor.MODEL_ARTIFACT_TYPE,
    )
    values = {
        successor.MODEL_CANDIDATE_ARTIFACT_TYPE: _registered_payload(
            repository,
            task_key=keys["predraw"],
            artifact_type=successor.MODEL_CANDIDATE_ARTIFACT_TYPE,
        ),
        successor.RANDOM_BASELINE_ARTIFACT_TYPE: _registered_payload(
            repository,
            task_key=keys["predraw"],
            artifact_type=successor.RANDOM_BASELINE_ARTIFACT_TYPE,
        ),
        successor.CHECKPOINT_ARTIFACT_TYPE: _registered_payload(
            repository,
            task_key=keys["predraw"],
            artifact_type=successor.CHECKPOINT_ARTIFACT_TYPE,
        ),
        successor.PREDRAW_REPORT_ARTIFACT_TYPE: _registered_payload(
            repository,
            task_key=keys["predraw"],
            artifact_type=successor.PREDRAW_REPORT_ARTIFACT_TYPE,
        ),
        successor.PREDRAW_REPLAY_ARTIFACT_TYPE: _registered_payload(
            repository,
            task_key=keys["predraw_replay"],
            artifact_type=successor.PREDRAW_REPLAY_ARTIFACT_TYPE,
        ),
    }
    return {
        "source_contract": source,
        "preregistration": preregistration,
        "dataset": dataset,
        "model": model,
        "expected": values,
    }


def run_reference_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    preregistration = dict(bundle["preregistration"])
    dataset_expected = dict(bundle["dataset"])
    model_expected = dict(bundle["model"])
    rows = [
        (
            str(item["issue"]),
            date.fromisoformat(str(item["draw_date"])),
            tuple(int(value) for value in item["red_numbers"]),
        )
        for item in dataset_expected["body"]["rows"]
    ]
    refit_started = time.perf_counter()
    dataset, model = successor.fit_model_artifacts(
        source_contract=dict(bundle["source_contract"]),
        preregistration=preregistration,
        history_rows=rows,
        target_issue=TARGET_ISSUE,
    )
    refit_seconds = time.perf_counter() - refit_started
    if dataset != dataset_expected or model != model_expected:
        raise P3PerformanceRuntimeError("frozen refit output changed")

    expected = dict(bundle["expected"])
    checkpoint_expected = expected[successor.CHECKPOINT_ARTIFACT_TYPE]
    candidate_started = time.perf_counter()
    candidates, baseline, checkpoint, report = successor.generate_predraw_artifacts(
        preregistration=preregistration,
        model=model,
        target_draw_date=date.fromisoformat(
            str(checkpoint_expected["body"]["checkpoint_deadline"])[:10]
        ),
        sealed_at=datetime.fromisoformat(str(checkpoint_expected["body"]["sealed_at"])),
    )
    candidate_seconds = time.perf_counter() - candidate_started
    generated = {
        successor.MODEL_CANDIDATE_ARTIFACT_TYPE: candidates,
        successor.RANDOM_BASELINE_ARTIFACT_TYPE: baseline,
        successor.CHECKPOINT_ARTIFACT_TYPE: checkpoint,
        successor.PREDRAW_REPORT_ARTIFACT_TYPE: report,
    }
    if any(generated[key] != expected[key] for key in generated):
        raise P3PerformanceRuntimeError("frozen predraw output changed")

    replay_started = time.perf_counter()
    replay = successor.build_predraw_replay_artifact(
        model_candidates=candidates,
        random_baseline=baseline,
        checkpoint=checkpoint,
        report=report,
    )
    replay_seconds = time.perf_counter() - replay_started
    if replay != expected[successor.PREDRAW_REPLAY_ARTIFACT_TYPE]:
        raise P3PerformanceRuntimeError("frozen replay output changed")
    return {
        "status": "EXACT_REFERENCE_EQUIVALENCE_VERIFIED",
        "target_issue": TARGET_ISSUE,
        "timing_seconds": {
            "refit": refit_seconds,
            "candidate": candidate_seconds,
            "replay": replay_seconds,
            "end_to_end": time.perf_counter() - started,
        },
        "peak_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "artifact_digests": {
            key: value["artifact_digest"]
            for key, value in {
                successor.DATASET_ARTIFACT_TYPE: dataset,
                successor.MODEL_ARTIFACT_TYPE: model,
                **generated,
                successor.PREDRAW_REPLAY_ARTIFACT_TYPE: replay,
            }.items()
        },
        "probability_vector": model["body"]["probabilities_q_1_to_33"],
        "probability_sum": model["body"]["probability_sum"],
        "top100_digest": candidates["artifact_digest"],
        "baseline_digest": baseline["artifact_digest"],
        "blue_strategy_digest": checkpoint["body"]["blue_strategy_digest"],
        "configuration_drift": checkpoint["body"]["configuration_drift"],
    }


def _read_int(path: Path) -> int:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as exc:
        raise P3PerformanceRuntimeError(f"power value unavailable: {path}") from exc


def read_power_limits(*, sysfs_root: Path = Path("/sys")) -> dict[str, int]:
    return {
        "msr_pl1_uw": _read_int(sysfs_root / MSR_RELATIVE),
        "mmio_pl1_uw": _read_int(sysfs_root / MMIO_RELATIVE),
        "msr_pl2_uw": _read_int(sysfs_root / MSR_PL2_RELATIVE),
        "mmio_pl2_uw": _read_int(sysfs_root / MMIO_PL2_RELATIVE),
        "msr_pl1_max_uw": _read_int(sysfs_root / MSR_MAX_RELATIVE),
        "mmio_pl1_max_uw": _read_int(sysfs_root / MMIO_MAX_RELATIVE),
    }


def _validated_targets(*, msr_watts: int, mmio_watts: int) -> dict[Path, int]:
    if msr_watts != 40 or mmio_watts not in ALLOWED_MMIO_WATTS:
        raise P3PerformanceRuntimeError("power target is outside frozen profiles")
    return {MSR_RELATIVE: 40_000_000, MMIO_RELATIVE: mmio_watts * 1_000_000}


def _docker_sysfs_write(path: Path, value: int) -> None:
    if path not in {MSR_RELATIVE, MMIO_RELATIVE}:
        raise P3PerformanceRuntimeError("power write path is not allowlisted")
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--privileged",
            "-v",
            "/sys:/host-sys",
            "python:3.12-slim",
            "python",
            "-c",
            "from pathlib import Path; import sys; Path(sys.argv[1]).write_text(sys.argv[2])",
            str(Path("/host-sys") / path),
            str(int(value)),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def reconcile_power_limits(
    *,
    msr_watts: int,
    mmio_watts: int,
    apply: bool,
    sysfs_root: Path = Path("/sys"),
    writer: Callable[[Path, int], None] | None = None,
) -> dict[str, Any]:
    targets = _validated_targets(msr_watts=msr_watts, mmio_watts=mmio_watts)
    before = read_power_limits(sysfs_root=sysfs_root)
    if targets[MMIO_RELATIVE] > before["mmio_pl1_max_uw"]:
        raise P3PerformanceRuntimeError("MMIO target exceeds hardware maximum")
    drift = {
        path: value
        for path, value in targets.items()
        if _read_int(sysfs_root / path) != value
    }
    if drift and apply:
        use_writer = writer or _docker_sysfs_write
        for path, value in drift.items():
            use_writer(path, value)
    after = read_power_limits(sysfs_root=sysfs_root)
    readback = {
        MSR_RELATIVE: after["msr_pl1_uw"],
        MMIO_RELATIVE: after["mmio_pl1_uw"],
    }
    if apply and any(readback[path] != value for path, value in targets.items()):
        raise P3PerformanceRuntimeError("power target readback mismatch")
    return {
        "status": "APPLIED_AND_VERIFIED" if apply else "READ_ONLY",
        "targets_uw": {str(path): value for path, value in targets.items()},
        "before": before,
        "after": after,
        "drifted_paths": [str(path) for path in drift],
        "write_count": len(drift) if apply else 0,
    }


def reconcile_platform_profile(*, apply: bool) -> dict[str, Any]:
    try:
        before = PLATFORM_PROFILE_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise P3PerformanceRuntimeError("platform profile is unavailable") from exc
    changed = before != "performance"
    if changed and apply:
        subprocess.run(
            ["powerprofilesctl", "set", "performance"],
            check=True,
            capture_output=True,
            text=True,
        )
    after = PLATFORM_PROFILE_PATH.read_text(encoding="utf-8").strip()
    if apply and after != "performance":
        raise P3PerformanceRuntimeError("platform profile readback mismatch")
    return {
        "status": "APPLIED_AND_VERIFIED" if apply else "READ_ONLY",
        "before": before,
        "after": after,
        "changed": changed and apply,
        "target": "performance",
    }


def _throttle_counts() -> dict[str, int]:
    output: dict[str, int] = {}
    paths = tuple(
        Path("/sys/devices/system/cpu").glob("cpu*/thermal_throttle/*_throttle_count")
    ) + tuple(
        Path("/sys/devices/system/cpu").glob(
            "cpu*/thermal_throttle/*_throttle_total_time_ms"
        )
    )
    for path in sorted(paths):
        try:
            output[str(path)] = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
    return output


@dataclass
class TelemetrySampler:
    interval: float = 0.25

    def __post_init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None

    def start(self) -> None:
        self._before = _throttle_counts()
        turbostat = Path("/usr/lib/linux-tools") / os.uname().release / "turbostat"
        if not turbostat.is_file():
            raise P3PerformanceRuntimeError("turbostat binary is unavailable")
        command = [
            "docker",
            "run",
            "--rm",
            "--privileged",
            "--pid",
            "host",
            "-v",
            f"{turbostat}:/host-turbostat:ro",
            "python:3.12-slim",
            "/host-turbostat",
            "--quiet",
            "--Summary",
            "--show",
            "Busy%,Bzy_MHz,PkgWatt,PkgTmp,CoreTmp,TSC_MHz",
            "--interval",
            str(self.interval),
            "--num_iterations",
            "100000",
        ]
        self._process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def stop(self) -> dict[str, Any]:
        if self._process is None:
            raise P3PerformanceRuntimeError("telemetry sampler was not started")
        self._process.terminate()
        try:
            stdout, stderr = self._process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            stdout, stderr = self._process.communicate(timeout=5)
        rows: list[dict[str, float]] = []
        for item in csv.DictReader(stdout.splitlines(), delimiter="\t"):
            try:
                rows.append(
                    {
                        "busy_percent": float(item["Busy%"]),
                        "frequency_mhz": float(item["Bzy_MHz"]),
                        "pkg_watt": float(item["PkgWatt"]),
                        "temperature_c": float(item["PkgTmp"]),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
        if not rows:
            raise P3PerformanceRuntimeError(
                f"turbostat telemetry unavailable: {stderr.strip()}"
            )
        after = _throttle_counts()
        values = rows
        return {
            "sample_count": len(values),
            "pkg_watt_mean": (
                statistics.fmean(item["pkg_watt"] for item in values)
                if values
                else None
            ),
            "pkg_watt_peak": (
                max(item["pkg_watt"] for item in values) if values else None
            ),
            "temperature_c_peak": (max(item["temperature_c"] for item in values)),
            "frequency_mhz_mean": statistics.fmean(
                item["frequency_mhz"] for item in values
            ),
            "frequency_mhz_peak": max(item["frequency_mhz"] for item in values),
            "busy_percent_mean": statistics.fmean(
                item["busy_percent"] for item in values
            ),
            "busy_percent_peak": max(item["busy_percent"] for item in values),
            "thermal_throttle_count_delta": sum(
                max(0, value - self._before.get(path, value))
                for path, value in after.items()
                if path.endswith("_count")
            ),
            "thermal_throttle_time_ms_delta": sum(
                max(0, value - self._before.get(path, value))
                for path, value in after.items()
                if path.endswith("_total_time_ms")
            ),
        }


def read_runtime_telemetry() -> dict[str, Any]:
    sampler = TelemetrySampler(interval=0.1)
    sampler.start()
    time.sleep(0.6)
    return sampler.stop()


def benchmark_matrix() -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for outer in OUTER_VALUES:
        values.append(
            {"family": "outer", "outer": outer, "inner": 1, "affinity": "all"}
        )
    for inner in INNER_VALUES:
        values.append(
            {"family": "inner", "outer": 1, "inner": inner, "affinity": "all"}
        )
    for outer, inner in HYBRID_VALUES:
        values.append(
            {
                "family": "hybrid",
                "outer": outer,
                "inner": inner,
                "affinity": "all",
            }
        )
    for affinity in AFFINITIES:
        values.append(
            {
                "family": "affinity",
                "outer": 1,
                "inner": 1,
                "affinity": affinity,
            }
        )
    unique: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()
    for item in values:
        identity = (item["outer"], item["inner"], item["affinity"])
        if identity not in seen:
            unique.append(item)
            seen.add(identity)
    return unique


def _reference_command(
    fixture: Path,
    *,
    inner: int,
    affinity: str,
    thread_profile: str | None = None,
) -> tuple[list[str], dict[str, str]]:
    env = os.environ.copy()
    values = (
        THREAD_PROFILES[thread_profile]
        if thread_profile is not None
        else {
            key: inner
            for key in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        }
    )
    for key, value in values.items():
        env[key] = str(value)
    command = [
        "taskset",
        "-c",
        AFFINITIES[affinity],
        sys.executable,
        str(Path(__file__).resolve()),
        "reference-run",
        "--fixture",
        str(fixture),
    ]
    return command, env


def _run_child(
    fixture: Path,
    *,
    inner: int,
    affinity: str,
    thread_profile: str | None = None,
) -> dict[str, Any]:
    command, env = _reference_command(
        fixture,
        inner=inner,
        affinity=affinity,
        thread_profile=thread_profile,
    )
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(completed.stdout)


def _measure_config(
    fixture: Path,
    *,
    config: Mapping[str, Any],
    measured_runs: int,
    perform_warmup: bool = True,
) -> dict[str, Any]:
    outer = int(config["outer"])
    inner = int(config["inner"])
    affinity = str(config["affinity"])
    thread_profile = config.get("thread_profile")
    if perform_warmup:
        _run_child(
            fixture,
            inner=inner,
            affinity=affinity,
            thread_profile=thread_profile,
        )
    measurements: list[dict[str, Any]] = []
    telemetry = TelemetrySampler()
    telemetry.start()
    try:
        for _ in range(measured_runs):
            started = time.perf_counter()
            outputs: list[dict[str, Any]] = []
            with ThreadPoolExecutor(max_workers=outer) as pool:
                futures = [
                    pool.submit(
                        _run_child,
                        fixture,
                        inner=inner,
                        affinity=affinity,
                        thread_profile=thread_profile,
                    )
                    for _ in range(outer)
                ]
                for future in as_completed(futures):
                    outputs.append(future.result())
            wall = time.perf_counter() - started
            if len(outputs) != outer or any(
                item["status"] != "EXACT_REFERENCE_EQUIVALENCE_VERIFIED"
                for item in outputs
            ):
                raise P3PerformanceRuntimeError("benchmark equivalence failed")
            measurements.append(
                {
                    "wall_seconds": wall,
                    "workloads": outer,
                    "workloads_per_second": outer / wall,
                    "median_reference_seconds": statistics.median(
                        item["timing_seconds"]["end_to_end"] for item in outputs
                    ),
                    "median_phase_seconds": {
                        phase: statistics.median(
                            item["timing_seconds"][phase] for item in outputs
                        )
                        for phase in ("refit", "candidate", "replay", "end_to_end")
                    },
                    "peak_rss_kib_sum": sum(item["peak_rss_kib"] for item in outputs),
                }
            )
    finally:
        telemetry_output = telemetry.stop()
    return _summarize_config(
        config=config,
        measurements=measurements,
        telemetry=telemetry_output,
        warmup_runs=int(perform_warmup),
    )


def _summarize_config(
    *,
    config: Mapping[str, Any],
    measurements: Sequence[Mapping[str, Any]],
    telemetry: Mapping[str, Any],
    warmup_runs: int,
) -> dict[str, Any]:
    if not measurements:
        raise P3PerformanceRuntimeError("benchmark measurements are missing")
    return {
        **dict(config),
        "warmup_runs": warmup_runs,
        "measured_runs": len(measurements),
        "measurements": list(measurements),
        "median_wall_seconds": statistics.median(
            item["wall_seconds"] for item in measurements
        ),
        "median_workloads_per_second": statistics.median(
            item["workloads_per_second"] for item in measurements
        ),
        "median_reference_seconds": statistics.median(
            item["median_reference_seconds"] for item in measurements
        ),
        "median_phase_seconds": {
            phase: statistics.median(
                item["median_phase_seconds"][phase] for item in measurements
            )
            for phase in ("refit", "candidate", "replay", "end_to_end")
        },
        "peak_rss_kib": max(item["peak_rss_kib_sum"] for item in measurements),
        "telemetry": dict(telemetry),
        "exact_output_equivalence": True,
    }


def _merge_telemetry(values: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total_samples = sum(int(item["sample_count"]) for item in values)
    if total_samples <= 0:
        raise P3PerformanceRuntimeError("benchmark telemetry samples are missing")
    mean_fields = (
        "pkg_watt_mean",
        "frequency_mhz_mean",
        "busy_percent_mean",
    )
    peak_fields = (
        "pkg_watt_peak",
        "temperature_c_peak",
        "frequency_mhz_peak",
        "busy_percent_peak",
    )
    output: dict[str, Any] = {"sample_count": total_samples}
    for field in mean_fields:
        output[field] = (
            sum(float(item[field]) * int(item["sample_count"]) for item in values)
            / total_samples
        )
    for field in peak_fields:
        output[field] = max(float(item[field]) for item in values)
    for field in (
        "thermal_throttle_count_delta",
        "thermal_throttle_time_ms_delta",
    ):
        output[field] = sum(int(item[field]) for item in values)
    return output


def _merge_config_results(values: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    first = values[0]
    config = {
        key: first[key]
        for key in ("family", "outer", "inner", "affinity", "thread_profile")
        if key in first
    }
    measurements = [
        measurement for item in values for measurement in item["measurements"]
    ]
    return _summarize_config(
        config=config,
        measurements=measurements,
        telemetry=_merge_telemetry([item["telemetry"] for item in values]),
        warmup_runs=sum(int(item["warmup_runs"]) for item in values),
    )


def _config_identity(value: Mapping[str, Any]) -> tuple[int, int, str, str | None]:
    return (
        int(value["outer"]),
        int(value["inner"]),
        str(value["affinity"]),
        None if value.get("thread_profile") is None else str(value["thread_profile"]),
    )


def run_benchmark(
    *,
    fixture: Path,
    runs: int,
    selected_only: bool,
    selected_inner: int,
    selected_affinity: str,
    selected_thread_profile: str | None = None,
) -> dict[str, Any]:
    if runs < 5:
        raise P3PerformanceRuntimeError(
            "benchmark requires at least five measured runs"
        )
    matrix = (
        [
            {
                "family": "selected",
                "outer": 1,
                "inner": selected_inner,
                "affinity": selected_affinity,
                "thread_profile": selected_thread_profile,
            }
        ]
        if selected_only
        else benchmark_matrix()
    )
    results = [
        _measure_config(fixture, config=item, measured_runs=runs) for item in matrix
    ]
    eligible = [item for item in results if item["outer"] == 1]
    ordered = sorted(eligible, key=lambda item: item["median_reference_seconds"])
    if len(ordered) >= 2:
        gap = (
            ordered[1]["median_reference_seconds"]
            / ordered[0]["median_reference_seconds"]
            - 1.0
        )
        if gap < 0.02 and runs < 9:
            finalists = [ordered[0], ordered[1]]
            extensions: dict[tuple[int, int, str, str | None], list[dict[str, Any]]] = {
                _config_identity(item): [] for item in finalists
            }
            for round_index in range(9 - runs):
                round_values = finalists if round_index % 2 == 0 else finalists[::-1]
                for finalist in round_values:
                    extensions[_config_identity(finalist)].append(
                        _measure_config(
                            fixture,
                            config={
                                key: finalist[key]
                                for key in (
                                    "family",
                                    "outer",
                                    "inner",
                                    "affinity",
                                    "thread_profile",
                                )
                                if key in finalist
                            },
                            measured_runs=1,
                            perform_warmup=False,
                        )
                    )
            replacements = {
                identity: _merge_config_results(
                    [
                        next(
                            item
                            for item in results
                            if _config_identity(item) == identity
                        ),
                        *extension,
                    ]
                )
                for identity, extension in extensions.items()
            }
            results = [
                replacements.get(_config_identity(item), item) for item in results
            ]
            eligible = [item for item in results if item["outer"] == 1]
            ordered = sorted(
                eligible, key=lambda item: item["median_reference_seconds"]
            )
    selected = ordered[0]
    return {
        "status": "BENCHMARK_COMPLETE",
        "matrix": results,
        "selected": {
            "outer": 1,
            "inner": selected["inner"],
            "affinity": selected["affinity"],
            "affinity_cpus": AFFINITIES[selected["affinity"]],
            "thread_profile": selected.get("thread_profile"),
            "thread_environment": (
                THREAD_PROFILES[selected["thread_profile"]]
                if selected.get("thread_profile") is not None
                else {
                    key: selected["inner"]
                    for key in (
                        "OMP_NUM_THREADS",
                        "OPENBLAS_NUM_THREADS",
                        "MKL_NUM_THREADS",
                        "NUMEXPR_NUM_THREADS",
                    )
                }
            ),
            "median_reference_seconds": selected["median_reference_seconds"],
            "median_wall_seconds": selected["median_wall_seconds"],
            "selection_rule": "MINIMUM_MEDIAN_FROZEN_WORKLOAD_END_TO_END_SECONDS",
        },
        "outer_concurrency_credit": "BATCH_THROUGHPUT_DIAGNOSTIC_ONLY",
        "scientific_identity_changed": False,
    }


def run_power_profile_benchmark(
    *,
    fixture: Path,
    selected: Mapping[str, Any],
    runs: int,
) -> dict[str, Any]:
    if runs < 5:
        raise P3PerformanceRuntimeError(
            "power profile benchmark requires at least five measured runs"
        )
    config = {
        "family": "power_profile",
        "outer": 1,
        "inner": int(selected["inner"]),
        "affinity": str(selected["affinity"]),
        "thread_profile": str(selected["thread_profile"]),
    }
    values: dict[int, list[dict[str, Any]]] = {item: [] for item in ALLOWED_MMIO_WATTS}
    trial_order: list[int] = []

    def measure_round(round_index: int) -> None:
        order = list(ALLOWED_MMIO_WATTS)
        if round_index % 2:
            order.reverse()
        for mmio_watts in order:
            power = reconcile_power_limits(
                msr_watts=40,
                mmio_watts=mmio_watts,
                apply=True,
            )
            measured = _measure_config(
                fixture,
                config=config,
                measured_runs=1,
                perform_warmup=not values[mmio_watts],
            )
            measured["configured_power"] = {
                "msr_pl1_w": 40,
                "mmio_pl1_w": mmio_watts,
            }
            measured["power_readback"] = power["after"]
            values[mmio_watts].append(measured)
            trial_order.append(mmio_watts)

    for index in range(runs):
        measure_round(index)
    merged = {watts: _merge_config_results(items) for watts, items in values.items()}
    ordered = sorted(
        merged,
        key=lambda watts: merged[watts]["median_reference_seconds"],
    )
    gap = (
        merged[ordered[1]]["median_reference_seconds"]
        / merged[ordered[0]]["median_reference_seconds"]
        - 1.0
    )
    if gap < 0.02 and runs < 9:
        for index in range(runs, 9):
            measure_round(index)
        merged = {
            watts: _merge_config_results(items) for watts, items in values.items()
        }

    profiles: list[dict[str, Any]] = []
    for mmio_watts in ALLOWED_MMIO_WATTS:
        measurement = merged[mmio_watts]
        telemetry = measurement["telemetry"]
        stable = (
            telemetry["thermal_throttle_time_ms_delta"] == 0
            and float(telemetry["temperature_c_peak"]) < 100.0
        )
        profiles.append(
            {
                "msr_watts": 40,
                "mmio_watts": mmio_watts,
                "stable": stable,
                "benchmark": measurement,
                "power_readbacks": [
                    item["power_readback"] for item in values[mmio_watts]
                ],
            }
        )
    eligible = [item for item in profiles if item["stable"]]
    if not eligible:
        raise P3PerformanceRuntimeError("no stable power profile")
    winner = min(
        eligible,
        key=lambda item: item["benchmark"]["median_reference_seconds"],
    )
    return {
        "status": "POWER_PROFILE_BENCHMARK_COMPLETE",
        "profiles": profiles,
        "trial_order_mmio_watts": trial_order,
        "selected": {"msr_watts": 40, "mmio_watts": winner["mmio_watts"]},
        "selection_rule": "FASTEST_VERIFIED_STABLE_FROZEN_WORKLOAD_END_TO_END",
    }


def run_baseline(*, bundle: Mapping[str, Any], runs: int) -> dict[str, Any]:
    if runs < 5:
        raise P3PerformanceRuntimeError("baseline requires at least five measured runs")
    with tempfile.TemporaryDirectory(prefix="dehps-p3-baseline-") as temp:
        fixture = Path(temp) / "reference.json"
        _json_write(fixture, bundle)

        def run_once() -> dict[str, Any]:
            started = time.perf_counter()
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "reference-run",
                    "--fixture",
                    str(fixture),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            output = json.loads(completed.stdout)
            output["process_wall_seconds"] = time.perf_counter() - started
            return output

        run_once()
        telemetry = TelemetrySampler()
        telemetry.start()
        try:
            measurements = [run_once() for _ in range(runs)]
        finally:
            telemetry_output = telemetry.stop()
    phases = ("refit", "candidate", "replay", "end_to_end")
    return {
        "status": "BASELINE_COMPLETE",
        "warmup_runs": 1,
        "measured_runs": runs,
        "environment": {
            key: os.environ.get(key)
            for key in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
        "affinity_cpus": sorted(os.sched_getaffinity(0)),
        "median_phase_seconds": {
            phase: statistics.median(
                item["timing_seconds"][phase] for item in measurements
            )
            for phase in phases
        },
        "median_wall_seconds": statistics.median(
            item["process_wall_seconds"] for item in measurements
        ),
        "peak_rss_kib": max(item["peak_rss_kib"] for item in measurements),
        "telemetry": telemetry_output,
        "exact_output_equivalence": all(
            item["status"] == "EXACT_REFERENCE_EQUIVALENCE_VERIFIED"
            for item in measurements
        ),
    }


def _load_runtime_config(path: Path) -> dict[str, Any]:
    value = _json_load(path)
    required = {
        "schema_version",
        "selected",
        "power_profile",
        "active_interval_seconds",
        "passive_interval_seconds",
        "operator",
        "runtime_compatibility_closure",
    }
    if set(value) != required or value["schema_version"] != "dehps.p3.performance.v2":
        raise P3PerformanceRuntimeError("runtime config identity changed")
    _validate_runtime_compatibility_closure(value["runtime_compatibility_closure"])
    selected = value["selected"]
    if (
        not isinstance(selected, Mapping)
        or set(selected) != {"outer", "inner", "affinity", "thread_profile"}
        or int(selected["outer"]) != 1
        or str(selected["thread_profile"]) not in THREAD_PROFILES
        or int(selected["inner"])
        != max(THREAD_PROFILES[str(selected["thread_profile"])].values())
        or str(selected["affinity"]) not in AFFINITIES
    ):
        raise P3PerformanceRuntimeError("runtime selection changed")
    profile = value["power_profile"]
    if (
        not isinstance(profile, Mapping)
        or set(profile)
        != {"msr_watts", "mmio_watts", "msr_pl2_watts", "mmio_pl2_watts"}
        or int(profile["msr_watts"]) != 40
        or int(profile["mmio_watts"]) not in ALLOWED_MMIO_WATTS
        or int(profile["msr_pl2_watts"]) != MSR_PL2_WATTS
        or int(profile["mmio_pl2_watts"]) != MMIO_PL2_WATTS
    ):
        raise P3PerformanceRuntimeError("runtime power profile changed")
    if not 1 <= int(value["active_interval_seconds"]) <= 5:
        raise P3PerformanceRuntimeError("active watchdog interval changed")
    if int(value["passive_interval_seconds"]) < 30:
        raise P3PerformanceRuntimeError("passive watchdog interval changed")
    return value


def _mode(path: Path = DEFAULT_MODE_PATH) -> str:
    if not path.is_file():
        return "passive"
    value = _json_load(path)
    mode = str(value.get("mode") or "")
    if mode not in {"active", "passive"}:
        raise P3PerformanceRuntimeError("watchdog mode changed")
    return mode


def set_mode(*, mode: str, path: Path = DEFAULT_MODE_PATH) -> dict[str, Any]:
    if mode not in {"active", "passive"}:
        raise P3PerformanceRuntimeError("watchdog mode invalid")
    value = {"mode": mode, "changed_at": datetime.now().astimezone().isoformat()}
    _json_write(path, value)
    return value


def _p3_unit_state() -> str:
    completed = subprocess.run(
        ["systemctl", "--user", "is-active", P3_UNIT],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() or "unknown"


def watchdog_once(
    *,
    config: Mapping[str, Any],
    state_path: Path,
    apply: bool,
    mode_path: Path = DEFAULT_MODE_PATH,
    p3_unit_state_override: str | None = None,
) -> dict[str, Any]:
    mode = _mode(mode_path)
    stale_active_recovered = False
    p3_unit_state = p3_unit_state_override or _p3_unit_state()
    if (
        mode == "active"
        and apply
        and p3_unit_state
        not in {
            "active",
            "activating",
            "deactivating",
        }
    ):
        set_mode(mode="passive", path=mode_path)
        mode = "passive"
        stale_active_recovered = True
    previous = _json_load(state_path) if state_path.is_file() else {}
    count = int(previous.get("reapply_count", 0))
    profile = config["power_profile"]
    if mode == "active":
        result = reconcile_power_limits(
            msr_watts=int(profile["msr_watts"]),
            mmio_watts=int(profile["mmio_watts"]),
            apply=apply,
        )
        platform = reconcile_platform_profile(apply=apply)
        result["platform_profile"] = platform
        result["telemetry"] = read_runtime_telemetry()
        count += int(result["write_count"]) + int(platform["changed"])
    else:
        result = {"status": "PASSIVE_MONITOR", "power": read_power_limits()}
    power = result.get("after") or result.get("power") or {}
    if (
        int(power.get("msr_pl2_uw", 0)) != int(profile["msr_pl2_watts"]) * 1_000_000
        or int(power.get("mmio_pl2_uw", 0))
        != int(profile["mmio_pl2_watts"]) * 1_000_000
    ):
        raise P3PerformanceRuntimeError("monitored PL2 readback changed")
    writes = int(result.get("write_count", 0))
    changed = bool(result.get("platform_profile", {}).get("changed", False))
    now = datetime.now().astimezone().isoformat()
    telemetry = result.get("telemetry", {})
    state = {
        "schema_version": "dehps.p3.performance-watchdog-state.v1",
        "mode": mode,
        "heartbeat_at": now,
        "timestamp": now,
        "performance_mode": mode.upper(),
        "target_msr_pl1_w": int(profile["msr_watts"]),
        "actual_msr_pl1_w": power.get("msr_pl1_uw", 0) / 1_000_000,
        "target_mmio_pl1_w": int(profile["mmio_watts"]),
        "actual_mmio_pl1_w": power.get("mmio_pl1_uw", 0) / 1_000_000,
        "target_msr_pl2_w": int(profile["msr_pl2_watts"]),
        "actual_msr_pl2_w": power.get("msr_pl2_uw", 0) / 1_000_000,
        "target_mmio_pl2_w": int(profile["mmio_pl2_watts"]),
        "actual_mmio_pl2_w": power.get("mmio_pl2_uw", 0) / 1_000_000,
        "package_power_w": telemetry.get("pkg_watt_mean"),
        "busy_frequency_mhz": telemetry.get("frequency_mhz_mean"),
        "temperature_c": telemetry.get("temperature_c_peak"),
        "reapply_count": count,
        "last_reapply_at": (
            now if writes or changed else previous.get("last_reapply_at")
        ),
        "stale_active_recovered": stale_active_recovered,
        "status": (
            "ACTIVE_READBACK_VERIFIED" if mode == "active" else "PASSIVE_WAIT_FORWARD"
        ),
        "last_result": result,
    }
    if apply:
        _json_write(state_path, state)
    return state


def run_drift_fixture(
    *,
    config: Mapping[str, Any],
    state_path: Path = DEFAULT_STATE_PATH,
    mode_path: Path = DEFAULT_MODE_PATH,
) -> dict[str, Any]:
    if _mode(mode_path) != "passive":
        raise P3PerformanceRuntimeError("drift fixture requires passive mode")
    profile = config["power_profile"]
    selected_msr = int(profile["msr_watts"]) * 1_000_000
    selected_mmio = int(profile["mmio_watts"]) * 1_000_000
    alternate_msr = 28_000_000
    alternate_mmio = 28_000_000 if int(profile["mmio_watts"]) == 20 else 20_000_000
    reconcile_platform_profile(apply=True)
    reconcile_power_limits(
        msr_watts=int(profile["msr_watts"]),
        mmio_watts=int(profile["mmio_watts"]),
        apply=True,
    )
    before_count = (
        int(_json_load(state_path).get("reapply_count", 0))
        if state_path.is_file()
        else 0
    )
    drifted: dict[str, int] | None = None
    active_state: dict[str, Any] | None = None
    try:
        _docker_sysfs_write(MSR_RELATIVE, alternate_msr)
        _docker_sysfs_write(MMIO_RELATIVE, alternate_mmio)
        drifted = read_power_limits()
        if (
            drifted["msr_pl1_uw"] != alternate_msr
            or drifted["mmio_pl1_uw"] != alternate_mmio
        ):
            raise P3PerformanceRuntimeError("drift fixture injection readback mismatch")
        set_mode(mode="active", path=mode_path)
        active_state = watchdog_once(
            config=config,
            state_path=state_path,
            apply=True,
            mode_path=mode_path,
            p3_unit_state_override="activating",
        )
        actual = active_state["last_result"]["after"]
        if (
            active_state["last_result"]["write_count"] != 2
            or active_state["reapply_count"] != before_count + 2
            or actual["msr_pl1_uw"] != selected_msr
            or actual["mmio_pl1_uw"] != selected_mmio
        ):
            raise P3PerformanceRuntimeError("drift fixture reapply invariant failed")
    finally:
        reconcile_power_limits(
            msr_watts=int(profile["msr_watts"]),
            mmio_watts=int(profile["mmio_watts"]),
            apply=True,
        )
        set_mode(mode="passive", path=mode_path)
        passive_state = watchdog_once(
            config=config,
            state_path=state_path,
            apply=True,
            mode_path=mode_path,
        )
    return {
        "status": "DRIFT_REAPPLY_READBACK_VERIFIED",
        "injected": drifted,
        "active_state": active_state,
        "final_state": passive_state,
        "reapply_delta": passive_state["reapply_count"] - before_count,
        "scientific_dispatch": False,
    }


def install_runtime(
    *,
    apply: bool,
    config_path: Path,
    operator: Mapping[str, Any],
    selected_inner: int,
    selected_affinity: str,
    selected_thread_profile: str,
    mmio_watts: int,
) -> dict[str, Any]:
    if selected_thread_profile not in THREAD_PROFILES:
        raise P3PerformanceRuntimeError("install thread profile invalid")
    thread_environment = THREAD_PROFILES[selected_thread_profile]
    merged_commit = str(operator.get("merged_commit") or "")
    runtime_compatibility_closure = build_runtime_compatibility_closure(merged_commit)
    config = {
        "schema_version": "dehps.p3.performance.v2",
        "selected": {
            "outer": 1,
            "inner": selected_inner,
            "affinity": selected_affinity,
            "thread_profile": selected_thread_profile,
        },
        "power_profile": {
            "msr_watts": 40,
            "mmio_watts": mmio_watts,
            "msr_pl2_watts": MSR_PL2_WATTS,
            "mmio_pl2_watts": MMIO_PL2_WATTS,
        },
        "active_interval_seconds": 2,
        "passive_interval_seconds": 60,
        "operator": dict(operator),
        "runtime_compatibility_closure": runtime_compatibility_closure,
    }
    _validated_targets(msr_watts=40, mmio_watts=mmio_watts)
    if (
        selected_inner != max(thread_environment.values())
        or selected_affinity not in AFFINITIES
    ):
        raise P3PerformanceRuntimeError("install selection invalid")
    if apply:
        verify_operator_governance(config)
    unit_source = ROOT_DIR / "deploy/systemd/dehps-p3-performance-watchdog.service"
    dropin_source = (
        ROOT_DIR
        / "deploy/systemd/dehps-forward-prequential-successor.service.d/10-performance-runtime.conf"
    )
    unit_target = Path.home() / ".config/systemd/user" / WATCHDOG_UNIT
    dropin_target = (
        Path.home()
        / ".config/systemd/user"
        / f"{P3_UNIT}.d/10-performance-runtime.conf"
    )
    commands = [
        ["systemctl", "--user", "disable", "--now", OLD_GUARD_UNIT],
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "enable", "--now", WATCHDOG_UNIT],
    ]
    if apply:
        _json_write(config_path, config)
        unit_text = unit_source.read_text(encoding="utf-8")
        dropin_text = dropin_source.read_text(encoding="utf-8")
        if (
            dropin_text.count("DEHPS_P3_INNER_THREADS=1") != 1
            or dropin_text.count("DEHPS_P3_CPU_AFFINITY=0-21") != 1
            or dropin_text.count("CPUAffinity=0-21") != 1
        ):
            raise P3PerformanceRuntimeError("systemd runtime template changed")
        dropin_text = dropin_text.replace(
            "DEHPS_P3_INNER_THREADS=1", f"DEHPS_P3_INNER_THREADS={selected_inner}"
        )
        for variable, value in thread_environment.items():
            dropin_text = dropin_text.replace(f"{variable}=1", f"{variable}={value}")
        dropin_text = dropin_text.replace(
            "DEHPS_P3_CPU_AFFINITY=0-21",
            f"DEHPS_P3_CPU_AFFINITY={AFFINITIES[selected_affinity]}",
        ).replace("CPUAffinity=0-21", f"CPUAffinity={AFFINITIES[selected_affinity]}")
        unit_target.parent.mkdir(parents=True, exist_ok=True)
        dropin_target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(unit_target, unit_text)
        atomic_write_text(dropin_target, dropin_text)
        unit_target.chmod(0o644)
        dropin_target.chmod(0o644)
        for command in commands:
            completed = subprocess.run(
                command, check=False, capture_output=True, text=True
            )
            if command[2:4] == ["disable", "--now"] and completed.returncode != 0:
                combined = completed.stdout + completed.stderr
                if "does not exist" not in combined and "not loaded" not in combined:
                    raise P3PerformanceRuntimeError("old guard disable failed")
            elif completed.returncode != 0:
                raise P3PerformanceRuntimeError(
                    f"runtime install failed: {' '.join(command)}: {completed.stderr.strip()}"
                )
    return {
        "status": "INSTALLED" if apply else "DRY_RUN_VERIFIED",
        "config": config,
        "commands": commands,
        "installed_paths": [str(unit_target), str(dropin_target)],
        "old_guard_replaced": OLD_GUARD_UNIT,
        "p3_unit_unchanged": P3_UNIT,
    }


def compact_status(config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    limits = read_power_limits()
    state = _json_load(DEFAULT_STATE_PATH) if DEFAULT_STATE_PATH.is_file() else None
    return {
        "status": "P3_PERFORMANCE_RUNTIME_STATUS",
        "config_present": config_path.is_file(),
        "mode": _mode(),
        "power_limits": limits,
        "platform_profile": reconcile_platform_profile(apply=False),
        "watchdog": state,
        "p3_science": "UNCHANGED",
        "p4_execution": "NOT_EXECUTED",
    }


def _operator_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "request_key": args.operator_request_key,
        "request_id": args.operator_request_id,
        "approval_decision_id": args.operator_approval_decision_id,
        "execution_id": args.operator_execution_id,
        "payload_sha256": args.operator_payload_sha256,
        "merged_commit": args.merged_commit,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    reference = subparsers.add_parser("reference-run")
    reference.add_argument("--fixture", type=Path)
    benchmark = subparsers.add_parser("benchmark")
    benchmark.add_argument("--output", type=Path, required=True)
    benchmark.add_argument("--runs", type=int, default=5)
    benchmark.add_argument("--selected-only", action="store_true")
    benchmark.add_argument("--selected-inner", type=int, default=1)
    benchmark.add_argument(
        "--selected-affinity", choices=tuple(AFFINITIES), default="all"
    )
    benchmark.add_argument("--selected-thread-profile", choices=tuple(THREAD_PROFILES))
    benchmark.add_argument("--expect-msr-watts", type=int, default=40)
    benchmark.add_argument("--expect-mmio-watts", type=int, default=20)
    baseline = subparsers.add_parser("baseline")
    baseline.add_argument("--output", type=Path, required=True)
    baseline.add_argument("--runs", type=int, default=5)
    profile = subparsers.add_parser("profile-benchmark")
    profile.add_argument("--apply", action="store_true")
    profile.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    profile.add_argument("--output", type=Path, required=True)
    profile.add_argument("--runs", type=int, default=5)
    drift = subparsers.add_parser("drift-test")
    drift.add_argument("--apply", action="store_true")
    drift.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    status = subparsers.add_parser("status")
    status.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    for name in ("enter", "exit", "watch"):
        command = subparsers.add_parser(name)
        command.add_argument("--apply", action="store_true")
        command.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
        if name == "watch":
            command.add_argument("--once", action="store_true")
    install = subparsers.add_parser("install")
    install.add_argument("--apply", action="store_true")
    install.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    install.add_argument("--selected-inner", type=int, required=True)
    install.add_argument(
        "--selected-affinity", choices=tuple(AFFINITIES), required=True
    )
    install.add_argument(
        "--selected-thread-profile", choices=tuple(THREAD_PROFILES), required=True
    )
    install.add_argument(
        "--mmio-watts", type=int, choices=ALLOWED_MMIO_WATTS, required=True
    )
    install.add_argument("--operator-request-key", required=True)
    install.add_argument("--operator-request-id", type=int, required=True)
    install.add_argument("--operator-approval-decision-id", type=int, required=True)
    install.add_argument("--operator-execution-id", type=int, required=True)
    install.add_argument("--operator-payload-sha256", required=True)
    install.add_argument("--merged-commit", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "reference-run":
        bundle = _json_load(args.fixture) if args.fixture else load_reference_bundle()
        output = run_reference_bundle(bundle)
    elif args.command == "benchmark":
        limits = read_power_limits()
        if (
            limits["msr_pl1_uw"] != args.expect_msr_watts * 1_000_000
            or limits["mmio_pl1_uw"] != args.expect_mmio_watts * 1_000_000
        ):
            raise P3PerformanceRuntimeError("benchmark power profile readback changed")
        bundle = load_reference_bundle()
        with tempfile.TemporaryDirectory(prefix="dehps-p3-performance-") as temp:
            fixture = Path(temp) / "reference.json"
            _json_write(fixture, bundle)
            output = run_benchmark(
                fixture=fixture,
                runs=args.runs,
                selected_only=args.selected_only,
                selected_inner=args.selected_inner,
                selected_affinity=args.selected_affinity,
                selected_thread_profile=args.selected_thread_profile,
            )
        output["power_limits"] = limits
        _json_write(args.output, output)
    elif args.command == "baseline":
        output = run_baseline(bundle=load_reference_bundle(), runs=args.runs)
        output["power_limits"] = read_power_limits()
        _json_write(args.output, output)
    elif args.command == "status":
        output = compact_status(args.config)
    elif args.command == "drift-test":
        if not args.apply:
            raise P3PerformanceRuntimeError("drift test requires Operator --apply")
        config = _load_runtime_config(args.config)
        verify_operator_governance(config)
        output = run_drift_fixture(config=config)
    elif args.command == "profile-benchmark":
        if not args.apply:
            raise P3PerformanceRuntimeError(
                "profile benchmark requires Operator --apply"
            )
        config = _load_runtime_config(args.config)
        verify_operator_governance(config)
        bundle = load_reference_bundle()
        selected = config["selected"]
        selected_mmio = int(config["power_profile"]["mmio_watts"])
        try:
            with tempfile.TemporaryDirectory(prefix="dehps-p3-power-profile-") as temp:
                fixture = Path(temp) / "reference.json"
                _json_write(fixture, bundle)
                output = run_power_profile_benchmark(
                    fixture=fixture,
                    selected=selected,
                    runs=args.runs,
                )
            selected_mmio = int(output["selected"]["mmio_watts"])
            config["power_profile"]["mmio_watts"] = selected_mmio
            _json_write(args.config, config)
            _json_write(args.output, output)
        finally:
            reconcile_power_limits(msr_watts=40, mmio_watts=selected_mmio, apply=True)
    elif args.command in {"enter", "exit", "watch"}:
        config = _load_runtime_config(args.config)
        if args.apply:
            verify_operator_governance(config)
        if args.command == "enter":
            set_mode(mode="active") if args.apply else None
            profile = config["power_profile"]
            output = reconcile_power_limits(
                msr_watts=int(profile["msr_watts"]),
                mmio_watts=int(profile["mmio_watts"]),
                apply=args.apply,
            )
            output["platform_profile"] = reconcile_platform_profile(apply=args.apply)
        elif args.command == "exit":
            output = (
                set_mode(mode="passive")
                if args.apply
                else {"mode": "passive", "status": "DRY_RUN"}
            )
        elif args.once:
            output = watchdog_once(
                config=config, state_path=DEFAULT_STATE_PATH, apply=args.apply
            )
        else:
            if not args.apply:
                raise P3PerformanceRuntimeError("continuous watchdog requires --apply")
            while True:
                output = watchdog_once(
                    config=config, state_path=DEFAULT_STATE_PATH, apply=True
                )
                interval = (
                    config["active_interval_seconds"]
                    if output["mode"] == "active"
                    else config["passive_interval_seconds"]
                )
                time.sleep(float(interval))
    elif args.command == "install":
        output = install_runtime(
            apply=args.apply,
            config_path=args.config,
            operator=_operator_from_args(args),
            selected_inner=args.selected_inner,
            selected_affinity=args.selected_affinity,
            selected_thread_profile=args.selected_thread_profile,
            mmio_watts=args.mmio_watts,
        )
    else:  # pragma: no cover
        raise AssertionError(args.command)
    print(json.dumps(output, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
