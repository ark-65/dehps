from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dehps.training.dependencies import TrainingDependencies
from dehps.training.models import (
    CandidateProposal,
    TrainingRoundRequest,
    TrainingRoundResult,
)


@dataclass(frozen=True)
class RuntimeRoundRequest:
    """Production-facing request envelope for exactly one training round."""

    round: TrainingRoundRequest

    @property
    def run_id(self) -> str:
        return self.round.run_id

    @property
    def round_index(self) -> int:
        return self.round.round_index


@dataclass
class RuntimeTrainingState:
    """Mutable run-scoped state shared across explicit round executions."""

    dependencies: TrainingDependencies | None = None
    values: dict[str, Any] = field(default_factory=dict)
    completed_rounds: int = 0
    latest_result: TrainingRoundResult | None = None


@dataclass(frozen=True)
class RuntimeRoundOutcome:
    request: RuntimeRoundRequest
    result: TrainingRoundResult | dict


@dataclass(frozen=True)
class RuntimeRoundExecutor:
    """Execute candidate, evaluation, promotion and I/O stages once, in order."""

    def execute(
        self,
        request: RuntimeRoundRequest,
        state: RuntimeTrainingState,
    ) -> RuntimeRoundOutcome:
        dependencies = state.dependencies
        if dependencies is None:
            raise RuntimeError("application training dependencies are not configured")
        round_request = request.round
        context = dependencies.repository.load_context(round_request)
        search_candidates = tuple(
            dependencies.candidate_search.propose(round_request, context)
        )
        remaining_budget = max(
            0,
            round_request.candidate_budget - len(search_candidates),
        )
        configured_advisor_budgets = (
            context.values.get("advisor_budgets", {})
            if context.values is not None
            else {}
        )
        advisor_budgets = self._advisor_budgets(
            remaining_budget,
            configured_advisor_budgets
            if isinstance(configured_advisor_budgets, dict)
            else {},
            dependencies,
        )
        advisor_candidates = dependencies.advisor_registry.propose(
            context.advisor_context,
            advisor_budgets,
        )
        candidates = search_candidates + tuple(
            CandidateProposal(
                config=candidate.config,
                source_key=candidate.source_key,
                protocol_version=candidate.protocol_version,
            )
            for candidate in advisor_candidates
        )
        evaluated = dependencies.evaluator.evaluate(
            round_request,
            context,
            candidates,
        )
        decision = dependencies.promotion_gate.decide(
            evaluated.selected_evaluation,
            context.current_best,
        )
        artifacts = tuple(
            dependencies.artifact_writer.write(round_request, evaluated, decision)
        )
        warnings = (
            ("candidate_budget_exceeded",)
            if len(candidates) > round_request.candidate_budget
            else ()
        )
        result = TrainingRoundResult(
            candidate_summaries=evaluated.candidate_summaries,
            evaluation=evaluated.selected_evaluation,
            promotion_decision=decision,
            artifacts=artifacts,
            warnings=warnings,
        )
        dependencies.repository.save_round(round_request, result)
        dependencies.event_publisher.publish(round_request, result)
        state.completed_rounds += 1
        state.latest_result = result
        return RuntimeRoundOutcome(request=request, result=result)

    @staticmethod
    def _advisor_budgets(
        remaining_budget: int,
        configured: dict,
        dependencies: TrainingDependencies,
    ) -> dict[str, int]:
        budgets: dict[str, int] = {}
        remaining = remaining_budget
        for advisor in dependencies.advisor_registry.advisors:
            count = min(remaining, max(0, int(configured.get(advisor.key, 0))))
            budgets[advisor.key] = count
            remaining -= count
        return budgets
