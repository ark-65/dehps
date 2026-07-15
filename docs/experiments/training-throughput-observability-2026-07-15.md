# Training throughput observability and prediction display — 2026-07-15

## Round contract

- Primary goal: make the existing training pipeline's real execution stages observable and provide a fixed, durable three-line forward-prediction display.
- Non-goals: no new scoring feature, weight, model, advisor, promotion rule, candidate filter, or production restart; no unmeasured jump from 28 to 96 configurations.
- Historical boundary: Gauss and Riemann are used only as diagnostic lenses. Historical lift and CPU utilization are not treated as proof of predictive improvement.

## Evidence before changes

The active supervisor run `20260714-213019` had already completed round 8 and was parked waiting for issue `2026081`. It was not an underutilized live training round.

Round 8 showed:

- prefilter: 28 generated configurations to 19 selected, 20 targets, 16 workers, 9.065 seconds;
- main evaluation: 100 targets, 16 workers, 56.6 seconds;
- unlabelled interval after target 100: 124 seconds before the target-inversion/diagnostic log line;
- dynamic KDJ: 16 workers, 39.156 seconds;
- near-dynamic KDJ: 9 workers, 4.394 seconds.

The ranked-universe cache already existed at `data/output/cache` and occupied 80.13 MiB. A direct load check returned a normal `ndarray`, not `numpy.memmap`; opening the hot `.npz` took about 0.005 seconds and accessing `numbers` about 0.0045 seconds. Linux `fork` target workers already inherit the parent matrix. This makes an immediate cache-format rewrite lower priority than identifying the 124-second unlabelled interval.

## Gauss pass

Strongest objection: the proposal to raise the per-round budget to 96 is not yet supported by a controlled timing or predictive comparison. The observed 28-configuration round did not reduce to two configurations; it retained 19. The known parallel sections already used 16 workers. Increasing the hypothesis family before measuring the serial post-evaluation interval increases multiple-testing and runtime cost without proving that the extra candidates survive prefiltering or improve frozen/forward results.

Exact obligations retained:

- legal red-six sample space remains 1,107,568;
- search and frozen/forward evidence remain separate;
- no neural hidden-size/epoch/budget promotion without an ablation against the same target windows and null discipline;
- no configuration-budget promotion without elapsed time, memory peak, survivor count, and frozen/forward evidence.

## Riemann pass

Strongest objection: “CPU utilization” was treating the round as one homogeneous space. The observed pipeline is a sequence of differently shaped spaces: candidate composition, target-parallel prefilter, target-parallel main evaluation, serial/unknown diagnostics, target inversion, dynamic regression, near-dynamic regression, persistence, and candidate refresh. Optimizing the already-parallel target manifold cannot explain or remove a serial post-evaluation gap.

The smallest structural repair is to expose each stage and its worker/config/target geometry before changing task granularity to configuration × target.

## Cross-review and disagreement

- Agreement: add stage telemetry and a stable prediction view first; preserve leakage and promotion gates.
- Gauss concern: 96 configurations and 32×500 neural settings enlarge the tested family before there is paired forward evidence.
- Riemann concern: configuration × target decomposition may add scheduling and serialization overhead when target-parallel work already saturates the configured 16 workers.
- Unresolved: whether the 124-second gap is mostly normalization/control diagnostics or target inversion. The new stage telemetry is the next verification.

## Implemented

### Round stage telemetry

`round_execution` is now published alongside, rather than over, `latest_progress`. It records:

- current stage and round;
- active worker count;
- generated and selected configuration counts;
- completed/total target progress;
- completed-stage durations;
- target-inversion limits;
- structured failure type and message.

Stage transitions are also emitted as `training_stage` log records. The stages are candidate generation, prefilter, main evaluation, post-evaluation diagnostics, target-weight inversion, near-miss inversion, dynamic KDJ, near-dynamic KDJ, round postprocessing, persistence/prediction refresh, and completion.

### Latest prediction product view

`scripts/show_latest_prediction.py` and the worker-local equivalent read durable `forward_prediction_runs` / `forward_prediction_candidates` rows. The output includes target issue, as-of issue, generation time, aggregate lifecycle status, prediction-source commit, viewer commit, source run and round, Top 10 for each of the three lines, and explicitly defined cross-line consensus numbers. New snapshots persist their source commit in metadata; legacy snapshots truthfully display `not_recorded` instead of attributing the viewer's code to an older prediction.

Consensus means a red number appears somewhere in the Top 10 of every available line. The occurrence count is descriptive only and is not a calibrated probability.

The live read-only verification returned issue `2026081`, as-of `2026080`, all three expected lines, 10 candidates per line, and aggregate status `waiting_draw`.

## Recommendation audit

| Recommendation | Result in this round | Evidence / next gate |
|---|---|---|
| Stage, worker, config, target observability | Implemented | Unit/contract tests pass; requires a fresh authorized round for real timings. |
| Forward evaluation closure | Already implemented and merged in PR #114 | Durable pending/evaluated lifecycle and idempotent compensation path exist. |
| Fixed latest-prediction view | Implemented | Verified against the live durable snapshot for `2026081`. |
| mmap/static cache | Partially pre-existing; no rewrite | Cache hit is fast, but `.npz` arrays are not mmap. Revisit only if cold-start/RSS evidence makes it material. |
| Configuration × target parallelism | Not added | Existing target-parallel pool already uses 16 workers; stage timing must identify the serial bottleneck first. |
| Raise configurations to 96 | Not promoted | Requires controlled 28/48/96 timing, RSS, survivor, frozen, and forward comparison. |
| Feature ablations | Not started | Separate research/acceptance round; no new feature logic in this consolidation round. |
| Champion/challenger auto-promotion | Existing gates preserved; not broadened | Current diagnostics say `noise_risk` and require frozen/forward lift. No forward evidence supports a broader automatic promotion. |
| Neural budget 0.20, hidden 32, epochs 500 | Not promoted | Must be an isolated ablation; current defaults remain 0.10, 8, 120. |
| Target inversion 8×100×12 / 24 GiB | Not promoted | First identify target-inversion stage time and peak memory with current 4×100×8 / 20 GiB settings. |

## Validation

- Focused telemetry and prediction tests: 4 passed.
- Training supervisor and watch regression suite: 280 passed.
- Full Python worker suite: 952 passed.
- Live durable prediction display: succeeded for issue `2026081` without writes.
- Python compile checks: passed.

Live 1–2-round validation is not executed in this round because the repository contains no approved `operator_isolated_run` or `operator_supervisor_restart` Agent Request. Starting or replacing the production supervisor would violate the project operation boundary. The next authorized run should compare stage durations for two completed rounds before any budget increase.
