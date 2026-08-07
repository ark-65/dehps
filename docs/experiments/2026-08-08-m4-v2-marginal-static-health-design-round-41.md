# M4 v2 Marginal-Static Measurement Health Design — Round 41

Date: 2026-08-08

Role: Engineering Agent

Primary goal: freeze and integrate a smaller, restartable marginal-static
measurement-health program without executing samples.

Non-goals: no sampled health run, historical outcome read, scientific result,
Evidence creation, accepted model, Prediction v2 production promotion, or
legacy-result reuse.

## Outcome

The Round-41 health-design capability is `COMPLETE` in the canonical live
mainline and its original execution is deterministically replay-verified. The
frozen future program contains 7,168 replicates in 112 independently resumable
shards of 64. The design task itself generated zero issues, replicates,
bootstrap samples, folds, or historical reads.

The first live dispatch failed closed on an artifact-type lookup before doing
any sampled work. The failure and its events were preserved. A narrowly bound
recovery reset only that task state, installed the corrected merged code, and
completed a fresh execution. No event was deleted or rewritten.

Round acceptance answer:

> **YES — validated by unified mainline execution and replay.**

This answer applies to the zero-work **health-design capability**. The separate
7,168-replicate health executor is still `INTEGRATION_PENDING` and has not run.

## Workload and throughput boundary

| Property | Legacy P2.6.1 program | Frozen M4 v2 marginal-static program |
| --- | ---: | ---: |
| Replicates | 31,000 | 7,168 |
| Outer evaluation issue predictions | 64,656,000 | 9,468,928 |
| Total generated issues | not reused | 15,920,128 |
| Execution shards | legacy layout | 112 × 64 replicates |
| Per-replicate database reads/writes | legacy path | 0 / 0 |
| CSV materialization | not reused | forbidden |
| Raw draw retention | legacy path | forbidden after state update |
| Duplicate raw replay | previously present | disabled |
| Routine physical checkpoint scan | previously present | disabled |

The replicate count is 76.9% lower (4.33× smaller), and outer evaluation work
is 85.4% lower (6.83× smaller) than the legacy P2.6.1 figures. Every replicate
has a worker-independent seed identity. Resume loads one compact completion
index, skips matching completed replicate digests directly, and keeps only the
issue count plus ordered signed `int64[33]` number-event counts in memory.

No speed or finish-time measurement exists yet for the new program because the
sampled executor is not implemented or dispatched. CPU usage is therefore
expected to fall while the Supervisor reports `WAITING_FOR_CAPABILITY`; that is
not training throttling.

## Frozen scientific boundary

- Branch: `MARGINAL_STATIC`.
- Estimator: `EXPANDING_LEGAL_MARGINAL_ALPHA_1`.
- Fixtures: one positive M1 control and three exact marginal-negative controls
  (uniform, T1, and J1).
- Scales: forward-like and historical-like sequence lengths from approved
  Research Request 318.
- Inference: 511 centered circular moving-block resamples, primary block 5,
  diagnostic blocks 3, 8, and 13.
- Acceptance: frozen positive direction, negative-control false-positive,
  Wilson-bound, bias, coverage, power, MDE-completeness, legality, and
  deterministic-replay gates.
- Runtime: single host, runtime-selected local workers, outputs independent of
  worker count and shard placement.

No threshold, seed, estimator, fixture, or inference rule was selected from a
result. No legacy P2.6.1 statistical payload was read or reused.

## Mainline lineage

The implemented and live-verified path is:

```text
Goal M4_INFORMATION_THEORY_EVIDENCE
  -> dependency resolver
  -> Ready Queue: m4-v2-marginal-static-measurement-health-design
  -> unified Research Evidence Supervisor
  -> capability m4_v2_marginal_static_measurement_health_design
  -> workload + inference + completion + execution artifacts
  -> task COMPLETE / projection VALIDATED_IN_MAINLINE
  -> Ready Queue: m4-v2-marginal-static-measurement-health-execution
```

### Integration matrix

| Contract element | Live proof |
| --- | --- |
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` |
| Ready condition | Round-40 fixture execution, four fixtures, bundle, completion, and Round-41 source contract resolved |
| Runner | Unified Research Evidence Supervisor, merged commit `ddb04f920cb2b9b9c4680ec51a4a93beecae3b88` |
| Capability | `m4_v2_marginal_static_measurement_health_design` |
| Execution | `036ccc288de6cbfa8a6fd8f3b5e637f6a66204c702dce622920af14abb6ff677` |
| Workload artifact | `ec4848874c8883b5e07b72af43a140867e1d3a7e3a865678fde5d3b5a7b1b557` |
| Inference artifact | `9edf2998c034631f45c163caf5c14c9d53805e2c125a1df24d5dd6111139baa0` |
| Completion artifact | `4fed70e9d81266ab01c9dfaa689470ac870d5f20fb44f96cfa3761d6eb071ef9` |
| Mainline execution artifact | `8404a16dd48c081e9ada61eb1a968dd0df5b3e1a05e9b6529626f4683f91c362` |
| Durable status | task `completed/COMPLETE`; status projection `VALIDATED_IN_MAINLINE` |
| Replay | `REPLAY_VERIFIED`; same execution and artifact identities; four registrations |
| Next consumer | `m4-v2-marginal-static-measurement-health-execution`, Ready but unsupported and not dispatched |

## Incident and exact recovery

The initial merged runtime at commit `2baa127…` requested artifact type
`m4_v2_marginal_static_fixture`. Round 40 had immutably registered all four
fixtures as `m4_v2_marginal_static_measurement_fixture`. The Supervisor failed
closed before materializing any design artifact or sampled work.

Immutable failed identity:

- task digest:
  `b2ae3d49de0eb1f8714d1636c4b6a3a05de2f66de99bef5bb1d4134dc85e78c4`
- execution:
  `14e0c7c93fc41406154a23de1c842d979706090b6e302b45b6551b75d3fffa04`
- started event:
  `6cd0e06ab7d75a1e00d44fac8171be0bde5d10dfafc3e5b56ceafec5678d5fca`
- failed event:
  `ea3073f7d0f696d95607843c5de60d3d2794ca5fee826efa385dcd76c38caa25`
- error: `registered artifact type is missing: m4_v2_marginal_static_fixture`
- generated issues, replicates, folds, history reads, and registered artifacts:
  all zero.

PR #275 corrected both execution and replay lookup to the immutable type and
normalizes the four fixtures into the frozen scientific order, failing closed
on missing, duplicate, or unexpected fixture IDs. Its Worker CI passed.

PR #276 added a recovery builder bound to the exact task, execution, two event
digests, error text, failed state, and absence of execution artifacts. The live
preflight verified:

- failed manifest `7bd17dfc…` -> recovered manifest `3751fafb…`;
- exactly one state change:
  `failed/INTEGRATED -> draft/INTEGRATION_PENDING`;
- zero task/event deletion, event rewrite, completed-task regression, or
  artifact rewrite;
- zero duplicate raw replay and zero physical checkpoint scan.

The new execution emitted started event `d1f70807…` and completed event
`1c6519ae…`. The original failed execution and its two events remain unchanged.

## Validation

- Focused health-design tests: 7 passed.
- Focused exact-recovery tests: 5 passed.
- M4/ResearchOS regression after recovery tooling: 538 passed, 4 skipped.
- Full Worker suite from a clean detached worktree: 2,109 passed, 4 skipped.
- PR #275 GitHub Worker CI: success in 7m20s.
- PR #276 GitHub Worker CI: success in 7m03s.
- Fresh Supervisor PID 1826889 ran merged commit `ddb04f9…` and produced
  multiple post-start heartbeats.
- Live deterministic replay: `REPLAY_VERIFIED` with identical execution and
  artifact identities.

## Current mainline and legacy state

The canonical research/training path is now M4 v2. The previous three adaptive
lines are retired from scheduling as `superseded`, not deleted:

- `legacy-adaptive-weight-search`;
- `legacy-production-candidate-generation`;
- `legacy-topk-feedback-tuning`.

Their immutable records remain available, while the final legacy baseline,
settlement record, and supervisor-stop tasks remain completed. This is a
controlled mainline switch, not a destructive data removal.

Legacy P2.6.1 is computationally settled and replayable, but its scientific
MeasurementHealth decision remains `REPAIR`; it is not a passing model and was
not overridden. Prediction v2/M4 v2 remains research and shadow decision logic,
not a production strategy promotion.

After the Round-41 design completion, the status projection reported
engineering progress 43% and evidence progress 25%. The only new Ready task is
the marginal-static sampled health executor. It requires a separate Research
contract, Engineering integration, merged code, and Operator authorization
before any of the 7,168 replicates may start.

## Next action

Integrate the sampled executor against the frozen workload and compact resume
contract. It must preserve deterministic child seeds, run without per-replicate
database/CSV operations, batch only compact summaries, skip completed replicate
digests directly, expose truthful throughput/ETA, and remain unable to read
historical outcomes or create Evidence until the synthetic health gates pass.

Sampled-executor integration answer at this checkpoint:

> **NO — INTEGRATION_PENDING.**
