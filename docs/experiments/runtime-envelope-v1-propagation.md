# Runtime Envelope v1 Propagation Round

## Primary goal

Propagate verified Runtime Envelope v1 evidence from the scoring boundary into
prediction, shadow, export, telemetry, and API-facing artifacts without changing
candidate identity, scoring, ranking, pending predictions, or production state.

## Non-goals

- No database migration or historical backfill.
- No candidate regeneration or rewrite of the 2026081 pending runs.
- No change to the scoring kernel, ranking contract, Feature ABI, or Candidate ABI.
- No attempt to synthesize Runtime Envelope evidence for legacy paths.
- No Evaluation Contract definition in this round.

## Projection contract

Every propagated value uses `runtime_envelope_projection.v1`:

- `verified`: contains a canonical `runtime_envelope.v1` payload that passed the
  Python parser, digest check, contract verification, and
  `state=artifact_produced` requirement.
- `unavailable`: contains no envelope and must include a structured reason.
- A present malformed envelope fails closed. It is never downgraded to
  `unavailable`.

## Propagation matrix

| Boundary | New verified runtime | Legacy runtime | Behavior |
| --- | --- | --- | --- |
| Kernel result | Full envelope | Empty legacy field | Existing behavior retained |
| Kernel telemetry | Version, state, digest | No asserted v1 identity | Existing verified path retained |
| Forward prediction metadata | Verified projection when a produced envelope is supplied | `prediction_created_without_runtime_envelope` | Written only for future snapshots |
| Latest prediction JSON | Per-run verified projection and aggregate digest summary | `legacy_prediction_without_runtime_envelope` | Read-only; no backfill |
| Latest prediction Markdown | Per-run status | `runtime_envelope=unavailable` | No evidence fabrication |
| Shadow comparison | Separate official and shadow projections | Side-specific legacy reason | One run cannot lend identity to the other |
| Candidate API DTO | Worker-produced projection | `legacy_training_snapshot_without_runtime_envelope` | Malformed stored projections fail closed |

## Compatibility result

The existing 2026081 prediction rows remain unchanged in PostgreSQL. When read
through the new projection layer they are explicitly interpreted as unavailable
Runtime Envelope provenance, while their ranking contract continues to normalize
independently as `legacy_score_partition`.

No candidate list, score, rank, prediction fingerprint, database row, or live
process is modified by this round.
