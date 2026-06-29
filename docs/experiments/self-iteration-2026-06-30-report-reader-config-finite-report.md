# Self-Iteration: Report Reader Finite Config Snapshot

Date: 2026-06-30

## Primary Goal

Reject non-finite numeric values in parsed experiment report config snapshots.

## Non-Goals

- No training, scoring, candidate-generation, advisor, or strategy changes.
- No change to DEHPS evidence level or prediction/betting language.
- No broad report format refactor.

## Change

- `parse_experiment_report` now rejects config snapshot values parsed as `NaN`, `Infinity`, `-Infinity`, or overflowed JSON numbers such as `1e309`.
- Nested config snapshot lists and objects are checked recursively.
- String values remain allowed when they are valid strings rather than non-finite numeric literals.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_agent_report_reader.py -q
apps/worker-python/.venv/bin/python -m pytest -q
```

Result:

- 13 report-reader tests passed.
- 307 worker tests passed.

## Guardrail

This is an evidence-ingestion boundary hardening change. It does not alter historical ranking behavior, strategy selection, candidate generation, or any claim about predictive ability.
