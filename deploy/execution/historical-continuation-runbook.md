# Fixed historical continuation handoff

Use Engineering827's accepted commit and immutable release builder for both
workers. Package the exact continuation contract, both plans, images, input
manifest, publisher inventory, old helper hashes, formal baseline, and rollback
references. No SQL schema change is required. Old inputs/releases remain intact.

`historical-continuation-host.py` is a fixed-package template, not a development
entry. Copy it into the packet as `continuation-host.py`. Stage verified bytes as
root-owned, non-writable files using the retained hash-bound staging pattern.
The new stage is `/opt/dehps/releases/historical-continuation-827`; configuration
and publisher use separate `historical-continuation-827` paths.

The packet must bind the accepted commit, original contract, both new and prior
release identities, exact plans/prefix, original expiry, <=24h continuation
budget, finite `review_before`, and exact typed Operator request key. The
`files` map covers every packet member except the packet itself; the external
entry pins the packet and staging program SHA256. Preserve original helpers at
their existing path and pin their bytes under `retained_helpers`.

The real ark sudo terminal invokes `review PACKET_SHA`. It authenticates the
installed UID/machine mapping, completed Engineering827, independently scoped
SQL Reviewer sessions, and the exact outer request. It neither accepts a chat
identity string nor invokes training. Actual prefix replay under read-only
transactions must reproduce the packaged contract before approval. It waits
for a separately recorded Operator execution before handing install to a
bounded system service. Never call this entry as Engineering to self-approve.

`install PACKET_SHA OPERATOR_EXECUTION_ID` verifies that actual lifecycle
identity and root review receipt before touching the historical units. It
pauses only those units, rechecks the prefix and runs old fixed-image replay
under the actual service UID. New input roots keep old files untouched; domain
locks, narrow credentials, source access, cgroups and service limits remain.
New plans are admitted before publication; missing dispatch cannot start a fit.

The acceptance service records runtime identities, current progress, two new
issues and independently readable reports, then enables the original15-minute
historical timers. It continues bounded batch acceptance and fresh-image replay.
Do not equate STARTING/missing count, no new draw or a temporary18—22 guard with
zero progress/failure. A permanent task error, expired budget, source damage or
auth failure stops acceptance and preserves the exact private error record.

Rollback under the admitted Operator operation stops only
`dehps-historical-publisher.{timer,service}` and
`dehps-historical-worker@{learning,observer}.{timer,service}`. Keep new plans,
SQL records, artifacts, failures and original sources. Do not restart the old
expired batch or remove evidence. Saved old reader environments and publisher
guard bytes are for inspection; restoring readers is a separate explicit
identity-bound operation if needed, not an automatic deletion/rewrite.

Never modify FormalP3/V11, fabricate2026104, send acceptance mail, extend the
original30-day admission, restart the ended12-hour watch, or use Docker to
circumvent unavailable sudo. If actual host authentication is absent, finish
the exact packet and report that concrete entry, not another request for intent.
