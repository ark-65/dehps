# M4 Measurement-v2 Repair-v2 Preregistration — Round 49

## Primary goal

Freeze and integrate the singular Repair-v2 execution contract so completed
children are restored from one compact index and skipped without regeneration
or duplicate validation.

## Non-goals

- Do not execute any of the 131,072 future children.
- Do not alter the estimator, fixtures, alpha, Wilson gates, sample size, or
  Round 47 `REPAIR_MEASUREMENT_SYSTEM` decision.
- Do not scan physical checkpoint trees, regenerate raw/sentinel results, read
  a database or CSV per child, or create a second completion path.
- Do not read historical outcomes, create Evidence, promote Prediction-v2,
  open P3, or perform a production prediction action.

## Frozen no-duplicate execution contract

The future workload remains exactly:

| Work | Count |
| --- | ---: |
| Matched reference children | 116,736 |
| Evaluation children | 14,336 |
| Total children | 131,072 |
| Shards | 2,048 x 64 |
| Generated sequence issues | 291,110,912 |
| Outer evaluation issues | 173,146,112 |

Reference identities bind the preregistration digest, lane, null family, scale,
evaluation index, and reference index. Evaluation identities bind the
preregistration digest, lane, cell, scale, and evaluation index. Worker and
shard placement never enter a seed or child identity.

The future runner must load the compact completion index exactly once. A child
whose registered completion and artifact identity match is skipped without
generation, statistical recomputation, sentinel work, or validation. A missing
or mismatched completion fails closed. Every new child may be dispatched at
most once per execution. Replay reconstructs registered aggregate content only.

This round itself executes zero formal children, generates zero issues, reads
zero compact indexes, and performs zero duplicate validations.

## Statistical boundary

The matched 19-reference block and conservative
`(1 + count(reference >= evaluation)) / 20` p-value are unchanged. Each of the
14 cells retains 1,024 evaluation indices and the frozen Wilson gates. The
six-control false-REPAIR claim remains the assumption-free union bound
`0.004767112426180425`; no cross-cell independence claim is made.

An IID reference block may serve IID alternative cells only at the same scale
and evaluation index. It cannot cross an evaluation index, scale, or nuisance
family.

## Gauss–Riemann cross-review

### Gauss pass

The arithmetic is exact: `3 * 2 * 1024 * 19 = 116736`,
`7 * 2 * 1024 = 14336`, and `131072 / 64 = 2048`. Identity domains and index
bounds are explicit and fail closed. The familywise statement uses only the
union bound.

### Riemann pass

The execution geometry preserves family, scale, and evaluation-index strata.
It does not flatten dependent score laws or let process topology alter the
statistical object.

### Disagreement

Sharing an IID block across same-index IID alternative cells introduces
cross-cell dependence. It is allowed for compute reuse but cannot support an
exact joint-binomial or all-cell independence assertion.

### Smallest shared conclusion

Canonical child identity plus load-once compact resume removes duplicate work
without weakening the matched-null statistical contract.

### Next verification

Implement the formal health runner against this preregistration, then verify at
least one real completed shard and one restart in which matching children are
skipped with no regenerated work.

## Validation

- Ruff: passed.
- New preregistration tests: 6 passed.
- Adjacent Repair-v2 tests: 45 passed.
- M4-v2 foundational groups: 68 passed.
- Full non-retired Worker suite: 2,085 passed, 4 skipped, 6 archived
  completed-lineage nodes deselected. The unfiltered suite has the same 42
  expected failures confined to seven permanently retired legacy three-line
  files and no new failure topology.
- Additive migration dry run against durable manifest
  `a07d2f364c8706ab85b874350ddaa1c5e6d5af49741f1ae15a422d1b54969b0c`:
  one revised preregistration task, one new health-execution task, zero state
  regressions, zero fact deletions, and zero unallowlisted rewrites.

## Mainline integration matrix

| Binding | Round 49 status |
| --- | --- |
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` |
| Resolver | Preregistration depends on the immutable, replay-verified Round 48 design |
| Ready Queue | Preregistration is the singular next executable M4 task after migration |
| Supervisor | `M4MarginalStaticRepairV2PreregistrationCapability` registered |
| Capability | Zero-work deterministic preregistration artifact builder |
| Artifacts | Workload/seeds, inference/gates, preregistration, completion, mainline execution |
| Status | Projects load-once resume, skip semantics, and the formal execution consumer |
| Next Task | `m4-v2-marginal-static-measurement-repair-v2-health-execution` |
| Replay | Rebuilds and byte-compares registered aggregate contracts with zero child work |

Final integration answer at code-review time:

`NO — INTEGRATION_PENDING`

The answer becomes `YES — validated by unified mainline execution and replay`
only after the merged commit is migrated, executed, registered, and replayed by
the canonical supervisor.
