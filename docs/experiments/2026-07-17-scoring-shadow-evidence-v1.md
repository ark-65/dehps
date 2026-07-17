# Scoring Kernel Shadow Evidence v1

## Round boundary

Primary goal: turn the existing shadow-report field list into an executable,
fail-closed NumPy/Numba comparison runtime and a three-issue evidence gate.

Non-goals:

- no production backend switch;
- no live shadow execution or production schedule change;
- no prediction, candidate, evaluation, watchdog, or database mutation;
- no automatic promotion authority;
- no tolerance-based or statistical equivalence claim.

## Root cause

`ShadowComparisonReport` described useful output fields, but there was no runtime
that executed both backends from one immutable request, no complete result seal,
no artifact verifier, and no cohort rule. A hand-authored report could therefore
not prove that NumPy and Numba consumed identical inputs or produced identical
candidate identities.

## Executable contract

`dehps.scoring_kernel.shadow` now provides:

- `run_shadow_comparison()` to execute official and shadow backends from the same
  `CandidateStore`, `PackedWindowState`, `WeightMatrix`, and `KernelRequest`;
- `compare_kernel_results()` for exact array and identity comparison;
- `verify_shadow_evidence()` for digest and internal-consistency verification;
- `write_shadow_artifact()` for atomic, content-addressed JSON evidence outside
  production tables;
- `shadow_promotion_readiness()` for the latest three consecutive target issues;
- `scripts.evaluate_scoring_shadow_gate` for read-only artifact-gate evaluation.

The comparison covers target scores, exact ranks, TopK IDs and scores, Red5 IDs,
scores and ranks, Candidate ABI verified identity, backend-neutral Runtime
Envelope dependencies, and whole-result payload digests. Any shape mismatch or
missing Candidate identity raises a structured `ShadowEvidenceViolation`.

Operational evidence is explicit. A correct pre-draw scoring comparison remains
`evaluation_status=pending` and cannot count as a passed issue. A passed line must
later carry post-draw evaluation, restart recovery, and watchdog results, all set
to `passed` with zero evaluation mismatch.

## Cohort governance

The default production cohort is:

```text
target issue N
  static_100
  dynamic_kdj
  dynamic_kdj_near
```

The latest three observed target issues must be consecutive and every required
line must pass. Older successful issues cannot hide a newer failure or pending
issue. Duplicate issue/line evidence is rejected. A successful cohort produces
`ready_for_independent_approval`, never backend promotion:

```text
automatic_promotion_allowed=false
```

## Validation

Focused shadow, ranking-contract, and scoring-kernel tests:

```text
49 passed in 8.57s
```

The integration test executes the real NumPy and Numba backends over 12,000
canonical candidates and verifies identical sealed result digests. Unit coverage
also includes score drift, shape drift, missing Candidate ABI identity, artifact
tampering, pending evaluation, missing lines, duplicate evidence, non-consecutive
issues, backend-neutral Runtime Envelope comparison, and a complete three-issue
cohort.

The empty-artifact CLI returns a sealed `insufficient_evidence` gate result, which
demonstrates that absence of evidence cannot be interpreted as a pass.

Complete worker regression:

```text
1152 passed, 4 existing multiprocessing fork warnings in 40.20s
```

## Operational state

This PR only establishes the evidence runtime. It did not execute a production
shadow, write a production artifact, restart a service, or change the official
`numpy_reference` backend. Live execution remains a separate Operator action.
