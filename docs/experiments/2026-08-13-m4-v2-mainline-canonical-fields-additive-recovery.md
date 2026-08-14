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
