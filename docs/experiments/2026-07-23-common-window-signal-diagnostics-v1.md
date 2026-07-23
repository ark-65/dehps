# Common-window signal diagnostics v1

## Round contract

- Role: Engineering Agent
- Agent Request: `engineering-signal-diagnostic-manifest-v1-20260723`
- Request id: `196`
- Execution id: `117`
- Primary goal: add one leakage-safe measurement surface for explicit feature
  isolation, full-space score gradients, rank similarity, equal-cost Top70
  outcomes, matched random controls, and paired block-bootstrap intervals.
- Non-goals: no new feature, learned model, weight update, search decision,
  negative-control suite beyond dynamic-feature permutation, production mutation,
  hypothesis conclusion, winner, or Promotion Gate change.

## Manifest

Every target uses one prior-history boundary and one full legal six-red universe.
The diagnostic manifest contains:

- unchanged full model;
- static-structure-only;
- recent-frequency-only;
- omission/interval-only;
- removal of existing adjacency, overlap, neighbor, and repeat fields;
- removal of all declared dynamic fields;
- fixed minimal linear weights;
- candidate-level permutation of the dynamic contribution.

`FrequencyRankerConfig` has no field literally named `cooccurrence`. The
`without_cooccurrence_adjacency` arm therefore records the exact existing mapping
instead of pretending that an absent feature was removed.

The dynamic permutation is not a weight shuffle. For each target:

```text
dynamic contribution = full score - static-structure score
negative-control score = static-structure score
                       + deterministic candidate permutation(dynamic contribution)
```

This preserves the dynamic contribution's marginal distribution while breaking
its candidate identity. The seed digest, target issue, permutation protocol, and
permutation-array digest are frozen in the artifact.

## Score-gradient contract

For every arm and outer target, the artifact records:

- score variance and unique-value ratio;
- score gaps at Top10, Top100, and Top10K;
- actual combination score, full-space rank, percentile, and score decile;
- ten equal rank-position deciles over all `1,107,568` legal combinations;
- future red-match mean and red3+/red4+/red5+/red6 rate per decile;
- adjacent-decile monotonicity and decile-index correlation;
- exact full-universe Spearman rank correlation against the full model;
- deterministic 50,000-pair Kendall estimate;
- Top10, Top100, and Top10K Jaccard overlap.

Ties use one explicit order:

```text
score descending, then full-legal lexicographic candidate id ascending
```

Score geometry is kept separate from set geometry. The same artifact also
settles each arm's Top70, eight matched-score-pool random Top70 controls, and
eight uniform-legal Top70 controls.

Across targets, it emits paired circular-block-bootstrap intervals for:

- arm Top70 minus full-model Top70;
- arm Top70 minus matched-score-pool random;
- arm Top70 minus uniform-legal random.

No field converts these measurements into a research winner or production
decision.

## Gauss pass

- The legal sample space is exact and includes combinations rejected by older
  hard filters.
- The target combination's lexicographic id is replayed against the universe
  row before accepting its rank.
- Every target's training history ends strictly before the target issue.
- Ticket budgets are 70 for every model and random-control portfolio.
- Random seeds are explicit SHA-256 digests; best-seed selection is absent.
- Bootstrap rows are paired by target and sampled with a frozen circular block
  contract.
- Digest-addressed output refuses content mismatch, and execution metadata is
  included in the snapshot digest.

## Riemann pass

- Full-space rank order, score deciles, TopK overlap, and Top70 portfolio utility
  remain separate representations.
- Candidate-level permutation preserves the dynamic score distribution while
  destroying its location on candidate space.
- Equivalent configurations are allowed and visible. For example, a base model
  that already equals the fixed minimal linear model produces identical config
  digests rather than fabricated diversity.
- A different Top10 family without a monotone decile gradient remains a
  different ordering, not evidence of signal.

## Live smoke

A one-target, full-legal-space smoke ending at `2026083` completed with
`promotion_allowed=false`. It exercised all eight arms, 128 random portfolios,
full-space rank correlations, score deciles, and paired settlement.

The smoke deliberately has no evidentiary interpretation. One useful failure-mode
example was visible: the permuted-dynamic arm happened to rank the target
`83,514`, while the full model ranked it `399,649`, but neither arm had a stable
monotone score-decile gradient. A single favorable rank from a negative control
is exactly why the intended run requires a common 60-target window.

The smoke artifact remains ignored under:

```text
data/output/optimization/signal-diagnostics-smoke-v1/
```

It was generated from a dirty development tree under the explicit smoke override
and is not admissible as authoritative evidence.

## Validation

- focused signal/legacy-ablation tests: `11 passed`;
- full worker suite: `1557 passed, 4 skipped`;
- full legal-space one-target live smoke: completed without runtime errors;
- no database writes, supervisor restart, training resume, or Promotion Gate
  mutation.

The authoritative 60-target run must be launched only from a clean accepted
commit. Its result remains diagnostic-only and requires a separate research
review before any interpretation.
