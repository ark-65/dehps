from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from dehps.contracts import canonical_digest

from .contracts import MeasurementValidationContractError
from .schedule import AnalysisReplicate


def checkpoint_journal_path(
    output_dir: Path,
    replicate: AnalysisReplicate,
) -> Path:
    return (
        output_dir
        / "checkpoint-journals"
        / replicate.cell.scale_id
        / replicate.cell.scenario_id
        / (
            f"{replicate.replicate_index:04d}-"
            f"{replicate.artifact_digest}.jsonl"
        )
    )


def _load_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    result: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("entry is not an object")
                result.append(value)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise MeasurementValidationContractError(
            "measurement_validation_checkpoint_journal_invalid",
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

    def record(
        self,
        *,
        fold_index: int,
        test_issue: int,
        checkpoint_digests: Mapping[str, str],
    ) -> None:
        entry = {
            "schema_version": (
                "dehps-m4-p2-strict-prior-checkpoint-journal-entry.v1"
            ),
            "fold_index": fold_index,
            "test_issue": test_issue,
            "probe_order": [
                "EMPIRICAL_BASELINE",
                "REGULARIZED_LOGISTIC_REGRESSION",
                "NAIVE_BAYES",
                "SHALLOW_CALIBRATED_TREE",
            ],
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
            or entry.get("target_access")
            != "forbidden_before_this_persisted_entry"
            for index, entry in enumerate(entries)
        )
    ):
        raise MeasurementValidationContractError(
            "measurement_validation_checkpoint_journal_replay_mismatch",
            f"strict-prior checkpoint journal changed: {replicate.artifact_digest}",
        )
