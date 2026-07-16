from dehps.training.orchestration_state import (
    ProductionOrchestrationState,
    orchestration_decision,
)


def test_waiting_for_draw_is_a_production_lock_not_a_global_training_lock() -> None:
    decision = orchestration_decision(
        active_prediction_exists=True,
        target_draw_available=False,
    )

    assert decision.state is ProductionOrchestrationState.WAITING_FOR_DRAW
    assert decision.production_prediction_allowed is False
    assert decision.research_training_allowed is True
    assert decision.evaluation_allowed is False
    assert decision.research_state == "RESEARCH_ONLY"


def test_draw_arrival_switches_the_production_chain_to_evaluation() -> None:
    decision = orchestration_decision(
        active_prediction_exists=True,
        target_draw_available=True,
    )

    assert decision.state is ProductionOrchestrationState.READY_FOR_EVALUATION
    assert decision.production_prediction_allowed is False
    assert decision.research_training_allowed is True
    assert decision.evaluation_allowed is True


def test_no_active_prediction_is_ready_for_production() -> None:
    decision = orchestration_decision(
        active_prediction_exists=False,
        target_draw_available=False,
    )

    assert decision.state is ProductionOrchestrationState.READY_FOR_PRODUCTION
    assert decision.production_prediction_allowed is True
    assert decision.research_training_allowed is True
