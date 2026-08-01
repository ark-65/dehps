from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest


CONTRACT_PATH = Path("configs/prediction-v2/prediction-v2-shadow-contract-v1.json")
LEGACY_BASELINE_PATH = Path("configs/prediction-v2/legacy-prediction-baseline-v1.json")
CUTOVER_PLAN_PATH = Path("configs/prediction-v2/prediction-v2-scheduler-cutover-plan-v1.json")
CONTROL_PLANE_PATH = Path("configs/prediction-v2/prediction-v2-shadow-mainline-v1.json")

CONTRACT_SCHEMA = "dehps-prediction-v2-shadow-contract.v1"
LEGACY_BASELINE_SCHEMA = "dehps-legacy-prediction-baseline-manifest.v1"
CUTOVER_PLAN_SCHEMA = "dehps-prediction-v2-scheduler-cutover-plan.v1"
ACTIVATION_SCHEMA = "dehps-legacy-prediction-retirement-activation.v1"
ACTIVATION_FACT = "prediction-v2:legacy-three-lines:RETIREMENT_ACTIVATED"
SHADOW_ROUTE = "BASELINE_ONLY"
EXPERT_STATUS = "NOT_AUTHORIZED"
HISTORICAL_EVIDENCE = "NOT_RUN"
_ISSUE = re.compile(r"^[0-9]{7}$")


class PredictionV2ContractError(ValueError):
    """Raised when a Prediction v2 boundary cannot be trusted."""


def require_issue(value: object, *, field: str) -> str:
    normalized = str(value or "").strip()
    if not _ISSUE.fullmatch(normalized):
        raise PredictionV2ContractError(f"{field} must contain seven ASCII digits")
    return normalized


def seal_artifact(
    payload: Mapping[str, Any],
    *,
    domain: str,
) -> dict[str, Any]:
    value = dict(payload)
    if value.get("artifact_digest") not in (None, ""):
        raise PredictionV2ContractError("artifact payload is already sealed")
    value.pop("artifact_digest", None)
    value["artifact_digest"] = canonical_digest(value, domain=domain)
    return value


def verify_artifact(
    payload: Mapping[str, Any],
    *,
    domain: str,
) -> dict[str, Any]:
    value = dict(payload)
    stored = str(value.pop("artifact_digest", ""))
    expected = canonical_digest(value, domain=domain)
    if stored != expected:
        raise PredictionV2ContractError("artifact digest mismatch")
    value["artifact_digest"] = stored
    return value


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PredictionV2ContractError(f"cannot load contract: {path}") from exc
    if not isinstance(value, dict):
        raise PredictionV2ContractError(f"contract must be a JSON object: {path}")
    return value


def load_shadow_contract(root_dir: Path) -> dict[str, Any]:
    payload = load_json_object(root_dir / CONTRACT_PATH)
    if payload.get("schema_version") != CONTRACT_SCHEMA:
        raise PredictionV2ContractError("unsupported Prediction v2 contract schema")
    if payload.get("mode") != "SHADOW_ONLY":
        raise PredictionV2ContractError("Prediction v2 contract must be shadow-only")
    if payload.get("route") != SHADOW_ROUTE:
        raise PredictionV2ContractError("Prediction v2 route must remain BASELINE_ONLY")
    if payload.get("pool_size") != 10_000 or payload.get("top_size") != 100:
        raise PredictionV2ContractError("Prediction v2 pool and Top100 sizes are frozen")
    if payload.get("state_windows") != [30, 60, 120]:
        raise PredictionV2ContractError("Prediction v2 state windows are frozen")
    experts = payload.get("experts")
    if not isinstance(experts, dict) or any(
        experts.get(name) != status
        for name, status in {
            "marginal": EXPERT_STATUS,
            "temporal": EXPERT_STATUS,
            "diversity": "OBSERVATION_ONLY",
        }.items()
    ):
        raise PredictionV2ContractError("Prediction v2 expert authorization changed")
    if payload.get("historical_evidence") != HISTORICAL_EVIDENCE:
        raise PredictionV2ContractError("shadow contract cannot carry Historical Evidence")
    return seal_artifact(payload, domain="dehps.prediction-v2.shadow-contract.v1")


def load_legacy_baseline(root_dir: Path) -> dict[str, Any]:
    payload = load_json_object(root_dir / LEGACY_BASELINE_PATH)
    if payload.get("schema_version") != LEGACY_BASELINE_SCHEMA:
        raise PredictionV2ContractError("unsupported legacy baseline schema")
    lines = payload.get("lines")
    if not isinstance(lines, list) or [line.get("line_key") for line in lines] != [
        "static_100",
        "dynamic_kdj",
        "dynamic_kdj_near",
    ]:
        raise PredictionV2ContractError("legacy baseline must preserve exactly three lines")
    if any(line.get("lifecycle") != "LEGACY_FROZEN" for line in lines):
        raise PredictionV2ContractError("legacy line lifecycle changed")
    return seal_artifact(payload, domain="dehps.legacy-prediction-baseline.v1")
