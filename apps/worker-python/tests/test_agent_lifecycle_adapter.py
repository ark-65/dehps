from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from dehps.agents.errors import (
    AgentAuthorizationError,
    AgentRequestConflictError,
    AgentRequestValidationError,
)
from dehps.agents.lifecycle_adapter import (
    PROVENANCE,
    TOOL_INPUT_SCHEMAS,
    TOOL_NAMES,
    AgentLifecycleAdapter,
    canonical_json_sha256,
    source_aware_sanitize,
    validate_closed_request_payload,
)
from dehps.agents.repository import (
    AgentRequestExecutionMetadata,
    AgentRequestRepository,
)
from dehps.agents.requests import (
    AgentExecutionStatus,
    AgentRequest,
    AgentRequestStatus,
    AgentRequestType,
    AgentRiskLevel,
)
from dehps.agents.roles import AgentRole
from dehps.agents.service import AgentRequestService

NOW = datetime(2026, 8, 12, tzinfo=UTC)


def request(
    *,
    status: AgentRequestStatus = AgentRequestStatus.DRAFT,
    risk: AgentRiskLevel = AgentRiskLevel.MEDIUM,
    request_type: AgentRequestType = AgentRequestType.ENGINEERING_IMPLEMENTATION,
) -> AgentRequest:
    payload = {"scope": "adapter", "acceptance": "tests", "non_goals": []}
    return AgentRequest(
        id=1,
        request_key="eng-adapter",
        request_type=request_type,
        requested_by_role=AgentRole.ENGINEERING,
        requested_by="engineering:owner",
        hypothesis_id=None,
        experiment_id=None,
        parent_request_id=None,
        title="Typed lifecycle adapter",
        summary="",
        payload=payload,
        status=status,
        risk_level=risk,
        requires_review=True,
        created_at=NOW,
        updated_at=NOW,
        submitted_at=None,
        resolved_at=None,
        metadata={"payload_sha256": canonical_json_sha256(payload)},
    )


class MemoryRepository:
    def __init__(self, value: AgentRequest | None = None) -> None:
        self.value = value or request()
        self.executions: list[AgentRequestExecutionMetadata] = []

    def get_request(self, request_key: str) -> AgentRequest:
        return self.value

    def get_request_contract(self, request_key: str, *, include_payload: bool):
        row = {
            "id": self.value.id,
            "request_key": self.value.request_key,
            "request_type": self.value.request_type.value,
            "requested_by_role": self.value.requested_by_role.value,
            "requested_by": self.value.requested_by,
            "status": self.value.status.value,
            "risk_level": self.value.risk_level.value,
            "requires_review": True,
            "created_at": NOW,
            "updated_at": NOW,
            "submitted_at": None,
            "resolved_at": None,
            "metadata_json": self.value.metadata,
        }
        if include_payload:
            row["payload_json"] = self.value.payload
        return row

    def list_decision_metadata(self, request_key: str):
        return []

    def list_execution_metadata(self, request_key: str):
        return self.executions

    def get_execution_metadata(self, request_key: str, execution_id: int):
        return next(execution for execution in self.executions if execution.id == execution_id)

    def transition(self, **arguments):
        if self.value.status != arguments["expected_status"]:
            raise AgentRequestConflictError("stale")
        self.value = replace(self.value, status=arguments["new_status"])
        return self.value


def test_tool_surface_and_schemas_are_closed_and_exact() -> None:
    assert TOOL_NAMES == (
        "dehps_lifecycle_request_get", "dehps_lifecycle_request_create",
        "dehps_lifecycle_request_submit", "dehps_lifecycle_request_review",
        "dehps_lifecycle_request_approve", "dehps_lifecycle_request_reject",
        "dehps_lifecycle_execution_start", "dehps_lifecycle_execution_complete",
        "dehps_lifecycle_execution_fail",
    )
    assert tuple(TOOL_INPUT_SCHEMAS) == TOOL_NAMES
    assert all(schema["additionalProperties"] is False for schema in TOOL_INPUT_SCHEMAS.values())


def test_request_get_returns_closed_payload_and_exact_provenance() -> None:
    response = AgentLifecycleAdapter(MemoryRepository()).request_get("eng-adapter")  # type: ignore[arg-type]
    assert response["request_contract_payload"] == {
        "scope": "adapter", "acceptance": "tests", "non_goals": []
    }
    assert response["source_provenance"]["request_contract_payload"] == PROVENANCE[
        "request_contract_payload"
    ]
    assert response["source_provenance"]["mixed_provenance"] is False


def test_digest_only_get_never_requests_payload_and_fails_closed_without_digest() -> None:
    repository = MemoryRepository(
        request(request_type=AgentRequestType.ENGINEERING_BUG_FIX)
    )
    repository.value = replace(repository.value, metadata={})
    adapter = AgentLifecycleAdapter(repository)  # type: ignore[arg-type]
    with pytest.raises(AgentRequestValidationError, match="payload_sha256"):
        adapter.request_get("eng-adapter")


def test_source_aware_sanitizer_blocks_execution_and_decision_payload_names() -> None:
    for value in (
        {"result_json": {}}, {"nested": {"error": {}}}, {"reason_json": {}},
        {"artifact_paths": []},
    ):
        with pytest.raises(AgentRequestValidationError, match="forbidden"):
            source_aware_sanitize(value, source="execution")


def test_closed_contract_allows_same_named_authorization_fields() -> None:
    payload = {
        "scope": {"result": "write-only input", "error": "write-only input"},
        "acceptance": {"artifact_paths": []},
        "non_goals": [],
    }
    validated = validate_closed_request_payload(
        AgentRequestType.ENGINEERING_IMPLEMENTATION, payload
    )
    assert source_aware_sanitize(
        validated, source="request_contract_payload.closed_schema"
    ) == payload
    with pytest.raises(AgentRequestValidationError, match="mixed provenance"):
        source_aware_sanitize(payload, source="request_contract_payload.closed_schema", mixed_provenance=True)


def test_owner_status_and_reviewer_separation_enforcement() -> None:
    repository = MemoryRepository()
    service = AgentRequestService(repository)  # type: ignore[arg-type]
    with pytest.raises(AgentAuthorizationError, match="recorded requester"):
        service.submit(
            "eng-adapter",
            actor_role=AgentRole.ENGINEERING,
            actor_id="engineering:not-owner",
        )
    repository.value = replace(
        repository.value,
        status=AgentRequestStatus.SUBMITTED,
        risk_level=AgentRiskLevel.CRITICAL,
    )
    with pytest.raises(AgentAuthorizationError, match="must differ"):
        service.begin_review(
            "eng-adapter",
            reviewer_role=AgentRole.REVIEWER,
            reviewer_id="engineering:owner",
        )


def test_critical_reviewer_may_not_be_a_recorded_executor() -> None:
    repository = MemoryRepository(
        replace(request(), status=AgentRequestStatus.SUBMITTED, risk_level=AgentRiskLevel.CRITICAL)
    )
    repository.executions.append(
        AgentRequestExecutionMetadata(
            id=2, request_id=1, executor_role=AgentRole.ENGINEERING,
            executor_id="reviewer:conflict", execution_type="modify_code",
            status=AgentExecutionStatus.COMPLETED, environment="development", run_id=None,
            started_at=NOW, completed_at=NOW, created_at=NOW,
        )
    )
    with pytest.raises(AgentAuthorizationError, match="recorded executor"):
        AgentRequestService(repository).begin_review(  # type: ignore[arg-type]
            "eng-adapter", reviewer_role=AgentRole.REVIEWER,
            reviewer_id="reviewer:conflict", environment="development",
        )


def test_stale_expected_status_fails_before_mutation() -> None:
    adapter = AgentLifecycleAdapter(MemoryRepository())  # type: ignore[arg-type]
    with pytest.raises(AgentRequestConflictError, match="expected submitted"):
        adapter.call(
            "dehps_lifecycle_request_review",
            {
                "request_key": "eng-adapter", "reviewer_role": "reviewer",
                "reviewer_id": "reviewer:a", "expected_status": "submitted",
                "environment": "development",
            },
        )


def test_operator_start_schema_requires_run_id_field() -> None:
    required = TOOL_INPUT_SCHEMAS["dehps_lifecycle_execution_start"]["required"]
    assert "run_id" in required


class SqlResult:
    def __init__(self, *, row=None, rows=None) -> None:
        self.row = row
        self.rows = rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class SqlSpy:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self, row_factory=None):
        return self

    def execute(self, sql, params=None):
        compact = " ".join(sql.split())
        self.statements.append(compact)
        if compact == "SELECT id FROM agent_requests WHERE request_key = %s":
            return SqlResult(row={"id": 1})
        if "FROM agent_request_decisions" in compact:
            return SqlResult(rows=[])
        if "FROM agent_request_executions" in compact:
            return SqlResult(rows=[])
        raise AssertionError(compact)


def test_metadata_sql_spy_excludes_sensitive_read_columns() -> None:
    connection = SqlSpy()

    @contextmanager
    def factory():
        with connection:
            yield connection

    repository = AgentRequestRepository(factory)  # type: ignore[arg-type]
    repository.list_decision_metadata("eng-adapter")
    repository.list_execution_metadata("eng-adapter")
    read_sql = " ".join(connection.statements).lower()
    assert "reason_json" not in read_sql
    assert "result_json" not in read_sql
    assert "error_json" not in read_sql
    assert "artifact_paths_json" not in read_sql
    assert "select *" not in read_sql
