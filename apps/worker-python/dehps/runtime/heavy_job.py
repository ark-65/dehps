from __future__ import annotations

import errno
import json
import os
import socket
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, MutableMapping, Sequence

try:
    import fcntl
except ImportError:  # pragma: no cover - the worker currently runs on Linux.
    fcntl = None  # type: ignore[assignment]


CPU_THREAD_ENV_VARS = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)
DEFAULT_CPU_THREAD_COUNT = 1
DEFAULT_LOCK_FILENAME = "dehps-heavy-job.lock"
INACTIVE_STATUSES = {"released", "finished", "completed", "success", "failed", "error", "cancelled"}

_HELD_LOCKS: set[Path] = set()
_HELD_LOCKS_MUTEX = threading.Lock()


def _find_root_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "docker-compose.yaml").exists():
            return parent
    return Path(__file__).resolve().parents[2]


ROOT_DIR = _find_root_dir()
DEFAULT_LOCK_PATH = ROOT_DIR / "runtime" / "logs" / DEFAULT_LOCK_FILENAME
DEFAULT_METADATA_PATH = DEFAULT_LOCK_PATH.with_name(f"{DEFAULT_LOCK_PATH.name}.json")


class HeavyJobLockError(RuntimeError):
    """Base error for heavy-job lock failures."""


class HeavyJobLockTimeout(HeavyJobLockError):
    """Raised when the heavy-job lock cannot be acquired before the deadline."""


@dataclass(frozen=True)
class HeavyJobOwnerStatus:
    metadata_path: Path
    metadata: dict[str, Any] | None
    active: bool
    pid_active: bool | None
    reason: str
    error: str | None = None


def metadata_path_for(lock_path: str | os.PathLike[str] | None = None) -> Path:
    path = Path(lock_path) if lock_path is not None else DEFAULT_LOCK_PATH
    return path.with_name(f"{path.name}.json")


def cpu_thread_env_overrides(
    thread_count: int | str = DEFAULT_CPU_THREAD_COUNT,
    *,
    env: Mapping[str, str] | None = None,
    override: bool = False,
) -> dict[str, str]:
    source = os.environ if env is None else env
    value = str(thread_count)
    return {
        name: value
        for name in CPU_THREAD_ENV_VARS
        if override or name not in source
    }


def apply_cpu_thread_env_defaults(
    thread_count: int | str = DEFAULT_CPU_THREAD_COUNT,
    *,
    env: MutableMapping[str, str] | None = None,
    override: bool = False,
) -> dict[str, str]:
    target = os.environ if env is None else env
    overrides = cpu_thread_env_overrides(thread_count, env=target, override=override)
    target.update(overrides)
    return overrides


def read_owner_metadata(metadata_path: str | os.PathLike[str] | None = None) -> dict[str, Any] | None:
    path = Path(metadata_path) if metadata_path is not None else DEFAULT_METADATA_PATH
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        raise HeavyJobLockError(f"Invalid heavy-job metadata JSON at {path}") from exc
    except OSError as exc:
        raise HeavyJobLockError(f"Unable to read heavy-job metadata at {path}: {exc}") from exc


def describe_heavy_job_owner(
    *,
    lock_path: str | os.PathLike[str] | None = None,
    metadata_path: str | os.PathLike[str] | None = None,
) -> HeavyJobOwnerStatus:
    resolved_metadata_path = Path(metadata_path) if metadata_path is not None else metadata_path_for(lock_path)
    try:
        metadata = read_owner_metadata(resolved_metadata_path)
    except HeavyJobLockError as exc:
        return HeavyJobOwnerStatus(
            metadata_path=resolved_metadata_path,
            metadata=None,
            active=False,
            pid_active=None,
            reason="metadata_unreadable",
            error=str(exc),
        )
    if metadata is None:
        return HeavyJobOwnerStatus(
            metadata_path=resolved_metadata_path,
            metadata=None,
            active=False,
            pid_active=None,
            reason="metadata_missing",
        )

    status = str(metadata.get("status", "")).lower()
    pid_active = is_pid_active(metadata.get("pid"))
    if status in INACTIVE_STATUSES:
        return HeavyJobOwnerStatus(
            metadata_path=resolved_metadata_path,
            metadata=metadata,
            active=False,
            pid_active=pid_active,
            reason=f"status_{status}",
        )

    return HeavyJobOwnerStatus(
        metadata_path=resolved_metadata_path,
        metadata=metadata,
        active=pid_active is True,
        pid_active=pid_active,
        reason=_pid_reason(pid_active),
    )


def is_pid_active(pid: Any) -> bool | None:
    try:
        parsed_pid = int(pid)
    except (TypeError, ValueError):
        return None
    if parsed_pid <= 0:
        return False
    try:
        os.kill(parsed_pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False
        if exc.errno == errno.EPERM:
            return True
        return None
    return True


def _pid_reason(pid_active: bool | None) -> str:
    if pid_active is True:
        return "pid_running"
    if pid_active is False:
        return "pid_not_running"
    return "pid_unknown"


class HeavyJobLock:
    def __init__(
        self,
        *,
        owner: str = "dehps-heavy-job",
        lock_path: str | os.PathLike[str] | None = None,
        metadata_path: str | os.PathLike[str] | None = None,
        timeout_seconds: float | None = 0,
        blocking: bool = True,
        status: str = "running",
        command: str | Sequence[str] | None = None,
        context: Mapping[str, Any] | None = None,
        poll_interval_seconds: float = 0.1,
        cleanup_metadata_on_release: bool = True,
        auto_heartbeat_interval_seconds: float | None = 30.0,
    ) -> None:
        self.owner = owner
        self.lock_path = Path(lock_path) if lock_path is not None else DEFAULT_LOCK_PATH
        self.metadata_path = Path(metadata_path) if metadata_path is not None else metadata_path_for(self.lock_path)
        self.timeout_seconds = timeout_seconds
        self.blocking = blocking
        self.status = status
        self.command = list(sys.argv) if command is None else command
        self.context = dict(context or {})
        self.poll_interval_seconds = max(0.01, poll_interval_seconds)
        self.cleanup_metadata_on_release = cleanup_metadata_on_release
        self.auto_heartbeat_interval_seconds = auto_heartbeat_interval_seconds
        self.pid = os.getpid()
        self.hostname = socket.gethostname()
        self.started_at: str | None = None
        self.metadata: dict[str, Any] | None = None
        self._lock_file: Any | None = None
        self._locked = False
        self._registered_path: Path | None = None
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

    def __enter__(self) -> HeavyJobLock:
        return self.acquire()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        release_status = "failed" if exc_type is not None else "released"
        self.release(status=release_status)
        return False

    def acquire(self) -> HeavyJobLock:
        if fcntl is None:
            raise HeavyJobLockError("Heavy-job locking requires fcntl on this platform")
        if self._locked:
            return self

        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = self._deadline()
        last_owner = None

        while True:
            if self._register_lock_path():
                try:
                    self._lock_file = self.lock_path.open("a+", encoding="utf-8")
                    fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    self._close_and_unregister()
                    last_owner = describe_heavy_job_owner(
                        lock_path=self.lock_path,
                        metadata_path=self.metadata_path,
                    )
                except OSError as exc:
                    self._close_and_unregister()
                    if exc.errno not in (errno.EACCES, errno.EAGAIN):
                        raise
                    last_owner = describe_heavy_job_owner(
                        lock_path=self.lock_path,
                        metadata_path=self.metadata_path,
                    )
                else:
                    self._locked = True
                    self.started_at = _utc_now_iso()
                    self.metadata = self._metadata(
                        status=self.status,
                        heartbeat_at=self.started_at,
                    )
                    _atomic_write_json(self.metadata_path, self.metadata)
                    self._start_auto_heartbeat()
                    return self
            else:
                last_owner = describe_heavy_job_owner(
                    lock_path=self.lock_path,
                    metadata_path=self.metadata_path,
                )

            if not self.blocking or _deadline_expired(deadline):
                raise HeavyJobLockTimeout(self._timeout_message(last_owner))
            _sleep_until_retry(deadline, self.poll_interval_seconds)

    def heartbeat(
        self,
        *,
        status: str | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._locked:
            raise HeavyJobLockError("Cannot heartbeat a heavy-job lock that is not held")

        current = read_owner_metadata(self.metadata_path)
        if current is not None and not self._owns_metadata(current):
            raise HeavyJobLockError(
                f"Refusing to overwrite heavy-job metadata owned by pid={current.get('pid')}"
            )

        metadata = dict(self.metadata or self._metadata(status=self.status))
        metadata["heartbeat_at"] = _utc_now_iso()
        if status is not None:
            metadata["status"] = status
        if context is not None:
            merged_context = dict(metadata.get("context") or {})
            merged_context.update(dict(context))
            metadata["context"] = _json_safe(merged_context)

        self.metadata = metadata
        _atomic_write_json(self.metadata_path, metadata)
        return metadata

    def release(self, *, status: str = "released") -> None:
        if not self._locked:
            return
        try:
            self._stop_auto_heartbeat()
            if self.cleanup_metadata_on_release:
                self._unlink_owned_metadata()
            else:
                finished_at = _utc_now_iso()
                metadata = dict(self.metadata or self._metadata(status=status))
                metadata.update(
                    {
                        "status": status,
                        "heartbeat_at": finished_at,
                        "finished_at": finished_at,
                    }
                )
                self.metadata = metadata
                _atomic_write_json(self.metadata_path, metadata)
        finally:
            if self._lock_file is not None:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
            self._close_and_unregister()
            self._locked = False

    def _start_auto_heartbeat(self) -> None:
        interval = self.auto_heartbeat_interval_seconds
        if interval is None or interval <= 0:
            return
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._auto_heartbeat_loop,
            args=(max(0.01, float(interval)),),
            daemon=True,
            name=f"dehps-heavy-job-heartbeat-{self.owner}",
        )
        self._heartbeat_thread.start()

    def _stop_auto_heartbeat(self) -> None:
        if self._heartbeat_thread is None:
            return
        self._heartbeat_stop.set()
        self._heartbeat_thread.join(timeout=2.0)
        self._heartbeat_thread = None

    def _auto_heartbeat_loop(self, interval_seconds: float) -> None:
        while not self._heartbeat_stop.wait(interval_seconds):
            if not self._locked:
                return
            try:
                self.heartbeat()
            except HeavyJobLockError:
                return

    def _metadata(self, *, status: str, heartbeat_at: str | None = None) -> dict[str, Any]:
        heartbeat = heartbeat_at or _utc_now_iso()
        started = self.started_at or heartbeat
        return {
            "owner": self.owner,
            "pid": self.pid,
            "hostname": self.hostname,
            "started_at": started,
            "heartbeat_at": heartbeat,
            "status": status,
            "command": _json_safe(self.command),
            "context": _json_safe(self.context),
            "lock_path": str(self.lock_path),
        }

    def _deadline(self) -> float | None:
        if not self.blocking:
            return time.monotonic()
        if self.timeout_seconds is None:
            return None
        return time.monotonic() + max(0.0, self.timeout_seconds)

    def _register_lock_path(self) -> bool:
        resolved_path = self.lock_path.resolve(strict=False)
        with _HELD_LOCKS_MUTEX:
            if resolved_path in _HELD_LOCKS:
                return False
            _HELD_LOCKS.add(resolved_path)
        self._registered_path = resolved_path
        return True

    def _unregister_lock_path(self) -> None:
        if self._registered_path is None:
            return
        with _HELD_LOCKS_MUTEX:
            _HELD_LOCKS.discard(self._registered_path)
        self._registered_path = None

    def _close_and_unregister(self) -> None:
        if self._lock_file is not None:
            self._lock_file.close()
            self._lock_file = None
        self._unregister_lock_path()

    def _owns_metadata(self, metadata: Mapping[str, Any]) -> bool:
        return (
            metadata.get("pid") == self.pid
            and metadata.get("owner") == self.owner
            and metadata.get("started_at") == self.started_at
        )

    def _unlink_owned_metadata(self) -> None:
        current = read_owner_metadata(self.metadata_path)
        if current is None:
            return
        if not self._owns_metadata(current):
            raise HeavyJobLockError(
                f"Refusing to remove heavy-job metadata owned by pid={current.get('pid')}"
            )
        self.metadata_path.unlink(missing_ok=True)

    def _timeout_message(self, owner_status: HeavyJobOwnerStatus | None) -> str:
        if owner_status and owner_status.metadata:
            metadata = owner_status.metadata
            return (
                f"Heavy-job lock is already held at {self.lock_path} "
                f"by owner={metadata.get('owner')!r} pid={metadata.get('pid')!r} "
                f"status={metadata.get('status')!r} heartbeat_at={metadata.get('heartbeat_at')!r} "
                f"active={owner_status.active}"
            )
        return f"Heavy-job lock is already held at {self.lock_path}"


def acquire_heavy_job_lock(**kwargs: Any) -> HeavyJobLock:
    return HeavyJobLock(**kwargs).acquire()


@contextmanager
def heavy_job_lock(**kwargs: Any) -> Iterator[HeavyJobLock]:
    lock = acquire_heavy_job_lock(**kwargs)
    try:
        yield lock
    except BaseException:
        lock.release(status="failed")
        raise
    else:
        lock.release()


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
            json.dump(_json_safe(payload), temp_file, indent=2, sort_keys=True)
            temp_file.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    return repr(value)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _deadline_expired(deadline: float | None) -> bool:
    return deadline is not None and time.monotonic() >= deadline


def _sleep_until_retry(deadline: float | None, poll_interval_seconds: float) -> None:
    if deadline is None:
        time.sleep(poll_interval_seconds)
        return
    remaining = deadline - time.monotonic()
    if remaining > 0:
        time.sleep(min(poll_interval_seconds, remaining))
