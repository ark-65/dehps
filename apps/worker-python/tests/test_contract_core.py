from dataclasses import replace
from datetime import datetime, timezone

import pytest

from dehps.contracts import (
    ContractCompatibilityError,
    ContractRef,
    ContractRequirement,
    canonical_digest,
    canonical_json,
    require_contract_compatibility,
)


def contract(family: str = "window", version: str = "1.0.0") -> ContractRef:
    return ContractRef.from_definition(
        family=family,
        semantic_version=version,
        schema_version=f"dehps.{family}.schema.v1",
        normative_definition={"family": family, "meaning": "fixed"},
        golden_suite={"cases": [{"input": 1, "output": 1}]},
    )


def test_canonical_json_is_order_stable_and_normalizes_utc() -> None:
    first = {
        "timestamp": datetime(2026, 7, 16, 8, 30, tzinfo=timezone.utc),
        "nested": {"b": 2, "a": 1},
    }
    second = {
        "nested": {"a": 1, "b": 2},
        "timestamp": datetime(2026, 7, 16, 8, 30, tzinfo=timezone.utc),
    }

    assert canonical_json(first) == canonical_json(second)
    assert canonical_digest(first, domain="test") == canonical_digest(second, domain="test")
    assert '"timestamp":"2026-07-16T08:30:00Z"' in canonical_json(first)


def test_canonical_json_rejects_unordered_or_nonfinite_payloads() -> None:
    with pytest.raises(TypeError, match="unordered"):
        canonical_json({"values": {1, 2}})
    with pytest.raises(ValueError, match="finite"):
        canonical_json({"value": float("nan")})
    with pytest.raises(ValueError, match="timezone"):
        canonical_json({"timestamp": datetime(2026, 7, 16, 8, 30)})


def test_contract_identity_is_stable_and_semver_does_not_grant_compatibility() -> None:
    dependency = contract("history_snapshot", "1.0.0")
    consumer = contract("window", "1.0.0")
    requirement = ContractRequirement.exact(dependency)
    require_contract_compatibility(
        consumer=consumer,
        dependency=dependency,
        requirement=requirement,
    )

    same_major_but_undeclared = contract("history_snapshot", "1.1.0")
    with pytest.raises(ContractCompatibilityError) as error:
        require_contract_compatibility(
            consumer=consumer,
            dependency=same_major_but_undeclared,
            requirement=requirement,
        )

    assert error.value.code == "unsupported_contract_version"


def test_contract_normative_digest_mismatch_fails_closed() -> None:
    dependency = contract("history_snapshot")
    consumer = contract("window")
    requirement = ContractRequirement.exact(dependency)
    mismatched = replace(dependency, normative_digest="0" * 64)

    with pytest.raises(ContractCompatibilityError) as error:
        require_contract_compatibility(
            consumer=consumer,
            dependency=mismatched,
            requirement=requirement,
        )

    assert error.value.code == "contract_normative_digest_mismatch"
    assert error.value.as_dict()["dependency"]["normative_digest"] == "0" * 64


def test_golden_suite_revision_does_not_change_normative_identity() -> None:
    original = contract("window")
    expanded_suite = replace(original, golden_suite_digest="0" * 64)

    assert original != expanded_suite
    assert original.normatively_equals(expanded_suite)
