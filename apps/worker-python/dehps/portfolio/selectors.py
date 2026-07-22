from __future__ import annotations

from typing import Protocol

from dehps.portfolio.models import PortfolioRequest, PortfolioSelection, reject


class PortfolioSelector(Protocol):
    key: str

    def select(self, request: PortfolioRequest) -> PortfolioSelection: ...


def select_portfolio(request: PortfolioRequest) -> PortfolioSelection:
    if request.selector_key == "score_topk":
        from dehps.portfolio.score_topk import ScoreTopKSelector

        selector: PortfolioSelector = ScoreTopKSelector()
    elif request.selector_key == "random_from_top_pool":
        from dehps.portfolio.random_pool import RandomFromTopPoolSelector

        selector = RandomFromTopPoolSelector()
    elif request.selector_key == "greedy_score_diversity":
        from dehps.portfolio.greedy import GreedyScoreDiversitySelector

        selector = GreedyScoreDiversitySelector()
    elif request.selector_key == "cluster_quota":
        from dehps.portfolio.cluster_quota import ClusterQuotaSelector

        selector = ClusterQuotaSelector()
    else:  # pragma: no cover - PortfolioRequest validates the closed registry
        reject(
            "portfolio_selector_key_invalid",
            "selector_key is not a registered research backend",
            selector_key=request.selector_key,
        )
    return selector.select(request)
