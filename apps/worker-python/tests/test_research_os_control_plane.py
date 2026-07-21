from dataclasses import FrozenInstanceError

import pytest

from dehps.research_os.compatibility import project_legacy_wait_task
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.models import (
    ControlPlaneManifest,
    DependencyType,
    ResearchOSValidationError,
    TaskLane,
    TaskStatus,
)


def _goal(goal_key: str, *, lane: str, objective_class: str) -> dict:
    return {
        "goal_key": goal_key,
        "semantic_version": "1.0.0",
        "objective_class": objective_class,
        "status": "active",
        "success_evidence": [f"{goal_key}:reviewed_bundle"],
        "owner_lane": lane,
    }


def _manifest(*, external_events: list[str] | None = None) -> dict:
    return {
        "schema_version": "research-os-control-plane-v1",
        "goals": [
            _goal("forward-30", lane="production", objective_class="prediction_quality"),
            _goal("improve-quality", lane="research", objective_class="prediction_quality"),
            _goal("integrity", lane="maintenance", objective_class="maintenance_integrity"),
        ],
        "tasks": [
            {
                "task_key": "evaluate-2026083",
                "goal_key": "forward-30",
                "task_type": "evaluation",
                "lane": "production",
                "priority": 100,
                "dependencies": [
                    {
                        "dependency_type": "external_event",
                        "target_key": "draw:2026083",
                    }
                ],
            },
            {
                "task_key": "historical-replay",
                "goal_key": "improve-quality",
                "task_type": "replay",
                "lane": "research",
                "priority": 80,
            },
            {
                "task_key": "feature-ablation",
                "goal_key": "improve-quality",
                "task_type": "feature_ablation",
                "lane": "research",
                "priority": 70,
                "dependencies": [
                    {
                        "dependency_type": "authority",
                        "target_key": "engineering:feature-ablation-v1",
                        "required_status": "approved",
                    }
                ],
            },
            {
                "task_key": "sealed-artifact-audit",
                "goal_key": "integrity",
                "task_type": "artifact_audit",
                "lane": "maintenance",
                "priority": 90,
            },
        ],
        "facts": {"external_events": external_events or []},
    }


def _by_task(snapshot):
    return {item.task_key: item for item in snapshot.resolutions}


def test_external_wait_is_local_and_event_arrival_changes_only_its_path() -> None:
    control_plane = ResearchOSControlPlane()

    first = control_plane.resolve(ControlPlaneManifest.from_dict(_manifest()))
    first_tasks = _by_task(first)

    assert first_tasks["evaluate-2026083"].status is TaskStatus.EXTERNAL_WAIT
    assert first_tasks["historical-replay"].status is TaskStatus.READY
    assert first_tasks["sealed-artifact-audit"].status is TaskStatus.READY
    assert first_tasks["feature-ablation"].status is TaskStatus.APPROVAL_WAIT
    assert [item.task_key for item in first.ready_queue] == [
        "sealed-artifact-audit",
        "historical-replay",
    ]

    second = control_plane.resolve(
        ControlPlaneManifest.from_dict(_manifest(external_events=["draw:2026083"]))
    )
    second_tasks = _by_task(second)

    assert second_tasks["evaluate-2026083"].status is TaskStatus.READY
    assert second_tasks["historical-replay"].status is TaskStatus.READY
    assert second_tasks["sealed-artifact-audit"].status is TaskStatus.READY
    assert first.manifest_digest != second.manifest_digest
    assert first.snapshot_digest != second.snapshot_digest


def test_goal_and_task_are_immutable_digest_addressed_artifacts() -> None:
    manifest = ControlPlaneManifest.from_dict(_manifest())
    same_manifest = ControlPlaneManifest.from_dict(_manifest())

    assert manifest.artifact_digest == same_manifest.artifact_digest
    assert manifest.goals[0].artifact_digest == same_manifest.goals[0].artifact_digest
    assert manifest.tasks[0].artifact_digest == same_manifest.tasks[0].artifact_digest
    with pytest.raises(FrozenInstanceError):
        manifest.tasks[0].priority = 999  # type: ignore[misc]


def test_task_dependency_completion_unblocks_downstream_and_affects_queue_order() -> None:
    payload = {
        "schema_version": "research-os-control-plane-v1",
        "goals": [_goal("research", lane="research", objective_class="prediction_quality")],
        "tasks": [
            {
                "task_key": "replay",
                "goal_key": "research",
                "task_type": "replay",
                "lane": "research",
                "status": "completed",
            },
            {
                "task_key": "diagnostics",
                "goal_key": "research",
                "task_type": "diagnostics",
                "lane": "research",
                "priority": 20,
                "dependencies": [
                    {"dependency_type": "task", "target_key": "replay", "required_status": "completed"}
                ],
            },
            {
                "task_key": "independent",
                "goal_key": "research",
                "task_type": "benchmark",
                "lane": "research",
                "priority": 20,
            },
        ],
    }

    snapshot = ResearchOSControlPlane().resolve(ControlPlaneManifest.from_dict(payload))

    assert _by_task(snapshot)["diagnostics"].status is TaskStatus.READY
    assert [item.task_key for item in snapshot.ready_queue] == ["diagnostics", "independent"]
    assert snapshot.ready_queue[0].unblocks_count == 0


@pytest.mark.parametrize(
    "tasks, expected",
    [
        (
            [
                {
                    "task_key": "one",
                    "goal_key": "research",
                    "task_type": "replay",
                    "lane": "research",
                    "dependencies": [{"dependency_type": "task", "target_key": "missing"}],
                }
            ],
            "references missing task",
        ),
        (
            [
                {
                    "task_key": "one",
                    "goal_key": "research",
                    "task_type": "replay",
                    "lane": "research",
                    "dependencies": [{"dependency_type": "task", "target_key": "two"}],
                },
                {
                    "task_key": "two",
                    "goal_key": "research",
                    "task_type": "diagnostics",
                    "lane": "research",
                    "dependencies": [{"dependency_type": "task", "target_key": "one"}],
                },
            ],
            "cycle detected",
        ),
    ],
)
def test_invalid_task_graph_fails_closed(tasks: list[dict], expected: str) -> None:
    payload = {
        "schema_version": "research-os-control-plane-v1",
        "goals": [_goal("research", lane="research", objective_class="prediction_quality")],
        "tasks": tasks,
    }

    with pytest.raises(ResearchOSValidationError, match=expected):
        ResearchOSControlPlane().resolve(ControlPlaneManifest.from_dict(payload))


@pytest.mark.parametrize(
    "mutation, expected",
    [
        ("duplicate_goal", "duplicate goal_key"),
        ("duplicate_task", "duplicate task_key"),
        ("missing_goal", "references missing goal"),
        ("lane_mismatch", "does not match"),
        ("invalid_goal_status", "invalid goal status"),
    ],
)
def test_invalid_identities_and_goal_contracts_fail_closed(mutation: str, expected: str) -> None:
    payload = {
        "schema_version": "research-os-control-plane-v1",
        "goals": [_goal("research", lane="research", objective_class="prediction_quality")],
        "tasks": [
            {
                "task_key": "replay",
                "goal_key": "research",
                "task_type": "replay",
                "lane": "research",
            }
        ],
    }
    if mutation == "duplicate_goal":
        payload["goals"].append(dict(payload["goals"][0]))
    elif mutation == "duplicate_task":
        payload["tasks"].append(dict(payload["tasks"][0]))
    elif mutation == "missing_goal":
        payload["tasks"][0]["goal_key"] = "missing"
    elif mutation == "lane_mismatch":
        payload["tasks"][0]["lane"] = "maintenance"
    elif mutation == "invalid_goal_status":
        payload["goals"][0]["status"] = "running"

    with pytest.raises(ResearchOSValidationError, match=expected):
        ResearchOSControlPlane().resolve(ControlPlaneManifest.from_dict(payload))


def test_legacy_wait_forward_projects_to_local_typed_dependencies() -> None:
    forward = project_legacy_wait_task(
        {
            "queue_key": "queue-forward",
            "action": "wait_forward",
            "reason": {"reason_code": "forward_evidence_insufficient", "min_paired_issues": 20},
        },
        goal_key="research",
    )
    approval = project_legacy_wait_task(
        {
            "queue_key": "queue-approval",
            "action": "wait_forward_pattern",
            "reason": {"reason_code": "open_agent_request", "request_key": "request-17"},
        },
        goal_key="research",
        lane=TaskLane.RESEARCH,
    )

    assert forward.dependencies[0].dependency_type is DependencyType.EXTERNAL_EVENT
    assert forward.dependencies[0].target_key == "forward_coverage:20"
    assert approval.dependencies[0].dependency_type is DependencyType.AUTHORITY
    assert approval.dependencies[0].target_key == "request-17"
