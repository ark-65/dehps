# R0–R5 control-layer refactor acceptance

The independent learning and observation domains are deployed, complete and
replay-verified. Formal P3 retains its frozen executor in a fixed release. Its
2026105 settlement has now recovered through the original canonical executor,
and the original report service delivered the current post-draw report once.
The next natural P3 cycle also sealed 2026106 and verified all three prerequisite
tasks. **R0–R5 engineering, deployment and current-cycle acceptance are complete**
within the retained-P3 compatibility arrangement specified by the roadmap.

This is control-layer engineering acceptance, not a new scientific experiment.
The retained learning conclusion remains **证据不足**. V11 remains retired.
R6 is a separate, bounded scientific milestone and was not started here.

## Stage evidence and scope

| Stage | Implemented result | Acceptance evidence |
| --- | --- | --- |
| R0 | Actual runtime/source/permission inventory, independent development checkout, owner-authorized scope and control-domain completion rules | [Baseline/checkpoint](2026-09-09-control-layer-refactor-checkpoint.md), roadmap and governance clarification; PR427. The final entry inventory below supersedes dated pending statements. |
| R1 | Explicit state/artifact/outbox/lock paths, isolated OS/database resources, authenticated review and execution admission | [Resource boundaries](2026-09-09-control-layer-r1-resource-boundaries.md), [authority](2026-09-10-control-layer-r1-authority.md), PR428–430; actual deployed identities and denial probes in the [independent activation](2026-09-11-control-layer-r5-activation.md). |
| R2 | Reused canonical Goal/DAG/resolver/Ready Queue, injected coordinator/verifier, immutable files and atomic commit/registration, fencing and reconstruction | [Store](2026-09-10-control-layer-r2-store.md), [mainline](2026-09-10-control-layer-r2-mainline.md), PR431–432. Real PostgreSQL lost acknowledgment, killed processes, database restart, full FK fixtures, concurrency and fresh-process replay were exercised. |
| R3 | Fixed source/dependency releases, distinct scientific/release/schema identities, explicit status consumer with UNKNOWN for missing/stale/wrong identity | [Release](2026-09-10-control-layer-r3-release.md), [status](2026-09-10-control-layer-r3-status.md), PR433–434. Installed namespaces and actual retained process source/dependency bytes were checked. |
| R4 | Complete observation and historical learning paths using their own domain resources and original computations | [Observation](2026-09-10-control-layer-r4-observation.md), [learning](2026-09-10-control-layer-r4-learning.md), PR435–436; actual installed initial/replay/repeat runs in the activation report. |
| R5 | Reviewed installations, independent workers/readers, fixed legacy P3, archived and masked duplicate writers, real current report recovery | PR437–446; actual local-owner reviews, fixed deployment818/659 and recovery819/660. This report records the resulting business acceptance separately from earlier preparation and failed operations. |

The original estimate of 8–12 PRs was exceeded: PR427–446 comprise twenty
implementation, packaging, deployment-correction and evidence rounds. The added
rounds addressed actual packaging, identity/permission, legacy mount/Git/runtime
compatibility and settlement recovery failures. They did not introduce new
models, model families, scientific search or a replacement Research OS.

The source comparison against ac0ef783 shows only additions under `dehps/`.
The old public supervisor, repository, learning runtime/computation, notification
runner and original learning-results report remain unchanged. New capability
implementations are injected at entry; the generic execution core does not gain
historical incident IDs or experiment-specific dispatch. The exact 2026105
adapter lives under `deploy/execution`, outside that core.

## Cross-stage acceptance A1–A12

| Requirement | Evidence actually covering the requirement |
| --- | --- |
| A1: reject writes to formal/other-domain resources | Lifecycle/path-escape/symlink sentinel cases plus real OS and PostgreSQL permission denials; installed separate UIDs, private SCRAM sockets, readonly inputs and no production credentials in new workers. |
| A2: labels cannot manufacture independent review | Real login/OID/principal mapping, alias and SET ROLE attacks, reverse reviewer/executor checks, direct table/helper denials, execution-time reauthorization; actual owner review receipts rather than fixture identities for deployment. |
| A3: committed calculation survives lost acknowledgment | Actual PostgreSQL commit followed by session termination, independent resume processes and unchanged computation count; learning fitting function called only once across crash/resume/replay. |
| A4: one versioned verification rule | Injected verifier used for prepare, commit, readback, replay and downstream; `test_verifier_failure_blocks_every_replay_and_downstream_read` and corrupt-input rejection. Original historical verifier semantics retained. |
| A5: interruption/concurrency cannot create two successes | Full canonical FK parents, real process kills and DB restart, unique commits, leases/fencing, atomic registration and downstream interruption; no key transaction or state transition mocked. |
| A6: frozen scientific semantics retained | All 2,599 historical probability/loss rows, original checkpoint, full analysis, diagnostic examples and archived Top-100 compared; observer complete 100-ticket diagnostic/sample/text/HTML equivalence. Runtime envelopes and run IDs remain explicitly distinct. |
| A7: ambiguous mail never retries automatically | Existing durable notification idempotency/uncertainty regression retained and passed; real current operation added exactly one normal post delivery. No test email, forced resend or uncertain SMTP retry. The mail mechanism itself was not replaced. |
| A8: development cannot change in-service source | Fixed images/root-owned releases and real readonly namespace/dependency checks; development branch changed independently while P3 uses its retained ac0ef78 package. |
| A9: wrong/stale status cannot look successful | Actual HTTP/status consumer tests for domain/plan/release/execution mismatch, missing/stale data and revoked execution; deployed readers have readonly mounts and no DB credentials. Stale finished projections honestly become UNKNOWN. |
| A10: extension without core/P3/mail changes | `test_another_registered_capability_extends_completed_plan_without_core_changes` executes an additional deterministic capability using its own registration/config; two real deployed domains execute and replay without restarting P3 or requiring mail. |
| A11: history verifiable and V11 unschedulable | Original frozen validators and historical replay; post-recovery comparison of all 634 original events, 32,431 registrations and 31,734 registered files; actual V11 service/timer masks. |
| A12: point-in-time diagnostic boundary | Frozen decision before later-opened label/report extension, false/backdated prediction metadata rejection, original decision binding unchanged; historical diagnostics remain explicitly post-hoc and are not newly issued predictions. |

The required CI job uses PostgreSQL17 and runs the actual isolation/authority/
store/mainline/consumer integrations without a missing-database skip. Earlier
exact-head CI runs and local results are retained in their stage reports. For
PR446, run34571735772 allocated no runner: all six jobs had zero steps and GitHub
reported billing/spending-limit failure. The repository's quota exception used
the passing local two-test recovery suite, full report path, physical PostgreSQL
restart and four typed/generic replays. This was not green GitHub test execution.

## Actual recovery819 and history preservation

The owner personally approved Request819, decision3496, at 2026-09-11 15:33:09
Asia/Shanghai. Its protected receipt binds package index
`ff04a7ddc26d80610e9ff4a09d7bb92ea5c1de9072263a4e335903ebc6fdec5e`,
request payload `963ebef967e21a9e8760efc6d62fcf244b4ca2ead0f32bc350bf32427d562728`
and a finite expiry. Operator execution660 verified that actual review before
any operation and is now **COMPLETED**, with its actual runtime evidence attached.
The agent did not perform the human approval step.

The root-owned recovery release is
`/opt/dehps/releases/p3-2026105-recovery-2e36491`, authentic source
`2e36491c66500ac006ff148d4398e3ecca47c5c2` with 645 real Git commits.
Its 1,855 files were verified before and after installation. It reuses the
unchanged fixed dependency environment from retained-p3-r5-alias-f8ec526.
Installed read-only/no-network inspection passed the original scientific source
digest `139ddc97ce1d81ea4e6182359f8391532ed1911090db004bcdf9ebcdea5f9493`
and runtime closure `a37a36d0ad9d35d85b50d56dca4941698db63dbccb75c98a381c4e0c861ef4f7`.

At 15:35:49 the four approved timers were paused. Existing jobs drained and the
two fixed residents were idle: each had two bwrap wrappers and one Python leaf,
with no active database transaction. After stopping them, installed read-only
input preflight passed. The incompatible common resident was archived intact to
`~/.config/systemd/user/retired-r5-2026105-2e36491/` and masked at 15:36:01.

The recovery appended one Ready transition and ran exactly the original
settlement and settlement-replay capabilities. The new authentic Git identity
avoided collision with the old failed execution; no old identity was rewritten.

| Record | Identity |
| --- | --- |
| Preserved failed execution | 03ac1de3ef19cd0b4f7090381f0cea974c6506cf08072fd8b4d663a5116c07d5 |
| New settlement execution | 02596b0942508cf7e3e9d34239ef0ff0c20fec3c97cdfdb897e839222ccc5089 |
| New settlement replay execution | 0bdcf838923b89d90a090f7763e967346c734a7a82538cb5d832085a9bd38d4e |
| Settlement artifact | 5308a9cd0ef9d3a727731781b3c419040f3d3e4d87f0a940c8c736d13c21a95c |
| Settlement replay artifact | 31b01ed92ada48a7186a7d42a6ae75b5b34cb4159584d0bcfbcb14bc10946689 |

Both tasks passed typed and generic replay plus the original report consumer.
No completed model was retrained and recovery itself sent no mail. The watchdog
and four original schedules were restored by 15:39:06. No rollback was needed.
Original failed events and the absent failed-execution artifact directory stayed
unchanged. The immutable-history comparison passed at 15:41:11.

The isolated restart test permits the frozen supervisor to refresh the mtime of
one diagnostic projection with identical bytes. Immutable artifact bytes and
mtimes remain unchanged; this is not a claim of zero filesystem metadata writes.

## Report integrity and current business cycle

**2026105 CURRENT_REPORT_ACCEPTED.** Its original prediction was sealed before
the September10 draw; the original pre-mail sent record at 17:00:49 remains.
Recovery did not manufacture a past prediction or alter its 100 tickets.

The natural post-mail invocation `ea91bc1a207941baa4e93fb94ed8784e` ran
15:40:58–15:42:20 from the fixed legacy release. It returned
`POST_DELIVERY_SETTLED` for **2026105**, with both registered report tasks passing
typed/generic replay. This is fresh current-issue evidence, not an old
ALREADY_SENT record or merely a zero exit status.

| Report/consumer check | Actual evidence |
| --- | --- |
| Post report | ef412b7a603481b54810520fe2761a74ede32158eb15e3212f1c838dcedcd0c3 |
| Post replay | 7886725534d466d67e9a5cde488c4a72f4e3933545cb4e794287189e99fd5714 |
| Audited payout input | a04aaf0157f61f375b36cec866f65a2bf993ea655e53de66a053f349bccb4894 |
| Delivery ledger | Exactly one new 2026105/post/sent entry, completed 15:42:20; every old ledger entry unchanged. SMTP acceptance is recorded; recipient opening is not claimed. |
| Readable consumer | Fresh read-only original consumer validates sealed parents, settlement, payout and replay; stored report equals reconstruction through the unchanged original report builder. |
| Historical gap | 2026104 missed pre-draw window remains explicit and was not backfilled. |
| Next pre-mail | 2026-09-13 17:00 Asia/Shanghai, **PENDING_DELIVERY**. A future event is not treated as delivered or as a reason to rerun engineering indefinitely. |

Natural P4 invocation `68a9a6492b5c42f9ab19ed1db5569de5` completed normally;
no new scientific promotion is claimed. Natural P3 invocation
`c7aa798949bd458586adbd1ea2c826fc` ran 15:44:03–15:48:43 and returned
`REGISTERED_SETTLEMENT_ADVANCED_TO_NEXT_SEAL`. It added the next five canonical
task definitions without deleting or rewriting the existing 165 tasks.

2026106 has a new `SEALED_BEFORE_DRAW` checkpoint, 100 model tickets, 100 random
baseline tickets, 33 probabilities and unchanged blue strategy. Training ends at
2026105. Refit `4244a2b5868c320dd6906ca068faba3f61c9af3bd3eeb4c2423159b2965bdd71`,
predraw `1cd03b8abf22589092e53af3de58f3b08f34de16208a1fbce0dde1b7b85bb978`
and replay `67e418810b70b51eb5731c280551f8ff9f969132fefc19e7639bd6694ee37c63`
all returned REPLAY_VERIFIED. A fresh read-only original consumer validated the
registered checkpoint and parent chain; its human-readable report exists.
The actual final manifest is
`743379480f628e36259a1b031acb1978643273c15fc8eb64f0a41cef0372e67c`.
All five 2026105 tasks and three 2026106 pre-draw tasks are completed. Settlement
and delivery that require the next draw remain pending their legitimate time.

Report-impact verdict: **CURRENT_REPORT_ACCEPTED_AND_NEXT_SEAL_VERIFIED**.
No historical gap has been erased, no future mail is labelled sent, and retained
scientific uncertainty has not been converted into a claim of predictive benefit.

## Final entry arrangement and rollback

| Entry | Arrangement |
| --- | --- |
| Learning and observer | Separate fixed images, non-login UIDs, private PostgreSQL and explicit input artifacts. Initial/replay/repeat runs complete; workers idle, database and readonly status consumers active. All 23 tables per domain and all 6/3 runtime files remain identical to accepted snapshots after formal recovery. |
| Formal P3 forward and performance hooks | Original ac0ef78 executor/science in fixed retained-p3-r5-alias-f8ec526; not migrated into the new coordinator. |
| Pre/post mail and armed P4 | Original fixed ac0ef78 entries and schedules; report lifecycle separate from learning/observation. |
| Performance watchdog | Fresh process using the same fixed retained release. |
| Incompatible common resident | Original unit preserved, disabled and masked; no competing DDL/dispatch loop. Historical inactive tasks are not silently completed. |
| Old observer | Request815 cancelled, service/timer archived and masked; original facts retained. |
| Old learning transient | Terminal historical failed run retained; no restart or duplicate writer. |
| Draw sync | Fixed entry retained, service inactive and its previously disabled timer still disabled. |
| Other inactive runtime/monitor entries | Remain disabled; not introduced as prerequisites for new experiments. |
| V11 | Service/timer remain masked; no restoration, replay, request or scheduling. |

The reviewed recovery package contains the exact commands and rollback. Before
any possible business append, failures restore original unit/configuration and
activation. After a possible append/commit, rollback preserves all facts, keeps
the offending duplicate writer masked, pauses future triggers and restores the
watchdog; it does not delete evidence, retry ambiguous delivery or repeat recovery
blindly. Existing releases and prior failed deployments816/817 remain archived.
The earlier fixed-release rollback must not be used to reactivate retired writers
or undo this later recovery's durable facts.

The Goal → Resolver → Ready Queue → Supervisor → Capability → Artifacts → Status
→ Next Consumer chain has actual deployed proof for both independent domains.
**YES — validated by unified mainline execution and replay.** Scientific benefit
remains unproven. No further framework, model family or continuous search is part
of this engineering closure.

Durable local evidence is in the Codex task's
`r5-2026105-recovery-20260911` directory: protected-review binding and
operator-819-execution-started.json; installed-recovery-namespace.json;
recovery-operation.jsonl; canonical-recovery-result.json;
production-history-continuity.json; learning/observer-unchanged-after-819.json;
natural-post-result.json; current-report-acceptance.json; final-runtime-acceptance.json;
operator-819-completed.json and the readable report.
Generated data and credentials are not committed. Publishing this Markdown and
the checkpoint changes no installed source, runtime setting, contract or schedule;
that documentation publication has **NO_RUNTIME_IMPACT**.
