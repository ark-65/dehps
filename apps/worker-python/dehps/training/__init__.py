"""Training exports behind an import-safe lazy package boundary."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "TrainingRoundRequest": ("dehps.training.models", "TrainingRoundRequest"),
    "TrainingRoundResult": ("dehps.training.models", "TrainingRoundResult"),
    "TrainingRoundRunner": ("dehps.training.round_runner", "TrainingRoundRunner"),
}

__all__ = ["TrainingRoundRequest", "TrainingRoundResult", "TrainingRoundRunner"]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(target[0]), target[1])
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
