# M4-P2.6.1 Two-Week Runtime Acceleration — Round 3

Date: 2026-08-04

Role: Engineering Agent  
Agent Request:
`engineering-m4-p2-6-1-two-week-runtime-acceleration-round-3-20260804`
(request 252, execution 173)

## Round contract

The primary goal is to reduce the late-prefix cost that makes the frozen
P2.6.1 workload increasingly slow while preserving the accepted statistical
experiment exactly.

Non-goals are changes to the generator, estimand, visible features, target
boundary, four probe families, hyperparameters, seeds, fold order, metrics,
resampling, workload size, Gate policy, result schema, immutable task identity,
or the currently executing Supervisor. No partial statistical result was read.

The accepted equivalence obligation was:

```text
same prefix rows and order
-> same sklearn model parameters and Platt parameters, bit for bit
-> same probability bits
-> same ProbeState and metric trees
-> same checkpoint and settlement identities
-> same checkpoint-journal bytes
```

## Gauss pass

The exact definitions and invariants were checked before implementation:

- Bernoulli NB has two unweighted classes and `binarize=0.0`; its fit is fully
  determined by exact integer class counts and exact integer counts of
  `standardized_feature > 0` for each class.
- The largest count is far below `2**53`, so conversion of those integer counts
  to float64 is exact. sklearn's own alpha check, feature-log-probability update,
  and class-prior update remain the probability kernel.
- `FrozenEstimator(tree)` returns the same already-fitted tree for every CV
  split. Its five ordered `cross_val_predict` slices are therefore equal to one
  prediction over the full calibration matrix in original row order.
- sklearn's own `_fit_calibrator` and public calibrated-classifier prediction
  wrapper remain in use; only redundant slicing and dispatch are removed.
- First, middle/terminal, class-balance, parameter-array, probability-bit,
  complete-result, trace, and journal boundaries were checked against the
  literal implementation.

The smallest defensible conclusion is limited to computational equivalence and
measured runtime reduction. It does not claim new predictive evidence.

## Profile decisions

A direct call to the same liblinear kernel was evaluated and rejected for this
round. It produced identical classes, coefficients, intercept, iteration count,
and probability bits, but removed only about 26 ms from a terminal HISTORICAL
fit (roughly three percent of that logistic fit). This was too small to justify
adding another private runtime boundary.

Two larger exact operators were accepted:

1. The runtime Bernoulli operator builds the exact sklearn estimator state from
   binary sufficient counts instead of materializing a dense float64 binarized
   matrix and two-column label indicator for every fold.
2. The runtime tree calibrator predicts once in original row order and feeds
   that exact response to sklearn's Platt kernel instead of dispatching the
   same frozen tree through five redundant CV slices.

The independent literal/golden path still uses the public sklearn fit paths.

## Measurements

All measurements fixed numerical thread pools at one and ran at low priority
while the existing 16-worker production Supervisor remained active. Absolute
times are therefore load-contended; the interleaved same-process A/B ratio is
the relevant Round 3 comparison.

Terminal HISTORICAL operator microbenchmarks:

| Operator | Accepted runtime before Round 3 | Round 3 exact operator |
| --- | ---: | ---: |
| Bernoulli NB fit | 0.371–0.477 s | 0.104–0.138 s |
| Frozen-tree Platt calibration | 0.182–0.251 s | 0.091–0.111 s |

Interleaved terminal HISTORICAL fold, three learned probes including
preprocessing and prediction:

| Path | Median wall seconds | Relative |
| --- | ---: | ---: |
| Round 1 runtime with public NB/calibration operators | 2.673088 | 1.000x |
| Round 3 exact operators | 2.442709 | 1.094x |

Every A/B repetition produced the same state digests and probability bits.
The cold pair was excluded from the ratio because the optimized member ran
second and was slower under concurrent production load; four interleaved warm
observations per path determine the reported median.

The full 61-fold independent replay took 329.91 seconds on the deliberately
literal path and 51.73 seconds on the optimized path. That 6.38x difference
includes all prior accepted acceleration, especially Round 1, and is not
attributed to Round 3 alone.

Round 3 improves the exact single-host path but still does not prove the
14-day capacity threshold. Applying 1.094x mechanically to Round 1's 8.316
folds/second would be about 9.10 folds/second, still far below the required
51.44 folds/second; this extrapolation is diagnostic, not a new capacity
measurement or completion promise.

## Exactness evidence

- Optimized/literal probe and golden-reference test files: `18 passed`.
- Ruff on all changed Python surfaces: PASS.
- Full 61-fold result object equality: PASS.
- Float64-tree result digest on both paths:
  `6c142006e902b951ee31cf799bb9527d5d370060ef0196821f7b9c1b0ae5667e`.
- All 61 captured fold traces, including probe states, probability values,
  IssueMetrics, checkpoints, and settlements: exact equality.
- Checkpoint journal raw UTF-8/LF bytes: exact equality (`40,250` bytes).
- Literal golden reference remains import-independent from the optimized
  runtime backend: PASS.

## Mainline integration matrix

| Requirement | State |
| --- | --- |
| Goal and frozen scientific contract | PASS, unchanged |
| Exact operator proof | PASS |
| Literal full-replicate replay | PASS, 61 of 61 folds |
| Result / trace / journal-byte equality | PASS |
| Resolver / Ready Queue / Supervisor | Existing canonical P2.6.1 path unchanged during Engineering work |
| Accepted PR merged to `main` | PENDING |
| Fresh Supervisor on merged source | PENDING |
| One to two fresh completed replicates | PENDING |
| Downstream completion guard and P2.9 consumer | Existing canonical consumer, pending fresh runtime proof |

Current completion answer:

```text
NO — INTEGRATION_PENDING
```
