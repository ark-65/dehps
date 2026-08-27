from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

LINEAGE_ID = "M4_ISOLATED_24H_CHALLENGER_RESEARCH_FACTORY_V11"
GOAL_KEY = LINEAGE_ID
GOAL_ID = "m4-isolated-24h-challenger-research-factory"
CONTRACT_KEY = "M4_ISOLATED_24H_CHALLENGER_RESEARCH_FACTORY_CONTRACT_V11"
CONTRACT_DIGEST = "6d14bd57f290e9e0a625658bf0255cf33d1609efa68e667993cc58ccec8f7a02"
LIFECYCLE_ADDENDUM_REQUEST_ID = 702
LIFECYCLE_ADDENDUM_APPROVAL_DECISION_ID = 2949
LIFECYCLE_ADDENDUM_PAYLOAD_SHA256 = (
    "8f6d92347f53e43a1ec7eb869e015d6d78cc1e37feb5661657312bf9e90ebe49"
)
CONTRACT_SCHEMA = "dehps-m4-isolated-24h-challenger-contract.v11"
CONTROL_PLANE_KEY = "m4-isolated-24h-challenger-mainline-v11"
FREEZE_FACT = "m4-isolated-24h-challenger-contract-v11:FROZEN"
MAIL_CONFIGURATION_FACT = "m4-isolated-24h-challenger-v11-mail-configuration:VERIFIED"
OPERATOR_ATTESTATION_FACT = (
    "m4-isolated-24h-challenger-v11-operator-attestation:VERIFIED"
)
MAIL_BLOCKED_FACT = (
    "m4-isolated-24h-challenger-v11-mail-configuration:ACTIVATION_BLOCKED_MAIL"
)
SOURCE_CONTRACT_PATH = "configs/research-os/m4-isolated-24h-challenger-source-v11.json"
SOURCE_SCHEMA = "dehps-m4-isolated-24h-challenger-source-contract.v11"
SOURCE_ARTIFACT_TYPE = "m4_isolated_24h_challenger_source_contract_v11"
DATABASE_SCHEMA_VERSION = "dehps-m4-isolated-24h-challenger-db.v11"
SOURCE_DOMAIN = "dehps.m4.isolated-24h-challenger.source-contract.v11"
SOURCE_SET_DOMAIN = "dehps.m4.isolated-24h-challenger.source-set.v11"
ARTIFACT_DOMAIN = "dehps.m4.isolated-24h-challenger.artifact.v11"
ARTIFACT_SCHEMA = "dehps-m4-isolated-24h-challenger-artifact.v11"
FORMAL_P3_LINEAGE = "M4_P3_FORWARD_PREQUENTIAL_CONFIRMATORY_SUCCESSOR_V1"
FORMAL_P3_SOURCE_DIGEST = (
    "139ddc97ce1d81ea4e6182359f8391532ed1911090db004bcdf9ebcdea5f9493"
)
FORMAL_P3_UNIT = "dehps-forward-prequential-successor.service"
FORMAL_P3_REQUIRED_STATUS = "AUTONOMOUS_WAIT_FORWARD"
WORKER_COUNT = 18
DAILY_BATCH_LIMIT = 44
ISSUE_BATCH_LIMIT = 132
ATTEMPTS_PER_BATCH = 18
CONFIGURATIONS_PER_BATCH = 6
SEED_ORDINALS = (0, 1, 2)
LIFETIME_MULTIPLICITY_LIMIT = 1_000_000
OUTER_FOLD_COUNT = 300
BASELINE_REPLICATES = 1_000
PORTFOLIO_SIZE = 100
LEGAL_RED_COMBINATION_COUNT = 1_107_568
LEASE_HEARTBEAT_SECONDS = 30
LEASE_STALE_AFTER_SECONDS = 180
WALL_TIMEOUT_SECONDS = 1_800
WORKER_RSS_SOFT_LIMIT_BYTES = 1 * 1024**3
WORKER_RSS_HARD_LIMIT_BYTES = 5 * 1024**3 // 4
THERMAL_SAMPLE_SECONDS = 10
THERMAL_PAUSE_CELSIUS = 92.0
THERMAL_PAUSE_CONSECUTIVE_SAMPLES = 2
THERMAL_HARD_STOP_CELSIUS = 100.0
THERMAL_RESUME_BELOW_CELSIUS = 80.0
THERMAL_RESUME_STABLE_SECONDS = 300
FORMAL_P3_POLL_SECONDS = 1
FORMAL_P3_KILL_GRACE_SECONDS = 5
FORMAL_P3_QUIESCENCE_SECONDS = 60
TIMEZONE = ZoneInfo("Asia/Shanghai")
SELECTION_CUTOFF = time(16, 40)
FREEZE_DEADLINE = time(16, 45)
PREDRAW_SEND_TIME = time(17, 0)
OFFICIAL_DRAW_TIME = time(21, 15)
DAILY_SEND_TIME = time(9, 0)
DRAW_WEEKDAYS = frozenset({1, 3, 6})  # Tuesday, Thursday, Sunday
INCIDENT_REASON_CODES = frozenset(
    {
        "DATA_BOUNDARY_VIOLATION",
        "ARTIFACT_DIGEST_MISMATCH",
        "REPLAY_FAILED",
        "CHECKPOINT_INCOMPLETE",
        "MULTIPLICITY_LEDGER_INCOMPLETE",
        "FORMAL_NAMESPACE_COLLISION",
        "FROZEN_ARTIFACT_MODIFIED",
        "UNVERIFIED_PREDICTION_DELIVERY_ATTEMPT",
        "RESOURCE_GUARD_TRIGGERED",
        "DEADLINE_OR_ABSENCE",
    }
)

_ISSUE_RE = re.compile(r"^[0-9]{7}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


class IsolatedChallengerContractError(ValueError):
    pass


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def domain_digest(value: object, *, domain: str) -> str:
    raw = domain.encode("utf-8") + b"\0" + canonical_json(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def require_digest(value: object, *, field: str) -> str:
    digest = str(value or "")
    if _DIGEST_RE.fullmatch(digest) is None:
        raise IsolatedChallengerContractError(f"{field}_invalid")
    return digest


def require_issue(value: object) -> str:
    issue = str(value or "")
    if _ISSUE_RE.fullmatch(issue) is None or int(issue[4:]) < 1:
        raise IsolatedChallengerContractError("target_issue_invalid")
    return issue


def draw_dates(year: int) -> tuple[date, ...]:
    current = date(year, 1, 1)
    end = date(year + 1, 1, 1)
    output: list[date] = []
    while current < end:
        if current.weekday() in DRAW_WEEKDAYS:
            output.append(current)
        current += timedelta(days=1)
    return tuple(output)


def require_history_draw_date(value: object, *, field: str) -> date:
    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    else:
        try:
            parsed = date.fromisoformat(str(value or ""))
        except ValueError as exc:
            raise IsolatedChallengerContractError(f"{field}_invalid") from exc
    return parsed


def require_draw_date(value: object, *, field: str) -> date:
    parsed = require_history_draw_date(value, field=field)
    if parsed.weekday() not in DRAW_WEEKDAYS:
        raise IsolatedChallengerContractError(f"{field}_not_scheduled_draw_day")
    return parsed


def next_ssq_draw_date(after: date) -> date:
    current = after + timedelta(days=1)
    while current.weekday() not in DRAW_WEEKDAYS:
        current += timedelta(days=1)
    return current


def next_official_issue(
    source_max_issue: str, *, candidate_draw_date: date
) -> str:
    source_max_issue = require_issue(source_max_issue)
    year = int(source_max_issue[:4])
    ordinal = int(source_max_issue[4:])
    if candidate_draw_date.year == year:
        if ordinal >= 999:
            raise IsolatedChallengerContractError("source_issue_ordinal_exhausted")
        return f"{year}{ordinal + 1:03d}"
    if candidate_draw_date.year == year + 1:
        return f"{year + 1}001"
    raise IsolatedChallengerContractError("candidate_draw_year_not_sequential")


def target_issue_projection(
    *,
    source_max_issue: str,
    source_max_draw_date: date | str,
    projection_time: datetime,
) -> dict[str, str]:
    source_max_issue = require_issue(source_max_issue)
    source_draw_date = require_history_draw_date(
        source_max_draw_date, field="source_max_draw_date"
    )
    if source_draw_date.year != int(source_max_issue[:4]):
        raise IsolatedChallengerContractError("source_issue_draw_year_changed")
    if projection_time.tzinfo is None:
        raise IsolatedChallengerContractError("projection_time_not_aware")
    projection_time = projection_time.astimezone(TIMEZONE)
    if source_draw_date > projection_time.date():
        raise IsolatedChallengerContractError("source_draw_date_after_projection")
    candidate_draw_date = next_ssq_draw_date(source_draw_date)
    candidate_issue = next_official_issue(
        source_max_issue, candidate_draw_date=candidate_draw_date
    )
    while True:
        deadline = datetime.combine(candidate_draw_date, PREDRAW_SEND_TIME, TIMEZONE)
        if projection_time <= deadline:
            break
        candidate_draw_date = next_ssq_draw_date(candidate_draw_date)
        candidate_issue = next_official_issue(
            candidate_issue, candidate_draw_date=candidate_draw_date
        )
    return {
        "source_max_issue": source_max_issue,
        "source_max_draw_date": source_draw_date.isoformat(),
        "target_issue": candidate_issue,
        "target_draw_date": candidate_draw_date.isoformat(),
        "deadline": deadline.isoformat(),
        "official_draw_time": datetime.combine(
            candidate_draw_date, OFFICIAL_DRAW_TIME, TIMEZONE
        ).isoformat(),
        "projection_time": projection_time.isoformat(),
    }


def schedule_for_issue(
    issue: str, *, target_draw_date: date | str
) -> dict[str, datetime]:
    require_issue(issue)
    draw_day = require_draw_date(target_draw_date, field="target_draw_date")
    return {
        "selection_cutoff": datetime.combine(draw_day, SELECTION_CUTOFF, TIMEZONE),
        "freeze_deadline": datetime.combine(draw_day, FREEZE_DEADLINE, TIMEZONE),
        "predraw_send": datetime.combine(draw_day, PREDRAW_SEND_TIME, TIMEZONE),
    }


def incident_identity(*, reason_code: str, first_offending_digest: str) -> str:
    if reason_code not in INCIDENT_REASON_CODES:
        raise IsolatedChallengerContractError("incident_reason_code_invalid")
    digest = require_digest(first_offending_digest, field="offending_artifact_digest")
    return hashlib.sha256(f"{reason_code}\0{digest}".encode()).hexdigest()


def render_context(
    *,
    source_max_issue: str,
    source_max_draw_date: date | str,
    target_issue: str | None = None,
    target_draw_date: date | str | None = None,
    batch_seq: int = 0,
    epoch_date: str | None = None,
    minute: str | None = None,
    incident_id: str | None = None,
    incident_reason_code: str = "DEADLINE_OR_ABSENCE",
    incident_offending_digest: str | None = None,
    cut_checkpoint_ref: str = "GENESIS",
    projection_time: str | None = None,
) -> dict[str, str]:
    source_max_issue = require_issue(source_max_issue)
    source_draw_date = require_history_draw_date(
        source_max_draw_date, field="source_max_draw_date"
    )
    if projection_time is None:
        immediate_draw_date = next_ssq_draw_date(source_draw_date)
        parsed_projection_time = datetime.combine(
            immediate_draw_date, PREDRAW_SEND_TIME, TIMEZONE
        )
    else:
        try:
            parsed_projection_time = datetime.fromisoformat(projection_time)
        except ValueError as exc:
            raise IsolatedChallengerContractError(
                "projection_time_invalid"
            ) from exc
        if parsed_projection_time.tzinfo is None:
            raise IsolatedChallengerContractError("projection_time_not_aware")
        parsed_projection_time = parsed_projection_time.astimezone(TIMEZONE)
    projected = target_issue_projection(
        source_max_issue=source_max_issue,
        source_max_draw_date=source_draw_date,
        projection_time=parsed_projection_time,
    )
    expected_target = projected["target_issue"]
    target_issue = (
        expected_target if target_issue is None else require_issue(target_issue)
    )
    if target_issue != expected_target:
        raise IsolatedChallengerContractError("target_issue_not_next_official_issue")
    expected_draw_date = projected["target_draw_date"]
    parsed_target_draw_date = (
        date.fromisoformat(expected_draw_date)
        if target_draw_date is None
        else require_draw_date(target_draw_date, field="target_draw_date")
    )
    if parsed_target_draw_date.isoformat() != expected_draw_date:
        raise IsolatedChallengerContractError("target_draw_date_not_projected")
    if not isinstance(batch_seq, int) or not 0 <= batch_seq <= 999_999_999_999:
        raise IsolatedChallengerContractError("batch_seq_invalid")
    draw_day = parsed_target_draw_date
    epoch_date = epoch_date or draw_day.strftime("%Y%m%d")
    minute = minute or draw_day.strftime("%Y%m%d") + "0000"
    incident_offending_digest = incident_offending_digest or hashlib.sha256(
        f"SIMULATION-OFFENDING\0{target_issue}".encode()
    ).hexdigest()
    incident_offending_digest = require_digest(
        incident_offending_digest, field="incident_offending_digest"
    )
    expected_incident_id = incident_identity(
        reason_code=incident_reason_code,
        first_offending_digest=incident_offending_digest,
    )
    incident_id = incident_id or expected_incident_id
    if re.fullmatch(r"[0-9]{8}", epoch_date) is None:
        raise IsolatedChallengerContractError("epoch_date_invalid")
    if re.fullmatch(r"[0-9]{12}", minute) is None:
        raise IsolatedChallengerContractError("minute_invalid")
    if cut_checkpoint_ref != "GENESIS" and re.fullmatch(
        r"[0-9]{12}", cut_checkpoint_ref
    ) is None:
        raise IsolatedChallengerContractError("cut_checkpoint_ref_invalid")
    require_digest(incident_id, field="incident_id")
    if incident_id != expected_incident_id:
        raise IsolatedChallengerContractError("incident_id_derivation_changed")
    return {
        "source_max_issue": source_max_issue,
        "source_max_draw_date": source_draw_date.isoformat(),
        "target_issue": target_issue,
        "target_draw_date": draw_day.isoformat(),
        "batch_seq": f"{batch_seq:012d}",
        "epoch_date": epoch_date,
        "minute": minute,
        "incident_id": incident_id,
        "incident_reason_code": incident_reason_code,
        "incident_offending_digest": incident_offending_digest,
        "cut_checkpoint_ref": cut_checkpoint_ref,
        "projection_time": parsed_projection_time.isoformat(),
    }


@dataclass(frozen=True)
class TaskTemplate:
    name: str
    group: str
    key_template: str
    capability: str
    artifact_types: tuple[str, ...]
    activation_mode: str
    status_projection: str

    def key(self, context: Mapping[str, str]) -> str:
        try:
            return self.key_template.format_map(dict(context))
        except KeyError as exc:
            raise IsolatedChallengerContractError(
                f"task_context_missing:{exc.args[0]}"
            ) from exc


SELF = "SELF_TYPED_PLUS_GENERIC_REPLAY"
PAIRED = "PAIRED_REPLAY_NO_FACT"
REPLAY = "TYPED_THEN_GENERIC_ONE_SHOT_FACT_GATE"
DELIVERY = "EXACTLY_ONCE_DELIVERY_THEN_GENERIC_RECEIPT_REPLAY"


TASK_TEMPLATES = (
    TaskTemplate(
        "genesis",
        "control",
        "m4-isolated-24h-challenger-v11-search-genesis",
        "M4IsolatedSearchGenesisCapabilityV11",
        ("M4IsolatedEmptyMultiplicityHeadV11", "M4IsolatedSearchCheckpointV11"),
        PAIRED,
        "GENESIS_REPLAY_WAIT",
    ),
    TaskTemplate(
        "search_batch",
        "control",
        "m4-isolated-24h-challenger-v11-search-batch-{batch_seq}",
        "M4IsolatedSearchBatchCapabilityV11",
        (
            "M4IsolatedCandidateRegistrationV11",
            "M4IsolatedMultiplicityRegistrationDeltaV11",
            "M4IsolatedMultiplicityRegistrationHeadV11",
            "M4IsolatedDuplicateSuppressionV11",
            "M4IsolatedExecutionAttemptV11",
            "M4IsolatedCandidateResultV11",
            "M4IsolatedSeedCohortV11",
            "M4IsolatedMultiplicityDeltaV11",
            "M4IsolatedSearchBatchV11",
        ),
        PAIRED,
        "SEARCH_BATCH_REPLAY_WAIT",
    ),
    TaskTemplate(
        "genesis_replay",
        "control",
        "m4-isolated-24h-challenger-v11-search-genesis-replay",
        "M4IsolatedSearchGenesisReplayCapabilityV11",
        ("M4IsolatedSearchCheckpointReplayV11",),
        REPLAY,
        "SEARCH_READY",
    ),
    TaskTemplate(
        "runtime_health",
        "control",
        "m4-isolated-24h-challenger-v11-runtime-health-{minute}",
        "M4IsolatedRuntimeHealthCapabilityV11",
        ("M4IsolatedRuntimeHealthV11",),
        SELF,
        "HEALTHY_OR_PREEMPTED",
    ),
    TaskTemplate(
        "preregistration",
        "control",
        "m4-isolated-24h-challenger-v11-preregistration",
        "M4IsolatedPreregistrationCapabilityV11",
        ("M4IsolatedPreregistrationV11",),
        SELF,
        "CONTRACT_FROZEN",
    ),
    TaskTemplate(
        "operator_attestation",
        "control",
        "m4-isolated-24h-challenger-v11-operator-attestation",
        "M4IsolatedOperatorAttestationCapabilityV11",
        ("M4IsolatedOperatorAttestationV11",),
        SELF,
        "OPERATOR_ATTESTATION_VERIFIED",
    ),
    TaskTemplate(
        "incident_head_genesis",
        "control",
        "m4-isolated-24h-challenger-v11-incident-head-genesis",
        "M4IsolatedIncidentHeadGenesisCapabilityV11",
        ("M4IsolatedEmptyIncidentHeadV11",),
        SELF,
        "INCIDENT_HEAD_READY",
    ),
    TaskTemplate(
        "search_checkpoint",
        "control",
        "m4-isolated-24h-challenger-v11-search-checkpoint-{batch_seq}",
        "M4IsolatedSearchCheckpointCapabilityV11",
        ("M4IsolatedSearchCheckpointV11",),
        PAIRED,
        "SEARCH_CHECKPOINT_REPLAY_WAIT",
    ),
    TaskTemplate(
        "mail_configuration",
        "control",
        "m4-isolated-24h-challenger-v11-mail-configuration",
        "M4IsolatedMailConfigurationCapabilityV11",
        ("M4IsolatedMailConfigurationV11",),
        SELF,
        "MAIL_CONFIGURATION_VERIFIED_OR_ACTIVATION_BLOCKED",
    ),
    TaskTemplate(
        "search_batch_replay",
        "control",
        "m4-isolated-24h-challenger-v11-search-batch-{batch_seq}-replay",
        "M4IsolatedSearchBatchReplayCapabilityV11",
        ("M4IsolatedSearchBatchReplayV11",),
        REPLAY,
        "SEARCH_CHECKPOINT_READY",
    ),
    TaskTemplate(
        "multiplicity_risk_limit",
        "control",
        "m4-isolated-24h-challenger-v11-multiplicity-risk-limit",
        "M4IsolatedMultiplicityRiskLimitCapabilityV11",
        ("M4IsolatedMultiplicityRiskLimitV11",),
        SELF,
        "MULTIPLICITY_RISK_LIMIT",
    ),
    TaskTemplate(
        "target_issue_projection",
        "control",
        "m4-isolated-24h-challenger-v11-target-{source_max_issue}-to-{target_issue}-projection",
        "M4IsolatedTargetIssueProjectionCapabilityV11",
        ("M4IsolatedTargetIssueProjectionV11",),
        SELF,
        "TARGET_PROJECTED",
    ),
    TaskTemplate(
        "search_checkpoint_replay",
        "control",
        "m4-isolated-24h-challenger-v11-search-checkpoint-{batch_seq}-replay",
        "M4IsolatedSearchCheckpointReplayCapabilityV11",
        ("M4IsolatedSearchCheckpointReplayV11",),
        REPLAY,
        "SEARCH_READY",
    ),
    TaskTemplate(
        "daily_summary",
        "daily",
        "m4-isolated-24h-challenger-v11-daily-{epoch_date}-summary",
        "M4IsolatedDailySummaryCapabilityV11",
        ("M4IsolatedDailySummaryV11",),
        PAIRED,
        "DAILY_REPLAY_WAIT",
    ),
    TaskTemplate(
        "daily_delivery",
        "daily",
        "m4-isolated-24h-challenger-v11-daily-{epoch_date}-delivery",
        "M4IsolatedMailDeliveryCapabilityV11",
        ("M4IsolatedDeliveryReceiptV11",),
        DELIVERY,
        "DAILY_SENT_OR_INCIDENT",
    ),
    TaskTemplate(
        "daily_mail_replay",
        "daily",
        "m4-isolated-24h-challenger-v11-daily-{epoch_date}-mail-replay",
        "M4IsolatedMailReplayCapabilityV11",
        ("M4IsolatedMailReplayV11",),
        REPLAY,
        "DAILY_DELIVERY_READY",
    ),
    TaskTemplate(
        "daily_mail_envelope",
        "daily",
        "m4-isolated-24h-challenger-v11-daily-{epoch_date}-mail-envelope",
        "M4IsolatedDailyMailEnvelopeCapabilityV11",
        ("M4IsolatedMailEnvelopeV11",),
        PAIRED,
        "DAILY_MAIL_REPLAY_WAIT",
    ),
    TaskTemplate(
        "daily_summary_replay",
        "daily",
        "m4-isolated-24h-challenger-v11-daily-{epoch_date}-summary-replay",
        "M4IsolatedDailySummaryReplayCapabilityV11",
        ("M4IsolatedDailySummaryReplayV11",),
        REPLAY,
        "DAILY_MAIL_READY",
    ),
    TaskTemplate(
        "incident_open",
        "incident",
        "m4-isolated-24h-challenger-v11-incident-{incident_id}-open",
        "M4IsolatedIncidentOpenCapabilityV11",
        ("M4IsolatedIncidentV11", "M4IsolatedIncidentHeadV11"),
        SELF,
        "INCIDENT_OPEN",
    ),
    TaskTemplate(
        "incident_mail_replay",
        "incident",
        "m4-isolated-24h-challenger-v11-incident-{incident_id}-mail-replay",
        "M4IsolatedMailReplayCapabilityV11",
        ("M4IsolatedMailReplayV11",),
        REPLAY,
        "INCIDENT_DELIVERY_READY",
    ),
    TaskTemplate(
        "incident_delivery",
        "incident",
        "m4-isolated-24h-challenger-v11-incident-{incident_id}-delivery",
        "M4IsolatedMailDeliveryCapabilityV11",
        ("M4IsolatedDeliveryReceiptV11",),
        DELIVERY,
        "INCIDENT_SENT_OR_UNCERTAIN",
    ),
    TaskTemplate(
        "incident_envelope",
        "incident",
        "m4-isolated-24h-challenger-v11-incident-{incident_id}-mail-envelope",
        "M4IsolatedIncidentMailEnvelopeCapabilityV11",
        ("M4IsolatedMailEnvelopeV11",),
        PAIRED,
        "INCIDENT_REPLAY_WAIT",
    ),
    TaskTemplate(
        "prediction",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-prediction",
        "M4IsolatedPredictionCapabilityV11",
        ("M4IsolatedPredictionV11",),
        PAIRED,
        "PREDICTION_REPLAY_WAIT",
    ),
    TaskTemplate(
        "settlement",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-settlement",
        "M4IsolatedSettlementCapabilityV11",
        ("M4IsolatedSettlementV11",),
        SELF,
        "SETTLEMENT_READY",
    ),
    TaskTemplate(
        "eligibility",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-eligibility",
        "M4IsolatedEligibilityCapabilityV11",
        ("M4IsolatedEligibilityV11",),
        SELF,
        "FREEZE_READY_OR_NO_ELIGIBLE",
    ),
    TaskTemplate(
        "post_delivery",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-post-delivery",
        "M4IsolatedMailDeliveryCapabilityV11",
        ("M4IsolatedDeliveryReceiptV11",),
        DELIVERY,
        "ISSUE_COMPLETE_OR_DELIVERY_INCIDENT",
    ),
    TaskTemplate(
        "history_snapshot",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-history-snapshot",
        "M4IsolatedHistorySnapshotCapabilityV11",
        ("M4IsolatedHistorySnapshotV11",),
        SELF,
        "SNAPSHOT_READY",
    ),
    TaskTemplate(
        "post_mail_replay",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-post-mail-replay",
        "M4IsolatedMailReplayCapabilityV11",
        ("M4IsolatedMailReplayV11",),
        REPLAY,
        "POSTDRAW_DELIVERY_READY",
    ),
    TaskTemplate(
        "predraw_delivery",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-predraw-delivery",
        "M4IsolatedMailDeliveryCapabilityV11",
        ("M4IsolatedDeliveryReceiptV11",),
        DELIVERY,
        "WAIT_DRAW",
    ),
    TaskTemplate(
        "challenger_freeze",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-challenger-freeze",
        "M4IsolatedChallengerFreezeCapabilityV11",
        ("M4IsolatedChallengerFreezeV11", "M4IsolatedNoChallengerV11"),
        SELF,
        "FROZEN_OR_ABSENT",
    ),
    TaskTemplate(
        "multiplicity_seal",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-multiplicity-seal",
        "M4IsolatedMultiplicitySealCapabilityV11",
        ("M4IsolatedMultiplicitySealV11",),
        SELF,
        "MULTIPLICITY_SEALED",
    ),
    TaskTemplate(
        "prediction_replay",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-prediction-replay",
        "M4IsolatedPredictionReplayCapabilityV11",
        ("M4IsolatedPredictionReplayV11",),
        REPLAY,
        "PREDRAW_MAIL_READY",
    ),
    TaskTemplate(
        "settlement_replay",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-settlement-replay",
        "M4IsolatedSettlementReplayCapabilityV11",
        ("M4IsolatedSettlementReplayV11",),
        REPLAY,
        "POSTDRAW_MAIL_READY",
    ),
    TaskTemplate(
        "settlement_report",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-settlement-report",
        "M4IsolatedSettlementReportCapabilityV11",
        ("M4IsolatedSettlementReportV11",),
        PAIRED,
        "SETTLEMENT_REPLAY_WAIT",
    ),
    TaskTemplate(
        "post_mail_envelope",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-post-mail-envelope",
        "M4IsolatedPostDrawMailEnvelopeCapabilityV11",
        ("M4IsolatedMailEnvelopeV11",),
        PAIRED,
        "POSTDRAW_MAIL_REPLAY_WAIT",
    ),
    TaskTemplate(
        "predraw_mail_replay",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-predraw-mail-replay",
        "M4IsolatedMailReplayCapabilityV11",
        ("M4IsolatedMailReplayV11",),
        REPLAY,
        "PREDRAW_DELIVERY_READY",
    ),
    TaskTemplate(
        "formal_p3_comparison_input",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-formal-p3-comparison-input",
        "M4IsolatedFormalP3ComparisonInputCapabilityV11",
        (
            "M4IsolatedFormalP3IssueProjectionV11",
            "M4IsolatedFormalP3PendingMarkerV11",
        ),
        SELF,
        "P3_COMPARISON_INPUT_RESOLVED",
    ),
    TaskTemplate(
        "formal_p3_comparison",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-formal-p3-comparison",
        "M4IsolatedFormalP3ComparisonCapabilityV11",
        ("M4IsolatedFormalP3ComparisonV11",),
        SELF,
        "P3_COMPARED_OR_PENDING",
    ),
    TaskTemplate(
        "predraw_mail_envelope",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-predraw-mail-envelope",
        "M4IsolatedPreDrawMailEnvelopeCapabilityV11",
        ("M4IsolatedMailEnvelopeV11",),
        PAIRED,
        "PREDRAW_MAIL_REPLAY_WAIT",
    ),
    TaskTemplate(
        "random_baseline_freeze",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-random-baseline-freeze",
        "M4IsolatedRandomBaselineFreezeCapabilityV11",
        ("M4IsolatedRandomBaselineSetV11",),
        PAIRED,
        "BASELINE_REPLAY_WAIT",
    ),
    TaskTemplate(
        "random_baseline_settlement",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-random-baseline-settlement",
        "M4IsolatedRandomBaselineSettlementCapabilityV11",
        ("M4IsolatedRandomBaselineSettlementV11",),
        SELF,
        "BASELINE_SETTLED",
    ),
    TaskTemplate(
        "random_baseline_freeze_replay",
        "issue",
        "m4-isolated-24h-challenger-v11-{target_issue}-random-baseline-freeze-replay",
        "M4IsolatedRandomBaselineReplayCapabilityV11",
        ("M4IsolatedRandomBaselineReplayV11",),
        REPLAY,
        "BASELINE_FROZEN",
    ),
)

ARTIFACT_TYPES = frozenset(
    artifact_type
    for template in TASK_TEMPLATES
    for artifact_type in template.artifact_types
) | frozenset(
    {
        "M4IsolatedIncidentV11",
        "M4IsolatedMailConfigurationV11",
        "M4IsolatedMailEnvelopeV11",
        "M4IsolatedMailReplayV11",
        "M4IsolatedDeliveryReceiptV11",
    }
)


def task_template_by_name(name: str) -> TaskTemplate:
    matches = [item for item in TASK_TEMPLATES if item.name == name]
    if len(matches) != 1:
        raise IsolatedChallengerContractError(f"task_template_not_unique:{name}")
    return matches[0]


def rendered_task_keys(context: Mapping[str, str]) -> tuple[str, ...]:
    keys = tuple(item.key(context) for item in TASK_TEMPLATES)
    if len(keys) != 42 or len(set(keys)) != 42:
        raise IsolatedChallengerContractError("rendered_task_key_set_changed")
    return keys


def formal_p3_activity_state(observation: Mapping[str, object]) -> str:
    required = {
        "query_ok",
        "LoadState",
        "ActiveState",
        "SubState",
        "MainPID",
        "ControlPID",
        "observed_monotonic_ns",
    }
    if set(observation) != required or observation.get("query_ok") is not True:
        return "PREEMPT"
    if (
        observation.get("LoadState") == "loaded"
        and observation.get("ActiveState") == "inactive"
        and observation.get("SubState") == "dead"
        and observation.get("MainPID") == 0
        and observation.get("ControlPID") == 0
        and isinstance(observation.get("observed_monotonic_ns"), int)
        and int(observation["observed_monotonic_ns"]) >= 0
    ):
        return "QUIESCENT"
    return "PREEMPT"


def assert_frozen_contract_surface() -> None:
    if len(TASK_TEMPLATES) != 42:
        raise IsolatedChallengerContractError("task_template_count_changed")
    if len(ARTIFACT_TYPES) != 43:
        raise IsolatedChallengerContractError("artifact_type_count_changed")
    if WORKER_COUNT != 18 or ATTEMPTS_PER_BATCH != 18:
        raise IsolatedChallengerContractError("parallelism_contract_changed")
    if LEGAL_RED_COMBINATION_COUNT != 1_107_568:
        raise IsolatedChallengerContractError("legal_space_changed")


assert_frozen_contract_surface()
