from __future__ import annotations

import argparse
import json
from pathlib import Path

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.regime import HistoryScope, select_history
from dehps.optimization.walk_forward import WalkForwardResult, deterministic_run_key, random_uniform_baseline, run_walk_forward
from dehps.storage.postgres_store import load_red_combination_universe


def numbers_text(numbers: tuple[int, ...]) -> str:
    return " ".join(f"{number:02d}" for number in numbers)


def render_walk_forward_report(
    result: WalkForwardResult,
    config: FrequencyRankerConfig,
    *,
    history_scope: str = "",
    regime_years: int | None = None,
    regime_start_date: str = "",
    regime_evidence_note: str = "",
) -> str:
    random_baseline = random_uniform_baseline(
        evaluated_draws=result.evaluated_draws,
        universe_size=result.universe_size,
    )
    ranks = "\n".join(
        (
            f"| {rank.issue} | {rank.rank} | {rank.score:.8f} | "
            f"{rank.hit_top_100} | {rank.hit_top_1000} | {rank.hit_top_10000} |"
        )
        for rank in result.target_ranks
    )
    zero_ranks = "\n".join(
        (
            f"| {rank.issue} | {rank.rank} | {rank.score:.8f} | "
            f"{rank.hit_top_100} | {rank.hit_top_1000} | {rank.hit_top_10000} |"
        )
        for rank in result.zero_model_target_ranks
    )
    candidates = "\n".join(
        f"| {rank} | `{numbers_text(numbers)}` | {score:.8f} |"
        for rank, numbers, score in result.top_candidates[:20]
    )
    return f"""# DEHPS Walk-Forward Optimization Report

- Strategy: `{result.strategy_key}`
- As-of issue: `{result.as_of_issue}`
- History fingerprint: `{result.history_fingerprint}`
- Config hash: `{result.config_hash}`
- Train window: {result.train_window}
- Eval window: {result.eval_window}
- Candidate cutoff: top {result.top_n}
- Workers: {result.workers}
- Universe size: {result.universe_size}
- History scope: `{history_scope}`
- Regime years: {regime_years if regime_years is not None else ""}
- Regime start date: {regime_start_date}
- Regime evidence note: {regime_evidence_note}

## Frozen Config

```json
{json.dumps(config.__dict__, indent=2, sort_keys=True)}
```

## Metrics

- evaluated_draws: {result.evaluated_draws}
- top_100_hits: {result.top_100_hits}
- top_1000_hits: {result.top_1000_hits}
- top_10000_hits: {result.top_10000_hits}
- top_100_hit_rate: {result.top_100_hits / result.evaluated_draws if result.evaluated_draws else 0:.6f}
- top_1000_hit_rate: {result.top_1000_hits / result.evaluated_draws if result.evaluated_draws else 0:.6f}
- top_10000_hit_rate: {result.top_10000_hits / result.evaluated_draws if result.evaluated_draws else 0:.6f}

## Baselines

Random uniform baseline is analytical only. It is not used to generate candidates.

| Baseline | Top 100 | Top 1000 | Top 10000 |
| --- | --- | --- | --- |
| Random expected hits | {random_baseline["top_100"]["expected_hits"]:.4f} | {random_baseline["top_1000"]["expected_hits"]:.4f} | {random_baseline["top_10000"]["expected_hits"]:.4f} |
| Structural zero-model hits | {result.zero_model_top_100_hits} | {result.zero_model_top_1000_hits} | {result.zero_model_top_10000_hits} |
| Frequency model hits | {result.top_100_hits} | {result.top_1000_hits} | {result.top_10000_hits} |

## Target Rank Distribution

| Issue | Rank | Score | Top 100 | Top 1000 | Top 10000 |
| --- | --- | --- | --- | --- | --- |
{ranks}

## Structural Zero-Model Rank Distribution

| Issue | Rank | Score | Top 100 | Top 1000 | Top 10000 |
| --- | --- | --- | --- | --- | --- |
{zero_ranks}

## Next Top Candidates Preview

| Rank | Red numbers | Score |
| --- | --- | --- |
{candidates}

## Protocol

- For each target issue, train only on draws before that issue.
- Rank the same legal red-ball sample space for every target.
- Generate candidates by scanning the full deterministic C(33,6) red-ball universe and sorting by frozen score rules.
- Report exact target rank instead of only pass/fail.
- Treat Top 100 as the hard optimization target and Top 10000 as the broad coverage target.

## Risk Note

This walk-forward report measures historical ranking behavior. It does not prove predictive ability or provide betting advice.
"""


def run_optimization(
    *,
    train_window: int,
    eval_window: int,
    top_n: int,
    as_of_issue: str | None = None,
    workers: int | None = None,
    history_scope: HistoryScope = "current_regime_default",
    regime_years: int = 10,
    output_dir: Path | None = None,
) -> dict[str, str | int]:
    config = FrequencyRankerConfig()
    with get_connection() as conn:
        selection = select_history(
            conn,
            scope=history_scope,
            as_of_issue=as_of_issue,
            regime_years=regime_years,
        )
        universe = load_red_combination_universe(conn)

    result = run_walk_forward(
        history=selection.history,
        train_window=train_window,
        eval_window=eval_window,
        top_n=top_n,
        config=config,
        universe=universe,
        workers=workers,
    )
    key = deterministic_run_key(
        strategy_key=result.strategy_key,
        as_of_issue=result.as_of_issue,
        train_window=result.train_window,
        eval_window=result.eval_window,
        top_n=result.top_n,
        history_fingerprint_value=result.history_fingerprint,
        config_hash_value=result.config_hash,
    )
    root = output_dir or ROOT_DIR / "data/output/optimization"
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / f"{key}.json"
    report_path = root / f"{key}.md"
    json_path.write_text(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    report_path.write_text(
        render_walk_forward_report(
            result,
            config,
            history_scope=selection.scope,
            regime_years=selection.regime_years,
            regime_start_date=selection.start_date.isoformat() if selection.start_date else "",
            regime_evidence_note=selection.evidence_note,
        )
    )
    return {
        "key": key,
        "strategy_key": result.strategy_key,
        "as_of_issue": result.as_of_issue,
        "history_fingerprint": result.history_fingerprint,
        "config_hash": result.config_hash,
        "evaluated_draws": result.evaluated_draws,
        "top_100_hits": result.top_100_hits,
        "top_1000_hits": result.top_1000_hits,
        "top_10000_hits": result.top_10000_hits,
        "workers": result.workers,
        "history_scope": selection.scope,
        "regime_years": selection.regime_years,
        "regime_start_date": selection.start_date.isoformat() if selection.start_date else "",
        "regime_evidence_note": selection.evidence_note,
        "json_path": str(json_path),
        "report_path": str(report_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-window", type=int, default=100)
    parser.add_argument("--eval-window", type=int, default=20)
    parser.add_argument("--top-n", type=int, default=10000)
    parser.add_argument("--as-of-issue")
    parser.add_argument("--workers", type=int)
    parser.add_argument("--history-scope", choices=["full_history_audit", "current_regime_default"], default="current_regime_default")
    parser.add_argument("--regime-years", type=int, default=10)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(
        run_optimization(
            train_window=args.train_window,
            eval_window=args.eval_window,
            top_n=args.top_n,
            as_of_issue=args.as_of_issue,
            workers=args.workers,
            history_scope=args.history_scope,
            regime_years=args.regime_years,
            output_dir=args.output_dir,
        ),
    )


if __name__ == "__main__":
    main()
