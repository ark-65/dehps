from dehps.experiments.ranking_disagreement.models import BASELINE_KEYS, STRATA_KEYS
from dehps.experiments.ranking_disagreement.statistics import aggregate_results, summarize_statistics


def test_statistics_include_all_strata_baselines_and_adjusted_p_values() -> None:
    issue = {
        "strata": {key: {"target_hit": False, "candidate_count": 3} for key in STRATA_KEYS},
        "baselines": {
            stratum: {baseline: {"target_hit": False, "candidate_count": 3} for baseline in BASELINE_KEYS}
            for stratum in STRATA_KEYS
        },
    }
    stats = summarize_statistics([issue, issue])
    aggregate = aggregate_results([issue, issue])

    assert len(stats["comparisons"]) == len(STRATA_KEYS) * len(BASELINE_KEYS)
    assert "multiple_comparison_adjusted_p_value" in stats["comparisons"][0]
    assert set(aggregate["strata"]) == set(STRATA_KEYS)
