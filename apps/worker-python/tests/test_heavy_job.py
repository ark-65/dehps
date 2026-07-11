from __future__ import annotations

import json
import os
import time

import pytest

from dehps.runtime.heavy_job import (
    HeavyJobLockError,
    HeavyJobLockTimeout,
    apply_cpu_thread_env_defaults,
    cpu_thread_env_overrides,
    describe_heavy_job_owner,
    heavy_job_lock,
    is_pid_active,
    mark_inactive_heavy_job_owner,
    metadata_path_for,
    read_owner_metadata,
)


def test_acquiring_lock_writes_metadata_and_releases_cleanly(tmp_path):
    lock_path = tmp_path / "dehps-heavy-job.lock"
    metadata_path = metadata_path_for(lock_path)

    with heavy_job_lock(
        owner="unit-test",
        lock_path=lock_path,
        timeout_seconds=0,
        command=["pytest", "test_heavy_job.py"],
        context={"job": "heavy"},
    ) as lock:
        assert lock.metadata_path == metadata_path
        assert metadata_path.exists()

        metadata = read_owner_metadata(metadata_path)
        assert metadata is not None
        assert metadata["owner"] == "unit-test"
        assert metadata["pid"] == os.getpid()
        assert metadata["status"] == "running"
        assert metadata["command"] == ["pytest", "test_heavy_job.py"]
        assert metadata["context"] == {"job": "heavy"}
        assert metadata["started_at"]
        assert metadata["heartbeat_at"]

        owner_status = describe_heavy_job_owner(lock_path=lock_path)
        assert owner_status.active is True
        assert owner_status.pid_active is True

        lock.heartbeat(status="scanning", context={"phase": 2})
        updated = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert updated["status"] == "scanning"
        assert updated["context"] == {"job": "heavy", "phase": 2}

    assert not metadata_path.exists()

    with heavy_job_lock(owner="unit-test-2", lock_path=lock_path, timeout_seconds=0):
        assert metadata_path.exists()


def test_second_acquire_times_out_while_first_lock_is_held(tmp_path):
    lock_path = tmp_path / "dehps-heavy-job.lock"

    with heavy_job_lock(owner="first", lock_path=lock_path, timeout_seconds=0):
        with pytest.raises(HeavyJobLockTimeout):
            with heavy_job_lock(owner="second", lock_path=lock_path, blocking=False):
                raise AssertionError("second lock should not be acquired")

        with pytest.raises(HeavyJobLockTimeout):
            with heavy_job_lock(
                owner="second",
                lock_path=lock_path,
                timeout_seconds=0.01,
                poll_interval_seconds=0.001,
            ):
                raise AssertionError("second lock should not be acquired")


def test_auto_heartbeat_refreshes_metadata_while_lock_is_held(tmp_path):
    lock_path = tmp_path / "dehps-heavy-job.lock"
    metadata_path = metadata_path_for(lock_path)

    with heavy_job_lock(
        owner="heartbeat-test",
        lock_path=lock_path,
        timeout_seconds=0,
        auto_heartbeat_interval_seconds=0.01,
    ):
        first = read_owner_metadata(metadata_path)
        assert first is not None
        first_mtime = metadata_path.stat().st_mtime_ns
        for _ in range(20):
            time.sleep(0.01)
            current = read_owner_metadata(metadata_path)
            assert current is not None
            if metadata_path.stat().st_mtime_ns != first_mtime:
                break
        else:
            raise AssertionError("auto heartbeat did not refresh metadata")

    assert not metadata_path.exists()


def test_cpu_thread_env_helper_fills_missing_without_overriding_explicit_values():
    env = {
        "OPENBLAS_NUM_THREADS": "8",
        "OTHER_ENV": "kept",
    }

    overrides = cpu_thread_env_overrides(2, env=env)
    assert overrides == {
        "OMP_NUM_THREADS": "2",
        "MKL_NUM_THREADS": "2",
        "NUMEXPR_NUM_THREADS": "2",
    }

    applied = apply_cpu_thread_env_defaults(2, env=env)
    assert applied == overrides
    assert env["OPENBLAS_NUM_THREADS"] == "8"
    assert env["OMP_NUM_THREADS"] == "2"
    assert env["MKL_NUM_THREADS"] == "2"
    assert env["NUMEXPR_NUM_THREADS"] == "2"
    assert env["OTHER_ENV"] == "kept"

    forced = cpu_thread_env_overrides(3, env=env, override=True)
    assert forced == {
        "OPENBLAS_NUM_THREADS": "3",
        "OMP_NUM_THREADS": "3",
        "MKL_NUM_THREADS": "3",
        "NUMEXPR_NUM_THREADS": "3",
    }


def test_dead_pid_metadata_is_reported_inactive(tmp_path):
    lock_path = tmp_path / "dehps-heavy-job.lock"
    metadata_path = metadata_path_for(lock_path)
    metadata_path.write_text(
        json.dumps(
            {
                "owner": "stale-job",
                "pid": 999_999_999,
                "started_at": "2026-06-18T00:00:00Z",
                "heartbeat_at": "2026-06-18T00:00:01Z",
                "status": "running",
                "command": ["old"],
                "context": {},
            }
        ),
        encoding="utf-8",
    )

    owner_status = describe_heavy_job_owner(lock_path=lock_path)

    assert owner_status.metadata is not None
    assert owner_status.metadata["owner"] == "stale-job"
    assert owner_status.active is False
    assert owner_status.pid_active is False
    assert owner_status.reason == "pid_not_running"


def test_stopped_owner_metadata_can_be_marked_waiting_without_losing_audit_context(tmp_path):
    lock_path = tmp_path / "dehps-heavy-job.lock"
    metadata_path = metadata_path_for(lock_path)
    metadata_path.write_text(
        json.dumps(
            {
                "owner": "training-supervisor",
                "pid": 999_999_999,
                "started_at": "2026-07-11T00:00:00Z",
                "heartbeat_at": "2026-07-11T00:01:00Z",
                "status": "running",
                "command": ["scripts/run_training_supervisor.py"],
                "context": {"train_window": 900},
            }
        ),
        encoding="utf-8",
    )

    updated = mark_inactive_heavy_job_owner(
        expected_pid=999_999_999,
        expected_owner="training-supervisor",
        status="waiting_for_forward_issue",
        lock_path=lock_path,
        context={"forward_wait": {"next_pending_issue": "2026079"}},
    )

    assert updated is not None
    assert updated["status"] == "waiting_for_forward_issue"
    assert updated["finished_at"] == updated["heartbeat_at"]
    assert updated["command"] == ["scripts/run_training_supervisor.py"]
    assert updated["context"] == {
        "train_window": 900,
        "forward_wait": {"next_pending_issue": "2026079"},
    }
    owner_status = describe_heavy_job_owner(lock_path=lock_path)
    assert owner_status.active is False
    assert owner_status.pid_active is False
    assert owner_status.reason == "status_waiting_for_forward_issue"


def test_inactive_metadata_transition_refuses_pid_or_owner_mismatch(tmp_path):
    lock_path = tmp_path / "dehps-heavy-job.lock"
    metadata_path = metadata_path_for(lock_path)
    metadata_path.write_text(
        json.dumps(
            {
                "owner": "new-job",
                "pid": 999_999_998,
                "status": "running",
                "context": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(HeavyJobLockError, match="expected pid"):
        mark_inactive_heavy_job_owner(
            expected_pid=999_999_999,
            status="waiting_for_forward_issue",
            lock_path=lock_path,
        )
    with pytest.raises(HeavyJobLockError, match="expected owner"):
        mark_inactive_heavy_job_owner(
            expected_pid=999_999_998,
            expected_owner="training-supervisor",
            status="waiting_for_forward_issue",
            lock_path=lock_path,
        )


def test_inactive_metadata_transition_refuses_live_pid_and_held_lock(tmp_path):
    lock_path = tmp_path / "dehps-heavy-job.lock"
    metadata_path = metadata_path_for(lock_path)
    metadata_path.write_text(
        json.dumps(
            {
                "owner": "live-job",
                "pid": os.getpid(),
                "status": "running",
                "context": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(HeavyJobLockError, match="pid_active=True"):
        mark_inactive_heavy_job_owner(
            expected_pid=os.getpid(),
            status="waiting_for_forward_issue",
            lock_path=lock_path,
        )

    with heavy_job_lock(owner="held-job", lock_path=lock_path):
        with pytest.raises(HeavyJobLockError, match="while lock is held"):
            mark_inactive_heavy_job_owner(
                expected_pid=os.getpid(),
                status="waiting_for_forward_issue",
                lock_path=lock_path,
            )


def test_fractional_pid_metadata_is_reported_unknown(tmp_path):
    lock_path = tmp_path / "dehps-heavy-job.lock"
    metadata_path = metadata_path_for(lock_path)
    metadata_path.write_text(
        json.dumps(
            {
                "owner": "bad-pid-job",
                "pid": os.getpid() + 0.5,
                "started_at": "2026-06-18T00:00:00Z",
                "heartbeat_at": "2026-06-18T00:00:01Z",
                "status": "running",
                "command": ["bad-pid"],
                "context": {},
            }
        ),
        encoding="utf-8",
    )

    owner_status = describe_heavy_job_owner(lock_path=lock_path)

    assert is_pid_active(f"{os.getpid()}.0") is None
    assert owner_status.active is False
    assert owner_status.pid_active is None
    assert owner_status.reason == "pid_unknown"


def test_unreadable_metadata_is_reported_inactive(tmp_path):
    lock_path = tmp_path / "dehps-heavy-job.lock"
    metadata_path = metadata_path_for(lock_path)
    metadata_path.mkdir()

    owner_status = describe_heavy_job_owner(lock_path=lock_path)

    assert owner_status.metadata is None
    assert owner_status.active is False
    assert owner_status.pid_active is None
    assert owner_status.reason == "metadata_unreadable"
    assert owner_status.error is not None
    assert str(metadata_path) in owner_status.error


def test_non_object_metadata_is_reported_inactive(tmp_path):
    lock_path = tmp_path / "dehps-heavy-job.lock"
    metadata_path = metadata_path_for(lock_path)
    metadata_path.write_text("[]", encoding="utf-8")

    owner_status = describe_heavy_job_owner(lock_path=lock_path)

    assert owner_status.metadata is None
    assert owner_status.active is False
    assert owner_status.pid_active is None
    assert owner_status.reason == "metadata_unreadable"
    assert owner_status.error is not None
    assert "expected object root" in owner_status.error


def test_completed_status_metadata_is_reported_inactive_even_with_live_pid(tmp_path):
    lock_path = tmp_path / "dehps-heavy-job.lock"
    metadata_path = metadata_path_for(lock_path)
    metadata_path.write_text(
        json.dumps(
            {
                "owner": "finished-job",
                "pid": os.getpid(),
                "started_at": "2026-06-18T00:00:00Z",
                "heartbeat_at": "2026-06-18T00:00:01Z",
                "status": "completed",
                "command": ["done"],
                "context": {},
            }
        ),
        encoding="utf-8",
    )

    owner_status = describe_heavy_job_owner(lock_path=lock_path)

    assert owner_status.active is False
    assert owner_status.pid_active is True
    assert owner_status.reason == "status_completed"


def test_padded_terminal_status_metadata_is_reported_inactive(tmp_path):
    lock_path = tmp_path / "dehps-heavy-job.lock"
    metadata_path = metadata_path_for(lock_path)
    metadata_path.write_text(
        json.dumps(
            {
                "owner": "finished-job",
                "pid": os.getpid(),
                "started_at": "2026-06-18T00:00:00Z",
                "heartbeat_at": "2026-06-18T00:00:01Z",
                "status": " Completed ",
                "command": ["done"],
                "context": {},
            }
        ),
        encoding="utf-8",
    )

    owner_status = describe_heavy_job_owner(lock_path=lock_path)

    assert owner_status.active is False
    assert owner_status.pid_active is True
    assert owner_status.reason == "status_completed"


def test_interrupted_status_metadata_is_reported_inactive_even_with_live_pid(tmp_path):
    lock_path = tmp_path / "dehps-heavy-job.lock"
    metadata_path = metadata_path_for(lock_path)
    metadata_path.write_text(
        json.dumps(
            {
                "owner": "interrupted-job",
                "pid": os.getpid(),
                "started_at": "2026-06-18T00:00:00Z",
                "heartbeat_at": "2026-06-18T00:00:01Z",
                "status": "interrupted",
                "command": ["stopped"],
                "context": {},
            }
        ),
        encoding="utf-8",
    )

    owner_status = describe_heavy_job_owner(lock_path=lock_path)

    assert owner_status.active is False
    assert owner_status.pid_active is True
    assert owner_status.reason == "status_interrupted"
