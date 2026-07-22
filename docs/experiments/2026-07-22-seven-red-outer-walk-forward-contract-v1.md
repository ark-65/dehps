# Seven-red strict outer walk-forward contract v1

## Round identity

- Goal: `GOAL-SEVEN-RED-COMPOUND-TOP10`
- Agent Request: `engineering-seven-red-outer-walk-forward-contract-v1`
  (Request 181)
- Execution: 102
- Role: Engineering Agent
- Scope: research-only outer-trial and walk-forward artifact compiler
- Production impact: none

## Primary goal

Freeze a replayable post-outcome artifact boundary for comparing Raw seven-red
Top10, Diversified seven-red Top10, six-red Top70, and deterministic random
controls over an explicit outer target sequence. This round compiles and checks
evidence shapes only; it does not execute a historical study or calculate a
cross-target result.

## Explicit non-goals

- No real target range, M, P, weights, inner window, or random seed recommendation.
- No historical run, database loader, CLI, API, web, scheduler, or supervisor.
- No effect estimate, p-value, confidence interval, multiplicity correction,
  winner, hypothesis decision, Evidence, predictive claim, betting output, or
  production action.
- No change to predecessor scoring, selection, settlement, or random semantics.

## Implemented contract

`SevenRedWalkForwardProtocol` requires an explicit strictly increasing tuple of
at least 30 target issues, an explicit existing random seed policy, the frozen
70-slot paid-ticket budget, family-matched random controls, complete arms, and
unaggregated per-target evidence. It has no defaults and contains no statistical
method or decision threshold.

`SevenRedOuterTrial.compile` verifies one target through the following boundary:

1. replay the target-matching inner-selection snapshot;
2. bind independent Raw and Diversified winners to their exact M/P score pools;
3. require both score pools to share one exact full six-red score vector and
   strict pre-target history boundary;
4. bind the Diversified weight vector and source candidate pool;
5. replay Raw Top10, Diversified Top10, and six-red Top70 portfolios;
6. bind each post-outcome settlement and require one identical six-red outcome;
7. replay one random cohort per selected family score pool under the same seed
   policy and bind every seed/control settlement to the common outcome.

The compressed trial evidence retains each strategy's paid-slot and unique-ticket
histograms, unique and duplicate counts, source/parameter/portfolio/settlement
digests, and every random seed × control row. Raw duplicate slots remain paid;
Diversified Top10, six-red Top70, and uniform-legal controls remain unique-70.

`SevenRedWalkForwardSnapshot` requires exactly one complete trial for every
protocol target and canonicalizes trial input order. It contains no cross-target
aggregate, statistical result, winner, or promotion status.

## Gauss pass: exact obligations

- **Chronology:** the selected score vector's history ends strictly before every
  trial target, and the inner-selection target equals the outer trial target.
- **Source equality:** Raw, Diversified, and Top70 bind one exact vector digest;
  M/P and Diversified weights bind their independently selected parameter
  digests.
- **Equal cost:** every strategy and every random portfolio contributes exactly
  70 paid slots. The equation `duplicate slots = 70 - unique tickets` is checked,
  and each histogram total is checked against its correct paid or unique count.
- **Outcome equality:** every strategy settlement and every matched-random
  settlement binds the same target and canonical six-red outcome.
- **Rectangles:** each random cohort retains every explicit seed and both control
  kinds; the walk-forward snapshot retains every explicit target exactly once.
- **Replay:** canonical input produces golden snapshot digest
  `35ea8dcd2d7d1f86a76ee33d6b1e0d175a58e5341505590ff1618aea1c542239`.

## Riemann pass: structural obligations

The comparison surface has two nested geometries. Within a target, every arm has
the same paid cost and outcome, while unique-ticket geometry remains visible
rather than being flattened. Across targets, the artifact is a complete ordered
sequence, not a performance summary that could hide sparse wins or excluded
failures.

Random-from-pool depends on the selected candidate pool, so one shared pool would
silently favor one strategy family's selected M/P. The contract therefore uses
family-matched cohorts: Raw is compared with controls generated from the selected
Raw pool, and Diversified with controls generated from the selected Diversified
pool. Uniform-legal rows are retained inside both matched cohorts because their
deterministic SHA-256 stream is also source-digest-separated. Later statistics
must respect these paired identities rather than pooling them as independent
observations.

## Shared conclusion and remaining uncertainty

The smallest shared conclusion is contractual: a later isolated run can create a
complete, equal-cost, leakage-checked outer evidence surface without selecting
seeds or computing a winner. No claim is made that Raw or Diversified Top10 beats
Top70 or either random control. Effect definitions, dependence-aware uncertainty,
and multiplicity control remain for the next statistical-contract round.

## Validation

Acceptance commands completed:

```text
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_seven_red_walk_forward.py
apps/worker-python/.venv/bin/python -m pytest -q
```

- Focused result: `9 passed in 10.26s` on the warm replay run.
- Full Worker result: `1515 passed, 4 skipped, 4 warnings in 116.33s`.
- The warnings are the pre-existing Python 3.14 multiprocessing `fork()`
  deprecation warnings in training-supervisor parallelism tests.
