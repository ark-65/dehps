# Seven-red leakage-safe inner-selection contract v1

## Round identity

- Goal: `GOAL-SEVEN-RED-COMPOUND-TOP10`
- Agent Request: `engineering-seven-red-inner-selection-contract-v1` (Request 180)
- Execution: 101
- Role: Engineering Agent
- Scope: research-only parameter-grid and inner-selection contract
- Production impact: none

## Primary goal

Freeze the parameter and evidence boundary needed to choose one Raw and one
Diversified seven-red strategy configuration using only a complete, strictly
prior inner window. This round defines and verifies artifacts; it does not run a
historical experiment or make a predictive claim.

## Explicit non-goals

- No recommended M, P, diversification weights, grid, or inner-window length.
- No outer-target portfolio, settlement, walk-forward runner, or statistical test.
- No random-control outcome in parameter selection and no best-seed selection.
- No hypothesis decision, Evidence row, lift claim, betting output, or production
  integration.

## Implemented contract

`SevenRedStrategyParameter` binds an explicit score-pool M/P configuration and a
strategy family. Raw rejects diversification weights; Diversified requires one
existing primitive integer weight vector. `SevenRedParameterGrid` canonicalizes
by the full parameter digest, rejects duplicates, and requires at least two
candidates in each family.

`SevenRedParameterIssueEvaluation.compile_raw` and
`compile_diversified` replay the score pool, check M/P, rebuild or bind the exact
strategy snapshot, replay the equal-cost portfolio, and bind its post-outcome
settlement. The retained selection evidence is the seven-coordinate
`unique_ticket_hit_histogram`; paid-slot duplicate amplification is absent from
the metric interface.

`SevenRedInnerSelectionProtocol` requires an explicit window of at least 20
issues and accepts only the frozen metric and tie-break identities. A snapshot
requires the same strictly increasing, strictly pre-outer issue tuple for every
parameter. Missing, extra, or duplicate cells fail closed.

Raw and Diversified winners are computed independently. The lexicographic metric
maximizes, in order:

1. issues with at least one unique exact-red6 ticket;
2. issues with at least one unique red5-or-better ticket;
3. sum of each issue's best unique-ticket matched-red count;
4. total unique red5 ticket count;
5. lower full parameter digest for an exact metric tie.

Every aggregate row and all parameter digests tied on the winning metric remain
in the snapshot. There is no global winner or promotion field.

## Gauss pass: exact obligations

- **Chronology:** every evaluation proves source history is strictly before its
  evaluated issue; every inner issue is strictly before the outer target.
- **Rectangle:** the expected Cartesian product is
  `parameter_grid × inner_issues`. Set equality plus duplicate rejection proves
  that no candidate has a shorter, different, or selectively dropped window.
- **Metric arithmetic:** all four coordinates are non-negative integers derived
  from the unique-ticket histogram. Coverage is an indicator, best match is the
  largest occupied bin, and red5 count is bin 5 only.
- **Tie discipline:** metric tuples are maximized exactly; only an exact four-way
  tie reaches the lower SHA-256 parameter digest rule.
- **Replay:** canonical input order, aggregate rows, family tie evidence, and the
  snapshot digest are deterministic. The synthetic golden snapshot digest is
  `960991d54d210de1316f8e40796bd7b34a016a514d8b02ab4761e01ed9159e3d`.

## Riemann pass: structural obligations

The object being selected is a point in a finite, explicitly declared parameter
grid, not a continuously optimized or retrospectively expanded search space.
Each point is evaluated over the same time slice, so the comparison geometry is
rectangular rather than a collection of incomparable sparse traces.

The lexicographic metric is deliberately sparse: exact-red6 and red5-or-better
coverage can remain tied for long windows. The lower-order best-match and red5
ticket-count coordinates make those ties observable without inventing a smooth
surrogate. This does not establish that the metric is statistically powerful;
the later outer walk-forward and statistical review must measure that limitation.

## Shared conclusion and remaining uncertainty

The smallest shared conclusion is contractual: the implementation can select
independent Raw and Diversified family parameters without reading an outer
outcome, using a complete common inner evidence surface and deterministic exact
tie rules. It does not show that either family beats six-red Top70 or random
controls. That question remains blocked on the later outer walk-forward and
statistical comparison rounds.

## Validation

Acceptance commands completed:

```text
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_seven_red_inner_selection.py
apps/worker-python/.venv/bin/python -m pytest -q
```

- Focused result: `11 passed in 2.74s`.
- Full Worker result: `1506 passed, 4 skipped, 4 warnings in 99.24s`.
- The four warnings are the pre-existing Python 3.14 multiprocessing `fork()`
  deprecation warnings in training-supervisor parallelism tests.
