from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

from .m4_p3_result_blind_design import M4_P3_STRUCTURAL_UTILITY_GOAL_KEY

M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_TASK_KEY = (
    "m4-p3-result-blind-structural-utility-preregistration"
)
M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_CAPABILITY = (
    "m4_p3_result_blind_structural_utility_preregistration"
)
M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_COMPLETION_FACT = (
    "m4-p3-result-blind-structural-utility-preregistration:COMPLETE"
)
M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY = (
    "m4-p3-result-blind-structural-utility-blind-generator-and-walk-forward"
)
M4_P3_STRUCTURAL_UTILITY_EXECUTION_APPROVED_EVENT = (
    "research-contract:m4-p3-result-blind-structural-utility-"
    "blind-generator-and-walk-forward:approved"
)
M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/"
    "m4-p3-result-blind-structural-utility-preregistration-source-v1.json"
)

RESEARCH_REQUEST_KEY = (
    "research-m4-p3-result-blind-structural-utility-preregistration-round-117-20260810"
)
RESEARCH_REQUEST_ID = 449
RESEARCH_EXECUTION_ID = 370
RESEARCH_PARENT_REQUEST_ID = 448
RESEARCH_CONTEXT_FINGERPRINT = (
    "12ce0a5ba65d2d9ff1d3bebe43792bb6671aba9f2c24f2a572aa51e987fc9bb3"
)
RESEARCH_PREREGISTRATION_DIGEST = (
    "407abd9dbedee32d5bca0456ae3018b5fae52720107ea895671e31ce360e6631"
)
RESEARCH_CONTRACT_DOMAIN = (
    "dehps.m4-p3.result-blind-structural-utility-preregistration-research-contract.v1"
)

PARENT_TASK_KEY = "prediction-v2-balanced-design-structural-utility-research-intake"
PARENT_CAPABILITY = "m4_p3_result_blind_structural_utility_design"
PARENT_EXECUTION_ID = "887d67dd0475f5ea0580c8c10818354b7a1196434768371b4d0276119de64f83"
PARENT_EXECUTION_DIGEST = (
    "c878b21f96e8e573158c0dfaf3d5c9ec020950390351920e745ce2e5ee5317db"
)
PARENT_DESIGN_DIGEST = (
    "ffbbc6603d472e736dfbc9f18598a5b4e8cc157991d303887614ef28891a163d"
)
PARENT_HANDOFF_DIGEST = (
    "251d248cfaace23106b33c656a6f05b7d9a9e85e0ede8d8d7844feab42c7c4cc"
)
PARENT_COMPLETION_DIGEST = (
    "02f16593f194d5697054dba433f37a55d45cebb24c87687c54f44dd8ff9a0869"
)
PARENT_COMPLETED_EVENT_DIGEST = (
    "27f672e4f598d9b432888415fcc187b70ff10193406c210050168e83ebf35f34"
)
PARENT_MANIFEST_DIGEST = (
    "12fc511be6f87bc99eca268b54d4900fdd1831af9b9ad6320d343368b98fdbdc"
)
PARENT_TASK_DIGEST = "34c1efc7ddbef7505cf880509320536ae4801d3ef1188375371d084cb94714b4"
PARENT_REGISTRATIONS = {
    "m4_p3_result_blind_structural_utility_design": (
        "50f8fd8e7e871ec2a60c0af36e7369ccfe5ce73a91176d31f5cfcb9998b50d41",
        PARENT_DESIGN_DIGEST,
        "dehps-m4-p3-result-blind-structural-utility-design.v1",
    ),
    "m4_p3_result_blind_structural_utility_preregistration_handoff": (
        "5d38dec0572f340832c2cad9a1261410fb881e534f71a0fd66cc57827bf4098c",
        PARENT_HANDOFF_DIGEST,
        "dehps-m4-p3-result-blind-structural-utility-preregistration-handoff.v1",
    ),
    "m4_p3_result_blind_structural_utility_design_completion": (
        "76b350e46ec9487aff74f81eada9deb432c6bb7ff827b9f365ad489d9ca4bb21",
        PARENT_COMPLETION_DIGEST,
        "dehps-m4-p3-result-blind-structural-utility-design-completion.v1",
    ),
    "research_os_mainline_execution": (
        "06d32ac6139327a51bdbfc523754f01bc73d72a5eea67f7ccbf988693fc23f48",
        PARENT_EXECUTION_DIGEST,
        "dehps-research-os-mainline-execution.v1",
    ),
}

_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/structural_utility/"
    "m4_p3_result_blind_preregistration.py"
)
_PREREGISTRATION_DOMAIN = (
    "dehps.m4-p3.result-blind-structural-utility-preregistration.v1"
)
_HANDOFF_DOMAIN = "dehps.m4-p3.result-blind-structural-utility-execution-handoff.v1"
_COMPLETION_DOMAIN = (
    "dehps.m4-p3.result-blind-structural-utility-preregistration-completion.v1"
)


class M4P3ResultBlindStructuralUtilityPreregistrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class M4P3ResultBlindStructuralUtilityPreregistrationRun:
    preregistration: Mapping[str, Any]
    execution_handoff: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return self.preregistration, self.execution_handoff, self.completion


def load_m4_p3_result_blind_structural_utility_preregistration_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise M4P3ResultBlindStructuralUtilityPreregistrationError(
            f"m4_p3_structural_utility_preregistration_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-p3-result-blind-structural-utility-preregistration-source.v1"
        or payload.get("artifact_type")
        != "m4_p3_result_blind_structural_utility_preregistration_source"
        or payload.get("contract_key")
        != "M4_P3_RESULT_BLIND_STRUCTURAL_UTILITY_PREREGISTRATION_SOURCE"
        or payload.get("research_request_key") != RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != RESEARCH_REQUEST_ID
        or payload.get("research_execution_id") != RESEARCH_EXECUTION_ID
        or payload.get("research_context_fingerprint") != RESEARCH_CONTEXT_FINGERPRINT
        or payload.get("research_preregistration_digest")
        != RESEARCH_PREREGISTRATION_DIGEST
        or payload.get("result_blind") is not True
        or payload.get("execution_authorized") is not False
        or payload.get("source_set_digest")
        != config_digest({"source_entries": entries})
        or payload.get("artifact_digest")
        != config_digest(
            {key: value for key, value in payload.items() if key != "artifact_digest"}
        )
        or not isinstance(entries, list)
        or len(entries) != 1
        or entries[0].get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entries[0].get("content_sha256"))
    ):
        raise M4P3ResultBlindStructuralUtilityPreregistrationError(
            "m4_p3_structural_utility_preregistration_source_invalid"
        )
    return payload


def verify_m4_p3_result_blind_structural_utility_preregistration_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    entry = contract["source_entries"][0]
    relative = str(entry["path"])
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise M4P3ResultBlindStructuralUtilityPreregistrationError(
            f"m4_p3_structural_utility_preregistration_source_missing:{relative}"
        )
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
        raise M4P3ResultBlindStructuralUtilityPreregistrationError(
            f"m4_p3_structural_utility_preregistration_source_modified:{relative}"
        )


def build_m4_p3_result_blind_structural_utility_preregistration_artifacts(
    *,
    source_contract: Mapping[str, Any],
    research_request: Mapping[str, Any],
    research_execution: Mapping[str, Any],
    completed_event: Mapping[str, Any],
    parent_registrations: Sequence[Mapping[str, Any]],
) -> M4P3ResultBlindStructuralUtilityPreregistrationRun:
    preregistered = _validate_research_contract(research_request, research_execution)
    _validate_parent_projection(completed_event, parent_registrations)
    source_digest = str(source_contract["artifact_digest"])
    parent_digests = (
        source_digest,
        RESEARCH_PREREGISTRATION_DIGEST,
        PARENT_EXECUTION_DIGEST,
        PARENT_DESIGN_DIGEST,
        PARENT_HANDOFF_DIGEST,
        PARENT_COMPLETION_DIGEST,
    )
    zero_work = _zero_work()
    boundary = dict(preregistered["claim_and_route_boundary"])
    preregistration = _artifact(
        schema_version=(
            "dehps-m4-p3-result-blind-structural-utility-preregistration.v1"
        ),
        artifact_type="m4_p3_result_blind_structural_utility_preregistration",
        body={
            "status": "FROZEN_BEFORE_GENERATION",
            "goal_key": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
            "research_request_key": RESEARCH_REQUEST_KEY,
            "research_request_id": RESEARCH_REQUEST_ID,
            "research_execution_id": RESEARCH_EXECUTION_ID,
            "research_context_fingerprint": RESEARCH_CONTEXT_FINGERPRINT,
            "research_preregistration_digest": RESEARCH_PREREGISTRATION_DIGEST,
            "incidental_prior_structural_values_observed_during_repository_discovery": True,
            "previous_structural_result_values_used_to_select_any_choice": False,
            "frozen_contract": preregistered,
            "generator_or_evaluation_execution_authorized": False,
            "next_consumer": M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
            **zero_work,
            **boundary,
        },
        parent_digests=parent_digests,
        domain=_PREREGISTRATION_DOMAIN,
    )
    handoff = _artifact(
        schema_version=(
            "dehps-m4-p3-result-blind-structural-utility-execution-handoff.v1"
        ),
        artifact_type=("m4_p3_result_blind_structural_utility_blind_execution_handoff"),
        body={
            "status": "COMPLETE",
            "goal_key": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
            "preregistration_artifact_digest": preregistration["artifact_digest"],
            "research_preregistration_digest": RESEARCH_PREREGISTRATION_DIGEST,
            "required_research_event": M4_P3_STRUCTURAL_UTILITY_EXECUTION_APPROVED_EVENT,
            "fold_count": preregistered["fold_manifest"]["fold_count"],
            "fold_manifest_digest": preregistered["fold_manifest"][
                "fold_manifest_digest"
            ],
            "portfolio_budget": preregistered["constructive_invariants"][
                "portfolio_size"
            ],
            "arm_keys": [item["arm"] for item in preregistered["arms"]],
            "confirmatory_coordinate_keys": [
                item["metric"] for item in preregistered["confirmatory_coordinates"]
            ],
            "random_seed_root": preregistered["arms"][0]["seed_root"],
            "bootstrap_seed_root": preregistered["paired_inference"][
                "bootstrap_seed_root"
            ],
            "execution_authorized": False,
            "next_consumer": M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
            **zero_work,
            **boundary,
        },
        parent_digests=(*parent_digests, str(preregistration["artifact_digest"])),
        domain=_HANDOFF_DOMAIN,
    )
    completion = _artifact(
        schema_version=(
            "dehps-m4-p3-result-blind-structural-utility-preregistration-completion.v1"
        ),
        artifact_type=(
            "m4_p3_result_blind_structural_utility_preregistration_completion"
        ),
        body={
            "status": "COMPLETE",
            "completion_fact": M4_P3_STRUCTURAL_UTILITY_PREREGISTRATION_COMPLETION_FACT,
            "source_contract_digest": source_digest,
            "research_preregistration_digest": RESEARCH_PREREGISTRATION_DIGEST,
            "parent_execution_digest": PARENT_EXECUTION_DIGEST,
            "parent_design_digest": PARENT_DESIGN_DIGEST,
            "parent_handoff_digest": PARENT_HANDOFF_DIGEST,
            "parent_completion_digest": PARENT_COMPLETION_DIGEST,
            "preregistration_artifact_digest": preregistration["artifact_digest"],
            "execution_handoff_digest": handoff["artifact_digest"],
            "registered_child_count": 3,
            "next_consumer": M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
            **zero_work,
            **boundary,
        },
        parent_digests=(
            source_digest,
            RESEARCH_PREREGISTRATION_DIGEST,
            str(preregistration["artifact_digest"]),
            str(handoff["artifact_digest"]),
        ),
        domain=_COMPLETION_DOMAIN,
    )
    return M4P3ResultBlindStructuralUtilityPreregistrationRun(
        preregistration=preregistration,
        execution_handoff=handoff,
        completion=completion,
    )


def replay_m4_p3_result_blind_structural_utility_preregistration(
    **kwargs: Any,
) -> tuple[M4P3ResultBlindStructuralUtilityPreregistrationRun, dict[str, Any]]:
    run = build_m4_p3_result_blind_structural_utility_preregistration_artifacts(
        **kwargs
    )
    return run, {
        "schema_version": (
            "dehps-m4-p3-result-blind-structural-utility-preregistration-replay.v1"
        ),
        "status": "REPLAY_VERIFIED",
        "same_registered_content": True,
        "workload_rerun": False,
        "portfolios_generated": 0,
        "folds_replayed": 0,
        "target_draw_rows_read": 0,
        "metric_results_read": 0,
        "previous_structural_result_values_used_to_select_any_choice": 0,
        "next_consumer": M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
    }


def _validate_research_contract(
    request: Mapping[str, Any], execution: Mapping[str, Any]
) -> Mapping[str, Any]:
    payload = request.get("payload")
    preregistered = (
        payload.get("preregistration") if isinstance(payload, Mapping) else None
    )
    metadata = request.get("metadata")
    result = execution.get("result")
    if (
        request.get("request_key") != RESEARCH_REQUEST_KEY
        or request.get("id") != RESEARCH_REQUEST_ID
        or request.get("request_type") != "research_scheduler_request"
        or request.get("status") != "completed"
        or request.get("parent_request_id") != RESEARCH_PARENT_REQUEST_ID
        or not isinstance(metadata, Mapping)
        or metadata.get("result_blind") is not True
        or metadata.get("result_aware") is not False
        or metadata.get(
            "incidental_prior_structural_values_observed_during_repository_discovery"
        )
        is not True
        or metadata.get("previous_structural_result_values_used_to_select_any_choice")
        is not False
        or not isinstance(preregistered, Mapping)
        or payload.get("context_fingerprint") != RESEARCH_CONTEXT_FINGERPRINT
        or canonical_digest(preregistered, domain=RESEARCH_CONTRACT_DOMAIN)
        != RESEARCH_PREREGISTRATION_DIGEST
        or execution.get("id") != RESEARCH_EXECUTION_ID
        or execution.get("request_id") != RESEARCH_REQUEST_ID
        or execution.get("status") != "completed"
        or not isinstance(result, Mapping)
        or result.get("contract_status") != "FROZEN_BEFORE_GENERATION"
        or result.get("fold_count") != 90
        or result.get("portfolios_generated") != 0
        or result.get("folds_executed") != 0
        or result.get("metric_results_read") != 0
        or result.get("target_draw_rows_read") != 0
        or result.get("previous_structural_result_values_used_to_select_any_choice")
        != 0
        or result.get("mainline_execution_authorized") is not False
    ):
        raise M4P3ResultBlindStructuralUtilityPreregistrationError(
            "m4_p3_structural_utility_research_preregistration_identity_changed"
        )
    return preregistered


def _validate_parent_projection(
    event: Mapping[str, Any], registrations: Sequence[Mapping[str, Any]]
) -> None:
    expected_event = {
        "event_digest": PARENT_COMPLETED_EVENT_DIGEST,
        "execution_id": PARENT_EXECUTION_ID,
        "control_plane_key": "m4-information-theory-mainline",
        "manifest_digest": PARENT_MANIFEST_DIGEST,
        "task_digest": PARENT_TASK_DIGEST,
        "task_key": PARENT_TASK_KEY,
        "capability": PARENT_CAPABILITY,
        "event_type": "completed",
        "sequence": 1,
    }
    if dict(event) != expected_event or len(registrations) != len(PARENT_REGISTRATIONS):
        raise M4P3ResultBlindStructuralUtilityPreregistrationError(
            "m4_p3_structural_utility_preregistration_parent_identity_changed"
        )
    observed: dict[str, tuple[str, str, str]] = {}
    for item in registrations:
        if (
            item.get("execution_id") != PARENT_EXECUTION_ID
            or item.get("control_plane_key") != "m4-information-theory-mainline"
            or item.get("task_key") != PARENT_TASK_KEY
            or item.get("task_digest") != PARENT_TASK_DIGEST
        ):
            raise M4P3ResultBlindStructuralUtilityPreregistrationError(
                "m4_p3_structural_utility_preregistration_parent_registration_changed"
            )
        observed[str(item.get("artifact_type"))] = (
            str(item.get("registration_digest")),
            str(item.get("artifact_digest")),
            str(item.get("schema_version")),
        )
    if observed != PARENT_REGISTRATIONS:
        raise M4P3ResultBlindStructuralUtilityPreregistrationError(
            "m4_p3_structural_utility_preregistration_parent_registration_changed"
        )


def _zero_work() -> dict[str, Any]:
    return {
        "result_blind": True,
        "portfolios_generated": 0,
        "folds_executed": 0,
        "random_replicates_executed": 0,
        "metric_results_read": 0,
        "target_draw_rows_read": 0,
        "bootstrap_resamples_executed": 0,
        "historical_feature_snapshots_materialized": 0,
        "previous_structural_result_values_used_to_select_any_choice_count": 0,
    }


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
    domain: str,
) -> dict[str, Any]:
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
