# Conservative Navigation And Freshness Fix V1

- Date: 2026-06-30
- Run id: `20260630-091612`
- Primary goal: unblock stalled supervisor navigation conservatively and correct next-candidate freshness for regime-scoped training rows.
- Non-goals: no new algorithm, no reward-function change, no frozen-primary relaxation, no prediction or betting claim.

## Change Summary

- Added a small experimental-navigation selector for supervisor search-base routing.
- Priority remains conservative: active `exploration_champion` first; otherwise active `rank_homogeneity_restart_champion` only when `rank_vector_changed=true`.
- Both `select_next_search_base(...)` calls now receive the same unified experimental-navigation candidate.
- Search-base metadata now records `exploration_navigation_source` and `exploration_navigation_reason`.
- `training_round_results` now stores backward-compatible history context: `history_scope`, `regime_years`, and `regime_start_date`.
- Training round persistence writes those fields from supervisor status.
- Next-candidate generation reloads current history through the training row's scope before computing freshness. Unknown legacy rows keep legacy full-history behavior.

## Gauss Pass

- Legal sample space was not changed; validation run used ranked universe size `1105506`.
- Frozen-primary promotion and navigation gates were not loosened. The new restart fallback only feeds the existing `experimental_navigation` path and still passes through distance, rank-vector, cooldown, and frozen-primary checks.
- The freshness comparison now uses the same history fingerprint scope as training when the row records `current_regime_default` or `full_history_audit`.
- Legacy rows with unknown scope remain stale/legacy rather than being silently reinterpreted.

## Riemann Pass

- The supervisor stall looked like a navigation-geometry issue, not evidence for a new scoring model.
- The existing restart champion was structurally disconnected from search-base motion; the fix connects it through the already bounded experimental-navigation channel.
- The stale next-candidate flag was a scope mismatch: training lived on the current-regime slice while candidate generation compared against full-history geometry.
- The smallest shared conclusion is scope alignment plus bounded routing, then live historical rounds judge behavior.

## Validation

- Targeted tests:
  `apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_training_supervisor.py apps/worker-python/tests/test_next_candidates.py -q`
  Result: `113 passed in 1.95s`.
- Full worker suite:
  `apps/worker-python/.venv/bin/python -m pytest -q`
  Result: `315 passed in 27.92s`.
- Fresh supervisor:
  old run `20260629-184002` was stopped; fresh run `20260630-091612` started with the same training parameters and updated code.
- Live rounds:
  round 1 completed with `search_base_next=search_challenger`, `changed=True`, no runtime error.
  round 2 completed with `search_base_next=round_best`, `changed=True`, no runtime error.
- Live freshness:
  `next_candidates.training_freshness.status=current`,
  `training_issue_matches_current=true`,
  `training_history_matches_current=true`,
  `training_issue_lag=0`,
  `freshness_mode=training_scope`,
  `history_scope=current_regime_default`,
  `regime_years=10`,
  `regime_start_date=2016-06-28`.

## Notes

- Early live rounds had `frozen_primary_lift_required=false`, so experimental navigation did not need to activate. The regression test covers the frozen-gate path where a changed rank-homogeneity restart champion becomes the experimental-navigation fallback without bypassing the gate.
- This report records diagnostic and operational evidence only. It does not promote a predictive claim.
