from __future__ import annotations

from dehps.training.runtime_round_executor import (
    RuntimeRoundExecutor,
    RuntimeRoundOutcome,
    RuntimeRoundRequest,
    RuntimeTrainingState,
)
from dehps.training.production_runtime import ProductionTrainingSession


def test_runtime_round_executor_exposes_explicit_request_state_outcome_contract() -> None:
    assert RuntimeRoundExecutor.execute.__annotations__ == {
        "request": "RuntimeRoundRequest",
        "state": "RuntimeTrainingState",
        "return": "RuntimeRoundOutcome",
    }
    assert RuntimeRoundRequest.__dataclass_fields__["round"].type == "TrainingRoundRequest"
    assert RuntimeTrainingState.__dataclass_fields__["completed_rounds"].default == 0


def test_production_session_builds_two_explicit_requests_from_persistent_state() -> None:
    state = RuntimeTrainingState(
        values={
            "round_index": 0,
            "deadline": None,
            "max_rounds": 2,
            "run_id": "run-1",
            "as_of_issue_value": "2026079",
            "history_fingerprint_value": "history",
            "max_configs_per_round": 20,
            "status": {
                "objective_policy_version": "rank_objective_v1",
                "objective_policy_hash": "policy-hash",
            },
        }
    )
    session = ProductionTrainingSession(state)

    first = session.next_request()
    assert first is not None
    assert first.round_index == 1
    assert first.round.candidate_budget == 20
    state.values["round_index"] = 1
    state.completed_rounds = 1

    second = session.next_request()
    assert second is not None
    assert second.round_index == 2
    assert second.run_id == first.run_id
    assert second.round.history_fingerprint == first.round.history_fingerprint
