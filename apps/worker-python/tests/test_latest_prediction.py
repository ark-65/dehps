from datetime import datetime, timezone

from dehps.forward_runtime.latest_prediction import (
    build_latest_prediction_payload,
    render_latest_prediction,
)


def _run(line_key: str, *, status: str = "pending") -> dict:
    return {
        "prediction_run_key": f"{line_key}:2026081:snapshot",
        "line_key": line_key,
        "line_label": line_key,
        "line_kind": line_key,
        "source_run_id": "run-1",
        "source_round_index": 8,
        "as_of_issue": "2026080",
        "target_issue": "2026081",
        "status": status,
        "generated_at": datetime(2026, 7, 15, tzinfo=timezone.utc),
        "candidate_count": 10000,
        "config_hash": f"hash-{line_key}",
        "metadata": {
            "git_commit": "source123",
            "prediction_metadata": {"protocol": f"{line_key}-model-v1"},
        },
    }


def test_latest_prediction_builds_three_lines_and_cross_line_consensus():
    runs = [_run("static_100"), _run("dynamic_kdj"), _run("dynamic_kdj_near")]
    candidates = []
    for run in runs:
        candidates.extend(
            (
                {
                    "prediction_run_key": run["prediction_run_key"],
                    "rank": 1,
                    "red_numbers": [1, 2, 3, 4, 5, 6],
                    "score": 0.5,
                },
                {
                    "prediction_run_key": run["prediction_run_key"],
                    "rank": 2,
                    "red_numbers": [1, 7, 8, 9, 10, 11],
                    "score": 0.4,
                },
            )
        )

    payload = build_latest_prediction_payload(
        runs,
        candidates,
        git_commit="abc123",
        top_limit=10,
    )

    assert payload["status"] == "waiting_draw"
    assert payload["git_commit"] == "source123"
    assert payload["viewer_git_commit"] == "abc123"
    assert payload["missing_lines"] == []
    assert payload["lines"][0]["prediction_run_key"] == "static_100:2026081:snapshot"
    assert payload["lines"][0]["line_kind"] == "static_100"
    assert payload["lines"][0]["model_version"] == "static_100-model-v1"
    assert payload["lines"][0]["parameter_version"] == "hash-static_100"
    assert payload["lines"][0]["ranking_contract"] == "legacy_score_partition"
    assert payload["lines"][0]["runtime_envelope"] == {
        "protocol": "runtime_envelope_projection.v1",
        "status": "unavailable",
        "reason": "legacy_prediction_without_runtime_envelope",
        "envelope": None,
    }
    assert payload["runtime_envelope_summary"] == {
        "status": "unavailable",
        "verified_count": 0,
        "unavailable_count": 3,
        "envelope_digests": [],
    }
    assert payload["shadow_scoring_summary"] == {
        "status": "unavailable",
        "captured_count": 0,
        "failed_count": 0,
        "unavailable_count": 3,
        "comparison_digests": [],
    }
    assert [line["line_key"] for line in payload["lines"]] == [
        "static_100",
        "dynamic_kdj",
        "dynamic_kdj_near",
    ]
    assert payload["consensus_numbers"][0] == {
        "number": 1,
        "line_count": 3,
        "candidate_occurrences": 6,
    }
    rendered = render_latest_prediction(payload)
    assert "Issue: 2026081" in rendered
    assert "Git (prediction source): source123" in rendered
    assert rendered.count("run=run-1 round=8 prediction_run=") == 3
    assert "model=static_100-model-v1 parameters=hash-static_100" in rendered
    assert "ranking_contract=legacy_score_partition" in rendered
    assert "runtime_envelope=unavailable" in rendered
    assert "shadow_scoring=unavailable" in rendered
    assert "Consensus across all lines: 01(6)" in rendered


def test_latest_prediction_reports_missing_line_instead_of_hiding_it():
    payload = build_latest_prediction_payload(
        [_run("static_100")],
        [],
        git_commit="abc123",
    )

    assert payload["status"] == "incomplete_lines"
    assert payload["missing_lines"] == ["dynamic_kdj", "dynamic_kdj_near"]


def test_latest_prediction_surfaces_structured_shadow_capture_failure():
    run = _run("static_100")
    run["metadata"]["shadow_scoring_failure"] = {
        "protocol": "scoring-kernel-shadow-capture-failure.v1",
        "status": "failed",
        "error": {"code": "backend_failed", "message": "numba unavailable"},
        "automatic_promotion_allowed": False,
    }

    payload = build_latest_prediction_payload([run], [], git_commit="abc123")

    assert payload["lines"][0]["shadow_scoring"]["status"] == "failed"
    assert payload["shadow_scoring_summary"] == {
        "status": "failed",
        "captured_count": 0,
        "failed_count": 1,
        "unavailable_count": 0,
        "comparison_digests": [],
    }


def test_latest_prediction_displays_optional_forward_challenger_without_changing_consensus():
    runs = [
        _run("static_100"),
        _run("dynamic_kdj"),
        _run("dynamic_kdj_near"),
        _run("forward_challenger"),
    ]
    candidates = [
        {
            "prediction_run_key": run["prediction_run_key"],
            "rank": 1,
            "red_numbers": [1, 2, 3, 4, 5, 6]
            if run["line_key"] != "forward_challenger"
            else [7, 8, 9, 10, 11, 12],
            "score": 0.5,
        }
        for run in runs
    ]

    payload = build_latest_prediction_payload(runs, candidates, git_commit="abc123")

    assert [line["line_key"] for line in payload["lines"]][-1] == "forward_challenger"
    assert [item["number"] for item in payload["consensus_numbers"]] == [1, 2, 3, 4, 5, 6]
    assert payload["missing_lines"] == []
