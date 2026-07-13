from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

from dehps.training.dependencies import TrainingDependencies
from dehps.training.models import CandidateProposal, TrainingRoundRequest, TrainingRoundResult


@dataclass
class TrainingRoundRunner:
    dependencies: TrainingDependencies | None = None
    runtime_rounds: Iterator[dict] | None = None
    final_status: dict | None = field(default=None, init=False)

    @classmethod
    def for_runtime(cls, runtime_rounds: Iterator[dict]) -> TrainingRoundRunner:
        return cls(runtime_rounds=runtime_rounds)

    def run(self, request: TrainingRoundRequest) -> TrainingRoundResult:
        dependencies = self._application_dependencies()
        context = dependencies.repository.load_context(request)
        search_candidates = tuple(dependencies.candidate_search.propose(request, context))
        remaining_budget = max(0, request.candidate_budget - len(search_candidates))
        configured_advisor_budgets = (
            context.values.get("advisor_budgets", {})
            if context.values is not None
            else {}
        )
        advisor_budgets = self._advisor_budgets(
            remaining_budget,
            configured_advisor_budgets if isinstance(configured_advisor_budgets, dict) else {},
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
        evaluated = dependencies.evaluator.evaluate(request, context, candidates)
        decision = dependencies.promotion_gate.decide(
            evaluated.selected_evaluation,
            context.current_best,
        )
        artifacts = tuple(dependencies.artifact_writer.write(request, evaluated, decision))
        warnings: list[str] = []
        if len(candidates) > request.candidate_budget:
            warnings.append("candidate_budget_exceeded")
        result = TrainingRoundResult(
            candidate_summaries=evaluated.candidate_summaries,
            evaluation=evaluated.selected_evaluation,
            promotion_decision=decision,
            artifacts=artifacts,
            warnings=tuple(warnings),
        )
        dependencies.repository.save_round(request, result)
        dependencies.event_publisher.publish(request, result)
        return result

    def run_runtime_round(self) -> dict | None:
        if self.runtime_rounds is None:
            raise RuntimeError("runtime round iterator is not configured")
        try:
            return next(self.runtime_rounds)
        except StopIteration as completed:
            self.final_status = completed.value or self.final_status or {}
            return None

    def _advisor_budgets(self, remaining_budget: int, configured: dict) -> dict[str, int]:
        budgets: dict[str, int] = {}
        remaining = remaining_budget
        dependencies = self._application_dependencies()
        for advisor in dependencies.advisor_registry.advisors:
            count = min(remaining, max(0, int(configured.get(advisor.key, 0))))
            budgets[advisor.key] = count
            remaining -= count
        return budgets

    def _application_dependencies(self) -> TrainingDependencies:
        if self.dependencies is None:
            raise RuntimeError("application dependencies are not configured")
        return self.dependencies
