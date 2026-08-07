from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

from .contracts import (
    BRANCH_IDS,
    MeasurementContractV2,
    MeasurementContractV2Error,
    json_compatible_copy,
)

PREFLIGHT_DESIGN_TASK_KEY = "m4-v2-branch-identifiability-preflight-design"
PREFLIGHT_DESIGN_CAPABILITY = "m4_v2_branch_identifiability_preflight_design"
PREFLIGHT_DESIGN_COMPLETION_FACT = (
    "m4-v2-branch-identifiability-preflight-design:FROZEN"
)
PREFLIGHT_FIXTURE_FREEZE_TASK_KEY = (
    "m4-v2-branch-identifiability-fixture-freeze"
)
PREFLIGHT_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-v2-branch-preflight-design-source-contract-v1.json"
)

_UNRESOLVED_VALUES = frozenset(
    {
        "UNRESOLVED_PENDING_PREFLIGHT",
        "DESIGN_ONLY_NOT_IMPLEMENTED",
        "IMPLEMENTED_REQUIRES_V2_PREFLIGHT",
        "IMPLEMENTED_REQUIRES_JOINT_PREFLIGHT",
    }
)


@dataclass(frozen=True)
class BranchPreflightDesignRun:
    branch_contracts: tuple[Mapping[str, Any], ...]
    cross_branch_contract: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (*self.branch_contracts, self.cross_branch_contract, self.completion)


class BranchPreflightDesignError(RuntimeError):
    pass


def load_preflight_source_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BranchPreflightDesignError(
            f"preflight_design_source_contract_unreadable:{path}"
        ) from exc
    if not isinstance(payload, dict):
        raise BranchPreflightDesignError(
            "preflight_design_source_contract_invalid"
        )
    entries = payload.get("source_entries")
    if (
        payload.get("schema_version")
        != "dehps-m4-v2-branch-preflight-source-contract.v1"
        or payload.get("artifact_type")
        != "m4_v2_branch_preflight_source_contract"
        or payload.get("contract_key")
        != "M4_V2_BRANCH_PREFLIGHT_DESIGN_SOURCE"
        or payload.get("result_blind") is not True
        or payload.get("historical_outcomes_read") is not False
        or payload.get("statistical_results_read") is not False
        or payload.get("evidence_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or not entries
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain="dehps.m4.v2.branch-preflight-source-set.v1",
        )
    ):
        raise BranchPreflightDesignError(
            "preflight_design_source_contract_invalid"
        )
    paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise BranchPreflightDesignError(
                "preflight_design_source_entry_invalid"
            )
        relative = str(entry.get("path") or "")
        digest = str(entry.get("content_sha256") or "")
        parsed = Path(relative)
        if (
            not relative
            or parsed.is_absolute()
            or ".." in parsed.parts
            or parsed.as_posix() != relative
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or relative in paths
        ):
            raise BranchPreflightDesignError(
                "preflight_design_source_entry_invalid"
            )
        paths.add(relative)
    return payload


def verify_preflight_source_bytes(
    *,
    root_dir: Path,
    contract: Mapping[str, Any],
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise BranchPreflightDesignError(
                f"preflight_design_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise BranchPreflightDesignError(
                f"preflight_design_source_modified:{relative}"
            )


def build_branch_preflight_design_artifacts(
    contract: MeasurementContractV2,
    *,
    design_execution_artifact_digest: str,
    design_replay_execution_artifact_digest: str,
    gate_compiler_replay_digest: str,
    execution_id: str,
    git_commit: str,
) -> BranchPreflightDesignRun:
    for name, digest in (
        ("design execution", design_execution_artifact_digest),
        ("design replay execution", design_replay_execution_artifact_digest),
        ("gate compiler replay", gate_compiler_replay_digest),
    ):
        if len(digest) != 64:
            raise BranchPreflightDesignError(f"{name} digest is invalid")

    gate = contract.payload["gate_compiler_contract"]
    role_rows = contract.payload["mechanism_role_contract"]["matrix"]
    common_parents = (
        contract.artifact_digest,
        design_execution_artifact_digest,
        design_replay_execution_artifact_digest,
        gate_compiler_replay_digest,
    )
    branch_contracts: list[Mapping[str, Any]] = []
    unresolved_by_branch: dict[str, list[dict[str, str]]] = {}
    for branch_id in BRANCH_IDS:
        branch = contract.branch(branch_id)
        roles = [
            {
                "mechanism_id": row["mechanism_id"],
                "implementation_status": row["implementation_status"],
                "branch_role": row["roles"][branch_id],
            }
            for row in role_rows
        ]
        unresolved = _unresolved_markers(
            {
                "estimand": branch,
                "mechanism_roles": roles,
            }
        )
        unresolved_by_branch[branch_id] = unresolved
        branch_contracts.append(
            _artifact(
                schema_version=(
                    "dehps-m4-v2-branch-identifiability-preflight-design.v1"
                ),
                artifact_type="m4_v2_branch_identifiability_preflight_design",
                body={
                    "status": "FROZEN_DESIGN",
                    "measurement_contract_v2_digest": contract.artifact_digest,
                    "branch_id": branch_id,
                    "branch_order_index": BRANCH_IDS.index(branch_id),
                    "estimand_digest": contract.estimand_digest(branch_id),
                    "legal_domain": contract.payload["legal_domain"],
                    "estimand": branch,
                    "mechanism_roles": roles,
                    "validity_checks": gate["validity_checks"],
                    "measurement_acceptance_checks": gate[
                        "measurement_acceptance_checks"
                    ],
                    "identifiability_status_values": gate[
                        "branch_report_provenance_contract"
                    ]["identifiability_preflight_status_values"],
                    "unresolved_contract_markers": unresolved,
                    "preflight_execution_status": "NOT_RUN",
                    "identifiability_preflight_status": None,
                    "formal_execution_allowed": False,
                    "historical_outcomes_read": False,
                    "statistical_results_read": False,
                    "evidence_created": False,
                    "decision_credit": False,
                    "production_action": "none",
                },
                parent_digests=common_parents,
                domain=f"dehps.m4.v2.branch-preflight-design.{branch_id}.v1",
            )
        )

    cross_branch = _artifact(
        schema_version="dehps-m4-v2-cross-branch-preflight-design.v1",
        artifact_type="m4_v2_cross_branch_preflight_design",
        body={
            "status": "FROZEN_DESIGN",
            "measurement_contract_v2_digest": contract.artifact_digest,
            "required_branch_order": list(BRANCH_IDS),
            "branch_preflight_design_digests": [
                item["artifact_digest"] for item in branch_contracts
            ],
            "no_duplicate_credit_invariants": contract.payload[
                "estimand_contract"
            ]["no_duplicate_credit_invariants"],
            "branch_report_provenance_contract": gate[
                "branch_report_provenance_contract"
            ],
            "statistical_input_contract": gate["statistical_input_contract"],
            "result_blind_freeze": contract.payload["result_blind_freeze"],
            "unresolved_contract_markers_by_branch": unresolved_by_branch,
            "preflight_result_count": 0,
            "formal_execution_allowed": False,
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "production_action": "none",
        },
        parent_digests=(
            *common_parents,
            *(str(item["artifact_digest"]) for item in branch_contracts),
        ),
        domain="dehps.m4.v2.cross-branch-preflight-design.v1",
    )
    completion = _artifact(
        schema_version="dehps-m4-v2-branch-preflight-design-completion.v1",
        artifact_type="m4_v2_branch_preflight_design_completion",
        body={
            "status": "COMPLETE",
            "execution_id": execution_id,
            "git_commit": git_commit,
            "measurement_contract_v2_digest": contract.artifact_digest,
            "branch_preflight_design_digests": [
                item["artifact_digest"] for item in branch_contracts
            ],
            "cross_branch_preflight_design_digest": cross_branch[
                "artifact_digest"
            ],
            "completion_fact": PREFLIGHT_DESIGN_COMPLETION_FACT,
            "branch_design_count": len(branch_contracts),
            "preflight_execution_count": 0,
            "preflight_result_count": 0,
            "actual_fold_count": 0,
            "formal_branch_runs_executed": 0,
            "historical_outcomes_read": False,
            "p2_6_1_partial_statistical_results_read": False,
            "p2_6_3_statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_increment": 0,
            "next_consumer": PREFLIGHT_FIXTURE_FREEZE_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(
            *common_parents,
            *(str(item["artifact_digest"]) for item in branch_contracts),
            str(cross_branch["artifact_digest"]),
        ),
        domain="dehps.m4.v2.branch-preflight-design-completion.v1",
    )
    return BranchPreflightDesignRun(
        branch_contracts=tuple(branch_contracts),
        cross_branch_contract=cross_branch,
        completion=completion,
    )


def _unresolved_markers(value: Any, *, path: str = "$") -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    if isinstance(value, Mapping):
        for key in sorted(value):
            matches.extend(
                _unresolved_markers(value[key], path=f"{path}.{key}")
            )
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            matches.extend(
                _unresolved_markers(item, path=f"{path}[{index}]")
            )
    elif isinstance(value, str) and value in _UNRESOLVED_VALUES:
        matches.append({"path": path, "value": value})
    return matches


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
    domain: str,
) -> dict[str, Any]:
    json_body = json_compatible_copy(body)
    if not isinstance(json_body, dict):
        raise MeasurementContractV2Error(
            "measurement_v2_preflight_design_invalid",
            "artifact body must be an object",
        )
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
