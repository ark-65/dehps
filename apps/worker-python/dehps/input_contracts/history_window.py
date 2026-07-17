from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any

from dehps.contracts import (
    ContractRef,
    ContractRequirement,
    canonical_digest,
    require_contract_compatibility,
)


_ISSUE_PATTERN = re.compile(r"^[0-9]{7}$")
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
WINDOW_STAGE_ABI_VERSION = "dehps.window-stage-abi.v1"

HISTORY_SNAPSHOT_NORMATIVE_DEFINITION = {
    "contract": "history_snapshot.v1.0.0",
    "domain": "ssq_red_draw_history",
    "identity_fields": ["issue", "draw_date", "red_numbers"],
    "issue": {"encoding": "seven_ascii_digits", "ordering": "strict_lexicographic_ascending"},
    "draw_date": {"encoding": "iso_8601_date_or_null"},
    "red_numbers": {
        "shape": [6],
        "range": [1, 33],
        "ordering": "strict_ascending",
        "duplicates": "forbidden",
    },
    "identity_excludes": ["source", "retrieved_at", "database_row_identity"],
    "empty_snapshot": "allowed",
}
HISTORY_SNAPSHOT_GOLDEN_SUITE = {
    "suite": "history_snapshot_golden.v1",
    "cases": [
        {
            "name": "two_canonical_draws",
            "records": [
                ["2026001", "2026-01-01", [1, 2, 3, 4, 5, 6]],
                ["2026002", "2026-01-04", [3, 8, 12, 18, 25, 33]],
            ],
            "expected_history_digest": "71d867675a558963fe9421df8532a35dbcd6bb7c4730189cebd67a033ee05d9f",
            "expected_snapshot_id": "history_snapshot.v1-2026002-71d867675a558963",
        },
        {
            "name": "empty_snapshot",
            "records": [],
            "expected_history_digest": "fbc89ca566295221744607b3c5230952c586ee436bfb0b3e2d4957e99eb08ca5",
            "expected_snapshot_id": "history_snapshot.v1-empty-fbc89ca566295221",
        },
    ],
}
HISTORY_SNAPSHOT_CONTRACT_V1 = ContractRef.from_definition(
    family="history_snapshot",
    semantic_version="1.0.0",
    schema_version="dehps.history-snapshot.schema.v1",
    normative_definition=HISTORY_SNAPSHOT_NORMATIVE_DEFINITION,
    golden_suite=HISTORY_SNAPSHOT_GOLDEN_SUITE,
)

WINDOW_NORMATIVE_DEFINITION = {
    "contract": "window.v1.0.0",
    "history_dependency": HISTORY_SNAPSHOT_CONTRACT_V1.normative_identity(),
    "as_of_issue": "must_exist_in_snapshot",
    "include_as_of": {
        "true": "include_the_as_of_draw",
        "false": "exclude_the_as_of_draw_for_backtest_target_boundaries",
    },
    "modes": {
        "expanding": "all_snapshot_records_before_or_through_the_cutoff",
        "rolling": "at_most_size_records_immediately_before_or_through_the_cutoff",
    },
    "ordering": "preserve_snapshot_order",
    "minimum_size": "reject_when_selected_record_count_is_smaller",
    "target_boundary": "target_issue_must_be_strictly_after_every_selected_issue",
    "missing_issues": "preserve_snapshot_rows_without_calendar_gap_imputation",
}
WINDOW_GOLDEN_SUITE = {
    "suite": "window_golden.v1",
    "snapshot_issues": ["2026001", "2026002", "2026003", "2026004"],
    "cases": [
        {
            "name": "rolling_include_as_of",
            "mode": "rolling",
            "size": 2,
            "as_of_issue": "2026003",
            "include_as_of": True,
            "expected_issues": ["2026002", "2026003"],
            "expected_artifact_digest": "390c578508abab2d37dcc9aabee78540258a3ebd7810042da730e91862845f30",
        },
        {
            "name": "rolling_exclude_backtest_target",
            "mode": "rolling",
            "size": 2,
            "as_of_issue": "2026003",
            "include_as_of": False,
            "target_issue": "2026003",
            "expected_issues": ["2026001", "2026002"],
            "expected_artifact_digest": "6d638a05a32bd3618e3d1bc095c4b052da4f8f2a7e365e300e81f0cf7df99eac",
        },
        {
            "name": "expanding_exclude_backtest_target",
            "mode": "expanding",
            "size": None,
            "as_of_issue": "2026004",
            "include_as_of": False,
            "target_issue": "2026004",
            "expected_issues": ["2026001", "2026002", "2026003"],
            "expected_artifact_digest": "32df0bbde1114368586d516c92871b625234dd7adee82752340720e1a51a1133",
        },
    ],
}
WINDOW_CONTRACT_V1 = ContractRef.from_definition(
    family="window",
    semantic_version="1.0.0",
    schema_version="dehps.window.schema.v1",
    normative_definition=WINDOW_NORMATIVE_DEFINITION,
    golden_suite=WINDOW_GOLDEN_SUITE,
)
WINDOW_HISTORY_REQUIREMENT = ContractRequirement.exact(HISTORY_SNAPSHOT_CONTRACT_V1)


class WindowMode(str, Enum):
    EXPANDING = "expanding"
    ROLLING = "rolling"


class InputContractViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


def _require_digest(name: str, value: str) -> None:
    if not _DIGEST_PATTERN.fullmatch(value):
        raise InputContractViolation("invalid_digest", f"{name} must be a lowercase sha256 digest", field=name)


def _require_issue(value: str, *, field_name: str) -> str:
    normalized = str(value).strip()
    if not _ISSUE_PATTERN.fullmatch(normalized):
        raise InputContractViolation(
            "invalid_issue_encoding",
            f"{field_name} must contain exactly seven ASCII digits",
            field=field_name,
            value=normalized,
        )
    return normalized


@dataclass(frozen=True)
class HistoryRecord:
    issue: str
    draw_date: date | None
    red_numbers: tuple[int, ...]

    def __post_init__(self) -> None:
        _require_issue(self.issue, field_name="issue")
        if self.draw_date is not None and (
            not isinstance(self.draw_date, date) or isinstance(self.draw_date, datetime)
        ):
            raise InputContractViolation("invalid_draw_date", "draw_date must be a date or null", issue=self.issue)
        if len(self.red_numbers) != 6:
            raise InputContractViolation("invalid_red_number_shape", "red_numbers must contain six values", issue=self.issue)
        if any(isinstance(number, bool) or not isinstance(number, int) for number in self.red_numbers):
            raise InputContractViolation("invalid_red_number_type", "red_numbers must contain integers", issue=self.issue)
        if tuple(sorted(self.red_numbers)) != self.red_numbers or len(set(self.red_numbers)) != 6:
            raise InputContractViolation(
                "noncanonical_red_numbers",
                "red_numbers must be unique and strictly ascending",
                issue=self.issue,
            )
        if any(number < 1 or number > 33 for number in self.red_numbers):
            raise InputContractViolation("red_number_out_of_range", "red_numbers must be in [1,33]", issue=self.issue)

    @classmethod
    def from_value(cls, value: object) -> HistoryRecord:
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            issue = value.get("issue")
            draw_date_value = value.get("draw_date")
            numbers = value.get("red_numbers")
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            if len(value) == 2:
                issue, numbers = value
                draw_date_value = None
            elif len(value) == 3:
                issue, draw_date_value, numbers = value
            else:
                raise InputContractViolation(
                    "invalid_history_record_shape",
                    "history records must have two or three fields",
                    field_count=len(value),
                )
        else:
            raise InputContractViolation("invalid_history_record", "unsupported history record type")
        try:
            parsed_date = date.fromisoformat(draw_date_value) if isinstance(draw_date_value, str) else draw_date_value
        except ValueError as exc:
            raise InputContractViolation("invalid_draw_date", "draw_date is not an ISO date") from exc
        if not isinstance(numbers, Sequence) or isinstance(numbers, (str, bytes, bytearray)):
            raise InputContractViolation("invalid_red_numbers", "red_numbers must be an ordered sequence")
        return cls(
            issue=str(issue),
            draw_date=parsed_date,
            red_numbers=tuple(numbers),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "issue": self.issue,
            "draw_date": self.draw_date.isoformat() if self.draw_date else None,
            "red_numbers": list(self.red_numbers),
        }

    def as_history_draw(self) -> tuple[str, date | None, tuple[int, ...]]:
        return self.issue, self.draw_date, self.red_numbers


def _history_payload(records: Sequence[HistoryRecord]) -> dict[str, Any]:
    return {
        "contract": HISTORY_SNAPSHOT_CONTRACT_V1.normative_identity(),
        "records": [record.as_dict() for record in records],
    }


@dataclass(frozen=True)
class HistorySnapshotArtifact:
    contract: ContractRef
    snapshot_id: str
    history_digest: str
    latest_issue: str | None
    draw_count: int
    records: tuple[HistoryRecord, ...]
    source: str = field(default="ssq_history", compare=False)

    @classmethod
    def from_history(
        cls,
        history: Sequence[object],
        *,
        source: str = "ssq_history",
    ) -> HistorySnapshotArtifact:
        records = tuple(HistoryRecord.from_value(value) for value in history)
        for previous, current in zip(records, records[1:]):
            if current.issue <= previous.issue:
                raise InputContractViolation(
                    "history_issue_order_violation",
                    "history issues must be unique and strictly ascending",
                    previous_issue=previous.issue,
                    current_issue=current.issue,
                )
        digest = canonical_digest(_history_payload(records), domain="dehps.history-snapshot-artifact.v1")
        latest_issue = records[-1].issue if records else None
        snapshot_id = f"history_snapshot.v1-{latest_issue or 'empty'}-{digest[:16]}"
        return cls(
            contract=HISTORY_SNAPSHOT_CONTRACT_V1,
            snapshot_id=snapshot_id,
            history_digest=digest,
            latest_issue=latest_issue,
            draw_count=len(records),
            records=records,
            source=source,
        )

    def __post_init__(self) -> None:
        if not self.contract.normatively_equals(HISTORY_SNAPSHOT_CONTRACT_V1):
            raise InputContractViolation(
                "history_snapshot_contract_mismatch",
                "history snapshot must use history_snapshot.v1.0.0",
            )
        _require_digest("history_digest", self.history_digest)
        if any(not isinstance(record, HistoryRecord) for record in self.records):
            raise InputContractViolation(
                "invalid_history_snapshot_record",
                "history snapshot records must be canonical HistoryRecord values",
            )
        for previous, current in zip(self.records, self.records[1:]):
            if current.issue <= previous.issue:
                raise InputContractViolation(
                    "history_issue_order_violation",
                    "history issues must be unique and strictly ascending",
                    previous_issue=previous.issue,
                    current_issue=current.issue,
                )
        expected = canonical_digest(_history_payload(self.records), domain="dehps.history-snapshot-artifact.v1")
        if expected != self.history_digest:
            raise InputContractViolation(
                "history_snapshot_digest_mismatch",
                "history snapshot payload does not match history_digest",
            )
        if self.draw_count != len(self.records):
            raise InputContractViolation("history_draw_count_mismatch", "draw_count does not match records")
        expected_latest = self.records[-1].issue if self.records else None
        if self.latest_issue != expected_latest:
            raise InputContractViolation("history_latest_issue_mismatch", "latest_issue does not match records")
        expected_id = f"history_snapshot.v1-{expected_latest or 'empty'}-{expected[:16]}"
        if self.snapshot_id != expected_id:
            raise InputContractViolation("history_snapshot_id_mismatch", "snapshot_id is not canonical")

    @property
    def first_issue(self) -> str | None:
        return self.records[0].issue if self.records else None

    @property
    def history_fingerprint(self) -> str:
        return self.history_digest

    def as_dict(self, *, include_records: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "contract": self.contract.as_dict(),
            "snapshot_id": self.snapshot_id,
            "history_digest": self.history_digest,
            "first_issue": self.first_issue,
            "latest_issue": self.latest_issue,
            "draw_count": self.draw_count,
            "source": self.source,
        }
        if include_records:
            payload["records"] = [record.as_dict() for record in self.records]
        return payload


@dataclass(frozen=True)
class WindowSpec:
    mode: WindowMode
    as_of_issue: str
    include_as_of: bool
    size: int | None
    minimum_size: int = 1
    target_issue: str | None = None
    contract: ContractRef = WINDOW_CONTRACT_V1

    def __post_init__(self) -> None:
        if isinstance(self.mode, str):
            try:
                object.__setattr__(self, "mode", WindowMode(self.mode))
            except ValueError as exc:
                raise InputContractViolation("unsupported_window_mode", f"unsupported mode: {self.mode}") from exc
        if not isinstance(self.mode, WindowMode):
            raise InputContractViolation("unsupported_window_mode", f"unsupported mode: {self.mode}")
        if not self.contract.normatively_equals(WINDOW_CONTRACT_V1):
            raise InputContractViolation("window_contract_mismatch", "WindowSpec must use window.v1.0.0")
        _require_issue(self.as_of_issue, field_name="as_of_issue")
        if self.target_issue is not None:
            _require_issue(self.target_issue, field_name="target_issue")
        if not isinstance(self.include_as_of, bool):
            raise InputContractViolation("invalid_include_as_of", "include_as_of must be boolean")
        if (
            isinstance(self.minimum_size, bool)
            or not isinstance(self.minimum_size, int)
            or self.minimum_size < 1
        ):
            raise InputContractViolation("invalid_minimum_size", "minimum_size must be positive")
        if self.mode is WindowMode.ROLLING:
            if isinstance(self.size, bool) or not isinstance(self.size, int) or self.size < 1:
                raise InputContractViolation("invalid_rolling_size", "rolling windows require a positive size")
            if self.minimum_size > self.size:
                raise InputContractViolation(
                    "minimum_size_exceeds_window_size",
                    "rolling minimum_size may not exceed size",
                )
        elif self.size is not None:
            raise InputContractViolation("expanding_window_has_size", "expanding windows require size=null")

    @property
    def spec_digest(self) -> str:
        return canonical_digest(self.identity_payload(), domain="dehps.window-spec.v1")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "contract": self.contract.normative_identity(),
            "mode": self.mode.value,
            "size": self.size,
            "minimum_size": self.minimum_size,
            "as_of_issue": self.as_of_issue,
            "include_as_of": self.include_as_of,
            "target_issue": self.target_issue,
        }

    def materialize(self, snapshot: HistorySnapshotArtifact) -> WindowArtifact:
        require_contract_compatibility(
            consumer=self.contract,
            dependency=snapshot.contract,
            requirement=WINDOW_HISTORY_REQUIREMENT,
        )
        index_by_issue = {record.issue: index for index, record in enumerate(snapshot.records)}
        if self.as_of_issue not in index_by_issue:
            raise InputContractViolation(
                "as_of_issue_not_in_snapshot",
                "as_of_issue must exist in the referenced history snapshot",
                as_of_issue=self.as_of_issue,
                snapshot_id=snapshot.snapshot_id,
            )
        as_of_index = index_by_issue[self.as_of_issue]
        stop_index = as_of_index + (1 if self.include_as_of else 0)
        start_index = 0 if self.mode is WindowMode.EXPANDING else max(0, stop_index - int(self.size or 0))
        records = snapshot.records[start_index:stop_index]
        if len(records) < self.minimum_size:
            raise InputContractViolation(
                "insufficient_window_history",
                "selected history is smaller than minimum_size",
                selected_count=len(records),
                minimum_size=self.minimum_size,
            )
        if self.target_issue is not None and records and self.target_issue <= records[-1].issue:
            raise InputContractViolation(
                "target_issue_leakage",
                "target_issue must be strictly after every selected history issue",
                target_issue=self.target_issue,
                latest_selected_issue=records[-1].issue,
            )
        return WindowArtifact.build(
            snapshot=snapshot,
            spec=self,
            records=records,
            start_index=start_index,
            stop_index=stop_index,
        )


@dataclass(frozen=True)
class WindowStageEnvelope:
    abi_version: str
    history_contract: ContractRef
    window_contract: ContractRef
    history_snapshot_digest: str
    window_spec_digest: str
    selected_payload_digest: str
    input_draw_count: int
    output_draw_count: int

    @property
    def envelope_digest(self) -> str:
        return canonical_digest(self.identity_payload(), domain="dehps.window-stage-envelope.v1")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "abi_version": self.abi_version,
            "history_contract": self.history_contract.normative_identity(),
            "window_contract": self.window_contract.normative_identity(),
            "history_snapshot_digest": self.history_snapshot_digest,
            "window_spec_digest": self.window_spec_digest,
            "selected_payload_digest": self.selected_payload_digest,
            "input_draw_count": self.input_draw_count,
            "output_draw_count": self.output_draw_count,
        }

    def validate(self) -> None:
        if self.abi_version != WINDOW_STAGE_ABI_VERSION:
            raise InputContractViolation("unsupported_abi_version", "unsupported Window stage ABI")
        require_contract_compatibility(
            consumer=self.window_contract,
            dependency=self.history_contract,
            requirement=WINDOW_HISTORY_REQUIREMENT,
        )
        if not self.window_contract.normatively_equals(WINDOW_CONTRACT_V1):
            raise InputContractViolation("window_contract_mismatch", "envelope must use window.v1.0.0")
        for name, value in (
            ("history_snapshot_digest", self.history_snapshot_digest),
            ("window_spec_digest", self.window_spec_digest),
            ("selected_payload_digest", self.selected_payload_digest),
        ):
            _require_digest(name, value)
        if self.input_draw_count < 0 or self.output_draw_count < 0:
            raise InputContractViolation("invalid_envelope_count", "envelope counts must be non-negative")
        if self.output_draw_count > self.input_draw_count:
            raise InputContractViolation("window_count_exceeds_snapshot", "window cannot exceed snapshot size")


@dataclass(frozen=True)
class WindowArtifact:
    spec: WindowSpec
    snapshot_id: str
    start_index: int
    stop_index: int
    records: tuple[HistoryRecord, ...]
    envelope: WindowStageEnvelope
    artifact_digest: str

    @classmethod
    def build(
        cls,
        *,
        snapshot: HistorySnapshotArtifact,
        spec: WindowSpec,
        records: tuple[HistoryRecord, ...],
        start_index: int,
        stop_index: int,
    ) -> WindowArtifact:
        selected_payload_digest = canonical_digest(
            [record.as_dict() for record in records],
            domain="dehps.window-selected-payload.v1",
        )
        envelope = WindowStageEnvelope(
            abi_version=WINDOW_STAGE_ABI_VERSION,
            history_contract=snapshot.contract,
            window_contract=spec.contract,
            history_snapshot_digest=snapshot.history_digest,
            window_spec_digest=spec.spec_digest,
            selected_payload_digest=selected_payload_digest,
            input_draw_count=snapshot.draw_count,
            output_draw_count=len(records),
        )
        envelope.validate()
        artifact_digest = canonical_digest(
            {
                "artifact_type": "window.v1",
                "parent_digests": [snapshot.history_digest, spec.spec_digest],
                "payload_digest": selected_payload_digest,
                "start_index": start_index,
                "stop_index": stop_index,
            },
            domain="dehps.window-artifact.v1",
        )
        return cls(
            spec=spec,
            snapshot_id=snapshot.snapshot_id,
            start_index=start_index,
            stop_index=stop_index,
            records=records,
            envelope=envelope,
            artifact_digest=artifact_digest,
        )

    def __post_init__(self) -> None:
        self.verify()

    def verify(self) -> None:
        """Re-run the fail-closed Window artifact checks at a runtime boundary."""
        self.envelope.validate()
        _require_digest("artifact_digest", self.artifact_digest)
        if not self.envelope.window_contract.normatively_equals(self.spec.contract):
            raise InputContractViolation(
                "window_envelope_contract_mismatch",
                "envelope window contract does not match WindowSpec",
            )
        if self.envelope.window_spec_digest != self.spec.spec_digest:
            raise InputContractViolation(
                "window_spec_digest_mismatch",
                "envelope window_spec_digest does not match WindowSpec",
            )
        if self.stop_index - self.start_index != len(self.records):
            raise InputContractViolation("window_index_count_mismatch", "window indices do not match records")
        if self.envelope.output_draw_count != len(self.records):
            raise InputContractViolation("window_envelope_count_mismatch", "envelope count does not match records")
        payload_digest = canonical_digest(
            [record.as_dict() for record in self.records],
            domain="dehps.window-selected-payload.v1",
        )
        if payload_digest != self.envelope.selected_payload_digest:
            raise InputContractViolation("window_payload_digest_mismatch", "records do not match envelope digest")
        expected = canonical_digest(
            {
                "artifact_type": "window.v1",
                "parent_digests": [self.envelope.history_snapshot_digest, self.spec.spec_digest],
                "payload_digest": payload_digest,
                "start_index": self.start_index,
                "stop_index": self.stop_index,
            },
            domain="dehps.window-artifact.v1",
        )
        if expected != self.artifact_digest:
            raise InputContractViolation("window_artifact_digest_mismatch", "artifact digest is not canonical")

    @property
    def first_issue(self) -> str:
        return self.records[0].issue

    @property
    def latest_issue(self) -> str:
        return self.records[-1].issue

    def as_history(self) -> list[tuple[str, date | None, tuple[int, ...]]]:
        return [record.as_history_draw() for record in self.records]

    def as_dict(self, *, include_records: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "contract": self.spec.contract.as_dict(),
            "snapshot_id": self.snapshot_id,
            "artifact_digest": self.artifact_digest,
            "spec": self.spec.identity_payload(),
            "first_issue": self.first_issue,
            "latest_issue": self.latest_issue,
            "draw_count": len(self.records),
            "start_index": self.start_index,
            "stop_index": self.stop_index,
            "envelope": {
                **self.envelope.identity_payload(),
                "envelope_digest": self.envelope.envelope_digest,
            },
        }
        if include_records:
            payload["records"] = [record.as_dict() for record in self.records]
        return payload
