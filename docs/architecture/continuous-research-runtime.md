# Continuous Research Runtime

Round 30 separates DEHPS into two independent runtimes:

```text
Draw Sync
   │
   ▼
History Database
   │
   ├── History Snapshot ──► Continuous Research Runtime
   │                         ├── proposal generation
   │                         ├── pattern mining
   │                         ├── feature synthesis
   │                         ├── strategy synthesis
   │                         ├── isolated experiments
   │                         └── research evidence
   │
   └── Forward Queue ─────► Forward Validation Runtime
                             ├── wait for new issue
                             ├── forward validation
                             ├── forward evidence
                             └── promotion review
```

The key invariant is simple: research may run forever on frozen historical snapshots, but promotion may only use forward evidence.

## History snapshots

Every research cycle starts by taking a `HistorySnapshot`:

- `latest_issue`
- `issue_count`
- `history_fingerprint`
- `snapshot_key`

The snapshot is immutable for the cycle. If draw sync adds a later issue during the cycle, the cycle continues on the old snapshot. Snapshot rotation is deferred until the next cycle boundary.

## Continuous research

`apps/worker-python/dehps/research_runtime/` contains:

- `runtime.py`: research runtime state and one-cycle execution.
- `scheduler.py`: selects research work without consulting forward readiness.
- `worker.py`: runs bounded batches of research cycles.
- `resident.py`: runs the continuous research runtime as a long-lived worker with
  PID, heartbeat, cycle log, snapshot, and budget audit.
- `queue.py`: allows only research actions.
- `snapshot.py`: creates immutable history snapshots and rotation decisions.
- `budget.py`: separates research CPU/memory from forward CPU/memory.

Research statuses:

- `research_running`
- `research_sleep`
- `research_budget_exhausted`
- `research_waiting_resources`

Research queue actions:

- `proposal_generation`
- `pattern_mining`
- `feature_synthesis`
- `strategy_synthesis`
- `isolated_experiment`
- `engineering_planning`
- `evidence_aggregation`

There is no `waiting_for_forward_issue` state in the continuous research runtime.

## Forward validation

`apps/worker-python/dehps/forward_runtime/` contains:

- `runtime.py`: maps forward reconciliation into forward runtime state.
- `queue.py`: allows only forward actions.
- `service.py`: read/status facade.
- `resident.py`: keeps the forward runtime alive as a heartbeat worker while it
  waits for new draw events.

Forward statuses:

- `forward_waiting`
- `forward_ready`
- `forward_running`

Forward queue actions:

- `pending_forward`
- `waiting`
- `forward_validation`
- `promotion`

Forward may wait. That wait never blocks research scheduling.

## Resident deployment

Round 31 makes the continuous research runtime the resident worker. The legacy
training supervisor is no longer the owner of continuous research.

Expected resident units:

- `dehps-research-runtime.service`
- `dehps-forward-runtime.service`
- `dehps-draw-sync.timer`

Legacy unit:

- `dehps-training-supervisor.service` must stay disabled.

Resident research writes:

- `runtime/logs/research-runtime.pid`
- `runtime/logs/research-runtime-state.json`
- `runtime/logs/research-runtime-cycles.jsonl`

Resident forward writes:

- `runtime/logs/forward-runtime.pid`
- `runtime/logs/forward-runtime-state.json`

The research resident fails closed if a legacy process matching
`run_training_supervisor|training_supervisor` is active. This prevents the legacy
supervisor and research runtime from consuming the same research queue.

Draw sync no longer starts the legacy training resume path by default. The
packaged draw-sync unit runs a resident `draw-sync watch --no-resume-on-event`
process. The forward runtime remains resident while research observes history
changes only at cycle boundaries through snapshot rotation.

## Evidence source boundary

Evidence now carries a source:

- `research`
- `forward`

Research evidence can support hypotheses, guide pattern discovery, and prioritize more research. It cannot promote production behavior. Promotion validation requires `forward` evidence.

## CPU and memory split

The runtime budget model keeps research and forward resources separately configurable. The default planning split is:

- research CPU: 12
- forward CPU: 4
- total memory: 20 GB
- research memory: 18 GB
- forward memory: 2 GB

These numbers are policy defaults, not automatic resource provisioning.

## Einstein pass

- Core question: can DEHPS keep generating historical research while preserving strict future validation?
- Invariant: forward evidence remains the only promotion-eligible evidence.
- Hypothesis: immutable snapshots prevent mid-cycle leakage while allowing continuous research.
- Measurement: research produces queue items while forward reports `forward_waiting`.
- Failure mode: research evidence is accidentally treated as forward evidence or a cycle mutates its history surface.
- Next experiment: run continuous cycles under a waiting forward runtime, then inject a later snapshot and verify rotation only at the next cycle boundary.
