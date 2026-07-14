from __future__ import annotations

from datetime import date, timedelta
from itertools import islice

from dehps.domain.combination import iter_ssq_red_combinations
from dehps.experiments.ranking_disagreement.models import DrawRecord
from dehps.experiments.ranking_disagreement.ranker_adapter import build_legal_universe


def small_history(count: int = 12) -> tuple[DrawRecord, ...]:
    combos = list(islice(iter_ssq_red_combinations(), count))
    return tuple(
        DrawRecord(
            issue=f"2024{index + 1:03d}",
            draw_date=date(2024, 1, 1) + timedelta(days=index),
            red_numbers=combo,
        )
        for index, combo in enumerate(combos)
    )


def small_universe(limit: int = 80):
    return build_legal_universe(limit=limit)
