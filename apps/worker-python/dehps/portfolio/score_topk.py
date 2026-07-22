from __future__ import annotations

from dehps.portfolio.models import (
    PortfolioRequest,
    PortfolioSelection,
    build_portfolio_selection,
    reject,
    thaw_json,
)


class ScoreTopKSelector:
    key = "score_topk"

    def select(self, request: PortfolioRequest) -> PortfolioSelection:
        if request.selector_key != self.key:
            reject("portfolio_selector_backend_mismatch", "request key does not match backend")
        config = thaw_json(request.selector_config)
        if config:
            reject(
                "portfolio_score_topk_config_invalid",
                "score_topk takes an empty selector_config",
            )
        return build_portfolio_selection(
            request,
            request.candidates[: request.budget],
            provenance={
                "backend": self.key,
                "algorithm": "strict_v1_score_desc_lex_id_asc",
                "stochastic": False,
                "production_integration": False,
            },
        )
