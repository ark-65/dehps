# Research Roadmap

## Milestone M2: Prediction Quality Improvement

Status: active.

M2 uses the stable Contract Runtime to test whether a frozen, transparent research change improves
ranking behavior and survives increasingly independent evidence. Runtime test growth is not an M2
outcome. Historical lift is evidence for or against a prediction hypothesis, not proof of future edge.

Observed baseline at M2 opening:

```text
evaluation identity: recent-100
Top100 / Top1000 / Top10000: 3 / 3 / 4
learning decision: no_learning_lift
production selection changed: false
```

The snapshot is documented by [Research Success Learning Loop v1](../experiments/2026-07-20-research-success-learning-loop-v1.md).

## Core question and invariant

Core question: does one preregistered research change improve the declared ranking objective relative
to frozen controls, then retain the effect outside the selection evidence?

Invariant: within each comparison, both sides use the same legal sample space, history identity,
target issues, candidate boundary, contract package, compute semantics, and cutoff definitions. In a
prospective rolling protocol, history may advance only with data legally available before the next
target; every new history and Runtime content identity must be sealed before that outcome. For the
full SSQ red-ball demo, the legal universe remains `C(33,6) = 1,107,568`; any ranked subset or
excluded rows must be explicit.

## Evidence ladder

| Level | Purpose | Metrics | Interpretation |
| --- | --- | --- | --- |
| Search diagnostic | Fast feedback, never promotion | Recent-30 and local rank movement | High variance; may reject quickly but cannot establish quality |
| Search selection | Choose a local research challenger | Recent-100 cutoff hits, exact ranks, rank tail, paired deltas | Selection evidence; repeated search requires multiple-testing caution |
| Stability | Detect window dependence | Recent-300 and sub-window breakdowns | Recent-300 overlaps Recent-100 and is not independent generalization evidence |
| Historical validation | Test a frozen rule through time | Expanding walk-forward, same-rate null, frozen controls | Historical rejection/retention evidence only |
| Forward generalization | Test genuinely unseen issues | Frozen future issues, exact/red5 ranks, calibration, failures | Only this level can increase generalization confidence |
| Promotion | Apply the existing gate | Evidence bundle, uncertainty, failure cases, independent decision | No Agent receives direct promotion authority |

Recent-30, Recent-100, and Recent-300 must name exact issue identities. A result selected on one of
these windows cannot be re-labelled as validation on the same observations.

## Quality metrics

- exact Top100, Top1000, and Top10000 hits;
- exact rank distribution: median, best, worst, p90/p95, and tail counts;
- Red5 metrics in their explicit rank namespace;
- keep rate, coverage rate, lift, and missed issues for filter-style strategies;
- calibration against the legal-universe/null probability with confidence intervals;
- stability across preregistered windows and sub-periods;
- generalization on frozen future issues;
- feature importance and ablation only when computed on identical boundaries.

Expected Value is `not_defined` for the current red-ball ranking output. It requires a separate
contract covering ticket cost, prize schedule, blue-ball or product scope, shared-prize dilution,
candidate portfolio construction, and bankroll/risk assumptions. Hit rate alone must not be converted
into a monetary EV.

## Process metrics are not model quality

The following diagnose research operations and must remain outside the quality score:

- evaluation completion and freshness;
- shadow capture/attestation coverage;
- experiment completion/failure rate;
- promotion submissions, approvals, rejections, and time-to-decision.

Promotion Rate is not optimized upward. A low rate can be healthy when the gate rejects weak ideas;
a high rate can indicate a weak gate. Shadow numerical equality belongs to Runtime Health, while the
presence of complete research evaluation evidence belongs to Research Process.

## M2 execution loop

```text
Preregister one hypothesis
  -> freeze model, Runtime-contract, and evaluation-contract identities
  -> seal each per-issue Runtime and evidence content identity
  -> implement an isolated challenger
  -> compare with baseline and same-boundary nulls
  -> run Recent-100 search selection
  -> run Recent-300 stability and frozen walk-forward checks
  -> capture forward/shadow evidence without changing production selection
  -> submit evidence to the existing Promotion Gate
```

Each batch changes one declared research mechanism. Runtime, sync, API, dashboard, and unrelated
features remain frozen so attribution is possible.

## Active forward protocol

[Frozen-Future-30 Rolling-History Preregistration](../experiments/2026-07-20-m2-frozen-future-30-rolling-history.md)
is the active prospective M2 study. It freezes model and contract identity while recomputing and
sealing each issue's history, Runtime, ABI, candidate, and Prediction Evidence identities before the
target outcome. The null remains `Binomial(30, 10000/1105506)`, the decision threshold remains at
least two exact Top10000 hits, and no conclusion is allowed before all 30 issues complete.

Runtime equality in this protocol is a health gate. Cohort completion is a Research Process metric.
Only the final preregistered outcome count is Research Quality evidence.

## Immediate priorities

1. Complete Frozen-Future-30 issue by issue without changing Feature, weight, scoring, ranking,
   candidate boundary, Runtime code, or production selection.
2. Keep each pre-outcome seal and post-outcome evaluation append-only; report process failures
   without turning interim hits into a Research decision.
3. Surface walk-forward, calibration, ablation, and forward evidence under one Research Dashboard
   contract without conflating Runtime equality with Prediction Quality.
4. Do not add a feature until Frozen-Future-30 finishes or a separately approved Research Request
   names its mechanism, baseline, failure condition, and non-overlapping evidence boundary.
