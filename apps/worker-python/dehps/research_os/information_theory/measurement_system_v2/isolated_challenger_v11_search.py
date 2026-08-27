from __future__ import annotations

import hashlib
import heapq
import itertools
import math
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import lru_cache
from multiprocessing import Manager
from pathlib import Path
from queue import Empty
from threading import Lock
from typing import Any

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import BernoulliNB
from sklearn.tree import DecisionTreeClassifier

from dehps.input_contracts.feature_contract import (
    FEATURE_COMPONENT_MANIFEST_DIGEST,
    FEATURE_COMPONENTS_V1,
)
from dehps.models.frequency_ranker import (
    FrequencyRankerConfig,
    score_frequency_candidate,
    train_frequency_stats,
)

from . import isolated_challenger_v11_contract as contract

HISTORY_SQL = """
SELECT id, issue, draw_date, red_numbers, r1, r2, r3, r4, r5, r6,
       blue_number, source, created_at
FROM ssq_history
WHERE issue < %(target_issue)s
ORDER BY issue ASC
""".strip()

TARGET_PROJECTION_SQL = """
SELECT id, issue, draw_date, red_numbers, r1, r2, r3, r4, r5, r6,
       blue_number, source, created_at
FROM ssq_history
ORDER BY issue ASC
""".strip()

HISTORY_SCHEMA_SQL = """
SELECT column_name, data_type, udt_name, is_nullable, ordinal_position
FROM information_schema.columns
WHERE table_schema = current_schema() AND table_name = 'ssq_history'
ORDER BY ordinal_position
""".strip()

REQUIRED_HISTORY_SCHEMA = {
    "id": ("bigint", "int8", "NO"),
    "issue": ("text", "text", "NO"),
    "draw_date": ("date", "date", "YES"),
    "red_numbers": ("ARRAY", "_int2", "NO"),
    "r1": ("smallint", "int2", "NO"),
    "r2": ("smallint", "int2", "NO"),
    "r3": ("smallint", "int2", "NO"),
    "r4": ("smallint", "int2", "NO"),
    "r5": ("smallint", "int2", "NO"),
    "r6": ("smallint", "int2", "NO"),
    "blue_number": ("smallint", "int2", "YES"),
    "source": ("text", "text", "YES"),
    "created_at": ("timestamp with time zone", "timestamptz", "NO"),
}

FAMILY_ORDER = (
    "MARGINAL_STATIC_ALPHA",
    "LOGISTIC_L2_LIBLINEAR",
    "BERNOULLI_NAIVE_BAYES",
    "SHALLOW_PLATT_TREE",
    "FEATURE_ABI32_LINEAR_RANKER",
)
TRAINING_WINDOWS: tuple[int | str, ...] = (900, 1500, "ALL_AVAILABLE")
PROBABILITY_CLIP = (0.000001, 0.999999)
ONE_HOT_FEATURE_IDS = tuple(
    f"red_number_one_hot_{number:02d}" for number in range(1, 34)
)
CALENDAR_FEATURE_ID = "known_target_weekday_one_hot_tuesday_thursday_sunday"
CALENDAR_COMPONENT_IDS = (
    "known_target_weekday_one_hot_tuesday",
    "known_target_weekday_one_hot_thursday",
    "known_target_weekday_one_hot_sunday",
)
LAG_FEATURE_IDS = ("hit_lag_1", "hit_lag_2", "hit_lag_3")
FREQUENCY_FEATURE_IDS = (
    "expanding_frequency",
    "rolling_frequency_5",
    "rolling_frequency_12",
    "rolling_frequency_30",
    "rolling_frequency_60",
    "rolling_frequency_120",
)
OMISSION_FEATURE_IDS = ("periods_since_seen_divided_by_available_history",)
HISTORY_FEATURE_IDS = LAG_FEATURE_IDS + FREQUENCY_FEATURE_IDS + OMISSION_FEATURE_IDS
OPTIONAL_FEATURE_GROUPS = (
    LAG_FEATURE_IDS,
    (CALENDAR_FEATURE_ID,),
    OMISSION_FEATURE_IDS,
    FREQUENCY_FEATURE_IDS,
)
FEATURE_ABI32_IDS = tuple(item.feature_id for item in FEATURE_COMPONENTS_V1)
FEATURE_ABI32_WEIGHT_FIELDS = tuple(item.weight_field for item in FEATURE_COMPONENTS_V1)

if (
    len(FEATURE_ABI32_IDS) != 32
    or len(set(FEATURE_ABI32_IDS)) != 32
    or FEATURE_COMPONENT_MANIFEST_DIGEST
    != "42ed7fc0a60a1be64f6f097f14e765f447f941d4427395a2e86bdbc99431c0c4"
):
    raise RuntimeError("isolated_v11_feature_abi32_identity_changed")


class IsolatedSearchError(contract.IsolatedChallengerContractError):
    pass


@dataclass(frozen=True)
class HistoryRow:
    issue: str
    draw_date: date
    red_numbers: tuple[int, ...]
    blue_number: int
    source: str


@dataclass(frozen=True)
class CandidateConfiguration:
    family: str
    representation: str
    training_window: int | str
    ordered_feature_ids: tuple[str, ...]
    ordered_hyperparameters: tuple[tuple[str, Any], ...]
    snapshot_digest: str
    source_contract_digest: str
    parent_configuration_id: str | None = None

    @property
    def configuration_id(self) -> str:
        body = {
            "lineage_id": contract.LINEAGE_ID,
            "family": self.family,
            "representation": self.representation,
            "training_window": self.training_window,
            "ordered_feature_ids": list(self.ordered_feature_ids),
            "ordered_hyperparameters": [
                list(item) for item in self.ordered_hyperparameters
            ],
            "snapshot_digest": self.snapshot_digest,
            "source_contract_digest": self.source_contract_digest,
            "parent_configuration_id": self.parent_configuration_id,
        }
        return contract.domain_digest(
            body,
            domain="dehps.m4.isolated-24h-challenger.configuration.v11",
        )


@dataclass(frozen=True)
class CandidateJob:
    configuration: CandidateConfiguration
    seed_ordinal: int
    candidate_id: str
    seed_hex: str
    parent_candidate_id: str | None = None


@dataclass(frozen=True)
class CandidateOutcome:
    candidate_id: str
    configuration_id: str
    seed_ordinal: int
    seed_hex: str
    status: str
    primary_mean: float
    block_means: tuple[float, float, float]
    fold_values: tuple[float, ...]
    error_code: str | None = None


@dataclass(frozen=True)
class CandidateAttemptOutcome:
    candidate_id: str
    retry_ordinal: int
    status: str
    reason: str | None


@dataclass(frozen=True)
class RegistryState:
    m_total: int = 0
    registration_seq: int = -1
    registered_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class BatchProposal:
    jobs: tuple[CandidateJob, ...]
    duplicate_suppressions: tuple[CandidateJob, ...]
    base_cursor: int
    adaptive_cursor: int
    slot_sources: tuple[str, ...]


class AtomicCandidateRegistry:
    """In-process mirror of the SERIALIZABLE database registration contract."""

    def __init__(self, state: RegistryState | None = None) -> None:
        self._state = state or RegistryState()
        self._lock = Lock()

    @property
    def state(self) -> RegistryState:
        with self._lock:
            return self._state

    def register_batch(self, jobs: Sequence[CandidateJob]) -> RegistryState:
        if len(jobs) != contract.ATTEMPTS_PER_BATCH:
            raise IsolatedSearchError("atomic_registration_requires_exactly_18")
        identities = tuple(job.candidate_id for job in jobs)
        if len(set(identities)) != len(identities):
            raise IsolatedSearchError("atomic_registration_duplicate_candidate")
        with self._lock:
            if self._state.m_total + len(jobs) > contract.LIFETIME_MULTIPLICITY_LIMIT:
                raise IsolatedSearchError("MULTIPLICITY_RISK_LIMIT")
            overlap = self._state.registered_ids.intersection(identities)
            if overlap:
                raise IsolatedSearchError("candidate_already_registered")
            self._state = RegistryState(
                m_total=self._state.m_total + len(jobs),
                registration_seq=self._state.registration_seq + 1,
                registered_ids=self._state.registered_ids.union(identities),
            )
            return self._state


def validate_history_schema(rows: Sequence[Mapping[str, Any]]) -> str:
    by_name: dict[str, Mapping[str, Any]] = {}
    normalized: list[dict[str, Any]] = []
    prior_ordinal = 0
    for raw in rows:
        required = {
            "column_name",
            "data_type",
            "udt_name",
            "is_nullable",
            "ordinal_position",
        }
        if set(raw) != required:
            raise IsolatedSearchError("HISTORY_SCHEMA_INVALID")
        name = str(raw["column_name"])
        ordinal = int(raw["ordinal_position"])
        if name in by_name or ordinal <= prior_ordinal:
            raise IsolatedSearchError("HISTORY_SCHEMA_INVALID")
        prior_ordinal = ordinal
        by_name[name] = raw
        normalized.append(
            {
                "column_name": name,
                "data_type": str(raw["data_type"]),
                "udt_name": str(raw["udt_name"]),
                "is_nullable": str(raw["is_nullable"]),
                "ordinal_position": ordinal,
            }
        )
    if not set(REQUIRED_HISTORY_SCHEMA).issubset(by_name):
        raise IsolatedSearchError("HISTORY_SCHEMA_INVALID")
    for name, expected in REQUIRED_HISTORY_SCHEMA.items():
        row = by_name[name]
        actual = (
            str(row["data_type"]),
            str(row["udt_name"]),
            str(row["is_nullable"]),
        )
        if actual != expected:
            raise IsolatedSearchError("HISTORY_SCHEMA_INVALID")
    return contract.domain_digest(
        normalized,
        domain="dehps.m4.isolated-24h-challenger.ssq-history-schema.v11",
    )


def normalize_projection_rows(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    output: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    seen_issues: set[str] = set()
    previous_issue: str | None = None
    previous_draw_date: date | None = None
    required = {
        "id",
        "issue",
        "draw_date",
        "red_numbers",
        "r1",
        "r2",
        "r3",
        "r4",
        "r5",
        "r6",
        "blue_number",
        "source",
        "created_at",
    }
    for raw in rows:
        if set(raw) != required:
            raise IsolatedSearchError("history_row_schema_changed")
        row_id = int(raw["id"])
        issue = contract.require_issue(raw["issue"])
        draw_date = raw["draw_date"]
        reds = tuple(int(value) for value in raw["red_numbers"])
        scalar_reds = tuple(int(raw[f"r{index}"]) for index in range(1, 7))
        blue_raw = raw["blue_number"]
        source_raw = raw["source"]
        created_at = raw["created_at"]
        if (
            row_id < 1
            or row_id in seen_ids
            or issue in seen_issues
            or not isinstance(draw_date, date)
            or issue[:4] != f"{draw_date.year:04d}"
            or len(reds) != 6
            or reds != tuple(sorted(reds))
            or len(set(reds)) != 6
            or any(not 1 <= value <= 33 for value in reds)
            or scalar_reds != reds
            or (
                blue_raw is not None
                and not 1 <= int(blue_raw) <= 16
            )
            or (source_raw is not None and not isinstance(source_raw, str))
            or not isinstance(created_at, datetime)
            or created_at.tzinfo is None
            or (previous_issue is not None and issue <= previous_issue)
            or (previous_draw_date is not None and draw_date <= previous_draw_date)
        ):
            raise IsolatedSearchError("DATA_BOUNDARY_VIOLATION")
        output.append(
            {
                "id": row_id,
                "issue": issue,
                "draw_date": draw_date.isoformat(),
                "red_numbers": list(reds),
                "r1": reds[0],
                "r2": reds[1],
                "r3": reds[2],
                "r4": reds[3],
                "r5": reds[4],
                "r6": reds[5],
                "blue_number": None if blue_raw is None else int(blue_raw),
                "source": source_raw,
                "created_at": created_at.astimezone(UTC).isoformat(
                    timespec="microseconds"
                ),
            }
        )
        seen_ids.add(row_id)
        seen_issues.add(issue)
        previous_issue = issue
        previous_draw_date = draw_date
    if not output:
        raise IsolatedSearchError("ssq_history_empty")
    return tuple(output)


def load_target_issue_projection(
    connection_factory: Callable[[], Any], *, projection_time: datetime
) -> dict[str, Any]:
    from psycopg.rows import dict_row

    if projection_time.tzinfo is None:
        raise IsolatedSearchError("projection_time_not_aware")
    projection_time = projection_time.astimezone(contract.TIMEZONE)
    with (
        connection_factory() as connection,
        connection.cursor(row_factory=dict_row) as cursor,
    ):
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        schema_rows = cursor.execute(HISTORY_SCHEMA_SQL).fetchall()
        raw_rows = cursor.execute(TARGET_PROJECTION_SQL).fetchall()
    schema_digest = validate_history_schema(schema_rows)
    normalized = normalize_projection_rows(raw_rows)
    source_max_issue = str(normalized[-1]["issue"])
    source_max_draw_date = str(normalized[-1]["draw_date"])
    projected = contract.target_issue_projection(
        source_max_issue=source_max_issue,
        source_max_draw_date=source_max_draw_date,
        projection_time=projection_time,
    )
    history_query_digest = contract.domain_digest(
        TARGET_PROJECTION_SQL,
        domain="dehps.m4.isolated-24h-challenger.schema-query.v11",
    )
    history_content_digest = contract.domain_digest(
        normalized,
        domain="dehps.m4.isolated-24h-challenger.ssq-history.v11",
    )
    schedule_contract_digest = contract.domain_digest(
        {
            "timezone": "Asia/Shanghai",
            "weekdays": [1, 3, 6],
            "source_anchor": "latest_audited_issue_plus_draw_date",
            "issue_progression": "sequential_with_draw_date",
            "deadline": "17:00:00",
            "official_draw_time": "21:15:00",
            "boundary": "projection_time<=deadline_selects_candidate",
        },
        domain="dehps.m4.isolated-24h-challenger.target-schedule.v11",
    )
    return {
        **projected,
        "history_query_digest": history_query_digest,
        "history_content_digest": history_content_digest,
        "schema_digest": schema_digest,
        "schedule_contract_digest": schedule_contract_digest,
    }

def normalize_history_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    target_issue: str,
    target_draw_date: date | str | None = None,
) -> tuple[HistoryRow, ...]:
    target_issue = contract.require_issue(target_issue)
    output: list[HistoryRow] = []
    seen: set[str] = set()
    seen_ids: set[int] = set()
    previous_draw_date: date | None = None
    for raw in rows:
        required = {
            "id",
            "issue",
            "draw_date",
            "red_numbers",
            "r1",
            "r2",
            "r3",
            "r4",
            "r5",
            "r6",
            "blue_number",
            "source",
            "created_at",
        }
        if set(raw) != required:
            raise IsolatedSearchError("history_row_schema_changed")
        issue = contract.require_issue(raw["issue"])
        row_id = int(raw["id"])
        if issue >= target_issue or issue in seen or row_id in seen_ids:
            raise IsolatedSearchError("DATA_BOUNDARY_VIOLATION")
        reds = tuple(int(value) for value in raw["red_numbers"])
        scalar_reds = tuple(int(raw[f"r{index}"]) for index in range(1, 7))
        if (
            row_id < 1
            or len(reds) != 6
            or reds != tuple(sorted(reds))
            or len(set(reds)) != 6
            or any(not 1 <= value <= 33 for value in reds)
            or scalar_reds != reds
        ):
            raise IsolatedSearchError("history_red_numbers_invalid")
        draw_date = raw["draw_date"]
        if (
            not isinstance(draw_date, date)
            or issue[:4] != f"{draw_date.year:04d}"
            or (
                previous_draw_date is not None
                and draw_date <= previous_draw_date
            )
        ):
            raise IsolatedSearchError("history_draw_date_invalid")
        blue = int(raw["blue_number"])
        if not 1 <= blue <= 16:
            raise IsolatedSearchError("history_blue_number_invalid")
        source = str(raw["source"] or "")
        created_at = raw["created_at"]
        if (
            not source
            or not isinstance(created_at, datetime)
            or created_at.tzinfo is None
        ):
            raise IsolatedSearchError("history_source_missing")
        output.append(HistoryRow(issue, draw_date, reds, blue, source))
        seen.add(issue)
        seen_ids.add(row_id)
        previous_draw_date = draw_date
    if not output or tuple(item.issue for item in output) != tuple(
        sorted(item.issue for item in output)
    ):
        raise IsolatedSearchError("history_issue_order_invalid")
    projected_draw_date = (
        contract.next_ssq_draw_date(output[-1].draw_date)
        if target_draw_date is None
        else contract.require_draw_date(
            target_draw_date, field="target_draw_date"
        )
    )
    if (
        projected_draw_date <= output[-1].draw_date
        or contract.next_official_issue(
            output[-1].issue, candidate_draw_date=projected_draw_date
        )
        != target_issue
    ):
        raise IsolatedSearchError("history_target_projection_changed")
    return tuple(output)


def history_snapshot_digest(
    rows: Sequence[HistoryRow],
    *,
    target_issue: str,
    target_draw_date: date | str | None = None,
) -> str:
    if not rows:
        raise IsolatedSearchError("history_empty")
    projected_draw_date = (
        contract.next_ssq_draw_date(rows[-1].draw_date)
        if target_draw_date is None
        else contract.require_draw_date(
            target_draw_date, field="target_draw_date"
        )
    )
    return contract.domain_digest(
        {
            "query": HISTORY_SQL,
            "target_issue": target_issue,
            "target_draw_date": projected_draw_date.isoformat(),
            "rows": [
                {
                    "issue": row.issue,
                    "draw_date": row.draw_date.isoformat(),
                    "red_numbers": list(row.red_numbers),
                    "blue_number": row.blue_number,
                    "source": row.source,
                }
                for row in rows
            ],
        },
        domain="dehps.m4.isolated-24h-challenger.history-snapshot.v11",
    )


def load_history(
    connection_factory: Callable[[], Any],
    *,
    target_issue: str,
    target_draw_date: date | str | None = None,
) -> tuple[HistoryRow, ...]:
    """Execute the frozen physical query and normalize its exact row projection."""

    from psycopg.rows import dict_row

    target_issue = contract.require_issue(target_issue)
    with (
        connection_factory() as connection,
        connection.cursor(row_factory=dict_row) as cursor,
    ):
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        schema_rows = cursor.execute(HISTORY_SCHEMA_SQL).fetchall()
        rows = cursor.execute(HISTORY_SQL, {"target_issue": target_issue}).fetchall()
    validate_history_schema(schema_rows)
    return normalize_history_rows(
        rows,
        target_issue=target_issue,
        target_draw_date=target_draw_date,
    )


def _target_matrix(history: Sequence[HistoryRow]) -> np.ndarray:
    targets = np.zeros((len(history), 33), dtype=np.uint8)
    for row_index, row in enumerate(history):
        targets[row_index, np.asarray(row.red_numbers, dtype=np.int16) - 1] = 1
    return targets


def _base_feature_cube(
    history: Sequence[HistoryRow], feature_ids: Sequence[str]
) -> np.ndarray:
    if not history:
        raise IsolatedSearchError("history_empty")
    unknown = set(feature_ids) - set(
        ONE_HOT_FEATURE_IDS + CALENDAR_COMPONENT_IDS + HISTORY_FEATURE_IDS
    )
    if unknown:
        raise IsolatedSearchError(
            "unsupported_base_feature:" + ",".join(sorted(unknown))
        )
    target = _target_matrix(history)
    cube = np.zeros((len(history), 33, len(feature_ids)), dtype=np.float64)
    counts = np.zeros(33, dtype=np.int64)
    last_seen = np.full(33, -1, dtype=np.int64)
    rolling_windows = (5, 12, 30, 60, 120)
    for issue_index, row in enumerate(history):
        for feature_index, feature_id in enumerate(feature_ids):
            if feature_id.startswith("red_number_one_hot_"):
                red = int(feature_id.rsplit("_", 1)[1]) - 1
                cube[issue_index, red, feature_index] = 1.0
            elif feature_id.startswith("known_target_weekday_one_hot_"):
                weekday = {
                    "known_target_weekday_one_hot_tuesday": 1,
                    "known_target_weekday_one_hot_thursday": 3,
                    "known_target_weekday_one_hot_sunday": 6,
                }[feature_id]
                cube[issue_index, :, feature_index] = float(
                    row.draw_date.weekday() == weekday
                )
            elif feature_id.startswith("hit_lag_"):
                lag = int(feature_id.rsplit("_", 1)[1])
                if issue_index >= lag:
                    cube[issue_index, :, feature_index] = target[issue_index - lag]
            elif feature_id == "expanding_frequency":
                if issue_index:
                    cube[issue_index, :, feature_index] = counts / issue_index
            elif feature_id.startswith("rolling_frequency_"):
                window = int(feature_id.rsplit("_", 1)[1])
                if window not in rolling_windows:
                    raise IsolatedSearchError("rolling_window_changed")
                start = max(0, issue_index - window)
                denominator = issue_index - start
                if denominator:
                    cube[issue_index, :, feature_index] = (
                        target[start:issue_index].sum(axis=0) / denominator
                    )
            elif feature_id == "periods_since_seen_divided_by_available_history":
                if issue_index:
                    periods = np.where(
                        last_seen >= 0,
                        issue_index - last_seen - 1,
                        issue_index,
                    )
                    cube[issue_index, :, feature_index] = periods / issue_index
            else:  # pragma: no cover - guarded by the exact set above
                raise IsolatedSearchError("feature_dispatch_changed")
        counts += target[issue_index]
        last_seen[target[issue_index].astype(bool)] = issue_index
    if not np.isfinite(cube).all():
        raise IsolatedSearchError("INVALID_FEATURES")
    return cube


def _feature_cube(
    history: Sequence[HistoryRow], feature_ids: Sequence[str]
) -> np.ndarray:
    expanded_feature_ids = tuple(
        expanded
        for feature_id in feature_ids
        for expanded in (
            CALENDAR_COMPONENT_IDS
            if feature_id == CALENDAR_FEATURE_ID
            else (feature_id,)
        )
    )
    base_ids: set[str] = set()
    parsed: list[tuple[str, tuple[str, ...]]] = []
    for feature_id in expanded_feature_ids:
        if feature_id.startswith("SQUARE(") and feature_id.endswith(")"):
            operand = feature_id[7:-1]
            if operand not in HISTORY_FEATURE_IDS:
                raise IsolatedSearchError("INVALID_FEATURES")
            base_ids.add(operand)
            parsed.append(("SQUARE", (operand,)))
        elif feature_id.startswith("PRODUCT(") and feature_id.endswith(")"):
            operands = tuple(feature_id[8:-1].split(","))
            if (
                len(operands) != 2
                or operands[0] not in ONE_HOT_FEATURE_IDS
                or operands[1] not in HISTORY_FEATURE_IDS
            ):
                raise IsolatedSearchError("INVALID_FEATURES")
            base_ids.update(operands)
            parsed.append(("PRODUCT", operands))
        else:
            base_ids.add(feature_id)
            parsed.append(("IDENTITY", (feature_id,)))
    ordered_base = tuple(sorted(base_ids))
    base_cube = _base_feature_cube(history, ordered_base)
    base_index = {value: index for index, value in enumerate(ordered_base)}
    output = np.empty((len(history), 33, len(parsed)), dtype=np.float64)
    for index, (operator, operands) in enumerate(parsed):
        first = base_cube[:, :, base_index[operands[0]]]
        if operator == "IDENTITY":
            output[:, :, index] = first
        elif operator == "SQUARE":
            output[:, :, index] = np.square(first)
        else:
            output[:, :, index] = first * base_cube[:, :, base_index[operands[1]]]
    if not np.isfinite(output).all():
        raise IsolatedSearchError("INVALID_FEATURES")
    return output


def expanded_feature_ids(feature_ids: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        expanded
        for feature_id in feature_ids
        for expanded in (
            CALENDAR_COMPONENT_IDS
            if feature_id == CALENDAR_FEATURE_ID
            else (feature_id,)
        )
    )


def _base_features() -> tuple[str, ...]:
    return ONE_HOT_FEATURE_IDS


def optional_group_feature_sets() -> tuple[tuple[str, ...], ...]:
    """Frozen whole-group base feature proposals in canonical order.

    Grammar-derived one-step neighbours are created by the adaptive scheduler;
    the base cursor starts from every whole-group combination so it reaches all
    four probability model families within the first 24-hour budget.
    """

    output: list[tuple[str, ...]] = []
    for mask in range(1 << len(OPTIONAL_FEATURE_GROUPS)):
        optional = sorted(
            feature
            for index, group in enumerate(OPTIONAL_FEATURE_GROUPS)
            if mask & (1 << index)
            for feature in group
        )
        output.append((*ONE_HOT_FEATURE_IDS, *optional))
    output.sort(
        key=lambda item: (
            len(item) - len(ONE_HOT_FEATURE_IDS),
            item[len(ONE_HOT_FEATURE_IDS) :],
        )
    )
    if len(output) != 16 or len(set(output)) != 16:
        raise IsolatedSearchError("base_feature_set_identity_changed")
    return tuple(output)


def _abi32_weights(active_count: int) -> tuple[str, ...]:
    if active_count not in range(1, 9):
        raise IsolatedSearchError("feature_abi_active_count_changed")
    quotient, remainder = divmod(20, active_count)
    units = [quotient + int(index < remainder) for index in range(active_count)]
    units.extend([0] * (32 - active_count))
    if sum(units) != 20 or any(value < 0 for value in units):
        raise IsolatedSearchError("feature_abi_weight_lattice_changed")
    return tuple(float(value / 20).hex() for value in units)


def base_configurations(
    *, snapshot_digest: str, source_contract_digest: str
) -> tuple[CandidateConfiguration, ...]:
    snapshot_digest = contract.require_digest(snapshot_digest, field="snapshot_digest")
    source_contract_digest = contract.require_digest(
        source_contract_digest, field="source_contract_digest"
    )
    features = _base_features()
    feature_sets = optional_group_feature_sets()
    output: list[CandidateConfiguration] = []
    for window in TRAINING_WINDOWS:
        for alpha in ("0.25", "1.0", "4.0"):
            output.append(
                CandidateConfiguration(
                    "MARGINAL_STATIC_ALPHA",
                    "STRICT_PRIOR_NUMBER_EVENT_V1",
                    window,
                    features,
                    (("alpha", alpha),),
                    snapshot_digest,
                    source_contract_digest,
                )
            )
        for selected_features in feature_sets:
            for c_value in ("0.01", "0.1", "1.0"):
                output.append(
                    CandidateConfiguration(
                        "LOGISTIC_L2_LIBLINEAR",
                        "STRICT_PRIOR_NUMBER_EVENT_V1",
                        window,
                        selected_features,
                        (
                            ("C", c_value),
                            ("penalty", "l2"),
                            ("solver", "liblinear"),
                            ("tol", "0.0001"),
                            ("max_iter", 1000),
                            ("class_weight", None),
                        ),
                        snapshot_digest,
                        source_contract_digest,
                    )
                )
            for alpha in ("0.5", "1.0", "2.0"):
                output.append(
                    CandidateConfiguration(
                        "BERNOULLI_NAIVE_BAYES",
                        "STRICT_PRIOR_NUMBER_EVENT_V1",
                        window,
                        selected_features,
                        (("alpha", alpha), ("binarize", "0.0")),
                        snapshot_digest,
                        source_contract_digest,
                    )
                )
            for depth in (2, 3):
                for leaf in (50, 100):
                    output.append(
                        CandidateConfiguration(
                            "SHALLOW_PLATT_TREE",
                            "STRICT_PRIOR_NUMBER_EVENT_V1",
                            window,
                            selected_features,
                            (
                                ("max_depth", depth),
                                ("min_samples_leaf", leaf),
                                ("criterion", "log_loss"),
                                ("calibration", "SIGMOID_LAST20_MIN120"),
                            ),
                            snapshot_digest,
                            source_contract_digest,
                        )
                    )
        for count in range(1, 9):
            weights = _abi32_weights(count)
            output.append(
                CandidateConfiguration(
                    "FEATURE_ABI32_LINEAR_RANKER",
                    "FEATURE_ABI32_COMBINATION_V1",
                    window,
                    FEATURE_ABI32_IDS[:count],
                    (("active_component_count", count), ("weight_hex_tuple", weights)),
                    snapshot_digest,
                    source_contract_digest,
                )
            )
    family_index = {family: index for index, family in enumerate(FAMILY_ORDER)}
    window_index = {value: index for index, value in enumerate(TRAINING_WINDOWS)}
    output.sort(
        key=lambda item: (
            family_index[item.family],
            item.representation.encode("utf-8"),
            window_index[item.training_window],
            len(item.ordered_feature_ids),
            item.ordered_feature_ids,
            contract.canonical_json(item.ordered_hyperparameters),
        )
    )
    if len({item.configuration_id for item in output}) != len(output):
        raise IsolatedSearchError("configuration_identity_collision")
    return tuple(output)


def candidate_seed(configuration: CandidateConfiguration, seed_ordinal: int) -> str:
    if seed_ordinal not in contract.SEED_ORDINALS:
        raise IsolatedSearchError("seed_ordinal_invalid")
    preimage = (
        "M4_ISOLATED_24H_V6|CANDIDATE|"
        f"{contract.LINEAGE_ID}|{configuration.configuration_id}|"
        f"{configuration.snapshot_digest}|seed_ordinal_{seed_ordinal}"
    )
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()[:32]


def candidate_cohort_id(configuration: CandidateConfiguration) -> str:
    return contract.domain_digest(
        [
            contract.LINEAGE_ID,
            configuration.configuration_id,
            configuration.snapshot_digest,
            configuration.source_contract_digest,
            contract.domain_digest(
                [
                    candidate_seed(configuration, item)
                    for item in contract.SEED_ORDINALS
                ],
                domain="dehps.m4.isolated-24h-challenger.seed-set.v11",
            ),
        ],
        domain="dehps.m4.isolated-24h-challenger.cohort.v11",
    )


def candidate_job(
    configuration: CandidateConfiguration, seed_ordinal: int
) -> CandidateJob:
    seed_hex = candidate_seed(configuration, seed_ordinal)
    cohort_id = candidate_cohort_id(configuration)
    candidate_id = contract.domain_digest(
        [cohort_id, seed_ordinal],
        domain="dehps.m4.isolated-24h-challenger.candidate.v11",
    )
    parent_candidate_id: str | None = None
    if configuration.parent_configuration_id is not None:
        parent_seed_set_digest = contract.domain_digest(
            [
                hashlib.sha256(
                    (
                        "M4_ISOLATED_24H_V6|CANDIDATE|"
                        f"{contract.LINEAGE_ID}|"
                        f"{configuration.parent_configuration_id}|"
                        f"{configuration.snapshot_digest}|seed_ordinal_{item}"
                    ).encode()
                ).hexdigest()[:32]
                for item in contract.SEED_ORDINALS
            ],
            domain="dehps.m4.isolated-24h-challenger.seed-set.v11",
        )
        parent_cohort_id = contract.domain_digest(
            [
                contract.LINEAGE_ID,
                configuration.parent_configuration_id,
                configuration.snapshot_digest,
                configuration.source_contract_digest,
                parent_seed_set_digest,
            ],
            domain="dehps.m4.isolated-24h-challenger.cohort.v11",
        )
        parent_candidate_id = contract.domain_digest(
            [parent_cohort_id, seed_ordinal],
            domain="dehps.m4.isolated-24h-challenger.candidate.v11",
        )
    return CandidateJob(
        configuration, seed_ordinal, candidate_id, seed_hex, parent_candidate_id
    )


def _configuration_with(
    parent: CandidateConfiguration,
    *,
    training_window: int | str | None = None,
    ordered_feature_ids: Sequence[str] | None = None,
    ordered_hyperparameters: Sequence[tuple[str, Any]] | None = None,
) -> CandidateConfiguration:
    return CandidateConfiguration(
        family=parent.family,
        representation=parent.representation,
        training_window=(
            parent.training_window if training_window is None else training_window
        ),
        ordered_feature_ids=(
            parent.ordered_feature_ids
            if ordered_feature_ids is None
            else tuple(ordered_feature_ids)
        ),
        ordered_hyperparameters=(
            parent.ordered_hyperparameters
            if ordered_hyperparameters is None
            else tuple(ordered_hyperparameters)
        ),
        snapshot_digest=parent.snapshot_digest,
        source_contract_digest=parent.source_contract_digest,
        parent_configuration_id=parent.configuration_id,
    )


def _optional_feature_universe() -> tuple[str, ...]:
    history = tuple(sorted(HISTORY_FEATURE_IDS))
    squares = tuple(
        f"SQUARE({feature_id})"
        for feature_id in sorted(FREQUENCY_FEATURE_IDS + OMISSION_FEATURE_IDS)
    )
    products = tuple(
        f"PRODUCT({one_hot},{history_feature})"
        for one_hot in ONE_HOT_FEATURE_IDS
        for history_feature in history
    )
    values = tuple(
        sorted(
            {
                CALENDAR_FEATURE_ID,
                *HISTORY_FEATURE_IDS,
                *squares,
                *products,
            }
        )
    )
    if len(values) != len(set(values)):
        raise IsolatedSearchError("adaptive_feature_universe_changed")
    return values


def _canonical_probability_features(optional: Iterable[str]) -> tuple[str, ...]:
    optional_set = set(optional)
    if optional_set.intersection(ONE_HOT_FEATURE_IDS):
        raise IsolatedSearchError("adaptive_optional_feature_changed")
    values = (*ONE_HOT_FEATURE_IDS, *sorted(optional_set))
    if len(values) > 64:
        raise IsolatedSearchError("adaptive_feature_limit_changed")
    return values


def adaptive_neighbors(
    parent: CandidateConfiguration,
) -> tuple[CandidateConfiguration, ...]:
    groups: list[list[CandidateConfiguration]] = [[] for _ in range(5)]
    window_index = TRAINING_WINDOWS.index(parent.training_window)
    for adjacent in (window_index - 1, window_index + 1):
        if 0 <= adjacent < len(TRAINING_WINDOWS):
            groups[0].append(
                _configuration_with(
                    parent, training_window=TRAINING_WINDOWS[adjacent]
                )
            )
    parameter_grids: dict[str, tuple[Any, ...]] = {
        "alpha": (
            ("0.25", "1.0", "4.0")
            if parent.family == "MARGINAL_STATIC_ALPHA"
            else (
                ("0.5", "1.0", "2.0")
                if parent.family == "BERNOULLI_NAIVE_BAYES"
                else ()
            )
        ),
        "C": ("0.01", "0.1", "1.0"),
        "max_depth": (2, 3),
        "min_samples_leaf": (50, 100),
    }
    parameters = dict(parent.ordered_hyperparameters)
    for name, value in parent.ordered_hyperparameters:
        grid = parameter_grids.get(name, ())
        if value not in grid:
            continue
        value_index = grid.index(value)
        for adjacent in (value_index - 1, value_index + 1):
            if 0 <= adjacent < len(grid):
                changed = dict(parameters)
                changed[name] = grid[adjacent]
                groups[1].append(
                    _configuration_with(
                        parent,
                        ordered_hyperparameters=tuple(
                            (key, changed[key])
                            for key, _ in parent.ordered_hyperparameters
                        ),
                    )
                )
    if parent.representation == "STRICT_PRIOR_NUMBER_EVENT_V1":
        mandatory = set(ONE_HOT_FEATURE_IDS)
        optional = set(parent.ordered_feature_ids) - mandatory
        for feature_id in sorted(optional, reverse=True):
            groups[2].append(
                _configuration_with(
                    parent,
                    ordered_feature_ids=_canonical_probability_features(
                        optional - {feature_id}
                    ),
                )
            )
        if len(parent.ordered_feature_ids) < 64:
            for feature_id in _optional_feature_universe():
                if feature_id not in parent.ordered_feature_ids:
                    groups[3].append(
                        _configuration_with(
                            parent,
                            ordered_feature_ids=_canonical_probability_features(
                                optional | {feature_id}
                            ),
                        )
                    )
    if parent.family == "FEATURE_ABI32_LINEAR_RANKER":
        weight_hex = tuple(str(value) for value in parameters["weight_hex_tuple"])
        units = [round(float.fromhex(value) * 20) for value in weight_hex]
        if len(units) != 32 or sum(units) != 20 or any(value < 0 for value in units):
            raise IsolatedSearchError("adaptive_abi32_weights_changed")
        for source_index in range(32):
            if units[source_index] <= 0:
                continue
            for destination_index in range(32):
                if source_index == destination_index:
                    continue
                moved = list(units)
                moved[source_index] -= 1
                moved[destination_index] += 1
                active = sum(value > 0 for value in moved)
                if active > 8:
                    continue
                changed = dict(parameters)
                changed["active_component_count"] = active
                changed["weight_hex_tuple"] = tuple(
                    float(value / 20).hex() for value in moved
                )
                groups[4].append(
                    _configuration_with(
                        parent,
                        ordered_feature_ids=tuple(
                            FEATURE_ABI32_IDS[index]
                            for index, value in enumerate(moved)
                            if value > 0
                        ),
                        ordered_hyperparameters=tuple(
                            (key, changed[key])
                            for key, _ in parent.ordered_hyperparameters
                        ),
                    )
                )
    output: list[CandidateConfiguration] = []
    seen: set[str] = set()
    for group in groups:
        for item in sorted(group, key=lambda value: value.configuration_id):
            if item.configuration_id not in seen:
                output.append(item)
                seen.add(item.configuration_id)
    return tuple(output)


def plan_batch(
    configurations: Sequence[CandidateConfiguration], *, cursor: int
) -> tuple[CandidateJob, ...]:
    selected = tuple(
        configurations[cursor : cursor + contract.CONFIGURATIONS_PER_BATCH]
    )
    if len(selected) != contract.CONFIGURATIONS_PER_BATCH:
        raise IsolatedSearchError("SEARCH_SPACE_EXHAUSTED")
    jobs = tuple(
        candidate_job(configuration, seed_ordinal)
        for configuration in selected
        for seed_ordinal in contract.SEED_ORDINALS
    )
    if len(jobs) != contract.ATTEMPTS_PER_BATCH:
        raise IsolatedSearchError("batch_cardinality_changed")
    return jobs


def plan_deterministic_batch(
    configurations: Sequence[CandidateConfiguration],
    *,
    base_cursor: int,
    adaptive_configurations: Sequence[CandidateConfiguration] = (),
    adaptive_cursor: int = 0,
    registered_states: Mapping[str, str] | None = None,
) -> BatchProposal:
    states = dict(registered_states or {})
    selected: list[CandidateConfiguration] = []
    suppressed: list[CandidateJob] = []
    sources: list[str] = []

    def next_novel(source: str) -> CandidateConfiguration | None:
        nonlocal base_cursor, adaptive_cursor
        values = configurations if source == "BASE" else adaptive_configurations
        while True:
            cursor = base_cursor if source == "BASE" else adaptive_cursor
            if cursor >= len(values):
                return None
            configuration = values[cursor]
            if source == "BASE":
                base_cursor += 1
            else:
                adaptive_cursor += 1
            jobs = tuple(
                candidate_job(configuration, ordinal)
                for ordinal in contract.SEED_ORDINALS
            )
            observed = [states.get(job.candidate_id) for job in jobs]
            if all(value is None for value in observed):
                return configuration
            if all(value == "TERMINAL" for value in observed):
                suppressed.extend(jobs)
                continue
            raise IsolatedSearchError("RESUME_INCOMPLETE")

    for source in (
        "BASE",
        "ADAPTIVE_OR_BASE",
        "BASE",
        "ADAPTIVE_OR_BASE",
        "BASE",
        "ADAPTIVE_OR_BASE",
    ):
        configuration = (
            next_novel("BASE")
            if source == "BASE"
            else next_novel("ADAPTIVE") or next_novel("BASE")
        )
        if configuration is None:
            raise IsolatedSearchError("SEARCH_SPACE_EXHAUSTED")
        selected.append(configuration)
        sources.append(
            "ADAPTIVE"
            if source == "ADAPTIVE_OR_BASE"
            and configuration in adaptive_configurations
            else "BASE"
        )
    jobs = tuple(
        candidate_job(configuration, seed_ordinal)
        for configuration in selected
        for seed_ordinal in contract.SEED_ORDINALS
    )
    if len(jobs) != contract.ATTEMPTS_PER_BATCH:
        raise IsolatedSearchError("batch_cardinality_changed")
    return BatchProposal(
        jobs=jobs,
        duplicate_suppressions=tuple(suppressed),
        base_cursor=base_cursor,
        adaptive_cursor=adaptive_cursor,
        slot_sources=tuple(sources),
    )


def deterministic_candidate_result(job: CandidateJob) -> CandidateOutcome:
    """Result-blind deterministic fixture evaluator used for equivalence checks."""

    raw = hashlib.sha256(f"{job.candidate_id}\0{job.seed_hex}".encode()).digest()
    values = tuple((byte - 127.5) / 2550.0 for byte in raw[:30])
    folds = tuple(
        values[index % len(values)] for index in range(contract.OUTER_FOLD_COUNT)
    )
    blocks = tuple(
        math.fsum(folds[offset : offset + 100]) / 100 for offset in (0, 100, 200)
    )
    return CandidateOutcome(
        candidate_id=job.candidate_id,
        configuration_id=job.configuration.configuration_id,
        seed_ordinal=job.seed_ordinal,
        seed_hex=job.seed_hex,
        status="SUCCEEDED",
        primary_mean=math.fsum(folds) / len(folds),
        block_means=blocks,
        fold_values=folds,
    )


def _hyperparameters(configuration: CandidateConfiguration) -> dict[str, Any]:
    return dict(configuration.ordered_hyperparameters)


def _training_start(configuration: CandidateConfiguration, target_index: int) -> int:
    window = configuration.training_window
    if window == "ALL_AVAILABLE":
        return 0
    if not isinstance(window, int) or window not in {900, 1500}:
        raise IsolatedSearchError("training_window_changed")
    return max(0, target_index - window)


def _fold_preprocess(
    train: np.ndarray,
    blind: np.ndarray,
    *,
    feature_ids: Sequence[str],
) -> tuple[np.ndarray, np.ndarray]:
    if (
        train.ndim != 2
        or blind.shape != (33, train.shape[1])
        or train.shape[1] != len(feature_ids)
        or not np.isfinite(train).all()
        or not np.isfinite(blind).all()
    ):
        raise IsolatedSearchError("INVALID_FEATURES")
    transformed_train = train.astype(np.float64, copy=True)
    transformed_blind = blind.astype(np.float64, copy=True)
    continuous = np.asarray(
        [
            not (
                feature_id.startswith(
                    (
                        "red_number_one_hot_",
                        "known_target_weekday_one_hot_",
                        "hit_lag_",
                        "PRODUCT(red_number_one_hot_",
                    )
                )
            )
            for feature_id in feature_ids
        ],
        dtype=bool,
    )
    if continuous.any():
        selected = transformed_train[:, continuous]
        medians = np.median(selected, axis=0)
        scales = np.std(selected, axis=0, ddof=0)
        scales[scales == 0.0] = 1.0
        transformed_train[:, continuous] = (selected - medians) / scales
        transformed_blind[:, continuous] = (
            transformed_blind[:, continuous] - medians
        ) / scales
    if (
        not np.isfinite(transformed_train).all()
        or not np.isfinite(transformed_blind).all()
    ):
        raise IsolatedSearchError("INVALID_FEATURES")
    return transformed_train, transformed_blind


def _probability_model_fold(
    *,
    job: CandidateJob,
    feature_cube: np.ndarray,
    target_matrix: np.ndarray,
    target_index: int,
) -> tuple[float, ...]:
    configuration = job.configuration
    internal_feature_ids = expanded_feature_ids(configuration.ordered_feature_ids)
    params = _hyperparameters(configuration)
    train_start = _training_start(configuration, target_index)
    issue_count = target_index - train_start
    if issue_count < 1:
        raise IsolatedSearchError("insufficient_training_history")
    if configuration.family == "MARGINAL_STATIC_ALPHA":
        alpha = float(params["alpha"])
        counts = target_matrix[train_start:target_index].sum(axis=0)
        probabilities = (counts + alpha * (6.0 / 33.0)) / (issue_count + alpha)
    else:
        train = feature_cube[train_start:target_index].reshape(
            issue_count * 33, feature_cube.shape[2]
        )
        blind = feature_cube[target_index]
        targets = target_matrix[train_start:target_index].reshape(issue_count * 33)
        if set(np.unique(targets)) != {0, 1}:
            raise IsolatedSearchError("insufficient_class_variation")
        sample_weight = np.full(targets.shape[0], 1.0 / 33.0, dtype=np.float64)
        seed = int(job.seed_hex, 16) & 0xFFFFFFFF
        if configuration.family == "SHALLOW_PLATT_TREE":
            calibration_count = max(120, math.ceil(0.2 * issue_count))
            if calibration_count >= issue_count:
                raise IsolatedSearchError("insufficient_training_history")
            model_issue_count = issue_count - calibration_count
            split = model_issue_count * 33
            model_train, transformed_blind = _fold_preprocess(
                train[:split], blind, feature_ids=internal_feature_ids
            )
            # The frozen model preprocessor is fit only on the model interval;
            # apply those exact median/scale values to the held-out calibration
            # interval by reusing the already transformed full matrix formula.
            raw_model = train[:split]
            raw_calibration = train[split:]
            continuous = np.asarray(
                [
                    not (
                        name.startswith(
                            (
                                "red_number_one_hot_",
                                "known_target_weekday_one_hot_",
                                "hit_lag_",
                                "PRODUCT(red_number_one_hot_",
                            )
                        )
                    )
                    for name in internal_feature_ids
                ],
                dtype=bool,
            )
            calibration_train = raw_calibration.astype(np.float64, copy=True)
            if continuous.any():
                medians = np.median(raw_model[:, continuous], axis=0)
                scales = np.std(raw_model[:, continuous], axis=0, ddof=0)
                scales[scales == 0.0] = 1.0
                calibration_train[:, continuous] = (
                    calibration_train[:, continuous] - medians
                ) / scales
            tree = DecisionTreeClassifier(
                criterion="log_loss",
                max_depth=int(params["max_depth"]),
                min_samples_leaf=int(params["min_samples_leaf"]),
                random_state=seed,
            )
            tree.fit(
                model_train,
                targets[:split],
                sample_weight=sample_weight[:split],
            )
            calibrated = CalibratedClassifierCV(FrozenEstimator(tree), method="sigmoid")
            calibrated.fit(
                calibration_train,
                targets[split:],
                sample_weight=sample_weight[split:],
            )
            probabilities = calibrated.predict_proba(transformed_blind)[:, 1]
        else:
            transformed_train, transformed_blind = _fold_preprocess(
                train, blind, feature_ids=internal_feature_ids
            )
            if configuration.family == "LOGISTIC_L2_LIBLINEAR":
                model = LogisticRegression(
                    penalty="l2",
                    C=float(params["C"]),
                    class_weight=None,
                    solver="liblinear",
                    max_iter=1000,
                    tol=0.0001,
                    random_state=seed,
                )
                model.fit(
                    transformed_train,
                    targets,
                    sample_weight=sample_weight,
                )
            elif configuration.family == "BERNOULLI_NAIVE_BAYES":
                model = BernoulliNB(alpha=float(params["alpha"]), binarize=0.0)
                model.fit(
                    transformed_train,
                    targets,
                    sample_weight=sample_weight,
                )
            else:
                raise IsolatedSearchError("probability_family_changed")
            probabilities = model.predict_proba(transformed_blind)[:, 1]
    clipped = np.clip(
        np.asarray(probabilities, dtype=np.float64),
        PROBABILITY_CLIP[0],
        PROBABILITY_CLIP[1],
    )
    if clipped.shape != (33,) or not np.isfinite(clipped).all():
        raise IsolatedSearchError("NONFINITE_SCORE")
    return tuple(float(value) for value in clipped)


def _evaluate_fixture(job: CandidateJob) -> CandidateOutcome:
    return deterministic_candidate_result(job)


def execute_jobs(
    jobs: Sequence[CandidateJob],
    *,
    worker_count: int,
    evaluator: Callable[[CandidateJob], CandidateOutcome] = _evaluate_fixture,
) -> tuple[CandidateOutcome, ...]:
    if worker_count not in {1, contract.WORKER_COUNT}:
        raise IsolatedSearchError("worker_count_not_frozen")
    if len(jobs) != contract.ATTEMPTS_PER_BATCH:
        raise IsolatedSearchError("batch_job_count_changed")
    if worker_count == 1:
        results = [evaluator(job) for job in jobs]
    else:
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            results = list(executor.map(evaluator, jobs, chunksize=1))
    by_id = {item.candidate_id: item for item in results}
    if len(by_id) != len(jobs):
        raise IsolatedSearchError("candidate_result_identity_changed")
    return tuple(by_id[job.candidate_id] for job in jobs)


def result_bytes(results: Sequence[CandidateOutcome]) -> bytes:
    return contract.canonical_json(
        [
            {
                "candidate_id": item.candidate_id,
                "configuration_id": item.configuration_id,
                "seed_ordinal": item.seed_ordinal,
                "seed_hex": item.seed_hex,
                "status": item.status,
                "primary_mean": item.primary_mean.hex(),
                "block_means": [value.hex() for value in item.block_means],
                "fold_values": [value.hex() for value in item.fold_values],
                "error_code": item.error_code,
            }
            for item in results
        ]
    ).encode("ascii")


def aggregate_seed_cohort(results: Sequence[CandidateOutcome]) -> dict[str, Any]:
    ordered = tuple(sorted(results, key=lambda item: item.seed_ordinal))
    if tuple(item.seed_ordinal for item in ordered) != contract.SEED_ORDINALS:
        raise IsolatedSearchError("SEED_COHORT_INCOMPLETE")
    if len({item.configuration_id for item in ordered}) != 1 or any(
        item.status != "SUCCEEDED" for item in ordered
    ):
        raise IsolatedSearchError("SEED_COHORT_INCOMPLETE")
    averaged = tuple(
        math.fsum(item.fold_values[index] for item in ordered) / 3.0
        for index in range(contract.OUTER_FOLD_COUNT)
    )
    seed_gate = all(
        item.primary_mean > 0 and all(block >= -0.02 for block in item.block_means)
        for item in ordered
    )
    return {
        "configuration_id": ordered[0].configuration_id,
        "ordered_candidate_ids": [item.candidate_id for item in ordered],
        "averaged_fold_values_hex": [item.hex() for item in averaged],
        "primary_mean": math.fsum(averaged) / len(averaged),
        "seed_gate_pass": seed_gate,
        "selected_seed_ordinal": 0,
    }


def legal_red_combinations() -> Iterable[tuple[int, ...]]:
    return itertools.combinations(range(1, 34), 6)


@lru_cache(maxsize=1)
def legal_combination_matrix() -> np.ndarray:
    flat = np.fromiter(
        itertools.chain.from_iterable(legal_red_combinations()),
        dtype=np.uint8,
        count=contract.LEGAL_RED_COMBINATION_COUNT * 6,
    )
    matrix = flat.reshape(contract.LEGAL_RED_COMBINATION_COUNT, 6)
    matrix.flags.writeable = False
    return matrix


def combination_rank_zero_based(red_tuple: Sequence[int]) -> int:
    candidate = tuple(int(value) for value in red_tuple)
    if (
        len(candidate) != 6
        or candidate != tuple(sorted(candidate))
        or len(set(candidate)) != 6
        or any(not 1 <= value <= 33 for value in candidate)
    ):
        raise IsolatedSearchError("realized_red_tuple_invalid")
    rank = 0
    lower = 1
    for position, selected in enumerate(candidate):
        for value in range(lower, selected):
            rank += math.comb(33 - value, 5 - position)
        lower = selected + 1
    return rank


def _probability_log_odds(probabilities: Sequence[float]) -> np.ndarray:
    vector = np.asarray(probabilities, dtype=np.float64)
    if (
        vector.shape != (33,)
        or not np.isfinite(vector).all()
        or np.any(vector < PROBABILITY_CLIP[0])
        or np.any(vector > PROBABILITY_CLIP[1])
    ):
        raise IsolatedSearchError("probability_vector_invalid")
    return np.log2(vector) - np.log2(1.0 - vector)


def probability_exact_rank(
    realized: Sequence[int], probabilities: Sequence[float]
) -> int:
    """Exact total-order rank with a vectorized safe-away / serial-near split."""

    realized_tuple = tuple(int(value) for value in realized)
    realized_lex_index = combination_rank_zero_based(realized_tuple)
    log_odds = _probability_log_odds(probabilities)
    matrix = legal_combination_matrix()
    approximate = np.zeros(matrix.shape[0], dtype=np.float64)
    for column in range(6):
        approximate += log_odds[matrix[:, column] - 1]
    observed = math.fsum(log_odds[value - 1] for value in realized_tuple)
    tolerance = (
        32.0
        * np.finfo(np.float64).eps
        * max(1.0, math.fsum(abs(log_odds[value - 1]) for value in realized_tuple))
    )
    safely_before = int(np.count_nonzero(approximate > observed + tolerance))
    near = np.flatnonzero(np.abs(approximate - observed) <= tolerance)
    exact_near_before = 0
    for index in near:
        values = matrix[int(index)]
        score = math.fsum(log_odds[int(value) - 1] for value in values)
        if score > observed or (score == observed and int(index) < realized_lex_index):
            exact_near_before += 1
    rank = safely_before + exact_near_before + 1
    if not 1 <= rank <= contract.LEGAL_RED_COMBINATION_COUNT:
        raise IsolatedSearchError("probability_rank_invalid")
    return rank


def probability_top_red_combinations(
    probabilities: Sequence[float], *, count: int = contract.PORTFOLIO_SIZE
) -> tuple[tuple[int, ...], ...]:
    if count != contract.PORTFOLIO_SIZE:
        raise IsolatedSearchError("top100_count_changed")
    log_odds = _probability_log_odds(probabilities)
    matrix = legal_combination_matrix()
    scores = np.zeros(matrix.shape[0], dtype=np.float64)
    for column in range(6):
        scores += log_odds[matrix[:, column] - 1]
    # Vectorized sums are used only to form a mathematically safe superset.  The
    # final order is the frozen serial math.fsum order.  With six addends, the
    # conservative symmetric bound below dominates any reduction-order error;
    # every row capable of crossing the approximate kth boundary is replayed.
    tolerance = (
        32.0
        * np.finfo(np.float64).eps
        * max(
            1.0,
            math.fsum(
                sorted((abs(float(value)) for value in log_odds), reverse=True)[:6]
            ),
        )
    )
    kth = float(np.partition(scores, -count)[-count])
    boundary = np.flatnonzero(scores >= kth - 2.0 * tolerance)
    exact = sorted(
        (
            (
                -math.fsum(log_odds[int(value) - 1] for value in matrix[int(index)]),
                int(index),
            )
            for index in boundary
        ),
        key=lambda item: (item[0], item[1]),
    )[:count]
    output = tuple(tuple(int(value) for value in matrix[index]) for _, index in exact)
    if len(output) != count or len(set(output)) != count:
        raise IsolatedSearchError("top100_identity_changed")
    return output


def probability_combination_score(
    red_tuple: tuple[int, ...], probabilities: Sequence[float]
) -> float:
    if len(probabilities) != 33:
        raise IsolatedSearchError("probability_vector_size_changed")
    selected = set(red_tuple)
    return math.fsum(
        math.log2(probabilities[index - 1])
        if index in selected
        else math.log2(1.0 - probabilities[index - 1])
        for index in range(1, 34)
    )


def top_red_combinations(
    score: Callable[[tuple[int, ...]], float], *, count: int = contract.PORTFOLIO_SIZE
) -> tuple[tuple[int, ...], ...]:
    if count != contract.PORTFOLIO_SIZE:
        raise IsolatedSearchError("top100_count_changed")
    ranked = heapq.nsmallest(
        count,
        (
            (-float(score(candidate)), candidate)
            for candidate in legal_red_combinations()
        ),
        key=lambda item: (item[0], item[1]),
    )
    if len(ranked) != count or len({item[1] for item in ranked}) != count:
        raise IsolatedSearchError("top100_identity_changed")
    return tuple(item[1] for item in ranked)


def realized_exact_rank(
    realized: tuple[int, ...], score: Callable[[tuple[int, ...]], float]
) -> int:
    realized = tuple(realized)
    if realized not in set(legal_red_combinations()):
        raise IsolatedSearchError("realized_red_tuple_invalid")
    observed = float(score(realized))
    before = 0
    for candidate in legal_red_combinations():
        candidate_score = float(score(candidate))
        if candidate_score > observed or (
            candidate_score == observed and candidate < realized
        ):
            before += 1
    return before + 1


def centered_rank_percentile(rank: int) -> float:
    if not 1 <= rank <= contract.LEGAL_RED_COMBINATION_COUNT:
        raise IsolatedSearchError("rank_outside_legal_space")
    return 0.5 - (rank - 1) / (contract.LEGAL_RED_COMBINATION_COUNT - 1)


def _abi32_rank(
    *,
    history: Sequence[HistoryRow],
    configuration: CandidateConfiguration,
    target_index: int,
) -> int:
    params = _hyperparameters(configuration)
    weight_hex = tuple(params["weight_hex_tuple"])
    if len(weight_hex) != 32:
        raise IsolatedSearchError("feature_abi_weight_count_changed")
    weights = tuple(float.fromhex(value) for value in weight_hex)
    if any(
        value < 0 or not math.isfinite(value) for value in weights
    ) or not math.isclose(math.fsum(weights), 1.0, rel_tol=0.0, abs_tol=1e-15):
        raise IsolatedSearchError("feature_abi_weight_lattice_changed")
    start = _training_start(configuration, target_index)
    training = [
        (row.issue, row.draw_date, row.red_numbers)
        for row in history[start:target_index]
    ]
    if not training:
        raise IsolatedSearchError("insufficient_training_history")
    stats = train_frequency_stats(
        training,
        target_draw_date=history[target_index].draw_date,
    )
    config_values = dict(zip(FEATURE_ABI32_WEIGHT_FIELDS, weights, strict=True))
    ranker_config = FrequencyRankerConfig(**config_values)
    score = lambda candidate: float(
        score_frequency_candidate(candidate, stats, ranker_config)["score"]
    )
    return realized_exact_rank(history[target_index].red_numbers, score)


def candidate_prediction_probabilities(
    job: CandidateJob,
    history: Sequence[HistoryRow],
    *,
    target_issue: str,
    target_draw_date: date | str | None = None,
) -> tuple[float, ...]:
    target_issue = contract.require_issue(target_issue)
    if not history:
        raise IsolatedSearchError("prediction_target_boundary_changed")
    projected_draw_date = (
        contract.next_ssq_draw_date(history[-1].draw_date)
        if target_draw_date is None
        else contract.require_draw_date(
            target_draw_date, field="target_draw_date"
        )
    )
    if (
        contract.next_official_issue(
            history[-1].issue, candidate_draw_date=projected_draw_date
        )
        != target_issue
    ):
        raise IsolatedSearchError("prediction_target_boundary_changed")
    if job.configuration.family == "FEATURE_ABI32_LINEAR_RANKER":
        raise IsolatedSearchError("feature_abi_prediction_uses_score_surface")
    sentinel = HistoryRow(
        issue=target_issue,
        draw_date=projected_draw_date,
        red_numbers=(1, 2, 3, 4, 5, 6),
        blue_number=1,
        source="TARGET_BLIND_SENTINEL_NOT_OBSERVED",
    )
    extended = (*history, sentinel)
    cube = _feature_cube(extended, job.configuration.ordered_feature_ids)
    targets = _target_matrix(extended)
    return _probability_model_fold(
        job=job,
        feature_cube=cube,
        target_matrix=targets,
        target_index=len(history),
    )


def candidate_prediction_score(
    job: CandidateJob,
    history: Sequence[HistoryRow],
    *,
    target_issue: str,
    target_draw_date: date | str | None = None,
) -> Callable[[tuple[int, ...]], float]:
    if job.configuration.family != "FEATURE_ABI32_LINEAR_RANKER":
        probabilities = candidate_prediction_probabilities(
            job,
            history,
            target_issue=target_issue,
            target_draw_date=target_draw_date,
        )
        return lambda candidate: probability_combination_score(candidate, probabilities)
    params = _hyperparameters(job.configuration)
    weights = tuple(float.fromhex(value) for value in params["weight_hex_tuple"])
    if len(weights) != 32:
        raise IsolatedSearchError("feature_abi_weight_count_changed")
    start = _training_start(job.configuration, len(history))
    training = [(row.issue, row.draw_date, row.red_numbers) for row in history[start:]]
    projected_draw_date = (
        contract.next_ssq_draw_date(history[-1].draw_date)
        if target_draw_date is None
        else contract.require_draw_date(
            target_draw_date, field="target_draw_date"
        )
    )
    stats = train_frequency_stats(
        training,
        target_draw_date=projected_draw_date,
    )
    ranker_config = FrequencyRankerConfig(
        **dict(zip(FEATURE_ABI32_WEIGHT_FIELDS, weights, strict=True))
    )
    return lambda candidate: float(
        score_frequency_candidate(candidate, stats, ranker_config)["score"]
    )


def evaluate_candidate_history(
    job: CandidateJob, history: Sequence[HistoryRow]
) -> CandidateOutcome:
    if len(history) <= contract.OUTER_FOLD_COUNT:
        raise IsolatedSearchError("insufficient_outer_history")
    configuration = job.configuration
    if (
        history_snapshot_digest(
            history,
            target_issue=contract.next_official_issue(
                history[-1].issue,
                candidate_draw_date=contract.next_ssq_draw_date(
                    history[-1].draw_date
                ),
            ),
            target_draw_date=contract.next_ssq_draw_date(history[-1].draw_date),
        )
        != configuration.snapshot_digest
    ):
        raise IsolatedSearchError("SNAPSHOT_DIGEST_MISMATCH")
    target_indices = range(
        len(history) - contract.OUTER_FOLD_COUNT,
        len(history),
    )
    feature_cube: np.ndarray | None = None
    target_matrix: np.ndarray | None = None
    if configuration.family != "FEATURE_ABI32_LINEAR_RANKER":
        feature_cube = _feature_cube(history, configuration.ordered_feature_ids)
        target_matrix = _target_matrix(history)
    folds: list[float] = []
    for target_index in target_indices:
        if configuration.family == "FEATURE_ABI32_LINEAR_RANKER":
            rank = _abi32_rank(
                history=history,
                configuration=configuration,
                target_index=target_index,
            )
        else:
            assert feature_cube is not None and target_matrix is not None
            probabilities = _probability_model_fold(
                job=job,
                feature_cube=feature_cube,
                target_matrix=target_matrix,
                target_index=target_index,
            )
            rank = probability_exact_rank(
                history[target_index].red_numbers,
                probabilities,
            )
        folds.append(centered_rank_percentile(rank))
    fold_values = tuple(folds)
    blocks = tuple(
        math.fsum(fold_values[offset : offset + 100]) / 100.0
        for offset in (0, 100, 200)
    )
    primary = math.fsum(fold_values) / contract.OUTER_FOLD_COUNT
    if (
        len(fold_values) != contract.OUTER_FOLD_COUNT
        or not math.isfinite(primary)
        or any(not math.isfinite(value) for value in (*blocks, *fold_values))
    ):
        raise IsolatedSearchError("NONFINITE_SCORE")
    return CandidateOutcome(
        candidate_id=job.candidate_id,
        configuration_id=configuration.configuration_id,
        seed_ordinal=job.seed_ordinal,
        seed_hex=job.seed_hex,
        status="SUCCEEDED",
        primary_mean=primary,
        block_means=blocks,
        fold_values=fold_values,
    )


def _evaluate_history_payload(
    payload: tuple[CandidateJob, tuple[HistoryRow, ...]],
) -> CandidateOutcome:
    job, history = payload
    try:
        return evaluate_candidate_history(job, history)
    except IsolatedSearchError as exc:
        raw_code = str(exc)
        if raw_code in {"SNAPSHOT_DIGEST_MISMATCH", "DATA_BOUNDARY_VIOLATION"}:
            error_code = "SOURCE_IDENTITY_INVALID"
        elif raw_code == "NONFINITE_SCORE":
            error_code = raw_code
        else:
            error_code = "INVALID_FEATURES"
        return CandidateOutcome(
            candidate_id=job.candidate_id,
            configuration_id=job.configuration.configuration_id,
            seed_ordinal=job.seed_ordinal,
            seed_hex=job.seed_hex,
            status="FAILED",
            primary_mean=0.0,
            block_means=(0.0, 0.0, 0.0),
            fold_values=(),
            error_code=error_code,
        )


def _evaluate_history_payload_with_ack(
    payload: tuple[CandidateJob, tuple[HistoryRow, ...]], ack_queue: Any
) -> CandidateOutcome:
    """Acknowledge entry into the worker before reading scientific inputs."""

    ack_queue.put(payload[0].candidate_id)
    return _evaluate_history_payload(payload)


def worker_rss_observation(processes: Sequence[Any]) -> dict[str, Any]:
    """Read exact per-worker RSS without serializing scientific outputs."""

    samples: list[dict[str, int]] = []
    unreadable_live_pids: list[int] = []
    for process in processes:
        pid = int(getattr(process, "pid", 0) or 0)
        if pid < 1 or not process.is_alive():
            continue
        try:
            status = Path(f"/proc/{pid}/status").read_text(encoding="ascii")
            values = [
                line.split()
                for line in status.splitlines()
                if line.startswith("VmRSS:")
            ]
            if len(values) != 1 or len(values[0]) != 3 or values[0][2] != "kB":
                raise ValueError("worker_rss_shape_changed")
            rss_bytes = int(values[0][1]) * 1024
            if rss_bytes < 0:
                raise ValueError("worker_rss_negative")
        except (OSError, ValueError):
            unreadable_live_pids.append(pid)
            continue
        samples.append({"pid": pid, "rss_bytes": rss_bytes})
    maximum = max((item["rss_bytes"] for item in samples), default=0)
    return {
        "query_ok": not unreadable_live_pids,
        "sample_count": len(samples),
        "maximum_rss_bytes": maximum,
        "soft_limit_exceeded": maximum >= contract.WORKER_RSS_SOFT_LIMIT_BYTES,
        "hard_limit_exceeded": (
            bool(unreadable_live_pids)
            or maximum >= contract.WORKER_RSS_HARD_LIMIT_BYTES
        ),
        "unreadable_live_pids": unreadable_live_pids,
    }


def _drain_worker_acknowledgements(
    acknowledgement_queue: Any,
    lease_by_id: Mapping[str, tuple[CandidateJob, int]],
    acknowledged_ids: set[str],
) -> tuple[tuple[CandidateJob, int], ...]:
    newly_acknowledged: list[tuple[CandidateJob, int]] = []
    while True:
        try:
            candidate_id = str(acknowledgement_queue.get_nowait())
        except Empty:
            break
        if candidate_id not in lease_by_id or candidate_id in acknowledged_ids:
            raise IsolatedSearchError("worker_start_ack_identity_changed")
        acknowledged_ids.add(candidate_id)
        newly_acknowledged.append(lease_by_id[candidate_id])
    return tuple(newly_acknowledged)


def execute_history_jobs(
    jobs: Sequence[CandidateJob],
    *,
    history: Sequence[HistoryRow],
    worker_count: int,
    activity_probe: Callable[[], bool] | None = None,
) -> tuple[CandidateOutcome, ...]:
    if worker_count not in {1, contract.WORKER_COUNT}:
        raise IsolatedSearchError("worker_count_not_frozen")
    if len(jobs) != contract.ATTEMPTS_PER_BATCH:
        raise IsolatedSearchError("batch_job_count_changed")
    frozen_history = tuple(history)
    payloads = tuple((job, frozen_history) for job in jobs)
    if worker_count == 1:
        results = [_evaluate_history_payload(payload) for payload in payloads]
    else:
        executor = ProcessPoolExecutor(max_workers=worker_count)
        futures = {
            executor.submit(_evaluate_history_payload, payload): payload[0]
            for payload in payloads
        }
        pending = set(futures)
        results = []
        preempted = False
        try:
            while pending:
                if activity_probe is not None and not activity_probe():
                    preempted = True
                    processes = tuple(executor._processes.values())
                    for process in processes:
                        if process.is_alive():
                            process.terminate()
                    deadline = (
                        time.monotonic()
                        + contract.FORMAL_P3_KILL_GRACE_SECONDS
                    )
                    for process in processes:
                        process.join(max(0.0, deadline - time.monotonic()))
                    for process in processes:
                        if process.is_alive():
                            process.kill()
                            process.join()
                    raise IsolatedSearchError("P3_PREEMPTED")
                done, pending = wait(
                    pending,
                    timeout=contract.FORMAL_P3_POLL_SECONDS,
                    return_when=FIRST_COMPLETED,
                )
                results.extend(future.result() for future in done)
        finally:
            executor.shutdown(wait=not preempted, cancel_futures=preempted)
    by_id = {item.candidate_id: item for item in results}
    if len(by_id) != len(jobs):
        raise IsolatedSearchError("candidate_result_identity_changed")
    return tuple(by_id[job.candidate_id] for job in jobs)


def execute_history_jobs_with_retries(
    jobs: Sequence[CandidateJob],
    *,
    history: Sequence[HistoryRow],
    activity_probe: Callable[[], bool],
    quiescence_waiter: Callable[[], bool],
    initial_outcomes: Mapping[str, CandidateOutcome] | None = None,
    initial_attempts: Sequence[CandidateAttemptOutcome] = (),
    initial_retry_ordinals: Mapping[str, int] | None = None,
    on_lease: Callable[[tuple[tuple[CandidateJob, int], ...]], None] | None = None,
    on_started: Callable[[tuple[tuple[CandidateJob, int], ...]], None] | None = None,
    on_unstarted: Callable[[tuple[tuple[CandidateJob, int], ...]], None] | None = None,
    on_heartbeat: Callable[[tuple[tuple[CandidateJob, int], ...]], None]
    | None = None,
    on_attempt: Callable[
        [CandidateJob, CandidateAttemptOutcome, CandidateOutcome | None], None
    ]
    | None = None,
    preemption_reason_probe: Callable[[], str | None] | None = None,
) -> tuple[tuple[CandidateOutcome, ...], tuple[CandidateAttemptOutcome, ...]]:
    if len(jobs) != contract.ATTEMPTS_PER_BATCH:
        raise IsolatedSearchError("batch_job_count_changed")
    frozen_history = tuple(history)
    job_by_id = {job.candidate_id: job for job in jobs}
    if len(job_by_id) != len(jobs):
        raise IsolatedSearchError("batch_candidate_identity_changed")
    terminal = dict(initial_outcomes or {})
    if not set(terminal).issubset(job_by_id):
        raise IsolatedSearchError("resume_outcome_identity_changed")
    attempts = list(initial_attempts)
    retry_by_id = {
        candidate_id: int(ordinal)
        for candidate_id, ordinal in dict(initial_retry_ordinals or {}).items()
    }
    if not set(retry_by_id).issubset(job_by_id) or any(
        not 0 <= ordinal <= 2 for ordinal in retry_by_id.values()
    ):
        raise IsolatedSearchError("resume_retry_ordinal_changed")
    pending = {
        job.candidate_id: job for job in jobs if job.candidate_id not in terminal
    }
    while pending:
        round_jobs = tuple(pending[key] for key in sorted(pending))
        leases = tuple(
            (job, retry_by_id.get(job.candidate_id, 0)) for job in round_jobs
        )
        if on_lease is not None:
            on_lease(leases)
        executor = ProcessPoolExecutor(
            max_workers=min(contract.WORKER_COUNT, len(round_jobs))
        )
        manager = Manager()
        acknowledgement_queue = manager.Queue()
        future_by_id = {
            executor.submit(
                _evaluate_history_payload_with_ack,
                (job, frozen_history),
                acknowledgement_queue,
            ): job
            for job in round_jobs
        }
        futures = set(future_by_id)
        lease_by_id = {job.candidate_id: (job, retry) for job, retry in leases}
        acknowledged_ids: set[str] = set()
        round_failure: str | None = None
        started = time.monotonic()
        last_heartbeat = started

        try:
            while futures:
                newly_acknowledged = _drain_worker_acknowledgements(
                    acknowledgement_queue, lease_by_id, acknowledged_ids
                )
                if newly_acknowledged and on_started is not None:
                    on_started(newly_acknowledged)
                reason = (
                    preemption_reason_probe()
                    if preemption_reason_probe is not None
                    else (None if activity_probe() else "P3_PREEMPTED")
                )
                if reason is not None:
                    round_failure = reason
                    break
                rss = worker_rss_observation(tuple(executor._processes.values()))
                if rss["hard_limit_exceeded"]:
                    round_failure = "WORKER_PROCESS_CRASH"
                    break
                if time.monotonic() - started >= contract.WALL_TIMEOUT_SECONDS:
                    round_failure = "WALL_TIMEOUT"
                    break
                if (
                    on_heartbeat is not None
                    and acknowledged_ids
                    and time.monotonic() - last_heartbeat
                    >= contract.LEASE_HEARTBEAT_SECONDS
                ):
                    on_heartbeat(
                        tuple(lease_by_id[item] for item in sorted(acknowledged_ids))
                    )
                    last_heartbeat = time.monotonic()
                done, futures = wait(
                    futures,
                    timeout=contract.FORMAL_P3_POLL_SECONDS,
                    return_when=FIRST_COMPLETED,
                )
                for future in sorted(
                    done,
                    key=lambda item: next(
                        index
                        for index, candidate in enumerate(round_jobs)
                        if candidate.candidate_id == future_by_id[item].candidate_id
                    ),
                ):
                    newly_acknowledged = _drain_worker_acknowledgements(
                        acknowledgement_queue, lease_by_id, acknowledged_ids
                    )
                    if newly_acknowledged and on_started is not None:
                        on_started(newly_acknowledged)
                    job = future_by_id[future]
                    if job.candidate_id not in acknowledged_ids:
                        round_failure = "WORKER_PROCESS_CRASH"
                        break
                    try:
                        outcome = future.result()
                    except Exception:  # noqa: BLE001 - worker crash is typed below
                        round_failure = "WORKER_PROCESS_CRASH"
                        break
                    retry_ordinal = retry_by_id.get(job.candidate_id, 0)
                    trace = CandidateAttemptOutcome(
                        candidate_id=job.candidate_id,
                        retry_ordinal=retry_ordinal,
                        status=outcome.status,
                        reason=outcome.error_code,
                    )
                    attempts.append(trace)
                    if on_attempt is not None:
                        on_attempt(job, trace, outcome)
                    retryable = outcome.error_code in {
                        "P3_PREEMPTED",
                        "WORKER_PROCESS_CRASH",
                        "WALL_TIMEOUT",
                    }
                    if outcome.status == "SUCCEEDED" or not retryable:
                        terminal[job.candidate_id] = outcome
                        pending.pop(job.candidate_id, None)
                    elif retry_ordinal < 2:
                        retry_by_id[job.candidate_id] = retry_ordinal + 1
                    else:
                        terminal[job.candidate_id] = outcome
                        pending.pop(job.candidate_id, None)
                if round_failure is not None:
                    break
        finally:
            if round_failure is not None:
                processes = tuple(executor._processes.values())
                for process in processes:
                    if process.is_alive():
                        process.terminate()
                deadline = time.monotonic() + contract.FORMAL_P3_KILL_GRACE_SECONDS
                for process in processes:
                    process.join(max(0.0, deadline - time.monotonic()))
                for process in processes:
                    if process.is_alive():
                        process.kill()
                        process.join()
                executor.shutdown(wait=False, cancel_futures=True)
            else:
                executor.shutdown(wait=True)
            late_acknowledgements = _drain_worker_acknowledgements(
                acknowledgement_queue, lease_by_id, acknowledged_ids
            )
            if late_acknowledgements and on_started is not None:
                on_started(late_acknowledgements)
            manager.shutdown()
        if round_failure is not None:
            retryable_failure = round_failure in {
                "P3_PREEMPTED",
                "WORKER_PROCESS_CRASH",
                "WALL_TIMEOUT",
            }
            unstarted = tuple(
                lease_by_id[candidate_id]
                for candidate_id in sorted(set(lease_by_id) - acknowledged_ids)
            )
            if unstarted and on_unstarted is not None:
                on_unstarted(unstarted)
            for candidate_id in sorted(acknowledged_ids):
                if candidate_id not in pending:
                    continue
                job = pending[candidate_id]
                retry_ordinal = retry_by_id.get(job.candidate_id, 0)
                trace = CandidateAttemptOutcome(
                    candidate_id=job.candidate_id,
                    retry_ordinal=retry_ordinal,
                    status="FAILED",
                    reason=round_failure,
                )
                attempts.append(trace)
                if on_attempt is not None:
                    on_attempt(job, trace, None)
                if retryable_failure and retry_ordinal < 2:
                    retry_by_id[job.candidate_id] = retry_ordinal + 1
                    continue
                terminal[job.candidate_id] = CandidateOutcome(
                    candidate_id=job.candidate_id,
                    configuration_id=job.configuration.configuration_id,
                    seed_ordinal=job.seed_ordinal,
                    seed_hex=job.seed_hex,
                    status="FAILED",
                    primary_mean=0.0,
                    block_means=(0.0, 0.0, 0.0),
                    fold_values=(),
                    error_code=round_failure,
                )
                pending.pop(job.candidate_id, None)
            if pending and (
                not retryable_failure or not quiescence_waiter()
            ):
                raise IsolatedSearchError("RESOURCE_GUARD_TRIGGERED")
    if pending or set(terminal) != {job.candidate_id for job in jobs}:
        raise IsolatedSearchError("candidate_retry_reducer_incomplete")
    ordered_attempts = sorted(
        attempts,
        key=lambda item: (
            next(
                index
                for index, job in enumerate(jobs)
                if job.candidate_id == item.candidate_id
            ),
            item.retry_ordinal,
        ),
    )
    return (
        tuple(terminal[job.candidate_id] for job in jobs),
        tuple(ordered_attempts),
    )


def combination_unrank(index: int) -> tuple[int, ...]:
    if not 0 <= index < contract.LEGAL_RED_COMBINATION_COUNT:
        raise IsolatedSearchError("combination_index_invalid")
    remaining = index
    result: list[int] = []
    smallest = 1
    for position in range(6):
        for value in range(smallest, 34):
            count = math.comb(33 - value, 5 - position)
            if remaining < count:
                result.append(value)
                smallest = value + 1
                break
            remaining -= count
    if len(result) != 6:
        raise IsolatedSearchError("combination_unrank_failed")
    return tuple(result)


def baseline_seed(target_issue: str, replicate: int) -> str:
    target_issue = contract.require_issue(target_issue)
    if not 0 <= replicate < contract.BASELINE_REPLICATES:
        raise IsolatedSearchError("baseline_replicate_invalid")
    preimage = (
        "M4_ISOLATED_24H_V6|BASELINE|"
        f"{contract.LINEAGE_ID}|{target_issue}|replicate_{replicate:04d}"
    )
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()[:32]


def random_baseline_portfolio(
    target_issue: str, replicate: int
) -> tuple[tuple[tuple[int, ...], int], ...]:
    seed = int(baseline_seed(target_issue, replicate), 16)
    rng = np.random.Generator(np.random.PCG64(seed))
    indices = sorted(
        int(item)
        for item in rng.choice(
            contract.LEGAL_RED_COMBINATION_COUNT,
            size=contract.PORTFOLIO_SIZE,
            replace=False,
        )
    )
    blues = [int(rng.integers(1, 17)) for _ in indices]
    portfolio = tuple(
        (combination_unrank(index), blue)
        for index, blue in zip(indices, blues, strict=True)
    )
    if len({reds for reds, _ in portfolio}) != contract.PORTFOLIO_SIZE:
        raise IsolatedSearchError("baseline_portfolio_duplicate")
    return portfolio


def baseline_set(
    target_issue: str,
) -> tuple[tuple[tuple[tuple[int, ...], int], ...], ...]:
    return tuple(
        random_baseline_portfolio(target_issue, replicate)
        for replicate in range(contract.BASELINE_REPLICATES)
    )


def add_deterministic_blue(
    red_top100: Sequence[tuple[int, ...]], *, seed_hex: str
) -> tuple[tuple[tuple[int, ...], int], ...]:
    if len(red_top100) != contract.PORTFOLIO_SIZE:
        raise IsolatedSearchError("prediction_top100_count_changed")
    rng = np.random.Generator(np.random.PCG64(int(seed_hex, 16)))
    return tuple((tuple(reds), int(rng.integers(1, 17))) for reds in red_top100)


def isolated_rank_blue_portfolio(
    red_top100: Sequence[tuple[int, ...]],
    *,
    target_issue: str,
    challenger_id: str,
) -> tuple[tuple[tuple[int, ...], int], ...]:
    target_issue = contract.require_issue(target_issue)
    challenger_id = contract.require_digest(challenger_id, field="challenger_id")
    if len(red_top100) != contract.PORTFOLIO_SIZE:
        raise IsolatedSearchError("prediction_top100_count_changed")
    output: list[tuple[tuple[int, ...], int]] = []
    for rank, reds in enumerate(red_top100):
        preimage = (
            "M4_ISOLATED_24H_V6|BLUE|"
            f"{contract.LINEAGE_ID}|{target_issue}|{challenger_id}|rank_{rank:03d}"
        )
        seed = int(hashlib.sha256(preimage.encode("utf-8")).hexdigest()[:32], 16)
        rng = np.random.Generator(np.random.PCG64(seed))
        output.append((tuple(reds), int(rng.integers(1, 17))))
    if len({reds for reds, _ in output}) != contract.PORTFOLIO_SIZE:
        raise IsolatedSearchError("prediction_top100_duplicate")
    return tuple(output)


def retry_attempts(
    job: CandidateJob, reasons: Sequence[str | None]
) -> tuple[dict[str, Any], ...]:
    retryable = {"P3_PREEMPTED", "WORKER_PROCESS_CRASH", "WALL_TIMEOUT"}
    if not 1 <= len(reasons) <= 3:
        raise IsolatedSearchError("execution_attempt_count_invalid")
    output: list[dict[str, Any]] = []
    succeeded = False
    for ordinal, reason in enumerate(reasons):
        if succeeded:
            raise IsolatedSearchError("post_success_retry_forbidden")
        if ordinal > 0 and output[-1]["reason"] not in retryable:
            raise IsolatedSearchError("nonretryable_attempt_retried")
        status = "SUCCEEDED" if reason is None else "FAILED"
        succeeded = status == "SUCCEEDED"
        output.append(
            {
                "execution_attempt_id": contract.domain_digest(
                    [job.candidate_id, ordinal],
                    domain="dehps.m4.isolated-24h-challenger.execution-attempt.v11",
                ),
                "candidate_id": job.candidate_id,
                "retry_ordinal": ordinal,
                "status": status,
                "reason": reason,
            }
        )
    if not succeeded and reasons[-1] in retryable and len(reasons) < 3:
        raise IsolatedSearchError("retry_sequence_incomplete")
    return tuple(output)


def synthetic_history(*, end_issue: str, count: int = 320) -> tuple[HistoryRow, ...]:
    """Result-blind deterministic fixture; never used by production execution."""

    end_issue = contract.require_issue(end_issue)
    year = int(end_issue[:4])
    ordinal = int(end_issue[4:])
    if count > ordinal:
        raise IsolatedSearchError("synthetic_history_cross_year_not_supported")
    dates = contract.draw_dates(year)
    output: list[HistoryRow] = []
    for current in range(ordinal - count + 1, ordinal + 1):
        seed = int(
            hashlib.sha256(f"fixture:{year}{current:03d}".encode()).hexdigest()[:32], 16
        )
        rng = np.random.Generator(np.random.PCG64(seed))
        reds = tuple(
            sorted(int(item) for item in rng.choice(33, size=6, replace=False) + 1)
        )
        output.append(
            HistoryRow(
                issue=f"{year}{current:03d}",
                draw_date=dates[current - 1],
                red_numbers=reds,
                blue_number=int(rng.integers(1, 17)),
                source="SYNTHETIC_RESULT_BLIND_FIXTURE",
            )
        )
    return tuple(output)
