# Shadow Attestation Closure v1 Acceptance

## Round contract

- Engineering authorization: Agent Request `129`
  (`engineering-shadow-attestation-closure-1354000`), execution `52`.
- Primary goal: automatically and idempotently close eligible simultaneous
  pre-draw shadow captures after draw synchronization and forward evaluation.
- Non-goals: no live activation, cron edit, supervisor restart, database
  migration, prediction/candidate rewrite, backend switch, automatic promotion,
  Kernel P2, GPU/SIMD, or scoring/ranking/feature/evaluation formula change.

## Root cause

Prediction creation already sealed simultaneous pre-draw NumPy/Numba evidence,
but neither `DrawSyncWatch` nor `daily_pipeline` linked completed evaluation into
a post-draw artifact. The compensation CLI accepted two untrusted strings,
`restart_recovery_result` and `watchdog_result`. Therefore evaluation could finish
without completing the shadow evidence chain, while a caller could claim
operational success without machine-verifiable facts.

## Change

The round adds:

- sealed Watch Cycle v1 evidence from the live draw-sync process;
- Operational Receipt v1 with verifier-recomputed replay/watchdog results;
- persisted-run reconstruction through the verified Runtime ABI and both scoring
  backends;
- an idempotent closure service with content-addressed artifact lookup;
- opt-in integration immediately after pending-forward evaluation;
- per-line pending/ineligible/failure outcomes and failure isolation;
- a safe diagnostic CLI that cannot self-report operational success.

No database schema or row is changed by this implementation.

## Validation

Focused evaluation/shadow/watch/runtime regression:

```text
53 passed in 5.51s
```

Complete worker regression:

```text
1254 passed, 4 existing multiprocessing fork warnings in 58.84s
```

The new tests cover:

- missing current issue and incomplete evaluation remain pending;
- missing simultaneous pre-draw capture remains ineligible;
- exact closure writes one content-addressed artifact;
- the second execution reuses it without replay or duplicate evidence;
- a watchdog commit mismatch produces no official attestation;
- one line failure does not erase another line's success;
- a caller cannot flip a failed operational result, reseal the digest, and pass
  verification;
- draw-sync records shadow failure without replacing successful evaluation;
- every closure path retains `automatic_promotion_allowed=false`.

## Production invariance and remaining gate

Read-only production inspection after the code/test round still reports target
`2026082`, three pending `strict_v1` runs, 10,000 candidates per line, and no
simultaneous shadow capture. No `shadow-*.json` artifact exists. Those runs remain
unchanged and cannot count retroactively.

`DEHPS_FORWARD_SHADOW_ATTESTATION` remains disabled and no process was restarted.
An approved Operator action is still required to deploy/activate the closure on
the watcher. Even after activation, backend promotion remains blocked until three
consecutive future issues each have all three post-draw attestations and receive
independent approval.
