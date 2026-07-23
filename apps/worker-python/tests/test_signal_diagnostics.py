from __future__ import annotations

from dataclasses import asdict

import numpy as np
import pytest

from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.signal_diagnostics import (
    COOCCURRENCE_ADJACENCY_FIELDS,
    DYNAMIC_FIELDS,
    MINIMAL_LINEAR_WEIGHTS,
    OMISSION_INTERVAL_FIELDS,
    RECENT_FREQUENCY_FIELDS,
    STATIC_STRUCTURE_FIELDS,
    _random_control_rows,
    bind_signal_diagnostic_context,
    circular_block_bootstrap,
    deterministic_random_scores,
    diagnostic_config_manifest,
    permute_dynamic_contribution,
    permute_history_issue_outcomes,
    permute_history_number_labels,
    ranking_similarity,
    validate_diagnostic_manifest,
)
from dehps.optimization.walk_forward import CONFIG_WEIGHT_FIELDS


def _all_weight_config(value: float = 0.37) -> FrequencyRankerConfig:
    return FrequencyRankerConfig(
        **{field: value for field in CONFIG_WEIGHT_FIELDS}
    )


def test_manifest_has_required_arms_and_changes_only_declared_fields() -> None:
    base = _all_weight_config()
    rows = diagnostic_config_manifest(base)
    validate_diagnostic_manifest(rows)
    configs = {label: config for label, config, _metadata in rows}

    assert set(configs) == {
        "full_model",
        "static_structure_only",
        "recent_frequency_only",
        "omission_interval_only",
        "without_cooccurrence_adjacency",
        "without_all_dynamic",
        "fixed_minimal_linear",
    }
    for label, keep in (
        ("static_structure_only", STATIC_STRUCTURE_FIELDS),
        ("recent_frequency_only", RECENT_FREQUENCY_FIELDS),
        ("omission_interval_only", OMISSION_INTERVAL_FIELDS),
    ):
        values = asdict(configs[label])
        for field in CONFIG_WEIGHT_FIELDS:
            assert values[field] == (0.37 if field in keep else 0.0)

    without_adjacency = asdict(configs["without_cooccurrence_adjacency"])
    for field in CONFIG_WEIGHT_FIELDS:
        assert without_adjacency[field] == (
            0.0 if field in COOCCURRENCE_ADJACENCY_FIELDS else 0.37
        )

    without_dynamic = asdict(configs["without_all_dynamic"])
    for field in CONFIG_WEIGHT_FIELDS:
        assert without_dynamic[field] == (
            0.0 if field in DYNAMIC_FIELDS else 0.37
        )

    minimal = asdict(configs["fixed_minimal_linear"])
    for field in CONFIG_WEIGHT_FIELDS:
        assert minimal[field] == MINIMAL_LINEAR_WEIGHTS.get(field, 0.0)


def test_candidate_level_dynamic_permutation_is_deterministic_and_preserves_marginal() -> None:
    full = np.array([2.0, 3.0, 5.0, 7.0], dtype=np.float64)
    static = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float64)

    first, first_digest = permute_dynamic_contribution(
        full_scores=full,
        static_scores=static,
        seed_digest="ab" * 32,
        target_issue="2026083",
    )
    second, second_digest = permute_dynamic_contribution(
        full_scores=full,
        static_scores=static,
        seed_digest="ab" * 32,
        target_issue="2026083",
    )

    assert first_digest == second_digest
    assert np.array_equal(first, second)
    assert sorted(first - static) == sorted(full - static)
    assert first.flags.writeable is False


def test_issue_permutation_preserves_slots_and_outcome_multiset() -> None:
    history = [
        ("2026001", None, (1, 2, 3, 4, 5, 6)),
        ("2026002", None, (7, 8, 9, 10, 11, 12)),
        ("2026003", None, (13, 14, 15, 16, 17, 18)),
    ]
    first, first_metadata = permute_history_issue_outcomes(
        history=history,
        seed_digest="ab" * 32,
        target_issue="2026004",
    )
    second, second_metadata = permute_history_issue_outcomes(
        history=history,
        seed_digest="ab" * 32,
        target_issue="2026004",
    )

    assert first == second
    assert first_metadata == second_metadata
    assert [draw[0] for draw in first] == [draw[0] for draw in history]
    assert sorted(draw[2] for draw in first) == sorted(draw[2] for draw in history)
    assert [draw[2] for draw in first] != [draw[2] for draw in history]
    assert first_metadata["source_history_fingerprint"] != first_metadata[
        "transformed_history_fingerprint"
    ]


def test_number_label_permutation_is_one_bijection_over_prior_history() -> None:
    history = [
        ("2026001", None, (1, 2, 3, 4, 5, 6)),
        ("2026002", None, (1, 7, 8, 9, 10, 11)),
    ]
    transformed, metadata = permute_history_number_labels(
        history=history,
        seed_digest="cd" * 32,
        target_issue="2026003",
    )
    mapping = {int(key): value for key, value in metadata["label_mapping"].items()}

    assert set(mapping) == set(range(1, 34))
    assert set(mapping.values()) == set(range(1, 34))
    assert [draw[0] for draw in transformed] == [draw[0] for draw in history]
    assert all(tuple(sorted(draw[2])) == draw[2] for draw in transformed)
    assert all(len(set(draw[2])) == 6 for draw in transformed)
    assert mapping[1] in transformed[0][2] and mapping[1] in transformed[1][2]


def test_random_score_control_is_deterministic_unique_and_read_only() -> None:
    first, first_metadata = deterministic_random_scores(
        candidate_count=100,
        seed_digest="ef" * 32,
        target_issue="2026083",
    )
    second, second_metadata = deterministic_random_scores(
        candidate_count=100,
        seed_digest="ef" * 32,
        target_issue="2026083",
    )

    assert np.array_equal(first, second)
    assert first_metadata == second_metadata
    assert len(np.unique(first)) == 100
    assert first.flags.writeable is False


def test_ranking_similarity_is_exact_for_identical_and_reversed_rankings() -> None:
    reference = np.array([0, 1, 2, 3, 4], dtype=np.int32)
    identical = ranking_similarity(
        reference_positions=reference,
        candidate_positions=reference.copy(),
        seed_digest="cd" * 32,
        target_issue="2026083",
        comparison_label="same",
    )
    reversed_result = ranking_similarity(
        reference_positions=reference,
        candidate_positions=reference[::-1].copy(),
        seed_digest="cd" * 32,
        target_issue="2026083",
        comparison_label="reverse",
    )

    assert identical["spearman_full_universe"] == 1.0
    assert identical["kendall_tau_pair_sample"] == 1.0
    assert reversed_result["spearman_full_universe"] == -1.0
    assert reversed_result["kendall_tau_pair_sample"] == pytest.approx(-1.0)


def test_circular_block_bootstrap_is_deterministic_and_paired() -> None:
    first = circular_block_bootstrap(
        [1.0, -1.0, 1.0, -1.0],
        seed_digest="ef" * 32,
        label="paired",
        block_length=2,
        resamples=100,
    )
    second = circular_block_bootstrap(
        [1.0, -1.0, 1.0, -1.0],
        seed_digest="ef" * 32,
        label="paired",
        block_length=2,
        resamples=100,
    )

    assert first == second
    assert first["mean"] == 0.0
    assert first["method"] == "circular_block_bootstrap"
    assert len(first["series_identity_digest"]) == 64


def test_circular_block_bootstrap_identity_excludes_display_label() -> None:
    first = circular_block_bootstrap(
        [0.5, -0.25, 1.0, -0.75, 0.0],
        seed_digest="ab" * 32,
        label="full_model:top70_minus_matched",
        block_length=2,
        resamples=100,
    )
    equivalent = circular_block_bootstrap(
        [0.5, -0.25, 1.0, -0.75, 0.0],
        seed_digest="ab" * 32,
        label="fixed_minimal_linear:top70_minus_matched",
        block_length=2,
        resamples=100,
    )

    assert first == equivalent


def test_manifest_validation_rejects_missing_arm() -> None:
    rows = diagnostic_config_manifest(FrequencyRankerConfig())
    with pytest.raises(Exception, match="manifest is incomplete"):
        validate_diagnostic_manifest(rows[:-1])


def test_execution_context_is_covered_by_snapshot_digest() -> None:
    payload = {
        "protocol": {"status": "diagnostic_only"},
        "snapshot_digest": "old",
    }
    first = bind_signal_diagnostic_context(
        payload,
        base_config_metadata={"source": "one"},
        history_scope={"scope": "frozen"},
    )
    second = bind_signal_diagnostic_context(
        payload,
        base_config_metadata={"source": "two"},
        history_scope={"scope": "frozen"},
    )

    assert first["snapshot_digest"] != second["snapshot_digest"]
    assert first["execution_context"]["base_config_metadata"]["source"] == "one"


def test_random_controls_bind_pool_identity_not_display_label() -> None:
    numbers = np.array(
        [
            tuple(range(start, start + 6))
            for start in range(1, 72)
        ],
        dtype=np.uint8,
    )
    scores = np.arange(len(numbers), dtype=np.float64)
    order = np.arange(len(numbers) - 1, -1, -1, dtype=np.int64)
    kwargs = {
        "scores": scores,
        "order": order,
        "numbers": numbers,
        "actual": tuple(range(1, 7)),
        "target_issue": "2026083",
        "seed_digests": ("ab" * 32,),
        "pool_size": len(numbers),
    }

    first = _random_control_rows(**kwargs)
    second = _random_control_rows(**kwargs)

    assert first == second
    assert first[0]["source_pool_sequence_digest"]
    assert first[1]["source_pool_sequence_digest"] is None
