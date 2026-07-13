from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from dehps.training.dependencies import TrainingDependencies
from dehps.training.models import TrainingRoundRequest, TrainingRoundResult
from dehps.training.runtime_round_executor import (
    RuntimeRoundExecutor,
    RuntimeRoundRequest,
    RuntimeTrainingState,
)


class ProductionTrainingSession(Protocol):
    state: RuntimeTrainingState
    executor: object

    def next_request(self) -> RuntimeRoundRequest | None: ...

    def finish(self, *, status: str = "completed", error: Exception | None = None) -> dict: ...


@dataclass
class TrainingRoundRunner:
    dependencies: TrainingDependencies | None = None
    production_session: ProductionTrainingSession | None = None
    final_status: dict | None = field(default=None, init=False)
    runtime_executor: object = field(default_factory=RuntimeRoundExecutor)
    runtime_state: RuntimeTrainingState | None = field(default=None, init=False)

    @classmethod
    def for_production(cls, session: ProductionTrainingSession) -> TrainingRoundRunner:
        runner = cls(production_session=session, runtime_executor=session.executor)
        runner.runtime_state = session.state
        return runner

    def next_request(self) -> RuntimeRoundRequest | None:
        if self.production_session is None:
            raise RuntimeError("production training session is not configured")
        return self.production_session.next_request()

    def run(
        self,
        request: TrainingRoundRequest | RuntimeRoundRequest,
    ) -> TrainingRoundResult | dict:
        if isinstance(request, RuntimeRoundRequest):
            if self.runtime_state is None:
                raise RuntimeError("runtime training state is not configured")
            outcome = self.runtime_executor.execute(request, self.runtime_state)
            return outcome.result
        if self.runtime_state is None:
            self.runtime_state = RuntimeTrainingState(self._application_dependencies())
        outcome = self.runtime_executor.execute(
            RuntimeRoundRequest(request),
            self.runtime_state,
        )
        return outcome.result

    def finish(
        self,
        *,
        status: str = "completed",
        error: Exception | None = None,
    ) -> dict:
        if self.production_session is None:
            return self.final_status or {}
        self.final_status = self.production_session.finish(status=status, error=error)
        return self.final_status

    def _application_dependencies(self) -> TrainingDependencies:
        if self.dependencies is None:
            raise RuntimeError("application dependencies are not configured")
        return self.dependencies
