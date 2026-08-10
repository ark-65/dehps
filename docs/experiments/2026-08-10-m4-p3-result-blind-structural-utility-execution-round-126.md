# M4-P3 Result-Blind Structural Utility Execution — Round 126

Date: 2026-08-10

Role: Engineering Agent

Engineering Request: 458

Engineering Execution: 379

Research Request: 457

Research Execution: 378

## Primary goal

Implement the separately authorized result-blind generator and 90-fold
walk-forward capability for M4-P3. The capability compares three equal-budget
100-ticket portfolios using portfolio-internal structural coordinates only:

- uniform random sampling without replacement, with 32 deterministic
  replicates per fold;
- the frozen legacy structural Top-100 selector;
- the frozen Prediction v2 structural selector.

## Explicit non-goals

- no winning number, payout, reward, outcome rank, or prediction label is read;
- no bootstrap, Holm adjustment, Evidence, or route decision is produced;
- no old training line is restarted;
- Prediction v2 remains `SHADOW_ONLY / BASELINE_ONLY`;
- no model, feature family, selector, threshold, or estimand is changed;
- no durable manifest import or canonical 90-fold execution occurs under the
  Engineering role.

## Frozen research binding

The implementation validates the completed Research Request 457 / Execution
378 contract digest
`a4167973da82dcdf212dd22ad5e8cf30f4ecf5cbd2ba8c2751a89dd04a4d4660`.
Its executable source contract is
`8f123b06647d509000f0e4e291087438b3009f6c1ec3e5cab327600c3bca14f6`.

The target sequence remains exactly `2026002` through `2026091`. Every fold
loads history only through `target_issue - 1`, requires at least 900 prior
rows, builds the same complete `C(33, 6) = 1,107,568` candidate ABI, and gives
both non-random selectors the identical frozen Top-10,000 scored pool.

## Implementation

The new structural-utility execution module provides:

- zero-based legal candidate sampling with a SHA-256 counter stream and
  rejection-unbiased bounded draws;
- exact 100-ticket validation before metric computation;
- integer sufficient statistics for pair/triple coverage, high-overlap
  collisions, pair entropy, largest similarity component, and family HHI;
- 90 prior-only fold artifacts, one result index, and one completion artifact;
- deterministic registered-artifact replay without rerunning scoring;
- digest-verified resume of complete fold artifacts;
- 18 immutable local checkpoints, one after every five completed folds.

The canonical Research Evidence Supervisor now owns execution, persistence,
registration, status projection, and replay. A completed capability registers
exactly 92 capability children plus its mainline execution artifact. The next
consumer is the separately authorized Evidence Compiler task; it remains
unimplemented and dependency-blocked.

## Migration dry run

The additive migration was evaluated against the current durable control plane
without importing it. Dry-run digest:
`b68909407600da7fa2c31c28917c3900c0d813cbc3f1276ccb3de2855af2896a`.

Observed boundary:

- 0 goal additions;
- 1 task addition: the inactive Evidence Compiler placeholder;
- 1 revised task: the blind generator and walk-forward task;
- 1 source fact and 1 research-approval event added;
- 0 task or goal deletions;
- 0 existing-state regressions;
- 0 fact deletions;
- 0 unallowlisted definition rewrites;
- `production_action = none` and `promotion_gate_opened = false`.

The tracked source manifest digest is
`86847be6f03486b7420e3daa24f286d20d7e872c4901260f6eb3f502b0df0ffe`.

## Validation

```text
ruff check (execution module, supervisor, execution tests): PASS

pytest -q
  test_research_os_mainline_supervisor.py
  test_m4_p3_result_blind_structural_utility_execution.py
  test_m4_p3_result_blind_structural_utility_preregistration.py

36 passed in 78.22s

Full worker validation in a temporary repository copy without the pre-existing
`runtime/prediction-v2/legacy-retirement-activation.json`:

2398 passed, 4 skipped, followed by the corrected source-partition test:
1 passed. Effective clean-runtime result: 2399 passed, 4 skipped.
```

The focused suite proves the deterministic random golden vector, complete
candidate ABI boundary, prior-only fold rejection, portfolio metric identities,
90-fold result-index replay, source-byte pinning, mainline child-registration
count, status projection, complete-fold resume without history reload, and the
5-fold checkpoint cadence.

The first full run in the live workspace reported 42 unrelated failures after
the seven newly exposed historical-fixture assertions were corrected. Those 42
all exercise retired legacy prediction/training paths and were caused by the
existing Operator activation artifact. It was preserved unchanged. The clean
temporary-copy run confirms the tracked source independently of that runtime
state.

## Mainline integration matrix

| Link | Round-126 state | Proof |
|---|---|---|
| Goal | Declared | `M4_P3_RESULT_BLIND_STRUCTURAL_UTILITY` |
| Resolver | Code complete | task dependencies and exact six input digests |
| Ready Queue | Not durably activated | additive migration is dry-run only |
| Supervisor | Code complete | canonical capability and replay registered |
| Capability | `CODE_COMPLETE` | 36-test validation; no canonical live run |
| Artifacts | Contract complete | 90 folds + index + completion defined |
| Status | Code complete | execution counts and blind boundary projected |
| Next task | Declared | separately authorized Evidence Compiler |
| Deterministic replay | Code complete | registered artifact reconstruction tested |

Integration answer:

`NO — INTEGRATION_PENDING`

Round 126 is not permitted to claim capability completion. A separately
approved Operator execution must import the exact committed migration, dispatch
the fresh Supervisor, complete all 90 folds, register the artifacts and fact,
and replay them. Only after that proof may the Evidence Compiler receive its
own Research contract.

## Round 127 live execution and fail-closed status finding

Merged commit `d2eb199f76458ea2b27e2d606aa4d9ef107a1727` completed the
canonical workload as execution `df9c1cca8252f6cec16ca9740ec051f5c6dbb5df19eb6d363f2b4070c79b1619`.
It produced 90 folds, 18 checkpoints and 93 registrations; registered-artifact
replay returned `REPLAY_VERIFIED` with no workload rerun and zero target-row or
bootstrap reads.

Operator Request 459 / Execution 380 nevertheless failed closed because the
unified status projection selected the earlier preregistration summary. The
completed task and completion fact were visible, but `execution_artifact_digest`,
`folds_executed` and `portfolios_generated` remained null/zero. All completed
artifacts, events and registrations are preserved. Engineering Runtime Fix
Request 460 / Execution 381 is limited to adding the completed blind-execution
task to the existing latest-summary precedence and artifact-loading boundaries;
it may not rerun the capability or change scientific behavior.

The Round-128 regression suite passed 30 tests. A read-only durable projection
with the corrected selector now reports execution artifact `df1dd942...`, 90
folds, 3,060 portfolios, zero target-row reads, execution integration `YES`,
and the Evidence Compiler as next consumer. The Goal-level answer correctly
remains `NO — INTEGRATION_PENDING` because inference and route selection have
not run.

## Round 130 research freeze and Round 131 Evidence Compiler engineering

Research Request 462 / Execution 383 froze the Evidence Compiler before any
structural-result read or decision work. The contract digest is
`888881ea69e660c3c6ff62b5f7d9849b3fa79fcc23db22582e2fa8a8df8a8a32`.
The Einstein diagnostic constraint reduced the inference claim to a transparent
same-budget null comparison: six frozen coordinates against both the random
and legacy controls, with no predictive or payout interpretation.

Engineering Request 463 / Execution 384 implements that frozen contract only:

- one shared 20,000-resample circular moving-block bootstrap index family,
  with block length 5 and 18 starts per resample, is used across all 12 series;
- SHA-256 counter-stream sampling, stable hypothesis ordering, Holm step-down
  adjustment, exact frozen order-statistic indexing, basic one-sided lower
  bounds, and 60-of-90 stability gates are deterministic;
- the route is scalar and all-gate: partial coordinate support cannot produce
  a supported route;
- a supported result permits candidate-portfolio-optimizer research only; a
  failed result stops the lottery structural-optimization route while retaining
  the Research OS, measurement, and replay infrastructure;
- Prediction v2 remains `SHADOW_ONLY / BASELINE_ONLY`, old training remains
  `FROZEN`, and no promotion, predictive probability, payout, or production
  action is authorized.

The canonical Supervisor consumes only the registered result index and
blind-execution completion with their exact frozen digests. It persists and
registers four capability children—bootstrap family, Evidence, route decision,
and completion—plus the immutable mainline execution. Replay re-runs the frozen
bootstrap compiler from the registered result index and requires exact artifact
identity. Separate status-summary inputs preserve the earlier 90-fold execution
projection after the compiler becomes the latest completed task.

The additive source migration changes exactly one existing task, adds one source
fact and the approved Research event, and makes no goal/task additions or
deletions. Dry-run digest:
`61365ce20f9e0228cae166dfe5f348e91c7bacbe36486386e8e5abc1b0d07a06`.
Tracked source manifest digest:
`a3aeacf15146fd0c55098eb3306e60ef1aa0e40d160a181ad1306b2b9744c5a6`.
The same migration evaluated against the current durable control plane produced
dry-run digest
`13d8b79e41400a2a0730b4b78e665a7cdd8e6e8e0b0bbf3acf1fb1826ec0704c`
and output manifest digest
`04137035bcecc1abdc9268661e9bcf10b6231d430b2ea5d860ba8c4acda32854`;
the resolver returned `ready / dependencies_satisfied` for the Evidence
Compiler. No import was performed under the Engineering role.

Round-131 code validation initially passed six new focused tests covering the
source and Research contracts, shared circular blocks, supported and failed
all-gate routes, deterministic compiler replay, Ready Queue resolution, and
status persistence. The broader M4-P3 focused suite exposed one historical
assertion that still expected the Evidence Compiler placeholder to be
unimplemented; that assertion was updated to the newly authorized capability
and dependency-wait state. No scientific logic changed.

### Round-131 integration matrix

| Link | Engineering state | Proof |
|---|---|---|
| Goal | Declared | `M4_P3_RESULT_BLIND_STRUCTURAL_UTILITY` |
| Resolver | Code complete | one revised task, exact six input digests |
| Ready Queue | Fixture validated | approved contract + completed parent resolves ready |
| Supervisor | Code complete | canonical compile, persistence, registration, replay |
| Capability | `CODE_COMPLETE` | frozen joint bootstrap and all-gate decision |
| Artifacts | Contract complete | four children + one mainline execution |
| Status | Code complete | execution and compiler summaries projected separately |
| Decision consumer | Declared | terminal structural route record |
| Deterministic replay | Code complete | 20,000-resample recompilation and identity check |

Integration answer at Engineering handoff:

`NO — INTEGRATION_PENDING`

The Evidence Compiler has not yet read the real registered result index or
produced a durable route. A separately authorized Operator run must import the
exact merged migration, dispatch this single Ready task, register all five
artifacts, project the route, and verify replay before the M4-P3 Goal may answer
`YES — validated by unified mainline execution and replay`.
