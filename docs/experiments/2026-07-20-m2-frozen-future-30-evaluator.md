# M2 Frozen-Future-30 Sealed Evaluator

- Status: accepted experiment tool implementation
- Owner lane: Research tooling
- Engineering Request: `engineering-m2-frozen-future-30-sealed-evaluator`, request id `153`
- Execution: `75`, isolated Engineering environment

## Round contract

Primary goal: provide the smallest pure evaluator that can bind one pre-outcome Frozen-Future-30
snapshot to its later Actual Outcome and deterministically compute the preregistered per-issue
metric.

Non-goals:

- no Feature, weight, Window formula, scoring, ranking, Candidate ABI, Runtime, or candidate change;
- no database access inside the evaluator;
- no production selection, promotion, optional stopping, cumulative decision, or hypothesis status
  change;
- no reconstruction of a missing pre-outcome snapshot;
- no claim that the result is a generic `EvaluationArtifactV1` when that artifact's full Runtime and
  Candidate ABI parents are unavailable.

## Implementation

`dehps.experiments.frozen_future_30` adds four operations:

1. `verify_frozen_future_snapshot` recomputes the outer sealed-manifest digest and verifies frozen
   model identity, source worker tree, universe boundaries, Runtime/Candidate identities, exact
   shadow equality, unchanged production state, and all 10,000 Prediction Evidence rows.
2. `compile_frozen_future_evaluation` requires a matching `ActualOutcomeArtifactV1`, delegates metric
   calculation to the existing `evaluate_ranked_candidates_v1`, and binds every available parent
   identity into one Frozen-Future-specific artifact.
3. `verify_frozen_future_evaluation` supports detached canonical verification and stronger
   recomputation when the sealed snapshot parent is supplied.
4. `write_frozen_future_evaluation` writes canonical, content-addressed isolated JSON and rejects a
   same-address byte collision.

The output protocol is `dehps.m2-frozen-future-30-evaluation.v1`. It records the existing Evaluation
Contract identity, metric-manifest digest, sealed snapshot digest, Prediction Evidence digest,
Actual Outcome artifact, complete Evaluation Contract metrics, evaluation code commit, and the
single per-issue primary boolean `exact_top10000_hit`.

Every artifact states:

```text
scientific_decision_allowed = false
production_selection_changed = false
promotion_allowed = false
```

## Fail-closed boundaries

The evaluator rejects:

- a mutated or re-addressed snapshot that changes frozen model identity;
- any wrong issue, legal/ranked universe, exclusion count, Top-N, config, scoring/ranking contract,
  source worker tree, Candidate ABI contract, or parent digest;
- non-contiguous ranks, duplicate candidates, missing Runtime identity, or non-exact shadow evidence;
- a snapshot that reports outcome availability, production access/change, promotion permission, or
  research-decision permission;
- an Actual Outcome for another target issue or a draw date different from the presealed
  `next_draw_date`;
- evaluation before the sealed prediction or before the authoritative draw date;
- mutated detached metrics, primary-metric disagreement, invalid code identity, noncanonical bytes,
  or a content-address collision.

## Validation

```text
.venv/bin/python -m pytest -q tests/test_frozen_future_30.py
18 passed

.venv/bin/python -m pytest -q \
  tests/test_frozen_future_30.py \
  tests/test_evaluation_artifact.py \
  tests/test_contract_core.py
36 passed
```

A read-only compatibility probe loaded the real ordinal-1 manifest
`2174a98eb64752396fe369bfad6d303b105ae539624a830ef8cee9485de23419`, verified all 10,000 rows and
Prediction Evidence digest
`bb5aeb5cb1a0dbf9ab97dc8306be70918af8c540498df420366b25317a1ed291`, and compiled then reverified
one explicitly synthetic rank-1 outcome in memory. The probe wrote no artifact and created no
scientific evidence.

## Scientific cross-review

- Gauss pass: exact parent digests, 10,000-row count and uniqueness, rank interval, issue order,
  time order, null boundary, and mutation failures are computable obligations.
- Riemann pass: the sealed prediction, later outcome, per-issue evaluation, cumulative cohort, and
  production state remain separate evidence spaces joined only by explicit parent identities.
- Shared conclusion: the tool is ready to measure one issue after its outcome, but it says nothing
  about Prediction Quality until real prospective evidence accumulates.
- Historical boundary: Gauss and Riemann are historically inspired review lenses, not literal minds,
  evidence, or authority.

## Next verification

Keep issue `2026083` at `1/30 sealed, 0/30 evaluated` until its authoritative outcome is present.
Then an approved isolated Operator execution must read that outcome, compile and persist the
ordinal-1 artifact, independently reverify it against the sealed parent, and leave production state
unchanged before ordinal 2 is built from rolling history.
