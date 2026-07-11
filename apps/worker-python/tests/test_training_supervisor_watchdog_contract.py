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


def test_watchdog_invalidates_accepted_evaluation_when_sync_changes_issue():
    script = (REPO_ROOT / "scripts/ensure_training_supervisor.sh").read_text(
        encoding="utf-8"
    )
    function_body = script.split(
        "evaluate_synced_predictions_if_needed() {", 1
    )[1].split("\n}\n\ntraining_pid_as_of_issue()", 1)[0]

    assert 'planner_args+=(--force-issue "$current_issue")' in function_body
    assert "sync changed current issue; forcing forward re-evaluation" in function_body
    assert function_body.index("--force-issue") < function_body.index(
        "plan_synced_prediction_evaluations.py"
    )


def test_watchdog_blocks_sync_conflicts_before_forward_release():
    script = (REPO_ROOT / "scripts/ensure_training_supervisor.sh").read_text(
        encoding="utf-8"
    )

    conflict_gate = "sync conflict audit blocked release"
    evaluation_call = (
        'if ! evaluate_synced_predictions_if_needed "$sync_output_file" '
        '"$sync_from_issue" "$latest_issue" "$prediction_snapshot_file"; then'
    )
    assert "sync_conflict_draw_count" in script
    assert "unresolved_data_conflict_count" in script
    assert conflict_gate in script
    assert "refusing evaluation, advisor refresh, or supervisor start" in script
    assert script.index(conflict_gate) < script.index(evaluation_call)
    assert script.index(conflict_gate) < script.index('if [[ "$signal_refresh_needed" == true ]]')
    assert script.index(conflict_gate) < script.index("setsid bash -lc")
