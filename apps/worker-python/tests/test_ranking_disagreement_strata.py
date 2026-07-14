import pytest

from dehps.experiments.ranking_disagreement.features import compute_features
from dehps.experiments.ranking_disagreement.rank_matrix import build_rank_matrix
from dehps.experiments.ranking_disagreement.ranker_adapter import RankingContext, built_in_rankers
from dehps.experiments.ranking_disagreement.strata import assign_strata, fit_strata_thresholds, strata_counts
from dehps.experiments.ranking_disagreement.windows import history_fingerprint
from ranking_disagreement_fixtures import small_history, small_universe


def test_strata_fit_is_search_only_and_assigns_one_label_per_combination() -> None:
    history = small_history(6)
    universe = small_universe(40)
    context = RankingContext("2024007", history, universe, history_fingerprint(history))
    frame = compute_features(build_rank_matrix(tuple(ranker.rank(context) for ranker in built_in_rankers())))

    thresholds = fit_strata_thresholds([frame], source_stage="historical_search")
    labels = assign_strata(frame, thresholds)

    assert sum(strata_counts(labels).values()) == universe.count
    assert thresholds.fingerprint
    with pytest.raises(ValueError, match="historical_search"):
        fit_strata_thresholds([frame], source_stage="frozen_validation")
