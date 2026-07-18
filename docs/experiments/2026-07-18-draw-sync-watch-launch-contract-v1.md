# Draw-Sync Watch Launch Contract v1 Acceptance

## Round contract

- Engineering authorization: Agent Request `131`
  (`engineering-draw-sync-launch-contract-c570c83`), execution `53`.
- Primary goal: make watcher activation and rollback fail-closed and idempotent
  across both code and configuration identity.
- Non-goals: no production activation/restart, cron edit, database migration,
  prediction/candidate/evaluation mutation, scoring change, backend switch,
  promotion, GPU, or SIMD.

## Root cause

The old ensure condition was only:

```text
running_commit == desired_commit
```

At a fixed commit, changing `DEHPS_FORWARD_SHADOW_ATTESTATION=false` to `true`
still returned `already running`. The submitted but unapproved Operator Request
`130` was cancelled before execution because neither activation nor rollback
could prove the loaded configuration.

## Implementation

- `dehps.draw_sync.launch_contract` builds, verifies, reads, writes, and exposes a
  CLI for `draw-sync-watch-launch.v1`.
- `DrawSyncWatch` atomically writes the verified contract at process start and
  includes it in state telemetry.
- `ensure_draw_sync_watch.sh` derives the desired digest, validates the running
  file, restarts on code or configuration drift, and rejects a replacement whose
  contract differs.
- The existing version file remains unchanged for compatibility.

## Validation

Focused contract, scheduler, and ensure-source tests:

```text
27 passed in 0.51s
bash -n scripts/ensure_draw_sync_watch.sh: passed
```

Coverage includes deterministic identity, attestation-sensitive digest, atomic
file round-trip, malformed/tampered rejection, invalid types and promotion
authority, scheduler state propagation, and the shell's dual commit/digest gate.

Complete worker regression:

```text
1259 passed, 4 existing multiprocessing fork warnings in 46.43s
```

## Production invariance

The engineering execution does not invoke the ensure script. The live watcher
therefore remains on its pre-round PID/commit until a new critical Operator
Request is explicitly approved. No production runtime artifact from this contract
is committed.
