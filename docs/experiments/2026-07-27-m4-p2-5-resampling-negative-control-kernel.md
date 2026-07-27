# M4-P2.5 Resampling and Negative-control Kernel

## Round contract

Primary goal: establish one deterministic, issue-level resampling and
negative-control execution layer, integrate it into the Research Evidence
Supervisor, and prove the fixed smoke path from P2.4 artifacts to P2.6
readiness.

Non-goals: formal false-positive, power, or MDE estimation; PE2 finalization;
real-history analysis; Full-score evaluation; production checkpoints; Evidence
promotion; or changes to signal strengths, practical-null, block sizes, shift
sets, or multiplicity policy.

The preregistration audit found no ambiguity requiring repair. Version 1.0.3
already fixes the issue-level unit, non-circular moving blocks, circular
Politis-Romano stationary bootstrap, distinct tail-block permutation, circular
shift direction, plus-one tails, ties, midrank percentile, Type-7 quantiles,
and separated seed domains.

## Frozen inputs

- Preregistration:
  `4fff51c58e4a46d664e414bfe4cc0d7269c8e3712734153faec548648144d0d9`
- Decision policy:
  `824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d`
- Synthetic manifest:
  `f84c2da3565f7eda41c3782517c78211805f57ea8f3bfd00659a93c380826a3c`
- Metric Kernel:
  `56b9d0a62d43d167069e5222c7095383c9c5106bb3361b0b1def75cf2b6c86a2`
- Walk-forward Harness:
  `177a3d591b7557a4231a276bfb007f0d42a94d942824403f5376f94fe904d2ca`
- P2.4 completion:
  `328144fa1abebfee88d46dbbce6d9deb7b9f1f5834fb9a0c83cc55adef32a353`
- P2.5 Kernel manifest:
  `1cde473524d7d6dcafba64ab7b0a1d2862b56149d5f6f198c73d88b406c3071b`
- P2.4 truth inputs: all 12 identities frozen in the Kernel manifest and
  checked against their calibration datasets before any plan is built.

## Resampling unit and methods

The minimum statistical unit is one issue: its 33-number target vector,
prediction checkpoint identity, settlement identity, and cluster identity move
together. Number events are not independent observations, so bootstrapping
them separately would inflate the effective sample size and could split a
six-of-33 outcome across blocks.

Moving block bootstrap samples, with replacement, from every valid
non-circular contiguous start in an ordered issue sequence. It concatenates
whole blocks and truncates only the right overflow to exactly `N` issues. The
primary block size is `5`; frozen sensitivity sizes are `3, 5, 8, 13`, taken
unchanged from preregistration.

Stationary bootstrap is implemented as circular Politis-Romano sampling with
restart probability `1/L` for expected lengths `3, 5, 8, 13`. It is
sensitivity-only. Block permutation uses non-circular size-5 blocks, preserves
within-block order, treats a short tail as a distinct final block, and rejects
identity permutations.

## Negative controls

- NC1 moves a whole issue target under a non-identity issue bijection.
- NC2 applies one global `1..33` bijection to every issue and all represented
  target identities.
- NC3 uses
  `shifted_target[t] = original_target[(t+k) mod N]`, with target moving
  forward relative to prediction and frozen shifts `1, 2, 3, 5, 8, 13, 21`.
- NC4 supports independent, block-correlated, and permutation-derived matched
  features. It records feature-manifest identity, shape, dtype, missingness,
  empirical marginals, temporal class, and an independent seed; its function
  has no target argument.
- NC5 supports rank, quantile, and mean/variance matched synthetic/probe score
  interfaces. Target, PE1, Brier, hit-rank, and settlement are forbidden
  inputs.
- NC6 references the P2.1 synthetic-null generator and does not implement a
  second null generator.

NC3 and descriptive metric resampling are post-prediction paths. NC1, NC2,
NC4, and NC6 are marked `RETRAIN_REQUIRED_CONTROL`; their child mappings
explicitly route new prediction and settlement identities through the P2.3
Harness. P2.5 is a plan-only smoke, so it validates that route and does not
misrepresent an old settlement as a refitted result.

## Statistic, inference, and replay contracts

P2.2 remains the only Metric Kernel. P2.5 reads trusted P2.3 aggregate values
for interface validation and contains no duplicate Log Loss, Brier, PE1, or
gain formula.

Upper-tail p-values use `(1 + count(T* >= Tobs)) / (B + 1)`, lower-tail uses
`<=`, and the two-sided value is `min(1, 2*min(p_upper,p_lower))`. Ties are
inclusive. Percentiles use midrank while the empirical CDF is inclusive;
quantiles are Hyndman-Fan Type 7. Every child records endpoint, hypothesis,
unit, and multiplicity family. Smoke aggregates contain no p-value and are
ineligible for formal inference.

Bootstrap, stationary, issue-permutation, number-permutation, random-feature,
random-score, and shard identities occupy distinct deterministic domains.
Calibration, evaluation-dataset, and power-replicate domains are forbidden.
Wall-clock and best-seed selection are rejected. Replicate identity excludes
execution order; resume reuses immutable plans, retry reuses the child seed,
and shard assignment is `replicate_index mod shard_count`.

## Fixed smoke and local replay

The frozen smoke contains 22 child plans:

- moving block: 4;
- stationary: 4;
- block permutation: 3;
- NC1 through NC6: `2, 2, 2, 2, 2, 1`.

These produce nine aggregates. Every plan preserves 902 complete issue
clusters, every target remains a legal 33-vector with six positives, and all
source mappings are persisted. Re-running against the same immutable output
directory returns the same artifact graph and performs no manual digest
assembly.

The local validation identity was intentionally synthetic and dirty, so it is
not the formal mainline record:

- run:
  `9df9dfc30d1f8d6e2e418e1042118167482482c0b467bb7f7b37b30a5a87dee5`;
- completion:
  `fdaa8a947388435c5f5a65bc4b8ef1adef770256b79467dcbc1598c86227e9d9`;
- state projection:
  `fed9cec4031f488f605f5e648a083ddc04e07e7460b9dec36987d4b5ac36cadf`;
- child count: `22`;
- aggregate count: `9`;
- persisted paths: `55`.

The formal post-merge Supervisor run records its commit-bound execution, run,
all 22 child, all nine aggregate, completion, control-plane, and snapshot
digests in the immutable mainline registry and operator completion record.

## Mainline and P2.6 consumption

The integrated path is:

```text
P2.4 COMPLETE
-> P2.5 Ready
-> Research Evidence Supervisor
-> P2.5 Runner
-> plans / children / aggregates / completion
-> P2.5 COMPLETE
-> m4-p2-false-positive-and-power-runs Ready
```

P2.6 must consume this Kernel and may not redefine bootstrap, permutation,
tail, block size, shift, seed, negative-control semantics, or failure handling.
P2.5 adds measurement and control capability only: Engineering Progress moves
from 34% to 37%, Evidence Progress stays 0%, Promotion Gate stays closed,
adaptive training stays stopped, and the rejected legacy mainline stays
frozen.

## Validation

- Focused resampling, contract, supervisor, status, and regression tests:
  `171 passed`.
- Worker: `1840 passed, 4 skipped`.
- API: `117 passed`.
- Web: `19 passed`.
- Web production build: passed.
- Local runner immutable replay: passed with zero new identities.
- Formal GitHub CI and post-merge mainline execution are operator acceptance
  steps and are not claimed by the dirty local smoke.

## Scope audit

No formal false-positive experiment, power run, MDE, PE2 correction,
real-history analysis, Full-score evaluation, production checkpoint, or
Evidence artifact was produced. Calibration datasets remain
`CALIBRATION_ONLY` and ineligible for evaluation, power, false-positive,
P2-Gate, or production use.
