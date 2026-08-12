from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import jsonschema

from dehps.agents.errors import (
    AgentAuthorizationError,
    AgentRequestConflictError,
    AgentRequestValidationError,
)
from dehps.agents.repository import (
    AgentRequestExecutionMetadata,
    AgentRequestRepository,
)
from dehps.agents.requests import (
    AgentRequest,
    AgentRequestType,
    AgentRiskLevel,
)
from dehps.agents.roles import AgentRole
from dehps.agents.service import AgentRequestService

TOOL_NAMES = (
    "dehps_lifecycle_request_get",
    "dehps_lifecycle_request_create",
    "dehps_lifecycle_request_submit",
    "dehps_lifecycle_request_review",
    "dehps_lifecycle_request_approve",
    "dehps_lifecycle_request_reject",
    "dehps_lifecycle_execution_start",
    "dehps_lifecycle_execution_complete",
    "dehps_lifecycle_execution_fail",
)
ROLE_VALUES = [role.value for role in AgentRole]
REQUEST_TYPE_VALUES = [request_type.value for request_type in AgentRequestType]
ENVIRONMENT_VALUES = ["isolated", "development", "production"]
RISK_VALUES = [risk.value for risk in AgentRiskLevel]
FULL_PAYLOAD_TYPES = frozenset(
    {AgentRequestType.ENGINEERING_IMPLEMENTATION, AgentRequestType.RESEARCH_SCHEDULER_REQUEST}
)
FORBIDDEN_EXECUTION_COLUMNS = frozenset(
    {"result_json", "error_json", "artifact_paths_json"}
)
FORBIDDEN_DECISION_COLUMNS = frozenset({"reason_json"})
FORBIDDEN_RESPONSE_KEYS = frozenset(
    {"result", "error", "artifact_paths", *FORBIDDEN_EXECUTION_COLUMNS, *FORBIDDEN_DECISION_COLUMNS}
)

PROVENANCE = {
    "request": "agent_requests.identity_columns.direct_single_table.v1",
    "request_contract_payload": "agent_requests.payload_json.direct_single_table.closed_schema.v1",
    "request_contract_payload_sha256": (
        "agent_requests.metadata_json.payload_sha256.pre_attested_at_create.v1"
    ),
    "decision": (
        "agent_request_decisions.metadata_columns.no_reason_json.direct_single_table.v1"
    ),
    "execution": (
        "agent_request_executions.metadata_columns.no_result_error_artifact_paths."
        "direct_single_table.v1"
    ),
    "mixed_provenance": False,
}


def _object_schema(properties: Mapping[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": required,
        "additionalProperties": False,
    }


REQUEST_KEY = {"type": "string", "minLength": 1}
ACTOR_ID = {"type": "string", "minLength": 1}
ROLE = {"type": "string", "enum": ROLE_VALUES}
ENVIRONMENT = {"type": "string", "enum": ENVIRONMENT_VALUES}
REASON = {"type": "object"}

TOOL_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    TOOL_NAMES[0]: _object_schema({"request_key": REQUEST_KEY}, ["request_key"]),
    TOOL_NAMES[1]: _object_schema(
        {
            "request_key": REQUEST_KEY,
            "request_type": {"type": "string", "enum": REQUEST_TYPE_VALUES},
            "requested_by_role": ROLE,
            "requested_by": ACTOR_ID,
            "actor_role": ROLE,
            "actor_id": ACTOR_ID,
            "title": {"type": "string", "minLength": 1},
            "summary": {"type": "string"},
            "payload": {"type": "object"},
            "environment": ENVIRONMENT,
            "risk_level": {"type": "string", "enum": RISK_VALUES},
            "hypothesis_key": {"type": ["string", "null"]},
            "experiment_key": {"type": ["string", "null"]},
            "parent_request_key": {"type": ["string", "null"]},
            "metadata": {"type": "object"},
        },
        [
            "request_key", "request_type", "requested_by_role", "requested_by",
            "actor_role", "actor_id", "title", "summary", "payload", "environment",
            "risk_level", "hypothesis_key", "experiment_key", "parent_request_key", "metadata",
        ],
    ),
    TOOL_NAMES[2]: _object_schema(
        {
            "request_key": REQUEST_KEY,
            "actor_role": ROLE,
            "actor_id": ACTOR_ID,
            "expected_status": {"const": "draft"},
            "environment": ENVIRONMENT,
        },
        ["request_key", "actor_role", "actor_id", "expected_status", "environment"],
    ),
    TOOL_NAMES[3]: _object_schema(
        {
            "request_key": REQUEST_KEY,
            "reviewer_role": {"const": "reviewer"},
            "reviewer_id": ACTOR_ID,
            "expected_status": {"const": "submitted"},
            "environment": ENVIRONMENT,
        },
        ["request_key", "reviewer_role", "reviewer_id", "expected_status", "environment"],
    ),
    TOOL_NAMES[4]: _object_schema(
        {
            "request_key": REQUEST_KEY,
            "reviewer_role": {"const": "reviewer"},
            "reviewer_id": ACTOR_ID,
            "expected_status": {"const": "under_review"},
            "environment": ENVIRONMENT,
            "reason": REASON,
        },
        ["request_key", "reviewer_role", "reviewer_id", "expected_status", "environment", "reason"],
    ),
    TOOL_NAMES[5]: _object_schema(
        {
            "request_key": REQUEST_KEY,
            "reviewer_role": {"const": "reviewer"},
            "reviewer_id": ACTOR_ID,
            "expected_status": {"const": "under_review"},
            "environment": ENVIRONMENT,
            "reason": REASON,
        },
        ["request_key", "reviewer_role", "reviewer_id", "expected_status", "environment", "reason"],
    ),
    TOOL_NAMES[6]: _object_schema(
        {
            "request_key": REQUEST_KEY,
            "executor_role": ROLE,
            "executor_id": ACTOR_ID,
            "expected_status": {"const": "approved"},
            "environment": ENVIRONMENT,
            "run_id": {"type": ["string", "null"]},
        },
        ["request_key", "executor_role", "executor_id", "expected_status", "environment", "run_id"],
    ),
    TOOL_NAMES[7]: _object_schema(
        {
            "request_key": REQUEST_KEY,
            "execution_id": {"type": "integer", "minimum": 1},
            "executor_role": ROLE,
            "executor_id": ACTOR_ID,
            "expected_status": {"const": "executing"},
            "result": {"type": "object"},
            "artifact_paths": {"type": "array", "items": {"type": "string"}},
        },
        ["request_key", "execution_id", "executor_role", "executor_id", "expected_status", "result", "artifact_paths"],
    ),
    TOOL_NAMES[8]: _object_schema(
        {
            "request_key": REQUEST_KEY,
            "execution_id": {"type": "integer", "minimum": 1},
            "executor_role": ROLE,
            "executor_id": ACTOR_ID,
            "expected_status": {"const": "executing"},
            "error": {"type": "object"},
        },
        ["request_key", "execution_id", "executor_role", "executor_id", "expected_status", "error"],
    ),
}


def canonical_json_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _serialize(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value


def validate_closed_request_payload(request_type: AgentRequestType, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise AgentRequestValidationError("request contract payload must be an object")
    value = dict(payload)
    if request_type == AgentRequestType.ENGINEERING_IMPLEMENTATION:
        if set(value) != {"scope", "acceptance", "non_goals"}:
            raise AgentRequestValidationError("engineering_implementation payload schema is not closed")
        if not isinstance(value["scope"], (str, Mapping)) or not isinstance(
            value["acceptance"], (str, Mapping)
        ) or not isinstance(value["non_goals"], list):
            raise AgentRequestValidationError("engineering_implementation payload types are invalid")
    elif request_type == AgentRequestType.RESEARCH_SCHEDULER_REQUEST:
        if set(value) != {"queue_key", "action", "reason", "context_fingerprint", "budget"}:
            raise AgentRequestValidationError("research_scheduler_request payload schema is not closed")
        if not all(isinstance(value[key], str) for key in ("queue_key", "action", "reason")):
            raise AgentRequestValidationError("research scheduler string fields are invalid")
        fingerprint = value["context_fingerprint"]
        if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(
            char not in "0123456789abcdef" for char in fingerprint
        ):
            raise AgentRequestValidationError("context_fingerprint must be 64 lowercase hex characters")
        if not isinstance(value["budget"], Mapping):
            raise AgentRequestValidationError("research scheduler budget must be an object")
    else:
        raise AgentRequestValidationError("request type is digest-only")
    return value


def source_aware_sanitize(value: Any, *, source: str, mixed_provenance: bool = False) -> Any:
    """Fail closed on result-bearing keys except a validated request contract payload."""
    if mixed_provenance:
        raise AgentRequestValidationError("mixed provenance responses are forbidden")
    if source == "request_contract_payload.closed_schema":
        return _serialize(value)
    if isinstance(value, Mapping):
        forbidden = FORBIDDEN_RESPONSE_KEYS.intersection(str(key) for key in value)
        if forbidden:
            raise AgentRequestValidationError(
                f"forbidden {source} response keys: {', '.join(sorted(forbidden))}"
            )
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            item_source = source
            if source == "adapter_response" and key == "request_contract_payload":
                item_source = "request_contract_payload.closed_schema"
            sanitized[str(key)] = source_aware_sanitize(item, source=item_source)
        return sanitized
    if isinstance(value, (list, tuple)):
        return [source_aware_sanitize(item, source=source) for item in value]
    return _serialize(value)


class AgentLifecycleAdapter:
    def __init__(
        self,
        repository: AgentRequestRepository,
        service: AgentRequestService | None = None,
    ) -> None:
        self.repository = repository
        self.service = service or AgentRequestService(repository)

    def call(self, tool_name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        if tool_name not in TOOL_INPUT_SCHEMAS:
            raise AgentRequestValidationError(f"unknown lifecycle tool: {tool_name}")
        jsonschema.validate(dict(arguments), TOOL_INPUT_SCHEMAS[tool_name])
        handlers = {
            TOOL_NAMES[0]: self.request_get,
            TOOL_NAMES[1]: self.request_create,
            TOOL_NAMES[2]: self.request_submit,
            TOOL_NAMES[3]: self.request_review,
            TOOL_NAMES[4]: self.request_approve,
            TOOL_NAMES[5]: self.request_reject,
            TOOL_NAMES[6]: self.execution_start,
            TOOL_NAMES[7]: self.execution_complete,
            TOOL_NAMES[8]: self.execution_fail,
        }
        response = handlers[tool_name](**dict(arguments))
        return source_aware_sanitize(response, source="adapter_response")

    def request_get(self, request_key: str) -> dict[str, Any]:
        metadata_row = self.repository.get_request_contract(request_key, include_payload=False)
        request_type = AgentRequestType(metadata_row["request_type"])
        payload = None
        payload_provenance = None
        if request_type in FULL_PAYLOAD_TYPES:
            row = self.repository.get_request_contract(request_key, include_payload=True)
            payload = validate_closed_request_payload(request_type, row.get("payload_json"))
            payload = source_aware_sanitize(
                payload, source="request_contract_payload.closed_schema"
            )
            payload_provenance = PROVENANCE["request_contract_payload"]
        digest = self._payload_digest(metadata_row)
        return self._response(
            request=self._request_identity(metadata_row),
            payload=payload,
            payload_digest=digest,
            payload_provenance=payload_provenance,
            decisions=self.repository.list_decision_metadata(request_key),
            executions=self.repository.list_execution_metadata(request_key),
        )

    def request_create(self, **arguments: Any) -> dict[str, Any]:
        actor_role = AgentRole(arguments.pop("actor_role"))
        actor_id = str(arguments.pop("actor_id"))
        requested_by_role = AgentRole(arguments.pop("requested_by_role"))
        requested_by = str(arguments.pop("requested_by"))
        if actor_role != requested_by_role or actor_id != requested_by:
            raise AgentAuthorizationError("create caller must equal the recorded requester")
        payload = dict(arguments.pop("payload"))
        digest = canonical_json_sha256(payload)
        metadata = dict(arguments.pop("metadata"))
        if "payload_sha256" in metadata and metadata["payload_sha256"] != digest:
            raise AgentRequestValidationError("caller payload_sha256 conflicts with canonical payload")
        metadata["payload_sha256"] = digest
        request = self.service.create_draft(
            requested_by_role=requested_by_role,
            requested_by=requested_by,
            request_type=AgentRequestType(arguments.pop("request_type")),
            risk_level=AgentRiskLevel(arguments.pop("risk_level")),
            payload=payload,
            metadata=metadata,
            **arguments,
        )
        return self.request_get(request.request_key)

    def request_submit(self, **arguments: Any) -> dict[str, Any]:
        self._expect_status(arguments["request_key"], arguments.pop("expected_status"))
        request = self.service.submit(
            arguments.pop("request_key"),
            actor_role=AgentRole(arguments.pop("actor_role")),
            **arguments,
        )
        return self.request_get(request.request_key)

    def request_review(self, **arguments: Any) -> dict[str, Any]:
        self._expect_status(arguments["request_key"], arguments.pop("expected_status"))
        request = self.service.begin_review(
            arguments.pop("request_key"),
            reviewer_role=AgentRole(arguments.pop("reviewer_role")),
            **arguments,
        )
        return self.request_get(request.request_key)

    def request_approve(self, **arguments: Any) -> dict[str, Any]:
        return self._review_resolution(self.service.approve, arguments)

    def request_reject(self, **arguments: Any) -> dict[str, Any]:
        return self._review_resolution(self.service.reject, arguments)

    def _review_resolution(self, method: Any, arguments: dict[str, Any]) -> dict[str, Any]:
        self._expect_status(arguments["request_key"], arguments.pop("expected_status"))
        request = method(
            arguments.pop("request_key"),
            reviewer_role=AgentRole(arguments.pop("reviewer_role")),
            **arguments,
        )
        return self.request_get(request.request_key)

    def execution_start(self, **arguments: Any) -> dict[str, Any]:
        self._expect_status(arguments["request_key"], arguments.pop("expected_status"))
        request, execution = self.service.begin_execution_metadata(
            arguments.pop("request_key"),
            executor_role=AgentRole(arguments.pop("executor_role")),
            **arguments,
        )
        del execution
        return self.request_get(request.request_key)

    def execution_complete(self, **arguments: Any) -> dict[str, Any]:
        self._expect_status(arguments["request_key"], arguments.pop("expected_status"))
        request, execution = self.service.complete_execution_metadata(
            arguments.pop("request_key"),
            executor_role=AgentRole(arguments.pop("executor_role")),
            **arguments,
        )
        del execution
        return self.request_get(request.request_key)

    def execution_fail(self, **arguments: Any) -> dict[str, Any]:
        self._expect_status(arguments["request_key"], arguments.pop("expected_status"))
        request, execution = self.service.fail_execution_metadata(
            arguments.pop("request_key"),
            executor_role=AgentRole(arguments.pop("executor_role")),
            **arguments,
        )
        del execution
        return self.request_get(request.request_key)

    def _expect_status(self, request_key: str, expected_status: str) -> None:
        row = self.repository.get_request_contract(request_key, include_payload=False)
        actual = str(row["status"])
        if actual != expected_status:
            raise AgentRequestConflictError(
                f"request status changed: expected {expected_status}, found {actual}"
            )
        self._payload_digest(row)

    @staticmethod
    def _payload_digest(row: Mapping[str, Any]) -> str:
        metadata = row.get("metadata_json")
        digest = metadata.get("payload_sha256") if isinstance(metadata, Mapping) else None
        if not isinstance(digest, str) or len(digest) != 64 or any(
            char not in "0123456789abcdef" for char in digest
        ):
            raise AgentRequestValidationError("missing or malformed pre-attested payload_sha256")
        return digest

    @staticmethod
    def _request_identity(row: Mapping[str, Any] | AgentRequest) -> dict[str, Any]:
        if isinstance(row, AgentRequest):
            values = {
                "id": row.id,
                "request_key": row.request_key,
                "request_type": row.request_type,
                "requested_by_role": row.requested_by_role,
                "requested_by": row.requested_by,
                "status": row.status,
                "risk_level": row.risk_level,
                "requires_review": row.requires_review,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "submitted_at": row.submitted_at,
                "resolved_at": row.resolved_at,
            }
        else:
            values = {key: row.get(key) for key in (
                "id", "request_key", "request_type", "requested_by_role", "requested_by",
                "status", "risk_level", "requires_review", "created_at", "updated_at",
                "submitted_at", "resolved_at",
            )}
        return _serialize(values)

    def _request_response(
        self,
        request: AgentRequest,
        *,
        execution: AgentRequestExecutionMetadata | None = None,
    ) -> dict[str, Any]:
        digest = self._payload_digest({"metadata_json": request.metadata})
        payload = None
        payload_provenance = None
        if request.request_type in FULL_PAYLOAD_TYPES:
            payload = validate_closed_request_payload(request.request_type, request.payload)
            payload = source_aware_sanitize(
                payload, source="request_contract_payload.closed_schema"
            )
            payload_provenance = PROVENANCE["request_contract_payload"]
        return self._response(
            request=self._request_identity(request),
            payload=payload,
            payload_digest=digest,
            payload_provenance=payload_provenance,
            executions=[] if execution is None else [execution],
        )

    @staticmethod
    def _response(
        *,
        request: Mapping[str, Any],
        payload: Mapping[str, Any] | None,
        payload_digest: str,
        payload_provenance: str | None,
        decisions: Any = None,
        executions: Any = None,
    ) -> dict[str, Any]:
        provenance = dict(PROVENANCE)
        provenance["request_contract_payload"] = payload_provenance
        provenance["decision"] = PROVENANCE["decision"] if decisions is not None else None
        provenance["execution"] = PROVENANCE["execution"] if executions is not None else None
        return {
            "request": _serialize(request),
            "request_contract_payload": _serialize(payload),
            "request_contract_payload_sha256": payload_digest,
            "decisions": _serialize(decisions),
            "executions": _serialize(executions),
            "source_provenance": provenance,
        }
