from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.models import (
    ControlPlaneManifest,
    m4_v2_domain_digest,
    stable_hash,
)


class GlobalRoutingRecoveryV3Error(RuntimeError):
    pass


INPUT_MANIFEST_DIGEST = "b50a4c07ee75cd9e87842b8ad62846b6c37af23a17a9fc71e1e3610ce2e8c319"
INPUT_SNAPSHOT_DIGEST = "527494d7827f5160b844b8025c98acf420a135e8811a93157e4adca7ab509369"
OLD_TASK_KEY = "m4-v2-global-routing-recovery-v2"
RECOVERY_TASK_KEY = "m4-v2-global-routing-recovery-v3"
RECOVERY_COMPLETION_FACT = f"{RECOVERY_TASK_KEY}:COMPLETE"
OLD_TASK_DIGEST = "a2c26aa0c86d22065508b74a640f37b4cd5b2531368ed234294a30c31cfbcbca"
OLD_SOURCE_DIGEST = "24bfd16ee558f13ec2a50a30a8d903a11934fc128f996f370d78fdba9a4929ec"
OLD_EXECUTION_ID = "d8a6721e74a7d998298c3769d99e0e5fc0a1e947120df70d1db15a20c3d8bcfe"
OLD_EVENT_MANIFEST_DIGEST = "8d9ed3811969cb80979c51e2c27f451ca2c4b127d59a2c1a9e105127b68bb084"
OLD_STARTED_EVENT_DIGEST = "91da4dd4d4a092fab8949589f1405a8a4b725854fe51c281c8f08ff976703565"
OLD_FAILED_EVENT_DIGEST = "cd7e1e68006a1c63c085a81fd9a3f4aa9e357ae6cccc92db09cfcaef39717811"
P3_TASK_KEYS = (
    "m4-p3-strict-historical-walk-forward",
    "m4-p3-predictive-preregistration-freeze",
)
RECOVERY_LINEAGE = {
    "cause": (
        "execution_owner_required_child_artifact_as_last_parent_instead_of_"
        "exact_membership_in_real_multi_artifact_execution"
    ),
    "old_active_definition_digest": OLD_TASK_DIGEST,
    "old_event_manifest_digest": OLD_EVENT_MANIFEST_DIGEST,
    "old_execution_id": OLD_EXECUTION_ID,
    "old_failed_event": {"event_digest": OLD_FAILED_EVENT_DIGEST, "sequence": 1},
    "old_started_event": {"event_digest": OLD_STARTED_EVENT_DIGEST, "sequence": 0},
    "old_state": {
        "completion_classification": "INTEGRATED",
        "declared_status": "failed",
        "reason_code": "task_failed",
        "resolved_status": "failed",
        "superseded_by_task_digest": None,
    },
    "old_task_key": OLD_TASK_KEY,
    "schema_version": "dehps-m4-v2-global-routing-recovery-lineage.v3",
    "successor_task_key": RECOVERY_TASK_KEY,
}
RECOVERY_LINEAGE_DIGEST = stable_hash(RECOVERY_LINEAGE)

GLOBAL_SOURCE_PATH = "configs/research-os/m4-v2-global-routing-source-v1.json"
GLOBAL_SOURCE_SCHEMA = "dehps-m4-v2-global-routing-source-contract.v1"
GLOBAL_SOURCE_ARTIFACT_TYPE = "m4_v2_global_routing_source_contract"
GLOBAL_GOVERNANCE_METADATA_DIGEST = (
    "6dba42d77db1334f6bca77cb1460f166e2070f40ffc319948e8ac7db3442820e"
)
GLOBAL_SOURCE_ENTRIES = (
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/routing.py",
    "apps/worker-python/dehps/research_os/supervisor.py",
    "apps/worker-python/dehps/research_os/information_theory/progress.py",
    "apps/worker-python/scripts/build_m4_v2_global_routing_manifest.py",
    "apps/worker-python/scripts/build_m4_v2_global_routing_recovery_manifest.py",
    "apps/worker-python/dehps/research_os/control_plane.py",
    "apps/worker-python/dehps/research_os/models.py",
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/migration.py",
    "apps/worker-python/scripts/build_m4_v2_global_routing_recovery_v2_manifest.py",
    "apps/worker-python/scripts/build_m4_v2_global_routing_recovery_v3_manifest.py",
)
SOURCE_SET_DOMAIN = "dehps.m4.v2.successor-source-set.v1"
SOURCE_CONTRACT_DOMAIN = "dehps.m4.v2.successor-source-contract.v1"
GLOBAL_SOURCE_FIELDS = {
    "schema_version",
    "artifact_type",
    "artifact_digest",
    "measurement_contract_key",
    "measurement_contract_digest",
    "source_fact",
    "research_context_fingerprint",
    "source_entries",
    "source_set_digest",
    "future_artifact_digests",
    "production_action",
    "governance_bindings",
    "failed_engineering_predecessor_binding",
    "governance_digest_reference_contract",
}


def _digest(value: object, name: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise GlobalRoutingRecoveryV3Error(f"{name}_invalid")
    return value


def validate_global_source_contract(
    source: Mapping[str, Any], *, root_dir: Path
) -> str:
    payload = deepcopy(dict(source))
    entries = payload.get("source_entries")
    if (
        set(payload) != GLOBAL_SOURCE_FIELDS
        or payload.get("schema_version") != GLOBAL_SOURCE_SCHEMA
        or payload.get("artifact_type") != GLOBAL_SOURCE_ARTIFACT_TYPE
        or payload.get("measurement_contract_key") != "M4_MEASUREMENT_CONTRACT_V2"
        or payload.get("measurement_contract_digest")
        != "a0a367c99d7646cadc162bd9ceb0d5d73481cd7c26656bf02b40a99d9180095b"
        or payload.get("source_fact")
        != "m4-v2-global-routing-contract:M4_MEASUREMENT_CONTRACT_V2:FROZEN"
        or payload.get("research_context_fingerprint")
        != "9eb546ff2bc2c7aa84d7ed78635fb5dec31c1aa8c5864768da57d8a7f1809ebf"
        or payload.get("future_artifact_digests") is not None
        or payload.get("production_action") != "none"
        or stable_hash(
            {
                key: payload.get(key)
                for key in (
                    "measurement_contract_key",
                    "measurement_contract_digest",
                    "source_fact",
                    "research_context_fingerprint",
                    "future_artifact_digests",
                    "production_action",
                    "governance_bindings",
                    "failed_engineering_predecessor_binding",
                    "governance_digest_reference_contract",
                )
            }
        )
        != GLOBAL_GOVERNANCE_METADATA_DIGEST
        or not isinstance(entries, list)
        or tuple(item.get("path") for item in entries if isinstance(item, Mapping))
        != GLOBAL_SOURCE_ENTRIES
    ):
        raise GlobalRoutingRecoveryV3Error("global_recovery_v3_source_shape_changed")
    verified: list[dict[str, str]] = []
    expected_root = root_dir.resolve()
    for expected_path, item in zip(GLOBAL_SOURCE_ENTRIES, entries, strict=True):
        if not isinstance(item, Mapping) or set(item) != {"path", "sha256"}:
            raise GlobalRoutingRecoveryV3Error("global_recovery_v3_source_entry_changed")
        absolute = (expected_root / expected_path).resolve()
        observed = str(item["sha256"])
        if (
            absolute != expected_root / expected_path
            or not absolute.is_file()
            or hashlib.sha256(absolute.read_bytes()).hexdigest() != observed
        ):
            raise GlobalRoutingRecoveryV3Error("global_recovery_v3_source_bytes_changed")
        verified.append({"path": expected_path, "sha256": observed})
    source_set_digest = m4_v2_domain_digest(
        {"source_entries": verified}, domain=SOURCE_SET_DOMAIN
    )
    identity = dict(payload)
    artifact_digest = _digest(identity.pop("artifact_digest", None), "source_artifact")
    if (
        payload.get("source_set_digest") != source_set_digest
        or m4_v2_domain_digest(identity, domain=SOURCE_CONTRACT_DOMAIN)
        != artifact_digest
    ):
        raise GlobalRoutingRecoveryV3Error("global_recovery_v3_source_identity_changed")
    return artifact_digest


def build_manifest(
    live_payload: Mapping[str, Any], *, global_source_contract_digest: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_digest = _digest(global_source_contract_digest, "global_source_contract_digest")
    if source_digest == OLD_SOURCE_DIGEST:
        raise GlobalRoutingRecoveryV3Error("global_recovery_v3_source_not_resealed")
    manifest = ControlPlaneManifest.from_dict(deepcopy(dict(live_payload)))
    snapshot = ResearchOSControlPlane().resolve(manifest)
    if manifest.artifact_digest != INPUT_MANIFEST_DIGEST:
        raise GlobalRoutingRecoveryV3Error("global_recovery_v3_input_manifest_changed")
    if snapshot.snapshot_digest != INPUT_SNAPSHOT_DIGEST or snapshot.ready_queue:
        raise GlobalRoutingRecoveryV3Error("global_recovery_v3_input_resolution_changed")
    tasks = {task.task_key: task for task in manifest.tasks}
    if len(tasks) != len(manifest.tasks) or RECOVERY_TASK_KEY in tasks:
        raise GlobalRoutingRecoveryV3Error("global_recovery_v3_task_identity_conflict")
    old = tasks.get(OLD_TASK_KEY)
    if old is None or old.artifact_digest != OLD_TASK_DIGEST:
        raise GlobalRoutingRecoveryV3Error("global_recovery_v3_old_definition_changed")
    old_state = manifest.task_state_by_digest[old.artifact_digest]
    if (
        old.input_artifact_digests != (OLD_SOURCE_DIGEST,)
        or old_state.declared_status.value != "failed"
        or old_state.completion_classification is None
        or old_state.completion_classification.value != "INTEGRATED"
        or old_state.superseded_by_task_digest is not None
    ):
        raise GlobalRoutingRecoveryV3Error("global_recovery_v3_old_state_changed")

    normalized = manifest.to_dict(include_digest=False)
    old_payload = next(item for item in normalized["tasks"] if item["task_key"] == OLD_TASK_KEY)
    successor_payload = deepcopy(old_payload)
    successor_payload["task_key"] = RECOVERY_TASK_KEY
    successor_payload["input_artifact_digests"] = [source_digest]
    successor_payload["status"] = "draft"
    successor_payload["completion_classification"] = "INTEGRATION_PENDING"
    successor_payload["superseded_by_task_digest"] = None
    metric = successor_payload["metric_contract"]
    if metric.get("completion_fact") != f"{OLD_TASK_KEY}:COMPLETE":
        raise GlobalRoutingRecoveryV3Error("global_recovery_v3_old_completion_fact_changed")
    metric["completion_fact"] = RECOVERY_COMPLETION_FACT
    downstream = metric["mainline_integration"]["downstream_artifacts"]
    if downstream[2] != f"{OLD_TASK_KEY}:COMPLETE":
        raise GlobalRoutingRecoveryV3Error("global_recovery_v3_old_downstream_fact_changed")
    downstream[2] = RECOVERY_COMPLETION_FACT
    old_route_path = (
        f"runtime/research-os/mainline/tasks/{OLD_TASK_KEY}/"
        "{execution_id}/artifacts/global-routing-decision/{artifact_digest}/decision.json"
    )
    if metric.get("route_artifact_path_template") != old_route_path:
        raise GlobalRoutingRecoveryV3Error("global_recovery_v3_old_route_path_changed")
    metric["route_artifact_path_template"] = old_route_path.replace(
        OLD_TASK_KEY, RECOVERY_TASK_KEY, 1
    )
    metric["recovery_lineage"] = deepcopy(RECOVERY_LINEAGE)
    metric["recovery_lineage_digest"] = RECOVERY_LINEAGE_DIGEST

    from dehps.research_os.models import Task

    successor_task = Task.from_dict(successor_payload)
    old_payload["superseded_by_task_digest"] = successor_task.artifact_digest
    normalized["tasks"].append(successor_payload)
    changed_p3: set[str] = set()
    for task in normalized["tasks"]:
        if task["task_key"] not in P3_TASK_KEYS:
            continue
        dependencies = task.get("dependencies", [])
        if not dependencies or dependencies[0] != {
            "dependency_type": "task",
            "required_status": "completed",
            "target_key": OLD_TASK_KEY,
        }:
            raise GlobalRoutingRecoveryV3Error(
                f"global_recovery_v3_p3_dependency_changed:{task['task_key']}"
            )
        dependencies[0]["target_key"] = RECOVERY_TASK_KEY
        changed_p3.add(task["task_key"])
    if changed_p3 != set(P3_TASK_KEYS):
        raise GlobalRoutingRecoveryV3Error("global_recovery_v3_p3_change_set_changed")

    successor = ControlPlaneManifest.from_dict(normalized)
    output_snapshot = ResearchOSControlPlane().resolve(successor)
    ready = tuple(item.task_key for item in output_snapshot.ready_queue)
    if ready != (RECOVERY_TASK_KEY,):
        raise GlobalRoutingRecoveryV3Error("global_recovery_v3_successor_not_unique_ready")
    successor_by_key = {task.task_key: task for task in successor.tasks}
    recovery = successor_by_key[RECOVERY_TASK_KEY]
    if successor_by_key[OLD_TASK_KEY].artifact_digest != OLD_TASK_DIGEST:
        raise GlobalRoutingRecoveryV3Error("global_recovery_v3_old_definition_changed")
    dry_run: dict[str, Any] = {
        "schema_version": "dehps-m4-v2-global-routing-recovery-dry-run.v3",
        "artifact_type": "m4_v2_global_routing_recovery_dry_run",
        "artifact_digest": "",
        "status": "VERIFIED",
        "input_manifest_digest": manifest.artifact_digest,
        "input_snapshot_digest": snapshot.snapshot_digest,
        "input_ready_task_keys": [],
        "old_task_key": OLD_TASK_KEY,
        "old_task_digest": old.artifact_digest,
        "old_durable_history_immutable": True,
        "recovery_task_key": RECOVERY_TASK_KEY,
        "recovery_task_digest": recovery.artifact_digest,
        "recovery_lineage_digest": RECOVERY_LINEAGE_DIGEST,
        "p3_revision_count": 2,
        "output_manifest_digest": successor.artifact_digest,
        "output_snapshot_digest": output_snapshot.snapshot_digest,
        "output_ready_task_keys": list(ready),
        "import_performed": False,
        "production_action": "none",
        "promotion_gate_opened": False,
        "p3_folds": 0,
    }
    identity = dict(dry_run)
    identity.pop("artifact_digest")
    dry_run["artifact_digest"] = canonical_digest(
        identity, domain="dehps.m4.v2.global-routing-recovery-dry-run.v3"
    )
    return successor.to_dict(include_digest=True), dry_run


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GlobalRoutingRecoveryV3Error(f"json_root_not_object:{path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the pure Global recovery-v3 manifest.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--global-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", type=Path, required=True)
    args = parser.parse_args()
    source = _load(args.global_source)
    source_digest = validate_global_source_contract(
        source, root_dir=Path(__file__).resolve().parents[3]
    )
    manifest, dry_run = build_manifest(
        _load(args.input), global_source_contract_digest=source_digest
    )
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    args.dry_run.write_text(
        json.dumps(dry_run, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
