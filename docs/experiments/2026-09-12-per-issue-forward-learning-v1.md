# Per-issue independent forward learning — implementation and contract

Owner scope consent: the current task's approved plan and explicit instruction
“我完全批准任何操作，直至计划完成” on 2026-09-12. Request820/execution661
records that consent by proxy; this is not an authenticated local Reviewer login
or a separately performed independent agent review. The implementing identity is
codex-thread:01a08fc3-d968-7341-9743-0bb657005ad5. Engineering is the current role.

Base: remote main26b1d7f, separate checkout. Formal P3 remains on its original
root-owned ac0ef78 release. Before implementation2026106 is sealed and replayed,
next pre-mail2026-09-13 17:00 Asia/Shanghai is PENDING_DELIVERY and draw time21:15.
2026105 has one pre/post sent record;2026104 remains an explicit historical gap.
Mail ledger SHA before changes:
78c05bb3bf59ac461c23e6216e20635cc8bde0bc2c4b84fcbb2bf2a8d443ca43.

## Frozen scientific definition

One primary model: existing expanding shrink900; controls: old alpha1 and
uniform6/33. Retain the existing formulas and 900-issue minimum. No features,
blue model, tuning, selection, promotion or result-dependent window changes.
Use all33 red labels and preserve all16 blue labels. An omission is a process
trace, not a causal explanation of the draw. Unestablished causes remain
证据不足. The candidate sampler is the existing uniform legal sampler, 10,000
unique combinations and100 selected tickets, descending composite score and
ascending lexicographic ties; the old and shrink900 arms share this fixed pool.
Pool seed binds contract and target issue, not future labels. Blue-by-rank is
the preserved deterministic strategy. Selection diagnostics are secondary.

At deployment freeze exactly60 explicit issue/date/deadline records from the
canonical calendar, the initial admitted history, export verification key and
scientific contract hash. Across year boundaries or calendar revisions, never
guess replacement issue identities: conflicting audited dates halt the relevant
input. A missed seal remains a gap and is never backfilled or replaced. A gap
prevents a favorable completed-window conclusion; describe available scores only.

Score the sealed prediction before absorbing the newly audited label. Main
endpoint: mean33-number Bernoulli log-loss, equally weighted by issue. Brier,
fixed20 calibration bins and all-ticket hit/exposure diagnostics are secondary.
Final analysis occurs once after the fixed60 targets; no interim aggregate
decision. Reuse the original paired circular block bootstrap: block13,
4,000 replicates, seed20260905, family8 (retained conservatively even though only
two primary contrasts remain). Both family intervals must have upper bound<0
for “本窗口观察到改善”; both controls must be beaten. Otherwise report
“未改善” when either entire interval is nonnegative, else “证据不足”. No
claim of confirmatory power or formal Evidence/Promotion credit follows.

## Declared integration and acceptance

| Task | Ready/upstream | Output and next consumer |
| --- | --- | --- |
| seal(t) | Frozen contract/history, predecessor score; actual clock before cutoff or explicit late gap | Immutable checkpoint,100-ticket trace; score(t) |
| score(t) | Committed seal and signed audited opened label | All labels/errors and next-update sufficient statistics; seal(t+1) and report |
| report(t) | Committed score and next seal, or terminal window | Machine/readable independent report; reader and replay |
| final analysis | All60 terminal issue scores | Paired intervals, gaps, honest conclusion; independent report/replay |

All tasks use the existing canonical Goal/Resolver/Ready Queue/Coordinator and
atomic file/PostgreSQL registration. An injected readiness check may defer a
task without claiming/failing it; it cannot grant authority or create a fact.
Inputs arrive through a separately trusted, readonly production exporter. Worker
credentials cannot write production or sign inputs. The export key and fixed
scientific definition are admitted together. No domain consumes another domain's
status projection as proof of completion.

Status and Evidence are separate: per-task execution, waiting reason and actual
run identity feed the existing readonly status interface; the scientific result
remains unproven. Readonly replay never fits, updates or refreshes a timestamp.
Signed input replacement, future labels, wrong issue/date, repeated events and
past-time seals must fail closed. A missing payout never blocks probability
scoring. Report failure must not block the next model update or formal mail.

Required checks: actual PostgreSQL end-to-end execution, fresh-process replay,
duplicate/concurrent trigger, lost commit acknowledgment, interruption/restart,
expired/revoked admission, all labels and deadline/availability boundaries.
Prepare release/rollback before installing. Boot activation covers independent
databases/readers only; a bounded admitted trigger schedules eligible tasks.
Completion requires one real seal/open/score/next-update/report/replay cycle;
until then report NO — INTEGRATION_PENDING / WAITING_FOR_REAL_DRAW.

Report impact at development start: no installed source, P3, timer or delivery
change. Lifecycle writes are request/audit metadata only. Before release and
after deployment repeat the exact-issue report/provenance/replay/ledger/timer
checks; do not infer delivery from future schedules or old ALREADY_SENT.

## Engineering validation and release boundary

The implementation adds 181 learning tasks and 60 separate observer tasks. The
final learning report consumes the final analysis. Readonly prefix replay makes
partial forward progress verifiable without requiring future draws or refitting.
Calendar source bytes, initial history, signer key and target list are content
bound. Source export requires a matching actual audit event in a readonly source
transaction. Signed publication uses fsync and no-clobber links, preserves first
availability on repeats, and rejects a conflicting later correction.

Source-side checks on September 12:

- 164 focused Worker/actual PostgreSQL checks passed in 331.98 seconds. Surfaces:
  forward contract/calculation/publication, complete 181-task gap window, separate
  observer DB consumption, new-process replay, coordinator/store/authority,
  current readonly status consumer, preserved observation and learning paths,
  canonical resolver/completion facts and execution authorization.
- API: 122 tests passed; TypeScript build passed. Input waits, report failures
  and expired admission remain distinct, with exact request/plan/release binding
  and no borrowed execution ID.
- Separate formal P3 report and readonly API regression command: 56 passed.
- Actual deadline-crossing transaction: no committed artifact or canonical
  registration survived rollback; recovery produced an explicit missed seal.
- Real lost-acknowledgment/repeated-trigger test: two fitting calls for two
  checkpoints, four learning commits, five attempts including one failed report,
  eight canonical events and four artifact registrations. The independent
  observer consumed the signed report in its own PostgreSQL database and did
  not fit. These are synthetic engineering fixtures, not real draw acceptance.
- Full 60-gap window: 181 commits/attempts and 362 canonical events; final report
  consumed the insufficient-evidence analysis. No retrospective fitting occurred.

The large DAG exposed repeated digest/regex work in completion-fact lookup.
Matching now compiles the same exact expression once per task; no completion
criterion changes. Verification can reuse exact immutable task/commit/byte
results within a synchronous traversal, while rereading bindings and checking
artifact hashes. New runs and replay rebuild their proof from an empty cache.

The installed-image revocation check and release artifacts are recorded in the
separate preparation packet after the committed image is built. The candidate
systemd syntax check currently reports only the expected absent, uninstalled
`/opt/dehps/releases/forward-publisher/venv/bin/python`; it is not boot acceptance.
See the [release and rollback runbook](../../deploy/execution/forward-learning-runbook.md).

| Integration step | Engineering fixture | Prospective runtime |
| --- | --- | --- |
| Goal, Resolver, Ready Queue, unified executor | Verified | Pending exact admission |
| Seal, score before update, next checkpoint | Verified with native clocks/DB | Pending canonical calendar and real draw |
| Immutable artifacts, ledger, status | Verified | Pending new release activation |
| Independent report consumer and replay | Verified in separate databases | Pending real-cycle evidence |
| Fixed-window final analysis consumer | Verified, including all 60 gaps | No prospective conclusion |

Overall: **NO — INTEGRATION_PENDING**. No new scientific Evidence, model
promotion, production timer installation or prospective experiment is claimed.
The standing owner consent is not independent scientific review or authenticated
runtime admission. Exact calendar coverage and separate Reviewer/Operator
bindings must be resolved before activation; no expired approval is reused.

Formal report impact during engineering: **NO_RUNTIME_IMPACT**, established by
the dependency/diff audit and current live observations. In-service Git remains
clean at ac0ef78; formal units still select the fixed retained release, not this
checkout or the new generic coordinator. No formal SQL schema, mail module,
frozen P3/learning calculation, notification ledger or timer was changed.
The readable 2026106 report binds training end 2026105, model
34fbe8519c00602d2b20a793fba62054a2b1b16620c054015b34414de235cc96,
seal 2026-09-11T15:46:48.105228+08:00 and draw September 13 at 21:15.
The live forward timer still reports `WAITING_FOR_AUDITED_DRAW` for 2026106;
mail ledger SHA remains the before value above. The next pre-mail remains
September 13 at 17:00, `PENDING_DELIVERY`. The four previously started independent
database/status services are running; their existing units remain static until
the separately reviewed boot target is installed.
