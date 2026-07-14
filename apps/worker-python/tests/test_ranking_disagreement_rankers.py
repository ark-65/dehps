from dehps.experiments.ranking_disagreement.models import FROZEN_RANKER_KEYS, normalize_ranker_key
from dehps.experiments.ranking_disagreement.ranker_adapter import RankingContext, built_in_rankers
from dehps.experiments.ranking_disagreement.windows import history_fingerprint
from ranking_disagreement_fixtures import small_history, small_universe


def test_rankers_emit_frozen_keys_and_complete_rank_vectors() -> None:
    history = small_history(6)
    universe = small_universe(40)
    context = RankingContext(
        as_of_issue="2024007",
        history=history,
        legal_universe=universe,
        history_fingerprint=history_fingerprint(history),
    )

    outputs = tuple(ranker.rank(context) for ranker in built_in_rankers())

    assert tuple(output.ranker_key for output in outputs) == FROZEN_RANKER_KEYS
    assert all(output.ranks.min() == 1 and output.ranks.max() == universe.count for output in outputs)
    assert normalize_ranker_key("frequency_based_ranker") == "frequency_based"
