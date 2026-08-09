# Prediction v2 balanced-design structural evaluation execution — round 105

Date: 2026-08-09

## Primary goal

Implement the frozen structural evaluation as the singular canonical Research
Evidence Supervisor capability, with 9,999 primary and 1,999 secondary null
replicates, deterministic checkpoints, and deterministic registered-output
replay.

## Non-goals

- Do not change the preregistered endpoint, null families, alpha, or outcome
  mapping.
- Do not read historical outcomes or create historical/forward Evidence.
- Do not create or activate a model, expert, portfolio, P3 task, or production
  route.
- Do not add a duplicate, membership, uniqueness, or repetition scan.
- Do not execute the fixed candidate or registered null program before the
  merged-main Operator round.

## Frozen execution

- Endpoint: `triple_collision_mass`.
- Exact optimized identity:
  `sum_T C(c_T,2) = sum_{i<j} C(popcount(mask_i & mask_j),3)`.
- Primary null:
  `Z33_ORBIT_PROFILE_MATCHED_WITHOUT_REPLACEMENT_5_FULL_1_SHORT_B176`,
  9,999 replicates.
- Secondary, non-gating null:
  `UNIFORM_PREFIX_WITHOUT_REPLACEMENT_FROM_ALL_1107568_LEGAL_BLOCKS_B176`,
  1,999 replicates.
- Randomness: domain-separated SHAKE256 counter mode with unbiased
  `random_below`, feeding sparse partial Fisher-Yates sampling without
  replacement.
- Kernel: parallel Numba `uint64` block-intersection/popcount evaluation.
- Chunks: 512 primary, 256 secondary.
- Checkpoints: append-only, digest-verified, contiguous chunk records. Resume
  skips only complete committed chunks and rejects tamper, gaps, overlaps,
  reordering, or partial records.
- Replay: recomputes inference from the registered replicate-index arrays; it
  does not regenerate samples or rerun the workload.

## Duplicate-validation removal

Both null generators are injective by construction within a replicate:
orbit representatives are selected without replacement for the matched null,
and legal block indices are selected without replacement for the secondary
null. The fixed candidate is consumed from the already registered certificate
and orbit inventory. Therefore this round has no separate duplicate,
membership, uniqueness, or repetition pass:

```text
duplicate_membership_uniqueness_or_repetition_scans = 0
duplicate_validation_pass = false
membership_validation_pass = false
uniqueness_validation_pass = false
repetition_scan = ABSENT_BY_CONSTRUCTION
```

This removes the redundant full scan without weakening the frozen sampling
contract. Structural correctness is checked through deterministic construction,
source identities, exact artifact digests, checkpoint sequence rules, and the
collision identity.

## Scientific review

Einstein pass: the smallest falsifiable claim is only whether the fixed
candidate has lower or higher triple-collision mass than the matched structural
null. No predictive or economic interpretation follows from that result.

Gauss pass: the legal sample space, without-replacement sampling, plus-one tail
counts, fixed alpha, exact combinatorial identity, deterministic vectors, and
thread-count invariance are explicit proof obligations.

Riemann pass: the primary null preserves the orbit-profile geometry of the
candidate, while the secondary null measures sensitivity to that geometry but
cannot change the primary outcome.

Shared conclusion: execute the single scalar endpoint under the matched null,
retain diagnostics as non-gating structure, and defer interpretation to the
separate result-decision task.

## Validation before publication

- Ruff passed on every touched Python surface.
- Focused structural-evaluation, parent-chain, recovery, manifest-index, and
  roadmap tests passed.
- Deterministic vectors cover SHAKE256 rejection sampling and sparse partial
  Fisher-Yates output.
- The direct triple-count implementation equals the optimized pair-intersection
  identity.
- The Numba kernel produces identical output with one and two threads.
- Checkpoint resume, tamper rejection, gap rejection, exact plus-one inference,
  registered-array replay, and pinned source bytes are covered.
- Additive migration dry run: 76 to 77 tasks, 75 unchanged, one allowlisted
  revision, one allowlisted new task, zero state regression, zero fact deletion,
  and zero unallowlisted rewrite.
- Full Worker suite: `2372 passed, 4 skipped, 26 warnings` in 279.04 seconds.
- Legacy-retirement activation was isolated only inside a trap-restored test
  shell and restored byte-for-byte; SHA-256 before and after was
  `711fc6149b0eefea99a19c4591b82a9b5a9513c7c1449c8152f13025f7f4f9af`.

## Mainline integration matrix

| Binding | Status before merged-main Operator execution |
| --- | --- |
| Goal declaration | Complete |
| Resolver and Ready Queue task | Complete in candidate manifest |
| Canonical Supervisor capability | Code complete |
| Fixed parent artifacts | Registered and exact |
| Null workload | Not executed in Engineering |
| Immutable result/diagnostics/completion artifacts | Pending execution |
| Unified status projection | Code complete |
| Deterministic registered-output replay | Code complete; pending real artifacts |
| Next result-decision consumer | Declared, unsupported pending next round |

Mainline acceptance answer before the Operator round:

`NO — INTEGRATION_PENDING`

The capability becomes complete only after the ready PR is merged, the exact
77-task manifest is imported by an approved Operator Request, the fresh
merged-main Supervisor completes all 11,998 replicates, the four output
registrations replay exactly, and the completion fact advances the result
decision task.
