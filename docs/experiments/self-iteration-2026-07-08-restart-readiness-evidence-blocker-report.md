# Self-Iteration Report: Restart Readiness Evidence Blocker

## Primary goal

Align training-watch restart readiness with the existing restart guard evidence
gate so a target-complete continuous supervisor is not reported as ready to stop
when the restart candidate lacks primary or secondary frontier improvement.

## Non-goals

- Do not change scoring, training, candidate generation, advisors, promotion
  gates, dynamic weights, or search strategy logic.
- Do not weaken frozen validation, leakage checks, baseline/null-model
  reporting, or evidence-level language.
- Do not make prediction, betting, or model-performance claims.
- Do not commit generated `data/output` or runtime artifacts.

## Initial state

The required watch command completed successfully:

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
```

Observed state before the fix:

- run id: `20260708-180612`
- severity: `alert`
- action: `prepare_restart_with_more_exploration`
- supervisor boundary: continuous supervisor at target `100 / 100`
- active supervisor PID: `4112789`
- rank homogeneity: `stale_rank_signature_cycle`, `1` unique signature in a
  `12` round window, stagnation above threshold
- restart candidate: rank vector changed with `100` changed targets, but
  frozen primary `[0, 0, 0]`, primary improvement `False`, secondary
  improvement `False`, improvement basis `none`
- experimental navigation: eligible, quality `passed`, config distance above
  minimum

The existing restart guard correctly rejected the live summary:

```text
watch_restart_not_ready:restart_frontier_improved,restart_improvement_basis
```

The watch readiness surface still reported the operator action as
`operator_review_then_stop_continuous_training_supervisor_before_restart`, which
could mislead the lifecycle workflow even though the guard would refuse the
restart.

## Evidence context

- Evidence level: `operational_training_diagnostic_no_predictive_claim`.
- Legal sample space: `ssq_red_ball_combinations`.
- Legal universe: `1107568`; ranked universe: `1105506`; excluded
  combinations: `2062`.
- Historical window: `current_regime_default`, expanding train mode,
  train window `900`, eval window `100`, regime start `2016-07-07`, top-N
  `10000`.
- Baseline/null model: incumbent frozen-primary baseline plus ranked-uniform
  per-draw random null.
- Leakage/data checks reported by watch: frozen-primary gate active,
  eval-slice overfit guardrail active, parser/sync duplicate checks passed.
- Uncertainty: frozen validation can remain at baseline even when eval-slice
  metrics look strong.

## Diagnostic constraint

Historical Gauss/Riemann lenses were used as verification and structure
constraints, not as authority or literal reconstructions.

- Task Frame: the object is an operational restart-readiness state under
  rank-homogeneity stagnation. Progress means clearer lifecycle control, not a
  new predictive strategy.
- Historical Boundary: Gauss and Riemann are historically inspired reasoning
  lenses only.
- Gauss Pass: the measurable facts are lock PID, supervisor status PID,
  target-boundary freshness, restart-candidate rank movement, frontier
  improvement fields, navigation eligibility, legal sample space, historical
  window, baseline/null model, and leakage checks. The restart must not be
  reported as stop-ready when the same evidence would make the guard reject it.
- Riemann Pass: the lifecycle state space has a distinct state for "target
  boundary reached, but restart evidence is incomplete." Collapsing that state
  into the stop-ready edge hides the real transition blocker.
- Cross-Review: Gauss rejects stop permission without frontier-improvement
  evidence; Riemann rejects an operator-action label that merges evidence
  insufficiency with the active-lock transition.
- Synthesis: keep the conservative guard unchanged and surface
  `restart_candidate_evidence` as an explicit readiness blocker.
- Next Verification: targeted unit tests, live watch output, and live guard
  refusal against the current run.

## Change

- Added restart-candidate evidence checks to `restart_readiness_summary` using
  the same candidate/navigation evidence dimensions as the restart guard:
  restart candidate active, rank vector changed, changed target count,
  full-eval rank, primary or secondary frontier improvement, improvement basis,
  navigation eligibility, quality, rank-vector change, and config-distance
  threshold.
- When those checks fail, watch now adds blocker
  `restart_candidate_evidence`, exposes `restart_candidate_evidence_ready` and
  `restart_candidate_evidence_blockers`, and reports status
  `blocked_by_restart_candidate_evidence`.
- For a target-complete continuous supervisor with incomplete restart evidence,
  the operator action is now
  `continue_current_training_supervisor_until_restart_candidate_evidence_improves`.
- Markdown and compact operator summaries now include the evidence gate fields.
- Added regression coverage for the live failure shape and compact-summary
  evidence fields.

## Validation

Commands:

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py apps/worker-python/tests/test_training_watch_restart_guard.py
apps/worker-python/.venv/bin/python -m py_compile apps/worker-python/scripts/watch_training_progress.py apps/worker-python/scripts/training_watch_restart_guard.py
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5 | apps/worker-python/.venv/bin/python apps/worker-python/scripts/training_watch_restart_guard.py --expected-pid 4112789
```

Results:

- Targeted pytest: `54 passed`.
- Python compile check: passed.
- Live watch after the change still reports run `20260708-180612`,
  `severity=alert`, `action=prepare_restart_with_more_exploration`.
- Live watch now reports restart readiness status
  `blocked_by_restart_candidate_evidence`, blockers
  `active_training_supervisor_lock` and `restart_candidate_evidence`, and
  evidence blockers `restart_frontier_improved` and
  `restart_improvement_basis`.
- Live guard still refuses restart as expected. A wrapper assertion confirmed
  the nonzero guard result and exact reason:

```text
watch_restart_not_ready:status,operator_action,restart_frontier_improved,restart_improvement_basis
```

## Guardrail

This is an operational watch/readiness fix only. It does not alter model
scoring, candidate generation, advisors, promotion gates, dynamic weights, or
betting language. The observed historical response-surface behavior remains
hypothesis evidence only and does not support guaranteed hits, settled
predictive advantage, or low-risk betting advice.
