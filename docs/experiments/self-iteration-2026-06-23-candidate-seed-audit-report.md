# Self-Iteration: Candidate Seed Audit Boundary

Date: 2026-06-23

## Primary Goal

Tighten the next-candidate leakage audit so the `future_outcome` check only passes when the frozen seed exactly matches the latest known issue.

## Non-Goals

- No new scoring algorithm, model, strategy, or threshold.
- No change to candidate ranking or red-ball generation.
- No betting-oriented language or prediction claim.

## Core Question

Can the candidate report truthfully claim the seed is derived from the latest known issue if a manual seed is older than the latest issue?

## Invariant

The legal red-ball sample space, history exclusion, baseline filter, and deterministic tie-breaking stay unchanged. The audit only labels whether the report protocol is sufficiently observable.

## Hypothesis

A stale or future numeric seed should produce a `warn` status because it is not exactly the latest known issue and therefore cannot support the existing report wording.

## Measurement

The candidate leakage audit should:

- pass `future_outcome` when `seed == latest_issue`;
- warn when the latest issue is malformed or missing;
- warn when the seed is older or newer than the latest issue.

## Failure Mode

This would be too strict if manual historical replays were intended to be described as current next-candidate reports. In that case the report should use different protocol language instead of passing the current audit.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_candidate_generation.py
apps/worker-python/.venv/bin/python -m pytest -q
```

Result:

- `6 passed in 0.02s`
- `200 passed in 19.48s`
