# P3 2026103 settlement replay incident recovery

Engineering Request #812; user approval recorded 2026-09-09; Engineering
execution #653. The role for this round is Engineering. Production release,
incident migration and delivery require a separate typed Operator execution.

## Contract and incident

The sole goal is to repair redundant Research OS DDL and restore the registered
2026103 settlement replay. Preserve the failed execution, old manifests,
artifacts, notification ledger, frozen scientific definitions and source bytes.
No model, strategy, threshold, Evidence, P4/P5/P6 or retired V11 work is included.

At 2026-09-06 21:57 CST, execution
`62bef55f17cb2d2cb6dee639afc2b6128c77a7ab32743495477715ec66b7ef5f`
failed with a PostgreSQL deadlock. The failure event
`dfe22cc7acbeb84baa585616540a25b583e88a7750e4371748e1ca0bbbeff1cb`
persisted, but the subsequent failure-state import was rejected by the frozen
successor transition guard. The task remained `running` at manifest
`c868353673facb6219f033252555750b0e5f2a3ed4f9707b3b43200d861d045b`.

The 2026103 settlement had already completed; its registered settlement digest
is `f58de9b214e6ace1229e8635324098344db4d75b2f8936cd0e5aa65204b42644`.
2026104 draw data arrived on September 8, but there is no registered pre-draw
prediction for it. That missed run cannot be reconstructed as a forward result.

## Implementation boundary

`ensure_research_os_schema` applies each schema digest once across processes.
The digest marker and DDL commit together; a transaction advisory lock serializes
first installation and upgrades. An already installed digest uses reads only,
avoiding repeated ALTER TABLE and trigger replacement during publication.

The incident migration accepts only the exact original head, task digest,
started/failed event pair, source digest and upstream settlement. It requires a
completed #812 and an active, bound Operator release. It appends a manifest that
makes this one replay task Ready (reusing an identical existing manifest when
present), plus an immutable operational observation in
the same transaction. It does not change the failed execution or mark it
successful. The unchanged Supervisor runs a new execution under the repaired
commit and owns all completion facts, artifacts and status publication.

The source-bound Supervisor, Repository, successor runner, notification code
and source manifests remain byte-identical. No general retry or source guard
exception is introduced. The recovery entry point stops if an additional
execution, partial registration, changed head, changed source or duplicate
attestation is found. A failed new attempt requires further review.

## Mainline declaration

| Field | Binding |
| --- | --- |
| Goal | `M4_P3_FORWARD_PREQUENTIAL_CONFIRMATORY_SUCCESSOR_V1` |
| Ready condition | Exact incident migration and original settlement dependency |
| Runner | Unchanged `ForwardPrequentialSupervisor` / unified Supervisor |
| Upstream | Frozen source, 2026103 predraw replay, registered settlement |
| Downstream | Registered settlement replay and existing Top-100 post report |
| Status | Existing manifest, resolver, Ready Queue and task state projection |
| Evidence rule | Operational repair only; no additional issue or scientific Evidence |
| Decision consumer | Existing frozen P3 policy |
| Next consumer | Existing notification report and canonical next-issue preparation |

## Validation and integration

Local validation:

- `python -m pytest -q tests/test_research_os_schema.py tests/test_postgres_store.py tests/test_p3_top100_notification.py`: **66 passed**.
- `DEHPS_TEST_POSTGRES=1 DEHPS_P3_INCIDENT_REPLAY=1 python -m pytest -q tests/test_p3_2026103_recovery.py`: **6 passed, 102 seconds**. The incident artifact root was `/home/ark/workspace/dehps`; the database URL was supplied privately through the environment.
- The PostgreSQL test copied Research OS rows into disposable schemas and
  registered artifact files into separate temporary directories. It proved the
  exact Ready transition, a new canonical execution, typed and generic replay,
  successful existing postdraw-bundle consumption, unchanged original failed
  event bytes, and one operational recovery observation. It also checked wrong
  executor/commit and altered-event rejection, concurrent initial DDL,
  rollback, and schema reads while an atomic-publication table lock is held.
- `git diff --check`: passed.

An additional run of `test_m4_p3_forward_prequential_confirmatory.py` exposed a
pre-existing failure in
`test_source_contract_and_old_lineage_are_both_replay_verifiable`:
`bounded_forward_source_bytes_changed:apps/worker-python/dehps/research_os/repository.py`.
The identical node fails on the unmodified main worktree at `745a06e`; that
Repository file is unchanged by this round and by `origin/main` at `4f9c794`.
The combined broader selection was **70 passed, 1 failed**. This round does not
claim a passing full worker suite or modify the archived lineage contract.

Production recovery and mail delivery have not yet run with this change.

| Integration stage | Current proof |
| --- | --- |
| Goal, Resolver, Ready Queue | Validated in isolated incident clone |
| Supervisor, artifacts, status | New execution completed in isolated clone |
| Existing downstream consumer | Postdraw bundle loaded in isolated clone |
| Deterministic replay | Typed and generic replay passed in isolated clone |
| Canonical production execution and delivery | Pending separate Operator release |

Training-mainline integration: **NO — INTEGRATION_PENDING**.
