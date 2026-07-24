from __future__ import annotations

from typing import Any, Mapping

from .digest import decision_policy_digest
from .enums import DecisionState


DECISION_PRIORITY = (
    DecisionState.REPAIR_MEASUREMENT_SYSTEM.value,
    DecisionState.SUPPORTED_WEAK_SIGNAL.value,
    DecisionState.PRACTICALLY_UNPREDICTABLE.value,
    DecisionState.INCONCLUSIVE_DUE_TO_POWER.value,
)


def decision_policy_identity(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": payload["version"],
        "digest": decision_policy_digest(payload),
        "priority": list(DECISION_PRIORITY),
    }
