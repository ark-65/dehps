# Training watch artifact persistence v1

Date: 2026-07-11

## Primary goal

Keep long-running DEHPS observation sustainable while preserving immediate evidence for material state changes. Stable parked-state polls should update the canonical latest artifacts without creating a new full JSON/Markdown pair every time.

## Non-goals

- No model, objective, weight, advisor, candidate source, search budget, or promotion change.
- No deletion, pruning, compression, or rewriting of existing versioned evidence.
- No relaxation of frozen validation, forward evidence, null, parser/sync, or leakage gates.

## Task frame

The live system was intentionally parked at issue `2026078`, awaiting the complete three-line snapshot for `2026079`. Advisors and parser/sync checks were current, forward evidence remained `0/20`, and automatic promotion remained disabled. At the same time, `data/output/optimization/training-watch` already contained 986 JSON and 986 Markdown files totaling 45,886,873 bytes. The latest pair alone was about 112 KB, while repeated parked-state calls materially changed only timestamps and observation ages.

The historical Gauss and Riemann names below denote inspired verification lenses, not literal minds or complete historical reconstructions.

## Gauss pass: verification

- Strongest claim: continuing same-history training cannot create independent evidence, and continuing to persist every identical poll creates storage cost without improving the statistical ledger.
- Weakest assumption: a selected material-state projection is sufficient to identify every transition that deserves an immediate versioned artifact.
- Required test: alert/action changes, parser conflict-count changes, new rounds, forward progress, advisor status, supervisor lifecycle, scientific-boundary state, and null-ledger progress must force a snapshot inside the heartbeat interval.
- Boundary: no historical authority is evidence; tests and live artifacts are the evidence.

## Riemann pass: structure

- Strongest claim: eight distinct source-conversion signatures mapping to one final-performance signature are different paths on the same observed historical surface, not eight independent surfaces. Waiting for the next unseen issue is the correct state-space transition.
- Weakest assumption: the chosen snapshot projection captures the relevant quotient classes of operational state without hiding a global transition.
- Required test: the projection must include evidence geometry, forward state, lifecycle, parser integrity, advisor freshness, holdout/prediction boundaries, and sequential-null coverage rather than only severity/action.
- Boundary: this is a modern structural analogy, not a claim about Riemann's literal methods.

## Cross-review and disagreement

Gauss rejects source-budget changes because no forward observation exists and the same-history adaptive family remains incomplete. Riemann agrees that compute should stop, but warns that an overly narrow artifact fingerprint could collapse distinct failure states. The implementation therefore includes exact integrity counts and scientific-boundary states in addition to the operator action.

The unresolved disagreement is whether the 120-minute heartbeat is globally optimal. It is an operational parameter, not a model parameter; future evidence may justify changing it, but this round makes no performance claim about that value.

## Synthesis

The smallest shared conclusion is:

1. Preserve the forward-wait parking decision.
2. Always atomically refresh `training-watch-latest.json` and `.md`.
3. Create versioned artifacts immediately on a material state transition.
4. While state is stable, create a versioned heartbeat at most once per 120 minutes.
5. Never delete existing versioned artifacts in this protocol.

## Implementation

`watch_training_progress.py` now records `artifact_persistence.protocol=material_change_or_heartbeat_v1`. Its material state includes run/round and query-window scope, severity/action, forward evidence and wait state, supervisor lifecycle, advisor freshness, parser/sync counts, holdout and prediction boundaries, source-performance geometry, sequential-null coverage, and heavy-job ownership relation. Calls with different `--limit` scopes may therefore create distinct snapshots; repeated calls at the same scope are throttled.

The CLI exposes `--snapshot-minutes`; the default is 120 and `0` preserves the prior every-call behavior. The CLI result says whether a versioned snapshot was created, why, and whether latest artifacts were updated.

The latest artifact also carries the last versioned snapshot timestamp and paths. Stable polls use that marker plus an existence check, avoiding an unbounded directory scan after the protocol has initialized; legacy latest artifacts fall back to one scan and are then upgraded.

## Validation

- Focused training-watch tests: 102 passed.
- Full worker suite after the final marker optimization: 612 passed.
- Temporary live output directory:
  - first call: `versioned_snapshot_created=true`, reason `first_snapshot`;
  - second unchanged call: `versioned_snapshot_created=false`, reason `stable_within_interval`;
  - exactly one versioned JSON/Markdown pair remained, while latest JSON/Markdown were refreshed.
- Real output directory at the same `--limit 5` scope: versioned JSON count remained 987 across two calls; both reported `stable_within_interval`, while latest artifacts received the durable last-snapshot marker.
- Live watchdog sync `sync-20260711-173639`: fetched 1, skipped 1, conflicts 0; evaluation batch accepted 0 due rows and the supervisor remained parked for `2026079`. Its different query-window scope produced one explicit scope snapshot; repeated calls at that scope were then throttled.
- Post-merge `main` commit `fbdfeb3`: watchdog sync `sync-20260711-174505` fetched 1, skipped 1, conflicts 0; no forward rows were due and the supervisor remained parked for `2026079`.
- Post-merge same-scope artifact count stayed 987 before and after the watchdog plus a direct watcher call. Latest reported `stable_within_interval`, parser/sync passed, unresolved conflicts were 0, historical holdout quarantine remained active, and promotion remained disabled.

## Acceptance result

The persistence protocol is accepted for continued operation. The next scientific verification remains the unchanged forward boundary: sync issue `2026079`, evaluate its pre-draw three-line snapshots, and continue accumulating paired unseen issues toward the 20-issue manual-review threshold.
