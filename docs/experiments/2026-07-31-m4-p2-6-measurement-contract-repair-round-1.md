# M4-P2.6 Measurement Contract Repair — Round 1

Date: 2026-07-31

Role: Engineering Agent

Primary goal: insert a result-blind identifiability preflight before P2.6,
archive the paused execution, and route the canonical Ready Queue to the
approved Scheme A repair.

## Authorization

- Engineering Request:
  `engineering-m4-p2-6-identifiability-preflight-repair-20260731`
- Operator Request:
  `operator-pause-m4-p2-6-measurement-contract-repair-20260731`
- Supplemental Operator Request:
  `operator-pause-m4-p2-6-independent-validator-20260731`
- User-approved repair:
  `SCHEME_A_MARGINAL_TRUTH_TO_MARGINAL_METRIC`

## Non-goals

- Do not inspect partial P2.6 statistical outcomes.
- Do not create Evidence from the paused execution.
- Do not add a joint model, interaction kernel, or new prediction algorithm.
- Do not freeze final P2.6.1 hyperparameters in this round.
- Do not start P2.6.1, P2.7, or P3 in this round.
- Do not delete or rewrite the old checkpoint tree.

## Result-blind identifiability result

The preflight compares the frozen P2.4 joint truth
`I(Y_vector; state)` with the information estimand visible to the P2.2
33-event marginal metric, `sum_n I(Y_n; state)`. It also audits whether the
P2.3 feature view explicitly represents the mechanism state required by the
contract.

The values below were read only from the twelve accepted P2.4 truth artifacts.
No paused P2.6 replicate result or aggregate was read.

| Scenario | Joint bits/issue | Composite marginal bits/issue | Joint − marginal | Classification summary |
| --- | ---: | ---: | ---: | --- |
| WEAK_SINGLE_NUMBER | 0.001000000056 | 0.001031223188 | -0.000031223132 | STATE_NOT_EXPOSED_TO_PROBE |
| WEAK_LOCAL_TEMPORAL | 0.001000000084 | 0.000765299220 | 0.000234700864 | STATE_NOT_EXPOSED_TO_PROBE |
| WEAK_PAIR | 0.001000000000 | 0.000263209414 | 0.000736790585 | STATE_NOT_EXPOSED_TO_PROBE |
| WEAK_MARGINAL_PRESERVING | 0.001000000007 | 0.000000000000 | 0.001000000007 | NOT_IDENTIFIABLE_BY_CURRENT_METRIC; STATE_NOT_EXPOSED_TO_PROBE |
| MEDIUM_PRACTICAL_SINGLE_NUMBER | 0.010000000030 | 0.010309794550 | -0.000309794520 | STATE_NOT_EXPOSED_TO_PROBE |
| MEDIUM_PRACTICAL_LOCAL_TEMPORAL | 0.009999999956 | 0.007648568866 | 0.002351431090 | STATE_NOT_EXPOSED_TO_PROBE |
| MEDIUM_PRACTICAL_PAIR | 0.010000000029 | 0.002544390782 | 0.007455609248 | TRUTH_METRIC_ESTIMAND_MISMATCH; STATE_NOT_EXPOSED_TO_PROBE |
| MEDIUM_PRACTICAL_MARGINAL_PRESERVING | 0.010000000044 | 0.000000000000 | 0.010000000044 | NOT_IDENTIFIABLE_BY_CURRENT_METRIC; TRUTH_METRIC_ESTIMAND_MISMATCH; STATE_NOT_EXPOSED_TO_PROBE |
| STRONG_SINGLE_NUMBER | 0.049999999912 | 0.051492598863 | -0.001492598951 | STATE_NOT_EXPOSED_TO_PROBE |
| STRONG_LOCAL_TEMPORAL | 0.049999999988 | 0.038144017086 | 0.011855982902 | TRUTH_METRIC_ESTIMAND_MISMATCH; STATE_NOT_EXPOSED_TO_PROBE |
| STRONG_PAIR | 0.050000000031 | 0.010428102831 | 0.039571897200 | TRUTH_METRIC_ESTIMAND_MISMATCH; STATE_NOT_EXPOSED_TO_PROBE |
| STRONG_MARGINAL_PRESERVING | 0.050000000067 | 0.000000000000 | 0.050000000067 | NOT_IDENTIFIABLE_BY_CURRENT_METRIC; TRUTH_METRIC_ESTIMAND_MISMATCH; STATE_NOT_EXPOSED_TO_PROBE |

Automatic decision:

```text
MEASUREMENT_CONTRACT_REPAIR_REQUIRED
```

Automatic fact:

```text
m4-p2-identifiability-decision:MEASUREMENT_CONTRACT_REPAIR_REQUIRED
```

The three marginal-preserving scenarios are the decisive exact counterexample:
their joint information is positive while their composite marginal
information is zero. No number of folds can make the current marginal metric
measure that joint-only signal.

## Paused execution archive

The old P2.6 definition and execution are preserved by
`m4-information-theory-p2-6-superseded-run-archive-v1.json`.

| Field | Preserved value |
| --- | --- |
| Old task digest | `975a8e0bf859bad1e7f5f33411471878dd731134ee1f3b81948bd8c8503dc4c0` |
| Parent execution id | `8e1c601233833b60442b45ebaeeaea53679c34eef1d00de5480827f415d517fd` |
| Execution plan digest | `4b6d1b5d3a72f09188adb844d9aacb4addfee68afd3bb5d6efe8f396694f5e3e` |
| Complete replicate artifacts | 13,223 |
| Checkpoint journal files | 13,243 |
| In-flight partial journals | 20 |
| Failed replicates | 0 |
| Artifact tree bytes | 978,493,712 |
| Artifacts deleted | No |
| Partial statistical results inspected | No |
| Evidence progress increment | 0 |

The revised task definition has a different immutable task digest and cannot
resume the archived execution id. It remains blocked until a separately frozen
P2.6.1 contract has passed the Scheme A repair.

## Mainline routing

```text
M4 Goal
  -> P2.5 COMPLETE
  -> Identifiability Preflight READY
  -> Research Evidence Supervisor
  -> Preflight report + exactly one decision fact
  -> Unified M4 status
  -> Scheme A repair task READY
```

The old path is fail-closed:

```text
old P2.6 execution -> SUPERSEDED
revised P2.6.1     -> DEPENDENCY_WAIT
P2.7               -> DEPENDENCY_WAIT
P3                 -> DEPENDENCY_WAIT
```

## Scheme A obligations carried to Round 2

1. Calibrate P2.4.1 truth to `sum_n I(Y_n; state)`, the same estimand settled
   by the current marginal metric.
2. Move marginal-preserving joint-only mechanisms out of the marginal power
   targets and retain them as identifiability negative controls.
3. make the signal representation contract explicit rather than assuming that
   a latent mechanism state is available to the probe.
4. Select logistic `C`, naive-Bayes `alpha`, tree structure, and Platt
   calibration configuration on an independent development seed/domain; freeze
   them before formal P2.6.1 validation.
5. Benchmark the frozen configuration. The structural fit count changes from
   46 estimator/calibrator fits per outer fold to 4; no end-to-end speedup claim
   is accepted before a live benchmark.

## Scientific review

Einstein pass:

- The cheapest decisive experiment is an instrument check, not another
  64,656,000-fold workload.
- The marginal-preserving cases provide a direct falsification of the claim
  that the current measurement system can recover every frozen joint signal.

Gauss pass:

- The legal six-of-33 sample space and accepted P2.4 truth identities are
  unchanged.
- The zero marginal information result is exact for the marginal-preserving
  mechanism; it is not a Monte Carlo fluctuation.
- No partial P2.6 result, post-hoc threshold, or selection path entered the
  decision.
- The two identifiability decision facts are enforced as mutually exclusive.

Smallest shared conclusion:

> Repair the estimand binding before spending additional formal compute.

## Validation

- Focused control-plane, contract, supervisor, and replay tests:
  `169 passed`.
- Full worker suite after the final expectation updates:
  `1878 passed, 4 skipped`.
- Four warnings are the existing Python 3.14 `multiprocessing` fork
  deprecation warnings in training-supervisor parallel-equivalence tests.
- `git diff --check`: passed.

## Integration matrix

| Binding | Round-1 state |
| --- | --- |
| Goal | Bound to `M4_INFORMATION_THEORY_EVIDENCE` |
| Resolver | Preflight resolves Ready after P2.5 |
| Ready Queue | Preflight is the only M4 Ready task |
| Supervisor | Capability registered |
| Capability | Deterministic result-blind comparison implemented |
| Artifacts | Frozen preflight manifest, archive, report, execution |
| Status | Repair-required projection implemented |
| Next task | Scheme A repair task only |
| Replay | Unit-level immutable event/artifact replay passed |
| Live canonical execution | Pending clean merged commit |

Final training-mainline conclusion for this pre-merge round:

```text
NO — implementation remains INTEGRATION_PENDING
```
