# M4-P2.6 Measurement Contract Repair — Round 2

Date: 2026-07-31

Role: Engineering Agent

Primary goal: implement the approved Scheme A contract, freeze development-only
hyperparameters, and integrate the repair as the sole canonical bridge from the
identifiability preflight to P2.6.1.

## Authorization

- User-approved strategy:
  `SCHEME_A_MARGINAL_TRUTH_TO_MARGINAL_METRIC`
- Engineering Request:
  `engineering-m4-p2-6-scheme-a-repair-20260731`
- Operator authority remains limited to the already approved safe pause and a
  later clean-main repair/P2.6.1 start.

## Governed task declaration

| Field | Binding |
| --- | --- |
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` |
| Task | `m4-p2-repair-measurement-system` |
| Ready condition | Preflight COMPLETE and `MEASUREMENT_CONTRACT_REPAIR_REQUIRED` fact available |
| Runner | Unified Research Evidence Supervisor |
| Upstream artifacts | Preflight report, superseded-run archive, repair manifest, P2.6.1 manifest, state-visible feature manifest |
| Downstream artifacts | Development selection, 12 typed marginal truths, identifiability confirmation, repair completion, immutable mainline execution |
| Status projection | `P2.6.1_REPAIRED_CONTRACT_READY` |
| Engineering progress | 38% to 40% |
| Evidence progress | 0% to 0%; repair artifacts are not Evidence |
| Decision consumer | P2.6.1 false-positive/power execution, then P2.7 automatic Gate |
| Next consumer | `m4-p2-false-positive-and-power-runs` |

## Non-goals

- Do not inspect the archived P2.6 partial statistical outcomes.
- Do not reuse an archived execution id, checkpoint, or formal seed.
- Do not add a joint probe, pair kernel, or production prediction feature.
- Do not make a power, historical-signal, betting, or promotion claim.
- Do not open P3 before the repaired P2.6.1 and P2.7 decision fact complete.
- Do not represent synthetic mechanism state as available in real history.

## Scheme A estimand repair

The repaired binding is:

```text
truth  = sum_n I(Y_n; state)
metric = sum_n out-of-sample number-event log-loss gain
unit   = bits per issue
```

Joint information remains a diagnostic. It is no longer used as the truth
target for a marginal measurement Gate.

Exact legal-space calibration produced eight feasible formal power targets:

| Mechanism | Requested marginal bits/issue | Parameter | Exact marginal bits/issue | Joint diagnostic bits/issue |
| --- | ---: | ---: | ---: | ---: |
| Single | 0.001 | 0.014135575623089196 | 0.001000000000064436 | 0.000969721470507291 |
| Single | 0.010 | 0.044536089757412835 | 0.010000000000077901 | 0.009699437284786710 |
| Single | 0.050 | 0.097863459519002150 | 0.050000000000197950 | 0.048548672250210940 |
| Local temporal | 0.001 | 0.021277510357300890 | 0.000999999999994442 | 0.001306704270693061 |
| Local temporal | 0.010 | 0.067219108197538010 | 0.009999999999709262 | 0.013076929899621864 |
| Local temporal | 0.050 | 0.149636616355415250 | 0.049999999999297204 | 0.065607830840824110 |
| Pair | 0.001 | 0.016717687392573710 | 0.001000000000084945 | 0.003839050650351993 |
| Pair | 0.010 | 0.052826252531192414 | 0.009999999999721088 | 0.047021087845974946 |

The original marginal-preserving weak, practical, and strong scenarios retain
positive joint information but exact zero marginal information. They are now
`JOINT_ONLY_NEGATIVE_CONTROL`, never power targets.

The frozen pair generator cannot create a 0.05-bit marginal target. At its
exact legal parameter upper bound `0.05645161290316936`, it reaches only
`0.011422379570594537` marginal bits per issue. `STRONG_PAIR` is therefore a
`MARGINAL_FEASIBILITY_SENTINEL`, excluded from power and MDE acceptance.

The complete typed disposition is:

```text
8 FORMAL_POWER_TARGET
3 JOINT_ONLY_NEGATIVE_CONTROL
1 MARGINAL_FEASIBILITY_SENTINEL
```

## Signal representation boundary

A scalar state field was insufficient because the logistic number-event model
also needed to distinguish which red-number marginal changed with state. The
repair adds 33 `state × red-number` coordinates.

The instrument is legal only when all of these hold:

- source is synthetic;
- mechanism state is fixed and available strictly before the target draw;
- the exact state sequence digest matches;
- dataset role is P2.6.1 formal synthetic validation or development only;
- real-history state access is explicitly `forbidden`;
- no pair, combination, or joint feature is introduced.

This is measurement instrumentation, not a claim that such state exists in
historical or forward production data.

## Frozen development selection

Hyperparameters were selected once on a development-only dataset:

| Contract item | Frozen value |
| --- | --- |
| Train issues | 1–900 |
| Validation issues | 901–960 |
| Scenarios | Null plus eight feasible Scheme A targets |
| Selection metric | Mean issue log loss across all development scenarios |
| Formal outcome used | No |
| Formal evaluation seed reused | No |
| Best-seed selection | Forbidden |
| Candidate estimator/calibrator fits | 126 |
| Development contract digest | `6801bdf6b339bf154c57fa89e77496a11550e25d07e601f0b1c6f5a776000890` |
| Result artifact digest | `90459ebf8b88afcc60ee1177043e436b90b71c00b557f15e9e4d7026f37586f2` |

Selected configuration:

```text
Logistic: C = 0.1
Naive Bayes: alpha = 2
Tree: max_depth = 2, min_samples_leaf = 50
```

Formal outer folds perform no hyperparameter selection:

```text
Empirical baseline       0 fits
Logistic                 1 fit
Naive Bayes              1 fit
Tree + Platt calibration 2 fits
Total                    4 fits per outer fold
```

The previous structural budget was 46 fits per outer fold. The repair therefore
removes 42 fits, or 91.3%, from each outer fold. This is a fit-count reduction,
not yet an end-to-end runtime claim.

## Repaired Gate

The P2.7 Gate now has disjoint scopes:

- null cells: ordinary false-positive point and Wilson gates;
- eight feasible signal scenarios: power, bias, coverage, RMSE, and MDE;
- three joint-only scenarios: marginal false-positive point and Wilson gates;
- strong pair sentinel: feasibility reporting only.

The complete 31,000-replicate / 64,656,000-fold workload remains frozen.
P2.6.1 runs it with the repaired estimand and four-fit contract. P2.7 still
requires exactly one mutually exclusive `PASS_TO_P3` or
`REPAIR_MEASUREMENT_SYSTEM` fact.

## Scientific cross-review

Einstein pass:

- The decisive question is whether the metric can observe the declared signal,
  not how quickly an unidentifiable workload can finish.
- Scheme A repairs the measurement claim without introducing a new joint model.

Gauss pass:

- Exact legal-space calculations prove the three marginal-preserving truths are
  zero in the marginal estimand.
- Exact upper-bound evaluation proves the 0.05 strong-pair marginal target is
  unreachable under the frozen generator.
- The smallest correction is to preserve the generator, type the unreachable
  cell as a sentinel, and keep it out of power acceptance.
- Development and formal seed domains are disjoint, and no archived result
  enters calibration or selection.

Riemann pass:

- The original truth lived on a joint-combination space while the metric lived
  on 33 marginal event coordinates.
- Simply exposing one scalar state coordinate did not make number-specific
  conditional marginals representable.
- The smallest shared representation is a synthetic-only state coordinate plus
  33 state-by-number coordinates; extending this state to real history would
  change the scientific claim and is forbidden.

Shared conclusion:

> The repaired experiment is now identifiable in the space it claims to
> measure, while joint-only structure remains an explicit negative control.

## Frozen source identities

| Artifact | Digest |
| --- | --- |
| Measurement repair manifest | `5e41910553643e6559e78aa401fdcdd1e661b5709eaf55f0e73e694fb5a61355` |
| P2.6.1 validation manifest | `a4e46a434a4b2ef9fe56ed0390d58ca5a45bbad21685b81cb983f7261b3abf58` |
| State-visible feature manifest | `1a76f46d7a47a134c1688657749bc040290f65a03dbc7c860e38144e02005981` |
| Repair task | `1f1329a7932f707516547a71ccfdae6a221504cf3dcc8b53d8df90b85245f285` |
| P2.6.1 task | `80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa` |
| P2.7 task | `65324dc8dcf3bc60ebc9630b7af0f80e8e35bd7ddae8a265c903ebdbff8f887a` |
| Source DAG manifest | `eab2583985b389dc8ee000fba74ee965fb75da131c2e709a05067a1cbfdbb9cc` |

## Validation before merge

- Focused repair, instrumentation, Gate, contract, control-plane, supervisor,
  and replay suite: `56 passed`.
- Development selection direct replay: identical artifact digest on both runs.
- `git diff --check`: passed.
- Full worker suite: `1888 passed, 4 skipped`.
- Four warnings are the existing Python 3.14 `multiprocessing` fork
  deprecation warnings in training-supervisor parallel-equivalence tests.

## Integration matrix

| Binding | Round-2 pre-merge state |
| --- | --- |
| Goal | Bound to `M4_INFORMATION_THEORY_EVIDENCE` |
| Dependency graph | Repair inserted between preflight and P2.6.1 |
| Resolver | Repair is the sole Ready M4 task |
| Ready Queue | Verified in source-manifest resolution |
| Supervisor | Repair and P2.6.1 capabilities registered |
| Capability | Exact calibration, frozen selection, and repair execution implemented |
| Upstream artifacts | Five immutable repair inputs required in order |
| Downstream artifacts | Development, truth, confirmation, completion, execution |
| Status | Repaired-contract-ready projection implemented |
| Engineering progress | 38% to 40% |
| Evidence progress | Remains 0% |
| Next task | P2.6.1 only |
| Replay | Unit-level execution and artifact replay verified |
| No old bypass | Old execution id is non-resumable; legacy validator remains stopped |
| Live canonical execution | Pending clean merged commit |

Final training-mainline conclusion for this pre-merge round:

```text
NO — implementation remains INTEGRATION_PENDING
```

## Post-merge canonical validation and operator cutover

PR `#232` passed the Worker Python Tests check and was merged with the
repository's squash method as commit
`e6dedaf9c835672a5e17007653ee6e8fe55b67d9`.

The clean `main` checkout imported source DAG
`eab2583985b389dc8ee000fba74ee965fb75da131c2e709a05067a1cbfdbb9cc`,
then executed the repair through the unified Research Evidence Supervisor:

| Binding | Canonical result |
| --- | --- |
| Repair task digest | `1f1329a7932f707516547a71ccfdae6a221504cf3dcc8b53d8df90b85245f285` |
| Execution id | `38725967d60cbd8cac21991b92a4ebf207a2ef2089182e5bd0497c827101e9b8` |
| Execution artifact | `5c35c8f3aa92c178a08128483cb214d9c0be08cd51599773357176395b7a0d33` |
| Completion artifact | `05bd2c43b000be675ca989e0c6f8720bc20e125d540df16be6350410f26d1f78` |
| Identifiability confirmation | `770e9ee229fb60a3dd16942f7b29a5563cafcfb70e5ed2624c44e4a808f2230c` |
| Development selection | `90459ebf8b88afcc60ee1177043e436b90b71c00b557f15e9e4d7026f37586f2` |
| Registered artifacts | 16 |
| Repair folds | 0 |
| Evidence increment | 0 |
| Old partial outcomes inspected | No |
| Old execution resumable | No |
| Replay | `REPLAY_VERIFIED`; same execution, contract, development, truth, and artifact identities |
| Next Ready task | `m4-p2-false-positive-and-power-runs` |

The repaired P2.6.1 research lane then started from the updated commit:

| Runtime item | Value |
| --- | --- |
| P2.6.1 task digest | `80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa` |
| Parent execution id | `cd64aacc48c5e1dac4f84d7f644e92384b50f37299b1643631b7ee872ab452b3` |
| Execution plan | `b5b0e48febcab8d4b5550eafa9586bee890095d91b853c3e711023083b3372a6` |
| Progress path | `runtime/logs/m4-p2-6-1-measurement-validation-progress.json` |
| Service | unified supervisor `active` |
| Legacy independent validator | `disabled` and `inactive` |
| Old equivalent-resume drop-in | removed from active systemd configuration and preserved in the superseded runtime archive |
| Research-lane budget | 8 workers, `Nice=10`, idle I/O, 800% CPU quota |
| Restart/recovery check | same execution id; 40 complete artifacts reused |
| Post-restart live check | 45 complete, 0 failed, 0 retried; five new artifacts completed under the bounded lane |

Partial P2.6.1 statistical outcomes are not used to revise the frozen
measurement contract, tune a threshold, or make an early Gate decision.
P2.6.1 remains `RUNNING`; P2.7 and P3 correctly remain dependency-gated until
the full formal workload and automatic Gate complete. Engineering work may
continue independently while the bounded research lane runs.

## Final integration matrix

| Integration item | Canonical evidence |
| --- | --- |
| Canonical Goal | `M4_INFORMATION_THEORY_EVIDENCE` |
| Dependency Graph | Repair completed between preflight and P2.6.1 |
| Ready Queue | Repair was sole Ready; P2.6.1 became sole Ready afterward |
| Unified Runner | Repair execution `38725967…`; P2.6.1 execution `cd64aacc…` |
| Upstream artifacts | Five ordered repair identities verified |
| Downstream artifacts | 16 repair artifacts registered |
| Status projection | `P2.6.1_REPAIRED_CONTRACT_READY`, then P2.6.1 `RUNNING` |
| Engineering Progress | 38% to 40% |
| Evidence Progress | 0% to 0% |
| Downstream consumer | P2.6.1 false-positive/power run |
| End-to-end replay | Repair replay verified without manual input assembly |
| No old bypass | Old resume path archived; legacy validator disabled |

Final training-mainline conclusion for the Measurement Contract Repair:

```text
YES — validated by unified mainline execution and replay
```

P2.6.1 itself is intentionally not classified COMPLETE; it is an active,
bounded research-lane execution awaiting all formal replicates and P2.7.
