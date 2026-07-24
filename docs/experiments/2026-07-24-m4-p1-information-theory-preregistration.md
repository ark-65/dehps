# M4-P1 Information-Theory Preregistration

## Round contract

- Primary goal: freeze the research question, legal sample space, targets, feature families, nulls, endpoints, practical-null, chronology, controls, power gates, decision policy, artifact identity, and forward-evidence interface before any formal result exists.
- Non-goals: no estimator implementation, no model training, no real-data analysis, no bootstrap/permutation run, no synthetic run, no hypothesis conclusion, and no production change.
- Source baseline: main commit `44d4820dd91a86ca8826c1448972e0dae8c97ad2`; canonical history ends at issue `2026084`.
- Engineering authority: approved `engineering-m4-information-theory-p1-preregistration-20260724`; execution `135`.

## Frozen identities

| Identity | Value |
|---|---|
| Contract | `m4-information-theory-contract-v1` |
| Contract digest | `ae4e741cfc55547785ca9cf57b5b49f37a3d8c4f2bd53daeff9228982f797a69` |
| Preregistration version | `1.0.0` |
| Preregistration digest | `a4f29c1392305b6ef2dc90134901c74f8ffb297071838d734d1e17e8439ad6e8` |
| Decision policy digest | `824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d` |
| P2 input digest | `9d566449102e0c4caf67c8e56ffe6c6b680705aada50590eb18be9ea832fa109` |
| History digest | `30224d09a8b2d9080d3bc848f50b534c6d6de50b2eac867882915e85acbf206b` |
| Feature contract digest | `c7b5d9572f93c17f4b84debd3f0e9f9d445b7e3c76c5bfe5d594d180064c9869` |
| F5 component manifest | `42ed7fc0a60a1be64f6f097f14e765f447f941d4427395a2e86bdbc99431c0c4` |
| Target contract digest | `c768d4cc34ca92ce705cc9bc796798e459e85ccc4bc32c2e44622691c5068b2a` |
| Freeze source commit | `80116b488f461ed214b46b9e2668bb190a435d0c` |

The canonical history identity is metadata-only: 3,481 issues from `2003001` (2003-02-23) through `2026084` (2026-07-23). P1 did not calculate any outcome statistic.

## Frozen research choices

- Primary unit: 33 binary red-number events per issue, with six positives and 27 negatives retained as one issue cluster.
- Pair role: all 528 unordered pairs, secondary exploratory only, minimum support 20 issues, Benjamini–Hochberg control, and never sufficient alone for a top-level positive decision.
- Structural targets: only the nine enumerated targets in the preregistration.
- Primary null: exact theoretical uniform sampling of six numbers without replacement from 33.
- Sensitivity null: expanding empirical number base rates fitted only inside each outer training history.
- Feature families: F0–F6. F5 binds the exact immutable 32-component Feature ABI rather than whatever code happens to exist at execution time.
- Allowed probes: empirical baseline, regularized logistic regression, naive Bayes, and a shallow calibrated tree. Logistic regression is primary; all selection and preprocessing remain nested.
- Joint primary endpoints: out-of-sample log-loss gain and bias-corrected information gain. Neither may be selected alone after results are observed.
- Practical equivalence interval: `[-0.01,+0.01] bits/issue`; auxiliary relative log-loss threshold `0.1%`.
- Walk-forward: expanding window, 900 initial training issues, first outer test issue `2009076`, one issue per test, horizon one.
- Primary stability partition: `2009076–2017139` and `2017140–2026084`; both must have positive direction for `SUPPORTED_WEAK_SIGNAL`.
- Sensitivity thirds: `2009076–2015016`, `2015017–2020111`, and `2020112–2026084`.
- Negative controls: issue-block permutation, number-label permutation, seven fixed circular shifts, matched random features, matched random score, and uniform synthetic null.
- Injected signal levels: 0.001, 0.01, and 0.05 bits/issue across four mechanisms, including a marginal-preserving conditional signal.
- Resampling: issue-level moving block bootstrap, primary block five, sensitivity blocks 3/5/8/13, stationary bootstrap sensitivity, 2,000 bootstrap and 2,000 permutation replicates.
- Multiplicity: Holm for primary and bounded comparison families; Benjamini–Hochberg for red-number and pair scans.
- Power: alpha 0.05, target power 0.80, practical-strength injected signal power at least 0.80, and fail-closed measurement repair when false-positive, bias, replay, or leakage gates fail.

## Practical-null dimensional review

The legal six-red space has `C(33,6) = 1,107,568` outcomes and theoretical entropy `20.0789638462 bits`. The 0.01-bit margin is therefore about `0.049803%` of the full entropy. A 0.01-bit gain corresponds to a geometric-mean likelihood ratio of `2^0.01 = 1.00695555`, or about `0.6956%` per issue.

There is no model-free conversion from information gain to an average probability-point improvement. As an orientation only, spreading 0.01 bits equally across 33 Bernoulli events at `p=6/33` gives a local KL approximation of about `0.7905` probability points. This approximation is not a decision statistic.

P1 does not claim the current sample can detect 0.01 bits/issue. That question is delegated to the frozen P2 injected-signal power gate. The interval is an equivalence margin: a practical-null conclusion is legal only when the full confidence interval lies inside it and the P2 measurement system can reliably detect the practical-strength signal.

## Design review

1. **Why number-level events?** They retain repeated probabilistic observations and proper scoring while preserving the exact six-of-33 constraint. A full-combination hit is too sparse to be the primary research unit.
2. **How is within-issue dependence handled?** All 33 events retain the issue cluster key; aggregation, bootstrap, permutation, confidence intervals, and validation splits use the issue as the atomic unit.
3. **Why this practical-null?** It is deliberately tiny relative to the legal-space entropy while still requiring a measurable likelihood improvement. It prevents statistically visible but operationally negligible effects from reopening unconstrained model work.
4. **What does 0.01 bits/issue mean?** It is 0.049803% of full entropy and a 0.6956% geometric-mean likelihood improvement, with no universal probability-point equivalent.
5. **Why theoretical uniform as the primary null?** It is fixed, training-free, auditable, and exactly matches the legal draw mechanism.
6. **Why is empirical base rate secondary?** It is estimated and can absorb finite-sample fluctuations. It is useful as a harder sensitivity comparator but cannot replace the exact legal null.
7. **Why is TopK not primary?** TopK single-issue hits are sparse, threshold-dependent, and invite post-hoc selection. Proper probability scores measure all predictions.
8. **Why cannot pair analysis decide the top-level hypothesis?** There are 528 pairs, low event rates, dependence, and a high selection burden. Even FDR-surviving pairs remain secondary evidence.
9. **What can leak future information?** Global scaling, binning, imputation, feature selection, base rates, smoothing, calibration, hyperparameter selection, window choice, and revised history applied retrospectively. Every fitted object is nested inside outer training.
10. **How is outer-result-driven selection prevented?** Model/hyperparameter/window candidates, tie-breaks, preprocessing, and partitions are frozen now; selection uses only three-fold expanding inner validation.
11. **How are no signal and low power separated?** Practical equivalence requires the entire interval inside the margin plus sufficient P2 injected-signal power and an MDE no larger than the margin. Otherwise the result is inconclusive.
12. **How do synthetic signals avoid favoring one model?** Four mechanisms span marginal, temporal, pair, and marginal-preserving conditional structures. Null and injected data traverse the same measurement path and all allowed probes are reported.
13. **Which controls best preserve the data-generating structure?** Circular shifts and issue-block permutations preserve local time/cluster structure; number-label permutation preserves six-red draws; uniform synthetic histories preserve the exact legal mechanism.
14. **When does forward evidence gain legal identity?** Only for the first issue strictly after P2 passes when the full immutable checkpoint exists before draw availability. No issue is named in advance at P1.
15. **How can a frozen preregistration change?** Never in place. A new semantic version must record `supersedes_digest`; the old digest remains replayable and cannot be deleted.
16. **What must P2 prove before P3?** Controlled synthetic-null false positives, at least 80% power at practical strength, bounded estimator bias, deterministic replay, and passing leakage checks. Failure yields `REPAIR_MEASUREMENT_SYSTEM`, not a real-data interpretation.

## Forward identity and 2026085

Issue `2026085` remains an independent `external_wait`. It is permanently listed as retroactively ineligible for M4 forward evidence because no P1-frozen, P2-passed pre-draw checkpoint existed. Observing the draw event cannot manufacture that identity later.

## Lifecycle and fail-closed behavior

The lifecycle is `DRAFT → VALIDATED → FROZEN → SUPERSEDED`. Freeze requires a clean Git tree, records the source commit, computes a canonical digest independent of JSON key order, and writes under the digest directory. Formal `run`, `negative-controls`, `power-analysis`, and `report` commands return `phase_gate_not_satisfied` in P1/P2-ready state.

## Scope audit

- Statistical estimators implemented: **NO**
- Real data analyzed: **NO**
- Synthetic validation executed: **NO**
- Bootstrap or permutation executed: **NO**
- Model training executed: **NO**
- Production paths changed: **NO**
- Promotion Gate: **CLOSED**
- Adaptive Supervisor: **STOPPED**
- Evidence progress: **0%**

The only data access in P1 was read-only identity metadata (issue count, bounds, dates, and fixed chronological partition boundaries). No draw outcome statistic was computed.
