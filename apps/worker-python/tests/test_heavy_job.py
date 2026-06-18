from __future__ import annotations

import json
import os
import time

import pytest

from dehps.runtime.heavy_job import (
    HeavyJobLockTimeout,
    apply_cpu_thread_env_defaults,
    cpu_thread_env_overrides,
    describe_heavy_job_owner,
    heavy_job_lock,
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
