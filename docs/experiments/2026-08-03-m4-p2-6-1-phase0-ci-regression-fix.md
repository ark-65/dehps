# M4-P2.6.1 Phase 0 CI regression fix

Date: 2026-08-03

Role: Engineering Agent

Engineering Request:
`engineering-m4-p2-6-1-phase0-ci-regression-fix-20260803` (Request 244,
Execution 165), approved by an independent Reviewer and parented to the
completed Phase 0 Request 243.

## Round contract

The sole goal of this round was to repair the five failures in GitHub Actions
run `30791235652` without changing the frozen P2.6.1 statistical contract or
touching its live execution. The round was limited to CI Git history, a
Prediction v2 non-interference assertion, control-plane-bound task artifact
paths and replay, pre-side-effect control-plane admission, the narrow
Prediction v2 execution-v1 compatibility exposed by that path fix, focused
tests, and the required immutable Phase 0 evidence cascade.

Non-goals were any estimator, generator, metric, threshold, seed, fold,
replicate, decision-policy, P2.7, P3, Historical Evidence, promotion, betting,
release, migration, process, service, scheduler, runtime-slot, or production
change. No partial or live P2.6.1 result was read.

## Failure diagnosis and fixes

The original CI result was `5 failed, 2001 passed, 6 skipped`.

1. `actions/checkout` used its default shallow history, so the real
   `git ls-tree` check for frozen baseline commit `70f83a…` failed with exit
   128. CI now uses `fetch-depth: 0`; the baseline check remains real and
   fail-closed.
2. A Prediction v2 isolation test fixed the SHA of the complete M4 manifest.
   That rejected the governed additive Phase 0 task even though Prediction v2
   did not mutate M4. The test now captures the M4 bytes before resolution and
   requires identical bytes afterward.
3. Supervisor artifact validation hard-coded
   `runtime/research-os/mainline/tasks`, rejecting the valid isolated
   `prediction-v2-shadow/tasks` root. The validator now maps only the two
   registered production control planes to fixed namespaces. Unknown control
   planes, cross-plane paths, absolute paths, non-canonical text, `..`, wrong
   task/execution identities, namespace/task/execution-root symlinks, and
   child symlink escape all fail closed. Prediction v2 replay now reuses the
   same digest, registry, provenance, namespace, path, and artifact validator
   as completion recovery instead of directly joining registry paths.
4. Once the path bug was removed, the existing Prediction v2 execution-v1
   schema exposed that it does not embed `registered_artifact_count`. Only for
   the exact Prediction v2 control plane and only when the field is absent,
   Supervisor uses the already digest-verified completed-event count. It still
   requires that count to equal the actual registry length and verifies every
   registration and artifact identity. Changing the old execution-v1 payload
   would have changed its immutable digest under the same execution identity,
   so no silent schema rewrite was made.
5. Unknown control-plane keys are now rejected by Supervisor construction
   before repository initialization, task dispatch, event/registration writes,
   or filesystem output. A zero-side-effect regression test locks this
   admission boundary.

## Immutable evidence cascade

The published Phase 0 nodes were retained rather than overwritten:

- runtime plan chain:
  `c34836c3… -> 5d6eafd3… -> eef5e18f…`
- control-plane manifest chain:
  `830cb10a… -> 4ae6aadb… -> e09aa5e5…`
- previous plan `5d6eafd3…` remains at the v1.1 path
- previous manifest `4ae6aadb…` is archived at source commit
  `b71de485d3251496cff964be0a2251dfa6272e29`

Final runtime-audit plan digest:
`eef5e18f6ffb342f264ef47913892efa91d92dfec0a32a51d2f1d0cb2711cbd5`

Final control-plane manifest digest:
`e09aa5e52f7b21e159fef78d7c0b87666caa09d84ee407fd8161c8b9396169a2`

Final construction source-integrity contract digest:
`afd43b526c4aceeab23f1480b18af00913c4d669d371fb7a83eaea4ac2eeee4c`

The audit orchestration source-set digest changed to
`fe201c394ca5754f6014226f70ff55e3a471e8c85836f7a95ec6815e1be85f2a`.
The shared, acceleration, and independent-oracle source sets stayed exactly
`53bc9f4d…`, `c8d1b26b…`, and `3df0dee1…`. The projected golden source contract
also stayed exactly
`37028c1b92eb16048d0ed4f19148bcd2f0b8ddfbe4a4aaf1cb7444c42b0b13b9`.

## Exact replay evidence

Two accepted runs used independent Python processes, canonical one-thread
environments, and separate fresh `/tmp` directories. Their deterministic
outputs were identical:

- status: `EXACT_GOLDEN_REPLAY_VERIFIED`
- runtime-audit plan:
  `eef5e18f6ffb342f264ef47913892efa91d92dfec0a32a51d2f1d0cb2711cbd5`
- elapsed wall time: 567.081 and 562.292 seconds; timing is not an acceptance
  metric because the runs executed concurrently
- GoldenReferencePlanArtifact:
  `6a588ff29de42e919e6d3562695b019f71593fac05e58e8e8d2ea80729628571`
- Phase0GoldenReferenceFixture.v1:
  `099815046b5417552364954f464ef6868decf991d39de2dc190b84edf3bf6f63`
- GoldenReferenceReplayArtifact:
  `04673d019c18e5454210add7b247470628351dbd7d12ee5531d39ed59f264d80`
- checkpoint journal SHA-256:
  `5ad68b8a9b6e97067d692fdf82f101520e261d2451262591e5ee178b4966db24`
- executor fingerprint:
  `e804e4eedf3c67ad9d35207367a096f6b830a6ab2ac29cc03501392d8430af32`
- 23 frozen inputs; 61 reference folds; 61 observed folds; 45 reference
  boundaries; 45 observed boundaries; 45 equivalence cases

One earlier post-fix calculation completed bundle construction and validation
but its temporary reporting script requested the wrong journal field name and
raised `KeyError` while printing. It was excluded from accepted evidence; both
accepted runs above started from scratch after the reporting script was fixed.

## Validation

- Seven focused security/regression cases passed, covering cross-plane paths,
  non-canonical and wrong-execution paths, child and execution-root symlink
  escape, self-consistent malicious replay registration, missing registry
  entries, narrow execution-v1 compatibility, and zero-side-effect rejection
  of unknown control planes.
- Full Prediction v2 test file: 21 passed.
- Complete affected suite across golden, control-plane, hardening, measurement
  execution, mainline Supervisor, Prediction v2, and replay/status persistence:
  137 passed in 218.59 seconds.
- Full Worker suite in a detached temporary Git worktree containing the final
  Python/config bytes and real Git history but no live runtime: 2010 passed,
  4 skipped, 4 warnings in 495.75 seconds.
- Black check, Ruff `F`/`I`, in-memory compilation of all seven changed Python
  files, and `git diff --check` passed.
- A direct full-suite run in the shared workspace produced 42 legacy-line
  failures because the local ignored retirement activation is already ACTIVE.
  That external state was not changed or deleted. A source-only snapshot was
  also rejected as a validation environment because omitting `.git` changes
  commit provenance to `unknown`; neither run is counted as code evidence.
- Strict plan load, real Git/source preflight, manifest digest, resolver,
  immutable supersession index, unchanged P2.6.1 task identity, and golden
  compatibility checks passed.

## Mainline integration matrix

| Contract element | State after this round |
| --- | --- |
| Goal | Existing `M4_MEASUREMENT_RUNTIME_AUDIT`; no new or competing Goal |
| Task DAG | Existing golden-reference and runtime-audit tasks now consume plan `eef5e18f…` |
| Resolver / Ready Queue | Still `EXTERNAL_WAIT`; no canonical executor or runtime-slot event was added |
| Supervisor | Prediction v2 and the M4-P2.9 strict completion/replay paths bind their exact registered namespaces; unknown Supervisor keys fail before side effects |
| Capability | Golden construction/replay remains wired only through the unified Supervisor |
| Artifacts | New immutable plan/manifest nodes append to, rather than overwrite, published lineage |
| Status | Engineering evidence advanced; Evidence Progress remains 0; production action remains none |
| Replay | Two manual exact replays passed; no canonical mainline execution fact was manufactured |
| Next consumer | Existing `m4-p2-9-measurement-runtime-audit`, still waiting on canonical executor and later runtime-slot release |

The code and evidence chain are validated for this CI fix, but the broad
capability has not executed through the canonical mainline Ready Queue and
physical replay path. Therefore its governed completion classification does
not advance beyond integration pending.

NO — INTEGRATION_PENDING.
