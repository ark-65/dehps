from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.measurement_system_v2 import (
    bounded_operational_forward as bounded,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.storage.postgres_store import load_history_with_dates


class M4V2BoundedOperationalForwardManifestError(ValueError):
    pass


CONTROL_PLANE_KEY = "m4-information-theory-mainline"
BASELINE_MANIFEST_DIGEST = (
    "f45786853f1da9e74c7bb269d05b2544c9780b1c64d0864ebaa3ed82bd2e8141"
)
BASELINE_SNAPSHOT_DIGEST = (
    "ca501081b7b26b489d072bedab3a2769f02d589c0d6240bf961d9f6747190acf"
)
FORMAL_P4_TASK_KEY = "m4-p4-negative-controls-and-robustness"
GOAL_KEY = bounded.GOAL_KEY
PREREGISTRATION_TASK_KEY = bounded.PREREGISTRATION_TASK_KEY
SOURCE_FACT_PREFIX = bounded.SOURCE_FACT_PREFIX


def _dependency(kind: str, key: str, status: str) -> dict[str, str]:
    return {"dependency_type": kind, "target_key": key, "required_status": status}


def _goal() -> dict[str, Any]:
    return {
        "goal_key": GOAL_KEY,
        "semantic_version": "1.0.0",
        "question": (
            "Can the frozen MARGINAL_STATIC protocol operate prospectively for exactly "
            "120 independently sealed shadow issues without identity drift?"
        ),
        "objective_class": "runtime_capability",
        "owner_lane": "research",
        "baseline_metric_manifest": {
            "p3_scientific_disposition": "INCONCLUSIVE_DUE_TO_POWER",
            "p3_governance_status": "CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION",
            "formal_p4": "DEPENDENCY_WAIT",
            "cohort_a_current": 0,
        },
        "target_metric_manifest": {
            "target_valid_issues": 120,
            "model_tickets_per_issue": 100,
            "random_baseline_tickets_per_issue": 100,
            "same_blue_strategy": True,
            "normal_codex_invocations": 0,
        },
        "success_evidence": [
            "registered frozen preregistration and replay",
            "registered per-issue model refit and 33-vector",
            "registered timely 100+100 checkpoint and pre-draw replay",
            "registered post-draw settlement and replay",
            "automatic next-issue refit and seal",
        ],
        "guardrails": [
            "shadow_only",
            "old P3 unchanged",
            "formal P4 dependency wait",
            "no PASS_TO_P4, P5, or Promotion",
            "no model, feature, parameter, threshold, or endpoint selection",
            "issues 20 and 60 integrity only",
            "Cohort A excluded from later confirmatory P3",
        ],
        "status": "active",
        "retired_at": None,
        "superseded_by_goal_digest": None,
    }


def _integration(*, consumer: str) -> dict[str, Any]:
    return {
        "goal": GOAL_KEY,
        "ready_condition": "registered upstream completion fact for the immediately prior stage",
        "runner": "unified Research Evidence Supervisor",
        "upstream_artifacts": [
            "M4V2ForwardEvidenceProgramDecisionArtifact",
            "M4V2BoundedOperationalForwardPreregistrationArtifact",
            "M4V2BoundedOperationalForwardModelArtifact",
            "audited draw-sync event when settling",
        ],
        "downstream_artifacts": [
            "preregistration/model/candidate/baseline/checkpoint/report/settlement/replay",
        ],
        "status_projection": "bounded operational forward compact status",
        "evidence_progress_rule": "one timely distinct settled official issue counts at most once",
        "decision_consumer": consumer,
        "downstream_consumer": consumer,
    }


def _task(
    *,
    key: str,
    capability: str,
    task_type: str,
    priority: int,
    dependencies: list[dict[str, str]],
    source_digest: str,
    target_issue: str | None,
    target_draw_date: str | None,
    completion_fact: str,
    next_consumer: str,
) -> dict[str, Any]:
    contract: dict[str, Any] = {
        "engineering_complete": True,
        "engineering_increment_percent": 0,
        "evidence_complete": False,
        "evidence_increment_percent": 0,
        "phase": task_type.upper().replace("_", "-"),
        "scope": "bounded_operational_forward_shadow_only",
        "completion_fact": completion_fact,
        "target_issue_count": 120,
        "data_reuse_policy": "STAGED_INDEPENDENT_SAMPLES",
        "formal_p4_modified": False,
        "pass_to_p4_emitted": False,
        "p5_started": False,
        "promotion_triggered": False,
        "production_action": "none",
        "mainline_integration": _integration(consumer=next_consumer),
    }
    if target_issue is not None:
        contract["target_issue"] = target_issue
        contract["target_draw_date"] = target_draw_date
    return {
        "task_key": key,
        "goal_key": GOAL_KEY,
        "task_type": task_type,
        "lane": "research",
        "priority": priority,
        "dependencies": dependencies,
        "input_artifact_digests": [source_digest],
        "requested_capability": capability,
        "metric_contract": contract,
        "status": "draft",
        "completion_classification": "INTEGRATION_PENDING",
    }


def issue_tasks(
    *,
    source_digest: str,
    target_issue: str,
    target_draw_date: str,
    previous_settlement_replay_fact: str | None = None,
) -> list[dict[str, Any]]:
    keys = bounded.issue_task_keys(target_issue)
    facts = bounded.issue_facts(target_issue)
    refit_dependencies = [
        _dependency("task", PREREGISTRATION_TASK_KEY, "completed"),
        _dependency("artifact", bounded.PREREGISTRATION_FACT, "available"),
    ]
    if previous_settlement_replay_fact is not None:
        refit_dependencies.append(
            _dependency("artifact", previous_settlement_replay_fact, "available")
        )
    return [
        _task(
            key=keys["refit"],
            capability=bounded.REFIT_CAPABILITY,
            task_type="bounded_operational_forward_refit",
            priority=121,
            dependencies=refit_dependencies,
            source_digest=source_digest,
            target_issue=target_issue,
            target_draw_date=target_draw_date,
            completion_fact=facts["refit"],
            next_consumer=keys["predraw"],
        ),
        _task(
            key=keys["predraw"],
            capability=bounded.PREDRAW_CAPABILITY,
            task_type="bounded_operational_forward_predraw",
            priority=120,
            dependencies=[_dependency("artifact", facts["refit"], "available")],
            source_digest=source_digest,
            target_issue=target_issue,
            target_draw_date=target_draw_date,
            completion_fact=facts["predraw"],
            next_consumer=keys["predraw_replay"],
        ),
        _task(
            key=keys["predraw_replay"],
            capability=bounded.PREDRAW_REPLAY_CAPABILITY,
            task_type="bounded_operational_forward_predraw_replay",
            priority=119,
            dependencies=[_dependency("artifact", facts["predraw"], "available")],
            source_digest=source_digest,
            target_issue=target_issue,
            target_draw_date=target_draw_date,
            completion_fact=facts["predraw_replay"],
            next_consumer=keys["settlement"],
        ),
        _task(
            key=keys["settlement"],
            capability=bounded.SETTLEMENT_CAPABILITY,
            task_type="bounded_operational_forward_settlement",
            priority=118,
            dependencies=[
                _dependency("artifact", facts["predraw_replay"], "available"),
                _dependency("external_event", facts["draw_synced"], "available"),
            ],
            source_digest=source_digest,
            target_issue=target_issue,
            target_draw_date=target_draw_date,
            completion_fact=facts["settlement"],
            next_consumer=keys["settlement_replay"],
        ),
        _task(
            key=keys["settlement_replay"],
            capability=bounded.SETTLEMENT_REPLAY_CAPABILITY,
            task_type="bounded_operational_forward_settlement_replay",
            priority=117,
            dependencies=[_dependency("artifact", facts["settlement"], "available")],
            source_digest=source_digest,
            target_issue=target_issue,
            target_draw_date=target_draw_date,
            completion_fact=facts["settlement_replay"],
            next_consumer="automatic_next_issue_refit",
        ),
    ]


def preregistration_task(*, source_digest: str) -> dict[str, Any]:
    return _task(
        key=PREREGISTRATION_TASK_KEY,
        capability=bounded.PREREGISTRATION_CAPABILITY,
        task_type="bounded_operational_forward_study_preregistration",
        priority=123,
        dependencies=[
            _dependency(
                "artifact",
                "m4-v2-forward-program:LAUNCH_BOUNDED_OPERATIONAL_FORWARD_STUDY",
                "available",
            ),
            _dependency(
                "artifact",
                "m4-v2-forward-data-reuse-policy:STAGED_INDEPENDENT_SAMPLES",
                "available",
            ),
        ],
        source_digest=source_digest,
        target_issue=None,
        target_draw_date=None,
        completion_fact=bounded.PREREGISTRATION_FACT,
        next_consumer="initial_marginal_static_refit",
    )


def _source_manifest(
    live: ControlPlaneManifest,
    *,
    source_digest: str,
    target_issue: str,
    target_draw_date: str,
) -> dict[str, Any]:
    payload = live.to_dict(include_digest=False)
    if any(goal["goal_key"] == GOAL_KEY for goal in payload["goals"]):
        raise M4V2BoundedOperationalForwardManifestError("bounded_goal_already_present")
    matches = [
        index
        for index, task in enumerate(payload["tasks"])
        if task["task_key"] == PREREGISTRATION_TASK_KEY
    ]
    if len(matches) != 1:
        raise M4V2BoundedOperationalForwardManifestError(
            "preregistration_identity_missing"
        )
    payload["goals"].append(_goal())
    payload["tasks"][matches[0]] = preregistration_task(source_digest=source_digest)
    payload["tasks"].extend(
        issue_tasks(
            source_digest=source_digest,
            target_issue=target_issue,
            target_draw_date=target_draw_date,
        )
    )
    return ControlPlaneManifest.from_dict(payload).to_dict(include_digest=True)


def build_manifest(
    live_payload: Mapping[str, Any],
    *,
    source_contract_digest: str,
    target_issue: str,
    target_draw_date: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    live = ControlPlaneManifest.from_dict(deepcopy(dict(live_payload)))
    if live.artifact_digest != BASELINE_MANIFEST_DIGEST:
        raise M4V2BoundedOperationalForwardManifestError("bounded_baseline_changed")
    baseline_snapshot = ResearchOSControlPlane().resolve(live)
    if baseline_snapshot.snapshot_digest != BASELINE_SNAPSHOT_DIGEST:
        raise M4V2BoundedOperationalForwardManifestError("bounded_snapshot_changed")
    parsed_date = date.fromisoformat(target_draw_date)
    if parsed_date.weekday() not in {1, 3, 6}:
        raise M4V2BoundedOperationalForwardManifestError("target_draw_date_invalid")
    source = _source_manifest(
        live,
        source_digest=source_contract_digest,
        target_issue=target_issue,
        target_draw_date=target_draw_date,
    )
    new_keys = tuple(bounded.issue_task_keys(target_issue).values())
    manifest, dry_run = build_additive_m4_v2_manifest(
        live_payload=live.to_dict(include_digest=True),
        source_payload=source,
        allowlisted_new_goal_keys=(GOAL_KEY,),
        allowlisted_new_task_keys=new_keys,
        allowlisted_revised_task_keys=(PREREGISTRATION_TASK_KEY,),
        add_artifact_facts=(SOURCE_FACT_PREFIX + source_contract_digest,),
        add_external_events=(),
    )
    output = ControlPlaneManifest.from_dict(manifest)
    snapshot = ResearchOSControlPlane().resolve(output)
    ready = tuple(item.task_key for item in snapshot.ready_queue)
    formal = next(
        item for item in snapshot.resolutions if item.task_key == FORMAL_P4_TASK_KEY
    )
    if ready != (PREREGISTRATION_TASK_KEY,) or formal.status.value != "dependency_wait":
        raise M4V2BoundedOperationalForwardManifestError(
            f"bounded_ready_or_formal_changed:{ready}:{formal.status.value}"
        )
    dry_run.update(
        {
            "target_issue": target_issue,
            "target_draw_date": target_draw_date,
            "unique_ready_task": PREREGISTRATION_TASK_KEY,
            "formal_p4_status": "dependency_wait",
            "pass_to_p4_emitted": False,
            "p5_started": False,
            "promotion_triggered": False,
        }
    )
    return output.to_dict(include_digest=True), dry_run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the bounded operational forward launch manifest."
    )
    parser.add_argument("--control-plane-key", default=CONTROL_PLANE_KEY)
    parser.add_argument("--target-issue", default="")
    parser.add_argument("--target-draw-date", default="")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run-output", type=Path, required=True)
    args = parser.parse_args()
    repository = PostgresResearchOSRepository()
    live = repository.export_manifest(control_plane_key=args.control_plane_key)
    source = bounded.load_source_contract(root_dir=ROOT_DIR)
    target_issue = args.target_issue
    target_draw_date = args.target_draw_date
    if not target_issue or not target_draw_date:
        with get_connection() as connection:
            history = load_history_with_dates(connection)
        target_issue, draw_date_value, _, _ = bounded.target_for_now(history)
        target_draw_date = draw_date_value.isoformat()
    output, dry_run = build_manifest(
        live,
        source_contract_digest=str(source["artifact_digest"]),
        target_issue=target_issue,
        target_draw_date=target_draw_date,
    )
    atomic_write_text(args.output, json.dumps(output, indent=2, sort_keys=True) + "\n")
    atomic_write_text(
        args.dry_run_output, json.dumps(dry_run, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(dry_run, sort_keys=True))


if __name__ == "__main__":
    main()
