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
    bind_signal_diagnostic_context,
    circular_block_bootstrap,
    diagnostic_config_manifest,
    permute_dynamic_contribution,
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
