# R1 authenticated authority

Status: component code and local validation complete; R2/R5 integration pending;
no deployment. Required CI will run on the reviewable PR's exact head.
Role: Engineering Agent, within the continuing owner-authorized R0–R5 scope.

This round binds new control-domain request, review and execution records to
PostgreSQL-authenticated login principals. It does not reinterpret historical
Reviewer labels, grant production access, restart P3, change science or send mail.

Before implementation: the R0 report baseline remains dated 2026-09-09. Expected
issue 2026105 has a 2026-09-10 17:00 pre-draw delivery trigger and 21:15 official
draw time in the canonical calendar; future delivery is PENDING_DELIVERY. The
2026104 ledger gap and previous notification window failure remain unresolved.
No assertion of current delivery or sealing is made. This round changes only the
isolated development checkout and disposable test resources. Production source,
the shared venv, timers, database and report paths are outside these mutations.
Adding Python source affects the development source closure; deploying it over
the old frozen release is forbidden. R3/R5 must preserve legacy release identity.

Contract: Goal = R1/A2; Ready = approved bounded engineering scope and isolated
test cluster; runner = required PostgreSQL CI job; upstream = explicit database
credentials and administrator-provisioned login-to-principal mapping; downstream
= immutable request/approval/execution identity records; status = this checkpoint;
Evidence rule = real SQL authentication/privilege tests, no mock authority;
decision consumer = R2 execution admission; next consumer = R3/R5 release entry.
R2/R5 integration remains pending until those consumers actually use the boundary.

Trust boundary: a separately administered database schema owns the tables and
narrow SECURITY DEFINER functions. Login names and role OIDs are provisioned by
the trusted administrator, mapped to stable principals and one control domain.
Aliases must map to the same principal. Shared reviewer/executor credentials are
not acceptable. Clients never supply an authoritative actor ID. Database owners,
superusers and the provisioning administrator are trusted infrastructure, not
runtime identities. Provisioning actual independently controlled identities and
protecting the deployment channel remain R5 requirements; fixture users do not
constitute actual human review.

PostgreSQL documents that session_user identifies the connection initiator,
whereas current_user changes in SECURITY DEFINER functions. Functions pin their
search path and revoke default PUBLIC execution privileges following the
[PostgreSQL function guidance](https://www.postgresql.org/docs/17/sql-createfunction.html)
and [session identity reference](https://www.postgresql.org/docs/17/functions-info.html).

The schema owner must be a fresh dedicated NOLOGIN role with no runtime members.
Install `dehps/execution/migrations/001_authority.sql` once in an administrator
transaction while using that owner. Revoke PUBLIC database access and public
schema CREATE; grant each login CONNECT, authority schema USAGE and only the six
entry function signatures listed in the integration fixture. Neither helper
functions nor tables/sequences receive runtime privileges. There is no runtime
bootstrap or fallback to production credentials. Provisioning and later mapping
changes are privileged operations, to be audited in the R5 deployment package.
The immutable records retain both the stable principal and original login/OID;
role name reuse alone cannot inherit an old approval.

Request content is hashed in PostgreSQL from its stored JSONB representation.
This is a new authorization-content digest, not a rewritten scientific digest.
Approval additionally binds the supplied release SHA-256 and a finite expiry.
Execution and reauthorization check both bindings, approval/reviewer validity,
revocation and reverse reviewer/executor separation. Record IDs cannot transfer
authority between logins. A revocation is permanent for that request; renewed
work needs a new request. Repeated valid begins by the same login return the same
execution reference. Request locks serialize begin/revoke; admission requires
READ COMMITTED to reject stale authorization snapshots.

The release digest argument is a comparison input, not attestation that those
bytes are running. R3's protected launcher must measure and bind the actual
release. R2 must call reauthorization in the same database transaction as the
protected state transition; calling the Python convenience method and later
performing an unrelated write would leave a time-of-check gap. Long running
compute must be rechecked before later authoritative side effects. Neither
release attestation nor the full commit store is claimed in this R1 component.

Validation (isolated checkout, disposable PostgreSQL 17):

| Check | Evidence |
| --- | --- |
| `python -m pytest -q -x --tb=short tests/test_execution_context.py integration_tests/test_execution_database_isolation.py integration_tests/test_execution_authority.py` | 45 passed in 2.73 s, including 19 authority cases |
| Additional `test_set_role_does_not_change_authenticated_principal` | 1 passed in 0.15 s; actual SET ROLE succeeds yet self-approval still fails |
| Raw SQL attacks | Table mutation, private helper calls, schema creation, unauthorized SET ROLE and SET SESSION AUTHORIZATION denied |
| Persisted authorization | Changed/null content and release, expired approval, disabled reviewer/executor, reviewer permission loss, domain mismatch and revocation denied on reconnect |
| Concurrency | Four real connections yield one durable execution; an execution blocked behind uncommitted revocation fails after that revocation commits |
| Wheel packaging | Built wheel with isolated build dependencies, installed into `/tmp/dehps-r1-authority-installed`; imported authority outside checkout, migration bytes match source, integration tests excluded, production settings not imported |
| Production dependency/diff audit | Original checkout clean at `ac0ef7832c6f13c7500b3f7d67731420b575c0f4`; no existing runner imports new authority module; no old Python implementation or source contract changed |

The first SQL install failed on an unparenthesized CASE expression in PL/pgSQL;
fixed and the full affected suite rerun successfully. The first wheel attempt
with `--no-build-isolation` found no setuptools backend; using pip's temporary
isolated build environment succeeded without installing into the shared venv.
Generated build files were removed; no runtime artifacts are committed.

Report impact: **NO_RUNTIME_IMPACT for this undeployed round**, supported by the
dependency/diff audit above. This does not certify the existing production report
chain or authorize deployment over historical frozen code. No current-issue
delivery, fresh P3 execution or replay acceptance is claimed. No algorithm,
scientific conclusion, historical artifact or mail ledger was modified.

Integration matrix: component request -> authenticated approval -> persisted
execution -> reconnect/reauthorize has real database evidence. Goal/Resolver/
Ready Queue/capability/artifact/next-consumer execution through the new control
domain is not yet implemented. **NO — INTEGRATION_PENDING**. R1/A2 has component
evidence; real entry/deployment identity acceptance remains R2–R5 work.
