from __future__ import annotations

import numpy as np

from scripts.probe_opencl_score_backend import (
    acceptance_summary,
    probe_configs,
    top_set_match_count,
)


def test_probe_configs_are_deterministic_and_varied():
    first = probe_configs(count=4, seed=20260711)
    second = probe_configs(count=4, seed=20260711)

    assert first == second
    assert len(set(first)) > 1


def test_top_set_match_count_compares_each_config():
    cpu = np.array(
        [
            [4.0, 1.0],
            [3.0, 4.0],
            [2.0, 3.0],
            [1.0, 2.0],
        ]
    )
    gpu = cpu.copy()
    gpu[:, 1] = [4.0, 3.0, 2.0, 1.0]

    assert top_set_match_count(cpu, gpu, top_n=2) == 1


def test_acceptance_requires_exact_scores_rank_sets_ranks_and_speed():
    accepted = acceptance_summary(
        rounded_score_matrix_exact=True,
        top_set_match_count=28,
        config_count=28,
        target_ranks_equal=True,
        full_end_to_end_speedup=1.2,
        min_speedup=1.05,
    )
    rejected = acceptance_summary(
        rounded_score_matrix_exact=False,
        top_set_match_count=27,
        config_count=28,
        target_ranks_equal=False,
        full_end_to_end_speedup=0.9,
        min_speedup=1.05,
    )

    assert accepted["status"] == "accepted"
    assert accepted["accepted_for_training"] is True
    assert accepted["blockers"] == []
    assert rejected["status"] == "rejected"
    assert rejected["accepted_for_training"] is False
    assert rejected["blockers"] == [
        "rounded_score_matrix_not_exact",
        "top_candidate_sets_changed",
        "target_ranks_changed",
        "insufficient_full_end_to_end_speedup",
    ]
    assert rejected["selection_changed"] is False
    assert rejected["promotion_allowed"] is False
