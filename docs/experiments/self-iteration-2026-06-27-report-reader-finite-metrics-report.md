# Self-Iteration: Report Reader Finite Metrics

Date: 2026-06-27

## Primary Goal

Reject non-finite numeric metric values when agent-readable experiment reports are parsed.

## Non-Goals

- No training, scoring, candidate-generation, advisor, or strategy changes.
- No change to DEHPS evidence level or prediction/betting language.
- No broad report format refactor.

## Change

- `parse_experiment_report` now rejects metric values parsed as `NaN`, `Infinity`, or `-Infinity`.
- Normal finite integer and float metrics keep their existing behavior.
- Config snapshot parsing is unchanged; the finite-number guard applies only to metrics used for report comparison and diagnostics.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_agent_report_reader.py -q
apps/worker-python/.venv/bin/python -m pytest -q
```

Result:

- 7 report-reader tests passed.
- 276 worker tests passed.

## Guardrail

This is a report-ingestion boundary hardening change. It does not alter historical ranking behavior, strategy selection, candidate generation, or any claim about predictive ability.
