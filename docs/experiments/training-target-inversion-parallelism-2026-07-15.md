# Target-weight inversion parallelism — 2026-07-15

## Round contract

- Primary goal: parallelize independent per-target inversion work while preserving the serial result sequence and payload exactly.
- Non-goals: no score, feature, target selection, delta generation, aggregation, advisor budget, model, promotion gate, or forward-prediction change.
- Baseline: commit `fc0aa5fae5712c950021a2aa44e28c1fa80df941`, 28 generated configurations, 100 inversion targets, 8 delta candidates per target, 16 configured workers.

## Task frame and historical boundary

The question is an execution-geometry question: can independent target inversions use the configured worker budget without changing their mathematical outputs? The Gauss and Riemann passes below are historically inspired verification lenses, not literal minds or complete reconstructions.

## Gauss pass: verification

- Strongest claim: every target call depends only on its target, immutable history prefix, immutable ranked universe, common base configuration, and fixed bounds. Reconstructing results by original target position preserves aggregation order.
- Weakest assumption: forked NumPy calculations with one BLAS thread remain bitwise identical to the serial path.
- Required checks: exact object equality for serial versus out-of-order parallel completion; unchanged target count/order; unchanged aggregate/config hashes; single-worker fallback; incomplete-worker-result failure.
- Boundary: this verifies computational equivalence only, not predictive value.

## Riemann pass: structure

- Strongest claim: the stage is a family of independent target fibers. The natural parallel coordinate is target, not an inner score-vector operation.
- Weakest assumption: process startup, serialization, and copy-on-write memory do not erase the latency gain at 100 targets.
- Required checks: live wall time, actual active workers, peak RSS, and swaps against the same baseline.
- Boundary: the fiber description is a modern structural analogy, not a historical theorem of Riemann.

## Cross-review, disagreement, and synthesis

Gauss requires ordered reconstruction and exact output comparison; Riemann requires measuring the whole stage rather than assuming that more processes help. The unresolved risk is peak memory: parallel target matrices may reduce latency while increasing resident memory.

Smallest shared conclusion: use a bounded target-level process pool, cap workers by valid targets, use fork/copy-on-write where available, report progress from the parent, preserve the ordered serial payload, and reject promotion if a live two-round run exceeds the existing 20 GiB budget or swaps.

## Implementation

- `invert_targets_for_summary` now accepts a worker count and optional parent progress callback.
- Valid targets receive stable sequence positions; workers may finish out of order, but the parent reconstructs the original order before aggregation.
- Worker initialization shares the ranked matrix, history, base config, and immutable parameters; tasks carry only target coordinates.
- One worker retains the same execution path and result ordering.
- Supervisor telemetry reports the configured/effective inversion workers and target progress.

## Validation

- Synthetic out-of-order worker test: parallel rows equal serial rows and retain original target order.
- Real NumPy matrix test: serial and two-worker `TargetWeightInversion` objects are exactly equal.
- Focused inversion/supervisor/telemetry regression suite: 176 passed.
- Python compile checks: passed.
- Full Python worker suite: 959 passed.
- Live two-round observability-only comparison: pending merge and separately approved Operator execution.

## Live acceptance gate

Using the same 28/100/8/16 baseline, two rounds must retain exact database invariance and complete without swaps or exceeding 20 GiB. The comparison will report inversion speedup, total wall time, CPU use, RSS, worker progress, and any result/hash mismatch. Configuration, neural, and inversion budgets remain frozen until this gate passes.
