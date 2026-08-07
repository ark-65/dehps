# M4 Measurement v2 Single Raw Validation — Round 32

Date: 2026-08-07

Role: Engineering Agent

Agent Request: `engineering-m4-v2-remove-duplicate-raw-replay-round-32-20260807`

Request / execution: `300 / 221`

## Primary goal

Remove the duplicate 31,000-replicate completion assembly from the Measurement
v2 raw source-binding step while retaining one canonical immutable
execution/event/registration-content validation and the downstream P2.7
deterministic gate replay.

## Non-goals

- No estimator, probe, feature, fold, seed, threshold, Gate decision mapping, or
  research conclusion change.
- No synthetic statistic, partial result, historical outcome, or Prediction v2
  promotion read or write.
- No P2.6.1 completion synthesis and no reuse or mutation of its incomplete
  runtime artifacts.
- No deletion or rewrite of the failed raw-replay execution event.
- No P3 execution.

## Incident and root cause

After the authorized P2.6.3 runtime-slot release, the unified Supervisor
completed Measurement v2 design and its physical replay. The next task,
`m4-v2-p2-6-1-raw-execution-replay`, failed with:

```text
measurement_validation_update_policy_mismatch:
replicate update policy does not match its task execution
```

The raw step first loaded the canonical completed measurement parent through
`_load_single_completed_execution`, which validates the execution, completed
event, all 31,035 registrations, canonical paths, registered digests, and stored
artifact content. It then called `verify_completion_replay`, which re-read and
reassembled all 31,000 replicates a second time. That second call omitted the
P2.6.3 periodic-refit policy digest and compared every P2.6.3 replicate against
`None`.

The same stale path also expected the frozen-incomplete P2.6.1 execution to have
a completion artifact, despite the already accepted relationship that P2.6.3
supersedes P2.6.1 for future measurement execution.

## Change

1. The raw source-binding call shape now validates the already registered
   completion identity in constant-size work and does not call replicate
   assembly. P2.7 remains the single downstream deterministic statistical gate
   replay.
2. The lightweight raw and Gate replay artifacts bind to the exact frozen
   P2.6.3 task, execution, execution artifact, completion artifact, and
   periodic-refit policy identities. P2.6.1 remains an immutable incomplete
   compatibility boundary; no completion is fabricated.
3. Marginal binding accepts only that exact P2.6.3 superseding identity while
   preserving the frozen result-blind decision mapping.
4. A fail-closed recovery builder verifies the exact failed task, execution,
   started event, failed event, and error before changing only its projected
   state from `failed/INTEGRATED` to `draft/INTEGRATION_PENDING`. Immutable
   events are preserved.

## Live read-only performance proof

Against the canonical local runtime:

```text
registered artifacts verified once: 31,035
canonical registry/content validation: 8.727 s
lightweight completion identity:       0.010 s
raw superseding binding:                0.003 s
bound execution: 7de420e96e495f357a75860249cf1529a0d14a8d272177cacb0eb6f04b556c0d
```

The removed layer was the second full 31,000-replicate reassembly. The retained
8.7-second pass is the single immutable registration/content boundary.

## Recovery dry-run

The live failed manifest produced:

```text
status: SAFE_TO_RECOVER
input manifest:  963a90eba7fe6e3e198cbf5b1e5825ea42f019bdc89077d7d0d9d72923ac52f5
output manifest: 46fd1eb3880dd3292ab7426625c874566d7d6563d25c8bc3cf70a04d6db5acd3
changed tasks: 1
deleted events: 0
rewritten events: 0
completed-task regressions: 0
statistical result payloads read: false
Prediction v2 promotion: false
P3 execution: false
```

## Validation

Focused source-binding, recovery, M4 hardening, and no-duplicate-assembly tests:

```text
69 passed
Ruff: passed
Python compile: passed
```

Broader measurement executor, unified Supervisor, and M4 hardening validation:

```text
117 passed in 97.05s
```

Full Worker validation from detached commit `9156e5e` in a clean worktree with
the isolated source root explicitly bound into `PYTHONPATH`:

```text
2058 passed, 4 skipped, 4 warnings in 211.73s
```

The warnings are the existing Python 3.14 multiprocessing `fork()` deprecation
warnings in training-supervisor parallelism tests.

The focused tests include exact P2.6.3 raw/Gate binding, tamper failure, marginal
decision mapping, immutable recovery history, Measurement v2 design/replay, and
the assertion that raw binding cannot call replicate assembly.

## Mainline integration matrix

| Required link | Current evidence | Status |
| --- | --- | --- |
| Goal | M4 Information Theory Evidence | bound |
| Resolver | exact failed-task recovery manifest built | source complete |
| Ready Queue | recovery changes only raw replay to draft | dry-run verified |
| Supervisor | existing raw/Gate/marginal capabilities retained | source complete |
| Capability | duplicate assembly removed; exact P2.6.3 binding added | source complete |
| Artifacts | lightweight raw/Gate artifacts and recovery report | source complete |
| Status | failed incident preserved; recovery state declared | source complete |
| Next Task | P2.7 replay, marginal binding, marginal decision replay | declared |
| Deterministic replay | focused tests pass | merged live replay pending |

Final integration answer:

**NO — INTEGRATION_PENDING**

The fix must be merged, the exact recovery manifest imported by an approved
Operator, and the recovered raw/Gate/marginal chain completed and replayed by
the unified mainline before this round is `COMPLETE`.
