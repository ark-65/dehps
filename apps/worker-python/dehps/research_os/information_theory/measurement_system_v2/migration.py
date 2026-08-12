from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.models import ControlPlaneManifest, stable_json


class AdditiveManifestMigrationError(RuntimeError):
    pass


STATE_FIELDS = (
    "status",
    "completion_classification",
    "superseded_by_task_digest",
)
GOAL_STATE_FIELDS = (
    "status",
    "retired_at",
    "superseded_by_goal_digest",
)
M4_V2_VERSIONED_SUCCESSOR_SOURCE_FACTS = {
    "TEMPORAL_MARGINAL_INCREMENT": {
        "historical": (
            "m4-v2-temporal-marginal-increment-contract:"
            "M4_MEASUREMENT_CONTRACT_V2:FROZEN"
        ),
        "active": (
            "m4-v2-temporal-marginal-increment-contract-v3:"
            "M4_MEASUREMENT_CONTRACT_V2:FROZEN"
        ),
    },
    "JOINT_RESIDUAL_INCREMENT": {
        "historical": (
            "m4-v2-joint-residual-increment-contract:"
            "M4_MEASUREMENT_CONTRACT_V2:FROZEN"
        ),
        "active": (
            "m4-v2-joint-residual-increment-contract-v3:"
            "M4_MEASUREMENT_CONTRACT_V2:FROZEN"
        ),
    },
}

M4_V2_RECOVERY_INPUT_MANIFEST_DIGEST = (
    "94f7e6448fa1572802a050129d09c8bd679772afc62f31f0d1dc2544d098c58a"
)
M4_V2_RECOVERY_INPUT_SNAPSHOT_DIGEST = (
    "85be3d0edf17b94510d68da6b5b8bfe1c73583222a8bc2822cb7e46bee08f4e3"
)
M4_V2_FAILED_TASK_KEY = "m4-v2-marginal-static-historical-identity-adoption"
M4_V2_RECOVERY_TASK_KEY = (
    "m4-v2-marginal-static-historical-identity-adoption-recovery-v1"
)
M4_V2_FAILED_EXECUTION_ID = (
    "43eed4c903a59595336b514f17c3be318714535e3b61341ae3a492f03fb4e488"
)
M4_V2_FAILED_EVENT_MANIFEST_DIGEST = (
    "79a8abb17bb705ab21350d6d3df882bbd39d89c3b7d2a3e9e5fa4f3c43046966"
)
M4_V2_FAILED_CAPABILITY = "m4_v2_marginal_static_historical_identity_adoption"
M4_V2_FAILED_EVENT_METADATA = (
    (
        0,
        "started",
        "dfae9cbce68c931b7e0b715223623a4e7691cbb2613b0f6ef3dbdb00deb550a3",
    ),
    (
        1,
        "failed",
        "8291bed8402c539f416f9c8d8a23c2f59800ff544d7b5ca90a5f3878d6ef665f",
    ),
)
M4_V2_ORIGINAL_TASK_DEFINITIONS = (
    (
        M4_V2_FAILED_TASK_KEY,
        "6f21824945ebdf8e19dcd946ffbc6260f8e28fc52555a5060422f152d37677fd",
    ),
    (
        "m4-v2-marginal-static-historical-branch-decision-replay",
        "ee575d4109b055e1988ae493e2a6a913704624d8e611063f707aed08d34e344e",
    ),
    (
        "m4-v2-temporal-marginal-increment-historical-measurement-design",
        "6dac3ba04bbd3177ce5fd19f1be2a1339f17d91797371ebac238c7b7bc13553a",
    ),
    (
        "m4-v2-temporal-marginal-increment-historical-measurement-preregistration",
        "abaf397c80a620310796e1190c89ac3f97c67b81fdcf48b2a1aa2f263e26b83f",
    ),
    (
        "m4-v2-temporal-marginal-increment-historical-measurement-gate-compiler",
        "fec3b8f121e30dd17e8691e0988cfdcdc6f694048e8e64314280bdadbdb70e7f",
    ),
    (
        "m4-v2-temporal-marginal-increment-historical-branch-decision-replay",
        "c604ff59b9d10354c0205b2174c54ad3a4d4839de6602636c2822e6c06c2251a",
    ),
    (
        "m4-v2-joint-residual-increment-historical-measurement-design",
        "5b99c388bcbf2f6edc94b798d44d18d0e62b4618ae449cd994a18f81f42dce3c",
    ),
    (
        "m4-v2-joint-residual-increment-historical-measurement-preregistration",
        "3747796049a496e39f1ea0b675b05b53553ee46c1d782ee1b3faa48d273af2f3",
    ),
    (
        "m4-v2-joint-residual-increment-historical-measurement-gate-compiler",
        "ee3508c6ebee7b552b2931f01d8f5dc4a396f12361c9037d49552c59922ec7c3",
    ),
    (
        "m4-v2-joint-residual-increment-historical-branch-decision-replay",
        "fd67e804ca63b7b694933ee1c6e7b909f128ece37c13c331b149da967a6f299d",
    ),
    (
        "m4-v2-global-routing",
        "e9857fa7f4f5e84fb8e096c60e4622bfef62691141416eeea82d36e0760d6d68",
    ),
)


def require_versioned_successor_source_fact_retention(
    artifact_facts: Iterable[str],
) -> None:
    """Reject an active v3 source fact that displaced its historical v2 fact."""

    facts = set(artifact_facts)
    for branch_id, identities in M4_V2_VERSIONED_SUCCESSOR_SOURCE_FACTS.items():
        if identities["active"] in facts and identities["historical"] not in facts:
            raise AdditiveManifestMigrationError(
                f"manifest_migration_historical_source_fact_missing:{branch_id}"
            )


def require_sha256_digest(value: object, *, field_name: str) -> str:
    """Return a canonical lowercase SHA-256 digest or fail closed."""

    digest = str(value or "")
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise AdditiveManifestMigrationError(
            f"manifest_migration_digest_invalid:{field_name}"
        )
    return digest


def build_additive_m4_v2_manifest(
    *,
    live_payload: Mapping[str, Any],
    source_payload: Mapping[str, Any],
    allowlisted_new_goal_keys: Iterable[str],
    allowlisted_new_task_keys: Iterable[str],
    allowlisted_revised_task_keys: Iterable[str],
    add_artifact_facts: Iterable[str],
    add_external_events: Iterable[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Merge source definitions into live truth without copying source states/facts."""

    live = deepcopy(dict(live_payload))
    source = deepcopy(dict(source_payload))
    ControlPlaneManifest.from_dict(live)
    ControlPlaneManifest.from_dict(source)
    live.pop("artifact_digest", None)
    source.pop("artifact_digest", None)
    live.pop("manifest_digest", None)
    source.pop("manifest_digest", None)
    requested_artifact_facts = set(add_artifact_facts)
    requested_external_events = set(add_external_events)
    normalized_live = ControlPlaneManifest.from_dict(live).to_dict(include_digest=False)
    normalized_source = ControlPlaneManifest.from_dict(source).to_dict(
        include_digest=False
    )
    live_goals = {str(item["goal_key"]): item for item in live.get("goals", [])}
    source_goals = {str(item["goal_key"]): item for item in source.get("goals", [])}
    requested_new_goal_keys = set(allowlisted_new_goal_keys)
    if not requested_new_goal_keys.issubset(source_goals):
        raise AdditiveManifestMigrationError(
            "manifest_migration_new_goal_allowlist_invalid"
        )
    existing_new_goal_keys = requested_new_goal_keys.intersection(live_goals)
    new_goal_keys = requested_new_goal_keys - existing_new_goal_keys
    normalized_live_goals = {
        str(item["goal_key"]): item for item in normalized_live["goals"]
    }
    normalized_source_goals = {
        str(item["goal_key"]): item for item in normalized_source["goals"]
    }
    for key, goal in normalized_live_goals.items():
        live_definition = {
            field: value
            for field, value in goal.items()
            if field not in GOAL_STATE_FIELDS
        }
        source_definition = {
            field: value
            for field, value in normalized_source_goals.get(key, {}).items()
            if field not in GOAL_STATE_FIELDS
        }
        if key not in source_goals or stable_json(live_definition) != stable_json(
            source_definition
        ):
            raise AdditiveManifestMigrationError(
                f"manifest_migration_goal_definition_changed:{key}"
            )
    live_tasks = {str(item["task_key"]): item for item in live.get("tasks", [])}
    normalized_live_tasks = {
        str(item["task_key"]): item for item in normalized_live["tasks"]
    }
    source_tasks = {str(item["task_key"]): item for item in source.get("tasks", [])}
    requested_new_keys = set(allowlisted_new_task_keys)
    revised_keys = set(allowlisted_revised_task_keys)
    if requested_new_keys.intersection(revised_keys):
        raise AdditiveManifestMigrationError(
            "manifest_migration_task_allowlists_overlap"
        )
    if not requested_new_keys.issubset(source_tasks) or not revised_keys.issubset(
        live_tasks.keys() & source_tasks.keys()
    ):
        raise AdditiveManifestMigrationError(
            "manifest_migration_allowlist_cannot_be_resolved"
        )
    existing_new_keys = requested_new_keys.intersection(live_tasks)
    new_keys = requested_new_keys - existing_new_keys
    normalized_source_tasks = {
        str(item["task_key"]): item for item in normalized_source["tasks"]
    }
    for key in sorted(existing_new_keys):
        live_definition = {
            field: value
            for field, value in normalized_live_tasks[key].items()
            if field not in STATE_FIELDS
        }
        source_definition = {
            field: value
            for field, value in normalized_source_tasks[key].items()
            if field not in STATE_FIELDS
        }
        if stable_json(live_definition) != stable_json(source_definition):
            raise AdditiveManifestMigrationError(
                f"manifest_migration_existing_new_task_changed:{key}"
            )

    output_tasks: list[dict[str, Any]] = []
    unchanged_task_keys: list[str] = []
    for live_task in live.get("tasks", []):
        key = str(live_task["task_key"])
        if key not in revised_keys:
            output_tasks.append(deepcopy(live_task))
            unchanged_task_keys.append(key)
            continue
        replacement = deepcopy(source_tasks[key])
        for field in STATE_FIELDS:
            if field in live_task:
                replacement[field] = deepcopy(live_task[field])
            else:
                replacement.pop(field, None)
        output_tasks.append(replacement)
    for source_task in source.get("tasks", []):
        if source_task["task_key"] in new_keys:
            output_tasks.append(deepcopy(source_task))

    output = {
        "schema_version": live["schema_version"],
        "goals": [
            *deepcopy(live["goals"]),
            *(deepcopy(source_goals[key]) for key in sorted(new_goal_keys)),
        ],
        "tasks": output_tasks,
        "facts": deepcopy(live["facts"]),
    }
    original_facts = deepcopy(output["facts"])
    existing_artifact_facts = requested_artifact_facts.intersection(
        output["facts"]["artifacts"]
    )
    existing_external_events = requested_external_events.intersection(
        output["facts"]["external_events"]
    )
    new_artifact_facts = requested_artifact_facts - existing_artifact_facts
    new_external_events = requested_external_events - existing_external_events
    output["facts"]["artifacts"] = sorted(
        set(output["facts"]["artifacts"]).union(requested_artifact_facts)
    )
    output["facts"]["external_events"] = sorted(
        set(output["facts"]["external_events"]).union(requested_external_events)
    )
    require_versioned_successor_source_fact_retention(output["facts"]["artifacts"])
    manifest = ControlPlaneManifest.from_dict(output)
    normalized = manifest.to_dict(include_digest=True)

    normalized_tasks = {str(item["task_key"]): item for item in normalized["tasks"]}
    normalized_goals = {str(item["goal_key"]): item for item in normalized["goals"]}
    for key, goal in normalized_live_goals.items():
        if stable_json(normalized_goals[key]) != stable_json(goal):
            raise AdditiveManifestMigrationError(
                f"manifest_migration_rewrote_goal_state:{key}"
            )
    for key in unchanged_task_keys:
        if stable_json(normalized_tasks[key]) != stable_json(
            normalized_live_tasks[key]
        ):
            raise AdditiveManifestMigrationError(
                f"manifest_migration_rewrote_existing_task:{key}"
            )
    for key in revised_keys:
        for field in STATE_FIELDS:
            if normalized_tasks[key].get(field) != normalized_live_tasks[key].get(
                field
            ):
                raise AdditiveManifestMigrationError(
                    f"manifest_migration_rewrote_task_state:{key}:{field}"
                )
    for fact_type, values in original_facts.items():
        if not set(values).issubset(normalized["facts"][fact_type]):
            raise AdditiveManifestMigrationError(
                f"manifest_migration_deleted_fact:{fact_type}"
            )

    dry_run: dict[str, Any] = {
        "schema_version": "dehps-m4-v2-additive-manifest-migration-dry-run.v1",
        "artifact_type": "m4_v2_manifest_migration_dry_run",
        "artifact_digest": "",
        "status": "VERIFIED",
        "live_goal_count": len(live["goals"]),
        "new_goal_keys": sorted(new_goal_keys),
        "requested_new_goal_keys": sorted(requested_new_goal_keys),
        "already_present_new_goal_keys": sorted(existing_new_goal_keys),
        "live_task_count": len(live["tasks"]),
        "output_task_count": len(normalized["tasks"]),
        "new_task_keys": sorted(new_keys),
        "requested_new_task_keys": sorted(requested_new_keys),
        "already_present_new_task_keys": sorted(existing_new_keys),
        "revised_task_keys": sorted(revised_keys),
        "unchanged_task_count": len(unchanged_task_keys),
        "existing_goal_deletions": 0,
        "existing_task_deletions": 0,
        "existing_state_regressions": 0,
        "existing_fact_deletions": 0,
        "unallowlisted_definition_rewrites": 0,
        "added_artifact_facts": sorted(new_artifact_facts),
        "requested_artifact_facts": sorted(requested_artifact_facts),
        "already_present_artifact_facts": sorted(existing_artifact_facts),
        "added_external_events": sorted(new_external_events),
        "requested_external_events": sorted(requested_external_events),
        "already_present_external_events": sorted(existing_external_events),
        "output_manifest_digest": manifest.artifact_digest,
        "import_performed": False,
        "production_action": "none",
        "promotion_gate_opened": False,
    }
    identity = dict(dry_run)
    identity.pop("artifact_digest")
    dry_run["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.v2.additive-manifest-migration-dry-run.v1",
    )
    return normalized, dry_run


def build_additive_task_manifest(
    *,
    live_payload: Mapping[str, Any],
    new_tasks: Sequence[Mapping[str, Any]],
    revised_tasks: Sequence[Mapping[str, Any]] = (),
    add_artifact_facts: Iterable[str] = (),
    add_external_events: Iterable[str] = (),
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build an idempotent additive task-only manifest revision.

    The supplied task definitions are the complete immutable target
    definitions.  Existing state remains owned by ``live_payload``; callers
    cannot use a repeated build to reset a task, replace history, or synthesize
    completion.  Repeating an identical build returns the same manifest bytes,
    while any definition drift fails closed in
    :func:`build_additive_m4_v2_manifest`.
    """

    live = deepcopy(dict(live_payload))
    ControlPlaneManifest.from_dict(live)
    live.pop("artifact_digest", None)
    live.pop("manifest_digest", None)

    def indexed(
        values: Sequence[Mapping[str, Any]], *, label: str
    ) -> dict[str, dict[str, Any]]:
        output: dict[str, dict[str, Any]] = {}
        for raw in values:
            item = deepcopy(dict(raw))
            key = str(item.get("task_key") or "").strip()
            if not key or key in output:
                raise AdditiveManifestMigrationError(
                    f"manifest_migration_{label}_task_identity_invalid:{key}"
                )
            output[key] = item
        return output

    new_by_key = indexed(new_tasks, label="new")
    revised_by_key = indexed(revised_tasks, label="revised")
    if set(new_by_key).intersection(revised_by_key):
        raise AdditiveManifestMigrationError(
            "manifest_migration_task_allowlists_overlap"
        )

    source = deepcopy(live)
    source_tasks = {
        str(item["task_key"]): deepcopy(item) for item in source.get("tasks", [])
    }
    source_order = [str(item["task_key"]) for item in source.get("tasks", [])]
    for key, task in revised_by_key.items():
        if key not in source_tasks:
            raise AdditiveManifestMigrationError(
                f"manifest_migration_revised_task_missing:{key}"
            )
        source_tasks[key] = task
    for key, task in new_by_key.items():
        source_tasks[key] = task
        if key not in source_order:
            source_order.append(key)
    source["tasks"] = [source_tasks[key] for key in source_order]

    return build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=tuple(new_by_key),
        allowlisted_revised_task_keys=tuple(revised_by_key),
        add_artifact_facts=add_artifact_facts,
        add_external_events=add_external_events,
    )


def build_failed_task_recovery_manifest(
    *,
    live_payload: Mapping[str, Any],
    recovery_task: Mapping[str, Any],
    revised_tasks: Sequence[Mapping[str, Any]],
    add_artifact_facts: Iterable[str] = (),
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Replace the frozen failed active slot without rewriting durable history.

    This pure builder validates the exact post-failure recovery input.  The
    repository import remains the sole transactional writer: because the old
    failed key is absent from the successor manifest and the recovery key is
    new, its immutable definition, failed state, execution and events remain
    addressable while the first unexecuted definition receives an ordinary
    same-key revision.  The remaining builders continue the same-key revision
    chain from this validated recovery root.
    """

    live = deepcopy(dict(live_payload))
    manifest = ControlPlaneManifest.from_dict(live)
    if manifest.artifact_digest != M4_V2_RECOVERY_INPUT_MANIFEST_DIGEST:
        raise AdditiveManifestMigrationError(
            "manifest_recovery_input_manifest_digest_changed"
        )
    snapshot = ResearchOSControlPlane().resolve(manifest)
    if snapshot.snapshot_digest != M4_V2_RECOVERY_INPUT_SNAPSHOT_DIGEST:
        raise AdditiveManifestMigrationError(
            "manifest_recovery_input_snapshot_digest_changed"
        )
    if snapshot.ready_queue:
        raise AdditiveManifestMigrationError("manifest_recovery_ready_queue_not_empty")

    tasks = list(manifest.tasks)
    by_key = {task.task_key: task for task in tasks}
    actual = tuple(
        (key, by_key[key].artifact_digest)
        for key, _ in M4_V2_ORIGINAL_TASK_DEFINITIONS
        if key in by_key
    )
    if actual != M4_V2_ORIGINAL_TASK_DEFINITIONS:
        raise AdditiveManifestMigrationError(
            "manifest_recovery_original_task_definitions_changed"
        )
    failed_task = by_key[M4_V2_FAILED_TASK_KEY]
    failed_state = manifest.task_state_by_digest[failed_task.artifact_digest]
    if (
        failed_state.declared_status.value != "failed"
        or (
            failed_state.completion_classification is None
            or failed_state.completion_classification.value != "INTEGRATED"
        )
        or failed_state.superseded_by_task_digest is not None
    ):
        raise AdditiveManifestMigrationError(
            "manifest_recovery_failed_task_state_changed"
        )

    recovery = deepcopy(dict(recovery_task))
    if recovery.get("task_key") != M4_V2_RECOVERY_TASK_KEY:
        raise AdditiveManifestMigrationError(
            "manifest_recovery_successor_task_key_changed"
        )
    revised_by_key = {
        str(item.get("task_key") or ""): deepcopy(dict(item))
        for item in revised_tasks
    }
    expected_revised = {
        "m4-v2-marginal-static-historical-branch-decision-replay"
    }
    if set(revised_by_key) != expected_revised:
        raise AdditiveManifestMigrationError(
            "manifest_recovery_revised_task_keys_changed"
        )
    if M4_V2_RECOVERY_TASK_KEY in by_key:
        raise AdditiveManifestMigrationError(
            "manifest_recovery_successor_already_present"
        )

    normalized_live = manifest.to_dict(include_digest=False)
    output_tasks: list[dict[str, Any]] = []
    for task in normalized_live["tasks"]:
        key = str(task["task_key"])
        if key == M4_V2_FAILED_TASK_KEY:
            output_tasks.append(recovery)
        elif key in revised_by_key:
            replacement = revised_by_key[key]
            for field in STATE_FIELDS:
                if field in task:
                    replacement[field] = deepcopy(task[field])
                else:
                    replacement.pop(field, None)
            output_tasks.append(replacement)
        else:
            output_tasks.append(deepcopy(task))

    facts = deepcopy(normalized_live["facts"])
    facts["artifacts"] = sorted(
        set(facts["artifacts"]).union(str(value) for value in add_artifact_facts)
    )
    require_versioned_successor_source_fact_retention(facts["artifacts"])
    output = {
        "schema_version": normalized_live["schema_version"],
        "goals": deepcopy(normalized_live["goals"]),
        "tasks": output_tasks,
        "facts": facts,
    }
    successor = ControlPlaneManifest.from_dict(output)
    normalized = successor.to_dict(include_digest=True)
    successor_snapshot = ResearchOSControlPlane().resolve(successor)
    ready_keys = tuple(item.task_key for item in successor_snapshot.ready_queue)
    if ready_keys != (M4_V2_RECOVERY_TASK_KEY,):
        raise AdditiveManifestMigrationError(
            "manifest_recovery_successor_not_unique_ready"
        )

    dry_run: dict[str, Any] = {
        "schema_version": "dehps-m4-v2-failed-task-recovery-migration-dry-run.v1",
        "artifact_type": "m4_v2_failed_task_recovery_migration_dry_run",
        "artifact_digest": "",
        "status": "VERIFIED",
        "input_manifest_digest": manifest.artifact_digest,
        "input_snapshot_digest": snapshot.snapshot_digest,
        "input_ready_task_keys": [],
        "old_failed_task_key": M4_V2_FAILED_TASK_KEY,
        "old_failed_task_digest": failed_task.artifact_digest,
        "old_failed_task_preserved_in_durable_history": True,
        "old_failed_task_present_in_active_manifest": False,
        "recovery_task_key": M4_V2_RECOVERY_TASK_KEY,
        "new_task_count": 1,
        "revised_same_key_count": 1,
        "revised_task_keys": sorted(revised_by_key),
        "output_manifest_digest": successor.artifact_digest,
        "output_snapshot_digest": successor_snapshot.snapshot_digest,
        "output_ready_task_keys": list(ready_keys),
        "import_performed": False,
        "production_action": "none",
        "promotion_gate_opened": False,
        "p3_folds": 0,
    }
    identity = dict(dry_run)
    identity.pop("artifact_digest")
    dry_run["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.v2.failed-task-recovery-migration-dry-run.v1",
    )
    return normalized, dry_run


def verify_failed_task_recovery_event_metadata(
    event_metadata: Sequence[Mapping[str, Any]],
) -> None:
    """Bind the result-blind durable execution/event projection before recovery."""

    observed = tuple(
        (
            int(item.get("sequence", -1)),
            str(item.get("event_type") or ""),
            str(item.get("event_digest") or ""),
            str(item.get("execution_id") or ""),
            str(item.get("task_key") or ""),
            str(item.get("task_digest") or ""),
            str(item.get("control_plane_key") or ""),
            str(item.get("manifest_digest") or ""),
            str(item.get("capability") or ""),
        )
        for item in event_metadata
    )
    expected = tuple(
        (
            sequence,
            event_type,
            event_digest,
            M4_V2_FAILED_EXECUTION_ID,
            M4_V2_FAILED_TASK_KEY,
            M4_V2_ORIGINAL_TASK_DEFINITIONS[0][1],
            "m4-information-theory-mainline",
            M4_V2_FAILED_EVENT_MANIFEST_DIGEST,
            M4_V2_FAILED_CAPABILITY,
        )
        for sequence, event_type, event_digest in M4_V2_FAILED_EVENT_METADATA
    )
    if observed != expected:
        raise AdditiveManifestMigrationError(
            "manifest_recovery_failed_execution_event_metadata_changed"
        )
