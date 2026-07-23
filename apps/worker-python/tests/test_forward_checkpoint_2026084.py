from __future__ import annotations

import json
from pathlib import Path

import pytest

from dehps.contracts import canonical_digest
from dehps.forward_checkpoint.issue_2026084 import (
    ARCHITECTURE_LABEL,
    AS_OF_ISSUE,
    CHECKPOINT_PROTOCOL,
    TARGET_ISSUE,
    ForwardCheckpointError,
    _control_aggregates,
    _settle_tickets,
    _verified_checkpoint,
    seal_2026084_checkpoint,
    settle_forward_checkpoint_if_available,
)


def _checkpoint_payload() -> dict[str, object]:
    return {
        "protocol": CHECKPOINT_PROTOCOL,
        "target_issue": TARGET_ISSUE,
        "target_draw_date": "2026-07-23",
        "as_of_issue": AS_OF_ISSUE,
        "sealed_at": "2026-07-23T10:00:00Z",
        "source_code_commit": "a" * 40,
        "architecture_label": ARCHITECTURE_LABEL,
        "database_cutoff": AS_OF_ISSUE,
        "outcome": None,
        "outer_sample_ordinal_if_settled": 61,
        "legacy_lines": [],
        "seven_red_source": {},
        "seven_red_forward": {},
        "guardrails": {
            "promotion_gate_opened": False,
            "automatic_promotion_allowed": False,
            "single_issue_upgrade_allowed": False,
            "production_action": "none",
        },
    }


def _write_checkpoint(path: Path, payload: dict[str, object]) -> None:
    digest = canonical_digest(
        payload,
        domain="dehps.2026084.forward-checkpoint.v1",
    )
    path.write_text(
        json.dumps({**payload, "checkpoint_digest": digest}),
        encoding="utf-8",
    )


def test_ticket_settlement_distinguishes_nominal_and_unique_counts() -> None:
    result = _settle_tickets(
        [(1, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 6), (1, 2, 3, 7, 8, 9)],
        (1, 2, 3, 4, 5, 6),
    )

    assert result["paid_ticket_count"] == 3
    assert result["unique_ticket_count"] == 2
    assert result["duplicate_ticket_count"] == 1
    assert result["red3_plus_ticket_count"] == 3
    assert result["red6_ticket_count"] == 2
    assert result["slot_hit_histogram"] == [0, 0, 0, 1, 0, 0, 2]
    assert result["unique_ticket_hit_histogram"] == [0, 0, 0, 1, 0, 0, 1]


def test_control_aggregates_keep_strategy_and_control_families_separate() -> None:
    rows = [
        {
            "strategy_family": "raw",
            "control_kind": "uniform_legal",
            "best_matched_red_count": best,
            "red3_plus_ticket_count": best - 1,
            "red4_plus_ticket_count": 0,
            "red5_plus_ticket_count": 0,
        }
        for best in (3, 5)
    ]

    result = _control_aggregates(rows)

    assert result == [
        {
            "strategy_family": "raw",
            "control_kind": "uniform_legal",
            "portfolio_count": 2,
            "mean_best_matched_red_count": 4.0,
            "mean_red3_plus_ticket_count": 3.0,
            "mean_red4_plus_ticket_count": 0.0,
            "mean_red5_plus_ticket_count": 0.0,
        }
    ]


def test_verified_checkpoint_rejects_post_outcome_payload(tmp_path: Path) -> None:
    payload = _checkpoint_payload()
    payload["outcome"] = {"red_numbers": [1, 2, 3, 4, 5, 6]}
    path = tmp_path / "checkpoint.json"
    _write_checkpoint(path, payload)

    with pytest.raises(ForwardCheckpointError, match="chronology guard"):
        _verified_checkpoint(path)


def test_verified_checkpoint_rejects_digest_mismatch(tmp_path: Path) -> None:
    payload = _checkpoint_payload()
    path = tmp_path / "checkpoint.json"
    _write_checkpoint(path, payload)
    encoded = json.loads(path.read_text(encoding="utf-8"))
    encoded["database_cutoff"] = "2026082"
    path.write_text(json.dumps(encoded), encoding="utf-8")

    with pytest.raises(ForwardCheckpointError, match="identity"):
        _verified_checkpoint(path)


def test_non_084_issue_is_not_applicable_without_database_access() -> None:
    assert settle_forward_checkpoint_if_available("2026085") == {
        "status": "not_applicable",
        "issue": "2026085",
    }


def test_084_missing_pre_outcome_checkpoint_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ForwardCheckpointError, match="checkpoint is missing"):
        settle_forward_checkpoint_if_available(
            TARGET_ISSUE,
            checkpoint_path=tmp_path / "missing.json",
        )


def test_existing_checkpoint_seal_is_idempotent_without_database_access(
    tmp_path: Path,
) -> None:
    payload = _checkpoint_payload()
    path = tmp_path / "checkpoint.json"
    _write_checkpoint(path, payload)

    result = seal_2026084_checkpoint(checkpoint_path=path)

    assert result["status"] == "already_sealed"
    assert result["checkpoint_digest"] == canonical_digest(
        payload,
        domain="dehps.2026084.forward-checkpoint.v1",
    )
