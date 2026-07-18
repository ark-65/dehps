# Evaluation Contract v1 acceptance report

## Round contract

- Primary goal: freeze the semantics of current forward-evaluation evidence as `evaluation.v1.0.0`.
- Non-goals: no Evaluation ABI, runtime/database migration, metric change, historical backfill,
  backend promotion, prediction regeneration, or production operation.
- Engineering request: `engineering-evaluation-contract-v1-20123ac`.
- Execution: `41`.

## Root gap

DEHPS already persisted exact-hit, Red5, cutoff, score, rank, leakage, and ranking-audit values, but
their meaning was distributed across the forward evaluator, ranking audit, shadow comparison, and
training metrics. Runtime Envelope therefore had an Evaluation Contract slot without one normative
contract that could explain those fields.

The most important ambiguity was rank namespace: exported candidate rank and full-universe model
score rank are both integers, but are not interchangeable evidence.

## Implemented boundary

`evaluation.v1.0.0` now freezes:

- canonical six-red actual outcomes and candidate identities;
- positive one-based source ranks;
- preservation of the source Ranking Contract;
- exact-six and exactly-five Red5 semantics;
- inclusive Top100, Top1000, and Top10000 cutoffs;
- separate counts for six-hit and five-hit candidates;
- null semantics for missing matches;
- blue-ball record-only behavior;
- `export_rank`, `model_score_rank`, and `rule_filter_rank` namespaces;
- deterministic comparison precedence separating contract changes from regressions.

The reference verifier rejects manifest drift, illegal outcomes/candidates, duplicate candidate
identities, invalid or non-monotonic ranks, non-finite scores, and invalid `strict_v1` tie order. It
does not repair or reorder evidence.

## Compatibility evidence

The golden suite is executed both by the new reference evaluator and the existing forward evaluator.
The following fields match exactly:

- exact rank and score;
- best Red5 rank, score, and identity;
- exact and Red5 hit flags at all three cutoffs;
- six-hit and five-hit cutoff counts;
- blue ball is recorded but not scored.

This is specification and verification work only. Existing evaluation payloads, rows, fingerprints,
prediction runs, pending candidates, and production state are unchanged.

## Validation

- Focused Evaluation/Ranking compatibility: `21 passed`.
- Contract Runtime and evaluation surface: `153 passed`.
- Full Python suite: `1179 passed, 4 existing multiprocessing warnings` in `47.95s`.

## Next boundary

The next staged round is Evaluation Artifact Runtime: compile and verify an immutable artifact bound
to Prediction, Actual Outcome, Ranking Audit, Runtime Envelope, and this contract. Historical rows
must remain compatibility evidence and must not be silently backfilled or re-evaluated.
