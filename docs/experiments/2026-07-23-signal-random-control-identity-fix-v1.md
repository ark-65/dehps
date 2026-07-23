# Signal diagnostic random-control identity fix v1

## Round contract

- Role: Engineering Agent
- Agent Request: `engineering-fix-signal-random-pool-identity-v1-20260723`
- Request id: `199`
- Execution id: `120`
- Primary goal: make matched and uniform random controls invariant to display
  labels and identical for equivalent candidate pools.
- Non-goals: no score, rank, model, feature, Top70 budget, bootstrap, evidence
  interpretation, production, or Promotion Gate change.

## Reproducer

The first 60-target Operator run produced snapshot
`252cb5abd145ce914f5bbf37d0dab2a94e367c4ce33ace90f654462fb7f100a9`.

`full_model` and `fixed_minimal_linear` had the same configuration digest and
identical rankings, but their matched-random mean best-red values differed:

```text
full_model            3.1020833333
fixed_minimal_linear  3.0604166667
```

The RNG derivation included `arm_label`. A display name therefore changed the
control tickets even when the scored candidate pool was identical. Operator
execution `119` was formally failed, and the artifact was preserved but marked
inadmissible.

## Fix

Matched-score-pool control identity now binds:

```text
seed digest
+ target issue
+ control kind
+ SHA-256(canonical ordered Top-pool candidate ids)
```

Uniform-legal control identity binds:

```text
seed digest
+ target issue
+ control kind
+ full legal universe identity
```

No arm label enters either RNG stream. Control rows now record the pool sequence
digest and universe identity.

## Verification

The full-legal-space one-target regression smoke showed:

```text
full_model.random_controls == fixed_minimal_linear.random_controls
static_structure_only.random_controls == without_all_dynamic.random_controls
```

Both comparisons were byte-identical. Their matched-random means were also
identical (`3.0` and `2.625`, respectively).

Validation:

- focused signal and legacy-ablation tests: `12 passed`;
- full worker suite: `1558 passed, 4 skipped`;
- one-target full-legal-space live regression smoke: completed;
- failed 60-target artifact retained; no evidence submission or interpretation;
- `promotion_allowed=false`.

The accepted fix requires a fresh certified tool identity and a new Operator
request before rerunning the 60-target diagnostic.
