from __future__ import annotations

from datetime import datetime, timedelta
import json

from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.neural_kdj_advisor import NeuralKdjOffsetAdvice
from dehps.optimization.neural_kdj_advisor import neural_kdj_advice_to_frequency_ranker_config_candidates
from dehps.optimization.ridge_kdj_advisor import RidgeKdjOffsetAdvice
from dehps.optimization.ridge_kdj_advisor import ridge_kdj_advice_to_frequency_ranker_config_candidates
from dehps.optimization.walk_forward import TargetRank, build_ranked_universe
import scripts.run_training_supervisor as supervisor
from scripts.run_training_supervisor import (
    active_supervisor_guard_rounds,
    active_supervisor_stagnation_round_count,
    best_challenger_summary,
    binomial_upper_tail_probability,
    bounded_unique_config_hashes,
    calculate_tail_risk_penalty,
    candidate_budget,
    candidate_source_survival,
    attach_baseline_overlap,
    attach_frozen_validation,
    compact_status_payload,
    config_hash,
    control_experiment_configs,
    control_experiment_summaries,
    carryover_candidate_configs_from_summaries,
    diagnostic_source_configs,
    evaluate_configs,
    frozen_validation_promotion_gate,
    frozen_validation_window,
    historical_candidate_source_hashes,
    generate_configs,
    load_prior_supervisor_carryover_configs,
    low_coverage_fields_from_summaries,
    load_prior_supervisor_candidates,
    merge_config_candidates,
    merge_reserved_candidate_configs,
    refill_candidate_configs,
    neural_kdj_advisor_metadata,
    near_miss_inversion_advisor,
    near_miss_targets_for_cutoff,
    phase_for_round,
    persisted_round_candidate_summaries,
    post_training_event,
    prefilter_configs,
    prefilter_holdout_isolation_audit,
    probability_calibration_diagnostics,
    probability_calibration_score,
    rank_signature_hash,
    reward_summary,
    resolve_training_deadline,
    rank_homogeneity_guardrail,
    recover_supervisor_continuity_configs,
    recover_supervisor_guard_history,
    search_base_min_distance_for_phase,
    ridge_kdj_advisor_metadata,
    should_checkpoint_supervisor_best,
    should_continue_training,
    sort_key,
    stagnation_round_count,
    target_hit_issues,
    training_event_payload,
    select_decision_round_best,
    select_target_weight_inversion_anchor,
    select_probability_calibration_champion,
    select_probability_focus_search_base,
    select_experimental_navigation_candidate,
    select_stagnation_exploration_champion,
    select_rank_homogeneity_restart_champion,
    select_supervisor_continuity_seed,
    select_source_frontier_champion,
    select_next_search_base,
    should_refresh_probability_focus,
    should_log_training_event_warning,
    source_frontier_diagnostics,
    stagnation_restart_catalog_position,
    stagnation_restart_candidate_configs,
    summarize_target_ranks,
    summary_config_hash,
    target_rank_movement,
    target_weight_inversion_advisor,
    target_weight_inversion_advisor_metadata,
    target_weight_inversion_budget_guardrail,
    training_progress_payload,
    weight_kdj_advisor_candidate_configs,
    weight_kdj_advisor_metadata,
)
from dehps.optimization.weight_kdj import weight_kdj_advice_from_signals


def supervisor_summary_for_config(
    config: FrequencyRankerConfig,
    *,
    top_100_hits: int = 0,
    top_1000_hits: int = 0,
    top_10000_hits: int = 3,
    median_rank: int = 500_000,
    best_rank: int = 1_000,
    worst_rank: int = 950_000,
    objective_score: float = 100.0,
    target_ranks: list[int] | None = None,
) -> dict:
    target_ranks = target_ranks or [best_rank]
    return {
        "config": config.__dict__,
        "config_hash": config_hash(config),
        "evaluated_draws": 100,
        "top_100_hits": top_100_hits,
        "top_1000_hits": top_1000_hits,
        "top_10000_hits": top_10000_hits,
        "median_rank": median_rank,
        "best_rank": best_rank,
        "worst_rank": worst_rank,
        "red5": {"top_100_hits": 0, "top_1000_hits": 0, "top_10000_hits": 0},
        "rank_quality": {
            "tail_over_1000000_count": 0,
            "tail_over_900000_count": 0,
            "tail_over_750000_count": 1,
        },
        "target_results": [
            {"issue": f"2026{index:03d}", "rank": rank}
            for index, rank in enumerate(target_ranks, start=1)
        ],
        "reward": {"objectiveScore": objective_score},
    }


def attach_test_frozen_validation(
    summary: dict,
    *,
    top_100_hits: int = 0,
    top_1000_hits: int = 0,
    top_10000_hits: int = 0,
    red5_top_100_hits: int = 0,
    red5_top_1000_hits: int = 0,
    red5_top_10000_hits: int = 0,
    median_rank: int = 700_000,
    objective_score: float = 0.0,
    tail_over_1000000_count: int = 0,
) -> dict:
    summary["frozen_validation"] = {
        "top_100_hits": top_100_hits,
        "top_1000_hits": top_1000_hits,
        "top_10000_hits": top_10000_hits,
        "median_rank": median_rank,
        "worst_rank": 1_000_000,
        "red5": {
            "top_100_hits": red5_top_100_hits,
            "top_1000_hits": red5_top_1000_hits,
            "top_10000_hits": red5_top_10000_hits,
        },
        "rank_quality": {"tail_over_1000000_count": tail_over_1000000_count},
        "reward": {"objectiveScore": objective_score},
    }
    return summary


def make_target_rank(issue: str, rank: int) -> TargetRank:
    return TargetRank(
        issue=issue,
        rank=rank,
        score=float(-rank),
        hit_top_100=rank <= 100,
        hit_top_1000=rank <= 1000,
        hit_top_10000=rank <= 10_000,
    )


def test_partitioned_summary_keeps_frozen_targets_out_of_search_metrics():
    targets = [
        make_target_rank("issue-1", 50),
        make_target_rank("issue-2", 500),
        make_target_rank("issue-3", 5_000),
        make_target_rank("issue-4", 75),
        make_target_rank("issue-5", 750),
    ]

    summary = supervisor.summarize_partitioned_target_ranks(
        target_ranks=targets,
        config=FrequencyRankerConfig(),
        as_of_issue="issue-5",
        history_fingerprint_value="history",
        train_window=3,
        train_mode="expanding",
        top_n=10_000,
        universe_size=1_107_568,
        validation_window=2,
    )

    assert summary["evaluated_draws"] == 3
    assert summary["top_100_hits"] == 1
    assert summary["top_1000_hits"] == 2
    assert summary["top_10000_hits"] == 3
    assert [row["issue"] for row in summary["target_results"]] == [
        "issue-1",
        "issue-2",
        "issue-3",
    ]
    assert summary["frozen_validation"]["issues"] == ["issue-4", "issue-5"]
    assert summary["frozen_validation"]["top_100_hits"] == 1
    assert summary["evaluation_split"] == {
        "protocol": supervisor.HOLDOUT_ISOLATION_PROTOCOL,
        "total_window": 5,
        "search_window": 3,
        "frozen_window": 2,
        "search_issues": ["issue-1", "issue-2", "issue-3"],
        "frozen_issues": ["issue-4", "issue-5"],
        "issue_overlap_count": 0,
        "search_uses_frozen_validation": False,
        "frozen_validation_role": "promotion_only",
    }


def test_historical_frozen_promotion_is_quarantined_fail_closed():
    candidate = attach_test_frozen_validation(
        supervisor_summary_for_config(FrequencyRankerConfig(structural_weight=0.8)),
        top_100_hits=1,
        objective_score=10.0,
    )
    incumbent = attach_test_frozen_validation(
        supervisor_summary_for_config(FrequencyRankerConfig(structural_weight=0.7)),
        objective_score=0.0,
    )

    base_gate = frozen_validation_promotion_gate(candidate, incumbent)
    quarantined = supervisor.quarantine_historical_frozen_promotion(base_gate)

    assert base_gate["passed"] is True
    assert quarantined["passed"] is False
    assert quarantined["reason"] == "historical_frozen_holdout_quarantined"
    assert quarantined["pre_quarantine_passed"] is True
    assert quarantined["promotion_holdout_status"] == "requires_forward_unseen_evidence"


def test_should_checkpoint_supervisor_best_only_for_carryover_or_promoted_best():
    summary = {"config_hash": "best"}

    assert should_checkpoint_supervisor_best(summary, round_index=0, improved=False) is True
    assert should_checkpoint_supervisor_best(summary, round_index=7, improved=False) is False
    assert should_checkpoint_supervisor_best(summary, round_index=7, improved=True) is True
    assert should_checkpoint_supervisor_best(None, round_index=0, improved=True) is False


def test_persisted_round_candidates_keep_decision_candidate_outside_top_five():
    summaries = [supervisor_summary_for_config(FrequencyRankerConfig(frequency_weight=0.1 + index * 0.01)) for index in range(6)]
    decision = supervisor_summary_for_config(FrequencyRankerConfig(frequency_weight=1.15))

    persisted = persisted_round_candidate_summaries(summaries, decision_round_best=decision)

    assert len(persisted) == 6
    assert [summary_config_hash(item) for item in persisted[:5]] == [
        summary_config_hash(item) for item in summaries[:5]
    ]
    assert summary_config_hash(persisted[-1]) == summary_config_hash(decision)
    assert "target_results" not in persisted[-1]


def test_recover_supervisor_continuity_reconstructs_legacy_restart_candidate():
    base = FrequencyRankerConfig(frequency_weight=0.7, omission_weight=0.05)
    restart_candidates = stagnation_restart_candidate_configs(
        base,
        max_configs=5,
        round_index=17,
        stagnation_rounds=16,
    )
    selected = restart_candidates[3]
    selected_hash = config_hash(selected)
    records = [
        {
            "run_id": "legacy-run",
            "round_index": 17,
            "best_config": base.__dict__,
            "best_summary": supervisor_summary_for_config(base),
            "top_results": [],
            "prefilter": {
                "stagnation_rounds": 16,
                "candidate_budget": {"stagnation_restart": 5},
                "search_base_start": {"config": base.__dict__},
                "rank_homogeneity_restart_champion": {"config_hash": selected_hash},
                "decision_round_best": {
                    "source": "source_frontier",
                    "config_hash": selected_hash,
                    "selected_frozen_primary_score": [0, 0, 1],
                    "frozen_primary_lift_baseline_score": [0, 0, 0],
                },
            },
        }
    ]

    configs, metadata = recover_supervisor_continuity_configs(records)

    assert [config_hash(config) for config in configs] == [selected_hash]
    assert metadata["recovered_count"] == 1
    assert metadata["candidates"][0]["recovery_mode"] == "deterministic_restart_recovery"


def test_recover_supervisor_continuity_reconstructs_rotated_restart_candidate():
    base = FrequencyRankerConfig(frequency_weight=0.7, omission_weight=0.05)
    restart_candidates = stagnation_restart_candidate_configs(
        base,
        max_configs=5,
        round_index=18,
        stagnation_rounds=17,
        catalog_offset=5,
    )
    selected = restart_candidates[2]
    selected_hash = config_hash(selected)
    records = [
        {
            "run_id": "rotated-run",
            "round_index": 18,
            "best_config": base.__dict__,
            "best_summary": supervisor_summary_for_config(base),
            "top_results": [],
            "prefilter": {
                "stagnation_rounds": 17,
                "stagnation_restart_catalog_offset": 5,
                "candidate_budget": {"stagnation_restart": 5},
                "search_base_start": {"config": base.__dict__},
                "rank_homogeneity_restart_champion": {"config_hash": selected_hash},
                "decision_round_best": {
                    "source": "rank_homogeneity_restart",
                    "config_hash": selected_hash,
                    "selected_frozen_primary_score": [0, 0, 1],
                    "frozen_primary_lift_baseline_score": [0, 0, 0],
                },
            },
        }
    ]

    configs, metadata = recover_supervisor_continuity_configs(records)

    assert [config_hash(config) for config in configs] == [selected_hash]
    assert metadata["recovered_count"] == 1
    assert metadata["candidates"][0]["recovery_mode"] == "deterministic_restart_recovery"


def test_holdout_isolated_continuity_rejects_legacy_frozen_selected_search_base():
    legacy = FrequencyRankerConfig(structural_weight=0.6)
    isolated = FrequencyRankerConfig(structural_weight=0.8)
    records = [
        {
            "run_id": "new-run",
            "round_index": 2,
            "prefilter": {
                "holdout_isolation": {
                    "protocol": supervisor.HOLDOUT_ISOLATION_PROTOCOL,
                    "search_uses_frozen_validation": False,
                },
                "search_base": {
                    "config": isolated.__dict__,
                    "source": "search_challenger",
                },
            },
        },
        {
            "run_id": "legacy-run",
            "round_index": 9,
            "prefilter": {
                "search_base": {
                    "config": legacy.__dict__,
                    "source": "source_frontier",
                },
            },
        },
    ]

    configs, metadata = supervisor.recover_holdout_isolated_continuity_configs(records)

    assert [config_hash(config) for config in configs] == [config_hash(isolated)]
    assert metadata["recovered_count"] == 1
    assert metadata["rejected_legacy_count"] == 1
    assert metadata["candidates"][0]["source"] == "search_challenger"


def test_supervisor_continuity_seed_requires_revalidated_frozen_primary_lift():
    baseline = attach_test_frozen_validation(
        supervisor_summary_for_config(FrequencyRankerConfig(frequency_weight=0.7)),
        top_10000_hits=0,
    )
    flat = attach_test_frozen_validation(
        supervisor_summary_for_config(FrequencyRankerConfig(frequency_weight=0.8)),
        top_10000_hits=0,
        objective_score=10.0,
    )
    lifted = attach_test_frozen_validation(
        supervisor_summary_for_config(FrequencyRankerConfig(frequency_weight=1.15)),
        top_10000_hits=1,
        objective_score=-5.0,
    )

    selected, metadata = select_supervisor_continuity_seed([flat, lifted], baseline=baseline)

    assert summary_config_hash(selected) == summary_config_hash(lifted)
    assert metadata["reason"] == "strict_frozen_primary_lift_revalidated"
    assert metadata["baseline_frozen_primary_score"] == [0, 0, 0]
    assert metadata["selected_frozen_primary_score"] == [0, 0, 1]


def test_duration_hours_zero_means_continuous_training():
    started_at = datetime(2026, 6, 22, 9, 0, 0)

    assert resolve_training_deadline(started_at, 0) is None
    assert resolve_training_deadline(started_at, -1) is None
    assert should_continue_training(5000, None, now=started_at + timedelta(days=365))


def test_positive_duration_hours_keeps_timed_training_mode():
    started_at = datetime(2026, 6, 22, 9, 0, 0)
    deadline = resolve_training_deadline(started_at, 24)

    assert deadline == started_at + timedelta(hours=24)
    assert should_continue_training(0, deadline, now=deadline + timedelta(seconds=1))
    assert should_continue_training(1, deadline, now=deadline - timedelta(seconds=1))
    assert not should_continue_training(1, deadline, now=deadline)


def test_phase_for_round_starts_broad_then_anneals_to_late_refine():
    assert phase_for_round(0) == ("large", 0.20, "early_broad")
    assert phase_for_round(1) == ("large", 0.15, "early_broad")
    assert phase_for_round(24) == ("medium", 0.08, "mid_search")
    assert phase_for_round(72) == ("small", 0.03, "late_refine")
    assert phase_for_round(90) in {
        ("small", 0.03, "late_refine"),
        ("micro", 0.015, "late_refine"),
        ("micro", 0.01, "late_refine"),
        ("small", 0.02, "late_refine"),
    }
    assert phase_for_round(90, stagnation_rounds=16) == ("large", 0.15, "stagnation_broad")
    assert search_base_min_distance_for_phase("early_broad") == 0.08
    assert search_base_min_distance_for_phase("mid_search") == 0.04
    assert search_base_min_distance_for_phase("late_refine") == 0.015


def test_target_weight_inversion_anchor_uses_challenger_when_incumbent_replays():
    incumbent_config = FrequencyRankerConfig()
    challenger_config = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    incumbent = supervisor_summary_for_config(
        incumbent_config,
        top_100_hits=2,
        top_1000_hits=3,
        top_10000_hits=3,
        median_rank=579_000,
        objective_score=2200.0,
    )
    challenger = supervisor_summary_for_config(
        challenger_config,
        top_100_hits=2,
        top_1000_hits=3,
        top_10000_hits=3,
        median_rank=581_000,
        objective_score=2190.0,
    )

    anchor, challenger_best, metadata = select_target_weight_inversion_anchor(
        summaries=[incumbent, challenger],
        prior_best_summary=incumbent,
        round_best=incumbent,
        improved=False,
    )

    assert best_challenger_summary([incumbent, challenger], summary_config_hash(incumbent)) is challenger
    assert anchor is challenger
    assert challenger_best is challenger
    assert metadata["source"] == "challenger_best"
    assert metadata["round_best_replays_incumbent"] is True
    assert metadata["config_hash"] == config_hash(challenger_config)
    assert metadata["incumbent_config_hash"] == config_hash(incumbent_config)
    assert metadata["challenger_rank_vector_changed"] is False


def test_target_weight_inversion_anchor_blocks_challenger_without_frozen_primary_lift():
    incumbent_config = FrequencyRankerConfig()
    challenger_config = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    incumbent = attach_test_frozen_validation(
        supervisor_summary_for_config(incumbent_config, target_ranks=[100, 900, 50_000]),
        top_10000_hits=0,
    )
    challenger = attach_test_frozen_validation(
        supervisor_summary_for_config(
            challenger_config,
            top_100_hits=3,
            top_1000_hits=3,
            top_10000_hits=3,
            target_ranks=[17, 55, 89],
            objective_score=2300.0,
        ),
        top_10000_hits=0,
    )

    anchor, challenger_best, metadata = select_target_weight_inversion_anchor(
        summaries=[incumbent, challenger],
        prior_best_summary=incumbent,
        round_best=challenger,
        improved=False,
        require_frozen_primary_lift=True,
        frozen_primary_lift_baseline=incumbent,
    )

    assert anchor is incumbent
    assert challenger_best is None
    assert metadata["source"] == "incumbent_primary_gate"
    assert metadata["round_best_primary_allowed"] is False
    assert metadata["round_best_frozen_primary_score"] == [0, 0, 0]


def test_best_challenger_prefers_different_rank_vector_over_config_only_change():
    incumbent_config = FrequencyRankerConfig()
    same_rank_config = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    changed_rank_config = FrequencyRankerConfig(frequency_weight=0.20, omission_weight=0.40)
    incumbent = supervisor_summary_for_config(incumbent_config, target_ranks=[100, 900, 50_000])
    same_rank = supervisor_summary_for_config(same_rank_config, target_ranks=[100, 900, 50_000], objective_score=2190.0)
    changed_rank = supervisor_summary_for_config(changed_rank_config, target_ranks=[99, 900, 50_000], objective_score=2180.0)

    challenger = best_challenger_summary(
        [incumbent, same_rank, changed_rank],
        summary_config_hash(incumbent),
        incumbent_summary=incumbent,
    )

    assert challenger is changed_rank


def test_next_search_base_advances_to_challenger_without_promoting_best():
    incumbent_config = FrequencyRankerConfig()
    challenger_config = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    incumbent = supervisor_summary_for_config(incumbent_config, objective_score=2200.0)
    challenger = supervisor_summary_for_config(challenger_config, objective_score=2190.0)

    next_base, metadata = select_next_search_base(
        current_base=incumbent_config,
        summaries=[incumbent, challenger],
        round_best=incumbent,
        improved=False,
    )

    assert config_hash(next_base) == config_hash(challenger_config)
    assert metadata["source"] == "search_challenger"
    assert metadata["changed"] is True
    assert metadata["previous_config_hash"] == config_hash(incumbent_config)
    assert metadata["config_hash"] == config_hash(challenger_config)


def test_next_search_base_does_not_stall_on_current_base_replay():
    current_config = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    alternative_config = FrequencyRankerConfig(frequency_weight=0.20, omission_weight=0.40)
    current = supervisor_summary_for_config(current_config, target_ranks=[100, 900, 50_000], objective_score=2190.0)
    alternative = supervisor_summary_for_config(
        alternative_config,
        target_ranks=[99, 900, 50_000],
        objective_score=2180.0,
    )

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[current, alternative],
        round_best=current,
        improved=False,
    )

    assert config_hash(next_base) == config_hash(alternative_config)
    assert metadata["source"] == "search_challenger"
    assert metadata["changed"] is True
    assert metadata["search_challenger_rank_vector_changed"] is True


def test_next_search_base_avoids_recent_two_config_bounce():
    current_config = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    previous_config = FrequencyRankerConfig()
    novel_config = FrequencyRankerConfig(frequency_weight=0.20, omission_weight=0.40)
    current = supervisor_summary_for_config(current_config, target_ranks=[100, 900, 50_000], objective_score=2190.0)
    previous = supervisor_summary_for_config(previous_config, target_ranks=[99, 900, 50_000], objective_score=2185.0)
    novel = supervisor_summary_for_config(novel_config, target_ranks=[101, 850, 50_000], objective_score=2180.0)

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[current, previous, novel],
        round_best=current,
        improved=False,
        recent_search_base_hashes=(config_hash(current_config), config_hash(previous_config)),
    )

    assert config_hash(next_base) == config_hash(novel_config)
    assert metadata["source"] == "search_challenger"
    assert metadata["changed"] is True
    assert metadata["config_hash"] not in metadata["recent_search_base_hashes"]


def test_next_search_base_prefers_distant_candidate_during_broad_phase():
    current_config = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    tiny_variant_config = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10001)
    distant_config = FrequencyRankerConfig(frequency_weight=0.25, omission_weight=0.30)
    current = supervisor_summary_for_config(current_config, target_ranks=[100, 900, 50_000], objective_score=2190.0)
    tiny_variant = supervisor_summary_for_config(
        tiny_variant_config,
        target_ranks=[99, 900, 50_000],
        objective_score=2189.0,
    )
    distant = supervisor_summary_for_config(
        distant_config,
        target_ranks=[120, 1200, 80_000],
        objective_score=2100.0,
    )

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[current, tiny_variant, distant],
        round_best=current,
        improved=False,
        min_config_distance=0.08,
    )

    assert config_hash(next_base) == config_hash(distant_config)
    assert metadata["source"] == "search_challenger"
    assert metadata["selected_config_distance"] >= 0.08
    assert metadata["search_challenger_config_distance"] >= 0.08


def test_next_search_base_skips_unpromoted_round_best_when_gate_closed():
    current_config = FrequencyRankerConfig()
    round_best_config = FrequencyRankerConfig(frequency_weight=0.40)
    challenger_config = FrequencyRankerConfig(frequency_weight=0.60)
    current = supervisor_summary_for_config(current_config, objective_score=2000.0)
    round_best = supervisor_summary_for_config(
        round_best_config,
        target_ranks=[100, 900, 50_000],
        objective_score=2300.0,
    )
    challenger = supervisor_summary_for_config(
        challenger_config,
        target_ranks=[90, 850, 49_000],
        objective_score=2100.0,
    )

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[current, round_best, challenger],
        round_best=round_best,
        improved=False,
        allow_unpromoted_round_best=False,
        round_best_skip_reason="stale_unpromoted_round_best_primary_gate",
    )

    assert config_hash(next_base) == config_hash(challenger_config)
    assert metadata["source"] == "search_challenger"
    assert metadata["round_best_search_allowed"] is False
    assert metadata["round_best_search_blocked"] is True
    assert metadata["round_best_skip_reason"] == "stale_unpromoted_round_best_primary_gate"
    assert metadata["round_best_config_hash"] == config_hash(round_best_config)


def test_next_search_base_keeps_unpromoted_round_best_when_gate_open():
    current_config = FrequencyRankerConfig()
    round_best_config = FrequencyRankerConfig(frequency_weight=0.40)
    challenger_config = FrequencyRankerConfig(frequency_weight=0.60)
    current = supervisor_summary_for_config(current_config, objective_score=2000.0)
    round_best = supervisor_summary_for_config(
        round_best_config,
        target_ranks=[100, 900, 50_000],
        objective_score=2300.0,
    )
    challenger = supervisor_summary_for_config(
        challenger_config,
        target_ranks=[90, 850, 49_000],
        objective_score=2100.0,
    )

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[current, round_best, challenger],
        round_best=round_best,
        improved=False,
        allow_unpromoted_round_best=True,
    )

    assert config_hash(next_base) == config_hash(round_best_config)
    assert metadata["source"] == "round_best"
    assert metadata["round_best_search_allowed"] is True
    assert metadata["round_best_search_blocked"] is False
    assert metadata["round_best_skip_reason"] == ""


def test_stale_round_best_search_base_gate_blocks_collapsed_unpromoted_round_best():
    gate = supervisor.stale_round_best_search_base_gate(
        stagnation_rounds=supervisor.PROBABILITY_PRIMARY_GATE_STAGNATION_THRESHOLD,
        rank_homogeneity={"active": True},
        promotion_gate={"passed": False, "primary_hit_passed": False},
    )

    assert gate["active"] is True
    assert gate["allow_unpromoted_round_best"] is False
    assert gate["reason"] == "stale_unpromoted_round_best_primary_gate"


def test_promotion_only_frozen_validation_blocks_round_best_without_guiding_navigation():
    gate = supervisor.stale_round_best_search_base_gate(
        stagnation_rounds=supervisor.PROBABILITY_PRIMARY_GATE_STAGNATION_THRESHOLD,
        rank_homogeneity={"active": True},
        promotion_gate={"passed": False, "primary_hit_passed": True},
        frozen_promotion_only=True,
    )

    assert gate["active"] is True
    assert gate["allow_unpromoted_round_best"] is False
    assert gate["require_frozen_primary_challenger"] is False
    assert gate["primary_hit_passed"] is True
    assert gate["navigation_primary_hit_passed"] is False
    assert gate["navigation_evidence"] == "search_slice_only"
    assert gate["frozen_validation_role"] == "promotion_only"

    below_search_threshold = supervisor.stale_round_best_search_base_gate(
        stagnation_rounds=supervisor.STAGNATION_THRESHOLD,
        rank_homogeneity={"active": True},
        promotion_gate={"passed": False, "primary_hit_passed": False},
        eval_slice_overfit={"active": True},
        frozen_promotion_only=True,
    )
    assert below_search_threshold["eval_slice_overfit_active"] is True
    assert below_search_threshold["navigation_eval_slice_overfit_active"] is False
    assert below_search_threshold["active"] is False


def test_promotion_only_search_navigation_prefers_changed_restart_geometry_without_frozen_lift():
    current_config = FrequencyRankerConfig()
    challenger_config = FrequencyRankerConfig(frequency_weight=0.60)
    restart_config = FrequencyRankerConfig(
        structural_weight=0.85,
        frequency_weight=1.15,
        omission_weight=1.15,
    )
    current = attach_test_frozen_validation(
        supervisor_summary_for_config(
            current_config,
            target_ranks=[100, 900, 50_000],
            objective_score=2200.0,
        ),
        top_10000_hits=0,
    )
    challenger = attach_test_frozen_validation(
        supervisor_summary_for_config(
            challenger_config,
            target_ranks=[90, 850, 49_000],
            objective_score=2190.0,
        ),
        top_10000_hits=0,
    )
    restart = attach_test_frozen_validation(
        supervisor_summary_for_config(
            restart_config,
            target_ranks=[500, 10_000, 900_000],
            objective_score=1800.0,
        ),
        top_10000_hits=0,
    )

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[current, challenger, restart],
        round_best=challenger,
        improved=False,
        exploration_navigation_candidate=restart,
        exploration_navigation_source="rank_homogeneity_restart_champion",
        exploration_navigation_reason="rank_homogeneity_restart_changed_rank_vector",
        excluded_rank_signature_hashes=(rank_signature_hash(challenger),),
        min_config_distance=0.08,
        allow_unpromoted_round_best=False,
        round_best_skip_reason="stale_unpromoted_round_best_primary_gate",
        require_frozen_primary_lift=False,
        frozen_primary_lift_baseline=current,
        frozen_promotion_only=True,
    )

    assert config_hash(next_base) == config_hash(restart_config)
    assert metadata["source"] == "experimental_navigation"
    assert metadata["exploration_navigation_eligible"] is True
    assert metadata["exploration_navigation_eligibility_basis"] == "search_slice_rank_geometry"
    assert metadata["exploration_navigation_selection_uses_frozen_validation"] is False
    assert metadata["exploration_navigation_selected"] is True
    assert metadata["exploration_navigation_preempted_by"] == ""
    assert metadata["exploration_navigation_primary_lift_passed"] is False
    assert metadata["selected_frozen_primary_score"] == [0, 0, 0]


def test_promotion_only_search_navigation_does_not_prioritize_unchanged_rank_geometry():
    current_config = FrequencyRankerConfig()
    challenger_config = FrequencyRankerConfig(frequency_weight=0.60)
    restart_config = FrequencyRankerConfig(
        structural_weight=0.85,
        frequency_weight=1.15,
        omission_weight=1.15,
    )
    current = supervisor_summary_for_config(
        current_config,
        target_ranks=[100, 900, 50_000],
        objective_score=2200.0,
    )
    challenger = supervisor_summary_for_config(
        challenger_config,
        target_ranks=[90, 850, 49_000],
        objective_score=2190.0,
    )
    unchanged_restart = supervisor_summary_for_config(
        restart_config,
        target_ranks=[100, 900, 50_000],
        objective_score=1800.0,
    )

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[current, challenger, unchanged_restart],
        round_best=challenger,
        improved=False,
        exploration_navigation_candidate=unchanged_restart,
        min_config_distance=0.08,
        allow_unpromoted_round_best=False,
        frozen_promotion_only=True,
    )

    assert config_hash(next_base) != config_hash(current_config)
    assert metadata["source"] == "search_challenger"
    assert metadata["exploration_navigation_eligible"] is False
    assert metadata["exploration_navigation_eligibility_basis"] == "ineligible"
    assert metadata["exploration_navigation_selection_uses_frozen_validation"] is False


def test_probability_focus_arbitration_preserves_eligible_navigation_audit():
    focus_metadata = {
        "source": "probability_focus",
        "config_hash": "focus-hash",
        "candidate_config_hash": "focus-hash",
        "reason": "selected_focus",
    }
    navigation_audit = {
        "source": "experimental_navigation",
        "config_hash": "restart-hash",
        "exploration_navigation_config_hash": "restart-hash",
        "exploration_navigation_eligible": True,
        "exploration_navigation_eligibility_basis": "search_slice_rank_geometry",
        "exploration_navigation_selection_uses_frozen_validation": False,
        "exploration_navigation_selected": True,
        "exploration_navigation_preempted_by": "",
        "exploration_navigation_rank_vector_changed": True,
    }

    merged = supervisor.merge_experimental_navigation_arbitration(
        focus_metadata,
        navigation_audit,
    )

    assert merged["source"] == "probability_focus"
    assert merged["config_hash"] == "focus-hash"
    assert merged["exploration_navigation_config_hash"] == "restart-hash"
    assert merged["exploration_navigation_eligible"] is True
    assert merged["exploration_navigation_eligibility_basis"] == "search_slice_rank_geometry"
    assert merged["exploration_navigation_selection_uses_frozen_validation"] is False
    assert merged["exploration_navigation_selected"] is False
    assert merged["exploration_navigation_preempted_by"] == "probability_focus"


def test_eval_slice_overfit_guardrail_blocks_unpromoted_round_best():
    round_best_config = FrequencyRankerConfig(frequency_weight=0.40)
    challenger_config = FrequencyRankerConfig(frequency_weight=0.60)
    round_best = attach_test_frozen_validation(
        supervisor_summary_for_config(
            round_best_config,
            top_100_hits=3,
            top_1000_hits=3,
            top_10000_hits=3,
            target_ranks=[17, 55, 89, 50_000],
            objective_score=2300.0,
        ),
        top_100_hits=0,
        top_1000_hits=0,
        top_10000_hits=0,
    )
    challenger = attach_test_frozen_validation(
        supervisor_summary_for_config(
            challenger_config,
            top_100_hits=3,
            top_1000_hits=3,
            top_10000_hits=3,
            target_ranks=[19, 60, 95, 40_000],
            objective_score=2200.0,
        ),
        top_100_hits=0,
        top_1000_hits=0,
        top_10000_hits=0,
    )

    overfit = supervisor.eval_slice_overfit_guardrail(
        summaries=[round_best, challenger],
        source_configs={"normal": (round_best_config,), "ridge_kdj": (challenger_config,)},
        round_best=round_best,
        prior_best_summary=round_best,
        rank_homogeneity={"active": True, "unique_signature_count": 1},
        promotion_gate={"passed": False, "primary_hit_passed": False},
        stagnation_rounds=supervisor.STAGNATION_THRESHOLD,
    )
    gate = supervisor.stale_round_best_search_base_gate(
        stagnation_rounds=supervisor.STAGNATION_THRESHOLD,
        rank_homogeneity={"active": True},
        promotion_gate={"passed": False, "primary_hit_passed": False},
        eval_slice_overfit=overfit,
    )

    assert overfit["active"] is True
    assert overfit["reason"] == "eval_slice_overfit_no_frozen_primary_lift"
    assert overfit["round_best_eval_primary_score"] == [3, 3, 3]
    assert overfit["round_best_frozen_primary_score"] == [0, 0, 0]
    assert overfit["round_best_top_100_hit_issues"] == ["2026001", "2026002", "2026003"]
    assert overfit["source_counts"] == {"normal": 1, "ridge_kdj": 1}
    assert gate["allow_unpromoted_round_best"] is False
    assert gate["require_frozen_primary_challenger"] is True
    assert gate["reason"] == "eval_slice_overfit_no_frozen_primary_lift"


def test_eval_slice_overfit_guardrail_labels_kept_diagnostic_sources():
    generated_config = FrequencyRankerConfig(frequency_weight=0.40)
    kept_elite_config = FrequencyRankerConfig(frequency_weight=0.60)
    round_best = attach_test_frozen_validation(
        supervisor_summary_for_config(
            generated_config,
            top_100_hits=3,
            top_1000_hits=3,
            top_10000_hits=3,
            target_ranks=[17, 55, 89],
        ),
        top_100_hits=0,
        top_1000_hits=0,
        top_10000_hits=0,
    )
    kept_elite = attach_test_frozen_validation(
        supervisor_summary_for_config(
            kept_elite_config,
            top_100_hits=3,
            top_1000_hits=3,
            top_10000_hits=3,
            target_ranks=[19, 60, 95],
        ),
        top_100_hits=0,
        top_1000_hits=0,
        top_10000_hits=0,
    )

    sources = diagnostic_source_configs(
        {"normal": (generated_config,)},
        best_config=generated_config,
        elite_configs=(kept_elite_config,),
    )
    overfit = supervisor.eval_slice_overfit_guardrail(
        summaries=[round_best, kept_elite],
        source_configs=sources,
        round_best=round_best,
        prior_best_summary=round_best,
        rank_homogeneity={"active": True, "unique_signature_count": 1},
        promotion_gate={"passed": False, "primary_hit_passed": False},
        stagnation_rounds=supervisor.STAGNATION_THRESHOLD,
    )

    assert overfit["source_counts"] == {"keep_elite": 1, "normal": 1}
    assert [row["source"] for row in overfit["suspicious_candidates"]] == ["normal", "keep_elite"]


def test_decision_round_best_requires_frozen_primary_lift_under_overfit_gate():
    incumbent_config = FrequencyRankerConfig(frequency_weight=0.30)
    restart_config = FrequencyRankerConfig(frequency_weight=0.90)
    incumbent = attach_test_frozen_validation(
        supervisor_summary_for_config(incumbent_config, target_ranks=[100, 900, 50_000]),
        top_100_hits=0,
        top_1000_hits=0,
        top_10000_hits=0,
    )
    restart = attach_test_frozen_validation(
        supervisor_summary_for_config(
            restart_config,
            top_100_hits=3,
            top_1000_hits=3,
            top_10000_hits=3,
            target_ranks=[17, 55, 89],
        ),
        top_100_hits=0,
        top_1000_hits=0,
        top_10000_hits=0,
    )

    selected, metadata = select_decision_round_best(
        round_best=restart,
        prior_best_summary=incumbent,
        improved=False,
        restart_champion=restart,
        require_frozen_primary_lift=True,
    )

    assert selected is incumbent
    assert metadata["source"] == "incumbent"
    assert metadata["reason"] == "incumbent_due_to_required_frozen_primary_lift"
    assert metadata["blocked_candidates"] == [
        {
            "source": "rank_homogeneity_restart",
            "config_hash": summary_config_hash(restart),
            "frozen_primary_score": [0, 0, 0],
        }
    ]


def test_decision_round_best_allows_primary_lift_under_overfit_gate():
    incumbent = attach_test_frozen_validation(
        supervisor_summary_for_config(FrequencyRankerConfig(frequency_weight=0.30)),
        top_10000_hits=0,
    )
    source_frontier = attach_test_frozen_validation(
        supervisor_summary_for_config(FrequencyRankerConfig(frequency_weight=0.65)),
        top_10000_hits=1,
    )

    selected, metadata = select_decision_round_best(
        round_best=source_frontier,
        prior_best_summary=incumbent,
        improved=False,
        source_frontier_champion=source_frontier,
        require_frozen_primary_lift=True,
    )

    assert selected is source_frontier
    assert metadata["source"] == "source_frontier"
    assert metadata["selected_frozen_primary_score"] == [0, 0, 1]


def test_target_weight_inversion_anchor_keeps_new_best_when_improved():
    incumbent_config = FrequencyRankerConfig()
    improved_config = FrequencyRankerConfig(frequency_weight=0.50, omission_weight=0.08)
    incumbent = supervisor_summary_for_config(incumbent_config, objective_score=2200.0)
    new_best = supervisor_summary_for_config(
        improved_config,
        top_100_hits=3,
        top_1000_hits=4,
        top_10000_hits=5,
        median_rank=420_000,
        objective_score=3200.0,
    )

    anchor, challenger_best, metadata = select_target_weight_inversion_anchor(
        summaries=[new_best, incumbent],
        prior_best_summary=incumbent,
        round_best=new_best,
        improved=True,
    )

    assert anchor is new_best
    assert challenger_best is new_best
    assert metadata["source"] == "new_best"
    assert metadata["round_best_replays_incumbent"] is False
    assert metadata["config_hash"] == config_hash(improved_config)


def test_generate_configs_keeps_base_and_clamps_weight_range():
    base = FrequencyRankerConfig(
        structural_weight=0.40,
        frequency_weight=0.30,
        omission_weight=0.25,
        previous_consecutive_weight=0.05,
    )

    configs = generate_configs(base, phase="large", step=1.0, max_configs=32)

    assert configs[0] == base
    assert len({tuple(config.__dict__.items()) for config in configs}) == len(configs)
    assert all(0 <= config.structural_weight <= 1.25 for config in configs)
    assert all(-0.30 <= config.previous_overlap_weight <= 0.30 for config in configs)


def test_candidate_budget_uses_search_intelligence_mix():
    budget = candidate_budget(20)

    assert budget == {"exploitation": 8, "exploration": 6, "replay": 4, "baseline": 2}
    assert sum(budget.values()) == 20


def test_training_round_self_diagnostics_blocks_collapsed_noise_round():
    config = FrequencyRankerConfig(frequency_weight=0.40)
    round_best = supervisor_summary_for_config(
        config,
        top_100_hits=3,
        top_1000_hits=3,
        top_10000_hits=3,
        target_ranks=[17, 55, 89, 500_000, 700_000],
    )
    diagnostics = supervisor.training_round_self_diagnostics(
        round_best=round_best,
        source_configs={"normal": (config,), "weight_kdj": ()},
        refined_configs=(config,),
        summaries=[round_best for _index in range(5)],
        rank_homogeneity={"active": True, "unique_signature_count": 1},
        promotion_gate={"passed": False, "primary_hit_passed": False},
        eval_slice_overfit={"active": True},
        target_weight_inversion_guardrail={"active": False},
        advisor_info={"selected_count": 0, "downweighted_count": 0, "rejected_count": 0},
        ridge_advisor_info={"selected_count": 0},
        neural_advisor_info={"selected_count": 0},
        universe_size=supervisor.DEFAULT_UNIVERSE_SIZE,
    )

    assert diagnostics["synthesis"]["status"] == "blocked"
    assert diagnostics["synthesis"]["action"] == "freeze_promotion_and_force_diagnostics"
    assert diagnostics["candidate_space"]["status"] == "collapsed"
    assert diagnostics["signal_vs_noise"]["status"] == "noise_risk"
    assert diagnostics["signal_vs_noise"]["candidate_hypothesis_count"] == 1
    assert diagnostics["signal_vs_noise"]["minimum_familywise_hypothesis_count"] == 3
    assert diagnostics["signal_vs_noise"]["sequential_observed_familywise_hypothesis_count"] == 3
    assert diagnostics["signal_vs_noise"]["sequential_family"]["total_round_count"] == 1
    assert diagnostics["signal_vs_noise"]["sequential_family"]["promotion_allowed"] is False
    assert diagnostics["weight_trust"]["status"] in {"blocked", "caution"}


def test_training_candidate_space_diagnostic_separates_stale_champion_from_diverse_top_results():
    configs = tuple(
        FrequencyRankerConfig(frequency_weight=round(0.30 + index * 0.05, 2))
        for index in range(5)
    )
    summaries = [
        supervisor_summary_for_config(
            config,
            target_ranks=[100 + index, 1_000 + index * 10, 10_000 + index * 100],
        )
        for index, config in enumerate(configs)
    ]

    diagnostic = supervisor.training_candidate_space_diagnostic(
        source_configs={"normal": configs},
        refined_configs=configs,
        summaries=summaries,
        rank_homogeneity={"active": True, "unique_signature_count": 1},
    )

    assert diagnostic["status"] == "diverse"
    assert diagnostic["unique_top_rank_signature_count"] == 5
    assert diagnostic["round_best_path_status"] == "stale"
    assert "round_best_path_homogeneous_current_candidates_still_diverse" in diagnostic["reasons"]


def test_decision_surface_diagnostic_detects_objective_tiebreak_pareto_tradeoffs():
    baseline = supervisor_summary_for_config(
        FrequencyRankerConfig(frequency_weight=0.30),
        top_100_hits=3,
        top_1000_hits=3,
        top_10000_hits=3,
        median_rank=600_000,
        best_rank=50,
        worst_rank=900_000,
        objective_score=100.0,
        target_ranks=[50, 1_000, 10_000],
    )
    baseline["rank_quality"].update(
        {
            "top_50000_hits": 3,
            "top_100000_hits": 5,
            "top_250000_hits": 17,
            "top_500000_hits": 36,
        }
    )
    baseline["reward"] = {
        "hitReward": 0.0,
        "baselineUniqueReward": 100.0,
        "baselineOverlapPenalty": 0.0,
        "red5Reward": 0.0,
        "rankQualityReward": 0.0,
        "rankPenalty": 0.0,
        "tailRiskPenalty": 0.0,
        "objectiveScore": 100.0,
    }
    challengers = []
    for index, objective_score in enumerate((99.999, 99.5), start=1):
        challenger = supervisor_summary_for_config(
            FrequencyRankerConfig(frequency_weight=round(0.30 + index * 0.05, 2)),
            top_100_hits=3,
            top_1000_hits=3,
            top_10000_hits=3,
            median_rank=500_000 - index,
            best_rank=45 - index,
            worst_rank=950_000 + index,
            objective_score=objective_score,
            target_ranks=[45 - index, 900, 9_000],
        )
        challenger["rank_quality"].update(
            {
                "top_50000_hits": 3,
                "top_100000_hits": 5,
                "top_250000_hits": 17,
                "top_500000_hits": 35,
            }
        )
        challenger["reward"] = {
            "hitReward": 0.0,
            "baselineUniqueReward": objective_score,
            "baselineOverlapPenalty": 0.0,
            "red5Reward": 0.0,
            "rankQualityReward": 0.0,
            "rankPenalty": 0.0,
            "tailRiskPenalty": 0.0,
            "objectiveScore": objective_score,
        }
        challengers.append(challenger)

    diagnostic = supervisor.decision_surface_dominance_diagnostic(
        [baseline, *challengers]
    )

    assert diagnostic["status"] == "objective_tiebreak_tradeoff"
    assert diagnostic["first_difference_counts"] == {"objective_score": 2}
    assert diagnostic["objective_gap_min"] == 0.001
    assert diagnostic["objective_gap_max"] == 0.5
    assert diagnostic["baseline_pareto_dominates_count"] == 0
    assert diagnostic["challenger_pareto_dominates_count"] == 0
    assert diagnostic["pareto_tradeoff_count"] == 2
    assert diagnostic["challenger_better_field_counts"]["neg_median_rank"] == 2
    assert diagnostic["baseline_better_field_counts"]["top_500000_hits"] == 2
    assert diagnostic["selection_uses_frozen_validation"] is False
    component_control = diagnostic["objective_component_control"]
    assert component_control["status"] == "measured"
    assert component_control["measured_comparison_count"] == 2
    assert component_control["largest_absolute_component_delta_counts"] == {
        "baseline_unique_reward": 2
    }
    assert component_control["max_abs_reconstruction_residual"] == 0.0
    assert component_control["selection_changed"] is False
    counterfactual = diagnostic["objective_component_counterfactual"]
    assert counterfactual["status"] == "measured"
    assert counterfactual["component"] == "tail_risk_penalty"
    assert counterfactual["counterfactual_top_changed"] is False
    assert counterfactual["selection_changed"] is False
    assert counterfactual["selection_uses_frozen_validation"] is False
    assert all(
        comparison["objective_component_residual"]["status"] == "measured"
        for comparison in diagnostic["comparisons"]
    )


def test_objective_component_residual_direction_normalizes_penalties():
    baseline = {
        "reward": {
            "hitReward": 0.0,
            "baselineUniqueReward": 110.0,
            "baselineOverlapPenalty": 0.0,
            "red5Reward": 0.0,
            "rankQualityReward": 0.0,
            "rankPenalty": 0.0,
            "tailRiskPenalty": 10.0,
            "objectiveScore": 100.0,
        }
    }
    challenger = {
        "reward": {
            "hitReward": 0.0,
            "baselineUniqueReward": 105.0,
            "baselineOverlapPenalty": 0.0,
            "red5Reward": 0.0,
            "rankQualityReward": 0.0,
            "rankPenalty": 0.0,
            "tailRiskPenalty": 6.0,
            "objectiveScore": 99.0,
        }
    }

    residual = supervisor.objective_component_residual(
        baseline,
        challenger,
        objective_gap=1.0,
    )

    assert residual["status"] == "measured"
    assert residual["component_deltas"]["baseline_unique_reward"] == 5.0
    assert residual["component_deltas"]["tail_risk_penalty"] == -4.0
    assert residual["component_delta_sum"] == 1.0
    assert residual["reconstruction_residual"] == 0.0
    assert residual["baseline_advantage_components"] == ["baseline_unique_reward"]
    assert residual["challenger_advantage_components"] == ["tail_risk_penalty"]

    mismatch = supervisor.objective_component_residual(
        baseline,
        challenger,
        objective_gap=2.0,
    )

    assert mismatch["status"] == "reconstruction_mismatch"
    assert mismatch["reconstruction_residual"] == 1.0


def test_objective_component_counterfactual_observes_tail_risk_flip_without_mutation():
    baseline = supervisor_summary_for_config(
        FrequencyRankerConfig(frequency_weight=0.30),
        objective_score=100.0,
    )
    baseline["reward"] = {
        "hitReward": 0.0,
        "baselineUniqueReward": 110.0,
        "baselineOverlapPenalty": 0.0,
        "red5Reward": 0.0,
        "rankQualityReward": 0.0,
        "rankPenalty": 0.0,
        "tailRiskPenalty": 10.0,
        "objectiveScore": 100.0,
    }
    challenger = supervisor_summary_for_config(
        FrequencyRankerConfig(frequency_weight=0.35),
        objective_score=99.0,
    )
    challenger["reward"] = {
        "hitReward": 0.0,
        "baselineUniqueReward": 111.0,
        "baselineOverlapPenalty": 0.0,
        "red5Reward": 0.0,
        "rankQualityReward": 0.0,
        "rankPenalty": 0.0,
        "tailRiskPenalty": 12.0,
        "objectiveScore": 99.0,
    }

    diagnostic = supervisor.objective_component_counterfactual([challenger, baseline])

    assert supervisor.sort_key(baseline) > supervisor.sort_key(challenger)
    assert diagnostic["status"] == "measured"
    assert diagnostic["component"] == "tail_risk_penalty"
    assert diagnostic["production_top_config_hash"] == supervisor.summary_config_hash(baseline)
    assert diagnostic["counterfactual_top_config_hash"] == supervisor.summary_config_hash(challenger)
    assert diagnostic["counterfactual_top_changed"] is True
    assert diagnostic["challenger_flip_count"] == 1
    assert diagnostic["baseline_retained_count"] == 0
    assert diagnostic["comparisons"] == [
        {
            "config_hash": supervisor.summary_config_hash(challenger),
            "production_objective_gap": 1.0,
            "component_delta": 2.0,
            "counterfactual_objective_gap": -1.0,
            "counterfactual_relation": "challenger_wins",
        }
    ]
    assert diagnostic["selection_changed"] is False
    assert diagnostic["selection_uses_frozen_validation"] is False
    assert baseline["reward"]["objectiveScore"] == 100.0
    assert challenger["reward"]["objectiveScore"] == 99.0


def test_recent_round_self_diagnostics_reads_compact_round_memory():
    diagnostic = {"synthesis": {"status": "caution"}}
    rounds = [
        {"prefilter": {"self_diagnostics": diagnostic}},
        {"prefilter": {}},
        {"prefilter": {"self_diagnostics": {"synthesis": {"status": "noise_risk"}}}},
    ]

    recent = supervisor.recent_round_self_diagnostics(rounds)

    assert recent == [
        diagnostic,
        {"synthesis": {"status": "noise_risk"}},
    ]


def test_recover_strategy_memory_diagnostics_keeps_cross_run_chronology_and_scope():
    oldest = {"protocol": supervisor.SELF_DIAGNOSTICS_PROTOCOL, "marker": "oldest"}
    newest = {"protocol": supervisor.SELF_DIAGNOSTICS_PROTOCOL, "marker": "newest"}
    records = [
        {
            "run_id": "current-run",
            "round_index": 2,
            "prefilter": {"self_diagnostics": newest},
        },
        {
            "run_id": "prior-b",
            "round_index": 3,
            "prefilter": {"self_diagnostics": newest},
        },
        {
            "run_id": "prior-b",
            "round_index": 2,
            "prefilter": {"self_diagnostics": {"protocol": "legacy"}},
        },
        {
            "run_id": "prior-a",
            "round_index": 8,
            "prefilter": {"self_diagnostics": oldest},
        },
    ]

    diagnostics, metadata = supervisor.recover_strategy_memory_diagnostics(
        records,
        current_run_id="current-run",
        limit=2,
    )

    assert diagnostics == [oldest, newest]
    assert metadata["record_count"] == 2
    assert metadata["source_run_ids"] == ["prior-a", "prior-b"]
    assert metadata["oldest_round"] == {"run_id": "prior-a", "round_index": 8}
    assert metadata["latest_round"] == {"run_id": "prior-b", "round_index": 3}
    assert metadata["selection_changed"] is False
    assert metadata["selection_uses_frozen_validation"] is False


def test_candidate_budget_reserves_explicit_weight_kdj_bucket():
    budget = candidate_budget(20, weight_kdj_budget_share=0.15)

    assert budget["weight_kdj"] == 3
    assert sum(budget.values()) == 20
    assert sum(value for name, value in budget.items() if name != "weight_kdj") == 17


def test_candidate_budget_reserves_ridge_without_squeezing_weight_kdj():
    budget = candidate_budget(20, weight_kdj_budget_share=0.15, ridge_kdj_budget_share=0.08)

    assert budget["weight_kdj"] == 3
    assert budget["ridge_kdj"] == 2
    assert sum(value for name, value in budget.items() if name not in {"weight_kdj", "ridge_kdj"}) == 15
    assert sum(budget.values()) == 20


def test_candidate_budget_reserves_neural_without_squeezing_other_advisors():
    budget = candidate_budget(
        20,
        weight_kdj_budget_share=0.15,
        ridge_kdj_budget_share=0.08,
        neural_kdj_budget_share=0.05,
    )

    assert budget["weight_kdj"] == 3
    assert budget["ridge_kdj"] == 2
    assert budget["neural_kdj"] == 1
    assert sum(value for name, value in budget.items() if name not in {"weight_kdj", "ridge_kdj", "neural_kdj"}) == 14
    assert sum(budget.values()) == 20


def test_candidate_budget_neural_density_experiment_returns_one_slot_to_normal_search():
    common = {
        "recency_canary_budget_share": 0.12,
        "weight_kdj_budget_share": 0.22,
        "ridge_kdj_budget_share": 0.08,
    }
    baseline = candidate_budget(28, neural_kdj_budget_share=0.10, **common)
    alternative = candidate_budget(28, neural_kdj_budget_share=0.07, **common)
    advisor_names = {"recency_canary", "weight_kdj", "ridge_kdj", "neural_kdj"}

    assert baseline["neural_kdj"] == 3
    assert alternative["neural_kdj"] == 2
    assert sum(baseline.values()) == 28
    assert sum(alternative.values()) == 28
    assert sum(value for name, value in alternative.items() if name not in advisor_names) == (
        sum(value for name, value in baseline.items() if name not in advisor_names) + 1
    )


def test_refill_candidate_configs_fills_reserved_source_deduplication_gap():
    first = FrequencyRankerConfig(frequency_weight=0.31)
    second = FrequencyRankerConfig(frequency_weight=0.32)
    fallback = FrequencyRankerConfig(frequency_weight=0.33)

    filled = refill_candidate_configs(
        (first, second),
        (second, fallback),
        max_configs=3,
    )

    assert filled == (first, second, fallback)


def test_candidate_budget_reserves_bounded_target_weight_inversion_bucket():
    budget = candidate_budget(
        20,
        weight_kdj_budget_share=0.15,
        ridge_kdj_budget_share=0.08,
        neural_kdj_budget_share=0.05,
        target_weight_inversion_budget_share=0.20,
        target_weight_inversion_available=8,
    )

    assert budget["weight_kdj"] == 3
    assert budget["ridge_kdj"] == 2
    assert budget["neural_kdj"] == 1
    assert budget["target_weight_inversion"] == 4
    assert sum(budget.values()) == 20


def test_candidate_budget_allows_larger_target_weight_inversion_bucket_when_configured():
    budget = candidate_budget(
        40,
        target_weight_inversion_budget_share=0.30,
        target_weight_inversion_available=12,
        target_weight_inversion_max_candidates=12,
    )

    assert budget["target_weight_inversion"] == 12
    assert sum(budget.values()) == 40


def test_candidate_budget_skips_target_weight_inversion_bucket_without_candidates():
    budget = candidate_budget(
        20,
        target_weight_inversion_budget_share=0.20,
        target_weight_inversion_available=0,
    )

    assert budget["target_weight_inversion"] == 0
    assert sum(budget.values()) == 20


def test_target_weight_inversion_guardrail_disables_stale_no_lift_budget():
    latest = {
        "status": "ready",
        "advice": [
            {
                "decision": "selected",
                "validation_metric": 0.03,
                "baseline_metric": 0.03,
            }
        ],
    }

    guardrail = target_weight_inversion_budget_guardrail(0.30, latest=latest, stagnation_rounds=227)

    assert guardrail["active"] is True
    assert guardrail["effective_share"] == 0.0
    assert guardrail["reason"] == "stale_no_validation_lift"


def test_target_weight_inversion_guardrail_keeps_budget_with_lift_or_early_rounds():
    latest = {
        "status": "ready",
        "advice": [
            {
                "decision": "selected",
                "validation_metric": 0.07,
                "baseline_metric": 0.03,
            }
        ],
    }

    lifted = target_weight_inversion_budget_guardrail(0.30, latest=latest, stagnation_rounds=227)
    early = target_weight_inversion_budget_guardrail(0.30, latest=None, stagnation_rounds=12)

    assert lifted["active"] is False
    assert lifted["effective_share"] == 0.30
    assert early["active"] is False
    assert early["effective_share"] == 0.30


def test_rank_homogeneity_guardrail_detects_repeated_rank_signatures():
    rounds = [
        {"prefilter": {"round_best_rank_signature_hash": f"sig-{index % 3}"}}
        for index in range(12)
    ]

    guardrail = rank_homogeneity_guardrail(rounds, stagnation_rounds=16)

    assert guardrail["active"] is True
    assert guardrail["reason"] == "stale_rank_signature_cycle"
    assert guardrail["trigger_mode"] == "low_diversity_cycle"
    assert guardrail["stagnation_threshold"] == 16
    assert guardrail["window"] == 12
    assert guardrail["unique_signature_count"] == 3
    assert guardrail["max_unique_signatures"] == 4
    assert guardrail["fallback_unique_signature_count"] == 3


def test_rank_homogeneity_guardrail_detects_four_exact_repeats_early():
    rounds = [
        {"prefilter": {"round_best_rank_signature_hash": "same-signature"}}
        for _ in range(4)
    ]

    guardrail = rank_homogeneity_guardrail(rounds, stagnation_rounds=4)

    assert guardrail["active"] is True
    assert guardrail["reason"] == "stale_rank_signature_cycle"
    assert guardrail["trigger_mode"] == "exact_repeat"
    assert guardrail["stagnation_threshold"] == 4
    assert guardrail["window"] == 4
    assert guardrail["unique_signature_count"] == 1


def test_rank_homogeneity_guardrail_waits_for_enough_stagnation_and_window():
    early = rank_homogeneity_guardrail(
        [{"prefilter": {"round_best_rank_signature_hash": "sig"}} for _ in range(4)],
        stagnation_rounds=3,
    )
    short = rank_homogeneity_guardrail(
        [{"prefilter": {"round_best_rank_signature_hash": "sig"}} for _ in range(3)],
        stagnation_rounds=4,
    )

    assert early["active"] is False
    assert early["reason"] == "below_stagnation_threshold"
    assert short["active"] is False
    assert short["reason"] == "insufficient_signature_window"


def test_rank_homogeneity_guardrail_keeps_searching_when_recent_signatures_vary():
    rounds = [
        {"prefilter": {"round_best_rank_signature_hash": signature}}
        for signature in ("sig-a", "sig-a", "sig-b", "sig-a")
    ]

    guardrail = rank_homogeneity_guardrail(rounds, stagnation_rounds=4)

    assert guardrail["active"] is False
    assert guardrail["reason"] == "rank_signatures_still_diverse"
    assert guardrail["unique_signature_count"] == 2


def test_rank_homogeneity_guardrail_requires_four_consecutive_observed_signatures():
    rounds = [
        {"prefilter": {"round_best_rank_signature_hash": "same-signature"}},
        {"prefilter": {"round_best_rank_signature_hash": "same-signature"}},
        {"prefilter": {"round_best_rank_signature_hash": "same-signature"}},
        {"prefilter": {}},
        {"prefilter": {"round_best_rank_signature_hash": "same-signature"}},
    ]

    guardrail = rank_homogeneity_guardrail(rounds, stagnation_rounds=5)

    assert guardrail["active"] is False
    assert guardrail["reason"] == "insufficient_signature_window"
    assert guardrail["observed"] == 3


def test_stagnation_restart_candidate_configs_are_bounded_and_distant():
    base = FrequencyRankerConfig(
        structural_weight=0.30,
        frequency_weight=0.30,
        omission_weight=0.20,
        tail_distribution_weight=0.10,
    )

    configs = stagnation_restart_candidate_configs(
        base,
        max_configs=8,
        round_index=40,
        stagnation_rounds=40,
    )

    assert len(configs) == 8
    assert len({config_hash(config) for config in configs}) == 8
    assert all(0 <= config.structural_weight <= 1.25 for config in configs)
    assert all(-0.30 <= config.tail_distribution_weight <= 0.30 for config in configs)
    assert all(
        any(getattr(config, field) != getattr(base, field) for field in supervisor.RESTART_CONTEXT_FIELDS)
        for config in configs[:5]
    )
    assert all(
        getattr(config, field) == getattr(base, field)
        for config in configs[:5]
        for field in supervisor.CONTEXT_FIELDS
        if field not in supervisor.RESTART_CONTEXT_FIELDS
    )
    assert any(config.frequency_weight >= 1.0 for config in configs)
    assert any(config.omission_weight >= 1.0 for config in configs)


def test_stagnation_restart_candidate_configs_skip_current_extreme_base():
    base = FrequencyRankerConfig(
        structural_weight=0.05,
        frequency_weight=1.15,
        omission_weight=0.05,
    )

    configs = stagnation_restart_candidate_configs(
        base,
        max_configs=5,
        round_index=29,
        stagnation_rounds=28,
    )

    assert len(configs) == 5
    assert config_hash(base) not in {config_hash(config) for config in configs}
    assert all(
        any(getattr(config, field) != getattr(base, field) for field in supervisor.RESTART_CONTEXT_FIELDS)
        for config in configs
    )


def test_stagnation_restart_candidate_configs_rotate_disjoint_batches():
    base = FrequencyRankerConfig(
        structural_weight=0.70,
        frequency_weight=0.70,
        omission_weight=0.14,
    )

    first = stagnation_restart_candidate_configs(
        base,
        max_configs=5,
        round_index=5,
        stagnation_rounds=4,
        catalog_offset=0,
    )
    second = stagnation_restart_candidate_configs(
        base,
        max_configs=5,
        round_index=6,
        stagnation_rounds=5,
        catalog_offset=5,
    )
    repeated_second = stagnation_restart_candidate_configs(
        base,
        max_configs=5,
        round_index=6,
        stagnation_rounds=5,
        catalog_offset=5,
    )

    first_hashes = {config_hash(config) for config in first}
    second_hashes = {config_hash(config) for config in second}
    assert len(first_hashes) == len(second_hashes) == 5
    assert first_hashes.isdisjoint(second_hashes)
    assert [config_hash(config) for config in second] == [
        config_hash(config) for config in repeated_second
    ]


def test_stagnation_restart_candidates_replace_same_history_exact_repeats():
    base = FrequencyRankerConfig(
        structural_weight=0.70,
        frequency_weight=0.70,
        omission_weight=0.14,
    )
    repeated = stagnation_restart_candidate_configs(
        base,
        max_configs=5,
        round_index=5,
        stagnation_rounds=4,
        catalog_offset=0,
    )
    repeated_hashes = tuple(config_hash(config) for config in repeated)

    replacements = stagnation_restart_candidate_configs(
        base,
        max_configs=5,
        round_index=5,
        stagnation_rounds=4,
        catalog_offset=0,
        excluded_config_hashes=repeated_hashes,
    )
    deterministic_replacements = stagnation_restart_candidate_configs(
        base,
        max_configs=5,
        round_index=5,
        stagnation_rounds=4,
        catalog_offset=0,
        excluded_config_hashes=repeated_hashes,
    )

    replacement_hashes = tuple(config_hash(config) for config in replacements)
    assert len(replacement_hashes) == 5
    assert set(replacement_hashes).isdisjoint(repeated_hashes)
    assert replacement_hashes == tuple(
        config_hash(config) for config in deterministic_replacements
    )


def test_stagnation_restart_candidates_use_deterministic_fallback_after_catalog_exhaustion():
    base = FrequencyRankerConfig(
        structural_weight=0.70,
        frequency_weight=0.70,
        omission_weight=0.14,
    )
    catalog = stagnation_restart_candidate_configs(
        base,
        max_configs=30,
        round_index=12,
        stagnation_rounds=11,
        catalog_offset=0,
    )
    catalog_hashes = tuple(config_hash(config) for config in catalog)

    fallback = stagnation_restart_candidate_configs(
        base,
        max_configs=5,
        round_index=12,
        stagnation_rounds=11,
        catalog_offset=0,
        excluded_config_hashes=catalog_hashes,
    )
    repeated_fallback = stagnation_restart_candidate_configs(
        base,
        max_configs=5,
        round_index=12,
        stagnation_rounds=11,
        catalog_offset=0,
        excluded_config_hashes=catalog_hashes,
    )

    fallback_hashes = tuple(config_hash(config) for config in fallback)
    assert len(catalog_hashes) == 30
    assert len(fallback_hashes) == 5
    assert set(fallback_hashes).isdisjoint(catalog_hashes)
    assert fallback_hashes == tuple(
        config_hash(config) for config in repeated_fallback
    )


def test_historical_candidate_source_hashes_are_bounded_and_deduplicated():
    records = [
        {
            "prefilter": {
                "source_survival": {
                    "stagnation_restart": {"hashes": ["hash-a", "hash-b"]}
                }
            }
        },
        {
            "prefilter": {
                "source_survival": {
                    "stagnation_restart": {"hashes": ["hash-b", "hash-c"]}
                }
            }
        },
        {"prefilter": {"source_survival": {"stagnation_restart": None}}},
    ]

    assert historical_candidate_source_hashes(
        records,
        source="stagnation_restart",
        limit=2,
    ) == ("hash-a", "hash-b")
    assert historical_candidate_source_hashes(
        records,
        source="stagnation_restart",
        limit=0,
    ) == ()


def test_stagnation_restart_catalog_position_uses_active_trigger_threshold():
    early = stagnation_restart_catalog_position(
        {
            "active": True,
            "stagnation_rounds": 5,
            "stagnation_threshold": 4,
        },
        budget=5,
    )
    fallback = stagnation_restart_catalog_position(
        {
            "active": True,
            "stagnation_rounds": 16,
            "stagnation_threshold": 16,
        },
        budget=5,
    )
    inactive = stagnation_restart_catalog_position(
        {"active": False, "stagnation_rounds": 20, "stagnation_threshold": 4},
        budget=5,
    )

    assert early == {"batch_index": 1, "catalog_offset": 5}
    assert fallback == {"batch_index": 0, "catalog_offset": 0}
    assert inactive == {"batch_index": 0, "catalog_offset": 0}


def test_reserved_weight_kdj_candidates_survive_full_normal_round():
    normal = tuple(FrequencyRankerConfig(frequency_weight=round(0.01 * index, 4)) for index in range(20))
    kdj = (
        FrequencyRankerConfig(frequency_weight=0.37),
        FrequencyRankerConfig(sum_tail_weight=-0.03),
        FrequencyRankerConfig(weekday_trend_weight=0.04),
    )

    merged = merge_reserved_candidate_configs(normal, kdj, max_configs=20, reserved_budget=3)

    assert len(merged) == 20
    assert all(config in merged for config in kdj)
    assert len([config for config in merged if config in normal]) == 17


def test_reserved_ridge_candidates_do_not_trim_existing_kdj_bucket():
    normal = tuple(FrequencyRankerConfig(frequency_weight=round(0.01 * index, 4)) for index in range(15))
    kdj = (
        FrequencyRankerConfig(frequency_weight=0.37),
        FrequencyRankerConfig(sum_tail_weight=-0.03),
        FrequencyRankerConfig(weekday_trend_weight=0.04),
    )
    ridge = (
        FrequencyRankerConfig(frequency_weight=0.41),
        FrequencyRankerConfig(sum_tail_weight=0.07),
    )

    with_kdj = merge_reserved_candidate_configs(normal, kdj, max_configs=18, reserved_budget=3)
    merged = merge_reserved_candidate_configs(with_kdj, ridge, max_configs=20, reserved_budget=2)

    assert len(merged) == 20
    assert all(config in merged for config in kdj)
    assert all(config in merged for config in ridge)
    assert len([config for config in merged if config in normal]) == 15


def test_reserved_neural_candidates_do_not_trim_existing_advisor_buckets():
    normal = tuple(FrequencyRankerConfig(frequency_weight=round(0.01 * index, 4)) for index in range(14))
    kdj = (
        FrequencyRankerConfig(frequency_weight=0.37),
        FrequencyRankerConfig(sum_tail_weight=-0.03),
        FrequencyRankerConfig(weekday_trend_weight=0.04),
    )
    ridge = (
        FrequencyRankerConfig(frequency_weight=0.41),
        FrequencyRankerConfig(sum_tail_weight=0.07),
    )
    neural = (FrequencyRankerConfig(omission_weight=0.42),)

    with_kdj = merge_reserved_candidate_configs(normal, kdj, max_configs=17, reserved_budget=3)
    with_ridge = merge_reserved_candidate_configs(with_kdj, ridge, max_configs=19, reserved_budget=2)
    merged = merge_reserved_candidate_configs(with_ridge, neural, max_configs=20, reserved_budget=1)

    assert len(merged) == 20
    assert all(config in merged for config in kdj)
    assert all(config in merged for config in ridge)
    assert all(config in merged for config in neural)
    assert len([config for config in merged if config in normal]) == 14


def test_reserved_target_weight_inversion_candidates_do_not_trim_existing_advisor_buckets():
    normal = tuple(FrequencyRankerConfig(frequency_weight=round(0.01 * index, 4)) for index in range(10))
    kdj = (
        FrequencyRankerConfig(frequency_weight=0.37),
        FrequencyRankerConfig(sum_tail_weight=-0.03),
        FrequencyRankerConfig(weekday_trend_weight=0.04),
    )
    target_inversion = (
        FrequencyRankerConfig(frequency_weight=0.45),
        FrequencyRankerConfig(omission_weight=0.42),
        FrequencyRankerConfig(sum_tail_weight=0.09),
        FrequencyRankerConfig(stable_range_weight=0.05),
    )

    with_kdj = merge_reserved_candidate_configs(normal, kdj, max_configs=13, reserved_budget=3)
    merged = merge_reserved_candidate_configs(with_kdj, target_inversion, max_configs=17, reserved_budget=4)

    assert len(merged) == 17
    assert all(config in merged for config in kdj)
    assert all(config in merged for config in target_inversion)
    assert len([config for config in merged if config in normal]) == 10


def test_candidate_source_survival_tracks_prefilter_top5_and_round_best():
    normal = (FrequencyRankerConfig(frequency_weight=0.31), FrequencyRankerConfig(frequency_weight=0.32))
    kdj = (FrequencyRankerConfig(omission_weight=0.41),)
    twi = (FrequencyRankerConfig(sum_tail_weight=0.07),)
    top_results = [
        {"config_hash": config_hash(kdj[0])},
        {"config_hash": config_hash(normal[0])},
    ]

    survival = candidate_source_survival(
        {"normal": normal, "weight_kdj": kdj, "target_weight_inversion": twi},
        refined_configs=(normal[0], kdj[0]),
        full_eval_top_results=top_results,
        round_best=top_results[0],
    )

    assert survival["normal"]["generated"] == 2
    assert survival["normal"]["prefilter_selected"] == 1
    assert survival["normal"]["full_eval_top5"] == 1
    assert survival["normal"]["round_best"] is False
    assert survival["weight_kdj"]["prefilter_selected"] == 1
    assert survival["weight_kdj"]["round_best"] is True
    assert survival["target_weight_inversion"]["prefilter_selected"] == 0


def test_source_frontier_diagnostics_tracks_best_non_normal_frozen_frontier():
    normal = FrequencyRankerConfig(frequency_weight=0.31)
    recency = FrequencyRankerConfig(short_hot_frequency_weight=0.18)
    normal_summary = attach_test_frozen_validation(
        supervisor_summary_for_config(normal, objective_score=2200.0),
        top_10000_hits=0,
        median_rank=800_000,
        objective_score=0.0,
    )
    recency_summary = attach_test_frozen_validation(
        supervisor_summary_for_config(recency, objective_score=2100.0),
        top_10000_hits=1,
        median_rank=650_000,
        objective_score=3.0,
    )

    diagnostics = source_frontier_diagnostics(
        summaries=[normal_summary, recency_summary],
        source_configs={"normal": (normal,), "recency_canary": (recency,)},
        prior_best_summary=normal_summary,
        round_best=normal_summary,
    )

    assert diagnostics["sources"]["normal"]["generated"] == 1
    assert diagnostics["sources"]["recency_canary"]["full_eval_count"] == 1
    assert diagnostics["sources"]["recency_canary"]["best"]["frozen_top_10000_hits"] == 1
    assert diagnostics["best_non_normal"]["source"] == "recency_canary"
    assert diagnostics["best_non_normal_primary"]["source"] == "recency_canary"
    assert diagnostics["best_non_normal"]["config_hash"] == config_hash(recency)


def test_source_frontier_diagnostics_marks_secondary_without_primary_lift():
    normal = FrequencyRankerConfig(frequency_weight=0.31)
    weight_kdj = FrequencyRankerConfig(sum_tail_weight=0.08)
    normal_summary = attach_test_frozen_validation(
        supervisor_summary_for_config(normal, objective_score=2200.0),
        top_10000_hits=0,
        red5_top_10000_hits=3,
        median_rank=800_000,
        objective_score=0.0,
    )
    weight_summary = attach_test_frozen_validation(
        supervisor_summary_for_config(weight_kdj, objective_score=2100.0),
        top_10000_hits=0,
        red5_top_10000_hits=5,
        median_rank=650_000,
        objective_score=3.0,
    )

    diagnostics = source_frontier_diagnostics(
        summaries=[normal_summary, weight_summary],
        source_configs={"normal": (normal,), "weight_kdj": (weight_kdj,)},
        prior_best_summary=normal_summary,
        round_best=normal_summary,
    )

    assert diagnostics["best_non_normal_primary"] is None
    assert diagnostics["best_non_normal_secondary"]["source"] == "weight_kdj"
    assert diagnostics["sources"]["weight_kdj"]["primary_score"] == [0, 0, 0]


def test_source_frontier_champion_waits_for_stagnation_threshold():
    normal = FrequencyRankerConfig()
    recency = FrequencyRankerConfig(short_hot_frequency_weight=0.18)
    normal_summary = attach_test_frozen_validation(supervisor_summary_for_config(normal), top_10000_hits=0)
    recency_summary = attach_test_frozen_validation(supervisor_summary_for_config(recency), top_10000_hits=1)

    champion, metadata = select_source_frontier_champion(
        summaries=[normal_summary, recency_summary],
        source_configs={"normal": (normal,), "recency_canary": (recency,)},
        round_best=normal_summary,
        prior_best_summary=normal_summary,
        stagnation_rounds=supervisor.SOURCE_FRONTIER_STAGNATION_THRESHOLD - 1,
    )

    assert champion is None
    assert metadata["active"] is False
    assert metadata["reason"] == "below_threshold"


def test_source_frontier_champion_selects_non_normal_frozen_lift():
    normal = FrequencyRankerConfig()
    recency = FrequencyRankerConfig(short_hot_frequency_weight=0.18, long_omission_cooldown_weight=0.12)
    normal_summary = attach_test_frozen_validation(
        supervisor_summary_for_config(normal, target_ranks=[10_000, 600_000]),
        top_10000_hits=0,
        median_rank=800_000,
        objective_score=0.0,
    )
    recency_summary = attach_test_frozen_validation(
        supervisor_summary_for_config(recency, target_ranks=[9_000, 590_000], objective_score=100.0),
        top_10000_hits=1,
        median_rank=650_000,
        objective_score=3.0,
    )

    champion, metadata = select_source_frontier_champion(
        summaries=[normal_summary, recency_summary],
        source_configs={"normal": (normal,), "recency_canary": (recency,)},
        round_best=normal_summary,
        prior_best_summary=normal_summary,
        stagnation_rounds=supervisor.SOURCE_FRONTIER_STAGNATION_THRESHOLD,
    )

    assert champion is recency_summary
    assert metadata["active"] is True
    assert metadata["source"] == "recency_canary"
    assert metadata["full_eval_rank"] == 2
    assert metadata["rank_vector_changed"] is True
    assert metadata["changed_target_count"] == 2
    assert metadata["reason"] == "source_frontier_primary_hit_lift"
    assert metadata["candidate_primary_score"] == [0, 0, 1]


def test_source_frontier_champion_rejects_non_normal_without_frozen_lift():
    normal = FrequencyRankerConfig()
    ridge = FrequencyRankerConfig(frequency_weight=0.45)
    normal_summary = attach_test_frozen_validation(
        supervisor_summary_for_config(normal, objective_score=2200.0),
        top_10000_hits=1,
        median_rank=650_000,
        objective_score=3.0,
    )
    ridge_summary = attach_test_frozen_validation(
        supervisor_summary_for_config(ridge, objective_score=2100.0),
        top_10000_hits=0,
        median_rank=900_000,
        objective_score=0.0,
    )

    champion, metadata = select_source_frontier_champion(
        summaries=[normal_summary, ridge_summary],
        source_configs={"normal": (normal,), "ridge_kdj": (ridge,)},
        round_best=normal_summary,
        prior_best_summary=normal_summary,
        stagnation_rounds=supervisor.SOURCE_FRONTIER_STAGNATION_THRESHOLD,
    )

    assert champion is None
    assert metadata["active"] is False
    assert metadata["reason"] == "no_non_normal_primary_frontier_lift"


def test_source_frontier_champion_rejects_secondary_only_lift():
    normal = FrequencyRankerConfig()
    weight_kdj = FrequencyRankerConfig(sum_tail_weight=0.08)
    normal_summary = attach_test_frozen_validation(
        supervisor_summary_for_config(normal, objective_score=2200.0),
        top_10000_hits=0,
        red5_top_10000_hits=3,
        median_rank=800_000,
        objective_score=0.0,
    )
    weight_summary = attach_test_frozen_validation(
        supervisor_summary_for_config(weight_kdj, objective_score=2100.0),
        top_10000_hits=0,
        red5_top_10000_hits=5,
        median_rank=650_000,
        objective_score=3.0,
    )

    champion, metadata = select_source_frontier_champion(
        summaries=[normal_summary, weight_summary],
        source_configs={"normal": (normal,), "weight_kdj": (weight_kdj,)},
        round_best=normal_summary,
        prior_best_summary=normal_summary,
        stagnation_rounds=supervisor.SOURCE_FRONTIER_STAGNATION_THRESHOLD,
    )

    assert champion is None
    assert metadata["reason"] == "no_non_normal_primary_frontier_lift"
    assert metadata["secondary_candidate_available"] is True
    assert metadata["secondary_candidate_source"] == "weight_kdj"


def test_stagnation_exploration_champion_waits_for_threshold():
    normal = FrequencyRankerConfig()
    target_inversion = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    normal_summary = supervisor_summary_for_config(normal, objective_score=2200.0)
    target_summary = supervisor_summary_for_config(target_inversion, objective_score=2190.0)

    champion, metadata = select_stagnation_exploration_champion(
        summaries=[normal_summary, target_summary],
        source_configs={"normal": (normal,), "target_weight_inversion": (target_inversion,)},
        round_best=normal_summary,
        stagnation_rounds=15,
    )

    assert champion is None
    assert metadata["active"] is False
    assert metadata["reason"] == "below_threshold"


def test_stagnation_exploration_champion_selects_top_exploratory_candidate():
    normal = FrequencyRankerConfig()
    ridge = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    target_inversion = FrequencyRankerConfig(sum_tail_weight=0.07)
    normal_summary = supervisor_summary_for_config(normal, objective_score=2200.0)
    ridge_summary = supervisor_summary_for_config(ridge, objective_score=2195.0)
    target_summary = supervisor_summary_for_config(target_inversion, objective_score=2190.0)

    champion, metadata = select_stagnation_exploration_champion(
        summaries=[normal_summary, ridge_summary, target_summary],
        source_configs={
            "normal": (normal,),
            "ridge_kdj": (ridge,),
            "target_weight_inversion": (target_inversion,),
        },
        round_best=normal_summary,
        stagnation_rounds=16,
    )

    assert champion is ridge_summary
    assert metadata["active"] is True
    assert metadata["source"] == "ridge_kdj"
    assert metadata["top_rank"] == 2
    assert metadata["reason"] == "stagnation_top_eval_exploration"


def test_probability_calibration_champion_guides_stagnated_search():
    round_best_config = FrequencyRankerConfig(frequency_weight=0.30)
    probability_config = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    round_best = supervisor_summary_for_config(
        round_best_config,
        top_100_hits=1,
        top_1000_hits=1,
        top_10000_hits=3,
        target_ranks=[50, 2_000, 40_000],
        objective_score=2200.0,
    )
    probability_candidate = supervisor_summary_for_config(
        probability_config,
        top_100_hits=1,
        top_1000_hits=2,
        top_10000_hits=3,
        target_ranks=[50, 500, 40_000],
        objective_score=2100.0,
    )
    for summary in (round_best, probability_candidate):
        summary["rank_quality"]["top_50000_hits"] = 3
        summary["probability_calibration"] = probability_calibration_diagnostics(summary, universe_size=1_000_000)

    champion, metadata = select_probability_calibration_champion(
        summaries=[round_best, probability_candidate],
        source_configs={"normal": (round_best_config,), "ridge_kdj": (probability_config,)},
        round_best=round_best,
        prior_best_summary=round_best,
        stagnation_rounds=16,
    )

    assert probability_calibration_score(probability_candidate) > probability_calibration_score(round_best)
    assert champion is probability_candidate
    assert metadata["active"] is True
    assert metadata["source"] == "ridge_kdj"
    assert metadata["full_eval_rank"] == 2
    assert metadata["reason"] == "stagnation_probability_calibration_better"


def test_probability_calibration_champion_requires_primary_lift_after_stale_stagnation():
    round_best_config = FrequencyRankerConfig(frequency_weight=0.30)
    probability_config = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    round_best = attach_test_frozen_validation(
        supervisor_summary_for_config(
            round_best_config,
            top_100_hits=1,
            top_1000_hits=1,
            top_10000_hits=3,
            target_ranks=[50, 2_000, 40_000],
            objective_score=2200.0,
        ),
        top_10000_hits=1,
    )
    probability_candidate = attach_test_frozen_validation(
        supervisor_summary_for_config(
            probability_config,
            top_100_hits=1,
            top_1000_hits=2,
            top_10000_hits=3,
            target_ranks=[50, 500, 40_000],
            objective_score=2100.0,
        ),
        top_10000_hits=1,
    )
    for summary in (round_best, probability_candidate):
        summary["rank_quality"]["top_50000_hits"] = 3
        summary["probability_calibration"] = probability_calibration_diagnostics(summary, universe_size=1_000_000)

    champion, metadata = select_probability_calibration_champion(
        summaries=[round_best, probability_candidate],
        source_configs={"normal": (round_best_config,), "ridge_kdj": (probability_config,)},
        round_best=round_best,
        prior_best_summary=round_best,
        stagnation_rounds=supervisor.PROBABILITY_PRIMARY_GATE_STAGNATION_THRESHOLD,
    )

    assert probability_calibration_score(probability_candidate) > probability_calibration_score(round_best)
    assert champion is None
    assert metadata["primary_gate_active"] is True
    assert metadata["reason"] == "probability_primary_gate_no_lift"
    assert metadata["blocked_candidate_config_hash"] == config_hash(probability_config)
    assert metadata["blocked_candidate_primary_score"] == [0, 0, 1]


def test_probability_calibration_champion_primary_gate_can_be_forced_by_overfit_guardrail():
    round_best_config = FrequencyRankerConfig(frequency_weight=0.30)
    probability_config = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    round_best = attach_test_frozen_validation(
        supervisor_summary_for_config(
            round_best_config,
            top_100_hits=3,
            top_1000_hits=3,
            top_10000_hits=3,
            target_ranks=[50, 90, 99, 40_000],
            objective_score=2200.0,
        ),
        top_100_hits=0,
        top_1000_hits=0,
        top_10000_hits=0,
    )
    probability_candidate = attach_test_frozen_validation(
        supervisor_summary_for_config(
            probability_config,
            top_100_hits=3,
            top_1000_hits=3,
            top_10000_hits=4,
            target_ranks=[50, 90, 99, 5_000],
            objective_score=2100.0,
        ),
        top_100_hits=0,
        top_1000_hits=0,
        top_10000_hits=0,
    )
    for summary in (round_best, probability_candidate):
        summary["rank_quality"]["top_50000_hits"] = 4
        summary["probability_calibration"] = probability_calibration_diagnostics(summary, universe_size=1_000_000)

    champion, metadata = select_probability_calibration_champion(
        summaries=[round_best, probability_candidate],
        source_configs={"normal": (round_best_config,), "ridge_kdj": (probability_config,)},
        round_best=round_best,
        prior_best_summary=round_best,
        stagnation_rounds=supervisor.STAGNATION_THRESHOLD,
        force_primary_gate=True,
    )

    assert probability_calibration_score(probability_candidate) > probability_calibration_score(round_best)
    assert champion is None
    assert metadata["primary_gate_active"] is True
    assert metadata["primary_gate_forced"] is True
    assert metadata["reason"] == "probability_primary_gate_no_lift"
    assert metadata["blocked_candidate_config_hash"] == config_hash(probability_config)
    assert metadata["blocked_candidate_primary_score"] == [0, 0, 0]


def test_probability_calibration_champion_allows_primary_lift_after_stale_stagnation():
    round_best_config = FrequencyRankerConfig(frequency_weight=0.30)
    probability_config = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    round_best = attach_test_frozen_validation(
        supervisor_summary_for_config(
            round_best_config,
            top_100_hits=1,
            top_1000_hits=1,
            top_10000_hits=3,
            target_ranks=[50, 2_000, 40_000],
            objective_score=2200.0,
        ),
        top_10000_hits=1,
    )
    probability_candidate = attach_test_frozen_validation(
        supervisor_summary_for_config(
            probability_config,
            top_100_hits=1,
            top_1000_hits=2,
            top_10000_hits=3,
            target_ranks=[50, 500, 40_000],
            objective_score=2100.0,
        ),
        top_10000_hits=2,
    )
    for summary in (round_best, probability_candidate):
        summary["rank_quality"]["top_50000_hits"] = 3
        summary["probability_calibration"] = probability_calibration_diagnostics(summary, universe_size=1_000_000)

    champion, metadata = select_probability_calibration_champion(
        summaries=[round_best, probability_candidate],
        source_configs={"normal": (round_best_config,), "ridge_kdj": (probability_config,)},
        round_best=round_best,
        prior_best_summary=round_best,
        stagnation_rounds=supervisor.PROBABILITY_PRIMARY_GATE_STAGNATION_THRESHOLD,
    )

    assert champion is probability_candidate
    assert metadata["primary_gate_active"] is True
    assert metadata["candidate_primary_score"] == [0, 0, 2]
    assert metadata["reason"] == "stagnation_probability_calibration_better"


def test_probability_focus_search_base_can_hold_probability_candidate():
    current_config = FrequencyRankerConfig(frequency_weight=0.30)
    focus_config = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    focus_summary = supervisor_summary_for_config(
        focus_config,
        top_100_hits=1,
        top_1000_hits=2,
        top_10000_hits=3,
        objective_score=2100.0,
    )

    next_base, metadata = select_probability_focus_search_base(
        current_base=current_config,
        focus_summary=focus_summary,
        focus_info={
            "active": True,
            "source": "ridge_kdj",
            "reason": "refreshed_from_probability_champion",
            "hold_rounds": 4,
            "remaining_rounds": 4,
            "refreshed": True,
        },
    )

    assert config_hash(next_base) == config_hash(focus_config)
    assert metadata["source"] == "probability_focus"
    assert metadata["focus_source"] == "ridge_kdj"
    assert metadata["changed"] is True
    assert metadata["remaining_rounds"] == 4
    assert metadata["top_1000_hits"] == 2


def test_probability_focus_search_base_can_hold_current_base_for_local_search():
    current_config = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    focus_summary = supervisor_summary_for_config(
        current_config,
        top_100_hits=1,
        top_1000_hits=2,
        top_10000_hits=3,
        objective_score=2100.0,
    )

    next_base, metadata = select_probability_focus_search_base(
        current_base=current_config,
        focus_summary=focus_summary,
        focus_info={
            "active": True,
            "source": "probability_focus",
            "reason": "held_previous_probability_focus",
            "hold_rounds": 4,
            "remaining_rounds": 3,
            "refreshed": False,
        },
    )

    assert config_hash(next_base) == config_hash(current_config)
    assert metadata["source"] == "probability_focus"
    assert metadata["changed"] is False
    assert metadata["selected_config_distance"] == 0.0
    assert metadata["remaining_rounds"] == 3


def test_probability_focus_search_base_obeys_recent_base_cooldown():
    current_config = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    focus_summary = supervisor_summary_for_config(
        current_config,
        top_100_hits=1,
        top_1000_hits=2,
        top_10000_hits=3,
        objective_score=2100.0,
    )

    next_base, metadata = select_probability_focus_search_base(
        current_base=current_config,
        focus_summary=focus_summary,
        focus_info={
            "active": True,
            "source": "probability_focus",
            "reason": "held_previous_probability_focus",
            "hold_rounds": 4,
            "remaining_rounds": 3,
            "refreshed": False,
        },
        recent_search_base_hashes=(config_hash(current_config),),
        min_config_distance=0.08,
    )

    assert next_base is None
    assert metadata["reason"] == "search_base_cooldown"
    assert metadata["selected_config_distance"] == 0.0
    assert metadata["recent_search_base_hashes"] == [config_hash(current_config)]


def test_probability_focus_same_hash_same_score_does_not_refresh_ttl():
    config = FrequencyRankerConfig(frequency_weight=0.45)
    champion_hash = config_hash(config)

    assert should_refresh_probability_focus(
        champion_config=config,
        champion_hash=champion_hash,
        champion_score=(1, 2, 3),
        probability_focus_hash="",
        probability_focus_score=(),
    )
    assert not should_refresh_probability_focus(
        champion_config=config,
        champion_hash=champion_hash,
        champion_score=(1, 2, 3),
        probability_focus_hash=champion_hash,
        probability_focus_score=(1, 2, 3),
    )
    assert should_refresh_probability_focus(
        champion_config=config,
        champion_hash=champion_hash,
        champion_score=(1, 2, 4),
        probability_focus_hash=champion_hash,
        probability_focus_score=(1, 2, 3),
    )


def test_probability_focus_different_hash_same_score_does_not_refresh_ttl():
    config = FrequencyRankerConfig(frequency_weight=0.46)

    assert not should_refresh_probability_focus(
        champion_config=config,
        champion_hash=config_hash(config),
        champion_score=(1, 2, 3),
        probability_focus_hash="older-focus-hash",
        probability_focus_score=(1, 2, 3),
    )


def test_probability_focus_search_base_returns_none_on_rank_signature_cooldown():
    current_config = FrequencyRankerConfig(frequency_weight=0.30)
    focus_config = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    focus_summary = supervisor_summary_for_config(
        focus_config,
        target_ranks=[100, 900, 50_000],
        objective_score=2100.0,
    )
    signature = rank_signature_hash(focus_summary)

    next_base, metadata = select_probability_focus_search_base(
        current_base=current_config,
        focus_summary=focus_summary,
        focus_info={
            "active": True,
            "source": "probability_focus",
            "reason": "refreshed_from_probability_champion",
            "hold_rounds": 4,
            "remaining_rounds": 4,
            "refreshed": True,
        },
        excluded_rank_signature_hashes=(signature,),
    )

    assert next_base is None
    assert metadata["reason"] == "rank_signature_cooldown"
    assert metadata["rank_signature_cooldown_hit"] is True


def test_probability_focus_search_base_requires_frozen_primary_lift_when_gated():
    current_config = FrequencyRankerConfig(frequency_weight=0.30)
    focus_config = FrequencyRankerConfig(frequency_weight=0.45, omission_weight=0.10)
    incumbent = attach_test_frozen_validation(
        supervisor_summary_for_config(current_config),
        top_10000_hits=0,
    )
    focus_summary = attach_test_frozen_validation(
        supervisor_summary_for_config(
            focus_config,
            top_100_hits=3,
            top_1000_hits=3,
            top_10000_hits=3,
        ),
        top_10000_hits=0,
    )

    next_base, metadata = select_probability_focus_search_base(
        current_base=current_config,
        focus_summary=focus_summary,
        focus_info={
            "active": True,
            "source": "probability_focus",
            "reason": "held_previous_probability_focus",
            "hold_rounds": 4,
            "remaining_rounds": 2,
            "refreshed": False,
        },
        require_frozen_primary_lift=True,
        frozen_primary_lift_baseline=incumbent,
    )

    assert next_base is None
    assert metadata["reason"] == "frozen_primary_lift_required"
    assert metadata["frozen_primary_lift_required"] is True
    assert metadata["selected_frozen_primary_score"] == [0, 0, 0]


def test_next_search_base_skips_round_best_with_excluded_rank_signature():
    current_config = FrequencyRankerConfig()
    round_best_config = FrequencyRankerConfig(frequency_weight=0.40)
    challenger_config = FrequencyRankerConfig(frequency_weight=0.60)
    round_best = supervisor_summary_for_config(
        round_best_config,
        target_ranks=[100, 900, 50_000],
        objective_score=2200.0,
    )
    challenger = supervisor_summary_for_config(
        challenger_config,
        target_ranks=[90, 850, 49_000],
        objective_score=2100.0,
    )

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[round_best, challenger],
        round_best=round_best,
        improved=False,
        excluded_rank_signature_hashes=(rank_signature_hash(round_best),),
    )

    assert config_hash(next_base) == config_hash(challenger_config)
    assert metadata["source"] == "search_challenger"
    assert metadata["round_best_rank_signature_hash"] == rank_signature_hash(round_best)
    assert metadata["rank_signature_hash"] == rank_signature_hash(challenger)


def test_next_search_base_requires_frozen_primary_lift_for_challenger_when_gated():
    current_config = FrequencyRankerConfig()
    blocked_config = FrequencyRankerConfig(frequency_weight=0.40)
    lift_config = FrequencyRankerConfig(frequency_weight=0.65)
    incumbent = attach_test_frozen_validation(
        supervisor_summary_for_config(current_config, target_ranks=[100, 900, 50_000]),
        top_10000_hits=0,
        tail_over_1000000_count=1,
    )
    blocked = attach_test_frozen_validation(
        supervisor_summary_for_config(
            blocked_config,
            top_100_hits=3,
            top_1000_hits=3,
            top_10000_hits=3,
            target_ranks=[17, 55, 89],
            objective_score=2300.0,
        ),
        top_10000_hits=0,
    )
    lift = attach_test_frozen_validation(
        supervisor_summary_for_config(
            lift_config,
            top_100_hits=1,
            top_1000_hits=2,
            top_10000_hits=3,
            target_ranks=[500, 900, 8_000],
            objective_score=100.0,
        ),
        top_10000_hits=1,
    )

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[incumbent, blocked, lift],
        round_best=blocked,
        improved=False,
        allow_unpromoted_round_best=False,
        round_best_skip_reason="eval_slice_overfit_no_frozen_primary_lift",
        require_frozen_primary_lift=True,
        frozen_primary_lift_baseline=incumbent,
    )

    assert config_hash(next_base) == config_hash(lift_config)
    assert metadata["source"] == "search_challenger"
    assert metadata["frozen_primary_lift_required"] is True
    assert metadata["frozen_primary_lift_baseline_score"] == [0, 0, 0]
    assert metadata["search_challenger_frozen_primary_score"] == [0, 0, 1]


def test_next_search_base_stays_put_when_gated_challengers_have_no_frozen_primary_lift():
    current_config = FrequencyRankerConfig()
    blocked_config = FrequencyRankerConfig(frequency_weight=0.40)
    incumbent = attach_test_frozen_validation(
        supervisor_summary_for_config(current_config, target_ranks=[100, 900, 50_000]),
        top_10000_hits=0,
        tail_over_1000000_count=1,
    )
    blocked = attach_test_frozen_validation(
        supervisor_summary_for_config(
            blocked_config,
            top_100_hits=3,
            top_1000_hits=3,
            top_10000_hits=3,
            target_ranks=[17, 55, 89],
            objective_score=2300.0,
        ),
        top_10000_hits=0,
    )

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[incumbent, blocked],
        round_best=blocked,
        improved=False,
        allow_unpromoted_round_best=False,
        round_best_skip_reason="eval_slice_overfit_no_frozen_primary_lift",
        require_frozen_primary_lift=True,
        frozen_primary_lift_baseline=incumbent,
    )

    assert config_hash(next_base) == config_hash(current_config)
    assert metadata["source"] == "unchanged"
    assert metadata["changed"] is False
    assert metadata["search_challenger_config_hash"] == ""
    assert metadata["selected_frozen_primary_score"] == [0, 0, 0]


def test_next_search_base_blocks_tail_only_experimental_navigation_when_primary_gate_active():
    current_config = FrequencyRankerConfig()
    blocked_config = FrequencyRankerConfig(frequency_weight=0.40)
    exploration_config = FrequencyRankerConfig(frequency_weight=0.15, omission_weight=0.35)
    incumbent = attach_test_frozen_validation(
        supervisor_summary_for_config(current_config, target_ranks=[100, 900, 50_000]),
        top_10000_hits=0,
        tail_over_1000000_count=1,
    )
    blocked = attach_test_frozen_validation(
        supervisor_summary_for_config(
            blocked_config,
            top_100_hits=3,
            top_1000_hits=3,
            top_10000_hits=3,
            target_ranks=[17, 55, 89],
            objective_score=2300.0,
        ),
        top_10000_hits=0,
    )
    exploration = attach_test_frozen_validation(
        supervisor_summary_for_config(
            exploration_config,
            target_ranks=[900, 80, 40_000],
            objective_score=1800.0,
        ),
        top_10000_hits=0,
    )

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[incumbent, blocked, exploration],
        round_best=blocked,
        improved=False,
        exploration_navigation_candidate=exploration,
        allow_unpromoted_round_best=False,
        round_best_skip_reason="eval_slice_overfit_no_frozen_primary_lift",
        require_frozen_primary_lift=True,
        frozen_primary_lift_baseline=incumbent,
        min_config_distance=0.08,
    )

    assert config_hash(next_base) == config_hash(current_config)
    assert metadata["source"] == "unchanged"
    assert metadata["changed"] is False
    assert metadata["round_best_search_blocked"] is True
    assert metadata["exploration_navigation_eligible"] is False
    assert metadata["exploration_navigation_primary_lift_passed"] is False
    assert metadata["exploration_navigation_primary_lift_blocked"] is True
    assert metadata["exploration_navigation_frozen_primary_score"] == [0, 0, 0]
    assert metadata["exploration_navigation_tail_over_1000000_delta"] == -1
    assert metadata["exploration_navigation_quality_reason"] == "passed"
    assert metadata["exploration_navigation_rank_vector_changed"] is True
    assert metadata["selected_frozen_primary_score"] == [0, 0, 0]


def test_next_search_base_blocks_experimental_navigation_without_tail_or_frontier_lift():
    current_config = FrequencyRankerConfig()
    blocked_config = FrequencyRankerConfig(frequency_weight=0.40)
    exploration_config = FrequencyRankerConfig(frequency_weight=0.15, omission_weight=0.35)
    incumbent = attach_test_frozen_validation(
        supervisor_summary_for_config(current_config, target_ranks=[100, 900, 50_000]),
        top_10000_hits=0,
    )
    blocked = attach_test_frozen_validation(
        supervisor_summary_for_config(
            blocked_config,
            top_100_hits=3,
            top_1000_hits=3,
            top_10000_hits=3,
            target_ranks=[17, 55, 89],
            objective_score=2300.0,
        ),
        top_10000_hits=0,
    )
    exploration = attach_test_frozen_validation(
        supervisor_summary_for_config(
            exploration_config,
            target_ranks=[900, 80, 40_000],
            objective_score=1800.0,
        ),
        top_10000_hits=0,
    )

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[incumbent, blocked, exploration],
        round_best=blocked,
        improved=False,
        exploration_navigation_candidate=exploration,
        allow_unpromoted_round_best=False,
        round_best_skip_reason="eval_slice_overfit_no_frozen_primary_lift",
        require_frozen_primary_lift=True,
        frozen_primary_lift_baseline=incumbent,
        min_config_distance=0.08,
    )

    assert config_hash(next_base) == config_hash(current_config)
    assert metadata["source"] == "unchanged"
    assert metadata["exploration_navigation_eligible"] is False
    assert metadata["exploration_navigation_quality_reason"] == "zero_frozen_primary_without_tail_or_frontier_lift"
    assert metadata["exploration_navigation_tail_over_1000000_delta"] == 0
    assert metadata["exploration_navigation_source_frontier_score_improved"] is False


def test_next_search_base_blocks_low_quality_restart_from_standard_round_best_path():
    current_config = FrequencyRankerConfig()
    restart_config = FrequencyRankerConfig(structural_weight=1.15, frequency_weight=0.05, omission_weight=0.05)
    alternative_config = FrequencyRankerConfig(frequency_weight=0.60, omission_weight=0.20)
    incumbent = attach_test_frozen_validation(
        supervisor_summary_for_config(current_config, target_ranks=[100, 900, 50_000]),
        top_10000_hits=0,
        median_rank=700_000,
        tail_over_1000000_count=0,
    )
    restart = attach_test_frozen_validation(
        supervisor_summary_for_config(
            restart_config,
            target_ranks=[90, 800, 45_000],
            objective_score=2300.0,
        ),
        top_10000_hits=0,
        median_rank=800_000,
        tail_over_1000000_count=1,
    )
    alternative = attach_test_frozen_validation(
        supervisor_summary_for_config(
            alternative_config,
            target_ranks=[95, 850, 48_000],
            objective_score=2100.0,
        ),
        top_10000_hits=0,
        median_rank=690_000,
        tail_over_1000000_count=0,
    )

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[incumbent, restart, alternative],
        round_best=restart,
        improved=False,
        exploration_navigation_candidate=restart,
        exploration_navigation_source="rank_homogeneity_restart_champion",
        exploration_navigation_reason="rank_homogeneity_restart_changed_rank_vector",
        allow_unpromoted_round_best=True,
        frozen_primary_lift_baseline=incumbent,
    )

    assert config_hash(next_base) == config_hash(alternative_config)
    assert metadata["source"] == "search_challenger"
    assert metadata["round_best_quality_blocked"] is True
    assert metadata["round_best_quality_reason"] == "zero_frozen_primary_without_tail_or_frontier_lift"
    assert metadata["exploration_navigation_quality_blocked"] is True
    assert metadata["quality_blocked_config_hashes"] == [config_hash(restart_config)]
    assert metadata["search_challenger_config_hash"] == config_hash(alternative_config)


def test_next_search_base_stays_put_when_low_quality_restart_is_only_option():
    current_config = FrequencyRankerConfig()
    restart_config = FrequencyRankerConfig(structural_weight=1.15, frequency_weight=0.05, omission_weight=0.05)
    incumbent = attach_test_frozen_validation(
        supervisor_summary_for_config(current_config, target_ranks=[100, 900, 50_000]),
        top_10000_hits=0,
        median_rank=700_000,
    )
    restart = attach_test_frozen_validation(
        supervisor_summary_for_config(
            restart_config,
            target_ranks=[90, 800, 45_000],
            objective_score=2300.0,
        ),
        top_10000_hits=0,
        median_rank=800_000,
        tail_over_1000000_count=1,
    )

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[incumbent, restart],
        round_best=restart,
        improved=False,
        exploration_navigation_candidate=restart,
        allow_unpromoted_round_best=True,
        frozen_primary_lift_baseline=incumbent,
    )

    assert config_hash(next_base) == config_hash(current_config)
    assert metadata["source"] == "unchanged"
    assert metadata["round_best_quality_blocked"] is True
    assert metadata["fallback_search_challenger_config_hash"] == ""


def test_next_search_base_allows_quality_passed_restart_on_standard_round_best_path():
    current_config = FrequencyRankerConfig()
    restart_config = FrequencyRankerConfig(structural_weight=1.15, frequency_weight=0.05, omission_weight=0.05)
    incumbent = attach_test_frozen_validation(
        supervisor_summary_for_config(current_config, target_ranks=[100, 900, 50_000]),
        top_10000_hits=0,
        median_rank=700_000,
    )
    restart = attach_test_frozen_validation(
        supervisor_summary_for_config(
            restart_config,
            target_ranks=[90, 800, 45_000],
            objective_score=2300.0,
        ),
        top_10000_hits=1,
        median_rank=650_000,
    )

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[incumbent, restart],
        round_best=restart,
        improved=False,
        exploration_navigation_candidate=restart,
        allow_unpromoted_round_best=True,
        frozen_primary_lift_baseline=incumbent,
    )

    assert config_hash(next_base) == config_hash(restart_config)
    assert metadata["source"] == "round_best"
    assert metadata["round_best_quality_blocked"] is False
    assert metadata["exploration_navigation_quality_blocked"] is False


def test_next_search_base_does_not_quality_block_formally_improved_candidate():
    current_config = FrequencyRankerConfig()
    improved_config = FrequencyRankerConfig(structural_weight=1.15, frequency_weight=0.05, omission_weight=0.05)
    incumbent = attach_test_frozen_validation(
        supervisor_summary_for_config(current_config, target_ranks=[100, 900, 50_000]),
        top_10000_hits=0,
        median_rank=700_000,
    )
    improved = attach_test_frozen_validation(
        supervisor_summary_for_config(
            improved_config,
            target_ranks=[90, 800, 45_000],
            objective_score=2300.0,
        ),
        top_10000_hits=0,
        median_rank=800_000,
        tail_over_1000000_count=1,
    )

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[incumbent, improved],
        round_best=improved,
        improved=True,
        exploration_navigation_candidate=improved,
        frozen_primary_lift_baseline=incumbent,
    )

    assert config_hash(next_base) == config_hash(improved_config)
    assert metadata["source"] == "new_best"
    assert metadata["round_best_quality_blocked"] is False
    assert metadata["quality_blocked_config_hashes"] == []


def test_next_search_base_blocks_secondary_frontier_navigation_when_primary_gate_active():
    current_config = FrequencyRankerConfig()
    blocked_config = FrequencyRankerConfig(frequency_weight=0.40)
    exploration_config = FrequencyRankerConfig(frequency_weight=0.15, omission_weight=0.35)
    incumbent = attach_test_frozen_validation(
        supervisor_summary_for_config(current_config, target_ranks=[100, 900, 50_000]),
        top_10000_hits=0,
        median_rank=700_000,
    )
    blocked = attach_test_frozen_validation(
        supervisor_summary_for_config(
            blocked_config,
            top_100_hits=3,
            top_1000_hits=3,
            top_10000_hits=3,
            target_ranks=[17, 55, 89],
            objective_score=2300.0,
        ),
        top_10000_hits=0,
    )
    exploration = attach_test_frozen_validation(
        supervisor_summary_for_config(
            exploration_config,
            target_ranks=[900, 80, 40_000],
            objective_score=1800.0,
        ),
        top_10000_hits=0,
        median_rank=600_000,
    )

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[incumbent, blocked, exploration],
        round_best=blocked,
        improved=False,
        exploration_navigation_candidate=exploration,
        allow_unpromoted_round_best=False,
        round_best_skip_reason="eval_slice_overfit_no_frozen_primary_lift",
        require_frozen_primary_lift=True,
        frozen_primary_lift_baseline=incumbent,
        min_config_distance=0.08,
    )

    assert config_hash(next_base) == config_hash(current_config)
    assert metadata["source"] == "unchanged"
    assert metadata["exploration_navigation_eligible"] is False
    assert metadata["exploration_navigation_primary_lift_passed"] is False
    assert metadata["exploration_navigation_primary_lift_blocked"] is True
    assert metadata["exploration_navigation_tail_over_1000000_delta"] == 0
    assert metadata["exploration_navigation_source_frontier_score_improved"] is True


def test_restart_champion_cannot_bypass_strict_primary_gate_with_tail_lift_only():
    current_config = FrequencyRankerConfig()
    blocked_config = FrequencyRankerConfig(frequency_weight=0.40)
    restart_config = FrequencyRankerConfig(frequency_weight=1.05, omission_weight=0.0)
    incumbent = attach_test_frozen_validation(
        supervisor_summary_for_config(current_config, target_ranks=[100, 900, 50_000]),
        top_10000_hits=0,
        tail_over_1000000_count=1,
    )
    blocked = attach_test_frozen_validation(
        supervisor_summary_for_config(
            blocked_config,
            top_100_hits=3,
            top_1000_hits=3,
            top_10000_hits=3,
            target_ranks=[17, 55, 89],
            objective_score=2300.0,
        ),
        top_10000_hits=0,
    )
    restart = attach_test_frozen_validation(
        supervisor_summary_for_config(
            restart_config,
            target_ranks=[80, 850, 49_000],
            objective_score=100.0,
        ),
        top_10000_hits=0,
    )
    restart_info = {
        "active": True,
        "rank_vector_changed": True,
        "reason": "rank_homogeneity_restart_changed_rank_vector",
    }

    navigation_candidate, navigation_info = select_experimental_navigation_candidate(
        exploration_champion=None,
        exploration_champion_info={"active": False, "reason": "no_exploratory_top_candidate"},
        restart_champion=restart,
        restart_champion_info=restart_info,
    )
    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[incumbent, blocked, restart],
        round_best=blocked,
        improved=False,
        exploration_navigation_candidate=navigation_candidate,
        exploration_navigation_source=str(navigation_info["source"]),
        exploration_navigation_reason=str(navigation_info["reason"]),
        allow_unpromoted_round_best=False,
        round_best_skip_reason="eval_slice_overfit_no_frozen_primary_lift",
        require_frozen_primary_lift=True,
        frozen_primary_lift_baseline=incumbent,
        min_config_distance=0.08,
    )

    assert navigation_candidate is restart
    assert config_hash(next_base) == config_hash(current_config)
    assert metadata["source"] == "unchanged"
    assert metadata["exploration_navigation_source"] == "rank_homogeneity_restart_champion"
    assert metadata["exploration_navigation_reason"] == "rank_homogeneity_restart_changed_rank_vector"
    assert metadata["exploration_navigation_eligible"] is False
    assert metadata["exploration_navigation_primary_lift_passed"] is False
    assert metadata["exploration_navigation_primary_lift_blocked"] is True
    assert metadata["exploration_navigation_tail_over_1000000_delta"] == -1
    assert metadata["selected_frozen_primary_score"] == [0, 0, 0]


def test_external_experimental_navigation_requires_and_accepts_strict_primary_lift():
    current_config = FrequencyRankerConfig()
    blocked_config = FrequencyRankerConfig(frequency_weight=0.40)
    exploration_config = FrequencyRankerConfig(frequency_weight=0.15, omission_weight=0.35)
    incumbent = attach_test_frozen_validation(
        supervisor_summary_for_config(current_config, target_ranks=[100, 900, 50_000]),
        top_10000_hits=0,
    )
    blocked = attach_test_frozen_validation(
        supervisor_summary_for_config(
            blocked_config,
            top_100_hits=3,
            top_1000_hits=3,
            top_10000_hits=3,
            target_ranks=[17, 55, 89],
            objective_score=2300.0,
        ),
        top_10000_hits=0,
    )
    exploration = attach_test_frozen_validation(
        supervisor_summary_for_config(
            exploration_config,
            target_ranks=[900, 80, 40_000],
            objective_score=1800.0,
        ),
        top_10000_hits=1,
    )

    next_base, metadata = select_next_search_base(
        current_base=current_config,
        summaries=[incumbent, blocked],
        round_best=blocked,
        improved=False,
        exploration_navigation_candidate=exploration,
        exploration_navigation_source="external_revalidated_navigation",
        exploration_navigation_reason="strict_primary_lift_revalidated",
        allow_unpromoted_round_best=False,
        round_best_skip_reason="eval_slice_overfit_no_frozen_primary_lift",
        require_frozen_primary_lift=True,
        frozen_primary_lift_baseline=incumbent,
        min_config_distance=0.08,
    )

    assert config_hash(next_base) == config_hash(exploration_config)
    assert metadata["source"] == "experimental_navigation"
    assert metadata["exploration_navigation_eligible"] is True
    assert metadata["exploration_navigation_primary_lift_passed"] is True
    assert metadata["exploration_navigation_primary_lift_blocked"] is False
    assert metadata["selected_frozen_primary_score"] == [0, 0, 1]


def test_rank_vector_restart_champion_preempts_exploration_navigation():
    exploration_config = FrequencyRankerConfig(sum_span_omission_weight=-0.148)
    restart_config = FrequencyRankerConfig(frequency_weight=0.05, omission_weight=1.15)
    exploration = supervisor_summary_for_config(exploration_config)
    restart = supervisor_summary_for_config(restart_config)

    navigation_candidate, navigation_info = select_experimental_navigation_candidate(
        exploration_champion=exploration,
        exploration_champion_info={
            "active": True,
            "source": "neural_kdj",
            "reason": "stagnation_top_eval_exploration",
        },
        restart_champion=restart,
        restart_champion_info={
            "active": True,
            "rank_vector_changed": True,
            "reason": "rank_homogeneity_restart_changed_rank_vector",
        },
    )

    assert navigation_candidate is restart
    assert navigation_info["source"] == "rank_homogeneity_restart_champion"
    assert navigation_info["reason"] == "rank_homogeneity_restart_changed_rank_vector"
    assert navigation_info["config_hash"] == summary_config_hash(restart)


def test_probability_calibration_champion_waits_for_stagnation_threshold():
    round_best_config = FrequencyRankerConfig(frequency_weight=0.30)
    challenger_config = FrequencyRankerConfig(frequency_weight=0.45)
    round_best = supervisor_summary_for_config(round_best_config, top_100_hits=1, top_1000_hits=1)
    challenger = supervisor_summary_for_config(challenger_config, top_100_hits=1, top_1000_hits=2)
    for summary in (round_best, challenger):
        summary["probability_calibration"] = probability_calibration_diagnostics(summary, universe_size=1_000_000)

    champion, metadata = select_probability_calibration_champion(
        summaries=[round_best, challenger],
        source_configs={"normal": (round_best_config,), "weight_kdj": (challenger_config,)},
        round_best=round_best,
        prior_best_summary=round_best,
        stagnation_rounds=15,
    )

    assert champion is None
    assert metadata["active"] is False
    assert metadata["reason"] == "below_threshold"


def test_rank_homogeneity_restart_champion_selects_changed_restart_outside_top5():
    incumbent = FrequencyRankerConfig()
    restart = FrequencyRankerConfig(
        frequency_weight=1.05,
        omission_weight=0.0,
        tail_distribution_weight=-0.30,
        red_omission_shape_weight=0.30,
        sum_span_omission_weight=-0.20,
    )
    normal_summaries = [
        supervisor_summary_for_config(
            FrequencyRankerConfig(frequency_weight=0.10 + index * 0.01),
            target_ranks=[100 + index, 900, 50_000],
            objective_score=2200.0 - index,
        )
        for index in range(5)
    ]
    restart_summary = attach_test_frozen_validation(
        supervisor_summary_for_config(
            restart,
            target_ranks=[80, 850, 49_000],
            objective_score=100.0,
        ),
        tail_over_1000000_count=1,
    )
    prior_best = attach_test_frozen_validation(
        supervisor_summary_for_config(incumbent, target_ranks=[100, 900, 50_000], objective_score=2200.0),
        tail_over_1000000_count=2,
    )

    champion, metadata = select_rank_homogeneity_restart_champion(
        summaries=[*normal_summaries, restart_summary],
        source_configs={
            "normal": tuple(FrequencyRankerConfig(frequency_weight=0.10 + index * 0.01) for index in range(5)),
            "stagnation_restart": (restart,),
        },
        round_best=normal_summaries[0],
        prior_best_summary=prior_best,
        rank_homogeneity={"active": True, "unique_signature_count": 3},
    )

    assert champion is restart_summary
    assert metadata["active"] is True
    assert metadata["full_eval_rank"] == 6
    assert metadata["rank_vector_changed"] is True
    assert metadata["changed_target_count"] == 3
    assert metadata["reason"] == "rank_homogeneity_restart_changed_rank_vector"
    assert metadata["primary_weight_pattern"] == "structural=0.40/frequency=1.05/omission=0.00"
    assert metadata["context_field_movement_count"] == 3
    assert metadata["frozen_primary_score"] == [0, 0, 0]
    assert metadata["baseline_frozen_primary_score"] == [0, 0, 0]
    assert metadata["tail_over_1000000_delta"] == -1
    assert metadata["source_frontier_score_improved"] is True
    assert metadata["source_frontier_primary_score_improved"] is False
    assert metadata["source_frontier_secondary_score_improved"] is True
    assert metadata["source_frontier_improvement_basis"] == "secondary"
    assert metadata["source_frontier_secondary_score"] == [0, 0, 0, -1, -700000.0, 0.0]
    assert metadata["baseline_source_frontier_secondary_score"] == [0, 0, 0, -2, -700000.0, 0.0]
    assert metadata["unique_rank_signature_count"] == 3


def test_rank_homogeneity_restart_champion_waits_for_active_guardrail():
    restart = FrequencyRankerConfig(frequency_weight=1.05, omission_weight=0.0)
    restart_summary = supervisor_summary_for_config(restart, target_ranks=[80, 850, 49_000])

    champion, metadata = select_rank_homogeneity_restart_champion(
        summaries=[restart_summary],
        source_configs={"stagnation_restart": (restart,)},
        round_best=restart_summary,
        prior_best_summary=None,
        rank_homogeneity={"active": False},
    )

    assert champion is None
    assert metadata["active"] is False
    assert metadata["reason"] == "rank_homogeneity_inactive"


def test_generate_configs_reuses_elite_configs_for_local_search():
    base = FrequencyRankerConfig()
    elite = FrequencyRankerConfig(
        structural_weight=0.35,
        frequency_weight=0.45,
        omission_weight=0.20,
        previous_consecutive_weight=0.12,
        previous_zone_shape_weight=0.18,
    )

    configs = generate_configs(base, phase="micro", step=0.02, max_configs=12, elite_configs=(elite,))

    assert elite in configs
    assert any(config.frequency_weight > elite.frequency_weight for config in configs)
    assert any(config.frequency_weight < elite.frequency_weight for config in configs)


def test_generate_configs_includes_late_shape_fields_under_round_limit():
    configs = generate_configs(FrequencyRankerConfig(), phase="micro", step=0.01, max_configs=28)

    assert any(config.weekday_trend_weight > 0 for config in configs)
    assert any(config.stable_range_weight > 0 for config in configs)
    assert any(config.tail_distribution_weight > 0 for config in configs)


def test_generate_configs_large_phase_keeps_themed_seed_candidates():
    configs = generate_configs(FrequencyRankerConfig(), phase="large", step=0.15, max_configs=28)

    assert any(config.weekday_trend_weight >= 0.10 for config in configs)
    assert any(config.mod012_weight > 0 and config.tail_distribution_weight > 0 for config in configs)
    assert any(config.first_last_sum_weight > 0 and config.stable_range_weight > 0 for config in configs)


def test_generate_configs_uses_history_and_stagnation_exploration():
    base = FrequencyRankerConfig()
    historical = [
        {
            "config": {
                **base.__dict__,
                "frequency_weight": 0.55,
                "tail_distribution_weight": 0.12,
            },
            "reward": {"objectiveScore": 120.0},
        },
        {
            "config": {
                **base.__dict__,
                "frequency_weight": 0.20,
                "tail_distribution_weight": -0.08,
            },
            "reward": {"objectiveScore": 20.0},
        },
        {
            "config": {**base.__dict__, "weekday_trend_weight": 0.10},
            "reward": {"objectiveScore": 80.0},
        },
        {
            "config": {**base.__dict__, "previous_overlap_weight": -0.10},
            "reward": {"objectiveScore": 40.0},
        },
        {
            "config": {**base.__dict__, "mod012_weight": 0.08},
            "reward": {"objectiveScore": 60.0},
        },
        {
            "config": {**base.__dict__, "red_omission_shape_weight": 0.08},
            "reward": {"objectiveScore": 70.0},
        },
    ]

    configs = generate_configs(
        base,
        phase="medium",
        step=0.07,
        max_configs=24,
        historical_summaries=historical,
        low_coverage_fields=("sum_tail_weight", "stable_range_weight"),
        stagnation_rounds=20,
        round_index=33,
    )

    assert len(configs) == len({config_hash(config) for config in configs}) <= 24
    assert any(abs(config.sum_tail_weight) >= 0.07 for config in configs)
    assert any(config.frequency_weight > 0.50 for config in configs)
    assert any(all(value == 0 for value in config.__dict__.values()) for config in configs)


def test_generate_configs_reserves_high_stagnation_exploration_slots():
    base = FrequencyRankerConfig()

    baseline_configs = generate_configs(
        base,
        phase="large",
        step=0.15,
        max_configs=11,
        stagnation_rounds=0,
        round_index=77,
    )
    stagnated_configs = generate_configs(
        base,
        phase="large",
        step=0.15,
        max_configs=11,
        stagnation_rounds=76,
        round_index=77,
    )

    baseline_hashes = {config_hash(config) for config in baseline_configs}
    stagnated_hashes = {config_hash(config) for config in stagnated_configs}

    assert len(stagnated_configs) == 11
    assert len(stagnated_hashes) == 11
    assert len(stagnated_hashes - baseline_hashes) >= 2


def test_weight_kdj_advisor_generates_bounded_candidate_offsets():
    base = FrequencyRankerConfig(frequency_weight=0.30, sum_tail_weight=0.0)
    signals = [
        {
            "signal_run_id": "weight-kdj-run-1",
            "issue": "2026067",
            "weight_name": "frequency_weight",
            "recommended_offset": 0.04,
            "objective_delta": 2.0,
            "j_value": 70.0,
        },
        {
            "signal_run_id": "weight-kdj-run-1",
            "issue": "2026068",
            "weight_name": "sum_tail_weight",
            "recommended_offset": -0.02,
            "objective_delta": 1.0,
            "j_value": 30.0,
        },
    ]

    configs = weight_kdj_advisor_candidate_configs(base, signals, max_configs=4)
    metadata = weight_kdj_advisor_metadata(signals, configs)

    assert any(round(config.frequency_weight, 6) == 0.34 for config in configs)
    assert any(round(config.sum_tail_weight, 6) == -0.02 for config in configs)
    assert metadata["mode"] == "advisor_only"
    assert metadata["candidate_count"] == len(configs)


def test_ridge_kdj_advisor_metadata_records_counts_and_advice_details():
    base = FrequencyRankerConfig(frequency_weight=0.30, sum_tail_weight=0.0)
    signals = [
        {
            "signal_run_id": "weight-kdj-run-1",
            "issue": "2026067",
            "weight_name": "frequency_weight",
        },
        {
            "signal_run_id": "weight-kdj-run-1",
            "issue": "2026068",
            "weight_name": "sum_tail_weight",
        },
    ]
    advice = (
        RidgeKdjOffsetAdvice(
            weight_name="frequency_weight",
            suggested_offset=0.03,
            confidence=0.70,
            train_rows=24,
            validation_metric=0.01,
            baseline_metric=0.03,
        ),
        RidgeKdjOffsetAdvice(
            weight_name="sum_tail_weight",
            suggested_offset=-0.02,
            confidence=0.20,
            train_rows=24,
            validation_metric=0.025,
            baseline_metric=0.03,
        ),
    )
    thresholds = {"min_confidence": 0.50, "min_train_rows": 12, "min_validation_rows": 4}
    params = {"step": 0.01, "ridge_alpha": 0.1}
    configs = ridge_kdj_advice_to_frequency_ranker_config_candidates(
        base,
        advice,
        max_configs=2,
        min_confidence=thresholds["min_confidence"],
    )

    metadata = ridge_kdj_advisor_metadata(
        signals,
        configs,
        enabled=True,
        budget=2,
        params=params,
        thresholds=thresholds,
        advice=advice,
    )

    assert metadata["mode"] == "advisor_only"
    assert metadata["enabled"] is True
    assert metadata["budget"] == 2
    assert metadata["params"] == params
    assert metadata["thresholds"] == thresholds
    assert metadata["signal_run_id"] == "weight-kdj-run-1"
    assert metadata["loaded_signals"] == 2
    assert metadata["latest_signal_issue"] == "2026068"
    assert metadata["selected_count"] == 1
    assert metadata["rejected_count"] == 1
    assert metadata["fields"] == ["frequency_weight", "sum_tail_weight"]
    assert metadata["advice"][0]["confidence"] == 0.70
    assert metadata["advice"][0]["validation_metric"] == 0.01
    assert metadata["advice"][0]["baseline_metric"] == 0.03
    assert metadata["advice"][0]["suggested_offset"] == 0.03
    assert metadata["config_hashes"] == [config_hash(configs[0])]


def test_neural_kdj_advisor_metadata_records_validation_and_candidate_hashes():
    base = FrequencyRankerConfig(frequency_weight=0.30, omission_weight=0.20)
    signals = [
        {
            "signal_run_id": "weight-kdj-run-1",
            "issue": "2026067",
            "weight_name": "frequency_weight",
        },
        {
            "signal_run_id": "weight-kdj-run-1",
            "issue": "2026068",
            "weight_name": "omission_weight",
        },
    ]
    advice = (
        NeuralKdjOffsetAdvice(
            weight_name="frequency_weight",
            suggested_offset=0.02,
            confidence=0.55,
            train_rows=40,
            validation_rows=10,
            validation_metric=0.012,
            baseline_metric=0.020,
            feature_names=("j", "k_minus_d"),
        ),
        NeuralKdjOffsetAdvice(
            weight_name="omission_weight",
            suggested_offset=-0.01,
            confidence=0.15,
            train_rows=40,
            validation_rows=10,
            validation_metric=0.018,
            baseline_metric=0.020,
            feature_names=("j", "k_minus_d"),
        ),
    )
    thresholds = {"min_confidence": 0.50}
    params = {"step": 0.01, "seed": 17, "hidden_units": 8, "epochs": 120, "model": "numpy_mlp_kdj_offset_v0"}
    configs = neural_kdj_advice_to_frequency_ranker_config_candidates(
        base,
        advice,
        max_configs=1,
        min_confidence=thresholds["min_confidence"],
    )

    metadata = neural_kdj_advisor_metadata(
        signals,
        configs,
        enabled=True,
        budget=1,
        params=params,
        thresholds=thresholds,
        advice=advice,
    )

    assert metadata["mode"] == "advisor_only"
    assert metadata["enabled"] is True
    assert metadata["budget"] == 1
    assert metadata["params"] == params
    assert metadata["thresholds"] == thresholds
    assert metadata["signal_run_id"] == "weight-kdj-run-1"
    assert metadata["loaded_signals"] == 2
    assert metadata["latest_signal_issue"] == "2026068"
    assert metadata["selected_count"] == 1
    assert metadata["rejected_count"] == 1
    assert metadata["fields"] == ["frequency_weight", "omission_weight"]
    assert metadata["advice"][0]["confidence"] == 0.55
    assert metadata["advice"][0]["validation_metric"] == 0.012
    assert metadata["advice"][0]["baseline_metric"] == 0.020
    assert metadata["advice"][0]["suggested_offset"] == 0.02
    assert metadata["advice"][0]["validation_rows"] == 10
    assert metadata["config_hashes"] == [config_hash(configs[0])]


def test_target_weight_inversion_metadata_records_sample_candidate_and_guardrails():
    configs = (
        FrequencyRankerConfig(frequency_weight=0.34),
        FrequencyRankerConfig(sum_tail_weight=0.02),
    )
    aggregate = {
        "sample_count": 5,
        "success_count": 3,
        "success_rate": 0.6,
        "hit_count": 1,
        "miss_count": 4,
        "outlier_count": 2,
        "latest_issue": "2026068",
        "stable_fields": ["frequency_weight"],
        "candidates": [
            {
                "label": "current_plus_weighted_delta",
                "config": configs[0].__dict__,
                "config_hash": config_hash(configs[0]),
                "delta_config": {"frequency_weight": 0.04},
            },
            {
                "label": "current_plus_only_stable_fields_delta",
                "config": configs[1].__dict__,
                "config_hash": config_hash(configs[1]),
                "delta_config": {"sum_tail_weight": 0.02},
            },
        ],
    }
    controls = [{"label": "null_baseline"}, {"label": "current_best_frozen_baseline"}]

    metadata = target_weight_inversion_advisor_metadata(
        enabled=True,
        budget=4,
        aggregate=aggregate,
        configs=configs,
        control_experiments=controls,
        frozen_validation_window_value=20,
    )

    assert metadata["mode"] == "target_weight_inversion_v0"
    assert metadata["enabled"] is True
    assert metadata["budget"] == 4
    assert metadata["sample_count"] == 5
    assert metadata["success_count"] == 3
    assert metadata["latest_issue"] == "2026068"
    assert metadata["candidate_count"] == 2
    assert metadata["candidate_labels"] == ["current_plus_weighted_delta", "current_plus_only_stable_fields_delta"]
    assert metadata["fields"] == ["frequency_weight", "sum_tail_weight"]
    assert metadata["selected_count"] == 2
    assert metadata["rejected_count"] == 0
    assert metadata["advice"][0]["weight_name"] == "frequency_weight"
    assert metadata["advice"][0]["suggested_offset"] == 0.04
    assert metadata["advice"][0]["decision"] == "selected"
    assert metadata["control_verdict"]["status"] == "queued_for_next_round"
    assert metadata["control_experiment_count"] == 2
    assert metadata["frozen_validation"] == {"window": 20, "control_count": 2}
    assert metadata["advisory_only"] is True


def test_target_weight_inversion_advisor_limits_candidates_for_next_round(monkeypatch):
    captured = {}

    def fake_invert_targets_for_summary(**kwargs):
        captured["target_results"] = kwargs["target_results"]
        captured["top_n"] = kwargs["top_n"]
        return ["inversion-row"]

    candidate_configs = tuple(FrequencyRankerConfig(frequency_weight=round(0.30 + index * 0.01, 4)) for index in range(5))

    def fake_target_inversion_payload(*, inversions, base_config):
        return (
            [{"target_issue": "2026068", "success": True}],
            {
                "mode": "target_weight_inversion_v0",
                "sample_count": 6,
                "success_count": 5,
                "success_rate": 0.833333,
                "hit_count": 1,
                "miss_count": 5,
                "outlier_count": 0,
                "candidates": [
                    {"label": f"candidate-{index}", "config": config.__dict__}
                    for index, config in enumerate(candidate_configs)
                ],
            },
            candidate_configs,
        )

    monkeypatch.setattr(supervisor, "invert_targets_for_summary", fake_invert_targets_for_summary)
    monkeypatch.setattr(supervisor, "target_inversion_payload", fake_target_inversion_payload)
    best_summary = {
        "config": FrequencyRankerConfig(frequency_weight=0.30).__dict__,
        "target_results": [{"issue": "2026068", "red_numbers": [1, 2, 3, 4, 5, 6]}],
    }

    rows, aggregate, configs, metadata = target_weight_inversion_advisor(
        history=[],
        ranked_universe=[],
        best_summary=best_summary,
        train_window=100,
        train_mode="expanding",
        top_n=10_000,
        max_candidates=8,
        budget=4,
        control_experiments=[{"label": "null_baseline"}],
        frozen_validation_window_value=20,
    )

    assert captured == {"target_results": best_summary["target_results"], "top_n": 10_000}
    assert rows == [{"target_issue": "2026068", "success": True}]
    assert aggregate["sample_count"] == 6
    assert len(configs) == 4
    assert metadata["candidate_count"] == 4
    assert metadata["candidate_labels"] == ["candidate-0", "candidate-1", "candidate-2", "candidate-3"]
    assert metadata["control_experiment_count"] == 1
    assert metadata["frozen_validation"]["window"] == 20


def test_near_miss_targets_for_cutoff_prioritizes_threshold_misses():
    targets = [
        {"issue": "2026001", "rank": 90, "red_numbers": [1, 2, 3, 4, 5, 6]},
        {"issue": "2026002", "rank": 408, "red_numbers": [1, 2, 3, 4, 5, 7]},
        {"issue": "2026003", "rank": 120, "red_numbers": [1, 2, 3, 4, 5, 8]},
        {"issue": "2026004", "rank": 501, "red_numbers": [1, 2, 3, 4, 5, 9]},
    ]

    selected = near_miss_targets_for_cutoff(targets, cutoff=100, upper=500, limit=2)

    assert [target["issue"] for target in selected] == ["2026003", "2026002"]


def test_near_miss_inversion_advisor_uses_tighter_cutoffs(monkeypatch):
    calls = []
    configs_by_cutoff = {
        100: FrequencyRankerConfig(frequency_weight=0.41),
        1000: FrequencyRankerConfig(omission_weight=0.42),
        10000: FrequencyRankerConfig(sum_tail_weight=0.09),
    }

    def fake_invert_targets_for_summary(**kwargs):
        calls.append(
            {
                "top_n": kwargs["top_n"],
                "issues": [target["issue"] for target in kwargs["target_results"]],
            }
        )
        return [f"inversion-{kwargs['top_n']}"]

    def fake_target_inversion_payload(*, inversions, base_config):
        cutoff = int(str(inversions[0]).split("-")[-1])
        config = configs_by_cutoff[cutoff]
        return (
            [{"target_issue": f"near-{cutoff}", "success": True}],
            {
                "success_count": 1,
                "partial_improvement_count": 0,
                "candidates": [{"config_hash": config_hash(config), "config": config.__dict__}],
            },
            (config,),
        )

    monkeypatch.setattr(supervisor, "invert_targets_for_summary", fake_invert_targets_for_summary)
    monkeypatch.setattr(supervisor, "target_inversion_payload", fake_target_inversion_payload)
    best_summary = {
        "config": FrequencyRankerConfig().__dict__,
        "target_results": [
            {"issue": "already_top100", "rank": 47, "red_numbers": [1, 2, 3, 4, 5, 6]},
            {"issue": "near_top100", "rank": 408, "red_numbers": [1, 2, 3, 4, 5, 7]},
            {"issue": "near_top1000", "rank": 1500, "red_numbers": [1, 2, 3, 4, 5, 8]},
            {"issue": "near_top10000", "rank": 45362, "red_numbers": [1, 2, 3, 4, 5, 9]},
            {"issue": "too_far", "rank": 70000, "red_numbers": [1, 2, 3, 4, 5, 10]},
        ],
    }

    configs, metadata = near_miss_inversion_advisor(
        history=[],
        ranked_universe=[],
        best_summary=best_summary,
        train_window=100,
        train_mode="expanding",
        enabled=True,
        max_configs=8,
        max_delta_candidates=8,
    )

    assert [call["top_n"] for call in calls] == [100, 1000, 10000]
    assert calls[0]["issues"] == ["near_top100"]
    assert calls[1]["issues"] == ["near_top1000"]
    assert calls[2]["issues"] == ["near_top10000"]
    assert len(configs) == 3
    assert metadata["status"] == "ready"
    assert metadata["candidate_count"] == 3
    assert [band["target_count"] for band in metadata["bands"]] == [1, 1, 1]


def test_bounded_unique_config_hashes_uses_hashes_and_limit():
    base = FrequencyRankerConfig()
    configs = (
        base,
        base,
        FrequencyRankerConfig(frequency_weight=0.40),
        FrequencyRankerConfig(frequency_weight=0.40),
        FrequencyRankerConfig(sum_tail_weight=0.04),
    )

    hashes = bounded_unique_config_hashes(configs, limit=2)

    assert hashes == [config_hash(base), config_hash(FrequencyRankerConfig(frequency_weight=0.40))]
    assert len(hashes) == len(set(hashes)) == 2


def test_weight_kdj_advisor_metadata_records_threshold_counts_and_fields():
    base = FrequencyRankerConfig(frequency_weight=0.30, sum_tail_weight=0.0, weekday_trend_weight=0.0)
    signals = [
        {
            "signal_run_id": "weight-kdj-run-1",
            "issue": "2026066",
            "weight_name": "frequency_weight",
            "recommended_offset": 0.03,
            "objective_delta": 2.0,
            "j_value": 55.0,
        },
        {
            "signal_run_id": "weight-kdj-run-1",
            "issue": "2026068",
            "weight_name": "frequency_weight",
            "recommended_offset": 0.03,
            "objective_delta": 2.0,
            "j_value": 70.0,
        },
        {
            "signal_run_id": "weight-kdj-run-1",
            "issue": "2026068",
            "weight_name": "sum_tail_weight",
            "recommended_offset": -0.03,
            "objective_delta": 0.2,
            "j_value": 25.0,
        },
        {
            "signal_run_id": "weight-kdj-run-1",
            "issue": "2026068",
            "weight_name": "weekday_trend_weight",
            "recommended_offset": 0.03,
            "objective_delta": 2.0,
            "j_value": 52.0,
        },
    ]
    thresholds = {
        "min_objective_delta": 1.0,
        "min_abs_offset": 0.01,
        "slope_window": 2,
        "neutral_band": 5.0,
    }
    advice = weight_kdj_advice_from_signals(signals, allowed_fields=tuple(base.__dict__), **thresholds)
    configs = weight_kdj_advisor_candidate_configs(base, signals, max_configs=3, **thresholds)

    metadata = weight_kdj_advisor_metadata(signals, configs, budget=3, thresholds=thresholds, advice=advice)

    assert metadata["budget"] == 3
    assert metadata["thresholds"] == thresholds
    assert metadata["selected_count"] == 1
    assert metadata["downweighted_count"] == 1
    assert metadata["rejected_count"] == 1
    assert metadata["selected_fields"] == ["frequency_weight"]
    assert metadata["latest_issue"] == "2026068"
    assert metadata["candidate_count"] == len(configs)


def test_prefilter_configs_keeps_base_and_elite_before_full_refine():
    universe = [
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
        (3, 10, 15, 20, 25, 33),
        (4, 11, 16, 21, 26, 30),
        (5, 12, 17, 22, 27, 29),
    ]
    history = [
        ("001", universe[0]),
        ("002", universe[1]),
        ("003", universe[2]),
        ("004", universe[3]),
        ("005", universe[4]),
        ("006", universe[0]),
        ("007", universe[1]),
    ]
    base = FrequencyRankerConfig()
    elite = FrequencyRankerConfig(structural_weight=0.35, frequency_weight=0.40, omission_weight=0.20)
    configs = (
        base,
        elite,
        FrequencyRankerConfig(structural_weight=0.10, frequency_weight=0.80, omission_weight=0.05),
        FrequencyRankerConfig(structural_weight=0.80, frequency_weight=0.10, omission_weight=0.05),
    )

    refined, metadata = prefilter_configs(
        history=history,
        ranked_universe=build_ranked_universe(universe),
        configs=configs,
        keep_configs=(base, elite),
        train_window=2,
        train_mode="expanding",
        eval_window=4,
        top_n=10000,
        workers=1,
        pool=None,
        round_index=1,
        stride=4,
        promote_limit=1,
    )

    assert base in refined
    assert elite in refined
    assert len(refined) <= 4
    assert metadata["generated_config_count"] == len(configs)
    assert metadata["refined_config_count"] == len(refined)
    assert metadata["target_count"] == 1
    assert metadata["diversity_added_count"] >= 0


def test_prefilter_configs_keeps_diversity_quota():
    universe = [
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
        (3, 10, 15, 20, 25, 33),
        (4, 11, 16, 21, 26, 30),
        (5, 12, 17, 22, 27, 29),
    ]
    history = [
        ("001", universe[0]),
        ("002", universe[1]),
        ("003", universe[2]),
        ("004", universe[3]),
        ("005", universe[4]),
        ("006", universe[0]),
        ("007", universe[1]),
    ]
    base = FrequencyRankerConfig()
    far = FrequencyRankerConfig(structural_weight=1.25, frequency_weight=0.0, omission_weight=0.0)
    configs = (
        base,
        FrequencyRankerConfig(structural_weight=0.41, frequency_weight=0.30, omission_weight=0.25),
        FrequencyRankerConfig(structural_weight=0.42, frequency_weight=0.30, omission_weight=0.25),
        far,
    )

    refined, metadata = prefilter_configs(
        history=history,
        ranked_universe=build_ranked_universe(universe),
        configs=configs,
        keep_configs=(base,),
        train_window=2,
        train_mode="expanding",
        eval_window=4,
        top_n=10000,
        workers=1,
        pool=None,
        round_index=1,
        stride=4,
        promote_limit=1,
        diversity_quota=1,
    )

    assert far in refined
    assert metadata["diversity_added_count"] == 1


def test_prefilter_configs_excludes_frozen_validation_targets():
    universe = [
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
        (3, 10, 15, 20, 25, 33),
        (4, 11, 16, 21, 26, 30),
    ]
    history = [
        (f"{index:03d}", universe[(index - 1) % len(universe)])
        for index in range(1, 13)
    ]
    base = FrequencyRankerConfig()

    _refined, metadata = prefilter_configs(
        history=history,
        ranked_universe=build_ranked_universe(universe),
        configs=(base,),
        keep_configs=(base,),
        train_window=2,
        train_mode="expanding",
        eval_window=8,
        top_n=10000,
        workers=1,
        pool=None,
        round_index=1,
        stride=1,
        frozen_validation_window_value=2,
    )

    assert metadata["search_target_count"] == 6
    assert metadata["frozen_target_count"] == 2
    assert metadata["target_issues"] == ["005", "006", "007", "008", "009", "010"]
    assert set(metadata["target_issues"]).isdisjoint({"011", "012"})


def test_prefilter_holdout_isolation_audit_fails_on_frozen_or_unknown_issue():
    evaluation_split = {
        "search_issues": ["001", "002", "003"],
        "frozen_issues": ["004", "005"],
    }

    passed = prefilter_holdout_isolation_audit(
        prefilter_target_issues=["001", "003"],
        evaluation_split=evaluation_split,
    )
    contaminated = prefilter_holdout_isolation_audit(
        prefilter_target_issues=["001", "004", "999"],
        evaluation_split=evaluation_split,
    )

    assert passed["passed"] is True
    assert passed["prefilter_frozen_issue_overlap_count"] == 0
    assert passed["prefilter_uses_frozen_validation"] is False
    assert contaminated["passed"] is False
    assert contaminated["prefilter_frozen_issue_overlap"] == ["004"]
    assert contaminated["prefilter_outside_split_issues"] == ["999"]
    assert contaminated["prefilter_uses_frozen_validation"] is True


def test_stagnation_and_low_coverage_fields_are_deterministic():
    rounds = [{"improved": True}, {"improved": False}, {"improved": False}]
    summaries = [
        {"config": {"frequency_weight": 0.4, "tail_distribution_weight": 0.1}},
        {"config": {"frequency_weight": 0.5}},
    ]

    assert stagnation_round_count(rounds) == 2
    assert low_coverage_fields_from_summaries(summaries, limit=2) == ("tail_distribution_weight", "frequency_weight")


def test_guard_history_recovers_same_history_unpromoted_streak_across_runs():
    records = [
        {
            "run_id": "run-new",
            "round_index": 2,
            "improved": False,
            "prefilter": {
                "round_best_rank_signature_hash": "sig-a",
                "eval_slice_overfit_guardrail": {"active": True},
                "stale_round_best_search_base_gate": {"active": True},
            },
        },
        {
            "run_id": "run-new",
            "round_index": 1,
            "improved": False,
            "prefilter": {"round_best_rank_signature_hash": "sig-a"},
        },
        {
            "run_id": "run-old",
            "round_index": 3,
            "improved": False,
            "prefilter": {"round_best_rank_signature_hash": "sig-a"},
        },
        {
            "run_id": "run-old",
            "round_index": 2,
            "improved": True,
            "prefilter": {"round_best_rank_signature_hash": "sig-b"},
        },
        {
            "run_id": "run-old",
            "round_index": 1,
            "improved": False,
            "prefilter": {"round_best_rank_signature_hash": "sig-b"},
        },
    ]

    history, metadata = recover_supervisor_guard_history(records)

    assert len(history) == 3
    assert stagnation_round_count(history) == 3
    assert metadata["active"] is True
    assert metadata["stagnation_rounds"] == 3
    assert metadata["source_run_ids"] == ["run-new", "run-old"]
    assert metadata["rank_signature_count"] == 3
    assert metadata["unique_rank_signature_count"] == 1
    assert metadata["latest_eval_slice_overfit_active"] is True
    assert metadata["latest_search_gate_active"] is True


def test_guard_history_continues_until_current_run_formally_improves():
    carryover = [
        {"improved": False, "prefilter": {"round_best_rank_signature_hash": "sig-a"}}
        for _ in range(4)
    ]
    current = [
        {"improved": False, "prefilter": {"round_best_rank_signature_hash": "sig-a"}}
    ]

    active = active_supervisor_guard_rounds(carryover, current)

    assert len(active) == 5
    assert stagnation_round_count(active) == 5
    guard = rank_homogeneity_guardrail(active, stagnation_rounds=5)
    assert guard["active"] is True
    assert guard["trigger_mode"] == "exact_repeat"

    current.extend(
        [
            {"improved": True, "prefilter": {"round_best_rank_signature_hash": "sig-b"}},
            {"improved": False, "prefilter": {"round_best_rank_signature_hash": "sig-c"}},
        ]
    )
    reset = active_supervisor_guard_rounds(carryover, current)

    assert len(reset) == 1
    assert stagnation_round_count(reset) == 1
    assert reset[0]["prefilter"]["round_best_rank_signature_hash"] == "sig-c"


def test_guard_history_respects_zero_limit():
    history, metadata = recover_supervisor_guard_history(
        [{"run_id": "run-1", "round_index": 1, "improved": False, "prefilter": {}}],
        limit=0,
    )

    assert history == []
    assert metadata["active"] is False
    assert metadata["stagnation_rounds"] == 0


def test_guard_history_preserves_monotonic_stagnation_beyond_record_window():
    records = [
        {
            "run_id": "run-new",
            "round_index": 3 - index,
            "improved": False,
            "prefilter": {
                "round_best_rank_signature_hash": "sig-a",
                **(
                    {
                        "guard_continuity": {
                            "effective_stagnation_rounds": 82,
                        }
                    }
                    if index == 0
                    else {}
                ),
            },
        }
        for index in range(3)
    ]

    history, metadata = recover_supervisor_guard_history(records, limit=3)

    assert len(history) == 3
    assert metadata["recovered_round_count"] == 3
    assert metadata["persisted_effective_stagnation_rounds"] == 82
    assert metadata["persisted_next_stagnation_rounds"] == 83
    assert metadata["stagnation_rounds"] == 83
    assert metadata["continuity_floor_applied"] is True
    assert metadata["record_window_saturated"] is True
    assert active_supervisor_stagnation_round_count(83, []) == 83
    assert active_supervisor_stagnation_round_count(
        83,
        [{"improved": False}],
    ) == 84
    assert stagnation_restart_catalog_position(
        {
            "active": True,
            "stagnation_rounds": 83,
            "stagnation_threshold": 4,
        },
        budget=5,
    ) == {"batch_index": 79, "catalog_offset": 395}


def test_active_supervisor_stagnation_resets_only_after_formal_improvement():
    current_rounds = [
        {"improved": False},
        {"improved": True},
        {"improved": False},
    ]

    assert active_supervisor_stagnation_round_count(83, current_rounds) == 1


def test_guard_history_latest_formal_improvement_clears_persisted_floor():
    history, metadata = recover_supervisor_guard_history(
        [
            {
                "run_id": "run-new",
                "round_index": 1,
                "improved": True,
                "prefilter": {
                    "guard_continuity": {
                        "effective_stagnation_rounds": 82,
                    }
                },
            },
            {
                "run_id": "run-old",
                "round_index": 80,
                "improved": False,
                "prefilter": {"round_best_rank_signature_hash": "sig-a"},
            },
        ]
    )

    assert history == []
    assert metadata["stagnation_rounds"] == 0
    assert metadata["persisted_next_stagnation_rounds"] is None
    assert metadata["continuity_floor_applied"] is False


def test_control_experiments_and_frozen_validation_are_recorded():
    base = FrequencyRankerConfig()
    controls = control_experiment_configs(base)
    summary_by_hash = {}
    for index, (_label, config) in enumerate(controls, start=1):
        summary = {
            "config": config.__dict__,
            "as_of_issue": "2026067",
            "history_fingerprint": "history-1",
            "config_hash": config_hash(config),
            "evaluated_draws": 3,
            "top_100_hits": 0,
            "top_1000_hits": 0,
            "top_10000_hits": index,
            "median_rank": 20000 + index,
            "best_rank": 100 + index,
            "worst_rank": 900000 - index,
            "red5": {"top_100_hits": 0, "top_1000_hits": 1, "top_10000_hits": 2},
            "rank_quality": {},
            "target_results": [
                {
                    "issue": "2026001",
                    "rank": 50000,
                    "hit_top_100": False,
                    "hit_top_1000": False,
                    "hit_top_10000": False,
                    "hit_red5_top_100": False,
                    "hit_red5_top_1000": False,
                    "hit_red5_top_10000": True,
                },
                {
                    "issue": "2026002",
                    "rank": 900,
                    "hit_top_100": False,
                    "hit_top_1000": True,
                    "hit_top_10000": True,
                    "red5_rank": 80,
                    "hit_red5_top_100": True,
                    "hit_red5_top_1000": True,
                    "hit_red5_top_10000": True,
                },
            ],
            "reward": {"objectiveScore": float(index)},
        }
        summary_by_hash[summary["config_hash"]] = summary

    summaries = list(summary_by_hash.values())
    attach_frozen_validation(summaries, validation_window=frozen_validation_window(10), universe_size=1107568)
    rows = control_experiment_summaries(summaries, controls)

    assert frozen_validation_window(100) == 20
    assert {label for label, _config in controls} == {
        "current_best_frozen_baseline",
        "default_baseline",
        "structural_baseline",
        "frequency_baseline",
        "omission_baseline",
        "null_baseline",
    }
    assert all(
        config.previous_consecutive_weight == 0
        for label, config in controls
        if label not in {"current_best_frozen_baseline", "default_baseline"}
    )
    assert len(rows) == len(controls)
    assert rows[0]["frozen_validation"]["window"] == 2
    assert rows[0]["frozen_validation"]["top_1000_hits"] == 1
    assert rows[0]["frozen_validation"]["red5"]["top_100_hits"] == 1


def frozen_summary(
    *,
    objective: float,
    worst_rank: int = 800_000,
    tail1000: int = 0,
    top100: int = 0,
    top1000: int = 0,
    top10000: int = 0,
) -> dict:
    return {
        "config_hash": f"hash-{objective}-{worst_rank}-{tail1000}",
        "frozen_validation": {
            "top_100_hits": top100,
            "top_1000_hits": top1000,
            "top_10000_hits": top10000,
            "worst_rank": worst_rank,
            "rank_quality": {
                "p95_rank": worst_rank,
                "tail_over_750000_count": 1,
                "tail_over_900000_count": 0,
                "tail_over_1000000_count": tail1000,
                "tail_risk_penalty": 1.0 + tail1000,
            },
            "reward": {"objectiveScore": objective},
        },
    }


def test_frozen_validation_promotion_gate_requires_objective_and_tail():
    incumbent = frozen_summary(objective=10.0, worst_rank=800_000)
    better = frozen_summary(objective=12.0, worst_rank=790_000, top10000=1)
    secondary_only = frozen_summary(objective=12.0, worst_rank=790_000)
    worse_tail = frozen_summary(objective=12.0, worst_rank=1_050_000, tail1000=1, top10000=1)
    worse_objective = frozen_summary(objective=9.5, worst_rank=790_000, top10000=1)

    assert frozen_validation_promotion_gate(better, incumbent)["passed"] is True
    secondary_gate = frozen_validation_promotion_gate(secondary_only, incumbent)
    assert secondary_gate["passed"] is False
    assert secondary_gate["primary_hit_passed"] is False
    assert frozen_validation_promotion_gate(worse_tail, incumbent)["passed"] is False
    assert frozen_validation_promotion_gate(worse_objective, incumbent)["passed"] is False
    assert frozen_validation_promotion_gate(better, None)["passed"] is True


def test_target_rank_movement_summarizes_per_issue_delta():
    baseline = {
        "target_results": [
            {"issue": "001", "rank": 100},
            {"issue": "002", "rank": 200},
            {"issue": "003", "rank": 300},
        ]
    }
    candidate = {
        "target_results": [
            {"issue": "001", "rank": 90},
            {"issue": "002", "rank": 205},
            {"issue": "003", "rank": 300},
        ]
    }

    movement = target_rank_movement(candidate, baseline)

    assert movement["target_count"] == 3
    assert movement["changed_target_count"] == 2
    assert movement["improved_count"] == 1
    assert movement["worsened_count"] == 1
    assert movement["median_abs_delta"] == 5.0


def test_prefilter_configs_target_parallel_matches_single_worker():
    universe = [
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
        (3, 10, 15, 20, 25, 33),
        (4, 11, 16, 21, 26, 30),
        (5, 12, 17, 22, 27, 29),
    ]
    history = [
        ("001", universe[0]),
        ("002", universe[1]),
        ("003", universe[2]),
        ("004", universe[3]),
        ("005", universe[4]),
        ("006", universe[0]),
        ("007", universe[1]),
    ]
    base = FrequencyRankerConfig()
    elite = FrequencyRankerConfig(structural_weight=0.35, frequency_weight=0.40, omission_weight=0.20)
    configs = (
        base,
        elite,
        FrequencyRankerConfig(structural_weight=0.10, frequency_weight=0.80, omission_weight=0.05),
        FrequencyRankerConfig(structural_weight=0.80, frequency_weight=0.10, omission_weight=0.05),
    )
    matrix = build_ranked_universe(universe)

    serial, serial_metadata = prefilter_configs(
        history=history,
        ranked_universe=matrix,
        configs=configs,
        keep_configs=(base, elite),
        train_window=2,
        train_mode="expanding",
        eval_window=5,
        top_n=10000,
        workers=1,
        pool=None,
        round_index=1,
        stride=1,
        promote_limit=2,
    )
    parallel, parallel_metadata = prefilter_configs(
        history=history,
        ranked_universe=matrix,
        configs=configs,
        keep_configs=(base, elite),
        train_window=2,
        train_mode="expanding",
        eval_window=5,
        top_n=10000,
        workers=2,
        pool=None,
        round_index=1,
        stride=1,
        promote_limit=2,
    )

    assert [config_hash(config) for config in parallel] == [config_hash(config) for config in serial]
    assert parallel_metadata["target_count"] == serial_metadata["target_count"] == 5
    assert parallel_metadata["target_worker_count"] == 2
    assert [item["config_hash"] for item in parallel_metadata["top_preview"]] == [
        item["config_hash"] for item in serial_metadata["top_preview"]
    ]


def test_evaluate_configs_target_parallel_matches_single_worker():
    universe = [
        (1, 8, 13, 18, 23, 31),
        (2, 9, 14, 19, 24, 32),
        (3, 10, 15, 20, 25, 33),
        (4, 11, 16, 21, 26, 30),
        (5, 12, 17, 22, 27, 29),
    ]
    history = [
        ("001", universe[0]),
        ("002", universe[1]),
        ("003", universe[2]),
        ("004", universe[3]),
        ("005", universe[4]),
        ("006", universe[0]),
    ]
    configs = (
        FrequencyRankerConfig(),
        FrequencyRankerConfig(structural_weight=0.2, frequency_weight=0.6, omission_weight=0.1),
    )
    matrix = build_ranked_universe(universe)

    single = evaluate_configs(
        history=history,
        ranked_universe=matrix,
        configs=configs,
        train_window=2,
        train_mode="expanding",
        eval_window=3,
        top_n=10000,
        workers=1,
        pool=None,
        progress_interval=0,
        round_index=1,
    )
    parallel = evaluate_configs(
        history=history,
        ranked_universe=matrix,
        configs=configs,
        train_window=2,
        train_mode="expanding",
        eval_window=3,
        top_n=10000,
        workers=2,
        pool=None,
        progress_interval=0,
        round_index=1,
    )

    assert parallel == single


def test_training_event_post_failure_is_non_fatal():
    sent = post_training_event({"run_id": "event-test"}, event_url="http://127.0.0.1:9/training-events/status", timeout=0.05)

    assert sent is False


def test_training_event_warning_is_rate_limited():
    supervisor._TRAINING_EVENT_WARNING_LAST.clear()

    assert should_log_training_event_warning("http://127.0.0.1:9", now=100.0) is True
    assert should_log_training_event_warning("http://127.0.0.1:9", now=120.0) is False
    assert should_log_training_event_warning("http://127.0.0.1:9", now=161.0) is True


def test_training_event_payload_is_compact_signal_only():
    payload = training_event_payload(
        {
            "run_id": "run-1",
            "status": "running",
            "pid": 12345,
            "updated_at": "2026-06-17T12:00:00",
            "latest_progress": {"round": 1},
            "search_base": {"source": "challenger_best"},
            "status_path": "/tmp/status.json",
            "report_path": "/tmp/status.md",
            "rounds": [{"large": "payload"}],
            "best": {"large": "payload"},
        }
    )

    assert payload == {
        "run_id": "run-1",
        "status": "running",
        "pid": 12345,
        "updated_at": "2026-06-17T12:00:00",
        "latest_progress": {"round": 1},
        "search_base": {"source": "challenger_best"},
        "status_path": "/tmp/status.json",
        "report_path": "/tmp/status.md",
    }


def test_write_status_uses_atomic_writer(monkeypatch, tmp_path):
    writes = []

    def fake_atomic_write_text(path, text):
        writes.append((path.name, text))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    monkeypatch.setattr(supervisor, "atomic_write_text", fake_atomic_write_text)

    supervisor.write_status(tmp_path / "status.json", {"run_id": "run-1", "status": "running"})

    assert [name for name, _ in writes] == ["status.json"]
    assert json.loads(writes[0][1]) == {"run_id": "run-1", "status": "running"}


def test_write_report_uses_atomic_writer(monkeypatch, tmp_path):
    writes = []

    def fake_atomic_write_text(path, text):
        writes.append((path.name, text))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    monkeypatch.setattr(supervisor, "atomic_write_text", fake_atomic_write_text)
    status = {
        "run_id": "run-1",
        "started_at": "2026-06-30T00:00:00",
        "updated_at": "2026-06-30T00:01:00",
        "deadline": None,
        "status": "running",
        "train_mode": "expanding",
        "train_window": 900,
        "eval_window": 100,
        "top_n": 10000,
        "workers": 1,
        "memory_budget_gb": 20,
        "universe_size": 1105506,
        "qian_kun": {"latest_issue": "2026073", "latest_label": "家人卦", "latest_pattern": "101011"},
        "rounds": [],
        "best": {"config": {}, "top_10000_hits": 0},
    }

    supervisor.write_report(tmp_path / "status.md", status)

    assert [name for name, _ in writes] == ["status.md"]
    assert writes[0][1].startswith("# DEHPS 24h Training Supervisor Report")


def test_training_line_round_payload_prefers_line_eval_window():
    payload = supervisor.training_line_round_payload(
        run_id="run-1",
        round_index=2,
        line_key="dynamic_kdj_near",
        line_label="Near-term Dynamic KDJ",
        line_kind="dynamic_kdj_near_training",
        policy_key="policy-1",
        policy_params={},
        summary={
            "status": "evaluated",
            "eval_window": 9,
            "top_100_hits": 0,
            "top_1000_hits": 0,
            "top_10000_hits": 0,
            "red5": {"top_100_hits": 0, "top_1000_hits": 0, "top_10000_hits": 0},
            "leakage_passed": True,
        },
        status={"train_mode": "expanding", "train_window": 900, "eval_window": 100, "top_n": 10000},
        train_mode_override="rolling",
    )

    assert payload["eval_window"] == 9
    assert payload["train_mode"] == "rolling"
    assert payload["train_window"] == 900


def test_compact_status_payload_includes_probability_focus_diagnostics():
    payload = compact_status_payload(
        {
            "run_id": "run-1",
            "near_miss_inversion_advisor": {"latest": {"candidate_count": 2}},
            "probability_focus": {"latest": {"active": True, "remaining_rounds": 3}},
            "rounds": [{"large": "payload"}],
            "best": {"large": "payload"},
        }
    )

    assert payload["near_miss_inversion_advisor"] == {"latest": {"candidate_count": 2}}
    assert payload["probability_focus"] == {"latest": {"active": True, "remaining_rounds": 3}}
    assert "rounds" not in payload
    assert "best" not in payload


def test_compact_status_payload_includes_supervisor_continuity_seed():
    continuity = {
        "mode": "same_history_validated_navigation_replay",
        "eligible": True,
        "selected_config_hash": "continuity-hash",
    }

    payload = compact_status_payload({"continuity_seed": continuity})

    assert payload["continuity_seed"] == continuity


def test_compact_status_payload_includes_strategy_memory_continuity():
    continuity = {
        "mode": "same_history_persisted_self_diagnostics",
        "record_count": 7,
        "selection_changed": False,
        "selection_uses_frozen_validation": False,
    }

    payload = compact_status_payload({"strategy_memory_continuity": continuity})

    assert payload["strategy_memory_continuity"] == continuity


def test_compact_status_payload_includes_sequential_null_ledger():
    ledger = {
        "protocol": "dehps-sequential-null-ledger-v1",
        "total_round_count": 307,
        "observed_diagnostic_round_count": 13,
        "legacy_uncounted_round_count": 294,
        "observed_candidate_hypothesis_count": 233,
        "observed_familywise_hypothesis_count": 699,
        "sequential_search_multiplicity_counted": False,
    }

    payload = compact_status_payload({"sequential_null_ledger": ledger})

    assert payload["sequential_null_ledger"] == ledger


def test_self_diagnostics_report_exposes_sequential_null_lower_bound():
    section = supervisor.self_diagnostics_report_section(
        {
            "self_diagnostics": {
                "synthesis": {"status": "noise_risk", "action": "require_forward"},
                "weight_trust": {"status": "caution", "score": 0.5, "action": "observe"},
                "candidate_space": {
                    "status": "diverse",
                    "active_refined_source_count": 5,
                    "unique_top_rank_signature_count": 10,
                },
                "signal_vs_noise": {
                    "status": "noise_risk",
                    "eval_window": 80,
                    "overfit_guard_active": True,
                    "sequential_family": {
                        "observed_diagnostic_round_count": 13,
                        "total_round_count": 307,
                        "observed_candidate_hypothesis_count": 233,
                        "observed_familywise_hypothesis_count": 699,
                        "legacy_uncounted_round_count": 294,
                        "adaptive_hypothesis_generation_counted": False,
                    },
                },
            }
        }
    )

    assert "observed rounds `13/307`" in section
    assert "candidate tests `233`" in section
    assert "family `699`" in section
    assert "legacy uncounted `294`" in section


def test_compact_status_payload_includes_prediction_input_boundary():
    boundary = {
        "protocol": "dehps-draw-outcome-input-boundary-v1",
        "status": "passed",
        "training_fields": ["issue", "draw_date", "red_numbers"],
        "selected_market_aggregate_fields": [],
        "ticket_distribution_observed": False,
    }

    payload = compact_status_payload({"prediction_input_boundary": boundary})

    assert payload["prediction_input_boundary"] == boundary


def test_prediction_input_boundary_report_states_non_identifiability_and_no_promotion():
    section = supervisor.prediction_input_boundary_report_section(
        {
            "prediction_input_boundary": {
                "protocol": "dehps-draw-outcome-input-boundary-v1",
                "status": "passed",
                "training_fields": ["issue", "draw_date", "red_numbers"],
                "selected_market_aggregate_fields": [],
                "ticket_distribution_observed": False,
                "ticket_distribution_identifiability": (
                    "aggregate_prize_counts_do_not_identify_ticket_level_number_selection"
                ),
                "market_data_role": "separate_observation_only_not_draw_probability",
                "draw_probability_effect": "none",
                "selection_changed": False,
                "promotion_allowed": False,
            }
        }
    )

    assert "status `passed`" in section
    assert "aggregate_prize_counts_do_not_identify_ticket_level_number_selection" in section
    assert "draw-probability effect `none`" in section
    assert "promotion allowed: `False`" in section


def test_compact_status_payload_includes_round_summary_without_full_rounds():
    payload = compact_status_payload(
        {
            "run_id": "run-1",
            "rounds": [
                {
                    "round": 1,
                    "phase": "large",
                    "step": 0.2,
                    "improved": True,
                    "best": {
                        "top_100_hits": 1,
                        "top_1000_hits": 2,
                        "top_10000_hits": 3,
                        "median_rank": 12345.0,
                        "best_rank": 42,
                        "worst_rank": 999999,
                        "red5": {"top_10000_hits": 7},
                        "rank_quality": {
                            "top_50000_hits": 4,
                            "tail_over_1000000_count": 0,
                        },
                        "reward": {"objectiveScore": 12.34},
                    },
                    "top_results": [{"large": "payload"}],
                },
                {
                    "round": 2,
                    "phase": "medium",
                    "step": 0.1,
                    "improved": False,
                    "best": {
                        "top_100_hits": 1,
                        "top_1000_hits": 2,
                        "top_10000_hits": 3,
                        "median_rank": 23456.0,
                        "best_rank": 84,
                        "worst_rank": 888888,
                        "red5": {"top_10000_hits": 8},
                        "rank_quality": {
                            "top_50000_hits": 5,
                            "tail_over_1000000_count": 1,
                        },
                        "reward": {"objectiveScore": 23.45},
                    },
                    "top_results": [{"large": "payload"}],
                },
            ],
            "best": {"large": "payload"},
        }
    )

    assert payload["round_summary"] == {
        "round_count": 2,
        "latest_round": 2,
        "last_improved_round": 1,
        "stagnation_rounds": 1,
        "latest_metrics": {
            "phase": "medium",
            "step": 0.1,
            "improved": False,
            "top_100_hits": 1,
            "top_1000_hits": 2,
            "top_10000_hits": 3,
            "red5_top_10000_hits": 8,
            "top_50000_hits": 5,
            "tail_over_1000000_count": 1,
            "median_rank": 23456.0,
            "best_rank": 84,
            "worst_rank": 888888,
            "objective_score": 23.45,
        },
    }
    assert "rounds" not in payload
    assert "best" not in payload


def test_compact_status_payload_keeps_latest_progress_separate_from_completed_rounds():
    latest_progress = {
        "logged_at": "2026-07-10T14:01:33",
        "round": 3,
        "target_index": 60,
        "target_total": 100,
        "issue": "2026037",
        "train_draws": 1456,
        "elapsed_seconds": 33.5,
    }

    payload = compact_status_payload(
        {
            "run_id": "run-1",
            "latest_progress": latest_progress,
            "rounds": [
                {
                    "round": 1,
                    "improved": False,
                    "best": {"top_10000_hits": 2},
                },
                {
                    "round": 2,
                    "improved": False,
                    "best": {"top_10000_hits": 3},
                },
            ],
        }
    )

    assert payload["latest_progress"] == latest_progress
    assert payload["round_summary"]["round_count"] == 2
    assert payload["round_summary"]["latest_round"] == 2
    assert payload["round_summary"]["stagnation_rounds"] == 2
    assert "target_index" not in payload["round_summary"]


def test_training_progress_payload_is_json_status_compatible():
    payload = training_progress_payload(
        round_index=2,
        target_index=7,
        target_total=100,
        issue="2026068",
        train_draws=1400,
        elapsed_seconds=12.34,
        logged_at="2026-06-17T12:00:00",
    )

    assert payload == {
        "logged_at": "2026-06-17T12:00:00",
        "round": 2,
        "target_index": 7,
        "target_total": 100,
        "issue": "2026068",
        "train_draws": 1400,
        "elapsed_seconds": 12.3,
    }


def test_training_sort_key_prefers_higher_coverage_then_lower_rank():
    weaker = {"top_100_hits": 0, "top_1000_hits": 0, "top_10000_hits": 3, "median_rank": 600000, "best_rank": 4000}
    stronger = {"top_100_hits": 0, "top_1000_hits": 0, "top_10000_hits": 4, "median_rank": 900000, "best_rank": 8000}
    tie_better_rank = {
        "top_100_hits": 0,
        "top_1000_hits": 0,
        "top_10000_hits": 3,
        "median_rank": 500000,
        "best_rank": 5000,
    }

    assert sort_key(stronger) > sort_key(weaker)
    assert sort_key(tie_better_rank) > sort_key(weaker)


def test_training_sort_key_prefers_top1000_over_extra_top10000_hit():
    top1000_hit = {
        "top_100_hits": 0,
        "top_1000_hits": 1,
        "top_10000_hits": 3,
        "median_rank": 650000,
        "best_rank": 864,
        "worst_rank": 1_096_000,
    }
    extra_top10000_hit = {
        "top_100_hits": 0,
        "top_1000_hits": 0,
        "top_10000_hits": 4,
        "median_rank": 590000,
        "best_rank": 3238,
        "worst_rank": 1_090_000,
    }

    assert reward_summary(top1000_hit)["hitReward"] > reward_summary(extra_top10000_hit)["hitReward"]
    assert sort_key(top1000_hit) > sort_key(extra_top10000_hit)


def test_reward_summary_penalizes_worse_rank_inside_same_hit_counts():
    better_rank = {
        "top_100_hits": 0,
        "top_1000_hits": 1,
        "top_10000_hits": 3,
        "median_rank": 400000,
        "best_rank": 500,
        "worst_rank": 900000,
    }
    worse_rank = {
        **better_rank,
        "median_rank": 700000,
        "worst_rank": 1_000_000,
    }

    assert reward_summary(better_rank)["objectiveScore"] > reward_summary(worse_rank)["objectiveScore"]
    assert sort_key(better_rank) > sort_key(worse_rank)


def test_binomial_upper_tail_probability_is_exact_for_small_cases():
    assert binomial_upper_tail_probability(2, 0, 0.5) == 1.0
    assert binomial_upper_tail_probability(2, 1, 0.5) == 0.75
    assert binomial_upper_tail_probability(2, 2, 0.5) == 0.25


def test_probability_calibration_records_null_lift_and_near_miss_windows():
    summary = {
        "evaluated_draws": 100,
        "top_100_hits": 2,
        "top_1000_hits": 3,
        "top_10000_hits": 3,
        "best_rank": 47,
        "median_rank": 564132,
        "worst_rank": 1_100_000,
        "rank_quality": {
            "top_50000_hits": 4,
            "p90_rank": 917953,
            "p95_rank": 982913,
        },
        "target_results": [
            {"issue": "near_top100", "rank": 408},
            {"issue": "near_top1000", "rank": 1500},
            {"issue": "near_top10000", "rank": 45362},
        ],
    }

    diagnostics = probability_calibration_diagnostics(summary, universe_size=1_000_000)

    assert diagnostics["mode"] == "null_binomial_rank_calibration_v0"
    assert diagnostics["bands"][0]["label"] == "top_100"
    assert diagnostics["bands"][0]["expected_hits"] == 0.01
    assert diagnostics["bands"][0]["lift_vs_null"] == 200.0
    assert diagnostics["bands"][3]["label"] == "top_50000"
    assert diagnostics["bands"][3]["expected_hits"] == 5.0
    assert diagnostics["rank_percentiles"]["best"] == 0.999954
    assert [window["count"] for window in diagnostics["near_miss_windows"]] == [1, 1, 1]
    assert diagnostics["near_miss_windows"][0]["issues"] == ["near_top100"]


def test_rank_quality_reward_keeps_tail_improvements_visible():
    better_tail = {
        "top_100_hits": 0,
        "top_1000_hits": 0,
        "top_10000_hits": 3,
        "median_rank": 400000,
        "best_rank": 3000,
        "worst_rank": 700000,
        "rank_quality": {
            "top_50000_hits": 8,
            "top_100000_hits": 12,
            "top_250000_hits": 30,
            "top_500000_hits": 60,
            "reward": 4.0,
        },
    }
    worse_tail = {
        **better_tail,
        "median_rank": 600000,
        "worst_rank": 1_050_000,
        "rank_quality": {
            "top_50000_hits": 4,
            "top_100000_hits": 8,
            "top_250000_hits": 20,
            "top_500000_hits": 45,
            "reward": 1.0,
        },
    }

    assert reward_summary(better_tail)["rankQualityReward"] > reward_summary(worse_tail)["rankQualityReward"]
    assert reward_summary(better_tail)["objectiveScore"] > reward_summary(worse_tail)["objectiveScore"]
    assert sort_key(better_tail) > sort_key(worse_tail)


def test_tail_risk_penalty_strongly_punishes_million_rank_outliers():
    stable_tail = {
        "top_100_hits": 0,
        "top_1000_hits": 1,
        "top_10000_hits": 3,
        "median_rank": 520000,
        "best_rank": 864,
        "worst_rank": 820000,
        "rank_quality": {
            "top_50000_hits": 5,
            "top_100000_hits": 8,
            "top_250000_hits": 24,
            "top_500000_hits": 41,
            "p95_rank": 780000,
            "tail_over_750000_count": 3,
            "tail_over_900000_count": 0,
            "tail_over_1000000_count": 0,
            "reward": 1.7,
        },
    }
    million_tail = {
        **stable_tail,
        "median_rank": 590000,
        "worst_rank": 1_097_823,
        "rank_quality": {
            **stable_tail["rank_quality"],
            "p95_rank": 1_030_000,
            "tail_over_750000_count": 12,
            "tail_over_900000_count": 7,
            "tail_over_1000000_count": 3,
        },
    }

    stable_reward = reward_summary(stable_tail)
    million_reward = reward_summary(million_tail)

    assert million_reward["tailRiskPenalty"] > stable_reward["tailRiskPenalty"] + 10
    assert stable_reward["objectiveScore"] > million_reward["objectiveScore"]
    assert sort_key(stable_tail) > sort_key(million_tail)


def test_calculate_tail_risk_penalty_is_threshold_and_shape_sensitive():
    low_tail = calculate_tail_risk_penalty(
        median_rank=400000,
        worst_rank=700000,
        p95_rank=650000,
        tail_over_750000_count=0,
        tail_over_900000_count=0,
        tail_over_1000000_count=0,
        universe_size=1_107_568,
    )
    high_tail = calculate_tail_risk_penalty(
        median_rank=600000,
        worst_rank=1_080_000,
        p95_rank=1_010_000,
        tail_over_750000_count=15,
        tail_over_900000_count=8,
        tail_over_1000000_count=4,
        universe_size=1_107_568,
    )

    assert high_tail > low_tail
    assert high_tail - low_tail > 20


def test_red5_reward_is_low_weight_and_cannot_override_exact_top1000():
    red5_top100_heavy = {
        "top_100_hits": 0,
        "top_1000_hits": 0,
        "top_10000_hits": 3,
        "median_rank": 400000,
        "best_rank": 3000,
        "worst_rank": 900000,
        "red5": {"top_100_hits": 20, "top_1000_hits": 35, "top_10000_hits": 80},
    }
    exact_top1000 = {
        "top_100_hits": 0,
        "top_1000_hits": 1,
        "top_10000_hits": 3,
        "median_rank": 650000,
        "best_rank": 864,
        "worst_rank": 1_096_000,
        "red5": {"top_100_hits": 0, "top_1000_hits": 0, "top_10000_hits": 0},
    }

    assert reward_summary(red5_top100_heavy)["red5Reward"] > 0
    assert reward_summary(red5_top100_heavy)["hitReward"] == 9
    assert sort_key(exact_top1000) > sort_key(red5_top100_heavy)


def _summary_for_overlap_test(config: FrequencyRankerConfig, issue_ranks: dict[str, int]) -> dict:
    ranks = list(issue_ranks.values())
    target_results = [
        {
            "issue": issue,
            "rank": rank,
            "hit_top_100": rank <= 100,
            "hit_top_1000": rank <= 1000,
            "hit_top_10000": rank <= 10000,
        }
        for issue, rank in issue_ranks.items()
    ]
    return {
        "config": config.__dict__,
        "config_hash": config_hash(config),
        "evaluated_draws": len(target_results),
        "top_100_hits": sum(rank <= 100 for rank in ranks),
        "top_1000_hits": sum(rank <= 1000 for rank in ranks),
        "top_10000_hits": sum(rank <= 10000 for rank in ranks),
        "median_rank": sorted(ranks)[len(ranks) // 2],
        "best_rank": min(ranks),
        "worst_rank": max(ranks),
        "red5": {"top_100_hits": 0, "top_1000_hits": 0, "top_10000_hits": 0},
        "rank_quality": {"reward": 0, "tail_over_750000_count": 0, "tail_over_900000_count": 0, "tail_over_1000000_count": 0},
        "target_results": target_results,
    }


def test_baseline_overlap_marks_unique_and_overlapped_hits():
    candidate_config = FrequencyRankerConfig(frequency_weight=0.44)
    default_config = FrequencyRankerConfig()
    null_config = FrequencyRankerConfig(structural_weight=0.0, frequency_weight=0.0, omission_weight=0.0, previous_consecutive_weight=0.0)
    candidate = _summary_for_overlap_test(candidate_config, {"2026001": 48, "2026002": 500, "2026003": 9000})
    default = _summary_for_overlap_test(default_config, {"2026002": 8000, "2026004": 700000})
    null = _summary_for_overlap_test(null_config, {"2026001": 9000, "2026005": 800000})
    summaries = [candidate, default, null]

    attach_baseline_overlap(
        summaries,
        (("default_baseline", default_config), ("null_baseline", null_config)),
        universe_size=1_107_568,
    )

    assert target_hit_issues(candidate, cutoff=10000) == {"2026001", "2026002", "2026003"}
    top10000 = candidate["baseline_overlap"]["bands"]["top_10000"]
    assert top10000["unique_hit_issues"] == ["2026003"]
    assert top10000["overlap_hit_issues"] == ["2026001", "2026002"]
    assert candidate["reward"]["baselineUniqueReward"] == 374
    assert candidate["reward"]["baselineOverlapPenalty"] == 6


def test_sort_key_prefers_unique_baseline_beating_top10000_hits():
    default_config = FrequencyRankerConfig()
    null_config = FrequencyRankerConfig(structural_weight=0.0, frequency_weight=0.0, omission_weight=0.0, previous_consecutive_weight=0.0)
    unique_config = FrequencyRankerConfig(frequency_weight=0.44)
    overlapped_config = FrequencyRankerConfig(frequency_weight=0.45)
    default = _summary_for_overlap_test(default_config, {"2026001": 9000, "2026002": 9100, "2026003": 9200})
    null = _summary_for_overlap_test(null_config, {"2026004": 9300, "2026005": 9400, "2026006": 9500})
    unique = _summary_for_overlap_test(unique_config, {"2026007": 9000, "2026008": 9100, "2026009": 9200})
    overlapped = _summary_for_overlap_test(overlapped_config, {"2026001": 9000, "2026002": 9100, "2026003": 9200})
    summaries = [unique, overlapped, default, null]

    attach_baseline_overlap(
        summaries,
        (("default_baseline", default_config), ("null_baseline", null_config)),
        universe_size=1_107_568,
    )

    assert unique["top_10000_hits"] == overlapped["top_10000_hits"] == 3
    assert unique["reward"]["objectiveScore"] > overlapped["reward"]["objectiveScore"]
    assert sort_key(unique) > sort_key(overlapped)


def test_summarize_target_ranks_counts_red5_difference_numbers():
    config = FrequencyRankerConfig()
    target_ranks = [
        TargetRank(
            issue="2026001",
            rank=12000,
            score=0.5,
            hit_top_100=False,
            hit_top_1000=False,
            hit_top_10000=False,
            red5_rank=88,
            red5_score=0.6,
            red5_numbers=(1, 2, 3, 4, 5, 7),
            red5_missing_number=6,
            red5_extra_number=7,
            hit_red5_top_100=True,
            hit_red5_top_1000=True,
            hit_red5_top_10000=True,
        )
    ]

    summary = summarize_target_ranks(
        target_ranks=target_ranks,
        config=config,
        as_of_issue="2026001",
        history_fingerprint_value="history-1",
        train_window=900,
        train_mode="expanding",
        top_n=10000,
        universe_size=1_107_568,
    )

    assert summary["red5"]["top_100_hits"] == 1
    assert summary["red5"]["missing_counts"] == {"06": 1}
    assert summary["red5"]["extra_counts"] == {"07": 1}
    assert summary["red5"]["pairs"] == [{"missing_number": 6, "extra_number": 7, "count": 1}]
    assert summary["red5"]["examples"][0]["issue"] == "2026001"
    assert summary["target_results"] == [
        {
            "issue": "2026001",
            "draw_date": None,
            "red_numbers": [],
            "rank": 12000,
            "score": 0.5,
            "hit_top_100": False,
            "hit_top_1000": False,
            "hit_top_10000": False,
            "red5_rank": 88,
            "red5_score": 0.6,
            "red5_numbers": [1, 2, 3, 4, 5, 7],
            "red5_missing_number": 6,
            "red5_extra_number": 7,
            "hit_red5_top_100": True,
            "hit_red5_top_1000": True,
            "hit_red5_top_10000": True,
        }
    ]
    assert summary["reward"]["red5Reward"] > 0
    assert summary["rank_quality"]["top_50000_hits"] == 1
    assert summary["rank_quality"]["tail_over_1000000_count"] == 0
    assert summary["reward"]["tailRiskPenalty"] > 0
    assert summary["reward"]["rankQualityReward"] > 0
    assert summary["probability_calibration"]["mode"] == "null_binomial_rank_calibration_v0"
    assert summary["probability_calibration"]["bands"][2]["label"] == "top_10000"


def test_load_prior_supervisor_candidates_keeps_same_protocol_global_best(tmp_path):
    config = FrequencyRankerConfig(frequency_weight=0.765, omission_weight=0)
    summary = {
        "config": {key: value for key, value in config.__dict__.items() if key != "stable_range_weight"},
        "as_of_issue": "2026067",
        "history_fingerprint": "history-1",
        "config_hash": config_hash(config),
        "evaluated_draws": 100,
        "top_100_hits": 0,
        "top_1000_hits": 1,
        "top_10000_hits": 3,
        "median_rank": 585483.5,
        "best_rank": 864,
        "worst_rank": 1_096_000,
        "run_key": "prior-best",
    }
    current = tmp_path / "training-supervisor-current.json"
    prior = tmp_path / "training-supervisor-prior.json"
    current.write_text("{}")
    prior.write_text(
        json.dumps(
            {
                "train_window": 900,
                "train_mode": "expanding",
                "eval_window": 100,
                "top_n": 10000,
                "best": summary,
                "rounds": [{"best": summary, "top_results": [summary]}],
            }
        )
    )

    candidates = load_prior_supervisor_candidates(
        output_dir=tmp_path,
        current_status_path=current,
        as_of_issue="2026067",
        history_fingerprint_value="history-1",
        train_window=900,
        train_mode="expanding",
        eval_window=100,
        top_n=10000,
        universe_size=1_107_568,
    )

    assert candidates[0]["run_key"] == "prior-best"
    assert candidates[0]["top_1000_hits"] == 1
    assert candidates[0]["reward"]["hitReward"] == 189
    assert candidates[0]["config"]["stable_range_weight"] == 0


def test_carryover_candidate_configs_replay_only_cross_history_configs():
    old_config = FrequencyRankerConfig(frequency_weight=0.765, omission_weight=0)
    current_config = FrequencyRankerConfig(frequency_weight=0.111, omission_weight=0)
    old_summary = {
        "config": old_config.__dict__,
        "as_of_issue": "2026068",
        "history_fingerprint": "history-old",
        "evaluated_draws": 100,
        "top_100_hits": 2,
        "top_1000_hits": 3,
        "top_10000_hits": 3,
        "median_rank": 579314.5,
        "best_rank": 48,
        "worst_rank": 1_100_657,
        "run_key": "old-best",
    }
    current_summary = {
        "config": current_config.__dict__,
        "as_of_issue": "2026070",
        "history_fingerprint": "history-current",
        "evaluated_draws": 100,
        "top_100_hits": 0,
        "top_1000_hits": 1,
        "top_10000_hits": 2,
        "median_rank": 522990,
        "best_rank": 441,
        "worst_rank": 1_097_472,
        "run_key": "current-best",
    }

    configs = carryover_candidate_configs_from_summaries(
        [current_summary, old_summary, old_summary],
        current_as_of_issue="2026070",
        current_history_fingerprint="history-current",
        universe_size=1_107_568,
    )

    assert configs == (old_config,)


def test_load_prior_supervisor_carryover_configs_keeps_matching_protocol_only(tmp_path):
    carryover_config = FrequencyRankerConfig(frequency_weight=0.765, omission_weight=0)
    wrong_protocol_config = FrequencyRankerConfig(frequency_weight=0.333, omission_weight=0)
    carryover_summary = {
        "config": carryover_config.__dict__,
        "as_of_issue": "2026068",
        "history_fingerprint": "history-old",
        "evaluated_draws": 100,
        "top_100_hits": 2,
        "top_1000_hits": 3,
        "top_10000_hits": 3,
        "median_rank": 579314.5,
        "best_rank": 48,
        "worst_rank": 1_100_657,
        "run_key": "carryover-best",
    }
    wrong_protocol_summary = {
        **carryover_summary,
        "config": wrong_protocol_config.__dict__,
        "run_key": "wrong-protocol",
    }
    current = tmp_path / "training-supervisor-current.json"
    matching = tmp_path / "training-supervisor-prior.json"
    wrong_protocol = tmp_path / "training-supervisor-wrong-protocol.json"
    current.write_text("{}")
    matching.write_text(
        json.dumps(
            {
                "train_window": 900,
                "train_mode": "expanding",
                "eval_window": 100,
                "top_n": 10000,
                "best": carryover_summary,
                "rounds": [{"best": carryover_summary, "top_results": [carryover_summary]}],
            }
        )
    )
    wrong_protocol.write_text(
        json.dumps(
            {
                "train_window": 600,
                "train_mode": "expanding",
                "eval_window": 100,
                "top_n": 10000,
                "best": wrong_protocol_summary,
            }
        )
    )

    configs = load_prior_supervisor_carryover_configs(
        output_dir=tmp_path,
        current_status_path=current,
        current_as_of_issue="2026070",
        current_history_fingerprint="history-current",
        train_window=900,
        train_mode="expanding",
        eval_window=100,
        top_n=10000,
        universe_size=1_107_568,
    )

    assert configs == (carryover_config,)


def test_merge_config_candidates_dedupes_by_config_hash():
    first = FrequencyRankerConfig(frequency_weight=0.765, omission_weight=0)
    duplicate = FrequencyRankerConfig(frequency_weight=0.765, omission_weight=0)
    second = FrequencyRankerConfig(frequency_weight=0.333, omission_weight=0)

    configs = merge_config_candidates((first, duplicate), (second,), limit=4)

    assert configs == (first, second)
