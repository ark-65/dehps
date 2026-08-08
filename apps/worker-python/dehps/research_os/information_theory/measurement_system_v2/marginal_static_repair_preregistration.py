from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-preregistration"
)
MARGINAL_STATIC_REPAIR_PREREGISTRATION_CAPABILITY = (
    "m4_v2_marginal_static_measurement_repair_preregistration"
)
MARGINAL_STATIC_REPAIR_PREREGISTRATION_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-repair-preregistration:FROZEN"
)
MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-health-execution"
)
MARGINAL_STATIC_REPAIR_PREREGISTRATION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-v2-marginal-static-repair-preregistration-source-v1.json"
)

MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-design"
)
MARGINAL_STATIC_REPAIR_DESIGN_EXECUTION_ID = (
    "cf005217eadff3ca0125fbfd9fd6433c79cfe14511e8e10c6d8bdfa3444f9e0c"
)
MARGINAL_STATIC_REPAIR_DESIGN_EXECUTION_DIGEST = (
    "ad4360f89416dcd190eed4022b3346b02c439c4fb4c4a59e8b47f5e9c87e2435"
)
MARGINAL_STATIC_REPAIR_ANALYTIC_FEASIBILITY_DIGEST = (
    "eabed1661dc45992e2940f01ddda31fb9d3e3bc673fefd29a249996133080de5"
)
MARGINAL_STATIC_REPAIR_DESIGN_DIGEST = (
    "54f52d6f06ce575b22fd44673af9d75508a210931d9c7790b674b0045d5caa98"
)
MARGINAL_STATIC_REPAIR_DESIGN_COMPLETION_DIGEST = (
    "ede0d15c456bbe4889849318624208e642066b3afb178559362804d37e5b00b7"
)

CALIBRATION_REPLICATES_PER_SCALE = 512
EVALUATION_REPLICATES_PER_CELL = 256
CALIBRATION_REPLICATES = 1024
EVALUATION_REPLICATES = 3584
TOTAL_REPLICATES = 4608
EXECUTION_SHARD_SIZE = 64
EXECUTION_SHARDS = 72
TOTAL_GENERATED_ISSUES = 10_234_368
TOTAL_OUTER_EVALUATION_ISSUES = 6_087_168
OLD_ROUND_42_REPLICATES = 7168
REPLICATE_REDUCTION_FRACTION = 5 / 14
CONFORMAL_ALPHA = 0.05
MAX_REJECTING_EXCEEDANCE_COUNT = 24
STUDENT_T_975_DF_255 = 1.9693105698498752
WILSON_Z_975 = 1.959963984540054

ROOT_SEED_DOMAIN = "M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_V1"
CALIBRATION_SEED_DOMAIN = "M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_CALIBRATION_V1"
EVALUATION_SEED_DOMAIN = "M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_EVALUATION_V1"
RESERVED_BOOTSTRAP_SEED_DOMAIN = "M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_BOOTSTRAP_V1"

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-m4-v2-marginal-static-repair-preregistration-round-45-20260808"
)
_EXPECTED_RESEARCH_ADDENDUM_KEY = (
    "research-m4-v2-marginal-static-repair-preregistration-"
    "exactness-addendum-round-45-20260808"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-v2-marginal-static-repair-preregistration-round-45-20260808"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/marginal_static_repair_preregistration.py"
)


class MarginalStaticRepairPreregistrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarginalStaticRepairPreregistrationRun:
    workload_and_seeds: Mapping[str, Any]
    inference_and_gates: Mapping[str, Any]
    preregistration: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (
            self.workload_and_seeds,
            self.inference_and_gates,
            self.preregistration,
            self.completion,
        )


def load_marginal_static_repair_preregistration_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticRepairPreregistrationError(
            f"marginal_static_repair_preregistration_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-repair-preregistration-source.v1"
        or payload.get("artifact_type")
        != "m4_v2_marginal_static_repair_preregistration_source"
        or payload.get("contract_key")
        != "M4_V2_MARGINAL_STATIC_REPAIR_PREREGISTRATION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 338
        or payload.get("research_execution_id") != 259
        or payload.get("research_addendum_key") != _EXPECTED_RESEARCH_ADDENDUM_KEY
        or payload.get("research_addendum_request_id") != 339
        or payload.get("research_addendum_execution_id") != 260
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 340
        or payload.get("formal_replicates_executed") != 0
        or payload.get("generated_issues") != 0
        or payload.get("bootstrap_replicates_executed") != 0
        or payload.get("duplicate_validation") is not False
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
            domain=("dehps.m4.v2.marginal-static-repair-preregistration-source-set.v1"),
        )
    ):
        raise MarginalStaticRepairPreregistrationError(
            "marginal_static_repair_preregistration_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise MarginalStaticRepairPreregistrationError(
            "marginal_static_repair_preregistration_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_marginal_static_repair_preregistration_source_bytes(
    *,
    root_dir: Path,
    contract: Mapping[str, Any],
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MarginalStaticRepairPreregistrationError(
                f"marginal_static_repair_preregistration_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise MarginalStaticRepairPreregistrationError(
                f"marginal_static_repair_preregistration_source_modified:{relative}"
            )


def split_conformal_p_value(
    calibration_scores: Sequence[float],
    evaluation_score: float,
) -> float:
    if len(calibration_scores) != CALIBRATION_REPLICATES_PER_SCALE:
        raise MarginalStaticRepairPreregistrationError(
            "marginal_static_repair_preregistration_calibration_count_invalid"
        )
    evaluation = float(evaluation_score)
    values = tuple(float(value) for value in calibration_scores)
    if not math.isfinite(evaluation) or any(
        not math.isfinite(value) for value in values
    ):
        raise MarginalStaticRepairPreregistrationError(
            "marginal_static_repair_preregistration_score_non_finite"
        )
    exceedances = sum(value >= evaluation for value in values)
    return (1 + exceedances) / (CALIBRATION_REPLICATES_PER_SCALE + 1)


def split_conformal_reject(
    calibration_scores: Sequence[float],
    evaluation_score: float,
) -> bool:
    p_value = split_conformal_p_value(calibration_scores, evaluation_score)
    return p_value <= CONFORMAL_ALPHA


def mean_student_t_interval(values: Sequence[float]) -> tuple[float, float]:
    if len(values) != EVALUATION_REPLICATES_PER_CELL:
        raise MarginalStaticRepairPreregistrationError(
            "marginal_static_repair_preregistration_interval_count_invalid"
        )
    sample = tuple(float(value) for value in values)
    if any(not math.isfinite(value) for value in sample):
        raise MarginalStaticRepairPreregistrationError(
            "marginal_static_repair_preregistration_interval_non_finite"
        )
    mean = math.fsum(sample) / len(sample)
    variance = math.fsum((value - mean) ** 2 for value in sample) / (len(sample) - 1)
    if variance == 0.0:
        return mean, mean
    margin = STUDENT_T_975_DF_255 * math.sqrt(variance / len(sample))
    return mean - margin, mean + margin


def repair_health_child_identity(
    *,
    preregistration_digest: str,
    lane: str,
    cell_id: str,
    scale_id: str,
    replicate_index: int,
) -> str:
    if (
        not _is_digest(preregistration_digest)
        or lane not in {"calibration", "evaluation"}
        or not cell_id
        or scale_id not in {"FORWARD_61", "HISTORICAL_2581"}
        or replicate_index < 0
    ):
        raise MarginalStaticRepairPreregistrationError(
            "marginal_static_repair_preregistration_child_identity_invalid"
        )
    maximum = (
        CALIBRATION_REPLICATES_PER_SCALE
        if lane == "calibration"
        else EVALUATION_REPLICATES_PER_CELL
    )
    if replicate_index >= maximum:
        raise MarginalStaticRepairPreregistrationError(
            "marginal_static_repair_preregistration_child_identity_invalid"
        )
    return canonical_digest(
        {
            "preregistration_digest": preregistration_digest,
            "lane": lane,
            "cell_id": cell_id,
            "scale_id": scale_id,
            "replicate_index": replicate_index,
        },
        domain="dehps.m4.v2.marginal-static-repair-health-child.v1",
    )


def build_marginal_static_repair_preregistration_artifacts(
    *,
    source_contract: Mapping[str, Any],
    repair_design_execution: Mapping[str, Any],
    analytic_feasibility: Mapping[str, Any],
    repair_design: Mapping[str, Any],
    repair_design_completion: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
) -> MarginalStaticRepairPreregistrationRun:
    frozen = source_contract.get("frozen_contract")
    if not isinstance(frozen, Mapping):
        raise MarginalStaticRepairPreregistrationError(
            "marginal_static_repair_preregistration_contract_missing"
        )
    _validate_frozen_contract(frozen)
    _validate_repair_design(
        execution=repair_design_execution,
        feasibility=analytic_feasibility,
        design=repair_design,
        completion=repair_design_completion,
    )
    source_digest = str(source_contract["artifact_digest"])
    parent_digests = (
        source_digest,
        str(repair_design_execution["artifact_digest"]),
        str(analytic_feasibility["artifact_digest"]),
        str(repair_design["artifact_digest"]),
        str(repair_design_completion["artifact_digest"]),
    )
    workload_and_seeds = _artifact(
        schema_version=("dehps-m4-v2-marginal-static-repair-health-workload-seeds.v1"),
        artifact_type="m4_v2_marginal_static_repair_health_workload_seeds",
        body={
            "status": "FROZEN",
            "source_contract_digest": source_digest,
            "scales": frozen["scales"],
            "cells_per_scale": frozen["cells_per_scale"],
            "calibration_lane": frozen["calibration_lane"],
            "evaluation_lane": frozen["evaluation_lane"],
            "calibration_replicates": CALIBRATION_REPLICATES,
            "evaluation_replicates": EVALUATION_REPLICATES,
            "total_replicates": TOTAL_REPLICATES,
            "execution_shard_size": EXECUTION_SHARD_SIZE,
            "execution_shards": EXECUTION_SHARDS,
            "planned_total_generated_issues": TOTAL_GENERATED_ISSUES,
            "planned_total_outer_evaluation_issues": (TOTAL_OUTER_EVALUATION_ISSUES),
            "old_round_42_replicates": OLD_ROUND_42_REPLICATES,
            "replicate_reduction_fraction": REPLICATE_REDUCTION_FRACTION,
            "seed_contract": frozen["seed_contract"],
            "runtime_boundary": frozen["runtime_boundary"],
            "formal_replicates_executed": 0,
            "generated_issues": 0,
            "bootstrap_replicates_executed": 0,
            "checkpoint_reads": 0,
            "compact_index_reads": 0,
            "duplicate_validation": False,
            "historical_outcomes_read": False,
            "evidence_created": False,
            "production_action": "none",
        },
        parent_digests=parent_digests,
        domain=("dehps.m4.v2.marginal-static-repair-health-workload-seeds.v1"),
    )
    inference_and_gates = _artifact(
        schema_version=("dehps-m4-v2-marginal-static-repair-health-inference-gates.v1"),
        artifact_type="m4_v2_marginal_static_repair_health_inference_gates",
        body={
            "status": "FROZEN",
            "source_contract_digest": source_digest,
            "analysis_unit": frozen["analysis_unit"],
            "detection_rule": frozen["detection_rule"],
            "mean_monte_carlo_interval": frozen["mean_monte_carlo_interval"],
            "wilson_interval": frozen["wilson_interval"],
            "proof_and_diagnostics": frozen["proof_and_diagnostics"],
            "control_gates": frozen["control_gates"],
            "local_target_classification": frozen["local_target_classification"],
            "decision": frozen["decision"],
            "max_rejecting_exceedance_count": (MAX_REJECTING_EXCEEDANCE_COUNT),
            "formal_replicates_executed": 0,
            "generated_issues": 0,
            "bootstrap_replicates_executed": 0,
            "duplicate_validation": False,
            "historical_outcomes_read": False,
            "evidence_created": False,
            "production_action": "none",
        },
        parent_digests=parent_digests,
        domain=("dehps.m4.v2.marginal-static-repair-health-inference-gates.v1"),
    )
    preregistration = _artifact(
        schema_version=("dehps-m4-v2-marginal-static-repair-health-preregistration.v1"),
        artifact_type=("m4_v2_marginal_static_repair_health_preregistration"),
        body={
            "status": "FROZEN_PREREGISTRATION",
            "branch_id": "MARGINAL_STATIC",
            "source_contract_digest": source_digest,
            "old_measurement_health": "REPAIR",
            "old_decision_preserved": "REPAIR_MEASUREMENT_SYSTEM",
            "repair_design_digest": repair_design["artifact_digest"],
            "workload_and_seed_digest": workload_and_seeds["artifact_digest"],
            "inference_and_gate_digest": inference_and_gates["artifact_digest"],
            "workload": frozen["workload"],
            "formal_execution_authorized": False,
            "automatic_pass_from_preregistration": False,
            "next_consumer": MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY,
            "formal_replicates_executed": 0,
            "generated_issues": 0,
            "bootstrap_replicates_executed": 0,
            "checkpoint_reads": 0,
            "duplicate_validation": False,
            "historical_outcomes_read": False,
            "evidence_created": False,
            "accepted_model_artifact_digest": None,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
        parent_digests=(
            *parent_digests,
            str(workload_and_seeds["artifact_digest"]),
            str(inference_and_gates["artifact_digest"]),
        ),
        domain=("dehps.m4.v2.marginal-static-repair-health-preregistration.v1"),
    )
    completion = _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-repair-health-preregistration-completion.v1"
        ),
        artifact_type=(
            "m4_v2_marginal_static_repair_health_preregistration_completion"
        ),
        body={
            "status": "COMPLETE",
            "execution_id": execution_id,
            "git_commit": git_commit,
            "source_contract_digest": source_digest,
            "repair_design_digest": repair_design["artifact_digest"],
            "workload_and_seed_digest": workload_and_seeds["artifact_digest"],
            "inference_and_gate_digest": inference_and_gates["artifact_digest"],
            "preregistration_digest": preregistration["artifact_digest"],
            "completion_fact": (MARGINAL_STATIC_REPAIR_PREREGISTRATION_COMPLETION_FACT),
            "next_consumer": MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY,
            "formal_replicates_executed": 0,
            "generated_issues": 0,
            "bootstrap_replicates_executed": 0,
            "checkpoint_reads": 0,
            "duplicate_validation": False,
            "historical_outcomes_read": False,
            "evidence_created": False,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
        parent_digests=(
            *parent_digests,
            str(workload_and_seeds["artifact_digest"]),
            str(inference_and_gates["artifact_digest"]),
            str(preregistration["artifact_digest"]),
        ),
        domain=(
            "dehps.m4.v2.marginal-static-repair-health-preregistration-completion.v1"
        ),
    )
    return MarginalStaticRepairPreregistrationRun(
        workload_and_seeds=workload_and_seeds,
        inference_and_gates=inference_and_gates,
        preregistration=preregistration,
        completion=completion,
    )


def _validate_repair_design(
    *,
    execution: Mapping[str, Any],
    feasibility: Mapping[str, Any],
    design: Mapping[str, Any],
    completion: Mapping[str, Any],
) -> None:
    if (
        execution.get("execution_id") != MARGINAL_STATIC_REPAIR_DESIGN_EXECUTION_ID
        or execution.get("artifact_digest")
        != MARGINAL_STATIC_REPAIR_DESIGN_EXECUTION_DIGEST
        or execution.get("task_key") != MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY
        or execution.get("completion_classification") != "VALIDATED_IN_MAINLINE"
        or execution.get("old_decision_preserved") != "REPAIR_MEASUREMENT_SYSTEM"
        or execution.get("duplicate_validation") is not False
        or execution.get("historical_outcomes_read") is not False
        or execution.get("evidence_created") is not False
        or execution.get("promotion_gate_opened") is not False
        or feasibility.get("artifact_type")
        != "m4_v2_marginal_static_repair_analytic_feasibility"
        or feasibility.get("artifact_digest")
        != MARGINAL_STATIC_REPAIR_ANALYTIC_FEASIBILITY_DIGEST
        or feasibility.get("duplicate_validation") is not False
        or design.get("artifact_type")
        != "m4_v2_marginal_static_measurement_repair_design"
        or design.get("artifact_digest") != MARGINAL_STATIC_REPAIR_DESIGN_DIGEST
        or design.get("old_decision_preserved") != "REPAIR_MEASUREMENT_SYSTEM"
        or design.get("automatic_pass_from_reanalysis") is not False
        or design.get("duplicate_validation") is not False
        or completion.get("artifact_type")
        != "m4_v2_marginal_static_repair_design_completion"
        or completion.get("artifact_digest")
        != MARGINAL_STATIC_REPAIR_DESIGN_COMPLETION_DIGEST
        or completion.get("completion_fact")
        != "m4-v2-marginal-static-measurement-repair-design:FROZEN"
        or completion.get("duplicate_validation") is not False
    ):
        raise MarginalStaticRepairPreregistrationError(
            "marginal_static_repair_preregistration_design_changed"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    workload = frozen.get("workload")
    seed = frozen.get("seed_contract")
    detection = frozen.get("detection_rule")
    interval = frozen.get("mean_monte_carlo_interval")
    wilson = frozen.get("wilson_interval")
    runtime = frozen.get("runtime_boundary")
    scales = frozen.get("scales")
    cells = frozen.get("cells_per_scale")
    if (
        frozen.get("task_key") != MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY
        or frozen.get("capability") != MARGINAL_STATIC_REPAIR_PREREGISTRATION_CAPABILITY
        or frozen.get("completion_fact")
        != MARGINAL_STATIC_REPAIR_PREREGISTRATION_COMPLETION_FACT
        or frozen.get("next_consumer")
        != MARGINAL_STATIC_REPAIR_HEALTH_EXECUTION_TASK_KEY
        or frozen.get("repair_design_digest") != MARGINAL_STATIC_REPAIR_DESIGN_DIGEST
        or frozen.get("old_decision") != "REPAIR_MEASUREMENT_SYSTEM"
        or not isinstance(scales, list)
        or len(scales) != 2
        or not isinstance(cells, list)
        or len(cells) != 7
        or not isinstance(workload, Mapping)
        or workload.get("calibration_replicates") != CALIBRATION_REPLICATES
        or workload.get("evaluation_replicates") != EVALUATION_REPLICATES
        or workload.get("total_replicates") != TOTAL_REPLICATES
        or workload.get("execution_shard_size") != EXECUTION_SHARD_SIZE
        or workload.get("execution_shards") != EXECUTION_SHARDS
        or workload.get("total_generated_issues_if_executed") != TOTAL_GENERATED_ISSUES
        or workload.get("total_outer_evaluation_issues_if_executed")
        != TOTAL_OUTER_EVALUATION_ISSUES
        or workload.get("old_round_42_replicates") != OLD_ROUND_42_REPLICATES
        or workload.get("replicate_reduction_fraction") != REPLICATE_REDUCTION_FRACTION
        or workload.get("nested_bootstrap_replicates_per_formal_replicate") != 0
        or workload.get("duplicate_validation") is not False
        or not isinstance(seed, Mapping)
        or seed.get("root_domain") != ROOT_SEED_DOMAIN
        or seed.get("calibration_child_domain") != CALIBRATION_SEED_DOMAIN
        or seed.get("evaluation_child_domain") != EVALUATION_SEED_DOMAIN
        or seed.get("reserved_bootstrap_domain") != RESERVED_BOOTSTRAP_SEED_DOMAIN
        or seed.get("bootstrap_children_executed") != 0
        or seed.get("round_42_child_seed_reuse") is not False
        or seed.get("calibration_evaluation_overlap") is not False
        or seed.get("worker_or_shard_identity_in_seed") is not False
        or not isinstance(detection, Mapping)
        or detection.get("calibration_replicates_per_scale")
        != CALIBRATION_REPLICATES_PER_SCALE
        or detection.get("alpha") != CONFORMAL_ALPHA
        or detection.get("max_rejecting_exceedance_count")
        != MAX_REJECTING_EXCEEDANCE_COUNT
        or detection.get("tie_rule") != "greater_than_or_equal"
        or detection.get("nested_bootstrap_replicates") != 0
        or detection.get("issue_block_bootstrap") != "forbidden"
        or not isinstance(interval, Mapping)
        or interval.get("sample_count") != EVALUATION_REPLICATES_PER_CELL
        or interval.get("critical_value") != STUDENT_T_975_DF_255
        or interval.get("bootstrap") != "forbidden"
        or not isinstance(wilson, Mapping)
        or wilson.get("z") != WILSON_Z_975
        or not isinstance(runtime, Mapping)
        or runtime.get("database_reads_during_replicate") != 0
        or runtime.get("database_writes_during_replicate") != 0
        or runtime.get("routine_physical_checkpoint_scan") != "forbidden"
        or runtime.get("raw_replay") != "forbidden"
        or runtime.get("csv_materialization") != "forbidden"
        or frozen.get("formal_replicates_executed") != 0
        or frozen.get("generated_issues") != 0
        or frozen.get("bootstrap_replicates_executed") != 0
        or frozen.get("duplicate_validation") is not False
        or frozen.get("historical_outcomes_read") is not False
        or frozen.get("evidence_created") is not False
        or frozen.get("production_action") != "none"
    ):
        raise MarginalStaticRepairPreregistrationError(
            "marginal_static_repair_preregistration_contract_invalid"
        )
    for field in (
        "analysis_unit",
        "calibration_lane",
        "evaluation_lane",
        "proof_and_diagnostics",
        "control_gates",
        "local_target_classification",
        "decision",
    ):
        if not frozen.get(field):
            raise MarginalStaticRepairPreregistrationError(
                "marginal_static_repair_preregistration_contract_invalid"
            )


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: tuple[str, ...],
    domain: str,
) -> dict[str, Any]:
    if not parent_digests or any(not _is_digest(item) for item in parent_digests):
        raise MarginalStaticRepairPreregistrationError(
            "marginal_static_repair_preregistration_parent_digest_invalid"
        )
    payload = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "artifact_digest": "",
        **dict(body),
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
