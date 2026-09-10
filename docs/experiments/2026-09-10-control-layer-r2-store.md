# R2 execution persistence and immutable publication

Role: Engineering Agent under the continuing R0–R5 owner authorization.
Stage: implementation in progress, no deployment or scientific experiment.

Goal: R2/A3/A5 crash-safe claim, attempt and commit semantics, consuming R1
reauthorization in the same transaction as state changes. Ready: isolated
PostgreSQL, real canonical Goal/Task/Manifest parent records and approved fixture
execution plan. Runner: required real PostgreSQL CI. Upstream: existing canonical
Task definitions, release identity, independent authorization and verifier ID.
Downstream: one immutable committed artifact reference and retained failed
attempts. Status: reconstruct from persistent facts, not projection JSON.
Evidence: actual process death/transaction/constraint/lease tests. Decision
consumer: versioned readback verifier; next consumer: R2 resume coordinator and
R4 canonical observation/learning paths. Full domain integration is pending.

Existing schema audit: infra/postgres/init/002_research_os.sql has immutable
Goal/Task/Manifest parents and event/artifact tables. Event uniqueness is only
(execution_id, sequence); artifact uniqueness is only (execution_id, digest,
type). repository.py record_mainline_execution_event and register_mainline_artifact
use separate transactions and include a historical incident-specific branch.
Reuse canonical definition parents and digest semantics; add only missing claim,
attempt and unique business commit records. Do not run the legacy schema migration
against production in this round. Fixtures use the real migration with complete
parents; no recovery mock removes foreign keys.

Before implementation report impact: production checkout remains ac0ef78 and is
not touched. Expected issue 2026105, 2026-09-10 17:00 pre-draw trigger / 21:15 draw,
and unresolved 2026104 ledger gap remain as the dated R0 baseline. No fresh seal,
replay or delivery acceptance is claimed. New execution modules are unreachable
from existing production runners; shared venv, services and artifacts stay on
old code. New files do affect the development Python source closure; no historical
source digest may be updated to accommodate them. R3/R5 must preserve the fixed
legacy release before any runtime switch.

## Implemented protocol

`execution_store.tasks` reuses the existing canonical task/manifest/control-plane
FKs. A (domain, business_key) is bound once to the approved task, manifest,
scientific contract, release, verifier ID and artifact schema. Closed
`execution-plan.v1` requests enumerate exact specs; another spec cannot be
registered or claimed with the same approval. Canonical parents must already be
registered; authorized manifest intake remains part of the next integration PR.

The same NOLOGIN owner as R1 owns the new schema. Runtime gets six narrow function
signatures (listed in the fixture), never direct table/sequence/helper grants.
Claim, renew, fail and commit reauthorize inside their database transaction and
lock the request then the task. Each attempt gets a UUID and increasing fencing
counter. A renewed live lease prevents a second claim; an expired attempt becomes
failed with lease_expired and can never commit. Explicit failure reasons survive
retry. Exactly one commit per task is enforced by the primary key; repeating the
same commit is idempotent, a different reference conflicts. Immutable triggers
also protect task definitions and commit records from update/delete.

`ArtifactStore` writes and fsyncs a temporary file, publishes by atomic hard link
with no replacement, fsyncs the directory, then verifies the resulting bytes.
New directory entries are also fsynced. Existing digest paths are verified, never
repaired or overwritten. Symlinks, wrong sizes and digest mismatches fail closed.
The parent directory is flushed even if mkdir reports an existing entry: another
writer may have created it and exited before its own flush. After this durability
review fix, all 29 context/file/kernel tests passed again.
A process killed between file preparation and DB commit leaves an unreferenced
file, not a successful task. Such files are retained; automated inventory/cleanup
is not implemented or claimed here. Committed missing/corrupt evidence blocks
readback and resume rather than silently retraining to hide the gap.

`ExecutionStore` requires an injected verifier registry and explicit resources.
The same task binding and verifier run on preparation, commit and result reads.
No experiment-specific imports, historical IDs or ambient production settings
enter this core. The verifier ID is pinned by the approved task and release;
R3 must bind the actual running bytes. The lower-level SQL transaction enforces
identity, fencing, uniqueness and references; the trusted worker's versioned
verifier enforces artifact semantics. Direct SQL is not a scientific verifier.

Status projection is outside the authoritative commit: real projection path
failure cannot reverse durable success. No source/artifact/metric digest from
legacy execution is rewritten. This component does not yet populate legacy
mainline completion events or advance the canonical resolver; the R2 coordinator
must make those consumers use committed evidence rather than create a competing
completion path. The subprocess fixture is a recovery acceptance driver, not a
new production/manual completion route.

## Validation and remaining acceptance

| Check | Result |
| --- | --- |
| `python -m pytest -q -x --tb=short tests/test_execution_context.py tests/test_execution_artifacts.py integration_tests/test_execution_database_isolation.py integration_tests/test_execution_authority.py integration_tests/test_execution_store.py` | 64 passed in 14.73 s: 23 context, 5 file, 3 DB isolation, 20 authority, 13 execution persistence |
| `python -m pytest -q integration_tests/test_execution_os_isolation.py` | 1 passed in 0.80 s after directory fsync change; real dual-domain kernel denial |
| Commit confirmation lost | Real SQL transaction commits, PostgreSQL terminates that session before execute returns; two fresh subprocess resumes verify once-committed bytes, compute marker remains one |
| Death before commit | Actual SIGKILL after file fsync; one expired failed attempt, one successful retry, one commit/blob, no inode/mtime replacement |
| PostgreSQL restart | Verify test label, fixed port, admin marker and cluster system_identifier, force `docker restart --time 0`, verify changed postmaster start time and unchanged cluster identity, then two fresh-process readbacks; still one computation/commit |
| Durable settings | Actual fixture connections verify fsync=on and synchronous_commit=on |
| Packaging | Built wheel; both SQL migration resources byte-match source; integration_tests excluded |
| Diff/import/production check | diff --check passed; original checkout clean ac0ef78; new modules not imported by existing production entry points; no production venv/resource mutation |

The local restart fixture initially used Docker's dynamic host port. Restart
changed 32771 to 32772, so the test and cleanup correctly failed to reconnect.
The disposable container was removed and recreated with explicit 127.0.0.1:32771;
a new precondition rejects dynamic port configuration before restart. The full
suite then passed. CI already binds fixed 5432:5432 and now labels its test
container. The container ID is obtained through the documented
[GitHub job service context](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#job-context).
This remains a required real-database job; no missing-configuration skip or test
exclusion was introduced.

Report-impact verdict: **NO_RUNTIME_IMPACT for this undeployed round**, based on
the concrete source/import/diff/resource audit above. The dated R0 issue gaps
remain; there is no current-issue delivery acceptance, deployment, new scientific
result or refreshed Formal P3 process to report.

Integration: local authenticated plan -> canonical parent FK -> claim -> file
verification -> transaction commit -> fresh-process verification is proven.
Goal/DAG/Resolver/Ready Queue -> new coordinator -> artifact registration/status
-> next task is still pending. **NO — INTEGRATION_PENDING**. Next R2 PR must add
canonical event/consumer integration, versioned replay/resume and downstream
interruption evidence. R3–R5 and full A1/A2/A6/A8–A12 acceptance remain outstanding.
