# Legacy Runtime Isolation v1

## Purpose

Runtime enforcement is incomplete while an application caller can still select a raw backend and
pass `CandidateStore + PackedWindowState` directly. Equal numerical output does not prove that the
History, Window, Candidate, Feature, code, and ABI identities were verified.

The application execution boundary is now:

```text
effective history + canonical CandidateStore
                    │
                    ▼
           RuntimeInputCompiler
                    │
                    ▼
          VerifiedRuntimePackage
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
 Feature ABI NumPy    Feature ABI Numba
          └─────────┬─────────┘
                    ▼
       strict comparison Artifact
```

## Removed escape hatches

The public application surface no longer contains:

- `KernelPlanner.backend()`;
- `execute_shadow_pair(...)`;
- `run_shadow_comparison(...)`;
- the optimization-layer `_score_matrix(...)` helper.

`KernelPlanner` can select only Feature ABI implementations for application execution. Preparing a
Feature ABI backend requires a sealed `VerifiedRuntimePackage`, and execution checks the prepared
backend identity.

## Post-draw replay

`scripts.run_forward_scoring_shadow` reconstructs the stored training boundary, verifies its history
and configuration fingerprints, and compiles that exact effective history with the stored target
issue. Both comparison backends receive one verified package. The emitted comparison records the
Runtime ABI Cache key, verified Runtime id, verification digest, Feature Runtime digest, and both
Runtime Envelopes.

This does not rewrite the original prediction or pre-draw Artifact. A run without pre-draw evidence
remains diagnostic post-hoc evidence. A run with a sealed simultaneous capture may link completed
evaluation evidence through the existing immutable attestation protocol.

## Source boundary

An AST-based regression test scans application and script consumers. It rejects imports or calls to
the removed raw execution names and rejects `.backend()` execution. Raw `NumpyReferenceBackend` and
`NumbaCpuBackend` classes remain available only inside scoring implementation tests and the explicit
`benchmark_scoring_kernel.py` oracle.

The Feature compiler's component reference and strict TopK utility remain implementation details;
they do not expose raw backend execution to control-plane callers.

## Non-goals

- no contract or scoring/ranking formula change;
- no backend default change or promotion decision;
- no prediction, pending candidate, database, or supervisor operation;
- no benchmark/reference oracle removal;
- no verification or digest performance optimization.
