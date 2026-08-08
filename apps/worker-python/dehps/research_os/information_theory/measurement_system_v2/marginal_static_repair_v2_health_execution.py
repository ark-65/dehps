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
from functools import cached_property, lru_cache
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
    _truth_marginals,
)
from .marginal_static_repair_v2_design import (
    FAMILYWISE_FALSE_REPAIR_MAX,
    NEGATIVE_CONTROL_WILSON_UPPER_MAX,
    POSITIVE_CONTROL_WILSON_LOWER_MIN,
    WILSON_Z,
)

MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-v2-health-execution"
)
MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_CAPABILITY = (
    "m4_v2_marginal_static_measurement_repair_v2_health_execution"
)
MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-repair-v2-health-execution:COMPLETE"
)
MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-v2-health-decision"
)
MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/"
    "m4-v2-marginal-static-repair-v2-health-execution-source-v1.json"
)
MARGINAL_STATIC_REPAIR_V2_HEALTH_PROGRESS_PATH = Path(
    "runtime/logs/m4-v2-marginal-static-repair-v2-health-execution-progress.json"
)

PREREGISTRATION_TASK_KEY = "m4-v2-marginal-static-measurement-repair-v2-preregistration"
PREREGISTRATION_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-repair-v2-preregistration:FROZEN"
)
PREREGISTRATION_EXECUTION_ID = (
    "9184a886d06065915145097e064649dece1516f586afae9178fa1c1683d5df09"
)
PREREGISTRATION_EXECUTION_DIGEST = (
    "f155005e27b2def725001006dde97295c7f4edd10d7ecba6b0367453f5357c9a"
)
WORKLOAD_SEED_DIGEST = (
    "ebf207815b452aa41a5f4c5071b5b05288784d420c4c7c16db05ce0ec67ec6fe"
)
INFERENCE_GATE_DIGEST = (
    "2a4d86430b85e7a262918275a08fbe8e1977311de08eb3ee4fe603208714adf5"
)
PREREGISTRATION_DIGEST = (
    "e3043d3c3c9e95e531d9255062bc1133f32937c82b99ca729ffdad5611a08ece"
)
PREREGISTRATION_COMPLETION_DIGEST = (
    "2c760cc54c14425237758cb035d830cd2ee05f22bbbee9339ecbb9b3bf81d448"
)

IID_NULL_FAMILY = "IID_UNIFORM"
T1_NULL_FAMILY = "T1_MARKOV_STATIONARY"
J1_NULL_FAMILY = "J1_WITHIN_DRAW_IS4"
NULL_FAMILIES = (IID_NULL_FAMILY, T1_NULL_FAMILY, J1_NULL_FAMILY)
NULL_FIXTURE_BY_FAMILY = {
    IID_NULL_FAMILY: NULL_FIXTURE_ID,
    T1_NULL_FAMILY: T1_FIXTURE_ID,
    J1_NULL_FAMILY: J1_FIXTURE_ID,
}
NULL_FAMILY_BY_FIXTURE = {
    NULL_FIXTURE_ID: IID_NULL_FAMILY,
    M1_FIXTURE_ID: IID_NULL_FAMILY,
    T1_FIXTURE_ID: T1_NULL_FAMILY,
    J1_FIXTURE_ID: J1_NULL_FAMILY,
}
SCALES = (
    ("FORWARD_61", 961, 61),
    ("HISTORICAL_2581", 3481, 2581),
)
LOCAL_TARGETS = (0.001, 0.01, 0.05)
LOCAL_ODDS = EXPECTED_LOCAL_ODDS
PRE_SAMPLE_LOCAL_POWER = {
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

REFERENCE_SCORES_PER_BLOCK = 19
EVALUATION_REPLICATES_PER_CELL = 1024
REFERENCE_CHILDREN = 116_736
EVALUATION_CHILDREN = 14_336
TOTAL_CHILDREN = 131_072
SHARD_SIZE = 64
SHARD_COUNT = 2048
PLANNED_GENERATED_ISSUES = 291_110_912
PLANNED_OUTER_EVALUATION_ISSUES = 173_146_112
LARGEST_NEGATIVE_CONTROL_PASSING_COUNT = 74
SIX_CONTROL_FALSE_REPAIR_UNION_BOUND = 0.004767112426180425
IDENTITY_ABSOLUTE_ERROR_MAX = 1e-12
ROOT_SEED_DOMAIN = "M4_V2_MARGINAL_STATIC_REPAIR_V2_HEALTH_V1"
REFERENCE_SEED_DOMAIN = "M4_V2_MARGINAL_STATIC_REPAIR_V2_CALIBRATION_BLOCK_V1"
EVALUATION_SEED_DOMAIN = "M4_V2_MARGINAL_STATIC_REPAIR_V2_EVALUATION_V1"
PREREGISTERED_EVALUATION_CELLS = (
    M1_FIXTURE_ID,
    NULL_FIXTURE_ID,
    T1_FIXTURE_ID,
    J1_FIXTURE_ID,
    "LOCAL_M1:0.001",
    "LOCAL_M1:0.010",
    "LOCAL_M1:0.050",
)
REFERENCE_IDENTITY_FIELDS = (
    "preregistration_digest",
    "reference",
    "null_family",
    "scale_id",
    "evaluation_index",
    "reference_index",
)
EVALUATION_IDENTITY_FIELDS = (
    "preregistration_digest",
    "evaluation",
    "cell_id",
    "scale_id",
    "evaluation_index",
)

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-m4-v2-marginal-static-repair-v2-health-execution-round-50-20260808"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-v2-marginal-static-repair-v2-health-execution-round-50-20260808"
)
_SOURCE_PATHS = (
    (
        "apps/worker-python/dehps/research_os/information_theory/"
        "measurement_system_v2/marginal_static_repair_v2_health_execution.py"
    ),
    (
        "apps/worker-python/dehps/research_os/information_theory/"
        "measurement_system_v2/marginal_static_health_execution.py"
    ),
)


class MarginalStaticRepairV2HealthExecutionError(RuntimeError):
    pass


class MarginalStaticRepairV2CheckpointPause(RuntimeError):
    """Controlled test-only pause after durable shard completion."""


@dataclass(frozen=True)
class RepairV2ChildSpec:
    lane: str
    null_family: str
    scale_id: str
    sequence_issues: int
    evaluation_issues: int
    evaluation_index: int
    preregistration_digest: str
    reference_index: int | None = None
    cell_id: str | None = None

    @property
    def identity(self) -> dict[str, Any]:
        if self.lane == "REFERENCE":
            return {
                "preregistration_digest": self.preregistration_digest,
                "lane": "reference",
                "null_family": self.null_family,
                "scale_id": self.scale_id,
                "evaluation_index": self.evaluation_index,
                "reference_index": self.reference_index,
            }
        return {
            "preregistration_digest": self.preregistration_digest,
            "lane": "evaluation",
            "cell_id": _preregistered_cell_id(str(self.cell_id)),
            "scale_id": self.scale_id,
            "evaluation_index": self.evaluation_index,
        }

    @cached_property
    def child_digest(self) -> str:
        domain = (
            "dehps.m4.v2.marginal-static-repair-v2-reference-child.v1"
            if self.lane == "REFERENCE"
            else "dehps.m4.v2.marginal-static-repair-v2-evaluation-child.v1"
        )
        return canonical_digest(
            self.identity,
            domain=domain,
        )

    @cached_property
    def child_seed_digest(self) -> str:
        domain = (
            REFERENCE_SEED_DOMAIN
            if self.lane == "REFERENCE"
            else EVALUATION_SEED_DOMAIN
        )
        return canonical_digest(self.identity, domain=domain)


@dataclass(frozen=True)
class RepairV2HealthExecutionRun:
    index_artifact: Mapping[str, Any]
    health_result: Mapping[str, Any]
    completion: Mapping[str, Any]
    runtime_seconds: float
    completed_before_run: int
    completed_during_run: int
    completed_shards_during_run: int
    worker_count: int

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (self.index_artifact, self.health_result, self.completion)


def build_evaluation_cells() -> tuple[HealthCell, ...]:
    cells: list[HealthCell] = []
    roles = {
        M1_FIXTURE_ID: "POSITIVE_CONTROL",
        NULL_FIXTURE_ID: "NEGATIVE_CONTROL",
        T1_FIXTURE_ID: "NEGATIVE_CONTROL",
        J1_FIXTURE_ID: "NEGATIVE_CONTROL",
    }
    for fixture_id in (M1_FIXTURE_ID, NULL_FIXTURE_ID, T1_FIXTURE_ID, J1_FIXTURE_ID):
        for scale_id, sequence_issues, evaluation_issues in SCALES:
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
        for scale_id, sequence_issues, evaluation_issues in SCALES:
            cells.append(
                HealthCell(
                    cell_id=f"LOCAL_M1:{target:.3f}:{scale_id}",
                    family="LOCAL_ALTERNATIVE",
                    fixture_id=M1_FIXTURE_ID,
                    role="LOCAL_POWER",
                    scale_id=scale_id,
                    sequence_issues=sequence_issues,
                    evaluation_issues=evaluation_issues,
                    odds=LOCAL_ODDS[target],
                    local_target_bits_per_issue=target,
                )
            )
    if len(cells) != 14 or len({cell.cell_id for cell in cells}) != 14:
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_cell_set_invalid"
        )
    return tuple(cells)


def _preregistered_cell_id(formal_cell_id: str) -> str:
    if formal_cell_id.startswith("BASE:"):
        _, fixture_id, _ = formal_cell_id.split(":", maxsplit=2)
        result = fixture_id
    else:
        result, _, _ = formal_cell_id.rpartition(":")
    if result not in PREREGISTERED_EVALUATION_CELLS:
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_preregistered_cell_invalid"
        )
    return result


@lru_cache(maxsize=1)
def _evaluation_cells_by_id() -> dict[str, HealthCell]:
    return {cell.cell_id: cell for cell in build_evaluation_cells()}


def build_child_specs(
    preregistration_digest: str = PREREGISTRATION_DIGEST,
) -> tuple[RepairV2ChildSpec, ...]:
    if preregistration_digest != PREREGISTRATION_DIGEST:
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_preregistration_changed"
        )
    specs: list[RepairV2ChildSpec] = []
    for null_family in NULL_FAMILIES:
        for scale_id, sequence_issues, evaluation_issues in SCALES:
            for evaluation_index in range(EVALUATION_REPLICATES_PER_CELL):
                for reference_index in range(REFERENCE_SCORES_PER_BLOCK):
                    specs.append(
                        RepairV2ChildSpec(
                            lane="REFERENCE",
                            null_family=null_family,
                            scale_id=scale_id,
                            sequence_issues=sequence_issues,
                            evaluation_issues=evaluation_issues,
                            evaluation_index=evaluation_index,
                            reference_index=reference_index,
                            preregistration_digest=preregistration_digest,
                        )
                    )
    for cell in build_evaluation_cells():
        null_family = NULL_FAMILY_BY_FIXTURE[cell.fixture_id]
        for evaluation_index in range(EVALUATION_REPLICATES_PER_CELL):
            specs.append(
                RepairV2ChildSpec(
                    lane="EVALUATION",
                    null_family=null_family,
                    scale_id=cell.scale_id,
                    sequence_issues=cell.sequence_issues,
                    evaluation_issues=cell.evaluation_issues,
                    evaluation_index=evaluation_index,
                    cell_id=cell.cell_id,
                    preregistration_digest=preregistration_digest,
                )
            )
    if len(specs) != TOTAL_CHILDREN:
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_workload_arithmetic_changed"
        )
    return tuple(specs)


def _cell_for_spec(spec: RepairV2ChildSpec) -> HealthCell:
    if spec.lane == "REFERENCE":
        fixture_id = NULL_FIXTURE_BY_FAMILY[spec.null_family]
        return HealthCell(
            cell_id=(
                f"REFERENCE:{spec.null_family}:{spec.scale_id}:"
                f"{spec.evaluation_index}:{spec.reference_index}"
            ),
            family="MATCHED_REFERENCE",
            fixture_id=fixture_id,
            role="REFERENCE_NULL",
            scale_id=spec.scale_id,
            sequence_issues=spec.sequence_issues,
            evaluation_issues=spec.evaluation_issues,
            odds=None,
            local_target_bits_per_issue=None,
        )
    try:
        return _evaluation_cells_by_id()[str(spec.cell_id)]
    except KeyError as exc:
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_evaluation_cell_invalid"
        ) from exc


def score_sequence_vectorized_identity(
    *,
    draws: np.ndarray,
    cell: HealthCell,
    conditional_truth: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    issue_count = int(draws.shape[0])
    evaluation_start = issue_count - cell.evaluation_issues
    if evaluation_start != MINIMUM_TRAINING_ISSUES:
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_training_boundary_changed"
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
        evaluated_counts.sum(axis=1), DRAW_SIZE * n_before.astype(np.int64)
    ):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_count_boundary_invalid"
        )
    q = (evaluated_counts + UNIFORM_Q) / (n_before[:, None] + 1.0)
    if not np.all((q > 0.0) & (q < 1.0)):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_estimator_invalid"
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
    independent_truth = np.einsum(
        "ij,ij->i", true_q, log_selected, optimize=True
    ) + np.einsum("ij,ij->i", 1.0 - true_q, log_unselected, optimize=True)
    identity_error = float(np.max(np.abs(truth - independent_truth)))
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
        or probability_error > IDENTITY_ABSOLUTE_ERROR_MAX
    ):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_identity_or_probability_failure"
        )
    return endpoint, truth, identity_error, probability_error


def run_child(spec: RepairV2ChildSpec) -> dict[str, Any]:
    _validate_spec(spec)
    cell = _cell_for_spec(spec)
    rng = np.random.Generator(np.random.PCG64DXSM(int(spec.child_seed_digest, 16)))
    draws, conditional_truth = _generate_sequence(cell, rng)
    endpoint, truth, identity_error, probability_error = (
        score_sequence_vectorized_identity(
            draws=draws,
            cell=cell,
            conditional_truth=conditional_truth,
        )
    )
    residual = endpoint - truth
    summary = {
        "schema_version": "dehps-m4-v2-marginal-static-repair-v2-health-child.v1",
        "artifact_type": "m4_v2_marginal_static_repair_v2_health_child_summary",
        "artifact_digest": "",
        "child_digest": spec.child_digest,
        "child_seed_digest": spec.child_seed_digest,
        "lane": spec.lane,
        "null_family": spec.null_family,
        "scale_id": spec.scale_id,
        "evaluation_index": spec.evaluation_index,
        "reference_index": spec.reference_index,
        "cell_id": spec.cell_id,
        "cell": asdict(cell),
        "sequence_issues": spec.sequence_issues,
        "evaluation_issues": spec.evaluation_issues,
        "observed_endpoint_bits_per_issue": float(np.mean(endpoint)),
        "conditional_truth_bits_per_issue": float(np.mean(truth)),
        "score_residual_bits_per_issue": float(np.mean(residual)),
        "score_residual_rmse_bits_per_issue": float(
            math.sqrt(float(np.mean(np.square(residual))))
        ),
        "conditional_identity_max_abs_error": identity_error,
        "probability_sum_max_abs_error": probability_error,
        "legal_draw_count": spec.sequence_issues,
        "illegal_draw_count": 0,
        "database_reads_during_child": 0,
        "database_writes_during_child": 0,
        "csv_materialized": False,
        "raw_draws_retained": False,
        "historical_outcomes_read": False,
        "numpy_version": np.__version__,
    }
    identity = dict(summary)
    identity.pop("artifact_digest")
    summary["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.v2.marginal-static-repair-v2-health-child-summary.v1",
    )
    _validate_new_summary(summary, spec=spec)
    return summary


def run_child_shard(specs: Sequence[RepairV2ChildSpec]) -> tuple[dict[str, Any], ...]:
    if not specs or len(specs) > SHARD_SIZE:
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_shard_size_invalid"
        )
    return tuple(run_child(spec) for spec in specs)


def load_marginal_static_repair_v2_health_execution_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticRepairV2HealthExecutionError(
            f"marginal_static_repair_v2_health_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-repair-v2-health-execution-source.v1"
        or payload.get("artifact_type")
        != "m4_v2_marginal_static_repair_v2_health_execution_source"
        or payload.get("contract_key")
        != "M4_V2_MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 355
        or payload.get("research_execution_id") != 276
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 356
        or payload.get("engineering_execution_id") != 277
        or payload.get("result_blind") is not True
        or payload.get("formal_children_executed") != 0
        or payload.get("generated_issues") != 0
        or payload.get("duplicate_validation") is not False
        or payload.get("historical_outcomes_read") is not False
        or payload.get("evidence_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or tuple(entry.get("path") for entry in entries if isinstance(entry, dict))
        != _SOURCE_PATHS
        or any(not _is_digest(entry.get("content_sha256")) for entry in entries)
        or not isinstance(frozen, dict)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain=(
                "dehps.m4.v2.marginal-static-repair-v2-health-execution-source-set.v1"
            ),
        )
        or payload.get("artifact_digest") != config_digest(payload)
    ):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_source_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_marginal_static_repair_v2_health_execution_source_bytes(
    *,
    root_dir: Path,
    contract: Mapping[str, Any],
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MarginalStaticRepairV2HealthExecutionError(
                f"marginal_static_repair_v2_health_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise MarginalStaticRepairV2HealthExecutionError(
                f"marginal_static_repair_v2_health_source_modified:{relative}"
            )


def execute_repair_v2_health_program(
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
    max_new_shards: int | None = None,
) -> RepairV2HealthExecutionRun:
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
    if max_new_shards is not None and (
        isinstance(max_new_shards, bool) or max_new_shards < 1
    ):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_max_shards_invalid"
        )
    started = time.monotonic()
    specs = build_child_specs(str(preregistration_artifact["artifact_digest"]))
    expected = {spec.child_digest: spec for spec in specs}
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
        },
        domain="dehps.m4.v2.marginal-static-repair-v2-health-context.v1",
    )
    task_dir = root_dir / "runtime/research-os/mainline/tasks" / task_key / execution_id
    index_path = task_dir / "checkpoints/completion-index.jsonl"
    entries = load_completion_index_once(
        index_path,
        context_digest=context_digest,
        expected_specs=expected,
    )
    completed_before = len(entries)
    pending = [spec for spec in specs if spec.child_digest not in entries]
    pending_shards = [
        tuple(pending[offset : offset + SHARD_SIZE])
        for offset in range(0, len(pending), SHARD_SIZE)
    ]
    if max_new_shards is not None:
        pending_shards = pending_shards[:max_new_shards]
    resolved_workers = _resolve_worker_count(worker_count)
    resolved_progress = progress_path or (
        root_dir / MARGINAL_STATIC_REPAIR_V2_HEALTH_PROGRESS_PATH
    )
    generated_issues = sum(
        int(entry["summary"]["sequence_issues"]) for entry in entries.values()
    )
    _write_progress(
        resolved_progress,
        execution_id=execution_id,
        task_digest=task_digest,
        completed_children=completed_before,
        generated_issues=generated_issues,
        started_monotonic=started,
        completed_before_run=completed_before,
        worker_count=resolved_workers,
        status="RUNNING",
    )
    completed_during = 0
    completed_shards = 0
    if pending_shards:
        with ProcessPoolExecutor(
            max_workers=resolved_workers,
            initializer=_initialize_worker,
        ) as pool:
            for summaries in pool.map(run_child_shard, pending_shards, chunksize=1):
                rows: list[dict[str, Any]] = []
                for summary in summaries:
                    digest = str(summary["child_digest"])
                    spec = expected[digest]
                    row = _completion_row(
                        context_digest=context_digest,
                        spec=spec,
                        summary=summary,
                    )
                    rows.append(row)
                    entries[digest] = row
                append_completion_rows(index_path, rows)
                completed_during += len(rows)
                completed_shards += 1
                generated_issues += sum(
                    int(summary["sequence_issues"]) for summary in summaries
                )
                _write_progress(
                    resolved_progress,
                    execution_id=execution_id,
                    task_digest=task_digest,
                    completed_children=len(entries),
                    generated_issues=generated_issues,
                    started_monotonic=started,
                    completed_before_run=completed_before,
                    worker_count=resolved_workers,
                    status="RUNNING",
                )
    if len(entries) != TOTAL_CHILDREN:
        _write_progress(
            resolved_progress,
            execution_id=execution_id,
            task_digest=task_digest,
            completed_children=len(entries),
            generated_issues=generated_issues,
            started_monotonic=started,
            completed_before_run=completed_before,
            worker_count=resolved_workers,
            status="CHECKPOINT_PAUSED",
        )
        raise MarginalStaticRepairV2CheckpointPause(
            f"repair_v2_health_checkpoint_pause:{len(entries)}/{TOTAL_CHILDREN}"
        )
    ordered_rows = tuple(entries[spec.child_digest] for spec in specs)
    index_artifact = build_completion_index_artifact(
        rows=ordered_rows,
        context_digest=context_digest,
        index_path=index_path,
        root_dir=root_dir,
        parent_digests=parent_digests,
    )
    health_result = build_health_result(
        summaries=tuple(row["summary"] for row in ordered_rows),
        index_digest=str(index_artifact["artifact_digest"]),
        workload_digest=str(workload_artifact["artifact_digest"]),
        inference_digest=str(inference_artifact["artifact_digest"]),
        preregistration_digest=str(preregistration_artifact["artifact_digest"]),
        parent_digests=parent_digests,
    )
    completion = build_health_completion(
        index_artifact=index_artifact,
        health_result=health_result,
        execution_id=execution_id,
        git_commit=git_commit,
        parent_digests=parent_digests,
    )
    elapsed = time.monotonic() - started
    _write_progress(
        resolved_progress,
        execution_id=execution_id,
        task_digest=task_digest,
        completed_children=TOTAL_CHILDREN,
        generated_issues=PLANNED_GENERATED_ISSUES,
        started_monotonic=started,
        completed_before_run=completed_before,
        worker_count=resolved_workers,
        status="COMPLETE",
    )
    return RepairV2HealthExecutionRun(
        index_artifact=index_artifact,
        health_result=health_result,
        completion=completion,
        runtime_seconds=elapsed,
        completed_before_run=completed_before,
        completed_during_run=completed_during,
        completed_shards_during_run=completed_shards,
        worker_count=resolved_workers,
    )


def load_completion_index_once(
    path: Path,
    *,
    context_digest: str,
    expected_specs: Mapping[str, RepairV2ChildSpec],
) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    if raw and not raw.endswith("\n"):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_index_truncated"
        )
    entries: dict[str, dict[str, Any]] = {}
    for line in raw.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MarginalStaticRepairV2HealthExecutionError(
                "marginal_static_repair_v2_health_index_invalid"
            ) from exc
        if not isinstance(row, dict):
            raise MarginalStaticRepairV2HealthExecutionError(
                "marginal_static_repair_v2_health_index_invalid"
            )
        digest = str(row.get("child_digest") or "")
        spec = expected_specs.get(digest)
        summary = row.get("summary")
        if (
            row.get("schema_version")
            != "dehps-m4-v2-marginal-static-repair-v2-health-completion-row.v1"
            or row.get("context_digest") != context_digest
            or spec is None
            or not isinstance(summary, Mapping)
            or row.get("summary_digest") != summary.get("artifact_digest")
            or summary.get("child_digest") != digest
            or summary.get("child_seed_digest") != spec.child_seed_digest
            or summary.get("lane") != spec.lane
            or summary.get("scale_id") != spec.scale_id
            or summary.get("evaluation_index") != spec.evaluation_index
            or summary.get("reference_index") != spec.reference_index
            or summary.get("cell_id") != spec.cell_id
        ):
            raise MarginalStaticRepairV2HealthExecutionError(
                "marginal_static_repair_v2_health_registered_summary_mismatch"
            )
        entries[digest] = row
    return entries


def append_completion_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def build_completion_index_artifact(
    *,
    rows: Sequence[Mapping[str, Any]],
    context_digest: str,
    index_path: Path,
    root_dir: Path,
    parent_digests: Sequence[str],
) -> dict[str, Any]:
    if len(rows) != TOTAL_CHILDREN:
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_index_incomplete"
        )
    lane_counts = Counter(str(row["summary"]["lane"]) for row in rows)
    family_counts = Counter(
        str(row["summary"]["null_family"])
        for row in rows
        if row["summary"]["lane"] == "REFERENCE"
    )
    cell_counts = Counter(
        str(row["summary"]["cell_id"])
        for row in rows
        if row["summary"]["lane"] == "EVALUATION"
    )
    try:
        relative_path = index_path.relative_to(root_dir).as_posix()
    except ValueError as exc:
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_index_path_invalid"
        ) from exc
    if (
        lane_counts
        != {"REFERENCE": REFERENCE_CHILDREN, "EVALUATION": EVALUATION_CHILDREN}
        or set(family_counts.values()) != {REFERENCE_CHILDREN // len(NULL_FAMILIES)}
        or len(family_counts) != len(NULL_FAMILIES)
        or set(cell_counts.values()) != {EVALUATION_REPLICATES_PER_CELL}
        or len(cell_counts) != 14
    ):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_index_strata_incomplete"
        )
    return _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-repair-v2-health-completion-index.v1"
        ),
        artifact_type=("m4_v2_marginal_static_repair_v2_health_completion_index"),
        body={
            "status": "COMPLETE",
            "context_digest": context_digest,
            "index_path": relative_path,
            "index_file_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
            "entry_count": len(rows),
            "lane_counts": dict(sorted(lane_counts.items())),
            "reference_family_counts": dict(sorted(family_counts.items())),
            "evaluation_cell_counts": dict(sorted(cell_counts.items())),
            "completion_index_loads_per_process": 1,
            "completed_matching_child_action": (
                "skip_without_generation_or_revalidation"
            ),
            "new_child_dispatch": "at_most_once_per_execution",
            "summary_storage": (
                "content_addressed_summary_embedded_in_append_only_completion_row"
            ),
            "recursive_checkpoint_scan": False,
            "raw_replay": False,
            "sentinel_replay": False,
            "duplicate_validation": False,
            "historical_outcomes_read": False,
        },
        parent_digests=parent_digests,
        domain=("dehps.m4.v2.marginal-static-repair-v2-health-completion-index.v1"),
    )


def build_health_result(
    *,
    summaries: Sequence[Mapping[str, Any]],
    index_digest: str,
    workload_digest: str,
    inference_digest: str,
    preregistration_digest: str,
    parent_digests: Sequence[str],
) -> dict[str, Any]:
    if len(summaries) != TOTAL_CHILDREN:
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_summary_count_invalid"
        )
    references: dict[tuple[str, str, int], list[float]] = {}
    evaluations: dict[str, list[Mapping[str, Any]]] = {}
    structural_pass = True
    for summary in summaries:
        values = (
            float(summary.get("observed_endpoint_bits_per_issue", math.nan)),
            float(summary.get("conditional_truth_bits_per_issue", math.nan)),
            float(summary.get("score_residual_bits_per_issue", math.nan)),
            float(summary.get("score_residual_rmse_bits_per_issue", math.nan)),
            float(summary.get("conditional_identity_max_abs_error", math.nan)),
            float(summary.get("probability_sum_max_abs_error", math.nan)),
        )
        structural_pass = structural_pass and (
            all(math.isfinite(value) for value in values)
            and values[4] <= IDENTITY_ABSOLUTE_ERROR_MAX
            and values[5] <= IDENTITY_ABSOLUTE_ERROR_MAX
            and summary.get("illegal_draw_count") == 0
        )
        if summary["lane"] == "REFERENCE":
            key = (
                str(summary["null_family"]),
                str(summary["scale_id"]),
                int(summary["evaluation_index"]),
            )
            references.setdefault(key, []).append(values[0])
        else:
            evaluations.setdefault(str(summary["cell_id"]), []).append(summary)
    expected_reference_blocks = (
        len(NULL_FAMILIES) * len(SCALES) * EVALUATION_REPLICATES_PER_CELL
    )
    if (
        len(references) != expected_reference_blocks
        or any(
            len(scores) != REFERENCE_SCORES_PER_BLOCK for scores in references.values()
        )
        or len(evaluations) != 14
        or any(
            len(values) != EVALUATION_REPLICATES_PER_CELL
            for values in evaluations.values()
        )
    ):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_matched_block_incomplete"
        )
    cell_results: list[dict[str, Any]] = []
    failed_required_gates: list[str] = []
    negative_control_count = 0
    positive_control_count = 0
    admissible_local_count = 0
    for cell_id in sorted(evaluations):
        values = sorted(
            evaluations[cell_id], key=lambda item: int(item["evaluation_index"])
        )
        cell = dict(values[0]["cell"])
        null_family = NULL_FAMILY_BY_FIXTURE[str(cell["fixture_id"])]
        detections: list[bool] = []
        p_values: list[float] = []
        for value in values:
            block = references[
                (
                    null_family,
                    str(value["scale_id"]),
                    int(value["evaluation_index"]),
                )
            ]
            exceedance = sum(
                score >= float(value["observed_endpoint_bits_per_issue"])
                for score in block
            )
            p_value = (1 + exceedance) / (REFERENCE_SCORES_PER_BLOCK + 1)
            p_values.append(p_value)
            detections.append(p_value <= 0.05)
        detected_count = sum(detections)
        detection_rate = detected_count / EVALUATION_REPLICATES_PER_CELL
        wilson_lower, wilson_upper = wilson_interval(
            detected_count, EVALUATION_REPLICATES_PER_CELL
        )
        identity_max = max(
            float(item["conditional_identity_max_abs_error"]) for item in values
        )
        probability_max = max(
            float(item["probability_sum_max_abs_error"]) for item in values
        )
        gates: dict[str, bool] = {
            "complete_finite": True,
            "conditional_identity": identity_max <= IDENTITY_ABSOLUTE_ERROR_MAX,
            "legal_draws_and_probabilities": (
                probability_max <= IDENTITY_ABSOLUTE_ERROR_MAX
            ),
        }
        classification = str(cell["role"])
        exact_upper_power: float | None = None
        required = True
        if cell["role"] == "NEGATIVE_CONTROL":
            negative_control_count += 1
            gates["negative_control_wilson_upper"] = (
                wilson_upper <= NEGATIVE_CONTROL_WILSON_UPPER_MAX
            )
            gates["negative_control_count_boundary"] = (
                detected_count <= LARGEST_NEGATIVE_CONTROL_PASSING_COUNT
            )
            classification = (
                "NEGATIVE_CONTROL_PASS"
                if all(gates.values())
                else "NEGATIVE_CONTROL_FAIL"
            )
        elif cell["role"] == "POSITIVE_CONTROL":
            positive_control_count += 1
            gates["positive_control_wilson_lower"] = (
                wilson_lower >= POSITIVE_CONTROL_WILSON_LOWER_MIN
            )
            classification = (
                "POSITIVE_CONTROL_PASS"
                if all(gates.values())
                else "POSITIVE_CONTROL_FAIL"
            )
        else:
            target = float(cell["local_target_bits_per_issue"])
            target_key = f"{target:.3f}"
            exact_upper_power = PRE_SAMPLE_LOCAL_POWER[str(cell["scale_id"])][
                target_key
            ]
            admissible = exact_upper_power >= POSITIVE_CONTROL_WILSON_LOWER_MIN
            gates["local_admissible"] = admissible
            if admissible:
                admissible_local_count += 1
                gates["admissible_local_wilson_lower"] = (
                    wilson_lower >= POSITIVE_CONTROL_WILSON_LOWER_MIN
                )
                classification = (
                    "DETECTABLE" if all(gates.values()) else "INSTRUMENT_LIMIT"
                )
            else:
                required = False
                classification = "SENSITIVITY_LIMIT"
        if required and not all(gates.values()):
            failed_required_gates.append(cell_id)
        cell_results.append(
            {
                "cell": cell,
                "null_family": null_family,
                "evaluation_replicates": EVALUATION_REPLICATES_PER_CELL,
                "reference_scores_per_evaluation": REFERENCE_SCORES_PER_BLOCK,
                "detected_count": detected_count,
                "detection_rate": detection_rate,
                "wilson_lower_95": wilson_lower,
                "wilson_upper_95": wilson_upper,
                "min_conformal_p": min(p_values),
                "max_conformal_p": max(p_values),
                "conditional_identity_max_abs_error": identity_max,
                "probability_sum_max_abs_error": probability_max,
                "exact_np_upper_power": exact_upper_power,
                "required_gate": required,
                "classification": classification,
                "gates": gates,
            }
        )
    if negative_control_count != 6 or positive_control_count != 2:
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_control_topology_changed"
        )
    if not structural_pass:
        preliminary = "INCONCLUSIVE"
    elif failed_required_gates:
        preliminary = "REPAIR"
    else:
        preliminary = "PASS"
    return _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-repair-v2-measurement-health-result.v1"
        ),
        artifact_type=("m4_v2_marginal_static_repair_v2_measurement_health_result"),
        body={
            "status": "COMPLETE_PENDING_DECISION_REPLAY",
            "branch_id": "MARGINAL_STATIC",
            "estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "preliminary_measurement_health": preliminary,
            "authoritative_decision": None,
            "workload_digest": workload_digest,
            "inference_digest": inference_digest,
            "preregistration_digest": preregistration_digest,
            "completion_index_digest": index_digest,
            "cell_results": cell_results,
            "cell_count": len(cell_results),
            "negative_control_count": negative_control_count,
            "positive_control_count": positive_control_count,
            "admissible_local_cell_count": admissible_local_count,
            "failed_required_gate_cell_ids": sorted(failed_required_gates),
            "failed_required_gate_cell_count": len(set(failed_required_gates)),
            "reference_children": REFERENCE_CHILDREN,
            "evaluation_children": EVALUATION_CHILDREN,
            "total_children": TOTAL_CHILDREN,
            "generated_issues": PLANNED_GENERATED_ISSUES,
            "outer_evaluation_issues": PLANNED_OUTER_EVALUATION_ISSUES,
            "all_children_complete": True,
            "all_legal_finite_and_identity_valid": structural_pass,
            "familywise_claim_basis": "union_bound_only",
            "six_control_false_repair_union_bound": (
                SIX_CONTROL_FALSE_REPAIR_UNION_BOUND
            ),
            "cross_cell_independence_claimed": False,
            "manual_override": False,
            "historical_execution_status": "NOT_AUTHORIZED",
            "historical_outcomes_read": False,
            "evidence_created": False,
            "accepted_model_artifact_digest": None,
            "promotion_gate_opened": False,
            "production_action": "none",
            "next_consumer": MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY,
        },
        parent_digests=(*parent_digests, index_digest),
        domain=("dehps.m4.v2.marginal-static-repair-v2-measurement-health-result.v1"),
    )


def build_health_completion(
    *,
    index_artifact: Mapping[str, Any],
    health_result: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
    parent_digests: Sequence[str],
) -> dict[str, Any]:
    return _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-repair-v2-health-execution-completion.v1"
        ),
        artifact_type=("m4_v2_marginal_static_repair_v2_health_execution_completion"),
        body={
            "status": "COMPLETE",
            "execution_id": execution_id,
            "git_commit": git_commit,
            "completion_index_digest": index_artifact["artifact_digest"],
            "health_result_digest": health_result["artifact_digest"],
            "preliminary_measurement_health": health_result[
                "preliminary_measurement_health"
            ],
            "authoritative_decision": None,
            "completion_fact": (
                MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_COMPLETION_FACT
            ),
            "next_consumer": MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY,
            "reference_children": REFERENCE_CHILDREN,
            "evaluation_children": EVALUATION_CHILDREN,
            "total_children": TOTAL_CHILDREN,
            "generated_issues": PLANNED_GENERATED_ISSUES,
            "completion_index_loads": 1,
            "raw_replicates_regenerated": 0,
            "sentinel_replicates_recomputed": 0,
            "duplicate_validation": False,
            "historical_outcomes_read": False,
            "evidence_created": False,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
        parent_digests=(
            *parent_digests,
            str(index_artifact["artifact_digest"]),
            str(health_result["artifact_digest"]),
        ),
        domain=("dehps.m4.v2.marginal-static-repair-v2-health-execution-completion.v1"),
    )


def rebuild_repair_v2_health_artifacts_from_index(
    *,
    root_dir: Path,
    index_artifact: Mapping[str, Any],
    workload_digest: str,
    inference_digest: str,
    preregistration_digest: str,
    execution_id: str,
    git_commit: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    path = root_dir / str(index_artifact["index_path"])
    if not path.is_file() or hashlib.sha256(
        path.read_bytes()
    ).hexdigest() != index_artifact.get("index_file_sha256"):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_replay_index_changed"
        )
    raw_rows = tuple(
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    )
    parent_digests = tuple(str(item) for item in index_artifact["parent_digests"])
    rebuilt_index = build_completion_index_artifact(
        rows=raw_rows,
        context_digest=str(index_artifact["context_digest"]),
        index_path=path,
        root_dir=root_dir,
        parent_digests=parent_digests,
    )
    health = build_health_result(
        summaries=tuple(row["summary"] for row in raw_rows),
        index_digest=str(rebuilt_index["artifact_digest"]),
        workload_digest=workload_digest,
        inference_digest=inference_digest,
        preregistration_digest=preregistration_digest,
        parent_digests=parent_digests,
    )
    completion = build_health_completion(
        index_artifact=rebuilt_index,
        health_result=health,
        execution_id=execution_id,
        git_commit=git_commit,
        parent_digests=parent_digests,
    )
    return rebuilt_index, health, completion


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    if total != EVALUATION_REPLICATES_PER_CELL or successes < 0 or successes > total:
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_wilson_input_invalid"
        )
    probability = successes / total
    denominator = 1.0 + WILSON_Z * WILSON_Z / total
    center = (probability + WILSON_Z * WILSON_Z / (2.0 * total)) / denominator
    radius = (
        WILSON_Z
        * math.sqrt(
            probability * (1.0 - probability) / total
            + WILSON_Z * WILSON_Z / (4.0 * total * total)
        )
        / denominator
    )
    return center - radius, center + radius


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
        task_key != MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY
        or not _is_digest(execution_id)
        or len(git_commit) != 40
        or not _is_digest(task_digest)
        or not _is_digest(source_contract.get("artifact_digest"))
        or preregistration_execution.get("execution_id") != PREREGISTRATION_EXECUTION_ID
        or preregistration_execution.get("artifact_digest")
        != PREREGISTRATION_EXECUTION_DIGEST
        or preregistration_execution.get("task_key") != PREREGISTRATION_TASK_KEY
        or preregistration_execution.get("completion_classification")
        != "VALIDATED_IN_MAINLINE"
        or preregistration_execution.get("completion_fact")
        != PREREGISTRATION_COMPLETION_FACT
        or workload_artifact.get("artifact_digest") != WORKLOAD_SEED_DIGEST
        or inference_artifact.get("artifact_digest") != INFERENCE_GATE_DIGEST
        or preregistration_artifact.get("artifact_digest") != PREREGISTRATION_DIGEST
        or preregistration_completion.get("artifact_digest")
        != PREREGISTRATION_COMPLETION_DIGEST
        or preregistration_completion.get("completion_fact")
        != PREREGISTRATION_COMPLETION_FACT
        or preregistration_artifact.get("formal_execution_authorized") is not False
        or preregistration_artifact.get("duplicate_validation") is not False
        or preregistration_completion.get("duplicate_validation") is not False
        or preregistration_execution.get("historical_outcomes_read") is not False
        or preregistration_execution.get("evidence_created") is not False
        or preregistration_execution.get("promotion_gate_opened") is not False
    ):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_inputs_invalid"
        )
    _validate_frozen_contract(source_contract["frozen_contract"])
    _validate_workload(workload_artifact)
    _validate_inference(inference_artifact)


def _validate_workload(workload: Mapping[str, Any]) -> None:
    frozen = workload.get("workload")
    resume = workload.get("resume_and_uniqueness")
    seed_contract = workload.get("seed_contract")
    child_identity = workload.get("child_identity")
    if (
        workload.get("artifact_type")
        != "m4_v2_marginal_static_repair_v2_health_workload_seeds"
        or workload.get("artifact_digest") != WORKLOAD_SEED_DIGEST
        or not isinstance(frozen, Mapping)
        or frozen.get("reference_children") != REFERENCE_CHILDREN
        or frozen.get("evaluation_children") != EVALUATION_CHILDREN
        or frozen.get("total_children") != TOTAL_CHILDREN
        or frozen.get("shard_size") != SHARD_SIZE
        or frozen.get("shard_count") != SHARD_COUNT
        or frozen.get("planned_generated_issues") != PLANNED_GENERATED_ISSUES
        or frozen.get("planned_outer_evaluation_issues")
        != PLANNED_OUTER_EVALUATION_ISSUES
        or tuple(workload.get("null_families", ())) != NULL_FAMILIES
        or tuple(workload.get("scales", ()))
        != tuple(scale_id for scale_id, _, _ in SCALES)
        or tuple(workload.get("evaluation_cells", ())) != PREREGISTERED_EVALUATION_CELLS
        or not isinstance(seed_contract, Mapping)
        or seed_contract.get("root") != ROOT_SEED_DOMAIN
        or seed_contract.get("reference") != REFERENCE_SEED_DOMAIN
        or seed_contract.get("evaluation") != EVALUATION_SEED_DOMAIN
        or seed_contract.get("best_seed_selection") != "forbidden"
        or seed_contract.get("old_seed_reuse") is not False
        or not isinstance(child_identity, Mapping)
        or tuple(child_identity.get("reference_fields", ()))
        != REFERENCE_IDENTITY_FIELDS
        or tuple(child_identity.get("evaluation_fields", ()))
        != EVALUATION_IDENTITY_FIELDS
        or child_identity.get("reference_index_range") != "0..18"
        or child_identity.get("evaluation_index_range") != "0..1023"
        or child_identity.get("worker_or_shard_identity_in_seed") is not False
        or child_identity.get("identity_collision") != "fail_closed"
        or not isinstance(resume, Mapping)
        or resume.get("completion_index_loads") != 1
        or resume.get("completed_matching_child")
        != "skip_without_generation_or_revalidation"
        or resume.get("new_child_dispatch_count") != "at_most_once_per_execution"
        or resume.get("duplicate_validation") is not False
        or workload.get("duplicate_validation") is not False
    ):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_workload_changed"
        )


def _validate_inference(inference: Mapping[str, Any]) -> None:
    matched = inference.get("matched_reference_rule")
    statistics = inference.get("statistics")
    if (
        inference.get("artifact_type")
        != "m4_v2_marginal_static_repair_v2_health_inference_gates"
        or inference.get("artifact_digest") != INFERENCE_GATE_DIGEST
        or not isinstance(matched, Mapping)
        or matched.get("reference_scores_per_block") != REFERENCE_SCORES_PER_BLOCK
        or matched.get("cross_family_reuse") != "forbidden"
        or matched.get("cross_scale_reuse") != "forbidden"
        or matched.get("cross_index_reuse") != "forbidden"
        or not isinstance(statistics, Mapping)
        or statistics.get("evaluation_replicates_per_cell")
        != EVALUATION_REPLICATES_PER_CELL
        or statistics.get("negative_control_wilson_upper_95_max")
        != NEGATIVE_CONTROL_WILSON_UPPER_MAX
        or statistics.get("positive_control_wilson_lower_95_min")
        != POSITIVE_CONTROL_WILSON_LOWER_MIN
        or statistics.get("largest_negative_control_passing_count")
        != LARGEST_NEGATIVE_CONTROL_PASSING_COUNT
        or statistics.get("six_control_false_repair_union_bound")
        != SIX_CONTROL_FALSE_REPAIR_UNION_BOUND
        or statistics.get("cross_cell_independence_claim") != "forbidden"
        or statistics.get("familywise_claim_basis") != "union_bound_only"
        or inference.get("duplicate_validation") is not False
    ):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_inference_changed"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    workload = frozen.get("workload")
    dispatch = frozen.get("dispatch")
    scoring = frozen.get("scoring")
    resume = frozen.get("resume")
    statistics = frozen.get("statistics")
    seed_and_strata = frozen.get("seed_and_strata")
    if (
        frozen.get("task_key") != MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY
        or frozen.get("capability")
        != MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_CAPABILITY
        or frozen.get("completion_fact")
        != MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_COMPLETION_FACT
        or frozen.get("next_consumer")
        != MARGINAL_STATIC_REPAIR_V2_HEALTH_DECISION_TASK_KEY
        or frozen.get("preregistration_execution_digest")
        != PREREGISTRATION_EXECUTION_DIGEST
        or frozen.get("workload_and_seed_digest") != WORKLOAD_SEED_DIGEST
        or frozen.get("inference_and_gate_digest") != INFERENCE_GATE_DIGEST
        or frozen.get("preregistration_digest") != PREREGISTRATION_DIGEST
        or frozen.get("preregistration_completion_digest")
        != PREREGISTRATION_COMPLETION_DIGEST
        or not isinstance(seed_and_strata, Mapping)
        or seed_and_strata.get("root_seed_domain") != ROOT_SEED_DOMAIN
        or seed_and_strata.get("reference_seed_domain") != REFERENCE_SEED_DOMAIN
        or seed_and_strata.get("evaluation_seed_domain") != EVALUATION_SEED_DOMAIN
        or tuple(seed_and_strata.get("null_families", ())) != NULL_FAMILIES
        or tuple(seed_and_strata.get("scales", ()))
        != tuple(scale_id for scale_id, _, _ in SCALES)
        or tuple(seed_and_strata.get("evaluation_cells", ()))
        != PREREGISTERED_EVALUATION_CELLS
        or tuple(seed_and_strata.get("reference_identity_fields", ()))
        != REFERENCE_IDENTITY_FIELDS
        or tuple(seed_and_strata.get("evaluation_identity_fields", ()))
        != EVALUATION_IDENTITY_FIELDS
        or frozen.get("local_admissibility_pre_sample_power") != PRE_SAMPLE_LOCAL_POWER
        or not isinstance(workload, Mapping)
        or workload.get("reference_children") != REFERENCE_CHILDREN
        or workload.get("evaluation_children") != EVALUATION_CHILDREN
        or workload.get("total_children") != TOTAL_CHILDREN
        or workload.get("shard_size") != SHARD_SIZE
        or workload.get("shard_count") != SHARD_COUNT
        or workload.get("planned_generated_issues") != PLANNED_GENERATED_ISSUES
        or workload.get("planned_outer_evaluation_issues")
        != PLANNED_OUTER_EVALUATION_ISSUES
        or not isinstance(dispatch, Mapping)
        or dispatch.get("unit") != "canonical_64_child_shard"
        or dispatch.get("process_pool_jobs") != SHARD_COUNT
        or dispatch.get("new_child_dispatch") != "at_most_once_per_execution"
        or dispatch.get("child_identity_independent_of_worker_and_shard") is not True
        or not isinstance(scoring, Mapping)
        or scoring.get("estimator") != "EXPANDING_LEGAL_MARGINAL_ALPHA_1"
        or scoring.get("slow_scalar_oracle_in_formal_child") is not False
        or scoring.get("independent_vectorized_identity_reduction") is not True
        or scoring.get("identity_absolute_error_max") != IDENTITY_ABSOLUTE_ERROR_MAX
        or scoring.get("fixture_or_gate_change") is not False
        or not isinstance(resume, Mapping)
        or resume.get("completion_index_loads_per_process") != 1
        or resume.get("matching_registered_summary")
        != "skip_without_generation_or_revalidation"
        or resume.get("missing_or_mismatched_registered_summary") != "fail_closed"
        or resume.get("recursive_checkpoint_scan") is not False
        or resume.get("duplicate_validation") is not False
        or resume.get("raw_replay") is not False
        or resume.get("sentinel_replay") is not False
        or not isinstance(statistics, Mapping)
        or statistics.get("reference_scores_per_block") != REFERENCE_SCORES_PER_BLOCK
        or statistics.get("evaluation_replicates_per_cell")
        != EVALUATION_REPLICATES_PER_CELL
        or statistics.get("negative_control_wilson_upper_95_max")
        != NEGATIVE_CONTROL_WILSON_UPPER_MAX
        or statistics.get("positive_control_wilson_lower_95_min")
        != POSITIVE_CONTROL_WILSON_LOWER_MIN
        or statistics.get("largest_negative_control_passing_count")
        != LARGEST_NEGATIVE_CONTROL_PASSING_COUNT
        or statistics.get("six_control_false_repair_union_bound")
        != SIX_CONTROL_FALSE_REPAIR_UNION_BOUND
        or statistics.get("familywise_claim_basis") != "union_bound_only"
        or statistics.get("cross_cell_independence_claim") != "forbidden"
        or frozen.get("authoritative_decision_in_execution") is not False
        or frozen.get("historical_outcomes_read") is not False
        or frozen.get("evidence_created") is not False
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("production_action") != "none"
    ):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_contract_invalid"
        )
    if (
        len(NULL_FAMILIES)
        * len(SCALES)
        * EVALUATION_REPLICATES_PER_CELL
        * REFERENCE_SCORES_PER_BLOCK
        != REFERENCE_CHILDREN
        or len(build_evaluation_cells()) * EVALUATION_REPLICATES_PER_CELL
        != EVALUATION_CHILDREN
        or REFERENCE_CHILDREN + EVALUATION_CHILDREN != TOTAL_CHILDREN
        or TOTAL_CHILDREN // SHARD_SIZE != SHARD_COUNT
        or SIX_CONTROL_FALSE_REPAIR_UNION_BOUND > FAMILYWISE_FALSE_REPAIR_MAX
    ):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_arithmetic_changed"
        )


def _validate_spec(spec: RepairV2ChildSpec) -> None:
    scale = next((item for item in SCALES if item[0] == spec.scale_id), None)
    if (
        spec.lane not in {"REFERENCE", "EVALUATION"}
        or spec.null_family not in NULL_FAMILIES
        or scale is None
        or (spec.sequence_issues, spec.evaluation_issues) != scale[1:]
        or not 0 <= spec.evaluation_index < EVALUATION_REPLICATES_PER_CELL
        or spec.preregistration_digest != PREREGISTRATION_DIGEST
    ):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_child_spec_invalid"
        )
    if spec.lane == "REFERENCE":
        if (
            spec.cell_id is not None
            or spec.reference_index is None
            or not 0 <= spec.reference_index < REFERENCE_SCORES_PER_BLOCK
        ):
            raise MarginalStaticRepairV2HealthExecutionError(
                "marginal_static_repair_v2_health_reference_spec_invalid"
            )
    elif spec.reference_index is not None or not spec.cell_id:
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_evaluation_spec_invalid"
        )


def _validate_new_summary(
    summary: Mapping[str, Any], *, spec: RepairV2ChildSpec
) -> None:
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
        supplied
        != canonical_digest(
            identity,
            domain=("dehps.m4.v2.marginal-static-repair-v2-health-child-summary.v1"),
        )
        or summary.get("child_digest") != spec.child_digest
        or summary.get("child_seed_digest") != spec.child_seed_digest
        or summary.get("lane") != spec.lane
        or summary.get("scale_id") != spec.scale_id
        or summary.get("evaluation_index") != spec.evaluation_index
        or summary.get("reference_index") != spec.reference_index
        or summary.get("cell_id") != spec.cell_id
        or any(
            not math.isfinite(float(summary.get(field, math.nan)))
            for field in finite_fields
        )
        or float(summary["conditional_identity_max_abs_error"])
        > IDENTITY_ABSOLUTE_ERROR_MAX
        or float(summary["probability_sum_max_abs_error"]) > IDENTITY_ABSOLUTE_ERROR_MAX
        or summary.get("illegal_draw_count") != 0
        or summary.get("historical_outcomes_read") is not False
    ):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_new_summary_invalid"
        )


def _completion_row(
    *,
    context_digest: str,
    spec: RepairV2ChildSpec,
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_new_summary(summary, spec=spec)
    return {
        "schema_version": (
            "dehps-m4-v2-marginal-static-repair-v2-health-completion-row.v1"
        ),
        "context_digest": context_digest,
        "child_digest": spec.child_digest,
        "summary_digest": summary["artifact_digest"],
        "summary": dict(summary),
    }


def _resolve_worker_count(requested: int | None) -> int:
    available = os.cpu_count() or 1
    if requested is None:
        raw = os.environ.get("DEHPS_M4_V2_REPAIR_V2_HEALTH_WORKERS", "")
        requested = int(raw) if raw else min(22, available)
    if isinstance(requested, bool) or requested < 1 or requested > available:
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_worker_count_invalid"
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
    completed_children: int,
    generated_issues: int,
    started_monotonic: float,
    completed_before_run: int,
    worker_count: int,
    status: str,
) -> None:
    elapsed = max(0.0, time.monotonic() - started_monotonic)
    completed_this_run = completed_children - completed_before_run
    rate = completed_this_run / elapsed if elapsed > 0.0 else 0.0
    remaining = TOTAL_CHILDREN - completed_children
    atomic_write_text(
        path,
        json.dumps(
            {
                "schema_version": (
                    "dehps-m4-v2-marginal-static-repair-v2-health-progress.v1"
                ),
                "status": status,
                "execution_id": execution_id,
                "task_digest": task_digest,
                "completed_children": completed_children,
                "resumed_children": completed_before_run,
                "completed_children_this_run": completed_this_run,
                "total_children": TOTAL_CHILDREN,
                "completed_shards": completed_children // SHARD_SIZE,
                "total_shards": SHARD_COUNT,
                "completed_percent": 100.0 * completed_children / TOTAL_CHILDREN,
                "generated_issues": generated_issues,
                "planned_generated_issues": PLANNED_GENERATED_ISSUES,
                "elapsed_seconds": elapsed,
                "children_per_second": rate,
                "eta_seconds": remaining / rate if rate > 0.0 else None,
                "worker_count": worker_count,
                "completion_index_loads": 1,
                "duplicate_validation": False,
                "historical_outcomes_read": False,
                "partial_scientific_results_exposed": False,
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
    domain: str,
) -> dict[str, Any]:
    if not parent_digests or any(not _is_digest(value) for value in parent_digests):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_parent_digest_invalid"
        )
    compatible = json_compatible_copy(body)
    if not isinstance(compatible, dict):
        raise MarginalStaticRepairV2HealthExecutionError(
            "marginal_static_repair_v2_health_artifact_invalid"
        )
    payload = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "artifact_digest": "",
        **compatible,
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
