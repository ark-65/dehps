# M4-v2 Mainline Canonical Fields and Additive Recovery

## Primary goal

Make the already frozen M4-v2 eleven-task route consumable by the canonical
mainline contract without changing science: replace the two legacy integration
field names, preserve the failed Marginal identity execution, and introduce one
new immutable recovery task key.

## Authorized change

- The failed task `m4-v2-marginal-static-historical-identity-adoption` remains
  immutable and queryable with its original definition, execution, and
  started/failed events.
- The active definition uses
  `m4-v2-marginal-static-historical-identity-adoption-recovery-v1` and retains
  the original capability, dependencies, registration order, and terminal fact.
- The remaining ten active tasks are same-key additive revisions.
- All eleven active definitions use only `downstream_consumer` and
  `evidence_progress_rule`; `next_consumer` and `evidence_rule` are absent.
- Global routing binds the exact four-route canonical JSON string. Unknown
  routes fail closed, and only `ADAPTIVE_RESEARCH_ELIGIBLE` names the inert P3
  preregistration consumer.

## Frozen recovery boundary

| Item | Frozen value |
|---|---|
| Input manifest | `94f7e6448fa1572802a050129d09c8bd679772afc62f31f0d1dc2544d098c58a` |
| Input snapshot | `85be3d0edf17b94510d68da6b5b8bfe1c73583222a8bc2822cb7e46bee08f4e3` |
| Input Ready queue | empty |
| First output Ready | `m4-v2-marginal-static-historical-identity-adoption-recovery-v1` |
| New keys | 1 |
| Same-key revisions | 10 |
| Predictive-P3 folds | 0 |

The pure builder checks this boundary before emitting bytes. Repository import
also locks the current control-plane row and verifies the exact result-blind
failed definition, state, execution, capability, source manifest, and ordered
started/failed event metadata before its first write. Missing, extra, reordered,
or substituted lineage aborts the same transaction. Import remains a separate
all-or-nothing Operator action; this Engineering execution did not import a
manifest or run the Supervisor.

## Integration matrix

| Link | Engineering evidence | Mainline status |
|---|---|---|
| Goal → Resolver | Exact recovery input and canonical task definitions tested | CODE_COMPLETE |
| Resolver → Ready Queue | Pure resolution yields the unique recovery task | CODE_COMPLETE |
| Ready Queue → Supervisor | Recovery key dispatch and parent lookup wired | INTEGRATION_PENDING |
| Supervisor → Artifacts | Original terminal/artifact compatibility identity retained | INTEGRATION_PENDING |
| Artifacts → Status | Canonical validator/projector binds the recovery completion fact | INTEGRATION_PENDING |
| Status → Next Task | Canonical downstream consumer chain frozen | INTEGRATION_PENDING |
| Deterministic replay | Code path and identities covered by tests | INTEGRATION_PENDING |

## Non-goals and result

No threshold, estimator, artifact schema, registration order, scientific
failure rule, branch result, or route rule changed. No Supervisor, workload,
replay, routing, P3, P4, Promotion, or production action ran. Predictive-P3
folds remain exactly zero.

`NO — INTEGRATION_PENDING`

The next consumer is a separately approved Operator import and unified-mainline
run from the frozen recovery manifest boundary.

## Four live source-envelope mechanical reseal and marginal replay recovery v1

1. The result-blind baseline is manifest
   `1331950e7f2c74ee8db22bb3383d1defb241b4bee0253d2fedbb8cde065cb470`,
   snapshot
   `d76b4200d439309c5a0b9c9ac1bb42b22649d3be182e996873ad8825fbaecd50`,
   and an empty Ready queue. The prospective five-file workspace material and
   binary-diff digests are `920dea92e74b9f25ec00532b3168401e5ce2bc42e32bf41bec6e178632856eaa`
   and `d9ed117774dff0af2b705ba0fdfb6610f608700a3167a1a1dda8514dca0e6a29`.
2. `migration.py` moves from `5319921d19e70305478348b077068cdd722274d0ffdafba8463562a6e1213d03`
   to `9456104df0d241c1376ae6c41971eee2443c09edb463da7e866685da6a5ab6b4`.
   The immutable failed replay still binds input `44b0c436e3b2c2e5d73c14db55d19db3fefb56877a415e71ef53ef078893da25`;
   only its recovery successor receives the live source digest.
3. Marginal reseals from raw/source-set/artifact
   `3a797411afaecebb014780d046bed71beb69978b7ac087eeb4543af3798ee4f7` /
   `1db37e401b78e674642aefb9207be90ee2f35f3a5907cd76c66a3162d587db10` /
   `44b0c436e3b2c2e5d73c14db55d19db3fefb56877a415e71ef53ef078893da25`
   to `a8edcaf63c98e23cd51d924f7dd8a33b593c92884796643f48640f2cebb60a08` /
   `0657d4d403733e921f11648fa6a37bd32ac62bdfedf13ca2ca86b45501f13981` /
   `f078eed2de707bf1e0ed80495eb9955bd8a909e170fed3318110574f7722e3bb`.
4. Temporal-v3 reseals from raw/source-set/artifact
   `72360714e3c82da8bab27b715d2ab8b627524adbd120855c7b75af01cc0dea99` /
   `0d9bf2e60dfb27322a809b0881f5bc1bedfcde47d6a32066bf1498b86a7d12ae` /
   `658b490f1c3b46c7beafb3f34ec42c58fd2481e92e4a03057de2ff43c070d825`
   to `a0867143a0fbf186c284b228a37ac5d83b2f7a782c63037bfefe9ba827e41883` /
   `ec9509f1cf0ed17036a1bc4a183aa235d81efdb4e479763e5ded2ec775ed28fb` /
   `d266bc0a49b9423871753c25e0c5b97d0fb39c6fad50a02e59fc75e1e5ccfe5a`.
5. Joint-v3 reseals from raw/source-set/artifact
   `33d11e512e146a47e5974f9e8ced894d47fcbbc616a27f70f828e2b0572c70a4` /
   `f3639c43ebd26f6d38a42bea1752297e24a6fd08d67334208e3c07047e224e5d` /
   `596f753ad6c273930c65fee35fde61461eb8a6b102461c083f22c887908598db`
   to `6f819a12cbed273a8ae7fcd8b132d63e1e0eeac3998d6ead55982623d0811b0c` /
   `d8408ccff4263fe51e3a490d258690afa53f15efdf4b863ed761404085b89bcc` /
   `3dc328e7067619967e5cf10333f69749e80b37143bbde8b59beb84ae64abe8a7`.
6. Global reseals from raw/source-set/artifact
   `8df1f3dddd1f7519c6c3f42ba3bbcc504c9eea7ce407f6c58e2fb05d4eab1bbb` /
   `aa48e145a2a058324b5e7a37ec541ddf2925d464e9c99d6b1aa6c026e49ac022` /
   `c8b1e4e50235179339fd95cb7e2af63d3e0616e25e30d689f7afec3019e19e7a`
   to `abb533d6b90c7bca54bd4b4da106274f5958fc45960df8083234b4646fc082c4` /
   `1396cd9ec6ec0bf62c304baebefc21a011e61ba5d403ccb65b5951229a740b6a` /
   `5df45852e589719de889cdd5c08dedc9985b037fb27670354cddcadff20ace66`.
7. The append-only Index links the four current live artifacts directly to
   those prospective artifacts. The four unlanded Request542 candidate
   artifacts are absent.
8. The old failed replay definition, state, execution, ordered started/failed
   events, embedded old task key, and old `44b0…` input remain immutable.
9. The recovery task uses prospective Marginal artifact `f078eed2…` only as
   provenance parent zero; its registered replay fact is unchanged.
10. Evidence raw/manifest/snapshot/length are
    `b3bed258e74f467727a70577051d3e640917f0b461ca887006c2511611e372a3` /
    `e7310b8cb567e2f959aea8d37601309a704cc2c5a8669f868618a84bafc3fa78` /
    `d5ff9a82bedd85281d74e6b799a95a00312c2af0d7ef20994af891f85fe38e31` /
    `342453`; Index raw/length are
    `a9facba65c722c70c2389b205a719631e17aa54d593c0968fda8d809f1120ffb` /
    `70852`.
11. All four source-envelope loaders must validate the resealed bytes before
    any separately authorized live import.
12. Integration matrix: `NO — INTEGRATION_PENDING`.

## Exact frozen recovery-v3 replay-only source resolution

1. Completed Research Request 617 / Execution 503 and approved Engineering
   Request 618 / Execution 504 authorize only
   `EXACT_FROZEN_V3_REPLAY_ONLY_SOURCE_RESOLUTION`. The implementation does
   not create recovery-v4, compatibility-v2, a schema, an artifact type, or a
   general historical-source fallback.
2. The immutable producer remains task
   `m4-v2-global-routing-recovery-v3`, task digest
   `bddceb738009ba18cf81d26453915349ab588ba574d3a24e6ffd5c1bd8e49ab2`,
   execution
   `503c39400e0fc1b285e2600de9baf52e702d28d582e1530db4ed516010df731d`,
   source contract `11cb628f…`, source set `cb48f271…`, and routing source SHA
   `6c676cda…`. Its route artifact `b35a0860…`, route registration
   `69a01c62…`, execution registration `e207fee8…`, and frozen route
   `DEEPER_VALIDATION_REQUIRED` are unchanged.
3. `ResearchEvidenceSupervisor.replay()` now resolves that one parent only
   after the exact approved compatibility successor is present in the running
   `INTEGRATED` stage. It verifies the producer contract and all ten producer
   entries from the pinned Git object `cbb2841b…`; current worktree bytes are
   never substituted for historical bytes.
4. The current parser implementation is independently verified by the existing
   compatibility-v1 source contract. It binds current `routing.py` SHA
   `abe869ee…`, current `supervisor.py`, unchanged `repository.py`, the singular
   compatibility builder, Research 617 / Reviewer Decision 2591, and
   Engineering 618 / Reviewer Decision 2596 / Execution 504. The current
   routing SHA is intentionally different from, and never compared with, the
   producer routing SHA.
5. Activation requires exact parent task, task digest, execution, execution
   artifact, both registration identities and parent digests, source contract,
   successor definition/digest/dependencies/full metric contract, and exact
   result-blind lifecycle identities. The lifecycle gate binds both complete
   Request payloads, execution types and metadata, all existing Decision
   identities, one approval and one execution per Request, and the singular
   Engineering completion transition. Missing, additional, malformed,
   unknown, drifted, or unauthorized identities fail before route parsing; no
   exception is converted into a fallback.
6. The authorized global-routing module passes `93` tests. The focused exact
   source-resolution matrix passes `11` tests covering successful zero-write
   replay, separate old/current source validation, governance payload,
   execution-count, Reviewer and Decision-chain drift, exact successor
   priority/dependency/metric drift, registration drift, producer-source
   drift, compatibility-source drift, and unauthorized-task rejection. Ruff,
   `py_compile`, source-contract reconstruction, historical source
   reconstruction, and `git diff --check` pass.
7. The final local Worker suite passes `2695` tests with `5` existing skips,
   `26` warnings, and zero failures in `1370.55s`. GitHub Actions quota is
   exhausted; by explicit user release policy, these local focused/full gates
   are authoritative and publication proceeds by a ready PR followed by direct
   squash merge without waiting for GitHub CI.
8. This Engineering round performs no import, Supervisor run, replay,
   Marginal/Temporal/Joint/Global Router workload, predictive-P3 fold, P4, or
   Promotion. Integration matrix: `NO — INTEGRATION_PENDING`. After merge, a
   fresh independently reviewed Operator must import the unique compatibility
   successor and invoke only the unified Supervisor replay path once.

## Recovery-v3 registered-replay compatibility successor

1. Completed Research Request 612 / Execution 501 and approved Engineering
   Request 613 / Execution 502 authorize one replay-only additive successor:
   `m4-v2-global-routing-recovery-v3-registered-replay-compatibility-v1`.
   Rejected Request 611 and failed Request 610 / Execution 500 / Decision 2571
   remain immutable and are not retried, modified, or reused.
2. The durable input remains completed recovery-v3 manifest
   `bf2cb25ab0c5ac750655700dc9df230eec3c7bbdf5114fd5349414c2f835f2cb`,
   snapshot
   `e30e18619d60b3ac3e3d361eea50c74db2323ac215f2781bc0255338186ff6ec`,
   Ready `[]`. The existing recovery-v3 task
   `bddceb738009ba18cf81d26453915349ab588ba574d3a24e6ffd5c1bd8e49ab2`
   remains `completed / COMPLETE`.
3. The frozen recovery-v3 execution
   `503c39400e0fc1b285e2600de9baf52e702d28d582e1530db4ed516010df731d`,
   started/completed event digests, route artifact
   `b35a0860e7e2d330513ddf4c0cfee8e1b8a6a59dc24f78bd5d5f55f53daf02db`,
   route registration
   `69a01c62616dc6bae4cb1924a2d1dbf39e6199b94e5de4d9cd14d5965ad48745`,
   execution artifact/registration, parent digests, canonical artifact path,
   raw route bytes, and route `DEEPER_VALIDATION_REQUIRED` are unchanged.
4. The repository keeps the original completed-v3 whole-equality path. A
   separate validator is selected only by the exact approved successor key and
   accepts only the fixed `COMPLETED_V3 -> READY -> RUNNING ->
   COMPLETED|FAILED` automaton. It reconstructs the exact baseline and unique
   successor stages, verifies both old events and registrations column by
   column, verifies the frozen route bytes, rejects successor registrations,
   and rejects every extra task, fact, event, definition rewrite, deletion, or
   state regression. There is no generic additive-manifest entry point.
5. The new source contract is bound to Research 612 / Decision 2577 and
   Engineering 613 / Decision 2582. Its only current source entries are the
   routing parser, repository validator, and pure compatibility builder. The
   builder preserves every existing goal, task, state, and fact, then adds one
   source fact, one authorization event, and one replay-only task. Resolver
   output is exactly one Ready task: the compatibility successor.
6. The routing parser only canonicalizes the already registered artifact's
   exact decision-projection field set before reconstruction. Missing fields,
   unknown fields, non-mapping rows, wrong row cardinality, unknown route,
   digest drift, malformed projection, parent drift, and registration drift
   remain fail-closed. The old artifact bytes and digest are not rewritten.
7. Validation on the frozen implementation tree passes: routing parser/source
   focused tests `10 passed`; complete Global-routing module `83 passed`;
   final replay-compatibility repository focused tests `9 passed`; fresh full
   Worker `2685 passed, 5 skipped, 26 warnings, 0 failed` in `1385.54s`. The
   skips are existing isolated-PostgreSQL conditions. Ruff, `py_compile`, JSON
   parsing, source-contract identity validation, and `git diff --check` pass on
   the same final tree.
8. This Engineering execution performs no durable import, Supervisor run,
   workload, Global Router execution, replay, P3 fold, P4 start, or Promotion.
   After ready PR and distinct PR-head/merged-main Worker successes, a fresh
   separately reviewed Operator Request may import the unique READY manifest,
   record the successor lifecycle, invoke the merged unified
   `ResearchEvidenceSupervisor.replay` exactly once for the frozen recovery-v3
   execution, persist only the approved completion/replay facts, and stop.
9. The frozen route is not `ADAPTIVE_RESEARCH_ELIGIBLE`; successful registered
   replay therefore closes predictive P3 as
   `CLOSED_NOT_AUTHORIZED_BY_GLOBAL_ROUTE`. Predictive-P3 folds remain `0`,
   P4 remains false, and Promotion remains false.
10. Integration matrix: `NO — INTEGRATION_PENDING`. The external post-commit
    PR-head and merged-main CI identities and the future Operator result are
    lifecycle evidence and are not recursively embedded into this committed
    report.

## Global routing recovery v3 exact65 HEAD-fixture source isolation

1. Research Request 598, Execution 489, and Decision 2513 completed the
   result-blind source-isolation contract. Engineering Request 597,
   Execution 488, and Decision 2508 remain failed, immutable, and no-retry;
   Engineering Request 599 and its unique Execution 490 are the sole fresh
   implementation authority.
2. The round adopts the frozen dirty18 bytes
   `e325ca45fb87f4440f11ac0146d759ec140abf4599cb31d78f9c859a2d72870e`
   / `3420`, retains the exact65 allowlist preimage
   `b525fc4d6e170eacc41e4d15c522db4e906682016cae45b36544e9a34ce5af10`
   / `39019`, and extends the inherited exact18 surface only with 46 tracked
   test modules plus one created historical fixture. The baseline material is
   `64d349d11375959f8c87c571eeb04485def937cff6d047fff5a7096d8f9eb155`
   / `12593`.
3. The created fixture
   `apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json`
   is byte-for-byte the Evidence Git object at
   `b6c03ba18e075529505f5107b86f82024602f652`. Its raw identity is
   `7c1974fd61bc15286f32b86371856254d4e68fef32d41289177aaca5974c6b91`
   / `343792`; it parses as `research-os-control-plane-v1` with manifest
   digest `8b6aa2e52b39abdedc00aaeeda348b910713edea778e67693f80a6c4df7955e3`,
   94 tasks, 87 artifact facts, and 15 external-event facts.
4. Each of the 46 legacy-stage test modules changes exactly one frozen
   module-level `MANIFEST_PATH`, `CONTROL_PATH`, or `CONTROL_PLANE_PATH`
   quoted RHS from the mutable canonical Evidence path to that historical
   fixture. Prefix/suffix and zero-context proofs show no other byte changed;
   all aliases resolve the fixture and none resolve the mutable Evidence.
   Imports, helpers, fixture setup, assertions, builders, control flow,
   nodeids, loaders, runtime dispatch, production code, skips, markers,
   fallbacks, and environment behavior are unchanged.
5. The frozen exact71 node set passes 71 tests with zero failures, skips, or
   xfails. The complete 46-module surface passes 484 tests; the inherited
   focused recovery-v3 surface passes 181 tests; and the repository module
   passes 88 tests with the same 4 isolated-PostgreSQL skips. Inherited
   exact18 Ruff, `py_compile`, seven JSON parses, `git diff --check`, and
   per-module baseline-to-final Ruff diagnostic equality all pass with no new
   diagnostic.
6. The fresh full Worker run passes 2661 tests with 4 existing skips, 26
   multiprocessing deprecation warnings, and zero failures in 1039.24
   seconds. No deselection, marker, assertion weakening, or skip increase was
   used.
7. Independent final review freezes the final 65 per-file identities, the
   declared-order final material, the exact raw tracked-plus-two-created
   inclusive diff, all 46 source spans, and this report's identity externally;
   none of those self-referential final digests is embedded here.
8. This Engineering round performs no manifest import, Supervisor run,
   workload, registered replay, production operation, P3 fold/event, P4
   action, or Promotion. Only after exact65 publication and distinct PR-head
   and merged-main Worker CI success may a fresh separately reviewed Operator
   import the unique canonical recovery-v3 manifest once, run the unified
   Supervisor once, stop, perform one registered-content result-blind replay,
   stop, and leave route-dependent P3 unexecuted for fresh Research.
9. Integration matrix: `NO — INTEGRATION_PENDING`. Recovery-v3 remains
   prospective until the separately authorized Operator path completes the
   unified mainline execution and deterministic registered-content replay.

## Global routing recovery v3 exact18 scope recovery

1. Research Request 596, Execution 487, and Decision 2503 completed the
   result-blind target-matrix clarification. Failed Engineering Request 593,
   Execution 484, and Decision 2488, and failed Engineering Request 595,
   Execution 486, and Decision 2498 remain immutable and are neither retried
   nor reused. Engineering Request 597 and Execution 488 are the sole fresh
   implementation authority.
2. The exact18 round adopts the frozen dirty17 bytes, updates only eight stale
   expected-value literals in the first three named control-plane test
   functions, and updates this report. The four functions retain 44 assertions:
   eight expected-value updates and 36 frozen assertions. The fourth function,
   imports, helpers, setup, control flow, historical P2/P5 literals, and every
   byte outside the authorized function envelopes remain unchanged.
3. The pre-update control-plane test identity is
   `05936ef46496856bfa0ff79d7a83b74f469cfc06201711e9446265058fc1b426`
   / `10647`; reversing exactly the eight expected-value updates reconstructs
   it byte-for-byte. The final control-plane identity is
   `53fa81226529bb153b151d3caa2cbdae5633c3096f0dc126ee824f0af78b3784`
   / `10657`. Final F1/F2/F3/F4 function identities are respectively
   `845f8b3b9a95782034362c6432da36be5a011287a5844e36af0560754dfee17b`
   / `1837`, `4055ea3c9b6c83d2910e33651fed8adb14190e77db763c2c7456590550032aec`
   / `944`, `bcbe0c0a760cf5b2b9a306163e9341d3789361a3ec31224ddb88b82615772fc2`
   / `1573`, and `0c7a7400e29d1fb5a8deeb514083d6cbb8223aa181c0ee475a149a08cf250764`
   / `2600`. Bytes outside F1-F3 are
   `cf7ab9aaca78692d2a5689a57260ee786b748ce867e54465b41a28073fa84b7c`
   / `6303` and bytes outside all four functions are
   `ca13e793174719673f38831cbc9e0ef66b7c6fdf8873a0113469b425a9124615`
   / `3703`.
4. The four resealed Marginal, Temporal, Joint, and Global source artifacts are
   `50b84cab26c034819431ec6f1a345808d498144ef2f5c016a0c52b5492e7e81a`,
   `99b32cba51531bde1b69722124a30091199b2ddbd073f5a886ea2d02ff3c6b5b`,
   `f9dfcde1d881c62dbf6cbebc895f88490b478e43278b701aa6779ea817e62fd2`,
   and `11cb628f050f05465676fe083a6f9c183cbf855edfec8e194e98ad0450cdfd64`.
   Global retains ten ordered entries and appends the recovery-v3 builder once
   at ordinal 9.
5. The pure prospective recovery-v3 manifest, snapshot, Ready task, task
   definition, lineage, and dry-run identities are
   `ed48af29b29ce4c7a53f7e700a595c5ff5967901e71fa69166bb2679815b7f8f`,
   `ca5636d335b23495b068cf1a0cad9c900bba83a9830e0690b70846ba262eb99b`,
   `m4-v2-global-routing-recovery-v3`,
   `bddceb738009ba18cf81d26453915349ab588ba574d3a24e6ffd5c1bd8e49ab2`,
   `2bb78ab0feedcc750c6a063dc874e1a1e0ab725dacab2f2fe8a24a6b2175d44c`,
   and `c2cd0fa858b592e3a1f8149d93fa7439d65c10727af78934915ff5769fc1769a`.
   The two dependency-only P3 revisions are
   `4ce1abbb70dc84ffb1efa77e5c56247ef973e0e0fc170986e22ba39dbfe58a1c`
   and `8d541f7f64a1f66cdebf085c4655d029be36e2a510cbe03ff72296661e385bc1`;
   predictive-P3 folds and events remain exactly `0`.
6. Direct control-plane nodes pass 4 tests, the complete control-plane module
   passes 7 tests, the inherited focused surface passes 181 tests, and the
   repository module passes 88 tests with 4 existing isolated-PostgreSQL
   skips. Ruff, `py_compile`, six JSON parses, and `git diff --check` pass. A
   fresh full Worker invocation on the final exact18 tree remains the external
   pre-publication evidence frozen by independent final review.
7. This Engineering round performs no manifest import, Supervisor run,
   workload, registered replay, production operation, P3 fold/event, P4
   action, or Promotion. A future Operator request may be considered only
   after exact18 publication and distinct PR-head and merged-main Worker CI
   success.
8. Integration matrix: `NO — INTEGRATION_PENDING`. Recovery-v3 has not been
   imported or exercised through the unified mainline Supervisor and
   deterministic registered-content replay.

## Recovery-v2 FAILED timestamp normalization and RUNNING live-pointer fixture

1. Completed Research Request 584, Execution 476, and Decision 2445 freeze one
   result-blind repository correction. Approved Engineering Request 587 and
   Execution 479 adopt only the exact four preimages left by failed
   Request 586 / Execution 478 / Decision 2455; those in turn include the
   timestamp-normalization source/test preimages left by failed Request 585 /
   Execution 477 / Decision 2450. Neither failed Engineering execution is
   retried or reused.
2. `PostgresResearchOSRepository` now parses a durable event-row
   `recorded_at` value and its typed-event counterpart only as an aware
   `datetime` or an aware ISO-8601 string, normalizes both to UTC, and requires
   exact instant equality. Naive, timezone-free, empty, unparseable,
   wrong-type, and different-instant values fail through the existing v2
   validation error and precedence. No alias, fallback, latest lookup, new
   transition, or competing validation path is introduced.
3. Relative to repository baseline `50628def…`, the only source deltas are the
   required datetime/UTC import, one closed UTC-normalization helper, and the
   existing started/failed `recorded_at` comparison seam. All other validator
   guards, error codes, evaluation order, and precedence remain unchanged.
4. The live-database compatibility node continues to prove the immutable
   recovery input manifest `03718fe3…`, snapshot `0c9c8dc9…`, and Ready `[]`.
   Separately, it now accepts the legal current RUNNING manifest
   `8d9ed3811969cb80979c51e2c27f451ca2c4b127d59a2c1a9e105127b68bb084`,
   snapshot
   `e60513a5d59644a2cc4aa0cc444bae880caf1af07e39813f6d2e46c9b6cf4086`,
   and Ready `[]`. Its baseline-identical prefix is `965e173b…` / `142731`
   bytes and suffix is `06c9e9fd…` / `128089` bytes; every changed byte is
   inside `test_recovery_input_fixture_matches_live_database_when_available`.
5. Final non-report path identities are repository
   `8f8094073590123a8ac250583417d3d9931116176d4889fd911c44c22a7a0719`
   / `89874`, repository tests
   `88387362b0738a02b26c6b38c4a28517ba24bbc12cf158c15624b4dcfd0121e1`
   / `63364`, and the Global-routing compatibility test
   `aac4d4c5afec65f1cef2606b62289914e546af3d9e11e34a1155654c35a229a1`
   / `272312`. The final review gate freezes this report's post-write identity,
   the declared-order exact4 material preimage, and the exact baseline binary
   diff from the final bytes, avoiding a recursive self-hash claim.
6. The exact live-database node passes once without skip; the eight timestamp
   cases pass; the final combined targeted surface passes 9 tests; the full
   repository module passes 69 tests with 4 existing isolated-PostgreSQL
   skips. The frozen repository plus repository-test Ruff command exits zero.
   The fourth-path baseline/current Ruff JSON outputs are exactly equal at
   `f84acf2e…` / `3598`, each containing only the historical I001 spanning
   lines 1–91 outside the authorized function; that function has no Ruff
   diagnostic. `py_compile`, AST parsing, source-span checks, and
   `git diff --check` pass. The fresh v3 pre-report full Worker run passes
   2636 tests with 4 existing skips, 26 warnings, and zero failures in
   698.06 seconds; the final post-report Worker run is the publication
   evidence frozen by the final review gate.
7. Request 581 / Execution 475, Request 585 / Execution 477, and Request 586 /
   Execution 478 remain failed, immutable, and no-retry. Durable recovery-v2 remains RUNNING/INTEGRATED
   with exactly the existing started and failed events, zero registrations,
   Ready `[]`, and predictive-P3 folds `0`. This Engineering round performs no
   import, Supervisor start, workload, replay, event, registration, route,
   P3 fold, P4 action, or Promotion, and performs no source reseal.
8. After exact4 publication and both Worker CI gates succeed, a fresh
   separately reviewed Operator may import exactly one FAILED terminal
   projection `b50a4c07…` / `527494d7…`, adding zero events and registrations,
   then must stop. Fresh result-blind Research v3 is the only next authority.
9. Integration matrix: `NO — INTEGRATION_PENDING`.

## Global recovery-v2 repository lifecycle transition automaton

1. Completed Research Request 577, Execution 472, and Decision 2422 freeze one
   result-blind repository policy correction.  The singular owner remains
   `PostgresResearchOSRepository._verify_m4_v2_failed_global_routing_recovery_v2_import`;
   generic `import_manifest` calls it before any write, while the unchanged
   Supervisor atomic-completion path reaches the same policy through
   `PostgresResearchOSRepository._verify_mainline_completion_records` after
   typed registrations and the completed event are staged in the same
   transaction and before manifest, task-state, or control-plane writes.
2. The finite policy accepts only exact INPUT idempotence; INPUT → READY;
   READY idempotence; READY → RUNNING; RUNNING idempotence with zero events or
   one canonical started event; RUNNING → COMPLETED; COMPLETED idempotence;
   RUNNING → FAILED; and terminal FAILED idempotence.  Every skip, regression,
   unknown stage, nonidentical repeated stage, alias, fallback, owner,
   cardinality, ordering, status/classification, fact, task, or science drift
   fails before its protected write boundary.
3. READY remains manifest
   `1cc4ebf7a458ecaf6eba3e3a8079012318a2bf7354cb4b3f9770dcfa9ddbe84d`,
   snapshot
   `93907aa79561e6e9929f5211703180f6d0619caa72b930086e473f0b0b5a2e56`,
   and unique Ready `m4-v2-global-routing-recovery-v2`.  RUNNING is manifest
   `8d9ed3811969cb80979c51e2c27f451ca2c4b127d59a2c1a9e105127b68bb084`,
   snapshot
   `e60513a5d59644a2cc4aa0cc444bae880caf1af07e39813f6d2e46c9b6cf4086`,
   Ready empty, and exactly the task-37 status and completion-classification
   changes.
4. COMPLETED is intentionally dynamic: the repository derives it from the
   canonical RUNNING manifest and cardinality-one typed execution identity,
   ordered started/completed events, the exact Global route and execution
   registrations, registered route identity, and only the matching
   mainline-completion, Global-completion, and route facts.  The repository
   independently recomputes the completed event's
   `dehps.m4.v2.mainline-publication-batch-identity.v1` digest from the exact
   RUNNING head, task/execution/git owners, and ordered route/execution
   registration artifact/path pairs; an internally self-consistent event with
   a different batch digest fails closed.  The repository
   reads no route or execution artifact payload bytes; the unchanged
   Supervisor remains the one canonical constructor, atomic publisher,
   postcommit typed readback owner, and deterministic replay owner.
5. FAILED is manifest
   `b50a4c07ee75cd9e87842b8ad62846b6c37af23a17a9fc71e1e3610ce2e8c319`,
   snapshot
   `527494d7827f5160b844b8025c98acf420a135e8811a93157e4adca7ab509369`,
   Ready empty, and exactly task-37 status `running → failed` while
   classification remains `INTEGRATED`.  It requires exactly the ordered
   started/failed events with one owner and git commit, zero registrations,
   and zero new completion, route, mainline, P3, P4, or Promotion facts.
   FAILED is terminal and cannot be retried, replayed, reset, completed, or
   superseded by this policy.
6. Generic rejection leaves the current canonical head unchanged.  Atomic
   COMPLETED rejection rolls back its same-transaction staged registrations,
   completed event, manifest, task-state, and control-plane writes.  The
   failed event and FAILED-manifest import remain separate transactions: an
   unexpected later manifest-write failure preserves the durable failed event
   and prior RUNNING head, requires services to stop, forbids retry, and
   requires fresh result-blind Research; no cross-transaction rollback is
   claimed.
7. All twelve pre-existing Global recovery-v2 guard codes and their precedence
   remain exact.  `m4_v2_global_recovery_v2_output_changed` is reserved for
   finite-stage or canonical-projection mismatch.  Frozen input, old
   recovery-v1 definition/state/events, strict Global source, branch replays,
   lineage, task order, snapshot, and both dependency-only P3 revisions are
   checked on every applicable stage.
8. The complete repository focused surface passes 61 tests with 4 existing
   isolated-PostgreSQL skips.  The repository plus Global-routing focused
   surface passes 52 tests with 85 deselected and zero failures.  The live
   database compatibility node separately proves that immutable INPUT
   manifest `03718fe3…` and snapshot `0c9c8dc9…` remain exact while the
   current pointer is the legal READY manifest `1cc4ebf7…`, snapshot
   `93907aa7…`, and unique recovery-v2 Ready task.  The legal-stage,
   event/registration/fact tamper, shared-hook, and atomic pre-write timing
   tests pass.  Ruff, `py_compile`, and `git diff --check` pass.  Full Worker
   validation passes 2628 tests with 4 existing skips and zero failures.
9. Request 576 and Execution 471 remain immutable and are never retried or
   reused.  Both Global builders and loaders, Supervisor, control plane,
   routing, progress, models, all four source configs, Evidence, and Index are
   byte-identical.  This Engineering round performs no import, Supervisor
   start, workload, replay, service mutation, P3 fold, P4 action, or
   Promotion.  During the validation pause, a user service was externally
   auto-started and immediately stopped after it emitted only a fail-closed
   status heartbeat (`dispatch_performed=false`) for its validation error;
   the durable manifest/snapshot/unique Ready projection, task state, event
   lineage, and predictive-P3 fold count remained unchanged.  Predictive-P3
   folds remain exactly `0`.
10. Failed Engineering Request 578 and Execution 473 are not retried; their
    exact three-path bytes were adopted only as frozen preimages under fresh
    Request 579 authority.  The fourth-path delta is wholly inside
    `test_recovery_input_fixture_matches_live_database_when_available`; every
    byte outside that function remains baseline-identical.
11. Integration matrix: `NO — INTEGRATION_PENDING`.  A fresh independently
    reviewed Operator request is required after exact4 publication and
    merged-main CI success.

## Global routing actual-schema recovery v2

1. The result-blind recovery input is manifest `03718fe3cb8744410d66f72f523e469baa5ff01c78334792c85fd9cd5c9298cc`, snapshot `0c9c8dc98f92f04c7c7ba57e824b881d65976415b7e9f3dc1fe1d793ec5cdc50`, and Ready `[]`.
2. Failed recovery-v1 definition `09068006b555e4d9f2d9bb4ec6a1c471daa244c82fe278c44407b2aeab1fcff2`, execution `bc2dada5ea040d488b9256ea2adb90163b6c46a45d517e545f7d24b39efa7c66`, and ordered started/failed events remain immutable.
3. The additive successor is `m4-v2-global-routing-recovery-v2`; its compatibility predicate reads source ownership from replay envelope parent zero and recovery lineage from the typed durable Marginal recovery task definition/state. It does not require nonexistent replay-body fields.
4. Marginal raw/source-set/artifact are `a6ab598845e822489218ad3595533d1f0128ca8a8955b4aa1e616df5c1c14308` / `513d5716a256b6863d8f0c1b4cf2d0798a2031cd7905bc9e9ce73233f618e7fa` / `b4d008248fbc5dc24e9d2e9c95ddb8fbae6123c7cf5d06a06b7361001069e265`.
5. Temporal raw/source-set/artifact are `f06cf742a7d1b23e618d87879001e184ef8a76c5dec65bcbf22e9cdb405964ce` / `5957d641a7ade50eebfb6a0b3de9260132875e03c66a5773b9cc6a0323179451` / `3056dc8ec97d91b8b7ad3f283b56e89693569e23b070e143c220f999d1dbac8e`.
6. Joint raw/source-set/artifact are `6e622bebb7bc65eafa8cb9eac579874e1d306048e09638d00dc466f1c9eb7eb8` / `d2e83e6d24548ecb9e902d5a3065070dfe94ad93b251455f229ff781f07135ff` / `d9b4e3a280c4d49db6c859c7c08736dcb6e8723875f8269df220d41a79b3240d`.
7. Global raw/source-set/artifact are `a4e2241ad1dca793c6436866232ec555862da949c016a6d32dae5fafb50840e1` / `51416beac1b615c6b5b91786f40f105b45ec7503285126649aa4334715b3a00c` / `24bfd16ee558f13ec2a50a30a8d903a11934fc128f996f370d78fdba9a4929ec`; recovery-v1 remains ordinal 4 and recovery-v2 is appended at ordinal 8.
8. The pure durable transformer output manifest/snapshot/dry-run/recovery definition are `1cc4ebf7a458ecaf6eba3e3a8079012318a2bf7354cb4b3f9770dcfa9ddbe84d` / `93907aa79561e6e9929f5211703180f6d0619caa72b930086e473f0b0b5a2e56` / `445df30d9ed25d78bdf6bd6870c89ba68efb6bce8206960dc1bfdd0ad35c076c` / `a2c26aa0c86d22065508b74a640f37b4cd5b2531368ed234294a30c31cfbcbca`; no import is performed here.
9. Checked-in Evidence raw/manifest/snapshot/length are `7c1974fd61bc15286f32b86371856254d4e68fef32d41289177aaca5974c6b91` / `8b6aa2e52b39abdedc00aaeeda348b910713edea778e67693f80a6c4df7955e3` / `b9af9f3e30699abbc2b90c2c747a3ccd52d0906876b8be705b509b613f47bbb1` / `343792`; goals remain 4 and tasks remain 94.
10. Artifact Index raw/length are `6bd884630820cf38ef23e3a7e4efdaeef2fc016ecdd58162c38d59ee6610debd` / `75881`; the four persisted source identities and prior Evidence identity point directly and reciprocally to the new identities.
11. Only the two predictive-P3 definitions are dependency-zero revisions from recovery-v1 to recovery-v2. Predictive-P3 folds remain `0`.
12. Integration matrix: `NO — INTEGRATION_PENDING`.
13. Predictive-P3 folds: `0`.

## Global recovery v3 import dispatcher correction

1. Formal Operator Request 603 and Execution 493 are immutable failed
   records under Decision 2536 and are not retried or reused. The sole
   conditional recovery-v3 import attempt failed before the first write;
   `import_count=0`, the durable manifest remains `b50a4c07…`, the durable
   snapshot remains `527494d7…`, Ready remains `[]`, and recovery-v3 retains
   zero definitions, states, events, and registrations.
2. A result-blind READ ONLY validator reproduction rebuilt the exact approved
   recovery-v3 candidate manifest `ed48af29…`, canonical identity
   `bd31cb80…` / `299516`, snapshot `ca5636d3…`, and unique Ready task
   `m4-v2-global-routing-recovery-v3`. The recovery-v3 verifier passes; the
   immediately following legacy recovery-v2 verifier rejects that additive
   successor as
   `ResearchOSValidationError("m4_v2_global_recovery_v2_output_changed")`.
   No result, error, decision, execution, or registered-artifact payload was
   read to establish the dispatcher fault.
3. Completed Research Request 604 / Execution 494 freezes the one permitted
   recovery-v3 repair. Approved Engineering Request 605 / Execution 495
   changes only the repository dispatcher, its repository tests, and this
   append-only report. No recovery-v4, artifact type, schema field, registry
   field, successor task, compatibility layer, threshold, estimand, or route
   is added.
4. `PostgresResearchOSRepository.import_manifest` always invokes the immutable
   recovery-v3 verifier first. Only after it passes, exact presence of
   `m4-v2-global-routing-recovery-v3` suppresses the incompatible
   recovery-v2 whole-manifest verifier. Inputs without that exact task still
   invoke the unchanged recovery-v2 verifier exactly once. The legacy
   recovery-v1 verifier and every downstream prewrite/write guard remain in
   their original order; malformed recovery-v3 input still fails before a
   skip or write.
5. Mandatory dispatcher tests pass `9` cases with one contract-defined
   isolated-PostgreSQL skip. The first independent review rejected an earlier
   probe that replaced the recovery-v3 verifier; the corrected default-suite
   cases now execute the immutable production verifier for exact `ed48` and
   all task/source/manifest tampering before observing dispatcher order and
   the no-write boundary. The complete repository module passes `97` tests
   with five isolated-PostgreSQL skips. Ruff, `py_compile`, exact3 scope, and
   `git diff --check` pass. A zero-failure full Worker run and fresh independent
   final code/contract review remain mandatory pre-commit gates.
6. The prior publication baseline remains PR 353: PR-head Worker run
   `31852289234` and merged-main Worker run `31853919479` both succeeded;
   merged main is `737b50bf533f3be909cb89e00892cddce10663c5`. Fresh
   dispatcher-fix PR-head and merged-main CI identities are external
   post-commit lifecycle evidence and are intentionally not recorded in this
   source report.
7. This Engineering round performs no production import, Supervisor run,
   workload, replay, route, P3 fold/event, P4 action, or Promotion. Predictive
   P3 folds remain exactly `0`.
8. Integration matrix: `NO — INTEGRATION_PENDING`. After exact3 publication
   and both fresh CI gates succeed, a fresh separately reviewed Operator must
   import the approved recovery-v3 manifest and resume Resolver-driven
   execution.

## Global recovery v2 repository builder loader closure

1. Completed Research Request 568 freezes one repository-only correction:
   `PostgresResearchOSRepository` loads the canonical recovery-v2 builder from
   its exact repository-root path through a fixed private
   `importlib.util.spec_from_file_location` module. The loader neither changes
   `sys.path` nor changes or depends on the process working directory.
2. The resolved builder path must remain inside the resolved repository root
   and must be a regular file. Missing, wrong, outside-root, symlink-escaped,
   non-file, unavailable-spec, unavailable-loader, execution, missing-symbol,
   noncallable-function, and invalid-error-class cases all fail before the
   first SQL write as
   `ResearchOSValidationError("m4_v2_global_recovery_v2_builder_unavailable")`
   with the original cause preserved.
3. One loader invocation returns one `ModuleType`; that same module owns the
   ordered 13 frozen constants, functions, and error class used by the existing
   pre-write validator. The canonical repository import remains the singular
   importer; builder algorithms and constants are not copied into the
   repository.
4. A real subprocess with cwd equal to the repository root reproduces the old
   `ModuleNotFoundError` for the former `scripts.*` package import and passes
   the private loader plus validator on the corrected bytes. The focused loader
   matrix passes 22 tests, the complete repository module passes 22 tests with
   4 isolated-PostgreSQL skips, and the repository plus Global-routing focused
   surface passes 94 tests with the same 4 skips. Ruff, `py_compile`, and
   `git diff --check` pass; full Worker zero-failure validation remains a
   mandatory pre-publication gate.
5. The standalone recovery-v2 builder, all four source envelopes, Evidence,
   Index, pure manifest `1cc4ebf7…`, snapshot `93907aa7…`, dry-run
   `445df30d…`, recovery definition `a2c26aa0…`, lineage `1f7ecdea…`,
   Ready queue, science, thresholds, route, P3, P4, and Promotion are unchanged.
6. Failed Operator Request 567 and Execution 465 are immutable and are not
   retried. This Engineering round performs no import, Supervisor start,
   workload, replay, or runtime mutation. Predictive-P3 folds remain `0`.
7. Integration matrix: `NO — INTEGRATION_PENDING`. After the fix is merged
   and merged-main CI is green, a fresh separately reviewed Operator Request is
   required for any canonical import or run.

## Global recovery v1 repository builder loader closure

1. Completed Research Request 572 and Engineering Request 573 freeze one
   repository-only correction: the legacy recovery-v1 pre-write validator now
   loads its singular canonical builder from the exact repository-root path
   through the fixed private module
   `_dehps_m4_v2_global_routing_recovery_v1_builder`.
2. The v1 loader uses exactly one
   `importlib.util.spec_from_file_location` /
   `importlib.util.module_from_spec` / `spec.loader.exec_module` sequence.
   It returns one `ModuleType` owning the ordered ten frozen symbols. Missing,
   non-file, outside-root, symlink-escaped, unavailable-spec,
   unavailable-loader, execution, missing-symbol, and noncallable-build cases
   fail before the first SQL write as
   `ResearchOSValidationError("m4_v2_global_recovery_v1_builder_unavailable")`
   with the original cause preserved.
3. The corrected repository contains zero production `scripts.*` imports,
   does not mutate `sys.path` or cwd, and has no alternate, fallback, or
   latest-module path. The existing recovery-v2 loader bytes, behavior, private
   module name, and tests are unchanged.
4. A real subprocess from repository-root cwd reproduces the old v1
   `ModuleNotFoundError`, then loads v2 followed by v1 and reaches both
   pre-write validators on the corrected bytes. The focused loader/owner matrix
   passes 35 tests; the complete repository module passes 37 tests with 4
   existing isolated-PostgreSQL skips; the repository plus Global-routing
   focused surface exits successfully. Ruff, `py_compile`, and
   `git diff --check` pass. Full Worker validation passes 2604 tests with 4
   existing skips and zero failures.
5. Both standalone builders, all four source envelopes, Evidence, Index, pure
   manifest/snapshot/dry-run/recovery/lineage identities, durable manifest
   `03718fe3…`, snapshot `0c9c8dc9…`, Ready `[]`, science, thresholds,
   routing, P3, P4, and Promotion remain unchanged.
6. Failed Operator Request 571 and Execution 468 are immutable and are not
   retried. This Engineering round performs no import, Supervisor start,
   workload, replay, or runtime mutation. Predictive-P3 folds remain `0`.
7. Integration matrix: `NO — INTEGRATION_PENDING`. After this exact3 change
   is merged and merged-main CI is green, a fresh separately reviewed Operator
   Request is required for any canonical import or run.

## Global routing recovery v1 and exact replay lineage

1. The result-blind recovery input is manifest `15f5d12cebb0eed31f4f0f33c1ac4d3d0878f9335d11741046305baf746eb216`, snapshot `e80b5fa52caee4cbab1f380aceda3dd55cede6581fb8ee62a882afdd843ea2c5`, and Ready `[]`.
2. The old failed `m4-v2-global-routing` definition, state, execution `7d1d2d82c6d46679f9e3da9f0d743b0d7a774262eb3c5220daefca11100ad12d`, and ordered event digests `dab8a953b60bebcb927147d123b7280392b9a3ead6f0d225ec5799e4b7caaebb` / `a4163025b41b837c1d3c467242b0710b9255bd68a0e6cb16378b64f6c7e0a37c` remain immutable.
3. The additive active successor is `m4-v2-global-routing-recovery-v1`; the two predictive-P3 definitions change only dependency zero from the old Global key to that successor.
4. Marginal raw/source-set/artifact are `518155b055a4e94abda2e803dc1c0b81a5eeab67f24286af6c8f5394c2687471` / `0925ab8fb843ff122338480076d9c61dbbaffde96365b02b2aeba50630a37dea` / `189a3d56f0986bf1c8cd5960a995ac36d0155cf341c8c554c1537c5278c0cd0b`.
5. Temporal raw/source-set/artifact are `96d6906e1e689219e541ba195b9dd83178c4f6f04758cc33155ec47050e57531` / `159d85ef452b51351483b13fdba2f4b0d207afada776b81f7dd525eaa49c652b` / `f4b95688273927fdf22d5ebc38fc51f7da9fc7a46321a655ebfa7b76ff4172f9`.
6. Joint raw/source-set/artifact are `8b92b8944d89d65d4d79dda74dcdd9f7ad99ce31040ba097ff12ef2be570ebd8` / `6160958a1c869716438be9ea27ca5492b419c8a88ec978a6c46db3952f60d131` / `212c8ab6820ac8a5f0c89e2d6be33b42ee91ca26276cc75c54a9cc3e3214a5b3`.
7. Global raw/source-set/artifact are `f65982c371c6e0598f51814e51e1fe0bd6162b7c23332976d39fd881e145ff5b` / `57e96ce7553ad9c3795e98ebbd32d49f12ba7eb3c6e696ba49c5752e0a7dd53b` / `ae2985e419e5b2839c29fe47372480ee50b35b7070109842f2984d5d44101670`; its source ordinal 4 is the standalone recovery builder.
8. Checked-in Evidence raw/manifest/snapshot/length are `f927c21e99d56cb857f39e8e0e8b7365de9652a97076ee5d5fc515461232ae82` / `37fe3ffd8f0c026615f9da80e2850398d2442657c773e41d5dbcd3e9627a0c5c` / `c12637a544f20882e20f8205d089f4371b59519c974b1a965eddbd02f37ddeed` / `343976`. The active Global successor owns `m4-v2-global-routing-recovery-v1:COMPLETE` and its recovery-key content-addressed artifact path. No import is performed here.
9. Artifact Index raw/length are `96daa788fee0cae47489f63d2d7ec8e3a953b48f40b9fd7bb23fd179c2e68d53` / `73604`; the four prior live source artifacts and prior Evidence manifest are historical `path_at_source` entries with direct reciprocal supersession to the final live identities; no unpersisted intermediate candidate is registered.
10. The Marginal recovered replay is accepted only by the exact Request555 decision/replay/mainline-execution conjunction; Temporal and Joint retain historical exact replay task-key equality.
11. No production import or Supervisor/workload/P3 execution occurred. Predictive-P3 folds remain `0`.
12. Integration matrix: `NO — INTEGRATION_PENDING`.
