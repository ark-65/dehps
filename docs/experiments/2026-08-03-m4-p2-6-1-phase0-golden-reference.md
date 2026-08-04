# M4-P2.6.1 Phase 0 Golden Reference

Date: 2026-08-03

Role: Engineering Agent
Agent Request: `engineering-m4-p2-6-1-phase0-golden-reference-20260803` (request 243, execution 164)

## Round contract

The single goal of this round is to make a frozen, exact, replayable Phase 0
correctness oracle available to the existing `M4_MEASUREMENT_RUNTIME_AUDIT`
mainline. The user authorization was: `另一条任务已经干净并且开发完成，这任务继续`.

Non-goals were enforced: no cache/vectorization/Numba/C/Rust optimization, no
change to the estimand, generator, features, probe models or hyperparameters,
metric, resampling, decision policy, folds, seed domains, workload, or
replicate counts; no live P2.6.1 stop/restart/import; no runtime-slot event; no
partial P2.6.1 statistical outcome read; no Historical Evidence, P2.7, P3,
production, betting, or Promotion Gate action.

## Falsifiable engineering hypothesis

The Phase 0 implementation is acceptable only if all of the following remain
true on the canonical executor:

1. The literal reference and observed backend produce exactly the same full
   FORWARD_61 NULL replicate, including 61 folds, all four probes, all 33
   number-event probabilities and IssueMetric fields, checkpoint/settlement/
   final identities, and UTF-8/LF journal bytes.
2. Replicate 0 first/middle/last fold feature views for NULL plus all four
   injected mechanisms on FORWARD_61, HISTORICAL, and LONG match as complete
   payload digests, including targets and red numbers (45 cases). The plan
   embeds all 45 identities and their domain-separated schedule digest.
3. Every float in the immutable fixture is represented as an exact IEEE-754
   binary64 bit pattern. Any bit, byte, source identity, executor identity,
   artifact, or lineage mismatch fails closed.
4. A production-like measured run has trace capture disabled and is timed only
   through evaluator return. A separate untimed correctness replay captures
   full traces; its result and journal must exactly equal the measured run and
   the registered golden fixture.

The null is that the two implementations differ somewhere inside this exact
contract. A mismatch freezes optimization eligibility; it is not averaged,
tolerated, or interpreted as research evidence.

## Oracle and independence boundary

The effective runtime oracle is the immutable, registered, replay-verified
`Phase0GoldenReferenceFixture.v1`, not a generic evaluator invocation.

- `immutable_golden_fixture_is_oracle = true`
- `acceleration_boundary_independent = true`
- `oracle_construction_fully_implementation_independent = false`

The constructor independently implements outer-fold orchestration,
state-visible feature construction, probe-runtime-cache bypass, replicate
orchestration, scalar permutation PE1 arithmetic, and checkpoint journal
serialization. It intentionally shares the frozen synthetic generator, probe
model core, IssueMetric kernel, bootstrap kernel, block-permutation schedule,
and primary inference kernel. Those shared source files are bound to raw
content SHA-256 and Git blob identities from commit
`70f83a5400c6207cbe3806e69329a233e461e311`; the Phase 0 acceleration,
independent-oracle, and audit-orchestration source sets are separately pinned.
Executable preflight checks current bytes against the plan. A registered source
attestation additionally checks every pinned file against the execution commit;
shared files must also match the frozen baseline commit.

Source identity is deliberately split. Construction and runtime attestations
bind five digests: the complete source contract plus the shared, acceleration,
oracle, and audit sets. Golden equivalence binds only a frozen three-digest
projection: its self-contained contract plus the shared and oracle sets. Thus a
superseding acceleration/audit plan may reuse the registered fixture, while any
shared/oracle/baseline-policy change fails compatibility and requires a new
reviewed fixture. The Phase 0 audit set conservatively pins every remaining
DEHPS Python source plus the canonical runner, service unit, and controlled
event publisher (65 shared, 4 acceleration, 11 oracle, and 369 audit files; no
overlaps). A fresh import of the complete literal golden evaluator loads 65
repository Python files, all in the shared/oracle projection and none in the
acceleration/audit sets. The observed runtime-cache implementation remains
lazy and is not imported by that check.

`acceleration_boundary_independent` means the literal behavioral path bypasses
the acceleration modules and its fresh-import closure excludes them. It does
not mean process isolation: canonical construction still runs inside the
unified supervisor process, whose broader import state may contain the
observed backend. The five-digest construction identity pins that complete
process-side source surface, and
`oracle_construction_fully_implementation_independent` remains false.

The oracle's scope is deliberately narrow. Full statistical equivalence covers
all 61 folds only for FORWARD_61/NULL replicate 0. The 45 cross-scale cases are
first/middle/last feature-payload boundary checks, not full-fold statistical or
splitter equivalence for HISTORICAL or LONG. A future splitter replacement or
full-scale execution engine therefore requires a superseding reviewed fixture;
the 45 boundary cases alone cannot authorize it.

The canonical executor fingerprint is
`e804e4eedf3c67ad9d35207367a096f6b830a6ab2ac29cc03501392d8430af32`.
It binds CPython/build/ABI/binaries, package RECORDs and critical extensions,
plus actual installed file-tree digests for the nine packages used by the
frozen numerical path (NumPy, SciPy, scikit-learn, joblib, narwhals,
threadpoolctl, Numba, llvmlite, and orjson); 21 critical extensions; LLVM
host/codegen identity; sklearn and joblib runtime configuration; loaded system
libraries; NumPy BLAS/SIMD identity; runtime thread pools; the exact numeric
environment; and the process-start hash secret. Numba/llvmlite are
conservatively bound because the metric module imports them, but the repaired
frozen 61-fold workload does not call its Numba exact-native helper.
Import-only optional packages outside the profiled numerical path (pandas,
python-dateutil, six, rich, and charset-normalizer) are not claimed as part of
the exact numerical package set. Exact replay is valid only for the same
canonical fingerprint.

## Mainline integration matrix

| Contract element | Phase 0 state |
| --- | --- |
| Goal | Existing `M4_MEASUREMENT_RUNTIME_AUDIT`; no competing Goal |
| Task DAG | New `m4-p2-9-golden-reference-freeze`; existing runtime audit consumes its task completion and `m4-p2-9-golden-reference:VERIFIED` fact |
| Ready condition | Frozen source identities plus `m4-canonical-executor:e804e4…` |
| Resolver / Ready Queue | Source projection is `EXTERNAL_WAIT`; the canonical event is deliberately absent |
| Runner | Capability is registered only in the unified Research Evidence Supervisor |
| Upstream artifacts | P2.6.1 task/repair/validation/state-visible/synthetic/preregistration/metric/walk-forward/resampling/truth identities and runtime-audit plan |
| Capability | Literal full replicate, preregistered 45-case boundary suite, observed exact comparison, source/executor binding, fail-first attestation |
| Immutable artifacts | Golden plan, Phase0 fixture, replay attestation, source-integrity attestation, and mainline execution artifact |
| Status projection | Resolver reason, required executor event/digest, artifact identities, replay flags, Engineering Progress, Evidence Progress 0, no outcomes/production action before execution |
| Replay | Deterministic physical replay is wired; manual validation is recorded below, but no canonical mainline execution fact was created |
| Next consumer | Existing `m4-p2-9-measurement-runtime-audit`; its later optimization consumer still requires a separate approved request/task |

The existing P2.6.1 task objects and frozen task digest
`80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa`
remain byte-for-model unchanged. No live state or result was imported.

## Validation evidence

Final runtime-audit source plan digest:
`5d6eafd399bc6a0fc87a2fa0fce4830824776194566aab4a8ab2299379646aff`

Final source control-plane manifest digest:
`4ae6aadbf1c9df861266c014ab58f4870d84fef4949fd93931a7ccd2c3da1fd8`

Manual canonical single-worker smoke (temporary directories only):

- first construction: PASS in 490.973 seconds; golden plan
  `6e8f9d31adba5c2b4af850295b05dd9c52db4131c692ad76ab82ae78d837ef2e`
- independent second construction/replay: PASS in 495.992 seconds; exact same
  golden plan, fixture, replay, journal, executor fingerprint, source identities,
  input count, and work counts
- fixture digest:
  `6ee1712f8a213b5a5c6fbbe8bcb2494213f1d79277b4658c8c2c5a0609d0f0d0`
- replay digest:
  `0f7dcf6891df9c4c1de46e9c96ed8727a19a10a44ca74f3f5bd50346b1a522cd`
- checkpoint journal SHA-256:
  `5ad68b8a9b6e97067d692fdf82f101520e261d2451262591e5ee178b4966db24`
- complete folds: reference 61, observed 61
- boundary payload cases: reference 45, observed 45

The first pre-fix full smoke failed closed because the observed boundary
snapshot omitted its `replicate_index` identity field. The field is now bound
to the evaluated replicate, a focused crash reproducer was added, and both
accepted full smokes above were executed from scratch after the fix.

Validation commands and results:

- Two separate canonical-environment Python processes invoked
  `_build_golden_reference_bundle`, `_validate_golden_artifact_set`, and
  `_golden_execution_work_counts` in fresh `/tmp` directories with one numeric
  thread and `PYTHONHASHSEED=0`: both returned
  `EXACT_GOLDEN_REPLAY_VERIFIED`; all deterministic identities matched exactly.
- `apps/worker-python/.venv/bin/python -m pytest -q` over
  `test_information_theory_golden_reference.py`,
  `test_information_theory_control_plane.py`,
  `test_m4_roadmap_v2_1_hardening.py`,
  `test_information_theory_measurement_validation_execution.py`, and
  `test_research_os_mainline_supervisor.py`: 105 passed in 148.12 seconds.
- Black check over all 22 changed Python files: PASS. Ruff check over the same
  files: PASS. In-memory compilation of all 22 files: PASS. `git diff --check`:
  PASS.
- Strict runtime-plan load plus real Git/source preflight: PASS. Control-plane
  manifest parse/digest, resolver projection, direct artifact-index
  supersession, historical P2.6.1 raw-object equality, fresh-import closure,
  executor fingerprint, and 45-case boundary schedule checks: PASS.

## Operational state and limitations

No canonical executor attestation or runtime-slot event was published in this
round. The guarded additive migration now has a deterministic path to verify
the executor, write a typed attestation and dry-run record, and publish the
exact executor event with the slot-release migration; executing/importing that
path requires a future approved Operator request after live P2.6.1 finishes.

Consequently, source code and manual replay validation can establish
`CODE_COMPLETE`/`INTEGRATION_PENDING`, but they cannot manufacture the
`Goal -> Resolver -> Ready Queue -> Supervisor -> Capability -> Artifacts ->
Status -> Next Task` execution fact. Correctness artifacts create zero
Historical Evidence and no research or production conclusion.

NO — INTEGRATION_PENDING.
