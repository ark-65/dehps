from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from dehps.research_os.information_theory.digest import config_digest


KERNEL_MANIFEST_DIGEST = (
    "1cde473524d7d6dcafba64ab7b0a1d2862b56149d5f6f198c73d88b406c3071b"
)
PREREGISTRATION_DIGEST = (
    "4fff51c58e4a46d664e414bfe4cc0d7269c8e3712734153faec548648144d0d9"
)
DECISION_POLICY_DIGEST = (
    "824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d"
)
SYNTHETIC_MANIFEST_DIGEST = (
    "f84c2da3565f7eda41c3782517c78211805f57ea8f3bfd00659a93c380826a3c"
)
METRIC_KERNEL_DIGEST = (
    "56b9d0a62d43d167069e5222c7095383c9c5106bb3361b0b1def75cf2b6c86a2"
)
WALK_FORWARD_HARNESS_DIGEST = (
    "177a3d591b7557a4231a276bfb007f0d42a94d942824403f5376f94fe904d2ca"
)
P24_COMPLETION_DIGEST = (
    "328144fa1abebfee88d46dbbce6d9deb7b9f1f5834fb9a0c83cc55adef32a353"
)
P24_EXECUTION_ID = (
    "772b5063f1a3578c7e8f8a2cd9f102357828608de8fbd80c2c1fb2c82b79afa2"
)
CONTROL_IDS = (
    "NC1_ISSUE_LABEL_PERMUTATION",
    "NC2_NUMBER_LABEL_PERMUTATION",
    "NC3_CIRCULAR_TARGET_SHIFT",
    "NC4_MATCHED_RANDOM_FEATURES",
    "NC5_MATCHED_RANDOM_SCORE",
    "NC6_SYNTHETIC_NULL",
)
SMOKE_FLAGS = (
    "SMOKE_TEST_ONLY",
    "NOT_FALSE_POSITIVE_EVIDENCE",
    "NOT_POWER_EVIDENCE",
    "NOT_MDE_EVIDENCE",
    "NOT_P2_GATE_EVIDENCE",
)


class ResamplingContractError(ValueError):
    pass


class ResamplingError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class ResamplingKernelManifest:
    payload: Mapping[str, Any]
    artifact_digest: str
    root_seed_set_digest: str
    primary_block_size: int
    sensitivity_block_sizes: tuple[int, ...]
    stationary_lengths: tuple[int, ...]
    frozen_shifts: tuple[int, ...]
    controls: tuple[Mapping[str, Any], ...]
    smoke_flags: tuple[str, ...]
    truth_artifact_digests: tuple[str, ...]
    injected_signal_completion_digest: str
    injected_signal_execution_id: str


def load_resampling_manifest(path: Path) -> ResamplingKernelManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResamplingContractError(str(exc)) from exc
    if not isinstance(payload, Mapping):
        raise ResamplingContractError("resampling manifest must be an object")
    return validate_resampling_manifest(payload)


def validate_resampling_manifest(
    payload: Mapping[str, Any],
) -> ResamplingKernelManifest:
    if (
        payload.get("schema_version")
        != "dehps-m4-p2-resampling-kernel-manifest.v1"
        or payload.get("artifact_type") != "resampling_kernel_manifest"
        or payload.get("phase") != "M4-P2.5"
        or payload.get("status") != "FROZEN"
        or payload.get("statistical_unit") != "issue"
    ):
        raise ResamplingContractError("P2.5 kernel manifest is not frozen")
    expected = {
        "preregistration_digest": PREREGISTRATION_DIGEST,
        "decision_policy_digest": DECISION_POLICY_DIGEST,
        "synthetic_manifest_digest": SYNTHETIC_MANIFEST_DIGEST,
        "metric_kernel_digest": METRIC_KERNEL_DIGEST,
        "walk_forward_harness_digest": WALK_FORWARD_HARNESS_DIGEST,
        "injected_signal_completion_digest": P24_COMPLETION_DIGEST,
        "injected_signal_execution_id": P24_EXECUTION_ID,
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            raise ResamplingContractError(f"{field} changed")
    methods = payload.get("methods")
    if not isinstance(methods, Mapping):
        raise ResamplingContractError("resampling methods are missing")
    moving = methods.get("moving_block_bootstrap")
    stationary = methods.get("stationary_bootstrap")
    block_permutation = methods.get("block_permutation")
    if (
        not isinstance(moving, Mapping)
        or moving.get("topology") != "non_circular"
        or moving.get("primary_block_size") != 5
        or moving.get("sensitivity_block_sizes") != [3, 5, 8, 13]
        or not isinstance(stationary, Mapping)
        or stationary.get("topology") != "circular"
        or stationary.get("expected_block_lengths") != [3, 5, 8, 13]
        or stationary.get("role") != "sensitivity_only"
        or not isinstance(block_permutation, Mapping)
        or block_permutation.get("block_size") != 5
        or block_permutation.get("tail_block_policy")
        != "include_as_final_distinct_block"
        or block_permutation.get("identity_permutation") != "forbidden"
    ):
        raise ResamplingContractError("frozen resampling semantics changed")
    shift = payload.get("circular_shift")
    if (
        not isinstance(shift, Mapping)
        or shift.get("formula")
        != "shifted_target[t]=original_target[(t+k) mod N]"
        or shift.get("direction") != "target_forward_relative_to_prediction"
        or shift.get("frozen_shifts") != [1, 2, 3, 5, 8, 13, 21]
    ):
        raise ResamplingContractError("circular shift semantics changed")
    controls = payload.get("negative_controls")
    if (
        not isinstance(controls, list)
        or tuple(item.get("control_id") for item in controls) != CONTROL_IDS
    ):
        raise ResamplingContractError("negative-control registry changed")
    for control in controls:
        applicable = control.get("applicable_artifact_types")
        required = control.get("required_upstream_digests")
        statistic = control.get("statistic_contract")
        if (
            not isinstance(applicable, list)
            or not applicable
            or not isinstance(required, list)
            or METRIC_KERNEL_DIGEST not in required
            or WALK_FORWARD_HARNESS_DIGEST not in required
            or not isinstance(statistic, Mapping)
            or statistic.get("name") != "PE1_mean_bits_per_issue"
            or statistic.get("unit") != "bits_per_issue"
            or statistic.get("metric_kernel_digest") != METRIC_KERNEL_DIGEST
            or not control.get("destroyed_relationship")
            or not control.get("preserved_properties")
            or not control.get("randomization_unit")
            or not control.get("execution_mode")
            or not control.get("seed_domain")
            or not control.get("multiplicity_family")
        ):
            raise ResamplingContractError(
                "negative-control execution contract changed"
            )
    inference = payload.get("inference_contract")
    if (
        not isinstance(inference, Mapping)
        or inference.get("primary_tail") != "upper"
        or inference.get("plus_one_correction") is not True
        or inference.get("upper_comparison") != ">="
        or inference.get("lower_comparison") != "<="
        or inference.get("percentile_method") != "midrank"
        or inference.get("quantile_method") != "Hyndman-Fan_type_7"
        or inference.get("smoke_formal_p_value") != "forbidden"
    ):
        raise ResamplingContractError("inference semantics changed")
    seed_policy = payload.get("seed_policy")
    if (
        not isinstance(seed_policy, Mapping)
        or seed_policy.get("wall_clock_seed") != "forbidden"
        or seed_policy.get("selection_policy") != "no_best_seed"
        or seed_policy.get("retry_reuses_child_seed") is not True
        or seed_policy.get("resume_reuses_child_seed") is not True
        or seed_policy.get("shard_change_preserves_child_seed") is not True
    ):
        raise ResamplingContractError("seed policy changed")
    performance = payload.get("performance_contract")
    if (
        not isinstance(performance, Mapping)
        or performance.get("plan_storage") != "index_based_view"
        or performance.get("formal_mapping_storage")
        != "source_index_and_parent_digest"
        or performance.get("mmap_supported") is not True
        or performance.get("maximum_resident_memory_mib_per_worker") != 512
    ):
        raise ResamplingContractError("performance contract changed")
    smoke = payload.get("smoke")
    if (
        not isinstance(smoke, Mapping)
        or tuple(smoke.get("flags", ())) != SMOKE_FLAGS
        or smoke.get("plan_only") is not True
        or smoke.get("eligible_for_formal_inference") is not False
    ):
        raise ResamplingContractError("smoke boundary changed")
    truths = tuple(str(value) for value in payload.get("truth_artifact_digests", ()))
    if len(truths) != 12 or any(len(value) != 64 for value in truths):
        raise ResamplingContractError("all twelve P2.4 truth identities are required")
    supplied = str(payload.get("artifact_digest", ""))
    calculated = config_digest(payload)
    if supplied != calculated or calculated != KERNEL_MANIFEST_DIGEST:
        raise ResamplingContractError("resampling kernel manifest digest changed")
    return ResamplingKernelManifest(
        payload=dict(payload),
        artifact_digest=calculated,
        root_seed_set_digest=str(seed_policy["root_seed_set_digest"]),
        primary_block_size=5,
        sensitivity_block_sizes=(3, 5, 8, 13),
        stationary_lengths=(3, 5, 8, 13),
        frozen_shifts=(1, 2, 3, 5, 8, 13, 21),
        controls=tuple(dict(item) for item in controls),
        smoke_flags=SMOKE_FLAGS,
        truth_artifact_digests=truths,
        injected_signal_completion_digest=P24_COMPLETION_DIGEST,
        injected_signal_execution_id=P24_EXECUTION_ID,
    )
