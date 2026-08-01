from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from dehps.contracts import canonical_digest

from .contracts import MeasurementContractV2, json_compatible_copy


DESIGN_COMPLETION_FACT = "m4-measurement-contract-v2-design:FROZEN"


@dataclass(frozen=True)
class MeasurementContractV2DesignRun:
    estimand_contract: Mapping[str, Any]
    mechanism_role_contract: Mapping[str, Any]
    gate_compiler_contract: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (
            self.estimand_contract,
            self.mechanism_role_contract,
            self.gate_compiler_contract,
            self.completion,
        )


def build_design_artifacts(
    contract: MeasurementContractV2,
    *,
    execution_id: str,
    git_commit: str,
) -> MeasurementContractV2DesignRun:
    estimand = _artifact(
        schema_version="dehps-m4-measurement-v2-estimand-contract.v1",
        artifact_type="measurement_v2_estimand_contract",
        body={
            "legal_domain": contract.payload["legal_domain"],
            "information_axes": contract.payload["information_axes"],
            "estimand_contract": contract.payload["estimand_contract"],
            "p2_6_1_lineage_boundary": contract.payload[
                "p2_6_1_lineage_boundary"
            ],
        },
        parent_digests=(contract.artifact_digest,),
        domain="dehps.m4.measurement-v2.estimand-contract.v1",
    )
    roles = _artifact(
        schema_version="dehps-m4-measurement-v2-role-contract.v1",
        artifact_type="measurement_v2_mechanism_role_contract",
        body={
            "mechanism_role_contract": contract.payload[
                "mechanism_role_contract"
            ],
        },
        parent_digests=(contract.artifact_digest,),
        domain="dehps.m4.measurement-v2.role-contract.v1",
    )
    gate = _artifact(
        schema_version="dehps-m4-measurement-v2-gate-contract.v1",
        artifact_type="measurement_v2_gate_compiler_contract",
        body={
            "gate_compiler_contract": contract.payload[
                "gate_compiler_contract"
            ],
        },
        parent_digests=(contract.artifact_digest,),
        domain="dehps.m4.measurement-v2.gate-contract.v1",
    )
    completion_body: dict[str, Any] = {
        "status": "COMPLETE",
        "execution_id": execution_id,
        "git_commit": git_commit,
        "measurement_contract_v2_digest": contract.artifact_digest,
        "estimand_contract_digest": estimand["artifact_digest"],
        "mechanism_role_contract_digest": roles["artifact_digest"],
        "gate_compiler_contract_digest": gate["artifact_digest"],
        "completion_fact": DESIGN_COMPLETION_FACT,
        "actual_fold_count": 0,
        "formal_branch_runs_executed": 0,
        "historical_outcomes_read": False,
        "p2_6_1_partial_statistical_results_read": False,
        "evidence_created": False,
        "evidence_progress_increment": 0,
        "p2_6_1_runtime_operation": "none",
        "next_consumer": "m4-v2-branch-identifiability-preflight-design",
        "production_action": "none",
    }
    completion = _artifact(
        schema_version="dehps-m4-measurement-v2-design-completion.v1",
        artifact_type="measurement_v2_design_completion",
        body=completion_body,
        parent_digests=(
            contract.artifact_digest,
            str(estimand["artifact_digest"]),
            str(roles["artifact_digest"]),
            str(gate["artifact_digest"]),
        ),
        domain="dehps.m4.measurement-v2.design-completion.v1",
    )
    return MeasurementContractV2DesignRun(
        estimand_contract=estimand,
        mechanism_role_contract=roles,
        gate_compiler_contract=gate,
        completion=completion,
    )


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: tuple[str, ...],
    domain: str,
) -> dict[str, Any]:
    json_body = json_compatible_copy(body)
    if not isinstance(json_body, dict):
        raise TypeError("measurement v2 artifact body must be an object")
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "artifact_digest": "",
        **json_body,
        "parent_digests": list(parent_digests),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload
