from __future__ import annotations

from dehps.research_runtime.models import ResearchCycleResult
from dehps.research_runtime.runtime import ContinuousResearchRuntime


class ContinuousResearchWorker:
    def __init__(self, runtime: ContinuousResearchRuntime | None = None) -> None:
        self.runtime = runtime or ContinuousResearchRuntime()

    def run(self, *, max_cycles: int = 1) -> tuple[ResearchCycleResult, ...]:
        if max_cycles < 1 or max_cycles > 100:
            raise ValueError("max_cycles must be between 1 and 100")
        results: list[ResearchCycleResult] = []
        for _ in range(max_cycles):
            # A snapshot rotation decision is made at cycle boundaries only.
            results.append(self.runtime.once(cycle_running=False))
        return tuple(results)
