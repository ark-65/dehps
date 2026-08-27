from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_artifacts as artifacts,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_contract as contract,
)
from dehps.research_os.models import ControlPlaneManifest

RESEARCH_APPROVAL_AUTHORITY = "agent-request:694:approved:decision-2925"
OPERATOR_CONFIGURATION_AUTHORITY = (
    "m4-isolated-24h-challenger-v11:operator-mail-configuration-authorized"
)


class IsolatedManifestError(contract.IsolatedChallengerContractError):
    pass


def _task_dependency(key: str) -> dict[str, str]:
    return {
        "dependency_type": "task",
        "target_key": key,
        "required_status": "completed",
    }


def _artifact_dependency(fact: str) -> dict[str, str]:
    return {
        "dependency_type": "artifact",
        "target_key": fact,
        "required_status": "available",
    }


def _external_dependency(event: str) -> dict[str, str]:
    return {
        "dependency_type": "external_event",
        "target_key": event,
        "required_status": "observed",
    }


def _authority_dependency(authority: str) -> dict[str, str]:
    return {
        "dependency_type": "authority",
        "target_key": authority,
        "required_status": "approved",
    }


def _dependency_names(name: str) -> tuple[tuple[str, str], ...]:
    return {
        "preregistration": (("authority", RESEARCH_APPROVAL_AUTHORITY),),
        "operator_attestation": (
            ("artifact", contract.FREEZE_FACT),
            ("authority", OPERATOR_CONFIGURATION_AUTHORITY),
        ),
        "incident_head_genesis": (("artifact", contract.FREEZE_FACT),),
        "mail_configuration": (
            ("artifact", contract.FREEZE_FACT),
            ("artifact", contract.OPERATOR_ATTESTATION_FACT),
        ),
        "target_issue_projection": (
            ("artifact", contract.FREEZE_FACT),
            ("external", "TARGET_PROJECTION_INPUT"),
        ),
        "history_snapshot": (("task_fact", "target_issue_projection:COMPLETE"),),
        "genesis": (
            ("task_fact", "history_snapshot:COMPLETE"),
            ("artifact", contract.MAIL_CONFIGURATION_FACT),
        ),
        "genesis_replay": (("task", "genesis"),),
        "search_batch": (
            ("task_fact", "genesis_replay:REGISTERED_REPLAY_VERIFIED"),
            ("artifact", contract.MAIL_CONFIGURATION_FACT),
            ("external", "RESOURCE_QUIESCENT_60S"),
        ),
        "search_batch_replay": (("task", "search_batch"),),
        "search_checkpoint": (
            ("task_fact", "search_batch_replay:REGISTERED_REPLAY_VERIFIED"),
        ),
        "search_checkpoint_replay": (("task", "search_checkpoint"),),
        "runtime_health": (("artifact", contract.FREEZE_FACT),),
        "multiplicity_risk_limit": (("external", "CAPACITY_BELOW_18"),),
        "multiplicity_seal": (
            ("task_fact", "history_snapshot:COMPLETE"),
            ("task_fact", "search_checkpoint_replay:REGISTERED_REPLAY_VERIFIED"),
            ("external", "SELECTION_CUTOFF"),
        ),
        "eligibility": (("task_fact", "multiplicity_seal:COMPLETE"),),
        "challenger_freeze": (
            ("task_fact", "eligibility:COMPLETE"),
            ("external", "FREEZE_DEADLINE"),
        ),
        "random_baseline_freeze": (("task_fact", "challenger_freeze:FROZEN"),),
        "random_baseline_freeze_replay": (("task", "random_baseline_freeze"),),
        "prediction": (
            ("task_fact", "challenger_freeze:FROZEN"),
            (
                "task_fact",
                "random_baseline_freeze_replay:REGISTERED_REPLAY_VERIFIED",
            ),
        ),
        "prediction_replay": (("task", "prediction"),),
        "predraw_mail_envelope": (
            ("task_fact", "prediction_replay:REGISTERED_REPLAY_VERIFIED"),
            ("external", "PREDRAW_SEND"),
        ),
        "predraw_mail_replay": (("task", "predraw_mail_envelope"),),
        "predraw_delivery": (
            ("task_fact", "predraw_mail_replay:REGISTERED_REPLAY_VERIFIED"),
            ("artifact", contract.MAIL_CONFIGURATION_FACT),
        ),
        "settlement": (
            ("task_fact", "prediction_replay:REGISTERED_REPLAY_VERIFIED"),
            ("external", "AUDITED_DRAW"),
        ),
        "random_baseline_settlement": (
            ("task_fact", "settlement:COMPLETE"),
            (
                "task_fact",
                "random_baseline_freeze_replay:REGISTERED_REPLAY_VERIFIED",
            ),
        ),
        "formal_p3_comparison_input": (
            ("task_fact", "settlement:COMPLETE"),
        ),
        "formal_p3_comparison": (
            ("task_fact", "formal_p3_comparison_input:RESOLVED"),
        ),
        "settlement_report": (
            ("task_fact", "settlement:COMPLETE"),
            ("task_fact", "random_baseline_settlement:COMPLETE"),
            ("task_fact", "formal_p3_comparison:RESOLVED"),
        ),
        "settlement_replay": (("task", "settlement_report"),),
        "post_mail_envelope": (
            ("task_fact", "settlement_replay:REGISTERED_REPLAY_VERIFIED"),
        ),
        "post_mail_replay": (("task", "post_mail_envelope"),),
        "post_delivery": (
            ("task_fact", "post_mail_replay:REGISTERED_REPLAY_VERIFIED"),
            ("artifact", contract.MAIL_CONFIGURATION_FACT),
        ),
        "daily_summary": (
            ("external", "DAILY_SEND"),
            ("task_fact", "incident_head_genesis:COMPLETE"),
        ),
        "daily_summary_replay": (("task", "daily_summary"),),
        "daily_mail_envelope": (
            ("task_fact", "daily_summary_replay:REGISTERED_REPLAY_VERIFIED"),
        ),
        "daily_mail_replay": (("task", "daily_mail_envelope"),),
        "daily_delivery": (
            ("task_fact", "daily_mail_replay:REGISTERED_REPLAY_VERIFIED"),
            ("artifact", contract.MAIL_CONFIGURATION_FACT),
        ),
        "incident_open": (
            ("task_fact", "incident_head_genesis:COMPLETE"),
            ("external", "INCIDENT_OPEN"),
        ),
        "incident_envelope": (("task_fact", "incident_open:OPEN"),),
        "incident_mail_replay": (("task", "incident_envelope"),),
        "incident_delivery": (
            ("task_fact", "incident_mail_replay:REGISTERED_REPLAY_VERIFIED"),
            ("artifact", contract.MAIL_CONFIGURATION_FACT),
        ),
    }.get(name, ())


def _dependencies(
    template: contract.TaskTemplate,
    *,
    key_by_name: Mapping[str, str],
    context: Mapping[str, str],
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for dependency_type, target in _dependency_names(template.name):
        if dependency_type == "task":
            output.append(_task_dependency(key_by_name[target]))
        elif dependency_type == "task_fact":
            name, suffix = target.split(":", 1)
            target_key = key_by_name[name]
            if template.name == "multiplicity_seal" and name == "search_checkpoint_replay":
                cut_ref = context["cut_checkpoint_ref"]
                if cut_ref == "GENESIS":
                    target_key = key_by_name["genesis_replay"]
                else:
                    cut_context = {**dict(context), "batch_seq": cut_ref}
                    target_key = contract.task_template_by_name(
                        "search_checkpoint_replay"
                    ).key(cut_context)
            if (
                template.name == "search_batch"
                and name == "genesis_replay"
                and int(context["batch_seq"]) > 0
            ):
                previous_context = {
                    **dict(context),
                    "batch_seq": f"{int(context['batch_seq']) - 1:012d}",
                }
                target_key = contract.task_template_by_name(
                    "search_checkpoint_replay"
                ).key(previous_context)
            output.append(_artifact_dependency(f"{target_key}:{suffix}"))
        elif dependency_type == "artifact":
            output.append(_artifact_dependency(target))
        elif dependency_type == "external":
            output.append(_external_dependency(target))
        elif dependency_type == "authority":
            output.append(_authority_dependency(target))
        else:
            raise IsolatedManifestError("dependency_type_not_frozen")
    return output


def _task_payload(
    *,
    template: contract.TaskTemplate,
    task_key: str,
    key_by_name: Mapping[str, str],
    context: Mapping[str, str],
    source_digest: str,
    priority: int,
) -> dict[str, Any]:
    return {
        "task_key": task_key,
        "goal_key": contract.GOAL_KEY,
        "task_type": f"m4_isolated_v11_{template.name}",
        "lane": "research",
        "dependencies": _dependencies(
            template, key_by_name=key_by_name, context=context
        ),
        "priority": priority,
        "input_artifact_digests": [source_digest],
        "requested_capability": template.capability,
        "metric_contract": {
            "lineage_id": contract.LINEAGE_ID,
            "contract_digest": contract.CONTRACT_DIGEST,
            "source_contract_digest": source_digest,
            "task_template": template.name,
            "task_group": template.group,
            "activation_mode": template.activation_mode,
            "ordered_artifact_outputs": list(template.artifact_types),
            "status_projection": template.status_projection,
            "render_context": dict(context),
            "worker_count": contract.WORKER_COUNT,
            "formal_p3_write_access": "FORBIDDEN",
            "promotion_authority": "NONE",
        },
        "status": "draft",
        "completion_classification": "INTEGRATION_PENDING",
    }


def _goal(*, context: Mapping[str, str], source_digest: str) -> dict[str, Any]:
    return {
        "goal_key": contract.GOAL_KEY,
        "semantic_version": "11.0.0",
        "objective_class": "prediction_quality",
        "success_evidence": [
            "42 exact task templates traverse Resolver, Ready Queue and Supervisor",
            "single-worker and 18-worker result bytes match",
            (
                "predraw, postdraw and daily external provider-ACK receipts replay; "
                "incident mail is simulation-replayed and sends externally on a real fault"
            ),
            "Formal P3 source, status, artifacts, facts and delivery ledger stay unchanged",
        ],
        "owner_lane": "research",
        "question": (
            "Can an isolated deterministic 24-hour challenger factory produce "
            "replayable research-only Top-100 portfolios without changing Formal P3?"
        ),
        "baseline_metric_manifest": {
            "isolated_factory": "NOT_REGISTERED",
            "formal_p3": contract.FORMAL_P3_REQUIRED_STATUS,
            "formal_p3_source_digest": contract.FORMAL_P3_SOURCE_DIGEST,
        },
        "target_metric_manifest": {
            "lineage_id": contract.LINEAGE_ID,
            "contract_digest": contract.CONTRACT_DIGEST,
            "source_contract_digest": source_digest,
            "source_max_issue": context["source_max_issue"],
            "target_issue": context["target_issue"],
            "worker_count": contract.WORKER_COUNT,
            "lifetime_multiplicity_limit": contract.LIFETIME_MULTIPLICITY_LIMIT,
            "cost_cny": "200.00",
            "mail_configuration_required": True,
        },
        "guardrails": [
            "RESEARCH_ONLY",
            "SHADOW",
            "strict_prior_only",
            "mail_configuration_before_search",
            "formal_p3_read_only_and_preemptive_priority",
            "no_p4_p5_p6_or_promotion",
        ],
        "status": "active",
    }


def build_manifest(
    *,
    context: Mapping[str, str],
    source_digest: str,
    operator_configuration_authorized: bool = False,
    simulation_events: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_digest = contract.require_digest(source_digest, field="source_digest")
    keys = contract.rendered_task_keys(context)
    key_by_name = {
        template.name: key
        for template, key in zip(contract.TASK_TEMPLATES, keys, strict=True)
    }
    tasks: list[dict[str, Any]] = []
    for priority, (template, task_key) in enumerate(
        zip(contract.TASK_TEMPLATES, keys, strict=True), start=1
    ):
        tasks.append(
            _task_payload(
                template=template,
                task_key=task_key,
                key_by_name=key_by_name,
                context=context,
                source_digest=source_digest,
                priority=1000 - priority,
            )
        )
    external_events = []
    if simulation_events:
        external_events = [
            "TARGET_PROJECTION_INPUT",
            "RESOURCE_QUIESCENT_60S",
            "SELECTION_CUTOFF",
            "FREEZE_DEADLINE",
            "PREDRAW_SEND",
            "AUDITED_DRAW",
            "DAILY_SEND",
            "INCIDENT_OPEN",
        ]
    authorities = [RESEARCH_APPROVAL_AUTHORITY]
    if operator_configuration_authorized:
        authorities.append(OPERATOR_CONFIGURATION_AUTHORITY)
    raw = {
        "schema_version": "research-os-control-plane-v1",
        "goals": [_goal(context=context, source_digest=source_digest)],
        "tasks": tasks,
        "facts": {
            "artifacts": [],
            "evidence": [],
            "external_events": external_events,
            "authorities": authorities,
        },
    }
    manifest = ControlPlaneManifest.from_dict(raw)
    payload = manifest.to_dict(include_digest=True)
    dry_run = {
        "schema_version": "dehps-m4-isolated-v11-manifest-dry-run.v1",
        "status": "DRY_RUN",
        "control_plane_key": contract.CONTROL_PLANE_KEY,
        "manifest_digest": manifest.artifact_digest,
        "task_count": len(manifest.tasks),
        "task_keys": [item.task_key for item in manifest.tasks],
        "capability_count": len({item.requested_capability for item in manifest.tasks}),
        "artifact_type_count": len(contract.ARTIFACT_TYPES),
        "source_digest": source_digest,
        "operator_configuration_authorized": operator_configuration_authorized,
        "simulation_events": simulation_events,
        "import_performed": False,
        "smtp_calls": 0,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
    }
    dry_run["artifact_digest"] = contract.domain_digest(
        dry_run, domain="dehps.m4.isolated-24h-challenger.manifest-dry-run.v11"
    )
    if dry_run["task_count"] != 42:
        raise IsolatedManifestError("manifest_task_count_changed")
    return payload, dry_run


BOOTSTRAP_TEMPLATE_NAMES = frozenset(
    {
        "preregistration",
        "operator_attestation",
        "incident_head_genesis",
        "mail_configuration",
        "target_issue_projection",
        "history_snapshot",
        "genesis",
        "genesis_replay",
        "search_batch",
        "search_batch_replay",
        "search_checkpoint",
        "search_checkpoint_replay",
        "runtime_health",
        "multiplicity_risk_limit",
    }
)
ISSUE_TEMPLATE_NAMES = frozenset(
    item.name for item in contract.TASK_TEMPLATES if item.group == "issue"
)
DAILY_TEMPLATE_NAMES = frozenset(
    item.name for item in contract.TASK_TEMPLATES if item.group == "daily"
)
INCIDENT_TEMPLATE_NAMES = frozenset(
    item.name for item in contract.TASK_TEMPLATES if item.group == "incident"
)
SEARCH_TEMPLATE_NAMES = frozenset(
    {
        "search_batch",
        "search_batch_replay",
        "search_checkpoint",
        "search_checkpoint_replay",
    }
)
HEALTH_TEMPLATE_NAMES = frozenset({"runtime_health"})


def _select_tasks(
    payload: Mapping[str, Any], *, template_names: frozenset[str]
) -> dict[str, Any]:
    manifest = ControlPlaneManifest.from_dict(deepcopy(dict(payload)))
    raw = manifest.to_dict(include_digest=False)

    def template_name(item: Mapping[str, Any]) -> str:
        metric = item["metric_contract"]
        if isinstance(metric, str):
            metric = json.loads(metric)
        if not isinstance(metric, Mapping):
            raise IsolatedManifestError("task_metric_contract_changed")
        return str(metric.get("task_template") or "")

    raw["tasks"] = [
        item for item in raw["tasks"] if template_name(item) in template_names
    ]
    return ControlPlaneManifest.from_dict(raw).to_dict(include_digest=True)


def build_bootstrap_manifest(
    *,
    context: Mapping[str, str],
    source_digest: str,
    operator_configuration_authorized: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    full, dry_run = build_manifest(
        context=context,
        source_digest=source_digest,
        operator_configuration_authorized=operator_configuration_authorized,
        simulation_events=False,
    )
    payload = _select_tasks(full, template_names=BOOTSTRAP_TEMPLATE_NAMES)
    return payload, {
        **dry_run,
        "manifest_digest": payload["manifest_digest"],
        "task_count": len(payload["tasks"]),
        "task_keys": [item["task_key"] for item in payload["tasks"]],
        "bootstrap": True,
    }


def extend_manifest(
    payload: Mapping[str, Any],
    *,
    context: Mapping[str, str],
    source_digest: str,
    template_names: frozenset[str],
    add_external_events: Sequence[str] = (),
) -> dict[str, Any]:
    if not template_names or not template_names.issubset(
        {item.name for item in contract.TASK_TEMPLATES}
    ):
        raise IsolatedManifestError("manifest_extension_template_set_changed")
    current = ControlPlaneManifest.from_dict(deepcopy(dict(payload)))
    operator_authorized = OPERATOR_CONFIGURATION_AUTHORITY in current.facts.authorities
    full, _ = build_manifest(
        context=context,
        source_digest=source_digest,
        operator_configuration_authorized=operator_authorized,
        simulation_events=False,
    )
    selected = _select_tasks(full, template_names=template_names)
    raw = current.to_dict(include_digest=False)
    existing = {item["task_key"] for item in raw["tasks"]}
    raw["tasks"].extend(
        item for item in selected["tasks"] if item["task_key"] not in existing
    )
    unknown_events = set(add_external_events) - {
        "TARGET_PROJECTION_INPUT",
        "RESOURCE_QUIESCENT_60S",
        "SELECTION_CUTOFF",
        "FREEZE_DEADLINE",
        "PREDRAW_SEND",
        "AUDITED_DRAW",
        "DAILY_SEND",
        "INCIDENT_OPEN",
        "CAPACITY_BELOW_18",
    }
    if unknown_events:
        raise IsolatedManifestError("manifest_extension_external_event_changed")
    raw["facts"]["external_events"] = sorted(
        set(raw["facts"]["external_events"]) | set(add_external_events)
    )
    return ControlPlaneManifest.from_dict(raw).to_dict(include_digest=True)


def manifest_with_facts(
    payload: Mapping[str, Any], *, add_artifact_facts: Sequence[str]
) -> dict[str, Any]:
    manifest = ControlPlaneManifest.from_dict(deepcopy(dict(payload)))
    raw = manifest.to_dict(include_digest=False)
    existing = set(raw["facts"]["artifacts"])
    additions = set(add_artifact_facts)
    if any(
        value.startswith("m4-p3-")
        or "PASS_TO_P4" in value
        or "PASS_TO_P5" in value
        or "PROMOTION" in value.upper()
        for value in additions
    ):
        raise IsolatedManifestError("fact_escaped_isolated_namespace")
    raw["facts"]["artifacts"] = sorted(existing | additions)
    return ControlPlaneManifest.from_dict(raw).to_dict(include_digest=True)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-max-issue", required=True)
    parser.add_argument("--target-issue")
    parser.add_argument("--batch-seq", type=int, default=0)
    parser.add_argument("--epoch-date")
    parser.add_argument("--minute")
    parser.add_argument("--incident-id")
    parser.add_argument(
        "--incident-reason-code", default="DEADLINE_OR_ABSENCE"
    )
    parser.add_argument("--incident-offending-digest")
    parser.add_argument("--projection-time")
    parser.add_argument("--source-digest")
    parser.add_argument("--operator-configuration-authorized", action="store_true")
    parser.add_argument("--simulation-events", action="store_true")
    parser.add_argument("--manifest", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    context = contract.render_context(
        source_max_issue=args.source_max_issue,
        target_issue=args.target_issue,
        batch_seq=args.batch_seq,
        epoch_date=args.epoch_date,
        minute=args.minute,
        incident_id=args.incident_id,
        incident_reason_code=args.incident_reason_code,
        incident_offending_digest=args.incident_offending_digest,
        projection_time=args.projection_time,
    )
    source_digest = args.source_digest
    if source_digest is None:
        source_digest = artifacts.load_source_contract()["artifact_digest"]
    payload, dry_run = build_manifest(
        context=context,
        source_digest=source_digest,
        operator_configuration_authorized=args.operator_configuration_authorized,
        simulation_events=args.simulation_events,
    )
    print(
        json.dumps(
            payload if args.manifest else dry_run,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
