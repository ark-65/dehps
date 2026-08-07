# M4 P2.6.3 Round 21 shared-runtime namespace recovery

Date: 2026-08-07

Role: Engineering Agent

Agent Request:
`engineering-m4-p2-6-3-shared-runtime-namespace-fix-round-21-20260807`
(request 287, execution 208)

## Primary goal

Allow the unified Research Evidence Supervisor to consume the completed P2.6.3
execution from the intentionally bound same-host canonical runtime root without
weakening control-plane, task, execution, or artifact confinement.

## Non-goals

- no change to the 31,000-replicate workload, seeds, scenarios, probes,
  features, refit interval, resampling, thresholds, Gate, or Evidence rules;
- no statistical-result inspection or research conclusion;
- no mutation, deletion, recomputation, or identity rewrite of completed P2.6.3
  runtime artifacts;
- no attempt to classify the superseded P2.6.1 partial executions as complete.

## Incident evidence

P2.6.3 execution
`7de420e96e495f357a75860249cf1529a0d14a8d272177cacb0eb6f04b556c0d`
completed all 31,000 formal replicates with zero failures, retries, or reused
results. It materialized 31 cell aggregates, its MDE artifact, its completion
artifact, and a `VALIDATED_IN_MAINLINE` execution artifact.

The next Supervisor heartbeat failed before downstream dispatch with:

```text
mainline artifact path escaped task namespace
```

The clean runtime worktree binds its top-level `runtime` entry to the canonical
same-host runtime root. `_canonical_task_artifact_path` constructed a logical
namespace below that entry, resolved it, and required the resolved and logical
paths to be identical. Expanding the authorized top-level symlink therefore
looked like an escape even though the registered artifact remained inside the
real task execution root.

## Implementation

The resolver now expands the top-level runtime binding first. It constructs the
control-plane namespace, task root, and execution root below that real runtime
path, then performs the existing real-path equality and containment checks.

The accepted boundary is deliberately narrow:

- a top-level runtime binding may resolve to the canonical runtime root;
- a symlink below that root may not replace the control-plane namespace;
- a task or execution root may not resolve elsewhere;
- a registered artifact must resolve below the exact real execution root;
- non-canonical relative paths, `..`, absolute paths, unknown control planes,
  namespace mismatches, and execution mismatches remain rejected.

## Validation

```text
pytest test_prediction_v2_shadow.py -k canonical_task_artifact_path
2 passed

pytest test_research_os_mainline_supervisor.py test_prediction_v2_shadow.py
38 passed

real P2.6.3 worktree/runtime reproducer
PASS: resolved to the canonical execution.json

ruff (UP017 pre-existing rule excluded for the touched legacy Supervisor)
PASS

black --check
PASS

git diff --check
PASS
```

The new regression also places an artifact symlink inside the accepted bound
runtime execution root and proves that the resolver still rejects it.

No statistical result payload was read during diagnosis or validation.

## P2.6.1 completion audit

P2.6.1 is not complete and must not be reported as such:

| Execution | Persisted operational status | Completed | Formal completion |
|---|---|---:|---|
| `8e1c6012...` | stale `RUNNING` coordinator | 13,223 / 31,000 | absent |
| `cd64aacc...` | stale `RUNNING` coordinator | 13,983 / 31,000 | absent |

Neither execution has a final mainline `execution.json` or completion artifact.
P2.6.1 was superseded by P2.6.3. P2.6.3 preserves the formal workload and
scientific contracts while using the separately preregistered fixed-64 update
policy; it is the capability that completed all 31,000 replicates.

## Mainline integration matrix

| Requirement | Round 21 status |
|---|---|
| Goal and authorized Engineering request | PASS — request 287 / execution 208 |
| Reproducer and root cause | PASS |
| Code and regression tests | PASS |
| P2.6.3 immutable 31,000 artifacts retained | PASS |
| Accepted PR merged to `main` | PENDING |
| Fresh clean-worktree Supervisor | PENDING |
| Completed P2.6.3 parent consumed | PENDING |
| P2.7 downstream task completed | PENDING |
| Deterministic replay proof | PENDING |
| Final status projection | PENDING |

Current completion answer:

```text
NO — INTEGRATION_PENDING
```
