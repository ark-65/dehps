# Primary P3 report style alignment

Engineering request 848 / execution 685. One goal: make the existing primary
pre-draw Top-100 and post-draw monetary report as readable as the omission report.
No training, ranking, candidates, prize/tax calculation or scientific conclusion
changes. No mail resend or test email is authorized by this round.

The HTML uses red/blue ball badges, a prominent cost/return summary, winners first
and the complete original 100-ticket table. Post-draw red hits are highlighted.
The primary registered estimated tax, after-tax receipt and net-return accounting
is preserved. Subject and plain-text alternative stay byte-for-byte identical.

## Canonical integration

| Contract element | Binding |
| --- | --- |
| Goal | `PRIMARY_P3_REPORT_PRESENTATION_V1` |
| Ready / upstream | Existing registered primary envelope/report, sealed candidates, typed and generic original replay |
| Resolver / queue | Existing Research OS control plane; separate additive presentation task pair per issue/kind |
| Runner | `PresentationSupervisor`, restricted capability map, existing `ResearchEvidenceSupervisor` atomic execution |
| Artifacts | Immutable HTML/source presentation and deterministic presentation replay; original artifacts unchanged |
| Status | Separate presentation supervisor state and lane projection |
| Evidence | Zero scientific credit; no training or promotion |
| Next consumer | Registered replay consumer, readable HTML projection, original delivery service and original ledger |
| Deterministic replay | New-process read-only replay; no training, records or mail appended |

The retained namespace and frozen mainline source remain unchanged. A protected
additive launcher reuses the existing namespace command and selects only the new
mail consumer entrypoint. It calls the original CLI with `apply=True, deliver=False`
before running the registered presentation tasks. Issue selection, pre-draw
window, payout-source acquisition and original replay therefore remain canonical.
Immediately before pre-draw delivery, the actual deadline is checked again.

The original delivery key includes original report/replay/recipient identities;
presentation deliberately preserves this key. Previously sent or uncertain mail
cannot become eligible for a second send because HTML changed. The existing
ledger remains the only SMTP deduplication path. Delivery failures retain its
existing uncertainty and manual-review handling. Presentation/projection failures
stop before SMTP; committed tasks can be replayed without recalculating models.

## Report integrity baseline and acceptance

- At start on 2026-09-23, formal worktree is clean at `ac0ef78`; effective mail
  entries use retained package `retained-p3-r5-alias-f8ec526`.
- Issue 2026110 has original registered pre/post reports and sent ledger entries.
  Its primary accounting is cost 200, gross/after-tax 25, estimated tax 0, net
  -175, ROI -87.50 percent; the renderer preserves these exact values.
- Current issue 2026111 was sealed on 2026-09-22 at 21:53:22 Asia/Shanghai;
  next pre-draw delivery is 2026-09-24 17:00, with the 21:15 draw deadline.
- Snapshot `runtime/style-848/protected-before.json` contains 84 protected files:
  exact-issue primary artifacts, ledger, source contracts, omission reports and
  original service/timer files. Runtime output is retained outside git.
- Focused tests cover preservation including tax-bearing cases, HTML escaping,
  count/duplicate/winner/sum/seal drift, task readiness, tampering, original sent
  and uncertain ledger behavior, and immutable readable projection retries.
- Real disposable PostgreSQL tests exercise pre and post render/replay via the
  unified supervisor and a new read-only process, conserving records and files.
  These isolated tests use synthetic canonical parents; actual registered-source
  loading is separately required at production acceptance.
- Both real-issue HTML previews were rendered in Chrome and visually inspected.

Engineering status: `NO — INTEGRATION_PENDING` until the separately approved
Operator release executes the accepted package in the actual primary namespace,
reads registered 2026110 pre/post sources, commits all four presentation tasks,
consumes readable reports and passes new-process read-only replay. Report-impact
acceptance must additionally compare the protected snapshot, verify current
2026111 provenance/replay and confirm unchanged timers and ledger. Future scheduled
delivery remains `PENDING_DELIVERY`; deployment does not prove SMTP delivery.

Deployment adds only two mail service drop-ins. Rollback removes those exact
new drop-ins and reloads the user manager, restoring retained original entries;
all committed presentation, failed events, originals and ledger evidence remain.

## Relocated-entry correction (Engineering 850)

Operator 849 staged the fixed package but stopped at entrypoint import before
registering any presentation task or sending mail. The retained bootstrap placed
the new script's directory on `sys.path`, so the original canonical CLI was not
found. All 84 protected files remained unchanged and no service entry was switched.
The original failure log remains in `runtime/primary-style-849`.

The correction explicitly locates the canonical scripts directory through the
frozen `ROOT_DIR`. A sparse relocated-package regression test reproduces the real
bootstrap, with only the additive files in the new release, and exercises both
current and retained dependencies. Scientific and presentation calculations are
unchanged. Deployment must use a new immutable package and successor Operator
request; the failed package and authorization history are retained.
