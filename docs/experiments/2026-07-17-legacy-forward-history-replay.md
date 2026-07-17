# Legacy Forward History Replay

Date: 2026-07-17

## Primary goal

Make forward evaluation and scoring-shadow replay reconstruct the exact history
snapshot used by legacy production runs whose metadata predates explicit
`history_scope` and `regime_years` fields.

## Non-goals

- Do not update production rows or historical metadata.
- Do not regenerate 2026081 or 2026082 candidates.
- Do not treat post-hoc replay as pre-draw shadow evidence.
- Do not change scoring, ranking, candidate, or feature contracts.

## Root cause

The three 2026081 runs contain the sealed history fingerprint
`34de80e61758227179a123e38a127aa3fc1a46ef5757d8b23757b5c6b7a84b6c`,
but their old resident process did not persist `history_scope` or
`regime_years`. The replay path therefore selected all 3477 draws through
2026080. The stored fingerprint instead matches exactly the 1498-draw
`current_regime_default` snapshot ending at 2026080 with the historical
10-year production window.

## Resolution contract

Explicit history metadata remains authoritative. For a legacy run without an
explicit scope:

1. Reconstruct full history and compare its digest.
2. If it differs, reconstruct only the frozen 10-year production default.
3. Accept that legacy selection only if its digest exactly equals the stored
   fingerprint.
4. Reject every other mismatch with
   `prediction_history_fingerprint_mismatch`.
5. Apply a rolling `train_window` only after the base snapshot identity has
   been verified.

This is digest-based compatibility, not heuristic inference or silent repair.

## Read-only production validation

The adapter was run against the existing database and wrote evidence only to
`/tmp`.

| Target | Lines | NumPy/Numba | Stored TopK | Evidence class |
| --- | ---: | --- | --- | --- |
| 2026081 | 3 | exact | matched | posthoc_reconstruction |
| 2026082 | 3 | exact | matched | posthoc_reconstruction |

All six official candidate artifacts matched their reconstructed NumPy result,
and all six Numba results were exactly equal to NumPy. Evaluation remained
`pending` and no database state changed.

The promotion gate correctly returned `insufficient_evidence`: both issues are
post-hoc, neither has completed evaluation/restart/watchdog attestation, and
only two issues exist instead of the required three.

## Validation

Focused validation:

```text
15 passed in 0.45s
```

The tests cover exact-digest legacy reconstruction and fail-closed rejection
when neither supported snapshot matches. Full worker validation is recorded in
the PR handoff.
