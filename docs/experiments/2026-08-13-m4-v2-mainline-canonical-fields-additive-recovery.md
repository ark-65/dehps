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
13. Predictive-P3 folds: `0`.
