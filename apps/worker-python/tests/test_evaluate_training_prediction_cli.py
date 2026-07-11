from scripts.evaluate_training_prediction import prediction_evaluation_succeeded


def test_prediction_evaluation_cli_accepts_only_evaluated_nonleaking_candidates():
    assert prediction_evaluation_succeeded(
        {
            "status": "evaluated",
            "candidate_count": 10000,
            "top_n": 10000,
            "summary": {"leakage_passed": True},
        }
    )


def test_prediction_evaluation_cli_rejects_missing_leaking_or_empty_results():
    assert not prediction_evaluation_succeeded(
        {
            "status": "missing_prediction_snapshot",
            "candidate_count": 0,
            "top_n": None,
            "summary": {},
        }
    )
    assert not prediction_evaluation_succeeded(
        {
            "status": "leakage_guard_failed",
            "candidate_count": 10000,
            "top_n": 10000,
            "summary": {"leakage_passed": False},
        }
    )
    assert not prediction_evaluation_succeeded(
        {
            "status": "evaluated",
            "candidate_count": 0,
            "top_n": 10000,
            "summary": {"leakage_passed": True},
        }
    )


def test_prediction_evaluation_cli_rejects_partial_ranked_set():
    assert not prediction_evaluation_succeeded(
        {
            "status": "evaluated",
            "candidate_count": 9999,
            "top_n": 10000,
            "summary": {"leakage_passed": True},
        }
    )
