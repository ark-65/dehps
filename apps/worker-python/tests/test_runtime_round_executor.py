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


def test_production_session_stops_before_next_round_on_frozen_plateau(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        "dehps.training.production_runtime.publish_status_snapshot",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "dehps.training.production_runtime.write_report",
        lambda *_args, **_kwargs: None,
    )
    status = {
        "status": "running",
        "objective_policy_version": "rank_objective_v1",
        "objective_policy_hash": "policy-hash",
        "frozen_plateau": {
            "stop_requested": True,
            "stop_reason": "frozen_validation_plateau",
        },
    }
    state = RuntimeTrainingState(
        values={
            "round_index": 40,
            "deadline": None,
            "max_rounds": 512,
            "run_id": "run-plateau",
            "as_of_issue_value": "2026083",
            "history_fingerprint_value": "history",
            "max_configs_per_round": 20,
            "status": status,
            "status_path": tmp_path / "status.json",
            "report_path": tmp_path / "report.md",
            "resolved_event_url": None,
            "write_status_json": True,
            "pool": None,
            "best_summary": None,
        }
    )

    session = ProductionTrainingSession(state)

    assert session.next_request() is None
    assert status["status"] == "stopped_plateau"
    assert session._finished is True
