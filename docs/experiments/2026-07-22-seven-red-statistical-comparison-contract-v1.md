# Seven-red multiplicity-controlled statistical contract v1

## Round identity

- Goal: `GOAL-SEVEN-RED-COMPOUND-TOP10`
- Agent Request: `engineering-seven-red-statistical-comparison-contract-v1`
  (Request 182)
- Execution: 103
- Role: Engineering Agent
- Scope: research-only statistical evidence compiler
- Production impact: none

## Primary goal

Freeze the comparison family and exact numerical procedures before loading a real
historical walk-forward result. The compiler consumes only a verified complete
outer snapshot and produces numerical evidence. It does not decide whether a
strategy outperforms a comparator.

## Explicit non-goals

- No historical run, database access, real parameter/target/seed choice, CLI,
  API, web, scheduler, or supervisor.
- No post-hoc endpoint, comparator, exclusion, alpha, block, seed, confidence,
  or multiplicity change.
- No boolean pass/fail, winner, Hypothesis or Evidence mutation, predictive
  conclusion, betting output, or production action.

## Pre-registered confirmatory family

The target issue—not a random seed—is the paired sample unit. The sole
confirmatory endpoint is the best matched-red count among unique paid tickets.
Exactly six one-sided strategy-greater comparisons are retained:

1. Raw Top10 versus six-red Top70;
2. Raw Top10 versus family-matched random-from-pool;
3. Raw Top10 versus family-matched uniform-legal;
4. Diversified Top10 versus six-red Top70;
5. Diversified Top10 versus family-matched random-from-pool;
6. Diversified Top10 versus family-matched uniform-legal.

For a random comparator, the endpoint is first calculated for every retained
seed row, then averaged exactly across all protocol seeds within the same target.
This produces one comparator value per target. Seed rows remain in the artifact
for sensitivity review but never increase the confirmatory sample size.

Each comparison retains target-aligned strategy values, comparator values,
paired differences, wins/losses/ties, the exact one-sided sign-test p-value, the
exact mean difference, a circular moving-block bootstrap interval for that mean,
and the all-six Holm-adjusted p-value.

The bootstrap stream is domain-separated by the explicit seed digest,
comparison ID, resample index, block index, and rejection attempt. Block starts
use unbiased uint64 rejection before modulo. Percentiles use the frozen two-sided
nearest-rank convention. The bootstrap is dependence sensitivity only and does
not replace the exact sign-test result.

Descriptive rows also retain exact-red6 coverage, red5-or-better coverage,
unique red5 ticket count, slot-weighted exact-red6 count, unique-ticket count,
and duplicate-slot count for every strategy and random seed/control row.

## Gauss pass: exact obligations

- **Pairing:** each comparison has exactly one strategy and comparator value for
  every ordered outer target; random seeds are averaged before differencing.
- **Sign tail:** ties are excluded. For `w` wins and `l` losses, the stored
  one-sided p-value is exactly
  `sum(C(w+l,k), k=w..w+l) / 2^(w+l)`; no discordance returns one.
- **Multiplicity:** all six raw p-values enter one Holm family. Sorting uses raw
  p then comparison ID, step-down values are monotone, and adjusted values are
  capped at one.
- **Arithmetic:** endpoints, means, p-values, adjusted values, resample means,
  rank probabilities, and interval bounds remain `Fraction` values.
- **Resampling:** every resample has exactly the target count after circular block
  concatenation and truncation; changing the seed or any paired value changes the
  distribution digest.
- **Replay:** the synthetic golden statistical snapshot digest is
  `88ade3f1c5c37c9751ea83d08547d6409c47c85136952852087f1268cf93f080`.

## Riemann pass: structural obligations

The source evidence is nested: seed rows live within controls, controls within a
matched family, and families within a target. Flattening that hierarchy would
create pseudo-replication and overstate certainty. The compiler preserves the
nesting and compares only target-level paired values.

The primary endpoint is discrete and tie-heavy. The exact sign test is therefore
transparent about how little directional information may remain. The block
bootstrap examines the geometry of adjacent target differences and may widen the
mean-effect interval when rolling training windows induce local dependence. It
does not turn a sparse endpoint into a continuous signal or prove target
independence.

Exact-red6 is expected to be especially sparse, so it remains a descriptive
diagnostic rather than a result-selected primary endpoint. A later Research
review must discuss it alongside red5-or-better coverage and failure modes even
if the confirmatory best-match evidence appears favorable.

## Shared conclusion and remaining uncertainty

The smallest shared conclusion is procedural: the later isolated run has a
pre-registered paired sample unit, one confirmatory endpoint, six fixed
comparisons, seed-safe random aggregation, exact sign tests, one Holm family, and
dependence-sensitive intervals. This round provides no evidence that any
strategy is better. Real protocol values, historical execution, and a separate
Research/Reviewer interpretation remain required.

## Validation

Acceptance commands completed:

```text
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_seven_red_statistics.py
apps/worker-python/.venv/bin/python -m pytest -q
```

- Focused result: `9 passed in 5.97s`.
- Full Worker result: `1524 passed, 4 skipped, 4 warnings in 160.26s`.
- The warnings are the pre-existing Python 3.14 multiprocessing `fork()`
  deprecation warnings in training-supervisor parallelism tests.
