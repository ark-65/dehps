from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_watchdog_reads_local_history_before_advisor_refresh_or_supervisor_start():
    script = (REPO_ROOT / "scripts/ensure_training_supervisor.sh").read_text(
        encoding="utf-8"
    )

    local_history_gate = 'latest_issue="$(latest_db_issue)"'
    assert local_history_gate in script
    assert "draw synchronization is decoupled from training watchdog" in script
    assert script.index(local_history_gate) < script.index('if [[ "$signal_refresh_needed" == true ]]')
    assert script.index(local_history_gate) < script.index("setsid bash -lc")
    assert "scripts/sync_latest_ssq.py" not in script
    assert "scripts/plan_ssq_remote_sync_poll.py" not in script


def test_draw_sync_responsibility_moved_to_independent_watch_process():
    script = (REPO_ROOT / "scripts/ensure_training_supervisor.sh").read_text(
        encoding="utf-8"
    )
    ensure_draw_sync = (REPO_ROOT / "scripts/ensure_draw_sync_watch.sh").read_text(
        encoding="utf-8"
    )
    draw_watch = (
        REPO_ROOT / "apps/worker-python/scripts/run_draw_sync_watch.py"
    ).read_text(encoding="utf-8")

    assert "run_draw_sync_watch.py" in ensure_draw_sync
    assert "DEHPS_DRAW_SYNC_INTERVAL_SECONDS:-900" in ensure_draw_sync
    assert "DEHPS_DRAW_SYNC_HOT_INTERVAL_SECONDS:-300" in ensure_draw_sync
    assert 'VERSION_FILE="$LOG_DIR/draw-sync-watch.version"' in ensure_draw_sync
    assert 'LAUNCH_CONTRACT_FILE="$LOG_DIR/draw-sync-watch.launch.json"' in ensure_draw_sync
    assert 'desired_commit="$(git -C "$REPO_ROOT" rev-parse HEAD' in ensure_draw_sync
    assert 'running_commit" == "$desired_commit"' in ensure_draw_sync
    assert 'running_launch_digest" == "$desired_contract_digest"' in ensure_draw_sync
    assert "dehps.draw_sync.launch_contract" in ensure_draw_sync
    assert "dehps.draw_sync.supervisor_ownership" in ensure_draw_sync
    assert "--require-manual-ownership" in ensure_draw_sync
    assert "draw sync supervisor ownership rejected manual mutation" in ensure_draw_sync
    assert "--shadow-attestation-enabled" in ensure_draw_sync
    assert "started with wrong launch contract" in ensure_draw_sync
    assert "stopping stale draw sync watch" in ensure_draw_sync
    assert "refusing overlapping restart" in ensure_draw_sync
    assert "source worktree is dirty; refusing draw sync watcher restart" in ensure_draw_sync
    assert "dehps.draw_sync.scheduler" in draw_watch
    assert "run_draw_sync_watch.py" not in script


def test_systemd_draw_sync_has_a_separate_verified_deployment_path():
    deployment = (REPO_ROOT / "scripts/ensure_draw_sync_systemd.sh").read_text(
        encoding="utf-8"
    )
    service = (REPO_ROOT / "deploy/systemd/dehps-draw-sync.service").read_text(
        encoding="utf-8"
    )

    assert 'if [[ "${1:-}" != "--apply" ]]' in deployment
    assert "dehps.draw_sync.systemd_deployment" in deployment
    assert 'systemctl --user stop "$SYSTEMD_TIMER" "$SYSTEMD_UNIT"' in deployment
    assert "unmanaged draw-sync watcher remains" in deployment
    assert "draw-sync oneshot launch digest mismatch" in deployment
    assert 'systemctl --user enable --now "$SYSTEMD_TIMER"' in deployment
    assert "draw-sync systemd deployment rolled back" in deployment
    assert "Type=oneshot" in service
    assert "Restart=always" not in service
    assert "EnvironmentFile=-/home/ark/.config/dehps/draw-sync.env" in service
    assert "--once --no-resume-on-event" in service


def test_watchdog_no_longer_runs_synced_prediction_evaluation():
    script = (REPO_ROOT / "scripts/ensure_training_supervisor.sh").read_text(
        encoding="utf-8"
    )

    assert "evaluate_synced_predictions_if_needed" not in script
    assert "plan_synced_prediction_evaluations.py" not in script
    assert "evaluate_training_prediction.py" not in script


def test_watchdog_blocks_unresolved_local_draw_conflicts_before_forward_release():
    script = (REPO_ROOT / "scripts/ensure_training_supervisor.sh").read_text(
        encoding="utf-8"
    )

    conflict_gate = "draw conflict audit blocked release"
    assert "sync_conflict_draw_count" not in script
    assert "unresolved_data_conflict_count" in script
    assert conflict_gate in script
    assert "refusing advisor refresh or supervisor start" in script
    assert script.index(conflict_gate) < script.index('if [[ "$signal_refresh_needed" == true ]]')
    assert script.index(conflict_gate) < script.index("setsid bash -lc")


def test_watchdog_checks_runtime_storage_before_advisor_or_heavy_work():
    script = (REPO_ROOT / "scripts/ensure_training_supervisor.sh").read_text(
        encoding="utf-8"
    )

    storage_gate = "runtime storage capacity blocked advisor refresh and supervisor start"
    assert "scripts/check_runtime_storage_capacity.py" in script
    assert storage_gate in script
    assert script.index(storage_gate) < script.index('latest_issue="$(latest_db_issue)"')
    assert script.index(storage_gate) < script.index("setsid bash -lc")


def test_watchdog_refuses_automated_training_from_a_dirty_source_tree():
    script = (REPO_ROOT / "scripts/ensure_training_supervisor.sh").read_text(
        encoding="utf-8"
    )

    dirty_gate = "source worktree is dirty; refusing automated production or research training"
    assert "git -C \"$REPO_ROOT\" status --porcelain=v1 --untracked-files=all" in script
    assert dirty_gate in script
    assert script.index(dirty_gate) < script.index("scripts/check_runtime_storage_capacity.py")
    assert script.index(dirty_gate) < script.index("setsid bash -lc")


def test_watchdog_decouples_remote_sync_from_ten_minute_local_checks():
    script = (REPO_ROOT / "scripts/ensure_training_supervisor.sh").read_text(
        encoding="utf-8"
    )

    assert "scripts/plan_ssq_remote_sync_poll.py" not in script
    assert "remote_sync_plan_status" not in script
    assert "remote SSQ sync skipped by cold cadence" not in script
    assert "skipped_remote_cold_cadence" not in script
    assert "draw synchronization is decoupled from training watchdog" in script


def test_watchdog_closes_inherited_cron_lock_before_supervisor_exec():
    script = (REPO_ROOT / "scripts/ensure_training_supervisor.sh").read_text(
        encoding="utf-8"
    )

    close_guard = '[[ "$(readlink "$fd_path" 2>/dev/null || true)" == "$watchdog_lock" ]]'
    supervisor_exec = 'exec .venv/bin/python "${args[@]}"'
    assert 'watchdog_lock="$5"' in script
    assert 'for fd_path in /proc/$$/fd/*; do' in script
    assert close_guard in script
    assert 'eval "exec ${fd}>&-"' in script
    assert script.index(close_guard) < script.index(supervisor_exec)
    assert '"$LOG_DIR/training-supervisor-watchdog.lock"' in script


def test_training_launcher_uses_validated_scale_defaults_and_keeps_them_overrideable():
    script = (REPO_ROOT / "scripts/ensure_training_supervisor.sh").read_text(
        encoding="utf-8"
    )

    assert 'NEURAL_KDJ_BUDGET_SHARE="${DEHPS_NEURAL_KDJ_BUDGET_SHARE:-0.20}"' in script
    assert 'MAX_CONFIGS_PER_ROUND="${DEHPS_MAX_CONFIGS_PER_ROUND:-96}"' in script
    assert 'MEMORY_BUDGET_GB="${DEHPS_MEMORY_BUDGET_GB:-24}"' in script
    assert 'NEURAL_KDJ_HIDDEN_UNITS="${DEHPS_NEURAL_KDJ_HIDDEN_UNITS:-8}"' in script
    assert 'NEURAL_KDJ_EPOCHS="${DEHPS_NEURAL_KDJ_EPOCHS:-120}"' in script
    assert 'TARGET_INVERSION_MAX_CANDIDATES="${DEHPS_TARGET_INVERSION_MAX_CANDIDATES:-8}"' in script
    assert 'TARGET_INVERSION_MAX_DELTAS="${DEHPS_TARGET_INVERSION_MAX_DELTAS:-12}"' in script
    assert 'PROGRESS_INTERVAL="${DEHPS_PROGRESS_INTERVAL:-5}"' in script
    assert '--max-configs-per-round "$max_configs_per_round"' in script
    assert '--memory-budget-gb "$memory_budget_gb"' in script
    assert '--neural-kdj-hidden-units "$neural_kdj_hidden_units"' in script
    assert '--neural-kdj-epochs "$neural_kdj_epochs"' in script
    assert '--target-weight-inversion-max-candidates "$target_inversion_max_candidates"' in script
    assert '--target-weight-inversion-max-deltas-per-target "$target_inversion_max_deltas"' in script
    assert '--progress-interval "$progress_interval"' in script
    assert '--workers "$training_workers"' in script
    assert "--cpu-threads 1" in script


def test_forward_wait_parks_only_production_and_runs_fingerprinted_research():
    script = (REPO_ROOT / "scripts/ensure_training_supervisor.sh").read_text(
        encoding="utf-8"
    )

    assert "state=WAITING_FOR_DRAW" in script
    assert "production_prediction_allowed=false" in script
    assert "research_state=RESEARCH_ONLY" in script
    assert "research_training_allowed=true" in script
    assert "scripts/run_isolated_research_lane.py" in script
    assert "--check-completed" in script
    assert "identical training fingerprint" in script
    assert 'RESEARCH_TRAIN_WINDOW="${DEHPS_RESEARCH_TRAIN_WINDOW:-900}"' in script
    assert 'RESEARCH_RANDOM_SEEDS="${DEHPS_RESEARCH_RANDOM_SEEDS:-}"' in script
    assert "--mode research" in script
    assert 'RESEARCH_TASKS="${DEHPS_RESEARCH_TASKS:-training-diagnostics,walk-forward,weight-grid,analytic-null-baseline}"' in script
    assert "seed_policy=${RESEARCH_RANDOM_SEEDS:-none}" in script
