# M4-P1 Resampling Preregistration Contract Repair

Date: 2026-07-27

Primary role: Engineering Agent

Task: `m4-p1-repair-resampling-preregistration-contract`

Task type: `REPAIR_PREREGISTRATION_CONTRACT`

## Outcome

This round freezes the missing executable semantics for M4-P2.4, P2.5, and
P2.6 before any P2.4 truth artifact or P2.5 resampling result exists.
Preregistration v1.0.2 supersedes v1.0.1; it does not modify v1.0.1 in place.

The round is contract-only. It implements no bootstrap, permutation,
random-feature, or random-score execution path. It runs neither P2.4 nor P2.5,
creates no truth artifact or replicate, and adds no Evidence.

## Immutable identities

| Artifact | Identity |
| --- | --- |
| Previous preregistration | v1.0.1 / `6e03cd828378badda6995c6582d80165b0a4ee3b5899b97737bad1494fcf1ae1` |
| New preregistration | v1.0.2 / `a8da6bf2404d3bf213ac74d331917d5308195b7c3174b002378e1bbd849f6dfa` |
| Decision Policy | `824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d` |
| Control-plane manifest | `0c076b73b39bd3da04cc172b881ab9b39981daf42ac48a577625f70d5854e063` |
| Final resolution snapshot | `f2fea9850ffbf9a66735384242345cd25427f664e97be236499e80096e519846` |

The accepted v1.0.1 source file remains byte-identical. Its SHA-256 file hash is
`40e3dee2477fba838ee5f0f5f9edc434c68fb2623f0ddcd6a34e22a4a6111e18`
both before and after this repair.

## Frozen resampling semantics

Moving-block bootstrap is non-circular. Its primary block size is 5 and its
sensitivity sizes are 3, 5, 8, and 13. Legal source starts are the inclusive
integer range from 0 through `N-L`; only complete length-`L` source blocks are
sampled, with replacement, preserving within-block order. Concatenation stops
after reaching at least `N`, then truncates the output from the right to exactly
`N` issues. A source tail cannot become a short source block, although it may
occur inside a complete block beginning at an earlier valid start. `N<L` fails
closed with `insufficient_issues_for_block_size`.

Stationary bootstrap is the circular Politis–Romano construction. The primary
expected block length is 5, so restart probability is 1/5. The initial index and
every restart are uniform over 0 through `N-1`; continuation advances by one
modulo `N`. Expected lengths 3, 5, 8, and 13 are sensitivity-only and are
ineligible as the primary method.

Block permutation is non-circular with block size 5. Complete blocks and an
optional final short tail block are the permutation units. The tail remains
distinct, is neither merged nor split, and its length must be recorded.
Within-block order is preserved and the identity block order is forbidden.

Circular shift uses:

```text
shifted_target[t] = original_target[(t + k) mod N]
```

The canonical direction is `target_forward_relative_to_prediction`. For
`[A,B,C,D]` and `k=1`, the shifted target is `[B,C,D,A]`. Zero is forbidden,
all issues remain effective, and every frozen shift in `[1,2,3,5,8,13,21]`
must run deterministically; shift selection has no seed.

## Frozen inference semantics

PE1 uses the upper tail. Upper and lower permutation p-values are:

```text
p_upper = (1 + count(T_null >= T_observed)) / (R + 1)
p_lower = (1 + count(T_null <= T_observed)) / (R + 1)
p_two_sided = min(1, 2 * min(p_upper, p_lower))
```

Ties are inclusive. Formal aggregates require the complete frozen seed set and
fail closed when replicates are incomplete; smoke aggregates cannot emit a
formal p-value.

The inclusive empirical CDF is `count(null <= observed) / R`. The reported
midrank percentile is
`(count(null < observed) + 0.5 * count(null == observed)) / R`.
Quantiles use Hyndman–Fan type 7. Artifact fields must distinguish the inclusive
CDF, midrank percentile, upper-tail plus-one p-value, and lower-tail plus-one
p-value.

## Frozen seed-domain contract

The contract names eleven independent identities:

- `M4_P2_CALIBRATION`
- `M4_P2_EVALUATION_DATASET`
- `M4_P2_BOOTSTRAP`
- `M4_P2_STATIONARY_BOOTSTRAP`
- `M4_P2_ISSUE_PERMUTATION`
- `M4_P2_NUMBER_PERMUTATION`
- `M4_P2_CIRCULAR_SHIFT`
- `M4_P2_RANDOM_FEATURE`
- `M4_P2_RANDOM_SCORE`
- `M4_P2_POWER_REPLICATE`
- `M4_P2_SHARD_ASSIGNMENT`

Every stochastic identity includes the domain, scenario, method, replicate
index, parent run digest, and root seed-set digest. Child identity derivation is
stable across retry, resume, and shard reassignment. Wall-clock seeds are
forbidden. Domain identity separates streams even if two derived raw integers
were ever equal.

Random features are generated per scenario × replicate × outer fold, cannot
access targets, require retraining, and scope their seed to feature generation.
Random scores are generated per scenario × replicate × issue, cannot access
targets or settlement metrics, and may match only the probe-score distribution.
Independent evaluation datasets read frozen P2.4 truth parameters without
recalibration. A power-replicate root orchestrates separate child identities and
cannot be reused directly by every component.

## Decision Policy audit

The Decision Policy was not modified or superseded. It contains the frozen
decision states, priorities, thresholds, and actions, but does not hardcode the
missing tail, p-value, percentile, quantile, or seed-completeness semantics and
does not embed a preregistration digest. Those repaired definitions therefore
belong solely to the superseding preregistration.

The Decision Policy source file remains byte-identical, with file SHA-256
`f5498ffc7506b79301fb1037ddd0152aa19e6b8de954475501be1d1362e9dd64`.

## Dependency and status projection

The pre-repair projection is reproducible from the final manifest:

```text
m4-p1-repair-resampling-preregistration-contract  READY
m4-p2-injected-signal-calibration                 BLOCKED_BY_CONTRACT
m4-p2-resampling                                  DEPENDENCY_WAIT
m4-p2-false-positive-and-power-runs               DEPENDENCY_WAIT
```

Its projected phase is `M4-P1 / BLOCKED`, and the repair task is the only Ready
task.

The final source projection is:

```text
m4-p1-repair-resampling-preregistration-contract  COMPLETE
m4-p2-injected-signal-calibration                 READY
m4-p2-resampling                                  DEPENDENCY_WAIT
m4-p2-false-positive-and-power-runs               DEPENDENCY_WAIT
```

P2.4 now depends on both the completed repair task and the v1.0.2 artifact fact,
and carries the v1.0.2 digest as an input identity. P2.4 is the only Ready task.

## Einstein review

The smallest shared invariant is:

```text
same frozen input identity
+ same seed-domain identity
+ same preregistered resampling and inference semantics
= one replayable statistical interpretation
```

The failure conditions are explicit: short input for a block size, incomplete
formal seed sets, identity block permutations, zero shifts, wall-clock seeds,
target access by random controls, and any silent semantic default all fail
closed. No result was available or inspected while selecting these rules, so
the repair cannot encode a result-driven choice.

## Scope and governance audit

- P2.4 executed: NO
- Truth artifacts generated: NO
- P2.5 implemented: NO
- Resampling executed: NO
- Replicates executed: NO
- Real historical data analyzed: NO
- Frozen primary thresholds changed: NO
- Practical null changed: NO
- Signal strengths changed: NO
- Primary block size changed: NO
- Frozen shift set changed: NO
- Power target changed: NO
- DDL added: NO
- Evidence Progress: 0%
- Promotion Gate: CLOSED
- Adaptive Supervisor: STOPPED
- Old training mainline: FROZEN

Engineering Progress remains 30%. This governance repair has zero engineering
increment and zero evidence increment.

## Validation contract

Focused tests cover immutable v1.0.1 replay, v1.0.2 supersession and digest,
required schema fields, every frozen resampling rule, plus-one and tie
semantics, CDF/midrank fixtures, quantile identity, all seed domains, disjoint
domain pairs, deterministic child derivation, retry/resume/shard stability,
target-access boundaries, pre/post repair Ready Queue states, progress
separation, and unchanged governance.

Repository-wide Worker, API, Web, build, and GitHub checks are acceptance gates.
Their final results are reported with the merged change rather than encoded as
scientific Evidence.
