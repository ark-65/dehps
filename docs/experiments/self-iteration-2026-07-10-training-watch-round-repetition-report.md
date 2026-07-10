# Self Iteration: Training Watch Round Repetition Diagnostic

- Date: 2026-07-10
- Branch: `chore/self-iterate-20260710-1002-training-watch-repetition`
- Primary goal: add a watcher-only diagnostic for repeated recent training rounds.
- Non-goals: no model changes, no advisor changes, no candidate-source changes, no weight-bound changes, no betting recommendation.

## Context

The active supervisor run `20260710-092258` was healthy at watch time, with fresh progress and no DB read error. The latest watch output also showed repeated recent round behavior: the same best config and same core rank metrics repeated across the recent window.

This is an operational search-observability concern, not evidence of predictive edge.

## Gauss/Riemann Diagnostic

- Task Frame: inspect whether repeated recent training rounds should cause a small code change.
- Historical Boundary: Gauss and Riemann are used here as historically inspired verification and structure lenses, not literal minds or authority.
- Gauss Pass: legal sample space remains `ssq_red_ball_combinations`; current watch reports `legal_universe_size=1107568`, `ranked_universe_size=1105506`, `excluded_universe_count=2062`, historical expanding window `train_window=900`, `eval_window=100`, and random ranked-uniform null context. The safe change is to measure repeated configs and repeated metric signatures without changing selection logic.
- Riemann Pass: the local symptom is a repeated point in the training response surface. The smallest structural improvement is to expose whether the recent window is varying or collapsed, rather than adding a new search direction.
- Cross-Review: do not promote historical repetition into a predictive claim; do not treat the diagnostic as a restart decision.
- Synthesis: add a read-only `round_repetition` watcher summary and Markdown section.
- Next Verification: continue monitoring future watch artifacts for whether repeated round windows correlate with rank-homogeneity gates or restart evidence.

## Change

`watch_training_progress.py` now computes a `round_repetition` diagnostic over the recent rows:

- best-config signature count and latest repeat streak
- core metric signature count and latest repeat streak
- active reason such as `same_config_and_metrics_repeated`
- explicit interpretation that this is diagnostic-only and not predictive evidence

The diagnostic appears in JSON, CLI operator summary, and Markdown output.

## Validation

- `apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py apps/worker-python/tests/test_training_watch_restart_guard.py`
- `apps/worker-python/.venv/bin/python -m compileall -q apps/worker-python/scripts/watch_training_progress.py`
- `apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5`

Live watcher validation reported `round_repetition.active=true`, reason `same_config_and_metrics_repeated`, window `5`, while keeping severity `ok` and action `continue_current_run`.

## Guardrail

Evidence level remains `operational_training_diagnostic_no_predictive_claim`. The diagnostic includes no guarantee of hits, no low-risk betting implication, and no automatic promotion. Baseline/null model, leakage checks, parser/sync duplicate status, uncertainty, and failure modes remain carried by the watcher evidence context.
