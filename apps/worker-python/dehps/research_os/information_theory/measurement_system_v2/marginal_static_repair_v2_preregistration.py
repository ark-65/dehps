from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-v2-preregistration"
)
MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_CAPABILITY = (
    "m4_v2_marginal_static_measurement_repair_v2_preregistration"
)
MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-repair-v2-preregistration:FROZEN"
)
MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-v2-health-execution"
)
MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-v2-marginal-static-repair-v2-preregistration-source-v1.json"
)

MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-v2-design"
)
MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_DIGEST = (
    "deb38aee3d1fae51c0524db0c883027af7475e636988a4d2c8fe7d3b0d6a2935"
)
MARGINAL_STATIC_REPAIR_V2_DESIGN_EXECUTION_ID = (
    "e6c7d7a9efcef74161b60a684aee9d56a7c57f2f81224066cb23656de7f69d27"
)
MARGINAL_STATIC_REPAIR_V2_DESIGN_EXECUTION_DIGEST = (
    "2fde91e5580f6e5dfb119f0666a42a5f137c9ea36d15ed5352633fab3f267144"
)
MARGINAL_STATIC_REPAIR_V2_PRESAMPLE_FEASIBILITY_DIGEST = (
    "645394d911ca6555db2363d792ef6e420f535a0caedfe480b09b7a2cf7e4aba2"
)
MARGINAL_STATIC_REPAIR_V2_DESIGN_DIGEST = (
    "741ddd093d3730d6d803468103b505af82da40fc8af2506d70edbb3e0f7af204"
)
MARGINAL_STATIC_REPAIR_V2_DESIGN_COMPLETION_DIGEST = (
    "802dd3a38bbd2a9af411a43c30b3bd4be3c407edfc8683b77565969e829cb644"
)

SCALES = ("FORWARD_61", "HISTORICAL_2581")
NULL_FAMILIES = ("IID_UNIFORM", "T1_MARKOV_STATIONARY", "J1_WITHIN_DRAW_IS4")
EVALUATION_CELLS = (
    "V2_M1_GROUP_ODDS_2_STATIONARY",
    "NULL_UNIFORM_LEGAL_SIX_OF_33",
    "V2_T1_OVERLAP_ODDS_2_MARKOV",
    "V2_J1_HISTORY_IS4_LAMBDA_HALF",
    "LOCAL_M1:0.001",
    "LOCAL_M1:0.010",
    "LOCAL_M1:0.050",
)
REFERENCE_SCORES_PER_BLOCK = 19
EVALUATION_REPLICATES_PER_CELL = 1024
REFERENCE_CHILDREN = 116_736
EVALUATION_CHILDREN = 14_336
TOTAL_CHILDREN = 131_072
SHARD_SIZE = 64
SHARD_COUNT = 2048
PLANNED_GENERATED_ISSUES = 291_110_912
PLANNED_OUTER_EVALUATION_ISSUES = 173_146_112
COMPACT_INDEX_LOADS = 1
NEGATIVE_CONTROL_WILSON_UPPER_MAX = 0.09
POSITIVE_CONTROL_WILSON_LOWER_MIN = 0.80
LARGEST_NEGATIVE_CONTROL_PASSING_COUNT = 74
SIX_CONTROL_FALSE_REPAIR_UNION_BOUND = 0.004767112426180425

ROOT_SEED_DOMAIN = "M4_V2_MARGINAL_STATIC_REPAIR_V2_HEALTH_V1"
REFERENCE_SEED_DOMAIN = "M4_V2_MARGINAL_STATIC_REPAIR_V2_CALIBRATION_BLOCK_V1"
EVALUATION_SEED_DOMAIN = "M4_V2_MARGINAL_STATIC_REPAIR_V2_EVALUATION_V1"

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-m4-v2-marginal-static-repair-v2-preregistration-round-49-20260808"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-v2-marginal-static-repair-v2-preregistration-round-49-20260808"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/marginal_static_repair_v2_preregistration.py"
)


class MarginalStaticRepairV2PreregistrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarginalStaticRepairV2PreregistrationRun:
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


def load_marginal_static_repair_v2_preregistration_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticRepairV2PreregistrationError(
            f"marginal_static_repair_v2_preregistration_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-repair-v2-preregistration-source.v1"
        or payload.get("artifact_type")
        != "m4_v2_marginal_static_repair_v2_preregistration_source"
        or payload.get("contract_key")
        != "M4_V2_MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 352
        or payload.get("research_execution_id") != 273
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 353
        or payload.get("engineering_execution_id") != 274
        or payload.get("formal_replicates_executed") != 0
        or payload.get("generated_issues") != 0
        or payload.get("compact_index_reads") != 0
        or payload.get("raw_replicates_regenerated") != 0
        or payload.get("sentinel_replicates_recomputed") != 0
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
            domain=(
                "dehps.m4.v2.marginal-static-repair-v2-preregistration-source-set.v1"
            ),
        )
    ):
        raise MarginalStaticRepairV2PreregistrationError(
            "marginal_static_repair_v2_preregistration_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise MarginalStaticRepairV2PreregistrationError(
            "marginal_static_repair_v2_preregistration_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_marginal_static_repair_v2_preregistration_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MarginalStaticRepairV2PreregistrationError(
                f"marginal_static_repair_v2_preregistration_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise MarginalStaticRepairV2PreregistrationError(
                f"marginal_static_repair_v2_preregistration_source_modified:{relative}"
            )


def reference_child_identity(
    *,
    preregistration_digest: str,
    null_family: str,
    scale_id: str,
    evaluation_index: int,
    reference_index: int,
) -> str:
    if (
        not _is_digest(preregistration_digest)
        or null_family not in NULL_FAMILIES
        or scale_id not in SCALES
        or isinstance(evaluation_index, bool)
        or not isinstance(evaluation_index, int)
        or not 0 <= evaluation_index < EVALUATION_REPLICATES_PER_CELL
        or isinstance(reference_index, bool)
        or not isinstance(reference_index, int)
        or not 0 <= reference_index < REFERENCE_SCORES_PER_BLOCK
    ):
        raise MarginalStaticRepairV2PreregistrationError(
            "marginal_static_repair_v2_preregistration_reference_identity_invalid"
        )
    return canonical_digest(
        {
            "preregistration_digest": preregistration_digest,
            "lane": "reference",
            "null_family": null_family,
            "scale_id": scale_id,
            "evaluation_index": evaluation_index,
            "reference_index": reference_index,
        },
        domain="dehps.m4.v2.marginal-static-repair-v2-reference-child.v1",
    )


def evaluation_child_identity(
    *,
    preregistration_digest: str,
    cell_id: str,
    scale_id: str,
    evaluation_index: int,
) -> str:
    if (
        not _is_digest(preregistration_digest)
        or cell_id not in EVALUATION_CELLS
        or scale_id not in SCALES
        or isinstance(evaluation_index, bool)
        or not isinstance(evaluation_index, int)
        or not 0 <= evaluation_index < EVALUATION_REPLICATES_PER_CELL
    ):
        raise MarginalStaticRepairV2PreregistrationError(
            "marginal_static_repair_v2_preregistration_evaluation_identity_invalid"
        )
    return canonical_digest(
        {
            "preregistration_digest": preregistration_digest,
            "lane": "evaluation",
            "cell_id": cell_id,
            "scale_id": scale_id,
            "evaluation_index": evaluation_index,
        },
        domain="dehps.m4.v2.marginal-static-repair-v2-evaluation-child.v1",
    )


def build_marginal_static_repair_v2_preregistration_artifacts(
    *,
    source_contract: Mapping[str, Any],
    design_execution: Mapping[str, Any],
    presample_feasibility: Mapping[str, Any],
    repair_v2_design: Mapping[str, Any],
    design_completion: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
) -> MarginalStaticRepairV2PreregistrationRun:
    frozen = source_contract.get("frozen_contract")
    if not isinstance(frozen, Mapping):
        raise MarginalStaticRepairV2PreregistrationError(
            "marginal_static_repair_v2_preregistration_contract_missing"
        )
    _validate_frozen_contract(frozen)
    _validate_design_lineage(
        execution=design_execution,
        feasibility=presample_feasibility,
        design=repair_v2_design,
        completion=design_completion,
    )
    if not _is_digest(execution_id) or len(git_commit) != 40:
        raise MarginalStaticRepairV2PreregistrationError(
            "marginal_static_repair_v2_preregistration_execution_identity_invalid"
        )
    source_digest = str(source_contract["artifact_digest"])
    parent_digests = (
        source_digest,
        str(design_execution["artifact_digest"]),
        str(presample_feasibility["artifact_digest"]),
        str(repair_v2_design["artifact_digest"]),
        str(design_completion["artifact_digest"]),
    )
    common = {
        "formal_replicates_executed": 0,
        "generated_issues": 0,
        "compact_index_reads": 0,
        "raw_replicates_regenerated": 0,
        "sentinel_replicates_recomputed": 0,
        "duplicate_validation": False,
        "historical_outcomes_read": False,
        "evidence_created": False,
        "production_action": "none",
    }
    workload_and_seeds = _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-repair-v2-health-workload-seeds.v1"
        ),
        artifact_type="m4_v2_marginal_static_repair_v2_health_workload_seeds",
        body={
            "status": "FROZEN",
            "source_contract_digest": source_digest,
            "scales": frozen["scales"],
            "evaluation_cells": frozen["evaluation_cells"],
            "null_families": frozen["null_families"],
            "workload": frozen["workload"],
            "child_identity": frozen["child_identity"],
            "seed_contract": frozen["seed_contract"],
            "resume_and_uniqueness": frozen["resume_and_uniqueness"],
            **common,
        },
        parent_digests=parent_digests,
        domain="dehps.m4.v2.marginal-static-repair-v2-health-workload-seeds.v1",
    )
    inference_and_gates = _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-repair-v2-health-inference-gates.v1"
        ),
        artifact_type="m4_v2_marginal_static_repair_v2_health_inference_gates",
        body={
            "status": "FROZEN",
            "source_contract_digest": source_digest,
            "matched_reference_rule": frozen["matched_reference_rule"],
            "statistics": frozen["statistics"],
            "decision": frozen["decision"],
            "familywise_claim_basis": "union_bound_only",
            "cross_cell_independence_claimed": False,
            **common,
        },
        parent_digests=parent_digests,
        domain="dehps.m4.v2.marginal-static-repair-v2-health-inference-gates.v1",
    )
    preregistration = _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-repair-v2-health-preregistration.v1"
        ),
        artifact_type="m4_v2_marginal_static_repair_v2_health_preregistration",
        body={
            "status": "FROZEN_PREREGISTRATION",
            "branch_id": "MARGINAL_STATIC",
            "source_contract_digest": source_digest,
            "repair_v2_design_digest": repair_v2_design["artifact_digest"],
            "workload_and_seed_digest": workload_and_seeds["artifact_digest"],
            "inference_and_gate_digest": inference_and_gates["artifact_digest"],
            "formal_execution_authorized": False,
            "automatic_pass_from_preregistration": False,
            "completed_matching_child_action": (
                "skip_without_generation_or_revalidation"
            ),
            "new_child_dispatch": "at_most_once_per_execution",
            "next_consumer": MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY,
            "accepted_model_artifact_digest": None,
            "promotion_gate_opened": False,
            **common,
        },
        parent_digests=(
            *parent_digests,
            str(workload_and_seeds["artifact_digest"]),
            str(inference_and_gates["artifact_digest"]),
        ),
        domain="dehps.m4.v2.marginal-static-repair-v2-health-preregistration.v1",
    )
    completion = _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-repair-v2-health-preregistration-completion.v1"
        ),
        artifact_type=(
            "m4_v2_marginal_static_repair_v2_health_preregistration_completion"
        ),
        body={
            "status": "COMPLETE",
            "execution_id": execution_id,
            "git_commit": git_commit,
            "source_contract_digest": source_digest,
            "repair_v2_design_digest": repair_v2_design["artifact_digest"],
            "workload_and_seed_digest": workload_and_seeds["artifact_digest"],
            "inference_and_gate_digest": inference_and_gates["artifact_digest"],
            "preregistration_digest": preregistration["artifact_digest"],
            "completion_fact": (
                MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_COMPLETION_FACT
            ),
            "next_consumer": MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY,
            "promotion_gate_opened": False,
            **common,
        },
        parent_digests=(
            *parent_digests,
            str(workload_and_seeds["artifact_digest"]),
            str(inference_and_gates["artifact_digest"]),
            str(preregistration["artifact_digest"]),
        ),
        domain=(
            "dehps.m4.v2.marginal-static-repair-v2-health-preregistration-completion.v1"
        ),
    )
    return MarginalStaticRepairV2PreregistrationRun(
        workload_and_seeds=workload_and_seeds,
        inference_and_gates=inference_and_gates,
        preregistration=preregistration,
        completion=completion,
    )


def _validate_design_lineage(
    *,
    execution: Mapping[str, Any],
    feasibility: Mapping[str, Any],
    design: Mapping[str, Any],
    completion: Mapping[str, Any],
) -> None:
    if (
        execution.get("execution_id") != MARGINAL_STATIC_REPAIR_V2_DESIGN_EXECUTION_ID
        or execution.get("artifact_digest")
        != MARGINAL_STATIC_REPAIR_V2_DESIGN_EXECUTION_DIGEST
        or execution.get("task_key") != MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY
        or execution.get("task_digest") != MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_DIGEST
        or execution.get("completion_classification") != "VALIDATED_IN_MAINLINE"
        or execution.get("registered_artifact_count") != 4
        or execution.get("formal_replicates_executed") != 0
        or execution.get("generated_issues") != 0
        or execution.get("duplicate_validation") is not False
        or feasibility.get("artifact_type")
        != "m4_v2_marginal_static_repair_v2_presample_feasibility"
        or feasibility.get("artifact_digest")
        != MARGINAL_STATIC_REPAIR_V2_PRESAMPLE_FEASIBILITY_DIGEST
        or feasibility.get("duplicate_validation") is not False
        or design.get("artifact_type")
        != "m4_v2_marginal_static_measurement_repair_v2_design"
        or design.get("artifact_digest") != MARGINAL_STATIC_REPAIR_V2_DESIGN_DIGEST
        or design.get("duplicate_validation") is not False
        or completion.get("artifact_type")
        != "m4_v2_marginal_static_repair_v2_design_completion"
        or completion.get("artifact_digest")
        != MARGINAL_STATIC_REPAIR_V2_DESIGN_COMPLETION_DIGEST
        or completion.get("completion_fact")
        != "m4-v2-marginal-static-measurement-repair-v2-design:FROZEN"
        or completion.get("duplicate_validation") is not False
    ):
        raise MarginalStaticRepairV2PreregistrationError(
            "marginal_static_repair_v2_preregistration_design_lineage_changed"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    workload = frozen.get("workload")
    identity = frozen.get("child_identity")
    seed = frozen.get("seed_contract")
    resume = frozen.get("resume_and_uniqueness")
    statistics = frozen.get("statistics")
    if (
        frozen.get("task_key") != MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY
        or frozen.get("capability")
        != MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_CAPABILITY
        or frozen.get("completion_fact")
        != MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_COMPLETION_FACT
        or frozen.get("next_consumer")
        != MARGINAL_STATIC_REPAIR_V2_HEALTH_EXECUTION_TASK_KEY
        or frozen.get("design_execution_digest")
        != MARGINAL_STATIC_REPAIR_V2_DESIGN_EXECUTION_DIGEST
        or frozen.get("presample_feasibility_digest")
        != MARGINAL_STATIC_REPAIR_V2_PRESAMPLE_FEASIBILITY_DIGEST
        or frozen.get("repair_v2_design_digest")
        != MARGINAL_STATIC_REPAIR_V2_DESIGN_DIGEST
        or frozen.get("design_completion_digest")
        != MARGINAL_STATIC_REPAIR_V2_DESIGN_COMPLETION_DIGEST
        or frozen.get("scales") != list(SCALES)
        or frozen.get("null_families") != list(NULL_FAMILIES)
        or frozen.get("evaluation_cells") != list(EVALUATION_CELLS)
        or not isinstance(workload, Mapping)
        or workload.get("reference_children") != REFERENCE_CHILDREN
        or workload.get("evaluation_children") != EVALUATION_CHILDREN
        or workload.get("total_children") != TOTAL_CHILDREN
        or workload.get("shard_size") != SHARD_SIZE
        or workload.get("shard_count") != SHARD_COUNT
        or workload.get("planned_generated_issues") != PLANNED_GENERATED_ISSUES
        or workload.get("planned_outer_evaluation_issues")
        != PLANNED_OUTER_EVALUATION_ISSUES
        or workload.get("nested_bootstrap_replicates") != 0
        or not isinstance(identity, Mapping)
        or identity.get("worker_or_shard_identity_in_seed") is not False
        or identity.get("identity_collision") != "fail_closed"
        or not isinstance(seed, Mapping)
        or seed.get("root") != ROOT_SEED_DOMAIN
        or seed.get("reference") != REFERENCE_SEED_DOMAIN
        or seed.get("evaluation") != EVALUATION_SEED_DOMAIN
        or seed.get("old_seed_reuse") is not False
        or seed.get("best_seed_selection") != "forbidden"
        or not isinstance(resume, Mapping)
        or resume.get("completion_index_loads") != COMPACT_INDEX_LOADS
        or resume.get("recursive_checkpoint_scan") is not False
        or resume.get("completed_matching_child")
        != "skip_without_generation_or_revalidation"
        or resume.get("completed_missing_or_mismatched_artifact") != "fail_closed"
        or resume.get("new_child_dispatch_count") != "at_most_once_per_execution"
        or resume.get("raw_replay") is not False
        or resume.get("sentinel_replay") is not False
        or resume.get("duplicate_validation") is not False
        or resume.get("aggregate_replay") != "registered_aggregate_content_only"
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
        or statistics.get("cross_cell_independence_claim") != "forbidden"
        or statistics.get("familywise_claim_basis") != "union_bound_only"
        or not isinstance(frozen.get("matched_reference_rule"), Mapping)
        or not isinstance(frozen.get("decision"), Mapping)
        or frozen.get("formal_replicates_executed") != 0
        or frozen.get("generated_issues") != 0
        or frozen.get("duplicate_validation") is not False
        or frozen.get("historical_outcomes_read") is not False
        or frozen.get("evidence_created") is not False
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("production_action") != "none"
    ):
        raise MarginalStaticRepairV2PreregistrationError(
            "marginal_static_repair_v2_preregistration_contract_invalid"
        )
    if (
        len(NULL_FAMILIES)
        * len(SCALES)
        * EVALUATION_REPLICATES_PER_CELL
        * REFERENCE_SCORES_PER_BLOCK
        != REFERENCE_CHILDREN
        or len(EVALUATION_CELLS) * len(SCALES) * EVALUATION_REPLICATES_PER_CELL
        != EVALUATION_CHILDREN
        or REFERENCE_CHILDREN + EVALUATION_CHILDREN != TOTAL_CHILDREN
        or TOTAL_CHILDREN // SHARD_SIZE != SHARD_COUNT
    ):
        raise MarginalStaticRepairV2PreregistrationError(
            "marginal_static_repair_v2_preregistration_workload_changed"
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
        raise MarginalStaticRepairV2PreregistrationError(
            "marginal_static_repair_v2_preregistration_parent_digest_invalid"
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
