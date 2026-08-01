from __future__ import annotations

import argparse

from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.research_os.supervisor import ResearchEvidenceSupervisor


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the unified DEHPS Research Evidence Supervisor."
    )
    parser.add_argument(
        "--control-plane-key",
        default="m4-information-theory-mainline",
    )
    parser.add_argument("--interval-seconds", type=float, default=15.0)
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Execute at most one READY/RUNNING capability and return.",
    )
    parser.add_argument(
        "--task-key",
        help="Restrict --run-once to one canonical task key.",
    )
    args = parser.parse_args()
    repository = PostgresResearchOSRepository()
    repository.ensure_schema()
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,
        control_plane_key=args.control_plane_key,
    )
    if args.task_key and not args.run_once:
        parser.error("--task-key requires --run-once")
    if args.run_once:
        print(supervisor.run_once(task_key=args.task_key))
        return
    supervisor.run_resident(interval_seconds=args.interval_seconds)


if __name__ == "__main__":
    main()
