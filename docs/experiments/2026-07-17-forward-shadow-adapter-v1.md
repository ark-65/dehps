# Forward Scoring Shadow Adapter v1

## Round boundary

Primary goal: bind the scoring shadow runtime to durable forward prediction and
evaluation evidence without changing production tables or pretending that a
post-hoc replay is a simultaneous production shadow.

Non-goals:

- no live database execution in this round;
- no production candidate or evaluation write;
- no watcher, scheduler, or backend change;
- no automatic shadow enablement;
- no promotion credit for historical reconstruction.

## Adapter contract

The read-only `scripts.run_forward_scoring_shadow` entry point loads all forward
runs for one target issue and validates, per line:

1. the persisted candidate count equals the durable candidate rows;
2. the as-of history can be reconstructed to the stored history fingerprint;
3. the stored configuration reproduces the exact config hash;
4. official NumPy and shadow Numba consume the same CandidateStore, window,
   weights, target, and KernelRequest;
5. reconstructed official TopK row IDs and eight-decimal scores match the durable
   `forward_prediction_candidates` artifact;
6. a completed evaluation is leakage-safe and its ranking-audit model rank and
   model score match the reconstructed official result;
7. the resulting artifact is sealed through the existing shadow evidence writer.

The ranked universe and CandidateStore are built once and reused across all
three production lines. Missing rows, rank gaps, history/config drift, malformed
candidates, and mismatched official output raise structured
`ForwardShadowViolation` errors. Differences are counted; the adapter never
reorders or repairs stored evidence.

## Reconstruction is not promotion evidence

Every artifact created by this script carries:

```text
capture_mode=posthoc_reconstruction
source_code_commit=<prediction commit>
replay_code_commit=<current commit>
automatic_promotion_allowed=false
```

The promotion-readiness gate now additionally requires:

- `capture_mode=simultaneous`;
- explicit, unique prediction run keys;
- source ranking contract `strict_v1`;
- matching source/replay commit;
- stored official candidate artifact status `matched` with zero ID/score mismatch.

Consequently, replaying 2026081 or 2026082 can diagnose historical identity and
evaluation differences, but cannot be counted as one of the required three live
shadow issues.

## Validation

Focused adapter, shadow runtime, scoring kernel, and Feature Runtime tests:

```text
48 passed in 8.98s
```

Coverage includes official CandidateStore row identity, score drift, completed
evaluation rank/score binding, pending evaluation, post-hoc provenance, and the
existing three-issue gate refusing non-simultaneous evidence. The CLI import and
argument surface were executed successfully.

Complete worker regression:

```text
1156 passed, 4 existing multiprocessing fork warnings in 40.93s
```

## Operational state

No database connection or live shadow operation was executed. The output path is
under ignored `data/output/scoring-shadow`; writing those artifacts for a real
target issue remains an explicit Operator action.
