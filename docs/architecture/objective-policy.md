# Objective Policy

DEHPS training objective configuration is an immutable, versioned value object. The current policy is `rank_objective_v1`; its constants are mechanically extracted from the pre-refactor supervisor and are not new tuning values.

`ObjectivePolicy.canonical_json()` serializes every field with sorted keys and compact separators. `objective_policy_hash` is SHA-256 over that canonical JSON, so mapping insertion order cannot change identity. The current hash is:

```text
c63399d633aa1ae0148df96698df77233458ccbb265db50ed959907bce726387
```

`evaluate_objective(TrainingMetrics, ObjectivePolicy)` is pure: it reads no database, environment variable, HTTP state, or runtime singleton. The legacy `reward_summary` surface delegates to it and keeps the existing camel-case payload and six-decimal rounding.

Every new training summary, status report, and `training_round_results` row records `objective_policy_version` and `objective_policy_hash`. Existing rows are compatible through `legacy_unversioned` and an empty hash; this round does not rewrite historical rows.

Changing any reward, penalty, rank band, or rounding rule requires a new policy version, new characterization evidence, and a separate algorithm-change round. Refactoring must never silently reuse `rank_objective_v1` for changed arithmetic.
