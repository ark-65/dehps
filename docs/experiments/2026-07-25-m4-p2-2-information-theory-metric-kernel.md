# M4-P2.2 Information-Theory Metric Kernel

## Round Contract

- Role: Engineering Agent.
- Authorized request: `engineering-m4-p2-2-metric-kernel-20260725`.
- Baseline commit: `48dbcff50c2d8addb983bb61372a27a7c11a8e2f`.
- Primary goal: freeze exactly what is measured before any P2.3 probe is connected.
- Preregistration: v1.0.1 / `6e03cd828378badda6995c6582d80165b0a4ee3b5899b97737bad1494fcf1ae1`.
- Decision policy: `824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d`.
- Synthetic manifest: `8493987cc4414414e33fb5c5ea148be1f42a1d9e57609600c4346fb642cbfa08`.
- Metric Kernel manifest: `56b9d0a62d43d167069e5222c7095383c9c5106bb3361b0b1def75cf2b6c86a2`.

## Einstein Constraint Pass

The conserved quantity is one legal issue containing exactly 33 labeled number events and exactly six positives. The null is the exact `6/33` marginal induced by uniform choice of six numbers without replacement. The smallest failing experiments are the equal-baseline, near-perfect, reversed, simultaneous-permutation, and illegal-joint fixtures. They expose unit reversal, cluster flattening, sign reversal, clipping drift, and marginal-versus-joint confusion before any model can hide those errors.

## What the Kernel Measures

The number-level score is a composite Bernoulli Log Loss. Each event is calculated stably in nats after applying the preregistered `epsilon=1e-6`; the 33 event losses are then summed into one issue. PE1's frozen reporting quantity is therefore `observed_oos_log_loss_gain_bits_per_issue`, with:

```text
gain = baseline issue loss - probe issue loss
positive = probe better
zero = equal
negative = probe worse
```

The 33 rows are not 33 independent inference samples. They are constrained members of one issue cluster. `sample_size_for_inference` is always `issue_count`, and P2.2 emits no IID standard error or confidence interval.

The exact theoretical composite baseline is:

```text
6 * -log(6/33) + 27 * -log(27/33)
= 15.646597330908634 nats/issue
= 22.57326837608838 bits/issue
```

Brier is retained at both `brier_mean_per_number_event` and `brier_sum_per_issue`. The issue sum is the later reporting quantity; improvement is baseline sum minus probe sum, so positive is better.

## Composite Versus Joint Probability

The legal complete-draw space is reused from P2.1:

```text
C(33,6) = 1,107,568
P(draw) = 1 / 1,107,568
joint uniform code length = log2(C(33,6))
                          = 20.078963846209348 bits
```

This is not the 22.57326837608838-bit composite Bernoulli baseline. A fixed-six target creates strong dependence among the 33 indicators. Multiplying marginals assigns mass to illegal zero-, one-, seven-, and 33-red outcomes, so the kernel raises `joint_probability_contract_violation` when a marginal vector is presented as a legal joint distribution.

## Probability and Calibration Contract

Inputs reject the wrong length, nonnumeric values, NaN, either infinity, values outside `[0,1]`, nonbinary targets, and targets without exactly six positives. Clipping is numerical safety only. Every issue records raw/clipped extrema, low/high clip counts, clip fraction, and epsilon separately for baseline and probe.

Calibration sufficient statistics use validated raw probabilities, not clipped replacements:

- event: probability, target, issue, red number;
- issue: mean predicted probability, predicted red count, actual count six, red-count error;
- aggregate: predicted and observed rates, calibration-in-the-large, mean predicted count, and mean absolute count error.

No bins, reliability curve, intercept, slope, ECE, isotonic model, or Platt model are selected in this round.

## Artifact and Unit Identity

The typed deterministic artifact contains NumberEventMetric, IssueMetric, and AggregateMetric layers. It records schema, source/parent digests, git commit, clean-tree assertion, preregistration and policy digests, kernel/config digests, issue count, `seed_policy=none`, exact joint code length, ordered issue sequence, and an explicit interpretation boundary.

The identity digest includes metric version, aggregation rule, epsilon, baseline, unit contract, issue cluster, and gain sign. Changing sum to mean, nats to bits, epsilon, baseline, sign, or issue aggregation changes the digest.

Only `bits_per_issue` may be compared with the frozen `[-0.01,+0.01] bits/issue` practical-null. Passing `bits_per_number_event` raises `unit_mismatch`.

PE2 is deliberately:

```text
bias_corrected_information_gain: NOT_IMPLEMENTED
reason: requires synthetic calibration / bias validation contract
eligible_for_final_pe2: false
```

Observed Log-loss Gain is not named true mutual information and is not a final bias-corrected estimator.

## P2.3 Interface

P2.3 supplies only:

- `issue_id` and identical `cluster_id`;
- a legal six-of-33 target vector;
- the exact baseline probability vector;
- a probe probability vector;
- source and parent digests.

It receives the canonical IssueMetric/aggregate artifact. Probe modules must not implement their own Log Loss or Brier formulas.

## Scope Audit

- Probe model implemented: NO.
- Bootstrap implemented: NO.
- Permutation implemented: NO.
- Injected signal implemented: NO.
- Large synthetic run executed: NO.
- Real historical data analyzed: NO.
- Production checkpoint generated: NO.
- Frozen thresholds changed: NO.
- Random source used by Metric Kernel: NO.
- Real evidence produced: NO.
- Production path changed: NO.

## Research OS State

- M4 Status: `ACTIVE / M4-P2 / RUNNING`.
- P2.1: COMPLETE.
- P2.2: COMPLETE.
- Next Ready task: `m4-p2-walk-forward-probe-harness`.
- Engineering progress: 26%.
- Evidence progress: 0%.
- Promotion Gate: CLOSED.
- Adaptive Supervisor: STOPPED.
- Old training mainline: REJECTED/FROZEN.
- Formal real-data analysis: NOT_STARTED.

## Analytical Fixtures

- Equal-to-baseline: PE1 gain `0`, Brier gain `0`.
- Better-than-baseline: PE1 and Brier gains positive.
- Worse-than-baseline: PE1 and Brier gains negative.
- Simultaneous target/probability permutation: issue sums unchanged.
- Joint probability guard: marginal product rejected.
- Exact joint code length: exponentiation recovers `C(33,6)`.

## Validation

Focused P2.2/P2 regression suite:

```text
111 passed
```

Eleven collected test cases directly cover extreme probabilities: NaN, positive/negative infinity, both out-of-range directions, zero/one clipping diagnostics, non-negativity across near-boundaries, near-perfect confidence, reversed confidence, shared-epsilon clipping, and clipped binary Brier. Additional cases cover shape, target cardinality/value, baseline, cluster, unit, and joint-contract failures.

Full local validation:

- Worker: `1676 passed, 4 skipped`.
- API: `117 passed`.
- Web: `19 passed`.
- Angular production build: passed.

GitHub CI, merged commit, and live idempotent control-plane synchronization are recorded in the completion handoff.

## Completion Format

```text
M4 Status: ACTIVE / M4-P2 / RUNNING
P2 Subphase: P2.1 COMPLETE; P2.2 COMPLETE
Next Task: m4-p2-walk-forward-probe-harness
Metric Kernel:
- Probability validation: COMPLETE
- Clipping: epsilon 1e-6, diagnostics explicit
- Number-event log loss: stable nats and bits
- Issue log loss: stable sum, bits/issue primary
- PE1: observed OOS gain; positive probe better
- Brier: sum/issue and mean/event; positive gain better
- Joint code length: 20.078963846209348 bits from C(33,6)
- Calibration statistics: deterministic sufficient statistics
- Aggregate metrics: issue-cluster sample size; no IID CI
- PE2: NOT_IMPLEMENTED
Unit Contract:
- Internal unit: nats
- Primary reporting unit: bits_per_issue
- Practical-null compatible metric: observed_oos_log_loss_gain_bits_per_issue
Artifacts:
- Schema: dehps-m4-information-theory-metric-artifact.v1
- Metric kernel version: m4-information-theory-metric-kernel-v1
- Manifest digest: 56b9d0a62d43d167069e5222c7095383c9c5106bb3361b0b1def75cf2b6c86a2
- Seed policy: none
```
