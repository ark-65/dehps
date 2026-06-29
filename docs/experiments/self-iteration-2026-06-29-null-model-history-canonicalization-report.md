# Self-Iteration 2026-06-29 - Null Model History Canonicalization

## Primary Goal

Prevent random null-model candidates from reusing historical red-ball combinations when the history input is semantically valid but not already sorted.

## Non-Goals

- Do not add a new scoring algorithm, advisor, strategy, or candidate source.
- Do not change DEHPS evidence level, prediction framing, or betting-oriented language.
- Do not alter generated runtime artifacts under `data/output` or `runtime`.

## Change

`generate_null_candidates` now normalizes historical red-ball tuples with the same canonicalizer used by candidate generation before checking random samples for history overlap.

A regression test uses a fixed random sequence where the first draw is a reversed historical combination. The null model must skip it and accept the next non-historical combination.

## Validation

- `apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_candidate_generation.py -q` -> 9 passed
- `apps/worker-python/.venv/bin/python -m pytest -q` -> 299 passed

## Evidence Boundary

This is a leakage-boundary hardening change for baseline generation. It does not claim improved prediction ability; it only makes the random baseline respect historical-combination exclusion under unsorted but equivalent inputs.
