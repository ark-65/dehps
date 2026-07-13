# Round 19 - Production Runtime Decomposition Phase 1

## Goal

Move one production training round behind an explicit request/state/outcome boundary and make the production Supervisor call `TrainingRoundRunner.run(request)` without changing algorithms, feature formulas, thresholds, search shares, evaluation windows, promotion rules, or persistence schemas.

## Non-goals

- No Hypothesis Registry or research state machine.
- No new advisor, model, feature, strategy, weight, threshold, or promotion rule.
- No ranking/backtest redesign.
- No production result promotion from smoke data.

## Before

Round 18 left `dehps.training.runtime` at roughly 8,500 lines. Production built `runtime.iter_supervisor_rounds()`, and `TrainingRoundRunner.run_runtime_round()` only called `next(runtime_rounds)`. Weight, Ridge, and Neural proposals reached a Registry, but their orchestration remained inline; Target Weight Inversion remained outside that protocol.

## After

- `dehps.training.runtime` is reduced to compatibility and established ranking/backtest helpers; the production loop is no longer in that module.
- `ProductionTrainingSession.next_request()` creates one immutable request from persistent run state.
- `ProductionRuntimeRoundExecutor.execute(request, state)` owns exactly one established production round.
- `TrainingSupervisor` calls `TrainingRoundRunner.run(request)` and never advances a runtime iterator.
- `run_runtime_round()` and the production `for_runtime()` constructor are removed.
- `CandidateSourceComposer` owns deterministic reserved-source ordering, deduplication, refill, and legacy capacity semantics.
- Weight, Ridge, Neural, and Target Weight Inversion proposals all pass through one `RuntimeAdvisorOrchestrator -> AdvisorRegistry` path.
- `RuntimeEvaluationNormalizer` owns source/baseline normalization, holdout-isolation audit, and fail-closed promotion decision ordering.
- Round persistence and status/report publication execute after the round decision inside the explicit executor.
- The legacy generator API remains a compatibility facade over the session/executor and is not used by the production CLI.
- GitHub Actions now runs the full Python worker suite for worker changes on pull requests and main pushes.

## Validation

Baseline before Round 19 changes:

```text
.venv/bin/python -m pytest -q
688 passed in 39.25s
```

Intermediate full suite after the explicit production call-path migration:

```text
.venv/bin/python -m pytest -q
692 passed in 47.24s
```

Final local suite after live-smoke regressions, session continuity coverage, documentation, and CI workflow:

```text
.venv/bin/python -m pytest -q
693 passed in 22.86s
```

The first GitHub Actions runs exposed three `training_watch` tests that still depended on local PostgreSQL reads and host disk-capacity state. Their missing mocks were fixed without changing production code. A forced no-database local run now passes the complete suite:

```text
DB_PORT=1 .venv/bin/python -m pytest -q
693 passed in 44.85s
```

Isolated database smoke used `dehps_round19_smoke`, cloned from the prior isolated fixture database and truncated of training result state. It did not use the production database.

```text
DB_NAME=dehps_round19_smoke .venv/bin/python scripts/run_training_supervisor.py \
  --duration-hours 1 --max-rounds 1 --train-window 900 --eval-window 10 \
  --top-n 10000 --as-of-issue 2026079 --workers 4 \
  --train-mode expanding --history-scope current_regime_default \
  --regime-years 10 --output-dir /tmp/dehps-round19-smoke \
  --progress-interval 5 --max-configs-per-round 4 \
  --memory-budget-gb 20 --event-url ''
```

Evidence:

- Failed smoke `20260713-141228` exposed a missing `evaluation_split` handoff after evaluation normalization.
- Failed smoke `20260713-141258` exposed a missing `raw_improved` handoff. Both failures occurred before round persistence and left no round row.
- Both values are now explicit `RuntimeEvaluationOutcome` fields with regression coverage.
- Fresh smoke `20260713-141323` completed exactly one round and exited with status `completed`.
- The successful row stores `rank_objective_v1`, policy hash `c63399d633aa1ae0148df96698df77233458ccbb265db50ed959907bce726387`, five candidate summaries, and a promotion reason.
- The corresponding three run ids have zero rows in the production `training_round_results` table.
- The short smoke window cannot train the dynamic lines; their bounded warnings and refusal to use a static fallback are established behavior, not a production runtime failure.

## Remaining Work

- Obtain the new GitHub Actions check on the ready PR.
- Merge, restart a fresh production Supervisor from merged main, record the run id, and observe at least two complete rounds.
- Keep deeper ranking/backtest helper decomposition separate from research feature work.
- Move the Hypothesis Registry to the next round.
