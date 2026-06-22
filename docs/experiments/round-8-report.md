# Round 8 Report

## Done

- Opened the optimization foundation stage without claiming predictive ability.
- Added a deterministic next-issue red-ball candidate generator.
- Added a same-protocol random null model summary.
- Added leakage checks for:
  - future outcome use
  - exact historical red-set overlap
  - duplicate candidate sets
  - blue-ball exclusion
  - frozen baseline thresholds
- Added Markdown and CSV candidate artifacts.
- Added tests for seeded candidate generation, history exclusion, null-model reproducibility, and leakage detection.

## Einstein Pass

Core question: can DEHPS output next-issue red-ball candidates while remaining a falsifiable, audited experiment rather than a prediction claim?

Invariant: before a draw, every legal six-red combination has the same mathematical probability.

Hypothesis: transparent structural scoring can produce a stable candidate set whose historical and future behavior can be audited against random null candidates of the same count.

Measurement: candidate count, score distribution, null-model score summary, exact historical overlap, duplicate detection, and later red-hit overlap after the next issue is known.

Failure mode: treating a structural candidate as predictive, tuning after seeing the next draw, or hiding a future-result dependency in the seed/config.

Next experiment: after issue `2026068` is known, freeze the generated artifact and compare these candidates against the actual red balls without changing the protocol.

## Tests

Worker:

```text
29 passed in 7.38s
```

## Commands Run

```bash
/home/ark/workspace/dehps/apps/worker-python/.venv/bin/python -m pytest
/home/ark/workspace/dehps/apps/worker-python/.venv/bin/python scripts/generate_next_candidates.py --limit 5 --random-sets 200
```

## Candidate Artifact

Generated key:

```text
next-red-candidates-20260616-100322
```

Latest known issue:

```text
2026067
```

Next issue hint:

```text
2026068
```

Candidate report:

```text
retired local artifact: data/output/candidates/next-red-candidates-20260616-100322.md
```

Candidate CSV:

```text
retired local artifact: data/output/candidates/next-red-candidates-20260616-100322.csv
```

Candidates:

```text
1. 02 04 13 21 28 30
2. 08 13 19 21 24 32
3. 06 10 12 13 24 31
4. 08 10 19 21 22 27
5. 09 14 15 18 27 31
```

Null model summary:

```text
random_sets: 200
candidate_count: 5
mean_score: 0.63771
max_score: 0.675
min_score: 0.2251
```

Leakage checks:

```text
future_outcome: pass
history_overlap: pass
duplicate_candidates: pass
blue_ball_exclusion: pass
frozen_thresholds: pass
```

## Acceptance Evidence

Candidate generation:

```text
apps/worker-python/dehps/candidates/generator.py
apps/worker-python/dehps/candidates/null_model.py
apps/worker-python/dehps/candidates/leakage.py
apps/worker-python/scripts/generate_next_candidates.py
```

Tests:

```text
apps/worker-python/tests/test_candidate_generation.py
```

## Problems

- The candidate generator still uses `baseline_v1`; it is an audited candidate-selection protocol, not an optimized predictive model.
- The tie-breaker seed is deterministic and based on the latest known issue, but different seed policies can produce different top candidates among equal-scoring combinations.
- Red-hit evaluation for issue `2026068` cannot be completed until that issue is actually known and synced.

## Next Round

Round 9 should add post-draw verification:

- Load a frozen candidate artifact.
- Sync the newly known issue.
- Compare candidate red sets against the actual red balls.
- Report exact-hit and partial-red-hit counts.
- Compare against random null candidates generated before the draw.

## Risk Note

These candidates do not represent guaranteed predictions or betting advice. They are frozen, inspectable hypotheses for later verification.
