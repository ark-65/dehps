from __future__ import annotations

import argparse

from dehps.forward_runtime.resident import ResidentForwardRuntime, ResidentForwardRuntimeConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the resident DEHPS forward validation runtime.")
    parser.add_argument("--interval-seconds", type=float, default=15.0)
    parser.add_argument("--max-checks", type=int)
    args = parser.parse_args()
    ResidentForwardRuntime(
        config=ResidentForwardRuntimeConfig(
            interval_seconds=args.interval_seconds,
            max_checks=args.max_checks,
        ),
    ).run()


if __name__ == "__main__":
    main()
