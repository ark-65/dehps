from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

from .marginal_static_health_decision import (
    EXPECTED_FAILED_GATE_MAP,
    HEALTH_RESULT_DIGEST,
    MARGINAL_STATIC_HEALTH_DECISION_REPAIR_FACT,
)

MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-design"
)
MARGINAL_STATIC_REPAIR_DESIGN_CAPABILITY = (
    "m4_v2_marginal_static_measurement_repair_design"
)
MARGINAL_STATIC_REPAIR_DESIGN_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-repair-design:FROZEN"
)
MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-preregistration"
)
MARGINAL_STATIC_REPAIR_DESIGN_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-v2-marginal-static-repair-design-source-v1.json"
)

HEALTH_DECISION_TASK_KEY = "m4-v2-marginal-static-measurement-health-decision"
HEALTH_DECISION_EXECUTION_ID = (
    "646d481ab9acfb495f5633e4968ab5e1138f938ca68fe971b4914b3a2c80b640"
)
HEALTH_DECISION_EXECUTION_ARTIFACT_DIGEST = (
    "523aaf632019acca749cd246c97514c68c22c6cf8001f64d752bb8d4fc5d3ddc"
)
HEALTH_DECISION_ARTIFACT_DIGEST = (
    "cb653dc02739958814b0e4b349e163bd10f9256a19c05f61dbc1808fe6948d50"
)

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-m4-v2-marginal-static-repair-design-round-44-20260808"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-v2-marginal-static-repair-design-round-44-20260808"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/marginal_static_repair_design.py"
)
_EXPECTED_FORWARD_POWER = {
    "0.010": 0.22958915217193457,
    "0.050": 0.6475131406108688,
}
_EXPECTED_HISTORICAL_POWER = {
    "0.010": 0.9999890785821147,
    "0.050": 0.9999999999999993,
}
_EXPECTED_OLD_POWER_REQUIREMENTS = {"0.010": 0.8, "0.050": 0.95}
_EXPECTED_ROOT_SEED_DOMAIN = "M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_V1"
_EXPECTED_BOOTSTRAP_SEED_DOMAIN = (
    "M4_V2_MARGINAL_STATIC_REPAIR_HEALTH_BOOTSTRAP_V1"
)


class MarginalStaticRepairDesignError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarginalStaticRepairDesignRun:
    feasibility: Mapping[str, Any]
    repair_design: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (self.feasibility, self.repair_design, self.completion)


def load_marginal_static_repair_design_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticRepairDesignError(
            f"marginal_static_repair_design_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-repair-design-source.v1"
        or payload.get("artifact_type")
        != "m4_v2_marginal_static_repair_design_source"
        or payload.get("contract_key")
        != "M4_V2_MARGINAL_STATIC_REPAIR_DESIGN_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 334
        or payload.get("research_execution_id") != 255
        or payload.get("engineering_request_key")
        != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 335
        or payload.get("result_aware") is not True
        or payload.get("formal_replicates_executed") != 0
        or payload.get("generated_issues") != 0
        or payload.get("historical_outcomes_read") is not False
        or payload.get("statistical_results_read") is not True
        or payload.get("evidence_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or len(entries) != 1
        or not isinstance(frozen, dict)
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain="dehps.m4.v2.marginal-static-repair-design-source-set.v1",
        )
    ):
        raise MarginalStaticRepairDesignError(
            "marginal_static_repair_design_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise MarginalStaticRepairDesignError(
            "marginal_static_repair_design_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_marginal_static_repair_design_source_bytes(
    *,
    root_dir: Path,
    contract: Mapping[str, Any],
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MarginalStaticRepairDesignError(
                f"marginal_static_repair_design_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise MarginalStaticRepairDesignError(
                f"marginal_static_repair_design_source_modified:{relative}"
            )


def build_marginal_static_repair_design_artifacts(
    *,
    source_contract: Mapping[str, Any],
    health_decision_execution: Mapping[str, Any],
    health_decision: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
) -> MarginalStaticRepairDesignRun:
    frozen = source_contract.get("frozen_contract")
    if not isinstance(frozen, Mapping):
        raise MarginalStaticRepairDesignError(
            "marginal_static_repair_design_contract_missing"
        )
    _validate_frozen_contract(frozen)
    _validate_health_decision(
        execution=health_decision_execution,
        decision=health_decision,
    )
    source_digest = str(source_contract["artifact_digest"])
    decision_execution_digest = str(health_decision_execution["artifact_digest"])
    decision_digest = str(health_decision["artifact_digest"])
    parent_digests = (source_digest, decision_execution_digest, decision_digest)
    feasibility = _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-repair-analytic-feasibility.v1"
        ),
        artifact_type="m4_v2_marginal_static_repair_analytic_feasibility",
        body={
            "status": "FROZEN_ANALYTIC_FEASIBILITY",
            "branch_id": "MARGINAL_STATIC",
            "source_contract_digest": source_digest,
            "health_result_digest": HEALTH_RESULT_DIGEST,
            "health_decision_digest": decision_digest,
            "method": frozen["pre_sample_feasibility_audit"]["method"],
            "test_size": 0.05,
            "legal_sample_space": "all C(33,6) legal subsets",
            "forward_61_exact_np_upper_power": frozen[
                "analytic_power_feasibility"
            ]["forward_61"],
            "historical_2581_exact_np_upper_power": frozen[
                "analytic_power_feasibility"
            ]["historical_2581"],
            "old_power_requirements": frozen["old_power_requirements"],
            "forward_61_gate_admissible": {"0.010": False, "0.050": False},
            "forward_61_classification": "ANALYTICALLY_INFEASIBLE",
            "historical_2581_classification": (
                "ORACLE_FEASIBLE_BUT_ONLINE_ESTIMATOR_TRUTH_NONPOSITIVE"
            ),
            "result_selected_exception": "forbidden",
            "generated_issues": 0,
            "synthetic_replicates": 0,
            "checkpoint_reads": 0,
            "duplicate_validation": False,
            "historical_outcomes_read": False,
            "evidence_created": False,
            "production_action": "none",
        },
        parent_digests=parent_digests,
        domain="dehps.m4.v2.marginal-static-repair-analytic-feasibility.v1",
    )
    repair_design = _artifact(
        schema_version="dehps-m4-v2-marginal-static-repair-design.v1",
        artifact_type="m4_v2_marginal_static_measurement_repair_design",
        body={
            "status": "FROZEN_DESIGN",
            "branch_id": "MARGINAL_STATIC",
            "source_contract_digest": source_digest,
            "health_result_digest": HEALTH_RESULT_DIGEST,
            "health_decision_digest": decision_digest,
            "old_measurement_health": "REPAIR",
            "old_decision_preserved": "REPAIR_MEASUREMENT_SYSTEM",
            "failed_gate_map": {
                key: list(value) for key, value in EXPECTED_FAILED_GATE_MAP.items()
            },
            "analytic_feasibility_digest": feasibility["artifact_digest"],
            "diagnosis": frozen["diagnosis"],
            "estimand_layers": frozen["estimand_layers"],
            "bias_and_truth": frozen["bias_and_truth"],
            "inference_routing": frozen["inference_routing"],
            "power_and_mde": frozen["power_and_mde"],
            "seed_contract": frozen["seed_contract"],
            "resource_boundary": frozen["resource_boundary"],
            "automatic_pass_from_reanalysis": False,
            "same_seed_tuning": "forbidden",
            "posthoc_threshold_change": "forbidden",
            "next_consumer": MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY,
            "generated_issues": 0,
            "synthetic_replicates": 0,
            "checkpoint_reads": 0,
            "duplicate_validation": False,
            "historical_outcomes_read": False,
            "evidence_created": False,
            "accepted_model_artifact_digest": None,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
        parent_digests=(*parent_digests, str(feasibility["artifact_digest"])),
        domain="dehps.m4.v2.marginal-static-measurement-repair-design.v1",
    )
    completion = _artifact(
        schema_version="dehps-m4-v2-marginal-static-repair-design-completion.v1",
        artifact_type="m4_v2_marginal_static_repair_design_completion",
        body={
            "status": "COMPLETE",
            "execution_id": execution_id,
            "git_commit": git_commit,
            "source_contract_digest": source_digest,
            "health_decision_digest": decision_digest,
            "analytic_feasibility_digest": feasibility["artifact_digest"],
            "repair_design_digest": repair_design["artifact_digest"],
            "completion_fact": MARGINAL_STATIC_REPAIR_DESIGN_COMPLETION_FACT,
            "next_consumer": MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY,
            "generated_issues": 0,
            "synthetic_replicates": 0,
            "checkpoint_reads": 0,
            "duplicate_validation": False,
            "historical_outcomes_read": False,
            "evidence_created": False,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
        parent_digests=(
            *parent_digests,
            str(feasibility["artifact_digest"]),
            str(repair_design["artifact_digest"]),
        ),
        domain="dehps.m4.v2.marginal-static-repair-design-completion.v1",
    )
    return MarginalStaticRepairDesignRun(
        feasibility=feasibility,
        repair_design=repair_design,
        completion=completion,
    )


def _validate_health_decision(
    *,
    execution: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> None:
    failed_gate_map = decision.get("failed_gate_map")
    expected_failed_gate_map = {
        key: list(value) for key, value in EXPECTED_FAILED_GATE_MAP.items()
    }
    if (
        execution.get("execution_id") != HEALTH_DECISION_EXECUTION_ID
        or execution.get("artifact_digest")
        != HEALTH_DECISION_EXECUTION_ARTIFACT_DIGEST
        or execution.get("task_key") != HEALTH_DECISION_TASK_KEY
        or execution.get("completion_classification") != "VALIDATED_IN_MAINLINE"
        or execution.get("decision") != "REPAIR_MEASUREMENT_SYSTEM"
        or execution.get("decision_fact")
        != MARGINAL_STATIC_HEALTH_DECISION_REPAIR_FACT
        or execution.get("duplicate_validation") is not False
        or execution.get("historical_outcomes_read") is not False
        or execution.get("evidence_created") is not False
        or execution.get("promotion_gate_opened") is not False
        or decision.get("artifact_type")
        != "m4_v2_marginal_static_measurement_health_decision"
        or decision.get("artifact_digest") != HEALTH_DECISION_ARTIFACT_DIGEST
        or decision.get("health_result_digest") != HEALTH_RESULT_DIGEST
        or decision.get("measurement_health") != "REPAIR"
        or decision.get("decision") != "REPAIR_MEASUREMENT_SYSTEM"
        or decision.get("decision_fact")
        != MARGINAL_STATIC_HEALTH_DECISION_REPAIR_FACT
        or decision.get("failed_cell_count") != 4
        or failed_gate_map != expected_failed_gate_map
        or decision.get("threshold_changed") is not False
        or decision.get("manual_override") is not False
        or decision.get("duplicate_validation") is not False
        or decision.get("historical_outcomes_read") is not False
        or decision.get("evidence_created") is not False
        or decision.get("promotion_gate_opened") is not False
        or decision.get("production_action") != "none"
    ):
        raise MarginalStaticRepairDesignError(
            "marginal_static_repair_design_health_decision_changed"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    feasibility = frozen.get("analytic_power_feasibility")
    seed_contract = frozen.get("seed_contract")
    resource = frozen.get("resource_boundary")
    if (
        frozen.get("task_key") != MARGINAL_STATIC_REPAIR_DESIGN_TASK_KEY
        or frozen.get("capability") != MARGINAL_STATIC_REPAIR_DESIGN_CAPABILITY
        or frozen.get("completion_fact")
        != MARGINAL_STATIC_REPAIR_DESIGN_COMPLETION_FACT
        or frozen.get("next_consumer")
        != MARGINAL_STATIC_REPAIR_PREREGISTRATION_TASK_KEY
        or frozen.get("health_result_digest") != HEALTH_RESULT_DIGEST
        or frozen.get("health_decision_digest")
        != HEALTH_DECISION_ARTIFACT_DIGEST
        or frozen.get("old_decision") != "REPAIR_MEASUREMENT_SYSTEM"
        or frozen.get("old_failed_gate_map")
        != {key: list(value) for key, value in EXPECTED_FAILED_GATE_MAP.items()}
        or not isinstance(feasibility, Mapping)
        or feasibility.get("forward_61") != _EXPECTED_FORWARD_POWER
        or feasibility.get("historical_2581") != _EXPECTED_HISTORICAL_POWER
        or frozen.get("old_power_requirements")
        != _EXPECTED_OLD_POWER_REQUIREMENTS
        or frozen.get("pre_sample_feasibility_audit", {}).get("test_size") != 0.05
        or frozen.get("pre_sample_feasibility_audit", {}).get("method")
        != (
            "exact legal-six group-count convolution and randomized "
            "Neyman-Pearson upper envelope"
        )
        or frozen.get("bias_and_truth", {}).get("absolute_numerical_error_max")
        != 1e-12
        or frozen.get("inference_routing", {}).get("iid")
        != "IID_RESAMPLING_OR_EXACT_METHOD_PREREGISTRATION_REQUIRED"
        or frozen.get("inference_routing", {}).get("dependent")
        != "CIRCULAR_BLOCK_WITH_SENSITIVITY"
        or not isinstance(seed_contract, Mapping)
        or seed_contract.get("root_seed_domain") != _EXPECTED_ROOT_SEED_DOMAIN
        or seed_contract.get("bootstrap_seed_domain")
        != _EXPECTED_BOOTSTRAP_SEED_DOMAIN
        or seed_contract.get("round_42_seed_reuse") is not False
        or seed_contract.get("worker_or_shard_identity_in_seed") is not False
        or seed_contract.get("best_seed_selection") != "forbidden"
        or not isinstance(resource, Mapping)
        or resource.get("repair_design_replicates") != 0
        or resource.get("repair_design_generated_issues") != 0
        or resource.get("checkpoint_reads") != 0
        or resource.get("duplicate_validation") is not False
        or resource.get("database_reads") != 0
        or resource.get("database_writes") != 0
        or resource.get("historical_outcomes_read") is not False
        or resource.get("evidence_created") is not False
        or frozen.get("automatic_pass_from_reanalysis") is not False
        or frozen.get("same_seed_tuning") != "forbidden"
        or frozen.get("posthoc_threshold_change") != "forbidden"
        or frozen.get("production_action") != "none"
    ):
        raise MarginalStaticRepairDesignError(
            "marginal_static_repair_design_contract_invalid"
        )
    for field in (
        "diagnosis",
        "estimand_layers",
        "bias_and_truth",
        "inference_routing",
        "power_and_mde",
    ):
        if not isinstance(frozen.get(field), Mapping):
            raise MarginalStaticRepairDesignError(
                "marginal_static_repair_design_contract_invalid"
            )


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: tuple[str, ...],
    domain: str,
) -> dict[str, Any]:
    if not parent_digests or any(not _is_digest(item) for item in parent_digests):
        raise MarginalStaticRepairDesignError(
            "marginal_static_repair_design_parent_digest_invalid"
        )
    payload = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "artifact_digest": "",
        **dict(body),
        "parent_digests": list(parent_digests),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
