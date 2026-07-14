import numpy as np
import pytest

from dehps.experiments.ranking_disagreement.rank_matrix import build_rank_matrix, validate_rank_matrix
from dehps.experiments.ranking_disagreement.ranker_adapter import RankingContext, built_in_rankers
from dehps.experiments.ranking_disagreement.windows import history_fingerprint
from ranking_disagreement_fixtures import small_history, small_universe


def test_rank_matrix_requires_no_missing_or_duplicate_ranks() -> None:
    history = small_history(6)
    universe = small_universe(40)
    context = RankingContext("2024007", history, universe, history_fingerprint(history))
    matrix = build_rank_matrix(tuple(ranker.rank(context) for ranker in built_in_rankers()))

    validate_rank_matrix(matrix)

    broken = matrix.__class__(
        **{**matrix.__dict__, "values": np.column_stack([matrix.values[:, 0], matrix.values[:, 0], matrix.values[:, 2]])}
    )
    broken.values[0, 0] = broken.values[1, 0]
    with pytest.raises(ValueError, match="missing|duplicates"):
        validate_rank_matrix(broken)
