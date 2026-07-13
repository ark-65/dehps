# Autonomous Hypothesis Proposal Engine

## Purpose

The Round 22 engine turns formal DEHPS research state into at most one reviewable Hypothesis proposal. It does not create a Registry Hypothesis, plan or execute an Experiment, change training, change the Objective, promote a strategy, or restart the Supervisor.

The safety boundary is:

```text
formal state -> deterministic context -> bounded candidates -> novelty -> validation -> ranking
                                                                         |
                                                                         v
                                                       submitted Agent Request only
```

## ResearchContext

`ResearchContextBuilder` reads the Round 20 Registry, persisted training rounds, versioned training-watch and stall-diagnosis artifacts, candidate-source diagnostics, the current Objective policy, implemented feature/model paths, forward-evidence state, sequential-null state, frozen-validation state, and the prediction-input boundary. It does not infer state from narrative reports.

The canonical, sorted JSON representation produces a SHA-256 context fingerprint. The same formal inputs and engine version therefore produce the same candidates, ranking, generated timestamp, and selection. An explicit artifact path may be supplied to persist the context; otherwise generation is dry-run and writes no artifact.

The Feature Catalog exposes 51 unique implemented or diagnostic features across twelve categories: calendar, candidate diversity, co-occurrence, distribution, frequency, model disagreement, omission, regime, residual, structural, transition, and trend. Every descriptor records its input boundary, temporal scope, leakage risk, implementation path, model use, known failures, current status, future-information flag, and production-use flag.

The Mechanism Catalog exposes ten mechanism families and binds rejected Registry families and hypotheses to them. Context construction fails if any rejected family cannot be associated with mechanism memory. This prevents a rejected mechanism from disappearing merely because its label changes.

## Proposal generation

Six pure generators each emit two fixed variants, for twelve candidates total:

- residual persistence;
- model disagreement;
- regime shift;
- co-occurrence graph drift;
- candidate-space density;
- multi-scale temporal residual.

Every `HypothesisProposal` freezes the scientific question, statement, null, minimal non-null, invariants, input/feature/model/baseline/metric/validation contracts, failure condition, novelty basis, rejected-family difference, self-deception risks, costs, confidence, and risk level. The legal universe is always the exact 1,107,568 red-ball 6-of-33 combinations.

Generators may use only the supplied context. They cannot read future outcomes, randomize a split, sweep seeds or epochs, or mutate the Registry, database, files, training runtime, Objective, or Supervisor.

## Novelty, validation, and ranking

The Novelty Detector compares mechanism, features, models, and validation protocol with active and rejected Registry records. It deterministically rejects exact duplicates and proposals whose only change is seed, epoch, depth, nearby weights, same-history search rounds, naming, or protocol wrapping. Rejected mechanism/feature-family reuse is rejected unless the formal reopen condition is satisfied.

The Validator requires an explicit null, minimal non-null, failure condition, same-universe/same-history/same-candidate/same-compute baseline, pre-target boundary, passed formal input boundary, no future information, expanding walk-forward validation, disjoint search/frozen windows, no selection on forward outcomes, novelty, bounded cost, sufficient source history, exact rank and tail metrics, at least 20 paired forward issues, available features/models, no betting promise, and all Registry preregistration fields.

Ranking is a deterministic weighted score over information gain, falsifiability, forward testability, novelty, Registry compatibility, leakage/overfitting risk, and implementation/compute cost. Ties are resolved by stable proposal key. The engine selects no more than one valid candidate and returns `selected=None` when none qualify.

## Submission and interfaces

`ResearchProposalSubmissionService` accepts only the engine's selected, top-ranked, valid candidate. It creates a Round 21 `research_hypothesis_proposal` Request as Research and immediately transitions it to `submitted`. The payload includes the engine version, context fingerprint, complete proposal, novelty report, score, validation report, and formal source IDs/keys/run IDs. A deterministic request key makes retries idempotent.

The CLI provides:

```text
dehps research-context build|show
dehps research-proposal generate|list|show|submit|validate
```

`generate` and `validate` are dry-run. Only `submit` writes, and its only write is the submitted Agent Request.

The NestJS module provides four GET-only routes:

```text
GET /research-autonomy/context
GET /research-autonomy/proposals
GET /research-autonomy/proposals/:key
GET /research-autonomy/engine-status
```

The API has no generation or submission route. Engine status explicitly reports `executionStarted=false`, `hypothesisCreated=false`, and `writeRoutesEnabled=false`.

## Scientific interpretation

Proposal rank is a decision about which falsifiable question is most informative to review next. It is not evidence that the proposed mechanism works, is predictive, or supports betting. Only a separately reviewed, preregistered, time-isolated Experiment can produce evidence, and existing Promotion gates remain unchanged.
