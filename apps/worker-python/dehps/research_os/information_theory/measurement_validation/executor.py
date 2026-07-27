from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from dehps.artifacts import atomic_write_text
from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.synthetic.contracts import (
    SyntheticRunManifest,
)

from .contracts import MeasurementValidationContractError, MeasurementValidationManifest
from .gate import aggregate_cell, build_mde_summary
from .journal import checkpoint_journal_path, verify_checkpoint_journal
from .schedule import AnalysisReplicate, assign_shard, iter_replicates


class ReplicateEvaluator(Protocol):
    def evaluate(self, replicate: AnalysisReplicate) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class ShardRunResult:
    shard_index: int
    shard_count: int
    assigned_replicates: int
    completed_replicates: int
    reused_replicates: int
    state_path: Path


@dataclass(frozen=True)
class CompletionResult:
    completion_artifact: Mapping[str, Any]
    completion_artifact_path: Path
    aggregate_artifacts: tuple[Mapping[str, Any], ...]
    aggregate_paths: tuple[Path, ...]
    mde_summary_artifact: Mapping[str, Any]
    mde_summary_path: Path
    replicate_paths: tuple[Path, ...]


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MeasurementValidationContractError(
            "measurement_validation_artifact_invalid",
            f"{path}: {exc}",
        ) from exc
    if not isinstance(value, dict):
        raise MeasurementValidationContractError(
            "measurement_validation_artifact_invalid",
            f"{path} is not an object",
        )
    return value


def persist_immutable(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        if _load_object(path) != dict(payload):
            raise MeasurementValidationContractError(
                "measurement_validation_artifact_collision",
                f"immutable artifact differs: {path}",
            )
        return
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


def _replicate_path(output_dir: Path, replicate: AnalysisReplicate) -> Path:
    return (
        output_dir
        / "replicates"
        / replicate.cell.scale_id
        / replicate.cell.scenario_id
        / f"{replicate.replicate_index:04d}-{replicate.artifact_digest}.json"
    )


def _validate_replicate_result(
    result: Mapping[str, Any],
    *,
    replicate: AnalysisReplicate,
    manifest: MeasurementValidationManifest,
) -> dict[str, Any]:
    payload = dict(result)
    required_identity = replicate.to_dict()
    for key in (
        "cell_id",
        "scale_id",
        "scenario_id",
        "mechanism",
        "signal_strength",
        "target_bits_per_issue",
        "outer_issue_count",
        "replicate_index",
        "parent_execution_id",
        "power_replicate_seed_digest",
        "evaluation_dataset_seed_digest",
    ):
        if payload.get(key) != required_identity[key]:
            raise MeasurementValidationContractError(
                "measurement_validation_replicate_identity_mismatch",
                f"{key} changed for {replicate.artifact_digest}",
            )
    if (
        payload.get("status") != "COMPLETE"
        or payload.get("bootstrap_replicate_count")
        != manifest.bootstrap_replicates
        or payload.get("permutation_replicate_count")
        != manifest.permutation_replicates
        or payload.get("leakage_status") != "PASS"
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_replicate_incomplete",
            f"formal replicate did not complete: {replicate.artifact_digest}",
        )
    probe_digests = payload.get("probe_run_digests")
    if (
        not isinstance(probe_digests, Mapping)
        or tuple(sorted(probe_digests))
        != tuple(sorted(manifest.payload["workload"]["probe_allowlist"]))
        or any(
            not isinstance(value, str) or len(value) != 64
            for value in probe_digests.values()
        )
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_probe_output_incomplete",
            "all four frozen probe digests are required",
        )
    for key in (
        "dataset_digest",
        "truth_artifact_digest",
        "ordered_outer_checkpoint_digest",
        "ordered_settlement_digest",
        "bootstrap_seed_set_digest",
        "permutation_seed_set_digest",
        "checkpoint_journal_digest",
    ):
        value = payload.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise MeasurementValidationContractError(
                "measurement_validation_replicate_incomplete",
                f"{key} is missing",
            )
    if (
        payload.get("checkpoint_journal_entry_count")
        != replicate.cell.outer_issue_count
        or payload.get("checkpoint_journal_path")
        != str(
            checkpoint_journal_path(Path("."), replicate).relative_to(
                Path(".")
            )
        )
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_checkpoint_journal_incomplete",
            "strict-prior checkpoint journal identity or count is missing",
        )
    for key in ("PE1", "PE2"):
        value = payload.get(key)
        if not isinstance(value, (int, float)):
            raise MeasurementValidationContractError(
                "measurement_validation_replicate_incomplete",
                f"{key} is missing",
            )
    if not isinstance(payload.get("truth_bits_per_issue"), (int, float)):
        raise MeasurementValidationContractError(
            "measurement_validation_replicate_incomplete",
            "P2.4 truth value is missing",
        )
    is_negative_control = replicate.cell.scenario_id == "NULL_UNIFORM"
    if (
        payload.get("negative_control_id")
        != ("NC6_SYNTHETIC_NULL" if is_negative_control else None)
        or payload.get("negative_control_replicate_index")
        != (replicate.replicate_index if is_negative_control else None)
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_negative_control_identity_mismatch",
            "formal NC6 identity must match the frozen NULL_UNIFORM cell",
        )
    if not isinstance(payload.get("confidence_intervals"), Mapping):
        raise MeasurementValidationContractError(
            "measurement_validation_replicate_incomplete",
            "confidence intervals are missing",
        )

    payload["schema_version"] = "dehps-m4-p2-analysis-replicate.v1"
    payload["artifact_type"] = "measurement_validation_analysis_replicate"
    payload["identity_artifact_digest"] = replicate.artifact_digest
    payload["measurement_validation_manifest_digest"] = manifest.artifact_digest
    payload["artifact_digest"] = ""
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4-p2.measurement-analysis-replicate.v1",
    )
    return payload


def run_shard(
    *,
    manifest: MeasurementValidationManifest,
    synthetic: SyntheticRunManifest,
    parent_execution_id: str,
    output_dir: Path,
    shard_index: int,
    shard_count: int,
    evaluator: ReplicateEvaluator,
    stop_after: int | None = None,
) -> ShardRunResult:
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must be in [0, shard_count)")
    assigned = 0
    completed = 0
    reused = 0
    processed_this_call = 0
    ordered_result_digests: list[str] = []
    for replicate in iter_replicates(
        manifest=manifest,
        synthetic=synthetic,
        parent_execution_id=parent_execution_id,
    ):
        assignment = assign_shard(replicate, shard_count=shard_count)
        if assignment.shard_index != shard_index:
            continue
        assigned += 1
        path = _replicate_path(output_dir, replicate)
        if path.is_file():
            existing = _load_object(path)
            if existing.get("identity_artifact_digest") != replicate.artifact_digest:
                raise MeasurementValidationContractError(
                    "measurement_validation_resume_identity_mismatch",
                    f"resume identity changed: {path}",
                )
            reused += 1
            completed += 1
            ordered_result_digests.append(str(existing["artifact_digest"]))
            continue
        result = _validate_replicate_result(
            evaluator.evaluate(replicate),
            replicate=replicate,
            manifest=manifest,
        )
        persist_immutable(path, result)
        completed += 1
        processed_this_call += 1
        ordered_result_digests.append(str(result["artifact_digest"]))
        if stop_after is not None and processed_this_call >= stop_after:
            break

    state: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-analysis-shard-state.v1",
        "status": (
            "COMPLETE"
            if completed == assigned and stop_after is None
            else "INTERRUPTED"
        ),
        "parent_execution_id": parent_execution_id,
        "measurement_validation_manifest_digest": manifest.artifact_digest,
        "shard_index": shard_index,
        "shard_count": shard_count,
        "assigned_replicates": assigned,
        "completed_replicates": completed,
        "reused_replicates": reused,
        "ordered_result_digest_root": canonical_digest(
            ordered_result_digests,
            domain="dehps.m4-p2.analysis-shard-results.v1",
        ),
    }
    state_path = output_dir / "shards" / f"{shard_index:04d}-of-{shard_count:04d}.json"
    atomic_write_text(
        state_path,
        json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    return ShardRunResult(
        shard_index=shard_index,
        shard_count=shard_count,
        assigned_replicates=assigned,
        completed_replicates=completed,
        reused_replicates=reused,
        state_path=state_path,
    )


def assemble_completion(
    *,
    manifest: MeasurementValidationManifest,
    synthetic: SyntheticRunManifest,
    parent_execution_id: str,
    output_dir: Path,
    git_commit: str,
) -> CompletionResult:
    replicate_paths: list[Path] = []
    replicates_by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_result_digests: set[str] = set()
    duplicate_count = 0
    bootstrap_seed_count = 0
    permutation_seed_count = 0
    negative_control_replicate_count = 0
    leakage_failure_count = 0
    failed_replicate_count = 0
    checkpoint_journal_failure_count = 0
    checkpoint_journal_digests: list[str] = []
    for replicate in iter_replicates(
        manifest=manifest,
        synthetic=synthetic,
        parent_execution_id=parent_execution_id,
    ):
        path = _replicate_path(output_dir, replicate)
        if not path.is_file():
            raise MeasurementValidationContractError(
                "measurement_validation_workload_incomplete",
                f"missing formal replicate: {replicate.artifact_digest}",
            )
        payload = _load_object(path)
        if payload.get("identity_artifact_digest") != replicate.artifact_digest:
            raise MeasurementValidationContractError(
                "measurement_validation_replicate_identity_mismatch",
                f"stored identity changed: {path}",
            )
        stored_identity = dict(payload)
        stored_digest = str(stored_identity.pop("artifact_digest", ""))
        if stored_digest != canonical_digest(
            stored_identity,
            domain="dehps.m4-p2.measurement-analysis-replicate.v1",
        ):
            raise MeasurementValidationContractError(
                "measurement_validation_replicate_digest_mismatch",
                f"stored replicate digest changed: {path}",
            )
        try:
            verify_checkpoint_journal(
                output_dir=output_dir,
                replicate=replicate,
                expected_digest=str(payload["checkpoint_journal_digest"]),
                expected_fold_count=replicate.cell.outer_issue_count,
            )
        except MeasurementValidationContractError:
            checkpoint_journal_failure_count += 1
            raise
        checkpoint_journal_digests.append(
            str(payload["checkpoint_journal_digest"])
        )
        result_digest = str(payload.get("artifact_digest") or "")
        if result_digest in seen_result_digests:
            duplicate_count += 1
        seen_result_digests.add(result_digest)
        if payload.get("status") != "COMPLETE":
            failed_replicate_count += 1
        if payload.get("leakage_status") != "PASS":
            leakage_failure_count += 1
        bootstrap_seed_count += int(payload.get("bootstrap_replicate_count") or 0)
        permutation_seed_count += int(payload.get("permutation_replicate_count") or 0)
        if payload.get("negative_control_id") == "NC6_SYNTHETIC_NULL":
            negative_control_replicate_count += 1
        replicates_by_cell[replicate.cell.cell_id].append(payload)
        replicate_paths.append(path)
    if len(replicate_paths) != manifest.scenario_replicates:
        raise MeasurementValidationContractError(
            "measurement_validation_workload_incomplete",
            "not all 31000 formal replicates were found",
        )

    aggregate_artifacts: list[dict[str, Any]] = []
    aggregate_paths: list[Path] = []
    for cell_id in sorted(replicates_by_cell):
        children = sorted(
            replicates_by_cell[cell_id],
            key=lambda item: int(item["replicate_index"]),
        )
        aggregate = aggregate_cell(children, manifest=manifest)
        aggregate_path = (
            output_dir
            / "aggregates"
            / str(aggregate["scale_id"])
            / f"{aggregate['scenario_id']}-{aggregate['artifact_digest']}.json"
        )
        persist_immutable(aggregate_path, aggregate)
        aggregate_artifacts.append(aggregate)
        aggregate_paths.append(aggregate_path)
    if len(aggregate_artifacts) != 31:
        raise MeasurementValidationContractError(
            "measurement_validation_aggregate_incomplete",
            "exactly 31 cell aggregates are required",
        )
    negative_control_aggregates = [
        item
        for item in aggregate_artifacts
        if item.get("negative_control_id") == "NC6_SYNTHETIC_NULL"
    ]
    if (
        len(negative_control_aggregates) != 3
        or negative_control_replicate_count
        != len(negative_control_aggregates)
        * manifest.negative_control_replicates
        or any(
            item.get("negative_control_replicate_count")
            != manifest.negative_control_replicates
            for item in negative_control_aggregates
        )
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_negative_control_incomplete",
            "each frozen scale requires exactly 1000 NC6 synthetic-null replicates",
        )
    mde_summary = build_mde_summary(aggregate_artifacts)
    mde_summary_path = (
        output_dir
        / "mde"
        / str(mde_summary["artifact_digest"])
        / "mde.json"
    )
    persist_immutable(mde_summary_path, mde_summary)

    ordered_replicate_digests = [
        str(_load_object(path)["artifact_digest"]) for path in replicate_paths
    ]
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-measurement-validation-completion.v1",
        "artifact_type": "measurement_validation_completion",
        "artifact_digest": "",
        "status": "COMPLETE",
        "parent_execution_id": parent_execution_id,
        "measurement_validation_manifest_digest": manifest.artifact_digest,
        "replicate_count": len(replicate_paths),
        "cell_aggregate_count": len(aggregate_artifacts),
        "outer_issue_predictions": manifest.outer_issue_predictions,
        "duplicate_replicate_count": duplicate_count,
        "failed_replicate_count": failed_replicate_count,
        "bootstrap_seed_count": bootstrap_seed_count,
        "permutation_seed_count": permutation_seed_count,
        "negative_control_id": "NC6_SYNTHETIC_NULL",
        "negative_control_cell_count": len(negative_control_aggregates),
        "negative_control_replicates_per_cell": (
            manifest.negative_control_replicates
        ),
        "negative_control_replicate_count": (
            negative_control_replicate_count
        ),
        "negative_control_seed_set_digests": [
            item["negative_control_seed_set_digest"]
            for item in negative_control_aggregates
        ],
        "incomplete_seed_set_count": sum(
            int(item.get("bootstrap_replicate_count") or 0)
            != manifest.bootstrap_replicates
            or int(item.get("permutation_replicate_count") or 0)
            != manifest.permutation_replicates
            for values in replicates_by_cell.values()
            for item in values
        ),
        "leakage_failure_count": leakage_failure_count,
        "checkpoint_journal_count": len(checkpoint_journal_digests),
        "checkpoint_journal_failure_count": (
            checkpoint_journal_failure_count
        ),
        "ordered_checkpoint_journal_digest_root": canonical_digest(
            checkpoint_journal_digests,
            domain="dehps.m4-p2.ordered-checkpoint-journals.v1",
        ),
        "ordered_replicate_digest_root": canonical_digest(
            ordered_replicate_digests,
            domain="dehps.m4-p2.ordered-formal-replicate-results.v1",
        ),
        "aggregate_digests": [
            item["artifact_digest"] for item in aggregate_artifacts
        ],
        "mde_summary_digest": mde_summary["artifact_digest"],
        "decision_policy_mde_at_61_bits_per_issue": mde_summary[
            "decision_policy_mde_at_61_bits_per_issue"
        ],
        "eligible_for_power_evidence": True,
        "eligible_for_false_positive_evidence": True,
        "evidence_created": True,
        "real_history_used": False,
        "production_action": "none",
        "git_commit": git_commit,
        "working_tree_clean": True,
        "parent_digests": [
            manifest.artifact_digest,
            *ordered_replicate_digests,
            *(str(item["artifact_digest"]) for item in aggregate_artifacts),
            str(mde_summary["artifact_digest"]),
        ],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4-p2.measurement-validation-completion.v1",
    )
    completion_path = (
        output_dir
        / "completion"
        / str(payload["artifact_digest"])
        / "completion.json"
    )
    persist_immutable(completion_path, payload)
    return CompletionResult(
        completion_artifact=payload,
        completion_artifact_path=completion_path,
        aggregate_artifacts=tuple(aggregate_artifacts),
        aggregate_paths=tuple(aggregate_paths),
        mde_summary_artifact=mde_summary,
        mde_summary_path=mde_summary_path,
        replicate_paths=tuple(replicate_paths),
    )


def verify_completion_replay(
    *,
    manifest: MeasurementValidationManifest,
    synthetic: SyntheticRunManifest,
    parent_execution_id: str,
    output_dir: Path,
    git_commit: str,
    expected_completion_digest: str,
) -> dict[str, Any]:
    replay = assemble_completion(
        manifest=manifest,
        synthetic=synthetic,
        parent_execution_id=parent_execution_id,
        output_dir=output_dir,
        git_commit=git_commit,
    )
    actual = str(replay.completion_artifact["artifact_digest"])
    if actual != expected_completion_digest:
        raise MeasurementValidationContractError(
            "measurement_validation_replay_mismatch",
            f"completion changed: expected {expected_completion_digest}, got {actual}",
        )
    return {
        "schema_version": "dehps-m4-p2-measurement-validation-replay.v1",
        "status": "REPLAY_VERIFIED",
        "parent_execution_id": parent_execution_id,
        "completion_artifact_digest": actual,
        "replicate_count": len(replay.replicate_paths),
        "aggregate_count": len(replay.aggregate_artifacts),
        "mde_summary_digest": replay.mde_summary_artifact[
            "artifact_digest"
        ],
        "same_replicate_identity": True,
        "same_aggregate_identity": True,
        "same_mde_identity": True,
        "same_completion_identity": True,
        "manual_input_assembly": False,
    }
