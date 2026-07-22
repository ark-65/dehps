# Seven-Red Random Control Contract v1 — 2026-07-22

## Round contract

- Primary goal: define deterministic multi-seed random-from-pool and uniform-legal equal-cost
  controls without reading outcomes or selecting a favorable seed.
- Engineering authorization: Agent Request `179`
  (`engineering-seven-red-random-control-contract-v1`), Execution `100`.
- Dependency: equal-cost portfolio contract and int64 ordering fix, merged through commit
  `3e8e5ff1e83473c565871ec8d8d9efd32f8c45f6`.
- Role: Engineering Agent after a separate Reviewer decision.
- Status: `RESEARCH_ONLY`, computational null generator, not a result.
- Production impact: none.

## Explicit multi-seed policy

`RandomControlSeedPolicy` requires at least two explicit unique lowercase SHA-256 digests in
ascending order. It has no default or generated seed. The frozen policy is:

```text
selection_policy = no_best_seed
```

The cohort compiler always emits both control kinds for every declared seed in this order:

```text
seed digest ascending
  -> random_from_pool
  -> uniform_legal
```

There is no API or Artifact field for ranking, filtering, omitting, or labeling a best seed.

## Random-from-pool control

The parent `SevenRedScoredCandidatePoolSnapshot` first passes deterministic replay. Every source
candidate receives a domain-separated SHA-256 priority binding:

- algorithm version;
- seed digest;
- target issue;
- parent score-pool snapshot digest;
- seven-red candidate identity.

The ten smallest priority digests are selected without replacement; a digest tie resolves by lower
seven-red `lex_id`. Selection order becomes candidate rank. Every candidate contributes all seven
canonical six-red expansions, producing exactly 70 paid slots. Expansion duplicates are preserved
and reported, not refilled.

This null is conditioned on the generated candidate pool. It does not represent the complete legal
space and must not be conflated with the uniform-legal control.

## Uniform-legal control

The legal universe contains `C(33,6)=1,107,568` canonical lexicographic six-red rows. For counter
`c` starting at zero, the sampler hashes this exact framing:

```text
ASCII domain + NUL
32 seed bytes + NUL
7 target-issue ASCII bytes + NUL
32 parent-score-pool-digest bytes + NUL
8-byte unsigned big-endian counter
```

The first eight SHA-256 output bytes form an unsigned big-endian 64-bit word `w`. To avoid modulo
mapping bias, the sampler computes:

```text
N = 1,107,568
L = floor(2^64 / N) * N
accept mapping only if w < L
lex_id = w mod N
```

Already accepted IDs are rejected and consume another counter. The first 70 distinct accepted IDs
in counter order form the portfolio. Every accepted slot records its counter and word; the
portfolio records total words consumed, modulo rejections, and duplicate rejections. Counter
overflow beyond unsigned 64-bit fails closed.

## Computational randomness boundary

Both controls are deterministic. Their null interpretation assumes domain-separated SHA-256
priorities and words behave sufficiently like pseudorandom values for this computational control.
The contract does not claim physical randomness, prove statistical independence, or certify a
randomness test suite. Reproducibility is a contract fact; randomness quality remains an assumption
to expose in later evidence.

## Immutable cohort and separate settlement

`RandomControlCohortSnapshot` binds the replay-verified parent score pool, target issue, pre-target
latest history issue, candidate-pool identity, seed policy, every portfolio digest, and canonical
seed/control order. It contains no actual issue, actual numbers, hit metric, post-target history,
timestamp, mutable RNG state, or selection result.

`RandomControlCohortSettlement` is a separate post-outcome Artifact. The actual issue must equal the
sealed cohort target. It settles every portfolio without omission and records paid-slot and
unique-ticket matched-red histograms from zero through six. Histogram totals remain 70 and each
portfolio's unique-ticket count respectively.

## Dual mathematical review

### Historical boundary

The Gauss and Riemann passes are historically inspired verification and structural lenses. They are
not literal reconstructions and provide no empirical result.

### Gauss pass: verification

- Strongest claim: seed cardinality/order, priority order, no-replacement identities, modulo
  threshold arithmetic, counters, rejection counts, 70-slot cost, cohort completeness, replay, and
  settlement totals are exact checks.
- Weakest assumption: SHA-256 values are an adequate computational pseudorandom source for the null.
- Required checks: forced modulo rejection, forced duplicate rejection, counter overflow, priority
  reference equality, all-seed completeness, and absence of best-seed selection.
- Boundary: deterministic sampling correctness does not establish null calibration on outcomes.

### Riemann pass: structure

- Strongest claim: pool-random and legal-universe-random probe two distinct source spaces while
  sharing the same 70-slot cost boundary.
- Weakest assumption: random selection inside a model-conditioned pool is an informative comparator
  for a diversified selector operating on that same pool.
- Required checks: retain source-space identity, do not mix the two null families, preserve pool
  expansion duplicates, and report every seed path.
- Boundary: the controls expose two geometries; neither is a privileged baseline by contract.

### Smallest shared conclusion

The two algorithms are acceptable as replayable computational null generators. Their later outcome
behavior, dependence, uncertainty, and adequacy as controls remain empirical questions.

## Deterministic evidence

The frozen fixture uses an all-zero six-red field, one Top-M seed, a 27-row seven-red pool, target
issue `2026002`, and explicit seed digests `aa...aa` and `bb...bb`.

For both seeds, random-from-pool produces 70 paid slots, 61 unique tickets, and nine duplicate
slots. Both uniform-legal controls consume 70 words in this fixture, with no modulo or duplicate
rejection, and produce 70 unique tickets. A forced-word test separately records one modulo and one
duplicate rejection, consuming 72 words to accept lex IDs 0 through 69.

Frozen identities:

- normative contract digest:
  `a705535bfe3b695434c132fd66e60fcc04741a03f675d07b48abd75c4ba64e2a`;
- seed-policy digest:
  `207e6925e3fee0ae5ed815232de8cc0f8fd48a45f92149398c87db65a63254fc`;
- portfolio digests in canonical order:
  `cfb944e1607f54f93d19ee60ee52085553dd89224b7bd10422aa2e26bdceee2f`,
  `8eea43a2a1a2f35e95c8220ec5d234f96fbdd14a2ca9287832f64b20521c78a5`,
  `d5c02d6dcbe2eba339fd966d02f9bceda71a18494f52ead19c960f3ef9179a98`,
  `3a4974a7ef10289a0a1947ff74ff160b35cf4d97296faf462e178f348234a081`;
- cohort digest:
  `5e9d01aeafd7e22c92133c4f089990c2c242db145ee80080e0126a1349d91714`.

## Validation

- Focused random-control tests: `11 passed in 4.09s`.
- Complete seven-red chain: `117 passed in 19.28s`.
- Complete Worker regression: `1495 passed, 4 skipped, 4 warnings in 113.19s`. The warnings are the
  existing Python 3.14 multiprocessing warning about `fork()` from a multi-threaded process; this
  round introduced no new warning class.
- `py_compile`, `git diff --check`, line-length, placeholder, and source-scope audits passed.

## Explicit limitations

This round does not recommend seeds, compare outcomes across issues, choose M/P or diversification
weights, run walk-forward, estimate uncertainty, perform statistical tests, create Evidence, decide
a hypothesis, recommend a bet, define economic value, or integrate with database, CLI, API, web,
scheduler, supervisor, or production TopK.
