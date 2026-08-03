from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.contracts import canonical_digest
from dehps.prediction.v2.contracts import load_json_object, seal_artifact
from dehps.prediction.v2.retirement import validate_activation
from dehps.research_os.models import ControlPlaneManifest

CUTOVER_TASK_KEY = "prediction-v2-shadow-scheduler-cutover-operator"
CUTOVER_CAPABILITY = "prediction_v2_shadow_live_activation_attestation"
CUTOVER_AUTHORITY_FACT = "operator_request:prediction-v2-live-cutover:approved"
LIVE_ACTIVATION_COMPLETION_FACT = "prediction-v2-shadow:LIVE_ACTIVATION:VERIFIED"
ACTIVATION_RELATIVE_PATH = "runtime/prediction-v2/legacy-retirement-activation.json"
COMPLETION_RELATIVE_PATH = "runtime/prediction-v2/live-cutover-completion.json"

_COMMIT = re.compile(r"^[0-9a-f]{40}$")


class PredictionV2ActivationBindingError(RuntimeError):
    pass


def _copy(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value))


def load_operator_completion(path: Path) -> tuple[dict[str, Any], str]:
    try:
        value = load_json_object(path)
    except (OSError, ValueError, TypeError) as exc:
        raise PredictionV2ActivationBindingError(
            f"cannot load Operator completion artifact: {path}"
        ) from exc
    return load_operator_completion_payload(value)


def persist_canonical_operator_completion(
    *,
    root_dir: Path,
    source_path: Path,
) -> tuple[Path, dict[str, Any], str]:
    completion, digest = load_operator_completion(source_path)
    destination = root_dir / COMPLETION_RELATIVE_PATH
    encoded = json.dumps(completion, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if destination.exists():
        if destination.read_text(encoding="utf-8") != encoded:
            raise PredictionV2ActivationBindingError(
                f"immutable Operator completion collision: {destination}"
            )
    else:
        atomic_write_text(destination, encoded)
    return destination, completion, digest


def build_live_activation_attestation(
    *,
    root_dir: Path,
    activation_path: str = ACTIVATION_RELATIVE_PATH,
    completion_path: str = COMPLETION_RELATIVE_PATH,
) -> dict[str, Any]:
    try:
        activation = validate_activation(
            load_json_object(root_dir / activation_path),
            root_dir=root_dir,
        )
        completion, completion_digest = load_operator_completion(
            root_dir / completion_path
        )
    except (OSError, TypeError, ValueError) as exc:
        raise PredictionV2ActivationBindingError(
            "live activation inputs are not verifiable"
        ) from exc
    legacy = completion["legacy_retirement"]
    prediction = completion["prediction_v2"]
    if legacy.get("activation_digest") != activation.get("artifact_digest"):
        raise PredictionV2ActivationBindingError(
            "Operator completion and retirement activation identities differ"
        )
    return seal_artifact(
        {
            "schema_version": "dehps-prediction-v2-live-activation-attestation.v1",
            "artifact_type": "PredictionV2LiveActivationAttestation.v1",
            "status": "VERIFIED",
            "operator_request": completion["operator_request"],
            "operator_execution_id": completion["operator_execution_id"],
            "operator_completion_payload_digest": completion_digest,
            "retirement_activation_digest": activation["artifact_digest"],
            "cutover_plan_digest": activation["cutover_plan_digest"],
            "legacy_lifecycle": legacy["status"],
            "legacy_compute": "STOPPED_AND_DISABLED",
            "legacy_artifacts": "PRESERVED_EXACTLY",
            "prediction_v2_mode": prediction["mode"],
            "prediction_v2_route": prediction["route"],
            "issue_task_state": prediction["issue_task_state"],
            "timers": {
                "pre_draw": prediction["pre_draw_timer"],
                "draw_sync": prediction["draw_sync_timer"],
            },
            "historical_evidence": "NOT_RUN",
            "evidence_progress_delta": 0,
            "promotion_gate_opened": False,
            "production_candidate_created": False,
            "m4_state_changed": False,
            "parent_digests": [
                activation["artifact_digest"],
                completion_digest,
                activation["cutover_plan_digest"],
            ],
        },
        domain="dehps.prediction-v2.live-activation-attestation.v1",
    )


def materialize_activation_binding_migration(
    *,
    root_dir: Path,
    base_manifest: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    completion_payload: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    before = _copy(base_manifest)
    before.pop("artifact_digest", None)
    before.pop("manifest_digest", None)
    source = _copy(source_manifest)
    source.pop("artifact_digest", None)
    source.pop("manifest_digest", None)
    source_tasks = {str(item.get("task_key")): item for item in source.get("tasks", [])}
    successor = source_tasks.get(CUTOVER_TASK_KEY)
    if successor is None or successor.get("requested_capability") != CUTOVER_CAPABILITY:
        raise PredictionV2ActivationBindingError(
            "source manifest lacks the activation-binding successor task"
        )
    try:
        activation = validate_activation(
            load_json_object(root_dir / ACTIVATION_RELATIVE_PATH),
            root_dir=root_dir,
        )
    except (OSError, TypeError, ValueError) as exc:
        raise PredictionV2ActivationBindingError(
            "retirement activation is not verifiable"
        ) from exc
    if completion_payload is None:
        completion, completion_digest = load_operator_completion(
            root_dir / COMPLETION_RELATIVE_PATH
        )
    else:
        completion = _copy(completion_payload)
        completion, completion_digest = load_operator_completion_payload(completion)
    if completion["legacy_retirement"].get("activation_digest") != activation["artifact_digest"]:
        raise PredictionV2ActivationBindingError(
            "migration completion and retirement activation identities differ"
        )
    successor = _copy(successor)
    successor["input_artifact_digests"] = [
        *successor.get("input_artifact_digests", []),
        activation["artifact_digest"],
        completion_digest,
    ]
    tasks = before.get("tasks")
    if not isinstance(tasks, list):
        raise PredictionV2ActivationBindingError("live manifest tasks are invalid")
    matches = [
        index
        for index, item in enumerate(tasks)
        if item.get("task_key") == CUTOVER_TASK_KEY
    ]
    if len(matches) != 1:
        raise PredictionV2ActivationBindingError(
            "live manifest must contain exactly one scheduler boundary task"
        )
    old_task = _copy(tasks[matches[0]])
    tasks[matches[0]] = successor
    facts = before.setdefault("facts", {})
    authorities = facts.setdefault("authorities", [])
    if CUTOVER_AUTHORITY_FACT not in authorities:
        authorities.append(CUTOVER_AUTHORITY_FACT)
    authorities.sort()
    report = verify_activation_binding_migration(
        original=base_manifest,
        migrated=before,
        source_successor=successor,
    )
    original_payload = _copy(base_manifest)
    original_payload.pop("manifest_digest", None)
    original_model = ControlPlaneManifest.from_dict(original_payload)
    successor_model = ControlPlaneManifest.from_dict(before)
    report["previous_task_digest"] = next(
        item.artifact_digest
        for item in original_model.tasks
        if item.task_key == CUTOVER_TASK_KEY
    )
    report["successor_task_digest"] = next(
        item.artifact_digest
        for item in successor_model.tasks
        if item.task_key == CUTOVER_TASK_KEY
    )
    report["old_requested_capability"] = old_task.get("requested_capability")
    return before, report


def load_operator_completion_payload(
    value: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    payload = _copy(value)
    # Reuse the file-backed validator without weakening its frozen contract.
    expected = {
        "schema_version": "dehps-prediction-v2-live-cutover-completion.v1",
        "artifact_type": "PredictionV2LiveCutoverCompletionArtifact.v1",
        "status": "OPERATION_COMPLETE",
    }
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            raise PredictionV2ActivationBindingError(
                f"Operator completion artifact mismatch: {key}"
            )
    # The remaining checks stay centralized by comparing a temporary-free clone.
    request_key = str(payload.get("operator_request") or "")
    if not request_key.startswith("operator_") or not isinstance(
        payload.get("operator_execution_id"), int
    ):
        raise PredictionV2ActivationBindingError(
            "Operator completion lacks typed request/execution identity"
        )
    source_commit = str(payload.get("source_commit") or "")
    if not _COMMIT.fullmatch(source_commit):
        raise PredictionV2ActivationBindingError(
            "Operator completion source commit is invalid"
        )
    for section in (
        "legacy_retirement",
        "prediction_v2",
        "m4_isolation",
        "evidence_boundary",
    ):
        if not isinstance(payload.get(section), Mapping):
            raise PredictionV2ActivationBindingError(
                "Operator completion sections are incomplete"
            )
    legacy = payload["legacy_retirement"]
    prediction = payload["prediction_v2"]
    isolation = payload["m4_isolation"]
    evidence = payload["evidence_boundary"]
    invariants = (
        legacy.get("status") == "LEGACY_FROZEN",
        legacy.get("compute_allowed") is False,
        legacy.get("preservation_check") == "EXACT_MATCH_TO_PREFLIGHT",
        prediction.get("mode") == "SHADOW_ONLY",
        prediction.get("route") == "BASELINE_ONLY",
        prediction.get("issue_task_state") == "ALL_FOUR_TASKS_COMPLETED",
        isolation.get("state_changed") is False,
        evidence.get("historical_evidence") == "NOT_RUN",
        evidence.get("evidence_progress_delta") == 0,
        evidence.get("promotion_gate_opened") is False,
        evidence.get("production_candidate_created") is False,
    )
    if not all(invariants):
        raise PredictionV2ActivationBindingError(
            "Operator completion payload invariant failed"
        )
    return payload, canonical_digest(
        payload,
        domain="dehps.prediction-v2.live-cutover-completion.v1",
    )


def verify_activation_binding_migration(
    *,
    original: Mapping[str, Any],
    migrated: Mapping[str, Any],
    source_successor: Mapping[str, Any],
) -> dict[str, Any]:
    before = _copy(original)
    before.pop("artifact_digest", None)
    before.pop("manifest_digest", None)
    after = _copy(migrated)
    after.pop("artifact_digest", None)
    after.pop("manifest_digest", None)
    ControlPlaneManifest.from_dict(before)
    ControlPlaneManifest.from_dict(after)
    if before.get("goals") != after.get("goals"):
        raise PredictionV2ActivationBindingError("activation migration changed goals")
    before_tasks = {str(item.get("task_key")): item for item in before.get("tasks", [])}
    after_tasks = {str(item.get("task_key")): item for item in after.get("tasks", [])}
    if set(before_tasks) != set(after_tasks):
        raise PredictionV2ActivationBindingError("activation migration changed task keys")
    for key in before_tasks.keys() - {CUTOVER_TASK_KEY}:
        if before_tasks[key] != after_tasks[key]:
            raise PredictionV2ActivationBindingError(
                f"activation migration changed existing task: {key}"
            )
    if after_tasks[CUTOVER_TASK_KEY] != dict(source_successor):
        raise PredictionV2ActivationBindingError(
            "activation migration successor task differs from source contract"
        )
    before_facts = before.get("facts", {})
    after_facts = after.get("facts", {})
    for fact_type in ("artifacts", "evidence", "external_events"):
        if before_facts.get(fact_type, []) != after_facts.get(fact_type, []):
            raise PredictionV2ActivationBindingError(
                f"activation migration changed {fact_type} facts"
            )
    expected_authorities = sorted(
        {*before_facts.get("authorities", []), CUTOVER_AUTHORITY_FACT}
    )
    if sorted(after_facts.get("authorities", [])) != expected_authorities:
        raise PredictionV2ActivationBindingError(
            "activation migration authority allowlist changed"
        )
    return {
        "schema_version": "dehps-prediction-v2-activation-binding-migration.v1",
        "status": "VERIFIED",
        "goals_deleted": 0,
        "tasks_deleted": 0,
        "existing_tasks_rewritten": 0,
        "allowlisted_task_revisions": [CUTOVER_TASK_KEY],
        "facts_deleted": 0,
        "authority_facts_added": [CUTOVER_AUTHORITY_FACT],
        "evidence_progress_delta": 0,
        "promotion_gate_opened": False,
        "m4_state_changed": False,
    }
