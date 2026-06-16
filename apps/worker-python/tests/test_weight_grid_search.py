from __future__ import annotations

from scripts.run_weight_grid_search import sort_key


def test_weight_grid_search_prefers_hits_then_lower_median_rank():
    weaker = {"top_100_hits": 0, "top_1000_hits": 0, "top_10000_hits": 1, "median_rank": 500000, "best_rank": 1000}
    stronger = {"top_100_hits": 0, "top_1000_hits": 0, "top_10000_hits": 1, "median_rank": 100000, "best_rank": 2000}

    assert sort_key(stronger) > sort_key(weaker)
