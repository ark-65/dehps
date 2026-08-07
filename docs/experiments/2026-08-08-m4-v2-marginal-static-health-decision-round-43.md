# M4 v2 Marginal-Static Health Decision — Round 43

## Primary goal

Integrate the frozen Round-42 measurement-health result into the canonical Goal,
resolver, Ready Queue, Research Evidence Supervisor, immutable artifact registry,
status projection, repair consumer, and deterministic replay without repeating
the synthetic validation workload.

## Non-goals

- Do not change any health gate or threshold.
- Do not generate another synthetic replicate or issue.
- Do not read historical outcomes.
- Do not infer that the predictive model has no information.
- Do not create Evidence, open promotion, or operate production.
- Do not design or execute the repair in this Engineering round.

## Frozen input and decision

- Measurement Contract v2:
  `a0a367c99d7646cadc162bd9ceb0d5d73481cd7c26656bf02b40a99d9180095b`
- Round-42 mainline execution:
  `89cb006231ae0956e70cee67050f0be090eb87c2441b4100d8c86a6cf646233b`
- Measurement-health result:
  `40b449a7abe4ac9fff6eb0e98212f5809e0f0ff76c93f1344b673b4716905e2d`
- Health completion:
  `e77c35c68b6043875c54c1bb06d2c64a70730c026950fe7c813efcfe54d5f8d3`
- Frozen health: `REPAIR`
- Frozen decision: `REPAIR_MEASUREMENT_SYSTEM`
- Decision fact:
  `m4-v2-marginal-static-measurement-health-decision:REPAIR`
- Next consumer:
  `m4-v2-marginal-static-measurement-repair-design`

The four failed cells and their failed gates are preserved exactly. No result is
relabelled and no threshold is relaxed.

## Scientific review

The Einstein pass asks for the smallest falsifiable statement supported by the
observations. That statement is: the currently frozen marginal-static
measurement instrument failed its own health contract in four cells and must be
repaired before historical measurement. It is not a statement that the target
model contains no predictive information.

The Gauss pass confirms exact lineage, unique decision mapping, complete/finite
cells, legal samples, zero historical reads, and preservation of the failed-gate
topology. The Riemann pass identifies the structural boundary: the failure is in
the measurement representation across short-window/local-effect cells, so a
separate repair design is required. Their smallest shared conclusion is
`REPAIR_MEASUREMENT_SYSTEM`; same-seed tuning and post-hoc threshold changes are
forbidden.

## Implementation

- Added the immutable, result-aware Round-43 source contract.
- Added the health-decision builder with exact parent-digest and failed-topology
  checks.
- Added the canonical Supervisor capability and immutable decision artifact.
- Added deterministic decision-only replay.
- Added the additive manifest migration and the repair-design DAG node.
- Added unified status projection for the decision and its repair consumer.
- Added focused tests for mapping, source integrity, capability execution,
  decision-only replay, migration preservation, and status projection.

The decision path explicitly records:

- `generated_issues = 0`
- `compact_index_reads = 0`
- `sentinel_replicates_recomputed = 0`
- `duplicate_validation = false`
- `historical_outcomes_read = false`
- `evidence_created = false`
- `promotion_gate_opened = false`
- `production_action = none`

## Validation

- Ruff and Python compilation: passed.
- Focused Round-43 tests: 6 passed.
- Related manifest/design/execution/decision tests: 54 passed.
- Source-partition and related tests after registering the new module: 55 passed.
- Full non-legacy-retirement worker suite: 2,046 passed, 4 skipped. The unfiltered
  local suite had the same 42 durable Prediction-v2-retirement failures already
  documented in Round 42; those tests deliberately attempt retired legacy-line
  computation and are blocked by the active local cutover artifact.
- Exact live-artifact decision preflight: produced deterministic artifact
  `cb653dc02739958814b0e4b349e163bd10f9256a19c05f61dbc1808fe6948d50`
  with four failed cells and zero duplicate validation.
- Additive migration dry run against the Round-42 live manifest: `VERIFIED`;
  one revised task, one new task, zero task deletion, zero state regression,
  zero fact deletion, and zero unallowlisted rewrite.

## Integration matrix

| Link | Engineering status |
| --- | --- |
| Goal | Bound to `M4_INFORMATION_THEORY_EVIDENCE` |
| Resolver | Decision and repair-design dependencies declared |
| Ready Queue | Exact five parent digests and source fact declared |
| Supervisor | Health-decision capability registered |
| Capability | Frozen `REPAIR` mapping implemented |
| Artifacts | Decision and mainline execution schemas implemented |
| Status | Decision and repair-design projections implemented |
| Next Task | Repair design declared; historical route remains closed |
| Replay | Decision-only deterministic replay implemented |

## Acceptance state

`NO — INTEGRATION_PENDING` at Engineering handoff. The code must merge, then the
additive migration, canonical Supervisor execution, artifact registration,
status projection, and deterministic replay must succeed on the merged commit.
