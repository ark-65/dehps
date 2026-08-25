from __future__ import annotations

import fcntl
import hashlib
import html
import json
import math
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentRequestStatus
from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.notifications.mail import MailDeliveryReceipt, QqMailConfig, QqMailService
from dehps.research_os.information_theory.measurement_system_v2 import (
    forward_prequential_confirmatory as p3,
)
from dehps.research_os.models import (
    MainlineArtifactRegistration,
    Task,
    m4_v2_domain_digest,
)
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.research_os.supervisor import (
    AtomicArtifactPayload,
    AtomicCapabilityResult,
    MainlineSupervisorError,
    ResearchEvidenceSupervisor,
    integration_contract,
)


class P3Top100NotificationError(RuntimeError):
    """Fail-closed notification contract violation."""


class P3Top100DeliveryStateError(P3Top100NotificationError):
    """The idempotent delivery ledger requires manual review."""


CONTROL_PLANE_KEY = "m4-p3-top100-notification-v2"
P3_CONTROL_PLANE_KEY = "m4-information-theory-mainline"
GOAL_KEY = "M4_P3_TOP100_REPLAY_BOUND_MAIL_AND_RETURN_V2"
SOURCE_CONTRACT_PATH = "configs/research-os/m4-p3-top100-notification-source-v2.json"
SOURCE_SCHEMA = "dehps-m4-p3-top100-notification-source-contract.v2"
SOURCE_ARTIFACT_TYPE = "m4_p3_top100_notification_source_contract_v2"
SOURCE_DOMAIN = "dehps.m4.p3.top100-notification.source-contract.v2"
SOURCE_SET_DOMAIN = "dehps.m4.p3.top100-notification.source-set.v2"

RESEARCH_REQUEST_KEY = "research-m4-p3-top100-mail-and-return-contract-v1"
RESEARCH_REQUEST_ID = 675
RESEARCH_APPROVAL_DECISION_ID = 2852
ENGINEERING_REQUEST_KEY = "engineering-m4-p3-top100-additive-v2-atomic-recovery-v1"
ENGINEERING_REQUEST_ID = 681
ENGINEERING_APPROVAL_DECISION_ID = 2880
ENGINEERING_EXECUTION_ID = 555
RESEARCH_PAYLOAD_SHA256 = (
    "31776e8dcf25177dd66505a2a9a4b1c7c092c37d50e3f8623644eb650b54f0c3"
)
ENGINEERING_PAYLOAD_SHA256 = (
    "bdba771e05237398e63704686ba21f7dc03e0f9671dd9a70d86df048405649cd"
)

PRE_ENVELOPE_CAPABILITY = "p3_top100_pre_mail_envelope_v2"
PRE_REPLAY_CAPABILITY = "p3_top100_pre_mail_replay_v2"
POST_REPORT_CAPABILITY = "p3_top100_post_return_report_v2"
POST_REPLAY_CAPABILITY = "p3_top100_post_return_replay_v2"
CAPABILITIES = (
    PRE_ENVELOPE_CAPABILITY,
    PRE_REPLAY_CAPABILITY,
    POST_REPORT_CAPABILITY,
    POST_REPLAY_CAPABILITY,
)

PRE_ENVELOPE_ARTIFACT_TYPE = "P3Top100PreMailEnvelopeV1"
PRE_REPLAY_ARTIFACT_TYPE = "P3Top100PreMailReplayV1"
PAYOUT_SOURCE_ARTIFACT_TYPE = "P3Top100IssuePayoutSourceV1"
POST_REPORT_ARTIFACT_TYPE = "P3Top100PostReturnReportV1"
POST_REPLAY_ARTIFACT_TYPE = "P3Top100PostReturnReplayV1"
ARTIFACT_DOMAINS = {
    PRE_ENVELOPE_ARTIFACT_TYPE: "dehps.m4.p3.top100-notification.pre-envelope.v1",
    PRE_REPLAY_ARTIFACT_TYPE: "dehps.m4.p3.top100-notification.pre-replay.v1",
    PAYOUT_SOURCE_ARTIFACT_TYPE: "dehps.m4.p3.top100-notification.payout-source.v1",
    POST_REPORT_ARTIFACT_TYPE: "dehps.m4.p3.top100-notification.post-report.v1",
    POST_REPLAY_ARTIFACT_TYPE: "dehps.m4.p3.top100-notification.post-replay.v1",
}

BEIJING = ZoneInfo("Asia/Shanghai")
DRAW_WEEKDAYS = frozenset({1, 3, 6})
PRE_SEND_TIME = time(17, 0)
UNIT_COST = Decimal("2.00")
PORTFOLIO_COST = Decimal("200.00")
TAX_FREE_BOUNDARY = Decimal("10000.00")
TAX_RATE = Decimal("0.20")
MONEY_QUANTUM = Decimal("0.01")
FIXED_PRIZES = {
    3: Decimal("3000.00"),
    4: Decimal("200.00"),
    5: Decimal("10.00"),
    6: Decimal("5.00"),
}
DELIVERY_LEDGER_PROTOCOL = "p3-top100-mail-ledger.v1"
DEFAULT_LEDGER_PATH = ROOT_DIR / "runtime/notifications/p3_top100_mail.json"


def issue_task_keys(issue: str) -> dict[str, str]:
    normalized = _issue(issue)
    prefix = f"m4-p3-top100-notification-v2-{normalized}"
    return {
        "pre": f"{prefix}-pre-envelope",
        "pre_replay": f"{prefix}-pre-envelope-replay",
        "post": f"{prefix}-post-return-report",
        "post_replay": f"{prefix}-post-return-report-replay",
    }


def issue_facts(issue: str) -> dict[str, str]:
    keys = issue_task_keys(issue)
    return {
        "pre": f"{keys['pre']}:COMPILED",
        "pre_replay": f"{keys['pre_replay']}:REPLAY_VERIFIED",
        "post": f"{keys['post']}:COMPILED",
        "post_replay": f"{keys['post_replay']}:REPLAY_VERIFIED",
    }


def _issue(value: Any) -> str:
    issue = str(value or "").strip()
    if not issue or not issue.isdigit():
        raise P3Top100NotificationError("notification_issue_changed")
    return issue


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _artifact(
    *, artifact_type: str, body: Mapping[str, Any], parent_digests: Sequence[str]
) -> dict[str, Any]:
    if artifact_type not in ARTIFACT_DOMAINS:
        raise P3Top100NotificationError("notification_artifact_type_changed")
    payload: dict[str, Any] = {
        "schema_version": f"dehps-{artifact_type}.v1",
        "artifact_type": artifact_type,
        "body": deepcopy(dict(body)),
        "parent_digests": [str(item) for item in parent_digests],
    }
    payload["artifact_digest"] = m4_v2_domain_digest(
        payload, domain=ARTIFACT_DOMAINS[artifact_type]
    )
    return payload


def validate_notification_artifact(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(value))
    artifact_type = str(payload.get("artifact_type") or "")
    if artifact_type not in ARTIFACT_DOMAINS or set(payload) != {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "body",
        "parent_digests",
    }:
        raise P3Top100NotificationError("notification_artifact_shape_changed")
    if payload["schema_version"] != f"dehps-{artifact_type}.v1":
        raise P3Top100NotificationError("notification_artifact_schema_changed")
    digest = str(payload.pop("artifact_digest") or "")
    if m4_v2_domain_digest(payload, domain=ARTIFACT_DOMAINS[artifact_type]) != digest:
        raise P3Top100NotificationError("notification_artifact_digest_changed")
    payload["artifact_digest"] = digest
    return payload


def load_source_contract(*, root_dir: Path = ROOT_DIR) -> dict[str, Any]:
    root = root_dir.resolve()
    path = (root / SOURCE_CONTRACT_PATH).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise P3Top100NotificationError("notification_source_missing")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "contract_key",
        "governance_bindings",
        "source_entries",
        "source_set_digest",
    }:
        raise P3Top100NotificationError("notification_source_shape_changed")
    if (
        payload["schema_version"] != SOURCE_SCHEMA
        or payload["artifact_type"] != SOURCE_ARTIFACT_TYPE
        or payload["contract_key"] != GOAL_KEY
    ):
        raise P3Top100NotificationError("notification_source_identity_changed")
    entries: list[dict[str, Any]] = []
    for item in payload["source_entries"]:
        if not isinstance(item, Mapping) or set(item) != {"path", "bytes", "sha256"}:
            raise P3Top100NotificationError("notification_source_entry_changed")
        relative = str(item["path"])
        source_path = (root / relative).resolve()
        if not source_path.is_relative_to(root) or not source_path.is_file():
            raise P3Top100NotificationError("notification_source_path_changed")
        raw = source_path.read_bytes()
        expected = {
            "path": relative,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        if dict(item) != expected:
            raise P3Top100NotificationError(
                f"notification_source_bytes_changed:{relative}"
            )
        entries.append(expected)
    source_set = m4_v2_domain_digest(entries, domain=SOURCE_SET_DOMAIN)
    if payload["source_set_digest"] != source_set:
        raise P3Top100NotificationError("notification_source_set_changed")
    identity = dict(payload)
    observed = str(identity.pop("artifact_digest") or "")
    if m4_v2_domain_digest(identity, domain=SOURCE_DOMAIN) != observed:
        raise P3Top100NotificationError("notification_source_digest_changed")
    return payload


def verify_governance(repository: AgentRequestRepository) -> None:
    research = repository.get_request(RESEARCH_REQUEST_KEY)
    engineering = repository.get_request(ENGINEERING_REQUEST_KEY)
    research_decisions = repository.list_decisions(RESEARCH_REQUEST_KEY)
    engineering_decisions = repository.list_decisions(ENGINEERING_REQUEST_KEY)
    executions = repository.list_execution_metadata(ENGINEERING_REQUEST_KEY)
    if (
        research.id != RESEARCH_REQUEST_ID
        or research.status is not AgentRequestStatus.APPROVED
        or hashlib.sha256(_canonical_json(research.payload)).hexdigest()
        != RESEARCH_PAYLOAD_SHA256
        or not any(
            item.id == RESEARCH_APPROVAL_DECISION_ID
            and item.decision_code == "request_approved"
            for item in research_decisions
        )
        or engineering.id != ENGINEERING_REQUEST_ID
        or engineering.status
        not in {AgentRequestStatus.EXECUTING, AgentRequestStatus.COMPLETED}
        or hashlib.sha256(_canonical_json(engineering.payload)).hexdigest()
        != ENGINEERING_PAYLOAD_SHA256
        or not any(
            item.id == ENGINEERING_APPROVAL_DECISION_ID
            and item.decision_code == "request_approved"
            for item in engineering_decisions
        )
        or not any(item.id == ENGINEERING_EXECUTION_ID for item in executions)
    ):
        raise P3Top100NotificationError("notification_governance_changed")


@dataclass(frozen=True)
class PredrawBundle:
    issue: str
    model_candidates: dict[str, Any]
    random_baseline: dict[str, Any]
    checkpoint: dict[str, Any]
    report: dict[str, Any]
    replay: dict[str, Any]

    @property
    def input_digests(self) -> tuple[str, ...]:
        return (
            self.model_candidates["artifact_digest"],
            self.checkpoint["artifact_digest"],
            self.replay["artifact_digest"],
        )


@dataclass(frozen=True)
class PostdrawBundle:
    predraw: PredrawBundle
    settlement: dict[str, Any]
    settlement_replay: dict[str, Any]

    @property
    def input_digests(self) -> tuple[str, ...]:
        return (
            *self.predraw.input_digests,
            self.settlement["artifact_digest"],
            self.settlement_replay["artifact_digest"],
        )


def _registration_record(value: Mapping[str, Any]) -> MainlineArtifactRegistration:
    record = MainlineArtifactRegistration(
        execution_id=str(value.get("execution_id") or ""),
        control_plane_key=str(value.get("control_plane_key") or ""),
        task_key=str(value.get("task_key") or ""),
        task_digest=str(value.get("task_digest") or ""),
        artifact_digest=str(value.get("artifact_digest") or ""),
        artifact_type=str(value.get("artifact_type") or ""),
        schema_version=str(value.get("schema_version") or ""),
        artifact_path=str(value.get("artifact_path") or ""),
        parent_digests=tuple(str(item) for item in value.get("parent_digests", ())),
        git_commit=str(value.get("git_commit") or ""),
    )
    if value.get("registration_digest") != record.registration_digest:
        raise P3Top100NotificationError("notification_registration_digest_changed")
    return record


def _completed_children(
    repository: PostgresResearchOSRepository,
    *,
    root_dir: Path,
    control_plane_key: str,
    task_key: str,
    expected_types: set[str],
    validator: Callable[[Mapping[str, Any]], dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    manifest = repository.load_manifest(control_plane_key=control_plane_key)
    tasks = [item for item in manifest.tasks if item.task_key == task_key]
    if len(tasks) != 1:
        raise P3Top100NotificationError("notification_parent_task_not_unique")
    task = tasks[0]
    events = repository.list_mainline_execution_events(
        control_plane_key=control_plane_key, task_key=task_key
    )
    completed = [item for item in events if item.get("event_type") == "completed"]
    if len(completed) != 1 or completed[0].get("task_digest") != task.artifact_digest:
        raise P3Top100NotificationError("notification_parent_completion_changed")
    execution_id = str(completed[0]["execution_id"])
    registrations = repository.list_mainline_artifacts(
        control_plane_key=control_plane_key, execution_id=execution_id
    )
    children = [
        item
        for item in registrations
        if item.get("artifact_type") != "research_os_mainline_execution"
    ]
    if {str(item.get("artifact_type")) for item in children} != expected_types:
        raise P3Top100NotificationError("notification_parent_artifact_set_changed")
    if len(children) != len(expected_types):
        raise P3Top100NotificationError("notification_parent_artifact_duplicated")
    output: dict[str, dict[str, Any]] = {}
    root = root_dir.resolve()
    for item in children:
        record = _registration_record(item)
        if (
            record.control_plane_key != control_plane_key
            or record.execution_id != execution_id
            or record.task_key != task_key
            or record.task_digest != task.artifact_digest
        ):
            raise P3Top100NotificationError("notification_registration_parent_changed")
        path = (root / record.artifact_path).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
            raise P3Top100NotificationError("notification_registered_path_changed")
        payload = validator(json.loads(path.read_text(encoding="utf-8")))
        if (
            record.artifact_digest != payload["artifact_digest"]
            or record.artifact_type != payload["artifact_type"]
            or record.schema_version != payload["schema_version"]
            or record.parent_digests != tuple(payload["parent_digests"])
        ):
            raise P3Top100NotificationError("notification_registered_content_changed")
        output[record.artifact_type] = payload
    return output


def _validated_tickets(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    body = candidate["body"]
    tickets = body.get("tickets")
    if (
        body.get("mode") != "SHADOW_ONLY"
        or body.get("candidate_count") != 100
        or not isinstance(tickets, list)
        or len(tickets) != 100
    ):
        raise P3Top100NotificationError("notification_candidate_set_changed")
    seen: set[tuple[int, ...]] = set()
    output: list[dict[str, Any]] = []
    for expected_rank, item in enumerate(tickets, start=1):
        if not isinstance(item, Mapping) or int(item.get("rank", 0)) != expected_rank:
            raise P3Top100NotificationError("notification_candidate_rank_changed")
        red = tuple(int(value) for value in item.get("red_numbers", ()))
        blue = int(item.get("blue_number", 0))
        score = float(item.get("model_log2_score", float("nan")))
        if (
            len(red) != 6
            or red != tuple(sorted(red))
            or len(set(red)) != 6
            or red[0] < 1
            or red[-1] > 33
            or not 1 <= blue <= 16
            or not math.isfinite(score)
            or red in seen
        ):
            raise P3Top100NotificationError("notification_candidate_ticket_changed")
        seen.add(red)
        output.append(
            {"rank": expected_rank, "red_numbers": list(red), "blue_number": blue}
        )
    return output


def load_predraw_bundle(
    repository: PostgresResearchOSRepository,
    *,
    issue: str,
    root_dir: Path = ROOT_DIR,
) -> PredrawBundle:
    issue = _issue(issue)
    keys = p3.issue_task_keys(issue)
    predraw = _completed_children(
        repository,
        root_dir=root_dir,
        control_plane_key=P3_CONTROL_PLANE_KEY,
        task_key=keys["predraw"],
        expected_types={
            p3.MODEL_CANDIDATE_ARTIFACT_TYPE,
            p3.RANDOM_BASELINE_ARTIFACT_TYPE,
            p3.CHECKPOINT_ARTIFACT_TYPE,
            p3.PREDRAW_REPORT_ARTIFACT_TYPE,
        },
        validator=p3.validate_artifact,
    )
    replay_values = _completed_children(
        repository,
        root_dir=root_dir,
        control_plane_key=P3_CONTROL_PLANE_KEY,
        task_key=keys["predraw_replay"],
        expected_types={p3.PREDRAW_REPLAY_ARTIFACT_TYPE},
        validator=p3.validate_artifact,
    )
    candidates = predraw[p3.MODEL_CANDIDATE_ARTIFACT_TYPE]
    baseline = predraw[p3.RANDOM_BASELINE_ARTIFACT_TYPE]
    checkpoint = predraw[p3.CHECKPOINT_ARTIFACT_TYPE]
    report = predraw[p3.PREDRAW_REPORT_ARTIFACT_TYPE]
    replay = replay_values[p3.PREDRAW_REPLAY_ARTIFACT_TYPE]
    _validated_tickets(candidates)
    if (
        candidates["body"].get("target_issue") != issue
        or checkpoint["body"].get("target_issue") != issue
        or checkpoint["body"].get("status") != "SEALED_BEFORE_DRAW"
        or checkpoint["body"].get("lineage_id") != p3.LINEAGE_ID
        or checkpoint["body"].get("configuration_drift") is not False
        or checkpoint["body"].get("model_candidate_digest")
        != candidates["artifact_digest"]
        or replay["body"].get("target_issue") != issue
        or replay["body"].get("status") != "REPLAY_VERIFIED"
        or replay["body"].get("registered_replay_status")
        != "REGISTERED_REPLAY_VERIFIED"
        or replay["body"].get("configuration_drift") is not False
        or replay["parent_digests"]
        != [
            candidates["artifact_digest"],
            baseline["artifact_digest"],
            checkpoint["artifact_digest"],
            report["artifact_digest"],
        ]
    ):
        raise P3Top100NotificationError("notification_predraw_parent_chain_changed")
    return PredrawBundle(issue, candidates, baseline, checkpoint, report, replay)


def load_postdraw_bundle(
    repository: PostgresResearchOSRepository,
    *,
    issue: str,
    root_dir: Path = ROOT_DIR,
) -> PostdrawBundle:
    predraw = load_predraw_bundle(repository, issue=issue, root_dir=root_dir)
    keys = p3.issue_task_keys(predraw.issue)
    settlement_values = _completed_children(
        repository,
        root_dir=root_dir,
        control_plane_key=P3_CONTROL_PLANE_KEY,
        task_key=keys["settlement"],
        expected_types={p3.SETTLEMENT_ARTIFACT_TYPE},
        validator=p3.validate_artifact,
    )
    replay_values = _completed_children(
        repository,
        root_dir=root_dir,
        control_plane_key=P3_CONTROL_PLANE_KEY,
        task_key=keys["settlement_replay"],
        expected_types={p3.SETTLEMENT_REPLAY_ARTIFACT_TYPE},
        validator=p3.validate_artifact,
    )
    settlement = settlement_values[p3.SETTLEMENT_ARTIFACT_TYPE]
    replay = replay_values[p3.SETTLEMENT_REPLAY_ARTIFACT_TYPE]
    if (
        settlement["body"].get("status") != "SETTLED"
        or settlement["body"].get("target_issue") != predraw.issue
        or settlement["body"].get("lineage_id") != p3.LINEAGE_ID
        or settlement["body"].get("configuration_drift") is not False
        or settlement["body"].get("ticket_support_decision_credit") is not False
        or replay["body"].get("status") != "REPLAY_VERIFIED"
        or replay["body"].get("registered_replay_status")
        != "REGISTERED_REPLAY_VERIFIED"
        or replay["body"].get("target_issue") != predraw.issue
        or replay["parent_digests"]
        != [settlement["artifact_digest"], predraw.checkpoint["artifact_digest"]]
    ):
        raise P3Top100NotificationError("notification_settlement_parent_chain_changed")
    return PostdrawBundle(predraw, settlement, replay)


def require_pre_draw_window(now: datetime, *, official_draw_time: str) -> datetime:
    local = now.astimezone(BEIJING)
    official = datetime.fromisoformat(official_draw_time).astimezone(BEIJING)
    if (
        local.date() != official.date()
        or local.weekday() not in DRAW_WEEKDAYS
        or local.timetz().replace(tzinfo=None) < PRE_SEND_TIME
        or local >= official
    ):
        raise P3Top100NotificationError("notification_predraw_window_closed")
    return local


def _recipient_digest(recipient: str) -> str:
    return hashlib.sha256(recipient.strip().lower().encode("utf-8")).hexdigest()


def build_pre_envelope(
    *, bundle: PredrawBundle, recipient_digest: str
) -> dict[str, Any]:
    tickets = _validated_tickets(bundle.model_candidates)
    if len(recipient_digest) != 64:
        raise P3Top100NotificationError("notification_recipient_digest_changed")
    subject = (
        f"[DEHPS][实验性·非投注建议] 双色球 {bundle.issue} "
        "新P3 Top-100（模拟投入200元）"
    )
    lines = [
        f"双色球 {bundle.issue} 新P3 Top-100（实验性影子输出）",
        f"P3 lineage: {p3.LINEAGE_ID}",
        f"候选集: {bundle.model_candidates['artifact_digest']}",
        f"开奖前回放: {bundle.replay['artifact_digest']} / REGISTERED_REPLAY_VERIFIED",
        "",
        "模拟投入：¥200.00（100 注 × ¥2.00）",
        "税前中奖总额：待开奖",
        "预计应纳税额：待开奖",
        "预计税后到账：待开奖",
        "扣除200元后的净收益：待开奖",
        "回报率：待开奖",
        "",
        "号码（红球 + 蓝球）：",
    ]
    lines.extend(
        f"#{item['rank']:03d}  红球 "
        + " ".join(f"{value:02d}" for value in item["red_numbers"])
        + f"  蓝球 {item['blue_number']:02d}  单注 ¥2.00"
        for item in tickets
    )
    lines.extend(
        [
            "",
            (
                "说明：这是固定模拟投入 200 元的账面展示。DEHPS 不购买彩票、不确认实际购买、"
                "不保证中奖，也未证明概率优势；若没有实际购买对应票据，实际财务收益为 0。"
            ),
        ]
    )
    text = "\n".join(lines)
    return _artifact(
        artifact_type=PRE_ENVELOPE_ARTIFACT_TYPE,
        body={
            "status": "COMPILED_NOT_DELIVERED",
            "issue": bundle.issue,
            "lineage_id": p3.LINEAGE_ID,
            "recipient_digest": recipient_digest,
            "subject": subject,
            "text": text,
            "html": f"<!doctype html><html><body><pre>{html.escape(text)}</pre></body></html>",
            "candidate_count": 100,
            "unit_cost_cny": "2.00",
            "hypothetical_total_cost_cny": "200.00",
            "predraw_replay_status": "REGISTERED_REPLAY_VERIFIED",
            "configuration_drift": False,
            "actual_purchase_known": False,
        },
        parent_digests=bundle.input_digests,
    )


def build_pre_replay(
    *, envelope: Mapping[str, Any], expected: Mapping[str, Any]
) -> dict[str, Any]:
    envelope = validate_notification_artifact(envelope)
    expected = validate_notification_artifact(expected)
    if envelope != expected or envelope["artifact_type"] != PRE_ENVELOPE_ARTIFACT_TYPE:
        raise P3Top100NotificationError("notification_pre_typed_replay_changed")
    return _artifact(
        artifact_type=PRE_REPLAY_ARTIFACT_TYPE,
        body={
            "status": "REPLAY_VERIFIED",
            "issue": envelope["body"]["issue"],
            "same_registered_content": True,
            "smtp_connected": False,
            "delivery_eligible": True,
        },
        parent_digests=(envelope["artifact_digest"], *envelope["parent_digests"]),
    )


def _record_value(record: Mapping[str, Any], names: Sequence[str]) -> Any:
    for name in names:
        value = record.get(name)
        if value not in (None, ""):
            return value
    return None


def _decimal_money(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value).replace(",", "")).quantize(
            MONEY_QUANTUM, rounding=ROUND_HALF_UP
        )
    except Exception as exc:
        raise P3Top100NotificationError("notification_prize_amount_changed") from exc
    if amount < 0:
        raise P3Top100NotificationError("notification_prize_amount_changed")
    return amount


def normalize_payout_record(
    *, record: Mapping[str, Any], bundle: PostdrawBundle
) -> dict[str, Any]:
    issue = _issue(_record_value(record, ("issue", "code", "term")))
    settlement = bundle.settlement["body"]
    red_raw = _record_value(
        record, ("red", "red_numbers", "redBalls", "frontWinningNum")
    )
    blue_raw = _record_value(
        record, ("blue", "blue_number", "blueBall", "backWinningNum")
    )
    red = tuple(
        int(item)
        for item in (
            red_raw.replace(",", " ").split()
            if isinstance(red_raw, str)
            else red_raw or ()
        )
    )
    blue = int(blue_raw or 0)
    details = record.get("winnerDetails")
    if (
        issue != bundle.predraw.issue
        or tuple(sorted(red)) != tuple(settlement["actual_red_numbers"])
        or blue != int(settlement["actual_blue_number"])
        or not isinstance(details, list)
        or len(details) != 6
    ):
        raise P3Top100NotificationError("notification_payout_draw_identity_changed")
    tiers: dict[int, dict[str, Any]] = {}
    for detail in details:
        if not isinstance(detail, Mapping):
            raise P3Top100NotificationError("notification_payout_tier_changed")
        tier = int(detail.get("awardEtc", 0))
        base = detail.get("baseBetWinner")
        if not isinstance(base, Mapping):
            raise P3Top100NotificationError("notification_payout_tier_changed")
        amount = _decimal_money(base.get("awardMoney"))
        award_num = int(base.get("awardNum", detail.get("awardNum", 0)) or 0)
        if tier not in range(1, 7) or tier in tiers or award_num < 0:
            raise P3Top100NotificationError("notification_payout_tier_changed")
        if tier in FIXED_PRIZES and amount != FIXED_PRIZES[tier]:
            raise P3Top100NotificationError("notification_fixed_prize_changed")
        tiers[tier] = {
            "tier": tier,
            "single_ticket_gross_cny": f"{amount:.2f}",
            "official_award_count": award_num,
        }
    if set(tiers) != set(range(1, 7)):
        raise P3Top100NotificationError("notification_payout_tier_set_changed")
    raw_digest = hashlib.sha256(_canonical_json(dict(record))).hexdigest()
    return _artifact(
        artifact_type=PAYOUT_SOURCE_ARTIFACT_TYPE,
        body={
            "status": "EXACT_ISSUE_PAYOUT_VALIDATED",
            "source": "zhcw",
            "source_url": "https://jc.zhcw.com/port/client_json.php",
            "raw_record_sha256": raw_digest,
            "issue": issue,
            "actual_red_numbers": list(red),
            "actual_blue_number": blue,
            "tiers": [tiers[index] for index in range(1, 7)],
            "training_or_p3_decision_credit": False,
        },
        parent_digests=(
            bundle.settlement["artifact_digest"],
            bundle.settlement_replay["artifact_digest"],
        ),
    )


def prize_tier(*, red_hits: int, blue_hit: bool) -> int:
    if red_hits == 6 and blue_hit:
        return 1
    if red_hits == 6:
        return 2
    if red_hits == 5 and blue_hit:
        return 3
    if red_hits == 5 or (red_hits == 4 and blue_hit):
        return 4
    if red_hits == 4 or (red_hits == 3 and blue_hit):
        return 5
    if red_hits <= 2 and blue_hit:
        return 6
    return 0


def calculate_return(gross: Decimal) -> dict[str, str]:
    gross = gross.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    tax = (
        Decimal("0.00")
        if gross <= TAX_FREE_BOUNDARY
        else (gross * TAX_RATE).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    )
    after_tax = (gross - tax).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    net = (after_tax - PORTFOLIO_COST).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    roi = ((net / PORTFOLIO_COST) * Decimal(100)).quantize(
        MONEY_QUANTUM, rounding=ROUND_HALF_UP
    )
    return {
        "hypothetical_cost_cny": "200.00",
        "gross_prize_cny": f"{gross:.2f}",
        "estimated_tax_cny": f"{tax:.2f}",
        "after_tax_receipt_cny": f"{after_tax:.2f}",
        "net_profit_cny": f"{net:.2f}",
        "roi_percent": f"{roi:.2f}",
    }


def build_post_report(
    *, bundle: PostdrawBundle, payout: Mapping[str, Any], recipient_digest: str
) -> dict[str, Any]:
    payout = validate_notification_artifact(payout)
    if payout["artifact_type"] != PAYOUT_SOURCE_ARTIFACT_TYPE:
        raise P3Top100NotificationError("notification_payout_artifact_changed")
    if payout["parent_digests"] != [
        bundle.settlement["artifact_digest"],
        bundle.settlement_replay["artifact_digest"],
    ]:
        raise P3Top100NotificationError("notification_payout_parent_changed")
    amounts = {
        int(item["tier"]): _decimal_money(item["single_ticket_gross_cny"])
        for item in payout["body"]["tiers"]
    }
    actual_red = {int(item) for item in bundle.settlement["body"]["actual_red_numbers"]}
    actual_blue = int(bundle.settlement["body"]["actual_blue_number"])
    winners: list[dict[str, Any]] = []
    tier_counts = {index: 0 for index in range(1, 7)}
    gross = Decimal("0.00")
    for ticket in _validated_tickets(bundle.predraw.model_candidates):
        red_hits = len(actual_red.intersection(ticket["red_numbers"]))
        blue_hit = int(ticket["blue_number"]) == actual_blue
        tier = prize_tier(red_hits=red_hits, blue_hit=blue_hit)
        if tier:
            amount = amounts[tier]
            gross += amount
            tier_counts[tier] += 1
            winners.append(
                {
                    **ticket,
                    "red_hits": red_hits,
                    "blue_hit": blue_hit,
                    "tier": tier,
                    "gross_prize_cny": f"{amount:.2f}",
                }
            )
    accounting = calculate_return(gross)
    losing_count = 100 - len(winners)
    subject = f"[DEHPS][开奖复盘·模拟收益] 双色球 {bundle.predraw.issue} 新P3 Top-100"
    lines = [
        f"双色球 {bundle.predraw.issue} 新P3 Top-100 开奖复盘",
        "开奖号码：红球 "
        + " ".join(f"{item:02d}" for item in sorted(actual_red))
        + f"  蓝球 {actual_blue:02d}",
        f"开奖结算回放：{bundle.settlement_replay['artifact_digest']}",
        f"奖金来源：中彩网当期 winnerDetails / {payout['body']['raw_record_sha256']}",
        "",
        "模拟投入：¥200.00（100 注 × ¥2.00）",
        f"税前中奖总额：¥{accounting['gross_prize_cny']}",
        f"预计应纳税额：¥{accounting['estimated_tax_cny']}",
        f"预计税后到账：¥{accounting['after_tax_receipt_cny']}",
        f"扣除200元后的净收益：¥{accounting['net_profit_cny']}",
        f"回报率：{accounting['roi_percent']}%",
        "",
        "中奖分布："
        + "，".join(f"{tier}等奖 {tier_counts[tier]} 注" for tier in range(1, 7))
        + f"，未中奖 {losing_count} 注",
        "中奖明细：",
    ]
    if winners:
        lines.extend(
            f"#{item['rank']:03d} 红球 "
            + " ".join(f"{value:02d}" for value in item["red_numbers"])
            + f" 蓝球 {item['blue_number']:02d}；红中{item['red_hits']} "
            + ("蓝中" if item["blue_hit"] else "蓝未中")
            + f"；{item['tier']}等奖 ¥{item['gross_prize_cny']}"
            for item in winners
        )
    else:
        lines.append("无中奖票据。")
    lines.extend(
        [
            "",
            (
                "税务口径：同一自然人、同一电脑彩票游戏、同一期全部中奖金额合并；"
                "合计不超过 ¥10,000.00 免征个人所得税，超过时按税前合计金额的 20% 估算。"
                "实际代扣及兑奖记录以彩票机构为准。"
            ),
            (
                "说明：这是固定模拟投入 200 元的账面复盘。DEHPS 不购买彩票、不确认实际购买、"
                "不保证中奖，也未证明概率优势；票据支持与奖金对 P3 科学决策均为零信用。"
            ),
        ]
    )
    text = "\n".join(lines)
    return _artifact(
        artifact_type=POST_REPORT_ARTIFACT_TYPE,
        body={
            "status": "COMPILED_NOT_DELIVERED",
            "issue": bundle.predraw.issue,
            "lineage_id": p3.LINEAGE_ID,
            "recipient_digest": recipient_digest,
            "subject": subject,
            "text": text,
            "html": f"<!doctype html><html><body><pre>{html.escape(text)}</pre></body></html>",
            "candidate_count": 100,
            "winner_count": len(winners),
            "losing_count": losing_count,
            "tier_counts": {str(key): value for key, value in tier_counts.items()},
            "winners": winners,
            "accounting": accounting,
            "tax_free_boundary_cny": "10000.00",
            "tax_rate_over_boundary": "0.20",
            "p3_decision_credit": False,
            "configuration_drift": False,
        },
        parent_digests=(
            *bundle.input_digests,
            payout["artifact_digest"],
        ),
    )


def build_post_replay(
    *, report: Mapping[str, Any], expected: Mapping[str, Any]
) -> dict[str, Any]:
    report = validate_notification_artifact(report)
    expected = validate_notification_artifact(expected)
    if report != expected or report["artifact_type"] != POST_REPORT_ARTIFACT_TYPE:
        raise P3Top100NotificationError("notification_post_typed_replay_changed")
    return _artifact(
        artifact_type=POST_REPLAY_ARTIFACT_TYPE,
        body={
            "status": "REPLAY_VERIFIED",
            "issue": report["body"]["issue"],
            "same_registered_content": True,
            "smtp_connected": False,
            "delivery_eligible": True,
        },
        parent_digests=(report["artifact_digest"], *report["parent_digests"]),
    )


class P3Top100NotificationCapability:
    def __init__(
        self, *, repository: PostgresResearchOSRepository, root_dir: Path = ROOT_DIR
    ) -> None:
        self.repository = repository
        self.root_dir = root_dir

    @staticmethod
    def _contract(task: Task) -> dict[str, Any]:
        return json.loads(task.metric_contract)

    def _notification_artifact(
        self, *, task_key: str, artifact_type: str
    ) -> dict[str, Any]:
        return _completed_children(
            self.repository,
            root_dir=self.root_dir,
            control_plane_key=CONTROL_PLANE_KEY,
            task_key=task_key,
            expected_types={artifact_type},
            validator=validate_notification_artifact,
        )[artifact_type]

    def execute(
        self,
        *,
        control_plane_key: str,
        task: Task,
        execution_id: str,
        git_commit: str,
    ) -> AtomicCapabilityResult:
        del execution_id, git_commit
        if control_plane_key != CONTROL_PLANE_KEY:
            raise MainlineSupervisorError("notification control plane changed")
        integration_contract(task)
        source = load_source_contract(root_dir=self.root_dir)
        verify_governance(AgentRequestRepository())
        contract = self._contract(task)
        issue = _issue(contract.get("issue"))
        recipient_digest = str(contract.get("recipient_digest") or "")
        keys = issue_task_keys(issue)
        capability = str(task.requested_capability)
        task_source_digest = str(task.input_artifact_digests[-1])
        if task_source_digest != source["artifact_digest"]:
            raise MainlineSupervisorError("notification task source changed")
        metadata = (
            ("issue", issue),
            ("lineage_id", p3.LINEAGE_ID),
            ("source_contract_digest", task_source_digest),
            ("configuration_drift", False),
            ("smtp_connected", False),
            ("external_delivery", False),
        )
        if capability == PRE_ENVELOPE_CAPABILITY:
            if task.task_key != keys["pre"]:
                raise MainlineSupervisorError("notification pre task changed")
            bundle = load_predraw_bundle(
                self.repository, issue=issue, root_dir=self.root_dir
            )
            expected_inputs = (*bundle.input_digests, task_source_digest)
            if task.input_artifact_digests != expected_inputs:
                raise MainlineSupervisorError("notification pre inputs changed")
            envelope = build_pre_envelope(
                bundle=bundle, recipient_digest=recipient_digest
            )
            return AtomicCapabilityResult(
                artifacts=(
                    AtomicArtifactPayload(
                        "p3-top100-pre-envelope", "envelope.json", envelope
                    ),
                ),
                completion_facts=(issue_facts(issue)["pre"],),
                execution_metadata=metadata,
            )
        if capability == PRE_REPLAY_CAPABILITY:
            if task.task_key != keys["pre_replay"]:
                raise MainlineSupervisorError("notification pre replay task changed")
            envelope = self._notification_artifact(
                task_key=keys["pre"], artifact_type=PRE_ENVELOPE_ARTIFACT_TYPE
            )
            bundle = load_predraw_bundle(
                self.repository, issue=issue, root_dir=self.root_dir
            )
            expected = build_pre_envelope(
                bundle=bundle, recipient_digest=recipient_digest
            )
            if task.input_artifact_digests != (
                envelope["artifact_digest"],
                task_source_digest,
            ):
                raise MainlineSupervisorError("notification pre replay inputs changed")
            replay = build_pre_replay(envelope=envelope, expected=expected)
            return AtomicCapabilityResult(
                artifacts=(
                    AtomicArtifactPayload(
                        "p3-top100-pre-replay", "replay.json", replay
                    ),
                ),
                completion_facts=(issue_facts(issue)["pre_replay"],),
                execution_metadata=metadata,
            )
        if capability == POST_REPORT_CAPABILITY:
            if task.task_key != keys["post"]:
                raise MainlineSupervisorError("notification post task changed")
            bundle = load_postdraw_bundle(
                self.repository, issue=issue, root_dir=self.root_dir
            )
            payout_raw = contract.get("payout_source")
            if not isinstance(payout_raw, Mapping):
                raise MainlineSupervisorError("notification payout task input changed")
            payout = validate_notification_artifact(payout_raw)
            expected_inputs = (
                *bundle.input_digests,
                payout["artifact_digest"],
                task_source_digest,
            )
            if task.input_artifact_digests != expected_inputs:
                raise MainlineSupervisorError("notification post inputs changed")
            report = build_post_report(
                bundle=bundle, payout=payout, recipient_digest=recipient_digest
            )
            return AtomicCapabilityResult(
                artifacts=(
                    AtomicArtifactPayload(
                        "p3-top100-payout-source", "payout.json", payout
                    ),
                    AtomicArtifactPayload(
                        "p3-top100-post-report", "report.json", report
                    ),
                ),
                completion_facts=(issue_facts(issue)["post"],),
                execution_metadata=metadata,
            )
        if capability == POST_REPLAY_CAPABILITY:
            if task.task_key != keys["post_replay"]:
                raise MainlineSupervisorError("notification post replay task changed")
            values = _completed_children(
                self.repository,
                root_dir=self.root_dir,
                control_plane_key=CONTROL_PLANE_KEY,
                task_key=keys["post"],
                expected_types={PAYOUT_SOURCE_ARTIFACT_TYPE, POST_REPORT_ARTIFACT_TYPE},
                validator=validate_notification_artifact,
            )
            payout = values[PAYOUT_SOURCE_ARTIFACT_TYPE]
            report = values[POST_REPORT_ARTIFACT_TYPE]
            bundle = load_postdraw_bundle(
                self.repository, issue=issue, root_dir=self.root_dir
            )
            expected = build_post_report(
                bundle=bundle, payout=payout, recipient_digest=recipient_digest
            )
            if task.input_artifact_digests != (
                report["artifact_digest"],
                payout["artifact_digest"],
                task_source_digest,
            ):
                raise MainlineSupervisorError("notification post replay inputs changed")
            replay = build_post_replay(report=report, expected=expected)
            return AtomicCapabilityResult(
                artifacts=(
                    AtomicArtifactPayload(
                        "p3-top100-post-replay", "replay.json", replay
                    ),
                ),
                completion_facts=(issue_facts(issue)["post_replay"],),
                execution_metadata=metadata,
            )
        raise MainlineSupervisorError("notification capability escaped allowlist")


class P3Top100NotificationSupervisor(ResearchEvidenceSupervisor):
    """Unified Research Evidence Supervisor restricted to notification tasks."""

    def __init__(self, **kwargs: Any) -> None:
        from dehps.research_os import supervisor as supervisor_module

        registered = supervisor_module._TASK_ARTIFACT_NAMESPACE_BY_CONTROL_PLANE.get(
            CONTROL_PLANE_KEY
        )
        if registered not in (None, "mainline"):
            raise MainlineSupervisorError("notification artifact namespace changed")
        supervisor_module._TASK_ARTIFACT_NAMESPACE_BY_CONTROL_PLANE[
            CONTROL_PLANE_KEY
        ] = "mainline"
        super().__init__(control_plane_key=CONTROL_PLANE_KEY, **kwargs)
        self.capabilities = {}
        capability = P3Top100NotificationCapability(
            repository=self.repository, root_dir=self.root_dir
        )
        for name in CAPABILITIES:
            self.capabilities[name] = capability

    @property
    def state_path(self) -> Path:
        return (
            self.root_dir / "runtime/logs/p3-top100-notification-supervisor-state.json"
        )

    def _build_lane_status(
        self,
        manifest: Any,
        *,
        snapshot: Any,
        dispatch_performed: bool,
        completed_summary: Mapping[str, Any] | None = None,
        m4_v2_global_replay_summary: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        del completed_summary, m4_v2_global_replay_summary
        ready_queue = [item.task_key for item in snapshot.ready_queue]
        return {
            "schema_version": "dehps-p3-top100-notification-status.v2",
            "status": "ARMED",
            "control_plane_key": CONTROL_PLANE_KEY,
            "manifest_digest": manifest.artifact_digest,
            "snapshot_digest": snapshot.snapshot_digest,
            "ready_queue": ready_queue,
            "next_ready_task": ready_queue[0] if ready_queue else None,
            "tasks": {
                item.task_key: item.status.value for item in snapshot.resolutions
            },
            "dispatch_performed": dispatch_performed,
            "p3_scientific_lineage_modified": False,
            "p3_dispatch_allowed": False,
            "p4_dispatch_allowed": False,
            "p5_dispatch_allowed": False,
            "unkeyed_dispatch_allowed": False,
        }

    def _write_lane_status(self, payload: Mapping[str, Any]) -> None:
        atomic_write_text(
            self.root_dir / "runtime/logs/p3-top100-notification-status.json",
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )

    def replay(
        self, *, task_key: str, execution_id: str | None = None
    ) -> dict[str, Any]:
        manifest = self.repository.load_manifest(control_plane_key=CONTROL_PLANE_KEY)
        tasks = [item for item in manifest.tasks if item.task_key == task_key]
        if len(tasks) != 1 or tasks[0].requested_capability not in CAPABILITIES:
            raise MainlineSupervisorError("notification replay task escaped allowlist")
        events = self.repository.list_mainline_execution_events(
            control_plane_key=CONTROL_PLANE_KEY,
            task_key=task_key,
            execution_id=execution_id,
        )
        completed = [item for item in events if item.get("event_type") == "completed"]
        if len(completed) != 1:
            raise MainlineSupervisorError("notification replay completion changed")
        resolved_execution_id = str(completed[0]["execution_id"])
        registrations = self.repository.list_mainline_artifacts(
            control_plane_key=CONTROL_PLANE_KEY, execution_id=resolved_execution_id
        )
        result = P3Top100NotificationCapability(
            repository=self.repository, root_dir=self.root_dir
        ).execute(
            control_plane_key=CONTROL_PLANE_KEY,
            task=tasks[0],
            execution_id=resolved_execution_id,
            git_commit=str(completed[0].get("git_commit") or "0" * 40),
        )
        expected = {
            str(item.payload["artifact_type"]): validate_notification_artifact(
                item.payload
            )
            for item in result.artifacts
        }
        registered = _completed_children(
            self.repository,
            root_dir=self.root_dir,
            control_plane_key=CONTROL_PLANE_KEY,
            task_key=task_key,
            expected_types=set(expected),
            validator=validate_notification_artifact,
        )
        if registered != expected:
            raise MainlineSupervisorError("notification generic replay changed")
        return {
            "schema_version": "dehps-research-evidence-supervisor-replay.v1",
            "status": "REPLAY_VERIFIED",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "control_plane_key": CONTROL_PLANE_KEY,
            "task_key": task_key,
            "execution_id": resolved_execution_id,
            "registered_artifact_count": len(registrations),
            "same_execution_identity": True,
            "same_artifact_identity": True,
            "same_registered_content": True,
            "manual_input_assembly": False,
            "dispatch_performed": False,
            "durable_state_changed": False,
        }


@dataclass(frozen=True)
class NotificationEmail:
    kind: str
    issue: str
    artifact_digest: str
    replay_digest: str
    recipient_digest: str
    subject: str
    text: str
    html: str

    @property
    def delivery_key(self) -> str:
        return hashlib.sha256(
            _canonical_json(
                {
                    "protocol": DELIVERY_LEDGER_PROTOCOL,
                    "kind": self.kind,
                    "issue": self.issue,
                    "artifact_digest": self.artifact_digest,
                    "replay_digest": self.replay_digest,
                    "recipient_digest": self.recipient_digest,
                }
            )
        ).hexdigest()


class P3Top100DeliveryLedger:
    def __init__(
        self,
        path: Path = DEFAULT_LEDGER_PATH,
        *,
        now_factory: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self.now_factory = now_factory

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def status(self, key: str) -> str | None:
        item = self._load()["deliveries"].get(key)
        return None if item is None else str(item["status"])

    def begin(self, email: NotificationEmail) -> None:
        state = self._load()
        if email.delivery_key in state["deliveries"]:
            raise P3Top100DeliveryStateError("notification delivery already has state")
        state["deliveries"][email.delivery_key] = {
            "status": "sending",
            "kind": email.kind,
            "issue": email.issue,
            "artifact_digest": email.artifact_digest,
            "replay_digest": email.replay_digest,
            "recipient_digest": email.recipient_digest,
            "started_at": self.now_factory().astimezone(UTC).isoformat(),
            "completed_at": None,
            "message_id": None,
        }
        self._write(state)

    def finish(
        self, key: str, *, status: str, receipt: MailDeliveryReceipt | None
    ) -> None:
        if status not in {"sent", "uncertain"}:
            raise P3Top100DeliveryStateError("notification delivery transition changed")
        state = self._load()
        item = state["deliveries"].get(key)
        if not isinstance(item, dict) or item.get("status") != "sending":
            raise P3Top100DeliveryStateError("notification delivery state changed")
        item["status"] = status
        item["completed_at"] = self.now_factory().astimezone(UTC).isoformat()
        item["message_id"] = None if receipt is None else receipt.message_id
        self._write(state)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"protocol": DELIVERY_LEDGER_PROTOCOL, "deliveries": {}}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise P3Top100DeliveryStateError("notification ledger unreadable") from exc
        if (
            not isinstance(value, dict)
            or value.get("protocol") != DELIVERY_LEDGER_PROTOCOL
            or not isinstance(value.get("deliveries"), dict)
            or any(
                not isinstance(item, dict)
                or item.get("status") not in {"sending", "sent", "uncertain"}
                for item in value["deliveries"].values()
            )
        ):
            raise P3Top100DeliveryStateError("notification ledger schema changed")
        return value

    def _write(self, value: Mapping[str, Any]) -> None:
        atomic_write_text(
            self.path,
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )


class P3Top100NotificationDeliveryService:
    def __init__(
        self,
        config: QqMailConfig,
        *,
        mail_service: QqMailService | None = None,
        ledger: P3Top100DeliveryLedger | None = None,
    ) -> None:
        if config.recipient is None:
            raise P3Top100NotificationError("notification recipient is required")
        self.config = config
        self.mail_service = mail_service or QqMailService(config)
        self.ledger = ledger or P3Top100DeliveryLedger()

    def deliver(self, email: NotificationEmail) -> dict[str, Any]:
        if _recipient_digest(self.config.destination) != email.recipient_digest:
            raise P3Top100NotificationError("notification delivery recipient changed")
        with self.ledger.exclusive():
            status = self.ledger.status(email.delivery_key)
            if status == "sent":
                return {"status": "ALREADY_SENT", "delivery_key": email.delivery_key}
            if status is not None:
                raise P3Top100DeliveryStateError(
                    f"notification delivery is {status}; manual review required"
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
                self.ledger.finish(email.delivery_key, status="uncertain", receipt=None)
                raise
            self.ledger.finish(email.delivery_key, status="sent", receipt=receipt)
        return {
            "status": "SENT",
            "delivery_key": email.delivery_key,
            "message_id": receipt.message_id,
        }


def registered_delivery_email(
    repository: PostgresResearchOSRepository,
    *,
    issue: str,
    kind: str,
    recipient: str,
    root_dir: Path = ROOT_DIR,
) -> NotificationEmail:
    keys = issue_task_keys(issue)
    if kind == "pre":
        artifact_type, replay_type = (
            PRE_ENVELOPE_ARTIFACT_TYPE,
            PRE_REPLAY_ARTIFACT_TYPE,
        )
        task_key, replay_key = keys["pre"], keys["pre_replay"]
    elif kind == "post":
        artifact_type, replay_type = (
            POST_REPORT_ARTIFACT_TYPE,
            POST_REPLAY_ARTIFACT_TYPE,
        )
        task_key, replay_key = keys["post"], keys["post_replay"]
    else:
        raise P3Top100NotificationError("notification delivery kind changed")
    values = _completed_children(
        repository,
        root_dir=root_dir,
        control_plane_key=CONTROL_PLANE_KEY,
        task_key=task_key,
        expected_types=(
            {artifact_type}
            if kind == "pre"
            else {PAYOUT_SOURCE_ARTIFACT_TYPE, artifact_type}
        ),
        validator=validate_notification_artifact,
    )
    replays = _completed_children(
        repository,
        root_dir=root_dir,
        control_plane_key=CONTROL_PLANE_KEY,
        task_key=replay_key,
        expected_types={replay_type},
        validator=validate_notification_artifact,
    )
    artifact = values[artifact_type]
    replay = replays[replay_type]
    generic = P3Top100NotificationSupervisor(
        repository=repository, root_dir=root_dir
    ).replay(task_key=replay_key)
    recipient_digest = _recipient_digest(recipient)
    if (
        generic.get("status") != "REPLAY_VERIFIED"
        or generic.get("same_execution_identity") is not True
        or generic.get("same_artifact_identity") is not True
        or generic.get("dispatch_performed") is not False
        or replay["body"].get("status") != "REPLAY_VERIFIED"
        or replay["body"].get("delivery_eligible") is not True
        or replay["parent_digests"][0] != artifact["artifact_digest"]
        or artifact["body"].get("recipient_digest") != recipient_digest
    ):
        raise P3Top100NotificationError("notification delivery replay gate changed")
    return NotificationEmail(
        kind=kind,
        issue=_issue(issue),
        artifact_digest=artifact["artifact_digest"],
        replay_digest=replay["artifact_digest"],
        recipient_digest=recipient_digest,
        subject=str(artifact["body"]["subject"]),
        text=str(artifact["body"]["text"]),
        html=str(artifact["body"]["html"]),
    )


__all__ = [name for name in globals() if name.isupper()] + [
    "NotificationEmail",
    "P3Top100DeliveryLedger",
    "P3Top100DeliveryStateError",
    "P3Top100NotificationCapability",
    "P3Top100NotificationDeliveryService",
    "P3Top100NotificationError",
    "P3Top100NotificationSupervisor",
    "PostdrawBundle",
    "PredrawBundle",
    "build_post_replay",
    "build_post_report",
    "build_pre_envelope",
    "build_pre_replay",
    "calculate_return",
    "issue_facts",
    "issue_task_keys",
    "load_postdraw_bundle",
    "load_predraw_bundle",
    "load_source_contract",
    "normalize_payout_record",
    "prize_tier",
    "registered_delivery_email",
    "require_pre_draw_window",
    "validate_notification_artifact",
    "verify_governance",
]
