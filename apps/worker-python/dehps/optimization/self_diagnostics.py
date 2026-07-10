from __future__ import annotations

from itertools import combinations
from math import comb, isfinite
from statistics import mean
from typing import Any


SELF_DIAGNOSTICS_PROTOCOL = "dehps-self-diagnostics-v1"
SPECIALIST_STRATEGY_PROTOCOL = "dehps-specialist-strategy-memory-v1"


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return result if isfinite(result) else default


def _rounded(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def binomial_upper_tail_probability(trials: int, hits: int, probability: float) -> float:
    if trials <= 0:
        return 1.0
    safe_hits = max(0, min(int(hits), int(trials)))
    safe_probability = min(1.0, max(0.0, float(probability)))
    if safe_hits <= 0:
        return 1.0
    if safe_probability <= 0.0:
        return 0.0
    if safe_probability >= 1.0:
        return 1.0
    return min(
        1.0,
        max(
            0.0,
            sum(
                comb(int(trials), value)
                * (safe_probability**value)
                * ((1.0 - safe_probability) ** (int(trials) - value))
                for value in range(safe_hits, int(trials) + 1)
            ),
        ),
    )


def _status_rank(status: str) -> int:
    order = {
        "blocked": 0,
        "collapsed": 1,
        "noise_risk": 2,
        "caution": 3,
        "narrow": 4,
        "monitor": 5,
        "candidate_signal": 6,
        "diverse": 7,
        "trusted": 8,
    }
    return order.get(status, 3)


def _extract_numbers(candidate: object) -> tuple[int, ...] | None:
    if isinstance(candidate, dict):
        raw = candidate.get("numbers") or candidate.get("red_numbers") or candidate.get("reds")
    elif isinstance(candidate, (tuple, list)) and len(candidate) >= 2:
        raw = candidate[1]
    else:
        raw = None
    if not isinstance(raw, (tuple, list)) or len(raw) != 6:
        return None
    try:
        numbers = tuple(sorted(int(value) for value in raw))
    except (TypeError, ValueError):
        return None
    return numbers if len(set(numbers)) == 6 else None


def candidate_space_diagnostic(candidates: list[Any] | tuple[Any, ...], *, top_limit: int = 100) -> dict[str, Any]:
    sample = [_extract_numbers(candidate) for candidate in list(candidates)[: max(0, top_limit)]]
    combinations_sample = [numbers for numbers in sample if numbers is not None]
    observed_count = len(combinations_sample)
    unique_combinations = set(combinations_sample)
    duplicate_count = max(0, observed_count - len(unique_combinations))
    unique_red_numbers = sorted({number for numbers in unique_combinations for number in numbers})
    pair_sample = combinations_sample[: min(50, len(combinations_sample))]
    pair_overlaps = [
        len(set(left) & set(right))
        for left, right in combinations(pair_sample, 2)
    ]
    average_pair_overlap = mean(pair_overlaps) if pair_overlaps else 0.0
    max_pair_overlap = max(pair_overlaps) if pair_overlaps else 0
    position_unique_counts: list[int] = []
    if combinations_sample:
        ordered_sample = [tuple(sorted(numbers)) for numbers in combinations_sample]
        for index in range(6):
            position_unique_counts.append(len({numbers[index] for numbers in ordered_sample}))

    reasons: list[str] = []
    status = "diverse"
    if observed_count == 0:
        status = "blocked"
        reasons.append("no_candidate_numbers")
    if duplicate_count > 0:
        status = "collapsed"
        reasons.append("duplicate_combinations_in_top_window")
    if observed_count >= 20 and len(unique_red_numbers) <= 12:
        status = "collapsed"
        reasons.append("top_candidates_use_too_few_red_numbers")
    if observed_count >= 20 and average_pair_overlap >= 4.25:
        status = "collapsed"
        reasons.append("top_candidates_share_too_many_numbers")
    if status == "diverse" and observed_count >= 20 and len(unique_red_numbers) < 18:
        status = "narrow"
        reasons.append("top_candidates_are_narrow_but_not_collapsed")
    if status == "diverse" and observed_count >= 20 and average_pair_overlap >= 3.75:
        status = "narrow"
        reasons.append("top_candidates_have_high_overlap")
    if not reasons:
        reasons.append("candidate_space_has_no_collapse_flag")

    return {
        "status": status,
        "sample_size": observed_count,
        "top_limit": top_limit,
        "unique_combination_count": len(unique_combinations),
        "duplicate_count": duplicate_count,
        "unique_red_number_count": len(unique_red_numbers),
        "unique_red_numbers": unique_red_numbers,
        "position_unique_counts": position_unique_counts,
        "average_pair_overlap": _rounded(average_pair_overlap),
        "max_pair_overlap": max_pair_overlap,
        "reasons": reasons,
    }


def weight_trust_diagnostic(
    summary: dict[str, Any] | None,
    *,
    dynamic_metadata: dict[str, Any] | None = None,
    min_eval_draws: int = 20,
) -> dict[str, Any]:
    summary = summary if isinstance(summary, dict) else {}
    metadata = dynamic_metadata if isinstance(dynamic_metadata, dict) else {}
    eval_window = _safe_int(summary.get("eval_window") or summary.get("evaluated_draws"))
    fallback_count = _safe_int(summary.get("fallback_target_count"))
    changed_count = _safe_int(summary.get("changed_target_count"))
    changed_ratio = changed_count / eval_window if eval_window > 0 else 0.0
    applied_offsets = metadata.get("applied_offsets") if isinstance(metadata.get("applied_offsets"), dict) else {}
    strength_state = metadata.get("strength_state") if isinstance(metadata.get("strength_state"), dict) else {}
    strength_confidence = _safe_float(strength_state.get("confidence"), 0.5)
    leakage_passed = bool(summary.get("leakage_passed", True)) and bool(metadata.get("leakage_passed", True))

    score = 1.0
    reasons: list[str] = []
    if eval_window <= 0:
        score = 0.0
        reasons.append("missing_regression_window")
    if not leakage_passed:
        score = 0.0
        reasons.append("leakage_guard_failed")
    if eval_window and eval_window < min_eval_draws:
        score -= 0.25
        reasons.append("small_regression_window")
    if fallback_count > 0:
        score -= min(0.35, fallback_count / max(1, eval_window) * 0.75)
        reasons.append("dynamic_offsets_missing_for_some_targets")
    if eval_window > 0 and changed_count > 0 and changed_ratio < 0.80:
        score -= 0.25
        reasons.append("dynamic_offsets_do_not_cover_enough_targets")
    if metadata and not applied_offsets:
        score -= 0.35
        reasons.append("no_current_dynamic_offset_applied")
    if strength_confidence < 0.35:
        score -= 0.15
        reasons.append("low_kdj_strength_confidence")

    score = max(0.0, min(1.0, score))
    if score <= 0.20:
        status = "blocked"
        action = "do_not_trust_dynamic_weight"
    elif score < 0.70:
        status = "caution"
        action = "observe_only_or_downweight"
    else:
        status = "trusted"
        action = "eligible_for_monitoring_not_promotion"
    if not reasons:
        reasons.append("no_weight_trust_blocker_detected")
    return {
        "status": status,
        "score": _rounded(score),
        "action": action,
        "eval_window": eval_window,
        "min_eval_draws": min_eval_draws,
        "fallback_target_count": fallback_count,
        "changed_target_count": changed_count,
        "changed_target_ratio": _rounded(changed_ratio),
        "leakage_passed": leakage_passed,
        "applied_offset_count": len(applied_offsets),
        "strength_confidence": _rounded(strength_confidence),
        "reasons": reasons,
    }


def signal_vs_noise_diagnostic(
    summary: dict[str, Any] | None,
    *,
    legal_sample_space: int,
    min_eval_draws: int = 20,
    forward_evaluations: list[dict[str, Any]] | None = None,
    overfit_guard_active: bool = False,
) -> dict[str, Any]:
    summary = summary if isinstance(summary, dict) else {}
    trials = _safe_int(summary.get("eval_window") or summary.get("evaluated_draws"))
    safe_space = max(1, int(legal_sample_space))
    bands = []
    for cutoff in (100, 1000, 10000):
        hits = _safe_int(summary.get(f"top_{cutoff}_hits"))
        probability = min(1.0, cutoff / safe_space)
        expected_hits = trials * probability
        p_value = binomial_upper_tail_probability(trials, hits, probability)
        bands.append(
            {
                "label": f"top_{cutoff}",
                "cutoff": cutoff,
                "hits": hits,
                "trials": trials,
                "null_probability": round(probability, 10),
                "expected_hits": _rounded(expected_hits),
                "lift_vs_null": _rounded(hits / expected_hits) if expected_hits > 0 else None,
                "binomial_tail_p_value": round(p_value, 10),
            }
        )
    strongest = min(bands, key=lambda item: item["binomial_tail_p_value"]) if bands else {}

    evaluated_forward = [
        row for row in (forward_evaluations or [])
        if isinstance(row, dict) and row.get("status") == "evaluated"
    ]
    forward_top100_hits = sum(1 for row in evaluated_forward if bool(row.get("hit_top_100")))

    reasons: list[str] = ["multiple_testing_unadjusted"]
    if trials <= 0:
        status = "blocked"
        reasons.append("missing_backtest_trials")
    elif overfit_guard_active:
        status = "noise_risk"
        reasons.append("eval_slice_overfit_guard_active")
    elif trials < min_eval_draws:
        status = "noise_risk"
        reasons.append("small_regression_window")
    elif float(strongest.get("binomial_tail_p_value", 1.0)) <= 0.01:
        status = "candidate_signal"
        reasons.append("historical_rank_lift_exceeds_null_tail_threshold")
    else:
        status = "noise_risk"
        reasons.append("historical_lift_not_strong_against_null")
    if not evaluated_forward:
        reasons.append("no_forward_evaluation_yet")
    elif len(evaluated_forward) < 10:
        reasons.append("forward_window_not_complete")
    return {
        "status": status,
        "eval_window": trials,
        "min_eval_draws": min_eval_draws,
        "legal_sample_space": safe_space,
        "bands": bands,
        "strongest_band": strongest,
        "forward_evaluated_count": len(evaluated_forward),
        "forward_top100_hits": forward_top100_hits,
        "overfit_guard_active": overfit_guard_active,
        "reasons": reasons,
    }


def build_prediction_self_diagnostics(
    *,
    regression_summary: dict[str, Any] | None,
    candidates: list[Any] | tuple[Any, ...],
    legal_sample_space: int,
    dynamic_metadata: dict[str, Any] | None = None,
    forward_evaluations: list[dict[str, Any]] | None = None,
    min_eval_draws: int = 20,
) -> dict[str, Any]:
    weight = weight_trust_diagnostic(
        regression_summary,
        dynamic_metadata=dynamic_metadata,
        min_eval_draws=min_eval_draws,
    )
    candidate_space = candidate_space_diagnostic(candidates)
    signal = signal_vs_noise_diagnostic(
        regression_summary,
        legal_sample_space=legal_sample_space,
        min_eval_draws=min_eval_draws,
        forward_evaluations=forward_evaluations,
    )
    component_statuses = [weight["status"], candidate_space["status"], signal["status"]]
    weakest_status = min(component_statuses, key=_status_rank)
    action = "monitor"
    if weakest_status in {"blocked", "collapsed", "noise_risk"}:
        action = "do_not_promote_without_forward_recovery"
    elif weakest_status in {"caution", "narrow"}:
        action = "monitor_with_uncertainty"
    return {
        "protocol": SELF_DIAGNOSTICS_PROTOCOL,
        "task_frame": "Detect untrusted dynamic weights, collapsed candidate space, and noise chasing before promotion.",
        "historical_boundary": "Gauss/Riemann are diagnostic lenses only; backtest lift is evidence, not proof.",
        "gauss_pass": {
            "sample_space": int(legal_sample_space),
            "null_model": "uniform red6 rank under legal SSQ sample space",
            "leakage_checked": bool((regression_summary or {}).get("leakage_passed", True)),
        },
        "riemann_pass": {
            "space": "ranked red6 candidate manifold induced by the current scoring function",
            "collapse_test": "top-window red-number coverage and pair-overlap geometry",
        },
        "weight_trust": weight,
        "candidate_space": candidate_space,
        "signal_vs_noise": signal,
        "synthesis": {
            "status": weakest_status,
            "action": action,
            "evidence_level": "experimental_training_diagnostic",
            "failure_modes": [
                "dynamic weight learned from noise",
                "candidate family collapsed into near-duplicates",
                "historical eval slice overfit without forward support",
            ],
        },
    }


def _status_from_diagnostic(diagnostic: dict[str, Any], path: tuple[str, ...]) -> str:
    current: Any = diagnostic
    for key in path:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return str(current or "")


def _count_statuses(diagnostics: list[dict[str, Any]], path: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for diagnostic in diagnostics:
        status = _status_from_diagnostic(diagnostic, path)
        if status:
            counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _near_dynamic_summary(near_dynamic_training: dict[str, Any] | None) -> dict[str, Any]:
    training = near_dynamic_training if isinstance(near_dynamic_training, dict) else {}
    latest = training.get("latest") if isinstance(training.get("latest"), dict) else {}
    summary = latest.get("summary") if isinstance(latest.get("summary"), dict) else latest.get("selected_summary")
    if not isinstance(summary, dict):
        summary = {}
    return {
        "status": latest.get("status") or training.get("status"),
        "stagnation_rounds": _safe_int(training.get("stagnation_rounds")),
        "top_100_hits": _safe_int(summary.get("top_100_hits")),
        "top_1000_hits": _safe_int(summary.get("top_1000_hits")),
        "top_10000_hits": _safe_int(summary.get("top_10000_hits")),
        "eval_window": _safe_int(summary.get("eval_window") or latest.get("eval_window")),
    }


def build_specialist_strategy_memory(
    *,
    current_diagnostic: dict[str, Any],
    recent_diagnostics: list[dict[str, Any]] | None = None,
    round_index: int,
    near_dynamic_training: dict[str, Any] | None = None,
    dynamic_training: dict[str, Any] | None = None,
    window: int = 8,
) -> dict[str, Any]:
    recent = [item for item in (recent_diagnostics or []) if isinstance(item, dict)]
    current = current_diagnostic if isinstance(current_diagnostic, dict) else {}
    windowed = (recent + [current])[-max(1, window):]
    synthesis_counts = _count_statuses(windowed, ("synthesis", "status"))
    weight_counts = _count_statuses(windowed, ("weight_trust", "status"))
    space_counts = _count_statuses(windowed, ("candidate_space", "status"))
    signal_counts = _count_statuses(windowed, ("signal_vs_noise", "status"))
    current_synthesis = _status_from_diagnostic(current, ("synthesis", "status"))
    current_weight = _status_from_diagnostic(current, ("weight_trust", "status"))
    current_space = _status_from_diagnostic(current, ("candidate_space", "status"))
    current_signal = _status_from_diagnostic(current, ("signal_vs_noise", "status"))
    near_summary = _near_dynamic_summary(near_dynamic_training)

    unresolved: list[str] = []
    if current_weight in {"blocked", "caution"} or weight_counts.get("caution", 0) + weight_counts.get("blocked", 0) >= 2:
        unresolved.append("weight_trust_not_stable")
    if current_space in {"collapsed", "narrow"} or space_counts.get("collapsed", 0) + space_counts.get("narrow", 0) >= 2:
        unresolved.append("candidate_space_needs_reframe")
    if current_signal == "noise_risk" or signal_counts.get("noise_risk", 0) >= 2:
        unresolved.append("signal_may_be_noise")
    if (
        near_summary["status"] == "evaluated"
        and near_summary["stagnation_rounds"] >= 2
        and near_summary["top_10000_hits"] == 0
    ):
        unresolved.append("near_dynamic_window_not_lifting")

    if "candidate_space_needs_reframe" in unresolved:
        experiment_key = "candidate_space_reframe_audit"
        experiment_action = "increase_diversity_pressure_before_trusting_round_best"
        rationale = "Candidate-space geometry is narrow or collapsed across the diagnostic window."
    elif "signal_may_be_noise" in unresolved:
        experiment_key = "null_model_forward_audit"
        experiment_action = "hold_promotion_until_forward_or_frozen_lift"
        rationale = "Historical lift is not stable enough against null and forward evidence."
    elif "weight_trust_not_stable" in unresolved:
        experiment_key = "weight_trust_audit"
        experiment_action = "observe_dynamic_offsets_without_promotion"
        rationale = "Weight advice remains cautionary or blocked."
    elif "near_dynamic_window_not_lifting" in unresolved:
        experiment_key = "near_dynamic_freeze_review"
        experiment_action = "keep_near_dynamic_as_monitor_only"
        rationale = "Near-window dynamic line has repeated zero-lift evidence."
    elif current_synthesis == "candidate_signal" or current_signal == "candidate_signal":
        experiment_key = "controlled_forward_monitor"
        experiment_action = "continue_monitoring_without_claiming_edge"
        rationale = "Historical evidence is interesting, but forward evidence remains required."
    else:
        experiment_key = "continue_baseline_comparison"
        experiment_action = "continue_monitoring"
        rationale = "No persistent failure mode dominates the current diagnostic window."

    return {
        "protocol": SPECIALIST_STRATEGY_PROTOCOL,
        "mode": "observe_only_strategy_memory",
        "round_index": int(round_index),
        "memory_window": len(windowed),
        "historical_boundary": "Gauss/Riemann are diagnostic lenses; strategy memory is not proof of predictive ability.",
        "task_frame": "Convert repeated diagnostics into a falsifiable next experiment for a narrow prediction specialist.",
        "gauss_pass": {
            "strongest_claim": "Only diagnostic state transitions are recorded; no new model is promoted.",
            "weakest_assumption": "Repeated diagnostic labels are meaningful enough to guide the next audit.",
            "next_test": "Check whether the recommended experiment improves frozen or forward evidence without leakage.",
        },
        "riemann_pass": {
            "strongest_claim": "The search state can be viewed as a path through weight and candidate-space geometry.",
            "weakest_assumption": "The current diagnostic coordinates expose the relevant structural obstruction.",
            "next_test": "Verify whether candidate diversity and source frontier behavior change under the recommendation.",
        },
        "state": {
            "current_synthesis": current_synthesis,
            "current_weight": current_weight,
            "current_candidate_space": current_space,
            "current_signal": current_signal,
            "synthesis_counts": synthesis_counts,
            "weight_counts": weight_counts,
            "candidate_space_counts": space_counts,
            "signal_counts": signal_counts,
            "near_dynamic": near_summary,
            "dynamic_training_status": (dynamic_training or {}).get("latest", {}).get("status")
            if isinstance((dynamic_training or {}).get("latest"), dict)
            else None,
        },
        "failure_hypotheses": unresolved or ["no_dominant_failure_mode"],
        "selected_experiment": {
            "key": experiment_key,
            "action": experiment_action,
            "rationale": rationale,
            "promotion_allowed": False,
            "evidence_level": "strategy_memory_observation",
        },
        "next_verification": [
            "keep legal sample space and as-of issue explicit",
            "compare against null/default baselines before treating lift as signal",
            "require frozen or forward evidence before promotion",
            "check candidate diversity before trusting a narrowed candidate family",
        ],
    }
