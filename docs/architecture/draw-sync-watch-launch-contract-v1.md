# Draw-Sync Watch Launch Contract v1

## Purpose

The draw-sync watcher is production control-plane code. A Git commit identifies
its source, but does not identify the configuration loaded by the process. Before
this contract, `ensure_draw_sync_watch.sh` treated a same-commit process as
current even when `DEHPS_FORWARD_SHADOW_ATTESTATION` had changed. Activation and
rollback could therefore report success without enforcing the requested runtime
configuration.

`draw-sync-watch-launch.v1` makes the process identity:

```text
Git commit
+ schedule intervals and timezone
+ resume-on-event policy
+ shadow-attestation enablement
+ automatic-promotion prohibition
= launch contract digest
```

## Runtime boundary

At process start, `DrawSyncWatch` builds and verifies the contract, then writes:

- the legacy plain commit version file;
- an atomic `draw-sync-watch.launch.json` contract;
- the same contract in every watcher state payload.

The launch contract is not an authority to generate predictions, evaluate runs,
or promote a backend. It fixes `automatic_promotion_allowed=false`.

## Ensure semantics

`scripts/ensure_draw_sync_watch.sh` independently builds the desired contract
from the exact current commit and approved environment. A running process is
accepted only when:

```text
running commit == desired commit
and
verified running contract digest == desired contract digest
```

Missing, malformed, tampered, stale-code, or stale-configuration contracts are
all stale. The script gracefully replaces only the draw-sync watcher and verifies
both identities again before reporting success.

The same rule makes rollback idempotent: changing attestation from `true` to
`false` changes the desired digest even if the code commit is unchanged, so the
ensure entry cannot incorrectly return `already running`.

## Contract fields

- `protocol = draw-sync-watch-launch.v1`
- full lowercase 40-character `code_commit`
- positive `interval_seconds`, `hot_interval_seconds`, and
  `cold_interval_seconds`
- valid IANA `timezone`
- boolean `resume_on_event`
- boolean `shadow_attestation_enabled`
- `automatic_promotion_allowed = false`
- deterministic `contract_digest`

The verifier rejects malformed types, invalid timezone/commit, promotion
authority, and any digest mismatch. Attestation remains disabled by default.

## Operational compatibility

The plain `.version` file remains for existing readers. A watcher created before
this contract has no valid launch file and is intentionally considered stale the
next time the ensure script is executed. Merely merging this code does not restart
or signal that process; production replacement still requires an approved
Operator Request.
