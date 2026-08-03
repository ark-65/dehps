"""Goal-driven DEHPS Research OS control-plane primitives.

Exports stay lazy so importing an isolated capability does not execute the
control plane, repository, or unrelated runtime modules as a side effect.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "ResearchOSControlPlane": (
        "dehps.research_os.control_plane",
        "ResearchOSControlPlane",
    ),
    "CompletionClassification": (
        "dehps.research_os.models",
        "CompletionClassification",
    ),
    "ControlPlaneManifest": ("dehps.research_os.models", "ControlPlaneManifest"),
    "DependencyFacts": ("dehps.research_os.models", "DependencyFacts"),
    "DependencyType": ("dehps.research_os.models", "DependencyType"),
    "ExternalExecutorObservation": (
        "dehps.research_os.models",
        "ExternalExecutorObservation",
    ),
    "MainlineArtifactRegistration": (
        "dehps.research_os.models",
        "MainlineArtifactRegistration",
    ),
    "MainlineExecutionEvent": ("dehps.research_os.models", "MainlineExecutionEvent"),
    "Goal": ("dehps.research_os.models", "Goal"),
    "GoalState": ("dehps.research_os.models", "GoalState"),
    "GoalStatus": ("dehps.research_os.models", "GoalStatus"),
    "ObjectiveClass": ("dehps.research_os.models", "ObjectiveClass"),
    "ResolutionSnapshot": ("dehps.research_os.models", "ResolutionSnapshot"),
    "Task": ("dehps.research_os.models", "Task"),
    "TaskDependency": ("dehps.research_os.models", "TaskDependency"),
    "TaskLane": ("dehps.research_os.models", "TaskLane"),
    "TaskState": ("dehps.research_os.models", "TaskState"),
    "TaskStatus": ("dehps.research_os.models", "TaskStatus"),
    "PostgresResearchOSRepository": (
        "dehps.research_os.repository",
        "PostgresResearchOSRepository",
    ),
}

__all__ = [
    "CompletionClassification",
    "ControlPlaneManifest",
    "DependencyFacts",
    "DependencyType",
    "ExternalExecutorObservation",
    "Goal",
    "GoalState",
    "GoalStatus",
    "MainlineArtifactRegistration",
    "MainlineExecutionEvent",
    "ObjectiveClass",
    "PostgresResearchOSRepository",
    "ResearchOSControlPlane",
    "ResolutionSnapshot",
    "Task",
    "TaskDependency",
    "TaskLane",
    "TaskState",
    "TaskStatus",
]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(target[0]), target[1])
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
