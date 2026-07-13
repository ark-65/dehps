from __future__ import annotations

from dataclasses import asdict

import pytest

from dehps.evaluation.objective import TrainingMetrics, evaluate_objective
from dehps.evaluation.objective_policy import DEFAULT_OBJECTIVE_POLICY, ObjectivePolicy


def test_rank_objective_v1_has_stable_canonical_hash_independent_of_mapping_order() -> None:
    values = asdict(DEFAULT_OBJECTIVE_POLICY)
    reconstructed = ObjectivePolicy(**dict(reversed(tuple(values.items()))))

    assert DEFAULT_OBJECTIVE_POLICY.version == "rank_objective_v1"
    assert reconstructed.canonical_json() == DEFAULT_OBJECTIVE_POLICY.canonical_json()
    assert reconstructed.policy_hash == DEFAULT_OBJECTIVE_POLICY.policy_hash
    assert DEFAULT_OBJECTIVE_POLICY.policy_hash == "c63399d633aa1ae0148df96698df77233458ccbb265db50ed959907bce726387"


def test_evaluate_objective_is_pure_and_preserves_legacy_arithmetic() -> None:
    metrics = TrainingMetrics(
        top_100_hits=1,
        top_1000_hits=2,
        top_10000_hits=3,
        median_rank=402_500.0,
        worst_rank=1_050_000,
        p95_rank=1_050_000,
        tail_over_750000_count=3,
        tail_over_900000_count=2,
        tail_over_1000000_count=1,
        baseline_unique_reward=314.0,
        baseline_overlap_penalty=103.0,
        red5_top_100_hits=1,
        red5_top_1000_hits=2,
        red5_top_10000_hits=3,
        rank_quality_reward=5.944591,
        universe_size=1_107_568,
        tail_risk_penalty=19.141591,
    )

    first = evaluate_objective(metrics, DEFAULT_OBJECTIVE_POLICY)
    second = evaluate_objective(metrics, DEFAULT_OBJECTIVE_POLICY)

    assert first == second
    assert first.objective == pytest.approx(1773.802585, abs=1e-6)
    assert first.policy_version == "rank_objective_v1"
    assert first.policy_hash == DEFAULT_OBJECTIVE_POLICY.policy_hash
