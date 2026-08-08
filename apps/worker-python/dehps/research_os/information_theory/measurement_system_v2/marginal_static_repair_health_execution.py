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
from pathlib import Path
from typing import Any

import numpy as np

from dehps.artifacts import atomic_write_text
from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

from .contracts import json_compatible_copy
from .marginal_static_fixtures import (
    J1_FIXTURE_ID,
    M1_FIXTURE_ID,
    NULL_FIXTURE_ID,
    T1_FIXTURE_ID,
)
from .marginal_static_health_execution import (
    DRAW_SIZE,
    EXPECTED_LOCAL_ODDS,
    MINIMUM_TRAINING_ISSUES,
    NUMBER_COUNT,
    UNIFORM_Q,
    HealthCell,
    _generate_sequence,
    _group_count_masses,
    _truth_marginals,
)
from .marginal_static_repair_preregistration import (
    CALIBRATION_REPLICATES,
    EVALUATION_REPLICATES,
    EXECUTION_SHARD_SIZE,
    EXECUTION_SHARDS,
    TOTAL_GENERATED_ISSUES,
    TOTAL_OUTER_EVALUATION_ISSUES,
    TOTAL_REPLICATES,
)

MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-health-execution"
)
MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_CAPABILITY = (
    "m4_v2_marginal_static_measurement_repair_health_execution"
)
MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-repair-health-execution:COMPLETE"
)
MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-health-decision"
)
MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/"
    "m4-v2-marginal-static-repair-health-execution-source-v1.json"
)
MARGINAL_STATIC_REPAIR_HEALTH_PROGRESS_PATH = Path(
    "runtime/logs/m4-v2-marginal-static-repair-health-execution-progress.json"
)

PREREGISTRATION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-preregistration"
)
PREREGISTRATION_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-repair-preregistration:FROZEN"
)
PREREGISTRATION_EXECUTION_ID = (
    "3fec7c989d45061eb97f1fa18101471b835fbb92761a5846d16b51f4d4416cb7"
)
PREREGISTRATION_EXECUTION_DIGEST = (
    "71aabda0936955a2189d7f70d64f681fff7112180a016f64c44d67169a2a5bf1"
)
WORKLOAD_SEED_DIGEST = (
    "18ebe3459240754b0f8f4b38789a97bb28a0c2f00bea9d51fd976690e1016a84"
)
INFERENCE_GATE_DIGEST = (
    "4a4491baf21295a881451549cf7f99b668681eb11b3a890c84be26f3de41df0e"
)
PREREGISTRATION_DIGEST = (
    "db904f2a5b934a8eef9c053b698b771a36a7c79f488439601e2dc66acc551476"
)
PREREGISTRATION_COMPLETION_DIGEST = (
    "41e621cdda7e06a00b76b224ff3c6060ac7af6ad84452a23e6d904bcef6c6bcd"
)

CALIBRATION_REPLICATES_PER_SCALE = 512
EVALUATION_REPLICATES_PER_CELL = 256
SCALE_COUNT = 2
EVALUATION_CELL_COUNT = 14
MAX_REJECTING_EXCEEDANCE_COUNT = 24
CONFORMAL_DENOMINATOR = 513
STUDENT_T_CRITICAL = 1.9693105698498752
STUDENT_T_DF = 255
WILSON_Z = 1.959963984540054
IDENTITY_ABSOLUTE_ERROR_MAX = 1e-12
LOCAL_TARGETS = (0.001, 0.01, 0.05)
EXPECTED_SCALES = (
    ("FORWARD_61", 961, 61),
    ("HISTORICAL_2581", 3481, 2581),
)
EXPECTED_FEASIBILITY = {
    "FORWARD_61": {
        "0.001": 0.0871168536260234,
        "0.010": 0.22958915217193457,
        "0.050": 0.6475131406108688,
    },
    "HISTORICAL_2581": {
        "0.001": 0.5862083770694855,
        "0.010": 0.9999890785821147,
        "0.050": 0.9999999999999993,
    },
}
ROOT_SEED_DOMAIN = "M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_V1"
CALIBRATION_SEED_DOMAIN = (
    "M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_CALIBRATION_V1"
)
EVALUATION_SEED_DOMAIN = "M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_EVALUATION_V1"


class MarginalStaticRepairHealthExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class RepairHealthReplicateSpec:
    lane: str
    cell: HealthCell
    replicate_index: int
    preregistration_digest: str

    @property
    def identity(self) -> dict[str, Any]:
        return {
            "preregistration_digest": self.preregistration_digest,
            "lane": self.lane,
            "cell_id": self.cell.cell_id,
            "scale_id": self.cell.scale_id,
            "replicate_index": self.replicate_index,
        }

    @property
    def replicate_digest(self) -> str:
        return canonical_digest(
            self.identity,
            domain="dehps.m4.v2.marginal-static-repair-health-replicate.v1",
        )

    @property
    def child_seed_digest(self) -> str:
        domain = (
            CALIBRATION_SEED_DOMAIN
            if self.lane == "CALIBRATION"
            else EVALUATION_SEED_DOMAIN
        )
        return canonical_digest(self.identity, domain=domain)


@dataclass(frozen=True)
class RepairHealthExecutionRun:
    index_artifact: Mapping[str, Any]
    feasibility_artifact: Mapping[str, Any]
    health_result: Mapping[str, Any]
    completion: Mapping[str, Any]
    runtime_seconds: float
    completed_before_run: int
    completed_during_run: int
    worker_count: int

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (
            self.index_artifact,
            self.feasibility_artifact,
            self.health_result,
            self.completion,
        )


def load_marginal_static_repair_health_execution_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticRepairHealthExecutionError(
            f"marginal_static_repair_health_execution_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-repair-health-execution-source.v1"
        or payload.get("artifact_type")
        != "m4_v2_marginal_static_repair_health_execution_source"
        or payload.get("contract_key")
        != "M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_SOURCE"
        or payload.get("research_request_key")
        != "research-m4-v2-marginal-static-repair-health-execution-round-46-20260808"
        or payload.get("research_request_id") != 343
        or payload.get("research_execution_id") != 264
        or payload.get("engineering_request_key")
        != "engineering-m4-v2-marginal-static-repair-health-execution-round-46-20260808"
        or payload.get("engineering_request_id") != 344
        or payload.get("engineering_execution_id") != 265
        or payload.get("result_blind") is not True
        or payload.get("formal_replicates_executed") != 0
        or payload.get("generated_issues") != 0
        or payload.get("historical_outcomes_read") is not False
        or payload.get("round_42_statistical_results_read") is not False
        or payload.get("evidence_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or len(entries) != 2
        or not isinstance(frozen, dict)
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain=(
                "dehps.m4.v2.marginal-static-repair-health-execution-source-set.v1"
            ),
        )
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_source_invalid"
        )
    expected_paths = (
        (
            "apps/worker-python/dehps/research_os/information_theory/"
            "measurement_system_v2/marginal_static_repair_health_execution.py"
        ),
        (
            "apps/worker-python/dehps/research_os/information_theory/"
            "measurement_system_v2/marginal_static_health_execution.py"
        ),
    )
    if tuple(entry.get("path") for entry in entries if isinstance(entry, dict)) != (
        expected_paths
    ) or any(not _is_digest(entry.get("content_sha256")) for entry in entries):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_marginal_static_repair_health_execution_source_bytes(
    *,
    root_dir: Path,
    contract: Mapping[str, Any],
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MarginalStaticRepairHealthExecutionError(
                f"marginal_static_repair_health_execution_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise MarginalStaticRepairHealthExecutionError(
                f"marginal_static_repair_health_execution_source_modified:{relative}"
            )


def build_repair_health_cells(
    workload_artifact: Mapping[str, Any],
) -> tuple[HealthCell, ...]:
    _validate_workload_artifact(workload_artifact)
    roles = {
        M1_FIXTURE_ID: "POSITIVE_CONTROL",
        NULL_FIXTURE_ID: "NEGATIVE_CONTROL",
        T1_FIXTURE_ID: "NEGATIVE_CONTROL",
        J1_FIXTURE_ID: "NEGATIVE_CONTROL",
    }
    cells: list[HealthCell] = []
    for fixture_id in (M1_FIXTURE_ID, NULL_FIXTURE_ID, T1_FIXTURE_ID, J1_FIXTURE_ID):
        for scale_id, sequence_issues, evaluation_issues in EXPECTED_SCALES:
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
    for target in LOCAL_TARGETS:
        for scale_id, sequence_issues, evaluation_issues in EXPECTED_SCALES:
            cells.append(
                HealthCell(
                    cell_id=f"LOCAL_M1:{target:.3f}:{scale_id}",
                    family="LOCAL_ALTERNATIVE",
                    fixture_id=M1_FIXTURE_ID,
                    role="LOCAL_POWER",
                    scale_id=scale_id,
                    sequence_issues=sequence_issues,
                    evaluation_issues=evaluation_issues,
                    odds=EXPECTED_LOCAL_ODDS[target],
                    local_target_bits_per_issue=target,
                )
            )
    if len(cells) != EVALUATION_CELL_COUNT or len({cell.cell_id for cell in cells}) != (
        EVALUATION_CELL_COUNT
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_cell_set_invalid"
        )
    return tuple(cells)


def build_repair_health_replicate_specs(
    *,
    workload_artifact: Mapping[str, Any],
    preregistration_digest: str,
) -> tuple[RepairHealthReplicateSpec, ...]:
    if preregistration_digest != PREREGISTRATION_DIGEST:
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_preregistration_changed"
        )
    evaluation_cells = build_repair_health_cells(workload_artifact)
    specs: list[RepairHealthReplicateSpec] = []
    for scale_id, sequence_issues, evaluation_issues in EXPECTED_SCALES:
        calibration_cell = HealthCell(
            cell_id=f"CALIBRATION:{NULL_FIXTURE_ID}:{scale_id}",
            family="CALIBRATION_NULL",
            fixture_id=NULL_FIXTURE_ID,
            role="CALIBRATION_NULL",
            scale_id=scale_id,
            sequence_issues=sequence_issues,
            evaluation_issues=evaluation_issues,
            odds=None,
            local_target_bits_per_issue=None,
        )
        specs.extend(
            RepairHealthReplicateSpec(
                lane="CALIBRATION",
                cell=calibration_cell,
                replicate_index=index,
                preregistration_digest=preregistration_digest,
            )
            for index in range(CALIBRATION_REPLICATES_PER_SCALE)
        )
    specs.extend(
        RepairHealthReplicateSpec(
            lane="EVALUATION",
            cell=cell,
            replicate_index=index,
            preregistration_digest=preregistration_digest,
        )
        for cell in evaluation_cells
        for index in range(EVALUATION_REPLICATES_PER_CELL)
    )
    result = tuple(specs)
    if (
        len(result) != TOTAL_REPLICATES
        or sum(spec.lane == "CALIBRATION" for spec in result)
        != CALIBRATION_REPLICATES
        or sum(spec.lane == "EVALUATION" for spec in result)
        != EVALUATION_REPLICATES
        or len({spec.replicate_digest for spec in result}) != TOTAL_REPLICATES
        or len({spec.child_seed_digest for spec in result}) != TOTAL_REPLICATES
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_replicate_set_invalid"
        )
    return result


def run_repair_health_replicate(spec: RepairHealthReplicateSpec) -> dict[str, Any]:
    _validate_spec(spec)
    rng = np.random.Generator(np.random.PCG64DXSM(int(spec.child_seed_digest, 16)))
    draws, conditional_truth = _generate_sequence(spec.cell, rng)
    endpoint, truth, identity_error, probability_error = (
        _score_sequence_with_identity(
            draws=draws,
            cell=spec.cell,
            conditional_truth=conditional_truth,
        )
    )
    observed_mean = float(np.mean(endpoint))
    truth_mean = float(np.mean(truth))
    residual = endpoint - truth
    residual_mean = float(np.mean(residual))
    residual_rmse = float(math.sqrt(float(np.mean(np.square(residual)))))
    finite = np.asarray(
        [
            observed_mean,
            truth_mean,
            residual_mean,
            residual_rmse,
            identity_error,
            probability_error,
        ],
        dtype=np.float64,
    )
    if not np.all(np.isfinite(finite)) or identity_error > IDENTITY_ABSOLUTE_ERROR_MAX:
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_nonfinite_or_identity_failure"
        )
    summary: dict[str, Any] = {
        "schema_version": (
            "dehps-m4-v2-marginal-static-repair-health-replicate.v1"
        ),
        "artifact_type": (
            "m4_v2_marginal_static_repair_health_replicate_summary"
        ),
        "artifact_digest": "",
        "replicate_digest": spec.replicate_digest,
        "child_seed_digest": spec.child_seed_digest,
        "lane": spec.lane,
        "cell": asdict(spec.cell),
        "replicate_index": spec.replicate_index,
        "sequence_issues": spec.cell.sequence_issues,
        "evaluation_issues": spec.cell.evaluation_issues,
        "observed_endpoint_bits_per_issue": observed_mean,
        "conditional_truth_bits_per_issue": truth_mean,
        "score_residual_bits_per_issue": residual_mean,
        "score_residual_rmse_bits_per_issue": residual_rmse,
        "conditional_identity_max_abs_error": identity_error,
        "legal_draw_count": spec.cell.sequence_issues,
        "illegal_draw_count": 0,
        "probability_sum_max_abs_error": probability_error,
        "nested_bootstrap_replicates": 0,
        "database_reads_during_replicate": 0,
        "database_writes_during_replicate": 0,
        "csv_materialized": False,
        "historical_outcomes_read": False,
        "round_42_statistical_results_read": False,
        "raw_draws_retained": False,
        "numpy_version": np.__version__,
    }
    identity = dict(summary)
    identity.pop("artifact_digest")
    summary["artifact_digest"] = canonical_digest(
        identity,
        domain=(
            "dehps.m4.v2.marginal-static-repair-health-replicate-summary.v1"
        ),
    )
    return summary


def execute_repair_health_program(
    *,
    root_dir: Path,
    task_key: str,
    execution_id: str,
    git_commit: str,
    task_digest: str,
    source_contract: Mapping[str, Any],
    preregistration_execution: Mapping[str, Any],
    workload_artifact: Mapping[str, Any],
    inference_artifact: Mapping[str, Any],
    preregistration_artifact: Mapping[str, Any],
    preregistration_completion: Mapping[str, Any],
    worker_count: int | None = None,
    progress_path: Path | None = None,
) -> RepairHealthExecutionRun:
    _validate_execution_inputs(
        task_key=task_key,
        execution_id=execution_id,
        git_commit=git_commit,
        task_digest=task_digest,
        source_contract=source_contract,
        preregistration_execution=preregistration_execution,
        workload_artifact=workload_artifact,
        inference_artifact=inference_artifact,
        preregistration_artifact=preregistration_artifact,
        preregistration_completion=preregistration_completion,
    )
    started = time.monotonic()
    feasibility = build_pre_sample_feasibility_artifact(
        source_contract=source_contract,
        preregistration_digest=str(preregistration_artifact["artifact_digest"]),
        parent_digests=(
            str(source_contract["artifact_digest"]),
            str(preregistration_execution["artifact_digest"]),
            str(workload_artifact["artifact_digest"]),
            str(inference_artifact["artifact_digest"]),
            str(preregistration_artifact["artifact_digest"]),
            str(preregistration_completion["artifact_digest"]),
        ),
    )
    specs = build_repair_health_replicate_specs(
        workload_artifact=workload_artifact,
        preregistration_digest=str(preregistration_artifact["artifact_digest"]),
    )
    task_dir = root_dir / "runtime/research-os/mainline/tasks" / task_key / execution_id
    checkpoint_root = task_dir / "checkpoints"
    index_path = checkpoint_root / "completion-index.jsonl"
    parent_digests = (
        str(source_contract["artifact_digest"]),
        str(preregistration_execution["artifact_digest"]),
        str(workload_artifact["artifact_digest"]),
        str(inference_artifact["artifact_digest"]),
        str(preregistration_artifact["artifact_digest"]),
        str(preregistration_completion["artifact_digest"]),
    )
    context_digest = canonical_digest(
        {
            "task_key": task_key,
            "task_digest": task_digest,
            "execution_id": execution_id,
            "git_commit": git_commit,
            "parent_digests": list(parent_digests),
            "feasibility_digest": feasibility["artifact_digest"],
        },
        domain="dehps.m4.v2.marginal-static-repair-health-execution-context.v1",
    )
    expected_by_digest = {spec.replicate_digest: spec for spec in specs}
    entries = load_repair_health_completion_index(
        index_path,
        context_digest=context_digest,
        expected_specs=expected_by_digest,
    )
    completed_before = len(entries)
    pending = [spec for spec in specs if spec.replicate_digest not in entries]
    resolved_workers = _resolve_worker_count(worker_count)
    resolved_progress = progress_path or (
        root_dir / MARGINAL_STATIC_REPAIR_HEALTH_PROGRESS_PATH
    )
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
            for summary in pool.map(
                run_repair_health_replicate,
                pending,
                chunksize=1,
            ):
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
                    append_repair_health_completion_entries(index_path, buffer)
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
        append_repair_health_completion_entries(index_path, buffer)
    if set(entries) != set(expected_by_digest):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_incomplete_index"
        )
    ordered_entries = tuple(entries[spec.replicate_digest] for spec in specs)
    index_artifact = build_repair_health_completion_index_artifact(
        entries=ordered_entries,
        context_digest=context_digest,
        index_path=index_path,
        root_dir=root_dir,
        parent_digests=(*parent_digests, str(feasibility["artifact_digest"])),
    )
    summaries = tuple(entry["summary"] for entry in ordered_entries)
    health_result = build_repair_health_result(
        summaries=summaries,
        feasibility_artifact=feasibility,
        index_digest=str(index_artifact["artifact_digest"]),
        workload_digest=str(workload_artifact["artifact_digest"]),
        inference_digest=str(inference_artifact["artifact_digest"]),
        preregistration_digest=str(preregistration_artifact["artifact_digest"]),
        parent_digests=parent_digests,
    )
    completion = build_repair_health_completion(
        health_result=health_result,
        index_artifact=index_artifact,
        feasibility_artifact=feasibility,
        execution_id=execution_id,
        git_commit=git_commit,
        parent_digests=parent_digests,
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
    return RepairHealthExecutionRun(
        index_artifact=index_artifact,
        feasibility_artifact=feasibility,
        health_result=health_result,
        completion=completion,
        runtime_seconds=elapsed,
        completed_before_run=completed_before,
        completed_during_run=completed_during,
        worker_count=resolved_workers,
    )


def build_pre_sample_feasibility_artifact(
    *,
    source_contract: Mapping[str, Any],
    preregistration_digest: str,
    parent_digests: Sequence[str],
) -> dict[str, Any]:
    if preregistration_digest != PREREGISTRATION_DIGEST:
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_preregistration_changed"
        )
    computed: dict[str, dict[str, float]] = {}
    for scale_id, _, evaluation_issues in EXPECTED_SCALES:
        computed[scale_id] = {
            f"{target:.3f}": _exact_randomized_np_power(
                EXPECTED_LOCAL_ODDS[target],
                evaluation_issues,
            )
            for target in LOCAL_TARGETS
        }
    for scale_id, expected in EXPECTED_FEASIBILITY.items():
        for target, value in expected.items():
            if abs(computed[scale_id][target] - value) > 2e-15:
                raise MarginalStaticRepairHealthExecutionError(
                    "marginal_static_repair_health_execution_feasibility_changed"
                )
    frozen_expected = source_contract["frozen_contract"]["pre_sample_feasibility"]
    if frozen_expected["upper_power"] != EXPECTED_FEASIBILITY:
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_feasibility_contract_changed"
        )
    return _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-repair-health-feasibility.v1"
        ),
        artifact_type="m4_v2_marginal_static_repair_health_feasibility",
        body={
            "status": "FROZEN_BEFORE_EVALUATION_DISPATCH",
            "method": (
                "exact legal-six group-count convolution and randomized "
                "level-0.05 Neyman-Pearson upper envelope"
            ),
            "test_size": 0.05,
            "upper_power": computed,
            "upper_power_gate": 0.80,
            "admissible_by_power": {
                scale_id: {
                    target: value >= 0.80 for target, value in values.items()
                }
                for scale_id, values in computed.items()
            },
            "computed_before_evaluation_dispatch": True,
            "alternative_results_read": False,
            "round_42_statistical_results_read": False,
            "generated_issues": 0,
            "duplicate_validation": False,
            "historical_outcomes_read": False,
            "evidence_created": False,
            "production_action": "none",
        },
        parent_digests=parent_digests,
        domain="dehps.m4.v2.marginal-static-repair-health-feasibility.v1",
    )


def load_repair_health_completion_index(
    path: Path,
    *,
    context_digest: str,
    expected_specs: Mapping[str, RepairHealthReplicateSpec],
) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    if raw and not raw.endswith("\n"):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_index_truncated"
        )
    entries: dict[str, dict[str, Any]] = {}
    for line in raw.splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MarginalStaticRepairHealthExecutionError(
                "marginal_static_repair_health_execution_index_invalid"
            ) from exc
        if not isinstance(entry, dict):
            raise MarginalStaticRepairHealthExecutionError(
                "marginal_static_repair_health_execution_index_invalid"
            )
        _validate_index_entry(
            entry,
            context_digest=context_digest,
            expected_specs=expected_specs,
        )
        digest = str(entry["replicate_digest"])
        if digest in entries:
            raise MarginalStaticRepairHealthExecutionError(
                "marginal_static_repair_health_execution_duplicate_index_entry"
            )
        entries[digest] = entry
    return entries


def append_repair_health_completion_entries(
    path: Path,
    entries: Sequence[Mapping[str, Any]],
) -> None:
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


def build_repair_health_completion_index_artifact(
    *,
    entries: Sequence[Mapping[str, Any]],
    context_digest: str,
    index_path: Path,
    root_dir: Path,
    parent_digests: Sequence[str],
) -> dict[str, Any]:
    entry_digests = [str(entry["entry_digest"]) for entry in entries]
    lane_counts = Counter(str(entry["summary"]["lane"]) for entry in entries)
    evaluation_counts = Counter(
        str(entry["summary"]["cell"]["cell_id"])
        for entry in entries
        if entry["summary"]["lane"] == "EVALUATION"
    )
    calibration_counts = Counter(
        str(entry["summary"]["cell"]["scale_id"])
        for entry in entries
        if entry["summary"]["lane"] == "CALIBRATION"
    )
    try:
        relative_path = index_path.relative_to(root_dir).as_posix()
    except ValueError as exc:
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_index_path_invalid"
        ) from exc
    payload = _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-repair-health-completion-index.v1"
        ),
        artifact_type="m4_v2_marginal_static_repair_health_completion_index",
        body={
            "status": "COMPLETE",
            "context_digest": context_digest,
            "index_path": relative_path,
            "index_file_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
            "entry_count": len(entry_digests),
            "entry_digests": entry_digests,
            "lane_counts": dict(sorted(lane_counts.items())),
            "calibration_scale_counts": dict(sorted(calibration_counts.items())),
            "evaluation_cell_counts": dict(sorted(evaluation_counts.items())),
            "completion_index_loads_per_process": 1,
            "recursive_checkpoint_scan": False,
            "database_reads_during_replicate": 0,
            "database_writes_during_replicate": 0,
            "csv_materialized": False,
            "raw_replay": False,
            "duplicate_validation": False,
            "historical_outcomes_read": False,
        },
        parent_digests=parent_digests,
        domain=(
            "dehps.m4.v2.marginal-static-repair-health-completion-index.v1"
        ),
    )
    if (
        payload["entry_count"] != TOTAL_REPLICATES
        or payload["lane_counts"]
        != {"CALIBRATION": CALIBRATION_REPLICATES, "EVALUATION": EVALUATION_REPLICATES}
        or set(payload["calibration_scale_counts"].values())
        != {CALIBRATION_REPLICATES_PER_SCALE}
        or len(payload["calibration_scale_counts"]) != SCALE_COUNT
        or set(payload["evaluation_cell_counts"].values())
        != {EVALUATION_REPLICATES_PER_CELL}
        or len(payload["evaluation_cell_counts"]) != EVALUATION_CELL_COUNT
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_index_incomplete"
        )
    return payload


def build_repair_health_result(
    *,
    summaries: Sequence[Mapping[str, Any]],
    feasibility_artifact: Mapping[str, Any],
    index_digest: str,
    workload_digest: str,
    inference_digest: str,
    preregistration_digest: str,
    parent_digests: Sequence[str],
) -> dict[str, Any]:
    if len(summaries) != TOTAL_REPLICATES:
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_summary_count_invalid"
        )
    seen: set[str] = set()
    calibration_by_scale: dict[str, list[Mapping[str, Any]]] = {}
    evaluation_by_cell: dict[str, list[Mapping[str, Any]]] = {}
    for summary in summaries:
        _validate_summary(summary)
        digest = str(summary["replicate_digest"])
        if digest in seen:
            raise MarginalStaticRepairHealthExecutionError(
                "marginal_static_repair_health_execution_duplicate_summary"
            )
        seen.add(digest)
        if summary["lane"] == "CALIBRATION":
            calibration_by_scale.setdefault(
                str(summary["cell"]["scale_id"]), []
            ).append(summary)
        else:
            evaluation_by_cell.setdefault(
                str(summary["cell"]["cell_id"]), []
            ).append(summary)
    if (
        set(calibration_by_scale) != {item[0] for item in EXPECTED_SCALES}
        or any(
            len(values) != CALIBRATION_REPLICATES_PER_SCALE
            for values in calibration_by_scale.values()
        )
        or len(evaluation_by_cell) != EVALUATION_CELL_COUNT
        or any(
            len(values) != EVALUATION_REPLICATES_PER_CELL
            for values in evaluation_by_cell.values()
        )
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_cell_completeness_invalid"
        )
    cell_results: list[dict[str, Any]] = []
    control_failures: list[str] = []
    instrument_limits: list[str] = []
    admissible_local_count = 0
    for cell_id in sorted(evaluation_by_cell):
        values = sorted(
            evaluation_by_cell[cell_id],
            key=lambda item: int(item["replicate_index"]),
        )
        cell = dict(values[0]["cell"])
        scale_id = str(cell["scale_id"])
        calibration_scores = np.asarray(
            [
                float(item["observed_endpoint_bits_per_issue"])
                for item in calibration_by_scale[scale_id]
            ],
            dtype=np.float64,
        )
        evaluation_scores = np.asarray(
            [float(item["observed_endpoint_bits_per_issue"]) for item in values],
            dtype=np.float64,
        )
        truth_values = np.asarray(
            [float(item["conditional_truth_bits_per_issue"]) for item in values],
            dtype=np.float64,
        )
        residual_values = np.asarray(
            [float(item["score_residual_bits_per_issue"]) for item in values],
            dtype=np.float64,
        )
        rmse_values = np.asarray(
            [float(item["score_residual_rmse_bits_per_issue"]) for item in values],
            dtype=np.float64,
        )
        if not all(
            array.size == EVALUATION_REPLICATES_PER_CELL
            and np.all(np.isfinite(array))
            for array in (evaluation_scores, truth_values, residual_values, rmse_values)
        ) or calibration_scores.size != CALIBRATION_REPLICATES_PER_SCALE:
            raise MarginalStaticRepairHealthExecutionError(
                "marginal_static_repair_health_execution_nonfinite_or_wrong_count"
            )
        exceedance_counts = np.count_nonzero(
            calibration_scores[:, None] >= evaluation_scores[None, :],
            axis=0,
        )
        conformal_p = (1.0 + exceedance_counts.astype(np.float64)) / (
            CONFORMAL_DENOMINATOR
        )
        detected_mask = exceedance_counts <= MAX_REJECTING_EXCEEDANCE_COUNT
        detected_count = int(np.count_nonzero(detected_mask))
        detection_rate = detected_count / EVALUATION_REPLICATES_PER_CELL
        wilson_low, wilson_high = wilson_interval(
            detected_count,
            EVALUATION_REPLICATES_PER_CELL,
            z=WILSON_Z,
        )
        observed_interval = student_t_interval(evaluation_scores)
        truth_interval = student_t_interval(truth_values)
        residual_interval = student_t_interval(residual_values)
        identity_max = max(
            float(item["conditional_identity_max_abs_error"]) for item in values
        )
        probability_max = max(
            float(item["probability_sum_max_abs_error"]) for item in values
        )
        gates: dict[str, bool] = {
            "complete_finite": True,
            "conditional_identity": identity_max <= IDENTITY_ABSOLUTE_ERROR_MAX,
            "legal_draws_and_probabilities": probability_max <= 1e-12,
        }
        classification = str(cell["role"])
        exact_upper_power: float | None = None
        if cell["role"] == "NEGATIVE_CONTROL":
            gates["negative_control_wilson_upper"] = wilson_high <= 0.09
            classification = (
                "NEGATIVE_CONTROL_PASS"
                if gates["negative_control_wilson_upper"]
                else "NEGATIVE_CONTROL_FAIL"
            )
        elif cell["role"] == "POSITIVE_CONTROL":
            gates["positive_control_wilson_lower"] = wilson_low >= 0.80
            classification = (
                "POSITIVE_CONTROL_PASS"
                if gates["positive_control_wilson_lower"]
                else "POSITIVE_CONTROL_FAIL"
            )
        elif cell["role"] == "LOCAL_POWER":
            target_key = f"{float(cell['local_target_bits_per_issue']):.3f}"
            exact_upper_power = float(
                feasibility_artifact["upper_power"][scale_id][target_key]
            )
            admissible = exact_upper_power >= 0.80 and truth_interval["lower"] > 0.0
            gates["local_admissible"] = admissible
            if not admissible:
                classification = "SENSITIVITY_LIMIT"
            elif wilson_low >= 0.80:
                classification = "DETECTABLE"
                admissible_local_count += 1
            else:
                classification = "INSTRUMENT_LIMIT"
                admissible_local_count += 1
                instrument_limits.append(cell_id)
            gates["local_not_instrument_limit"] = (
                classification != "INSTRUMENT_LIMIT"
            )
        if not all(
            value
            for key, value in gates.items()
            if key not in {"local_admissible"}
        ) and (
            cell["role"] != "LOCAL_POWER" or classification == "INSTRUMENT_LIMIT"
        ):
            control_failures.append(cell_id)
        cell_results.append(
            {
                "cell": cell,
                "replicate_count": EVALUATION_REPLICATES_PER_CELL,
                "calibration_replicate_count": CALIBRATION_REPLICATES_PER_SCALE,
                "detected_count": detected_count,
                "detection_rate": detection_rate,
                "wilson_lower_95": wilson_low,
                "wilson_upper_95": wilson_high,
                "min_conformal_p": float(np.min(conformal_p)),
                "max_conformal_p": float(np.max(conformal_p)),
                "max_rejecting_exceedance_count": MAX_REJECTING_EXCEEDANCE_COUNT,
                "observed_mean_interval_95": observed_interval,
                "conditional_truth_interval_95": truth_interval,
                "conditional_truth_positive_fraction": float(
                    np.count_nonzero(truth_values > 0.0)
                    / EVALUATION_REPLICATES_PER_CELL
                ),
                "score_residual_interval_95": residual_interval,
                "mean_score_residual_rmse_bits_per_issue": float(
                    np.mean(rmse_values)
                ),
                "conditional_identity_max_abs_error": identity_max,
                "probability_sum_max_abs_error": probability_max,
                "exact_np_upper_power": exact_upper_power,
                "classification": classification,
                "gates": gates,
            }
        )
    mde_by_scale: dict[str, float | str] = {}
    for scale_id, _, _ in EXPECTED_SCALES:
        detectable = sorted(
            float(item["cell"]["local_target_bits_per_issue"])
            for item in cell_results
            if item["cell"]["scale_id"] == scale_id
            and item["cell"]["role"] == "LOCAL_POWER"
            and item["classification"] == "DETECTABLE"
        )
        mde_by_scale[scale_id] = min(detectable) if detectable else ">0.05"
    structural_pass = all(
        item["gates"]["complete_finite"]
        and item["gates"]["conditional_identity"]
        and item["gates"]["legal_draws_and_probabilities"]
        for item in cell_results
    )
    if not structural_pass or control_failures or instrument_limits:
        preliminary = "REPAIR"
    elif admissible_local_count > 0:
        preliminary = "PASS"
    else:
        preliminary = "INCONCLUSIVE_DUE_TO_SENSITIVITY"
    return _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-repaired-measurement-health-result.v1"
        ),
        artifact_type="m4_v2_marginal_static_repaired_measurement_health_result",
        body={
            "status": "COMPLETE_PENDING_DECISION_REPLAY",
            "preliminary_measurement_health": preliminary,
            "authoritative_decision": None,
            "branch_id": "MARGINAL_STATIC",
            "estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "workload_digest": workload_digest,
            "inference_digest": inference_digest,
            "preregistration_digest": preregistration_digest,
            "completion_index_digest": index_digest,
            "feasibility_digest": feasibility_artifact["artifact_digest"],
            "cell_results": cell_results,
            "cell_count": EVALUATION_CELL_COUNT,
            "calibration_replicate_count": CALIBRATION_REPLICATES,
            "evaluation_replicate_count": EVALUATION_REPLICATES,
            "replicate_count": TOTAL_REPLICATES,
            "admissible_local_cell_count": admissible_local_count,
            "control_failure_cell_ids": sorted(set(control_failures)),
            "instrument_limit_cell_ids": sorted(set(instrument_limits)),
            "mde_by_scale_bits_per_issue": mde_by_scale,
            "generated_issues": TOTAL_GENERATED_ISSUES,
            "outer_evaluation_issues": TOTAL_OUTER_EVALUATION_ISSUES,
            "nested_bootstrap_replicates": 0,
            "all_legal": True,
            "all_finite": True,
            "all_cells_complete": True,
            "conditional_identity_pass": structural_pass,
            "manual_or_partial_override": False,
            "automatic_pass_from_sensitivity_limits": False,
            "accepted_model_artifact_digest": None,
            "historical_execution_status": "NOT_AUTHORIZED",
            "historical_outcomes_read": False,
            "round_42_statistical_results_read": False,
            "evidence_created": False,
            "promotion_gate_opened": False,
            "production_action": "none",
            "next_consumer": MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY,
        },
        parent_digests=(
            *parent_digests,
            str(feasibility_artifact["artifact_digest"]),
            index_digest,
        ),
        domain=(
            "dehps.m4.v2.marginal-static-repaired-measurement-health-result.v1"
        ),
    )


def build_repair_health_completion(
    *,
    health_result: Mapping[str, Any],
    index_artifact: Mapping[str, Any],
    feasibility_artifact: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
    parent_digests: Sequence[str],
) -> dict[str, Any]:
    return _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-repair-health-execution-completion.v1"
        ),
        artifact_type=(
            "m4_v2_marginal_static_repair_health_execution_completion"
        ),
        body={
            "status": "COMPLETE",
            "execution_id": execution_id,
            "git_commit": git_commit,
            "preliminary_measurement_health": health_result[
                "preliminary_measurement_health"
            ],
            "authoritative_decision": None,
            "completion_index_digest": index_artifact["artifact_digest"],
            "feasibility_digest": feasibility_artifact["artifact_digest"],
            "health_result_digest": health_result["artifact_digest"],
            "completion_fact": (
                MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_COMPLETION_FACT
            ),
            "replicate_count": TOTAL_REPLICATES,
            "calibration_replicates": CALIBRATION_REPLICATES,
            "evaluation_replicates": EVALUATION_REPLICATES,
            "generated_issues": TOTAL_GENERATED_ISSUES,
            "outer_evaluation_issues": TOTAL_OUTER_EVALUATION_ISSUES,
            "nested_bootstrap_replicates": 0,
            "duplicate_validation": False,
            "raw_replay": False,
            "actual_fold_count": 0,
            "historical_outcomes_read": False,
            "round_42_statistical_results_read": False,
            "evidence_created": False,
            "promotion_gate_opened": False,
            "accepted_model_artifact_digest": None,
            "next_consumer": MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(
            *parent_digests,
            str(index_artifact["artifact_digest"]),
            str(feasibility_artifact["artifact_digest"]),
            str(health_result["artifact_digest"]),
        ),
        domain=(
            "dehps.m4.v2.marginal-static-repair-health-execution-completion.v1"
        ),
    )


def rebuild_repair_health_artifacts_from_index(
    *,
    root_dir: Path,
    source_contract: Mapping[str, Any],
    index_artifact: Mapping[str, Any],
    workload_digest: str,
    inference_digest: str,
    preregistration_digest: str,
    execution_id: str,
    git_commit: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    path = root_dir / str(index_artifact.get("index_path") or "")
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != (
        index_artifact.get("index_file_sha256")
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_replay_index_changed"
        )
    raw_entries = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]
    if len(raw_entries) != TOTAL_REPLICATES or [
        entry.get("entry_digest") for entry in raw_entries
    ] != index_artifact.get("entry_digests"):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_replay_entries_changed"
        )
    parent_digests_with_feasibility = tuple(
        str(item) for item in index_artifact["parent_digests"]
    )
    parent_digests = parent_digests_with_feasibility[:-1]
    feasibility = build_pre_sample_feasibility_artifact(
        source_contract=source_contract,
        preregistration_digest=preregistration_digest,
        parent_digests=parent_digests,
    )
    if feasibility["artifact_digest"] != parent_digests_with_feasibility[-1]:
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_replay_feasibility_changed"
        )
    rebuilt_index = build_repair_health_completion_index_artifact(
        entries=raw_entries,
        context_digest=str(index_artifact["context_digest"]),
        index_path=path,
        root_dir=root_dir,
        parent_digests=parent_digests_with_feasibility,
    )
    health = build_repair_health_result(
        summaries=tuple(entry["summary"] for entry in raw_entries),
        feasibility_artifact=feasibility,
        index_digest=str(rebuilt_index["artifact_digest"]),
        workload_digest=workload_digest,
        inference_digest=inference_digest,
        preregistration_digest=preregistration_digest,
        parent_digests=parent_digests,
    )
    completion = build_repair_health_completion(
        health_result=health,
        index_artifact=rebuilt_index,
        feasibility_artifact=feasibility,
        execution_id=execution_id,
        git_commit=git_commit,
        parent_digests=parent_digests,
    )
    return rebuilt_index, feasibility, health, completion


def conformal_exceedance_count(
    calibration_scores: Sequence[float],
    evaluation_score: float,
) -> tuple[int, float, bool]:
    values = np.asarray(calibration_scores, dtype=np.float64)
    if values.shape != (CALIBRATION_REPLICATES_PER_SCALE,) or not np.all(
        np.isfinite(values)
    ) or not math.isfinite(evaluation_score):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_conformal_input_invalid"
        )
    count = int(np.count_nonzero(values >= evaluation_score))
    p_value = (1.0 + count) / CONFORMAL_DENOMINATOR
    return count, p_value, count <= MAX_REJECTING_EXCEEDANCE_COUNT


def student_t_interval(values: Sequence[float] | np.ndarray) -> dict[str, float]:
    data = np.asarray(values, dtype=np.float64)
    if data.shape != (EVALUATION_REPLICATES_PER_CELL,) or not np.all(
        np.isfinite(data)
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_t_interval_input_invalid"
        )
    mean = float(math.fsum(float(item) for item in data) / data.size)
    standard_deviation = float(np.std(data, ddof=1))
    if standard_deviation == 0.0:
        lower = upper = mean
    else:
        radius = STUDENT_T_CRITICAL * standard_deviation / math.sqrt(data.size)
        lower, upper = mean - radius, mean + radius
    if not all(math.isfinite(item) for item in (mean, standard_deviation, lower, upper)):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_t_interval_nonfinite"
        )
    return {
        "mean": mean,
        "sample_standard_deviation": standard_deviation,
        "lower": lower,
        "upper": upper,
        "sample_count": EVALUATION_REPLICATES_PER_CELL,
        "degrees_of_freedom": STUDENT_T_DF,
        "critical_value": STUDENT_T_CRITICAL,
    }


def wilson_interval(successes: int, total: int, *, z: float) -> tuple[float, float]:
    if (
        isinstance(successes, bool)
        or isinstance(total, bool)
        or not isinstance(successes, int)
        or not isinstance(total, int)
        or total != EVALUATION_REPLICATES_PER_CELL
        or successes < 0
        or successes > total
        or z != WILSON_Z
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_wilson_input_invalid"
        )
    p = successes / total
    denominator = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denominator
    radius = (
        z
        * math.sqrt(p * (1.0 - p) / total + z * z / (4.0 * total * total))
        / denominator
    )
    return center - radius, center + radius


def _score_sequence_with_identity(
    *,
    draws: np.ndarray,
    cell: HealthCell,
    conditional_truth: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    issue_count = int(draws.shape[0])
    evaluation_start = issue_count - cell.evaluation_issues
    if evaluation_start != MINIMUM_TRAINING_ISSUES:
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_training_boundary_changed"
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
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_count_boundary_invalid"
        )
    q = (evaluated_counts + UNIFORM_Q) / (n_before[:, None] + 1.0)
    if not np.all((q > 0.0) & (q < 1.0)):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_estimator_invalid"
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
    scalar_oracle = np.asarray(
        [
            math.fsum(
                float(true_q[row, column]) * float(log_selected[row, column])
                + (1.0 - float(true_q[row, column]))
                * float(log_unselected[row, column])
                for column in range(NUMBER_COUNT)
            )
            for row in range(cell.evaluation_issues)
        ],
        dtype=np.float64,
    )
    identity_error = float(np.max(np.abs(truth - scalar_oracle)))
    probability_error = float(
        max(
            np.max(np.abs(q.sum(axis=1) - DRAW_SIZE)),
            np.max(np.abs(true_q.sum(axis=1) - DRAW_SIZE)),
        )
    )
    if (
        not np.all(np.isfinite(endpoint))
        or not np.all(np.isfinite(truth))
        or not math.isfinite(identity_error)
        or identity_error > IDENTITY_ABSOLUTE_ERROR_MAX
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_score_identity_invalid"
        )
    return endpoint, truth, identity_error, probability_error


def _exact_randomized_np_power(odds: float, count: int) -> float:
    null = _sum_distribution(_group_count_masses(16, 17, 1.0), count)
    alternative = _sum_distribution(_group_count_masses(16, 17, odds), count)
    null_tail = np.cumsum(null[::-1])[::-1]
    alternative_tail = np.cumsum(alternative[::-1])[::-1]
    candidates = np.flatnonzero(null_tail <= 0.05)
    if candidates.size == 0 or int(candidates[0]) < 1:
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_np_threshold_invalid"
        )
    threshold = int(candidates[0])
    randomization = (0.05 - null_tail[threshold]) / null[threshold - 1]
    size = float(null_tail[threshold] + randomization * null[threshold - 1])
    power = float(
        alternative_tail[threshold]
        + randomization * alternative[threshold - 1]
    )
    if abs(size - 0.05) > 2e-15 or not 0.0 <= power <= 1.0:
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_np_power_invalid"
        )
    return power


def _sum_distribution(values: np.ndarray, count: int) -> np.ndarray:
    result = np.asarray([1.0], dtype=np.float64)
    base = np.asarray(values, dtype=np.float64)
    exponent = count
    while exponent:
        if exponent & 1:
            result = np.convolve(result, base)
        exponent //= 2
        if exponent:
            base = np.convolve(base, base)
    result = np.maximum(result, 0.0)
    return result / np.sum(result)


def _persist_summary_and_build_entry(
    *,
    checkpoint_root: Path,
    context_digest: str,
    spec: RepairHealthReplicateSpec,
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_summary(summary)
    if (
        summary.get("replicate_digest") != spec.replicate_digest
        or summary.get("child_seed_digest") != spec.child_seed_digest
        or summary.get("replicate_index") != spec.replicate_index
        or summary.get("lane") != spec.lane
        or summary.get("cell") != asdict(spec.cell)
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_summary_identity_changed"
        )
    relative = Path("checkpoints/summaries") / f"{spec.replicate_digest}.json"
    path = checkpoint_root.parent / relative
    _persist_immutable(path, summary)
    entry: dict[str, Any] = {
        "schema_version": (
            "dehps-m4-v2-marginal-static-repair-health-index-entry.v1"
        ),
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
        domain="dehps.m4.v2.marginal-static-repair-health-index-entry.v1",
    )
    return entry


def _validate_index_entry(
    entry: Mapping[str, Any],
    *,
    context_digest: str,
    expected_specs: Mapping[str, RepairHealthReplicateSpec],
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
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_index_shape_changed"
        )
    identity = dict(entry)
    supplied = identity.pop("entry_digest")
    digest = str(entry.get("replicate_digest") or "")
    summary = entry.get("summary")
    spec = expected_specs.get(digest)
    if (
        entry.get("schema_version")
        != "dehps-m4-v2-marginal-static-repair-health-index-entry.v1"
        or supplied
        != canonical_digest(
            identity,
            domain="dehps.m4.v2.marginal-static-repair-health-index-entry.v1",
        )
        or entry.get("context_digest") != context_digest
        or spec is None
        or not isinstance(summary, Mapping)
        or entry.get("summary_digest") != summary.get("artifact_digest")
        or entry.get("summary_path") != f"checkpoints/summaries/{digest}.json"
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_index_identity_changed"
        )
    _validate_summary(summary)
    if (
        summary.get("replicate_digest") != spec.replicate_digest
        or summary.get("child_seed_digest") != spec.child_seed_digest
        or summary.get("cell") != asdict(spec.cell)
        or summary.get("lane") != spec.lane
        or summary.get("replicate_index") != spec.replicate_index
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_index_summary_changed"
        )


def _validate_summary(summary: Mapping[str, Any]) -> None:
    identity = dict(summary)
    supplied = identity.pop("artifact_digest", None)
    finite_fields = (
        "observed_endpoint_bits_per_issue",
        "conditional_truth_bits_per_issue",
        "score_residual_bits_per_issue",
        "score_residual_rmse_bits_per_issue",
        "conditional_identity_max_abs_error",
        "probability_sum_max_abs_error",
    )
    if (
        summary.get("schema_version")
        != "dehps-m4-v2-marginal-static-repair-health-replicate.v1"
        or summary.get("artifact_type")
        != "m4_v2_marginal_static_repair_health_replicate_summary"
        or supplied
        != canonical_digest(
            identity,
            domain=(
                "dehps.m4.v2.marginal-static-repair-health-replicate-summary.v1"
            ),
        )
        or summary.get("lane") not in {"CALIBRATION", "EVALUATION"}
        or not _is_digest(summary.get("replicate_digest"))
        or not _is_digest(summary.get("child_seed_digest"))
        or any(not math.isfinite(float(summary.get(field, math.nan))) for field in finite_fields)
        or summary.get("conditional_identity_max_abs_error", math.inf)
        > IDENTITY_ABSOLUTE_ERROR_MAX
        or summary.get("illegal_draw_count") != 0
        or summary.get("nested_bootstrap_replicates") != 0
        or summary.get("database_reads_during_replicate") != 0
        or summary.get("database_writes_during_replicate") != 0
        or summary.get("csv_materialized") is not False
        or summary.get("historical_outcomes_read") is not False
        or summary.get("round_42_statistical_results_read") is not False
        or summary.get("raw_draws_retained") is not False
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_summary_invalid"
        )


def _validate_execution_inputs(
    *,
    task_key: str,
    execution_id: str,
    git_commit: str,
    task_digest: str,
    source_contract: Mapping[str, Any],
    preregistration_execution: Mapping[str, Any],
    workload_artifact: Mapping[str, Any],
    inference_artifact: Mapping[str, Any],
    preregistration_artifact: Mapping[str, Any],
    preregistration_completion: Mapping[str, Any],
) -> None:
    if (
        task_key != MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY
        or not _is_digest(execution_id)
        or len(git_commit) != 40
        or not _is_digest(task_digest)
        or not _is_digest(source_contract.get("artifact_digest"))
        or preregistration_execution.get("execution_id")
        != PREREGISTRATION_EXECUTION_ID
        or preregistration_execution.get("artifact_digest")
        != PREREGISTRATION_EXECUTION_DIGEST
        or preregistration_execution.get("task_key") != PREREGISTRATION_TASK_KEY
        or preregistration_execution.get("completion_classification")
        != "VALIDATED_IN_MAINLINE"
        or preregistration_execution.get("completion_fact")
        != PREREGISTRATION_COMPLETION_FACT
        or workload_artifact.get("artifact_digest") != WORKLOAD_SEED_DIGEST
        or inference_artifact.get("artifact_digest") != INFERENCE_GATE_DIGEST
        or preregistration_artifact.get("artifact_digest")
        != PREREGISTRATION_DIGEST
        or preregistration_completion.get("artifact_digest")
        != PREREGISTRATION_COMPLETION_DIGEST
        or preregistration_artifact.get("formal_execution_authorized") is not False
        or preregistration_artifact.get("historical_outcomes_read") is not False
        or preregistration_completion.get("completion_fact")
        != PREREGISTRATION_COMPLETION_FACT
        or preregistration_completion.get("generated_issues") != 0
        or preregistration_completion.get("formal_replicates_executed") != 0
        or preregistration_completion.get("duplicate_validation") is not False
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_inputs_invalid"
        )
    _validate_frozen_contract(source_contract["frozen_contract"])
    _validate_workload_artifact(workload_artifact)
    _validate_inference_artifact(inference_artifact)


def _validate_workload_artifact(workload: Mapping[str, Any]) -> None:
    scales = tuple(
        (
            str(item.get("scale_id") or ""),
            int(item.get("sequence_issues", 0)),
            int(item.get("evaluation_issues", 0)),
        )
        for item in workload.get("scales", ())
    )
    if (
        workload.get("artifact_type")
        != "m4_v2_marginal_static_repair_health_workload_seeds"
        or workload.get("artifact_digest") != WORKLOAD_SEED_DIGEST
        or scales != EXPECTED_SCALES
        or workload.get("calibration_replicates") != CALIBRATION_REPLICATES
        or workload.get("evaluation_replicates") != EVALUATION_REPLICATES
        or workload.get("total_replicates") != TOTAL_REPLICATES
        or workload.get("execution_shard_size") != EXECUTION_SHARD_SIZE
        or workload.get("execution_shards") != EXECUTION_SHARDS
        or workload.get("planned_total_generated_issues") != TOTAL_GENERATED_ISSUES
        or workload.get("planned_total_outer_evaluation_issues")
        != TOTAL_OUTER_EVALUATION_ISSUES
        or workload.get("duplicate_validation") is not False
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_workload_changed"
        )


def _validate_inference_artifact(inference: Mapping[str, Any]) -> None:
    detection = inference.get("detection_rule")
    interval = inference.get("mean_monte_carlo_interval")
    wilson = inference.get("wilson_interval")
    if (
        inference.get("artifact_type")
        != "m4_v2_marginal_static_repair_health_inference_gates"
        or inference.get("artifact_digest") != INFERENCE_GATE_DIGEST
        or not isinstance(detection, Mapping)
        or detection.get("max_rejecting_exceedance_count")
        != MAX_REJECTING_EXCEEDANCE_COUNT
        or detection.get("calibration_replicates_per_scale")
        != CALIBRATION_REPLICATES_PER_SCALE
        or detection.get("tie_rule") != "greater_than_or_equal"
        or detection.get("nested_bootstrap_replicates") != 0
        or not isinstance(interval, Mapping)
        or interval.get("sample_count") != EVALUATION_REPLICATES_PER_CELL
        or interval.get("degrees_of_freedom") != STUDENT_T_DF
        or interval.get("critical_value") != STUDENT_T_CRITICAL
        or interval.get("sample_standard_deviation_ddof") != 1
        or not isinstance(wilson, Mapping)
        or wilson.get("z") != WILSON_Z
        or inference.get("duplicate_validation") is not False
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_inference_changed"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if (
        frozen.get("task_key") != MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY
        or frozen.get("capability")
        != MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_CAPABILITY
        or frozen.get("completion_fact")
        != MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_COMPLETION_FACT
        or frozen.get("next_consumer")
        != MARGINAL_STATIC_REPAIR_HEALTH_DECISION_TASK_KEY
        or frozen.get("preregistration_execution_digest")
        != PREREGISTRATION_EXECUTION_DIGEST
        or frozen.get("workload_and_seed_digest") != WORKLOAD_SEED_DIGEST
        or frozen.get("inference_and_gate_digest") != INFERENCE_GATE_DIGEST
        or frozen.get("preregistration_digest") != PREREGISTRATION_DIGEST
        or frozen.get("preregistration_completion_digest")
        != PREREGISTRATION_COMPLETION_DIGEST
        or frozen.get("calibration_replicates") != CALIBRATION_REPLICATES
        or frozen.get("evaluation_replicates") != EVALUATION_REPLICATES
        or frozen.get("total_replicates") != TOTAL_REPLICATES
        or frozen.get("execution_shards") != EXECUTION_SHARDS
        or frozen.get("execution_shard_size") != EXECUTION_SHARD_SIZE
        or frozen.get("total_generated_issues") != TOTAL_GENERATED_ISSUES
        or frozen.get("total_outer_evaluation_issues")
        != TOTAL_OUTER_EVALUATION_ISSUES
        or frozen.get("pre_sample_feasibility", {}).get("upper_power")
        != EXPECTED_FEASIBILITY
        or frozen.get("max_rejecting_exceedance_count")
        != MAX_REJECTING_EXCEEDANCE_COUNT
        or frozen.get("student_t_critical") != STUDENT_T_CRITICAL
        or frozen.get("student_t_degrees_of_freedom") != STUDENT_T_DF
        or frozen.get("wilson_z") != WILSON_Z
        or frozen.get("conditional_identity_absolute_error_max")
        != IDENTITY_ABSOLUTE_ERROR_MAX
        or frozen.get("root_seed_domain") != ROOT_SEED_DOMAIN
        or frozen.get("calibration_seed_domain") != CALIBRATION_SEED_DOMAIN
        or frozen.get("evaluation_seed_domain") != EVALUATION_SEED_DOMAIN
        or frozen.get("nested_bootstrap_replicates") != 0
        or frozen.get("duplicate_validation") is not False
        or frozen.get("raw_replay") != "forbidden"
        or frozen.get("database_io_during_replicate") != 0
        or frozen.get("csv_materialization") != "forbidden"
        or frozen.get("historical_outcomes_read") is not False
        or frozen.get("round_42_statistical_results_read") is not False
        or frozen.get("evidence_created") is not False
        or frozen.get("production_action") != "none"
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_contract_invalid"
        )


def _validate_spec(spec: RepairHealthReplicateSpec) -> None:
    limit = (
        CALIBRATION_REPLICATES_PER_SCALE
        if spec.lane == "CALIBRATION"
        else EVALUATION_REPLICATES_PER_CELL
    )
    if (
        spec.lane not in {"CALIBRATION", "EVALUATION"}
        or spec.replicate_index < 0
        or spec.replicate_index >= limit
        or spec.cell.sequence_issues - spec.cell.evaluation_issues
        != MINIMUM_TRAINING_ISSUES
        or spec.cell.scale_id not in {scale_id for scale_id, _, _ in EXPECTED_SCALES}
        or spec.preregistration_digest != PREREGISTRATION_DIGEST
    ):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_spec_invalid"
        )


def _resolve_worker_count(requested: int | None) -> int:
    available = os.cpu_count() or 1
    if requested is None:
        raw = os.environ.get("DEHPS_M4_V2_REPAIR_HEALTH_WORKERS", "")
        requested = int(raw) if raw else min(22, available)
    if isinstance(requested, bool) or requested < 1 or requested > available:
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_worker_count_invalid"
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
        "schema_version": (
            "dehps-m4-v2-marginal-static-repair-health-progress.v1"
        ),
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
        "nested_bootstrap_replicates": 0,
        "duplicate_validation": False,
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
            raise MarginalStaticRepairHealthExecutionError(
                f"marginal_static_repair_health_execution_checkpoint_invalid:{path}"
            ) from exc
        if existing != dict(payload):
            raise MarginalStaticRepairHealthExecutionError(
                f"marginal_static_repair_health_execution_checkpoint_collision:{path}"
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
    if not parent_digests or any(not _is_digest(item) for item in parent_digests):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_parent_digest_invalid"
        )
    json_body = json_compatible_copy(body)
    if not isinstance(json_body, dict):
        raise MarginalStaticRepairHealthExecutionError(
            "marginal_static_repair_health_execution_artifact_invalid"
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
