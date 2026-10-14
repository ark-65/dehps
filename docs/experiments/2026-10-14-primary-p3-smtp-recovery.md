# Primary P3 SMTP recovery — Engineering 855

One goal: repair primary pre/post mail transport and reconcile the preserved
2026117 post attempt. Engineering execution692 uses the owner's continuing
repair/restart authorization and explicitly delegated approval, recorded against
the verified ark uid1000 principal. This is not independent agent review.

## Report impact before implementation

2026117 was genuinely sealed before the October13 draw; pre mail was sent at
17:05:48 Beijing. Its complete post report and registered deterministic replay
exist. Post delivery at22:19:49 failed with QQ SMTP `SSLError`; the exact original
ledger row is `uncertain`, has no Message-ID and must remain intact.
Post report digest is `e7034de5963197ea69315373cdb95d519c2ea2465bdb8a8b56489fe1c20f6cc7`;
replay is `1a9ae0966038c2367d8f6d2da64e262c1c0afa86d07d9600eb7b394690112f65`;
delivery is `825b8d5c7f44605db65dd0ff7a24adad5dbde8d6e1abf1e92409ba6eaf14abb1`.
Next primary pre trigger is October15 17:00 Beijing. Existing source/admission
expiry checks remain authoritative. Historical recovery expires October15
08:55:24 Beijing and its successful117 post delivery is outside this change.

Current status is NO — INTEGRATION_PENDING. A restart cannot prove delivery.
The old exception does not identify whether DATA was submitted; no safe retry
can be inferred from the absence of a sender IMAP copy or a now-healthy socket.
Read-only TLS1.3 and TLS1.2 connection/login/NOOP/QUIT diagnostics passed without
DATA. Sender INBOX/Sent/Junk contain no matching SMTP copy; that is not proof
of non-delivery. Recipient mailbox/provider transport reconciliation is pending.

## Declared integration and boundaries

Existing primary notification Goal → canonical report Coordinator/Resolver and
Ready Queue → unchanged report and replay artifacts → existing presentation
consumer → exact registered delivery identity → immutable transport receipts
and original ledger → existing timer's next invocation.

Ready: same issue registered report, official payout and REPLAY_VERIFIED.
Runner: retained primary scientific source/dependencies and presentation entry.
Upstream: original seal, audited settlement, report and replay. Downstream:
unchanged subject/text/HTML, recipient and ticket/accounting semantics; durable
Message-ID and SMTP phase receipts. Evidence: operational only, no scientific
credit. Status: canonical task facts plus separate transport/wait receipt.
Decision/next consumer: exact dedupe and existing primary pre/post mail timers.

The repair is an additive entry/transport adapter. It keeps original contracts,
source bytes, failed events, ledger rows, and model/training paths. It retries
only bounded transport failures proven before DATA, retains genuine ambiguity,
and treats accepted DATA separately from connection cleanup. It sends no test
mail. Production switching needs a fixed reviewed package, scoped Operator
execution and rollback removing only this entry switch.

## Acceptance

Engineering and production evidence will be appended here. The 2026117 post
delivery remains blocked until positive provider/recipient evidence establishes
acceptance or non-submission. No blind resend or rewritten `sent` claim is allowed.

Focused isolated validation under the earlier requested SMTP failure verification:
`python -m pytest -q tests/test_primary_transport.py tests/test_mail_service.py`
passed19 cases (nine additive cases and ten retained mail cases), without network
or test mail. It covers accepted DATA followed by QUIT SSL failure, failure after
acceptance, safe pre-DATA retry with one Message-ID, unknown DATA blocking,
bounded durable retry, untouched old uncertain state, lost ledger acknowledgement
and corrupt receipt rejection. Scoped Ruff and diff checks pass.

The implementation retains all frozen files and the old presentation package.
Only the mail entry imports the additive transport; it does not change the
training scheduler, strategies, scientific source contracts, public API or DB.
The canonical report/replay consumer runs before a normal new SMTP transaction;
an exact unknown old record returns a visible wait before expensive recompilation.
Current original ledger SHA256 is
`249a438f86b056966b23964f3f6c4e2a3730cff0ba1f0c442320ab1ccc7e80a4`;
frozen CLI remains
`92a387d0ec74039111d38e2886f2dde1b6736ee9d79285d88efdef9e59e73506`.
117 pre HTML is `491a8caaf0bc538ea915e06ebcf66fc85ec4aab08d8e0607e2cdf7b422743095`;
post HTML is `7db9274a1d800157bcbeef3c23adce592b82868ef67f8b7defdff31fc01b1dc5`.

The owner replied that the old message could not be found. This is retained as
manual diagnostic context, not provider-confirmed non-submission. The release
contains no old117 resend approval or fabricated transport proof.
