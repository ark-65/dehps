# Feature Contract v1 Specification - 2026-07-17

## Goal

Freeze `feature.v1.0.0` before Feature ABI or runtime migration work.

## Non-goals

- No Feature ABI package.
- No Kernel, Numba, TopK, or scoring formula change.
- No production prediction, pending candidate, database, or runtime-state mutation.
- No Feature Compiler replacement for `component_tile`.

## What changed

- Added `dehps.input_contracts.feature_contract`.
- Defined the 32-component feature manifest with stable `index`, `feature_id`, `weight_field`, dtype, shape, dependency, formula, and missing-value policy.
- Bound the component order to the existing scoring kernel component order and `CONFIG_WEIGHT_FIELDS`.
- Added a real 32-value golden vector for a fixed four-draw history and candidate `[3, 8, 12, 18, 25, 33]`.
- Added `FeatureContractVerifier`, which rejects component-count, index, duplicate-id, duplicate-weight, dtype, shape, finite-value-policy, and digest drift.
- Documented the Feature Contract separately from future Feature ABI work.

## Contract boundary

Feature is defined as:

```text
Feature = F(WindowArtifact, CandidateABIPackage)
```

This round freezes meaning and order. It deliberately does not create the machine Feature ABI layout. Kernel backends still use the current `component_tile` path.

## Validation

Focused validation:

```bash
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_feature_contract.py
```

Result:

```text
5 passed in 0.20s
```

Covered:

- component count equals `COMPONENT_COUNT == 32`;
- component weight mapping equals `CONFIG_WEIGHT_FIELDS`;
- manifest carries Window and Candidate dependencies;
- manifest rejects duplicate feature ids and non-finite policy drift;
- golden vector matches current reference `component_tile`.

## Database And Production State

No database migration was added. No production predictions, pending candidates, historical fingerprints, or live runtime state were modified.

