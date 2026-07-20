# Evaluation Contract v1 Specification

## Status and scope

`evaluation.v1.0.0` freezes the meaning of DEHPS forward-evaluation evidence. It is a semantic
contract, not an Evaluation ABI and not a database migration.

The contract answers four questions without ambiguity:

1. Which actual outcome and prediction artifact are being evaluated?
2. Which rank namespace does each rank field use?
3. What counts as exact-six, Red5, and a Top100/1000/10000 hit?
4. Is a comparison difference caused by a contract change or a regression under the same contract?

This round deliberately does not alter the existing forward evaluator, persisted rows, pending runs,
objective policy, promotion gate, or historical artifacts.

## Evaluation function

```text
Evaluation = E(PredictionArtifact, ActualOutcome, RankingAudit)
```

Every future Evaluation Artifact must bind:

- `prediction_run_key` and `target_issue`;
- Candidate Contract and candidate artifact identity;
- source Scoring Contract;
- source Ranking Contract;
- Evaluation Contract;
- actual outcome identity;
- evaluation payload digest.

The blue ball may be retained as outcome provenance, but is never an input to a red-ball metric.

Evaluation evidence status is a different namespace from execution lifecycle. For example,
`missing_actual_draw` describes the evidence result, while `running/completed/failed` describes an
evaluation run and `pending/evaluating/evaluated/evaluation_failed` describes prediction lifecycle.
One must not be inferred from the spelling of another.

## Outcome and candidate rules

Actual red numbers and every candidate are canonical Candidate v1 values: six unique, strictly
increasing integers in `[1,33]`.

Candidate rows preserve their source artifact ordering. Evaluation does not sort, repair, deduplicate,
or recompute rank. Ranks are positive, one-based, and strictly increasing. Under `strict_v1`, scores
must be non-increasing and equal-score rows must use ascending `lex_id`. Legacy source rows remain
identified as `legacy_score_partition`; they are interpreted, never rewritten.

## Metric semantics

- Exact hit: candidate red numbers equal all six actual red numbers.
- Red5: set intersection with actual red numbers has cardinality exactly five, not at least five.
- Best Red5: the minimum source rank among Red5 candidates.
- Cutoffs: `100`, `1000`, and `10000`, with inclusive `rank <= cutoff` boundaries.
- Cutoff counts: exact-six and exactly-five candidates are counted separately.
- Missing match: rank and score are null, never zero and never a sentinel rank.

The normative manifest and its digest live in
`dehps.input_contracts.evaluation_contract`.

## Rank namespaces

Evaluation v1 forbids treating all rank-shaped fields as interchangeable:

| Namespace | Meaning |
| --- | --- |
| `export_rank` | Rank in the persisted/exported candidate artifact |
| `model_score_rank` | Exact full-legal-universe rank from scoring audit |
| `rule_filter_rank` | Rank at one named audit/filter stage |

An absent exported exact combination does not imply that its full-universe model score rank is absent.
Reports must retain the namespace instead of copying one value into another field.

## Comparison classification

Comparison uses deterministic precedence:

1. `evaluation-contract difference`;
2. `scoring-contract difference`;
3. `score regression`;
4. `ranking-contract difference` when candidate identity differs across Ranking Contracts but scores do not;
5. `candidate identity regression` under the same contracts;
6. `evaluation metric regression`;
7. `exact`.

This prevents a legacy/strict tie-boundary identity change from being reported as a model score change.

## Golden suite and verifier

`EVALUATION_GOLDEN_SUITE` fixes an outcome, ordered candidate rows, exact rank, best Red5, inclusive
cutoff counts, and the no-blue-scoring rule. `EvaluationContractVerifier` fails closed on contract
drift, illegal outcomes or candidates, duplicate identities, invalid rank order, non-finite scores,
and invalid strict tie order.

The verifier returns no repaired rows. Runtime migration must consume verified input or reject it.

## Current integration boundary

The Evaluation Artifact compiler/verifier and pending-forward integration are implemented. Current
forward evaluation performs pure metric calculation, compiles and verifies one parent-bound artifact,
then finalizes JSON, Markdown, database summary, and service result exactly once. Shadow attestation
closure binds completed evaluation evidence without granting automatic promotion.

Legacy prediction artifacts that predate Runtime Envelope provenance remain explicitly unavailable;
current code does not replay history to invent a source identity. Historical rows are not backfilled
or re-evaluated merely because the contract now exists.

An Evaluation ABI remains unnecessary until a non-Python evaluation backend creates a real machine
boundary. Dashboard freshness and evidence-status projection are presentation work under
[Dashboard Governance](dashboard-governance.md), not a new Evaluation semantic version.
