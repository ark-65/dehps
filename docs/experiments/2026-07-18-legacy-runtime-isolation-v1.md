# Legacy Runtime Isolation v1 acceptance report

## Round contract

- Primary goal: remove the final application-level raw scoring Runtime bypass.
- Engineering authorization: Agent Request `125`
  (`engineering-legacy-runtime-isolation-5d67a45`), execution `48`.
- Base commit: `5d67a45`.
- Runtime operation impact: none; no database, supervisor, deployment, prediction, or research
  decision operation was performed.

## Root cause

The simultaneous forward shadow path already consumed one `VerifiedRuntimePackage`, but the
post-draw compensation script still called raw NumPy and Numba backends through
`execute_shadow_pair(...)`. That path could reproduce correct scores without proving the shared
History/Window/Candidate/Feature Runtime identity.

The same raw helper and `KernelPlanner.backend()` were publicly importable, so documentation alone
could not prevent a future application caller from restoring the bypass.

## Implemented boundary

- Post-draw replay compiles the exact persisted training history and target issue through
  `RuntimeInputCompiler`.
- Both shadow backends execute from one verified Runtime package.
- Runtime ABI Cache receipts propagate into comparison evidence.
- Raw shadow helpers, the raw Planner accessor, and the optimization score-matrix helper are removed.
- The independent full-matrix formula remains local to benchmark/tests.
- An AST source-boundary test rejects future application reintroduction of the raw names.

## Validation

Focused shadow/forward/Runtime regression:

```text
83 passed in 14.84s
```

Complete worker regression:

```text
1213 passed, 4 warnings in 51.13s
```

The warnings are the existing Python 3.14 `multiprocessing` warning about calling `fork()` from a
multi-threaded process; this round introduced no new warning class.

The post-draw replay fixture also executed the removed raw NumPy calculation as a test-only oracle.
The verified NumPy result was strictly equal for target scores, exact ranks, TopK candidate ids and
scores, and Red5 candidate ids, scores, and ranks. The verified NumPy and Numba results emitted the
same `verified_runtime_id`, matching the Runtime ABI Cache receipt.

The source-boundary scan proves that non-test application/script consumers contain no import or call
of `NumpyReferenceBackend`, `NumbaCpuBackend`, `_score_matrix`, `execute_shadow_pair`,
`run_shadow_comparison`, or `.backend()`. The only raw backend class consumer outside implementation
modules is the explicit `scripts/benchmark_scoring_kernel.py` oracle.

## Non-impact evidence

- no production backend or environment default changed;
- no prediction or candidate generation path changed;
- no database schema or data mutation;
- no supervisor or live process operation;
- no scoring, ranking, evaluation, seed, or post-draw attestation formula change.

## Remaining boundary

Application scoring paths now require verified Runtime inputs. Backend implementation classes remain
testable, and the explicit benchmark oracle remains available for independent equivalence evidence.
The next engineering target is verification/digest performance without weakening fail-closed
mutation detection. Three real future-issue shadow attestations and independent backend promotion
approval remain outstanding.
