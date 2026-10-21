"""Read-only M4 progress projection and one-per-week notification consumer.

This consumer never dispatches research, changes a scientific decision, or uses
the retired training supervisor as a source. A missing or stale projection is
reported as such instead of being presented as a fresh training round.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterator
from zoneinfo import ZoneInfo

from dehps.notifications.mail import QqMailConfig, QqMailService


ROOT = Path(__file__).resolve().parents[4]
STATUS_PATH = ROOT / "runtime/logs/m4-information-theory-status.json"
SUPERVISOR_PATH = ROOT / "runtime/logs/research-evidence-supervisor-state.json"
LEDGER_PATH = ROOT / "runtime/notifications/research-progress-mail.json"
REPORT_DIR = ROOT / "runtime/research-progress-mail/reports"
SHANGHAI = ZoneInfo("Asia/Shanghai")
SOURCE_MAX_AGE = timedelta(hours=48)
PROTOCOL = "dehps-research-progress-mail.v1"


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _write_atomic(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        os.fchmod(handle.fileno(), 0o600)
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def _read(path: Path) -> tuple[dict[str, Any] | None, str | None, str]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("not an object")
        return value, _digest(raw), "available"
    except (OSError, ValueError, json.JSONDecodeError):
        return None, None, "unavailable"


def _period(now: datetime) -> str:
    year, week, _ = now.astimezone(SHANGHAI).isocalendar()
    return f"{year}-W{week:02d}"


@dataclass(frozen=True)
class ProgressReport:
    period: str
    subject: str
    text: str
    source_status: str
    status_sha256: str | None
    supervisor_sha256: str | None

    def artifact(self) -> dict[str, Any]:
        return {
            "protocol": PROTOCOL,
            "period": self.period,
            "subject": self.subject,
            "text": self.text,
            "source_status": self.source_status,
            "status_sha256": self.status_sha256,
            "supervisor_sha256": self.supervisor_sha256,
        }


def render_report(
    *, now: datetime, status_path: Path = STATUS_PATH, supervisor_path: Path = SUPERVISOR_PATH
) -> ProgressReport:
    period = _period(now)
    status, status_hash, status_read = _read(status_path)
    supervisor, supervisor_hash, supervisor_read = _read(supervisor_path)
    source_status = "UNAVAILABLE"
    heartbeat: datetime | None = None
    if status is not None and supervisor is not None:
        try:
            if status.get("schema_version") != "dehps-m4-information-theory-status.v1":
                raise ValueError("status schema")
            if supervisor.get("schema_version") != "dehps-research-evidence-supervisor-state.v1":
                raise ValueError("supervisor schema")
            if not all(
                status.get(key) and status.get(key) == supervisor.get(key)
                for key in ("manifest_digest", "snapshot_digest")
            ):
                raise ValueError("source identity mismatch")
            heartbeat = datetime.fromisoformat(str(supervisor["heartbeat_at"]).replace("Z", "+00:00"))
            if heartbeat.tzinfo is None or heartbeat > now.astimezone(UTC) + timedelta(minutes=5):
                raise ValueError("invalid heartbeat")
            source_status = "CURRENT" if now.astimezone(UTC) - heartbeat <= SOURCE_MAX_AGE else "STALE"
        except (KeyError, TypeError, ValueError):
            source_status = "UNAVAILABLE"

    lines = [
        f"DEHPS 研究进度｜{period}",
        f"状态来源：{source_status}",
    ]
    if heartbeat is not None and source_status != "UNAVAILABLE":
        lines.append(f"最近主线执行：{heartbeat.astimezone(SHANGHAI):%Y-%m-%d %H:%M}（北京时间）")
    if source_status == "UNAVAILABLE":
        lines.extend(
            [
                "本期无法核实研究进度；不推断训练轮次或研究结论。",
                f"研究状态文件：{status_read}；监督器状态文件：{supervisor_read}。",
            ]
        )
    else:
        assert status is not None and supervisor is not None
        if source_status == "STALE":
            lines.append("状态已超过 48 小时；以下为最后一次可核对的快照，不代表当前训练仍在运行。")
        lines.extend(
            [
                f"研究目标：{status.get('goal', 'UNKNOWN')}",
                f"阶段/状态：{status.get('current_phase', 'UNKNOWN')} / {status.get('current_state', 'UNKNOWN')}",
                f"旧训练主线：{status.get('old_training_mainline', 'UNKNOWN')}",
            ]
        )
        progress = status.get("progress") or {}
        if isinstance(progress, dict):
            lines.append(
                "进度投影：工程 {engineering}%；证据 {evidence}%。这两个值不是预测效果。".format(
                    engineering=progress.get("engineering_percent", "UNKNOWN"),
                    evidence=progress.get("evidence_percent", "UNKNOWN"),
                )
            )
        historical = progress.get("historical_walk_forward") if isinstance(progress, dict) else None
        if isinstance(historical, dict):
            lines.append(
                "历史逐期评估投影：{completed}/{total}。".format(
                    completed=historical.get("completed", "UNKNOWN"),
                    total=historical.get("total") if historical.get("total") is not None else "未定",
                )
            )
        if status.get("current_state") == "DEPENDENCY_WAIT" and not status.get("next_ready_task"):
            lines.append("当前无可执行的下一训练任务；快照未提供本周新增训练轮次证据。")
        else:
            lines.append("训练是否完成须以主线执行、注册产物和回放记录为准。")
        blockers = status.get("blocked_by") or []
        if isinstance(blockers, list) and blockers:
            lines.append("等待依赖：")
            lines.extend(
                f"- {item.get('target_key', 'UNKNOWN')}（需 {item.get('required_status', 'UNKNOWN')}）"
                for item in blockers if isinstance(item, dict)
            )
        lines.extend(
            [
                f"最近任务：{supervisor.get('task_key', 'UNKNOWN')}",
                f"执行标识：{supervisor.get('execution_id', 'UNKNOWN')}",
                f"主线快照：{status.get('snapshot_digest', 'UNKNOWN')}",
                "本邮件只报告研究状态，不构成模型晋级或投注建议。",
            ]
        )
    return ProgressReport(
        period=period,
        subject=f"[DEHPS][研究进度] {period} M4",
        text="\n".join(lines) + "\n",
        source_status=source_status,
        status_sha256=status_hash,
        supervisor_sha256=supervisor_hash,
    )


@contextmanager
def _exclusive(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.with_suffix(path.suffix + ".lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"protocol": PROTOCOL, "periods": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("protocol") != PROTOCOL or not isinstance(value.get("periods"), dict):
        raise ValueError("research progress ledger invalid")
    return value


def deliver_report(
    report: ProgressReport,
    *,
    config: QqMailConfig,
    ledger_path: Path = LEDGER_PATH,
    report_dir: Path = REPORT_DIR,
    mail_service: QqMailService | None = None,
    now: datetime | None = None,
) -> dict[str, str]:
    if config.recipient is None:
        raise ValueError("research progress recipient must be explicitly configured")
    at = (now or datetime.now(UTC)).astimezone(UTC).isoformat()
    recipient_digest = _digest(config.destination.strip().lower().encode())
    artifact = report.artifact()
    artifact_bytes = _canonical(artifact)
    artifact_digest = _digest(artifact_bytes)
    with _exclusive(ledger_path):
        ledger = _ledger(ledger_path)
        old = ledger["periods"].get(report.period)
        if old is not None:
            if old.get("recipient_digest") != recipient_digest:
                raise ValueError("research progress recipient changed for period")
            if old.get("status") == "smtp_returned":
                return {"status": "ALREADY_SENT", "period": report.period}
            raise ValueError("research progress delivery requires manual reconciliation")
        artifact_path = report_dir / f"{report.period}-{artifact_digest}.json"
        if artifact_path.exists() and _digest(artifact_path.read_bytes()) != artifact_digest:
            raise ValueError("research progress artifact differs")
        if not artifact_path.exists():
            _write_atomic(artifact_path, artifact_bytes)
        entry = {
            "status": "sending",
            "recipient_digest": recipient_digest,
            "artifact_digest": artifact_digest,
            "artifact_path": str(artifact_path),
            "started_at": at,
            "message_id": None,
        }
        ledger["periods"][report.period] = entry
        _write_atomic(ledger_path, _canonical(ledger))
        try:
            receipt = (mail_service or QqMailService(config)).send(
                subject=report.subject, text=report.text, recipient=config.destination
            )
        except Exception:
            entry["status"] = "uncertain"
            entry["completed_at"] = datetime.now(UTC).isoformat()
            _write_atomic(ledger_path, _canonical(ledger))
            raise
        entry["status"] = "smtp_returned"
        entry["completed_at"] = datetime.now(UTC).isoformat()
        entry["message_id"] = receipt.message_id
        _write_atomic(ledger_path, _canonical(ledger))
        return {"status": "SMTP_RETURNED", "period": report.period, "message_id": receipt.message_id}
