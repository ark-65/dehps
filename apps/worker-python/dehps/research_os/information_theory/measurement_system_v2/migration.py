from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from typing import Any

from dehps.contracts import canonical_digest
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
