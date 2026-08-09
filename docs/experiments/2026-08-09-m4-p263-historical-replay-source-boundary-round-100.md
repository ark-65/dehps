# M4-P2.6.3 Historical Replay Source Boundary — Round 100

Date: 2026-08-09

Role: Engineering Agent

Agent Request: `engineering-m4-p263-historical-replay-source-boundary-round-100-20260809`

Request / execution: `427 / 348`

## Primary goal

Make the frozen P2.6.3 golden-reference and arithmetic-correct Runtime Audit
executions replay with the exact Git commit recorded by their immutable
execution artifacts, while preserving the strict current-source boundary for
fresh capability execution.

## Non-goals

- Do not modify either frozen source plan, fixture, event, execution artifact,
  registration, digest, statistical contract, or historical result.
- Do not weaken source-integrity checks for a new golden or Runtime Audit
  execution.
- Do not change a model, feature, estimator, fold, seed, metric, threshold,
  Evidence rule, Gate decision, Prediction v2 state, promotion state, or P3
  readiness.
- Do not dispatch training, consume historical outcomes, or assemble replay
  inputs manually.

## Failure classification

Current merged-main Supervisor replay of the completed P2.6.3 golden task
failed with:

```text
SourceIntegrityError:
audit_orchestration_source_modified:
apps/worker-python/dehps/research_os/information_theory/
measurement_system_v2/__init__.py
```

This was not evidence corruption. The completed execution is pinned to commit
`ff5745fcf6b1ab67f41a258f606b6c28fe85aeda`, but current replay reconstructed
its frozen physical audit with later merged source bytes. The same temporal
source-selection error applied to the arithmetic-correct Runtime Audit at
commit `142e533ec00f3e29c61faec4a1ea5813a1123e3d`.

Before implementation, isolated manual replays at both execution commits
verified that the immutable runtime artifacts and registrations remained
intact. Therefore the smallest valid repair was to select the execution-time
source boundary, not to update any frozen expected identity.

## Implementation

Historical delegation is allowlisted to exactly two canonical tasks:

- `m4-p2-9-p263-golden-reference-freeze`
- `m4-p2-9-p263-runtime-observation-arithmetic-fix`

After the current Supervisor has loaded and verified the unique completed
event, execution artifact, registry count, and registered artifact paths, it:

1. validates the execution artifact's 40-character Git identity;
2. requires that commit to be an ancestor of current `HEAD`;
3. creates a detached temporary worktree at that exact commit;
4. binds the current immutable `runtime` root read-only by replay convention;
5. runs the historical canonical Supervisor replay with deterministic numeric
   thread settings;
6. accepts only one `REPLAY_VERIFIED` JSON result with exact control-plane,
   task, execution, execution-artifact, registry-count, and capability-replay
   identities;
7. removes the runtime link and temporary worktree on success or failure.

If the recorded execution commit equals current `HEAD`, delegation is not
used and the current in-process capability replay remains authoritative. New
execution still performs its existing current-source preflight and source
integrity audit. This preserves both requirements:

```text
historical execution -> execution-time source -> immutable artifact replay
fresh execution      -> current source         -> strict source preflight
```

## Result blindness and scientific boundary

The change selects code provenance only. It does not expose historical draw
outcomes or statistical results to either capability. The replayed artifacts
continue to attest:

- `historical_outcomes_read = false`
- `p2_6_1_partial_statistical_results_read = false`
- `p2_6_3_statistical_results_read = false`
- `manual_input_assembly = false`
- Evidence progress unchanged
- production action unchanged

The legal six-number draw space remains equiprobable. This round creates no
predictive claim and supplies no basis for Prediction v2 promotion.

## Validation before publication

Focused lint and regression validation:

```text
ruff format: passed
ruff check: passed
execution-commit replay tests: 2 passed
Supervisor test module: 18 passed in 37.39s
full Worker CI: 2354 passed, 4 skipped, 26 warnings in 266.82s
git diff --check: passed
```

The regression tests prove deterministic environment binding, historical
worktree selection, exact identity acceptance, identity-drift rejection, and
cleanup on both the success and fail-closed paths. The 26 full-suite warnings
are the pre-existing Python 3.14 multiprocessing `fork()` deprecation warning;
there were no test failures. The ignored live Prediction v2 activation file
was restored after CI with its original SHA-256 identity
`711fc6149b0eefea99a19c4591b82a9b5a9513c7c1449c8152f13025f7f4f9af`.

Real durable-control-plane replays from the unmerged Engineering checkout:

| Task | Folds | Execution | Execution artifact | Registrations | Result |
| --- | ---: | --- | --- | ---: | --- |
| P2.6.3 golden reference | 122 | `2af22766e803e8b6fc2a32ee6eaa21f71ca9f466ad366992fdc1306a6f2339bb` | `8d4f58daadab78e3fc105550d58a873cf1912915665b639d1ece3ffb95d7e6cd` | 5 | `REPLAY_VERIFIED` |
| arithmetic-correct Runtime Audit | 61 | `8d93e36c180a6336de8adf3b0ddbf7aba23a65930aa81bf83fe6494f2c81e1f6` | `15d81348683123d6f6d2a55984a2c0d15aba559c1097dd449a1525751b79a75d` | 6 | `REPLAY_VERIFIED` |

The golden replay reproduced the same fixture, plan, full replicate payload,
full fold trace, boundary snapshots, checkpoint journal bytes, and replay
attestation. The Runtime Audit reproduced the same registered golden parent,
benchmark plan, source-integrity attestation, equivalence attestation,
benchmark attempt, and runtime observation identities.

The surrounding compatibility execution `d885fc3e...` (4 registrations) and
runtime-slot eligibility execution `ae3d67ba...` (2 registrations) also
returned `REPLAY_VERIFIED` from the same current Engineering checkout. Thus the
repair does not bypass or regress either adjacent canonical replay boundary.

## Mainline integration matrix

| Required link | Engineering evidence | Merged-main proof |
| --- | --- | --- |
| Goal | canonical M4 Goal unchanged | pending |
| Resolver | no task or dependency change | unchanged |
| Ready Queue | no readiness mutation | unchanged |
| Supervisor | execution-commit replay boundary implemented | pending merged source |
| Capability | both historical capabilities physically replayed | pending merged-main Operator replay |
| Artifacts | exact immutable identities retained | pending merged-main confirmation |
| Status | no status or progress mutation | unchanged |
| Next Task | structural-evaluation design remains Ready | unchanged |
| Deterministic replay | real 122-fold and 61-fold replays passed | pending merged-main replay |

Final integration answer for this Engineering round:

**NO — INTEGRATION_PENDING**

Completion requires full Worker CI, ready-PR merge, and a separately approved
Operator execution that replays compatibility, golden, Runtime Audit, and
runtime-slot eligibility from the merged commit. No frozen identity may be
rewritten during that acceptance step.
