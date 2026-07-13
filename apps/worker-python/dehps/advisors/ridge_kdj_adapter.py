from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from dehps.advisors.protocol import AdvisorContext
from dehps.models.frequency_ranker import FrequencyRankerConfig


@dataclass(frozen=True)
class RidgeKdjAdvisorAdapter:
    proposer: Callable[[AdvisorContext, int], Sequence[FrequencyRankerConfig]]
    key: str = "ridge_kdj"
    protocol_version: str = "ridge_kdj_advisor_v1"

    def propose(self, context: AdvisorContext, budget: int) -> Sequence[FrequencyRankerConfig]:
        return self.proposer(context, budget)
