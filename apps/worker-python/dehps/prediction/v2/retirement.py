from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dehps.config import ROOT_DIR
from dehps.prediction.v2.contracts import (
    ACTIVATION_FACT,
    ACTIVATION_SCHEMA,
    CUTOVER_PLAN_PATH,
    CUTOVER_PLAN_SCHEMA,
    PredictionV2ContractError,
    load_json_object,
    load_legacy_baseline,
    load_shadow_contract,
    seal_artifact,
    verify_artifact,
)


DEFAULT_ACTIVATION_PATH = ROOT_DIR / "runtime/prediction-v2/legacy-retirement-activation.json"


class LegacyPredictionRetiredError(RuntimeError):
    pass


def load_cutover_plan(root_dir: Path) -> dict[str, Any]:
    payload = load_json_object(root_dir / CUTOVER_PLAN_PATH)
    if payload.get("schema_version") != CUTOVER_PLAN_SCHEMA:
        raise PredictionV2ContractError("unsupported scheduler cutover plan schema")
    if payload.get("mode") != "DRY_RUN_ONLY":
        raise PredictionV2ContractError("source cutover plan must remain dry-run only")
    return seal_artifact(payload, domain="dehps.prediction-v2.scheduler-cutover-plan.v1")


def validate_activation(
    payload: Mapping[str, Any],
    *,
    root_dir: Path = ROOT_DIR,
) -> dict[str, Any]:
    value = verify_artifact(payload, domain="dehps.legacy-prediction-retirement-activation.v1")
    baseline = load_legacy_baseline(root_dir)
    contract = load_shadow_contract(root_dir)
    plan = load_cutover_plan(root_dir)
    expected = {
        "schema_version": ACTIVATION_SCHEMA,
        "status": "ACTIVE",
        "activation_fact": ACTIVATION_FACT,
        "legacy_baseline_digest": baseline["artifact_digest"],
        "prediction_v2_contract_digest": contract["artifact_digest"],
        "cutover_plan_digest": plan["artifact_digest"],
        "legacy_artifacts_preserved": True,
        "m4_state_changed": False,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise PredictionV2ContractError(f"legacy retirement activation mismatch: {key}")
    if not str(value.get("operator_request_id") or "").startswith("operator_"):
        raise PredictionV2ContractError("activation requires an approved typed Operator Request")
    if not str(value.get("activated_at") or "").strip():
        raise PredictionV2ContractError("activation requires a durable timestamp")
    return value


def legacy_retirement_status(
    *,
    root_dir: Path = ROOT_DIR,
    activation_path: Path | None = None,
) -> dict[str, Any]:
    path = activation_path or DEFAULT_ACTIVATION_PATH
    if not path.is_file():
        return {"status": "INACTIVE", "compute_allowed": True, "activation_path": str(path)}
    payload = load_json_object(path)
    activation = validate_activation(payload, root_dir=root_dir)
    return {
        "status": "ACTIVE",
        "compute_allowed": False,
        "activation_path": str(path),
        "activation_digest": activation["artifact_digest"],
    }


def require_legacy_compute_allowed(
    operation: str,
    *,
    root_dir: Path = ROOT_DIR,
    activation_path: Path | None = None,
) -> None:
    status = legacy_retirement_status(root_dir=root_dir, activation_path=activation_path)
    if status["status"] == "ACTIVE":
        raise LegacyPredictionRetiredError(f"legacy_prediction_line_retired:{operation}")


def scheduler_cutover_dry_run(*, root_dir: Path = ROOT_DIR) -> dict[str, Any]:
    baseline = load_legacy_baseline(root_dir)
    contract = load_shadow_contract(root_dir)
    plan = load_cutover_plan(root_dir)
    return seal_artifact(
        {
            "schema_version": "dehps-prediction-v2-scheduler-cutover-dry-run.v1",
            "artifact_type": "PredictionV2SchedulerCutoverDryRun.v1",
            "status": "PLAN_VERIFIED_NO_OPERATION",
            "legacy_baseline_digest": baseline["artifact_digest"],
            "prediction_v2_contract_digest": contract["artifact_digest"],
            "cutover_plan_digest": plan["artifact_digest"],
            "live_state_changed": False,
            "service_operations_executed": [],
            "database_writes_executed": [],
            "messages_sent": [],
            "m4_state_changed": False,
            "promotion_gate_opened": False,
            "parent_digests": [
                baseline["artifact_digest"],
                contract["artifact_digest"],
                plan["artifact_digest"],
            ],
        },
        domain="dehps.prediction-v2.scheduler-cutover-dry-run.v1",
    )
