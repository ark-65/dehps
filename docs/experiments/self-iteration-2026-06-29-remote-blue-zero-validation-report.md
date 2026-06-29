# Self-Iteration 2026-06-29 - Remote Blue Zero Validation

## Primary Goal

Prevent remote SSQ record normalization from silently dropping explicit falsy field values, especially `blue: 0`, before parser validation can reject invalid draw data.

## Non-Goals

- Do not change training, optimization, candidate generation, scoring, or advisor logic.
- Do not add a new data source or parsing strategy.
- Do not change DEHPS evidence level, prediction framing, or betting-oriented language.
- Do not alter generated runtime artifacts under `data/output` or `runtime`.

## Change

`_normalize_remote_record` now chooses the first non-null, non-blank alias value instead of relying on truthiness. This preserves explicit invalid values such as numeric zero so the existing draw validator can report the real boundary failure.

A regression test verifies that a remote record with `blue: 0` keeps that value and is rejected by the existing blue-ball range check.

## Validation

- `apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_ssq_client.py apps/worker-python/tests/test_ssq_parser.py -q` -> 28 passed
- `apps/worker-python/.venv/bin/python -m pytest -q` -> 300 passed

## Evidence Boundary

This is a data-quality validation hardening change. It does not claim improved prediction ability; it only prevents invalid upstream draw values from being masked before historical data ingestion checks.
