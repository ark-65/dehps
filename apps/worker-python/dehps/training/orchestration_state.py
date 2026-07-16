from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProductionOrchestrationState(str, Enum):
    READY_FOR_PRODUCTION = "READY_FOR_PRODUCTION"
    WAITING_FOR_DRAW = "WAITING_FOR_DRAW"
    READY_FOR_EVALUATION = "READY_FOR_EVALUATION"
    EVALUATING = "EVALUATING"
    READY_FOR_PROMOTION = "READY_FOR_PROMOTION"


@dataclass(frozen=True)
class OrchestrationDecision:
    state: ProductionOrchestrationState
    production_prediction_allowed: bool
    research_training_allowed: bool
    evaluation_allowed: bool
    research_state: str
    reason: str


def orchestration_decision(
    *,
    active_prediction_exists: bool,
    target_draw_available: bool,
    evaluation_in_progress: bool = False,
    evaluation_completed: bool = False,
) -> OrchestrationDecision:
    if evaluation_in_progress:
        state = ProductionOrchestrationState.EVALUATING
        reason = "evaluation_in_progress"
    elif active_prediction_exists and target_draw_available:
        state = ProductionOrchestrationState.READY_FOR_EVALUATION
        reason = "draw_available_for_active_prediction"
    elif active_prediction_exists:
        state = ProductionOrchestrationState.WAITING_FOR_DRAW
        reason = "active_prediction_waiting_for_draw"
    elif evaluation_completed:
        state = ProductionOrchestrationState.READY_FOR_PROMOTION
        reason = "forward_evaluation_completed"
    else:
        state = ProductionOrchestrationState.READY_FOR_PRODUCTION
        reason = "no_active_production_prediction"

    return OrchestrationDecision(
        state=state,
        production_prediction_allowed=(
            state is ProductionOrchestrationState.READY_FOR_PRODUCTION
        ),
        research_training_allowed=True,
        evaluation_allowed=(
            state is ProductionOrchestrationState.READY_FOR_EVALUATION
        ),
        research_state=(
            "RESEARCH_ONLY"
            if state is ProductionOrchestrationState.WAITING_FOR_DRAW
            else "RESEARCH_ALLOWED"
        ),
        reason=reason,
    )
