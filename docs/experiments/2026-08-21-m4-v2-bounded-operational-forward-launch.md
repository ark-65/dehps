# M4-v2 bounded operational forward launch

## Primary goal

Launch the frozen `MARGINAL_STATIC` protocol as Cohort A before the first dynamically eligible pre-draw deadline. This round adds only the missing mainline bindings for preregistration, mechanical refit, paired 100/100 shadow output, immutable checkpoint, settlement, replay, compact status, and the existing draw-sync/systemd loop.

## Non-goals

No model or feature family, tuning, threshold change, historical P3 rewrite, formal P4 activation, P5, Promotion, generic registry, recovery version, or production betting authorization is introduced. Cohort A is excluded from a later confirmatory P3. Issues 20 and 60 are integrity-only; issue 120 is the sole outcome-bearing review.

## Frozen operating contract

- Estimator: `EXPANDING_LEGAL_MARGINAL_ALPHA_1`, `q_i=(c_i+2/11)/(n+1)`.
- Inputs: expanding audited legal red-number history strictly before the target issue; no feature family.
- Candidate arms: 10,000 deterministic legal proposals ranked by frozen Bernoulli log score to exactly 100 model tickets, paired with exactly 100 independently seeded legal-uniform tickets.
- Blue: `SHARED_DETERMINISTIC_UNIFORM_BLUE_BY_RANK_V1`, identical by rank across arms.
- Deadline: 17:00 Asia/Shanghai on an official Tue/Thu/Sun draw date; official draw time 21:15.
- Primary endpoint: model 33-event Bernoulli log2 score minus the legal-uniform `q=2/11` score for the same official issue.
- Missing checkpoint: never backfill; skip to the next legal issue.

## Mainline integration matrix

| Stage | Ready condition | Runner | Registered output | Next consumer |
|---|---|---|---|---|
| Preregistration | selected-program and staged-sample facts | Unified Research Evidence Supervisor | frozen contract + replay | initial refit |
| Refit | registered preregistration | Unified Research Evidence Supervisor | dataset, model, 33-vector, identities | pre-draw generator |
| Pre-draw | registered model | Unified Research Evidence Supervisor | 100/100 sets, checkpoint, report | pre-draw replay |
| Settlement | audited draw-sync fact | Unified Research Evidence Supervisor | primary endpoint and support metrics | settlement replay |
| Next issue | registered settlement replay | Python draw-sync callback | next issue five-task DAG | next refit |

Acceptance requires `YES — validated by unified mainline execution and replay` after the merged-main Operator launch. Runtime identities and the first report path are recorded in registered artifacts and the final Goal handoff, not fabricated in this source report.
