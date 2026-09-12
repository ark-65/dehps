# Per-issue forward learning release and rollback

This is a deployment candidate, not an admission or a completed real-draw run.
The scientific definition and integration matrix are in
[the round report](../../docs/experiments/2026-09-12-per-issue-forward-learning-v1.md).
Formal P3 retains its fixed release and all existing mail paths and schedules.

## Preconditions and separate authority

Owner consent authorizes preparing and testing this bounded implementation.
It is not a local authenticated Reviewer login. Preserve request 820's explicit
proxy provenance. Never acquire the owner's Reviewer credential, relabel the
implementing principal as a reviewer, grant a bypass role, or update an expired
approval. The existing authenticated SQL admission remains unchanged.

Before activation, prepare and review these exact bindings:

1. Accepted Git commit, worker and API image IDs, dependency inventories, release
   descriptors, image archives and archive hashes. Use Python 3.14.4 and the
   existing `dehps/prediction/frozen_learning/constraints.txt` to retain NumPy
   2.4.6. Both worker configurations use schema `execution-entry.v1`, their own
   `control_plane`, factory
   `dehps.prediction.forward_learning.capabilities:build_capabilities`, and
   `lease_seconds: 300`. Build with the existing `dehps.execution.release` builder.
2. A reviewed canonical calendar containing exactly 60 explicit issue/deadline/
   draw records, archived source bytes and their SHA256. Include market closures
   and the year rollover. A weekly projection is not an authoritative calendar.
   Calendar corrections cannot silently replace issue identities or overwrite
   the frozen contract. Missing coverage remains `MISSING_CANONICAL_CALENDAR`.
3. A new Ed25519 publisher key, held outside worker input mounts. Record its
   public key in the contract. Keep the private JSON file mode 0600, owned by
   the trusted host publisher; do not put it in Git, logs, descriptors or images.
4. A dedicated nonprivileged source login with SELECT only on `ssq_history`,
   `draw_issue_events`, and `draw_sync_runs`. The exporter uses a repeatable-read,
   read-only transaction and matches the complete current history fingerprint
   to an actual successful draw audit event. It never initializes production
   schemas, crawls, updates labels or runs the formal executor.
5. Separate fresh learning and observer requests binding their exact plans and
   releases. The true independent Reviewer approves each through the existing
   scoped login and finite expiry. A separately authorized Operator installs
   and begins them. Preserve both independent PostgreSQL clusters and identities.
   Do not reuse the completed R5 requests or recreate their databases.
6. A producer-reader login mapped only to the learning domain with read authority
   and the exact `read_plan`, `read_result`, `mainline_context` functions. It has
   no request, review, execute, table-DML, owner, or privileged-role rights.
   This is distinct from the learning worker's operator credential.

The 2026 closure source verified on September 12 is the
[Ministry of Finance announcement](https://zhs.mof.gov.cn/zhengcefabu/202512/t20251225_3980205.htm).
It specifies October 1–4 closure. At preparation time, a source covering the
2027 part of the cohort has not been verified. Do not deploy a guessed calendar.

## Freeze and install inputs

`dehps.prediction.forward_learning.operations freeze` requires explicit
`--source-credentials`, `--calendar`, `--calendar-sha256`, `--calendar-source`,
`--output`, and `--key-file`. It creates a **new** directory and never replaces
an earlier freeze. The calendar packet is:

```json
{
  "schema": "forward-calendar.v1",
  "targets": ["exactly 60 reviewed {issue, deadline, draw_at} objects"],
  "source_sha256": "SHA256 of archived canonical source bytes",
  "source_description": "authority, version and known calendar coverage"
}
```

The example is a schema guide, not executable calendar data. Freeze only before
the first target's 17:00 Asia/Shanghai cutoff. Initial historical availability
is conservatively the export observation time, not an invented earlier ingest
time. The source audit receipt binds all red and blue values.

Install the same immutable `contract.json`, `initial.json`, and `calendar-source` in
`/opt/dehps/inputs/forward-learning` and `/opt/dehps/inputs/forward-observer`.
Install each domain's `release.json` and `execution.json`; the latter retains
the existing schema `execution-input.v1`, actual `request_id` and exact `plan`.
Workers receive input mounts read-only. The host publisher owns the append-only
input directories and has no writable mount into a worker's source release.

Precreate `opened`, `receipts`, `observations`, and `reports` under both input
roots. The learning root/subdirectories are owned by `dehps-learning`, group
`dehps-learning`; the observer inputs are owned by `dehps-learning`, group
`dehps-observer`. Use setgid directories mode 02750; published files are 0640.
Verify read access as the actual observer UID and denied writes from both
worker containers. Do not change the observer's artifact/runtime ownership.

The trusted publisher runs from the root-owned accepted host source and frozen
venv at `/opt/dehps/releases/forward-publisher`; package its bytes and dependency
inventory in the review packet. No editable development checkout is a runtime
dependency. Install its matching stdlib launcher at `launcher/launch.py`.

`publisher.json` is a private file owned by `dehps-learning`. Its exact fields:

```json
{
  "schema": "forward-publisher.v1",
  "approved_until": "finite reviewed timestamp no later than both admissions",
  "key_file": "/etc/dehps/forward/export-key.json",
  "contract_sha256": "accepted contract digest",
  "learning_inputs": "/opt/dehps/inputs/forward-learning",
  "observer_inputs": "/opt/dehps/inputs/forward-observer",
  "source_credentials": "/etc/dehps/forward/source-reader.json",
  "producer_reader": {
    "inputs": "/opt/dehps/inputs/forward-learning",
    "runtime_root": "/var/lib/dehps/control-learning",
    "release_sha256": "accepted learning release digest",
    "reader_credentials": "/etc/dehps/forward/learning-reader.json",
    "code_root": "/opt/dehps/releases/forward-publisher/source"
  }
}
```

Credential files retain the existing closed `{dsn, database, role}` schema;
all identities are explicit. The key file has only `ed25519_private_key`, a
base64 raw 32-byte private key. Do not echo any of these private files.

## Activation and acceptance

Record the actual review/request/execution identities before installing the
candidate units. `dehps-independent.target` covers existing database/status
boot recovery. Enable the publisher and two worker timers only after exact
admissions and inputs exist. The timers poll; the existing Goal/DAG/Resolver/
Ready Queue/Coordinator decide and commit work. There is no second training
completion path. Expired approval yields `AUTHORIZATION_REQUIRED`, not renewal.

Update only the two independent status readers to the newly accepted API image
and exact plan/release/execution bindings. Do not alter formal API sources or
mail routes. Include the actual `requestId` in each independent reader source
binding so an expired-admission projection cannot borrow another request's
identity. Keep historical completed records, but display current wait reasons
and isolated report failures separately. Projection timestamps are operational
observations, never proof of completion or delivery.

Run the new learning entry immediately, record its actual run/attempt/commit
and checkpoint, then run `--action replay-prefix` using the new fixed launcher.
Record the actual commit timestamp before the cutoff. Before a draw, no score
or report success may be claimed. After the real audited event, verify:

`sealed probabilities -> score -> next checkpoint -> registered report ->`
`signed publisher bundle -> independent observer commit -> fresh-process replay`.

Machine results are immutable registered artifacts; human reports are published
under the observer inputs' `reports/<issue>.md`. The final issue's report also
depends on the final analysis, so a 60-issue conclusion has a real consumer.
Missing payouts do not block scoring. Missing predictions stay gaps; missing
labels stay waiting. Duplicate signed events retain the first availability.
Corrections that conflict with a published label fail instead of rewriting it.

Preserve exact before/after formal evidence for issue 2026106 (or the current
issue if activation is later): source binding, pre-draw seal/report/replay,
mail ledger and timer next triggers. The recorded pre-mail for September 13 at
17:00 remains `PENDING_DELIVERY` until the actual ledger proves delivery.
Do not run a mail command as an independent-service acceptance test.

## Failure and rollback

Stop only the new three timers and their in-flight services at safe boundaries.
Retain input envelopes, receipts, artifacts, attempts, registrations and failed
events. Restore the previously recorded independent reader configurations when
appropriate; an old projection must remain visibly stale. Database boot recovery
may remain active. Do not reactivate expired R5 workloads, the old observer, V11,
or restart Formal P3 as rollback.

A failed report can retry without refitting an already committed checkpoint.
A transaction that crosses the seal cutoff rolls back artifact registration;
recovery records `MISSED_SEAL`. Ambiguous commit acknowledgment is resolved by
verified durable readback. A killed uncommitted attempt waits for its fenced
lease before retry. Database container CID recovery remains the existing exact-
identity Operator procedure; never remove a CID or database directory blindly.

Installation, tests, a merge or a service exit do not complete this experiment.
Until the first real end-to-end draw cycle, the capability remains
`NO — INTEGRATION_PENDING`. Predictive improvement requires the separately
frozen full-window analysis, and never grants Formal P3 promotion.
