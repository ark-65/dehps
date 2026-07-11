# Training Compute Parallelization v1

## Primary Goal

Reduce wall-clock time for the existing training loop by parallelizing independent Dynamic KDJ target evaluations and increasing the supervisor's configurable CPU worker default, while preserving exact model outputs and scientific guards.

## Non-Goals

- Do not change models, features, candidate budgets, sort order, objective components, weights, historical windows, or promotion rules.
- Do not count faster computation as predictive progress.
- Do not claim GPU participation without a verified compute backend.
- Do not install unpinned accelerator dependencies into the training environment.

## Task Frame

Run `20260711-091651` showed low aggregate CPU use outside existing target pools and two serial Dynamic KDJ sweeps per round. The 80-target Dynamic sweep took about 122 seconds and the 9-target Near sweep about 16 seconds. Each target reads the same immutable ranked-universe matrix and produces an independent result, so the narrow performance hypothesis is that ordered target-level threading can use NumPy's native kernels concurrently without changing results.

## Historical Boundary

Gauss and Riemann below are historically inspired verification and structural lenses, not literal minds or complete reconstructions.

- Hardware: Intel Core Ultra 7 155H, 22 logical CPUs, 30 GiB RAM, Intel Arc integrated graphics.
- Python: 3.14 virtual environment, NumPy 2.4.6 with OpenBLAS; BLAS threads remain capped at one per worker.
- GPU visibility: `/dev/dri/renderD128` is present.
- GPU compute backends: no OpenVINO, PyTorch/XPU, TensorFlow, JAX, `dpctl`, `dpnp`, ONNX Runtime, or PyOpenCL in the project environment; no OpenCL/Level Zero loader was found.
- Canonical training boundary remains issue `2026078`, expanding 900/100 with 80/20 search/frozen isolation.

## Gauss Pass

Strongest claim: the serial and parallel paths perform the same deterministic per-target function and consume results in original target order. Unit validation compares selected strength, selected summary, rows, ranks, and target ordering across one and three workers.

Weakest assumption: target-level NumPy calls remain thread-safe for the immutable shared matrix. The live round is the runtime check; any exception, metric drift, or ordering change falsifies acceptance.

Proof obligation: preserve strength order within a target, target order across the evaluation window, one BLAS thread per target worker, and exactly the same leakage and result aggregation logic.

## Riemann Pass

Strongest claim: the computation is a product over independent target slices sharing one read-only universe. Parallelizing that product changes scheduling, not the mathematical map from history and configuration to ranks.

Weakest assumption: more workers always improve throughput. The matrix operations are memory-bandwidth-heavy and the CPU mixes performance and efficiency cores, so scaling must be measured rather than inferred from core count.

Structural test: compare phase-level elapsed time and whole-round duration under unchanged work. Keep worker count configurable because saturation may shift with other host workloads.

## Cross-Review

- Gauss requires exact result equivalence and rejects speed-only acceptance if metrics or target order change.
- Riemann identifies the Dynamic/Near target dimension as the safe parallel axis over a shared immutable matrix.
- Both reject nested BLAS oversubscription; `--cpu-threads 1` remains unchanged.
- Both treat Intel Arc as unavailable until a project-supported backend passes its own deterministic feasibility test.

## Disagreement

Gauss prefers the conservative existing 10 workers until a benchmark proves a higher count. Riemann permits using more independent target slices because the host exposes 22 logical CPUs. The shared measured choice is a configurable default of 16: it gave a small full-evaluation improvement and a large Dynamic/Near improvement, while leaving six logical CPUs for the desktop, database, and orchestration.

## Synthesis

`dynamic_kdj_strength_sweep_training_summary` now accepts a worker count, evaluates target slices with an ordered `ThreadPoolExecutor`, and reports `target_worker_count` plus `elapsed_seconds`. The supervisor passes its normalized worker count to both Dynamic and Near sweeps and logs their phase timings. `ensure_training_supervisor.sh` exposes `DEHPS_TRAINING_WORKERS`, defaulting to 16. Hourly self-iteration is instructed to check compute timing and backend availability without conflating speed with model strength.

## Baseline Audit

Unmodified run `20260711-091651`, round 2:

- 100-target full evaluation: `60.9s` with 10 workers;
- serial target inversion and post-evaluation segment remained about `122s` before Dynamic began;
- Dynamic KDJ 80-target sweep: about `122s`;
- Near Dynamic KDJ 9-target sweep: about `16s`;
- round start `09:25:33`, strategy-memory completion `09:30:54`: about `321s`.

The model outputs were Dynamic exact `[2,3,3]`, red5 Top10k `28`, and Near exact `[0,0,0]`.

## Implementation

The thread pool shares the immutable ranked-universe matrix and maps target indexes in order. Per-target dynamic configuration construction, leakage metadata, rank calculation, and target payload construction stay together; aggregation runs serially in target order. This avoids copying the roughly 1.1-million-row matrix into a new accelerator representation and avoids nested process-pool serialization.

## Live Verification

Fresh run `20260711-093253`, PID `3331695`, started with the updated code and 16 workers. Durable round 1 completed without runtime errors:

- full evaluation: `54.3s`, versus the comparable 10-worker range of `55.8–60.9s`;
- Dynamic KDJ: `35.481s` with 16 workers, versus about `122s` serial, approximately `3.4x` faster;
- Near Dynamic KDJ: `3.778s` with 9 workers, versus about `16s`, approximately `4.2x` faster;
- whole round: about `225s`, versus `321s`, approximately `30%` lower wall time;
- Dynamic outputs remained exact `[2,3,3]`, red5 Top10k `28`;
- Near outputs remained exact `[0,0,0]`;
- decision surface remained `objective_tiebreak_tradeoff`; strategy remained observe-only with promotion disabled;
- round boundary reached `target_complete_round_recorded`, advisors were current, prefilter isolation passed, and forward evidence remained `0/20`.

The 16-worker full-evaluation stage scaled only modestly, consistent with memory-bandwidth and hybrid-core limits. The accepted gain is therefore the previously serial Dynamic/Near path, not a claim of linear CPU scaling.

## Falsification

Reject the change if parallel and serial summaries differ, target order changes, any Dynamic/Near live output drifts under identical inputs, memory pressure destabilizes the supervisor, or whole-round timing regresses repeatedly. Reduce `DEHPS_TRAINING_WORKERS` if host contention or memory pressure appears. GPU enablement remains rejected until a pinned backend can enumerate Intel Arc, pass deterministic CPU/device equivalence on representative rank kernels, and demonstrate end-to-end benefit after transfer overhead.

## Validation

- targeted Next Candidates and supervisor suites: `176 passed`;
- serial/parallel Dynamic KDJ result-equivalence test: passed;
- Python compile and diff checks: passed;
- fresh live supervisor round: passed with phase timings and unchanged outputs;
- full worker suite: `500 passed`.

## Next Verification

Profile the approximately 132-second target-inversion/post-evaluation segment, now the dominant round bottleneck, before changing it. For GPU, first create a separate pinned Intel Arc feasibility probe; do not migrate the small NumPy MLP merely because a device exists, since its dataset is too small to justify transfer and runtime overhead. Continue treating model progress separately: the current learning loop still needs the predeclared objective-component residual control and future frozen/forward evidence.
