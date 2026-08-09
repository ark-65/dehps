# Prediction v2 balanced-design feasibility design — Round 84

## Primary goal

Bind the approved result-blind Research Request 411 to the canonical M4 Goal,
resolver, Ready Queue, unified supervisor, immutable artifacts, status projection,
downstream preregistration task, and deterministic replay. This round freezes the
exact `2-(33,6,5)` feasibility question; it does not run a constructor or solver.

## Non-goals

- No historical rows, prior scores, prior predictions, or prior rankings are read.
- No solver node or candidate block is executed.
- No existence or nonexistence claim is made.
- No Evidence, model, candidate expert, promotion, P3, or production action is
  created.
- No legacy Prediction mainline is reactivated.

## Exact design boundary

The fixed 176-block, six-number portfolio has the necessary integer identities:

- `176 * 6 = 33 * 32 = 1056`
- `176 * C(6,2) = C(33,2) * 5 = 2640`
- `32 * 5 = 5 * 32 = 160` locally at every point

These identities establish arithmetic compatibility only. They do not prove that
a simple `2-(33,6,5)` design exists. A future bounded search miss is registered as
`NOT_FOUND_WITHIN_FROZEN_BUDGET`, not as a nonexistence proof.

## Repetition policy

Independent duplicate, membership, and uniqueness scans are absent. Future block
generation must emit strictly increasing canonical combinadic block IDs, so
repetition is impossible by construction. Artifacts expose the declarative marker
`repetition_scan=ABSENT_BY_CONSTRUCTION`; they do not execute a second validation
pass. Immutable artifact-registry identity checks remain part of mainline
provenance and are not candidate duplication scans.

## Governance and validation

- Research Request 411 / Research execution 332: approved and completed.
- Engineering Request 412 / Engineering execution 333: approved and authorized.
- Source contract digest:
  `a9665143242689b02702f88f9782d5fe11a52240fed11d1c6ebfef8d5dca10c2`.
- Frozen contract digest:
  `f428cc9df3a988f8d2919efa3b369ca3b5cdc4a64c4e29a03787bc14d4fe0271`.
- Additive migration dry run: 70 to 71 tasks; one allowlisted task revision,
  one allowlisted new task, zero deletions, zero state regressions, zero
  unallowlisted rewrites.
- Targeted artifact, replay, migration, status, index, and supervisor tests pass.

## Mainline integration matrix

| Binding | Round 84 state |
| --- | --- |
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` |
| Resolver / Ready Queue | Approved event is additive; feasibility task becomes Ready after import |
| Supervisor | Singular balanced-design feasibility capability registered |
| Capability | Zero-work exact feasibility-design artifact builder |
| Artifacts | Specification, preregistration handoff, completion, mainline execution |
| Status | Design and downstream preregistration projections implemented |
| Next task | `prediction-v2-balanced-design-feasibility-preregistration` |
| Replay | Deterministic registered-content replay implemented |
| Merged-main live proof | Pending PR merge and fresh Operator execution |

Integration answer: **NO — INTEGRATION_PENDING**. Source behavior is code-complete,
but capability completion requires merged-main import, fresh unified supervisor
execution, immutable registration, completion projection, and deterministic replay.
