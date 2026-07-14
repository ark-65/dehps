from __future__ import annotations

from pathlib import Path

from dehps.experiments.ranking_disagreement.artifacts import ArtifactWriter
from dehps.experiments.ranking_disagreement.models import (
    BASELINE_KEYS,
    FROZEN_HYPOTHESIS_KEY,
    FROZEN_PLAN_FINGERPRINT,
    FROZEN_PLAN_KEY,
    STRATA_KEYS,
)


def make_round24_artifacts(path: Path, *, validation_valid: bool = True) -> Path:
    writer = ArtifactWriter(
        base_directory=path,
        plan_key=FROZEN_PLAN_KEY,
        plan_fingerprint=FROZEN_PLAN_FINGERPRINT,
        proposal_fingerprint="proposal",
        hypothesis_key=FROZEN_HYPOTHESIS_KEY,
        experiment_key="ranking_disagreement_round24_isolated",
        history_fingerprint="history",
        legal_universe_fingerprint="universe",
        code_commit="test",
    )
    search_issues = [f"s{i:03d}" for i in range(100)]
    frozen_issues = [f"f{i:03d}" for i in range(20)]
    writer.write_json(
        "issue_windows.json",
        {
            "feasibility_issue": search_issues[0],
            "search_issues": search_issues,
            "frozen_issues": frozen_issues,
            "forward_issues": [],
            "search_issue_count": 100,
            "frozen_issue_count": 20,
            "forward_validation_executed": False,
        },
    )
    writer.write_json("ranker_versions.json", {"rankers": []})
    writer.write_json("strata_thresholds.json", {"fingerprint": "thresholds"})
    writer.write_json("feasibility.json", {"status": "completed"})
    writer.write_json("search_results.json", {"status": "completed", "issue_count": 100, "aggregate": aggregate()})
    writer.write_json("frozen_results.json", {"status": "completed", "issue_count": 20, "aggregate": aggregate()})
    per_issue = [
        {"stage": "frozen_validation", "issue": issue, "strata": per_issue_strata(), "baselines": {}}
        for issue in frozen_issues
    ]
    writer.write_jsonl("per_issue_results.jsonl", per_issue)
    writer.write_json("statistics.json", {"version": "test", "comparisons": comparisons()})
    writer.write_json("validation_report.json", {"valid": validation_valid})
    writer.write_summary("execution_summary.md", {"status": "completed"})
    writer.write_manifest()
    return path


def aggregate():
    return {
        "issue_count": 20,
        "strata": {stratum: {"target_hit_count": 0, "target_hit_rate": 0.0, "mean_candidate_count": 10.0} for stratum in STRATA_KEYS},
        "baselines": {
            stratum: {
                baseline: {"target_hit_count": 0, "target_hit_rate": 0.0, "mean_candidate_count": 10.0, "baseline_lift": 0.0}
                for baseline in BASELINE_KEYS
            }
            for stratum in STRATA_KEYS
        },
    }


def per_issue_strata():
    return {
        stratum: {
            "target_hit": False,
            "candidate_count": 10,
            "top_100_hits": False,
            "top_1000_hits": False,
            "top_10000_hits": False,
            "mean_rank": 100.0,
            "median_rank": 100.0,
            "p95_rank": 100.0,
            "worst_rank": 100.0,
            "tail_over_750000": 0,
            "tail_over_900000": 0,
            "tail_over_1000000": 0,
        }
        for stratum in STRATA_KEYS
    }


def comparisons():
    return [
        {
            "stratum": stratum,
            "baseline": baseline,
            "paired_rank_difference": 0.0,
            "bootstrap_confidence_interval": {"low": -0.1, "high": 0.1},
            "permutation_null": {"p_value": 1.0},
            "effect_size": 0.0,
            "multiple_comparison_adjusted_p_value": 1.0,
        }
        for stratum in STRATA_KEYS
        for baseline in BASELINE_KEYS
    ]
