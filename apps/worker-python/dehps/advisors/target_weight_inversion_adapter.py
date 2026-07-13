from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from dehps.advisors.protocol import AdvisorContext
from dehps.models.frequency_ranker import FrequencyRankerConfig


@dataclass(frozen=True)
class TargetWeightInversionAdvisorAdapter:
    """Expose the established inversion candidate source through the advisor protocol."""

    proposer: Callable[[AdvisorContext, int], Sequence[FrequencyRankerConfig]]
    key: str = "target_weight_inversion"
    protocol_version: str = "target_weight_inversion_advisor_v1"

    def propose(self, context: AdvisorContext, budget: int) -> Sequence[FrequencyRankerConfig]:
        return self.proposer(context, budget)
