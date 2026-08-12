from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY = (
    "m4-p3-predictive-route-reconciliation"
)
PREDICTIVE_ROUTE_RECONCILIATION_CAPABILITY = (
    "m4_p3_predictive_route_reconciliation"
)
PREDICTIVE_ROUTE_RECONCILIATION_COMPLETION_FACT = (
    "m4-p3-predictive-route-reconciliation:COMPLETE"
)
PREDICTIVE_ROUTE_DECISION_FACT = (
    "m4-p3-predictive-route-decision:DAG_REPAIR_REQUIRED"
)
P2R_TO_P6_POLICY_FACT = (
    "m4-p2r-to-p6-dependency-policy:RESEARCH_ALLOWED_PROMOTION_BLOCKED"
)
PREDICTIVE_P3_PASS_TO_P4_FACT = "m4-p3-predictive-decision:PASS_TO_P4"
P2R_PROMOTION_ACCEPTANCE_FACT = (
    "m4-p2r-measurement-repair-validation:ALL_FROZEN_ACCEPTANCE_PASS"
)

PREDICTIVE_P3_TASK_KEY = "m4-p3-strict-historical-walk-forward"
GLOBAL_ROUTING_TASK_KEY = "m4-v2-global-routing"
P4_TASK_KEY = "m4-p4-negative-controls-and-robustness"
P5_TASK_KEY = "m4-p5-forward-evidence"
P6_TASK_KEY = "m4-p6-information-bound-and-decision"
P2_CLOSURE_TASK_KEY = "m4-p2-synthetic-measurement-validation"
P2R_TASK_KEY = "m4-p2r-measurement-repair-validation"
STRUCTURAL_P3_EVIDENCE_COMPILER_TASK_KEY = (
    "m4-p3-result-blind-structural-utility-evidence-compiler"
)

P2_CLOSURE_COMPLETION_FACT = "m4-p2-closure:COMPLETE_WITH_REPAIR_OUTCOME"
P2_REPAIR_DECISION_FACT = (
    "m4-p2-measurement-decision:REPAIR_MEASUREMENT_SYSTEM"
)
P2_PASS_TO_P3_FACT = "m4-p2-measurement-decision:PASS_TO_P3"
P2R_EXECUTION_APPROVED_EVENT = (
    "research-contract:m4-p2r-measurement-repair-validation-execution:approved"
)
STRUCTURAL_P3_COMPLETION_FACT = (
    "m4-p3-result-blind-structural-utility-evidence-compiler:COMPLETE"
)
ADAPTIVE_RESEARCH_ELIGIBILITY_FACT = (
    "m4-v2-routing:ADAPTIVE_RESEARCH_ELIGIBLE"
)
GLOBAL_ROUTING_BRANCH_REPLAY_FACTS = (
    "m4-v2-branch-decision-replay:MARGINAL_HISTORICAL:VERIFIED",
    "m4-v2-branch-decision-replay:TEMPORAL_MARGINAL_INCREMENT:VERIFIED",
    "m4-v2-branch-decision-replay:JOINT_RESIDUAL_INCREMENT:VERIFIED",
)

ROUTE_RESEARCH_REQUEST_KEY = "research-m4-p3-predictive-route-reconciliation"
ROUTE_RESEARCH_REQUEST_ID = 472
ROUTE_RESEARCH_EXECUTION_ID = 393
ROUTE_REVIEWER_APPROVAL_DECISION_ID = 1969
ROUTE_RESEARCH_APPROVED_EVENT = (
    "research-contract:m4-p3-predictive-route-reconciliation:approved"
)

POLICY_RESEARCH_REQUEST_KEY = "research-m4-p2r-to-p6-dependency-policy"
POLICY_RESEARCH_REQUEST_ID = 473
POLICY_RESEARCH_EXECUTION_ID = 394
POLICY_REVIEWER_APPROVAL_DECISION_ID = 1970
POLICY_RESEARCH_APPROVED_EVENT = (
    "research-contract:m4-p2r-to-p6-dependency-policy:approved"
)

ENGINEERING_REQUEST_ID = 474
ENGINEERING_EXECUTION_ID = 395
ENGINEERING_REVIEWER_APPROVAL_DECISION_ID = 1977
ENGINEERING_APPROVED_EVENT = (
    "engineering-contract:m4-p3-predictive-route-reconciliation:approved"
)

PREDICTIVE_ROUTE_DECISION = "DAG_REPAIR_REQUIRED"
P2R_TO_P6_POLICY = "RESEARCH_ALLOWED_PROMOTION_BLOCKED"
PREDICTIVE_P3_PRIMARY_ENDPOINT = "out_of_sample_log_loss_improvement"
EQUAL_BUDGET_COMPARISON_RELATIONSHIP = (
    "SEPARATE_FUTURE_SECONDARY_OR_DOWNSTREAM_CONTRACT"
)
STRUCTURAL_P3_TERMINAL_DECISION = "NO_STABLE_STRUCTURAL_UTILITY"

PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/"
    "m4-p3-predictive-route-reconciliation-source-v1.json"
)
PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_SCHEMA = (
    "dehps-m4-p3-predictive-route-reconciliation-source.v1"
)
PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_ARTIFACT_TYPE = (
    "m4_p3_predictive_route_reconciliation_source"
)
PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_CONTRACT_KEY = (
    "M4_P3_PREDICTIVE_ROUTE_RECONCILIATION_SOURCE"
)
PREDICTIVE_ROUTE_RECONCILIATION_V1_HISTORICAL_COMMIT = (
    "15760f143ad92d7dd6df34a89924af950669a513"
)
PREDICTIVE_ROUTE_RECONCILIATION_V1_CONFIG_SHA256 = (
    "ec4ec69c912229d56728f7ec12480420fb2010964798fa8a91c35f8f4bf8cfed"
)
PREDICTIVE_ROUTE_RECONCILIATION_INSPECTED_MAIN_SHA = (
    "f58f46829f0dede149bc5f116e0fd660768d3a82"
)
PREDICTIVE_ROUTE_RECONCILIATION_STATIC_MANIFEST_DIGEST = (
    "f3f263d3ef9c5028223070b7fc228c2ef95ffc315a86479d17ebccb0a87b890b"
)
PREDICTIVE_ROUTE_RECONCILIATION_DURABLE_MANIFEST_DIGEST = (
    "0194d06a18cfbf51394af87aaf03149a440fc1f39f608e0acbe8fd0df75ca763"
)
PREDICTIVE_ROUTE_RECONCILIATION_DURABLE_SNAPSHOT_DIGEST = (
    "e7466e5b8752630c21c808b8dc2e7b27d197fd9a80d023ca001762b83b9be591"
)

_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "predictive_route_reconciliation.py"
)
_SOURCE_PATHS = (
    _SOURCE_MODULE_PATH,
    (
        "apps/worker-python/scripts/"
        "build_m4_p3_predictive_route_reconciliation_manifest.py"
    ),
    "apps/worker-python/dehps/research_os/control_plane.py",
    "apps/worker-python/dehps/research_os/models.py",
    (
        "apps/worker-python/dehps/research_os/information_theory/"
        "measurement_system_v2/migration.py"
    ),
    "apps/worker-python/dehps/research_os/supervisor.py",
    "apps/worker-python/dehps/research_os/information_theory/progress.py",
)
_RECONCILIATION_DOMAIN = (
    "dehps.m4-p3.predictive-route-reconciliation-artifact.v1"
)
_POLICY_DOMAIN = "dehps.m4-p2r-to-p6.dependency-policy-artifact.v1"
_ROUTE_DECISION_DOMAIN = "dehps.m4-p3.predictive-route-decision-artifact.v1"
_REQUEST_IDENTITY_DOMAIN = "dehps.agent-request.result-blind-metadata.v1"
_EXECUTION_METADATA_IDENTITY_DOMAIN = (
    "dehps.agent-request-execution.result-blind-metadata.v1"
)
_REVIEWER_DECISION_IDENTITY_DOMAIN = (
    "dehps.agent-request-decision.append-only-identity.v1"
)
_EXECUTION_ARTIFACT_PATHS_IDENTITY_DOMAIN = (
    "dehps.agent-request-execution.artifact-paths.v1"
)
_FORBIDDEN_BLINDED_PAYLOAD_KEYS = frozenset(
    {
        "prediction_results",
        "predictive_p3_result_payload",
        "historical_fold_scores",
        "relative_random_baseline_performance",
        "winning_numbers",
        "prizes",
        "returns",
        "outcome_rank",
        "future_test_window_results",
    }
)

_LEGACY_DURABLE_P3_DEPENDENCIES = (
    ("task", P2_CLOSURE_TASK_KEY, "completed"),
    ("artifact", P2_PASS_TO_P3_FACT, "available"),
)
_CANONICAL_SOURCE_P3_DEPENDENCIES = (
    ("task", GLOBAL_ROUTING_TASK_KEY, "completed"),
    ("artifact", ADAPTIVE_RESEARCH_ELIGIBILITY_FACT, "available"),
)
_EXPECTED_P4_DEPENDENCIES = (
    ("task", PREDICTIVE_P3_TASK_KEY, "completed"),
    ("artifact", PREDICTIVE_P3_PASS_TO_P4_FACT, "available"),
)
_EXPECTED_P5_DEPENDENCIES = (
    ("task", P4_TASK_KEY, "completed"),
    ("task", "m4-forward-evidence-intake-2026085", "completed"),
)
_EXPECTED_P6_DEPENDENCIES = (
    ("task", P2_CLOSURE_TASK_KEY, "completed"),
    ("task", PREDICTIVE_P3_TASK_KEY, "completed"),
    ("task", P4_TASK_KEY, "completed"),
    ("task", P5_TASK_KEY, "completed"),
    ("artifact", P2R_TO_P6_POLICY_FACT, "available"),
)
_P2R_TO_P6_POLICY_FACT_PREFIX = "m4-p2r-to-p6-dependency-policy:"
_EXPECTED_P6_POLICY_METRICS = {
    "p2r_to_p6_policy": P2R_TO_P6_POLICY,
    "p2r_blocks_research_summary": False,
    "p2r_blocks_promotion": True,
    "promotion_release_fact": P2R_PROMOTION_ACCEPTANCE_FACT,
    "promotion_gate_default": "FAIL_CLOSED",
    "promotion_allowed_in_this_capability": False,
    "prediction_v2_mode_while_p2r_pending": "SHADOW_ONLY",
    "prediction_v2_route_while_p2r_pending": "BASELINE_ONLY",
}


class PredictiveRouteReconciliationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictiveRouteReconciliationArtifacts:
    reconciliation: Mapping[str, Any]
    p2r_to_p6_policy: Mapping[str, Any]
    route_decision: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (
            self.reconciliation,
            self.p2r_to_p6_policy,
            self.route_decision,
        )


def load_predictive_route_reconciliation_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictiveRouteReconciliationError(
            f"predictive_route_reconciliation_source_unreadable:{path}"
        ) from exc
    try:
        _validate_source_contract(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_source_invalid"
        ) from exc
    return payload


def verify_predictive_route_reconciliation_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    _validate_source_contract(contract)
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise PredictiveRouteReconciliationError(
                f"predictive_route_reconciliation_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise PredictiveRouteReconciliationError(
                f"predictive_route_reconciliation_source_modified:{relative}"
            )


def verify_predictive_route_reconciliation_v1_historical_git_objects(
    *,
    root_dir: Path,
    commit_oid: str,
    source_paths: Sequence[str],
) -> dict[str, Any]:
    """Audit immutable v1 against raw blobs at its pinned historical commit."""

    normalized_source_paths = tuple(str(path) for path in source_paths)
    if (
        commit_oid != PREDICTIVE_ROUTE_RECONCILIATION_V1_HISTORICAL_COMMIT
        or normalized_source_paths != _SOURCE_PATHS
        or len(set(normalized_source_paths)) != len(_SOURCE_PATHS)
    ):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_historical_identity_changed"
        )
    root = root_dir.resolve()
    env = {**os.environ, "GIT_NO_REPLACE_OBJECTS": "1"}

    def git(*arguments: str) -> bytes:
        try:
            return subprocess.run(
                ["git", *arguments],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError) as exc:
            raise PredictiveRouteReconciliationError(
                "predictive_route_reconciliation_historical_git_object_unavailable"
            ) from exc

    resolved = git("rev-parse", "--verify", f"{commit_oid}^{{commit}}").decode().strip()
    if resolved != commit_oid:
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_historical_commit_changed"
        )

    def historical_blob(relative: str) -> tuple[str, bytes]:
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise PredictiveRouteReconciliationError(
                "predictive_route_reconciliation_historical_path_unsafe"
            )
        record = git("ls-tree", "-z", commit_oid, "--", relative)
        records = [item for item in record.split(b"\0") if item]
        if len(records) != 1:
            raise PredictiveRouteReconciliationError(
                f"predictive_route_reconciliation_historical_source_missing:{relative}"
            )
        try:
            header, observed_path = records[0].split(b"\t", 1)
            mode, object_type, object_oid = header.decode("ascii").split(" ")
        except (ValueError, UnicodeDecodeError) as exc:
            raise PredictiveRouteReconciliationError(
                "predictive_route_reconciliation_historical_tree_invalid"
            ) from exc
        if (
            mode != "100644"
            or object_type != "blob"
            or observed_path.decode("utf-8") != relative
            or len(object_oid) != 40
        ):
            raise PredictiveRouteReconciliationError(
                f"predictive_route_reconciliation_historical_source_invalid:{relative}"
            )
        return object_oid, git("cat-file", "blob", object_oid)

    config_relative = PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_CONTRACT_PATH.as_posix()
    config_oid, config_bytes = historical_blob(config_relative)
    if hashlib.sha256(config_bytes).hexdigest() != PREDICTIVE_ROUTE_RECONCILIATION_V1_CONFIG_SHA256:
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_historical_config_modified"
        )
    try:
        contract = json.loads(config_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_historical_config_invalid"
        ) from exc
    _validate_source_contract(contract)
    source_oids: dict[str, str] = {}
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        object_oid, content = historical_blob(relative)
        if hashlib.sha256(content).hexdigest() != entry["content_sha256"]:
            raise PredictiveRouteReconciliationError(
                f"predictive_route_reconciliation_historical_source_modified:{relative}"
            )
        source_oids[relative] = object_oid
    return {
        "status": "VERIFIED",
        "commit_oid": commit_oid,
        "config_blob_oid": config_oid,
        "config_sha256": PREDICTIVE_ROUTE_RECONCILIATION_V1_CONFIG_SHA256,
        "artifact_digest": contract["artifact_digest"],
        "source_set_digest": contract["source_set_digest"],
        "source_blob_oids": source_oids,
    }


def governance_request_identity_digest(request: Mapping[str, Any]) -> str:
    return canonical_digest(
        _request_identity(request),
        domain=_REQUEST_IDENTITY_DOMAIN,
    )


def governance_execution_metadata_digest(execution: Mapping[str, Any]) -> str:
    return canonical_digest(
        _execution_metadata_identity(execution),
        domain=_EXECUTION_METADATA_IDENTITY_DOMAIN,
    )


def governance_reviewer_decision_digest(decision: Mapping[str, Any]) -> str:
    return canonical_digest(
        _reviewer_decision_identity(decision),
        domain=_REVIEWER_DECISION_IDENTITY_DOMAIN,
    )


def validate_result_blind_authorizations(
    *,
    source_contract: Mapping[str, Any],
    route_research_request: Mapping[str, Any],
    route_execution_metadata: Mapping[str, Any],
    route_decisions: Sequence[Mapping[str, Any]],
    policy_research_request: Mapping[str, Any],
    policy_execution_metadata: Mapping[str, Any],
    policy_decisions: Sequence[Mapping[str, Any]],
    engineering_request: Mapping[str, Any],
    engineering_execution_metadata: Mapping[str, Any],
    engineering_decisions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate only sanitized authority metadata; execution result fields are forbidden."""

    _validate_source_contract(source_contract)
    route = _validate_authorization_line(
        label="route",
        frozen=source_contract["route_research_request"],
        request=route_research_request,
        execution=route_execution_metadata,
        decisions=route_decisions,
        expected_request_key=ROUTE_RESEARCH_REQUEST_KEY,
        expected_request_id=ROUTE_RESEARCH_REQUEST_ID,
        expected_execution_id=ROUTE_RESEARCH_EXECUTION_ID,
        expected_decision_id=ROUTE_REVIEWER_APPROVAL_DECISION_ID,
        expected_request_type="research_scheduler_request",
        expected_executor_role="research",
    )
    policy = _validate_authorization_line(
        label="policy",
        frozen=source_contract["policy_research_request"],
        request=policy_research_request,
        execution=policy_execution_metadata,
        decisions=policy_decisions,
        expected_request_key=POLICY_RESEARCH_REQUEST_KEY,
        expected_request_id=POLICY_RESEARCH_REQUEST_ID,
        expected_execution_id=POLICY_RESEARCH_EXECUTION_ID,
        expected_decision_id=POLICY_REVIEWER_APPROVAL_DECISION_ID,
        expected_request_type="research_scheduler_request",
        expected_executor_role="research",
    )
    engineering = _validate_authorization_line(
        label="engineering",
        frozen=source_contract["engineering_request"],
        request=engineering_request,
        execution=engineering_execution_metadata,
        decisions=engineering_decisions,
        expected_request_key=str(source_contract["engineering_request"]["request_key"]),
        expected_request_id=ENGINEERING_REQUEST_ID,
        expected_execution_id=ENGINEERING_EXECUTION_ID,
        expected_decision_id=ENGINEERING_REVIEWER_APPROVAL_DECISION_ID,
        expected_request_type="engineering_implementation",
        expected_executor_role="engineering",
    )
    return {
        "status": "VALIDATED",
        "result_payloads_read": 0,
        "route": route,
        "policy": policy,
        "engineering": engineering,
    }


def build_predictive_route_reconciliation_artifacts(
    *,
    source_contract: Mapping[str, Any],
    authorization: Mapping[str, Any],
) -> PredictiveRouteReconciliationArtifacts:
    _validate_source_contract(source_contract)
    _validate_authorization_summary(authorization)
    parent_digests = _parent_digests(source_contract, authorization)

    reconciliation = _artifact(
        schema_version="dehps-m4-p3-predictive-route-reconciliation.v1",
        artifact_type="M4P3PredictiveRouteReconciliationArtifact",
        domain=_RECONCILIATION_DOMAIN,
        parent_digests=parent_digests,
        body={
            "status": "RECONCILED",
            "inspected_main_sha": source_contract["inspected_main_sha"],
            "static_manifest_digest": source_contract["static_manifest_digest"],
            "durable_manifest_digest": source_contract["durable_manifest_digest"],
            "durable_snapshot_digest": source_contract[
                "durable_snapshot_digest"
            ],
            "prediction_p3_task_identity": deepcopy(
                source_contract["prediction_p3_task_identity"]
            ),
            "actual_dependencies": deepcopy(source_contract["actual_dependencies"]),
            "source_dependencies": deepcopy(source_contract["source_dependencies"]),
            "global_routing_state": deepcopy(
                source_contract["global_routing_state"]
            ),
            "adaptive_research_eligible_fact": deepcopy(
                source_contract["adaptive_research_eligible_fact"]
            ),
            "p4_p5_p6_dependency_graph": deepcopy(
                source_contract["p4_p5_p6_dependency_graph"]
            ),
            "structural_p3_terminal_state": deepcopy(
                source_contract["structural_p3_terminal_state"]
            ),
            "detected_drift": deepcopy(source_contract["detected_drift"]),
            "drift_proven_by_dependency_mismatch": True,
            "old_goal_work_classification": deepcopy(
                source_contract["old_goal_work_classification"]
            ),
            "estimand_relationship": deepcopy(
                source_contract["estimand_relationship"]
            ),
            "result_payload_reads": 0,
            "historical_database_reads": 0,
            "computation": 0,
            "new_historical_folds": 0,
            "evidence_created": False,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
    )
    policy = _artifact(
        schema_version="dehps-m4-p2r-to-p6-dependency-policy.v1",
        artifact_type="P2RToP6DependencyPolicyArtifact",
        domain=_POLICY_DOMAIN,
        parent_digests=parent_digests,
        body={
            "status": "FROZEN",
            "policy": P2R_TO_P6_POLICY,
            "policy_fact": P2R_TO_P6_POLICY_FACT,
            "decision_rationale": deepcopy(source_contract["policy_rationale"]),
            "frozen_before_predictive_p3_result_access": True,
            "p3_p4_p5_dependency_effect": {
                "p2r_blocks_p3": False,
                "p2r_blocks_p4": False,
                "p2r_blocks_p5": False,
            },
            "p6_dependency_effect": {
                "research_summary_allowed_without_p2r": True,
                "hard_p2r_task_dependency": False,
                "policy_fact_required": P2R_TO_P6_POLICY_FACT,
            },
            "promotion_behavior": {
                "promotion_blocked_until_p2r_acceptance": True,
                "promotion_release_fact": P2R_PROMOTION_ACCEPTANCE_FACT,
                "promotion_gate": "FAIL_CLOSED",
                "prediction_v2_mode": "SHADOW_ONLY",
                "prediction_v2_route": "BASELINE_ONLY",
            },
            "result_payload_reads": 0,
            "computation": 0,
            "evidence_created": False,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
    )
    route_decision = _artifact(
        schema_version="dehps-m4-p3-predictive-route-decision.v1",
        artifact_type="PredictiveP3RouteDecisionArtifact",
        domain=_ROUTE_DECISION_DOMAIN,
        parent_digests=parent_digests,
        body={
            "status": "FROZEN",
            "decision": PREDICTIVE_ROUTE_DECISION,
            "decision_fact": PREDICTIVE_ROUTE_DECISION_FACT,
            "decision_rationale": deepcopy(
                source_contract["route_decision_rationale"]
            ),
            "decision_count": 1,
            "prediction_p3_task_key": PREDICTIVE_P3_TASK_KEY,
            "existing_task_identity_preserved": True,
            "successor_created": False,
            "scientific_endpoint_changed": False,
            "primary_endpoint": PREDICTIVE_P3_PRIMARY_ENDPOINT,
            "equal_budget_100_ticket_comparison_role": (
                EQUAL_BUDGET_COMPARISON_RELATIONSHIP
            ),
            "repair_scope": [
                "durable_dependency_identity",
                "p4_explicit_pass_fact_gate",
                "p6_frozen_policy_wiring",
                "unified_status_projection",
            ],
            "global_routing_status": "dependency_wait",
            "prediction_p3_status": "dependency_wait",
            "next_legal_task": deepcopy(source_contract["next_legal_task"]),
            "result_payload_reads": 0,
            "historical_database_reads": 0,
            "computation": 0,
            "new_historical_folds": 0,
            "evidence_created": False,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
    )
    return PredictiveRouteReconciliationArtifacts(
        reconciliation=reconciliation,
        p2r_to_p6_policy=policy,
        route_decision=route_decision,
    )


def replay_predictive_route_reconciliation_artifacts(
    *,
    expected: PredictiveRouteReconciliationArtifacts,
    source_contract: Mapping[str, Any],
    authorization: Mapping[str, Any],
    registered_content_verified: bool = False,
) -> dict[str, Any]:
    rebuilt = build_predictive_route_reconciliation_artifacts(
        source_contract=source_contract,
        authorization=authorization,
    )
    if tuple(dict(item) for item in expected.artifacts) != tuple(
        dict(item) for item in rebuilt.artifacts
    ):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_replay_identity_changed"
        )
    return {
        "schema_version": "dehps-m4-p3-predictive-route-reconciliation-replay.v1",
        "status": (
            "REGISTERED_REPLAY_VERIFIED"
            if registered_content_verified
            else "DETERMINISTIC_REBUILD_VERIFIED"
        ),
        "artifact_digests": [
            str(item["artifact_digest"]) for item in rebuilt.artifacts
        ],
        "same_registered_content": registered_content_verified,
        "registration_readback_performed": registered_content_verified,
        "same_reviewer_decision_identities": True,
        "workload_rerun": False,
        "result_payload_reads": 0,
        "historical_database_reads": 0,
        "historical_folds_replayed": 0,
        "evidence_created": False,
        "promotion_gate_opened": False,
        "manual_input_assembly": False,
        "production_action": "none",
    }


def validate_repaired_manifest_structure(
    manifest: Mapping[str, Any] | Any,
) -> dict[str, Any]:
    """Validate permanent route wiring without constraining runtime progress."""

    payload = _manifest_payload(manifest)
    tasks = _singular_tasks(payload)
    required_tasks = {
        PREDICTIVE_P3_TASK_KEY,
        P4_TASK_KEY,
        P6_TASK_KEY,
    }
    missing = sorted(required_tasks - set(tasks))
    if missing:
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_structural_tasks_missing:"
            + ",".join(missing)
        )

    _require_dependencies(
        tasks[PREDICTIVE_P3_TASK_KEY],
        expected=_CANONICAL_SOURCE_P3_DEPENDENCIES,
        label="predictive_p3",
    )
    _require_dependencies(
        tasks[P4_TASK_KEY], expected=_EXPECTED_P4_DEPENDENCIES, label="p4"
    )
    p3_metric = _mapping(
        tasks[PREDICTIVE_P3_TASK_KEY].get("metric_contract"), "p3 metric"
    )
    if p3_metric.get("primary_endpoint") != PREDICTIVE_P3_PRIMARY_ENDPOINT:
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_primary_endpoint_changed"
        )

    p6_dependencies = _dependency_tuples(tasks[P6_TASK_KEY].get("dependencies"))
    p6_policy_dependencies = tuple(
        item
        for item in p6_dependencies
        if item[0] == "artifact"
        and item[1].startswith(_P2R_TO_P6_POLICY_FACT_PREFIX)
    )
    if p6_policy_dependencies != (
        ("artifact", P2R_TO_P6_POLICY_FACT, "available"),
    ):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_p6_policy_dependency_changed"
        )
    if any(
        dependency_type == "task" and target_key == P2R_TASK_KEY
        for dependency_type, target_key, _ in p6_dependencies
    ):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_p2r_hard_dependency_present:p6"
        )

    p6_metric = _mapping(tasks[P6_TASK_KEY].get("metric_contract"), "p6 metric")
    if any(
        p6_metric.get(key) != expected
        for key, expected in _EXPECTED_P6_POLICY_METRICS.items()
    ):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_p6_policy_wiring_changed"
        )
    return {
        "status": "VERIFIED",
        "predictive_p3_dependencies": [
            list(item) for item in _CANONICAL_SOURCE_P3_DEPENDENCIES
        ],
        "p4_dependencies": [list(item) for item in _EXPECTED_P4_DEPENDENCIES],
        "p6_policy_fact": P2R_TO_P6_POLICY_FACT,
        "p2r_hard_task_dependency": False,
        "p6_policy_metrics": dict(_EXPECTED_P6_POLICY_METRICS),
    }


def validate_repaired_manifest(
    manifest: Mapping[str, Any] | Any,
    *,
    source_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the approved additive repair without resolving or executing a task."""

    _validate_source_contract(source_contract)
    payload = _manifest_payload(manifest)
    tasks = _singular_tasks(payload)
    facts = _facts(payload)

    required_tasks = {
        PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY,
        PREDICTIVE_P3_TASK_KEY,
        GLOBAL_ROUTING_TASK_KEY,
        P4_TASK_KEY,
        P5_TASK_KEY,
        P6_TASK_KEY,
        P2_CLOSURE_TASK_KEY,
        P2R_TASK_KEY,
        STRUCTURAL_P3_EVIDENCE_COMPILER_TASK_KEY,
    }
    missing = sorted(required_tasks - set(tasks))
    if missing:
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_manifest_tasks_missing:"
            + ",".join(missing)
        )
    forbidden_successors = sorted(
        key
        for key in tasks
        if key != PREDICTIVE_P3_TASK_KEY
        and (
            "repair-outcome-strict-historical-walk-forward" in key
            or key == "m4-p3-repair-outcome-successor"
        )
    )
    if forbidden_successors:
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_unauthorized_successor_present"
        )

    validate_repaired_manifest_structure(payload)
    _require_dependencies(
        tasks[P5_TASK_KEY], expected=_EXPECTED_P5_DEPENDENCIES, label="p5"
    )
    _require_dependencies(
        tasks[P6_TASK_KEY], expected=_EXPECTED_P6_DEPENDENCIES, label="p6"
    )
    artifact_facts = facts["artifacts"]
    external_events = facts["external_events"]
    if (
        tasks[P2_CLOSURE_TASK_KEY].get("status") != "completed"
        or P2_REPAIR_DECISION_FACT not in artifact_facts
        or P2_PASS_TO_P3_FACT in artifact_facts
        or P2_CLOSURE_COMPLETION_FACT not in artifact_facts
        or STRUCTURAL_P3_COMPLETION_FACT not in artifact_facts
        or P2R_EXECUTION_APPROVED_EVENT in external_events
        or ADAPTIVE_RESEARCH_ELIGIBILITY_FACT in artifact_facts
        or PREDICTIVE_P3_PASS_TO_P4_FACT in artifact_facts
    ):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_immutable_fact_boundary_changed"
        )

    governance_status = str(
        tasks[PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY].get("status") or "draft"
    )
    governance_completed = governance_status == "completed"
    governance_facts = {
        PREDICTIVE_ROUTE_RECONCILIATION_COMPLETION_FACT,
        PREDICTIVE_ROUTE_DECISION_FACT,
        P2R_TO_P6_POLICY_FACT,
    }
    present_governance_facts = governance_facts.intersection(artifact_facts)
    if governance_completed != (present_governance_facts == governance_facts):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_completion_facts_inconsistent"
        )
    if not governance_completed and present_governance_facts:
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_premature_governance_fact"
        )
    if tasks[P2R_TASK_KEY].get("status", "draft") != "draft":
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_p2r_state_changed"
        )
    if tasks[STRUCTURAL_P3_EVIDENCE_COMPILER_TASK_KEY].get("status") != "completed":
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_structural_terminal_state_changed"
        )

    missing_global_facts = [
        fact for fact in GLOBAL_ROUTING_BRANCH_REPLAY_FACTS if fact not in artifact_facts
    ]
    if not missing_global_facts or tasks[GLOBAL_ROUTING_TASK_KEY].get("status") == "completed":
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_global_routing_not_waiting"
        )
    return {
        "status": "VERIFIED",
        "governance_completed": governance_completed,
        "durable_manifest_digest": source_contract["durable_manifest_digest"],
        "durable_snapshot_digest": source_contract["durable_snapshot_digest"],
        "prediction_p3_task_key": PREDICTIVE_P3_TASK_KEY,
        "prediction_p3_status": "dependency_wait",
        "global_routing_status": "dependency_wait",
        "missing_global_routing_facts": missing_global_facts,
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


def _validate_source_contract(value: Mapping[str, Any] | Any) -> None:
    payload = _mapping(value, "source contract")
    entries = payload.get("source_entries")
    if (
        payload.get("schema_version")
        != PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_SCHEMA
        or payload.get("artifact_type")
        != PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_ARTIFACT_TYPE
        or payload.get("contract_key")
        != PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_CONTRACT_KEY
        or payload.get("inspected_main_sha")
        != PREDICTIVE_ROUTE_RECONCILIATION_INSPECTED_MAIN_SHA
        or payload.get("static_manifest_digest")
        != PREDICTIVE_ROUTE_RECONCILIATION_STATIC_MANIFEST_DIGEST
        or payload.get("durable_manifest_digest")
        != PREDICTIVE_ROUTE_RECONCILIATION_DURABLE_MANIFEST_DIGEST
        or payload.get("durable_snapshot_digest")
        != PREDICTIVE_ROUTE_RECONCILIATION_DURABLE_SNAPSHOT_DIGEST
        or payload.get("route_decision") != PREDICTIVE_ROUTE_DECISION
        or payload.get("p2r_to_p6_policy") != P2R_TO_P6_POLICY
        or payload.get("result_payload_reads") != 0
        or payload.get("historical_database_reads") != 0
        or payload.get("computation") != 0
        or payload.get("new_historical_folds") != 0
        or payload.get("evidence_created") is not False
        or payload.get("promotion_gate_opened") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or tuple(str(entry.get("path") or "") for entry in entries)
        != _SOURCE_PATHS
        or any(not _is_digest(entry.get("content_sha256")) for entry in entries)
        or payload.get("source_set_digest")
        != config_digest({"source_entries": entries})
        or payload.get("artifact_digest")
        != config_digest(
            {key: item for key, item in payload.items() if key != "artifact_digest"}
        )
    ):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_source_invalid"
        )

    identity = _mapping(payload.get("prediction_p3_task_identity"), "P3 identity")
    if identity.get("task_key") != PREDICTIVE_P3_TASK_KEY:
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_p3_identity_changed"
        )
    actual_dependencies = _dependency_tuples(payload.get("actual_dependencies"))
    source_dependencies = _dependency_tuples(payload.get("source_dependencies"))
    if actual_dependencies != _LEGACY_DURABLE_P3_DEPENDENCIES:
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_actual_dependencies_changed"
        )
    if source_dependencies != _CANONICAL_SOURCE_P3_DEPENDENCIES:
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_source_dependencies_changed"
        )
    if (
        payload.get("detected_drift") is not True
        or actual_dependencies == source_dependencies
    ):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_drift_not_proven"
        )
    global_state = _mapping(payload.get("global_routing_state"), "global routing")
    if (
        global_state.get("task_key") != GLOBAL_ROUTING_TASK_KEY
        or global_state.get("status") != "dependency_wait"
    ):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_global_route_changed"
        )
    adaptive = _mapping(
        payload.get("adaptive_research_eligible_fact"), "adaptive fact"
    )
    if (
        adaptive.get("fact") != ADAPTIVE_RESEARCH_ELIGIBILITY_FACT
        or adaptive.get("available") is not False
    ):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_adaptive_fact_changed"
        )
    structural = _mapping(
        payload.get("structural_p3_terminal_state"), "structural P3"
    )
    if (
        structural.get("decision") != STRUCTURAL_P3_TERMINAL_DECISION
        or structural.get("terminal") is not True
    ):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_structural_state_changed"
        )
    estimand = _mapping(payload.get("estimand_relationship"), "estimand")
    if (
        estimand.get("primary_endpoint") != PREDICTIVE_P3_PRIMARY_ENDPOINT
        or estimand.get("equal_budget_100_ticket_comparison_role")
        != EQUAL_BUDGET_COMPARISON_RELATIONSHIP
        or estimand.get("scientific_endpoint_changed") is not False
        or estimand.get("contracts_merged") is not False
    ):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_estimand_conflict"
        )
    effects = _mapping(payload.get("policy_effects"), "policy effects")
    expected_effects = {
        "p2r_blocks_p3": False,
        "p2r_blocks_p4": False,
        "p2r_blocks_p5": False,
        "p6_research_summary_allowed_without_p2r": True,
        "promotion_blocked_until_p2r_acceptance": True,
        "prediction_v2_mode": "SHADOW_ONLY",
        "prediction_v2_route": "BASELINE_ONLY",
    }
    if any(effects.get(key) != item for key, item in expected_effects.items()):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_policy_effects_changed"
        )
    for key in (
        "route_research_request",
        "policy_research_request",
        "engineering_request",
    ):
        _validate_frozen_authorization(_mapping(payload.get(key), key))
    for key in (
        "p4_p5_p6_dependency_graph",
        "old_goal_work_classification",
    ):
        _mapping(payload.get(key), key)
    for key in ("policy_rationale", "route_decision_rationale", "next_legal_task"):
        if payload.get(key) in (None, "", [], {}):
            raise PredictiveRouteReconciliationError(
                f"predictive_route_reconciliation_{key}_missing"
            )


def _validate_frozen_authorization(value: Mapping[str, Any]) -> None:
    if (
        not str(value.get("request_key") or "").strip()
        or not isinstance(value.get("request_id"), int)
        or not isinstance(value.get("execution_id"), int)
        or not isinstance(value.get("reviewer_approval_decision_id"), int)
        or not _is_digest(value.get("request_identity_digest"))
        or not _is_digest(value.get("execution_metadata_digest"))
        or not _is_digest(value.get("reviewer_approval_decision_digest"))
    ):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_authorization_identity_invalid"
        )


def _validate_authorization_line(
    *,
    label: str,
    frozen: Mapping[str, Any],
    request: Mapping[str, Any],
    execution: Mapping[str, Any],
    decisions: Sequence[Mapping[str, Any]],
    expected_request_key: str,
    expected_request_id: int,
    expected_execution_id: int,
    expected_decision_id: int,
    expected_request_type: str,
    expected_executor_role: str,
) -> dict[str, Any]:
    _validate_frozen_authorization(frozen)
    if (
        request.get("id") != expected_request_id
        or request.get("request_key") != expected_request_key
        or _enum_text(request.get("request_type")) != expected_request_type
        or frozen.get("request_key") != expected_request_key
        or frozen.get("request_id") != expected_request_id
        or frozen.get("execution_id") != expected_execution_id
        or frozen.get("reviewer_approval_decision_id") != expected_decision_id
    ):
        raise PredictiveRouteReconciliationError(
            f"predictive_route_reconciliation_{label}_request_identity_changed"
        )
    if _enum_text(request.get("status")) != "completed":
        raise PredictiveRouteReconciliationError(
            f"predictive_route_reconciliation_{label}_request_not_completed"
        )
    _reject_result_payload_fields(execution)
    artifact_paths = _validated_execution_artifact_paths(execution, label=label)
    if (
        execution.get("id") != expected_execution_id
        or execution.get("request_id") != expected_request_id
        or _enum_text(execution.get("executor_role")) != expected_executor_role
    ):
        raise PredictiveRouteReconciliationError(
            f"predictive_route_reconciliation_{label}_execution_identity_changed"
        )
    if (
        _enum_text(execution.get("status")) != "completed"
        or execution.get("completed_at") in (None, "")
    ):
        raise PredictiveRouteReconciliationError(
            f"predictive_route_reconciliation_{label}_execution_not_completed"
        )
    request_digest = governance_request_identity_digest(request)
    execution_digest = governance_execution_metadata_digest(execution)
    if (
        request_digest != frozen.get("request_identity_digest")
        or execution_digest != frozen.get("execution_metadata_digest")
    ):
        raise PredictiveRouteReconciliationError(
            f"predictive_route_reconciliation_{label}_metadata_digest_changed"
        )
    approval = _approval_decision(
        decisions,
        request_id=expected_request_id,
        decision_id=expected_decision_id,
        label=label,
    )
    decision_digest = governance_reviewer_decision_digest(approval)
    if decision_digest != frozen.get("reviewer_approval_decision_digest"):
        raise PredictiveRouteReconciliationError(
            f"predictive_route_reconciliation_{label}_reviewer_decision_changed"
        )
    return {
        "request_key": expected_request_key,
        "request_id": expected_request_id,
        "execution_id": expected_execution_id,
        "reviewer_approval_decision_id": expected_decision_id,
        "request_identity_digest": request_digest,
        "execution_metadata_digest": execution_digest,
        "reviewer_approval_decision_digest": decision_digest,
        "request_status": "completed",
        "execution_status": "completed",
        "execution_completed_at_present": True,
        "execution_artifact_paths": list(artifact_paths),
    }


def _approval_decision(
    decisions: Sequence[Mapping[str, Any]],
    *,
    request_id: int,
    decision_id: int,
    label: str,
) -> Mapping[str, Any]:
    matches = [item for item in decisions if item.get("id") == decision_id]
    if len(matches) != 1:
        raise PredictiveRouteReconciliationError(
            f"predictive_route_reconciliation_{label}_approval_not_singular"
        )
    approval = matches[0]
    _reject_blinded_payload(approval.get("reason") or {}, path="decision.reason")
    if (
        approval.get("request_id") != request_id
        or approval.get("previous_status") != "under_review"
        or approval.get("new_status") != "approved"
        or approval.get("decision_code") != "request_approved"
        or _enum_text(approval.get("decided_by_role")) != "reviewer"
    ):
        raise PredictiveRouteReconciliationError(
            f"predictive_route_reconciliation_{label}_approval_invalid"
        )
    later_control_decisions = [
        item
        for item in decisions
        if int(item.get("id") or 0) > decision_id
        and item.get("request_id") == request_id
        and _enum_text(item.get("decided_by_role")) == "reviewer"
        and item.get("decision_code")
        in {"request_approved", "request_rejected", "request_invalidated"}
    ]
    if later_control_decisions:
        raise PredictiveRouteReconciliationError(
            f"predictive_route_reconciliation_{label}_approval_superseded"
        )
    return approval


def _request_identity(request: Mapping[str, Any]) -> dict[str, Any]:
    _reject_blinded_payload(request.get("payload") or {})
    return {
        "id": request.get("id"),
        "request_key": request.get("request_key"),
        "request_type": _enum_text(request.get("request_type")),
        "requested_by_role": _enum_text(request.get("requested_by_role")),
        "requested_by": request.get("requested_by"),
        "hypothesis_id": request.get("hypothesis_id"),
        "experiment_id": request.get("experiment_id"),
        "parent_request_id": request.get("parent_request_id"),
        "title": request.get("title"),
        "summary": request.get("summary"),
        "payload": deepcopy(request.get("payload") or {}),
        "risk_level": _enum_text(request.get("risk_level")),
        "requires_review": request.get("requires_review"),
        "metadata": deepcopy(request.get("metadata") or {}),
    }


def _execution_metadata_identity(execution: Mapping[str, Any]) -> dict[str, Any]:
    _reject_result_payload_fields(execution)
    return {
        "id": execution.get("id"),
        "request_id": execution.get("request_id"),
        "executor_role": _enum_text(execution.get("executor_role")),
        "executor_id": execution.get("executor_id"),
        "execution_type": execution.get("execution_type"),
        "environment": execution.get("environment"),
        "run_id": execution.get("run_id"),
        "started_at": execution.get("started_at"),
        "created_at": execution.get("created_at"),
    }


def _reviewer_decision_identity(decision: Mapping[str, Any]) -> dict[str, Any]:
    _reject_blinded_payload(decision.get("reason") or {}, path="decision.reason")
    return {
        "id": decision.get("id"),
        "request_id": decision.get("request_id"),
        "previous_status": decision.get("previous_status"),
        "new_status": decision.get("new_status"),
        "decision_code": decision.get("decision_code"),
        "summary": decision.get("summary"),
        "reason": deepcopy(decision.get("reason") or {}),
        "decided_by_role": _enum_text(decision.get("decided_by_role")),
        "decided_by": decision.get("decided_by"),
        "decided_at": decision.get("decided_at"),
        "created_at": decision.get("created_at"),
    }


def _reject_result_payload_fields(execution: Mapping[str, Any]) -> None:
    forbidden = {
        "result",
        "result_json",
        "execution_result",
        "error",
        "error_json",
    }.intersection(execution)
    if forbidden:
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_execution_metadata_not_sanitized:"
            + ",".join(sorted(forbidden))
        )


def _validated_execution_artifact_paths(
    execution: Mapping[str, Any], *, label: str
) -> tuple[str, ...]:
    raw = execution.get("artifact_paths")
    if not isinstance(raw, list):
        raise PredictiveRouteReconciliationError(
            f"predictive_route_reconciliation_{label}_artifact_paths_invalid"
        )
    if any(not isinstance(item, str) or not item.strip() for item in raw):
        raise PredictiveRouteReconciliationError(
            f"predictive_route_reconciliation_{label}_artifact_paths_invalid"
        )
    paths = tuple(raw)
    if len(paths) != len(set(paths)):
        raise PredictiveRouteReconciliationError(
            f"predictive_route_reconciliation_{label}_artifact_paths_not_singular"
        )
    return paths


def _reject_blinded_payload(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        forbidden = _FORBIDDEN_BLINDED_PAYLOAD_KEYS.intersection(value)
        if forbidden:
            raise PredictiveRouteReconciliationError(
                "predictive_route_reconciliation_blinded_payload_contains_results:"
                + path
                + ":"
                + ",".join(sorted(forbidden))
            )
        for key, item in value.items():
            _reject_blinded_payload(item, path=f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, item in enumerate(value):
            _reject_blinded_payload(item, path=f"{path}[{index}]")


def _validate_authorization_summary(value: Mapping[str, Any]) -> None:
    if (
        value.get("status") != "VALIDATED"
        or value.get("result_payloads_read") != 0
    ):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_authorization_not_validated"
        )
    for label in ("route", "policy", "engineering"):
        line = _mapping(value.get(label), f"authorization {label}")
        artifact_paths = line.get("execution_artifact_paths")
        if (
            line.get("request_status") != "completed"
            or line.get("execution_status") != "completed"
            or line.get("execution_completed_at_present") is not True
            or not isinstance(line.get("request_id"), int)
            or not isinstance(line.get("execution_id"), int)
            or not isinstance(artifact_paths, list)
            or any(not isinstance(item, str) or not item for item in artifact_paths)
            or len(artifact_paths) != len(set(artifact_paths))
        ):
            raise PredictiveRouteReconciliationError(
                "predictive_route_reconciliation_authorization_runtime_state_invalid"
            )
        for key in (
            "request_identity_digest",
            "execution_metadata_digest",
            "reviewer_approval_decision_digest",
        ):
            if not _is_digest(line.get(key)):
                raise PredictiveRouteReconciliationError(
                    "predictive_route_reconciliation_authorization_digest_invalid"
                )


def _parent_digests(
    source_contract: Mapping[str, Any], authorization: Mapping[str, Any]
) -> tuple[str, ...]:
    values = [
        str(source_contract["artifact_digest"]),
        str(source_contract["static_manifest_digest"]),
        str(source_contract["durable_manifest_digest"]),
        str(source_contract["durable_snapshot_digest"]),
    ]
    for label in ("route", "policy", "engineering"):
        line = authorization[label]
        values.extend(
            str(line[key])
            for key in (
                "request_identity_digest",
                "execution_metadata_digest",
                "reviewer_approval_decision_digest",
            )
        )
        values.append(
            canonical_digest(
                {
                    "label": label,
                    "request_id": line["request_id"],
                    "execution_id": line["execution_id"],
                    "artifact_paths": list(line["execution_artifact_paths"]),
                },
                domain=_EXECUTION_ARTIFACT_PATHS_IDENTITY_DOMAIN,
            )
        )
    if len(values) != len(set(values)):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_parent_identity_collision"
        )
    return tuple(values)


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    domain: str,
    parent_digests: Sequence[str],
    body: Mapping[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "artifact_digest": "",
        **deepcopy(dict(body)),
        "parent_digests": list(parent_digests),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _manifest_payload(value: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return deepcopy(dict(value))
    to_dict = getattr(value, "to_dict", None)
    if not callable(to_dict):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_manifest_invalid"
        )
    payload = to_dict(include_digest=False)
    if not isinstance(payload, dict):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_manifest_invalid"
        )
    return payload


def _singular_tasks(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw = payload.get("tasks")
    if not isinstance(raw, list):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_manifest_tasks_invalid"
        )
    tasks: dict[str, Mapping[str, Any]] = {}
    for item in raw:
        task = _mapping(item, "task")
        key = str(task.get("task_key") or "")
        if not key or key in tasks:
            raise PredictiveRouteReconciliationError(
                "predictive_route_reconciliation_task_identity_not_singular"
            )
        tasks[key] = task
    return tasks


def _facts(payload: Mapping[str, Any]) -> dict[str, set[str]]:
    raw = _mapping(payload.get("facts"), "facts")
    output: dict[str, set[str]] = {}
    for key in ("artifacts", "evidence", "external_events", "authorities"):
        values = raw.get(key)
        if not isinstance(values, list):
            raise PredictiveRouteReconciliationError(
                f"predictive_route_reconciliation_facts_invalid:{key}"
            )
        output[key] = {str(item) for item in values}
    return output


def _require_dependencies(
    task: Mapping[str, Any],
    *,
    expected: tuple[tuple[str, str, str], ...],
    label: str,
) -> None:
    if _dependency_tuples(task.get("dependencies")) != expected:
        raise PredictiveRouteReconciliationError(
            f"predictive_route_reconciliation_{label}_dependencies_changed"
        )


def _dependency_mappings(task: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    raw = task.get("dependencies")
    if not isinstance(raw, list):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_dependencies_invalid"
        )
    return tuple(_mapping(item, "dependency") for item in raw)


def _dependency_tuples(value: Any) -> tuple[tuple[str, str, str], ...]:
    if not isinstance(value, list):
        raise PredictiveRouteReconciliationError(
            "predictive_route_reconciliation_dependencies_invalid"
        )
    return tuple(
        (
            str(_mapping(item, "dependency").get("dependency_type") or ""),
            str(_mapping(item, "dependency").get("target_key") or ""),
            str(
                _mapping(item, "dependency").get("required_status")
                or "available"
            ),
        )
        for item in value
    )


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PredictiveRouteReconciliationError(
            f"predictive_route_reconciliation_{label.replace(' ', '_')}_invalid"
        )
    return value


def _enum_text(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


__all__ = [
    "ADAPTIVE_RESEARCH_ELIGIBILITY_FACT",
    "ENGINEERING_APPROVED_EVENT",
    "ENGINEERING_EXECUTION_ID",
    "ENGINEERING_REQUEST_ID",
    "ENGINEERING_REVIEWER_APPROVAL_DECISION_ID",
    "EQUAL_BUDGET_COMPARISON_RELATIONSHIP",
    "GLOBAL_ROUTING_BRANCH_REPLAY_FACTS",
    "GLOBAL_ROUTING_TASK_KEY",
    "P2R_PROMOTION_ACCEPTANCE_FACT",
    "P2R_TASK_KEY",
    "P2R_TO_P6_POLICY",
    "P2R_TO_P6_POLICY_FACT",
    "P4_TASK_KEY",
    "P5_TASK_KEY",
    "P6_TASK_KEY",
    "POLICY_RESEARCH_APPROVED_EVENT",
    "POLICY_RESEARCH_EXECUTION_ID",
    "POLICY_RESEARCH_REQUEST_ID",
    "POLICY_RESEARCH_REQUEST_KEY",
    "POLICY_REVIEWER_APPROVAL_DECISION_ID",
    "PREDICTIVE_P3_PASS_TO_P4_FACT",
    "PREDICTIVE_P3_PRIMARY_ENDPOINT",
    "PREDICTIVE_P3_TASK_KEY",
    "PREDICTIVE_ROUTE_DECISION",
    "PREDICTIVE_ROUTE_DECISION_FACT",
    "PREDICTIVE_ROUTE_RECONCILIATION_CAPABILITY",
    "PREDICTIVE_ROUTE_RECONCILIATION_COMPLETION_FACT",
    "PREDICTIVE_ROUTE_RECONCILIATION_DURABLE_MANIFEST_DIGEST",
    "PREDICTIVE_ROUTE_RECONCILIATION_DURABLE_SNAPSHOT_DIGEST",
    "PREDICTIVE_ROUTE_RECONCILIATION_INSPECTED_MAIN_SHA",
    "PREDICTIVE_ROUTE_RECONCILIATION_SOURCE_CONTRACT_PATH",
    "PREDICTIVE_ROUTE_RECONCILIATION_STATIC_MANIFEST_DIGEST",
    "PREDICTIVE_ROUTE_RECONCILIATION_TASK_KEY",
    "PREDICTIVE_ROUTE_RECONCILIATION_V1_CONFIG_SHA256",
    "PREDICTIVE_ROUTE_RECONCILIATION_V1_HISTORICAL_COMMIT",
    "ROUTE_RESEARCH_APPROVED_EVENT",
    "ROUTE_RESEARCH_EXECUTION_ID",
    "ROUTE_RESEARCH_REQUEST_ID",
    "ROUTE_RESEARCH_REQUEST_KEY",
    "ROUTE_REVIEWER_APPROVAL_DECISION_ID",
    "STRUCTURAL_P3_TERMINAL_DECISION",
    "PredictiveRouteReconciliationArtifacts",
    "PredictiveRouteReconciliationError",
    "build_predictive_route_reconciliation_artifacts",
    "governance_execution_metadata_digest",
    "governance_request_identity_digest",
    "governance_reviewer_decision_digest",
    "load_predictive_route_reconciliation_source_contract",
    "replay_predictive_route_reconciliation_artifacts",
    "validate_repaired_manifest",
    "validate_repaired_manifest_structure",
    "validate_result_blind_authorizations",
    "verify_predictive_route_reconciliation_source_bytes",
    "verify_predictive_route_reconciliation_v1_historical_git_objects",
]
