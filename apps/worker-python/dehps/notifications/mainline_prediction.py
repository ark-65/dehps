from __future__ import annotations

import fcntl
import hashlib
import html
import json
import math
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Callable, Iterator
from zoneinfo import ZoneInfo

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.notifications.mail import MailDeliveryReceipt, QqMailConfig, QqMailService


MAINLINE_KEY = "static_100"
TOP_LIMIT = 100
BEIJING_TIMEZONE = ZoneInfo("Asia/Shanghai")
DRAW_WEEKDAYS = frozenset({1, 3, 6})  # Tuesday, Thursday, Sunday
SCHEDULED_SEND_TIME = time(17, 0)
DRAW_TIME = time(21, 15)
DELIVERY_LEDGER_PROTOCOL = "mainline-prediction-mail-ledger.v1"
DEFAULT_DELIVERY_LEDGER_PATH = (
    ROOT_DIR / "runtime" / "notifications" / "mainline_prediction_mail.json"
)


class MainlinePredictionMailError(RuntimeError):
    """Raised when prediction mail compilation or delivery must fail closed."""


class PredictionDeliveryStateError(MainlinePredictionMailError):
    """Raised when the delivery ledger is malformed or delivery is ambiguous."""


@dataclass(frozen=True)
class MainlinePredictionEmail:
    delivery_key: str
    issue: str
    as_of_issue: str
    prediction_run_key: str
    prediction_fingerprint: str
    subject: str
    text: str
    html: str
    candidate_count: int


@dataclass(frozen=True)
class MainlinePredictionDeliveryResult:
    status: str
    delivery_key: str
    issue: str
    prediction_run_key: str
    candidate_count: int
    message_id: str | None


def require_pre_draw_delivery_window(now: datetime) -> datetime:
    local = now.astimezone(BEIJING_TIMEZONE)
    if local.weekday() not in DRAW_WEEKDAYS:
        raise MainlinePredictionMailError(
            "mainline prediction mail may send only on Tuesday, Thursday, or Sunday"
        )
    local_time = local.timetz().replace(tzinfo=None)
    if local_time < SCHEDULED_SEND_TIME:
        raise MainlinePredictionMailError(
            "mainline prediction mail window has not opened at 17:00 Asia/Shanghai"
        )
    if local_time >= DRAW_TIME:
        raise MainlinePredictionMailError(
            "mainline prediction mail window closed at the 21:15 draw boundary"
        )
    return local


def compile_mainline_prediction_email(
    payload: dict[str, Any],
    *,
    recipient: str,
) -> MainlinePredictionEmail:
    issue = str(payload.get("issue") or "").strip()
    as_of_issue = str(payload.get("as_of_issue") or "").strip()
    if not issue or not as_of_issue or issue <= as_of_issue:
        raise MainlinePredictionMailError(
            "latest prediction must identify a future issue after its as-of issue"
        )

    matching_lines = [
        line for line in payload.get("lines", []) if line.get("line_key") == MAINLINE_KEY
    ]
    if len(matching_lines) != 1:
        raise MainlinePredictionMailError(
            "latest prediction must contain exactly one static_100 mainline"
        )
    line = matching_lines[0]
    if line.get("status") != "pending":
        raise MainlinePredictionMailError(
            "static_100 mainline must be pending before draw delivery"
        )

    candidates = list(line.get("top_candidates") or [])
    expected_ranks = list(range(1, TOP_LIMIT + 1))
    actual_ranks = [int(candidate.get("rank", 0)) for candidate in candidates]
    if actual_ranks != expected_ranks:
        raise MainlinePredictionMailError(
            "static_100 mainline must contain contiguous ranks 1 through 100"
        )
    combinations: set[tuple[int, ...]] = set()
    for candidate in candidates:
        numbers = tuple(int(value) for value in candidate.get("red_numbers") or ())
        score = float(candidate.get("score", float("nan")))
        if (
            len(numbers) != 6
            or tuple(sorted(numbers)) != numbers
            or len(set(numbers)) != 6
            or numbers[0] < 1
            or numbers[-1] > 33
            or not math.isfinite(score)
        ):
            raise MainlinePredictionMailError(
                f"static_100 rank {candidate['rank']} has invalid red numbers"
            )
        if numbers in combinations:
            raise MainlinePredictionMailError(
                "static_100 Top 100 must not contain duplicate combinations"
            )
        combinations.add(numbers)

    prediction_run_key = str(line.get("prediction_run_key") or "").strip()
    prediction_fingerprint = str(line.get("prediction_fingerprint") or "").strip()
    if not prediction_run_key or not prediction_fingerprint:
        raise MainlinePredictionMailError(
            "static_100 mainline must carry prediction run identity and fingerprint"
        )
    delivery_key = _delivery_key(
        issue=issue,
        prediction_run_key=prediction_run_key,
        prediction_fingerprint=prediction_fingerprint,
        recipient=recipient,
    )
    subject = f"[DEHPS][实验性] 双色球 {issue} 主线预测 Top 100"
    metadata_lines = [
        f"目标期次：{issue}",
        f"历史截止：{as_of_issue}",
        f"生成时间：{payload.get('generated_at')}",
        f"主线：{MAINLINE_KEY}",
        f"预测运行：{prediction_run_key}",
        f"模型版本：{line.get('model_version')}",
        f"参数版本：{line.get('parameter_version')}",
        f"排名契约：{line.get('ranking_contract')}",
        f"候选全集数量：{line.get('candidate_count')}",
    ]
    warning_lines = [
        "风险说明：这是训练中的实验性决策支持输出，不保证中奖，也不代表模型已达到预测目标。",
        "历史表现不能证明未来结果；请理性购彩、量力而行，禁止未成年人购彩。",
    ]
    candidate_lines = [
        _render_text_candidate(candidate)
        for candidate in candidates
    ]
    text_body = "\n".join(
        [
            *metadata_lines,
            "",
            *warning_lines,
            "",
            "主线 Top 100（红球）：",
            *candidate_lines,
        ]
    )
    html_body = _render_html(
        subject=subject,
        metadata_lines=metadata_lines,
        warning_lines=warning_lines,
        candidates=candidates,
    )
    return MainlinePredictionEmail(
        delivery_key=delivery_key,
        issue=issue,
        as_of_issue=as_of_issue,
        prediction_run_key=prediction_run_key,
        prediction_fingerprint=prediction_fingerprint,
        subject=subject,
        text=text_body,
        html=html_body,
        candidate_count=len(candidates),
    )


class PredictionMailDeliveryLedger:
    def __init__(
        self,
        path: Path = DEFAULT_DELIVERY_LEDGER_PATH,
        *,
        now_factory: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self._now_factory = now_factory

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def status(self, delivery_key: str) -> str | None:
        entry = self._load()["deliveries"].get(delivery_key)
        return None if entry is None else str(entry.get("status"))

    def begin(self, email: MainlinePredictionEmail) -> None:
        state = self._load()
        existing = state["deliveries"].get(email.delivery_key)
        if existing is not None:
            status = str(existing.get("status"))
            if status == "sent":
                return
            raise PredictionDeliveryStateError(
                f"delivery {email.delivery_key} is {status}; manual review is required"
            )
        state["deliveries"][email.delivery_key] = {
            "status": "sending",
            "issue": email.issue,
            "prediction_run_key": email.prediction_run_key,
            "candidate_count": email.candidate_count,
            "started_at": self._timestamp(),
            "completed_at": None,
            "message_id": None,
        }
        self._write(state)

    def mark_sent(
        self,
        delivery_key: str,
        receipt: MailDeliveryReceipt,
    ) -> None:
        self._transition(
            delivery_key,
            expected="sending",
            status="sent",
            message_id=receipt.message_id,
        )

    def mark_uncertain(self, delivery_key: str) -> None:
        self._transition(
            delivery_key,
            expected="sending",
            status="uncertain",
            message_id=None,
        )

    def _transition(
        self,
        delivery_key: str,
        *,
        expected: str,
        status: str,
        message_id: str | None,
    ) -> None:
        state = self._load()
        entry = state["deliveries"].get(delivery_key)
        if entry is None or entry.get("status") != expected:
            found = None if entry is None else entry.get("status")
            raise PredictionDeliveryStateError(
                f"delivery {delivery_key} expected {expected}, found {found}"
            )
        entry["status"] = status
        entry["completed_at"] = self._timestamp()
        entry["message_id"] = message_id
        self._write(state)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"protocol": DELIVERY_LEDGER_PROTOCOL, "deliveries": {}}
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise PredictionDeliveryStateError("prediction mail ledger is unreadable") from None
        if (
            not isinstance(state, dict)
            or state.get("protocol") != DELIVERY_LEDGER_PROTOCOL
            or not isinstance(state.get("deliveries"), dict)
        ):
            raise PredictionDeliveryStateError("prediction mail ledger schema is invalid")
        allowed_statuses = {"sending", "sent", "uncertain"}
        if any(
            not isinstance(entry, dict) or entry.get("status") not in allowed_statuses
            for entry in state["deliveries"].values()
        ):
            raise PredictionDeliveryStateError("prediction mail ledger state is invalid")
        return state

    def _write(self, state: dict[str, Any]) -> None:
        atomic_write_text(
            self.path,
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )

    def _timestamp(self) -> str:
        return self._now_factory().astimezone(timezone.utc).isoformat()


class MainlinePredictionNotificationService:
    def __init__(
        self,
        config: QqMailConfig,
        *,
        mail_service: QqMailService | None = None,
        ledger: PredictionMailDeliveryLedger | None = None,
    ) -> None:
        if config.recipient is None:
            raise MainlinePredictionMailError(
                "DEHPS_QQ_MAIL_RECIPIENT is required for scheduled prediction delivery"
            )
        self.config = config
        self.mail_service = mail_service or QqMailService(config)
        self.ledger = ledger or PredictionMailDeliveryLedger()

    def preview(self, payload: dict[str, Any]) -> MainlinePredictionEmail:
        return compile_mainline_prediction_email(
            payload,
            recipient=self.config.destination,
        )

    def deliver(
        self,
        payload: dict[str, Any],
        *,
        now: datetime,
    ) -> MainlinePredictionDeliveryResult:
        require_pre_draw_delivery_window(now)
        email = self.preview(payload)
        with self.ledger.exclusive():
            current_status = self.ledger.status(email.delivery_key)
            if current_status == "sent":
                return MainlinePredictionDeliveryResult(
                    status="already_sent",
                    delivery_key=email.delivery_key,
                    issue=email.issue,
                    prediction_run_key=email.prediction_run_key,
                    candidate_count=email.candidate_count,
                    message_id=None,
                )
            if current_status is not None:
                raise PredictionDeliveryStateError(
                    f"delivery {email.delivery_key} is {current_status}; manual review is required"
                )
            self.ledger.begin(email)
            try:
                receipt = self.mail_service.send(
                    subject=email.subject,
                    text=email.text,
                    html=email.html,
                    recipient=self.config.destination,
                )
            except Exception:
                self.ledger.mark_uncertain(email.delivery_key)
                raise
            self.ledger.mark_sent(email.delivery_key, receipt)
        return MainlinePredictionDeliveryResult(
            status="sent",
            delivery_key=email.delivery_key,
            issue=email.issue,
            prediction_run_key=email.prediction_run_key,
            candidate_count=email.candidate_count,
            message_id=receipt.message_id,
        )


def _delivery_key(
    *,
    issue: str,
    prediction_run_key: str,
    prediction_fingerprint: str,
    recipient: str,
) -> str:
    identity = json.dumps(
        {
            "issue": issue,
            "line_key": MAINLINE_KEY,
            "prediction_run_key": prediction_run_key,
            "prediction_fingerprint": prediction_fingerprint,
            "recipient": recipient.lower(),
            "top_limit": TOP_LIMIT,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _render_text_candidate(candidate: dict[str, Any]) -> str:
    numbers = " ".join(f"{int(value):02d}" for value in candidate["red_numbers"])
    return f"{int(candidate['rank']):03d}. {numbers} | score={float(candidate['score']):.8f}"


def _render_html(
    *,
    subject: str,
    metadata_lines: list[str],
    warning_lines: list[str],
    candidates: list[dict[str, Any]],
) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{int(candidate['rank'])}</td>"
        f"<td>{html.escape(' '.join(f'{int(value):02d}' for value in candidate['red_numbers']))}</td>"
        f"<td>{float(candidate['score']):.8f}</td>"
        "</tr>"
        for candidate in candidates
    )
    metadata = "".join(f"<li>{html.escape(line)}</li>" for line in metadata_lines)
    warnings = "".join(f"<p><strong>{html.escape(line)}</strong></p>" for line in warning_lines)
    return (
        "<!doctype html><html><body>"
        f"<h1>{html.escape(subject)}</h1>"
        f"<ul>{metadata}</ul>{warnings}"
        "<h2>主线 Top 100（红球）</h2>"
        "<table border=\"1\" cellspacing=\"0\" cellpadding=\"4\">"
        "<thead><tr><th>Rank</th><th>红球</th><th>Score</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        "</body></html>"
    )
