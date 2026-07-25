# M4-P2.3 Strict Synthetic Walk-forward Probe Harness

## Round Contract

- Role: Engineering Agent.
- Authorized request: `engineering-m4-p2-3-walk-forward-harness-20260725`.
- Baseline commit: `f59a6b1b1dde6f02f13aa3465e560cb38931b448`.
- Primary goal: make leakage, pre-checkpoint target access, outer-result tuning, and competing predictions structurally impossible.
- Preregistration: `6e03cd828378badda6995c6582d80165b0a4ee3b5899b97737bad1494fcf1ae1`.
- Decision policy: `824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d`.
- P2.1 synthetic manifest: `8493987cc4414414e33fb5c5ea148be1f42a1d9e57609600c4346fb642cbfa08`.
- P2.2 Metric Kernel: `56b9d0a62d43d167069e5222c7095383c9c5106bb3361b0b1def75cf2b6c86a2`.
- P2.3 harness manifest: `177a3d591b7557a4231a276bfb007f0d42a94d942824403f5376f94fe904d2ca`.

## Einstein Constraint Pass

The conserved object is one chronological issue cluster containing 33 number events and six positives. A legal fold has a one-way causal surface: all feature, preprocessing, inner-validation, and probe state is available no later than `test_issue - 1`; the target may cross that surface only after one immutable prediction checkpoint exists.

The easiest ways to fool the measurement are a target-derived feature, a global scaler, shuffled validation, a test issue inside training, or a second prediction selected after seeing loss. Each is implemented as a minimal canary and rejected before it can become a settlement.

## Exact Walk-forward Boundary

The frozen mode is an expanding window with a one-issue horizon:

```text
outer train = issues [1, ..., t - 1]
outer test  = issue  [t]
max(train) < t
```

`minimum_training_issues=900` is present in both preregistration v1.0.1 and every P2.1 synthetic scale. The `FORWARD_61` scale therefore defines 61 legal outer folds, with the first test issue at synthetic index 901. P2.3 executes only two fixed folds, 901 and 902, as a small smoke. It does not execute the 61-fold sequence as evidence and does not run scenario replicates.

Every fold identity contains dataset, train start/end, test issue, feature view, preprocessing manifest, probe manifest, Metric Kernel, and preregistration identities. A boundary or identity change changes the fold digest.

## Target Isolation and Exactly-once Prediction

The probe receives a `TrainingDatasetView`, not the full synthetic artifact. Its `issue()` method rejects every issue after `outer_train_end` with `target_access_boundary_violation`. The separate `BlindTestFeatureView` contains only 33 ordered feature rows plus explicit availability metadata. It has no target, red mask, draw numbers, or target-derived diagnostics.

The legal order is:

1. freeze the outer fold;
2. construct historical training and blind test views;
3. fit all preprocessing and probe state inside outer training;
4. persist one target-free prediction checkpoint;
5. reveal the target;
6. call the P2.2 Metric Kernel;
7. persist the immutable settlement.

The exactly-once key is `(dataset_digest, probe_manifest_digest, test_issue)`. An identical replay returns the same digest. A different probability vector under the same formal identity raises `duplicate_prediction_identity` before target reveal.

## Features and Preprocessing

The minimal `FV1_SYNTHETIC_HISTORY_STATE` contains:

- previous-issue hit;
- expanding prior frequency;
- periods since last prior hit;
- red number divided by 33.

Every row for issue `t` uses only issues before `t` and records `available_through_issue=t-1`. The target-as-feature canary sets availability to `t` and is rejected as `future_feature_leakage`.

`StandardScaler` is fitted independently inside each inner training prefix and again on the complete outer training interval for the final outer probe. Its immutable state records fit start/end, ordered feature names, mean, scale, and state digest. A claimed fit end after `outer_train_end` raises `preprocessor_fit_range_violation`.

## Probe and Inner-validation Contracts

The registry contains only:

1. theoretical uniform baseline;
2. expanding empirical baseline;
3. regularized logistic regression.

The theoretical baseline performs no fit, uses no seed, and emits exactly `6/33` for every number.

The empirical baseline is implemented because preregistration explicitly freezes Jeffreys beta-binomial smoothing: `(count_j + 0.5) / (training_issue_count + 1)`. Counts use the current outer training view only. Changing later synthetic targets cannot change an earlier empirical prediction.

The primary logistic probe uses the frozen contract:

```text
penalty = L2
C candidates = [0.01, 0.1, 1.0]
class_weight = null
solver = liblinear
max_iter = 1000
tol = 0.0001
implementation = scikit-learn==1.9.0
seed = dataset replicate seed
```

Selection uses three expanding blocked chronological inner folds and `issue_mean_log_loss` produced through the Metric Kernel. Every candidate gets the same inner folds. Ties prefer lower complexity and then lexical config identity. No outer PE1, Brier, cumulative gain, scenario aggregate, or final smoke result enters selection.

Convergence is fail-closed. Solver failure, warning, insufficient class variation, or an invalid matrix creates a structured failed fold. The harness does not silently change the solver, iteration limit, regularization, or model, and it has no baseline fallback.

## Metric Settlement and Aggregate

Only `m4-information-theory-metric-kernel-v1` calculates Log Loss, PE1, Brier, clipping diagnostics, and issue metrics. A wrong kernel digest raises `metric_kernel_identity_mismatch`. Probe, harness, CLI, and report modules contain no replacement scoring formulas.

The theoretical baseline smoke produces exactly:

```text
PE1 = 0 bits/issue
Brier gain = 0 per issue
predicted red count = 6
```

The fixed-seed logistic null smoke completed two folds with legal probabilities and deterministic artifacts. Its observed mean PE1 during implementation validation was approximately `-0.0448690772 bits/issue`. That value is only a process check; it is not used for selection or any signal claim.

The aggregate records completed, failed, and fallback folds separately; stable cumulative PE1; descriptive mean/median; Brier gain; predicted count; clipping; and convergence summary. Its inference sample size is completed issue count. It emits no IID CI, block-bootstrap CI, permutation p-value, MDE, power, PE2, or signal decision.

Every run is marked:

```text
SMOKE_TEST_ONLY
NOT_POWER_EVIDENCE
NOT_P2_GATE_EVIDENCE
descriptive_only = true
eligible_for_p2_gate = false
```

## Leakage Canary Results

- Test target as feature: rejected with `future_feature_leakage`.
- Global scaler: rejected with `preprocessor_fit_range_violation`.
- Shuffled/random CV: rejected with `non_chronological_inner_validation`.
- Test issue in training: rejected with `outer_train_test_overlap`.
- Second competing prediction: rejected with `duplicate_prediction_identity` before target reveal.
- Dataset changed after training/checkpoint: rejected with `dataset_mutation_detected` or a digest mismatch.

## Determinism and Resume

Run identity includes dataset, harness, probe, selected test issues, seed policy, replicate seed, outer contract, and git commit. Checkpoints and settlements are immutable and digest-addressed. Replays under worker counts 1 and 2, forward and reverse scheduling, repeated CLI execution, and interrupted resume produce the same ordered child graph and final artifact. No output rounding or post-hoc quantization is used.

The operational state is written before fold execution and updated after each immutable child. Resume verifies the frozen run identity, reuses completed children, and settles only missing folds.

## Required Questions

1. **Outer boundary:** expanding `[1..t-1] -> [t]`, horizon one.
2. **Minimum training length:** 900, from preregistration v1.0.1 and the P2.1 scale contract.
3. **Exactly once:** yes; one formal identity per dataset/probe/test issue.
4. **Checkpoint target-free:** yes; schema and runtime validator prohibit target fields.
5. **Target reveal:** only after checkpoint persistence and dataset identity revalidation.
6. **Preprocessing fit proof:** fit start/end and state digest are recorded; fit end must not exceed outer train end.
7. **Why no random K-fold:** it violates time order and the frozen three-fold expanding blocked contract.
8. **Logistic selection:** inner issue-mean Log Loss across frozen C candidates, then frozen tie-break.
9. **Outer metric used for selection:** none.
10. **Convergence failure:** structured failed fold, fail closed, no silent fallback or contract mutation.
11. **Theoretical PE1:** exactly zero.
12. **Theoretical Brier gain:** exactly zero.
13. **Logistic null smoke role:** process validation only.
14. **Timestamp guard:** `available_through_issue < target_issue` is explicit and validated.
15. **Global scaler canary:** rejected.
16. **Target feature canary:** rejected.
17. **Duplicate prediction:** rejected before target access.
18. **Metric source:** the P2.2 Metric Kernel is the only source.
19. **Formal power evidence:** none.
20. **Real history read:** no.
21. **Production checkpoint generated:** no.
22. **Why P2.4 next:** the leak-proof harness now exists, so injected-signal calibration is the next dependency.

## Artifacts and Research OS

- Fold schema: `dehps-m4-information-theory-walk-forward-fold.v1`.
- Prediction schema: `dehps-m4-information-theory-prediction-checkpoint.v1`.
- Settlement schema: `dehps-m4-information-theory-fold-settlement.v1`.
- Run schema: `dehps-m4-information-theory-walk-forward-run.v1`.
- Harness manifest digest: `177a3d591b7557a4231a276bfb007f0d42a94d942824403f5376f94fe904d2ca`.
- Projected control-plane manifest: `3c511268fd1211c6c71de8ec3ac9c0afd218855ed58885a26b4cec4638175157`.
- Projected snapshot: `0439797f775bbda55b92421b3d6feb9baf98d79e9a0a51d2779f25907c94e614`.
- Engineering progress: 30%.
- Evidence progress: 0%.
- Next Ready task: `m4-p2-injected-signal-calibration`.

Final clean-tree smoke run digests, merged commit, GitHub CI, and live idempotent control-plane synchronization are recorded in the completion handoff because run identity includes the final git commit.

## Validation

- P2.3 requirements suite: `83 passed`.
- Combined P2.2/P2.3 and Research OS regression: `181 passed`.
- Full Worker: `1759 passed, 4 skipped`.
- API: `117 passed`.
- Web: `19 passed`.
- Angular production build: passed.

## Scope Audit

- Injected signal implemented: NO.
- Bootstrap implemented: NO.
- Permutation implemented: NO.
- Large replicate run: NO.
- Real historical data analyzed: NO.
- Production checkpoint generated: NO.
- Frozen thresholds changed: NO.
- PE2 implemented: NO.
- Evidence produced: NO.
- Production path changed: NO.

## Governance

- Promotion Gate: CLOSED.
- Adaptive Supervisor: STOPPED.
- Old training mainline: REJECTED/FROZEN.
- Formal real-data analysis: NOT_STARTED.
- Issue 2026085: permanently ineligible for M4 forward evidence.
