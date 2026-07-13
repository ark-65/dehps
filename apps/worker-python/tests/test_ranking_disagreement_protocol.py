from experiment_plan_fixtures import ranking_plan


def test_ranking_disagreement_protocol_has_required_strata_baselines_and_metrics() -> None:
    plan = ranking_plan()

    assert tuple(plan.feature_contract["strata"]["keys"]) == (
        "low_disagreement",
        "medium_disagreement",
        "high_disagreement",
        "extreme_disagreement",
    )
    assert set(plan.baseline_contract["matched_baselines"]) == {
        "budget_matched_random",
        "rank_matched_consensus",
        "current_production_ranker",
    }
    assert set(plan.metric_contract["required"]) >= {
        "exact_target_rank",
        "top_100_hits",
        "top_1000_hits",
        "top_10000_hits",
        "median_rank",
        "mean_rank",
        "p95_rank",
        "worst_rank",
        "mean_reciprocal_rank",
        "tail_over_750000",
        "tail_over_900000",
        "tail_over_1000000",
        "baseline_lift",
        "stratum_stability",
        "direction_consistency",
    }


def test_time_protocol_freezes_search_frozen_and_forward_boundaries() -> None:
    protocol = ranking_plan().validation_protocol

    assert protocol["search_issue_count"] == 100
    assert protocol["frozen_issue_count"] == 20
    assert protocol["forward_min_paired_issues"] == 20
    assert protocol["train_mode"] == "expanding"
    assert protocol["random_split"] is False
    assert protocol["search_frozen_overlap"] == 0
    assert protocol["frozen_validation_required_before_forward"] is True
    assert protocol["legal_universe_fingerprint"]
    assert protocol["objective_policy_hash"]
