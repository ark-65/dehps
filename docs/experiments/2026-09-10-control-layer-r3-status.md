# R3 explicit status consumers

Role: Engineering, continuing owner-authorized R0–R5 scope. Implementation and
acceptance in progress. No production deployment.

Goal: expose only the explicitly configured control domain/plan/execution/release
status, with missing, stale or mismatched data reported as unknown. Ready: exact
deployment-selected bindings and an isolated readable projection root. Runner:
canonical coordinator projection and a read-only API consumer. Upstream: R1
execution reference and R2 verified snapshot. Downstream: explicitly attributed
status response. Evidence rule: real PostgreSQL execution to real file to actual
HTTP response, including failed startup/recovery and wrong/old identities. Decision
consumer: API status reader. Next consumer: R4 observation/learning entry monitoring
and R5 deployment checks.

Before implementation: production checkout remains retained at ac0ef78. This
development worktree and temporary API/database resources have no production
consumer. No production sources, dependency installation, timer, DB or delivery
ledger changes are targeted. The dated 2026104 gap and 2026105 report acceptance
remain unclaimed. New status is an operational projection, not fresh scientific
evidence, deterministic replay proof or production report completion.

The new endpoint is explicitly configured and never searches legacy paths for a
fallback success. Existing legacy routes remain a retained compatibility surface;
they must not be used to certify the new control domain. Missing domain binding
means unavailable, never implicit Formal P3 selection. Deploying/redirecting
consumers remains part of the reviewed R5 package.

## Implemented behavior

The coordinator emits `execution-status.v2` with the exact authenticated execution
reference and release binding, in addition to the domain envelope, initial plan,
verified manifest, process run ID, phase, timestamp and declared task states.
Starting a run replaces an earlier projection before admission; admission or
recovery-verifier failure records FAILED without rewriting durable task facts.
During calculation, successful lease renewals refresh RUNNING status. Readonly
canonical replay still leaves projections and persisted records untouched.

`GET /execution-status` and `GET /execution-status/:controlPlane` use only
deployment-configured sources. An unconfigured domain returns 404. Configurations
are closed and copied at startup; the caller cannot pass a filesystem path or
select a production fallback. The reader validates the domain, plan, execution and
release plus schema, UUID, task states and bounded UTC timestamp. Completed phase
requires completed task states. Symlinks, non-regular or oversized files, malformed
JSON and unsupported legacy schemas fail closed. Missing, unreadable, stale,
future-dated or mismatched input returns UNKNOWN with a reason and no cached success.
No raw filesystem path or unexpected payload field is reflected in the response.

Status is explicitly labeled OPERATIONAL_PROJECTION_ONLY and
durableCompletionVerified=false. The API does not claim a live process, redo the
scientific verifier, grant approval or establish report delivery. Freshness is a
bounded observation; failed projection writes remain visible through coordinator
projection_errors/launch handling and eventual staleness, not file repair. R4/R5
must bind the actual release and deployment sources. This change does not certify
the R3 packaging-only smoke image as an admitted scientific execution.

## Validation

- All affected Worker/context/artifact/authority/store/mainline/HTTP checks:
  **79 passed in 37.42 s**, using a separately labeled disposable PostgreSQL 17.
  The existing force-restart/FK/fencing checks remained enabled.
- API `npm test`: **121 passed**, no skipped or failed tests.
- API `npm run build`: passed.
- Fresh canonical process `f9a1d714-0803-493c-866c-0c13d6262619` and independent
  replay `6867c0f9-58c6-42e6-854f-3073172336c9` reconstructed manifest
  `e0ab562823de62a7302efcb53d6c9878a01b9b74f2db3a6a0e557d04102be62a`.
- Actual PostgreSQL -> atomic file -> separate Nest HTTP API used canonical run
  `922d9966-3eef-40e9-913a-a1fbe9712acd`. After deactivating the fixture's real
  execution principal, run `c1ac31a8-8f45-4ec5-9fe1-ecfb2da2a84b` failed admission
  and the HTTP endpoint reported FAILED; commit/attempt/event/artifact counts were
  unchanged. A separate shared-verifier rejection likewise replaced old success
  without mutating persisted results.
- A real three-second computation renewed its one-second lease and emitted at
  least four distinct RUNNING timestamps. The actual HTTP reader accepted it with
  a one-second freshness bound, then observed completion.
- Real API reads and independent replay preserved status bytes/mtime and canonical
  counts. Wrong plan/release/execution references were rejected. HTTP test processes
  received no DB credentials; worker subprocesses now receive only the explicit
  operator configuration rather than inheriting the administrator test DSN.

The first loopback HTTP test could not run inside the default command sandbox;
the authorized isolated test ran on a temporary 127.0.0.1 port. An empty-directory
test cleanup used rm rather than rmdir and was corrected. No persistence assertion
or verifier was mocked away. The final command log is retained at
`/tmp/dehps-r3-status-worker-tests.log`; API log at
`/tmp/dehps-r3-status-api-tests.log`. Temporary database and HTTP services are closed.

Required CI now installs the locked API dependencies, runs API tests/build and
executes the real cross-process HTTP integration alongside PostgreSQL tests. API
changes also trigger this workflow. All existing worker shards remain required.

Integration verdict: this engineering fixture exercises the canonical Goal/DAG,
resolver, Ready Queue, coordinator, immutable records, projection, actual HTTP
consumer and readonly replay. Existing observation/learning path migration and
scientific parity still belong to R4; actual service/resource/release acceptance
still belongs to R5. Overall **NO — INTEGRATION_PENDING**.

Report impact: **NO_RUNTIME_IMPACT for this undeployed round**. The diff changes
only the new coordinator's projections, an additive API route, documentation and
isolated tests/CI. No old supervisor, scientific kernel, source contract, schema,
report or mail consumer is changed. API dependencies were installed only under
the development worktree. The original production checkout remains clean ac0ef78;
no service restart, production write, mail send or new report acceptance occurred.
