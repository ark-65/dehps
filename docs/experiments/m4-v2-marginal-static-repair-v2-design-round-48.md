# M4 Measurement-v2 Repair-v2 Design — Round 48

## Primary goal

Freeze and integrate a second measurement-repair design that corrects the
exchangeability and shared-calibration defects diagnosed after the Round 47
`REPAIR_MEASUREMENT_SYSTEM` decision.

## Non-goals

- Do not execute any new formal replicate.
- Do not regenerate any prior raw, compact-index, sentinel, or fold result.
- Do not read historical outcomes or create prediction evidence.
- Do not alter the estimator, fixtures, alpha, Wilson gates, or Round 47
  decision.
- Do not authorize Prediction-v2 promotion or any production action.

## Frozen design

The old repaired-health program calibrated every score law from an IID null
pool and reused a calibration pool across evaluation indices. That does not
justify exchangeability for the T1/J1 dependent nulls or independent binomial
counting across evaluation replicates.

Repair-v2 freezes three matched null families at both scales:

| Fixture | Calibration null family |
| --- | --- |
| NULL and M1 | `IID_UNIFORM` |
| T1 | `T1_MARKOV_STATIONARY` |
| J1 | `J1_WITHIN_DRAW_IS4` |

Each evaluation index receives its own 19-reference matched block. The frozen
conformal p-value is `(1 + count(reference >= evaluation)) / 20`; ties are
conservative and a block may not be reused across evaluation indices.

The presample gate uses 1,024 evaluation replicates per cell. Wilson upper
`<= 0.09` accepts at most 74 detections. Under the exact `p=0.05` boundary,
the per-control false-repair probability is at most
`0.0007945187376967374`; the six-control union bound is
`0.004767112426180425`, below the frozen `0.005` familywise limit.

## Duplicate-work removal

The design and status contract freeze:

- `compact_index_direct_resume=true`;
- `recursive_checkpoint_scan=false`;
- `raw_replay=false`;
- `sentinel_replay=false`;
- `duplicate_validation=false`;
- no nested bootstrap;
- no database or CSV access per replicate.

Completed shards will therefore be selected from the compact completion index
and skipped. A result is generated once and consumed once; deterministic replay
checks immutable registered artifacts and does not regenerate the statistical
workload.

This round itself executed zero replicates and generated zero issues. The future
preregistered budget is 131,072 replicates in 2,048 shards of 64, with
291,110,912 planned generated issues. Those numbers are a future execution
budget, not work performed in this round.

## Gauss–Riemann cross-review

### Gauss pass

The legal sample space remains `C(33,6)=1,107,568`. The exact binomial boundary,
Wilson threshold, probability arithmetic, seed separation, null-family mapping,
and no-duplicate-work invariants are explicit and machine checked.

### Riemann pass

The null geometry is no longer flattened into one IID score distribution.
Calibration is stratified by dependence structure and scale, and independent
reference blocks preserve the local score law for every evaluation index.

### Disagreement

Reusing an IID reference block across alternative cells may be computationally
convenient, but it cannot be used to claim cross-cell independence. The frozen
negative-control familywise proof therefore relies only on fresh blocks across
evaluation indices; it does not infer additional independence from alternative
cells.

### Smallest shared conclusion

The prior repaired-health result remains `REPAIR`. A new sample is admissible
only after this independent-block, matched-null design has been integrated and
preregistered in the unified mainline.

### Next verification

Freeze the Repair-v2 execution/preregistration artifacts, then implement compact
index resume with exact shard uniqueness before authorizing the 131,072-replicate
program.

## Validation

- Ruff: passed.
- Repair-v2 targeted and adjacent mainline tests: 124 passed.
- Full non-retired Python suite: 2,085 passed, 4 skipped. The 42 failures in
  the unfiltered suite are confined to seven intentionally retired legacy
  three-line test files; their production entry points correctly fail closed.
- Additive migration dry run: one revised task, one new downstream task, zero
  state regressions, zero fact deletions, zero unallowlisted rewrites.

## Mainline integration matrix

| Binding | Round 48 status |
| --- | --- |
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` |
| Resolver | Repair-v2 design depends on the immutable Round 47 REPAIR fact and source fact |
| Ready Queue | Design becomes the singular next executable M4 task after migration |
| Supervisor | `M4MarginalStaticRepairV2DesignCapability` registered |
| Capability | Zero-work deterministic design artifact builder |
| Artifacts | Presample feasibility, Repair-v2 design, completion, mainline execution |
| Status | Projects Repair-v2 design and its preregistration consumer |
| Next Task | `m4-v2-marginal-static-measurement-repair-v2-preregistration` |
| Replay | Rebuilds and byte-compares registered design artifacts without statistical recomputation |

Final integration answer at code-review time:

`NO — INTEGRATION_PENDING`

The answer becomes `YES — validated by unified mainline execution and replay`
only after the merged commit is migrated, executed, registered, and replayed by
the canonical supervisor.
