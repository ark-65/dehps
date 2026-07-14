# Round 30 - Decouple Continuous Research From Forward Validation

## Goal

Split DEHPS into two independent pipelines:

- Continuous Research Pipeline
- Forward Validation Pipeline

Research should continue on immutable history snapshots while forward validation waits for new开奖 observations. The forward gate remains strict and remains the only path to promotion evidence.

## What changed

- Added `dehps.research_runtime` with immutable history snapshots, research runtime statuses, queue actions, budget scheduling, cycle execution, and a worker.
- Added `dehps.forward_runtime` with forward-only statuses and queue actions.
- Added evidence source semantics: `research` and `forward`.
- Added a promotion evidence-source validator that rejects research evidence for promotion review.
- Added CLI status commands:
  - `dehps research-runtime status`
  - `dehps research-runtime once`
  - `dehps forward-runtime status`

## Important boundary

Round 30 does not cancel the forward gate. It changes what the gate can block:

- Forward gate can block forward validation and promotion.
- Forward gate cannot block continuous research work.

Research evidence is useful for prioritization and hypothesis refinement. It is not promotion evidence.

## Validation

New tests:

- `test_snapshot_rotation.py`
- `test_research_runtime.py`
- `test_forward_runtime.py`
- `test_runtime_decoupling.py`
- `test_parallel_runtime.py`
- `test_budget_scheduler.py`
- `test_evidence_source_boundary.py`

Completed commands:

```bash
cd apps/worker-python
.venv/bin/python -m pytest -q
DB_PORT=1 .venv/bin/python -m pytest -q
```

Results:

- Worker: `934 passed in 28.78s`
- Worker with `DB_PORT=1`: `934 passed in 25.14s`
- CLI smoke: `dehps research-runtime status` returned `research_running`
- CLI smoke: `dehps forward-runtime status` returned `forward_waiting`
- CLI smoke: `dehps research-runtime once` emitted a `pattern_mining` queue item with `forward_gate_ignored_for_research=true`

## Smoke expectation

When forward is waiting for `2026080`, `forward-runtime status` may report `forward_waiting`, while `research-runtime once` still emits a research queue item such as `pattern_mining` on the frozen `2026079` snapshot.

If `2026080` is synced during a research cycle, the current cycle keeps its old fingerprint. The next cycle rotates to the new snapshot.
