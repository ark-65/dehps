from __future__ import annotations

"""Run isolated historical research while forward production is parked.

The adaptive task reuses the production search implementation under the strict
``observability_only`` persistence policy.  It may select a local research champion,
but never writes current prediction candidates or changes production promotion state.
"""

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = WORKER_ROOT.parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.optimization.regime import select_history
from dehps.optimization.walk_forward import fingerprint_history
from dehps.ranking_contract import STRICT_RANKING_CONTRACT
from dehps.runtime.heavy_job import heavy_job_lock
from dehps.source_version import resolve_git_commit
from dehps.training.persistence_policy import apply_read_only_database_guard
from dehps.training.research_fingerprint import (
    RESEARCH_EXECUTION_MODE,
    ResearchTaskFingerprint,
    ResearchTaskSpec,
    ResearchTrainingFingerprint,
    SeedPolicy,
    completed_manifest_matches,
)


LANE_KEY = "isolated_historical_research"
SUITE_VERSION = "idle-optimization-v4"
DEFAULT_MODEL_VERSION = "frequency-ranker-kdj-v1"
DEFAULT_FEATURE_VERSION = "frequency-ranker-structural-v1"
DEFAULT_CANDIDATE_ALGORITHM_VERSION = "kdj-controls-v1"
DEFAULT_TASKS = (
    "training-diagnostics",
    "analytic-null-baseline",
    "adaptive-success-training",
)
DETERMINISTIC_TASKS = frozenset(
    (*DEFAULT_TASKS, "walk-forward", "weight-grid", "feature-ablation", "dynamic-kdj")
)
STOCHASTIC_TASKS = frozenset(("frozen-controls",))
RANKING_TASKS = frozenset(
    (
        "adaptive-success-training",
        "walk-forward",
        "weight-grid",
        "feature-ablation",
        "dynamic-kdj",
        "frozen-controls",
    )
)
ALLOWED_TASKS = DETERMINISTIC_TASKS | STOCHASTIC_TASKS
TASK_CONFIG_FIELDS = {
    "training-diagnostics": (
        "profile_key",
        "history_scope",
        "regime_years",
        "diagnostics_snapshot",
    ),
    "walk-forward": ("train_mode", "train_window", "eval_window", "top_n", "history_scope", "regime_years"),
    "weight-grid": ("train_mode", "train_window", "eval_window", "top_n", "history_scope", "regime_years"),
    "analytic-null-baseline": ("eval_window", "top_n", "history_scope", "regime_years"),
    "adaptive-success-training": (
        "train_mode",
        "train_window",
        "eval_window",
        "top_n",
        "history_scope",
        "regime_years",
        "workers",
        "adaptive_max_rounds",
        "adaptive_max_configs_per_round",
        "adaptive_memory_budget_gb",
        "adaptive_weight_kdj_budget_share",
        "adaptive_ridge_kdj_budget_share",
        "adaptive_target_inversion_max_candidates",
        "adaptive_target_inversion_max_deltas",
        "continuation_snapshot",
    ),
    "feature-ablation": ("train_mode", "train_window", "eval_window", "top_n", "history_scope", "regime_years"),
    "dynamic-kdj": ("train_mode", "train_window", "eval_window", "top_n", "history_scope", "regime_years"),
    "frozen-controls": (
        "train_mode",
        "train_window",
        "eval_window",
        "top_n",
        "history_scope",
        "regime_years",
        "random_algorithm_version",
        "sampling_method",
        "monte_carlo_trials",
    ),
}
TASK_EVALUATION_CONTRACTS = {
    "training-diagnostics": "training-diagnostics-read-only-v1",
    "walk-forward": "fixed-historical-walk-forward-v1",
    "weight-grid": "complete-weight-grid-v1",
    "analytic-null-baseline": "analytic-uniform-rank-null-v1",
    "adaptive-success-training": "recent-history-success-learning-v1",
    "feature-ablation": "fixed-feature-family-ablation-v1",
    "dynamic-kdj": "frozen-dynamic-kdj-backtest-v1",
    "frozen-controls": "monte-carlo-random-ranking-controls-v1",
}
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data/output/optimization/research-lane"
DEFAULT_LOCK_PATH = ROOT_DIR / "runtime/logs/isolated-research-lane.lock"


def git_worktree_changes(repo_root: Path = REPO_ROOT) -> tuple[str, ...]:
    try:
        result = subprocess.run(
            [
                "git",
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("research_worktree_status_unavailable") from exc
    return tuple(line for line in result.stdout.splitlines() if line.strip())


def require_clean_worktree(repo_root: Path = REPO_ROOT) -> None:
    changes = git_worktree_changes(repo_root)
    if changes:
        preview = ",".join(changes[:5])
        raise RuntimeError(
            "research_requires_clean_worktree:"
            f"change_count={len(changes)}:changes={preview}"
        )


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
    random_seeds: str | None,
    tasks: tuple[str, ...],
    diagnostics_run_id: str | None = None,
    adaptive_max_rounds: int = 512,
    adaptive_max_configs_per_round: int = 96,
    adaptive_memory_budget_gb: int = 24,
    adaptive_weight_kdj_budget_share: float = 0.22,
    adaptive_ridge_kdj_budget_share: float = 0.22,
    adaptive_target_inversion_max_candidates: int = 8,
    adaptive_target_inversion_max_deltas: int = 12,
    adaptive_progress_interval: int = 5,
) -> list[tuple[str, str, list[str]]]:
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
                *(["--run-id", diagnostics_run_id] if diagnostics_run_id else []),
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
        "analytic-null-baseline": (
            "analytic_null_baseline",
            [
                sys.executable,
                "scripts/generate_analytic_null_baseline.py",
                *common,
                "--output-dir",
                str(output_dir / "analytic-null-baseline"),
            ],
        ),
        "adaptive-success-training": (
            "adaptive_success_training",
            [
                sys.executable,
                "scripts/run_training_supervisor.py",
                "--observability-only",
                "--max-rounds",
                str(adaptive_max_rounds),
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
                "--workers",
                str(workers),
                "--max-configs-per-round",
                str(adaptive_max_configs_per_round),
                "--memory-budget-gb",
                str(adaptive_memory_budget_gb),
                "--progress-interval",
                str(adaptive_progress_interval),
                "--output-dir",
                str(output_dir / "adaptive-success-training"),
                "--write-status-json",
                "--enable-weight-kdj-advisor",
                "--weight-kdj-budget-share",
                str(adaptive_weight_kdj_budget_share),
                "--enable-ridge-kdj-advisor",
                "--ridge-kdj-budget-share",
                str(adaptive_ridge_kdj_budget_share),
                "--target-weight-inversion-max-candidates",
                str(adaptive_target_inversion_max_candidates),
                "--target-weight-inversion-max-targets",
                str(eval_window),
                "--target-weight-inversion-max-deltas-per-target",
                str(adaptive_target_inversion_max_deltas),
                "--cpu-threads",
                "1",
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
                str(random_seeds or ""),
                "--workers",
                str(workers),
                "--output-dir",
                str(output_dir / "kdj-controls"),
            ],
        ),
    }
    if "frozen-controls" in tasks and not str(random_seeds or "").strip():
        raise ValueError("stochastic frozen-controls task requires --random-seeds")
    return [(task, *commands[task]) for task in tasks]


def adaptive_continuation_snapshot(
    output_dir: Path,
    *,
    as_of_issue: str,
    train_mode: str,
    train_window: int,
    eval_window: int,
    top_n: int,
) -> dict[str, Any]:
    """Fingerprint semantic search progress without using run ids or timestamps."""

    task_dir = output_dir / "adaptive-success-training"
    evaluated_hashes: set[str] = set()
    champion_hashes: set[str] = set()
    search_base_hashes: set[str] = set()
    for status_path in sorted(task_dir.glob("training-supervisor-*.json")):
        status = load_manifest(status_path)
        if not isinstance(status, dict):
            continue
        status_candidates = [status.get("best")]
        for round_info in status.get("rounds") or []:
            if isinstance(round_info, dict):
                status_candidates.append(round_info.get("best"))
                status_candidates.extend(round_info.get("top_results") or [])
        observed_issues = {
            str(candidate.get("as_of_issue"))
            for candidate in status_candidates
            if isinstance(candidate, dict) and candidate.get("as_of_issue")
        }
        if (
            status.get("execution_mode") != "observability_only"
            or (observed_issues and observed_issues != {as_of_issue})
            or status.get("train_mode") != train_mode
            or int(status.get("train_window") or 0) != train_window
            or int(status.get("eval_window") or 0) != eval_window
            or int(status.get("top_n") or 0) != top_n
        ):
            continue
        for candidate in status_candidates:
            if isinstance(candidate, dict) and candidate.get("config_hash"):
                evaluated_hashes.add(str(candidate["config_hash"]))
        learning = status.get("research_learning")
        if isinstance(learning, dict):
            champion = learning.get("champion")
            if isinstance(champion, dict) and champion.get("config_hash"):
                champion_hashes.add(str(champion["config_hash"]))
        search_base = status.get("search_base")
        if isinstance(search_base, dict) and search_base.get("config_hash"):
            search_base_hashes.add(str(search_base["config_hash"]))
    semantic_state = {
        "evaluated_config_hashes": sorted(evaluated_hashes),
        "research_champion_hashes": sorted(champion_hashes),
        "search_base_hashes": sorted(search_base_hashes),
    }
    digest = hashlib.sha256(
        json.dumps(semantic_state, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "protocol": "adaptive-search-semantic-continuation-v1",
        "evaluated_config_count": len(evaluated_hashes),
        "semantic_state_digest": digest,
    }


def latest_adaptive_training_status(output_dir: Path) -> dict[str, Any] | None:
    task_dir = output_dir / "adaptive-success-training"
    paths = sorted(
        task_dir.glob("training-supervisor-*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return load_manifest(paths[0]) if paths else None


def execute_research_command(
    *,
    task_type: str,
    name: str,
    command: list[str],
    log_path: Path,
    training_fingerprint: str,
    as_of_issue: str,
) -> subprocess.CompletedProcess[str]:
    lock_context = (
        nullcontext(None)
        if task_type == "adaptive-success-training"
        else heavy_job_lock(
            owner="research-training",
            timeout_seconds=0.0,
            context={
                "training_fingerprint": training_fingerprint,
                "as_of_issue": as_of_issue,
                "task": name,
                "production_prediction_write_allowed": False,
            },
        )
    )
    with lock_context as heavy_lock, log_path.open("w", encoding="utf-8") as log_handle:
        if heavy_lock is not None:
            heavy_lock.heartbeat(
                status="running",
                context={"task": name, "training_fingerprint": training_fingerprint},
            )
        return subprocess.run(
            command,
            cwd=WORKER_ROOT,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
        )


def manifest_matches(manifest: Any, *, training_fingerprint: str) -> bool:
    return completed_manifest_matches(
        manifest,
        lane_key=LANE_KEY,
        training_fingerprint=training_fingerprint,
    )


def parse_random_seeds(value: str | None) -> tuple[int, ...]:
    if value is None or not value.strip():
        return ()
    try:
        seeds = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise ValueError("--random-seeds must be comma-separated integers") from exc
    return tuple(sorted(set(seeds)))


def parse_tasks(value: str) -> tuple[str, ...]:
    tasks = tuple(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))
    if not tasks:
        raise ValueError("--tasks must contain at least one task")
    unknown = sorted(set(tasks) - ALLOWED_TASKS)
    if unknown:
        raise ValueError(f"unknown research tasks: {','.join(unknown)}")
    return tasks


def project_config_for_task(full_config: dict[str, Any], *, task_type: str) -> dict[str, Any]:
    fields = TASK_CONFIG_FIELDS.get(task_type)
    if fields is None:
        raise ValueError(f"unknown research task: {task_type}")
    return {field: full_config[field] for field in fields}


def project_versions_for_task(args: argparse.Namespace, *, task_type: str) -> tuple[str, str, str]:
    if task_type == "training-diagnostics":
        return ("training-diagnostics-v1", "training-round-results-v1", "not-applicable")
    if task_type == "analytic-null-baseline":
        return ("analytic-uniform-rank-null-v1", "not-applicable", "legal-6-of-33-v1")
    return (args.model_version, args.feature_version, args.candidate_algorithm_version)


def training_diagnostics_snapshot(conn, *, run_id: str | None = None) -> dict[str, Any]:
    with conn.cursor(row_factory=dict_row) as cur:
        resolved_run_id = run_id
        if not resolved_run_id:
            latest = cur.execute(
                "SELECT run_id FROM training_round_results ORDER BY updated_at DESC, round_index DESC LIMIT 1"
            ).fetchone()
            resolved_run_id = str(latest["run_id"]) if latest else None
        if not resolved_run_id:
            return {"run_id": None, "row_count": 0, "max_round_index": None, "max_updated_at": None}
        snapshot = cur.execute(
            """
            SELECT count(*)::int AS row_count,
                   max(round_index)::int AS max_round_index,
                   max(updated_at) AS max_updated_at
            FROM training_round_results
            WHERE run_id = %s
            """,
            (resolved_run_id,),
        ).fetchone()
    return {
        "run_id": resolved_run_id,
        "row_count": int(snapshot["row_count"] or 0),
        "max_round_index": snapshot["max_round_index"],
        "max_updated_at": snapshot["max_updated_at"].isoformat() if snapshot["max_updated_at"] else None,
    }


def build_training_contract(
    *,
    args: argparse.Namespace,
    history_fingerprint_value: str,
) -> ResearchTrainingFingerprint:
    seeds = parse_random_seeds(args.random_seeds)
    tasks = parse_tasks(args.tasks)
    stochastic_tasks = tuple(task for task in tasks if task in STOCHASTIC_TASKS)
    if stochastic_tasks and not seeds:
        raise ValueError("stochastic research tasks require an explicit seed policy")
    if not stochastic_tasks and seeds:
        raise ValueError("deterministic research suite does not accept --random-seeds")
    full_config = {
        "profile_key": args.profile_key,
        "train_mode": args.train_mode,
        "train_window": args.train_window,
        "eval_window": args.eval_window,
        "top_n": args.top_n,
        "history_scope": args.history_scope,
        "regime_years": args.regime_years,
        "workers": args.workers,
        "adaptive_max_rounds": args.adaptive_max_rounds,
        "adaptive_max_configs_per_round": args.adaptive_max_configs_per_round,
        "adaptive_memory_budget_gb": args.adaptive_memory_budget_gb,
        "adaptive_weight_kdj_budget_share": args.adaptive_weight_kdj_budget_share,
        "adaptive_ridge_kdj_budget_share": args.adaptive_ridge_kdj_budget_share,
        "adaptive_target_inversion_max_candidates": args.adaptive_target_inversion_max_candidates,
        "adaptive_target_inversion_max_deltas": args.adaptive_target_inversion_max_deltas,
        "continuation_snapshot": getattr(
            args,
            "continuation_snapshot",
            {
                "protocol": "adaptive-search-semantic-continuation-v1",
                "evaluated_config_count": 0,
                "semantic_state_digest": hashlib.sha256(b"{}").hexdigest(),
            },
        ),
        "diagnostics_snapshot": getattr(
            args,
            "diagnostics_snapshot",
            {"run_id": args.diagnostics_run_id, "row_count": None, "max_round_index": None, "max_updated_at": None},
        ),
        "random_algorithm_version": "python-mt19937-uniform-rank-v1",
        "sampling_method": "uniform_integer_rank_with_replacement",
        "monte_carlo_trials": args.eval_window,
    }
    code_commit = resolve_git_commit(REPO_ROOT)
    seed_policy = (
        SeedPolicy(
            seeds=seeds,
            aggregation=args.seed_aggregation,
            selection_policy=args.seed_selection_policy,
        )
        if stochastic_tasks
        else None
    )
    task_fingerprints = []
    for task in tasks:
        model_version, feature_version, candidate_algorithm_version = project_versions_for_task(
            args,
            task_type=task,
        )
        task_fingerprints.append(
            ResearchTaskFingerprint(
                history_max_issue=args.as_of_issue,
                history_fingerprint=history_fingerprint_value,
                training_mode=args.mode,
                model_version=model_version,
                feature_version=feature_version,
                candidate_algorithm_version=candidate_algorithm_version,
                code_commit=code_commit,
                spec=ResearchTaskSpec(
                    task_type=task,
                    execution_mode="stochastic" if task in STOCHASTIC_TASKS else "deterministic",
                    config=project_config_for_task(full_config, task_type=task),
                    evaluation_contract=TASK_EVALUATION_CONTRACTS[task],
                    ranking_contract=(
                        STRICT_RANKING_CONTRACT if task in RANKING_TASKS else None
                    ),
                    seed_policy=seed_policy if task in STOCHASTIC_TASKS else None,
                ),
            )
        )
    return ResearchTrainingFingerprint(
        training_mode=args.mode,
        suite_version=SUITE_VERSION,
        tasks=tuple(task_fingerprints),
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
        "- Boundary: PostgreSQL is transaction-read-only. Adaptive search runs under observability-only policy; it may select a local research champion but cannot write current prediction candidates or change production selection/promotion state.",
        "",
        "## Task executions",
        "",
    ]
    for run in runs:
        rows.append(
            f"- `{run.get('name')}` ({run.get('execution_mode')}): `{run.get('status')}` "
            f"({run.get('elapsed_seconds')}s; ranking contract "
            f"`{run.get('ranking_contract') or 'not_applicable'}`; log `{run.get('log_path')}`)"
        )
    rows.extend(
        [
            "",
            "Research learning is judged on the fixed recent-history success contract. Frozen and forward evidence remain separate gates for any production change.",
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
    parser.add_argument("--adaptive-max-rounds", type=int, default=int(os.getenv("DEHPS_RESEARCH_ADAPTIVE_MAX_ROUNDS", "512")))
    parser.add_argument(
        "--adaptive-max-configs-per-round",
        type=int,
        default=int(os.getenv("DEHPS_RESEARCH_ADAPTIVE_MAX_CONFIGS_PER_ROUND", "96")),
    )
    parser.add_argument(
        "--adaptive-memory-budget-gb",
        type=int,
        default=int(os.getenv("DEHPS_RESEARCH_ADAPTIVE_MEMORY_BUDGET_GB", "24")),
    )
    parser.add_argument(
        "--adaptive-weight-kdj-budget-share",
        type=float,
        default=float(os.getenv("DEHPS_RESEARCH_ADAPTIVE_WEIGHT_KDJ_BUDGET_SHARE", "0.22")),
    )
    parser.add_argument(
        "--adaptive-ridge-kdj-budget-share",
        type=float,
        default=float(os.getenv("DEHPS_RESEARCH_ADAPTIVE_RIDGE_KDJ_BUDGET_SHARE", "0.22")),
    )
    parser.add_argument(
        "--adaptive-target-inversion-max-candidates",
        type=int,
        default=int(os.getenv("DEHPS_RESEARCH_ADAPTIVE_TARGET_INVERSION_MAX_CANDIDATES", "8")),
    )
    parser.add_argument(
        "--adaptive-target-inversion-max-deltas",
        type=int,
        default=int(os.getenv("DEHPS_RESEARCH_ADAPTIVE_TARGET_INVERSION_MAX_DELTAS", "12")),
    )
    parser.add_argument(
        "--adaptive-progress-interval",
        type=int,
        default=int(os.getenv("DEHPS_RESEARCH_ADAPTIVE_PROGRESS_INTERVAL", "5")),
    )
    parser.add_argument("--diagnostics-run-id")
    parser.add_argument("--random-seeds", default=os.getenv("DEHPS_RESEARCH_RANDOM_SEEDS"))
    parser.add_argument("--seed-aggregation", choices=["mean_variance"], default="mean_variance")
    parser.add_argument("--seed-selection-policy", choices=["no_best_seed"], default="no_best_seed")
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
    for name in (
        "train_window",
        "eval_window",
        "top_n",
        "regime_years",
        "adaptive_max_rounds",
        "adaptive_max_configs_per_round",
        "adaptive_memory_budget_gb",
        "adaptive_target_inversion_max_candidates",
        "adaptive_target_inversion_max_deltas",
        "adaptive_progress_interval",
    ):
        if int(getattr(args, name)) < 1:
            raise ValueError(f"--{name.replace('_', '-')} must be positive")

    require_clean_worktree()
    database_guard = apply_read_only_database_guard(True)

    with get_connection() as conn:
        selection = select_history(
            conn,
            scope=args.history_scope,
            as_of_issue=args.as_of_issue,
            regime_years=args.regime_years,
        )
        diagnostics_snapshot = training_diagnostics_snapshot(
            conn,
            run_id=args.diagnostics_run_id,
        )
    args.diagnostics_run_id = diagnostics_snapshot["run_id"]
    args.diagnostics_snapshot = diagnostics_snapshot
    if not selection.dated_history:
        raise ValueError("selected history is empty")
    observed_issue = str(selection.dated_history[-1][0])
    if observed_issue != args.as_of_issue:
        raise ValueError(f"as-of issue mismatch: requested={args.as_of_issue} observed={observed_issue}")
    history_fingerprint_value = fingerprint_history(selection.dated_history)
    args.continuation_snapshot = adaptive_continuation_snapshot(
        args.output_dir,
        as_of_issue=args.as_of_issue,
        train_mode=args.train_mode,
        train_window=args.train_window,
        eval_window=args.eval_window,
        top_n=args.top_n,
    )
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
                    "as_of_issue": args.as_of_issue,
                    "history_fingerprint": history_fingerprint_value,
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
            "code_commit": resolve_git_commit(REPO_ROOT),
            **contract.as_dict(),
            "database_guard": database_guard,
            "research_selection_changed": False,
            "production_selection_changed": False,
            "promotion_allowed": False,
            "main_candidate_write_allowed": False,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "runs": [],
        }
        if tasks:
            task_contracts = {task.spec.task_type: task for task in contract.tasks}
            for task_type, name, command in research_commands(
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
                diagnostics_run_id=args.diagnostics_run_id,
                adaptive_max_rounds=args.adaptive_max_rounds,
                adaptive_max_configs_per_round=args.adaptive_max_configs_per_round,
                adaptive_memory_budget_gb=args.adaptive_memory_budget_gb,
                adaptive_weight_kdj_budget_share=args.adaptive_weight_kdj_budget_share,
                adaptive_ridge_kdj_budget_share=args.adaptive_ridge_kdj_budget_share,
                adaptive_target_inversion_max_candidates=args.adaptive_target_inversion_max_candidates,
                adaptive_target_inversion_max_deltas=args.adaptive_target_inversion_max_deltas,
                adaptive_progress_interval=args.adaptive_progress_interval,
            ):
                task_contract = task_contracts[task_type]
                log_path = args.output_dir / f"{stamp}-{name}.log"
                command_started = time.monotonic()
                completed = execute_research_command(
                    task_type=task_type,
                    name=name,
                    command=command,
                    log_path=log_path,
                    training_fingerprint=contract.value,
                    as_of_issue=args.as_of_issue,
                )
                result = {
                    "task_type": task_type,
                    "name": name,
                    "execution_mode": task_contract.spec.execution_mode,
                    "ranking_contract": task_contract.spec.ranking_contract,
                    "experiment_fingerprint": task_contract.experiment_fingerprint,
                    "status": "completed" if completed.returncode == 0 else "failed",
                    "returncode": completed.returncode,
                    "elapsed_seconds": round(time.monotonic() - command_started, 3),
                    "log_path": str(log_path),
                }
                if task_contract.spec.seed_policy is not None:
                    result["replicates"] = [
                        {
                            "seed": seed,
                            "run_fingerprint": task_contract.run_fingerprint(seed),
                        }
                        for seed in task_contract.spec.seed_policy.seeds
                    ]
                if task_type == "adaptive-success-training":
                    adaptive_status = latest_adaptive_training_status(args.output_dir)
                    learning = (
                        adaptive_status.get("research_learning")
                        if isinstance(adaptive_status, dict)
                        else None
                    )
                    result["persistence_policy"] = (
                        adaptive_status.get("persistence_policy")
                        if isinstance(adaptive_status, dict)
                        else None
                    )
                    result["research_learning"] = learning
                    result["status_path"] = (
                        adaptive_status.get("status_path")
                        if isinstance(adaptive_status, dict)
                        else None
                    )
                    champion = learning.get("champion") if isinstance(learning, dict) else None
                    if isinstance(champion, dict) and champion.get("config_hash"):
                        payload["research_selection_changed"] = True
                        payload["research_champion"] = champion
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
