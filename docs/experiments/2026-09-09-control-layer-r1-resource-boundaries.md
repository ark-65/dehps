# R1 resource boundary implementation

Scope: first R1 PR, explicit filesystem/database admission and independently
enforced resource permissions. Owner authorization is recorded in the R0
checkpoint. This adds no algorithm, training run, production operation, or
research decision. It does not declare R1 or the refactor complete.

## Changes and proof

`dehps.execution.context.RunContext` owns fixed state/status/log/artifact/lock/
outbox areas within an explicit domain. Mutable projections may write only the
first three. All path traversal is anchored to directory descriptors with
O_NOFOLLOW; parent escapes, symlink ancestors, invalid domains and unsafe roots
fail closed. Projection envelopes bind their consumer to the control domain.
Atomic replacement flushes the file and its directory. This API constrains
cooperating code; the process mount/UID boundary is what constrains arbitrary
code choosing the wrong path.

`DatabaseBinding` requires explicit connection coordinates and credentials,
rejects connection services and ambient libpq command/host overrides, verifies
database/session-role identity, and denies privileged roles, database owners,
or memberships allowing privileged roles. It imports neither production config
nor the legacy supervisor. Admission is not a substitute for PostgreSQL grants.

Validation in the isolated development worktree:

| Evidence | Result |
| --- | --- |
| `python -m pytest -q tests/test_execution_context.py` | 23 passed; lifecycle branches, traversal, symlinks, projection identity, finite payload, credential defaults and import boundary |
| `python -m pytest -q integration_tests/test_execution_database_isolation.py` | 3 passed on a separately started disposable PostgreSQL 17 cluster; real CREATE/GRANT/REVOKE and cleanup, direct libpq cross-domain denial, DDL denial, admin-admission denial |
| `python -m pytest -q integration_tests/test_execution_os_isolation.py` | 1 passed; two non-root/no-network/read-only containers, five lifecycle states each, 30 real kernel write denials, formal sentinel bytes/mtime unchanged |
| `git diff --check` | passed |

The local DB cluster is `codex-dehps-execution-r1-01a0857a`, initialized with test
admin database `dehps_execution_test_admin`, never the existing dehps DB or its
credentials. Tests create only randomly named fixture databases and roles and
drop those exact objects in teardown. They cannot silently skip a missing test
DSN. OS tests bind only fixture directories and this boundary module, not any
production directory, socket or credential. Local image identity:
`sha256:d764629ce0ddd8c71fd371e9901efb324a95789d2315a47db7e4d27e78f1b0e9`.

The new mandatory CI job provisions its own PostgreSQL service, requires the
real DB tests and kernel isolation tests, and feeds the existing `pytest`
aggregate gate. No existing tests or exclusions were removed. These tests do
not prove crash recovery or scientific parity; those belong to R2/R4.

Two failures were fixed inside the continuing authorization: PurePosixPath('.')
has no components and needed explicit rejection; the OS fixture initially used
a group-writable formal directory, causing admission to reject it before the
kernel write check. The fixture now uses mode 0700 so the intended read-only
mount denial is actually exercised.

## Remaining acceptance and report impact

This is `CODE_COMPLETE / INTEGRATION_PENDING`, not an isolated training capability
completion. New task dispatch/storage/verifier and migrated observation/learning
entry points remain R2/R4 work. Existing legacy entry points have not been
rewritten or activated. A1 has component and real-resource evidence; acceptance
of the final migrated entry points is still pending. A2 identity is the next R1
PR. No supervisor run ID is claimed for this foundation-only change.

Integration matrix: Goal/DAG/Resolver/Ready Queue/Runner are planned in the R0
contract, but the new path has no completed immutable execution, next consumer,
or deterministic replay yet. **NO — INTEGRATION_PENDING**.

Report impact: `NO_RUNTIME_IMPACT` for the current undeployed change, established
by a clean original production checkout at ac0ef78, no imports of these new
modules from any existing runner, and no production service/configuration/DB/
artifact mutation. The new Python files WOULD affect learning_v1's whole-tree
source identity if a legacy experiment were pointed at a newly updated checkout.
Therefore this verdict is not release approval: R3 must pin the historical
release and R4 must verify archived artifacts before deployment. Never update
old source digests to accommodate these added modules.

The exact issue/deadline/ledger/timer baseline and original failures remain in
the R0 checkpoint. 2026104's ledger gap remains open; 2026105's scheduled
2026-09-10 17:00 delivery is future acceptance, not a completed delivery. This
isolated test work does not generate reports, send mail, restart Formal P3 or
erase those gaps.
