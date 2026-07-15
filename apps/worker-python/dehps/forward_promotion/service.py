from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from psycopg import Connection

from dehps.db import get_connection
from dehps.forward_promotion.gate import evaluate_forward_promotion
from dehps.forward_promotion.storage import (
    load_active_forward_promotion_cohort,
    load_forward_promotion_pairs,
    persist_forward_promotion_decision,
)


ConnectionFactory = Callable[[], AbstractContextManager[Connection[Any]]]


def reconcile_forward_promotion(
    *, connection_factory: ConnectionFactory = get_connection,
) -> dict[str, Any]:
    with connection_factory() as conn:
        cohort = load_active_forward_promotion_cohort(conn)
        if cohort is None:
            return {"status": "no_active_cohort", "promote": False}
        pairs = load_forward_promotion_pairs(conn, cohort)
        decision = evaluate_forward_promotion(cohort, pairs)
        persist_forward_promotion_decision(conn, cohort=cohort, decision=decision)
        return {"cohort_key": cohort["cohort_key"], **decision}
