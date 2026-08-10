# M4-P3 result-blind structural-utility design — round 112

Date: 2026-08-10

Role: Engineering Agent

Approved request: Engineering Request 444 / Execution 365

Research parent: Research Request 443 / Execution 364

## Primary goal

Create the independent `M4_P3_RESULT_BLIND_STRUCTURAL_UTILITY` Goal and bind its
zero-work estimand/interface compiler to the singular Research Evidence
Supervisor path. Reuse and rebind the existing unstarted structural-utility
intake instead of creating a competing completion path.

## Explicit non-goals

- No portfolio, fold, seed schedule, random replicate, structural metric, draw
  result, hit, payout, reward, rank, return, or historical outcome was read or
  generated.
- No old three-line training process was restarted.
- No Prediction v2 promotion, predictive P3 authorization, Evidence, model,
  expert, betting output, or production action was created.
- No preregistration, blind generator, walk-forward workload, Evidence Compiler
  result, or structural route decision was implemented in this round.

## Frozen design boundary

The estimand is the paired fold-level structural difference among three
equal-budget, same-universe arms, each producing exactly 100 distinct canonical
six-of-33 tickets:

1. uniform random without replacement as the primary null;
2. a frozen compliant legacy structural Top100 comparator, or fail closed;
3. the frozen existing Prediction v2 structural selector with an explicit
   budget-100 rule, or fail closed.

The fold count remains bounded to 60–120 and must be fixed by the next
preregistration before any generation. `unique_ticket_fraction = 1/1` is a
construction-validity invariant, not confirmatory evidence. The six
confirmatory coordinates are:

- pair coverage ratio, higher is better;
- triple coverage ratio, higher is better;
- high-overlap ticket-pair rate, lower is better;
- normalized pair-usage entropy, higher is better;
- largest similarity-cluster fraction, lower is better;
- structural-family concentration HHI, lower is better.

No unfrozen scalar utility or post-hoc Pareto preference is allowed. A later
positive structural result cannot establish predictive probability or expected
payout; historical prediction Evidence remains `INCONCLUSIVE` under every
allowed structural decision.

## Result-blind interface

Allowed inputs are the legal-universe descriptor, canonical candidate encoding,
candidate-internal structural features, digest-pinned cutoff-safe prior-only
feature snapshots, and frozen source/configuration/seed identities.

Forbidden inputs include target or future draw numbers, hit/payout/return/reward
labels, outcome ranks, raw draw rows in generator or evaluator interfaces,
previous structural result values used to select a choice, and post-hoc arm,
fold, seed, threshold, or metric changes.

The design compiler reads only the parent completed-event metadata and three
registered artifact identities. It does not load the parent payloads or the
registered structural result values. Its deterministic artifacts record:

```text
parent_payloads_read = 0
portfolios_generated = 0
folds_executed = 0
metric_results_read = 0
raw_outcome_rows_read = 0
previous_structural_result_values_read = 0
```

## Additive migration

The repository candidate is generated from the static canonical source
manifest. The durable PostgreSQL export is used only for a read-only additive
migration rehearsal and is never written back into the repository file.

The rehearsal against the durable 78-task manifest reported:

- one new Goal: `M4_P3_RESULT_BLIND_STRUCTURAL_UTILITY`;
- one revised, previously unstarted task:
  `prediction-v2-balanced-design-structural-utility-research-intake`;
- one new downstream task:
  `m4-p3-result-blind-structural-utility-preregistration`;
- one source fact and the already approved structural-utility Research event;
- zero Goal/task deletion, fact deletion, state regression, or unallowlisted
  definition rewrite;
- `import_performed=false` and `production_action=none`;
- dry-run digest
  `c8c2ce8e9817eb102e5ca24293e4ba50ae4813e207efac6812325cfd0bcd16a2`;
- rehearsed output manifest digest
  `1eb4767e2d40ca388923c7a2107e60928e44e9558a5672558c2899aabce0899e`.

The committed source manifest digest is
`6bfb2795468b0a9fbe5ef86c005903ce243fee0900a7ab2f72410eccf0330d3e`.
Its artifact index preserves the prior manifest identity as superseded and
appends the new current identity. The source contract digest is
`e954cb282933d8e41d9dae9497ee0a88016bceb69a9126edfb6235c70299658b`.

## Validation

- Ruff on every touched Python surface: passed.
- New M4-P3 result-blind design tests: 4 passed.
- Focused control-plane, Supervisor, M4 status, parent result-decision, artifact
  index, and source-integrity regressions: passed.
- Additive live migration rehearsal: `VERIFIED`, with no import.
- `git diff --check`: passed.
- Full Worker suite before updating the manifest index/source-partition
  expectations: 2324 passed, 4 skipped, 56 failed. Thirteen failures were
  directly caused by the new manifest/index identity and source partition and
  pass after correction. The remaining failures are pre-existing retired
  legacy-path expectations (old KDJ/training, forward evaluation, and old mail
  paths reject with `legacy_prediction_line_retired`) plus an older feasibility
  recovery fixture hard-coded to 71 tasks. This round does not reactivate or
  alter those retired paths.

## Integration matrix

| Link | Code-review status |
| --- | --- |
| Goal -> Resolver | independent Goal and singular rebound intake validated |
| Resolver -> Ready Queue | static source remains dependency-wait; durable migration rehearsal resolves the design after the parent completion fact |
| Ready Queue -> Supervisor | capability registered and focused-tested |
| Supervisor -> Capability | zero-work, result-blind compiler implemented |
| Capability -> Artifacts | design, preregistration handoff, and completion are deterministic |
| Artifacts -> Status | independent structural-utility projection tested |
| Status -> Next Task | preregistration task exists with no capability and a separate approval boundary |
| Deterministic replay | local compiler replay verified |
| Merged-main durable execution and replay | pending separate Operator Request |

Integration answer at the Engineering code-review boundary:

```text
NO — INTEGRATION_PENDING
```

The answer can become `YES — validated by unified mainline execution and replay`
only after a ready PR is merged and an independently approved Operator request
imports the additive manifest, dispatches the design through the canonical
Supervisor, registers its execution and three children, verifies replay, and
projects the preregistration consumer.

## Post-merge migration handoff correction — round 113

Merged-main preflight found that the round 112 builder retained the verified
live-state-preserving manifest only in memory and wrote the static source
candidate to its output path. Importing that static candidate would correctly
fail the repository's completed-state regression guard. Engineering Request
445 / Execution 366 therefore adds only two operational properties:

- the builder accepts the exact already-migrated canonical source manifest
  idempotently and rejects every other source identity;
- explicit `--output-kind merged` writes the existing additive migration
  result, while `source` retains the reviewable repository-generation mode.

On merged main, the corrected builder reproduced dry-run digest
`c8c2ce8e9817eb102e5ca24293e4ba50ae4813e207efac6812325cfd0bcd16a2`,
emitted live-state-preserving manifest
`1eb4767e2d40ca388923c7a2107e60928e44e9558a5672558c2899aabce0899e`,
left the canonical artifact index byte-identical, and resolved exactly the
M4-P3 design task as Ready. No Goal, task, estimand, source contract,
capability, status contract, artifact, or scientific boundary changed.

PR 324's clean GitHub runner also exposed one historical recovery-test fixture
that removed the seven post-recovery tasks known before this Goal but not the
new M4-P3 preregistration task. The fixture therefore contained 72 tasks while
the production recovery contract correctly requires the original 71-task
failure boundary. Round 113 changes only the fixture reconstruction: it removes
the independent M4-P3 Goal, both new tasks, and their source fact/event before
exercising the unchanged production recovery guard.

Round 113 validation on a clean detached worktree using the exact GitHub Worker
command: 2375 passed, 4 skipped, 6 explicitly deselected by CI, 22 warnings,
zero failures in 203.44 seconds. The merged-output and source-output modes,
byte-identical artifact-index pass-through, exact Ready resolution, Ruff, and
`git diff --check` also passed.

## Objective-class schema correction — round 115

Operator Request 446 / Execution 367 attempted the approved additive import on
merged main and failed before dispatch. PostgreSQL rejected
`structural_decision_utility` because the Python enum and canonical manifest had
been extended in round 112 while
`research_os_goal_definitions_objective_class_check` still contained only the
previous four values. The import transaction rolled back: the durable control
plane remained 3 Goals / 78 tasks, no structural Goal or task was inserted, no
Supervisor task was dispatched, and no artifact or result payload was read.

Engineering Request 447 / Execution 368 corrects only that schema boundary.
Both fresh-table creation and the idempotent existing-database ALTER path now
allow the exact five-value domain: `prediction_quality`,
`structural_decision_utility`, `runtime_capability`, `knowledge_quality`, and
`maintenance_integrity`. The named CHECK is replaced without changing tables,
rows, keys, indexes, manifests, states, facts, executions, registrations, or
the scientific contract. Live DDL and the import retry remain separate Operator
actions after merge.

Round 115 validation: focused schema/repository/M4-P3/Research OS regressions
passed; Ruff and `git diff --check` passed; the exact GitHub Worker command in a
clean detached worktree completed with 2375 passed, 4 skipped, 6 CI-deselected,
22 warnings, and zero failures in 204.60 seconds.
