from __future__ import annotations

"""Run bounded, read-only historical research while forward training is parked.

This lane deliberately never invokes the training supervisor and never writes current
prediction candidates.  It is a fixed audit suite: its artifacts may inform a human
review, but cannot change line selection or promotion.
"""

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = WORKER_ROOT.parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.optimization.regime import select_history
from dehps.optimization.walk_forward import fingerprint_history
from dehps.runtime.heavy_job import heavy_job_lock
from dehps.source_version import resolve_git_commit
from dehps.training.persistence_policy import apply_read_only_database_guard
from dehps.training.research_fingerprint import (
    RESEARCH_EXECUTION_MODE,
    ResearchTrainingFingerprint,
    completed_manifest_matches,
)


LANE_KEY = "isolated_historical_research"
SUITE_VERSION = "idle-optimization-v2"
DEFAULT_MODEL_VERSION = "frequency-ranker-kdj-v1"
DEFAULT_FEATURE_VERSION = "frequency-ranker-structural-v1"
DEFAULT_CANDIDATE_ALGORITHM_VERSION = "kdj-controls-v1"
DEFAULT_TASKS = (
    "training-diagnostics",
    "walk-forward",
    "weight-grid",
    "feature-ablation",
    "dynamic-kdj",
    "frozen-controls",
)
ALLOWED_TASKS = frozenset(DEFAULT_TASKS)
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data/output/optimization/research-lane"
DEFAULT_LOCK_PATH = ROOT_DIR / "runtime/logs/isolated-research-lane.lock"


def research_commands(
    *,
    as_of_issue: str,
    workers: int,
    output_dir: Path,
    train_mode: str,
    train_window: int,
    eval_window: int,
    top_n: int,
    history_scope: str,
    regime_years: int,
    random_seeds: str,
    tasks: tuple[str, ...],
) -> list[tuple[str, list[str]]]:
    common = [
        "--as-of-issue",
        as_of_issue,
        "--train-mode",
        train_mode,
        "--train-window",
        str(train_window),
        "--eval-window",
        str(eval_window),
        "--top-n",
        str(top_n),
        "--history-scope",
        history_scope,
        "--regime-years",
        str(regime_years),
    ]
    commands = {
        "training-diagnostics": (
            "training_diagnostics",
            [
                sys.executable,
                "scripts/generate_training_diagnostics.py",
                "--read-only",
                "--output-dir",
                str(output_dir / "training-diagnostics"),
            ],
        ),
        "walk-forward": (
            "walk_forward_optimization",
            [
                sys.executable,
                "scripts/run_walk_forward_optimization.py",
                *common,
                "--workers",
                str(workers),
                "--output-dir",
                str(output_dir / "walk-forward"),
            ],
        ),
        "weight-grid": (
            "weight_grid_search",
            [
                sys.executable,
                "scripts/run_weight_grid_search.py",
                *common,
                "--workers",
                str(workers),
                "--output-dir",
                str(output_dir / "weight-grid"),
            ],
        ),
        "feature-ablation": (
            "feature_family_ablation",
            [
                sys.executable,
                "scripts/run_feature_ablation.py",
                "--read-only",
                *common,
                "--workers",
                str(workers),
                "--output-dir",
                str(output_dir / "feature-ablation"),
            ],
        ),
        "dynamic-kdj": (
            "dynamic_kdj_frozen_backtest",
            [
                sys.executable,
                "scripts/run_dynamic_kdj_backtest.py",
                "--read-only",
                *common,
                "--output-dir",
                str(output_dir / "dynamic-kdj"),
            ],
        ),
        "frozen-controls": (
            "kdj_advisor_frozen_controls",
            [
                sys.executable,
                "scripts/run_control_experiments.py",
                "--read-only",
                "--candidate-source",
                "kdj",
                *common,
                "--random-seeds",
                random_seeds,
                "--workers",
                str(workers),
                "--output-dir",
                str(output_dir / "kdj-controls"),
            ],
        ),
    }
    return [commands[task] for task in tasks]


def manifest_matches(manifest: Any, *, training_fingerprint: str) -> bool:
    return completed_manifest_matches(
        manifest,
        lane_key=LANE_KEY,
        training_fingerprint=training_fingerprint,
    )


def parse_random_seeds(value: str) -> tuple[int, ...]:
    try:
        seeds = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise ValueError("--random-seeds must be comma-separated integers") from exc
    if not seeds:
        raise ValueError("--random-seeds must contain at least one integer")
    return seeds


def parse_tasks(value: str) -> tuple[str, ...]:
    tasks = tuple(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))
    if not tasks:
        raise ValueError("--tasks must contain at least one task")
    unknown = sorted(set(tasks) - ALLOWED_TASKS)
    if unknown:
        raise ValueError(f"unknown research tasks: {','.join(unknown)}")
    return tasks


def build_training_contract(
    *,
    args: argparse.Namespace,
    history_fingerprint_value: str,
) -> ResearchTrainingFingerprint:
    seeds = parse_random_seeds(args.random_seeds)
    tasks = parse_tasks(args.tasks)
    config = {
        "profile_key": args.profile_key,
        "train_mode": args.train_mode,
        "train_window": args.train_window,
        "eval_window": args.eval_window,
        "top_n": args.top_n,
        "history_scope": args.history_scope,
        "regime_years": args.regime_years,
        "random_seeds": list(seeds),
        "tasks": list(tasks),
    }
    return ResearchTrainingFingerprint(
        history_max_issue=args.as_of_issue,
        history_fingerprint=history_fingerprint_value,
        training_mode=args.mode,
        suite_version=SUITE_VERSION,
        model_version=args.model_version,
        feature_version=args.feature_version,
        candidate_algorithm_version=args.candidate_algorithm_version,
        config=config,
        code_commit=resolve_git_commit(REPO_ROOT),
        seed=seeds[0],
    )


def load_manifest(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def fingerprint_manifest_path(output_dir: Path, training_fingerprint: str) -> Path:
    return output_dir / f"isolated-research-lane-{training_fingerprint}.json"


def render_report(payload: dict[str, Any]) -> str:
    runs = payload.get("runs") if isinstance(payload.get("runs"), list) else []
    rows = [
        "# Isolated Historical Research Lane",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- As-of issue: `{payload.get('as_of_issue')}`",
        f"- Suite: `{payload.get('suite_version')}`",
        f"- Training fingerprint: `{payload.get('training_fingerprint')}`",
        f"- Config hash: `{payload.get('config_hash')}`",
        f"- Code commit: `{payload.get('code_commit')}`",
        f"- History fingerprint: `{payload.get('history_fingerprint')}`",
        "- Boundary: PostgreSQL is transaction-read-only; this suite does not run the training supervisor used for production, write current prediction candidates, select a line, or promote a model.",
        "",
        "## Fixed audits",
        "",
    ]
    for run in runs:
        rows.append(
            f"- `{run.get('name')}`: `{run.get('status')}` "
            f"({run.get('elapsed_seconds')}s; log `{run.get('log_path')}`)"
        )
    rows.extend(
        [
            "",
            "Results are historical diagnostics only. They require the normal frozen and forward-evidence gates before any main-line change.",
            "",
        ]
    )
    return "\n".join(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a fixed, isolated DEHPS historical research suite.")
    parser.add_argument("--mode", choices=[RESEARCH_EXECUTION_MODE], default=RESEARCH_EXECUTION_MODE)
    parser.add_argument("--as-of-issue", required=True)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--profile-key", default=os.getenv("DEHPS_RESEARCH_PROFILE", "idle-optimization-default"))
    parser.add_argument("--train-mode", choices=["expanding", "rolling"], default="expanding")
    parser.add_argument("--train-window", type=int, default=900)
    parser.add_argument("--eval-window", type=int, default=100)
    parser.add_argument("--top-n", type=int, default=10000)
    parser.add_argument("--history-scope", choices=["full_history_audit", "current_regime_default"], default="current_regime_default")
    parser.add_argument("--regime-years", type=int, default=10)
    parser.add_argument("--random-seeds", default=os.getenv("DEHPS_RESEARCH_RANDOM_SEEDS", "11,23,37"))
    parser.add_argument(
        "--tasks",
        default=os.getenv("DEHPS_RESEARCH_TASKS", ",".join(DEFAULT_TASKS)),
        help="Comma-separated idle optimization tasks.",
    )
    parser.add_argument("--model-version", default=os.getenv("DEHPS_RESEARCH_MODEL_VERSION", DEFAULT_MODEL_VERSION))
    parser.add_argument("--feature-version", default=os.getenv("DEHPS_RESEARCH_FEATURE_VERSION", DEFAULT_FEATURE_VERSION))
    parser.add_argument(
        "--candidate-algorithm-version",
        default=os.getenv("DEHPS_RESEARCH_CANDIDATE_ALGORITHM_VERSION", DEFAULT_CANDIDATE_ALGORITHM_VERSION),
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--lock-path", type=Path, default=DEFAULT_LOCK_PATH)
    parser.add_argument(
        "--check-completed",
        action="store_true",
        help="Exit successfully only when this exact research fingerprint already completed.",
    )
    parser.add_argument(
        "--print-fingerprint",
        action="store_true",
        help="Print the resolved research fingerprint without running the suite.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.workers < 1:
        raise ValueError("--workers must be positive")
    for name in ("train_window", "eval_window", "top_n", "regime_years"):
        if int(getattr(args, name)) < 1:
            raise ValueError(f"--{name.replace('_', '-')} must be positive")

    database_guard = apply_read_only_database_guard(True)

    with get_connection() as conn:
        selection = select_history(
            conn,
            scope=args.history_scope,
            as_of_issue=args.as_of_issue,
            regime_years=args.regime_years,
        )
    if not selection.dated_history:
        raise ValueError("selected history is empty")
    observed_issue = str(selection.dated_history[-1][0])
    if observed_issue != args.as_of_issue:
        raise ValueError(f"as-of issue mismatch: requested={args.as_of_issue} observed={observed_issue}")
    history_fingerprint_value = fingerprint_history(selection.dated_history)
    contract = build_training_contract(
        args=args,
        history_fingerprint_value=history_fingerprint_value,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    latest_path = args.output_dir / "isolated-research-lane-latest.json"
    completed_path = fingerprint_manifest_path(args.output_dir, contract.value)
    previous = load_manifest(completed_path) or load_manifest(latest_path)
    already_completed = manifest_matches(
        previous,
        training_fingerprint=contract.value,
    )
    if args.print_fingerprint or args.check_completed:
        print(
            json.dumps(
                {
                    "status": "already_completed" if already_completed else "not_completed",
                    "lane_key": LANE_KEY,
                    **contract.as_dict(),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        if args.check_completed and not already_completed:
            raise SystemExit(1)
        return

    args.lock_path.parent.mkdir(parents=True, exist_ok=True)
    with args.lock_path.open("a+", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "already_running", "lane_key": LANE_KEY}, ensure_ascii=False))
            return
        if manifest_matches(
            previous,
            training_fingerprint=contract.value,
        ):
            print(
                json.dumps(
                    {
                        "status": "already_completed_for_fingerprint",
                        "lane_key": LANE_KEY,
                        "as_of_issue": args.as_of_issue,
                        "suite_version": SUITE_VERSION,
                        "training_fingerprint": contract.value,
                    },
                    ensure_ascii=False,
                )
            )
            return

        started = time.monotonic()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        tasks = parse_tasks(args.tasks)
        payload: dict[str, Any] = {
            "status": "running",
            "lane_key": LANE_KEY,
            "suite_version": SUITE_VERSION,
            "as_of_issue": args.as_of_issue,
            "history_fingerprint": history_fingerprint_value,
            **contract.as_dict(),
            "database_guard": database_guard,
            "selection_changed": False,
            "promotion_allowed": False,
            "main_candidate_write_allowed": False,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "runs": [],
        }
        with heavy_job_lock(
            owner="research-training",
            timeout_seconds=0.0,
            context={
                "training_fingerprint": contract.value,
                "as_of_issue": args.as_of_issue,
                "tasks": list(tasks),
                "production_prediction_write_allowed": False,
            },
        ) as heavy_lock:
            for name, command in research_commands(
                as_of_issue=args.as_of_issue,
                workers=args.workers,
                output_dir=args.output_dir,
                train_mode=args.train_mode,
                train_window=args.train_window,
                eval_window=args.eval_window,
                top_n=args.top_n,
                history_scope=args.history_scope,
                regime_years=args.regime_years,
                random_seeds=args.random_seeds,
                tasks=tasks,
            ):
                log_path = args.output_dir / f"{stamp}-{name}.log"
                command_started = time.monotonic()
                heavy_lock.heartbeat(
                    status="running",
                    context={"task": name, "training_fingerprint": contract.value},
                )
                with log_path.open("w", encoding="utf-8") as log_handle:
                    completed = subprocess.run(
                        command,
                        cwd=WORKER_ROOT,
                        stdout=log_handle,
                        stderr=subprocess.STDOUT,
                        check=False,
                        text=True,
                    )
                result = {
                    "name": name,
                    "status": "completed" if completed.returncode == 0 else "failed",
                    "returncode": completed.returncode,
                    "elapsed_seconds": round(time.monotonic() - command_started, 3),
                    "log_path": str(log_path),
                }
                payload["runs"].append(result)
                if completed.returncode != 0:
                    payload["status"] = "failed"
                    break
            else:
                payload["status"] = "completed"
        payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        payload["elapsed_seconds"] = round(time.monotonic() - started, 3)
        report_path = args.output_dir / f"isolated-research-lane-{stamp}.md"
        payload["report_path"] = str(report_path)
        encoded_payload = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"
        completed_path.write_text(encoded_payload, encoding="utf-8")
        latest_path.write_text(encoded_payload, encoding="utf-8")
        report_path.write_text(render_report(payload), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        if payload["status"] != "completed":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
