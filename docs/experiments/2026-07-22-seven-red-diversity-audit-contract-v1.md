# Seven-Red Diversity Audit Contract v1 — 2026-07-22

## Round contract

- Primary goal: add an immutable, outcome-blind structural audit over a complete pre-scored
  seven-red candidate pool and its frozen Raw Top10.
- Engineering authorization: Agent Request `174`
  (`engineering-seven-red-diversity-audit-contract-v1`), Execution `95`.
- Dependencies: completed Request `173`, `seven-red-domain.v1.0.0`, and
  `seven-red-raw-top10.v1.0.0`, merged commit
  `5a98e78429368778fd021acdac489fd58bc93140`.
- Role: Engineering Agent after a separate Reviewer approval.
- Status: `RESEARCH_ONLY` and observational only.
- Production impact: none.

## Implemented artifact

`SevenRedDiversityAuditSnapshot` binds two exact source identities:

- the complete canonical `PreScoredSevenRedCandidateList` digest;
- the `RawSevenRedTop10Snapshot` digest whose source must equal that candidate list.

It derives separate `SevenRedGeometryMetrics` for the complete pool and the exact ten Raw Top10
candidates. The audit does not change a candidate, rank, raw score, normalized score, row digest, or
source digest. The ten original Raw entries are retained verbatim in the audit identity.

The Artifact contains no target draw, settlement, history window, seed, generated timestamp,
selector, threshold, or mutable runtime input. Equal source Artifact bytes therefore reproduce the
same content and digest.

## Exact metric contract

For each audited set of `B` distinct seven-red candidates, the Artifact records:

- all 33 red-number occurrence counts and exact maximum exposure numerator and denominator;
- the exact pairwise seven-red intersection histogram `H_0 ... H_6`;
- exact shared-core pair counts for core sizes one through six;
- unique pair and triple core counts, legal and attainable denominators, maximum multiplicity, and
  all tied maximum cores;
- all `7B` deterministic six-red expansion slots, unique expansions, duplicate slots,
  multiplicity histogram, and every colliding six-red core with its canonical source identities;
- a domain-separated candidate-set digest, collision digest, and audit snapshot digest.

Decimal means, coverage rates, and concentrations are explicitly derivative summaries rounded to
ten digits. Integer counts, histograms, numerators, and denominators are the normative evidence.

## Gauss-style proof obligations

### Object

The object is a finite set of canonical seven-element subsets of a 33-element red-number universe.
Each candidate deterministically contributes its seven six-element subsets.

### Known invariants

For every core size `k` from one through six, let `m(c)` be the number of candidates containing
core `c`, and let `H_j` be the number of candidate pairs whose intersection has size `j`. Then:

```text
S_k = sum over k-cores c of C(m(c), 2)
    = sum over j >= k of C(j, k) * H_j
```

The implementation computes each exact `S_k`, recovers `H_6 ... H_1` by descending binomial
inversion, and sets `H_0 = C(B,2) - sum(H_1 ... H_6)`. Negative or inconsistent counts fail closed.
This costs a fixed 126 non-empty proper-subset emissions per candidate rather than comparing every
candidate pair.

For expansion coverage:

```text
total expansion slots = 7B
duplicate slots = total slots - unique six-red expansions
H_6 = sum over six-red cores c of C(m(c), 2)
```

The final identity follows because two distinct seven-red sets share an expanded six-red ticket if
and only if their intersection contains that six-red core. Higher multiplicity is preserved rather
than flattened into a boolean duplicate flag.

### Boundary and conclusion

These are exact combinatorial identities, not empirical performance evidence. They prove that the
Artifact measures structural compression consistently. They do not prove that lower overlap,
higher unique expansion count, or any later diversified selector improves draw coverage.

## Frozen deterministic evidence

The golden pool uses the twelve milestone-2 fixture candidates. All share reds `1 ... 6`, making a
deliberately extreme multi-collision boundary:

| Scope | Candidates | Candidate pairs | Overlap-6 pairs | Unique expansions | Duplicate slots |
| --- | ---: | ---: | ---: | ---: | ---: |
| Complete pool | 12 | 66 | 66 | 73 / 84 | 11 |
| Raw Top10 | 10 | 45 | 45 | 61 / 70 | 9 |

A separate no-collision fixture uses ten candidates with five shared reds and disjoint extra pairs.
It produces exactly `70 / 70` unique expansions, zero duplicate slots, and no overlap-six pair.

Frozen identities:

- normative contract digest:
  `9cdc0b3293bfb143412d3715a6b8374fd778f3bc9d007ed2b690d7cffab1e53a`;
- golden pool candidate-set digest:
  `d2214aa750b3f38a185976c325207e9ad5a9cca4623847124df158868f69b9ad`;
- golden Raw Top10 candidate-set digest:
  `548abab8c72590a7249933b5549019c3182d7d313cdb523bc44b215bee9ab697`;
- golden audit snapshot digest:
  `bbf9b9f79465bde31277f2b59235041d93ebe8f3e8a20a8bb0f05ea6363b6287`.

## Validation

- Focused diversity audit plus both predecessor regressions:

  ```bash
  apps/worker-python/.venv/bin/python -m pytest -q \
    tests/test_seven_red_diversity.py \
    tests/test_seven_red_raw_top10.py \
    tests/test_seven_red_domain.py
  ```

  Result: `54 passed in 0.53s`.
- The focused suite includes brute-force pairwise cross-checks against the incidence inversion,
  exact no-collision and high-multiplicity cases, source permutation replay, source binding,
  immutable storage, and tamper rejection.
- Complete Worker regression: `1432 passed, 4 skipped, 4 warnings in 79.16s`. The warnings are the
  existing Python 3.14 multiprocessing warning about `fork()` from a multi-threaded process; this
  round introduced no new warning class.
- `py_compile` and `git diff --check` passed. An optional Ruff check could not run because Ruff is
  not installed in the project virtual environment (`No module named ruff`); Ruff is not a declared
  repository validation command.
- Source-scope audit found no diversity-audit import outside `dehps.seven_red`, its focused tests,
  and this report.

## Explicit limitations and next dependency

This round does not implement a diversified selector, enforce 70 unique tickets, choose a threshold
or coefficient, generate or score seven-red candidates, run a random baseline, compare six-red
Top70, settle an actual draw, run walk-forward evaluation, perform a statistical test, create
Evidence, or decide the long-term hypothesis.

The next dependency is a separately audited deterministic Diversified Top10 selection contract.
Its objective and tie-breaks must be frozen without target outcomes, and Raw Top10 must remain an
unaltered control. Equal-cost walk-forward and random baselines remain later rounds.
