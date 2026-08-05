from __future__ import annotations

import base64
import binascii
import json
import math
import os
import re
import struct
import zlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest

from .contracts import MeasurementValidationContractError
from .schedule import AnalysisReplicate

PROBE_ORDER = (
    "EMPIRICAL_BASELINE",
    "REGULARIZED_LOGISTIC_REGRESSION",
    "NAIVE_BAYES",
    "SHALLOW_CALIBRATED_TREE",
)
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_PROBABILITY_COUNT = 33
_SETTLED_FOLD_SCHEMA = "dehps-m4-p2-settled-fold-resume-entry.v1"
_SETTLED_FOLD_ENTRY_DOMAIN = "dehps.m4-p2.settled-fold-resume-entry.v1"
_CHECKPOINT_ENTRY_DOMAIN = "dehps.m4-p2.strict-prior-checkpoint-entry.v1"


def checkpoint_journal_path(
    output_dir: Path,
    replicate: AnalysisReplicate,
) -> Path:
    return (
        output_dir
        / "checkpoint-journals"
        / replicate.cell.scale_id
        / replicate.cell.scenario_id
        / (f"{replicate.replicate_index:04d}-" f"{replicate.artifact_digest}.jsonl")
    )


def settled_fold_resume_journal_path(
    output_dir: Path,
    replicate: AnalysisReplicate,
) -> Path:
    return (
        output_dir
        / "settled-fold-resume"
        / replicate.cell.scale_id
        / replicate.cell.scenario_id
        / (f"{replicate.replicate_index:04d}-" f"{replicate.artifact_digest}.jsonl")
    )


def _load_lines(
    path: Path,
    *,
    error_code: str = "measurement_validation_checkpoint_journal_invalid",
) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    result: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise TypeError("entry is not an object")
                result.append(value)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise MeasurementValidationContractError(
            error_code,
            f"{path}: {exc}",
        ) from exc
    return result


def _journal_digest(entries: list[dict[str, Any]]) -> str:
    return canonical_digest(
        entries,
        domain="dehps.m4-p2.strict-prior-checkpoint-journal.v1",
    )


class StrictPriorCheckpointJournal:
    def __init__(
        self,
        *,
        output_dir: Path,
        replicate: AnalysisReplicate,
    ) -> None:
        self.path = checkpoint_journal_path(output_dir, replicate)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries = _load_lines(self.path)

    def __len__(self) -> int:
        return len(self._entries)

    def entry(self, fold_index: int) -> dict[str, Any]:
        try:
            entry = self._entries[fold_index]
        except IndexError as exc:
            raise MeasurementValidationContractError(
                "measurement_validation_checkpoint_journal_gap",
                f"checkpoint journal has no fold {fold_index}",
            ) from exc
        return {
            **entry,
            "probe_order": list(entry.get("probe_order", [])),
            "checkpoint_digests": dict(entry.get("checkpoint_digests", {})),
        }

    def record(
        self,
        *,
        fold_index: int,
        test_issue: int,
        checkpoint_digests: Mapping[str, str],
    ) -> None:
        entry = {
            "schema_version": ("dehps-m4-p2-strict-prior-checkpoint-journal-entry.v1"),
            "fold_index": fold_index,
            "test_issue": test_issue,
            "probe_order": list(PROBE_ORDER),
            "checkpoint_digests": dict(checkpoint_digests),
            "target_access": "forbidden_before_this_persisted_entry",
        }
        if fold_index < len(self._entries):
            if self._entries[fold_index] != entry:
                raise MeasurementValidationContractError(
                    "measurement_validation_checkpoint_replay_mismatch",
                    f"checkpoint journal changed at fold {fold_index}",
                )
            return
        if fold_index != len(self._entries):
            raise MeasurementValidationContractError(
                "measurement_validation_checkpoint_journal_gap",
                "checkpoint journal entries must be contiguous",
            )
        encoded = json.dumps(
            entry,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(encoded + "\n")
            handle.flush()
        self._entries.append(entry)

    def finalize(self, *, expected_fold_count: int) -> tuple[str, int]:
        if len(self._entries) != expected_fold_count:
            raise MeasurementValidationContractError(
                "measurement_validation_checkpoint_journal_incomplete",
                (
                    f"expected {expected_fold_count} strict-prior checkpoints, "
                    f"found {len(self._entries)}"
                ),
            )
        with self.path.open("rb") as handle:
            os.fsync(handle.fileno())
        return _journal_digest(self._entries), len(self._entries)


def _encode_probability_matrix(
    probabilities: Mapping[str, tuple[float, ...]],
) -> str:
    raw = bytearray()
    for probe_id in PROBE_ORDER:
        values = probabilities[probe_id]
        if len(values) != _PROBABILITY_COUNT or any(
            not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in values
        ):
            raise MeasurementValidationContractError(
                "measurement_validation_settled_fold_resume_invalid",
                "settled probability vectors must contain 33 finite probabilities",
            )
        raw.extend(struct.pack(f">{_PROBABILITY_COUNT}d", *values))
    return base64.b64encode(zlib.compress(bytes(raw), level=6)).decode("ascii")


def _decode_probability_matrix(
    value: object,
) -> dict[str, tuple[float, ...]]:
    if not isinstance(value, str):
        raise TypeError("probability payload is not base64 text")
    compressed = base64.b64decode(value, validate=True)
    expected_size = len(PROBE_ORDER) * _PROBABILITY_COUNT * 8
    decompressor = zlib.decompressobj()
    raw = decompressor.decompress(compressed, expected_size + 1)
    if len(raw) != expected_size:
        raise ValueError("probability payload has the wrong byte length")
    if not decompressor.eof or decompressor.unused_data or decompressor.unconsumed_tail:
        raise ValueError("probability payload has invalid compressed framing")
    vector_size = _PROBABILITY_COUNT * 8
    probabilities = {
        probe_id: tuple(
            struct.unpack(
                f">{_PROBABILITY_COUNT}d",
                raw[index * vector_size : (index + 1) * vector_size],
            )
        )
        for index, probe_id in enumerate(PROBE_ORDER)
    }
    if any(
        not math.isfinite(value) or not 0.0 <= value <= 1.0
        for values in probabilities.values()
        for value in values
    ):
        raise ValueError("probability payload contains a non-finite or invalid value")
    return probabilities


def _encode_target(values: tuple[int, ...]) -> str:
    if (
        len(values) != _PROBABILITY_COUNT
        or any(value not in (0, 1) for value in values)
        or sum(values) != 6
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_settled_fold_resume_invalid",
            "settled target vectors must contain six ones across 33 values",
        )
    return base64.b64encode(bytes(values)).decode("ascii")


def _decode_target(value: object) -> tuple[int, ...]:
    if not isinstance(value, str):
        raise TypeError("target payload is not base64 text")
    raw = base64.b64decode(value, validate=True)
    target = tuple(raw)
    if (
        len(target) != _PROBABILITY_COUNT
        or any(item not in (0, 1) for item in target)
        or sum(target) != 6
    ):
        raise ValueError("target payload is not a legal 6-of-33 vector")
    return target


def _checkpoint_entry_digest(entry: Mapping[str, Any]) -> str:
    return canonical_digest(
        dict(entry),
        domain=_CHECKPOINT_ENTRY_DOMAIN,
    )


class SettledFoldResumeJournal:
    """Additive post-target state used only to skip exact completed folds."""

    def __init__(
        self,
        *,
        output_dir: Path,
        replicate: AnalysisReplicate,
    ) -> None:
        self.path = settled_fold_resume_journal_path(output_dir, replicate)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries = _load_lines(
            self.path,
            error_code="measurement_validation_settled_fold_resume_invalid",
        )
        self._validate_entries()

    def __len__(self) -> int:
        return len(self._entries)

    def _validate_entries(self) -> None:
        previous_digest: str | None = None
        try:
            for fold_index, entry in enumerate(self._entries):
                entry_digest = entry.get("entry_digest")
                body = dict(entry)
                body.pop("entry_digest", None)
                state_digests = entry.get("probe_state_digests")
                probabilities = entry.get("probabilities_float64_be_zlib_base64")
                if (
                    entry.get("schema_version") != _SETTLED_FOLD_SCHEMA
                    or entry.get("fold_index") != fold_index
                    or not isinstance(entry.get("test_issue"), int)
                    or entry.get("probe_order") != list(PROBE_ORDER)
                    or entry.get("previous_entry_digest") != previous_digest
                    or not isinstance(entry.get("checkpoint_entry_digest"), str)
                    or _SHA256_PATTERN.fullmatch(
                        str(entry.get("checkpoint_entry_digest"))
                    )
                    is None
                    or not isinstance(state_digests, dict)
                    or set(state_digests) != set(PROBE_ORDER)
                    or any(
                        not isinstance(value, str)
                        or _SHA256_PATTERN.fullmatch(value) is None
                        for value in state_digests.values()
                    )
                    or not isinstance(probabilities, str)
                    or not isinstance(entry_digest, str)
                    or _SHA256_PATTERN.fullmatch(entry_digest) is None
                    or entry_digest
                    != canonical_digest(body, domain=_SETTLED_FOLD_ENTRY_DOMAIN)
                ):
                    raise ValueError(f"invalid settled fold entry {fold_index}")
                _decode_probability_matrix(probabilities)
                _decode_target(entry.get("target_uint8_base64"))
                previous_digest = entry_digest
        except (
            KeyError,
            ValueError,
            TypeError,
            binascii.Error,
            struct.error,
            zlib.error,
        ) as exc:
            raise MeasurementValidationContractError(
                "measurement_validation_settled_fold_resume_invalid",
                f"{self.path}: {exc}",
            ) from exc

    def restored_fold(
        self,
        fold_index: int,
        *,
        checkpoint_entry: Mapping[str, Any],
    ) -> tuple[
        dict[str, str],
        dict[str, tuple[float, ...]],
        tuple[int, ...],
    ]:
        try:
            entry = self._entries[fold_index]
        except IndexError as exc:
            raise MeasurementValidationContractError(
                "measurement_validation_settled_fold_resume_gap",
                f"settlement resume journal has no fold {fold_index}",
            ) from exc
        if (
            entry["fold_index"] != checkpoint_entry.get("fold_index")
            or entry["test_issue"] != checkpoint_entry.get("test_issue")
            or entry["checkpoint_entry_digest"]
            != _checkpoint_entry_digest(checkpoint_entry)
        ):
            raise MeasurementValidationContractError(
                "measurement_validation_settled_fold_checkpoint_mismatch",
                f"settled fold {fold_index} does not bind its strict-prior checkpoint",
            )
        try:
            state_digests = dict(entry["probe_state_digests"])
            probabilities = _decode_probability_matrix(
                entry["probabilities_float64_be_zlib_base64"]
            )
            target = _decode_target(entry["target_uint8_base64"])
        except (
            KeyError,
            ValueError,
            TypeError,
            binascii.Error,
            struct.error,
            zlib.error,
        ) as exc:
            raise MeasurementValidationContractError(
                "measurement_validation_settled_fold_resume_invalid",
                f"{self.path}: {exc}",
            ) from exc
        return state_digests, probabilities, target

    def record(
        self,
        *,
        fold_index: int,
        test_issue: int,
        checkpoint_entry: Mapping[str, Any],
        probe_state_digests: Mapping[str, str],
        probabilities: Mapping[str, tuple[float, ...]],
        target_vector: tuple[int, ...],
    ) -> None:
        if (
            set(probe_state_digests) != set(PROBE_ORDER)
            or set(probabilities) != set(PROBE_ORDER)
            or any(
                not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None
                for value in probe_state_digests.values()
            )
            or checkpoint_entry.get("fold_index") != fold_index
            or checkpoint_entry.get("test_issue") != test_issue
            or checkpoint_entry.get("probe_order") != list(PROBE_ORDER)
        ):
            raise MeasurementValidationContractError(
                "measurement_validation_settled_fold_resume_invalid",
                "settled fold probes changed from the frozen order",
            )
        body = {
            "schema_version": _SETTLED_FOLD_SCHEMA,
            "fold_index": fold_index,
            "test_issue": test_issue,
            "probe_order": list(PROBE_ORDER),
            "checkpoint_entry_digest": _checkpoint_entry_digest(checkpoint_entry),
            "previous_entry_digest": (
                None if not self._entries else self._entries[-1]["entry_digest"]
            ),
            "probe_state_digests": dict(probe_state_digests),
            "probabilities_float64_be_zlib_base64": _encode_probability_matrix(
                {probe_id: tuple(probabilities[probe_id]) for probe_id in PROBE_ORDER}
            ),
            "target_uint8_base64": _encode_target(tuple(target_vector)),
        }
        entry = {
            **body,
            "entry_digest": canonical_digest(
                body,
                domain=_SETTLED_FOLD_ENTRY_DOMAIN,
            ),
        }
        if fold_index < len(self._entries):
            if self._entries[fold_index] != entry:
                raise MeasurementValidationContractError(
                    "measurement_validation_settled_fold_replay_mismatch",
                    f"settled fold changed at index {fold_index}",
                )
            return
        if fold_index != len(self._entries):
            raise MeasurementValidationContractError(
                "measurement_validation_settled_fold_resume_gap",
                "settled fold resume entries must be contiguous",
            )
        encoded = json.dumps(
            entry,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(encoded + "\n")
            handle.flush()
        self._entries.append(entry)


def verify_checkpoint_journal(
    *,
    output_dir: Path,
    replicate: AnalysisReplicate,
    expected_digest: str,
    expected_fold_count: int,
) -> None:
    entries = _load_lines(checkpoint_journal_path(output_dir, replicate))
    if (
        len(entries) != expected_fold_count
        or _journal_digest(entries) != expected_digest
        or any(
            entry.get("fold_index") != index
            or entry.get("target_access") != "forbidden_before_this_persisted_entry"
            for index, entry in enumerate(entries)
        )
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_checkpoint_journal_replay_mismatch",
            f"strict-prior checkpoint journal changed: {replicate.artifact_digest}",
        )
