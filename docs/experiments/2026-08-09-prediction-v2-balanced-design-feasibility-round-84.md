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
  `f055aae2ae70af5d21fbfc2a1bfa50952fca595e906cd82556b445c3299acade`.
- Frozen contract digest:
  `7ba0ca00660b91e4a91eac640f5d932ff1073963089f21f7bf62f67ab04d6287`.
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

## Round 88 identity correction and zero-work recovery

The first merged-main attempt failed closed before artifact creation. The frozen
source accidentally bound a 62-character transcription of the already immutable
route-completion digest. The supervisor correctly rejected it with
`Prediction v2 balanced-design feasibility input identities changed`.

- Failed task digest:
  `de250a22f39c245d90f78a91d4a9184246e30e705ead656407504e41b0cb94b0`.
- Failed execution:
  `135b2ad17fb5e7bfb146859fc35927ee3521eadfd16294221d70483b3ea4f456`.
- Preserved failed event:
  `6fdcf5a081b29f735cd392e7aa8ea6e99d4ae858e202a6b667fa62d9908f188a`.
- Failed durable manifest:
  `41a0256dfbee93122ab207218d6b7f85122963b0018edaac2bf8c401a17e3259`.
- Execution artifacts: zero.
- Solver nodes and generated candidate blocks: zero.
- Corrected immutable route-completion digest:
  `147cd0819bca3da1a925812e4f1ac556eeefef79b1973b1027406b9d6a511887`.

Recovery is fail-closed and replaces only that failed task definition, preserving
the started/failed execution events and old source fact. It adds the corrected
source fact and resets the new task identity to `draft/INTEGRATION_PENDING` for a
fresh execution ID. It cannot recover if an artifact, completed event, error
change, unrelated task-definition rewrite, or manifest-identity drift is present.

The read-only recovery rehearsal against the durable failed state passed:

- Corrected task digest:
  `be3f64a29262c9807a8d7f5fce795a2334f2b3359fd862903f3c2fdcbea53985`.
- Proposed recovered manifest:
  `ca82cdfc8a166d0212f6c94efaaf83eceb0722a2bf6a63316fed4dd93a19965d`.
- Changed tasks: one; added source facts: one.
- Deleted tasks, facts, or events: zero; rewritten events: zero.
- Preexisting execution artifacts: zero.

The repetition policy is unchanged and stricter after correction: no independent
duplicate, membership, uniqueness, or repetition pass exists. Strictly increasing
canonical combinadic IDs make repeated blocks unrepresentable. The recovery path
also records `repetition_scan=ABSENT_BY_CONSTRUCTION` and performs no candidate
work.

Round 88 integration answer remains **NO — INTEGRATION_PENDING** until this
correction is merged, the exact recovery is imported by a newly approved Operator
execution, and the corrected capability completes and replays on merged main.
