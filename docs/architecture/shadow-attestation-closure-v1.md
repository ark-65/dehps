# Shadow Attestation Closure v1

## Boundary

This runtime closes the gap between an immutable simultaneous pre-draw scoring
capture and its post-draw evaluation attestation. It does not generate or alter
predictions, rewrite evaluation rows, select a backend, or authorize promotion.

The production hook is opt-in:

```text
DEHPS_FORWARD_SHADOW_ATTESTATION=true
```

The default is disabled. Enabling or restarting a production watcher remains a
separate Operator action.

## Evidence flow

```text
simultaneous pre-draw capture in prediction metadata
                         |
draw-sync watch: audited sync + evaluation batch
                         |
sealed Watch Cycle v1
                         |
persisted prediction/history/config/candidates replay
                         |
NumPy reference == Numba CPU == stored official artifact
                         |
derived Operational Receipt v1
                         |
content-addressed post_draw_attested artifact
```

`restart_recovery_result` is derived from a complete replay of the persisted
forward run. The replay must reproduce the sealed history/config boundary,
official candidate identities and scores, completed evaluation rank/score, source
commit, and exact NumPy/Numba result.

`watchdog_result` is derived from the live draw-sync cycle. The cycle must carry a
successful audited `no_change`, `new_issue`, or `corrected_issue` sync, a zero-
failure evaluation batch, the same current issue, and the same loaded code commit
as the replay.

The receipt stores those facts and their digests. Verification recomputes both
results from the embedded replay and watch-cycle facts. Rewriting `passed` and
recomputing a plain digest is rejected as
`shadow_operational_receipt_derivation_mismatch`.

## Eligibility and idempotency

Only a non-superseded run with all of the following is eligible:

- a sealed `capture_mode=simultaneous` pre-draw capture;
- prediction status `evaluated`;
- forward evaluation status `completed`;
- synchronized actual draw for the watch cycle's current issue.

Legacy/post-hoc runs remain diagnostic-only. Missing draws and incomplete
evaluations remain pending. A successful attestation is written by comparison
digest; reruns verify and reuse the same file. Failed operational evidence is
reported but not persisted as a competing attestation, so a later valid retry
cannot create an ambiguous pair.

Failures are isolated per line and included in the draw-sync state. They never
replace accepted evaluation results. Every closure report and receipt fixes
`automatic_promotion_allowed=false`.

## Interfaces

- `ForwardShadowAttestationService.close_cycle()` is the idempotent control-plane
  entry.
- `DrawSyncWatch` calls it only when the opt-in environment flag is enabled.
- `scripts.run_forward_scoring_shadow` no longer accepts caller-declared restart
  or watchdog pass strings. A sealed `--watch-cycle-evidence` file is required to
  create an attestation; without it the command emits diagnostic reconstruction
  only.
- `scripts.evaluate_scoring_shadow_gate` remains read-only and still requires
  three consecutive complete issues plus independent approval.

## Compatibility

No database migration is required. Existing 2026081/2026082 predictions,
candidates, fingerprints, statuses, timestamps and evidence remain untouched.
The first qualifying issue must have been created with simultaneous pre-draw
capture and later closed by an activated watcher running the same source commit.
