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
from dehps.research_os.models import ControlPlaneManifest, Task, m4_v2_domain_digest


class GlobalRoutingReplayCompatibilityV1Error(RuntimeError):
    pass


INPUT_MANIFEST_DIGEST = "bf2cb25ab0c5ac750655700dc9df230eec3c7bbdf5114fd5349414c2f835f2cb"
INPUT_SNAPSHOT_DIGEST = "e30e18619d60b3ac3e3d361eea50c74db2323ac215f2781bc0255338186ff6ec"
OLD_TASK_KEY = "m4-v2-global-routing-recovery-v3"
OLD_TASK_DIGEST = "bddceb738009ba18cf81d26453915349ab588ba574d3a24e6ffd5c1bd8e49ab2"
OLD_EXECUTION_ID = "503c39400e0fc1b285e2600de9baf52e702d28d582e1530db4ed516010df731d"
OLD_STARTED_EVENT_DIGEST = "c1824f7eaf3974fc11c194279db01e09e838565e1dc8c13d342474595f3ac1f0"
OLD_COMPLETED_EVENT_DIGEST = "7120593f98b7188e2c49af937a04d4c68204ae56b4961950174c5085884fc1d7"
OLD_EVENT_MANIFEST_DIGEST = "37fd5343464d87ea853ccc32ec85c3396a62ba4d79401b44eec7fc26694e20d2"
OLD_ROUTE_ARTIFACT_DIGEST = "b35a0860e7e2d330513ddf4c0cfee8e1b8a6a59dc24f78bd5d5f55f53daf02db"
OLD_ROUTE_REGISTRATION_DIGEST = "69a01c62616dc6bae4cb1924a2d1dbf39e6199b94e5de4d9cd14d5965ad48745"
OLD_EXECUTION_ARTIFACT_DIGEST = "dc233fb990d4b7d1ca1dd6693ec95c4bb960ffc58d18a0d3f5f97a5e5141bc44"
OLD_EXECUTION_REGISTRATION_DIGEST = "e207fee89e567de793d81fdf38b489c1ae8472dee59791c1eb79771f9ab022c8"
OLD_ROUTE = "DEEPER_VALIDATION_REQUIRED"
OLD_GIT_COMMIT = "cbb2841b682f20d1c42d7159ff32e8a802d0878c"
OLD_ROUTE_PATH = (
    "runtime/research-os/mainline/tasks/m4-v2-global-routing-recovery-v3/"
    f"{OLD_EXECUTION_ID}/artifacts/global-routing-decision/"
    f"{OLD_ROUTE_ARTIFACT_DIGEST}/decision.json"
)
OLD_ROUTE_RAW_SHA256 = "5b81b9a116d345e462e44d7d3a47fa5f4f9d1de1566d66df8ae15c9f0567e25c"
OLD_ROUTE_RAW_LENGTH = 5068
OLD_EXECUTION_PATH = (
    "runtime/research-os/mainline/tasks/m4-v2-global-routing-recovery-v3/"
    f"{OLD_EXECUTION_ID}/execution.json"
)

SUCCESSOR_TASK_KEY = (
    "m4-v2-global-routing-recovery-v3-registered-replay-compatibility-v1"
)
SUCCESSOR_COMPLETION_FACT = f"{SUCCESSOR_TASK_KEY}:COMPLETE"
REGISTERED_REPLAY_FACT = f"{SUCCESSOR_TASK_KEY}:REGISTERED_REPLAY_VERIFIED"
AUTHORIZATION_EVENT = (
    "agent-request:613:APPROVE_EXACT_ADDITIVE_REPLAY_SUCCESSOR_IMPORT"
)

SOURCE_PATH = (
    "configs/research-os/m4-v2-global-routing-replay-compatibility-v1.json"
)
SOURCE_SCHEMA = "dehps-m4-v2-global-routing-replay-compatibility-source.v1"
SOURCE_ARTIFACT_TYPE = "m4_v2_global_routing_source_contract"
SOURCE_ENTRIES = (
    "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/routing.py",
    "apps/worker-python/dehps/research_os/repository.py",
    "apps/worker-python/scripts/build_m4_v2_global_routing_replay_compatibility_v1_manifest.py",
)
SOURCE_SET_DOMAIN = "dehps.m4.v2.global-routing-replay-compatibility.source-set.v1"
SOURCE_CONTRACT_DOMAIN = "dehps.m4.v2.global-routing-replay-compatibility.source.v1"
SOURCE_FIELDS = {
    "schema_version",
    "artifact_type",
    "artifact_digest",
    "source_entries",
    "source_set_digest",
    "research_request_id",
    "research_decision_id",
    "engineering_request_id",
    "engineering_decision_id",
    "review_outcome",
    "baseline_manifest_digest",
    "old_task_digest",
    "old_route_artifact_digest",
    "old_route_registration_digest",
    "global_route",
    "successor_task_key",
    "workload_rerun",
    "predictive_p3_folds",
    "p4_started",
    "promotion_triggered",
}


def _digest(value: object, name: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise GlobalRoutingReplayCompatibilityV1Error(f"{name}_invalid")
    return value


def validate_source_contract(source: Mapping[str, Any], *, root_dir: Path) -> str:
    payload = deepcopy(dict(source))
    entries = payload.get("source_entries")
    if (
        set(payload) != SOURCE_FIELDS
        or payload.get("schema_version") != SOURCE_SCHEMA
        or payload.get("artifact_type") != SOURCE_ARTIFACT_TYPE
        or payload.get("research_request_id") != 612
        or payload.get("research_decision_id") != 2577
        or payload.get("engineering_request_id") != 613
        or payload.get("engineering_decision_id") != 2582
        or payload.get("review_outcome")
        != "APPROVE_EXACT_ADDITIVE_REPLAY_SUCCESSOR_IMPORT"
        or payload.get("baseline_manifest_digest") != INPUT_MANIFEST_DIGEST
        or payload.get("old_task_digest") != OLD_TASK_DIGEST
        or payload.get("old_route_artifact_digest") != OLD_ROUTE_ARTIFACT_DIGEST
        or payload.get("old_route_registration_digest")
        != OLD_ROUTE_REGISTRATION_DIGEST
        or payload.get("global_route") != OLD_ROUTE
        or payload.get("successor_task_key") != SUCCESSOR_TASK_KEY
        or payload.get("workload_rerun") is not False
        or payload.get("predictive_p3_folds") != 0
        or payload.get("p4_started") is not False
        or payload.get("promotion_triggered") is not False
        or not isinstance(entries, list)
        or tuple(item.get("path") for item in entries if isinstance(item, Mapping))
        != SOURCE_ENTRIES
    ):
        raise GlobalRoutingReplayCompatibilityV1Error(
            "global_routing_replay_compatibility_source_shape_changed"
        )
    verified: list[dict[str, str]] = []
    expected_root = root_dir.resolve()
    for expected_path, item in zip(SOURCE_ENTRIES, entries, strict=True):
        if not isinstance(item, Mapping) or set(item) != {"path", "sha256"}:
            raise GlobalRoutingReplayCompatibilityV1Error(
                "global_routing_replay_compatibility_source_entry_changed"
            )
        absolute = (expected_root / expected_path).resolve()
        observed = str(item["sha256"])
        if (
            absolute != expected_root / expected_path
            or not absolute.is_file()
            or hashlib.sha256(absolute.read_bytes()).hexdigest() != observed
        ):
            raise GlobalRoutingReplayCompatibilityV1Error(
                "global_routing_replay_compatibility_source_bytes_changed"
            )
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
        raise GlobalRoutingReplayCompatibilityV1Error(
            "global_routing_replay_compatibility_source_identity_changed"
        )
    return artifact_digest


def build_manifest(
    live_payload: Mapping[str, Any], *, source_contract_digest: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_digest = _digest(source_contract_digest, "source_contract_digest")
    manifest = ControlPlaneManifest.from_dict(deepcopy(dict(live_payload)))
    snapshot = ResearchOSControlPlane().resolve(manifest)
    if manifest.artifact_digest != INPUT_MANIFEST_DIGEST:
        raise GlobalRoutingReplayCompatibilityV1Error(
            "global_routing_replay_compatibility_input_manifest_changed"
        )
    if snapshot.snapshot_digest != INPUT_SNAPSHOT_DIGEST or snapshot.ready_queue:
        raise GlobalRoutingReplayCompatibilityV1Error(
            "global_routing_replay_compatibility_input_resolution_changed"
        )
    tasks = {task.task_key: task for task in manifest.tasks}
    if len(tasks) != len(manifest.tasks) or SUCCESSOR_TASK_KEY in tasks:
        raise GlobalRoutingReplayCompatibilityV1Error(
            "global_routing_replay_compatibility_task_conflict"
        )
    old = tasks.get(OLD_TASK_KEY)
    if old is None or old.artifact_digest != OLD_TASK_DIGEST:
        raise GlobalRoutingReplayCompatibilityV1Error(
            "global_routing_replay_compatibility_old_task_changed"
        )
    old_state = manifest.task_state_by_digest[old.artifact_digest]
    if (
        old_state.declared_status.value != "completed"
        or old_state.completion_classification is None
        or old_state.completion_classification.value != "COMPLETE"
    ):
        raise GlobalRoutingReplayCompatibilityV1Error(
            "global_routing_replay_compatibility_old_state_changed"
        )

    normalized = manifest.to_dict(include_digest=False)
    successor_payload = {
        "task_key": SUCCESSOR_TASK_KEY,
        "goal_key": old.goal_key,
        "goal_digest": old.goal_digest,
        "task_type": "replay",
        "lane": old.lane.value,
        "dependencies": [
            {
                "dependency_type": "task",
                "target_key": OLD_TASK_KEY,
                "required_status": "completed",
            },
            {
                "dependency_type": "artifact",
                "target_key": source_digest,
                "required_status": "available",
            },
            {
                "dependency_type": "external_event",
                "target_key": AUTHORIZATION_EVENT,
                "required_status": "available",
            },
        ],
        "priority": old.priority,
        "input_artifact_digests": [
            source_digest,
            OLD_ROUTE_ARTIFACT_DIGEST,
            OLD_ROUTE_REGISTRATION_DIGEST,
            OLD_EXECUTION_ARTIFACT_DIGEST,
            OLD_EXECUTION_REGISTRATION_DIGEST,
        ],
        "requested_capability": "m4_v2_global_routing_registered_replay_compatibility",
        "metric_contract": {
            "schema_version": "dehps-m4-v2-global-routing-replay-compatibility.v1",
            "mode": "replay_only",
            "replay_api": "ResearchEvidenceSupervisor.replay",
            "replay_task_key": OLD_TASK_KEY,
            "replay_execution_id": OLD_EXECUTION_ID,
            "route_artifact_digest": OLD_ROUTE_ARTIFACT_DIGEST,
            "route_registration_digest": OLD_ROUTE_REGISTRATION_DIGEST,
            "execution_artifact_digest": OLD_EXECUTION_ARTIFACT_DIGEST,
            "execution_registration_digest": OLD_EXECUTION_REGISTRATION_DIGEST,
            "global_route": OLD_ROUTE,
            "completion_fact": SUCCESSOR_COMPLETION_FACT,
            "registered_replay_fact": REGISTERED_REPLAY_FACT,
            "workload_rerun": False,
            "branch_workloads_rerun": False,
            "global_router_workload_rerun": False,
            "predictive_p3_folds": 0,
            "p4_started": False,
            "promotion_triggered": False,
        },
        "status": "draft",
        "completion_classification": "INTEGRATION_PENDING",
        "superseded_by_task_digest": None,
    }
    successor = Task.from_dict(successor_payload, goal_digest=old.goal_digest)
    normalized["tasks"].append(successor_payload)
    normalized["facts"]["artifacts"] = sorted(
        {*normalized["facts"]["artifacts"], source_digest}
    )
    normalized["facts"]["external_events"] = sorted(
        {*normalized["facts"]["external_events"], AUTHORIZATION_EVENT}
    )
    output = ControlPlaneManifest.from_dict(normalized)
    output_snapshot = ResearchOSControlPlane().resolve(output)
    ready = tuple(item.task_key for item in output_snapshot.ready_queue)
    if ready != (SUCCESSOR_TASK_KEY,):
        raise GlobalRoutingReplayCompatibilityV1Error(
            "global_routing_replay_compatibility_not_unique_ready"
        )
    output_tasks = {task.task_key: task for task in output.tasks}
    if (
        output_tasks[SUCCESSOR_TASK_KEY].artifact_digest != successor.artifact_digest
        or tuple(output.goals) != tuple(manifest.goals)
        or tuple(output.tasks[:-1]) != tuple(manifest.tasks)
        or tuple(output.goal_states) != tuple(manifest.goal_states)
        or tuple(output.task_states[:-1]) != tuple(manifest.task_states)
    ):
        raise GlobalRoutingReplayCompatibilityV1Error(
            "global_routing_replay_compatibility_existing_identity_changed"
        )
    dry_run: dict[str, Any] = {
        "schema_version": "dehps-m4-v2-global-routing-replay-compatibility-dry-run.v1",
        "artifact_type": "m4_v2_global_routing_replay_compatibility_dry_run",
        "artifact_digest": "",
        "status": "VERIFIED",
        "input_manifest_digest": manifest.artifact_digest,
        "input_snapshot_digest": snapshot.snapshot_digest,
        "input_ready_task_keys": [],
        "old_task_key": OLD_TASK_KEY,
        "old_task_digest": old.artifact_digest,
        "successor_task_key": SUCCESSOR_TASK_KEY,
        "successor_task_digest": successor.artifact_digest,
        "output_manifest_digest": output.artifact_digest,
        "output_snapshot_digest": output_snapshot.snapshot_digest,
        "output_ready_task_keys": list(ready),
        "existing_goal_deletions": 0,
        "existing_task_deletions": 0,
        "existing_fact_deletions": 0,
        "existing_state_regressions": 0,
        "existing_definition_rewrites": 0,
        "new_task_count": 1,
        "workload_rerun": False,
        "predictive_p3_folds": 0,
        "p4_started": False,
        "promotion_triggered": False,
    }
    identity = dict(dry_run)
    identity.pop("artifact_digest")
    dry_run["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.v2.global-routing-replay-compatibility-dry-run.v1",
    )
    return output.to_dict(include_digest=True), dry_run


def transition_manifest(
    ready_payload: Mapping[str, Any],
    *,
    status: str,
    classification: str,
    execution_id: str | None = None,
) -> dict[str, Any]:
    ready = ControlPlaneManifest.from_dict(deepcopy(dict(ready_payload)))
    payload = ready.to_dict(include_digest=False)
    matches = [
        item for item in payload["tasks"] if item["task_key"] == SUCCESSOR_TASK_KEY
    ]
    if len(matches) != 1:
        raise GlobalRoutingReplayCompatibilityV1Error(
            "global_routing_replay_compatibility_task_changed"
        )
    matches[0]["status"] = status
    matches[0]["completion_classification"] = classification
    if status == "completed":
        if not execution_id:
            raise GlobalRoutingReplayCompatibilityV1Error(
                "global_routing_replay_compatibility_execution_missing"
            )
        mainline_fact = (
            f"mainline-execution:{SUCCESSOR_TASK_KEY}:"
            f"{Task.from_dict(matches[0]).artifact_digest}:{execution_id}:completed"
        )
        payload["facts"]["artifacts"] = sorted(
            {
                *payload["facts"]["artifacts"],
                SUCCESSOR_COMPLETION_FACT,
                REGISTERED_REPLAY_FACT,
                mainline_fact,
            }
        )
    return ControlPlaneManifest.from_dict(payload).to_dict(include_digest=True)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GlobalRoutingReplayCompatibilityV1Error(f"json_root_not_object:{path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the approved replay-only recovery-v3 compatibility manifest."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", type=Path, required=True)
    args = parser.parse_args()
    source_digest = validate_source_contract(
        _load(args.source), root_dir=Path(__file__).resolve().parents[3]
    )
    manifest, dry_run = build_manifest(
        _load(args.input), source_contract_digest=source_digest
    )
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    args.dry_run.write_text(
        json.dumps(dry_run, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
