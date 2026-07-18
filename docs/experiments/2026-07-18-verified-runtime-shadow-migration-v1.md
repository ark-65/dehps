# Verified Runtime simultaneous shadow migration v1

## Round contract

- Primary goal: make simultaneous forward shadow evidence execute both backends from one verified
  Runtime ABI package.
- Engineering authorization: Agent Request `122`
  (`engineering-verified-runtime-shadow-migration-44b8405`), execution `45`.
- Base commit: `44b8405`.
- Production impact: none.
- Non-goals: no backend-default switch, database migration, pending candidate rewrite, supervisor
  operation, scoring change, GPU, or promotion decision.

## Root cause

The forward hook used `execute_shadow_pair(...)`, which independently called legacy
`prepare(candidate_store)` for NumPy and Numba. Candidate ABI identity was present, but Feature ABI,
History/Window identity, Runtime verification, and a shared `verified_runtime_id` were absent from
the simultaneous evidence chain.

## Implemented boundary

- Effective forward history is compiled to a History Snapshot and Window Artifact.
- Existing CandidateStore payload is reused through its Candidate ABI package.
- `RuntimeABICache.compile_runtime(...)` creates or retrieves one verifier-gated Runtime package.
- Feature ABI NumPy and Feature ABI Numba execute from that exact package.
- Comparison evidence seals the shared Runtime id, Runtime/Feature digests, cache receipts, Runtime
  Envelopes, Candidate ABI identity, strict TopK result, and official-row artifact check.
- Missing or divergent Runtime identity is counted as a comparison mismatch and fails exact status.
- The legacy shadow entry remains available for historical compatibility but is no longer used by
  simultaneous forward capture.

## Acceptance assertions

The focused fixture verifies:

1. official and shadow backends are `feature_abi_numpy_reference` and `feature_abi_numba_cpu`;
2. both results carry one `verified_runtime_id` and zero Runtime identity mismatches;
3. strict candidate IDs and scores match the official generated rows;
4. a repeated identical capture returns the same output and Runtime id;
5. the repeated compile reports Feature and Runtime cache hits;
6. automatic promotion remains disabled;
7. a shadow exception remains structured without changing official candidates.

## Validation

- Shadow/Feature/Cache focused regression: `58 passed` in `15.16s`.
- Full Python regression: `1203 passed, 4 existing multiprocessing fork warnings` in `59.03s`.
- No API or Web surface changed, so their suites were not required for this round.

## Remaining evidence boundary

This is an implementation acceptance round, not a backend promotion. Three future target issues must
still produce simultaneous pre-draw evidence, completed post-draw evaluation, restart recovery, and
watchdog checks with zero differences before any independent default-switch approval.
