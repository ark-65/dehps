from __future__ import annotations

import hashlib
import json
import math
import os
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from fractions import Fraction
from math import comb
from pathlib import Path
from typing import Any

import numpy as np

from dehps.artifacts import atomic_write_text
from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

from .contracts import json_compatible_copy
from .marginal_static_fixtures import (
    FIXTURE_ORDER,
    J1_FIXTURE_ID,
    M1_FIXTURE_ID,
    NULL_FIXTURE_ID,
    T1_FIXTURE_ID,
)
from .marginal_static_health_design import (
    MARGINAL_STATIC_HEALTH_DESIGN_COMPLETION_FACT,
)

MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-health-execution"
)
MARGINAL_STATIC_HEALTH_EXECUTION_CAPABILITY = (
    "m4_v2_marginal_static_measurement_health_execution"
)
MARGINAL_STATIC_HEALTH_EXECUTION_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-health-execution:COMPLETE"
)
MARGINAL_STATIC_HEALTH_DECISION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-health-decision"
)
MARGINAL_STATIC_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-v2-marginal-static-health-execution-source-v1.json"
)
MARGINAL_STATIC_HEALTH_PROGRESS_PATH = Path(
    "runtime/logs/m4-v2-marginal-static-health-execution-progress.json"
)

NUMBER_COUNT = 33
DRAW_SIZE = 6
MINIMUM_TRAINING_ISSUES = 900
REPLICATES_PER_CELL = 512
TOTAL_CELLS = 14
TOTAL_REPLICATES = 7_168
EXECUTION_SHARD_SIZE = 64
EXECUTION_SHARDS = 112
TOTAL_GENERATED_ISSUES = 15_920_128
TOTAL_OUTER_EVALUATION_ISSUES = 9_468_928
BOOTSTRAP_REPLICATES = 511
PRIMARY_BLOCK_SIZE = 5
SENSITIVITY_BLOCK_SIZES = (3, 8, 13)
LOCAL_TARGETS = (0.001, 0.01, 0.05)
UNIFORM_Q = DRAW_SIZE / NUMBER_COUNT
UNIFORM_SCORE = DRAW_SIZE * math.log2(UNIFORM_Q) + (
    NUMBER_COUNT - DRAW_SIZE
) * math.log2(1.0 - UNIFORM_Q)
LEGAL_COMBINATION_COUNT = comb(NUMBER_COUNT, DRAW_SIZE)
LEXICOGRAPHIC_HALF_BOUNDARY = (4, 7, 8, 20, 23, 30)
T1_PARTITION = 2_875_258
IS4_WEIGHTS = (
    Fraction(219, 221),
    Fraction(-1, 1),
    Fraction(1, 1),
    Fraction(-1, 1),
    Fraction(1, 1),
    Fraction(-219, 221),
    Fraction(1, 1),
)
EXPECTED_SCALES = (
    ("FORWARD_61", 961, 61),
    ("HISTORICAL_2581", 3481, 2581),
)
EXPECTED_LOCAL_ODDS = {
    0.001: 1.0331367284982704,
    0.01: 1.1085745296098741,
    0.05: 1.2594098354832832,
}


class MarginalStaticHealthExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class HealthCell:
    cell_id: str
    family: str
    fixture_id: str
    role: str
    scale_id: str
    sequence_issues: int
    evaluation_issues: int
    odds: float | None
    local_target_bits_per_issue: float | None


@dataclass(frozen=True)
class ReplicateSpec:
    cell: HealthCell
    replicate_index: int
    source_contract_digest: str

    @property
    def identity(self) -> dict[str, Any]:
        return {
            "source_contract_digest": self.source_contract_digest,
            "cell_id": self.cell.cell_id,
            "fixture_id": self.cell.fixture_id,
            "scale_id": self.cell.scale_id,
            "replicate_index": self.replicate_index,
        }

    @property
    def replicate_digest(self) -> str:
        return canonical_digest(
            self.identity,
            domain="dehps.m4.v2.marginal-static-health-replicate.v1",
        )

    @property
    def child_seed_digest(self) -> str:
        return canonical_digest(
            self.identity,
            domain="M4_V2_MARGINAL_STATIC_HEALTH_V1",
        )


@dataclass(frozen=True)
class HealthExecutionRun:
    index_artifact: Mapping[str, Any]
    health_result: Mapping[str, Any]
    completion: Mapping[str, Any]
    runtime_seconds: float
    completed_before_run: int
    completed_during_run: int
    worker_count: int

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (self.index_artifact, self.health_result, self.completion)


def load_marginal_static_health_execution_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticHealthExecutionError(
            f"marginal_static_health_execution_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-health-execution-source.v1"
        or payload.get("artifact_type")
        != "m4_v2_marginal_static_health_execution_source"
        or payload.get("contract_key")
        != "M4_V2_MARGINAL_STATIC_HEALTH_EXECUTION_SOURCE"
        or payload.get("research_request_key")
        != (
            "research-m4-v2-marginal-static-health-execution-integration-"
            "round-42-20260808"
        )
        or payload.get("research_request_id") != 325
        or payload.get("research_execution_id") != 246
        or payload.get("engineering_request_key")
        != "engineering-m4-v2-marginal-static-health-execution-round-42-20260808"
        or payload.get("engineering_request_id") != 326
        or payload.get("result_blind") is not True
        or payload.get("formal_replicates_executed") != 0
        or payload.get("generated_issues") != 0
        or payload.get("historical_outcomes_read") is not False
        or payload.get("statistical_results_read") is not False
        or payload.get("evidence_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or len(entries) != 1
        or not isinstance(frozen, dict)
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain=("dehps.m4.v2.marginal-static-health-execution-source-set.v1"),
        )
    ):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path")
        != (
            "apps/worker-python/dehps/research_os/information_theory/"
            "measurement_system_v2/marginal_static_health_execution.py"
        )
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_source_entry_invalid"
        )
    _validate_frozen_execution_contract(frozen)
    return payload


def verify_marginal_static_health_execution_source_bytes(
    *,
    root_dir: Path,
    contract: Mapping[str, Any],
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MarginalStaticHealthExecutionError(
                f"marginal_static_health_execution_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise MarginalStaticHealthExecutionError(
                f"marginal_static_health_execution_source_modified:{relative}"
            )


def build_health_cells(workload: Mapping[str, Any]) -> tuple[HealthCell, ...]:
    scales = tuple(
        (
            str(item.get("scale_id") or ""),
            int(item.get("sequence_issues", 0)),
            int(item.get("evaluation_issues", 0)),
        )
        for item in workload.get("scales", ())
    )
    if (
        scales != EXPECTED_SCALES
        or tuple(workload.get("frozen_fixture_ids", ())) != FIXTURE_ORDER
        or tuple(workload.get("local_marginal_power_targets_bits_per_issue", ()))
        != LOCAL_TARGETS
        or workload.get("replicates_per_fixture_scale_cell") != REPLICATES_PER_CELL
        or workload.get("replicates_per_local_alternative_scale_cell")
        != REPLICATES_PER_CELL
        or workload.get("total_replicates") != TOTAL_REPLICATES
        or workload.get("execution_shard_size") != EXECUTION_SHARD_SIZE
        or workload.get("execution_shards") != EXECUTION_SHARDS
    ):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_workload_changed"
        )
    roles = {
        M1_FIXTURE_ID: "POSITIVE_CONTROL",
        NULL_FIXTURE_ID: "NEGATIVE_CONTROL",
        T1_FIXTURE_ID: "NEGATIVE_CONTROL",
        J1_FIXTURE_ID: "NEGATIVE_CONTROL",
    }
    cells: list[HealthCell] = []
    for fixture_id in FIXTURE_ORDER:
        for scale_id, sequence_issues, evaluation_issues in scales:
            cells.append(
                HealthCell(
                    cell_id=f"BASE:{fixture_id}:{scale_id}",
                    family="BASE_FIXTURE",
                    fixture_id=fixture_id,
                    role=roles[fixture_id],
                    scale_id=scale_id,
                    sequence_issues=sequence_issues,
                    evaluation_issues=evaluation_issues,
                    odds=2.0 if fixture_id == M1_FIXTURE_ID else None,
                    local_target_bits_per_issue=None,
                )
            )
    calibration = {
        float(item["target_bits_per_issue"]): float(item["group_a_to_b_odds"])
        for item in workload.get("local_alternative_calibration", ())
    }
    if calibration != EXPECTED_LOCAL_ODDS:
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_local_calibration_changed"
        )
    for target in LOCAL_TARGETS:
        for scale_id, sequence_issues, evaluation_issues in scales:
            cells.append(
                HealthCell(
                    cell_id=f"LOCAL_M1:{target:.3f}:{scale_id}",
                    family="LOCAL_ALTERNATIVE",
                    fixture_id=M1_FIXTURE_ID,
                    role="LOCAL_POWER",
                    scale_id=scale_id,
                    sequence_issues=sequence_issues,
                    evaluation_issues=evaluation_issues,
                    odds=calibration[target],
                    local_target_bits_per_issue=target,
                )
            )
    if len(cells) != TOTAL_CELLS or len({cell.cell_id for cell in cells}) != len(cells):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_cell_set_invalid"
        )
    return tuple(cells)


def build_replicate_specs(
    *,
    workload: Mapping[str, Any],
    source_contract_digest: str,
) -> tuple[ReplicateSpec, ...]:
    if not _is_digest(source_contract_digest):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_source_digest_invalid"
        )
    specs = tuple(
        ReplicateSpec(
            cell=cell,
            replicate_index=replicate_index,
            source_contract_digest=source_contract_digest,
        )
        for cell in build_health_cells(workload)
        for replicate_index in range(REPLICATES_PER_CELL)
    )
    if (
        len(specs) != TOTAL_REPLICATES
        or len({spec.replicate_digest for spec in specs}) != TOTAL_REPLICATES
    ):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_replicate_set_invalid"
        )
    return specs


def run_replicate(spec: ReplicateSpec) -> dict[str, Any]:
    _validate_spec(spec)
    rng = np.random.Generator(np.random.PCG64DXSM(int(spec.child_seed_digest, 16)))
    draws, conditional_truth = _generate_sequence(spec.cell, rng)
    endpoint, truth = _score_sequence(
        draws=draws,
        cell=spec.cell,
        conditional_truth=conditional_truth,
    )
    observed_mean = float(np.mean(endpoint))
    truth_mean = float(np.mean(truth))
    blocks: dict[str, Any] = {}
    for block_size in (PRIMARY_BLOCK_SIZE, *SENSITIVITY_BLOCK_SIZES):
        block_seed_digest = canonical_digest(
            {
                "replicate_seed_digest": spec.child_seed_digest,
                "block_size": block_size,
            },
            domain="M4_V2_MARGINAL_STATIC_HEALTH_BOOTSTRAP_V1",
        )
        blocks[str(block_size)] = _moving_block_inference(
            endpoint,
            block_size=block_size,
            seed_digest=block_seed_digest,
        )
    primary = blocks[str(PRIMARY_BLOCK_SIZE)]
    values = np.asarray(
        [
            observed_mean,
            truth_mean,
            observed_mean - truth_mean,
            primary["interval_lower"],
            primary["interval_upper"],
            primary["upper_tail_p"],
        ],
        dtype=np.float64,
    )
    if not np.all(np.isfinite(values)):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_nonfinite_summary"
        )
    summary: dict[str, Any] = {
        "schema_version": "dehps-m4-v2-marginal-static-health-replicate.v1",
        "artifact_type": "m4_v2_marginal_static_health_replicate_summary",
        "artifact_digest": "",
        "replicate_digest": spec.replicate_digest,
        "child_seed_digest": spec.child_seed_digest,
        "cell": asdict(spec.cell),
        "replicate_index": spec.replicate_index,
        "sequence_issues": spec.cell.sequence_issues,
        "evaluation_issues": spec.cell.evaluation_issues,
        "observed_endpoint_bits_per_issue": observed_mean,
        "conditional_truth_bits_per_issue": truth_mean,
        "score_bias_bits_per_issue": observed_mean - truth_mean,
        "primary_interval_lower": primary["interval_lower"],
        "primary_interval_upper": primary["interval_upper"],
        "primary_upper_tail_p": primary["upper_tail_p"],
        "detected": primary["upper_tail_p"] <= 0.05,
        "truth_covered": (
            primary["interval_lower"] <= truth_mean <= primary["interval_upper"]
        ),
        "block_inference": blocks,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "legal_draw_count": spec.cell.sequence_issues,
        "illegal_draw_count": 0,
        "probability_sum_max_abs_error": 0.0,
        "database_reads_during_replicate": 0,
        "database_writes_during_replicate": 0,
        "csv_materialized": False,
        "historical_outcomes_read": False,
        "statistical_results_read": False,
        "raw_draws_retained": False,
        "numpy_version": np.__version__,
    }
    identity = dict(summary)
    identity.pop("artifact_digest")
    summary["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.v2.marginal-static-health-replicate-summary.v1",
    )
    return summary


def execute_health_program(
    *,
    root_dir: Path,
    task_key: str,
    execution_id: str,
    git_commit: str,
    task_digest: str,
    source_contract: Mapping[str, Any],
    workload_artifact: Mapping[str, Any],
    inference_artifact: Mapping[str, Any],
    design_completion: Mapping[str, Any],
    design_execution_artifact_digest: str,
    worker_count: int | None = None,
    progress_path: Path | None = None,
) -> HealthExecutionRun:
    _validate_execution_inputs(
        task_key=task_key,
        execution_id=execution_id,
        git_commit=git_commit,
        task_digest=task_digest,
        source_contract=source_contract,
        workload_artifact=workload_artifact,
        inference_artifact=inference_artifact,
        design_completion=design_completion,
        design_execution_artifact_digest=design_execution_artifact_digest,
    )
    started = time.monotonic()
    source_digest = str(source_contract["artifact_digest"])
    specs = build_replicate_specs(
        workload=workload_artifact["workload"],
        source_contract_digest=source_digest,
    )
    task_dir = root_dir / "runtime/research-os/mainline/tasks" / task_key / execution_id
    checkpoint_root = task_dir / "checkpoints"
    index_path = checkpoint_root / "completion-index.jsonl"
    context_digest = canonical_digest(
        {
            "task_key": task_key,
            "task_digest": task_digest,
            "execution_id": execution_id,
            "git_commit": git_commit,
            "source_contract_digest": source_digest,
            "design_execution_artifact_digest": design_execution_artifact_digest,
            "workload_digest": workload_artifact["artifact_digest"],
            "inference_digest": inference_artifact["artifact_digest"],
            "design_completion_digest": design_completion["artifact_digest"],
        },
        domain="dehps.m4.v2.marginal-static-health-execution-context.v1",
    )
    expected_by_digest = {spec.replicate_digest: spec for spec in specs}
    entries = load_completion_index(
        index_path,
        context_digest=context_digest,
        expected_specs=expected_by_digest,
    )
    completed_before = len(entries)
    pending = [spec for spec in specs if spec.replicate_digest not in entries]
    resolved_workers = _resolve_worker_count(worker_count)
    resolved_progress = progress_path or root_dir / MARGINAL_STATIC_HEALTH_PROGRESS_PATH
    generated_before = sum(
        int(entry["summary"]["sequence_issues"]) for entry in entries.values()
    )
    _write_progress(
        resolved_progress,
        execution_id=execution_id,
        task_digest=task_digest,
        completed_replicates=completed_before,
        generated_issues=generated_before,
        started_monotonic=started,
        completed_before_run=completed_before,
        worker_count=resolved_workers,
        status="RUNNING",
    )
    completed_during = 0
    buffer: list[dict[str, Any]] = []
    if pending:
        with ProcessPoolExecutor(
            max_workers=resolved_workers,
            initializer=_initialize_worker,
        ) as pool:
            for summary in pool.map(run_replicate, pending, chunksize=1):
                spec = expected_by_digest[str(summary["replicate_digest"])]
                entry = _persist_summary_and_build_entry(
                    checkpoint_root=checkpoint_root,
                    context_digest=context_digest,
                    spec=spec,
                    summary=summary,
                )
                buffer.append(entry)
                entries[spec.replicate_digest] = entry
                completed_during += 1
                if len(buffer) >= 8:
                    append_completion_entries(index_path, buffer)
                    buffer.clear()
                if completed_during % 8 == 0:
                    _write_progress(
                        resolved_progress,
                        execution_id=execution_id,
                        task_digest=task_digest,
                        completed_replicates=len(entries),
                        generated_issues=sum(
                            int(item["summary"]["sequence_issues"])
                            for item in entries.values()
                        ),
                        started_monotonic=started,
                        completed_before_run=completed_before,
                        worker_count=resolved_workers,
                        status="RUNNING",
                    )
    if buffer:
        append_completion_entries(index_path, buffer)
    if set(entries) != set(expected_by_digest):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_incomplete_index"
        )
    ordered_entries = tuple(entries[spec.replicate_digest] for spec in specs)
    index_artifact = build_completion_index_artifact(
        entries=ordered_entries,
        context_digest=context_digest,
        index_path=index_path,
        root_dir=root_dir,
        parent_digests=(
            source_digest,
            design_execution_artifact_digest,
            str(workload_artifact["artifact_digest"]),
            str(inference_artifact["artifact_digest"]),
            str(design_completion["artifact_digest"]),
        ),
    )
    summaries = tuple(entry["summary"] for entry in ordered_entries)
    health_result = build_health_result(
        summaries=summaries,
        index_digest=str(index_artifact["artifact_digest"]),
        workload_digest=str(workload_artifact["artifact_digest"]),
        inference_digest=str(inference_artifact["artifact_digest"]),
        parent_digests=tuple(index_artifact["parent_digests"]),
    )
    completion = build_health_completion(
        health_result=health_result,
        index_artifact=index_artifact,
        execution_id=execution_id,
        git_commit=git_commit,
        parent_digests=tuple(index_artifact["parent_digests"]),
    )
    elapsed = time.monotonic() - started
    _write_progress(
        resolved_progress,
        execution_id=execution_id,
        task_digest=task_digest,
        completed_replicates=TOTAL_REPLICATES,
        generated_issues=TOTAL_GENERATED_ISSUES,
        started_monotonic=started,
        completed_before_run=completed_before,
        worker_count=resolved_workers,
        status="COMPLETE",
    )
    return HealthExecutionRun(
        index_artifact=index_artifact,
        health_result=health_result,
        completion=completion,
        runtime_seconds=elapsed,
        completed_before_run=completed_before,
        completed_during_run=completed_during,
        worker_count=resolved_workers,
    )


def load_completion_index(
    path: Path,
    *,
    context_digest: str,
    expected_specs: Mapping[str, ReplicateSpec],
) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    if raw and not raw.endswith("\n"):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_index_truncated"
        )
    entries: dict[str, dict[str, Any]] = {}
    for line in raw.splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MarginalStaticHealthExecutionError(
                "marginal_static_health_execution_index_invalid"
            ) from exc
        if not isinstance(entry, dict):
            raise MarginalStaticHealthExecutionError(
                "marginal_static_health_execution_index_invalid"
            )
        _validate_index_entry(
            entry,
            context_digest=context_digest,
            expected_specs=expected_specs,
        )
        digest = str(entry["replicate_digest"])
        if digest in entries:
            raise MarginalStaticHealthExecutionError(
                "marginal_static_health_execution_duplicate_index_entry"
            )
        entries[digest] = entry
    return entries


def append_completion_entries(path: Path, entries: Sequence[Mapping[str, Any]]) -> None:
    if not entries:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(
        json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for entry in entries
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def build_completion_index_artifact(
    *,
    entries: Sequence[Mapping[str, Any]],
    context_digest: str,
    index_path: Path,
    root_dir: Path,
    parent_digests: Sequence[str],
) -> dict[str, Any]:
    entry_digests = [str(entry["entry_digest"]) for entry in entries]
    cell_counts = Counter(str(entry["summary"]["cell"]["cell_id"]) for entry in entries)
    try:
        relative_path = index_path.relative_to(root_dir).as_posix()
    except ValueError as exc:
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_index_path_invalid"
        ) from exc
    payload = _artifact(
        schema_version="dehps-m4-v2-marginal-static-health-completion-index.v1",
        artifact_type="m4_v2_marginal_static_health_completion_index",
        body={
            "status": "COMPLETE",
            "context_digest": context_digest,
            "index_path": relative_path,
            "index_file_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
            "entry_count": len(entry_digests),
            "entry_digests": entry_digests,
            "cell_counts": dict(sorted(cell_counts.items())),
            "completion_index_loads_per_process": 1,
            "recursive_checkpoint_scan": False,
            "database_reads_during_replicate": 0,
            "database_writes_during_replicate": 0,
            "csv_materialized": False,
            "duplicate_raw_replay": False,
            "historical_outcomes_read": False,
        },
        parent_digests=parent_digests,
        domain="dehps.m4.v2.marginal-static-health-completion-index.v1",
    )
    if (
        payload["entry_count"] != TOTAL_REPLICATES
        or set(payload["cell_counts"].values()) != {REPLICATES_PER_CELL}
        or len(payload["cell_counts"]) != TOTAL_CELLS
    ):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_index_incomplete"
        )
    return payload


def build_health_result(
    *,
    summaries: Sequence[Mapping[str, Any]],
    index_digest: str,
    workload_digest: str,
    inference_digest: str,
    parent_digests: Sequence[str],
) -> dict[str, Any]:
    if len(summaries) != TOTAL_REPLICATES:
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_summary_count_invalid"
        )
    by_cell: dict[str, list[Mapping[str, Any]]] = {}
    seen: set[str] = set()
    for summary in summaries:
        _validate_summary(summary)
        digest = str(summary["replicate_digest"])
        if digest in seen:
            raise MarginalStaticHealthExecutionError(
                "marginal_static_health_execution_duplicate_summary"
            )
        seen.add(digest)
        by_cell.setdefault(str(summary["cell"]["cell_id"]), []).append(summary)
    if len(by_cell) != TOTAL_CELLS or any(
        len(values) != REPLICATES_PER_CELL for values in by_cell.values()
    ):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_cell_completeness_invalid"
        )
    cell_results: list[dict[str, Any]] = []
    for cell_id in sorted(by_cell):
        values = sorted(by_cell[cell_id], key=lambda item: item["replicate_index"])
        cell = dict(values[0]["cell"])
        detected = sum(bool(item["detected"]) for item in values)
        covered = sum(bool(item["truth_covered"]) for item in values)
        rate = detected / REPLICATES_PER_CELL
        coverage = covered / REPLICATES_PER_CELL
        bias = (
            math.fsum(float(item["score_bias_bits_per_issue"]) for item in values)
            / REPLICATES_PER_CELL
        )
        wilson_low, wilson_high = _wilson_interval(
            detected,
            REPLICATES_PER_CELL,
            z=1.959963984540054,
        )
        gates = {
            "bias": abs(bias) <= 0.0025,
            "coverage": 0.925 <= coverage <= 0.975,
        }
        if cell["role"] == "NEGATIVE_CONTROL":
            gates["negative_rate"] = rate <= 0.075
            gates["negative_wilson_upper"] = wilson_high <= 0.09
        elif cell["role"] == "POSITIVE_CONTROL":
            gates["positive_power"] = rate >= 0.95
        elif cell["role"] == "LOCAL_POWER":
            target = float(cell["local_target_bits_per_issue"])
            if target == 0.01:
                gates["practical_power"] = rate >= 0.80
            elif target == 0.05:
                gates["strong_power"] = rate >= 0.95
        cell_results.append(
            {
                "cell": cell,
                "replicate_count": REPLICATES_PER_CELL,
                "detected_count": detected,
                "detection_rate": rate,
                "wilson_lower_95": wilson_low,
                "wilson_upper_95": wilson_high,
                "mean_score_bias_bits_per_issue": bias,
                "coverage_count": covered,
                "coverage_rate": coverage,
                "gates": gates,
                "status": "PASS" if all(gates.values()) else "FAIL",
            }
        )
    mde_by_scale: dict[str, float | str] = {}
    for scale_id, _, _ in EXPECTED_SCALES:
        local = sorted(
            (
                float(item["cell"]["local_target_bits_per_issue"]),
                float(item["detection_rate"]),
            )
            for item in cell_results
            if item["cell"]["family"] == "LOCAL_ALTERNATIVE"
            and item["cell"]["scale_id"] == scale_id
        )
        if [target for target, _ in local] != list(LOCAL_TARGETS):
            raise MarginalStaticHealthExecutionError(
                "marginal_static_health_execution_mde_grid_incomplete"
            )
        passing = [target for target, power in local if power >= 0.80]
        mde_by_scale[scale_id] = min(passing) if passing else ">0.05"
    passed = all(item["status"] == "PASS" for item in cell_results)
    return _artifact(
        schema_version="dehps-m4-v2-marginal-static-measurement-health-result.v1",
        artifact_type="m4_v2_marginal_static_measurement_health_result",
        body={
            "status": "COMPLETE",
            "measurement_health": "PASS" if passed else "REPAIR",
            "branch_id": "MARGINAL_STATIC",
            "estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "workload_digest": workload_digest,
            "inference_digest": inference_digest,
            "completion_index_digest": index_digest,
            "cell_results": cell_results,
            "cell_count": TOTAL_CELLS,
            "replicate_count": TOTAL_REPLICATES,
            "mde_by_scale_bits_per_issue": mde_by_scale,
            "generated_issues": TOTAL_GENERATED_ISSUES,
            "outer_evaluation_issues": TOTAL_OUTER_EVALUATION_ISSUES,
            "bootstrap_replicates_per_interval": BOOTSTRAP_REPLICATES,
            "all_legal": True,
            "all_finite": True,
            "all_cells_complete": True,
            "manual_or_partial_override": False,
            "accepted_model_artifact_digest": None,
            "historical_execution_status": "NOT_AUTHORIZED",
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "production_action": "none",
            "next_consumer": MARGINAL_STATIC_HEALTH_DECISION_TASK_KEY,
        },
        parent_digests=(*parent_digests, index_digest),
        domain="dehps.m4.v2.marginal-static-measurement-health-result.v1",
    )


def build_health_completion(
    *,
    health_result: Mapping[str, Any],
    index_artifact: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
    parent_digests: Sequence[str],
) -> dict[str, Any]:
    return _artifact(
        schema_version="dehps-m4-v2-marginal-static-health-execution-completion.v1",
        artifact_type="m4_v2_marginal_static_health_execution_completion",
        body={
            "status": "COMPLETE",
            "execution_id": execution_id,
            "git_commit": git_commit,
            "measurement_health": health_result["measurement_health"],
            "completion_index_digest": index_artifact["artifact_digest"],
            "health_result_digest": health_result["artifact_digest"],
            "completion_fact": MARGINAL_STATIC_HEALTH_EXECUTION_COMPLETION_FACT,
            "replicate_count": TOTAL_REPLICATES,
            "generated_issues": TOTAL_GENERATED_ISSUES,
            "outer_evaluation_issues": TOTAL_OUTER_EVALUATION_ISSUES,
            "actual_fold_count": 0,
            "historical_outcomes_read": False,
            "evidence_created": False,
            "accepted_model_artifact_digest": None,
            "next_consumer": MARGINAL_STATIC_HEALTH_DECISION_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(
            *parent_digests,
            str(index_artifact["artifact_digest"]),
            str(health_result["artifact_digest"]),
        ),
        domain="dehps.m4.v2.marginal-static-health-execution-completion.v1",
    )


def rebuild_health_artifacts_from_index(
    *,
    root_dir: Path,
    index_artifact: Mapping[str, Any],
    workload_digest: str,
    inference_digest: str,
    execution_id: str,
    git_commit: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    path = root_dir / str(index_artifact.get("index_path") or "")
    if not path.is_file() or hashlib.sha256(
        path.read_bytes()
    ).hexdigest() != index_artifact.get("index_file_sha256"):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_replay_index_changed"
        )
    raw_entries = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]
    if len(raw_entries) != TOTAL_REPLICATES or [
        entry.get("entry_digest") for entry in raw_entries
    ] != index_artifact.get("entry_digests"):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_replay_entries_changed"
        )
    summaries = tuple(entry["summary"] for entry in raw_entries)
    parent_digests = tuple(str(item) for item in index_artifact["parent_digests"])
    rebuilt_index = build_completion_index_artifact(
        entries=raw_entries,
        context_digest=str(index_artifact["context_digest"]),
        index_path=path,
        root_dir=root_dir,
        parent_digests=parent_digests,
    )
    health = build_health_result(
        summaries=summaries,
        index_digest=str(rebuilt_index["artifact_digest"]),
        workload_digest=workload_digest,
        inference_digest=inference_digest,
        parent_digests=parent_digests,
    )
    completion = build_health_completion(
        health_result=health,
        index_artifact=rebuilt_index,
        execution_id=execution_id,
        git_commit=git_commit,
        parent_digests=parent_digests,
    )
    return rebuilt_index, health, completion


def _generate_sequence(
    cell: HealthCell,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray | None]:
    if cell.fixture_id == T1_FIXTURE_ID:
        return _generate_t1(cell.sequence_issues, cell.evaluation_issues, rng)
    if cell.fixture_id == J1_FIXTURE_ID:
        return _generate_j1(cell.sequence_issues, rng), None
    odds = 1.0 if cell.fixture_id == NULL_FIXTURE_ID else cell.odds
    if odds is None or not math.isfinite(odds) or odds <= 0.0:
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_odds_invalid"
        )
    return _generate_group_iid(cell.sequence_issues, odds, rng), None


def _generate_group_iid(
    issue_count: int,
    odds: float,
    rng: np.random.Generator,
) -> np.ndarray:
    masses = _group_count_masses(16, 17, odds)
    counts = rng.choice(DRAW_SIZE + 1, size=issue_count, p=masses)
    draws = np.empty((issue_count, DRAW_SIZE), dtype=np.int8)
    group_a = np.arange(1, 17, dtype=np.int8)
    group_b = np.arange(17, 34, dtype=np.int8)
    for k in range(DRAW_SIZE + 1):
        rows = np.flatnonzero(counts == k)
        if rows.size == 0:
            continue
        left = _uniform_row_subsets(group_a, rows.size, k, rng)
        right = _uniform_row_subsets(group_b, rows.size, DRAW_SIZE - k, rng)
        draws[rows] = np.sort(np.concatenate((left, right), axis=1), axis=1)
    _validate_draws(draws)
    return draws


def _generate_t1(
    issue_count: int,
    evaluation_issues: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    draws = np.empty((issue_count, DRAW_SIZE), dtype=np.int8)
    draws[0] = _generate_group_iid(1, 1.0, rng)[0]
    evaluation_start = issue_count - evaluation_issues
    truth = np.empty((evaluation_issues, NUMBER_COUNT), dtype=np.float64)
    masses = np.asarray(
        [
            comb(6, k) * comb(27, DRAW_SIZE - k) * (2**k) / T1_PARTITION
            for k in range(DRAW_SIZE + 1)
        ],
        dtype=np.float64,
    )
    expected_overlap = float(np.dot(np.arange(7, dtype=np.float64), masses))
    q_in = expected_overlap / 6.0
    q_out = (DRAW_SIZE - expected_overlap) / 27.0
    numbers = np.arange(1, NUMBER_COUNT + 1, dtype=np.int8)
    if evaluation_start == 0:
        truth[0].fill(UNIFORM_Q)
    for issue_index in range(1, issue_count):
        previous = draws[issue_index - 1]
        overlap = int(rng.choice(DRAW_SIZE + 1, p=masses))
        inside = (
            np.empty(0, dtype=np.int8)
            if overlap == 0
            else rng.choice(previous, size=overlap, replace=False)
        )
        mask = np.ones(NUMBER_COUNT, dtype=bool)
        mask[previous.astype(np.int64) - 1] = False
        outside_pool = numbers[mask]
        outside_count = DRAW_SIZE - overlap
        outside = (
            np.empty(0, dtype=np.int8)
            if outside_count == 0
            else rng.choice(outside_pool, size=outside_count, replace=False)
        )
        draws[issue_index] = np.sort(np.concatenate((inside, outside)))
        if issue_index >= evaluation_start:
            row = truth[issue_index - evaluation_start]
            row.fill(q_out)
            row[previous.astype(np.int64) - 1] = q_in
    _validate_draws(draws)
    return draws, truth


def _generate_j1(issue_count: int, rng: np.random.Generator) -> np.ndarray:
    draws = np.empty((issue_count, DRAW_SIZE), dtype=np.int8)
    draws[0] = _generate_group_iid(1, 1.0, rng)[0]
    base = np.asarray(
        [
            comb(16, k) * comb(17, DRAW_SIZE - k) / LEGAL_COMBINATION_COUNT
            for k in range(DRAW_SIZE + 1)
        ],
        dtype=np.float64,
    )
    rows = {
        sign: np.asarray(
            [
                base[k] * (1.0 + sign * 0.5 * float(IS4_WEIGHTS[k]))
                for k in range(DRAW_SIZE + 1)
            ],
            dtype=np.float64,
        )
        for sign in (-1, 1)
    }
    group_a = np.arange(1, 17, dtype=np.int8)
    group_b = np.arange(17, 34, dtype=np.int8)
    for issue_index in range(1, issue_count):
        previous = tuple(int(value) for value in draws[issue_index - 1])
        sign = -1 if previous <= LEXICOGRAPHIC_HALF_BOUNDARY else 1
        k = int(rng.choice(DRAW_SIZE + 1, p=rows[sign]))
        left = rng.choice(group_a, size=k, replace=False) if k else group_a[:0]
        right_count = DRAW_SIZE - k
        right = (
            rng.choice(group_b, size=right_count, replace=False)
            if right_count
            else group_b[:0]
        )
        draws[issue_index] = np.sort(np.concatenate((left, right)))
    _validate_draws(draws)
    return draws


def _score_sequence(
    *,
    draws: np.ndarray,
    cell: HealthCell,
    conditional_truth: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray]:
    issue_count = int(draws.shape[0])
    evaluation_start = issue_count - cell.evaluation_issues
    if evaluation_start != MINIMUM_TRAINING_ISSUES:
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_training_boundary_changed"
        )
    indicators = np.zeros((issue_count, NUMBER_COUNT), dtype=np.uint8)
    indicators[
        np.repeat(np.arange(issue_count), DRAW_SIZE),
        draws.astype(np.int64).ravel() - 1,
    ] = 1
    cumulative = np.cumsum(indicators, axis=0, dtype=np.int64)
    counts_before = np.empty_like(cumulative)
    counts_before[0] = 0
    counts_before[1:] = cumulative[:-1]
    evaluated_counts = counts_before[evaluation_start:]
    n_before = np.arange(evaluation_start, issue_count, dtype=np.float64)
    if not np.array_equal(
        evaluated_counts.sum(axis=1),
        DRAW_SIZE * n_before.astype(np.int64),
    ):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_count_boundary_invalid"
        )
    q = (evaluated_counts + UNIFORM_Q) / (n_before[:, None] + 1.0)
    if (
        not np.all((q > 0.0) & (q < 1.0))
        or float(np.max(np.abs(q.sum(axis=1) - DRAW_SIZE))) > 1e-12
    ):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_estimator_invalid"
        )
    outcomes = indicators[evaluation_start:].astype(np.float64)
    log_selected = np.log2(q / UNIFORM_Q)
    log_unselected = np.log2((1.0 - q) / (1.0 - UNIFORM_Q))
    endpoint = np.sum(
        outcomes * log_selected + (1.0 - outcomes) * log_unselected,
        axis=1,
    )
    true_q = _truth_marginals(
        cell=cell,
        evaluation_issues=cell.evaluation_issues,
        conditional_truth=conditional_truth,
    )
    truth = np.sum(
        true_q * log_selected + (1.0 - true_q) * log_unselected,
        axis=1,
    )
    if not np.all(np.isfinite(endpoint)) or not np.all(np.isfinite(truth)):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_score_nonfinite"
        )
    return endpoint, truth


def _truth_marginals(
    *,
    cell: HealthCell,
    evaluation_issues: int,
    conditional_truth: np.ndarray | None,
) -> np.ndarray:
    if cell.fixture_id == T1_FIXTURE_ID:
        if conditional_truth is None or conditional_truth.shape != (
            evaluation_issues,
            NUMBER_COUNT,
        ):
            raise MarginalStaticHealthExecutionError(
                "marginal_static_health_execution_t1_truth_missing"
            )
        return conditional_truth
    if cell.fixture_id in {NULL_FIXTURE_ID, J1_FIXTURE_ID}:
        return np.full((evaluation_issues, NUMBER_COUNT), UNIFORM_Q)
    if cell.odds is None:
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_m1_truth_missing"
        )
    masses = _group_count_masses(16, 17, cell.odds)
    expected_a = float(np.dot(np.arange(7, dtype=np.float64), masses))
    q_a = expected_a / 16.0
    q_b = (DRAW_SIZE - expected_a) / 17.0
    if cell.local_target_bits_per_issue is not None:
        gain = _binary_composite_gain(q_a, q_b)
        if abs(gain - cell.local_target_bits_per_issue) > 1e-11:
            raise MarginalStaticHealthExecutionError(
                "marginal_static_health_execution_local_truth_changed"
            )
    row = np.concatenate(
        (
            np.full(16, q_a, dtype=np.float64),
            np.full(17, q_b, dtype=np.float64),
        )
    )
    return np.broadcast_to(row, (evaluation_issues, NUMBER_COUNT))


def _moving_block_inference(
    values: np.ndarray,
    *,
    block_size: int,
    seed_digest: str,
) -> dict[str, Any]:
    data = np.asarray(values, dtype=np.float64)
    size = int(data.size)
    if size < block_size or block_size < 1 or not _is_digest(seed_digest):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_bootstrap_invalid"
        )
    observed = float(np.mean(data))
    centered = data - observed
    full_blocks, remainder = divmod(size, block_size)
    extended = np.concatenate((centered, centered[: block_size - 1]))
    cumulative = np.concatenate(([0.0], np.cumsum(extended, dtype=np.float64)))
    starts = np.arange(size)
    block_sums = cumulative[starts + block_size] - cumulative[starts]
    rng = np.random.Generator(np.random.PCG64DXSM(int(seed_digest, 16)))
    chosen = rng.integers(
        0,
        size,
        size=(BOOTSTRAP_REPLICATES, full_blocks + int(remainder > 0)),
    )
    deviations = np.sum(block_sums[chosen[:, :full_blocks]], axis=1)
    if remainder:
        remainder_sums = cumulative[starts + remainder] - cumulative[starts]
        deviations += remainder_sums[chosen[:, -1]]
    deviations /= size
    q025, q975 = np.quantile(
        deviations,
        [0.025, 0.975],
        method="linear",
    )
    result = {
        "block_size": block_size,
        "interval_lower": float(observed - q975),
        "interval_upper": float(observed - q025),
        "upper_tail_p": float(
            (1 + int(np.count_nonzero(deviations >= observed)))
            / (BOOTSTRAP_REPLICATES + 1)
        ),
        "resample_count": BOOTSTRAP_REPLICATES,
        "quantile_method": "Hyndman-Fan type 7",
        "seed_digest": seed_digest,
    }
    if not all(
        math.isfinite(float(result[field]))
        for field in ("interval_lower", "interval_upper", "upper_tail_p")
    ):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_bootstrap_nonfinite"
        )
    return result


def _persist_summary_and_build_entry(
    *,
    checkpoint_root: Path,
    context_digest: str,
    spec: ReplicateSpec,
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_summary(summary)
    if (
        summary.get("replicate_digest") != spec.replicate_digest
        or summary.get("child_seed_digest") != spec.child_seed_digest
        or summary.get("replicate_index") != spec.replicate_index
        or summary.get("cell") != asdict(spec.cell)
    ):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_summary_identity_changed"
        )
    relative = Path("checkpoints/summaries") / f"{spec.replicate_digest}.json"
    path = checkpoint_root.parent / relative
    _persist_immutable(path, summary)
    entry: dict[str, Any] = {
        "schema_version": "dehps-m4-v2-marginal-static-health-index-entry.v1",
        "entry_digest": "",
        "context_digest": context_digest,
        "replicate_digest": spec.replicate_digest,
        "summary_digest": summary["artifact_digest"],
        "summary_path": relative.as_posix(),
        "summary": dict(summary),
    }
    identity = dict(entry)
    identity.pop("entry_digest")
    entry["entry_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.v2.marginal-static-health-index-entry.v1",
    )
    return entry


def _validate_index_entry(
    entry: Mapping[str, Any],
    *,
    context_digest: str,
    expected_specs: Mapping[str, ReplicateSpec],
) -> None:
    if set(entry) != {
        "schema_version",
        "entry_digest",
        "context_digest",
        "replicate_digest",
        "summary_digest",
        "summary_path",
        "summary",
    }:
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_index_shape_changed"
        )
    identity = dict(entry)
    supplied = identity.pop("entry_digest")
    digest = str(entry.get("replicate_digest") or "")
    summary = entry.get("summary")
    spec = expected_specs.get(digest)
    if (
        entry.get("schema_version")
        != "dehps-m4-v2-marginal-static-health-index-entry.v1"
        or supplied
        != canonical_digest(
            identity,
            domain="dehps.m4.v2.marginal-static-health-index-entry.v1",
        )
        or entry.get("context_digest") != context_digest
        or spec is None
        or not isinstance(summary, Mapping)
        or entry.get("summary_digest") != summary.get("artifact_digest")
        or entry.get("summary_path") != f"checkpoints/summaries/{digest}.json"
    ):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_index_identity_changed"
        )
    _validate_summary(summary)
    if (
        summary.get("replicate_digest") != spec.replicate_digest
        or summary.get("child_seed_digest") != spec.child_seed_digest
        or summary.get("cell") != asdict(spec.cell)
        or summary.get("replicate_index") != spec.replicate_index
    ):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_index_summary_changed"
        )


def _validate_summary(summary: Mapping[str, Any]) -> None:
    identity = dict(summary)
    supplied = identity.pop("artifact_digest", None)
    if (
        summary.get("schema_version")
        != "dehps-m4-v2-marginal-static-health-replicate.v1"
        or summary.get("artifact_type")
        != "m4_v2_marginal_static_health_replicate_summary"
        or supplied
        != canonical_digest(
            identity,
            domain="dehps.m4.v2.marginal-static-health-replicate-summary.v1",
        )
        or not _is_digest(summary.get("replicate_digest"))
        or not _is_digest(summary.get("child_seed_digest"))
        or summary.get("illegal_draw_count") != 0
        or summary.get("database_reads_during_replicate") != 0
        or summary.get("database_writes_during_replicate") != 0
        or summary.get("csv_materialized") is not False
        or summary.get("historical_outcomes_read") is not False
        or summary.get("raw_draws_retained") is not False
    ):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_summary_invalid"
        )


def _validate_execution_inputs(
    *,
    task_key: str,
    execution_id: str,
    git_commit: str,
    task_digest: str,
    source_contract: Mapping[str, Any],
    workload_artifact: Mapping[str, Any],
    inference_artifact: Mapping[str, Any],
    design_completion: Mapping[str, Any],
    design_execution_artifact_digest: str,
) -> None:
    if (
        task_key != MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY
        or not _is_digest(execution_id)
        or len(git_commit) != 40
        or not _is_digest(task_digest)
        or not _is_digest(source_contract.get("artifact_digest"))
        or workload_artifact.get("artifact_type")
        != "m4_v2_marginal_static_health_workload"
        or inference_artifact.get("artifact_type")
        != "m4_v2_marginal_static_health_inference"
        or design_completion.get("artifact_type")
        != "m4_v2_marginal_static_health_design_completion"
        or design_completion.get("completion_fact")
        != MARGINAL_STATIC_HEALTH_DESIGN_COMPLETION_FACT
        or not _is_digest(design_execution_artifact_digest)
        or workload_artifact.get("sampled_execution_status") != "NOT_AUTHORIZED"
        or workload_artifact.get("historical_outcomes_read") is not False
        or inference_artifact.get("sampled_execution_status") != "NOT_AUTHORIZED"
        or inference_artifact.get("manual_or_partial_override") != "forbidden"
        or design_completion.get("generated_issues") != 0
        or design_completion.get("synthetic_replicates") != 0
    ):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_inputs_invalid"
        )
    _validate_frozen_execution_contract(source_contract["frozen_contract"])
    build_health_cells(workload_artifact["workload"])


def _validate_frozen_execution_contract(frozen: Mapping[str, Any]) -> None:
    if (
        frozen.get("task_key") != MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY
        or frozen.get("capability") != MARGINAL_STATIC_HEALTH_EXECUTION_CAPABILITY
        or frozen.get("next_consumer") != MARGINAL_STATIC_HEALTH_DECISION_TASK_KEY
        or frozen.get("cell_count") != TOTAL_CELLS
        or frozen.get("replicates_per_cell") != REPLICATES_PER_CELL
        or frozen.get("total_replicates") != TOTAL_REPLICATES
        or frozen.get("execution_shards") != EXECUTION_SHARDS
        or frozen.get("execution_shard_size") != EXECUTION_SHARD_SIZE
        or frozen.get("total_generated_issues") != TOTAL_GENERATED_ISSUES
        or frozen.get("total_outer_evaluation_issues") != TOTAL_OUTER_EVALUATION_ISSUES
        or frozen.get("minimum_training_issues") != MINIMUM_TRAINING_ISSUES
        or frozen.get("bootstrap_replicates") != BOOTSTRAP_REPLICATES
        or frozen.get("primary_block_size") != PRIMARY_BLOCK_SIZE
        or frozen.get("sensitivity_block_sizes") != list(SENSITIVITY_BLOCK_SIZES)
        or frozen.get("database_io_during_replicate") != 0
        or frozen.get("csv_materialization") != "forbidden"
        or frozen.get("duplicate_raw_replay") != "forbidden"
        or frozen.get("routine_physical_checkpoint_scan") != "forbidden"
        or frozen.get("historical_outcomes_read") is not False
        or frozen.get("evidence_created") is not False
    ):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_contract_invalid"
        )


def _validate_spec(spec: ReplicateSpec) -> None:
    if (
        spec.replicate_index < 0
        or spec.replicate_index >= REPLICATES_PER_CELL
        or spec.cell.sequence_issues - spec.cell.evaluation_issues
        != MINIMUM_TRAINING_ISSUES
        or spec.cell.scale_id not in {scale_id for scale_id, _, _ in EXPECTED_SCALES}
        or not _is_digest(spec.source_contract_digest)
    ):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_spec_invalid"
        )


def _group_count_masses(group_a: int, group_b: int, odds: float) -> np.ndarray:
    values = np.asarray(
        [
            comb(group_a, k) * comb(group_b, DRAW_SIZE - k) * odds**k
            for k in range(DRAW_SIZE + 1)
        ],
        dtype=np.float64,
    )
    values /= float(np.sum(values))
    if not np.all(values >= 0.0) or abs(float(np.sum(values)) - 1.0) > 1e-15:
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_group_mass_invalid"
        )
    return values


def _uniform_row_subsets(
    values: np.ndarray,
    row_count: int,
    size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if size == 0:
        return np.empty((row_count, 0), dtype=np.int8)
    keys = rng.random((row_count, values.size))
    positions = np.argpartition(keys, size - 1, axis=1)[:, :size]
    return values[positions]


def _validate_draws(draws: np.ndarray) -> None:
    if (
        draws.ndim != 2
        or draws.shape[1] != DRAW_SIZE
        or np.any(draws < 1)
        or np.any(draws > NUMBER_COUNT)
        or np.any(np.diff(np.sort(draws, axis=1), axis=1) <= 0)
    ):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_illegal_draw"
        )


def _binary_composite_gain(q_a: float, q_b: float) -> float:
    return 16 * (
        q_a * math.log2(q_a / UNIFORM_Q)
        + (1.0 - q_a) * math.log2((1.0 - q_a) / (1.0 - UNIFORM_Q))
    ) + 17 * (
        q_b * math.log2(q_b / UNIFORM_Q)
        + (1.0 - q_b) * math.log2((1.0 - q_b) / (1.0 - UNIFORM_Q))
    )


def _wilson_interval(successes: int, total: int, *, z: float) -> tuple[float, float]:
    p = successes / total
    denominator = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denominator
    radius = (
        z
        * math.sqrt(p * (1.0 - p) / total + z * z / (4.0 * total * total))
        / denominator
    )
    return center - radius, center + radius


def _resolve_worker_count(requested: int | None) -> int:
    available = os.cpu_count() or 1
    if requested is None:
        raw = os.environ.get("DEHPS_M4_V2_HEALTH_WORKERS", "")
        requested = int(raw) if raw else min(22, available)
    if isinstance(requested, bool) or requested < 1 or requested > available:
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_worker_count_invalid"
        )
    return requested


def _initialize_worker() -> None:
    for key in (
        "OPENBLAS_NUM_THREADS",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[key] = "1"


def _write_progress(
    path: Path,
    *,
    execution_id: str,
    task_digest: str,
    completed_replicates: int,
    generated_issues: int,
    started_monotonic: float,
    completed_before_run: int,
    worker_count: int,
    status: str,
) -> None:
    elapsed = max(0.0, time.monotonic() - started_monotonic)
    completed_this_run = completed_replicates - completed_before_run
    rate = completed_this_run / elapsed if elapsed > 0.0 else 0.0
    remaining = TOTAL_REPLICATES - completed_replicates
    eta = remaining / rate if rate > 0.0 else None
    payload = {
        "schema_version": "dehps-m4-v2-marginal-static-health-progress.v1",
        "status": status,
        "execution_id": execution_id,
        "task_digest": task_digest,
        "completed_replicates": completed_replicates,
        "resumed_replicates": completed_before_run,
        "completed_replicates_this_run": completed_this_run,
        "total_replicates": TOTAL_REPLICATES,
        "completed_shards": completed_replicates // EXECUTION_SHARD_SIZE,
        "total_shards": EXECUTION_SHARDS,
        "completed_percent": 100.0 * completed_replicates / TOTAL_REPLICATES,
        "generated_issues": generated_issues,
        "planned_generated_issues": TOTAL_GENERATED_ISSUES,
        "elapsed_seconds": elapsed,
        "replicates_per_second": rate,
        "eta_seconds": eta,
        "worker_count": worker_count,
        "database_reads_during_replicate": 0,
        "database_writes_during_replicate": 0,
        "csv_materialized": False,
        "partial_scientific_results_exposed": False,
    }
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


def _persist_immutable(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise MarginalStaticHealthExecutionError(
                f"marginal_static_health_execution_checkpoint_invalid:{path}"
            ) from exc
        if existing != dict(payload):
            raise MarginalStaticHealthExecutionError(
                f"marginal_static_health_execution_checkpoint_collision:{path}"
            )
        return
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
    domain: str,
) -> dict[str, Any]:
    json_body = json_compatible_copy(body)
    if not isinstance(json_body, dict):
        raise MarginalStaticHealthExecutionError(
            "marginal_static_health_execution_artifact_invalid"
        )
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "artifact_digest": "",
        **json_body,
        "parent_digests": list(parent_digests),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
