from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from dehps.contracts import canonical_digest


PREREGISTRATION_DIGEST_DOMAIN = "dehps.m4-information-theory.preregistration.v1"
DECISION_POLICY_DIGEST_DOMAIN = "dehps.m4-information-theory.decision-policy.v1"
CONFIG_DIGEST_DOMAIN = "dehps.m4-information-theory.config.v1"
CONTRACT_DIGEST_DOMAIN = "dehps.m4-information-theory.contract.v1"


def _without_self_digest(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(dict(payload))
    normalized.pop("artifact_digest", None)
    return normalized


def preregistration_digest(payload: Mapping[str, Any]) -> str:
    return canonical_digest(
        _without_self_digest(payload),
        domain=PREREGISTRATION_DIGEST_DOMAIN,
    )


def decision_policy_digest(payload: Mapping[str, Any]) -> str:
    return canonical_digest(
        _without_self_digest(payload),
        domain=DECISION_POLICY_DIGEST_DOMAIN,
    )


def config_digest(payload: Mapping[str, Any]) -> str:
    return canonical_digest(
        _without_self_digest(payload),
        domain=CONFIG_DIGEST_DOMAIN,
    )


def information_theory_contract_digest(payload: Mapping[str, Any]) -> str:
    return canonical_digest(
        _without_self_digest(payload),
        domain=CONTRACT_DIGEST_DOMAIN,
    )
