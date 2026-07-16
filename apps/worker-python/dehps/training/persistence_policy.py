from __future__ import annotations

import os


READ_ONLY_PGOPTION = "-c default_transaction_read_only=on"


def apply_read_only_database_guard(enabled: bool) -> str:
    """Make every new libpq connection fail closed on attempted writes."""
    if not enabled:
        return "disabled"
    current = os.environ.get("PGOPTIONS", "").strip()
    if "default_transaction_read_only=on" not in current:
        os.environ["PGOPTIONS"] = " ".join(
            part for part in (current, READ_ONLY_PGOPTION) if part
        )
    return "postgres_default_transaction_read_only"


def apply_observability_only_database_guard(enabled: bool) -> str:
    """Backward-compatible name for the shared read-only execution guard."""
    return apply_read_only_database_guard(enabled)


def training_persistence_policy(observability_only: bool) -> dict:
    return {
        "database_writes": not observability_only,
        "prediction_refresh": not observability_only,
        "training_event_posts": not observability_only,
        "local_status_and_report_writes": True,
        "database_guard": (
            "postgres_default_transaction_read_only"
            if observability_only
            else "disabled"
        ),
        "skipped_rounds": [],
    }
