from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.seed_domains import (
    derive_m4_p2_seed,
)
from dehps.research_os.information_theory.synthetic.contracts import (
    SyntheticRunManifest,
)

from .contracts import MeasurementValidationContractError, MeasurementValidationManifest

ROOT_SEED_SET_DIGEST = (
    "b7fe8fab4e6fbb6387823d8354e6a9ac6da15b03f26ba0dc2ce7756f296e73b7"
)
REPLICATES_PER_CELL = 1000


@dataclass(frozen=True)
class AnalysisCell:
    scale_id: str
    scenario_id: str
    mechanism: str
    signal_strength: str
    target_bits_per_issue: float
    outer_issue_count: int
    scenario_role: str | None = None
    formal_power_eligible: bool | None = None

    @property
    def cell_id(self) -> str:
        return f"{self.scale_id}:{self.scenario_id}"

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "cell_id": self.cell_id,
            "scale_id": self.scale_id,
            "scenario_id": self.scenario_id,
            "mechanism": self.mechanism,
            "signal_strength": self.signal_strength,
            "target_bits_per_issue": self.target_bits_per_issue,
            "outer_issue_count": self.outer_issue_count,
            "replicates": REPLICATES_PER_CELL,
        }
        if self.scenario_role is not None:
            payload.update(
                {
                    "scenario_role": self.scenario_role,
                    "formal_power_eligible": self.formal_power_eligible,
                }
            )
        return payload


@dataclass(frozen=True)
class AnalysisReplicate:
    cell: AnalysisCell
    replicate_index: int
    parent_execution_id: str
    power_replicate_seed: int
    power_replicate_seed_digest: str
    evaluation_dataset_seed: int
    evaluation_dataset_seed_digest: str
    artifact_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "dehps-m4-p2-analysis-replicate-identity.v1",
            "artifact_type": "analysis_replicate_identity",
            "artifact_digest": self.artifact_digest,
            **self.cell.to_dict(),
            "replicate_index": self.replicate_index,
            "parent_execution_id": self.parent_execution_id,
            "power_replicate_seed": self.power_replicate_seed,
            "power_replicate_seed_digest": self.power_replicate_seed_digest,
            "evaluation_dataset_seed": self.evaluation_dataset_seed,
            "evaluation_dataset_seed_digest": self.evaluation_dataset_seed_digest,
        }


@dataclass(frozen=True)
class ShardAssignment:
    replicate: AnalysisReplicate
    shard_count: int
    shard_index: int
    assignment_seed_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.replicate.to_dict(),
            "shard_count": self.shard_count,
            "shard_index": self.shard_index,
            "assignment_seed_digest": self.assignment_seed_digest,
        }


def _scenario_ids(entry: dict[str, Any], synthetic: SyntheticRunManifest) -> tuple[str, ...]:
    declared = entry["scenario_ids"]
    if declared == "ALL_13_FROZEN_SCENARIOS":
        values = tuple(item.scenario_id for item in synthetic.scenarios)
    else:
        values = tuple(str(value) for value in declared)
    if len(values) != int(entry["scenario_count"]) or len(set(values)) != len(values):
        raise MeasurementValidationContractError(
            "measurement_validation_schedule_invalid",
            f"scenario set changed for {entry['scale_id']}",
        )
    return values


def build_cells(
    manifest: MeasurementValidationManifest,
    synthetic: SyntheticRunManifest,
) -> tuple[AnalysisCell, ...]:
    schedule = manifest.payload["workload"]["schedule"]
    repaired_contracts = {
        str(item["scenario_id"]): item
        for item in manifest.payload.get("scenario_contracts", [])
    }
    cells: list[AnalysisCell] = []
    for entry in schedule:
        scale_id = str(entry["scale_id"])
        scale = synthetic.scale(scale_id)
        outer_issue_count = int(entry["outer_issue_count"])
        if scale.outer_evaluation_length != outer_issue_count:
            raise MeasurementValidationContractError(
                "measurement_validation_schedule_invalid",
                f"outer issue count changed for {scale_id}",
            )
        for scenario_id in _scenario_ids(dict(entry), synthetic):
            scenario = synthetic.scenario(scenario_id)
            repaired = repaired_contracts.get(scenario_id)
            cells.append(
                AnalysisCell(
                    scale_id=scale_id,
                    scenario_id=scenario.scenario_id,
                    mechanism=scenario.mechanism,
                    signal_strength=scenario.signal_strength,
                    target_bits_per_issue=(
                        scenario.target_bits_per_issue
                        if repaired is None
                        else float(
                            repaired[
                                "marginal_information_bits_per_issue"
                            ]
                        )
                    ),
                    outer_issue_count=outer_issue_count,
                    scenario_role=(
                        None if repaired is None else str(repaired["role"])
                    ),
                    formal_power_eligible=(
                        None
                        if repaired is None
                        else repaired["role"] == "FORMAL_POWER_TARGET"
                    ),
                )
            )
    if len(cells) != 31 or len({item.cell_id for item in cells}) != 31:
        raise MeasurementValidationContractError(
            "measurement_validation_schedule_invalid",
            "the frozen workload requires exactly 31 unique cells",
        )
    if sum(item.outer_issue_count * REPLICATES_PER_CELL for item in cells) != (
        manifest.outer_issue_predictions
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_schedule_invalid",
            "outer prediction total changed",
        )
    return tuple(cells)


def build_replicate(
    *,
    cell: AnalysisCell,
    replicate_index: int,
    parent_execution_id: str,
) -> AnalysisReplicate:
    if not 0 <= replicate_index < REPLICATES_PER_CELL:
        raise ValueError("replicate_index must be in [0,1000)")
    power = derive_m4_p2_seed(
        root_seed_set_digest=ROOT_SEED_SET_DIGEST,
        seed_domain="M4_P2_POWER_REPLICATE",
        scenario_id=cell.scenario_id,
        method_id=f"{cell.scale_id}:analysis_replicate",
        replicate_index=replicate_index,
        parent_run_digest=parent_execution_id,
    )
    evaluation = derive_m4_p2_seed(
        root_seed_set_digest=ROOT_SEED_SET_DIGEST,
        seed_domain="M4_P2_EVALUATION_DATASET",
        scenario_id=cell.scenario_id,
        method_id=f"{cell.scale_id}:evaluation_dataset",
        replicate_index=replicate_index,
        parent_run_digest=str(power["seed_digest"]),
    )
    identity = {
        "scale_id": cell.scale_id,
        "scenario_id": cell.scenario_id,
        "replicate_index": replicate_index,
        "power_replicate_seed_digest": power["seed_digest"],
        "evaluation_dataset_seed_digest": evaluation["seed_digest"],
        "parent_execution_id": parent_execution_id,
    }
    if cell.scenario_role is not None:
        identity.update(
            {
                "scenario_role": cell.scenario_role,
                "formal_power_eligible": cell.formal_power_eligible,
                "target_bits_per_issue": cell.target_bits_per_issue,
            }
        )
    digest = canonical_digest(
        identity,
        domain="dehps.m4-p2.analysis-replicate-identity.v1",
    )
    return AnalysisReplicate(
        cell=cell,
        replicate_index=replicate_index,
        parent_execution_id=parent_execution_id,
        power_replicate_seed=int(power["seed"]),
        power_replicate_seed_digest=str(power["seed_digest"]),
        evaluation_dataset_seed=int(evaluation["seed"]),
        evaluation_dataset_seed_digest=str(evaluation["seed_digest"]),
        artifact_digest=digest,
    )


def iter_replicates(
    *,
    manifest: MeasurementValidationManifest,
    synthetic: SyntheticRunManifest,
    parent_execution_id: str,
) -> Iterable[AnalysisReplicate]:
    for cell in build_cells(manifest, synthetic):
        for replicate_index in range(REPLICATES_PER_CELL):
            yield build_replicate(
                cell=cell,
                replicate_index=replicate_index,
                parent_execution_id=parent_execution_id,
            )


def assign_shard(replicate: AnalysisReplicate, *, shard_count: int) -> ShardAssignment:
    if shard_count < 1:
        raise ValueError("shard_count must be positive")
    assignment = derive_m4_p2_seed(
        root_seed_set_digest=ROOT_SEED_SET_DIGEST,
        seed_domain="M4_P2_SHARD_ASSIGNMENT",
        scenario_id=replicate.cell.scenario_id,
        method_id=f"{replicate.cell.scale_id}:shards:{shard_count}",
        replicate_index=replicate.replicate_index,
        parent_run_digest=replicate.artifact_digest,
    )
    return ShardAssignment(
        replicate=replicate,
        shard_count=shard_count,
        shard_index=int(assignment["seed"]) % shard_count,
        assignment_seed_digest=str(assignment["seed_digest"]),
    )


def execution_plan_summary(
    *,
    manifest: MeasurementValidationManifest,
    synthetic: SyntheticRunManifest,
    parent_execution_id: str,
    shard_count: int,
) -> dict[str, Any]:
    cells = build_cells(manifest, synthetic)
    counts = [0] * shard_count
    replicate_digests: list[str] = []
    seed_digests: set[str] = set()
    for replicate in iter_replicates(
        manifest=manifest,
        synthetic=synthetic,
        parent_execution_id=parent_execution_id,
    ):
        assignment = assign_shard(replicate, shard_count=shard_count)
        counts[assignment.shard_index] += 1
        replicate_digests.append(replicate.artifact_digest)
        seed_digests.add(replicate.power_replicate_seed_digest)
        seed_digests.add(replicate.evaluation_dataset_seed_digest)
    if len(replicate_digests) != manifest.scenario_replicates:
        raise MeasurementValidationContractError(
            "measurement_validation_schedule_incomplete",
            "not all 31000 replicate identities were generated",
        )
    if len(set(replicate_digests)) != len(replicate_digests):
        raise MeasurementValidationContractError(
            "measurement_validation_duplicate_replicate",
            "replicate identities must be globally unique",
        )
    if len(seed_digests) != 2 * manifest.scenario_replicates:
        raise MeasurementValidationContractError(
            "measurement_validation_duplicate_seed",
            "power and evaluation child seeds must be globally unique",
        )
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-analysis-execution-plan.v1",
        "artifact_type": "analysis_execution_plan",
        "artifact_digest": "",
        "measurement_validation_manifest_digest": manifest.artifact_digest,
        "parent_execution_id": parent_execution_id,
        "cell_count": len(cells),
        "replicate_count": len(replicate_digests),
        "outer_issue_predictions": sum(
            item.outer_issue_count * REPLICATES_PER_CELL for item in cells
        ),
        "shard_count": shard_count,
        "replicate_count_by_shard": counts,
        "ordered_replicate_digest_root": canonical_digest(
            replicate_digests,
            domain="dehps.m4-p2.ordered-analysis-replicates.v1",
        ),
        "seed_set_digest": canonical_digest(
            sorted(seed_digests),
            domain="dehps.m4-p2.analysis-seed-set.v1",
        ),
        "cells": [item.to_dict() for item in cells],
        "resume_reuses_child_seed": True,
        "shard_change_preserves_child_seed": True,
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4-p2.analysis-execution-plan.v1",
    )
    return payload
