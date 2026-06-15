from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from dehps.backtest.coverage import run_baseline_backtest
from dehps.backtest.report import render_experiment_report
from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.storage.postgres_store import load_history, save_experiment


def run_backtest(strategy_key: str) -> dict:
    experiment_key = f"{strategy_key}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    with get_connection() as conn:
        history = load_history(conn)
        metrics = run_baseline_backtest(history)
        report = render_experiment_report(experiment_key, strategy_key, metrics)
        save_experiment(conn, experiment_key, strategy_key, metrics, report)
    output = ROOT_DIR / "data/output/experiments" / f"{experiment_key}.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report)
    return {"experiment_key": experiment_key, **metrics, "report_path": str(output)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy-key", default="baseline_v1")
    args = parser.parse_args()
    print(run_backtest(args.strategy_key))


if __name__ == "__main__":
    main()

