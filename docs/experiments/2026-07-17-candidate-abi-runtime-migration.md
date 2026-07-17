# Candidate ABI Runtime Migration - 2026-07-17

## Goal

Connect `candidate_abi.v1` to the existing CandidateStore -> Kernel -> Artifact path without changing scoring math, ranking output, pending predictions, or database state.

## Non-goals

- No Feature Contract or Feature ABI work.
- No candidate generation, hard-filter, compression, sampling, or Top-N strategy change.
- No Numba math, TopK, production backend default, or database migration.
- No rewrite of existing production prediction runs or pending candidate rows.

## Changes

- Added `CandidateArrayCompiler`, which compiles already-materialized Candidate ABI buffers without reordering, repair, or payload copying.
- Added a CandidateStore adapter that compiles the current `numbers` and `candidate_mask` buffers into a verified Candidate ABI package.
- Kept existing Kernel candidate ids as CandidateStore row indexes, preserving current strict_v1 scoring and ranking output.
- Added fail-closed Kernel preparation: a store without a valid Candidate ABI package, or with mismatched contract/layout/digest/buffer metadata, is rejected before scoring.
- Propagated Candidate ABI envelope fields into scoring telemetry, matrix cache metadata, `scoring_kernel` cache metadata, and shadow comparison reports.

## Compatibility Notes

Candidate ABI describes representation and identity. It does not own candidate-set policy. Hard filters, excluded combinations, compressed sets, merged sources, and research sampling remain Candidate Set Artifact or generation-strategy concerns.

The adapter is explicit compatibility infrastructure. It may feed the current hot path, but long-term Kernel backends should consume compiled ABI packages directly rather than relying on the legacy CandidateStore adapter.

## Validation

Focused validation:

```bash
apps/worker-python/.venv/bin/python -m pytest -q \
  apps/worker-python/tests/test_candidate_abi_contract.py \
  apps/worker-python/tests/test_scoring_kernel.py \
  apps/worker-python/tests/test_ranking_contract.py
```

Result:

```text
52 passed in 14.70s
```

Covered:

- mmap-backed matrix `numbers` buffer is reused as Candidate ABI payload;
- CandidateStore mask buffer is reused as Candidate ABI payload;
- Kernel telemetry carries `candidate_abi`, `candidate_digest`, `candidate_layout_digest`, and `candidate_package_digest`;
- shadow comparison report carries Candidate ABI identity;
- ABI layout mismatch is rejected before scoring;
- existing strict_v1 scoring/ranking expectations remain unchanged.

## Database And Production State

No database migration was added. No production prediction rows, pending candidates, historical fingerprints, or runtime prediction state were modified.

