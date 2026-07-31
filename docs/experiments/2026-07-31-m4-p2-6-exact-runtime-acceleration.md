# M4-P2.6 Exact Runtime Acceleration

Date: 2026-07-31

## Round contract

- Primary goal: reduce the wall time of the frozen 31,000-replicate P2.6
  workload without changing any statistical, model, leakage, seed, fold,
  artifact, or Gate identity.
- Non-goals: reduce the preregistered workload, change a probe or
  hyperparameter, use tolerance-based artifact substitution, inspect partial
  statistical outcomes, run P2.7 early, or enable a GPU merely because the
  device is visible.

## Einstein pass

- Core question: which repeated computation can be removed while every
  observable P2.6 result remains identical?
- Invariants: 31 cells, 31,000 replicates, 64,656,000 outer folds, expanding
  walk-forward boundaries, four frozen probes, literal P2.2 numerical output,
  strict-prior checkpoint order, all seed identities, all digests, and the
  automatic Gate.
- Hypothesis: repeated tuple-to-array conversion, repeated fold-local
  preprocessing, Python-level positive `fsum`, and canonical feature JSON are
  material overhead that can be replaced by exact caches or byte-identical
  compiled paths.
- Measurement: terminal-fold wall time, bitwise float equality, probe state
  digest equality, full replicate artifact equality, and checkpoint journal
  byte equality.
- Failure mode: a faster path that changes even one probability bit, digest,
  journal byte, child identity, retry outcome, or decision input is rejected.
- Next experiment: deploy only after full tests and a mainline resume prove
  that existing artifacts are reused and newly completed artifacts pass the
  independent validator.

## Profile result

The original HISTORICAL terminal-fold cProfile on this host recorded:

- 13.09 seconds under the low-priority isolated profiling protocol;
- 2.58 seconds in repeated `numpy.asarray`;
- 2.42 seconds in the literal nested-validation Metric Kernel;
- 1.93 seconds in canonical JSON encoding;
- about 2.27 seconds in liblinear and tree fitting.

The accepted implementation candidates are:

1. one fold-local `ExactProbeRuntimeCache` shared by the frozen probes;
2. cached immutable feature, target, scaler, transformed, and tree-fit arrays;
3. an exact Numba transcription of CPython positive `math.fsum`, with fastmath
   disabled and the same `log`, `log1p`, clipping, and `LN_2`;
4. pinned `orjson==3.11.9` for the internal ASCII primitive feature identity,
   only after proving its bytes equal canonical stdlib JSON;
5. prevalidated float32 tree input reuse with sklearn `check_input=False`,
   after the ordinary frozen validation boundary has already passed.

The optimized terminal-fold profile reduced the nested Metric Kernel to about
0.23 seconds and canonical feature serialization to about 0.31 seconds.
Paired and staged measurements observed approximately 1.7x to 2.0x terminal
fold speedup under concurrent mainline load. This is a local-host estimate,
not yet a completed-workload throughput claim.

## Exactness evidence

- 10,000 deterministic random legal issue/probability rows produced bitwise
  identical literal and Numba log-loss values.
- All 16 train/blind feature identities built by the representative
  HISTORICAL terminal fold produced byte-identical stdlib and orjson canonical
  JSON; measured serialization speedup was 7.48x.
- Cached and uncached terminal-fold executions produced identical state
  digests and prediction tuples for all four probes.
- Re-executing the already-completed formal
  `FORWARD_61 / NULL_UNIFORM / replicate 0` produced:
  - identical final result object;
  - identical final artifact digest;
  - identical 61-entry checkpoint journal bytes.
- Targeted probe, measurement-validation, and walk-forward suites:
  `101 passed`.
- Full worker suite: `1,874 passed, 4 skipped`.

Live resumed-mainline evidence remains pending.

## GPU boundary

The host exposes Intel Arc Graphics through OpenCL with 128 compute units and
FP64 support, and PyOpenCL is installed. That does not make the frozen sklearn
pipeline GPU-capable:

- liblinear, the shallow decision tree, and Platt calibration remain CPU
  implementations;
- the now-compiled nested metric is only a small fraction of optimized fold
  time, so transferring it to the GPU cannot supply the required order of
  magnitude;
- the existing real-score OpenCL probe measured 0.851x end-to-end speed and
  failed exact rounded-matrix equivalence.

Therefore this round does not enable a P2.6 GPU backend. Reaching a one-to-two
day wall time requires deterministic multi-node replicate sharding or a new
preregistered measurement implementation; it cannot be obtained by toggling
the integrated GPU.

## In-flight runtime migration contract

P2.6 was already RUNNING at commit
`84e3069480c01157418b8d588f08ccff7a32b7a9`. The Supervisor therefore keeps
that commit as the frozen execution identity and still rejects an arbitrary
source change. This acceleration may resume the same execution only when:

1. `DEHPS_P26_EQUIVALENT_RESUME_FROM_COMMIT` exactly names that original
   execution commit;
2. the working tree is clean;
3. this evidence report exists inside the repository;
4. the resumed task is exactly P2.6; and
5. an immutable `measurement_validation_runtime_migration` artifact records
   the execution commit, actual runtime commit, report SHA-256, unchanged
   statistical contract, and unchanged workload.

The migration artifact becomes a registered child and parent of the final
P2.6 mainline execution artifact. Newly generated replicate and checkpoint
identities remain under the original execution commit so existing journals can
be verified and resumed byte-for-byte; the actual source commit is preserved
separately rather than hidden.

## Integration matrix

| Requirement | Current evidence |
|---|---|
| Goal and frozen task contract unchanged | PASS |
| Replicate, seed, fold, probe, metric, and Gate identities unchanged | local exactness PASS |
| Existing formal artifact and journal replay | one complete replicate PASS |
| Full relevant worker test suite | PASS: 1,874 passed, 4 skipped |
| Accepted PR merged to `main` | PENDING |
| Updated unified Supervisor invoked | PENDING |
| Existing execution resumes without artifact loss | PENDING |
| New mainline replicates independently verified | PENDING |
| Deterministic completion and P2.7 consumer | waiting on full workload |

Current completion answer:

```text
NO — INTEGRATION_PENDING
```
