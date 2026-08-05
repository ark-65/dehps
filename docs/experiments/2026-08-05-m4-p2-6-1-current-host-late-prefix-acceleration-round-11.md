# M4 P2.6.1 current-host late-prefix acceleration — Round 11

Date: 2026-08-05

Role: Engineering Agent

Agent Request: `engineering-m4-p2-6-1-current-host-late-prefix-acceleration-round-11-20260805` (#267)

Execution: #188

Production impact during Engineering: none

## Primary goal

Reduce the progressively increasing exact fold cost of the frozen P2.6.1
workload on the current Intel Core Ultra 7 155H host. Accept a candidate only
when a warm, interleaved, late-prefix end-to-end benchmark is at least 1.10x
faster and immutable scientific outputs remain exact.

## Non-goals

- No second-host deployment, packaging, database migration, or worker tuning.
- No workload, fold, refit cadence, solver, tolerance, C, model, Gate, or
  Promotion change.
- No statistical result payload read and no Evidence Progress increment.
- No production Supervisor mutation under Engineering authority.

## Einstein pass

- **Core question:** which computation grows with the prefix even though the
  frozen output identity does not require it on the production no-trace path?
- **Invariant:** sample space, manifest, cells, replicates, folds, probe order,
  features, targets, seeds, estimator parameters, probabilities, probe states,
  checkpoints, settlements, journal bytes, task digest, and execution id.
- **Hypothesis:** exact trace-view serialization and repeated tree-prefix work
  are avoidable runtime costs, not scientific computations.
- **Measurement:** component CPU profile, exact-versus-compact view benchmark,
  five consecutive terminal LONG folds, and full FORWARD_61 result/journal
  replay.
- **Failure:** reject on any output difference, speedup below 1.10x, source
  boundary failure, memory regression, or production-only special case that
  bypasses target-access guards.
- **Smallest experiment:** keep the exact identity path when trace capture is
  enabled; use a compact internal identity otherwise; retain exact fitted
  preprocessors across folds and an eight-entry tree LRU inside one replicate.

## Result-blind baseline profile

Terminal LONG fold, NULL cell, replicate 0, 6,961 training issues, 229,713 rows,
38 features. Numerical libraries were single-threaded. The diagnostic process
was pinned to CPU 21 at niceness 19 while the production Supervisor remained
active. Process CPU time was used so scheduler wait was not counted.

| Component | Warm CPU seconds | Share of four-probe path |
|---|---:|---:|
| exact liblinear | 8.12 | 60.8% |
| exact sparse shallow tree | 4.23 | 31.7% |
| exact Bernoulli NB | 1.02 | 7.6% |
| empirical/prediction overhead | 0.05 | 0.4% |
| four-probe total | 13.37 | 100% |

The tree's 4.26-second preparation split into 0.824 seconds of repeated
model-prefix scaling, 0.669 seconds of dense-to-CSC conversion, 1.753 seconds
of `tree.fit`, 0.090 seconds of threshold restoration, and approximately 0.668
seconds of calibration and state construction.

The production evaluator also rebuilt the exact public train-view identity on
every fold. At the terminal LONG prefix this took a median 3.109 CPU seconds,
although that digest is consumed only by optional trace capture.

## Implemented acceleration

1. `StrictPriorFeatureCache.build_runtime_train_feature_view` now has two
   explicit modes:
   - trace capture: unchanged exact public identity and payload;
   - no trace: compact internal-only identity with NumPy-backed values and
     targets, no repeated 229,713-row JSON/SHA256 serialization.
2. The compact path retains a vectorized row-order and authorized-buffer guard;
   it does not weaken target-access or number-event validation.
3. Exact fitted preprocessors are retained by contiguous issue-prefix identity
   for the lifetime of one replicate. A tree's 80% model prefix can reuse the
   exact scaler calculated by an earlier full outer fold.
4. Exact sparse trees use an eight-entry per-replicate LRU. Because
   `floor(0.8N)` repeats once per five outer folds, the repeated fold reuses the
   identical tree while still refitting the changed Platt calibration split.
5. All caches are owned by one `StrictPriorFeatureCache`, so no object crosses
   dataset or replicate identity.

## Performance evidence

### Exact train-view operator

| Sample | Exact identity CPU s | Compact identity CPU s | Speedup |
|---:|---:|---:|---:|
| 1 | 3.156 | 0.0232 | 135.95x |
| 2 | 3.109 | 0.0220 | 141.39x |
| 3 | 2.970 | 0.0217 | 137.10x |

Both exact and compact digests were stable across samples. This microbenchmark
was diagnostic only; acceptance used the full fold benchmark below.

### Five consecutive terminal LONG folds

Baseline and candidate were interleaved. Baseline used the exact trace-view
identity and disabled cross-fold reuse; all estimator code and inputs were
otherwise the same. Candidate scaler states for the tree model prefixes were
warmed exactly as earlier outer folds would have produced them. The five-fold
window covers one complete `floor(0.8N)` repetition cycle.

| Fold | Training issues | Tree issues | Baseline CPU s | Candidate CPU s | Speedup | Exact state/probability |
|---:|---:|---:|---:|---:|---:|---|
| 6057 | 6,957 | 5,565 | 16.107 | 12.191 | 1.321x | yes |
| 6058 | 6,958 | 5,566 | 15.857 | 11.886 | 1.334x | yes |
| 6059 | 6,959 | 5,567 | 15.580 | 12.035 | 1.295x | yes |
| 6060 | 6,960 | 5,568 | 16.140 | 12.332 | 1.309x | yes |
| 6061 | 6,961 | 5,568 | 16.018 | 9.768 | 1.640x | yes |

- Baseline median: 16.018 CPU seconds.
- Candidate median: 12.035 CPU seconds.
- Aggregate speedup: **1.369173x**.
- Aggregate CPU-time reduction: **26.96%**.
- Acceptance threshold: 1.10x.
- All four probe state trees and all probability binary64 values were exact on
  every fold.

## Exact replay

The production-like no-trace evaluator completed all 61 FORWARD_61 folds and
was checked against the registered literal Round 6 oracle:

- result float64-tree digest:
  `e239c79849894d269dc8d33997c8a13ec1e6dc75f40c7f1bbd614105de9370b4`
- registered expected result digest: identical
- checkpoint journal SHA256:
  `5ad68b8a9b6e97067d692fdf82f101520e261d2451262591e5ee178b4966db24`
- registered expected journal SHA256: identical
- journal byte count: 40,250
- status: `EXACT_COMPACT_PRODUCTION_REPLAY_VERIFIED`
- replay directory:
  `runtime/round11-compact-replay.svjgxu`

No statistical result payload was inspected. The replay compared immutable
identity digests and journal bytes only.

## Source governance

- Shared frozen source set: unchanged.
- Independent oracle source set: unchanged.
- Approved acceleration source set:
  `2616176e39473ac1cfac7a716ee824f46f6012bd61aea6cb1d6d46c13ca8a79f`
- Audit orchestration source set:
  `6663d1bb8aa31d215f558f9973199b9bb2df4511894e68c6dacf9d3fa5ee8296`
- Superseding runtime audit plan v1.1.5:
  `e2bfb82be29bedac51be6905e6049b4a10e5c0cde0198995e12279bf969714ca`
- Superseding control-plane manifest:
  `b1f72ebe01daf38c39724f2b6b2beaa1e0be391974e708ba1be65e8cf12ae3be`

## Integration matrix

| Mainline link | Round 11 evidence | Status |
|---|---|---|
| Goal | Request #267 current-host exact late-prefix acceleration | complete |
| Resolver | Superseding control-plane manifest resolves as snapshot `67a5492f25d892ba75499aaeeec665ec1f4bdc02cb972c8c3bbd6fdad71ddf32` | isolated validated; live import pending |
| Ready Queue | Resolver built the deterministic queue from manifest `b1f72ebe...`; live DB state remains untouched | isolated validated; live import pending |
| Supervisor | Existing production Supervisor intentionally remains on c1c8330 | `INTEGRATION_PENDING` |
| Capability | Compact no-trace identity plus exact prefix/scaler/tree reuse | code complete |
| Artifacts | tests, v1.1.5 plan, control-plane update, this report | code complete |
| Status | `unified_m4_status.p2_6_1_current_host_late_prefix_acceleration_round_11` | `INTEGRATION_PENDING` |
| Next task | merge, separate Operator cutover, fresh run id, two completed live replicates, deterministic replay | pending |

Mainline integration answer at Engineering evidence time:

**NO — INTEGRATION_PENDING.**

The capability may be reported complete only after the merged source is used by
the canonical Resolver, Ready Queue, Supervisor, artifact/status path, next
consumer, and deterministic replay under a separately authorized Operator
execution.

## Validation commands

- Ruff on all changed Python and test files: passed.
- Source-integrity preflight for v1.1.5: passed.
- Control-plane manifest digest and Resolver snapshot: passed.
- `test_information_theory_extended_probes.py`: 7 passed.
- `test_information_theory_measurement_validation_execution.py`: 22 passed.
- `test_m4_roadmap_v2_1_hardening.py`: 63 passed.
- Focused literal/golden boundary tests: 4 passed, 9 deselected.
- Full compact production replay: 61 folds, exact result and journal.

## Known limits and next experiment

- A 1.369x exact fold speedup is material but does not alone prove the two-week
  completion target for all remaining work.
- Exact liblinear remains approximately 60% of the post-view fold path and is
  the next lower-bound target.
- Existing in-progress replicas must replay their journals after a production
  restart because the current journal is an integrity replay, not a
  computational checkpoint. Operator cutover timing must account for that one-
  time cost.
- The next falsifiable experiment is a live two-replicate throughput comparison
  after cutover, followed by an exact liblinear/native-build experiment only if
  the measured remaining ETA still exceeds two weeks.
