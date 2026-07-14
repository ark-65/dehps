from dehps.experiments.ranking_disagreement.baselines import evaluate_strata_and_baselines
from dehps.experiments.ranking_disagreement.features import compute_features
from dehps.experiments.ranking_disagreement.rank_matrix import build_rank_matrix
from dehps.experiments.ranking_disagreement.ranker_adapter import RankingContext, built_in_rankers
from dehps.experiments.ranking_disagreement.strata import fit_strata_thresholds
from dehps.experiments.ranking_disagreement.windows import history_fingerprint
from ranking_disagreement_fixtures import small_history, small_universe


def test_baselines_are_budget_matched_and_deterministic() -> None:
    history = small_history(6)
    universe = small_universe(40)
    context = RankingContext("2024007", history, universe, history_fingerprint(history))
    matrix = build_rank_matrix(tuple(ranker.rank(context) for ranker in built_in_rankers()))
    frame = compute_features(matrix)
    thresholds = fit_strata_thresholds([frame])

    first = evaluate_strata_and_baselines(
        frame=frame, matrix=matrix, thresholds=thresholds, target_combination_id=7, seed=99
    )
    second = evaluate_strata_and_baselines(
        frame=frame, matrix=matrix, thresholds=thresholds, target_combination_id=7, seed=99
    )

    assert first == second
    for stratum, metrics in first["strata"].items():
        for baseline in first["baselines"][stratum].values():
            assert baseline["candidate_count"] == metrics["candidate_count"]
