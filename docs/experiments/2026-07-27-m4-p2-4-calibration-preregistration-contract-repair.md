# M4-P2.4 Calibration Preregistration Contract Repair

Date: 2026-07-27

Primary role: Engineering Agent

Task: `m4-p1-repair-injected-signal-preregistration-contract`

Task type: `REPAIR_PREREGISTRATION_CONTRACT`

## Outcome

The P2.4 entry audit failed closed before any injected-signal calibration ran.
Preregistration v1.0.2 named the strengths and mechanisms but did not contain
an executable absolute calibration tolerance, relative tolerance, Monte Carlo
uncertainty tolerance, or final information-coordinate binding. The accepted
P2 synthetic manifest also contained none of those fields and still referenced
the older preregistration identity.

This contract-only round freezes the missing semantics in preregistration
v1.0.3 and synthetic run manifest v1.0.1. It does not implement or execute a
generator, solve a parameter, create a truth artifact, run a probe, or add
Evidence.

## Immutable identities

| Artifact | Identity |
| --- | --- |
| Previous preregistration | v1.0.2 / `a8da6bf2404d3bf213ac74d331917d5308195b7c3174b002378e1bbd849f6dfa` |
| Repaired preregistration | v1.0.3 / `4fff51c58e4a46d664e414bfe4cc0d7269c8e3712734153faec548648144d0d9` |
| Previous synthetic manifest | v1.0.0 / `8493987cc4414414e33fb5c5ea148be1f42a1d9e57609600c4346fb642cbfa08` |
| Repaired synthetic manifest | v1.0.1 / `f84c2da3565f7eda41c3782517c78211805f57ea8f3bfd00659a93c380826a3c` |
| Decision Policy | `824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d` |
| Control-plane manifest | `0c1b98cebbe0908eeba5e1f29a0edc6f61d92dace47879acb1e36396ad589c25` |
| Source baseline | `35e905c405d28d0d560f9d8f9bf023a4ebb3e396` |

The accepted v1.0.2 preregistration and v1.0.0 synthetic manifest are retained
as separate immutable files. Neither is edited in place.

## Frozen information definitions

All three injected strengths bind to:

```text
joint_draw_information_bits_per_issue
= I(S_t ; Y_{t+1})
= sum_s P(s) sum_y P(y|s) log2(P(y|s) / P(y))
```

The sum is over the exact legal `C(33,6)` draw space.

The composite number-event diagnostic is the sum of the 33 individual binary
event mutual informations. It is not interchangeable with the joint draw
information. The IS3 pair diagnostic is the information in the frozen
pair-group event; because the IS3 law is uniform within the event and non-event
strata, it equals the joint draw information for that mechanism.

Conditional and unconditional KL diagnostics use base-2 units and therefore
remain in bits per issue.

## Frozen calibration and numerical tolerances

| Contract item | Frozen value |
| --- | ---: |
| Absolute calibration error | `1e-10` bits/issue |
| Relative calibration error | `1e-6` |
| Probability normalization | `1e-12` |
| Null-limit residual | `1e-15` |
| Unconditional number marginal deviation | `1e-12` |
| IS4 conditional number marginal deviation | `1e-12` |
| Expected selected-count deviation | `1e-12` |
| MC maximum standard error | `0.00025` bits/issue |
| MC agreement envelope | `4 * SE + 1e-10` |
| MC maximum sample count | `8,388,608` |

Calibration must pass both the absolute and relative error conditions. The
independent Monte Carlo audit cannot change the solved parameter. It uses only
the `M4_P2_CALIBRATION` seed domain and an immutable doubling schedule.

The solver is deterministic bisection with a required bracket, 128 maximum
iterations, `1e-14` parameter-width tolerance, and a 65-point monotonicity
audit. Missing brackets fail as `REPAIR_INJECTED_SIGNAL_CALIBRATION`;
extrapolation is forbidden.

## Frozen mechanism geometry

IS1 shifts the exact inclusion probability of number 1 by `+/- delta` under a
balanced state. Draws are uniform within the legal contains/excludes strata.

IS2 partitions all legal draws into two equal lexicographic-rank halves. The
state of issue `t` changes the probability that issue `t+1` occupies the same
half. The state is available through `t`; the target is `t+1`, and P2.3's
timestamp guard is mandatory in smoke execution.

IS3 uses the frozen pair group `{(1,2),(3,4)}` and the event that at least one
pair is complete. The balanced state shifts that event probability by
`+/- delta`; draws are uniform within the two exact legal strata. The
`PAIR_DOMINANT` label additionally requires maximum single-number information
to be no more than 10% of pair information and maximum conditional marginal
shift to be no more than 0.01. Failure changes the description, not the
calibration target.

IS4 uses `K = |Y intersect {1..16}|` and weights

```text
g(K) = [219/221, -1, 1, -1, 1, -219/221, 1]
P(Y | S) = P0(Y) * (1 +/- lambda * g(K))
```

Exact hypergeometric identities give both
`sum P0(K) g(K) = 0` and `sum P0(K) K g(K) = 0`. Consequently the conditional
laws normalize, every number marginal is preserved, the expected selected
count remains six, and the balanced unconditional mixture is exactly the legal
uniform null.

## Gauss–Riemann cross-review

Historical boundary: Gauss and Riemann are used as historically inspired
verification lenses, not literal minds and not scientific authority.

Task frame: repair the missing executable semantics before any output exists,
without changing the frozen strengths, nulls, or downstream decision rules.

Gauss pass — strongest claim: exact legal-space sums, immutable tolerances,
bracketed solving, residual tests, and seed isolation make every calibration
claim arithmetically falsifiable. Weakest assumption: binary state mechanisms
must still span the strongest 0.05-bit target inside strictly positive
probability bounds. Required test: prove brackets and monotonicity for all
twelve scenarios before accepting any truth artifact.

Riemann pass — strongest claim: binding all strengths to joint draw information
provides one invariant coordinate across four different conditional
distribution geometries. Weakest assumption: diagnostic projections may hide
structure if interpreted as replacement targets. Required test: record joint,
composite, pair, and marginal diagnostics separately for every scenario.

Cross-review: the Gauss lens rejects any tolerance selected after calibration
or any unbounded Monte Carlo assertion. The Riemann lens rejects comparing
mechanisms in different information coordinates or naming four aliases of one
generator.

Disagreement: whether every mechanism will satisfy all target brackets remains
an explicit implementation-time proof obligation. No calibration output is
available in this round, so the issue remains testable rather than resolved by
post-hoc adjustment.

Smallest shared conclusion: P2.4 may resume only against v1.0.3 and synthetic
manifest v1.0.1, with exact legal-space joint truth as primary, alternative
projections as diagnostics, and Monte Carlo restricted to independent
confirmation.

Next verification: implement each generator independently, verify legal
six-of-33 output, probability normalization, null limits, symmetry,
monotonicity, brackets, solver residuals, marginal diagnostics, deterministic
truth replay, and the P2.3/P2.2 smoke path before formal supervisor completion.

## Dependency and status projection

Before this repair completes:

```text
m4-p1-repair-injected-signal-preregistration-contract  READY
m4-p2-injected-signal-calibration                      BLOCKED_BY_CONTRACT
m4-p2-resampling                                       DEPENDENCY_WAIT
m4-p2-false-positive-and-power-runs                    DEPENDENCY_WAIT
```

After the repaired artifacts are available:

```text
m4-p1-repair-injected-signal-preregistration-contract  COMPLETE
m4-p2-injected-signal-calibration                      READY
m4-p2-resampling                                       DEPENDENCY_WAIT
m4-p2-false-positive-and-power-runs                    DEPENDENCY_WAIT
```

P2.4 now depends on the completed repair, v1.0.3, and synthetic manifest
v1.0.1. It remains the only Ready task.

## Scope and governance audit

- P2.4 executed: NO
- Injected generators implemented: NO
- Calibration parameters solved: NO
- Truth artifacts generated: NO
- P2.3/P2.2 smoke executed: NO
- Resampling executed: NO
- Power or false-positive runs executed: NO
- Real historical data analyzed: NO
- Evidence created: NO
- Signal strengths changed: NO
- Practical null changed: NO
- Decision Policy changed: NO
- Engineering Progress: 30%
- Evidence Progress: 0%
- Promotion Gate: CLOSED
- Adaptive Supervisor: STOPPED
- Production action: none
