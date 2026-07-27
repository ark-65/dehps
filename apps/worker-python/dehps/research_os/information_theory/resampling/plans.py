from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.seed_domains import derive_m4_p2_seed

from .contracts import ResamplingError, ResamplingKernelManifest


@dataclass(frozen=True)
class ResamplingPlan:
    method: str
    source_issue_count: int
    source_indices: tuple[int, ...]
    seed: int | None
    seed_digest: str | None
    config: Mapping[str, Any]
    plan_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "dehps-m4-p2-resampling-plan.v1",
            "artifact_type": "resampling_plan",
            "artifact_digest": self.plan_digest,
            "method": self.method,
            "source_issue_count": self.source_issue_count,
            "resampled_issue_count": len(self.source_indices),
            "source_indices": list(self.source_indices),
            "seed": self.seed,
            "seed_digest": self.seed_digest,
            "config": dict(self.config),
            "plan_digest": self.plan_digest,
        }


def _derive(
    *,
    manifest: ResamplingKernelManifest,
    seed_domain: str,
    scenario_id: str,
    method_id: str,
    replicate_index: int,
    parent_run_digest: str,
) -> tuple[np.random.Generator, int, str]:
    derived = derive_m4_p2_seed(
        root_seed_set_digest=manifest.root_seed_set_digest,
        seed_domain=seed_domain,
        scenario_id=scenario_id,
        method_id=method_id,
        replicate_index=replicate_index,
        parent_run_digest=parent_run_digest,
    )
    seed = int(derived["seed"])
    return np.random.default_rng(seed), seed, str(derived["seed_digest"])


def _build_plan(
    *,
    method: str,
    issue_count: int,
    indices: Sequence[int],
    seed: int | None,
    seed_digest: str | None,
    config: Mapping[str, Any],
) -> ResamplingPlan:
    identity = {
        "method": method,
        "source_issue_count": issue_count,
        "source_indices": list(indices),
        "seed": seed,
        "seed_digest": seed_digest,
        "config": dict(config),
    }
    digest = canonical_digest(identity, domain="dehps.m4-p2.resampling-plan.v1")
    return ResamplingPlan(
        method=method,
        source_issue_count=issue_count,
        source_indices=tuple(int(value) for value in indices),
        seed=seed,
        seed_digest=seed_digest,
        config=dict(config),
        plan_digest=digest,
    )


def moving_block_plan(
    issue_count: int,
    *,
    block_size: int,
    manifest: ResamplingKernelManifest,
    scenario_id: str,
    replicate_index: int,
    parent_run_digest: str,
) -> ResamplingPlan:
    if issue_count < block_size or block_size < 1:
        raise ResamplingError(
            "insufficient_issues_for_block_size",
            "non-circular moving block requires N >= L >= 1",
        )
    rng, seed, seed_digest = _derive(
        manifest=manifest,
        seed_domain="M4_P2_BOOTSTRAP",
        scenario_id=scenario_id,
        method_id=f"moving_block_L{block_size}",
        replicate_index=replicate_index,
        parent_run_digest=parent_run_digest,
    )
    starts: list[int] = []
    indices: list[int] = []
    while len(indices) < issue_count:
        start = int(rng.integers(0, issue_count - block_size + 1))
        starts.append(start)
        indices.extend(range(start, start + block_size))
    indices = indices[:issue_count]
    return _build_plan(
        method="moving_block_bootstrap",
        issue_count=issue_count,
        indices=indices,
        seed=seed,
        seed_digest=seed_digest,
        config={
            "block_size": block_size,
            "topology": "non_circular",
            "block_start_positions": starts,
            "overflow_policy": "truncate_right",
        },
    )


def stationary_plan(
    issue_count: int,
    *,
    expected_block_length: int,
    manifest: ResamplingKernelManifest,
    scenario_id: str,
    replicate_index: int,
    parent_run_digest: str,
) -> ResamplingPlan:
    if issue_count < 1 or expected_block_length < 1:
        raise ResamplingError("invalid_stationary_bootstrap", "N and expected length must be positive")
    rng, seed, seed_digest = _derive(
        manifest=manifest,
        seed_domain="M4_P2_STATIONARY_BOOTSTRAP",
        scenario_id=scenario_id,
        method_id=f"stationary_L{expected_block_length}",
        replicate_index=replicate_index,
        parent_run_digest=parent_run_digest,
    )
    current = int(rng.integers(0, issue_count))
    indices = [current]
    restarts = [0]
    probability = 1.0 / expected_block_length
    for position in range(1, issue_count):
        if rng.random() < probability:
            current = int(rng.integers(0, issue_count))
            restarts.append(position)
        else:
            current = (current + 1) % issue_count
        indices.append(current)
    return _build_plan(
        method="stationary_bootstrap",
        issue_count=issue_count,
        indices=indices,
        seed=seed,
        seed_digest=seed_digest,
        config={
            "expected_block_length": expected_block_length,
            "restart_probability": probability,
            "topology": "circular",
            "restart_positions": restarts,
            "role": "sensitivity_only",
        },
    )


def block_permutation_plan(
    issue_count: int,
    *,
    block_size: int,
    manifest: ResamplingKernelManifest,
    scenario_id: str,
    replicate_index: int,
    parent_run_digest: str,
) -> ResamplingPlan:
    blocks = [
        list(range(start, min(start + block_size, issue_count)))
        for start in range(0, issue_count, block_size)
    ]
    if len(blocks) < 2:
        raise ResamplingError(
            "insufficient_blocks_for_permutation",
            "block permutation requires at least two blocks",
        )
    rng, seed, seed_digest = _derive(
        manifest=manifest,
        seed_domain="M4_P2_ISSUE_PERMUTATION",
        scenario_id=scenario_id,
        method_id=f"block_permutation_L{block_size}",
        replicate_index=replicate_index,
        parent_run_digest=parent_run_digest,
    )
    order = list(range(len(blocks)))
    for _ in range(32):
        candidate = rng.permutation(len(blocks)).tolist()
        if candidate != order:
            order = candidate
            break
    else:
        raise ResamplingError("identity_permutation_forbidden", "could not draw non-identity block order")
    indices = [index for block_index in order for index in blocks[block_index]]
    return _build_plan(
        method="block_permutation",
        issue_count=issue_count,
        indices=indices,
        seed=seed,
        seed_digest=seed_digest,
        config={
            "block_size": block_size,
            "topology": "non_circular",
            "block_order": order,
            "tail_block_length": len(blocks[-1]),
            "within_block_order": "preserved",
        },
    )


def issue_label_permutation_plan(
    issue_count: int,
    *,
    manifest: ResamplingKernelManifest,
    scenario_id: str,
    replicate_index: int,
    parent_run_digest: str,
) -> ResamplingPlan:
    if issue_count < 2:
        raise ResamplingError("insufficient_issues_for_permutation", "at least two issues are required")
    rng, seed, seed_digest = _derive(
        manifest=manifest,
        seed_domain="M4_P2_ISSUE_PERMUTATION",
        scenario_id=scenario_id,
        method_id="issue_label_permutation",
        replicate_index=replicate_index,
        parent_run_digest=parent_run_digest,
    )
    identity = list(range(issue_count))
    indices = identity
    for _ in range(32):
        candidate = rng.permutation(issue_count).tolist()
        if candidate != identity:
            indices = candidate
            break
    else:
        raise ResamplingError("identity_permutation_forbidden", "could not draw non-identity issue mapping")
    return _build_plan(
        method="issue_label_permutation",
        issue_count=issue_count,
        indices=indices,
        seed=seed,
        seed_digest=seed_digest,
        config={"mapping_is_bijection": True, "prediction_identity": "preserved"},
    )


def number_label_permutation(
    *,
    manifest: ResamplingKernelManifest,
    scenario_id: str,
    replicate_index: int,
    parent_run_digest: str,
) -> tuple[dict[int, int], int, str, str]:
    rng, seed, seed_digest = _derive(
        manifest=manifest,
        seed_domain="M4_P2_NUMBER_PERMUTATION",
        scenario_id=scenario_id,
        method_id="number_label_permutation",
        replicate_index=replicate_index,
        parent_run_digest=parent_run_digest,
    )
    identity = np.arange(1, 34)
    mapped = identity
    for _ in range(32):
        candidate = rng.permutation(identity)
        if not np.array_equal(candidate, identity):
            mapped = candidate
            break
    else:
        raise ResamplingError("identity_permutation_forbidden", "could not draw non-identity number mapping")
    mapping = {int(left): int(right) for left, right in zip(identity, mapped, strict=True)}
    digest = canonical_digest(
        {str(key): value for key, value in mapping.items()},
        domain="dehps.m4-p2.number-label-mapping.v1",
    )
    return mapping, seed, seed_digest, digest


def circular_shift_plan(issue_count: int, *, shift: int) -> ResamplingPlan:
    if shift <= 0 or shift >= issue_count:
        raise ResamplingError("invalid_circular_shift", "shift must satisfy 1 <= k < N")
    indices = [(index + shift) % issue_count for index in range(issue_count)]
    return _build_plan(
        method="circular_target_shift",
        issue_count=issue_count,
        indices=indices,
        seed=None,
        seed_digest=None,
        config={
            "shift": shift,
            "direction": "target_forward_relative_to_prediction",
            "topology": "circular",
            "effective_issue_count": issue_count,
        },
    )


def shard_for_replicate(replicate_index: int, shard_count: int) -> int:
    if replicate_index < 0 or shard_count < 1:
        raise ResamplingError("invalid_shard_contract", "replicate and shard count are invalid")
    return replicate_index % shard_count


def apply_issue_plan(
    issues: Sequence[Mapping[str, Any]],
    plan: ResamplingPlan,
) -> tuple[dict[str, Any], ...]:
    if len(issues) != plan.source_issue_count:
        raise ResamplingError("source_issue_count_mismatch", "plan and source lengths differ")
    result: list[dict[str, Any]] = []
    for position, source_index in enumerate(plan.source_indices):
        source = dict(issues[source_index])
        target = source.get("target_vector")
        if (
            not isinstance(target, list)
            or len(target) != 33
            or sum(int(value) for value in target) != 6
        ):
            raise ResamplingError("issue_cluster_split", "source issue is not one legal target cluster")
        result.append(
            {
                **source,
                "source_issue_id": str(source.get("issue_id", source.get("issue_index"))),
                "resampled_position": position,
                "cluster_id": str(source.get("cluster_id", source.get("issue_index"))),
            }
        )
    return tuple(result)
