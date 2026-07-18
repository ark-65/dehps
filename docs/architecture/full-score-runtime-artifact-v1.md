# FullScore Runtime Artifact v1

## Purpose

Some research diagnostics require every candidate/config score, not only TopK or exact ranks. A full
score grid is therefore a legitimate Artifact type, but it must not bypass Runtime enforcement by
returning an unaudited NumPy array.

`full_score_grid_artifact.v1` defines this path:

```text
VerifiedRuntimePackage + WeightMatrix + code commit
                         │
                         ▼
             FullScore Artifact Compiler
                         │
              verified Feature ABI tiles
                         │
                         ▼
          float64[candidate, config] scores
                         │
                         ▼
       Header + payload digest + Runtime Envelope
                         │
                         ▼
             FullScore Artifact Verifier
```

The compiler sees only Feature ABI columns and numeric weights. It does not interpret Frequency,
Gap, Zone, history rows, candidate rules, or residual-model meaning.

## Artifact identity

The header binds:

- artifact, scoring, and ranking contract versions;
- explicit reference backend;
- `verified_runtime_id`, Runtime verification digest, and Feature Runtime digest;
- candidate, config, and Feature component counts;
- candidate-major C-contiguous `float64` layout;
- WeightMatrix digest;
- full score-buffer digest.

The Runtime Envelope independently binds History Snapshot, Window Artifact, Candidate ABI, Feature
ABI, scoring/ranking contracts, backend, full code commit, ABI package, canonical state path, and the
artifact payload digest.

`artifact_digest` seals both the FullScore payload and Runtime Envelope. Metadata can be stored in
JSON without embedding the potentially large score buffer.

## Compiler semantics

For each verified Feature tile:

```text
scores[start:end] = round(feature_values @ weights.T, 8)
```

The output layout is `candidate_major_c_contiguous`, so `scores[:, config_index]` preserves existing
research consumers. The score buffer is finite, C-contiguous, object-free, and read-only before the
Artifact is returned.

## Fail-closed verification

Verification rejects:

- raw or incorrectly sealed Runtime inputs;
- Runtime/weight/header identity drift;
- wrong dtype, shape, layout, or writable score buffers;
- NaN or infinity;
- score payload mutation;
- Runtime Envelope backend, state, binding, or payload mismatch.

No verifier path casts, copies, rounds, repairs, reorders, or recalculates caller-supplied Artifact
data.

## Residual research migration

The near-residual backtest now calls `compile_score_config_grid_artifact(...)`, consumes the same
candidate-major score columns as before, and includes `score_artifact` metadata in every target row.
Residual construction, deterministic shuffle seed, ranking metrics, target boundaries, and output
claims are unchanged.

`score_config_grid(...)` remains only as a compatibility projection returning the verified
Artifact's read-only `scores` view. The independent score-matrix oracle now lives only inside
`scripts/benchmark_scoring_kernel.py` and tests; application modules no longer expose it.

## Non-goals

- no persistence database schema;
- no new residual model or research conclusion;
- no production prediction change;
- no Numba/GPU FullScore backend;
- no verifier-performance relaxation.
