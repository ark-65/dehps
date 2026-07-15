from __future__ import annotations

from contextlib import contextmanager

from dehps.forward_runtime.evaluation_service import ForwardEvaluationService


def run_row() -> dict:
    return {
        "prediction_run_key": "static_100:2026080:snapshot-1",
        "line_key": "static_100",
        "line_label": "Static",
        "line_kind": "static",
        "snapshot_key": "snapshot-1",
        "source_run_id": "training-1",
        "source_round_index": 1,
        "as_of_issue": "2026079",
        "target_issue": "2026080",
        "train_mode": "expanding",
        "train_window": 900,
        "top_n": 1,
        "candidate_count": 1,
        "config_hash": "config-1",
        "config": {},
        "metadata": {},
        "status": "pending",
    }


class Result:
    def fetchone(self):
        return (1,)


class Connection:
    def __init__(self, service):
        self.service = service

    def execute(self, sql, params=None):
        if "SET status = 'evaluated'" in sql:
            self.service.status = "evaluated"
        return Result()


class Harness(ForwardEvaluationService):
    def __init__(self, *, draw, evaluator, promotion_reconciler=None):
        self.status = "pending"
        self.attempts = 0
        self.failure = None

        @contextmanager
        def connection_factory():
            yield Connection(self)

        super().__init__(
            connection_factory=connection_factory,
            actual_loader=lambda _conn, **_kwargs: draw,
            prediction_loader=lambda _conn, **_kwargs: (
                [{"rank": 1, "red_numbers": [4, 5, 11, 19, 27, 32], "score": 1.0}],
                None,
            ),
            ranking_auditor=lambda *_args, **_kwargs: {"model_score_rank": 1},
            snapshot_evaluator=evaluator,
            promotion_reconciler=promotion_reconciler or (
                lambda **_kwargs: {"status": "no_active_cohort", "promote": False}
            ),
        )

    def pending_runs(self):
        if self.status not in {"pending", "evaluation_failed"}:
            return []
        row = run_row()
        row["status"] = self.status
        return [row]

    def _claim(self, prediction_run_key, target_issue, evaluation_run_key):
        if self.status not in {"pending", "evaluation_failed"}:
            return False
        self.status = "evaluating"
        self.attempts += 1
        return True

    def _record_failure(self, prediction_run_key, evaluation_run_key, error):
        self.status = "evaluation_failed"
        self.failure = error


def accepted_payload(*_args, **_kwargs):
    return {
        "status": "evaluated",
        "candidate_count": 1,
        "summary": {"leakage_passed": True},
    }


def test_pending_run_stays_pending_until_draw_exists() -> None:
    service = Harness(draw=None, evaluator=accepted_payload)

    result = service.evaluate_pending(write_report=False)

    assert result["missing_draw_count"] == 1
    assert result["evaluated_count"] == 0
    assert service.status == "pending"
    assert service.attempts == 0


def test_draw_availability_triggers_evaluation_and_repeat_is_idempotent() -> None:
    service = Harness(
        draw={"issue": "2026080", "red_numbers": [4, 5, 11, 19, 27, 32]},
        evaluator=accepted_payload,
    )

    first = service.evaluate_pending(write_report=False)
    second = service.evaluate_pending(write_report=False)

    assert first["evaluated_count"] == 1
    assert second["pending_count"] == 0
    assert service.status == "evaluated"
    assert service.attempts == 1


def test_failed_evaluation_records_status_and_retries() -> None:
    calls = 0

    def flaky(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("database unavailable")
        return accepted_payload()

    service = Harness(
        draw={"issue": "2026080", "red_numbers": [4, 5, 11, 19, 27, 32]},
        evaluator=flaky,
    )

    first = service.evaluate_pending(write_report=False)
    second = service.evaluate_pending(write_report=False)

    assert first["failed_count"] == 1
    assert service.failure == {"type": "RuntimeError", "message": "database unavailable"}
    assert second["evaluated_count"] == 1
    assert service.status == "evaluated"
    assert service.attempts == 2


def test_promotion_reconciliation_failure_is_structured_without_undoing_evaluation() -> None:
    def fail_reconciliation(**_kwargs):
        raise RuntimeError("promotion database unavailable")

    service = Harness(
        draw={"issue": "2026080", "red_numbers": [4, 5, 11, 19, 27, 32]},
        evaluator=accepted_payload,
        promotion_reconciler=fail_reconciliation,
    )

    result = service.evaluate_pending(write_report=False)

    assert result["evaluated_count"] == 1
    assert service.status == "evaluated"
    assert result["forward_promotion"] == {
        "status": "reconciliation_failed",
        "promote": False,
        "error": {
            "type": "RuntimeError",
            "message": "promotion database unavailable",
        },
    }
