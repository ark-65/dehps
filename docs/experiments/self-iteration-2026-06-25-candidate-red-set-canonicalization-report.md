# Self-Iteration Report: Candidate Red-Set Canonicalization

- Date: 2026-06-25
- Primary goal: harden candidate generation and leakage audit against red-ball order differences.
- Non-goals: no scoring change, no strategy change, no predictive claim, no training heuristic promotion.

## Change

Candidate generation now canonicalizes historical and universe red-ball tuples with `normalize_red_numbers` before exclusion, scoring, tie-breaking, and duplicate suppression. The leakage audit applies the same canonicalization before checking historical overlap and duplicate candidates.

This keeps the legal red-ball set explicit: `(1, 2, 3, 4, 5, 6)` and `(6, 5, 4, 3, 2, 1)` are treated as the same historical/candidate red set.

## Validation

```bash
apps/worker-python/.venv/bin/python -m pytest apps/worker-python/tests/test_candidate_generation.py -q
apps/worker-python/.venv/bin/python -m pytest -q
```

Results:

- Candidate generation tests: 8 passed.
- Worker Python tests: 256 passed.

## Scientific Boundary

This is a leakage and data-canonicalization guardrail only. It does not change DEHPS into a lottery prediction system and does not alter the requirement that historical hypotheses be judged against explicit baselines and future frozen draws.
