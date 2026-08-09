# Prediction v2 balanced-design feasibility execution — round 93

## Primary goal

Implement approved Engineering Request 420 as the singular executable consumer
of frozen Research Request 417: compile the complete `Z_33` translation-orbit
quotient, execute the exact 16-coordinate multicover, checkpoint it durably, and
emit a proof-carrying cyclic feasibility result.

## Non-goals

- No full `v=33` inventory or search was executed during Engineering.
- No noncyclic search and no global nonexistence conclusion.
- No database, historical draw, prior score, prior prediction, ranking, or prior
  feasibility-result input.
- No model, prediction Evidence, expert activation, promotion, P3, betting, or
  production action.

## Repetition validation removed

There is no separate duplicate, membership, uniqueness, or repetition pass.
The representation makes repetition unavailable:

1. every block is generated from one minimum translation representative;
2. signature groups retain exact representative multiplicity;
3. the solver materializes selected representative IDs in increasing order;
4. the certificate stores one first combinadic ID followed by unsigned
   `gap_minus_one` values, so its decoded block IDs are strictly increasing;
5. the verifier reconstructs the selected orbits and performs one point/pair
   incidence-count pass only.

The projected marker remains:

```text
repetition_scan = ABSENT_BY_CONSTRUCTION
```

## Executable boundary

The implementation preserves the preregistered scope and budgets:

- `C(33,6) = 1,107,568` legal blocks;
- 201,376 zero-normalized candidates;
- 33,561 full size-33 orbits and five short size-11 orbits;
- profiles `(5 full, 1 short)` then `(4 full, 4 short)`;
- exact circular-distance target `(5,...,5)` over 16 coordinates;
- 100,000,000 node maximum, checkpoints every 1,000,000 nodes, and 4 GiB
  resident-memory limit;
- positive `FOUND_EXACT_2_33_6_5_DESIGN` only after exact certificate counting;
- negative `NOT_FOUND_WITHIN_FROZEN_BUDGET` remains cyclic/budget bounded;
- identity or proof failure has no research conclusion.

The append-only checkpoint journal binds the source contract, preregistration,
execution ID, completed branch index, residual, selected multiplicities, DFS
stack, node count, transcript, and previous checkpoint digest.

## Gauss–Riemann cross-review

The Gauss pass supplied the exact proof obligations: rank/unrank bijection,
orbit cardinality, lossless signature multiplicity, deterministic resume, and
33 point counts of 32 plus 528 pair counts of 5 for a formal positive result.
The Riemann pass kept the quotient boundary explicit: the 16 distance
coordinates are lossless only inside the declared translation-invariant space,
and cyclic exhaustion says nothing about noncyclic designs. Their shared
conclusion was implemented as asymmetric outcome semantics: a verified
certificate can prove cyclic existence; a miss cannot prove global
nonexistence.

## Validation performed in Engineering

- Complete `v=7,k=3` translation-orbit inventory against the literal legal
  universe.
- Deterministic Fano-plane exact-multicover certificate and one-pass incidence
  verification.
- Node-cap interruption and hash-bound checkpoint resume equal to uninterrupted
  search.
- Source, checkpoint, and certificate tamper rejection.
- Registered inventory/result/completion replay without rerunning the search.
- Unified Supervisor execution/registration/replay using a toy proof.
- Additive 72-to-73 task migration dry run against the durable control plane:
  71 unchanged tasks, one allowlisted revision, one allowlisted addition, zero
  state regressions, zero fact deletions, and zero unallowlisted rewrites.
- Result-decision stop boundary and status projection.
- Focused execution/preregistration/design/hardening suite: 96 passed.
- The local full worker run reached 2,297 passed and four skipped. One related
  historical recovery-fixture failure was fixed and included in the 96-pass
  rerun. The other 42 failures are legacy prediction/mail/training tests blocked
  by this host's durable `legacy-retirement-activation.json`; that runtime state
  was preserved. Clean-checkout GitHub CI remains the full-suite acceptance
  authority.

## Integration matrix

| Binding | Round-93 code-complete state |
| --- | --- |
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` |
| Resolver | Completed preregistration, completion fact, and approved execution event declared |
| Ready Queue | Additive migration preserves durable state and makes only execution runnable |
| Supervisor | Execution capability, three children, mainline artifact, and replay path implemented |
| Capability | Complete cyclic quotient compiler, exact multicover, checkpoint, certificate, and verifier implemented |
| Artifacts | Orbit inventory, search result with proof, and execution completion |
| Status | Outcome, exact counters, no-repeat construction, and result-decision boundary projected |
| Next Task | Unsupported `prediction-v2-balanced-design-feasibility-result-decision` |
| Merged-main execution | Pending PR merge and CI |
| Deterministic durable replay | Pending merged-main Operator execution |

Integration answer at code-complete time:

```text
NO — INTEGRATION_PENDING
```

It can become `YES — validated by unified mainline execution and replay` only
after merged-main CI, an approved Operator import, one formal Supervisor
execution, four immutable registrations, status projection, and deterministic
registered-output replay succeed.
