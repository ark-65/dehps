# Training roadmap completion audit — 2026-07-15

## Round contract

- Primary goal: audit and close every implementation item in the training-throughput and forward-learning roadmap from `pasted-text-1.txt`.
- Non-goals: no new score, feature formula, weight, model family, candidate source, promotion threshold, data window, TopN, worker-count, or production strategy change.
- Authorization: Agent Request `engineering-close-training-roadmap-observability-6fa6582` (request id 97, execution id 20).
- Starting commit: `6fa6582`.

## Einstein pass

- Core question: does the system now execute and expose the complete training/forward loop, or does higher CPU activity merely hide missing evidence?
- Invariants: legal red-six space remains 1,107,568; ranked filtered space remains 1,105,506; outcome data is unavailable before its issue; search, frozen validation, and forward evidence remain distinct; historical lift cannot promote a production strategy by itself.
- Null model: all legal red-six combinations are equiprobable before a draw. DEHPS ranking is a transparent structural-scoring hypothesis, not a probability claim.
- Measurement: stage timing and workers, exact logical config-target pairs, mmap identity, durable prediction/evaluation rows, feature-ablation isolation, promotion cohort invariants, tests, and bounded live resource observations.
- Failure mode: declaring the roadmap complete from green unit tests while the merged launcher, durable database, prediction product, or production watchdog contradicts it.
- Decisive experiment: merged-code run `20260715-150735` required persisted schedule details, a five-completed-target progress cadence, zero swap, and unchanged durable state.

## Requirement audit

| Roadmap item | Current implementation | Authoritative evidence | Status |
| --- | --- | --- | --- |
| 1. Stage/worker/config/target monitoring | `RoundStageTracker` records current/completed stages, durations, active workers, generated/selected configs, target progress, failure details, and the evaluation schedule geometry. | `test_round_observability.py`; merged-code run `20260715-150735` preserved all stages, details, and 16-worker progress. | Complete. |
| 2. Forward evaluation auto-persistence | Draw sync evaluates pending runs after changed and unchanged sync attempts; structured failures retry; due failures block training resume. | `ForwardEvaluationService`, scheduler tests, compensation CLI, PR #114. | Complete. |
| 3. Fixed latest-prediction product | Durable three-line view includes issue, as-of issue, generation time, lifecycle status, source/viewer commit, model version, parameter version, prediction/source run, round, TopN, and consensus. | `show_latest_prediction.py`; `test_latest_prediction.py`; live read-only issue `2026081` output. | Complete. |
| 4. Local mmap universe/features | Versioned local `.npy` arrays are opened read-only with mmap; atomic build path validates schema/rules/counts and excludes PostgreSQL from the hot static-matrix path. | `walk_forward.py`; mmap tests; hot cache open 0.003–0.004 seconds; 1,107,568 source / 1,105,506 ranked / 2,062 excluded. | Complete. |
| 5. Config × target evaluation work | The logical grid is every selected config × every target. Scheduling uses target shards because each worker computes the full config dimension in one vectorized matrix multiply; status exposes exact pair count and names this mode `target_shard_vectorized_config_grid`. | Serial/parallel equality tests; schedule contract test; run `20260715-150735` persisted 26 × 100 = 2,600 pairs with 16 workers. | Complete without redundant per-config feature recomputation. |
| 6. Larger bounded experiment budget | Launcher defaults are 96 configs, 20% neural share, 22% Weight KDJ, 8×100×12 inversion, 16 workers, one BLAS thread, and 24 GiB. | Launcher contract tests; controlled 28/48/96 run; merged-code run `20260715-150735`. | Complete. |
| 7. Feature-family ablation | Deterministic leave-one-family-out tool evaluates full and six ablated models on identical search/frozen issues; it is diagnostic-only and cannot promote. | `run_feature_ablation.py`; feature-ablation tests/report and runtime artifact. | Complete. |
| 8. Champion/challenger promotion | Prospective fixed challenger, 20 paired unseen issues, frozen config identity, leakage/duplicate/completeness checks, existing PromotionGate, consecutive-loss bound, atomic champion checkpoint, and idempotent terminal decisions. | Forward-promotion tests/report; production schema; zero currently eligible cohorts. | Complete and fail-closed. |

## Deliberate deviations from the draft recommendation

The literal 32-hidden-unit / 500-epoch default was tested in bounded run `20260715-142155`. Process `VmSwap` rose to 87,740 KiB, so the configuration failed the declared zero-swap gate. The accepted default is 8×120 while retaining 96 configurations and a 20% neural candidate share. Run `20260715-144158` completed with six zero-swap samples, 96 generated configs, 26 selected configs, and 1,615% aggregate CPU.

The process pool does not enqueue 2,600 independent `(config_hash, target_issue)` jobs after a 26×100 selection. That would recompute target statistics and static feature components once per config. Instead, it enqueues 100 target shards and evaluates all 26 configs in a vectorized matrix operation inside each shard. This covers the same 2,600 logical pairs, keeps 16 workers active, shares the read-only mmap/fork-COW universe, and is the measured lower-overhead realization of the requested work geometry.

## Forward and production boundary

- Issue `2026081` remains `waiting_draw`, as-of `2026080`, with three required runs and 30,000 durable candidates.
- No continuous supervisor is active because the watchdog correctly parked at `watch_forward_wait_ready:2026080->2026081`.
- Forward-promotion cohort and champion counts are both zero; no historical candidate is eligible for prospective promotion.
- Issue `2026080` actual-red audit found generation and hard filtering passed, initial rank 298,492, and model ranks 643,938 / 663,994 / 696,201. The miss was caused by model scoring, not export truncation.

## Validation and live acceptance

Pre-merge validation:

```text
bash -n scripts/ensure_training_supervisor.sh
15 focused prediction/stage/launcher tests passed in 0.40s
982 full worker tests passed in 34.06s
live read-only latest-prediction display passed for issue 2026081
```

Operator Request `operator-validate-training-roadmap-c164d98` (request id 98, execution id 21) ran commit `c164d98` in bounded observability-only mode. Supervisor run `20260715-150735` completed one round with:

- 96 generated and 26 selected configurations;
- 100 target shards, 2,600 exact config-target logical pairs, and 16 active main-evaluation workers;
- main evaluation 66.072 seconds and target inversion 50.730 seconds;
- dynamic / near-dynamic training 42.506 / 4.593 seconds;
- 277.87 seconds wall time and 1,616% CPU;
- maximum RSS 10,096,652 KiB; four process-tree samples and `/usr/bin/time` all reported zero swap;
- read-only mmap cache hit in 0.003 seconds;
- observability-only persistence skipped, with durable training rows, three issue-2026081 runs, and 30,000 candidates unchanged.

`--progress-interval 5` means emit after every five completed targets, plus the first and final target. The observed sequence was `1, 5, 10, …, 95, 100`; it is not a five-wall-clock-second timer.

The normal watchdog was invoked after acceptance and parked again at `watch_forward_wait_ready:2026080->2026081`. No continuous supervisor was left running on unchanged history.

## Completion decision

All eight roadmap items are implemented and verified against current code, tests, durable database state, and merged-code runtime behavior. Operational completion does not change the scientific boundary: no forward draw has yet evaluated issue `2026081`, the current promotion cohort is empty, and neither CPU utilization nor historical results establish predictive lift.
