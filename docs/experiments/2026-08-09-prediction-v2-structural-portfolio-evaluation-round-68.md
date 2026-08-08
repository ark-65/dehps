# Prediction v2 structural portfolio evaluation — Round 68

Date: 2026-08-09

Role sequence: Research Agent -> Reviewer -> Engineering Agent

Primary goal: bind the replay-verified B176 structural result to one exact,
non-predictive evaluation and route it to a separate structural-use decision.

## Non-goals

- Do not rerun the optimizer, null generator, checkpoints, folds, bootstrap
  children, history, CSV, or database data queries.
- Do not retune the budget, seeds, objective, gate, threshold, or selected
  portfolio after observing the result.
- Do not call the frozen mechanical fraction a calibrated p-value.
- Do not claim global optimality, practical decision usefulness, prediction
  Evidence, probability advantage, or lottery edge.
- Do not authorize a model, candidate expert, promotion, P3, betting output, or
  production action.

## Frozen scientific interpretation

The registered execution produced one selected B176 portfolio after a frozen
22-island, 5,767,168-proposal optimizer and compared it with 4,096 uniformly
sampled same-budget portfolios. The evaluation reads those registered summaries
only; all new execution counters are zero.

Exact finite-design reference values and observed gaps are:

| Coordinate | Ideal | Selected | Gap |
| --- | ---: | ---: | ---: |
| Singleton square sum | 33,792 | 33,796 | +4 |
| Pair square sum | 13,200 | 14,152 | +952 |
| Minimum replacement distance | 2 required | 2 | 0 |
| Pairwise replacement-distance sum | 76,032 | 76,030 | -2 |

The best registered uniform-null extremes were 34,104, 15,144, 2, and
75,876 in the same coordinate order. The selected portfolio strictly dominated
all 4,096 nulls and was dominated by none. Sixteen of 22 independently seeded
final optimizer islands passed the frozen gate and each of those sixteen
dominated every null.

The bounded decision is therefore:

```text
SUPPORTED_AT_FROZEN_B176_AGAINST_UNIFORM_RANDOM_ONLY
```

This supports only the fixed optimizer-versus-uniform construction hypothesis.
The selected portfolio was chosen from 22 optimized islands while null rows were
unoptimized uniform portfolios, so `1/4097` remains a mechanical gate fraction,
not a calibrated inferential p-value or a generalization test. Every legal
six-of-33 combination still has equal pre-draw probability.

## Einstein and Gauss–Riemann review

The Einstein lens forced the evaluation to identify the smallest falsifiable
claim: a fixed bounded optimizer can improve the frozen structural coordinates
relative to uniform same-budget construction. It also made explicit that actual
decision usefulness is the next unknown, not an implied consequence.

Gauss pass:

- strongest claim: the ideals, gaps, null extrema, dominance counts, and
  16-of-22 robustness are exact finite computations;
- weakest assumption: optimized-island selection versus unoptimized nulls
  supports description of the fixed optimizer, not calibrated inference;
- required check: exact identities, finite arithmetic, multiplicity disclosure,
  and zero-work replay.

Riemann pass:

- strongest claim: sixteen islands repeatedly reach a narrow near-design region
  in the finite structural space;
- weakest assumption: the four coordinates are useful for a human decision;
  they contain no outcome-label, human-behavior, payout, or predictive geometry;
- required check: keep structural routing separate from prediction routing.

Shared conclusion: advance only to
`prediction-v2-structural-route-decision`, preserve Prediction v2 as
`SHADOW_ONLY` / `BASELINE_ONLY`, and keep historical Evidence `INCONCLUSIVE`.

## Implementation

The round adds:

- a source-bound evaluator that verifies the exact registered execution,
  portfolio, optimizer index, null comparison, and execution completion;
- three immutable outputs: evaluation decision, structural route handoff, and
  evaluation completion;
- one unified Supervisor capability and deterministic registered-output replay;
- an additive DAG revision of the existing Ready evaluation task plus exactly
  one new route-decision placeholder;
- status projection for the bounded evaluation result and exact next consumer;
- a production migration builder that preserves all durable tasks, states,
  facts, events, failed events, and registered artifacts.

No repeated-combination validation path, scan, artifact field, or replay field
was added. The evaluator trusts the registered immutable portfolio identity and
evaluates only the declared structural summaries.

## Validation

- Evaluator-focused tests: `7 passed`.
- Prediction v2 structural/promotion/Supervisor focused group: `65 passed`.
- Full Worker suite: `2241 passed, 4 skipped, 42 failed`; every failure is an
  expected legacy-retirement guard from the already retired three-line
  prediction/training/mail path, with no new failure in this round's surface.
- Python compilation: passed.
- Ruff formatting and lint: passed.
- `git diff --check`: passed.
- Additive live-manifest migration dry-run:
  - live tasks: 65;
  - output tasks: 66;
  - revised tasks: only `prediction-v2-structural-portfolio-evaluation`;
  - new tasks: only `prediction-v2-structural-route-decision`;
  - existing state regressions: 0;
  - existing fact deletions: 0;
  - unallowlisted definition rewrites: 0.
  - dry-run artifact identity:
    `6c90d8f95fdba32eeb8b4abe35185b7b562e8657108648904162e73dc1470490`;
  - output manifest identity:
    `cd176024366258505e40819d9c67b66d2282bcba3d2ad7734f68642b35c9e0f7`.

The final registered-input reconstruction produced deterministic child
identities `e467e86b...` (evaluation), `bd59e548...` (route handoff), and
`95c1f01e...` (completion), using source contract `b194c87b...`. These remain
pre-publication identities until the same bytes are executed on merged main.

The complete non-retired Worker suite and GitHub CI are required before merged
Operator execution. A fresh merged Supervisor execution and durable replay are
also required before capability acceptance.

## Mainline integration matrix

| Link | Code/review state | Durable state before publication |
| --- | --- | --- |
| Goal | M4 active goal preserved | active |
| Resolver | additive revision tested | current evaluation Ready but unsupported |
| Ready Queue | exact evaluation task identified | one Ready task |
| Supervisor | evaluator registered and synthetically exercised | merged execution pending |
| Capability | exact evaluation builder passed | durable execution pending |
| Artifacts | three child identities deterministic | registration pending |
| Status | route-decision projection tested | merged status pending |
| Next task | structural route decision declared | dispatch pending |
| Replay | registered-output replay tested | durable replay pending |

Mainline acceptance at code-review time:

```text
NO — INTEGRATION_PENDING
```

It becomes `YES — validated by unified mainline execution and replay` only after
ready PR merge, exact additive import, a fresh merged Supervisor execution, four
durable artifact registrations, route-decision Ready observation, and
deterministic replay.
