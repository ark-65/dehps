from __future__ import annotations

import fcntl
import hashlib
import html
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterator

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.notifications.mail import MailDeliveryReceipt, QqMailConfig, QqMailService
from dehps.optimization.next_candidates import (
    DYNAMIC_KDJ_LINE_KEY,
    NEAR_DYNAMIC_KDJ_LINE_KEY,
    STATIC_100_LINE_KEY,
)
from dehps.storage.postgres_store import TOTAL_SSQ_RED_COMBINATIONS


REPORT_PROTOCOL = "post-draw-three-line-evaluation-report.v1"
REPORT_RENDERER_VERSION = "post-draw-three-line-text.v1"
DELIVERY_LEDGER_PROTOCOL = "post-draw-evaluation-report-mail-ledger.v1"
REQUIRED_LINE_KEYS = (
    STATIC_100_LINE_KEY,
    DYNAMIC_KDJ_LINE_KEY,
    NEAR_DYNAMIC_KDJ_LINE_KEY,
)
LINE_TITLES = {
    STATIC_100_LINE_KEY: "主线（static_100）",
    DYNAMIC_KDJ_LINE_KEY: "动态线（dynamic_kdj）",
    NEAR_DYNAMIC_KDJ_LINE_KEY: "近邻动态线（dynamic_kdj_near）",
}
DEFAULT_REPORT_DIR = ROOT_DIR / "data/output/post-draw-evaluation-reports"
DEFAULT_DELIVERY_LEDGER_PATH = (
    ROOT_DIR / "runtime/notifications/post_draw_evaluation_report_mail.json"
)


class PostDrawEvaluationReportError(RuntimeError):
    """Raised when a complete, leakage-safe three-line report cannot be compiled."""


class PostDrawDeliveryStateError(PostDrawEvaluationReportError):
    """Raised when delivery state is malformed or SMTP acceptance is ambiguous."""


@dataclass(frozen=True)
class PostDrawEvaluationReport:
    issue: str
    report_digest: str
    delivery_key: str
    subject: str
    text: str
    html: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class PostDrawEvaluationDeliveryResult:
    status: str
    issue: str
    report_digest: str
    delivery_key: str
    json_path: str
    text_path: str
    message_id: str | None


def load_post_draw_evaluations(
    conn: Connection,
    *,
    issue: str,
) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT e.evaluation_key, e.prediction_run_key, e.evaluation_run_key,
                   e.prediction_ranking_contract, e.line_key, e.line_label, e.line_kind,
                   e.snapshot_key, e.run_id, e.source_round_index, e.as_of_issue,
                   e.predicted_issue, e.actual_draw_date, e.actual_red_numbers,
                   e.actual_blue_number, e.exact_rank, e.hit_top_100,
                   e.hit_top_1000, e.hit_top_10000, e.red5_rank, e.red5_numbers,
                   e.hit_red5_top_100, e.hit_red5_top_1000,
                   e.hit_red5_top_10000, e.candidate_count,
                   e.snapshot_generated_at, e.status, e.summary,
                   e.prediction_metadata, e.evaluated_at,
                   p.top_n, p.candidate_count AS prediction_candidate_count,
                   p.config_hash, p.prediction_fingerprint,
                   p.ranking_contract AS run_ranking_contract,
                   p.status AS prediction_status,
                   er.status AS evaluation_run_status,
                   h.draw_date AS current_actual_draw_date,
                   h.red_numbers AS current_actual_red_numbers,
                   h.blue_number AS current_actual_blue_number,
                   (SELECT count(*)::integer
                      FROM forward_prediction_candidates c
                     WHERE c.prediction_run_key = e.prediction_run_key)
                     AS persisted_candidate_count
            FROM training_prediction_evaluations e
            JOIN forward_prediction_runs p
              ON p.prediction_run_key = e.prediction_run_key
            JOIN forward_evaluation_runs er
              ON er.evaluation_run_key = e.evaluation_run_key
            JOIN ssq_history h
              ON h.issue = e.predicted_issue
            WHERE e.predicted_issue = %s
              AND e.line_key = ANY(%s)
            ORDER BY e.line_key, e.evaluated_at
            """,
            (issue, list(REQUIRED_LINE_KEYS)),
        ).fetchall()
    return [_json_safe(dict(row)) for row in rows]


def deliver_post_draw_evaluation_report(issue: str) -> dict[str, Any]:
    """Deliver one accepted issue through the shared idempotent mail contract."""
    from dehps.prediction.v2.retirement import require_legacy_compute_allowed

    require_legacy_compute_allowed("legacy_three_line_post_draw_report")
    from dehps.db import get_connection
    from dehps.forward_checkpoint import settle_forward_checkpoint_if_available

    service = PostDrawEvaluationNotificationService(QqMailConfig.from_environment())
    with get_connection() as conn:
        rows = load_post_draw_evaluations(conn, issue=issue)
        forward_checkpoint = settle_forward_checkpoint_if_available(issue, conn=conn)
    result = service.deliver(rows)
    return {
        "status": result.status,
        "issue": result.issue,
        "report_digest": result.report_digest,
        "delivery_key": result.delivery_key,
        "json_path": result.json_path,
        "text_path": result.text_path,
        "message_id": result.message_id,
        "forward_checkpoint": forward_checkpoint,
    }


def compile_post_draw_evaluation_report(
    rows: list[dict[str, Any]],
    *,
    recipient: str,
) -> PostDrawEvaluationReport:
    from dehps.prediction.v2.retirement import require_legacy_compute_allowed

    require_legacy_compute_allowed("legacy_three_line_post_draw_report")
    lines = _validate_and_normalize_rows(rows)
    issue = str(lines[0]["predicted_issue"])
    actual_red = list(lines[0]["actual_red_numbers"])
    actual_blue = int(lines[0]["actual_blue_number"])
    actual_draw_date = str(lines[0]["actual_draw_date"])

    normalized_lines = [_report_line(line) for line in lines]
    evidence = {
        "protocol": REPORT_PROTOCOL,
        "renderer_version": REPORT_RENDERER_VERSION,
        "issue": issue,
        "actual_draw_date": actual_draw_date,
        "actual_red_numbers": actual_red,
        "actual_blue_number": actual_blue,
        "blue_scored": False,
        "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
        "lines": normalized_lines,
        "summary": _summary(normalized_lines),
        "guardrail": (
            "Forward-only red-ball evaluation. All ranks are bound to pre-draw frozen "
            "prediction runs; the blue ball is recorded but not scored."
        ),
    }
    report_digest = hashlib.sha256(_canonical_json(evidence).encode("utf-8")).hexdigest()
    payload = {**evidence, "report_digest": report_digest}
    text = render_post_draw_evaluation_report(payload)
    delivery_key = _delivery_key(issue, report_digest, recipient)
    subject = f"[DEHPS][开奖后评估] 双色球 {issue} 三线命中与排名详报"
    return PostDrawEvaluationReport(
        issue=issue,
        report_digest=report_digest,
        delivery_key=delivery_key,
        subject=subject,
        text=text,
        html=f"<!doctype html><html><body><pre>{html.escape(text)}</pre></body></html>",
        payload=payload,
    )


def write_post_draw_evaluation_artifacts(
    report: PostDrawEvaluationReport,
    output_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"post-draw-evaluation-{report.issue}-{report.report_digest}"
    json_path = output_dir / f"{stem}.json"
    text_path = output_dir / f"{stem}.txt"
    encoded = json.dumps(report.payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if json_path.exists() and json_path.read_text(encoding="utf-8") != encoded:
        raise PostDrawEvaluationReportError("digest-addressed JSON artifact content mismatch")
    if text_path.exists() and text_path.read_text(encoding="utf-8") != report.text:
        raise PostDrawEvaluationReportError("digest-addressed text artifact content mismatch")
    atomic_write_text(json_path, encoded)
    atomic_write_text(text_path, report.text)
    return json_path, text_path


def render_post_draw_evaluation_report(payload: dict[str, Any]) -> str:
    issue = payload["issue"]
    actual_red = " ".join(f"{int(value):02d}" for value in payload["actual_red_numbers"])
    actual_blue = f"{int(payload['actual_blue_number']):02d}"
    universe = int(payload["legal_sample_space"])
    summary = payload["summary"]
    sections = [
        f"DEHPS 双色球 {issue} 三线开奖后评估详报",
        "=" * 58,
        f"开奖日期：{payload['actual_draw_date']}",
        f"开奖号码：红球 {actual_red} | 蓝球 {actual_blue}",
        "评估范围：只评价 6 个红球；蓝球仅记录，不参与评分或命中统计。",
        f"合法红球组合全集：{universe:,}",
        f"证据摘要：三条线完整，泄漏检查通过，报表摘要 {payload['report_digest']}",
        f"报表渲染契约：{payload['renderer_version']}",
        "",
        "一、三线总览",
        "-" * 58,
    ]
    for line in payload["lines"]:
        sections.append(
            " | ".join(
                (
                    line["title"],
                    f"全空间模型排名 {line['model_score_rank']:,}/{universe:,}",
                    f"冻结导出排名 {_rank_text(line['final_export_rank'], line['top_n'])}",
                    f"精确6红 Top100/1000/10000 {_hit_triplet(line, 'exact')}",
                    f"红5最佳排名 {_rank_text(line['red5_rank'], line['top_n'])}",
                )
            )
        )
    sections.extend(
        (
            "",
            f"全空间模型排名最佳：{summary['best_model_rank_line']}，第 {summary['best_model_rank']:,} 名",
            f"精确6红进入 Top100/1000/10000 的线数：{summary['exact_hit_line_counts']['top_100']}/"
            f"{summary['exact_hit_line_counts']['top_1000']}/{summary['exact_hit_line_counts']['top_10000']}",
            f"红5进入 Top100/1000/10000 的线数：{summary['red5_hit_line_counts']['top_100']}/"
            f"{summary['red5_hit_line_counts']['top_1000']}/{summary['red5_hit_line_counts']['top_10000']}",
            "",
            "二、逐线明细",
            "=" * 58,
        )
    )
    for index, line in enumerate(payload["lines"], start=1):
        cutoff_counts = line["matched_red_count_by_cutoff"]
        artifact = line["evaluation_artifact"]
        sections.extend(
            (
                f"{index}. {line['title']}",
                "-" * 58,
                f"本次开奖号码在训练成果全空间模型排名：{line['model_score_rank']:,} / {universe:,}",
                f"排名所处前段比例：{line['model_rank_fraction_percent']:.4f}%（数值越小越靠前）",
                f"初始结构排名：{_optional_int(line['initial_score_rank'])}",
                f"冻结 Top{line['top_n']:,} 导出排名：{_rank_text(line['final_export_rank'], line['top_n'])}",
                f"精确6红 Top100：{_yes_no(line['hit_top_100'])}",
                f"精确6红 Top1000：{_yes_no(line['hit_top_1000'])}",
                f"精确6红 Top10000：{_yes_no(line['hit_top_10000'])}",
                f"红5最佳组合：{_numbers_text(line['red5_numbers'])}",
                f"红5最佳排名：{_rank_text(line['red5_rank'], line['top_n'])}",
                f"红5 Top100：{_yes_no(line['hit_red5_top_100'])}",
                f"红5 Top1000：{_yes_no(line['hit_red5_top_1000'])}",
                f"红5 Top10000：{_yes_no(line['hit_red5_top_10000'])}",
                "冻结候选中的命中组合数：",
                f"  Top100：6红={cutoff_counts['top_100']['6']}，5红={cutoff_counts['top_100']['5']}",
                f"  Top1000：6红={cutoff_counts['top_1000']['6']}，5红={cutoff_counts['top_1000']['5']}",
                f"  Top10000：6红={cutoff_counts['top_10000']['6']}，5红={cutoff_counts['top_10000']['5']}",
                f"排名路径：合法生成={_pass_fail(line['generated'])} -> 硬过滤={_pass_fail(line['passed_hard_filters'])} "
                f"-> 全空间排名={line['model_score_rank']} -> 冻结导出排名={line['final_export_rank']}",
                f"淘汰阶段/原因：{_stage_text(line['eliminated_stage'])} / "
                f"{_reason_text(line['elimination_reason'])}",
                f"预测依据期：{line['as_of_issue']}；目标期：{issue}",
                f"预测快照：{line['snapshot_key']}",
                f"预测运行：{line['prediction_run_key']}",
                f"评估运行：{line['evaluation_run_key']}",
                f"候选完整性：{line['candidate_count']:,}/{line['top_n']:,}",
                f"Ranking Contract：{line['prediction_ranking_contract']}",
                f"配置摘要：{line['config_hash']}",
                f"预测指纹：{line['prediction_fingerprint']}",
                f"泄漏检查：{_pass_fail(line['leakage_passed'])}",
                f"Evaluation Artifact：{artifact['status']} / {artifact.get('artifact_digest') or '无（历史兼容证据）'}",
                f"Runtime Envelope：{artifact.get('source_runtime_envelope_digest') or '无（历史兼容证据）'}",
                f"Candidate ABI：{artifact.get('candidate_package_digest') or '无（历史兼容证据）'}",
                f"快照生成时间：{line['snapshot_generated_at']}",
                f"评估完成时间：{line['evaluated_at']}",
                "",
            )
        )
    sections.extend(
        (
            "三、口径与随机基线",
            "=" * 58,
            "1. “全空间模型排名”来自开奖前冻结配置在同一合法红球全集上的重放排名；不是开奖后重新调参结果。",
            "2. “冻结导出排名”只表示是否进入保存的 TopN。未进入时，精确组合导出排名为空，但全空间模型排名仍然有效。",
            "3. “精确6红”与“红5”是两种不同指标，不能互相替代。",
            f"4. 等概率随机组合进入 Top100/1000/10000 的单次概率约为 "
            f"{100 / universe * 100:.5f}% / {1000 / universe * 100:.5f}% / {10000 / universe * 100:.5f}%。",
            "5. 单期排名或命中只是一份前向证据，不足以证明稳定预测能力；应结合滚动历史与 Walk-forward 结果判断。",
            "",
            f"报表证据摘要（SHA-256）：{payload['report_digest']}",
            "本邮件由开奖前冻结预测快照与开奖后验收 Evaluation 自动编译。",
        )
    )
    return "\n".join(sections) + "\n"


class PostDrawEvaluationDeliveryLedger:
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

    def begin(self, report: PostDrawEvaluationReport) -> None:
        state = self._load()
        existing = state["deliveries"].get(report.delivery_key)
        if existing is not None:
            status = str(existing.get("status"))
            if status == "sent":
                return
            raise PostDrawDeliveryStateError(
                f"delivery {report.delivery_key} is {status}; manual review is required"
            )
        state["deliveries"][report.delivery_key] = {
            "status": "sending",
            "issue": report.issue,
            "report_digest": report.report_digest,
            "started_at": self._timestamp(),
            "completed_at": None,
            "message_id": None,
        }
        self._write(state)

    def mark_sent(self, delivery_key: str, receipt: MailDeliveryReceipt) -> None:
        self._transition(delivery_key, expected="sending", status="sent", message_id=receipt.message_id)

    def mark_uncertain(self, delivery_key: str) -> None:
        self._transition(delivery_key, expected="sending", status="uncertain", message_id=None)

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
            raise PostDrawDeliveryStateError(
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
            raise PostDrawDeliveryStateError("post-draw mail ledger is unreadable") from None
        if (
            not isinstance(state, dict)
            or state.get("protocol") != DELIVERY_LEDGER_PROTOCOL
            or not isinstance(state.get("deliveries"), dict)
        ):
            raise PostDrawDeliveryStateError("post-draw mail ledger schema is invalid")
        if any(
            not isinstance(entry, dict) or entry.get("status") not in {"sending", "sent", "uncertain"}
            for entry in state["deliveries"].values()
        ):
            raise PostDrawDeliveryStateError("post-draw mail ledger state is invalid")
        return state

    def _write(self, state: dict[str, Any]) -> None:
        atomic_write_text(
            self.path,
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )

    def _timestamp(self) -> str:
        return self._now_factory().astimezone(timezone.utc).isoformat()


class PostDrawEvaluationNotificationService:
    def __init__(
        self,
        config: QqMailConfig,
        *,
        mail_service: QqMailService | None = None,
        ledger: PostDrawEvaluationDeliveryLedger | None = None,
        output_dir: Path = DEFAULT_REPORT_DIR,
    ) -> None:
        if config.recipient is None:
            raise PostDrawEvaluationReportError(
                "DEHPS_QQ_MAIL_RECIPIENT is required for post-draw report delivery"
            )
        self.config = config
        self.mail_service = mail_service or QqMailService(config)
        self.ledger = ledger or PostDrawEvaluationDeliveryLedger()
        self.output_dir = output_dir

    def preview(self, rows: list[dict[str, Any]]) -> PostDrawEvaluationReport:
        return compile_post_draw_evaluation_report(rows, recipient=self.config.destination)

    def deliver(self, rows: list[dict[str, Any]]) -> PostDrawEvaluationDeliveryResult:
        report = self.preview(rows)
        json_path, text_path = write_post_draw_evaluation_artifacts(report, self.output_dir)
        with self.ledger.exclusive():
            current_status = self.ledger.status(report.delivery_key)
            if current_status == "sent":
                return PostDrawEvaluationDeliveryResult(
                    status="already_sent",
                    issue=report.issue,
                    report_digest=report.report_digest,
                    delivery_key=report.delivery_key,
                    json_path=str(json_path),
                    text_path=str(text_path),
                    message_id=None,
                )
            if current_status is not None:
                raise PostDrawDeliveryStateError(
                    f"delivery {report.delivery_key} is {current_status}; manual review is required"
                )
            self.ledger.begin(report)
            try:
                receipt = self.mail_service.send(
                    subject=report.subject,
                    text=report.text,
                    html=report.html,
                    recipient=self.config.destination,
                )
            except Exception:
                self.ledger.mark_uncertain(report.delivery_key)
                raise
            self.ledger.mark_sent(report.delivery_key, receipt)
        return PostDrawEvaluationDeliveryResult(
            status="sent",
            issue=report.issue,
            report_digest=report.report_digest,
            delivery_key=report.delivery_key,
            json_path=str(json_path),
            text_path=str(text_path),
            message_id=receipt.message_id,
        )


def _validate_and_normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_line: dict[str, list[dict[str, Any]]] = {key: [] for key in REQUIRED_LINE_KEYS}
    for raw in rows:
        row = _json_safe(raw)
        line_key = str(row.get("line_key") or "")
        if line_key in by_line:
            by_line[line_key].append(row)
    invalid_counts = {key: len(values) for key, values in by_line.items() if len(values) != 1}
    if invalid_counts:
        raise PostDrawEvaluationReportError(
            f"three-line accepted evidence must contain exactly one row per line: {invalid_counts}"
        )
    ordered = [by_line[key][0] for key in REQUIRED_LINE_KEYS]
    issue = str(ordered[0].get("predicted_issue") or "")
    actual_identity = (
        str(ordered[0].get("actual_draw_date") or ""),
        tuple(int(value) for value in ordered[0].get("actual_red_numbers") or ()),
        ordered[0].get("actual_blue_number"),
    )
    actual_red = actual_identity[1]
    actual_blue = actual_identity[2]
    if (
        not issue
        or not actual_identity[0]
        or len(actual_red) != 6
        or tuple(sorted(actual_red)) != actual_red
        or len(set(actual_red)) != 6
        or actual_red[0] < 1
        or actual_red[-1] > 33
        or actual_blue is None
        or not 1 <= int(actual_blue) <= 16
    ):
        raise PostDrawEvaluationReportError("complete draw identity is required")
    for row in ordered:
        _validate_row(row, issue=issue, actual_identity=actual_identity)
    return ordered


def _validate_row(
    row: dict[str, Any],
    *,
    issue: str,
    actual_identity: tuple[str, tuple[int, ...], Any],
) -> None:
    summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
    audit = summary.get("ranking_audit") if isinstance(summary.get("ranking_audit"), dict) else {}
    if str(row.get("predicted_issue") or "") != issue:
        raise PostDrawEvaluationReportError("all evaluation rows must target the same issue")
    row_actual = (
        str(row.get("actual_draw_date") or ""),
        tuple(int(value) for value in row.get("actual_red_numbers") or ()),
        row.get("actual_blue_number"),
    )
    if row_actual != actual_identity:
        raise PostDrawEvaluationReportError("all evaluation rows must bind to the same draw")
    current_actual = (
        str(row.get("current_actual_draw_date") or ""),
        tuple(int(value) for value in row.get("current_actual_red_numbers") or ()),
        row.get("current_actual_blue_number"),
    )
    if current_actual != actual_identity:
        raise PostDrawEvaluationReportError(
            f"line {row.get('line_key')} evaluated draw disagrees with current official history"
        )
    if (
        row.get("status") != "evaluated"
        or row.get("prediction_status") != "evaluated"
        or row.get("evaluation_run_status") != "completed"
    ):
        raise PostDrawEvaluationReportError(f"line {row.get('line_key')} is not fully evaluated")
    prediction_run_key = str(row.get("prediction_run_key") or "")
    evaluation_run_key = str(row.get("evaluation_run_key") or "")
    snapshot_key = str(row.get("snapshot_key") or "")
    if not prediction_run_key or not evaluation_run_key or not snapshot_key:
        raise PostDrawEvaluationReportError(f"line {row.get('line_key')} lacks durable run identity")
    as_of_issue = str(row.get("as_of_issue") or "")
    if not as_of_issue or not _issue_less_than(as_of_issue, issue) or summary.get("leakage_passed") is not True:
        raise PostDrawEvaluationReportError(f"line {row.get('line_key')} failed the pre-draw leakage guard")
    top_n = int(row.get("top_n") or 0)
    counts = {
        int(row.get("candidate_count") or 0),
        int(row.get("prediction_candidate_count") or 0),
        int(row.get("persisted_candidate_count") or 0),
    }
    if top_n <= 0 or counts != {top_n}:
        raise PostDrawEvaluationReportError(
            f"line {row.get('line_key')} frozen candidate snapshot is incomplete"
        )
    legal_space = int(audit.get("legal_sample_space") or 0)
    model_rank = int(audit.get("model_score_rank") or 0)
    ranking_contract = str(row.get("prediction_ranking_contract") or "")
    if (
        audit.get("protocol") != "forward-actual-ranking-path-v1"
        or str(audit.get("issue") or "") != issue
        or audit.get("line_key") != row.get("line_key")
        or audit.get("prediction_run_key") != prediction_run_key
        or audit.get("snapshot_key") != snapshot_key
        or tuple(int(value) for value in audit.get("actual_reds") or ()) != actual_identity[1]
        or audit.get("ranking_contract") != ranking_contract
        or row.get("run_ranking_contract") != ranking_contract
        or audit.get("generated") is not True
        or audit.get("passed_hard_filters") is not True
        or legal_space != TOTAL_SSQ_RED_COMBINATIONS
        or not 1 <= model_rank <= legal_space
    ):
        raise PostDrawEvaluationReportError(f"line {row.get('line_key')} lacks a valid full-universe rank")
    final_export_rank = audit.get("final_export_rank")
    exact_rank = row.get("exact_rank")
    if final_export_rank != exact_rank or (
        final_export_rank is not None and not 1 <= int(final_export_rank) <= top_n
    ):
        raise PostDrawEvaluationReportError(f"line {row.get('line_key')} export rank evidence disagrees")
    red5_rank = row.get("red5_rank")
    if red5_rank is not None and not 1 <= int(red5_rank) <= top_n:
        raise PostDrawEvaluationReportError(f"line {row.get('line_key')} red5 rank is outside the frozen export")
    _validate_cutoff_flags(row, rank=exact_rank, prefix="")
    _validate_cutoff_flags(row, rank=red5_rank, prefix="red5_")
    cutoff_counts = summary.get("matched_red_count_by_cutoff")
    if not _valid_cutoff_counts(cutoff_counts):
        raise PostDrawEvaluationReportError(f"line {row.get('line_key')} cutoff overlap counts are invalid")
    artifact = summary.get("evaluation_artifact")
    if not isinstance(artifact, dict) or artifact.get("status") not in {"verified", "unavailable"}:
        raise PostDrawEvaluationReportError(f"line {row.get('line_key')} lacks Evaluation Artifact state")
    if artifact.get("status") == "verified" and not artifact.get("artifact_digest"):
        raise PostDrawEvaluationReportError(f"line {row.get('line_key')} verified artifact lacks a digest")


def _validate_cutoff_flags(row: dict[str, Any], *, rank: Any, prefix: str) -> None:
    normalized_rank = None if rank is None else int(rank)
    for cutoff in (100, 1000, 10000):
        field = f"hit_{prefix}top_{cutoff}"
        expected = normalized_rank is not None and normalized_rank <= cutoff
        if row.get(field) is not expected:
            raise PostDrawEvaluationReportError(f"line {row.get('line_key')} has inconsistent {field}")


def _valid_cutoff_counts(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    previous = {"5": 0, "6": 0}
    for cutoff in (100, 1000, 10000):
        counts = value.get(f"top_{cutoff}")
        if not isinstance(counts, dict):
            return False
        current: dict[str, int] = {}
        for overlap in ("5", "6"):
            count = counts.get(overlap)
            if not isinstance(count, int) or isinstance(count, bool) or count < previous[overlap]:
                return False
            current[overlap] = count
        previous = current
    return True


def _report_line(row: dict[str, Any]) -> dict[str, Any]:
    summary = row["summary"]
    audit = summary["ranking_audit"]
    artifact = summary["evaluation_artifact"]
    model_rank = int(audit["model_score_rank"])
    return {
        "line_key": row["line_key"],
        "title": LINE_TITLES[row["line_key"]],
        "line_label": row.get("line_label"),
        "prediction_run_key": row["prediction_run_key"],
        "evaluation_run_key": row["evaluation_run_key"],
        "snapshot_key": row["snapshot_key"],
        "as_of_issue": row["as_of_issue"],
        "prediction_ranking_contract": row["prediction_ranking_contract"],
        "config_hash": row["config_hash"],
        "prediction_fingerprint": row["prediction_fingerprint"],
        "candidate_count": int(row["candidate_count"]),
        "top_n": int(row["top_n"]),
        "snapshot_generated_at": row["snapshot_generated_at"],
        "evaluated_at": row["evaluated_at"],
        "leakage_passed": True,
        "model_score_rank": model_rank,
        "model_rank_fraction_percent": model_rank / TOTAL_SSQ_RED_COMBINATIONS * 100,
        "initial_score_rank": audit.get("initial_score_rank"),
        "final_export_rank": audit.get("final_export_rank"),
        "generated": audit.get("generated"),
        "passed_hard_filters": audit.get("passed_hard_filters"),
        "eliminated_stage": audit.get("eliminated_stage"),
        "elimination_reason": audit.get("elimination_reason"),
        "hit_top_100": bool(row["hit_top_100"]),
        "hit_top_1000": bool(row["hit_top_1000"]),
        "hit_top_10000": bool(row["hit_top_10000"]),
        "red5_rank": row.get("red5_rank"),
        "red5_numbers": row.get("red5_numbers"),
        "hit_red5_top_100": bool(row["hit_red5_top_100"]),
        "hit_red5_top_1000": bool(row["hit_red5_top_1000"]),
        "hit_red5_top_10000": bool(row["hit_red5_top_10000"]),
        "matched_red_count_by_cutoff": summary["matched_red_count_by_cutoff"],
        "evaluation_artifact": {
            "status": artifact.get("status"),
            "reason": artifact.get("reason"),
            "evaluation_contract": artifact.get("evaluation_contract"),
            "artifact_digest": artifact.get("artifact_digest"),
            "source_runtime_envelope_digest": artifact.get("source_runtime_envelope_digest"),
            "candidate_package_digest": artifact.get("candidate_package_digest"),
            "automatic_promotion_allowed": artifact.get("automatic_promotion_allowed"),
        },
    }


def _summary(lines: list[dict[str, Any]]) -> dict[str, Any]:
    best = min(lines, key=lambda line: int(line["model_score_rank"]))
    return {
        "best_model_rank_line": best["title"],
        "best_model_rank": best["model_score_rank"],
        "exact_hit_line_counts": {
            f"top_{cutoff}": sum(bool(line[f"hit_top_{cutoff}"]) for line in lines)
            for cutoff in (100, 1000, 10000)
        },
        "red5_hit_line_counts": {
            f"top_{cutoff}": sum(bool(line[f"hit_red5_top_{cutoff}"]) for line in lines)
            for cutoff in (100, 1000, 10000)
        },
    }


def _delivery_key(issue: str, report_digest: str, recipient: str) -> str:
    return hashlib.sha256(
        _canonical_json(
            {
                "protocol": DELIVERY_LEDGER_PROTOCOL,
                "issue": issue,
                "report_digest": report_digest,
                "recipient": recipient.lower(),
            }
        ).encode("utf-8")
    ).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


def _issue_less_than(left: str, right: str) -> bool:
    try:
        return int(left) < int(right)
    except ValueError:
        return left < right


def _yes_no(value: Any) -> str:
    return "命中" if value is True else "未命中"


def _pass_fail(value: Any) -> str:
    return "通过" if value is True else "未通过"


def _stage_text(value: Any) -> str:
    return {
        None: "无",
        "generation": "合法组合生成",
        "hard_filter": "硬过滤",
        "model_score": "全空间模型排名",
        "final_export": "冻结导出",
    }.get(value, str(value))


def _reason_text(value: Any) -> str:
    return {
        None: "无",
        "model_score_rank_below_export_cutoff": "全空间排名低于冻结导出截止位",
        "expected_candidate_missing_from_export": "应导出的候选在冻结快照中缺失",
        "export_rank_mismatch": "冻结导出排名与全空间排名不一致",
        "invalid_legal_combination": "开奖号码不是合法红球组合",
    }.get(value, str(value))


def _hit_triplet(line: dict[str, Any], prefix: str) -> str:
    field_prefix = "hit_" if prefix == "exact" else "hit_red5_"
    return "/".join(
        "是" if line[f"{field_prefix}top_{cutoff}"] else "否"
        for cutoff in (100, 1000, 10000)
    )


def _rank_text(rank: Any, top_n: int) -> str:
    return f"第 {int(rank):,} 名" if rank is not None else f"未进入 Top{int(top_n):,}"


def _optional_int(value: Any) -> str:
    return "无" if value is None else f"{int(value):,}"


def _numbers_text(values: Any) -> str:
    if not values:
        return "无（TopN 内没有红5组合）"
    return " ".join(f"{int(value):02d}" for value in values)


__all__ = [
    "PostDrawDeliveryStateError",
    "PostDrawEvaluationDeliveryLedger",
    "PostDrawEvaluationDeliveryResult",
    "PostDrawEvaluationNotificationService",
    "PostDrawEvaluationReport",
    "PostDrawEvaluationReportError",
    "compile_post_draw_evaluation_report",
    "deliver_post_draw_evaluation_report",
    "load_post_draw_evaluations",
    "render_post_draw_evaluation_report",
    "write_post_draw_evaluation_artifacts",
]
