# Champion-path collapse audit v1

## Primary goal

Separate diversity in the retained candidate set from diversity in the persisted
champion path and the scalar decision boundary.

## Frozen source

The audit consumes the preserved adaptive-search status artifact:

```text
data/output/optimization/research-lane/adaptive-success-training/
training-supervisor-20260722-140006.json
```

It contains 189 completed rounds, 88 retained candidates, and 88 unique evaluated
configuration hashes. The last improvement is round 58 and the recorded
stagnation length is 131 rounds.

## Common score boundary

Every retained configuration is compiled together through the production Full
score compiler using:

- history through issue 2026083;
- the inferred 2026084 draw date;
- target issue 2026084;
- all 1,107,568 legal six-red candidates;
- the common score-descending, lex-id tie policy;
- no 2026084 outcome.

For every candidate the output records the complete config, source family,
persisted candidate rank, existing search/frozen metrics, weight distance to the
champion, exact full-space Spearman, deterministic sampled Kendall, Top10/100/10K
Jaccard, and ordered TopK sequence digests.

## Decision-path audit

The report separately records:

- persisted champion hash, source family, and improvement round;
- source-family counts overall and in Top1/5/10/20;
- primary hit-signature concentration;
- champion/runner-up primary tie and objective margin;
- diagnostic winners under already recorded search objective, frozen objective,
  median rank, and worst rank components.

Those component selectors are sensitivity diagnostics, not proposed replacement
objectives.

## Development full-space smoke

The 88-config full-legal smoke completed without accessing the 2026084 outcome:

```text
f4fbc26b4a010aeee00983ce253ce9423a71ccfd05d0e8afd8436ea46344ff77
```

Observed implementation diagnostics:

- 52 unique ordered Top10 sequences;
- 79 unique ordered Top100 sequences;
- 87 unique ordered Top10000 sequences;
- full-space Spearman versus champion from -0.495937 to 1.0;
- all persisted Top5 candidates from the `normal` source family;
- champion and runner-up tied on `(Top100, Top1000, Top10000)`;
- relative recorded objective margin `0.000007364158`;
- four distinct winners across five already-recorded component views.

These values validate the report surface. The smoke is not formal Research
Evidence; a clean merged-commit Operator run remains required.

## Non-goals

- No candidate generation, training, scoring change, objective change, or
  selection change.
- No 2026084 outcome or settlement.
- No production mutation, hypothesis transition, or Promotion Gate change.
