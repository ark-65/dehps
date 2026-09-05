# Prediction error learning: phase one

Goal: `dehps-mainline-prediction-error-learning`.
Engineering Request 810 / execution 651 implements the user's 2026-09-05
authorization. This round delivers offline decision tracing and complete samples;
production deployment and real email delivery require a later user decision.

## Contract before implementation

| Required item | Phase-one boundary |
| --- | --- |
| Mainline problem | Explain Top-100 omissions from actual frozen decisions and retain complete labels for future learning |
| Canonical Goal | `dehps-mainline-prediction-error-learning` |
| Supported task | Existing P3 refit, predraw/replay and notification post-return-report; no replacement |
| Ready condition | Exact registered completed predraw and refit parents; post-draw diagnosis additionally requires registered settlement/replay and already-open issue payout/report |
| Runner | Additive read-only offline preview adapter calling the existing canonical P3 and PnL functions; not a second prediction or completion runner |
| Upstream | Exact source contract, preregistration, frozen dataset/model, candidates, baseline, checkpoint/replay, settlement/replay, opened payout/report |
| Downstream | Content-addressed decision record, complete 33-red/16-blue label sample, all-ticket diagnosis, extended offline PnL preview |
| Status projection | `OFFLINE_VERIFIED / INTEGRATION_PENDING`, per-issue provenance and sample state; no formal Goal mutation |
| Evidence rule | Engineering only, zero scientific/Promotion credit; no cumulative sealed statistics |
| Decision consumer | Human deployment review; existing Formal P3 gate is unchanged |
| Next consumer | Future authorized observation integration and separately frozen learning candidate; no automatic training ingestion |

No changes to Formal P3 source bytes, model, features, update, ranking, Top-100,
blue assignment, timer, or historical artifacts. Existing P3 already freezes
the historical dataset, count sufficient statistics, exact probability fractions,
generator seeds, Top-100 and rank-wise blue assignment. Reuse those producers.
New records made after the draw are explicitly post-hoc indexes of that evidence,
never newly sealed predictions. Missing historical input remains missing.

The current generator samples 10,000 unique legal red combinations, scores the
33 Bernoulli events, and keeps the first 100 with ascending lex-id ties. There is
no extra diversity filter or final exclusion stage. The diagnostic reports that
absence instead of inventing one. A hypothetical insertion rank is distinct from
the actual generated-pool rank. All 100 tickets and all missing/extra replacement
pairs are analysed; no hindsight selection of a nearest ticket.

Integrity checks precede optional explanation/rendering. A reporting failure
returns the verified base PnL report and a visible diagnostic failure; corrupted
prediction or label lineage fails closed for the affected preview/sample.
No diagnostic code is imported by the live prediction or settlement path.

## Existing training entry

`ForwardPrequentialCapability.execute` dispatches `REFIT_CAPABILITY` through the
existing Research Evidence Supervisor. `fit_model_artifacts` selects history
strictly before the target and calls `estimate_legal_marginals`, with
`q_i=(c_i+2/11)/(n+1)`. There are no learned interactions or blue-ball model.
The new sample store records labels and availability for a future consumer; it
does not assert that writing a sample retrained or improved a model.

## V11 retirement

Operator Request 809 / execution 650 completed shutdown only. Both exact user
units `dehps-m4-isolated-24h-challenger-v11.timer` and `.service` are masked,
with no V11 process. Their failure states were not reset. The three dirty files
remain in the original checkout and were backed up separately with a binary
patch whose restoration was verified. All 530 V11 runtime files were archived
and compared byte for byte. Twenty shared unit files and enabled states were
unchanged. Historical database events, registrations, incidents and failures
were not modified. No old replay, SMTP, downstream or recovery ran.

Local evidence: `/home/ark/workspace/dehps/runtime/v11-retirement-20260905/`.
Research disposition remains `FROZEN_INCOMPLETE / RECOVERY_ABANDONED`; successful
shutdown does not turn the abandoned 20260828 recovery into a success.

## Acceptance evidence

The read-only adapter verified registered parents, actual predraw completion
timestamps, exact model refit from the frozen dataset, all four original predraw
artifacts, predraw replay, settlement, payout, the existing PnL report and its
replay. Three already-open V3 issue reports were processed without querying any
interim-review/cumulative-result task. The CLI uses read-only database
transactions with a 15-second statement timeout and has no deployment/mail flag.

| Opened issue | Actual red numbers | First omission | Hypothetical insertion rank in frozen pool | Simulated cost / gross / net |
| --- | --- | --- | --- | --- |
| 2026100 | 03 04 09 13 22 31 | NOT_GENERATED | 4635 | CNY 200 / 25 / -175 |
| 2026101 | 05 06 08 09 24 25 | NOT_GENERATED | 4324 | CNY 200 / 25 / -175 |
| 2026102 | 03 04 10 13 16 25 | NOT_GENERATED | 6664 | CNY 200 / 50 / -150 |

These are separate descriptive issue diagnostics, not a cumulative test or a
claim of a recurring learnable cause. The insertion rank is hypothetical; it
never changes the actual NOT_GENERATED classification or the original Top-100.
All 100 tickets, all missing/extra replacement pairs, 33 number exposures,
4,950 ticket overlaps, red-hit distribution and full red/blue hits are retained.

Concrete 2026102 example (the original rank-1 ticket, chosen by predraw rank):

- Original red ticket: `06 14 17 19 22 26`; frozen score `-22.02639843407095`.
- Replace 6 with 3: probability `0.19096365195250592 -> 0.18324716152666995`,
  marginal rank `6 -> 16`, historical count `668 -> 641`, with `n=3498`.
- New score `-22.099600686887324`, delta `-0.07320225281637605`.
  The removed-event and added-event contributions are respectively
  `+2.0829064592908897` and `-2.156108712107266`; no interaction is claimed.
- Hypothetical insertion rank `1 -> 17`, but the replacement was NOT_GENERATED
  and therefore was not eligible for selection. A high hypothetical rank is not
  evidence that the historical pipeline actually considered that combination.
- Winning red combination score `-22.660455713016876`, below the Top-100 cutoff
  by `0.4827149200273553`. Its first omission remains generation, not ranking.
- Red-hit counts: zero hits 53 tickets, one hit 40, two hits 7; no complete red
  or red/blue hits. Blue-only awards account for the CNY 50 simulated payout.

Every processed issue has complete 33-red and 16-blue labels plus its original
features/probabilities/100 tickets. Successful complete hits are covered by the
synthetic test fixture as well as failures; they take the same sample path.
The samples are `RECORDED_NOT_INGESTED_BY_NEW_LEARNER`.

Existing (unchanged) red-count training inclusion was separately verified in
the next frozen dataset, including temporal eligibility:

| Label issue | Audited settlement completion (UTC+08) | Next original seal (UTC+08) | Next dataset digest |
| --- | --- | --- | --- |
| 2026100 | 2026-08-30 21:52:17.238197 | 2026-08-30 21:55:42.748295 | `3544d85b15c55ec0d564d0f35d31ce542fb1dc47a06f4d14acc2f2159f22786b` |
| 2026101 | 2026-09-01 21:52:49.476319 | 2026-09-01 21:56:28.987841 | `59b8bd05b9cae6ed0fcd6957693847189b9450ce2e337ae0e53a01c8fd00abeb` |
| 2026102 | 2026-09-03 22:00:42.330236 | 2026-09-03 22:04:33.126363 | `82930858fdfce2af1ef741d9ed43430d5eca3afd8cb3f93f1d591cfcb6ffce2c` |

2026103 was also captured before its draw as `PREDRAW_OBSERVATION`, without any
outcome read or label sample. The three older records are explicitly
`POST_HOC_DIAGNOSTIC_INDEX`. They contain the original registered predraw facts;
their new creation times do not purport to be historical seal times.

Local delivery root:
`/home/ark/workspace/dehps-error-learning-phase1/runtime/error-learning/`.
Each `202610{0,1,2}-delivery/preview.html` is an offline, expandable all-ticket
report. Full frozen records and complete samples are in the corresponding
`-final/decisions` and `-final/samples` directories. Predraw-only 2026103 is under
`2026103-verified/decisions`. The final per-issue replay/ingestion proof is
`final-acceptance/91fafc3751b049d552f5b9112dfa69073eca0a6c3536082ec138ba68afd8d739.json`.
These generated outputs are deliberately not committed.

## Validation and limitations

Command (from `apps/worker-python`, using the existing project venv):

```sh
python -m pytest -q tests/test_prediction_error_learning.py \
  tests/test_p3_top100_notification.py \
  tests/test_m4_p3_forward_prequential_confirmatory.py
```

Result: **52 passed, 1 pre-existing failure**. The same failing node was run
independently in the original `main` checkout and fails identically:

```text
test_source_contract_and_old_lineage_are_both_replay_verifiable
bounded_forward_source_bytes_changed:apps/worker-python/dehps/research_os/repository.py
```

Neither that repository module nor any Formal P3 source entry was changed.
The historical bounded-lineage hash is not resealed. Running the focused suite
with only that independently reproduced baseline failure deselected gives
**52 passed, 1 deselected**. The complete failure output remains at
`runtime/error-learning/tests-full-focused.txt`; it is not represented as a
fully green suite. New tests cover missing provenance, corrupt artifacts,
actual versus hypothetical ranks/ties, the requested 7-to-2 replacement,
all-ticket/success/failure sampling, same/earlier issue labels, availability
times, backdated sample issue, optional reporting failures versus mandatory
integrity failures, immutable writes and scoped result-blind access.

The loaded current P3 model and feature versions are unchanged. Its probability
vector is marginal, not a calibrated joint six-number model. Exact data ingestion
cutoff timestamps were not recorded historically: the report retains the real
issue boundary and says that timestamp is missing. A missing refit registration
produces UNKNOWN and no trainable sample; damaged registered data fails closed.
The opened-report adapter targets the existing V3 route (2026100 onward), and
does not recover or rewrite older V1/V2 reports. Cumulative patterns, new tuning,
new learning-rule validation and predictive improvement remain unevaluated.

## Integration matrix at the deployment boundary

| Item | Evidence / status |
| --- | --- |
| Canonical Goal | User Goal and Engineering Request 810, not imported as a new production Goal |
| Dependency Graph | Existing refit -> predraw -> replay -> settlement -> replay -> report reused read-only |
| Ready Queue | Existing completed parent tasks checked; no new live task/fact added |
| Unified Runner | Canonical P3 and PnL functions called offline; no new production dispatch |
| Upstream artifacts | Registration/digest/timestamp verification for each exact issue |
| Downstream artifacts | Immutable local decisions, complete samples, diagnoses and previews |
| Status projection | Per-issue OFFLINE_VERIFIED; mainline INTEGRATION_PENDING |
| Engineering Progress | Phase-one implementation and offline acceptance delivered |
| Evidence Progress | Zero scientific decision credit; no improvement claim |
| Downstream consumer | Human deployment review; future learner not connected |
| End-to-end replay | Three exact deterministic offline replays; no new live execution fact |
| No old bypass | Formal/V11 runners never import this adapter; no old recovery or competing prediction path |

**NO — implementation remains INTEGRATION_PENDING** until separately authorized
mainline deployment and real-cycle acceptance.
