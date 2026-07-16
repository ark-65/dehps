"""Executable contract primitives shared by DEHPS control-plane stages."""

from dehps.contracts.core import (
    ContractCompatibilityError,
    ContractRef,
    ContractRequirement,
    canonical_digest,
    canonical_json,
    require_contract_compatibility,
)

__all__ = [
    "ContractCompatibilityError",
    "ContractRef",
    "ContractRequirement",
    "canonical_digest",
    "canonical_json",
    "require_contract_compatibility",
]
