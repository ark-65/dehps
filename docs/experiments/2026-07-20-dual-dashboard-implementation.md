# Dual Dashboard Implementation

Date: 2026-07-20

Role: Engineering Agent

Agent Request: `engineering-dual-dashboard-de85f31`

Parent governance: `de85f31f9858848c9448a314bc6dff9c479edfe3`

## Primary goal

Implement separate Runtime and Research dashboard projections and Angular views without changing prediction, training, Runtime, or promotion behavior.

## Delivered interfaces

- `GET /dashboard/runtime` separates accepted Runtime capability from live operational health.
- `GET /dashboard/research` separates Research Quality from Research Process.
- Angular exposes distinct Runtime Dashboard and Research Dashboard tabs while retaining the existing detailed views.
- Evidence uses explicit `verified`, `warning`, `stale`, `missing`, `failed`, `not_applicable`, and `not_defined` states.

## Evidence semantics

- Source-controlled M1 acceptance is a persistent capability statement, not a live-health statement.
- Backend equality and worker regression have an explicit review window and become `stale` after it expires.
- Missing acceptance, backend, Recent-30, Recent-300, calibration, Shadow, or future-generalization evidence fails closed as `missing`.
- Recent-100 is same-window search-selection evidence. The current `3 / 3 / 4` artifact can be verified as an evaluation while overall Research Quality remains `warning` when it records `no_learning_lift`.
- Recent-300 is labeled overlapping stability evidence, not independent generalization.
- Walk-forward artifacts are labeled historical rejection/validation evidence.
- Promotion Rate is descriptive only.
- Expected Value remains `not_defined` until payout, cost, and decision-policy contracts exist.

## Non-goals preserved

- No feature, weight, window, candidate, scoring, ranking, or evaluation algorithm changed.
- No Runtime backend, ABI, supervisor, database schema, deployment, production default, or Promotion Gate changed.
- No predictive conclusion or automatic promotion was produced.

## Validation

```text
cd apps/api && npm test
117 passed

cd apps/api && npm run build
passed

cd apps/web && npm test
19 passed

cd apps/web && npm run build
passed

git diff --check
passed
```

## Known limitations

- No independent Recent-30 or Recent-300 artifact currently exists.
- No sealed future-issue Shadow cohort currently exists.
- Calibration and Expected Value contracts remain undefined.
- Runtime operational evidence must be refreshed after its review window; the dashboard intentionally does not remain permanently green.
