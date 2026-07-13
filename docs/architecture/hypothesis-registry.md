# Hypothesis Registry Architecture

Round 20 makes research governance durable without coupling it to training or promotion. The registry records human-created families, hypotheses, experiments, evidence, decisions, and reopen conditions. It does not run experiments, change candidates, or promote strategies.

## Data model

| Table | Responsibility | Important constraints |
| --- | --- | --- |
| `research_hypothesis_families` | Mechanism-level boundary and rejection scope | unique `family_key`; checked status/scope; object metadata |
| `research_hypotheses` | Falsifiable claim and preregistration contract | unique `hypothesis_key`; restricted family/parent FKs; no self-parent; checked status/scope |
| `research_hypothesis_experiments` | Explicit run/report/artifact association | unique `experiment_key`; restricted hypothesis FK; optional external/training identifiers |
| `research_hypothesis_evidence` | Immutable-by-service observed facts | restricted hypothesis/experiment FKs; checked direction; `(hypothesis, type, content_hash)` dedupe |
| `research_hypothesis_decisions` | Append-only lifecycle audit | exactly one hypothesis/family subject; update/delete trigger rejects mutation |

All timestamps use `TIMESTAMPTZ`. JSON objects and arrays have database type checks and safe defaults. Historical rows use `ON DELETE RESTRICT`; the registry never cascades away experiments, evidence, decisions, parents, or children.

Status changes are protected twice:

1. Python transition functions reject illegal edges.
2. PostgreSQL status triggers reject direct updates unless the Repository enables the transaction-local registry transition guard.

The Repository changes status and inserts its Decision in the same transaction. A Decision insertion failure rolls back the status update.

## State machines

Hypothesis:

```text
proposed -------> preregistered -------> running
    |                   |                  |  |  |  |
    +-> invalidated     +-> invalidated   |  |  |  +-> invalidated
                                           |  |  +----> inconclusive
                                           |  +-------> rejected
                                           +----------> accepted_for_followup

accepted_for_followup -> running | rejected | inconclusive
```

`rejected`, `inconclusive`, and `invalidated` are not changed back in place. A rejected hypothesis can only use the explicit reopen operation, which preserves the old row and creates a new `proposed` child/version.

Family:

```text
active -> partially_rejected | rejected | exhausted
partially_rejected -> active | rejected | exhausted
rejected/exhausted -- explicit reopen only --> reopened
reopened -> active | partially_rejected | rejected | exhausted
```

Experiment:

```text
planned -> running | cancelled | invalidated
running -> completed | failed | invalidated | cancelled
```

Experiment terminal states are immutable.

## Preregistration and completion gates

`preregister()` requires non-empty:

- statement;
- null hypothesis;
- minimal non-null;
- invariants;
- baseline definition;
- metric definition;
- failure condition;
- self-deception risk.

`start()` requires a preregistered hypothesis, at least one planned experiment, and a family that is neither rejected nor exhausted.

`complete_with_decision()` requires a running hypothesis, at least one Evidence record, explicit cited Evidence IDs, no associated running experiment, and a non-empty decision code.

## Parameter rejection versus mechanism rejection

`parameter_region` rejects a bounded configuration/representation region. Its Decision must record:

- rejected parameter region;
- failed metrics;
- data boundary;
- prohibited parameter-only retries.

The family becomes `partially_rejected` but remains open to genuinely different hypotheses.

`mechanism_family` rejects the normalized input/target/validation mechanism. Its Decision must additionally record a mechanism signature. The family becomes `rejected`, and the Repository refuses new active hypotheses under it.

Both scopes explicitly prohibit presenting these as a new mechanism:

- a new random seed;
- more epochs;
- more depth;
- nearby weights;
- more search rounds on the same history;
- renaming without changing inputs, target, and validation protocol.

## Reopen semantics

Reopen never edits or deletes the rejection. It requires:

- a stored non-empty `reopen_condition`;
- a non-empty `reopen_reason`;
- a new unique hypothesis key;
- a recorded change in new data, feature family, causal variable, or validation protocol.

The new hypothesis uses `parent_hypothesis_id` to reference the rejected row and starts as `proposed`. The old hypothesis remains `rejected`; a new append-only Decision records the created version. A mechanism-rejected family must itself be explicitly reopened before a new hypothesis version can be created.

## Human CLI

The CLI accepts complex data through `--input JSON_FILE` and emits stable sorted JSON:

```text
dehps hypothesis family-create
dehps hypothesis family-list
dehps hypothesis create
dehps hypothesis list
dehps hypothesis show
dehps hypothesis preregister
dehps hypothesis start
dehps hypothesis reject
dehps hypothesis inconclusive
dehps hypothesis invalidate
dehps hypothesis reopen
dehps hypothesis experiment-add
dehps hypothesis evidence-add
dehps hypothesis decisions
```

Registry errors go to stderr and return exit code 2. There is no command for automatic experiment execution, Agent research, production promotion, or strategy mutation.

Report and artifact paths are normalized to repository-relative paths under `docs/experiments/` or `data/output/`. Missing files fail closed unless the input explicitly marks an external reference. Content SHA-256 calculation is optional.

## Read-only API

The NestJS `ResearchHypothesisModule` exposes only GET endpoints:

```text
GET /research/hypothesis-families
GET /research/hypothesis-families/:key
GET /research/hypotheses
GET /research/hypotheses/:key
GET /research/hypotheses/:key/experiments
GET /research/hypotheses/:key/evidence
GET /research/hypotheses/:key/decisions
```

Lists accept `status`, `family_key`, `created_after`, `created_before`, `limit`, and `offset` where meaningful. Responses identify their entity type. PostgreSQL JSON strings are normalized into objects/arrays, and missing detail or child subjects return 404. The module exposes no POST, PUT, PATCH, or DELETE route.

## Authority boundary

- Humans may use the CLI to register and decide hypotheses.
- Repository and Service enforce lifecycle and audit constraints; they do not judge statistical significance.
- Training, Objective Policy, Candidate Source, Advisor Registry, Evaluation, and Promotion do not import or consult the registry.
- The read-only API cannot trigger state transitions.
- Round 20 does not add LLM, prompt, Agent, scheduler, vector search, or automatic Markdown inference.

## Known limitations

- Reopen-condition satisfaction is recorded and structurally constrained, but semantic truth still requires human review.
- Evidence IDs in Decisions are an immutable JSON citation list rather than individual foreign-key rows.
- Existing Markdown reports are not migrated automatically; only explicit human registration is supported.
- Registry DDL is additive and available through PostgreSQL initialization and Worker compatibility setup, but Round 20 deliberately does not apply it to the production database.
