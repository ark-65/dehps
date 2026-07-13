from __future__ import annotations

from dehps.training.runtime_round_executor import (
    RuntimeRoundExecutor,
    RuntimeRoundOutcome,
    RuntimeRoundRequest,
    RuntimeTrainingState,
)


def test_runtime_round_executor_exposes_explicit_request_state_outcome_contract() -> None:
    assert RuntimeRoundExecutor.execute.__annotations__ == {
        "request": "RuntimeRoundRequest",
        "state": "RuntimeTrainingState",
        "return": "RuntimeRoundOutcome",
    }
    assert RuntimeRoundRequest.__dataclass_fields__["round"].type == "TrainingRoundRequest"
    assert RuntimeTrainingState.__dataclass_fields__["completed_rounds"].default == 0
