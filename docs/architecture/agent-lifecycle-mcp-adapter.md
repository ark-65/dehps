# Project-scoped typed Agent lifecycle MCP adapter

Status: `CODE_COMPLETE`; capability status: `INTEGRATION_PENDING` until a later
Codex process reloads the project MCP configuration and successfully performs a
metadata-only lifecycle replay. This implementation does not start a Supervisor,
workload, P3/P4 fold, release, or production operation.

## Purpose and boundary

The adapter replaces pasted lifecycle Shell with nine typed project tools. It is
not a general automation bridge. Every mutation is routed through
`AgentRequestService` and `AgentAuthorityPolicy`; the MCP layer has no generic
Shell, SQL, filesystem, git, Supervisor, workload, artifact, hypothesis,
promotion, P3, or P4 tool.

The exact exposed tool order is:

1. `dehps_lifecycle_request_get`
2. `dehps_lifecycle_request_create`
3. `dehps_lifecycle_request_submit`
4. `dehps_lifecycle_request_review`
5. `dehps_lifecycle_request_approve`
6. `dehps_lifecycle_request_reject`
7. `dehps_lifecycle_execution_start`
8. `dehps_lifecycle_execution_complete`
9. `dehps_lifecycle_execution_fail`

Each input schema is closed with `additionalProperties: false`. Roles, request
types, risk levels, environments, and expected statuses use enums or constants.
The expected status is checked immediately before a mutation, so stale or
concurrent callers fail without broadening authority. Create requires the caller
role/id to equal the recorded requester. Submit requires that recorded owner.
Review actions require Reviewer authority. A critical request also requires the
Reviewer id to differ from the requester and every recorded executor. Execution
requires an approved request and repeats policy authorization at start. Only the
recorded running executor can complete or fail an execution. Operator execution
requires a non-empty `run_id`.

## Result-blind storage contract

The adapter-specific repository and service paths never select, return,
materialize, log, or hash these execution columns:

- `result_json`
- `error_json`
- `artifact_paths_json`

They also never select, return, materialize, log, or hash decision
`reason_json`. Completion inputs are parameterized writes only. Metadata-only
`SELECT` and `RETURNING` clauses enumerate safe execution and decision columns;
they do not use `*`. Responses recursively reject result-bearing keys from
execution, decision, caller, or mixed provenance.

The narrow exception is a typed `request_contract_payload`. It has direct,
single-table provenance from `agent_requests.payload_json`, with no join,
subquery, view, derived value, or mixed provenance. Only these two closed schemas
may return full payload bytes:

- `engineering_implementation`: exactly `scope`, `acceptance`, `non_goals`;
  scope and acceptance are strings or objects and non_goals is an array.
- `research_scheduler_request`: exactly `queue_key`, `action`, `reason`,
  `context_fingerprint`, `budget`; the fingerprint is 64 lowercase hex and
  budget is an object.

Fields named `reason`, `result`, `error`, or `artifact_paths` inside one of those
validated authorization contracts are legal contract input and are not confused
with forbidden decision/execution output. Every other request type is
digest-only. Its response omits payload bytes and uses the canonical JSON SHA-256
attested in `agent_requests.metadata_json.payload_sha256` at create time. A
missing or malformed attestation fails closed.

Every response reports these exact provenance tags where applicable:

| Response field | Provenance tag |
| --- | --- |
| request | `agent_requests.identity_columns.direct_single_table.v1` |
| request_contract_payload | `agent_requests.payload_json.direct_single_table.closed_schema.v1` |
| request_contract_payload_sha256 | `agent_requests.metadata_json.payload_sha256.pre_attested_at_create.v1` |
| decisions | `agent_request_decisions.metadata_columns.no_reason_json.direct_single_table.v1` |
| executions | `agent_request_executions.metadata_columns.no_result_error_artifact_paths.direct_single_table.v1` |

`source_provenance.mixed_provenance` is always false.

## Project installation and activation

The server is registered in project-local `.codex/config.toml` and runs
`apps/worker-python/.venv/bin/python -m dehps.agents.lifecycle_mcp`. The worker
dependency is `mcp>=1.0,<2`. No user-global Codex configuration is modified.

Installation and current-process reload are deliberately outside the
implementation execution. A later authorized integration step must install the
worker dependencies if needed, restart or reload Codex so project MCP discovery
rereads `.codex/config.toml`, verify the exact `tools/list`, and perform a
metadata-only replay. Existing Codex processes do not acquire a newly registered
MCP server without that reload boundary.

## Validation and mainline status

Focused tests lock the exact tool list and schemas, role/owner/status boundaries,
critical Reviewer separation, Operator run-id requirement, provenance-aware
sanitization, digest-only failure behavior, SQL column exclusions, stdio
initialize/list behavior, and database-free invalid calls. The authorized worker
suite is the regression boundary. The six committed PyCharm project files are
hash-locked; `.idea/workspace.xml` remains ignored and is never force-added.

Training-mainline integration answer: **NO — INTEGRATION_PENDING**. This adapter
is governance infrastructure, not a completed training capability. A later typed
request must prove project discovery and deterministic lifecycle replay before
its status can advance beyond `CODE_COMPLETE`.
