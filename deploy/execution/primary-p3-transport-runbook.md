# Primary SMTP transport release

Scope: retained primary pre/post presentation consumers only. Keep the original
report, task/replay artifacts, prediction source, ledger rows and timers. Never
reset or delete an old sending/uncertain row. Missing IMAP copies or a user's
not-found result cannot establish non-submission.

1. Inspect the clean worktree, exact issue117 report/replay, original ledger,
   namespace/presentation release identities and user timers.
2. Complete Engineering855 under its recorded owner-delegated decision. Package
   only `primary_transport.py`, `run_primary_p3_transport.py`, and transport
   `launch.py` from the accepted PR commit. Include SHA256s in `package.json`.
3. Create a critical Operator release Request binding this package, reviewed
   accepted commit, transport source and entry hashes, retained850 package,
   original row/report/replay identity, allowed services and rollback. The
   Operator admission in `release.json` binds its exact typed payload digest.
4. Authenticate the authorized Operator and install a root-owned, non-writable
   package under `/opt/dehps/releases/primary-p3-transport-855`. Save the immutable
   old ledger snapshot, report/timer/source hashes and drop-in contents separately.
5. Run its `--mode replay` entry without `--deliver` for exact117 pre/post. Require
   unchanged content/identity, registered deterministic replay and no SMTP.
6. Add one later-sorting pre/post user service drop-in selecting the package
   launcher. Preserve existing ExecCondition and timer schedules. Reload and
   restart only the two primary mail timers and the post mail consumer.
7. The post consumer must return `WAITING_TRANSPORT_RECONCILIATION` for old117
   without opening SMTP or rewriting its ledger row. A fresh DATA250 receipt
   proves acceptance even if cleanup or ledger acknowledgement fails. A known
   pre-DATA transient error may retry at most six connections under the exact
   delivery identity; any DATA ambiguity stops further delivery.
8. Record before/after issue artifacts, immutable old row, read-only replay,
   actual delivery status and next enabled timer trigger. Do not report full
   recovery until the real117 mail is reconciled and delivery is confirmed.

An old117 retry requires a reviewed immutable `reconciliation` entry with exact
registered email/content identity, original row digest, provider evidence SHA256,
`outcome=NOT_SUBMITTED` and
`evidence_kind=PROVIDER_CONFIRMED_NOT_SUBMITTED`. Bind the receipt in a new exact
Operator package. Positive received-message evidence should be recorded as
acceptance; do not send that report again. A provider log/screenshot needs its
actual outcome, not merely an absent search result.

Rollback: remove only the two added `primary-transport-855` drop-ins, reload the
user manager and restart its two unchanged primary mail timers. Keep all original
and new receipts, ledger rows, failure records and installed release packages.
Do not restart the training supervisor, Formal P3, V11 or historical services.
