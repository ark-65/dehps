# Forward Evaluation Sync-Change Recheck — 2026-07-11

## Primary Goal

Invalidate an otherwise accepted forward evaluation when the current draw is inserted or updated by the same watchdog sync, so corrected official draw data is evaluated before advisor refresh or supervisor release.

## Non-Goals

- No model, advisor, source budget, candidate, objective, or promotion change.
- No weakening of idempotent retry on later unchanged syncs.
- No retroactive reconstruction once a historical prediction snapshot has been replaced.

## Triggering Observation

`ssq_history` has no row-level `updated_at`. The supported update path replaces a CSV draw with official `zhcw` numbers. An accepted evaluation for the identical snapshot could otherwise be subtracted from the pending set even though its actual draw changed in the current sync.

## Gauss-Inspired Version Invariant

- **Object:** due snapshot set `S`, accepted subset `A`, and current sync change indicator `C`.
- **Normal fixed point:** when `C=0`, evaluate `S-A`.
- **Changed-current transition:** when `C>0`, the current issue is forced back into the evaluation plan, so its effective accepted subset is empty for that run.
- **Next fixed point:** after successful recomputation and a later unchanged sync, the new accepted rows are skipped normally.
- **Boundary:** this validates evaluation freshness relative to the current sync event, not predictive quality.

## Change

- Added repeatable `--force-issue` planning input.
- The watchdog passes the current issue whenever inserted plus updated count is positive.
- Accepted rows for a forced issue no longer suppress evaluation.
- Unrelated accepted issues remain idempotently skipped.
- Added forced-current and unrelated-issue tests plus an orchestration contract test.

## Validation Plan

- Focused planner, watchdog-contract, and prompt-contract tests.
- Full Python worker suite.
- Live unchanged-sync replay must keep `changed_count=0`, emit zero evaluation work, remain parked, and start no supervisor.

## Validation Result

- Focused planner, watchdog-contract, and prompt-contract tests: `24 passed`.
- Final full Python worker suite: `596 passed`.
- Watchdog and autonomous self-iteration shell syntax checks passed.
- Live unchanged-sync replay at `2026-07-11 17:03 CST`:
  - inserted and updated counts remained zero;
  - no force issue was added and the planner emitted `count=0`;
  - the complete `2026079` three-line snapshot remained pending with `10,000` candidates per line;
  - lifecycle remained consistently parked;
  - no supervisor or self-iteration process started.

## Evidence Boundary

The legal universe, history/frozen windows, null baseline, quarantine, leakage rules, selection, and promotion remain unchanged. The sync-change signal only invalidates stale evaluation acceptance for the current release attempt.
