from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from dehps.advisors.protocol import AdvisorCandidate, AdvisorContext, TrainingAdvisor


@dataclass(frozen=True)
class AdvisorRegistry:
    advisors: tuple[TrainingAdvisor, ...]

    @classmethod
    def build(cls, advisors: Iterable[TrainingAdvisor]) -> AdvisorRegistry:
        values = tuple(advisors)
        keys = [advisor.key for advisor in values]
        if len(keys) != len(set(keys)):
            raise ValueError("advisor keys must be unique")
        return cls(values)

    def propose(
        self,
        context: AdvisorContext,
        budgets: Mapping[str, int],
    ) -> tuple[AdvisorCandidate, ...]:
        candidates: list[AdvisorCandidate] = []
        for advisor in self.advisors:
            budget = max(0, int(budgets.get(advisor.key, 0)))
            for config in advisor.propose(context, budget)[:budget]:
                candidates.append(
                    AdvisorCandidate(
                        config=config,
                        source_key=advisor.key,
                        protocol_version=advisor.protocol_version,
                    )
                )
        return tuple(candidates)
