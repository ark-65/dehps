from dehps.training.persistence_policy import (
    READ_ONLY_PGOPTION,
    apply_observability_only_database_guard,
    apply_read_only_database_guard,
    training_persistence_policy,
)


def test_observability_only_database_guard_is_fail_closed_and_idempotent(monkeypatch):
    monkeypatch.setenv("PGOPTIONS", "-c statement_timeout=60000")

    first = apply_observability_only_database_guard(True)
    second = apply_observability_only_database_guard(True)

    assert first == "postgres_default_transaction_read_only"
    assert second == first
    assert READ_ONLY_PGOPTION in __import__("os").environ["PGOPTIONS"]
    assert __import__("os").environ["PGOPTIONS"].count(
        "default_transaction_read_only=on"
    ) == 1


def test_normal_mode_does_not_change_postgres_options(monkeypatch):
    monkeypatch.setenv("PGOPTIONS", "-c statement_timeout=60000")

    assert apply_observability_only_database_guard(False) == "disabled"
    assert __import__("os").environ["PGOPTIONS"] == "-c statement_timeout=60000"


def test_research_lane_uses_the_same_fail_closed_database_guard(monkeypatch):
    monkeypatch.delenv("PGOPTIONS", raising=False)

    assert apply_read_only_database_guard(True) == "postgres_default_transaction_read_only"
    assert READ_ONLY_PGOPTION in __import__("os").environ["PGOPTIONS"]


def test_observability_only_policy_disables_every_external_write_surface():
    policy = training_persistence_policy(True)

    assert policy == {
        "database_writes": False,
        "prediction_refresh": False,
        "training_event_posts": False,
        "local_status_and_report_writes": True,
        "database_guard": "postgres_default_transaction_read_only",
        "skipped_rounds": [],
    }
