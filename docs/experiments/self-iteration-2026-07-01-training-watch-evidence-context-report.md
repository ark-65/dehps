# Self-Iteration Report: Training Watch Evidence Context

## Primary Goal

Expose the evidence boundary of a training-watch alert in both JSON and Markdown so an operator can see the legal sample space, historical window, operational baseline, leakage guardrails, uncertainty, and failure modes without opening the full supervisor artifact.

## Non-Goals

- Do not change training strategy, advisor budgets, candidate sources, weight bounds, promotion gates, or supervisor restart behavior.
- Do not claim predictive lift, betting edge, guaranteed hits, or low-risk betting advice from the stalled run.
- Do not stop or replace the active supervisor process.

## Runtime Observation

- Latest watched run: `20260701-040511`.
- Current watcher result after the change: `round_count=148`, `severity=alert`, `action=prepare_restart_with_more_exploration`.
- The active heavy-job lock still belongs to the current training supervisor, so restart preparation remains blocked by live runtime state.
- Evidence context now reports `legal_universe=1107568`, `ranked_universe=1105506`, `excluded=2062`, `history_scope=current_regime_default`, `train_window=900`, `eval_window=100`, and `top_n=10000`.

## Gauss/Riemann Diagnostic

- Task Frame: the object is the watch report for an already-running DEHPS training supervisor. Progress means stronger observability of the evidence boundary, not a new search heuristic.
- Historical Boundary: Gauss and Riemann are used as historically inspired verification and structural lenses, not literal minds, authorities, or complete reconstructions.
- Gauss Pass: the measurable residual remains eval-slice strength versus frozen-validation failure. The report now states the legal sample space, historical window, incumbent frozen-primary baseline, eval-slice overfit guardrail, and the fact that parser/sync/duplicate checks are not rerun by the watcher. No performance claim is accepted without those boundaries.
- Riemann Pass: the stalled run lives across several state spaces: completed DB rounds, in-progress supervisor status, guardrail decisions, and runtime lock ownership. The new evidence context makes those boundaries visible in one operator-facing surface instead of leaving them distributed across artifacts.
- Cross-Review: Gauss rejects using `Top100/1000/10000=3/3/3` as proof while frozen primary remains `[0, 0, 0]`. Riemann rejects an alert that names stagnation but hides the sample-space and validation surface on which the alert is defined.
- Disagreement: this does not prove that broader exploration will improve frozen validation; it only makes the current diagnostic state auditable.
- Synthesis: the smallest supported conclusion is an operational observability improvement for a stalled training watch alert.
- Next Verification: continue monitoring the active supervisor; if the current process is intentionally stopped or finishes, only then start a fresh supervisor under the normal heavy-job lock discipline.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py
```

Result: `20 passed`.

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
```

Result: generated a live watch report for `20260701-040511` with the new `evidence_context` JSON field and `## Evidence Context` Markdown section.
