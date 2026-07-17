# Forward Evaluation Operator Readiness

Date: 2026-07-17

## Primary goal

Freeze the production preconditions, immutable candidate baselines, execution
order, rollback boundary, and acceptance evidence for recovering the 2026081
forward-evaluation loop and enabling future simultaneous scoring shadow capture.

## Non-goals

- Do not execute evaluation or update production rows in this engineering round.
- Do not interrupt the active research lane.
- Do not regenerate or supersede 2026081/2026082 predictions.
- Do not change the production scoring backend from `numpy_reference`.
- Do not count post-hoc reconstruction as pre-draw shadow evidence.

## Read-only production snapshot

- Repository commit: `7175a8e`.
- Latest history issue: `2026081`.
- 2026081: three pending runs, 30,000 stored candidates, no evaluation rows.
- 2026082: three pending runs, 30,000 stored candidates, no evaluation rows.
- The 2026081 draw event is still pending.
- The formal cron entry already runs the daily pipeline at 21:45 Asia/Shanghai
  on Tuesday, Thursday, and Sunday.
- No user systemd daily-pipeline unit is installed. Installing a duplicate timer
  is therefore not part of this recovery.
- Draw-sync watcher PID 2655006 started on 2026-07-14. It predates the evaluation
  closure, has no version file, and its state payload has no forward-evaluation
  section.
- Forward-runtime PID 2731725 is a read-only status heartbeat. It does not execute
  pending evaluations.
- A research-only weight-grid task currently owns the heavy-job lock. It must not
  be stopped by this operation.

## Immutable candidate baselines

The digest input is the ordered sequence `rank:red_numbers:score` for each run.

| Issue | Line | Count | Baseline MD5 |
| --- | --- | ---: | --- |
| 2026081 | static_100 | 10000 | `ef9b5d95058c3de83065d05e4acf5f1f` |
| 2026081 | dynamic_kdj | 10000 | `82dc0cd0aa4b6013c9bd05d5f520d764` |
| 2026081 | dynamic_kdj_near | 10000 | `e34ee70f4a89dd57cfe29c5164b152dc` |
| 2026082 | static_100 | 10000 | `906718a1924e81e79f2b9583d156bc0d` |
| 2026082 | dynamic_kdj | 10000 | `ea342d6f8836d6355614807ce53fbdbe` |
| 2026082 | dynamic_kdj_near | 10000 | `9ec443319acbe85af1186352f5839f85` |

The null ranking contract on 2026081 must continue to normalize to
`legacy_score_partition` without writing it back. The stored `strict_v1` values
on 2026082 must remain unchanged.

## Required Operator contract

The approved production request must name the exact commit and authorize only:

1. Wait for the current research heavy-job owner to release naturally; do not
   terminate or restart it.
2. Capture the six candidate counts and ordered digests again immediately before
   execution; abort on drift.
3. Run `python -m scripts.evaluate_pending_forward_runs` from the current main
   commit.
4. Require exactly three completed 2026081 evaluations and zero failed rows.
5. Run the command a second time and require zero new evaluations.
6. Recompute all six candidate counts and digests and require exact equality with
   the pre-operation snapshot.
7. Gracefully retire only the stale draw-sync watcher after confirming its PID,
   command, and state-file ownership. Start the current watcher with the same
   `--no-resume-on-event` policy; do not touch the forward or research runtimes.
8. Verify a fresh watcher version file, heartbeat, current commit, successful
   no-change sync, and an idempotent zero-work evaluation batch.
9. Add `DEHPS_FORWARD_SHADOW_CAPTURE=true` and
   `DEHPS_FORWARD_SHADOW_WORKERS=8` to the formal 21:45 pipeline environment and
   the training-watch environment used for the next production supervisor.
10. Keep `numpy_reference` official. Shadow evidence is diagnostic only and
    automatic promotion remains forbidden.

## Abort and rollback

Abort before mutation when the repository is dirty, main is not the approved
commit, the active research owner changes unexpectedly, any candidate digest
drifts, or more than three 2026081 active runs exist.

If evaluation fails, preserve the structured `evaluation_failed` state and error;
do not delete or rewrite evidence. The retry entry point is idempotent and must be
used after correcting the failure.

If the replacement watcher fails its heartbeat, stop only that replacement and
restore the previous watcher command from the captured process contract. Do not
roll back completed evaluation rows and do not rewrite candidates.

If shadow capture fails on a future prediction, preserve the official NumPy run,
store structured shadow failure evidence, and leave production backend and
promotion state unchanged.

## Acceptance evidence

- Three unique completed evaluation rows for 2026081, one per prediction run.
- Three 2026081 prediction runs in `evaluated` state with normalized legacy
  ranking provenance.
- A second compensation run reports zero evaluated and zero failed.
- All six candidate counts and ordered digests remain identical.
- The watcher reports the approved code commit and a current heartbeat.
- The 21:45 schedule remains singular; no duplicate timer is installed.
- The active research run is neither killed nor replaced by this operation.
- The first eligible pre-draw capture is a future prediction after activation;
  2026081 and 2026082 remain post-hoc and cannot count toward promotion.
