# M4-P2.6.3 Superseding Compatibility — Round 24

Date: 2026-08-07

Role: Engineering Agent

Agent Request: `engineering-m4-p263-superseding-compatibility-round-24-20260807`

Request / execution: `292 / 213`

## Primary goal

Preserve the immutable P2.6.1 source identity while declaring P2.6.3 as a
separate superseding measurement implementation, prove that both source
manifests are independently replayable, and add the compatibility acceptance
as the only predecessor of Measurement v2 design.

## Non-goals

- Do not rewrite the P2.6.1 historical identity or incomplete runtime state.
- Do not reuse or mix P2.6.1 checkpoints or results with P2.6.3.
- Do not supersede the P2.9 runtime-audit source plan in this round.
- Do not create research Evidence or promote Prediction v2.
- Do not switch the production mainline.

## Frozen identity matrix

| Boundary | P2.6.1 frozen baseline | P2.6.3 superseding implementation |
| --- | --- | --- |
| Source commit | `5714688cf50545fd125f4dc8422ac7e5f0bfec1f` | `947c7b4d8c040fa0d7351a2bf6859c33fa428411` |
| Manifest digest | `b1f72ebe01daf38c39724f2b6b2beaa1e0be391974e708ba1be65e8cf12ae3be` | `39435df4057f0df747f2b56c48282d6fc4ad9a266fbb8f31262e3984ece712ba` |
| Task digest | `80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa` | `85a08402a4a0c37f75ee1675f4970ef00a7a0b0992b4204251c0c2cc79324de4` |
| Capability | `m4_p2_6_1_false_positive_and_power` | `m4_p2_6_3_periodic_refit_false_positive_and_power` |
| Formal runtime | incomplete, two stale executions retained | complete, immutable 31,000-replicate execution |
| Historical Evidence | `NOT_RUN` | `NOT_RUN` |
| Result reuse | forbidden | no P2.6.1 result or checkpoint reused |

The source task key is historically reused, but the task identity is not. The
P2.6.1 manifest therefore remains addressable through its frozen fixture; it
is not rebound to the current mutable manifest path.

## Artifacts and replay

- Compatibility Request:
  `42d9583d2b333e171b99dfde27732b687e2deec2359a423d20d5d295103d1cec`
- P2.6.1 fixture:
  `f9716c799e1e55e58585c7e9acf0730f9d05111ab6e375cfb9bea85ecbdeacc5`
- P2.6.3 fixture:
  `53f9a4b7d92944dfd6a46d317b018bdc6b434fc69bb977d72ae6d1f177e0c73b`
- P2.6.1 deterministic source replay:
  `8a8f76a9df75feed30a8d7edbabd3ab572bfaba406f57e090223bf2f8a343a2f`
- P2.6.3 deterministic source replay:
  `466e27854724e1a19b73287af32c9234794442e3f3fb1f4bb7885752c43fd592`

The replay reads each manifest directly from its frozen Git commit, verifies
the raw-byte SHA-256, parses the canonical Control Plane manifest, and binds
the exact task digest and capability. It reads no score, prediction, ranking,
power, false-positive, bias, RMSE, coverage, or MDE result.

## Canonical mainline path

```text
M4 Goal
  -> Resolver
  -> m4-p2-6-3-superseding-compatibility-acceptance
  -> Ready Queue
  -> Research Evidence Supervisor
  -> P2.6.1 source replay + P2.6.3 source replay
  -> MeasurementCompatibilityAcceptanceArtifact
  -> unified_m4_status.measurement_system_v2.compatibility
  -> m4-v2-measurement-contract-design
```

The capability creates three immutable child artifacts plus one canonical
mainline execution artifact. Its completion fact is
`m4-p2-6-3-compatibility:VERIFIED`. Engineering and Evidence progress are not
incremented by compatibility attestations; Prediction v2 promotion remains
forbidden.

## Validation

Passed:

```text
40 passed in 1.51s
```

Coverage includes fixture/request identity checks, recomputed-digest tamper
rejection, both historical source replays, canonical Supervisor artifact
materialization, artifact-index replayability, DAG readiness, status
projection, and P2.6.1/P2.6.3 separation.

The original failing subset improved from `13 failed / 95 passed` to:

```text
10 failed / 98 passed
```

The remaining ten failures all belong to the deliberately unchanged P2.9
runtime-audit v1.1.5 source plan and its Round-6 sparse-tree compatibility
fixture. That plan still describes the prior source partition and must be
superseded by a new Runtime Audit artifact; changing its hashes in place would
violate the frozen contract.

## Mainline integration matrix

| Required link | Source implementation | Live mainline proof |
| --- | --- | --- |
| Goal | declared | existing live M4 Goal |
| Resolver | declared and unit-verified | import pending |
| Ready Queue | dependency behavior unit-verified | import pending |
| Supervisor | capability registered and exercised | execution pending |
| Capability | dual replay and acceptance pass | execution pending |
| Artifacts | four immutable artifacts materialize in test | registration pending |
| Status | compatibility projection unit-verified | live projection pending |
| Next Task | Measurement v2 design depends on verified compatibility | live dependency pending |
| Deterministic replay | exact source replay digests verified | post-import replay pending |

Final integration answer:

**NO — INTEGRATION_PENDING**

The next authorized round must supersede the P2.9 runtime-audit plan, audit
the complete P2.6.3 source partition and strict-prior periodic-refit chronology,
restore full CI, then import and execute this compatibility task through the
unified mainline.
