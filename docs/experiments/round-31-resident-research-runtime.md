# Round 31 - Resident Continuous Research Runtime

## Goal

Deploy the Round 30 continuous research runtime as the resident research worker,
while the forward runtime waits independently for new draw evidence.

The intended operating state is:

- Continuous Research Runtime: resident, cycling, and never waiting for forward.
- Forward Runtime: resident and allowed to wait for the next issue.
- Draw Sync: managed by the draw-sync timer/watch path.
- Legacy Training Supervisor: not running.

## Changes

- Added a resident research runtime wrapper with PID, heartbeat, lock, state, and
  JSONL cycle audit.
- Added a resident forward runtime wrapper with PID, heartbeat, lock, and state.
- Added CLI commands:
  - `dehps research-runtime run`
  - `dehps forward-runtime run`
- Added user-service-ready systemd units:
  - `deploy/systemd/dehps-research-runtime.service`
  - `deploy/systemd/dehps-forward-runtime.service`
  - updated `deploy/systemd/dehps-draw-sync.service`
- Changed draw-sync watch default so new events no longer launch legacy training
  resume unless explicitly requested with `--resume-on-event`.
- Added tests for:
  - 10 resident research cycles;
  - legacy supervisor concurrency blocking;
  - resident forward waiting status;
  - draw-sync default no legacy training resume.
- Follow-up runtime fix:
  - resident research cycles now execute wired research actions instead of only
    emitting queued items;
  - current safe executor runs Round 28 Pattern Discovery / Feature Synthesis /
    Strategy Synthesis / Proposal Generation with research-only persistence;
  - duplicate pattern proposal submission is idempotent, so repeated resident
    cycles reuse the existing Research Proposal Request instead of crashing.
- Follow-up utilization fix:
  - `research_cpu` now controls real parallel pattern-discovery lanes;
  - lanes perform CPU-heavy dry-run searches across different history windows;
  - the parent process persists all lanes serially to avoid Postgres
    deadlocks and foreign-key races;
  - repository summaries now expose observation, validation, and cycle counts so
    learning/evidence accumulation is visible even when formulas are canonicalized;
  - the packaged resident unit now uses `--interval-seconds 1` and
    `--daily-cycle-limit 5760`.

## Operational boundary

Research evidence remains source=`research` and cannot promote production
behavior. Promotion remains forward-only.

The resident research worker refuses to start when a legacy supervisor process is
active. Stale PID files may be cleaned only after the PID is confirmed inactive.

## Validation

Completed:

```bash
cd apps/worker-python
.venv/bin/python -m pytest -q tests/test_resident_research_runtime.py tests/test_resident_forward_runtime.py tests/test_draw_sync_scheduler.py
# 8 passed

.venv/bin/python -m compileall -q dehps/research_runtime dehps/forward_runtime dehps/draw_sync scripts/run_research_runtime.py scripts/run_forward_runtime.py dehps/cli.py

.venv/bin/python -m pytest -q
# 938 passed

DB_PORT=1 .venv/bin/python -m pytest -q
# 938 passed
```

Resident smoke:

- `dehps research-runtime run --max-cycles 10 --interval-seconds 0`
  completed `cycles_completed=10`.
- Last 10 cycle records had:
  - `snapshot_stable_within_cycle=true`
  - `evidence_source=research`
  - `forward_wait_blocks_research=false`
  - snapshot key `history-snapshot-2026079-d9aae1656126e465`
- `dehps forward-runtime run --max-checks 2 --interval-seconds 0`
  reported `forward_waiting`.

Installed user services:

```bash
systemctl --user status dehps-research-runtime.service
# Active: active (running)

systemctl --user status dehps-forward-runtime.service
# Active: active (running)

systemctl --user status dehps-draw-sync.timer
# Active: active (waiting)
```

Runtime state after service start:

- Research runtime: `active=true`, `status=research_running`,
  `forward_wait_blocks_research=false`.
- Research execution: Pattern Discovery wrote `83` patterns, `50` features,
  `30` strategies, and submitted
  `research-proposal-pattern-440767addb399de1`.
- Resource utilization smoke: the 12-lane resident service reached 17 tasks,
  ~423 MB peak memory, and more than 100 CPU seconds in the first 42 seconds.
  Cycle audit showed `parallel_lanes=12`, `max_workers=12`,
  `discovered_count=996`, `feature_count=600`, and `strategy_count=360`.
- Learning smoke after serial lane persistence: a 4-lane cycle persisted four
  windows and produced `repository_delta.pattern_count=57`,
  `repository_delta.feature_count=32`, and
  `repository_delta.strategy_count=26`; proposal submission was skipped because
  an open pattern proposal already existed.
- Forward runtime: `active=true`, `status=forward_waiting`.
- Draw sync watch: `status=ok`, `resume_on_event=false`.
- Legacy supervisor process: none.
- `dehps-training-supervisor.service`: not found/disabled.
- `dehps-training-resume.service`: not found/disabled.

## Smoke plan

1. Confirm no legacy training supervisor process is running.
2. Confirm stale legacy PID files before cleanup.
3. Install user systemd units and reload the user daemon.
4. Start research runtime, forward runtime, and draw-sync timer.
5. Run at least 10 research cycles and verify:
   - cycle count increases;
   - snapshot remains stable within each cycle;
   - `forward_wait_blocks_research=false`;
   - evidence source is `research`;
   - forward runtime remains `forward_waiting`;
   - legacy supervisor process count remains zero.
