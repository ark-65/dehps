# Prediction v2 Shadow Scheduler Binding — 2026-08-01

## Round contract

- Engineering Request: `engineering-prediction-v2-shadow-scheduler-binding-20260801`
- Request id: `232`
- Engineering execution: `153`
- Primary goal: add the source path for one replay-verified Prediction v2 shadow Top100 before each draw and one replay-verified settlement report after durable draw synchronization.
- Non-goals: no live scheduler installation, no service stop/start, no mail send, no legacy retirement activation, no M4 operation, no signal-bearing model, and no Historical Evidence.

## Outcome

The source capability now materializes an additive, issue-specific maintenance DAG:

```text
prior-only HistorySnapshotArtifact
  -> issue pre-draw execution
  -> pre-draw physical replay
  -> replay-verified notification envelope
  -> durable audited draw-sync event
  -> post-draw execution
  -> post-draw physical replay
  -> replay-verified notification envelope
```

Every issue artifact remains `route=BASELINE_ONLY`, `HistoricalEvidence=NOT_RUN`, `Evidence Progress=0`, and `promotion_gate_opened=false`. Marginal, Temporal, Joint, Expert Router, MoE, and other signal-bearing estimators remain unauthorized.

## Implemented boundaries

- A canonical prior-only history artifact and immutable `PredictionV2IssueManifest.v1` bind the as-of and target issues. The target must be later than and absent from the snapshot.
- Four deterministic per-issue tasks pass through the existing Goal, Resolver, Ready Queue, unified Research Evidence Supervisor, artifact registry, status projection, next consumer, and replay path.
- Pre-draw replay reconstructs state, the legal-null 10,000-candidate pool, Top100, and report and compares exact artifact identities.
- Post-draw work requires a matching external event fact plus one immutable audited draw artifact. Missing, duplicate, stale, mismatched, corrected, or digest-changed inputs fail closed.
- Notification envelopes are created only by replay tasks. The idempotent ledger uses `sending`, `sent`, and `uncertain`; an ambiguous SMTP failure requires manual review and is never automatically retried.
- The draw-sync watcher invokes the v2 post consumer only after the separately governed legacy-retirement activation is present. Consumer or notification failure is recorded without replacing successful draw synchronization.
- The source pre-draw timer is Tuesday/Thursday/Sunday at 17:00 Asia/Shanghai. The post-draw path is triggered by the existing audited draw-sync watcher, not by an independent outcome poller.
- The immutable live scheduler plan declares stop-before-start ordering, source units, rollback ordering, and the Operator boundary. This Engineering round did not execute those operations.
- Target issue inference handles calendar-year rollover by resetting the sequence to `001` when the next scheduled draw enters a new year.

## Integration matrix

| Link | Source validation in this round | Live state |
| --- | --- | --- |
| Goal | Per-issue runtime-capability Goal is added once | Not imported live |
| Resolver | Pre waits for reference replay; post waits for pre replay and draw-sync fact | Not imported live |
| Ready Queue | Tested with additive issue manifest | Not imported live |
| Supervisor | Pre, pre replay, post, and post replay run through `ResearchEvidenceSupervisor` in memory | No resident process operated |
| Capability | Four issue capabilities registered under isolated `prediction-v2-shadow` control plane | Source only |
| Artifacts | Issue, history, live scheduler plan, state, pool, Top100, reports, replays, draw, envelopes, and executions registered | No production artifacts created |
| Status | Shadow status remains evidence-zero and Promotion Gate closed | No live status changed |
| Next consumer | Only replay-verified envelopes can reach the delivery ledger | No messages sent |
| Replay | Exact pre/post physical replay succeeds; tamper and identity mismatch fail closed | No production replay executed |

## Isolation proof

- M4 manifest SHA-256 before/after source work: `316c8acd7e8d04a92410274600b999e626327bf74a3d256f9c7cc202612a17c0`.
- No P2.6.1 statistical result was read.
- No resident Supervisor was stopped, started, or restarted.
- No systemd unit or timer was installed, enabled, disabled, started, or stopped.
- No database control-plane key was imported by this Engineering execution.
- No SMTP connection or live delivery was attempted.
- Legacy artifacts and history remain untouched.

## Validation

- Focused Prediction v2 + draw-sync suite: `33 passed`.
- Ruff on all newly added/touched Prediction v2 scheduler-binding files: passed (the draw-sync module retains three pre-existing broad-catch findings outside this round's new isolated consumer).
- Impacted Research OS / draw-sync / Prediction v2 suite: `63 passed, 4 skipped`.
- Complete Worker suite on the final source: `1953 passed, 4 skipped, 4 warnings` in `374.67s`; warnings are the pre-existing Python 3.14 multiprocessing/fork deprecations in parallel training tests.

## Completion statement

`NO — INTEGRATION_PENDING`.

The implementation is source-complete and exercises the full canonical chain with an in-memory control plane, but the capability is intentionally not complete until an independently approved typed Operator Release performs the atomic legacy retirement, additive live import, real issue execution, physical replay, delivery verification, rollback proof, and M4 zero-change audit.

## Post-merge cutover erratum

Read-only live inspection after PR #237 found that the packaged draw-sync unit still declared `Wants=dehps-forward-runtime.service`. That dependency would restart the legacy three-line forward runtime on the first draw-sync timer activation after retirement.

Engineering Request `engineering-prediction-v2-cutover-unit-decoupling-20260801` removes only that source-unit dependency and adds a regression assertion that audited draw ingestion plus the Prediction v2 post consumer remain configured without any `Wants` or `Requires` edge to the legacy forward runtime. Network and PostgreSQL ordering are unchanged. No installed unit or live service was modified by the erratum round.

Erratum validation: focused draw-sync/systemd/Prediction v2 tests `38 passed`; final complete Worker suite `1954 passed, 4 skipped, 4 warnings`; M4 manifest SHA-256 remained `316c8acd7e8d04a92410274600b999e626327bf74a3d256f9c7cc202612a17c0`.

## Live import incident and recovery

The first approved live activation reached the merged draw-sync unit but failed before synchronization or notification delivery. `dehps.draw_sync.scheduler` attempted to import `scripts.run_prediction_v2_shadow_issue`; when Python executes `scripts/run_draw_sync_watch.py`, the scripts directory itself is on `sys.path`, not its parent as a `scripts` package. The resulting `ModuleNotFoundError` was recorded under Operator execution `155`, both Prediction v2 timers were stopped, legacy compute remained disabled, and the M4 service identity remained unchanged.

Engineering Request `engineering-prediction-v2-draw-sync-import-runtime-fix-20260801` changes only that loader to the canonical sibling-script import and adds a subprocess regression using the same scripts-directory import context. No draw-sync logic, Prediction v2 artifact, estimator, route, evidence rule, Promotion Gate, live service, cron, database, activation, or M4 state is changed by the repair.

The next recovery pre-draw attempt exposed a second fail-closed integration gap before control-plane import or mail delivery: durable repository exports identify themselves with `manifest_digest`, while the per-issue extension removed only the source-only `artifact_digest` spelling. Engineering Request `engineering-prediction-v2-live-manifest-digest-fix-20260802` clears both derived identity spellings before pre/post additive extension and validates exported-manifest-shaped fixtures. Existing goals, tasks and facts remain subject to the same zero-delete/zero-rewrite migration check.

After that repair, the manually authorized 2026088 pre-draw task and replay completed and the replay-bound notification was delivered exactly once. The first Persistent timer catch-up then failed before dispatch because a durable repository export includes derived task projection fields (`goal_digest` and `superseded_by_task_digest`) that are absent from a source task declaration. Engineering Request `engineering-prediction-v2-existing-issue-idempotence-fix-20260802` excludes only those repository-derived fields, together with runtime status fields, from the source-definition identity comparison. All source-owned fields remain exact and any drift still fails closed. This makes an exact already-imported issue a no-op without weakening artifact, fact, task, or goal identity validation.

## Live activation status-binding follow-up

Operator execution `161` completed the physical legacy retirement and Prediction v2 shadow cutover, but the isolated control plane still projected the scheduler boundary as `approval_wait`. Consequently, the status artifact continued to say `NOT_PUBLISHED` even though the old services were stopped and disabled, the replacement timers were active, issue `2026088` had completed all four tasks and replays, and its pre/post notifications had each been delivered exactly once.

Engineering Request `engineering-prediction-v2-live-activation-status-binding-20260803` closes only that canonical status-chain gap:

- the existing scheduler boundary becomes a maintenance activation-attestation capability under the unified Supervisor;
- an allowlisted migration may revise only that task definition and add only the frozen Operator authority fact;
- the task binds the sealed retirement activation, immutable Operator completion payload, and cutover plan as three exact input identities;
- the capability emits an immutable `PredictionV2LiveActivationAttestation.v1` and a completion fact;
- physical replay reconstructs the attestation from the same activation and completion inputs, checks registered content and execution child identity, and fails closed on tampering;
- `legacy_retirement_activation=VERIFIED` and `legacy_compute_state=STOPPED_AND_DISABLED` are projected only from the replayable mainline completion fact.

This source round does not import the live manifest, publish the canonical completion copy, execute the capability, operate services or timers, send notifications, or touch M4. Those actions remain a separate typed Operator execution after merge. `HistoricalEvidence=NOT_RUN`, Evidence Progress `0`, and `promotion_gate_opened=false` remain invariant.

Source validation for the follow-up: the focused activation migration/replay tests pass (`2 passed`), the complete Prediction v2 shadow suite passes (`19 passed`), and the complete Worker suite in a clean detached worktree passes (`1957 passed, 4 skipped, 4 pre-existing Python 3.14 fork warnings`) in `362.94s`. The final live integration matrix is recorded at the accepted commit/Operator boundary rather than inferred from source availability.
