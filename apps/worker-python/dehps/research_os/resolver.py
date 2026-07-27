from __future__ import annotations

from collections import defaultdict

from dehps.research_os.models import (
    ControlPlaneManifest,
    DependencyType,
    GoalStatus,
    ResearchOSValidationError,
    Task,
    TaskDependency,
    TaskResolution,
    TaskStatus,
    TERMINAL_TASK_STATUSES,
)
from dehps.research_os.mainline import validate_mainline_completion_declarations


class TaskDependencyResolver:
    """Resolve every Task independently; no Task may create a global wait state."""

    def resolve(self, manifest: ControlPlaneManifest) -> tuple[TaskResolution, ...]:
        validate_mainline_completion_declarations(manifest)
        goals = self._unique_goals(manifest)
        tasks = self._unique_tasks(manifest)
        self._validate_task_graph(tasks)
        goal_states = manifest.goal_state_by_digest
        task_states = manifest.task_state_by_digest
        completed = {
            task.task_key
            for task in manifest.tasks
            if task_states[task.artifact_digest].declared_status is TaskStatus.COMPLETED
        }
        resolutions: list[TaskResolution] = []
        for task in sorted(manifest.tasks, key=lambda item: item.task_key):
            goal = goals.get(task.goal_key)
            if goal is None:
                raise ResearchOSValidationError(
                    f"task {task.task_key!r} references missing goal {task.goal_key!r}"
                )
            if task.goal_digest != goal.artifact_digest:
                raise ResearchOSValidationError(
                    f"task {task.task_key!r} goal_digest does not match Goal definition"
                )
            if task.lane is not goal.owner_lane:
                raise ResearchOSValidationError(
                    f"task {task.task_key!r} lane {task.lane.value!r} does not match "
                    f"goal {goal.goal_key!r} owner lane {goal.owner_lane.value!r}"
                )
            task_state = task_states.get(task.artifact_digest)
            if task_state is None:
                raise ResearchOSValidationError(
                    f"task {task.task_key!r} is missing its declared state"
                )
            goal_state = goal_states.get(goal.artifact_digest)
            if goal_state is None:
                raise ResearchOSValidationError(
                    f"goal {goal.goal_key!r} is missing its lifecycle state"
                )
            if task_state.declared_status in TERMINAL_TASK_STATUSES:
                resolutions.append(
                    self._resolution(
                        task,
                        task_state.declared_status,
                        f"task_{task_state.declared_status.value}",
                    )
                )
                continue
            if task_state.declared_status is TaskStatus.RUNNING:
                resolutions.append(
                    self._resolution(task, TaskStatus.RUNNING, "mainline_execution_running")
                )
                continue
            if goal_state.status is not GoalStatus.ACTIVE:
                resolutions.append(
                    self._resolution(task, TaskStatus.DEPENDENCY_WAIT, "goal_not_active")
                )
                continue
            unsatisfied = tuple(
                dependency
                for dependency in task.dependencies
                if not self._satisfied(dependency, manifest=manifest, completed_tasks=completed)
            )
            if not unsatisfied:
                resolutions.append(self._resolution(task, TaskStatus.READY, "dependencies_satisfied"))
                continue
            if any(item.dependency_type is DependencyType.AUTHORITY for item in unsatisfied):
                status = TaskStatus.APPROVAL_WAIT
                reason = "authority_dependency_unsatisfied"
            elif any(item.dependency_type is DependencyType.EXTERNAL_EVENT for item in unsatisfied):
                status = TaskStatus.EXTERNAL_WAIT
                reason = "external_event_dependency_unsatisfied"
            elif any(
                item.dependency_type is DependencyType.TASK
                and item.target_key
                == "m4-p1-repair-resampling-preregistration-contract"
                for item in unsatisfied
            ):
                status = TaskStatus.BLOCKED_BY_CONTRACT
                reason = "preregistration_contract_dependency_unsatisfied"
            else:
                status = TaskStatus.DEPENDENCY_WAIT
                reason = "dependency_unsatisfied"
            resolutions.append(self._resolution(task, status, reason, unsatisfied))
        return tuple(resolutions)

    @staticmethod
    def _unique_goals(manifest: ControlPlaneManifest):
        goals = {}
        for goal in manifest.goals:
            if goal.goal_key in goals:
                raise ResearchOSValidationError(f"duplicate goal_key: {goal.goal_key}")
            goals[goal.goal_key] = goal
        return goals

    @staticmethod
    def _unique_tasks(manifest: ControlPlaneManifest) -> dict[str, Task]:
        tasks: dict[str, Task] = {}
        for task in manifest.tasks:
            if task.task_key in tasks:
                raise ResearchOSValidationError(f"duplicate task_key: {task.task_key}")
            tasks[task.task_key] = task
        return tasks

    @staticmethod
    def _validate_task_graph(tasks: dict[str, Task]) -> None:
        adjacency: dict[str, list[str]] = defaultdict(list)
        for task in tasks.values():
            for dependency in task.dependencies:
                if dependency.dependency_type is not DependencyType.TASK:
                    continue
                target = tasks.get(dependency.target_key)
                if target is None:
                    raise ResearchOSValidationError(
                        f"task {task.task_key!r} references missing task {dependency.target_key!r}"
                    )
                if target.goal_key != task.goal_key:
                    raise ResearchOSValidationError(
                        f"task dependency {task.task_key!r} -> {target.task_key!r} crosses Goals"
                    )
                adjacency[task.task_key].append(target.task_key)

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_key: str, path: tuple[str, ...]) -> None:
            if task_key in visiting:
                cycle = " -> ".join((*path, task_key))
                raise ResearchOSValidationError(f"task dependency cycle detected: {cycle}")
            if task_key in visited:
                return
            visiting.add(task_key)
            for target_key in adjacency.get(task_key, ()):
                visit(target_key, (*path, task_key))
            visiting.remove(task_key)
            visited.add(task_key)

        for task_key in sorted(tasks):
            visit(task_key, ())

    @staticmethod
    def _satisfied(
        dependency: TaskDependency,
        *,
        manifest: ControlPlaneManifest,
        completed_tasks: set[str],
    ) -> bool:
        facts = manifest.facts
        if dependency.dependency_type is DependencyType.TASK:
            return dependency.target_key in completed_tasks
        if dependency.dependency_type is DependencyType.ARTIFACT:
            return dependency.target_key in facts.artifacts
        if dependency.dependency_type is DependencyType.EVIDENCE:
            return dependency.target_key in facts.evidence
        if dependency.dependency_type is DependencyType.EXTERNAL_EVENT:
            return dependency.target_key in facts.external_events
        if dependency.dependency_type is DependencyType.AUTHORITY:
            return dependency.target_key in facts.authorities
        raise ResearchOSValidationError(
            f"unsupported dependency type: {dependency.dependency_type.value}"
        )

    @staticmethod
    def _resolution(
        task: Task,
        status: TaskStatus,
        reason_code: str,
        unsatisfied: tuple[TaskDependency, ...] = (),
    ) -> TaskResolution:
        return TaskResolution(
            task_key=task.task_key,
            goal_key=task.goal_key,
            task_digest=task.artifact_digest,
            status=status,
            reason_code=reason_code,
            unsatisfied_dependencies=unsatisfied,
        )
