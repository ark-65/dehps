# M4 v2 marginal-static repaired-health decision — Round 47

## Round boundary

- Primary goal: integrate the replay-verified Round-46 repaired-health result as one immutable, zero-work decision capability.
- Role: Engineering Agent under approved Request 347 / Research Request 346.
- Non-goals: no estimator, calibration, threshold, fixture, seed, sample, historical outcome, Evidence, model acceptance, Prediction-v2 promotion, P3, or production change.
- Duplicate validation: forbidden in execution and replay.

## Frozen observed result

The Round-46 independent run completed 4,608 replicate paths and 10,234,368 generated sequence issues. Its aggregate replay was verified from one compact index read with zero raw or sentinel regeneration. The repaired-health result is complete, legal, finite, and satisfies the conditional identity oracle, but its preregistered outcome is `REPAIR` because three negative controls fail `negative_control_wilson_upper`:

| Cell | Detection rate | Wilson 95% interval |
|---|---:|---:|
| `BASE:V2_J1_HISTORY_IS4_LAMBDA_HALF:HISTORICAL_2581` | 0.0703125 | [0.0449355, 0.1083943] |
| `BASE:V2_T1_OVERLAP_ODDS_2_MARKOV:FORWARD_61` | 0.0781250 | [0.0511406, 0.1175832] |
| `BASE:V2_T1_OVERLAP_ODDS_2_MARKOV:HISTORICAL_2581` | 0.1484375 | [0.1100947, 0.1971752] |

No instrument-limit cell was produced. Sensitivity-limit cells are preserved as instrument characterization and are not reclassified as control failures.

## Decision capability

The new capability `m4_v2_marginal_static_measurement_repair_health_decision` consumes only these exact registered parents:

- execution `2d2e4b542d51980b131e303b931d56ccbc7e96c1e75c4c6115957bdf20827116`
- health result `f7bc1d3a2d64945eb8a93d1f9afec499f11e4f7c90a1b91a8e1825e26d1dce3f`
- completion `f9a79b6d2ea60237c575f39d4524636a5d9b6f31d1e461c7bf56e3ce7066b462`
- source contract `2186e18ae26fb3770476d968df4f1e63dca1035cbf5858860580d8d766a50dd4`

The exact projected artifact digest is `0ffafc6b5d89e4e17e71c981b985bd228d4ed20686fd85bd79e84461c642fcb5`. It emits:

- authoritative decision: `REPAIR_MEASUREMENT_SYSTEM`
- fact: `m4-v2-marginal-static-measurement-repair-health-decision:REPAIR`
- historical eligibility: false
- next consumer: `m4-v2-marginal-static-measurement-repair-v2-design`
- generated work, compact-index reads, raw/sentinel replay, and duplicate validation: zero

## Gauss/Riemann cross-review

- Gauss pass: the only defensible decision is the frozen REPAIR mapping; all parent identities and the three Wilson failures are exact proof obligations.
- Riemann pass: the failure geometry is concentrated in dependent null fixtures across both scales, so the scalar decision retains fixture, scale, rate, and interval topology.
- Disagreement: null-family calibration/exchangeability mismatch is a plausible diagnosis, not yet a proven cause.
- Smallest shared conclusion: issue REPAIR mechanically and route only to a separately preregistered, independent repair-v2 design. Same-seed tuning and threshold relaxation remain forbidden.

## Engineering validation

- Decision capability contract: 6 focused tests passed.
- Current non-retired Worker mainline: 2,079 passed, 4 skipped.
- Source partition, additive migration, status projection, supervisor capability, deterministic replay, and artifact-index checks are included in that run.
- Ruff and `git diff --check`: passed.
- The seven permanently retired legacy entrypoint test files remain outside the canonical mainline; no current failure was excluded.

## Mainline integration matrix

| Link | Engineering state |
|---|---|
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` |
| Resolver | repaired-health decision depends on completed execution, completion fact, and source fact |
| Ready Queue | additive migration revises only the existing decision task |
| Supervisor | capability registered; merged live execution still pending |
| Capability | pure registered-artifact decision projector implemented |
| Artifacts | decision + mainline execution registration implemented |
| Status | authoritative decision and repair-v2 phase projection implemented |
| Next Task | one additive repair-v2-design placeholder |
| Replay | deterministic decision-only replay implemented; merged replay pending |

Integration answer: **NO — INTEGRATION_PENDING**.

The answer remains NO until a ready-for-review PR is green and merged, a fresh merged-commit unified Supervisor executes this exact decision once, both artifacts register immutably, and decision-only replay verifies the same execution identity. Broader M4 Evidence and Prediction-v2 promotion remain incomplete regardless of this round's code status.
