# M4 V2 Marginal-Static Historical Preregistration — Round 53

Date: 2026-08-08

Role sequence: Research Agent -> Engineering Agent

Primary goal: freeze and integrate the exact content-addressed historical
dataset, fold, checkpoint, resampling, and efficient-resume identities before
any historical score or endpoint is computed.

## Non-goals

- No historical score was computed.
- No formal walk-forward fold was executed.
- No bootstrap child was executed.
- No historical Evidence, accepted model, promotion, betting output, or
  production action was created.
- No temporal or joint branch was started.

## Typed authorization

- Research Request 367 / Execution 288 froze the falsifiable, result-blind
  preregistration contract.
- Engineering Request 368 / Execution 289 authorized only the implementation,
  additive DAG revision, status projection, deterministic replay, tests, and
  this report.
- Engineering did not query `ssq_history`; all implementation tests used a
  synthetic 3,481-row boundary fixture.

## Research correction

The earlier identity
`30224d09a8b2d9080d3bc848f50b534c6d6de50b2eac867882915e85acbf206b`
was explicitly documented as metadata-only. It could not prove the red-number
content used by the future measurement. Round 53 therefore retains that value
only as lineage and makes the existing `history_snapshot.v1.0.0` digest over
`(issue, draw_date, sorted red_numbers)` the sole formal dataset identity.

This was the decisive Einstein-style check: state the observable claim, ask
what artifact could falsify a silent historical revision, and reject an
identity that did not hash the measured content.

## Frozen measurement boundary

- Query: one bounded, ordered `ssq_history` query for issues `2003001` through
  `2026084` under a read-only repeatable-read transaction.
- Rows: exactly 3,481, from 2003-02-23 through 2026-07-23.
- Training prefix: ordinals 1..900.
- Evaluation folds: ordinals 901..3481, exactly 2,581 identities.
- Strict-prior order per fold: fit counts through `t-1`, persist the virtual
  checkpoint, expose target `t`, score it, update six counts with `t`, settle.
- Resampling: 2,000 deterministic root seeds, eight fixed schemes, 16,000
  child identities; no best-seed selection.
- Primary inference: non-circular moving-block bootstrap length 5, fixed
  three-endpoint Holm family, preregistered intervals, equivalence rule,
  dependence-aware MDE, and time-stability partitions.

## Efficiency and resume contract

The future executor is constrained to:

- load the immutable dataset snapshot once and keep it memory-resident;
- perform zero database reads and zero database writes per fold;
- initialize one 33-count vector from the first 900 issues and update only the
  six observed red counts after each settled fold;
- use 11 fold shards of size 256, with 21 folds in the final shard;
- load the immutable completion index once;
- skip a verified completed fold without recomputation;
- skip a completed shard after one aggregate-digest check, without a directory
  scan;
- dispatch every new fold at most once in an execution;
- keep `duplicate_validation=false` and avoid routine physical-checkpoint
  scans.

This round removes repeated validation from the hot path without weakening
identity checks: validation moves to the content-addressed snapshot, immutable
completion index, and shard aggregate boundary.

## Mainline artifacts implemented

The capability deterministically emits six immutable child artifacts plus its
mainline execution record:

1. content-addressed historical dataset snapshot;
2. 2,581-fold identity manifest;
3. checkpoint/settlement order manifest;
4. 2,000-root / 16,000-child resampling manifest;
5. efficient historical execution plan;
6. preregistration completion;
7. unified mainline execution record.

The replay path reconstructs all six child artifacts from the registered
dataset records. It performs zero database queries, hashes zero newly read
rows, computes zero scores, executes zero folds and zero bootstrap children,
and verifies all seven registered identities.

## Additive migration proof

The dry run against durable manifest
`d318cd28ec4bd92371bd43e3bc5b91492921f2764d808b49312a6cbbcfdac443`
returned `VERIFIED`:

- live tasks: 57;
- output tasks: 58;
- revised task: historical preregistration only;
- added task: historical measurement execution only;
- unchanged tasks: 56;
- state regressions: 0;
- fact deletions: 0;
- task deletions: 0;
- unallowlisted definition rewrites: 0;
- dry-run artifact:
  `26b0ab38c8c93dd0c0dacc135015c496874aa507b478b645deec1264ed8262b8`;
- projected durable output manifest:
  `dbddc5b8545e25a53b2a19cf23912d2af92849f2a551aecc99c7f420f62d7c05`.

## Validation

- Source contract and byte-integrity verification: PASS.
- Python compilation and Ruff: PASS.
- Focused Round 53 tests: 9 passed.
- Adjacent historical-design, Repair-v2 decision, Supervisor, and persisted
  status tests: 43 passed.
- Full non-retired suite: 2,126 passed, 4 skipped (the four warnings are the
  existing Python 3.14 `fork()` deprecation warnings).
- Fresh merged Supervisor execution and deterministic replay: pending after
  publication.

## Integration matrix

| Link | Engineering proof | Durable mainline proof |
|---|---|---|
| Goal -> Resolver | additive task and dependencies validate | pending import |
| Resolver -> Ready Queue | preregistration becomes executable only after frozen design | pending import |
| Ready Queue -> Supervisor | capability is registered under the exact requested capability | pending merged run |
| Supervisor -> Capability | one-query snapshot and result-blind preregistration path tested | pending merged run |
| Capability -> Artifacts | six children plus execution are deterministic | pending durable registration |
| Artifacts -> Status | preregistration and next execution projections tested | pending durable projection |
| Status -> Next Task | exact historical execution task added as sole next consumer | pending Ready observation |
| Deterministic replay | registered snapshot reconstruction tested with zero requery | pending durable replay |

Final integration answer for this engineering checkpoint:

**NO — INTEGRATION_PENDING.**

The round may advance to `VALIDATED_IN_MAINLINE` only after the ready PR is
merged, a fresh Supervisor executes this exact capability once, all seven
artifacts are durably registered, status exposes the new execution task as the
sole Ready consumer, and deterministic replay succeeds without another
database query.
