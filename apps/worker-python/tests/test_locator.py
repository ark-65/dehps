from dehps.engineering.locator import RepositoryLocator
from experiment_plan_fixtures import ranking_plan


def test_locator_reuses_existing_ranking_disagreement_components() -> None:
    located = RepositoryLocator().locate(ranking_plan())
    by_key = {item.key: item for item in located}

    assert by_key["ranking_disagreement_package"].exists is True
    assert by_key["ranking_disagreement_executor"].exists is True
    assert by_key["ranking_disagreement_ranker_adapter"].exists is True
    assert by_key["matched_budget_baselines"].exists is True
    assert by_key["ranking_disagreement_metrics"].exists is True
    assert any(item.kind == "test" and "ranking_disagreement" in item.path for item in located)
