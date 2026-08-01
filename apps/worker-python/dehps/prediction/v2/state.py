from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from typing import Any

from dehps.contracts import canonical_digest
from dehps.input_contracts.history_window import (
    HistoryRecord,
    HistorySnapshotArtifact,
    WindowMode,
    WindowSpec,
)
from dehps.prediction.v2.contracts import PredictionV2ContractError, require_issue, seal_artifact


STATE_SCHEMA = "dehps-prediction-v2-state-artifact.v1"


def _slope(values: Sequence[float]) -> float:
    count = len(values)
    if count < 2:
        return 0.0
    mean_x = (count - 1) / 2.0
    mean_y = sum(values) / count
    denominator = sum((index - mean_x) ** 2 for index in range(count))
    if denominator == 0:
        return 0.0
    return sum(
        (index - mean_x) * (value - mean_y)
        for index, value in enumerate(values)
    ) / denominator


def _window_statistics(records: Sequence[HistoryRecord]) -> dict[str, Any]:
    draw_count = len(records)
    counts = Counter(number for record in records for number in record.red_numbers)
    rates = [counts[number] / draw_count for number in range(1, 34)]
    total_slots = draw_count * 6
    slot_shares = [counts[number] / total_slots for number in range(1, 34)]
    entropy = -sum(share * math.log2(share) for share in slot_shares if share > 0)
    odd_rates = [sum(number % 2 for number in record.red_numbers) / 6 for record in records]
    high_rates = [sum(number >= 17 for number in record.red_numbers) / 6 for record in records]
    sums = [sum(record.red_numbers) for record in records]
    last_seen: dict[int, int] = {}
    for index, record in enumerate(records):
        for number in record.red_numbers:
            last_seen[number] = index
    gaps = [draw_count - 1 - last_seen[number] if number in last_seen else draw_count for number in range(1, 34)]
    return {
        "draw_count": draw_count,
        "number_counts": counts_payload(counts),
        "number_rates": [round(value, 12) for value in rates],
        "number_gaps": gaps,
        "entropy_bits": round(entropy, 12),
        "concentration_hhi": round(sum(share * share for share in slot_shares), 12),
        "odd_rate_mean": round(sum(odd_rates) / draw_count, 12),
        "odd_rate_slope": round(_slope(odd_rates), 12),
        "high_rate_mean": round(sum(high_rates) / draw_count, 12),
        "high_rate_slope": round(_slope(high_rates), 12),
        "sum_mean": round(sum(sums) / draw_count, 12),
        "sum_slope": round(_slope([float(value) for value in sums]), 12),
    }


def counts_payload(counts: Counter[int]) -> list[int]:
    return [counts[number] for number in range(1, 34)]


def encode_state(
    history: HistorySnapshotArtifact,
    *,
    as_of_issue: str,
    target_issue: str,
    windows: tuple[int, ...] = (30, 60, 120),
) -> dict[str, Any]:
    history.verify()
    as_of = require_issue(as_of_issue, field="as_of_issue")
    target = require_issue(target_issue, field="target_issue")
    if target <= as_of:
        raise PredictionV2ContractError("target_issue must be strictly after as_of_issue")
    if history.latest_issue != as_of:
        raise PredictionV2ContractError("history snapshot must end exactly at as_of_issue")
    if tuple(windows) != (30, 60, 120):
        raise PredictionV2ContractError("state windows must remain 30/60/120")
    if history.draw_count < max(windows):
        raise PredictionV2ContractError("Prediction v2 requires at least 120 prior draws")
    encoded_windows: dict[str, Any] = {}
    parent_digests: list[str] = [history.history_digest]
    for size in windows:
        materialized = WindowSpec(
            mode=WindowMode.ROLLING,
            size=size,
            minimum_size=size,
            as_of_issue=as_of,
            include_as_of=True,
            target_issue=target,
        ).materialize(history)
        parent_digests.append(materialized.artifact_digest)
        encoded_windows[str(size)] = {
            "window_artifact_digest": materialized.artifact_digest,
            **_window_statistics(materialized.records),
        }
    return seal_artifact(
        {
            "schema_version": STATE_SCHEMA,
            "artifact_type": "PredictionV2StateArtifact.v1",
            "as_of_issue": as_of,
            "target_issue": target,
            "history_snapshot_id": history.snapshot_id,
            "history_digest": history.history_digest,
            "state_windows": list(windows),
            "windows": encoded_windows,
            "state_usage": "DIAGNOSTIC_ONLY_UNTIL_EXPERT_RESEARCH_AUTHORIZATION",
            "historical_evidence": "NOT_RUN",
            "parent_digests": parent_digests,
        },
        domain="dehps.prediction-v2.state-artifact.v1",
    )
