from __future__ import annotations

from pathlib import Path
from typing import Any

from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentRequestStatus, AgentRequestType
from dehps.experiments.ranking_disagreement.artifacts import validate_manifest
from dehps.experiments.ranking_disagreement.models import (
    BASELINE_KEYS,
    FROZEN_PLAN_FINGERPRINT,
    FROZEN_PLAN_KEY,
    FROZEN_RANKER_KEYS,
    STRATA_KEYS,
    normalize_ranker_key,
)
from dehps.research.repository import HypothesisRepository
from dehps.research.status import HypothesisStatus
from dehps.research_planning.repository import ExperimentPlanningRepository


def validate_frozen_plan(plan: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(key: str, passed: bool, reason: str) -> None:
        checks.append({"key": key, "passed": bool(passed), "reason": reason})

    add("plan_key", plan.get("plan_key") == FROZEN_PLAN_KEY, "plan key must match Round 24 frozen object")
    add(
        "plan_fingerprint",
        plan.get("plan_fingerprint") == FROZEN_PLAN_FINGERPRINT,
        "plan fingerprint must be unchanged",
    )
    add("mechanism", plan.get("mechanism") == "ranking_model_disagreement", "mechanism must remain frozen")
    rankers = tuple(
        normalize_ranker_key(str(item.get("key")))
        for item in plan.get("model_contract", {}).get("rankers", [])
    )
    add("rankers", rankers == FROZEN_RANKER_KEYS, f"rankers must normalize to {FROZEN_RANKER_KEYS}")
    strata = tuple(plan.get("feature_contract", {}).get("strata", {}).get("keys", []))
    add("strata", strata == STRATA_KEYS, f"strata must be {STRATA_KEYS}")
    baselines = tuple(plan.get("baseline_contract", {}).get("matched_baselines", []))
    add("baselines", baselines == BASELINE_KEYS, f"baselines must be {BASELINE_KEYS}")
    protocol = plan.get("validation_protocol", {})
    add("search_window", protocol.get("search_issue_count") == 100, "search window must be 100 historical issues")
    add("frozen_window", protocol.get("frozen_issue_count") == 20, "frozen window must be next 20 historical issues")
    add("forward_not_executed", protocol.get("forward_min_paired_issues") == 20, "forward is planned but not run")
    valid = all(item["passed"] for item in checks)
    return {"valid": valid, "checks": checks, "failure_reasons": [item["reason"] for item in checks if not item["passed"]]}


def load_and_validate_plan(plan_key: str = FROZEN_PLAN_KEY) -> dict[str, Any]:
    payload = ExperimentPlanningRepository().get_materialized_plan_payload(plan_key)
    report = validate_frozen_plan(payload)
    if not report["valid"]:
        raise ValueError("frozen plan validation failed: " + "; ".join(report["failure_reasons"]))
    hypothesis = HypothesisRepository().get_hypothesis(str(payload["hypothesis_key"]))
    if hypothesis.status != HypothesisStatus.PREREGISTERED:
        raise ValueError(f"hypothesis must remain preregistered; found {hypothesis.status.value}")
    return payload


def require_approved_operator_request(*, operator_request_key: str, plan_key: str) -> dict[str, Any]:
    request = AgentRequestRepository().get_request(operator_request_key)
    if request.request_type != AgentRequestType.OPERATOR_ISOLATED_RUN:
        raise ValueError(f"request is not operator_isolated_run: {operator_request_key}")
    if request.status != AgentRequestStatus.APPROVED:
        raise ValueError(f"operator request must be approved before run-isolated; found {request.status.value}")
    payload = request.payload
    if payload.get("experiment_plan_key") != plan_key:
        raise ValueError("operator request does not target the requested plan")
    if payload.get("environment") != "isolated":
        raise ValueError("operator request environment must be isolated")
    if payload.get("production_access") is not False:
        raise ValueError("operator request production_access must be false")
    database = str(payload.get("database") or "")
    if database in {"dehps", "production", "prod"}:
        raise ValueError(f"operator request cannot target production database: {database}")
    return {"valid": True, "request_key": request.request_key, "database": database, "payload": payload}


def validate_artifact_directory(path: Path) -> dict[str, Any]:
    return validate_manifest(path / "manifest.json")
