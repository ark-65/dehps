# Round 29 - Decouple Data Synchronization and Automatic Training Resume

## Goal

Decouple official draw synchronization from the training forward-wait gate, then add an audited exactly-once path from “new issue synced” to “training supervisor resumed.”

## What changed

- Added `dehps.draw_sync` with formal sync run records, draw audits, issue detection, idempotent new-issue events, a scheduler policy, and a watch process.
- Added `dehps.forward_state` to reconcile audited draw events with the supervisor's pending forward issue.
- Added `dehps.training_resume` to claim one event, launch one supervisor, persist the attempt, and mark events consumed only after launch succeeds.
- Added CLI commands:
  - `dehps draw-sync once|watch|status|events`
  - `dehps forward reconcile|status`
  - `dehps training-resume check|execute|history`
- Added read-only API modules for draw sync, training resume, and forward state.
- Added systemd units for periodic draw sync and explicit training resume.
- Updated `scripts/ensure_training_supervisor.sh` so the training watchdog no longer performs remote draw sync.

## Verification focus

Round 29 is not a model/training change. The core verification target is control-flow safety:

- draw sync can run independently while training is parked;
- new issue events are audited and idempotent;
- resume is blocked unless the forward issue, event fingerprint, process state, heavy lock, and allowed git ref all agree;
- failed launches are retryable;
- consumed events do not relaunch training.

## Non-goals preserved

- No model changes.
- No objective changes.
- No feature changes.
- No promotion changes.
- No production strategy changes.
- No training execution as part of the round implementation.

## Operational smoke plan

Use an isolated database such as `dehps_round29_smoke`:

```bash
cd apps/worker-python
DEHPS_TRAINING_RESUME_ALLOW_CURRENT_REF=1 .venv/bin/python -m dehps.cli draw-sync once
.venv/bin/python -m dehps.cli draw-sync status
.venv/bin/python -m dehps.cli forward reconcile
.venv/bin/python -m dehps.cli training-resume check
```

Expected behavior:

- `draw_sync_runs` records every run.
- no event is emitted for `no_change`;
- exactly one pending event is emitted for a truly new audited issue;
- `training-resume check` reports wait when any gate is missing;
- production DB is untouched when `DB_NAME=dehps_round29_smoke`.

## Validation

Completed validation:

```bash
cd apps/worker-python
.venv/bin/python -m pytest -q
DB_PORT=1 .venv/bin/python -m pytest -q

cd apps/api
npm test
npm run build
```

Results:

- Worker: `918 passed in 23.37s`
- Worker with `DB_PORT=1`: `918 passed in 23.58s`
- API: `109 passed`
- API build: passed

The Round 29 tests include draw audits, new-issue event idempotency, scheduler cadence, forward reconciliation, exactly-once resume, failure retry, concurrency, and the supervisor/draw-sync decoupling boundary.

## Isolated smoke

Local isolated smoke database: `dehps_round29_smoke`.

Smoke commands:

```bash
docker exec ark-dehps-postgres psql -U dehps -d postgres -c "CREATE DATABASE dehps_round29_smoke"
docker exec -i ark-dehps-postgres psql -U dehps -d dehps_round29_smoke -v ON_ERROR_STOP=1 < infra/postgres/init/001_init.sql
DB_HOST=localhost DB_PORT=54329 DB_NAME=dehps_round29_smoke DB_USER=dehps DB_PASSWORD=dehps_password .venv/bin/python -m dehps.cli draw-sync status
DB_HOST=localhost DB_PORT=54329 DB_NAME=dehps_round29_smoke DB_USER=dehps DB_PASSWORD=dehps_password .venv/bin/python -m dehps.cli forward status
DB_HOST=localhost DB_PORT=54329 DB_NAME=dehps_round29_smoke DB_USER=dehps DB_PASSWORD=dehps_password .venv/bin/python -m dehps.cli training-resume execute
```

Smoke result:

- isolated schema applied successfully;
- seeded isolated `ssq_history` reached latest issue `2026080`;
- `draw-sync status` returned no production events/runs in the isolated DB;
- `training-resume execute` found no pending event and therefore returned `executed:false`;
- no real training supervisor was launched from the feature branch.
