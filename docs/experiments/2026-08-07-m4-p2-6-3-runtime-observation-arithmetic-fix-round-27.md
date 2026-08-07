# M4-P2.6.3 Runtime Observation Arithmetic Fix — Round 27

Date: 2026-08-07

Role: Engineering Agent

Agent Request: `engineering-m4-p263-runtime-observation-arithmetic-fix-round-27-20260807`

Request / execution: `295 / 216`

## Primary goal

Fix the live P2.6.3 Runtime Audit failure caused by a stale P2.6.1 fit-rate
literal, while preserving the immutable failed execution and audit plan and
publishing a distinct retry identity.

## Non-goals

- No model, probe, feature, fold, seed, estimator, resampling, threshold, Gate,
  Evidence, or research-conclusion change.
- No statistical result payload read and no P2.6.1 result/checkpoint reuse.
- No edit or retry of the immutable v1.1.6 plan, failed execution, or completed
  compatibility/golden artifacts.
- No live import, Supervisor restart, Prediction v2 promotion, or production
  cutover in this Engineering round.

## Live failure evidence

PR #263 merged as commit
`ff5745fcf6b1ab67f41a258f606b6c28fe85aeda`. Operator Request 294 imported an
additive manifest with zero Goal/Task/Fact deletion, zero state regression, and
zero unallowlisted definition rewrite. The merged Supervisor then produced:

| Task | Execution | Result |
| --- | --- | --- |
| P2.6.3 compatibility acceptance | `d885fc3e9b3c5fd5fe51824b0cb60cf43cdc400afe28066b909b3e50af764596` | `COMPLETED` |
| P2.6.3 golden-reference freeze | `2af22766e803e8b6fc2a32ee6eaa21f71ca9f466ad366992fdc1306a6f2339bb` | `COMPLETED` |
| P2.6.3 runtime audit v1.1.6 | `a63ad3c8a71f11cc4dd0db790c9acaa308e85918cb45cad4e66e547b5e4663fc` | `FAILED` |

Failed event:
`349f21c339fe3acc24bda93e03297b2744c87e2cca1fd9f48b2ab25c15c74b87`

Error:

```text
runtime audit observation arithmetic changed
```

The measured observer and the structural validator both declare `fit_count =
64`. The observer computes `fits_per_second = fit_count / wall_time_seconds`,
but the arithmetic validator still compared the value against the superseded
P2.6.1 literal `244 / wall_time_seconds`. The failure occurred after the
measured 61-fold evaluation and before runtime artifacts were committed. It did
not alter the completed 31,000-replicate execution.

## Fix and immutable supersession

The arithmetic check now derives the rate from the already structurally
validated `fit_count`. A regression test builds an exact 61-fold, 64-fit,
4,000-resample observation, verifies it passes, then recomputes a valid artifact
digest around the stale `244 / wall` value and verifies the arithmetic boundary
still rejects it.

| Identity | Digest / key | State |
| --- | --- | --- |
| Runtime Audit v1.1.6 | `ccbed31f36ad9486f5489d5827c6456d1853259eaeb1ab7a61077347c7e06056` | immutable, loadable, superseded |
| Runtime Audit v1.1.7 | `8c97fd5fdc006cba6a4145dbd56acc566b9507e18279d06437d0aa472adb2cd2` | current arithmetic-fix plan |
| Failed runtime task | `m4-p2-9-p263-measurement-runtime-audit` / `1e0033856ecd69803e861129e80e7d94180b819481353205640f53cb7b3d9e59` | `SUPERSEDED` |
| Retry runtime task | `m4-p2-9-p263-runtime-observation-arithmetic-fix` / `d2c81c1afc0986ff48130d745269c57ba809c69ea29267d9c290f09e4026490f` | distinct `INTEGRATION_PENDING` identity |

The completed v1.1.6 golden execution is not copied or rebound. The v1.1.7
runtime task may consume it only after the existing golden completion fact and
`require_golden_source_compatibility` prove that shared/oracle source identity
is unchanged. The only source difference is in audit orchestration.

## Duplicate checkpoint validation boundary

The Round-23 change remains intact: completion assembly performs one complete
checkpoint-journal verification per replicate. This fix does not add another
journal replay and does not weaken recovery continuity, tamper rejection,
artifact-commit validation, or source/equivalence attestation.

## Validation

Focused validation before clean full CI:

```text
163 passed, 1 failed in 107.57s
1 passed (artifact-index correction)
3 passed (final arithmetic, v1.1.6/v1.1.7, and status projections)
Ruff: passed
git diff --check: passed
generator replay: stable
```

The single intermediate failure was an artifact-index representation error:
the newly superseded `07ef...` control-plane manifest initially still pointed
at the mutable current path. It now uses merged commit `ff5745f...` plus
`path_at_source`, matching every earlier immutable historical manifest.

Full clean-worktree Worker CI, with an absolute worktree-local `PYTHONPATH`:

```text
2048 passed, 4 skipped, 4 warnings in 203.19s
```

The warnings are the same pre-existing Python 3.14 multiprocessing `fork()`
deprecation warnings in training-supervisor parallelism tests. There are no
test failures.

## Mainline integration matrix

| Required link | Current evidence | Status |
| --- | --- | --- |
| Goal | existing live M4 Runtime Audit Goal | live |
| Resolver | failed task superseded; retry dependencies unit-verified | source complete |
| Ready Queue | retry waits completed golden, compatibility, executor, and v1.1.7 | source complete |
| Supervisor | arithmetic-fix capability registered | source complete |
| Capability | exact regression passes | live retry pending |
| Artifacts | v1.1.6 retained; v1.1.7 and index lineage frozen | source complete |
| Status | failed task supersession and retry task projected | source complete |
| Next Task | runtime bottleneck review | declared |
| Deterministic replay | compatibility and golden live replay completed | runtime retry pending |

Final integration answer:

**NO — INTEGRATION_PENDING**

After merge, a new Operator request must additively import only v1.1.7 and the
retry task, preserve the completed compatibility/golden facts, start the merged
Supervisor, complete the new audit execution, and replay the committed runtime
artifacts. Prediction v2 promotion remains forbidden.
