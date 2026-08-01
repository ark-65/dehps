from __future__ import annotations

import fcntl
import json
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.prediction.v2.contracts import seal_artifact, verify_artifact
from dehps.prediction.v2.reports import (
    render_post_draw_markdown,
    render_pre_draw_markdown,
)

LEDGER_PROTOCOL = "prediction-v2-shadow-notification-ledger.v1"


class PredictionV2NotificationError(RuntimeError):
    pass


def build_notification_envelope(
    *,
    report: Mapping[str, Any],
    replay_artifact: Mapping[str, Any],
    report_kind: str,
) -> dict[str, Any]:
    if report_kind == "pre_draw":
        report_value = verify_artifact(report, domain="dehps.prediction-v2.pre-draw-report.v1")
        issue = str(report_value["target_issue"])
        body = render_pre_draw_markdown(report_value)
        subject = f"[DEHPS][Shadow·零模型] 双色球 {issue} Top100"
    elif report_kind == "post_draw":
        report_value = verify_artifact(report, domain="dehps.prediction-v2.post-draw-report.v1")
        issue = str(report_value["issue"])
        body = render_post_draw_markdown(report_value)
        subject = f"[DEHPS][Shadow·零模型] 双色球 {issue} 开奖后报告"
    else:
        raise PredictionV2NotificationError("unsupported notification report kind")
    replay = verify_artifact(
        replay_artifact,
        domain="dehps.prediction-v2.replay-artifact.v1",
    )
    expected_kind = "PRE_DRAW" if report_kind == "pre_draw" else "POST_DRAW"
    if replay.get("replay_kind") != expected_kind:
        raise PredictionV2NotificationError("replay kind does not match notification report")
    if replay.get("status") != "REPLAY_VERIFIED":
        raise PredictionV2NotificationError("notification requires replay verification")
    if report_value["artifact_digest"] not in replay.get("parent_digests", []):
        raise PredictionV2NotificationError("replay is not bound to the report")
    return seal_artifact(
        {
            "schema_version": "dehps-prediction-v2-notification-envelope.v1",
            "artifact_type": "PredictionV2NotificationEnvelope.v1",
            "channel": "EMAIL",
            "report_kind": report_kind,
            "issue": issue,
            "subject": subject,
            "body_markdown": body,
            "report_artifact_digest": report_value["artifact_digest"],
            "replay_artifact_digest": replay["artifact_digest"],
            "route": "BASELINE_ONLY",
            "shadow_only": True,
            "historical_evidence": "NOT_RUN",
            "predictive_claim": "NONE",
            "promotion_gate_opened": False,
            "parent_digests": [report_value["artifact_digest"], replay["artifact_digest"]],
        },
        domain="dehps.prediction-v2.notification-envelope.v1",
    )


class PredictionV2NotificationLedger:
    def __init__(
        self,
        path: Path,
        *,
        now_factory: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self.now_factory = now_factory

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def deliver(
        self,
        envelope: Mapping[str, Any],
        *,
        sender: Callable[[str, str], str | None],
    ) -> dict[str, Any]:
        value = verify_artifact(
            envelope,
            domain="dehps.prediction-v2.notification-envelope.v1",
        )
        key = str(value["artifact_digest"])
        with self.exclusive():
            state = self._load()
            existing = state["deliveries"].get(key)
            if existing is not None:
                if existing.get("status") == "sent":
                    return dict(existing)
                raise PredictionV2NotificationError(
                    f"delivery {key} is {existing.get('status')}; manual review required"
                )
            entry = {
                "status": "sending",
                "issue": value["issue"],
                "report_kind": value["report_kind"],
                "envelope_digest": key,
                "started_at": self._timestamp(),
                "completed_at": None,
                "message_id": None,
            }
            state["deliveries"][key] = entry
            self._write(state)
            try:
                message_id = sender(str(value["subject"]), str(value["body_markdown"]))
            except Exception:
                entry["status"] = "uncertain"
                entry["completed_at"] = self._timestamp()
                self._write(state)
                raise
            entry["status"] = "sent"
            entry["completed_at"] = self._timestamp()
            entry["message_id"] = message_id
            self._write(state)
            return dict(entry)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "protocol": LEDGER_PROTOCOL,
                "schema_version": "dehps-prediction-v2-notification-delivery-ledger.v1",
                "artifact_type": "PredictionV2NotificationDeliveryLedger.v1",
                "historical_evidence": "NOT_RUN",
                "promotion_gate_opened": False,
                "deliveries": {},
            }
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PredictionV2NotificationError("notification ledger is unreadable") from exc
        if (
            not isinstance(value, dict)
            or value.get("protocol") != LEDGER_PROTOCOL
            or value.get("artifact_type") != "PredictionV2NotificationDeliveryLedger.v1"
            or not isinstance(value.get("deliveries"), dict)
            or any(
                not isinstance(entry, dict)
                or entry.get("status") not in {"sending", "sent", "uncertain"}
                for entry in value["deliveries"].values()
            )
        ):
            raise PredictionV2NotificationError("notification ledger schema is invalid")
        return value

    def _write(self, value: Mapping[str, Any]) -> None:
        atomic_write_text(
            self.path,
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )

    def _timestamp(self) -> str:
        return self.now_factory().astimezone(timezone.utc).isoformat()
