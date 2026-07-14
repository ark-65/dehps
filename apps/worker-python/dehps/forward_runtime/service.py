from __future__ import annotations

from dehps.forward_runtime.runtime import ForwardValidationRuntime


class ForwardRuntimeService:
    def __init__(self, runtime: ForwardValidationRuntime | None = None) -> None:
        self.runtime = runtime or ForwardValidationRuntime()

    def status(self, *, event_key: str | None = None) -> dict:
        return {
            "runtime": "forward_validation",
            "state": self.runtime.status(event_key=event_key),
            "research_runtime_blocked": False,
        }
