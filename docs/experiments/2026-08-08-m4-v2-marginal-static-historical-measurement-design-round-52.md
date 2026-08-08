# M4 v2 marginal-static historical measurement design — Round 52

Date: 2026-08-08

Role boundary: Research Request 362 / Execution 283 -> Engineering Request 363 /
Execution 284

Primary goal: freeze and mainline-integrate the result-blind historical
measurement design authorized by the Round-51 Repair-v2 health PASS, while
stopping at a separate historical preregistration task.

## Scope and non-goals

This round designs the historical measurement; it does not execute it. It reads
only issue/date metadata observed during Research and reads no red or blue
outcome values during the canonical capability. It executes zero historical
folds and zero bootstrap replicates, creates no Evidence or accepted model,
does not promote Prediction-v2, does not enter P3, and performs no production
action.

The canonical design binds eight immutable parent identities: its source
contract, the Repair-v2 PASS execution and decision, the marginal-static
contract execution and estimator contract, the Measurement Contract v2 design
execution and gate compiler, and preregistration v1.0.3.

## Historical boundary and exact design

The metadata-only audit observed 3,487 unique dated issues from `2003001`
(2003-02-23) through `2026090` (2026-08-06). The frozen existing dataset cutoff
ends at `2026084` (2026-07-23), so exactly 3,481 rows are in scope and the six
later rows `2026085` through `2026090` are excluded. The ordered issue/date
metadata SHA-256 through the cutoff is
`437ffb9d03ca844e0564dd147050e6668bf600fc6e601c6e4dcc0753b65fe2fe`.

The exact walk-forward design is:

- ordinals 1-900 (`2003001`-`2009075`): initial strict-prior training;
- ordinals 901-3481 (`2009076`-`2026084`): 2,581 one-issue outer folds;
- each fold fits only ordinals 1 through `t-1`, persists a virtual retrospective
  checkpoint, and exposes target `t` only afterward;
- current-target, future-target, and post-cutoff access are hard failures;
- failed or missing folds fail closed.

The candidate is the frozen `EXPANDING_LEGAL_MARGINAL_ALPHA_1` estimator,
`q_i(t)=(c_i(t-1)+2/11)/(n(t-1)+1)`, with exact probability-sum identity 6.
The adjacent baseline is the legal-uniform marginal probability `2/11`. The
endpoint is the issue-level sum of 33 Bernoulli log2 score differences in
bits/issue; it is explicitly not a joint-information claim.

## Frozen inference and stability

The issue is the resampling cluster; treating 33 number-event rows as
independent is forbidden. The fixed Holm family retains all three primary branch
endpoints, assigning p=1 to absent or invalid branches. The marginal-static
primary null is `Delta <= 0.01 bits/issue`, with a one-sided upper test,
non-circular moving-block bootstrap length 5, block sensitivities 3/8/13,
stationary-bootstrap sensitivities 3/5/8/13, and 2,000 future replicates.

Positive evidence requires the complete health-passing run, distinct candidate
and baseline, Holm-adjusted p<=0.05, and a simultaneous lower bound above 0.01.
Negative evidence requires the separate one-sided Bonferroni equivalence upper
bound below 0.01, at least 0.8 equivalence power at zero, and MDE<=0.01.
Non-significance without that equivalence power is INCONCLUSIVE.

Chronological stability is frozen before result access:

- halves: 1,291 issues (`2009076`-`2017139`) and 1,290 issues
  (`2017140`-`2026084`);
- thirds: 861, 860, and 860 issues, ending respectively at `2015016`,
  `2020111`, and `2026084`.

Global number relabeling is an equivariance check, while issue-block permutation,
circular target shift, and matched random score are diagnostics. None receives
decision credit or replaces the legal-uniform primary baseline.

## Gauss–Riemann cross-review

Historical boundary: Gauss and Riemann are historically grounded reasoning
lenses, not literal minds or complete reconstructions.

### Task frame and historical boundary

The claim under design is conditional historical marginal information gain for
one frozen prequential trajectory. The legal object is an unordered 6-subset of
1..33, with 1,107,568 legal subsets, no within-draw duplicates, and no blue ball.
The design cannot support a forward guarantee or a temporal/joint claim.

### Gauss pass — verification

- Strongest claim: the arithmetic boundary is exact: 3,481 eligible issues,
  900 strict-prior training issues, and 2,581 one-step evaluation folds.
- Weakest assumption: the previously frozen red-only dataset digest will still
  match at preregistration/execution time; this design binds but does not inspect
  it.
- Null and leakage obligations: use the legal-uniform adjacent baseline, preserve
  the fixed three-branch family, resample issues rather than 33 pseudo-rows, and
  reject any current/future/post-cutoff target access.
- Numerical obligation: preserve the exact sum-6 identity without clipping,
  renormalization, hyperparameter search, or post-result partition changes.

### Riemann pass — structure

- Strongest claim: expanding strict-prior counts define a transparent
  prequential trajectory whose historical geometry can be measured without
  inventing latent state.
- Weakest assumption: static marginal geometry may be invariant under global
  relabeling and weakly affected by some order controls, so those controls cannot
  serve as decisive null generators.
- Structural obligation: keep chronology, half/third partitions, and the
  post-cutoff forward cohort separate; the retrospective virtual checkpoint is
  an ordering proof, never forward Evidence.

### Cross-review, disagreement, and synthesis

Gauss would prefer every null control to offer exact inferential calibration;
Riemann notes that relabeling and some permutations preserve much of the static
marginal object and are primarily invariance or alignment diagnostics. The
disagreement is resolved by granting them zero decision credit and keeping the
legal-uniform baseline and issue-cluster inference primary.

The smallest shared conclusion is to freeze the exact 3481/900/2581 design,
bind the existing dataset digest for next verification, preserve the fixed
partitions and failure rules, read no outcomes now, and route only to a separate
result-blind historical preregistration.

Next verification: the preregistration capability must verify the frozen dataset
digest and code/source identities before any historical result is exposed.

## Implementation

- Pure design module with exact source-byte and parent-identity validation.
- Source contract digest:
  `ad07217101c613d1b7afa273054adb7a8c3fe3a7c6a36eea4012bbbae2483753`.
- Source-set digest:
  `2824ca2231bba937634eb865fdf2e25f35b006c08030ea16e0d5ad16270c1b8a`.
- Canonical source manifest digest:
  `e483329a916e02374dd4735c58a32d08a0e922d31cd5abf554d5a3d779bfde56`.
- Additive migration revises exactly the existing historical-design placeholder,
  adds exactly the separate preregistration task, and adds one source fact.
  Engineering dry-run reports zero state regression, fact deletion, or
  unallowlisted definition rewrite.
- Supervisor execution registers dataset boundary, walk-forward design,
  inference design, completion, and mainline execution artifacts. Replay rebuilds
  and compares all five identities.

## Validation

- New capability: 7 passed.
- Adjacent M4/Supervisor surface: passed.
- Ruff, compileall, source-byte verification, additive migration dry run, and
  `git diff --check`: passed.
- Full non-retired Worker mainline: 2,115 passed, 4 skipped, 4 warnings.
  The first full pass exposed one exact source-partition count that increased by
  one for the new audit module; the count and total coverage proof were updated,
  75 focused hardening/design tests passed, and the complete suite then passed.

## Mainline integration matrix

| Link | Engineering state |
| --- | --- |
| Goal | Bound to `M4_INFORMATION_THEORY_EVIDENCE` |
| Resolver | Exact Repair-v2 PASS and seven additional immutable inputs required |
| Ready Queue | Design revision becomes the sole Ready task after additive migration |
| Supervisor | Capability registered; live merged execution pending |
| Capability | Result-blind historical design implemented |
| Artifacts | Boundary + walk-forward + inference + completion + execution |
| Status | Exact 3481/900/2581 contract and zero-work boundary projected |
| Next Task | Separate historical preregistration declared |
| Replay | Deterministic five-artifact reconstruction implemented; live replay pending |

Integration answer at Engineering completion:

```text
NO — INTEGRATION_PENDING
```

The capability becomes complete only after a ready PR merges, a fresh merged
unified Research Evidence Supervisor executes it from the durable Ready Queue,
the design fact makes the preregistration task Ready, and replay verifies all five
registered identities.
