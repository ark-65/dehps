from __future__ import annotations

from statistics import median
from typing import Any

from dehps.evaluation.models import BaselineComparison, EvaluationResult, LeakageReport
from dehps.evaluation.objective import TrainingMetrics, evaluate_objective
from dehps.evaluation.objective_policy import DEFAULT_OBJECTIVE_POLICY
from dehps.evaluation.promotion import PromotionGate
from dehps.evaluation.tail_risk import calculate_tail_risk_penalty
from dehps.ranking_contract import normalize_ranking_contract


FORWARD_CHALLENGER_LINE_KEY = "forward_challenger"
FORWARD_CHALLENGER_LINE_LABEL = "prospective fixed-config challenger"
FORWARD_PROMOTION_PROTOCOL = "config_bound_forward_promotion_v1"
FORWARD_PROMOTION_MIN_PAIRED_ISSUES = 20
FORWARD_PROMOTION_MAX_LOSING_STREAK = 3
LEGAL_UNIVERSE_SIZE = 1_107_568


def _percentile(values: list[int], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * fraction + 0.999999)))
    return float(ordered[index])


def _longest_losing_streak(pairs: list[dict[str, Any]]) -> int:
    longest = 0
    current = 0
    for pair in pairs:
        if int(pair["challenger"]["model_rank"]) > int(pair["incumbent"]["model_rank"]):
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _evaluation(rows: list[dict[str, Any]], *, config_hash: str) -> EvaluationResult:
    ranks = [int(row["model_rank"]) for row in rows]
    red5_ranks = [int(row.get("red5_rank") or LEGAL_UNIVERSE_SIZE + 1) for row in rows]
    top_100_hits = sum(rank <= 100 for rank in ranks)
    top_1000_hits = sum(rank <= 1000 for rank in ranks)
    top_10000_hits = sum(rank <= 10000 for rank in ranks)
    median_rank = float(median(ranks))
    worst_rank = max(ranks)
    p95_rank = _percentile(ranks, 0.95)
    over_750000 = sum(rank > 750_000 for rank in ranks)
    over_900000 = sum(rank > 900_000 for rank in ranks)
    over_1000000 = sum(rank > 1_000_000 for rank in ranks)
    tail_risk = calculate_tail_risk_penalty(
        median_rank=median_rank,
        worst_rank=worst_rank,
        p95_rank=p95_rank,
        tail_over_750000_count=over_750000,
        tail_over_900000_count=over_900000,
        tail_over_1000000_count=over_1000000,
        universe_size=LEGAL_UNIVERSE_SIZE,
        policy=DEFAULT_OBJECTIVE_POLICY,
    )
    objective = evaluate_objective(
        TrainingMetrics(
            top_100_hits=top_100_hits,
            top_1000_hits=top_1000_hits,
            top_10000_hits=top_10000_hits,
            median_rank=median_rank,
            worst_rank=worst_rank,
            p95_rank=p95_rank,
            tail_over_750000_count=over_750000,
            tail_over_900000_count=over_900000,
            tail_over_1000000_count=over_1000000,
            baseline_unique_reward=0.0,
            baseline_overlap_penalty=0.0,
            red5_top_100_hits=sum(rank <= 100 for rank in red5_ranks),
            red5_top_1000_hits=sum(rank <= 1000 for rank in red5_ranks),
            red5_top_10000_hits=sum(rank <= 10000 for rank in red5_ranks),
            rank_quality_reward=0.0,
            universe_size=LEGAL_UNIVERSE_SIZE,
            tail_risk_penalty=tail_risk,
        ),
        DEFAULT_OBJECTIVE_POLICY,
    )
    return EvaluationResult(
        objective=objective.objective,
        top_100_hits=top_100_hits,
        top_1000_hits=top_1000_hits,
        top_10000_hits=top_10000_hits,
        median_rank=median_rank,
        p95_rank=p95_rank,
        worst_rank=worst_rank,
        tail_risk=tail_risk,
        tail_over_750000_count=over_750000,
        tail_over_900000_count=over_900000,
        tail_over_1000000_count=over_1000000,
        baseline_comparison=BaselineComparison(),
        leakage_report=LeakageReport(passed=True),
        valid=True,
        has_forward_evidence=True,
        config_hash=config_hash,
    )


def _evaluation_payload(value: EvaluationResult) -> dict[str, Any]:
    return {
        "config_hash": value.config_hash,
        "objective": value.objective,
        "primary_score": list(value.primary_score),
        "median_rank": value.median_rank,
        "p95_rank": value.p95_rank,
        "worst_rank": value.worst_rank,
        "tail_risk": value.tail_risk,
        "tail_over_750000_count": value.tail_over_750000_count,
        "tail_over_900000_count": value.tail_over_900000_count,
        "tail_over_1000000_count": value.tail_over_1000000_count,
    }


def evaluate_forward_promotion(
    cohort: dict[str, Any],
    pairs: list[dict[str, Any]],
) -> dict[str, Any]:
    min_pairs = int(cohort.get("min_paired_issues") or FORWARD_PROMOTION_MIN_PAIRED_ISSUES)
    max_losing_streak = int(cohort.get("max_losing_streak") or FORWARD_PROMOTION_MAX_LOSING_STREAK)
    incumbent_hash = str(cohort.get("incumbent_config_hash") or "")
    challenger_hash = str(cohort.get("challenger_config_hash") or "")
    blockers: list[str] = []
    if cohort.get("status") != "accumulating":
        blockers.append(f"cohort_not_accumulating:{cohort.get('status')}")
    if cohort.get("historical_gate_passed") is not True:
        blockers.append("historical_gate_not_passed")
    seen: set[str] = set()
    for pair in pairs:
        issue = str(pair.get("target_issue") or "")
        incumbent = pair.get("incumbent") if isinstance(pair.get("incumbent"), dict) else {}
        challenger = pair.get("challenger") if isinstance(pair.get("challenger"), dict) else {}
        if not issue or issue in seen:
            blockers.append(f"duplicate_or_missing_issue:{issue or 'missing'}")
        seen.add(issue)
        duplicate_lines = pair.get("duplicate_line_keys")
        if isinstance(duplicate_lines, list) and duplicate_lines:
            blockers.append(f"duplicate_forward_lines:{issue}:{','.join(sorted(str(value) for value in duplicate_lines))}")
        if incumbent.get("config_hash") != incumbent_hash:
            blockers.append(f"incumbent_config_drift:{issue}")
        if challenger.get("config_hash") != challenger_hash:
            blockers.append(f"challenger_config_drift:{issue}")
        if normalize_ranking_contract(incumbent.get("ranking_contract")) != normalize_ranking_contract(
            challenger.get("ranking_contract")
        ):
            blockers.append(f"ranking_contract_mismatch:{issue}")
        for label, row in (("incumbent", incumbent), ("challenger", challenger)):
            if row.get("status") != "evaluated" or row.get("leakage_passed") is not True:
                blockers.append(f"invalid_forward_evaluation:{issue}:{label}")
            if str(row.get("target_issue") or issue) != issue:
                blockers.append(f"target_issue_mismatch:{issue}:{label}")
            if int(row.get("candidate_count") or 0) != int(row.get("top_n") or 0):
                blockers.append(f"incomplete_candidate_set:{issue}:{label}")
            if not isinstance(row.get("model_rank"), int):
                blockers.append(f"missing_model_rank:{issue}:{label}")
        if int(incumbent.get("top_n") or 0) != int(challenger.get("top_n") or 0):
            blockers.append(f"top_n_mismatch:{issue}")
    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return {
            "protocol": FORWARD_PROMOTION_PROTOCOL,
            "status": "invalid",
            "promote": False,
            "paired_issue_count": len(pairs),
            "min_paired_issues": min_pairs,
            "blockers": blockers,
        }
    if len(pairs) < min_pairs:
        return {
            "protocol": FORWARD_PROMOTION_PROTOCOL,
            "status": "accumulating",
            "promote": False,
            "paired_issue_count": len(pairs),
            "min_paired_issues": min_pairs,
            "remaining_issue_count": min_pairs - len(pairs),
            "blockers": [f"insufficient_paired_forward_issues:{len(pairs)}/{min_pairs}"],
        }
    frozen_pairs = pairs[:min_pairs]
    incumbent = _evaluation([pair["incumbent"] for pair in frozen_pairs], config_hash=incumbent_hash)
    challenger = _evaluation([pair["challenger"] for pair in frozen_pairs], config_hash=challenger_hash)
    gate = PromotionGate().decide(challenger, incumbent)
    losing_streak = _longest_losing_streak(frozen_pairs)
    streak_passed = losing_streak <= max_losing_streak
    promote = gate.accepted and streak_passed
    reason_codes = list(gate.reason_codes)
    if not streak_passed:
        reason_codes.append("consecutive_forward_worsening")
    return {
        "protocol": FORWARD_PROMOTION_PROTOCOL,
        "status": "promoted" if promote else "rejected",
        "promote": promote,
        "paired_issue_count": len(frozen_pairs),
        "min_paired_issues": min_pairs,
        "issues": [str(pair["target_issue"]) for pair in frozen_pairs],
        "incumbent": _evaluation_payload(incumbent),
        "challenger": _evaluation_payload(challenger),
        "promotion_gate": {
            "accepted": gate.accepted,
            "reason_codes": list(gate.reason_codes),
            "human_summary": gate.human_summary,
        },
        "max_losing_streak": losing_streak,
        "allowed_losing_streak": max_losing_streak,
        "consecutive_worsening_passed": streak_passed,
        "reason_codes": reason_codes,
        "blockers": [] if promote else reason_codes,
    }
