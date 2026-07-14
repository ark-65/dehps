import numpy as np

from dehps.experiments.ranking_disagreement.features import compute_features
from dehps.experiments.ranking_disagreement.models import FROZEN_FEATURE_KEYS
from dehps.experiments.ranking_disagreement.rank_matrix import build_rank_matrix
from dehps.experiments.ranking_disagreement.ranker_adapter import RankingContext, built_in_rankers
from dehps.experiments.ranking_disagreement.windows import history_fingerprint
from ranking_disagreement_fixtures import small_history, small_universe


def test_features_are_complete_finite_and_versioned() -> None:
    history = small_history(6)
    universe = small_universe(40)
    context = RankingContext("2024007", history, universe, history_fingerprint(history))
    matrix = build_rank_matrix(tuple(ranker.rank(context) for ranker in built_in_rankers()))
    frame = compute_features(matrix)

    assert set(FROZEN_FEATURE_KEYS) == {*frame.numeric, *frame.categorical}
    assert all(np.isfinite(value).all() for value in frame.numeric.values())
    assert frame.feature_fingerprint
