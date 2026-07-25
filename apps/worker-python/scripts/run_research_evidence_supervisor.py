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
    args = parser.parse_args()
    repository = PostgresResearchOSRepository()
    repository.ensure_schema()
    ResearchEvidenceSupervisor(
        repository=repository,
        control_plane_key=args.control_plane_key,
    ).run_resident(interval_seconds=args.interval_seconds)


if __name__ == "__main__":
    main()
