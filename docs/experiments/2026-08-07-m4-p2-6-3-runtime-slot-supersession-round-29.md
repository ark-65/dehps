# M4-P2.6.3 Runtime-Slot Supersession — Round 29

Date: 2026-08-07

Role: Engineering Agent

Agent Request: `engineering-m4-p263-runtime-slot-supersession-round-29-20260807`

Request / execution: `297 / 218`

## Primary goal

Replace the permanently unreachable P2.6.1 terminal-completion premise with a
result-blind P2.6.3 runtime-slot eligibility task, a post-stop Operator guard,
and an additive one-event migration. This releases the canonical Supervisor
runtime resource without pretending that frozen-incomplete P2.6.1 completed.

## Non-goals

- No model, probe, feature, estimator, fold, seed, resampling, threshold, Gate,
  Evidence, or research-conclusion change.
- No P2.6.1 completion synthesis, result/checkpoint reuse, or historical result
  payload read.
- No modification of completed compatibility, golden, runtime-audit execution,
  or immutable Runtime Audit v1.1.6/v1.1.7 contents.
- No live service stop, event publication, Prediction v2 promotion, or P3
  execution in this Engineering round.

## Replaced premise

The legacy terminal guard releases `m4-runtime-slot:p2-6-1-released` only after
one unique completed P2.6.1 execution. P2.6.1 is now deliberately frozen
incomplete and P2.6.3 is its accepted superseding measurement execution, so the
old predicate cannot become true. Reusing it would leave Measurement v2 in a
permanent external wait; fabricating P2.6.1 completion would corrupt the
immutable execution history.

The new eligibility predicate consumes only frozen identities and durable
mainline metadata:

- exact P2.6.1 and P2.6.3 fixture identities;
- unique completed P2.6.3 compatibility, golden, and arithmetic-correct
  runtime-audit task identities;
- exact started/completed event metadata and registered artifact contracts;
- the immutable superseded identity of the failed first Runtime Audit attempt;
- the absence of a downstream design/replay/preflight/P3 dispatch before the
  eligibility execution began.

It reads no statistical result payload and produces zero Evidence progress.

## Source and replay boundary

Runtime Audit v1.1.6 and v1.1.7 are now validated as historical, digest-pinned
embedded source partitions. New source files no longer reinterpret their
frozen allowlists against the current repository tree.

The new gate has a separate immutable source contract,
`m4-p263-runtime-slot-governance-source-contract-v1.json`. It pins the eight
implementation and operational-entrypoint files used by eligibility, replay,
status projection, post-stop verification, and one-event migration. The
eligibility artifact records both the contract digest and source-set digest in
its basis and parent lineage.

Replay verifies the same task definitions, completion execution ids, event
digests, registration digests, artifact contracts, failed-attempt
supersession, and eligibility execution identity. Recomputed artifact digests
cannot enable result reads, Evidence, or promotion.

## Operator boundary

The Engineering capability may only produce an
`ELIGIBLE_AFTER_OPERATOR_STOP` artifact. A separately approved Operator must:

1. stop `dehps-research-evidence-supervisor.service`;
2. verify `ActiveState=inactive`, an empty worker cgroup, and no downstream
   started event;
3. create a `SAFE_TO_RELEASE_SLOT` guard bound to the exact registered
   eligibility artifact;
4. build and review a migration whose only live-state change is adding
   `m4-runtime-slot:p2-6-1-released`;
5. import the verified manifest and restart the merged Supervisor.

The migration additionally proves that the eligibility task digest and unique
completion execution match the eligibility artifact, and that the resulting
Ready Queue contains only `m4-v2-measurement-contract-design`.

## Validation

Focused validation:

```text
92 passed in 3.80s
Ruff: passed
Python compile: passed
governance source contract: 8/8 source hashes verified
```

The focused set covers the new eligibility/replay/guard/migration tests,
historical Runtime Audit source contracts, Measurement v2 status persistence,
control-plane validation, and P2.6.3 compatibility.

Full Worker validation ran from detached commit `205e800` in an isolated clean
worktree, so the ignored live Prediction v2 activation state in the shared
operator worktree could not alter legacy-retirement test assumptions:

```text
2055 passed, 4 skipped, 4 warnings in 224.12s
```

The warnings are the existing Python 3.14 multiprocessing `fork()` deprecation
warnings in training-supervisor parallelism tests. There are no test failures.

## Mainline integration matrix

| Required link | Current evidence | Status |
| --- | --- | --- |
| Goal | canonical M4 Runtime Audit Goal | source bound |
| Resolver | eligibility dependencies and result-blind wait boundary tested | source complete |
| Ready Queue | eligibility precedes the external slot event; post-event queue is design only | source complete |
| Supervisor | eligibility capability registered | source complete |
| Capability | metadata-only eligibility and source contract verified | source complete |
| Artifacts | eligibility, execution, replay, guard, and migration contracts | source complete |
| Status | runtime-slot eligibility and Operator-pending states projected | source complete |
| Next Task | Measurement v2 design after one authorized external event | declared |
| Deterministic replay | immutable metadata replay tests pass | live execution pending |

Final integration answer:

**NO — INTEGRATION_PENDING**

The capability must be merged, additively imported, executed by the unified
Supervisor, replayed from registered metadata, and then consumed by the
authorized Operator boundary before it can be `VALIDATED_IN_MAINLINE` or
`COMPLETE`.
