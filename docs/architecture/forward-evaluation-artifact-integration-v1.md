# Forward Evaluation Artifact Integration v1

## Purpose

This migration connects completed forward evaluation to `evaluation_artifact.v1` without
reinterpreting historical predictions. It changes the evidence boundary, not scoring or evaluation
semantics.

```text
forward_prediction_run
        │
        ├── persisted Runtime Envelope projection
        ├── ordered prediction candidates
        └── ranking contract
        │
        ▼
pure prediction snapshot evaluation (no write)
        │
        ▼
Forward Evaluation Artifact Adapter
        ├── verified   -> detached Evaluation Artifact + compact projection
        ├── unavailable -> explicit legacy/missing-evidence projection
        └── failed      -> structured invalid-evidence projection
        │
        ▼
single existing finalize operation
        ├── JSON report
        ├── Markdown report
        └── training_prediction_evaluations summary
```

The adapter projection is also returned by `ForwardEvaluationService`. JSON, Markdown, the database
summary, and the service result therefore describe the same artifact decision.

## Eligibility

A verified artifact requires all of the following:

- `ranking_contract=strict_v1`;
- a persisted `runtime_envelope_projection.v1` with `status=verified`;
- an `artifact_produced` scoring Runtime Envelope;
- a Candidate ABI package whose digest exactly matches that envelope;
- a completed evaluation payload with `leakage_passed=true` and all persisted candidate rows;
- canonical Prediction Evidence, Actual Outcome, and Ranking Audit parents.

Before persistence, the adapter also requires the payload's run key, line, target issue, Ranking
Contract, draw date, blue number, and Ranking Audit to equal those parents. It then compares every
exact-six, Red5, cutoff, and matched-count value with metrics recomputed by the Artifact compiler.
This prevents the detached artifact and the database row from becoming two contradictory facts.

The runtime never reconstructs or guesses a missing historical Runtime Envelope. A present malformed
projection is `failed`; absence is `unavailable`. The canonical Candidate ABI resolver is cached by
the expected package digest and rejects a different universe instead of trying alternate layouts.

## Compatibility policy

| Source state | Projection | Forward evaluation |
| --- | --- | --- |
| legacy ranking contract | `unavailable: legacy_ranking_contract` | accepted |
| strict run without stored Runtime Envelope | `unavailable: prediction_created_without_runtime_envelope` | accepted |
| malformed stored evidence | `failed` with structured reason | accepted unless required |
| verified strict evidence | `verified` with artifact digest | accepted |
| any non-verified state with `evaluation_artifact_required=true` | structured exception | `evaluation_failed`, retryable |

The required flag is opt-in. It lets future production policy fail closed after Runtime Envelope
capture is mandatory while preserving existing pending runs.

## Persistence model

The full artifact contains ordered candidates and is written as a standalone deterministic JSON file
under `data/output/prediction-evaluations/evaluation-artifacts/`. The database summary carries only a
compact projection:

- protocol, status, reason, and required policy;
- Evaluation and Ranking Contract identities;
- artifact and Evaluation Stage Envelope identity;
- source Runtime Envelope and Candidate ABI package digests;
- detached artifact path;
- `automatic_promotion_allowed=false`.

No database migration is required because the projection is stored in the existing JSONB summary.
Artifact generation does not itself authorize model promotion.

## Transaction and retry behavior

The snapshot evaluator runs with `write_report=false` and `persist=false`. After the adapter decision
is attached, the existing finalizer is invoked exactly once with the caller's original report policy
and `persist=true`. Evaluation-run and prediction-run lifecycle updates remain in the same database
transaction.

If a required artifact cannot be verified, no evaluation payload is finalized. The service records a
structured failure and leaves the prediction in `evaluation_failed`, so the existing pending evaluator
can retry it idempotently. A detached file written before a later database failure has deterministic
content and path and is safely replaced on retry.

## Non-goals

- no historical artifact backfill;
- no prediction or candidate regeneration;
- no schema migration;
- no scoring, ranking, feature, candidate, or evaluation formula change;
- no production backend promotion, supervisor restart, or watchdog change.
