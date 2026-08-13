from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest
from dehps.config import ROOT_DIR
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory import (
    predictive_route_reconciliation as route,
)
from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.information_theory.predictive_route_reconciliation import (
    ADAPTIVE_RESEARCH_ELIGIBILITY_FACT,
    ENGINEERING_EXECUTION_ID,
    ENGINEERING_REQUEST_ID,
    ENGINEERING_REVIEWER_APPROVAL_DECISION_ID,
    EQUAL_BUDGET_COMPARISON_RELATIONSHIP,
    GLOBAL_ROUTING_BRANCH_REPLAY_FACTS,
    GLOBAL_ROUTING_TASK_KEY,
    P2R_TASK_KEY,
    P2R_TO_P6_POLICY,
    P2R_TO_P6_POLICY_FACT,
    P4_TASK_KEY,
    P5_TASK_KEY,
    P6_TASK_KEY,
    POLICY_RESEARCH_EXECUTION_ID,
    POLICY_RESEARCH_REQUEST_ID,
    POLICY_RESEARCH_REQUEST_KEY,
    POLICY_REVIEWER_APPROVAL_DECISION_ID,
    PREDICTIVE_P3_PASS_TO_P4_FACT,
    PREDICTIVE_P3_PRIMARY_ENDPOINT,
    PREDICTIVE_P3_TASK_KEY,
    PREDICTIVE_ROUTE_DECISION,
    PREDICTIVE_ROUTE_DECISION_FACT,
    PREDICTIVE_ROUTE_RECONCILIATION_CAPABILITY,
    PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_CONTRACT_PATH,
    PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY,
    ROUTE_RESEARCH_EXECUTION_ID,
    ROUTE_RESEARCH_REQUEST_ID,
    ROUTE_RESEARCH_REQUEST_KEY,
    ROUTE_REVIEWER_APPROVAL_DECISION_ID,
    STRUCTURAL_P3_TERMINAL_DECISION,
    PredictiveRouteReconciliationArtifacts,
    PredictiveRouteReconciliationError,
    build_predictive_route_reconciliation_artifacts,
    governance_execution_metadata_digest,
    governance_request_identity_digest,
    governance_reviewer_decision_digest,
    load_predictive_route_reconciliation_source_contract,
    replay_predictive_route_reconciliation_artifacts,
    validate_repaired_manifest,
    validate_result_blind_authorizations,
    verify_predictive_route_reconciliation_source_bytes,
)
from dehps.research_os.information_theory.progress import build_m4_status
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import (
    ControlPlaneManifest,
    MainlineArtifactRegistration,
    TaskStatus,
)

from scripts import build_m4_p3_predictive_route_reconciliation_manifest as builder

MANIFEST_PATH = (
    ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"
)
INDEX_PATH = (
    ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
)
ENGINEERING_REQUEST_KEY = (
    "engineering-m4-p3-predictive-route-reconciliation-round-139-20260811"
)
P2_CLOSURE_TASK_KEY = "m4-p2-synthetic-measurement-validation"
P2_CLOSURE_COMPLETION_FACT = "m4-p2-closure:COMPLETE_WITH_REPAIR_OUTCOME"
P2_REPAIR_DECISION_FACT = (
    "m4-p2-measurement-decision:REPAIR_MEASUREMENT_SYSTEM"
)
P2_PASS_TO_P3_FACT = "m4-p2-measurement-decision:PASS_TO_P3"
P2R_EXECUTION_APPROVED_EVENT = (
    "research-contract:m4-p2r-measurement-repair-validation-execution:approved"
)
STRUCTURAL_COMPILER_TASK_KEY = (
    "m4-p3-result-blind-structural-utility-evidence-compiler"
)
STRUCTURAL_COMPILER_COMPLETION_FACT = (
    "m4-p3-result-blind-structural-utility-evidence-compiler:COMPLETE"
)
SOURCE_MODULE_PATH = Path(
    "apps/worker-python/dehps/research_os/information_theory/"
    "predictive_route_reconciliation.py"
)
SOURCE_PATHS = (
    SOURCE_MODULE_PATH,
    Path(
        "apps/worker-python/scripts/"
        "build_m4_p3_predictive_route_reconciliation_manifest.py"
    ),
    Path("apps/worker-python/dehps/research_os/control_plane.py"),
    Path("apps/worker-python/dehps/research_os/models.py"),
    Path(
        "apps/worker-python/dehps/research_os/information_theory/"
        "measurement_system_v2/migration.py"
    ),
    Path("apps/worker-python/dehps/research_os/supervisor.py"),
    Path("apps/worker-python/dehps/research_os/information_theory/progress.py"),
)


def _authorization_line(
    *,
    request_key: str,
    request_id: int,
    execution_id: int,
    decision_id: int,
    request_type: str,
    executor_role: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    request = {
        "id": request_id,
        "request_key": request_key,
        "request_type": request_type,
        "status": "completed",
        "parent_request_id": 468 if executor_role == "research" else 472,
        "payload": {
            "scope": "result-blind governance metadata only",
            "result_payload_reads": 0,
            "computation": 0,
        },
        "metadata": {"scientific_contract_change": False},
    }
    execution = {
        "id": execution_id,
        "request_id": request_id,
        "executor_role": executor_role,
        "executor_id": f"{executor_role}:codex",
        "execution_type": "isolated",
        "status": "completed",
        "environment": "isolated",
        "run_id": f"governance-{execution_id}",
        "started_at": f"2026-08-11T10:{execution_id % 60:02d}:00+08:00",
        "completed_at": f"2026-08-11T10:{execution_id % 60:02d}:01+08:00",
        "artifact_paths": [],
        "created_at": f"2026-08-11T10:{execution_id % 60:02d}:00+08:00",
    }
    decision = {
        "id": decision_id,
        "request_id": request_id,
        "previous_status": "under_review",
        "new_status": "approved",
        "decision_code": "request_approved",
        "summary": "Approved frozen zero-work governance scope",
        "reason": {
            "result_blind": True,
            "result_payload_reads": 0,
            "computation": 0,
        },
        "decided_by_role": "reviewer",
        "decided_by": "reviewer:codex-m4-p3-route-policy",
        "decided_at": f"2026-08-11T10:{decision_id % 60:02d}:00+08:00",
        "created_at": f"2026-08-11T10:{decision_id % 60:02d}:00+08:00",
    }
    frozen = {
        "request_key": request_key,
        "request_id": request_id,
        "execution_id": execution_id,
        "reviewer_approval_decision_id": decision_id,
        "request_identity_digest": governance_request_identity_digest(request),
        "execution_metadata_digest": governance_execution_metadata_digest(execution),
        "reviewer_approval_decision_digest": governance_reviewer_decision_digest(
            decision
        ),
    }
    return request, execution, decision, frozen


def _synthetic_contract_and_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    route_request, route_execution, route_decision, route_frozen = (
        _authorization_line(
            request_key=ROUTE_RESEARCH_REQUEST_KEY,
            request_id=ROUTE_RESEARCH_REQUEST_ID,
            execution_id=ROUTE_RESEARCH_EXECUTION_ID,
            decision_id=ROUTE_REVIEWER_APPROVAL_DECISION_ID,
            request_type="research_scheduler_request",
            executor_role="research",
        )
    )
    policy_request, policy_execution, policy_decision, policy_frozen = (
        _authorization_line(
            request_key=POLICY_RESEARCH_REQUEST_KEY,
            request_id=POLICY_RESEARCH_REQUEST_ID,
            execution_id=POLICY_RESEARCH_EXECUTION_ID,
            decision_id=POLICY_REVIEWER_APPROVAL_DECISION_ID,
            request_type="research_scheduler_request",
            executor_role="research",
        )
    )
    engineering_request, engineering_execution, engineering_decision, engineering_frozen = (
        _authorization_line(
            request_key=ENGINEERING_REQUEST_KEY,
            request_id=ENGINEERING_REQUEST_ID,
            execution_id=ENGINEERING_EXECUTION_ID,
            decision_id=ENGINEERING_REVIEWER_APPROVAL_DECISION_ID,
            request_type="engineering_implementation",
            executor_role="engineering",
        )
    )
    source_entries = [
        {
            "path": source_path.as_posix(),
            "content_sha256": hashlib.sha256(
                (ROOT_DIR / source_path).read_bytes()
            ).hexdigest(),
        }
        for source_path in SOURCE_PATHS
    ]
    contract: dict[str, Any] = {
        "schema_version": route.PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_SCHEMA,
        "artifact_type": route.PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_ARTIFACT_TYPE,
        "contract_key": route.PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_CONTRACT_KEY,
        "artifact_digest": "",
        "inspected_main_sha": (
            route.PREDICTIVE_ROUTE_RECONCILIATION_INSPECTED_MAIN_SHA
        ),
        "static_manifest_digest": (
            route.PREDICTIVE_ROUTE_RECONCILIATION_STATIC_MANIFEST_DIGEST
        ),
        "durable_manifest_digest": (
            route.PREDICTIVE_ROUTE_RECONCILIATION_DURABLE_MANIFEST_DIGEST
        ),
        "durable_snapshot_digest": (
            route.PREDICTIVE_ROUTE_RECONCILIATION_DURABLE_SNAPSHOT_DIGEST
        ),
        "route_decision": PREDICTIVE_ROUTE_DECISION,
        "p2r_to_p6_policy": P2R_TO_P6_POLICY,
        "prediction_p3_task_identity": {
            "task_key": PREDICTIVE_P3_TASK_KEY,
            "static_task_digest": "d" * 64,
            "durable_task_digest": "e" * 64,
        },
        "actual_dependencies": [
            {
                "dependency_type": "task",
                "target_key": P2_CLOSURE_TASK_KEY,
                "required_status": "completed",
            },
            {
                "dependency_type": "artifact",
                "target_key": P2_PASS_TO_P3_FACT,
                "required_status": "available",
            },
        ],
        "source_dependencies": [
            {
                "dependency_type": "task",
                "target_key": GLOBAL_ROUTING_TASK_KEY,
                "required_status": "completed",
            },
            {
                "dependency_type": "artifact",
                "target_key": ADAPTIVE_RESEARCH_ELIGIBILITY_FACT,
                "required_status": "available",
            },
        ],
        "global_routing_state": {
            "task_key": GLOBAL_ROUTING_TASK_KEY,
            "status": "dependency_wait",
            "completion_classification": "INTEGRATION_PENDING",
            "missing_replay_facts": list(GLOBAL_ROUTING_BRANCH_REPLAY_FACTS),
        },
        "adaptive_research_eligible_fact": {
            "fact": ADAPTIVE_RESEARCH_ELIGIBILITY_FACT,
            "available": False,
        },
        "p4_p5_p6_dependency_graph": {
            "p4": [PREDICTIVE_P3_TASK_KEY, PREDICTIVE_P3_PASS_TO_P4_FACT],
            "p5": [P4_TASK_KEY, "m4-forward-evidence-intake-2026085"],
            "p6": [
                P2_CLOSURE_TASK_KEY,
                PREDICTIVE_P3_TASK_KEY,
                P4_TASK_KEY,
                P5_TASK_KEY,
                P2R_TO_P6_POLICY_FACT,
            ],
        },
        "structural_p3_terminal_state": {
            "task_key": STRUCTURAL_COMPILER_TASK_KEY,
            "decision": STRUCTURAL_P3_TERMINAL_DECISION,
            "terminal": True,
            "fold_count": 90,
            "bootstrap_resamples": 20_000,
            "mainline": "VALIDATED_IN_MAINLINE",
            "replay": "REPLAY_VERIFIED",
        },
        "detected_drift": True,
        "drift_detail": {
            "surface": "durable_predictive_p3_dependencies",
            "static": [GLOBAL_ROUTING_TASK_KEY, ADAPTIVE_RESEARCH_ELIGIBILITY_FACT],
            "durable": [P2_CLOSURE_TASK_KEY, P2_PASS_TO_P3_FACT],
        },
        "old_goal_work_classification": {
            "A": [],
            "B": [],
            "C": [],
            "D": [],
            "result_blindness_potentially_breached": False,
        },
        "estimand_relationship": {
            "primary_endpoint": PREDICTIVE_P3_PRIMARY_ENDPOINT,
            "equal_budget_100_ticket_comparison_role": (
                EQUAL_BUDGET_COMPARISON_RELATIONSHIP
            ),
            "scientific_endpoint_changed": False,
            "contracts_merged": False,
        },
        "policy_effects": {
            "p2r_blocks_p3": False,
            "p2r_blocks_p4": False,
            "p2r_blocks_p5": False,
            "p6_research_summary_allowed_without_p2r": True,
            "promotion_blocked_until_p2r_acceptance": True,
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
        },
        "route_research_request": route_frozen,
        "policy_research_request": policy_frozen,
        "engineering_request": engineering_frozen,
        "policy_rationale": {
            "selected": P2R_TO_P6_POLICY,
            "promotion": "fail_closed_until_independent_p2r_acceptance",
        },
        "route_decision_rationale": {
            "selected": PREDICTIVE_ROUTE_DECISION,
            "scope": "identity_and_status_projection_only",
        },
        "next_legal_task": {
            "task_key": GLOBAL_ROUTING_TASK_KEY,
            "wait_reason": "three replay-verified branch decisions are absent",
        },
        "result_payload_reads": 0,
        "historical_database_reads": 0,
        "computation": 0,
        "new_historical_folds": 0,
        "evidence_created": False,
        "promotion_gate_opened": False,
        "production_action": "none",
        "source_entries": source_entries,
        "source_set_digest": config_digest({"source_entries": source_entries}),
    }
    contract["artifact_digest"] = config_digest(
        {key: value for key, value in contract.items() if key != "artifact_digest"}
    )
    inputs = {
        "route_research_request": route_request,
        "route_execution_metadata": route_execution,
        "route_decisions": [route_decision],
        "policy_research_request": policy_request,
        "policy_execution_metadata": policy_execution,
        "policy_decisions": [policy_decision],
        "engineering_request": engineering_request,
        "engineering_execution_metadata": engineering_execution,
        "engineering_decisions": [engineering_decision],
    }
    return contract, inputs


def _recompute_contract(contract: dict[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(contract)
    output["source_set_digest"] = config_digest(
        {"source_entries": output["source_entries"]}
    )
    output["artifact_digest"] = config_digest(
        {key: value for key, value in output.items() if key != "artifact_digest"}
    )
    return output


def _task(payload: dict[str, Any], task_key: str) -> dict[str, Any]:
    matches = [item for item in payload["tasks"] if item["task_key"] == task_key]
    assert len(matches) == 1
    return matches[0]


def _manifest(payload: dict[str, Any]) -> ControlPlaneManifest:
    normalized = copy.deepcopy(payload)
    normalized.pop("artifact_digest", None)
    normalized.pop("manifest_digest", None)
    return ControlPlaneManifest.from_dict(normalized)


def _resolution(payload: dict[str, Any], task_key: str):
    snapshot = ResearchOSControlPlane().resolve(_manifest(payload))
    return next(item for item in snapshot.resolutions if item.task_key == task_key)


def _source_payload(contract: dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return builder.build_source_payload(payload, source_contract=contract)


def _durable_drift_fixture(source_payload: dict[str, Any]) -> dict[str, Any]:
    """Build sanitized durable metadata with the audited legacy P3 dependency drift."""

    # Durable export is normalized; using that representation also proves the
    # migration does not rewrite omitted/default fields on unrelated tasks.
    live = _manifest(source_payload).to_dict(include_digest=False)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY
    ]
    global_task = next(
        task
        for task in live["tasks"]
        if task["task_key"] == "m4-v2-global-routing-recovery-v1"
    )
    global_task["task_key"] = GLOBAL_ROUTING_TASK_KEY
    for task in live["tasks"]:
        for dependency in task["dependencies"]:
            if dependency["target_key"] == "m4-v2-global-routing-recovery-v1":
                dependency["target_key"] = GLOBAL_ROUTING_TASK_KEY

    p3 = _task(live, PREDICTIVE_P3_TASK_KEY)
    p3["dependencies"] = [
        {
            "dependency_type": "task",
            "target_key": P2_CLOSURE_TASK_KEY,
            "required_status": "completed",
        },
        {
            "dependency_type": "artifact",
            "target_key": P2_PASS_TO_P3_FACT,
            "required_status": "available",
        },
    ]
    for key in (
        "route_decision",
        "route_identity_repaired",
        "scientific_contract_changed",
        "ticket_budget_comparison_relationship",
        "promotion_allowed",
    ):
        p3["metric_contract"].pop(key, None)

    p4 = _task(live, P4_TASK_KEY)
    p4["dependencies"] = [
        item
        for item in p4["dependencies"]
        if item["target_key"] != PREDICTIVE_P3_PASS_TO_P4_FACT
    ]
    for key in (
        "predictive_p3_pass_fact",
        "task_completion_alone_unlocks_p4",
        "p2r_blocks_research",
        "promotion_allowed",
    ):
        p4["metric_contract"].pop(key, None)

    p6 = _task(live, P6_TASK_KEY)
    p6["dependencies"] = [
        item
        for item in p6["dependencies"]
        if item["target_key"] != P2R_TO_P6_POLICY_FACT
    ]
    for key in (
        "p2r_to_p6_policy",
        "p2r_blocks_research_summary",
        "p2r_blocks_promotion",
        "promotion_release_fact",
        "promotion_gate_default",
        "promotion_allowed_in_this_capability",
        "prediction_v2_mode_while_p2r_pending",
        "prediction_v2_route_while_p2r_pending",
    ):
        p6["metric_contract"].pop(key, None)

    for task_key in (P2_CLOSURE_TASK_KEY, STRUCTURAL_COMPILER_TASK_KEY):
        task = _task(live, task_key)
        task["status"] = "completed"
        task["completion_classification"] = "COMPLETE"

    artifacts = live["facts"]["artifacts"]
    artifacts[:] = [
        value
        for value in artifacts
        if not value.startswith(builder.SOURCE_FACT_PREFIX)
        and not value.startswith("mainline-execution:" + P2_CLOSURE_TASK_KEY + ":")
        and not value.startswith("mainline-execution:" + STRUCTURAL_COMPILER_TASK_KEY + ":")
        and value
        not in {
            ADAPTIVE_RESEARCH_ELIGIBILITY_FACT,
            P2_PASS_TO_P3_FACT,
            PREDICTIVE_P3_PASS_TO_P4_FACT,
            P2R_TO_P6_POLICY_FACT,
            route.PREDICTIVE_ROUTE_RECONCILIATION_COMPLETION_FACT,
            route.PREDICTIVE_ROUTE_DECISION_FACT,
            *GLOBAL_ROUTING_BRANCH_REPLAY_FACTS,
        }
    ]
    for value in (
        P2_REPAIR_DECISION_FACT,
        P2_CLOSURE_COMPLETION_FACT,
        STRUCTURAL_COMPILER_COMPLETION_FACT,
    ):
        if value not in artifacts:
            artifacts.append(value)
    live["facts"]["external_events"] = [
        value
        for value in live["facts"]["external_events"]
        if value
        not in {
            builder.ROUTE_RESEARCH_APPROVED_EVENT,
            builder.POLICY_RESEARCH_APPROVED_EVENT,
            builder.ENGINEERING_APPROVED_EVENT,
            P2R_EXECUTION_APPROVED_EVENT,
        }
    ]

    manifest = _manifest(live)
    tasks = {item.task_key: item for item in manifest.tasks}
    artifacts.extend(
        [
            mainline_completion_fact(
                task=tasks[P2_CLOSURE_TASK_KEY], execution_id="1" * 64
            ),
            mainline_completion_fact(
                task=tasks[STRUCTURAL_COMPILER_TASK_KEY], execution_id="2" * 64
            ),
        ]
    )
    return live


@pytest.fixture
def repaired_bundle() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract, _ = _synthetic_contract_and_inputs()
    source = _source_payload(contract)
    live = _durable_drift_fixture(source)
    live_manifest = _manifest(live)
    migration_contract = copy.deepcopy(contract)
    migration_contract["durable_manifest_digest"] = live_manifest.artifact_digest
    migration_contract["durable_snapshot_digest"] = (
        ResearchOSControlPlane().resolve(live_manifest).snapshot_digest
    )
    repaired, dry_run = builder.build_live_migration(
        live_payload=live,
        source_payload=source,
        source_contract=migration_contract,
    )
    return contract, live, repaired, dry_run


def _validated_authorization(
    contract: dict[str, Any], inputs: dict[str, Any]
) -> dict[str, Any]:
    return validate_result_blind_authorizations(
        source_contract=contract,
        **inputs,
    )


def test_source_contract_is_registered_and_bytes_are_fail_closed(tmp_path: Path) -> None:
    source = load_predictive_route_reconciliation_source_contract(
        ROOT_DIR / PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_CONTRACT_PATH
    )
    audit = route.verify_predictive_route_reconciliation_v1_historical_git_objects(
        root_dir=ROOT_DIR,
        commit_oid=route.PREDICTIVE_ROUTE_RECONCILIATION_V1_HISTORICAL_COMMIT,
        source_paths=SOURCE_PATHS,
    )
    assert audit["status"] == "VERIFIED"
    assert audit["artifact_digest"] == source["artifact_digest"]
    assert audit["source_set_digest"] == source["source_set_digest"]
    with pytest.raises(PredictiveRouteReconciliationError, match="source_modified"):
        verify_predictive_route_reconciliation_source_bytes(
            root_dir=ROOT_DIR,
            contract=source,
        )
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[source["artifact_digest"]] == {
        "artifact_type": route.PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_ARTIFACT_TYPE,
        "path": PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_CONTRACT_PATH.as_posix(),
        "identity_field": "artifact_digest",
    }
    assert source["result_payload_reads"] == 0
    assert source["historical_database_reads"] == 0
    assert source["new_historical_folds"] == 0
    assert source["evidence_created"] is False
    assert source["promotion_gate_opened"] is False

    synthetic, _ = _synthetic_contract_and_inputs()
    for source_path in SOURCE_PATHS:
        target = tmp_path / source_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT_DIR / source_path).read_bytes())
    verify_predictive_route_reconciliation_source_bytes(
        root_dir=tmp_path,
        contract=synthetic,
    )
    target.write_bytes(target.read_bytes() + b"\n# tampered\n")
    with pytest.raises(
        PredictiveRouteReconciliationError,
        match="source_modified",
    ):
        verify_predictive_route_reconciliation_source_bytes(
            root_dir=tmp_path,
            contract=synthetic,
        )


def test_authorization_validation_is_result_blind_and_append_only() -> None:
    contract, inputs = _synthetic_contract_and_inputs()
    before = copy.deepcopy(inputs)
    authorization = _validated_authorization(contract, inputs)
    assert inputs == before
    assert authorization["status"] == "VALIDATED"
    assert authorization["result_payloads_read"] == 0
    assert {
        authorization[label]["reviewer_approval_decision_id"]
        for label in ("route", "policy", "engineering")
    } == {1969, 1970, 1977}

    contaminated = copy.deepcopy(inputs)
    contaminated["route_execution_metadata"]["result_json"] = {
        "historical_fold_scores": [0.1]
    }
    with pytest.raises(
        PredictiveRouteReconciliationError,
        match="execution_metadata_not_sanitized",
    ):
        _validated_authorization(contract, contaminated)

    blinded_payload = copy.deepcopy(inputs)
    blinded_payload["route_research_request"]["payload"]["nested"] = {
        "predictive_p3_result_payload": {"endpoint": 0.1}
    }
    with pytest.raises(
        PredictiveRouteReconciliationError,
        match="blinded_payload_contains_results",
    ):
        _validated_authorization(contract, blinded_payload)

    superseded = copy.deepcopy(inputs)
    later = copy.deepcopy(superseded["route_decisions"][0])
    later["id"] = ROUTE_REVIEWER_APPROVAL_DECISION_ID + 100
    later["new_status"] = "rejected"
    later["decision_code"] = "request_rejected"
    superseded["route_decisions"].append(later)
    with pytest.raises(
        PredictiveRouteReconciliationError,
        match="approval_superseded",
    ):
        _validated_authorization(contract, superseded)


def test_agent_execution_metadata_requires_exactly_one_frozen_execution() -> None:
    request_id = ROUTE_RESEARCH_REQUEST_ID
    execution_id = ROUTE_RESEARCH_EXECUTION_ID

    def execution_row(row_id: int) -> dict[str, Any]:
        return {
            "id": row_id,
            "request_id": request_id,
            "executor_role": "research",
            "executor_id": "research:codex",
            "execution_type": "isolated",
            "status": "completed",
            "environment": "isolated",
            "run_id": f"governance-{row_id}",
            "started_at": "2026-08-11T10:00:00+08:00",
            "completed_at": "2026-08-11T10:00:01+08:00",
            "artifact_paths_json": [],
            "created_at": "2026-08-11T10:00:00+08:00",
        }

    class SyntheticAgentRepository:
        def __init__(self, rows: list[dict[str, Any]]) -> None:
            self.rows = rows

        def list_execution_metadata(self, *, request_id: int):
            assert request_id == ROUTE_RESEARCH_REQUEST_ID
            return copy.deepcopy(self.rows)

    def capability(rows: list[dict[str, Any]]):
        return supervisor_module.M4PredictiveRouteReconciliationCapability(
            repository=object(),
            agent_repository=SyntheticAgentRepository(rows),
        )

    selected = capability([execution_row(execution_id)])._execution_metadata(
        request_id=request_id,
        execution_id=execution_id,
    )
    assert selected == {
        "id": execution_id,
        "request_id": request_id,
        "executor_role": "research",
        "executor_id": "research:codex",
        "execution_type": "isolated",
        "status": "completed",
        "environment": "isolated",
        "run_id": f"governance-{execution_id}",
        "started_at": "2026-08-11T10:00:00+08:00",
        "completed_at": "2026-08-11T10:00:01+08:00",
        "artifact_paths": [],
        "created_at": "2026-08-11T10:00:00+08:00",
    }

    rejected_rows = (
        [],
        [execution_row(execution_id), execution_row(execution_id + 1)],
        [execution_row(execution_id + 1)],
    )
    for rows in rejected_rows:
        with pytest.raises(
            supervisor_module.MainlineSupervisorError,
            match="execution metadata is not exact-one",
        ):
            capability(rows)._execution_metadata(
                request_id=request_id,
                execution_id=execution_id,
            )

    for invalid_paths in ({}, "artifact.json", [1]):
        invalid = execution_row(execution_id)
        invalid["artifact_paths_json"] = invalid_paths
        with pytest.raises(
            supervisor_module.MainlineSupervisorError,
            match="execution artifact paths are invalid",
        ):
            capability([invalid])._execution_metadata(
                request_id=request_id,
                execution_id=execution_id,
            )


def test_exact_three_artifacts_freeze_route_policy_estimands_and_zero_work() -> None:
    contract, inputs = _synthetic_contract_and_inputs()
    authorization = _validated_authorization(contract, inputs)
    before = copy.deepcopy((contract, authorization))
    artifacts = build_predictive_route_reconciliation_artifacts(
        source_contract=contract,
        authorization=authorization,
    )
    assert (contract, authorization) == before
    assert isinstance(artifacts, PredictiveRouteReconciliationArtifacts)
    assert [item["artifact_type"] for item in artifacts.artifacts] == [
        "M4P3PredictiveRouteReconciliationArtifact",
        "P2RToP6DependencyPolicyArtifact",
        "PredictiveP3RouteDecisionArtifact",
    ]
    assert len({item["artifact_digest"] for item in artifacts.artifacts}) == 3
    for item in artifacts.artifacts:
        assert item["result_payload_reads"] == 0
        assert item["computation"] == 0
        assert item["evidence_created"] is False
        assert item["promotion_gate_opened"] is False
        assert item["production_action"] == "none"

    reconciliation, policy, decision = artifacts.artifacts
    assert reconciliation["detected_drift"] is True
    assert reconciliation["drift_proven_by_dependency_mismatch"] is True
    assert reconciliation["structural_p3_terminal_state"] == {
        "task_key": STRUCTURAL_COMPILER_TASK_KEY,
        "decision": STRUCTURAL_P3_TERMINAL_DECISION,
        "terminal": True,
        "fold_count": 90,
        "bootstrap_resamples": 20_000,
        "mainline": "VALIDATED_IN_MAINLINE",
        "replay": "REPLAY_VERIFIED",
    }
    assert policy["policy"] == P2R_TO_P6_POLICY
    assert policy["frozen_before_predictive_p3_result_access"] is True
    assert policy["p3_p4_p5_dependency_effect"] == {
        "p2r_blocks_p3": False,
        "p2r_blocks_p4": False,
        "p2r_blocks_p5": False,
    }
    assert policy["promotion_behavior"]["promotion_gate"] == "FAIL_CLOSED"
    assert policy["promotion_behavior"]["prediction_v2_mode"] == "SHADOW_ONLY"
    assert policy["promotion_behavior"]["prediction_v2_route"] == "BASELINE_ONLY"
    assert decision["decision"] == PREDICTIVE_ROUTE_DECISION
    assert decision["prediction_p3_task_key"] == PREDICTIVE_P3_TASK_KEY
    assert decision["existing_task_identity_preserved"] is True
    assert decision["successor_created"] is False
    assert decision["primary_endpoint"] == PREDICTIVE_P3_PRIMARY_ENDPOINT
    assert (
        decision["equal_budget_100_ticket_comparison_role"]
        == EQUAL_BUDGET_COMPARISON_RELATIONSHIP
    )
    assert decision["scientific_endpoint_changed"] is False

    changed_paths = copy.deepcopy(authorization)
    changed_paths["engineering"]["execution_artifact_paths"] = [
        "docs/experiments/changed-after-completion.json"
    ]
    changed = build_predictive_route_reconciliation_artifacts(
        source_contract=contract,
        authorization=changed_paths,
    )
    assert [item["artifact_digest"] for item in changed.artifacts] != [
        item["artifact_digest"] for item in artifacts.artifacts
    ]


def test_replay_is_deterministic_and_tampering_fails_closed() -> None:
    contract, inputs = _synthetic_contract_and_inputs()
    authorization = _validated_authorization(contract, inputs)
    artifacts = build_predictive_route_reconciliation_artifacts(
        source_contract=contract,
        authorization=authorization,
    )
    replay = replay_predictive_route_reconciliation_artifacts(
        expected=artifacts,
        source_contract=contract,
        authorization=authorization,
    )
    assert replay["status"] == "DETERMINISTIC_REBUILD_VERIFIED"
    assert replay["same_registered_content"] is False
    assert replay["registration_readback_performed"] is False
    assert replay["artifact_digests"] == [
        item["artifact_digest"] for item in artifacts.artifacts
    ]
    assert replay["workload_rerun"] is False
    assert replay["historical_folds_replayed"] == 0
    assert replay["result_payload_reads"] == 0

    registered = replay_predictive_route_reconciliation_artifacts(
        expected=artifacts,
        source_contract=contract,
        authorization=authorization,
        registered_content_verified=True,
    )
    assert registered["status"] == "REGISTERED_REPLAY_VERIFIED"
    assert registered["same_registered_content"] is True
    assert registered["registration_readback_performed"] is True

    tampered_reconciliation = copy.deepcopy(dict(artifacts.reconciliation))
    tampered_reconciliation["detected_drift"] = []
    tampered = PredictiveRouteReconciliationArtifacts(
        reconciliation=tampered_reconciliation,
        p2r_to_p6_policy=artifacts.p2r_to_p6_policy,
        route_decision=artifacts.route_decision,
    )
    with pytest.raises(
        PredictiveRouteReconciliationError,
        match="replay_identity_changed",
    ):
        replay_predictive_route_reconciliation_artifacts(
            expected=tampered,
            source_contract=contract,
            authorization=authorization,
        )


def test_supervisor_registered_replay_verifies_all_registered_content(
    monkeypatch,
) -> None:
    contract, inputs = _synthetic_contract_and_inputs()
    authorization = _validated_authorization(contract, inputs)
    artifacts = build_predictive_route_reconciliation_artifacts(
        source_contract=contract,
        authorization=authorization,
    )
    manifest = _manifest(_source_payload(contract))
    task = next(
        item
        for item in manifest.tasks
        if item.task_key == PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY
    )
    execution_id = "9" * 64
    execution_artifact = {
        "schema_version": supervisor_module.MAINLINE_EXECUTION_SCHEMA,
        "artifact_type": "research_os_mainline_execution",
        "artifact_digest": "8" * 64,
        "git_commit": "a" * 40,
        "parent_digests": [],
    }
    expected_payloads = (*artifacts.artifacts, execution_artifact)

    def registration_payload(
        payload: dict[str, Any], index: int
    ) -> dict[str, Any]:
        record = MainlineArtifactRegistration(
            execution_id=execution_id,
            control_plane_key=supervisor_module.M4_CONTROL_PLANE_KEY,
            task_key=task.task_key,
            task_digest=task.artifact_digest,
            artifact_digest=str(payload["artifact_digest"]),
            artifact_type=str(payload["artifact_type"]),
            schema_version=str(payload.get("schema_version") or "unknown"),
            artifact_path=(
                "runtime/research-os/mainline/tasks/"
                f"{task.task_key}/{execution_id}/artifacts/{index}.json"
            ),
            parent_digests=tuple(
                str(value) for value in payload.get("parent_digests", ())
            ),
            git_commit="a" * 40,
        )
        return {
            "registration_digest": record.registration_digest,
            "execution_id": record.execution_id,
            "control_plane_key": record.control_plane_key,
            "task_key": record.task_key,
            "task_digest": record.task_digest,
            "artifact_digest": record.artifact_digest,
            "artifact_type": record.artifact_type,
            "schema_version": record.schema_version,
            "artifact_path": record.artifact_path,
            "parent_digests": list(record.parent_digests),
            "git_commit": record.git_commit,
        }

    registrations = [
        registration_payload(payload, index)
        for index, payload in enumerate(expected_payloads)
    ]

    class SyntheticRepository:
        def list_mainline_artifacts(
            self, *, control_plane_key: str, execution_id: str
        ) -> list[dict[str, Any]]:
            assert control_plane_key == supervisor_module.M4_CONTROL_PLANE_KEY
            assert execution_id == "9" * 64
            return copy.deepcopy(registrations)

    capability = supervisor_module.M4PredictiveRouteReconciliationCapability(
        repository=SyntheticRepository(),
        agent_repository=object(),
    )
    monkeypatch.setattr(
        supervisor_module,
        "load_predictive_route_reconciliation_source_contract",
        lambda _path: contract,
    )
    monkeypatch.setattr(
        supervisor_module,
        "verify_predictive_route_reconciliation_source_bytes",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        capability,
        "_load_authorization",
        lambda *, source_contract: authorization,
    )
    verified: list[tuple[dict[str, Any], ...]] = []

    def verify_registered_artifacts(
        *, root_dir: Path, registrations, expected_payloads
    ) -> None:
        assert root_dir == ROOT_DIR
        assert len(registrations) == 4
        verified.append(tuple(expected_payloads))

    monkeypatch.setattr(
        supervisor_module,
        "_verify_v2_registered_artifacts",
        verify_registered_artifacts,
    )
    replay = capability.verify_registered_replay(
        control_plane_key=supervisor_module.M4_CONTROL_PLANE_KEY,
        task=task,
        execution_id=execution_id,
        execution_artifact=execution_artifact,
    )
    assert verified == [expected_payloads]
    assert replay["status"] == "REGISTERED_REPLAY_VERIFIED"
    assert replay["same_registered_content"] is True
    assert replay["registration_readback_performed"] is True
    assert replay["result_payload_reads"] == 0
    assert replay["historical_folds_replayed"] == 0

    tampered_record = MainlineArtifactRegistration(
        execution_id=execution_id,
        control_plane_key=supervisor_module.M4_CONTROL_PLANE_KEY,
        task_key=task.task_key,
        task_digest="0" * 64,
        artifact_digest=str(expected_payloads[0]["artifact_digest"]),
        artifact_type=str(expected_payloads[0]["artifact_type"]),
        schema_version=str(expected_payloads[0].get("schema_version") or "unknown"),
        artifact_path=str(registrations[0]["artifact_path"]),
        parent_digests=tuple(expected_payloads[0].get("parent_digests", ())),
        git_commit="a" * 40,
    )
    registrations[0]["task_digest"] = tampered_record.task_digest
    registrations[0]["registration_digest"] = tampered_record.registration_digest
    with pytest.raises(
        supervisor_module.MainlineSupervisorError,
        match="registered identity changed",
    ):
        capability.verify_registered_replay(
            control_plane_key=supervisor_module.M4_CONTROL_PLANE_KEY,
            task=task,
            execution_id=execution_id,
            execution_artifact=execution_artifact,
        )
    assert verified == [expected_payloads]

    escaped_record = MainlineArtifactRegistration(
        execution_id=execution_id,
        control_plane_key=supervisor_module.M4_CONTROL_PLANE_KEY,
        task_key=task.task_key,
        task_digest=task.artifact_digest,
        artifact_digest=str(expected_payloads[0]["artifact_digest"]),
        artifact_type=str(expected_payloads[0]["artifact_type"]),
        schema_version=str(expected_payloads[0].get("schema_version") or "unknown"),
        artifact_path=(
            "runtime/research-os/mainline/tasks/"
            f"{task.task_key}/{execution_id}/artifacts/../escaped.json"
        ),
        parent_digests=tuple(expected_payloads[0].get("parent_digests", ())),
        git_commit="a" * 40,
    )
    registrations[0] = {
        "registration_digest": escaped_record.registration_digest,
        "execution_id": escaped_record.execution_id,
        "control_plane_key": escaped_record.control_plane_key,
        "task_key": escaped_record.task_key,
        "task_digest": escaped_record.task_digest,
        "artifact_digest": escaped_record.artifact_digest,
        "artifact_type": escaped_record.artifact_type,
        "schema_version": escaped_record.schema_version,
        "artifact_path": escaped_record.artifact_path,
        "parent_digests": list(escaped_record.parent_digests),
        "git_commit": escaped_record.git_commit,
    }
    with pytest.raises(
        supervisor_module.MainlineSupervisorError,
        match="artifact path is not canonical",
    ):
        capability.verify_registered_replay(
            control_plane_key=supervisor_module.M4_CONTROL_PLANE_KEY,
            task=task,
            execution_id=execution_id,
            execution_artifact=execution_artifact,
        )
    assert verified == [expected_payloads]


def test_route_replay_is_allowlisted_and_selects_strong_completed_loader(
    monkeypatch,
) -> None:
    assert PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY in (
        supervisor_module._EXECUTION_COMMIT_REPLAY_TASK_KEYS
    )
    selected: dict[str, Any] = {}

    class StrongLoaderSelected(RuntimeError):
        pass

    def strong_loader(**kwargs):
        selected.update(kwargs)
        raise StrongLoaderSelected

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        strong_loader,
    )
    supervisor = supervisor_module.ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    with pytest.raises(StrongLoaderSelected):
        supervisor.replay(task_key=PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY)
    assert selected == {
        "repository": supervisor.repository,
        "root_dir": ROOT_DIR,
        "control_plane_key": supervisor_module.M4_CONTROL_PLANE_KEY,
        "task_key": PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY,
    }


def test_static_durable_drift_and_estimand_conflict_are_detectable() -> None:
    contract, inputs = _synthetic_contract_and_inputs()
    assert contract["static_manifest_digest"] != contract["durable_manifest_digest"]
    drift = contract["drift_detail"]
    assert drift["static"] == [
        GLOBAL_ROUTING_TASK_KEY,
        ADAPTIVE_RESEARCH_ELIGIBILITY_FACT,
    ]
    assert drift["durable"] == [P2_CLOSURE_TASK_KEY, P2_PASS_TO_P3_FACT]

    no_drift = copy.deepcopy(contract)
    no_drift["detected_drift"] = False
    no_drift = _recompute_contract(no_drift)
    with pytest.raises(PredictiveRouteReconciliationError, match="drift_not_proven"):
        _validated_authorization(no_drift, inputs)

    merged_estimands = copy.deepcopy(contract)
    merged_estimands["estimand_relationship"]["contracts_merged"] = True
    merged_estimands["estimand_relationship"][
        "equal_budget_100_ticket_comparison_role"
    ] = "SAME_PRIMARY_ENDPOINT"
    merged_estimands = _recompute_contract(merged_estimands)
    with pytest.raises(PredictiveRouteReconciliationError, match="estimand_conflict"):
        _validated_authorization(merged_estimands, inputs)

    canonicalized_durable_dependencies = copy.deepcopy(contract)
    canonicalized_durable_dependencies["actual_dependencies"] = [
        {
            "dependency_type": "task",
            "target_key": GLOBAL_ROUTING_TASK_KEY,
            "required_status": "completed",
        },
        {
            "dependency_type": "artifact",
            "target_key": ADAPTIVE_RESEARCH_ELIGIBILITY_FACT,
            "required_status": "available",
        },
    ]
    canonicalized_durable_dependencies = _recompute_contract(
        canonicalized_durable_dependencies
    )
    with pytest.raises(
        PredictiveRouteReconciliationError,
        match="actual_dependencies_changed",
    ):
        _validated_authorization(canonicalized_durable_dependencies, inputs)


@pytest.mark.parametrize(
    ("frozen_field", "expected_error"),
    (
        ("durable_manifest_digest", "source_invalid"),
        ("durable_snapshot_digest", "source_invalid"),
        ("actual_dependencies", "actual_dependencies_changed"),
    ),
)
def test_frozen_live_identity_and_legacy_dependencies_reject_changes(
    frozen_field: str,
    expected_error: str,
) -> None:
    contract, inputs = _synthetic_contract_and_inputs()
    assert contract["durable_manifest_digest"] == (
        route.PREDICTIVE_ROUTE_RECONCILIATION_DURABLE_MANIFEST_DIGEST
    )
    assert contract["durable_snapshot_digest"] == (
        route.PREDICTIVE_ROUTE_RECONCILIATION_DURABLE_SNAPSHOT_DIGEST
    )
    assert contract["actual_dependencies"] == [
        {
            "dependency_type": "task",
            "target_key": P2_CLOSURE_TASK_KEY,
            "required_status": "completed",
        },
        {
            "dependency_type": "artifact",
            "target_key": P2_PASS_TO_P3_FACT,
            "required_status": "available",
        },
    ]

    changed = copy.deepcopy(contract)
    if frozen_field == "actual_dependencies":
        changed[frozen_field] = copy.deepcopy(contract["source_dependencies"])
    else:
        frozen_digest = str(changed[frozen_field])
        replacement = "0" if frozen_digest[0] != "0" else "1"
        changed[frozen_field] = replacement + frozen_digest[1:]
    changed = _recompute_contract(changed)

    with pytest.raises(PredictiveRouteReconciliationError, match=expected_error):
        _validated_authorization(changed, inputs)


def test_source_builder_preserves_p2_p2r_and_structural_p3_and_separates_routes() -> None:
    contract, _ = _synthetic_contract_and_inputs()
    base = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source = builder.build_source_payload(base, source_contract=contract)
    base_tasks = {item["task_key"]: item for item in base["tasks"]}
    source_tasks = {item["task_key"]: item for item in source["tasks"]}

    for task_key in (
        P2_CLOSURE_TASK_KEY,
        P2R_TASK_KEY,
        STRUCTURAL_COMPILER_TASK_KEY,
        P5_TASK_KEY,
    ):
        assert source_tasks[task_key] == base_tasks[task_key]
    assert source_tasks[P2_CLOSURE_TASK_KEY]["metric_contract"]["terminal_status"] == (
        "COMPLETE_WITH_REPAIR_OUTCOME"
    )
    assert source_tasks[P2_CLOSURE_TASK_KEY]["metric_contract"]["decision"] == (
        "REPAIR_MEASUREMENT_SYSTEM"
    )
    assert source_tasks[P2R_TASK_KEY]["metric_contract"]["status"] == (
        "PENDING_VALIDATION"
    )
    assert source_tasks[P2R_TASK_KEY]["metric_contract"][
        "validation_execution_authorized"
    ] is False
    structural_metric = source_tasks[STRUCTURAL_COMPILER_TASK_KEY]["metric_contract"]
    assert structural_metric["fold_count"] == 90
    assert structural_metric["bootstrap_resamples"] == 20_000
    assert structural_metric["predictive_p3_authorized"] is False

    # Static source records the immutable P2 outcome in the task contract.  The
    # durable decision fact is preserved from live truth and is not synthesized.
    assert P2_REPAIR_DECISION_FACT not in source["facts"]["artifacts"]
    assert P2_PASS_TO_P3_FACT not in source["facts"]["artifacts"]
    assert ADAPTIVE_RESEARCH_ELIGIBILITY_FACT not in source["facts"]["artifacts"]
    assert PREDICTIVE_P3_PASS_TO_P4_FACT not in source["facts"]["artifacts"]
    assert P2R_TO_P6_POLICY_FACT not in source["facts"]["artifacts"]

    predictive_p3 = source_tasks[PREDICTIVE_P3_TASK_KEY]
    assert predictive_p3["dependencies"] == [
        {
            "dependency_type": "task",
            "target_key": GLOBAL_ROUTING_TASK_KEY,
            "required_status": "completed",
        },
        {
            "dependency_type": "artifact",
            "target_key": ADAPTIVE_RESEARCH_ELIGIBILITY_FACT,
            "required_status": "available",
        },
    ]
    assert predictive_p3["metric_contract"]["primary_endpoint"] == (
        PREDICTIVE_P3_PRIMARY_ENDPOINT
    )
    assert predictive_p3["metric_contract"][
        "ticket_budget_comparison_relationship"
    ] == EQUAL_BUDGET_COMPARISON_RELATIONSHIP
    assert predictive_p3["metric_contract"]["promotion_allowed"] is False
    assert source_tasks[P4_TASK_KEY]["dependencies"][-1]["target_key"] == (
        PREDICTIVE_P3_PASS_TO_P4_FACT
    )
    assert source_tasks[P6_TASK_KEY]["dependencies"][-1]["target_key"] == (
        P2R_TO_P6_POLICY_FACT
    )
    for task_key in (PREDICTIVE_P3_TASK_KEY, P4_TASK_KEY, P5_TASK_KEY, P6_TASK_KEY):
        assert all(
            dependency["target_key"] != P2R_TASK_KEY
            for dependency in source_tasks[task_key]["dependencies"]
        )
    assert sum(key == PREDICTIVE_P3_TASK_KEY for key in source_tasks) == 1
    assert all("repair-outcome-strict-historical" not in key for key in source_tasks)


def test_live_migration_is_additive_and_preserves_all_existing_state_and_facts(
    repaired_bundle,
) -> None:
    _, live, repaired, dry_run = repaired_bundle
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_goal_keys"] == []
    assert dry_run["new_task_keys"] == [PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY]
    assert dry_run["revised_task_keys"] == sorted(
        (PREDICTIVE_P3_TASK_KEY, P4_TASK_KEY, P6_TASK_KEY)
    )
    for key in (
        "existing_goal_deletions",
        "existing_task_deletions",
        "existing_state_regressions",
        "existing_fact_deletions",
        "unallowlisted_definition_rewrites",
    ):
        assert dry_run[key] == 0
    assert dry_run["import_performed"] is False
    assert dry_run["production_action"] == "none"
    assert dry_run["promotion_gate_opened"] is False

    live_tasks = {item["task_key"]: item for item in live["tasks"]}
    repaired_tasks = {item["task_key"]: item for item in repaired["tasks"]}
    assert set(live_tasks).issubset(repaired_tasks)
    assert len(repaired_tasks) == len(live_tasks) + 1
    for task_key, task in live_tasks.items():
        assert repaired_tasks[task_key].get("status") == task.get("status")
        assert repaired_tasks[task_key].get("completion_classification") == task.get(
            "completion_classification"
        )
    for fact_type, values in live["facts"].items():
        assert set(values).issubset(repaired["facts"][fact_type])
    assert _task(repaired, P2_CLOSURE_TASK_KEY)["status"] == "completed"
    assert _task(repaired, STRUCTURAL_COMPILER_TASK_KEY)["status"] == "completed"
    assert _task(repaired, P2R_TASK_KEY).get("status", "draft") == "draft"


def test_repaired_manifest_keeps_structural_terminal_and_predictive_p3_waiting(
    repaired_bundle,
) -> None:
    contract, _, repaired, _ = repaired_bundle
    verification = validate_repaired_manifest(repaired, source_contract=contract)
    assert verification == {
        "status": "VERIFIED",
        "governance_completed": False,
        "durable_manifest_digest": contract["durable_manifest_digest"],
        "durable_snapshot_digest": contract["durable_snapshot_digest"],
        "prediction_p3_task_key": PREDICTIVE_P3_TASK_KEY,
        "prediction_p3_status": "dependency_wait",
        "global_routing_status": "dependency_wait",
        "missing_global_routing_facts": list(GLOBAL_ROUTING_BRANCH_REPLAY_FACTS),
        "adaptive_research_eligible_fact_available": False,
        "p4_pass_fact_available": False,
        "p2r_status": "PENDING_VALIDATION",
        "p2r_execution_authorized": False,
        "structural_p3_decision": STRUCTURAL_P3_TERMINAL_DECISION,
        "promotion_gate": "FAIL_CLOSED",
        "result_payload_reads": 0,
        "computation": 0,
        "evidence_created": False,
        "production_action": "none",
    }
    snapshot = ResearchOSControlPlane().resolve(_manifest(repaired))
    resolutions = {item.task_key: item for item in snapshot.resolutions}
    assert resolutions[STRUCTURAL_COMPILER_TASK_KEY].status is TaskStatus.COMPLETED
    assert resolutions[PREDICTIVE_P3_TASK_KEY].status is TaskStatus.DEPENDENCY_WAIT
    assert resolutions[GLOBAL_ROUTING_TASK_KEY].status is TaskStatus.DEPENDENCY_WAIT
    assert resolutions[P2R_TASK_KEY].status is TaskStatus.EXTERNAL_WAIT
    assert resolutions[PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY].status is (
        TaskStatus.READY
    )
    ready_keys = {item.task_key for item in snapshot.ready_queue}
    assert PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY in ready_keys
    assert PREDICTIVE_P3_TASK_KEY not in ready_keys
    assert STRUCTURAL_COMPILER_TASK_KEY not in ready_keys


def test_repair_or_adaptive_alone_cannot_bypass_global_routing(
    repaired_bundle,
) -> None:
    _, _, repaired, _ = repaired_bundle
    assert P2_REPAIR_DECISION_FACT in repaired["facts"]["artifacts"]
    assert ADAPTIVE_RESEARCH_ELIGIBILITY_FACT not in repaired["facts"]["artifacts"]
    assert _resolution(repaired, PREDICTIVE_P3_TASK_KEY).status is (
        TaskStatus.DEPENDENCY_WAIT
    )

    global_only = copy.deepcopy(repaired)
    global_task = next(
        task
        for task in _manifest(global_only).tasks
        if task.task_key == GLOBAL_ROUTING_TASK_KEY
    )
    _task(global_only, GLOBAL_ROUTING_TASK_KEY)["status"] = "completed"
    _task(global_only, GLOBAL_ROUTING_TASK_KEY)["completion_classification"] = (
        "COMPLETE"
    )
    global_only["facts"]["artifacts"].append(
        mainline_completion_fact(task=global_task, execution_id="f" * 64)
    )
    assert _resolution(global_only, PREDICTIVE_P3_TASK_KEY).status is (
        TaskStatus.DEPENDENCY_WAIT
    )

    adaptive_only = copy.deepcopy(repaired)
    adaptive_only["facts"]["artifacts"].append(ADAPTIVE_RESEARCH_ELIGIBILITY_FACT)
    assert _resolution(adaptive_only, PREDICTIVE_P3_TASK_KEY).status is (
        TaskStatus.DEPENDENCY_WAIT
    )

    canonical_both = copy.deepcopy(global_only)
    canonical_both["facts"]["artifacts"].append(
        ADAPTIVE_RESEARCH_ELIGIBILITY_FACT
    )
    assert _resolution(canonical_both, PREDICTIVE_P3_TASK_KEY).status is (
        TaskStatus.READY
    )


def test_predictive_p3_completion_and_explicit_pass_are_both_required_for_p4(
    repaired_bundle,
) -> None:
    _, _, repaired, _ = repaired_bundle
    completed_only = copy.deepcopy(repaired)
    _task(completed_only, PREDICTIVE_P3_TASK_KEY)["status"] = "completed"
    assert _resolution(completed_only, P4_TASK_KEY).status is TaskStatus.DEPENDENCY_WAIT

    pass_only = copy.deepcopy(repaired)
    pass_only["facts"]["artifacts"].append(PREDICTIVE_P3_PASS_TO_P4_FACT)
    assert _resolution(pass_only, P4_TASK_KEY).status is TaskStatus.DEPENDENCY_WAIT

    completed_and_pass = copy.deepcopy(completed_only)
    completed_and_pass["facts"]["artifacts"].append(
        PREDICTIVE_P3_PASS_TO_P4_FACT
    )
    assert _resolution(completed_and_pass, P4_TASK_KEY).status is TaskStatus.READY
    assert _resolution(completed_and_pass, P6_TASK_KEY).status is (
        TaskStatus.DEPENDENCY_WAIT
    )
    assert _task(completed_and_pass, P4_TASK_KEY)["metric_contract"][
        "promotion_allowed"
    ] is False


def test_p6_uses_frozen_policy_fact_without_hard_p2r_task_dependency(
    repaired_bundle,
) -> None:
    _, _, repaired, _ = repaired_bundle
    downstream_complete = copy.deepcopy(repaired)
    for task_key in (PREDICTIVE_P3_TASK_KEY, P4_TASK_KEY, P5_TASK_KEY):
        _task(downstream_complete, task_key)["status"] = "completed"
    p6 = _task(downstream_complete, P6_TASK_KEY)
    assert all(item["target_key"] != P2R_TASK_KEY for item in p6["dependencies"])
    assert p6["dependencies"][-1] == {
        "dependency_type": "artifact",
        "target_key": P2R_TO_P6_POLICY_FACT,
        "required_status": "available",
    }
    assert _resolution(downstream_complete, P6_TASK_KEY).status is (
        TaskStatus.DEPENDENCY_WAIT
    )

    wrong_policy = copy.deepcopy(downstream_complete)
    wrong_policy["facts"]["artifacts"].append(
        "m4-p2r-to-p6-dependency-policy:HARD_DEPENDENCY"
    )
    assert _resolution(wrong_policy, P6_TASK_KEY).status is TaskStatus.DEPENDENCY_WAIT

    frozen_policy = copy.deepcopy(downstream_complete)
    frozen_policy["facts"]["artifacts"].append(P2R_TO_P6_POLICY_FACT)
    assert _resolution(frozen_policy, P6_TASK_KEY).status is TaskStatus.READY
    assert _resolution(frozen_policy, P2R_TASK_KEY).status is TaskStatus.EXTERNAL_WAIT
    metric = p6["metric_contract"]
    assert metric["p2r_to_p6_policy"] == P2R_TO_P6_POLICY
    assert metric["p2r_blocks_research_summary"] is False
    assert metric["p2r_blocks_promotion"] is True
    assert metric["promotion_gate_default"] == "FAIL_CLOSED"
    assert metric["promotion_allowed_in_this_capability"] is False
    assert metric["prediction_v2_mode_while_p2r_pending"] == "SHADOW_ONLY"
    assert metric["prediction_v2_route_while_p2r_pending"] == "BASELINE_ONLY"


def test_unauthorized_successor_is_absent_and_rejected(repaired_bundle) -> None:
    contract, _, repaired, _ = repaired_bundle
    keys = [item["task_key"] for item in repaired["tasks"]]
    assert keys.count(PREDICTIVE_P3_TASK_KEY) == 1
    assert all("repair-outcome-strict-historical" not in key for key in keys)

    contaminated = copy.deepcopy(repaired)
    successor = copy.deepcopy(_task(contaminated, PREDICTIVE_P3_TASK_KEY))
    successor["task_key"] = "m4-p3-repair-outcome-strict-historical-walk-forward"
    contaminated["tasks"].append(successor)
    with pytest.raises(
        PredictiveRouteReconciliationError,
        match="unauthorized_successor_present",
    ):
        validate_repaired_manifest(contaminated, source_contract=contract)


def _called_leaf(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def test_domain_builder_and_capability_have_no_blinded_work_operations() -> None:
    capability = supervisor_module.M4PredictiveRouteReconciliationCapability
    sources = {
        "domain": inspect.getsource(route),
        "builder": inspect.getsource(builder),
        "capability": inspect.getsource(capability),
    }
    forbidden_calls = {
        "load_history",
        "load_history_until_with_dates",
        "load_outcomes",
        "run_fold",
        "run_walk_forward",
        "bootstrap",
        "resample",
        "generate_candidate",
        "generate_candidates",
        "add_evidence",
        "promote",
    }
    forbidden_result_fields = {
        "result",
        "result_json",
        "execution_result",
        "prediction_results",
        "predictive_p3_result_payload",
        "historical_fold_scores",
    }
    for label, source in sources.items():
        tree = ast.parse(source)
        called = {
            leaf
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            if (leaf := _called_leaf(node)) is not None
        }
        assert called.isdisjoint(forbidden_calls), (label, called & forbidden_calls)
        accessed_attributes = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        assert accessed_attributes.isdisjoint(forbidden_result_fields), (
            label,
            accessed_attributes & forbidden_result_fields,
        )
        result_key_reads = {
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and node.args[0].value in forbidden_result_fields
        }
        assert result_key_reads == set(), (label, result_key_reads)


def test_supervisor_registration_and_unified_status_projection(repaired_bundle) -> None:
    contract, _, repaired, _ = repaired_bundle
    supervisor = supervisor_module.ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert PREDICTIVE_ROUTE_RECONCILIATION_CAPABILITY in supervisor.capabilities
    assert supervisor.capabilities[
        PREDICTIVE_ROUTE_RECONCILIATION_CAPABILITY
    ].__class__.__name__ == "M4PredictiveRouteReconciliationCapability"

    authorization = _validated_authorization(
        contract,
        _synthetic_contract_and_inputs()[1],
    )
    artifacts = build_predictive_route_reconciliation_artifacts(
        source_contract=contract,
        authorization=authorization,
    )
    manifest = _manifest(repaired)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    pending_status = build_m4_status(
        manifest,
        snapshot=snapshot,
        predictive_route_reconciliation_summary={"status": "COMPLETE"},
    )
    pending = pending_status["predictive_route_reconciliation"]
    assert pending["status"] == "INTEGRATION_PENDING"
    assert pending["registered_execution_summary_valid"] is False
    assert pending["predictive_result_reads"] is None
    assert pending["mainline_integration"] == "NO — INTEGRATION_PENDING"

    completed_payload = copy.deepcopy(repaired)
    route_task_payload = _task(
        completed_payload, PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY
    )
    route_task_payload["status"] = "completed"
    route_task_payload["completion_classification"] = "COMPLETE"
    completed_payload["facts"]["artifacts"].extend(
        [
            route.PREDICTIVE_ROUTE_RECONCILIATION_COMPLETION_FACT,
            PREDICTIVE_ROUTE_DECISION_FACT,
            P2R_TO_P6_POLICY_FACT,
        ]
    )
    completed_manifest_without_execution_fact = _manifest(completed_payload)
    completed_task = next(
        item
        for item in completed_manifest_without_execution_fact.tasks
        if item.task_key == PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY
    )
    completed_payload["facts"]["artifacts"].append(
        mainline_completion_fact(task=completed_task, execution_id="f" * 64)
    )
    completed_manifest = _manifest(completed_payload)
    summary = {
        "artifact_type": "research_os_mainline_execution",
        "artifact_digest": "f" * 64,
        "execution_artifact_digest": "f" * 64,
        "execution_task_key": PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY,
        "task_key": PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY,
        "task_digest": completed_task.artifact_digest,
        "capability": PREDICTIVE_ROUTE_RECONCILIATION_CAPABILITY,
        "status": "COMPLETE",
        "completion_classification": "VALIDATED_IN_MAINLINE",
        "predictive_route_reconciliation_source_contract_digest": (
            completed_task.input_artifact_digests[0]
        ),
        "audited_durable_manifest_digest": (
            route.PREDICTIVE_ROUTE_RECONCILIATION_DURABLE_MANIFEST_DIGEST
        ),
        "audited_durable_snapshot_digest": (
            route.PREDICTIVE_ROUTE_RECONCILIATION_DURABLE_SNAPSHOT_DIGEST
        ),
        "predictive_p3_route_decision": PREDICTIVE_ROUTE_DECISION,
        "p2r_to_p6_policy": P2R_TO_P6_POLICY,
        "completion_facts": [
            route.PREDICTIVE_ROUTE_RECONCILIATION_COMPLETION_FACT,
            PREDICTIVE_ROUTE_DECISION_FACT,
            P2R_TO_P6_POLICY_FACT,
        ],
        "registered_artifact_count": 4,
        "actual_fold_count": 0,
        "predictive_result_reads": 0,
        "historical_database_reads": 0,
        "computation": 0,
        "new_historical_folds": 0,
        "evidence_created": False,
        "promotion_gate_opened": False,
        "promotion_allowed": False,
        "production_action": "none",
        "replay_status": "REGISTERED_REPLAY_VERIFIED",
        "m4_p3_predictive_route_reconciliation_digest": artifacts.reconciliation[
            "artifact_digest"
        ],
        "p2r_to_p6_dependency_policy_digest": artifacts.p2r_to_p6_policy[
            "artifact_digest"
        ],
        "predictive_p3_route_decision_digest": artifacts.route_decision[
            "artifact_digest"
        ],
    }
    status = build_m4_status(
        completed_manifest,
        snapshot=ResearchOSControlPlane().resolve(completed_manifest),
        predictive_route_reconciliation_summary=summary,
    )
    projection = status["predictive_route_reconciliation"]
    assert projection["status"] == "COMPLETE"
    assert projection["registered_execution_summary_valid"] is True
    assert projection["route_decision"] == PREDICTIVE_ROUTE_DECISION
    assert projection["p2r_to_p6_policy"] == P2R_TO_P6_POLICY
    assert projection["predictive_result_reads"] == 0
    assert projection["computation"] == 0
    assert projection["evidence_created"] is False
    assert projection["promotion_gate_opened"] is False
    for key in (
        "m4_p3_predictive_route_reconciliation_digest",
        "p2r_to_p6_dependency_policy_digest",
        "predictive_p3_route_decision_digest",
    ):
        assert projection[key] == summary[key]
    assert (
        projection["mainline_integration"]
        == "YES — validated by unified mainline execution and replay"
    )

    for drifted_task_key in (PREDICTIVE_P3_TASK_KEY, P4_TASK_KEY, P6_TASK_KEY):
        drifted_payload = copy.deepcopy(completed_payload)
        drifted_task = _task(drifted_payload, drifted_task_key)
        if drifted_task_key == P6_TASK_KEY:
            policy_dependency = next(
                item
                for item in drifted_task["dependencies"]
                if item["target_key"] == P2R_TO_P6_POLICY_FACT
            )
            policy_dependency["required_status"] = "completed"
        else:
            drifted_task["dependencies"][0]["required_status"] = "available"
        drifted_manifest = _manifest(drifted_payload)
        drifted_projection = build_m4_status(
            drifted_manifest,
            snapshot=ResearchOSControlPlane().resolve(drifted_manifest),
            predictive_route_reconciliation_summary=summary,
        )["predictive_route_reconciliation"]
        assert drifted_projection["resolver_status"] == "completed"
        assert drifted_projection["completion_fact_registered"] is True
        assert drifted_projection["route_decision_fact_registered"] is True
        assert drifted_projection["policy_fact_registered"] is True
        assert drifted_projection["status"] == "INTEGRATION_PENDING"
        assert drifted_projection["structural_manifest_valid"] is False
        assert drifted_projection["structural_validation_error"] is not None
        assert drifted_projection["registered_execution_summary_valid"] is False
        assert drifted_projection["route_decision"] is None
        assert drifted_projection["p2r_to_p6_policy"] is None
        assert drifted_projection["detected_drift"] is None
        assert drifted_projection["predictive_p3"]["canonical_dependencies"] is None
        assert drifted_projection["downstream_policy"]["p2r_blocks_p3"] is None
        assert drifted_projection[
            "m4_p3_predictive_route_reconciliation_digest"
        ] is None
        assert drifted_projection["p2r_to_p6_dependency_policy_digest"] is None
        assert drifted_projection["predictive_p3_route_decision_digest"] is None
        assert drifted_projection["replay_status"] is None
        assert drifted_projection["next_legal_task"] == (
            "dependency_wait:predictive route structural wiring invalid"
        )
        assert drifted_projection["mainline_integration"] == (
            "NO — INTEGRATION_PENDING"
        )

    tampered_summary = copy.deepcopy(summary)
    tampered_summary["predictive_result_reads"] = 1
    tampered_status = build_m4_status(
        completed_manifest,
        snapshot=ResearchOSControlPlane().resolve(completed_manifest),
        predictive_route_reconciliation_summary=tampered_summary,
    )["predictive_route_reconciliation"]
    assert tampered_status["status"] == "INTEGRATION_PENDING"
    assert tampered_status["registered_execution_summary_valid"] is False
    assert tampered_status["predictive_result_reads"] is None
