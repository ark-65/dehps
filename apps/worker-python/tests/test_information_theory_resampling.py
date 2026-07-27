from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pytest

from dehps.research_os.information_theory.resampling import (
    KERNEL_MANIFEST_DIGEST,
    ResamplingContractError,
    ResamplingError,
    apply_issue_plan,
    apply_number_mapping,
    block_permutation_plan,
    circular_shift_plan,
    issue_label_permutation_plan,
    load_resampling_manifest,
    matched_random_features,
    matched_random_score,
    moving_block_plan,
    negative_control_registry,
    number_label_permutation,
    percentile_summary,
    plus_one_p_value,
    shard_for_replicate,
    stationary_plan,
    type7_quantiles,
    validate_resampling_manifest,
)
from dehps.research_os.information_theory.resampling.runner import (
    _aggregate_artifact,
)
from dehps.research_os.information_theory.walk_forward import (
    FEATURE_MANIFEST_DIGEST,
)


ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = (
    ROOT
    / "configs/research-os/"
    "m4-information-theory-p2-5-resampling-kernel-v1.json"
)
PARENT_DIGEST = "a" * 64


@pytest.fixture(scope="module")
def manifest():
    return load_resampling_manifest(MANIFEST_PATH)


def _issues(count: int = 17) -> tuple[dict, ...]:
    rows = []
    for index in range(count):
        numbers = [((index + offset) % 33) + 1 for offset in range(6)]
        target = [0] * 33
        for number in numbers:
            target[number - 1] = 1
        rows.append(
            {
                "issue_id": str(index),
                "issue_index": index,
                "cluster_id": str(index),
                "sorted_red_numbers": sorted(numbers),
                "target_vector": target,
                "prediction_checkpoint_identity": f"prediction-{index}",
                "settlement_identity": f"settlement-{index}",
            }
        )
    return tuple(rows)


def test_frozen_manifest_binds_methods_controls_seeds_and_inference(manifest) -> None:
    assert manifest.artifact_digest == KERNEL_MANIFEST_DIGEST
    assert manifest.primary_block_size == 5
    assert manifest.sensitivity_block_sizes == (3, 5, 8, 13)
    assert manifest.stationary_lengths == (3, 5, 8, 13)
    assert manifest.frozen_shifts == (1, 2, 3, 5, 8, 13, 21)
    assert len(manifest.truth_artifact_digests) == 12
    assert tuple(negative_control_registry(manifest)) == (
        "NC1_ISSUE_LABEL_PERMUTATION",
        "NC2_NUMBER_LABEL_PERMUTATION",
        "NC3_CIRCULAR_TARGET_SHIFT",
        "NC4_MATCHED_RANDOM_FEATURES",
        "NC5_MATCHED_RANDOM_SCORE",
        "NC6_SYNTHETIC_NULL",
    )

    changed = copy.deepcopy(dict(manifest.payload))
    changed["methods"]["moving_block_bootstrap"]["primary_block_size"] = 4
    with pytest.raises(ResamplingContractError, match="semantics changed"):
        validate_resampling_manifest(changed)


def test_moving_block_is_issue_level_non_circular_replayable(manifest) -> None:
    first = moving_block_plan(
        17,
        block_size=5,
        manifest=manifest,
        scenario_id="NULL_UNIFORM",
        replicate_index=0,
        parent_run_digest=PARENT_DIGEST,
    )
    replay = moving_block_plan(
        17,
        block_size=5,
        manifest=manifest,
        scenario_id="NULL_UNIFORM",
        replicate_index=0,
        parent_run_digest=PARENT_DIGEST,
    )
    changed = moving_block_plan(
        17,
        block_size=5,
        manifest=manifest,
        scenario_id="NULL_UNIFORM",
        replicate_index=1,
        parent_run_digest=PARENT_DIGEST,
    )
    applied = apply_issue_plan(_issues(), first)

    assert first == replay
    assert first.plan_digest != changed.plan_digest
    assert len(first.source_indices) == len(applied) == 17
    assert first.config["topology"] == "non_circular"
    assert first.config["overflow_policy"] == "truncate_right"
    assert all(
        right == left + 1
        for start in first.config["block_start_positions"]
        for left, right in zip(
            range(start, min(start + 4, 16)),
            range(start + 1, min(start + 5, 17)),
            strict=True,
        )
    )
    assert all(len(item["target_vector"]) == 33 for item in applied)
    assert all(sum(item["target_vector"]) == 6 for item in applied)


def test_moving_block_size_one_and_short_sequence_fail_closed(manifest) -> None:
    plan = moving_block_plan(
        9,
        block_size=1,
        manifest=manifest,
        scenario_id="NULL_UNIFORM",
        replicate_index=0,
        parent_run_digest=PARENT_DIGEST,
    )
    assert len(plan.source_indices) == 9
    assert all(0 <= index < 9 for index in plan.source_indices)
    with pytest.raises(ResamplingError, match="insufficient_issues_for_block_size"):
        moving_block_plan(
            4,
            block_size=5,
            manifest=manifest,
            scenario_id="NULL_UNIFORM",
            replicate_index=0,
            parent_run_digest=PARENT_DIGEST,
        )


def test_stationary_bootstrap_is_circular_sensitivity_and_replayable(manifest) -> None:
    plan = stationary_plan(
        31,
        expected_block_length=5,
        manifest=manifest,
        scenario_id="NULL_UNIFORM",
        replicate_index=2,
        parent_run_digest=PARENT_DIGEST,
    )
    replay = stationary_plan(
        31,
        expected_block_length=5,
        manifest=manifest,
        scenario_id="NULL_UNIFORM",
        replicate_index=2,
        parent_run_digest=PARENT_DIGEST,
    )
    assert plan == replay
    assert plan.config["restart_probability"] == 0.2
    assert plan.config["topology"] == "circular"
    assert plan.config["role"] == "sensitivity_only"
    assert len(apply_issue_plan(_issues(31), plan)) == 31


def test_block_permutation_preserves_internal_order_and_distinct_tail(manifest) -> None:
    plan = block_permutation_plan(
        17,
        block_size=5,
        manifest=manifest,
        scenario_id="NULL_UNIFORM",
        replicate_index=0,
        parent_run_digest=PARENT_DIGEST,
    )
    assert plan.config["block_order"] != [0, 1, 2, 3]
    assert plan.config["tail_block_length"] == 2
    source_blocks = [
        list(range(0, 5)),
        list(range(5, 10)),
        list(range(10, 15)),
        list(range(15, 17)),
    ]
    assert list(plan.source_indices) == [
        item
        for block_index in plan.config["block_order"]
        for item in source_blocks[block_index]
    ]
    with pytest.raises(ResamplingError, match="insufficient_blocks_for_permutation"):
        block_permutation_plan(
            5,
            block_size=5,
            manifest=manifest,
            scenario_id="NULL_UNIFORM",
            replicate_index=0,
            parent_run_digest=PARENT_DIGEST,
        )


def test_issue_label_permutation_is_non_identity_bijection(manifest) -> None:
    plan = issue_label_permutation_plan(
        17,
        manifest=manifest,
        scenario_id="NULL_UNIFORM",
        replicate_index=0,
        parent_run_digest=PARENT_DIGEST,
    )
    assert sorted(plan.source_indices) == list(range(17))
    assert list(plan.source_indices) != list(range(17))
    applied = apply_issue_plan(_issues(), plan)
    assert [item["source_issue_id"] for item in applied] != [
        str(index) for index in range(17)
    ]
    assert all(sum(item["target_vector"]) == 6 for item in applied)


def test_number_label_mapping_is_global_bijection_and_maps_whole_issue(manifest) -> None:
    mapping, seed, seed_digest, mapping_digest = number_label_permutation(
        manifest=manifest,
        scenario_id="NULL_UNIFORM",
        replicate_index=0,
        parent_run_digest=PARENT_DIGEST,
    )
    assert set(mapping) == set(mapping.values()) == set(range(1, 34))
    assert any(left != right for left, right in mapping.items())
    assert seed > 0 and len(seed_digest) == len(mapping_digest) == 64
    mapped = [apply_number_mapping(issue, mapping) for issue in _issues()]
    assert all(len(set(item["sorted_red_numbers"])) == 6 for item in mapped)
    assert all(sum(item["target_vector"]) == 6 for item in mapped)
    with pytest.raises(ResamplingError, match="invalid_permutation_mapping"):
        apply_number_mapping(_issues()[0], {1: 1})


@pytest.mark.parametrize("shift", [1, 2, 3, 5, 8, 13, 21])
def test_circular_shift_frozen_direction_wrap_and_count(shift: int) -> None:
    plan = circular_shift_plan(31, shift=shift)
    assert plan.source_indices[0] == shift
    assert plan.source_indices[-1] == (30 + shift) % 31
    assert len(plan.source_indices) == 31
    assert plan.config["direction"] == "target_forward_relative_to_prediction"


def test_circular_shift_zero_is_forbidden() -> None:
    with pytest.raises(ResamplingError, match="invalid_circular_shift"):
        circular_shift_plan(31, shift=0)


@pytest.mark.parametrize(
    "strategy",
    [
        "independent_matched_noise",
        "block_correlated_matched_noise",
        "permutation_derived_matched_noise",
    ],
)
def test_random_features_match_shape_marginals_and_record_contract(
    manifest,
    strategy: str,
) -> None:
    features = np.arange(102, dtype=np.float64).reshape(34, 3)
    result, metadata = matched_random_features(
        features,
        missing_mask=None,
        strategy=strategy,
        source_feature_manifest_digest=FEATURE_MANIFEST_DIGEST,
        source_provenance="pre_target_feature_view",
        manifest=manifest,
        scenario_id="NULL_UNIFORM",
        replicate_index=0,
        parent_run_digest=PARENT_DIGEST,
    )
    assert result.shape == features.shape
    assert result.dtype == features.dtype
    assert metadata["target_access"] == "forbidden_by_function_signature"
    assert metadata["source_feature_manifest_digest"] == FEATURE_MANIFEST_DIGEST
    for column in range(features.shape[1]):
        assert sorted(result[:, column]) == sorted(features[:, column])


def test_random_feature_missingness_and_random_score_replay(manifest) -> None:
    features = np.arange(40, dtype=float).reshape(20, 2)
    mask = np.zeros_like(features, dtype=bool)
    mask[2, 1] = True
    first, metadata = matched_random_features(
        features,
        missing_mask=mask,
        strategy="independent_matched_noise",
        source_feature_manifest_digest=FEATURE_MANIFEST_DIGEST,
        source_provenance="pre_target_feature_view",
        manifest=manifest,
        scenario_id="NULL_UNIFORM",
        replicate_index=3,
        parent_run_digest=PARENT_DIGEST,
    )
    replay, replay_metadata = matched_random_features(
        features,
        missing_mask=mask,
        strategy="independent_matched_noise",
        source_feature_manifest_digest=FEATURE_MANIFEST_DIGEST,
        source_provenance="pre_target_feature_view",
        manifest=manifest,
        scenario_id="NULL_UNIFORM",
        replicate_index=3,
        parent_run_digest=PARENT_DIGEST,
    )
    assert np.array_equal(first, replay, equal_nan=True)
    assert metadata == replay_metadata
    assert np.isnan(first[2, 1])
    for column in range(features.shape[1]):
        observed = ~mask[:, column]
        assert sorted(first[observed, column]) == sorted(
            features[observed, column]
        )

    scores, score_metadata = matched_random_score(
        tuple(range(20)),
        strategy="rank_distribution",
        source_provenance="synthetic_probe_score",
        manifest=manifest,
        scenario_id="NULL_UNIFORM",
        replicate_index=0,
        parent_run_digest=PARENT_DIGEST,
    )
    assert sorted(scores) == list(map(float, range(20)))
    assert score_metadata["target_access"] == "forbidden_by_function_signature"
    assert "target" in score_metadata["forbidden_inputs"]
    with pytest.raises(ResamplingError, match="target_dependent_negative_control"):
        matched_random_features(
            features,
            missing_mask=None,
            strategy="independent_matched_noise",
            source_feature_manifest_digest=FEATURE_MANIFEST_DIGEST,
            source_provenance="post_settlement_target_features",
            manifest=manifest,
            scenario_id="NULL_UNIFORM",
            replicate_index=0,
            parent_run_digest=PARENT_DIGEST,
        )
    with pytest.raises(ResamplingError, match="target_dependent_random_score"):
        matched_random_score(
            tuple(range(20)),
            strategy="rank_distribution",
            source_provenance="hit_rank",
            manifest=manifest,
            scenario_id="NULL_UNIFORM",
            replicate_index=0,
            parent_run_digest=PARENT_DIGEST,
        )


def test_seed_domains_and_deterministic_sharding(manifest) -> None:
    domains = manifest.payload["seed_policy"]["domains"]
    forbidden = manifest.payload["seed_policy"]["forbidden_domains"]
    assert len(domains) == len(set(domains))
    assert set(domains).isdisjoint(forbidden)
    assert [shard_for_replicate(index, 3) for index in range(8)] == [
        0,
        1,
        2,
        0,
        1,
        2,
        0,
        1,
    ]
    with pytest.raises(ResamplingError, match="invalid_shard_contract"):
        shard_for_replicate(0, 0)


def test_plus_one_tails_ties_percentile_quantiles_and_fail_closed() -> None:
    values = [0.0, 1.0, 1.0, 2.0]
    assert plus_one_p_value(1.0, values, tail="upper") == 4 / 5
    assert plus_one_p_value(1.0, values, tail="lower") == 4 / 5
    assert plus_one_p_value(1.0, values, tail="two_sided") == 1.0
    summary = percentile_summary(1.0, values)
    assert summary["rank_mid"] == 2.0
    assert summary["percentile_midrank"] == 0.5
    assert summary["empirical_cdf_inclusive"] == 0.75
    assert type7_quantiles([0, 1, 2, 3, 4])["q50"] == 2.0
    with pytest.raises(ResamplingError, match="empty_null_distribution"):
        plus_one_p_value(1.0, [])
    with pytest.raises(ResamplingError, match="nan_statistic"):
        plus_one_p_value(float("nan"), values)


def test_aggregate_rejects_unit_and_multiplicity_contract_violations(
    manifest,
) -> None:
    child = {
        "artifact_digest": "b" * 64,
        "method": "moving_block_bootstrap",
        "control_id": None,
        "unit": "bits_per_issue",
        "multiplicity_family": "SENSITIVITY_FAMILY",
        "seed_digest": "c" * 64,
    }
    aggregate = _aggregate_artifact(
        group_id="moving_block_bootstrap",
        children=[child],
        manifest=manifest,
        git_commit="d" * 40,
        working_tree_clean=True,
    )
    assert aggregate["replicate_count_completed"] == 1
    assert aggregate["eligible_for_formal_inference"] is False

    wrong_unit = {**child, "unit": "bits_per_number_event"}
    with pytest.raises(ResamplingError, match="unit_mismatch"):
        _aggregate_artifact(
            group_id="moving_block_bootstrap",
            children=[wrong_unit],
            manifest=manifest,
            git_commit="d" * 40,
            working_tree_clean=True,
        )
    missing_family = {**child, "multiplicity_family": ""}
    with pytest.raises(ResamplingError, match="missing_multiplicity_family"):
        _aggregate_artifact(
            group_id="moving_block_bootstrap",
            children=[missing_family],
            manifest=manifest,
            git_commit="d" * 40,
            working_tree_clean=True,
        )
    with pytest.raises(ResamplingError, match="incomplete_seed_set"):
        _aggregate_artifact(
            group_id="moving_block_bootstrap",
            children=[child],
            manifest=manifest,
            git_commit="d" * 40,
            working_tree_clean=True,
            expected_replicate_count=2,
        )
