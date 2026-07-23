# Signal negative-control framework v1

## Primary goal

Add three opt-in controls that destroy a declared information link while
preserving the common legal universe, target window, selector, ticket budget,
settlement, and uncertainty contract.

## Controls

### Prior issue-outcome permutation

The control deterministically permutes prior six-red outcomes across the fixed
prior issue/date slots. It preserves history length and the exact multiset of
prior outcomes, then calls `compile_score_config_grid_artifact` with the same
frozen Full configuration.

Destroyed link:

```text
prior issue/date slot -> observed six-red outcome
```

### Prior red-label permutation

The control applies one deterministic bijection over labels 1 through 33 to
every prior draw, without changing the real target draw. It preserves issue/date
order and legal six-red cardinality, then calls the same Full production score
compiler.

Destroyed link:

```text
red-number identity in prior history -> real future red-number identity
```

### Random score

The control assigns a deterministic unique random order to all 1,107,568 legal
six-red candidates. It then uses the same rank tie policy, Top70 selector,
matched and uniform controls, settlement, and series-identity bootstrap.

Destroyed link:

```text
model features -> candidate score
```

## Interface

The controls are disabled by default. Enable them with:

```text
run_signal_diagnostics.py --include-negative-controls
```

Each target records:

- the destroyed linkage and preserved invariants;
- a canonical transformation digest;
- source and transformed history fingerprints where applicable;
- the production Full-score artifact digest for both history controls;
- the downstream scoring-path declaration for random score.

The real target draw is never transformed.

## Validation

Focused tests cover deterministic replay, issue-slot and outcome-multiset
preservation, the 1..33 label bijection, legal transformed draws, and unique
read-only random scores.

A one-target full-legal smoke for issue 2026083 produced snapshot:

```text
1ea91f150fd9d66d1d2e362e639c4f9b0fa20669f0e11500cbc2863f7d309b72
```

The smoke verified both history controls used
`compile_score_config_grid_artifact`, all three controls used the common
downstream diagnostics, the actual target remained unchanged, and the snapshot
digest covered all metadata. All eight pre-existing arm rows for target 2026083
were byte-identical to the accepted pre-change snapshot, confirming the opt-in
path does not alter existing diagnostics.

## Non-goals

- No predictive feature, model, weight, selector, or objective was added.
- No existing artifact was overwritten.
- No research conclusion or hypothesis transition is produced.
- `promotion_allowed` remains false.
