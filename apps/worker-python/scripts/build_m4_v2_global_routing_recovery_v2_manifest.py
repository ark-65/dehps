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


class GlobalRoutingRecoveryV2Error(RuntimeError):
    pass


INPUT_MANIFEST_DIGEST = "03718fe3cb8744410d66f72f523e469baa5ff01c78334792c85fd9cd5c9298cc"
INPUT_SNAPSHOT_DIGEST = "0c9c8dc98f92f04c7c7ba57e824b881d65976415b7e9f3dc1fe1d793ec5cdc50"
OLD_TASK_KEY = "m4-v2-global-routing-recovery-v1"
RECOVERY_TASK_KEY = "m4-v2-global-routing-recovery-v2"
RECOVERY_COMPLETION_FACT = f"{RECOVERY_TASK_KEY}:COMPLETE"
OLD_TASK_DIGEST = "09068006b555e4d9f2d9bb4ec6a1c471daa244c82fe278c44407b2aeab1fcff2"
OLD_SOURCE_DIGEST = "ae2985e419e5b2839c29fe47372480ee50b35b7070109842f2984d5d44101670"
OLD_EXECUTION_ID = "bc2dada5ea040d488b9256ea2adb90163b6c46a45d517e545f7d24b39efa7c66"
OLD_EVENT_MANIFEST_DIGEST = "1c8447a23f6b9c3b36cdd643bee6d5731b738a6756b58239f1e93401aaaf45ee"
OLD_STARTED_EVENT_DIGEST = "6755e55e8452245c33b98943ccffac08b48975e760cfab0f78cb141ef9602b57"
OLD_FAILED_EVENT_DIGEST = "ded0415587e7a32c7bb30f2bc721df3ce8e74f93c98c419cd9c1a59cdc560a09"
P3_REVISIONS = (
    (
        "m4-p3-strict-historical-walk-forward",
        "c39f15f7facf9d3878923bc8b2da6b9992bc069a9aab5373feb2e78890f7a89f",
        "23cb05bf26a222a464f1f6650f698740225c98a96a4d0ee33bb3eca37f59d0b6",
    ),
    (
        "m4-p3-predictive-preregistration-freeze",
        "36ef2ea3ff39c874054d606000bd3b51fa3b18f917fb85beae77643a818b9c13",
        "a6edc248330e82fc83680ed32a88f6c56386c19ac0b8570da8a2a32b8dd36e03",
    ),
)
RECOVERY_LINEAGE = {
    "cause": "compatibility_predicate_required_nonexistent_replay_body_fields",
    "old_active_definition_digest": OLD_TASK_DIGEST,
    "old_event_manifest_digest": OLD_EVENT_MANIFEST_DIGEST,
    "old_execution_id": OLD_EXECUTION_ID,
    "old_failed_event": {"event_digest": OLD_FAILED_EVENT_DIGEST, "sequence": 1},
    "old_started_event": {"event_digest": OLD_STARTED_EVENT_DIGEST, "sequence": 0},
    "old_state": {
        "completion_classification": "INTEGRATED",
        "declared_status": "failed",
        "superseded_by_task_digest": None,
    },
    "old_task_key": OLD_TASK_KEY,
    "schema_version": "dehps-m4-v2-global-routing-recovery-lineage.v2",
    "successor_task_key": RECOVERY_TASK_KEY,
}
RECOVERY_LINEAGE_DIGEST = stable_hash(RECOVERY_LINEAGE)
GLOBAL_SOURCE_PATH = "configs/research-os/m4-v2-global-routing-source-v1.json"
GLOBAL_SOURCE_SCHEMA = "dehps-m4-v2-global-routing-source-contract.v1"
GLOBAL_SOURCE_ARTIFACT_TYPE = "m4_v2_global_routing_source_contract"
GLOBAL_MEASUREMENT_CONTRACT_KEY = "M4_MEASUREMENT_CONTRACT_V2"
GLOBAL_MEASUREMENT_CONTRACT_DIGEST = (
    "a0a367c99d7646cadc162bd9ceb0d5d73481cd7c26656bf02b40a99d9180095b"
)
GLOBAL_SOURCE_FACT = (
    "m4-v2-global-routing-contract:M4_MEASUREMENT_CONTRACT_V2:FROZEN"
)
GLOBAL_RESEARCH_CONTEXT_FINGERPRINT = (
    "9eb546ff2bc2c7aa84d7ed78635fb5dec31c1aa8c5864768da57d8a7f1809ebf"
)
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
        raise GlobalRoutingRecoveryV2Error(f"{name}_invalid")
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
        or payload.get("measurement_contract_key")
        != GLOBAL_MEASUREMENT_CONTRACT_KEY
        or payload.get("measurement_contract_digest")
        != GLOBAL_MEASUREMENT_CONTRACT_DIGEST
        or payload.get("source_fact") != GLOBAL_SOURCE_FACT
        or payload.get("research_context_fingerprint")
        != GLOBAL_RESEARCH_CONTEXT_FINGERPRINT
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
        raise GlobalRoutingRecoveryV2Error("global_recovery_v2_source_shape_changed")
    verified: list[dict[str, str]] = []
    for expected_path, item in zip(GLOBAL_SOURCE_ENTRIES, entries, strict=True):
        if not isinstance(item, Mapping) or set(item) != {"path", "sha256"}:
            raise GlobalRoutingRecoveryV2Error("global_recovery_v2_source_entry_changed")
        absolute = (root_dir / expected_path).resolve()
        expected_root = root_dir.resolve()
        observed = str(item["sha256"])
        if (
            absolute != expected_root / expected_path
            or not absolute.is_file()
            or hashlib.sha256(absolute.read_bytes()).hexdigest() != observed
        ):
            raise GlobalRoutingRecoveryV2Error("global_recovery_v2_source_bytes_changed")
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
        raise GlobalRoutingRecoveryV2Error("global_recovery_v2_source_identity_changed")
    return artifact_digest


def build_manifest(
    live_payload: Mapping[str, Any], *, global_source_contract_digest: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_digest = _digest(global_source_contract_digest, "global_source_contract_digest")
    if source_digest == OLD_SOURCE_DIGEST:
        raise GlobalRoutingRecoveryV2Error("global_recovery_v2_source_not_resealed")
    manifest = ControlPlaneManifest.from_dict(deepcopy(dict(live_payload)))
    snapshot = ResearchOSControlPlane().resolve(manifest)
    if manifest.artifact_digest != INPUT_MANIFEST_DIGEST:
        raise GlobalRoutingRecoveryV2Error("global_recovery_v2_input_manifest_changed")
    if snapshot.snapshot_digest != INPUT_SNAPSHOT_DIGEST or snapshot.ready_queue:
        raise GlobalRoutingRecoveryV2Error("global_recovery_v2_input_resolution_changed")
    tasks = {task.task_key: task for task in manifest.tasks}
    if len(tasks) != len(manifest.tasks) or RECOVERY_TASK_KEY in tasks:
        raise GlobalRoutingRecoveryV2Error("global_recovery_v2_task_identity_conflict")
    old = tasks.get(OLD_TASK_KEY)
    if old is None or old.artifact_digest != OLD_TASK_DIGEST:
        raise GlobalRoutingRecoveryV2Error("global_recovery_v2_old_definition_changed")
    old_state = manifest.task_state_by_digest[old.artifact_digest]
    if (
        old.input_artifact_digests != (OLD_SOURCE_DIGEST,)
        or old_state.declared_status.value != "failed"
        or old_state.completion_classification is None
        or old_state.completion_classification.value != "INTEGRATED"
        or old_state.superseded_by_task_digest is not None
    ):
        raise GlobalRoutingRecoveryV2Error("global_recovery_v2_old_state_changed")
    expected_p3 = {key: (before, after) for key, before, after in P3_REVISIONS}
    for key, (before, _) in expected_p3.items():
        if key not in tasks or tasks[key].artifact_digest != before:
            raise GlobalRoutingRecoveryV2Error(f"global_recovery_v2_p3_old_changed:{key}")

    normalized = manifest.to_dict(include_digest=False)
    changed = set()
    for task in normalized["tasks"]:
        key = task["task_key"]
        if key == OLD_TASK_KEY:
            task["task_key"] = RECOVERY_TASK_KEY
            task["input_artifact_digests"] = [source_digest]
            task["status"] = "draft"
            task["completion_classification"] = "INTEGRATION_PENDING"
            task["superseded_by_task_digest"] = None
            metric_contract = task["metric_contract"]
            if metric_contract["completion_fact"] != f"{OLD_TASK_KEY}:COMPLETE":
                raise GlobalRoutingRecoveryV2Error(
                    "global_recovery_v2_old_completion_fact_changed"
                )
            metric_contract["completion_fact"] = RECOVERY_COMPLETION_FACT
            downstream = metric_contract["mainline_integration"]["downstream_artifacts"]
            if downstream[2] != f"{OLD_TASK_KEY}:COMPLETE":
                raise GlobalRoutingRecoveryV2Error(
                    "global_recovery_v2_old_downstream_fact_changed"
                )
            downstream[2] = RECOVERY_COMPLETION_FACT
            expected_route_path = (
                f"runtime/research-os/mainline/tasks/{OLD_TASK_KEY}/"
                "{execution_id}/artifacts/global-routing-decision/"
                "{artifact_digest}/decision.json"
            )
            if metric_contract["route_artifact_path_template"] != expected_route_path:
                raise GlobalRoutingRecoveryV2Error(
                    "global_recovery_v2_old_route_path_changed"
                )
            metric_contract["route_artifact_path_template"] = expected_route_path.replace(
                OLD_TASK_KEY, RECOVERY_TASK_KEY, 1
            )
            metric_contract["recovery_lineage"] = deepcopy(RECOVERY_LINEAGE)
            metric_contract["recovery_lineage_digest"] = RECOVERY_LINEAGE_DIGEST
            changed.add(OLD_TASK_KEY)
        elif key in expected_p3:
            dependencies = task["dependencies"]
            if not dependencies or dependencies[0] != {
                "dependency_type": "task",
                "required_status": "completed",
                "target_key": OLD_TASK_KEY,
            }:
                raise GlobalRoutingRecoveryV2Error(
                    f"global_recovery_v2_p3_dependency_changed:{key}"
                )
            dependencies[0]["target_key"] = RECOVERY_TASK_KEY
            changed.add(key)
    if changed != {OLD_TASK_KEY, *expected_p3}:
        raise GlobalRoutingRecoveryV2Error("global_recovery_v2_change_set_changed")
    successor = ControlPlaneManifest.from_dict(normalized)
    successor_by_key = {task.task_key: task for task in successor.tasks}
    for key, (_, after) in expected_p3.items():
        if successor_by_key[key].artifact_digest != after:
            raise GlobalRoutingRecoveryV2Error(f"global_recovery_v2_p3_new_changed:{key}")
    output_snapshot = ResearchOSControlPlane().resolve(successor)
    ready = tuple(item.task_key for item in output_snapshot.ready_queue)
    if ready != (RECOVERY_TASK_KEY,):
        raise GlobalRoutingRecoveryV2Error("global_recovery_v2_successor_not_unique_ready")
    recovery = successor_by_key[RECOVERY_TASK_KEY]
    dry_run: dict[str, Any] = {
        "schema_version": "dehps-m4-v2-global-routing-recovery-dry-run.v2",
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
        identity, domain="dehps.m4.v2.global-routing-recovery-dry-run.v2"
    )
    return successor.to_dict(include_digest=True), dry_run


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GlobalRoutingRecoveryV2Error(f"json_root_not_object:{path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the pure Global recovery-v2 manifest.")
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
        _load(args.input),
        global_source_contract_digest=source_digest,
    )
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    args.dry_run.write_text(
        json.dumps(dry_run, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
