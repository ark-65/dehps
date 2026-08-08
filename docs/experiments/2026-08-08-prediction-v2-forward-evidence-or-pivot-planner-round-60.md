# Prediction v2 Forward-Evidence or Structural-Pivot Planner — Round 60

Date: 2026-08-08

Role sequence: Research Agent -> Engineering Agent

Primary goal: consume the replay-verified Prediction v2 promotion-planner
summaries exactly once, determine whether a candidate-specific prospective
evidence program is operationally defined and feasible inside the explicit
two-week planning horizon, and select the structural decision-support design
route without relabelling `INCONCLUSIVE` Evidence.

## Non-goals

- No raw history, database data row, CSV, fold, bootstrap child, checkpoint,
  candidate score, ranking, prior prediction, or duplicate index is read.
- No Evidence, equivalence, threshold, MDE, estimator, hierarchy, model, or
  historical conclusion is recomputed or changed.
- No candidate model, structural algorithm, expert, promotion, P3 transition,
  betting output, or production action is created.

## Typed authorization

- Research Request 382 / Execution 303 froze the result-aware selection
  contract after the Promotion Planner was durably executed and replayed.
- Engineering Request 383 / Execution 304 authorizes only the content-addressed
  planner, additive DAG migration, Supervisor execution/replay integration,
  status projection, tests, and this report.
- Durable execution remains forbidden before merge and a separate Operator
  release.

## Scientific selection

Historical Evidence remains `INCONCLUSIVE`; the upstream decision remains
`HOLD_BASELINE_ONLY`, and no accepted candidate identity exists.

The feasibility calculation is explicitly classified as
`NON_EVIDENTIARY_SAME_LAW_SQUARE_ROOT_PROJECTION`. Under the planning-only
assumption that the frozen endpoint, variance, and dependence-aware resampling
law remain stable:

```text
n_required = ceil(2581 * (0.013459908060402983 / 0.01)^2) = 4676
additional issues = 4676 - 2581 = 2095
two-week maximum at 3 issues/week = 6 issues
projected two-week MDE = 0.01344429029293817 bits/issue
```

At the planning cadence, 2,095 issues are about 698.33 weeks or 13.38 years.
This is not a formal power claim and is not Evidence. It establishes only that
ordinary prospective accumulation cannot cross the frozen 0.01 bits/issue MDE
threshold inside the two-week operational horizon.

The selected near-term program is therefore
`STRUCTURAL_DECISION_SUPPORT_PIVOT`, with the next consumer
`prediction-v2-structural-decision-support-design`. Prediction research is
`FROZEN_PENDING_SEPARATE_RESULT_BLIND_PREREGISTRATION`, not rejected. Passive
future observations may be used only by a later separately preregistered
program.

## Duplicate-validation boundary

The capability consumes exactly five content identities:

1. this source contract;
2. the registered Promotion Planner mainline execution;
3. the registered promotion plan;
4. the registered forward-evidence-or-pivot route;
5. the registered Promotion Planner completion.

It performs only constant-size schema, digest, lineage, status, Evidence,
route, shadow-boundary, and frozen-arithmetic checks. Execution and replay
must both report:

```text
database_queries = 0
historical_rows_read = 0
folds = 0
bootstrap_children = 0
duplicate_validation = false
```

## Mainline outputs

The Planner emits three immutable children plus one execution record:

1. prospective evidence feasibility assessment;
2. structural decision-support pivot plan;
3. forward-or-pivot planner completion;
4. unified mainline execution.

It creates only
`prediction-v2-forward-evidence-or-pivot-planner:COMPLETE`. The additive
migration revises only the current Ready planner, adds only
`prediction-v2-structural-decision-support-design`, and adds one source fact.

## Scientific cross-review

Einstein-style falsification pass: the smallest testable claim is route
feasibility, not whether the historical signal is zero. The projection must be
able to fail if its fixed constants change and must never become Evidence.

Gauss-style verification pass: the arithmetic produces 4,676 total issues,
2,095 additional issues, and a two-week projected MDE of
0.01344429029293817. Stable variance and dependence are its weakest
assumptions, so it is a planning projection only.

Riemann-style structural pass: without an accepted predictive coordinate, the
valid near-term space is transparent combination-space compression, risk
control, and diversity design—not an unsupported continuation of a candidate
expert family.

Disagreement: a future candidate-specific program may become legal, but its
model, endpoint, horizon, and power contract do not exist yet.

Smallest shared conclusion: select structural design now, keep Prediction v2
`SHADOW_ONLY / BASELINE_ONLY`, preserve `INCONCLUSIVE`, and require a new
result-blind preregistration before any future prediction experiment.

## Validation

- Source contract, bound source bytes, frozen projection and shadow identity:
  PASS.
- Constant-size builder, upstream tamper failure, and structural-route
  selection: PASS.
- Additive migration with one revised task, one new task, no state regression,
  no fact deletion, and no unallowlisted rewrite: PASS.
- Synthetic Supervisor execution and deterministic replay: PASS.
- Focused Planner tests: 7 passed.
- Focused Planner/Gate/Research-OS/hardening suite: 123 passed, 4 skipped.
- Complete non-retired Worker suite: 2165 passed, 4 skipped in 259.61s.
- Fresh merged Supervisor execution and durable replay: pending publication.

## Integration matrix

| Link | Engineering proof | Durable mainline proof |
|---|---|---|
| Goal -> Resolver | frozen task and dependency contract load | pending import |
| Resolver -> Ready Queue | exact five input identities declared | pending Ready observation |
| Ready Queue -> Supervisor | singular capability registered | pending merged run |
| Supervisor -> Capability | synthetic execution completes | pending merged run |
| Capability -> Artifacts | three children plus execution are deterministic | pending registration |
| Artifacts -> Status | structural pivot and zero-work counters project | pending durable projection |
| Status -> Next Task | exact structural-design consumer declared | pending Ready observation |
| Deterministic replay | four synthetic payloads replay byte-identically | pending durable replay |

Final integration answer for this engineering checkpoint:

**NO — INTEGRATION_PENDING.**

It becomes `YES — validated by unified mainline execution and replay` only
after merge, additive import, one fresh merged Supervisor execution, four
registrations, exact downstream Ready observation, and deterministic replay.
