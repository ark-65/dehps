from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.models import ControlPlaneManifest, stable_hash


class GlobalRoutingRecoveryError(RuntimeError):
    pass


INPUT_MANIFEST_DIGEST = "15f5d12cebb0eed31f4f0f33c1ac4d3d0878f9335d11741046305baf746eb216"
INPUT_SNAPSHOT_DIGEST = "e80b5fa52caee4cbab1f380aceda3dd55cede6581fb8ee62a882afdd843ea2c5"
OLD_TASK_KEY = "m4-v2-global-routing"
RECOVERY_TASK_KEY = "m4-v2-global-routing-recovery-v1"
RECOVERY_COMPLETION_FACT = f"{RECOVERY_TASK_KEY}:COMPLETE"
OLD_TASK_DIGEST = "da2910f9a7371c46225e0df5a400b3c64ca36bbe05dd98c881a232d66ae144ae"
OLD_SOURCE_DIGEST = "5df45852e589719de889cdd5c08dedc9985b037fb27670354cddcadff20ace66"
OLD_EXECUTION_ID = "7d1d2d82c6d46679f9e3da9f0d743b0d7a774262eb3c5220daefca11100ad12d"
OLD_EVENT_MANIFEST_DIGEST = "91ea3e8de6b48c51cf854a2f7254b81da758db601fbacf4971d648ebf3031b6c"
OLD_STARTED_EVENT_DIGEST = "dab8a953b60bebcb927147d123b7280392b9a3ead6f0d225ec5799e4b7caaebb"
OLD_FAILED_EVENT_DIGEST = "a4163025b41b837c1d3c467242b0710b9255bd68a0e6cb16378b64f6c7e0a37c"
P3_REVISIONS = (
    (
        "m4-p3-strict-historical-walk-forward",
        "188e902da86eea04ca2b1c27b010cec30a66432bcc328a6f8da4a426434a3aef",
        "c39f15f7facf9d3878923bc8b2da6b9992bc069a9aab5373feb2e78890f7a89f",
    ),
    (
        "m4-p3-predictive-preregistration-freeze",
        "d4faa29bff5071985533253341941eaddc4e7ba99b56d23725ab75a38981fac5",
        "36ef2ea3ff39c874054d606000bd3b51fa3b18f917fb85beae77643a818b9c13",
    ),
)
RECOVERY_LINEAGE = {
    "cause": "exact_replay_envelope_historical_key_with_recovery_registration_key",
    "old_active_definition_digest": OLD_TASK_DIGEST,
    "old_event_manifest_digest": OLD_EVENT_MANIFEST_DIGEST,
    "old_execution_id": OLD_EXECUTION_ID,
    "old_failed_event": {"event_digest": OLD_FAILED_EVENT_DIGEST, "sequence": 1},
    "old_older_definition_digest": "321660dd0f35e3bc3a4ea752d9257e24014bc1b5966b05f6ba5ef63656e5a377",
    "old_started_event": {"event_digest": OLD_STARTED_EVENT_DIGEST, "sequence": 0},
    "old_state": {
        "completion_classification": "INTEGRATED",
        "declared_status": "failed",
        "reason_code": "task_failed",
        "resolved_status": "failed",
        "superseded_by_task_digest": None,
    },
    "old_task_key": OLD_TASK_KEY,
    "schema_version": "dehps-m4-v2-global-routing-recovery-lineage.v1",
    "successor_task_key": RECOVERY_TASK_KEY,
}
RECOVERY_LINEAGE_DIGEST = stable_hash(RECOVERY_LINEAGE)


def _digest(value: object, name: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise GlobalRoutingRecoveryError(f"{name}_invalid")
    return value


def build_manifest(
    live_payload: Mapping[str, Any], *, global_source_contract_digest: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_digest = _digest(global_source_contract_digest, "global_source_contract_digest")
    if source_digest == OLD_SOURCE_DIGEST:
        raise GlobalRoutingRecoveryError("global_recovery_source_not_resealed")
    manifest = ControlPlaneManifest.from_dict(deepcopy(dict(live_payload)))
    snapshot = ResearchOSControlPlane().resolve(manifest)
    if manifest.artifact_digest != INPUT_MANIFEST_DIGEST:
        raise GlobalRoutingRecoveryError("global_recovery_input_manifest_changed")
    if snapshot.snapshot_digest != INPUT_SNAPSHOT_DIGEST or snapshot.ready_queue:
        raise GlobalRoutingRecoveryError("global_recovery_input_resolution_changed")
    tasks = {task.task_key: task for task in manifest.tasks}
    if len(tasks) != len(manifest.tasks) or RECOVERY_TASK_KEY in tasks:
        raise GlobalRoutingRecoveryError("global_recovery_task_identity_conflict")
    old = tasks.get(OLD_TASK_KEY)
    if old is None or old.artifact_digest != OLD_TASK_DIGEST:
        raise GlobalRoutingRecoveryError("global_recovery_old_definition_changed")
    old_state = manifest.task_state_by_digest[old.artifact_digest]
    if (
        old.input_artifact_digests != (OLD_SOURCE_DIGEST,)
        or old_state.declared_status.value != "failed"
        or old_state.completion_classification is None
        or old_state.completion_classification.value != "INTEGRATED"
        or old_state.superseded_by_task_digest is not None
    ):
        raise GlobalRoutingRecoveryError("global_recovery_old_state_changed")
    expected_p3 = {key: (before, after) for key, before, after in P3_REVISIONS}
    for key, (before, _) in expected_p3.items():
        if key not in tasks or tasks[key].artifact_digest != before:
            raise GlobalRoutingRecoveryError(f"global_recovery_p3_old_changed:{key}")

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
            metric_contract["completion_fact"] = RECOVERY_COMPLETION_FACT
            downstream = metric_contract["mainline_integration"]["downstream_artifacts"]
            if downstream[2] != f"{OLD_TASK_KEY}:COMPLETE":
                raise GlobalRoutingRecoveryError(
                    "global_recovery_old_completion_fact_changed"
                )
            downstream[2] = RECOVERY_COMPLETION_FACT
            expected_route_path = (
                f"runtime/research-os/mainline/tasks/{OLD_TASK_KEY}/"
                "{execution_id}/artifacts/global-routing-decision/"
                "{artifact_digest}/decision.json"
            )
            if metric_contract["route_artifact_path_template"] != expected_route_path:
                raise GlobalRoutingRecoveryError("global_recovery_old_route_path_changed")
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
                raise GlobalRoutingRecoveryError(f"global_recovery_p3_dependency_changed:{key}")
            dependencies[0]["target_key"] = RECOVERY_TASK_KEY
            changed.add(key)
    if changed != {OLD_TASK_KEY, *expected_p3}:
        raise GlobalRoutingRecoveryError("global_recovery_change_set_changed")
    successor = ControlPlaneManifest.from_dict(normalized)
    successor_by_key = {task.task_key: task for task in successor.tasks}
    for key, (_, after) in expected_p3.items():
        if successor_by_key[key].artifact_digest != after:
            raise GlobalRoutingRecoveryError(f"global_recovery_p3_new_changed:{key}")
    output_snapshot = ResearchOSControlPlane().resolve(successor)
    ready = tuple(item.task_key for item in output_snapshot.ready_queue)
    if ready != (RECOVERY_TASK_KEY,):
        raise GlobalRoutingRecoveryError("global_recovery_successor_not_unique_ready")
    recovery = successor_by_key[RECOVERY_TASK_KEY]
    dry_run: dict[str, Any] = {
        "schema_version": "dehps-m4-v2-global-routing-recovery-dry-run.v1",
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
        identity, domain="dehps.m4.v2.global-routing-recovery-dry-run.v1"
    )
    return successor.to_dict(include_digest=True), dry_run


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GlobalRoutingRecoveryError(f"json_root_not_object:{path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the pure Global recovery manifest.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--global-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", type=Path, required=True)
    args = parser.parse_args()
    source = _load(args.global_source)
    manifest, dry_run = build_manifest(
        _load(args.input),
        global_source_contract_digest=_digest(source.get("artifact_digest"), "global_source_contract_digest"),
    )
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    args.dry_run.write_text(json.dumps(dry_run, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
