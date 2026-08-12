from __future__ import annotations

from contextlib import contextmanager

import pytest
from dehps.forward_runtime.evaluation_service import ForwardEvaluationService


@pytest.fixture
def inactive_legacy_retirement(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "dehps.prediction.v2.retirement.DEFAULT_ACTIVATION_PATH",
        tmp_path / "legacy-retirement-not-activated.json",
    )


pytestmark = pytest.mark.usefixtures("inactive_legacy_retirement")


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
        "ranking_contract": None,
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
    def __init__(
        self,
        *,
        draw,
        evaluator,
        artifact_adapter=None,
        promotion_reconciler=None,
    ):
        self.status = "pending"
        self.attempts = 0
        self.failure = None
        self.finalized = []

        def finalizer(_conn, payload, **kwargs):
            self.finalized.append({"payload": payload, "kwargs": kwargs})
            return payload

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
            snapshot_finalizer=finalizer,
            artifact_adapter=artifact_adapter,
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

    def _claim(self, prediction_run_key, target_issue, evaluation_run_key, prediction_ranking_contract):
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
    assert first["results"][0]["ranking_contract"] == "legacy_score_partition"
    assert first["results"][0]["evaluation_artifact"]["status"] == "unavailable"
    assert first["results"][0]["evaluation_artifact"]["reason"] == "legacy_ranking_contract"
    assert len(service.finalized) == 1
    assert service.finalized[0]["kwargs"] == {
        "output_dir": None,
        "write_report": False,
        "persist": True,
    }


def test_evaluation_receives_the_normalized_prediction_contract() -> None:
    received = None
    persistence = None

    def evaluator(*_args, **kwargs):
        nonlocal received, persistence
        received = kwargs["prediction_ranking_contract"]
        persistence = (kwargs["write_report"], kwargs["persist"])
        return accepted_payload()

    service = Harness(
        draw={"issue": "2026080", "red_numbers": [4, 5, 11, 19, 27, 32]},
        evaluator=evaluator,
    )

    result = service.evaluate_pending(write_report=False)

    assert result["evaluated_count"] == 1
    assert received == "legacy_score_partition"
    assert persistence == (False, False)


def test_artifact_projection_is_attached_before_the_single_finalize() -> None:
    def artifact_adapter(**kwargs):
        assert kwargs["evaluation_payload"]["summary"] == {"leakage_passed": True}
        assert kwargs["write_artifact"] is True
        return {
            "protocol": "forward_evaluation_artifact_projection.v1",
            "status": "verified",
            "artifact_digest": "a" * 64,
        }

    service = Harness(
        draw={"issue": "2026080", "red_numbers": [4, 5, 11, 19, 27, 32]},
        evaluator=accepted_payload,
        artifact_adapter=artifact_adapter,
    )

    result = service.evaluate_pending(write_report=True)

    assert result["evaluated_count"] == 1
    assert result["results"][0]["evaluation_artifact"]["status"] == "verified"
    assert len(service.finalized) == 1
    assert service.finalized[0]["payload"]["summary"]["evaluation_artifact"][
        "artifact_digest"
    ] == "a" * 64
    assert service.finalized[0]["kwargs"]["write_report"] is True


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


def test_required_artifact_failure_is_structured_and_retryable() -> None:
    calls = 0

    class RequiredArtifactError(RuntimeError):
        def as_dict(self):
            return {
                "code": "forward_evaluation_artifact_required",
                "projection": {"status": "failed", "reason": "runtime_envelope_parse_error"},
            }

    def artifact_adapter(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RequiredArtifactError("required artifact unavailable")
        return {"status": "verified", "artifact_digest": "a" * 64}

    service = Harness(
        draw={"issue": "2026080", "red_numbers": [4, 5, 11, 19, 27, 32]},
        evaluator=accepted_payload,
        artifact_adapter=artifact_adapter,
    )

    first = service.evaluate_pending(write_report=False)
    second = service.evaluate_pending(write_report=False)

    assert first["failed_count"] == 1
    assert first["results"][0]["error"]["details"]["code"] == (
        "forward_evaluation_artifact_required"
    )
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
