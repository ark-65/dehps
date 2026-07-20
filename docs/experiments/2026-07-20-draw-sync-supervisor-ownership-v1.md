# Draw-Sync Supervisor Ownership v1

## Round contract

- Engineering Request: `engineering-draw-sync-supervisor-ownership-ed569e3`
  (request 133, execution 55).
- Primary goal: prevent systemd and manual draw-sync supervisors from owning the
  same runtime files or executing concurrently.
- Non-goals: no installed-unit change, live restart, prediction mutation,
  candidate backfill, backend switch, or automatic promotion.

## Incident evidence

After Operator execution 54, the manually launched watcher used PID `1010834`
and verified launch digest `c0c7ff7f...42f11` with attestation enabled. The
previous PID belonged to `dehps-draw-sync.service`, whose installed stale unit
contained `Type=simple` and `Restart=always`. Systemd relaunched PID `1013083`
30 seconds later with launch digest `93513116...206d9` and attestation disabled.

Both processes then wrote the same PID, version, launch, and state paths. This
contradicted the single-owner invariant even though forward evaluation itself
was idempotent.

The approved rollback stopped only manual replacement PID `1010834`. Production
returned to one systemd-owned watcher, PID `1013083`, with attestation disabled.
No prediction, candidate, evaluation, or database row was rewritten by the
rollback.

## Root cause

The launch contract bound code and watcher configuration but not supervisor
ownership. `ensure_draw_sync_watch.sh` trusted the PID file and could signal a
systemd-owned process. The installed user unit also lagged behind the repository
one-shot unit.

## Change

- Add a structured systemd ownership probe and fail closed before manual PID
  mutation.
- Add `draw-sync-systemd-deployment.v1` to bind unit, timer, environment, code,
  and launch-contract identities.
- Add a rollback-capable, explicit `--apply` systemd deployment entry point.
- Add a dedicated non-secret draw-sync environment and explicit one-shot CLI
  schedule.
- Add tests for absent ownership, inactive-but-installed ownership, active PID
  ownership, tampered deployment contracts, source drift, environment drift,
  and promotion-authority rejection.

## Production boundary

This engineering round does not reinstall or restart systemd. A new critical
Operator Request must capture the exact merged commit and deployment digest
before activation is attempted again.
