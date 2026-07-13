# Round 20: Hypothesis Registry Foundation

## Outcome

Round 20 establishes a persistent, status-constrained, auditable Hypothesis Registry. It adds no model, Advisor, feature, strategy, weight, training behavior, Objective change, Candidate Source change, Promotion change, Angular page, Agent, or automated research action.

## Primary goal and non-goals

Primary goal: represent hypothesis families, hypotheses, experiments, evidence, decisions, rejection scope, and reopen conditions as linked durable records.

Explicit non-goals remained intact:

- no production training code or schema change;
- no automatic experiment execution or strategy promotion;
- no historical Markdown scanning or inferred conclusions;
- no LLM/Agent orchestration;
- no production database writes;
- no production Supervisor restart.

## Data model

Five additive tables were added to both `infra/postgres/init/001_init.sql` and the Worker compatibility schema path:

1. `research_hypothesis_families`;
2. `research_hypotheses`;
3. `research_hypothesis_experiments`;
4. `research_hypothesis_evidence`;
5. `research_hypothesis_decisions`.

The isolated database catalog confirmed primary keys, unique keys, checked status/scope/direction values, restricted foreign keys, JSON type checks, self-parent prevention, and Evidence content-hash deduplication.

Decision rows are append-only through a PostgreSQL update/delete trigger. Hypothesis and family status triggers reject direct updates; only the Repository transaction-local guard can perform a status change. Repository tests prove that a Decision write failure rolls back the status update.

## State and transition rules

Allowed hypothesis path:

```text
proposed -> preregistered -> running
running -> accepted_for_followup | rejected | inconclusive | invalidated
accepted_for_followup -> running | rejected | inconclusive
```

`proposed -> running` and every in-place transition out of `rejected` are illegal. Experiment terminal states cannot transition. Rejected/exhausted families use a separate explicit reopen path.

Every status change writes a Decision with previous/new status, decision code, summary, structured reason, Evidence citations, actor, and timestamps.

## Rejection scope and reopen

Parameter-region rejection records the exact parameter/representation boundary, metrics, data boundary, and retry prohibitions. It moves an active family to `partially_rejected` but permits genuinely new hypotheses.

Mechanism-family rejection records a mechanism signature and moves the family to `rejected`. The Repository then rejects new hypotheses until explicit family reopen.

Both rejection forms prohibit seed, epoch, depth, nearby-weight, same-history-search, or rename-only recycling.

Hypothesis reopen does not overwrite the rejection. It creates a new `proposed` child row and records `hypothesis_reopened_as_version`. Reopen requires a stored condition, reason, unique key, and changed basis in new data, a feature family, a causal variable, or a validation protocol.

## CLI

The human-only `dehps hypothesis` Typer group implements:

- family create/list;
- hypothesis create/list/show;
- preregister/start/reject/inconclusive/invalidate/reopen;
- experiment and Evidence registration;
- Decision listing.

Complex input is supplied as JSON files. Output is stable sorted JSON. Domain errors use stderr and exit code 2. No experiment-run, auto-research, or strategy-promotion command exists.

## Read-only API

The new NestJS module serves seven GET endpoints for family, hypothesis, experiment, Evidence, and Decision reads. It supports status/family/time filters and pagination, normalizes JSONB, returns 404 for missing entities, and has no write route.

An isolated live API process successfully read all seven routes from `dehps_round20_smoke`; a missing hypothesis returned HTTP 404.

## Isolated smoke

Database: `dehps_round20_smoke`.

Explicitly registered families:

- `generic_structural_mlp` -> `partially_rejected`, scope `parameter_region`;
- `nonlinear_kdj_weight_interaction` -> `rejected`, scope `mechanism_family`.

Explicitly registered hypotheses:

- `round89_generic_structural_mlp_v1` -> `rejected`;
- `round89_nonlinear_kdj_weight_interaction_v1` -> `rejected`;
- `round89_temporal_residual_feature_mlp_v2` -> `proposed`, parent ID of the first rejected hypothesis.

The structure-MLP evidence records preserve random-split AUC, temporal-positive AUC, and seed instability. The Neural KDJ evidence preserves frozen-best/candidate objective, Top100/Top1000, and tail-risk comparisons from `docs/experiments/autonomous-hypothesis-cycle-2026-07-13.md`.

Formal CLI sequence completed family/hypothesis/experiment creation, preregistration, start, Evidence registration, rejection, Decision listing, and reopen. A seed/epoch-only reopen returned exit code 2. A new temporal residual-sign feature family created a child version without modifying the rejection.

Database negative checks returned errors as required:

- direct hypothesis status update: rejected by status guard;
- Decision update: rejected as immutable;
- duplicate Evidence hash/type/hypothesis: rejected by unique index;
- deleting a referenced hypothesis: rejected by foreign key;
- creating a hypothesis in the rejected Neural KDJ family: CLI exit code 2.

Final isolated counts included two families, three hypotheses, two experiments, four Evidence rows, and nine Decisions (including family decisions).

## Production isolation evidence

No Registry DDL or smoke writes were applied to production database `dehps`. The following production audit returned `NULL` for all five relations:

```sql
SELECT name, to_regclass(name)
FROM unnest(ARRAY[
  'research_hypothesis_families',
  'research_hypotheses',
  'research_hypothesis_experiments',
  'research_hypothesis_evidence',
  'research_hypothesis_decisions'
]) AS name;
```

Because the five production relations do not exist, they contain no smoke keys. This is the fail-closed interpretation of “do not write production database.”

The prior Supervisor run `20260713-143325` was not restarted. It completed five rounds and entered `waiting_for_forward_issue`; Round 20 did not change its process or frozen strategy.

## Validation

Worker baseline before changes:

```text
693 passed
```

Worker after changes:

```text
.venv/bin/python -m pytest -q
756 passed in 23.66s

DB_PORT=1 .venv/bin/python -m pytest -q
756 passed in 21.47s
```

API:

```text
npm test
58 passed

npm run build
passed
```

The 63 new Worker tests cover schema, all declared transitions, illegal transitions, transaction rollback, preregistration, start/completion gates, CLI JSON/errors, parameter/family rejection, reopen, path validation, and Evidence deduplication.

## Known limitations

- The Registry records changed-basis facts for reopen, but a human still judges whether they semantically satisfy the stored condition.
- Decision Evidence citations are stored as an immutable JSON ID list, not a join table.
- Historical reports remain untouched; the two Round 89 cases exist only in the isolated validation database.
- Production Registry initialization is intentionally deferred to an explicit deployment/migration action after code acceptance.

## Next round

Round 21 may separate Research and Engineering Agent authority only after an explicit goal. It must consume this registry without gaining production promotion authority and must not bypass preregistration or rejection memory.
