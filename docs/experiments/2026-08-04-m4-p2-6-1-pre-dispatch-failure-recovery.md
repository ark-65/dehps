# M4 P2.6.1 Pre-dispatch Failure Recovery

Date: 2026-08-04

Role: Engineering Agent

Primary goal: preserve the immutable incident and restore the same frozen P2.6.1 execution through the unified Supervisor

Non-goals: statistical changes, estimator changes, workload changes, new execution identity, result inspection, or production strategy action

## Incident

Operator execution 175 attempted to move the accepted P2.6.1 runtime from 16 to 20 workers. The first detached `e60452d` service start occurred before the detached worktree's `runtime` path was linked to the preserved canonical runtime directory.

The database still projected the task as `RUNNING`, so the unified Supervisor selected the existing task and entered the capability. Before `run_parallel_execution` or any worker dispatch, repaired-truth discovery failed because the detached root could not see upstream runtime artifacts. The generic failure boundary then immutably recorded:

- task: `m4-p2-false-positive-and-power-runs`
- task digest: `80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa`
- execution: `cd64aacc48c5e1dac4f84d7f644e92384b50f37299b1643631b7ee872ab452b3`
- failed event: `c003525e63c6570f74dbde06c2cb8ed67e79886829c7a4be52f13f2bede9544e`
- error class: `repaired_measurement_validation_truth_missing`

No second execution was created. No partial statistical result was read. The service was stopped after diagnosis.

## Recovery contract

The failed event is not deleted, edited, hidden, or relabeled. Recovery is fail-closed and is available only when all of the following hold:

1. The exact frozen task digest, execution id, running-manifest digest, capability, failed-event digest, event sequence, original execution commit, and error payload match the recorded incident.
2. `DEHPS_P26_RECOVER_FAILED_EVENT_DIGEST` equals the exact failed-event digest.
3. The incident report is inside the runtime repository and is content-hashed into a new immutable recovery artifact.
4. All twelve repaired truths validate and the preserved coordinator, checkpoint-journal root, and replicate root exist.
5. No unregistered `execution.json` completion marker exists and no completed event is present.

After preflight, the existing task is projected back to the same canonical `RUNNING` manifest. No second `started` event is written. A later recovered terminal event uses sequence 2, preserving the sequence-1 failed event permanently.

The result-blind terminal guard recognizes only this exact failed-event digest as recovered history. Every unknown failed event remains a governance incident.

## Validation

Focused validation covers:

- exact-token same-execution recovery;
- wrong-token rejection;
- immutable recovery-artifact replay;
- preserved `started -> failed -> completed` history with terminal sequence 2;
- ordinary failed-event rejection;
- recovered terminal-guard waiting and stop-required states;
- existing completed-event crash recovery and manifest-provenance behavior.

The full Worker suite must pass before merge. Production recovery is a separate approved Operator action and is not authorized by this Engineering round.

## Integration matrix

| Mainline stage | Engineering status | Required proof |
| --- | --- | --- |
| Goal | Bound to P2.6.1 same-execution recovery | This report and Agent Request 176 |
| Resolver | Code complete | Exact failed task can be selected only with the pinned token |
| Ready Queue | Code complete | Ordinary failed tasks remain terminal |
| Supervisor | Code complete | Preflight, immutable recovery receipt, sequence-2 terminal event |
| Capability | Unchanged | Same P2.6.1 scientific runner and checkpoint directory |
| Artifacts | Code complete | Failed event preserved; recovery receipt added |
| Status | Code complete | Exact failed state returns to the original running manifest |
| Next task | Pending | Requires green CI and a separate live Operator recovery |
| Deterministic replay | Pending live execution | Existing P2.6.1 replay remains the completion gate |

## Final integration answer

**NO — INTEGRATION_PENDING.** Engineering recovery code is not completion. The capability becomes validated only after green full CI, merged source, a separately authorized unified-mainline recovery of the same execution, fresh durable checkpoint completions, and later deterministic replay.
