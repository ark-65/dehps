from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.models import ControlPlaneManifest


class NineDownstreamRevisionError(RuntimeError):
    pass


INPUT_MANIFEST_DIGEST = (
    "21242d61f4f61821f4409e345dace191e5bef68566d1ddffc70b1a9a2e1c0954"
)
INPUT_SNAPSHOT_DIGEST = (
    "7f6ffcf58f22669cdd196a52d775e3cb8b5590487b46e234f049ac7023288969"
)
OUTPUT_MANIFEST_DIGEST = (
    "12496224588629f0486aadd6dbadaf07059788833936d20466f1daaad8b74588"
)
OUTPUT_SNAPSHOT_DIGEST = (
    "db82b9eba89c0228db7855d86da3e1a833f47e6591f2d346f6bd5e384c0d805c"
)
OUTPUT_DRY_RUN_DIGEST = (
    "492f9cbf79e325d9e4fcac496e72f450d19aae32eda0db91fceee377d24271c7"
)
RECOVERY_TASK_KEY = (
    "m4-v2-marginal-static-historical-branch-decision-replay-recovery-v1"
)
SOURCE_DIGESTS = {
    "TEMPORAL_MARGINAL_INCREMENT": (
        "d266bc0a49b9423871753c25e0c5b97d0fb39c6fad50a02e59fc75e1e5ccfe5a"
    ),
    "JOINT_RESIDUAL_INCREMENT": (
        "3dc328e7067619967e5cf10333f69749e80b37143bbde8b59beb84ae64abe8a7"
    ),
    "GLOBAL_ROUTING": (
        "5df45852e589719de889cdd5c08dedc9985b037fb27670354cddcadff20ace66"
    ),
}
REVISION_VALIDATION_ORDER = (
    (
        "m4-v2-temporal-marginal-increment-historical-measurement-design",
        "f8011af57197bee0774c393e7f2b2a43015ffce890a8d754ce8043f1efd3923d",
        "658b490f1c3b46c7beafb3f34ec42c58fd2481e92e4a03057de2ff43c070d825",
        "ec4ce534bd4aeb983ec6042c81ab5f92ca08dac46aa4a16bf6242f332c18360f",
        SOURCE_DIGESTS["TEMPORAL_MARGINAL_INCREMENT"],
    ),
    (
        "m4-v2-temporal-marginal-increment-historical-measurement-preregistration",
        "1816c0a58fd4e5e141b4daee564c12a1cd2ac13a5d5371233a2ce227a6028d7f",
        "658b490f1c3b46c7beafb3f34ec42c58fd2481e92e4a03057de2ff43c070d825",
        "c940b04c6d3960ae69c1ada8ce301de271da9025c3abb36ffe650f2f5eff8dfb",
        SOURCE_DIGESTS["TEMPORAL_MARGINAL_INCREMENT"],
    ),
    (
        "m4-v2-temporal-marginal-increment-historical-measurement-gate-compiler",
        "c21abbb47738f738441606b9e22ba0c244826b688379f0afb8ed225c1df85934",
        "658b490f1c3b46c7beafb3f34ec42c58fd2481e92e4a03057de2ff43c070d825",
        "349463cb8c4a836a8c77263528915d907878b6cea0136301e3806c2254ad108c",
        SOURCE_DIGESTS["TEMPORAL_MARGINAL_INCREMENT"],
    ),
    (
        "m4-v2-temporal-marginal-increment-historical-branch-decision-replay",
        "a512d423d5a3d83375bf36c33d427147c9ab08c1957cc6a03ef7082b105af126",
        "658b490f1c3b46c7beafb3f34ec42c58fd2481e92e4a03057de2ff43c070d825",
        "bfdbe688703c437a98d610ef8578335a6f1022e82b6dcf0a2deed79498d64e5c",
        SOURCE_DIGESTS["TEMPORAL_MARGINAL_INCREMENT"],
    ),
    (
        "m4-v2-joint-residual-increment-historical-measurement-design",
        "427ba2b9e7e02a371983d8af03c701fd635b9d38febf0cd122a812403c9b688f",
        "596f753ad6c273930c65fee35fde61461eb8a6b102461c083f22c887908598db",
        "c17821ffe9d26dbee9f81d65641aea856232cfd3d1a3f228dca4f367b3987f57",
        SOURCE_DIGESTS["JOINT_RESIDUAL_INCREMENT"],
    ),
    (
        "m4-v2-joint-residual-increment-historical-measurement-preregistration",
        "1696ecae5a07a776b3fe38fcdb2a174793cdc7b1e09579c8e06871a5e184fdd5",
        "596f753ad6c273930c65fee35fde61461eb8a6b102461c083f22c887908598db",
        "4e81b41f66a57067afa177c96c63aba8b8094463f96831cd208468ba704e693f",
        SOURCE_DIGESTS["JOINT_RESIDUAL_INCREMENT"],
    ),
    (
        "m4-v2-joint-residual-increment-historical-measurement-gate-compiler",
        "963e25629ac1bedf236ccab5723b288e7a971aad65bcf28b65de7dc6db2fe6cd",
        "596f753ad6c273930c65fee35fde61461eb8a6b102461c083f22c887908598db",
        "b4a82f06c378d7827061f2ab29d01cacb9774d7f9b2260ac8a06b4972523cdb0",
        SOURCE_DIGESTS["JOINT_RESIDUAL_INCREMENT"],
    ),
    (
        "m4-v2-joint-residual-increment-historical-branch-decision-replay",
        "220f84b412414ccc6b38eb69ca9b3cff560c32002b4cbce4896548095ce33c4b",
        "596f753ad6c273930c65fee35fde61461eb8a6b102461c083f22c887908598db",
        "3a9cb018e3cfb5b99f3fd5028b5f437defee9356c3ebb300d1bb01574dc5404e",
        SOURCE_DIGESTS["JOINT_RESIDUAL_INCREMENT"],
    ),
    (
        "m4-v2-global-routing",
        "321660dd0f35e3bc3a4ea752d9257e24014bc1b5966b05f6ba5ef63656e5a377",
        "c8b1e4e50235179339fd95cb7e2af63d3e0616e25e30d689f7afec3019e19e7a",
        "da2910f9a7371c46225e0df5a400b3c64ca36bbe05dd98c881a232d66ae144ae",
        SOURCE_DIGESTS["GLOBAL_ROUTING"],
    ),
)


def _require_digest(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise NineDownstreamRevisionError(f"{field_name}_invalid")
    return value


def build_manifest(
    pure_recovery_payload: Mapping[str, Any],
    *,
    temporal_source_contract_digest: str,
    joint_source_contract_digest: str,
    global_source_contract_digest: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    supplied_sources = {
        "TEMPORAL_MARGINAL_INCREMENT": _require_digest(
            temporal_source_contract_digest,
            field_name="temporal_source_contract_digest",
        ),
        "JOINT_RESIDUAL_INCREMENT": _require_digest(
            joint_source_contract_digest,
            field_name="joint_source_contract_digest",
        ),
        "GLOBAL_ROUTING": _require_digest(
            global_source_contract_digest,
            field_name="global_source_contract_digest",
        ),
    }
    if supplied_sources != SOURCE_DIGESTS:
        raise NineDownstreamRevisionError("nine_revision_source_contract_digests_changed")

    manifest = ControlPlaneManifest.from_dict(deepcopy(dict(pure_recovery_payload)))
    if manifest.artifact_digest != INPUT_MANIFEST_DIGEST:
        raise NineDownstreamRevisionError("nine_revision_input_manifest_changed")
    snapshot = ResearchOSControlPlane().resolve(manifest)
    if snapshot.snapshot_digest != INPUT_SNAPSHOT_DIGEST:
        raise NineDownstreamRevisionError("nine_revision_input_snapshot_changed")
    input_ready = tuple(item.task_key for item in snapshot.ready_queue)
    expected_ready = (RECOVERY_TASK_KEY,)
    if input_ready != expected_ready:
        raise NineDownstreamRevisionError("nine_revision_input_ready_changed")

    expected_by_key = {
        task_key: (old_definition, old_input, new_definition, new_input)
        for task_key, old_definition, old_input, new_definition, new_input in (
            REVISION_VALIDATION_ORDER
        )
    }
    expected_keys = set(expected_by_key)
    old_inputs = {item[2] for item in REVISION_VALIDATION_ORDER}
    typed_by_key = {task.task_key: task for task in manifest.tasks}
    if len(typed_by_key) != len(manifest.tasks):
        raise NineDownstreamRevisionError("nine_revision_duplicate_task_key")
    discovered_targets = {
        task.task_key
        for task in manifest.tasks
        if len(task.input_artifact_digests) == 1
        and task.input_artifact_digests[0] in old_inputs
    }
    if discovered_targets != expected_keys:
        raise NineDownstreamRevisionError("nine_revision_target_set_changed")
    for task_key, old_definition, old_input, _, _ in REVISION_VALIDATION_ORDER:
        task = typed_by_key.get(task_key)
        if task is None:
            raise NineDownstreamRevisionError("nine_revision_target_task_missing")
        if task.artifact_digest != old_definition:
            raise NineDownstreamRevisionError(
                f"nine_revision_old_definition_changed:{task_key}"
            )
        if tuple(task.input_artifact_digests) != (old_input,):
            raise NineDownstreamRevisionError(
                f"nine_revision_old_singleton_input_changed:{task_key}"
            )

    normalized = manifest.to_dict(include_digest=False)
    changed = 0
    for task in normalized["tasks"]:
        task_key = task["task_key"]
        if task_key in expected_by_key:
            task["input_artifact_digests"] = [expected_by_key[task_key][3]]
            changed += 1
    if changed != len(REVISION_VALIDATION_ORDER):
        raise NineDownstreamRevisionError("nine_revision_target_count_changed")

    successor = ControlPlaneManifest.from_dict(normalized)
    successor_by_key = {task.task_key: task for task in successor.tasks}
    for task_key, _, _, new_definition, _ in REVISION_VALIDATION_ORDER:
        if successor_by_key[task_key].artifact_digest != new_definition:
            raise NineDownstreamRevisionError(
                f"nine_revision_new_definition_changed:{task_key}"
            )
    if successor.artifact_digest != OUTPUT_MANIFEST_DIGEST:
        raise NineDownstreamRevisionError("nine_revision_output_manifest_changed")
    successor_snapshot = ResearchOSControlPlane().resolve(successor)
    if successor_snapshot.snapshot_digest != OUTPUT_SNAPSHOT_DIGEST:
        raise NineDownstreamRevisionError("nine_revision_output_snapshot_changed")
    output_ready = tuple(item.task_key for item in successor_snapshot.ready_queue)
    if output_ready != expected_ready:
        raise NineDownstreamRevisionError("nine_revision_output_ready_changed")

    revisions = [
        {
            "task_key": task_key,
            "old_definition_digest": old_definition,
            "new_definition_digest": new_definition,
            "old_input_artifact_digests": [old_input],
            "new_input_artifact_digests": [new_input],
        }
        for task_key, old_definition, old_input, new_definition, new_input in (
            REVISION_VALIDATION_ORDER
        )
    ]
    dry_run: dict[str, Any] = {
        "schema_version": (
            "dehps-m4-v2-nine-downstream-resealed-input-additive-revision-dry-run.v1"
        ),
        "artifact_type": (
            "m4_v2_nine_downstream_resealed_input_additive_revision_dry_run"
        ),
        "artifact_digest": "",
        "status": "VERIFIED",
        "input_manifest_digest": manifest.artifact_digest,
        "input_snapshot_digest": snapshot.snapshot_digest,
        "input_ready_task_keys": list(input_ready),
        "revision_validation_order": revisions,
        "revised_same_key_count": len(revisions),
        "new_task_count": 0,
        "output_manifest_digest": successor.artifact_digest,
        "output_snapshot_digest": successor_snapshot.snapshot_digest,
        "output_ready_task_keys": list(output_ready),
        "old_definition_bytes_immutable": True,
        "import_performed": False,
        "production_action": "none",
        "promotion_gate_opened": False,
        "p3_folds": 0,
    }
    identity = dict(dry_run)
    identity.pop("artifact_digest")
    dry_run["artifact_digest"] = canonical_digest(
        identity,
        domain=(
            "dehps.m4.v2.nine-downstream-resealed-input-additive-revision-dry-run.v1"
        ),
    )
    if dry_run["artifact_digest"] != OUTPUT_DRY_RUN_DIGEST:
        raise NineDownstreamRevisionError("nine_revision_output_dry_run_changed")
    return successor.to_dict(include_digest=True), dry_run


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise NineDownstreamRevisionError(f"json_root_not_object:{path}")
    return value


def _source_digest(path: Path, *, field_name: str) -> str:
    return _require_digest(_load(path).get("artifact_digest"), field_name=field_name)


def _serialized(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _write_temp(final_path: Path, content: bytes) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{final_path.name}.", suffix=".tmp", dir=final_path.parent
    )
    temp_path = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return temp_path


def _replace_path(temp_path: Path, final_path: Path) -> None:
    os.replace(temp_path, final_path)


def _publish_pair(
    output_path: Path,
    output_content: bytes,
    dry_run_path: Path,
    dry_run_content: bytes,
) -> None:
    staged: list[Path] = []
    try:
        staged.append(_write_temp(output_path, output_content))
        staged.append(_write_temp(dry_run_path, dry_run_content))
    except BaseException:
        for path in staged:
            path.unlink(missing_ok=True)
        raise
    try:
        _replace_path(staged[0], output_path)
        _replace_path(staged[1], dry_run_path)
    finally:
        for path in staged:
            path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the pure M4-v2 nine-task resealed-input additive revision manifest."
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--temporal-source", type=Path, required=True)
    parser.add_argument("--joint-source", type=Path, required=True)
    parser.add_argument("--global-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", type=Path, required=True)
    args = parser.parse_args()

    resolved = [
        args.input.resolve(),
        args.temporal_source.resolve(),
        args.joint_source.resolve(),
        args.global_source.resolve(),
        args.output.resolve(),
        args.dry_run.resolve(),
    ]
    if len(set(resolved)) != len(resolved):
        raise SystemExit("builder inputs and outputs must be six distinct paths")

    manifest, dry_run = build_manifest(
        _load(args.input),
        temporal_source_contract_digest=_source_digest(
            args.temporal_source,
            field_name="temporal_source.artifact_digest",
        ),
        joint_source_contract_digest=_source_digest(
            args.joint_source,
            field_name="joint_source.artifact_digest",
        ),
        global_source_contract_digest=_source_digest(
            args.global_source,
            field_name="global_source.artifact_digest",
        ),
    )
    output_content = _serialized(manifest)
    dry_run_content = _serialized(dry_run)
    _publish_pair(args.output, output_content, args.dry_run, dry_run_content)
    print(json.dumps(dry_run, sort_keys=True))


if __name__ == "__main__":
    main()
