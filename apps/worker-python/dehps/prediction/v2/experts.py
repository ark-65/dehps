from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from dehps.prediction.v2.contracts import EXPERT_STATUS, SHADOW_ROUTE


class ExpertNotAuthorizedError(RuntimeError):
    pass


class MarginalExpert:
    status = EXPERT_STATUS

    def score(self, *_args: object, **_kwargs: object) -> list[float]:
        raise ExpertNotAuthorizedError("marginal expert requires a separate Research Request")


class TemporalExpert:
    status = EXPERT_STATUS

    def score(self, *_args: object, **_kwargs: object) -> list[float]:
        raise ExpertNotAuthorizedError("temporal expert requires a separate Research Request")


class FusionRouter:
    route = SHADOW_ROUTE

    def select_route(self, _state: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "route": self.route,
            "signal_bearing_experts_used": [],
            "reason": "historical eligibility and expert estimators are not authorized",
        }


def diversity_diagnostics(candidates: Sequence[Sequence[int]]) -> dict[str, Any]:
    rows = [tuple(int(number) for number in row) for row in candidates]
    exposures = {number: 0 for number in range(1, 34)}
    pair_counts: dict[tuple[int, int], int] = {}
    triple_keys: set[tuple[int, int, int]] = set()
    for row in rows:
        for number in row:
            exposures[number] += 1
        for left in range(len(row)):
            for right in range(left + 1, len(row)):
                pair = (row[left], row[right])
                pair_counts[pair] = pair_counts.get(pair, 0) + 1
                for third in range(right + 1, len(row)):
                    triple_keys.add((row[left], row[right], row[third]))
    overlap_pairs = len(rows) * (len(rows) - 1) // 2
    # Each number contributes one overlap to every pair of rows containing it.
    # This is exactly the mean pairwise intersection, computed in O(N) time.
    overlap_total = sum(count * (count - 1) // 2 for count in exposures.values())
    return {
        "role": "OBSERVATION_ONLY",
        "duplicate_count": len(rows) - len(set(rows)),
        "max_number_exposure": max(exposures.values(), default=0),
        "number_exposure": [exposures[number] for number in range(1, 34)],
        "mean_pairwise_overlap": round(overlap_total / overlap_pairs, 12) if overlap_pairs else 0.0,
        "pair_coverage": len(pair_counts),
        "triple_coverage": len(triple_keys),
        "selection_effect": False,
    }
