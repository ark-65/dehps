# Daily Pipeline Direct-Import Recovery V1

## Primary goal

Restore the scheduled SSQ data-update entry point when `daily_pipeline.py` is
executed directly, matching the checked-in cron and systemd commands.

## Non-goals

- No crawler, parser, sync-window, advisor, training, candidate, or promotion changes.
- No claims about prediction quality or historical lift.

## Evidence

The scheduled command runs `python scripts/daily_pipeline.py`. In that mode,
Python places `scripts/` on `sys.path`; the previous package-qualified sibling
import failed with `ModuleNotFoundError: No module named 'scripts'` before sync
could begin. Module execution still retains the package-qualified import.

The regression test removes the worker root from `sys.path` while preserving an
installed-package equivalent for `dehps`, reproducing the deployment boundary
without relying on the developer virtualenv's editable path.

## Validation

```text
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_daily_pipeline.py -q
```

This is an operational data-closure repair only. The legal red-ball sample space,
historical windows, null baseline, holdout isolation, leakage checks, duplicate
checks, frozen quarantine, and forward-evidence requirements are unchanged.

## Gauss-Riemann cross-review

- **Task Frame:** verify that the checked-in scheduled entry point can reach
  argument parsing and later sync stages; progress means a deployment-shaped
  regression test changes from import failure to success.
- **Historical Boundary:** Gauss and Riemann are used only as historically
  inspired verification lenses, not literal minds or authority.
- **Gauss Pass:** the precondition is exact: direct execution exposes `scripts/`
  rather than its parent. The failing exception and passing regression test
  establish the local import claim. No performance baseline is implicated.
- **Riemann Pass:** module execution and direct execution are distinct import
  domains. The conditional preserves the package domain while making the sibling
  module reachable in the direct-script domain.
- **Cross-Review and disagreement:** both lenses accept entry-point reachability;
  neither treats `--help` as proof that the next live network and database sync
  will succeed.
- **Synthesis:** this is a verified startup repair, not evidence of new data,
  improved frozen validation, predictive lift, or betting advantage.
- **Next verification:** observe the next scheduled run for parser/sync success,
  canonical issue alignment, and duplicate-check status before attributing a
  completed data-update closure.
