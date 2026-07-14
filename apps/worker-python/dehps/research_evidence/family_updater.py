from __future__ import annotations

from dehps.research.repository import HypothesisRepository


class FamilyDecisionReader:
    """Read-only family status helper for Round 25 reports and tests."""

    def __init__(self, repository: HypothesisRepository | None = None) -> None:
        self.repository = repository or HypothesisRepository()

    def family_status_for_hypothesis(self, hypothesis_key: str) -> str:
        hypothesis = self.repository.get_hypothesis(hypothesis_key)
        for family in self.repository.list_families(limit=10_000):
            if family.id == hypothesis.family_id:
                return family.status.value
        return "unknown"
