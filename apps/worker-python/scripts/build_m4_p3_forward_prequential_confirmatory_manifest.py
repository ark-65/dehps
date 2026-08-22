from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.measurement_system_v2 import (
    forward_prequential_confirmatory as successor,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
    build_additive_task_manifest,
)
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.repository import PostgresResearchOSRepository


class ForwardPrequentialManifestError(ValueError):
    pass


CONTROL_PLANE_KEY = "m4-information-theory-mainline"


def _dependency(kind: str, key: str, status: str) -> dict[str, str]:
    return {"dependency_type": kind, "target_key": key, "required_status": status}


def goal() -> dict[str, Any]:
    return {
        "goal_key": successor.GOAL_KEY,
        "semantic_version": "1.0.0",
        "question": (
            "Does the frozen mechanically refit MARGINAL_STATIC model produce a "
            "practically meaningful positive paired OOS log-loss gain against the "
            "same-issue legal-uniform baseline under a five-look confirmatory design?"
        ),
        "objective_class": "prediction_quality",
        "owner_lane": "research",
        "baseline_metric_manifest": {
            "old_p3_threshold_bits_per_issue": 0.01,
            "old_p3_power": 0.80,
            "old_p3_disposition": "INCONCLUSIVE_DUE_TO_POWER",
            "old_bounded_lineage": "IMMUTABLE_HISTORY_NOT_CURRENT_ROUTE",
        },
        "target_metric_manifest": {
            "practical_threshold_bits_per_issue": successor.PRACTICAL_THRESHOLD,
            "maximum_valid_issues": successor.MAX_N,
            "interim_looks": list(successor.LOOKS),
            "model_tickets_per_issue": 100,
            "random_baseline_tickets_per_issue": 100,
            "normal_codex_invocations": 0,
        },
        "success_evidence": [
            "registered result-blind preregistration and dormant P4 preregistration",
            "registered per-issue t-1 refit, 33-vector, 100+100 timely checkpoint and replay",
            "registered per-issue settlement and replay",
            "only frozen-look corrected decisions",
            "PASS_TO_P4 makes the dormant formal P4 task Ready and terminates P3 accumulation",
        ],
        "guardrails": [
            "old P3 and old bounded lineage immutable",
            "no old checkpoint reuse",
            "no model feature parameter baseline ticket or blue-strategy drift",
            "formal P4 cannot run before successor PASS_TO_P4",
            "no P5 Promotion or betting authorization",
        ],
        "status": "active",
        "retired_at": None,
        "superseded_by_goal_digest": None,
    }


def _integration(*, consumer: str) -> dict[str, Any]:
    return {
        "goal": successor.GOAL_KEY,
        "ready_condition": "registered completion fact from the immediately prior frozen stage",
        "runner": "ForwardPrequentialSupervisor subclass of unified ResearchEvidenceSupervisor",
        "upstream_artifacts": [
            "approved Research Request 640 / Execution 524 / Reviewer Decision 2697",
            "approved Engineering Request 641 / Execution 525 / Reviewer Decision 2702",
            "frozen MARGINAL_STATIC estimator contract",
            "durable audited history through t-1",
        ],
        "downstream_artifacts": [
            "preregistration/P4-preregistration/model/33-vector/100+100/checkpoint/report/settlement/replay/interim-decision"
        ],
        "status_projection": "forward prequential compact status",
        "evidence_progress_rule": "one distinct timely settled successor issue counts at most once",
        "decision_consumer": consumer,
        "downstream_consumer": consumer,
    }


def task(
    *,
    key: str,
    capability: str,
    task_type: str,
    priority: int,
    dependencies: list[dict[str, str]],
    source_digest: str,
    completion_fact: str,
    next_consumer: str,
    target_issue: str | None = None,
    target_draw_date: str | None = None,
    look: int | None = None,
) -> dict[str, Any]:
    contract: dict[str, Any] = {
        "engineering_complete": True,
        "engineering_increment_percent": 0,
        "evidence_complete": False,
        "evidence_increment_percent": 0,
        "phase": task_type.upper().replace("_", "-"),
        "scope": "m4_p3_forward_prequential_confirmatory_successor_v1",
        "completion_fact": completion_fact,
        "maximum_valid_issues": successor.MAX_N,
        "practical_threshold_bits_per_issue": successor.PRACTICAL_THRESHOLD,
        "interim_looks": list(successor.LOOKS),
        "configuration_drift": False,
        "old_lineage_modified": False,
        "old_lineage_current_projection": False,
        "formal_p4_executed": False,
        "p5_started": False,
        "promotion_triggered": False,
        "production_action": "none",
        "mainline_integration": _integration(consumer=next_consumer),
    }
    if target_issue is not None:
        contract["target_issue"] = target_issue
        contract["target_draw_date"] = target_draw_date
    if look is not None:
        contract["look"] = look
    return {
        "task_key": key,
        "goal_key": successor.GOAL_KEY,
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
    keys = successor.issue_task_keys(target_issue)
    facts = successor.issue_facts(target_issue)
    refit_dependencies = [
        _dependency("task", successor.PREREGISTRATION_TASK_KEY, "completed"),
        _dependency("artifact", successor.PREREGISTRATION_FACT, "available"),
    ]
    if previous_settlement_replay_fact is not None:
        refit_dependencies.append(
            _dependency("artifact", previous_settlement_replay_fact, "available")
        )
    return [
        task(
            key=keys["refit"],
            capability=successor.REFIT_CAPABILITY,
            task_type="forward_prequential_refit",
            priority=205,
            dependencies=refit_dependencies,
            source_digest=source_digest,
            completion_fact=facts["refit"],
            next_consumer=keys["predraw"],
            target_issue=target_issue,
            target_draw_date=target_draw_date,
        ),
        task(
            key=keys["predraw"],
            capability=successor.PREDRAW_CAPABILITY,
            task_type="forward_prequential_predraw",
            priority=204,
            dependencies=[_dependency("artifact", facts["refit"], "available")],
            source_digest=source_digest,
            completion_fact=facts["predraw"],
            next_consumer=keys["predraw_replay"],
            target_issue=target_issue,
            target_draw_date=target_draw_date,
        ),
        task(
            key=keys["predraw_replay"],
            capability=successor.PREDRAW_REPLAY_CAPABILITY,
            task_type="forward_prequential_predraw_replay",
            priority=203,
            dependencies=[_dependency("artifact", facts["predraw"], "available")],
            source_digest=source_digest,
            completion_fact=facts["predraw_replay"],
            next_consumer=keys["settlement"],
            target_issue=target_issue,
            target_draw_date=target_draw_date,
        ),
        task(
            key=keys["settlement"],
            capability=successor.SETTLEMENT_CAPABILITY,
            task_type="forward_prequential_settlement",
            priority=202,
            dependencies=[
                _dependency("artifact", facts["predraw_replay"], "available"),
                _dependency("external_event", facts["draw_synced"], "available"),
            ],
            source_digest=source_digest,
            completion_fact=facts["settlement"],
            next_consumer=keys["settlement_replay"],
            target_issue=target_issue,
            target_draw_date=target_draw_date,
        ),
        task(
            key=keys["settlement_replay"],
            capability=successor.SETTLEMENT_REPLAY_CAPABILITY,
            task_type="forward_prequential_settlement_replay",
            priority=201,
            dependencies=[_dependency("artifact", facts["settlement"], "available")],
            source_digest=source_digest,
            completion_fact=facts["settlement_replay"],
            next_consumer="frozen_interim_review_or_automatic_next_issue_refit",
            target_issue=target_issue,
            target_draw_date=target_draw_date,
        ),
    ]


def initial_tasks(
    *, source_digest: str, target_issue: str, target_draw_date: str
) -> list[dict[str, Any]]:
    preregistration = task(
        key=successor.PREREGISTRATION_TASK_KEY,
        capability=successor.PREREGISTRATION_CAPABILITY,
        task_type="forward_prequential_confirmatory_preregistration",
        priority=210,
        dependencies=[
            _dependency(
                "artifact", successor.SOURCE_FACT_PREFIX + source_digest, "available"
            ),
            _dependency("artifact", successor.CURRENT_ROUTE_FACT, "available"),
        ],
        source_digest=source_digest,
        completion_fact=successor.PREREGISTRATION_FACT,
        next_consumer="first_successor_marginal_static_refit",
    )
    reviews = [
        task(
            key=successor.review_task_key(look),
            capability=successor.REVIEW_CAPABILITY,
            task_type="forward_prequential_interim_review",
            priority=209,
            dependencies=[
                _dependency("artifact", successor.review_ready_fact(look), "available")
            ],
            source_digest=source_digest,
            completion_fact=successor.review_completion_fact(look),
            next_consumer=(
                successor.P4_TASK_KEY
                if look == successor.MAX_N
                else "terminal_P4_projection_or_next_frozen_look"
            ),
            look=look,
        )
        for look in successor.LOOKS
    ]
    p4 = task(
        key=successor.P4_TASK_KEY,
        capability=successor.P4_CAPABILITY,
        task_type="formal_p4_negative_controls_and_robustness",
        priority=208,
        dependencies=[
            _dependency("artifact", successor.P4_PREREGISTRATION_FACT, "available"),
            _dependency("artifact", successor.P3_COMPLETE_FACT, "available"),
            _dependency("artifact", successor.PASS_TO_P4_FACT, "available"),
        ],
        source_digest=source_digest,
        completion_fact=f"{successor.P4_TASK_KEY}:COMPLETE",
        next_consumer="formal_P4_evidence_and_decision",
    )
    return [
        preregistration,
        *issue_tasks(
            source_digest=source_digest,
            target_issue=target_issue,
            target_draw_date=target_draw_date,
        ),
        *reviews,
        p4,
    ]


def build_initial_manifest(
    live_payload: Mapping[str, Any],
    *,
    source_digest: str,
    target_issue: str,
    target_draw_date: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    live = ControlPlaneManifest.from_dict(deepcopy(dict(live_payload)))
    if any(item.goal_key == successor.GOAL_KEY for item in live.goals):
        raise ForwardPrequentialManifestError("successor_goal_already_present")
    source = live.to_dict(include_digest=False)
    source["goals"].append(goal())
    tasks = initial_tasks(
        source_digest=source_digest,
        target_issue=target_issue,
        target_draw_date=target_draw_date,
    )
    source["tasks"].extend(tasks)
    output, dry_run = build_additive_m4_v2_manifest(
        live_payload=live.to_dict(include_digest=True),
        source_payload=source,
        allowlisted_new_goal_keys=(successor.GOAL_KEY,),
        allowlisted_new_task_keys=tuple(item["task_key"] for item in tasks),
        allowlisted_revised_task_keys=(),
        add_artifact_facts=(
            successor.SOURCE_FACT_PREFIX + source_digest,
            successor.CURRENT_ROUTE_FACT,
            successor.OLD_ROUTE_HISTORY_FACT,
        ),
        add_external_events=(),
    )
    manifest = ControlPlaneManifest.from_dict(output)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    ready = tuple(item.task_key for item in snapshot.ready_queue)
    p4 = next(
        item for item in snapshot.resolutions if item.task_key == successor.P4_TASK_KEY
    )
    if (
        ready != (successor.PREREGISTRATION_TASK_KEY,)
        or p4.status.value != "dependency_wait"
    ):
        raise ForwardPrequentialManifestError(
            f"successor_initial_projection_changed:{ready}:{p4.status.value}"
        )
    dry_run.update(
        {
            "target_issue": target_issue,
            "target_draw_date": target_draw_date,
            "unique_ready_task": successor.PREREGISTRATION_TASK_KEY,
            "current_route": successor.LINEAGE_ID,
            "old_lineage_projection": "IMMUTABLE_HISTORY_NOT_CURRENT_ROUTE",
            "formal_p4_status": "dependency_wait",
        }
    )
    return manifest.to_dict(include_digest=True), dry_run


def append_issue_manifest(
    live_payload: Mapping[str, Any],
    *,
    source_digest: str,
    target_issue: str,
    target_draw_date: str,
    previous_issue: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    tasks = issue_tasks(
        source_digest=source_digest,
        target_issue=target_issue,
        target_draw_date=target_draw_date,
        previous_settlement_replay_fact=successor.issue_facts(previous_issue)[
            "settlement_replay"
        ],
    )
    return build_additive_task_manifest(live_payload=live_payload, new_tasks=tasks)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the M4-P3 forward successor manifest"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    repository = PostgresResearchOSRepository()
    source = successor.load_source_contract(root_dir=ROOT_DIR)
    live = repository.export_manifest(control_plane_key=CONTROL_PLANE_KEY)
    from dehps.db import get_connection
    from dehps.storage.postgres_store import load_history_with_dates

    with get_connection() as connection:
        history = load_history_with_dates(connection)
    issue, draw_date, _, _ = successor.target_for_now(history)
    output, dry_run = build_initial_manifest(
        live,
        source_digest=str(source["artifact_digest"]),
        target_issue=issue,
        target_draw_date=draw_date.isoformat(),
    )
    if args.output:
        atomic_write_text(
            args.output,
            json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )
    print(json.dumps(dry_run, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
