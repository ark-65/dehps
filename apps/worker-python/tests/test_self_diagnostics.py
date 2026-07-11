from __future__ import annotations

from dehps.optimization.self_diagnostics import (
    build_specialist_strategy_memory,
    build_prediction_self_diagnostics,
    candidate_space_diagnostic,
    signal_vs_noise_diagnostic,
    weight_trust_diagnostic,
)


def test_weight_trust_blocks_leakage_and_missing_dynamic_offset():
    diagnostic = weight_trust_diagnostic(
        {
            "eval_window": 9,
            "changed_target_count": 9,
            "fallback_target_count": 0,
            "leakage_passed": False,
        },
        dynamic_metadata={"leakage_passed": False, "applied_offsets": {}},
    )

    assert diagnostic["status"] == "blocked"
    assert diagnostic["action"] == "do_not_trust_dynamic_weight"
    assert "leakage_guard_failed" in diagnostic["reasons"]
    assert "no_current_dynamic_offset_applied" in diagnostic["reasons"]


def test_candidate_space_diagnostic_detects_collapsed_top_window():
    candidates = [
        (index + 1, (1, 2, 3, 4, 5, 6 + index % 2), 1.0)
        for index in range(30)
    ]

    diagnostic = candidate_space_diagnostic(candidates)

    assert diagnostic["status"] == "collapsed"
    assert diagnostic["unique_red_number_count"] <= 7
    assert "top_candidates_use_too_few_red_numbers" in diagnostic["reasons"]


def test_signal_vs_noise_marks_small_window_as_noise_risk():
    diagnostic = signal_vs_noise_diagnostic(
        {"eval_window": 9, "top_100_hits": 3, "top_1000_hits": 3, "top_10000_hits": 3},
        legal_sample_space=1_107_568,
    )

    assert diagnostic["status"] == "noise_risk"
    assert "small_regression_window" in diagnostic["reasons"]
    assert diagnostic["strongest_band"]["label"] in {"top_100", "top_1000", "top_10000"}
    assert diagnostic["minimum_familywise_hypothesis_count"] == 3
    assert diagnostic["sequential_search_multiplicity_counted"] is False


def test_signal_vs_noise_uses_minimum_familywise_adjustment_for_candidate_selection():
    summary = {
        "eval_window": 80,
        "top_100_hits": 0,
        "top_1000_hits": 2,
        "top_10000_hits": 2,
    }

    single_candidate = signal_vs_noise_diagnostic(
        summary,
        legal_sample_space=1_105_506,
        candidate_hypothesis_count=1,
    )
    selected_from_two = signal_vs_noise_diagnostic(
        summary,
        legal_sample_space=1_105_506,
        candidate_hypothesis_count=2,
    )

    assert single_candidate["status"] == "candidate_signal"
    assert selected_from_two["status"] == "noise_risk"
    assert selected_from_two["minimum_familywise_hypothesis_count"] == 6
    assert selected_from_two["strongest_band"]["label"] == "top_1000"
    assert selected_from_two["strongest_band"]["binomial_tail_p_value"] < 0.01
    assert selected_from_two["strongest_band"]["bonferroni_adjusted_p_value"] > 0.01
    assert all(
        0.0 <= band["bonferroni_adjusted_p_value"] <= 1.0
        for band in selected_from_two["bands"]
    )
    assert "historical_lift_not_strong_against_minimum_familywise_null" in selected_from_two["reasons"]


def test_prediction_self_diagnostics_synthesizes_weakest_status():
    payload = build_prediction_self_diagnostics(
        regression_summary={
            "eval_window": 9,
            "changed_target_count": 9,
            "fallback_target_count": 0,
            "leakage_passed": True,
            "top_100_hits": 0,
            "top_1000_hits": 0,
            "top_10000_hits": 0,
        },
        candidates=[(index + 1, (1, 2, 3, 4, 5, 6 + index % 2), 1.0) for index in range(30)],
        legal_sample_space=1_107_568,
        dynamic_metadata={
            "leakage_passed": True,
            "applied_offsets": {"frequency_weight": 0.01},
            "strength_state": {"confidence": 0.5},
        },
    )

    assert payload["synthesis"]["status"] == "collapsed"
    assert payload["candidate_space"]["status"] == "collapsed"
    assert payload["signal_vs_noise"]["status"] == "noise_risk"


def test_specialist_strategy_memory_selects_weight_trust_audit():
    current = {
        "synthesis": {"status": "caution"},
        "weight_trust": {"status": "caution"},
        "candidate_space": {"status": "diverse"},
        "signal_vs_noise": {"status": "candidate_signal"},
    }

    memory = build_specialist_strategy_memory(
        current_diagnostic=current,
        recent_diagnostics=[current],
        round_index=3,
    )

    assert memory["selected_experiment"]["key"] == "weight_trust_audit"
    assert memory["selected_experiment"]["promotion_allowed"] is False
    assert "weight_trust_not_stable" in memory["failure_hypotheses"]


def test_specialist_strategy_memory_selects_near_dynamic_freeze_review():
    current = {
        "synthesis": {"status": "monitor"},
        "weight_trust": {"status": "trusted"},
        "candidate_space": {"status": "diverse"},
        "signal_vs_noise": {"status": "candidate_signal"},
    }

    memory = build_specialist_strategy_memory(
        current_diagnostic=current,
        recent_diagnostics=[],
        round_index=4,
        near_dynamic_training={
            "stagnation_rounds": 2,
            "latest": {
                "status": "evaluated",
                "summary": {
                    "eval_window": 9,
                    "top_100_hits": 0,
                    "top_1000_hits": 0,
                    "top_10000_hits": 0,
                },
            },
        },
    )

    assert memory["selected_experiment"]["key"] == "near_dynamic_freeze_review"
    assert "near_dynamic_window_not_lifting" in memory["failure_hypotheses"]


def test_specialist_strategy_memory_separates_stale_champion_from_candidate_collapse():
    current = {
        "synthesis": {"status": "blocked"},
        "weight_trust": {"status": "blocked"},
        "candidate_space": {
            "status": "diverse",
            "round_best_path_status": "stale",
        },
        "decision_surface": {"status": "mixed_decision_surface"},
        "signal_vs_noise": {"status": "noise_risk"},
    }

    memory = build_specialist_strategy_memory(
        current_diagnostic=current,
        recent_diagnostics=[current],
        round_index=8,
    )

    assert "candidate_space_needs_reframe" not in memory["failure_hypotheses"]
    assert "decision_surface_stale_champion" in memory["failure_hypotheses"]
    assert memory["state"]["current_candidate_space"] == "diverse"
    assert memory["state"]["current_decision_surface"] == "mixed_decision_surface"
    assert memory["state"]["current_round_best_path"] == "stale"
    assert memory["selected_experiment"] == {
        "key": "decision_surface_dominance_audit",
        "action": "audit_objective_dominance_before_expanding_candidate_space",
        "rationale": "Current Top candidates have distinct rank vectors, but the same champion path remains dominant.",
        "promotion_allowed": False,
        "evidence_level": "strategy_memory_observation",
    }


def test_specialist_strategy_memory_routes_objective_tiebreak_tradeoff_audit():
    current = {
        "synthesis": {"status": "blocked"},
        "weight_trust": {"status": "blocked"},
        "candidate_space": {
            "status": "diverse",
            "round_best_path_status": "stale",
        },
        "decision_surface": {"status": "objective_tiebreak_tradeoff"},
        "signal_vs_noise": {"status": "noise_risk"},
    }

    memory = build_specialist_strategy_memory(
        current_diagnostic=current,
        recent_diagnostics=[current],
        round_index=4,
    )

    assert "objective_tiebreak_hides_pareto_tradeoffs" in memory["failure_hypotheses"]
    assert memory["selected_experiment"] == {
        "key": "objective_tiebreak_pareto_audit",
        "action": "predeclare_objective_component_control_without_sort_change",
        "rationale": (
            "Objective score is the first tie-break across non-dominated Top challengers; "
            "record component residuals before any sort experiment."
        ),
        "promotion_allowed": False,
        "evidence_level": "strategy_memory_observation",
    }


def test_specialist_strategy_memory_advances_to_component_residual_stability_audit():
    current = {
        "synthesis": {"status": "blocked"},
        "weight_trust": {"status": "blocked"},
        "candidate_space": {
            "status": "diverse",
            "round_best_path_status": "stale",
        },
        "decision_surface": {
            "status": "objective_tiebreak_tradeoff",
            "objective_component_control": {"status": "measured"},
        },
        "signal_vs_noise": {"status": "noise_risk"},
    }

    memory = build_specialist_strategy_memory(
        current_diagnostic=current,
        recent_diagnostics=[current],
        round_index=5,
    )

    assert "objective_component_residuals_need_stability" in memory["failure_hypotheses"]
    assert "objective_tiebreak_hides_pareto_tradeoffs" not in memory["failure_hypotheses"]
    assert memory["state"]["current_objective_component_control"] == "measured"
    assert memory["state"]["objective_component_control_counts"] == {"measured": 2}
    assert memory["selected_experiment"] == {
        "key": "objective_component_residual_audit",
        "action": "observe_component_residual_stability_without_sort_change",
        "rationale": (
            "Objective components are now reconstructed on the search slice; observe which component "
            "repeatedly controls the local gap before predeclaring any counterfactual sort control."
        ),
        "promotion_allowed": False,
        "evidence_level": "strategy_memory_observation",
    }


def test_specialist_strategy_memory_advances_to_tail_risk_counterfactual_audit():
    current = {
        "synthesis": {"status": "blocked"},
        "weight_trust": {"status": "blocked"},
        "candidate_space": {
            "status": "diverse",
            "round_best_path_status": "stale",
        },
        "decision_surface": {
            "status": "objective_tiebreak_tradeoff",
            "objective_component_control": {"status": "measured"},
            "objective_component_counterfactual": {"status": "measured"},
        },
        "signal_vs_noise": {"status": "noise_risk"},
    }

    memory = build_specialist_strategy_memory(
        current_diagnostic=current,
        recent_diagnostics=[current],
        round_index=6,
    )

    assert "tail_risk_counterfactual_needs_stability" in memory["failure_hypotheses"]
    assert "objective_component_residuals_need_stability" not in memory["failure_hypotheses"]
    assert memory["state"]["current_objective_component_counterfactual"] == "measured"
    assert memory["state"]["objective_component_counterfactual_counts"] == {"measured": 2}
    assert memory["selected_experiment"] == {
        "key": "tail_risk_counterfactual_audit",
        "action": "observe_tail_risk_counterfactual_without_selection_change",
        "rationale": (
            "The mature residual window predeclared a tail-risk-only counterfactual; observe whether "
            "its local Top choice changes while production sorting and promotion remain unchanged."
        ),
        "promotion_allowed": False,
        "evidence_level": "strategy_memory_observation",
    }
