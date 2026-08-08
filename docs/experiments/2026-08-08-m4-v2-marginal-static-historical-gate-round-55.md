# M4 V2 Marginal-Static Historical Gate Compiler — Round 55

Date: 2026-08-08

Role sequence: Research Agent -> Engineering Agent

Primary goal: compile the already complete and replay-verified Round 54
historical result exactly once under the frozen three-branch Measurement v2
family, create conditional historical Evidence, and route the immutable result
to a separate Prediction v2 promotion planner without repeating any fold,
bootstrap, database query, or duplicate-validation pass.

## Non-goals

- No historical fold or bootstrap child is recomputed.
- No database query, CSV export, model fitting, threshold tuning, or post-hoc
  family redefinition is performed.
- No Temporal or Joint branch result is invented; each unrun branch receives
  the preregistered p-value 1.0.
- No production activation, direct Prediction v2 promotion, betting output, or
  forward-evidence claim is made.

## Typed authorization and result boundary

- Research Request 373 / Execution 294 froze the result-aware decision
  contract before the Engineering Agent read any durable statistical payload.
- Engineering Request 374 / Execution 295 authorized the content-addressed
  compiler, additive DAG migration, Supervisor integration, status projection,
  deterministic replay, synthetic tests, and this report.
- Engineering validation used synthetic positive, negative, unstable, and
  underpowered fixtures only. It did not read the durable Round 54 p-value,
  effect interval, half means, thirds, MDE, or equivalence result.

## Frozen decision rules

The fixed family is `MARGINAL_STATIC`, `TEMPORAL_MARGINAL_INCREMENT`, and
`JOINT_RESIDUAL_INCREMENT`, with Holm familywise alpha 0.05. The two unrun
branches remain in the family with p-value 1.0.

- `POSITIVE`: MeasurementHealth PASS, complete run, distinct candidate and
  baseline, Holm-adjusted p-value at most 0.05, simultaneous lower effect bound
  greater than 0.01 bits/issue, and both frozen half means greater than zero.
- `NEGATIVE`: the same health/completeness/identity boundaries, adjusted
  p-value greater than 0.05, sufficient equivalence power, MDE in [0, 0.01],
  and the one-sided equivalence upper bound at most 0.01 bits/issue.
- Every other state is `INCONCLUSIVE`. A statistically significant but
  half-unstable result and a nonsignificant but underpowered result therefore
  receive no promotion-planning eligibility.

The three frozen thirds remain diagnostic and have no decision credit. Global
coverage remains `PARTIAL`; only a positive marginal result may emit
`CANDIDATE_INFORMATION_FOUND`.

The Einstein-style constraint was to ask what would falsify the candidate
before interpreting its historical result. Half stability, practical effect,
multiplicity, power, and equivalence are therefore compiled from immutable
inputs rather than selected after seeing the answer.

## Duplicate-work removal

The Gate capability reads only already registered immutable artifacts:

1. Round 54 mainline execution;
2. completion index;
3. inference aggregate;
4. undecided branch candidate;
5. execution completion;
6. frozen Gate Compiler contract;
7. this content-addressed source contract.

It executes zero folds, zero bootstrap children, and zero database queries.
`duplicate_validation=false` remains explicit. Integrity is checked once at
the registered artifact boundary and again by deterministic replay; no second
physical scan or statistical execution exists.

## Mainline outputs implemented

The capability emits six immutable children plus one mainline execution:

1. legal-uniform baseline model identity;
2. evaluated marginal-static candidate model identity;
3. hierarchical fixed-family Gate output;
4. conditional historical Evidence;
5. Prediction v2 promotion-planning eligibility;
6. Gate completion;
7. unified mainline execution record.

The candidate is accepted for downstream baseline use only for `POSITIVE`.
Even then, the output is merely eligible for the separate
`prediction-v2-promotion-planner`; `promotion_gate_opened=false` and
`production_action=none` are invariant.

## Additive migration contract

The migration revises only the previously drafted Gate task and adds only the
Prediction v2 promotion planner. It preserves all durable task states and
facts, adds the Gate source identity, and forbids deletion or unallowlisted
definition rewrites. The planner depends on the completed Gate task and its
immutable completion fact, so the resolver cannot dispatch it early.

## Validation

- Content-addressed source contract and bound-byte verification: PASS.
- Python compilation, Ruff, JSON parsing, manifest identity, and diff check:
  PASS.
- Round 55 focused tests: 9 passed.
- Synthetic Supervisor Gate execution registered all 7 artifacts: PASS.
- Synthetic deterministic replay rebuilt and byte-verified all 7 artifacts:
  PASS.
- Round 54 historical execution plus Supervisor regression: 54 passed.
- Complete non-retired Worker suite: 2,143 passed, 4 skipped. The seven
  explicitly retired legacy prediction test files remain outside this suite;
  their 43 expected failures were separately observed under the active legacy
  retirement guard.
- Fresh merged Supervisor execution and durable replay: pending publication.

## Integration matrix

| Link | Engineering proof | Durable mainline proof |
|---|---|---|
| Goal -> Resolver | additive Gate revision and planner dependency validate | pending import |
| Resolver -> Ready Queue | exact seven input identities are frozen | pending Ready observation |
| Ready Queue -> Supervisor | Gate capability is registered | pending merged run |
| Supervisor -> Capability | synthetic execution completes with zero recomputation | pending merged run |
| Capability -> Artifacts | six children plus execution are deterministic | pending registration |
| Artifacts -> Status | Evidence, eligibility, and planner projection tested | pending projection |
| Status -> Next Task | exact Prediction v2 planner is declared | pending Ready observation |
| Deterministic replay | all seven synthetic identities replay | pending durable replay |

Final integration answer for this engineering checkpoint:

**NO — INTEGRATION_PENDING.**

The capability may advance to `VALIDATED_IN_MAINLINE` only after the ready PR
is merged, a fresh merged Supervisor compiles the exact durable Round 54
artifacts once, all seven outputs are registered, the Prediction v2 promotion
planner becomes Ready, and replay verifies identical registered bytes with
zero database queries, zero folds, zero bootstrap children, and no duplicate
validation.

## Round 56 runtime recovery note

The first merged Operator attempt failed before Gate compilation because the
Supervisor looked for `measurement_v2_gate_compiler_contract` in the
historical-design child registration set. That contract is an immutable parent
owned by `m4-v2-measurement-contract-design` and is intentionally not
re-registered by historical design. No statistical decision was compiled, no
Round 55 artifact was registered, and no Evidence was created.

The narrow recovery changes only the owner task used by execution and replay
to load the same frozen digest
`9f9519be92fb5db4a4fb4939d1d5d3d32f7646a6e449f3dd20fd5c63b409f821`.
The regression test now asserts that exact owner lookup. The failed durable
event remains preserved; scientific rules, source contract, manifest, task
inputs, and all immutable parent identities are unchanged.
