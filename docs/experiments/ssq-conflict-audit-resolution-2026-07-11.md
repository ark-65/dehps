# SSQ conflict audit resolution round — 2026-07-11

## Primary goal

Add a safe operator recovery path for parser/sync draw conflicts so resolved evidence remains auditable while only unresolved conflicts block forward evaluation, advisor refresh, and supervisor startup.

## Non-goals

- No prediction model, weight, candidate source, advisor, or promotion rule changes.
- No automatic conflict selection or autonomous use of the resolver.
- No deletion or rewriting of historical conflict evidence or sync-run counts.

## Gauss verification pass

The smallest proof obligation is draw-state identity, not model performance:

1. A resolution must explicitly choose the recorded existing or incoming state.
2. Both red-ball states must remain legal six-number sorted subsets of 1–33.
3. The canonical row must still equal one of the two recorded states while locked; a third state fails closed.
4. Operator identity and a non-empty verification note are mandatory.
5. Original conflict rows and historical sync `conflict_count` values remain immutable evidence. Resolution is additive metadata.
6. The watchdog rejects a conflict found in its current sync and any unresolved stored conflict before release. The watcher reports historical counts but alerts only on unresolved evidence.

## Implementation

- Added additive resolution metadata to `ssq_data_conflicts` and an idempotent runtime schema migration.
- Added a manual-only CLI requiring conflict id, explicit `existing|incoming`, verification note, and operator identity.
- Added row locks, canonical stale-state checks, legal red-number checks, and grouped duplicate-conflict resolution.
- Changed stored-conflict gates from all recorded evidence to unresolved evidence while preserving total and latest-sync counts in reports.
- Added self-iteration instructions that explicitly forbid autonomous invocation.

## Validation

- Focused conflict, watcher, watchdog, and self-iteration tests: 117 passed.
- Full worker suite: 608 passed.
- Shell syntax checks: passed.
- Live schema migration added all six resolution columns; recorded conflicts: 0, unresolved conflicts: 0.
- Live watchdog sync `sync-20260711-172359`: fetched 1, skipped 1, conflicts 0; forward batch accepted 0 due rows; supervisor remained intentionally parked for `2026079`.

## Operational recovery

The operator verifies an authoritative draw, runs `scripts/resolve_ssq_data_conflict.py`, then lets the next watchdog sync re-check the selected canonical state. If the source continues disagreeing, the sync creates unresolved evidence again and release remains blocked.
