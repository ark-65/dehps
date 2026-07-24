# M4-P2.1 Synthetic Contracts and Null Generator

## Round Contract

- Primary goal: freeze replayable synthetic contracts and implement the exact uniform six-of-33 null generator.
- Role: Engineering Agent.
- Authorized request: `engineering-m4-p2-1-synthetic-null-generator-20260724`.
- Baseline commit: `1b4bdde9bad333b605a4e5dc1bbe335444556427`.
- Preregistration: v1.0.1 / `6e03cd828378badda6995c6582d80165b0a4ee3b5899b97737bad1494fcf1ae1`.
- Decision policy: `824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d`.

## Explicit Non-goals

This round did not implement or execute metrics, models, walk-forward probes, injected-signal generation, bootstrap, permutation, power, false-positive evaluation, automatic P2 gating, or real-history analysis. It did not change a production prediction path, Promotion Gate, adaptive supervisor, practical-null threshold, preregistered signal strength, block size, multiplicity rule, or decision state.

## Exact Synthetic Null

Each issue is sampled independently by an explicit `numpy.random.Generator` from the legal set `{1,...,33}`, choosing exactly six numbers without replacement. The six numbers are sorted canonically and compiled into:

- a one-based `issue_index`;
- a uint64-compatible `red_mask`, with bit `n-1` representing number `n`;
- `sorted_red_numbers[6]`;
- a binary `target_vector[33]` containing exactly six positive entries.

The generator has no real-history input and no fitted parameter. A stochastic run requires the existing normalized `SeedPolicy`. A replicate seed must belong to the frozen half-open range `[200000, 201000)`. No global RNG or wall-clock seed is used.

The truth contract derives exact values from combinatorial formulas:

- legal combinations: `C(33,6)`;
- number marginal: `6/33`;
- pair marginal: `C(31,4)/C(33,6)`;
- one complete draw: `1/C(33,6)`.

No approximate probability is frozen as synthetic truth.

## Frozen Work Manifest

The P2.1 run manifest digest is `8493987cc4414414e33fb5c5ea148be1f42a1d9e57609600c4346fb642cbfa08`.

It fixes:

- 13 scenarios: one implemented uniform null and twelve unimplemented injected-signal contracts;
- three sequence scales: historical `3481`, forward-61 `961`, and long `6962`;
- minimum training length `900`;
- 1,000 null replicate seeds;
- the four preregistered probe names;
- primary block size `5` and sensitivity sizes `[3,5,8,13]`;
- an explicit later-P2 workload of 31,000 scenario-replicates and 64,656,000 outer predictions.

These counts are planning identities only. This round executed zero large replicates, zero metric evaluations, and zero real-data analyses.

## Einstein Constraint Pass

The legal sample space and its symmetries were treated as proof obligations rather than empirical approximations. The smallest failing checks were made explicit: six unique in-range numbers, target/mask equivalence, exact theoretical marginals, deterministic replay, seed-policy membership, and rejection of any real-data reference. This makes later injected-signal work falsifiable against a transparent null.

## Research OS State

P2 is split into an audited chain:

1. P2.1 synthetic contracts and null generator — COMPLETE.
2. P2.2 metric kernel — READY.
3. P2.3 walk-forward probe harness — dependency wait.
4. P2.4 injected-signal calibration — dependency wait.
5. P2.5 resampling — dependency wait.
6. P2.6 false-positive and power runs — dependency wait.
7. P2.7 automatic gate and report — dependency wait.

Projected state is `ACTIVE / M4-P2 / RUNNING`. Engineering progress is 23%; Evidence progress is 0%. Formal real-data analysis remains `NOT_STARTED`. Promotion Gate remains `CLOSED`; adaptive supervisor remains `STOPPED`; old training remains `REJECTED/FROZEN`; issue `2026085` remains retroactively ineligible and in `external_wait`.

The numeric acceptance tolerance for empirical confidence-interval coverage is not frozen in P1. It is recorded as a fail-closed dependency that must be resolved before P2.6/P2.7; this round did not invent one.

## Validation

Focused P2.1 contract, generator, replay, invalid-input, CLI, governance, and Research OS tests:

```text
50 passed
```

Full local validation:

- Worker: `1615 passed, 4 skipped`.
- API: `117 passed`.
- Web: `19 passed`.
- Angular production build: passed.

## Next Ready Task

`m4-p2-metric-kernel`

P3 remains closed until every P2 subtask is complete and the preregistered measurement-system gate passes.
