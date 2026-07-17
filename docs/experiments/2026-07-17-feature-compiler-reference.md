# Feature Compiler Reference Implementation - 2026-07-17

## Goal

Implement the control-plane reference compiler for `feature.v1.0.0` and prove that it reproduces the
existing NumPy component calculation without changing scoring runtime behavior.

## Non-goals

- No Feature ABI v1 layout.
- No Kernel Planner, NumPy backend, Numba backend, scoring, ranking, or TopK change.
- No production prediction, pending candidate, database, fingerprint, or live runtime mutation.
- No replacement of the current `component_tile` hot path.

## Runtime boundary added

```text
WindowArtifact.verify()
        +
CandidateStore.validate() -> CandidateABIVerifier
        +
target execution context
        |
        v
FeatureCompiler (NumPy reference)
        |
        v
CompiledFeatureArtifact
        |
        v
FeatureArtifactVerifier -> reject / accept
```

The artifact binds:

- Feature Contract and component-manifest digests;
- Window Artifact digest;
- Candidate ABI package digest;
- candidate static-column digest for the compiled row range;
- target-date/weekday context digest;
- compiler version, row range, dtype, shape, and Feature values digest.

Candidate static columns are recorded because the current reference calculation uses precomputed
CandidateStore fields beyond Candidate ABI v1's `numbers`, `mask`, and `lex_id`. This is explicit
transition evidence, not a claim that those columns already belong to Candidate ABI or Feature ABI.

## Failure policy

The compiler and verifier do not reorder, coerce, repair, or silently normalize inputs. They reject:

- invalid Window artifacts;
- missing or invalid Candidate ABI packages;
- invalid row ranges, target dates, or target-date leakage;
- contract or manifest mismatch;
- dependency-digest mismatch;
- non-`float64`, non-contiguous, wrong-shape, non-finite, or mutated Feature values.

## Identity and determinism

Identical Window, Candidate runtime input, row range, and target context produce the same header and
artifact digest. A different target weekday produces a different context and artifact identity.
System time and random state are not compiler inputs.

## Validation

Focused validation:

```bash
apps/worker-python/.venv/bin/python -m pytest -q \
  apps/worker-python/tests/test_feature_compiler.py \
  apps/worker-python/tests/test_feature_contract.py
```

Result:

```text
15 passed
```

Covered:

- exact equality with the current reference `component_tile`;
- Golden Row stability;
- deterministic repeated compilation;
- payload-mutation rejection;
- Candidate dependency-mismatch rejection;
- invalid row-range rejection;
- explicit target-context identity;
- proof that the artifact is not attached to CandidateStore or consumed by Kernel state.

Contract/kernel regression:

```text
72 passed
```

Full worker regression:

```text
1097 passed, 4 existing multiprocessing/fork warnings
```

## Production state

No database migration or live operation was performed. Existing predictions, the 2026081 pending
runs and candidates, production backend defaults, watchdog state, and historical artifacts remain
unchanged.
