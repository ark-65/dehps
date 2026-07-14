from __future__ import annotations

import argparse

from dehps.research_runtime.models import ResidentResearchRuntimeConfig, ResearchRuntimeBudget
from dehps.research_runtime.resident import ResidentResearchRuntime


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the resident DEHPS continuous research runtime.")
    parser.add_argument("--interval-seconds", type=float, default=15.0)
    parser.add_argument("--max-cycles", type=int)
    parser.add_argument("--research-cpu", type=int, default=12)
    parser.add_argument("--forward-cpu", type=int, default=4)
    parser.add_argument("--total-memory-gb", type=int, default=20)
    parser.add_argument("--research-memory-gb", type=int, default=18)
    parser.add_argument("--forward-memory-gb", type=int, default=2)
    parser.add_argument("--daily-cycle-limit", type=int, default=100)
    args = parser.parse_args()
    ResidentResearchRuntime(
        budget=ResearchRuntimeBudget(
            research_cpu=args.research_cpu,
            forward_cpu=args.forward_cpu,
            total_memory_gb=args.total_memory_gb,
            research_memory_gb=args.research_memory_gb,
            forward_memory_gb=args.forward_memory_gb,
            daily_cycle_limit=args.daily_cycle_limit,
        ),
        config=ResidentResearchRuntimeConfig(
            interval_seconds=args.interval_seconds,
            max_cycles=args.max_cycles,
        ),
    ).run()


if __name__ == "__main__":
    main()
