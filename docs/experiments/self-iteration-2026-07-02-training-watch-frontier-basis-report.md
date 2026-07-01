# Self-Iteration Report: Training Watch Frontier Basis

- Branch: `fix/self-iterate-20260702-0601-training-watch-frontier-split`
- Primary goal: make restart-champion source-frontier diagnostics distinguish primary frozen lift from secondary frontier movement in supervisor metadata and training-watch Markdown.
- Non-goals: change no strategy, advisor, candidate source, promotion gate, frozen-validation gate, weight bound, or betting recommendation.

## Initial Observation

`apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5` reported run `20260701-165125` with `severity=alert`, `action=prepare_restart_with_more_exploration`, `stagnation_rounds=195`, active eval-slice overfit guardrail, rank homogeneity, and active supervisor lock PID `3626371`.

The live watch evidence boundary remained explicit:

- Legal sample space: SSQ red-ball combinations, legal universe `1,107,568`, ranked universe `1,105,506`, excluded `2,062`.
- Historical window: current regime default, expanding train mode, train window `900`, eval window `100`, top-N `10000`, latest issue `2026074`.
- Baseline/null model: incumbent frozen-primary baseline and ranked-uniform null model were reported by watch.
- Leakage checks: parser/sync/duplicates/universe checks reported `ok=True`; promotion remained blocked by `frozen_validation_not_better`.
- Evidence level: operational training diagnostic only; no guaranteed-hit, settled-edge, or low-risk betting claim.

## Gauss/Riemann Diagnostic

- Task Frame: the object is training-watch/supervisor evidence labeling during a high-stagnation alert. Progress means making the measured residual auditable without changing the training search.
- Historical Boundary: Gauss and Riemann are used here as historically inspired verification and structure lenses, not as literal minds or authority.
- Gauss Pass: the measured residual is eval primary `[3, 3, 3]` versus frozen primary `[0, 0, 0]`. A restart champion may still report `source_frontier_score_improved=True` through secondary tuple movement, so the proof obligation is to expose primary and secondary components separately.
- Riemann Pass: the old single boolean collapsed two spaces: primary frozen hit lift and secondary frontier quality. The report needed a coordinate split so operators can tell whether a frontier movement is primary, secondary, or absent.
- Cross-Review: do not weaken gates or promote the result from this evidence; do not leave the operator to infer source-frontier basis from raw JSON.
- Synthesis: the smallest safe fix is observability-only metadata and Markdown output: keep the legacy boolean, add primary/secondary improvement flags and an improvement basis label.
- Next Verification: continue live supervisor monitoring; any future strategy change still requires the same legal sample space, frozen validation, null/baseline controls, leakage checks, uncertainty, and failure-case reporting.

## Change

- `run_training_supervisor.py` now records restart-champion `baseline_frozen_primary_score`, `source_frontier_secondary_score`, `baseline_source_frontier_secondary_score`, `source_frontier_primary_score_improved`, `source_frontier_secondary_score_improved`, and `source_frontier_improvement_basis`.
- `watch_training_progress.py` carries those fields into `gate_summary` and renders `frontier_basis`, `primary_improved`, and `secondary_improved` in the Gate Snapshot.
- Tests cover a secondary-only frontier improvement where frozen primary remains `[0, 0, 0]`.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py apps/worker-python/tests/test_training_supervisor.py
```

Result: `137 passed in 6.50s`.

Fresh supervisor validation:

- Stopped stale pre-change supervisor PID `3626371`.
- Started fresh supervisor with standard script:

```bash
scripts/ensure_training_supervisor.sh
```

- Fresh run id: `20260702-060504`
- Fresh PID: `4033458`
- Log: `runtime/logs/training-supervisor-kdj-ridge-neural-target-inversion-20260702-060504.log`
- Round 1 completed: `round=1 no_improvement best_top10000=3`
- Round 2 completed: `round=2 no_improvement best_top10000=3`
- Round 3 started, confirming the supervisor continued after two completed rounds.
- Log scan during monitoring found no `Traceback`, `ERROR`, `Exception`, `HeavyJobLockTimeout`, `failed`, or `killed` marker.

Updated watch validation:

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --run-id 20260702-060504 --limit 5
```

Result: `severity=ok`, `action=continue_current_run`, `restart_readiness.status=not_requested`.

## Result

The monitor no longer leaves `source_frontier_score_improved=True` ambiguous when frozen-primary lift is absent. This is an observability fix only. It preserves existing baseline/null, frozen-validation, leakage, uncertainty, and failure-mode guardrails and makes no predictive or betting claim.
