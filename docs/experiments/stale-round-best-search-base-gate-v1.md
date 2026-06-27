# Stale Round-Best And Eval-Slice Overfit Gate V1

## Summary

This round addresses two false-progress paths found during the long-running supervisor plateau. The stale probability primary gate stopped weak probability candidates from becoming `probability_focus`, but an unpromoted `round_best` could still become the next `search_base` during stale rank-homogeneity collapse. A second failure mode appeared when candidates reached `Top100=3` on the current eval slice while frozen primary validation stayed `[0, 0, 0]`.

The change is intentionally narrow. It does not add a model, advisor, score function, data source, training window, evaluation window, or strategy family. It only prevents an unaccepted `round_best` from steering the next search base after the same frozen-primary gate has already rejected it under stale collapsed conditions.

## Four Agent Review

- Gauss verification: the same candidate must not bypass a frozen-validation rejection by reappearing under a different selection path. `Top100=3` is a discovery signal, not proof, when the repeated adaptive search has already selected many candidates and frozen primary remains zero.
- Riemann structure: rank-signature collapse means the search is stuck on a low-dimensional sheet of the candidate space. `Top100=3` with frozen `[0, 0, 0]` is a local chart that does not continue across the frozen boundary.
- Dialogue synthesis: after stagnation, rank homogeneity, failed promotion, and failed frozen primary lift coincide, `round_best` is allowed to remain evidence but not a navigation base. If the current eval slice looks strong while the frozen slice stays empty, probability focus must also carry frozen primary burden.
- Main-agent acceptance: keep this as a guardrail only. Do not treat it as evidence of predictive lift until live historical rounds beat the same frozen baseline.

## Old Run Evidence

Source run:

```text
run_id=20260626-110923
pid=2160635
as_of_issue=2026070
legal_universe_size=1107568
ranked_universe_size=1105506
```

Observed plateau:

- At least `280` completed rounds were observed before this change.
- `improved_count=0` remained true in the long run.
- Recent completed status reported `stagnation_rounds=280`.
- Rank homogeneity was active with `unique_signature_count=1/12`.
- The promotion gate rejected the candidate with `reason=frozen_validation_not_better`.
- Frozen primary score was tied at `[0, 0, 0]` for candidate and incumbent.
- Probability calibration stayed blocked by `probability_primary_gate_no_lift`.
- The visible score was still attractive on the current eval slice: `Top100=3`, `Top1000=3`, `Top10000=3`.
- Round `278` selected `search_base_next=round_best` even though the round was `no_improvement`.
- Later rounds sometimes selected `search_challenger`, but the rejected `round_best` path remained legal in code and could recur.

## Change

- Added `stale_round_best_search_base_gate`.
- The gate activates only when all of these are true:
  - rank-homogeneity guardrail is active;
  - stagnation has reached `PROBABILITY_PRIMARY_GATE_STAGNATION_THRESHOLD`;
  - frozen promotion did not pass;
  - frozen primary-hit improvement did not pass.
- `select_next_search_base` now accepts `allow_unpromoted_round_best`.
- When the gate is closed, the blocked `round_best` is also excluded from `search_challenger`, so it cannot bypass the gate by being relabeled.
- Search-base metadata now records `round_best_search_allowed`, `round_best_search_blocked`, `round_best_skip_reason`, `round_best_config_hash`, and `round_best_config_distance`.
- Completed round diagnostics now record `stale_round_best_search_base_gate` under `prefilter`.
- Added `eval_slice_overfit_guardrail`.
- The eval-slice guardrail activates when all of these are true:
  - rank-homogeneity guardrail is active;
  - stagnation has reached `STAGNATION_THRESHOLD`;
  - promotion did not pass;
  - frozen primary-hit improvement did not pass;
  - `round_best` has at least `3` Top100 hits on the full eval slice;
  - `round_best` frozen primary score is `[0, 0, 0]`.
- The guardrail records suspicious candidate rows with full-eval rank, config hash, source, rank-signature hash, Top100 hit issues, and Top100 hit ranks.
- When the eval-slice guardrail is active, it forces the probability-calibration primary gate before the older stale threshold of `64` rounds.
- When the eval-slice guardrail is active, it also closes the unpromoted `round_best` search-base path and reports `round_best_skip_reason=eval_slice_overfit_no_frozen_primary_lift`.

## Non-Goals

- No change to legal sample space.
- No change to historical scope, training window, evaluation window, or target issue.
- No new candidate generator, model, or scoring term.
- No promotion of objective-only, Red5-only, median-rank-only, near-miss-only, or probability-shape-only improvements.
- No claim that this by itself improves prediction quality.

## Validation

Unit tests:

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_training_supervisor.py apps/worker-python/tests/test_training_watch.py -q
```

Result:

```text
104 passed in 2.00s
```

Live supervisor validation:

```text
run_id=20260627-113053
pid=101414
log=runtime/logs/training-supervisor-eval-slice-overfit-gate-20260627-113052.log
as_of_issue=2026070
```

Observed results:

- The supervisor restarted from the updated code and wrote status JSON normally.
- Round `1` completed without runtime errors and recorded eval-slice telemetry while inactive because `stagnation_rounds=0`.
- Round `2` completed without runtime errors and selected `search_challenger` after `no_improvement best_top10000=3`.
- By completed round `38`, the eval-slice guardrail was active with `reason=eval_slice_overfit_no_frozen_primary_lift`.
- Round `38` still had full-eval primary score `[3, 3, 3]`, frozen primary score `[0, 0, 0]`, promotion reason `frozen_validation_not_better`, and `primary_hit_passed=false`.
- The suspicious Top100 issues were repeatedly concentrated on `2026025`, `2026043`, and `2026048`; round `38` counted each of them in `5` suspicious candidates.
- The stale search-base gate reported the same reason, so the unpromoted `round_best` path was closed and the next base stayed on `search_challenger`.
- Log scan found no `Traceback`, `ERROR`, `Exception`, or `HeavyJobLockTimeout` during the monitored run.

## Acceptance Boundary

Accept this round only as an anti-false-progress search-base guardrail. A future candidate still needs frozen primary-hit lift, tail safety, leakage checks, and null/baseline comparison before it can be treated as predictive progress.
