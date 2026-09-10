# R2 canonical execution and replay integration

Role: Engineering Agent under the recorded continuing R0–R5 owner consent.
Status: local implementation/integration verification passed; PR/CI acceptance
pending. No production deployment or new scientific experiment.

This round connects the existing Goal/Task model, dependency resolver and Ready
Queue to authenticated persistence, canonical execution/artifact registration,
status reconstruction and downstream consumption. It does not add a new model,
change scientific rules, update historical digests or restart Formal P3.

Contract: Goal = R2/A3/A4/A5 canonical execution and replay; Ready = frozen approved
plan, explicit isolated credentials/resources, registered capability/verifier
versions; runner = the new domain coordinator; upstream = canonical manifest and
approved task bindings; downstream = immutable result plus canonical execution/
artifact records; status = reconstructed canonical manifest and domain projection;
evidence = real PostgreSQL transactions, process interruptions and downstream
replay; decision consumer = shared versioned verifier; next consumer = dependent
Ready Queue task and R4 observation/learning entry points.

Before implementation report baseline: production checkout remains clean ac0ef78,
2026105 pre-draw trigger is 2026-09-10 17:00 and official draw 21:15; dated 2026104
ledger gap remains unresolved. No fresh sealing/delivery/replay acceptance is
claimed. This isolated checkout, test databases and fixture files have no live
production consumer. Source closure additions must not be deployed over the
frozen legacy release. R3/R5 retain that compatibility obligation.

Design: a versioned execution-plan.v2 packet binds the exact canonical manifest,
Goal/Task definitions and task specifications to an authenticated approval. Intake
inserts only those approved immutable parent records. Python reconstructs and
validates all canonical digests before intake and again before execution/replay;
SQL binds all writes to the frozen approved packet and rejects immutable conflicts.
No runtime role receives direct canonical-table DML.

Artifact registration and started/completed event records join the result commit
in one transaction through a trusted registration sink. A committed result left
without a canonical registration by an older component path is registered from
its persistent attempt/commit facts without recomputing it. Read-only replay
never repairs missing records. Completion facts and the next Ready Queue are
reconstructed from verified commit/registration pairs, never caller status labels
or mutable status files. Original Task/Goal/Manifest/event digest algorithms are
retained. New attempt execution IDs use SHA-256 of UUID bytes; historical IDs do
not change.

## Implemented behavior

The coordinator loads only registered capability and verifier versions supplied
by its entry point; it imports no legacy supervisor or production settings.
An approved plan cannot assert completed/running tasks in its initial manifest.
The existing resolver and Ready Queue determine eligibility. Committed parent
results are verified before being supplied to a dependent capability. Leases are
renewed by a bounded statement-timeout heartbeat while calculation runs.

The additive migration imports the frozen canonical definition packet, keeps
immutable plan/task dependency bindings, and exposes only four additional scoped
entry functions. Existing execution-plan.v1 callers remain compatible. Already
committed task bindings can be reused by an extended approved plan without
retraining or overwriting their original release association. Changing a
previously bound dependency or immutable definition is rejected.

Started/completed events and artifact registration participate in the result
transaction. Their control domain, Task, execution, artifact path/digest/schema,
parents, timestamps, release and scientific-contract reference must match the
persisted records. SQL also checks their hashes using the existing Mainline*
envelopes. The private canonicalizer accepts runtime record integers/strings/
arrays/objects only, explicitly rejects scientific floating-point payloads, and
matches legacy ensure_ascii=True including surrogate pairs and DEL. Goal/Task/
scientific hashes continue to use the original Python implementations.

No git commit is fabricated: the legacy registration git_commit field is empty
for these new records; the approved release SHA-256 is recorded explicitly in
the event payload. R3 must bind that release to actual code/dependencies and
supply its real release provenance. The fixture release hash is not a deployed
release or proof of source attestation.

The canonical state for a new plan is reconstructed from its immutable initial
manifest and verified commit/registration pairs. It is not taken from the legacy
control-plane head's initial status declarations or a mutable status file. Each
successful Task has exactly one original-format mainline completion fact; the
same resolver consumes this reconstructed manifest to release its dependent
Task. Read-only replay reconstructs the same manifest without writing status or
repairing records. The new API/status consumer must explicitly select domain and
plan in R3; no claim is made that the legacy status API already understands this
projection. Old production heads and historical manifests are unchanged.

A component-only commit with missing mainline records is INTEGRATION_PENDING.
The coordinator can verify its persisted bytes and register its existing attempt
without recomputation. Replay alone fails until that recovery occurs. Hash or
binding conflicts are not repaired by rewriting history. A result whose parent
was not committed and registered at attempt start cannot be canonically
registered. Capability failures retain the underlying attempt record.

## Verification

Full affected command, with a separately labeled disposable PostgreSQL 17 and
explicit test DSN/container identity:

```text
python -m pytest -q -s -x --tb=short tests/test_execution_context.py tests/test_execution_artifacts.py integration_tests/test_execution_database_isolation.py integration_tests/test_execution_authority.py integration_tests/test_execution_store.py integration_tests/test_execution_mainline.py
76 passed in 28.19s
```

The 12 new mainline cases cover two-task canonical execution, dependency artifact
provenance, independent-process replay with identical reconstructed manifest,
SIGKILL inside the registration transaction, SIGKILL in the downstream capability,
component-commit registration recovery, corrupted definition/unknown capability
rejection, adding a third registered capability without core edits, automatic
lease renewal, revocation/read-only replay, parent readiness and atomic rejection,
forged SQL record digest rejection, shared verifier failure and exact legacy
runtime digest compatibility. Existing v1 store tests now apply migration 003 as
well, verifying compatibility after replacing the authorization helper.

One captured two-task execution from the full successful run:

- Canonical coordinator process run ID: `1bcc27dc-ac50-4a82-886a-abb4f59d90e6`.
- New replay process run ID: `0c451fbc-dcdd-426c-8b8b-41123ca264df`.
- Reconstructed completed manifest digest: `b4829c7ee1281aeb379eeb9c4fb0f0eee13603faeae36dec19511b00fb63e917`.
- Two commits, two successful attempts, four canonical events and two artifact
  registrations; the consumer registration references the source artifact.
- Source and consumer compute counters each equal one after fresh-process replay;
  replay leaves status-file mtime unchanged. Interrupted attempts are separately
  retained and counted by their dedicated cases.

These are disposable engineering-fixture executions, not newly claimed production
or scientific evidence. Fixture DB/roles/files are cleaned after verification.
An actual worker wheel was built and inspected: all three SQL migrations and the
plan/coordinator/ledger modules byte-match source, and integration_tests is not
packaged. The generated build directory was removed.
The required CI job now includes this mainline suite. The original production
checkout remains clean at ac0ef78, and no production service, dependency, source
contract, artifact or delivery ledger was changed.

The first local run caught SQL variable/column ambiguity in intake; the next
caught JSON operator precedence in event validation. Both were corrected and
retested against real PostgreSQL. Digest review identified the existing
ensure_ascii=True rule; the SQL runtime canonicalizer explicitly preserves it
and the Unicode/integer comparison test passed. No verifier, constraint or test
was disabled to obtain these results.

Integration verdict: the deterministic engineering path now exercises
Goal -> Resolver -> Ready Queue -> Coordinator -> Capability -> Immutable Result
-> Canonical Records -> Status -> Next Task -> Replay. This is local integration
proof of the new control core. Existing observation/learning capabilities still
require their R4 migrations and frozen-science parity checks; actual release
isolation and deployment remain R3/R5. Overall project verdict remains
**NO — INTEGRATION_PENDING**.

Report impact: **NO_RUNTIME_IMPACT for this undeployed round**, supported by the
explicit isolated checkout/resources and import/diff audit. Existing 2026104 gap
and current-issue sealing/delivery acceptance remain unclaimed. This engineering
result neither certifies production reports nor changes the learning report's
"insufficient evidence" conclusion.
