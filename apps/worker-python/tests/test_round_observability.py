from datetime import datetime

from dehps.training.round_observability import RoundStageTracker


def test_round_stage_tracker_preserves_target_progress_and_stage_durations():
    status = {"latest_progress": {"target_index": 7}}
    published = []
    logged = []
    ticks = iter((10.0, 12.5, 12.5))
    tracker = RoundStageTracker(
        status=status,
        publish=lambda: published.append(status["round_execution"].copy()),
        log=logged.append,
        monotonic=lambda: next(ticks),
        now=lambda: datetime(2026, 7, 15, 12, 0, 0),
    )

    tracker.transition(
        "main_evaluation",
        round_index=3,
        active_workers=16,
        generated_config_count=28,
        selected_config_count=19,
        target_completed=0,
        target_total=100,
    )
    tracker.update_target_progress(completed=10, total=100, publish=False)
    tracker.transition(
        "post_evaluation_diagnostics",
        round_index=3,
        active_workers=1,
        generated_config_count=28,
        selected_config_count=19,
        target_completed=100,
        target_total=100,
    )

    execution = status["round_execution"]
    assert status["latest_progress"] == {"target_index": 7}
    assert execution["stage"] == "post_evaluation_diagnostics"
    assert execution["active_workers"] == 1
    assert execution["completed_stages"] == [
        {
            "stage": "main_evaluation",
            "elapsed_seconds": 2.5,
            "completed_at": "2026-07-15T12:00:00",
            "active_workers": 16,
            "generated_config_count": 28,
            "selected_config_count": 19,
            "target_progress": {"completed": 10, "total": 100},
        }
    ]
    assert "stage=main_evaluation" in logged[0]
    assert len(published) == 2


def test_round_stage_tracker_marks_failure_without_swallowing_error():
    status = {}
    tracker = RoundStageTracker(
        status=status,
        publish=lambda: None,
        log=lambda _message: None,
        monotonic=lambda: 1.0,
        now=lambda: datetime(2026, 7, 15, 12, 0, 0),
    )
    tracker.transition("prefilter", round_index=1, active_workers=4)

    tracker.fail(error=RuntimeError("boom"))

    assert status["round_execution"]["status"] == "failed"
    assert status["round_execution"]["active_workers"] == 0
    assert status["round_execution"]["error"] == {
        "type": "RuntimeError",
        "message": "boom",
    }


def test_round_stage_tracker_keeps_bounded_completed_round_history():
    status = {}
    tracker = RoundStageTracker(
        status=status,
        publish=lambda: None,
        log=lambda _message: None,
        monotonic=lambda: 1.0,
        now=lambda: datetime(2026, 7, 15, 12, 0, 0),
    )

    for round_index in range(1, 11):
        tracker.transition("main_evaluation", round_index=round_index, active_workers=16)
        tracker.complete(round_index=round_index)

    history = status["round_execution_history"]
    assert [item["round"] for item in history] == list(range(3, 11))
    assert all(item["status"] == "completed" for item in history)
    assert history[-1]["completed_stages"][0]["stage"] == "main_evaluation"
