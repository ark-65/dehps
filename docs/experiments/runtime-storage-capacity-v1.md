# Runtime storage capacity v1

Date: 2026-07-11

## Primary goal

Prevent the long-running DEHPS training and self-iteration loop from silently exhausting its filesystem while preserving all existing runtime and scientific evidence.

## Non-goals

- No deletion, compression, rotation, movement, or rewriting of runtime evidence.
- No model, advisor, objective, candidate, budget, selection, or promotion change.
- No recursive scan of the growing watcher evidence directory.

## Evidence and thresholds

Before this round, the repository filesystem had approximately 804 GiB free. The three known append-only scheduler logs totaled about 73.5 MB, including a 69.8 MB self-iteration log. This was not an immediate capacity incident, but there was no machine-readable guard before sync or heavy training startup.

The protocol predeclares two free-space thresholds using the stricter ratio or absolute value:

- warning: `max(5% of filesystem, 20 GiB)`;
- critical: `max(1% of filesystem, 5 GiB)`.

Warning is observation-only and requests an evidence-retention review. Critical or unavailable capacity fails closed before synchronization, forward evaluation, advisor refresh, and supervisor startup. Neither state authorizes automatic cleanup.

## Implementation

- `dehps.runtime.storage_capacity` uses one filesystem capacity call and direct `stat` calls for the three known append-only logs.
- `check_runtime_storage_capacity.py` exits nonzero only for `critical` or `unavailable` states.
- The watchdog invokes the checker before any sync or heavy work.
- The watcher exposes the complete summary in JSON, compact operator output, Markdown, recommendation notes, and material artifact-state transitions.
- The two-hour self-iteration contract requires review and prohibits automatic deletion, compression, rotation, or evidence replacement.

## Safety invariants

- `automatic_cleanup_allowed=false`.
- `selection_changed=false`.
- `promotion_allowed=false`.
- Capacity growth is operational evidence, not model improvement.

## Validation

- Focused storage, watcher, watchdog-contract, and self-iteration-contract tests: 122 passed.
- Shell syntax checks passed.
- Live capacity: `healthy`, free ratio `0.858019`, free bytes `863054258176`, warning threshold `50293399347`, critical threshold `10058679869`.
- Live observed append logs: `73499853` bytes.
- Live watchdog `sync-20260711-181159`: capacity accepted, fetched 1, skipped 1, conflicts 0; no forward rows were due and the supervisor remained parked for `2026079`.
- Full worker suite: 620 passed.
- Post-merge validation: pending.

## Remaining limitation

This protocol detects capacity risk but does not choose a retention policy. Any future archival design must preserve evidence content and integrity, document restoration, and remain an explicit reviewed change.
