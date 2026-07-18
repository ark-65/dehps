# Evaluation Artifact Runtime v1 acceptance report

## Round contract

- Primary goal: compile completed Evaluation Contract evidence into a detached, fail-closed artifact.
- Engineering request: `engineering-evaluation-artifact-runtime-679b0b8`.
- Execution: `42`.
- Non-goals: no forward persistence integration, database migration, Runtime Envelope reinterpretation,
  historical backfill, production operation, prediction regeneration, or Evaluation ABI.

## Implemented boundary

The runtime now has four immutable identities:

1. `prediction_evidence.v1` for run, line, target, source contracts and ordered candidate payload;
2. `actual_outcome.v1` for target issue, draw date, red/blue outcome and no-blue-scoring policy;
3. `evaluation_stage_envelope.v1` for all parent digests, compiler identity and output digest;
4. `evaluation_artifact.v1` for the complete detached evidence package.

The compiler recomputes exact-six, Red5 and cutoff metrics through
`evaluate_ranked_candidates_v1`. It never accepts caller-computed metrics as authority.

## Runtime enforcement

- Source Runtime Envelope must be `artifact_produced` and `scoring_kernel_result`.
- Source Evaluation Contract must still be null; source scoring evidence is never rewritten.
- Prediction Candidate, Scoring and Ranking identities must equal the source envelope.
- The resolved Candidate ABI Package is verified, then each prediction row is checked by `lex_id`
  and canonical numbers membership.
- Prediction and Outcome target issues must match.
- Target issue must be strictly after the source History Snapshot latest issue.
- Ranking Audit is canonical JSON with its own digest.
- Detached reconstruction must reproduce every parent digest, metrics payload and final artifact digest.

Evaluation uses a separate Stage Envelope instead of pretending that post-draw evaluation is another
transition in the scoring Kernel state machine.

## Validation

- Evaluation Artifact/Contract/Runtime provenance focused suite: `60 passed`.
- Contract Runtime regression: `164 passed`.
- Full Python suite: `1188 passed, 4 existing multiprocessing warnings` in `56.10s`.
- GitHub Actions: pending.

## Production impact

None. The compiler is not called by pending forward evaluation in this round. No database row,
historical artifact, pending candidate, prediction run, supervisor, cron entry, backend default, or
production status was changed.

## Next migration

Add an explicit adapter for eligible strict forward runs that can resolve their source Runtime
Envelope and Candidate ABI artifact. Legacy rows must emit structured `unavailable` provenance rather
than being backfilled, guessed, or silently treated as Evaluation Artifact v1.
