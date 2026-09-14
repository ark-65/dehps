# Historical report learning and bounded incremental intake

Engineering Request 823, approved by the authenticated local Reviewer `ark`
(UID 1000), decision 3512; Engineering Execution 663. Request 822 is retained.
Base: `3c774fbb726bee6f2f0d952094c6f4dab3f73d26`, isolated worktree.

The goal is to run fixed shrink900 over audited historical labels immediately,
then accept new opened reports for 30 days. No model selection, new omission
features, blue training, production promotion, or new forward experiment is
included. Original reports are evidence, never instructions or labels. Missing
2026104 predraw evidence stays a gap even when its label is used in reconstruction.

## Contract declared before implementation

| Component | Binding |
| --- | --- |
| Goal | Historical reconstruction followed by bounded incremental intake |
| Ready | Authenticated scoped admission; frozen input identity; prior committed checkpoint; complete audited opened label; formal workload idle |
| Runner | Existing execution entry, capability factory, Coordinator and Ready Queue |
| Upstream | Frozen history, machine evaluation/reference archive, signed append-only label envelopes |
| Downstream | Per-issue pre/post statistics, all 33 red and 16 blue labels, scores, complete omission diagnostics; separately retryable reports |
| Status | Existing execution-status.v2, bound to the new plan/release/execution; derived batch and report progress |
| Evidence rule | Descriptive historical reconstruction; engineering success cannot establish predictive improvement |
| Decision consumer | Versioned verifier at commit, readback, independent observation and replay |
| Next consumer | Next update, report, independent observation, batch summary and readonly replay |

The immutable task plan reserves 32 incremental input slots within the 30-day
admission. These are intake capacity, not guessed issue identities or a required
sample window. Empty slots wait without fitting; filling them requires a signed
audited source prefix in issue order. Capacity or authorization exhaustion pauses
writes. Neither causes automatic approval extension. The historical batch is a
separately identifiable completed prefix and does not wait for these slots.

Warmup is exactly 900 rows. Each historical issue gets its own atomic registered
update and checkpoint, then a separate retryable report. The first batch deadline
is 24 hours from its committed start and survives restarts. A single compute
worker per domain and one BLAS thread remain below the two-worker ceiling.

## Report integrity baseline

Current formal issue: 2026107; draw 2026-09-15 21:15 +08:00; predraw mail due
2026-09-15 17:00 +08:00. The existing predraw seal was made on 2026-09-13;
delivery remains PENDING_DELIVERY. Formal source checkout stays at ac0ef783.
The exact file hashes, timers and mail ledger are recorded in the uncommitted
engineering evidence `runtime/historical-report-learning/engineering-663/before.json`.
Changes use separate fixed inputs, independent databases, status bindings and
units. No formal schema, P3/V11 artifact, source contract or mail path is changed.
Shared coordinator/API changes, if needed, require isolated regression evidence.
No acceptance mail is authorized.

## Acceptance status

Code implemented; production integration remains **NO — INTEGRATION_PENDING**.
Runtime admission is separate from the engineering approval. No historical
production activation, full-batch completion or predictive improvement is claimed
by this source report. The complete-batch engineering run is still underway;
its immutable checkpoint and execution evidence remain in the isolated runtime.

The actual frozen input contract is
`48a01bbb3e4ae4fc26616dc8309d6a97ad1c148038e3c1b6ff984f7aa0841346`:
3503 complete labels through 2026106, 2603 historical evaluations after 900 warmup
rows. This includes the verified original 3499/2599 plus four later audited draws.
The new plan has 5272 learning tasks and 2636 separate observation tasks, including
32 empty incremental slots. No 2026107 outcome is present. The 2026104 original
prediction gap is retained.

Real disposable PostgreSQL tests passed for two consecutive updates, lost commit
acknowledgment, separately retried report rendering, duplicate and concurrent
triggers, actual process SIGKILL and committed-checkpoint recovery, authorization
expiry/revocation during calculation, independent observation, and fresh-process
replay with fitting prohibited. The final focused historical/core group passed
26 tests. Mainline completion matching/control-plane/supervisor checks passed 64;
earlier forward calculation/release and supervisor checks passed 75. These groups
overlap and are not added into a single total. Forward mainline/database installer
regressions passed 11 checks; API passed 123 tests and its build. New systemd unit
definitions passed static verification; this does not prove they are enabled.

The full real-data engineering fixture first witnessed issues 2009076 and 2009077:
learning run `82287f6d-d805-43c3-8335-0a7fc0cda97d`, observer run
`776d8a4b-6290-4ce1-af2e-96abaf658b3e`. PostgreSQL contained five producer commits
(freeze, two updates, two reports) and two independent observer commits. Readable
reconstruction and separate original audit views exist. These authenticated
fixture roles and fixture release bindings are **not production admissions**.

Large-batch verification revealed repeated immutable-plan parsing, repeated SQL
payload scans and quadratic completion-fact matching. The necessary shared changes
retain canonical definitions, resolver/queue transitions, exact task/parent/plan
matching and every actual authorization check. The private SQL index has no
public write grant and is protected against mutation. A synthetic completion
state over the real 5272-task frozen plan, with 2000 completed tasks, reduced one
completion-validation pass from 1.068 seconds to 0.0098 seconds. Exact matching
tests cover malformed facts, changed task digests and multiple execution IDs.
This timing is engineering evidence, not a prediction result.

The first test invocation after recovery omitted the worktree PYTHONPATH, causing
three child-process imports to load the old installation and fail before execution.
The corrected worktree environment passed. An earlier full-batch fixture was
interrupted before model updates while large-plan admission was being optimized;
its evidence is retained. Later full-batch restarts preserve committed updates
and use the same finite fixture admission, without approval extension.

## Integration matrix and report impact

| Path | Isolated engineering proof | Deployed historical task |
| --- | --- | --- |
| Goal → Resolver → Ready Queue → Coordinator | Real PostgreSQL, exact plan membership | Pending exact runtime admission |
| Score → complete-label update → checkpoint | Consecutive updates and recovery verified | Pending fixed-release execution |
| Registered report → independent observer | Separate database, readable original/reconstruction views | Pending actual consumer |
| Replay → retained evidence | New process, no fitting or appended records | Pending deployed replay |
| Historical batch → incremental intake | Ordered/deduplicated inputs and timer definitions verified | Batch and timer activation pending |

Engineering report-impact verdict: **NO_RUNTIME_IMPACT**, supported by the
isolated worktree and dependency audit: formal workers execute the retained
`ac0ef783` source through a fixed mount namespace, not this modified shared source.
All nine retained namespace entry bindings were verified without execution.
Current 2026107 has seven verified registered artifacts, an actual predraw seal at
2026-09-13T22:04:22.542528+08:00, REPLAY_VERIFIED, and a human report matching its
registered text. The mail ledger remains
`bab7ab42ee1c04360615eb7050f9bdb6f1985a7946cd940e446d08f2d1424925`.
Future 2026107 delivery remains PENDING_DELIVERY. No formal service, source,
database schema, P3/V11 artifact or notification route was changed; no mail sent.

Release/activation acceptance must append the exact fixed package and runtime
IDs, complete batch and independent replay, actual readable registered reports,
enabled 15-minute timers and boot recovery, and another current-issue report-chain
comparison. The two independent databases alone may receive migration 004;
installation and runtime authority must be recorded separately from Engineering
Request 823. Historical performance remains descriptive and **证据不足**.
