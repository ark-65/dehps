# Historical authenticated preflight repair — Engineering829

The attempted Operator828 deployment stopped before runtime approval because
`request_get` authenticates its database identity with `SELECT ... FOR SHARE`.
The host reader incorrectly enabled PostgreSQL transaction read-only mode,
which rejects that lock. Its previous test checked the transaction setting but
never exercised the actual preparation CLI. The original root-private failure
and the entire failed827 packet remain retained.

Engineering829 was approved through actual ark sudo authentication, explicitly
delegated by the owner for this exact request, and execution667 reauthorized
implementation. This is distinct from an agent claiming Reviewer authority.
The clean implementation base is main5294ad9. The primary goal is to repair
host inspection and publication. Model computation, research contracts,
generic executor authority, SQL schemas/grants and FormalP3/V11/mail are out of
scope.

The historical reader now exposes exactly four existing authenticated read
statements: request_get, read_plan, read_result and mainline_context. Normal
transactions retain the identity row locks; writes, admission, claims, commits,
registration and approvals are rejected before execution. Raw connections and
cursors are not returned. This prevents accidental writes through this reader;
it does not claim to sandbox arbitrary Python or replace scoped SQL privileges.

A separate historical read context permits actual root to inspect the known
learning61010 and observer61011 owners. Generic RunContext still rejects a root
writer against service-owned domains. Artifact preparation and projection
writes are explicitly disabled; existing descriptor traversal and size/digest
verification remain in force. Wrong domain owners are rejected.

The successor host template uses separate829 staging, configuration, SQL login
and input paths. Failed827 bytes and submitted828 are never replaced. Accepted
827 worker images, their exact plans and the594-prefix continuation contract
are retained after a dependency/diff audit; only the publisher/host read surface
changes. The original expiry2026-10-15T00:55:24.344038+00:00 and <=24h continuation
cap remain. No original budget is restarted or extended.

## Validation and integration

Regression validation invokes the real preparation CLI in a fresh process
against disposable PostgreSQL, then repeats it as actual container root with
61010/61011-owned fixture roots. Every authority/store/public table count and
all pre-existing status/blob bytes are compared before/after. A mixed-release
publisher case consumes the retained prefix, adds two independently registered
reports and replays both domains without adding records. Existing continuation
crash/concurrency/revocation/deadline and formal-window checks are retained.
All49 targeted checks passed (195.88s); validation.xml records exact cases.
The initial regression test harness first used the wrong DSN variable, then
expected the wrong rejection text; those failed logs are retained. The actual
root/service-owner CLI case passed, and the final complete run passed.
All17 formal hashes remained unchanged after engineering validation.

| Integration link | Engineering evidence | Production status |
| --- | --- | --- |
| Goal, resolver, ready queue, supervisor | Existing singular coordinator in disposable SQL domains | Exact successor admission required |
| Historical capability and immutable artifacts | Retained prefix plus two canonical updates | Original594 retained; new release pending |
| Status and independent report consumer | Actual observer and readable reports | New release pending |
| Deterministic replay | Fresh CLI plus mixed-release read replay, no additional records | Full original prefix rechecked at admission; new full batch pending |

Production completion: **NO — INTEGRATION_PENDING**. This engineering repair
does not establish prediction improvement or claim training has restarted.
The successor Operator packet must bind the accepted publisher, unchanged
workers/plans, input inventory, formal baseline and stop-only rollback before
actual runtime approval and execution.

## Report impact and continuity

Before implementation, the exact current formal issue2026108 was sealed at
2026-09-15T22:05:55.196395+08:00 using data through2026107, ahead of the
2026-09-17T21:15:00+08:00 draw. Its registered sources, replay and readable report
were present. Delivery is PENDING_DELIVERY (next predraw mail2026-09-17 17:00),
not delivery acceptance. All17 protected report/source/mail-ledger/unit hashes
matched the previous accepted baseline at the start of667; enabled timer state
was captured separately. The2026104 original-prediction gap remains explicit.

Report-impact verdict: the change repairs the independent historical reader
used for prefix admission and observer publication. It does not modify formal
source bindings, generic SQL/executor code, formal units or mail. Before/after
hashes and timer evidence are retained under runtime/historical-preflight-829.
Production report acceptance still requires two fresh updates/reports and final
batch replay under the separately approved operation; no acceptance mail is
sent. Ordinary scheduled mail may legitimately change its ledger during long
acceptance; retain any strict-baseline refusal and inspect the actual entries.
