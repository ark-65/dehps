# DEHPS Candidate Report

- Candidate key: `next-red-candidates-20260616-100322`
- Latest known issue: 2026067
- Next issue hint: 2026068
- Frozen seed: `2026067`

## Protocol

- Generate legal 双色球 red-ball combinations only.
- Exclude exact historical red-ball combinations already present in local history.
- Keep combinations accepted by `baseline_v1`.
- Rank by DEHPS score descending, anomaly penalty ascending, and deterministic seed hash.
- Do not use future draw outcomes, blue balls, or post-result threshold tuning.

## Candidates

| Rank | Red numbers | Score | Anomaly penalty | Tie hash |
| --- | --- | --- | --- | --- |
| 1 | `02 04 13 21 28 30` | 0.675000 | 0.0000 | 0000045c608d |
| 2 | `08 13 19 21 24 32` | 0.675000 | 0.0000 | 000024c785de |
| 3 | `06 10 12 13 24 31` | 0.675000 | 0.0000 | 000034fa18a4 |
| 4 | `08 10 19 21 22 27` | 0.675000 | 0.0000 | 00004a946afe |
| 5 | `09 14 15 18 27 31` | 0.675000 | 0.0000 | 000061f243de |

## Null Model

- random_sets: 200
- candidate_count: 5
- mean_score: 0.63771
- max_score: 0.675
- min_score: 0.2251

## Leakage Checks

- future_outcome: pass - seed is derived from the latest known issue, not a future result
- history_overlap: pass - 0 candidate exact red sets already appeared in history
- duplicate_candidates: pass - candidate red sets are unique
- blue_ball_exclusion: pass - candidate generation uses red-ball structure only
- frozen_thresholds: pass - baseline_v1 StrategyConfig is fixed at generation time

## Risk Note

Every legal red-ball combination has the same mathematical probability before the draw. These candidates are transparent structural hypotheses for later verification, not guaranteed predictions or betting advice.
