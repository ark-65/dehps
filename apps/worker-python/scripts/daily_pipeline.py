from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import date, datetime

from dehps.backtest.coverage import run_baseline_backtest
from dehps.backtest.report import render_daily_report, render_experiment_report
from dehps.config import ROOT_DIR, get_settings
from dehps.crawler.ssq_sync import sync_ssq
from dehps.db import get_connection
from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.next_candidates import refresh_training_next_candidates_current
from dehps.optimization.weight_kdj import DEFAULT_KDJ_WINDOW
from dehps.runtime.heavy_job import HeavyJobLock, apply_cpu_thread_env_defaults
from dehps.storage.postgres_store import (
    create_pipeline_run,
    finish_pipeline_run,
    latest_draw,
    load_history,
    previous_experiment_metrics,
    save_experiment,
)
from scripts.generate_weight_kdj_signals import CANONICAL_SIGNAL_RUN_ID, generate_signals, parse_weights


def _latest_local_issue() -> str | None:
    with get_connection() as conn:
        row = conn.execute("SELECT max(issue) FROM ssq_history").fetchone()
    if not row or not row[0]:
        return None
    return str(row[0])


def _sync_for_source(source: str, *, csv_file: str | None, run_key: str) -> dict:
    if source == "zhcw":
        latest_issue = _latest_local_issue()
        return sync_ssq(
            source,
            history=True,
            from_issue=latest_issue,
            csv_file=csv_file,
            run_key=run_key,
        )
    return sync_ssq(source, history=(source == "csv"), csv_file=csv_file, run_key=run_key)


def _load_git_helper():
    helper_path = ROOT_DIR / "apps/worker-python/scripts/git_commit_and_push.py"
    spec = importlib.util.spec_from_file_location("git_commit_and_push", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load git helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _heartbeat_heavy_lock(
    heavy_lock: HeavyJobLock | None,
    *,
    status: str | None = None,
    context: dict | None = None,
) -> bool:
    if heavy_lock is None:
        return False
    try:
        heavy_lock.heartbeat(status=status, context=context)
    except Exception as exc:
        print(f"[daily_pipeline] heavy_job_heartbeat_warning error={exc}", file=sys.stderr, flush=True)
        return False
    return True


def run_pipeline(
    strategy_key: str,
    source: str,
    *,
    csv_file: str | None = None,
    auto_git: bool = False,
    force: bool = False,
    skip_weight_kdj_signals: bool = False,
    heavy_job_lock_timeout_seconds: float = 0.0,
    cpu_threads: int = 1,
) -> dict:
    apply_cpu_thread_env_defaults(cpu_threads)
    settings = get_settings()
    run_key = f"daily-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    experiment_key = f"{strategy_key}-{run_key}"
    summary: dict = {"run_key": run_key, "source": source, "strategy_key": strategy_key}
    heavy_lock: HeavyJobLock | None = None

    with get_connection() as conn:
        create_pipeline_run(conn, run_key)

    try:
        heavy_lock = HeavyJobLock(
            owner="daily-pipeline",
            lock_path=ROOT_DIR / "runtime/logs/dehps-heavy-job.lock",
            timeout_seconds=heavy_job_lock_timeout_seconds,
            context={
                "run_key": run_key,
                "source": source,
                "strategy_key": strategy_key,
                "skip_weight_kdj_signals": skip_weight_kdj_signals,
            },
        ).acquire()
        sync_summary = _sync_for_source(source, csv_file=csv_file, run_key=f"{run_key}-sync")
        is_new_data = sync_summary.get("inserted_count", 0) > 0
        has_synced_changes = is_new_data or sync_summary.get("updated_count", 0) > 0
        summary["sync_run_key"] = sync_summary["run_key"]
        summary["sync"] = sync_summary
        _heartbeat_heavy_lock(
            heavy_lock,
            context={"sync_run_key": sync_summary["run_key"], "has_synced_changes": has_synced_changes},
        )

        metrics = {
            "total_combinations": 1107568,
            "kept_combinations": 0,
            "keep_rate": 0,
            "history_draws": 0,
            "covered_draws": 0,
            "coverage_rate": 0,
            "lift": 0,
        }
        previous = None
        latest = sync_summary.get("latest_draw")

        if is_new_data or force:
            with get_connection() as conn:
                history = load_history(conn)
                previous = previous_experiment_metrics(conn, strategy_key)
                latest = latest_draw(conn) or latest
                metrics = run_baseline_backtest(history)
                experiment_report = render_experiment_report(experiment_key, strategy_key, metrics)
                save_experiment(conn, experiment_key, strategy_key, metrics, experiment_report)
            experiment_path = ROOT_DIR / "data/output/experiments" / f"{experiment_key}.md"
            experiment_path.parent.mkdir(parents=True, exist_ok=True)
            experiment_path.write_text(experiment_report)
            summary["experiment_key"] = experiment_key
            summary["experiment_report_path"] = str(experiment_path)

        if has_synced_changes and not skip_weight_kdj_signals:
            summary["weight_kdj"] = generate_signals(
                signal_run_id=CANONICAL_SIGNAL_RUN_ID,
                mode="incremental",
                as_of_issue=None,
                issues=1000,
                allow_partial=True,
                train_mode="expanding",
                train_window=900,
                top_n=10000,
                weights=parse_weights(None),
                primary_step=0.03,
                context_step=0.01,
                kdj_window=DEFAULT_KDJ_WINDOW,
                chunk_size=25,
                base_config=FrequencyRankerConfig(),
                dry_run=False,
            )
            _heartbeat_heavy_lock(heavy_lock, context={"weight_kdj": summary["weight_kdj"]})

        if has_synced_changes:
            try:
                with get_connection() as conn:
                    summary["training_next_candidates"] = refresh_training_next_candidates_current(conn, top_n=10000)
            except Exception as exc:
                summary["training_next_candidates"] = {"status": "failed", "error_message": str(exc)}
            _heartbeat_heavy_lock(
                heavy_lock,
                context={"training_next_candidates": summary["training_next_candidates"]},
            )

        daily_report = render_daily_report(run_key, source, latest, is_new_data, metrics, previous)
        daily_path = ROOT_DIR / "data/output/daily" / f"{date.today().isoformat()}-dehps-daily-report.md"
        daily_path.parent.mkdir(parents=True, exist_ok=True)
        daily_path.write_text(daily_report)
        summary["daily_report_path"] = str(daily_path)
        summary["metrics"] = metrics

        if auto_git or settings.dehps_auto_git:
            git_helper = _load_git_helper()
            issue = latest.get("issue") if latest else "unknown"
            git_result = git_helper.git_commit_and_push(
                f"chore(data): sync ssq draw {issue}",
                push=True,
                remote=settings.dehps_git_remote,
                branch=settings.dehps_git_branch,
            )
            summary["git"] = git_result
            summary["git_commit_sha"] = git_result.get("sha")
            if git_result.get("status") == "push_failed":
                summary["error_message"] = git_result.get("error")

        with get_connection() as conn:
            finish_pipeline_run(conn, run_key, "success", summary)
        _heartbeat_heavy_lock(heavy_lock, status="completed", context={"daily_report_path": summary["daily_report_path"]})
        return summary
    except Exception as exc:
        summary["error_message"] = str(exc)
        _heartbeat_heavy_lock(heavy_lock, status="failed", context={"error": str(exc)})
        with get_connection() as conn:
            finish_pipeline_run(conn, run_key, "failed", summary)
        raise
    finally:
        if heavy_lock is not None:
            heavy_lock.release()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy-key", default="baseline_v1")
    parser.add_argument("--source", default="zhcw", choices=["zhcw", "csv"])
    parser.add_argument("--csv-file", help="Explicit CSV path when --source csv is used")
    parser.add_argument("--auto-git", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-weight-kdj-signals", action="store_true")
    parser.add_argument("--heavy-job-lock-timeout-seconds", type=float, default=0.0)
    parser.add_argument("--cpu-threads", type=int, default=1)
    args = parser.parse_args()
    if args.source == "csv" and not args.csv_file and not get_settings().ssq_csv_path:
        parser.error("--source csv requires --csv-file or SSQ_CSV_PATH")
    print(
        run_pipeline(
            args.strategy_key,
            args.source,
            csv_file=args.csv_file,
            auto_git=args.auto_git,
            force=args.force,
            skip_weight_kdj_signals=args.skip_weight_kdj_signals,
            heavy_job_lock_timeout_seconds=args.heavy_job_lock_timeout_seconds,
            cpu_threads=args.cpu_threads,
        )
    )


if __name__ == "__main__":
    main()
