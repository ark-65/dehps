# Self-Iteration: SSQ Red Number Container Guardrail

Date: 2026-06-25

## Primary Goal

Make malformed `red_numbers` payloads fail with explicit parser `ValueError` messages before SSQ sync or CSV/remote import surfaces a low-level `TypeError`.

## Non-Goals

- No scoring, optimization, training, advisor, candidate-generation, or strategy changes.
- No database schema or runtime state changes.
- No lottery-prediction or betting-language changes.

## Change

- `validate_ssq_draw` now rejects `red_numbers=None`, scalar containers, mappings, and bytes-like values with diagnostic `ValueError` messages.
- Added parser tests for missing and malformed `red_numbers` containers.

## Validation

- `apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_ssq_parser.py -q` -> 16 passed
- `apps/worker-python/.venv/bin/python -m pytest -q` -> 242 passed

## Scientific Guardrail

This is an input-validation and sync diagnostics fix. It does not alter historical ranking behavior, strategy selection, candidate scoring, or any claim about predictive ability.
