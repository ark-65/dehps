# Draw-Sync Supervisor Ownership v1

## Boundary

Draw sync may be owned by exactly one supervisor. A resident manual watcher and
the user systemd unit must never run at the same time, even when both processes
would execute idempotent database operations.

The ownership chain is:

```text
Operator Request
  -> systemd deployment contract
  -> installed unit + timer + dedicated environment
  -> one-shot launch contract
  -> audited watch state
```

The manual `ensure_draw_sync_watch.sh` path probes `dehps-draw-sync.service` and
`dehps-draw-sync.timer` before reading or signalling a watcher PID. A loaded,
enabled, active, or PID-owning systemd unit causes a structured fail-closed
rejection. There is no force flag. An operator must either use the canonical
systemd deployment path or deliberately uninstall systemd ownership first.

## Canonical systemd mode

`deploy/systemd/dehps-draw-sync.service` is a one-shot service. The timer starts
a fresh interpreter for every poll, preventing a stale resident process from
bypassing newly deployed evaluation or attestation code.

The dedicated non-secret file `~/.config/dehps/draw-sync.env` owns only:

- `DEHPS_FORWARD_SHADOW_ATTESTATION`;
- `DEHPS_FORWARD_SHADOW_CAPTURE`;
- `DEHPS_FORWARD_SHADOW_WORKERS`.

The general project `.env` remains a separate source for database and service
configuration. The draw-sync environment must not contain credentials.

`draw-sync-systemd-deployment.v1` binds the exact Git commit, source unit and
timer digests, desired watcher launch-contract digest, and normalized shadow
environment. It always records `automatic_promotion_allowed=false`.

## Deployment behavior

`scripts/ensure_draw_sync_systemd.sh --apply` is an Operator-only path. It:

1. rejects a dirty worktree;
2. compiles the desired launch and deployment contracts;
3. recognizes an already-converged installation without restarting it;
4. stops the timer and service before changing their definitions;
5. aborts if any unmanaged watcher remains;
6. installs the repository one-shot unit, timer, and dedicated environment;
7. runs one immediate audited one-shot cycle;
8. verifies code identity, launch digest, evaluation status, and promotion lock;
9. enables the timer and seals the deployment artifact;
10. restores the previous installation if any step fails.

The script does not kill an unmanaged process. That condition requires a
separate, PID-specific Operator decision.

## Non-goals

- No prediction generation or candidate replacement.
- No evaluation-contract or scoring-contract change.
- No automatic production backend switch.
- No permission to rewrite historical shadow evidence.
