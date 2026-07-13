from __future__ import annotations

from dataclasses import dataclass

from dehps.training.dependencies import TrainingDependencies
from dehps.training.models import CandidateProposal, TrainingRoundRequest, TrainingRoundResult


@dataclass(frozen=True)
class TrainingRoundRunner:
    dependencies: TrainingDependencies

    def run(self, request: TrainingRoundRequest) -> TrainingRoundResult:
        context = self.dependencies.repository.load_context(request)
        search_candidates = tuple(self.dependencies.candidate_search.propose(request, context))
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
        advisor_candidates = self.dependencies.advisor_registry.propose(
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
        evaluated = self.dependencies.evaluator.evaluate(request, context, candidates)
        decision = self.dependencies.promotion_gate.decide(
            evaluated.selected_evaluation,
            context.current_best,
        )
        artifacts = tuple(self.dependencies.artifact_writer.write(request, evaluated, decision))
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
        self.dependencies.repository.save_round(request, result)
        self.dependencies.event_publisher.publish(request, result)
        return result

    def _advisor_budgets(self, remaining_budget: int, configured: dict) -> dict[str, int]:
        budgets: dict[str, int] = {}
        remaining = remaining_budget
        for advisor in self.dependencies.advisor_registry.advisors:
            count = min(remaining, max(0, int(configured.get(advisor.key, 0))))
            budgets[advisor.key] = count
            remaining -= count
        return budgets
