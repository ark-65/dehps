from __future__ import annotations

from dehps.forward_promotion.gate import evaluate_forward_promotion
from dehps.forward_promotion.storage import (
    FORWARD_PROMOTION_SCHEMA_SQL,
    persist_forward_promotion_decision,
)


def cohort(**overrides):
    return {
        "cohort_key": "cohort-1",
        "status": "accumulating",
        "incumbent_config_hash": "incumbent",
        "challenger_config_hash": "challenger",
        "historical_gate_passed": True,
        "min_paired_issues": 20,
        "max_losing_streak": 3,
        **overrides,
    }


def pairs(*, incumbent_ranks=None, challenger_ranks=None):
    incumbent_ranks = incumbent_ranks or [500] * 20
    challenger_ranks = challenger_ranks or [50] * 20
    rows = []
    for index, (incumbent_rank, challenger_rank) in enumerate(
        zip(incumbent_ranks, challenger_ranks, strict=True),
        start=1,
    ):
        issue = str(2026100 + index)
        common = {
            "target_issue": issue,
            "status": "evaluated",
            "candidate_count": 10000,
            "top_n": 10000,
            "leakage_passed": True,
            "red5_rank": 5000,
        }
        rows.append(
            {
                "target_issue": issue,
                "incumbent": {
                    **common,
                    "config_hash": "incumbent",
                    "model_rank": incumbent_rank,
                },
                "challenger": {
                    **common,
                    "config_hash": "challenger",
                    "model_rank": challenger_rank,
                },
            }
        )
    return rows


def test_forward_promotion_accumulates_until_frozen_minimum():
    decision = evaluate_forward_promotion(cohort(), pairs()[:19])

    assert decision["status"] == "accumulating"
    assert decision["promote"] is False
    assert decision["remaining_issue_count"] == 1


def test_forward_promotion_uses_existing_gate_and_promotes_clear_improvement():
    decision = evaluate_forward_promotion(cohort(), pairs())

    assert decision["status"] == "promoted"
    assert decision["promote"] is True
    assert decision["promotion_gate"]["accepted"] is True
    assert decision["challenger"]["primary_score"] > decision["incumbent"]["primary_score"]


def test_forward_promotion_rejects_tail_regression_even_with_primary_lift():
    decision = evaluate_forward_promotion(
        cohort(),
        pairs(
            incumbent_ranks=[500] * 20,
            challenger_ranks=[50] * 19 + [1_100_000],
        ),
    )

    assert decision["status"] == "rejected"
    assert decision["promote"] is False
    assert "tail_risk_worse" in decision["reason_codes"]


def test_forward_promotion_rejects_four_consecutive_worse_issues():
    decision = evaluate_forward_promotion(
        cohort(),
        pairs(
            incumbent_ranks=[100] * 4 + [1000] * 16,
            challenger_ranks=[200] * 4 + [50] * 16,
        ),
    )

    assert decision["promotion_gate"]["accepted"] is True
    assert decision["status"] == "rejected"
    assert decision["max_losing_streak"] == 4
    assert "consecutive_forward_worsening" in decision["reason_codes"]


def test_forward_promotion_fails_closed_on_history_or_config_identity():
    history_failure = evaluate_forward_promotion(
        cohort(historical_gate_passed=False),
        pairs(),
    )
    drift_rows = pairs()
    drift_rows[3]["challenger"]["config_hash"] = "changed"
    drift_failure = evaluate_forward_promotion(cohort(), drift_rows)

    assert history_failure["status"] == "invalid"
    assert "historical_gate_not_passed" in history_failure["blockers"]
    assert drift_failure["status"] == "invalid"
    assert "challenger_config_drift:2026104" in drift_failure["blockers"]


def test_forward_promotion_fails_closed_on_duplicate_line_for_an_issue():
    duplicate_rows = pairs()
    duplicate_rows[0]["duplicate_line_keys"] = ["static_100"]

    decision = evaluate_forward_promotion(cohort(), duplicate_rows)

    assert decision["status"] == "invalid"
    assert "duplicate_forward_lines:2026101:static_100" in decision["blockers"]


def test_forward_promotion_does_not_treat_mixed_ranking_contracts_as_model_evidence():
    mixed = pairs()
    mixed[0]["incumbent"]["ranking_contract"] = "legacy_score_partition"
    mixed[0]["challenger"]["ranking_contract"] = "strict_v1"

    decision = evaluate_forward_promotion(cohort(), mixed)

    assert decision["status"] == "invalid"
    assert "ranking_contract_mismatch:2026101" in decision["blockers"]


def test_forward_promotion_schema_has_one_active_cohort_and_durable_champion():
    assert "forward_promotion_cohorts" in FORWARD_PROMOTION_SCHEMA_SQL
    assert "idx_forward_promotion_one_accumulating" in FORWARD_PROMOTION_SCHEMA_SQL
    assert "WHERE status = 'accumulating'" in FORWARD_PROMOTION_SCHEMA_SQL
    assert "forward_champion_state" in FORWARD_PROMOTION_SCHEMA_SQL
    assert "REFERENCES forward_promotion_cohorts" in FORWARD_PROMOTION_SCHEMA_SQL


def test_duplicate_terminal_reconciliation_cannot_publish_champion(monkeypatch):
    class Result:
        rowcount = 0

    class Connection:
        def __init__(self):
            self.statements = []

        def execute(self, sql, params=None):
            self.statements.append((sql, params))
            return Result()

    connection = Connection()
    supervisor_writes = []
    monkeypatch.setattr(
        "dehps.forward_promotion.storage.upsert_training_supervisor_best",
        lambda *_args, **kwargs: supervisor_writes.append(kwargs),
    )
    value = {
        **cohort(),
        "challenger_config": {"structural_weight": 0.4},
        "challenger_summary": {"config": {"structural_weight": 0.4}},
    }

    persist_forward_promotion_decision(
        connection,
        cohort=value,
        decision={"status": "promoted", "promote": True, "paired_issue_count": 20},
    )

    assert len(connection.statements) == 1
    assert "status = 'accumulating'" in connection.statements[0][0]
    assert supervisor_writes == []
