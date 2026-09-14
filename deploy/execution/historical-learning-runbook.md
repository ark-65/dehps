# Historical report learning release

This is the separate `historical-report-learning.v1` contract. Keep the existing
frozen 60-issue forward contract, old historical verification, P3, V11 and mail
routes unchanged. Engineering Request 823 does not supply runtime admission.

Build learning and observer releases through the existing fixed-release builder,
with factory `dehps.prediction.historical_learning.capabilities:build_capabilities`,
`execution-entry.v1`, explicit domain, lease 300, and the retained
`dehps/prediction/frozen_learning/constraints.txt`. Pin Python 3.14.4, NumPy 2.4.6,
the accepted commit, base/worker/API image IDs, dependency inventory and archive
SHA256. One process per domain; all BLAS thread counts equal one. A third
computational exporter shares the observer flock for its full lifetime, so at
most two computations run. Install the supplied historical tmpfiles definition
before services start; the root-owned lock directory prevents inode replacement.

Freeze the verified existing historical export with the new `operations freeze`
entry. It requires a nonprivileged source reader, retained input SHA256 and root,
the original report root, a new output directory and a private Ed25519 key.
The source reader has SELECT only on `ssq_history`, `draw_issue_events`,
`draw_sync_runs` and `research_os_mainline_artifacts`. The source transaction is
repeatable-read/read-only. No report text supplies a label. Verify all 3499
baseline labels and 2599 retained evaluation references plus audited later rows.

Install immutable inputs into `/opt/dehps/inputs/historical-learning` and
`historical-observer`, not the existing R5 or forward input roots. Bind each
domain's exact `execution.json` request and plan and `release.json`. The private
signing key and source/producer-reader credentials belong only to the trusted
host publisher at `/opt/dehps/releases/historical-publisher`; worker input mounts
are read-only. Keep the actual scoped worker Operator credentials separate.
Provision both publication trees owned by `dehps-learning`, with their consuming
domain group, directories 2750 and files 0640. The publisher uses umask 0027 so
new per-issue directories inherit the setgid group and remain readable by the
observer. Private credentials and signing key remain 0600, outside these trees.
The source reader is not a mainline owner login. The producer reader is
read-only and has no request, approval, execution or table-DML privileges.

Root must install read-only bind mounts of the host's
`/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice` at each
input root's `formal-cgroups`, using persistent systemd mount units. Use the
actual `systemd-escape --path --suffix=mount` unit names, `Options=bind,ro`, and
order them after `user@1000.service`. These are observation-only mounts; do not
edit formal service units, locks or deadlines. Each compute dispatch checks
actual formal service process membership. A missing guard leaves the task waiting.

Apply `004_plan_index.sql` only to the two independent control databases, under
their existing non-login schema owner, after verifying their cluster identities
and the original three migrations. It adds a private immutable request/specification
index needed by the 5272-task learning plan. It preserves actual session identity,
request locks and reauthorization on every admission/claim/commit. It grants no
runtime DML or new approval API. Never apply it to the formal database. An expired
or revoked request must still fail, including admission of a completed plan.

The publisher's private `historical-publisher.v1` configuration has exactly
`activated_at`, `approved_until`, `key_file`, `contract_sha256`, `learning_inputs`,
`observer_inputs`, `source_credentials`, `source_root` and `producer_reader`
(plus `schema`). The reader object has `inputs`, `runtime_root`, `release_sha256`,
`reader_credentials`, `code_root`, matching the fixed accepted release.
`approved_until` must be within 30 days of activation and within both actual
scoped approvals. Never extend an expired approval automatically.

Use authenticated Reviewer and Operator routes for both exact plans/releases.
Record their real request/execution IDs. Do not use a principal string as a
substitute for authenticated approval. Provision inputs and services only in
the resulting bounded Operator operation. Start the historical learning entry
immediately and witness two committed consecutive updates. Publish their
registered reports, run the separate observer, and read its actual registered
artifacts and human reports. Then finish the batch and replay in a fresh process.
Historical acceptance is the complete batch prefix; unused incremental slots
remain waiting. Use `--action replay-prefix` because intake remains open.

After those first reports pass, enable the new publisher and two worker timers
and confirm boot recovery. The timers run every 15 minutes. No new labels means
no new model update. Report rendering retries have their own tasks. Source
conflicts append error evidence and halt affected successor updates. At 24 hours
from the first committed batch start, new historical computation stops; already
committed progress remains. Actual SQL admission is checked again at commit,
including expiry/revocation during computation.

Bind the independent status API to the new plan/release/execution/request IDs.
`historicalProgress` is an operational projection, never proof of registration.
Read observer reports at `reports/<issue>.md` and `reports/summary.md`, keeping
original predictions and historical reconstruction distinct. 2026104 remains
an original-prediction gap. Unopened issues cannot be scored.
The separately labeled original results are at `reports/original/<issue>/index.md`
with the exact original JSON bytes, candidates and rankings. These audit views
are derived from input-bound source references; they are not new completion facts.

Rollback stops/disables only the new publisher/worker timers and workers,
preserves every input, checkpoint, error, report and database record, and restores
the prior independent status binding if necessary. Do not delete the new evidence
or modify formal P3/V11 artifacts, notification ledgers or existing timers. Before
and after activation compare the current formal issue's seal, provenance, replay,
registered readable report, mail ledger and next timer triggers. Do not send
acceptance mail. Code merge, deployment, batch acceptance and predictive evidence
must be reported as separate states.
