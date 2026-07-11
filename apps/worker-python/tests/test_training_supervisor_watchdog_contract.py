from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_watchdog_fails_closed_before_advisor_refresh_or_supervisor_start():
    script = (REPO_ROOT / "scripts/ensure_training_supervisor.sh").read_text(
        encoding="utf-8"
    )

    guarded_call = (
        'if ! evaluate_synced_predictions_if_needed "$sync_output_file" '
        '"$sync_from_issue" "$latest_issue" "$prediction_snapshot_file"; then'
    )
    assert guarded_call in script
    assert "forward prediction evaluation did not complete safely" in script
    assert script.index(guarded_call) < script.index('if [[ "$signal_refresh_needed" == true ]]')
    assert script.index(guarded_call) < script.index("setsid bash -lc")
    assert "plan_synced_prediction_evaluations.py" in script
    assert "refusing advisor refresh or supervisor start" in script


def test_watchdog_always_rechecks_due_snapshots_for_idempotent_retry():
    script = (REPO_ROOT / "scripts/ensure_training_supervisor.sh").read_text(
        encoding="utf-8"
    )
    function_body = script.split(
        "evaluate_synced_predictions_if_needed() {", 1
    )[1].split("\n}\n\ntraining_pid_as_of_issue()", 1)[0]

    assert "plan_synced_prediction_evaluations.py" in function_body
    assert "prediction evaluation skipped changed_count" not in function_body
    assert "forward prediction evaluation batch accepted count=0" not in function_body
