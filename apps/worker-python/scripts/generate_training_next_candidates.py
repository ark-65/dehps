from __future__ import annotations

import argparse
import json

from dehps.db import get_connection
from dehps.optimization.next_candidates import refresh_training_next_candidates_current
from dehps.runtime.heavy_job import HeavyJobLock, apply_cpu_thread_env_defaults


def generate_training_next_candidates(
    *,
    run_id: str | None = None,
    top_n: int = 10000,
    heavy_job_lock_timeout_seconds: float | None = 0,
    cpu_threads: int = 1,
    skip_heavy_job_lock: bool = False,
) -> dict:
    apply_cpu_thread_env_defaults(cpu_threads)

    def refresh() -> dict:
        with get_connection() as conn:
            return refresh_training_next_candidates_current(conn, run_id=run_id, top_n=top_n)

    if skip_heavy_job_lock:
        return refresh()

    with HeavyJobLock(
        owner="training-next-candidates",
        timeout_seconds=heavy_job_lock_timeout_seconds,
        context={"run_id": run_id, "top_n": top_n},
    ):
        return refresh()


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh the current next-issue Top-N candidate snapshot from training results.")
    parser.add_argument("--run-id")
    parser.add_argument("--top-n", type=int, default=10000)
    parser.add_argument("--heavy-job-lock-timeout-seconds", type=float, default=0.0)
    parser.add_argument("--cpu-threads", type=int, default=1)
    parser.add_argument("--skip-heavy-job-lock", action="store_true")
    args = parser.parse_args()
    payload = generate_training_next_candidates(
        run_id=args.run_id,
        top_n=args.top_n,
        heavy_job_lock_timeout_seconds=args.heavy_job_lock_timeout_seconds,
        cpu_threads=args.cpu_threads,
        skip_heavy_job_lock=args.skip_heavy_job_lock,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
