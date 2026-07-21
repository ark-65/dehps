from __future__ import annotations

from collections import Counter

from dehps.research_os.models import (
    ControlPlaneManifest,
    DependencyType,
    ReadyQueueItem,
    TaskStatus,
    TaskResolution,
)


class ReadyQueue:
    """Build a deterministic portfolio of every currently eligible Task."""

    @staticmethod
    def build(
        manifest: ControlPlaneManifest,
        resolutions: tuple[TaskResolution, ...],
    ) -> tuple[ReadyQueueItem, ...]:
        tasks = {task.task_key: task for task in manifest.tasks}
        downstream = Counter(
            dependency.target_key
            for task in manifest.tasks
            for dependency in task.dependencies
            if dependency.dependency_type is DependencyType.TASK
        )
        items = [
            ReadyQueueItem(
                task_key=resolution.task_key,
                goal_key=resolution.goal_key,
                lane=tasks[resolution.task_key].lane,
                task_digest=resolution.task_digest,
                priority=tasks[resolution.task_key].priority,
                unblocks_count=downstream[resolution.task_key],
            )
            for resolution in resolutions
            if resolution.status is TaskStatus.READY
        ]
        return tuple(
            sorted(
                items,
                key=lambda item: (-item.priority, -item.unblocks_count, item.task_key),
            )
        )
