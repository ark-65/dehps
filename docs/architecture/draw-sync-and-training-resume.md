# Draw Sync and Automatic Training Resume

Round 29 separates two concerns that used to live inside the training watchdog:

```text
draw synchronization
        ↓
audited new-issue event
        ↓
forward-state reconciliation
        ↓
exactly-once training resume
```

The important rule is that `waiting_for_forward_issue` is not allowed to block data synchronization. Draw sync is an independent service with its own PID file, heartbeat, lock, database audit, and event log. Training resume is a separate consumer that can only launch a supervisor after an audited `draw_issue_events` row proves that the pending forward issue is now present.

## Components

- `apps/worker-python/dehps/draw_sync/`
  - Reads the formal draw source through the existing SSQ synchronizer.
  - Audits legal red balls, blue ball range, issue order, duplicates, and history fingerprint.
  - Writes append-only `draw_sync_runs`.
  - Emits idempotent `draw_issue_events` only for audited new issues.
- `apps/worker-python/dehps/forward_state/`
  - Reconciles the pending forward issue recorded by the training watch with audited draw events.
  - Refuses resume when the old supervisor PID is still alive, the heavy-job lock is active, the event fingerprint no longer matches history, or the current git ref is not allowed for resume.
- `apps/worker-python/dehps/training_resume/`
  - Claims one pending/failed draw event.
  - Launches a new training supervisor once.
  - Marks the event consumed only after launch succeeds.
  - Leaves launch failures retryable.

## Database tables

- `draw_sync_runs`: append-only audit of every sync attempt, including locked/source unavailable/invalid/audit failed outcomes.
- `draw_issue_events`: idempotent forward-boundary events. A new issue may only have one active pending/consuming/consumed event.
- `training_resume_attempts`: append-only decisions from the resume controller.

## Runtime boundaries

`scripts/ensure_training_supervisor.sh` no longer calls `scripts/sync_latest_ssq.py` or the remote sync cadence planner. It only reads `ssq_history`, checks conflicts and training health, refreshes local training signals when needed, and parks/runs the supervisor according to the forward gate.

Independent draw sync entrypoints:

- `dehps draw-sync once`
- `dehps draw-sync watch`
- `scripts/run_draw_sync_watch.py`
- `scripts/ensure_draw_sync_watch.sh`
- `deploy/systemd/dehps-draw-sync.service`
- `deploy/systemd/dehps-draw-sync.timer`

`draw-sync once` is sync-only and never launches training. As of Round 31,
`draw-sync watch` defaults to `resume_on_event=false`; legacy training resume
must be requested explicitly with `--resume-on-event` and should remain disabled
for the resident runtime deployment.

Resume entrypoints:

- `dehps forward reconcile`
- `dehps forward status`
- `dehps training-resume check`
- `dehps training-resume execute`
- `deploy/systemd/dehps-training-resume.service`

## API

All API routes are read-only:

- `GET /draw-sync/status`
- `GET /draw-sync/runs`
- `GET /draw-sync/events`
- `GET /training-resume/status`
- `GET /training-resume/history`
- `GET /forward-state`

No API route can modify training, draw history, events, or production state.

## Safety invariants

- A draw event is never created from Markdown, prompts, or training-watch text.
- A new issue event requires a changed history fingerprint and a passing draw audit.
- Resume requires an unconsumed audited event at or beyond the pending forward issue.
- A failed launch returns the event to `failed`, which is retryable.
- A consumed event cannot launch training again.
- Draw-sync and training-resume locks are separate from the heavy training lock.
- The packaged Round 31 systemd draw-sync service is a resident
  `draw-sync watch --no-resume-on-event` process and no longer starts
  `dehps-training-resume.service`.
- The long-running draw-sync watch does not call legacy resume by default.
