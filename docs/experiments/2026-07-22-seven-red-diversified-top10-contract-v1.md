# Seven-Red Diversified Top10 Contract v1 — 2026-07-22

## Round contract

- Primary goal: implement one deterministic, parameterized greedy research backend that selects
  ten scored seven-red candidates with exactly 70 unique six-red expansion tickets.
- Engineering authorization: Agent Request `175`
  (`engineering-seven-red-diversified-top10-contract-v1`), Execution `96`.
- Dependency: completed Request `174`, `seven-red-diversity-audit.v1.0.0`, merged commit
  `810d19f36ea2b6061ff700fa90ccc6961c925ae3`.
- Role: Engineering Agent after a separate Reviewer decision.
- Status: `RESEARCH_ONLY`, parameterized backend, not a trained configuration.
- Production impact: none.

## Configuration has no default

`SevenRedDiversificationWeights` requires four explicit non-negative integer coefficients:

- source-rank quality;
- unique red-pair coverage;
- unique red-triple coverage;
- number-exposure concentration penalty.

At least one coefficient must be positive, and the vector must be primitive: its greatest common
divisor is one. This rejects scale-equivalent spellings such as `(2,2,2,2)` versus `(1,1,1,1)`.
Booleans, floats, negatives, missing or unknown fields, and all-zero vectors fail closed. The
contract publishes no default, recommended, tuned, or production coefficient vector.

The `(1,1,1,1)` vector below is a golden test fixture only. Its presence is not evidence that equal
weights are useful.

## Exact set utility

The source audit binds the complete scored pool and frozen Raw Top10. Pool source ranks use the
unchanged milestone-2 contract: normalized score rounded to eight decimals descending, then lower
seven-red `lex_id`.

For pool size `N`, a candidate at one-based source rank `r` has exact quality:

```text
q = (N - r + 1) / N
```

For a partial selected set `S` and final budget `B=10`, utility is evaluated with `Fraction`:

```text
U(S) = wq * sum(q(c), c in S) / B
     + w2 * unique_pairs(S) / min(C(33,2), 21B)
     + w3 * unique_triples(S) / min(C(33,3), 35B)
     - we * sum(number_occurrence_n(S)^2, n=1..33) / (7B)^2
```

The frozen denominators are `210`, `350`, and `4900`. Every step records the exact numerator and
denominator of each marginal and cumulative component; binary floating-point values do not decide
selection.

At each step, the backend considers only candidates whose seven six-red expansions are all new.
It chooses the largest exact marginal `Delta U`, then higher exact source quality, then lower
seven-red `lex_id`. If its greedy path cannot reach ten candidates, it fails without returning a
partial snapshot. A successful snapshot therefore proves:

```text
10 distinct seven-red candidates
70 total expansion slots
70 unique six-red tickets
0 duplicate slots
overlap_histogram[6] = 0
```

## Dual mathematical review

### Task frame

The question for this round is not whether diversity predicts draws. It is whether one auditable
backend can express a score/diversity trade-off, preserve equal-cost deduplication, and replay every
choice without outcomes or hidden defaults.

### Historical boundary

The following Gauss and Riemann passes are historically inspired verification and structural
lenses. They are not literal reconstructions of either mathematician and their authority is not
evidence for the selector.

### Gauss pass: verification

- Strongest claim: the source rank, rational utility, primitive parameter identity, marginal
  comparison, tie-breaks, and 70-ticket invariant are exact and mechanically testable.
- Weakest assumption: the four chosen components span a useful decision boundary; no result in this
  round establishes that.
- Requested check: independently recompute every feasible marginal on a frozen small pool, check
  coefficient-axis boundaries, and reject any hidden floating-point or iteration-order choice.
- Boundary: exact arithmetic verifies implementation behavior, not predictive merit.

### Riemann pass: structure

- Strongest claim: a set utility represents changing portfolio geometry more faithfully than a
  fixed pairwise overlap threshold.
- Weakest assumption: pair/triple coverage and squared number exposure are the right coordinates for
  the latent candidate geometry.
- Requested check: compare paths under isolated coefficient axes and inspect whether a locally good
  choice creates a later completion singularity.
- Boundary: the set-geometry framing is a structural conjecture, not a performance result.

### Cross-review and disagreement

Gauss rejects any claim of superiority without a sealed historical window, random controls,
six-red Top70, leakage checks, and uncertainty. Riemann rejects treating greedy local choices as the
shape of the global feasible-set space.

The unresolved disagreements are explicit:

- hard 70-ticket uniqueness may sacrifice source score and has not been shown beneficial;
- greedy selection can fail on one path even when another compatible ten-set might exist;
- coefficient usefulness and stability are unknown;
- the four-coordinate utility may omit relevant structure or duplicate information.

### Smallest shared conclusion

The backend is acceptable only as a deterministic parameterized experiment tool. It is not a
global optimizer, trained strategy, prediction result, or production candidate line.

### Next verification

Later rounds must define a leakage-safe parameter-selection protocol using inner historical windows,
then compare the frozen chosen configuration on untouched outer windows against Raw Top10, six-red
Top70, random-from-pool, and uniform-legal equal-cost controls. Failed greedy completions and all
weight candidates must remain in the evidence ledger.

## Frozen deterministic evidence

The golden source contains 16 scored candidates. Its four highest ranks share a common six-red core,
so the Raw control has 67 unique expansions from 70 slots. The `(1,1,1,1)` fixture chooses source
ranks:

```text
1, 5, 6, 10, 11, 7, 14, 12, 8, 15
```

The selected geometry has:

- overlap histogram `H_0 ... H_6 = [10,11,9,11,4,0,0]`;
- 172 unique pair cores and 331 unique triple cores;
- maximum number occurrence `7 / 10` candidates;
- exactly `70 / 70` unique six-red expansions.

Frozen identities:

- normative contract digest:
  `e7118cfd74402fe87de50b954a3c89d84c4465af692fc5a57f8a9b941b10f6cc`;
- golden configuration digest:
  `3fff1bf6e92ab83a43d2a363ebb196a8b71b3dbe2b2e6f600dfa39ab93f22a15`;
- golden source audit digest:
  `35aed27d888db1ec5945221d2bc1376691821e4a5fad9e3603c6c0573c46010b`;
- golden selected candidate-set digest:
  `001b37e84290d49c30435eb4d71afca11fc35e0ffc6684af8fce5a4d29b74a54`;
- golden Diversified Top10 snapshot digest:
  `df94359201cd9f431da5880fe17a222b70b098812c3c82ef28dbec947ac567cf`.

## Validation

- Focused selector plus all predecessor seven-red tests:

  ```bash
  apps/worker-python/.venv/bin/python -m pytest -q \
    tests/test_seven_red_diversified.py \
    tests/test_seven_red_diversity.py \
    tests/test_seven_red_raw_top10.py \
    tests/test_seven_red_domain.py
  ```

  Result: `77 passed in 2.19s`.
- Tests independently recompute every feasible greedy marginal, exercise each coefficient axis,
  verify the score-only boundary, freeze exact tie behavior, replay source permutations, require
  70 unique expansions, preserve source rows and Raw control, reject infeasible pools, and reject
  step, metric, fraction, configuration, and digest inconsistencies.
- Complete Worker regression: `1455 passed, 4 skipped, 4 warnings in 88.41s`. The warnings are the
  existing Python 3.14 multiprocessing warning about `fork()` from a multi-threaded process; this
  round introduced no new warning class.
- `py_compile`, `git diff --check`, line-length audit, placeholder audit, and source-scope audit
  passed.

## Explicit limitations

This round does not select weights from history, claim global optimality, generate or score seven-red
candidates, run a random baseline, compare six-red Top70, settle target draws, run walk-forward,
perform statistical tests, create Evidence, decide a hypothesis, recommend a bet, or integrate with
database, CLI, API, web, scheduler, supervisor, or production TopK.
