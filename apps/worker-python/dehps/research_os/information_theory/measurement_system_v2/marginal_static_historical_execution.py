from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

from .marginal_static_historical_preregistration import (
    CHECKPOINT_PHASE_ORDER,
    EVALUATION_FOLD_COUNT,
    FOLD_SHARD_COUNT,
    FOLD_SHARD_SIZE,
    HISTORICAL_ISSUE_COUNT,
    INITIAL_TRAINING_ISSUES,
    RESAMPLING_CHILD_COUNT,
    RESAMPLING_SCHEMES,
    ROOT_REPLICATES,
)

MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY = (
    "m4-v2-marginal-static-historical-measurement-execution"
)
MARGINAL_STATIC_HISTORICAL_EXECUTION_CAPABILITY = (
    "m4_v2_marginal_static_historical_measurement_execution"
)
MARGINAL_STATIC_HISTORICAL_EXECUTION_COMPLETION_FACT = (
    "m4-v2-marginal-static-historical-measurement-execution:COMPLETE"
)
MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY = (
    "m4-v2-marginal-static-historical-measurement-gate-compiler"
)
MARGINAL_STATIC_HISTORICAL_EXECUTION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-v2-marginal-static-historical-execution-source-v1.json"
)

MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY = (
    "m4-v2-marginal-static-historical-measurement-preregistration"
)
MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_DIGEST = (
    "c3ca378b7ec7c0e5d96bee9bd889e97bdabcc6f43b1e064c53a31247f9ccd808"
)
MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_EXECUTION_ID = (
    "5d23e5412fa39a08f258ef2a070ff490a79b8e9c34fd503d8ebd82d6e41ed19c"
)
MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_EXECUTION_DIGEST = (
    "5523e3269207f46e8ab47eabdd7ad3c698a8198e407dfa1b7c7766e0b0c6c41e"
)
HISTORICAL_DATASET_SNAPSHOT_DIGEST = (
    "999064903fa8a040520ab2a664a1ce3ec35321a90f0e5823626194c64c8d98c6"
)
HISTORICAL_DATASET_CONTENT_DIGEST = (
    "8f7b7527d6ee95301b58002e594b0955b7e0f391421b8c438b87fc4f2507b106"
)
HISTORICAL_FOLD_MANIFEST_DIGEST = (
    "5a68579161ad5528ee15b8b1ea3e314d6acb05203885a5514e5654da026e9ad7"
)
HISTORICAL_CHECKPOINT_ORDER_MANIFEST_DIGEST = (
    "40b85566e977311438add76d301d9614050bfac7fa0de618c1f415299f8b88cd"
)
HISTORICAL_RESAMPLING_MANIFEST_DIGEST = (
    "0115e6143760309409cadce212921b52d5a9448a237b86b0a620542e189ea135"
)
HISTORICAL_EXECUTION_PLAN_DIGEST = (
    "f8491fa0c1c13848979814a00387a197c6140270c55dd4fbe77849060f92f198"
)
HISTORICAL_PREREGISTRATION_COMPLETION_DIGEST = (
    "0e3b9de56776e5636f6bd6c1b85126aa124745a723fe946a591421d37407def5"
)
GATE_COMPILER_CONTRACT_DIGEST = (
    "9f9519be92fb5db4a4fb4939d1d5d3d32f7646a6e449f3dd20fd5c63b409f821"
)

NUMBER_COUNT = 33
DRAW_SIZE = 6
BASELINE_Q = 2.0 / 11.0
BASELINE_NOT_Q = 9.0 / 11.0
PRIMARY_THRESHOLD = 0.01
FAMILYWISE_ALPHA = 0.05
PRIMARY_BLOCK_LENGTH = 5
SIMULTANEOUS_BRANCH_COUNT = 3

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-m4-v2-marginal-static-historical-measurement-execution-round-54-20260808"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-v2-marginal-static-historical-measurement-"
    "execution-round-54-20260808"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/marginal_static_historical_execution.py"
)
FROZEN_CONTRACT_DIGEST = (
    "e299a1450e2c0540bc1cdd660e45a486f2bf1f8ed2bf84f98a3083544e7c6832"
)


class MarginalStaticHistoricalExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarginalStaticHistoricalExecutionRun:
    fold_shards: tuple[Mapping[str, Any], ...]
    completion_index: Mapping[str, Any]
    resampling_output: Mapping[str, Any]
    inference_aggregate: Mapping[str, Any]
    branch_candidate: Mapping[str, Any]
    completion: Mapping[str, Any]
    completion_index_loads: int
    restored_shard_count: int
    skipped_fold_count: int
    newly_computed_fold_count: int

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (
            *self.fold_shards,
            self.completion_index,
            self.resampling_output,
            self.inference_aggregate,
            self.branch_candidate,
            self.completion,
        )


def load_marginal_static_historical_execution_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticHistoricalExecutionError(
            f"marginal_static_historical_execution_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-historical-execution-source.v1"
        or payload.get("artifact_type")
        != "m4_v2_marginal_static_historical_execution_source"
        or payload.get("contract_key")
        != "M4_V2_MARGINAL_STATIC_HISTORICAL_EXECUTION_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 370
        or payload.get("research_execution_id") != 291
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 371
        or payload.get("engineering_execution_id") != 292
        or payload.get("scientific_contract_changed") is not False
        or payload.get("database_queries_during_capability") != 0
        or payload.get("completion_index_loads") != 1
        or payload.get("duplicate_validation") is not False
        or payload.get("evidence_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or len(entries) != 1
        or not isinstance(frozen, dict)
        or payload.get("frozen_contract_digest") != FROZEN_CONTRACT_DIGEST
        or canonical_digest(
            frozen,
            domain=(
                "dehps.m4.v2.marginal-static-historical-execution-frozen-contract.v1"
            ),
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain=("dehps.m4.v2.marginal-static-historical-execution-source-set.v1"),
        )
    ):
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_marginal_static_historical_execution_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MarginalStaticHistoricalExecutionError(
                f"marginal_static_historical_execution_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise MarginalStaticHistoricalExecutionError(
                f"marginal_static_historical_execution_source_modified:{relative}"
            )


def score_issue(
    *, counts: np.ndarray, training_issue_count: int, red_numbers: Sequence[int]
) -> tuple[float, np.ndarray]:
    count_vector = np.asarray(counts, dtype=np.int64)
    if count_vector.shape != (NUMBER_COUNT,) or training_issue_count < 1:
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_count_state_invalid"
        )
    red = np.asarray(tuple(red_numbers), dtype=np.int64)
    if (
        red.shape != (DRAW_SIZE,)
        or np.any(red < 1)
        or np.any(red > NUMBER_COUNT)
        or np.unique(red).size != DRAW_SIZE
    ):
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_red_row_invalid"
        )
    probabilities = (count_vector.astype(np.float64) + BASELINE_Q) / (
        float(training_issue_count) + 1.0
    )
    if (
        np.any(probabilities <= 0.0)
        or np.any(probabilities >= 1.0)
        or not math.isclose(
            float(np.sum(probabilities)),
            float(DRAW_SIZE),
            rel_tol=0.0,
            abs_tol=2e-14,
        )
    ):
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_probability_invalid"
        )
    target = np.zeros(NUMBER_COUNT, dtype=np.bool_)
    target[red - 1] = True
    score = float(
        np.sum(np.log2(probabilities[target] / BASELINE_Q), dtype=np.float64)
        + np.sum(
            np.log2((1.0 - probabilities[~target]) / BASELINE_NOT_Q),
            dtype=np.float64,
        )
    )
    if not math.isfinite(score):
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_score_nonfinite"
        )
    return score, probabilities


def build_marginal_static_historical_execution_artifacts(
    *,
    source_contract: Mapping[str, Any],
    preregistration_execution: Mapping[str, Any],
    dataset_snapshot: Mapping[str, Any],
    fold_manifest: Mapping[str, Any],
    checkpoint_order_manifest: Mapping[str, Any],
    resampling_manifest: Mapping[str, Any],
    execution_plan: Mapping[str, Any],
    preregistration_completion: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
    progress_dir: Path | None = None,
    interrupt_after_shards: int | None = None,
) -> MarginalStaticHistoricalExecutionRun:
    frozen = source_contract.get("frozen_contract")
    if not isinstance(frozen, Mapping):
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_contract_missing"
        )
    _validate_frozen_contract(frozen)
    _validate_registered_inputs_once(
        preregistration_execution=preregistration_execution,
        dataset_snapshot=dataset_snapshot,
        fold_manifest=fold_manifest,
        checkpoint_order_manifest=checkpoint_order_manifest,
        resampling_manifest=resampling_manifest,
        execution_plan=execution_plan,
        preregistration_completion=preregistration_completion,
    )
    if not _is_digest(execution_id) or len(git_commit) != 40:
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_identity_invalid"
        )
    source_digest = str(source_contract["artifact_digest"])
    resume_identity = {
        "task_key": MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY,
        "execution_id": execution_id,
        "git_commit": git_commit,
        "source_contract_digest": source_digest,
        "preregistration_execution_digest": preregistration_execution[
            "artifact_digest"
        ],
        "dataset_snapshot_digest": dataset_snapshot["artifact_digest"],
        "dataset_content_digest": dataset_snapshot["dataset_content_digest"],
        "fold_manifest_digest": fold_manifest["artifact_digest"],
        "checkpoint_order_manifest_digest": checkpoint_order_manifest[
            "artifact_digest"
        ],
        "resampling_manifest_digest": resampling_manifest["artifact_digest"],
        "execution_plan_digest": execution_plan["artifact_digest"],
        "preregistration_completion_digest": preregistration_completion[
            "artifact_digest"
        ],
    }
    records = dataset_snapshot["history_snapshot"]["records"]
    folds = fold_manifest["folds"]
    order_entries = checkpoint_order_manifest["entries"]
    operational = _load_operational_index_once(
        progress_dir=progress_dir,
        resume_identity=resume_identity,
    )
    completion_index_loads = 1
    restored_shards = list(operational["completed_shards"])
    restored_shard_count = len(restored_shards)
    if restored_shards:
        counts = np.asarray(restored_shards[-1]["counts_after_shard"], dtype=np.int64)
        score_entries = [
            dict(entry) for shard in restored_shards for entry in shard["score_entries"]
        ]
    else:
        counts = np.zeros(NUMBER_COUNT, dtype=np.int64)
        for record in records[:INITIAL_TRAINING_ISSUES]:
            red = np.asarray(record["red_numbers"], dtype=np.int64)
            counts[red - 1] += 1
        score_entries = []
    if int(np.sum(counts)) != DRAW_SIZE * (
        INITIAL_TRAINING_ISSUES + len(score_entries)
    ):
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_resume_count_invalid"
        )

    fold_shards: list[dict[str, Any]] = [dict(item) for item in restored_shards]
    newly_computed_fold_count = 0
    for shard_index in range(restored_shard_count, FOLD_SHARD_COUNT):
        start = shard_index * FOLD_SHARD_SIZE
        end = min(start + FOLD_SHARD_SIZE, EVALUATION_FOLD_COUNT)
        shard_entries: list[dict[str, Any]] = []
        for fold_index in range(start, end):
            fold = folds[fold_index]
            order = order_entries[fold_index]
            record = records[int(fold["test_ordinal"]) - 1]
            training_count = int(fold["training_end_ordinal"])
            counts_before_digest = canonical_digest(
                counts.tolist(),
                domain=("dehps.m4.v2.marginal-static-historical-count-vector.v1"),
            )
            checkpoint_digest = canonical_digest(
                {
                    "fold_digest": fold["fold_digest"],
                    "order_digest": order["order_digest"],
                    "phase_order": list(CHECKPOINT_PHASE_ORDER),
                    "training_issue_count": training_count,
                    "counts_digest": counts_before_digest,
                },
                domain=("dehps.m4.v2.marginal-static-historical-virtual-checkpoint.v1"),
            )
            score, probabilities = score_issue(
                counts=counts,
                training_issue_count=training_count,
                red_numbers=record["red_numbers"],
            )
            red = np.asarray(record["red_numbers"], dtype=np.int64)
            counts[red - 1] += 1
            counts_after_digest = canonical_digest(
                counts.tolist(),
                domain=("dehps.m4.v2.marginal-static-historical-count-vector.v1"),
            )
            probability_digest = canonical_digest(
                probabilities.tolist(),
                domain=("dehps.m4.v2.marginal-static-historical-probabilities.v1"),
            )
            settlement_digest = canonical_digest(
                {
                    "fold_digest": fold["fold_digest"],
                    "checkpoint_digest": checkpoint_digest,
                    "probability_digest": probability_digest,
                    "score_bits_per_issue": score,
                    "counts_after_digest": counts_after_digest,
                },
                domain=("dehps.m4.v2.marginal-static-historical-fold-settlement.v1"),
            )
            shard_entries.append(
                {
                    "fold_index": fold_index,
                    "fold_digest": fold["fold_digest"],
                    "test_ordinal": fold["test_ordinal"],
                    "test_issue": fold["test_issue"],
                    "checkpoint_digest": checkpoint_digest,
                    "probability_digest": probability_digest,
                    "score_bits_per_issue": score,
                    "settlement_digest": settlement_digest,
                }
            )
        shard = _artifact(
            schema_version=(
                "dehps-m4-v2-marginal-static-historical-fold-score-shard.v1"
            ),
            artifact_type="m4_v2_marginal_static_historical_fold_score_shard",
            body={
                "status": "SETTLED",
                "source_contract_digest": source_digest,
                "dataset_content_digest": dataset_snapshot["dataset_content_digest"],
                "fold_manifest_digest": fold_manifest["artifact_digest"],
                "checkpoint_order_manifest_digest": checkpoint_order_manifest[
                    "artifact_digest"
                ],
                "shard_index": shard_index,
                "fold_start_index": start,
                "fold_end_index_exclusive": end,
                "fold_count": end - start,
                "score_entries": shard_entries,
                "counts_after_shard": counts.tolist(),
                "counts_after_digest": canonical_digest(
                    counts.tolist(),
                    domain=("dehps.m4.v2.marginal-static-historical-count-vector.v1"),
                ),
                "database_reads": 0,
                "database_writes": 0,
                "duplicate_validation": False,
                "evidence_created": False,
                "production_action": "none",
            },
            parent_digests=(
                source_digest,
                str(dataset_snapshot["artifact_digest"]),
                str(fold_manifest["artifact_digest"]),
                str(checkpoint_order_manifest["artifact_digest"]),
            ),
            domain=("dehps.m4.v2.marginal-static-historical-fold-score-shard.v1"),
        )
        fold_shards.append(shard)
        score_entries.extend(shard_entries)
        newly_computed_fold_count += len(shard_entries)
        _persist_operational_progress(
            progress_dir=progress_dir,
            resume_identity=resume_identity,
            fold_shards=fold_shards,
        )
        if (
            interrupt_after_shards is not None
            and len(fold_shards) >= interrupt_after_shards
        ):
            raise MarginalStaticHistoricalExecutionError(
                "marginal_static_historical_execution_synthetic_interruption"
            )

    if (
        len(fold_shards) != FOLD_SHARD_COUNT
        or len(score_entries) != EVALUATION_FOLD_COUNT
        or [int(item["fold_index"]) for item in score_entries]
        != list(range(EVALUATION_FOLD_COUNT))
        or int(np.sum(counts)) != DRAW_SIZE * HISTORICAL_ISSUE_COUNT
    ):
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_fold_completion_invalid"
        )
    skipped_fold_count = EVALUATION_FOLD_COUNT - newly_computed_fold_count
    completion_index = _artifact(
        schema_version=("dehps-m4-v2-marginal-static-historical-completion-index.v1"),
        artifact_type="m4_v2_marginal_static_historical_completion_index",
        body={
            "status": "COMPLETE",
            "source_contract_digest": source_digest,
            "resume_identity": resume_identity,
            "completed_shard_count": len(fold_shards),
            "completed_fold_count": len(score_entries),
            "shards": [
                {
                    "shard_index": item["shard_index"],
                    "fold_start_index": item["fold_start_index"],
                    "fold_end_index_exclusive": item["fold_end_index_exclusive"],
                    "fold_count": item["fold_count"],
                    "artifact_digest": item["artifact_digest"],
                    "counts_after_digest": item["counts_after_digest"],
                }
                for item in fold_shards
            ],
            "shard_set_digest": canonical_digest(
                fold_shards,
                domain=("dehps.m4.v2.marginal-static-historical-fold-shard-set.v1"),
            ),
            "canonical_score_sequence_digest": canonical_digest(
                score_entries,
                domain=("dehps.m4.v2.marginal-static-historical-score-sequence.v1"),
            ),
            "completion_index_loads": completion_index_loads,
            "completed_fold_action": "skip_from_verified_aggregate_index",
            "routine_physical_checkpoint_scan": False,
            "duplicate_validation": False,
            "partial_run_evidence": "forbidden",
            "evidence_created": False,
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            *(str(item["artifact_digest"]) for item in fold_shards),
        ),
        domain="dehps.m4.v2.marginal-static-historical-completion-index.v1",
    )

    scores = np.asarray(
        [float(item["score_bits_per_issue"]) for item in score_entries],
        dtype=np.float64,
    )
    child_results, scheme_summaries = _execute_resampling(
        scores=scores,
        children=resampling_manifest["children"],
    )
    resampling_output = _artifact(
        schema_version=("dehps-m4-v2-marginal-static-historical-resampling-output.v1"),
        artifact_type="m4_v2_marginal_static_historical_resampling_output",
        body={
            "status": "COMPLETE",
            "source_contract_digest": source_digest,
            "score_sequence_digest": completion_index[
                "canonical_score_sequence_digest"
            ],
            "resampling_manifest_digest": resampling_manifest["artifact_digest"],
            "child_count": len(child_results),
            "scheme_count": len(scheme_summaries),
            "child_results": child_results,
            "scheme_summaries": scheme_summaries,
            "selection_policy": "no_best_seed_or_scheme",
            "sensitivity_decision_credit": False,
            "database_reads": 0,
            "duplicate_validation": False,
            "evidence_created": False,
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(completion_index["artifact_digest"]),
            str(resampling_manifest["artifact_digest"]),
        ),
        domain="dehps.m4.v2.marginal-static-historical-resampling-output.v1",
    )
    inference = _inference_summary(
        scores=scores,
        scheme_summaries=scheme_summaries,
    )
    inference_aggregate = _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-historical-inference-aggregate.v1"
        ),
        artifact_type="m4_v2_marginal_static_historical_inference_aggregate",
        body={
            "status": "COMPLETE",
            "source_contract_digest": source_digest,
            "dataset_content_digest": dataset_snapshot["dataset_content_digest"],
            "score_sequence_digest": completion_index[
                "canonical_score_sequence_digest"
            ],
            "resampling_output_digest": resampling_output["artifact_digest"],
            **inference,
            "formal_historical_folds_executed": EVALUATION_FOLD_COUNT,
            "bootstrap_children_executed": RESAMPLING_CHILD_COUNT,
            "complete_run": True,
            "partial_run_evidence": "forbidden",
            "duplicate_validation": False,
            "evidence_created": False,
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(completion_index["artifact_digest"]),
            str(resampling_output["artifact_digest"]),
        ),
        domain=("dehps.m4.v2.marginal-static-historical-inference-aggregate.v1"),
    )
    branch_candidate = _artifact(
        schema_version=("dehps-m4-v2-marginal-static-historical-branch-candidate.v1"),
        artifact_type="m4_v2_marginal_static_historical_branch_candidate",
        body={
            "status": "READY_FOR_GATE_COMPILER_AFTER_REPLAY",
            "branch_id": "MARGINAL_STATIC",
            "source_contract_digest": source_digest,
            "gate_compiler_contract_digest": GATE_COMPILER_CONTRACT_DIGEST,
            "inference_aggregate_digest": inference_aggregate["artifact_digest"],
            "endpoint_digest": completion_index["canonical_score_sequence_digest"],
            "candidate_estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "baseline_id": "LEGAL_UNIFORM_NUMBER_EVENT_BASELINE",
            "candidate_baseline_distinct": True,
            "measurement_health": "PASS",
            "historical_run_status": "COMPLETE",
            "primary_p_value": inference["primary_raw_p_value"],
            "holm_adjusted_p_value": inference["holm_adjusted_p_value"],
            "effect_interval_bits_per_issue": inference[
                "simultaneous_effect_interval_bits_per_issue"
            ],
            "equivalence_upper_bound_bits_per_issue": inference[
                "equivalence_upper_bound_bits_per_issue"
            ],
            "mde_bits_per_issue": inference["mde_bits_per_issue"],
            "equivalence_power_at_zero": inference["equivalence_power_at_zero"],
            "equivalence_power_sufficient": inference["equivalence_power_sufficient"],
            "half_means_bits_per_issue": inference["half_means_bits_per_issue"],
            "third_means_bits_per_issue": inference["third_means_bits_per_issue"],
            "decision": None,
            "decision_compiled": False,
            "evidence_created": False,
            "accepted_model_artifact_digest": None,
            "promotion_gate_opened": False,
            "next_consumer": MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(inference_aggregate["artifact_digest"]),
        ),
        domain=("dehps.m4.v2.marginal-static-historical-branch-candidate.v1"),
    )
    completion = _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-historical-execution-completion.v1"
        ),
        artifact_type="m4_v2_marginal_static_historical_execution_completion",
        body={
            "status": "COMPLETE",
            "execution_id": execution_id,
            "git_commit": git_commit,
            "source_contract_digest": source_digest,
            "completion_index_digest": completion_index["artifact_digest"],
            "resampling_output_digest": resampling_output["artifact_digest"],
            "inference_aggregate_digest": inference_aggregate["artifact_digest"],
            "branch_candidate_digest": branch_candidate["artifact_digest"],
            "fold_shard_count": len(fold_shards),
            "formal_historical_folds_executed": EVALUATION_FOLD_COUNT,
            "historical_scores_computed": EVALUATION_FOLD_COUNT,
            "bootstrap_children_executed": RESAMPLING_CHILD_COUNT,
            "database_queries_during_capability": 0,
            "completion_index_loads": completion_index_loads,
            "resume_supported": True,
            "duplicate_validation": False,
            "routine_physical_checkpoint_scan": False,
            "evidence_created": False,
            "completion_fact": MARGINAL_STATIC_HISTORICAL_EXECUTION_COMPLETION_FACT,
            "next_consumer": MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(completion_index["artifact_digest"]),
            str(resampling_output["artifact_digest"]),
            str(inference_aggregate["artifact_digest"]),
            str(branch_candidate["artifact_digest"]),
        ),
        domain=("dehps.m4.v2.marginal-static-historical-execution-completion.v1"),
    )
    return MarginalStaticHistoricalExecutionRun(
        fold_shards=tuple(fold_shards),
        completion_index=completion_index,
        resampling_output=resampling_output,
        inference_aggregate=inference_aggregate,
        branch_candidate=branch_candidate,
        completion=completion,
        completion_index_loads=completion_index_loads,
        restored_shard_count=restored_shard_count,
        skipped_fold_count=skipped_fold_count,
        newly_computed_fold_count=newly_computed_fold_count,
    )


def _execute_resampling(
    *, scores: np.ndarray, children: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data = np.asarray(scores, dtype=np.float64)
    if (
        data.shape != (EVALUATION_FOLD_COUNT,)
        or not np.all(np.isfinite(data))
        or len(children) != RESAMPLING_CHILD_COUNT
    ):
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_resampling_input_invalid"
        )
    grouped: dict[str, list[Mapping[str, Any]]] = {
        scheme: [] for scheme in RESAMPLING_SCHEMES
    }
    for child in children:
        scheme = str(child.get("scheme_id"))
        if scheme not in grouped or not _is_digest(child.get("child_digest")):
            raise MarginalStaticHistoricalExecutionError(
                "marginal_static_historical_execution_resampling_child_invalid"
            )
        grouped[scheme].append(child)
    child_results: list[dict[str, Any]] = []
    scheme_summaries: list[dict[str, Any]] = []
    for scheme_id in RESAMPLING_SCHEMES:
        scheme_children = grouped[scheme_id]
        if len(scheme_children) != ROOT_REPLICATES or [
            int(item["replicate_index"]) for item in scheme_children
        ] != list(range(ROOT_REPLICATES)):
            raise MarginalStaticHistoricalExecutionError(
                "marginal_static_historical_execution_resampling_order_invalid"
            )
        if scheme_id.startswith("MOVING_BLOCK_NONCIRCULAR_LENGTH_"):
            block_length = int(scheme_id.split("_LENGTH_")[1].split("_")[0])
            means = _moving_block_means(
                data=data,
                block_length=block_length,
                child_digests=[str(item["child_digest"]) for item in scheme_children],
            )
            topology = "non_circular_moving_block"
        else:
            block_length = int(scheme_id.split("_LENGTH_")[1].split("_")[0])
            means = _stationary_means(
                data=data,
                expected_block_length=block_length,
                child_digests=[str(item["child_digest"]) for item in scheme_children],
            )
            topology = "circular_stationary"
        for child, mean_value in zip(scheme_children, means, strict=True):
            child_results.append(
                {
                    "child_digest": child["child_digest"],
                    "replicate_index": child["replicate_index"],
                    "scheme_id": scheme_id,
                    "resampled_mean_bits_per_issue": float(mean_value),
                }
            )
        scheme_summaries.append(
            {
                "scheme_id": scheme_id,
                "topology": topology,
                "block_length": block_length,
                "replicate_count": ROOT_REPLICATES,
                "means_bits_per_issue": means.tolist(),
                "mean_of_means_bits_per_issue": float(np.mean(means)),
                "standard_deviation_bits_per_issue": float(np.std(means, ddof=1)),
                "decision_credit": scheme_id
                == "MOVING_BLOCK_NONCIRCULAR_LENGTH_5_PRIMARY",
            }
        )
    if len(child_results) != RESAMPLING_CHILD_COUNT:
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_resampling_count_invalid"
        )
    return child_results, scheme_summaries


def _moving_block_means(
    *, data: np.ndarray, block_length: int, child_digests: Sequence[str]
) -> np.ndarray:
    size = int(data.size)
    full_blocks, remainder = divmod(size, block_length)
    cumulative = np.concatenate(([0.0], np.cumsum(data, dtype=np.float64)))
    starts = np.arange(size - block_length + 1)
    block_sums = cumulative[starts + block_length] - cumulative[starts]
    remainder_sums = (
        cumulative[starts + remainder] - cumulative[starts] if remainder else None
    )
    means = np.empty(len(child_digests), dtype=np.float64)
    for index, digest in enumerate(child_digests):
        rng = np.random.Generator(np.random.PCG64DXSM(int(digest, 16)))
        chosen = rng.integers(
            0,
            size - block_length + 1,
            size=full_blocks + int(remainder > 0),
        )
        total = float(np.sum(block_sums[chosen[:full_blocks]], dtype=np.float64))
        if remainder:
            assert remainder_sums is not None
            total += float(remainder_sums[chosen[-1]])
        means[index] = total / size
    return means


def _stationary_means(
    *, data: np.ndarray, expected_block_length: int, child_digests: Sequence[str]
) -> np.ndarray:
    size = int(data.size)
    probability = 1.0 / float(expected_block_length)
    positions = np.arange(size, dtype=np.int64)
    means = np.empty(len(child_digests), dtype=np.float64)
    for index, digest in enumerate(child_digests):
        rng = np.random.Generator(np.random.PCG64DXSM(int(digest, 16)))
        restart = np.empty(size, dtype=np.bool_)
        restart[0] = True
        restart[1:] = rng.random(size - 1) < probability
        restart_positions = positions[restart]
        starts = rng.integers(0, size, size=restart_positions.size)
        block_ids = np.cumsum(restart, dtype=np.int64) - 1
        last_restart = np.maximum.accumulate(np.where(restart, positions, 0))
        source_indices = (starts[block_ids] + positions - last_restart) % size
        means[index] = float(np.mean(data[source_indices]))
    return means


def _inference_summary(
    *, scores: np.ndarray, scheme_summaries: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    observed = float(np.mean(scores))
    primary = next(
        item
        for item in scheme_summaries
        if item["scheme_id"] == "MOVING_BLOCK_NONCIRCULAR_LENGTH_5_PRIMARY"
    )
    raw_means = np.asarray(primary["means_bits_per_issue"], dtype=np.float64)
    centered_null_means = raw_means - observed + PRIMARY_THRESHOLD
    raw_p = float(
        (1 + int(np.count_nonzero(centered_null_means >= observed)))
        / (ROOT_REPLICATES + 1)
    )
    alpha_branch = FAMILYWISE_ALPHA / SIMULTANEOUS_BRANCH_COUNT
    lower, upper = np.quantile(
        raw_means,
        [alpha_branch / 2.0, 1.0 - alpha_branch / 2.0],
        method="linear",
    )
    equivalence_upper = float(
        np.quantile(raw_means, 1.0 - alpha_branch, method="linear")
    )
    standard_error = float(np.std(raw_means, ddof=1))
    if not math.isfinite(standard_error) or standard_error <= 0.0:
        mde = None
        power = None
        power_sufficient = False
    else:
        normal = NormalDist()
        z_alpha = normal.inv_cdf(1.0 - alpha_branch)
        z_power = normal.inv_cdf(0.8)
        mde = max(0.0, (z_alpha + z_power) * standard_error)
        power = normal.cdf(PRIMARY_THRESHOLD / standard_error - z_alpha)
        power_sufficient = power >= 0.8
    adjusted = min(1.0, 3.0 * raw_p)
    return {
        "observed_mean_bits_per_issue": observed,
        "primary_threshold_bits_per_issue": PRIMARY_THRESHOLD,
        "primary_raw_p_value": raw_p,
        "fixed_family_raw_p_values": {
            "MARGINAL_STATIC": raw_p,
            "TEMPORAL_MARGINAL_INCREMENT": 1.0,
            "JOINT_RESIDUAL_INCREMENT": 1.0,
        },
        "fixed_family_holm_adjusted_p_values": {
            "MARGINAL_STATIC": adjusted,
            "TEMPORAL_MARGINAL_INCREMENT": 1.0,
            "JOINT_RESIDUAL_INCREMENT": 1.0,
        },
        "holm_adjusted_p_value": adjusted,
        "simultaneous_effect_interval_bits_per_issue": {
            "lower": float(lower),
            "upper": float(upper),
            "simultaneous_confidence_level": 0.95,
            "per_branch_total_alpha": alpha_branch,
            "quantile_method": "Hyndman-Fan type 7",
        },
        "equivalence_upper_bound_bits_per_issue": equivalence_upper,
        "bootstrap_standard_error_bits_per_issue": standard_error,
        "mde_bits_per_issue": mde,
        "equivalence_power_at_zero": power,
        "equivalence_power_sufficient": power_sufficient,
        "half_means_bits_per_issue": [
            float(np.mean(scores[:1291])),
            float(np.mean(scores[1291:])),
        ],
        "third_means_bits_per_issue": [
            float(np.mean(scores[:861])),
            float(np.mean(scores[861:1721])),
            float(np.mean(scores[1721:])),
        ],
        "conditioning_scope": ("frozen_prequential_trajectory_not_forward_guarantee"),
        "sensitivity_decision_credit": False,
    }


def _load_operational_index_once(
    *, progress_dir: Path | None, resume_identity: Mapping[str, Any]
) -> dict[str, Any]:
    empty = {
        "schema_version": (
            "dehps-m4-v2-marginal-static-historical-operational-index.v1"
        ),
        "artifact_digest": "",
        "resume_identity": dict(resume_identity),
        "completed_shards": [],
    }
    if progress_dir is None:
        return empty
    path = progress_dir / "completion-index.json"
    if not path.exists():
        return empty
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_operational_index_unreadable"
        ) from exc
    identity = dict(payload) if isinstance(payload, dict) else {}
    observed_digest = identity.pop("artifact_digest", None)
    if (
        payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-historical-operational-index.v1"
        or payload.get("resume_identity") != dict(resume_identity)
        or not isinstance(payload.get("completed_shards"), list)
        or observed_digest
        != canonical_digest(
            identity,
            domain=("dehps.m4.v2.marginal-static-historical-operational-index.v1"),
        )
    ):
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_operational_index_invalid"
        )
    shards = payload["completed_shards"]
    if len(shards) > FOLD_SHARD_COUNT or [
        int(item.get("shard_index", -1)) for item in shards
    ] != list(range(len(shards))):
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_operational_shards_invalid"
        )
    return payload


def _persist_operational_progress(
    *,
    progress_dir: Path | None,
    resume_identity: Mapping[str, Any],
    fold_shards: Sequence[Mapping[str, Any]],
) -> None:
    if progress_dir is None:
        return
    progress_dir.mkdir(parents=True, exist_ok=True)
    shard = fold_shards[-1]
    shard_path = (
        progress_dir
        / "shards"
        / f"{int(shard['shard_index']):02d}-{shard['artifact_digest']}.json"
    )
    _persist_immutable_json(shard_path, shard)
    payload = {
        "schema_version": (
            "dehps-m4-v2-marginal-static-historical-operational-index.v1"
        ),
        "artifact_digest": "",
        "resume_identity": dict(resume_identity),
        "completed_shards": [dict(item) for item in fold_shards],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.v2.marginal-static-historical-operational-index.v1",
    )
    _atomic_write_json(progress_dir / "completion-index.json", payload)


def _validate_registered_inputs_once(
    *,
    preregistration_execution: Mapping[str, Any],
    dataset_snapshot: Mapping[str, Any],
    fold_manifest: Mapping[str, Any],
    checkpoint_order_manifest: Mapping[str, Any],
    resampling_manifest: Mapping[str, Any],
    execution_plan: Mapping[str, Any],
    preregistration_completion: Mapping[str, Any],
) -> None:
    records = dataset_snapshot.get("history_snapshot", {}).get("records")
    folds = fold_manifest.get("folds")
    orders = checkpoint_order_manifest.get("entries")
    children = resampling_manifest.get("children")
    if (
        preregistration_execution.get("execution_id")
        != MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_EXECUTION_ID
        or preregistration_execution.get("artifact_digest")
        != MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_EXECUTION_DIGEST
        or preregistration_execution.get("task_key")
        != MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY
        or preregistration_execution.get("task_digest")
        != MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_DIGEST
        or preregistration_execution.get("completion_classification")
        != "VALIDATED_IN_MAINLINE"
        or preregistration_execution.get("registered_artifact_count") != 7
        or dataset_snapshot.get("artifact_digest") != HISTORICAL_DATASET_SNAPSHOT_DIGEST
        or dataset_snapshot.get("dataset_content_digest")
        != HISTORICAL_DATASET_CONTENT_DIGEST
        or fold_manifest.get("artifact_digest") != HISTORICAL_FOLD_MANIFEST_DIGEST
        or checkpoint_order_manifest.get("artifact_digest")
        != HISTORICAL_CHECKPOINT_ORDER_MANIFEST_DIGEST
        or resampling_manifest.get("artifact_digest")
        != HISTORICAL_RESAMPLING_MANIFEST_DIGEST
        or execution_plan.get("artifact_digest") != HISTORICAL_EXECUTION_PLAN_DIGEST
        or preregistration_completion.get("artifact_digest")
        != HISTORICAL_PREREGISTRATION_COMPLETION_DIGEST
        or not isinstance(records, list)
        or len(records) != HISTORICAL_ISSUE_COUNT
        or not isinstance(folds, list)
        or len(folds) != EVALUATION_FOLD_COUNT
        or not isinstance(orders, list)
        or len(orders) != EVALUATION_FOLD_COUNT
        or not isinstance(children, list)
        or len(children) != RESAMPLING_CHILD_COUNT
        or execution_plan.get("formal_historical_execution_authorized") is not False
        or execution_plan.get("duplicate_validation") is not False
    ):
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_registered_lineage_invalid"
        )
    expected_issues = [str(item.get("issue")) for item in records]
    if (
        expected_issues[0] != "2003001"
        or expected_issues[-1] != "2026084"
        or len(set(expected_issues)) != HISTORICAL_ISSUE_COUNT
    ):
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_dataset_order_invalid"
        )
    for fold_index, (fold, order) in enumerate(zip(folds, orders, strict=True)):
        expected_ordinal = INITIAL_TRAINING_ISSUES + fold_index + 1
        record = records[expected_ordinal - 1]
        red = record.get("red_numbers")
        if (
            fold.get("fold_index") != fold_index
            or fold.get("test_ordinal") != expected_ordinal
            or fold.get("training_end_ordinal") != expected_ordinal - 1
            or fold.get("test_issue") != record.get("issue")
            or order.get("fold_index") != fold_index
            or order.get("fold_digest") != fold.get("fold_digest")
            or order.get("phase_order") != list(CHECKPOINT_PHASE_ORDER)
            or not isinstance(red, list)
            or len(red) != DRAW_SIZE
            or sorted(red) != red
            or len(set(red)) != DRAW_SIZE
            or min(red) < 1
            or max(red) > NUMBER_COUNT
        ):
            raise MarginalStaticHistoricalExecutionError(
                "marginal_static_historical_execution_fold_order_invalid"
            )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    scoring = frozen.get("scoring")
    resampling = frozen.get("resampling")
    execution = frozen.get("execution")
    artifacts = frozen.get("artifact_contract")
    if (
        frozen.get("task_key") != MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY
        or frozen.get("capability") != MARGINAL_STATIC_HISTORICAL_EXECUTION_CAPABILITY
        or frozen.get("completion_fact")
        != MARGINAL_STATIC_HISTORICAL_EXECUTION_COMPLETION_FACT
        or frozen.get("next_consumer") != MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY
        or frozen.get("preregistration_execution_digest")
        != MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_EXECUTION_DIGEST
        or not isinstance(scoring, Mapping)
        or scoring.get("fold_count") != EVALUATION_FOLD_COUNT
        or scoring.get("baseline_probability") != "2/11"
        or not isinstance(resampling, Mapping)
        or resampling.get("child_count") != RESAMPLING_CHILD_COUNT
        or resampling.get("generator")
        != "numpy.random.Generator(numpy.random.PCG64DXSM(int(child_digest,16)))"
        or not isinstance(execution, Mapping)
        or execution.get("dataset_loads") != 1
        or execution.get("database_queries") != 0
        or execution.get("completion_index_loads") != 1
        or execution.get("fold_shard_count") != FOLD_SHARD_COUNT
        or execution.get("duplicate_validation") is not False
        or not isinstance(artifacts, Mapping)
        or artifacts.get("registered_child_count") != 16
        or frozen.get("evidence_created") is not False
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("production_action") != "none"
    ):
        raise MarginalStaticHistoricalExecutionError(
            "marginal_static_historical_execution_contract_invalid"
        )


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
    domain: str,
) -> dict[str, Any]:
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


def _persist_immutable_json(path: Path, payload: Mapping[str, Any]) -> None:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise MarginalStaticHistoricalExecutionError(
                "marginal_static_historical_execution_immutable_shard_conflict"
            )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8")


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    temporary.write_text(encoded, encoding="utf-8")
    os.replace(temporary, path)


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
