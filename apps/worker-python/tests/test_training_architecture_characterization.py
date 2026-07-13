from __future__ import annotations

import pytest

from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.walk_forward import TargetRank
import scripts.run_training_supervisor as legacy


UNIVERSE_SIZE = 1_107_568
HISTORY_FINGERPRINT = "fixture-history-fingerprint"
AS_OF_ISSUE = "2026067"


def _target(issue: str, rank: int, red5_rank: int) -> TargetRank:
    return TargetRank(
        issue=issue,
        rank=rank,
        score=float(-rank),
        hit_top_100=rank <= 100,
        hit_top_1000=rank <= 1_000,
        hit_top_10000=rank <= 10_000,
        red5_rank=red5_rank,
        red5_score=float(-red5_rank),
        red5_numbers=(1, 2, 3, 4, 5, 6),
        red5_missing_number=7,
        red5_extra_number=6,
        hit_red5_top_100=red5_rank <= 100,
        hit_red5_top_1000=red5_rank <= 1_000,
        hit_red5_top_10000=red5_rank <= 10_000,
    )


def _objective_fixture() -> dict:
    targets = [
        _target("issue-1", 50, 80),
        _target("issue-2", 500, 800),
        _target("issue-3", 5_000, 8_000),
        _target("issue-4", 800_000, 700_000),
        _target("issue-5", 950_000, 920_000),
        _target("issue-6", 1_050_000, 1_000_001),
    ]
    summary = legacy.summarize_target_ranks(
        target_ranks=targets,
        config=FrequencyRankerConfig(
            structural_weight=0.55,
            frequency_weight=0.30,
            omission_weight=0.15,
            previous_consecutive_weight=0.0,
        ),
        as_of_issue=AS_OF_ISSUE,
        history_fingerprint_value=HISTORY_FINGERPRINT,
        train_window=900,
        train_mode="expanding",
        top_n=10_000,
        universe_size=UNIVERSE_SIZE,
    )
    summary["baseline_overlap"] = {
        "unique_reward": 314.0,
        "overlap_penalty": 103.0,
        "bands": {},
    }
    summary["reward"] = legacy.reward_summary(summary, universe_size=UNIVERSE_SIZE)
    return summary


def _frozen_summary(
    objective: float,
    *,
    top_10000_hits: int = 0,
    worst_rank: int = 800_000,
    tail_risk: float = 1.0,
) -> dict:
    return {
        "config_hash": f"fixture-{objective}-{top_10000_hits}-{worst_rank}",
        "frozen_validation": {
            "top_100_hits": 0,
            "top_1000_hits": 0,
            "top_10000_hits": top_10000_hits,
            "worst_rank": worst_rank,
            "rank_quality": {
                "p95_rank": worst_rank,
                "tail_over_750000_count": int(worst_rank > 750_000),
                "tail_over_900000_count": int(worst_rank > 900_000),
                "tail_over_1000000_count": int(worst_rank > 1_000_000),
                "tail_risk_penalty": tail_risk,
            },
            "reward": {"objectiveScore": objective},
        },
    }


def test_characterizes_complete_rank_objective_v1_arithmetic() -> None:
    summary = _objective_fixture()

    assert summary["top_100_hits"] == 1
    assert summary["top_1000_hits"] == 2
    assert summary["top_10000_hits"] == 3
    assert summary["median_rank"] == 402_500.0
    assert summary["worst_rank"] == 1_050_000
    assert summary["rank_quality"]["p95_rank"] == 1_050_000
    assert summary["rank_quality"]["tail_risk_penalty"] == pytest.approx(19.141591, abs=1e-6)
    assert summary["red5"]["top_100_hits"] == 1
    assert summary["red5"]["top_1000_hits"] == 2
    assert summary["red5"]["top_10000_hits"] == 3
    assert summary["reward"] == pytest.approx(
        {
            "hitReward": 1569.0,
            "baselineUniqueReward": 314.0,
            "baselineOverlapPenalty": 103.0,
            "red5Reward": 7.6,
            "rankQualityReward": 5.944591,
            "rankPenalty": 0.600415,
            "tailRiskPenalty": 19.141591,
            "objectiveScore": 1773.802585,
        },
        abs=1e-6,
    )


@pytest.mark.parametrize(
    ("total", "expected"),
    [
        (1, {"exploitation": 0, "exploration": 0, "replay": 0, "baseline": 0, "weight_kdj": 1, "recency_canary": 0}),
        (2, {"exploitation": 0, "exploration": 0, "replay": 0, "baseline": 0, "weight_kdj": 1, "recency_canary": 1}),
        (3, {"exploitation": 1, "exploration": 0, "replay": 0, "baseline": 0, "weight_kdj": 1, "recency_canary": 1}),
        (7, {"exploitation": 1, "exploration": 1, "replay": 1, "baseline": 1, "weight_kdj": 2, "recency_canary": 1}),
        (20, {"exploitation": 5, "exploration": 4, "replay": 2, "baseline": 1, "weight_kdj": 5, "recency_canary": 3}),
    ],
)
def test_characterizes_candidate_budget_rounding_and_conservation(total: int, expected: dict[str, int]) -> None:
    actual = legacy.candidate_budget(
        total,
        recency_canary_budget_share=0.12,
        weight_kdj_budget_share=0.22,
    )

    assert actual == expected
    assert sum(actual.values()) == total
    assert all(0 <= count <= total for count in actual.values())


def test_characterizes_search_phase_schedule_and_stagnation_override() -> None:
    assert [legacy.phase_for_round(index) for index in range(4)] == [
        ("large", 0.20, "early_broad"),
        ("large", 0.15, "early_broad"),
        ("medium", 0.10, "early_broad"),
        ("large", 0.12, "early_broad"),
    ]
    assert [legacy.phase_for_round(index) for index in range(24, 27)] == [
        ("medium", 0.08, "mid_search"),
        ("medium", 0.06, "mid_search"),
        ("small", 0.04, "mid_search"),
    ]
    assert [legacy.phase_for_round(index) for index in range(72, 76)] == [
        ("small", 0.03, "late_refine"),
        ("micro", 0.015, "late_refine"),
        ("micro", 0.01, "late_refine"),
        ("small", 0.02, "late_refine"),
    ]
    assert legacy.phase_for_round(90, stagnation_rounds=16) == ("large", 0.15, "stagnation_broad")

    repeated = [{"prefilter": {"round_best_rank_signature_hash": "same"}} for _ in range(4)]
    homogeneity = legacy.rank_homogeneity_guardrail(repeated, stagnation_rounds=4)
    assert homogeneity["active"] is True
    assert homogeneity["trigger_mode"] == "exact_repeat"
    assert homogeneity["stagnation_threshold"] == 4


def test_characterizes_legacy_promotion_and_forward_quarantine() -> None:
    incumbent = _frozen_summary(10.0)
    clear_promotion = _frozen_summary(12.0, top_10000_hits=1, worst_rank=790_000)
    secondary_only = _frozen_summary(12.0, worst_rank=790_000)
    worse_tail = _frozen_summary(12.0, top_10000_hits=1, worst_rank=1_010_000, tail_risk=3.0)
    worse_objective = _frozen_summary(9.0, top_10000_hits=1, worst_rank=790_000)

    assert legacy.frozen_validation_promotion_gate(clear_promotion, incumbent)["passed"] is True
    assert legacy.frozen_validation_promotion_gate(secondary_only, incumbent)["passed"] is False
    assert legacy.frozen_validation_promotion_gate(worse_tail, incumbent)["passed"] is False
    assert legacy.frozen_validation_promotion_gate(worse_objective, incumbent)["passed"] is False
    missing = legacy.frozen_validation_promotion_gate(None, incumbent)
    assert (missing["passed"], missing["reason"]) == (False, "missing_candidate")
    assert missing["reason_codes"] == ["missing_candidate"]

    quarantined = legacy.quarantine_historical_frozen_promotion(
        legacy.frozen_validation_promotion_gate(clear_promotion, incumbent)
    )
    assert quarantined["passed"] is False
    assert quarantined["reason"] == "historical_frozen_holdout_quarantined"
    assert quarantined["promotion_holdout_status"] == "requires_forward_unseen_evidence"


def test_characterizes_reproducible_identity_candidate_order_and_objective() -> None:
    first = _objective_fixture()
    second = _objective_fixture()
    base = FrequencyRankerConfig(
        structural_weight=0.55,
        frequency_weight=0.30,
        omission_weight=0.15,
        previous_consecutive_weight=0.0,
    )
    candidates = legacy.stagnation_restart_candidate_configs(
        base,
        max_configs=5,
        round_index=31,
        stagnation_rounds=16,
    )

    assert legacy.deterministic_seed("stagnation_restart", 31, 16) == 28_143
    assert first["config_hash"] == second["config_hash"] == "65710d82d75d98bc8d233c78a974df5f36c4dd1c15e025ed72276baa12c48b77"
    assert first["run_key"] == second["run_key"] == "walk-forward-frequency_v1-asof-2026067-42197a57f8cc"
    assert first["reward"]["objectiveScore"] == pytest.approx(second["reward"]["objectiveScore"], abs=1e-6)
    assert [legacy.config_hash(config) for config in candidates] == [
        "f8b9b246e5f4cd84930839cf1943484a21ad22bb249c26a4883424954e98ee33",
        "9f00803c537b4aa81e0ed6d9f0d60614010e0f1a26f6c00d51ddb9e4c88d21a1",
        "75e26c7f7f4776f56fa31b04f286e627a55abca6332209f9229d7dc484cf8464",
        "9751475ed70c2b7f2543bd46325d29a3b34e1880f78c099165be9ffb47c5f016",
        "726bfc760648a8b069b55b1ff1f239e62e45e4d84c920b5ebebcbfa57db8bb77",
    ]
