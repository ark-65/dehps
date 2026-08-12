# M4-v2 Mainline Canonical Fields and Additive Recovery

## Primary goal

Make the already frozen M4-v2 eleven-task route consumable by the canonical
mainline contract without changing science: replace the two legacy integration
field names, preserve the failed Marginal identity execution, and introduce one
new immutable recovery task key.

## Authorized change

- The failed task `m4-v2-marginal-static-historical-identity-adoption` remains
  immutable and queryable with its original definition, execution, and
  started/failed events.
- The active definition uses
  `m4-v2-marginal-static-historical-identity-adoption-recovery-v1` and retains
  the original capability, dependencies, registration order, and terminal fact.
- The remaining ten active tasks are same-key additive revisions.
- All eleven active definitions use only `downstream_consumer` and
  `evidence_progress_rule`; `next_consumer` and `evidence_rule` are absent.
- Global routing binds the exact four-route canonical JSON string. Unknown
  routes fail closed, and only `ADAPTIVE_RESEARCH_ELIGIBLE` names the inert P3
  preregistration consumer.

## Frozen recovery boundary

| Item | Frozen value |
|---|---|
| Input manifest | `94f7e6448fa1572802a050129d09c8bd679772afc62f31f0d1dc2544d098c58a` |
| Input snapshot | `85be3d0edf17b94510d68da6b5b8bfe1c73583222a8bc2822cb7e46bee08f4e3` |
| Input Ready queue | empty |
| First output Ready | `m4-v2-marginal-static-historical-identity-adoption-recovery-v1` |
| New keys | 1 |
| Same-key revisions | 10 |
| Predictive-P3 folds | 0 |

The pure builder checks this boundary before emitting bytes. Repository import
also locks the current control-plane row and verifies the exact result-blind
failed definition, state, execution, capability, source manifest, and ordered
started/failed event metadata before its first write. Missing, extra, reordered,
or substituted lineage aborts the same transaction. Import remains a separate
all-or-nothing Operator action; this Engineering execution did not import a
manifest or run the Supervisor.

## Integration matrix

| Link | Engineering evidence | Mainline status |
|---|---|---|
| Goal → Resolver | Exact recovery input and canonical task definitions tested | CODE_COMPLETE |
| Resolver → Ready Queue | Pure resolution yields the unique recovery task | CODE_COMPLETE |
| Ready Queue → Supervisor | Recovery key dispatch and parent lookup wired | INTEGRATION_PENDING |
| Supervisor → Artifacts | Original terminal/artifact compatibility identity retained | INTEGRATION_PENDING |
| Artifacts → Status | Canonical validator/projector binds the recovery completion fact | INTEGRATION_PENDING |
| Status → Next Task | Canonical downstream consumer chain frozen | INTEGRATION_PENDING |
| Deterministic replay | Code path and identities covered by tests | INTEGRATION_PENDING |

## Non-goals and result

No threshold, estimator, artifact schema, registration order, scientific
failure rule, branch result, or route rule changed. No Supervisor, workload,
replay, routing, P3, P4, Promotion, or production action ran. Predictive-P3
folds remain exactly zero.

`NO — INTEGRATION_PENDING`

The next consumer is a separately approved Operator import and unified-mainline
run from the frozen recovery manifest boundary.
