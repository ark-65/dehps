from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dehps.contracts import canonical_digest

from .contracts import BRANCH_IDS, MeasurementContractV2Error

ADAPTIVE_RESEARCH_ELIGIBILITY_FACT = (
    "m4-v2-routing:ADAPTIVE_RESEARCH_ELIGIBLE"
)
NO_DETECTABLE_INFORMATION = (
    "NO_DETECTABLE_INFORMATION_UNDER_FROZEN_M4_V2_CONTRACT"
)


def compile_m4_v2_routing_decision(
    gate_output: Mapping[str, Any],
) -> dict[str, Any]:
    """Route only replay-eligible, full-coverage hierarchical evidence."""

    if (
        gate_output.get("schema_version")
        != "dehps-m4-measurement-gate-compiler-output.v2"
        or gate_output.get("artifact_type")
        != "hierarchical_measurement_gate_output"
        or gate_output.get("promotion_gate_opened") is not False
        or gate_output.get("production_action") != "none"
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_routing_input_invalid",
            "routing requires a non-production v2 Gate Compiler output",
        )
    gate_digest = str(gate_output.get("artifact_digest") or "")
    if len(gate_digest) != 64:
        raise MeasurementContractV2Error(
            "measurement_v2_routing_input_invalid",
            "Gate Compiler output digest is missing",
        )
    branch_outputs = gate_output.get("branch_outputs")
    if not isinstance(branch_outputs, list) or len(branch_outputs) != 3:
        raise MeasurementContractV2Error(
            "measurement_v2_routing_input_invalid",
            "routing requires all three branch outputs",
        )
    by_id = {
        str(item.get("branch_id")): item
        for item in branch_outputs
        if isinstance(item, Mapping)
    }
    if set(by_id) != set(BRANCH_IDS):
        raise MeasurementContractV2Error(
            "measurement_v2_routing_input_invalid",
            "routing branch coverage changed",
        )
    coverage = gate_output.get("global_coverage")
    if coverage not in {"FULL", "PARTIAL"}:
        raise MeasurementContractV2Error(
            "measurement_v2_routing_input_invalid",
            "routing coverage is invalid",
        )
    health = {
        branch_id: by_id[branch_id].get("measurement_health")
        for branch_id in BRANCH_IDS
    }
    evidence = {
        branch_id: by_id[branch_id].get("historical_evidence")
        for branch_id in BRANCH_IDS
    }
    if any(value not in {"PASS", "REPAIR", "INCONCLUSIVE"} for value in health.values()):
        raise MeasurementContractV2Error(
            "measurement_v2_routing_input_invalid",
            "branch Measurement Health is invalid",
        )
    if any(
        value not in {"POSITIVE", "NEGATIVE", "INCONCLUSIVE", "NOT_RUN"}
        for value in evidence.values()
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_routing_input_invalid",
            "branch Historical Evidence is invalid",
        )

    positive = [
        branch_id
        for branch_id in BRANCH_IDS
        if health[branch_id] == "PASS" and evidence[branch_id] == "POSITIVE"
    ]
    repair = [branch_id for branch_id in BRANCH_IDS if health[branch_id] == "REPAIR"]
    if coverage == "FULL" and positive:
        route = "ADAPTIVE_RESEARCH_ELIGIBLE"
        next_lane = "P3_ADAPTIVE_RESEARCH"
    elif coverage == "FULL" and all(
        evidence[branch_id] == "NEGATIVE" for branch_id in BRANCH_IDS
    ):
        route = NO_DETECTABLE_INFORMATION
        next_lane = "KERNEL_SEARCH_EFFICIENCY"
    elif repair and not positive:
        route = "MEASUREMENT_REPAIR_REQUIRED"
        next_lane = "MEASUREMENT_REPAIR"
    else:
        route = "DEEPER_VALIDATION_REQUIRED"
        next_lane = "M4_DEEPER_VALIDATION"

    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-measurement-routing-decision.v1",
        "artifact_type": "m4_measurement_routing_decision",
        "artifact_digest": "",
        "gate_output_digest": gate_digest,
        "measurement_contract_v2_digest": gate_output.get("contract_digest"),
        "global_coverage": coverage,
        "gate_global_evidence": gate_output.get("global_evidence"),
        "route": route,
        "next_lane": next_lane,
        "positive_branches": positive,
        "repair_branches": repair,
        "expert_router_research_enabled": (
            route == "ADAPTIVE_RESEARCH_ELIGIBLE"
        ),
        "adaptive_research_eligibility_fact": (
            ADAPTIVE_RESEARCH_ELIGIBILITY_FACT
            if route == "ADAPTIVE_RESEARCH_ELIGIBLE"
            else None
        ),
        "full_coverage_required": True,
        "partial_candidate_does_not_route": True,
        "production_candidate_created": False,
        "promotion_gate_opened": False,
        "production_action": "none",
        "parent_digests": [gate_digest],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.measurement-v2.routing-decision.v1",
    )
    return payload
