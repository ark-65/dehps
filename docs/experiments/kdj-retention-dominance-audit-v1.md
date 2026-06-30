# KDJ Retention And Dominance Audit V1

## Goal

Add conservative auditability around dynamic KDJ weight advice. The change measures retention risk, KDJ strength sensitivity, and structural-layer concentration without adding a hard filter, changing the reward function, or relaxing frozen promotion gates.

## Non-goals

- No hard KDJ filtering or candidate exclusion.
- No supervisor search-base or acceptance rule change.
- No new DB table and no Redis usage change.
- No claim that historical KDJ retention guarantees future retention.

## Gauss / Riemann / Einstein Pass

- Einstein pass: KDJ strength is now a falsifiable variable under the same universe and target issues. Strength `0.0` is the static baseline; strength `1.0` is the current dynamic offset scale.
- Gauss pass: retention is counted exactly by rank bands. A dynamic candidate that loses a target already inside static Top10000 records `retention_lost_top10000`.
- Riemann pass: KDJ advice is grouped into structural layers such as parity, sum, span, zone, omission, frequency, adjacency, calendar, qian_kun, and other. Layer concentration is diagnostic evidence, not a promotion rule.

## Implementation Notes

- `dynamic_config_for_target(...)` now accepts `offset_scale`, defaulting to `1.0`.
- `evaluate_dynamic_kdj_backtest(...)` now accepts `strength_sweep` and `retention_bands`.
- Dynamic KDJ payloads now include:
  - `strength_sweep`
  - `retention_audit`
  - `kdj_layer_audit`
  - `skill_audit`
- `render_dynamic_kdj_report(...)` renders strength, retention, layer, and skill-audit sections.
- `run_dynamic_kdj_backtest.py` adds `--kdj-strength-sweep` and `--retention-bands`.
- `--no-write` now prints compact acceptance, retention, strength, and layer-audit summaries.

## Validation

- `apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_dynamic_kdj_backtest.py apps/worker-python/tests/test_weight_kdj.py -q`
  - Passed: 17 tests.
- `apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_training_supervisor.py -q`
  - Passed: 105 tests.
- `apps/worker-python/.venv/bin/python -m pytest -q`
  - Passed: 327 tests.
  - Warning: existing multiprocessing fork deprecation warning in `test_prefilter_configs_target_parallel_matches_single_worker`.
- CLI smoke:
  - Command: `apps/worker-python/.venv/bin/python apps/worker-python/scripts/run_dynamic_kdj_backtest.py --eval-window 2 --disable-negative-controls --no-write --kdj-strength-sweep 0,0.25,0.5,1.0 --retention-bands 100,1000,10000,50000`
  - Result: completed without runtime error.
  - Acceptance: `RESEARCH_ONLY`, as expected for a two-draw smoke.
  - Retention: `lost_top10000_count=0`.
  - Strength sweep: best by objective and median rank was strength `1.0` on the two-draw smoke.
  - Layer audit: top layer was `sum` with contribution share `0.269952`; no concentration warning.

## Live Supervisor Validation

- Stopped the older supervisor and started a fresh supervisor with the same training parameters.
- Direct `nohup` launches exited during carryover evaluation without traceback because the app tool shell cleaned the process group. Restarting with `setsid` fixed the runtime launch method.
- Live run:
  - Run id: `20260630-142439`
  - PID: `2133732`
  - Log: `runtime/logs/training-supervisor-kdj-retention-audit-setsid-20260630-142439.log`
  - Status: running.
  - Completed rounds: 2.
  - Entered round: 3.
  - Runtime errors: none observed.
- Database/status checks:
  - `training_round_results`: 2 rows for run `20260630-142439`, max round `2`.
  - `training_supervisor_best`: run `20260630-142439`, round `2`, best Top100/Top1000/Top10000 = `3/3/3`.
  - `training_next_candidates_current`: 10000 rows, source round `2`, run `20260630-142439`.
  - Status JSON `next_candidates.training_freshness.status`: `current`.

## Boundary

This is a historical audit and diagnostic change. It does not assert prediction ability, does not produce betting advice, and does not promote KDJ output unless later frozen or forward validation supports it under the existing baseline discipline.
