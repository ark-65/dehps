# Seven-Red Score-Pool Compiler v1 — 2026-07-22

## Round contract

- Primary goal: compile one explicitly bounded seven-red research candidate pool from one verified
  six-red FullScore configuration column.
- Engineering authorization: Agent Request `176`
  (`engineering-seven-red-score-pool-compiler-v1`), Execution `97`.
- Dependencies: the canonical seven-red domain, Raw Top10 candidate-list ABI, and existing verified
  FullScore Grid Runtime Artifact.
- Role: Engineering Agent after a separate Reviewer decision.
- Status: `RESEARCH_ONLY`, deterministic bridge contract, not a trained strategy.
- Production impact: none.

This round does not choose parameter values from history. `M=seed_top_n` and `P=pool_top_n` are
mandatory constructor arguments; neither has a default or recommendation. `P` must be at least ten
so the resulting pool can legally feed the existing Raw Top10 and diversified-selector contracts.

## Verified six-red source boundary

`SixRedFullScoreVector.from_full_score_grid(...)` first invokes the existing FullScore verifier with
the corresponding `VerifiedRuntimePackage` and `WeightMatrix`. It then requires the complete
`C(33,6)=1,107,568` candidate universe and selects exactly one explicit configuration column.

The bridge converts its round-8 binary64 scores to immutable signed `int64` ticks at scale
`100,000,000`. Reconstruction to round 8 must equal the source column exactly; non-round-8 values
and tick overflow fail closed. The vector identity binds:

- FullScore artifact, payload, and matrix digests;
- Runtime Envelope and candidate-package digests;
- history snapshot and strict latest issue;
- window artifact and window-spec digests;
- weights digest, configuration index and configuration count;
- source code commit and the complete score-tick vector digest.

## Deterministic Top-M generation

The compiler ranks all six-red rows by exact score tick descending, then six-red `lex_id`
ascending. It retains exactly the explicit Top-M seeds. Each seed produces its 27 legal seven-red
supersets by adding each number in `[1,33]` not already present. Supersets are canonicalized and
deduplicated by seven-red `lex_id`; the snapshot retains every contributing seed rank.

The target issue is an explicit seven-digit input, while the bound source history must end strictly
before it. There is no target outcome, settlement result, random seed, timestamp, or post-target
field in the compiler interface.

## Exact constituent-mean score

For each deduplicated seven-red candidate, the compiler obtains all seven canonical six-red subset
IDs and their source ticks. With integer sum `S`, its score is the exact rational value:

```text
mean = S / (7 * 100,000,000)
```

Ranking never compares floats. The nearest round-8 ranking tick is derived directly from integer
division:

```text
q, r = divmod(S, 7)
ranking_tick = q + 1 if 2*r > 7 else q
```

Because seven is odd, an exact half-tick tie cannot occur. This also handles negative sums without
an asymmetric truncation rule. Candidates rank by this tick descending and then seven-red
`lex_id` ascending. Exactly P rows are retained; insufficient deduplicated candidates fail closed.

The selected rows are projected into the existing `ScoredSevenRedCandidate` and
`PreScoredSevenRedCandidateList` ABI without changing its Raw Top10 ranking contract. Each row also
retains its seven constituent IDs and ticks, exact sum, ranking tick, source seed ranks, and a
domain-separated digest. `SevenRedScorePoolVerifier` deterministically recompiles a snapshot from
its bound source and rejects mixed-source or stale-row artifacts.

## Dual mathematical review

### Task frame

This round asks only whether a bounded, replayable bridge can turn the existing complete six-red
score field into a legal seven-red pool. It does not ask whether the mean score predicts a draw or
whether any M/P pair is useful.

### Historical boundary

The Gauss and Riemann passes below are historically inspired verification and structural lenses,
not literal reconstructions or evidence for predictive merit.

### Gauss pass: verification

- Strongest claim: universe cardinality, Top-M order, 27-superset count, exact deduplication,
  constituent arithmetic, chronology, and replay identities are mechanically checkable.
- Weakest assumption: an arithmetic mean of seven constituent six-red scores is a meaningful
  seven-red score; this round only freezes it as a transparent null bridge.
- Required checks: exact negative and positive rounding, lexicographic ties, source-column binding,
  full-universe cardinality, mutation detection, and no target outcome path.
- Boundary: fixed-point exactness proves deterministic computation, not calibration or lift.

### Riemann pass: structure

- Strongest claim: Top-M superset closure creates a connected local neighborhood around strong
  six-red seeds while preserving shared-parent multiplicity as explicit provenance.
- Weakest assumption: useful seven-red candidates lie near individual high-scoring six-red rows;
  a combination with seven moderately strong constituents could be excluded before aggregation.
- Required checks: deduplication geometry as M grows, candidate-family collapse, source-seed
  multiplicity, and coverage discontinuities at Top-M boundaries.
- Boundary: the pool is a search-space restriction, not a model of the full seven-red geometry.

### Cross-review and disagreement

Gauss requires future outer-window comparison against the same equal-cost controls before any
performance language. Riemann warns that Top-M truncation may distort the geometry before the mean
aggregator sees it. Their shared conclusion is deliberately small: the compiler is acceptable as a
deterministic research input whose M/P sensitivity remains untested.

The unresolved issues are explicit:

- neither M nor P has been selected or shown stable;
- mean aggregation is transparent but not empirically justified;
- Top-M seed truncation can omit globally competitive constituent portfolios;
- increasing M changes both pool size and overlap geometry discontinuously;
- no walk-forward, null model, uncertainty interval, or equal-cost outcome comparison exists yet.

## Deterministic evidence

Focused fixtures verify:

- one seed produces exactly 27 unique legal supersets;
- the first two lexicographic six-red seeds produce 54 occurrences but 53 unique candidates;
- their shared `(1,2,3,4,5,6,7)` candidate retains both source ranks;
- exact sums `10/7` and `-13/7` map to ranking ticks `1` and `-2`;
- score and seed ties resolve by lower canonical `lex_id`;
- replay is identical and a source-vector substitution is rejected;
- invalid M/P, writable or incomplete vectors, non-round-8 source values, insufficient P, and
  noncausal target issues fail closed.

Frozen normative contract digest:
`2cc06af78b195391ed6f0aa762cc220225c1e5bc128b6dd96bd7103ad22af59a`.

The all-zero full-universe replay fixture with explicit `M=2`, `P=10` freezes:

- source-vector digest:
  `3e7c397c6c9cdfbfe2c093e57bbf24a043f421ed8d0d75ce2db31c2ae7aaf29f`;
- configuration digest:
  `7052f65b9f42fb8f8cc5e989e773f085be0d4977661f5cde2e19748fef4c90da`;
- candidate-pool digest:
  `dff8be9ae00300481e411ac02bddfc96199f7feee1622dddfd8f448179f0aee1`;
- compiler snapshot digest:
  `83aef5541caf520f80e97e3ad681242a9e9f7df76f1e694b74c3c194c6ccb0c5`.

## Validation

- Focused compiler and all downstream seven-red selector/audit tests:

  ```bash
  apps/worker-python/.venv/bin/python -m pytest -q \
    apps/worker-python/tests/test_seven_red_scoring.py \
    apps/worker-python/tests/test_seven_red_raw_top10.py \
    apps/worker-python/tests/test_seven_red_diversity.py \
    apps/worker-python/tests/test_seven_red_diversified.py \
    apps/worker-python/tests/test_seven_red_domain.py
  ```

  Result: `93 passed in 3.81s`.
- `py_compile`, `git diff --check`, and a 119-column source audit passed.
- Complete Worker regression: `1471 passed, 4 skipped, 4 warnings in 172.36s`. The warnings are
  the existing Python 3.14 multiprocessing warning about `fork()` from a multi-threaded process;
  this round introduced no new warning class.

## Explicit limitations

This round does not train or recommend M/P, introduce an alternative score aggregator, evaluate a
target draw, run walk-forward, perform statistical tests, compare Raw Top10, Diversified Top10,
six-red Top70, random-from-pool, or uniform-legal controls, create Evidence, decide a hypothesis,
recommend a bet, or integrate with database, CLI, API, web, scheduler, supervisor, or production
TopK.
