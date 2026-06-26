# Stale Probability Primary Gate V1

## Summary

This round responds to a long DEHPS training plateau. The live supervisor continued to produce candidate rounds, but the accepted predictive frontier did not move: recent evidence stayed at `Top100=2`, `Top1000=3`, `Top10000=3`, with `best_top10000=3` and no promotion.

The change is conservative. It does not add a scoring algorithm, candidate family, data source, lottery signal, or historical-window change. It only tightens which probability-calibration candidates are allowed to steer the next search base after stale stagnation.

## Four Agent Review

- Gauss verification: a candidate that improves probability shape or near-miss counts without frozen primary-hit lift must not drive a long-stalled search loop.
- Riemann structure: repeated rank signatures and repeated near-miss neighborhoods indicate local basin collapse, so search-base selection should resist being pulled back by the same local structure.
- Probability-focus control: probability champion remains useful early, but after stale stagnation it needs the same primary-frontier burden already used by source-frontier acceptance.
- Operations acceptance: the old long run should be replaced by a fresh supervisor after the code change, then watched for at least 1-2 completed rounds without runtime errors.

## Change

- Added `PROBABILITY_PRIMARY_GATE_STAGNATION_THRESHOLD`, reusing the existing stale threshold of `64` rounds.
- `select_probability_calibration_champion` now records primary-gate metadata.
- Once the stale threshold is reached, a probability-calibration champion must improve frozen primary score `(top_100_hits, top_1000_hits, top_10000_hits)` versus the accepted baseline.
- Better probability-calibration candidates without primary lift are reported as `probability_primary_gate_no_lift` instead of being allowed to become `probability_focus`.
- `probability_focus` now refreshes only on strictly stronger probability score, even when the candidate hash differs.
- When rank-homogeneity collapse is active, `probability_focus` must obey the same recent-search-base cooldown and minimum config-distance constraints as normal search-base selection.
- Status now keeps `prefilter.completed_latest` so completed-round diagnostics are not hidden by mid-round progress snapshots in `prefilter.latest`.

## Old Run Evidence

Source run:

```text
run_id=20260625-174916
pid=1706400
as_of_issue=2026070
legal_universe_size=1107568
ranked_universe_size=1105506
```

Observed plateau:

- `249` completed rounds at the time of review; the old process was later stopped after round `250` completed and round `251` had reached target `100/100` but had not written a completed-round decision.
- `0` accepted improvements in the scanned live log.
- Repeated `no_improvement best_top10000=3`.
- Latest accepted live metric remained `Top100=2`, `Top1000=3`, `Top10000=3`.
- Source-frontier primary champion remained inactive with `no_non_normal_primary_frontier_lift`.
- Near-miss inversion repeatedly produced broad `10000`-band misses without `100` or `1000` band near misses.
- Rank homogeneity stayed active in the recent window, with only `2/12` or `3/12` unique signatures.

## Non-Goals

- No change to legal sample space.
- No change to training or evaluation windows.
- No new model, advisor, or candidate generator.
- No promotion of near-miss, Red5, median-rank, or objective-only improvements.
- No claim that this improves predictive performance by itself.

## Validation

Unit tests:

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_training_supervisor.py -q
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_training_supervisor.py apps/worker-python/tests/test_training_watch.py -q
```

Results:

```text
92 passed in 0.78s
98 passed in 0.42s
```

Live validation:

```text
code_commit=437f51a
old_run_id=20260625-174916
old_pid=1706400
new_run_id=20260626-110923
new_pid=2160635
new_log=runtime/logs/training-supervisor-stale-probability-primary-gate-20260626-110923.log
new_status=data/output/optimization/training-supervisor-20260626-110923.json
new_report=data/output/optimization/training-supervisor-20260626-110923.md
```

Live result:

- Fresh supervisor started from committed code `437f51a`.
- Static universe remained `1107568`; ranked universe remained `1105506`.
- Round `1` and round `2` completed and were persisted in `training_round_results`.
- Both completed rounds had `improved=false`, `Top100=2`, `Top1000=3`, `Top10000=3`, median rank `579812`, worst rank `1100279`, objective `3642.049251`.
- No runtime `Traceback`, `ERROR`, `Exception`, or `HeavyJobLockTimeout` appeared in the new run log.
- Watchdog attempts at `11:10` and `11:20` failed on the active heavy-job lock held by new PID `2160635`, confirming no duplicate supervisor took over.
- `prefilter.completed_latest` was populated after round `1` and round `2`, while `prefilter.latest` continued to show current in-progress round state.
- The primary stale gate did not yet trigger in live validation because fresh-run stagnation was below thresholds: probability champion threshold `16`, primary gate threshold `64`.

## Acceptance Boundary

This round is accepted only as an anti-false-progress guardrail. It is not accepted as evidence that DEHPS has found a stronger predictive signal. Future promotion still requires frozen primary-hit lift, tail safety, leakage checks, and the same historical-window/null-model discipline.
