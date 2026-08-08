# Prediction v2 Promotion Planner — Round 58

Date: 2026-08-08

Role sequence: Research Agent -> Engineering Agent

Primary goal: consume the replay-verified Measurement v2 Gate result exactly
once, compile the frozen Prediction v2 planning route, and preserve the live
`SHADOW_ONLY / BASELINE_ONLY` boundary without repeating historical,
fold-level, bootstrap-level, database, or duplicate validation.

## Non-goals

- No raw history, CSV, fold, bootstrap child, checkpoint, candidate score,
  prediction rank, or database row is read.
- No duplicate scan or second validation pass is performed.
- No Evidence value, threshold, MDE, equivalence rule, hierarchy, estimator,
  model identity, or time partition is changed.
- No Temporal or Joint branch is executed without an accepted marginal
  baseline.
- No candidate expert, production promotion, P3 execution, betting output, or
  production action is authorized.

## Typed authorization

- Research Request 379 / Execution 300 froze the exhaustive result-aware route
  contract after the Gate had produced replay-verified Evidence.
- Engineering Request 380 / Execution 301 authorized only the singular
  content-addressed planner, additive DAG migration, Supervisor execution and
  replay, status projection, tests, and this report.
- The Engineering contract explicitly sets
  `duplicate_validation_allowed=false` and does not authorize durable execution
  before merge.

## Frozen route

| Historical Evidence | Plan decision | Downstream route | Direct promotion |
|---|---|---|---|
| `POSITIVE` | `FORWARD_SHADOW_EVIDENCE_PLAN_ELIGIBLE` | `FUTURE_ONLY_PREDICTION_V2_CANDIDATE_EVIDENCE` | false |
| `NEGATIVE` | `PREDICTIVE_PROMOTION_CLOSED` | `STRUCTURAL_DECISION_SUPPORT_PIVOT_REVIEW` | false |
| `INCONCLUSIVE` | `HOLD_BASELINE_ONLY` | `FUTURE_EVIDENCE_OR_STRUCTURAL_PIVOT_REVIEW` | false |

The actual frozen Gate value is `INCONCLUSIVE`, so this planner must emit
`HOLD_BASELINE_ONLY`. It must not relabel p=1 as equivalence or a negative
finding: the MDE is 0.0134599081 bits/issue, above the 0.01 practical threshold,
and `equivalence_power_sufficient=false`.

## Duplicate-validation removal

The capability receives exactly eight content identities:

1. this planner source contract;
2. the registered Gate mainline execution;
3. legal-uniform baseline model identity;
4. evaluated marginal candidate model identity;
5. fixed-family Gate output;
6. historical Evidence;
7. Prediction v2 planning eligibility;
8. Gate completion.

It performs only constant-size schema, digest, lineage, Evidence, eligibility,
coverage, and shadow-contract consistency checks. It does not traverse the
3,481 historical issues, 2,581 folds, 16,000 bootstrap children, or any
duplicate index. Execution, completion, status, and deterministic replay all
carry:

```text
database_queries = 0
historical_rows_read = 0
folds_executed = 0
bootstrap_children_executed = 0
duplicate_validation = false
```

This removes repeated validation work while retaining the content-addressed
boundary necessary to reject a mismatched or tampered registered summary.

## Mainline outputs

The Planner emits three immutable children plus one execution record:

1. Prediction v2 promotion plan;
2. forward-evidence or structural-pivot route;
3. promotion-planner completion;
4. unified mainline execution.

It creates only `prediction-v2-promotion-planner:COMPLETE`. It creates no new
Evidence fact, accepted model, expert authorization, promotion, or production
state.

The additive migration revises only the existing promotion-planner task, adds
only `prediction-v2-forward-evidence-or-pivot-planner`, and adds one source
fact. Existing task states, facts, execution events, failed events, and
registered artifacts are preserved.

## Scientific cross-review

Einstein-style falsification pass: the smallest justified operational claim is
that a consistent `POSITIVE` result could be planned for future-only shadow
evidence. The actual `INCONCLUSIVE` value cannot justify a candidate expert,
negative claim, or production route.

Gauss-style exactness pass: the positive rule failed and the negative rule is
unproven because the frozen MDE exceeds the practical threshold and power is
insufficient. The planner therefore preserves `INCONCLUSIVE` exactly.

Riemann-style structural pass: Temporal and Joint are conditional incremental
spaces, not independent escape routes. Changing the hierarchy after observing
the marginal result would be a new research program.

Disagreement: more prospective marginal evidence versus a structurally
reframed measurement space cannot be decided by the current Gate.

Smallest shared conclusion: keep `BASELINE_ONLY`, close direct promotion, and
send the unresolved choice to a separately preregistered future-evidence-or-
pivot planner.

## Validation

- Source contract, frozen policy, bound source bytes, and Prediction v2 shadow
  identity: PASS.
- Exhaustive synthetic `POSITIVE`, `NEGATIVE`, and `INCONCLUSIVE` routes: PASS.
- Evidence/eligibility mismatch rejection: PASS.
- Additive migration with one revised task, one new task, no state regression,
  no fact deletion, and no unallowlisted rewrite: PASS.
- Synthetic Supervisor execution: four registrations, no duplicate validation,
  no history/fold/bootstrap/database work: PASS.
- Synthetic deterministic replay: identical four registered payloads with no
  duplicate validation or new Evidence: PASS.
- Focused Planner, Gate, historical execution, control-plane, artifact-index,
  persistence, and replay suite: 67 passed.
- Ruff, JSON parsing, Python compilation, and diff check: PASS.
- Complete non-retired Worker suite: 2,158 passed, 4 skipped. The seven
  explicitly retired legacy prediction test files remain excluded.
- Fresh merged Supervisor execution and durable replay: pending publication.

## Integration matrix

| Link | Engineering proof | Durable mainline proof |
|---|---|---|
| Goal -> Resolver | frozen task and dependency contract load | pending import |
| Resolver -> Ready Queue | exact eight input identities declared | pending Ready observation |
| Ready Queue -> Supervisor | singular capability registered | pending merged run |
| Supervisor -> Capability | synthetic execution completes | pending merged run |
| Capability -> Artifacts | three children plus execution are deterministic | pending registration |
| Artifacts -> Status | baseline-only route and no-duplicate counters project | pending durable projection |
| Status -> Next Task | exact future-evidence-or-pivot consumer declared | pending Ready observation |
| Deterministic replay | four synthetic payloads replay byte-identically | pending durable replay |

Final integration answer for this engineering checkpoint:

**NO — INTEGRATION_PENDING.**

The answer may become `YES — validated by unified mainline execution and
replay` only after the ready PR is merged, the additive manifest is imported,
a fresh merged Supervisor executes the Planner once, all four artifacts are
registered, the declared downstream planner is Ready, and replay verifies the
same bytes with zero database queries, history rows, folds, bootstrap children,
and duplicate validation.
