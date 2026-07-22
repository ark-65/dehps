# Seven-Red Domain Contract v1 — 2026-07-22

## Round contract

- Primary goal: establish the immutable, deterministic domain core for the research-only
  `seven_red_compound_top10` line.
- Engineering authorization: Agent Request `172`
  (`engineering-seven-red-domain-contract-v1`), execution `93`.
- Base commit: `9c50359f17a23822c83393b28064e29479426dd5`.
- Role: Engineering Agent.
- Status: `RESEARCH_ONLY`.
- Production impact: none.

## Implemented boundary

The new `dehps.seven_red` package contains only domain and evidence primitives:

- a frozen seven-red candidate value with seven strictly increasing integers in `[1,33]`;
- a frozen six-red combination value for expansion and actual outcomes;
- deterministic full SHA-256 candidate and combination identities;
- the existing Candidate Contract's zero-based full-universe lexicographic IDs and uint64 masks;
- deterministic lexicographic `C(7,6) = 7` expansion with source, ordinal, omission, and
  provenance-bound expansion identity;
- an immutable, digest-addressed expansion batch that rejects duplicate source candidates and
  duplicate expanded six-red coverage;
- deterministic settlement against one actual six-red outcome, including the seven-red
  `hit_count`, all seven expanded match counts, and a content digest;
- an executable ContractRef, normative definition, and golden suite.

The seven-red universe is `C(33,7) = 4,272,048`. The implementation reuses the generic Candidate
Contract with `(domain_size=33, pick_count=7)` rather than creating a second ranking, mask, or record
serialization convention. It deliberately does not use the legacy `normalize_red_numbers` helper:
that helper sorts and coerces input, while this contract must fail closed on noncanonical order,
duplicates, non-integers, and out-of-range values.

## Expansion and settlement invariants

For a seven-red candidate with `h` numbers present in the actual six-red outcome:

- omitting one of the `h` matching numbers produces `h` expanded combinations with `h-1` matches;
- omitting one of the other `7-h` numbers produces `7-h` expanded combinations retaining `h`
  matches;
- the expanded counts always sum to seven.

The tests prove the required cases programmatically:

| Seven-red hit | Expanded result |
| ---: | --- |
| 6/7 | 1 red6 and 6 red5 |
| 5/7 | 2 red5 and 5 red4 |
| 4/7 | 3 red4 and 4 red3 |

Batch expansion fails closed if two different seven-red candidates share a six-red core. A valid
batch therefore has `expanded_unique_count = source_count × 7` and
`effective_coverage_ratio = 1.0`.

## Probability and cost boundary

This round makes no prediction or expected-return claim. One seven-red set expands to seven ordinary
six-red combinations. Ten unique seven-red sets can cover at most 70 unique six-red combinations,
costing 140 yuan at 2 yuan per entry. Under uniform random selection and complete uniqueness, that
red6 probability is the same as 70 unique ordinary six-red singles; the research question is future
model ability to select useful seven-red supersets, not a mathematical advantage created by the
compound format itself.

## Validation

- Focused final contract suite:
  `apps/worker-python/.venv/bin/python -m pytest -q tests/test_seven_red_domain.py`
  — `19 passed in 0.70s`.
- Complete worker regression:
  `apps/worker-python/.venv/bin/python -m pytest -q`
  — `1396 passed, 4 skipped, 4 warnings in 160.90s`.
- The four warnings are the existing Python 3.14 `multiprocessing` warning about `fork()` from a
  multi-threaded process; this round introduced no new warning class.
- Source-scope audit found no import or integration outside the new research package and its focused
  test module.
- No database, API, web, CLI, scheduler, watchdog, forward-wait, supervisor, training, scoring,
  prediction, or production TopK path was changed or operated.

## Explicit non-goals and remaining work

This round does not implement a scoring model, Raw Top10, Diversified Top10, diversity metrics,
random baselines, six-red Top70 comparisons, walk-forward evaluation, statistical significance,
shadow mode, database persistence, or buying advice. It does not create Evidence or decide whether
the long-term hypothesis is supported.

The next round must use a new approved Agent Request. The intended next dependency is the immutable
candidate-list and Top10 snapshot layer built on this domain contract; it must not modify production
TopK behavior.
