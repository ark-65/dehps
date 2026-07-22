from __future__ import annotations

from platform import python_version
import random

from dehps.contracts import canonical_digest
from dehps.portfolio.models import (
    PortfolioRequest,
    PortfolioSelection,
    build_portfolio_selection,
    reject,
    thaw_json,
)


class RandomFromTopPoolSelector:
    key = "random_from_top_pool"

    def select(self, request: PortfolioRequest) -> PortfolioSelection:
        if request.selector_key != self.key:
            reject("portfolio_selector_backend_mismatch", "request key does not match backend")
        config = thaw_json(request.selector_config)
        if set(config) != {"sampling_contract"} or config["sampling_contract"] != "uniform_without_replacement":
            reject(
                "portfolio_random_pool_config_invalid",
                "random_from_top_pool requires the exact uniform-without-replacement contract",
            )
        if request.seed is None:
            reject(
                "portfolio_random_pool_seed_missing",
                "random_from_top_pool requires an explicit master seed",
            )
        seed_scope = {
            "selector_key": self.key,
            "selector_config_digest": request.selector_config_digest,
            "candidate_pool_digest": request.candidate_pool_digest,
            "budget": request.budget,
            "context": thaw_json(request.context),
        }
        seed_digest = canonical_digest(
            {"master_seed": request.seed, "scope": seed_scope},
            domain="dehps.candidate-portfolio-selector-derived-seed.v1",
        )
        derived_seed = int(seed_digest[:16], 16)
        rng = random.Random(derived_seed)
        choice_order = rng.sample(request.candidates, request.budget)
        return build_portfolio_selection(
            request,
            choice_order,
            provenance={
                "backend": self.key,
                "algorithm": "uniform_without_replacement_from_sealed_pool",
                "stochastic": True,
                "master_seed": request.seed,
                "derived_seed": derived_seed,
                "seed_derivation_digest": seed_digest,
                "rng_algorithm": "python.random.MT19937",
                "python_version": python_version(),
                "production_integration": False,
            },
        )
