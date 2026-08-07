from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

from .contracts import json_compatible_copy
from .marginal_static_fixtures import (
    FIXTURE_ORDER,
    MARGINAL_STATIC_FIXTURE_FREEZE_COMPLETION_FACT,
)

MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY = (
    "m4-v2-marginal-static-measurement-health-design"
)
MARGINAL_STATIC_HEALTH_DESIGN_CAPABILITY = (
    "m4_v2_marginal_static_measurement_health_design"
)
MARGINAL_STATIC_HEALTH_DESIGN_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-health-design:FROZEN"
)
MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-health-execution"
)
MARGINAL_STATIC_HEALTH_DESIGN_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-v2-marginal-static-health-design-source-v1.json"
)

_EXPECTED_REQUEST_KEY = "research-m4-v2-marginal-static-health-design-round-41-20260808"
_EXPECTED_SCALES = (
    {"scale_id": "FORWARD_61", "evaluation_issues": 61, "sequence_issues": 961},
    {
        "scale_id": "HISTORICAL_2581",
        "evaluation_issues": 2581,
        "sequence_issues": 3481,
    },
)
_EXPECTED_LOCAL_TARGETS = (0.001, 0.01, 0.05)


class MarginalStaticHealthDesignError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarginalStaticHealthDesignRun:
    workload: Mapping[str, Any]
    inference: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (self.workload, self.inference, self.completion)


def load_marginal_static_health_design_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticHealthDesignError(
            f"marginal_static_health_design_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-health-design-source.v1"
        or payload.get("artifact_type") != "m4_v2_marginal_static_health_design_source"
        or payload.get("contract_key") != "M4_V2_MARGINAL_STATIC_HEALTH_DESIGN_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_REQUEST_KEY
        or payload.get("research_request_id") != 318
        or payload.get("research_execution_id") != 239
        or payload.get("result_blind") is not True
        or payload.get("generated_issues") != 0
        or payload.get("synthetic_replicates") != 0
        or payload.get("historical_outcomes_read") is not False
        or payload.get("statistical_results_read") is not False
        or payload.get("evidence_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or not entries
        or not isinstance(frozen, dict)
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain=("dehps.m4.v2.marginal-static-health-design-source-set.v1"),
        )
    ):
        raise MarginalStaticHealthDesignError(
            "marginal_static_health_design_source_invalid"
        )
    paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise MarginalStaticHealthDesignError(
                "marginal_static_health_design_source_entry_invalid"
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
            raise MarginalStaticHealthDesignError(
                "marginal_static_health_design_source_entry_invalid"
            )
        paths.add(relative)
    _validate_frozen_contract(frozen)
    return payload


def verify_marginal_static_health_design_source_bytes(
    *,
    root_dir: Path,
    contract: Mapping[str, Any],
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MarginalStaticHealthDesignError(
                f"marginal_static_health_design_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise MarginalStaticHealthDesignError(
                f"marginal_static_health_design_source_modified:{relative}"
            )


def build_marginal_static_health_design_artifacts(
    *,
    source_contract: Mapping[str, Any],
    fixture_execution_artifact_digest: str,
    fixture_contracts: Sequence[Mapping[str, Any]],
    fixture_bundle: Mapping[str, Any],
    fixture_completion: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
) -> MarginalStaticHealthDesignRun:
    frozen = source_contract.get("frozen_contract")
    if not isinstance(frozen, Mapping):
        raise MarginalStaticHealthDesignError(
            "marginal_static_health_design_contract_missing"
        )
    _validate_frozen_contract(frozen)
    if len(fixture_execution_artifact_digest) != 64:
        raise MarginalStaticHealthDesignError(
            "marginal_static_health_design_parent_digest_invalid"
        )
    fixtures = tuple(fixture_contracts)
    fixture_ids = tuple(str(item.get("fixture_id") or "") for item in fixtures)
    fixture_digests = tuple(str(item.get("artifact_digest") or "") for item in fixtures)
    if (
        fixture_ids != FIXTURE_ORDER
        or len(set(fixture_digests)) != len(FIXTURE_ORDER)
        or any(len(digest) != 64 for digest in fixture_digests)
        or fixture_bundle.get("fixture_digests") != list(fixture_digests)
        or fixture_bundle.get("sampled_workload_status") != "NOT_FROZEN"
        or fixture_completion.get("completion_fact")
        != MARGINAL_STATIC_FIXTURE_FREEZE_COMPLETION_FACT
        or fixture_completion.get("fixture_bundle_digest")
        != fixture_bundle.get("artifact_digest")
        or fixture_completion.get("generated_issues") != 0
        or fixture_completion.get("synthetic_replicates") != 0
        or fixture_completion.get("historical_outcomes_read") is not False
    ):
        raise MarginalStaticHealthDesignError(
            "marginal_static_health_design_fixture_lineage_invalid"
        )

    source_digest = str(source_contract["artifact_digest"])
    parent_digests = (
        source_digest,
        fixture_execution_artifact_digest,
        *(str(item) for item in fixture_digests),
        str(fixture_bundle["artifact_digest"]),
        str(fixture_completion["artifact_digest"]),
    )
    workload_contract = frozen["workload"]
    workload = _artifact(
        schema_version="dehps-m4-v2-marginal-static-health-workload.v1",
        artifact_type="m4_v2_marginal_static_health_workload",
        body={
            "status": "FROZEN_DESIGN",
            "source_contract_digest": source_digest,
            "fixture_execution_artifact_digest": fixture_execution_artifact_digest,
            "fixture_digests": list(fixture_digests),
            "fixture_bundle_digest": fixture_bundle["artifact_digest"],
            "fixture_completion_digest": fixture_completion["artifact_digest"],
            "workload": workload_contract,
            "seed_contract": frozen["seed_contract"],
            "runtime_boundary": frozen["runtime_boundary"],
            "sampled_execution_status": "NOT_AUTHORIZED",
            "generated_issues": 0,
            "synthetic_replicates": 0,
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "production_action": "none",
        },
        parent_digests=parent_digests,
        domain="dehps.m4.v2.marginal-static-health-workload.v1",
    )
    inference = _artifact(
        schema_version="dehps-m4-v2-marginal-static-health-inference.v1",
        artifact_type="m4_v2_marginal_static_health_inference",
        body={
            "status": "FROZEN_DESIGN",
            "source_contract_digest": source_digest,
            "workload_digest": workload["artifact_digest"],
            "inference": frozen["inference"],
            "acceptance": frozen["acceptance"],
            "failure_condition": frozen["failure_condition"],
            "manual_or_partial_override": "forbidden",
            "sampled_execution_status": "NOT_AUTHORIZED",
            "interval_result_count": 0,
            "power_result_count": 0,
            "mde_result_count": 0,
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "production_action": "none",
        },
        parent_digests=(*parent_digests, str(workload["artifact_digest"])),
        domain="dehps.m4.v2.marginal-static-health-inference.v1",
    )
    completion = _artifact(
        schema_version="dehps-m4-v2-marginal-static-health-design-completion.v1",
        artifact_type="m4_v2_marginal_static_health_design_completion",
        body={
            "status": "COMPLETE",
            "execution_id": execution_id,
            "git_commit": git_commit,
            "source_contract_digest": source_digest,
            "workload_digest": workload["artifact_digest"],
            "inference_digest": inference["artifact_digest"],
            "completion_fact": MARGINAL_STATIC_HEALTH_DESIGN_COMPLETION_FACT,
            "planned_total_replicates": workload_contract["total_replicates"],
            "planned_total_generated_issues": workload_contract[
                "total_generated_issues_if_executed"
            ],
            "planned_total_outer_evaluation_issues": workload_contract[
                "total_outer_evaluation_issues_if_executed"
            ],
            "planned_execution_shards": workload_contract["execution_shards"],
            "generated_issues": 0,
            "synthetic_replicates": 0,
            "bootstrap_replicates_executed": 0,
            "formal_branch_runs_executed": 0,
            "actual_fold_count": 0,
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_increment": 0,
            "sampled_execution_status": "NOT_AUTHORIZED",
            "historical_execution_status": "NOT_AUTHORIZED",
            "next_consumer": MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(
            *parent_digests,
            str(workload["artifact_digest"]),
            str(inference["artifact_digest"]),
        ),
        domain="dehps.m4.v2.marginal-static-health-design-completion.v1",
    )
    return MarginalStaticHealthDesignRun(
        workload=workload,
        inference=inference,
        completion=completion,
    )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    workload = frozen.get("workload")
    inference = frozen.get("inference")
    acceptance = frozen.get("acceptance")
    seeds = frozen.get("seed_contract")
    runtime = frozen.get("runtime_boundary")
    if not all(
        isinstance(item, Mapping)
        for item in (workload, inference, acceptance, seeds, runtime)
    ):
        raise MarginalStaticHealthDesignError(
            "marginal_static_health_design_contract_invalid"
        )
    assert isinstance(workload, Mapping)
    assert isinstance(inference, Mapping)
    assert isinstance(acceptance, Mapping)
    assert isinstance(seeds, Mapping)
    assert isinstance(runtime, Mapping)
    scales = workload.get("scales")
    fixture_ids = workload.get("frozen_fixture_ids")
    targets = workload.get("local_marginal_power_targets_bits_per_issue")
    expected_generated = 3584 * (961 + 3481)
    expected_outer = 3584 * (61 + 2581)
    if (
        tuple(scales or ()) != _EXPECTED_SCALES
        or tuple(fixture_ids or ()) != FIXTURE_ORDER
        or tuple(targets or ()) != _EXPECTED_LOCAL_TARGETS
        or workload.get("minimum_training_issues") != 900
        or workload.get("replicates_per_fixture_scale_cell") != 512
        or workload.get("replicates_per_local_alternative_scale_cell") != 512
        or workload.get("base_fixture_replicates") != 4096
        or workload.get("local_alternative_replicates") != 3072
        or workload.get("total_replicates") != 7168
        or workload.get("total_generated_issues_if_executed") != expected_generated
        or workload.get("total_outer_evaluation_issues_if_executed") != expected_outer
        or workload.get("execution_shard_size") != 64
        or workload.get("execution_shards") != 112
        or inference.get("bootstrap_replicates") != 511
        or inference.get("primary_block_size") != 5
        or inference.get("sensitivity_block_sizes") != [3, 8, 13]
        or inference.get("confidence_level") != 0.95
        or inference.get("detection_alpha") != 0.05
        or acceptance.get("negative_control_false_positive_rate_max") != 0.075
        or acceptance.get("negative_control_wilson_upper_95_max") != 0.09
        or acceptance.get("absolute_score_bias_max_bits_per_issue") != 0.0025
        or acceptance.get("coverage_rate_interval") != [0.925, 0.975]
        or acceptance.get("practical_0_01_power_min") != 0.8
        or acceptance.get("strong_0_05_power_min") != 0.95
        or seeds.get("wall_clock_seed") is not False
        or seeds.get("worker_or_shard_identity_in_seed") is not False
        or runtime.get("database_reads_during_replicate") != 0
        or runtime.get("database_writes_during_replicate") != 0
        or runtime.get("csv_materialization") != "forbidden"
        or runtime.get("duplicate_raw_replay") != "forbidden"
        or runtime.get("routine_physical_checkpoint_scan") != "forbidden"
        or runtime.get("single_host_only") is not True
        or frozen.get("generated_issues") != 0
        or frozen.get("synthetic_replicates") != 0
        or frozen.get("historical_outcomes_read") is not False
        or frozen.get("statistical_results_read") is not False
        or frozen.get("evidence_created") is not False
        or frozen.get("next_consumer") != MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY
    ):
        raise MarginalStaticHealthDesignError(
            "marginal_static_health_design_contract_invalid"
        )


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
        raise MarginalStaticHealthDesignError(
            "marginal_static_health_design_artifact_invalid"
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
