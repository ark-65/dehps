# Self-Iteration Report: Stagnation Restart Base Dedupe

- Date: 2026-07-01
- Primary goal: prevent stagnation restart candidates from replaying the current search base when that base already matches one of the restart extremes.
- Non-goals: no new model, advisor, candidate source, scoring rule, promotion rule, weight boundary, history-window change, or betting recommendation.
- Initial status: working tree was clean before edits.

## Training Status

- Initial watch command: `apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5`
- Initial watched run: `20260701-020654`
- Initial watch result: `severity=warn`, `action=watch_stagnation_recovery`, 28 stagnation rounds at first check.
- Live issue after watchdog sync: `2026074`; sync fetched 1 row from `zhcw` and skipped it because it was already present.
- Fresh supervisor after the change: run id `20260701-040511`, PID `2916275`, as-of issue `2026074`.
- Fresh watch result after two completed rounds: `round_count=2`, `severity=ok`, `action=continue_current_run`.

Legal and evaluation context:

- Legal red-ball sample space: `C(33, 6) = 1,107,568`.
- Latest supervisor ranked universe: 1,105,506 after 2,062 exclusions.
- History scope: `current_regime_default`.
- Train window: 900 draws; eval window: 100 draws.
- Frozen validation window in the fresh report: 20 issues, `2026055` through `2026074`.
- Baseline/null context: supervisor reports retain null calibration and baseline overlap fields; this round makes no predictive or betting claim.

## Gauss/Riemann Diagnostic

- Task Frame: the active run showed stagnation, frozen-primary blocking, rank-homogeneity pressure, and a metadata contradiction where an experimental navigation candidate had reason `rank_homogeneity_restart_changed_rank_vector` but distance 0 from the current search base. Progress means removing an invalid replay from the restart candidate set without weakening the frozen-validation gate.
- Historical Boundary: Gauss and Riemann are used as historically inspired verification and structure lenses, not literal minds, authorities, or complete reconstructions.
- Gauss Pass: the object is the restart candidate set under the legal SSQ red-ball sample space and current 900/100 train/eval windows. The invariant is candidate identity after the same clamp/dedupe transform used by `add_unique`. A candidate equal to the current base has zero search distance and cannot provide restart evidence. The null/baseline posture remains unchanged; no lift claim is made.
- Riemann Pass: the search-space obstruction was local geometry, not performance: the restart source could contain the point already occupied by the current search base. That point cannot move the trajectory out of a rank-signature cycle and creates misleading navigation metadata.
- Cross-Review: Gauss rejects promoting eval-slice hits or changing gates from this evidence. Riemann rejects treating a zero-distance point as exploration in the search space.
- Synthesis: the smallest safe fix is to seed the restart candidate dedupe set with the current base using the same normalized key as all generated candidates.
- Next Verification: if future stagnation persists, inspect whether restart candidates now have nonzero distance and changed rank vectors under the same legal sample space, frozen validation window, null/baseline controls, leakage checks, and failure-case reporting.

## Change

- `apps/worker-python/scripts/run_training_supervisor.py`
  - `stagnation_restart_candidate_configs()` now seeds its local dedupe set with the clamp-normalized current base key.
  - This prevents the current search base from consuming a stagnation restart slot when it already equals a primary restart extreme.
- `apps/worker-python/tests/test_training_supervisor.py`
  - Added a regression test for the observed extreme-base replay case.

This is a candidate hygiene and observability fix. It does not add a strategy or relax promotion/search gates.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_supervisor.py -k 'stagnation_restart_candidate_configs or restart_champion or next_search_base'
```

Result: `15 passed, 94 deselected`.

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_supervisor.py
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py
```

Results: `109 passed`; `14 passed`.

```bash
apps/worker-python/.venv/bin/python -m pytest -q
```

Result: `339 passed`.

Fresh supervisor smoke:

```bash
scripts/ensure_training_supervisor.sh
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --run-id 20260701-040511 --limit 5
```

Observed:

- Round 1 completed target evaluation `100/100`, selected `search_challenger`, and ended with `no_improvement best_top10000=3`.
- Round 2 completed target evaluation `100/100`, selected `search_challenger`, and ended with `no_improvement best_top10000=3`.
- Round 3 started, confirming the fresh supervisor continued after two completed rounds.
- No `Traceback`, `Error`, `failed`, `exception`, or `killed` lines were found in the fresh supervisor log during validation.

## Result

The stale live process was stopped, and a fresh supervisor is running with the updated code. The current search base can no longer be emitted as a stagnation restart candidate through this path. This reduces wasted restart budget and removes a misleading zero-distance navigation candidate while preserving the existing frozen-validation, null/baseline, and leakage guardrails.
