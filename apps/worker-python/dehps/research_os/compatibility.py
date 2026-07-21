from __future__ import annotations

from typing import Any, Mapping

from dehps.research_os.models import (
    DependencyType,
    ResearchOSValidationError,
    Task,
    TaskDependency,
    TaskLane,
)


LEGACY_FORWARD_ACTIONS = frozenset({"wait_forward", "wait_forward_pattern"})


def project_legacy_wait_task(
    item: Mapping[str, Any],
    *,
    goal_key: str,
    lane: TaskLane = TaskLane.RESEARCH,
) -> Task:
    """Project one legacy WAIT action into a task-local typed dependency.

    The adapter is deliberately narrow. Non-wait legacy actions need an explicit
    Task contract instead of being guessed into the new control plane.
    """

    action = str(item.get("action") or "")
    if action not in LEGACY_FORWARD_ACTIONS:
        raise ResearchOSValidationError(f"legacy action is not a forward wait: {action!r}")
    queue_key = str(item.get("queue_key") or "").strip()
    if not queue_key:
        raise ResearchOSValidationError("legacy wait item requires queue_key")
    reason = item.get("reason") or item.get("reason_json") or {}
    if not isinstance(reason, Mapping):
        raise ResearchOSValidationError("legacy wait reason must be an object")
    reason_code = str(reason.get("reason_code") or "")
    if reason_code == "open_agent_request":
        request_key = str(reason.get("request_key") or "").strip()
        if not request_key:
            raise ResearchOSValidationError("open_agent_request wait requires request_key")
        dependency = TaskDependency(DependencyType.AUTHORITY, request_key, "completed")
    else:
        explicit_event = str(reason.get("external_event_key") or "").strip()
        if explicit_event:
            event_key = explicit_event
        else:
            minimum = int(reason.get("min_paired_issues") or 0)
            event_key = f"forward_coverage:{minimum}" if minimum else "forward_observation:next"
        dependency = TaskDependency(DependencyType.EXTERNAL_EVENT, event_key, "available")
    return Task(
        task_key=f"legacy:{queue_key}",
        goal_key=goal_key,
        task_type=action,
        lane=lane,
        dependencies=(dependency,),
        priority=int(round(float(item.get("priority_score") or 0) * 1000)),
    )
